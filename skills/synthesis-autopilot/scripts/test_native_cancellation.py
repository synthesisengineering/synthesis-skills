"""Actual journal/PM owners, isolated concurrent processes, no native provider."""

from copy import deepcopy
import json
import os
import hashlib
import multiprocessing
import sys
import delegation_boundary as boundary
from pathlib import Path
import time
import pytest
from test_controller import (
    facade,
    engine,
    world,
    start_request,
    invoke,
    state_of,
    request,
)
from test_run_state import command
import coordination_process

__all__ = ["facade", "engine", "world"]


def prepared(facade, engine, world):
    response = invoke(facade, world, start_request(world))
    state = state_of(world, response)

    def seed(current, payload, context):
        flow = current["extensions"]["workflow"]
        flow["children"]["child"] = {
            "child_id": "child",
            "task_id": "work",
            "mode": "native-cli",
            "client": "codex",
            "disposition": "running",
            "cancellation_requested": False,
            "audit_status": "required",
            "reservation_id": "cost",
            "owner": deepcopy(current["owner"]),
        }
        flow["graph"]["nodes"]["work"]["status"] = "running"
        return current

    engine.register_command("fixture.child", seed, allowed_fields=("extensions",))
    state = command(engine, world, state, "fixture.child", {})
    path = world["project"] / "resources/check.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "native_worker",
                "arguments": {"child_id": "child", "timeout_seconds": 15},
            }
        )
    )
    state = command(
        engine,
        world,
        state,
        "artifact.register",
        {
            "id": "check",
            "path": str(path),
            "role": "input",
            "required": True,
            "retention": "durable",
        },
    )
    return state


def observe(engine, world, state, ident="native-attempt"):
    return engine.observe(
        world["project"],
        state["run_id"],
        "native_worker",
        {"check_id": "check"},
        expected_revision=state["revision"],
        command_id=ident,
        actor=world["actor"],
        runtime_root=world["runtime"],
    )


def tail(engine, world, state):
    return engine.load_run(world["project"], state["run_id"])


def external_cancel(world, state, reason):
    """Fresh interpreter: no inherited in-process PM observation capability."""
    script = world["scratch"] / ("cancel-" + str(state["revision"]) + ".py")
    script.write_text(
        "import json,sys\nfrom pathlib import Path\nsys.path.insert(0,"
        + repr(str(Path(__file__).parent))
        + ")\nimport autopilot\ne=autopilot.engine()\nw=json.loads(sys.argv[1])\ns=e.load_run(Path(w['project']),w['run'])\ne.apply_command(Path(w['project']),w['run'],'workflow.cancel_child',{'child_id':'child','reason':w['reason']},expected_revision=s['revision'],command_id='external-cancel',actor=w['actor'],runtime_root=Path(w['runtime']))\n"
    )
    result = coordination_process.run(
        [
            sys.executable,
            "-B",
            str(script),
            json.dumps(
                {
                    "project": str(world["project"]),
                    "run": state["run_id"],
                    "actor": world["actor"],
                    "runtime": str(world["runtime"]),
                    "reason": reason,
                }
            ),
        ],
        cwd=world["scratch"],
        timeout=10,
    )
    (world["scratch"] / "external-cancel.log").write_text(result.stdout + result.stderr)
    assert result.returncode == 0, (result.stdout, result.stderr)


@pytest.mark.parametrize("target", ["run", "child", "task"])
def test_real_concurrent_controller_cancellation(
    facade, engine, world, monkeypatch, target
):
    state = prepared(facade, engine, world)
    ready = world["scratch"] / "observer-ready"
    result = world["scratch"] / "observer-result.json"

    def native(ctx, payload):
        ready.write_text("observer executing")
        end = time.monotonic() + 12
        while time.monotonic() < end:
            value = ctx["current_cancellation"]()
            if value["requested"]:
                return {
                    "child_id": "child",
                    "cancellation": value,
                    "usage": {"tokens": None, "usd_micros": None},
                    "terminal": "failed",
                    "process_cleanup": {
                        "cleanup_verified": True,
                        "native_terminal": "UNKNOWN",
                        "scope": "synthetic observer has no native child",
                    },
                }
            time.sleep(0.02)
        raise TimeoutError("owner cancellation was not received")

    monkeypatch.setattr(
        boundary,
        "run_worker",
        lambda state, child_id, context, **kw: native(context, {}),
    )

    def child():
        try:
            result.write_text(json.dumps({"state": observe(engine, world, state)}))
        except BaseException as exc:
            result.write_text(
                json.dumps({"error": type(exc).__name__ + ": " + str(exc)})
            )

    process = multiprocessing.get_context("fork").Process(target=child)
    process.start()
    try:
        end = time.monotonic() + 15
        while not ready.exists() and process.is_alive() and time.monotonic() < end:
            time.sleep(0.02)
        assert ready.exists(), (
            result.read_text() if result.exists() else process.exitcode
        )
        current = tail(engine, world, state)
        values = {"target": target, "reason": "Synthetic current cancellation"}
        if target != "run":
            values["target_id"] = "child" if target == "child" else "work"
        response = invoke(
            facade, world, request("cancel", values, current, identity="cancel-active")
        )
        (world["scratch"] / "cancel-response.json").write_text(json.dumps(response))
        process.join(15)
        assert not process.is_alive()
        outcome = json.loads(result.read_text())
        assert "error" not in outcome, (outcome, response)
        final = tail(engine, world, state)
        assert final["native_execution"]["native-attempt"]["status"] == "completed"
        assert final["observations"]["native-attempt"]["data"]["cancellation"][
            "requested"
        ]
        assert final["observations"]["native-attempt"]["data"]["usage"] == {
            "tokens": None,
            "usd_micros": None,
        }
        assert (
            final["extensions"]["workflow"]["children"]["child"]["disposition"]
            == "running"
        )
        if target == "run":
            assert final["status"] not in engine.TERMINAL
            assert response["status"] == "CANCELLATION_REQUESTED", response
        before = deepcopy(final)
        assert observe(engine, world, state) == before  # No second effect.
        assert tail(engine, world, state) == before
    finally:
        if process.is_alive():
            process.terminate()
        process.join(5)
        assert not process.is_alive()


