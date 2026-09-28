from pathlib import Path
import json
import sys
import pytest

S = Path(__file__).resolve().parent
sys.path.insert(0, str(S))
import team_contract as tc  # noqa: E402 - exact sibling source is selected before importing the owner
from test_team_contract import contract  # noqa: E402 - exact sibling source is selected before importing the owner


def inventory():
    return {
        "schema": 1,
        "repository": "https://git.example/org-one/notes.git",
        "observed_at": "2026-09-27T00:00:00Z",
        "coverage": {"complete": True, "total": 3, "next_cursor": None},
        "items": [
            {
                "id": "issue-1",
                "author": "p-one",
                "created_at": "2026-09-26T00:00:00Z",
                "status": "open",
                "lane": "safety-fixtures",
                "audience": "engineer",
                "runtime": "codex",
                "evidence_plane": "source",
                "reproduction": "missing",
                "accepted": False,
                "events": [
                    {
                        "id": "event-1",
                        "actor": "p-two",
                        "kind": "response",
                        "at": "2026-09-26T01:00:00Z",
                        "sha256": "a" * 64,
                    }
                ],
            },
            {
                "id": "issue-2",
                "author": "p-one",
                "created_at": "2026-09-26T00:00:00Z",
                "status": "closed",
                "lane": "methodology",
                "audience": "engineer",
                "runtime": "codex",
                "evidence_plane": "source",
                "reproduction": "verified",
                "accepted": True,
                "events": [
                    {
                        "id": "event-2",
                        "actor": "p-two",
                        "kind": "accepted",
                        "at": "2026-09-26T03:00:00Z",
                        "sha256": "b" * 64,
                    }
                ],
            },
            {
                "id": "issue-3",
                "author": "p-one",
                "created_at": "2026-09-26T00:00:00Z",
                "status": "open",
                "lane": "documentation",
                "audience": "writer",
                "runtime": "claude",
                "evidence_plane": "source",
                "reproduction": "not-applicable",
                "accepted": False,
                "events": [],
            },
        ],
    }


def test_complete_queue_censors_unanswered_without_false_median():
    import contribution_evidence as ce

    d = contract()
    d["people"][1]["roles"].append("maintainer")
    r = ce.report(inventory(), d)
    assert (
        r["first_response"]["answered"] == 2 and r["first_response"]["unanswered"] == 1
    )
    assert r["first_response"]["median_seconds_answered_only"] == 7200
    assert r["queue"][0]["reproduction"] == "missing" and r["production_slo"] is None


@pytest.mark.parametrize(
    "bad", ["total", "cursor", "future", "duplicate", "acceptance"]
)
def test_unknown_incomplete_or_fabricated_acceptance_refuses(bad):
    import contribution_evidence as ce

    x = inventory()
    d = contract()
    d["people"][1]["roles"].append("maintainer")
    if bad == "total":
        x["coverage"]["total"] = 4
    if bad == "cursor":
        x["coverage"]["next_cursor"] = "more"
    if bad == "future":
        x["items"][0]["events"][0]["at"] = "2027-01-01T00:00:00Z"
    if bad == "duplicate":
        x["items"][1]["id"] = x["items"][0]["id"]
    if bad == "acceptance":
        x["items"][1]["events"] = []
    with pytest.raises(ValueError):
        ce.report(x, d)


def test_role_proposal_does_not_appoint_and_needs_accepted_work():
    import contribution_evidence as ce

    d = contract()
    d["people"][1]["roles"].append("maintainer")
    before = json.dumps(d, sort_keys=True)
    proposal = ce.propose_role(
        d,
        inventory(),
        person="p-one",
        role="contributor",
        scope=["repo-one"],
        backup="p-two",
    )
    assert proposal["status"] == "PROPOSED" and json.dumps(d, sort_keys=True) == before
    assert proposal["accepted_work"] == ["issue-2"]
    with pytest.raises(ValueError):
        ce.propose_role(
            d,
            inventory(),
            person="p-one",
            role="runtime-steward",
            scope=["codex"],
            backup="p-two",
        )


def test_offboarding_refuses_orphaned_service_custody():
    d = contract()
    d["governance"]["mirror_owner"] = "p-two"
    with pytest.raises(ValueError):
        tc.retire_principal(
            d,
            "p-one",
            at="2026-09-27T00:00:00Z",
            expected_revision=1,
            service_successors={},
        )
    out = tc.retire_principal(
        d,
        "p-one",
        at="2026-09-27T00:00:00Z",
        expected_revision=1,
        service_successors={"service-one": ["p-two"]},
    )
    assert (
        out["people"][0]["status"] == "retired" and d["people"][0]["status"] == "active"
    )
    assert out["seats"][0]["occupancies"][0]["person"] == "p-one"
    assert out["seats"][0]["occupancies"][0]["closed"]
    with pytest.raises(ValueError):
        tc.entitlement_plan(out, "p-one", requested=[])
