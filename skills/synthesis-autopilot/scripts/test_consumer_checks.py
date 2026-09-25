"""Actual bounded consumer observations; self-reported PASS is never input."""
from __future__ import annotations
import hashlib
import importlib
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture
def checks():
    return importlib.import_module("consumer_checks")


@pytest.fixture
def consumer(tmp_path):
    files = {"output": ("result.json", '{"answer":5}'),
             "program": ("check.py", 'import json\nfrom pathlib import Path\nprint(json.dumps(json.loads(Path("result.json").read_text())))\n'),
             "spec": ("check.json", json.dumps({"schema_version": 1, "kind": "python-consumer",
                 "criterion_id": "accept", "artifact_id": "output", "script_artifact_id": "program",
                 "expected": {"answer": 5}, "argv": [], "timeout_seconds": 2}))}
    artifacts = {}
    for identity, (name, content) in files.items():
        (tmp_path / name).write_text(content)
        artifacts[identity] = {"path": name, "digest": hashlib.sha256(content.encode()).hexdigest(),
                               "role": "output" if identity == "output" else "input"}
    return {"project": tmp_path, "artifacts": artifacts,
            "state": {"contract": {"criteria": [{"id": "accept", "artifact_ids": ["output"]}]}},
            "binding": {"session_uuid": "producer"}}


def test_consumer_observes_actual_subprocess_and_target(checks, consumer):
    result = checks.observe(consumer, {"check_id": "spec"})
    assert result["passed"] is True
    assert result["observations"] == {"expected": {"answer": 5}, "observed": {"answer": 5}, "consumer_verified": True}
    assert result["execution"]["sandbox_verified"] is True
    assert result["execution"]["returncode"] == 0
    assert len(result["execution"]["stdout_digest"]) == 64
    assert result["artifact_digest"] == consumer["artifacts"]["output"]["digest"]
    assert result["independent"] is False  # A separate process is not an independent test design.


def test_consumer_requires_registered_unchanged_spec_and_inputs(checks, consumer):
    (consumer["project"] / "result.json").write_text('{"answer":99}')
    with pytest.raises(ValueError, match="changed"):
        checks.observe(consumer, {"check_id": "spec"})


def test_consumer_refuses_forged_result_unknown_spec_and_unsafe_path(checks, consumer):
    with pytest.raises(ValueError):
        checks.observe(consumer, {"check_id": "spec", "passed": True})
    with pytest.raises(ValueError):
        checks.observe(consumer, {"check_id": "missing"})
    path = consumer["project"] / "check.py"
    path.unlink()
    path.symlink_to("/etc/passwd")
    with pytest.raises(ValueError):
        checks.observe(consumer, {"check_id": "spec"})


def test_failed_actual_consumer_stays_failed(checks, consumer):
    path = consumer["project"] / "check.py"
    path.write_text('print("self-reported PASS")\n')
    consumer["artifacts"]["program"]["digest"] = hashlib.sha256(path.read_bytes()).hexdigest()
    result = checks.observe(consumer, {"check_id": "spec"})
    assert result["passed"] is False
    assert result["observations"]["observed"] is None


def test_execution_unavailable_is_not_a_result(checks, consumer, monkeypatch):
    def unavailable(*args, **kwargs):
        raise ValueError("OS sandbox unavailable")
    monkeypatch.setattr(checks, "run_python_check", unavailable)
    with pytest.raises(ValueError, match="sandbox"):
        checks.observe(consumer, {"check_id": "spec"})


@pytest.mark.parametrize("corruption", ["duplicate", "nonfinite", "boolean-schema"])
def test_consumer_rejects_ambiguous_specification_json(checks, consumer, corruption):
    path = consumer["project"] / "check.json"
    raw = path.read_text()
    if corruption == "duplicate":
        raw = raw.replace('"schema_version": 1', '"schema_version": 9, "schema_version": 1')
    elif corruption == "nonfinite":
        raw = raw.replace('"answer": 5', '"answer": NaN')
    else:
        raw = raw.replace('"schema_version": 1', '"schema_version": true')
    path.write_text(raw)
    consumer["artifacts"]["spec"]["digest"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        checks.observe(consumer, {"check_id": "spec"})


def test_boolean_does_not_satisfy_numeric_consumer_result(checks, consumer):
    spec = consumer["project"] / "check.json"
    spec.write_text(spec.read_text().replace('"answer": 5', '"answer": 1'))
    program = consumer["project"] / "check.py"
    program.write_text('print(\'{"answer":true}\')\n')
    for identity, path in (("spec", spec), ("program", program)):
        consumer["artifacts"][identity]["digest"] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert checks.observe(consumer, {"check_id": "spec"})["passed"] is False


@pytest.mark.parametrize("stdout,expected_pass", [("null", True), ("self-reported PASS", False), ("", False), ("NaN", False)])
def test_null_result_requires_successfully_decoded_json(checks, consumer, stdout, expected_pass):
    spec = consumer["project"] / "check.json"
    value = json.loads(spec.read_text()); value["expected"] = None
    spec.write_text(json.dumps(value))
    program = consumer["project"] / "check.py"
    program.write_text("print(" + repr(stdout) + ")\n")
    for identity, path in (("spec", spec), ("program", program)):
        consumer["artifacts"][identity]["digest"] = hashlib.sha256(path.read_bytes()).hexdigest()
    result = checks.observe(consumer, {"check_id": "spec"})
    assert result["execution"]["returncode"] == 0
    assert result["observations"]["observed"] is None
    assert result["passed"] is expected_pass
    assert result["observations"]["consumer_verified"] is expected_pass


def test_ambiguous_historical_null_needs_fresh_decoding_proof(checks, consumer):
    spec = consumer["project"] / "check.json"
    value = json.loads(spec.read_text()); value["expected"] = None; spec.write_text(json.dumps(value))
    program = consumer["project"] / "check.py"; program.write_text('print("null")\n')
    for identity, path in (("spec", spec), ("program", program)):
        consumer["artifacts"][identity]["digest"] = hashlib.sha256(path.read_bytes()).hexdigest()
    data = checks.observe(consumer, {"check_id": "spec"})
    criterion = consumer["state"]["contract"]["criteria"][0]
    assert checks.accept({"data": data}, consumer["state"], criterion, consumer)
    # Simulated historical format lacks the decoding fact; old observers used
    # the same null value for a parse failure. Preserve it but require a rerun.
    data["execution"].pop("json_decoded")
    assert not checks.accept({"data": data}, consumer["state"], criterion, consumer)
