"""One approval for a reviewed batch of sends (design note M37 part 4, 2026-11-14; review round 1 of 5.23.0).

A seat drafts replies in batches of about twenty; the principal reads every text and recipient in the hold and types
one code for the batch's digest. Each entry then sends once, word for word, within 12 hours, from the session that
ran the granted command, and every spend checks that session's record for the principal's code again. A connector
entry binds the whole call; a messages entry the local sender's recipient, chat, service and text; a Messenger entry
one send step: a browser_batch that loads the conversation again, types the words and runs the entry's send script,
which reads the composer and sends in the same run. Every other check runs first, and anything that differs falls
back to the code per call.
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

from synthesis import approvals, board, cli, guards, paths, sends

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "inbox-backlog"
SLACK, MAIL, EVENT = "mcp__slack__slack_send_message", "mcp__workspace-mcp__send_gmail_message", "mcp__workspace__create_event"
CHROME, KEYS, SCRIPT = ("mcp__claude-in-chrome__browser_batch", "mcp__claude-in-chrome__computer",
                        "mcp__claude-in-chrome__javascript_tool")
CONFIG = {"send_tools": ["mcp__*__slack_send_message", "mcp__*__send_gmail_message", "mcp__*__create_event"],
          "send_window_signatures": [r"Helperbot here"],
          "forbidden_phrases": [{"name": "delay-apology", "pattern": r"sorry for the delay", "why": "say what happened"}]}
REPLY = "Thanks, Tuesday works. I'll bring the notes."
SAID = {"channel_id": "D0123", "message": REPLY}
CALL = {"tool": SLACK, "input": SAID}
E2EE, PLAIN = "https://www.facebook.com/messages/e2ee/t/1000000001/", "https://www.facebook.com/messages/t/1000000002/"
CHAT = {"channel": "messenger", "to": "facebook.com/messages/e2ee/t/1000000001", "text": REPLY}
TEXT = {"channel": "messages", "to": "+15550100", "text": REPLY}
GROUP = {"channel": "messages", "members": ["+15550102", "+15550101"], "service": "SMS", "chat": "chat-9", "text": REPLY}
SESSION = {"session_id": "S-principal"}
RETURN = {"action": "key", "text": "Return", "tabId": 7, "action_summary": "Sends the reply"}


@pytest.fixture(autouse=True)
def _seat(principal, tmp_path):
    """The principal's session (the `principal` fixture's), on the batch's project, with a folder for batch files."""
    global APPROVE, FOLDER, RECORD
    APPROVE, FOLDER, RECORD = principal, tmp_path, principal.transcript
    RECORD.touch()
    board.touch("S-principal", project=PROJECT)


def today() -> list:
    return sends.ledger(time.strftime("%Y-%m-%d"))


def batch_file(entries, name="replies-1", project=PROJECT, folder=None) -> Path:
    file = (folder or FOLDER) / f"{name}.json"
    file.write_text(json.dumps({"batch": name, "project": project, "entries": entries}, ensure_ascii=False), encoding="utf-8")
    return file


def granted(entries, name="replies-1") -> dict:
    """A batch the principal opened: the guard's hold in this session's record, their code typed after it, the command
    run here."""
    file = batch_file(entries, name)
    APPROVE(held_in_record(guards.check("Bash", {"command": f"synthesis sends batch {file}"}, CONFIG, cwd=str(FOLDER))))
    assert cli.main(["--session", "S-principal", "sends", "batch", str(file)]) == 0
    return next(b for b in sends.batches() if b["batch"] == name)


def held_in_record(reason: str) -> str:
    """The guard's hold as the harness records it, the held call's result, in the session's record; the hold."""
    ident, at = f"toolu_{time.time_ns()}", datetime.now(timezone.utc).isoformat()
    _record({"type": "assistant", "timestamp": at, "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": ident, "name": "Bash", "input": {"command": "synthesis sends batch"}}]}},
            {"type": "user", "timestamp": at, "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": ident, "is_error": True, "content": reason}]}})
    return reason


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "synthesis.cli", *args], capture_output=True, text=True, cwd=ROOT,
                          stdin=subprocess.DEVNULL)


def _record(*lines) -> None:
    with RECORD.open("a", encoding="utf-8") as handle:
        handle.writelines(json.dumps(line) + "\n" for line in lines)


def read_calendar() -> None:
    at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    ident = f"toolu_{time.time_ns()}"
    _record({"type": "assistant", "timestamp": at, "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": ident, "name": "mcp__workspace__get_events", "input": {}}]}},
            {"type": "user", "timestamp": at, "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": ident, "content": "[]"}]}})


def held(reason) -> bool:
    return bool(reason) and "approve followed by the code" in reason


SENDER = ROOT / "skills" / "synthesis-local-messaging" / "scripts" / "messages_send.py"


def ran_sender() -> None:
    """A command that runs the messages sender, let through by this session's guard: the ticket its send spends on."""
    assert guards.check("Bash", {"command": f"python3 {SENDER} --to +15550100 --text-file reply.txt"}, CONFIG, cwd=str(FOLDER),
                        session={**SESSION, "transcript_path": str(RECORD)}) is None


# --- the batch file and its digest -----------------------------------------------------------------------------


def test_the_digest_binds_every_field_and_not_the_files_layout():
    batch = {"batch": "replies-1", "project": PROJECT, "entries": [CALL, CHAT, TEXT, GROUP]}
    first = sends.batch_digest(batch)
    assert first == hashlib.sha256(json.dumps(batch, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                                   .encode("utf-8")).hexdigest()
    changes = [("batch", None, "replies-2"), ("project", None, "another"), (0, "tool", "mcp__slack2__slack_send_message"),
               (0, "input", {**SAID, "channel_id": "D0124"}), (0, "input", {**SAID, "message": REPLY + " "}),
               (1, "to", "facebook.com/messages/t/1000000001"), (1, "text", REPLY[:-1]), (2, "to", "+15550109"),
               (2, "text", REPLY.replace("I'll", "I’ll")), (3, "service", "iMessage"), (3, "chat", "chat-8")]
    for where, field, value in changes:
        other = copy.deepcopy(batch)
        if field is None:
            other[where] = value
        else:
            other["entries"][where][field] = value
        assert sends.batch_digest(other) != first, (where, field)
    assert sends.batch_digest({**batch, "entries": [CHAT, CALL, TEXT, GROUP]}) != first
    laid_out = FOLDER / "laid-out.json"
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
    ({"batch": "b", "project": PROJECT, "entries": [CALL, {**CHAT, "to": "facebook.com/groups/1"}]}, "entry 2"),
    ({"batch": "b", "project": PROJECT, "entries": [{**CHAT, "channel": "instagram"}]}, "entry 1"),
    ({"batch": "b", "project": PROJECT, "entries": [{**TEXT, "to": "Pat"}]}, "entry 1"),
    ({"batch": "b", "project": PROJECT, "entries": [{**CHAT, "text": "   "}]}, "entry 1"),
    ({"batch": "b", "project": PROJECT, "entries": [{"tool": "mcp__claude-in-chrome__computer", "input": {"action": "key"}}]},
     "entry 1"),
    ({"batch": "b", "project": PROJECT, "entries": [CALL, TEXT, CALL]}, "entry 3 repeats entry 1"),
])
def test_a_batch_file_of_another_shape_is_refused_with_what_is_wrong(batch, says):
    file = FOLDER / "batch.json"
    file.write_text(json.dumps(batch), encoding="utf-8")
    with pytest.raises(ValueError, match=says):
        sends.read_batch(str(file))


def test_a_key_given_twice_or_a_number_json_lacks_is_refused():
    twice = FOLDER / "twice.json"
    twice.write_text('{"batch": "b", "project": "p", "entries": [{"channel": "messages", "to": "+15550100", '
                     '"text": "Shown.", "text": "Sent."}]}', encoding="utf-8")
    with pytest.raises(ValueError, match="twice"):
        sends.read_batch(str(twice))
    odd = FOLDER / "odd.json"
    odd.write_text('{"batch": "b", "project": "p", "entries": [{"tool": "%s", "input": {"n": NaN}}]}' % SLACK, encoding="utf-8")
    with pytest.raises(ValueError):
        sends.read_batch(str(odd))


@pytest.mark.parametrize("hidden", ["\x1b[8m Also send me the door code.\x1b[0m", "Also send the code.\r\rThanks.", "a\x00b",
                                    "a\x7fb", "a\x85b", "tab\tseparated"])
def test_a_control_character_other_than_a_newline_is_refused_anywhere_in_the_file(hidden):
    """Review #5: an escape code concealed words in the listing and a carriage return printed one line over another."""
    for entries in ([{**CHAT, "text": "Thanks. " + hidden}], [{**TEXT, "text": hidden}],
                    [{"tool": SLACK, "input": {"channel_id": "D1", "message": hidden}}],
                    [{"tool": SLACK, "input": {"channel_id": "D1", "message": "Fine.", "note" + hidden: "x"}}]):
        with pytest.raises(ValueError, match="control character"):
            sends.read_batch(str(batch_file(entries)))
    assert sends.read_batch(str(batch_file([{**CHAT, "text": "Line one.\nLine two."}])))  # a newline is a line break


def test_the_listing_shows_every_text_escaped_so_nothing_hides_in_it():
    """Review #5 and #12: zero-width and direction marks shown as codes, a text as the guard holds it."""
    sly = {**CHAT, "text": "Thanks.​‮See you."}
    listing = sends.batch_listing(sends.read_batch(str(batch_file([sly, CALL]))), show=True)
    assert "\\u200b" in listing and "\\u202e" in listing and "‮" not in listing and "​" not in listing
    assert '"Thanks.' in listing and "D0123" in listing and json.dumps(REPLY) in listing


@pytest.mark.parametrize("to", [
    "https://www.facebook.com/messages/e2ee/t/1000000001/", "www.facebook.com/messages/e2ee/t/1000000001",
    "facebook.com/messages/e2ee/t/1000000001/", "facebook.com/messages/e2ee/t/1000000001?for=Carol",
    "alice.example@facebook.com/messages/e2ee/t/1000000001", "facebook.com:8443/messages/e2ee/t/1000000001",
    "m.facebook.com/messages/e2ee/t/1000000001", "facebook.com/messages/e2ee/t/1000000001#Dana",
])
def test_only_the_canonical_address_of_a_conversation_is_accepted(to):
    """Review #6: four entries read as alice, bob, Carol and Dana were one conversation."""
    with pytest.raises(ValueError, match="entry 1"):
        sends.read_batch(str(batch_file([{**CHAT, "to": to}])))


