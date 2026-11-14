"""One approval for a reviewed batch of sends (design note M37 part 4, 2026-11-14; review round 1 of 5.23.0).

A seat drafts replies in batches of about twenty; the principal reads every text and recipient in the hold and types
one code for the batch's digest. Each entry then sends once, word for word, within 12 hours, from the session that
ran the granted command, and every spend checks that session's record for the principal's code again. A connector
entry binds the whole call; a messages entry the local sender's recipient, chat, service and text; a browser entry a
send verified first: the shipped composer check on the tab, then one Return or Send click on that same tab. Every
other check runs first, and anything that differs falls back to the code per call.
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
    """A batch the principal opened: the guard's hold, their code typed in this session, the command run here."""
    file = batch_file(entries, name)
    APPROVE(guards.check("Bash", {"command": f"synthesis sends batch {file}"}, CONFIG, cwd=str(FOLDER)))
    assert cli.main(["--session", "S-principal", "sends", "batch", str(file)]) == 0
    return next(b for b in sends.batches() if b["batch"] == name)


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "synthesis.cli", *args], capture_output=True, text=True, cwd=ROOT,
                          stdin=subprocess.DEVNULL)


def _record(*lines) -> None:
    with RECORD.open("a", encoding="utf-8") as handle:
        handle.writelines(json.dumps(line) + "\n" for line in lines)


def checked(url=E2EE, text=REPLY, tab=7, focused=True, staged=0, server="mcp__claude-in-chrome", script=None, age=1.0,
            error=False, report=None) -> dict:
    """The shipped composer check run on a tab, and its result, in the session's record; the session."""
    ident, at = f"toolu_{time.time_ns()}", (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat()
    found = report or json.dumps({"check": "synthesis-composer-1", "url": url, "text": text, "focused": focused,
                                  "staged": staged, "boxes": 1})
    tabs = f"\n\nTab Context:\n- Executed on tabId: {tab}\n- Available tabs:\n  • tabId {tab}: \"Messenger\" (\"{url}\")"
    _record({"type": "assistant", "timestamp": at, "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": ident, "name": f"{server}__javascript_tool",
                 "input": {"action": "javascript_exec", "text": script or sends.COMPOSER_CHECK, "tabId": tab}}]}},
            {"type": "user", "timestamp": at, "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": ident, "is_error": error, "content": [{"type": "text", "text": found + tabs}]}]}})
    return {**SESSION, "transcript_path": str(RECORD)}


def other_call(name=KEYS, given=None, tab=7) -> None:
    ident, at = f"toolu_{time.time_ns()}", datetime.now(timezone.utc).isoformat()
    _record({"type": "assistant", "timestamp": at, "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": ident, "name": name, "input": given or {"action": "screenshot", "tabId": tab}}]}},
            {"type": "user", "timestamp": at, "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": ident, "content": [{"type": "text", "text": "Done"}]}]}})


def send(session, given=None, tool=KEYS, config=CONFIG):
    return guards.check(tool, given or RETURN, config, session=session)


def read_calendar() -> None:
    at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    ident = f"toolu_{time.time_ns()}"
    _record({"type": "assistant", "timestamp": at, "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": ident, "name": "mcp__workspace__get_events", "input": {}}]}},
            {"type": "user", "timestamp": at, "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": ident, "content": "[]"}]}})


def held(reason) -> bool:
    return bool(reason) and "approve followed by the code" in reason


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
        assert held(guards.check_send(tool, given, CONFIG)), (tool, given)
    assert guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG) is None
    assert guards.check_send("messages_send", members, CONFIG) is None
    one = {"to": ["+15550103"], "service": "iMessage", "text": "On my way.", "chat": "chat-7"}
    assert guards.check_send("messages_send", one, CONFIG) is None
    with pytest.raises(ValueError, match="entry 1"):
        sends.read_batch(str(batch_file([{**GROUP, "members": ["+15550100", "+15550100"]}])))


@pytest.mark.parametrize("attachment", [{"path": "plan.pdf"}, {"url": "https://files.example.com/shared/plan.pdf", "filename": "plan.pdf"}])
def test_a_call_the_connector_fetches_or_reads_a_file_for_is_never_covered(attachment):
    """Review #16: a file fetched from a url when the call runs, up to 12 hours after the principal read the batch."""
    mail = {"to": "pat@example.com", "subject": "Plan", "body": "<p>The plan is attached.</p>", "body_format": "html",
            "attachments": [attachment]}
    granted([{"tool": MAIL, "input": mail}])
    assert held(guards.check_send(MAIL, mail, CONFIG, SESSION))


# --- the browser: the box is checked, then one Return or Send click on that tab ---------------------------------


def test_the_cli_prints_the_composer_check_and_the_guard_lets_it_run():
    assert _cli("sends", "composer-check").stdout.strip() == sends.COMPOSER_CHECK
    other_call()  # a page in the record: the call below runs on a messaging site's tab
    assert guards.check(SCRIPT, {"action": "javascript_exec", "text": sends.COMPOSER_CHECK, "tabId": 7}, CONFIG,
                        session=checked()) is None


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
def test_a_browser_entry_goes_only_after_a_check_of_its_conversations_box(entry_to, url, goes):
    granted([{**CHAT, "to": entry_to}])
    reason = send(checked(url=url))
    assert (reason is None) is goes, reason
    assert goes or held(reason)


