"""Combined review round 1 of 22.8 with 22.18 (64b430ff): C2, C10, C7a, and C1 on the open list. C8 is in the release
tool's own tests (test_skills_manager_release_combined_1.py) and in tests/test_release_grant.py.

C2: the launcher's `<shell> -c '<line>'` wrapper was taken for the launcher by the shell's basename alone, so a program
of the agent's named bash, sh or zsh carried the launcher's line, minted the grant, and ran with nothing else judged.
C10: install.py's `dict | None` annotations had no `from __future__ import annotations`, so the runtime did not load on
Python 3.9, the oldest interpreter it pins (Apple's Command Line Tools Python). C7a: the guard read the checkout's
manifest to its end, so a FIFO there stopped it. C1 (crafted, open): a program in the installer's own process that
replaces install's bound names by names built at run time passes the guard. C2's remainder (crafted, open): a shell put
ahead of the system's on the harness's PATH after the line has passed runs in its place.
"""

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from synthesis import guards, install, paths

ROOT = Path(__file__).resolve().parents[1]
STUB = "def check(*args, **kwargs):\n    return None\n"
JUDGE = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from synthesis import guards
for line in json.loads(sys.argv[2]):
    print(json.dumps(guards.check("Bash", {"command": line}, {}, cwd=sys.argv[3], session={"session_id": "S-agent"})))
"""


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A home of the test's own with the runtime installed from this tree, and `judge`, which runs the guard from that
    runtime with this process's environment (its PATH is the harness's)."""
    home = tmp_path / "home"
    for key, value in (("HOME", home), ("SYNTHESIS_HOME", home / ".synthesis" / "v5"), ("CLAUDE_CONFIG_DIR", home / ".claude"),
                       ("CODEX_HOME", home / ".codex"), ("XDG_DATA_HOME", home / ".local" / "share"),
                       ("SYNTHESIS_CLAUDE_DESKTOP_DIR", home / "Library" / "Application Support" / "Claude")):
        monkeypatch.setenv(key, str(value))
    for key in ("SYNTHESIS_SESSION", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "MUSE_SESSION_ID", "CDPATH", "OLDPWD"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")  # the harness's own (the hook's launcher would put its folders first)
    install.install(ROOT)
    work = tmp_path / "work"
    work.mkdir()

    def judge(*lines):
        done = subprocess.run([sys.executable, "-I", "-S", "-c", JUDGE, str(paths.home() / "current"), json.dumps(list(lines)),
                               str(work)], capture_output=True, text=True, timeout=300, env=dict(os.environ))
        assert done.returncode == 0, done.stderr[-2000:]
        return [json.loads(line) for line in done.stdout.splitlines()]
    return {"v5": paths.home(), "work": work, "judge": judge, "tmp": tmp_path}


def _line(world) -> str:
    return f"{world['v5'] / 'bin' / 'synthesis-release'} --install-only --tag v99.0.0"


def _grants(world) -> list:
    folder = world["v5"] / "state" / "release-grants"
    return sorted(folder.glob("*.json")) if folder.is_dir() else []


# --- C2: the shell a wrapped line names must be one no user can write -------------------------------------------------

@pytest.mark.parametrize("form", ["{tools}/bash -c '{line}'", "tools/sh -c '{line}'", "{tools}/zsh -lc '{line}'"],
                         ids=["a program named bash", "a program named sh, by a relative path", "a program named zsh, -lc"])
def test_c2_a_program_named_as_a_shell_is_not_the_launchers_line(world, form):
    tools = world["work"] / "tools"
    tools.mkdir(exist_ok=True)
    for name in ("bash", "sh", "zsh"):
        (tools / name).write_text("#!/bin/sh\nexit 0\n")
        (tools / name).chmod(0o755)
    said, = world["judge"](form.format(tools=tools, line=_line(world)))
    assert said is not None and not _grants(world), said


def test_c2_a_bare_shell_found_first_in_a_folder_a_user_writes_is_not_the_launchers_line(world, monkeypatch):
    tools = world["tmp"] / "tools"  # this user's own, first on the harness's PATH, with a `bash` of the agent's in it
    tools.mkdir()
    (tools / "bash").write_text("#!/bin/sh\nexit 0\n")
    (tools / "bash").chmod(0o755)
    monkeypatch.setenv("PATH", f"{tools}:/usr/bin:/bin:/usr/sbin:/sbin")
    said, = world["judge"](f"bash -lc '{_line(world)}'")
    assert said is not None and not _grants(world), said


def test_c2_control_the_systems_shell_carrying_the_launchers_line_passes_and_mints(world):
    assert world["judge"](f"/bin/bash -c '{_line(world)}'", f"bash -lc '{_line(world)}'") == [None, None]
    assert len(_grants(world)) == 1


def test_c2_control_folders_a_user_writes_first_on_path_leave_the_line_to_the_systems_shell(world, monkeypatch):
    """As on the principal's Mac and CI's runners: folders this user writes come first on the harness's PATH, and the
    first `bash` on it is the system's. Codex's shell tool hands the launcher's line to that `bash` (A7)."""
    mine = world["tmp"] / "mine"
    mine.mkdir()
    monkeypatch.setenv("PATH", f"{mine}:/usr/bin:/bin:/usr/sbin:/sbin")
    assert world["judge"](f"bash -lc '{_line(world)}'") == [None] and len(_grants(world)) == 1


@pytest.mark.xfail(strict=True, reason="open, crafted (C2's remainder): a shell put in a folder a user writes, ahead of "
                   "the system's on PATH, after the line passed and before the harness looks the shell up, runs instead")
def test_c2_open_no_shell_of_the_agents_can_be_put_ahead_of_the_systems_once_the_line_has_passed(world, monkeypatch):
    mine = world["tmp"] / "mine"
    mine.mkdir()
    monkeypatch.setenv("PATH", f"{mine}:/usr/bin:/bin:/usr/sbin:/sbin")
    said, put = world["judge"](f"bash -lc '{_line(world)}'", f"cp /bin/sh {mine}/bash")  # the race's two steps
    assert said is not None or put is not None, "the line passed, and a bash of the agent's may then be put ahead"


def test_c2_a_link_this_user_can_repoint_is_not_the_systems_shell(world, monkeypatch):
    """A link of this user's that leads to the system's shell, or to the folder it is in, passes the test of the file it
    leads to; but this user can point it at a program of the agent's once the line has passed, before the shell runs."""
    links = world["tmp"] / "links"
    links.mkdir()
    (links / "bash").symlink_to("/bin/bash")
    said, = world["judge"](f"{links}/bash -c '{_line(world)}'")
    assert said is not None and not _grants(world), said
    system = world["tmp"] / "system"
    system.symlink_to("/bin")
    monkeypatch.setenv("PATH", f"{system}:/usr/bin:/bin")
    said, = world["judge"](f"bash -lc '{_line(world)}'")
    assert said is not None and not _grants(world), said


# --- C10: every runtime module loads on the oldest Python the runtime pins ---------------------------------------------

def _version(python: str) -> tuple:
    try:
        done = subprocess.run([python, "-I", "-S", "-c", "import sys; print(sys.version_info[0], sys.version_info[1])"],
                              capture_output=True, text=True, timeout=60, env={})
    except (OSError, subprocess.SubprocessError):
        return ()
    return tuple(int(n) for n in done.stdout.split()) if done.returncode == 0 else ()


OLDEST = next((p for p in (sys.executable, "/Library/Developer/CommandLineTools/usr/bin/python3", shutil.which("python3.9") or "")
               if p and _version(p) == (3, 9)), "")


@pytest.mark.skipif(not OLDEST, reason="no Python 3.9 here (CI's 3.9 job runs this file under it)")
def test_c10_every_runtime_module_loads_on_the_oldest_python_the_runtime_pins(tmp_path):
    modules = sorted(p.stem for p in (ROOT / "synthesis").glob("*.py") if p.stem != "__main__")  # that one runs the CLI
    code = "import importlib, sys; sys.path.insert(0, sys.argv[1]); [importlib.import_module('synthesis.' + m) for m in sys.argv[2:]]"
    done = subprocess.run([OLDEST, "-I", "-S", "-c", code, str(ROOT), *modules], capture_output=True, text=True, timeout=300,
                          env={"HOME": str(tmp_path), "SYNTHESIS_HOME": str(tmp_path / "v5")})
    assert done.returncode == 0, done.stderr[-2000:]


# --- C7a: the checkout's manifest is read as the guard reads a file it may not wait on ----------------------------------

def test_c7a_a_fifo_for_the_checkouts_manifest_does_not_stop_the_guard(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path / "v5"))
    checkout = tmp_path / "synthesis-skills"
    (checkout / ".claude-plugin").mkdir(parents=True)
    fifo = checkout / ".claude-plugin" / "plugin.json"
    os.mkfifo(fifo)
    done = threading.Event()
    threading.Thread(target=lambda: (guards._grant_release({"--repo-root": str(checkout)}, "line"), done.set()), daemon=True).start()
    finished = done.wait(10)
    if not finished:  # free the reader this test left waiting
        os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
    assert finished, "the guard waited on the FIFO named as the checkout's manifest"
    assert not list((tmp_path / "v5").rglob("release-grants/*.json"))  # nothing read, nothing granted


