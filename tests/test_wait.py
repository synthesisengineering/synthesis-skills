"""Waiting for an expected event is a task: the watcher is armed before the turn ends.

On 2026-11-11 a session told its principal a peer "should be asking you soon" and ended its turn. Board messages
reach a session only when a prompt is submitted, so nothing would have woken it; the principal noticed because the
peer told him. Its first watcher then polled `synthesis inbox`, which marks what it prints as read, and sat silent
for half an hour because the session was bound to no project and the message was addressed to one. These tests
pin what closes that: one command that waits and is its own record, a read that consumes nothing, a sender told
what will deliver the message, and a turn-end check that sends back a reply which announces a wait with nothing
armed. Committed before the code.
"""
import errno
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
    done = cli("wait", "run", "--for", "3s", "--", sys.executable, "-c", CHECK, str(pids), TIDY, "30")
    assert done.returncode == 3 and "nothing arrived in 3 s" in done.stderr and time.time() - began < 15
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
    done = cli("wait", "run", "--every", "0.2s", "--for", "3s", "--", sys.executable, "-c", CHECK, str(pids), IDLE, "0")
    assert done.returncode == 3 and "nothing arrived in 3 s" in done.stderr
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


# --- what comes after the bound is not the event -------------------------------------------------------------------

@pytest.fixture
def clock(monkeypatch):
    """A clock the test moves. A sleep ends two hundredths of a second late, as real sleeps end late, and what the
    test has set for a moment inside one happens at that moment."""
    class Clock:
        late = 0.02

        def __init__(self):
            self.now, self.due = time.time(), []

        def after(self, seconds, happen):
            self.due.append((self.now + seconds, happen))

        def sleep(self, seconds):
            ends = self.now + seconds + self.late
            for moment, happen in sorted(self.due, key=lambda due: due[0]):
                if moment <= ends:
                    self.due.remove((moment, happen))
                    self.now = max(self.now, moment)
                    happen()
            self.now = ends
    moved = Clock()
    monkeypatch.setattr(time, "time", lambda: moved.now)
    monkeypatch.setattr(time, "sleep", moved.sleep)
    return moved


@pytest.mark.parametrize("bound, every, arrives", [
    ("1s", "2s", 1.01),                                                               # the review's input
    ("30m", "2s", 1800.01),                                                           # a wait of half an hour
    ("45s", "5m", 45.01),                                                             # one that looks less often than its bound is long
])
def test_a_message_that_arrives_after_the_bound_is_not_the_event(two, clock, capsys, bound, every, arrives):
    """2026-11-12, a second review: mail that arrived 1.01 seconds into a wait of one second ended the wait with 0 and
    was reported as arrived. The wait looked once more after its bound and counted what that look found."""
    from synthesis import wait
    clock.after(arrives, lambda: board.message("S1", "S2", "the review is in"))
    assert wait.main(["message", "--for", bound, "--every", every], "S1") == 3
    said = capsys.readouterr()
    assert said.out == "" and "nothing arrived in" in said.err and "still waiting for a message" in said.err
    assert wait.live("S1") == [] and len(board.inbox("S1", "alpha")) == 1             # it came, too late: unread, and the next wait finds it at once
    assert wait.main(["message", "--for", bound, "--every", every], "S1") == 0 and "(1 unread)" in capsys.readouterr().out


@pytest.mark.parametrize("there", [False, True], ids=["appears", "changes"])
def test_a_file_that_appears_or_changes_after_the_bound_is_not_the_event(two, clock, capsys, tmp_path, there):
    from synthesis import wait
    target = tmp_path / "result.json"
    if there:
        target.write_text("{}", encoding="utf-8")

    def written():
        target.write_text('{"done": true}', encoding="utf-8")
        os.utime(target, (time.time() + 5, time.time() + 5))                          # a later time, whatever the file system's grain
    clock.after(1.01, written)
    assert wait.main(["file", str(target), "--for", "1s"], "S1") == 3
    said = capsys.readouterr()
    assert said.out == "" and "nothing arrived in 1 s: still waiting for the file" in said.err
    assert target.read_text(encoding="utf-8") == '{"done": true}' and wait.live("S1") == []   # it was written, after the bound


