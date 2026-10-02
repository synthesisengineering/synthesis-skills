"""Synthetic regression for PM state reader parity at both controller consumers."""
from pathlib import Path
import sys
import json
import os

import pytest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parents[1] / 'synthesis-project-management/scripts'))
from test_controller import (facade, engine, world, start_request, request, invoke,
                             state_of, prepared_consumer)
import project_state
from run_admission import native_binding


def adopt_large_pm(world, size=300_000):
    proof = native_binding(world['board'], world['actor']['native_payload'])
    project_state.build_operational_state(world['project'], project_id='alpha', phase='verification',
        status='active', controlling_plan='plan.md',
        accepted_baseline='Synthetic retained state. ' + 'x' * size,
        next_actions=['Verify the actual checkpoint consumer.'], last_session='Synthetic session',
        session_id=proof['session_uuid'], source_heads={})
    path = world['project'] / project_state.STATE_FILE
    assert 256 * 1024 < path.stat().st_size < project_state.MAX_STATE_JSON_BYTES
    assert project_state.read_operational_state(path)['project_id'] == 'alpha'


def test_large_pm_state_checkpoint_uses_pm_contract(facade, world):
    started = invoke(facade, world, start_request(world))
    adopt_large_pm(world)
    response = invoke(facade, world, request('checkpoint',
        {'reason': 'Verify large owner-produced PM state', 'include_pm': True},
        state_of(world, started)))
    assert response['status'] == 'RECORDED', response['diagnostics']
    assert state_of(world, response)['extensions']['controller']['checkpoint']['pm'] is not None


def test_large_pm_state_terminal_postamble_uses_pm_contract(facade, world):
    adopt_large_pm(world)
    state, _ = prepared_consumer(facade, world)
    response = invoke(facade, world, request('finish', {'disposition': 'completed'}, state))
    assert response['status'] == 'COMPLETED', response['diagnostics']
    assert response['coverage']['closure_postamble']['status'] == 'PASS'


@pytest.mark.parametrize("consumer", ["checkpoint", "finish"])
@pytest.mark.parametrize("invalid", ["oversized", "duplicate", "nonfinite", "symlink", "fifo"])
def test_pm_consumers_refuse_invalid_state(facade, world, monkeypatch, consumer, invalid):
    adopt_large_pm(world)
    if consumer == "finish":
        state, _ = prepared_consumer(facade, world)
        values = {"disposition": "completed"}
    else:
        started = invoke(facade, world, start_request(world))
        state = state_of(world, started)
        values = {"reason": "Invalid PM state must refuse", "include_pm": True}
    path = world["project"] / project_state.STATE_FILE
    retained = path.with_name("original-pm-state.json")
    original = None

    def corrupt():
        nonlocal original
        original = path.read_bytes()
        if invalid == "oversized":
            path.write_text('{"padding":"' + 'x' * project_state.MAX_STATE_JSON_BYTES + '"}')
        elif invalid == "duplicate":
            path.write_text('{"project_id":"alpha","project_id":"alpha"}')
        elif invalid == "nonfinite":
            path.write_text('{"value":NaN}')
        else:
            path.rename(retained)
            if invalid == "symlink":
                path.symlink_to(retained)
            else:
                os.mkfifo(path)

    if consumer == "finish":
        # Poison after terminal journal commit so the real final PM consumer,
        # rather than an earlier execution-basis inventory, sees this input.
        postamble = facade._postamble
        def corrupted_postamble(tx):
            corrupt()
            return postamble(tx)
        monkeypatch.setattr(facade, "_postamble", corrupted_postamble)
    else:
        corrupt()
    response = invoke(facade, world, request(consumer, values, state))
    assert response["status"] == "UNRESOLVED", response
    assert response["diagnostics"]
    after = state_of(world, response)
    if consumer == "checkpoint":
        # Durable request/admission prefixes remain, but no PM checkpoint is accepted.
        assert "checkpoint" not in after["extensions"]["controller"]
    else:
        assert after["status"] == "completed"
        assert response["coverage"]["closure_postamble"]["status"] == "PENDING"
    # The consumer may not repair or normalize invalid evidence on its own.
    if invalid == "symlink":
        assert path.is_symlink() and retained.read_bytes() == original
    elif invalid == "fifo":
        import stat
        assert stat.S_ISFIFO(path.lstat().st_mode) and retained.read_bytes() == original


def test_large_requests_keep_request_ceiling(facade, tmp_path):
    assert facade.MAX_REQUEST_BYTES == 256 * 1024
    raw = json.dumps({"padding": "x" * 300_000}).encode()
    path = tmp_path / "oversized-request.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="size bound"):
        facade.read_request(path)
    with pytest.raises(ValueError, match="size bound"):
        facade.decode_request(raw)


def test_checkpoint_journals_large_owner_state_above_physical_limit(facade, world):
    started = invoke(facade, world, start_request(world))
    adopt_large_pm(world, size=6_270_116)
    response = invoke(facade, world, request('checkpoint',
        {'reason': 'Verify complete owner state through journal preparation', 'include_pm': True},
        state_of(world, started)))
    assert response['status'] == 'RECORDED', response['diagnostics']
    state = state_of(world, response)
    assert state['extensions']['controller']['checkpoint']['pm'] is not None
