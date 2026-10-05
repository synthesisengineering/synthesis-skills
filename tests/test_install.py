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


def test_cli_shim_runs_the_installed_copy(tmp_path, isolated_home):
    install.install(_plugin_copy(tmp_path))
    out = subprocess.run([str(isolated_home / "bin" / "synthesis"), "version"], capture_output=True, text=True,
                         env={**os.environ, "SYNTHESIS_HOME": str(isolated_home)})
    assert out.returncode == 0 and out.stdout.strip().startswith("5.")


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
