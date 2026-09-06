#!/usr/bin/env python3
"""UX-001: exercise emitted recovery guidance without launching either client.

The engine/client boundary is stubbed; the real report, CLI, transaction and
receipt-verification producers run against isolated temporary state. Recovery
text must not turn installed currency into exact-task lifecycle acceptance.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import onboard  # noqa: E402
import synthesis_cli  # noqa: E402
import system_contract  # noqa: E402
from test_independent_review import (  # noqa: E402
    _descriptor_file,
    _engine_result,
    _registry_event,
    bootstrap,
    live_receipt,
)
from test_synthesis_cli import verified_uninstall_engine  # noqa: E402
from test_system_contract import (  # noqa: E402
    live_receipt as receipt_fixture,
    native_transcript,
    release_record,
    release_repo,
)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    """Neither an installed launcher nor the real receipt registry is an input."""
    monkeypatch.delenv("SYNTHESIS_ACTIVE_DESCRIPTOR", raising=False)
    monkeypatch.delenv("SYNTHESIS_RESOLVED_BOOTSTRAP", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def _recovery_contract(text: str, clients: tuple[str, ...]) -> None:
    """Assert the ordered recovery ladder, not a particular helper signature."""
    lower = text.lower()
    for client in clients:
        assert "restart " + ("claude code" if client == "claude" else "codex") in lower
    assert "existing" in lower, text
    assert "reopen" in lower or "resume" in lower, text
    assert lower.index("existing") < lower.index("new "), text
    assert "sessionstart" in lower and "transcript" in lower, text
    assert "same" in lower and ("uuid" in lower or "session" in lower), text
    assert "version" in lower and "root" in lower, text
    assert "metadata" in lower, text
    assert "unsupported" in lower or "not support" in lower, text
    assert "fail" in lower or "mismatch" in lower, text
    if "codex" in clients:
        assert "if" in lower and "hook" in lower and "trust" in lower, text


def _state(tmp_path: Path, clients: tuple[str, ...]):
    state = system_contract.SystemState(home=tmp_path / "home")
    receipt = receipt_fixture(tmp_path, clients[0], home=state.home)
    root = Path(receipt["plugin_root"])
    desired = system_contract.default_desired_state("skills-only", list(clients), "stable")
    planes = synthesis_cli._planes(desired, "setup")
    planes.update({
        "release": release_record(root),
        "source-provenance": {"status": "verified", "root": str(root)},
    })
    state.run_transaction("setup", desired, lambda _tx: planes)
    return state, receipt


def _fresh_event(state, receipt, *, client=None, session_id=None):
    event = dict(receipt)
    event.update({
        "client": client or receipt["client"],
        "session_id": session_id or receipt["session_id"],
        "receipt_event_id": str(uuid.uuid4()),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    })
    event["provenance_env"] = event["client"] + "-transcript"
    transcript = native_transcript(state.home, event["client"], event["session_id"])
    event["transcript_path"] = str(transcript)
    return event


@pytest.mark.parametrize("clients", [("claude",), ("codex",), ("claude", "codex")])
@pytest.mark.parametrize("as_json", [False, True], ids=["human", "json"])
def test_doctor_emits_existing_conversation_recovery(tmp_path, capsys, clients, as_json):
    state, _ = _state(tmp_path, clients)
    assert synthesis_cli.main(
        ["doctor"] + (["--json"] if as_json else []),
        state=state, engine_runner=lambda _argv: _engine_result(),
    ) == 1
    output = capsys.readouterr().out
    text = json.loads(output)["next_action"] if as_json else output
    _recovery_contract(text, clients)


@pytest.mark.parametrize("loaded,missing", [("claude", "codex"), ("codex", "claude")])
def test_partial_doctor_only_requests_the_missing_client(tmp_path, capsys, loaded, missing):
    state, receipt = _state(tmp_path, (loaded, missing))
    assert state.record_live_load(receipt=_fresh_event(state, receipt))
    assert synthesis_cli.main(
        ["doctor", "--json"], state=state, engine_runner=lambda _argv: _engine_result(),
    ) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["planes"]["live-loaded"]["missing_clients"] == [missing]
    assert "restart " + ("claude code" if loaded == "claude" else "codex") not in payload["next_action"].lower()
    _recovery_contract(payload["next_action"], (missing,))


@pytest.mark.parametrize("as_json", [False, True], ids=["human", "json"])
def test_setup_transaction_emits_the_recovery_ladder(tmp_path, capsys, as_json):
    state = system_contract.SystemState(home=tmp_path / "home")
    engine = _engine_result()
    engine["effective_selection"] = {
        "profile": "skills-only", "clients": ["claude", "codex"],
        "personal_workspace": None, "personal_configuration": None,
        "layers": system_contract.default_desired_state(
            "skills-only", ["claude", "codex"], "stable"
        )["layers"],
    }
    assert synthesis_cli.main(
        ["setup", "--profile", "skills-only", "--clients", "claude,codex"]
        + (["--json"] if as_json else []),
        state=state, engine_runner=lambda _argv: engine,
    ) == 0
    output = capsys.readouterr().out
    transaction = state.read_observation()["transactions"][-1]
    assert transaction["live-loaded"]["status"] == "restart-required"
    text = json.loads(output)["live-loaded"]["detail"] if as_json else output
    _recovery_contract(text, ("claude", "codex"))
    _recovery_contract(transaction["live-loaded"]["detail"], ("claude", "codex"))


def _native_report(client, scenario, as_json, capsys):
    before = "9.8.6" if scenario == "upgrade" else "9.8.7"
    record = [(False, None), (True, "9.8.7")] if scenario == "initial" else [
        (True, before), (True, "9.8.7"),
    ]
    report = onboard.Report(as_json=as_json)
    with patch.object(onboard, "plugin_record", side_effect=record), \
         patch.object(onboard, "expected_policy_version", return_value=("9.8.7", "fixture")), \
         patch.object(onboard, "configured_marketplace_ref", return_value="main"), \
         patch.object(onboard, "refresh_plugin", return_value=(True, "refreshed")) as refresh, \
         patch.object(onboard, "install_plugin", return_value=(True, "installed")) as install, \
         patch.object(onboard, "synchronize_codex_history", return_value=(True, "preserved")):
        onboard.phase_ecosystem(
            report, {client: "fixture-client"}, False, False,
            {"channel": "stable", "version_pin": None}, refresh_native_plugins=True,
        )
    assert report.exit_code() == 0
    (install if scenario == "initial" else refresh).assert_called_once()
    (refresh if scenario == "initial" else install).assert_not_called()
    onboard.finish(report, argparse.Namespace(json=as_json, dry_run=False), 0)
    output = capsys.readouterr().out
    if as_json:
        output = " ".join(
            str(step["detail"]) + " " + str(step.get("hint") or "")
            for step in json.loads(output)["steps"]
        )
    return output, report


@pytest.mark.parametrize("client", ["claude", "codex"])
@pytest.mark.parametrize("scenario", ["upgrade", "initial", "same-version"])
@pytest.mark.parametrize("as_json", [False, True], ids=["human", "json"])
def test_native_success_does_not_abandon_existing_conversations(capsys, client, scenario, as_json):
    text, report = _native_report(client, scenario, as_json, capsys)
    if scenario == "same-version":
        assert report.steps[0]["status"] == onboard.OK
        assert "no new task needed" not in text.lower()
    else:
        assert report.steps[0]["status"] == onboard.CHANGED
    _recovery_contract(text, (client,))
    if scenario == "initial":
        assert "none" in text.lower() or "no existing" in text.lower(), text


@pytest.mark.parametrize("client", ["claude", "codex"])
def test_native_no_refresh_positive_control_does_not_launch_client(client):
    report = onboard.Report(as_json=True)
    with patch.object(onboard, "plugin_record", return_value=(True, "9.8.7")), \
         patch.object(onboard, "expected_policy_version", return_value=("9.8.7", "fixture")), \
         patch.object(onboard, "configured_marketplace_ref", return_value="stable"), \
         patch.object(onboard, "refresh_plugin") as refresh, \
         patch.object(onboard, "install_plugin") as install:
        onboard.phase_ecosystem(
            report, {client: "fixture-client"}, False, False,
            {"channel": "stable", "version_pin": None}, refresh_native_plugins=True,
        )
    refresh.assert_not_called()
    install.assert_not_called()
    assert report.steps[0]["status"] == onboard.OK
    assert "no refresh needed" in report.steps[0]["detail"]
    assert "no new task needed" not in report.steps[0]["detail"]


def test_native_version_mismatch_uses_public_terminal_update_hint():
    report = onboard.Report(as_json=True)
    with patch.object(onboard, "plugin_record", return_value=(True, "9.8.6")), \
         patch.object(onboard, "expected_policy_version", return_value=("9.8.7", "fixture")), \
         patch.object(onboard, "refresh_plugin") as refresh:
        onboard.phase_ecosystem(
            report, {"codex": "fixture-client"}, False, False,
            {"channel": "stable", "version_pin": None}, refresh_native_plugins=False,
        )
    refresh.assert_not_called()
    assert report.steps[0]["status"] == onboard.ACTION
    hint = report.steps[0]["hint"]
    assert "synthesis update" in hint and "last action" in hint
    assert "onboard.py update" not in hint


@pytest.mark.parametrize("as_json", [False, True], ids=["human", "json"])
def test_uninstall_not_applicable_never_requests_restart(tmp_path, capsys, as_json):
    state, _ = _state(tmp_path, ("claude", "codex"))
    assert synthesis_cli.main(
        ["uninstall"] + (["--json"] if as_json else []),
        state=state, engine_runner=verified_uninstall_engine,
    ) == 0
    output = capsys.readouterr().out
    transaction = state.read_observation()["transactions"][-1]
    assert transaction["live-loaded"]["status"] == "not-applicable"
    assert "restart" not in output.lower()
    assert "fresh selected-client" not in output.lower()


@pytest.mark.parametrize("client", ["claude", "codex"])
def test_genuine_same_uuid_event_is_accepted_without_a_new_conversation(tmp_path, client):
    state, receipt = _state(tmp_path, (client,))
    event = _fresh_event(state, receipt)
    _registry_event(state.live_receipt_registry_root(), event, bound_at_record=True)
    promoted = state.promote_live_receipts(binder=live_receipt.transcript_binds_session)
    assert [(item["client"], item["session_id"]) for item in promoted] == [(client, receipt["session_id"])]
    plane = state.read_observation()["transactions"][-1]["live-loaded"]
    assert plane["status"] == "verified"
    assert plane["receipts"][client]["receipt_event_id"] == event["receipt_event_id"]


def test_doctor_global_event_is_labelled_not_exact_invoking_task_acceptance(tmp_path, monkeypatch, capsys):
    state, receipt = _state(tmp_path, ("codex",))
    invoking_session = str(uuid.uuid4())
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:" + invoking_session)
    event = _fresh_event(state, receipt)
    assert event["session_id"] != invoking_session
    _registry_event(state.live_receipt_registry_root(), event, bound_at_record=True)
    assert synthesis_cli.main(
        ["doctor", "--json"], state=state, engine_runner=lambda _argv: _engine_result(),
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    plane = payload["planes"]["live-loaded"]
    assert plane["status"] == "verified"
    assert plane["receipts"]["codex"]["session_id"] == event["session_id"]
    assert plane["scope"] == "recorded-selected-client-sessions"
    assert synthesis_cli.main(
        ["doctor"], state=state, engine_runner=lambda _argv: _engine_result(),
    ) == 0
    human = capsys.readouterr().out.lower()
    assert "recorded" in human and "not" in human and "task" in human, human


def _recorded_event_with_newer_candidate(tmp_path):
    """A remains attached; independently prove that newer B is promotable."""
    state, receipt = _state(tmp_path, ("codex",))
    positive_control = system_contract.SystemState(home=tmp_path / "positive-control")
    desired = state.read_desired()
    positive_control.run_transaction("setup", desired, lambda _tx: {
        "release": release_record(Path(receipt["plugin_root"])),
        "source-provenance": {"status": "verified", "root": receipt["plugin_root"]},
        "live-loaded": {"status": "restart-required"},
    })
    first = _fresh_event(state, receipt)
    _registry_event(state.live_receipt_registry_root(), first, bound_at_record=True)
    assert state.promote_live_receipts(binder=live_receipt.transcript_binds_session)
    state.record_outcome({"status": "verified", "task": "fixture-outcome"})

    newer = _fresh_event(state, receipt, session_id=str(uuid.uuid4()))
    assert newer["recorded_at"] > first["recorded_at"]
    for target in (state, positive_control):
        target_event = dict(newer)
        target_event["transcript_path"] = str(native_transcript(
            target.home, newer["client"], newer["session_id"],
        ))
        _registry_event(target.live_receipt_registry_root(), target_event, bound_at_record=True)
    promoted = positive_control.promote_live_receipts(binder=live_receipt.transcript_binds_session)
    assert [item["session_id"] for item in promoted] == [newer["session_id"]]
    control = positive_control.read_observation()["transactions"][-1]["live-loaded"]
    assert control["receipts"]["codex"]["receipt_event_id"] == newer["receipt_event_id"]
    assert state.promote_live_receipts(binder=live_receipt.transcript_binds_session) == []
    return state, first, newer


@pytest.mark.parametrize("command", ["doctor", "status"])
@pytest.mark.parametrize("as_json", [False, True], ids=["human", "json"])
def test_retained_event_is_labelled_recorded_not_latest(tmp_path, capsys, command, as_json):
    state, first, newer = _recorded_event_with_newer_candidate(tmp_path)
    assert synthesis_cli.main(
        [command] + (["--json"] if as_json else []),
        state=state, engine_runner=lambda _argv: _engine_result(),
    ) == 0
    output = capsys.readouterr().out
    stored = state.read_observation()["transactions"][-1]["live-loaded"]
    assert stored["receipts"]["codex"]["receipt_event_id"] == first["receipt_event_id"]
    assert first["receipt_event_id"] != newer["receipt_event_id"]
    if as_json:
        payload = json.loads(output)
        if command == "doctor":
            scope = payload["planes"]["live-loaded"]
            assert scope["receipts"]["codex"]["receipt_event_id"] == first["receipt_event_id"]
        else:
            scope = payload["live_scope"]
        assert scope["scope"] == "recorded-selected-client-sessions"
    else:
        lower = output.lower()
        assert "recorded" in lower and "selected" in lower and "not" in lower and "task" in lower
        assert "latest session" not in lower and "latest qualifying" not in lower


@pytest.mark.parametrize("command", ["doctor", "status"])
@pytest.mark.parametrize("as_json", [False, True], ids=["human", "json"])
def test_scope_presentation_preserves_observation_and_outcome_bytes(tmp_path, capsys, command, as_json):
    state, _, _ = _recorded_event_with_newer_candidate(tmp_path)
    before = state.observation_path.read_bytes()
    observed = json.loads(before)
    latest = observed["transactions"][-1]
    outcome = latest["outcome-verified"]
    assert outcome["live_loaded_sha256"] == system_contract.json_digest(latest["live-loaded"])
    assert synthesis_cli.main(
        [command] + (["--json"] if as_json else []),
        state=state, engine_runner=lambda _argv: _engine_result(),
    ) == 0
    output = capsys.readouterr().out
    assert state.observation_path.read_bytes() == before
    after = state.read_observation()["transactions"][-1]
    assert after["outcome-verified"] == outcome
    assert outcome["live_loaded_sha256"] == system_contract.json_digest(after["live-loaded"])
    if as_json:
        payload = json.loads(output)
        if command == "status":
            assert payload["observed"] == observed
            assert payload["live_scope"]["scope"] == "recorded-selected-client-sessions"
        else:
            assert payload["planes"]["outcome-verified"] == outcome


@pytest.mark.parametrize("defect", ["wrong-version", "missing-root", "wrong-digest", "unbound", "stale"])
def test_receipt_rejection_positive_control_remains_fail_closed(tmp_path, defect):
    state, receipt = _state(tmp_path, ("codex",))
    event = _fresh_event(state, receipt)
    if defect == "wrong-version":
        event = receipt_fixture(tmp_path, "codex", "9.8.6", home=state.home)
        assert state.record_live_load(receipt=event) is False
    else:
        match = {
            "missing-root": "unavailable", "wrong-digest": "release digest",
            "unbound": "transcript-bound", "stale": "freshness",
        }[defect]
        if defect == "missing-root":
            event["plugin_root"] = str(tmp_path / "nonexistent")
        elif defect == "wrong-digest":
            loaded = tmp_path / "wrong-loaded-root"
            shutil.copytree(event["plugin_root"], loaded)
            (loaded / "hooks/hooks.json").write_text(
                json.dumps({"hooks": {"SessionStart": [{"command": "altered"}]}}) + "\n",
                encoding="utf-8",
            )
            event["plugin_root"] = str(loaded)
        elif defect == "unbound":
            event["transcript_bound_at_record"] = False
        else:
            event["recorded_at"] = "2020-01-01T00:00:00+00:00"
        with pytest.raises(system_contract.ContractError, match=match):
            state.record_live_load(receipt=event)
    assert state.read_observation()["transactions"][-1]["live-loaded"]["status"] == "restart-required"
    assert state.record_live_load(receipt=_fresh_event(state, receipt))
    assert state.read_observation()["transactions"][-1]["live-loaded"]["status"] == "verified"


def test_doctor_repair_precedes_reload_in_real_installed_failure(tmp_path, capsys):
    state, _ = _state(tmp_path, ("codex",))
    failing = _engine_result(1, steps=[{
        "phase": "ecosystem", "status": "action-needed", "detail": "fixture install defect",
    }])
    assert synthesis_cli.main(
        ["doctor", "--json"], state=state, engine_runner=lambda _argv: failing,
    ) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["planes"]["installed"]["status"] == "defective"
    assert payload["next_action"].startswith("Run synthesis repair")
    assert "restart" not in payload["next_action"].lower()


def test_doctor_provenance_repair_precedes_reload_and_installed_repair(tmp_path, monkeypatch, capsys):
    checkout = release_repo(tmp_path)
    root, descriptor = bootstrap.materialize_release(
        checkout, tmp_path / "releases", channel="stable", ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    active = _descriptor_file(tmp_path / "active.json", descriptor, root)
    monkeypatch.setenv("SYNTHESIS_ACTIVE_DESCRIPTOR", str(active))
    state = system_contract.SystemState(home=tmp_path / "home")
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable")
    state.run_transaction("setup", desired, lambda _tx: {
        "release": descriptor,
        "resolved": {"status": "verified", "release": descriptor},
        "source-provenance": {"status": "verified", "root": str(root)},
    })
    target = root / ".codex-plugin/plugin.json"
    os.chmod(target, 0o644)
    target.write_text('{"name":"synthesis-skills","version":"9.8.7","altered":true}\n', encoding="utf-8")
    assert synthesis_cli.main(
        ["doctor", "--json"], state=state, engine_runner=lambda _argv: _engine_result(1),
    ) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["planes"]["source-provenance"]["status"] == "drifted"
    assert payload["planes"]["installed"]["status"] == "defective"
    assert "content digest" in payload["next_action"]
    assert "synthesis update" in payload["next_action"]
    assert "restart" not in payload["next_action"].lower()
