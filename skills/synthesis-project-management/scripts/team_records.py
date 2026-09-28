#!/usr/bin/env python3
"""Publish exact team record proposals through the existing record transaction.

No new approval database, credential manager, claim owner or deletion engine.
Human approval is an explicit agent attestation, as at other existing action
owners; neither a declaration nor this API authenticates a human account.
"""

from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import team_contract as tc
import contribution_evidence as ce


def _owner():
    path = Path(__file__).resolve().parents[2] / "synthesis-context-lifecycle/scripts"
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    import record_transaction

    return record_transaction


def _inputs(project, relative, expected_digest, board, native_payload):
    if (
        not isinstance(relative, str)
        or Path(relative).is_absolute()
        or ".." in Path(relative).parts
    ):
        raise ValueError(
            "team record must be a confined existing project-relative source"
        )
    target = Path(project).absolute() / relative
    raw = tc.read_source(target, expected_digest=expected_digest)
    d = tc.load(target, expected_digest=expected_digest)
    actor = tc.board_principal(board, native_payload=native_payload)
    import run_admission

    actor["claim_hash"] = run_admission.native_binding(
        Path(board), native_payload, readonly=True
    )["claim_hash"]
    if actor["sha256"] != expected_digest:
        raise ValueError("native board and edited team declaration differ")
    return target, raw, d, actor


def _approval(d, actor, action, digest, approval, scope=None):
    tc._object(
        approval,
        {"person", "proposal_digest", "quote"},
        label="explicit approval attestation",
    )
    if (
        approval["person"] != actor["person"]
        or approval["proposal_digest"] != digest
        or not isinstance(approval["quote"], str)
        or not 1 <= len(approval["quote"].strip()) <= 4096
    ):
        raise ValueError("approval is not exact current principal and proposal")
    p = tc._principal(d, actor["person"])
    allowed = d["policy"]["approval_roles"].get(action, [])
    roles = (
        [tc.effective_roles(d, actor["person"], scope=value) for value in scope]
        if scope
        else [p["roles"]]
    )
    if (
        p["kind"] != "human"
        or not roles
        or any(not set(value).intersection(allowed) for value in roles)
    ):
        raise ValueError("current appointing/offboarding role has no authority")


def _write(
    project,
    relative,
    raw,
    out,
    board,
    payload,
    digest,
    dry_run,
    claim_hash,
    sources=None,
):
    return _owner().apply(
        Path(project),
        [
            {
                "file": relative,
                "expected_sha256": digest,
                "edits": [
                    {
                        "op": "replace",
                        "anchor": raw.decode("utf-8"),
                        "replacement": json.dumps(out, sort_keys=True, indent=2) + "\n",
                    }
                ],
            }
        ],
        board=Path(board),
        native_payload=payload,
        dry_run=dry_run,
        expected_claim_hash=claim_hash,
        source_custody=sources,
    )


def appoint(
    project,
    relative,
    *,
    expected_digest,
    board,
    native_payload,
    inventory,
    proposal,
    approval,
    at,
    dry_run=False,
):
    target, raw, d, actor = _inputs(
        project, relative, expected_digest, board, native_payload
    )
    tc._object(
        proposal,
        {
            "schema",
            "status",
            "person",
            "role",
            "scope",
            "backup",
            "replaces",
            "expected_revision",
            "declaration_sha256",
            "inventory_sha256",
            "source_evidence",
            "accepted_work",
            "digest",
        },
        label="role proposal",
    )
    current = ce.propose_role(
        d,
        inventory,
        person=proposal["person"],
        role=proposal["role"],
        scope=proposal["scope"],
        backup=proposal["backup"],
        evidence_root=project,
        replaces=proposal["replaces"],
    )
    if current != proposal:
        raise ValueError("role proposal or accepted source changed")
    _approval(d, actor, "appoint-role", proposal["digest"], approval, proposal["scope"])
    moment = tc._time(at)
    if moment < tc._time(inventory["observed_at"]):
        raise ValueError("appointment predates accepted evidence")
    out = copy.deepcopy(d)
    history = out["governance"].setdefault("role_history", [])
    # A replacement closes only the exact same scoped office; unrelated scope
    # and departed attributions remain intact. No legacy role is synthesized.
    for old in history:
        if old["id"] == proposal["replaces"]:
            if moment <= tc._time(old["opened"]):
                raise ValueError("appointment is not after current occupancy")
            old["closed"] = at
    history.append(
        {
            "id": "appointment-" + proposal["digest"][:32],
            "person": proposal["person"],
            "role": proposal["role"],
            "scope": proposal["scope"],
            "backup": proposal["backup"],
            "opened": at,
            "closed": None,
            "accepted_work": proposal["accepted_work"],
            "inventory_sha256": proposal["inventory_sha256"],
            "appointed_by": actor["person"],
            "approval_digest": proposal["digest"],
            "native_ref": actor["native_ref"],
            "replaces": proposal["replaces"],
        }
    )
    out["revision"] += 1
    tc.validate(out)
    tc.read_source(target, expected_digest=expected_digest)
    sources = []
    for sha in proposal["source_evidence"]["files"]:
        name = "resources/evidence/contributions/" + sha + ".json"
        captured, meta = _owner()._snapshot(Path(project) / name)
        if hashlib.sha256(captured).hexdigest() != sha:
            raise ValueError("accepted source changed before custody")
        sources.append({"file": name, "expected": meta})
    result = _write(
        project,
        relative,
        raw,
        out,
        board,
        native_payload,
        expected_digest,
        dry_run,
        actor["claim_hash"],
        sources,
    )
    return {
        "record_transaction": result,
        "new_declaration_sha256": hashlib.sha256(
            (json.dumps(out, sort_keys=True, indent=2) + "\n").encode()
        ).hexdigest(),
        "board_rebinding_required": True,
        "host_appointment_verified": False,
        "policy_activated": False,
    }


