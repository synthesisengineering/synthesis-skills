#!/usr/bin/env python3
"""Emit a compact, verified project anchor for agent lifecycle hooks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from project_context import extract, next_actions, record_freshness


DEFAULT_POINTER = Path.home() / ".synthesis" / "active-project.json"
DEFAULT_COORDINATION_BOARD = (
    Path.home() / ".synthesis" / "coordination" / "active-sessions.md"
)

def active_session_ids(board: Path) -> list[str]:
    if not board.is_file():
        return []
    text = board.read_text(encoding="utf-8")
    if not all(
        heading in text
        for heading in ("## Active sessions", "## Messages", "## Protocol")
    ):
        raise ValueError(f"coordination board schema is invalid: {board}")
    active = []
    in_table = False
    for line in text.splitlines():
        if line.strip() == "## Active sessions":
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table or not line.startswith("|"):
            continue
        columns = [re.sub(r"[*`]", "", value).strip() for value in line.split("|")[1:-1]]
        if len(columns) not in {7, 12} or columns[0] in {"id", "----"}:
            continue
        if set(columns[0]) == {"-"}:
            continue
        if columns[-1].lower() not in {
            "released",
            "complete",
            "completed",
            "closed",
        }:
            active.append(columns[0])
    return active


def build(pointer: Path, coordination_board: Path = DEFAULT_COORDINATION_BOARD) -> str:
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z (%A)")
    lines = [f"Verified local time: {now}."]
    sessions = active_session_ids(coordination_board)
    if sessions:
        lines.append(
            "Cross-agent coordination is active for session(s): "
            + ", ".join(sessions)
            + ". Read the coordination board and verify claims before writes."
        )
    if not pointer.is_file():
        lines.append("No active synthesis project pointer is set.")
        return "\n".join(lines)

    data = json.loads(pointer.read_text(encoding="utf-8"))
    project = Path(data["project"]).expanduser().resolve()
    context_path = project / "CONTEXT.md"
    if not context_path.is_file():
        raise FileNotFoundError(f"active project CONTEXT.md is missing: {context_path}")

    context = context_path.read_text(encoding="utf-8")
    phase = extract(context, "Phase")
    status = extract(context, "Status")
    plan = data.get("plan", "unknown")
    if plan != "unknown" and not Path(plan).is_file():
        raise FileNotFoundError(f"active plan is missing: {plan}")

    lines.extend(
        [
            f"Active synthesis project: {project}.",
            f"Current phase: {phase}.",
            f"Current status: {status}.",
            f"Controlling plan: {plan}.",
        ]
    )
    fresh, freshness_detail = record_freshness(project)
    if not fresh:
        lines.append(f"RECORD STALENESS WARNING: {freshness_detail}.")
    actions = next_actions(context)
    if actions:
        lines.append("Recorded next actions:")
        lines.extend(f"- {action}" for action in actions)
    lines.append("Re-read CONTEXT.md and the controlling plan before substantive work.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--active-project-file", type=Path, default=DEFAULT_POINTER)
    parser.add_argument(
        "--coordination-board",
        type=Path,
        default=DEFAULT_COORDINATION_BOARD,
    )
    parser.add_argument(
        "--format",
        choices=("text", "codex", "claude"),
        default="text",
        help="Wrap output for a client hook schema.",
    )
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    try:
        message = build(
            args.active_project_file.expanduser(),
            args.coordination_board.expanduser(),
        )
    except Exception as exc:
        print(f"synthesis project context failed closed: {exc}", file=sys.stderr)
        return 2

    if args.format == "codex":
        event = payload.get("hook_event_name", "SessionStart")
        print(
            json.dumps(
                {
                    "continue": True,
                    "hookSpecificOutput": {
                        "hookEventName": event,
                        "additionalContext": message,
                    },
                }
            )
        )
    elif args.format == "claude":
        print(
            json.dumps(
                {
                    "continue": True,
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": message,
                    },
                }
            )
        )
    else:
        print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
