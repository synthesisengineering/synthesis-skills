"""One approval for a reviewed batch of sends (design note M37 part 4, 2026-11-14).

A seat drafts replies in batches of about twenty; the principal reads every text and recipient and types one code
for the batch's digest. Each entry then sends once, word for word, within 12 hours, from a session on the batch's
project. A connector entry binds the whole call (the tool and its exact input, string values compared after their
line endings are written one way); a browser entry binds one call that types the entry's text and sends it, on the
page whose address names the conversation; a messages entry binds the local sender's handle or members and text.
Every other check runs first, and anything that differs falls back to the code per call.
"""

import copy
import hashlib
import json
import subprocess
import sys
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from synthesis import board, guards, paths, sends

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "inbox-backlog"
SLACK, MAIL, EVENT = "mcp__slack__slack_send_message", "mcp__workspace-mcp__send_gmail_message", "mcp__workspace__create_event"
CHROME = "mcp__claude-in-chrome__browser_batch"
CONFIG = {"send_tools": ["mcp__*__slack_send_message", "mcp__*__send_gmail_message", "mcp__*__create_event"],
          "send_window_signatures": [r"Helperbot here"],
          "forbidden_phrases": [{"name": "delay-apology", "pattern": r"sorry for the delay", "why": "say what happened"}]}
REPLY = "Thanks, Tuesday works. I'll bring the notes."
SAID = {"channel_id": "D0123", "message": REPLY}
CALL = {"tool": SLACK, "input": SAID}
E2EE, PLAIN = "https://www.facebook.com/messages/e2ee/t/1000000001/", "https://www.facebook.com/messages/t/1000000002/"
CHAT = {"channel": "messenger", "to": "facebook.com/messages/e2ee/t/1000000001", "text": REPLY}
TEXT = {"channel": "messages", "to": "+15550100", "text": REPLY}
SESSION = {"session_id": "S-principal"}


@pytest.fixture(autouse=True)
def _on_the_project(principal):
    """The principal's session (the `principal` fixture's) works on the batch's project."""
    board.touch("S-principal", project=PROJECT)


def today() -> list:
    return sends.ledger(time.strftime("%Y-%m-%d"))


def opened(entries, project=PROJECT, name="replies-1") -> dict:
    """A batch the principal's code opened, as `synthesis sends batch` does once it holds the grant."""
    return sends.open_batch({"batch": name, "project": project, "entries": entries})


def batch_file(folder: Path, entries, project=PROJECT, name="replies-1") -> Path:
    file = folder / f"{name}.json"
    file.write_text(json.dumps({"batch": name, "project": project, "entries": entries}, ensure_ascii=False), encoding="utf-8")
    return file


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "synthesis.cli", *args], capture_output=True, text=True, cwd=ROOT,
                          stdin=subprocess.DEVNULL)


def page(record: Path, url: str, tab: int = 7, others: dict = None) -> dict:
    """The session, its record holding Claude in Chrome's newest result: the call ran on this page (others: more tabs)."""
    ident = f"toolu_{time.time_ns()}"
    listing = "\n".join(f"  • tabId {t}: \"Messenger\" (\"{u}\")" for t, u in {tab: url, **(others or {})}.items())
    text = f"Typed\n\nTab Context:\n- Executed on tabId: {tab}\n- Available tabs:\n{listing}"
    with record.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": ident, "name": CHROME, "input": {}}]}}) + "\n")
        handle.write(json.dumps({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": ident, "content": [{"type": "text", "text": text}]}]}}) + "\n")
    return {**SESSION, "transcript_path": str(record)}


def read_calendar(record: Path) -> None:
    at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    ident = f"toolu_{time.time_ns()}"
    with record.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "assistant", "timestamp": at, "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": ident, "name": "mcp__workspace__get_events", "input": {}}]}}) + "\n")
        handle.write(json.dumps({"type": "user", "timestamp": at, "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": ident, "content": "[]"}]}}) + "\n")


def steps(*given):
    return {"actions": [{"name": n, "input": i} for n, i in given]}


def typed(text):
    return ("computer", {"action": "type", "text": text, "action_summary": "Types the reply"})


def key(keys, said="Presses the key"):
    return ("computer", {"action": "key", "text": keys, "action_summary": said})


RETURN = key("Return", "Sends the reply")
FOCUS = ("computer", {"action": "left_click", "ref": "ref_4", "action_summary": "Focuses the message box"})
CLEAR = (key("cmd+a", "Selects everything in the message box"), key("Backspace", "Clears the message box"))


def typed_and_sent(text=REPLY):
    return steps(*CLEAR, typed(text), RETURN)


def held(reason) -> bool:
    return bool(reason) and "approve followed by the code" in reason


# --- the batch file and its digest -----------------------------------------------------------------------------


