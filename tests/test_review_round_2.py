"""Review round 2 of 5.23.1 (releases from the protected runtime): N1, N2 and N4, and git by its real path.

N1: a Codex workdir, or a terminal tab's cwd, of `~/.synthesis/v5/current/..` was placed by its text (`normpath`), but
the kernel follows `current` first, so the command ran in `releases/` and overwrote the runtime's guard. N2: the release
launcher kept `SYNTHESIS_HOME`, so a profile's value moved the run, and its fresh clone, to a home the guard does not
protect. N4: a Mac moved to 5.23.1 by 5.23.0's own session start kept 5.23.0's launchers, unpinned and with no
`synthesis-release`, because no later session start rewrote them. And Apple's `/usr/bin/git` is a shim that finds the
git it runs through `xcrun_db`, a file in this user's own temporary folder that holds each tool's path, so the launchers
put the real git first on PATH, found and checked as the interpreter is.
"""

import io
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from synthesis import guards, hook, install, paths

ROOT = Path(__file__).resolve().parents[1]
OLD_HOOK = '#!/bin/sh\nd=$(cd "$(dirname "$0")/.." && pwd)\nexec python3 -S "$d/current/synthesis/hook.py" "$@"\n'


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    for key, value in (("HOME", home), ("SYNTHESIS_HOME", home / ".synthesis" / "v5"), ("CLAUDE_CONFIG_DIR", home / ".claude"),
                       ("CODEX_HOME", home / ".codex"), ("XDG_DATA_HOME", home / ".local" / "share")):
        monkeypatch.setenv(key, str(value))
    home.mkdir()
    install.install(ROOT)
    return home


def _check(tool, tool_input, cwd):
    return guards.check(tool, tool_input, {}, cwd=str(cwd), session={"session_id": "S-1"})


def test_n1_a_workdir_or_a_tab_through_current_and_dotdot_is_placed_where_the_kernel_runs_it(home, tmp_path):
    release = Path(os.path.realpath(paths.home() / "current")).name
    through = f"{paths.home() / 'current'}/.."  # the kernel follows `current` first: this is releases/
    line = f"printf x > {release}/synthesis/guards.py"
    said = _check("exec_command", {"cmd": line, "workdir": through}, tmp_path)
    assert said and said.startswith("Refused"), said
    said = _check("mcp__terminal__run_in_terminal", {"command": line, "cwd": through}, tmp_path)
    assert said and said.startswith("Refused"), said
    said = _check("Bash", {"command": f"git -C {through} rm -q --cached {release}/HASH"}, tmp_path)
    assert said, said  # git -C changes folder as the kernel does too


def test_n2_the_launchers_run_their_own_home_whatever_the_caller_exports(home, tmp_path):
    python = install.pinned(paths.home())
    if not python:
        pytest.skip("no interpreter owned by root on this machine to pin")
    probe = tmp_path / "probe.py"
    probe.write_text("import json, os\nprint(json.dumps(dict(os.environ)))\n")
    launcher = tmp_path / "launch"
    launcher.write_text(install.launcher_text(python, shlex.quote(str(probe)), home=paths.home()))
    launcher.chmod(0o755)
    seen = json.loads(subprocess.run([str(launcher)], env={**os.environ, "SYNTHESIS_HOME": str(tmp_path / "elsewhere")},
                                     capture_output=True, text=True, check=True).stdout)
    assert seen["SYNTHESIS_HOME"] == str(paths.home()), seen["SYNTHESIS_HOME"]
    text = (paths.home() / "bin" / "synthesis-release").read_text(encoding="utf-8")
    assert f"SYNTHESIS_HOME={shlex.quote(str(paths.home()))}" in text


def _session_start(monkeypatch, plugin=""):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"session_id": "S-1", "cwd": str(ROOT)})))
    hook.main(["hook.py", "session-start", *([str(plugin)] if plugin else [])])


def test_n4_a_session_start_rewrites_launchers_that_differ_from_what_this_runtime_writes(home, monkeypatch, capsys):
    python = install.pinned(paths.home())
    if not python:
        pytest.skip("no interpreter owned by root on this machine to pin")
    bin_dir = paths.home() / "bin"
    (bin_dir / "synthesis-hook").write_text(OLD_HOOK)  # what 5.23.0's session start left behind
    (bin_dir / "synthesis-release").unlink()
    (paths.home() / "git-hooks" / "commit-msg").write_text("#!/bin/sh\nexec python3 -S x \"$@\"\n")
    _session_start(monkeypatch, ROOT)
    capsys.readouterr()
    python = install.pinned(paths.home())
    assert python and not install.interpreter_problems(python)
    for name in (*install.ENTRY_POINTS, *install.GIT_HOOKS):
        folder = "git-hooks" if name in install.GIT_HOOKS else "bin"
        assert (paths.home() / folder / name).read_text(encoding="utf-8") == install.launcher(paths.home(), python, name), name
    (bin_dir / "synthesis-release").unlink()
    _session_start(monkeypatch)  # a harness that passes no plugin folder: the launchers are put right all the same
    capsys.readouterr()
    assert (bin_dir / "synthesis-release").is_file()


def test_git_runs_by_its_real_path_never_through_apples_shim_or_a_folder_this_user_writes(home, tmp_path):
    git = install.pinned_git()
    if sys.platform == "darwin":
        assert not git.startswith("/usr/bin/"), git  # the shim reads its target from a file this user owns
    if not git:
        pytest.skip("no git owned by root on this machine to pin")
    assert os.path.realpath(git) == git and install.interpreter_problems(git) == []
    python = install.pinned(paths.home())
    if not python:
        pytest.skip("no interpreter owned by root on this machine to pin")
    probe = tmp_path / "probe.py"
    probe.write_text("import os, shutil\nprint(os.environ['PATH'])\nprint(os.path.realpath(shutil.which('git')))\n")
    launcher = tmp_path / "launch"
    launcher.write_text(install.launcher_text(python, shlex.quote(str(probe)), home=paths.home()))
    launcher.chmod(0o755)
    planted = tmp_path / "planted"
    planted.mkdir()
    (planted / "git").write_text("#!/bin/sh\nexit 0\n")
    (planted / "git").chmod(0o755)
    path, found = subprocess.run([str(launcher)], env={**os.environ, "PATH": f"{planted}:{os.environ['PATH']}"},
                                 capture_output=True, text=True, check=True).stdout.split("\n")[:2]
    assert path.startswith(os.path.dirname(git) + ":") and found == git, (path, found)
