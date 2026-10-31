"""R3: protection. Sends and deploys need a single-use approval of the exact thing."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from synthesis import approvals, guards

SLACK = "mcp__slack__slack_send_message"
MESSAGE = {"channel_id": "C1", "message": "The release is out."}


def _code(reason):
    return re.search(r'code ([a-z0-9]{6})', reason).group(1)


def test_send_is_blocked_until_the_principal_types_its_code_and_then_allowed_once(principal):
    reason = guards.check(SLACK, MESSAGE, {})
    assert "approval" in reason
    assert principal(reason, "yes, approve {code}") == [f"{SLACK}: C1 The release is out."]
    assert guards.check(SLACK, {**MESSAGE, "message": "The release is out!"}, {}) is not None
    assert guards.check(SLACK, MESSAGE, {}) is None
    assert guards.check(SLACK, MESSAGE, {}) is not None  # spent


def test_an_unknown_or_agent_invented_code_grants_nothing():
    guards.check(SLACK, MESSAGE, {})
    assert approvals.grant_from_prompt("approve abcdef") == []
    assert guards.check(SLACK, MESSAGE, {}) is not None


def test_the_cli_offers_no_way_to_approve():
    from synthesis import cli
    assert "approve" not in cli.parser().format_help().replace("approvals", "")


def test_expired_approval_does_not_open_the_gate(monkeypatch, principal):
    principal(guards.check(SLACK, MESSAGE, {}))
    monkeypatch.setattr(approvals, "TTL_SECONDS", -1)
    assert guards.check(SLACK, MESSAGE, {}) is not None


def test_forbidden_phrase_blocks_even_an_approved_message():
    config = {"forbidden_phrases": [{"name": "no-apology", "pattern": r"\bsorry\b", "why": "never apologize"}]}
    text = {"channel_id": "C1", "message": "Sorry for the delay."}
    assert "no-apology" in guards.check(SLACK, text, config)


@pytest.mark.parametrize("tool", ["mcp__workspace-mcp__send_gmail_message", "mcp__workspace_mcp__draft_gmail_message",
                                  "mcp__d01c6c5a__reply", "mcp__apple-mail__send_email"])
def test_every_client_spelling_of_a_send_tool_is_guarded(tool):
    assert guards.is_send_tool(tool, {})


@pytest.mark.parametrize("tool", ["mcp__slack__slack_read_channel", "Read", "mcp__gmail__search_threads"])
def test_reads_are_never_guarded(tool):
    assert guards.check(tool, {"query": "x"}, {}) is None


def test_deploy_needs_approval_of_that_exact_command(principal):
    command = "cd ~/site && bash build.sh && wrangler pages deploy dist --project-name=site"
    reason = guards.check("Bash", {"command": command}, {})
    assert "production" in reason
    principal(reason)
    assert guards.check("Bash", {"command": command}, {}) is None
    assert guards.check("Bash", {"command": command}, {}) is not None


def test_push_to_a_repo_that_deploys_on_push_counts_as_a_deploy(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    config = {"push_deploys": [str(site)]}
    assert guards.check("Bash", {"command": f"git -C {site} push origin main"}, config) is not None
    assert guards.check("Bash", {"command": f"git -C {tmp_path} push origin main"}, config) is None


def test_a_deploy_inside_a_script_the_command_runs_needs_approval(tmp_path):
    """2026-10-30: `bash scripts/publish-site.sh` published a site; the wrangler call was inside the script."""
    (tmp_path / "scripts").mkdir()
    publish = tmp_path / "scripts" / "publish-site.sh"
    publish.write_text('#!/bin/bash\nset -eu\nSITE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"\nbash build.sh\n'
                       'npx wrangler pages deploy "$SITE_ROOT" --project-name=tool --branch=main\n')
    publish.chmod(0o755)
    (tmp_path / "build.sh").write_text("#!/bin/bash\nnpx astro build\nnpx wrangler deploy --dry-run --outdir out\n")
    (tmp_path / "wrapper.sh").write_text("#!/bin/sh\nexec bash scripts/publish-site.sh \"$@\"\n")
    for command in ("bash scripts/publish-site.sh", "./scripts/publish-site.sh", "sh -e wrapper.sh",
                    f"cd {tmp_path} && bash -o pipefail scripts/publish-site.sh"):
        assert "production" in guards.check("Bash", {"command": command}, {}, cwd=str(tmp_path)), command
    for command in ("bash build.sh", "bash missing.sh", "bash -c 'echo hi'", "./build.sh"):
        assert guards.check("Bash", {"command": command}, {}, cwd=str(tmp_path)) is None, command


@pytest.mark.parametrize("command", ["npx wrangler deploy --dry-run", "npm publish --dry-run",
                                     "npx wrangler pages deploy dist --dry-run"])
def test_a_dry_run_publishes_nothing(command):
    assert guards.check("Bash", {"command": command}, {}) is None


def test_the_desktop_apps_terminal_tab_is_guarded_like_bash(tmp_path):
    """2026-10-30: commands typed into the Claude desktop app's terminal tab passed every shell guard."""
    tab = "mcp__terminal__run_in_terminal"
    assert "protected" in guards.check(tab, {"command": "rm -rf ~"}, {})
    assert "production" in guards.check(tab, {"command": "npx wrangler pages deploy dist"}, {})
    (tmp_path / "publish.sh").write_text("#!/bin/sh\nnpm publish --access public\n")
    assert "production" in guards.check(tab, {"command": "sh publish.sh", "cwd": str(tmp_path)}, {}, cwd="/")
    assert guards.check(tab, {"command": "ls -la"}, {}) is None
    assert guards.guarded(tab, {"command": "ls"})


