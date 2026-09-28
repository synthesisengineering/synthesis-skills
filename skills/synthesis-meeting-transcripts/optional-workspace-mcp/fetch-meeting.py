#!/usr/bin/env python3
"""Fetch an AI-generated meeting transcript (Gemini notes + full word-for-word transcript)
from Google Drive via a self-hosted workspace-mcp server, and save to the project's local
transcript archive.

Cross-platform: macOS, Linux, Windows.

Usage:
  fetch-meeting.py [MEETING-NAME] [--date YYYY-MM-DD] [--account EMAIL]

Examples:
  fetch-meeting.py                      # today's standup (default)
  fetch-meeting.py standup              # today's standup
  fetch-meeting.py standup --date 2026-04-21
  fetch-meeting.py "PDE Leadership"     # uses generic_pattern from config
  fetch-meeting.py standup --account me@work.example.com   # override account

Config: reads .agents/meeting-transcripts.yaml starting from CWD and walking up.
Falls back to .claude/meeting-transcripts.yaml for existing projects.

Use the verified synthesis exec-public entry. Its pinned interpreter requires
httpx and PyYAML; see the acquisition entry reference for explicit setup.
"""

from __future__ import annotations

import argparse
import time

try:
    import fcntl
except ImportError:
    fcntl = None
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

try:
    import httpx
    import yaml
except ImportError as exc:
    print(
        f"Missing dependency in the verified interpreter: {exc.name}.", file=sys.stderr
    )
    print(
        "Install httpx and PyYAML into the selected interpreter through authorized environment setup; do not select an unverified interpreter.",
        file=sys.stderr,
    )
    sys.exit(2)


sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp_client import (
    call_tool_text,
    _parse_sse,
    bounded_post,
    _init_session,
    session_headers,
)
from document_tabs import select_tabs

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_transcripts

# --- Config loading -----------------------------------------------------------


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
        "See synthesis-meeting-transcripts/SKILL.md for the schema."
    )


def load_config(path: Path) -> dict:
    with path.open() as f:
        cfg = yaml.safe_load(f)
    # v0.2.0 schema (2026-04-22): transcripts_repo replaces ai_knowledge_repo
    # to align with synthesis-slack-sync v2.0.0+ and the workspace-rooted layout.
    required = ["workspace", "google_account", "transcripts_path", "transcripts_repo"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        # Backward-compat hint: if someone has v1.x schema (ai_knowledge_repo),
        # tell them what to rename.
        if cfg.get("ai_knowledge_repo") and "transcripts_repo" in missing:
            raise ValueError(
                f"Config {path} uses pre-v0.2.0 schema (ai_knowledge_repo). "
                "Rename ai_knowledge_repo to transcripts_repo and set it to the "
                "absolute path of the workspace-private repo. See the SKILL.md "
                "for the current schema."
            )
        raise ValueError(f"Config {path} missing required keys: {missing}")
    cfg["transcripts_repo"] = str(Path(cfg["transcripts_repo"]).expanduser())
    return cfg


# --- MCP HTTP client ----------------------------------------------------------


def mcp_call(url: str, tool: str, args: dict, *, capture=None) -> str:
    """Call an MCP tool over HTTP streamable transport, return concatenated text content."""
    with httpx.Client(timeout=60, follow_redirects=False, trust_env=False) as c:
        sid = _init_session(c, url=url, capture=capture, client_name="fetch-meeting.py")
        r = bounded_post(
            c,
            url,
            capture=capture,
            headers=session_headers(sid),
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": tool, "arguments": args},
            },
        )
    r.raise_for_status()
    return call_tool_text(_parse_sse(r.text))


def server_reachable(url: str) -> bool:
    try:
        base = url.rsplit("/mcp", 1)[0]
        r = httpx.get(f"{base}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


# --- Pattern resolution -------------------------------------------------------


def resolve_pattern(cfg: dict, meeting: str) -> str:
    """Look up meeting_patterns[name], else substitute into generic_pattern."""
    patterns = cfg.get("meeting_patterns") or {}
    if meeting in patterns:
        return patterns[meeting]
    generic = (
        cfg.get("generic_pattern")
        or 'name contains "{{name}}" and name contains "Notes by Gemini"'
    )
    return generic.replace("{{name}}", meeting)


# --- File IO helpers ----------------------------------------------------------


def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^\w\s-]", "", s).strip()
    s = re.sub(r"[\s_-]+", "-", s)
    return s