def test_a_look_that_ends_after_the_bound_finds_nothing_in_time(two, clock, capsys):
    """The review ran the loop itself on a clock of its own: what turned up at 1.01 seconds of a bound of one second
    was the event. A look that begins inside the bound and ends after it has not found it in time either."""
    from synthesis import wait

    def watch(ready):
        began = clock.now
        return wait._watch("S1", "a message", began + 1, 1, 2, lambda: ready(began))
    assert watch(lambda began: "it is here" if clock.now - began >= 1.01 else "") == 3
    clock.late = 0                                                                    # now sleeps end on time, and a look takes 0.03 s

    def slow(began):
        clock.now += 0.03
        return "it is here" if clock.now - began >= 1.01 else ""
    assert watch(slow) == 3
    said = capsys.readouterr()
    assert said.out == "" and said.err.count("nothing arrived in 1 s: still waiting for a message") == 2
    assert wait.live("S1") == []


@pytest.mark.parametrize("bound, every, arrives", [
    ("1s", "2s", 0.5),                                                                # between two looks `--every` apart
    ("1s", "2s", 0.9),                                                                # a tenth of a second before the bound
    ("30m", "2s", 1799.9),
    ("45s", "5m", 20),                                                                # the wait looks less often than its bound is long
    ("12h", "5m", 43199.9),
])
def test_a_message_that_arrives_inside_the_bound_is_found_however_seldom_the_wait_looks(two, clock, capsys, bound, every, arrives):
    """The other side of the same edge. A look that ends after the bound counts for nothing, so the wait looks again
    just inside it: mail that came a tenth of a second before the bound is not said to have never come."""
    from synthesis import wait
    clock.after(arrives, lambda: board.message("S1", "S2", "the review is in"))
    assert wait.main(["message", "--for", bound, "--every", every], "S1") == 0
    said = capsys.readouterr()
    assert "(1 unread)" in said.out and said.err == ""


@pytest.mark.parametrize("there", [False, True], ids=["appears", "changes"])
def test_a_file_that_appears_or_changes_just_inside_the_bound_is_found(two, clock, capsys, tmp_path, there):
    from synthesis import wait
    target = tmp_path / "result.json"
    if there:
        target.write_text("{}", encoding="utf-8")

    def written():
        target.write_text('{"done": true}', encoding="utf-8")
        os.utime(target, (time.time() + 5, time.time() + 5))
    clock.after(0.9, written)
    assert wait.main(["file", str(target), "--for", "1s"], "S1") == 0
    assert capsys.readouterr().out == f"{target} {'changed' if there else 'appeared'}\n"


def test_a_look_that_ends_on_the_bound_still_counts(two, clock, capsys):
    """On a clock whose sleeps end on time the last look falls on the bound itself, and what is ready at that moment,
    not before, is the event."""
    from synthesis import wait
    clock.late = 0
    until = clock.now + 1
    assert wait._watch("S1", "a message", until, 1, 2, lambda: "it is here" if clock.now >= until else "") == 0
    assert capsys.readouterr().out == "it is here\n" and clock.now == until


def test_a_command_is_tried_every_interval_and_not_once_more_on_the_edge_of_the_bound(two, clock, monkeypatch, capsys):
    """A look for mail costs nothing, so one is made just inside the bound. A try of a command takes time and would be
    stopped a moment after it began: `wait run` keeps to its interval."""
    from synthesis import wait
    tried = []

    class Check:                                                                      # a check that fails at once
        def __init__(self, command, **kwargs):
            tried.append(round(clock.now - began, 2))

        def wait(self, timeout=None):
            return 1
    monkeypatch.setattr(subprocess, "Popen", Check)
    monkeypatch.setattr(wait, "_stop", lambda proc: None)
    began = clock.now
    assert wait.main(["run", "--for", "45s", "--every", "30s", "--", "ci-check"], "S1") == 3
    assert tried == [0, 30.02] and "nothing arrived in 45 s" in capsys.readouterr().err


