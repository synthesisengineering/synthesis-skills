"""R3.1: the send guard binds the whole call and checks the text before anyone approves it.

CI has no ~/.synthesis, so these tests load the public example config shipped with the
message-guard skill (skills/synthesis-message-guard/config.example.json) and say so here.
"""

import base64
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import quote

import pytest

from synthesis import approvals, guards, paths, sends

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


# --- a file attached by its path ---------------------------------------------------------------------------
# The workspace connector's mail tools read an attachment given as a path from the connector's own disk, and
# only from its attachment folder and the folders it was started with (ALLOWED_FILE_DIRS, where its start script
# names the synthesis outbox). A file anywhere else was refused after the principal had approved the send; with
# a second attachment the connector could read, the message went out without the first. The guard refuses such
# a call before any code is issued and says where to put the file.
#
# Only what the connector reads counts as attached. It takes each attachment from the entry's `url`, else the file
# at its `path`, else base64 `content` with a `filename` (gmail_tools._prepare_gmail_message, 2.1.0). An entry it
# cannot read that way it leaves out of the mail, and letters outside standard base64 it skips, attaching other
# bytes. So an entry that names its file under another key, gives no source or two, gives content that is not
# standard base64, or names a file it reads from no folder is refused the same way.

SEND = "mcp__workspace-mcp__send_gmail_message"
MAIL = {"to": "a@example.com", "subject": "Plan", "body": "<p>The plan is attached.</p>", "body_format": "html",
        "user_google_email": "me@example.com"}
AS_CONTENT = [{"filename": "plan.pdf", "content": "UEsDBA=="},
              {"url": "https://files.example.com/plan.pdf", "filename": "plan.pdf"}]


def _put(folder: Path, name: str = "plan.pdf") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(b"%PDF-1.4\n")
    return folder / name


@pytest.fixture
def scratch(tmp_path, monkeypatch):
    """A file in a session's scratch folder, a temporary home with an outbox, and none of the connector's
    settings inherited from the machine the tests run on."""
    for key in ("ALLOWED_FILE_DIRS", "WORKSPACE_ATTACHMENT_DIR"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "user"))
    paths.outbox().mkdir(parents=True)
    return _put(tmp_path / "scratch").parent


def _attached(file, tool: str = SEND, config: dict = CONFIG):
    return guards.check(tool, {**MAIL, "attachments": [{"path": str(file)}]}, config)


def _refused(given, *said: str) -> str:
    """The refusal of a mail call that carries these attachments: it says each of these, and no code is filed."""
    reason = guards.check(SEND, {**MAIL, "attachments": given}, CONFIG)
    assert all(words in reason for words in said), (reason, said)
    assert "approve" not in reason and approvals.pending() == [], reason
    return reason


@pytest.mark.parametrize("tool", [SEND, "mcp__workspace_mcp__draft_gmail_message", "mcp__mail_server__send_gmail_message"])
def test_a_file_outside_the_folders_the_connector_reads_is_refused_with_no_code_and_passes_once_staged(tool, scratch):
    outside = scratch / "plan.pdf"
    reason = _attached(outside, tool)
    assert f"the attachment {outside} is outside the folders the mail connector reads" in reason
    assert f"copy the file into {paths.outbox()}" in reason and "file this send again" in reason
    assert "approve" not in reason and approvals.pending() == []
    staged = shutil.copy(outside, paths.outbox() / "plan.pdf")
    assert "approval" in _attached(staged, tool) and len(approvals.pending()) == 1


@pytest.mark.parametrize("key", ["file_path", "filePath", "file", "file_id", "driveFileId"])
def test_a_file_named_under_any_key_but_path_is_refused_with_no_code_and_told_the_key_the_connector_reads(key, scratch):
    """The connector reads an attachment's file under `path` and under no other key. An entry that named it as
    `file_path` passed the guard and the principal approved it; the mail then went without the file."""
    staged = str(shutil.copy(scratch / "plan.pdf", paths.outbox() / "plan.pdf"))
    for entry in ({key: staged}, {key: staged, "filename": "plan.pdf", "mime_type": "application/pdf"}):
        for given, place in (([entry], 1), (AS_CONTENT + [entry], 3), (json.dumps([entry]), 1)):
            _refused(given, f"attachment {place} ", "has none of `path`, `content` and `url`", f"`{key}`",
                     "the file at its `path`", f"staged in {paths.outbox()}", "file this send again")
    assert "approval" in _attached(staged)  # the same file, under the key the connector reads