def extract_content(raw: str) -> str:
    """Strip the workspace-mcp 'File: ... --- CONTENT ---' header, return body only."""
    marker = "--- CONTENT ---"
    if marker in raw:
        return raw.split(marker, 1)[1].lstrip("\n")
    return raw


def inventory_documents(
    list_documents, *, source, account, start, through, positive_control, max_pages=100
):
    """Enumerate all declared source documents using an owner-bound adapter.

    Adapter response is {ok, documents:[{source_id, occurred_at}], next_cursor,
    complete, tool_call_id}. occurred_at is the configured source's explicit
    window timestamp, never inferred from title or file ordering. Raw response
    preservation belongs to the caller. No source is omitted for relevance.
    """
    if (
        start.tzinfo is None
        or through.tzinfo is None
        or start > through
        or not 1 <= max_pages <= 100
    ):
        raise ValueError("invalid source inventory window or page bound")
    sys.path.insert(
        0, str(Path(__file__).resolve().parents[2] / "synthesis-daily-rituals/scripts")
    )
    from acquisition_evidence import validate_recorder_control

    validate_recorder_control(
        positive_control,
        source=source,
        account=account,
        after=through,
        now=dt.datetime.now().astimezone(),
    )
    cursor = None
    seen = set()
    docs = []
    ids = set()
    calls = []
    deadline = time.monotonic() + 120
    for _ in range(max_pages):
        if time.monotonic() >= deadline:
            raise ValueError("source inventory time bound reached")
        page = list_documents(
            source=source,
            account=account,
            oldest=start.isoformat(),
            latest=through.isoformat(),
            cursor=cursor,
            limit=100,
        )
        if time.monotonic() >= deadline:
            raise ValueError("source inventory time bound reached")
        if not isinstance(page, dict) or page.get("ok") is not True:
            raise ValueError("source inventory failed; coverage unknown")
        call_id = page.get("tool_call_id")
        if not isinstance(call_id, str) or not call_id:
            raise ValueError("source inventory raw provenance missing")
        calls.append(call_id)
        rows = page.get("documents")
        if not isinstance(rows, list) or len(rows) > 1000:
            raise ValueError("source inventory page invalid")
        for row in rows:
            key = row.get("source_id")
            at = dt.datetime.fromisoformat(row.get("occurred_at"))
            if (
                not isinstance(key, str)
                or not key
                or key in ids
                or at.tzinfo is None
                or not start <= at <= through
            ):
                raise ValueError(
                    "source inventory duplicate ID or invalid window timestamp"
                )
            docs.append(row)
            ids.add(key)
            if len(docs) > 10000:
                raise ValueError("source document bound reached")
        next_cursor = page.get("next_cursor")
        if next_cursor not in (None, "") and not isinstance(next_cursor, str):
            raise ValueError("source inventory invalid pagination cursor")
        if next_cursor is None or next_cursor == "":
            if page.get("complete") is not True:
                raise ValueError("source inventory completion unknown")
            return {
                "documents": docs,
                "complete": True,
                "next_cursor": None,
                "from": start.isoformat(),
                "through": through.isoformat(),
                "observed_at": dt.datetime.now().astimezone().isoformat(),
                "positive_control": positive_control,
                "tool_call_id": calls[-1],
                "tool_call_ids": calls,
            }
        if not isinstance(next_cursor, str) or next_cursor in seen:
            raise ValueError("source inventory repeated cursor")
        seen.add(next_cursor)
        cursor = next_cursor
    raise ValueError("source inventory page bound reached; coverage unknown")


