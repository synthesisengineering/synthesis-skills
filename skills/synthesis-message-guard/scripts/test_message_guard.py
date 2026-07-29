from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("message_guard.py")
SPEC = importlib.util.spec_from_file_location("message_guard", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

SAMPLE_TOOLS = [
    "mcp__abc__slack_send_message",
    "mcp__abc__slack_send_message_draft",
    "mcp__abc__slack_schedule_message",
    "mcp__workspace__draft_gmail_message",
    "mcp__workspace__send_gmail_message",
    "mcp__mail__create_draft",
    "mcp__mail__update_draft",
    "mcp__apple-mail__send_email",
    "mcp__mail__send_message",
]
MATCHER = (
    "mcp__.*__(slack_send_message|slack_send_message_draft|"
    "slack_schedule_message|draft_gmail_message|send_gmail_message|"
    "create_draft|update_draft|send_email|send_message)$"
)


def write_hooks(path: Path, matcher: str, command: str) -> None:
    path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": matcher,
                            "hooks": [{"type": "command", "command": command}],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )


def test_hook_config_accepts_claude_and_codex_shape(tmp_path: Path) -> None:
    for filename in ("settings.json", "hooks.json"):
        path = tmp_path / filename
        write_hooks(path, MATCHER, "python3 message_guard.py --gate")
        assert MODULE.hook_config_covers(path, SAMPLE_TOOLS)


def test_hook_config_rejects_partial_matcher(tmp_path: Path) -> None:
    path = tmp_path / "hooks.json"
    write_hooks(
        path,
        "mcp__.*__slack_send_message$",
        "python3 message_guard.py --gate",
    )
    assert not MODULE.hook_config_covers(path, SAMPLE_TOOLS)


def test_hook_config_rejects_missing_guard(tmp_path: Path) -> None:
    path = tmp_path / "hooks.json"
    write_hooks(path, MATCHER, "python3 another_guard.py --gate")
    assert not MODULE.hook_config_covers(path, SAMPLE_TOOLS)
