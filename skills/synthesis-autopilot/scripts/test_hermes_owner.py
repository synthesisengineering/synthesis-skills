"""Real PM/worker/registry/reader/vendor consumers; synthetic local native producer."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
import test_run_state as run_fixture
from test_workflow import _owner_register
from test_vendor_native import fixture_source
import hermes_transport
import vendor_native
import vendor_bundle
from test_hermes_transport import short_native_root

__all__ = ["short_native_root"]

world = run_fixture.world
command = run_fixture.command


@pytest.fixture
def observed(world, monkeypatch, request, short_native_root):
    import autopilot
    import workflow
    import test_workflow
    from test_run_admission import write_board, git

    sys.path.insert(
        0, str(Path(__file__).resolve().parents[2] / "synthesis-onboarding/scripts")
    )
    from system_contract import canonical_tree_digest
    import sqlite3

    w = world
    native_root = short_native_root
    git(native_root, "init", "-b", "main")
    scratch = native_root / "s"
    scratch.mkdir()
    output = w["project"] / "o"
    output.mkdir()
    write_board(
        w,
        claims=f"{w['project']}/**; {native_root}/**",
        workspace=f"{w['repo']} @ main; {native_root} @ main",
    )
    root = fixture_source(w["project"] / "release")
    state_home = w["project"] / "registry"
    state_home.mkdir(mode=0o700)
    home = w["project"] / "hermes"
    home.mkdir(mode=0o700)
    with sqlite3.connect(home / "state.db") as db:
        db.execute(
            "CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, parent_session_id TEXT, started_at REAL, ended_at REAL, cwd TEXT, profile_name TEXT)"
        )
        db.execute(
            "INSERT INTO sessions VALUES (?,?,?,?,?,?,?)",
            (
                "session-opaque-1",
                "cli",
                None,
                time.time(),
                None,
                str(w["project"]),
                "default",
            ),
        )
    (home / "state.db").chmod(0o600)
    producer = w["project"] / "producer.py"
    conf = Path(__file__).resolve().parents[2] / "synthesis-agent-conformance/scripts"
    producer.write_text(
        """import json,sys,os\nfrom pathlib import Path\nsys.path.insert(0,"""
        + repr(str(conf))
        + """)\nimport hermes_adapter as adapter\nq=json.loads(Path(sys.argv[1]).read_text())\nos.environ['HERMES_HOME']=q['home']\nadapter.recover=lambda *a:"Synthetic project context"\nresult=adapter.handle(q['payload'],Path(q['home']),Path(q['index']),'alpha',active=q['active'],state_home=Path(q['state_home']),capture_socket=Path(q['socket']))\nprint(json.dumps(result))\n"""
    )
    packet = w["project"] / "packet.json"
    parent = hermes_transport.process_identity(os.getpid())
    hookargv = [parent["argv"][0], str(producer), str(packet)]
    pins = {}
    for arg in [*parent["argv"], *hookargv]:
        if (
            arg.startswith("/")
            and Path(arg).is_file()
            and (arg.endswith(".py") or os.access(arg, os.X_OK))
        ):
            pins[arg] = hashlib.sha256(Path(arg).read_bytes()).hexdigest()
    chosen = {
        "schema": 1,
        "client": "hermes",
        "session_id": "session-opaque-1",
        "profile_home": str(home),
        "state_home": str(state_home),
        "profile": "default",
        "cwd": str(w["project"]),
        "process": parent,
        "hook_argv": hookargv,
        "source_files": pins,
        "producer_version": "synthetic-official-contract",
    }
    runtime = autopilot.engine()
    workflow.register_preparers(runtime.register_preparer)
    state = run_fixture.create(runtime, w)
    state = command(
        runtime, w, state, "native.enroll", {"source_handle": "root", "mode": "native"}
    )
    state = command(
        runtime,
        w,
        state,
        "workflow.configure",
        {"dimensions": test_workflow.dimensions(parallelizable=False)},
    )
    state = command(
        runtime,
        w,
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
        runtime,
        w,
        state,
        "workflow.budget",
        {
            "limits": {"wall_millis": {"limit": 60000, "enforcement": "hard"}},
            "deadline": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        },
    )
    for ident, category, n in [
        ("worker-budget", "work", 30000),
        ("audit-budget", "integration", 10000),
        ("verification-budget", "verification", 10000),
        ("recovery-budget", "recovery", 10000),
    ]:
        state = command(
            runtime,
            w,
            state,
            "workflow.reserve",
            {
                "reservation_id": ident,
                "amounts": {"wall_millis": n},
                "category": category,
            },
        )
    state = _owner_register(runtime, w, state, "hermes-selection", chosen)
    path = w["project"] / "hermes-selection.json"
    roles = {
        "schema_version": 1,
        "immutable_inputs": [
            {
                "artifact_id": "hermes-selection",
                "path": str(path),
                "digest": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        ],
        "output_roots": [str(output)],
        "scratch_root": str(scratch),
    }
    paths = [str(output), str(scratch)]
    brief = {
        "child_id": "hermes-observe",
        "task_id": "work",
        "deliverables": ["Observe exact synthetic context consumption"],
        "paths": paths,
        "criteria": ["accept"],
        "reservation_id": "worker-budget",
        "integration_reservation_id": "audit-budget",
        "verification_reservation_id": "verification-budget",
        "recovery_reservation_id": "recovery-budget",
        "integration_owner": state["owner"]["session_uuid"],
        "return_contract": ["artifact_ids", "evidence_ids", "disposition"],
        "cancellation": "Retain partial observations",
        "mode": "native-cli",
        "client": "hermes",
        "required_capabilities": [hermes_transport.CAPABILITY],
        "file_contract": roles,
        "admission_id": "parent",
        "admission_requests": [{"id": "parent", "actor": w["actor"], "paths": paths}],
    }
    state = command(runtime, w, state, "workflow.dispatch", brief)
    state = _owner_register(
        runtime,
        w,
        state,
        "observe-spec",
        {
            "schema_version": 1,
            "kind": "native_worker",
            "arguments": {"child_id": "hermes-observe", "timeout_seconds": 10},
        },
    )
    result = []
    errors = []
    active = {
        "release_root": str(root),
        "version": "1.2.3",
        "content_digest": canonical_tree_digest(root),
    }
    socket = scratch / "hook.sock"

    def producer_calls():
        try:
            until = time.monotonic() + 4
            while not socket.exists() and time.monotonic() < until:
                time.sleep(0.01)
            payload = {
                "hook_event_name": "pre_llm_call",
                "session_id": chosen["session_id"],
                "cwd": chosen["cwd"],
                "profile": "default",
                "extra": {"turn_id": "t1"},
            }
            q = {
                "home": str(home),
                "state_home": str(state_home),
                "index": str(w["repo"] / "projects/index.yaml"),
                "active": active,
                "socket": str(socket),
                "payload": payload,
            }
            packet.write_text(json.dumps(q))
            done = subprocess.run(hookargv, capture_output=True, timeout=4)
            assert done.returncode == 0, done.stderr
            out = json.loads(done.stdout)
            assert "SYNTHESIS_NATIVE_RECEIPT " in out.get("context", ""), out
            result.append(out)
            payload["hook_event_name"] = "pre_api_request"
            payload["extra"] = {
                "turn_id": "t1",
                "api_request_id": "a1",
                "request": {
                    "method": "POST",
                    "body": {
                        "messages": [
                            {"role": "user", "content": "Question\n\n" + out["context"]}
                        ]
                    },
                },
            }
            if getattr(request, "param", None) in {"large-raw", "medium-raw"}:
                payload["extra"]["retained_auxiliary"] = "X" * (
                    800000 if request.param == "large-raw" else 80000
                )
            packet.write_text(json.dumps(q))
            done = subprocess.run(hookargv, capture_output=True, timeout=4)
            assert done.returncode == 0 and json.loads(done.stdout) == {}, (
                done.stdout + done.stderr
            )
        except BaseException as ex:
            errors.append(repr(ex))

    worker = threading.Thread(target=producer_calls)
    worker.start()
    try:
        state = runtime.observe(
            w["project"],
            state["run_id"],
            "native_worker",
            {"check_id": "observe-spec"},
            expected_revision=state["revision"],
            command_id="observed",
            actor=w["actor"],
            runtime_root=w["runtime"],
        )
    finally:
        worker.join(12)
        assert not worker.is_alive()
    assert not errors, errors
    state = command(
        runtime,
        w,
        state,
        "workflow.worker_record",
        {"child_id": "hermes-observe", "receipt_id": "observed"},
    )
    child = state["extensions"]["workflow"]["children"]["hermes-observe"]
    assert child["worker_observation"]["terminal"] == "completed", Path(
        child["worker_observation"]["receipt_path"]
    ).read_text()
    state = command(
        runtime,
        w,
        state,
        "native.enroll",
        {"source_handle": "worker:hermes-observe", "mode": "native"},
    )
    state = command(
        runtime,
        w,
        state,
        "native.observe",
        {
            "source_handle": "worker:hermes-observe",
            "through_event": None,
            "task_id": "work",
            "attempt_id": None,
        },
    )
    ext = state["extensions"]["native_observations"]
    batch = ext["latest_batch"]
    if getattr(request, "param", None) == "large-raw":
        assert any(gap["code"] == "oversized_record" for gap in batch["gaps"])
    else:
        assert not batch["gaps"] and not batch["diagnostics"], batch
    ids = [e["event_id"] for e in batch["events"] if e["kind"] == "runtime.hook"]
    assert len(ids) == (1 if getattr(request, "param", None) == "large-raw" else 2)
    selection = {
        "project": str(w["project"]),
        "run_id": state["run_id"],
        "actor": w["actor"],
        "source_handle": "worker:hermes-observe",
        "source_generation": ext["sources"]["worker:hermes-observe"]["binding"][
            "generation"
        ],
        "event_ids": ids,
        "registry_latest": str(state_home),
    }
    witness = json.loads(result[0]["context"].split("SYNTHESIS_NATIVE_RECEIPT ")[1])
    receipt = (
        state_home
        / "agent-conformance/observations/hermes"
        / hashlib.sha256(chosen["session_id"].encode()).hexdigest()
        / (witness["event_id"] + ".json")
    )
    return {
        "root": root,
        "entry": {"plugin_root": str(root), "receipt": str(receipt)},
        "selection": selection,
        "inventory": vendor_bundle.source_inventory(root),
        "state": state,
        "runtime": runtime,
        "world": w,
        "chosen": chosen,
        "worker": child["worker_observation"],
    }


def consume(f):
    return vendor_native.current_callback(
        f["root"], "hermes", f["entry"], "1.2.3", f["inventory"], f["selection"]
    )


def test_real_admitted_hermes_consumer_positive(observed):
    result = consume(observed)
    assert result["status"] == "PASS", result
    assert result["scope"] == "admitted-hermes-context-consumption-only"
    assert (
        result["native_permissions"] == "UNKNOWN"
        and result["model_turn_completed"] is False
    )
    assert result["action_authorized"] is False


@pytest.mark.parametrize(
    "fault",
    [
        "forged-receipt",
        "stale",
        "foreign-generation",
        "foreign-registry",
        "partial-events",
        "mutated-source",
        "mutated-transport",
        "mutated-raw-frame",
        "mutated-frame-index",
    ],
)
def test_current_owner_refuses_substitution(observed, fault):
    f = observed
    assert consume(f)["status"] == "PASS"
    if fault in ("forged-receipt", "stale"):
        p = Path(f["entry"]["receipt"])
        data = json.loads(p.read_bytes())
        data["recorded_at"] = "2000-01-01T00:00:00Z"
        p.write_text(json.dumps(data))
    elif fault == "foreign-generation":
        f["selection"]["source_generation"] = "foreign"
    elif fault == "foreign-registry":
        f["selection"]["registry_latest"] = str(f["world"]["project"])
    elif fault == "partial-events":
        f["selection"]["event_ids"].pop()
    elif fault == "mutated-source":
        (f["root"] / "SKILL.md").write_text("changed")
    elif fault == "mutated-transport":
        p = Path(f["worker"]["receipt_path"]).parent / "stdout.jsonl"
        p.write_bytes(p.read_bytes() + b"{}\n")
    elif fault == "mutated-raw-frame":
        p = Path(f["worker"]["receipt_path"]).parent / "frame-1.bin"
        p.write_bytes(p.read_bytes() + b" ")
    elif fault == "mutated-frame-index":
        p = Path(f["worker"]["receipt_path"]).parent / "transport.json"
        p.write_text('{"frames": []}')
    assert consume(f)["status"] == "UNKNOWN"


def test_observation_completion_requires_integration_audit(observed):
    f = observed
    result = command(
        f["runtime"],
        f["world"],
        f["state"],
        "workflow.return",
        {
            "child_id": "hermes-observe",
            "disposition": "complete",
            "artifact_ids": [],
            "evidence_ids": ["observed"],
            "reason": "Synthetic context observation only; no execution acceptance",
        },
    )
    child = result["extensions"]["workflow"]["children"]["hermes-observe"]
    assert child["audit_status"] == "required"
    assert child["worker_observation"]["boundary"]["status"] == "UNKNOWN"
    assert (
        result["extensions"]["workflow"]["graph"]["nodes"]["work"]["status"]
        == "blocked"
    )


def test_hermes_cannot_advertise_managed_execution():
    import delegation_boundary

    value = delegation_boundary.capability("hermes")
    assert value["operations"] == ["native-context-observation"]
    assert value["write_enforcement"] == "UNAVAILABLE"
    with pytest.raises(ValueError):
        delegation_boundary.validate_requirements("hermes", ["execute"])


@pytest.mark.parametrize("observed", ["large-raw"], indirect=True)
def test_complete_large_raw_frame_reaches_actual_owner(observed):
    # Complete transport custody does not erase a gap from the existing reader
    # with a smaller admitted record bound. No default limit is raised.
    assert observed["worker"]["terminal"] == "completed"
    assert consume(observed)["status"] == "UNKNOWN"
    assert observed["worker"]["model_turns_started"] == 0
    raw = Path(observed["worker"]["receipt_path"]).parent / "frame-1.bin"
    assert 800000 < raw.stat().st_size < hermes_transport.MAX_FRAME


def test_receipt_bool_is_not_zero_started_turns(observed):
    import hermes_worker
    from copy import deepcopy

    data = deepcopy(observed["worker"])
    path = Path(data["receipt_path"])
    receipt = json.loads(path.read_bytes())
    data["model_turns_started"] = False
    receipt["data"]["model_turns_started"] = False
    path.write_text(json.dumps(receipt))
    data["receipt_digest"] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert not hermes_worker.verify(
        data, {"state": observed["state"], "project": observed["world"]["project"]}
    )


@pytest.mark.parametrize("observed", ["medium-raw"], indirect=True)
def test_supported_native_record_size_consumes_exact_bytes(observed):
    assert consume(observed)["status"] == "PASS"


def test_vendor_rechecks_current_session_after_installed_verification(
    observed, monkeypatch
):
    import sqlite3
    import system_contract

    assert consume(observed)["status"] == "PASS"
    original = system_contract.verify_native_release_inventory
    calls = []

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(1)
        if len(calls) == 1:
            with sqlite3.connect(
                Path(observed["chosen"]["profile_home"]) / "state.db"
            ) as database:
                database.execute(
                    "UPDATE sessions SET cwd=?", ("/foreign/current-session",)
                )
        return result

    monkeypatch.setattr(system_contract, "verify_native_release_inventory", changed)
    result = consume(observed)
    assert result["status"] == "UNKNOWN"
    assert "session/profile changed" in result["reason"]
    assert len(calls) == 2