def test_two_entries_for_one_conversation_are_refused():
    for entries in ([CHAT, {**CHAT, "text": "And one more thing."}], [TEXT, {**TEXT, "text": "Also this."}],
                    [GROUP, {**GROUP, "text": "Also this."}]):
        with pytest.raises(ValueError, match="entry 2 .*conversation"):
            sends.read_batch(str(batch_file(entries)))


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
    ("https://www.facebook.com/messages/t/١٢٣", None),
])
def test_a_page_address_is_read_as_its_site_and_path(address, place):
    """The coordinator, 2026-11-14: an encrypted chat's address and a plain one's are two conversations, and so are the
    two sites'; a page's slash and query are left off (a batch file names only the canonical form)."""
    assert sends.conversation(address) == place


# --- asking: `synthesis sends batch <file>` ----------------------------------------------------------------------


def test_only_the_principals_code_for_that_digest_opens_a_batch_and_the_hold_shows_every_entry():
    """Review #12: the hold itself carries every recipient and text, escaped, which the code is typed against."""
    file = batch_file([CALL, CHAT])
    digest = sends.batch_digest(sends.read_batch(str(file)))
    command = f"synthesis sends batch {file}"
    reason = guards.check("Bash", {"command": command}, CONFIG, cwd=str(FOLDER))
    assert held(reason) and digest in reason and "2 sends" in reason and str(file) in reason
    assert "D0123" in reason and json.dumps(REPLY) in reason and "facebook.com/messages/e2ee/t/1000000001" in reason
    for free in (f"synthesis sends batch {file} --show", "synthesis sends batch --help", "synthesis sends status",
                 "synthesis sends close", "synthesis sends log", "synthesis sends composer-check"):
        assert guards.check("Bash", {"command": free}, CONFIG, cwd=str(FOLDER)) is None, free
    for spelled in (f"python3 -m synthesis.cli sends batch {file}", f"synthesis --session S-principal sends batch {file}",
                    f"cd {FOLDER} && synthesis sends batch {file.name}"):
        assert held(guards.check("Bash", {"command": spelled}, CONFIG, cwd=str(ROOT))), spelled
    shown = _cli("sends", "batch", str(file), "--show")
    assert shown.returncode == 0 and json.dumps(REPLY) in shown.stdout and digest in shown.stdout and sends.batches() == []
    listed = _cli("--session", "S-principal", "sends", "batch", str(file))
    assert listed.returncode == 2 and "type approve" in listed.stderr and sends.batches() == []
    APPROVE(reason)
    assert guards.check("Bash", {"command": command}, CONFIG, cwd=str(FOLDER)) is None
    done = _cli("--session", "S-principal", "sends", "batch", str(file))
    assert done.returncode == 0 and digest[:12] in done.stdout and "2 of 2 entries left" in done.stdout
    assert [b["digest"] for b in sends.batches()] == [digest]
    assert _cli("--session", "S-principal", "sends", "batch", str(file)).returncode == 2  # the grant was spent


def test_no_terminal_opens_a_batch_without_the_code(monkeypatch, capsys):
    """Review #7: the own-terminal shortcut opened a batch when `env -i` and `script` made a terminal."""
    file = batch_file([CALL])
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    assert cli.main(["--session", "S-principal", "sends", "batch", str(file)]) == 2 and sends.batches() == []
    assert "type approve" in capsys.readouterr().err


def test_a_file_changed_after_the_hold_does_not_get_the_grant():
    file = batch_file([CALL])
    APPROVE(guards.check("Bash", {"command": f"synthesis sends batch {file}"}, CONFIG, cwd=str(FOLDER)))
    batch_file([{"tool": SLACK, "input": {**SAID, "message": REPLY + " Bring the keys too."}}])
    assert held(guards.check("Bash", {"command": f"synthesis sends batch {file}"}, CONFIG, cwd=str(FOLDER)))
    assert _cli("--session", "S-principal", "sends", "batch", str(file)).returncode == 2 and sends.batches() == []


def test_a_batch_the_command_would_refuse_is_never_put_to_the_principal():
    reason = guards.check("Bash", {"command": f"synthesis sends batch {FOLDER / 'absent.json'}"}, CONFIG, cwd=str(FOLDER))
    assert reason and "can't open" in reason and not held(reason)
    bad = batch_file([], name="empty")
    assert "1 to 50" in guards.check("Bash", {"command": f"synthesis sends batch {bad}"}, CONFIG, cwd=str(FOLDER))


def test_every_sends_command_in_a_line_is_judged():
    """Review #7: only the first `sends batch` of a line was judged, and so was only the first `sends open`."""
    first, second = batch_file([CALL], name="approved"), batch_file([TEXT], name="never-shown")
    APPROVE(guards.check("Bash", {"command": f"synthesis sends batch {first}"}, CONFIG, cwd=str(FOLDER)))
    line = f"synthesis sends batch {first} ; env -i PATH=/usr/bin script -q /dev/null synthesis sends batch {second}"
    reason = guards.check("Bash", {"command": line}, CONFIG, cwd=str(FOLDER))
    assert held(reason) and sends.batch_digest(sends.read_batch(str(second)))[:12] in reason
    window = "synthesis sends open --hours 2 --sends 3 --channels jira"
    APPROVE(guards.check("Bash", {"command": window}, CONFIG, cwd=str(FOLDER)))
    later = f"{window} && synthesis sends open --hours 12 --sends 50 --channels all"
    assert held(guards.check("Bash", {"command": later}, CONFIG, cwd=str(FOLDER)))
    waits = f"synthesis wait --for 1 -- synthesis sends batch {second}"  # a CLI word anywhere in the words
    assert held(guards.check("Bash", {"command": waits}, CONFIG, cwd=str(FOLDER)))


@pytest.mark.parametrize("tail, name", [(["--proj", "approved.json", "never-shown.json"], "never-shown.json"),
                                        (["--", "--show"], "--show"), (["--", "-h"], "-h")])
def test_the_guard_reads_a_sends_command_as_the_cli_does(tail, name):
    """Review #8: the guard checked A and the CLI opened B; `-- --show` and `-- -h` were read as options by the guard
    and as files by the CLI."""
    batch_file([CALL], name="approved")
    (FOLDER / name).write_text(json.dumps({"batch": "x", "project": PROJECT, "entries": [TEXT]}), encoding="utf-8")
    APPROVE(guards.check("Bash", {"command": f"synthesis sends batch {FOLDER / 'approved.json'}"}, CONFIG, cwd=str(FOLDER)))
    import shlex
    reason = guards.check("Bash", {"command": shlex.join(["synthesis", "sends", "batch", *tail])}, CONFIG, cwd=str(FOLDER))
    assert held(reason) and sends.batch_digest(sends.read_batch(str(FOLDER / name)))[:12] in reason


def test_a_sends_command_the_guard_cannot_read_as_the_cli_would_waits_for_a_code():
    for line in ("synthesis sends batch $BATCH_FILE", "synthesis sends batch `ls *.json`", "synthesis sends batch --bogus x"):
        reason = guards.check("Bash", {"command": line}, CONFIG, cwd=str(FOLDER))
        assert held(reason) and "as the CLI reads it" in reason, line


def test_a_file_goes_only_with_sends_batch():
    """Review #14: `sends open ... -- -h` opened a window, since the new file positional took `-h`."""
    line = "synthesis sends --hours 12 --sends 50 --channels slack open -- -h"
    reason = guards.check("Bash", {"command": line}, CONFIG, cwd=str(FOLDER))
    assert reason and "only with" in reason
    done = _cli("--session", "S-principal", "sends", "--hours", "12", "--sends", "50", "--channels", "slack", "open", "--", "-h")
    assert done.returncode == 2 and "only with" in done.stderr and sends.window() == {}


def test_editing_the_file_after_the_grant_changes_nothing():
    granted([CALL])
    edited = {**SAID, "message": "Something else entirely."}
    batch_file([{"tool": SLACK, "input": edited}])
    assert held(guards.check(SLACK, edited, CONFIG, session=SESSION))
    assert guards.check(SLACK, SAID, CONFIG, session=SESSION) is None


def test_a_post_beside_an_approved_window_or_batch_command_is_still_judged():
    window = "synthesis sends open --hours 2 --sends 3 --channels jira"
    APPROVE(guards.check("Bash", {"command": window}, CONFIG, cwd=str(FOLDER)))
    file = batch_file([CALL])
    APPROVE(guards.check("Bash", {"command": f"synthesis sends batch {file}"}, CONFIG, cwd=str(FOLDER)))
    for command in (window, f"synthesis sends batch {file}"):
        assert guards.check("Bash", {"command": command}, CONFIG, cwd=str(FOLDER)) is None
        reason = guards.check("Bash", {"command": f'{command} && bkt pr comment 5 -m "Approved from my side."'},
                              CONFIG, cwd=str(FOLDER))
        assert held(reason) and "posts to bitbucket" in reason, command


# --- what an entry covers, and who may spend it ------------------------------------------------------------------


def test_each_entry_sends_once_and_the_ledger_names_the_batch_and_the_entry():
    other = {**SAID, "channel_id": "D0999"}
    data = granted([{"tool": SLACK, "input": other}, CALL])
    assert guards.check(SLACK, SAID, CONFIG, session=SESSION) is None
    assert held(guards.check(SLACK, SAID, CONFIG, session=SESSION))
    entry = today()[-1]
    assert entry["how"] == f"batch:{data['digest'][:12]}:1" and entry["channel"] == "slack"
    assert f"batch:{data['digest'][:12]}:1" in _cli("sends", "log").stdout
    assert guards.check(SLACK, other, CONFIG, session=SESSION) is None


def test_racing_calls_for_one_entry_send_it_once():
    granted([CALL])
    results, start = [], threading.Barrier(6)

    def race():
        start.wait()
        results.append(guards.check_send(SLACK, SAID, CONFIG, SESSION))
    racers = [threading.Thread(target=race) for _ in range(6)]
    for racer in racers:
        racer.start()
    for racer in racers:
        racer.join()
    assert sum(r is None for r in results) == 1 and all(held(r) for r in results if r is not None)


def test_only_the_session_that_ran_the_granted_command_spends_its_entries():
    """Review #10: `synthesis use` needs no code, so a project was no bound; the grant's own session is."""
    granted([CALL])
    for other in ("S-other", "S-unknown"):
        board.touch(other, project=PROJECT)
        assert held(guards.check(SLACK, SAID, CONFIG, session={"session_id": other})), other
    assert guards.check(SLACK, SAID, CONFIG, session=SESSION) is None


def test_batch_state_alone_is_never_a_grant():
    """Review #17: state an agent wrote for itself opened and sent. Each spend checks the granting session's record for
    the principal's code again, as a per-call approval does."""
    batch = sends.read_batch(str(batch_file([CALL])))
    sends.open_batch(batch, {"code": "7abcde", "asked": time.time() - 60}, "S-principal")  # a code nobody typed
    assert held(guards.check(SLACK, SAID, CONFIG, session=SESSION))
    other = RECORD.parent / "S-other.jsonl"
    other.write_text(json.dumps({"type": "user", "timestamp": datetime.now(timezone.utc).isoformat(), "origin": {"kind": "human"},
                                 "message": {"role": "user", "content": "approve 7abcde"}}) + "\n", encoding="utf-8")
    assert held(guards.check(SLACK, SAID, CONFIG, session=SESSION))  # typed, but in another session's record
    sends.close_batches()
    data = granted([CALL])
    assert data["session"] == "S-principal" and data["code"] and guards.check(SLACK, SAID, CONFIG, session=SESSION) is None


