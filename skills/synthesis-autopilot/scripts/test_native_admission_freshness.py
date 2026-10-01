"""Protected consumers use bounded current replay; all histories are synthetic."""

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from test_native_replay_driver import original, values
from test_native_replay import (
    engine as engine,
    world as world,
    bridge as bridge,
    append,
    src,
)
from test_controller import (
    facade as facade,
    invoke,
    request,
    state_of,
    start_request,
    prepared_consumer,
)
from test_run_state import command

__all__ = ["engine", "world", "bridge", "facade"]


def tool_append(world, suffix="one"):
    session = world["actor"]["native_payload"]["session_id"]
    append(
        world,
        {
            "type": "assistant",
            "uuid": "call-" + suffix,
            "sessionId": session,
            "message": {
                "role": "assistant",
                "id": "message-" + suffix,
                "content": [
                    {
                        "type": "tool_use",
                        "id": "read-" + suffix,
                        "name": "Read",
                        "input": {"path": "synthetic"},
                    }
                ],
            },
        },
        {
            "type": "user",
            "uuid": "result-" + suffix,
            "sessionId": session,
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "read-" + suffix,
                        "content": "Synthetic result",
                        "is_error": False,
                    }
                ],
            },
        },
    )


def recovered(facade, engine, world, monkeypatch, *, large=False):
    state = original(world, facade, engine, monkeypatch, large=large)
    response = invoke(
        facade,
        world,
        request(
            "recover",
            values(facade, bytes=256 * 1024 * 1024),
            state,
            "recover-original",
        ),
    )
    assert response["coverage"]["replay_driver"]["status"] == "complete", response
    return state_of(world, response)


def intent(facade, state, identity="protected", **limits):
    req = request("next", {"mode": "start"}, state, identity)
    if limits:
        req["replay_limits"] = {**facade.REPLAY_DEFAULTS, **limits}
    return req


def effect_payload():
    return {
        "id": "write",
        "target": "fixture:target",
        "payload_digest": "a" * 64,
        "idempotency_key": "once",
        "authority_ref": "",
    }


def owned(facade, world, state, name, payload, identity="owned"):
    req = request(
        "record",
        {
            "kind": "protected_command",
            "command": name,
            "payload": payload,
            "command_id": identity,
        },
        state,
        identity,
    )
    return invoke(facade, world, req)


def test_large_recover_append_next_revalidates_complete_original_prefix(
    facade, engine, world, monkeypatch, bridge
):
    state = recovered(facade, engine, world, monkeypatch, large=True)
    before = deepcopy(state)
    assert world["transcript"].stat().st_size > 1024 * 1024
    tool_append(world)
    response = invoke(facade, world, intent(facade, state, bytes=256 * 1024 * 1024))
    final = state_of(world, response)
    assert response["status"] == "READY", response
    assert (
        final["extensions"]["workflow"]["graph"]["nodes"]["work"]["status"] == "running"
    )
    assert response["coverage"]["replay_driver"]["status"] == "complete"
    assert src(final)["history"] == src(before)["history"]
    assert src(final)["binding"]["generation"] == src(before)["binding"]["generation"]
    assert (
        bridge.current_invalidation(engine.inspect_context(final, world["actor"]))[
            "status"
        ]
        == "clear"
    )
    assert (
        final["extensions"]["workflow"]["budget"]
        == before["extensions"]["workflow"]["budget"]
    )
    assert final["effects"] == before["effects"]


