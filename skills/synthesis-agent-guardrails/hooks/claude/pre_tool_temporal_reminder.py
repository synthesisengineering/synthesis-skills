#!/usr/bin/env python3
"""pre_tool_temporal_reminder.py — Claude Code PreToolUse hook.

Fires before Edit/Write/NotebookEdit tool calls. If the target file path
looks date-sensitive (session logs, daily plans, CONTEXT.md, MEMORY.md, any
file under a sessions/ directory), emits a stderr reminder of today's
verified date and the cache-vs-truth rule.

This is the reinforcement layer for the cache-vs-truth output gate in the
project instructions and the mid-session refresh protocol. It catches the
case where the agent is about to write a session-log entry or update
CONTEXT.md with a possibly-cached date.

Hook input (stdin, JSON, per Claude Code PreToolUse spec):
    {
        "session_id": "...",
        "tool_name": "Edit" | "Write" | "NotebookEdit",
        "tool_input": {
            "file_path": "...",
            ...
        },
        "cwd": "..."
    }

Output: emits a stderr reminder when target path matches the date-sensitive
patterns; silent otherwise. Exit 0 always (warn, never block). The user is
the final enforcer.

Matcher in settings.json: this hook registers under matcher "Edit|Write|
NotebookEdit". The path-pattern filtering happens inside this script so
the matcher itself stays simple.

Related: the mid-session refresh protocol; the checkpoint protocol; the
cache-vs-truth output gate in the project instructions.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
HOOKS_ROOT = HOOKS_DIR.parent
if str(HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(HOOKS_ROOT))
from _settings import doctor_prologue, hook_enabled  # noqa: E402

HOOK_NAME = "pre_tool_temporal_reminder"

# Regex patterns that flag a file path as date-sensitive. Any match → reminder.
DATE_SENSITIVE_PATTERNS = [
    re.compile(r"/sessions/\d{4}-\d{2}\.md$"),       # project session logs
    re.compile(r"/daily-plans/\d{4}-\d{2}-\d{2}"),    # daily plan files
    re.compile(r"/CONTEXT\.md$"),                     # project working memory
    re.compile(r"/MEMORY\.md$"),                      # workspace memory index
    re.compile(r"/projects/index\.yaml$"),            # project index with last_session
    re.compile(r"/lessons/\d{4}-\d{2}-\d{2}-"),       # dated lesson files
]


def now_str() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z (%A)")


def is_date_sensitive(path: str) -> bool:
    return any(p.search(path) for p in DATE_SENSITIVE_PATTERNS)


def doctor() -> int:
    lines, _healthy = doctor_prologue(HOOK_NAME)
    lines.append(f"date_sensitive_patterns={len(DATE_SENSITIVE_PATTERNS)}")
    print("\n".join(lines))
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if "--doctor" in argv:
        return doctor()
    if not hook_enabled(HOOK_NAME):
        return 0

    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return 0

    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not file_path:
        return 0

    if not is_date_sensitive(file_path):
        return 0

    # Build the reminder. Include today's verified date and a pointer to the
    # cache-vs-truth rule. This prints to stderr; Claude Code surfaces stderr
    # output from PreToolUse hooks back to the agent.
    today = now_str()
    msg = (
        f"\n[pre-tool-temporal-reminder] About to write to a date-sensitive file: {file_path}\n"
        f"  - Today's verified date: {today}\n"
        f"  - If you are writing a session-log entry or date header, use this date — NOT a date inferred from session continuity or memory.\n"
        f"  - If you are computing an interval (\"N days ago\", \"last session\"), run `git log` on the project path first.\n"
        f"  - The cache-vs-truth output gate applies to time: session-log dates and CONTEXT.md fields are caches subject to drift.\n"
        f"  - The checkpoint protocol is the codified verification procedure.\n"
    )
    sys.stderr.write(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
