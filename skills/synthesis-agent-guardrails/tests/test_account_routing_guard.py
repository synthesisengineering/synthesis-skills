"""Regressions for the cross-account artifact gate.

The incident this closes: a calendar invitation to two client colleagues was created
through the personal-account connector and dispatched with a personal address as
organizer. An invitation cannot be unsent, so the control has to sit before the call
rather than after it.

The second regression here is the guard's OWN first defect. Its first draft matched
tool-name suffixes, which made `slack_send_message` match `send_message`; every Slack
send from a client workspace would have been blocked, including the one sanctioned
agent-send lane, which carries no Google account parameter and never will. A guard that
blocks the approved path trains its own bypass, so the exact-terminal-name behavior is
pinned by tests.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent.parent / "guards" / "account_routing_guard.py"
SPEC = importlib.util.spec_from_file_location("account_routing_guard", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

CFG = {
    "workspaces": {
        "/w/client": {"account": "person@client.example.com", "label": "Client"},
        "/w/client/nested": {"account": "person@nested.example.com", "label": "Nested"},
    }
}
INSIDE = "/w/client/repo"


def _allow(tool: str, tool_input: dict, cwd: str = INSIDE) -> bool:
    allow, _ = MODULE.evaluate(tool, tool_input, cwd, CFG)
    return allow


def test_personal_connector_mutating_inside_client_workspace_blocks():
    assert not _allow("mcp__abc123__create_event", {"summary": "Sync"})


def test_account_bound_tool_with_right_account_allows():
    assert _allow(
        "mcp__example__manage_event",
        {"user_google_email": "person@client.example.com", "action": "create"},
    )


def test_account_bound_tool_with_wrong_account_blocks():
    assert not _allow(
        "mcp__example__manage_event",
        {"user_google_email": "person@personal.example.com", "action": "create"},
    )


def test_account_match_is_case_insensitive():
    assert _allow(
        "mcp__example__send_gmail_message",
        {"user_google_email": "Person@Client.Example.COM"},
    )


def test_read_only_calls_are_never_gated():
    for tool in ("list_events", "get_event", "search_events", "search_gmail_messages"):
        assert _allow(f"mcp__abc123__{tool}", {})


def test_outside_any_configured_workspace_allows():
    assert _allow("mcp__abc123__create_event", {"summary": "x"}, cwd="/w/personal")


def test_nested_workspace_wins_over_parent():
    """Longest-prefix match: the nested root's account governs, not its parent's."""
    assert _allow(
        "mcp__example__manage_event",
        {"user_google_email": "person@nested.example.com"},
        cwd="/w/client/nested/repo",
    )
    assert not _allow(
        "mcp__example__manage_event",
        {"user_google_email": "person@client.example.com"},
        cwd="/w/client/nested/repo",
    )


def test_slack_sends_are_not_this_guards_boundary():
    """The regression that would have broken the sanctioned agent-send lane.

    Slack tool names END WITH the Google terminal names this guard gates. Suffix
    matching swept them in; exact terminal-name matching must not.
    """
    for tool in (
        "slack_send_message",
        "slack_send_message_draft",
        "slack_schedule_message",
    ):
        assert _allow(f"mcp__slack__{tool}", {"channel": "C1"}), tool


def test_personal_gmail_mutations_inside_client_workspace_block():
    for tool in ("send_message", "create_draft", "reply", "forward", "trash_message"):
        assert not _allow(f"mcp__gmail__{tool}", {"to": "friend@example.com"}), tool


def test_session_to_session_messaging_is_not_this_guards_boundary():
    """The guard's second false positive, caught on its first live call.

    `send_message` is Gmail on one connector, Google Chat on another, and agent-to-agent
    session messaging on a third. Only the first two cross an account boundary, so the
    bare name is gated on payload shape rather than unconditionally.
    """
    assert _allow(
        "mcp__agent_messaging__send_message",
        {"session_id": "local_x", "message": "hi"},
    )


def test_google_chat_send_is_still_gated_by_payload_shape():
    assert not _allow("mcp__example__send_message", {"space_id": "spaces/x"})
    assert _allow(
        "mcp__example__send_message",
        {"space_id": "spaces/x", "user_google_email": "person@client.example.com"},
    )


def test_terminal_name_strips_only_the_server_prefix():
    assert MODULE.terminal_name("mcp__srv__send_message") == "send_message"
    assert MODULE.terminal_name("send_message") == "send_message"
    assert MODULE.terminal_name("mcp__srv__slack_send_message") == "slack_send_message"


def test_workspace_without_an_account_fails_closed():
    broken = {"workspaces": {"/w/client": {"label": "Client"}}}
    try:
        MODULE.evaluate("mcp__abc__create_event", {}, INSIDE, broken)
    except RuntimeError:
        return
    raise AssertionError("a workspace with no configured account must fail closed")


def test_tool_hint_surfaces_in_the_block_message():
    hinted = {"workspaces": {"/w/client": {
        "account": "person@client.example.com", "label": "Client",
        "tool_hint": "calendar-mcp: manage_event",
    }}}
    allow, message = MODULE.evaluate("mcp__abc__create_event", {"summary": "x"}, INSIDE, hinted)
    assert not allow
    assert "(calendar-mcp: manage_event)" in message
    allow, message = MODULE.evaluate("mcp__abc__create_event", {"summary": "x"}, INSIDE, CFG)
    assert not allow
    assert "pass user_google_email=person@client.example.com.\n" in message


def _configured_env(tmp_path, cfg: dict) -> dict:
    config_file = tmp_path / "workspaces.json"
    config_file.write_text(json.dumps(cfg))
    env = dict(os.environ)
    env["ACCOUNT_ROUTING_CONFIG"] = str(config_file)
    return env


def _run(payload: dict, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )


def test_gate_exits_2_and_explains_on_a_blocked_call(tmp_path):
    result = _run(
        {
            "tool_name": "mcp__abc123__create_event",
            "tool_input": {"summary": "Sync"},
            "cwd": "/w/client/x",
        },
        _configured_env(tmp_path, CFG),
    )
    assert result.returncode == 2
    assert "BLOCKED" in result.stderr
    assert "person@client.example.com" in result.stderr


def test_gate_fails_closed_on_unreadable_payload(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="{not json",
        capture_output=True,
        text=True,
        env=_configured_env(tmp_path, CFG),
    )
    assert result.returncode == 2
    assert "FAILED CLOSED" in result.stderr


def test_gate_allows_when_no_workspaces_configured(tmp_path):
    env = dict(os.environ)
    env["ACCOUNT_ROUTING_CONFIG"] = str(tmp_path / "missing.json")
    result = _run(
        {
            "tool_name": "mcp__abc123__create_event",
            "tool_input": {"summary": "Sync"},
            "cwd": "/w/client/x",
        },
        env,
    )
    assert result.returncode == 0, result.stderr


def test_doctor_reports_healthy_and_exits_zero(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--doctor"],
        capture_output=True,
        text=True,
        env=_configured_env(tmp_path, CFG),
    )
    assert result.returncode == 0, result.stdout
    assert "HEALTHY" in result.stdout
    assert "FAIL" not in result.stdout


def test_doctor_reports_unhealthy_when_unconfigured(tmp_path):
    env = dict(os.environ)
    env["ACCOUNT_ROUTING_CONFIG"] = str(tmp_path / "missing.json")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--doctor"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 2
    assert "UNHEALTHY" in result.stdout
    assert "workspaces.json" in result.stdout
