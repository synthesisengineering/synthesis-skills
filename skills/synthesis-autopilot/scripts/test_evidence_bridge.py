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
    with world["transcript"].open("a") as handle:
        handle.write(json.dumps({"type": "assistant", "sessionId": world["actor"]["native_payload"]["session_id"],
            "message": {"content": [{"type": "tool_use", "id": call_id, "name": name, "input": arguments}]}}) + "\n")
        handle.write(json.dumps({"type": "user", "sessionId": world["actor"]["native_payload"]["session_id"],
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
    criterion = {"id": "accept", "method": "consumer-check", "required": True}
    for data in ({"passed": False, "returncode": 1}, {"passed": True, "returncode": 1}, {"passed": False, "returncode": 0}):
        assert not predicates["consumer-check"]({"kind": "consumer-check", "data": data}, observed["state"], criterion, observed)
    assert predicates["consumer-check"]({"kind": "consumer-check", "data": {"passed": True, "returncode": 0}}, observed["state"], criterion, observed)
    assert not predicates["continuation-cancellation"]({"kind": "continuation-cancellation", "data": {"cancelled": False}}, observed["state"], criterion, observed)