# --- C1, on the open list: names built at run time aimed at install's bound names -------------------------------------

@pytest.mark.xfail(strict=True, reason="C1, open (crafted): a program in the installer's own process that replaces "
                                       "install's bound names by names built at run time passes the guard")
@pytest.mark.parametrize("name,value", [("_appr' + 'ove", "lambda *a, **k: None"), ("_rele' + 'ased", "lambda *a, **k: True")],
                         ids=["_approve replaced", "_released replaced"])
def test_c1_a_program_replacing_a_bound_name_by_a_built_name_waits_or_installs_nothing(world, name, value):
    evil = world["tmp"] / "my-plugin"
    shutil.copytree(os.path.realpath(world["v5"] / "current"), evil, ignore=shutil.ignore_patterns("__pycache__", "HASH", "SOURCE"))
    (evil / "synthesis" / "guards.py").write_text(STUB)
    program = ("import importlib as m, os, sys; sys.path.insert(0, os.environ['T']); i = m.import_module('synth' + 'esis.install'); "
               f"setattr(i, '{name}', {value}); getattr(i, 'inst' + 'all')(os.environ['F'])")
    line = f"T={ROOT} F={evil} python3 -c \"{program}\""
    said, = world["judge"](line)
    if said is None:
        subprocess.run(["/bin/sh", "-c", line], capture_output=True, text=True, timeout=300,
                       env={**os.environ, "PATH": f"{os.path.dirname(sys.executable)}:/usr/bin:/bin"})
    replaced = (Path(os.path.realpath(world["v5"] / "current")) / "synthesis" / "guards.py").read_text() == STUB
    assert not (said is None and replaced), "passed with no code, and the runtime is now the agent's"
