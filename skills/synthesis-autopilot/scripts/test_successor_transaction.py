"""Synthetic causal successor transactions through real PM and journal owners."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
_fixture = importlib.import_module("test_run_state")
engine, world = _fixture.engine, _fixture.world
create, command, output = _fixture.create, _fixture.command, _fixture.output


def predecessor(engine, world, rows=2, artifacts=1):
    import workflow

    workflow.register_commands(engine.register_command)
    state = create(engine, world)
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
    for index in range(rows):
        state = command(
            engine,
            world,
            state,
            "workflow.reserve",
            {
                "reservation_id": f"r{index}",
                "category": "work",
                "amounts": {"model_tokens": 1000},
            },
        )
        state = command(
            engine,
            world,
            state,
            "workflow.settle",
            {
                "reservation_id": f"r{index}",
                "actual": None if index % 2 else {"model_tokens": 23},
            },
        )
    for index in range(artifacts):
        path = world["project"] / f"input-{index}.txt"
        path.write_text(f"Synthetic retained evidence {index}\n")
        state = command(
            engine,
            world,
            state,
            "artifact.register",
            {
                "id": f"a{index}",
                "path": str(path),
                "role": "evidence",
                "retention": "durable",
                "required": True,
            },
        )
    return command(
        engine,
        world,
        state,
        "close",
        {"status": "incomplete", "reason": "Bounded interval ended"},
    )


def intent(engine, world, old):
    auth = world["project"] / "authorization.txt"
    auth.write_text(
        "Synthetic explicit authority for this project continuation only.\n"
    )
    head = engine._last_event(world["project"], old["run_id"])
    return {
        "predecessor": {
            "run_id": old["run_id"],
            "revision": old["revision"],
            "event_digest": head["digest"],
            "state_digest": engine._digest(old),
            "deadline": old["extensions"]["workflow"]["budget"]["deadline"],
        },
        "deadline": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "authorization_ref": {
            "path": "authorization.txt",
            "digest": hashlib.sha256(auth.read_bytes()).hexdigest(),
        },
    }


def advance(engine, world, request, **kw):
    return engine.create_successor(
        world["project"],
        project_id="alpha",
        intent=request,
        actor=world["actor"],
        command_id="successor-one",
        runtime_root=world["runtime"],
        **kw,
    )


def test_successor_retains_complete_ledger_and_predecessor_bytes(engine, world):
    old = predecessor(engine, world)
    request = intent(engine, world, old)
    home = engine._home(world["project"], old["run_id"])
    before = {
        str(p.relative_to(home)): p.read_bytes() for p in home.rglob("*") if p.is_file()
    }
    new = advance(engine, world, request)
    assert (
        new["run_id"] != old["run_id"]
        and new["status"] == "preparing"
        and new["revision"] == 1
    )
    original = deepcopy(old["extensions"]["workflow"]["budget"])
    original["deadline"] = request["deadline"]
    assert new["extensions"]["workflow"]["budget"] == original
    assert new["artifacts"] == old["artifacts"]
    assert new["contract"] == old["contract"]
    assert new["successor"]["predecessor"] == request["predecessor"]
    assert advance(engine, world, request) == new
    assert before == {
        str(p.relative_to(home)): p.read_bytes() for p in home.rglob("*") if p.is_file()
    }
    assert (
        new["extensions"]["workflow"]["budget"]["reservations"]["r1"]["actual"] is None
    )


def test_successor_controller_and_cli_admit_the_same_existing_owner(engine, world):
    import controller

    old = predecessor(engine, world)
    req = {
        "schema_version": 1,
        "request_id": "successor",
        "operation": "successor",
        "project_id": "alpha",
        "input": intent(engine, world, old),
    }
    response = controller.handle(
        req,
        project=world["project"],
        actor=world["actor"],
        runtime_root=world["runtime"],
    )
    assert response["status"] == "READY", response
    assert response["revision"] == 1
    again = controller.handle(
        req,
        project=world["project"],
        actor=world["actor"],
        runtime_root=world["runtime"],
    )
    assert again["run_id"] == response["run_id"] and again["revision"] == 1


@pytest.mark.parametrize(
    "fault",
    [
        "revision",
        "event_digest",
        "state_digest",
        "deadline",
        "missing",
        "artifact",
        "authorization",
        "expired",
        "limit",
        "unclaimed",
        "native",
    ],
)
def test_successor_refuses_changed_inputs_and_authority_without_commit(
    engine, world, fault
):
    from test_run_admission import write_board

    old = predecessor(engine, world)
    req = intent(engine, world, old)
    if fault in {"revision", "event_digest", "state_digest", "deadline"}:
        ref = req["predecessor"]
        ref[fault] = (
            ref[fault] - 1
            if fault == "revision"
            else "0" * 64
            if fault.endswith("digest")
            else "2000-01-01T00:00:00Z"
        )
    elif fault == "missing":
        (
            engine._home(world["project"], old["run_id"])
            / "events"
            / "000000000002.json"
        ).rename(world["project"] / "retained-event.json")
    elif fault == "artifact":
        (world["project"] / "input-0.txt").write_text("Changed bytes")
    elif fault == "authorization":
        (world["project"] / "authorization.txt").write_text("Changed intent")
    elif fault == "expired":
        req["deadline"] = "2000-01-01T00:00:00Z"
    elif fault == "limit":
        req["limits"] = {"model_tokens": {"limit": 10000000, "enforcement": "forecast"}}
    elif fault == "unclaimed":
        write_board(world, claims=str(world["project"] / "elsewhere/**"))
    elif fault == "native":
        world["actor"]["native_payload"]["session_id"] = (
            "01990000-0000-7000-8000-000000000099"
        )
    with pytest.raises((ValueError, OSError)):
        advance(engine, world, req)
    home = engine._home(
        world["project"], engine.successor_identity(world["project"], old["run_id"])
    )
    assert not (home / "events").exists()


@pytest.mark.parametrize(
    "phase", ["before", "after", "projection", "pending_index", "committed_index"]
)
def test_successor_interrupted_commit_prefix_is_exactly_recoverable(
    engine, world, monkeypatch, phase
):
    old = predecessor(engine, world)
    req = intent(engine, world, old)
    append, project, index = engine._append, engine._project, engine._index_update
    fired = False

    def crash_append(*a, **kw):
        nonlocal fired
        if phase == "before" and not fired:
            fired = True
            raise OSError("Synthetic crash before authoritative event")
        result = append(*a, **kw)
        if phase == "after" and not fired:
            fired = True
            raise OSError("Synthetic crash after authoritative event")
        return result

    def crash_project(*a, **kw):
        nonlocal fired
        if phase == "projection" and not fired:
            fired = True
            raise OSError("Synthetic projection interruption")
        return project(*a, **kw)

    def crash_index(*a, **kw):
        nonlocal fired
        if (
            (phase == "pending_index" and a[-1].get("status") == "pending")
            or (phase == "committed_index" and a[-1].get("status") != "pending")
        ) and not fired:
            fired = True
            if phase == "pending_index":
                index(*a, **kw)
            raise OSError("Synthetic discovery interruption")
        return index(*a, **kw)

    monkeypatch.setattr(engine, "_append", crash_append)
    monkeypatch.setattr(engine, "_project", crash_project)
    monkeypatch.setattr(engine, "_index_update", crash_index)
    with pytest.raises(OSError):
        advance(engine, world, req)
    child_id = engine.successor_identity(world["project"], old["run_id"])
    committed = phase in {"after", "projection", "committed_index"}
    if committed:
        assert engine.load_run(world["project"], child_id)["status"] == "preparing"
    else:
        with pytest.raises(ValueError):
            engine.load_run(world["project"], child_id)
        with pytest.raises(ValueError):
            engine.owned_runs(world["actor"], runtime_root=world["runtime"])
    new = advance(engine, world, req)
    assert new["revision"] == 1
    assert (
        len(list((engine._home(world["project"], new["run_id"]) / "events").iterdir()))
        == 1
    )
    assert advance(engine, world, req) == new
    changed = deepcopy(req)
    changed["deadline"] = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    with pytest.raises(ValueError, match="different"):
        advance(engine, world, changed)


def inject_extension(engine, world, old, transform):
    # Deliberate synthetic trusted-code producer, never a caller receipt.
    def reducer(state, payload, context):
        transform(state["extensions"])
        return state

    engine.register_command("fixture.custody", reducer, terminal_safe=True)
    return command(engine, world, old, "fixture.custody", {})


@pytest.mark.parametrize("fault", ["worker", "audit", "node", "continuation", "launch"])
def test_successor_cannot_orphan_live_registered_custody(engine, world, fault):
    old = predecessor(engine, world)

    def update(ext):
        if fault in {"worker", "audit"}:
            ext["workflow"]["children"]["child"] = {
                "disposition": "running" if fault == "worker" else "completed",
                "audit_status": "required",
            }
        elif fault == "node":
            ext["workflow"]["graph"] = {"nodes": {"active": {"status": "running"}}}
        elif fault == "continuation":
            ext["capabilities"] = {"continuation": {"status": "registered"}}
        else:
            ext["prepared_native_launch"] = {
                "permits": {"launch": {"status": "unknown"}}
            }

    old = inject_extension(engine, world, old, update)
    with pytest.raises(ValueError, match="custody|active|cancellation"):
        advance(engine, world, intent(engine, world, old))


def test_successor_preserves_failures_attempts_and_cancellation_lineages(engine, world):
    old = predecessor(engine, world)

    def update(ext):
        ext["workflow_persistence"] = {
            "schema_version": 1,
            "attempts": [{"attempt_id": "failed-trial", "outcome": "failed"}],
            "rearms": [],
            "cancelled_obligations": ["never-again"],
            "lineages": {"never-again": ["accept"]},
        }
        ext["workflow"]["quality_history"] = {
            "work": [{"passed": False, "reason": "Retained failed experiment"}]
        }

    old = inject_extension(engine, world, old, update)
    new = advance(engine, world, intent(engine, world, old))
    assert (
        new["extensions"]["workflow_persistence"]
        == old["extensions"]["workflow_persistence"]
    )
    assert (
        new["extensions"]["workflow"]["quality_history"]
        == old["extensions"]["workflow"]["quality_history"]
    )
    assert new["evidence"] == old["evidence"]
    assert new["verification"] == old["verification"]


def test_successor_chain_rejects_lost_ancestor_and_retains_old_deadlines(engine, world):
    first = predecessor(engine, world)
    second = advance(engine, world, intent(engine, world, first))
    second = command(
        engine,
        world,
        second,
        "close",
        {"status": "incomplete", "reason": "Second bounded end"},
    )
    req = intent(engine, world, second)
    req["deadline"] = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    third = engine.create_successor(
        world["project"],
        project_id="alpha",
        intent=req,
        actor=world["actor"],
        command_id="successor-two",
        runtime_root=world["runtime"],
    )
    assert (
        engine.load_run(world["project"], first["run_id"])["extensions"]["workflow"][
            "budget"
        ]["deadline"]
        == first["extensions"]["workflow"]["budget"]["deadline"]
    )
    lost = (
        engine._home(world["project"], first["run_id"]) / "events" / "000000000001.json"
    )
    lost.rename(world["project"] / "retained-ancestor.json")
    with pytest.raises(ValueError):
        engine.load_run(world["project"], third["run_id"])


def test_successor_rechecks_revoked_remote_admission(engine, world, monkeypatch):
    from test_run_admission import write_board

    old = predecessor(engine, world)
    req = intent(engine, world, old)
    admit = engine.admit_paths
    calls = []

    def revoked(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            write_board(world, status="released")
        return admit(*args, **kwargs)

    monkeypatch.setattr(engine, "admit_paths", revoked)
    with pytest.raises(ValueError):
        advance(engine, world, req)
    assert len(calls) == 2
    assert not (
        engine._home(
            world["project"], engine.successor_identity(world["project"], old["run_id"])
        )
        / "events"
    ).exists()


def test_successor_concurrent_competitors_cannot_duplicate_child(engine, world):
    import subprocess

    old = predecessor(engine, world)
    req = intent(engine, world, old)
    data = world["scratch"] / "competitors.json"
    data.write_text(
        json.dumps(
            {
                "project": str(world["project"]),
                "runtime": str(world["runtime"]),
                "intent": req,
                "actor": world["actor"],
            }
        )
    )
    source = Path(engine.__file__).parent
    script = """import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import run_state
