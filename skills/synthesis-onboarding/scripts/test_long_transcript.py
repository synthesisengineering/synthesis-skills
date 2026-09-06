#!/usr/bin/env python3
"""LIFECYCLE-001: long native history remains valid without unbounded reads.

All files are generated in temporary homes. The transcript contents, receipt
registry and generation are real inputs to the production verifier; none of
its binding, digest, persistence or promotion operations is mocked.
"""

from __future__ import annotations

import json
import shutil
import sys
import tracemalloc
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
CONFORMANCE_SCRIPTS = SCRIPTS.parents[1] / "synthesis-agent-conformance" / "scripts"
for directory in (SCRIPTS, CONFORMANCE_SCRIPTS):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import live_receipt  # noqa: E402
import synthesis_cli  # noqa: E402
import system_contract  # noqa: E402
from test_system_contract import live_receipt as receipt_fixture, release_record  # noqa: E402


MIB = 1024 * 1024
HISTORICAL_LIMIT = 64 * MIB
PEAK_MEMORY_LIMIT = 16 * MIB


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    monkeypatch.delenv("SYNTHESIS_ACTIVE_DESCRIPTOR", raising=False)
    monkeypatch.delenv("SYNTHESIS_RESOLVED_BOOTSTRAP", raising=False)
    monkeypatch.delenv("SYNTHESIS_PUBLIC_SESSIONSTART_RECEIPT", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def _binding(client: str, session_id: str) -> dict:
    if client == "codex":
        return {
            "type": "session_meta",
            "payload": {"id": session_id, "cwd": "/workspace/example"},
        }
    return {"type": "user", "sessionId": session_id, "message": {"role": "user"}}


def _case(tmp_path: Path, client: str):
    state = system_contract.SystemState(tmp_path / "home")
    receipt = receipt_fixture(tmp_path, client)
    session_id = receipt["session_id"]
    if client == "codex":
        transcript = (
            state.home / ".codex" / "sessions" / "2030" / "01" / "02"
            / ("rollout-2030-01-02T03-04-05-" + session_id + ".jsonl")
        )
    else:
        transcript = state.home / ".claude" / "projects" / "-workspace-example" / (session_id + ".jsonl")
    transcript.parent.mkdir(parents=True)
    transcript.write_text(json.dumps(_binding(client, session_id)) + "\n", encoding="utf-8")
    receipt["transcript_path"] = str(transcript)
    root = Path(receipt["plugin_root"])
    desired = system_contract.default_desired_state("skills-only", [client], "stable")
    state.run_transaction(
        "setup", desired,
        lambda _tx: {
            "release": release_record(root),
            "source-provenance": {"status": "verified", "root": str(root)},
            "live-loaded": {"status": "restart-required"},
        },
    )
    receipt["recorded_at"] = datetime.now(timezone.utc).isoformat()
    return state, receipt, transcript


def _write_long_transcript(transcript: Path, client: str, session_id: str, shape: str) -> None:
    """Write actual JSONL bytes, including a native-shaped very large record."""
    block = "x" * (64 * 1024)
    with transcript.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(_binding(client, session_id)) + "\n")
        if shape == "many-records":
            record = (
                {"type": "event_msg", "payload": {"type": "agent_message", "message": block}}
                if client == "codex"
                else {"type": "assistant", "sessionId": session_id,
                      "message": {"role": "assistant", "content": [{"type": "text", "text": block}]}}
            )
            line = json.dumps(record) + "\n"
            for _ in range(1041):
                handle.write(line)
        else:
            if client == "codex":
                handle.write('{"type":"event_msg","payload":{"type":"agent_message","message":"')
            else:
                handle.write('{"type":"assistant","sessionId":' + json.dumps(session_id)
                             + ',"message":{"role":"assistant","content":[{"type":"text","text":"')
            for _ in range(1041):
                handle.write(block)
            handle.write('"}}\n' if client == "codex" else '"}]}}\n')
    assert transcript.stat().st_size > HISTORICAL_LIMIT