@pytest.mark.parametrize("fault", ["interruption", "error"])
def test_interrupted_intent_is_not_replayed(facade, engine, world, monkeypatch, fault):
    state = prepared(facade, engine, world)
    calls = []

    def native(ctx, payload):
        calls.append(1)
        if fault == "interruption":
            raise KeyboardInterrupt()
        raise ValueError("synthetic failed observer before result commit")

    monkeypatch.setattr(
        boundary,
        "run_worker",
        lambda state, child_id, context, **kw: native(context, {}),
    )
    with pytest.raises((KeyboardInterrupt, ValueError)):
        observe(engine, world, state)
    pending = tail(engine, world, state)
    assert pending["native_execution"]["native-attempt"]["status"] == "pending"
    for ident in ("native-attempt", "another-attempt"):
        with pytest.raises(ValueError):
            observe(engine, world, pending, ident)
    assert calls == [1]
    assert tail(engine, world, state) == pending
    with pytest.raises(ValueError):
        command(
            engine,
            world,
            pending,
            "progress",
            {"summary": "Cannot bypass unresolved effect"},
        )


@pytest.mark.parametrize(
    "fault", ["stale", "foreign", "wrong-child", "changed-command", "spec-change"]
)
def test_pending_intent_refuses_substitution(facade, engine, world, monkeypatch, fault):
    state = prepared(facade, engine, world)

    def native(ctx, payload):
        raise KeyboardInterrupt()

    monkeypatch.setattr(
        boundary,
        "run_worker",
        lambda state, child_id, context, **kw: native(context, {}),
    )
    with pytest.raises(KeyboardInterrupt):
        observe(engine, world, state)
    pending = tail(engine, world, state)
    actor = deepcopy(world["actor"])
    expected = pending["revision"]
    child = "child"
    if fault == "stale":
        expected -= 1
    if fault == "foreign":
        actor["native_payload"]["session_id"] = "01990000-0000-7000-8000-000000000099"
    if fault == "wrong-child":
        child = "foreign-child"
    if fault == "changed-command":
        with pytest.raises(ValueError):
            engine.observe(
                world["project"],
                state["run_id"],
                "native_worker",
                {"check_id": "different"},
                expected_revision=expected,
                command_id="native-attempt",
                actor=actor,
                runtime_root=world["runtime"],
            )
    elif fault == "spec-change":
        (world["project"] / "resources/check.json").write_text("{}")
        with pytest.raises(ValueError):
            observe(engine, world, pending)
    else:
        with pytest.raises(ValueError):
            command(
                engine,
                world,
                pending,
                "workflow.cancel_child",
                {"child_id": child, "reason": "Synthetic"},
                actor=actor,
                expected_revision=expected,
            )
    assert tail(engine, world, state) == pending


def test_cancel_between_intent_and_launch_is_visible(
    facade, engine, world, monkeypatch
):
    state = prepared(facade, engine, world)
    effect = []

    def native(ctx, payload):
        pending = tail(engine, world, state)
        external_cancel(world, pending, "Before launch")
        cancellation = ctx["current_cancellation"]()
        if not cancellation["requested"]:
            effect.append("launched")
        return {
            "cancellation": cancellation,
            "usage": {"tokens": None, "usd_micros": None},
            "terminal": "not_started",
        }

    monkeypatch.setattr(
        boundary,
        "run_worker",
        lambda state, child_id, context, **kw: native(context, {}),
    )
    final = observe(engine, world, state)
    assert not effect
    assert final["observations"]["native-attempt"]["data"]["terminal"] == "not_started"
    assert final["native_execution"]["native-attempt"]["observed_cancellation"][
        "requested"
    ]


def test_cancel_after_native_completion_before_append_retains_both_facts(
    facade, engine, world, monkeypatch
):
    state = prepared(facade, engine, world)

    def native(ctx, payload):
        external_cancel(world, tail(engine, world, state), "Completion race")
        return {"terminal": "completed", "usage": {"tokens": 7, "usd_micros": None}}

    monkeypatch.setattr(
        boundary,
        "run_worker",
        lambda state, child_id, context, **kw: native(context, {}),
    )
    final = observe(engine, world, state)
    assert final["observations"]["native-attempt"]["data"]["usage"]["tokens"] == 7
    assert final["native_execution"]["native-attempt"]["observed_cancellation"][
        "requested"
    ]
    assert (
        final["extensions"]["workflow"]["children"]["child"]["disposition"] == "running"
    )


def test_derived_intent_collision_refuses_without_poisoning_history(
    facade, engine, world
):
    state = prepared(facade, engine, world)
    ident = "native-intent-" + engine._digest("native-attempt")[:32]
    state = command(
        engine,
        world,
        state,
        "progress",
        {"summary": "Existing exact command"},
        command_id=ident,
    )
    with pytest.raises(ValueError):
        observe(engine, world, state)
    assert tail(engine, world, state) == state


# Original-intent recovery: every OS child and transcript below is synthetic.


