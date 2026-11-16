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


def ran_sender() -> dict:
    """A command that runs the messages sender, let through by this session's guard: the ticket its send spends on; the
    sender's own run of that command, which takes it (round 4, #6)."""
    assert guards.check("Bash", {"command": f"python3 {SENDER} --to +15550100 --text-file reply.txt"}, CONFIG, cwd=str(FOLDER),
                        session={**SESSION, "transcript_path": str(RECORD)}) is None
    return _run(*TO_A)


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
        assert held(guards.check_send(tool, given, CONFIG, run=ran_sender())), (tool, given)
    assert guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG, run=ran_sender()) is None
    assert guards.check_send("messages_send", members, CONFIG, run=ran_sender()) is None
    one = {"to": ["+15550103"], "service": "iMessage", "text": "On my way.", "chat": "chat-7"}
    assert guards.check_send("messages_send", one, CONFIG, run=ran_sender()) is None
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
                   "a-batch-step": (CHROME, {"actions": [{"name": "computer", "input": {"action": "left_click", "coordinate": [5, 5],
                                                                                          "tabId": 7, "action_summary": "Clicks"}}]}),
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
    reason = guards.check(CHROME, batched, CONFIG, session=listed("https://example.com/", tab=9)) or ""
    assert "shipped" in reason and "call of its own" not in reason and not held(reason), reason  # after the batch's own
    # navigate (round 4, #2), the page's own rule (round 5, #3)


def test_the_shipped_read_only_scripts_run_there():
    session = listed()
    for script in [sends.COMPOSER_CHECK, *_extractors()]:
        assert guards.check(SCRIPT, {"action": "javascript_exec", "text": script, "tabId": 7}, CONFIG, session=session) is None


def test_a_tab_another_session_lists_on_a_messenger_site_takes_no_page_script():
    """The third round (#2): a session that last saw a tab on another page, or never saw it, is not the only one judging."""
    other = RECORD.parent / "S-other.jsonl"
    other.touch()
    paths.write_json(paths.state() / "transcripts" / "S-other.json", {"path": str(other)})
    session = listed("https://example.com/", tab=9)  # this session's own list shows another page there
    time.sleep(0.01)
    listed(E2EE, tab=9, record=other)  # and the other session's newer list shows a chat (round 4, #13: the newer list decides)
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
    assert held(guards.check(SCRIPT, {"action": "javascript_exec", "text": text, "tabId": 8}, CONFIG, session=session)), text
    assert guards.check(SCRIPT, {"action": "javascript_exec", "text": "reopen(1); x.open('GET', '/a')", "tabId": 8}, CONFIG,
                        session=session) is None


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
    assert held(guards.check_send("imessage_send", asked, CONFIG, run=_run(*TO_A)))  # no command the guard let through runs it
    assert guards.check("Bash", {"command": line}, CONFIG, cwd=str(FOLDER), session=OTHER) is None
    assert held(guards.check_send("imessage_send", asked, CONFIG, {"session_id": "S-principal"}, run=_run(*TO_A)))  # S-other's ticket
    assert guards.check("Bash", {"command": line}, CONFIG, cwd=str(FOLDER), session={**SESSION, "transcript_path": str(RECORD)}) is None
    assert guards.check_send("imessage_send", asked, CONFIG, run=_run(*TO_A)) is None  # its own session's ticket, spent with the entry
    assert held(guards.check_send("imessage_send", asked, CONFIG, run=_run(*TO_A)))  # one ticket, one send


@pytest.mark.parametrize("form", ["link", "runpy"])
def test_a_sender_run_under_another_name_spends_no_entry(form):
    """Review 3 #5: a link made earlier, or runpy from python3 -c, kept the --session naming the principal's session,
    and another session spent its entry. Such a run files no ticket, so it waits for the code per call."""
    granted([TEXT])
    (FOLDER / "reply_tool.py").symlink_to(SENDER)
    command = ("python3 reply_tool.py --to +15550100 --text-file reply.txt" if form == "link" else
               f"python3 -c \"import runpy, sys; sys.argv = ['m', '--to', '+15550100', '--text-file', 'reply.txt']; "
               f"runpy.run_path('{SENDER}', run_name='__main__')\"")
    guards.check("Bash", {"command": command}, CONFIG, cwd=str(FOLDER), session=OTHER)  # a link files S-other's own ticket
    run = _run(*TO_A, program=FOLDER / "reply_tool.py") if form == "link" else _run(*TO_A)  # the run sees its own file
    assert held(guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG, {"session_id": "S-principal"}, run=run))
    assert not today()