NOT_AS_GIVEN = [  # (an entry the connector would not attach as given, what the guard says of it)
    ({"filename": "plan.pdf", "content": "UEsDBA"}, "`content` that is not standard base64"),  # padding its decoder refuses
    ({"filename": "plan.pdf", "content": "UEsD-A_="}, "`content` that is not standard base64"),  # URL-safe letters: it skips them
    # It skips the prefix's punctuation too, reads the rest as data and attaches those other bytes with no word.
    ({"filename": "plan.pdf", "content": "data:application/pdf;base64,UEsDBA=="}, "`content` that is not standard base64"),
    ({"filename": "plan.pdf", "content": ["UEsDBA=="]}, "`content` that is not standard base64"),
    ({"content": "UEsDBA=="}, "`content` with no `filename`"),
    ({"filename": "plan.pdf", "mime_type": "application/pdf"}, "has none of `path`, `content` and `url`"),
    ({"filename": "plan.pdf", "content": "", "path": ""}, "has none of `path`, `content` and `url`"),
    ({"url": "", "filename": "plan.pdf"}, "an empty `url`"),
]


@pytest.mark.parametrize("entry,said", NOT_AS_GIVEN, ids=[f"{n}: {said}" for n, (_, said) in enumerate(NOT_AS_GIVEN)])
def test_an_entry_the_connector_would_not_attach_as_given_is_refused_with_no_code(entry, said, scratch):
    """The connector sends when at least one attachment attached and leaves the others out: a mail approved with
    two files went with one. Alone, such an entry cost an approval before the connector refused the call. Each
    entry here was run through the connector's own code (2.1.0): all but the `data:` one are left out."""
    staged = {"path": str(shutil.copy(scratch / "plan.pdf", paths.outbox() / "plan.pdf"))}
    for given, place in (([entry], 1), ([staged, entry], 2), (json.dumps([staged, entry]), 2)):
        _refused(given, f"attachment {place} ", said, "would not go as given", "file this send again")


def test_content_the_connector_decodes_goes_to_the_code(scratch):
    """Standard base64 with a name, also in lines as a MIME encoder writes it: its decoder skips the line breaks."""
    in_lines = base64.encodebytes(bytes(range(256)) * 2).decode("ascii")
    assert "+" in in_lines and "/" in in_lines and in_lines.count("\n") > 5
    for content in ("UEsDBA==", in_lines, " UEsDBA== \n"):
        call = {**MAIL, "attachments": [{"filename": "plan.bin", "content": content}]}
        assert "approval" in guards.check(SEND, call, CONFIG), content


@pytest.mark.parametrize("entry,read", [
    ({"url": "https://files.example.com/plan.pdf", "path": "<staged>"}, "url"),
    ({"path": "<staged>", "content": "UEsDBA==", "filename": "plan.pdf"}, "path"),
    ({"url": "https://files.example.com/plan.pdf", "content": "UEsDBA==", "filename": "plan.pdf"}, "url"),
    ({"url": None, "path": "<staged>"}, "url"),  # a key left empty still leads: it fetches nothing and reads no path
])
def test_an_entry_with_two_sources_is_refused_since_the_connector_reads_one_and_never_the_other(entry, read, scratch):
    """It takes the `url` before the `path` and the `path` before the `content`, and says nothing of the one it
    skipped: the principal would see a file named in the call that is not the one attached."""
    staged = str(shutil.copy(scratch / "plan.pdf", paths.outbox() / "plan.pdf"))
    entry = {key: staged if value == "<staged>" else value for key, value in entry.items()}
    _refused([entry], "attachment 1 ", f"reads only the `{read}`", "give one of them", "file this send again")
    assert "approval" in guards.check(SEND, {**MAIL, "attachments": [{"path": staged}, AS_CONTENT[0]]}, CONFIG)


