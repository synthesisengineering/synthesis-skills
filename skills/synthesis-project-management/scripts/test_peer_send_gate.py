"""The peer send gate: every direct lane needs a receipt, a live target, and a named sender."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import coordination as ENGINE  # noqa: E402
import peer_addressing as PA  # noqa: E402
import peer_send_gate as GATE  # noqa: E402

SENDER_SID = "11111111-1111-4111-8111-111111111111"
TARGET_SID = "33333333-3333-4333-8333-333333333333"
SENDER_ENV = {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": SENDER_SID, "CLAUDE_CODE_HOST_SESSION_ID": "local_sender", "CLAUDE_PID": "1"}
TARGET_ENV = {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": TARGET_SID, "CLAUDE_CODE_HOST_SESSION_ID": "local_target", "CLAUDE_PID": "2"}


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    for name in ("SYNTHESIS_CLIENT_SESSION_REF", "CLAUDE_CODE_HOST_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CLAUDE_PID", "CLAUDECODE", "SYNTHESIS_PEER_REGISTRY"):
        monkeypatch.delenv(name, raising=False)


def args(board: Path, **values):
    return type("Args", (), {"board": board, **values})()


def claim(board: Path, project: str, env: dict, monkeypatch, *, machine: str = "m1", agent: str = "Claude Code"):
    for key in ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_HOST_SESSION_ID", "CLAUDE_PID", "SYNTHESIS_CLIENT_SESSION_REF"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    request = args(board, id=None, agent=agent, machine=machine, project=project, mode="interactive", goal=f"goal-{project}", workspace=[f"/tmp/wt-{project} @ feature/{project}"], area=[f"repo-{project}/**"], context_role="owner")
    assert ENGINE.command_claim(request) == 0
    return [row for row in ENGINE.rows(board.read_text(encoding="utf-8")) if row.project == project][0]


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Sender (this shell) and target seats on one board, target alive in the registry."""
    board = tmp_path / "board.md"
    target = claim(board, "project-t", TARGET_ENV, monkeypatch)
    sender = claim(board, "project-s", SENDER_ENV, monkeypatch)
    registry = tmp_path / "registry"
    registry.mkdir()
    entry = {"pid": os.getpid(), "sessionId": TARGET_SID, "cwd": "/tmp/t", "messagingSocketPath": "/tmp/cc-socks/777.sock", "name": "peer-4a"}
    (registry / f"{os.getpid()}.json").write_text(json.dumps(entry), encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    return type("World", (), {"board": board, "sender": sender, "target": target, "registry": registry, "home": home, "tmp": tmp_path})()


def resolve(world, selector: str | None = None):
    request = args(world.board, to=selector or world.target.compact_id, role=None, include_released=False, stale_after_minutes=240, json=False, no_receipt=False, registry=world.registry, local_machine="m1")
    assert ENGINE.command_resolve(request) == 0


def payload(tool: str, tool_input: dict, *, session_id: str = SENDER_SID, transcript: str | None = None) -> dict:
    data = {"session_id": session_id, "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input, "cwd": "/tmp"}
    if transcript:
        data["transcript_path"] = transcript
    return data


def evaluate(world, data: dict, env: dict | None = None) -> GATE.Decision:
    return GATE.evaluate(data, board=world.board, registry=world.registry, environ=env or SENDER_ENV, home=world.home)


def body(world, text: str = "please review the handoff") -> str:
    return f"from {world.sender.compact_id} (project-s): {text}"


# --- classification -------------------------------------------------------------------------

def test_non_peer_tools_and_in_process_targets_pass_without_a_board(tmp_path) -> None:
    missing = tmp_path / "nope.md"
    for tool, tool_input in (("Read", {"file_path": "/x"}), ("SendMessage", {"to": "main", "message": "x"}), ("SendMessage", {"to": "acb566644f52b0a44", "message": "x"}), ("Bash", {"command": "git status"})):
        decision = GATE.evaluate(payload(tool, tool_input), board=missing, registry=tmp_path, environ=SENDER_ENV, home=tmp_path)
        assert decision.allow and not decision.logged, (tool, decision)


def test_named_teammates_pass_when_a_team_registers_them(tmp_path) -> None:
    team = tmp_path / ".claude" / "teams" / "alpha"
    team.mkdir(parents=True)
    (team / "config.json").write_text(json.dumps({"members": [{"name": "researcher"}]}), encoding="utf-8")
    decision = GATE.evaluate(payload("SendMessage", {"to": "researcher", "message": "go"}), board=tmp_path / "nope.md", registry=tmp_path, environ=SENDER_ENV, home=tmp_path)
    assert decision.allow and decision.lane == "in-process"


def test_display_names_and_refs_are_refused_as_addresses(world) -> None:
    for to in ("peer-4a", "peer-4a [902d19]", "[902d19]", "example-operations"):
        decision = evaluate(world, payload("SendMessage", {"to": to, "message": body(world)}))
        assert not decision.allow, to
        assert "display name" in decision.reason and "uds:" in decision.reason


# --- harness lane ---------------------------------------------------------------------------

def test_socket_address_needs_a_receipt_then_passes(world) -> None:
    data = payload("SendMessage", {"to": "uds:/tmp/cc-socks/777.sock", "message": body(world)})
    refused = evaluate(world, data)
    assert not refused.allow and "no delivery receipt" in refused.reason and "resolve --to" in refused.reason
    resolve(world)
    allowed = evaluate(world, data)
    assert allowed.allow, allowed.reason
    assert allowed.lane == "harness" and allowed.target_uuid == world.target.session_uuid


def test_socket_that_no_longer_maps_to_the_resolved_session_is_refused(world) -> None:
    resolve(world)
    for path in world.registry.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["sessionId"] = "someone-else"
        path.write_text(json.dumps(data), encoding="utf-8")
    decision = evaluate(world, payload("SendMessage", {"to": "uds:/tmp/cc-socks/777.sock", "message": body(world)}))
    assert not decision.allow and "no longer maps" in decision.reason


def test_a_receipt_for_one_socket_does_not_admit_another(world) -> None:
    resolve(world)
    decision = evaluate(world, payload("SendMessage", {"to": "uds:/tmp/cc-socks/778.sock", "message": body(world)}))
    assert not decision.allow and "no delivery receipt" in decision.reason


def test_reply_may_copy_the_from_address_of_a_received_message(world) -> None:
    transcript = world.tmp / "transcript.jsonl"
    transcript.write_text(json.dumps({"type": "user", "message": {"content": '<cross-session-message from="uds:/tmp/cc-socks/777.sock" from-name="peer-4a">hi</cross-session-message>'}}) + "\n", encoding="utf-8")
    decision = evaluate(world, payload("SendMessage", {"to": "uds:/tmp/cc-socks/777.sock", "message": body(world, "got it")}, transcript=str(transcript)))
    assert decision.allow and "reply" in decision.reason
    other = evaluate(world, payload("SendMessage", {"to": "uds:/tmp/cc-socks/999.sock", "message": body(world, "got it")}, transcript=str(transcript)))
    assert not other.allow


def test_idle_subscription_without_text_needs_only_the_receipt(world) -> None:
    resolve(world)
    decision = evaluate(world, payload("SendMessage", {"to": "uds:/tmp/cc-socks/777.sock", "notify_when_idle": True}))
    assert decision.allow


# --- ccd lane -------------------------------------------------------------------------------

def test_ccd_session_id_needs_a_matching_receipt(world) -> None:
    data = payload("mcp__ccd_session_mgmt__send_message", {"session_id": "local_target", "message": body(world)})
    assert not evaluate(world, data).allow
    resolve(world, "project-t")
    decision = evaluate(world, data)
    assert decision.allow and decision.lane == "ccd"
    wrong = evaluate(world, payload("mcp__ccd_session_mgmt__send_message", {"session_id": "local_other", "message": body(world)}))
    assert not wrong.allow


def test_released_target_is_refused_even_with_a_receipt(world) -> None:
    resolve(world)
    assert ENGINE.command_release(args(world.board, id=world.target.compact_id)) == 0
    decision = evaluate(world, payload("mcp__ccd_session_mgmt__send_message", {"session_id": "local_target", "message": body(world)}))
    assert not decision.allow and "no longer an active board row" in decision.reason


# --- sender and body rules ------------------------------------------------------------------

def test_message_must_carry_the_senders_board_id(world) -> None:
    resolve(world)
    decision = evaluate(world, payload("mcp__ccd_session_mgmt__send_message", {"session_id": "local_target", "message": "please review"}))
    assert not decision.allow and f"from {world.sender.compact_id}" in decision.reason


def test_sender_without_a_seat_is_refused(world) -> None:
    resolve(world)
    stranger = {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "44444444-4444-4444-8444-444444444444"}
    decision = GATE.evaluate(payload("mcp__ccd_session_mgmt__send_message", {"session_id": "local_target", "message": body(world)}, session_id=stranger["CLAUDE_CODE_SESSION_ID"]), board=world.board, registry=world.registry, environ=stranger, home=world.home)
    assert not decision.allow and "claim first" in decision.reason


def test_missing_session_id_and_unreadable_board_fail_closed(world, tmp_path) -> None:
    data = payload("mcp__ccd_session_mgmt__send_message", {"session_id": "local_target", "message": body(world)})
    data.pop("session_id")
    assert not evaluate(world, data).allow
    decision = GATE.evaluate(payload("mcp__ccd_session_mgmt__send_message", {"session_id": "local_target", "message": body(world)}), board=tmp_path / "absent.md", registry=world.registry, environ=SENDER_ENV, home=world.home)
    assert not decision.allow and "unreadable" in decision.reason


def test_same_text_to_a_second_session_is_a_broadcast(world, monkeypatch) -> None:
    resolve(world)
    first = payload("mcp__ccd_session_mgmt__send_message", {"session_id": "local_target", "message": body(world, "the release shipped")})
    decision = evaluate(world, first)
    assert decision.allow
    GATE.record(world.board, first, decision, SENDER_ENV)
    third = claim(world.board, "project-u", {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "55555555-5555-4555-8555-555555555555", "CLAUDE_CODE_HOST_SESSION_ID": "local_third"}, monkeypatch, machine="m1")
    for key, value in SENDER_ENV.items():
        monkeypatch.setenv(key, value)
    resolve(world, third.compact_id)
    second = evaluate(world, payload("mcp__ccd_session_mgmt__send_message", {"session_id": "local_third", "message": body(world, "the release shipped")}))
    assert not second.allow and "broadcast" in second.reason
    different = evaluate(world, payload("mcp__ccd_session_mgmt__send_message", {"session_id": "local_third", "message": body(world, "a different note for you")}))
    assert different.allow


# --- codex lane -----------------------------------------------------------------------------

def test_codex_queue_needs_a_receipt_for_that_thread(world, monkeypatch) -> None:
    codex = claim(world.board, "project-x", {"SYNTHESIS_CLIENT_SESSION_REF": "codex:0a0a0a0a-1b1b-4c1c-8d1d-2e2e2e2e2e2e"}, monkeypatch, agent="OpenAI Codex")
    monkeypatch.delenv("SYNTHESIS_CLIENT_SESSION_REF")
    for key, value in SENDER_ENV.items():
        monkeypatch.setenv(key, value)
    command = f'codex queue --thread 0a0a0a0a-1b1b-4c1c-8d1d-2e2e2e2e2e2e --message "{body(world, "please pick this up")}"'
    refused = evaluate(world, payload("Bash", {"command": command}))
    assert not refused.allow and refused.lane == "codex"
    resolve(world, codex.compact_id)
    allowed = evaluate(world, payload("Bash", {"command": command}))
    assert allowed.allow, allowed.reason
    assert evaluate(world, payload("exec_command", {"cmd": "codex queue --message x"})).allow is False


# --- process contract -----------------------------------------------------------------------

def test_gate_process_blocks_with_exit_2_and_admits_with_exit_0(world) -> None:
    script = SCRIPTS_DIR / "peer_send_gate.py"
    env = {**os.environ, **SENDER_ENV, "SYNTHESIS_PEER_REGISTRY": str(world.registry)}
    for key in ("SYNTHESIS_CLIENT_SESSION_REF",):
        env.pop(key, None)
    data = payload("SendMessage", {"to": "peer-4a [902d19]", "message": body(world)})
    blocked = subprocess.run([sys.executable, str(script), "--board", str(world.board), "--gate"], input=json.dumps(data), capture_output=True, text=True, env=env)
    assert blocked.returncode == 2 and "peer-send-gate BLOCKED" in blocked.stderr
    resolve(world)
    data = payload("SendMessage", {"to": "uds:/tmp/cc-socks/777.sock", "message": body(world)})
    admitted = subprocess.run([sys.executable, str(script), "--board", str(world.board), "--gate"], input=json.dumps(data), capture_output=True, text=True, env=env)
    assert admitted.returncode == 0, admitted.stderr
    log = [json.loads(line) for line in PA.send_log_path(world.board).read_text(encoding="utf-8").splitlines()]
    assert [entry["decision"] for entry in log] == ["deny", "allow"]
    garbage = subprocess.run([sys.executable, str(script), "--board", str(world.board), "--gate"], input="not json", capture_output=True, text=True, env=env)
    assert garbage.returncode == 2


def test_doctor_reports_seat_and_stores(world, capsys) -> None:
    assert GATE.doctor(world.board, SENDER_ENV) == 0
    out = capsys.readouterr().out
    assert "PASS peer-send-gate.board" in out and "PASS peer-send-gate.seat" in out
    assert GATE.doctor(world.board, {}) == 1
    assert "FAIL peer-send-gate.identity" in capsys.readouterr().out