def test_the_digest_binds_every_field_and_not_the_files_layout(tmp_path):
    batch = {"batch": "replies-1", "project": PROJECT, "entries": [CALL, CHAT, TEXT]}
    first = sends.batch_digest(batch)
    assert first == hashlib.sha256(json.dumps(batch, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                                   .encode("utf-8")).hexdigest()
    changes = [("batch", None, "replies-2"), ("project", None, "another"), (0, "tool", "mcp__slack2__slack_send_message"),
               (0, "input", {**SAID, "channel_id": "D0124"}), (0, "input", {**SAID, "message": REPLY + " "}),
               (1, "channel", "instagram"), (1, "to", "facebook.com/messages/t/1000000001"), (1, "text", REPLY[:-1]),
               (2, "to", "+15550101"), (2, "text", REPLY.replace("I'll", "I’ll"))]
    for where, field, value in changes:
        other = copy.deepcopy(batch)
        if field is None:
            other[where] = value
        else:
            other["entries"][where][field] = value
        assert sends.batch_digest(other) != first, (where, field)
    assert sends.batch_digest({**batch, "entries": [CHAT, CALL, TEXT]}) != first  # the order of the entries
    assert sends.batch_digest({**batch, "entries": [CALL, CHAT]}) != first
    laid_out = tmp_path / "laid-out.json"  # the same batch written another way
    laid_out.write_text(json.dumps({"entries": batch["entries"], "project": PROJECT, "batch": "replies-1"}, indent=4),
                        encoding="utf-8")
    assert sends.batch_digest(sends.read_batch(str(laid_out))) == first


@pytest.mark.parametrize("batch, says", [
    ({"batch": "b", "project": PROJECT, "entries": []}, "1 to 50"),
    ({"batch": "b", "project": PROJECT, "entries": [{"tool": SLACK, "input": {"channel_id": "D1", "message": f"Note {i}."}}
                                                    for i in range(51)]}, "1 to 50"),
    ({"batch": "b", "project": "", "entries": [CALL]}, "project"),
    ({"batch": "b", "project": PROJECT, "entries": [CALL], "note": "extra"}, "nothing else"),
    ({"batch": "b", "project": PROJECT, "entries": [{**CALL, "why": "context"}]}, "entry 1"),
    ({"batch": "b", "project": PROJECT, "entries": [CALL, {**CHAT, "to": "https://www.facebook.com/groups/1/"}]}, "entry 2"),
    ({"batch": "b", "project": PROJECT, "entries": [{**CHAT, "channel": "instagram"}]}, "entry 1"),
    ({"batch": "b", "project": PROJECT, "entries": [{**TEXT, "to": "Pat"}]}, "entry 1"),
    ({"batch": "b", "project": PROJECT, "entries": [{**CHAT, "text": "   "}]}, "entry 1"),
    ({"batch": "b", "project": PROJECT, "entries": [{"tool": "mcp__claude-in-chrome__computer", "input": {"action": "key"}}]},
     "entry 1"),
    ({"batch": "b", "project": PROJECT, "entries": [CALL, CHAT, CALL]}, "entry 3 repeats entry 1"),
])
def test_a_batch_file_of_another_shape_is_refused_with_what_is_wrong(tmp_path, batch, says):
    file = tmp_path / "batch.json"
    file.write_text(json.dumps(batch), encoding="utf-8")
    with pytest.raises(ValueError, match=says):
        sends.read_batch(str(file))


def test_a_key_given_twice_or_a_number_json_lacks_is_refused(tmp_path):
    """What the principal reads must be what the digest binds: a reader that keeps the first of two keys and one that
    keeps the last would show different words."""
    twice = tmp_path / "twice.json"
    twice.write_text('{"batch": "b", "project": "p", "entries": [{"channel": "messages", "to": "+15550100", '
                     '"text": "Shown.", "text": "Sent."}]}', encoding="utf-8")
    with pytest.raises(ValueError, match="twice"):
        sends.read_batch(str(twice))
    odd = tmp_path / "odd.json"
    odd.write_text('{"batch": "b", "project": "p", "entries": [{"tool": "%s", "input": {"n": NaN}}]}' % SLACK, encoding="utf-8")
    with pytest.raises(ValueError):
        sends.read_batch(str(odd))


@pytest.mark.parametrize("address, place", [
    ("facebook.com/messages/e2ee/t/1000000001", ("messenger", "facebook.com/messages/e2ee/t/1000000001")),
    ("https://www.facebook.com/messages/e2ee/t/1000000001/?locale=en_US#x", ("messenger", "facebook.com/messages/e2ee/t/1000000001")),
    ("https://web.facebook.com/messages/t/1000000002", ("messenger", "facebook.com/messages/t/1000000002")),
    ("messenger.com/t/1000000003/", ("messenger", "messenger.com/t/1000000003")),
    ("https://www.messenger.com/e2ee/t/1000000004", ("messenger", "messenger.com/e2ee/t/1000000004")),
    ("https://facebook.com.example.org/messages/t/1", None), ("https://notfacebook.com/messages/t/1", None),
    ("https://www.facebook.com/messages/", None), ("https://www.facebook.com/messages/t/", None),
    ("https://www.facebook.com/messages/t/1/photos", None), ("https://www.facebook.com/Messages/t/1", None),
    ("https://www.facebook.com/messages/t/%31", None), ("+15550100", None),
    ("https://www.facebook.com/messages/t/١٢٣", None),  # digits of another script are no id
])
def test_a_conversation_is_its_site_and_path_with_its_slash_and_query_left_off(address, place):
    """The coordinator, 2026-11-14: facebook.com's chat list links every chat to `/messages/e2ee/t/<digits>/`. An
    encrypted chat's address and a plain one's are two conversations, and so are the two sites' (host plus path,
    a trailing slash and the query ignored)."""
    assert sends.conversation(address) == place


# --- asking: `synthesis sends batch <file>` ----------------------------------------------------------------------


def test_only_the_principals_code_for_that_digest_opens_a_batch(tmp_path, principal):
    file = batch_file(tmp_path, [CALL, CHAT])
    digest = sends.batch_digest(sends.read_batch(str(file)))
    command = f"synthesis sends batch {file}"
    reason = guards.check("Bash", {"command": command}, CONFIG, cwd=str(tmp_path))
    assert held(reason) and digest[:12] in reason and "2 sends" in reason and str(file) in reason and "--show" in reason
    for free in (f"synthesis sends batch {file} --show", "synthesis sends batch --help", "synthesis sends status",
                 "synthesis sends close", "synthesis sends log"):
        assert guards.check("Bash", {"command": free}, CONFIG, cwd=str(tmp_path)) is None, free
    for spelled in (f"python3 -m synthesis.cli sends batch {file}", f"synthesis --session S-principal sends batch {file}",
                    f"cd {tmp_path} && synthesis sends batch {file.name}"):
        assert held(guards.check("Bash", {"command": spelled}, CONFIG, cwd=str(ROOT))), spelled
    shown = _cli("sends", "batch", str(file), "--show")
    assert shown.returncode == 0 and REPLY in shown.stdout and digest in shown.stdout and SLACK in shown.stdout
    assert "facebook.com/messages/e2ee/t/1000000001" in shown.stdout and sends.batches() == []
    listed = _cli("--session", "S-principal", "sends", "batch", str(file))
    assert listed.returncode == 2 and "type approve" in listed.stderr and sends.batches() == []
    assert digest in listed.stdout and REPLY not in listed.stdout  # the count and recipients; the texts take --show
    principal(reason)
    assert guards.check("Bash", {"command": command}, CONFIG, cwd=str(tmp_path)) is None
    done = _cli("sends", "batch", str(file))
    assert done.returncode == 0 and digest[:12] in done.stdout and "2 of 2 entries left" in done.stdout
    assert [b["digest"] for b in sends.batches()] == [digest]
    assert _cli("sends", "batch", str(file)).returncode == 2  # the grant was spent


def test_a_file_changed_after_the_hold_does_not_get_the_grant(tmp_path, principal):
    file = batch_file(tmp_path, [CALL])
    principal(guards.check("Bash", {"command": f"synthesis sends batch {file}"}, CONFIG, cwd=str(tmp_path)))
    batch_file(tmp_path, [{"tool": SLACK, "input": {**SAID, "message": REPLY + " Bring the keys too."}}])
    assert held(guards.check("Bash", {"command": f"synthesis sends batch {file}"}, CONFIG, cwd=str(tmp_path)))
    assert _cli("sends", "batch", str(file)).returncode == 2 and sends.batches() == []


def test_a_batch_the_command_would_refuse_is_never_put_to_the_principal(tmp_path):
    reason = guards.check("Bash", {"command": f"synthesis sends batch {tmp_path / 'absent.json'}"}, CONFIG, cwd=str(tmp_path))
    assert reason and "can't open" in reason and not held(reason)
    bad = batch_file(tmp_path, [], name="empty")
    assert "1 to 50" in guards.check("Bash", {"command": f"synthesis sends batch {bad}"}, CONFIG, cwd=str(tmp_path))


def test_editing_the_file_after_the_grant_changes_nothing(tmp_path, principal):
    file = batch_file(tmp_path, [CALL])
    principal(guards.check("Bash", {"command": f"synthesis sends batch {file}"}, CONFIG, cwd=str(tmp_path)))
    assert _cli("sends", "batch", str(file)).returncode == 0
    edited = {**SAID, "message": "Something else entirely."}
    batch_file(tmp_path, [{"tool": SLACK, "input": edited}])
    assert held(guards.check(SLACK, edited, CONFIG, session=SESSION))
    assert guards.check(SLACK, SAID, CONFIG, session=SESSION) is None


def test_a_post_beside_an_approved_window_or_batch_command_is_still_judged(tmp_path, principal):
    """A held window code let the whole line through, a post after it included."""
    window = "synthesis sends open --hours 2 --sends 3 --channels jira"
    principal(guards.check("Bash", {"command": window}, CONFIG, cwd=str(tmp_path)))
    file = batch_file(tmp_path, [CALL])
    principal(guards.check("Bash", {"command": f"synthesis sends batch {file}"}, CONFIG, cwd=str(tmp_path)))
    for command in (window, f"synthesis sends batch {file}"):
        assert guards.check("Bash", {"command": command}, CONFIG, cwd=str(tmp_path)) is None
        reason = guards.check("Bash", {"command": f'{command} && bkt pr comment 5 -m "Approved from my side."'},
                              CONFIG, cwd=str(tmp_path))
        assert held(reason) and "posts to bitbucket" in reason, command


# --- what an entry covers ----------------------------------------------------------------------------------------


def test_each_entry_sends_once_and_the_ledger_names_the_batch_and_the_entry():
    other = {**SAID, "channel_id": "D0999"}
    data = opened([{"tool": SLACK, "input": other}, CALL])
    assert guards.check(SLACK, SAID, CONFIG, session=SESSION) is None
    assert held(guards.check(SLACK, SAID, CONFIG, session=SESSION))  # spent
    entry = today()[-1]
    assert entry["how"] == f"batch:{data['digest'][:12]}:1" and entry["channel"] == "slack"
    assert f"batch:{data['digest'][:12]}:1" in _cli("sends", "log").stdout
    assert guards.check(SLACK, other, CONFIG, session=SESSION) is None


def test_two_sessions_racing_for_one_entry_send_it_once():
    board.touch("S-other", project=PROJECT)
    opened([CALL])
    results, start = [], threading.Barrier(6)

    def send(session_id):
        start.wait()
        results.append(guards.check_send(SLACK, SAID, CONFIG, {"session_id": session_id}))
    racers = [threading.Thread(target=send, args=(s,)) for s in ("S-principal", "S-other") * 3]
    for racer in racers:
        racer.start()
    for racer in racers:
        racer.join()
    assert sum(r is None for r in results) == 1 and all(held(r) for r in results if r is not None)
    assert len([e for e in today() if e["how"].startswith("batch:")]) == 1


@pytest.mark.parametrize("tool, given", [
    (SLACK, {**SAID, "channel_id": "D0124"}),                         # another recipient
    (SLACK, {**SAID, "message": REPLY + " "}),                        # a trailing space
    (SLACK, {**SAID, "message": REPLY.replace("o", "о", 1)}),    # a lookalike letter (Cyrillic o)
    (SLACK, {**SAID, "message": REPLY[:-1] + "!"}),                   # one character
    (SLACK, {**SAID, "thread_ts": "1731600000.000100"}),              # a field more
    (SLACK, {**SAID, "channel_id": "d0123"}),                         # the recipient in another case
    ("mcp__slack2__slack_send_message", SAID),                       # another tool
])
def test_any_difference_from_an_entry_is_held(tool, given):
    opened([CALL])
    assert held(guards.check(tool, given, CONFIG, session=SESSION))
    assert guards.check(SLACK, SAID, CONFIG, session=SESSION) is None  # the entry was not spent by them


def test_line_endings_are_the_one_difference_overlooked():
    paragraphs = "Thanks for the notes.\n\nTuesday works."
    opened([{"tool": SLACK, "input": {**SAID, "message": paragraphs}}])
    assert guards.check(SLACK, {**SAID, "message": paragraphs.replace("\n", "\r\n")}, CONFIG, session=SESSION) is None
    entry = {"tool": SLACK, "input": {**SAID, "message": paragraphs.replace("\n", "\r")}}
    assert sends.call_entry(entry, SLACK, {**SAID, "message": paragraphs})
    assert not sends.call_entry({"tool": SLACK, "input": {**SAID, "flag": 1}}, SLACK, {**SAID, "flag": True})


def test_the_messages_sender_is_matched_by_its_handle_or_members_and_text():
    """messages_send.py asks the guard itself: `--to` as imessage_send {to, text}, `--members` as messages_send {to:
    the sorted members, service, text, chat}, a photo by its hash beside them."""
    opened([TEXT, {"channel": "messages", "to": "+15550102,+15550101", "text": REPLY}])
    for tool, given in (("imessage_send", {"to": "+15550199", "text": REPLY}),
                        ("imessage_send", {"to": "+15550100", "text": REPLY + "!"}),
                        ("imessage_send", {"to": "+15550100", "text": REPLY, "photo": {"name": "a.jpg", "bytes": 9, "sha256": "0" * 64}}),
                        ("messages_send", {"to": ["+15550100"], "service": "iMessage", "text": REPLY, "chat": "chat-1"}),
                        ("messages_send", {"to": ["+15550101"], "service": "SMS", "text": REPLY, "chat": "chat-9"})):
        assert held(guards.check_send(tool, given, CONFIG)), (tool, given)
    assert guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG) is None
    members = {"to": ["+15550101", "+15550102"], "service": "SMS", "text": REPLY, "chat": "chat-9"}
    assert guards.check_send("messages_send", members, CONFIG) is None
    assert held(guards.check_send("messages_send", members, CONFIG))