@pytest.mark.parametrize("name", [".env", ".env.production", "credentials.json", "Client_Secret.json", ".netrc",
                                  ".ssh/id_ed25519.pub", "team/.AWS/config", ".env.d/notes.txt"])
def test_a_staged_file_whose_name_or_folder_marks_secrets_is_refused_since_the_connector_reads_no_such_file(name, scratch):
    """The connector reads no .env, key or credentials file from any folder, the outbox included
    (core.utils.validate_file_path). Staging one again changes nothing, so the refusal does not say to."""
    staged = _put((paths.outbox() / name).parent, Path(name).name)
    reason = _attached(staged)
    assert f"the attachment {staged} is one the mail connector never reads" in reason
    assert "copy the file into" not in reason and "approve" not in reason and approvals.pending() == []


def test_a_name_that_only_resembles_one_is_read_and_a_folder_of_keys_under_an_allowed_home_is_not(scratch, monkeypatch):
    for name in ("env.txt", "my.env", ".environment", "credentials.txt", "notes/client_secret.json.txt"):
        assert "approval" in _attached(_put((paths.outbox() / name).parent, Path(name).name)), name
    monkeypatch.setenv("ALLOWED_FILE_DIRS", os.pathsep.join([str(Path.home()), os.sep]))
    assert "approval" in _attached(_put(Path.home() / "reports"))
    for file in (_put(Path.home() / ".kube", "config"), _put(Path.home() / ".config" / "gcloud", "notes.txt"), "/etc/passwd"):
        assert "never reads" in _attached(file), file


@pytest.mark.parametrize("given,said", [
    ({}, "`attachments` is neither a list of entries nor the JSON text of one"),
    ({"path": "<staged>"}, "`attachments` is neither a list of entries nor the JSON text of one"),  # one entry, not in a list
    (json.dumps({"path": "<staged>"}), "`attachments` is neither a list of entries nor the JSON text of one"),
    ("not a list", "`attachments` is neither a list of entries nor the JSON text of one"),
    ("", "`attachments` is neither a list of entries nor the JSON text of one"),
    ("null", "`attachments` is neither a list of entries nor the JSON text of one"),
    (["<staged>"], "attachment 1 is not an object"),  # a list of paths
    ([{"path": "<staged>"}, 7], "attachment 2 is not an object"),
])
def test_attachments_in_a_shape_the_connector_refuses_are_refused_with_no_code(given, said, scratch):
    """Its parameter takes a list of objects, or the JSON text of one, and nothing else: each shape here was put to
    the connector's own parameter type (2.1.0), which refuses it. The call cost an approval first."""
    staged = str(_staged(scratch))
    given = json.loads(json.dumps(given).replace("<staged>", staged))
    _refused(given, said, "file this send again")


def test_content_or_a_url_is_no_file_read_and_only_the_file_beside_it_is_judged(scratch):
    for given in ("absent", None, [], "[]", AS_CONTENT, json.dumps(AS_CONTENT)):
        call = dict(MAIL) if given == "absent" else {**MAIL, "attachments": given}
        assert "approval" in guards.check(SEND, call, CONFIG), given
    outside = scratch / "plan.pdf"
    mixed = AS_CONTENT + [{"path": str(outside), "filename": "plan.pdf"}]
    for given in (mixed, json.dumps(mixed)):  # some clients send a list as its JSON text, and the connector reads it
        reason = guards.check(SEND, {**MAIL, "attachments": given}, CONFIG)
        assert reason.count("copy the file into") == 1 and str(outside) in reason and "approve" not in reason, given


def test_the_rule_is_the_workspace_connectors_and_another_mail_tool_is_as_it_was(scratch):
    """Another connector reads no path from this disk under these folders: its call is not this rule's to judge."""
    outside = scratch / "plan.pdf"
    for entry in ({"filename": "plan.pdf", "content": f"sha256:{'0' * 64}:{outside}"}, {"path": str(outside)}):
        assert "approval" in guards.check(DRAFT, {**EMAIL, "attachments": [entry]}, CONFIG), entry
    assert "approve" not in _attached(outside)


