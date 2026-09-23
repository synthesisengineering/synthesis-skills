#!/usr/bin/env python3
"""long_session_detector.py — Claude Code Stop hook.

Detects when a Claude Code session has been running long enough that the
agent's in-context sense of "today" is likely drifting from reality. Emits
a stderr reminder to re-anchor date and project state via the checkpoint
protocol.

Threshold: 4 hours of wall-clock time since session start. Sessions that
span a midnight boundary will cross this threshold by definition. The
4-hour figure is conservative — token-cheap and catches the
day-spans-overnight case.

Tracks per-session "first seen" timestamp in ~/.claude/session-start-times.json
keyed by session_id. The Stop hook fires after every assistant message, so
state needs to persist across invocations. If the session_id is unknown, this
hook treats the current invocation as session start.

Hook input (stdin, JSON, per Claude Code Stop spec):
    {
        "session_id": "...",
        "transcript_path": "...",
        "cwd": "...",
        "stop_hook_active": true | false
    }

Output: emits a stderr reminder when threshold is crossed; silent otherwise.
Stop hooks fire after the assistant message has been sent, so this is a
safety-net reminder, not a blocker. Exit 0 always.

Related: the checkpoint protocol (the recommended re-anchor procedure).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
HOOKS_ROOT = HOOKS_DIR.parent
if str(HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(HOOKS_ROOT))
from _settings import doctor_prologue, hook_enabled  # noqa: E402

HOOK_NAME = "long_session_detector"
STATE_FILE = Path.home() / ".claude" / "session-start-times.json"
THRESHOLD_SECONDS = 4 * 60 * 60  # 4 hours


def load_state() -> dict[str, float]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text() or "{}")
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict[str, float]) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2))
    except OSError:
        pass  # non-fatal


def gc_state(state: dict[str, float], max_age_seconds: int = 7 * 24 * 3600) -> dict[str, float]:
    """Drop entries older than max_age_seconds to keep the file bounded."""
    now = datetime.now(timezone.utc).timestamp()
    return {sid: ts for sid, ts in state.items() if now - ts < max_age_seconds}


def doctor() -> int:
    lines, _healthy = doctor_prologue(HOOK_NAME)
    lines.append(f"state_file={STATE_FILE}")
    lines.append(f"threshold_seconds={THRESHOLD_SECONDS}")
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
        data = {}

    session_id = data.get("session_id")
    if not session_id:
        return 0  # nothing to track

    state = load_state()
    state = gc_state(state)
    now_ts = datetime.now(timezone.utc).timestamp()

    first_seen = state.get(session_id)
    if first_seen is None:
        state[session_id] = now_ts
        save_state(state)
        return 0  # first stop event for this session; nothing more to do

    elapsed = now_ts - first_seen
    save_state(state)  # refresh GC on every invocation

    if elapsed < THRESHOLD_SECONDS:
        return 0  # below threshold; silent

    # Above threshold. Emit reminder to stderr.
    hours = elapsed / 3600
    msg = (
        f"\n[long-session-detector] This session has been running for ~{hours:.1f} hours "
        f"of wall-clock time. The agent's in-context sense of \"today\" and \"last session\" "
        f"may have drifted from reality.\n"
        f"  - Run `date` to verify current time.\n"
        f"  - Run `git log` on the active project(s) to verify recent history.\n"
        f"  - Invoke the checkpoint protocol for the full re-anchor procedure.\n"
        f"  - The cache-vs-truth output gate applies: session-log dates and CONTEXT.md fields are caches.\n"
    )
    sys.stderr.write(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