# --- a command that cannot be started is refused, not tried again ---------------------------------------------------

@pytest.mark.parametrize("named, why", [
    ("a name that is not on PATH", "was not found"),
    ("a path that does not exist", "was not found"),
    ("a file that is not executable", "is not executable"),
    ("a directory", "is not executable"),
    ("a whole command given as one word", "was not found"),
    ("a script whose interpreter is missing", f"cannot be run ({os.strerror(errno.ENOENT)})"),
    ("a file that is no program", f"cannot be run ({os.strerror(errno.ENOEXEC)})"),
])
def test_a_command_that_cannot_be_started_is_refused_at_once_in_one_line(two, tmp_path, monkeypatch, named, why):
    """2026-11-12, a third review: `wait run --for 1m -- no-such-command` ended in a Python traceback. No try of such a
    command starts, so the wait refuses it the way it refuses a bound it cannot read: one line, exit 2, at once. The
    line names the program as it was given, which the traceback did: a command quoted whole after `--` is one word,
    and reads as a program that was not found only when that word is shown. And the plain words are said only where
    they are true: a script that is there, whose interpreter is not, fails with the error of a missing program."""
    from synthesis import paths
    script, folder, orphan, text = tmp_path / "check.sh", tmp_path / "checks", tmp_path / "orphan.sh", tmp_path / "notes.txt"
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o644)
    orphan.write_text(f"#!{tmp_path / 'gone' / 'interpreter'}\nexit 0\n", encoding="utf-8")
    text.write_text("no program\n", encoding="utf-8")
    for there in (orphan, text):
        there.chmod(0o755)
    folder.mkdir()
    monkeypatch.setenv("PATH", str(folder))                                           # one empty folder: what a name finds there is the same on every machine
    program = {"a name that is not on PATH": "synthesis-no-such-command", "a path that does not exist": str(tmp_path / "gone" / "check"),
               "a file that is not executable": str(script), "a directory": str(folder),
               "a whole command given as one word": "synthesis-no-such-command --branch main",
               "a script whose interpreter is missing": str(orphan), "a file that is no program": str(text)}[named]
    words = [program] if " " in program else [program, "--branch", "main"]
    began = time.time()
    done = cli("wait", "run", "--for", "1m", "--", *words)
    assert done.returncode == 2 and time.time() - began < 20                          # at once: its bound is a minute on
    assert done.stderr == f"`{' '.join(words)}` could not be started: its program {program!r} {why}\n" and done.stdout == ""
    assert not list((paths.board() / "waits").rglob("*.json"))                        # and it left no record of a wait behind