def test_the_connectors_own_folder_and_each_folder_it_is_started_with_count_and_no_other(scratch, monkeypatch, tmp_path):
    default = _put(Path.home() / ".workspace-mcp" / "attachments")
    own, extra, other, beside = (_put(tmp_path / name) for name in ("own", "extra", "other", "extra-more"))
    assert "approval" in _attached(default) and "approval" in _attached(_put(paths.outbox() / "deck"))
    assert all("approve" not in _attached(file) for file in (own, extra, other, beside))
    monkeypatch.setenv("WORKSPACE_ATTACHMENT_DIR", str(own.parent))  # the connector's folder is this one, not the default
    assert "approval" in _attached(own) and "approve" not in _attached(default)
    monkeypatch.setenv("ALLOWED_FILE_DIRS", os.pathsep.join(["/srv/reports", f" {extra.parent} ", ""]))
    assert "approval" in _attached(extra) and "approval" in _attached(own)
    assert all("approve" not in _attached(file) for file in (other, beside))  # a name that only starts the same
    monkeypatch.setenv("ALLOWED_FILE_DIRS", os.sep)
    assert "approval" in _attached(other)


def test_a_path_is_read_as_the_connector_reads_it(scratch, monkeypatch, tmp_path):
    """Links are followed before the comparison. The path must be whole: the connector resolves a relative one in
    its own folder and expands no `~`. And it must name a file that is there."""
    outbox, outside = paths.outbox(), scratch / "plan.pdf"
    staged = _put(outbox, "staged.pdf")
    (outbox / "leads-out.pdf").symlink_to(outside)  # in the outbox by name, elsewhere in fact
    (scratch / "leads-in.pdf").symlink_to(staged)  # elsewhere by name, in the outbox in fact
    (tmp_path / "also-the-outbox").symlink_to(outbox, target_is_directory=True)
    assert "outside the folders" in _attached(outbox / "leads-out.pdf")
    assert "approval" in _attached(scratch / "leads-in.pdf")
    assert "approval" in _attached(tmp_path / "also-the-outbox" / "staged.pdf")
    assert f"the attachment {outbox / 'gone.pdf'} does not exist" in _attached(outbox / "gone.pdf")
    (outbox / "deck").mkdir()
    assert f"the attachment {outbox / 'deck'} is not a file" in _attached(outbox / "deck")
    _put(Path.home() / ".workspace-mcp" / "attachments")
    monkeypatch.chdir(outbox)
    for partial in ("staged.pdf", "./staged.pdf", "~/.workspace-mcp/attachments/plan.pdf"):
        assert f"the attachment {partial} is not a full path" in _attached(partial)
    assert len(approvals.pending()) == 2  # the two files that are in the outbox in fact


def test_a_staged_file_that_has_gone_is_refused_again_and_its_code_is_kept_for_when_it_is_back(scratch):
    staged = Path(shutil.copy(scratch / "plan.pdf", paths.outbox() / "plan.pdf"))
    _approve(_attached(staged))
    staged.unlink()
    assert "does not exist" in _attached(staged)
    shutil.copy(scratch / "plan.pdf", staged)
    assert _attached(staged) is None  # not spent on the call the connector would have refused
    assert "approval" in _attached(staged)  # and spent once


def test_a_send_window_lets_no_unreadable_file_through_and_spends_no_send_on_it(scratch):
    config = {**CONFIG, "send_window_signatures": ["The plan is attached"]}
    sends.open_window(1, ["email"], count=1)
    assert "outside the folders" in _attached(scratch / "plan.pdf", config=config)
    assert "1 of 1 sends left" in sends.describe(sends.window())
    staged = shutil.copy(scratch / "plan.pdf", paths.outbox() / "plan.pdf")
    assert _attached(staged, config=config) is None and sends.window() == {}


