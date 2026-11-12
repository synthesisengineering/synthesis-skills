"""Waiting for an expected event is a task: the watcher is armed before the turn ends.

On 2026-11-11 a session told its principal a peer "should be asking you soon" and ended its turn. Board messages
reach a session only when a prompt is submitted, so nothing would have woken it; the principal noticed because the
peer told him. Its first watcher then polled `synthesis inbox`, which marks what it prints as read, and sat silent
for half an hour because the session was bound to no project and the message was addressed to one. These tests
pin what closes that: one command that waits and is its own record, a read that consumes nothing, a sender told
what will deliver the message, and a turn-end check that sends back a reply which announces a wait with nothing
armed. Committed before the code.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from synthesis import board, reply_check

ROOT = Path(__file__).resolve().parents[1]


def cli(*args, session="S1", timeout=30, **kwargs):
    return subprocess.run([sys.executable, "-m", "synthesis", *args], capture_output=True, text=True, cwd=ROOT, timeout=timeout,
                          env={**os.environ, "SYNTHESIS_SESSION": session}, **kwargs)


def start(*args, session="S1"):
    return subprocess.Popen([sys.executable, "-m", "synthesis", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            cwd=ROOT, env={**os.environ, "SYNTHESIS_SESSION": session})


@pytest.fixture
def two():
    board.touch("S1", project="alpha", harness="claude-code")
    board.touch("S2", project="beta", harness="claude-code")


# --- a read that consumes nothing ---------------------------------------------------------------------------------

def test_a_peek_lists_unread_messages_and_marks_none(two):
    board.message("S1", "S2", "the offer letter is signed")
    peek = cli("inbox", "--peek")
    assert peek.returncode == 0 and "the offer letter is signed" in peek.stdout and "S2" in peek.stdout
    assert "the offer letter is signed" in cli("inbox", "--peek").stdout              # still unread
    assert "the offer letter is signed" in cli("inbox").stdout                        # read here, and marked
    assert cli("inbox").stdout.strip() == "" and cli("inbox", "--peek").stdout.strip() == ""


# --- the watcher is one command, and it is its own registration ---------------------------------------------------

def test_a_wait_for_a_message_returns_at_once_for_one_already_unread_and_never_prints_its_body(two):
    board.message("S1", "S2", "SECRET BODY that a notification could cut off")
    done = cli("wait", "message", "--for", "20s")
    assert done.returncode == 0 and "1 unread" in done.stdout and board.short_name("S2") in done.stdout
    assert "SECRET BODY" not in done.stdout + done.stderr and "synthesis inbox" in done.stdout
    assert "SECRET BODY" in cli("inbox").stdout                                       # the wait consumed nothing


def test_a_wait_wakes_when_the_message_arrives_and_holds_a_record_while_it_runs(two):
    from synthesis import wait
    proc = start("wait", "message", "--for", "30s", "--every", "0.2s")
    deadline = time.time() + 10
    while not wait.live("S1") and time.time() < deadline:
        time.sleep(0.05)
    held = wait.live("S1")
    assert len(held) == 1 and held[0]["what"].startswith("a message") and held[0]["until"] > time.time()
    board.message("S1", "S2", "here it is")
    out, err = proc.communicate(timeout=15)
    assert proc.returncode == 0 and "unread" in out, (out, err)
    assert wait.live("S1") == []                                                      # the record goes when the wait ends


def test_a_wait_that_reaches_its_bound_exits_3_and_says_nothing_arrived(two):
    done = cli("wait", "message", "--for", "1s", "--every", "0.2s")
    assert done.returncode == 3 and "nothing arrived" in (done.stdout + done.stderr)
    from synthesis import wait
    assert wait.live("S1") == []


def test_a_wait_from_one_sender_is_not_woken_by_another(two):
    board.touch("S3", project="gamma", harness="codex")
    board.message("S1", "S3", "not the one awaited")
    done = cli("wait", "message", "--from", board.short_name("S2"), "--for", "1s", "--every", "0.2s")
    assert done.returncode == 3
    board.message("S1", "S2", "the one awaited")
    for sender in (board.short_name("S2"), "S2", "project:beta"):
        assert cli("wait", "message", "--from", sender, "--for", "5s").returncode == 0, sender


def test_a_session_bound_to_no_project_is_told_what_cannot_reach_it():
    board.touch("S9", harness="claude-code")
    done = cli("wait", "message", "--for", "1s", "--every", "0.2s", session="S9")
    assert done.returncode == 3 and "bound to no project" in done.stderr and "synthesis resume" in done.stderr


def test_a_record_whose_process_is_gone_is_not_live(two, isolated_home):
    from synthesis import wait
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    wait.record("S1", "a message", time.time() + 600, pid=dead.pid)
    assert wait.live("S1") == []
    wait.record("S1", "a message", time.time() - 1, pid=os.getpid())                  # and one past its bound is not either
    assert wait.live("S1") == []


def test_a_wait_for_a_file_wakes_when_it_appears_or_changes(two, tmp_path):
    target = tmp_path / "result.json"
    proc = start("wait", "file", str(target), "--for", "30s", "--every", "0.2s")
    time.sleep(0.6)
    assert proc.poll() is None
    target.write_text("{}", encoding="utf-8")
    out, _ = proc.communicate(timeout=15)
    assert proc.returncode == 0 and "result.json" in out
    proc = start("wait", "file", str(target), "--for", "30s", "--every", "0.2s")
    time.sleep(0.6)
    assert proc.poll() is None                                                       # there already, unchanged: still waiting
    os.utime(target, (time.time() + 5, time.time() + 5))
    proc.communicate(timeout=15)
    assert proc.returncode == 0


def test_a_wait_for_a_command_returns_when_it_succeeds_and_at_its_bound_when_it_does_not(two, tmp_path):
    marker = tmp_path / "ci-green"
    proc = start("wait", "run", "--every", "0.2s", "--for", "30s", "--", "test", "-f", str(marker))
    time.sleep(0.6)
    assert proc.poll() is None
    marker.touch()
    out, _ = proc.communicate(timeout=15)
    assert proc.returncode == 0 and "exited 0" in out
    assert cli("wait", "run", "--every", "0.2s", "--for", "1s", "--", "false").returncode == 3


def test_a_note_records_a_wait_the_harness_holds_and_the_list_shows_every_sessions(two):
    from synthesis import wait
    made = cli("wait", "note", "the CI run on the release branch", "--by", "a background task that exits when CI ends", "--for", "2h")
    assert made.returncode == 0 and "2 h" in made.stdout
    held = wait.live("S1")
    assert len(held) == 1 and held[0]["by"].startswith("a background task") and not held[0].get("pid")
    cli("wait", "note", "a reply from the vendor", "--by", "the hourly timer", "--for", "30m", session="S2")
    listed = cli("wait", "list").stdout
    assert "the CI run on the release branch" in listed and "a reply from the vendor" in listed
    assert board.short_name("S1") in listed and board.short_name("S2") in listed
    assert cli("wait", "note", "something", "--for", "2h").returncode == 2             # a note says what will wake the seat


def test_a_wait_cannot_run_past_twelve_hours_or_without_a_bound_it_can_read(two):
    assert cli("wait", "message", "--for", "13h").returncode == 2
    assert cli("wait", "message", "--for", "soon").returncode == 2


# --- the sender is told what will deliver the message --------------------------------------------------------------

def test_the_sender_is_told_what_will_deliver_the_message(two):
    idle = cli("msg", "S1", "are you there", session="S2")
    assert idle.returncode == 0 and "reads it at its next prompt" in idle.stdout
    cli("inbox")                                                                      # read, so the wait below has nothing yet
    proc = start("wait", "message", "--for", "30s", "--every", "0.2s")
    from synthesis import wait
    deadline = time.time() + 10
    while not wait.live("S1") and time.time() < deadline:
        time.sleep(0.05)
    assert wait.live("S1")
    watched = cli("msg", "S1", "now you are watching", session="S2")
    proc.communicate(timeout=15)
    assert "is watching" in watched.stdout and proc.returncode == 0
    nobody = cli("msg", "project:delta-unbound", "anyone", "--durable", session="S2")
    assert nobody.returncode != 0                                                     # no such project anywhere
    board.touch("S5", project="epsilon", harness="codex")
    s5 = board.load("S5")
    s5.seen = time.time() - board.STALE_SECONDS - 5
    board.save(s5)
    kept = cli("msg", "project:epsilon", "for whoever comes next", session="S2")
    assert kept.returncode == 0 and "no session is bound to" in kept.stdout and "synthesis resume epsilon" in kept.stdout


def test_a_wake_goes_through_the_recipients_own_harness_with_a_fixed_text(two):
    from synthesis import wait
    ran = []
    fake = lambda command, **kw: ran.append((command, kw.get("input"))) or subprocess.CompletedProcess(command, 0, "", "")  # noqa: E731
    codex = board.touch("T-codex", project="beta", harness="codex")
    said = wait.wake(codex, run=fake)
    assert ran[0][0][:2] == ["codex", "queue"] and "T-codex" in ran[0][0] and wait.NUDGE in ran[0][0] and "woken" in said
    muse = board.touch("T-muse", project="beta", harness="muse")
    wait.wake(muse, run=fake)
    assert ran[1][0][:3] == ["muse", "session-message", "send"] and "T-muse" in ran[1][0] and ran[1][1] == wait.NUDGE
    claude = board.touch("T-claude", project="beta", harness="claude-code")
    assert "no command" in wait.wake(claude, run=fake) and len(ran) == 2              # nothing was run for it
    assert "approve" not in wait.NUDGE.lower() and "synthesis inbox" in wait.NUDGE    # the text carries no instruction but where to look


# --- the turn-end check --------------------------------------------------------------------------------------------

ANNOUNCED = [
    "The review is running; I'll pick it up once it lands.",
    "Their answer should come shortly, and then I will merge.",
    "Waiting for the vendor's confirmation before the next step.",
    "CI is still going. When it finishes I'll cut the release.",
]


@pytest.mark.parametrize("reply", ANNOUNCED)
def test_a_reply_that_announces_a_wait_with_nothing_armed_is_sent_back_once(two, reply):
    payload = {"last_assistant_message": reply, "session_id": "S1"}
    reason = reply_check.check(payload, {})
    assert reason and "nothing is armed" in reason and "synthesis wait" in reason
    assert "ask" in reason and "nothing wakes this seat" in reason                    # the three ways out
    assert reply_check.check({**payload, "stop_hook_active": True}, {}) is None


@pytest.mark.parametrize("reply", ANNOUNCED)
def test_an_armed_wait_passes(two, reply):
    from synthesis import wait
    wait.record("S1", "the review", time.time() + 600, pid=os.getpid())
    assert reply_check.check({"last_assistant_message": reply, "session_id": "S1"}, {}) is None
    assert reply_check.check({"last_assistant_message": reply, "session_id": "S2"}, {}) is not None   # another session's watcher is not this one's


@pytest.mark.parametrize("reply", [
    "Waiting for your answer on the release bar.",
    "The draft is ready. Once you approve it, I send it.",
    "Two options are below; which do you want?",
    "I will pick it up once you type the code.",
    "The rule bans \"waiting for\" with nothing armed, so I removed the line.",       # a phrase that is only named
    "Round 8 found nothing. The release is done and installed.",                      # no wait at all
])
def test_a_wait_on_the_principals_own_next_message_or_no_wait_at_all_passes(two, reply):
    assert reply_check.check({"last_assistant_message": reply, "session_id": "S1"}, {}) is None


def test_the_phrases_are_config_and_an_autopilot_run_with_its_plan_is_armed(two, tmp_path, isolated_home):
    reply = "The export is queued; back when the batch closes."
    assert reply_check.check({"last_assistant_message": reply, "session_id": "S1"}, {}) is None
    assert reply_check.check({"last_assistant_message": reply, "session_id": "S1"}, {"wait_phrases": ["back when"]}) is not None
    pointer = isolated_home / "state" / "autopilot" / "S1.json"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n\nStatus: running\nOwner session: S1\n", encoding="utf-8")
    pointer.write_text(json.dumps({"plan": str(plan)}), encoding="utf-8")
    assert reply_check.check({"last_assistant_message": ANNOUNCED[0], "session_id": "S1"}, {}) is None


# --- a session with no project is told what waits ------------------------------------------------------------------

def test_a_session_bound_to_no_project_is_told_at_its_start_which_projects_have_mail_waiting(isolated_home):
    board.touch("S2", project="beta", harness="claude-code")
    (isolated_home / "config.json").parent.mkdir(parents=True, exist_ok=True)
    board.touch("S7", project="zeta", harness="claude-code")
    gone = board.load("S7")
    gone.seen = time.time() - board.STALE_SECONDS - 5
    board.save(gone)
    board.message("project:zeta", "S2", "the numbers you asked for")
    out = subprocess.run([sys.executable, "-m", "synthesis.hook", "session-start"], input=json.dumps({"session_id": "S8", "cwd": str(ROOT)}),
                         capture_output=True, text=True, cwd=ROOT).stdout
    said = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "bound to no project" in said and "zeta" in said and "synthesis resume zeta" in said
    bound = subprocess.run([sys.executable, "-m", "synthesis.hook", "session-start"], input=json.dumps({"session_id": "S2", "cwd": str(ROOT)}),
                           capture_output=True, text=True, cwd=ROOT).stdout
    assert "bound to no project" not in bound


# --- the doctor ----------------------------------------------------------------------------------------------------

def test_the_doctor_runs_the_turn_end_check_on_a_canned_reply(monkeypatch):
    from synthesis import doctor
    assert doctor.check_wait_check().status == "ok"
    monkeypatch.setattr(reply_check, "check", lambda payload, config: None)
    failed = doctor.check_wait_check()
    assert failed.status == "fail" and "not sent back" in failed.detail