def test_the_sender_takes_no_session_of_its_own():
    import importlib.util
    spec = importlib.util.spec_from_file_location("messages_send_under_test", SENDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(SystemExit):  # an argument it does not have: nothing is read, resolved or sent
        module.main(["--to", "+15550100", "--session", "S-principal"])


# --- review round 4 (2026-11-15) -----------------------------------------------------------------------------------
# A page script that reached a Messenger chat by a way the batch's rule did not read (#2), a driven page the record does
# not show (#9), the built-in pane's own results (#5), another session's call in another browser or one a hook refused
# (#10), another session's stale list (#13), names a script builds (#7) and blanks of a drawing kind (#8); the sender's
# ticket (#6, #11, #12), the ledger of a Messenger send the script declined, and a batch's last usable hour.

PANE = "mcp__Claude_Browser__"
BUILT_CLICK = "document.querySelector('[aria-label=\"Press enter to send\"]')['cli' + 'ck']()"
WRITTEN_CLICK = "document.querySelector('[aria-label*=\"Press enter\"]').click()"


def _batch_on(tab, *steps) -> dict:
    return {"actions": [{"name": name, "input": {**given, "tabId": tab}} for name, given in steps]}


@pytest.mark.parametrize("move", [("navigate", {"url": "https://m.me/patexample"}), ("navigate", {"url": "https://fb.com/messages/t/1000000001/"}),
                                  ("navigate", {"url": "https://fb.me/2xYz9Q"}), ("navigate", {"url": "https://bit.ly/3AbCdEf"}),
                                  ("computer", {"action": "left_click", "coordinate": [120, 340], "action_summary": "Opens the Messenger link"}),
                                  ("computer", {"action": "key", "text": "Return"}), ("computer", {"action": "type", "text": "x\n"})],
                         ids=["m.me", "fb.com", "fb.me", "short-link", "a-link-clicked", "a-key", "a-typed-line-break"])
@pytest.mark.parametrize("script", [BUILT_CLICK, WRITTEN_CLICK, "document.title"], ids=["built", "written", "reads"])
def test_a_script_after_a_step_that_may_move_the_page_is_refused(move, script):
    """Round 4, #2: the page a later step acts on was the batch's own navigate's address, and a click never moved it, so a
    batch that landed on a Messenger chat by m.me, fb.com, fb.me, a short link or a followed link ran its script there."""
    session = listed("https://example.com/", tab=9)
    batch = _batch_on(9, move, ("computer", {"action": "type", "text": "Words nobody approved."}),
                      ("javascript_tool", {"action": "javascript_exec", "text": script}))
    reason = sent(batch)
    onto = move[0] == "navigate" and guards._messenger_site(move[1]["url"])  # onto a Messenger site's page: only the plugin's own
    if script == "document.title" and not onto:  # a read after a move from a page that is no messaging site's runs (round 5 prep)
        assert reason is None, reason
    else:  # onto a Messenger site's page that page's own rule is named (round 5, #3)
        assert reason and not held(reason) and ("shipped" if onto else "may have moved") in reason, reason
    alone = sent({"actions": [batch["actions"][-1]]})  # in a call of its own, judged on the page the list shows
    assert session and alone is None, alone


LOCAL = "http://localhost:3000/"
CLICK_SAVE = ("computer", {"action": "left_click", "coordinate": [5, 5], "action_summary": "Clicks Save"})


@pytest.mark.parametrize("script", ["document.title", "document.querySelector('#save').click()"])
def test_a_click_then_a_script_on_a_local_app_runs_in_chrome_and_in_the_pane(script):
    """The batch's moved rule refused a pane batch on localhost that clicked and then read: ordinary work. On a local
    app's page a click moves nothing, and a script after it runs, one that clicks Save included (review round 6, #4, as
    ruled: a local page that redirects the tab is on the open list)."""
    listed(LOCAL, tab=9)
    acts = False
    reason = sent(_batch_on(9, CLICK_SAVE, ("javascript_tool", {"action": "javascript_exec", "text": script})))
    assert (reason and "may have moved" in reason) if acts else reason is None, reason
    ran(PANE + "navigate", {"url": LOCAL}, said=f"navigated to {LOCAL}\n\n\nTab Context:\n- Executed on tabId: tab-1\n- "
        f"Available tabs:\n  • tabId tab-1: \"App\" ({LOCAL})")
    pane = {"actions": [{"name": "computer", "input": {k: v for k, v in CLICK_SAVE[1].items()}},
                        {"name": "javascript_tool", "input": {"action": "javascript_exec", "text": script}}]}
    reason = sent(pane, tool=PANE + "browser_batch")
    assert (reason and "may have moved" in reason) if acts else reason is None, reason
    assert sent({"actions": [pane["actions"][-1]]}, tool=PANE + "browser_batch") is None  # in a call of its own it runs


def test_a_click_then_a_read_on_an_ordinary_site_runs_and_one_that_acts_goes_in_its_own_call():
    listed("https://docs.example.com/guide", tab=9)
    click = ("computer", {"action": "left_click", "coordinate": [5, 5], "action_summary": "Opens the next page"})
    assert sent(_batch_on(9, click, ("javascript_tool", {"action": "javascript_exec", "text": "document.title"}))) is None
    for script in (WRITTEN_CLICK, BUILT_CLICK):  # it may have followed a link to a chat: what acts waits for a list of tabs
        reason = sent(_batch_on(9, click, ("javascript_tool", {"action": "javascript_exec", "text": script})))
        assert reason and "may have moved" in reason and not held(reason), (script, reason)


@pytest.mark.parametrize("url", ["https://www.linkedin.com/messaging/", "https://m.me/patexample", "https://www.facebook.com/messages/"])
def test_a_move_onto_a_messaging_page_then_a_script_is_refused(url):
    """Onto a Messenger site's page any script but the plugin's own is refused; onto another messaging site's page a script
    that acts or cannot be read is, and a read runs, as main's rule lets it on that page."""
    listed("https://docs.example.com/guide", tab=9)
    for script in ("document.title", WRITTEN_CLICK):
        reason = sent(_batch_on(9, ("navigate", {"url": url}), ("javascript_tool", {"action": "javascript_exec", "text": script})))
        if script == "document.title" and not guards._messenger_site(url):
            assert reason is None, (url, reason)
        else:
            assert reason and not held(reason), (url, script, reason)


@pytest.mark.parametrize("url", ["back", "/inbox"])
def test_a_move_to_a_page_the_guard_cannot_place_then_a_script_is_refused(url):
    listed("https://docs.example.com/guide", tab=9)
    reason = sent(_batch_on(9, ("navigate", {"url": url}), ("javascript_tool", {"action": "javascript_exec", "text": "document.title"})))
    assert reason and not held(reason), (url, reason)


def test_a_script_after_a_navigate_to_a_local_app_still_runs():
    session = listed("https://example.com/", tab=9)
    assert session and sent(_batch_on(9, ("navigate", {"url": "http://localhost:3000/"}),
                                     ("javascript_tool", {"action": "javascript_exec", "text": "document.title"}))) is None


@pytest.mark.parametrize("url", ["https://m.me/patexample", "https://fb.com/messages/t/1000000001/", "https://fb.me/2xYz9Q",
                                 "https://business.facebook.com/latest/inbox/all"])
def test_every_host_the_guard_counts_as_messenger_takes_only_the_shipped_scripts(url):
    assert guards._messenger_site(url), url
    listed(url, tab=9)
    reason = sent({"actions": [{"name": "javascript_tool", "input": {"action": "javascript_exec", "text": "document.title", "tabId": 9}}]})
    assert reason and "Messenger site" in reason and not held(reason), reason


def test_a_script_in_the_built_in_pane_after_its_navigate_runs():
    """Round 4, #5: the pane's own results name its page; a Chrome list is not needed for it."""
    ran(PANE + "tabs_context", {}, said=json.dumps({"browserOpen": True, "tabs": [{"tabId": "1", "origin": "http://localhost:3000", "isActive": True}]}))
    ran(PANE + "navigate", {"url": "http://localhost:3000/"}, said="Navigated to http://localhost:3000/")
    assert sent({"action": "javascript_exec", "text": "document.title"}, tool=PANE + "javascript_tool") is None


@pytest.mark.parametrize("spelling", ["window?.open('{c}')", "document.defaultView.open('{c}')", "open`{c}`",
                                      "Reflect.apply(open, window, ['{c}'])", "open/**/('{c}')"])
def test_open_by_any_spelling_is_refused_on_a_messaging_page(spelling):
    """Round 4, #7: MOVES knew some spellings of open(; every script there but the shipped readers is refused now."""
    listed("https://www.linkedin.com/messaging/", tab=5)
    text = spelling.format(c="https://www.linkedin.com/messaging/thread/2-abc/")
    reason = guards.check(SCRIPT, {"action": "javascript_exec", "text": text, "tabId": 5}, CONFIG, session={**SESSION, "transcript_path": str(RECORD)})
    assert reason and (held(reason) or "cannot read" in reason), text  # main's rule there: it acts, or it cannot be read


def test_a_character_whose_name_says_it_draws_nothing_is_shown_as_its_code():
    """Round 4, #8: blanks, joiners and selectors of a drawing category printed as they are in the hold."""
    import re as _re
    import unicodedata
    for c in ("\U00013441", "\U00013442", "⵿", "\U0001107f", "\U00011a47", "\U0001bc9d"):
        assert sends._escaped(c) != c, hex(ord(c))
    named = [chr(n) for n in range(0x110000) if unicodedata.category(chr(n))[0] in "LMNPS"
             and _re.search(r"\b(?:BLANK|FILLER|JOINER|SUBJOINER|CONJOINER|SELECTOR)\b", unicodedata.name(chr(n), ""))]
    assert named and not [hex(ord(c)) for c in named if sends._escaped(c) == c]
    assert sends._escaped("Tuesday, à demain 🙂") == "Tuesday, à demain 🙂"


def test_a_driven_script_on_a_page_its_record_does_not_show_is_refused():
    """Round 4, #9: after a tab change the driven browser's page is unknown, and an unknown page takes no script."""
    ran("mcp__plugin_playwright_playwright__browser_navigate", {"url": E2EE}, said=f"- Page URL: {E2EE}\n")
    ran("mcp__plugin_playwright_playwright__browser_tabs", {"action": "new"}, said="Opened a new tab")
    ran("mcp__plugin_playwright_playwright__browser_tabs", {"action": "select", "index": 0}, said="Selected tab 0")
    reason = sent({"function": "() => { JSON.stringify = () => '{}' }"}, tool="mcp__plugin_playwright_playwright__browser_evaluate")
    assert reason and "does not show" in reason and not held(reason), reason


def test_another_sessions_call_in_another_browser_or_one_that_changes_nothing_leaves_the_send_step():
    """Round 4, #10: another session's pane screenshot, which names no tab, voided the step; so would any computer action."""
    granted([CHAT])
    other = FOLDER / "S-other.jsonl"
    paths.write_json(paths.state() / "transcripts" / "S-other.json", {"path": str(other)})
    session = opened()
    ran(PANE + "computer", {"action": "screenshot"}, record=other)
    ran(KEYS, {"action": "screenshot", "tabId": 7}, record=other)
    ran(KEYS, {"action": "scroll", "tabId": 7, "coordinate": [10, 10], "scroll_direction": "down"}, record=other)
    assert sent(step()) is None and [e["how"] for e in today()] == [f"batch:{granted_digest()}:0"]


def granted_digest() -> str:
    return sends.batches()[0]["digest"][:12]


def test_another_sessions_action_on_the_tab_in_the_same_browser_voids_the_send_step():
    granted([CHAT])
    other = FOLDER / "S-other.jsonl"
    paths.write_json(paths.state() / "transcripts" / "S-other.json", {"path": str(other)})
    session = opened()
    ran(KEYS, {"action": "left_click", "coordinate": [5, 5], "tabId": 7, "action_summary": "Clicks the chat"}, record=other)
    assert session and "Another session's record" in (sent(step()) or "")


def test_a_call_a_hook_refused_does_not_void_the_send_step():
    granted([CHAT])
    opened()
    ident, at = f"toolu_{time.time_ns()}", datetime.now(timezone.utc).isoformat()
    _record({"type": "assistant", "timestamp": at, "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": ident, "name": SCRIPT, "input": {"action": "javascript_exec", "text": "document.title", "tabId": 7}}]}},
            {"type": "user", "timestamp": at, "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": ident, "is_error": True,
                 "content": f"PreToolUse:{SCRIPT} hook error: This page script runs on a Messenger site's tab"}]}})
    assert sent(step()) is None