def test_the_composing_reference_lists_this_check_with_the_words_the_guard_blocks_with(scratch, monkeypatch):
    composing = (Path(__file__).resolve().parents[1] / "skills" / "synthesis-message-guard" / "references" / "composing.md")
    listed = " ".join(composing.read_text(encoding="utf-8").split())
    monkeypatch.chdir(scratch)
    said = {"is outside the folders the mail connector reads": scratch / "plan.pdf", "is not a full path": "plan.pdf",
            "does not exist": paths.outbox() / "gone.pdf", "is not a file": paths.outbox()}
    for words, file in said.items():
        assert words in _attached(file) and words in listed, words
    assert all(f"`{name}`" in listed for name in ("path", *sorted(guards.FILE_MAIL_TOOLS), "ALLOWED_FILE_DIRS"))


def test_the_composing_reference_lists_what_counts_as_attached_the_drive_tools_and_the_bytes_an_approval_covers(scratch):
    """Each check the guard gained is in the reference's table with the words the guard blocks with, and the
    sentence an approval request ends with for a call that names files is in both references word for word."""
    skills = Path(__file__).resolve().parents[1] / "skills"
    listed = " ".join((skills / "synthesis-message-guard" / "references" / "composing.md").read_text(encoding="utf-8").split())
    sending = " ".join((skills / "synthesis-agent-correspondence" / "references" / "gates-and-sending.md")
                       .read_text(encoding="utf-8").split())
    assert "`path`, `file_path` or `filePath`" not in listed  # the earlier row, which had a file go under three keys
    staged = _staged(scratch)
    entries = {"has none of `path`, `content` and `url`": {"file_path": str(staged)},
               "the mail connector reads only the": {"path": str(staged), "content": "UEsDBA==", "filename": "plan.pdf"},
               "gives `content` with no `filename`": {"content": "UEsDBA=="},
               "gives `content` that is not standard base64": {"filename": "plan.pdf", "content": "UEsDBA"},
               "has an empty `url`": {"url": ""},
               "is one the mail connector never reads": {"path": str(_put(paths.outbox(), ".env"))}}
    for words, entry in entries.items():
        assert words in guards.check(SEND, {**MAIL, "attachments": [entry]}, CONFIG) and words in listed, words
    words = "is neither a list of entries nor the JSON text of one"
    assert words in guards.check(SEND, {**MAIL, "attachments": {"path": str(staged)}}, CONFIG) and words in listed
    upload = _uploaded(scratch / "plan.pdf")
    for words in ("is outside the folders the connector reads", "make this call again"):
        assert words in upload and words in listed, words
    for name in (*guards.FILE_DRIVE_TOOLS, *set(guards.FILE_DRIVE_TOOLS.values()), "file://"):
        assert f"`{name}`" in listed, name
    asked = _attached(staged)
    covers = asked.split("Then make this identical call again. ", 1)[1]
    assert covers.startswith("The approval covers each file") and covers in listed and covers in sending
    for words in ("cannot be read", f"{guards.HASH_SECONDS:g} seconds", "hash of that file's bytes"):
        assert words in listed, words


# --- a local file a Drive tool reads ---------------------------------------------------------------------------
# The same connector reads a local file for five Drive tools, under the same folder rule (2.1.0: drive_tools.py
# and drive_helpers._resolve_import_media). update_drive_file and import_to_google_doc, _sheets and _slides take
# `file_path`, a path or a file:// URL; create_drive_file takes `fileUrl`, a file on this disk when it is a file://
# URL. update_drive_file waits for a code, since it changes a document others read; the others ask for none.

UPDATE = "mcp__workspace-mcp__update_drive_file"
DOC_IMPORT = "mcp__workspace-mcp__import_to_google_doc"
NEW_FILE = "mcp__workspace-mcp__create_drive_file"
NO_CODE = [(DOC_IMPORT, "file_path"), ("mcp__workspace_mcp__import_to_google_sheets", "file_path"),
           ("mcp__drive_server__import_to_google_slides", "file_path"), (NEW_FILE, "fileUrl")]
DRIVE = {"user_google_email": "me@example.com", "file_name": "Plan", "file_id": "1aBcD3fGh1jK"}


