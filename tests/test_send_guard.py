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


def test_an_imessage_signature_may_show_its_domain_since_imessage_cannot_carry_a_named_link():
    """An operations session, 2026-10-14: a signed iMessage could pass in no form. With the domain as text the
    link rule refused it; without the domain a branding rule refused it. iMessage never renders a named link."""
    signed = "Running ten minutes late.\n\n🤖 Helperbot, for the principal (helperbot.example)"
    assert not [p for p in guards.message_problems("imessage_send", {"to": "+15555550100", "text": signed}, CONFIG)
                if "must be the link" in p]
    assert any("must be the link" in p for p in guards.message_problems(SLACK, {"channel_id": "C1", "message": signed}, CONFIG))


def test_an_rsvp_comment_may_show_the_domain_since_it_is_plain_text():
    """An operations session, 2026-10-22: a declined invitation could not carry its signed note. The RSVP comment
    reaches the organizer as plain text, so no named link can render there; the event's description still can."""
    signed = "Rajiv can't make this one; he'll follow up by email.\n\n🤖 Helperbot (helperbot.example)"
    for tool, field in (("mcp__workspace-mcp__manage_event", "rsvp_comment"), ("mcp__gcal__respond_to_event", "responseComment")):
        call = {"action": "rsvp", "response": "declined", "user_google_email": "me@personal.example", field: signed}
        assert not [p for p in guards.message_problems(tool, call, CONFIG) if "must be the link" in p], tool
    described = {"action": "update", "user_google_email": "me@personal.example", "description": signed}
    assert any("must be the link" in p for p in guards.message_problems("mcp__workspace-mcp__manage_event", described, CONFIG))


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
    # 2026-10-23: an accepted RSVP with notifications off went out with no code; every RSVP waits (5.0.3).
    ({"action": "rsvp", "event_id": "e1", "response": "accepted", "send_updates": "none"}, False),
    ({"action": "RSVP", "event_id": "e1", "response": "declined", "send_updates": "none"}, False),
])
def test_a_calendar_write_that_emails_no_one_needs_no_approval(tool_input, quiet):
    """Rajiv's ruling, 2026-10-06: calendar writes wait for approval because invitations email people in his
    name; a write that names no attendees and turns notifications off emails no one."""
    config = {"send_tools": ["mcp__*__manage_event", "mcp__*__create_event", "mcp__*__respond_to_event"]}
    tool = "mcp__workspace__manage_event" if "action" in tool_input else "mcp__workspace__create_event"
    reason = guards.check(tool, tool_input, config)
    assert (reason is None) is quiet, reason
    assert guards.check("mcp__workspace__respond_to_event", {"event_id": "e1", "send_updates": "none"}, config)


def test_a_branding_link_in_html_counts_as_branding_and_a_phrase_split_by_a_link_still_blocks():
    """An operations session, 2026-10-13: a rule requiring the persona's domain read only the tag-stripped text, where
    an HTML signature keeps the domain in its href, so the canonical email signature could never pass."""
    signed = ('<p>The plan is attached.</p><p>🤖 <em>I\'m the principal\'s <a href="https://helperbot.example/">'
              'Helperbot</a>, sent under standing direction</em></p>')
    call = {"to": "x@example.com", "subject": "Plan", "body_format": "html", "body": signed}
    tool = "mcp__workspace-mcp__send_gmail_message"
    assert "approval" in guards.check(tool, call, CONFIG)
    unbranded = {**call, "body": "<p>The plan is attached.</p><p>🤖 <em>Helperbot, sent under standing direction</em></p>"}
    assert "persona-marker-without-branding" in guards.check(tool, unbranded, CONFIG)
    split = {**call, "body": '<p>I am <a href="https://example.com/">sorry</a> for the delay.</p>'}
    assert "delay-apology" in guards.check(tool, split, CONFIG)


# Rajiv, 2026-10-13: an agent message addressed someone by their official first name. The example config lists
# that pair with example.test identifiers; the name is checked only in a call that carries one of them.
GOES_BY_BOB = "this message involves someone who goes by Bob; write Bob, not Robert"
BOB_EMAIL = {**EMAIL, "to": ["bob@example.test"], "htmlBody": "<p>Robert, the plan is attached.</p>",
             "body": "Robert, the plan is attached."}


@pytest.mark.parametrize("tool,call", [
    (DRAFT, BOB_EMAIL),
    (DRAFT, {**BOB_EMAIL, "to": ["a@example.com"], "cc": ["BOB@example.test"]}),
    (DRAFT, {**BOB_EMAIL, "htmlBody": "<p>Bob, the plan is attached.</p>", "body": "Bob, the plan is attached.",
             "subject": "Robert's plan"}),
    (SLACK, {"channel_id": "U0EXAMPLE", "message": "Robert, the plan is attached."}),
    (SLACK, {"channel_id": "C0EXAMPLE", "message": "Thanks <@U0EXAMPLE>. Robert's notes are the valuable part."}),
])
def test_an_official_first_name_is_refused_when_the_call_identifies_someone_who_goes_by_another(tool, call):
    reason = guards.check(tool, call, CONFIG)
    assert GOES_BY_BOB in reason and "approve" not in reason, reason


@pytest.mark.parametrize("tool,call", [
    (DRAFT, {**BOB_EMAIL, "to": ["kathryn@other.example"]}),  # another Robert: no identifier of Bob's in the call
    (SLACK, {"channel_id": "C0EXAMPLE", "message": "Robert, the plan is attached."}),
    (SLACK, {"channel_id": "C0EXAMPLE", "message": "Thanks <@U0OTHER>. Robert's notes are the valuable part."}),
])
def test_the_same_first_name_for_someone_else_is_never_blocked(tool, call):
    assert "approval" in guards.check(tool, call, CONFIG)


@pytest.mark.parametrize("tool,call", [
    (DRAFT, {**BOB_EMAIL, "htmlBody": "<p>Bob, the plan is attached.</p>", "body": "Bob, the plan is attached."}),
    # the address field keeps the directory's display name; only the words a person reads change
    (DRAFT, {**BOB_EMAIL, "to": ["Robert Example <bob@example.test>"], "htmlBody": "<p>Bob, the plan is attached.</p>",
             "body": "Bob, the plan is attached."}),
    (SLACK, {"channel_id": "C0EXAMPLE", "message": "Thanks <@U0EXAMPLE>. Bob's notes are the valuable part."}),
    (SLACK, {"channel_id": "U0EXAMPLE", "message": "Bob, the notes are at kathryn.notes.example."}),  # case-sensitive
])
def test_the_preferred_name_passes(tool, call):
    assert "approval" in guards.check(tool, call, CONFIG)


def test_no_preferred_names_key_means_no_name_check():
    config = {k: v for k, v in CONFIG.items() if k != "preferred_names"}
    assert "approval" in guards.check(DRAFT, BOB_EMAIL, config)
    assert "approval" in guards.check(SLACK, {"channel_id": "U0EXAMPLE", "message": "Robert, the plan is attached."}, config)
