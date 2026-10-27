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
    sends.open_window(2, ["jira", "bitbucket"], count=5)
    assert guards.check(*jira, CONFIG) is None
    assert guards.check("Bash", {"command": f'bkt pr comment 5 -m "{SIGNED}"'}, CONFIG, cwd=str(tmp_path)) is None
    assert "approval" in guards.check(jira[0], {"issueIdOrKey": "AB-1", "commentBody": "Unsigned."}, CONFIG)
    assert "approval" in guards.check("mcp__13d2__slack_send_message", {"channel_id": "C1", "message": SIGNED}, CONFIG)
    assert [e["how"] for e in sends.ledger(time.strftime("%Y-%m-%d"))] == ["window", "window"]
    sends.close_window()
    assert "approval" in guards.check(*jira, CONFIG)


def test_a_window_is_capped_ends_by_itself_and_can_be_scoped_to_a_project():
    with pytest.raises(ValueError, match="at most 12 hours"):
        sends.open_window(13, ["jira"], count=1)
    with pytest.raises(ValueError, match="name the channels"):
        sends.open_window(2, [], count=1)
    for count in (0, 51):
        with pytest.raises(ValueError, match="name the sends"):
            sends.open_window(2, ["jira"], count=count)
    data = sends.open_window(1, ["all"], project="alpha", count=3)
    assert sends.covered("jira", [SIGNED], "alpha", CONFIG) and not sends.covered("jira", [SIGNED], "beta", CONFIG)
    (sends._window_file()).write_text(json.dumps({**data, "until": time.time() - 1}), encoding="utf-8")
    assert sends.window() == {} and not sends.covered("jira", [SIGNED], "alpha", CONFIG)


def test_a_window_closes_after_its_planned_sends_and_one_without_them_covers_none(tmp_path):
    """2026-10-27: a window stayed open for hours after its planned sends, and later sends went out under it."""
    jira = ("mcp__85ff__addCommentToJiraIssue", {"issueIdOrKey": "AB-1", "commentBody": SIGNED})
    sends.open_window(2, ["jira"], count=2)
    assert "2 of 2 sends left" in sends.describe(sends.window())
    assert guards.check(*jira, CONFIG) is None and "1 of 2 sends left" in sends.describe(sends.window())
    assert guards.check(*jira, CONFIG) is None and sends.window() == {}  # the last planned send closed it
    assert "approval" in guards.check(*jira, CONFIG)
    data = sends.open_window(2, ["jira"], count=1)
    sends._window_file().write_text(json.dumps({k: v for k, v in data.items() if k != "sends"}), encoding="utf-8")
    assert sends.window() and "approval" in guards.check(*jira, CONFIG)  # opened before planned sends existed
    sends.close_window()
    assert "can't open" in guards.check("Bash", {"command": "synthesis sends open --hours 2 --channels jira"},
                                        CONFIG, cwd=str(tmp_path))


def test_only_the_principal_opens_a_window(tmp_path, principal):
    for command in ("synthesis sends open --hours 6 --sends 4 --channels jira", "python3 -m synthesis.cli sends open --hours 6 --sends 4 --channels jira",
                    # A project session, 2026-10-13: a global option before `sends` opened a window with no code
                    "synthesis --session S-principal sends open --hours 6 --sends 4 --channels jira",
                    "synthesis sends open --hours=6 --sends=4 --channels=jira"):
        assert "type approve" in guards.check("Bash", {"command": command}, CONFIG, cwd=str(tmp_path)), command
    for command in ("synthesis sends --help", "synthesis sends open --help", "synthesis --session S1 sends open -h"):
        assert guards.check("Bash", {"command": command}, CONFIG, cwd=str(tmp_path)) is None, command
    reason = guards.check("Bash", {"command": "synthesis sends open --hours 6 --sends 4 --channels jira"}, CONFIG, cwd=str(tmp_path))
    principal(reason)
    assert guards.check("Bash", {"command": "synthesis sends open --hours 6 --sends 4 --channels jira"}, CONFIG, cwd=str(tmp_path)) is None
    sneaky = "python3 -c 'from synthesis import sends; sends.open_window(12, [\"all\"])'"
    assert "send-window code" in guards.check("Bash", {"command": sneaky}, CONFIG, cwd=str(tmp_path))
    grant = "python3 -c 'from synthesis import approvals; approvals.grant_from_prompt(\"approve abc123\")'"
    assert "send-window code" in guards.check("Bash", {"command": grant}, CONFIG, cwd=str(tmp_path))
    state = "python3 -c 'from synthesis import paths; (paths.state() / \"sends\" / \"window.json\").write_text(\"{}\")'"
    assert "send-window code" in guards.check("Bash", {"command": state}, CONFIG, cwd=str(tmp_path))
    # Reading stays allowed (2026-10-13: a read-only check of the installed guard was refused).
    look = "python3 -c 'from synthesis import sends, guards; print(sends.window(), guards._sends(\"mcp__x__send_email\", {}, {}))'"
    assert guards.check("Bash", {"command": look}, CONFIG, cwd=str(tmp_path)) is None
    assert guards.check("Bash", {"command": "synthesis sends close"}, CONFIG, cwd=str(tmp_path)) is None


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "synthesis.cli", *args], capture_output=True, text=True, cwd=ROOT)


