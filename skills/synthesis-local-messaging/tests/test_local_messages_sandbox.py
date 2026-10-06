# SPDX-License-Identifier: Apache-2.0
"""The OS sandbox runner, moved from the old autopilot engine with its tests (autopilot row G)."""

from __future__ import annotations

import json
from pathlib import Path
import socket
import sys
import time

import pytest

import os_sandbox


def test_actual_sandbox_denies_private_reads_host_writes_and_network(tmp_path, need_sandbox):
    root = tmp_path / "worker"
    root.mkdir()
    private = tmp_path / "secret.txt"
    private.write_text("private-sentinel")
    script = root / "check.py"
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    try:
        script.write_text(
            "import json,socket\nresults=[]\n"
            f"for operation in [lambda:open({str(private)!r}).read(),lambda:open({str(private)!r},'w').write('changed'),"
            f"lambda:socket.create_connection(('127.0.0.1',{listener.getsockname()[1]}),timeout=.2)]:\n"
            " try: operation();results.append('permitted')\n except OSError: results.append('denied')\nprint(json.dumps(results))\n")
        result = os_sandbox.run_python_check(script, root)
        assert result["returncode"] == 0, result
        assert json.loads(result["stdout"]) == ["denied"] * 3
        assert private.read_text() == "private-sentinel"
    finally:
        listener.close()


def test_sandbox_output_and_a_closed_pipe_process_stay_bounded(tmp_path, need_sandbox):
    script = tmp_path / "check.py"
    script.write_text('while True: print("x"*4096,flush=True)\n')
    result = os_sandbox.run_python_check(script, tmp_path, timeout_seconds=.4, output_limit=8192)
    assert result["output_exceeded"] is True
    assert len(result["stdout"].encode()) <= 8192
    script.write_text("import os,time\nos.close(1);os.close(2);time.sleep(30)\n")
    started = time.monotonic()
    result = os_sandbox.run_python_check(script, tmp_path, timeout_seconds=.2)
    assert result["timed_out"] is True
    assert time.monotonic() - started < 2


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS process isolation boundary")
def test_mac_worker_cannot_fork_or_spawn_a_process_outside_the_deadline(tmp_path, need_sandbox):
    script = tmp_path / "check.py"
    script.write_text(
        "import json,os,sys\nresults=[]\ntry:\n pid=os.fork()\n if pid==0:os._exit(0)\n os.waitpid(pid,0);results.append('forked')\n"
        "except OSError:results.append('denied')\ntry:\n pid=os.posix_spawn(sys.executable,[sys.executable,'-I','-c','pass'],{})\n"
        " os.waitpid(pid,0);results.append('spawned')\nexcept OSError:results.append('denied')\nprint(json.dumps(results))\n")
    result = os_sandbox.run_python_check(script, tmp_path)
    assert result["returncode"] == 0, result
    assert json.loads(result["stdout"]) == ["denied", "denied"]


def test_missing_sandbox_never_runs_the_code(tmp_path, monkeypatch):
    script = tmp_path / "check.py"
    marker = tmp_path / "ran"
    script.write_text(f"open({str(marker)!r},'w').write('x')\n")
    monkeypatch.setattr(os_sandbox, "sandbox_available", lambda: False)
    with pytest.raises(ValueError, match="sandbox is unavailable"):
        os_sandbox.run_python_check(script, tmp_path)
    assert not marker.exists()


def test_check_script_outside_its_root_is_refused(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("pass\n")
    with pytest.raises(ValueError, match="outside the admitted root"):
        os_sandbox.run_python_check(outside, root)


def test_no_sandbox_on_this_platform_means_no_command(tmp_path, monkeypatch):
    monkeypatch.setattr(os_sandbox.platform, "system", lambda: "Windows")
    with pytest.raises(ValueError, match="unavailable"):
        os_sandbox._sandbox_command(tmp_path, tmp_path, tmp_path / "check.py", [])


def test_linux_sandbox_preserves_loader_library_paths(tmp_path, monkeypatch):
    """ELF interpreters use /lib or /lib64 even on a usr-merged host."""
    exists, resolve = Path.exists, Path.resolve
    aliases = {"/lib", "/lib64"}
    monkeypatch.setattr(os_sandbox.platform, "system", lambda: "Linux")
    monkeypatch.setattr(os_sandbox.shutil, "which", lambda name: "/usr/bin/bwrap")
    monkeypatch.setattr(Path, "exists", lambda path: True if str(path) in aliases else exists(path))
    monkeypatch.setattr(Path, "resolve", lambda path, *a, **kw: Path("/usr/lib") if str(path) in aliases else resolve(path, *a, **kw))
    command, provider = os_sandbox._sandbox_command(tmp_path, tmp_path / "scratch", tmp_path / "check.py", [])
    mounts = [tuple(command[i:i + 3]) for i, value in enumerate(command) if value in {"--ro-bind", "--bind"}]
    for alias in aliases:
        assert ("--ro-bind", alias, alias) in mounts
    assert provider == "linux-bubblewrap"
    assert "--unshare-all" in command
    assert command[command.index("--remount-ro") + 1] == "/"
    assert ("--ro-bind", "/", "/") not in mounts
    assert [item for item in mounts if item[0] == "--bind"] == [("--bind", str(tmp_path / "scratch"), str(tmp_path / "scratch"))]