@pytest.mark.parametrize("damage", ["rewrite-append", "cancel", "unknown"])
def test_admission_refuses_changed_prefix_or_new_authority(
    facade, engine, world, monkeypatch, damage
):
    state = recovered(facade, engine, world, monkeypatch)
    if damage == "rewrite-append":
        body = world["transcript"].read_bytes()
        assert b"custom-title" in body
        world["transcript"].write_bytes(
            body.replace(b"custom-title", b"custom-titlf", 1)
        )
        tool_append(world)
    elif damage == "cancel":
        append(
            world,
            {
                "type": "user",
                "uuid": "new-cancel",
                "sessionId": world["actor"]["native_payload"]["session_id"],
                "message": {"role": "user", "content": "Pause this task"},
            },
        )
    else:
        append(world, {"type": "unrecognized-native-authority", "trusted": True})
    response = invoke(facade, world, intent(facade, state))
    final = state_of(world, response)
    assert response["status"] == "UNRESOLVED", response
    assert (
        final["extensions"]["workflow"]["graph"]["nodes"]["work"]["status"] == "pending"
    )
    assert final["effects"] == state["effects"]
    if damage == "rewrite-append":
        assert src(final)["replay"]["status"] == "failed"
    # Never silently re-enroll after a failed replay.
    repeat = invoke(facade, world, intent(facade, final, "new-request"))
    assert repeat["status"] == "UNRESOLVED"
    assert state_of(world, repeat)["effects"] == state["effects"]


@pytest.mark.parametrize("limit", [{"steps": 1}, {"bytes": 1}, {"wall_millis": 1}])
def test_limited_request_cannot_replenish_same_intent(
    facade, engine, world, monkeypatch, limit
):
    state = recovered(facade, engine, world, monkeypatch)
    tool_append(world)
    req = intent(facade, state, **limit)
    response = invoke(facade, world, req)
    first = state_of(world, response)
    report = response["coverage"]["replay_driver"]
    assert response["status"] == "UNRESOLVED", response
    assert (
        first["extensions"]["workflow"]["graph"]["nodes"]["work"]["status"] == "pending"
    )
    again = invoke(facade, world, req)
    assert state_of(world, again) == first
    retained = again["coverage"]["replay_driver"]
    for field in ("steps", "validation_bytes_charged", "started_at", "deadline"):
        assert retained[field] == report[field]
    assert first["effects"] == state["effects"]


def test_interrupted_preflight_retains_committed_charges_and_can_resume(
    facade, engine, world, monkeypatch
):
    state = recovered(facade, engine, world, monkeypatch)
    tool_append(world)
    req = intent(facade, state, wall_millis=120000)
    apply = engine.apply_command
    fired = False

    def interrupted(*args, **kwargs):
        nonlocal fired
        result = apply(*args, **kwargs)
        binding = kwargs.get("request_binding", {})
        if (
            binding.get("request_id") == req["request_id"]
            and args[2] == "native.observe"
            and not fired
        ):
            fired = True
            raise OSError("synthetic interruption after charged durable observation")
        return result

    monkeypatch.setattr(engine, "apply_command", interrupted)
    response = invoke(facade, world, req)
    retained = state_of(world, response)
    assert fired and response["status"] == "UNRESOLVED"
    assert (
        retained["extensions"]["workflow"]["graph"]["nodes"]["work"]["status"]
        == "pending"
    )
    report = response["coverage"]["replay_driver"]
    monkeypatch.setattr(engine, "apply_command", apply)
    complete = invoke(facade, world, req)
    assert complete["status"] == "READY", complete
    final = state_of(world, complete)
    assert complete["coverage"]["replay_driver"]["started_at"] == report["started_at"]
    assert complete["coverage"]["replay_driver"]["steps"] > report["steps"]
    again = invoke(facade, world, req)
    assert state_of(world, again) == final


@pytest.mark.parametrize(
    "name,payload",
    [
        ("effect.prepare", effect_payload()),
        ("workflow.task", {"task_id": "work", "action": "start"}),
    ],
)
def test_actual_commit_refuses_mutation_after_preflight(
    facade, engine, world, monkeypatch, name, payload
):
    state = recovered(facade, engine, world, monkeypatch)
    tool_append(world)
    apply = engine.apply_command
    fired = False

    def mutate(*args, **kwargs):
        nonlocal fired
        if args[2] == name and not fired:
            fired = True
            body = world["transcript"].read_bytes()
            world["transcript"].write_bytes(
                body.replace(b"custom-title", b"custom-titlf", 1)
            )
            tool_append(world, "raced")
        return apply(*args, **kwargs)

    monkeypatch.setattr(engine, "apply_command", mutate)
    response = owned(facade, world, state, name, payload)
    final = state_of(world, response)
    assert fired and response["status"] == "UNRESOLVED", response
    assert final["effects"] == state["effects"]
    assert (
        final["extensions"]["workflow"]["graph"]["nodes"]["work"]["status"] == "pending"
    )


