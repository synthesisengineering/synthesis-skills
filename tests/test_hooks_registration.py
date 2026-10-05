"""R8: hooks fire only where they protect something, and every send tool is matched."""

import json
import re
from pathlib import Path

import pytest

from synthesis import guards

HOOKS = json.loads((Path(__file__).resolve().parents[1] / "hooks" / "hooks.json").read_text())["hooks"]


def test_only_the_four_needed_events_are_registered():
    assert set(HOOKS) == {"SessionStart", "UserPromptSubmit", "PreToolUse", "Stop"}


@pytest.mark.parametrize("tool", sorted(guards.SHELL_TOOLS) + ["mcp__slack__slack_send_message",
                                                                 "mcp__workspace-mcp__draft_gmail_message",
                                                                 "mcp__d01c6c5a__reply", "mcp__apple-mail__send_email"])
def test_guarded_tools_reach_the_hook(tool):
    assert re.fullmatch(HOOKS["PreToolUse"][0]["matcher"], tool)


@pytest.mark.parametrize("tool", ["Read", "Edit", "Write", "Grep", "mcp__slack__slack_read_channel"])
def test_reads_and_edits_never_start_the_hook(tool):
    assert not re.fullmatch(HOOKS["PreToolUse"][0]["matcher"], tool)