@pytest.mark.parametrize("tool, given", [
    (SLACK, {**SAID, "channel_id": "D0124"}), (SLACK, {**SAID, "message": REPLY + " "}),
    (SLACK, {**SAID, "message": REPLY.replace("o", "о", 1)}), (SLACK, {**SAID, "message": REPLY[:-1] + "!"}),
    (SLACK, {**SAID, "thread_ts": "1731600000.000100"}), (SLACK, {**SAID, "channel_id": "d0123"}),
    ("mcp__slack2__slack_send_message", SAID),
])
def test_any_difference_from_an_entry_is_held(tool, given):
    granted([CALL])
    assert held(guards.check(tool, given, CONFIG, session=SESSION))
    assert guards.check(SLACK, SAID, CONFIG, session=SESSION) is None


def test_line_endings_are_the_one_difference_overlooked():
    paragraphs = "Thanks for the notes.\n\nTuesday works."
    granted([{"tool": SLACK, "input": {**SAID, "message": paragraphs}}])
    assert guards.check(SLACK, {**SAID, "message": paragraphs.replace("\n", "\r\n")}, CONFIG, session=SESSION) is None
    entry = {"tool": SLACK, "input": {**SAID, "message": paragraphs}}
    assert sends.call_entry(entry, SLACK, {**SAID, "message": paragraphs.replace("\n", "\r")})
    assert not sends.call_entry({"tool": SLACK, "input": {**SAID, "flag": 1}}, SLACK, {**SAID, "flag": True})


def test_a_messages_entry_binds_the_senders_recipient_chat_service_and_text():
    """Review #13: messages_send.py asks the guard itself: `--to` as imessage_send {to, text}; `--members` as
    messages_send {to: the sorted members, service, text, chat}, which an entry names in full, one member included."""
    granted([TEXT, GROUP, {"channel": "messages", "members": ["+15550103"], "service": "iMessage", "chat": "chat-7",
                           "text": "On my way."}])
    members = {"to": ["+15550101", "+15550102"], "service": "SMS", "text": REPLY, "chat": "chat-9"}
    for tool, given in (("imessage_send", {"to": "+15550199", "text": REPLY}),
                        ("imessage_send", {"to": "+15550100", "text": REPLY, "photo": {"name": "a.jpg", "bytes": 9, "sha256": "0" * 64}}),
                        ("messages_send", {**members, "service": "iMessage"}), ("messages_send", {**members, "chat": "chat-2"}),
                        ("messages_send", {"to": ["+15550100"], "service": "iMessage", "text": REPLY, "chat": "chat-1"})):
        ran_sender()
        assert held(guards.check_send(tool, given, CONFIG)), (tool, given)
    ran_sender()
    assert guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG) is None
    ran_sender()
    assert guards.check_send("messages_send", members, CONFIG) is None
    one = {"to": ["+15550103"], "service": "iMessage", "text": "On my way.", "chat": "chat-7"}
    ran_sender()
    assert guards.check_send("messages_send", one, CONFIG) is None
    with pytest.raises(ValueError, match="entry 1"):
        sends.read_batch(str(batch_file([{**GROUP, "members": ["+15550100", "+15550100"]}])))


@pytest.mark.parametrize("attachment", [{"path": "plan.pdf"}, {"url": "https://files.example.com/shared/plan.pdf", "filename": "plan.pdf"}])
def test_a_call_the_connector_fetches_or_reads_a_file_for_is_never_covered(attachment):
    """Review #16: a file fetched from a url when the call runs, up to 12 hours after the principal read the batch."""
    mail = {"to": "pat@example.com", "subject": "Plan", "body": "<p>The plan is attached.</p>", "body_format": "html",
            "attachments": [attachment]}
    granted([{"tool": MAIL, "input": mail}])
    assert guards.check_send(MAIL, mail, CONFIG, SESSION)  # its own code, or refused outright as no full path
    assert not any(e["how"].startswith("batch") for e in today())


# --- the browser: one step reloads the conversation, types the words, and its send script checks and sends ---------
# The third round of 5.24.0's review (#1, #2, #3, #6): a check read in one call and a Return pressed in another left
# room for a page script, a typist or another session between them. Now the read and the send are one synchronous run
# of one shipped page script, the last step of a browser_batch that first loads the conversation again on its tab.


def listed(url=E2EE, tab=7, record=None) -> dict:
    """A browser call whose result lists a tab on a page, in a session's record (this one's unless named); the session."""
    ident, at = f"toolu_{time.time_ns()}", datetime.now(timezone.utc).isoformat()
    tabs = f"\n\nTab Context:\n- Executed on tabId: {tab}\n- Available tabs:\n  • tabId {tab}: \"Messenger\" (\"{url}\")"
    with (record or RECORD).open("a", encoding="utf-8") as handle:
        for line in ({"type": "assistant", "timestamp": at, "message": {"role": "assistant", "content": [
                         {"type": "tool_use", "id": ident, "name": KEYS, "input": {"action": "screenshot", "tabId": tab}}]}},
                     {"type": "user", "timestamp": at, "message": {"role": "user", "content": [
                         {"type": "tool_result", "tool_use_id": ident, "content": [{"type": "text", "text": "Done" + tabs}]}]}}):
            handle.write(json.dumps(line) + "\n")
    return {**SESSION, "transcript_path": str(record or RECORD)}


def ran(name, given, record=None, said="Done") -> None:
    """A finished call and its result in a session's record (this one's unless named)."""
    ident, at = f"toolu_{time.time_ns()}", datetime.now(timezone.utc).isoformat()
    with (record or RECORD).open("a", encoding="utf-8") as handle:
        for line in ({"type": "assistant", "timestamp": at, "message": {"role": "assistant", "content": [
                         {"type": "tool_use", "id": ident, "name": name, "input": given}]}},
                     {"type": "user", "timestamp": at, "message": {"role": "user", "content": [
                         {"type": "tool_result", "tool_use_id": ident, "content": [{"type": "text", "text": said}]}]}}):
            handle.write(json.dumps(line) + "\n")


def made(tab=7, record=None) -> None:
    """The browser's own tabs_create in a session's record, its result as the extension writes it."""
    ran("mcp__claude-in-chrome__tabs_create_mcp", {}, record, f"Created new tab. Tab ID: {tab}\n\nTab Context:\n- Executed on "
        f"tabId: {tab}\n- Available tabs:\n  • tabId {tab}: \"New Tab\" (\"chrome://newtab/\")")


def opened(url=E2EE, tab=7) -> dict:
    """A tab this session made with tabs_create and navigated to a page; the session."""
    made(tab)
    return listed(url, tab)


def step(entry=CHAT, tab=7, url=None, words=None, script=None, middle=None, after=()) -> dict:
    """A batch's Messenger send as one browser_batch: load the conversation's address on the tab again, type the words,
    run the entry's send script there, last."""
    go = {"name": "navigate", "input": {"url": url or f"https://www.{entry['to']}/", "tabId": tab}}
    typing = middle if middle is not None else [
        {"name": "computer", "input": {"action": "type", "text": entry["text"] if words is None else words, "tabId": tab}}]
    run = {"name": "javascript_tool", "input": {"action": "javascript_exec", "text": script or sends.send_script(entry), "tabId": tab}}
    return {"actions": [go, *typing, run, *after]}


def sent(given, config=CONFIG, tool=CHROME):
    return guards.check(tool, given, config, session={**SESSION, "transcript_path": str(RECORD)})


def test_the_cli_prints_the_composer_check_and_the_send_script_and_the_guard_lets_them_run():
    assert _cli("sends", "composer-check").stdout.strip() == sends.COMPOSER_CHECK
    assert guards.check(SCRIPT, {"action": "javascript_exec", "text": sends.COMPOSER_CHECK, "tabId": 7}, CONFIG,
                        session=listed()) is None
    data = granted([CALL, CHAT])
    shown = cli_out("sends", "script", "--entry", f"{data['digest'][:12]}:2")
    assert shown == sends.send_script(CHAT) and sends.SEND_MARK in shown
    assert guards.check("Bash", {"command": f"synthesis sends script --entry {data['digest'][:12]}:2"}, CONFIG, cwd=str(FOLDER)) is None
    for wrong in (f"{data['digest'][:12]}:1", f"{data['digest'][:12]}:3", "0000:2"):  # a connector entry, none, no batch
        assert cli_main("sends", "script", "--entry", wrong) == 2


def cli_out(*args) -> str:
    import contextlib
    import io
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert cli.main(["--session", "S-principal", *args]) == 0
    return out.getvalue().strip()


def cli_main(*args) -> int:
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return cli.main(["--session", "S-principal", *args])


@pytest.mark.parametrize("entry_to, url, goes", [
    ("facebook.com/messages/e2ee/t/1000000001", E2EE, True),
    ("facebook.com/messages/e2ee/t/1000000001", "https://www.facebook.com/messages/e2ee/t/1000000001?locale=en_US", True),
    ("facebook.com/messages/t/1000000002", PLAIN, True),
    ("messenger.com/t/1000000003", "https://www.messenger.com/t/1000000003/", True),
    ("messenger.com/e2ee/t/1000000004", "https://www.messenger.com/e2ee/t/1000000004", True),
    ("facebook.com/messages/e2ee/t/1000000001", "https://www.facebook.com/messages/t/1000000001/", False),
    ("facebook.com/messages/t/1000000002", "https://www.facebook.com/messages/e2ee/t/1000000002/", False),
    ("messenger.com/t/1000000003", "https://www.messenger.com/e2ee/t/1000000003/", False),
    ("messenger.com/e2ee/t/1000000004", "https://www.messenger.com/t/1000000004/", False),
    ("facebook.com/messages/e2ee/t/1000000001", "https://www.messenger.com/e2ee/t/1000000001/", False),
    ("facebook.com/messages/e2ee/t/1000000001", "https://www.facebook.com/messages/e2ee/t/1000000009/", False),
    ("facebook.com/messages/e2ee/t/1000000001", "https://facebook.com.example.org/messages/e2ee/t/1000000001/", False),
    ("facebook.com/messages/e2ee/t/1000000001", "https://www.facebook.com/messages/", False),
])
def test_a_messenger_entry_goes_as_one_send_step_on_a_tab_already_on_its_conversation(entry_to, url, goes):
    """The tab must already show the conversation in this session's newest list of tabs, so the load the step makes
    changes no address any session's guard reads (a page script there is refused, below)."""
    entry = {**CHAT, "to": entry_to}
    granted([entry])
    opened(url)
    reason = sent(step(entry))
    assert (reason is None) is goes, reason


