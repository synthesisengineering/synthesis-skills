"""Every channel (Rajiv, 2026-10-13): a call is a send by what it does, in a connector or the shell; own
repositories are not sends; a send window, opened only with the principal's code, lets signed sends go
without a per-message code, and every send the guard lets through is in the day's ledger."""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from synthesis import guards, sends

ROOT = Path(__file__).resolve().parents[1]
CONFIG = {"own_repos": ["me-owner/*"], "send_window_signatures": [r"hasn't reviewed the details yet"]}
SIGNED = "Status is green.\n\n🤖 _Helperbot here; the principal hasn't reviewed the details yet_"


@pytest.mark.parametrize("tool", [
    "mcp__85ff__addCommentToJiraIssue", "mcp__85ff__createJiraIssue", "mcp__85ff__editJiraIssue",
    "mcp__85ff__createConfluenceFooterComment", "mcp__85ff__updateConfluencePage", "mcp__ws__manage_document_comment",
    "mcp__c362__notion-create-comment", "mcp__c362__notion-create-pages", "mcp__71d6__create_file_comment",
    "mcp__ws__create_reaction", "mcp__13d2__slack_create_canvas", "mcp__7ec6__sendReminder",
    "mcp__github__create_pull_request", "mcp__github__add_issue_comment", "mcp__71d6__share_file",
    "mcp__ws__set_drive_file_permissions", "mcp__552d__execute_zapier_write_action", "mcp__ws__manage_out_of_office"])
def test_a_tool_that_delivers_words_to_people_is_a_send(tool):
    assert sends.says(tool, {})


@pytest.mark.parametrize("tool", [
    "mcp__85ff__getJiraIssue", "mcp__ws__list_document_comments", "mcp__13d2__slack_read_channel", "mcp__71d6__create_folder",
    "mcp__85ff__createIssueLink", "mcp__85ff__addWorklogToJiraIssue", "mcp__apple-notes__create_note",
    "mcp__github__merge_pull_request", "mcp__c362__notion-create-database", "mcp__ccd_session_mgmt__send_message",
    "mcp__c362__notion-send-message-to-session", "mcp__ws__create_doc", "mcp__85ff__transitionJiraIssue"])
def test_reads_and_writes_no_one_reads_are_not_sends(tool):
    assert not sends.says(tool, {})


def test_a_jira_comment_waits_for_a_code_and_work_in_an_own_repository_does_not():
    assert "approval" in guards.check("mcp__85ff__addCommentToJiraIssue", {"issueIdOrKey": "AB-1", "commentBody": "Done."}, CONFIG)
    pr = {"owner": "me-owner", "repo": "tools", "title": "Fix", "body": "Fixes the parser."}
    assert guards.check("mcp__github__create_pull_request", pr, CONFIG) is None
    assert "approval" in guards.check("mcp__github__create_pull_request", {**pr, "owner": "team"}, CONFIG)


@pytest.mark.parametrize("command,posts", [
    ('gh pr comment 12 -R team/app --body "Looks good."', True),
    ('gh pr comment 12 -R me-owner/tools --body "Looks good."', False),
    ('gh issue view 12 -R team/app', False),
    ('bkt pr comment 5 -m "Approved from my side."', True),
    ("curl -X POST https://api.example.com/v1/notes -d '{\"text\": \"hi\"}'", True),
    ("curl -s https://api.example.com/v1/notes", False),
    ("curl -X POST http://localhost:3000/api/notes -d x=1", False),
    ("gh api repos/team/app/issues/1/comments -f body=hi", True),
    ("gh api repos/me-owner/tools/issues/1/comments -f body=hi", False),
    ("gh api graphql -f query='query { viewer { login } }'", False),
    ("http POST https://api.example.com/v1/notes text=hi", True),
])
def test_a_shell_command_that_posts_waits_for_a_code(command, posts, tmp_path):
    reason = guards.check("Bash", {"command": command}, CONFIG, cwd=str(tmp_path))
    assert (reason is not None and "posts to" in reason) is posts, reason


