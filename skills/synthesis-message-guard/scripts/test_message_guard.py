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


# --- doctor controls from the 2026-08 config incidents ----------------------


def test_dead_surrogate_pattern_detection() -> None:
    """A pattern whose source carries lone surrogates (the escaped-emoji
    authoring mistake) can never match decoded text; the doctor's control
    predicate must identify it while a real-character pattern passes."""
    import re

    dead_source = "\ud83e\uddde|RagBot"
    live_source = "\U0001F9DE|RagBot"
    def is_dead(rx):
        return any("\ud800" <= ch <= "\udfff" for ch in rx.pattern)
    assert is_dead(re.compile(dead_source))
    assert not is_dead(re.compile(live_source))
    # And the dead form genuinely fails to match the decoded emoji — the
    # incident's mechanism, kept here as the reason the control exists.
    assert re.compile(dead_source).search("\U0001F9DE hello") is None
    assert re.compile(live_source).search("\U0001F9DE hello") is not None


def test_config_clean_controls_scan() -> None:
    """doctor_clean_controls entries run through the live scanner: a
    canonical legitimate message must produce zero hits, and a config
    change that starts blocking real traffic must be detectable."""
    import re

    cblock = [("bad-brand", re.compile("RagBot"))]
    cwarn: list = []
    canonical = "Ragbot here with the summary — details at ragbot.ai"
    hits, _ = MODULE.scan_text(canonical, cblock, cwarn)
    assert hits == []
    over_broad = [("bad-brand", re.compile("ragbot", re.IGNORECASE))]
    hits2, _ = MODULE.scan_text(canonical, over_broad, cwarn)
    assert hits2, "an over-broad pattern must be visible to the control"