def test_a_command_that_cannot_be_started_gets_no_second_try_and_one_that_starts_and_fails_does(two, clock, monkeypatch, capsys):
    """Whatever the system says of a command it cannot run is the refusal, said once, with no sleep and no second try,
    and so it is for a command that goes missing between two tries. Of a program that is there to run, only the
    system's own words are said. A command that starts and exits with anything but 0, the 126 and 127 of a shell
    included, has failed a try: it is tried again until the bound."""
    import shutil
    from synthesis import paths, wait
    starts, tried, there, asked = [], [], [], signal.getsignal(signal.SIGTERM)
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}" if there else None)   # whether a program by the name is there to run

    class Check:                                                                      # each start ends as the test set it: an exit code, or no start
        def __init__(self, command, **kwargs):
            tried.append(command)
            self.code = starts.pop(0)
            if isinstance(self.code, OSError):
                raise self.code

        def wait(self, timeout=None):
            return self.code
    monkeypatch.setattr(subprocess, "Popen", Check)
    monkeypatch.setattr(wait, "_stop", lambda proc: None)

    def run(*outcomes):
        starts[:], tried[:], began = outcomes, [], clock.now
        code = wait.main(["run", "--for", "45s", "--every", "30s", "--", "ci-check", "--branch", "main"], "S1")
        said = capsys.readouterr()
        assert not list((paths.board() / "waits").rglob("*.json")) and signal.getsignal(signal.SIGTERM) is asked
        return code, said.out, said.err, len(tried), round(clock.now - began, 2)      # what it returned and printed, its tries, the seconds it took
    refused = "`ci-check --branch main` could not be started: its program 'ci-check' {}\n"
    for error, why in ((FileNotFoundError(errno.ENOENT, "No such file or directory", "ci-check"), "was not found"),
                       (PermissionError(errno.EACCES, "Permission denied", "ci-check"), "is not executable"),
                       (OSError(errno.ENOEXEC, "Exec format error", "ci-check"), "cannot be run (Exec format error)")):   # a file that is no program
        assert run(error) == (2, "", refused.format(why), 1, 0)
    there.append("ci-check")                                                          # now a program by that name is there, and may be run
    for error, why in ((FileNotFoundError(errno.ENOENT, "No such file or directory", "ci-check"), "cannot be run (No such file or directory)"),
                       (PermissionError(errno.EPERM, "Operation not permitted", "ci-check"), "cannot be run (Operation not permitted)")):
        assert run(error) == (2, "", refused.format(why), 1, 0)                       # its interpreter is missing; a sandbox forbids the run
    there.clear()
    gone = FileNotFoundError(errno.ENOENT, "No such file or directory", "ci-check")
    assert run(1, gone) == (2, "", refused.format("was not found"), 2, 30.02)         # it started and failed, then it was gone
    assert run(127, 126) == (3, "", "nothing arrived in 45 s: still waiting for `ci-check --branch main` to succeed\n", 2, 45.02)


def test_a_shell_that_cannot_find_its_command_has_started_and_failed_so_it_is_tried_again(two, tmp_path):
    tries = tmp_path / "tries"
    done = cli("wait", "run", "--every", "0.2s", "--for", "2s", "--", "sh", "-c", 'echo try >> "$1"; synthesis-no-such-command', "sh", str(tries))
    assert done.returncode == 3 and "nothing arrived in 2 s" in done.stderr and "could not be started" not in done.stderr
    assert len(tries.read_text(encoding="utf-8").splitlines()) >= 2


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


# --- a note is taken down once what it awaited is handled ----------------------------------------------------------

def note(what, session="S1", bound="12h"):
    made = cli("wait", "note", what, "--by", "the harness's timer", "--for", bound, session=session)
    assert made.returncode == 0, made.stderr


def outcome(done):
    return done.returncode, done.stdout, done.stderr


def test_a_note_is_withdrawn_by_the_seat_that_made_it_one_by_its_words_or_all_at_once(two):
    """2026-11-12, a third review: a note stood until its bound. When what it awaited was handled an hour into a note
    of twelve, the board and the turn-end check showed a wait that was over for eleven hours more."""
    from synthesis import paths, wait
    for what in ("the CI run on the release branch", "a reply from the vendor", "the nightly export"):
        note(what)
    assert outcome(cli("wait", "clear", "a reply from the vendor")) == (0, "cleared: a reply from the vendor\n", "")
    assert [w["what"] for w in wait.live("S1")] == ["the CI run on the release branch", "the nightly export"]
    assert outcome(cli("wait", "clear")) == (0, "cleared: the CI run on the release branch\ncleared: the nightly export\n", "")
    assert wait.live("S1") == [] and not list((paths.board() / "waits").rglob("*.json"))