def _uploaded(named, tool: str = UPDATE, key: str = "file_path", config: dict = CONFIG):
    """The guard's answer to a Drive call that names this local file for the connector to read."""
    return guards.check(tool, {**DRIVE, key: str(named)}, config)


def test_a_drive_update_from_a_file_outside_the_folders_is_refused_with_no_code_and_asks_once_staged(scratch):
    outside = scratch / "plan.pdf"
    for named in (outside, outside.as_uri()):
        reason = _uploaded(named)
        assert f"the file {outside} is outside the folders the connector reads" in reason, reason
        assert f"copy the file into {paths.outbox()}" in reason and "full path as `file_path`" in reason
        assert "make this call again" in reason and "approve" not in reason and approvals.pending() == []
    staged = Path(shutil.copy(outside, paths.outbox() / "plan.pdf"))
    assert "approval" in _uploaded(staged) and "approval" in _uploaded(staged.as_uri())
    for as_it_was in ({"content": "# Plan"}, {"file_url": "https://files.example.com/plan.docx"}, {"name": "Plan v2"},
                      {"file_path": None}):
        assert "approval" in guards.check(UPDATE, {**DRIVE, **as_it_was}, CONFIG), as_it_was


@pytest.mark.parametrize("tool,key", NO_CODE)
def test_a_drive_tool_that_asks_for_no_code_is_refused_for_a_file_outside_the_folders_and_goes_once_staged(tool, key, scratch):
    def named(file) -> str:
        return Path(file).as_uri() if key == "fileUrl" else str(file)

    outside = scratch / "plan.pdf"
    reason = _uploaded(named(outside), tool, key)
    assert f"the file {outside} is outside the folders the connector reads" in reason, reason
    assert f"copy the file into {paths.outbox()}" in reason and f"`{key}`" in reason and "make this call again" in reason
    assert ("after `file://`" in reason) is (key == "fileUrl")
    staged = shutil.copy(outside, paths.outbox() / "plan.pdf")
    assert _uploaded(named(staged), tool, key) is None
    assert guards.check(tool, {**DRIVE, "content": "# Plan"}, CONFIG) is None  # nothing read from this disk
    assert approvals.pending() == []
    asks = {**CONFIG, "send_tools": [f"mcp__*__{tool.rsplit('__', 1)[-1]}"]}  # where the principal made it wait for a code
    assert "outside the folders" in _uploaded(named(outside), tool, key, asks) and approvals.pending() == []
    assert "approval" in _uploaded(named(staged), tool, key, asks)


def test_a_drive_file_is_read_as_the_connector_reads_it(scratch, monkeypatch):
    """Whole, there, a file, links followed, and not one it reads from no folder: the rule a mail attachment has."""
    outbox, outside = paths.outbox(), scratch / "plan.pdf"
    _put(outbox, "staged.pdf")
    (outbox / "leads-out.pdf").symlink_to(outside)
    assert "outside the folders" in _uploaded(outbox / "leads-out.pdf")
    assert f"the file {outbox / 'gone.docx'} does not exist" in _uploaded(outbox / "gone.docx")
    assert f"the file {outbox} is not a file" in _uploaded(outbox)
    monkeypatch.chdir(outbox)
    for partial in ("staged.pdf", "", "file:staged.pdf", "https://files.example.com/plan.docx"):  # an empty one is still a path to it
        assert "is not a full path" in _uploaded(partial), partial
    never = _uploaded(_put(outbox, ".env"))
    assert "is one the connector never reads" in never and "copy the file into" not in never
    assert approvals.pending() == []


def test_a_file_url_is_turned_into_a_path_as_the_connector_turns_it(scratch):
    """It takes the URL's path, percent-decoded, without its query or fragment, and puts any host but localhost in
    front of it, which names no file on this disk."""
    spaced = _put(paths.outbox(), "plan v2 100%.docx")
    for url in (spaced.as_uri(), "file://localhost" + quote(str(spaced)), "file://LOCALHOST" + quote(str(spaced)),
                "file:" + quote(str(spaced)), spaced.as_uri() + "?download=1#page=2"):
        assert "%20" in url and "%25" in url
        assert "approval" in _uploaded(url), url
        assert _uploaded(url, NEW_FILE, "fileUrl") is None, url
    elsewhere = "file://fileserver" + quote(str(spaced))
    for reason in (_uploaded(elsewhere), _uploaded(elsewhere, NEW_FILE, "fileUrl")):
        assert f"the file //fileserver{spaced} does not exist" in reason and "approve" not in reason, reason
    assert len(approvals.pending()) == 5  # one for each spelling of the staged file's URL in an update


