"""The runtime the guard runs changes only on the principal's code (review round 2 of 5.23.1, N5 and N6; the principal's
sandbox rulings of 2026-11-15: the guard holds each command that writes what the guard trusts for his code of that
exact command, and releases install from the protected release tool).

N5: `synthesis install <folder>` made any folder the runtime with no code, by PATH and by its stable path, and the
version floor read only what the folder says about itself. N6: `synthesis uninstall` removed `current`, the launchers
and the releases with no code, and the next session start's bootstrap then installed the harness folder's own code as
a first install. Every spelling of the CLI that installs, removes or rewrites the runtime now waits for the code of
that exact command; a program that calls the installer waits where the guard can read it; and a session start
installs only into a home that no runtime has been in."""

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
BOOTSTRAP = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]["SessionStart"][0]["hooks"][0]["command"]


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A home of the test's own with the runtime installed in it from this tree: `~`, `$HOME` and the synthesis home
    lead there, and the principal's session has a record his codes are read from."""
    home = tmp_path / "home"
    for key, value in (("HOME", home), ("SYNTHESIS_HOME", home / ".synthesis" / "v5"), ("CLAUDE_CONFIG_DIR", home / ".claude"),
                       ("CODEX_HOME", home / ".codex"), ("XDG_DATA_HOME", home / ".local" / "share"),
                       ("SYNTHESIS_CLAUDE_DESKTOP_DIR", home / "Library" / "Application Support" / "Claude")):
        monkeypatch.setenv(key, str(value))
    monkeypatch.setenv("SYNTHESIS_SESSION", "S-principal")
    record = home / ".claude" / "projects" / "-work" / "S-principal.jsonl"
    record.parent.mkdir(parents=True)
    record.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "hello"}}) + "\n", encoding="utf-8")
    paths.write_json(paths.state() / "transcripts" / "S-principal.json", {"path": str(record)})
    install.install(ROOT)
    work = tmp_path / "work"
    work.mkdir()
    folder = tmp_path / "my-plugin"  # an agent's copy of the runtime with its own guard, at the running version number
    shutil.copytree(os.path.realpath(paths.home() / "current"), folder, ignore=shutil.ignore_patterns("__pycache__", "HASH", "SOURCE"))
    (folder / "synthesis" / "guards.py").write_text(STUB, encoding="utf-8")

    def approve(reason: str) -> list:
        code = re.search(r"\bcode ([a-z0-9]{6})\b", reason).group(1)
        when = (datetime.now(timezone.utc) + timedelta(milliseconds=5)).isoformat()
        with record.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"type": "user", "timestamp": when, "origin": {"kind": "human"}, "sessionId": "S-principal",
                                     "message": {"role": "user", "content": f"approve {code}"}}) + "\n")
        time.sleep(0.01)
        return approvals.grant_from_prompt(f"approve {code}")

    return {"home": home, "v5": paths.home(), "work": work, "folder": folder, "approve": approve,
            "runtime": Path(os.path.realpath(paths.home() / "current")), "session": {"session_id": "S-principal",
                                                                                   "transcript_path": str(record)}}


def _verdict(world, line, where=None):
    return guards.check("Bash", {"command": line} if isinstance(line, str) else line, {}, cwd=str(where or world["work"]),
                        session=world["session"])


def _lines(world, items) -> list:
    v5, f, rt = world["v5"], shlex.quote(str(world["folder"])), world["runtime"]
    return [item.format(v5=v5, f=f, rt=rt, home=world["home"]) for item in items]


WAITS = [
    "synthesis install {f}",                                    # N5, by PATH
    "{v5}/bin/synthesis install {f}",                           # N5, by the stable path
    "~/.synthesis/v5/bin/synthesis install {f}",
    "$HOME/.synthesis/v5/bin/synthesis install {f}",
    "~/.local/bin/synthesis install {f}",                       # the link setup makes
    "synthesis install",                                        # the CLI's own folder: it rewrites the launchers
    "synthesis install --git-hooks",
    "synthesis --session S-principal install {f}",              # a global option before the command
    "synthesis --session=S-principal install {f}",
    "synthesis install -- {f}",
    "synthesis uninstall",                                      # N6
    "{v5}/bin/synthesis uninstall",
    "python3 -m synthesis.cli install {f}",
    "python3 -m synthesis install {f}",
    "python3 -I -S -m synthesis.cli uninstall",
    "python3 -m synthesis.install {f}",
    "python3 -m synthesis.install uninstall",
    "python3 -S {rt}/synthesis/install.py {f}",                 # the runtime's own install.py, run by path
    "python3 -S {rt}/synthesis/install.py uninstall",
    "python3 {rt}/synthesis/cli.py install {f}",
    "python3 -S {f}/synthesis/install.py {f}",                  # an agent's copy of it
    "sh {v5}/bin/synthesis uninstall",                          # the CLI's script read by a shell
    "bash -lc 'synthesis install {f}'",
    "cd {f} && synthesis install .",
    "env -i PATH=/usr/bin:/bin synthesis uninstall",
    "nohup synthesis uninstall >/dev/null 2>&1 &",
    "C=install; synthesis $C {f}",                              # a subcommand the line spells through a variable
    "for c in who uninstall; do synthesis $c; done",            # or a loop
    "synthesis $(printf install) {f}",                          # one the guard cannot read
    "synthesis uninstall $FLAGS",                               # a word that may be empty when it runs
    "find {f} -maxdepth 0 -exec synthesis install {{}} \\;",
    "uv run synthesis install {f}",
    "ln -s {v5}/bin/synthesis s && ./s uninstall",
]