def test_a_call_that_has_the_connector_read_a_file_waits_for_its_own_code(tmp_path, monkeypatch):
    """The batch binds a path, not the bytes a file holds when the call comes; the code per call binds them."""
    for name in ("ALLOWED_FILE_DIRS", "WORKSPACE_ATTACHMENT_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "user"))
    paths.outbox().mkdir(parents=True)
    (paths.outbox() / "plan.pdf").write_bytes(b"%PDF-1.4\n")
    mail = {"to": "a@example.com", "subject": "Plan", "body": "<p>The plan is attached.</p>", "body_format": "html",
            "attachments": [{"path": str(paths.outbox() / "plan.pdf")}]}
    opened([{"tool": MAIL, "input": mail}])
    assert held(guards.check_send(MAIL, mail, CONFIG, SESSION))


# --- the browser: one call types the text and sends it, on the conversation's page ------------------------------


@pytest.mark.parametrize("entry_to, url, goes", [
    ("facebook.com/messages/e2ee/t/1000000001", E2EE, True),
    ("https://www.facebook.com/messages/e2ee/t/1000000001/", "https://www.facebook.com/messages/e2ee/t/1000000001?locale=en_US", True),
    ("facebook.com/messages/t/1000000002", PLAIN, True),
    ("messenger.com/t/1000000003", "https://www.messenger.com/t/1000000003/", True),
    ("messenger.com/e2ee/t/1000000004", "https://www.messenger.com/e2ee/t/1000000004", True),
    ("facebook.com/messages/e2ee/t/1000000001", "https://www.facebook.com/messages/t/1000000001/", False),
    ("facebook.com/messages/t/1000000002", "https://www.facebook.com/messages/e2ee/t/1000000002/", False),
    ("messenger.com/t/1000000003", "https://www.messenger.com/e2ee/t/1000000003/", False),
    ("messenger.com/e2ee/t/1000000004", "https://www.messenger.com/t/1000000004/", False),
    ("facebook.com/messages/e2ee/t/1000000001", "https://www.messenger.com/e2ee/t/1000000001/", False),
    ("facebook.com/messages/e2ee/t/1000000001", "https://www.facebook.com/messages/e2ee/t/1000000009/", False),
    ("facebook.com/messages/e2ee/t/1000000001", "https://www.facebook.com/messages/e2ee/t/10000000011/", False),
    ("facebook.com/messages/e2ee/t/1000000001", "https://facebook.com.example.org/messages/e2ee/t/1000000001/", False),
    ("facebook.com/messages/e2ee/t/1000000001", "https://www.facebook.com/messages/", False),
])
def test_a_browser_entry_goes_only_on_the_page_that_names_its_conversation(tmp_path, entry_to, url, goes):
    opened([{**CHAT, "to": entry_to}])
    reason = guards.check(CHROME, typed_and_sent(), CONFIG, session=page(tmp_path / "record.jsonl", url))
    assert (reason is None) is goes, reason
    assert goes or held(reason)


def test_a_return_or_send_click_in_a_call_that_did_not_type_the_text_is_held(tmp_path, principal):
    opened([CHAT])
    session = page(principal.transcript, E2EE)
    send = ("computer", {"action": "left_click", "ref": "ref_5", "action_summary": "Clicks Send"})
    for call in (steps(RETURN), steps(send), steps(*CLEAR, RETURN)):
        assert held(guards.check(CHROME, call, CONFIG, session=session)), call
    assert guards.check(CHROME, steps(*CLEAR, typed(REPLY), send), CONFIG, session=session) is None


def test_a_call_clears_the_box_types_the_whole_text_and_sends_it_once_or_waits(tmp_path):
    """The coordinator, 2026-11-14: on Messenger a plain Return sends, so paragraphs are typed with shift and Return
    between them, and the text is rebuilt from the typed words and those line breaks. Typing appends to whatever
    draft the box holds, so the call first selects everything and deletes it (one click that says it focuses the box
    may come before); anything else between the clearing and the send leaves the code per call."""
    two = "First paragraph of the reply.\nSecond paragraph."
    opened([{**CHAT, "text": two}])
    session = page(tmp_path / "record.jsonl", E2EE)
    one, line, rest = typed("First paragraph of the reply."), key("shift+Return", "Starts a new line"), typed("Second paragraph.")
    elsewhere = ("computer", {"action": "left_click", "ref": "ref_8", "action_summary": "Clicks the conversation header"})
    for call in (steps(*CLEAR, typed(two), RETURN),                           # a typed line break sends its line alone
                 steps(one, line, rest, RETURN),                              # no clearing: a draft in the box would go too
                 steps(CLEAR[1], one, line, rest, RETURN),                    # Backspace without select-all
                 steps(*CLEAR, one, line, rest, key("Up", "Moves up"), RETURN),  # an arrow key before the send
                 steps(*CLEAR, one, line, rest, elsewhere, RETURN),           # a click elsewhere
                 steps(*CLEAR, one, ("computer", {"action": "scroll", "coordinate": [5, 5], "scroll_direction": "up"}),
                       line, rest, RETURN),                                   # a scroll
                 steps(*CLEAR, one, line, rest, ("javascript_tool", {"text": "document.title", "action_summary": "Reads it"}),
                       RETURN),                                               # a script
                 steps(*CLEAR, one, rest, RETURN),                            # no line between the paragraphs
                 steps(*CLEAR, one, line, rest, RETURN, typed("More."), RETURN),  # a second send
                 steps(*CLEAR, one, line, rest, key("cmd+Return", "Sends it")),
                 steps(elsewhere, *CLEAR, one, line, rest, RETURN),           # a click that does not say it focuses the box
                 steps(FOCUS, FOCUS, *CLEAR, one, line, rest, RETURN),
                 steps(("form_input", {"ref": "ref_4", "value": two, "action_summary": "Fills the message box"}), RETURN),
                 steps(("computer", {"action": "left_click_drag", "start_coordinate": [1, 1], "coordinate": [9, 9]}),
                       *CLEAR, one, line, rest, RETURN)):
        assert guards.check(CHROME, call, CONFIG, session=session), call
    assert guards.check(CHROME, steps(FOCUS, *CLEAR, one, line, rest, RETURN), CONFIG, session=session) is None
    opened([{**CHAT, "text": two}], name="replies-2")
    clear = key("ctrl+a Delete", "Clears the message box")  # the two keys in one action, and Enter for Return
    assert guards.check(CHROME, steps(clear, one, key("shift+Enter", "Starts a new line"), rest, key("Enter", "Sends it")),
                        CONFIG, session=session) is None


def test_the_page_is_the_conversation_a_navigate_step_of_the_same_call_opens(tmp_path):
    opened([CHAT])
    session = page(tmp_path / "record.jsonl", "https://www.facebook.com/")
    there = ("navigate", {"url": E2EE, "tabId": 7})
    elsewhere = ("navigate", {"url": "https://www.facebook.com/messages/e2ee/t/1000000009/", "tabId": 7})
    on = lambda step: (step[0], {**step[1], "tabId": 7})  # noqa: E731
    clear = [on(c) for c in CLEAR]
    assert held(guards.check(CHROME, steps(there, *clear, on(typed(REPLY)), elsewhere, on(RETURN)), CONFIG, session=session))
    assert held(guards.check(CHROME, steps(there, *clear, on(typed(REPLY)), ("navigate", {"url": "back", "tabId": 7}), on(RETURN)),
                             CONFIG, session=session))
    assert held(guards.check(CHROME, typed_and_sent(), CONFIG, session={**SESSION, "transcript_path": str(tmp_path / "none")}))
    assert guards.check(CHROME, steps(there, *clear, on(typed(REPLY)), on(RETURN)), CONFIG, session=session) is None


def test_a_draft_is_cleared_but_a_paste_or_an_upload_keeps_the_page_on_the_code(tmp_path, principal):
    """A typed text split across calls: the call's own clearing takes out a draft typed earlier. A paste, a file, a
    drop or a script's work may stay beside the words (a pasted image is an attachment), so the page's entries wait
    for the code per call until a send from it goes, and that code spends the entry with the send."""
    opened([CHAT, {**CHAT, "text": "Second reply."}, {**CHAT, "text": "Third reply."}])
    session = page(principal.transcript, E2EE)
    assert guards.check(CHROME, steps(typed("P.S. ")), CONFIG, session=session) is None  # typing alone sends nothing
    assert guards.check(CHROME, typed_and_sent(), CONFIG, session=session) is None
    assert guards.check(CHROME, steps(key("cmd+v", "Pastes the photo")), CONFIG, session=session) is None
    reason = guards.check(CHROME, typed_and_sent("Second reply."), CONFIG, session=session)
    assert held(reason) and "earlier" in reason
    principal(reason)
    assert guards.check(CHROME, typed_and_sent("Second reply."), CONFIG, session=session) is None
    assert today()[-1]["how"] == "approval"
    assert held(guards.check(CHROME, typed_and_sent("Second reply."), CONFIG, session=session))  # one message, one release
    upload = {"imageId": "img-1", "ref": "ref_3", "tabId": 7}
    assert guards.check("mcp__claude-in-chrome__upload_image", upload, CONFIG, session=session) is None
    assert held(guards.check(CHROME, typed_and_sent("Third reply."), CONFIG, session=session))


def test_a_paste_on_another_page_of_a_call_its_code_released_keeps_that_page_on_the_code(principal):
    """A send empties the box it went from; from a call on two pages, which one sent cannot be told, and a paste it
    left on the other stays."""
    elsewhere = "https://www.facebook.com/messages/e2ee/t/1000000005/"
    opened([{**CHAT, "to": "facebook.com/messages/e2ee/t/1000000005"}])
    session = page(principal.transcript, E2EE, others={8: elsewhere})
    on8 = lambda step: (step[0], {**step[1], "tabId": 8})  # noqa: E731
    call = steps(on8(key("cmd+v", "Pastes the photo")), typed("Hello."), RETURN)
    principal(guards.check(CHROME, call, CONFIG, session=session))
    assert guards.check(CHROME, call, CONFIG, session=session) is None
    reason = guards.check(CHROME, steps(*map(on8, CLEAR), on8(typed(REPLY)), on8(RETURN)), CONFIG, session=session)
    assert held(reason) and "earlier" in reason


def test_an_entry_covers_only_its_own_kind_of_send(tmp_path):
    opened([CHAT])
    assert held(guards.check(SLACK, SAID, CONFIG, session=SESSION))                  # the browser entry's words by a connector
    assert held(guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG))  # by the messages sender
    assert held(guards.check(CHROME, typed_and_sent(), CONFIG, session=page(tmp_path / "r.jsonl", PLAIN)))  # on another page
    assert guards.check(CHROME, typed_and_sent(), CONFIG, session=page(tmp_path / "r.jsonl", E2EE)) is None