def test_real_cli_effect_preflight_keeps_idempotency_and_low_level_refusal(
    facade, engine, world, monkeypatch
):
    state = recovered(facade, engine, world, monkeypatch)
    tool_append(world)
    before = deepcopy(state)
    with pytest.raises(ValueError):
        command(engine, world, state, "effect.prepare", effect_payload())
    assert engine.load_run(world["project"], state["run_id"]) == before
    actor = world["scratch"] / "effect-actor.json"
    actor.write_text(json.dumps(world["actor"]))
    payload = world["scratch"] / "effect.json"
    payload.write_text(json.dumps(effect_payload()))
    limits = world["scratch"] / "limits.json"
    limits.write_text(json.dumps(facade.REPLAY_DEFAULTS))
    args = [
        sys.executable,
        str(Path(__file__).with_name("autopilot.py")),
        "command",
        "--project",
        str(world["project"]),
        "--actor",
        str(actor),
        "--run-id",
        state["run_id"],
        "--name",
        "effect.prepare",
        "--payload",
        str(payload),
        "--command-id",
        "cli-effect",
        "--expected-revision",
        str(state["revision"]),
        "--replay-limits",
        str(limits),
    ]
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "SYNTHESIS_AUTOPILOT_RUNTIME": str(world["runtime"])},
    )
    assert completed.returncode == 0, completed.stderr
    final = engine.load_run(world["project"], state["run_id"])
    assert final["effects"]["write"]["status"] == "prepared"
    assert any(
        row["command_id"] == "cli-effect"
        for row in engine._events(world["project"], state["run_id"])
    )
    repeated = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "SYNTHESIS_AUTOPILOT_RUNTIME": str(world["runtime"])},
    )
    assert repeated.returncode == 0, repeated.stderr
    assert engine.load_run(world["project"], state["run_id"]) == final


def test_readonly_and_stale_cas_never_reconcile(facade, engine, world, monkeypatch):
    state = recovered(facade, engine, world, monkeypatch)
    tool_append(world)
    view = invoke(
        facade, world, request("next", {"mode": "inspect"}, state, "readonly")
    )
    assert state_of(world, view) == state
    req = intent(facade, state)
    req["expected_revision"] -= 1
    assert invoke(facade, world, req)["status"] == "UNRESOLVED"
    assert state_of(world, view) == state
    req = request("next", {"mode": "inspect"}, state)
    req["replay_limits"] = deepcopy(facade.REPLAY_DEFAULTS)
    with pytest.raises(ValueError, match="protected mutation"):
        facade.validate_request(req)


def test_ordinary_nonreplayed_next_keeps_existing_owner_path(facade, world):
    state = state_of(world, invoke(facade, world, start_request(world)))
    tool_append(world)
    output = invoke(facade, world, intent(facade, state))
    final = state_of(world, output)
    assert output["status"] == "READY"
    assert "replay_driver" not in output["coverage"]
    assert "replay" not in src(final)
    assert not any(
        row["command"] == "recovery.admit"
        for row in facade.run_state._events(world["project"], final["run_id"])
    )


def force_replay(facade, engine, world, state):
    source = src(state)
    data = values(facade, bytes=256 * 1024 * 1024)
    data["source_reconciliations"] = [
        {
            "source_handle": "root",
            "prior_generation": source["binding"]["generation"],
            "prior_cursor_digest": engine._digest(source["cursor"]),
            "new_generation": None,
            "mode": "replay",
        }
    ]
    output = invoke(
        facade, world, request("recover", data, state, "explicit-original-replay")
    )
    assert output["coverage"]["replay_driver"]["status"] == "complete", output
    return state_of(world, output)