def test_clearing_when_no_such_note_is_held_says_so_and_withdraws_nothing(two):
    from synthesis import wait
    assert outcome(cli("wait", "clear")) == (0, "this session holds no note\n", "")
    assert outcome(cli("wait", "clear", "the CI run")) == (0, "this session holds no note 'the CI run'\n", "")
    note("the CI run")
    assert outcome(cli("wait", "clear", "the CI rnu")) == (0, "this session holds no note 'the CI rnu'\n", "")   # its words, mistyped
    assert outcome(cli("wait", "clear", "the CI")) == (0, "this session holds no note 'the CI'\n", "")           # and a part of them
    assert [w["what"] for w in wait.live("S1")] == ["the CI run"]
    wait.record("S1", "the old build", time.time() - 1, by="the harness's timer")     # a note whose bound has passed is over already
    assert outcome(cli("wait", "clear", "the old build")) == (0, "this session holds no note 'the old build'\n", "")
    assert outcome(cli("wait", "clear")) == (0, "cleared: the CI run\n", "")


def test_clearing_never_touches_another_sessions_note(two, capsys):
    from synthesis import wait
    note("the CI run", session="S2")
    assert outcome(cli("wait", "clear")) == (0, "this session holds no note\n", "")      # S1 holds none: S2's is not its to clear,
    assert outcome(cli("wait", "clear", "the CI run")) == (0, "this session holds no note 'the CI run'\n", "")   # by its words either,
    note("the CI run")
    assert outcome(cli("wait", "clear", "the CI run")) == (0, "cleared: the CI run\n", "")   # and of two that say the same, its own goes
    assert wait.live("S1") == [] and [(w["session"], w["what"]) for w in wait.live("S2")] == [("S2", "the CI run")]
    other = cli("--session", "S2", "wait", "clear")                                  # a shell acts only as the session it belongs to
    assert other.returncode != 0 and "cannot act as S2" in other.stderr and len(wait.live("S2")) == 1
    for session in ("a b", "a_b"):                                                    # two ids the board keeps under one folder name
        wait.record(session, "the deploy", time.time() + 600, by="the harness's timer")
    assert wait.main(["clear"], "a b") == 0 and capsys.readouterr().out == "cleared: the deploy\n"
    assert [w["session"] for w in wait.live("a_b")] == ["a_b"]


def test_clearing_leaves_a_running_watchers_record_and_its_watcher_alone(two, tmp_path):
    """A record with a process is taken down by the end of that process and by nothing else: a seat that could clear it
    would show nothing armed while its watcher still ran."""
    from synthesis import wait
    target = tmp_path / "result.json"
    proc = start("wait", "file", str(target), "--for", "60s", "--every", "0.2s")
    try:
        deadline = time.time() + 10
        while not wait.live("S1") and time.time() < deadline:
            time.sleep(0.05)
        watched = wait.live("S1")[0]["what"]
        note("the CI run")
        assert outcome(cli("wait", "clear", watched)) == (0, f"this session holds no note {watched!r}\n", "")   # a watcher's words name no note
        assert outcome(cli("wait", "clear")) == (0, "cleared: the CI run\n", "")
        assert outcome(cli("wait", "clear")) == (0, "this session holds no note\n", "")
        assert [(w["what"], w["pid"]) for w in wait.live("S1")] == [(watched, proc.pid)] and proc.poll() is None
        target.write_text("{}", encoding="utf-8")                                     # and the watcher still does its work
        out, _ = proc.communicate(timeout=15)
        assert proc.returncode == 0 and "result.json appeared" in out and wait.live("S1") == []
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()


