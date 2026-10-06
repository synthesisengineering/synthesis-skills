"""R3.1: the send guard binds the whole call and checks the text before anyone approves it.

CI has no ~/.synthesis, so these tests load the public example config shipped with the
message-guard skill (skills/synthesis-message-guard/config.example.json) and say so here.
"""

import json
import re
from pathlib import Path

import pytest

from synthesis import guards

CONFIG = json.loads((Path(__file__).resolve().parents[1] / "skills" / "synthesis-message-guard" / "config.example.json")
                    .read_text(encoding="utf-8"))
SLACK = "mcp__slack__slack_send_message"
DRAFT = "mcp__0a1b2c3d__create_draft"
SIGNED = ("Thank you for writing this up properly. The step list is the valuable part. Send times that suit you "
          "and I will make one of them work.\n\n"
          "🤖 _I'm the principal's <https://helperbot.example/|Helperbot>, sent under standing direction, every reply is read_")
KNOWN_BAD = "I'm sorry for the delay. I went quiet on you, and I'm the least able to judge this myself."
EMAIL = {"to": ["a@example.com"], "cc": ["b@example.com"], "bcc": ["c@example.com"], "subject": "Next steps",
         "htmlBody": "<p>The plan is attached.</p><p>Tuesday works.</p>", "body": "The plan is attached.\n\nTuesday works.",
         "replyToMessageId": "18c0ffee", "attachments": [{"filename": "plan.pdf", "content": "UEsDBA=="}]}


@pytest.fixture(autouse=True)
def _principal(principal):
    global _approve
    _approve = principal


def test_positive_controls_a_real_signed_message_passes_and_a_known_bad_one_blocks():
    assert "approval" in guards.check(SLACK, {"channel_id": "C0EXAMPLE", "message": SIGNED}, CONFIG)
    reason = guards.check(SLACK, {"channel_id": "C0EXAMPLE", "message": KNOWN_BAD}, CONFIG)
    assert "delay-apology" in reason and "approve" not in reason


@pytest.mark.parametrize("field,value", [("to", ["x@example.com"]), ("cc", []), ("bcc", ["d@example.com"]),
                                         ("subject", "Next steps!"), ("replyToMessageId", "18c0ffef"),
                                         ("body", "The plan is attached.\n\nWednesday works."),
                                         ("attachments", [{"filename": "plan-v2.pdf", "content": "UEsDBA=="}])])
def test_an_approval_covers_every_field_of_the_call(field, value):
    _approve(guards.check(DRAFT, EMAIL, CONFIG))
    assert "approve" in guards.check(DRAFT, {**EMAIL, field: value}, CONFIG)
    assert guards.check(DRAFT, EMAIL, CONFIG) is None


def test_two_sessions_composing_at_once_keep_separate_approvals():
    one = {"channel_id": "C1", "message": "First note."}
    two = {"channel_id": "C2", "message": "Second note."}
    first, second = guards.check(SLACK, one, CONFIG), guards.check(SLACK, two, CONFIG)
    _approve(first)
    _approve(second)
    assert guards.check(SLACK, two, CONFIG) is None and guards.check(SLACK, one, CONFIG) is None


@pytest.mark.parametrize("html", ["<p>I am so<b></b>rry for the delay.</p>", "<p>I am &#115;orry for the delay.</p>",
                                  "<p>Sorry for the\n   delay.</p>"])
def test_a_banned_phrase_hidden_by_markup_or_entities_still_blocks(html):
    assert "delay-apology" in guards.check(DRAFT, {**EMAIL, "htmlBody": html}, CONFIG)


@pytest.mark.parametrize("header,blocked", [("&lt;id@host.example&gt;", True), ("<id@host.example", True),
                                            ("<id@host.example>", False), ("<a@h.example> <b@h.example>", False)])
def test_threading_headers_carry_literal_message_ids(header, blocked):
    call = {"to": "a@example.com", "subject": "Re: plan", "body": "<p>Yes.</p>", "body_format": "html",
            "in_reply_to": header, "references": header, "user_google_email": "me@example.com"}
    reason = guards.check("mcp__workspace-mcp__send_gmail_message", call, CONFIG)
    assert ("Message-ID" in reason or "unbalanced" in reason) is blocked, reason


@pytest.mark.parametrize("change,expected", [
    ({"htmlBody": None}, "never plain text"),
    ({"htmlBody": "<p>One line<br>broken.</p>"}, "<br>"),
    ({"body": "The plan is\nattached.\n\nTuesday works."}, "inside a paragraph"),
    ({"htmlBody": "<p>See <a href='javascript:x'>this</a>.</p>"}, "https, http or mailto"),
    ({"htmlBody": "<p>Notes</p><table><tr><td>x</td></tr></table>"}, "unsupported HTML element"),
    ({"htmlBody": "<p>See [the plan](https://example.com/plan).</p>"}, "markdown"),
    ({"body": "**Tuesday** works."}, "markdown"),
])
def test_email_is_html_with_whole_paragraphs_and_no_markdown(change, expected):
    call = {k: v for k, v in {**EMAIL, **change}.items() if v is not None}
    reason = guards.check(DRAFT, call, CONFIG)
    assert expected in reason and "approve" not in reason, reason


