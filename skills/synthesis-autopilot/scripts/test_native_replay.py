"""Synthetic full-interval replay through real admitted journal owners."""

from copy import deepcopy
import pytest
import native_claude as adapter
import native_observations as native
from test_run_state import engine as engine, world as world, create, command
from test_observation_bridge import bridge as bridge, enroll, observe, append, reconcile
from test_native_claude_context import record
from test_controller import facade as facade

__all__ = ["engine", "world", "bridge", "facade"]


def broken_history(
    engine, world, monkeypatch, *, cancel=False, rows=1, extra=(), separate_cancel=False
):
    decode = adapter.decode_record
    version = adapter.ADAPTER_VERSION

    def prior(row, *args, **kwargs):
        if row.get("type") == "custom-title":
            raise adapter.DialectError("retained synthetic prior grammar gap")
        return decode(row, *args, **kwargs)

    monkeypatch.setattr(adapter, "ADAPTER_VERSION", "synthetic-prior")
    monkeypatch.setattr(adapter, "decode_record", prior)
    state = enroll(engine, world, create(engine, world))
    session = world["actor"]["native_payload"]["session_id"]
    if cancel:
        append(
            world,
            {
                "type": "user",
                "uuid": "original-cancel",
                "sessionId": session,
                "message": {"role": "user", "content": "Pause original task"},
            },
        )
    if cancel and separate_cancel:
        state = observe(engine, world, state)
    append(
        world,
        *(
            record("custom-title", session, "synthetic inert title")
            for _ in range(rows)
        ),
    )
    append(world, *extra)
    for _ in range(100):
        state = observe(engine, world, state)
        if (
            state["extensions"]["native_observations"]["sources"]["root"]["cursor"][
                "offset"
            ]
            == world["transcript"].stat().st_size
        ):
            break
    assert (
        state["extensions"]["native_observations"]["sources"]["root"]["cursor"][
            "first_gap"
        ]
        is not None
    )
    monkeypatch.setattr(adapter, "ADAPTER_VERSION", version)
    monkeypatch.setattr(adapter, "decode_record", decode)
    return state


def replay_to_end(engine, world, state, limit=100):
    state = reconcile(engine, world, state)
    for _ in range(limit):
        source = state["extensions"]["native_observations"]["sources"]["root"]
        if source.get("replay", {}).get("status") in {"complete", "failed"}:
            return state
        state = observe(engine, world, state)
        assert engine.load_run(world["project"], state["run_id"]) == state
    pytest.fail("bounded replay did not finish")


@pytest.mark.parametrize("cancel", [False, True])
def test_complete_original_replay_preserves_invalidation_and_original_gap(
    bridge, engine, world, monkeypatch, cancel
):
    state = broken_history(engine, world, monkeypatch, cancel=cancel)
    original = deepcopy(state)
    state = replay_to_end(engine, world, state)
    source = state["extensions"]["native_observations"]["sources"]["root"]
    assert source["replay"]["status"] == "complete"
    checked = bridge.current_invalidation(engine.inspect_context(state, world["actor"]))
    assert checked["status"] == ("invalidated" if cancel else "clear"), checked
    assert (
        checked["pre_enrollment"] == "UNKNOWN" and checked["authority_granted"] is False
    )
    assert (
        source["history"][-1]["cursor"]
        == original["extensions"]["native_observations"]["sources"]["root"]["cursor"]
    )
    assert (
        original["extensions"]["native_observations"]["invalidation_index"].items()
        <= state["extensions"]["native_observations"]["invalidation_index"].items()
    )
    assert state["effects"] == original["effects"] and state["status"] != "completed"


def src(state):
    return state["extensions"]["native_observations"]["sources"]["root"]


def drain(engine, world, state):
    for _ in range(80):
        if src(state)["replay"]["status"] in {"complete", "failed"}:
            return state
        state = observe(engine, world, state)
    pytest.fail("finite replay drain exhausted")


@pytest.mark.parametrize("steps", [0, 1, 2, 3])
def test_cold_journal_resume_and_repeated_operation_are_idempotent(
    bridge, engine, world, monkeypatch, steps
):
    state = reconcile(
        engine, world, broken_history(engine, world, monkeypatch, cancel=True)
    )
    for _ in range(steps):
        before = deepcopy(state)
        state = observe(
            engine, world, state, command_id=f"replay-step-{steps}-{state['revision']}"
        )
        assert (
            observe(
                engine,
                world,
                before,
                command_id=f"replay-step-{steps}-{before['revision']}",
            )
            == state
        )
        assert (
            bridge.current_invalidation(engine.inspect_context(state, world["actor"]))[
                "status"
            ]
            != "clear"
        )
        state = engine.load_run(world["project"], state["run_id"])
    state = drain(engine, world, state)
    assert src(state)["replay"]["status"] == "complete"
    assert (
        bridge.current_invalidation(engine.inspect_context(state, world["actor"]))[
            "status"
        ]
        == "invalidated"
    )


