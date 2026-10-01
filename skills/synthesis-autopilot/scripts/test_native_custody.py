"""Synthetic process controls: never invokes an installed native client."""

import importlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest
from test_native_protocol import initialized, complete_resume, terminal
from native_muse_contract import binding

SOURCE = Path(os.environ.get("NATIVE_SOURCE", str(Path(__file__).resolve().parent)))
sys.path.insert(0, str(SOURCE))
n = importlib.import_module("native_resume")


def absent(group):
    try:
        os.killpg(group, 0)
        return False
    except ProcessLookupError:
        return True
    except PermissionError:
        return False


def rescue(process):
    if not absent(process.pid):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except PermissionError:
            pass
    process.wait(timeout=3)
    deadline = time.monotonic() + 2
    while not absent(process.pid) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert absent(process.pid), "synthetic process group unresolved"
    for stream in (process.stdin, process.stdout, process.stderr):
        if stream and not stream.closed:
            stream.close()


def test_close_removes_group_descendant_after_leader_exits(monkeypatch, tmp_path):
    real = subprocess.Popen
    child_pid = tmp_path / "child.pid"
    code = """import os,time,sys
pid=os.fork()
if pid==0:
 for fd in (0,1,2):os.close(fd)
 with open(sys.argv[1],'w') as f:f.write(str(os.getpid()))
 time.sleep(30)
 os._exit(0)
while not os.path.exists(sys.argv[1]):time.sleep(.005)
os._exit(0)
"""
    monkeypatch.setattr(
        n.subprocess,
        "Popen",
        lambda args, **kwargs: real(
            [sys.executable, "-I", "-B", "-c", code, str(child_pid)], **kwargs
        ),
    )
    rpc = n.MuseConnection("/synthetic", tmp_path, timeout=2)
    try:
        with pytest.raises(EOFError):
            rpc.call("initialize", {})
        assert child_pid.exists() and not absent(rpc.process.pid), (
            "positive control did not leave a live owned group member"
        )
        rpc.close()
        assert absent(rpc.process.pid), (
            "close left the native process group alive after its leader exited"
        )
    finally:
        rescue(rpc.process)
        print(
            json.dumps(
                {
                    "case": "exited-leader",
                    "pid": rpc.process.pid,
                    "child_pid": int(child_pid.read_text()),
                    "returncode": rpc.process.returncode,
                    "group_absent": absent(rpc.process.pid),
                }
            )
        )


@pytest.mark.parametrize(
    "step", ["blocking", "selector", "register-first", "register-second"]
)
def test_constructor_failure_reaps_owned_process(monkeypatch, tmp_path, step):
    real = subprocess.Popen
    made = []

    def spawn(args, **kwargs):
        p = real(
            [sys.executable, "-I", "-B", "-c", "import time;time.sleep(30)"], **kwargs
        )
        made.append(p)
        return p

    monkeypatch.setattr(n.subprocess, "Popen", spawn)
    if step == "blocking":
        monkeypatch.setattr(
            n.os,
            "set_blocking",
            lambda *a: (_ for _ in ()).throw(OSError("controlled setup failure")),
        )
    elif step == "selector":
        monkeypatch.setattr(
            n.selectors,
            "DefaultSelector",
            lambda: (_ for _ in ()).throw(OSError("controlled setup failure")),
        )
    else:
        actual = n.selectors.DefaultSelector

        def selector():
            s = actual()
            register = s.register
            seen = []

            def reg(*args):
                seen.append(args)
                if len(seen) == (1 if step == "register-first" else 2):
                    raise OSError("controlled setup failure")
                return register(*args)

            s.register = reg
            return s

        monkeypatch.setattr(n.selectors, "DefaultSelector", selector)
    try:
        with pytest.raises(OSError, match="controlled setup failure"):
            n.MuseConnection("/synthetic", tmp_path, timeout=2)
        assert len(made) == 1
        assert made[0].poll() is not None and absent(made[0].pid), (
            "constructor left a live owned process"
        )
        assert all(s.closed for s in (made[0].stdin, made[0].stdout, made[0].stderr))
    finally:
        for p in made:
            rescue(p)
            print(
                json.dumps(
                    {
                        "case": "setup-" + step,
                        "pid": p.pid,
                        "returncode": p.returncode,
                        "group_absent": absent(p.pid),
                    }
                )
            )


