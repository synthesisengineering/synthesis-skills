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

Requires `uv` for httpx + pyyaml. Run via: `uv run --with httpx --with pyyaml python fetch-meeting.py ...`
Or install deps with pip first.
"""

from __future__ import annotations

import argparse
import hashlib
import secrets
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
    print(f"Missing dependency: {exc.name}. Run via:", file=sys.stderr)
    print(
        "  uv run --with httpx --with pyyaml python fetch-meeting.py [args]",
        file=sys.stderr,
    )
    sys.exit(2)


sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp_client import call_tool_text, _parse_sse, bounded_post
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


def mcp_call(url: str, tool: str, args: dict) -> str:
    """Call an MCP tool over HTTP streamable transport, return concatenated text content."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    with httpx.Client(timeout=60) as c:
        r = bounded_post(c,
            url,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "fetch-meeting.py", "version": "0.1"},
                },
            },
        )
        r.raise_for_status()
        sid = r.headers.get("mcp-session-id")
        if not sid:
            raise RuntimeError(f"No session ID in response: {r.text[:200]}")
        bounded_post(c,
            url,
            headers={**headers, "Mcp-Session-Id": sid},
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        r = bounded_post(c,
            url,
            headers={**headers, "Mcp-Session-Id": sid},
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
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "synthesis-daily-rituals/scripts"))
    from acquisition_evidence import validate_recorder_control
    validate_recorder_control(positive_control, source=source, account=account,
                              after=through, now=dt.datetime.now().astimezone())
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


def _archive_directory(path, *, create=False):
    """Open each component without following links; caller owns the returned fd."""
    current = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:]:
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=current)
                except FileExistsError:
                    pass
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current
            )
            os.close(current)
            current = child
        return current
    except BaseException:
        os.close(current)
        raise


def save_verified(path, content, *, force=False):
    """Publish under a cooperative directory lock; preserve replaced/staging bytes.

    All writes are descriptor-relative to the no-follow opened archive directory.
    Managed project records still use the separate context transaction owner.
    """
    if fcntl is None:
        raise ValueError(
            "archive publication requires an available bounded file-lock owner"
        )
    sys.path.insert(
        0, str(Path(__file__).resolve().parents[2] / "synthesis-daily-rituals/scripts")
    )
    from ritual_workers import read_regular

    path = Path(path)
    if ".." in path.parts:
        raise ValueError("archive traversal refused")
    path = Path(os.path.abspath(path))
    parent = path.parent
    fd = _archive_directory(parent, create=True)
    original = os.fstat(fd)
    staging = None

    def same_parent():
        check = _archive_directory(parent)
        try:
            present = os.fstat(check)
            if (present.st_dev, present.st_ino) != (original.st_dev, original.st_ino):
                raise ValueError("archive directory changed")
        finally:
            os.close(check)

    try:
        deadline = time.monotonic() + 5
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ValueError("archive writer busy; no write attempted")
                time.sleep(0.02)
        same_parent()
        payload = content.encode("utf-8")
        if len(payload) > 8 * 1024 * 1024:
            raise ValueError("transcript exceeds archive bound")
        digest = hashlib.sha256(payload).hexdigest()
        old = None
        if os.path.lexists(path):
            old = read_regular(path, 8 * 1024 * 1024)
            if old == payload:
                rows = verify_transcripts.audit_files(
                    [path], expected_hashes={str(path): digest}
                )
                if any(row["status"] == "INCOMPLETE" for row in rows):
                    raise ValueError("existing exact transcript incomplete")
                return {"path": str(path), "sha256": digest, "saved": False}
            if not force:
                raise ValueError(
                    "archive differs; explicit force required to preserve and replace"
                )
            backup = path.with_name(
                path.name + ".old-" + hashlib.sha256(old).hexdigest() + ".md"
            )
            if os.path.lexists(backup):
                if read_regular(backup, 8 * 1024 * 1024) != old:
                    raise ValueError("archive backup conflict")
            else:
                same_parent()
                bfd = os.open(
                    backup.name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=fd,
                )
                with os.fdopen(bfd, "wb") as stream:
                    stream.write(old)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.fsync(fd)
        same_parent()
        name = "." + path.name + "." + secrets.token_hex(16) + ".md"
        staging = parent / name
        handle = os.open(
            name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd
        )
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(fd)
        rows = verify_transcripts.audit_files(
            [staging], expected_hashes={str(staging): digest}
        )
        if any(row["status"] == "INCOMPLETE" for row in rows):
            raise ValueError(
                "exact fetched transcript failed completeness; staging retained: "
                + str(staging)
            )
        same_parent()
        if old is not None and read_regular(path, 8 * 1024 * 1024) != old:
            raise ValueError("archive changed before replacement")
        if old is None and os.path.lexists(path):
            raise ValueError("archive appeared before publication")
        os.replace(name, path.name, src_dir_fd=fd, dst_dir_fd=fd)
        staging = None
        os.fsync(fd)
        rows = verify_transcripts.audit_files(
            [path], expected_hashes={str(path): digest}
        )
        if any(row["status"] == "INCOMPLETE" for row in rows):
            raise ValueError("saved transcript failed exact verification")
        return {
            "path": str(path),
            "sha256": digest,
            "saved": True,
            "verification": rows,
        }
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


# --- Main ---------------------------------------------------------------------


def main() -> int:
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
    args = p.parse_args()

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
    print("Fetching full content (includes all tabs: notes + transcript)...")

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