@pytest.mark.parametrize(
    "fault",
    [
        "old-bytes",
        "new-bytes",
        "append",
        "truncated",
        "removed",
        "rotation",
        "symlink",
        "chmod",
        "hardlink",
    ],
)
def test_changed_source_at_each_retained_stage_cannot_supply_clear(
    bridge, engine, world, monkeypatch, fault
):
    state = broken_history(engine, world, monkeypatch, cancel=True)
    state = reconcile(engine, world, state)
    state = observe(
        engine, world, state
    )  # one raw witness admitted, not the whole interval
    path = world["transcript"]
    raw = path.read_bytes()
    if fault == "old-bytes":
        path.write_bytes(raw.replace(b"Pause original", b"Allow original"))
    elif fault == "new-bytes":
        path.write_bytes(raw.replace(b"synthetic inert", b"rewritten inert"))
    elif fault == "append":
        append(world, record("mode", world["actor"]["native_payload"]["session_id"]))
    elif fault == "truncated":
        path.write_bytes(raw[:-1])
    elif fault in {"removed", "rotation", "symlink"}:
        moved = path.with_name("retained-original.jsonl")
        path.rename(moved)
        if fault == "rotation":
            path.write_bytes(raw)
        elif fault == "symlink":
            path.symlink_to(moved)
    elif fault == "chmod":
        path.chmod(0o600 if path.stat().st_mode & 0o777 != 0o600 else 0o640)
    elif fault == "hardlink":
        import os

        os.link(path, path.with_name("alias.jsonl"))
    if fault in {"removed", "symlink"}:
        with pytest.raises(ValueError, match="admission|missing|unsafe"):
            observe(engine, world, state)
        assert engine.load_run(world["project"], state["run_id"]) == state
        return
    failed = observe(engine, world, state)
    assert src(failed)["replay"]["status"] == "failed"
    assert (
        bridge.current_invalidation(engine.inspect_context(failed, world["actor"]))[
            "status"
        ]
        == "unknown"
    )
    assert src(failed)["cursor"] == src(state)["cursor"]
    again = reconcile(engine, world, failed)
    assert src(again)["replay"] == src(failed)["replay"]  # no retry loop


@pytest.mark.parametrize(
    "fault", ["missing", "changed", "foreign", "unknown", "oversized"]
)
def test_decoder_cannot_erase_or_reinterpret_original_semantics(
    bridge, engine, world, monkeypatch, fault
):
    state = broken_history(engine, world, monkeypatch, cancel=True)
    decode = adapter.decode_record

    def altered(row, *args, **kwargs):
        facts = decode(row, *args, **kwargs)
        if row.get("type") == "user":
            if fault == "missing":
                return []
            if fault == "changed":
                facts[0]["data"] = {"invented": "new meaning"}
            if fault == "foreign":
                raise adapter.DialectError("foreign native identity")
        if row.get("type") == "custom-title" and fault in {"unknown", "oversized"}:
            raise adapter.DialectError("unsupported/oversized retained record")
        return facts

    monkeypatch.setattr(adapter, "decode_record", altered)
    result = replay_to_end(engine, world, state)
    assert src(result)["replay"]["status"] == "failed"
    assert (
        result["extensions"]["native_observations"]["invalidation_index"]
        == state["extensions"]["native_observations"]["invalidation_index"]
    )
    assert (
        bridge.current_invalidation(engine.inspect_context(result, world["actor"]))[
            "status"
        ]
        == "unknown"
    )


def test_permission_refusal_retains_cursor_and_has_no_new_effect(
    bridge, engine, world, monkeypatch
):
    state = reconcile(engine, world, broken_history(engine, world, monkeypatch))
    opened = native._open

    def denied(path, binding=None):
        if str(path) == str(world["transcript"]):
            raise PermissionError("synthetic read refusal")
        return opened(path, binding)

    monkeypatch.setattr(native, "_open", denied)
    result = observe(engine, world, state)
    assert src(result)["replay"]["status"] == "failed"
    assert src(result)["cursor"] == src(state)["cursor"]
    assert result["effects"] == state["effects"]