def test_term_ignoring_leader_and_descendant_are_bounded(monkeypatch, tmp_path):
    real = subprocess.Popen
    pid_file = tmp_path / "child.pid"
    code = """import os,signal,sys,time
signal.signal(signal.SIGTERM,signal.SIG_IGN)
pid=os.fork()
if pid==0:
 with open(sys.argv[1],'w') as f:f.write(str(os.getpid()))
while True:time.sleep(.05)
"""
    monkeypatch.setattr(
        n.subprocess,
        "Popen",
        lambda args, **kwargs: real(
            [sys.executable, "-I", "-B", "-c", code, str(pid_file)], **kwargs
        ),
    )
    rpc = n.MuseConnection("/synthetic", tmp_path, timeout=0.2)
    try:
        with pytest.raises(TimeoutError):
            rpc.call("initialize", {})
        assert pid_file.exists()
        started = time.monotonic()
        result = rpc.close()
        assert time.monotonic() - started < 4.5
        assert (
            result["group_absent"]
            and result["leader_reaped"]
            and result["signals"] == ["TERM", "KILL"]
        )
        assert rpc.close() == result
    finally:
        rescue(rpc.process)
        print(
            json.dumps(
                {
                    "case": "term-ignore",
                    "pid": rpc.process.pid,
                    "child_pid": int(pid_file.read_text()),
                    "returncode": rpc.process.returncode,
                    "group_absent": absent(rpc.process.pid),
                }
            )
        )


@pytest.mark.parametrize("already_reaped", [True, False])
def test_unproven_group_identity_cannot_signal_foreign_group(
    monkeypatch, already_reaped
):
    import io
    from types import SimpleNamespace

    signals = []
    rpc = n.MuseConnection.__new__(n.MuseConnection)
    rpc.cleanup = None
    rpc.selector = None
    rpc._child_waitable = lambda _: False
    rpc.process = SimpleNamespace(
        pid=314159,
        returncode=0 if already_reaped else None,
        stdin=io.BytesIO(),
        stdout=io.BytesIO(),
        stderr=io.BytesIO(),
    )

    def signal_group(pid, sig):
        assert pid == 314159
        signals.append(sig)

    monkeypatch.setattr(n.os, "killpg", signal_group)
    with pytest.raises(ValueError, match="unproven"):
        rpc.close()
    assert signals and all(sig == 0 for sig in signals)
    assert all(
        s.closed for s in (rpc.process.stdin, rpc.process.stdout, rpc.process.stderr)
    )
    before = list(signals)
    with pytest.raises(ValueError, match="no repeated signals"):
        rpc.close()
    assert signals == before