# --- every other check still runs first --------------------------------------------------------------------------


def test_an_entry_that_names_a_time_still_needs_a_fresh_calendar_read(tmp_path, principal):
    config, words = {**CONFIG, "fresh_calendar": {}}, "Tuesday at 3:30 pm works for me."
    timed = {**SAID, "message": words}
    opened([{"tool": SLACK, "input": timed}, {**CHAT, "text": words}])
    session = page(principal.transcript, E2EE)
    for tool, given in ((SLACK, timed), (CHROME, typed_and_sent(words))):
        reason = guards.check(tool, given, config, session=session)
        assert held(reason) and "names a time" in reason, tool
    read_calendar(principal.transcript)
    assert guards.check(SLACK, timed, config, session=session) is None
    assert guards.check(CHROME, typed_and_sent(words), config, session=session) is None
    assert [e["how"][:6] for e in today()] == ["batch:", "batch:"]


def test_an_entry_released_by_the_code_for_its_time_is_spent_with_it(principal):
    config, timed = {**CONFIG, "fresh_calendar": {}}, {**SAID, "message": "Tuesday at 3:30 pm works for me."}
    opened([{"tool": SLACK, "input": timed}])
    session = {**SESSION, "transcript_path": str(principal.transcript)}
    principal.transcript.touch()
    principal(guards.check(SLACK, timed, config, session=session))
    assert guards.check(SLACK, timed, config, session=session) is None
    read_calendar(principal.transcript)
    assert held(guards.check(SLACK, timed, config, session=session))


