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


def test_delivery_survives_evidence_bookkeeping_but_not_a_new_wait(bridge, observed, world):
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
