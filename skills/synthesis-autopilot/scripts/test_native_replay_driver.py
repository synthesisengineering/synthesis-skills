"""Actual recover facade/CLI; all native producers and ownership are synthetic."""

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from test_controller import (
    facade as facade,
    invoke,
    request,
    start_request,
    state_of,
    attribute_recovery_fixture,
)  # noqa: F401
from test_native_replay import (
    bridge as bridge,
    engine as engine,
    world as world,
    adapter,
    append,
    record,
    observe,
    src,
)  # noqa: F401


__all__ = ["facade", "bridge", "engine", "world"]


def original(world, facade, engine, monkeypatch, *, cancel=False, large=False):
    version, decode = adapter.ADAPTER_VERSION, adapter.decode_record
    monkeypatch.setattr(adapter, "ADAPTER_VERSION", "synthetic-prior-driver")

    def before(row, *args, **kwargs):
        if row.get("type") == "custom-title":
            raise adapter.DialectError("prior synthetic unsupported record")
        return decode(row, *args, **kwargs)

    monkeypatch.setattr(adapter, "decode_record", before)
    started = invoke(facade, world, start_request(world))
    assert started["status"] == "READY", started
    state = state_of(world, started)
    session = world["actor"]["native_payload"]["session_id"]
    if cancel:
        append(
            world,
            {
                "type": "user",
                "uuid": "original-cancellation",
                "sessionId": session,
                "message": {"role": "user", "content": "Pause this original task"},
            },
        )
    append(world, record("custom-title", session))
    if large:
        for _ in range(25):
            append(
                world,
                {
                    "type": "assistant",
                    "sessionId": session,
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "x" * 50000}],
                    },
                },
            )
    for _ in range(32):
        state = observe(engine, world, state)
        if src(state)["cursor"]["offset"] == world["transcript"].stat().st_size:
            break
    else:
        pytest.fail("fixture input enrollment exceeded its fixed page count")
    assert src(state)["cursor"]["first_gap"] is not None
    monkeypatch.setattr(adapter, "ADAPTER_VERSION", version)
    monkeypatch.setattr(adapter, "decode_record", decode)
    return state


@pytest.mark.parametrize("cancel", [False, True])
def test_one_recover_invocation_completes_original_interval(
    facade, engine, world, bridge, monkeypatch, cancel
):
    state = original(world, facade, engine, monkeypatch, cancel=cancel, large=True)
    before = deepcopy(state)
    req = request(
        "recover",
        {
            "reconcile_sources": True,
            "replay_limits": {**facade.REPLAY_DEFAULTS, "bytes": 256 * 1024 * 1024},
        },
        state,
        "single-recovery",
    )
    output = invoke(facade, world, req)
    final = state_of(world, output)
    assert src(final)["replay"]["status"] == "complete", output
    assert output["coverage"]["replay_driver"]["status"] == "complete"
    assert (
        src(final)["replay"]["frontier"] - src(final)["replay"]["original_offset"]
        > 1024 * 1024
    )
    actual = bridge.current_invalidation(engine.inspect_context(final, world["actor"]))
    assert actual["status"] == ("invalidated" if cancel else "clear")
    assert final["effects"] == before["effects"]
    assert (
        final["extensions"]["workflow"]["budget"]
        == before["extensions"]["workflow"]["budget"]
    )
    again = invoke(facade, world, req)
    assert state_of(world, again) == final


def test_real_cli_recovers_without_an_external_tool_iteration(
    facade, engine, world, monkeypatch
):
    state = original(world, facade, engine, monkeypatch, large=True)
    req = request(
        "recover",
        {
            "reconcile_sources": True,
            "replay_limits": {**facade.REPLAY_DEFAULTS, "bytes": 256 * 1024 * 1024},
        },
        state,
        "one-cli-recovery",
    )
    actor = world["scratch"] / "actor.json"
    actor.write_text(json.dumps(world["actor"]))
    intent = world["scratch"] / "recover.json"
    intent.write_text(json.dumps(req))
    attribute_recovery_fixture(world)
    done = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("autopilot.py")),
            "recover",
            "--project",
            str(world["project"]),
            "--actor",
            str(actor),
            "--request",
            str(intent),
            "--source-mode",
            "synthetic",
        ],
        capture_output=True,
        text=True,
        timeout=25,
        env={**os.environ, "SYNTHESIS_AUTOPILOT_RUNTIME": str(world["runtime"])},
    )
    assert done.returncode == 0, done.stderr
    output = json.loads(done.stdout)
    assert len(done.stdout.splitlines()) == 1
    final = engine.load_run(world["project"], state["run_id"])
    assert src(final)["replay"]["status"] == "complete", output
    assert output["coverage"]["replay_driver"]["status"] == "complete"


