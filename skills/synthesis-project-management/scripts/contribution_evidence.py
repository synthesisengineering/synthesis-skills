#!/usr/bin/env python3
"""Governance's bounded issue inventory, censored response report and role proposals.

Imports are local public owners. Source documents remain in existing project
records; this module creates no issue store, remote labels or appointments.
"""

from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import statistics
import team_contract as tc

LANES = frozenset(
    {
        "documentation",
        "methodology",
        "safety-fixtures",
        "runtime-adapters",
        "onboarding-accessibility",
        "compatibility",
        "translations",
        "research",
    }
)
PLANES = frozenset({"source", "installed", "live", "continuity", "capability"})
ROLES = ("contributor", "repeat-contributor", "runtime-steward", "maintainer")


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def report(inventory, declaration, *, evidence_root=None):
    d = tc.validate(declaration)
    tc._object(
        inventory,
        {"schema", "repository", "observed_at", "coverage", "items"},
        label="issue inventory",
    )
    if inventory["schema"] != 1 or type(inventory["schema"]) is not int:
        raise ValueError("unsupported issue inventory")
    from urllib.parse import urlsplit

    remote = urlsplit(inventory["repository"])
    if (
        remote.scheme != "https"
        or not remote.hostname
        or remote.username
        or remote.password
        or remote.query
        or remote.fragment
    ):
        raise ValueError(
            "issue repository must be an explicit credential-free HTTPS source"
        )
    repositories = [
        r for r in d["repositories"] if r["remote"] == inventory["repository"]
    ]
    if len(repositories) != 1:
        raise ValueError("issue inventory must bind one exact declared repository")
    repository_id = repositories[0]["id"]
    end = tc._time(inventory["observed_at"])
    coverage = tc._object(
        inventory["coverage"], {"complete", "total", "next_cursor"}, label="coverage"
    )
    items = tc._entries(inventory["items"], "issue items")
    if (
        coverage["complete"] is not True
        or type(coverage["total"]) is not int
        or coverage["total"] != len(items)
        or coverage["next_cursor"] is not None
    ):
        raise ValueError("incomplete issue inventory: coverage remains UNKNOWN")
    people = {p["id"]: p for p in d["people"]}
    maintainers = {
        p["id"]
        for p in d["people"]
        if p["kind"] == "human"
        and p["status"] == "active"
        and "maintainer" in tc.effective_roles(d, p["id"], scope=repository_id)
    }
    queue, answered, censored, accepted = [], [], [], []
    all_events = set()
    for item in items:
        tc._object(
            item,
            {
                "id",
                "author",
                "created_at",
                "status",
                "lane",
                "audience",
                "runtime",
                "evidence_plane",
                "reproduction",
                "accepted",
                "events",
            },
            label="issue",
        )
        if (
            item["author"] not in people
            or item["lane"] not in LANES
            or item["evidence_plane"] not in PLANES
        ):
            raise ValueError("unknown issue author, lane or evidence plane")
        tc._id(item["audience"])
        tc._id(item["runtime"])
        if (
            item["status"] not in {"open", "closed"}
            or item["reproduction"]
            not in {"missing", "unresolved", "verified", "not-applicable"}
            or type(item["accepted"]) is not bool
        ):
            raise ValueError("invalid issue disposition")
        start = tc._time(item["created_at"])
        if start > end:
            raise ValueError("issue begins after observed coverage")
        responses, acceptances = [], []
        for event in tc._entries(item["events"], "issue events"):
            tc._object(
                event, {"id", "actor", "kind", "at", "sha256"}, label="issue event"
            )
            at = tc._time(event["at"])
            if (
                event["id"] in all_events
                or event["actor"] not in people
                or event["kind"] not in {"response", "accepted", "reopened"}
                or not tc.HEX.fullmatch(str(event["sha256"]))
                or not start <= at <= end
            ):
                raise ValueError("duplicate, future or unsupported issue event")
            all_events.add(event["id"])
            if len(all_events) > tc.MAX_ITEMS:
                raise ValueError("aggregate event inventory exceeds bound")
            if event["actor"] in maintainers and event["actor"] != item["author"]:
                if event["kind"] in {"response", "accepted"}:
                    responses.append(at)
                if event["kind"] == "accepted":
                    acceptances.append(at)
        if item["accepted"]:
            if (
                not acceptances
                or item["status"] != "closed"
                or item["reproduction"] not in {"verified", "not-applicable"}
            ):
                raise ValueError(
                    "accepted work lacks resolved reproduction and maintainer acceptance"
                )
            last_reopen = max(
                (tc._time(e["at"]) for e in item["events"] if e["kind"] == "reopened"),
                default=start,
            )
            if max(acceptances) < last_reopen:
                raise ValueError("reopened work cannot remain accepted")
            accepted.append(copy.deepcopy(item))
        first = (min(responses) - start).total_seconds() if responses else None
        age = (end - start).total_seconds()
        if first is None:
            censored.append({"id": item["id"], "minimum_wait_seconds": age})
        else:
            answered.append(first)
        queue.append(
            {
                k: item[k]
                for k in (
                    "id",
                    "status",
                    "lane",
                    "audience",
                    "runtime",
                    "evidence_plane",
                    "reproduction",
                    "accepted",
                )
            }
            | {
                "age_seconds": age,
                "first_response_seconds": first,
                "labels": [
                    "lane:" + item["lane"],
                    "audience:" + item["audience"],
                    "runtime:" + item["runtime"],
                    "evidence:" + item["evidence_plane"],
                ]
                + (
                    ["needs-reproduction"]
                    if item["reproduction"] in {"missing", "unresolved"}
                    else []
                ),
            }
        )
    source_evidence = (
        verify_sources(inventory, evidence_root) if evidence_root is not None else None
    )
    return {
        "schema": 1,
        "repository_id": repository_id,
        "source_evidence": source_evidence,
        "source_authentication": "OPERATOR_CAPTURE_ATTESTATION_NOT_REMOTE_AUTHENTICATION",
        "inventory_sha256": digest(inventory),
        "declaration_sha256": digest(d),
        "coverage": "COMPLETE_DECLARED_INVENTORY",
        "remote_coverage_verified": False,
        "queue": sorted(queue, key=lambda x: (-x["age_seconds"], x["id"])),
        "first_response": {
            "answered": len(answered),
            "unanswered": len(censored),
            "median_seconds_answered_only": statistics.median(answered)
            if answered
            else None,
            "right_censored": censored,
        },
        "accepted_work": accepted,
        "production_slo": None,
        "remote_mutations": False,
    }