def test_only_a_created_tab_result_makes_the_tab_this_sessions():
    """The extension's own words, read over 60 days of records: `Created new tab. Tab ID: N`, and every such result's
    `Executed on tabId` names that tab. A result without them (an error) made no tab."""
    granted([CHAT])
    ran("mcp__claude-in-chrome__tabs_create_mcp", {}, said="Error: no tab group\n\nTab Context:\n- Executed on tabId: 7")
    listed(E2EE, tab=7)
    assert "not made by this session's tabs_create" in (sent(step()) or "")


def test_the_newest_list_of_tabs_across_sessions_decides_a_tabs_page():
    """Round 4, #13: another session's older list showing tab 7 on a chat refused a script on the document this session's
    newer list shows there."""
    other = FOLDER / "S-other.jsonl"
    paths.write_json(paths.state() / "transcripts" / "S-other.json", {"path": str(other)})
    listed(E2EE, tab=7, record=other)
    time.sleep(0.01)
    session = listed("https://docs.google.com/document/d/1abc/edit", tab=7)
    assert guards.check(SCRIPT, {"action": "javascript_exec", "text": "document.title", "tabId": 7}, CONFIG, session=session) is None
    time.sleep(0.01)
    listed(E2EE, tab=7, record=other)  # now the other session's list is the newer
    reason = guards.check(SCRIPT, {"action": "javascript_exec", "text": "document.title", "tabId": 7}, CONFIG, session=session) or ""
    assert "another session's newer list" in reason and E2EE in reason, reason
    for tool, given in ((NAVIGATE_TOOL, {"url": "javascript:void(document.title)", "tabId": 7}),  # a javascript: address goes nowhere,
                        (CHROME, {"actions": [{"name": "navigate", "input": {"url": "javascript:void(0)", "tabId": 7}}]})):  # alone or in a batch
        reason = guards.check(tool, given, CONFIG, session=session) or ""
        assert "another session's newer list" in reason, (tool, reason)


