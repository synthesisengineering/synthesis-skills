#!/usr/bin/env python3
"""Fetch an AI-generated meeting transcript (Gemini notes + full word-for-word transcript)
from Google Drive via a self-hosted workspace-mcp server, and save to the project's local
transcript archive. Standard library only.

Cross-platform: macOS, Linux, Windows.

Usage:
  fetch-meeting.py [MEETING-NAME] [--date YYYY-MM-DD] [--account EMAIL]
  fetch-meeting.py --window FROM THROUGH        # which docs in the window are saved, and how far the watermark may move

Examples:
  fetch-meeting.py                      # today's standup (default)
  fetch-meeting.py standup              # today's standup
  fetch-meeting.py standup --date 2026-04-21
  fetch-meeting.py "PDE Leadership"     # uses generic_pattern from config
  fetch-meeting.py standup --account me@work.example.com   # override account
  fetch-meeting.py --window 2026-10-01 2026-10-05

Config: reads .agents/meeting-transcripts.yaml starting from CWD and walking up.
Falls back to .claude/meeting-transcripts.yaml for existing projects.

The transcript is chosen by the document's own tab ID (`--transcript-tab-id`, or config
`transcript_tab_id`), else by a tab title (config `transcript_tab_title`, default "Transcript")
that exactly one tab in a complete tab list carries. A tool error is "unknown", never "no
transcript". Exit 0 saved and verified; 1 not found, unknown or incomplete; 2 bad usage.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2]))  # the plugin root, which holds synthesis/
import mcp_client  # noqa: E402
import verify_transcripts  # noqa: E402
from synthesis.yamlish import load_mapping  # noqa: E402

DOC_TYPE = "application/vnd.google-apps.document"
PAGE_SIZE = 100
call = lambda url, account, tool, **args: mcp_client.call_tool(tool, {"user_google_email": account, **args}, url, "fetch-meeting.py")
modified_in = lambda start, through: f'modifiedTime > "{start}T00:00:00" and modifiedTime < "{through + dt.timedelta(days=1)}T00:00:00"'

# --- Config loading (the plugin's YAML reader, synthesis/yamlish.py) ---


def find_config() -> Path:
    """Walk up from CWD looking for meeting-transcripts.yaml config."""
    d = Path.cwd().resolve()
    while d != d.parent:
        for config_dir in (".agents", ".claude"):
            candidate = d / config_dir / "meeting-transcripts.yaml"
            if candidate.exists():
                return candidate
        d = d.parent
    raise FileNotFoundError(
        "No .agents/meeting-transcripts.yaml or .claude/meeting-transcripts.yaml "
        "found in current tree. "
        "See synthesis-meeting-transcripts/references/setup.md for the schema."
    )


def load_config(path: Path) -> dict:
    cfg = load_mapping(path.read_text(encoding="utf-8"), str(path))
    required = ["workspace", "google_account", "transcripts_path", "transcripts_repo"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        raise ValueError(f"Config {path} missing required keys: {missing}; see references/setup.md")
    cfg["transcripts_repo"] = str(Path(cfg["transcripts_repo"]).expanduser())
    return cfg


def resolve_pattern(cfg: dict, meeting: str) -> str:
    """Look up meeting_patterns[name], else substitute into generic_pattern."""
    patterns = cfg.get("meeting_patterns") or {}
    if meeting in patterns:
        return patterns[meeting]
    generic = cfg.get("generic_pattern") or 'name contains "{{name}}" and name contains "Notes by Gemini"'
    return generic.replace("{{name}}", meeting)


def slugify(name: str) -> str:
    s = re.sub(r"[^\w\s-]", "", name.lower()).strip()
    return re.sub(r"[\s_-]+", "-", s)


def server_reachable(url: str) -> bool:
    try:
        with mcp_client.OPENER.open(urllib.request.Request(url.rsplit("/mcp", 1)[0] + "/health"), timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


# --- Tabs: chosen by stable ID; every way of not finding one has its own reason (IR-57) ---------


def tab_inventory(text: str, file_id: str) -> tuple:
    """(tabs, complete) from inspect_doc_structure's JSON. Unparseable is not "no tabs"."""
    head = f"Document structure analysis for {file_id}:"
    body = text.split(head, 1)[1] if head in text else text
    body = body.rsplit("\n\nLink: ", 1)[0].strip()
    try:
        document = mcp_client.strict_json(body)
    except ValueError:
        return None, False
    if not isinstance(document, dict) or not isinstance(document.get("tabs"), list):
        return None, False
    complete = document.get("tabsComplete", True) is True and document.get("truncated", False) is False \
        and not document.get("nextPageToken")
    tabs, pending = [], list(document["tabs"])
    while pending:
        tab = pending.pop(0)
        tab_id = tab.get("tab_id", tab.get("tabId")) if isinstance(tab, dict) else None
        if not isinstance(tab_id, str) or not tab_id or any(t["tab_id"] == tab_id for t in tabs) or len(tabs) > 1000:
            raise ValueError("missing or duplicate tab ID")
        tabs.append({"tab_id": tab_id, "title": str(tab.get("title", ""))})
        pending.extend(tab.get("child_tabs", tab.get("childTabs", [])) or [])
    return tabs, complete


