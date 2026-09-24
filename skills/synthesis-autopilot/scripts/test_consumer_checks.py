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