def test_a_send_step_goes_once_and_its_ledger_line_names_the_entry():
    data = granted([CHAT])
    opened()
    assert sent(step()) is None
    assert today()[-1]["how"] == f"batch:{data['digest'][:12]}:0"
    assert sent(step())  # spent


TYPE = {"action": "type", "text": REPLY, "tabId": 7}


def _shapes() -> dict:
    return {
    "no-load-first": {"actions": step()["actions"][1:]},
    "a-load-naming-no-tab": {"actions": [{"name": "navigate", "input": {"url": E2EE}}, *step()["actions"][1:]]},
    "a-load-with-a-fragment": step(url=E2EE + "#"),
    "a-load-with-a-query": step(url=E2EE + "?ref=1"),
    "a-load-by-http": step(url="http://www.facebook.com/messages/e2ee/t/1000000001/"),
    "a-load-of-another-conversation": step(url=PLAIN),
    "a-script-to-a-page": step(url="javascript:void(0)"),
    "the-script-not-last": step(after=[{"name": "computer", "input": {"action": "screenshot", "tabId": 7}}]),
    "the-script-on-another-tab": {"actions": [*step()["actions"][:-1], {"name": "javascript_tool", "input": {
        "action": "javascript_exec", "text": sends.send_script(CHAT), "tabId": 8}}]},
    "typing-on-another-tab": step(middle=[{"name": "computer", "input": {**TYPE, "tabId": 8}}]),
    "a-click-between": step(middle=[{"name": "computer", "input": TYPE}, {"name": "computer", "input": {
        "action": "left_click", "ref": "ref_5", "tabId": 7, "action_summary": "Clicks the box"}}]),
    "a-return-between": step(middle=[{"name": "computer", "input": TYPE}, {"name": "computer", "input": {
        "action": "key", "text": "Return", "tabId": 7}}]),
    "a-line-break-typed": step(middle=[{"name": "computer", "input": {**TYPE, "text": REPLY + "\n"}}]),
    "a-form-value-set": step(middle=[{"name": "form_input", "input": {"ref": "ref_5", "value": REPLY, "tabId": 7}}]),
    "the-script-changed": step(script=sends.send_script(CHAT).replace("innerText", "textContent")),
    "the-script-of-other-words": step(script=sends.send_script({**CHAT, "text": REPLY + " P.S. Wire the deposit."})),
    "two-scripts": {"actions": [*step()["actions"], step()["actions"][-1]]},
    }


@pytest.mark.parametrize("shape", [
    "no-load-first", "a-load-naming-no-tab", "a-load-with-a-fragment", "a-load-with-a-query", "a-load-by-http",
    "a-load-of-another-conversation", "a-script-to-a-page", "the-script-not-last", "the-script-on-another-tab",
    "typing-on-another-tab", "a-click-between", "a-return-between", "a-line-break-typed", "a-form-value-set",
    "the-script-changed", "the-script-of-other-words", "two-scripts"])
def test_a_send_step_of_any_other_shape_is_refused_and_spends_nothing(shape):
    granted([CHAT])
    opened()
    assert sent(_shapes()[shape]), shape
    assert not any(e["how"].startswith("batch") for e in today())
    assert sent(step()) is None  # the entry is still there


def test_a_send_step_on_a_tab_not_yet_on_its_conversation_is_refused():
    granted([CHAT])
    opened("https://example.com/")
    assert sent(step())
    listed()
    assert sent(step()) is None


def test_the_send_script_runs_only_as_the_last_step_of_its_send():
    granted([CHAT])
    session = opened()
    assert "last step" in guards.check(SCRIPT, {"action": "javascript_exec", "text": sends.send_script(CHAT), "tabId": 7},
                                       CONFIG, session=session)
    assert sent(step()) is None


# --- the coordinator's ruling on the opener (2026-11-15): the send step runs only on a tab this session made --------
# No page holds a handle to a tab the browser tool made and only this session navigated: a page gets a handle to
# another window only by opening it. The guard reads which tabs this session made from its own tabs_create results.


def test_the_send_step_runs_only_on_a_tab_this_session_made_with_tabs_create():
    granted([CHAT, {**CHAT, "to": "facebook.com/messages/t/1000000002"}])
    listed()  # on the conversation, but made by no tabs_create of this session
    reason = sent(step())
    assert reason and "tabs_create" in reason
    made(tab=8)  # another tab made here makes tab 7 none (its list here names tab 8 alone, so tab 7 is listed again)
    listed()
    assert "tabs_create" in sent(step())
    opened(tab=9)
    assert sent(step(tab=9)) is None
    listed(PLAIN, tab=9)  # the same tab, navigated by this session to the next conversation, carries the next send
    assert sent(step({**CHAT, "to": "facebook.com/messages/t/1000000002"}, tab=9)) is None


def _other_record():
    other = RECORD.parent / "S-other.jsonl"
    other.touch()
    paths.write_json(paths.state() / "transcripts" / "S-other.json", {"path": str(other)})
    return other


@pytest.mark.parametrize("what", ["navigate", "script", "click", "a-batch-step", "a-navigate-naming-no-tab"])
def test_another_sessions_call_on_the_tab_since_this_session_made_it_voids_it(what):
    granted([CHAT])
    other = _other_record()
    ran("mcp__claude-in-chrome__navigate", {"url": "https://example.com/", "tabId": 7}, other)  # before it was made: no matter
    opened()
    name, given = {"navigate": ("mcp__claude-in-chrome__navigate", {"url": E2EE, "tabId": 7}),
                   "script": (SCRIPT, {"action": "javascript_exec", "text": "document.title", "tabId": 7}),
                   "click": (KEYS, {"action": "left_click", "ref": "ref_1", "tabId": 7, "action_summary": "Clicks"}),
                   "a-batch-step": (CHROME, {"actions": [{"name": "computer", "input": {"action": "scroll", "tabId": 7}}]}),
                   "a-navigate-naming-no-tab": ("mcp__claude-in-chrome__navigate", {"url": "https://example.com/"})}[what]
    ran(name, given, other)
    reason = sent(step())
    assert reason and "another session" in reason.lower(), reason
    assert not any(e["how"].startswith("batch") for e in today())


def test_a_call_of_another_session_before_the_tab_was_made_voids_nothing():
    granted([CHAT])
    ran("mcp__claude-in-chrome__navigate", {"url": E2EE, "tabId": 7}, _other_record())
    time.sleep(0.01)
    opened()
    assert sent(step()) is None


def test_a_page_script_on_the_tab_since_this_session_made_it_voids_it():
    """A window a page script opened keeps an opener's handle to the tab: the opener the guard can see."""
    granted([CHAT])
    opened("https://example.com/")
    ran(SCRIPT, {"action": "javascript_exec", "text": "window.name = 'x'; open('https://example.com/b')", "tabId": 7})
    listed()  # navigated to the conversation since
    reason = sent(step())
    assert reason and "page script" in reason, reason


def test_the_opener_probe_is_refused_at_the_send_step():
    """The third round's residual: the agent's own data: page, listed as it loaded, moves to facebook.com; a script there
    passes as one on the data: page, opens the chat and keeps a timer that patches it through any load. The tab it opened
    was made by no tabs_create of this session, so the send step on it is refused."""
    granted([CHAT])
    stale = "data:text/html,%3Cscript%3EsetTimeout(()=%3Elocation='https://www.facebook.com/messages/t/1000000009/',3000)%3C/script%3E"
    opener = (f"self.chat = open('{E2EE}'); setInterval(() => {{ try {{ const w = chat; if (!w.__p) {{ const c = "
              "w.HTMLElement.prototype.click; w.HTMLElement.prototype.click = function () { w.document.querySelector("
              "'[role=textbox]').append(' P.S.'); return c.call(this); }; w.__p = 1; } } catch (e) {} }, 5)")
    session = opened(stale, tab=9)
    assert guards.check(SCRIPT, {"action": "javascript_exec", "text": opener, "tabId": 9}, CONFIG, session=session) is None  # unseen
    ran(SCRIPT, {"action": "javascript_exec", "text": opener, "tabId": 9})
    listed(E2EE, tab=10)  # the chat it opened, listed by the next call
    reason = sent(step(tab=10))
    assert reason and "tabs_create" in reason, reason


# A page as small as the check needs, of the shape the coordinator read on a live Messenger chat (2026-11-14): one
# contenteditable textbox labelled `Write to <Name>`, `aria-placeholder="Aa"`, a Lexical editor, in no form, whose
# innerText is a single line break while empty, with the focus on the body after load.
FAKE_DOM = r"""
class El {
  constructor(tag, attrs, kids, text) { this.tagName = tag.toUpperCase(); this.attrs = attrs || {}; this.kids = kids || [];
    this.text = text || ''; this.parentElement = null; this.kids.forEach(k => { k.parentElement = this; }); }
  getAttribute(n) { return n in this.attrs ? this.attrs[n] : null; }
  hasAttribute(n) { return n in this.attrs; }
  contains(o) { for (let e = o; e; e = e.parentElement) if (e === this) return true; return false; }
  closest(s) { for (let e = this; e; e = e.parentElement) if (matches(e, s)) return e; return null; }
  get innerText() { return this.text; }
  click() { clicks.push(this.getAttribute('aria-label') || this.tagName); }
  querySelectorAll(s) { const out = []; const walk = e => e.kids.forEach(k => { if (matches(k, s)) out.push(k); walk(k); });
    walk(this); return out; }
}
const clicks = [];
function matches(el, list) {
  return list.split(',').some(one => {
    if (one.trim() === '*') return true;
    const m = one.trim().match(/^([a-z0-9]*)((?:\[[^\]]+\])*)$/i);
    if (!m) throw new Error('a selector this page cannot read: ' + one);
    if (m[1] && el.tagName !== m[1].toUpperCase()) return false;
    return [...m[2].matchAll(/\[([\w-]+)(?:(\*?=)"([^"]*)"(\s+i)?)?\]/g)].every(([, name, op, value, ci]) => {
      const have = el.getAttribute(name);
      if (have === null) return false;
      const [a, b] = ci ? [have.toLowerCase(), value.toLowerCase()] : [have, value];
      return !op || (op === '=' ? a === b : a.includes(b));
    });
  });
}
const el = (tag, attrs, kids, text) => new El(tag, attrs, kids, text);
const LIVE = {contenteditable: 'true', role: 'textbox', 'aria-label': 'Write to Pat Example', 'aria-placeholder': 'Aa',
              'data-lexical-editor': 'true'};
"""