def test_actual_finish_after_replay_and_append_keeps_quality_gate(
    facade, engine, world
):
    state, _ = prepared_consumer(facade, world)
    state = force_replay(facade, engine, world, state)
    tool_append(world)
    output = invoke(
        facade,
        world,
        request("finish", {"disposition": "completed"}, state, "finish-replayed"),
    )
    assert output["status"] == "COMPLETED", output
    assert output["coverage"]["replay_driver"]["status"] == "complete"
    assert (
        state_of(world, output)["extensions"]["workflow"]["graph"]["nodes"]["work"][
            "status"
        ]
        == "done"
    )


def test_actual_dispatch_after_replay_and_append_retains_exact_admission(
    facade, engine, world, monkeypatch
):
    state = recovered(facade, engine, world, monkeypatch)
    for identity, category in (
        ("worker", "work"),
        ("audit", "integration"),
        ("verify", "verification"),
        ("recover", "recovery"),
    ):
        state = command(
            engine,
            world,
            state,
            "workflow.reserve",
            {
                "reservation_id": identity,
                "amounts": {"model_tokens": 100},
                "category": category,
            },
        )
    root = world["project"] / "delegated"
    for sub in ("output", "scratch"):
        (root / sub).mkdir(parents=True)
    brief = {
        "child_id": "native-child",
        "task_id": "work",
        "deliverables": ["Produce reviewed output"],
        "paths": [str(root)],
        "criteria": ["accept"],
        "reservation_id": "worker",
        "integration_reservation_id": "audit",
        "verification_reservation_id": "verify",
        "recovery_reservation_id": "recover",
        "integration_owner": state["owner"]["session_uuid"],
        "return_contract": ["artifact_ids", "evidence_ids", "disposition"],
        "cancellation": "Retain partial evidence and return",
        "mode": "native-cli",
        "client": "claude",
        "required_capabilities": ["read", "write", "edit", "shell"],
        "file_contract": {
            "schema_version": 1,
            "immutable_inputs": [],
            "output_roots": [str(root / "output")],
            "scratch_root": str(root / "scratch"),
        },
        "admission_id": "parent",
        "admission_requests": [
            {"id": "parent", "actor": world["actor"], "paths": [str(root)]}
        ],
    }
    tool_append(world)
    with pytest.raises(ValueError):
        command(engine, world, state, "workflow.dispatch", brief)
    output = owned(
        facade, world, state, "workflow.dispatch", brief, "dispatch-after-append"
    )
    assert output["status"] == "RECORDED", output
    child = state_of(world, output)["extensions"]["workflow"]["children"][
        "native-child"
    ]
    assert child["producer"] is None and child["authority_granted"] is False
    assert child["file_contract"] == brief["file_contract"]


@pytest.mark.parametrize(
    "command_name,payload",
    [
        ("workflow.dispatch", {}),
        ("workflow.attempt", {}),
        ("workflow.progress", {}),
        ("workflow.task", {"action": "start"}),
        ("effect.prepare", {}),
        ("close", {"status": "completed"}),
        ("native.launch.prepare", {}),
        ("observe:native_worker", {}),
        ("recovery.instructions", {}),
        ("supervision.action", {"action": "request"}),
    ],
)
def test_existing_protected_route_inventory(facade, command_name, payload):
    assert facade.protected_command(command_name, payload)


@pytest.mark.parametrize(
    "command_name,payload",
    [
        ("close", {"status": "cancelled"}),
        ("workflow.task", {"action": "cancel"}),
        ("native.launch.cancel", {}),
        ("supervision.action", {"action": "stop"}),
        ("unknown-grant", {}),
    ],
)
def test_cleanup_and_unknown_routes_cannot_be_wrapped_as_authority(
    facade, world, command_name, payload
):
    req = request(
        "record",
        {
            "kind": "protected_command",
            "command": command_name,
            "payload": payload,
            "command_id": "unsafe",
        },
        {"run_id": "10000000-0000-4000-8000-000000000001", "revision": 1},
    )
    with pytest.raises(ValueError):
        facade.validate_request(req)