def test_concurrent_mutation_during_last_read_stays_unknown(
    bridge, engine, world, monkeypatch
):
    state = reconcile(engine, world, broken_history(engine, world, monkeypatch))
    while src(state)["replay"]["phase"] != "decode":
        state = observe(engine, world, state)
    read = native.read_page

    def raced(*args, **kwargs):
        page = read(*args, **kwargs)
        path = world["transcript"]
        path.write_bytes(
            path.read_bytes().replace(b"synthetic inert", b"rewritten inert")
        )
        return page

    monkeypatch.setattr(native, "read_page", raced)
    result = observe(engine, world, state)
    assert src(result)["replay"]["status"] == "failed"
    assert (
        bridge.current_invalidation(engine.inspect_context(result, world["actor"]))[
            "status"
        ]
        == "unknown"
    )


def test_complete_replay_does_not_certify_later_old_range_mutation(
    bridge, engine, world, monkeypatch
):
    state = replay_to_end(engine, world, broken_history(engine, world, monkeypatch))
    assert src(state)["replay"]["status"] == "complete"
    path = world["transcript"]
    path.write_bytes(path.read_bytes().replace(b"synthetic inert", b"rewritten inert"))
    assert (
        bridge.current_invalidation(engine.inspect_context(state, world["actor"]))[
            "status"
        ]
        == "unknown"
    )
    # Reopening recovery cannot certify changed old hashes.
    failed = drain(engine, world, reconcile(engine, world, state))
    assert src(failed)["replay"]["status"] == "failed"


@pytest.mark.parametrize(
    "field",
    ["prior_generation", "prior_cursor_digest", "new_generation", "start_offset"],
)
def test_explicit_replay_refuses_wrong_or_skipped_frontier(
    bridge, engine, world, monkeypatch, field
):
    state = broken_history(engine, world, monkeypatch)
    spec = {
        "prior_generation": src(state)["binding"]["generation"],
        "prior_cursor_digest": native._digest(src(state)["cursor"]),
        "new_generation": None,
        "mode": "replay",
    }
    spec[field] = 1 if field == "start_offset" else "0" * 64
    with pytest.raises(ValueError):
        reconcile(engine, world, state, spec)
    assert engine.load_run(world["project"], state["run_id"]) == state


def test_original_range_tampering_before_start_is_not_reconciled(
    bridge, engine, world, monkeypatch
):
    state = broken_history(engine, world, monkeypatch)
    path = world["transcript"]
    path.write_bytes(path.read_bytes().replace(b"synthetic inert", b"rewritten inert"))
    result = replay_to_end(engine, world, state)
    assert src(result)["replay"]["status"] == "failed"


def test_unchanged_large_interval_progresses_in_finite_chunks(
    bridge, engine, world, monkeypatch
):
    # Actual original ranges exceed the old all-at-once continuity ceiling.
    decode = adapter.decode_record
    version = adapter.ADAPTER_VERSION
    monkeypatch.setattr(adapter, "ADAPTER_VERSION", "synthetic-prior")
    state = enroll(engine, world, create(engine, world))
    session = world["actor"]["native_payload"]["session_id"]
    for i in range(25):
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
    while src(state)["cursor"]["offset"] < world["transcript"].stat().st_size:
        state = observe(engine, world, state)
    monkeypatch.setattr(adapter, "ADAPTER_VERSION", version)
    monkeypatch.setattr(adapter, "decode_record", decode)
    original = deepcopy(state)
    result = replay_to_end(engine, world, state)
    assert src(result)["replay"]["status"] == "complete"
    assert (
        src(result)["replay"]["frontier"] - src(result)["replay"]["original_offset"]
        > 1024 * 1024
    )
    assert len(src(result)["ranges"]) >= 2
    assert (
        bridge.current_invalidation(engine.inspect_context(result, world["actor"]))[
            "status"
        ]
        == "clear"
    )
    assert (
        result["extensions"]["native_observations"]["projection"]["events"]
        == original["extensions"]["native_observations"]["projection"]["events"]
    )


