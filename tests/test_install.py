"""R7.1 and R7.5: one stable hook path that survives upgrades and deleted plugin folders."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from synthesis import install

ROOT = Path(__file__).resolve().parents[1]


def _plugin_copy(tmp_path, name="plugin-v1"):
    dest = tmp_path / name
    shutil.copytree(ROOT / "synthesis", dest / "synthesis", ignore=shutil.ignore_patterns("__pycache__"))
    return dest


def _run_hook(home, event, payload):
    return subprocess.run([str(home / "bin" / "synthesis-hook"), event], input=json.dumps(payload),
                          capture_output=True, text=True, env={**os.environ, "SYNTHESIS_HOME": str(home)})


def test_install_creates_the_stable_hook_and_it_guards(tmp_path, isolated_home):
    plugin = _plugin_copy(tmp_path)
    assert "synthesis runtime" in install.install(plugin)
    out = _run_hook(isolated_home, "pre-tool-use", {"tool_name": "Bash", "tool_input": {"command": "rm -rf ~"}})
    assert json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_a_running_task_keeps_working_after_its_plugin_folder_is_deleted(tmp_path, isolated_home):
    plugin = _plugin_copy(tmp_path)
    install.install(plugin)
    shutil.rmtree(plugin)  # the harness prunes the old version folder mid-task
    out = _run_hook(isolated_home, "pre-tool-use", {"tool_name": "Bash", "tool_input": {"command": "ls"}})
    assert out.returncode == 0 and out.stderr == ""


def test_upgrade_switches_current_and_keeps_the_hook_text_identical(tmp_path, isolated_home):
    v1 = _plugin_copy(tmp_path, "v1")
    install.install(v1)
    hook_text = (isolated_home / "bin" / "synthesis-hook").read_text()
    first = os.path.realpath(isolated_home / "current")
    v2 = _plugin_copy(tmp_path, "v2")
    (v2 / "synthesis" / "__init__.py").write_text('__version__ = "5.0.1"\n')
    install.install(v2)
    assert os.path.realpath(isolated_home / "current") != first
    assert (isolated_home / "bin" / "synthesis-hook").read_text() == hook_text
    assert install.install(v2).endswith(str(isolated_home / "current"))  # idempotent


def test_a_session_on_an_older_plugin_never_switches_the_runtime_back(tmp_path, isolated_home):
    """2026-10-06: a session that loaded the 5.0.2 plugin started or compacted after 5.0.3 shipped, and its
    session-start hook switched the stable runtime back to 5.0.2 for every harness. Only an explicit install may."""
    old, new = _plugin_copy(tmp_path, "old"), _plugin_copy(tmp_path, "new")
    (old / "synthesis" / "__init__.py").write_text('__version__ = "1.0.0"\n')
    (new / "synthesis" / "__init__.py").write_text('__version__ = "1.0.1"\n')
    install.install(new)
    installed = os.path.realpath(isolated_home / "current")
    out = subprocess.run([str(isolated_home / "bin" / "synthesis-hook"), "session-start", str(old)], input="{}",
                         capture_output=True, text=True, env={**os.environ, "SYNTHESIS_HOME": str(isolated_home)})
    assert out.returncode == 0 and os.path.realpath(isolated_home / "current") == installed
    assert "not newer" in install.install(old, forward_only=True)
    newer = _plugin_copy(tmp_path, "newer")
    (newer / "synthesis" / "__init__.py").write_text('__version__ = "1.0.2"\n')
    install.install(newer, forward_only=True)  # a session on a newer plugin still upgrades everyone
    assert install.version(isolated_home / "current") == (1, 0, 2)
    install.install(old)  # a deliberate rollback is an explicit install
    assert install.version(isolated_home / "current") == (1, 0, 0)


def test_cli_shim_runs_the_installed_copy_through_a_link_from_any_folder(tmp_path, isolated_home):
    """setup.py links ~/.local/bin/synthesis to the shim; a checkout in the working directory
    (its own synthesis/ package) must not stand in for the installed runtime."""
    install.install(_plugin_copy(tmp_path))
    link, decoy = tmp_path / "local-bin" / "synthesis", tmp_path / "checkout" / "synthesis"
    link.parent.mkdir()
    link.symlink_to(isolated_home / "bin" / "synthesis")
    decoy.mkdir(parents=True)
    (decoy / "__init__.py").write_text('__version__ = "decoy"\n')
    for command in (isolated_home / "bin" / "synthesis", link):
        out = subprocess.run([str(command), "version"], capture_output=True, text=True, cwd=decoy.parent,
                             env={**os.environ, "SYNTHESIS_HOME": str(isolated_home)})
        assert out.returncode == 0 and out.stdout.strip().startswith("5."), out.stderr


def test_hook_commands_in_the_plugin_never_name_a_version_folder():
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]
    commands = [h["command"] for event in hooks.values() for group in event for h in group["hooks"]]
    for command in commands:
        assert "$HOME/.synthesis/v5/bin/synthesis-hook" in command


def test_first_session_start_bootstraps_from_the_exact_registered_command(tmp_path):
    home = tmp_path / "fresh-home"
    home.mkdir()
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]
    command = hooks["SessionStart"][0]["hooks"][0]["command"]
    plugin = _plugin_copy(tmp_path)
    env = {k: v for k, v in os.environ.items() if k != "SYNTHESIS_HOME"}
    env.update(HOME=str(home), CLAUDE_PLUGIN_ROOT=str(plugin))
    out = subprocess.run(["/bin/sh", "-c", command], input=json.dumps({"session_id": "fresh", "source": "startup"}),
                         capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    assert (home / ".synthesis" / "v5" / "bin" / "synthesis-hook").is_file()
    assert (home / ".synthesis" / "v5" / "board" / "sessions" / "fresh.json").is_file()


def test_install_writes_global_git_hooks_that_run_the_commit_check(tmp_path, isolated_home):
    install.install(_plugin_copy(tmp_path))
    for name in install.GIT_HOOKS:
        hook = isolated_home / "git-hooks" / name
        assert os.access(hook, os.X_OK) and "commit_check.py" in hook.read_text()
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "k.txt").write_text("key AKIA" + "ABCDEFGHIJKLMNOP\n")
    subprocess.run(["git", "-C", str(repo), "add", "k.txt"], check=True)
    env = {**os.environ, "SYNTHESIS_HOME": str(isolated_home)}
    out = subprocess.run(["git", "-C", str(repo), "-c", f"core.hooksPath={isolated_home / 'git-hooks'}",
                          "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "x"],
                         capture_output=True, text=True, env=env)
    assert out.returncode != 0 and "AWS access key" in out.stderr


def test_bootstrap_command_writes_no_bytecode_into_the_plugin_folder():
    command = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert "python3 -B -S" in command


# ---- owned registrations and uninstall (owned_registrations, slimmed) ----------

def _hooks_path():
    return subprocess.run(["git", "config", "--global", "--get-all", "core.hooksPath"],
                          capture_output=True, text=True).stdout.split()


def test_git_hooks_option_records_the_previous_path_and_uninstall_restores_it(tmp_path, isolated_home):
    subprocess.run(["git", "config", "--global", "core.hooksPath", "/opt/team-hooks"], check=True)
    install.install(_plugin_copy(tmp_path))
    assert "was /opt/team-hooks" in install.register_git_hooks()
    assert _hooks_path() == [str(isolated_home / "git-hooks")]
    install.register_git_hooks()  # a rerun must not record our own path as "before"
    report = install.uninstall()
    assert _hooks_path() == ["/opt/team-hooks"]
    assert any("restored core.hooksPath to /opt/team-hooks" in line for line in report)


def test_git_hooks_are_not_touched_without_the_option(tmp_path, isolated_home):
    install.install(_plugin_copy(tmp_path))
    assert _hooks_path() == []
    assert not (isolated_home / "registrations.json").exists()


def test_uninstall_keeps_a_hooks_path_the_user_changed_since(tmp_path, isolated_home):
    install.install(_plugin_copy(tmp_path))
    install.register_git_hooks()
    subprocess.run(["git", "config", "--global", "core.hooksPath", "/opt/mine"], check=True)
    report = install.uninstall()
    assert _hooks_path() == ["/opt/mine"]
    assert any("kept core.hooksPath" in line for line in report)


def test_uninstall_removes_only_unedited_files_install_wrote(tmp_path, isolated_home):
    install.install(_plugin_copy(tmp_path))
    (isolated_home / "bin" / "synthesis").write_text("#!/bin/sh\n# my wrapper\n")
    (isolated_home / "config.json").write_text('{"send_tools": ["x"]}\n')
    report = install.uninstall()
    assert (isolated_home / "bin" / "synthesis").is_file()
    assert not (isolated_home / "bin" / "synthesis-hook").exists()
    assert not (isolated_home / "current").exists() and not any((isolated_home / "releases").iterdir())
    assert (isolated_home / "config.json").read_text() == '{"send_tools": ["x"]}\n'
    assert any("edited since install" in line for line in report)


def test_uninstall_dry_run_changes_nothing(tmp_path, isolated_home):
    install.install(_plugin_copy(tmp_path))
    install.register_git_hooks()
    before = sorted(str(p) for p in isolated_home.rglob("*"))
    report = install.uninstall(dry_run=True)
    assert sorted(str(p) for p in isolated_home.rglob("*")) == before
    assert _hooks_path() == [str(isolated_home / "git-hooks")]
    assert any(line.startswith("would remove") for line in report)


def test_install_rerun_changes_nothing(tmp_path, isolated_home):
    plugin = _plugin_copy(tmp_path)
    install.install(plugin)
    stamp = {str(p): p.stat().st_mtime_ns for p in isolated_home.rglob("*")}
    install.install(plugin)
    assert {str(p): p.stat().st_mtime_ns for p in isolated_home.rglob("*")} == stamp


def test_command_line_install_with_git_hooks_then_uninstall(tmp_path, isolated_home):
    plugin = _plugin_copy(tmp_path)
    run = lambda *a: subprocess.run([sys.executable, "-S", str(plugin / "synthesis" / "install.py"), *a],
                                    capture_output=True, text=True, env={**os.environ, "SYNTHESIS_HOME": str(isolated_home)})
    out = run(str(plugin), "--git-hooks")
    assert out.returncode == 0 and "core.hooksPath ->" in out.stdout
    out = run("uninstall")
    assert out.returncode == 0 and "restored core.hooksPath to unset" in out.stdout and _hooks_path() == []


def _with_day_end(plugin: Path) -> Path:
    scripts = plugin / "skills" / "synthesis-daily-rituals" / "scripts"
    shutil.copytree(ROOT / "skills" / "synthesis-daily-rituals" / "scripts", scripts,
                    ignore=shutil.ignore_patterns("__pycache__", "*.py"))
    return plugin


def test_every_install_carries_the_day_end_launcher_and_nudge(tmp_path, isolated_home):
    plugin = _with_day_end(_plugin_copy(tmp_path))
    install.install(plugin)
    for name in install.DAY_END:
        copy = isolated_home / "bin" / name
        assert os.access(copy, os.X_OK)
        assert copy.read_bytes() == (plugin / "skills" / "synthesis-daily-rituals" / "scripts" / name).read_bytes()
    nudge = plugin / "skills" / "synthesis-daily-rituals" / "scripts" / "day-end-nudge.sh"
    nudge.write_text(nudge.read_text() + "# next release\n")
    install.install(plugin)  # a new release replaces the copy
    assert (isolated_home / "bin" / "day-end-nudge.sh").read_text().endswith("# next release\n")


def test_uninstall_removes_unedited_day_end_copies_and_keeps_an_edited_one(tmp_path, isolated_home):
    install.install(_with_day_end(_plugin_copy(tmp_path)))
    launcher = isolated_home / "bin" / "day-end"
    launcher.write_text(launcher.read_text() + "# my tweak\n")
    report = install.uninstall()
    assert launcher.is_file() and not (isolated_home / "bin" / "day-end-nudge.sh").exists()
    assert any(line.startswith("kept") and "day-end:" in line for line in report)


def test_inbox_scripts_get_a_stable_path_and_a_change_makes_a_new_release(tmp_path, isolated_home):
    plugin = _plugin_copy(tmp_path)
    scripts = plugin / "skills" / "synthesis-inbox-cleanup" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "icloud_plan.py").write_text("print('plan')\n")
    (scripts / "test_icloud_plan.py").write_text("")
    install.install(plugin)
    stable = isolated_home / "current" / "skills" / "synthesis-inbox-cleanup" / "scripts"
    assert (stable / "icloud_plan.py").read_text() == "print('plan')\n"
    assert not (stable / "test_icloud_plan.py").exists()
    first = install.current_hash()
    (scripts / "icloud_plan.py").write_text("print('plan v2')\n")
    install.install(plugin)
    assert install.current_hash() != first and (stable / "icloud_plan.py").read_text() == "print('plan v2')\n"


def test_the_nudge_finds_the_deadline_sweep_in_the_runtime(tmp_path, isolated_home):
    """The 16:55 nudge runs the critical-deadline alert outside any session, so the sweep needs a stable path."""
    plugin = _plugin_copy(tmp_path)
    shutil.copytree(ROOT / "skills" / "synthesis-daily-rituals" / "scripts", plugin / "skills" / "synthesis-daily-rituals" / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__"))
    install.install(plugin)
    sweep = isolated_home / "current" / "skills" / "synthesis-daily-rituals" / "scripts" / "decay_sweep.py"
    done = subprocess.run([sys.executable, "-S", str(sweep), "--alert-declared", "--as-of", "2026-11-06"],
                          capture_output=True, text=True, env={**os.environ, "SYNTHESIS_HOME": str(isolated_home)})
    assert done.returncode == 0, done.stderr
    assert "0 due" in done.stdout  # no workspace declares plan folders here, so nothing is posted or spoken


def test_the_cli_installs_from_a_plugin_folder(tmp_path, isolated_home, capsys):
    from synthesis import cli
    assert cli.main(["install", str(_plugin_copy(tmp_path))]) == 0
    assert "synthesis runtime" in capsys.readouterr().out
    assert (isolated_home / "bin" / "synthesis-hook").is_file()


def test_the_board_moves_out_of_the_state_folder_and_approvals_stay(isolated_home):
    """5.1.18: the board has its own folder, the one Codex's sandbox may write; approvals stay where it cannot."""
    from synthesis import board
    old = isolated_home / "state"
    (old / "sessions").mkdir(parents=True)
    (old / "sessions" / "S1.json").write_text(json.dumps({"session": "S1", "claims": ["/r/a/**"], "seen": 1.0}))
    (old / "messages" / "S1").mkdir(parents=True)
    (old / "messages" / "S1" / "1-1.json").write_text(json.dumps({"from": "S2", "text": "hi", "at": 1.0}))
    (old / "claims.jsonl").write_text('{"session": "S1"}\n')
    (old / "approvals").mkdir()
    assert install.move_board(isolated_home) == ["sessions", "messages", "claims.jsonl"]
    assert board.load("S1").claims == ["/r/a/**"] and board.inbox("S1")[0]["text"] == "hi"
    assert not any((old / n).exists() for n in ("sessions", "messages", "claims.jsonl")) and (old / "approvals").is_dir()
    assert install.move_board(isolated_home) == []


