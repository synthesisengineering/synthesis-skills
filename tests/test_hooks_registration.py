"""R8: hooks fire only where they protect something, and every send tool is matched.

2026-10-14: the matcher listed send-shaped connector names, so `createJiraIssue` and every other tool the guard
recognizes by what it does never reached it, and Edit and Write (which could write a send window by hand) were
never checked. Every connector tool and every file-edit tool now reaches the guard; built-in reads do not."""

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from synthesis import doctor, guards

ROOT = Path(__file__).resolve().parents[1]
HOOKS = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]
MUSE_HOOKS = json.loads((ROOT / ".muse-plugin" / "plugin.json").read_text())["capabilities"]["hooks"]


def test_only_the_four_needed_events_are_registered():
    assert set(HOOKS) == {"SessionStart", "UserPromptSubmit", "PreToolUse", "Stop"}


@pytest.mark.parametrize("tool", sorted(guards.SHELL_TOOLS) + ["mcp__slack__slack_send_message",
                                                                 "mcp__workspace-mcp__draft_gmail_message",
                                                                 "mcp__d01c6c5a__reply", "mcp__apple-mail__send_email",
                                                                 "mcp__apple-calendar__create_event",
                                                                 "mcp__workspace-mcp__manage_event",
                                                                 "mcp__3cd455d4__respond_to_event",
                                                                 "mcp__workspace-mcp__manage_out_of_office",
                                                                 "mcp__7512aea3__share_file",
                                                                 "mcp__workspace-mcp__set_drive_file_permissions",
                                                                 "mcp__85ff0050-6527__createJiraIssue",
                                                                 "mcp__atlassian__addCommentToJiraIssue",
                                                                 "mcp__github__create_pull_request",
                                                                 "mcp__c3621cad__notion-create-comment",
                                                                 "mcp__workspace-mcp__manage_document_comment",
                                                                 "mcp__computer-use__computer_batch",
                                                                 "mcp__computer-use__app_click",
                                                                 "mcp__claude-in-chrome__browser_batch"]
                         + sorted(guards.FILE_TOOLS))
def test_guarded_tools_reach_the_hook(tool):
    assert re.fullmatch(HOOKS["PreToolUse"][0]["matcher"], tool)


@pytest.mark.parametrize("tool", ["Read", "Grep", "Glob", "LS", "WebFetch", "WebSearch", "TodoWrite"])
def test_built_in_reads_never_start_the_hook(tool):
    assert not re.fullmatch(HOOKS["PreToolUse"][0]["matcher"], tool)


# ---- a guard that cannot answer (5.21.0) ------------------------------------------------------------------------------
# Claude Code lets a call through when its PreToolUse hook times out, crashes, prints output it cannot read or cannot
# start (the stable hook missing), unless the handler sets "onFailure": "block", which it honors from 2.1.295. Each
# harness reads its hooks differently, so what each reads was probed in homes of their own on 2026-11-14 (Claude Code
# 2.1.316 and 2.1.293, Codex 0.167.0-alpha.4.1, Muse 1.4.20).

def test_in_claude_code_a_guard_that_cannot_answer_holds_the_call():
    handlers = [handler for group in HOOKS["PreToolUse"] for handler in group["hooks"]]
    assert handlers and all(handler.get("onFailure") == "block" for handler in handlers)


def test_no_other_event_blocks_on_a_hook_failure():
    """Holding a person's prompt or a session's start on a hook failure costs more than it protects, and Claude Code
    ignores the setting on Stop."""
    assert [event for event, groups in HOOKS.items() if event != "PreToolUse"
            for group in groups for handler in group["hooks"] if "onFailure" in handler] == []


def test_codex_reads_every_hook_of_the_shared_file_and_hashes_the_guard_as_before():
    """Codex reads all of a hooks.json or none of it. With the field it read all four and listed the guard's hash as
    without it (its handler has no deny_unknown_fields), so an approval given before 5.21.0 still holds."""
    group = HOOKS["PreToolUse"][0]
    guard = group["hooks"][0]
    assert guard.get("onFailure") == "block" and doctor.codex_hooks_problem({"hooks": HOOKS}) == ""
    without = {key: value for key, value in guard.items() if key != "onFailure"}
    assert doctor.codex_hook_hash("PreToolUse", group["matcher"], guard) == doctor.codex_hook_hash("PreToolUse", group["matcher"], without)


