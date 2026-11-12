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
import re
import signal
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


def quiet(session_id):
    """Last seen past the threshold, as a session that ended hours ago is."""
    gone = board.load(session_id)
    gone.seen = time.time() - board.STALE_SECONDS - 5
    board.save(gone)


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


def test_a_command_still_running_at_the_bound_is_stopped_and_the_wait_exits_3(two, tmp_path, monkeypatch, capsys):
    """2026-11-12, a review: `wait run --for 1s` on a check that took two minutes exited 0 two minutes later. The check
    was given no time limit, and its exit code was read before the bound was."""
    from synthesis import wait
    clock, given, stopped = [time.time()], [], []
    began = clock[0]

    class Check:                                                                      # the process of a check that takes two minutes, then exits 0
        def __init__(self, command, **kwargs):
            self.command = command

        def wait(self, timeout=None):
            given.append(timeout)
            if timeout is not None and timeout < 120:
                clock[0] += timeout
                raise subprocess.TimeoutExpired(self.command, timeout)
            clock[0] += 120
            return 0
    with monkeypatch.context() as fake:
        fake.setattr(time, "time", lambda: clock[0])
        fake.setattr(time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
        fake.setattr(subprocess, "Popen", Check)
        fake.setattr(wait, "_stop", stopped.append)                                   # no signal is sent for a process that is not there
        assert wait.main(["run", "--for", "1s", "--", "ci-check"], "S1") == 3
        said = capsys.readouterr()
        assert "nothing arrived in 1 s" in said.err and "exited 0" not in said.out
        assert given == [pytest.approx(1)] and clock[0] - began == pytest.approx(1)   # one try, given the time left, stopped at the bound
        assert len(stopped) == 1 and stopped[0].command == ["ci-check"]
        fake.setattr(Check, "wait", lambda self, timeout=None: clock.__setitem__(0, clock[0] + 120) or 0)   # it ends after the bound: no success
        assert wait.main(["run", "--for", "1s", "--", "ci-check"], "S1") == 3 and "exited 0" not in capsys.readouterr().out
        assert wait.live("S1") == []
    pid, began = tmp_path / "pid", time.time()
    done = cli("wait", "run", "--for", "2s", "--", sys.executable, "-c",
               "import os, sys, time; open(sys.argv[1], 'w').write(str(os.getpid())); time.sleep(30)", str(pid))
    assert done.returncode == 3 and "nothing arrived in 2 s" in done.stderr and time.time() - began < 15
    with pytest.raises(ProcessLookupError):                                           # the check was stopped, not left to run on
        os.kill(int(pid.read_text()), 0)


# --- a try is stopped with every process it started ----------------------------------------------------------------

# A check that starts a worker, as a script that puts a job in the background does. Once the worker is up it writes
# down its own process and the worker's, one try to a line, stays for the seconds it is given, then fails.
CHECK = ("import os, subprocess, sys, time; "
         "worker = subprocess.Popen([sys.executable, '-c', sys.argv[2], sys.argv[1]], stdout=subprocess.PIPE); "
         "worker.stdout.readline(); open(sys.argv[1], 'a').write(f'{os.getpid()} {worker.pid}\\n'); "
         "time.sleep(float(sys.argv[3])); sys.exit(1)")
IDLE = "print('up', flush=True); import time; time.sleep(30)"
TIDY = ("import signal, sys, time; "                                                  # asked to end, it says so and ends
        "signal.signal(signal.SIGTERM, lambda *_: (open(sys.argv[1] + '.asked', 'w').close(), sys.exit(0))); "
        "print('up', flush=True); time.sleep(30)")
DEAF = "import signal; signal.signal(signal.SIGTERM, signal.SIG_IGN); "               # asked to end, it stays


def left(mark):
    """The processes still running whose command line names a test's own file: a wait, its check and each worker."""
    listed = subprocess.run(["ps", "-A", "-ww", "-o", "pid=", "-o", "stat=", "-o", "command="], capture_output=True, text=True)
    return [int(row.split()[0]) for row in listed.stdout.splitlines() if str(mark) in row and not row.split()[1].startswith("Z")]


def running_on(mark, within=5):
    """What is still running once it has had `within` seconds to end."""
    deadline = time.time() + within
    while left(mark) and time.time() < deadline:
        time.sleep(0.1)
    return left(mark)


@pytest.fixture
def pids(tmp_path):
    """The file a check writes its processes to. Its path is on the command line of the check and of each worker,
    which is how a test finds what still runs, and how whatever a failing test left running is killed when it ends."""
    file = tmp_path / "pids"
    try:
        yield file
    finally:
        for pid in left(file):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_a_worker_the_check_started_is_stopped_with_it_at_the_bound(two, pids):
    """2026-11-12, a second review: `wait run --for 1s` on a check that had started a 30-second worker and then slept
    exited 3 at the bound with the check stopped and its worker still running. Only the check itself was stopped."""
    began = time.time()
    done = cli("wait", "run", "--for", "2s", "--", sys.executable, "-c", CHECK, str(pids), TIDY, "30")
    assert done.returncode == 3 and "nothing arrived in 2 s" in done.stderr and time.time() - began < 15
    assert len(pids.read_text().split()) == 2 and running_on(pids) == []              # the check and its worker: neither runs on
    assert Path(f"{pids}.asked").exists()                                             # and the worker was asked to end before anything was killed


def test_what_does_not_end_when_asked_is_killed(two, pids):
    began = time.time()
    done = cli("wait", "run", "--for", "3s", "--", sys.executable, "-c", DEAF + CHECK, str(pids), DEAF + IDLE, "30")
    assert done.returncode == 3 and "nothing arrived in 3 s" in done.stderr and time.time() - began < 20
    assert len(pids.read_text().split()) == 2 and running_on(pids) == []


def test_a_try_that_fails_leaves_nothing_it_started_running(two, pids):
    """A check that starts a worker and fails at once is run again and again: no try's worker is left behind it, so
    when the bound comes nothing the command started is running."""
    done = cli("wait", "run", "--every", "0.4s", "--for", "2s", "--", sys.executable, "-c", CHECK, str(pids), IDLE, "0")
    assert done.returncode == 3 and "nothing arrived in 2 s" in done.stderr
    assert len(pids.read_text().splitlines()) >= 2 and running_on(pids) == []         # several tries, each with a worker of its own


def test_a_wait_that_is_told_to_end_stops_the_try_it_is_running(two, pids):
    """A try runs in a process group of its own, so a signal sent to the wait and its group no longer reaches the try
    by itself: the wait stops the try before it goes."""
    from synthesis import wait
    proc = start("wait", "run", "--for", "60s", "--", sys.executable, "-c", CHECK, str(pids), IDLE, "30")
    deadline = time.time() + 10
    while not (pids.exists() and pids.read_text().strip()) and time.time() < deadline:
        time.sleep(0.05)
    assert len(pids.read_text().split()) == 2                                         # the check and its worker are up
    proc.terminate()
    proc.communicate(timeout=15)
    assert proc.returncode not in (0, 3) and running_on(pids) == []                   # no success, no bound: it was ended, and so was its try
    assert wait.live("S1") == []


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


def test_a_session_stays_addressable_for_the_whole_bound_of_its_wait(two, monkeypatch, capsys):
    """2026-11-12, a review: nine hours into a twelve-hour wait, a message to the waiting session was refused as sent
    to a stale one. Its watcher was running, and nothing counted that."""
    from synthesis import cli, wait
    for other in ("S3", "S4"):
        board.touch(other, project="gamma", harness="claude-code")
    assert wait.main(["note", "the CI run", "--by", "the harness's timer", "--for", "12h"], "S4") == 0
    clock, sent = [time.time()], []
    began, seen = clock[0], board.load("S1").seen

    def sleep(seconds):                                                               # nine hours on, between two looks, a peer writes
        clock[0] += seconds
        if clock[0] - began >= 9 * 3600 and not sent:
            sent.append(cli.main(["--session", "S2", "msg", "S1", "the review is in"]))
            sent.append(cli.main(["--session", "S2", "msg", "project:alpha", "and so is its summary"]))
    monkeypatch.setattr(time, "time", lambda: clock[0])
    monkeypatch.setattr(time, "sleep", sleep)
    ended = wait.main(["message", "--for", "12h", "--every", "5m"], "S1")
    said = capsys.readouterr()
    assert sent == [0, 0], said.err                                                   # neither was refused as sent to a stale session
    assert "sent to S1: it is watching" in said.out and "sent to project:alpha: it is watching" in said.out
    assert ended == 0 and "(2 unread)" in said.out and clock[0] - began < 10 * 3600
    assert board.resolve("S4").session == "S4"                                        # a wait the harness holds keeps its seat addressable too
    for over in ("S1", "S3"):                                                         # S1's wait is over, S3 never had one: both quiet nine hours
        with pytest.raises(board.AddressError, match="stale"):
            board.resolve(over)
    assert board.load("S1").seen == seen                                              # and a watcher never writes its session's record


# --- the sender is told what will deliver the message --------------------------------------------------------------

def test_a_word_of_a_message_is_not_taken_for_the_command(two):
    """The first review: `synthesis msg S1 wait` was handed to the wait command, and nothing was sent."""
    for text in ("wait", "doctor", "worktree"):
        sent = cli("msg", "S1", text, session="S2")
        assert sent.returncode == 0 and "reads it at its next prompt" in sent.stdout, (text, sent.stderr)
    assert [m["text"] for m in board.inbox("S1")] == ["wait", "doctor", "worktree"]
    assert cli("--session", "S1", "wait", "note", "the build", "--by", "a timer").returncode == 0     # and the commands still run


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


def test_a_durable_message_sent_with_wake_nudges_each_live_session_on_the_project_once(monkeypatch, capsys):
    """2026-11-12, a review: `msg project:<id> --durable --wake` woke no one. A durable message names no one session,
    and the wake was taken from the one session a message names."""
    from synthesis import cli, wait
    ran, wake = [], wait.wake
    fake = lambda command, **kw: ran.append(command) or subprocess.CompletedProcess(command, 0, "", "")  # noqa: E731
    monkeypatch.setattr(wait, "wake", lambda target: wake(target, run=fake))          # no harness command is ever run
    for name, harness in (("SENDER", "codex"), ("T-codex", "codex"), ("T-muse", "muse"), ("T-claude", "claude-code"), ("T-quiet", "codex")):
        board.touch(name, project="alpha", harness=harness)
    board.touch("T-elsewhere", project="beta", harness="codex")
    quiet("T-quiet")
    send = ["--session", "SENDER", "msg", "project:alpha"]
    assert cli.main(send + ["the release is cut", "--durable", "--wake"]) == 0
    line = capsys.readouterr().out
    assert [c[:2] for c in ran] == [["codex", "queue"], ["muse", "session-message"]] and "T-codex" in ran[0] and "T-muse" in ran[1]
    assert line.startswith("sent to project:alpha: it is kept for every session that works on alpha") and line.count("\n") == 1
    assert line.count("woken through its own harness") == 2 and "no command wakes a claude-code session" in line
    assert all(line.count(board.short_name(name)) == 1 for name in ("T-codex", "T-muse", "T-claude"))
    assert not any(board.short_name(name) in line for name in ("SENDER", "T-quiet", "T-elsewhere"))   # itself, a stale one, another project's
    assert all(len(board.inbox(name, "alpha")) == 1 for name in ("T-codex", "T-muse", "T-claude", "T-quiet"))   # and each still reads it
    assert cli.main(send + ["and the notes are filed", "--durable"]) == 0 and len(ran) == 2   # no --wake, no nudge
    wait.record("T-muse", "a message", time.time() + 600, pid=os.getpid(), every=300)   # T-muse now watches: it is told so and left alone
    capsys.readouterr()
    assert cli.main(send + ["and the tag is pushed", "--durable", "--wake"]) == 0 and [c[0] for c in ran[2:]] == ["codex"]
    assert f"{board.short_name('T-muse')}: it is watching and checks every 5 min" in capsys.readouterr().out
    assert cli.main(["--session", "SENDER", "msg", "T-codex", "one more thing", "--wake"]) == 0 and len(ran) == 4   # one session, one nudge
    assert "reads it at its next prompt; woken through its own harness" in capsys.readouterr().out


def test_the_sender_is_told_how_often_a_watcher_looks(two, monkeypatch, capsys):
    """2026-11-12, a review: "it is watching and wakes within seconds" was printed for a watcher started with
    `--every 5m`, which finds mail only at its next look, up to five minutes on."""
    from synthesis import cli, wait
    told = []

    def sleep(seconds):                                                               # while the watcher sleeps between two looks, a peer sends
        told.append((wait.live("S1")[0].get("every"), cli.main(["--session", "S2", "msg", "S1", f"note {len(told)}"])))
    monkeypatch.setattr(time, "sleep", sleep)
    for every, line in (("5m", "it is watching and checks every 5 min"), ("90s", "it is watching and checks every 1 min 30 s"),
                        ("2s", "it is watching and wakes within seconds")):
        assert wait.main(["message", "--for", "30m", "--every", every], "S1") == 0
        out = capsys.readouterr().out
        assert f"sent to S1: {line}\n" in out, (every, out)
        board.inbox("S1", "alpha", mark_read=True)                                    # read, so the next watcher starts with nothing
    assert told == [(300, 0), (90, 0), (2, 0)]                                        # how often it looks is in the wait's record


# --- the turn-end check --------------------------------------------------------------------------------------------

ANNOUNCED = [
    "The review is running; I'll pick it up once it lands.",
    "Their answer should come shortly, and then I will merge.",
    "Waiting for the vendor's confirmation before the next step.",
    "CI is still going. When it finishes I'll cut the release.",
    "The registry update is the only action left; I'm waiting for the holder's reply as directed.",
    "Only the calendar worker is still running. When it finishes, I'll send the plan.",
    "I am waiting on the peer's answer before I continue.",
    "I'll wait for the build and then merge.",
    "Done so far: the draft.\n- Still waiting on the second reviewer's verdict.",
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
    # Ten days of real final replies (2026-11-12): most that said "waiting on" were the principal's move or someone else's wait.
    "Still waiting on you from earlier: the two drafts.",
    "Waiting on you:\n1. The three approval codes in my previous message\n2. The publish step",
    "The publish step is waiting on your confirmation in the terminal tab.",
    "The package is waiting for you in the terminal tab. Click into it and press Return.",
    "Two drafts are waiting for you to send yourself.",
    "These three are waiting on you before you fly:\n1. The meeting tomorrow\n2. The memo",
    "He is still waiting on the call times promised for today.",                      # someone else's wait
    "I'd add this question to the terms we're waiting on from the vendor.",
    "The thread was waiting on a lock, which is why the test hung.",                  # an explanation
    "I'm waiting on you for the last two answers.",
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


def test_the_hint_names_exactly_the_projects_whose_mail_a_session_that_binds_now_would_find(isolated_home, tmp_path):
    """2026-11-12, a review: the hint left out mail more than a day old sent while no session was on its project, and
    durable mail an earlier session had read, though the inbox of a session that bound to the project held both."""
    board.touch("S2", project="kappa", harness="claude-code")
    for session, name in (("S5", "omega"), ("S6", "lambda"), ("S7", "sigma")):       # three projects whose one session ended hours ago
        board.touch(session, project=name, harness="claude-code")
        quiet(session)
    old = board.message("project:sigma", "S2", "sent two days ago, with no session on sigma")
    os.utime(old, (time.time() - 48 * 3600,) * 2)
    board.message("project:lambda", "S2", "for every session on lambda", durable=True)
    assert len(board.inbox("S6", "lambda", mark_read=True)) == 1                      # an earlier session read it
    board.message("project:omega", "S2", "this one S8 has read")
    assert len(board.inbox("S8", "omega", mark_read=True)) == 1
    board.message("project:kappa", "S7", "for every session on kappa", durable=True)  # a live session is on kappa; S8 has not read this
    board.touch("S8", harness="claude-code")
    board.message("S8", "S2", "to S8 itself, about no project")
    out = subprocess.run([sys.executable, "-S", str(ROOT / "synthesis" / "hook.py"), "session-start"], capture_output=True, text=True,
                         cwd=tmp_path, input=json.dumps({"session_id": "S8", "cwd": str(tmp_path)})).stdout
    said = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    hint = "".join(note for note in said.split("\n\n") if "bound to no project" in note)
    assert re.findall(r"for: ([^.]+)\.", hint) == ["kappa, lambda, sigma"] and "synthesis resume kappa" in hint, said
    own = len(board.inbox("S8"))
    assert own == 1 and board.waiting("S8") == ["kappa", "lambda", "sigma"]
    for name in ("kappa", "lambda", "sigma", "omega", "delta"):                       # the hint and the inbox never disagree
        assert (name in board.waiting("S8")) == (len(board.inbox("S8", name)) > own), name
    board.inbox("S8", "kappa", mark_read=True)
    assert board.waiting("S8") == ["lambda", "sigma"]                                 # read once, it waits no longer


def test_the_hint_names_the_newest_mail_first_and_counts_the_rest(isolated_home, tmp_path):
    """A board that has run for months holds a box for every project; a session that has read none of it is told
    the eight with the newest mail and how many more there are."""
    board.touch("S2", project="kappa", harness="claude-code")
    for at, name in enumerate("abcdefghij"):
        board.touch(f"T{at}", project=name, harness="claude-code")                    # each project's one session ended hours ago
        quiet(f"T{at}")
        sent = board.message(f"project:{name}", "S2", f"for {name}", durable=True)
        os.utime(sent, (time.time() - at * 3600,) * 2)                                # a is the newest, j the oldest
    board.touch("S8", harness="claude-code")
    assert board.waiting("S8") == list("abcdefghij")
    out = subprocess.run([sys.executable, "-S", str(ROOT / "synthesis" / "hook.py"), "session-start"], capture_output=True, text=True,
                         cwd=tmp_path, input=json.dumps({"session_id": "S8", "cwd": str(tmp_path)})).stdout
    said = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "waiting for: a, b, c, d, e, f, g, h and 2 more." in said and "synthesis resume a" in said, said


# --- the doctor ----------------------------------------------------------------------------------------------------

def test_the_doctor_runs_the_turn_end_check_on_a_canned_reply(monkeypatch):
    from synthesis import doctor
    assert doctor.check_wait_check().status == "ok"
    monkeypatch.setattr(reply_check, "check", lambda payload, config: None)
    failed = doctor.check_wait_check()
    assert failed.status == "fail" and "not sent back" in failed.detail