def test_a_cleared_note_is_gone_from_the_list_from_who_and_from_the_turn_end_check(two):
    reply = {"last_assistant_message": ANNOUNCED[0], "session_id": "S1"}
    for session in ("S1", "S2"):
        note("the CI run", session=session, bound="2h")
    quiet("S1")                                                                       # S1 was last seen hours ago, S2 a moment ago

    def who(*options):                                                                # each seat's row by its session
        return {row.split()[1]: row for row in cli("who", *options).stdout.splitlines() if re.match(r"[a-z2-7]{6} ", row)}

    def listed():                                                                     # the short names of the seats `wait list` shows
        return [row.split()[0] for row in cli("wait", "list").stdout.splitlines()]
    rows = who()
    assert set(rows) == {"S1", "S2"} and re.search(r"min ago  STALE  waiting until \d\d:\d\d$", rows["S1"])
    assert re.search(r"min ago  waiting until \d\d:\d\d$", rows["S2"])
    assert listed() == [board.short_name("S1"), board.short_name("S2")] and reply_check.check(reply, {}) is None
    assert outcome(cli("wait", "clear")) == (0, "cleared: the CI run\n", "")
    assert set(who()) == {"S2"} and who("--all")["S1"].endswith("min ago  STALE")     # quiet and waiting for nothing: stale, as before its note
    assert listed() == [board.short_name("S2")] and "nothing is armed" in reply_check.check(reply, {})
    assert outcome(cli("wait", "clear", session="S2")) == (0, "cleared: the CI run\n", "")
    assert who()["S2"].endswith("min ago") and listed() == []


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


def test_a_seat_in_a_live_wait_is_listed_for_the_whole_bound_of_its_wait(two, tmp_path, capsys):
    """2026-11-12, a second review: nine hours into a twelve-hour wait `synthesis who` printed nothing for the waiting
    seat, though a message still reached it, and `who --all` said only that it was stale. The waiting skill tells a
    seat whose wake did not come to read its binding there."""
    from synthesis import cli, wait
    now, area = time.time(), str(tmp_path / "area")
    board.claim("S1", [area])
    for name, project in (("S3", "gamma"), ("S4", "delta"), ("S5", "epsilon"), ("S6", None), ("S7", "eta")):
        board.touch(name, project=project, harness="codex")
    ended = subprocess.Popen([sys.executable, "-c", "pass"])
    ended.wait()
    wait.record("S1", "a message", now + 3 * 3600, pid=os.getpid(), every=300)        # nine hours into twelve, its watcher running
    wait.record("S4", "a message", now - 60, pid=os.getpid())                         # a wait whose bound passed a minute ago
    wait.record("S5", "the build", now + 3600, pid=ended.pid)                         # a wait whose watcher is gone
    wait.record("S6", "the CI run", now + 2 * 3600, by="the harness's timer")         # a wait the harness holds, on a seat bound to no project
    wait.record("S7", "a file", now + 1800, pid=os.getpid())                          # a seat seen a moment ago that waits too
    for name in ("S1", "S3", "S4", "S5", "S6"):                                       # each of these was last seen nine hours ago
        seat = board.load(name)
        seat.seen = now - 9 * 3600
        board.save(seat)

    def who(*options):                                                                # what it printed, and each seat's row by its session
        assert cli.main(["who", *options]) == 0
        said = capsys.readouterr().out
        return said, {row.split()[1]: row for row in said.splitlines() if re.match(r"[a-z2-7]{6} ", row)}

    def until(hours):
        return "waiting until " + time.strftime("%H:%M", time.localtime(now + hours * 3600))
    said, listed = who()
    assert set(listed) == {"S1", "S2", "S6", "S7"}                                    # who can be reached: not S3, S4 or S5
    assert re.search(r"claude-code +alpha +540 min ago  STALE  " + until(3) + "$", listed["S1"])   # its binding, its stale claims, its wait
    assert f"{listed['S1']}\n    {board.as_claim(area)}\n" in said
    assert re.search(r"codex +- +540 min ago  STALE  " + until(2) + "$", listed["S6"])
    assert listed["S7"].endswith("min ago  " + until(0.5)) and listed["S2"].endswith("min ago")
    said, everyone = who("--all")
    assert set(everyone) == {"S1", "S2", "S3", "S4", "S5", "S6", "S7"}
    assert all(everyone[name].endswith("540 min ago  STALE") for name in ("S3", "S4", "S5"))
    assert all(everyone[name] == listed[name] for name in listed)
    assert board.holders(area) == []                                                  # its claims are stale as before: they block nothing,
    with pytest.raises(board.ClaimConflict, match="it is stale, retry with --take"):
        board.claim("S2", [area])
    assert board.claim("S2", [area], take_stale=True).claims == [board.as_claim(area)]   # a peer that asks may take them,
    assert board.resolve("S1").session == "S1" and wait.live("S4") == wait.live("S5") == []   # and mail still reaches the seat