def select_transcript(tabs, complete: bool, tab_id: str | None = None, title: str | None = None) -> dict:
    """Which tab holds the transcript. status: transcript, no-source or unknown, with a reason."""
    if tabs is None:
        return {"status": "unknown", "reason": "tab-inventory-unavailable"}
    if not complete:
        return {"status": "unknown", "reason": "tab-inventory-incomplete"}
    if tab_id:
        chosen = [t for t in tabs if t["tab_id"] == tab_id]
    else:
        chosen = [t for t in tabs if t["title"] == (title or "Transcript")]
        if len(chosen) > 1:
            return {"status": "unknown", "reason": "transcript-tab-title-not-unique"}
    if not chosen:
        return {"status": "no-source", "reason": "transcript-tab-absent"}  # only a complete inventory can say this
    return {"status": "transcript", "reason": None, "transcript_tab_id": chosen[0]["tab_id"]}


def fetch_document(url: str, account: str, file_id: str, tab_id: str | None, title: str | None) -> dict:
    try:
        structure = call(url, account, "inspect_doc_structure", document_id=file_id)
        try:
            tabs, complete = tab_inventory(structure, file_id)
        except ValueError as exc:
            return {"status": "unknown", "reason": "tab-inventory-unavailable", "detail": str(exc)}
        result = select_transcript(tabs, complete, tab_id, title)
        if result["status"] == "unknown":
            return result
        texts = {t["tab_id"]: call(url, account, "get_doc_as_markdown", document_id=file_id, tab_id=t["tab_id"],
                                   include_comments=False) for t in tabs}
    except ValueError as exc:  # an error is "unknown", never "no transcript"
        return {"status": "unknown", "reason": "tool-error", "detail": str(exc)}
    chosen = result.get("transcript_tab_id")
    result["notes"] = "\n\n".join(f"### {t['title']}\n\n{texts[t['tab_id']]}" for t in tabs if t["tab_id"] != chosen)
    result["transcript"] = texts.get(chosen, "")
    if result["status"] == "transcript" and not result["transcript"].strip():
        result.update(status="no-source", reason="transcript-tab-empty")
    return result


# --- The window: every source doc, saved or not (IR-55) ---------------------------------------


ROW = re.compile(r'Name: "(?P<name>[^"\n]*)" \(ID: (?P<id>[A-Za-z0-9_-]+)(?:, Type: (?P<type>[^,)]+))?'
                 r'(?:[^)\n]*?Created: (?P<created>[0-9T:.+\-Z]+))?(?:[^)\n]*?Modified: (?P<modified>[0-9T:.+\-Z]+))?')
MARGIN_HOURS = 2  # this check reads Drive, never a calendar; on 2026-10-08 it passed two meetings still under way


def saved_ids(meetings: Path) -> dict:
    """Doc ID to saved file: a `**Source ID:**` header, a Google Doc link, or a `> Source:` line's first backticked ID."""
    found = {}
    for path in sorted(meetings.glob("*.md")) if meetings.is_dir() else []:
        head = path.read_text(encoding="utf-8", errors="replace")[:4000]
        for doc_id in re.findall(r"(?:google-drive:|/document/d/)([A-Za-z0-9_-]+)|^>[ \t]*Source:[^\n]*?`([A-Za-z0-9_-]+)`", head, re.M):
            found.setdefault(doc_id[0] or doc_id[1], path.name)
    return found


