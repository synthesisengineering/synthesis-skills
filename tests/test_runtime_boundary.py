"""Review round 1 of 22.18: the CLI itself refuses to replace or remove an installed runtime without the principal's
code, however it was started, and the code binds the install that actually happens.

H1: the guard held the CLI only where it was the command on the line, so a script run by sh, by its path or sourced,
Python's subprocess or os.system, perl, awk, a git alias, a make recipe, a wrapper by another name, crontab and at each
reached it with no code. Now `cmd_install` and `cmd_uninstall` (and install.py's own main, which runs them) spend a live
grant the principal's prompt backs for the exact change, or file the request themselves and say what the hook says; the
hook only asks for the same subject for the direct spellings, so the principal approves before the run.
H2: the code bound `package_hash`, which read only `synthesis/*.py` and the stable scripts, of the folder as the hook saw
it. Now every file an install copies is hashed, the install is made from a copy staged in the protected releases folder
and checked there, and a `synthesis` that PATH resolves to anything but the stable launcher is not read as the CLI."""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from synthesis import approvals, guards, install, paths

ROOT = Path(__file__).resolve().parents[1]
HELD = "approve followed by the code"
STUB = "def check(*args, **kwargs):\n    return None\n"
SID = "S-principal"


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A home of the test's own with the runtime installed from this tree, the principal's session and its record, an
    agent's copy of the runtime with its own guard, and the stable launcher first on PATH as `synthesis`."""
    home = tmp_path / "home"
    for key, value in (("HOME", home), ("SYNTHESIS_HOME", home / ".synthesis" / "v5"), ("CLAUDE_CONFIG_DIR", home / ".claude"),
                       ("CODEX_HOME", home / ".codex"), ("XDG_DATA_HOME", home / ".local" / "share"),
                       ("SYNTHESIS_CLAUDE_DESKTOP_DIR", home / "Library" / "Application Support" / "Claude")):
        monkeypatch.setenv(key, str(value))
    monkeypatch.setenv("SYNTHESIS_SESSION", SID)
    record = home / ".claude" / "projects" / "-work" / f"{SID}.jsonl"
    record.parent.mkdir(parents=True)
    record.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "hello"}}) + "\n", encoding="utf-8")
    install.install(ROOT)  # a first install: the home holds nothing yet
    approvals.remember(SID, str(record))  # as the prompt hook then records it, with each harness's folders (22.19)
    evil = tmp_path / "my-plugin"
    shutil.copytree(os.path.realpath(paths.home() / "current"), evil, ignore=shutil.ignore_patterns("__pycache__", "HASH", "SOURCE"))
    (evil / "synthesis" / "guards.py").write_text(STUB, encoding="utf-8")
    benign = tmp_path / "next-release"
    shutil.copytree(os.path.realpath(paths.home() / "current"), benign, ignore=shutil.ignore_patterns("__pycache__", "HASH", "SOURCE"))
    with open(benign / "synthesis" / "paths.py", "a", encoding="utf-8") as handle:
        handle.write("\n# a release of its own\n")
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "synthesis").symlink_to(paths.home() / "bin" / "synthesis")
    (tools / "python3").symlink_to(sys.executable)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setenv("PATH", f"{tools}:/usr/bin:/bin:/usr/sbin:/sbin")  # `synthesis` is the test home's stable launcher

    def typed(code: str, grant: bool = True):
        """The principal types approve <code> in his session; the prompt hook grants it where a runtime runs it."""
        when = (datetime.now(timezone.utc) + timedelta(milliseconds=5)).isoformat()
        with record.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"type": "user", "timestamp": when, "origin": {"kind": "human"}, "sessionId": SID,
                                     "message": {"role": "user", "content": f"approve {code}"}}) + "\n")
        time.sleep(0.01)
        return approvals.grant_from_prompt(f"approve {code}") if grant else []

    def run(line: str, path: str = ""):
        return subprocess.run(["/bin/sh", "-c", line], cwd=str(work), capture_output=True, text=True, timeout=300,
                              env={**os.environ, "PATH": path or f"{tools}:/usr/bin:/bin"})

    def judge(line: str, path: str = ""):
        env = {"PATH": path} if path else {}
        with pytest.MonkeyPatch.context() as patched:
            for key, value in env.items():
                patched.setenv(key, value)
            return guards.check("Bash", {"command": line}, {}, cwd=str(work),
                                session={"session_id": SID, "transcript_path": str(record)})

    return {"v5": paths.home(), "evil": evil, "benign": benign, "tools": tools, "work": work, "typed": typed, "run": run,
            "judge": judge, "record": record}


