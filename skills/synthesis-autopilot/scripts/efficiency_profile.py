#!/usr/bin/env python3
"""Bounded local profiling of existing owners; no model/provider operations.

Cold means a new Python interpreter, not a flushed OS cache or uncached model
prompt. Warm repeats still revalidate current owner/source state. The existing
native_review_observer process owner supplies finite time/output/reap control;
only this file's fixed Python probe is launched, never a caller command.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time
import tracemalloc

MAX_INPUT_BYTES = 64 * 1024
OWNERS = {
    "startup": "PM native identity, current registry and claimed paths",
    "resume": "current run journal and fresh owner/evidence inspection",
    "checkpoint": "read-only checkpoint capsule computation with live PM admission",
    "review": "current criterion evidence report; no model reviewer",
}


def _json(raw):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate profiling field")
            result[key] = value
        return result

    if not isinstance(raw, bytes) or len(raw) > MAX_INPUT_BYTES:
        raise ValueError("profiling input bound")
    value = json.loads(
        raw,
        object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(
            ValueError("nonfinite profiling input")
        ),
    )
    if not isinstance(value, dict):
        raise ValueError("profiling input must be an object")
    return value


def _spec(value):
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "owner",
        "project",
        "project_id",
        "run_id",
        "actor",
    }:
        raise ValueError("profiling requires exact current owner inputs")
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["owner"] not in OWNERS
    ):
        raise ValueError("unsupported profiling owner/schema")
    if (
        not isinstance(value["project"], str)
        or not Path(value["project"]).is_absolute()
        or ".." in Path(value["project"]).parts
    ):
        raise ValueError("profiling requires an absolute project")
    if not isinstance(value["actor"], dict) or set(value["actor"]) != {
        "board",
        "native_payload",
    }:
        raise ValueError("profiling requires native owner inputs")
    for key in ("project_id", "run_id"):
        if not isinstance(value[key], str) or not 1 <= len(value[key]) <= 128:
            raise ValueError("invalid profiling identity")
    if len(json.dumps(value).encode()) > MAX_INPUT_BYTES:
        raise ValueError("profiling case byte bound")


def _digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _operation(spec):
    import autopilot

    engine = autopilot.engine()
    project = Path(spec["project"])
    actor = spec["actor"]
    state = engine.load_run(project, spec["run_id"])
    if state["project_id"] != spec["project_id"]:
        raise ValueError("profiling cannot change selected project")
    if spec["owner"] == "startup":
        proof = engine._binding(project, state, actor, readonly=True)
        return {
            "status": "PASS",
            "project_id": proof["project_id"],
            "owner": proof["native_ref"],
            "claim_hash": proof["claim_hash"],
        }
    if spec["owner"] == "checkpoint":
        from run_admission import admission_scope
        import recovery_capsule

        proof = engine._binding(project, state, actor, readonly=True)
        with admission_scope(proof, actor, project) as token:
            context = engine._context_observed(
                project, state, {}, proof, actor=actor, observation=token
            )
            context.update(
                project=project, state=state, actor=actor, admission_observation=token
            )
            capsule = recovery_capsule.capture(context)
        return {
            "status": "PASS",
            "run_id": capsule["run_id"],
            "basis": capsule["basis"],
            "obligations_sha256": _digest(capsule["obligations"]),
            "authority_granted": capsule["authority_granted"],
        }
    context = engine.inspect_context(state, actor, project=project)
    if spec["owner"] == "review":
        result = engine.criterion_report(state, context)
        return {"status": result["status"], "criteria": result["criteria"]}
    return {
        "status": "PASS",
        "run_id": state["run_id"],
        "revision": state["revision"],
        "plan_digest": context["plan_digest"],
        "owner": context["binding"]["native_ref"],
        "claim_hash": context["binding"]["claim_hash"],
        "artifacts": {k: v["digest"] for k, v in context["artifacts"].items()},
    }


def _probe(spec, iterations):
    _spec(spec)
    if type(iterations) is not int or not 1 <= iterations <= 5:
        raise ValueError("probe iteration bound")
    samples = []
    for _ in range(iterations):
        tracemalloc.start()
        cpu = time.process_time()
        wall = time.perf_counter()
        try:
            outcome = _operation(spec)
        except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
            outcome = {
                "status": "REFUSED",
                "error_type": type(exc).__name__,
                "reason": str(exc)[:2048],
            }
        elapsed = time.perf_counter() - wall
        used = time.process_time() - cpu
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        samples.append(
            {
                "outcome": outcome,
                "outcome_sha256": _digest(outcome),
                "wall_seconds": elapsed,
                "cpu_seconds": used,
                "python_peak_bytes": peak,
                "process_maxrss_bytes": rss if sys.platform == "darwin" else rss * 1024,
                "rss_scope": "process lifetime high-water; not per-operation delta",
            }
        )
    root = Path(__file__).resolve().parents[3]
    sources = {}
    for module in tuple(sys.modules.values()):
        file = getattr(module, "__file__", None)
        if file:
            path = Path(file)
            if path.suffix == ".py" and path.is_relative_to(root):
                sources[str(path.relative_to(root))] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
    return {
        "samples": samples,
        "source_digests": sources,
        "provider_tokens": None,
        "energy_joules": None,
    }


def measure(spec, scratch, *, repetitions=3, seconds=30):
    if (
        type(repetitions) is not int
        or not 1 <= repetitions <= 5
        or type(seconds) not in (int, float)
        or not 0 < seconds <= 30
    ):
        raise ValueError("finite profiling repetition/deadline envelope required")
    _spec(spec)
    import journal_storage
    from native_review_observer import _bounded_process

    scratch = Path(scratch)
    if not scratch.is_absolute() or ".." in scratch.parts:
        raise ValueError("profiling needs explicit retained scratch")
    fd = journal_storage._safe_directory(scratch.parent)
    try:
        os.mkdir(scratch.name, 0o700, dir_fd=fd)
        os.fsync(fd)
    finally:
        os.close(fd)
    processes = []
    reports = []
    for index, iterations in enumerate([1] * repetitions + [repetitions]):
        directory = scratch / str(index)
        directory.mkdir(mode=0o700)
        request = {"spec": spec, "iterations": iterations}
        prompt = json.dumps(request, sort_keys=True, separators=(",", ":"))
        (directory / "input.json").write_text(prompt + "\n")
        env = dict(os.environ)
        env.update(PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(directory))
        start = time.monotonic()
        try:
            code, out, err, elapsed = _bounded_process(
                [sys.executable, str(Path(__file__).resolve()), "--probe"],
                prompt,
                directory,
                seconds,
                env,
            )
            (directory / "stdout.log").write_bytes(out)
            (directory / "stderr.log").write_bytes(err)
            disposition = {
                "index": index,
                "returncode": code,
                "seconds": elapsed,
                "terminal": "reaped",
                "owner": "native_review_observer._bounded_process",
                "escaped_descendants": "UNKNOWN",
                "output_sha256": hashlib.sha256(out).hexdigest(),
            }
            processes.append(disposition)
            (directory / "process.json").write_text(
                json.dumps(disposition, indent=2) + "\n"
            )
            if code != 0:
                raise ValueError("local owner probe failed; retained stdout/stderr")
            result = _json(out)
            if (
                set(result)
                != {"samples", "source_digests", "provider_tokens", "energy_joules"}
                or len(result["samples"]) != iterations
            ):
                raise ValueError("local owner probe returned malformed evidence")
            reports.append(result)
        except BaseException as exc:
            if not (directory / "process.json").exists():
                disposition = {
                    "index": index,
                    "seconds": time.monotonic() - start,
                    "status": "INCOMPLETE",
                    "reason": str(exc)[:2048],
                    "output_completeness": "UNKNOWN",
                    "owner": "native_review_observer._bounded_process",
                    "terminal": "owner cleanup attempted",
                }
                (directory / "process.json").write_text(
                    json.dumps(disposition, indent=2) + "\n"
                )
            raise
    samples = [sample for report in reports for sample in report["samples"]]
    equivalent = len({r["outcome_sha256"] for r in samples}) == 1
    same_sources = all(
        r["source_digests"] == reports[0]["source_digests"] for r in reports
    )
    result = {
        "schema_version": 1,
        "owner": spec["owner"],
        "owner_boundary": OWNERS[spec["owner"]],
        "scope": "local deterministic owner; not harness-wide performance",
        "cold_definition": "new interpreter; OS filesystem cache not flushed",
        "warm_definition": "same interpreter; every operation revalidates current authority and bytes",
        "cold_interpreters": reports[:-1],
        "warm_interpreter": reports[-1],
        "processes": processes,
        "outcome_equivalence": "PASS" if equivalent and same_sources else "FAIL",
        "operational_status": samples[0]["outcome"]["status"]
        if equivalent
        else "CHANGED",
        "source_digests": reports[0]["source_digests"],
        "source_observation_scope": "On-disk source for loaded local modules at probe completion; not executable-memory attestation",
        "source_equivalence": "PASS" if same_sources else "FAIL",
        "provider_tokens": None,
        "cached_model_tokens": None,
        "harness_tool_calls": None,
        "energy_joules": None,
        "native_acceptance": "UNKNOWN",
        "authority_granted": False,
    }
    (scratch / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--case", type=Path)
    parser.add_argument("--scratch", type=Path)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--seconds", type=float, default=30)
    args = parser.parse_args(argv)
    if args.probe:
        request = _json(sys.stdin.buffer.read(MAX_INPUT_BYTES + 1))
        if set(request) != {"spec", "iterations"}:
            raise ValueError("invalid fixed probe request")
        result = _probe(request["spec"], request["iterations"])
    else:
        if args.case is None or args.scratch is None:
            raise ValueError("case and retained scratch are required")
        import journal_storage

        result = measure(
            _json(journal_storage.read_regular(args.case, MAX_INPUT_BYTES)),
            args.scratch,
            repetitions=args.repetitions,
            seconds=args.seconds,
        )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "INCOMPLETE", "reason": str(exc)}), file=sys.stderr)
        raise SystemExit(2)
