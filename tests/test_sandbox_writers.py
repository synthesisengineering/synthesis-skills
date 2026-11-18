"""The guard's sandbox, part 1, its other writers (design 2.3 and 4.5; the principal's rulings of 2026-11-15).

The guard's own settings change only through `synthesis config apply <file>`, run outside the sandbox, which shows the
change and waits for the principal's code of exactly that content; that one unsandboxed line then needs no second code.
An MCP server runs outside every sandbox, so a tool of one that writes a file is judged by its path arguments against
the sealed and protected folders. And the installer refuses, naming why, where it cannot write the sealed runtime,
rather than install half of it.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from synthesis import approvals, guards, install, paths

ROOT = Path(__file__).resolve().parents[1]


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "synthesis.cli", *args], capture_output=True, text=True, cwd=ROOT,
                          stdin=subprocess.DEVNULL)


@pytest.fixture
def settings(tmp_path, write_config):
    write_config({"own_repos": ["me/*"]})
    new = tmp_path / "config.json"
    new.write_text(json.dumps({"own_repos": ["me/*", "team/*"], "sheet_hosts": ["rp-sheets"]}), encoding="utf-8")
    return new


# --- the guard's settings: `synthesis config apply` (design 2.3) ----------------------------------------------------------

def test_a_settings_change_waits_for_the_code_of_exactly_that_content(settings, principal):
    asked = _cli("config", "apply", str(settings))
    assert asked.returncode == 2 and "type approve followed by the code" in asked.stdout
    assert "own_repos" in asked.stdout and "sheet_hosts" in asked.stdout  # the change, key by key
    assert json.loads(paths.config_file().read_text(encoding="utf-8")) == {"own_repos": ["me/*"]}
    principal(asked.stdout)
    done = _cli("config", "apply", str(settings))
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(paths.config_file().read_text(encoding="utf-8")) == json.loads(settings.read_text(encoding="utf-8"))
    again = _cli("config", "apply", str(settings))
    assert again.returncode == 0 and "already" in again.stdout  # nothing to change, nothing asked


def test_a_settings_file_changed_after_the_code_is_another_change(settings, principal):
    principal(_cli("config", "apply", str(settings)).stdout)
    settings.write_text(json.dumps({"own_repos": ["*"]}), encoding="utf-8")
    later = _cli("config", "apply", str(settings))
    assert later.returncode == 2 and "type approve followed by the code" in later.stdout
    assert json.loads(paths.config_file().read_text(encoding="utf-8")) == {"own_repos": ["me/*"]}


@pytest.mark.parametrize("text", ["not json", "[]", '"a string"'])
def test_a_file_that_holds_no_settings_is_refused_and_asks_nothing(settings, text):
    settings.write_text(text, encoding="utf-8")
    refused = _cli("config", "apply", str(settings))
    assert refused.returncode == 2 and "JSON object" in refused.stderr and approvals.pending() == []


def test_the_launchers_settings_line_outside_the_sandbox_needs_only_the_code_of_the_change(settings, principal, tmp_path,
                                                                                         monkeypatch):
    launcher = str(paths.home() / "bin" / "synthesis")
    monkeypatch.setattr(guards, "_launcher", lambda word, name: word == launcher and name == "synthesis")
    line = f"{launcher} config apply {settings}"
    call = {"command": line, "dangerouslyDisableSandbox": True}
    assert "type approve followed by the code" in guards.check("Bash", call, {}, cwd=str(tmp_path))  # no change approved yet
    principal(_cli("config", "apply", str(settings)).stdout)
    assert guards.check("Bash", call, {}, cwd=str(tmp_path)) is None
    other = {"command": f"synthesis config apply {settings}", "dangerouslyDisableSandbox": True}  # a `synthesis` the guard cannot place
    assert "type approve followed by the code" in guards.check("Bash", other, {}, cwd=str(tmp_path))


# --- an MCP tool that writes a file (design 4.5) ---------------------------------------------------------------------

@pytest.mark.parametrize("tool, key", [("mcp__serena__create_text_file", "relative_path"), ("mcp__fs__write_file", "path"),
                                       ("mcp__serena__replace_content", "relative_path"), ("mcp__fs__move_file", "destination"),
                                       ("mcp__workspace-mcp__download_gmail_attachment", "save_path")])
def test_an_mcp_tool_that_writes_into_a_sealed_folder_is_refused(tool, key, tmp_path):
    for target in (paths.approvals() / "grants" / ("a" * 64 + ".json"), paths.home() / "current" / "synthesis" / "approvals.py",
                   paths.transcript_roots()["claude-code"] / "-work" / "s.jsonl"):
        reason = guards.check(tool, {key: str(target), "content": "{}"}, {}, cwd=str(tmp_path))
        assert reason and reason.startswith("Refused") and "MCP" in reason, (tool, target)


def test_an_mcp_tool_that_reads_there_or_writes_elsewhere_passes(tmp_path):
    grant = str(paths.approvals() / "grants" / ("a" * 64 + ".json"))
    assert guards.check("mcp__serena__read_file", {"relative_path": grant}, {}, cwd=str(tmp_path)) is None
    assert guards.check("mcp__fs__write_file", {"path": str(tmp_path / "notes.md"), "content": "x"}, {}, cwd=str(tmp_path)) is None
    memory = paths.transcript_roots()["claude-code"] / "-work" / "memory" / "notes.md"  # the agent's own, as for the file tools
    assert guards.check("mcp__fs__write_file", {"path": str(memory), "content": "x"}, {}, cwd=str(tmp_path)) is None


# --- the installer where it cannot write the sealed runtime (design 4.5) ----------------------------------------------------

def test_an_install_that_cannot_write_the_sealed_runtime_refuses_and_installs_nothing(isolated_home):
    if os.geteuid() == 0:
        pytest.skip("root writes a folder whatever its mode")
    (isolated_home / "releases").mkdir(parents=True)
    (isolated_home / "releases").chmod(0o555)
    try:
        with pytest.raises(install.Refused, match="cannot write") as refused:
            install.install(ROOT)
    finally:
        (isolated_home / "releases").chmod(0o755)
    assert str(isolated_home / "releases") in str(refused.value) and not os.path.lexists(isolated_home / "current")
    assert not (isolated_home / "bin").exists()


def test_a_settings_path_that_is_no_regular_file_never_holds_the_guard_or_the_command(tmp_path, monkeypatch, capsys):
    """The guard reads the file an agent names in a settings line: a FIFO there must not hold it to its deadline."""
    import time
    from synthesis import hook
    fifo = tmp_path / "settings.fifo"
    os.mkfifo(fifo)
    launcher = str(paths.home() / "bin" / "synthesis")
    monkeypatch.setattr(guards, "_launcher", lambda word, name: word == launcher)
    began = time.monotonic()
    hook.pre_tool_use({"session_id": "S1", "tool_name": "Bash", "cwd": str(tmp_path),
                       "tool_input": {"command": f"{launcher} config apply {fifo}", "dangerouslyDisableSandbox": True}})
    held = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "type approve followed by the code" in held and time.monotonic() - began < 2, held
    refused = subprocess.run([sys.executable, "-m", "synthesis.cli", "config", "apply", str(fifo)], capture_output=True, text=True,
                             cwd=ROOT, stdin=subprocess.DEVNULL, timeout=20)
    assert refused.returncode == 2 and "JSON object" in refused.stderr
