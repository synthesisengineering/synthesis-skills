# SPDX-License-Identifier: Apache-2.0
"""The OS sandbox, moved from the old autopilot engine with its tests (autopilot row G). Each check runs
through the same `_sandbox_command` and process settings the reader's `run_page` uses."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

import pytest

import local_messaging as lm
from local_messaging_fixtures import add, imessage, request
import os_sandbox


def confined(script: Path, root: Path) -> subprocess.CompletedProcess:
    """Run `script` as run_page runs its worker: `root` read-only, a fresh writable scratch folder."""
    with tempfile.TemporaryDirectory(prefix="local-messaging-") as name:
        scratch = Path(name).resolve()
        command, _ = os_sandbox._sandbox_command(root, scratch, script, [])
        command.insert(command.index("-I"), "-B")
        env = {"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "TMPDIR": str(scratch)}
        return subprocess.run(command, cwd=scratch, env=env, capture_output=True, text=True, timeout=15)


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
            f"lambda:open({str(root / 'written')!r},'w').write('x'),"
            f"lambda:socket.create_connection(('127.0.0.1',{listener.getsockname()[1]}),timeout=.2)]:\n"
            " try: operation();results.append('permitted')\n except OSError: results.append('denied')\nprint(json.dumps(results))\n")
        result = confined(script, root)
        assert result.returncode == 0, result
        assert json.loads(result.stdout) == ["denied"] * 4
        assert private.read_text() == "private-sentinel" and not (root / "written").exists()
    finally:
        listener.close()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS process isolation boundary")
def test_mac_worker_cannot_fork_or_spawn_a_process(tmp_path, need_sandbox):
    script = tmp_path / "check.py"
    script.write_text(
        "import json,os,sys\nresults=[]\ntry:\n pid=os.fork()\n if pid==0:os._exit(0)\n os.waitpid(pid,0);results.append('forked')\n"
        "except OSError:results.append('denied')\ntry:\n pid=os.posix_spawn(sys.executable,[sys.executable,'-I','-c','pass'],{})\n"
        " os.waitpid(pid,0);results.append('spawned')\nexcept OSError:results.append('denied')\nprint(json.dumps(results))\n")
    result = confined(script, tmp_path)
    assert result.returncode == 0, result
    assert json.loads(result.stdout) == ["denied", "denied"]


def test_missing_sandbox_means_the_reader_runs_nothing(tmp_path, monkeypatch):
    path, db = imessage(tmp_path / "source")
    add(db)
    db.close()
    monkeypatch.setattr(os_sandbox.platform, "system", lambda: "Windows")
    started = []
    monkeypatch.setattr(lm.subprocess, "run", lambda *a, **kw: started.append(a))
    with pytest.raises(ValueError, match="sandbox is unavailable"):
        lm.run_page({**request(path), "after": 0, "upper": None})
    assert started == []


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