def test_a_posted_body_file_is_scanned_and_one_the_guard_cannot_read_is_refused(tmp_path):
    config = {**CONFIG, "forbidden_phrases": [{"name": "delay-apology", "pattern": r"sorry for the delay"}]}
    (tmp_path / "reply.md").write_text("Sorry for the delay. Merged now.\n", encoding="utf-8")
    command = "gh pr comment 12 -R team/app --body-file reply.md"
    assert "delay-apology" in guards.check("Bash", {"command": command}, config, cwd=str(tmp_path))
    missing = guards.check("Bash", {"command": command.replace("reply.md", "absent.md")}, config, cwd=str(tmp_path))
    assert "cannot read" in missing


def test_a_window_lets_signed_sends_in_its_channels_go_and_logs_each(tmp_path):
    jira = ("mcp__85ff__addCommentToJiraIssue", {"issueIdOrKey": "AB-1", "commentBody": SIGNED})
    sends.open_window(2, ["jira", "bitbucket"])
    assert guards.check(*jira, CONFIG) is None
    assert guards.check("Bash", {"command": f'bkt pr comment 5 -m "{SIGNED}"'}, CONFIG, cwd=str(tmp_path)) is None
    assert "approval" in guards.check(jira[0], {"issueIdOrKey": "AB-1", "commentBody": "Unsigned."}, CONFIG)
    assert "approval" in guards.check("mcp__13d2__slack_send_message", {"channel_id": "C1", "message": SIGNED}, CONFIG)
    assert [e["how"] for e in sends.ledger(time.strftime("%Y-%m-%d"))] == ["window", "window"]
    sends.close_window()
    assert "approval" in guards.check(*jira, CONFIG)


def test_a_window_is_capped_ends_by_itself_and_can_be_scoped_to_a_project():
    with pytest.raises(ValueError, match="at most 12 hours"):
        sends.open_window(13, ["jira"])
    with pytest.raises(ValueError, match="name the channels"):
        sends.open_window(2, [])
    data = sends.open_window(1, ["all"], project="alpha")
    assert sends.covered("jira", [SIGNED], "alpha", CONFIG) and not sends.covered("jira", [SIGNED], "beta", CONFIG)
    (sends._window_file()).write_text(json.dumps({**data, "until": time.time() - 1}), encoding="utf-8")
    assert sends.window() == {} and not sends.covered("jira", [SIGNED], "alpha", CONFIG)


def test_only_the_principal_opens_a_window(tmp_path, principal):
    for command in ("synthesis sends open --hours 6 --channels jira", "python3 -m synthesis.cli sends open --hours 6 --channels jira"):
        assert "type approve" in guards.check("Bash", {"command": command}, CONFIG, cwd=str(tmp_path))
    reason = guards.check("Bash", {"command": "synthesis sends open --hours 6 --channels jira"}, CONFIG, cwd=str(tmp_path))
    principal(reason)
    assert guards.check("Bash", {"command": "synthesis sends open --hours 6 --channels jira"}, CONFIG, cwd=str(tmp_path)) is None
    sneaky = "python3 -c 'from synthesis import sends; sends.open_window(12, [\"all\"])'"
    assert "send-window code" in guards.check("Bash", {"command": sneaky}, CONFIG, cwd=str(tmp_path))
    assert guards.check("Bash", {"command": "synthesis sends close"}, CONFIG, cwd=str(tmp_path)) is None


def test_the_command_line_and_the_prompt_hook_show_an_open_window():
    def cli(*args):
        return subprocess.run([sys.executable, "-m", "synthesis.cli", "sends", *args], capture_output=True, text=True, cwd=ROOT)
    assert cli("open", "--hours", "13", "--channels", "jira").returncode == 2
    opened = cli("open", "--hours", "3", "--channels", "jira,bitbucket")
    assert opened.returncode == 0 and "(bitbucket, jira)" in opened.stdout
    hook = subprocess.run([sys.executable, "-m", "synthesis.hook", "user-prompt-submit"], input=json.dumps(
        {"session_id": "S1", "prompt": "carry on"}), capture_output=True, text=True, cwd=ROOT).stdout
    assert "Send window open until" in hook
    assert "closed" in cli("close").stdout and "no send window" in cli("status").stdout