@pytest.mark.parametrize("item", WAITS)
def test_every_spelling_that_installs_or_removes_the_runtime_waits_for_the_principal(world, item):
    line = _lines(world, [item])[0]
    reason = _verdict(world, line)
    assert reason and HELD in reason, (item, reason)


@pytest.mark.parametrize("tool,given", [("exec_command", {"cmd": "synthesis uninstall"}), ("shell", {"command": ["synthesis", "uninstall"]}),
                                        ("shell", {"command": ["bash", "-lc", "synthesis install /tmp/x"]}), ("bash", {"command": "synthesis uninstall"}),
                                        ("mcp__terminal__run_in_terminal", {"command": "synthesis uninstall"})])
def test_each_harness_shell_is_read_the_same_way(world, tool, given):
    reason = guards.check(tool, given, {}, cwd=str(world["work"]), session=world["session"])
    assert reason and HELD in reason, (tool, reason)


PASSES = [
    "synthesis doctor", "synthesis doctor --json", "synthesis who", "synthesis who --all", "synthesis version",
    "synthesis approvals", "synthesis install --help", "synthesis install -h", "synthesis --session S-principal uninstall --help",
    "synthesis uninstall --dry-run", "synthesis uninstall --dry", "python3 -m synthesis.cli who", "python3 -m synthesis.cli install --help",
    "python3 -m synthesis.install uninstall --dry-run", "synthesis install {f} {f}",  # the CLI refuses two folders: nothing runs
    "synthesis uninstall --dry-run=no",  # argparse refuses a value for a flag: nothing runs, as the guard reads it
    "for c in who version install; do synthesis $c --help; done",  # each value the loop gives is read (2 such loops in 60 days)
    "cd $HOME && synthesis uninstall --dry-run",
    "cat {v5}/current/HASH", "ls -la {v5}", "echo synthesis install {f}", "git commit -m 'synthesis install {f}'",
    "grep -rn 'synthesis uninstall' docs", "cat > notes.md <<'EOF'\nrun synthesis install {f}\nEOF",
    "python3 -c \"import sys; from synthesis import install; print(install.version_tuple('5.1.0'))\"",
    "python3 -c \"import json; print(json.dumps({{'synthesis': 'install'}}))\"",
    "python3 -c \"compile(open('{f}/synthesis/guards.py').read(), 'guards.py', 'exec')\"",  # a syntax check runs nothing
]


@pytest.mark.parametrize("item", PASSES)
def test_what_writes_no_runtime_needs_no_code(world, item):
    line = _lines(world, [item])[0]
    assert _verdict(world, line) is None, item


PROGRAMS = [
    "python3 -c \"import sys; from synthesis import install; install.install('{f}')\"",       # an import after `;`
    "python3 -c \"import os, synthesis.install as i; i.uninstall()\"",                          # in a list of imports
    "python3 -c \"if 1: from synthesis import cli; cli.main(['install', '{f}'])\"",             # after a colon
    "python3 - <<'EOF'\nimport sys; from synthesis import install\ninstall.install('{f}')\nEOF",
    "python3 -c \"import importlib; importlib.import_module('synthesis.install').install('{f}')\"",
    "python3 -c \"m = __import__('synthesis.install', fromlist=['install']); m.install('{f}')\"",
    "python3 -c \"import runpy; runpy.run_module('synthesis.cli', run_name='__main__')\" install {f}",
    "python3 -c \"import importlib.util as u; s = u.spec_from_file_location('i', '{f}/synthesis/install.py'); "
    "m = u.module_from_spec(s); s.loader.exec_module(m); m.install('{f}')\"",
    "cd {f} && python3 -c \"exec(open('synthesis/cli.py').read())\" install {f}",  # the CLI's code run from its file
]


