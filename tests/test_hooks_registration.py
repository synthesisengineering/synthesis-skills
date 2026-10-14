"""R8: hooks fire only where they protect something, and every send tool is matched.

2026-10-14: the matcher listed send-shaped connector names, so `createJiraIssue` and every other tool the guard
recognizes by what it does never reached it, and Edit and Write (which could write a send window by hand) were
never checked. Every connector tool and every file-edit tool now reaches the guard; built-in reads do not."""

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
                                                                 "mcp__d01c6c5a__reply", "mcp__apple-mail__send_email",
                                                                 "mcp__apple-calendar__create_event",
                                                                 "mcp__workspace-mcp__manage_event",
                                                                 "mcp__3cd455d4__respond_to_event",
                                                                 "mcp__workspace-mcp__manage_out_of_office",
                                                                 "mcp__7512aea3__share_file",
                                                                 "mcp__workspace-mcp__set_drive_file_permissions",
                                                                 "mcp__85ff0050-6527__createJiraIssue",
                                                                 "mcp__atlassian__addCommentToJiraIssue",
                                                                 "mcp__github__create_pull_request",
                                                                 "mcp__c3621cad__notion-create-comment",
                                                                 "mcp__workspace-mcp__manage_document_comment"]
                         + sorted(guards.FILE_TOOLS))
def test_guarded_tools_reach_the_hook(tool):
    assert re.fullmatch(HOOKS["PreToolUse"][0]["matcher"], tool)


@pytest.mark.parametrize("tool", ["Read", "Grep", "Glob", "LS", "WebFetch", "WebSearch", "TodoWrite"])
def test_built_in_reads_never_start_the_hook(tool):
    assert not re.fullmatch(HOOKS["PreToolUse"][0]["matcher"], tool)
