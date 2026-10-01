"""Real PM/admission/worker/journal/registry path; synthetic local producer only."""

from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import pytest
import test_run_state as run_fixtures

engine = run_fixtures.engine
world = run_fixtures.world
command = run_fixtures.command
create = run_fixtures.create
from test_native_callback import config, records, SID  # noqa: E402
from test_vendor_native import fixture_source, consumer, bundle  # noqa: E402


@pytest.fixture
def admitted_codex(world, monkeypatch, request):
    import autopilot
    import workflow
    import delegation_boundary as boundary
    from test_workflow import dimensions, _owner_register
    from evaluation_artifacts import _sandbox_command
    from live_receipt import receipt_event_path

    fault = getattr(request, "param", None)
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
    configuration = config(scratch)
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
            "required_capabilities": ["native-callback"],
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
    rows = records(configuration, "Synthetic delivered context\n" + witness)
    if fault == "partial-coverage":
        from test_native_callback import hook

        others = []
        for i in range(255):
            for kind in ("running", "completed"):
                row = hook(kind, context="Additional synthetic callback")
                row["params"]["run"]["id"] = "additional-" + str(i)
                others.append(row)
        rows[-1:-1] = others

    for row in rows[1:-1]:
        row["params"]["run"]["sourcePath"] = str(root / "hooks/hooks.json")
    if fault == "untrusted-source":
        for row in rows[1:3]:
            row["params"]["run"]["source"] = "user"
    emitter = delegated / "emitter.py"
    emitter.write_text(
        "import json,sys\nrows="
        + repr(rows)
        + "\nfor line in sys.stdin:\n r=json.loads(line)\n"
        + ' if r.get("method")=="initialize": print(json.dumps(rows[0]),flush=True)\n'
        + ' elif r.get("method")=="thread/start":\n'
        + "  for row in rows[1:]: print(json.dumps(row),flush=True)\n"
    )
    argv = _sandbox_command(world["project"], scratch, emitter, [])[0]
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
    else:
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


def consume(f):
    return consumer.current_callback(
        f["root"], "codex", f["entry"], "1.2.3", f["inventory"], f["selection"]
    )


def test_actual_owner_codex_callback_reaches_vendor_consumer(admitted_codex):
    result = consume(admitted_codex)
    assert result["status"] == "PASS", result
    assert result["scope"] == "admitted-ephemeral-callback-context"
    assert (
        result["model_turn_completed"] is False
        and result["native_recovery"] == "UNKNOWN"
    )
    assert result["action_authorized"] is False


@pytest.mark.parametrize(
    "fault",
    [
        "foreign-session",
        "registry-bytes",
        "source",
        "generation",
        "event",
        "request",
        "raw",
        "claim",
        "expired",
        "executable",
    ],
)
def test_actual_codex_owner_refuses_changed_or_foreign_evidence(
    admitted_codex, fault, monkeypatch
):
    f = admitted_codex
    assert consume(f)["status"] == "PASS"
    if fault in ("foreign-session", "registry-bytes"):
        receipt = deepcopy(f["receipt"])
        receipt["session_id"] = "foreign"
        f["path"].write_text(json.dumps(receipt))
    if fault == "source":
        (f["root"] / "SKILL.md").write_text("Changed after observation")
    if fault == "generation":
        f["selection"]["source_generation"] = "foreign"
    if fault == "event":
        f["selection"]["event_ids"][0] = "sha256:" + "0" * 64
    if fault in ("request", "raw"):
        child = f["state"]["extensions"]["workflow"]["children"]["callback"]
        base = Path(child["worker_observation"]["receipt_path"]).parent
        target = base / ("requests.jsonl" if fault == "request" else "stdout.jsonl")
        target.write_bytes(target.read_bytes() + b"{}\n")
    if fault == "executable":
        (f["world"]["project"] / "delegated/fixture-native").write_text(
            "changed producer bytes"
        )
    if fault == "claim":
        from test_run_admission import write_board

        write_board(f["world"], claims=str(f["world"]["project"] / "other") + "/**")
    if fault == "expired":

        class Future(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.now(tz) + timedelta(minutes=6)

        monkeypatch.setattr(consumer, "datetime", Future)
    assert consume(f)["status"] == "UNKNOWN"


@pytest.mark.parametrize("admitted_codex", ["untrusted-source"], indirect=True)
def test_user_callback_cannot_impersonate_installed_plugin(admitted_codex):
    assert consume(admitted_codex)["status"] == "UNKNOWN"


@pytest.mark.parametrize(
    "admitted_codex",
    ["stale-candidate", "forged-marker", "replayed-marker"],
    indirect=True,
)
def test_actual_captured_marker_cannot_launder_a_stale_or_forged_candidate(
    admitted_codex,
):
    assert consume(admitted_codex)["status"] == "UNKNOWN"


@pytest.mark.parametrize("admitted_codex", ["partial-coverage"], indirect=True)
def test_partial_observed_capture_requires_real_catchup_before_pass(admitted_codex):
    f = admitted_codex
    assert consume(f)["status"] == "UNKNOWN"
    state = command(
        f["runtime"],
        f["world"],
        f["state"],
        "native.observe",
        {
            "source_handle": "worker:callback",
            "through_event": None,
            "task_id": "work",
            "attempt_id": None,
        },
    )
    batch = state["extensions"]["native_observations"]["latest_batch"]
    session = [e for e in batch["events"] if e["kind"] == "session.started"]
    assert len(session) == 1
    f["selection"]["event_ids"][-1] = session[0]["event_id"]
    f["state"] = state
    assert consume(f)["status"] == "PASS"