def test_a_push_or_merge_to_a_repository_that_publishes_needs_approval(tmp_path):
    """2026-10-30: a merge on the Homebrew tap published a formula before its release existed."""
    tap = tmp_path / "tap"
    subprocess.run(["git", "init", "-q", str(tap)], check=True)
    subprocess.run(["git", "-C", str(tap), "remote", "add", "origin", "https://github.com/acme/homebrew-tap.git"], check=True)
    (tap / "Formula").mkdir()
    (tap / "Formula" / "tool.rb").write_text("class Tool < Formula\nend\n")
    subprocess.run(["git", "-C", str(tap), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tap), "-c", "user.name=t", "-c", "user.email=t@example.test", "-c", "core.hooksPath=/dev/null",
                    "commit", "-qm", "formula"], check=True)
    config = {"deploy_remotes": ["acme/homebrew-tap"]}
    assert "production" in guards.check("Bash", {"command": f"git -C {tap} push origin main"}, config)
    assert "production" in guards.check("Bash", {"command": "gh pr merge 13 -R acme/homebrew-tap --merge"}, config)
    assert "production" in guards.check("Bash", {"command": "gh pr merge 13 --merge"}, config, cwd=str(tap))
    assert guards.check("Bash", {"command": "gh pr merge 13 -R acme/other --merge"}, config) is None
    assert guards.check("Bash", {"command": f"git -C {tap} push origin main"}, {}) is None


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
                                             ("local_shell", {"command": "rm -rf ~"}),
                                             ("bash", {"command": "rm -rf ~"})])  # Muse's spelling
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


def test_unreadable_config_blocks_routed_calendar_and_mail_calls(isolated_home):
    import os
    isolated_home.mkdir(parents=True, exist_ok=True)
    (isolated_home / "config.json").write_text("{not json", encoding="utf-8")
    env = {**os.environ, "SYNTHESIS_HOME": str(isolated_home)}
    out = _hook("pre-tool-use", {"tool_name": "mcp__google__create_event", "tool_input": {"summary": "x"}}, env)
    assert json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_a_spent_or_expired_approval_leaves_no_file_behind(isolated_home, monkeypatch, principal):
    reason = guards.check(SLACK, MESSAGE, {})
    principal(reason)
    assert guards.check(SLACK, MESSAGE, {}) is None
    assert list((isolated_home / "state" / "approvals").iterdir()) == []
    guards.check(SLACK, {**MESSAGE, "message": "another"}, {})
    import os
    import time
    old = time.time() - approvals.TTL_SECONDS - 60
    for f in (isolated_home / "state" / "approval-requests").iterdir():
        os.utime(f, (old, old))
    code = approvals.request("send", "fresh", "fresh")
    assert [f.stem for f in (isolated_home / "state" / "approval-requests").iterdir()] == [code]