def test_a_verified_send_goes_once_and_its_ledger_line_names_the_entry():
    data = granted([CHAT])
    assert send(checked()) is None
    assert today()[-1]["how"] == f"batch:{data['digest'][:12]}:0"
    assert held(send(checked()))  # spent


@pytest.mark.parametrize("what", ["text", "focus", "staged", "old", "between", "script", "error", "tab", "server",
                                  "unreported", "two reports"])
def test_a_check_that_does_not_show_exactly_the_entry_ready_in_a_focused_box_leaves_the_code(what):
    """Review #1, #2, #4 and #15: the guard trusted which tab, where the focus was, an emptied box and an earlier paste.
    Now the box itself is read first, on the send's own tab and browser, in the last 60 seconds, with nothing between."""
    granted([CHAT])
    session = (checked(text="P.S. " + REPLY) if what == "text" else checked(focused=False) if what == "focus" else
               checked(staged=1) if what == "staged" else checked(age=61) if what == "old" else
               checked(script=sends.COMPOSER_CHECK.replace("innerText", "textContent")) if what == "script" else
               checked(error=True) if what == "error" else checked(tab=8) if what == "tab" else
               checked(server="mcp__Claude_Browser") if what == "server" else
               checked(report="Done") if what == "unreported" else
               checked(report=json.dumps({"check": "synthesis-composer-1", "url": E2EE, "text": REPLY, "focused": True,
                                          "staged": 0}) * 2) if what == "two reports" else checked())
    if what == "between":
        other_call()
    assert held(send(session)), what
    assert send(checked()) is None  # the entry was not spent by it


@pytest.mark.parametrize("given", [
    {**RETURN, "repeat": 2}, {**RETURN, "text": "cmd+Return"}, {**RETURN, "text": "Return Return"},
    {"action": "right_click", "ref": "ref_5", "tabId": 7, "action_summary": "Sends the reply"},
    {"action": "double_click", "ref": "ref_5", "tabId": 7, "action_summary": "Clicks Send"},
    {"action": "left_click", "ref": "ref_5", "tabId": 7, "action_summary": "Clicks Send", "modifiers": "shift"},
    {"action": "key", "text": "Return", "action_summary": "Sends the reply"},  # no tab named
])
def test_the_send_is_one_plain_return_or_send_click_on_the_checked_tab(given):
    """Review #3: Return with repeat 2 passed as the single send."""
    granted([CHAT])
    assert held(send(checked(), given)), given
    assert send(checked(), {"action": "left_click", "ref": "ref_5", "tabId": 7, "action_summary": "Clicks Send"}) is None


def test_typing_and_sending_in_one_call_never_spends_an_entry():
    """Review #1 to #4 and #9: clearing, focus, typing and Return in one call let the guard trust what it cannot see."""
    granted([CHAT])
    one_call = {"actions": [{"name": "computer", "input": {"action": "key", "text": "cmd+a", "tabId": 7}},
                            {"name": "computer", "input": {"action": "key", "text": "Backspace", "tabId": 7}},
                            {"name": "computer", "input": {"action": "type", "text": REPLY, "tabId": 7}},
                            {"name": "computer", "input": {"action": "key", "text": "Return", "tabId": 7}}]}
    assert held(send(checked(), one_call, tool=CHROME))
    single = {"actions": [{"name": "computer", "input": RETURN}]}  # a batch of one plain Return is the send itself
    assert send(checked(), single, tool=CHROME) is None


def test_an_entry_covers_only_its_own_kind_of_send():
    granted([CHAT])
    assert held(guards.check(SLACK, SAID, CONFIG, session=SESSION))
    assert held(guards.check_send("imessage_send", {"to": "+15550100", "text": REPLY}, CONFIG))
    assert held(send(checked(url=PLAIN)))
    assert send(checked()) is None


# --- every other check still runs first --------------------------------------------------------------------------


def test_an_entry_that_names_a_time_still_needs_a_fresh_calendar_read():
    config, words = {**CONFIG, "fresh_calendar": {}}, "Tuesday at 3:30 pm works for me."
    timed = {**SAID, "message": words}
    granted([{"tool": SLACK, "input": timed}, {**CHAT, "text": words}])
    session = {**SESSION, "transcript_path": str(RECORD)}
    for reason in (guards.check(SLACK, timed, config, session=session), send(checked(text=words), config=config)):
        assert held(reason) and "names a time" in reason
    read_calendar()
    assert guards.check(SLACK, timed, config, session=session) is None
    assert send(checked(text=words), config=config) is None


def test_an_entry_released_by_the_code_for_its_time_is_spent_with_it():
    config, timed = {**CONFIG, "fresh_calendar": {}}, {**SAID, "message": "Tuesday at 3:30 pm works for me."}
    granted([{"tool": SLACK, "input": timed}])
    session = {**SESSION, "transcript_path": str(RECORD)}
    APPROVE(guards.check(SLACK, timed, config, session=session))
    assert guards.check(SLACK, timed, config, session=session) is None
    read_calendar()
    assert held(guards.check(SLACK, timed, config, session=session))


def test_the_register_scan_still_refuses_a_forbidden_phrase_in_an_entry_and_in_the_box():
    words = "Sorry for the delay, Tuesday works."
    granted([{"tool": SLACK, "input": {**SAID, "message": words}}, {**CHAT, "text": words}])
    assert "delay-apology" in guards.check(SLACK, {**SAID, "message": words}, CONFIG, session=SESSION)
    assert "delay-apology" in send(checked(text=words))
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
    signed = {**SAID, "message": "Status is green. Helperbot here"}
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
