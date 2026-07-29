#!/usr/bin/env python3
"""Emit a compact, verified project anchor for agent lifecycle hooks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_POINTER = Path.home() / ".synthesis" / "active-project.json"


def extract(context: str, key: str) -> str:
    match = re.search(rf"^\*\*{re.escape(key)}:\*\*\s*(.+)$", context, re.MULTILINE)
    return match.group(1).strip() if match else "unknown"


def next_actions(context: str) -> list[str]:
    match = re.search(
        r"^## What's Next[^\n]*\n(.*?)(?=^## |\Z)",
        context,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return []
    return [line.strip() for line in match.group(1).splitlines() if line.strip()][:5]


def build(pointer: Path) -> str:
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z (%A)")
    lines = [f"Verified local time: {now}."]
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
        message = build(args.active_project_file.expanduser())
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