def recorder_readiness(cfg, mcp_url, account, *, call=None):
    """Perform a declared read-only identity probe, distinct from server health.

    The connector adapter must return authenticated/account fields; text-only,
    expired, and mismatched-account responses remain unknown/refused. Tool
    semantics are declared by the owner configuration, never guessed by name.
    """
    call = call or mcp_call
    probe = cfg.get("recorder_probe")
    if (
        not isinstance(probe, dict)
        or probe.get("semantics") != "authentication-read-only"
    ):
        raise ValueError(
            "recorder sign-in unknown: owner-declared read-only probe missing"
        )
    if (
        not isinstance(probe.get("tool"), str)
        or not probe["tool"]
        or not isinstance(probe.get("arguments", {}), dict)
    ):
        raise ValueError("invalid recorder identity probe")
    payload = json.loads(call(mcp_url, probe["tool"], probe.get("arguments", {})))
    if (
        not isinstance(payload, dict)
        or payload.get("authenticated") is not True
        or payload.get("account") != account
        or not isinstance(payload.get("tool_call_id"), str)
        or not payload["tool_call_id"].strip()
    ):
        raise ValueError("recorder sign-in failed or account mismatch")
    return {
        "status": "authenticated",
        "account": account,
        "observed_at": dt.datetime.now().astimezone().isoformat(),
        "tool": probe["tool"],
        "tool_call_id": payload["tool_call_id"],
        "native_acceptance": False,
    }


def save_verified(path, content, *, force=False):
    sys.path.insert(
        0, str(Path(__file__).resolve().parents[2] / "synthesis-daily-rituals/scripts")
    )
    from archive_publish import _publish

    def validate(target, digest):
        return verify_transcripts.audit_files(
            [target], expected_hashes={str(target): digest}
        )

    return _publish(path, content, validate=validate, force=force)


