"""Authenticated, content-bound hosted test evidence; never publication authority.

GitHub owns the run and artifact. The release boundary independently binds the
current clean source and publication state, then performs installation checks.
No caller-supplied success file or diagnostic artifact is accepted here.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import time
import zipfile

REPOSITORY = "synthesisengineering/synthesis-skills"
WORKFLOW = ".github/workflows/validate.yml"
ARTIFACT = "candidate-validation"
MAX_BYTES = 1024 * 1024
RECORD_BYTES = 32768


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def validate_record(record, expected, source, contract, workflow, run_id, attempt):
    fixed = {"schema": 1, "repository": REPOSITORY, "run_id": run_id,
             "run_attempt": attempt, "tree": expected["head_tree"],
             "base": expected["change_base"], "manifest_sha256": expected["manifest_sha256"],
             "source_sha256": source, "contract_sha256": digest(contract),
             "workflow_sha256": workflow, "authorizes_release": False}
    if not isinstance(record, dict) or any(type(record.get(k)) is not type(v) or record.get(k) != v for k, v in fixed.items()):
        raise ValueError("hosted validation does not bind this candidate and contract")
    if record.get("coverage") != {"declared": len(contract), "terminal": len(contract), "not_run": 0}:
        raise ValueError("hosted validation coverage is incomplete")
    if not re.fullmatch(r"[0-9a-f]{64}", str(record.get("execution_sha256", ""))):
        raise ValueError("hosted execution digest is missing")
    return record


class GitHub:
    def __init__(self, repo):
        self.repo = repo
        self.deadline = time.monotonic() + 120

    def api(self, endpoint, *, binary=False):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("hosted verification deadline exhausted")
        result = subprocess.run(["gh", "api", "--hostname", "github.com", endpoint],
                                cwd=self.repo, capture_output=True, timeout=min(30, remaining))
        if result.returncode or len(result.stdout) > MAX_BYTES:
            raise ValueError("authenticated GitHub evidence unavailable or oversized")
        return result.stdout if binary else json.loads(result.stdout)


def archive_record(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if len(members) != 1 or members[0].filename != "candidate-validation.json":
            raise ValueError("hosted artifact membership differs")
        item = members[0]
        if item.file_size > RECORD_BYTES or item.is_dir() or item.flag_bits & 1:
            raise ValueError("hosted artifact member refused")
        return json.loads(archive.read(item))


def distribution(api, candidate_commit):
    prefix = f"repos/{REPOSITORY}/actions"
    listing = api(f"{prefix}/workflows/distribution.yml/runs?head_sha={candidate_commit}&per_page=100")
    runs = [r for r in listing.get("workflow_runs", [])
            if r.get("head_sha") == candidate_commit and r.get("event") in {"push", "pull_request"}]
    if not runs:
        raise ValueError("distribution validation unavailable for this candidate")
    run = max(runs, key=lambda r: r["id"])
    if (run.get("path") != ".github/workflows/distribution.yml"
            or run.get("status") != "completed" or run.get("conclusion") != "success"
            or run.get("repository", {}).get("full_name") != REPOSITORY
            or run.get("head_repository", {}).get("full_name") != REPOSITORY):
        raise ValueError("distribution validation is not successful authoritative evidence")
    attempt = run.get("run_attempt")
    if type(attempt) is not int or attempt < 1:
        raise ValueError("distribution run attempt unavailable")
    jobs = api(f"{prefix}/runs/{run['id']}/attempts/{attempt}/jobs?per_page=100")
    rows = jobs.get("jobs", [])
    required = {f"packages ({os}, {python})" for os in ("ubuntu-latest", "macos-latest")
                for python in ("3.12", "3.13", "3.14")}
    if (jobs.get("total_count") != len(rows) or len(rows) != 7
            or {j.get("name") for j in rows} != required | {"arch-package"}):
        raise ValueError("distribution matrix is incomplete")
    for job in rows:
        conclusion = "skipped" if job["name"] == "arch-package" else "success"
        if job.get("status") != "completed" or job.get("conclusion") != conclusion:
            raise ValueError("required distribution job did not succeed")
    return {"run_id": run["id"], "attempt": attempt}


def verify(api, run_id, expected, source, contract, workflow, candidate_commit):
    prefix = f"repos/{REPOSITORY}"
    run = api(f"{prefix}/actions/runs/{run_id}")
    if (run.get("id") != run_id or run.get("status") != "completed" or run.get("conclusion") != "success"
            or run.get("path") != WORKFLOW or run.get("repository", {}).get("full_name") != REPOSITORY
            or run.get("head_repository", {}).get("full_name") != REPOSITORY
            or run.get("event") not in {"push", "pull_request"}
            or run.get("head_sha") != candidate_commit):
        raise ValueError("hosted run is not successful authoritative candidate validation")
    attempt = run.get("run_attempt")
    if type(attempt) is not int or attempt < 1:
        raise ValueError("hosted run attempt unavailable")
    jobs = api(f"{prefix}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100")
    rows = jobs.get("jobs", [])
    required = {"source-checks", "conformance", "onboarding-portability (ubuntu-latest)", "onboarding-portability (macos-latest)"}
    if (jobs.get("total_count") != len(rows) or len(rows) != len(required)
            or {x.get("name") for x in rows} != required
            or any(x.get("status") != "completed" or x.get("conclusion") != "success" for x in rows)):
        raise ValueError("hosted required jobs are incomplete or unsuccessful")
    for name, step in [("source-checks", "Run the complete source catalog concurrently"),
                       ("conformance", "Consume transaction-bound R5 acceptance"),
                       ("conformance", "Retain candidate validation")]:
        job = next(x for x in rows if x["name"] == name)
        matches = [x for x in job.get("steps", []) if x.get("name") == step]
        if len(matches) != 1 or matches[0].get("conclusion") != "success" or matches[0].get("status") != "completed":
            raise ValueError("hosted required execution step did not complete")
    artifacts = api(f"{prefix}/actions/runs/{run_id}/artifacts?per_page=100")
    values = artifacts.get("artifacts", [])
    if artifacts.get("total_count") != len(values):
        raise ValueError("hosted artifact listing is incomplete")
    matches = [a for a in values if a.get("name") == ARTIFACT]
    if len(matches) != 1:
        raise ValueError("unique candidate validation artifact unavailable")
    artifact = matches[0]
    if (artifact.get("expired") is not False or type(artifact.get("id")) is not int
            or type(artifact.get("size_in_bytes")) is not int or not 0 < artifact["size_in_bytes"] <= MAX_BYTES
            or artifact.get("workflow_run", {}).get("id") != run_id
            or artifact.get("workflow_run", {}).get("head_sha") != candidate_commit):
        raise ValueError("hosted artifact identity or size refused")
    raw = api(f"{prefix}/actions/artifacts/{artifact['id']}/zip", binary=True)
    if len(raw) > MAX_BYTES:
        raise ValueError("hosted artifact exceeds byte limit")
    artifact_digest = artifact.get("digest")
    if artifact_digest is not None and artifact_digest != "sha256:" + hashlib.sha256(raw).hexdigest():
        raise ValueError("hosted artifact digest mismatch")
    record = validate_record(archive_record(raw), expected, source, contract, workflow, run_id, attempt)
    return {"run_id": run_id, "attempt": attempt, "candidate_commit": candidate_commit,
            "distribution": distribution(api, candidate_commit),
            "artifact_id": artifact["id"], "artifact_sha256": hashlib.sha256(raw).hexdigest(),
            "record": record}