@pytest.mark.parametrize("cancel", [False, True])
def test_real_controller_recovery_preserves_costs_and_user_precedence(
    bridge, engine, world, monkeypatch, facade, cancel
):
    from test_controller import invoke, request, start_request, state_of
    from test_resource_policy import _claude_usage

    decode, version = adapter.decode_record, adapter.ADAPTER_VERSION
    monkeypatch.setattr(adapter, "ADAPTER_VERSION", "synthetic-controller-prior")

    def prior(row, *args, **kwargs):
        if row.get("type") == "custom-title":
            raise adapter.DialectError("synthetic original gap")
        return decode(row, *args, **kwargs)

    monkeypatch.setattr(adapter, "decode_record", prior)
    started = invoke(facade, world, start_request(world))
    assert started["status"] == "READY", started
    state = state_of(world, started)
    _claude_usage(world, amount=17)
    session = world["actor"]["native_payload"]["session_id"]
    if cancel:
        append(
            world,
            {
                "type": "user",
                "uuid": "controller-pause",
                "sessionId": session,
                "message": {"role": "user", "content": "Pause original instruction"},
            },
        )
    append(world, record("custom-title", session))
    state = observe(engine, world, state)
    budget = deepcopy(state["extensions"]["workflow"]["budget"])
    assert len(budget["native_usage"]["measurements"]) == 1
    original = deepcopy(state)
    monkeypatch.setattr(adapter, "ADAPTER_VERSION", version)
    monkeypatch.setattr(adapter, "decode_record", decode)
    for number in range(16):
        result = invoke(
            facade,
            world,
            request(
                "recover",
                {"reconcile_sources": True},
                state,
                f"replay-recovery-{number}",
            ),
        )
        assert result["status"] in {"READY", "UNRESOLVED", "RECONCILE"}, result
        state = state_of(world, result)
        if src(state).get("replay", {}).get("status") == "complete":
            break
    assert src(state)["replay"]["status"] == "complete", result
    assert state["extensions"]["workflow"]["budget"] == budget
    current = bridge.current_invalidation(engine.inspect_context(state, world["actor"]))
    assert current["status"] == ("invalidated" if cancel else "clear"), current
    assert (
        state["effects"] == original["effects"]
        and state["status"] == original["status"]
    )
    assert state["contract_digest"] == original["contract_digest"]
    assert (
        state["extensions"]["workflow"]["children"]
        == original["extensions"]["workflow"]["children"]
    )


def test_known_conflicting_pair_is_not_promoted_by_replay(
    bridge, engine, world, monkeypatch
):
    from test_observation_bridge import pair

    version = adapter.ADAPTER_VERSION
    monkeypatch.setattr(adapter, "ADAPTER_VERSION", "synthetic-prior-pairs")
    state = enroll(engine, world, create(engine, world))
    append(world, *pair(world), *pair(world, output="contradiction"))
    state = observe(engine, world, state)
    ids = [
        e["event_id"]
        for e in state["extensions"]["native_observations"]["latest_batch"]["events"]
    ]
    projection = deepcopy(state["extensions"]["native_observations"]["projection"])
    monkeypatch.setattr(adapter, "ADAPTER_VERSION", version)
    state = replay_to_end(engine, world, state)
    assert src(state)["replay"]["status"] == "complete"
    assert (
        state["extensions"]["native_observations"]["projection"]["pairs"]
        == projection["pairs"]
    )
    with pytest.raises(ValueError, match="contradiction"):
        engine.inspect_context(state, world["actor"])["current_native_events"](ids)


def test_original_epoch_or_ancestor_alias_is_not_a_decoder_upgrade(
    bridge, engine, world, monkeypatch
):
    state = broken_history(engine, world, monkeypatch)
    path = world["transcript"]
    directory = path.parent
    retained = directory.with_name("retained-source-directory")
    directory.rename(retained)
    directory.symlink_to(retained, target_is_directory=True)
    with pytest.raises(ValueError, match="aliased|unsafe|admission"):
        reconcile(engine, world, state)
    assert engine.load_run(world["project"], state["run_id"]) == state


@pytest.mark.parametrize("fault", ["foreign", "unknown", "oversized"])
def test_actual_unsupported_record_replay_remains_unknown(
    bridge, engine, world, monkeypatch, fault
):
    session = world["actor"]["native_payload"]["session_id"]
    row = record(
        "custom-title",
        "foreign" if fault == "foreign" else session,
        "x" * (1024 * 1024 + 100) if fault == "oversized" else "fixture",
    )
    if fault == "unknown":
        row["type"] = "future-unsupported-record"
    if fault == "foreign":
        state = enroll(engine, world, create(engine, world))
        append(world, row)
        with pytest.raises(ValueError, match="unambiguously|admission"):
            observe(engine, world, state)
        assert engine.load_run(world["project"], state["run_id"]) == state
        return
    state = broken_history(engine, world, monkeypatch, extra=[row])
    result = replay_to_end(engine, world, state)
    assert src(result)["replay"]["status"] == "failed"
    assert src(result)["replay"]["failed_batch"]["gaps"]
    assert (
        bridge.current_invalidation(engine.inspect_context(result, world["actor"]))[
            "status"
        ]
        == "unknown"
    )