def values(facade, **limits):
    return {
        "reconcile_sources": True,
        "replay_limits": {**facade.REPLAY_DEFAULTS, **limits},
    }


@pytest.mark.parametrize(
    "limit,reason",
    [
        ({"steps": 1}, "step_limit"),
        ({"bytes": 1}, "validation_byte_limit"),
        ({"wall_millis": 1}, "time_limit"),
    ],
)
def test_limits_retain_frontier_and_cannot_refill_same_request(
    facade, engine, world, monkeypatch, limit, reason
):
    state = original(world, facade, engine, monkeypatch)
    req = request("recover", values(facade, **limit), state, "limited-recovery")
    first = invoke(facade, world, req)
    report = first["coverage"]["replay_driver"]
    assert first["status"] == "RECONCILE", first
    assert report["status"] == "limited" and report["reason"] == reason
    final = state_of(world, first)
    repeated = invoke(facade, world, req)
    assert state_of(world, repeated) == final
    same = repeated["coverage"]["replay_driver"]
    assert same["steps"] == report["steps"] and same["deadline"] == report["deadline"]
    assert same["validation_bytes_charged"] == report["validation_bytes_charged"]
    assert final["effects"] == state["effects"]
    assert (
        final["extensions"]["workflow"]["budget"]
        == state["extensions"]["workflow"]["budget"]
    )
    changed = deepcopy(req)
    changed["input"]["replay_limits"]["bytes"] += 1
    assert invoke(facade, world, changed)["status"] == "UNRESOLVED"
    assert state_of(world, repeated) == final


@pytest.mark.parametrize("phase", ["reconcile", "ranges", "semantics", "decode"])
def test_postcommit_interruption_recovers_exact_prefix(
    facade, engine, world, monkeypatch, phase
):
    state = original(world, facade, engine, monkeypatch, large=True)
    req = request(
        "recover", values(facade, bytes=256 * 1024 * 1024), state, "interrupted-driver"
    )
    import run_state

    original_project = run_state._project
    fired = False

    def fail_once(project, state):
        nonlocal fired
        replay = src(state).get("replay", {})
        steps = (
            state.get("extensions", {})
            .get("controller", {})
            .get("requests", {})
            .get(req["request_id"], {})
            .get("steps", {})
        )
        reached = (
            phase == "reconcile"
            and any(".reconcile." in k for k in steps)
            or phase != "reconcile"
            and replay.get("phase") == phase
            and any(".observe." in k for k in steps)
        )
        if reached and not fired:
            fired = True
            raise OSError("synthetic process loss after exact owner journal commit")
        return original_project(project, state)

    monkeypatch.setattr(run_state, "_project", fail_once)
    first = invoke(facade, world, req)
    assert fired and first["status"] == "UNRESOLVED", first
    prefix = engine.load_run(world["project"], state["run_id"])
    assert first["coverage"]["replay_driver"]["steps"] == sum(
        k.startswith("bounded-replay.")
        for k in prefix["extensions"]["controller"]["requests"][req["request_id"]][
            "steps"
        ]
    )
    old_steps = deepcopy(
        prefix["extensions"]["controller"]["requests"][req["request_id"]]["steps"]
    )
    monkeypatch.setattr(run_state, "_project", original_project)
    final_response = invoke(facade, world, req)
    final = state_of(world, final_response)
    assert src(final)["replay"]["status"] == "complete", final_response
    current_steps = final["extensions"]["controller"]["requests"][req["request_id"]][
        "steps"
    ]
    assert all(current_steps[k] == v for k, v in old_steps.items())
    journal = list(run_state._events(world["project"], final["run_id"]))
    assert len(journal) == len({event["command_id"] for event in journal})
    assert final["effects"] == state["effects"]
    assert (
        final["extensions"]["workflow"]["budget"]
        == state["extensions"]["workflow"]["budget"]
    )


def test_appending_during_one_operation_refuses_without_skipping(
    facade, engine, world, monkeypatch
):
    state = original(world, facade, engine, monkeypatch, large=True)
    original_step = facade._Transaction.step
    changed = False

    def raced(tx, name, command, payload, **kwargs):
        nonlocal changed
        result = original_step(tx, name, command, payload, **kwargs)
        if (
            name.startswith("bounded-replay.")
            and command == "native.observe"
            and not changed
        ):
            changed = True
            append(
                world,
                record("custom-title", world["actor"]["native_payload"]["session_id"]),
            )
        return result

    monkeypatch.setattr(facade._Transaction, "step", raced)
    output = invoke(
        facade,
        world,
        request(
            "recover", values(facade, bytes=256 * 1024 * 1024), state, "mutated-driver"
        ),
    )
    final = state_of(world, output)
    assert changed and output["status"] == "RECONCILE", output
    assert src(final)["replay"]["status"] == "failed"
    assert (
        output["coverage"]["replay_driver"]["reason"] == "source_reconciliation_failed"
    )
    assert src(final)["cursor"] == src(state)["cursor"]
    assert final["effects"] == state["effects"]


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"steps": True},
        {"steps": 0},
        {"steps": 4097},
        {"bytes": float("inf")},
        {"unknown": 2},
    ],
)
def test_closed_limit_schema_changes_no_state(facade, engine, world, monkeypatch, bad):
    state = original(world, facade, engine, monkeypatch)
    limits = {} if not bad else {**facade.REPLAY_DEFAULTS, **bad}
    with pytest.raises(ValueError):
        invoke(
            facade,
            world,
            request(
                "recover",
                {"reconcile_sources": True, "replay_limits": limits},
                state,
                "invalid-limit",
            ),
        )
    assert engine.load_run(world["project"], state["run_id"]) == state


