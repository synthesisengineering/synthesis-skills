"""Real PM/admission/worker/journal/registry path; synthetic local producer only."""

from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import pytest
import test_run_state as run_fixtures

engine = run_fixtures.engine
world = run_fixtures.world
command = run_fixtures.command
create = run_fixtures.create
from test_native_callback import SID  # noqa: E402
from test_vendor_native import fixture_source, consumer, bundle  # noqa: E402


@pytest.fixture
def admitted_managed(world, monkeypatch, request):
    import autopilot
    import workflow
    import delegation_boundary as boundary
    from test_workflow import dimensions, _owner_register
    from evaluation_artifacts import _sandbox_command
    from live_receipt import receipt_event_path

    fault = getattr(request, "param", None)
    productive = fault == "productive"
    root = fixture_source(world["scratch"] / "release")
    latest = world["scratch"] / "registry/latest.json"
    latest.parent.mkdir()
    import session_context

    monkeypatch.setenv("SYNTHESIS_HOME", str(world["scratch"] / "system-state"))
    monkeypatch.setenv("SYNTHESIS_CALLBACK_OBSERVATION", "codex-ephemeral-callback")
    monkeypatch.setattr(
        session_context, "plugin_identity", lambda: ("1.2.3", str(root))
    )
    monkeypatch.setattr(session_context, "execution_root", lambda: root)
    payload = {
        "session_id": SID,
        "hook_event_name": "SessionStart",
        "cwd": str(world["project"]),
        "source": "startup",
    }
    assert session_context.record_live_receipt(payload, latest)
    receipt = session_context.record_context_outcome(
        payload, latest, "INJECTED", "Synthetic context", return_record=True
    )
    eid = receipt["receipt_event_id"]
    path = receipt_event_path(latest, client="codex", session_id=SID, event_id=eid)
    assert receipt["callback_candidate"] is True and not latest.exists()
    runtime = autopilot.engine()
    workflow.register_preparers(runtime.register_preparer)
    state = create(runtime, world)
    for kind, payload in [
        ("native.enroll", {"source_handle": "root", "mode": "native"}),
        ("workflow.configure", {"dimensions": dimensions(parallelizable=False)}),
        (
            "workflow.graph",
            {
                "nodes": [
                    {"id": "work", "deps": [], "criteria": ["accept"], "estimate": 1}
                ],
                "wip_limit": 1,
            },
        ),
        (
            "workflow.budget",
            {
                "limits": {"wall_millis": {"limit": 60000, "enforcement": "hard"}},
                "deadline": (
                    datetime.now(timezone.utc) + timedelta(minutes=5)
                ).isoformat(),
            },
        ),
    ]:
        state = command(runtime, world, state, kind, payload)
    for identity, category, amount in [
        ("work-budget", "work", 30000),
        ("integrate", "integration", 10000),
        ("verify", "verification", 10000),
        ("recover", "recovery", 10000),
    ]:
        state = command(
            runtime,
            world,
            state,
            "workflow.reserve",
            {
                "reservation_id": identity,
                "amounts": {"wall_millis": amount},
                "category": category,
            },
        )
    delegated = world["project"] / "delegated"
    scratch = delegated / "scratch"
    scratch.mkdir(parents=True)
    from test_managed_permissions import (
        managed,
        Echo,
        successful_observation,
        rows as managed_rows,
    )
    import native_protection
    import hashlib
    import shlex

    configuration, _, _, probe_spec = managed.__wrapped__(delegated)
    if productive:
        configuration["required_capabilities"] = ["read"]
    scratch = Path(configuration["file_contract"]["scratch_root"])
    emitter = delegated / "emitter.py"
    argv = _sandbox_command(
        world["project"],
        Path(configuration["file_contract"]["output_roots"][0]),
        emitter,
        [],
    )[0]
    launcher = delegated / "fixture-native"
    launcher.write_text("#!/bin/sh\nexec " + shlex.join(argv) + "\n")
    launcher.chmod(0o700)
    profile = configuration["file_contract"]["permissions"]["profile"]
    profile["native_executable"] = {
        "path": str(launcher),
        "sha256": hashlib.sha256(launcher.read_bytes()).hexdigest(),
        "size": launcher.stat().st_size,
    }
    configuration["executable_identity"] = profile["native_executable"]
    inputs = configuration["file_contract"]["immutable_inputs"]
    files = {x["artifact_id"]: Path(x["path"]) for x in inputs}
    files["policy"].write_text(json.dumps(profile))
    probe_spec["filesystem"]["profile_sha256"] = boundary.digest(profile)
    files["spec"].write_text(json.dumps(probe_spec))
    files["reference"].write_text(
        json.dumps(
            {
                "path": str(files["spec"]),
                "sha256": hashlib.sha256(files["spec"].read_bytes()).hexdigest(),
            }
        )
    )
    for item in inputs:
        item["digest"] = hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest()
        state = command(
            runtime,
            world,
            state,
            "artifact.register",
            {
                "id": item["artifact_id"],
                "path": item["path"],
                "role": "input",
                "required": False,
                "retention": "durable",
            },
        )
    monkeypatch.setattr(
        native_protection.socket, "create_connection", lambda *a, **k: Echo()
    )
    state = command(
        runtime,
        world,
        state,
        "workflow.dispatch",
        {
            "child_id": "callback",
            "task_id": "work",
            "deliverables": ["Observe one synthetic callback through the real owner"],
            "paths": [str(delegated)],
            "criteria": ["accept"],
            "reservation_id": "work-budget",
            "integration_reservation_id": "integrate",
            "verification_reservation_id": "verify",
            "recovery_reservation_id": "recover",
            "integration_owner": state["owner"]["session_uuid"],
            "return_contract": ["artifact_ids", "evidence_ids", "disposition"],
            "cancellation": "Retain exact partial callback transport",
            "mode": "native-cli",
            "client": "codex",
            "required_capabilities": configuration["required_capabilities"],
            "file_contract": configuration["file_contract"],
            "admission_id": "parent",
            "admission_requests": [
                {"id": "parent", "actor": world["actor"], "paths": [str(delegated)]}
            ],
        },
    )
    if fault == "stale-candidate":
        receipt["recorded_at"] = (
            datetime.now(timezone.utc) - timedelta(minutes=6)
        ).isoformat()
        path.write_text(json.dumps(receipt))
    witness = consumer.callback_witness(receipt, latest)
    if fault == "forged-marker":
        witness = consumer.PREFIX + json.dumps({"event_id": eid, "sha256": "0" * 64})
    if fault == "replayed-marker":
        import uuid

        witness = consumer.PREFIX + json.dumps(
            {"event_id": str(uuid.uuid4()), "sha256": "0" * 64}
        )
    rows = managed_rows(
        configuration,
        outcome={
            "exitCode": 0,
            "stdout": json.dumps(successful_observation(probe_spec)),
            "stderr": "",
        },
    )
    rows[3]["params"]["run"]["entries"][0]["text"] = (
        "Synthetic delivered context\n" + witness
    )
    if fault == "partial-coverage":
        from test_native_callback import hook

        others = []
        for i in range(255):
            for kind in ("running", "completed"):
                row = hook(kind, context="Additional synthetic callback")
                row["params"]["run"]["id"] = "additional-" + str(i)
                others.append(row)
        rows[-1:-1] = others

    for row in rows:
        if row.get("method", "").startswith("hook/"):
            row["params"]["run"]["sourcePath"] = str(root / "hooks/hooks.json")
    if fault == "untrusted-source":
        for row in rows:
            if row.get("method", "").startswith("hook/"):
                row["params"]["run"]["source"] = "user"
    target = next(
        x["path"]
        for x in probe_spec["filesystem"]["controls"]
        if x["operation"] == "allowed-create"
    )
    emitter.write_text(
        "import json,sys,pathlib\nrows="
        + repr(rows)
        + "\nfor line in sys.stdin:\n r=json.loads(line)\n"
        + " if r.get('method')=='initialize': print(json.dumps(rows[0]),flush=True)\n"
        + " elif r.get('method')=='config/read': print(json.dumps(rows[1] if r['id']==2 else rows[-2]),flush=True)\n"
        + " elif r.get('method')=='thread/start':\n  for row in rows[2:5]: print(json.dumps(row),flush=True)\n"
        + " elif r.get('method')=='command/exec':\n  pathlib.Path("
        + repr(target)
        + ").write_bytes(b'SYNTHESIS-STUDY-ALLOWED-WRITE\\n')\n  print(json.dumps(rows[-1]),flush=True)\n"
    )
    if productive:
        from test_managed_permissions import config_read, reply

        emitter.write_text(
            "import json,sys,pathlib\nrows="
            + repr(rows)
            + "\nconfig="
            + repr(config_read(configuration))
            + "\nthread="
            + repr(reply(configuration)["thread"])
            + "\n"
            "for line in sys.stdin:\n r=json.loads(line)\n m=r.get('method')\n v=None\n"
            " if m=='initialize': v=rows[0]['result']\n"
            " elif m=='config/read': v=config\n"
            " elif m=='thread/start':\n  v=rows[-3]['result']\n  for row in rows[2:4]: print(json.dumps(row),flush=True)\n"
            " elif m=='command/exec':\n  pathlib.Path("
            + repr(target)
            + ").write_bytes(b'SYNTHESIS-STUDY-ALLOWED-WRITE\\n')\n  v=rows[-1]['result']\n"
            " elif m=='thread/read': v={'thread':dict(thread,status={'type':'idle'})}\n"
            " elif m=='turn/start': v={'turn':{'id':'owner-turn'}}\n"
            " if v is not None: print(json.dumps({'id':r['id'],'result':v}),flush=True)\n"
            " if m=='turn/start':\n"
            "  for status,method in [('inProgress','turn/started'),('completed','turn/completed')]: print(json.dumps({'method':method,'params':{'threadId':thread['id'],'turn':{'id':'owner-turn','status':status,'items':[]}}}),flush=True)\n"
        )
    argv = _sandbox_command(
        world["project"],
        Path(configuration["file_contract"]["output_roots"][0]),
        emitter,
        [],
    )[0]
    # Only the actual native executable is replaced by a confined local fixture.
    # PM admission, configuration, transport, receipt, journal and reader stay real.
    launcher = delegated / "fixture-native"
    import shlex

    launcher.write_text("#!/bin/sh\nexec " + shlex.join(argv) + "\n")
    launcher.chmod(0o700)
    monkeypatch.setattr(
        boundary,
        "client_selection",
        lambda *a: (configuration["selected"], str(launcher)),
    )
    import native_resume
    import hashlib

    monkeypatch.setattr(
        native_resume,
        "binary_identity",
        lambda p: {
            "path": str(p),
            "sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest(),
            "size": Path(p).stat().st_size,
        },
    )
    state = _owner_register(
        runtime,
        world,
        state,
        "worker-spec",
        {
            "schema_version": 1,
            "kind": "native_worker",
            "arguments": {"child_id": "callback", "timeout_seconds": 5},
        },
    )
    state = runtime.observe(
        world["project"],
        state["run_id"],
        "native_worker",
        {"check_id": "worker-spec"},
        expected_revision=state["revision"],
        command_id="executed",
        actor=world["actor"],
        runtime_root=world["runtime"],
    )
    state = command(
        runtime,
        world,
        state,
        "workflow.worker_record",
        {"child_id": "callback", "receipt_id": "executed"},
    )
    child = state["extensions"]["workflow"]["children"]["callback"]
    assert child["worker_observation"]["terminal"] == "completed", child[
        "worker_observation"
    ]
    assert child["worker_observation"]["boundary"]["status"] == "ENFORCED"
    state = command(
        runtime,
        world,
        state,
        "native.enroll",
        {"source_handle": "worker:callback", "mode": "native"},
    )
    state = command(
        runtime,
        world,
        state,
        "native.observe",
        {
            "source_handle": "worker:callback",
            "through_event": None,
            "task_id": "work",
            "attempt_id": None,
        },
    )
    ext = state["extensions"]["native_observations"]
    batch = ext["latest_batch"]
    assert not batch["gaps"] and not batch["diagnostics"], batch
    ids = [e["event_id"] for e in batch["events"]]
    if fault == "partial-coverage":
        assert 2 < len(ids) < 513
        assert not any(e["kind"] == "session.started" for e in batch["events"])
        assert ext["sources"]["worker:callback"]["coverage"]["backlog_bytes"] > 0
    elif not productive:
        assert len(ids) == 3
    selection_ids = ids if fault != "partial-coverage" else [ids[0], ids[1], ids[-1]]
    return {
        "root": root,
        "path": path,
        "receipt": receipt,
        "runtime": runtime,
        "state": state,
        "world": world,
        "inventory": bundle.source_inventory(root),
        "entry": {"plugin_root": str(root), "receipt": str(path)},
        "selection": {
            "project": str(world["project"]),
            "run_id": state["run_id"],
            "actor": world["actor"],
            "source_handle": "worker:callback",
            "source_generation": ext["sources"]["worker:callback"]["binding"][
                "generation"
            ],
            "event_ids": selection_ids,
            "registry_latest": str(latest),
        },
    }