def test_resume_names_a_quiet_seat_that_holds_a_live_wait_and_marks_it_as_who_does(two, tmp_path, write_config, capsys):
    """2026-11-12, a third review: `synthesis who` listed a seat nine hours into a twelve-hour wait on a project, and
    `synthesis resume` of that project did not name it. The session that picked the project up was told of no one
    else there, though the waiting seat would wake and write the same records."""
    from synthesis import cli, wait
    root, now = tmp_path / "ai-knowledge-test", time.time()
    home = root / "projects" / "alpha"
    home.mkdir(parents=True)
    (home / "CONTEXT.md").write_text("# Alpha\n", encoding="utf-8")
    write_config({"knowledge_roots": [str(root)]})
    ended = subprocess.Popen([sys.executable, "-c", "pass"])
    ended.wait()
    for name, at in (("W1", "alpha"), ("W2", "alpha"), ("W3", "gamma"), ("W4", "alpha"), ("Q1", "alpha"), ("Q2", "alpha"), ("Q3", "alpha")):
        board.touch(name, project=at, harness="codex")
    board.claim("W3", [str(home / "resources")])                                      # a seat of another project that claimed a folder of this one
    wait.record("W1", "a message", now + 3 * 3600, pid=os.getpid(), every=300)        # nine hours into twelve, its watcher running
    wait.record("W2", "the CI run", now + 2 * 3600, by="the harness's timer")         # a wait the harness holds
    wait.record("W3", "a file", now + 3600, pid=os.getpid())
    wait.record("W4", "a message", now + 1800, pid=os.getpid())                       # a seat seen a moment ago that waits too
    wait.record("Q2", "a message", now - 60, pid=os.getpid())                         # a wait whose bound passed a minute ago
    wait.record("Q3", "the build", now + 3600, pid=ended.pid)                         # a wait whose watcher is gone
    wait.record("S2", "a message", now + 3600, pid=os.getpid())                       # a wait on another project, with no claim here
    for name in ("W1", "W2", "W3", "Q1", "Q2", "Q3", "S2"):                           # each of these was last seen nine hours ago
        seat = board.load(name)
        seat.seen = now - 9 * 3600
        board.save(seat)

    def until(hours):
        return "waiting until " + time.strftime("%H:%M", time.localtime(now + hours * 3600))
    assert cli.main(["--session", "R1", "resume", "alpha"]) == 0
    named = {line.split()[3]: line for line in capsys.readouterr().out.splitlines() if line.startswith("- Live session ")}
    assert set(named) == {"S1", "W1", "W2", "W3", "W4"}                               # not Q1, Q2 or Q3, nor S2 of another project
    for name, hours in (("W1", 3), ("W2", 2), ("W3", 1), ("W4", 0.5)):
        assert f") works here, {until(hours)}; one session owns CONTEXT.md" in named[name], named[name]
        assert named[name].endswith(f"coordinate with synthesis msg {board.short_name(name)}.")
    assert ") works here; one session owns CONTEXT.md" in named["S1"]                 # a seat that waits for nothing is named as before
    assert cli.main(["who"]) == 0
    rows = {row.split()[1]: row for row in capsys.readouterr().out.splitlines() if re.match(r"[a-z2-7]{6} ", row)}
    assert set(rows) == set(named) | {"S2", "R1"}                                     # `who` lists the same seats, with S2 and the one that resumed
    for name in ("W1", "W2", "W3", "W4"):                                             # and gives each waiting seat the same mark
        assert re.search(r"waiting until \d\d:\d\d$", rows[name]).group(0) in named[name]


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
