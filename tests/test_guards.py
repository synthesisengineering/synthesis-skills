"""R3: protection. Sends and deploys need a single-use approval of the exact thing."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from synthesis import approvals, guards

SLACK = "mcp__slack__slack_send_message"
MESSAGE = {"channel_id": "C1", "message": "The release is out."}


def test_send_is_blocked_until_the_exact_text_is_approved_and_then_allowed_once():
    assert "approval" in guards.check(SLACK, MESSAGE, {})
    approvals.record("send", {"tool": SLACK, "input": MESSAGE})
    assert guards.check(SLACK, {**MESSAGE, "message": "The release is out!"}, {}) is not None
    assert guards.check(SLACK, MESSAGE, {}) is None
    assert guards.check(SLACK, MESSAGE, {}) is not None  # spent


def test_expired_approval_does_not_open_the_gate(monkeypatch):
    approvals.record("send", {"tool": SLACK, "input": MESSAGE})
    monkeypatch.setattr(approvals, "TTL_SECONDS", -1)
    assert guards.check(SLACK, MESSAGE, {}) is not None


def test_forbidden_phrase_blocks_even_an_approved_message():
    config = {"forbidden_phrases": [{"name": "no-apology", "pattern": r"\bsorry\b", "why": "never apologize"}]}
    text = {"channel_id": "C1", "message": "Sorry for the delay."}
    approvals.record("send", {"tool": SLACK, "input": text})
    assert "no-apology" in guards.check(SLACK, text, config)


@pytest.mark.parametrize("tool", ["mcp__workspace-mcp__send_gmail_message", "mcp__workspace_mcp__draft_gmail_message",
                                  "mcp__d01c6c5a__reply", "mcp__apple-mail__send_email"])
def test_every_client_spelling_of_a_send_tool_is_guarded(tool):
    assert guards.is_send_tool(tool, {})


@pytest.mark.parametrize("tool", ["mcp__slack__slack_read_channel", "Read", "mcp__gmail__search_threads"])
def test_reads_are_never_guarded(tool):
    assert guards.check(tool, {"query": "x"}, {}) is None


def test_deploy_needs_approval_of_that_exact_command():
    command = "cd ~/site && bash build.sh && wrangler pages deploy dist --project-name=site"
    assert "production" in guards.check("Bash", {"command": command}, {})
    approvals.record("deploy", command)
    assert guards.check("Bash", {"command": command}, {}) is None
    assert guards.check("Bash", {"command": command}, {}) is not None


def test_push_to_a_repo_that_deploys_on_push_counts_as_a_deploy(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    config = {"push_deploys": [str(site)]}
    assert guards.check("Bash", {"command": f"git -C {site} push origin main"}, config) is not None
    assert guards.check("Bash", {"command": f"git -C {tmp_path} push origin main"}, config) is None


@pytest.mark.parametrize("command", ["rm -rf ~", "rm -rf ~/workspaces", "rm -Rf /", "ls && rm -rf $HOME/workspaces"])
def test_recursive_delete_of_a_protected_root_is_refused(command):
    if "$HOME" in command:
        command = command.replace("$HOME", str(Path.home()))
    assert "protected" in guards.check("Bash", {"command": command}, {})


def test_recursive_delete_of_a_repository_root_is_refused_but_its_build_dir_is_not(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "build").mkdir()
    assert guards.check("Bash", {"command": f"rm -rf {repo}"}, {}) is not None
    assert guards.check("Bash", {"command": f"rm -rf {repo / 'build'}"}, {}) is None


@pytest.mark.parametrize("command,blocked", [("git push --force origin main", True),
                                             ("git push -f origin HEAD:master", True),
                                             ("git push --force origin feature/x", False),
                                             ("git status", False), ("ls -la", False)])
def test_force_push_only_to_default_branches_is_refused(command, blocked):
    assert (guards.check("Bash", {"command": command}, {}) is not None) is blocked


@pytest.mark.parametrize("tool,tool_input", [("exec_command", {"cmd": ["rm", "-rf", str(Path.home())]}),
                                             ("shell", {"command": ["bash", "-lc", "rm -rf ~"]}),
                                             ("local_shell", {"command": "rm -rf ~"})])
def test_every_harness_shell_tool_is_guarded(tool, tool_input):
    assert guards.check(tool, tool_input, {}) is not None


def _hook(event, payload, env):
    return subprocess.run([sys.executable, "-m", "synthesis.hook", event], input=json.dumps(payload),
                          capture_output=True, text=True, env=env,
                          cwd=Path(__file__).resolve().parents[1])


def test_unreadable_config_blocks_sends_and_bash_but_not_other_tools(isolated_home, monkeypatch):
    import os
    isolated_home.mkdir(parents=True, exist_ok=True)
    (isolated_home / "config.json").write_text("{not json", encoding="utf-8")
    env = {**os.environ, "SYNTHESIS_HOME": str(isolated_home)}
    for tool in (SLACK, "Bash"):
        out = _hook("pre-tool-use", {"tool_name": tool, "tool_input": {"command": "ls"}}, env)
        assert json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    out = _hook("pre-tool-use", {"tool_name": "Read", "tool_input": {}}, env)
    assert out.stdout.strip() == ""