def _code(text: str) -> str:
    return re.search(r"\bcode ([0-9a-f]{6})\b", text).group(1)


def _guards(world) -> str:
    found = world["v5"] / "current" / "synthesis" / "guards.py"
    return found.read_text() if found.is_file() else ""


# ---- H1: the CLI refuses, however it was started ------------------------------------------------------------------

def test_the_cli_run_by_itself_refuses_to_replace_the_runtime_and_says_what_the_hook_says(world):
    done = world["run"](f"synthesis install {shlex.quote(str(world['evil']))}")
    assert done.returncode != 0 and HELD in done.stderr and "this exact install" in done.stderr, done.stderr
    assert _guards(world) != STUB
    assert len(approvals.pending()) == 1  # it filed the request itself


@pytest.mark.parametrize("route", ["script by sh", "script by path", "script sourced", "substituted", "python subprocess",
                                   "python os.system", "a python file", "perl", "awk", "git alias", "make", "wrapper"])
def test_every_route_that_starts_the_cli_ends_at_its_refusal(world, tmp_path, route):
    f = shlex.quote(str(world["evil"]))
    script = tmp_path / "w.sh"
    script.write_text(f"synthesis install {f}\n")
    script.chmod(0o755)
    (tmp_path / "p.py").write_text(f"import subprocess\nsubprocess.run(['synthesis', 'install', {str(world['evil'])!r}])\n")
    (tmp_path / "Makefile").write_text(f"all:\n\tsynthesis install {f}\n")
    (tmp_path / "s").write_text('#!/bin/sh\nexec synthesis "$@"\n')
    (tmp_path / "s").chmod(0o755)
    lines = {"script by sh": f"sh {script}", "script by path": str(script), "script sourced": f". {script}",
             "substituted": f"bash -c \"$(cat {script})\"",
             "python subprocess": f"python3 -c \"import subprocess; subprocess.run(['synthesis', 'install', {str(world['evil'])!r}])\"",
             "python os.system": f"python3 -c \"import os; os.system('synthesis install {world['evil']}')\"",
             "a python file": f"python3 {tmp_path / 'p.py'}", "perl": f"perl -e 'system(\"synthesis\", \"install\", \"{world['evil']}\")'",
             "awk": f"awk 'BEGIN{{system(\"synthesis install {world['evil']}\")}}'",
             "git alias": f"git -c alias.i='!synthesis install {world['evil']}' i", "make": f"make -s -f {tmp_path / 'Makefile'}",
             "wrapper": f"{tmp_path / 's'} install {f}"}
    if route in ("perl", "make") and not shutil.which(route):
        pytest.skip(f"no {route} here")
    world["run"](lines[route])
    assert _guards(world) != STUB and len(approvals.pending()) == 1, route


def test_uninstall_waits_for_the_code_and_the_code_lets_it_run(world):
    done = world["run"]("synthesis uninstall")
    assert done.returncode != 0 and HELD in done.stderr and (world["v5"] / "current").exists()
    world["typed"](_code(done.stderr))
    done = world["run"]("synthesis uninstall")
    assert done.returncode == 0 and not (world["v5"] / "current").exists(), done.stderr


def test_the_hook_asks_and_the_cli_spends(world):
    line = f"synthesis install {shlex.quote(str(world['benign']))}"
    reason = world["judge"](line)
    assert reason and HELD in reason and "synthesis runtime" in reason
    world["typed"](_code(reason))
    assert world["judge"](line) is None and world["judge"](line) is None  # the hook checks the grant and spends nothing
    done = world["run"](line)
    assert done.returncode == 0, done.stderr
    assert "# a release of its own" in (world["v5"] / "current" / "synthesis" / "paths.py").read_text()
    assert HELD in world["judge"](line)  # the CLI spent it


