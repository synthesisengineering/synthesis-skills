"""Bounded native CLI review executes once and grades blind controls itself."""
import hashlib
import importlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture
def observer():
    return importlib.import_module("native_review_observer")


@pytest.fixture
def review(tmp_path):
    files = {"draft": "The sample is five.", "rubric": "Reject unsupported facts.",
             "one": "The sample is five.", "two": "The sample is five hundred."}
    artifacts = {}
    def add(key, body):
        (tmp_path / (key + ".txt")).write_text(body)
        artifacts[key] = {"path": key + ".txt", "digest": hashlib.sha256(body.encode()).hexdigest(),
                          "role": "output" if key == "draft" else "input"}
    for key, body in files.items():
        add(key, body)
    manifest = {"schema_version": 1, "domain": "writing", "rubric": "Source fidelity",
                "rubric_artifact_id": "rubric", "rubric_digest": artifacts["rubric"]["digest"],
                "controls": [{"artifact_id": key, "artifact_digest": artifacts[key]["digest"], "expected": value}
                             for key, value in (("one", "PASS"), ("two", "FAIL"))]}
    add("gold", json.dumps(manifest))
    context = {"project": tmp_path, "artifacts": artifacts, "evidence": {},
        "binding": {"session_uuid": "owner"},
        "state": {"run_id": "run-one", "contract_digest": "a" * 64, "profile_digest": "b" * 64,
                  "contract": {"criteria": [{"id": "accept", "artifact_ids": ["draft"]}]},
                  "extensions": {"workflow": {"budget": {"reservations": {
                      "review-one": {"status": "reserved", "category": "review", "amounts": {"wall_millis": 120000, "usd_micros": 2000000}}}}}}}}
    arguments = {"mode": "native-cli", "client": "claude", "criterion_id": "accept", "artifact_id": "draft",
                 "calibration_manifest_id": "gold", "reservation_id": "review-one", "timeout_seconds": 120,
                 "max_cost_usd": 2}
    return context, arguments


def result(prompt, failed=False):
    request = json.loads(prompt.split("\nREQUEST\n", 1)[1])
    response = {"bindings": request["bindings"], "artifact_digest": request["artifact_digest"],
        "observations": {"source_fidelity": True, "reader_purpose": True, "structure": True, "voice": True},
        "findings": [], "controls": [{"artifact_id": c["artifact_id"], "artifact_digest": c["digest"],
            "verdict": "PASS" if c["content"] == "The sample is five." or failed else "FAIL"} for c in request["controls"]]}
    return {"response": response, "session_id": "native-child", "model": "configured-native-model",
            "usage": {"cost_usd": 0.1}, "stdout_digest": "c" * 64, "wall_seconds": 1,
            "returncode": 0, "tool_calls": [], "client": "claude"}


def test_observer_hides_gold_and_derives_calibration(observer, review, monkeypatch):
    context, args = review
    def execute(client, prompt, **kwargs):
        assert '"expected"' not in prompt and '"gold"' not in prompt
        return result(prompt)
    monkeypatch.setattr(observer, "execute_native", execute)
    actual = observer.observe_native_cli_review(context, args)
    assert actual["calibrated"] is True and actual["passed"] is True
    assert actual["independent"] is True and actual["reviewer"] == "claude-cli:native-child"
    assert actual["execution"]["usage"]["cost_usd"] == 0.1
    with pytest.raises(ValueError, match="attempt"):
        observer.observe_native_cli_review(context, args)


def test_bad_blind_control_remains_authentic_failed_calibration(observer, review, monkeypatch):
    context, args = review
    monkeypatch.setattr(observer, "execute_native", lambda client, prompt, **kw: result(prompt, True))
    actual = observer.observe_native_cli_review(context, args)
    assert actual["calibrated"] is False and actual["passed"] is False


