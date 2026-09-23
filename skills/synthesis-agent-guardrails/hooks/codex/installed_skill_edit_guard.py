#!/usr/bin/env python3
"""Codex PreToolUse guard for installed skill directories.

Installed skill copies are deployment artifacts. Edit source repos first, then
refresh installed copies.
"""

import json
import os
import re
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
HOOKS_ROOT = HOOKS_DIR.parent
if str(HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(HOOKS_ROOT))
from _settings import doctor_prologue, hook_enabled  # noqa: E402

HOOK_NAME = "installed_skill_edit_guard"
HOME = Path.home().resolve()
PROTECTED_ROOTS = [
    HOME / ".claude" / "skills",
    HOME / ".codex" / "skills",
    HOME / ".agents" / "skills",
    HOME / ".cursor" / "skills",
]


def is_protected_path(value: str) -> bool:
    if not value:
        return False
    expanded = os.path.expanduser(value.strip().strip('"').strip("'"))
    try:
        path = Path(expanded).resolve(strict=False)
    except Exception:
        return False
    return any(path == root or root in path.parents for root in PROTECTED_ROOTS)


def extract_paths_from_patch(text: str) -> list[str]:
    paths = []
    for line in text.splitlines():
        match = re.match(r"\*\*\* (?:Add|Update|Delete) File: (.+)$", line)
        if match:
            paths.append(match.group(1).strip())
    return paths


def deny(reason: str) -> int:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


def doctor() -> int:
    lines, _healthy = doctor_prologue(HOOK_NAME)
    lines.append(f"protected_roots={len(PROTECTED_ROOTS)}")
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

    tool_input = payload.get("tool_input") or {}
    candidates = []
    for key in ("file_path", "path", "notebook_path"):
        value = tool_input.get(key)
        if isinstance(value, str):
            candidates.append(value)

    for key in ("command", "cmd", "patch"):
        value = tool_input.get(key)
        if isinstance(value, str):
            candidates.extend(extract_paths_from_patch(value))

    if any(is_protected_path(path) for path in candidates):
        return deny(
            "Installed skill directories are deployment artifacts. Edit the "
            "source skill repo first, commit and push all configured remotes, "
            "then refresh installed copies for Claude Code and Codex."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