def acquire_window(
    cfg,
    *,
    mode,
    through,
    backfill,
    capture_root,
    evidence_path=None,
    advance=False,
    force=False,
    home=None,
):
    """Actual declared acquisition → exact archives → existing watermark owner."""
    sys.path.insert(
        0, str(Path(__file__).resolve().parents[2] / "synthesis-daily-rituals/scripts")
    )
    from acquisition_transport import Capture, ReadTransport, output_path
    from archive_publish import publish_json
    import sync_watermark
    from acquisition_evidence import moment, validate
    from google_read import GoogleRead

    if mode not in {"health", "inventory", "fetch"} or advance and mode != "fetch":
        raise ValueError("invalid acquisition mode or advance intent")
    if mode == "fetch":
        evidence_path = output_path(evidence_path)
    output_path(capture_root, directory=True)
    now = dt.datetime.now().astimezone()
    through = sync_watermark.parse_moment(through, dt.datetime.now().astimezone())
    if through > now:
        raise ValueError("future acquisition window")
    relative_archive = Path(cfg["transcripts_path"])
    if (
        relative_archive.is_absolute()
        or ".." in relative_archive.parts
        or not Path(cfg["transcripts_repo"]).is_absolute()
    ):
        raise ValueError(
            "archive configuration must name an absolute repository and relative transcript path"
        )
    output_path(Path(cfg["transcripts_repo"]) / relative_archive, directory=True)
    workspace = cfg["workspace"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", workspace):
        raise ValueError("invalid workspace identity")
    window = sync_watermark.window(workspace, "meetings", now=through, home=home)
    start = moment(window["from"] or backfill)
    if start > through:
        raise ValueError("invalid acquisition window")
    # Validate all non-secret contract fields before resolving a credential.
    adapter = GoogleRead(cfg, None)
    capture = Capture(capture_root)
    transport = ReadTransport(cfg["acquisition_adapter"].get("token"), capture)
    adapter.transport = transport
    try:
        readiness = adapter.readiness()
        health = {
            "dependencies": "available",
            "transport": "responsive",
            "recorder": readiness,
            "native_acceptance": False,
        }
        if mode == "health":
            return health
        control = adapter.positive_control()
        inventory = inventory_documents(
            adapter.list_documents,
            source="google-drive",
            account=cfg["google_account"],
            start=start,
            through=through,
            positive_control=control,
        )
        if mode == "inventory":
            return {
                "health": health,
                "inventory": inventory,
                "custody": capture.summary(include_receipts=False),
                "can_advance": False,
            }
        archive_root = Path(cfg["transcripts_repo"]) / cfg["transcripts_path"]
        if not archive_root.is_absolute() or ".." in archive_root.parts:
            raise ValueError("archive root must be a physical absolute path")
        receipts = []
        for doc in inventory["documents"]:
            raw, call = adapter.document(doc["source_id"])
            selected = select_tabs(
                json.dumps(raw), transcript_tab_id=cfg["transcript_tab_id"]
            )
            if selected["status"] != "transcript":
                raise ValueError(
                    "declared transcript unavailable: "
                    + str(selected["reason"])
                    + "; raw notes retained in custody"
                )
            content = (
                f"# Meeting source {doc['source_id']}\n\n**Source ID:** google-drive:{doc['source_id']}\n"
                f"**Transcript tab ID:** {cfg['transcript_tab_id']}\n**Raw response SHA256:** {call.rsplit('#', 1)[1]}\n\n"
                "## Tool notes — lossy derivative\n\n"
                + selected["notes"]
                + "\n\n## Verbatim transcript\n\n"
                + selected["transcript"]
            )
            filename = "meetings/" + doc["source_id"] + ".md"
            saved = save_verified(archive_root / filename, content, force=force)
            receipts.append({"path": filename, "sha256": saved["sha256"]})
        evidence = {
            "schema": 1,
            "workspace": workspace,
            "surface": "meetings",
            "from": start.isoformat(),
            "through": through.isoformat(),
            "archive_root": str(archive_root),
            "archives": receipts,
            "declared_sources": ["google-drive"],
            "sources": [
                {
                    "id": "google-drive",
                    "account": cfg["google_account"],
                    "readiness": readiness,
                    "inventory": inventory,
                }
            ],
            "custody": capture.summary(),
        }
        checked = validate(
            evidence,
            workspace=workspace,
            surface="meetings",
            through=through,
            previous=moment(window["from"]) if window["from"] else None,
        )
        if not evidence_path:
            raise ValueError("fetch requires an exact evidence output path")
        saved_evidence = publish_json(evidence_path, evidence)
        result = {
            "coverage": checked,
            "evidence": saved_evidence,
            "saved_files": receipts,
            "custody": capture.summary(include_receipts=False),
        }
        if advance:
            result["watermark"] = sync_watermark.advance(
                workspace,
                "meetings",
                through.isoformat(),
                acquisition=evidence,
                home=home,
                now=dt.datetime.now().astimezone(),
            )
        return result
    finally:
        transport.close()


def acquisition_main(argv):
    parser = argparse.ArgumentParser(
        description="Bounded declared meeting acquisition; no implicit adapter fallback"
    )
    parser.add_argument(
        "--mode", choices=["health", "inventory", "fetch"], required=True
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--through", required=True)
    parser.add_argument("--backfill-from", required=True)
    parser.add_argument("--capture-dir", required=True)
    parser.add_argument("--evidence")
    parser.add_argument("--advance", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = acquire_window(
            load_config(Path(args.config)),
            mode=args.mode,
            through=args.through,
            backfill=args.backfill_from,
            capture_root=args.capture_dir,
            evidence_path=args.evidence,
            advance=args.advance,
            force=args.force,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(
            json.dumps(
                {"coverage": "unknown", "can_advance": False, "reason": str(exc)}
            )
        )
        return 2


# --- Main ---------------------------------------------------------------------


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--mode" in argv:
        return acquisition_main(argv)

    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "meeting", nargs="?", default="standup", help="Meeting name (default: standup)"
    )
    p.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    p.add_argument(
        "--account", default=None, help="Override google_account from config"
    )
    p.add_argument(
        "--transcript-tab-id", help="provider stable ID, never a title match"
    )
    p.add_argument(
        "--readiness-only",
        action="store_true",
        help="probe recorder identity; do not fetch or write",
    )
    p.add_argument(
        "--force", action="store_true", help="Overwrite if transcript already saved"
    )
    p.add_argument(
        "--port", type=int, default=int(os.environ.get("WORKSPACE_MCP_PORT", 8765))
    )
    args = p.parse_args(argv)

    target_date = args.date or dt.date.today().isoformat()

    try:
        config_path = find_config()
        cfg = load_config(config_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    account = args.account or cfg["google_account"]
    mcp_url = f"http://localhost:{args.port}/mcp"

    if not server_reachable(mcp_url):
        print(f"ERROR: workspace-mcp not reachable at {mcp_url}", file=sys.stderr)
        print("       Run ./start.sh or verify server status.", file=sys.stderr)
        return 1

    try:
        readiness = recorder_readiness(cfg, mcp_url, account)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.readiness_only:
        print(json.dumps(readiness))
        return 0

    # Compute out path (v0.2.0 schema — workspace is implicit in transcripts_repo name)
    out_dir = Path(cfg["transcripts_repo"]) / cfg["transcripts_path"] / "meetings"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{slugify(args.meeting)}-{target_date}.md"

    if out_file.exists() and not args.force:
        print(f"Already exists: {out_file}")
        print("Use --force to overwrite.")
        return 1

    # Resolve pattern and bracket date
    pattern = resolve_pattern(cfg, args.meeting)
    start = dt.date.fromisoformat(target_date)
    end = start + dt.timedelta(days=1)
    query = f'{pattern} and modifiedTime > "{start.isoformat()}T00:00:00" and modifiedTime < "{end.isoformat()}T00:00:00"'

    print(f"Searching Drive ({account}) for: {args.meeting} on {target_date}")
    print(f"  Pattern: {pattern}")

    search = mcp_call(
        mcp_url,
        "search_drive_files",
        {"user_google_email": account, "query": query, "page_size": 5},
    )

    ids = re.findall(r"ID:\s*([A-Za-z0-9_-]+)", search)
    if len(set(ids)) != 1:
        print(
            f"No matching doc found for '{args.meeting}' on {target_date} in {account}'s Drive.",
            file=sys.stderr,
        )
        print(f"Query tried: {query}", file=sys.stderr)
        return 1
    file_id = ids[0]
    print(f"Found doc: {file_id}")
    print(
        "Fetching content; structured tab completeness still requires verification..."
    )

    raw = mcp_call(
        mcp_url,
        "get_drive_file_content",
        {"user_google_email": account, "file_id": file_id},
    )
    selected = select_tabs(
        extract_content(raw),
        transcript_tab_id=args.transcript_tab_id or cfg.get("transcript_tab_id"),
    )
    if selected["status"] == "unknown" or selected["reason"] == "transcript-tab-absent":
        print(json.dumps(selected), file=sys.stderr)
        return 1
    if selected["status"] == "no-source":
        content = (
            "⚠️ summary-only — no verbatim transcript returned for the declared tab ID.\n\n"
            + "<!-- VERIFIER: no-source-transcript --> "
            + selected["reason"]
            + "\n\n"
            + "## Tool notes — lossy derivative\n\n"
            + selected["notes"]
        )
        print(
            "WARNING: "
            + selected["reason"]
            + "; preserved source notes are not primary transcript evidence.",
            file=sys.stderr,
        )
    else:
        content = (
            "## Tool notes — lossy derivative\n\n"
            + selected["notes"]
            + "\n\n## Verbatim transcript\n\n"
            + selected["transcript"]
        )
    if not content.strip():
        print("ERROR: fetched doc but content was empty.", file=sys.stderr)
        return 1

    weekday = start.strftime("%A")
    month = start.strftime("%B")
    human = f"{weekday}, {month} {start.day}, {start.year}"
    title = args.meeting.title()

    header = (
        f"# {title} — {human}\n\n"
        f"**Source:** Gemini meeting notes + full transcript\n"
        f"**Google Doc:** https://docs.google.com/document/d/{file_id}/edit\n"
        f"**Source ID:** google-drive:{file_id}\n"
        f"**Transcript tab ID:** {selected['transcript_tab_id']}\n"
        f"**Fetched via:** workspace-mcp ({account}) — {dt.date.today().isoformat()}\n\n"
        f"---\n\n"
    )
    try:
        receipt = save_verified(out_file, header + content, force=args.force)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"saved_files": [receipt]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