NAVIGATE_TOOL = "mcp__claude-in-chrome__navigate"


def _run(*argv, program=SENDER, cwd=None) -> dict:
    """The sender's own run, as messages_send.py hands it to the guard: its file, its arguments and its folder."""
    return {"program": str(program), "argv": list(argv), "cwd": str(cwd or FOLDER)}


TO_A = ("--to", "+15550100", "--text-file", "reply.txt")


@pytest.mark.parametrize("command", ["cat {s}", "ls -la {s}", "grep -n TICKET {s}", "git diff -- {s}", "head -5 {s}"])
def test_a_command_that_only_names_the_senders_file_files_no_ticket(command):
    """Round 4, #6 and #12: any word named messages_send.py filed a ticket, and two fresh tickets held every send."""
    granted([TEXT])
    me = {**SESSION, "transcript_path": str(RECORD)}
    assert guards.check("Bash", {"command": command.format(s=SENDER)}, CONFIG, cwd=str(FOLDER), session=me) is None
    assert not list((paths.state() / "sends" / "sender").glob("*.json")) if (paths.state() / "sends" / "sender").is_dir() else True
    assert held(guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG, run=_run(*TO_A)))


def test_the_ticket_is_bound_to_its_command_and_taken_by_that_run_alone():
    granted([TEXT, {**TEXT, "to": "+15550101"}])
    me = {**SESSION, "transcript_path": str(RECORD)}
    assert guards.check("Bash", {"command": f"python3 {SENDER} {' '.join(TO_A)}"}, CONFIG, cwd=str(FOLDER), session=me) is None
    other_run = _run("--to", "+15550101", "--text-file", "reply.txt")
    assert held(guards.check_send("imessage_send", {"to": "+15550101", "text": REPLY}, CONFIG, run=other_run))  # another command's run
    assert held(guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG, run=_run(*TO_A, cwd=FOLDER / "elsewhere")))
    assert guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG, run=_run(*TO_A)) is None
    assert held(guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG, run=_run(*TO_A)))  # one run, one ticket
    assert [e["session"] for e in today()] == ["S-principal"]


def test_a_link_to_the_sender_is_the_sender_and_spends_only_its_own_sessions_entries():
    """Round 4, #6: `cat` of the sender filed a ticket for the principal's session, and another session's sender, run
    through a link, took it. A link is read as the sender now, so it files that session's own ticket, which spends none
    of the principal's entries; a cat files none."""
    granted([TEXT])
    (FOLDER / "reply_tool.py").symlink_to(SENDER)
    me = {**SESSION, "transcript_path": str(RECORD)}
    assert guards.check("Bash", {"command": f"cat {SENDER}"}, CONFIG, cwd=str(FOLDER), session=me) is None
    linked = "python3 reply_tool.py --to +15550100 --text-file reply.txt"
    assert guards.check("Bash", {"command": linked}, CONFIG, cwd=str(FOLDER), session=OTHER) is None
    assert held(guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG,
                                  run=_run(*TO_A, program=FOLDER / "reply_tool.py")))
    assert not today()


def test_each_sender_run_in_one_line_takes_a_ticket_of_its_own():
    """Round 4, #11: one ticket a command, so the second approved entry of a line waited for a code of its own."""
    granted([TEXT, {**TEXT, "to": "+15550101"}])
    me = {**SESSION, "transcript_path": str(RECORD)}
    second = ("--to", "+15550101", "--text-file", "b.txt")
    line = f"python3 {SENDER} {' '.join(TO_A)} && python3 {SENDER} {' '.join(second)}"
    assert guards.check("Bash", {"command": line}, CONFIG, cwd=str(FOLDER), session=me) is None
    assert guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG, run=_run(*TO_A)) is None
    PROCESS["line"] = f"/usr/bin/python3 {SENDER} {' '.join(second)}"  # the second run's own process (review round 5, #4)
    assert guards.check_send("imessage_send", {"to": "+15550101", "text": REPLY}, CONFIG, run=_run(*second)) is None


def test_another_sessions_read_of_the_sender_leaves_the_principals_send_alone():
    """Round 4, #12: another session's grep of the sender's source filed a second ticket, and the principal's send waited."""
    granted([TEXT])
    me = {**SESSION, "transcript_path": str(RECORD)}
    assert guards.check("Bash", {"command": f"grep -n TICKET {SENDER}"}, CONFIG, cwd=str(FOLDER), session=OTHER) is None
    assert guards.check("Bash", {"command": f"python3 {SENDER} {' '.join(TO_A)}"}, CONFIG, cwd=str(FOLDER), session=me) is None
    assert guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG, run=_run(*TO_A)) is None


def test_two_sessions_running_the_identical_command_in_one_folder_both_wait():
    granted([TEXT])
    me, line = {**SESSION, "transcript_path": str(RECORD)}, f"python3 {SENDER} {' '.join(TO_A)}"
    for session in (OTHER, me):
        assert guards.check("Bash", {"command": line}, CONFIG, cwd=str(FOLDER), session=session) is None
    assert held(guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG, run=_run(*TO_A)))


def test_the_sender_hands_the_guard_its_own_run(monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("messages_send_run", SENDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seen = {}
    monkeypatch.setattr(guards, "check_send", lambda tool, given, config, session=None, run=None: seen.update(run=run) or
                        "approve followed by the code abc123")
    result = module._send("+15550100", REPLY, "k" * 32, lambda: {"chat_id": "c"}, "imessage_send", lambda route: {"to": "+15550100",
                          "text": REPLY}, run={"argv": list(TO_A)})
    assert result["status"] == "needs-approval"
    assert seen["run"] == {"program": str(SENDER.resolve()), "argv": list(TO_A), "cwd": str(Path.cwd().resolve())}
    captured = {}
    monkeypatch.setattr(module, "send", lambda to, text, account=None, attachment=None, run=None: captured.update(run=run) or {"status": "refused"})
    (FOLDER / "reply.txt").write_text(REPLY, encoding="utf-8")
    monkeypatch.chdir(FOLDER)
    module.main(list(TO_A))
    assert captured["run"] == {"argv": list(TO_A)}


def _reported(sent_it: bool, call: str) -> None:
    report = json.dumps({"send": sends.SEND_MARK, "url": E2EE, "conversation": True, "box": "found", "words": sent_it,
                         "staged": 0, "marks": 0, "inline": 0, "controls": 1, "sent": sent_it, "after": "" if sent_it else REPLY})
    _record({"type": "user", "timestamp": datetime.now(timezone.utc).isoformat(), "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": call, "content": [{"type": "text", "text": json.dumps(report)}]}]}})