def test_the_register_scan_still_refuses_a_forbidden_phrase_in_an_entry(tmp_path):
    words = "Sorry for the delay, Tuesday works."
    opened([{"tool": SLACK, "input": {**SAID, "message": words}}, {**CHAT, "text": words}])
    assert "delay-apology" in guards.check(SLACK, {**SAID, "message": words}, CONFIG, session=SESSION)
    assert "delay-apology" in guards.check(CHROME, typed_and_sent(words), CONFIG, session=page(tmp_path / "r.jsonl", E2EE))
    assert not any(e["how"].startswith("batch") for e in today())


def test_an_address_that_can_change_is_still_held():
    config, words = {**CONFIG, "temporary_addresses": {}}, "The draft is at https://quiet-river-1234.trycloudflare.com/notes"
    opened([{"tool": SLACK, "input": {**SAID, "message": words}}])
    assert "never given to anyone" in guards.check(SLACK, {**SAID, "message": words}, config, session=SESSION)


def test_a_meeting_placed_on_today_is_never_covered(monkeypatch):
    monkeypatch.setattr(guards, "_today", lambda: date(2026, 11, 9))
    config = {**CONFIG, "same_day_meetings": {"exempt": []}}
    invite = {"summary": "Follow-up", "start_time": "2026-11-09T15:00:00", "end_time": "2026-11-09T15:30:00",
              "attendees": ["a@example.com"], "user_google_email": "me@example.com"}
    later = {**invite, "start_time": "2026-11-10T15:00:00", "end_time": "2026-11-10T15:30:00"}
    opened([{"tool": EVENT, "input": invite}, {"tool": EVENT, "input": later}])
    reason = guards.check_send(EVENT, invite, config, SESSION)
    assert held(reason) and "same-day" in reason
    assert guards.check_send(EVENT, later, config, SESSION) is None