def test_first_install_help_dry_run_and_refused_words_need_no_code(tmp_path, monkeypatch, world):
    from synthesis import cli
    assert world["run"]("synthesis install --help").returncode == 0
    assert world["run"]("synthesis uninstall --dry-run").returncode == 0 and (world["v5"] / "current").exists()
    assert world["run"](f"synthesis install {world['evil']} {world['evil']}").returncode != 0
    assert approvals.pending() == []
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path / "fresh"))  # a home no runtime has been in
    assert cli.main(["install", str(world["benign"])]) == 0 and (tmp_path / "fresh" / "current" / "synthesis" / "hook.py").is_file()


# ---- H2: the code binds the install that happens ------------------------------------------------------------------

def test_a_package_added_after_the_code_is_not_installed_on_it(world):
    line = f"synthesis install {shlex.quote(str(world['benign']))}"
    world["typed"](_code(world["judge"](line)))
    (world["benign"] / "synthesis" / "guards").mkdir()
    (world["benign"] / "synthesis" / "guards" / "__init__.py").write_text(STUB)  # no hash the old code read changes
    done = world["run"](line)
    assert done.returncode != 0 and HELD in done.stderr
    assert not (Path(os.path.realpath(world["v5"] / "current")) / "synthesis" / "guards").exists()


def test_a_folder_changed_after_the_hook_passed_it_is_never_what_is_installed(world):
    line = f"synthesis install {shlex.quote(str(world['benign']))}"
    world["typed"](_code(world["judge"](line)))
    assert world["judge"](line) is None
    (world["benign"] / "synthesis" / "guards.py").write_text(STUB)  # after the hook passed it, before the command runs
    done = world["run"](line)
    assert done.returncode != 0 and HELD in done.stderr and _guards(world) != STUB


def test_every_file_an_install_copies_is_hashed_and_installed_from_its_staged_copy(world, tmp_path):
    folder = world["benign"]
    before = install.package_hash(folder)
    (folder / "synthesis" / "sub").mkdir()
    (folder / "synthesis" / "sub" / "x.py").write_text("x = 1\n")
    assert install.package_hash(folder) != before
    (folder / "CHANGELOG.md").write_text("# Changelog\n")
    third = install.package_hash(folder)
    try:  # a direct call is staged, hashed and checked like the CLI's (Q4)
        install.install(folder)
    except install.Unapproved as held:
        world["typed"](_code(str(held)))
        install.install(folder)
    release = Path(os.path.realpath(world["v5"] / "current"))
    assert release.name == third and (release / "synthesis" / "sub" / "x.py").is_file()
    assert not [p for p in (world["v5"] / "releases").iterdir() if p.name.startswith(".") and p.name != ".install.lock"]  # no staging left


def test_a_synthesis_that_path_resolves_elsewhere_is_not_read_as_the_cli(world, tmp_path):
    planted = tmp_path / "local-bin"
    planted.mkdir()
    (planted / "synthesis").write_text(f"#!/bin/sh\nexec {world['v5']}/bin/synthesis install {world['evil']}\n")
    (planted / "synthesis").chmod(0o755)
    path = f"{planted}:{world['tools']}:/usr/bin:/bin"
    said = world["judge"]("synthesis install", path=path) or ""
    assert "synthesis runtime from the CLI's own folder" not in said  # it is another program, never the CLI's own install
    world["run"]("synthesis install", path=path)  # the program it is runs the real CLI, which refuses
    assert _guards(world) != STUB


def test_the_clis_own_install_binds_what_it_installs_from(world):
    reason = world["judge"]("synthesis install")
    assert reason and HELD in reason
    world["typed"](_code(reason))
    assert world["run"]("synthesis install").returncode == 0


def test_a_runtime_removed_on_the_code_is_installed_again_on_a_code_the_session_shows(world):
    """With the runtime gone no hook records a grant, so the CLI reads the session's own record: the principal types the
    code in a session the hook saw before, and the identical install runs, from his terminal or that session's shell."""
    world["typed"](_code(world["run"]("synthesis uninstall").stderr))
    assert world["run"]("synthesis uninstall").returncode == 0
    from synthesis import cli
    assert cli.main(["install", str(world["benign"])]) == 2 and not (world["v5"] / "current").exists()
    world["typed"](approvals.pending()[0], grant=False)  # the prompt hook did not run: only the record shows it
    assert cli.main(["install", str(world["benign"])]) == 0 and (world["v5"] / "current" / "synthesis" / "hook.py").is_file()


