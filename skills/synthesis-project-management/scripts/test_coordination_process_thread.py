from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import os
import signal
import sys
import time
import subprocess
import select
import pytest
import coordination_process as P

SOURCE = Path(P.__file__).resolve()


def thread_call(tmp_path, command, **kw):
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(P.run, command, cwd=tmp_path, **kw).result(timeout=8)


def test_thread_positive_and_handlers(tmp_path):
    before = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
    r = thread_call(tmp_path, [sys.executable, "-c", 'print("literal")'])
    assert r.returncode == 0 and r.stdout == "literal\n"
    assert before == {s: signal.getsignal(s) for s in before}


@pytest.mark.parametrize("why", ["timeout", "output"])
def test_thread_limits_remain_refusals(tmp_path, why):
    script = "import time;time.sleep(10)" if why == "timeout" else 'print("x"*10000)'
    expected = TimeoutError if why == "timeout" else ValueError
    with pytest.raises(expected, match="ceiling"):
        thread_call(
            tmp_path, [sys.executable, "-c", script], timeout=0.2, output_bytes=64
        )


def test_concurrent_threads_have_separate_custody(tmp_path):
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [
            pool.submit(
                P.run, [sys.executable, "-c", f"print({i})"], cwd=tmp_path, timeout=3
            )
            for i in range(4)
        ]
        assert [p.result(timeout=7).stdout for p in jobs] == [
            f"{i}\n" for i in range(4)
        ]


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGKILL])
def test_parent_death_eof_reaps_thread_command(tmp_path, sig):
    pidfile = tmp_path / "command.pid"
    beat = tmp_path / "beat"
    script = (
        "import os,time;from pathlib import Path;Path("
        + repr(str(pidfile))
        + ").write_text(str(os.getpid()));\nwhile True:\n Path("
        + repr(str(beat))
        + ").write_text(str(time.monotonic()));time.sleep(.02)"
    )
    launcher = tmp_path / "parent.py"
    launcher.write_text(
        'import sys,importlib.util\nfrom concurrent.futures import ThreadPoolExecutor\nfrom pathlib import Path\ns=importlib.util.spec_from_file_location("p",'
        + repr(str(SOURCE))
        + ");p=importlib.util.module_from_spec(s);s.loader.exec_module(p)\nwith ThreadPoolExecutor(max_workers=1) as e:e.submit(p.run,"
        + repr([sys.executable, "-c", script])
        + ",cwd=Path("
        + repr(str(tmp_path))
        + "),timeout=20).result()\n"
    )
    proc = subprocess.Popen(
        [sys.executable, str(launcher)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    watch = None
    child = None
    try:
        until = time.monotonic() + 3
        while not pidfile.exists() and proc.poll() is None and time.monotonic() < until:
            time.sleep(0.01)
        assert pidfile.exists(), proc.communicate(timeout=1)
        child = int(pidfile.read_text())
        if hasattr(os, "pidfd_open"):
            watch = ("fd", os.pidfd_open(child))
        else:
            q = select.kqueue()
            q.control(
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
            watch = ("kq", q)
        os.kill(proc.pid, sig)
        proc.wait(timeout=3)
        if watch[0] == "fd":
            assert select.select([watch[1]], [], [], 4)[0]
        else:
            assert watch[1].control(None, 1, 4)
        after = beat.read_bytes()
        time.sleep(0.08)
        assert beat.read_bytes() == after
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=3)
        if child:
            try:
                os.kill(child, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        if watch:
            if watch[0] == "fd":
                os.close(watch[1])
            else:
                watch[1].close()
        proc.stdout.close()
        proc.stderr.close()


def test_thread_snapshot_stays_exact_and_anonymous(tmp_path):
    import tempfile

    with tempfile.TemporaryFile(dir=tmp_path) as f:
        f.write(b"exact snapshot")
        f.flush()
        f.seek(0)
        r = thread_call(
            tmp_path,
            [
                sys.executable,
                "-c",
                f"import os;print(os.read({f.fileno()},100).decode())",
            ],
            pass_fds=(f.fileno(),),
            timeout=3,
        )
        assert r.stdout == "exact snapshot\n"
    with (tmp_path / "linked").open("w+b") as f:
        with pytest.raises(ValueError, match="anonymous"):
            thread_call(
                tmp_path,
                [sys.executable, "-c", "raise SystemExit(99)"],
                pass_fds=(f.fileno(),),
            )


def test_thread_tiny_deadline_remains_timeout(tmp_path):
    with pytest.raises(TimeoutError, match="ceiling"):
        thread_call(tmp_path, [sys.executable, "-c", "pass"], timeout=0.00001)


def test_thread_timeout_reaps_term_ignoring_descendant(tmp_path):
    beat = tmp_path / "descendant"
    script = (
        "import os,signal,time;from pathlib import Path\np=os.fork()\nif p==0:\n signal.signal(signal.SIGTERM,signal.SIG_IGN)\n while True:\n  Path("
        + repr(str(beat))
        + ").write_text(str(time.monotonic()));time.sleep(.01)\nelse:time.sleep(20)"
    )
    with pytest.raises(TimeoutError, match="ceiling"):
        thread_call(tmp_path, [sys.executable, "-c", script], timeout=0.3)
    assert beat.exists()
    before = beat.read_bytes()
    time.sleep(0.15)
    assert beat.read_bytes() == before


def test_interrupted_thread_owner_keeps_eof_custody(tmp_path, monkeypatch):
    marker = tmp_path / "heartbeat"
    script = (
        "import time;from pathlib import Path\nwhile True:\n Path("
        + repr(str(marker))
        + ").write_text(str(time.monotonic()));time.sleep(.01)"
    )
    popen = P.subprocess.Popen
    helpers = []

    def launch(*args, **kwargs):
        p = popen(*args, **kwargs)
        helpers.append(p)
        until = time.monotonic() + 3
        while not marker.exists():
            assert time.monotonic() < until
            time.sleep(0.01)
        return p

    monkeypatch.setattr(P.subprocess, "Popen", launch)

    def interrupt(*args, **kwargs):
        raise InterruptedError("Synthetic interruption of worker thread")

    monkeypatch.setattr(P.selectors.DefaultSelector, "select", interrupt)
    with pytest.raises(InterruptedError):
        thread_call(tmp_path, [sys.executable, "-c", script], timeout=5)
    assert len(helpers) == 1 and helpers[0].returncode is not None
    before = marker.read_bytes()
    time.sleep(0.1)
    assert marker.read_bytes() == before


def test_thread_dispatch_cannot_execute_replaced_module_path(tmp_path, monkeypatch):
    import importlib.util
    path = tmp_path / "owner.py"
    path.write_bytes(SOURCE.read_bytes())
    spec = importlib.util.spec_from_file_location("isolated_owner_snapshot", path)
    owner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owner)
    sentinel = tmp_path / "unapproved-effect"
    original = owner.subprocess.Popen
    dispatches = []
    def swap(argv, *args, **kwargs):
        if "--thread-owner" in argv:
            dispatches.append(argv)
            path.write_text("from pathlib import Path\nPath(" + repr(str(sentinel)) + ").write_text('late replacement executed')\n")
        return original(argv, *args, **kwargs)
    monkeypatch.setattr(owner.subprocess, "Popen", swap)
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(owner.run, [sys.executable, "-c", "print('intended')"], cwd=tmp_path, timeout=3).result(timeout=8)
    assert result.stdout == "intended\n" and result.returncode == 0
    assert len(dispatches) == 1 and "-I" in dispatches[0] and "-B" in dispatches[0]
    assert not sentinel.exists()
