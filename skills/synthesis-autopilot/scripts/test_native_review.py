"""Native provenance fixtures; no fixture represents a live review acceptance."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_evidence_bridge import observed, record, append_claude_tool  # noqa: F401
from test_run_admission import world  # noqa: F401


@pytest.fixture
def review():
    return importlib.import_module("native_review")


def package(context, reviewer="claude-agent:review-call"):
    bindings = {key: context["state"][key] for key in ("run_id", "contract_digest", "profile_digest")}
    request = {"schema_version": 1, "kind": "quality_observation", "bindings": bindings,
               "artifact_digests": {"output": "a" * 64}, "producer": context["binding"]["native_ref"]}
    data = {"criterion_id": "accept", "artifact_id": "output", "artifact_digest": "a" * 64,
            "rubric": "fixture-rubric", "method": "independent-review", "producer": request["producer"],
            "reviewer": reviewer, "independent": True, "domain": "code", "findings": [],
            "observations": {"functional": True, "edge_cases": True, "maintainable": True}}
    context["artifacts"]["output"] = {"path": "output.txt", "digest": "a" * 64}
    response = {"schema_version": 1, "kind": request["kind"], "bindings": bindings, "data": data}
    return request, response


def test_claude_agent_result_requires_native_pair_and_exact_review_bindings(review, observed, world):
    request, response = package(observed)
    append_claude_tool(world, "Agent", {"prompt": json.dumps({"autopilot_review": request})},
                      {"autopilot_review": response}, "review-call")
    data = {**response["data"], "source": {"kind": "native-agent", "call_id": "review-call"}}
    receipt = record("quality_observation", data, observed)
    assert review.verify_source(receipt, observed)
    changed = deepcopy(receipt)
    changed["data"]["findings"] = [{"severity": "critical", "resolved": False}]
    assert not review.verify_source(changed, observed)
    observed["artifacts"]["output"]["digest"] = "b" * 64
    assert not review.verify_source(receipt, observed)


@pytest.mark.parametrize("mutation", ["shell", "duplicate", "error", "producer"])
def test_native_review_rejects_self_certification_and_ambiguous_or_failed_calls(review, observed, world, mutation):
    request, response = package(observed)
    if mutation == "producer":
        response["data"]["reviewer"] = request["producer"]
    name = "Bash" if mutation == "shell" else "Agent"
    append_claude_tool(world, name, {"prompt": json.dumps({"autopilot_review": request})},
                      {"autopilot_review": response}, "review-call")
    if mutation == "duplicate":
        append_claude_tool(world, name, {"prompt": json.dumps({"autopilot_review": request})},
                          {"autopilot_review": response}, "review-call")
    if mutation == "error":
        raw = world["transcript"].read_text().replace('"tool_result",', '"tool_result", "is_error": true,')
        world["transcript"].write_text(raw)
    receipt = record("quality_observation", {**response["data"], "source": {"kind": "native-agent", "call_id": "review-call"}}, observed)
    assert not review.verify_source(receipt, observed)


def test_codex_plaintext_child_parser_requires_namespace_target_and_full_visible_body(review, observed):
    request, response = package(observed, reviewer="/root/reviewer")
    call = {"type": "response_item", "payload": {"type": "function_call", "namespace": "collaboration",
        "name": "followup_task", "call_id": "dispatch", "arguments": json.dumps({"target": "/root/reviewer",
        "message": json.dumps({"autopilot_review": request})})}}
    message = {"type": "response_item", "payload": {"type": "agent_message", "id": "result",
        "author": "/root/reviewer", "recipient": "/root", "content": [{"type": "input_text",
        "text": json.dumps({"autopilot_review": response})}]}}
    source = {"kind": "native-child", "call_id": "dispatch", "message_id": "result"}
    assert review.parse_codex_child([call, message], source)["reviewer"] == "/root/reviewer"
    encrypted = deepcopy(message)
    encrypted["payload"]["content"].append({"type": "encrypted_content", "encrypted_content": "opaque"})
    assert review.parse_codex_child([call, encrypted], source) is None
    call["payload"]["namespace"] = "untrusted"
    assert review.parse_codex_child([call, message], source) is None


def test_native_user_amendment_is_exact_instruction_not_assistant_or_tool_text(review, observed, world):
    data = {"approved": True, "replacement_digest": "b" * 64}
    instruction = {"autopilot_authorization": {"schema_version": 1, "kind": "profile-amendment",
        "bindings": {key: observed["state"][key] for key in ("run_id", "contract_digest", "profile_digest")}, "data": data}}
    event = {"type": "user", "uuid": "user-approval", "sessionId": world["actor"]["native_payload"]["session_id"],
             "message": {"role": "user", "content": json.dumps(instruction)}}
    with world["transcript"].open("a") as stream:
        stream.write(json.dumps(event) + "\n")
    receipt = record("profile-amendment", {**data, "source": {"kind": "native-user", "message_id": "user-approval"}}, observed)
    assert review.verify_source(receipt, observed)
    receipt["data"]["replacement_digest"] = "c" * 64
    assert not review.verify_source(receipt, observed)
    receipt["data"]["replacement_digest"] = "b" * 64
    world["transcript"].write_text(world["transcript"].read_text().replace('"type": "user", "uuid": "user-approval"', '"type": "assistant", "uuid": "user-approval"'))
    assert not review.verify_source(receipt, observed)


def test_codex_delegation_requires_native_dispatch_ack_and_exact_canonical_target(review, observed):
    data = {"child_id": "/root/worker", "mode": "artifact-only", "integration_owner": observed["binding"]["session_uuid"],
            "task_id": "build", "paths": ["/fixture/project/output"], "deliverables": ["Output"], "criteria": ["accept"],
            "reservation_id": "work", "integration_reservation_id": "integrate", "return_contract": ["artifact_ids", "evidence_ids", "disposition"],
            "cancellation": "Return partial artifacts when cancelled"}
    envelope = {"schema_version": 1, "kind": "delegation", "bindings": {
        key: observed["state"][key] for key in ("run_id", "contract_digest", "profile_digest")}, "data": data}
    call = {"type": "response_item", "payload": {"type": "function_call", "namespace": "collaboration",
        "name": "followup_task", "call_id": "dispatch", "arguments": json.dumps({"target": "/root/worker",
        "message": json.dumps({"autopilot_delegation": envelope})})}}
    ack = {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "dispatch", "output": ""}}
    source = {"kind": "native-dispatch", "call_id": "dispatch"}
    assert review.parse_codex_dispatch([call, ack], source) == envelope
    assert review.parse_codex_dispatch([call], source) is None
    assert review.parse_codex_dispatch([call, ack, ack], source) is None
    call["payload"]["arguments"] = json.dumps({"target": "/root/foreign", "message": json.dumps({"autopilot_delegation": envelope})})
    assert review.parse_codex_dispatch([call, ack], source) is None


def muse_event(native, event):
    return {"schema_version": 1, "stream": {"kind": "session", "id": native},
            "record_type": "event", "payload_type": "runtime.session",
            "payload": {"kind": "run", "run_id": "native-run", "event": event}}


def test_muse_review_binds_native_spawn_and_ready_result_not_arbitrary_tool_text(review, observed):
    native = "01990000-0000-7000-8000-000000000044"
    child = "01990000-0000-7000-8000-000000000055"
    request, response = package(observed, reviewer="muse-subagent:" + child)
    calls = [muse_event(native, {"kind": "assistant_tool_calls_committed", "tool_calls": [{
        "id": "spawn-item", "call_id": "spawn", "name": "subagent_spawn", "args": json.dumps({
        "command_id": "spawn-command", "objective": json.dumps({"autopilot_review": request}), "role": "reviewer"})}]}),
        muse_event(native, {"kind": "tool_result_batch_committed", "results": [{"tool_call_id": "spawn", "text": json.dumps({
            "status": "accepted", "subagent_id": child, "task_ref": "task/fixture#0", "agent_path": "main/reviewer/1", "work_id": "fixture-work"})}]}),
        muse_event(native, {"kind": "assistant_tool_calls_committed", "tool_calls": [{"id": "read-item", "call_id": "read",
            "name": "subagent_read_result", "args": json.dumps({"subagent_id": child})}]}),
        muse_event(native, {"kind": "tool_result_batch_committed", "results": [{"tool_call_id": "read", "text": json.dumps({
            "status": "ready", "subagent_id": child, "task_ref": "task/fixture#5", "summary": json.dumps({"autopilot_review": response}),
            "workspace": None, "evidence_refs": [], "artifact_refs": []})}]})]
    source = {"kind": "native-muse-child", "spawn_call_id": "spawn", "result_call_id": "read"}
    assert review.parse_muse_review(calls, source, native)["response"] == response
    assert review.parse_muse_review(calls + [calls[-1]], source, native) is None
    changed = deepcopy(calls)
    changed[2]["payload"]["event"]["tool_calls"][0]["name"] = "bash"
    assert review.parse_muse_review(changed, source, native) is None
    changed = deepcopy(calls)
    changed[-1]["stream"]["id"] = "foreign"
    assert review.parse_muse_review(changed, source, native) is None
    for invalid in ("task/foreign#5", "task/fixture#-1", "fixture#5"):
        changed = deepcopy(calls)
        output = json.loads(changed[-1]["payload"]["event"]["results"][0]["text"])
        output["task_ref"] = invalid
        changed[-1]["payload"]["event"]["results"][0]["text"] = json.dumps(output)
        assert review.parse_muse_review(changed, source, native) is None
    changed = deepcopy(calls)
    output = json.loads(changed[1]["payload"]["event"]["results"][0]["text"])
    output["task_ref"] = "task/fixture#6"
    changed[1]["payload"]["event"]["results"][0]["text"] = json.dumps(output)
    assert review.parse_muse_review(changed, source, native) is None
    changed = deepcopy(calls)
    changed.insert(2, muse_event(native, {"kind": "assistant_tool_calls_committed", "tool_calls": [{
        "call_id": "followup", "name": "subagent_send_message", "args": json.dumps({
            "subagent_id": child, "message": "Change the task", "mode": "followup"})}]}))
    assert review.parse_muse_review(changed, source, native) is None


def test_async_native_question_reply_is_bound_to_exact_question_and_positive_option(review):
    title = "Approve the reviewed proposal at project/proposal.json (sha256 " + "a" * 64 + ")?"
    call = {"type": "response_item", "payload": {"type": "function_call", "name": "request_user_input_async",
        "call_id": "question-call", "arguments": json.dumps({"questions": [{"title": title, "options": ["Approve proposal", "Keep current contract"]}]})}}
    ack = {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "question-call", "output": '{"accepted":true}'}}
    answer = {"questionItemId": json.dumps(["request_user_input_async", "question-call", 0]), "question": title, "answer": "Approve proposal"}
    reply = {"type": "response_item", "payload": {"type": "message", "id": "user-answer", "role": "user", "content": [{"type": "input_text",
        "text": "<send_user_message_question_reply>\n" + json.dumps([answer]) + "\n</send_user_message_question_reply>"}]}}
    source = {"kind": "native-question", "call_id": "question-call", "message_id": "user-answer", "question_index": 0}
    assert review.parse_codex_question([call, ack, reply], source, title, "Approve proposal") is True
    assert review.parse_codex_question([call, ack], source, title, "Approve proposal") is False
    assert review.parse_codex_question([call, ack, reply], source, title + "changed", "Approve proposal") is False
    assert review.parse_codex_question([call, ack, reply], source, title, "Keep current contract") is False
    reply["payload"]["role"] = "assistant"
    assert review.parse_codex_question([call, ack, reply], source, title, "Approve proposal") is False


def calibration_package(context, request, response):
    import hashlib
    def artifact(ident, text):
        path = context["project"] / (ident + ".json")
        path.write_text(text)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        context["artifacts"][ident] = {"path": path.name, "digest": digest}
        return digest
    rubric = artifact("rubric", '"Check the stated writing dimensions"')
    positive = artifact("positive-control", '"A complete source-faithful control"')
    negative = artifact("negative-control", '"A control with a deliberate unsupported statement"')
    controls = [{"artifact_id": "positive-control", "artifact_digest": positive, "expected": "PASS"},
                {"artifact_id": "negative-control", "artifact_digest": negative, "expected": "FAIL"}]
    manifest = {"schema_version": 1, "domain": "writing", "rubric": "fixture-rubric", "rubric_artifact_id": "rubric",
                "rubric_digest": rubric, "controls": controls}
    manifest_digest = artifact("control-manifest", json.dumps(manifest))
    request["artifact_digests"].update({"rubric": rubric, "positive-control": positive, "negative-control": negative})
    response["data"].update(domain="writing", calibrated=True,
        observations={"source_fidelity": True, "reader_purpose": True, "structure": True, "voice": True},
        calibration={"manifest_id": "control-manifest", "manifest_digest": manifest_digest,
            "reviewer": response["data"]["reviewer"], "rubric_artifact_id": "rubric", "rubric_digest": rubric,
            "observations": [{"artifact_id": row["artifact_id"], "artifact_digest": row["artifact_digest"], "verdict": row["expected"]} for row in controls]})


@pytest.mark.parametrize("case", ["flag-only", "valid", "false-positive", "visible-labels", "failed-calibration"])
def test_native_calibration_rederives_blind_positive_and_negative_controls(review, observed, world, case):
    request, response = package(observed)
    response["data"].update(domain="writing", calibrated=True)
    if case != "flag-only":
        calibration_package(observed, request, response)
    if case in {"false-positive", "failed-calibration"}:
        response["data"]["calibration"]["observations"][1]["verdict"] = "PASS"
    if case == "failed-calibration":
        response["data"]["calibrated"] = False
    if case == "visible-labels":
        request["artifact_digests"]["control-manifest"] = observed["artifacts"]["control-manifest"]["digest"]
    append_claude_tool(world, "Agent", {"prompt": json.dumps({"autopilot_review": request})}, {"autopilot_review": response}, "review-call")
    receipt = record("quality_observation", {**response["data"], "source": {"kind": "native-agent", "call_id": "review-call"}}, observed)
    assert review.verify_source(receipt, observed) is (case in {"valid", "failed-calibration"})


def _mutate_after_first_native_read(monkeypatch, path, mutation):
    original = Path.open
    changed = False
    class Reader:
        def __init__(self, stream): self.stream = stream
        def __enter__(self): return self
        def __exit__(self, *args): return self.stream.__exit__(*args)
        def __getattr__(self, name): return getattr(self.stream, name)
        def read(self, *args):
            nonlocal changed
            value = self.stream.read(*args)
            if not changed:
                changed = True
                mutation()
            return value
    def opened(target, *args, **kwargs):
        stream = original(target, *args, **kwargs)
        return Reader(stream) if target == path and args and args[0] == 'rb' else stream
    monkeypatch.setattr(Path, 'open', opened)


def test_native_snapshot_accepts_identical_completed_prefix_during_append(review, tmp_path, monkeypatch):
    path = tmp_path / 'native.jsonl'
    path.write_bytes(b'{"id":"complete"}\n')
    def append():
        with path.open('ab') as stream:
            stream.write(b'{"id":"later"}\n{"partial":')
    _mutate_after_first_native_read(monkeypatch, path, append)
    assert review._records(path) == [{'id': 'complete'}]


@pytest.mark.parametrize('mutation', ['in-place', 'truncate', 'replace', 'symlink'])
def test_native_snapshot_rejects_changed_or_replaced_selected_prefix(review, tmp_path, monkeypatch, mutation):
    path = tmp_path / 'native.jsonl'
    original = b'{"id":"complete"}\n'
    path.write_bytes(original)
    replacement = tmp_path / 'replacement.jsonl'
    replacement.write_bytes(original)
    def change():
        if mutation == 'in-place': path.write_bytes(original.replace(b'complete', b'changed!'))
        elif mutation == 'truncate': path.write_bytes(b'')
        elif mutation == 'replace': replacement.replace(path)
        else:
            path.unlink()
            path.symlink_to(replacement)
    _mutate_after_first_native_read(monkeypatch, path, change)
    with pytest.raises(ValueError): review._records(path)


def test_native_snapshot_uses_only_complete_initial_lines_and_keeps_bound(review, tmp_path, monkeypatch):
    path = tmp_path / 'native.jsonl'
    path.write_bytes(b'{"id":"old-outside-window"}\n{"id":"inside"}\n{"unfinished":')
    monkeypatch.setattr(review, 'MAX_TRANSCRIPT_BYTES', 36)
    assert review._records(path) == [{'id': 'inside'}]
    path.write_bytes(b'{"unfinished":')
    with pytest.raises(ValueError): review._records(path)
    path.write_bytes(b'{invalid}\n')
    with pytest.raises(ValueError): review._records(path)