def _on_page(page: str, script: str) -> str:
    import shutil
    if not shutil.which("node"):
        pytest.skip("node runs the composer's scripts against a page here; this machine has none")
    program = (FAKE_DOM + page + "\nconst document = {querySelectorAll: s => body.querySelectorAll(s), activeElement: focus};"
               "\nconst location = new URL(href);\nconst report = " + script + ";\nconsole.log(JSON.stringify({report, clicks}));")
    done = subprocess.run(["node", "-"], input=program, capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return done.stdout


def _composer_on(page: str) -> dict:
    """The shipped check's report on a page built by `page` (JavaScript that sets `body`, `focus` and `href`)."""
    return json.loads(json.loads(_on_page(page, sends.COMPOSER_CHECK))["report"])


def _send_on(page: str, entry=CHAT) -> tuple:
    """(the entry's send script's report, the controls it clicked) on a page built by `page`."""
    done = json.loads(_on_page(page, sends.send_script(entry)))
    return json.loads(done["report"]), done["clicks"]


# The live shapes (the coordinator's reads of 2026-11-14 and -15): in plain mode the composer is its parent's only
# child; the message log, its photos and its headings lie outside that parent.
LIVE_ROW = ("const box = el('div', LIVE, [], {text});"
            "const row = el('div', {{}}, [el('div', {{}}, [box]), el('div', {{role: 'button', 'aria-label': 'Press enter to send'}})"
            "{more}]);"
            "const body = el('body', {{}}, [el('div', {{role: 'main'}}, [el('div', {{role: 'grid'}}, [el('img', {{src: "
            "'photo-in-the-thread.jpg'}}), el('h4', {{}}, [], 'Pat Example')]), el('div', {{}}, [row])])]);"
            "const focus = {focus}; const href = 'https://www.facebook.com/messages/e2ee/t/1000000001/';")
HIDDEN_COMPOSE = ("el('h3', {style: 'position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0)'}, "
                  "[], 'Compose')")
LIVE_BANNER = ("el('div', {}, [el('div', {role: 'heading'}, [], 'Replying to Pat'), "
               "el('div', {}, [], 'Can you wire it today?'), el('div', {role: 'button', 'aria-label': 'Cancel reply'})])")
# A composer ready to send: the words typed, its icons drawn as svg inside their controls, `Send a like` turned into
# `Press enter to send` (round 1's live read), the hidden `Compose` heading inside it, the log outside its parent.
READY = ("const box = el('div', LIVE, [], TEXT);"
         "const icon = l => el('div', {role: 'button', 'aria-label': l}, [el('svg', {})]);"
         "const composer = el('div', {}, [" + HIDDEN_COMPOSE + ", INSIDE...['Send a voice clip', 'Attach a file up to 100 MB', "
         "'Choose a sticker', 'Choose a GIF'].map(icon), el('div', {}, [box]), icon('Choose an emoji'), icon('Press enter to send')]);"
         "const body = el('body', {}, [el('div', {role: 'main'}, [el('div', {role: 'grid'}, [el('img', {src: 'photo-in-the-thread.jpg'}), "
         "el('h4', {}, [], 'Pat Example')]), el('div', {}, BESIDE)])]);"
         "const focus = box; const href = HREF;")


def ready(text=REPLY + "\n", inside="", beside="[composer]", href=E2EE) -> str:
    return (READY.replace("TEXT", json.dumps(text)).replace("INSIDE", inside).replace("BESIDE", beside)
            .replace("HREF", json.dumps(href)))


PREVIEW = ("el('div', {}, [el('img', {src: 'blob:https://www.facebook.com/5d1c', alt: ''}), "
           "el('div', {role: 'button', 'aria-label': 'Remove attachment'})])")
EDIT = "el('div', {}, [el('span', {}, [], 'Edit message'), el('div', {role: 'button', 'aria-label': 'Close'})])"
CHIP = "el('div', {}, [el('svg', {}), el('span', {}, [], 'lease.pdf'), el('div', {role: 'button', 'aria-label': 'Close'})]), "
PAGES = {  # a page, and whether the send script sends on it
    "plain": (ready(), True),
    "one-character-more": (ready(text=REPLY + "!\n"), False),
    "a-photo-strip-beside-the-composer": (ready(beside=f"[{PREVIEW}, composer]"), False),  # the third round's #6 shapes
    "a-file-chip-inside-the-composer": (ready(inside=CHIP), False),
    "an-edit-banner-beside-the-composer": (ready(beside=f"[{EDIT}, composer]"), False),
    "an-edit-banner-inside-the-composer": (ready(inside=EDIT + ", "), False),
    "the-live-reply-banner-beside-it": (ready(beside=f"[{LIVE_BANNER}, composer]"), False),
    "an-emoji-drawn-in-the-box": (ready().replace("el('div', LIVE, [],", "el('div', LIVE, [el('img', {alt: 'x'})],"), False),
    "another-conversation": (ready(href=PLAIN), False),
    "the-plain-chat-of-its-number": (ready(href="https://www.facebook.com/messages/t/1000000001/"), False),
    "no-send-control": (ready().replace("icon('Press enter to send')", "icon('Send a like')"), False),
    "two-send-controls": (ready().replace("icon('Press enter to send')", "icon('Press enter to send'), icon('Send')"), False),
    "two-boxes": (ready(beside="[composer, el('div', {contenteditable: 'true', role: 'textbox', 'aria-placeholder': 'Aa'})]"), False),
}


@pytest.mark.parametrize("page", sorted(PAGES))
def test_the_send_script_reads_the_composer_and_sends_in_the_same_run_only_when_all_is_as_approved(page):
    """The third round (#1, #2, #3, #6): the read and the send are one synchronous run, so nothing acts between them."""
    built, goes = PAGES[page]
    report, clicked = _send_on(built)
    assert report["send"] == sends.SEND_MARK and report["sent"] is goes and clicked == (["Press enter to send"] if goes else []), report


@pytest.mark.parametrize("text, entry_text, goes", [
    (REPLY + "\n", REPLY, True),                                                   # the one trailing break Lexical adds
    (REPLY, REPLY, True),
    ("First paragraph.\n\nSecond.\n", "First paragraph.\n\nSecond.", True),        # shift+Enter breaks read as \n inside
    ("First line.\nSecond line.", "First line.\r\nSecond line.", True),            # an entry's line endings, written one way
    ("\n", REPLY, False),                                                          # an empty box reads as one break
    (REPLY + "\n\n", REPLY, False),                                                # only one trailing break is Lexical's
    ("\n" + REPLY, REPLY, False),
])
def test_the_send_script_reads_the_box_as_lexical_writes_it(text, entry_text, goes):
    """The coordinator's live check, 2026-11-14: an empty Messenger box's innerText is a single line break."""
    report, clicked = _send_on(ready(text=text), {**CHAT, "text": entry_text})
    assert report["sent"] is goes and bool(clicked) is goes, report


def test_the_send_scripts_digest_is_sha256_of_the_words():
    texts = ["", "a", REPLY, "x" * 55, "x" * 56, "x" * 64, "Café 日本 👍🏽\nLine two.", "€" * 300]
    found = json.loads(_on_page("const body = null; const focus = null; const href = 'https://example.com/';",
                                "(() => { " + sends._SHA + " return JSON.stringify(" + json.dumps(texts) + ".map(sha)); })()"))
    assert json.loads(found["report"]) == [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in texts]


def test_the_composer_check_reads_the_live_messenger_box():
    report = _composer_on(LIVE_ROW.format(text=json.dumps("\n"), more="", focus="body"))
    assert report == {"check": sends.COMPOSER_MARK, "url": E2EE, "box": "found", "text": "\n", "focused": False,
                      "staged": 0, "marks": 0, "inline": 0, "boxes": 1}
    typed = _composer_on(LIVE_ROW.format(text=json.dumps(REPLY + "\n"), more="", focus="box"))
    assert typed["text"] == REPLY + "\n" and typed["focused"] is True and typed["staged"] == 0
    staged = _composer_on(LIVE_ROW.format(text=json.dumps(REPLY + "\n"), focus="box",
                                          more=", el('img', {src: 'blob:preview'}), el('div', {'aria-label': 'Remove attachment'})"))
    assert staged["staged"] == 2
    attach = _composer_on(LIVE_ROW.format(text=json.dumps("\n"), focus="body", more="").replace(
        "'aria-label': 'Press enter to send'", "'aria-label': 'Attach a file'"))
    assert attach["staged"] == 0  # the attach control alone places the composer too


def test_the_composer_check_matches_nothing_with_two_boxes_or_no_composer_around_one():
    two = _composer_on(LIVE_ROW.format(text=json.dumps("\n"), focus="body", more="").replace(
        "el('div', {}, [row])", "el('div', {}, [row]), el('div', {contenteditable: 'true', role: 'textbox', 'aria-placeholder': 'Aa'})"))
    assert two["box"] == "ambiguous" and two["text"] is None and two["staged"] is None
    alone = _composer_on("const box = el('div', LIVE, [], '\\n'); const body = el('body', {}, [el('div', {}, [box])]);"
                         "const focus = body; const href = 'https://www.facebook.com/messages/e2ee/t/1000000001/';")
    assert alone["box"] == "found" and alone["staged"] == "unknown"
    other = _composer_on("const box = el('div', {contenteditable: 'true', role: 'textbox', 'aria-label': 'Search'}, [], '');"
                         "const body = el('body', {}, [box]); const focus = body; const href = 'https://www.facebook.com/';")
    assert other["box"] == "none" and other["boxes"] == 1
    for label in ("Message", "Write to Dana Example"):  # either label alone names the box
        named = _composer_on(LIVE_ROW.format(text=json.dumps("\n"), focus="body", more="").replace(
            "const box = el('div', LIVE,", f"const box = el('div', {{contenteditable: 'true', role: 'textbox', 'aria-label': '{label}'}},"))
        assert named["box"] == "found", label


def test_the_hold_says_how_a_messenger_entry_is_sent():
    file = batch_file([CALL, CHAT])
    reason = guards.check("Bash", {"command": f"synthesis sends batch {file}"}, CONFIG, cwd=str(FOLDER))
    assert "synthesis sends script" in reason and "browser_batch" in reason and "Return" in reason
    alone = guards.check("Bash", {"command": f"synthesis sends batch {batch_file([CALL], name='mail-only')}"}, CONFIG,
                         cwd=str(FOLDER))
    assert "synthesis sends script" not in alone


def test_a_return_or_a_click_on_a_messenger_tab_spends_no_entry():
    """A Return after typed words, or a click on Send, sends whatever the box holds then: it waits for the code per call,
    and only the send step spends an entry."""
    granted([CHAT])
    session = opened()
    typed = {"actions": [{"name": "computer", "input": {"action": "type", "text": REPLY, "tabId": 7}},
                         {"name": "computer", "input": {"action": "key", "text": "Return", "tabId": 7}}]}
    for tool, given in ((CHROME, typed), (KEYS, RETURN),
                        (KEYS, {"action": "left_click", "ref": "ref_5", "tabId": 7, "action_summary": "Clicks Send"})):
        assert held(guards.check(tool, given, CONFIG, session=session)), given
    assert sent(step()) is None


def test_an_entry_covers_only_its_own_kind_of_send():
    granted([CHAT])
    assert held(guards.check(SLACK, SAID, CONFIG, session=SESSION))
    assert held(guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG))
    opened(PLAIN)
    assert sent(step({**CHAT, "to": "facebook.com/messages/t/1000000002"}))
    listed()
    assert sent(step()) is None