def configured(facade, engine, world, monkeypatch):
    state = prepared(facade, engine, world)
    outputs = world["project"] / "resources/review-output"
    outputs.mkdir()
    scratch = world["project"] / "resources/review-scratch"
    scratch.mkdir()
    source = world["project"] / "resources/check.json"
    contract = {
        "schema_version": 1,
        "immutable_inputs": [
            {
                "artifact_id": "check",
                "path": str(source),
                "digest": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        ],
        "output_roots": [str(outputs)],
        "scratch_root": str(scratch),
    }

    def seed(s, p, c):
        child = s["extensions"]["workflow"]["children"]["child"]
        child.update(
            client="claude",
            file_contract=contract,
            paths=[str(outputs), str(scratch)],
            required_capabilities=["read", "write", "edit", "shell"],
            integration_owner=s["owner"]["session_uuid"],
            deliverables=["Write an explicitly synthetic result"],
            reservation_id="cost",
        )
        s["extensions"]["workflow"]["budget"]["reservations"]["cost"] = {
            "id": "cost",
            "parent_id": None,
            "actual": None,
            "status": "reserved",
            "category": "work",
            "amounts": {"wall_millis": 10000, "usd_micros": 1000000},
        }
        s["extensions"]["workflow"]["budget"]["limits"].update(
            {
                name: {"limit": limit, "enforcement": "forecast"}
                for name, limit in [
                    ("tokens", 10000),
                    ("usd_micros", 10000000),
                    ("wall_millis", 100000),
                ]
            }
        )
        s["extensions"]["workflow"]["budget"]["reservations"]["cost"]["amounts"].update(
            tokens=1000, model_tokens=1000
        )
        return s

    engine.register_command("fixture.configure", seed, allowed_fields=("extensions",))
    state = command(engine, world, state, "fixture.configure", {})
    cli = world["scratch"] / "synthetic-cli"
    cli.write_text(
        "#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\nsys.stdin.read()\n"
        + f'Path({str(outputs / "result.txt")!r}).write_text("Synthetic result, no provider")\n'
        + 'print(json.dumps({"type":"system","subtype":"init","session_id":"review-fixture","model":"configured"}))\n'
        + 'print(json.dumps({"type":"result","subtype":"success","session_id":"review-fixture","total_cost_usd":0.1,"usage":{"input_tokens":4,"output_tokens":2}}))\n'
    )
    cli.chmod(0o700)
    monkeypatch.setattr(
        boundary, "client_selection", lambda client, env: ({"effort": "high"}, str(cli))
    )
    return state


def interrupted(
    facade, engine, world, monkeypatch, phase="receipt", custody="valid", alive=False
):
    state = configured(facade, engine, world, monkeypatch)
    ready = world["scratch"] / "observer-ready"
    actual = boundary.run_worker

    def worker(*a, **kw):
        data = actual(*a, **kw)
        assert boundary.verify_worker_observation(data, a[2])
        receipt = Path(data["receipt_path"])
        if custody == "partial":
            receipt.write_text('{"interrupted":')
        if custody == "missing":
            receipt.rename(receipt.with_name("receipt.preserved"))
        (world["scratch"] / "observed.json").write_text(json.dumps(data))
        ready.write_text("receipt complete")
        if alive:
            end = time.monotonic() + 25
            while time.monotonic() < end:
                time.sleep(0.02)
        os._exit(0)

    monkeypatch.setattr(boundary, "run_worker", worker)
    if phase != "receipt":
        append = engine._append

        def crash(*a, **kw):
            value = append(*a, **kw)
            if a[4] == (
                "native.execution.prepare"
                if phase == "prepared"
                else "native.execution.dispatch"
            ):
                ready.write_text(phase)
                os._exit(0)
            return value

        monkeypatch.setattr(engine, "_append", crash)

    def owner():
        try:
            observe(engine, world, state)
        except BaseException as exc:
            (world["scratch"] / "observer-error").write_text(repr(exc))
            os._exit(2)

    process = multiprocessing.get_context("fork").Process(target=owner)
    process.start()
    end = time.monotonic() + 18
    while not ready.exists() and process.is_alive() and time.monotonic() < end:
        time.sleep(0.02)
    if not ready.exists():
        process.join(1)
        if process.is_alive():
            process.kill()
            process.join(2)
        pytest.fail(
            (world["scratch"] / "observer-error").read_text()
            if (world["scratch"] / "observer-error").exists()
            else f"child exit {process.exitcode}"
        )
    if not alive:
        process.join(2)
        assert not process.is_alive()
        assert process.exitcode == 0
    return state, process


def recover(facade, engine, world, state, identity="recover-intent"):
    current = tail(engine, world, state)
    return invoke(
        facade,
        world,
        request("recover", {"reconcile_sources": False}, current, identity),
    )


def test_actual_dead_observer_retained_receipt_is_recovered(
    facade, engine, world, monkeypatch
):
    state, p = interrupted(facade, engine, world, monkeypatch)
    before = tail(engine, world, state)
    response = recover(facade, engine, world, state)
    after = tail(engine, world, state)
    assert after["native_execution"]["native-attempt"]["status"] == "completed", (
        response
    )
    assert after["observations"]["native-attempt"]["data"]["usage"] == {
        "tokens": 6,
        "usd_micros": 100000,
    }
    old_budget = before["extensions"]["workflow"]["budget"]
    new_budget = after["extensions"]["workflow"]["budget"]
    assert {key: new_budget[key] for key in old_budget} == old_budget
    assert set(new_budget) - set(old_budget) <= {"native_usage"}
    if "native_usage" not in old_budget:
        # Existing ordinary controller recovery initializes an empty ledger;
        # this is not a refill, settlement, measurement or revised deadline.
        assert all(
            not value
            for key, value in new_budget.get("native_usage", {}).items()
            if key != "schema_version"
        )
    assert (
        world["project"] / "resources/review-output/result.txt"
    ).read_text() == "Synthetic result, no provider"
    again = observe(engine, world, before)
    assert again["native_execution"]["native-attempt"]["status"] == "completed"


@pytest.mark.parametrize("phase", ["prepared", "dispatch"])
def test_real_observer_loss_fence_distinguishes_no_dispatch(
    facade, engine, world, monkeypatch, phase
):
    state, p = interrupted(facade, engine, world, monkeypatch, phase=phase)
    response = recover(facade, engine, world, state)
    after = tail(engine, world, state)
    assert after["native_execution"]["native-attempt"]["status"] == (
        "not_started" if phase == "prepared" else "pending"
    ), response
    assert "native-attempt" not in after.get("observations", {})
    assert not (world["project"] / "resources/review-output/result.txt").exists()


@pytest.mark.parametrize("custody", ["partial", "missing"])
def test_dead_observer_ambiguous_receipt_never_clears_pending(
    facade, engine, world, monkeypatch, custody
):
    state, p = interrupted(facade, engine, world, monkeypatch, custody=custody)
    before = tail(engine, world, state)
    response = recover(facade, engine, world, state)
    assert response["status"] == "UNRESOLVED", response
    assert tail(engine, world, state) == before


def test_live_observer_receipt_cannot_be_stolen(facade, engine, world, monkeypatch):
    state, p = interrupted(facade, engine, world, monkeypatch, alive=True)
    try:
        before = tail(engine, world, state)
        response = recover(facade, engine, world, state)
        assert response["status"] == "UNRESOLVED", response
        assert tail(engine, world, state) == before
        assert p.is_alive()
    finally:
        p.kill()
        p.join(3)
        assert not p.is_alive()


def test_incomplete_close_retains_effect_and_late_exact_receipt(
    facade, engine, world, monkeypatch
):
    state, p = interrupted(facade, engine, world, monkeypatch, custody="missing")
    state = tail(engine, world, state)
    state = command(
        engine,
        world,
        state,
        "close",
        {
            "status": "incomplete",
            "reason": "Original effect remains ambiguous; retained custody pending",
        },
    )
    assert state["native_execution"]["native-attempt"]["status"] == "pending"
    terminal = deepcopy(state["terminal"])
    receipt = (
        world["project"]
        / f"resources/autopilot-runs/{state['run_id']}/native-worker-attempts/child/receipt.json"
    )
    receipt.with_name("receipt.preserved").rename(receipt)
    response = recover(facade, engine, world, state)
    after = tail(engine, world, state)
    assert after["status"] == "incomplete", response
    assert after["terminal"] == terminal
    assert after["native_execution"]["native-attempt"]["status"] == "completed", (
        response
    )


def test_original_observer_lease_refuses_replacement_and_alias(
    facade, engine, world, monkeypatch
):
    state, p = interrupted(facade, engine, world, monkeypatch)
    state = tail(engine, world, state)
    path = (
        world["project"] / state["native_execution"]["native-attempt"]["lease"]["path"]
    )
    saved = path.with_suffix(".preserved")
    path.rename(saved)
    path.write_bytes(saved.read_bytes())
    path.chmod(0o600)
    response = recover(facade, engine, world, state)
    assert response["status"] == "UNRESOLVED"
    assert tail(engine, world, state) == state
    path.rename(path.with_suffix(".substitute"))
    path.symlink_to(saved)
    response = recover(facade, engine, world, state, "recover-alias")
    assert response["status"] == "UNRESOLVED"
    assert tail(engine, world, state) == state


@pytest.mark.parametrize(
    "fault",
    [
        "receipt_nonce",
        "receipt_bytes",
        "check",
        "plan",
        "copied_board",
        "stale_revision",
    ],
)
def test_original_recovery_refuses_changed_source_or_authority(
    facade, engine, world, monkeypatch, fault
):
    state, p = interrupted(facade, engine, world, monkeypatch)
    state = tail(engine, world, state)
    if fault.startswith("receipt"):
        path = (
            world["project"]
            / f"resources/autopilot-runs/{state['run_id']}/native-worker-attempts/child/receipt.json"
        )
        data = json.loads(path.read_text())
        if fault == "receipt_nonce":
            data["configuration"]["observation_intent"]["nonce"] = (
                "not-the-original-invocation"
            )
        else:
            data["data"]["usage"]["tokens"] = 0
        path.write_text(json.dumps(data))
    elif fault == "check":
        (world["project"] / "resources/check.json").write_text("{}")
    elif fault == "plan":
        world["plan"].write_text(
            world["plan"].read_text() + "\nChanged human instruction\n"
        )
    elif fault == "copied_board":
        copied = world["scratch"] / "copied-board.md"
        copied.write_bytes(world["board"].read_bytes())
        world["actor"] = {**world["actor"], "board": str(copied)}
    values = request("recover", {"reconcile_sources": False}, state, "recover-changed")
    if fault == "stale_revision":
        values["expected_revision"] -= 1
    response = invoke(facade, world, values)
    assert response["status"] == "UNRESOLVED", response
    assert tail(engine, world, state) == state


@pytest.mark.parametrize("commit", ["before", "after"])
def test_original_result_crash_window_is_replay_safe(
    facade, engine, world, monkeypatch, commit
):
    state, p = interrupted(facade, engine, world, monkeypatch)
    state = tail(engine, world, state)
    values = request("recover", {"reconcile_sources": False}, state, "recover-window")
    actual = engine._append

    def interrupted_append(*args, **kwargs):
        if args[2] == "native-attempt":
            if commit == "after":
                actual(*args, **kwargs)
            raise KeyboardInterrupt(
                "Synthetic recovery interruption at original outcome commit"
            )
        return actual(*args, **kwargs)

    monkeypatch.setattr(engine, "_append", interrupted_append)
    with pytest.raises(KeyboardInterrupt):
        invoke(facade, world, values)
    monkeypatch.setattr(engine, "_append", actual)
    response = invoke(facade, world, values)
    final = tail(engine, world, state)
    assert final["native_execution"]["native-attempt"]["status"] == "completed", (
        response
    )
    events = list(engine._events(world["project"], state["run_id"]))
    assert sum(row["command_id"] == "native-attempt" for row in events) == 1
    assert sum(row["command"] == "native.execution.recover" for row in events) == 1
    assert "recover-window" in final["extensions"]["controller"]["requests"]


def test_recovery_ack_cannot_reuse_original_command_id(
    facade, engine, world, monkeypatch
):
    state, p = interrupted(facade, engine, world, monkeypatch)
    state = tail(engine, world, state)
    with pytest.raises(ValueError, match="own command identity"):
        engine.apply_command(
            world["project"],
            state["run_id"],
            "native.execution.recover",
            {"intent_id": "native-attempt"},
            expected_revision=state["revision"],
            command_id="native-attempt",
            actor=world["actor"],
            runtime_root=world["runtime"],
        )
    assert tail(engine, world, state) == state


def terminal_audit(facade, engine, world, monkeypatch, *, prelaunch=False):
    state, p = interrupted(
        facade, engine, world, monkeypatch, phase="prepared" if prelaunch else "receipt"
    )
    state = tail(engine, world, state)
    state = command(
        engine,
        world,
        state,
        "close",
        {
            "status": "incomplete",
            "reason": "Retain original interrupted work and all unmeasured costs",
        },
    )
    terminal = deepcopy(state["terminal"])
    recover(facade, engine, world, state)
    state = tail(engine, world, state)
    if not prelaunch:
        state = command(
            engine,
            world,
            state,
            "workflow.worker_record",
            {"child_id": "child", "receipt_id": "native-attempt"},
        )
    state = command(
        engine,
        world,
        state,
        "workflow.return",
        {
            "child_id": "child",
            "disposition": "failed",
            "artifact_ids": [],
            "evidence_ids": [],
            "reason": "Original interrupted attempt was not accepted as complete",
        },
    )
    child = state["extensions"]["workflow"]["children"]["child"]
    from test_evidence_bridge import record, append_claude_tool

    context = engine.inspect_context(state, world["actor"], project=world["project"])
    producer = "child" if prelaunch else child["producer"]
    measured = (
        {}
        if prelaunch
        else {
            **child["worker_observation"]["usage"],
            "wall_millis": child["worker_observation"]["elapsed_millis"],
        }
    )
    bindings = {
        key: state[key] for key in ("run_id", "contract_digest", "profile_digest")
    }
    review_request = {
        "schema_version": 1,
        "kind": "child_integration",
        "bindings": bindings,
        "artifact_digests": {"check": state["artifacts"]["check"]["digest"]},
        "producer": producer,
    }
    data = {
        "child_id": "child",
        "task_id": "work",
        "accepted": False,
        "criteria": [],
        "artifact_ids": [],
        "artifact_digests": {},
        "reviewer": "claude-agent:late-audit",
        "producer": producer,
        "integration_owner": state["owner"]["session_uuid"],
        "actual": measured,
    }
    reply = {
        "schema_version": 1,
        "kind": "child_integration",
        "bindings": bindings,
        "data": data,
    }
    append_claude_tool(
        world,
        "Agent",
        {"prompt": json.dumps({"autopilot_review": review_request})},
        {"autopilot_review": reply},
        "late-audit",
    )
    receipt = record(
        "child_integration",
        {**data, "source": {"kind": "native-agent", "call_id": "late-audit"}},
        {**context, "state": state},
    )
    path = world["project"] / "late-audit.json"
    path.write_text(json.dumps(receipt))
    return state, terminal, path


@pytest.mark.parametrize("prelaunch", [False, True])
def test_terminal_original_child_actual_native_audit_preserves_unknown_cost(
    facade, engine, world, monkeypatch, prelaunch
):
    state, terminal, path = terminal_audit(
        facade, engine, world, monkeypatch, prelaunch=prelaunch
    )
    state = command(
        engine,
        world,
        state,
        "artifact.register",
        {
            "id": "late-audit",
            "path": str(path),
            "role": "evidence",
            "retention": "durable",
            "required": False,
        },
    )
    state = command(
        engine,
        world,
        state,
        "evidence.record",
        {"id": "late-audit", "kind": "child_integration", "artifact_id": "late-audit"},
    )
    state = command(
        engine,
        world,
        state,
        "workflow.integrate",
        {"child_id": "child", "receipt_id": "late-audit"},
    )
    assert state["status"] == "incomplete" and state["terminal"] == terminal
    assert (
        state["extensions"]["workflow"]["children"]["child"]["audit_status"]
        == "rejected"
    )
    reservation = state["extensions"]["workflow"]["budget"]["reservations"]["cost"]
    assert (
        reservation["status"] == "unknown"
        and reservation["amounts"]["model_tokens"] == 1000
    )
    assert "model_tokens" not in (reservation["actual"] or {})


@pytest.mark.parametrize(
    "fault", ["unrelated_child", "forged_review", "changed_after_read"]
)
def test_terminal_audit_cannot_adopt_foreign_or_changed_evidence(
    facade, engine, world, monkeypatch, fault
):
    state, terminal, path = terminal_audit(facade, engine, world, monkeypatch)
    if fault != "changed_after_read":
        record = json.loads(path.read_text())
        if fault == "unrelated_child":
            record["data"]["child_id"] = "foreign-child"
        else:
            record["data"]["actual"]["tokens"] = 0
        path.write_text(json.dumps(record))
    else:
        real = engine._reduce

        def change(*args, **kwargs):
            value = real(*args, **kwargs)
            if args[2] == "artifact.register":
                path.write_text("{}")
            return value

        monkeypatch.setattr(engine, "_reduce", change)
    with pytest.raises(ValueError):
        command(
            engine,
            world,
            state,
            "artifact.register",
            {
                "id": "late-audit",
                "path": str(path),
                "role": "evidence",
                "retention": "durable",
                "required": False,
            },
        )
    assert tail(engine, world, state) == state


@pytest.mark.parametrize(
    "command_name,payload",
    [
        (
            "workflow.reserve",
            {
                "reservation_id": "new",
                "amounts": {"model_tokens": 1},
                "category": "work",
            },
        ),
        (
            "workflow.task",
            {"task_id": "work", "action": "retry", "reason": "Not permitted"},
        ),
        (
            "artifact.register",
            {
                "id": "unrelated",
                "path": "resources/check.json",
                "role": "input",
                "retention": "durable",
                "required": False,
            },
        ),
        (
            "workflow.return",
            {
                "child_id": "foreign",
                "disposition": "failed",
                "artifact_ids": [],
                "evidence_ids": [],
                "reason": "Not ours",
            },
        ),
    ],
)
def test_terminal_late_custody_never_admits_other_work(
    facade, engine, world, monkeypatch, command_name, payload
):
    state, terminal, path = terminal_audit(facade, engine, world, monkeypatch)
    with pytest.raises(ValueError):
        command(engine, world, state, command_name, payload)
    assert tail(engine, world, state) == state


@pytest.mark.parametrize("busy", [False, True])
def test_large_retained_history_actual_transport_cancellation(
    facade, engine, world, monkeypatch, busy
):
    from test_successor_transaction import intent, advance

    state = prepared(facade, engine, world)
    child = deepcopy(state["extensions"]["workflow"]["children"]["child"])

    def history(s, p, c):
        s["extensions"]["retained_cancellation_measurement"] = {
            "payload": "X" * (512 * 1024),
            "ordinal": p["ordinal"],
        }
        s["extensions"]["workflow"]["children"] = {}
        s["extensions"]["workflow"]["graph"]["nodes"]["work"]["status"] = "pending"
        return s

    engine.register_command("fixture.history", history, allowed_fields=("extensions",))
    for i in range(80):
        state = command(engine, world, state, "fixture.history", {"ordinal": i})
    old = command(
        engine,
        world,
        state,
        "close",
        {"status": "incomplete", "reason": "Retained measured synthetic history"},
    )
    home = engine._home(world["project"], old["run_id"])
    hashes = {
        str(p.relative_to(home)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in home.rglob("*.json")
        if p.is_file()
    }
    logical = sum((home / key).stat().st_size for key in hashes)
    state = advance(engine, world, intent(engine, world, old))

    def restore(s, p, c):
        s["extensions"]["workflow"]["children"]["child"] = deepcopy(child)
        s["extensions"]["workflow"]["graph"]["nodes"]["work"]["status"] = "running"
        return s

    engine.register_command("fixture.restore", restore, allowed_fields=("extensions",))
    state = command(engine, world, state, "fixture.restore", {})
    stats = []

    def worker(s, child_id, context, **kwargs):
        from native_resume import NativeCancellation

        def validate():
            begin = time.monotonic()
            value = context["current_cancellation"]()
            stats.append(
                {
                    "seconds": time.monotonic() - begin,
                    "requested": value["requested"],
                    "revision": value["revision"],
                }
            )
            if value["requested"]:
                raise NativeCancellation(value)

        def cancel():
            # Forked Python inherits an active ContextVar from the observer.
            # Execute a fresh ordinary owner, as a separate CLI invocation does.
            code = "import sys,json,time;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import autopilot;engine=autopilot.engine();a=json.loads(sys.argv[2]);time.sleep(.35);p=Path(a['project']);s=engine.load_run(p,a['run_id']);engine.apply_command(p,a['run_id'],'workflow.cancel_child',{'child_id':'child','reason':'Measured synthetic cancellation'},expected_revision=s['revision'],command_id='measured-cancel',actor=a['actor'],runtime_root=Path(a['runtime']));Path(a['marker']).write_text(str(time.monotonic()))"
            values = {
                "project": str(world["project"]),
                "run_id": state["run_id"],
                "actor": world["actor"],
                "runtime": str(world["runtime"]),
                "marker": str(world["scratch"] / "cancel-committed"),
            }
            os.execv(
                sys.executable,
                [
                    sys.executable,
                    "-B",
                    "-c",
                    code,
                    str(Path(__file__).parent),
                    json.dumps(values),
                ],
            )

        process = multiprocessing.get_context("fork").Process(target=cancel)
        process.start()
        code = "import sys,time\nsys.stdin.read()\n" + (
            'while True: print("synthetic activity",flush=True);time.sleep(.01)'
            if busy
            else "time.sleep(60)"
        )
        began = time.monotonic()
        try:
            result = boundary._execute_native(
                [sys.executable, "-B", "-c", code],
                "",
                world["scratch"],
                12,
                dict(os.environ),
                revalidate=validate,
            )
        finally:
            process.join(3)
            if process.is_alive():
                process.kill()
                process.join(2)
        assert process.exitcode == 0
        exit_code, stdout, stderr, failure, cleanup = result
        assert failure and "cancel" in failure.lower(), result
        assert cleanup["cleanup_verified"] is True, cleanup
        assert any(row["requested"] for row in stats)
        (world["scratch"] / "history-transport-measurement.json").write_text(
            json.dumps(
                {
                    "busy": busy,
                    "retained_predecessor_bytes": logical,
                    "predecessor_events": old["revision"],
                    "polls": stats,
                    "transport_seconds": time.monotonic() - began,
                    "exit_code": exit_code,
                    "cleanup": cleanup,
                    "stdout_bytes": len(stdout),
                    "stderr_bytes": len(stderr),
                    "native_acceptance": False,
                },
                indent=2,
            )
        )
        return {
            "terminal": "failed",
            "usage": {"tokens": None, "usd_micros": None},
            "process_cleanup": cleanup,
            "cancellation": {"requested": True},
        }

    monkeypatch.setattr(boundary, "run_worker", worker)
    final = observe(engine, world, state)
    assert final["native_execution"]["native-attempt"]["status"] == "completed"
    after = {
        str(p.relative_to(home)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in home.rglob("*.json")
        if p.is_file()
    }
    assert after == hashes


def test_original_recovery_and_root_cancel_serialize_without_relaunch(
    facade, engine, world, monkeypatch
):
    state, p = interrupted(facade, engine, world, monkeypatch)
    start = world["scratch"] / "concurrent-start"
    outputs = []
    children = []

    def contender(which):
        end = time.monotonic() + 10
        while not start.exists() and time.monotonic() < end:
            time.sleep(0.01)
        current = tail(engine, world, state)
        try:
            cmd = "native.execution.recover" if which == "recover" else "close"
            payload = (
                {"intent_id": "native-attempt"}
                if which == "recover"
                else {
                    "status": "cancelled",
                    "reason": "Concurrent source-authorized cancellation",
                }
            )
            result = engine.apply_command(
                world["project"],
                state["run_id"],
                cmd,
                payload,
                expected_revision=current["revision"],
                command_id="concurrent-" + which,
                actor=world["actor"],
                runtime_root=world["runtime"],
            )
            output = {"revision": result["revision"]}
        except ValueError as exc:
            output = {"refusal": str(exc)}
        (world["scratch"] / ("concurrent-" + which + ".json")).write_text(
            json.dumps(output)
        )

    for which in ("recover", "cancel"):
        process = multiprocessing.get_context("fork").Process(
            target=contender, args=(which,)
        )
        process.start()
        children.append(process)
    start.write_text("dispatch")
    try:
        for process in children:
            process.join(15)
            assert process.exitcode == 0
    finally:
        for process in children:
            if process.is_alive():
                process.kill()
                process.join(2)
    for which in ("recover", "cancel"):
        outputs.append(
            json.loads(
                (world["scratch"] / ("concurrent-" + which + ".json")).read_text()
            )
        )
    current = tail(engine, world, state)
    if current["native_execution"]["native-attempt"]["status"] == "pending":
        recover(facade, engine, world, current, "concurrent-recovery-retry")
    current = tail(engine, world, state)
    if not current.get("cancellation_requested"):
        current = command(
            engine,
            world,
            current,
            "close",
            {
                "status": "cancelled",
                "reason": "Complete the retained cancellation request",
            },
        )
    assert current["native_execution"]["native-attempt"]["status"] == "completed"
    assert current["cancellation_requested"] and current["status"] != "cancelled"
    events = list(engine._events(world["project"], state["run_id"]))
    assert sum(row["command_id"] == "native-attempt" for row in events) == 1
    assert sum(row["command"] == "native.execution.dispatch" for row in events) == 1


@pytest.mark.parametrize(
    "fault", [None, "different_request", "changed_nonce", "active"]
)
def test_original_lease_before_intent_process_loss_retains_request_identity(
    facade, engine, world, monkeypatch, fault
):
    state = configured(facade, engine, world, monkeypatch)
    ready = world["scratch"] / "lease-created"
    actual = engine._new_native_lease

    def died():
        def boundary(*args, **kwargs):
            actual(*args, **kwargs)
            ready.write_text("private lease fsynced; no intent appended")
            os._exit(0)

        engine._new_native_lease = boundary
        observe(engine, world, state)

    process = multiprocessing.get_context("fork").Process(target=died)
    process.start()
    process.join(15)
    if process.is_alive():
        process.kill()
        process.join(2)
    assert process.exitcode == 0 and ready.exists()
    unchanged = tail(engine, world, state)
    assert unchanged == state and not unchanged.get("native_execution")
    path = engine._home(world["project"], state["run_id"]) / (
        ".native-" + engine._digest("native-attempt") + ".lock"
    )
    raw = path.read_bytes()
    before = path.stat()
    holder = None
    if fault == "changed_nonce":
        changed = json.loads(raw)
        changed["nonce"] = "not-a-nonce"
        path.write_text(json.dumps(changed))
    elif fault == "active":
        entered = world["scratch"] / "orphan-holder"

        def hold():
            with engine.bounded_lock(path, create=False):
                entered.write_text("held")
                time.sleep(15)

        holder = multiprocessing.get_context("fork").Process(target=hold)
        holder.start()
        until = time.monotonic() + 5
        while not entered.exists() and time.monotonic() < until:
            time.sleep(0.02)
        assert entered.exists()
    try:
        if fault:
            with pytest.raises((ValueError, OSError)):
                if fault == "different_request":
                    engine.observe(
                        world["project"],
                        state["run_id"],
                        "native_worker",
                        {"check_id": "foreign-check"},
                        expected_revision=state["revision"],
                        command_id="native-attempt",
                        actor=world["actor"],
                        runtime_root=world["runtime"],
                    )
                else:
                    observe(engine, world, state)
            assert tail(engine, world, state) == state
        else:
            final = observe(engine, world, state)
            assert final["native_execution"]["native-attempt"]["status"] == "completed"
            assert (
                final["native_execution"]["native-attempt"]["nonce"]
                == json.loads(raw)["nonce"]
            )
            assert path.read_bytes() == raw and path.stat().st_ino == before.st_ino
            assert (
                len(list((world["project"] / "resources/review-output").iterdir())) == 1
            )
            assert (
                sum(
                    row["command"] == "native.execution.dispatch"
                    for row in engine._events(world["project"], state["run_id"])
                )
                == 1
            )
    finally:
        if holder is not None:
            holder.kill()
            holder.join(2)
            assert not holder.is_alive()


def test_reused_process_identity_never_substitutes_for_exclusive_original_lease(
    facade, engine, world, monkeypatch
):
    state, dead = interrupted(facade, engine, world, monkeypatch)
    state = tail(engine, world, state)
    path = engine._check_native_lease(
        world["project"], state["native_execution"]["native-attempt"]
    )
    entered = world["scratch"] / "new-custodian"

    def holder():
        with engine.bounded_lock(path, create=False):
            entered.write_text(str(os.getpid()))
            time.sleep(15)

    process = multiprocessing.get_context("fork").Process(target=holder)
    process.start()
    until = time.monotonic() + 5
    while not entered.exists() and time.monotonic() < until:
        time.sleep(0.02)
    assert entered.exists() and process.pid != dead.pid
    try:
        # Even though the recorded observer PID is dead, another holder of its
        # exact inode forbids recovery. PID liveness never grants custody.
        response = recover(facade, engine, world, state, "held-by-new-process")
        assert (
            response["status"] == "UNRESOLVED" and tail(engine, world, state) == state
        )
    finally:
        process.kill()
        process.join(2)
    response = recover(facade, engine, world, state, "released-exact-lease")
    assert (
        tail(engine, world, state)["native_execution"]["native-attempt"]["status"]
        == "completed"
    ), response


@pytest.mark.parametrize("terminal", ["completed", "cancelled"])
def test_late_custody_does_not_reopen_successful_or_cancelled_intervals(
    engine, world, terminal
):
    from test_run_state import verified

    state, _ = verified(engine, world)
    state = command(
        engine,
        world,
        state,
        "close",
        {"status": terminal, "reason": "Synthetic terminal positive"},
    )
    assert state["status"] == terminal
    with pytest.raises(ValueError):
        command(
            engine,
            world,
            state,
            "native.execution.recover",
            {"intent_id": "unbound-original"},
        )
    with pytest.raises(ValueError):
        command(
            engine,
            world,
            state,
            "workflow.return",
            {
                "child_id": "unbound-child",
                "disposition": "failed",
                "artifact_ids": [],
                "evidence_ids": [],
                "reason": "Unbound",
            },
        )
    assert tail(engine, world, state) == state


@pytest.mark.parametrize("boundary_name", ["receipt", "constraint"])
def test_recovery_rechecks_original_plan_at_final_commit_fence(
    facade, engine, world, monkeypatch, boundary_name
):
    state, p = interrupted(facade, engine, world, monkeypatch)
    state = tail(engine, world, state)
    original = world["plan"].read_text()
    if boundary_name == "receipt":
        verifier = boundary.verify_worker_observation
        count = 0

        def changed(*args, **kwargs):
            nonlocal count
            value = verifier(*args, **kwargs)
            count += 1
            if count == 2:
                world["plan"].write_text(
                    original + "\nChanged after final receipt readback\n"
                )
            return value

        monkeypatch.setattr(boundary, "verify_worker_observation", changed)
    else:

        def changed(*args, **kwargs):
            if args[1] == "native.execution.recover":
                world["plan"].write_text(
                    original + "\nChanged during constraint check\n"
                )

        monkeypatch.setitem(engine._CONSTRAINTS, "fixture-final-source-change", changed)
    response = recover(facade, engine, world, state)
    assert response["status"] == "UNRESOLVED", response
    assert tail(engine, world, state) == state


def test_copied_board_cannot_prepare_original_native_custody(
    facade, engine, world, monkeypatch
):
    state = configured(facade, engine, world, monkeypatch)
    copied = world["scratch"] / "copied-board.md"
    copied.write_bytes(world["board"].read_bytes())
    actor = {**world["actor"], "board": str(copied)}
    with pytest.raises(ValueError):
        engine.observe(
            world["project"],
            state["run_id"],
            "native_worker",
            {"check_id": "check"},
            expected_revision=state["revision"],
            command_id="native-attempt",
            actor=actor,
            runtime_root=world["runtime"],
        )
    assert tail(engine, world, state) == state
    assert not list(
        engine._home(world["project"], state["run_id"]).glob(".native-*.lock")
    )


def test_pre_dispatch_absence_cannot_follow_an_aliased_attempt_parent(
    facade, engine, world, monkeypatch
):
    state, p = interrupted(facade, engine, world, monkeypatch, phase="prepared")
    state = tail(engine, world, state)
    foreign = world["scratch"] / "unrelated-empty"
    foreign.mkdir()
    parent = engine._home(world["project"], state["run_id"]) / "native-worker-attempts"
    parent.symlink_to(foreign, target_is_directory=True)
    with pytest.raises(ValueError):
        command(
            engine,
            world,
            state,
            "native.execution.recover",
            {"intent_id": "native-attempt"},
        )
    assert tail(engine, world, state) == state and not list(foreign.iterdir())


# Receipt and absence proof must survive every final append boundary.

def retain(world, name, before, after, response, mutations):
    (world['scratch'] / (name + '.json')).write_text(json.dumps({
        'before': before, 'after': after, 'response': response,
        'mutations': mutations, 'native_provider_calls': 0,
        'injection': 'File mutation synchronized at the existing registered guard after receipt verification; no owner/admission bypass.'
    }, indent=2) + '\n')


@pytest.mark.parametrize('fault', ['none', 'receipt', 'stdout'])
def test_recovery_rechecks_exact_receipt_after_constraints(facade, engine, world, monkeypatch, fault):
    initial, observer = interrupted(facade, engine, world, monkeypatch)
    assert observer.exitcode == 0 and not observer.is_alive()
    before = tail(engine, world, initial)
    attempt = world['project'] / 'resources/autopilot-runs' / before['run_id'] / 'native-worker-attempts/child'
    calls = []
    def mutation(state, operation, payload, context):
        if operation != 'native.execution.recover':
            return
        calls.append(fault)
        if fault == 'receipt':
            path = attempt / 'receipt.json'
            value = json.loads(path.read_text())
            value['data']['usage']['tokens'] = 0
            path.write_text(json.dumps(value))
        elif fault == 'stdout':
            path = attempt / 'stdout.jsonl'
            path.write_bytes(path.read_bytes() + b'\n{"unverified":"late mutation"}\n')
    engine.register_constraint('review-late-receipt', mutation)
    try:
        response = recover(facade, engine, world, initial)
    finally:
        engine.unregister_constraint('review-late-receipt')
    after = tail(engine, world, initial)
    retain(world, 'late-receipt-' + fault, before, after, response, calls)
    assert calls == [fault]
    if fault == 'none':
        assert after['native_execution']['native-attempt']['status'] == 'completed'
        assert after['observations']['native-attempt']['data']['usage']['tokens'] == 6
    else:
        assert after == before, 'Changed original receipt/raw custody must refuse before the original result append'


@pytest.mark.parametrize('create_attempt', [False, True])
def test_prepared_absence_is_rechecked_at_final_append(facade, engine, world, monkeypatch, create_attempt):
    initial, observer = interrupted(facade, engine, world, monkeypatch, phase='prepared')
    assert observer.exitcode == 0 and not observer.is_alive()
    before = tail(engine, world, initial)
    attempt = world['project'] / 'resources/autopilot-runs' / before['run_id'] / 'native-worker-attempts/child'
    assert not attempt.exists()
    calls = []
    def mutation(state, operation, payload, context):
        if operation == 'native.execution.recover':
            calls.append(create_attempt)
            if create_attempt:
                attempt.mkdir(parents=True)
                (attempt / 'unexpected-custody').write_text('Concurrent synthetic attempt marker')
    engine.register_constraint('review-late-attempt', mutation)
    try:
        response = recover(facade, engine, world, initial)
    finally:
        engine.unregister_constraint('review-late-attempt')
    after = tail(engine, world, initial)
    retain(world, 'late-attempt-' + str(create_attempt), before, after, response, calls)
    assert calls == [create_attempt]
    if create_attempt:
        assert after == before, 'New attempt custody invalidates the original no-dispatch absence proof'
    else:
        assert after['native_execution']['native-attempt']['status'] == 'not_started'
        assert 'native-attempt' not in after.get('observations', {})


def mutate_attempt(world, state, fault):
    attempt = (world['project'] / 'resources/autopilot-runs' / state['run_id']
               / 'native-worker-attempts/child')
    if fault == 'receipt':
        p = attempt / 'receipt.json'
        data = json.loads(p.read_text())
        data['data']['usage']['tokens'] = 0
        p.write_text(json.dumps(data))
    elif fault == 'stdout':
        p = attempt / 'stdout.jsonl'
        p.write_bytes(p.read_bytes() + b'\n{"unverified":"late mutation"}\n')
    elif fault == 'attempt':
        attempt.mkdir(parents=True)
        (attempt / 'unexpected-custody').write_text('Synthetic concurrent custody')


@pytest.mark.parametrize('fault', ['none', 'receipt', 'stdout'])
def test_live_result_rechecks_receipt_after_constraints(facade, engine, world, monkeypatch, fault):
    initial = configured(facade, engine, world, monkeypatch)
    calls = []

    def mutation(state, operation, payload, context):
        if operation == 'observe:native_worker':
            calls.append(fault)
            mutate_attempt(world, state, fault)

    engine.register_constraint('adjacent-live-custody', mutation)
    error = None
    try:
        observe(engine, world, initial)
    except ValueError as exc:
        error = str(exc)
    finally:
        engine.unregister_constraint('adjacent-live-custody')
    after = tail(engine, world, initial)
    (world['scratch'] / ('live-commit-' + fault + '.json')).write_text(json.dumps({
        'calls': calls, 'error': error, 'state': after, 'native_provider_calls': 0,
    }, indent=2) + '\n')
    assert calls == [fault]
    if fault == 'none':
        assert error is None
        assert after['native_execution']['native-attempt']['status'] == 'completed'
        assert after['observations']['native-attempt']['data']['usage']['tokens'] == 6
    else:
        assert error, 'Mutated retained custody must refuse the ordinary result commit'
        assert after['native_execution']['native-attempt']['status'] == 'pending'
        assert 'native-attempt' not in after.get('observations', {})


@pytest.mark.parametrize('fault', ['none', 'receipt', 'stdout', 'attempt'])
def test_recovery_ack_checks_custody_after_original_commit(facade, engine, world, monkeypatch, fault):
    phase = 'prepared' if fault == 'attempt' else 'receipt'
    initial, observer = interrupted(facade, engine, world, monkeypatch, phase=phase)
    assert observer.exitcode == 0 and not observer.is_alive()
    before = tail(engine, world, initial)
    actual = engine._append
    calls = []

    def append_then_mutate(*args, **kwargs):
        value = actual(*args, **kwargs)
        if args[2] == 'native-attempt':
            calls.append(fault)
            mutate_attempt(world, before, fault)
        return value

    monkeypatch.setattr(engine, '_append', append_then_mutate)
    response = recover(facade, engine, world, initial)
    after = tail(engine, world, initial)
    events = list(engine._events(world['project'], initial['run_id']))
    acks = [x for x in events if x['command'] == 'native.execution.recover']
    (world['scratch'] / ('ack-commit-' + fault + '.json')).write_text(json.dumps({
        'calls': calls, 'response': response, 'state': after,
        'ack_ids': [x['command_id'] for x in acks], 'native_provider_calls': 0,
    }, indent=2) + '\n')
    assert calls == [fault]
    assert sum(x['command_id'] == 'native-attempt' for x in events) == 1
    assert after['native_execution']['native-attempt']['status'] == (
        'not_started' if fault == 'attempt' else 'completed')
    if fault == 'none':
        assert len(acks) == 1
    else:
        assert not acks, 'Late custody change must not receive a recovery acknowledgement'
        assert after['revision'] == before['revision'] + 1