@pytest.mark.parametrize("defect", ["tool", "binding", "artifact", "returncode", "duplicate-control"])
def test_invalid_native_observation_does_not_become_evidence(observer, review, monkeypatch, defect):
    context, args = review
    def execute(client, prompt, **kwargs):
        native = result(prompt)
        if defect == "tool": native["tool_calls"] = ["shell"]
        if defect == "binding": native["response"]["bindings"]["run_id"] = "elsewhere"
        if defect == "artifact": (context["project"] / "draft.txt").write_text("changed")
        if defect == "returncode": native["returncode"] = 1
        if defect == "duplicate-control": native["response"]["controls"][1] = native["response"]["controls"][0]
        return native
    monkeypatch.setattr(observer, "execute_native", execute)
    with pytest.raises(ValueError): observer.observe_native_cli_review(context, args)


def test_review_without_reserved_resources_does_not_launch(observer, review, monkeypatch):
    context, args = review
    context["state"]["extensions"]["workflow"]["budget"]["reservations"].clear()
    monkeypatch.setattr(observer, "execute_native", lambda *a, **kw: pytest.fail("must not execute"))
    with pytest.raises(ValueError, match="reservation"):
        observer.observe_native_cli_review(context, args)


def test_interrupted_attempt_cannot_repeat_provider_call(observer, review, monkeypatch):
    context, args = review
    def interrupt(*a, **kw): raise TimeoutError("native review timed out")
    monkeypatch.setattr(observer, "execute_native", interrupt)
    with pytest.raises(TimeoutError): observer.observe_native_cli_review(context, args)
    with pytest.raises(ValueError, match="attempt"): observer.observe_native_cli_review(context, args)


@pytest.mark.parametrize("client", ["claude", "codex", "muse"])
def test_supported_native_argv_has_restricted_tools_and_no_shell_override(observer, tmp_path, client):
    argv = observer.native_argv(client, "/tools/" + client, tmp_path, {"model": "chosen", "model_reasoning_effort": "high"})
    assert not any(flag in argv for flag in ("--yolo", "--disable-sandbox", "--dangerously-bypass-approvals-and-sandbox"))
    if client == "claude": assert "--safe-mode" in argv and argv[argv.index("--tools") + 1] == ""
    if client == "codex": assert "read-only" in argv and "--ignore-user-config" in argv and "shell_tool" in argv
    if client == "muse": assert all(v in argv for v in ("--disable-write", "--disable-shell", "--disable-web-tools"))


def test_native_parsers_require_actual_completed_identity(observer):
    answer = {"bindings": {}, "controls": []}
    claude = [{"type": "system", "subtype": "init", "session_id": "native", "model": "configured", "tools": []},
              {"type": "result", "subtype": "success", "is_error": False, "session_id": "native", "result": json.dumps(answer), "total_cost_usd": 0.1}]
    assert observer.parse_native("claude", claude)["response"] == answer
    with pytest.raises(ValueError): observer.parse_native("claude", claude[1:])
    codex = [{"type": "thread.started", "thread_id": "native"}, {"type": "turn.started"},
             {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(answer)}},
             {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 4}}]
    assert observer.parse_native("codex", codex)["session_id"] == "native"
    with pytest.raises(ValueError): observer.parse_native("codex", codex[:-1])


def test_muse_parser_binds_native_completion_and_rejects_tool_activity(observer):
    def event(seq, kind, payload):
        return {"schema_version": 1, "stream": {"kind": "session", "id": "native"}, "sequence": seq,
                "causation_id": "command", "payload_type": kind,
                "payload": {"command_id": "command", **payload}}
    events = [event(1, "runtime.command.accepted", {"kind": "command_accepted", "command_kind": "turn.submit"}),
              event(2, "turn.input.user", {"kind": "turn_input_user", "prompt": "review"}),
              event(3, "run.terminal.completed", {"kind": "run_terminal", "terminal": "completed",
                  "run_stream": {"kind": "run", "id": "command"}, "text": '{"answer":5}', "reason": None})]
    assert observer.parse_native("muse", events)["response"] == {"answer": 5}
    with pytest.raises(ValueError): observer.parse_native("muse", events[:-1])
    events.insert(2, event(2.5, "runtime.session", {"kind": "run", "event": {"kind": "assistant_tool_calls_committed", "tool_calls": [{"name": "read_file"}]}}))
    with pytest.raises(ValueError): observer.parse_native("muse", events)
