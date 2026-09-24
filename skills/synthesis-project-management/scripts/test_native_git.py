"""Native identity queries retain descriptor isolation and bounded execution."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

from test_claim_scope_cache import checkouts  # noqa: F401


@pytest.fixture
def native_git():
    return importlib.import_module("native_git")


@pytest.mark.parametrize("query", [
    ("config", "--null", "--show-origin", "--list"),
    ("rev-parse", "--path-format=absolute", "--git-common-dir", "--show-toplevel"),
    ("worktree", "list", "--porcelain", "-z"),
    ("rev-parse", "--show-toplevel", "--symbolic-full-name", "HEAD"),
])
def test_fixed_native_queries_match_ordinary_subprocess_byte_for_byte(native_git, checkouts, query):
    for repository in checkouts:
        command = ["git", "--no-optional-locks", "-C", str(repository), *query]
        expected = subprocess.run(command, capture_output=True, timeout=10)
        actual = native_git.run(command, capture_output=True, timeout=10)
        assert (actual.returncode, actual.stdout, actual.stderr) == (expected.returncode, expected.stdout, expected.stderr)


def test_native_query_honors_cwd_environment_and_text_mode(native_git, checkouts):
    repository, _ = checkouts
    env = {**os.environ, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "fixture.observed", "GIT_CONFIG_VALUE_0": "exact-value"}
    command = ["git", "config", "--null", "--show-origin", "--list"]
    expected = subprocess.run(command, cwd=repository, env=env, capture_output=True, text=True, timeout=10)
    actual = native_git.run(command, cwd=repository, env=env, capture_output=True, text=True, timeout=10)
    assert (actual.returncode, actual.stdout, actual.stderr) == (expected.returncode, expected.stdout, expected.stderr)
    assert "exact-value" in actual.stdout


@pytest.mark.parametrize("argv", [["git", "commit"], [sys.executable, "--version"], ["git", "-c", "alias.fixture=!false", "fixture"]])
def test_public_query_entry_refuses_unregistered_argv(native_git, argv):
    with pytest.raises(ValueError):
        native_git.run(argv, capture_output=True)


def _secret_probe(path):
    info = path.stat()
    return ("import os,json; found=[]\n"
            "for fd in range(3,512):\n"
            " try:\n"
            "  s=os.fstat(fd)\n"
            f"  if (s.st_dev,s.st_ino)==({info.st_dev},{info.st_ino}): found.append(fd)\n"
            " except OSError: pass\n"
            "print(json.dumps(found))")


def test_inheritable_secret_fd_is_closed_with_concurrent_descriptor_creation(native_git, tmp_path):
    secret = tmp_path / "private-descriptor"
    secret.write_text("synthetic fixture only")
    descriptor = os.open(secret, os.O_RDONLY)
    os.set_inheritable(descriptor, True)
    probe = _secret_probe(secret)
    stop = threading.Event()
    descriptors = [descriptor]
    def churn():
        while not stop.is_set():
            current = os.open(secret, os.O_RDONLY)
            os.set_inheritable(current, True)
            descriptors.append(current)
            time.sleep(0.0001)
            os.close(current)
    worker = threading.Thread(target=churn)
    worker.start()
    try:
        for _ in range(12):
            done = native_git._spawn([sys.executable, "-I", "-c", probe])
            assert done.returncode == 0
            assert json.loads(done.stdout) == []
    finally:
        stop.set()
        worker.join(timeout=2)
        os.close(descriptor)
    assert not worker.is_alive()
    assert max(descriptors) < 512  # The negative probe covers every race FD.


@pytest.mark.skipif(sys.platform != "darwin", reason="Darwin atomic spawn flag positive control")
def test_darwin_secret_fd_positive_control_depends_on_atomic_cloexec_flag(native_git, tmp_path, monkeypatch):
    assert native_git._get_darwin_api() is not None
    secret = tmp_path / "positive-control"
    secret.write_text("synthetic fixture only")
    descriptor = os.open(secret, os.O_RDONLY)
    os.set_inheritable(descriptor, True)
    try:
        with monkeypatch.context() as changed:
            changed.setattr(native_git, "_CLOEXEC_DEFAULT", 0)
            visible = native_git._spawn([sys.executable, "-I", "-c", _secret_probe(secret)])
        assert descriptor in json.loads(visible.stdout)
        closed = native_git._spawn([sys.executable, "-I", "-c", _secret_probe(secret)])
        assert json.loads(closed.stdout) == []
    finally:
        os.close(descriptor)


def test_closed_parent_stdio_does_not_alias_spawn_file_actions(native_git, tmp_path):
    report = tmp_path / "closed-stdio.json"
    script = (
        "import os,sys,json\n"
        f"sys.path.insert(0,{str(Path(native_git.__file__).parent)!r})\n"
        "import native_git\n"
        "for fd in (0,1,2): os.close(fd)\n"
        "result=native_git._spawn([sys.executable,'-I','-c',"
        "\"import os,sys; assert os.read(0,1)==b''; print('stdout'); print('stderr',file=sys.stderr)\"])\n"
        f"with open({str(report)!r},'w') as f: json.dump([result.returncode,result.stdout.decode(),result.stderr.decode()],f)\n"
    )
    done = subprocess.run([sys.executable, "-I", "-c", script], capture_output=True, timeout=10)
    assert done.returncode == 0
    assert json.loads(report.read_text()) == [0, "stdout\n", "stderr\n"]


@pytest.mark.parametrize("failure", ["timeout", "combined-output-limit"])
def test_failed_child_is_killed_and_reaped_with_bounded_capture(native_git, monkeypatch, failure):
    original = native_git._start_process
    pids = []
    def started(*args, **kwargs):
        process = original(*args, **kwargs)
        pids.append(process.pid)
        return process
    monkeypatch.setattr(native_git, "_start_process", started)
    program = "import time; time.sleep(10)" if failure == "timeout" else "import os,time; os.write(1,b'x'*600); os.write(2,b'y'*600); time.sleep(10)"
    expected = subprocess.TimeoutExpired if failure == "timeout" else native_git.OutputLimitExceeded
    start = time.monotonic()
    with pytest.raises(expected):
        native_git._spawn([sys.executable, "-I", "-c", program], timeout=0.05 if failure == "timeout" else 2, max_output_bytes=1024)
    assert time.monotonic() - start < 1
    assert len(pids) == 1
    with pytest.raises(ChildProcessError):
        os.waitpid(pids[0], os.WNOHANG)


def test_missing_native_capability_uses_standard_close_fds_subprocess(native_git, monkeypatch):
    monkeypatch.setattr(native_git, "_get_darwin_api", lambda: None)
    original = native_git.subprocess.Popen
    calls = []
    def started(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)
    monkeypatch.setattr(native_git.subprocess, "Popen", started)
    done = native_git._spawn([sys.executable, "-I", "-c", "print('fallback')"])
    assert done.stdout == b"fallback\n"
    assert len(calls) == 1
    assert calls[0]["close_fds"] is True
    assert not calls[0].get("shell", False)


def test_spawn_errors_release_owned_descriptors(native_git):
    def descriptors():
        result = set()
        for fd in range(3, 256):
            try:
                os.fstat(fd)
                result.add(fd)
            except OSError:
                pass
        return result
    before = descriptors()
    for _ in range(10):
        with pytest.raises(OSError):
            native_git._spawn(["/nonexistent-synthetic-fixture/program"])
    assert descriptors() == before


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_invalid_deadline_is_rejected_before_spawn(native_git, timeout):
    with pytest.raises(ValueError):
        native_git._spawn([sys.executable, "-I", "-c", "raise AssertionError('must not execute')"], timeout=timeout)