@pytest.mark.parametrize("outcome", ["sent", "declined", "unread"])
def test_the_days_ledger_lists_a_messenger_send_by_what_its_script_did(outcome):
    """Round 4's notes: the ledger listed a Messenger send when the guard let the step through, and "On your behalf"
    could name a message the script then declined to send."""
    granted([CHAT])
    opened()
    assert guards.check(CHROME, step(), CONFIG, session={**SESSION, "transcript_path": str(RECORD), "tool_use_id": "toolu_step"}) is None
    if outcome != "unread":
        _reported(outcome == "sent", "toolu_step")
    row = today()[0]
    assert row["how"].startswith("batch:") and row["sent"] is {"sent": True, "declined": False, "unread": None}[outcome]
    printed = cli_out("sends", "log")
    assert ("not sent" in printed) is (outcome == "declined") and ("unconfirmed" in printed) is (outcome == "unread"), printed


def test_a_batch_is_open_until_twelve_hours_after_the_principal_typed_its_code():
    """Round 4's notes: `sends status` named the grant plus 12 hours, while a spend needs the code typed in the last 12."""
    typed = time.time() - 600
    data = sends.open_batch(sends.read_batch(str(batch_file([CALL]))), {"code": "abc123", "asked": typed - 30, "at": typed}, "S-principal")
    assert abs(float(data["until"]) - (typed + sends.MAX_HOURS * 3600)) < 1 and float(data["granted"]) > typed
    assert [b["digest"] for b in sends.batches()] == [data["digest"]]  # still whole, and open


# --- review round 5 (2026-11-15) -----------------------------------------------------------------------------------
# #1: the moved rule did not count a page script that moves the tab, a form value, an upload, a navigate the agent
# marked `exact` or a move on a local app's page; #3: on a Messenger page it gave its own words, not that page's rule's;
# #4: a sender's ticket was taken by any identical run, one the guard never saw included; #5: a sub-agent's send step was
# read by its session's record alone; #6: the CHANGELOG's word on other messaging sites' pages.

SHOP = "https://shop.example.com/contact"
UNSAID = "document.querySelector('[aria-label*=\"enter to\"]').click()"  # a click on Send whose text names no send word
PLAIN_SEND = "document.querySelector('[aria-label=\"Press enter to send\"]').click()"
MOVERS = {"location-href-to-the-chat": "location.href = 'https://www.facebook.com/messages/e2ee/t/1000000001/'",
          "location-href": "location.href = 'https://bit.ly/3AbCdEf'", "location-assign": "location.assign('https://bit.ly/3AbCdEf')",
          "history-back": "history.back()", "history-go": "history.go(-1)",
          "a-link-followed-by-a-script": "document.querySelector('a[href*=\"m.me\"]').click()"}


def _then_send(*first, script=UNSAID) -> dict:
    return _batch_on(9, *first, ("computer", {"action": "wait", "duration": 3}), ("computer", {"action": "type", "text": "Words nobody approved."}),
                     ("javascript_tool", {"action": "javascript_exec", "text": script}))


@pytest.mark.parametrize("name", sorted(MOVERS))
def test_a_page_script_that_moves_the_tab_is_a_move(name):
    listed(SHOP, tab=9)
    reason = sent(_then_send(("javascript_tool", {"action": "javascript_exec", "text": MOVERS[name]})))
    assert reason and "may have moved" in reason and not held(reason), (name, reason)


@pytest.mark.parametrize("first", [("form_input", {"ref": "ref_12", "value": "Message us on Messenger"}),
                                   ("upload_image", {"imageId": "img_1", "ref": "ref_3"}),
                                   ("file_upload", {"paths": ["/tmp/a.txt"], "ref": "ref_4"})], ids=["form-input", "upload-image", "file-upload"])
def test_a_form_value_or_an_upload_is_a_move(first):
    listed(SHOP, tab=9)
    reason = sent(_then_send(first))
    assert reason and "may have moved" in reason and not held(reason), (first[0], reason)


def test_exact_is_the_guards_own_word_and_never_an_agents():
    listed(SHOP, tab=9)
    reason = sent(_then_send(("navigate", {"url": "https://bit.ly/3AbCdEf", "exact": True})))
    assert reason and "may have moved" in reason, "a navigate the agent marked exact moved the tab"
    playwright = "mcp__plugin_playwright_playwright__"  # the guard's own first step for a driven browser still places its page
    ran(playwright + "browser_navigate", {"url": "https://shop.example.com/"},
        said="### Ran Playwright code\n### Page\n- Page URL: https://shop.example.com/\n- Page Title: Shop\n")
    acts = {"function": "() => document.querySelector('#save').click()"}
    assert guards.check(playwright + "browser_evaluate", acts, CONFIG, session={**SESSION, "transcript_path": str(RECORD)}) is None


@pytest.mark.parametrize("first", [("navigate", {"url": "http://localhost:8000/new"}), CLICK_SAVE], ids=["a-local-navigate", "a-local-click"])
def test_after_a_navigate_or_a_click_on_a_local_app_its_scripts_run(first):
    """Review round 6, #4, as ruled: on a local app a navigate or a click moves nothing, so a read and a script that
    clicks Save both run; a local page that redirects the tab is on the open list."""
    listed(LOCAL, tab=9)
    for script in ("document.title", "document.querySelector('#save').click()"):
        assert sent(_batch_on(9, first, ("javascript_tool", {"action": "javascript_exec", "text": script}))) is None, script


@pytest.mark.parametrize("move", [("navigate", {"url": E2EE}), ("computer", {"action": "left_click", "coordinate": [5, 5],
                                                                            "action_summary": "Opens the thread"})], ids=["onto", "on"])