@pytest.mark.parametrize("tool", [UPDATE, DOC_IMPORT])
def test_a_file_on_this_disk_given_as_file_url_is_refused_since_the_connector_fetches_only_http_there(tool, scratch):
    """`file_url` is fetched over http or https: the connector refuses a file:// URL there, which for an update is
    after the principal's code. A file on this disk goes under `file_path`."""
    staged = Path(shutil.copy(scratch / "plan.pdf", paths.outbox() / "plan.pdf"))
    for named in (staged.as_uri(), str(staged), "FILE://localhost" + str(staged)):  # as a URL, or as the bare path
        reason = guards.check(tool, {**DRIVE, "file_url": named}, CONFIG)
        assert "`file_url`" in reason and "full path as `file_path`" in reason and "make this call again" in reason, named
        assert named in reason and "approve" not in reason and approvals.pending() == [], named
    remote = guards.check(tool, {**DRIVE, "file_url": "https://files.example.com/plan.docx"}, CONFIG)
    assert remote is None if tool == DOC_IMPORT else "approval" in remote  # an address it does fetch is as it was


def test_the_rule_is_these_five_tools_and_a_remote_address_or_another_tool_is_as_it_was(scratch):
    outside = scratch / "plan.pdf"
    for tool in ("mcp__workspace-mcp__get_drive_file_content", "mcp__files__upload_file", "mcp__workspace-mcp__create_drive_folder"):
        assert guards.check(tool, {**DRIVE, "file_path": str(outside), "fileUrl": outside.as_uri()}, CONFIG) is None, tool
    edit = {"document_id": "doc-1", "text": "Agenda", "file_path": str(outside)}
    assert "approval" in guards.check("mcp__workspace-mcp__modify_doc_text", edit, CONFIG)
    for remote in ("https://files.example.com/plan.pdf", "http://files.example.com/plan.pdf", str(outside)):
        assert _uploaded(remote, NEW_FILE, "fileUrl") is None, remote  # fetched, or no URL at all: nothing read from this disk
    assert _uploaded(outside.as_uri(), NEW_FILE, "file_path") is None  # the key this tool reads is `fileUrl`


# --- the approval binds the bytes of each file the connector reads ---------------------------------------------
# An approval is keyed by a digest of the whole call, and a file the call names went into it as its path alone:
# a copy replaced in the outbox between the principal's code and the call went out under the old approval. The
# digest now takes in the content hash of each file the connector will read, as the iMessage sender binds a photo.

def _code(reason: str) -> str:
    return re.search(r"\bcode ([a-z0-9]{6})\b", reason).group(1)


def _staged(scratch) -> Path:
    return Path(shutil.copy(scratch / "plan.pdf", paths.outbox() / "plan.pdf"))


@pytest.mark.parametrize("ask", [_attached, _uploaded, lambda file: _uploaded(Path(file).as_uri())],
                         ids=["a mail attachment", "a Drive file by its path", "a Drive file by its URL"])
def test_a_file_replaced_between_the_approval_and_the_call_needs_a_new_approval(ask, scratch):
    staged = _staged(scratch)
    approved = staged.read_bytes()
    first = ask(staged)
    assert "as it is now" in first  # the request says what it covers
    _approve(first)
    staged.write_bytes(b"%PDF-1.4\nanother plan\n")
    second = ask(staged)
    assert "approval" in second and _code(second) != _code(first) and len(approvals.pending()) == 1
    staged.write_bytes(approved)  # the bytes the principal approved, back in place: that approval is theirs
    assert ask(staged) is None
    assert "approval" in ask(staged)  # and spent once