def test_exact_source_is_rechecked_at_commit_and_read_boundaries(
    bridge, engine, world, monkeypatch
):
    state = broken_history(engine, world, monkeypatch)
    state = reconcile(engine, world, state)
    while src(state)["replay"]["phase"] != "decode":
        state = observe(engine, world, state)
    append_event = engine._append

    def raced(*args, **kwargs):
        path = world["transcript"]
        path.write_bytes(
            path.read_bytes().replace(b"synthetic inert", b"rewritten inert")
        )
        return append_event(*args, **kwargs)

    monkeypatch.setattr(engine, "_append", raced)
    result = observe(engine, world, state)
    # Journaled historical completion is not a current readback proof.
    assert (
        bridge.current_invalidation(engine.inspect_context(result, world["actor"]))[
            "status"
        ]
        == "unknown"
    )


def test_replayed_generation_keeps_original_cancelled_run_terminal(
    bridge, engine, world, monkeypatch
):
    state = broken_history(engine, world, monkeypatch, cancel=True)
    state = command(
        engine,
        world,
        state,
        "close",
        {"status": "cancelled", "reason": "Actual user cancellation"},
    )
    with pytest.raises(ValueError):
        reconcile(engine, world, state)
    assert engine.load_run(world["project"], state["run_id"]) == state
    assert state["status"] == "cancelled"


def test_retained_history_range_hashes_cannot_be_replaced_by_new_interval(
    bridge, engine, world, monkeypatch
):
    state = broken_history(engine, world, monkeypatch)
    original = deepcopy(state)
    # An explicit historical interval was previously accepted as UNKNOWN.
    from test_observation_bridge import reconciliation_spec

    state = reconcile(
        engine,
        world,
        state,
        reconciliation_spec(
            src(state), mode="interval", start_offset=src(state)["enrollment"]["offset"]
        ),
    )
    path = world["transcript"]
    path.write_bytes(path.read_bytes().replace(b"synthetic inert", b"rewritten inert"))
    state = observe(engine, world, state)
    spec = reconciliation_spec(src(state), mode="replay")
    result = drain(engine, world, reconcile(engine, world, state, spec))
    assert src(result)["replay"]["status"] == "failed"
    assert src(result)["history"][0]["ranges"] == src(original)["ranges"]


def test_partial_original_frame_cannot_gain_full_interval_coverage(
    bridge, engine, world, monkeypatch
):
    version = adapter.ADAPTER_VERSION
    monkeypatch.setattr(adapter, "ADAPTER_VERSION", "synthetic-partial-prior")
    state = enroll(engine, world, create(engine, world))
    with world["transcript"].open("ab") as stream:
        stream.write(b'{"type":"custom-title"')
    with pytest.raises(ValueError, match="unambiguously|admission"):
        observe(engine, world, state)
    monkeypatch.setattr(adapter, "ADAPTER_VERSION", version)
    with pytest.raises(ValueError, match="unambiguously|admission"):
        reconcile(engine, world, state)
    assert engine.load_run(world["project"], state["run_id"]) == state