def window(url: str, cfg: dict, account: str, start: dt.date, through: dt.date, now: dt.datetime | None = None) -> dict:
    """The window's docs, saved or not, by declared pattern and as `undeclared`, and the earliest moment that holds the bookmark."""
    now = (now or dt.datetime.now().astimezone()).replace(microsecond=0)
    generic = resolve_pattern(cfg, "Notes by Gemini")
    patterns = cfg.get("meeting_patterns") or {"(generic)": generic}
    saved, docs, bounded = saved_ids(Path(cfg["transcripts_repo"]) / cfg["transcripts_path"] / "meetings"), {}, []
    for name, pattern in list(patterns.items()) + ([("(undeclared)", generic)] if "(generic)" not in patterns else []):
        text = call(url, account, "search_drive_files", query=f"{pattern} and {modified_in(start, through)}",
                    page_size=PAGE_SIZE, detailed=True)
        rows = [m.groupdict() for m in ROW.finditer(text)]
        if len(rows) >= PAGE_SIZE or "nextPageToken:" in text or "incompleteSearch" in text:
            bounded.append(name)  # more may exist: the listing cannot be called complete
        for row in rows:
            if row["type"] in (None, DOC_TYPE):
                docs.setdefault(row["id"], {**row, "pattern": name, "saved": saved.get(row["id"])})
    listed = sorted(docs.values(), key=lambda d: d["modified"] or "")
    unsaved = [d for d in listed if not d["saved"] and d["pattern"] in patterns]
    holds = [(dt.datetime.combine(through, dt.time(23, 59, 59), dt.timezone.utc), "the window's end, in UTC as Drive reads it"),
             (now - dt.timedelta(hours=MARGIN_HOURS), f"{MARGIN_HOURS} hours before the run: a meeting under way may have no doc yet")]
    holds += [(dt.datetime.fromisoformat(d["created"].replace("Z", "+00:00")) - dt.timedelta(seconds=1),
               f"just before unsaved doc {d['id']} was created") for d in unsaved if d["created"]]
    at, why = min(holds) if not set(bounded) & set(patterns) and all(d["created"] for d in unsaved) else (
        None, "a declared search may hide more docs, or an unsaved doc has no creation time")
    return {"from": start.isoformat(), "through": through.isoformat(), "checked_at": now.isoformat(), "searched": patterns,
            "scope": f"Only these patterns were searched: {', '.join(patterns)}. A doc none of them matches is not in `documents` "
                     "and advance_through does not cover it; `undeclared` lists the Gemini notes docs no declared pattern found.",
            "documents": [d for d in listed if d["pattern"] in patterns], "unsaved": [d["id"] for d in unsaved],
            "undeclared": [d for d in listed if d["pattern"] not in patterns], "bounded_patterns": bounded,
            "advance_through": at and at.astimezone(now.tzinfo).replace(microsecond=0).isoformat(), "advance_reason": why,
            "note": "the search shows what Drive returned; it cannot prove the listing complete"}


