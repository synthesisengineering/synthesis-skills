#!/usr/bin/env python3
"""Codex Stop hook: catch filenames mentioned in a response that are not clickable links.

Twin of the Claude hook. The detection logic is NOT duplicated — it is imported from
`../claude/bare_filename_detector.py` so the two clients can never drift apart on what
counts as a violation. Only the input contract differs: Codex hands the text directly as
`last_assistant_message`, where Claude Code hands a transcript path to parse.

The rule is stated ABSOLUTE in the project instructions: every file named in a
chat response is a markdown link carrying the full absolute path. The prose rule
failed anyway, which is why there is now a backstop rather than only a rule.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Single source of truth for detection — the Claude-side module. It goes to the FRONT of
# sys.path every time, not merely somewhere on it: when both hook directories share one
# interpreter (pytest prepends each collected test directory), a bare import of
# `bare_filename_detector` must reach the Claude core ahead of this twin, or the line
# below imports the twin itself and fails with a circular ImportError.
CLAUDE_HOOKS = Path(__file__).resolve().parent.parent / "claude"
while str(CLAUDE_HOOKS) in sys.path:
    sys.path.remove(str(CLAUDE_HOOKS))
sys.path.insert(0, str(CLAUDE_HOOKS))
HOOKS_ROOT = CLAUDE_HOOKS.parent
if str(HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(HOOKS_ROOT))

from bare_filename_detector import find_violations  # noqa: E402
from _settings import doctor_prologue, hook_enabled  # noqa: E402

HOOK_NAME = "bare_filename_detector"
LOG_FILE = Path.home() / ".codex" / "bare-filename-log.jsonl"


def doctor() -> int:
    lines, _healthy = doctor_prologue(HOOK_NAME)
    lines.append(f"log_file={LOG_FILE}")
    lines.append("detection_core=../claude/bare_filename_detector.py")
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
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    text = payload.get("last_assistant_message") or ""
    if not text:
        return 0

    cwd = payload.get("cwd", "")
    # Codex gives no prior user turn here; passing "" means an echoed filename is still
    # flagged. That is the safe direction — a false positive costs one glance.
    hits = find_violations(text, "", cwd)
    if not hits:
        return 0

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": payload.get("session_id", "unknown"),
        "turn_id": payload.get("turn_id", "unknown"),
        "cwd": cwd,
        "violations": hits,
    }
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass

    names = ", ".join(h["token"] for h in hits[:6])
    more = f" (+{len(hits) - 6} more)" if len(hits) > 6 else ""
    print(
        "\n  UNLINKED FILENAMES IN YOUR RESPONSE — ABSOLUTE rule in project instructions\n"
        f"  Named without a clickable link: {names}{more}\n"
        "  Every file in a chat response is [name](/absolute/path).\n"
        "  Correct it in your next message.\n",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
