"""R3.6: calendar and mail calls act as the account configured for the session's workspace."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from synthesis import guards, paths

ROOT = Path(__file__).resolve().parents[1]
INCIDENT = json.loads((ROOT / "tests" / "fixtures" / "incidents.json").read_text(encoding="utf-8"))["client_calendar_invite"]
CLIENT, PERSONAL, DEFAULT = "me@clientco.example", "me@personal.example", "me@personal.example"


@pytest.fixture
def ws(tmp_path):
    """A client workspace, a personal workspace, and a directory in neither."""
    dirs = {name: tmp_path / name for name in ("clientco", "personal", "elsewhere")}
    for d in dirs.values():
        (d / "projects" / "kickoff").mkdir(parents=True)
    config = {"account_routing": {"default_account": DEFAULT, "workspaces": {
        str(dirs["clientco"]): {"account": CLIENT, "label": "ClientCo", "aliases": ["ClientCo Exchange"]},
        str(dirs["personal"]): {"account": PERSONAL}}}}
    return dirs, config


def _check(tool, tool_input, config, cwd):
    return guards.check(tool, tool_input, config, cwd=str(cwd))


def test_the_incident_shape_is_refused_and_the_reason_names_the_right_account(ws):
    dirs, config = ws
    cwd = INCIDENT["cwd"].replace("{client_ws}", str(dirs["clientco"]))
    reason = _check(INCIDENT["tool"], INCIDENT["input"], config, cwd)
    assert CLIENT in reason and "ClientCo" in reason and DEFAULT in reason


def test_an_account_less_call_is_refused_even_with_no_default_account(ws):
    dirs, config = ws
    del config["account_routing"]["default_account"]
    reason = _check("mcp__gcal__create_event", {"summary": "x"}, config, dirs["clientco"])
    assert "names no account" in reason and CLIENT in reason


def test_the_workspace_account_is_allowed_and_another_account_is_refused(ws):
    dirs, config = ws
    call = {"action": "create", "summary": "x", "user_google_email": CLIENT.upper()}
    assert _check("mcp__workspace-mcp__manage_event", call, config, dirs["clientco"]) is None
    reason = _check("mcp__workspace-mcp__manage_event", {**call, "user_google_email": PERSONAL}, config, dirs["clientco"])
    assert f"would act as {PERSONAL}" in reason and f"account is {CLIENT}" in reason


def test_the_personal_workspace_is_routed_too(ws):
    dirs, config = ws
    assert _check("mcp__gcal__create_event", {"summary": "x"}, config, dirs["personal"]) is None  # default account
    reason = _check("mcp__workspace-mcp__manage_event", {"action": "create", "user_google_email": CLIENT}, config, dirs["personal"])
    assert PERSONAL in reason


def test_outside_every_workspace_nothing_is_routed(ws):
    dirs, config = ws
    assert _check("mcp__gcal__create_event", {"summary": "x"}, config, dirs["elsewhere"]) is None


def test_reads_are_never_routed(ws):
    dirs, config = ws
    for tool in ("mcp__gcal__list_events", "mcp__gcal__get_event", "mcp__gmail__search_threads", "mcp__gmail__get_thread"):
        assert _check(tool, {"query": "x"}, config, dirs["clientco"]) is None


def test_the_deepest_configured_workspace_wins(ws, tmp_path):
    dirs, config = ws
    nested = dirs["clientco"] / "partner"
    nested.mkdir()
    config["account_routing"]["workspaces"][str(nested)] = {"account": "me@partner.example"}
    call = {"action": "create", "user_google_email": "me@partner.example"}
    assert _check("mcp__workspace-mcp__manage_event", call, config, nested) is None
    assert _check("mcp__workspace-mcp__manage_event", call, config, dirs["clientco"]) is not None


def test_a_symlinked_or_tilde_workspace_root_still_matches(ws, tmp_path, monkeypatch):
    dirs, config = ws
    link = tmp_path / "link-to-client"
    link.symlink_to(dirs["clientco"])
    config["account_routing"]["workspaces"] = {str(link): {"account": CLIENT}}
    assert _check("mcp__gcal__create_event", {"summary": "x"}, config, dirs["clientco"]) is not None
    monkeypatch.setenv("HOME", str(tmp_path))
    config["account_routing"]["workspaces"] = {"~/clientco": {"account": CLIENT}}
    assert _check("mcp__gcal__create_event", {"summary": "x"}, config, dirs["clientco"] / "projects") is not None


def test_an_aliased_account_name_and_a_display_address_are_accepted(ws):
    dirs, config = ws
    config["message_format"] = {"plain_email_tools": ["mcp__apple-mail__*"]}  # this transport sends plain text only
    mail = {"to": "a@clientco.example", "subject": "s", "body": "b"}
    assert "approval" in _check("mcp__apple-mail__send_email", {**mail, "from_account": "ClientCo Exchange"}, config, dirs["clientco"])
    assert "approval" in _check("mcp__apple-mail__send_email", {**mail, "from_account": f"Me <{CLIENT}>"}, config, dirs["clientco"])
    assert "would act as" in _check("mcp__apple-mail__send_email", {**mail, "from_account": "iCloud"}, config, dirs["clientco"])


def test_apple_calendar_is_routed_by_calendar_name(ws):
    dirs, config = ws
    event = {"summary": "x", "start_date": "today at 2 PM", "end_date": "today at 3 PM"}
    assert _check("mcp__apple-calendar__create_event", {**event, "calendar": "ClientCo Exchange"}, config, dirs["clientco"]) is None
    assert _check("mcp__apple-calendar__create_event", {**event, "calendar": "Home"}, config, dirs["clientco"]) is not None


def test_a_wrong_account_send_is_refused_before_any_approval_is_filed(ws):
    dirs, config = ws
    reason = _check("mcp__0a1b2c3d__send_message", {"to": ["a@clientco.example"], "body": "hi"}, config, dirs["clientco"])
    assert CLIENT in reason
    assert not (paths.state() / "approval-requests").exists()


@pytest.mark.parametrize("tool,tool_input", [
    ("mcp__ccd_session_mgmt__send_message", {"session_id": "local_1", "message": "hi"}),  # session to session
    ("mcp__slack__slack_send_message", {"channel_id": "C1", "message": "hi"}),          # the send guard's alone
    ("mcp__slack__slack_send_message_draft", {"channel_id": "C1", "message": "hi"}),
])
def test_messages_with_no_account_boundary_are_not_routed(ws, tool, tool_input):
    dirs, config = ws
    assert not guards.routed(tool, tool_input)
    reason = _check(tool, tool_input, config, dirs["clientco"])
    assert reason is None or "approval" in reason


def test_an_addressed_send_message_needs_send_approval_whatever_its_server_is_called(ws):
    dirs, config = ws
    reason = _check("mcp__0a1b2c3d__send_message", {"to": ["friend@example.com"], "htmlBody": "<p>hi</p>"}, config, dirs["personal"])
    assert "approval" in reason


@pytest.mark.parametrize("routing", [{"workspaces": ["not", "a", "map"]}, "not a map",
                                     {"workspaces": {"/": {"label": "no account"}}}])
def test_malformed_routing_config_fails_closed(ws, routing):
    dirs, config = ws
    assert _check("mcp__gcal__create_event", {"summary": "x"}, {"account_routing": routing}, dirs["clientco"]) is not None


def test_no_routing_config_routes_nothing(ws):
    dirs, _ = ws
    assert _check("mcp__gcal__create_event", {"summary": "x"}, {}, dirs["clientco"]) is None


def test_routed_calls_fail_closed_when_the_config_is_unreadable():
    assert guards.guarded("mcp__gcal__create_event")
    assert guards.guarded("mcp__0a1b2c3d__send_message", {"to": ["a@example.com"]})
    assert not guards.guarded("mcp__ccd_session_mgmt__send_message", {"session_id": "x"})
    assert not guards.guarded("mcp__gcal__list_events")


def test_the_hook_routes_by_the_directory_it_runs_in(ws, isolated_home):
    dirs, config = ws
    isolated_home.mkdir(parents=True, exist_ok=True)
    (isolated_home / "config.json").write_text(json.dumps(config), encoding="utf-8")
    env = {**os.environ, "SYNTHESIS_HOME": str(isolated_home)}
    payload = json.dumps({"tool_name": INCIDENT["tool"], "tool_input": INCIDENT["input"]})
    for cwd, denied in ((dirs["clientco"], True), (dirs["elsewhere"], False)):
        out = subprocess.run([sys.executable, "-S", str(ROOT / "synthesis" / "hook.py"), "pre-tool-use"],
                             input=payload, capture_output=True, text=True, env=env, cwd=cwd)
        decision = json.loads(out.stdout)["hookSpecificOutput"]["permissionDecisionReason"] if out.stdout.strip() else ""
        assert (CLIENT in decision) is denied