def save(out_file: Path, text: str, force: bool) -> None:
    text = verify_transcripts.redact_image_keys(text)  # an image's access key never reaches the repository
    if out_file.exists():
        if out_file.read_text(encoding="utf-8") == text:
            return
        if not force:
            raise FileExistsError(f"{out_file} exists with different content; use --force to replace it")
        out_file.rename(out_file.with_name(f"{out_file.stem}.old-{dt.datetime.now():%Y%m%d%H%M%S}.md"))
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(text, encoding="utf-8")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("meeting", nargs="?", default="standup", help="Meeting name (default: standup)")
    p.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    p.add_argument("--account", default=None, help="Override google_account from config")
    p.add_argument("--transcript-tab-id", help="the document's own stable tab ID, never a title match")
    p.add_argument("--window", nargs=2, metavar=("FROM", "THROUGH"), help="list the window's docs, saved and unsaved")
    p.add_argument("--force", action="store_true", help="Replace a saved transcript (the old one is kept as .old-*.md)")
    p.add_argument("--port", type=int, default=int(os.environ.get("WORKSPACE_MCP_PORT", 8765)))
    args = p.parse_args(argv)
    try:
        cfg = load_config(find_config())
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    account = args.account or cfg["google_account"]
    mcp_url = f"http://localhost:{args.port}/mcp"
    if not server_reachable(mcp_url):
        print(f"ERROR: workspace-mcp not reachable at {mcp_url}", file=sys.stderr)
        print("       Run ./start.sh or verify server status.", file=sys.stderr)
        return 1

    if args.window:
        try:
            listing = window(mcp_url, cfg, account, dt.date.fromisoformat(args.window[0]), dt.date.fromisoformat(args.window[1]))
        except ValueError as exc:
            print(json.dumps({"coverage": "unknown", "reason": str(exc)}))
            return 1
        print(json.dumps(listing, indent=2))
        return 1 if listing["unsaved"] or not listing["advance_through"] else 0

    target_date = args.date or dt.date.today().isoformat()
    start = dt.date.fromisoformat(target_date)
    pattern = resolve_pattern(cfg, args.meeting)
    query = f"{pattern} and {modified_in(start, start)}"
    print(f"Searching Drive ({account}) for: {args.meeting} on {target_date}")
    print(f"  Pattern: {pattern}")
    try:
        search = call(mcp_url, account, "search_drive_files", query=query, page_size=5)
    except ValueError as exc:
        print(f"ERROR: search failed, coverage unknown: {exc}", file=sys.stderr)
        return 1
    ids = sorted(set(re.findall(r"ID:\s*([A-Za-z0-9_-]+)", search)))
    if len(ids) != 1:
        print(f"{'No matching doc' if not ids else 'More than one doc'} found for '{args.meeting}' on {target_date} "
              f"in {account}'s Drive: {', '.join(ids) or 'none'}", file=sys.stderr)
        print(f"Query tried: {query}", file=sys.stderr)
        return 1
    file_id = ids[0]
    print(f"Found doc: {file_id}")
    selected = fetch_document(mcp_url, account, file_id, args.transcript_tab_id or cfg.get("transcript_tab_id"),
                              cfg.get("transcript_tab_title"))
    if selected["status"] == "unknown":
        print(json.dumps({k: v for k, v in selected.items() if k not in ("notes", "transcript")}), file=sys.stderr)
        return 1
    if selected["status"] == "no-source":
        body = ("⚠️ summary-only — no verbatim transcript in the document.\n\n<!-- VERIFIER: no-source-transcript --> "
                f"{selected['reason']}\n\n## Tool notes — lossy derivative\n\n{selected['notes']}")
        print(f"WARNING: {selected['reason']}; the saved notes are not primary transcript evidence.", file=sys.stderr)
    else:
        body = f"## Tool notes — lossy derivative\n\n{selected['notes']}\n\n## Verbatim transcript\n\n{selected['transcript']}"
    human = f"{start.strftime('%A')}, {start.strftime('%B')} {start.day}, {start.year}"
    header = (f"# {args.meeting.title()} — {human}\n\n"
              f"**Source:** Gemini meeting notes + full transcript\n"
              f"**Google Doc:** https://docs.google.com/document/d/{file_id}/edit\n"
              f"**Source ID:** google-drive:{file_id}\n"
              f"**Transcript tab ID:** {selected.get('transcript_tab_id') or 'none'}\n"
              f"**Fetched via:** workspace-mcp ({account}) — {dt.date.today().isoformat()}\n\n---\n\n")
    out_file = Path(cfg["transcripts_repo"]) / cfg["transcripts_path"] / "meetings" / f"{slugify(args.meeting)}-{target_date}.md"
    try:
        save(out_file, header + body, args.force)
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    audit = verify_transcripts.audit_files([out_file])[0]
    print(json.dumps({"saved": str(out_file), "verification": audit["status"]}))
    return 0 if audit["status"] in ("OK", "OK (no-source-transcript)") else 1


if __name__ == "__main__":
    sys.exit(main())