def test_source_currentness_after_completed_request_stays_separate(
    facade, engine, world, monkeypatch, bridge
):
    state = original(world, facade, engine, monkeypatch)
    req = request("recover", values(facade), state, "completed-then-changed")
    first = invoke(facade, world, req)
    final = state_of(world, first)
    assert first["coverage"]["replay_driver"]["status"] == "complete"
    append(
        world, record("custom-title", world["actor"]["native_payload"]["session_id"])
    )
    again = invoke(facade, world, req)
    assert state_of(world, again) == final
    assert again["status"] != "READY", again
    assert (
        bridge.current_invalidation(engine.inspect_context(final, world["actor"]))[
            "status"
        ]
        == "unknown"
    )


def test_original_time_allowance_survives_cold_retry(
    facade, engine, world, monkeypatch
):
    from datetime import timedelta
    import run_state

    state = original(world, facade, engine, monkeypatch)
    req = request("recover", values(facade), state, "expired-prefix")
    project = run_state._project

    def fail(path, state):
        if src(state).get("replay", {}).get("status") == "pending":
            raise OSError("synthetic interruption")
        return project(path, state)

    monkeypatch.setattr(run_state, "_project", fail)
    first = invoke(facade, world, req)
    assert first["status"] == "UNRESOLVED"
    monkeypatch.setattr(run_state, "_project", project)
    prefix = engine.load_run(world["project"], state["run_id"])
    before = first["coverage"]["replay_driver"]
    monkeypatch.setattr(
        facade,
        "_driver_clock",
        lambda: run_state._time(before["deadline"]) + timedelta(seconds=1),
    )
    retry = invoke(facade, world, req)
    final = state_of(world, retry)
    after = retry["coverage"]["replay_driver"]
    assert after["reason"] == "time_limit" and after["deadline"] == before["deadline"]
    assert (
        after["steps"] == before["steps"]
        and after["validation_bytes_charged"] == before["validation_bytes_charged"]
    )
    assert src(final)["replay"] == src(prefix)["replay"]


def test_concurrent_revision_before_effect_refuses_unbudgeted_phase(
    facade, engine, world, monkeypatch
):
    state = original(world, facade, engine, monkeypatch)
    step = facade._Transaction.step
    fired = False

    def concurrent(tx, name, command, payload, **kwargs):
        nonlocal fired
        if (
            command == "native.observe"
            and name.startswith("bounded-replay.")
            and not fired
        ):
            fired = True
            current = engine.load_run(world["project"], state["run_id"])
            engine.apply_command(
                world["project"],
                state["run_id"],
                "controller.checkpoint",
                {"reason": "Concurrent synthetic journal record", "include_pm": False},
                expected_revision=current["revision"],
                command_id="concurrent-record",
                actor=world["actor"],
                runtime_root=world["runtime"],
            )
        return step(tx, name, command, payload, **kwargs)

    monkeypatch.setattr(facade._Transaction, "step", concurrent)
    output = invoke(
        facade, world, request("recover", values(facade), state, "concurrent-driver")
    )
    assert fired and output["status"] == "UNRESOLVED", output
    final = state_of(world, output)
    assert src(final)["replay"]["witness_index"] == 0
    assert output["coverage"]["replay_driver"]["steps"] == 1


def test_source_count_limit_is_checked_before_owner_work(facade, monkeypatch):
    from datetime import datetime, timezone, timedelta
    import time

    class Tx:
        pass

    tx = Tx()
    calls = []
    report = {
        "sources": ["root", "worker:one"],
        "limits": {"sources": 1},
        "steps": 0,
        "validation_bytes_charged": 0,
    }
    monkeypatch.setattr(
        facade,
        "_driver_state",
        lambda *args: (
            report,
            [],
            datetime.now(timezone.utc) + timedelta(seconds=30),
            time.monotonic() + 30,
        ),
    )
    tx.step = lambda *args, **kwargs: calls.append(args)
    assert facade._bounded_recovery(tx, {})["reason"] == "source_count_limit"
    assert calls == []
