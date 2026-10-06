"""R7.1 and R7.5: one stable hook path that survives upgrades and deleted plugin folders."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

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
    assert (home / ".synthesis" / "v5" / "state" / "sessions" / "fresh.json").is_file()


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


def test_the_cli_installs_from_a_plugin_folder(tmp_path, isolated_home, capsys):
    from synthesis import cli
    assert cli.main(["install", str(_plugin_copy(tmp_path))]) == 0
    assert "synthesis runtime" in capsys.readouterr().out
    assert (isolated_home / "bin" / "synthesis-hook").is_file()