# ---- review round 2 of 22.18, K2: setup names the session its install needs -----------------------------------------

def _setup():
    sys.path.insert(0, str(ROOT / "skills" / "synthesis-onboarding" / "scripts"))
    import setup
    return setup


def test_setup_takes_session_and_passes_it_to_the_install(world, monkeypatch):
    """From the principal's own terminal no session is in the environment, so a setup run over an installed runtime
    could not name the session his code is typed in; `--session` names it, and the stop message says so."""
    setup = _setup()
    done = subprocess.run([sys.executable, str(ROOT / "skills" / "synthesis-onboarding" / "scripts" / "setup.py"), "--help"],
                          capture_output=True, text=True, timeout=120)
    assert re.search(r"--session(?![\w-])", done.stdout), "setup.py names no --session"
    for key in ("SYNTHESIS_SESSION", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "MUSE_SESSION_ID"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(install.Unapproved, match="--session"):
        setup.install_runtime(False, session={"session_id": ""})
    world["typed"](approvals.pending()[0])
    assert any("synthesis runtime" in line for line in setup.install_runtime(False, session={"session_id": SID}))


def test_setup_s_first_install_still_needs_no_session(tmp_path, monkeypatch):
    setup = _setup()
    monkeypatch.setenv("SYNTHESIS_SESSION", "")
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path / "fresh"))
    assert any("synthesis runtime" in line for line in setup.install_runtime(False, session={"session_id": ""}))


# ---- review round 4 of 5.23.1, Q4: the check is in install and uninstall themselves ---------------------------------

def test_a_program_that_calls_the_installer_itself_spends_the_code_too(world):
    with pytest.raises(install.Unapproved, match="approve followed by the code"):
        install.install(world["evil"])
    assert _guards(world) != STUB
    world["typed"](approvals.pending()[0])
    install.install(world["evil"])  # the principal's code for exactly this staged copy
    assert _guards(world) == STUB


def test_uninstall_called_itself_waits_too(world):
    with pytest.raises(install.Unapproved):
        install.uninstall(codex_cleared=True)
    assert (world["v5"] / "current").exists()


def test_a_rollback_is_its_own_kind_named_as_a_downgrade(world):
    (world["benign"] / "synthesis" / "__init__.py").write_text('__version__ = "5.0.0"\n')
    with pytest.raises(install.Unapproved, match=r"back from \d+\.\d+\.\d+ to 5\.0\.0, a downgrade"):
        install.install(world["benign"])
    said = world["judge"](f"synthesis install {shlex.quote(str(world['benign']))}")
    assert "back from" in said and "a downgrade" in said
    staged = install.change(world["v5"], world["benign"], world["benign"], "d")[0]
    assert staged["action"] == "rollback" and staged["to"] == "5.0.0"


RELEASE = r"""
import sys
sys.path.insert(0, sys.argv[1])
from synthesis import install
try:
    print(install.install(sys.argv[2]))
except install.Unapproved:
    print("unapproved")
"""


def test_the_release_tools_own_file_run_isolated_from_the_runtime_installs_nothing_without_the_hooks_grant(world):
    """22.18's release route trusted the process's main program and the interpreter's flags, which a program in the same
    process can set (round 2, K1). The release tool's own file, run `-I -S` from the protected runtime, now installs a
    folder only with the grant the hook writes for the launcher's line (tests/test_release_grant.py), and never a
    folder of anyone's but the tool's fresh clone of that tag."""
    release = Path(os.path.realpath(world["v5"] / "current"))
    tool = release / "skills" / "synthesis-skills-manager" / "scripts" / "release.py"
    tool.parent.mkdir(parents=True, exist_ok=True)
    tool.write_text(RELEASE)
    ran = subprocess.run([sys.executable, "-I", "-S", str(tool), str(release), str(world["benign"])], capture_output=True,
                         text=True, timeout=300).stdout.split()
    assert ran[-1:] == ["unapproved"] and "# a release of its own" not in (world["v5"] / "current" / "synthesis" / "paths.py").read_text()