def test_the_window_and_the_batch_never_combine(tmp_path):
    signed = {**SAID, "message": "Status is green. Helperbot here"}
    sends.open_window(2, ["slack", "bitbucket"], count=1)
    data = opened([{"tool": SLACK, "input": signed}, CALL])
    assert guards.check(SLACK, signed, CONFIG, session=SESSION) is None
    assert today()[-1]["how"] == f"batch:{data['digest'][:12]}:0"
    assert "1 of 1 sends left" in sends.describe(sends.window())  # the window's planned send is untouched
    assert today()[-1]["how"].startswith("batch:") and guards.check(SLACK, signed, CONFIG, session=SESSION) is None
    assert today()[-1]["how"] == "window" and sends.window() == {}  # the second copy went on the window, as its own send
    post = f'bkt pr comment 5 -m "{REPLY}"'  # no shell post is a batch entry's, whatever its words
    assert "posts to bitbucket" in guards.check("Bash", {"command": post}, CONFIG, cwd=str(tmp_path), session=SESSION)


def test_a_session_on_another_project_or_none_cannot_spend_an_entry():
    board.touch("S-elsewhere", project="another-project")
    board.touch("S-unbound")
    opened([CALL])
    for session_id in ("S-elsewhere", "S-unbound", "S-unknown"):
        assert held(guards.check(SLACK, SAID, CONFIG, session={"session_id": session_id})), session_id
    assert guards.check(SLACK, SAID, CONFIG, session=SESSION) is None