@pytest.mark.parametrize("item", PROGRAMS)
def test_a_program_that_calls_the_installer_never_passes_with_no_code(world, item):
    line = _lines(world, [item])[0]
    assert _verdict(world, line) is not None, item


def test_the_code_binds_the_exact_command_where_it_runs_and_the_folder_as_it_is(world, tmp_path):
    line = _lines(world, ["synthesis install {f}"])[0]
    reason = _verdict(world, line)
    assert "synthesis runtime" in reason and str(world["folder"]) in reason
    world["approve"](reason)
    assert _verdict(world, line) is None  # the identical command, once
    assert HELD in _verdict(world, line)  # and only once
    world["approve"](_verdict(world, line))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    assert HELD in _verdict(world, line, where=elsewhere)  # another folder to run in asks again
    (world["folder"] / "synthesis" / "guards.py").write_text(STUB + "# changed after the approval\n", encoding="utf-8")
    assert HELD in _verdict(world, line)  # the folder changed after the code: it asks again
    assert HELD in _verdict(world, line + " --git-hooks")


JUDGE = r"""
import json, sys
sys.path[0] = sys.argv[1]
from synthesis import guards
for line in json.loads(sys.argv[2]):
    print(json.dumps(guards.check("Bash", {"command": line}, {}, cwd=sys.argv[3], session={"session_id": "S-other"})))
"""


def test_the_installed_runtime_holds_its_own_entry_points(world):
    """Judged by the guard the hook runs, from the runtime's own folder, where its install.py and cli.py are the plugin's
    as it shipped (and a program of its own passes as one): each still waits."""
    lines = _lines(world, ["python3 -S {v5}/current/synthesis/install.py {f}", "python3 -S {v5}/current/synthesis/install.py uninstall",
                           "python3 {v5}/current/synthesis/cli.py uninstall", "{v5}/bin/synthesis install {f}", "synthesis uninstall"])
    done = subprocess.run([sys.executable, "-S", "-c", JUDGE, str(world["v5"] / "current"), json.dumps(lines), str(world["work"])],
                          capture_output=True, text=True, timeout=300, env=dict(os.environ))
    assert done.returncode == 0, done.stderr[-2000:]
    said = [json.loads(line) for line in done.stdout.splitlines()]
    assert len(said) == len(lines) and all(s and HELD in s for s in said), list(zip(lines, said))


def test_n5_end_to_end_a_held_install_leaves_the_runtime_as_it_was(world):
    """The review's probe: the guard holds `synthesis install <folder>`, so the runtime keeps its own guard."""
    line = f"{world['v5']}/bin/synthesis install {shlex.quote(str(world['folder']))}"
    assert HELD in _verdict(world, line)
    assert (Path(os.path.realpath(world["v5"] / "current")) / "synthesis" / "guards.py").read_text() != STUB


# ---- the session start installs only into a home no runtime has been in --------------------------------------------