def test_board_entries_in_both_places_are_merged_and_nothing_is_lost(isolated_home):
    """An older release's session-start hook can switch to a newer one without moving the board, so a session may
    write the new folder before the old one is merged: both copies' claims are kept, the rest is archived. The new
    copy may be a fresh record (the release script's own claim, 2026-10-30): its empty fields never erase set ones."""
    from synthesis import board, paths
    old, new = isolated_home / "state", isolated_home / "board"
    for root, claims, seen, project in ((old, ["/r/a/**"], 1.0, "alpha"), (new, ["/r/b/**"], 2.0, "")):
        (root / "sessions").mkdir(parents=True)
        (root / "sessions" / "S1.json").write_text(json.dumps({"session": "S1", "claims": claims, "seen": seen,
                                                               "started": seen, "goal": str(seen), "project": project}))
        (root / "claims.jsonl").write_text(f'{{"at": {seen}}}\n')
        (root / "claims.lock").write_text("")
    (old / "sessions" / "S2.json").write_text(json.dumps({"session": "S2", "claims": [], "seen": 1.0}))
    install.move_board(isolated_home)
    merged = board.load("S1")
    assert merged.claims == ["/r/a/**", "/r/b/**"] and merged.goal == "2.0" and board.load("S2") is not None
    assert merged.project == "alpha" and merged.started == 1.0 and merged.seen == 2.0
    assert (new / "claims.jsonl").read_text() == '{"at": 2.0}\n{"at": 1.0}\n'
    kept = sorted(p.relative_to(isolated_home / "archive").parts[1:] for p in (isolated_home / "archive").rglob("*")
                  if p.is_file())
    assert kept == [("claims.jsonl",), ("claims.lock",), ("sessions", "S1.json")] and paths.old_board() == []


