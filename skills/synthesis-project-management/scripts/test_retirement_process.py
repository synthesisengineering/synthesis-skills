"""Real retained-runtime process custody, independent of the live source path."""

import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import signal
import subprocess
import sys
import threading
import time
import types

import pytest

import retirement_runtime as runtime


def staged_helper(tmp_path, body):
    source = tmp_path / "skills/synthesis-project-management"
    original = Path(runtime.__file__).parent.parent
    for relative in runtime.MEMBERS:
        target = runtime.source_member(source, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(runtime.source_member(original, relative), target)
    (source / "scripts/coordination.py").write_text(body)
    store = tmp_path / "retained"
    return store, runtime.stage(source, store)


def watch_exit(pid):
    if hasattr(os, "pidfd_open"):
        return ("pidfd", os.pidfd_open(pid))
    queue = select.kqueue()
    queue.control(
        [
            select.kevent(
                pid,
                filter=select.KQ_FILTER_PROC,
                flags=select.KQ_EV_ADD | select.KQ_EV_ONESHOT,
                fflags=select.KQ_NOTE_EXIT,
            )
        ],
        0,
        0,
    )
    return ("kqueue", queue)


def exited(observer):
    kind, handle = observer
    if kind == "pidfd":
        return bool(select.select([handle], [], [], 2)[0])
    return any(
        event.fflags & select.KQ_NOTE_EXIT for event in handle.control(None, 1, 2)
    )


def close_observer(observer):
    if observer[0] == "pidfd":
        os.close(observer[1])
    else:
        observer[1].close()


@pytest.mark.parametrize(
    "mode", ["timeout", "overflow", "parent-exit", "success", "SIGINT", "SIGTERM"]
)
def test_retained_invoke_owns_descendants_through_every_terminal_path(
    tmp_path, monkeypatch, mode
):
    pidfile = tmp_path / "child.pid"
    ready = tmp_path / "child.ready"
    body = (
        """import os,signal,time
from pathlib import Path
pid=os.fork()
if pid==0:
 signal.signal(signal.SIGTERM,signal.SIG_IGN)
 if MODE=='success':
  os.close(1);os.close(2)
 Path(READY).write_text('ready')
 time.sleep(30)
else:
 until=time.monotonic()+3
 while not Path(READY).exists():
  if time.monotonic()>until:raise RuntimeError('child startup timed out')
  time.sleep(.005)
 pending = Path(str(PIDFILE) + '.pending')
 pending.write_text(str(pid))
 pending.replace(Path(PIDFILE))
 if MODE=='overflow':os.write(1,b'x'*10000)
 if MODE in ('parent-exit','success'):raise SystemExit(0)
 time.sleep(30)
""".replace("MODE", repr(mode))
        .replace("READY", repr(str(ready)))
        .replace("PIDFILE", repr(str(pidfile)))
    )
    store, digest = staged_helper(tmp_path, body)
    monkeypatch.setattr(
        runtime, "INVOKE_TIMEOUT", 0.4 if mode not in ("SIGINT", "SIGTERM") else 5
    )
    monkeypatch.setattr(runtime, "INVOKE_OUTPUT_BYTES", 64)
    original = subprocess.Popen
    owned, observers, timers = [], [], []

    def track(*args, **kwargs):
        process = original(*args, **kwargs)
        owned.append(process)
        until = time.monotonic() + 3
        while not pidfile.exists():
            if time.monotonic() > until:
                raise RuntimeError("fixture child not observed")
            time.sleep(0.005)
        observers.append(watch_exit(int(pidfile.read_text())))
        if mode in ("SIGINT", "SIGTERM"):
            timer = threading.Timer(
                0.05, os.kill, args=(os.getpid(), getattr(signal, mode))
            )
            timers.append(timer)
            timer.start()
        return process

    monkeypatch.setattr(subprocess, "Popen", track)
    before = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    started = time.monotonic()
    try:
        if mode == "success":
            result = runtime.invoke(store, digest, tmp_path / "unused.md", [])
            assert result.returncode == 0 and result.stdout == ""
        elif mode in ("SIGINT", "SIGTERM"):
            with pytest.raises(RuntimeError, match="interrupted by signal"):
                runtime.invoke(store, digest, tmp_path / "unused.md", [])
        elif mode == "overflow":
            with pytest.raises(ValueError, match="output ceiling"):
                runtime.invoke(store, digest, tmp_path / "unused.md", [])
        else:
            with pytest.raises(TimeoutError):
                runtime.invoke(store, digest, tmp_path / "unused.md", [])
        assert time.monotonic() - started < 5
        assert len(owned) == 1 and owned[0].returncode is not None
        assert exited(observers[0]), (
            "retained helper descendant survived terminal cleanup"
        )
        assert all(signal.getsignal(sig) == handler for sig, handler in before.items())
        assert not list(store.rglob("*.pyc")) and not list(store.rglob("__pycache__"))
        (tmp_path / "process-disposition.json").write_text(
            json.dumps(
                {
                    "mode": mode,
                    "parent_pid": owned[0].pid,
                    "parent_returncode": owned[0].returncode,
                    "descendant_pid": int(pidfile.read_text()),
                    "descendant_kernel_exit_observed": True,
                    "source_sha256": hashlib.sha256(
                        Path(runtime.__file__).read_bytes()
                    ).hexdigest(),
                },
                indent=2,
            )
            + "\n"
        )
    finally:
        for timer in timers:
            timer.cancel()
            timer.join(timeout=1)
        for process in owned:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=2)
        for observer in observers:
            close_observer(observer)