def _registry_event(tmp_path: Path, receipt: dict, *, registry: Path | None = None) -> tuple[Path, Path]:
    registry = registry if registry is not None else tmp_path / "registry"
    path = registry / receipt["client"] / receipt["session_id"] / (receipt["receipt_event_id"] + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Promotion is the real pending-at-hook path, not an invented direct proof.
    path.write_text(json.dumps(dict(receipt, transcript_bound_at_record=False)) + "\n", encoding="utf-8")
    return registry, path


@pytest.mark.parametrize("client", ["codex", "claude"])
@pytest.mark.parametrize("shape", ["many-records", "large-record"])
@pytest.mark.parametrize("route", ["direct", "promotion"])
def test_long_native_transcript_is_accepted_with_bounded_memory(tmp_path, client, shape, route):
    state, receipt, transcript = _case(tmp_path, client)
    _write_long_transcript(transcript, client, receipt["session_id"], shape)
    transcript_digest = system_contract.file_digest(transcript)
    desired_before = state.desired_path.read_bytes()
    registry, event_path = _registry_event(tmp_path, receipt)
    event_before = event_path.read_bytes()

    tracemalloc.start()
    try:
        if route == "direct":
            accepted = state.record_live_load(receipt=receipt)
        else:
            accepted = state.promote_live_receipts(
                binder=live_receipt.transcript_binds_session, registry_root=registry,
            )
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert accepted, "a genuine long conversation must attach to its matching generation"
    assert peak < PEAK_MEMORY_LIMIT, f"verification allocated {peak} bytes for a streamed transcript"
    live = state.read_observation()["transactions"][-1]["live-loaded"]
    assert live["status"] == "verified"
    recorded = live["receipts"][client]
    assert recorded["session_id"] == receipt["session_id"]
    assert recorded["receipt_event_id"] == receipt["receipt_event_id"]
    assert recorded["transcript_sha256"] == transcript_digest
    assert recorded["transcript_bound_at_promotion"] is (route == "promotion")
    assert system_contract.file_digest(transcript) == transcript_digest
    assert state.desired_path.read_bytes() == desired_before
    assert event_path.read_bytes() == event_before
    if route == "promotion":
        observation_before = state.observation_path.read_bytes()
        assert state.promote_live_receipts(
            binder=live_receipt.transcript_binds_session, registry_root=registry,
        ) == []
        assert state.observation_path.read_bytes() == observation_before


@pytest.mark.parametrize("client", ["codex", "claude"])
@pytest.mark.parametrize("shape", ["quoted-only", "conflicting", "wrong-client", "malformed"])
@pytest.mark.parametrize("route", ["direct", "promotion"])
def test_structured_identity_is_required_without_mutating_state(tmp_path, client, shape, route):
    state, receipt, transcript = _case(tmp_path, client)
    session_id = receipt["session_id"]
    if shape == "quoted-only":
        text = json.dumps({"type": "message", "text": "quoted session " + session_id}) + "\n"
    elif shape == "conflicting":
        text = json.dumps(_binding(client, session_id)) + "\n"
        text += json.dumps(_binding(client, str(uuid.uuid4()))) + "\n"
    elif shape == "wrong-client":
        text = json.dumps(_binding("claude" if client == "codex" else "codex", session_id)) + "\n"
    else:
        text = '{"sessionId": "' + session_id + '"\n'
    transcript.write_text(text, encoding="utf-8")
    registry, _ = _registry_event(tmp_path, receipt)
    desired_before = state.desired_path.read_bytes()
    observation_before = state.observation_path.read_bytes()
    if route == "direct":
        with pytest.raises(system_contract.ContractError, match="transcript"):
            state.record_live_load(receipt=receipt)
    else:
        assert state.promote_live_receipts(
            binder=live_receipt.transcript_binds_session, registry_root=registry,
        ) == []
    assert state.desired_path.read_bytes() == desired_before
    assert state.observation_path.read_bytes() == observation_before


@pytest.mark.parametrize("client", ["codex", "claude"])
@pytest.mark.parametrize("fault", ["symlink-file", "symlink-parent", "stale", "wrong-root"])
def test_live_load_preserves_path_time_and_payload_rejection(tmp_path, client, fault):
    state, receipt, transcript = _case(tmp_path, client)
    if fault == "symlink-file":
        alias = tmp_path / "alias.jsonl"
        alias.symlink_to(transcript)
        receipt["transcript_path"] = str(alias)
    elif fault == "symlink-parent":
        alias = tmp_path / "alias-directory"
        alias.symlink_to(transcript.parent, target_is_directory=True)
        receipt["transcript_path"] = str(alias / transcript.name)
    elif fault == "stale":
        receipt["recorded_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    else:
        foreign_root = tmp_path / "different-plugin"
        shutil.copytree(Path(receipt["plugin_root"]), foreign_root)
        (foreign_root / "hooks" / "hooks.json").write_text(
            json.dumps({"hooks": {"SessionStart": [{"command": "different"}]}}) + "\n",
            encoding="utf-8",
        )
        receipt["plugin_root"] = str(foreign_root)
    desired_before = state.desired_path.read_bytes()
    observation_before = state.observation_path.read_bytes()
    with pytest.raises(system_contract.ContractError):
        state.record_live_load(receipt=receipt)
    assert state.desired_path.read_bytes() == desired_before
    assert state.observation_path.read_bytes() == observation_before


@pytest.mark.parametrize("client", ["codex", "claude"])
def test_short_structured_transcript_positive_control(tmp_path, client):
    state, receipt, _ = _case(tmp_path, client)
    assert state.record_live_load(receipt=receipt)
    assert state.read_observation()["transactions"][-1]["live-loaded"]["status"] == "verified"


@pytest.mark.parametrize("client", ["codex", "claude"])
def test_transcript_outside_client_root_is_rejected(tmp_path, client):
    state, receipt, transcript = _case(tmp_path, client)
    outside = state.home / "unowned-transcript.jsonl"
    shutil.copyfile(transcript, outside)
    receipt["transcript_path"] = str(outside)
    before = state.observation_path.read_bytes()
    with pytest.raises(system_contract.ContractError, match="transcript"):
        state.record_live_load(receipt=receipt)
    assert state.observation_path.read_bytes() == before


def test_claude_subagent_transcript_cannot_prove_the_parent_session(tmp_path):
    state, receipt, transcript = _case(tmp_path, "claude")
    subagent = transcript.parent / receipt["session_id"] / "subagents" / "agent-fixture.jsonl"
    subagent.parent.mkdir(parents=True)
    shutil.copyfile(transcript, subagent)
    receipt["transcript_path"] = str(subagent)
    before = state.observation_path.read_bytes()
    with pytest.raises(system_contract.ContractError, match="transcript"):
        state.record_live_load(receipt=receipt)
    assert state.observation_path.read_bytes() == before


def _different_plugin(tmp_path: Path, receipt: dict) -> str:
    root = tmp_path / "different-plugin"
    shutil.copytree(Path(receipt["plugin_root"]), root)
    (root / "hooks" / "hooks.json").write_text(
        json.dumps({"hooks": {"SessionStart": [{"command": "different"}]}}) + "\n",
        encoding="utf-8",
    )
    return str(root)


def _healthy_engine(_args):
    """Only external client execution is substituted; CLI and validation run."""
    return {"engine": "fixture", "counts": {"ok": 1}, "steps": [], "exit": 0}


@pytest.mark.parametrize("client", ["codex", "claude"])
@pytest.mark.parametrize("command", ["doctor", "status"])
@pytest.mark.parametrize("as_json", [True, False], ids=["json", "human"])
@pytest.mark.parametrize("fault,reason", [("identity", "transcript"), ("payload", "digest")])
def test_rejected_candidate_surfaces_reason_without_restart_loop(
    tmp_path, capsys, client, command, as_json, fault, reason,
):
    state, receipt, transcript = _case(tmp_path, client)
    if fault == "identity":
        transcript.write_text(json.dumps(_binding(client, str(uuid.uuid4()))) + "\n", encoding="utf-8")
    else:
        receipt["plugin_root"] = _different_plugin(tmp_path, receipt)
    _, event = _registry_event(tmp_path, receipt, registry=state.live_receipt_registry_root())
    event_before = event.read_bytes()
    desired_before = state.desired_path.read_bytes()
    observation_before = state.observation_path.read_bytes()

    result = synthesis_cli.main(
        [command] + (["--json"] if as_json else []), state=state, engine_runner=_healthy_engine,
    )
    assert result == (1 if command == "doctor" else 0)
    output = capsys.readouterr().out
    payload = json.loads(output) if as_json else None
    note = payload.get("promotion_note", "") if payload else output
    assert reason in note.lower(), "the actual receipt rejection must reach the user"
    assert client in note.lower()
    if command == "doctor":
        action = payload["next_action"] if payload else output
        assert "restart " not in action.lower(), "validation failure is not missing SessionStart evidence"
    assert event.read_bytes() == event_before
    assert state.desired_path.read_bytes() == desired_before
    assert state.observation_path.read_bytes() == observation_before


@pytest.mark.parametrize("client", ["codex", "claude"])
@pytest.mark.parametrize("command", ["doctor", "status"])
def test_accepted_candidate_suppresses_another_candidate_rejection(tmp_path, capsys, client, command):
    state, receipt, _ = _case(tmp_path, client)
    registry = state.live_receipt_registry_root()
    _registry_event(tmp_path, receipt, registry=registry)
    rejected = dict(
        receipt, plugin_root=_different_plugin(tmp_path, receipt),
        receipt_event_id=str(uuid.uuid4()), recorded_at=datetime.now(timezone.utc).isoformat(),
    )
    _registry_event(tmp_path, rejected, registry=registry)

    assert synthesis_cli.main(
        [command, "--json"], state=state, engine_runner=_healthy_engine,
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert not payload.get("promotion_note")
    assert payload["promoted"] == [{"client": client, "session_id": receipt["session_id"]}]
    live = state.read_observation()["transactions"][-1]["live-loaded"]
    assert live["status"] == "verified"
    assert live["receipts"][client]["receipt_event_id"] == receipt["receipt_event_id"]