def test_a_well_formed_email_reaches_approval():
    assert "approval" in guards.check(DRAFT, EMAIL, CONFIG)
    call = {"to": "a@example.com", "subject": "Plan", "body": "<p>Tuesday works.</p>", "body_format": "html",
            "user_google_email": "me@example.com"}
    assert "approval" in guards.check("mcp__workspace-mcp__draft_gmail_message", call, CONFIG)
    assert "never plain text" in guards.check("mcp__workspace-mcp__draft_gmail_message", {**call, "body_format": "plain"}, CONFIG)


def test_a_plain_only_transport_is_allowed_only_when_the_principal_lists_it():
    call = {"to": "a@example.com", "subject": "Plan", "body": "Tuesday works.\n\nThanks."}
    assert "never plain text" in guards.check("mcp__apple-mail__send_email", call, CONFIG)
    config = {**CONFIG, "message_format": {**CONFIG["message_format"], "plain_email_tools": ["mcp__apple-mail__*"]}}
    assert "approval" in guards.check("mcp__apple-mail__send_email", call, config)
    assert "inside a paragraph" in guards.check("mcp__apple-mail__send_email", {**call, "body": "Tuesday\nworks."}, config)


@pytest.mark.parametrize("text,blocked", [
    ("This sentence was hard-wrapped\nin the middle.", True),
    ("First paragraph.\n\nSecond paragraph.", False),
    ("Three things:\n- one\n- two\n1. three\n> a quote", False),
    ("Run this:\n```\nline one\nline two\n```", False),
    ("*Bold* and _italic_ in Slack mrkdwn, with a <https://example.com|link>.", False),
])
def test_chat_text_never_breaks_a_paragraph_but_lists_quotes_and_code_keep_their_lines(text, blocked):
    reason = guards.check(SLACK, {"channel_id": "C1", "message": text}, CONFIG)
    assert ("inside a paragraph" in reason) is blocked, reason
    allowed = {**CONFIG, "message_format": {"allow_line_breaks_in_paragraphs": True}}
    assert "approval" in guards.check(SLACK, {"channel_id": "C1", "message": text}, allowed)


@pytest.mark.parametrize("text,blocked", [
    ("Done.\n\n🤖 Helperbot, on behalf of the principal · helperbot.example", True),
    ("Done.\n\n🤖 _I'm the principal's <https://helperbot.example/|Helperbot>_", False),
    ("Done. Details at helperbot.example.", False),  # no persona marker: not a signature
])
def test_a_persona_signature_is_a_link_on_channels_that_render_links(text, blocked):
    reason = guards.check(SLACK, {"channel_id": "C1", "message": text}, CONFIG)
    assert ("persona name itself must be the link" in reason) is blocked, reason
    exempt = {**CONFIG, "signature": {**CONFIG["signature"], "plain_url_tools": ["mcp__slack__*"]}}
    assert "approval" in guards.check(SLACK, {"channel_id": "C1", "message": text}, exempt)


def test_session_to_session_messages_are_not_correspondence():
    assert guards.check("mcp__ccd_session_mgmt__send_message", {"session_id": "local_1", "message": "Line one\nline two"}, CONFIG) is None


def test_the_example_config_is_valid():
    for rule in CONFIG["forbidden_phrases"]:
        re.compile(rule["pattern"])
    assert "persona casing" in guards.check(SLACK, {"channel_id": "C1", "message": "Sent by HelperBot."}, CONFIG)


@pytest.mark.parametrize("tool_input,quiet", [
    ({"action": "update", "event_id": "e1", "start_time": "2026-10-07T07:00", "send_updates": "none"}, True),
    ({"summary": "Travel hold", "visibility": "private", "sendUpdates": "none"}, True),
    ({"summary": "Sync", "attendees": ["a@example.com"], "send_updates": "none"}, False),
    ({"action": "update", "event_id": "e1", "send_updates": "all"}, False),
    ({"action": "update", "event_id": "e1"}, False),
])
def test_a_calendar_write_that_emails_no_one_needs_no_approval(tool_input, quiet):
    """Rajiv's ruling, 2026-10-06: calendar writes wait for approval because invitations email people in his
    name; a write that names no attendees and turns notifications off emails no one."""
    config = {"send_tools": ["mcp__*__manage_event", "mcp__*__create_event", "mcp__*__respond_to_event"]}
    tool = "mcp__workspace__manage_event" if "action" in tool_input else "mcp__workspace__create_event"
    reason = guards.check(tool, tool_input, config)
    assert (reason is None) is quiet, reason
    assert guards.check("mcp__workspace__respond_to_event", {"event_id": "e1", "send_updates": "none"}, config)