def test_an_entry_past_twelve_hours_from_the_grant_is_held(monkeypatch):
    opened([CALL])
    later = time.time() + 12 * 3600 + 5
    monkeypatch.setattr(time, "time", lambda: later)
    assert held(guards.check(SLACK, SAID, CONFIG, session=SESSION))


@pytest.mark.parametrize("damage", ["text", "longer", "renamed", "unreadable", "spent"])
def test_tampered_or_unreadable_batch_state_falls_back_to_the_code(damage):
    data = opened([CALL])
    file = paths.state() / "sends" / "batches" / f"{data['digest']}.json"
    state = json.loads(file.read_text(encoding="utf-8"))
    if damage == "text":
        state["entries"][0]["input"]["message"] = "Edited after the grant."
    elif damage == "longer":
        state["until"] = state["granted"] + 24 * 3600
    elif damage == "spent":
        state["spent"] = {"7": {"at": 1}}
    if damage == "renamed":
        file.rename(file.with_name("0" * 64 + ".json"))
    elif damage == "unreadable":
        file.write_text("{not json", encoding="utf-8")
    else:
        file.write_text(json.dumps(state), encoding="utf-8")
    for given in (SAID, {**SAID, "message": "Edited after the grant."}):
        assert held(guards.check(SLACK, given, CONFIG, session=SESSION)), given


