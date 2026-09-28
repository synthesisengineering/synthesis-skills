from pathlib import Path
import copy
import hashlib
import json
import sys
import pytest

S = Path(__file__).resolve().parent
sys.path.insert(0, str(S))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import team_contract as tc  # noqa: E402 - exact sibling source is selected before importing the owner
import team_records as tr  # noqa: E402 - exact sibling source is selected before importing the owner
import contribution_evidence as ce  # noqa: E402 - exact sibling source is selected before importing the owner
import coordination as c  # noqa: E402 - exact sibling source is selected before importing the owner
from test_team_contract import contract  # noqa: E402 - exact sibling source is selected before importing the owner
from test_p13_governance import inventory as declared_inventory  # noqa: E402 - exact sibling source is selected before importing the owner


import test_run_admission as world_fixtures  # noqa: E402 - explicit sibling fixture owner

world = world_fixtures.world


def inventory(project):
    value = declared_inventory()
    home = project / "resources/evidence/contributions"
    home.mkdir(parents=True, exist_ok=True)
    for item in value["items"]:
        for event in item["events"]:
            raw = json.dumps(
                {
                    "issue_id": item["id"],
                    "event": {k: v for k, v in event.items() if k != "sha256"},
                },
                sort_keys=True,
            ).encode()
            sha = hashlib.sha256(raw).hexdigest()
            (home / (sha + ".json")).write_bytes(raw)
            event["sha256"] = sha
    return value


def setup(w):
    d = contract()
    d["governance"]["mirror_owner"] = "p-two"
    d["people"][1]["roles"].append("maintainer")
    d["policy"]["approval_roles"].update(
        {"appoint-role": ["maintainer"], "offboard": ["maintainer"]}
    )
    raw = json.dumps(d, sort_keys=True, indent=2) + "\n"
    f = w["project"] / "team.json"
    f.write_text(raw)
    sha = hashlib.sha256(f.read_bytes()).hexdigest()
    (w["board"].parent / "team.json").write_text(raw)
    rows = c.rows(w["board"].read_text())
    rows[0].person = "p-two"
    old = copy.deepcopy(rows[0])
    identity = c.new_identity([rows[0].identity])
    old = c.with_identity(old, identity)
    old.client_ref = "cc:departed"
    old.person = "p-one"
    old.status = "released"
    old.claims = []
    w["board"].write_text(
        c.replace_table(c.template(), [rows[0], old])
        + "\nTeam-Contract: team.json @ "
        + sha
        + "\n"
    )
    pending = w["scratch"] / "repo-guard/pending"
    pending.mkdir(parents=True)
    return d, f, sha, pending.parent


def test_actual_appointment_uses_native_claimed_record_transaction(world):
    d, f, sha, guard = setup(world)
    proposal = ce.propose_role(
        d,
        inventory(world["project"]),
        person="p-one",
        role="contributor",
        scope=["repo-one"],
        backup="p-two",
        evidence_root=world["project"],
    )
    result = tr.appoint(
        world["project"],
        "team.json",
        expected_digest=sha,
        board=world["board"],
        native_payload=world["actor"]["native_payload"],
        inventory=inventory(world["project"]),
        proposal=proposal,
        approval={
            "person": "p-two",
            "proposal_digest": proposal["digest"],
            "quote": "Approve this synthetic exact appointment.",
        },
        at="2026-09-27T00:00:01Z",
    )
    assert result["record_transaction"]["status"] == "committed"
    out = tc.load(f)
    history = out["governance"]["role_history"]
    assert history[0]["person"] == "p-one" and history[0]["appointed_by"] == "p-two"
    assert history[0]["native_ref"] == world["actor"]["native_payload"][
        "session_id"
    ].join(["cc:", ""])
    assert result["policy_activated"] is False and result["board_rebinding_required"]


@pytest.mark.parametrize("bad", ["approver", "digest", "claim", "source", "work"])
def test_appointment_refuses_forgery_before_record_write(world, bad):
    d, f, sha, g = setup(world)
    original = f.read_bytes()
    inv = inventory(world["project"])
    proposal = ce.propose_role(
        d,
        inv,
        person="p-one",
        role="contributor",
        scope=["repo-one"],
        backup="p-two",
        evidence_root=world["project"],
    )
    approval = {
        "person": "p-two",
        "proposal_digest": proposal["digest"],
        "quote": "Synthetic",
    }
    if bad == "approver":
        approval["person"] = "p-one"
    if bad == "digest":
        approval["proposal_digest"] = "f" * 64
    if bad == "claim":
        world["board"].write_text(
            world["board"]
            .read_text()
            .replace(
                str(world["project"]) + "/**", str(world["project"]) + "/unrelated/**"
            )
        )
    if bad == "source":
        sha = "f" * 64
    if bad == "work":
        inv["items"][1]["accepted"] = False
    with pytest.raises((ValueError, RuntimeError)):
        tr.appoint(
            world["project"],
            "team.json",
            expected_digest=sha,
            board=world["board"],
            native_payload=world["actor"]["native_payload"],
            inventory=inv,
            proposal=proposal,
            approval=approval,
            at="2026-09-27T00:00:01Z",
        )
    assert f.read_bytes() == original


def test_actual_offboarding_retains_attribution_and_foreign_manifests(world):
    d, f, sha, g = setup(world)
    foreign = g / "pending" / (hashlib.sha256(b"foreign-native").hexdigest() + ".json")
    foreign.write_text(
        json.dumps({"session_id": "foreign-native", "paths": ["synthetic"]})
    )
    before = foreign.read_bytes()
    observed = tc.observed_offboarding(
        d, "p-one", board=world["board"], repo_guard_root=g
    )
    request = {
        "person": "p-one",
        "at": "2026-09-27T00:00:01Z",
        "service_successors": {"service-one": ["p-two"]},
        "declaration_sha256": sha,
        "observed": observed,
    }
    result = tr.offboard(
        world["project"],
        "team.json",
        expected_digest=sha,
        board=world["board"],
        native_payload=world["actor"]["native_payload"],
        repo_guard_root=g,
        approval={
            "person": "p-two",
            "proposal_digest": ce.digest(request),
            "quote": "Retire the synthetic principal; retain custody.",
        },
        **{k: request[k] for k in ("person", "at", "service_successors")},
    )
    assert result["record_transaction"]["status"] == "committed"
    assert tc.load(f)["people"][0]["status"] == "retired"
    assert foreign.read_bytes() == before
    assert (
        result["host_revocation"] == "UNVERIFIED_EXTERNAL"
        and not result["claims_released"]
        and not result["data_deleted"]
    )


def test_actual_effect_manifest_blocks_departure_without_touching_claims(world):
    d, f, sha, g = setup(world)
    pending = g / "pending" / (hashlib.sha256(b"departed").hexdigest() + ".json")
    pending.write_text(json.dumps({"session_id": "departed", "paths": ["retained"]}))
    before = f.read_bytes()
    obs = tc.observed_offboarding(d, "p-one", board=world["board"], repo_guard_root=g)
    assert not obs["managed_ready"]
    assert obs["blockers"][0]["reason"] == "outstanding attributed effects"
    assert f.read_bytes() == before and pending.exists()