def _harness_folder(tmp_path, version="") -> Path:
    plugin = tmp_path / "plugins-cache" / "synthesis-skills" / "next"
    shutil.copytree(ROOT, plugin, ignore=shutil.ignore_patterns(".git", "__pycache__", "tests"))
    (plugin / "synthesis" / "guards.py").write_text(STUB, encoding="utf-8")  # what an agent writes into the harness's cache
    if version:
        (plugin / "synthesis" / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    return plugin


def _session_start(world, tmp_path, plugin, command=BOOTSTRAP, root_env="CLAUDE_PLUGIN_ROOT"):
    """hooks.json's SessionStart command as the harness runs it: sh, HOME kept, python3 from PATH."""
    python_dir = tmp_path / "py"
    python_dir.mkdir(exist_ok=True)
    if not (python_dir / "python3").exists():
        (python_dir / "python3").symlink_to(sys.executable)
    env = {**os.environ, "PATH": f"{python_dir}:/usr/bin:/bin", root_env: str(plugin)}
    return subprocess.run(["/bin/sh", "-c", command.replace("${CLAUDE_PLUGIN_ROOT}", "$" + root_env)], input='{"session_id": "S-next"}',
                          text=True, env=env, capture_output=True, timeout=300)


def _guards_now(world) -> str:
    found = world["v5"] / "current" / "synthesis" / "guards.py"
    return found.read_text() if found.is_file() else ""


def test_a_session_start_never_replaces_an_installed_runtime_even_with_a_newer_plugin(world, tmp_path):
    plugin = _harness_folder(tmp_path, version="99.0.0")
    before = os.path.realpath(world["v5"] / "current")
    _session_start(world, tmp_path, plugin)
    assert os.path.realpath(world["v5"] / "current") == before and _guards_now(world) != STUB


def test_n6_after_the_runtime_is_removed_a_session_start_installs_nothing_from_the_harness_folder(world, tmp_path):
    plugin = _harness_folder(tmp_path)
    install.uninstall(codex_cleared=True)  # what `synthesis uninstall` does once the principal's code lets it run
    assert not (world["v5"] / "current").exists() and not (world["v5"] / "bin" / "synthesis-hook").exists()
    done = _session_start(world, tmp_path, plugin)
    assert not (world["v5"] / "current").exists() and _guards_now(world) != STUB
    assert "a session start" in done.stderr and str(world["v5"]) in done.stderr  # said where the harness shows hook errors


def test_a_runtime_removed_by_hand_is_not_installed_again_by_the_bootstrap(world, tmp_path):
    plugin = _harness_folder(tmp_path)
    (world["v5"] / "current").unlink()
    (world["v5"] / "bin" / "synthesis-hook").unlink()
    _session_start(world, tmp_path, plugin)
    assert not (world["v5"] / "current").exists()


def test_n9_a_hash_removed_or_a_launcher_folder_moved_makes_no_first_install(world, tmp_path):
    """The review's N9 routes that a guard may not read (Codex's workdir through `current/..`, which this branch does not
    place) end the same way: the runtime's traces stay, so neither the stable hook's session start nor the bootstrap
    installs the harness folder's code."""
    plugin = _harness_folder(tmp_path)
    (world["runtime"] / "HASH").unlink()
    subprocess.run([str(world["v5"] / "bin" / "synthesis-hook"), "session-start", str(plugin)], input="{}", capture_output=True,
                   text=True, env=dict(os.environ), timeout=300)
    assert _guards_now(world) != STUB and not (world["runtime"] / "HASH").exists()
    (world["v5"] / "bin").rename(world["v5"] / "bin.old")
    _session_start(world, tmp_path, plugin)
    assert _guards_now(world) != STUB and not (world["v5"] / "bin").exists()


def test_muse_s_bootstrap_installs_nothing_where_a_runtime_was(world, tmp_path):
    plugin = _harness_folder(tmp_path)
    install.uninstall(codex_cleared=True)
    script = (ROOT / ".muse-plugin" / "hooks" / "session-start.sh").read_text()
    _session_start(world, tmp_path, plugin, command=script, root_env="MUSE_PLUGIN_ROOT")
    assert not (world["v5"] / "current").exists()


def test_a_true_first_install_still_comes_from_the_harness_folder(tmp_path, monkeypatch):
    home = tmp_path / "fresh"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SYNTHESIS_HOME", str(home / ".synthesis" / "v5"))
    plugin = tmp_path / "plugins-cache" / "synthesis-skills" / "first"
    shutil.copytree(ROOT, plugin, ignore=shutil.ignore_patterns(".git", "__pycache__", "tests"))
    done = _session_start({"v5": home / ".synthesis" / "v5"}, tmp_path, plugin)
    assert (home / ".synthesis" / "v5" / "current" / "synthesis" / "hook.py").is_file(), done.stderr
    assert os.access(home / ".synthesis" / "v5" / "bin" / "synthesis-hook", os.X_OK)


def test_first_only_reads_what_a_runtime_leaves_behind(world, tmp_path):
    plugin = _harness_folder(tmp_path)
    kept = install.install(plugin, first_only=True)  # the runtime is there and whole: kept, quietly
    assert "kept" in kept and _guards_now(world) != STUB
    install.uninstall(codex_cleared=True)
    with pytest.raises(RuntimeError, match="a session start"):  # gone, but its state and board are there: never a first install
        install.install(plugin, first_only=True)
    assert install.traces(world["v5"]) and not (world["v5"] / "current").exists()
    empty = tmp_path / "empty-home"
    os.environ["SYNTHESIS_HOME"] = str(empty)
    try:
        assert install.traces(empty) == [] and "synthesis runtime" in install.install(plugin, first_only=True)
    finally:
        os.environ["SYNTHESIS_HOME"] = str(world["v5"])


def test_the_bootstrap_entry_passes_first_and_an_explicit_install_still_installs(world, tmp_path):
    plugin = _harness_folder(tmp_path)
    done = subprocess.run([sys.executable, "-S", str(plugin / "synthesis" / "install.py"), str(plugin)], capture_output=True,
                          text=True, env={**os.environ, "SYNTHESIS_HOME": str(world["v5"])}, timeout=300)
    assert _guards_now(world) != STUB and done.returncode == 0  # the runtime is there: install.py, the bootstrap's entry, keeps it
    from synthesis import cli
    assert cli.main(["install", str(plugin)]) == 0 and _guards_now(world) == STUB  # an explicit install, once the code let it run