def verify_sources(inventory, project):
    """Verify exact retained captured event bodies, without inventing host auth.

    Existing project evidence owns these files. Hashes alone, remote-looking IDs
    or a role proposal do not count as retained accepted-work evidence.
    """
    root = Path(project).absolute() / "resources/evidence/contributions"
    records, total = {}, 0
    for item in inventory["items"]:
        for event in item["events"]:
            sha = event["sha256"]
            if not tc.HEX.fullmatch(str(sha)):
                raise ValueError("event evidence digest invalid")
            raw = tc.read_source(root / (sha + ".json"), expected_digest=sha)
            total += len(raw)
            if total > 8 * 1024 * 1024 or len(records) >= 512:
                raise ValueError("captured event evidence exceeds aggregate bound")
            expected = {
                "issue_id": item["id"],
                "event": {k: v for k, v in event.items() if k != "sha256"},
            }
            if json.loads(raw, object_pairs_hook=tc._unique) != expected:
                raise ValueError(
                    "captured event evidence differs from claimed acceptance"
                )
            records[sha] = len(raw)
    for sha in records:
        tc.read_source(root / (sha + ".json"), expected_digest=sha)
    return {
        "root": "resources/evidence/contributions",
        "files": records,
        "bytes": total,
    }


def propose_role(
    declaration,
    inventory,
    *,
    person,
    role,
    scope,
    backup,
    evidence_root=None,
    replaces=None,
):
    d = tc.validate(declaration)
    p = tc._principal(d, person)
    b = tc._principal(d, backup)
    if (
        p["kind"] != "human"
        or b["kind"] != "human"
        or person == backup
        or role not in ROLES
    ):
        raise ValueError(
            "role needs a distinct active human backup and supported level"
        )
    scope = tc._ids(scope, "role scope")
    if not scope:
        raise ValueError("explicit role scope required")
    current = d["governance"].get("role_history", [])
    if replaces is not None:
        prior = next((r for r in current if r["id"] == replaces), None)
        if (
            not prior
            or prior["closed"] is not None
            or prior["role"] != role
            or set(prior["scope"]) != set(scope)
        ):
            raise ValueError("succession requires the exact current scoped appointment")
    if any(
        r["person"] == person
        and r["role"] == role
        and r["closed"] is None
        and set(r["scope"]) == set(scope)
        and r["id"] != replaces
        for r in current
    ):
        raise ValueError(
            "current appointment must be explicitly selected for replacement"
        )
    reviewed = report(inventory, d, evidence_root=evidence_root)
    works = [item for item in reviewed["accepted_work"] if item["author"] == person]
    minimum = {
        "contributor": 1,
        "repeat-contributor": 3,
        "runtime-steward": 3,
        "maintainer": 3,
    }[role]
    if len(works) < minimum:
        raise ValueError("accepted work does not meet declared governance threshold")
    if role == "runtime-steward":
        if any(
            not any(
                x["runtime"] == surface
                and x["evidence_plane"] == "live"
                and x["lane"] in {"runtime-adapters", "compatibility"}
                for x in works
            )
            for surface in scope
        ):
            raise ValueError(
                "runtime stewardship requires accepted live evidence for every named surface"
            )
    elif not set(scope) <= {r["id"] for r in d["repositories"]}:
        raise ValueError("role scope is not a declared repository")
    if role != "runtime-steward" and scope != [reviewed["repository_id"]]:
        raise ValueError("accepted work does not establish other repository scope")
    if role == "maintainer" and len({x["lane"] for x in works}) < 2:
        raise ValueError("maintainer evidence must span contribution lanes")
    result = {
        "schema": 1,
        "status": "PROPOSED",
        "person": person,
        "role": role,
        "scope": scope,
        "backup": backup,
        "replaces": replaces,
        "expected_revision": d["revision"],
        "declaration_sha256": digest(d),
        "source_evidence": reviewed["source_evidence"],
        "inventory_sha256": digest(inventory),
        "accepted_work": sorted(x["id"] for x in works),
    }
    return result | {"digest": digest(result)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--team", required=True, type=Path)
    parser.add_argument("--team-digest", required=True)
    parser.add_argument("--evidence-project", type=Path)
    a = parser.parse_args(argv)
    try:
        inv = tc.load_document(a.inventory)
        d = tc.load(a.team, expected_digest=a.team_digest)
        result = report(inv, d, evidence_root=a.evidence_project)
        if (
            tc.load_document(a.inventory) != inv
            or tc.load(a.team, expected_digest=a.team_digest) != d
        ):
            raise ValueError("source changed while reporting")
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "UNKNOWN", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