def test_a_script_after_a_move_onto_or_on_a_messenger_page_is_given_that_pages_rule(move):
    listed("https://docs.example.com/guide" if move[0] == "navigate" else E2EE, tab=9)
    reason = sent(_batch_on(9, move, ("javascript_tool", {"action": "javascript_exec", "text": "document.title"})))
    assert reason and "call of its own" not in reason and "get_page_text" in reason, reason


# The process a sender's guard call runs in, as `ps` shows it (#4): the sender's direct run of TO_A unless a test says
# otherwise; each test's own process is the harness's, as the hook's is.
PROCESS = {"line": ""}


@pytest.fixture(autouse=True)
def _sender_process(monkeypatch):
    PROCESS["line"] = f"/usr/bin/python3 {SENDER} {' '.join(TO_A)}"
    monkeypatch.setattr(sends, "_own_line", lambda: PROCESS["line"], raising=False)


def test_a_ticket_is_taken_only_by_the_process_whose_command_filed_it():
    granted([TEXT])
    me = {**SESSION, "transcript_path": str(RECORD)}
    assert guards.check("Bash", {"command": f"false && python3 {SENDER} {' '.join(TO_A)}"}, CONFIG, cwd=str(FOLDER), session=me) is None
    runpy = (f"python3 -c \"import runpy, sys; sys.argv = ['m'] + '{' '.join(TO_A)}'.split(); runpy.run_path('{SENDER}', "
             "run_name='__main__')\"")
    assert guards.check("Bash", {"command": runpy}, CONFIG, cwd=str(FOLDER), session=OTHER) is None  # no sender seen: no ticket
    PROCESS["line"] = runpy.replace('\\"', '"')  # the run the guard never saw: its own command line is runpy's
    assert held(guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG, run=_run(*TO_A)))
    assert not today()
    PROCESS["line"] = f"/usr/bin/python3 {SENDER} {' '.join(TO_A)}"  # the process of the command that filed it takes it
    assert guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG, run=_run(*TO_A)) is None


def test_a_ticket_filed_under_another_harness_is_taken_by_no_process_of_this_one(monkeypatch):
    granted([TEXT])
    me = {**SESSION, "transcript_path": str(RECORD)}
    monkeypatch.setattr(sends, "_harness", lambda: [999999, "Thu Jan  1 00:00:00 1970"], raising=False)  # another session's harness
    assert guards.check("Bash", {"command": f"python3 {SENDER} {' '.join(TO_A)}"}, CONFIG, cwd=str(FOLDER), session=me) is None
    assert held(guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG, run=_run(*TO_A)))
    assert not today()


def test_a_process_reads_its_own_command_line_and_its_harness_from_the_system():
    """What a sender's process reads of itself is the system's: its command line as `ps` shows it, and an ancestor its
    hook's harness is; a run that sets sys.argv changes neither."""
    if not sends._harness():  # a terminal's login above this run, or none: the binding files no ticket here
        pytest.skip("no harness process of this run's own above it")
    program = ("import json, sys; sys.argv = ['m', 'X' * 3]; from synthesis import sends; "
               "print(json.dumps({'line': sends._own_line(), 'ancestors': sorted(map(list, sends._ancestors()))}))")
    done = subprocess.run([sys.executable, "-c", program, "--marker"], capture_output=True, text=True, cwd=ROOT,
                          env={**__import__("os").environ, "PYTHONPATH": str(ROOT)}, timeout=60)
    assert done.returncode == 0, done.stderr[-800:]
    seen = json.loads(done.stdout)
    assert seen["line"].endswith("--marker") and not seen["line"].endswith("XXX"), seen["line"]
    harness = sends._harness()
    assert harness and list(harness) in seen["ancestors"], (harness, len(seen["ancestors"]))


def test_a_sub_agents_send_step_on_a_tab_it_made_reads_its_own_record():
    granted([CHAT])
    own = RECORD.parent / RECORD.stem / "subagents" / "agent-a1.jsonl"
    own.parent.mkdir(parents=True, exist_ok=True)
    made(7, own)
    listed(E2EE, 7, own)
    sub = {**SESSION, "transcript_path": str(RECORD), "agent_id": "a1"}
    assert guards.check(CHROME, step(), CONFIG, session=sub) is None
    assert [e["session"] for e in today()] == ["S-principal"]


def test_the_changelog_says_what_mains_rule_does_on_other_messaging_sites():
    entry = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").split("## [5.23.1]")[0]
    assert "on every other messaging site's page none runs but the shipped read-only ones" not in entry
    listed("https://www.linkedin.com/messaging/thread/2-abc/", tab=5)
    read = sent({"actions": [{"name": "javascript_tool", "input": {"action": "javascript_exec", "text": "document.title", "tabId": 5}}]})
    opened_ = sent({"actions": [{"name": "javascript_tool", "input": {"action": "javascript_exec", "tabId": 5,
                                                                         "text": "window?.open('https://www.linkedin.com/messaging/')"}}]})
    assert read is None and held(opened_), (read, opened_)


CRAFTED_MOVERS = {"location-by-a-built-name": "location[['hr', 'ef'].join('')] = 'https://m.me/patexample'",
                  "a-refresh-written-into-the-page": ("document.body.innerHTML = '<meta http-equiv=\"refresh\" "
                                                      "content=\"0;url=https://m.me/patexample\">'")}


@pytest.mark.xfail(strict=True, reason="on the open list in docs/runtime-integration.md: a move made to beat the reader")
@pytest.mark.parametrize("name", sorted(CRAFTED_MOVERS))
def test_open_a_move_the_page_script_reader_does_not_see(name):
    listed(SHOP, tab=9)
    assert sent(_then_send(("javascript_tool", {"action": "javascript_exec", "text": CRAFTED_MOVERS[name]}))), name


