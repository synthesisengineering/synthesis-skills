#!/usr/bin/env python3
"""Execute a registered Python consumer check under the native OS sandbox.

This observer is invoked by the run engine, which records its actual result.
It never accepts caller-supplied output, a PASS assertion, or action approval.
The declared check is task-owned code: its adequacy still needs review. A
separate process is not evidence of independent test design.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate consumer JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("non-finite consumer JSON value")))


def _same_json(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def run_python_check(*args, **kwargs):
    # Stop only verifies existing observations; importing the execution runner
    # belongs to active checks, not the latency-sensitive passive path.
    from evaluation_artifacts import run_python_check as execute
    return execute(*args, **kwargs)


def _registered(context, identity):
    record = context["artifacts"].get(identity)
    if not isinstance(record, dict):
        raise ValueError("consumer requires a registered artifact")
    root = Path(context["project"]).resolve()
    raw = Path(record["path"])
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError("consumer artifact path escapes the project")
    path = root / raw
    if path.is_symlink() or any(p.is_symlink() for p in path.parents) or not path.is_file():
        raise ValueError("consumer artifact path is unsafe or missing")
    if hashlib.sha256(path.read_bytes()).hexdigest() != record["digest"]:
        raise ValueError("consumer artifact changed since registration")
    return path, record


def observe(context, payload):
    if not isinstance(payload, dict) or set(payload) != {"check_id"}:
        raise ValueError("consumer accepts only a registered check_id")
    spec_path, spec_record = _registered(context, payload["check_id"])
    if spec_record["role"] != "input":
        raise ValueError("check specification must be a registered input")
    spec = _json(spec_path.read_text())
    fields = {"schema_version", "kind", "criterion_id", "artifact_id", "script_artifact_id", "expected", "argv", "timeout_seconds"}
    if not isinstance(spec, dict) or set(spec) != fields or type(spec["schema_version"]) is not int or spec["schema_version"] != 1 or spec["kind"] != "python-consumer":
        raise ValueError("unknown consumer check schema or kind")
    criteria = context["state"]["contract"]["criteria"]
    criterion = next((c for c in criteria if c["id"] == spec["criterion_id"]), None)
    if criterion is None or spec["artifact_id"] not in criterion["artifact_ids"]:
        raise ValueError("consumer expands the accepted criterion")
    _, output = _registered(context, spec["artifact_id"])
    script, program = _registered(context, spec["script_artifact_id"])
    if program["role"] != "input" or script.suffix != ".py":
        raise ValueError("consumer script must be a registered Python input")
    argv, timeout = spec["argv"], spec["timeout_seconds"]
    if not isinstance(argv, list) or len(argv) > 32 or any(not isinstance(a, str) or len(a) > 4096 or "\0" in a for a in argv):
        raise ValueError("invalid bounded consumer arguments")
    if type(timeout) is not int or not 1 <= timeout <= 60:
        raise ValueError("consumer timeout must be 1 through 60 seconds")
    before = {identity: _registered(context, identity)[1]["digest"] for identity in context["artifacts"]}
    execution = run_python_check(script, Path(context["project"]), argv,
                                 timeout_seconds=timeout, output_limit=65536)
    for identity in before:
        _registered(context, identity)
    stdout, stderr = execution.pop("stdout"), execution.pop("stderr")
    execution.update(logical_argv=[str(Path(sys.executable).resolve()), "-I", str(script), *argv],
                     interpreter_version=sys.version.split()[0],
                     stdout_digest=hashlib.sha256(stdout.encode()).hexdigest(),
                     stderr_digest=hashlib.sha256(stderr.encode()).hexdigest())
    try:
        observed = _json(stdout)
    except (ValueError, TypeError):
        observed = None
    successful = (execution["returncode"] == 0 and execution["sandbox_verified"] is True
                  and not execution["timed_out"] and not execution["output_exceeded"])
    return {"check_id": payload["check_id"], "criterion_id": spec["criterion_id"],
            "artifact_id": spec["artifact_id"], "artifact_digest": output["digest"],
            "input_digests": before, "domain": "software", "rubric": "declared Python consumer result",
            "method": "sandboxed registered consumer", "producer": context["binding"]["session_uuid"],
            "reviewer": "bundled-consumer-check/1", "independent": False,
            "observations": {"expected": spec["expected"], "observed": observed,
                             "consumer_verified": successful},
            "findings": [] if successful and _same_json(observed, spec["expected"]) else ["Consumer did not establish the expected result"],
            "passed": successful and _same_json(observed, spec["expected"]), "execution": execution}


def register_observers(register_observer):
    register_observer("consumer-check", observe)


def accept(record, state, criterion, context):
    data = record.get("data", {})
    execution = data.get("execution", {})
    return (data.get("criterion_id") == criterion["id"] and data.get("artifact_id") in criterion["artifact_ids"]
            and data.get("passed") is True and execution.get("returncode") == 0
            and execution.get("sandbox_verified") is True and not execution.get("timed_out")
            and not execution.get("output_exceeded"))