def test_cold_replay_keeps_journal_commit_after_projection_interruption(
    bridge, engine, world, monkeypatch
):
    state = reconcile(
        engine, world, broken_history(engine, world, monkeypatch, cancel=True)
    )
    project = engine._project

    def interrupted(*args, **kwargs):
        raise OSError("synthetic interrupted projection after journal commit")

    monkeypatch.setattr(engine, "_project", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        observe(engine, world, state, command_id="interrupted-replay-page")
    monkeypatch.setattr(engine, "_project", project)
    committed = engine.load_run(world["project"], state["run_id"])
    assert committed["revision"] == state["revision"] + 1
    assert (
        observe(engine, world, state, command_id="interrupted-replay-page") == committed
    )
    result = drain(engine, world, committed)
    assert src(result)["replay"]["status"] == "complete"
    assert (
        bridge.current_invalidation(engine.inspect_context(result, world["actor"]))[
            "status"
        ]
        == "invalidated"
    )


def test_replay_after_real_successor_reads_original_journal_and_keeps_costs(
    bridge, engine, world, monkeypatch
):
    from test_successor_transaction import intent, advance
    from datetime import datetime, timezone, timedelta
    import workflow

    workflow.register_commands(engine.register_command)
    state = broken_history(
        engine, world, monkeypatch, cancel=True, separate_cancel=True
    )
    state = command(
        engine,
        world,
        state,
        "workflow.configure",
        {
            "dimensions": {
                "domains": ["software"],
                "uncertainty": "low",
                "effect": "local-reversible",
                "horizon": "session",
                "parallelizable": False,
            }
        },
    )
    state = command(
        engine,
        world,
        state,
        "workflow.budget",
        {
            "limits": {"model_tokens": {"limit": 1000000, "enforcement": "forecast"}},
            "deadline": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
    )
    state = command(
        engine,
        world,
        state,
        "workflow.reserve",
        {
            "reservation_id": "original-cost",
            "category": "work",
            "amounts": {"model_tokens": 53},
        },
    )
    state = command(
        engine,
        world,
        state,
        "workflow.settle",
        {"reservation_id": "original-cost", "actual": None},
    )
    old = command(
        engine,
        world,
        state,
        "close",
        {"status": "incomplete", "reason": "Original bounded interval ended"},
    )
    state = advance(engine, world, intent(engine, world, old))
    result = replay_to_end(engine, world, state)
    assert src(result)["replay"]["status"] == "complete", src(result)["replay"].get(
        "failure"
    )
    verdict = bridge.current_invalidation(
        engine.inspect_context(result, world["actor"])
    )
    assert verdict["status"] == "invalidated", verdict
    assert engine.load_run(world["project"], old["run_id"]) == old
    before, after = (
        deepcopy(old["extensions"]["workflow"]["budget"]),
        deepcopy(result["extensions"]["workflow"]["budget"]),
    )
    before.pop("deadline")
    after.pop("deadline")
    assert before == after and result["effects"] == old["effects"]


# Original history may end inside a complete on-disk frame, or retain an
# unconsumed tail enrollment before an explicitly selected earlier interval.
def original_cursor_shape(engine, world, monkeypatch, shape):
    from test_observation_bridge import pair, reconciliation_spec
    with monkeypatch.context() as prior:
        prior.setattr(adapter, "ADAPTER_VERSION", "synthetic-prior")
        header = world["transcript"].stat().st_size
        if shape == "unequal":
            append(world, *pair(world, "earlier"))
        state = enroll(engine, world, create(engine, world))
        if shape == "unequal":
            state = reconcile(engine, world, state,
                reconciliation_spec(src(state), "interval", start_offset=header))
        else:
            append(world, *pair(world, "prefix"))
            for index in range(6):
                append(world, {"type": "assistant", "sessionId": world["actor"]["native_payload"]["session_id"],
                    "message": {"role": "assistant", "content": [{"type": "text", "text": str(index) * 200000}]}})
        state = observe(engine, world, state)
    return state


@pytest.mark.parametrize("shape", ["partial", "unequal"])
def test_original_cursor_shapes_replay_without_discarding_history(bridge, engine, world, monkeypatch, shape):
    state = original_cursor_shape(engine, world, monkeypatch, shape)
    original = deepcopy(state)
    state = replay_to_end(engine, world, state)
    assert src(state)["replay"]["status"] == "complete"
    assert src(state)["cursor"]["offset"] == src(original)["cursor"]["offset"]
    assert src(state)["history"][-1]["cursor"] == src(original)["cursor"]
    assert src(state)["history"][:len(src(original)["history"])] == src(original)["history"]
    assert state["effects"] == original["effects"]
    if shape == "partial":
        assert src(state)["cursor"]["pending"] == src(original)["cursor"]["pending"]
        assert src(state)["replay"]["pending_bytes"] > 0
        # Actual owner refresh completes the same frame under the new decoder.
        state = replay_to_end(engine, world, state)
        assert src(state)["cursor"]["offset"] == world["transcript"].stat().st_size
        assert src(state)["cursor"]["frame_start"] == src(state)["cursor"]["offset"]
        assert not src(state)["cursor"]["pending"]
    else:
        assert src(state)["replay"]["noncontributing_empty_generations"] == [src(original)["history"][0]["binding"]["generation"]]


@pytest.mark.parametrize("fault", ["pending", "prefix", "truncate"])
def test_partial_cursor_recovery_refuses_changed_source(bridge, engine, world, monkeypatch, fault):
    state = original_cursor_shape(engine, world, monkeypatch, "partial")
    source = src(state)
    data = world["transcript"].read_bytes()
    if fault == "truncate":
        changed = data[:source["cursor"]["offset"] - 1]
    else:
        at = source["cursor"]["frame_start"] + 30 if fault == "pending" else source["enrollment"]["offset"] + 30
        changed = data[:at] + bytes([data[at] ^ 1]) + data[at + 1:]
    world["transcript"].write_bytes(changed)
    try:
        final = replay_to_end(engine, world, state)
    except ValueError:
        return
    assert src(final)["replay"]["status"] == "failed"


@pytest.mark.parametrize("fault", ["range", "pending", "gap", "event", "foreign"])
def test_unequal_generation_requires_actual_zero_consumption(bridge, engine, world, monkeypatch, fault):
    state = original_cursor_shape(engine, world, monkeypatch, "unequal")
    old = deepcopy(src(state))
    generation = old["history"][0]
    if fault == "range":
        generation["ranges"] = [{"offset": generation["enrollment"]["offset"], "length": 1, "sha256": "0" * 64}]
    elif fault == "pending":
        generation["cursor"]["pending"] = "eA=="
    elif fault == "gap":
        generation["cursor"]["first_gap"] = 0
    elif fault == "foreign":
        generation["binding"]["inode"] += 1
    shadow = deepcopy(state)
    shadow["extensions"]["native_observations"]["sources"]["root"] = old
    if fault == "event":
        index = next(iter(shadow["extensions"]["native_observations"]["event_index"].values()))
        index["generation"] = generation["binding"]["generation"]
    # Exercise actual replay admission inside the authenticated preparer; the
    # modified value is a fault injection, never a forged journal fixture.
    original = bridge._begin_replay
    monkeypatch.setattr(bridge, "_begin_replay", lambda context, handle, prior, fresh:
        original({**context, "state": shadow}, handle, old, fresh))
    with pytest.raises(ValueError):
        reconcile(engine, world, state)
    assert engine.load_run(world["project"], state["run_id"]) == state


@pytest.mark.parametrize("kind", ["compact", "stream"])
def test_replay_charge_covers_actual_bounded_decode_reads(tmp_path, monkeypatch, kind):
    from test_native_observations import source, completed_item
    from test_native_span_counter import large
    import observation_bridge
    row = completed_item(750000) if kind == "compact" else large(native.MAX_STREAM_SPAN_BYTES - 1024)
    path, binding, cursor = source(tmp_path, [row])
    target = 200000 if kind == "compact" else 3 * 1024 * 1024
    while cursor["offset"] < target:
        batch = native.read_page(binding, cursor, limits=native.Limits(page_bytes=min(1024 * 1024, target - cursor["offset"])))
        assert not batch["gaps"] and not batch["diagnostics"]
        cursor = batch["cursor"]
    enrollment = {"offset": cursor["enrolled_from"], "anchor": None}
    retained = {"binding": binding, "cursor": cursor, "ranges": [], "enrollment": enrollment}
    fresh = deepcopy(retained)
    retained["replay"] = {"status": "pending", "phase": "decode", "mode": "refresh",
        "snapshot": observation_bridge._replay_stamp(path.stat()),
        "path_chain": observation_bridge._replay_path_chain(str(path)),
        "prior_cursor_digest": native._digest(cursor), "prior_ranges_digest": native._digest([]),
        "prior_enrollment_digest": native._digest(enrollment), "fresh": fresh,
        "frontier": path.stat().st_size, "expected": {}, "matched": [], "aliases": {},
        "indices": {}, "revisions": [], "revision_index": 0, "witnesses": [], "witness_index": 0,
        "original_offset": cursor["enrolled_from"]}
    charge = observation_bridge.replay_read_ceiling(retained)
    reads = []
    stable = native._stable_read
    def counted(*args, **kwargs):
        raw = stable(*args, **kwargs)
        reads.append(2 * len(raw))
        return raw
    monkeypatch.setattr(native, "_stable_read", counted)
    result = observation_bridge._prepare_replay_page({"state": {"run_id": "bounded-fixture"}}, "root", retained)
    assert result["source"]["replay"]["status"] == "complete", result
    assert not result["batch"]["gaps"] and not result["batch"]["diagnostics"]
    assert charge >= sum(reads) > 2 * path.stat().st_size
    assert observation_bridge.replay_read_ceiling(retained, historical=True) == charge + 8 * binding["header_length"]


@pytest.mark.parametrize("fault", ["header-zero", "header-too-large", "header-generation", "cursor", "index", "length", "offset", "phase"])
def test_replay_charge_refuses_forged_bounds_before_source_io(bridge, engine, world, monkeypatch, fault):
    state = broken_history(engine, world, monkeypatch)
    state = reconcile(engine, world, state)
    source = deepcopy(src(state))
    replay = source["replay"]
    if fault.startswith("header"):
        replay["fresh"]["binding"]["header_length"] = {"header-zero": 0, "header-too-large": native.MAX_HEADER_BYTES + 1, "header-generation": 1}[fault]
    elif fault == "cursor":
        replay["fresh"]["cursor"]["frame_start"] = -1
    elif fault == "index":
        replay["witness_index"] = -1
    elif fault == "length":
        replay["witnesses"][0]["length"] = bridge.MAX_REPLAY_PAGE_BYTES + 1
    elif fault == "offset":
        replay["witnesses"][0]["offset"] = -1
    else:
        replay["phase"] = "unknown"
    def forbidden(*args, **kwargs):
        raise AssertionError("pricing must not open native files")
    monkeypatch.setattr(native, "_open", forbidden)
    with pytest.raises(ValueError):
        bridge.replay_read_ceiling(source)


def test_replay_charge_semantics_only_reserves_remaining_component(bridge, engine, world, monkeypatch):
    state = broken_history(engine, world, monkeypatch, cancel=True)
    state = reconcile(engine, world, state)
    source = deepcopy(src(state))
    replay = source["replay"]
    replay["phase"] = "semantics"
    assert replay["revisions"]
    header = replay["fresh"]["binding"]["header_length"]
    assert bridge.replay_read_ceiling(source) == 4 * header + bridge.MAX_CONSUMPTION_BYTES + 1
    # Exercise the actual component reader, not a mocked accepted batch.
    import journal_storage
    context = {**engine.inspect_context(state, world["actor"]), "state": state, "project": world["project"]}
    reads = []
    stable, component = native._stable_read, journal_storage._read_at
    def native_read(*args, **kwargs):
        raw = stable(*args, **kwargs)
        reads.append(2 * len(raw))
        return raw
    def component_read(*args, **kwargs):
        raw = component(*args, **kwargs)
        reads.append(len(raw))
        return raw
    with monkeypatch.context() as measured:
        measured.setattr(native, "_stable_read", native_read)
        measured.setattr(journal_storage, "_read_at", component_read)
        prepared = bridge._prepare_replay_page(context, "root", source)
    assert prepared["source"]["replay"]["status"] == "pending", prepared["source"]["replay"].get("failure")
    assert prepared["source"]["replay"]["revision_index"] == 1
    assert 4 * header < sum(reads) <= bridge.replay_read_ceiling(source)
    replay["revision_index"] = len(replay["revisions"])
    assert bridge.replay_read_ceiling(source) == 4 * header
    assert bridge.replay_read_ceiling(source, historical=True) == 12 * header



def test_semantic_charge_includes_component_growth_refusal_byte(bridge, engine, world, monkeypatch, tmp_path):
    import journal_storage
    state = broken_history(engine, world, monkeypatch, cancel=True)
    state = reconcile(engine, world, state)
    source = deepcopy(src(state))
    source["replay"]["phase"] = "semantics"
    assert source["replay"]["revisions"]
    monkeypatch.setattr(bridge, "MAX_CONSUMPTION_BYTES", 1024)
    path = tmp_path / "growing-component.json"
    path.write_bytes(b" " * 1022 + b"{}")
    before = path.stat()
    original = journal_storage.os.fdopen
    reads = []
    class Stream:
        def __init__(self, stream):
            self.stream = stream
        def __getattr__(self, name):
            return getattr(self.stream, name)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return self.stream.__exit__(*args)
        def read(self, count):
            with path.open("ab") as writer:
                writer.write(b"!")
            raw = self.stream.read(count)
            reads.append(len(raw))
            return raw
    def fdopen(fd, *args, **kwargs):
        stat = journal_storage.os.fstat(fd)
        stream = original(fd, *args, **kwargs)
        return Stream(stream) if (stat.st_dev, stat.st_ino) == (before.st_dev, before.st_ino) else stream
    monkeypatch.setattr(journal_storage.os, "fdopen", fdopen)
    with pytest.raises(ValueError, match="changed during read"):
        journal_storage.component(path, (), max_bytes=bridge.MAX_CONSUMPTION_BYTES)
    assert reads == [1025]
    header = source["replay"]["fresh"]["binding"]["header_length"]
    assert bridge.replay_read_ceiling(source) == 4 * header + sum(reads)