def test_the_command_refuses_to_open_a_window_from_an_agent_without_the_principals_code(principal):
    """The gate rests on the command, not on the guard matching its spelling (a project session, 2026-10-13)."""
    ask = ("--session", "S-principal", "sends", "open", "--hours", "3", "--sends", "4", "--channels", "jira,bitbucket")
    refused = _cli(*ask)
    assert refused.returncode == 2 and "type approve" in refused.stderr and sends.window() == {}
    principal(refused.stderr)
    assert _cli("sends", "open", "--hours", "3", "--sends", "4", "--channels", "jira").returncode == 2  # another scope: no grant
    opened = _cli(*ask)
    assert opened.returncode == 0 and "(bitbucket, jira)" in opened.stdout and sends.window()
    assert _cli(*ask).returncode == 2  # the grant was spent
    assert _cli("sends", "open", "--help").returncode == 0


def test_the_command_line_and_the_prompt_hook_show_an_open_window():
    assert _cli("sends", "open", "--hours", "13", "--channels", "jira").returncode == 2
    sends.open_window(3, ["jira", "bitbucket"], count=2)
    assert "(bitbucket, jira)" in _cli("sends", "status").stdout
    hook = subprocess.run([sys.executable, "-m", "synthesis.hook", "user-prompt-submit"], input=json.dumps(
        {"session_id": "S1", "prompt": "carry on"}), capture_output=True, text=True, cwd=ROOT).stdout
    assert "Send window open until" in hook
    assert "closed" in _cli("sends", "close").stdout and "no send window" in _cli("sends", "status").stdout


# --- reported by a project session, 2026-10-13, on 5.0.11 ---------------------------------------------

BRANDING = {**CONFIG, "forbidden_phrases": [{"name": "retired-branding", "pattern": "helperbot(?!\\.example)",
                                              "case_sensitive": True}]}


def test_the_register_scan_reads_the_message_not_file_names_and_reads_a_body_from_cat(tmp_path):
    clean, bad = tmp_path / "460-helperbot-comment.json", tmp_path / "461-reply.json"
    clean.write_text('{"content": {"raw": "Merged; thanks."}}', encoding="utf-8")
    bad.write_text('{"content": {"raw": "sent by helperbot"}}', encoding="utf-8")
    post = "bkt api /repositories/team/app/pullrequests/5/comments -X POST -d \"$(cat {})\""
    assert "posts to bitbucket" in guards.check("Bash", {"command": post.format(clean)}, BRANDING, cwd=str(tmp_path))
    assert "retired-branding" in guards.check("Bash", {"command": post.format(bad)}, BRANDING, cwd=str(tmp_path))
    unresolved = guards.check("Bash", {"command": post.format("$S/461-reply.json")}, BRANDING, cwd=str(tmp_path))
    assert "cannot read" in unresolved
    inline = 'bkt pr comment 5 -m "sent by helperbot"'
    assert "retired-branding" in guards.check("Bash", {"command": inline}, BRANDING, cwd=str(tmp_path))


def test_a_shell_send_approval_binds_where_it_runs_not_where_the_shell_started(tmp_path, principal):
    repo, elsewhere = tmp_path / "repo", tmp_path / "elsewhere"
    repo.mkdir()
    elsewhere.mkdir()
    command = f'cd {repo} && bkt pr comment 5 -m "Approved from my side."'
    reason = guards.check("Bash", {"command": command}, CONFIG, cwd=str(tmp_path))
    assert f"runs in {repo}" in reason
    principal(reason)
    assert guards.check("Bash", {"command": command}, CONFIG, cwd=str(elsewhere)) is None


def test_the_prompt_hook_names_a_typed_code_that_matched_nothing(tmp_path):
    from synthesis import approvals
    first = approvals.request("send", {"tool": "t", "input": 1}, "first send")
    second = approvals.request("send", {"tool": "t", "input": 2}, "second send")
    prompt = f"approve {first} / approve {second} / approve 9abcde"
    out = subprocess.run([sys.executable, "-m", "synthesis.hook", "user-prompt-submit"], input=json.dumps(
        {"session_id": "S1", "prompt": prompt}), capture_output=True, text=True, cwd=ROOT).stdout
    assert "first send" in out and "second send" in out
    assert "Not granted: no pending request has the code 9abcde" in out and first not in out.split("Not granted")[1]