def test_refresh_more_than_generation_capacity_preserves_actual_lineage(
    facade, engine, world, monkeypatch, bridge
):
    """Cheap exact owner-stage control; actual journal admission is tested above."""
    state = recovered(facade, engine, world, monkeypatch)
    initial = deepcopy(src(state))
    context = engine.inspect_context(state, world["actor"], project=world["project"])
    context.update(project=world["project"], actor=world["actor"])
    session = world["actor"]["native_payload"]["session_id"]
    for number in range(bridge.MAX_GENERATIONS + 2):
        append(
            world,
            {
                "type": "custom-title",
                "sessionId": session,
                "customTitle": "benign-" + str(number),
            },
        )
        context["state"] = state
        source = src(state)
        prepared = bridge._begin_refresh(context, "root", source, source)
        source = prepared["source"]
        assert source["replay"].get("mode") == "refresh"
        state["extensions"]["native_observations"]["sources"]["root"] = source
        for _ in range(len(source["ranges"]) + 4):
            context["state"] = state
            prepared = bridge._prepare_replay_page(context, "root", src(state))
            state = bridge._reduce_replay_page(state, prepared, context)
            if src(state)["replay"]["status"] != "pending":
                break
        assert src(state)["replay"]["status"] == "complete", src(state)["replay"].get(
            "failure"
        )
        assert src(state)["binding"] == initial["binding"]
        assert src(state)["history"] == initial["history"]
        assert src(state)["replay"]["aliases"] == initial["replay"]["aliases"]
    assert src(state)["replay"]["refresh_count"] == bridge.MAX_GENERATIONS + 2
    (world["scratch"] / "generation-capacity-result.json").write_text(
        json.dumps(
            {
                "cycles": bridge.MAX_GENERATIONS + 2,
                "history_entries": len(src(state)["history"]),
                "generation_unchanged": True,
                "scope": "actual replay stages with synthetic context, not native acceptance",
            },
            indent=2,
        )
    )


def test_measured_large_protected_preflight_reads_each_prefix_range_once(
    facade, engine, world, monkeypatch, bridge
):
    import time

    state = recovered(facade, engine, world, monkeypatch, large=True)
    tool_append(world)
    stable_read = bridge.native._stable_read
    reads = []

    def measured(*args, **kwargs):
        value = stable_read(*args, **kwargs)
        if Path(args[1]) == world["transcript"]:
            reads.append({"offset": args[2], "length": args[3]})
        return value

    monkeypatch.setattr(bridge.native, "_stable_read", measured)
    started = time.monotonic()
    response = invoke(facade, world, intent(facade, state, bytes=256 * 1024 * 1024))
    elapsed = time.monotonic() - started
    assert response["status"] == "READY", response
    original_ranges = src(state)["ranges"]
    for witness in original_ranges:
        assert (
            sum(
                row == {"offset": witness["offset"], "length": witness["length"]}
                for row in reads
            )
            == 1
        )
    result = {
        "source_bytes": world["transcript"].stat().st_size,
        "wall_seconds": elapsed,
        "stable_read_requested_bytes": sum(row["length"] for row in reads),
        "stable_read_calls": reads,
        "conservative_driver": response["coverage"]["replay_driver"],
        "metric_boundary": "native stable-read requests; excludes header, PM, journal and setup I/O",
    }
    (world["scratch"] / "measured-admission.json").write_text(
        json.dumps(result, indent=2)
    )
    assert result["stable_read_requested_bytes"] < result["source_bytes"] * 4