def test_registered_managed_probe_reaches_native_vendor_and_completion(
    admitted_managed,
):
    f = admitted_managed
    result = consumer.current_callback(
        f["root"], "codex", f["entry"], "1.2.3", f["inventory"], f["selection"]
    )
    assert result["status"] == "PASS", result
    source = f["state"]["extensions"]["native_observations"]["sources"][
        "worker:callback"
    ]
    assert source["binding"]["producer"]["dialect"] == "codex.app_server_managed"
    state = command(
        f["runtime"],
        f["world"],
        f["state"],
        "workflow.return",
        {
            "child_id": "callback",
            "disposition": "complete",
            "artifact_ids": [],
            "evidence_ids": ["executed"],
            "reason": "Source-only actual registered probe consumer acceptance",
        },
    )
    child = state["extensions"]["workflow"]["children"]["callback"]
    assert child["disposition"] == "complete" and child["audit_status"] == "required"
    # Invalid copied receipt cannot authenticate itself after current source changes.
    path = Path(child["file_contract"]["permissions"]["source"]["path"])
    path.write_text("{}")
    assert (
        consumer.current_callback(
            f["root"], "codex", f["entry"], "1.2.3", f["inventory"], f["selection"]
        )["status"]
        == "UNKNOWN"
    )


@pytest.mark.parametrize(
    "admitted_managed",
    ["forged-marker", "replayed-marker", "untrusted-source"],
    indirect=True,
)
def test_managed_probe_cannot_authenticate_foreign_hook(admitted_managed):
    f = admitted_managed
    assert (
        consumer.current_callback(
            f["root"], "codex", f["entry"], "1.2.3", f["inventory"], f["selection"]
        )["status"]
        == "UNKNOWN"
    )


@pytest.mark.parametrize("admitted_managed", ["productive"], indirect=True)
def test_registered_managed_productive_turn_reaches_native_vendor_and_return(
    admitted_managed,
):
    f = admitted_managed
    result = consumer.current_callback(
        f["root"], "codex", f["entry"], "1.2.3", f["inventory"], f["selection"]
    )
    assert result["status"] == "PASS", result
    assert result["model_turn_completed"] is True
    state = command(
        f["runtime"],
        f["world"],
        f["state"],
        "workflow.return",
        {
            "child_id": "callback",
            "disposition": "complete",
            "artifact_ids": [],
            "evidence_ids": ["executed"],
            "reason": "Source-only actual registered productive consumer acceptance",
        },
    )
    assert (
        state["extensions"]["workflow"]["children"]["callback"]["disposition"]
        == "complete"
    )