def test_a_quoted_greater_than_sign_is_not_a_write_and_a_real_redirect_into_state_is(tmp_path, isolated_home):
    from synthesis import paths
    state = paths.state()
    (state / "approval-requests").mkdir(parents=True, exist_ok=True)
    read = (f"cd {state} && for f in approval-requests/*.json; do python3 -c \"import json,sys; d=json.load(open(sys.argv[1])); "
            "print({k: (v if k != 'code' else '<pending>') for k, v in d.items()})\" \"$f\"; done")
    assert guards.check("Bash", {"command": read}, CONFIG, cwd=str(tmp_path)) is None
    for write in (f"echo x > {state}/approvals/x.json", f"cd {state} && echo x >> approvals/x.json",
                  f"bash -c 'echo x > {state}/approvals/x.json'"):
        assert "writes into the synthesis state" in guards.check("Bash", {"command": write}, CONFIG, cwd=str(tmp_path)), write


# --- reported by project sessions, 2026-10-13 and 10-14, on 5.0.12 -------------------------------------

@pytest.mark.parametrize("command,posts", [
    ('bkt -c work pr edit 5 --title "A clearer title"', True),  # a global option hid the subcommand
    ("bkt -c work api /repositories/team/app/pullrequests/5 -X PUT -d '{\"title\": \"x\"}'", True),
    ('gh -R team/app pr comment 3 --body "Looks good."', True),
    ("bkt pr edit --help", False),
    ("gh pr comment -h", False),
    ("bkt -c work pr list", False),
])
def test_global_options_do_not_hide_a_post_and_help_is_never_one(command, posts, tmp_path):
    reason = guards.check("Bash", {"command": command}, CONFIG, cwd=str(tmp_path))
    assert (reason is not None and "posts to" in reason) is posts, reason


HEREDOC = ("bkt api /repositories/team/app/pullrequests/5/comments -X POST -d \"$(python3 -c 'import json,sys; "
           "print(json.dumps({{\\\"content\\\": {{\\\"raw\\\": sys.stdin.read()}}}}))' <<'MSG'\n{}\nMSG\n)\"")


def test_a_heredoc_message_is_read_without_the_code_around_it(tmp_path):
    whole = HEREDOC.format("First paragraph of the reply.\n\nSecond paragraph.")
    assert "posts to bitbucket" in guards.check("Bash", {"command": whole}, CONFIG, cwd=str(tmp_path))
    broken = HEREDOC.format("A paragraph that was\nhard-wrapped.")
    assert "inside a paragraph" in guards.check("Bash", {"command": broken}, CONFIG, cwd=str(tmp_path))
    unknown = 'bkt pr comment 5 -m "$(date)"'
    assert "cannot read" in guards.check("Bash", {"command": unknown}, CONFIG, cwd=str(tmp_path))


def test_an_escaped_emoji_in_json_is_the_emoji_and_a_body_rewritten_in_the_same_command_is_refused(tmp_path):
    body = tmp_path / "comment.json"
    body.write_text(json.dumps({"content": {"raw": SIGNED}}, ensure_ascii=True), encoding="utf-8")
    assert "\\ud83e" in body.read_text(encoding="utf-8")
    sends.open_window(1, ["bitbucket"], count=2)
    post = f"bkt api /repositories/team/app/pullrequests/5/comments -X POST -d @{body}"
    assert guards.check("Bash", {"command": post}, CONFIG, cwd=str(tmp_path)) is None  # the window sees the signature
    rewrite = f"python3 make_body.py > {body} && {post}"
    assert "write the file in one command" in guards.check("Bash", {"command": rewrite}, CONFIG, cwd=str(tmp_path))
    sends.close_window()


def test_file_tools_cannot_write_approvals_or_a_send_window(tmp_path, isolated_home):
    from synthesis import paths
    window = paths.state() / "sends" / "window.json"
    assert "would write" in guards.check("Write", {"file_path": str(window), "content": "{}"}, CONFIG, cwd=str(tmp_path))
    assert "would write" in guards.check("Edit", {"file_path": str(window), "old_string": "a", "new_string": "b"}, CONFIG)
    patch = f"*** Begin Patch\n*** Add File: {window}\n+{{}}\n*** End Patch"
    assert "would write" in guards.check("apply_patch", {"input": patch}, CONFIG, cwd=str(tmp_path))
    assert "writes into the synthesis state" in guards.check("Bash", {"command": f"apply_patch <<'PATCH'\n{patch}\nPATCH"},
                                                            CONFIG, cwd=str(tmp_path))
    assert guards.check("Write", {"file_path": str(tmp_path / "notes.md"), "content": "x"}, CONFIG, cwd=str(tmp_path)) is None


