"""Finite command custody never reports a timeout or truncated run as success."""

import select
import os
import signal
import sys
import time

import pytest

import coordination_process as P


@pytest.mark.parametrize("command", [[], [""], ["a\x00b"], "echo unsafe", [3]])
def test_rejects_ambiguous_argv(tmp_path, command):
    with pytest.raises(ValueError):
        P.run(command, cwd=tmp_path)


@pytest.mark.parametrize("limit", [0, -1, 901, True, float("inf"), float("nan"), "1"])
def test_rejects_unbounded_time(tmp_path, limit):
    with pytest.raises(ValueError):
        P.run([sys.executable, "-c", "pass"], cwd=tmp_path, timeout=limit)


@pytest.mark.parametrize("limit", [0, -1, True, 1048577])
def test_rejects_invalid_capture(tmp_path, limit):
    with pytest.raises(ValueError):
        P.run([sys.executable, "-c", "pass"], cwd=tmp_path, output_bytes=limit)


def test_positive_exact_status_and_argv_no_shell(tmp_path):
    result = P.run(
        [
            sys.executable,
            "-c",
            "import sys;print(sys.argv[1]);raise SystemExit(9)",
            "$(false); literal",
        ],
        cwd=tmp_path,
    )
    assert result.returncode == 9 and result.stdout == "$(false); literal\n"


def test_output_overflow_fails_and_reaps_owned_process(tmp_path, monkeypatch):
    real = P.subprocess.Popen
    owned = []

    def track(*a, **kw):
        process = real(*a, **kw)
        owned.append(process)
        return process

    monkeypatch.setattr(P.subprocess, "Popen", track)
    with pytest.raises(ValueError, match="output ceiling"):
        P.run(
            [
                sys.executable,
                "-c",
                'import os,time;os.write(1,b"x"*10000);time.sleep(30)',
            ],
            cwd=tmp_path,
            output_bytes=64,
        )
    assert len(owned) == 1 and owned[0].returncode is not None
    with pytest.raises(ProcessLookupError):
        os.killpg(owned[0].pid, 0)


@pytest.mark.parametrize("parent_exits", [False, True])
def test_timeout_and_parent_exit_reap_descendant_group(
    tmp_path, monkeypatch, parent_exits
):
    # The descendant deliberately ignores TERM and inherits the capture pipe.
    script = """import os,signal,time
pid=os.fork()
if pid==0:
 signal.signal(signal.SIGTERM,signal.SIG_IGN)
 time.sleep(30)
else:
 from pathlib import Path
 Path(CHILD_FILE).write_text(str(pid))
 print(pid,flush=True)
 if not EXIT:time.sleep(30)
""".replace("EXIT", repr(parent_exits)).replace(
        "CHILD_FILE", repr(str(tmp_path / "child.pid"))
    )
    real = P.subprocess.Popen
    owned = []
    observers = []

    def track(*a, **kw):
        p = real(*a, **kw)
        owned.append(p)
        until = time.monotonic() + 2
        while not (tmp_path / "child.pid").exists():
            assert time.monotonic() < until
            time.sleep(0.005)
        child = int((tmp_path / "child.pid").read_text())
        if hasattr(os, "pidfd_open"):
            observers.append(("pidfd", os.pidfd_open(child)))
        else:
            queue = select.kqueue()
            queue.control(
                [
                    select.kevent(
                        child,
                        filter=select.KQ_FILTER_PROC,
                        flags=select.KQ_EV_ADD | select.KQ_EV_ONESHOT,
                        fflags=select.KQ_NOTE_EXIT,
                    )
                ],
                0,
                0,
            )
            observers.append(("kqueue", queue))
        return p

    monkeypatch.setattr(P.subprocess, "Popen", track)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        P.run([sys.executable, "-c", script], cwd=tmp_path, timeout=0.3)
    assert time.monotonic() - started < 3
    assert owned[0].returncode is not None
    # Observe the descendant's kernel exit event registered before cleanup;
    # kill(pid, 0) can be denied by a managed host after reparenting.
    kind, observer = observers[0]
    try:
        if kind == "pidfd":
            assert select.select([observer], [], [], 2)[0]
        else:
            assert any(
                event.fflags & select.KQ_NOTE_EXIT
                for event in observer.control(None, 1, 2)
            )
    finally:
        if kind == "pidfd":
            os.close(observer)
        else:
            observer.close()


def test_interruption_restores_handlers_and_reaps(tmp_path, monkeypatch):
    real = P.subprocess.Popen
    owned = []
    old = signal.getsignal(signal.SIGTERM)

    def track(*a, **kw):
        p = real(*a, **kw)
        owned.append(p)
        return p

    monkeypatch.setattr(P.subprocess, "Popen", track)

    def interrupted(*_):
        raise InterruptedError("fixture interrupt")

    monkeypatch.setattr(P.selectors.DefaultSelector, "select", interrupted)
    with pytest.raises(InterruptedError):
        P.run([sys.executable, "-c", "import time;time.sleep(30)"], cwd=tmp_path)
    assert signal.getsignal(signal.SIGTERM) == old and owned[0].returncode is not None
    with pytest.raises(ProcessLookupError):
        os.killpg(owned[0].pid, 0)


@pytest.mark.parametrize("fds", [[], (True,), (0,), (-1,), (3, 4)])
def test_snapshot_descriptor_shape_is_closed(tmp_path, fds):
    import coordination_process

    with pytest.raises(ValueError):
        coordination_process.run(
            [sys.executable, "-c", "raise SystemExit(99)"], cwd=tmp_path, pass_fds=fds
        )


def test_path_linked_file_cannot_be_passed_as_snapshot(tmp_path):
    import coordination_process

    with (tmp_path / "linked").open("w+b") as snapshot:
        with pytest.raises(ValueError, match="anonymous snapshot"):
            coordination_process.run(
                [sys.executable, "-c", "raise SystemExit(99)"],
                cwd=tmp_path,
                pass_fds=(snapshot.fileno(),),
            )


def test_pipe_cannot_be_passed_as_snapshot(tmp_path):
    import coordination_process

    read, write = os.pipe()
    try:
        with pytest.raises(ValueError, match="anonymous snapshot"):
            coordination_process.run(
                [sys.executable, "-c", "raise SystemExit(99)"],
                cwd=tmp_path,
                pass_fds=(read,),
            )
    finally:
        os.close(read)
        os.close(write)
