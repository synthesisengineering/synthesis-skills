"""Current protocol grants through the real journal; native process is synthetic."""

import json
from copy import deepcopy
import pytest
from test_prepared_native_launch import prepared, TOKEN
import importlib
from test_controller import attribute_recovery_fixture

_fixture_owner = importlib.import_module("test_controller")
engine = _fixture_owner.engine
facade = _fixture_owner.facade
world = _fixture_owner.world


def muse_world(world, monkeypatch):
    from test_native_transport import muse_rows, SESSION

    root = world["scratch"] / "muse-sessions"
    target = root / "2026" / "01" / "01" / SESSION / "session.jsonl"
    target.parent.mkdir(parents=True)
    target.write_text("".join(json.dumps(x) + "\n" for x in muse_rows()[:2]))
    world["transcript"] = target
    world["actor"]["native_payload"].pop("transcript_path")
    prior = world["actor"]["native_payload"]["session_id"]
    world["actor"]["native_payload"]["session_id"] = SESSION
    monkeypatch.setenv("MUSE_SESSIONS_DIR", str(root))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "muse:" + SESSION)
    monkeypatch.setenv("MUSE_SESSION_ID", SESSION)
    world["board"].write_text(
        world["board"]
        .read_text()
        .replace("| claude |", "| muse |")
        .replace("cc:" + prior, "muse:" + SESSION)
    )
    import native_resume

    monkeypatch.setattr(
        native_resume,
        "installed_binary",
        lambda client: {"path": "/synthetic/muse", "sha256": "a" * 64, "size": 4},
    )


def test_real_muse_prepare_derives_protocol_without_caller_override(
    facade, world, monkeypatch
):
    import native_muse_contract as contract

    muse_world(world, monkeypatch)
    state = prepared(facade, world)
    row = state["extensions"]["prepared_native_launch"]["permits"]["permit1"]
    assert row["client"] == "muse" and row["native_protocol"] == contract.binding()
    assert row["ownership_transfer"] is False and row["effect_replay_allowed"] is False


@pytest.mark.parametrize("phase", ["reserve", "submit"])
def test_actual_owner_critical_section_refuses_changed_qualification(
    facade, world, monkeypatch, phase
):
    import native_muse_contract as contract
    import prepared_native_launch as owner
    import run_state

    muse_world(world, monkeypatch)
    state = prepared(facade, world)
    attribute_recovery_fixture(world)
    if phase == "submit":
        state = owner._step(
            world["project"],
            state["run_id"],
            "permit1",
            TOKEN,
            "reserve",
            runtime_root=world["runtime"],
        )
    old = deepcopy(state)
    changed = contract.binding()
    changed["fingerprint"] = "sha256:" + "0" * 64
    monkeypatch.setattr(contract, "binding", lambda: changed)
    with pytest.raises(ValueError, match="protocol qualification"):
        owner._step(
            world["project"],
            state["run_id"],
            "permit1",
            TOKEN,
            phase,
            runtime_root=world["runtime"],
            send=lambda: pytest.fail("changed qualification dispatched"),
        )
    assert run_state.load_run(world["project"], state["run_id"]) == old


def test_real_owner_retains_queued_command_and_exact_withdrawal(
    facade, world, monkeypatch
):
    import prepared_native_launch as owner
    import run_state
    from test_native_queue_custody import execute

    muse_world(world, monkeypatch)
    state = prepared(facade, world)
    attribute_recovery_fixture(world)
    grant = state["extensions"]["prepared_native_launch"]["permits"]["permit1"]
    result, calls, _, _ = execute(
        monkeypatch,
        grant_override=grant,
        dispatch=lambda: owner.execute(
            world["project"],
            state["run_id"],
            "permit1",
            TOKEN,
            runtime_root=world["runtime"],
        ),
    )
    row = run_state.load_run(world["project"], state["run_id"])["extensions"][
        "prepared_native_launch"
    ]["permits"]["permit1"]
    assert row["admission"]["commandId"] == grant["turn_command_id"]
    assert row["admission"]["disposition"] == "queued"
    assert row["outcome"] == result
    assert row["outcome"]["queue_reconciliation"]["status"] == "removed"
    assert row["status"] == "unknown" and not result["task_accepted"]
    assert [method for method, _ in calls].count("turn/start") == 1
    before = deepcopy(row)
    with pytest.raises(ValueError, match="one-shot launch"):
        owner.execute(
            world["project"],
            state["run_id"],
            "permit1",
            TOKEN,
            runtime_root=world["runtime"],
        )
    assert (
        run_state.load_run(world["project"], state["run_id"])["extensions"][
            "prepared_native_launch"
        ]["permits"]["permit1"]
        == before
    )
