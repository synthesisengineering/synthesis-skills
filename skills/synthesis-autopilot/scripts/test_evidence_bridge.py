"""Production evidence observers use actual temporary PM/native/file state."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"))
from test_run_admission import world, write_board  # noqa: F401
from test_run_state import create, command, contract  # noqa: E402


@pytest.fixture
def bridge():
    return importlib.import_module("evidence_bridge")


@pytest.fixture
def observed(world):
    engine = importlib.import_module("run_state")
    state = create(engine, world)
    return {"project": world["project"], "state": state, "binding": state["owner"],
            "actor": world["actor"], "now": datetime.now(timezone.utc).isoformat(), "artifacts": {}}


def record(kind, data, ctx):
    now = datetime.fromisoformat(ctx["now"])
    return {"kind": kind, "data": data, "observed_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
            "bindings": {**ctx["binding"], **{k: ctx["state"][k] for k in ("run_id", "contract_digest", "profile_digest")}}}


@pytest.mark.parametrize("kind", ["project-resolution", "native-identity", "claim-ownership"])
def test_local_observation_rederives_live_pm_truth(bridge, observed, kind):
    data = bridge.observe_local(kind, observed)
    assert bridge.verify_source(record(kind, data, observed), observed)
    altered = copy.deepcopy(data)
    key = next(iter(altered))
    altered[key] = "invented"
    assert not bridge.verify_source(record(kind, altered, observed), observed)


def test_changed_registry_or_revoked_claim_invalidates_old_observation(bridge, observed, world):
    data = bridge.observe_local("project-resolution", observed)
    receipt = record("project-resolution", data, observed)
    (world["repo"] / "projects/index.yaml").write_text("- id: other\n  status: active\n")
    assert not bridge.verify_source(receipt, observed)
    (world["repo"] / "projects/index.yaml").write_text("- id: alpha\n  status: active\n")
    write_board(world, status="released")
    assert not bridge.verify_source(receipt, observed)


def test_native_claim_is_not_a_caller_supplied_identity(bridge, observed, world):
    receipt = record("native-identity", bridge.observe_local("native-identity", observed), observed)
    world["transcript"].write_text('{"type":"user","sessionId":"forged"}\n')
    assert not bridge.verify_source(receipt, observed)


def test_working_input_requires_registered_current_bytes_and_no_arbitrary_path(bridge, observed, world):
    path = world["project"] / "input.txt"
    path.write_text("Evidence\n")
    observed["artifacts"]["input"] = {"path": "input.txt", "digest": hashlib.sha256(path.read_bytes()).hexdigest(), "role": "input"}
    data = bridge.observe_local("working-input", observed, artifact_id="input")
    assert bridge.verify_source(record("working-input", data, observed), observed)
    assert not bridge.verify_source(record("working-input", {**data, "path": "/arbitrary/tool-output.json"}, observed), observed)
    path.write_text("Changed\n")
    assert not bridge.verify_source(record("working-input", data, observed), observed)


def append_claude_tool(world, name, arguments, output, call_id="native-call"):
    timestamp = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    with world["transcript"].open("a") as handle:
        handle.write(json.dumps({"type": "assistant", "timestamp": timestamp, "sessionId": world["actor"]["native_payload"]["session_id"],
            "message": {"content": [{"type": "tool_use", "id": call_id, "name": name, "input": arguments}]}}) + "\n")
        handle.write(json.dumps({"type": "user", "timestamp": timestamp, "sessionId": world["actor"]["native_payload"]["session_id"],
            "message": {"content": [{"type": "tool_result", "tool_use_id": call_id, "content": json.dumps(output)}]}}) + "\n")


def test_native_nonexec_tool_result_is_bound_to_actual_call_and_contents(bridge, observed, world):
    result = {"id": "native-job", "status": "ACTIVE"}
    append_claude_tool(world, "CronCreate", {"cron": "*/5 * * * *", "prompt": "Resume run"}, result)
    evidence = bridge.native_tool_observation(observed, "native-call")
    assert evidence["tool"] == "CronCreate"
    assert evidence["result"] == result
    assert not bridge.verify_source(record("capability", {"verified": True}, observed), observed)


def test_arbitrary_exec_output_and_user_pasted_tool_events_are_not_evidence(bridge, observed, world):
    append_claude_tool(world, "Bash", {"command": "echo verified"}, {"status": "PASS"}, "shell")
    assert bridge.native_tool_observation(observed, "shell") is None
    with world["transcript"].open("a") as handle:
        handle.write(json.dumps({"type": "user", "sessionId": world["actor"]["native_payload"]["session_id"],
            "message": {"content": [{"type": "tool_use", "id": "spoof", "name": "CronCreate", "input": {}}]}}) + "\n")
    assert bridge.native_tool_observation(observed, "spoof") is None


def test_native_tool_unknown_or_duplicate_call_is_not_accepted(bridge, observed, world):
    assert bridge.native_tool_observation(observed, "absent") is None
    append_claude_tool(world, "CronCreate", {}, {"id": "a"})
    append_claude_tool(world, "CronCreate", {}, {"id": "b"})
    assert bridge.native_tool_observation(observed, "native-call") is None


def test_delivery_projection_cannot_turn_queued_into_delivered(bridge, observed, world):
    append_claude_tool(world, "mcp__codex_app__send_message_to_thread", {"threadId": "peer", "prompt": "Review run " + observed["state"]["run_id"]},
                       {"status": "queued", "threadId": "peer"})
    data = {"source": {"kind": "native-tool", "call_id": "native-call"},
            "delivery_id": "native-call", "channel": "codex-task", "status": "queued"}
    assert bridge.verify_source(record("delivery", data, observed), observed)
    assert not bridge.verify_source(record("delivery", {**data, "status": "delivered"}, observed), observed)


def test_unobservable_wake_survival_or_effect_stays_unknown(bridge, observed):
    for kind in ("capability", "continuation-wake", "effect-readback", "quality_observation"):
        assert not bridge.verify_source(record(kind, {"verified": True, "status": "PASS"}, observed), observed)


def test_registered_production_source_overrides_test_verifier(bridge, observed, world):
    engine = importlib.import_module("run_state")
    registered = {}
    bridge.register_sources(lambda kind, fn: registered.update({kind: fn}))
    assert {"project-resolution", "native-identity", "claim-ownership", "working-input", "delivery"} <= set(registered)
    assert registered["claim-ownership"](record("claim-ownership", {"verified": True}, observed), observed) is False
    bridge.register_sources(engine.register_evidence_source)
    engine.register_verifier("claim-ownership", lambda proof, bindings: True)
    path = world["project"] / "forged.json"
    path.write_text(json.dumps(record("claim-ownership", {"verified": True}, observed)))
    state = command(engine, world, observed["state"], "artifact.register", {
        "id": "forged", "path": str(path), "role": "evidence", "retention": "durable", "required": False})
    state = command(engine, world, state, "evidence.record", {"id": "forged", "kind": "claim-ownership", "artifact_id": "forged"})
    ctx = engine.inspect_context(state, world["actor"], project=world["project"])
    assert ctx["verify_receipt"]("forged", "claim-ownership", {}) is False


def test_ordinary_local_artifact_task_completes_through_cli_without_verifier_configuration(bridge, world):
    cli = Path(__file__).with_name("autopilot.py")
    actor = world["scratch"] / "actor.json"
    actor.write_text(json.dumps(world["actor"]))
    completion = world["scratch"] / "contract.json"
    completion.write_text(json.dumps(contract()))
    profile = world["scratch"] / "profile.json"
    profile.write_text(json.dumps({"schema": 1, "items": [{"id": "fixture", "required": True, "criterion_ids": ["accept"]}]}))
    env = {**os.environ, "SYNTHESIS_AUTOPILOT_RUNTIME": str(world["runtime"])}
    def run(args):
        done = subprocess.run([sys.executable, str(cli), *args], capture_output=True, text=True, env=env, timeout=15)
        assert done.returncode == 0, done.stderr + done.stdout
        return json.loads(done.stdout)
    state = run(["create", "--project", str(world["project"]), "--project-id", "alpha", "--plan", str(world["plan"]),
                 "--contract", str(completion), "--profile", str(profile), "--actor", str(actor), "--command-id", "cli-create"])
    artifact = world["project"] / "output.txt"
    artifact.write_text("Verified output")
    for name, data in [("artifact.register", {"id": "output", "path": str(artifact), "role": "output", "retention": "durable", "required": True}),
                       ("transition", {"status": "verifying"}), ("verify", {"criteria": ["accept"]}), ("close", {"status": "completed"})]:
        request = world["scratch"] / (name + ".json")
        request.write_text(json.dumps(data))
        state = run(["command", "--project", str(world["project"]), "--run-id", state["run_id"], "--name", name,
                     "--payload", str(request), "--actor", str(actor), "--expected-revision", str(state["revision"]),
                     "--command-id", name])
    assert state["status"] == "completed"


def ready_context(observed, world):
    engine = importlib.import_module("run_state")
    output = world["project"] / "output.txt"
    output.write_text("Actual result\n")
    current = command(engine, world, observed["state"], "artifact.register", {
        "id": "output", "path": str(output), "role": "output", "retention": "durable", "required": True})
    current = command(engine, world, current, "transition", {"status": "verifying"})
    current = command(engine, world, current, "verify", {"criteria": ["accept"]})
    pure = engine.inspect_context(current, world["actor"], project=world["project"])
    current["extensions"]["workflow"] = {"graph": {"nodes": {"build": {"id": "build", "criteria": ["accept"], "status": "running"}}}}
    return {**observed, "state": current, "artifacts": pure["artifacts"],
            "criterion_report": engine.criterion_report(current, pure)}


def test_workflow_completion_and_profile_are_derived_from_current_criteria(bridge, observed, world):
    ctx = ready_context(observed, world)
    data = bridge.observe_workflow("task_completion", ctx, task_id="build")
    assert data["criteria"] == ["accept"]
    assert bridge.verify_source(record("task_completion", data, ctx), ctx)
    assert not bridge.verify_source(record("task_completion", {**data, "criteria": []}, ctx), ctx)
    data = bridge.observe_workflow("profile", ctx)
    assert data["satisfied_items"] == ["fixture"]
    assert bridge.verify_source(record("profile", data, ctx), ctx)


def test_workflow_completion_rechecks_artifact_bytes_after_report(bridge, observed, world):
    ctx = ready_context(observed, world)
    data = bridge.observe_workflow("task_completion", ctx, task_id="build")
    (world["project"] / "output.txt").write_text("Changed result")
    assert not bridge.verify_source(record("task_completion", data, ctx), ctx)


def test_progress_source_binds_actual_input_and_output_digests(bridge, observed, world):
    ctx = ready_context(observed, world)
    data = bridge.observe_workflow("progress_observation", ctx, task_id="build")
    assert data["artifact_digests"] == {"output": ctx["artifacts"]["output"]["digest"]}
    assert bridge.verify_source(record("progress_observation", data, ctx), ctx)
    assert not bridge.verify_source(record("progress_observation", {**data, "negative_finding": True}, ctx), ctx)


def test_native_delivery_wait_metadata_must_appear_in_actual_prompt(bridge, observed, world):
    state = observed["state"]
    state["waits"] = {"review": {"id": "review", "kind": "user", "status": "pending", "reason": "Review"}}
    cap = importlib.import_module("capabilities")
    wait = cap.wait_binding(state)
    args = {"threadId": "peer", "prompt": json.dumps({"run_id": state["run_id"], **wait})}
    append_claude_tool(world, "mcp__codex_app__send_message_to_thread", args,
                       {"status": "delivered", "threadId": "peer"})
    data = {"source": {"kind": "native-tool", "call_id": "native-call"},
            "delivery_id": "native-call", "channel": "codex-task", "status": "delivered", **wait}
    assert bridge.verify_source(record("delivery", data, observed), observed)
    assert not bridge.verify_source(record("delivery", {**data, "wait_ids": ["invented"]}, observed), observed)


def test_continuation_cancellation_requires_actual_native_readback(bridge, observed, world):
    state = observed["state"]
    state["extensions"]["capabilities"] = {"continuation": {"job_id": "job-1", "surface": "claude-code-cli", "binding": {
        **{key: observed["binding"][key] for key in ("project_id", "project_root", "session_uuid", "native_ref", "claim_hash", "repository", "branch")},
        **{key: state[key] for key in ("run_id", "contract_digest", "profile_digest")}}}}
    append_claude_tool(world, "CronDelete", {"id": "job-1"}, {"id": "job-1", "deleted": True}, "delete")
    append_claude_tool(world, "CronList", {}, {"jobs": []}, "readback")
    data = {"source": {"kind": "native-tool", "call_id": "delete", "readback_call_id": "readback"},
            "job_id": "job-1", "cancelled": True}
    assert bridge.verify_source(record("continuation-cancellation", data, observed), observed)
    assert not bridge.verify_source(record("continuation-cancellation", {**data, "job_id": "foreign"}, observed), observed)


def test_authentic_negative_observation_is_not_passing_acceptance(bridge, observed):
    predicates = {}
    bridge.register_acceptance_predicates(lambda kind, fn: predicates.update({kind: fn}))
    criterion = {"id": "accept", "method": "consumer-check", "required": True, "artifact_ids": ["output"]}
    for data in ({"passed": False, "returncode": 1}, {"passed": True, "returncode": 1}, {"passed": False, "returncode": 0}):
        assert not predicates["consumer-check"]({"kind": "consumer-check", "data": data}, observed["state"], criterion, observed)
    positive = {"criterion_id": "accept", "artifact_id": "output", "passed": True,
                "execution": {"returncode": 0, "sandbox_verified": True, "timed_out": False, "output_exceeded": False}}
    assert predicates["consumer-check"]({"kind": "consumer-check", "data": positive}, observed["state"], criterion, observed)
    assert not predicates["continuation-cancellation"]({"kind": "continuation-cancellation", "data": {"cancelled": False}}, observed["state"], criterion, observed)


def test_local_and_recovery_observers_produce_real_core_event_evidence(bridge, observed, world):
    engine = importlib.import_module("run_state")
    cap = importlib.import_module("capabilities")
    bridge.register_sources(engine.register_evidence_source)
    bridge.register_observers(engine.register_observer)
    bridge.register_acceptance_predicates(engine.register_acceptance)
    cap.register_commands(engine.register_command)
    current = observed["state"]
    specs = {"resolver": {"kind": "project-resolution", "arguments": {}},
             "native": {"kind": "native-identity", "arguments": {}},
             "claim": {"kind": "claim-ownership", "arguments": {}},
             "recovery": {"kind": "recovery", "arguments": {"resolver_receipt": "resolver-observation", "native_receipt": "native-observation",
                 "claim_receipt": "claim-observation", "input_receipts": []}}}
    for ident, data in specs.items():
        path = world["project"] / (ident + ".json")
        path.write_text(json.dumps({"schema_version": 1, **data}))
        current = command(engine, world, current, "artifact.register", {"id": ident, "path": str(path), "role": "input", "retention": "durable", "required": False})
    for ident, data in specs.items():
        current = engine.observe(world["project"], current["run_id"], data["kind"], {"check_id": ident},
            actor=world["actor"], command_id=ident + "-observation", expected_revision=current["revision"], runtime_root=world["runtime"])
    ctx = engine.inspect_context(current, world["actor"], project=world["project"])
    assert ctx["verify_receipt"]("recovery-observation", "recovery", {})
    assert current["evidence"]["recovery-observation"]["data"]["remaining"] == ["accept"]
    current = command(engine, world, current, "recovery.record", {"receipt": "recovery-observation"})
    ctx = engine.inspect_context(current, world["actor"], project=world["project"])
    assert cap.status_view(current, ctx)["recovery_status"] == "verified"
    (world["repo"] / "projects/index.yaml").write_text("- id: alpha\n  status: paused\n")
    ctx = engine.inspect_context(current, world["actor"], project=world["project"])
    assert not ctx["verify_receipt"]("resolver-observation", "project-resolution", {})
    assert not ctx["verify_receipt"]("recovery-observation", "recovery", {})


def test_delivery_survives_evidence_bookkeeping_but_not_a_new_wait(bridge, observed, world, monkeypatch):
    engine = importlib.import_module("run_state")
    cap = importlib.import_module("capabilities")
    bridge.register_sources(engine.register_evidence_source)
    cap.register_commands(engine.register_command)
    current = command(engine, world, observed["state"], "wait.add", {"id": "review", "kind": "user", "reason": "Review actual output"})
    ctx = {**observed, "state": current}
    wait = cap.wait_binding(current)
    append_claude_tool(world, "mcp__codex_app__send_message_to_thread",
        {"threadId": "peer", "prompt": json.dumps({"run_id": current["run_id"], **wait})},
        {"status": "delivered", "threadId": "peer"})
    data = {"source": {"kind": "native-tool", "call_id": "native-call"},
            "delivery_id": "native-call", "channel": "codex-task", "status": "delivered", **wait}
    path = world["project"] / "delivery.json"
    path.write_text(json.dumps(record("delivery", data, ctx)))
    current = command(engine, world, current, "artifact.register", {"id": "delivery", "path": str(path), "role": "evidence", "retention": "durable", "required": False})
    current = command(engine, world, current, "evidence.record", {"id": "delivery", "kind": "delivery", "artifact_id": "delivery"})
    current = command(engine, world, current, "delivery.record", {"receipt": "delivery"})
    pure = engine.inspect_context(current, world["actor"], project=world["project"])
    assert cap.wait_delivery_status(current, pure)["delivered"]
    # The original delivery remains an authentic past event while its exact
    # wait and receipt remain current. Intake recency is not a five-minute
    # requirement to send the same waiting-user notification repeatedly.
    later = datetime.fromisoformat(ctx["now"]) + timedelta(minutes=6)
    monkeypatch.setattr(engine, "_now", lambda: later.isoformat())
    pure = engine.inspect_context(current, world["actor"], project=world["project"])
    assert cap.wait_delivery_status(current, pure)["delivered"]
    current = command(engine, world, current, "delivery.record", {"receipt": "delivery"})
    pure = engine.inspect_context(current, world["actor"], project=world["project"])
    assert cap.wait_delivery_status(current, pure)["delivered"]
    for envelope in ("fresh", "backdated"):
        incoming = record("delivery", data, {**ctx, "now": later.isoformat()} if envelope == "fresh" else ctx)
        new_path = world["project"] / (envelope + "-delivery.json")
        new_path.write_text(json.dumps(incoming))
        current = command(engine, world, current, "artifact.register", {"id": envelope, "path": str(new_path), "role": "evidence", "retention": "durable", "required": False})
        current = command(engine, world, current, "evidence.record", {"id": envelope, "kind": "delivery", "artifact_id": envelope})
        with pytest.raises(ValueError, match="receipt"):
            command(engine, world, current, "delivery.record", {"receipt": envelope})
    # Reusing the original receipt ID must not renew an old native event by
    # replacing its envelope with a longer expiry. Preserve exact proof bytes.
    replacement = record("delivery", data, ctx)
    replacement["expires_at"] = (later + timedelta(days=1)).isoformat()
    path.write_text(json.dumps(replacement))
    current = command(engine, world, current, "artifact.register", {"id": "delivery", "path": str(path), "role": "evidence", "retention": "durable", "required": False})
    with pytest.raises(ValueError):
        command(engine, world, current, "evidence.record", {"id": "delivery", "kind": "delivery", "artifact_id": "delivery"})
    pure = engine.inspect_context(current, world["actor"], project=world["project"])
    assert not cap.wait_delivery_status(current, pure)["delivered"]
    path.write_text(json.dumps(record("delivery", data, ctx)))
    current = command(engine, world, current, "artifact.register", {"id": "delivery", "path": str(path), "role": "evidence", "retention": "durable", "required": False})
    monkeypatch.setattr(engine, "_now", lambda: (later + timedelta(hours=2)).isoformat())
    pure = engine.inspect_context(current, world["actor"], project=world["project"])
    assert not cap.wait_delivery_status(current, pure)["delivered"]
    monkeypatch.setattr(engine, "_now", lambda: later.isoformat())
    current = command(engine, world, current, "wait.add", {"id": "publish", "kind": "user", "reason": "Publication choice"})
    pure = engine.inspect_context(current, world["actor"], project=world["project"])
    assert not cap.wait_delivery_status(current, pure)["delivered"]


@pytest.mark.parametrize("custom", [False, True])
def test_codex_literal_native_tool_wrapper_is_observable_without_arbitrary_exec(bridge, observed, world, monkeypatch, custom):
    import run_admission
    native = world["actor"]["native_payload"]["session_id"]
    root = world["scratch"] / "codex"
    root.mkdir()
    transcript = root / "session.jsonl"
    transcript.write_text(json.dumps({"type": "session_meta", "payload": {"id": native}}) + "\n")
    monkeypatch.setenv("CODEX_HOME", str(root))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:" + native)
    world["board"].write_text(world["board"].read_text().replace("| claude |", "| codex |").replace("cc:" + native, "codex:" + native))
    actor = copy.deepcopy(world["actor"])
    actor["native_payload"]["transcript_path"] = str(transcript)
    binding = run_admission.admit_paths(world["board"], "alpha", world["project"], [world["plan"]], actor["native_payload"], readonly=True)
    ctx = {**observed, "actor": actor, "binding": binding}
    source = 'text(await tools.mcp__codex_app__read_thread({"threadId":"peer"}));'
    def append(call_id, code, namespace="functions"):
        payload = {"type": "custom_tool_call" if custom else "function_call", "namespace": namespace, "name": "exec", "call_id": call_id,
                   "input" if custom else "arguments": code if custom else json.dumps({"code": code})}
        result = {"type": "custom_tool_call_output" if custom else "function_call_output", "call_id": call_id, "output": json.dumps({"threadId": "peer", "status": "completed"})}
        with transcript.open("a") as handle:
            handle.write(json.dumps({"type": "response_item", "payload": payload}) + "\n")
            handle.write(json.dumps({"type": "response_item", "payload": result}) + "\n")
    append("read", source)
    assert bridge.native_tool_observation(ctx, "read")["tool"] == "mcp__codex_app__read_thread"
    for ident, code, namespace in [("extra", source + 'text({"verified":true});', "functions"),
                                   ("shell", 'text(await tools.exec_command({"cmd":"echo PASS"}));', "functions"),
                                   ("foreign", source, "untrusted"),
                                   ("variable", 'text(await tools.mcp__codex_app__read_thread(args));', "functions")]:
        append(ident, code, namespace)
        assert bridge.native_tool_observation(ctx, ident) is None


def test_local_effect_readback_is_actual_bounded_state_not_claimed_success(bridge, world):
    import autopilot
    engine = autopilot.engine()
    current = create(engine, world)
    target = world["project"] / "published.txt"
    content = b"delivered artifact\n"
    intent = {"id": "publish", "target": "file:published.txt", "payload_digest": hashlib.sha256(content).hexdigest(),
              "idempotency_key": "local-write-1", "authority_ref": ""}
    current = command(engine, world, current, "effect.prepare", intent)
    spec = world["project"] / "readback.json"
    spec.write_text(json.dumps({"schema_version": 1, "kind": "effect-readback", "arguments": {"effect_id": "publish"}}))
    current = command(engine, world, current, "artifact.register", {"id": "readback-spec", "path": str(spec), "role": "input", "required": False, "retention": "durable"})
    def observe(ident):
        nonlocal current
        current = engine.observe(world["project"], current["run_id"], "effect-readback", {"check_id": "readback-spec"},
            expected_revision=current["revision"], command_id=ident, actor=world["actor"], runtime_root=world["runtime"])
        return current["evidence"][ident]["data"]
    assert observe("read-absent")["status"] == "absent"
    target.write_bytes(b"wrong output")
    assert observe("read-wrong")["status"] == "failed"
    target.write_bytes(content)
    assert observe("read-present")["status"] == "confirmed"
    current = command(engine, world, current, "effect.reconcile", {"id": "publish", "evidence": "read-present"})
    assert current["effects"]["publish"]["status"] == "confirmed"
    target.unlink()
    target.symlink_to(world["plan"])
    with pytest.raises(ValueError):
        observe("unsafe-link")


def test_native_registration_readback_is_observed_without_claiming_future_wake(bridge, observed, world):
    bindings = {key: observed["state"][key] for key in ("run_id", "contract_digest", "profile_digest")}
    prompt = json.dumps({"autopilot_continuation": {"schema_version": 1, "bindings": bindings}})
    args = {"cron": "*/5 * * * *", "prompt": prompt, "recurring": True}
    append_claude_tool(world, "CronCreate", args, {"id": "abcd1234"}, "create-job")
    append_claude_tool(world, "CronList", {}, {"jobs": [{"id": "abcd1234", **args}]}, "list-job")
    data = bridge.observe_native_registration(observed, "create-job", "list-job")
    assert data["job_id"] == "abcd1234" and data["registration_status"] == "observed"
    assert data["wake_status"] == "unknown" and data["survival"] == []
    assert "next_wake_at" not in data and "lease_expires_at" not in data
    assert bridge.verify_source(record("continuation-registration", data, observed), observed)
    forged = {**data, "next_wake_at": "2030-01-01T00:00:00Z"}
    assert not bridge.verify_source(record("continuation-registration", forged, observed), observed)
    wrong = copy.deepcopy(data);wrong["job_id"] = "foreign1"
    assert not bridge.verify_source(record("continuation-registration", wrong, observed), observed)


def test_capability_components_preserve_unknowns_and_require_genuine_receipts(bridge, observed, world):
    bindings = {key: observed["state"][key] for key in ("run_id", "contract_digest", "profile_digest")}
    args = {"cron": "*/5 * * * *", "prompt": json.dumps({"autopilot_continuation": {"schema_version": 1, "bindings": bindings}}), "recurring": True}
    append_claude_tool(world, "CronCreate", args, {"id": "abcd1234"}, "create-job")
    append_claude_tool(world, "CronList", {}, {"jobs": [{"id": "abcd1234", **args}]}, "list-job")
    data = bridge.observe_native_capability(observed, {"create_call_id": "create-job", "readback_call_id": "list-job"})
    assert data["capabilities"]["native_identity"] is True
    assert data["capabilities"]["registration_readback"] is True
    assert data["capabilities"]["wake_observation"] is False
    assert data["capabilities"]["independent_observer"] is False
    assert data["capabilities"]["survival"] == []
    assert bridge.verify_source(record("capability", data, observed), observed)
    forged = copy.deepcopy(data);forged["capabilities"]["survival"] = ["reboot"]
    assert not bridge.verify_source(record("capability", forged, observed), observed)


def test_old_native_delivery_cannot_be_wrapped_in_new_receipt(bridge, observed, world):
    args = {"threadId": "peer", "prompt": observed["state"]["run_id"]}
    append_claude_tool(world, "mcp__codex_app__send_message_to_thread", args, {"status": "delivered", "threadId": "peer"})
    data = {"source": {"kind": "native-tool", "call_id": "native-call"}, "delivery_id": "native-call", "channel": "codex-task", "status": "delivered"}
    assert bridge.verify_source(record("delivery", data, observed), observed)
    lines = [json.loads(line) for line in world["transcript"].read_text().splitlines()]
    for line in lines:
        if "timestamp" in line:
            line["timestamp"] = "2000-01-01T00:00:00Z"
    world["transcript"].write_text("".join(json.dumps(line) + "\n" for line in lines))
    assert not bridge.verify_source(record("delivery", data, observed), observed)


def test_terminal_delivery_observation_uses_predeclared_target_and_actual_native_result(bridge, world):
    import autopilot
    engine = autopilot.engine()
    current = create(engine, world)
    spec = world["project"] / "delivery.json"
    spec.write_text(json.dumps({"schema_version": 1, "kind": "delivery", "arguments": {"thread_id": "peer"}}))
    current = command(engine, world, current, "artifact.register", {"id": "delivery-spec", "path": str(spec), "role": "input", "required": False, "retention": "durable"})
    current = command(engine, world, current, "close", {"status": "cancelled", "reason": "Fixture stopped"})
    terminal = copy.deepcopy(current["terminal"])
    append_claude_tool(world, "mcp__codex_app__send_message_to_thread", {"threadId": "peer", "prompt": current["run_id"]}, {"status": "delivered", "threadId": "peer"}, "delivered-after-close")
    # Native result timestamp occurs after the immutable terminal boundary.
    lines = [json.loads(line) for line in world["transcript"].read_text().splitlines()]
    for line in lines:
        if "timestamp" in line:
            line["timestamp"] = datetime.now(timezone.utc).isoformat()
    world["transcript"].write_text("".join(json.dumps(line) + "\n" for line in lines))
    current = engine.observe(world["project"], current["run_id"], "delivery", {"check_id": "delivery-spec"},
        expected_revision=current["revision"], command_id="observed-after-close", actor=world["actor"], runtime_root=world["runtime"])
    current = command(engine, world, current, "delivery.record", {"receipt": "observed-after-close"})
    assert current["status"] == "cancelled" and current["terminal"] == terminal
    assert current["extensions"]["capabilities"]["deliveries"]["delivered-after-close"]["status"] == "delivered"


def quality_repair_world(world, *, change_output=True):
    """Real core and OS-sandbox consumer receipts; no verifier callbacks."""
    import autopilot
    engine = autopilot.engine()
    current = create(engine, world)
    current = command(engine, world, current, "workflow.configure", {"dimensions": {
        "domains": ["software"], "uncertainty": "low", "effect": "local-reversible",
        "horizon": "session", "parallelizable": False}})
    def register(identity, content, role="input"):
        nonlocal current
        path = world["project"] / (identity + (".py" if identity == "program" else ".json"))
        path.write_text(content)
        current = command(engine, world, current, "artifact.register", {
            "id": identity, "path": str(path), "role": role, "required": role == "output", "retention": "durable"})
        return path
    register("output", '{"answer":0}', "output")
    register("program", 'from pathlib import Path\nprint(Path("output.json").read_text())\n')
    register("consumer", json.dumps({"schema_version": 1, "kind": "python-consumer", "criterion_id": "accept",
        "artifact_id": "output", "script_artifact_id": "program", "expected": {"answer": 1}, "argv": [], "timeout_seconds": 2}))
    def observe(kind, check_id, identity):
        nonlocal current
        current = engine.observe(world["project"], current["run_id"], kind, {"check_id": check_id},
            expected_revision=current["revision"], command_id=identity, actor=world["actor"], runtime_root=world["runtime"])
    observe("consumer-check", "consumer", "failed-consumer")
    register("first-review-spec", json.dumps({"schema_version": 1, "kind": "quality_observation",
        "arguments": {"observation_id": "failed-consumer"}}))
    observe("quality_observation", "first-review-spec", "failed-review")
    current = command(engine, world, current, "workflow.grade", {
        "criterion_id": "accept", "receipt_ids": ["failed-review"], "independent": False})
    prior = copy.deepcopy(current["extensions"]["workflow"]["quality"]["accept"])
    assert prior["verdict"] == "FAIL"
    if change_output:
        register("output", '{"answer":1}', "output")
    observe("consumer-check", "consumer", "repaired-consumer")
    register("second-review-spec", json.dumps({"schema_version": 1, "kind": "quality_observation",
        "arguments": {"observation_id": "repaired-consumer"}}))
    observe("quality_observation", "second-review-spec", "repaired-review")
    arguments = {"criterion_id": "accept", "prior_grade_digest": prior.get("grade_digest", "missing-grade-fingerprint"),
                 "receipt_ids": ["repaired-review"]}
    register("resolution-spec", json.dumps({"schema_version": 1, "kind": "quality_resolution", "arguments": arguments}))
    return engine, current, prior, arguments


def test_quality_resolution_derives_changed_output_from_real_consumer_attempts(bridge, world):
    engine, current, prior, arguments = quality_repair_world(world)
    failed_snapshot = copy.deepcopy(current["observations"]["failed-review"])
    current = engine.observe(world["project"], current["run_id"], "quality_resolution", {"check_id": "resolution-spec"},
        expected_revision=current["revision"], command_id="repair-resolution", actor=world["actor"], runtime_root=world["runtime"])
    data = current["evidence"]["repair-resolution"]["data"]
    assert data["prior_grade_digest"] == prior["grade_digest"]
    assert data["prior_receipt_ids"] == ["failed-review"] and data["receipt_ids"] == ["repaired-review"]
    assert data["prior_receipt_digests"] == {"failed-review": failed_snapshot["digest"]}
    assert data["new_receipt_digests"] == {"repaired-review": current["observations"]["repaired-review"]["digest"]}
    assert data["changed_artifacts"] == {"output": {
        "before": [failed_snapshot["data"]["artifact_digest"]], "after": current["artifacts"]["output"]["digest"]}}
    assert data["changed_evidence"] and not {"approved", "passed", "verdict"} & data.keys()
    pure = engine.inspect_context(current, world["actor"], project=world["project"])
    assert pure["verify_receipt"]("repair-resolution", "quality_resolution", {})
    assert not pure["verify_receipt"]("failed-review", "quality_observation", {})  # Honest stale old artifact.
    current = command(engine, world, current, "workflow.grade", {"criterion_id": "accept",
        "receipt_ids": ["repaired-review"], "independent": False, "resolution_receipt_id": "repair-resolution"})
    assert current["extensions"]["workflow"]["quality"]["accept"]["verdict"] == "PASS"
    assert current["observations"]["failed-review"] == failed_snapshot
    pure = engine.inspect_context(current, world["actor"], project=world["project"])
    assert pure["verify_receipt"]("repair-resolution", "quality_resolution", {})
    with pytest.raises(ValueError):
        engine.observe(world["project"], current["run_id"], "quality_resolution", {"check_id": "resolution-spec"},
            expected_revision=current["revision"], command_id="replayed-resolution", actor=world["actor"], runtime_root=world["runtime"])


@pytest.mark.parametrize("damage", ["unchanged", "prior-attempt", "grade", "old-observation", "historical-verdict", "new-observation", "new-set", "criterion"])
def test_quality_resolution_rejects_unchanged_or_forged_repair(bridge, world, damage):
    engine, current, prior, arguments = quality_repair_world(world, change_output=damage != "unchanged")
    pure = engine.inspect_context(current, world["actor"], project=world["project"])
    context = {**pure, "state": copy.deepcopy(current), "project": world["project"], "actor": world["actor"]}
    if damage == "prior-attempt":
        arguments["receipt_ids"] = ["failed-review"]
    elif damage == "grade":
        context["state"]["extensions"]["workflow"]["quality"]["accept"]["round"] = 99
    elif damage == "old-observation":
        context["state"]["observations"]["failed-review"]["data"]["artifact_digest"] = "a" * 64
    elif damage == "historical-verdict":
        forged = context["state"]["extensions"]["workflow"]["quality"]["accept"]
        # The retained consumer review is not independent. Its computed verdict
        # becomes UNKNOWN under this substituted grade policy, while the old
        # stored FAIL still satisfies the pure failing-artifact comparison.
        forged["independent"] = True
        forged["grade_digest"] = hashlib.sha256(json.dumps(
            {key: value for key, value in forged.items() if key != "grade_digest"},
            sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        arguments["prior_grade_digest"] = forged["grade_digest"]
    elif damage == "new-observation":
        context["state"]["evidence"]["repaired-review"]["data"]["artifact_digest"] = "b" * 64
    elif damage == "new-set":
        arguments["receipt_ids"].append("failed-review")
    elif damage == "criterion":
        arguments["criterion_id"] = "other"
    with pytest.raises(ValueError):
        bridge.observe_quality_resolution(context, arguments)


def test_claude_actual_structured_tool_result_and_list_shape(bridge, observed, world):
    bindings = {key: observed["state"][key] for key in ("run_id", "contract_digest", "profile_digest")}
    args = {"cron": "* * * * *", "prompt": json.dumps({"autopilot_continuation": {"schema_version": 1, "bindings": bindings}}), "recurring": False}
    append_claude_tool(world, "CronCreate", args, {"id": "abcd1234", "humanSchedule": "Every minute", "recurring": False, "durable": False}, "native-create")
    append_claude_tool(world, "CronList", {}, {"jobs": [{"id": "abcd1234", "cron": args["cron"], "prompt": args["prompt"], "humanSchedule": "Every minute", "durable": False}]}, "native-list")
    records = [json.loads(line) for line in world["transcript"].read_text().splitlines()]
    for event in records:
        content = event.get("message", {}).get("content", [])
        if event.get("type") == "user" and isinstance(content, list) and len(content) == 1 and content[0].get("type") == "tool_result":
            event["tool_use_result"] = json.loads(content[0]["content"])
            content[0]["content"] = "Native human readable result; no JSON in prose."
    world["transcript"].write_text("".join(json.dumps(line) + "\n" for line in records))
    observed_result = bridge.native_tool_observation(observed, "native-create")
    assert observed_result["result"]["recurring"] is False
    data = bridge.observe_native_registration(observed, "native-create", "native-list")
    assert data["recurring"] is False and data["registration_status"] == "observed"


def test_native_cancellation_observer_requires_current_requested_job_and_readback(bridge, observed, world):
    state = observed["state"]
    requested = (datetime.fromisoformat(observed["now"]) - timedelta(seconds=2)).isoformat()
    state["extensions"]["capabilities"] = {"continuation": {"job_id": "abcd1234", "surface": "claude-code-cli", "cancel_requested_at": requested,
        "binding": {**{key: observed["binding"][key] for key in bridge.BINDING_KEYS}, **{key: state[key] for key in ("run_id", "contract_digest", "profile_digest")}}}}
    append_claude_tool(world, "CronDelete", {"id": "abcd1234"}, {"id": "abcd1234", "deleted": True}, "delete")
    append_claude_tool(world, "CronList", {}, {"jobs": []}, "readback")
    data = bridge.observe_native_cleanup("continuation-cancellation", {"job_id": "abcd1234"}, observed)
    assert data["cancelled"] is True
    assert bridge.verify_source(record("continuation-cancellation", data, observed), observed)
    with pytest.raises(ValueError):
        bridge.observe_native_cleanup("continuation-cancellation", {"job_id": "foreign1"}, observed)
    state["extensions"]["capabilities"]["continuation"]["cancel_requested_at"] = observed["now"]
    with pytest.raises(ValueError):
        bridge.observe_native_cleanup("continuation-cancellation", {"job_id": "abcd1234"}, observed)


def test_native_scheduler_wake_requires_unique_registered_prompt_and_host_queue(bridge, observed, world):
    bindings = {key: observed["state"][key] for key in ("run_id", "contract_digest", "profile_digest")}
    args = {"cron": "* * * * *", "prompt": json.dumps({"autopilot_continuation": {"schema_version": 1, "bindings": bindings}}), "recurring": False}
    append_claude_tool(world, "CronCreate", args, {"id": "abcd1234", "recurring": False}, "native-create")
    append_claude_tool(world, "CronList", {}, {"jobs": [{"id": "abcd1234", "cron": args["cron"], "prompt": args["prompt"]}]}, "native-list")
    timestamp = (datetime.fromisoformat(observed["now"]) - timedelta(milliseconds=100)).isoformat()
    session = world["actor"]["native_payload"]["session_id"]
    queued = {"type": "queue-operation", "operation": "enqueue", "sessionId": session, "timestamp": timestamp, "content": args["prompt"]}
    wake = {"type": "user", "sessionId": session, "isMeta": True, "queueSkipAttachments": True, "promptSource": "sdk", "promptId": "wake-prompt", "uuid": "wake-event", "timestamp": timestamp,
            "message": {"role": "user", "content": args["prompt"]}}
    with world["transcript"].open("a") as handle:
        handle.write(json.dumps(queued) + "\n" + json.dumps(wake) + "\n")
    data = bridge.observe_native_wake(observed, "native-create", "native-list", "wake-event")
    assert data["job_id"] == "abcd1234" and data["event_id"] == "wake-event"
    assert data["next_wake_status"] == "unknown" and "next_wake_at" not in data
    assert bridge.verify_source(record("continuation-wake", data, observed), observed)
    world["transcript"].write_text(world["transcript"].read_text().replace('"isMeta": true', '"isMeta": false'))
    assert not bridge.verify_source(record("continuation-wake", data, observed), observed)


def native_turn_end_probe(world, observed):
    """Actual wire shapes, synthetic timestamps, and two distinct native jobs."""
    now = datetime.fromisoformat(observed['now'])
    minute = now.replace(second=0, microsecond=0)
    bindings = {key: observed['state'][key] for key in ('run_id', 'contract_digest', 'profile_digest')}
    def prompt(role, generation, **extra):
        return json.dumps({'autopilot_continuation': {'schema_version': 1, 'bindings': bindings,
            'role': role, 'generation': generation, **extra}})
    worker = {'cron': '* * * * *', 'recurring': True, 'prompt': prompt('worker', 'probe')}
    monitor = {'cron': '* * * * *', 'recurring': True,
               'prompt': prompt('backstop', 'probe', worker_job_id='worker01')}
    active = {'cron': '* * * * *', 'recurring': True, 'prompt': prompt('worker', 'active')}
    session = world['actor']['native_payload']['session_id']
    def tool(name, args, result, ident, when):
        stamp = when.isoformat()
        events = [{'type':'assistant','sessionId':session,'timestamp':stamp,
            'message':{'content':[{'type':'tool_use','id':ident,'name':name,'input':args}]}},
            {'type':'user','sessionId':session,'timestamp':stamp,'toolUseResult':result,
             'message':{'content':[{'type':'tool_result','tool_use_id':ident,'content':'Native result'}]}}]
        with world['transcript'].open('a') as handle:
            handle.write(''.join(json.dumps(event)+'\n' for event in events))
    def wake(ident, text, when):
        events = [{'type':'queue-operation','operation':'enqueue','sessionId':session,
            'timestamp':when.isoformat(),'content':text},
            {'type':'user','sessionId':session,'timestamp':when.isoformat(),'uuid':ident,
             'isMeta':True,'queueSkipAttachments':True,'promptSource':'sdk','promptId':ident+'-prompt',
             'message':{'role':'user','content':text}}]
        with world['transcript'].open('a') as handle:
            handle.write(''.join(json.dumps(event)+'\n' for event in events))
    first = minute-timedelta(minutes=3)
    tool('CronCreate',worker,{'id':'worker01','recurring':True},'probe-create',first-timedelta(seconds=5))
    tool('CronCreate',monitor,{'id':'monitor1','recurring':True},'monitor-create',first-timedelta(seconds=4))
    tool('CronList',{}, {'jobs':[{'id':'worker01',**worker},{'id':'monitor1',**monitor}]}, 'probe-list',first-timedelta(seconds=3))
    wake('worker-wake',worker['prompt'],first+timedelta(seconds=5))
    tool('CronDelete',{'id':'worker01'},{'id':'worker01','deleted':True},'probe-cancel',first+timedelta(seconds=6))
    wake('monitor-wake',monitor['prompt'],first+timedelta(minutes=2,seconds=15))
    tool('CronList',{}, {'jobs':[{'id':'monitor1',**monitor}]},'monitor-check',first+timedelta(minutes=2,seconds=16))
    tool('CronCreate',active,{'id':'worker02','recurring':True},'active-create',now-timedelta(seconds=3))
    active_monitor={'cron':'* * * * *','recurring':True,'prompt':prompt('backstop','active',worker_job_id='worker02')}
    tool('CronCreate',active_monitor,{'id':'monitor2','recurring':True},'active-monitor-create',now-timedelta(seconds=2))
    tool('CronList',{}, {'jobs':[{'id':'worker02',**active},{'id':'monitor2',**active_monitor}]},'active-list',now-timedelta(seconds=1))
    arguments={'create_call_id':'probe-create','readback_call_id':'probe-list','wake_event_id':'worker-wake',
        'monitor_create_call_id':'monitor-create','monitor_readback_call_id':'probe-list',
        'monitor_wake_event_id':'monitor-wake','monitor_check_call_id':'monitor-check',
        'cancellation_call_id':'probe-cancel','cancellation_readback_call_id':'monitor-check'}
    return arguments, active, wake


def native_renewal_fixture(bridge, observed, world, *, registration_expiry_seconds=None):
    """Authenticated temporary PM/native source, preserving admitted envelopes."""
    import capabilities as cap
    observed['now'] = datetime.fromisoformat(observed['now']).replace(second=45, microsecond=0).isoformat()
    args, active, wake = native_turn_end_probe(world, observed)
    records = {}; observed['evidence'] = records
    verdicts = {}
    def verified(ref, kind, bindings):
        # Match the engine's once-per-immutable-context source evaluation;
        # renewal links form a DAG, not repeated independent PM operations.
        if ref not in records or records[ref]['kind'] != kind:
            return False
        key = (id(observed['state']), observed['now'], ref, json.dumps(records[ref], sort_keys=True))
        if key not in verdicts:
            verdicts[key] = bridge.verify_source(records[ref], observed)
        return verdicts[key]
    observed['verify_receipt'] = verified
    def save(kind, data, identity):
        records[identity] = {**record(kind, data, observed), 'id': identity}
        return identity
    save('capability', bridge.observe_native_capability(observed, args), 'cap')
    observed['state'] = cap.record_capability(observed['state'], {'surface': 'claude-code-cli', 'receipt': 'cap'}, observed)
    data = bridge.observe_native_registration(observed, 'active-create', 'active-list', capability_receipt='cap', monitor_create_call_id='active-monitor-create')
    save('continuation-registration', data, 'registered')
    if registration_expiry_seconds is not None:
        records['registered']['expires_at'] = (datetime.fromisoformat(observed['now']) + timedelta(seconds=registration_expiry_seconds)).isoformat()
    observed['state'] = cap.register_continuation(observed['state'], {'receipt': 'registered', 'horizon': 'turn_end'}, observed)
    original_rows = [json.loads(line) for line in world['transcript'].read_text().splitlines()]
    active_list = next(row for row in original_rows if any(p.get('tool_use_id') == 'active-list'
        for p in row.get('message', {}).get('content', []) if isinstance(p, dict)))
    def readback(identity, when, jobs=None):
        append_claude_tool(world, 'CronList', {}, jobs or active_list['toolUseResult'], identity)
        rows = [json.loads(line) for line in world['transcript'].read_text().splitlines()]
        for row in rows[-2:]: row['timestamp'] = when.isoformat()
        world['transcript'].write_text(''.join(json.dumps(row) + '\n' for row in rows))
    return records, save, active, wake, readback


def test_native_renewal_caps_original_registration_envelope_expiry(bridge, observed, world):
    records, _, _, _, readback = native_renewal_fixture(bridge, observed, world, registration_expiry_seconds=310)
    readback('short-original-renewal', datetime.fromisoformat(observed['now']) + timedelta(seconds=20))
    observed['now'] = (datetime.fromisoformat(observed['now']) + timedelta(seconds=21)).isoformat()
    data = bridge.observe_native_renewal(observed, 'short-original-renewal', 'registered')
    assert data['lease_expires_at'] == bridge._time(records['registered']['expires_at'])


def test_same_native_pair_can_renew_with_fresh_readbacks_and_wake_again_after_five_minutes(bridge, observed, world):
    import capabilities as cap
    records, save, active, wake, readback = native_renewal_fixture(bridge, observed, world)
    first = datetime.fromtimestamp(records['registered']['data']['deadline_provenance']['nominal_at'], timezone.utc) + timedelta(seconds=5)
    original = copy.deepcopy(observed['state']['extensions']['capabilities']['continuation'])
    listing = 'active-list'; lease = 'registered'
    for number in range(6):
        when = first + timedelta(minutes=number)
        wake(f'wake-{number}', active['prompt'], when)
        observed['now'] = (when + timedelta(seconds=1)).isoformat()
        data = bridge.observe_native_wake(observed, 'active-create', listing, f'wake-{number}',
            registration_receipt='registered', lease_receipt=lease)
        save('continuation-wake', data, f'wake-{number}')
        observed['state'] = cap.observe_wake(observed['state'], {'receipt': f'wake-{number}'}, observed)
        listing = f'fresh-list-{number}'
        readback(listing, when + timedelta(seconds=2))
        observed['now'] = (when + timedelta(seconds=3)).isoformat()
        renewal = bridge.observe_native_renewal(observed, listing, lease)
        assert renewal['lease_expires_at'] <= (when + timedelta(seconds=302)).timestamp()
        save('continuation-renewal', renewal, f'renew-{number}')
        observed['state'] = cap.renew_continuation(observed['state'], {'receipt': f'renew-{number}'}, observed)
        lease = f'renew-{number}'
    job = observed['state']['extensions']['capabilities']['continuation']
    assert len(job['wakes']) == 6 and len(job['renewals']) == 6
    assert job['registered_at'] == original['registered_at'] and job['registration_receipt'] == 'registered'
    assert bridge._time(job['wakes'][-1]['observed_at']) - bridge._time(job['wakes'][0]['observed_at']) == 300
    assert cap.continuation_status(observed['state'], observed)['continuation_verified'] is True
    cap.validate_horizon(observed['state'], 'turn_end', observed)
    assert observed['verify_receipt']('cap', 'capability', {})
    assert observed['verify_receipt']('registered', 'continuation-registration', {})
    assert observed['verify_receipt']('wake-0', 'continuation-wake', {})


@pytest.mark.parametrize('fault', ['missing_monitor', 'changed_worker', 'stale', 'after_expiry', 'replayed_list', 'cancelled'])
def test_native_renewal_requires_fresh_same_pair_readback_before_expiry(bridge, observed, world, fault):
    records, _, _, _, readback = native_renewal_fixture(bridge, observed, world)
    start = datetime.fromisoformat(observed['now']); at = start + timedelta(seconds=5)
    listing = 'renew-list'
    readback(listing, at)
    if fault in {'missing_monitor', 'changed_worker'}:
        rows = [json.loads(line) for line in world['transcript'].read_text().splitlines()]
        result = json.loads(rows[-1]['message']['content'][0]['content'])
        if fault == 'missing_monitor': result['jobs'] = result['jobs'][:1]
        else: result['jobs'][0]['prompt'] = 'changed'
        rows[-1]['message']['content'][0]['content'] = json.dumps(result)
        world['transcript'].write_text(''.join(json.dumps(row) + '\n' for row in rows))
    elif fault == 'replayed_list': listing = 'active-list'
    elif fault == 'cancelled':
        append_claude_tool(world, 'CronDelete', {'id': 'worker02'}, {'id': 'worker02', 'deleted': True}, 'cancel-current')
        rows = [json.loads(line) for line in world['transcript'].read_text().splitlines()]
        for row in rows[-2:]: row['timestamp'] = (at + timedelta(seconds=1)).isoformat()
        world['transcript'].write_text(''.join(json.dumps(row) + '\n' for row in rows))
    observed['now'] = (at + timedelta(seconds=301 if fault == 'stale' else 1)).isoformat()
    if fault == 'after_expiry': observed['now'] = datetime.fromtimestamp(records['registered']['data']['lease_expires_at'], timezone.utc).isoformat()
    with pytest.raises(ValueError): bridge.observe_native_renewal(observed, listing, 'registered')


@pytest.mark.parametrize('event', ['cancel', 'pair-removed'])
@pytest.mark.parametrize('timestamp', ['future', 'missing', 'old'])
def test_later_native_invalidation_cannot_hide_behind_unfresh_timestamp(bridge, observed, world, event, timestamp):
    _, _, _, _, readback = native_renewal_fixture(bridge, observed, world)
    start = datetime.fromisoformat(observed['now'])
    readback('renew-list', start + timedelta(seconds=5))
    observed['now'] = (start + timedelta(seconds=6)).isoformat()
    assert bridge.observe_native_renewal(observed, 'renew-list', 'registered')['job_id'] == 'worker02'
    if event == 'cancel':
        append_claude_tool(world, 'CronDelete', {'id': 'worker02'}, {'id': 'worker02', 'deleted': True}, 'invalidating-event')
    else:
        append_claude_tool(world, 'CronList', {}, {'jobs': []}, 'invalidating-event')
    rows = [json.loads(line) for line in world['transcript'].read_text().splitlines()]
    for row in rows[-2:]:
        if timestamp == 'missing': row.pop('timestamp')
        else: row['timestamp'] = (start + timedelta(seconds=60 if timestamp == 'future' else -600)).isoformat()
    world['transcript'].write_text(''.join(json.dumps(row) + '\n' for row in rows))
    assert not bridge._recent_native(bridge.native_tool_observation(observed, 'invalidating-event'), observed)
    with pytest.raises(ValueError):
        bridge.observe_native_renewal(observed, 'renew-list', 'registered')


@pytest.mark.parametrize('timestamp', ['future', 'missing', 'old'])
def test_native_renewal_keeps_freshness_for_affirmative_readback(bridge, observed, world, timestamp):
    _, _, _, _, readback = native_renewal_fixture(bridge, observed, world)
    start = datetime.fromisoformat(observed['now'])
    readback('unfresh-list', start + timedelta(seconds=60 if timestamp == 'future' else -600))
    if timestamp == 'missing':
        rows = [json.loads(line) for line in world['transcript'].read_text().splitlines()]
        for row in rows[-2:]: row.pop('timestamp')
        world['transcript'].write_text(''.join(json.dumps(row) + '\n' for row in rows))
    observed['now'] = (start + timedelta(seconds=6)).isoformat()
    with pytest.raises(ValueError):
        bridge.observe_native_renewal(observed, 'unfresh-list', 'registered')


@pytest.mark.parametrize('gap', ['overflow', 'ambiguous-cancel'])
def test_native_renewal_refuses_incomplete_invalidation_coverage(bridge, observed, world, gap):
    _, _, _, _, readback = native_renewal_fixture(bridge, observed, world)
    start = datetime.fromisoformat(observed['now'])
    readback('renew-list', start + timedelta(seconds=5))
    observed['now'] = (start + timedelta(seconds=6)).isoformat()
    assert bridge.observe_native_renewal(observed, 'renew-list', 'registered')['job_id'] == 'worker02'
    append_claude_tool(world, 'CronDelete', {'id': 'worker02'}, {'id': 'worker02', 'deleted': True}, 'cancel-current')
    if gap == 'overflow':
        for number in range(64):
            readback('later-list-' + str(number), start + timedelta(seconds=6))
    else:
        append_claude_tool(world, 'CronDelete', {'id': 'worker02'}, {'id': 'worker02', 'deleted': True}, 'cancel-current')
    rows = [json.loads(line) for line in world['transcript'].read_text().splitlines()]
    for row in rows:
        content = row.get('message', {}).get('content', [])
        if isinstance(content, list) and any(isinstance(item, dict) and
                (item.get('id') == 'cancel-current' or item.get('tool_use_id') == 'cancel-current') for item in content):
            row['timestamp'] = observed['now']
    world['transcript'].write_text(''.join(json.dumps(row) + '\n' for row in rows))
    with pytest.raises(ValueError):
        bridge.observe_native_renewal(observed, 'renew-list', 'registered')


def test_admitted_history_has_no_64_call_lifetime_limit_but_new_renewal_keeps_current_bound(bridge, observed, world, monkeypatch):
    """A fresh anchored renewal survives complete harmless historical traffic."""
    import capabilities as cap
    records, save, _, _, readback = native_renewal_fixture(bridge, observed, world)
    start = datetime.fromisoformat(observed['now'])
    readback('first-renewal-list', start + timedelta(seconds=5))
    observed['now'] = (start + timedelta(seconds=6)).isoformat()
    assert bridge.verify_source(records['registered'], observed) is True
    renewal = bridge.observe_native_renewal(observed, 'first-renewal-list', 'registered')
    save('continuation-renewal', renewal, 'first-renewal')
    observed['state'] = cap.renew_continuation(observed['state'], {'receipt': 'first-renewal'}, observed)
    for number in range(65):
        readback('harmless-list-' + str(number), start + timedelta(seconds=7 + number))
    observed['now'] = (start + timedelta(seconds=73)).isoformat()
    assert bridge._time(observed['now']) < renewal['lease_expires_at']
    latest = bridge.native_tool_observation(observed, 'harmless-list-64')
    assert bridge._native_observations(observed, fresh_only=False, after_observation=latest) == []
    # New callers cannot borrow historical permission or silently widen the
    # current negative window. The old anchor still exceeds its current cap.
    original = bridge.native_tool_observation(observed, 'active-list')
    with pytest.raises(ValueError, match='exceeds bounded coverage'):
        bridge._native_observations(observed, fresh_only=False, after_observation=original)
    calls = []
    native = bridge.native_tool_observation
    def counted(context, call_id):
        calls.append(call_id)
        return native(context, call_id)
    monkeypatch.setattr(bridge, 'native_tool_observation', counted)
    assert bridge.verify_source(records['registered'], observed) is True
    # Historical coverage must use one indexed snapshot, not fan out into a
    # full authenticated transcript scan for every historical tool call.
    assert not any(identity.startswith('harmless-list-') for identity in calls)
    fresh = bridge.observe_native_renewal(observed, 'harmless-list-64', 'first-renewal')
    assert fresh['job_id'] == 'worker02'
    assert fresh['lease_expires_at'] > renewal['lease_expires_at']


@pytest.mark.parametrize('fault', ['cancelled', 'missing_pair', 'duplicate', 'missing_result'])
def test_historical_native_coverage_keeps_earlier_invalidation_before_65_good_lists(bridge, observed, world, fault):
    records, _, _, _, readback = native_renewal_fixture(bridge, observed, world)
    start = datetime.fromisoformat(observed['now'])
    assert bridge.verify_source(records['registered'], observed) is True
    if fault == 'cancelled':
        append_claude_tool(world, 'CronDelete', {'id': 'worker02'}, {'id': 'worker02', 'deleted': True}, 'hidden-negative')
    elif fault == 'missing_pair':
        readback('hidden-negative', start + timedelta(seconds=1), {'jobs': []})
    else:
        readback('hidden-negative', start + timedelta(seconds=1))
        if fault == 'duplicate':
            readback('hidden-negative', start + timedelta(seconds=1))
        else:
            rows = world['transcript'].read_text().splitlines()
            world['transcript'].write_text('\n'.join(rows[:-1]) + '\n')
    for number in range(65):
        readback('later-good-' + str(number), start + timedelta(seconds=2 + number))
    observed['now'] = (start + timedelta(seconds=68)).isoformat()
    latest = bridge.native_tool_observation(observed, 'later-good-64')
    assert bridge._native_observations(observed, fresh_only=False, after_observation=latest) == []
    # A current affirmative listing cannot erase historical cancellation,
    # pair absence or ambiguous/incomplete authenticated native calls.
    assert bridge.verify_source(records['registered'], observed) is False
    with pytest.raises(ValueError):
        bridge.observe_native_renewal(observed, 'later-good-64', 'registered')


@pytest.mark.parametrize('fault', ['new_id', 'changed_data', 'backdated_envelope', 'expired_receipt', 'claim_revoked'])
def test_historical_native_intake_requires_identical_admitted_envelope_and_current_authority(bridge, observed, world, fault):
    records, _, _, _, _ = native_renewal_fixture(bridge, observed, world)
    observed['now'] = (datetime.fromisoformat(observed['now']) + timedelta(seconds=310)).isoformat()
    candidate = copy.deepcopy(records['cap'])
    if fault == 'new_id': candidate['id'] = 'new-stale-envelope'
    elif fault == 'changed_data': candidate['data']['unknown'] = []
    elif fault == 'backdated_envelope': candidate['observed_at'] = (datetime.fromisoformat(candidate['observed_at']) - timedelta(seconds=1)).isoformat()
    elif fault == 'expired_receipt': observed['now'] = candidate['expires_at']
    elif fault == 'claim_revoked': write_board(world, status='released')
    assert bridge.verify_source(candidate, observed) is False


def test_renewal_registered_as_production_observer_source_and_nonterminal_reducer(bridge):
    import capabilities as cap
    commands = {}; observers = {}; sources = {}
    cap.register_commands(lambda name, fn, **kw: commands.update({name: kw}))
    bridge.register_observers(lambda name, fn, **kw: observers.update({name: kw}))
    bridge.register_sources(lambda name, fn: sources.update({name: fn}))
    assert commands['continuation.renew']['terminal_safe'] is False
    assert observers['continuation-renewal']['terminal_safe'] is False
    assert 'continuation-renewal' in sources


def test_engine_observation_and_reducer_retains_exact_native_intake_without_extending_expired_lease(bridge, observed, world, monkeypatch):
    import autopilot
    import capabilities as cap
    engine = autopilot.engine()
    clock = datetime.fromisoformat(observed['now']).replace(second=45, microsecond=0)
    observed['now'] = clock.isoformat()
    args, _, _ = native_turn_end_probe(world, observed)
    monkeypatch.setattr(engine, '_now', lambda: clock.isoformat())
    current = observed['state']
    def observe(kind, arguments, identity):
        nonlocal current
        path = world['project'] / (identity + '.json')
        path.write_text(json.dumps({'schema_version': 1, 'kind': kind, 'arguments': arguments}))
        current = command(engine, world, current, 'artifact.register', {'id': identity + '-spec', 'path': str(path),
            'role': 'input', 'required': False, 'retention': 'durable'})
        current = engine.observe(world['project'], current['run_id'], kind, {'check_id': identity + '-spec'},
            expected_revision=current['revision'], command_id=identity, actor=world['actor'], runtime_root=world['runtime'])
    observe('capability', args, 'cap-native')
    current = command(engine, world, current, 'capability.record', {'surface': 'claude-code-cli', 'receipt': 'cap-native'})
    observe('continuation-registration', {'create_call_id': 'active-create', 'readback_call_id': 'active-list',
        'capability_receipt': 'cap-native', 'monitor_create_call_id': 'active-monitor-create'}, 'registered-native')
    current = command(engine, world, current, 'continuation.register', {'receipt': 'registered-native', 'horizon': 'turn_end'})
    clock += timedelta(seconds=10)
    native_rows = [json.loads(line) for line in world['transcript'].read_text().splitlines()]
    listing = next(row['toolUseResult'] for row in native_rows if any(part.get('tool_use_id') == 'active-list'
        for part in row.get('message', {}).get('content', []) if isinstance(part, dict)))
    append_claude_tool(world, 'CronList', {}, listing, 'engine-renew-list')
    native_rows = [json.loads(line) for line in world['transcript'].read_text().splitlines()]
    for row in native_rows[-2:]: row['timestamp'] = clock.isoformat()
    world['transcript'].write_text(''.join(json.dumps(row) + '\n' for row in native_rows))
    clock += timedelta(seconds=1)
    observe('continuation-renewal', {'readback_call_id': 'engine-renew-list', 'previous_lease_receipt': 'registered-native'}, 'renewed-native')
    current = command(engine, world, current, 'continuation.renew', {'receipt': 'renewed-native'})
    assert current['extensions']['capabilities']['continuation']['lease_receipt'] == 'renewed-native'
    assert current['extensions']['capabilities']['continuation']['wakes'] == []
    # The actual engine source-verdict closure also replays every admitted
    # ancestor. Harmless traffic must not impose a 64-call lifetime ceiling.
    for number in range(65):
        append_claude_tool(world, 'CronList', {}, listing, 'engine-harmless-' + str(number))
    clock += timedelta(seconds=310)
    context = engine.inspect_context(current, world['actor'], project=world['project'])
    assert context['verify_receipt']('cap-native', 'capability', {}) is True
    assert context['verify_receipt']('registered-native', 'continuation-registration', {}) is True
    assert context['verify_receipt']('renewed-native', 'continuation-renewal', {}) is True
    assert cap.continuation_status(current, context)['state'] == 'expired'
    original = copy.deepcopy(current)
    # The retained historical event cannot be repackaged as a new intake.
    forged = copy.deepcopy(current['evidence']['cap-native']); forged['id'] = 'new-id'
    assert bridge.verify_source(forged, {**context, 'state': current, 'project': world['project'], 'actor': world['actor']}) is False
    assert current == original


def test_native_turn_end_components_admit_actual_registration_with_computed_deadlines(bridge, observed, world):
    import capabilities as cap
    args, _, _ = native_turn_end_probe(world, observed)
    data = bridge.observe_native_capability(observed,args)
    assert data['capabilities']['survival'] == ['turn_end']
    assert data['backstop']['status'] == 'missed'
    assert data['backstop']['worker_job_id'] != data['backstop']['observer_job_id']
    records={'cap':record('capability',data,observed)}
    observed['evidence']=records
    observed['verify_receipt']=lambda ref,kind,bindings: records[ref]['kind']==kind and bridge.verify_source(records[ref],observed)
    state=cap.record_capability(observed['state'],{'surface':'claude-code-cli','receipt':'cap'},observed)
    assert cap.admission(state,'claude-code-cli','turn_end',observed)['admitted']
    assert not cap.admission(state,'claude-code-cli','reboot',observed)['admitted']
    registration=bridge.observe_native_registration(observed,'active-create','active-list',capability_receipt='cap',monitor_create_call_id='active-monitor-create')
    assert registration['deadline_provenance']['kind']=='control-plane-derived'
    assert registration['deadline_provenance']['maximum_jitter_seconds']==30
    assert registration['observer_id']=='native-job:monitor2'
    records['active']=record('continuation-registration',registration,observed)
    state=cap.register_continuation(state,{'receipt':'active','horizon':'turn_end'},observed)
    assert state['extensions']['capabilities']['continuation']['job_id']=='worker02'
    assert cap.continuation_status(state,observed)['state']=='awaiting_first_wake'


@pytest.mark.parametrize('fault',['same_job','early_monitor','worker_did_wake','monitor_missing','cancel_not_observed','foreign_run'])
def test_native_turn_end_probe_rejects_unproved_or_nonindependent_components(bridge,observed,world,fault):
    args, _, wake=native_turn_end_probe(world,observed)
    if fault=='same_job':
        args['monitor_create_call_id']=args['create_call_id'];args['monitor_wake_event_id']=args['wake_event_id']
    else:
        rows=[json.loads(line) for line in world['transcript'].read_text().splitlines()]
        for event in rows:
            parts=event.get('message',{}).get('content',[])
            if fault=='early_monitor' and event.get('uuid')=='monitor-wake':
                worker=next(row for row in rows if row.get('uuid')=='worker-wake')
                event['timestamp']=(datetime.fromisoformat(worker['timestamp'])+timedelta(seconds=1)).isoformat()
            if fault=='monitor_missing' and any(isinstance(p,dict) and p.get('tool_use_id')=='monitor-check' for p in parts):
                event['toolUseResult']={'jobs':[]}
            if fault=='cancel_not_observed' and any(isinstance(p,dict) and p.get('tool_use_id')=='probe-cancel' for p in parts):
                event['toolUseResult']={'id':'worker01','deleted':False}
            if fault=='foreign_run' and event.get('uuid')=='worker-wake':
                event['message']['content']='foreign'
        if fault=='worker_did_wake':
            worker=copy.deepcopy(next(row for row in rows if row.get('uuid')=='worker-wake'))
            monitor=next(row for row in rows if row.get('uuid')=='monitor-wake')
            worker['uuid']='unexpected-worker-wake';worker['timestamp']=(datetime.fromisoformat(monitor['timestamp'])-timedelta(seconds=1)).isoformat()
            rows.insert(rows.index(monitor),worker)
        world['transcript'].write_text(''.join(json.dumps(row)+'\n' for row in rows))
    with pytest.raises(ValueError):
        bridge.observe_native_capability(observed,args)


def test_registered_native_wake_has_derived_next_boundary_and_preserves_native_time(bridge,observed,world):
    import capabilities as cap
    args, active, wake=native_turn_end_probe(world,observed)
    records={'cap':record('capability',bridge.observe_native_capability(observed,args),observed)}
    observed['evidence']=records
    observed['verify_receipt']=lambda ref,kind,bindings: records[ref]['kind']==kind and bridge.verify_source(records[ref],observed)
    initial=cap.record_capability(observed['state'],{'surface':'claude-code-cli','receipt':'cap'},observed)
    registered=bridge.observe_native_registration(observed,'active-create','active-list',capability_receipt='cap',monitor_create_call_id='active-monitor-create')
    records['active']=record('continuation-registration',registered,observed)
    current=cap.register_continuation(initial,{'receipt':'active','horizon':'turn_end'},observed)
    actual=datetime.fromisoformat(observed['now'])+timedelta(seconds=10)
    wake('active-wake',active['prompt'],actual)
    observed['now']=(actual+timedelta(seconds=1)).isoformat()
    data=bridge.observe_native_wake(observed,'active-create','active-list','active-wake',registration_receipt='active')
    assert data['deadline_provenance']['kind']=='control-plane-derived'
    assert data['native_observed_at']==actual.isoformat()
    records['wake']=record('continuation-wake',data,observed)
    current=cap.observe_wake(current,{'receipt':'wake'},observed)
    assert current['extensions']['capabilities']['continuation']['wakes'][0]['observed_at']==actual.isoformat()
    assert cap.continuation_status(current,observed)['state']=='observed'


def test_replacement_worker_cannot_reuse_probe_backstop_target(bridge,observed,world):
    args,_,_=native_turn_end_probe(world,observed)
    records={'cap':record('capability',bridge.observe_native_capability(observed,args),observed)}
    observed['evidence']=records
    observed['verify_receipt']=lambda ref,kind,bindings: bridge.verify_source(records[ref],observed)
    with pytest.raises(ValueError):
        bridge.observe_native_registration(observed,'active-create','active-list',capability_receipt='cap',monitor_create_call_id='monitor-create')


def test_native_current_registration_refuses_later_cancellation(bridge,observed,world):
    args,_,_=native_turn_end_probe(world,observed)
    records={'cap':record('capability',bridge.observe_native_capability(observed,args),observed)}
    observed['evidence']=records
    observed['verify_receipt']=lambda ref,kind,bindings: bridge.verify_source(records[ref],observed)
    append_claude_tool(world,'CronDelete',{'id':'worker02'},{'id':'worker02','deleted':True},'late-cancel')
    with pytest.raises(ValueError):
        bridge.observe_native_registration(observed,'active-create','active-list',capability_receipt='cap',monitor_create_call_id='active-monitor-create')


def test_native_pair_cancellation_cannot_hide_surviving_backstop(bridge,observed,world):
    state=observed['state'];requested=(datetime.fromisoformat(observed['now'])-timedelta(seconds=3)).isoformat()
    state['extensions']['capabilities']={'continuation':{'job_id':'worker02','observer_id':'native-job:monitor2','surface':'claude-code-cli','cancel_requested_at':requested,
        'binding':{**{k:observed['binding'][k] for k in bridge.BINDING_KEYS},**{k:state[k] for k in ('run_id','contract_digest','profile_digest')}}}}
    append_claude_tool(world,'CronDelete',{'id':'worker02'},{'id':'worker02','deleted':True},'delete-worker')
    append_claude_tool(world,'CronList',{}, {'jobs':[{'id':'monitor2'}]},'pair-readback')
    data=bridge.observe_native_cleanup('continuation-cancellation',{'job_id':'worker02'},observed)
    assert data['cancelled'] is False
    append_claude_tool(world,'CronDelete',{'id':'monitor2'},{'id':'monitor2','deleted':True},'delete-monitor')
    append_claude_tool(world,'CronList',{}, {'jobs':[]},'pair-empty')
    data=bridge.observe_native_cleanup('continuation-cancellation',{'job_id':'worker02'},observed)
    assert data['cancelled'] is True


def test_cron_deadline_uses_native_host_local_minute_steps(bridge,monkeypatch):
    import time
    prior=os.environ.get('TZ')
    try:
        monkeypatch.setenv('TZ','Asia/Kolkata');time.tzset()
        result=bridge._schedule_deadline('*/20 * * * *','2026-09-24T10:00:05+00:00')
        assert result['nominal_at']==datetime(2026,9,24,10,10,tzinfo=timezone.utc).timestamp()
        assert result['maximum_jitter_seconds']==600
    finally:
        if prior is None:monkeypatch.delenv('TZ',raising=False)
        else:monkeypatch.setenv('TZ',prior)
        time.tzset()


def test_native_tool_pair_uses_completed_snapshot_while_writer_appends(bridge, observed, world, monkeypatch):
    import native_review
    from test_native_review import _mutate_after_first_native_read
    append_claude_tool(world, 'CronList', {}, {'jobs': []}, 'snapshot-pair')
    original = native_review._records
    calls = []
    def completed(path):
        calls.append(str(path))
        def append():
            with Path(path).open('ab') as stream:
                stream.write(b'{"new_native_event":')
        _mutate_after_first_native_read(monkeypatch, Path(path), append)
        return original(path)
    monkeypatch.setattr(native_review, '_records', completed)
    result = bridge.native_tool_observation(observed, 'snapshot-pair')
    assert result is not None and result['result'] == {'jobs': []}
    assert calls == [str(world['transcript'])]


def test_local_readback_access_time_does_not_mean_content_changed(bridge, observed, world):
    import os
    path = world['project'] / 'target.txt'
    content = b'local observed bytes'
    path.write_bytes(content)
    observed['state']['effects']['target'] = {'id': 'target', 'idempotency_key': 'target-once', 'target': 'file:target.txt', 'payload_digest': hashlib.sha256(content).hexdigest()}
    os.utime(path, ns=(1, path.stat().st_mtime_ns))
    result = bridge._local_effect_readback(observed, 'target')
    assert result['status'] == 'confirmed'
    assert result['observed_digest'] == hashlib.sha256(content).hexdigest()


def test_later_native_wake_reuses_live_registration_after_its_first_deadline(bridge, observed, world):
    import capabilities as cap
    observed['now'] = datetime.fromisoformat(observed['now']).replace(second=45, microsecond=0).isoformat()
    args, active, wake = native_turn_end_probe(world, observed)
    # A two-minute probe, followed by two active wakes within all existing
    # five-minute evidence windows. This does not extend any freshness policy.
    rows = [json.loads(line) for line in world['transcript'].read_text().splitlines()]
    for event in rows:
        parts = event.get('message', {}).get('content', [])
        is_active = any(isinstance(item, dict) and
            (str(item.get('id', '')).startswith('active-') or str(item.get('tool_use_id', '')).startswith('active-'))
            for item in parts) if isinstance(parts, list) else False
        if 'timestamp' in event and not is_active:
            event['timestamp'] = (datetime.fromisoformat(event['timestamp']) + timedelta(minutes=1)).isoformat()
    world['transcript'].write_text(''.join(json.dumps(row) + '\n' for row in rows))
    records = {'cap': record('capability', bridge.observe_native_capability(observed, args), observed)}
    observed['evidence'] = records
    observed['verify_receipt'] = lambda ref, kind, bindings: records[ref]['kind'] == kind and bridge.verify_source(records[ref], observed)
    current = cap.record_capability(observed['state'], {'surface': 'claude-code-cli', 'receipt': 'cap'}, observed)
    registration = bridge.observe_native_registration(observed, 'active-create', 'active-list', capability_receipt='cap', monitor_create_call_id='active-monitor-create')
    records['registered'] = record('continuation-registration', registration, observed)
    current = cap.register_continuation(current, {'receipt': 'registered', 'horizon': 'turn_end'}, observed)
    first = datetime.fromtimestamp(registration['deadline_provenance']['nominal_at'], timezone.utc) + timedelta(seconds=5)
    for number, at in enumerate((first, first + timedelta(minutes=1)), start=1):
        identity = f'active-wake-{number}'
        wake(identity, active['prompt'], at)
        observed['now'] = (at + timedelta(seconds=1)).isoformat()
        data = bridge.observe_native_wake(observed, 'active-create', 'active-list', identity, registration_receipt='registered')
        records[identity] = record('continuation-wake', data, observed)
        current = cap.observe_wake(current, {'receipt': identity}, observed)
    assert cap.continuation_status(current, observed)['continuation_verified'] is True
    assert cap.continuation_status(current, observed)['observed_wakes'] == 2
    # An expired initial deadline cannot admit a brand-new continuation, even
    # though its historical registration remains a valid current-lease source.
    fresh = cap.record_capability(observed['state'], {'surface': 'claude-code-cli', 'receipt': 'cap'}, observed)
    with pytest.raises(ValueError, match='deadline|lease'):
        cap.register_continuation(fresh, {'receipt': 'registered', 'horizon': 'turn_end'}, observed)


def worker_check(observed, world, arguments):
    path = world["project"] / "worker-check.json"
    path.write_text(json.dumps({"schema_version": 1, "kind": "native_worker", "arguments": arguments}))
    observed["artifacts"]["worker-check"] = {"path": "worker-check.json", "digest": hashlib.sha256(path.read_bytes()).hexdigest(), "role": "input"}
    observed["state"].setdefault("extensions", {})["workflow"] = {"children": {"child-a": {"client": "claude", "mode": "native-cli"}}}
    return {"check_id": "worker-check"}


def test_native_worker_observer_registered_without_completion_acceptance(bridge, observed):
    callbacks = {}
    bridge.register_observers(lambda kind, callback, **kw: callbacks.update({kind: (callback, kw)}))
    assert "native_worker" in callbacks
    assert callbacks["native_worker"][1]["terminal_safe"] is False
    assert "native_worker" in bridge.KINDS
    assert not bridge._accept({"kind": "native_worker", "data": {"preservation": "PASS", "native_exit_code": 0}}, observed["state"], {}, observed)


def test_native_worker_observer_uses_owned_runtime_and_dispatched_client(bridge, observed, world, monkeypatch):
    import types
    calls = []
    result = {"child_id": "child-a", "producer": "claude-cli:actual-test-session", "preservation": "PASS"}
    def launch(state, child_id, context, **kwargs):
        calls.append((state, child_id, context, kwargs))
        return result
    monkeypatch.setitem(sys.modules, "delegation_boundary", types.SimpleNamespace(run_worker=launch))
    payload = worker_check(observed, world, {"child_id": "child-a", "timeout_seconds": 60})
    assert bridge._observe("native_worker", observed, payload) == result
    assert len(calls) == 1
    assert calls[0][1] == "child-a"
    assert calls[0][3] == {"client": "claude", "runtime_root": world["project"] / "resources/autopilot-runs" / observed["state"]["run_id"] / "native-worker-attempts", "timeout_seconds": 60}


@pytest.mark.parametrize("extra", [{"client": "muse"}, {"runtime_root": "/arbitrary"}, {"environment": {}}, {"command": "anything"}])
def test_native_worker_observer_rejects_caller_execution_overrides(bridge, observed, world, extra):
    payload = worker_check(observed, world, {"child_id": "child-a", "timeout_seconds": 60, **extra})
    with pytest.raises(ValueError): bridge._observe("native_worker", observed, payload)


def test_native_worker_receipt_file_cannot_claim_engine_execution(bridge, observed):
    assert not bridge.verify_source(record("native_worker", {"preservation": "PASS", "native_exit_code": 0, "producer": "invented"}, observed), observed)