def test_muse_reads_its_own_manifest_whose_hooks_carry_only_fields_it_accepts():
    """Muse reads .muse-plugin/plugin.json alone (it ignores the other manifests and hooks/hooks.json), and refuses the
    whole plugin for a hook field it does not support: `onFailure` there left it no hooks at all. It has no such
    setting; a hook that is missing, crashes or times out lets the call through there."""
    assert len(MUSE_HOOKS) == 4 and all(set(hook) <= {"id", "event", "command", "timeoutMs", "statusMessage"} for hook in MUSE_HOOKS)


@pytest.mark.parametrize("reference", ["skills/synthesis-message-guard/references/config.md",
                                       "skills/synthesis-agent-guardrails/references/config.md", "docs/runtime-integration.md"])
def test_the_references_say_what_holds_when_the_guard_cannot_answer_in_each_harness(reference):
    text = " ".join((ROOT / reference).read_text(encoding="utf-8").split())
    assert all(said in text for said in ('"onFailure": "block"', "2.1.295", "times out", "Codex", "Muse")), reference


# ---- a guard that cannot start or crashes, in Codex and Muse too (5.21.0) ------------------------------------------
# Codex and Muse have no "onFailure", and let a call through when the hook's command exits with an error; both block
# on exit 2 with a reason (Muse's hook test, Codex's source). So the guard's own command turns any failure of the
# stable hook into exit 2 with one line of reason, and a deny the hook gives, which exits 0 with its JSON, keeps its own.

STAND_INS = {"missing": None,
             "crashes": "#!/bin/sh\necho 'Traceback (most recent call last): a stand-in that crashes' >&2\nexit 1\n",
             "denies": "#!/bin/sh\ncat >/dev/null\nprintf '%s' '{\"hookSpecificOutput\": {\"hookEventName\": \"PreToolUse\", "
                       "\"permissionDecision\": \"deny\", \"permissionDecisionReason\": \"held by the guard\"}}'\n",
             "allows": "#!/bin/sh\ncat >/dev/null\nexit 0\n"}
GUARDS = {"the plugin's hooks.json": ["/bin/sh", "-c", HOOKS["PreToolUse"][0]["hooks"][0]["command"]],
          "Muse's pre-tool-use.sh": ["/bin/sh", str(ROOT / ".muse-plugin" / "hooks" / "pre-tool-use.sh")],
          "the user-level declaration": ["/bin/sh", "-c", doctor.codex_user_declaration({"hooks": HOOKS})["PreToolUse"][0]["hooks"][0]["command"]]}


def run_guard(home, argv, stand_in):
    """The guard's command as a harness runs it, the call's JSON on its stdin, with a stand-in stable hook under a HOME
    of its own (None: no hook at all)."""
    hook = home / ".synthesis" / "v5" / "bin" / "synthesis-hook"
    if stand_in is not None:
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text(stand_in)
        hook.chmod(0o755)
    return subprocess.run(argv, input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "echo hi"}}),
                          capture_output=True, text=True, timeout=20, env={**os.environ, "HOME": str(home)})


@pytest.mark.parametrize("where", GUARDS)
def test_a_guard_that_cannot_start_or_crashes_holds_the_call_with_one_line_of_reason(tmp_path, where):
    for kind in ("missing", "crashes"):
        done = run_guard(tmp_path / kind, GUARDS[where], STAND_INS[kind])
        assert done.returncode == 2 and done.stdout == "", (where, kind, done.returncode)
        assert done.stderr.strip().splitlines()[-1].startswith("synthesis guard could not run"), (where, kind)


@pytest.mark.parametrize("where", GUARDS)
def test_a_deny_the_guard_gives_keeps_its_own_reason_and_exit_code_and_an_allow_stays_one(tmp_path, where):
    denied = run_guard(tmp_path / "denies", GUARDS[where], STAND_INS["denies"])
    assert denied.returncode == 0 and denied.stderr == ""
    assert json.loads(denied.stdout)["hookSpecificOutput"]["permissionDecisionReason"] == "held by the guard"
    allowed = run_guard(tmp_path / "allows", GUARDS[where], STAND_INS["allows"])
    assert (allowed.returncode, allowed.stdout, allowed.stderr) == (0, "", "")


def test_only_the_guard_holds_on_a_failure_and_every_hook_still_calls_the_stable_hook():
    commands = [(e, h["command"]) for e, _, h in doctor.hooks_json_entries({"hooks": HOOKS})]
    assert [e for e, c in commands if "exit 2" in c] == ["PreToolUse"]
    assert doctor.check_hooks_wired("codex", commands).status == "ok"
    declared = doctor.codex_user_declaration({"hooks": HOOKS})
    assert all(doctor.calls_stable_hook(e, h["command"]) for e, groups in declared.items() for g in groups for h in g["hooks"])