def test_the_bytes_are_bound_and_not_the_files_size_or_date(scratch):
    staged = _staged(scratch)
    before = staged.stat()
    _approve(_attached(staged))
    staged.write_bytes(staged.read_bytes().replace(b"1.4", b"1.5"))  # as long as it was
    os.utime(staged, ns=(before.st_atime_ns, before.st_mtime_ns))  # and dated as it was
    after = staged.stat()
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)
    assert "approval" in _attached(staged)


def test_a_link_pointed_at_another_file_after_the_approval_needs_a_new_one_though_the_call_is_the_same(scratch):
    """The connector follows links, so the bytes bound are those of the file a link leads to."""
    staged, other = _staged(scratch), _put(paths.outbox(), "other.pdf")
    other.write_bytes(b"%PDF-1.4\nthe other plan\n")
    link = scratch / "latest.pdf"
    link.symlink_to(staged)
    _approve(_attached(link))
    link.unlink()
    link.symlink_to(other)
    assert "approval" in _attached(link)
    link.unlink()
    link.symlink_to(staged)
    assert _attached(link) is None


def test_each_file_of_a_call_is_bound_and_a_file_the_call_does_not_name_is_not(scratch):
    one, two, beside = _staged(scratch), _put(paths.outbox(), "terms.pdf"), _put(paths.outbox(), "notes.txt")
    call = {**MAIL, "attachments": [{"path": str(one)}, {"path": str(two)}, AS_CONTENT[0]]}
    for changed in (one, two):
        _approve(guards.check(SEND, call, CONFIG))
        kept = changed.read_bytes()
        changed.write_bytes(kept + b"a line added\n")
        assert "approval" in guards.check(SEND, call, CONFIG), changed
        changed.write_bytes(kept)
        assert guards.check(SEND, call, CONFIG) is None, changed
    _approve(guards.check(SEND, call, CONFIG))
    beside.write_bytes(b"another session's file, staged beside these\n")
    assert guards.check(SEND, call, CONFIG) is None
    plain = {"channel_id": "C1", "message": "The plan is in the shared folder."}  # a call that names no file is as it was
    _approve(guards.check(SLACK, plain, CONFIG))
    assert guards.check(SLACK, plain, CONFIG) is None


def test_a_file_too_large_to_hash_in_the_guards_time_refuses_the_call_and_is_never_sent_on_its_path_alone(scratch, monkeypatch):
    """A harness passes over a hook that runs past its time, so the read is bounded well inside it: a file whose
    bytes cannot be bound in that time is refused."""
    hooks = json.loads((Path(__file__).resolve().parents[1] / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    given = min(hook["timeout"] for group in hooks["hooks"]["PreToolUse"] for hook in group["hooks"])
    allowed = guards.HASH_SECONDS
    assert 0 < allowed <= given / 2
    staged = _staged(scratch)
    _approve(_attached(staged))
    monkeypatch.setattr(guards, "HASH_SECONDS", 0)  # as if the file took longer than the guard may spend
    refused = _attached(staged)
    assert f"the attachment {staged} cannot be read" in refused and "approve" not in refused, refused
    monkeypatch.setattr(guards, "HASH_SECONDS", allowed)
    assert _attached(staged) is None  # the approval was kept


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a file whatever its mode")
@pytest.mark.parametrize("ask,what", [(_attached, "the attachment"), (_uploaded, "the file")],
                         ids=["a mail attachment", "a Drive file"])
def test_a_file_that_cannot_be_read_when_the_call_is_made_refuses_the_call(ask, what, scratch):
    staged = _staged(scratch)
    staged.chmod(0)
    try:
        unasked = ask(staged)
        assert f"{what} {staged} cannot be read" in unasked and "approve" not in unasked and approvals.pending() == []
        staged.chmod(0o600)
        _approve(ask(staged))
        staged.chmod(0)
        refused = ask(staged)
        assert f"{what} {staged} cannot be read" in refused and "approve" not in refused
    finally:
        staged.chmod(0o600)
    assert ask(staged) is None  # the approval was kept for the call the connector can make