v=json.loads(Path(sys.argv[2]).read_text())
s=run_state.create_successor(Path(v['project']),project_id='alpha',intent=v['intent'],actor=v['actor'],command_id='successor-one',runtime_root=Path(v['runtime']))
print(json.dumps(s,sort_keys=True))
"""
    processes = []
    try:
        for _ in range(2):
            processes.append(
                subprocess.Popen(
                    [sys.executable, "-c", script, str(source), str(data)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            )
        outputs = [p.communicate(timeout=30) for p in processes]
        assert all(p.returncode == 0 for p in processes), outputs
        values = [json.loads(out) for out, _ in outputs]
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
            for stream in (proc.stdout, proc.stderr):
                stream.close()
        (world["scratch"] / "PROCESS_DISPOSITIONS.json").write_text(
            json.dumps(
                [
                    {
                        "pid": proc.pid,
                        "returncode": proc.returncode,
                        "reaped": proc.returncode is not None,
                    }
                    for proc in processes
                ]
            )
        )
    assert values[0] == values[1]
    assert (
        len(
            list(
                (
                    engine._home(world["project"], values[0]["run_id"]) / "events"
                ).iterdir()
            )
        )
        == 1
    )


@pytest.mark.parametrize("limit", ["elapsed", "depth", "bytes"])
def test_successor_declared_bounds_fail_before_event(engine, world, monkeypatch, limit):
    old = predecessor(engine, world)
    req = intent(engine, world, old)
    monkeypatch.setattr(
        engine,
        {
            "elapsed": "MAX_SUCCESSOR_SECONDS",
            "depth": "MAX_SUCCESSOR_DEPTH",
            "bytes": "MAX_SUCCESSOR_ARTIFACT_BYTES",
        }[limit],
        0,
    )
    with pytest.raises(ValueError, match="bound|depth"):
        advance(engine, world, req)


def test_successor_observed_effect_remains_unresolved_until_its_real_owner_reconciles(
    engine, world
):
    old = create(engine, world)
    import workflow

    workflow.register_commands(engine.register_command)
    old = command(
        engine,
        world,
        old,
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
    old = command(
        engine,
        world,
        old,
        "workflow.budget",
        {
            "limits": {"model_tokens": {"limit": 1000, "enforcement": "forecast"}},
            "deadline": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
    )
    old = command(
        engine,
        world,
        old,
        "effect.prepare",
        {
            "id": "publication",
            "target": "synthetic-target",
            "payload_digest": "a" * 64,
            "idempotency_key": "one-publication",
            "authority_ref": "",
        },
    )
    old = command(
        engine,
        world,
        old,
        "close",
        {"status": "incomplete", "reason": "Unresolved effect retained"},
    )
    with pytest.raises(ValueError, match="effect custody"):
        advance(engine, world, intent(engine, world, old))


def test_successor_rechecks_evidence_changed_during_last_admission(
    engine, world, monkeypatch
):
    old = predecessor(engine, world)
    req = intent(engine, world, old)
    admit = engine.admit_paths
    calls = []

    def changing(*args, **kwargs):
        result = admit(*args, **kwargs)
        calls.append(1)
        if len(calls) == 2:
            (world["project"] / "input-0.txt").write_text(
                "Changed while remote admission ran"
            )
        return result

    monkeypatch.setattr(engine, "admit_paths", changing)
    with pytest.raises(ValueError, match="changed during final"):
        advance(engine, world, req)
    assert not (
        engine._home(
            world["project"], engine.successor_identity(world["project"], old["run_id"])
        )
        / "events"
    ).exists()


@pytest.mark.parametrize("fault", ["cycle", "missing", "undercount", "dimension"])
def test_successor_rejects_malformed_ledger_without_refunding(engine, world, fault):
    old = predecessor(engine, world)

    def corrupt(ext):
        rows = ext["workflow"]["budget"]["reservations"]
        if fault == "cycle":
            rows["r1"]["parent_id"] = "r1"
        elif fault == "missing":
            rows["r1"]["parent_id"] = "absent"
        elif fault == "undercount":
            rows["r1"]["status"] = "settled"
        else:
            rows["r1"]["amounts"] = {}

    old = inject_extension(engine, world, old, corrupt)
    with pytest.raises(ValueError, match="budget|reservation|ancestry"):
        advance(engine, world, intent(engine, world, old))


def test_successor_retained_shape_179_reservations_68_artifacts_needs_two_fences(
    engine, world, monkeypatch
):
    import run_admission
    import time
    import workflow

    workflow.register_commands(engine.register_command)
    state = create(engine, world)
    snapshot = run_admission._snapshot
    calls = []

    def counted(*args, **kwargs):
        calls.append(bool(kwargs.get("readonly", False)))
        return snapshot(*args, **kwargs)

    monkeypatch.setattr(run_admission, "_snapshot", counted)
    start = time.monotonic()
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
    for index in range(179):
        state = command(
            engine,
            world,
            state,
            "workflow.reserve",
            {
                "reservation_id": f"r{index}",
                "category": "work",
                "amounts": {"model_tokens": 1000},
            },
        )
    for index in range(88):
        state = command(
            engine,
            world,
            state,
            "workflow.settle",
            {
                "reservation_id": f"r{index}",
                "actual": None if index % 2 else {"model_tokens": 23},
            },
        )
    for index in range(68):
        path = world["project"] / f"evidence-{index}.txt"
        path.write_text(f"Synthetic preserved input {index}\\n")
        state = command(
            engine,
            world,
            state,
            "artifact.register",
            {
                "id": f"e{index}",
                "path": str(path),
                "role": "evidence",
                "retention": "durable",
                "required": True,
            },
        )
    state = command(
        engine,
        world,
        state,
        "workflow.graph",
        {
            "nodes": [
                {"id": "work", "deps": [], "criteria": ["accept"], "estimate": 1}
            ],
            "wip_limit": 1,
        },
    )
    state = command(
        engine,
        world,
        state,
        "progress",
        {"summary": "Synthetic ordinary restoration complete"},
    )
    ordinary = {
        "seconds": time.monotonic() - start,
        "mutating_snapshots": calls.count(False),
        "commands": 339,
    }
    assert ordinary["mutating_snapshots"] == 678
    state = command(
        engine,
        world,
        state,
        "close",
        {"status": "incomplete", "reason": "Measured ordinary prefix"},
    )
    req = intent(engine, world, state)
    calls.clear()
    start = time.monotonic()
    new = advance(engine, world, req)
    successor = {
        "seconds": time.monotonic() - start,
        "mutating_snapshots": calls.count(False),
        "commands": 1,
    }
    assert successor["mutating_snapshots"] == 2
    expected = deepcopy(state["extensions"]["workflow"]["budget"])
    expected["deadline"] = req["deadline"]
    assert new["extensions"]["workflow"]["budget"] == expected
    assert new["artifacts"] == state["artifacts"]
    assert workflow.budget_summary(new) == workflow.budget_summary(state)
    result = {
        "scope": "Synthetic local PM transport; counts are actual calls to the remote-capable admission owner, not fabricated remote latency.",
        "ordinary": ordinary,
        "successor": successor,
        "reservations": 179,
        "artifacts": 68,
        "budget_summary_equal": True,
        "exact_ledger_except_new_deadline": True,
        "artifact_metadata_equal": True,
        "unknown_actuals_retained": True,
    }
    (world["scratch"] / "MEASUREMENT.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


def test_successor_old_successful_verification_remains_historical(engine, world):
    import workflow

    old = create(engine, world)
    old, _ = output(engine, world, old)
    old = command(engine, world, old, "transition", {"status": "verifying"})
    old = command(engine, world, old, "verify", {"criteria": ["accept"]})
    assert (
        engine.criterion_report(
            old, engine.inspect_context(old, world["actor"], project=world["project"])
        )["status"]
        == "PASS"
    )
    workflow.register_commands(engine.register_command)
    old = command(
        engine,
        world,
        old,
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
    old = command(
        engine,
        world,
        old,
        "workflow.budget",
        {
            "limits": {"model_tokens": {"limit": 1000, "enforcement": "forecast"}},
            "deadline": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
    )
    old = command(
        engine,
        world,
        old,
        "close",
        {"status": "incomplete", "reason": "Retain prior verified outcome"},
    )
    new = advance(engine, world, intent(engine, world, old))
    assert new["verification"] == old["verification"]
    assert (
        engine.criterion_report(
            new, engine.inspect_context(new, world["actor"], project=world["project"])
        )["status"]
        == "FAIL"
    )


def test_successor_exact_cli_entry_executes_existing_owner(
    engine, world, monkeypatch, capsys
):
    import autopilot

    old = predecessor(engine, world)
    req = {
        "schema_version": 1,
        "request_id": "cli-successor",
        "operation": "successor",
        "project_id": "alpha",
        "input": intent(engine, world, old),
    }
    request_file, actor_file = (
        world["scratch"] / "request.json",
        world["scratch"] / "actor.json",
    )
    request_file.write_text(json.dumps(req))
    actor_file.write_text(json.dumps(world["actor"]))
    monkeypatch.setenv("SYNTHESIS_AUTOPILOT_RUNTIME", str(world["runtime"]))
    assert (
        autopilot.main(
            [
                "successor",
                "--project",
                str(world["project"]),
                "--request",
                str(request_file),
                "--actor",
                str(actor_file),
            ]
        )
        == 0
    )
    response = json.loads(capsys.readouterr().out)
    assert response["status"] == "READY"
    assert (
        engine.load_run(world["project"], response["run_id"])["successor"][
            "predecessor"
        ]
        == req["input"]["predecessor"]
    )


def test_successor_predecessor_replacement_during_final_admission_refuses_atomically(
    engine, world, monkeypatch
):
    old = predecessor(engine, world)
    req = intent(engine, world, old)
    admit = engine.admit_paths
    calls = []

    def changing(*args, **kwargs):
        result = admit(*args, **kwargs)
        calls.append(1)
        if len(calls) == 2:
            path = (
                engine._home(world["project"], old["run_id"])
                / "events"
                / "000000000001.json"
            )
            raw = path.read_bytes()
            path.rename(world["scratch"] / "retained-original-event.json")
            path.write_bytes(raw)
        return result

    monkeypatch.setattr(engine, "admit_paths", changing)
    with pytest.raises(ValueError, match="changed during final"):
        advance(engine, world, req)
    assert not (
        engine._home(
            world["project"], engine.successor_identity(world["project"], old["run_id"])
        )
        / "events"
    ).exists()


def test_successor_zero_retry_and_changed_authority_after_committed_event_preserve_prefix(
    engine, world, monkeypatch
):
    from test_run_admission import write_board

    old = predecessor(engine, world)
    req = intent(engine, world, old)
    original = engine._project

    def crash(*args, **kwargs):
        raise OSError("Synthetic retained committed event")

    monkeypatch.setattr(engine, "_project", crash)
    with pytest.raises(OSError):
        advance(engine, world, req)
    child_id = engine.successor_identity(world["project"], old["run_id"])
    committed = engine.load_run(world["project"], child_id)
    write_board(world, status="released")
    monkeypatch.setattr(engine, "_project", original)
    with pytest.raises(ValueError):
        advance(engine, world, req)
    assert engine.load_run(world["project"], child_id) == committed
    assert not (engine._home(world["project"], child_id) / "current.json").exists()


@pytest.mark.parametrize("fault", ["symlink", "fifo", "oversize"])
def test_successor_artifact_special_files_refuse_without_reading_target(
    engine, world, fault
):
    import os

    old = predecessor(engine, world)
    req = intent(engine, world, old)
    path = world["project"] / "input-0.txt"
    path.rename(world["scratch"] / "retained-input.txt")
    if fault == "symlink":
        path.symlink_to(world["scratch"] / "retained-input.txt")
    elif fault == "fifo":
        os.mkfifo(path)
    else:
        with path.open("wb") as stream:
            stream.truncate(64 * 1024 * 1024 + 1)
    with pytest.raises((ValueError, OSError)):
        advance(engine, world, req)


@pytest.mark.parametrize("committed", [False, True])
@pytest.mark.parametrize("change", ["plan", "claim", "history"])
def test_successor_fresh_final_fence_includes_recovery(
    engine, world, monkeypatch, committed, change
):
    old = predecessor(engine, world)
    req = intent(engine, world, old)
    if committed:
        project = engine._project
        monkeypatch.setattr(
            engine,
            "_project",
            lambda *a: (_ for _ in ()).throw(OSError("Interrupted projection")),
        )
        with pytest.raises(OSError):
            advance(engine, world, req)
        monkeypatch.setattr(engine, "_project", project)
    admit, calls = engine.admit_paths, []

    def changed(*args, **kw):
        proof = admit(*args, **kw)
        calls.append(1)
        if len(calls) == 2:
            if change == "claim":
                proof["claim_hash"] = "0" * 64
            elif change == "plan":
                path = engine._plan(world["project"], old["plan"]).resolved
                path.write_text(path.read_text() + "\nNew material instruction\n")
            else:
                path = (
                    engine._home(world["project"], old["run_id"])
                    / "events"
                    / "000000000001.json"
                )
                raw = path.read_bytes()
                path.rename(world["scratch"] / "original-event.json")
                path.write_bytes(raw)
        return proof

    monkeypatch.setattr(engine, "admit_paths", changed)
    with pytest.raises(ValueError, match="changed"):
        advance(engine, world, req)
    home = engine._home(
        world["project"], engine.successor_identity(world["project"], old["run_id"])
    )
    assert len(list((home / "events").glob("*.json"))) == int(committed)


@pytest.mark.parametrize("where", ["predecessor", "authorization_ref"])
def test_successor_nested_intent_is_closed(engine, world, where):
    old = predecessor(engine, world)
    req = intent(engine, world, old)
    req[where]["admission_requests"] = []
    with pytest.raises(ValueError, match="unknown"):
        advance(engine, world, req)


def test_successor_retains_waits_and_hard_quota_without_running(engine, world):
    import workflow

    old = create(engine, world)
    workflow.register_commands(engine.register_command)
    old = command(
        engine,
        world,
        old,
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
    old = command(
        engine,
        world,
        old,
        "workflow.budget",
        {
            "limits": {"model_tokens": {"limit": 10, "enforcement": "hard"}},
            "deadline": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
    )
    old = command(
        engine,
        world,
        old,
        "workflow.reserve",
        {
            "reservation_id": "spent",
            "category": "work",
            "amounts": {"model_tokens": 10},
        },
    )
    old = command(
        engine,
        world,
        old,
        "wait.add",
        {"id": "human", "kind": "user", "reason": "Physical user action"},
    )
    old = command(
        engine,
        world,
        old,
        "close",
        {"status": "incomplete", "reason": "Waiting for the user"},
    )
    new = advance(engine, world, intent(engine, world, old))
    assert new["waits"] == old["waits"]
    assert workflow.budget_summary(new) == workflow.budget_summary(old)
    with pytest.raises(ValueError):
        command(
            engine,
            world,
            new,
            "workflow.reserve",
            {
                "reservation_id": "more",
                "category": "work",
                "amounts": {"model_tokens": 1},
            },
        )
    with pytest.raises(ValueError, match="wait"):
        command(engine, world, new, "transition", {"status": "running"})


@pytest.mark.parametrize("stage", ["pending", "committed"])
@pytest.mark.parametrize("change", ["plan", "claim", "request"])
def test_successor_interrupted_basis_cannot_change_between_attempts(
    engine, world, monkeypatch, stage, change
):
    from test_run_admission import write_board

    old = predecessor(engine, world, rows=0, artifacts=0)
    req = intent(engine, world, old)
    target = "_append" if stage == "pending" else "_project"
    original = getattr(engine, target)

    def crash(*args, **kwargs):
        raise OSError("Retained interrupted transaction prefix")

    monkeypatch.setattr(engine, target, crash)
    with pytest.raises(OSError):
        advance(engine, world, req)
    monkeypatch.setattr(engine, target, original)
    if change == "plan":
        world["plan"].write_text(
            world["plan"].read_text() + "\nDifferent human instructions\n"
        )
    elif change == "claim":
        write_board(world, claims=str(world["repo"]) + "/**")
    else:
        req = deepcopy(req)
        req["deadline"] = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    with pytest.raises(ValueError, match="changed|different"):
        advance(engine, world, req)


def test_successor_different_board_cannot_copy_the_native_seat(engine, world):
    old = predecessor(engine, world, rows=0, artifacts=0)
    req = intent(engine, world, old)
    path = world["scratch"] / "other-board.md"
    path.write_bytes(world["board"].read_bytes())
    world["actor"]["board"] = str(path)
    with pytest.raises(ValueError, match="owner"):
        advance(engine, world, req)


def test_successor_slow_index_cannot_age_commit_deadline(engine, world, monkeypatch):
    old = predecessor(engine, world, rows=0, artifacts=0)
    req = intent(engine, world, old)
    original = engine._native_index_update

    def delay(*args, **kwargs):
        original(*args, **kwargs)
        monkeypatch.setattr(
            engine,
            "_now",
            lambda: (
                datetime.fromisoformat(req["deadline"]) + timedelta(seconds=1)
            ).isoformat(),
        )

    monkeypatch.setattr(engine, "_native_index_update", delay)
    with pytest.raises(ValueError, match="expired"):
        advance(engine, world, req)
    child = engine.successor_identity(world["project"], old["run_id"])
    assert not (engine._home(world["project"], child) / "events").exists()


@pytest.mark.parametrize("before", [True, False])
def test_successor_freezes_parent_before_terminal_observer_effect(engine, world, before):
    old = predecessor(engine, world, rows=0, artifacts=1)
    calls = []
    def observe(context, payload):
        calls.append(payload)
        return {"status": "cancelled"}
    engine.register_observer("continuation-cancellation", observe, terminal_safe=True)
    def cleanup():
        return engine.observe(world["project"], old["run_id"], "continuation-cancellation", {"check_id": "a0"}, expected_revision=old["revision"], command_id="terminal-cleanup", actor=world["actor"], runtime_root=world["runtime"])
    if before:
        updated = cleanup()
        new = advance(engine, world, intent(engine, world, updated))
        assert len(calls) == 1
    else:
        new = advance(engine, world, intent(engine, world, old))
        with pytest.raises(ValueError, match="successor.*immutable"):
            cleanup()
        assert calls == []
        assert engine.load_run(world["project"], old["run_id"]) == old
    assert engine.load_run(world["project"], new["run_id"]) == new



@pytest.mark.parametrize("staging", [False, True])
def test_successor_streams_physical_entries_before_sort(engine, world, monkeypatch, staging):
    import os
    from contextlib import contextmanager
    from types import SimpleNamespace
    old = predecessor(engine, world, rows=0, artifacts=0)
    req = intent(engine, world, old)
    directory = engine._home(world["project"], old["run_id"]) / "events"
    original = os.scandir
    identity = directory.stat().st_ino
    seen = []
    monkeypatch.setattr(engine, "MAX_EVENTS", 20)
    def corpus():
        for index in range(22):
            seen.append(index)
            assert index <= 20, "physical bound checked after unbounded materialization"
            yield SimpleNamespace(name=f".run-{index}" if staging else f"{index + 1:012d}.json")
    @contextmanager
    def entries(path):
        if type(path) is int and os.fstat(path).st_ino == identity:
            yield corpus()
        else:
            with original(path) as rows:
                yield rows
    monkeypatch.setattr(os, "scandir", entries)
    with pytest.raises(ValueError, match="enumeration limit"):
        advance(engine, world, req)
    assert len(seen) == 21


def test_events_never_materialize_directory_via_listdir(engine, world, monkeypatch):
    import os
    old = predecessor(engine, world, rows=0, artifacts=0)
    def refused(*args, **kwargs):
        raise AssertionError("unbounded listdir was used")
    monkeypatch.setattr(os, "listdir", refused)
    assert engine.load_run(world["project"], old["run_id"]) == old


def test_events_descriptor_identity_change_refuses(engine, world, monkeypatch):
    import os
    from contextlib import contextmanager
    old = predecessor(engine, world, rows=0, artifacts=0)
    directory = engine._home(world["project"], old["run_id"]) / "events"
    identity = directory.stat().st_ino
    original = os.scandir
    @contextmanager
    def changing(fd):
        with original(fd) as rows:
            yield rows
        if type(fd) is int and os.fstat(fd).st_ino == identity:
            (directory / ".run-retained-new-entry").write_text("Retained competing directory mutation")
    monkeypatch.setattr(os, "scandir", changing)
    with pytest.raises(ValueError, match="changed during enumeration"):
        engine.load_run(world["project"], old["run_id"])


@pytest.mark.parametrize("shape", ["empty", "committed", "corrupt"])
def test_successor_prefix_discovery_streams_and_retains_refusals(engine, world, monkeypatch, shape):
    old = predecessor(engine, world, rows=0, artifacts=0)
    req = intent(engine, world, old)
    home = engine._home(world["project"], engine.successor_identity(world["project"], old["run_id"]))
    if shape == "committed":
        committed = advance(engine, world, req)
    else:
        (home / "events").mkdir(parents=True)
        if shape == "corrupt":
            (home / "events" / "unexpected").write_text("Retained corruption")
    original = Path.iterdir
    def forbidden(path):
        if path == home / "events":
            raise AssertionError("successor prefix used materializing Path.iterdir")
        return original(path)
    monkeypatch.setattr(Path, "iterdir", forbidden)
    if shape == "corrupt":
        with pytest.raises(ValueError, match="unexpected|gap"):
            advance(engine, world, req)
        assert (home / "events" / "unexpected").read_text() == "Retained corruption"
    else:
        result = advance(engine, world, req)
        assert result["status"] == "preparing"
        if shape == "committed":
            assert result == committed


def test_ordinary_creation_replay_uses_the_same_bounded_prefix(engine, world, monkeypatch):
    original = create(engine, world)
    directory = engine._home(world["project"], original["run_id"]) / "events"
    previous = Path.iterdir
    def forbidden(path):
        if path == directory:
            raise AssertionError("ordinary create replay materialized the directory")
        return previous(path)
    monkeypatch.setattr(Path, "iterdir", forbidden)
    assert create(engine, world) == original
