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
    print("  uv run --with httpx --with pyyaml python fetch-meeting.py [args]", file=sys.stderr)
    sys.exit(2)


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
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    with httpx.Client(timeout=60) as c:
        r = c.post(url, headers=headers, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26", "capabilities": {},
                "clientInfo": {"name": "fetch-meeting.py", "version": "0.1"},
            },
        })
        sid = r.headers.get("mcp-session-id")
        if not sid:
            raise RuntimeError(f"No session ID in response: {r.text[:200]}")
        c.post(url, headers={**headers, "Mcp-Session-Id": sid},
               json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        r = c.post(url, headers={**headers, "Mcp-Session-Id": sid}, json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool, "arguments": args},
        })
    # Parse SSE
    for line in r.text.strip().split("\n"):
        if line.startswith("data: "):
            data = json.loads(line[6:])
            if "error" in data:
                raise RuntimeError(f"MCP error: {data['error']}")
            content = data.get("result", {}).get("content", [])
            return "\n".join(i.get("text", "") for i in content if i.get("type") == "text")
    raise RuntimeError(f"No data frame in MCP response: {r.text[:200]}")


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
    generic = cfg.get("generic_pattern") or 'name contains "{{name}}" and name contains "Notes by Gemini"'
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


# --- Main ---------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("meeting", nargs="?", default="standup", help="Meeting name (default: standup)")
    p.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    p.add_argument("--account", default=None, help="Override google_account from config")
    p.add_argument("--force", action="store_true", help="Overwrite if transcript already saved")
    p.add_argument("--port", type=int, default=int(os.environ.get("WORKSPACE_MCP_PORT", 8765)))
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

    # Compute out path (v0.2.0 schema — workspace is implicit in transcripts_repo name)
    out_dir = Path(cfg["transcripts_repo"]) / cfg["transcripts_path"] / "meetings"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{slugify(args.meeting)}-{target_date}.md"

    if out_file.exists() and not args.force:
        print(f"Already exists: {out_file}")
        print("Use --force to overwrite.")
        return 0

    # Resolve pattern and bracket date
    pattern = resolve_pattern(cfg, args.meeting)
    start = dt.date.fromisoformat(target_date)
    end = start + dt.timedelta(days=1)
    query = f'{pattern} and modifiedTime > "{start.isoformat()}T00:00:00" and modifiedTime < "{end.isoformat()}T00:00:00"'

    print(f"Searching Drive ({account}) for: {args.meeting} on {target_date}")
    print(f"  Pattern: {pattern}")

    search = mcp_call(mcp_url, "search_drive_files",
                      {"user_google_email": account, "query": query, "page_size": 5})

    m = re.search(r"ID:\s*([A-Za-z0-9_-]+)", search)
    if not m:
        print(f"No matching doc found for '{args.meeting}' on {target_date} in {account}'s Drive.", file=sys.stderr)
        print(f"Query tried: {query}", file=sys.stderr)
        return 1
    file_id = m.group(1)
    print(f"Found doc: {file_id}")
    print("Fetching full content (includes all tabs: notes + transcript)...")

    raw = mcp_call(mcp_url, "get_drive_file_content",
                   {"user_google_email": account, "file_id": file_id})
    content = extract_content(raw)
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
        f"**Fetched via:** workspace-mcp ({account}) — {dt.date.today().isoformat()}\n\n"
        f"---\n\n"
    )
    out_file.write_text(header + content)
    line_count = len(out_file.read_text().splitlines())
    print(f"Saved: {out_file}")
    print(f"Lines: {line_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