def test_any_hook_merges_a_board_an_older_release_wrote_in_the_state_folder(tmp_path, isolated_home):
    install.install(_plugin_copy(tmp_path))
    (isolated_home / "state" / "sessions").mkdir(parents=True)
    (isolated_home / "state" / "sessions" / "S9.json").write_text(json.dumps({"session": "S9", "claims": [], "seen": 1.0}))
    out = _run_hook(isolated_home, "pre-tool-use", {"tool_name": "Bash", "tool_input": {"command": "ls"}})
    assert out.returncode == 0 and (isolated_home / "board" / "sessions" / "S9.json").is_file()
    assert not (isolated_home / "state" / "sessions").exists()


def test_the_guard_finds_the_holds_ledgers_reader_in_the_runtime(tmp_path, isolated_home):
    """The same-day rule asks the chief of staff's own ledger reader which holds are in force; hooks run from the runtime."""
    plugin = _plugin_copy(tmp_path)
    scripts = plugin / "skills" / "synthesis-chief-of-staff" / "scripts"
    shutil.copytree(ROOT / "skills" / "synthesis-chief-of-staff" / "scripts", scripts, ignore=shutil.ignore_patterns("__pycache__"))
    install.install(plugin)
    reader = isolated_home / "current" / "skills" / "synthesis-chief-of-staff" / "scripts" / "holds_state.py"
    assert reader.read_bytes() == (scripts / "holds_state.py").read_bytes()
    probe = ("import sys; sys.path.insert(0, sys.argv[1]); from synthesis import guards; import os; "
             "print(os.path.realpath(guards.HOLDS_READER))")
    done = subprocess.run([sys.executable, "-S", "-c", probe, str(isolated_home / "current")], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == os.path.realpath(reader)


# ---- the runtime is compiled once, at install ---------------------------------------------------------------------
# A hook is a new Python process on every tool call. A caller whose environment says to write no bytecode caches
# nothing it compiles, so the guards were compiled from their source on every call: about 72 ms for a shell
# command's check on the principal's Mac, against a 50 ms budget, and 33 ms once the runtime carried compiled code
# (2026-11-12, measured on 5.8.0).

def _compiled(runtime) -> set:
    """The runtime's modules this interpreter finds compiled code for, where it looks for it: beside the source, or
    under the prefix an interpreter keeps its compiled code in (Apple's Python has one, keyed by the path a module
    is imported from, which for a hook is the path through `current`)."""
    from importlib.util import cache_from_source
    return {path.stem for path in (runtime / "synthesis").glob("*.py") if Path(cache_from_source(str(path))).is_file()}


def test_the_runtime_carries_compiled_code_whatever_the_callers_environment_says(tmp_path, isolated_home, monkeypatch):
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    plugin = _plugin_copy(tmp_path)
    install.install(plugin)
    assert {"guards", "hook", "approvals", "paths", "commit_check", "reply_check"} <= _compiled(isolated_home / "current")
    assert not (plugin / "synthesis" / "__pycache__").exists()  # the plugin folder stays as its harness installed it
    assert install.current_hash() == install.package_hash(plugin)  # the hash is of the source, not of what was compiled


def test_a_hook_started_from_the_compiled_runtime_guards_as_before(tmp_path, isolated_home):
    install.install(_plugin_copy(tmp_path))
    out = _run_hook(isolated_home, "pre-tool-use", {"tool_name": "Bash", "tool_input": {"command": "rm -rf ~"}})
    assert json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_an_install_over_a_runtime_without_compiled_code_adds_it(tmp_path, isolated_home):
    """A runtime installed before this, or one whose compiled code was cleaned away, is repaired by the next install
    of the same release: nothing is rebuilt, and the compiled code is put back."""
    plugin = _plugin_copy(tmp_path)
    install.install(plugin)
    runtime = isolated_home / "current"
    from importlib.util import cache_from_source
    for source in (runtime / "synthesis").glob("*.py"):
        Path(cache_from_source(str(source))).unlink()
    assert _compiled(runtime) == set()
    stamp = (runtime / "SOURCE").read_text(encoding="utf-8")
    install.install(plugin)
    assert "guards" in _compiled(runtime) and (runtime / "SOURCE").read_text(encoding="utf-8") == stamp


def test_a_session_start_compiles_a_runtime_that_reached_it_uncompiled(tmp_path, isolated_home, monkeypatch):
    """An upgrade through a harness is made by the session start of the runtime already there. From a release before
    5.8.1 that is an installer that compiles nothing, and 5.8.1's own session start then found the runtime "not newer"
    and returned before it compiled anything: such a Mac kept the slow hook until someone ran an install by hand
    (found by a review before 5.8.1 was released). The interpreter a hook runs on can change under a runtime the
    same way."""
    plugin = _plugin_copy(tmp_path)
    with monkeypatch.context() as older:
        older.setattr(install, "_compile", lambda package: None)  # the installer of a release before 5.8.1
        install.install(plugin)
    runtime = isolated_home / "current"
    assert _compiled(runtime) == set()
    assert "is not newer" in install.install(plugin, forward_only=True)
    assert {"guards", "hook", "approvals", "paths"} <= _compiled(runtime)
    import compileall
    monkeypatch.setattr(compileall, "compile_dir", lambda *args, **kwargs: pytest.fail("a compiled runtime was compiled again"))
    assert "is not newer" in install.install(plugin, forward_only=True)  # every later session start only looks


def test_compiled_code_is_held_to_its_source_and_not_to_its_date(tmp_path, isolated_home):
    """Python takes a compiled file for current when its source has the date and the size the file recorded. Under an
    interpreter that keeps compiled code by path, every release is read through the one path `current`, so a file of
    the next release with the same size and date ran the release before it. A compiled file carries its source's
    hash instead, and is checked against it each time it is loaded."""
    from importlib.util import cache_from_source
    install.install(_plugin_copy(tmp_path))
    source = isolated_home / "current" / "synthesis" / "__init__.py"
    was, text = source.stat(), source.read_text(encoding="utf-8")
    release = ".".join(str(part) for part in install.version(isolated_home / "current"))
    other = "9" * len(release)
    source.write_text(text.replace(f'"{release}"', f'"{other}"'), encoding="utf-8")
    os.utime(source, ns=(was.st_atime_ns, was.st_mtime_ns))
    assert (source.stat().st_size, int(source.stat().st_mtime)) == (was.st_size, int(was.st_mtime)) and other != release
    said = subprocess.run([sys.executable, "-S", "-c", "import sys; sys.path.insert(0, sys.argv[1]); import synthesis; "
                           "print(synthesis.__version__)", str(isolated_home / "current")], capture_output=True, text=True,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert said.stdout.strip() == other, said.stderr
    assert Path(cache_from_source(str(source.with_name("guards.py")))).read_bytes()[4] & 3 == 3  # hashed, and checked


def test_an_interpreter_with_nowhere_to_keep_compiled_code_still_gets_a_whole_install(tmp_path, isolated_home, monkeypatch):
    """Compiling saves time and is never a step an install can fail on. With no cache tag the standard library raises
    NotImplementedError, which went past the one error the installer caught and left `current` switched and the hook
    script unwritten."""
    monkeypatch.setattr(sys.implementation, "cache_tag", None)
    install.install(_plugin_copy(tmp_path))
    assert (isolated_home / "bin" / "synthesis-hook").is_file() and install.current_hash()


# ---- review round 2 of 5.21.0, R2-2: the runtime never goes while Codex's own hooks file runs it -------------------

def _codex_declares(command):
    codex = Path(os.environ["CODEX_HOME"])
    codex.mkdir(parents=True, exist_ok=True)
    (codex / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": command}]}]}}))
    return codex


def test_uninstall_refuses_while_codexs_own_hooks_file_runs_the_stable_hook(tmp_path, isolated_home, capsys):
    """`synthesis uninstall` took the runtime and left Codex's user-level hooks calling it, and the guard's then held every
    call in Codex, with nothing left there to put the runtime back (q07)."""
    from synthesis import cli
    install.install(_plugin_copy(tmp_path))
    _codex_declares('"$HOME/.synthesis/v5/bin/synthesis-hook" pre-tool-use')
    with pytest.raises(install.InUse, match="PreToolUse"):
        install.uninstall()
    assert (isolated_home / "bin" / "synthesis-hook").is_file()
    assert cli.main(["uninstall"]) == 1 and "setup.py uninstall" in capsys.readouterr().out
    assert (isolated_home / "bin" / "synthesis-hook").is_file()
    _codex_declares("echo mine")                                                   # a hook that never runs it
    assert any(line.startswith("removed") for line in install.uninstall())


# ---- review round 2 of 5.21.0, R2-7: the guard answers, closed, before a harness gives up on it --------------------

def test_a_guard_slower_than_its_deadline_answers_closed_inside_the_hooks_limit(tmp_path):
    """A slow guard (a cold repository read, a lock) ran past the 5 seconds a harness gives the hook, and Codex and Muse
    let the call through. The guard keeps a deadline of its own under that, and its work, git and every other process
    it starts, stops there with a deny."""
    from synthesis import hook
    assert hook.GUARD_SECONDS <= 4
    code = (f"import sys, time; sys.path.insert(0, {str(ROOT)!r}); from synthesis import hook, guards; "
            "hook.GUARD_SECONDS = 0.5; guards.check = lambda *a, **k: time.sleep(10); "
            "sys.exit(hook.main(['synthesis-hook', 'pre-tool-use']))")
    began = time.monotonic()
    done = subprocess.run([sys.executable, "-c", code], input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}}),
                          capture_output=True, text=True, timeout=30, env={**os.environ, "SYNTHESIS_HOME": str(tmp_path / "home")})
    decision = json.loads(done.stdout)["hookSpecificOutput"]
    assert done.returncode == 0 and decision["permissionDecision"] == "deny" and time.monotonic() - began < 5
    assert "did not answer within 0.5 seconds" in decision["permissionDecisionReason"]