def offboard(
    project,
    relative,
    *,
    expected_digest,
    board,
    native_payload,
    person,
    at,
    service_successors,
    repo_guard_root,
    approval,
    dry_run=False,
):
    target, raw, d, actor = _inputs(
        project, relative, expected_digest, board, native_payload
    )
    observed = tc.observed_offboarding(
        d, person, board=board, repo_guard_root=repo_guard_root
    )
    request = {
        "person": person,
        "at": at,
        "service_successors": service_successors,
        "declaration_sha256": expected_digest,
        "observed": observed,
    }
    _approval(d, actor, "offboard", ce.digest(request), approval)
    if not observed["managed_ready"]:
        raise ValueError(
            "outstanding claims or effects require their exact owners; none released"
        )
    out = tc.retire_principal(
        d,
        person,
        at=at,
        expected_revision=d["revision"],
        service_successors=service_successors,
    )
    if (
        tc.observed_offboarding(d, person, board=board, repo_guard_root=repo_guard_root)
        != observed
    ):
        raise ValueError("offboarding custody changed before commit")
    out["governance"].setdefault("departures", []).append(
        {
            "id": "departure-" + ce.digest(request)[:32],
            "person": person,
            "at": at,
            "approved_by": actor["person"],
            "approval_digest": ce.digest(request),
            "native_ref": actor["native_ref"],
            "observation_digest": ce.digest(observed),
        }
    )
    tc.validate(out)
    tc.read_source(target, expected_digest=expected_digest)
    result = _write(
        project,
        relative,
        raw,
        out,
        board,
        native_payload,
        expected_digest,
        dry_run,
        actor["claim_hash"],
    )
    return {
        "record_transaction": result,
        "managed_principal": "retired-in-new-declaration",
        "host_revocation": "UNVERIFIED_EXTERNAL",
        "board_rebinding_required": True,
        "claims_released": False,
        "data_deleted": False,
        "retained_deletion_unit": d["deletion_unit"],
    }


def dispatch(operation, request):
    if not isinstance(request, dict):
        raise ValueError("bounded object request required")
    if operation == "appoint":
        return appoint(**request)
    if operation == "offboard":
        return offboard(**request)
    if operation in {"contributions", "propose-role", "observe-offboarding"}:
        request = dict(request)
        path = request.pop("team")
        sha = request.pop("team_digest")
        document = tc.load(path, expected_digest=sha)
        if operation == "observe-offboarding":
            result = tc.observed_offboarding(document, **request)
        else:
            inventory_path = request.pop("inventory")
            inventory = tc.load_document(inventory_path)
            if operation == "contributions":
                result = ce.report(inventory, document, **request)
            else:
                result = ce.propose_role(document, inventory, **request)
            if tc.load_document(inventory_path) != inventory:
                raise ValueError("inventory changed during operation")
        tc.load(path, expected_digest=sha)
        return result
    raise ValueError("unknown managed team operation")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "operation",
        choices=[
            "contributions",
            "propose-role",
            "observe-offboarding",
            "appoint",
            "offboard",
        ],
    )
    p.add_argument("--request", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        request = tc.load_document(a.request)
        result = dispatch(a.operation, request)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError, TypeError) as exc:
        print(json.dumps({"status": "REFUSED", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
