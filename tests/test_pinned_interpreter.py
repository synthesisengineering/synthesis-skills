"""Review round 1 of 5.23.1 (P1, P3, A4): every entry point runs an interpreter pinned at install, isolated.

The hook launcher ran `python3 -S` from PATH. On the principal's Mac both harnesses put folders this user writes
(~/Library/Python/3.12/bin, ~/.local/bin) before the real interpreter on PATH, so one file named python3 there replaced
the guard (P1); where python3 is Apple's, one compiled file under ~/Library/Caches/com.apple.python did the same (P3);
and the no-code release ran whatever a .pth file, usercustomize, PYTHONPATH, DEVELOPER_DIR or DYLD_INSERT_LIBRARIES
put in front of it (A4). The reviewer's remedy: at install, pin the interpreter by its real path, accepted only when it
and every folder above it are owned by root and writable by neither this user nor its groups; the launchers in the
protected bin/ run it with -I -S and an environment of named variables only. The hook, the git hooks, the CLI and the
release tool each run through one.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from synthesis import doctor, install

ROOT = Path(__file__).resolve().parents[1]
LAUNCHERS = ("bin/synthesis-hook", "bin/synthesis", "bin/synthesis-release", "git-hooks/pre-commit",
             "git-hooks/pre-merge-commit", "git-hooks/commit-msg")


def _trusted() -> str:
    python = install.pinned_python()
    if not python:
        pytest.skip("no interpreter owned by root on this machine to pin")
    return python


def _planted_dyld(path: str) -> dict:
    """DYLD_INSERT_LIBRARIES for a hostile environment, where macOS's loader strips it from /bin/sh, as System Integrity
    Protection has it do for every program the system protects: there the launcher, a script /bin/sh runs, is what
    clears it before the interpreter starts. With that protection off, as on GitHub's macOS runners, the loader acts on
    /bin/sh itself before any line of a launcher runs, so no launcher can come first, and a planted library that is not
    there stops the shell (the integration review of 5.24.0's CI). Elsewhere the variable means nothing, and is planted."""
    if sys.platform == "darwin":
        done = subprocess.run(["/bin/sh", "-c", 'echo "${DYLD_INSERT_LIBRARIES-stripped}"'], capture_output=True, text=True,
                              env={"PATH": "/usr/bin:/bin", "DYLD_INSERT_LIBRARIES": "/nonexistent/none.dylib"})
        if not (done.returncode == 0 and done.stdout.strip() == "stripped"):
            return {}
    return {"DYLD_INSERT_LIBRARIES": path}


def test_an_interpreter_this_user_can_change_is_never_pinned(tmp_path):
    mine = tmp_path / "bin" / "python3"
    mine.parent.mkdir()
    shutil.copy2(os.path.realpath(sys.executable), mine)
    assert any("not owned by root" in p for p in install.interpreter_problems(str(mine)))
    link = tmp_path / "python-link"
    link.symlink_to(os.path.realpath("/usr/bin/env"))
    assert any("real path" in p for p in install.interpreter_problems(str(link)))
    assert install.interpreter_problems(os.path.realpath("/usr/bin/env")) == []  # root's, and not this user's to change
    assert install.pinned_python([str(mine)]) == ""
    python = _trusted()
    assert install.pinned_python([str(mine), python]) == python and install.interpreter_problems(python) == []


def test_the_launcher_runs_isolated_with_only_the_named_variables(tmp_path):
    python = _trusted()
    probe = tmp_path / "probe.py"
    probe.write_text("import json, os, sys\nprint(json.dumps({'env': dict(os.environ), 'isolated': sys.flags.isolated, "
                     "'no_site': sys.flags.no_site, 'executable': os.path.realpath(sys.executable), 'argv': sys.argv[1:]}))\n")
    launcher = tmp_path / "launch"
    launcher.write_text(install.launcher_text(python, shlex.quote(str(probe))))
    launcher.chmod(0o755)
    hostile = {"PATH": f"{tmp_path}:/usr/bin:/bin", "HOME": str(tmp_path), "PYTHONPATH": str(tmp_path), "PYTHONHOME": "/x",
               "PYTHONSTARTUP": "/x", **_planted_dyld("/x.dylib"), "LD_PRELOAD": "/x.so", "DEVELOPER_DIR": str(tmp_path),
               "GIT_EXEC_PATH": str(tmp_path), "SYNTHESIS_HOME": str(tmp_path / "s"), "CLAUDE_CODE_SESSION_ID": "S-1"}
    seen = json.loads(subprocess.run([str(launcher), "a b", "c"], env=hostile, capture_output=True, text=True,
                                     check=True).stdout)
    assert seen["isolated"] == 1 and seen["no_site"] == 1 and seen["executable"] == python and seen["argv"] == ["a b", "c"]
    own = {k for k in seen["env"] if k.startswith("__CF")}  # what macOS itself gives every process it starts
    assert set(seen["env"]) - own <= set(install.KEPT) | {"PATH"}, sorted(set(seen["env"]) - own - set(install.KEPT))
    assert not [k for k in seen["env"] if k.startswith(("PYTHON", "DYLD_", "LD_", "GIT_EXEC", "DEVELOPER"))]
    git = install.pinned_git()  # the real git's folder first, then the system's (review round 2)
    assert seen["env"]["PATH"].startswith((os.path.dirname(git) + ":" if git else "") + install.SAFE_PATH + ":"), seen["env"]["PATH"]
    assert seen["env"]["SYNTHESIS_HOME"] == str(tmp_path / "s")  # a launcher made with no home keeps the caller's
    assert "SYNTHESIS_CLAUDE_BIN" not in seen["env"]  # a variable left unset stays unset, not empty


def test_every_variable_the_runtime_reads_is_one_the_launchers_keep():
    """Measured with every entry point run once (the review's measurement) and held here by reading the code: each
    variable a module of the runtime asks for by name is on the kept list, or the git hooks' list."""
    asked = set()
    for source in (ROOT / "synthesis").glob("*.py"):
        text = source.read_text(encoding="utf-8")
        asked |= set(re.findall(r"(?:environ\.get\(|environ\[|getenv\()\s*[\"']([A-Z][A-Z0-9_]+)[\"']", text))
        asked |= set(re.findall(r"\"(SYNTHESIS_[A-Z_]+_BIN)\"", text))
    asked -= {"OUT"}  # guards.py's comment on reading a program's own `os.environ["OUT"]`, not a read of its own
    asked -= {"PATH"}  # each launcher sets it itself: its own folders first, then the caller's (the harness's own, C2)
    assert asked <= set(install.KEPT) | set(install.GIT_KEPT), sorted(asked - set(install.KEPT) - set(install.GIT_KEPT))


def _hostile_world(tmp_path, home: Path) -> dict:
    """What an agent can place with no code: a python3 first on PATH, a user site .pth and usercustomize, a module on
    PYTHONPATH and DYLD_INSERT_LIBRARIES, each writing the marker if it ever runs."""
    marker = tmp_path / "placed-code-ran"
    planted = tmp_path / "planted"
    planted.mkdir()
    (planted / "python3").write_text(f"#!/bin/sh\ntouch {marker}\nexec {shlex.quote(os.path.realpath(sys.executable))} \"$@\"\n")
    (planted / "python3").chmod(0o755)
    (planted / "json.py").write_text(f"open({str(marker)!r}, 'w').write('json')\n")
    for site in (home / "Library" / "Python" / f"{sys.version_info[0]}.{sys.version_info[1]}" / "lib" / "python" / "site-packages",
                 home / ".local" / "lib" / f"python{sys.version_info[0]}.{sys.version_info[1]}" / "site-packages"):
        site.mkdir(parents=True)
        (site / "placed.pth").write_text(f"import os; open({str(marker)!r}, 'w').write('pth')\n")
        (site / "usercustomize.py").write_text(f"open({str(marker)!r}, 'w').write('usercustomize')\n")
    env = {**os.environ, "PATH": f"{planted}{os.pathsep}{os.environ.get('PATH', '')}", "PYTHONPATH": str(planted),
           **_planted_dyld(str(planted / "none.dylib")), "HOME": str(home)}
    return {"marker": marker, "env": env}


def test_the_installed_hook_runs_none_of_the_code_an_agent_can_place(tmp_path, isolated_home):
    python = _trusted()
    install.install(ROOT)
    for rel in LAUNCHERS:
        text = (isolated_home / rel).read_text(encoding="utf-8")
        assert f"{shlex.quote(python)} -I -S " in text and "/usr/bin/env -i " in text, rel
        assert not re.search(r"(?:^|\s)python3\s", text.split("\n", 2)[-1]), rel  # nothing found on PATH runs
    world = _hostile_world(tmp_path, tmp_path / "home")
    said = subprocess.run([str(isolated_home / "bin" / "synthesis-hook"), "pre-tool-use"], env=world["env"],
                          input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm -rf ~"}}),
                          capture_output=True, text=True, timeout=60)
    assert json.loads(said.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny", said.stdout + said.stderr
    assert not world["marker"].exists(), world["marker"].read_text()


def test_the_cli_the_commit_check_and_the_release_tool_load_under_isolation(tmp_path, isolated_home):
    _trusted()
    install.install(ROOT)
    world = _hostile_world(tmp_path, tmp_path / "home")
    cli = subprocess.run([str(isolated_home / "bin" / "synthesis"), "--help"], env=world["env"], capture_output=True,
                         text=True, timeout=60)
    assert cli.returncode == 0 and "usage" in cli.stdout.lower(), cli.stderr
    tool = subprocess.run([str(isolated_home / "bin" / "synthesis-release"), "--help"], env=world["env"],
                          capture_output=True, text=True, timeout=60)
    assert tool.returncode == 0 and tool.stdout.startswith("usage: release.py"), tool.stderr
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "notes.md").write_text("plain words\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    done = subprocess.run(["git", "-C", str(repo), "-c", f"core.hooksPath={isolated_home / 'git-hooks'}", "commit", "-qm",
                           "Plain words"], env={**{k: v for k, v in world["env"].items() if not k.startswith("DYLD_")},
                                                "SYNTHESIS_HOME": str(isolated_home)}, capture_output=True,
                          text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert not world["marker"].exists(), world["marker"].read_text()


def test_with_no_interpreter_that_may_be_pinned_install_stops_and_the_launchers_refuse(tmp_path, isolated_home, monkeypatch):
    """Since review round 3 (M3) an install with nothing to pin stops, naming what to install; a session start that
    finds its pinned interpreter gone and nothing to pin writes launchers that refuse, so the hooks fail closed."""
    _trusted()
    install.install(ROOT)
    monkeypatch.setattr(install, "pinned_python", lambda candidates=None: "")
    with pytest.raises(install.Refused, match="python.org"):
        install.install(ROOT)
    pinned = install.pinned
    monkeypatch.setattr(install, "pinned", lambda home: "")  # the pinned interpreter is gone
    install.refresh_launchers(isolated_home)
    said = subprocess.run([str(isolated_home / "bin" / "synthesis-hook"), "pre-tool-use"], input="{}",
                          capture_output=True, text=True, timeout=60)
    assert said.returncode == 2 and "owned by root" in said.stderr, said.stderr
    monkeypatch.setattr(install, "pinned", pinned)
    assert doctor.check_hook_script(isolated_home).status == "fail"


def test_the_doctor_checks_the_pin_and_every_launcher(tmp_path, isolated_home):
    _trusted()
    install.install(ROOT)
    check = doctor.check_hook_script(isolated_home)
    assert check.status == "ok" and install.pinned(isolated_home) in check.detail, check
    mine = tmp_path / "python3"
    shutil.copy2(os.path.realpath(sys.executable), mine)
    for rel in ("bin/synthesis", "git-hooks/commit-msg"):
        launcher = isolated_home / rel
        before = launcher.read_text(encoding="utf-8")
        launcher.write_text(before.replace(" -I -S ", " -S "), encoding="utf-8")  # isolation dropped
        assert doctor.check_hook_script(isolated_home).status == "fail", rel
        launcher.write_text(before, encoding="utf-8")
    hook = isolated_home / "bin" / "synthesis-hook"
    hook.write_text(install.launcher_text(str(mine), "x"), encoding="utf-8")  # an interpreter this user can change
    check = doctor.check_hook_script(isolated_home)
    assert check.status == "fail" and "owned by root" in check.detail, check


# --- A5 (2026-11-17): the hooks follow the Mac's newest Python. The installer pins the newest final release among the
# acceptable interpreters, from 3.9 to the newest the checks test (install.TESTED), never one newer or not yet released.
# Until 5.24.1 it pinned the first acceptable one, the interpreter running the install, so a Mac whose default moved to
# 3.15 kept its hooks on 3.12. -----------------------------------------------------------------------------------------

def _fake(folder: Path, name: str, says: str) -> str:
    """A stand-in interpreter that prints what `pinned_python` asks a candidate for: major, minor and release level."""
    path = folder / name
    path.write_text(f"#!/bin/sh\necho '{says}'\n", encoding="utf-8")
    path.chmod(0o755)
    return os.path.realpath(path)


def test_the_newest_final_python_the_checks_test_is_pinned(tmp_path, monkeypatch):
    monkeypatch.setattr(install, "interpreter_problems", lambda path: [])  # each stands in for one owned by root
    old, new = _fake(tmp_path, "py312", "3 12 final"), _fake(tmp_path, "py315", "3 15 final")
    assert install.pinned_python([old, new]) == new and install.pinned_python([new, old]) == new
    newer = _fake(tmp_path, "py316", f"3 {install.TESTED[1] + 1} final")
    assert install.pinned_python([old, newer]) == old  # newer than the checks test: never pinned
    assert install.pinned_python([old, _fake(tmp_path, "py315a", "3 15 alpha")]) == old  # not a final release
    assert install.pinned_python([_fake(tmp_path, "py38", "3 8 final")]) == ""
    assert install.pinned_python([_fake(tmp_path, "garbled", "not a version")]) == ""
    twin = _fake(tmp_path, "py315b", "3 15 final")
    assert install.pinned_python([new, twin]) == new  # of two the same, the first


def test_each_python_org_version_on_the_mac_is_a_candidate(tmp_path, monkeypatch):
    """python.org installs each version in its own folder, and `Current` names only the last one installed."""
    monkeypatch.setattr(install, "interpreter_problems", lambda path: [])
    versions = tmp_path / "Versions"
    for minor in ("12", "15"):
        (versions / f"3.{minor}" / "bin").mkdir(parents=True)
        _fake(versions / f"3.{minor}" / "bin", "python3", f"3 {minor} final")
    monkeypatch.setattr(install, "FRAMEWORKS", str(versions / "*" / "bin" / "python3"))
    monkeypatch.setattr(install, "PYTHONS", ())
    monkeypatch.setattr(sys, "executable", _fake(tmp_path, "running", "3 12 final"))
    assert install.pinned_python() == os.path.realpath(versions / "3.15" / "bin" / "python3")


def test_the_newest_python_the_installer_pins_is_the_newest_the_checks_test():
    """Read from the workflow, never restated: a Python the checks stop testing is no longer pinned, and one they add is."""
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    matrix = re.search(r"^\s+python: \[(.*)\]", text, re.M).group(1)
    assert install.TESTED == max(tuple(map(int, v.split("."))) for v in re.findall(r'"(3\.\d+)"', matrix))
