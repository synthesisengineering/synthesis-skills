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