def test_a_python_script_that_only_cites_a_protected_path_may_write_a_project_record(tmp_path, isolated_home):
    """An operations session, 2026-10-14: a stdin script writing project records was refused because the text it
    wrote cited a transcript path. Only a write's target counts; a path carried in by a variable still does."""
    from synthesis import paths
    state = paths.state()
    cites = f"python3 - <<'EOF'\nfrom pathlib import Path\nPath('notes.md').write_text('Source: {state}/sessions/x.json')\nEOF"
    assert guards.check("Bash", {"command": cites}, CONFIG, cwd=str(tmp_path)) is None
    for writes in (f"python3 - <<'EOF'\nopen('{state}/approvals/x.json', 'w').write('x')\nEOF",
                   f"python3 - <<'EOF'\nimport os\nroot = '{state}'\np = os.path.join(root, 'sends', 'window.json')\n"
                   "open(p, 'w').write('{}')\nEOF",
                   f"python3 -c \"from pathlib import Path; Path('{state}/sends/window.json').write_text('x')\""):
        assert "runs a script that writes" in guards.check("Bash", {"command": writes}, CONFIG, cwd=str(tmp_path)), writes


def test_messages_sends_are_their_own_channel_not_email():
    """2026-10-20: the iMessage tools carry a `to` field, so they fell through to the email channel, and an email
    send window would have covered them."""
    for tool in ("imessage_send", "messages_send"):
        assert sends.channel(tool, {"to": "+15551234567", "text": "On my way."}) == "messages"


# --- a shared document and a line that fits only some channels (reported 2026-10-27) ----------------------------

@pytest.mark.parametrize("tool", ["mcp__ws__modify_doc_text", "mcp__ws__batch_update_doc", "mcp__ws__insert_doc_elements",
                                  "mcp__ws__find_and_replace_doc", "mcp__ws__modify_sheet_values",
                                  "mcp__ws__batch_update_presentation", "mcp__ws__update_drive_file"])
def test_an_edit_to_a_document_others_read_waits_for_the_code(tool):
    """An agent added a line to an agenda seven colleagues read, with no code: an edit there is published in the
    principal's name. Its line breaks are the document's own, so the paragraph rule does not apply."""
    call = {"document_id": "doc-1", "text": "Agenda\nItem one\nItem two"}
    assert sends.says(tool, {}) and sends.channel(tool, call) == "docs"
    assert "approval" in guards.check(tool, call, CONFIG)
    assert not sends.says("mcp__ws__get_doc_content", {}) and not sends.says("mcp__ws__create_doc", {})


def test_a_register_rule_can_hold_on_some_channels_only(tmp_path):
    """The principal, 2026-10-27: the line saying he has not reviewed the details only makes sense for low-stakes
    things like scheduling; it had gone out on three Jira answers."""
    rule = {"name": "not-reviewed-on-work-items", "pattern": "hasn't reviewed the details yet",
            "channels": ["jira", "bitbucket"], "why": "that line is for low-stakes logistics such as scheduling"}
    config = {**CONFIG, "forbidden_phrases": [rule]}
    refused = guards.check("mcp__85ff__addCommentToJiraIssue", {"issueIdOrKey": "AB-1", "commentBody": SIGNED}, config)
    assert "low-stakes logistics" in refused
    assert "low-stakes" in guards.check("Bash", {"command": f'bkt pr comment 5 -m "{SIGNED}"'}, config, cwd=str(tmp_path))
    slack = guards.check("mcp__13d2__slack_send_message", {"channel_id": "C1", "message": SIGNED}, config)
    assert "low-stakes" not in slack and "approval" in slack


def test_a_change_to_an_events_time_or_a_delete_asks_for_the_occurrence_preview():
    """2026-10-27: a series moved to a new hour revived a meeting canceled at the old hour; the approval request had
    listed only the next occurrences. Now it asks for every occurrence from today, canceled and moved ones included."""
    config = {**CONFIG, "send_tools": ["mcp__*__delete_event"]}
    peer = {"event_id": "e1", "attendees": ["peer@example.test"], "send_updates": "all"}
    move = guards.check("mcp__ws__manage_event", {**peer, "action": "update", "start_time": "2026-10-27T14:00:00-04:00"}, config)
    assert "occurrences from today through the next three" in move and "this and following" in move
    note = guards.check("mcp__ws__manage_event", {**peer, "action": "update", "description": "Agenda attached"}, config)
    assert "approval" in note and "occurrences" not in note
    assert "occurrences from today" in guards.check("mcp__ws__delete_event", {"event_id": "e1"}, config)