def test_a_real_process_of_the_command_takes_its_ticket_and_another_process_does_not():
    """Round 5, #4, with nothing standing in for the system: the guard files the ticket here, and a process this test
    starts takes it only when its own command line, as the system shows it, is the run's, under this harness."""
    if not sends._harness():  # a terminal's login above this run, or none: the binding files no ticket here
        pytest.skip("no harness process of this run's own above it")
    import os
    granted([TEXT])
    me = {**SESSION, "transcript_path": str(RECORD)}
    assert guards.check("Bash", {"command": f"python3 {SENDER} {' '.join(TO_A)}"}, CONFIG, cwd=str(FOLDER), session=me) is None
    program = ("import json; from synthesis import guards; print(json.dumps(guards.check_send('imessage_send', "
               f"{{'to': '+15550100', 'text': {REPLY!r}}}, {CONFIG!r}, run={{'program': {str(SENDER)!r}, 'argv': {list(TO_A)!r}, "
               f"'cwd': {str(FOLDER)!r}}})))")
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    other = subprocess.run([sys.executable, "-c", program, "--not-the-run"], capture_output=True, text=True, cwd=FOLDER, env=env, timeout=60)
    assert other.returncode == 0 and held(json.loads(other.stdout)), other.stderr[-600:]
    mine = subprocess.run([sys.executable, "-c", program, str(SENDER), *TO_A], capture_output=True, text=True, cwd=FOLDER, env=env, timeout=60)
    assert mine.returncode == 0 and json.loads(mine.stdout) is None, mine.stderr[-600:]
    assert [e["session"] for e in today()] == ["S-principal"]



# --- review round 6 (2026-11-15) -----------------------------------------------------------------------------------
# #4, as ruled: a page script moves a tab only when it can navigate (a location change, a click, a submit, `open`), not
# when it sets a value or writes by fetch; on a local app a navigate or a click moves nothing. #1: an alias of
# `location` and Object.assign(location, ...) move it. A local page that redirects the tab, and a page that redirects
# itself after the last list, are on the open list. #2: `ps` is the system's, by its full path. #3: the reference.

SAVE = "document.querySelector('#save').click()"


@pytest.mark.parametrize("tool, tab", [(CHROME, 11), (PANE + "browser_batch", "tab-1")], ids=["chrome", "pane"])
def test_on_a_local_app_a_click_then_a_script_that_clicks_save_runs(tool, tab):
    page = "http://localhost:3000/items"
    if tab == "tab-1":
        ran(PANE + "navigate", {"url": page}, said=f"navigated to {page}\n\n\nTab Context:\n- Executed on tabId: {tab}\n- "
            f"Available tabs:\n  • tabId {tab}: \"App\" ({page})")
    else:
        listed(page, tab=tab)
    click = ("computer", {"action": "left_click", "coordinate": [40, 60], "action_summary": "Opens the Add item form"})
    assert sent(_batch_on(tab, click, ("javascript_tool", {"action": "javascript_exec", "text": SAVE})), tool=tool) is None


@pytest.mark.parametrize("first", ["document.querySelector('#freq').value = 'weekly'",
                                   "fetch('/api/settings', {method: 'POST', body: 'freq=weekly'})"], ids=["a-value", "a-fetch-write"])
def test_a_script_that_sets_a_value_or_writes_by_fetch_is_no_move(first):
    listed("https://admin.example.com/settings", tab=9)
    batch = _batch_on(9, ("javascript_tool", {"action": "javascript_exec", "text": first}), ("javascript_tool", {"action": "javascript_exec", "text": SAVE}))
    reason = sent(batch)  # a write by fetch waits for its own code as a send, on any page; neither is a move
    assert reason is None if "value" in first else held(reason) and "may have moved" not in reason, reason


@pytest.mark.parametrize("mover", ["const l = location; l.href = 'https://www.facebook.com/messages/e2ee/t/1000000001/'",
                                   "const {location: l} = window; l.assign('https://bit.ly/3AbCdEf')",
                                   "Object.assign(location, {href: 'https://bit.ly/3AbCdEf'})", "window.open('https://m.me/patexample')",
                                   "location.href = 'https://m.me/patexample'"],
                         ids=["an-alias", "a-destructured-alias", "object-assign", "an-open", "a-location-change"])
@pytest.mark.parametrize("page", [SHOP, LOCAL], ids=["ordinary", "local"])
def test_a_script_that_can_navigate_is_a_move_on_any_page(mover, page):
    listed(page, tab=9)
    reason = sent(_then_send(("javascript_tool", {"action": "javascript_exec", "text": mover})))
    assert reason and "may have moved" in reason and not held(reason), (mover, reason)


@pytest.mark.parametrize("mover", ["location.href &&= 'https://m.me/patexample'", "location.pathname &&= '/messages/t/1000000001/'",
                                   "const l = location; l.href &&= 'https://m.me/patexample'", "const l = location; l.search ||= '?ref=1'"],
                         ids=["the-address", "a-part", "an-alias", "an-alias-part"])
def test_a_script_that_navigates_by_any_assignment_operator_is_a_move(mover):
    # Review round 7 of the page rule (Y3's class): every assignment operator sets the address, not `=` alone.
    listed(SHOP, tab=9)
    control = sent(_then_send(("javascript_tool", {"action": "javascript_exec", "text": mover.replace("&&=", "=").replace("||=", "=")})))
    assert control and "may have moved" in control, ("control: the = form", control)
    reason = sent(_then_send(("javascript_tool", {"action": "javascript_exec", "text": mover})))
    assert reason and "may have moved" in reason and not held(reason), (mover, reason)


def test_a_form_value_still_moves_the_tab_since_a_select_can_navigate():
    listed("https://admin.example.com/settings", tab=9)
    reason = sent(_batch_on(9, ("form_input", {"ref": "ref_4", "value": "Weekly"}), ("javascript_tool", {"action": "javascript_exec", "text": SAVE})))
    assert reason and "may have moved" in reason, reason


CRAFTED_REDIRECTS = {"a-local-page-that-redirects-the-tab": ("http://localhost:8000/", [("navigate", {"url": "http://localhost:8000/r.html"})]),
                     "a-page-that-redirects-itself": ("https://shop.example.com/redirect-in-5s", [])}


@pytest.mark.xfail(strict=True, reason="on the open list in docs/runtime-integration.md: a page that moves the tab by itself")
@pytest.mark.parametrize("name", sorted(CRAFTED_REDIRECTS))
def test_open_a_page_that_moves_the_tab_by_itself(name):
    page, first = CRAFTED_REDIRECTS[name]
    listed(page, tab=9)
    assert sent(_then_send(*first)), name  # the click names no word like send, as the reviewer's probe has it