def test_non_reaping_probe_retains_exact_child_identity(tmp_path):
    probe = n._child_wait_probe()
    p = subprocess.Popen(
        [sys.executable, "-I", "-B", "-c", "print('ready',flush=True)"],
        stdout=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        assert probe(p.pid)
        assert p.stdout.read() == b"ready\n"
        assert probe(p.pid), "exited but unreaped child must still anchor the group"
        assert p.returncode is None
        assert p.wait(timeout=2) == 0
        assert not probe(p.pid), "reaped child must not remain an ownership anchor"
    finally:
        if p.returncode is None:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait(timeout=2)
        p.stdout.close()
        print(
            json.dumps(
                {
                    "case": "wait-probe",
                    "pid": p.pid,
                    "returncode": p.returncode,
                    "group_absent": absent(p.pid),
                }
            )
        )


def test_missing_ownership_probe_refuses_before_spawn(monkeypatch, tmp_path):
    called = []
    monkeypatch.delattr(n.os, "waitid", raising=False)
    monkeypatch.setattr(n.sys, "platform", "unsupported-synthetic")
    monkeypatch.setattr(n.subprocess, "Popen", lambda *a, **k: called.append(a))
    with pytest.raises(OSError, match="ownership check unavailable"):
        n.MuseConnection("/synthetic", tmp_path)
    assert called == []


def test_ownership_probe_interruptions_are_finite(monkeypatch):
    calls = []

    def interrupted(*args):
        calls.append(args)
        raise OSError(n.errno.EINTR, "controlled interruption")

    monkeypatch.setattr(n.os, "waitid", interrupted, raising=False)
    with pytest.raises(OSError, match="repeatedly interrupted"):
        n._child_wait_probe()(123)
    assert len(calls) == 4


def test_constructor_keyboard_interrupt_still_reaps(monkeypatch, tmp_path):
    real = subprocess.Popen
    made = []

    def spawn(args, **kwargs):
        p = real(
            [sys.executable, "-I", "-B", "-c", "import time;time.sleep(30)"], **kwargs
        )
        made.append(p)
        return p

    monkeypatch.setattr(n.subprocess, "Popen", spawn)
    monkeypatch.setattr(
        n.os, "set_blocking", lambda *a: (_ for _ in ()).throw(KeyboardInterrupt())
    )
    try:
        with pytest.raises(KeyboardInterrupt):
            n.MuseConnection("/synthetic", tmp_path)
        assert len(made) == 1 and made[0].returncode is not None and absent(made[0].pid)
    finally:
        for p in made:
            rescue(p)
            print(
                json.dumps(
                    {
                        "case": "setup-interrupt",
                        "pid": p.pid,
                        "returncode": p.returncode,
                        "group_absent": absent(p.pid),
                    }
                )
            )


def test_cleanup_interrupt_still_reaps(monkeypatch, tmp_path):
    real = subprocess.Popen
    original_sleep = time.sleep
    calls = []
    monkeypatch.setattr(
        n.subprocess,
        "Popen",
        lambda args, **kwargs: real(
            [sys.executable, "-I", "-B", "-c", "import time;time.sleep(30)"], **kwargs
        ),
    )
    rpc = n.MuseConnection("/synthetic", tmp_path, timeout=2)

    def interrupted(seconds):
        if not calls:
            calls.append(seconds)
            raise KeyboardInterrupt("controlled close interruption")
        original_sleep(seconds)

    monkeypatch.setattr(n.time, "sleep", interrupted)
    try:
        with pytest.raises(KeyboardInterrupt, match="controlled close"):
            rpc.close()
        assert rpc.process.returncode is not None and absent(rpc.process.pid), (
            "interrupt escaped cleanup before reaping"
        )
        assert rpc.cleanup["group_absent"] and rpc.cleanup["leader_reaped"]
    finally:
        rescue(rpc.process)
        print(
            json.dumps(
                {
                    "case": "close-interrupt",
                    "pid": rpc.process.pid,
                    "returncode": rpc.process.returncode,
                    "group_absent": absent(rpc.process.pid),
                }
            )
        )


def test_group_anchor_rechecked_before_escalating_signal(monkeypatch):
    import io
    from types import SimpleNamespace

    probes = []
    signals = []
    rpc = n.MuseConnection.__new__(n.MuseConnection)
    rpc.cleanup = None
    rpc.selector = None

    def owned(_):
        probes.append(True)
        return len(probes) == 1

    rpc._child_waitable = owned
    rpc.process = SimpleNamespace(
        pid=314159,
        returncode=None,
        stdin=io.BytesIO(),
        stdout=io.BytesIO(),
        stderr=io.BytesIO(),
        wait=lambda **k: None,
    )
    monkeypatch.setattr(n.os, "killpg", lambda pid, sig: signals.append(sig))
    monkeypatch.setattr(n.time, "sleep", lambda seconds: None)
    with pytest.raises(ValueError, match="unproven"):
        rpc.close()
    assert signal.SIGTERM in signals and signal.SIGKILL not in signals


def test_cleanup_failure_cannot_report_native_terminal(monkeypatch):
    import hashlib
    from types import SimpleNamespace

    grant = {
        "client": "muse",
        "native_protocol": binding(),
        "native_session_id": "01990000-0000-7000-8000-000000000022",
        "workspace": "/fixture",
        "binary": {"path": "/fixture/binary", "sha256": "a" * 64, "size": 4},
        "max_wall_seconds": 30,
        "max_output_bytes": 65536,
        "resume_command_id": n.command_id(),
        "turn_command_id": n.command_id(),
        "native_posture": {
            "schema_version": 1,
            "profile": "muse-restricted-v1",
            "sandbox_enabled": True,
            "network": "restricted",
            "shell_enabled": True,
            "write_enabled": True,
            "workspace_trust": False,
            "approval_mode": "onRequest",
        },
    }

    class RPC:
        def __init__(self, *a, **kw):
            self.wire = hashlib.sha256()
            self.size = 0
            self.stderr = b""
            self.process = SimpleNamespace(returncode=None)
            self.deadline = time.monotonic() + 30
            self.cleanup = {"group_absent": False, "leader_reaped": False}

        def initialize(self):
            return initialized()

        def call(self, method, payload):
            if method == "session/resume":
                return complete_resume(
                    {
                        "session": {
                            "sessionId": grant["native_session_id"],
                            "status": "idle",
                            "activeTurnId": None,
                            "forkedFrom": None,
                            "workspaceRoot": "/fixture",
                            "path": "/fixture/log",
                            "approvalMode": {
                                "mode": "onRequest",
                                "source": "startup",
                                "lastCommandId": None,
                            },
                        },
                        "pendingRequests": [],
                    }
                )
            return {
                "commandId": grant["turn_command_id"],
                "status": "accepted",
                "disposition": "started",
                "startedNewTurn": True,
                "turnId": "native-turn",
            }

        def terminal(self, *args):
            return terminal(args[0], args[1])

        def close(self):
            raise ValueError("synthetic unresolved group")

    monkeypatch.setattr(n, "MuseConnection", RPC)
    monkeypatch.setattr(n, "binary_identity", lambda path: grant["binary"])
    result = n.launch(
        grant, "fixture", send_admitted=lambda call: call(), cancelled=lambda: False
    )
    assert result["status"] == "unknown" and result["cancellation_outcome"] == "UNKNOWN"
    assert (
        result["cleanup_error"] == "synthetic unresolved group"
        and result["task_accepted"] is False
    )
    assert result["terminal"] == terminal(grant["native_session_id"], "native-turn"), (
        "retain observation without grading it success"
    )