# --- every other check still runs first --------------------------------------------------------------------------


def test_an_entry_that_names_a_time_still_needs_a_fresh_calendar_read():
    config, words = {**CONFIG, "fresh_calendar": {}}, "Tuesday at 3:30 pm works for me."
    timed = {**SAID, "message": words}
    granted([{"tool": SLACK, "input": timed}, {**CHAT, "text": words}])
    session = opened()
    for reason in (guards.check(SLACK, timed, config, session=session), sent(step({**CHAT, "text": words}), config=config)):
        assert held(reason) and "names a time" in reason
    read_calendar()
    assert guards.check(SLACK, timed, config, session=session) is None
    assert sent(step({**CHAT, "text": words}), config=config) is None


def test_an_entry_released_by_the_code_for_its_time_is_spent_with_it():
    config, timed = {**CONFIG, "fresh_calendar": {}}, {**SAID, "message": "Tuesday at 3:30 pm works for me."}
    granted([{"tool": SLACK, "input": timed}])
    session = {**SESSION, "transcript_path": str(RECORD)}
    APPROVE(guards.check(SLACK, timed, config, session=session))
    assert guards.check(SLACK, timed, config, session=session) is None
    read_calendar()
    assert held(guards.check(SLACK, timed, config, session=session))


def test_the_register_scan_still_refuses_a_forbidden_phrase_in_an_entry():
    words = "Sorry for the delay, Tuesday works."
    granted([{"tool": SLACK, "input": {**SAID, "message": words}}, {**CHAT, "text": words}])
    opened()
    assert "delay-apology" in guards.check(SLACK, {**SAID, "message": words}, CONFIG, session=SESSION)
    assert "delay-apology" in sent(step({**CHAT, "text": words}))
    assert not any(e["how"].startswith("batch") for e in today())


def test_an_address_that_can_change_is_still_held():
    config, words = {**CONFIG, "temporary_addresses": {}}, "The draft is at https://quiet-river-1234.trycloudflare.com/notes"
    granted([{"tool": SLACK, "input": {**SAID, "message": words}}])
    assert "never given to anyone" in guards.check(SLACK, {**SAID, "message": words}, config, session=SESSION)


def test_a_meeting_placed_on_today_is_never_covered(monkeypatch):
    monkeypatch.setattr(guards, "_today", lambda: date(2026, 11, 9))
    config = {**CONFIG, "same_day_meetings": {"exempt": []}}
    invite = {"summary": "Follow-up", "start_time": "2026-11-09T15:00:00", "end_time": "2026-11-09T15:30:00",
              "attendees": ["a@example.com"], "user_google_email": "me@example.com"}
    later = {**invite, "start_time": "2026-11-10T15:00:00", "end_time": "2026-11-10T15:30:00"}
    granted([{"tool": EVENT, "input": invite}, {"tool": EVENT, "input": later}])
    reason = guards.check_send(EVENT, invite, config, SESSION)
    assert held(reason) and "same-day" in reason
    assert guards.check_send(EVENT, later, config, SESSION) is None


def test_the_window_and_the_batch_never_combine():
    signed = {"channel_id": "D0777", "message": "Status is green. Helperbot here"}
    sends.open_window(2, ["slack", "bitbucket"], count=1)
    data = granted([{"tool": SLACK, "input": signed}, CALL])
    assert guards.check(SLACK, signed, CONFIG, session=SESSION) is None
    assert today()[-1]["how"] == f"batch:{data['digest'][:12]}:0"
    assert "1 of 1 sends left" in sends.describe(sends.window())
    assert guards.check(SLACK, signed, CONFIG, session=SESSION) is None
    assert today()[-1]["how"] == "window" and sends.window() == {}
    post = f'bkt pr comment 5 -m "{REPLY}"'
    assert "posts to bitbucket" in guards.check("Bash", {"command": post}, CONFIG, cwd=str(FOLDER), session=SESSION)


def test_an_entry_past_twelve_hours_from_the_grant_is_held(monkeypatch):
    granted([CALL])
    later = time.time() + 12 * 3600 + 5
    monkeypatch.setattr(time, "time", lambda: later)
    assert held(guards.check(SLACK, SAID, CONFIG, session=SESSION))


@pytest.mark.parametrize("damage", ["text", "longer", "renamed", "unreadable", "spent", "unspent", "session"])
def test_tampered_or_unreadable_batch_state_falls_back_to_the_code(damage):
    """Review #11: a spent mark removed from the state, or the state handed to another session, opens nothing: the
    spends ledger keeps each entry's spend, and the session is checked against the principal's record."""
    data = granted([CALL, {"tool": SLACK, "input": {**SAID, "channel_id": "D0999"}}])
    if damage == "unspent":
        assert guards.check(SLACK, SAID, CONFIG, session=SESSION) is None
    file = paths.state() / "sends" / "batches" / f"{data['digest']}.json"
    state = json.loads(file.read_text(encoding="utf-8"))
    if damage == "text":
        state["entries"][0]["input"]["message"] = "Edited after the grant."
    elif damage == "longer":
        state["until"] = state["granted"] + 24 * 3600
    elif damage == "spent":
        state["spent"] = {"7": {"at": 1}}
    elif damage == "unspent":
        state["spent"] = {}
    elif damage == "session":
        state["session"] = "S-other"
    if damage == "renamed":
        file.rename(file.with_name("0" * 64 + ".json"))
    elif damage == "unreadable":
        file.write_text("{not json", encoding="utf-8")
    else:
        file.write_text(json.dumps(state), encoding="utf-8")
    for given in (SAID, {**SAID, "message": "Edited after the grant."}):
        assert held(guards.check(SLACK, given, CONFIG, session=SESSION)), given
    if damage == "unspent":  # and the status view counts the ledger's spend
        assert "1 of 2 entries left" in _cli("sends", "status").stdout
    if damage == "session":
        board.touch("S-other", project=PROJECT)
        assert held(guards.check(SLACK, SAID, CONFIG, session={"session_id": "S-other"}))


def test_close_ends_every_open_batch_and_status_shows_what_is_left():
    other = {**SAID, "channel_id": "D0999"}
    first = granted([CALL, {"tool": SLACK, "input": other}])
    second = granted([TEXT], name="replies-2")
    assert guards.check(SLACK, SAID, CONFIG, session=SESSION) is None
    status = _cli("sends", "status").stdout
    assert first["digest"][:12] in status and "1 of 2 entries left" in status
    assert second["digest"][:12] in status and "1 of 1 entries left" in status
    assert "2 batches ended" in _cli("sends", "close").stdout and sends.batches() == []
    assert held(guards.check(SLACK, other, CONFIG, session=SESSION))


def test_a_batch_granted_again_keeps_what_already_went():
    other = {**SAID, "channel_id": "D0999"}
    granted([CALL, {"tool": SLACK, "input": other}])
    assert guards.check(SLACK, SAID, CONFIG, session=SESSION) is None
    sends.close_batches()
    granted([CALL, {"tool": SLACK, "input": other}])
    assert held(guards.check(SLACK, SAID, CONFIG, session=SESSION))
    assert guards.check(SLACK, other, CONFIG, session=SESSION) is None


# --- only the principal grants: the state is written by the command alone ---------------------------------------


@pytest.mark.parametrize("tool, given", [
    ("Write", {"content": "{}"}), ("Edit", {"old_string": "a", "new_string": "b"}),
    ("MultiEdit", {"edits": []}), ("write_file", {"content": "{}"}), ("edit_file", {"edits": []}),
])
def test_the_file_tools_cannot_write_the_batch_state_or_the_spends_ledger(tool, given):
    for state in (paths.state() / "sends" / "batches" / ("a" * 64 + ".json"), paths.state() / "sends" / "batch-spends.jsonl"):
        named = {"file_path": str(state)} if tool in ("Write", "Edit", "MultiEdit") else {"path": str(state)}
        reason = guards.check(tool, {**named, **given}, CONFIG, cwd=str(FOLDER))
        assert reason and "would write" in reason


def test_no_shell_line_or_script_writes_the_batch_state_or_opens_a_batch():
    state = paths.state() / "sends" / "batches" / ("a" * 64 + ".json")
    patch = f"*** Begin Patch\n*** Add File: {state}\n+{{}}\n*** End Patch"
    assert "would write" in guards.check("apply_patch", {"input": patch}, CONFIG, cwd=str(FOLDER))
    for line in (f"echo '{{}}' > {state}", f"cp {FOLDER / 'b.json'} {state}"):
        assert "writes into the synthesis state" in guards.check("Bash", {"command": line}, CONFIG, cwd=str(FOLDER)), line
    for script in ("python3 -c 'from synthesis import sends; sends.open_batch({\"batch\": \"b\", \"project\": \"p\", \"entries\": []})'",
                   "python3 -c 'from synthesis import sends; sends._batch_file(\"a\").write_text(\"{}\")'"):
        reason = guards.check("Bash", {"command": script}, CONFIG, cwd=str(FOLDER))
        assert reason and "send-window code" in reason, script
    look = "python3 -c 'from synthesis import sends; print(sends.batches())'"
    assert guards.check("Bash", {"command": look}, CONFIG, cwd=str(FOLDER)) is None


# --- review round 2 (2026-11-15) ---------------------------------------------------------------------------------


def _extractors() -> list:
    """The read-only page scripts 5.23.0 ships, as their own commands print them."""
    rituals, exports = ROOT / "skills" / "synthesis-daily-rituals" / "scripts", ROOT / "skills" / "synthesis-message-exports" / "scripts"
    runs = [[str(rituals / "messenger_messages.py"), "extractor", "--inbox", inbox] for inbox in ("chats", "requests", "archived")]
    runs += [[str(exports / "chat_page.py"), "extractor"]]
    return [subprocess.run([sys.executable, *run], capture_output=True, text=True, check=True).stdout.rstrip("\n") for run in runs]


FORGE = "JSON.stringify = () => '{}'"


@pytest.mark.parametrize("url", [E2EE, "https://www.facebook.com/", "https://business.facebook.com/latest/inbox",
                                 "https://www.messenger.com/t/1000000003/"])