def test_the_process_table_and_command_line_are_the_systems_whatever_ps_comes_first_on_path(tmp_path):
    import os
    fake = tmp_path / "fakeps"
    fake.mkdir()
    (fake / "ps").write_text("#!/bin/sh\necho '1 0 Thu Jan  1 00:00:00 1970 forged'\n", encoding="utf-8")
    (fake / "ps").chmod(0o755)
    program = "from synthesis import sends; print(len(sends._table())); print(sends._own_line())"
    done = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, cwd=ROOT, timeout=60,
                          env={**os.environ, "PYTHONPATH": str(ROOT), "PATH": f"{fake}:{os.environ.get('PATH', '')}"})
    rows, line = done.stdout.splitlines()[:2]
    assert int(rows) > 2 and "forged" not in line and line.endswith("sends._own_line())"), done.stdout[-300:]


def test_a_hook_under_shells_alone_names_no_harness(monkeypatch):
    """A hook whose ancestors are shells up to the system's first process (a run left behind by its terminal) names no
    harness, so it files no ticket and each send waits (review round 7, #2, as ruled: round 6 named the topmost shell,
    which two sessions under it share)."""
    import os
    monkeypatch.setattr(sends, "_table", lambda: {os.getppid(): (4242, "Sat Nov 15 10:00:00 2026", "zsh"),
                                                  4242: (1, "Sat Nov 15 09:00:00 2026", "sh")})
    assert sends._harness() == []


def test_the_reference_says_how_a_sender_ticket_is_bound():
    text = (ROOT / "skills" / "synthesis-message-guard" / "references" / "config.md").read_text(encoding="utf-8")
    ticket = text[text.index("The messages sender names no session"):][:3000]
    assert "so do identical runs of two sessions in one folder within the same minute" not in text
    assert "command line" in ticket and "harness" in ticket, ticket[:200]



# --- review round 7 (2026-11-15) -----------------------------------------------------------------------------------
# #2, as ruled: a hook whose walk finds no harness process of the session's own files no ticket. #3, as ruled: an entry
# spent by a call that is then held is given back, and one a call left with no answer spent stays spent.

HARNESS_TABLES = {  # (process table, whether hook A's harness is its session's own); hook A's parent 1000, session B's 2000
    "claude-code": ({1000: (900, "S9", "claude"), 900: (1, "S8", "zsh"), 2000: (901, "S7", "claude"), 901: (1, "S6", "zsh")}, True),
    "only-shells-under-one-topmost-shell": ({1000: (900, "S9", "sh"), 900: (1, "S8", "zsh"), 2000: (900, "S7", "zsh")}, False),
    "a-python-harness-twice-in-one-terminal-tab": ({1000: (800, "S9", "Python"), 800: (700, "S8", "zsh"), 700: (600, "S7", "login"),
                                                    600: (1, "S6", "Terminal"), 2000: (810, "S5", "Python"), 810: (700, "S4", "zsh")}, False),
}


@pytest.mark.parametrize("case", sorted(HARNESS_TABLES))
def test_a_ticket_is_filed_only_under_a_harness_of_the_sessions_own(monkeypatch, case):
    import os
    granted([TEXT])
    table, own = HARNESS_TABLES[case]
    monkeypatch.setattr(sends, "_table", lambda: dict(table))
    monkeypatch.setattr(os, "getppid", lambda: 1000)  # session A's hook
    assert sends._harness() == ([1000, "S9"] if own else []), case
    me = {**SESSION, "transcript_path": str(RECORD)}
    assert guards.check("Bash", {"command": f"false && python3 {SENDER} {' '.join(TO_A)}"}, CONFIG, cwd=str(FOLDER), session=me) is None
    monkeypatch.setattr(os, "getppid", lambda: 2000)  # session B's process, its command line the run's
    assert held(guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG, run=_run(*TO_A))) and not today(), case
    monkeypatch.setattr(os, "getppid", lambda: 1000)  # session A's own process under its harness
    verdict = guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG, run=_run(*TO_A))
    assert (verdict is None) if own else held(verdict), (case, verdict)


def _failing_log_once(monkeypatch):
    real, calls = sends.log, []

    def log(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise OSError("the day's ledger cannot be written")
        return real(*args, **kwargs)
    monkeypatch.setattr(sends, "log", log)


def test_an_entry_spent_by_a_call_that_is_then_held_is_given_back(monkeypatch):
    data = granted([CALL])
    me = {**SESSION, "transcript_path": str(RECORD)}
    _failing_log_once(monkeypatch)
    with pytest.raises(OSError):
        guards.check(SLACK, SAID, CONFIG, session=me)  # held after its entry was spent: the day's ledger failed
    assert (data["digest"], 0) not in sends._spends(net=True) and "0" not in next(b for b in sends.batches() if b["digest"] == data["digest"])["spent"]
    assert (data["digest"], 0) in sends._spends()  # the ledger keeps the spend's own line, beside the line that gives it back
    assert guards.check(SLACK, SAID, CONFIG, session=me) is None  # the identical retry spends it
    assert (data["digest"], 0) in sends._spends(net=True) and [r["how"] for r in today()] == [f"batch:{data['digest'][:12]}:0"]


@pytest.mark.parametrize("answer", ["held", "none"])
def test_under_the_hook_a_held_answer_gives_the_entry_back_and_no_answer_keeps_it(answer):
    data = granted([CALL])
    me = {**SESSION, "transcript_path": str(RECORD)}
    guards.hook_answers()  # this thread's call is the hook's: its records wait for its answer
    try:
        assert guards.check(SLACK, SAID, CONFIG, session=me) is None
        if answer == "held":
            guards.answered(False)
        else:
            guards.hook_answers()  # the next call: the earlier one, never answered, may have run
    finally:
        guards.answered(True)
    assert ((data["digest"], 0) in sends._spends(net=True)) is (answer == "none"), answer


def test_a_script_that_gives_an_entry_back_is_refused():
    """Giving an entry back makes it spendable again, so only the guard's own held call does it (review round 7, #3)."""
    command = "python3 -c \"from synthesis import sends; sends.batch_unspend('0' * 64, 0, 'm')\""
    reason = guards.check("Bash", {"command": command}, CONFIG, cwd=str(FOLDER), session={**SESSION, "transcript_path": str(RECORD)})
    assert reason and not held(reason), reason