@pytest.mark.parametrize(
    "mode", ["timeout", "overflow", "parent-exit", "success", "SIGINT", "SIGTERM"]
)
def test_custody_pid_publication_survives_writer_preemption(tmp_path, monkeypatch, mode):
    """A visible PID record is complete before the observer consumes it."""
    original = staged_helper

    def preempted(root, body):
        pause = """
_write_text = Path.write_text
def delayed_pid(self, value, *args, **kwargs):
 if self.name in ('child.pid', 'child.pid.pending'):
  with self.open('w') as stream:
   time.sleep(.12)
   return stream.write(value)
 return _write_text(self, value, *args, **kwargs)
Path.write_text = delayed_pid
"""
        assert body.count("from pathlib import Path") == 1
        return original(root, body.replace("from pathlib import Path", "from pathlib import Path" + pause))

    monkeypatch.setattr(sys.modules[__name__], "staged_helper", preempted)
    test_retained_invoke_owns_descendants_through_every_terminal_path(
        tmp_path, monkeypatch, mode
    )


def test_exact_retained_process_owner_ignores_ambient_module_cache(
    tmp_path, monkeypatch
):
    store, digest = staged_helper(tmp_path, 'print("actual retained helper")\n')
    impostor = types.ModuleType("coordination_process")
    impostor.run = lambda *_a, **_k: pytest.fail("ambient module cache was selected")
    monkeypatch.setitem(sys.modules, "coordination_process", impostor)
    result = runtime.invoke(store, digest, tmp_path / "unused.md", [])
    assert result.returncode == 0 and result.stdout == "actual retained helper\n"
    assert not list(store.rglob("*.pyc"))


def test_changed_code_after_verify_cannot_execute(tmp_path, monkeypatch):
    store, digest = staged_helper(tmp_path, 'print("actual retained helper")\n')
    sentinel = tmp_path / "forbidden-execution"
    original = runtime.process_owner

    def replace(executable, pinned):
        member = executable.with_name("coordination_process.py")
        member.chmod(0o600)
        member.write_text(
            f'from pathlib import Path\nPath({str(sentinel)!r}).write_text("bad")\n'
        )
        member.chmod(0o400)
        return original(executable, pinned)

    monkeypatch.setattr(runtime, "process_owner", replace)
    with pytest.raises(ValueError, match="changed before execution"):
        runtime.invoke(store, digest, tmp_path / "unused.md", [])
    assert not sentinel.exists()


@pytest.mark.parametrize(
    "problem", ["missing", "symlink", "hardlink", "writable", "fifo"]
)
def test_process_owner_dependency_is_required_before_execution(tmp_path, problem):
    store, digest = staged_helper(tmp_path, 'print("actual retained helper")\n')
    member = store / ("coordination-" + digest) / "scripts/coordination_process.py"
    saved = tmp_path / "original-owner.py"
    member.rename(saved)
    if problem == "symlink":
        member.symlink_to(saved)
    elif problem == "hardlink":
        os.link(saved, member)
    elif problem == "writable":
        shutil.copyfile(saved, member)
        member.chmod(0o666)
    elif problem == "fifo":
        os.mkfifo(member)
    with pytest.raises((OSError, ValueError)):
        runtime.invoke(store, digest, tmp_path / "unused.md", [])


