"""A15, 2026-11-18: a tool glob in the config names the same tool in every harness.

Codex's hook names an MCP tool with each character of its server's name that is no letter, digit or `_` written as
`_` (`mcp__workspace_mcp__send_message`); Claude Code names it with the server's own name
(`mcp__workspace-mcp__send_message`). A Chat message signed with the plain fallback, which the principal's config
allows for that tool in `signature.plain_url_tools`, was refused in Codex as showing the persona's domain as text,
since the glob named the server as Claude Code does. Every glob over tool names is now read in both spellings.
"""

import json
from pathlib import Path

import pytest

from synthesis import guards, sends

EXAMPLE = json.loads((Path(__file__).resolve().parents[1] / "skills" / "synthesis-message-guard" / "config.example.json")
                     .read_text(encoding="utf-8"))
PLAIN = {"user_google_email": "me@example.test", "space_id": "spaces/AAA",
         "message_text": "The slides are in the shared deck.\n\n🤖 Helperbot (helperbot.example), approved before sending"}
LINKED = "must be the link"


def allowing(*globs) -> dict:
    return {**EXAMPLE, "signature": {**EXAMPLE["signature"], "plain_url_tools": list(globs)}}


@pytest.mark.parametrize("glob", ["*workspace-mcp__send_message", "*workspace_mcp__send_message"])
@pytest.mark.parametrize("tool", ["mcp__workspace-mcp__send_message", "mcp__workspace_mcp__send_message"])
def test_a_plain_signature_the_config_allows_passes_in_every_harness(tool, glob):
    assert not [p for p in guards.message_problems(tool, PLAIN, allowing(glob)) if LINKED in p]


def test_the_incidents_call_reaches_its_approval_in_codex():
    reason = guards.check("mcp__workspace_mcp__send_message", PLAIN, allowing("*workspace-mcp__send_message"))
    assert reason and LINKED not in reason and "approve followed by the code" in reason, reason


@pytest.mark.parametrize("tool", ["mcp__other-chat__send_message", "mcp__other_chat__send_message"])
def test_a_tool_the_config_does_not_name_still_needs_the_named_link(tool):
    assert [p for p in guards.message_problems(tool, PLAIN, allowing("*workspace-mcp__send_message")) if LINKED in p]


def test_a_hyphen_inside_a_globs_brackets_keeps_its_meaning():
    assert not [p for p in guards.message_problems("mcp__chat_7__send_message", PLAIN, allowing("mcp__chat-[0-9]__send_message"))
                if LINKED in p]
    assert [p for p in guards.message_problems("mcp__chat_x__send_message", PLAIN, allowing("mcp__chat-[0-9]__send_message"))
            if LINKED in p]


def test_every_other_glob_over_tool_names_reads_both_spellings():
    assert guards.is_send_tool("mcp__my_crm__log_note", {"send_tools": ["mcp__my-crm__log_note"]})
    assert guards.is_send_tool("mcp__my-crm__log_note", {"send_tools": ["mcp__my_crm__log_note"]})
    assert not sends.says("mcp__agent_relay__post_note", {"not_send_tools": ["mcp__agent-relay__*"]})
    assert sends.says("mcp__agent_relay__post_note", {})
    plain = {**EXAMPLE, "message_format": {**EXAMPLE["message_format"], "plain_email_tools": ["mcp__apple-mail__*"]}}
    mail = {"to": "pat@example.test", "subject": "Notes", "body": "The notes are attached."}
    assert not [p for p in guards.message_problems("mcp__apple_mail__send_email", mail, plain) if "never plain text" in p]
    assert guards._reads_calendar("mcp__team_cal__agenda", ["mcp__team-cal__agenda"])