def test_close_ends_every_open_batch_and_status_shows_what_is_left():
    other = {**SAID, "channel_id": "D0999"}
    first = opened([CALL, {"tool": SLACK, "input": other}])
    second = opened([TEXT], name="replies-2")
    assert guards.check(SLACK, SAID, CONFIG, session=SESSION) is None
    status = _cli("sends", "status").stdout
    assert first["digest"][:12] in status and "1 of 2 entries left" in status
    assert second["digest"][:12] in status and "1 of 1 entries left" in status
    closed = _cli("sends", "close").stdout
    assert "2 batch" in closed and sends.batches() == []
    assert held(guards.check(SLACK, other, CONFIG, session=SESSION))


def test_a_batch_granted_again_keeps_what_already_went():
    other = {**SAID, "channel_id": "D0999"}
    opened([CALL, {"tool": SLACK, "input": other}])
    assert guards.check(SLACK, SAID, CONFIG, session=SESSION) is None
    sends.close_batches()
    opened([CALL, {"tool": SLACK, "input": other}])
    assert held(guards.check(SLACK, SAID, CONFIG, session=SESSION))
    assert guards.check(SLACK, other, CONFIG, session=SESSION) is None


# --- only the principal grants: the state is written by the command alone ---------------------------------------


@pytest.mark.parametrize("tool, given", [
    ("Write", {"content": "{}"}), ("Edit", {"old_string": "a", "new_string": "b"}),
    ("MultiEdit", {"edits": []}), ("write_file", {"content": "{}"}), ("edit_file", {"edits": []}),
])
def test_the_file_tools_cannot_write_the_batch_state(tmp_path, tool, given):
    state = paths.state() / "sends" / "batches" / ("a" * 64 + ".json")
    named = {"file_path": str(state)} if tool in ("Write", "Edit", "MultiEdit") else {"path": str(state)}
    reason = guards.check(tool, {**named, **given}, CONFIG, cwd=str(tmp_path))
    assert reason and "would write" in reason


def test_no_shell_line_or_script_writes_the_batch_state_or_opens_a_batch(tmp_path):
    state = paths.state() / "sends" / "batches" / ("a" * 64 + ".json")
    patch = f"*** Begin Patch\n*** Add File: {state}\n+{{}}\n*** End Patch"
    assert "would write" in guards.check("apply_patch", {"input": patch}, CONFIG, cwd=str(tmp_path))
    for line in (f"echo '{{}}' > {state}", f"cp {tmp_path / 'b.json'} {state}"):
        assert "writes into the synthesis state" in guards.check("Bash", {"command": line}, CONFIG, cwd=str(tmp_path)), line
    for script in ("python3 -c 'from synthesis import sends; sends.open_batch({\"batch\": \"b\", \"project\": \"p\", \"entries\": []})'",
                   "python3 -c 'from synthesis import sends; sends._batch_file(\"a\").write_text(\"{}\")'"):
        reason = guards.check("Bash", {"command": script}, CONFIG, cwd=str(tmp_path))
        assert reason and "send-window code" in reason, script
    look = "python3 -c 'from synthesis import sends; print(sends.batches())'"
    assert guards.check("Bash", {"command": look}, CONFIG, cwd=str(tmp_path)) is None