@pytest.mark.parametrize(
    "member", ["coordination.py", "coordination_schema.py", "wordlist"]
)
def test_late_dispatch_replacement_never_executes_unverified_bytes(
    tmp_path, monkeypatch, member
):
    marker = tmp_path / "original-result"
    body = (
        "import coordination_schema\nfrom pathlib import Path\n"
        f"Path({str(marker)!r}).write_text(str(len(coordination_schema.session_words())))\n"
    )
    store, digest = staged_helper(tmp_path, body)
    sentinel = tmp_path / "forbidden-effect"
    original = runtime.process_owner

    def wrapping(executable, pinned):
        owner = original(executable, pinned)

        def replaced(*args, **kwargs):
            if member == "wordlist":
                target = (
                    executable.parent.parent
                    / "references/session-words-v1.txt.zlib.b85"
                )
                replacement = b"broken wordlist"
            else:
                target = executable.with_name(member)
                replacement = (
                    f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('bad')\n"
                ).encode()
            target.chmod(0o600)
            target.write_bytes(replacement)
            target.chmod(0o400)
            return owner.run(*args, **kwargs)

        return types.SimpleNamespace(run=replaced)

    monkeypatch.setattr(runtime, "process_owner", wrapping)
    with pytest.raises(ValueError, match="content changed"):
        runtime.invoke(store, digest, tmp_path / "unused.md", [])
    assert not sentinel.exists(), "unverified late code executed before refusal"
    assert marker.read_text() == "2048", "the exact admitted resource was not used"
    assert not list(store.rglob("*.pyc"))


@pytest.mark.parametrize("alteration", ["wire", "manifest", "member"])
def test_transport_tampering_fails_before_any_source_execution(
    tmp_path, monkeypatch, alteration
):
    sentinel = tmp_path / "must-not-run"
    store, digest = staged_helper(
        tmp_path,
        f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('bad')\n",
    )
    original = runtime.process_owner

    def wrapping(executable, pinned):
        owner = original(executable, pinned)

        def replaced(command, **kwargs):
            fd = kwargs["pass_fds"][0]
            with os.fdopen(os.dup(fd), "r+b") as data:
                value = json.loads(data.read())
                if alteration == "wire":
                    value["manifest"] = "00"
                elif alteration == "manifest":
                    value["manifest"] = b"{}".hex()
                else:
                    value["files"]["scripts/coordination.py"] = (
                        b"raise RuntimeError('changed')".hex()
                    )
                wire = runtime.canonical(value)
                data.seek(0)
                data.truncate()
                data.write(wire)
                data.flush()
                data.seek(0)
                if alteration != "wire":
                    command[7] = hashlib.sha256(wire).hexdigest()
            return owner.run(command, **kwargs)

        return types.SimpleNamespace(run=replaced)

    monkeypatch.setattr(runtime, "process_owner", wrapping)
    done = runtime.invoke(store, digest, tmp_path / "unused.md", [])
    assert done.returncode != 0 and not sentinel.exists()
    assert (
        "byte transport changed" in done.stdout
        if alteration == "wire"
        else "binding changed" in done.stdout
        if alteration == "manifest"
        else "snapshot member changed" in done.stdout
    )


def test_verified_loader_does_not_read_unadmitted_resources(tmp_path):
    store, digest = staged_helper(
        tmp_path,
        "import coordination_schema\ncoordination_schema.__loader__.get_data('/etc/passwd')\n",
    )
    done = runtime.invoke(store, digest, tmp_path / "unused.md", [])
    assert done.returncode != 0 and "outside the admitted runtime" in done.stdout


def test_late_unlisted_stdlib_shadow_cannot_execute(tmp_path, monkeypatch):
    marker = tmp_path / "original"
    body = ("import sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path(__file__).parent))\nimport fractions\n"
            f"Path({str(marker)!r}).write_text(str(fractions.Fraction(1,2)))\n")
    store,digest = staged_helper(tmp_path,body)
    sentinel = tmp_path / "forbidden"
    original = runtime.process_owner
    def wrapping(executable,pinned):
        owner=original(executable,pinned)
        def changed(*args,**kwargs):
            target=executable.with_name("fractions.py")
            target.write_text(f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('bad')\n")
            return owner.run(*args,**kwargs)
        return types.SimpleNamespace(run=changed)
    monkeypatch.setattr(runtime,"process_owner",wrapping)
    with pytest.raises(ValueError,match="unexpected retained"):
        runtime.invoke(store,digest,tmp_path/"unused",[])
    assert not sentinel.exists()
    assert marker.read_text()=="1/2"