def test_successor_index_collision_cannot_hide_authenticated_predecessor_batch(
    facade, engine, world, monkeypatch, bridge
):
    from test_successor_transaction import intent as successor_intent, advance

    state = recovered(facade, engine, world, monkeypatch)
    tool_append(world)
    state = command(
        engine,
        world,
        state,
        "native.observe",
        {
            "source_handle": "root",
            "through_event": None,
            "task_id": None,
            "attempt_id": None,
        },
    )
    extension = state["extensions"]["native_observations"]
    event_id = next(iter(extension["event_index"]))
    index = deepcopy(extension["event_index"][event_id])
    expected, _ = bridge._indexed_batch(
        {
            **engine.inspect_context(state, world["actor"]),
            "state": state,
            "project": world["project"],
        },
        index,
        max_bytes=8 * 1024 * 1024,
    )

    # Current schema accepts historical projections without this optional cache.
    # Preserve the authenticated event/index; only the latest-cache absence is synthetic.
    def historical_cache_absence(current, payload, context):
        current["extensions"]["native_observations"].pop("latest_batch", None)
        return current

    engine.register_command(
        "fixture.historical_cache_absence",
        historical_cache_absence,
        allowed_fields=("extensions",),
    )
    state = command(engine, world, state, "fixture.historical_cache_absence", {})
    old = command(
        engine,
        world,
        state,
        "close",
        {"status": "incomplete", "reason": "Bounded fixture interval"},
    )
    newer = advance(engine, world, successor_intent(engine, world, old))
    while newer["revision"] <= index["revision"]:
        newer = command(
            engine,
            world,
            newer,
            "progress",
            {"summary": "Unrelated successor narration"},
        )
    context = {
        **engine.inspect_context(newer, world["actor"]),
        "state": newer,
        "project": world["project"],
    }
    found, charged = bridge._indexed_batch(context, index, max_bytes=8 * 1024 * 1024)
    assert found == expected and charged > 0
    assert engine.load_run(world["project"], old["run_id"]) == old
    with pytest.raises(ValueError):
        bridge._indexed_batch(
            context, {**index, "batch_digest": "f" * 64}, max_bytes=8 * 1024 * 1024
        )
    with pytest.raises(ValueError):
        bridge._indexed_batch(context, index, max_bytes=1)


@pytest.mark.parametrize("encoded", [False, True])
def test_absent_journal_component_retains_cost_but_corruption_never_routes(
    tmp_path, encoded
):
    import journal_storage as storage

    home = tmp_path / "resources/autopilot-runs/10000000-0000-4000-8000-000000000009"
    path = home / "events/000000000001.json"
    path.parent.mkdir(parents=True)
    value = {"state": {"extensions": {"unrelated": "x" * (2100000 if encoded else 7)}}}
    if encoded:
        raw, blocks = storage.encode(value)
        storage.materialize(home, blocks)
        path.write_bytes(raw)
    else:
        path.write_text(json.dumps(value))
    with pytest.raises(storage.ComponentAbsent) as caught:
        storage.component(
            path,
            ("state", "extensions", "native_observations", "latest_batch"),
            max_bytes=8 * 1024 * 1024,
        )
    assert 0 < caught.value.charged_bytes < 8 * 1024 * 1024
    with pytest.raises(ValueError) as limited:
        storage.component(
            path,
            ("state", "extensions", "native_observations", "latest_batch"),
            max_bytes=1,
        )
    assert not isinstance(limited.value, storage.ComponentAbsent)
    original = path.with_name("preserved-original.json")
    path.rename(original)
    with pytest.raises((OSError, ValueError)) as absent:
        storage.component(
            path,
            ("state", "extensions", "native_observations", "latest_batch"),
            max_bytes=8 * 1024 * 1024,
        )
    assert not isinstance(absent.value, storage.ComponentAbsent)
    path.write_bytes(b"{invalid")
    with pytest.raises(ValueError) as corrupted:
        storage.component(
            path,
            ("state", "extensions", "native_observations", "latest_batch"),
            max_bytes=8 * 1024 * 1024,
        )
    assert not isinstance(corrupted.value, storage.ComponentAbsent)