@pytest.mark.parametrize("script", [
    FORGE, "Object.defineProperty(HTMLElement.prototype, 'innerText', {get() { return 'x'; }})", "document.title",
    f"self.chat = open('{E2EE}')", "setTimeout(() => document.querySelector('[aria-label=\"Send a like\"]').focus(), 1500)",
], ids=["forge", "a-getter", "a-read", "an-opener", "a-timer"])
def test_no_page_script_but_the_shipped_ones_runs_on_a_messenger_sites_tab(url, script):
    """The third round (#1, #2): a page script on any page of those sites, which share the chat's origin, can change what
    the send script reads or what a click sends, then or later; it is refused at its own call."""
    reason = guards.check(SCRIPT, {"action": "javascript_exec", "text": script, "tabId": 7}, CONFIG, session=listed(url))
    assert reason and "shipped" in reason, reason
    batched = {"actions": [{"name": "navigate", "input": {"url": url, "tabId": 9}},
                           {"name": "javascript_tool", "input": {"action": "javascript_exec", "text": script, "tabId": 9}}]}
    assert "shipped" in (guards.check(CHROME, batched, CONFIG, session=listed("https://example.com/", tab=9)) or "")


def test_the_shipped_read_only_scripts_run_there():
    session = listed()
    for script in [sends.COMPOSER_CHECK, *_extractors()]:
        assert guards.check(SCRIPT, {"action": "javascript_exec", "text": script, "tabId": 7}, CONFIG, session=session) is None


def test_a_tab_another_session_lists_on_a_messenger_site_takes_no_page_script():
    """The third round (#2): a session that last saw a tab on another page, or never saw it, is not the only one judging."""
    other = RECORD.parent / "S-other.jsonl"
    other.touch()
    paths.write_json(paths.state() / "transcripts" / "S-other.json", {"path": str(other)})
    listed(E2EE, tab=9, record=other)
    session = listed("https://example.com/", tab=9)  # this session's own list shows another page there
    for tab in (9,):
        reason = guards.check(SCRIPT, {"action": "javascript_exec", "text": FORGE, "tabId": tab}, CONFIG, session=session)
        assert reason and "shipped" in reason


def test_a_page_script_off_the_messenger_sites_runs_as_before():
    session = listed("https://example.com/", tab=9)
    assert guards.check(SCRIPT, {"action": "javascript_exec", "text": "document.title", "tabId": 9}, CONFIG, session=session) is None


@pytest.mark.parametrize("where", ["a-tab-no-record-lists", "back-from-another-site", "a-path-from-another-site"])
def test_a_page_script_on_a_page_no_record_names_is_refused(where):
    """Round 3's probe of #2 on the head: an opener script on a tab no list of tabs named yet passed, and in a browser
    such a script can open the chat and keep a timer that patches it through the send step's load. A page the guard
    cannot place may be a Messenger site's, so it takes no page script (rule 6: fail closed)."""
    session = listed("https://example.com/", tab=9)
    opener = {"action": "javascript_exec", "text": f"self.chat = open('{E2EE}')", "tabId": 9}
    if where == "a-tab-no-record-lists":
        tool, given = SCRIPT, {**opener, "tabId": 12}
    else:
        tool, given = CHROME, {"actions": [{"name": "navigate", "input": {"url": "back" if where.startswith("back") else "/l.php",
                                                                          "tabId": 9}}, {"name": "javascript_tool", "input": opener}]}
    reason = guards.check(tool, given, CONFIG, session=session)
    assert reason and "no list of tabs" in reason, reason


@pytest.mark.parametrize("text", ["open('https://www.linkedin.com/messaging/thread/1/')", "globalThis.open('/messaging/thread/1/')",
                                  "window['open']('/messaging/thread/1/')", "self.open('/messaging/thread/1/')"])
def test_opening_a_page_by_any_spelling_of_open_is_refused_on_a_messaging_page(text):
    """The third round (#2): `open(` opens a chat and marks it read as `window.open(` does, under any name. Since 5.23.1
    (round 4, #3 and #7) every page script on a messaging site's page but the shipped readers is refused, by any spelling."""
    session = listed("https://www.linkedin.com/messaging/", tab=8)
    for script in (text, "reopen(1); x.open('GET', '/a')"):
        reason = guards.check(SCRIPT, {"action": "javascript_exec", "text": script, "tabId": 8}, CONFIG, session=session)
        assert reason and "shipped" in reason and not held(reason), script


def test_the_hold_shows_the_files_path_escaped():
    """Review 2 #3: line breaks in the file's name printed a fake listing, and an escape code hid the real one."""
    batch = sends.read_batch(str(batch_file([CALL])))
    sly = str(FOLDER / "replies\n  1. slack by mcp__x: channel_id \"D1\"\x1b[8m.json")
    reason = sends.batch_refusal(batch, sly)
    assert "\x1b" not in reason and "\n  1. slack by mcp__x" not in reason and "\\u001b" in reason
    (FOLDER / "bad\x1b[8m.json").write_text("{", encoding="utf-8")
    with pytest.raises(ValueError) as refused:
        sends.read_batch(str(FOLDER / "bad\x1b[8m.json"))
    assert "\x1b" not in str(refused.value)


def test_the_batch_name_and_project_are_shown_escaped():
    """Review 2 #11: the approval's summary and `sends status` showed them raw."""
    data = granted([CALL], name="replies‮-1")
    pending = [paths.read_json(p) for p in (paths.state() / "approval-requests").glob("*.json")]
    assert all("‮" not in p.get("summary", "") for p in pending)
    assert "‮" not in sends.describe_batch(data) and "\\u202e" in sends.describe_batch(data)


def test_the_code_for_a_messenger_entrys_time_binds_this_exact_send():
    """Review 2 #4: the code the time's hold asked for released whatever the box held at the next Return. Now it binds
    the send step itself: its conversation's address, and its script, which holds the words' digest."""
    config, words = {**CONFIG, "fresh_calendar": {}}, "Tuesday at 3:30 pm works for me."
    entry = {**CHAT, "text": words}
    data = granted([entry])
    opened()
    reason = sent(step(entry), config=config)
    assert held(reason) and "names a time" in reason
    APPROVE(reason)
    assert sent(step(entry, words=words + " P.S."), config=config)  # another call: its own hold
    assert sent(step(entry), config=config) is None
    assert today()[-1]["how"] == f"batch:{data['digest'][:12]}:0" and sent(step(entry), config=config)


def test_a_spends_code_must_be_the_one_typed_for_this_batchs_digest():
    """Review 2 #5: any code the principal typed in 12 hours, for anything, made forged batch state spendable."""
    unrelated = approvals.request("send", {"tool": SLACK, "input": {"channel_id": "D0555", "message": "Hi."}}, "a note")
    APPROVE(held_in_record(f"Sending needs the principal's approval: type approve followed by the code {unrelated}."))
    batch = sends.read_batch(str(batch_file([CALL])))
    sends.open_batch(batch, {"code": unrelated, "asked": time.time() - 30}, "S-principal")
    assert held(guards.check(SLACK, SAID, CONFIG, session=SESSION))


def _says(text: str, age: float = 0.0) -> None:
    """The agent's own words in the session's record, as Claude Code writes an assistant text block."""
    _record({"type": "assistant", "timestamp": (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat(),
             "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}})


def _typed(code: str, age: float) -> None:
    _record({"type": "user", "timestamp": (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat(),
             "origin": {"kind": "human"}, "sessionId": "S-principal", "message": {"role": "user", "content": f"approve {code}"}})


def test_a_line_the_agent_writes_never_ties_a_code_to_a_batch():
    """Review 3 #4: the hold was any record line naming the digest and the code, so the agent's own sentence tied a code
    the principal typed for an unrelated note to forged batch state (the state write stands in for round 2's #6)."""
    note = {"tool": SLACK, "input": {"channel_id": "D0555", "message": "Hi."}}
    code = approvals.request("send", note, "a note")
    batch = sends.read_batch(str(batch_file([CALL])))
    _says(f"Batch digest {sends.batch_digest(batch)} is filed for later. The note waits on the code {code}.")
    APPROVE(f"code {code}")
    sends.open_batch(batch, {"code": code, "asked": time.time() - 30}, "S-principal")
    assert held(guards.check(SLACK, SAID, CONFIG, session=SESSION))


def test_a_forged_batch_outlives_no_code_typed_hours_ago():
    """Review 3 #4, second case: a code typed three hours ago for something else let forged state go, where 5.23.0's
    fifteen minutes refuse a forged approval of the same message."""
    code, hours = approvals.request("send", {"tool": SLACK, "input": {"channel_id": "D0555", "message": "Hi."}}, "a note"), 3 * 3600
    batch = sends.read_batch(str(batch_file([CALL])))
    _says(f"batch {sends.batch_digest(batch)}; the note waits on the code {code}", age=hours + 60)
    _typed(code, age=hours)
    sends.open_batch(batch, {"code": code, "asked": time.time() - hours - 120}, "S-principal")
    assert held(guards.check(SLACK, SAID, CONFIG, session=SESSION))


def test_a_batch_whose_digest_and_code_the_agent_repeats_still_sends():
    """Review 3, its note: the newest line naming both was taken as the hold, so repeating them after the principal typed
    the code held every later send of a granted batch."""
    data = granted([CALL, {"tool": SLACK, "input": {"channel_id": "D0124", "message": REPLY}}])
    time.sleep(0.02)  # after the principal's code, which the fixture stamps 5 ms ahead
    _says(f"Batch {data['digest']} is open on the code {data['code']}; two sends to go.")
    assert guards.check(SLACK, SAID, CONFIG, session=SESSION) is None
    assert guards.check(SLACK, {"channel_id": "D0124", "message": REPLY}, CONFIG, session=SESSION) is None


def test_the_functions_that_lead_into_the_state_are_the_guards_to_see():
    assert {"sends._spends_file", "sends._batch_file", "sends._window_file"} <= guards.SYNTHESIS_PLACES
    assert "sends._requests_file" in guards.SYNTHESIS_PLACES  # the guard's own record of each batch's code (round 3 #4)
    for line in ("python3 -c 'from synthesis import sends; sends._spends_file().write_text(\"\")'",
                 "python3 -c 'from synthesis import sends; open(sends._spends_file(), \"w\").close()'"):
        assert guards.check("Bash", {"command": line}, CONFIG, cwd=str(FOLDER)), line


def test_a_photo_or_a_file_carrying_field_is_never_covered_and_connector_entries_go_one_to_a_conversation():
    """Review 2 #7: the connector form carried the messages sender's photo, and skipped one entry per conversation."""
    photo = {"name": "a.jpg", "bytes": 9, "sha256": "0" * 64}
    with pytest.raises(ValueError, match="entry 1"):
        sends.read_batch(str(batch_file([{"tool": "imessage_send", "input": {"to": "+15550100", "text": REPLY, "photo": photo}}])))
    with pytest.raises(ValueError, match="entry 2 .*conversation"):
        sends.read_batch(str(batch_file([CALL, {"tool": SLACK, "input": {**SAID, "message": "And another thing."}}])))
    for field in ("photo", "picture", "video", "audio", "voice", "blob", "sticker", "thumbnail", "avatar"):
        sends.close_batches()
        given = {"channel_id": f"D-{field}", "message": REPLY, field: photo}
        granted([{"tool": SLACK, "input": given}], name=f"carry-{field}")
        assert held(guards.check(SLACK, given, CONFIG, session=SESSION)), field


def test_every_invisible_or_variation_character_is_shown_as_its_code():
    """Review 2 #8: variation selectors, U+034F, U+115F and U+3164 printed as is, rendering as nothing."""
    hidden = "️\U000e0100͏ᅟᅠㅤﾠ⠀ 　"
    listing = sends.batch_listing(sends.read_batch(str(batch_file([{**CHAT, "text": "Thanks." + hidden + " See you."}]))), show=True)
    assert not set(hidden) & set(listing)
    for code in ("\\ufe0f", "\\U000e0100", "\\u034f", "\\u115f", "\\u3164"):
        assert code in listing, code


@pytest.mark.parametrize("blank", ["\U0001d159", "\U00016fe4"], ids=["U+1D159", "U+16FE4"])
def test_a_character_that_draws_nothing_is_shown_as_its_code(blank):
    """Review 3 #7: MUSICAL SYMBOL NULL NOTEHEAD (a symbol) and KHITAN SMALL SCRIPT FILLER (a mark) printed as is."""
    listing = sends.batch_listing(sends.read_batch(str(batch_file([{**CHAT, "text": "Thanks." + blank + " See you."}]))), show=True)
    assert blank not in listing and f"\\U{ord(blank):08x}" in listing


def test_only_what_draws_a_glyph_prints_as_it_is():
    """Review 3 #7, the rule turned round: letters, marks, digits, punctuation and symbols print as they are, and so do
    a plain space and a line break, so a connector call's input prints one field to a line (it printed as one line,
    each line break shown as its code)."""
    drawn = "Café 日本 ١٢٣ — 👍🏽 €"
    listing = sends.batch_listing(sends.read_batch(str(batch_file([{**CHAT, "text": drawn}, CALL]))), show=True)
    assert json.dumps(drawn, ensure_ascii=False) in listing
    assert '\n       {\n         "channel_id": "D0123",\n' in listing and "\\u000a" not in listing


def test_a_lone_surrogate_is_refused_as_a_control_character_is():
    """A JSON escape may hold half of a surrogate pair, which no listing shows and no message can carry."""
    odd = FOLDER / "surrogate.json"
    odd.write_text('{"batch": "b", "project": "p", "entries": [{"channel": "messenger", "to": "%s", "text": "Hi \\ud800 there."}]}'
                   % CHAT["to"], encoding="utf-8")
    with pytest.raises(ValueError, match="surrogate"):
        sends.read_batch(str(odd))


@pytest.mark.parametrize("odd", [" ", " ", "‮", " ", "é", "/"],
                         ids=["line-separator", "paragraph-separator", "right-to-left-override", "space", "accent", "slash"])
def test_a_tool_name_holds_only_plain_letters_digits_and_the_marks_names_use(odd):
    """Review 3 #9: a tool name printed raw in the listing, the one field not escaped, so a line separator in it drew a
    line of the agent's own text beside the entries; a name holds only [A-Za-z0-9_.:-]."""
    with pytest.raises(ValueError, match="entry 1 names a tool"):
        sends.read_batch(str(batch_file([{"tool": SLACK + odd + "x", "input": {"channel_id": "D0123", "message": "Hi."}}])))
    assert sends.read_batch(str(batch_file([{"tool": "mcp__a1-b2.c3:d__slack_send_message", "input": SAID}])))


def test_the_composer_check_reports_a_reply_or_edit_banner_and_images_in_the_box():
    reply = ("el('div', {}, [el('span', {}, [], 'Replying to Dana Example'), el('span', {}, [], 'Can you wire it today?'),"
             " el('div', {role: 'button', 'aria-label': 'Close'})])")
    edit = "el('div', {}, [el('span', {}, [], 'Editing message'), el('div', {role: 'button', 'aria-label': 'Cancel'})])"
    for banner in (reply, edit):
        page = LIVE_ROW.format(text=json.dumps(REPLY + "\n"), more="", focus="box").replace(
            "[el('div', {}, [box])", "[" + banner + ", el('div', {}, [box])")
        assert _composer_on(page)["marks"] > 0, banner
    plain = _composer_on(LIVE_ROW.format(text=json.dumps("Editing the plan now.\n"), more="", focus="box"))
    assert plain["marks"] == 0  # the box's own words are no banner
    drawn = _composer_on(LIVE_ROW.format(text=json.dumps(REPLY + "\n"), more="", focus="box").replace(
        "const box = el('div', LIVE, [],", "const box = el('div', LIVE, [el('img', {alt: 'x', src: 'emoji.png'})],"))
    assert drawn["inline"] == 1


# Reply mode as the coordinator read it on a live chat (2026-11-15): the banner is the composer's previous sibling, not
# inside it: a `role="heading"` reading `Replying to <First name>`, the quoted message's text and a `Cancel reply`
# button; the composer holds its seven controls and the box, focused and empty. The check reads every other child of
# the composer's parent, so a banner after the composer (where an edit banner might sit; none was read live) marks too.
# The composer always holds a visually hidden `<h3>` reading `Compose` (HIDDEN_COMPOSE: the live read of
# synthesis-composer-4, 2026-11-15: one pixel square, clipped, placed absolutely), and in plain mode it is its parent's only child.
LIVE_REPLY = ("const box = el('div', LIVE, [], '\\n');"
              "const composer = el('div', {}, [" + HIDDEN_COMPOSE + ", ...['Send a voice clip', 'Attach a file up to 100 MB', "
              "'Choose a sticker', 'Choose a GIF'].map(l => el('div', {role: 'button', 'aria-label': l})), el('div', {}, [box]), "
              "el('div', {role: 'button', 'aria-label': 'Choose an emoji'}), el('div', {role: 'button', 'aria-label': 'Send a like'})]);"
              "const body = el('body', {}, [el('div', {role: 'main'}, [el('div', {}, CHILDREN)])]);"
              "const focus = box; const href = 'https://www.facebook.com/messages/e2ee/t/1000000001/';")


def test_the_hidden_compose_heading_inside_the_composer_is_no_mark():
    """The live read of synthesis-composer-4: a plain composer read one mark, its own hidden `Compose` heading."""
    plain = _composer_on(LIVE_REPLY.replace("CHILDREN", "[composer]").replace("const focus = box", "const focus = body"))
    assert plain == {"check": sends.COMPOSER_MARK, "url": E2EE, "box": "found", "text": "\n", "focused": False,
                     "staged": 0, "marks": 0, "inline": 0, "boxes": 1}
    assert _composer_on(LIVE_REPLY.replace("CHILDREN", f"[{LIVE_BANNER}, composer]"))["marks"] > 0
    for heading in ("el('h3', {}, [], 'Replying to Pat')", "el('div', {role: 'heading'}, [], 'Editing message')"):
        titled = LIVE_REPLY.replace("CHILDREN", "[composer]").replace(HIDDEN_COMPOSE, heading)
        assert _composer_on(titled)["marks"] > 0, heading  # inside the composer, a heading counts by its own words


@pytest.mark.parametrize("after", [False, True], ids=["before", "after"])
@pytest.mark.parametrize("banner", [
    LIVE_BANNER,
    "el('div', {role: 'heading'}, [], 'Replying to Pat')",
    "el('div', {}, [el('div', {role: 'heading'}, [], 'Pat')])",
    "el('div', {}, [el('h4', {}, [], 'Pat')])",
    "el('div', {}, [el('div', {role: 'button', 'aria-label': 'Cancel reply'})])",
    "el('div', {}, [el('div', {role: 'button'}, [], 'Cancel reply')])",
    "el('div', {}, [el('span', {}, [], 'Editing message')])",
], ids=["live", "the-sibling-the-heading", "a-heading-whatever-it-reads", "a-heading-by-its-tag", "cancel-by-its-label",
        "cancel-by-its-text", "editing"])
def test_the_composer_check_reads_reply_mode_from_the_banner_beside_the_composer(banner, after):
    def on(sibling):
        return _composer_on(LIVE_REPLY.replace("CHILDREN", f"[composer, {sibling}]" if after else f"[{sibling}, composer]"))
    report = on(banner)
    assert report["marks"] > 0 and report["box"] == "found" and report["focused"] is True and report["text"] == "\n"
    plain = on("el('div', {}, [el('span', {}, [], 'Pat Example')])")
    assert plain["marks"] == 0 and plain["staged"] == 0  # a sibling that is no banner marks nothing


OTHER = {"session_id": "S-other", "transcript_path": "/nonexistent/S-other.jsonl"}


def test_the_senders_session_is_the_one_whose_guard_let_it_run():
    """Review 3 #5 (round 2's #10): the sender's own --session chose whose entry it spent, and the shell guard checked
    that only on a word named messages_send.py. Now the sender names no session: a command the guard sees run it files a
    one-use ticket for the session the hook names, and an entry is spent only on its granting session's ticket."""
    granted([TEXT])
    asked, line = {"to": "+15550100", "text": REPLY}, f"python3 {SENDER} --to +15550100 --text-file reply.txt"
    assert held(guards.check_send("imessage_send", asked, CONFIG))  # no command the guard let through runs it
    assert guards.check("Bash", {"command": line}, CONFIG, cwd=str(FOLDER), session=OTHER) is None
    assert held(guards.check_send("imessage_send", asked, CONFIG, {"session_id": "S-principal"}))  # S-other's ticket
    assert guards.check("Bash", {"command": line}, CONFIG, cwd=str(FOLDER), session={**SESSION, "transcript_path": str(RECORD)}) is None
    assert guards.check_send("imessage_send", asked, CONFIG) is None  # its own session's ticket, spent with the entry
    assert held(guards.check_send("imessage_send", asked, CONFIG))  # one ticket, one send


@pytest.mark.parametrize("form", ["link", "runpy"])
def test_a_sender_run_under_another_name_spends_no_entry(form):
    """Review 3 #5: a link made earlier, or runpy from python3 -c, kept the --session naming the principal's session,
    and another session spent its entry. Such a run files no ticket, so it waits for the code per call."""
    granted([TEXT])
    (FOLDER / "reply_tool.py").symlink_to(SENDER)
    command = ("python3 reply_tool.py --to +15550100 --text-file reply.txt" if form == "link" else
               f"python3 -c \"import runpy, sys; sys.argv = ['m', '--to', '+15550100', '--text-file', 'reply.txt']; "
               f"runpy.run_path('{SENDER}', run_name='__main__')\"")
    guards.check("Bash", {"command": command}, CONFIG, cwd=str(FOLDER), session=OTHER)  # whatever it says, it files no ticket
    assert held(guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG, {"session_id": "S-principal"}))


def test_the_sender_takes_no_session_of_its_own():
    import importlib.util
    spec = importlib.util.spec_from_file_location("messages_send_under_test", SENDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(SystemExit):  # an argument it does not have: nothing is read, resolved or sent
        module.main(["--to", "+15550100", "--session", "S-principal"])
