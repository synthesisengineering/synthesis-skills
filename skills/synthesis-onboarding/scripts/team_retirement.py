"""Archive exact principal-owned derived copies through the enrollment owner.

Repository data, accounts, tokens, ACLs, unrelated copies and departed identity
records are never removed. Unknown historical ownership refuses new custody.
"""

from __future__ import annotations
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import onboard
from enrollment import engine_lock, recover_copy_transactions
from system_contract import ContractError

PM = Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"
if str(PM) not in sys.path:
    sys.path.insert(0, str(PM))
import team_contract as tc  # noqa: E402 - exact sibling source is selected before importing the owner


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _inputs(state, manifest_path, selection):
    if (
        Path(onboard.HOME).absolute() != Path(state.home).absolute()
        or Path(onboard.STATE_DIR).absolute() != Path(state.state_dir).absolute()
    ):
        raise ContractError(
            "retirement must use the current existing enrollment owner roots"
        )
    manifest = onboard.load_manifest(Path(manifest_path))
    source = manifest.get("team_contract")
    tc._object(source, {"path", "sha256"}, label="team source")
    tc._object(
        selection, {"person", "requested", "team_digest"}, label="principal selection"
    )
    if (
        selection["team_digest"] != source["sha256"]
        or Path(source["path"]).name != source["path"]
    ):
        raise ContractError("retirement requires exact reviewed team declaration")
    document = tc.load(
        Path(manifest["_path"]).parent / source["path"],
        expected_digest=source["sha256"],
    )
    if (
        document["organization"] != manifest["org"]["id"]
        or document["deletion_unit"] != manifest["org"]["workspace"]
    ):
        raise ContractError("retirement organization/deletion-unit differs")
    person = next(
        (p for p in document["people"] if p["id"] == selection["person"]), None
    )
    departures = [
        d
        for d in document["governance"].get("departures", [])
        if d["person"] == selection["person"]
    ]
    if not person or person["status"] != "retired" or not departures:
        raise ContractError("retirement needs an approved departed principal record")
    receipts = onboard.Receipts(state.state_dir / "receipts.json")
    scope = {
        "organization": document["organization"],
        "deletion_unit": document["deletion_unit"],
        "principal": selection["person"],
    }
    selected = {}
    foreign = 0
    copies = receipts.data.get("org_skill_copies", {})
    if not isinstance(copies, dict) or len(copies) > 512:
        raise ContractError("bounded owned-copy inventory required")
    for name, record in copies.items():
        if not isinstance(record, dict):
            raise ContractError("copy ownership record malformed")
        if (
            record.get("organization") == scope["organization"]
            and record.get("deletion_unit") == scope["deletion_unit"]
            and "principal" not in record
        ):
            raise ContractError(
                "historical copy has unknown principal custody; preserve for owner-led recovery"
            )
        if onboard.organization_copy_matches(record, scope):
            onboard.verify_org_copy(Path(name), record)
            selected[name] = copy.deepcopy(record)
        else:
            foreign += 1
    result = copy.deepcopy(manifest)
    result["skills_repos"] = []
    result["_team_selection"] = copy.deepcopy(selection)
    return result, document, receipts, selected, foreign


def plan(state, manifest, selection, *, at=None):
    _m, d, receipts, selected, foreign = _inputs(state, manifest, selection)
    now = datetime.now(timezone.utc) if at is None else tc._time(at)
    value = {
        "schema": 1,
        "operation": "principal-copy-retirement",
        "manifest": str(Path(manifest).absolute()),
        "manifest_sha256": hashlib.sha256(tc.read_source(manifest)).hexdigest(),
        "selection": copy.deepcopy(selection),
        "organization": d["organization"],
        "deletion_unit": d["deletion_unit"],
        "home": str(state.home),
        "state_dir": str(state.state_dir),
        "receipts_sha256": digest(receipts.data),
        "copies": selected,
        "foreign_copies_preserved": foreign,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=15)).isoformat(),
        "host_revocation": "UNVERIFIED_EXTERNAL",
        "repository_data_deleted": False,
        "archive_only": True,
    }
    return value | {"digest": digest(value)}


def apply(state, proposal, *, approval_digest, dry_run=False):
    if (
        not isinstance(proposal, dict)
        or proposal.get("digest") != approval_digest
        or digest({k: v for k, v in proposal.items() if k != "digest"})
        != approval_digest
    ):
        raise ContractError("exact reviewed retirement plan approval required")

    def fresh():
        if (
            not tc._time(proposal["created_at"])
            <= datetime.now(timezone.utc)
            <= tc._time(proposal["expires_at"])
        ):
            raise ContractError("retirement plan is expired or future-dated")

    fresh()
    with engine_lock(state.state_dir, read_only=dry_run):
        recover_copy_transactions(state.state_dir, state.home, verify_only=True)
        current = plan(
            state,
            proposal["manifest"],
            proposal["selection"],
            at=proposal["created_at"],
        )
        if current != proposal:
            raise ContractError("retirement inputs changed since exact preview")
        manifest, _d, receipts, _selected, _foreign = _inputs(
            state, proposal["manifest"], proposal["selection"]
        )
        fresh()
        report = onboard.Report(dry_run=dry_run, as_json=True)
        onboard.phase_org_skills(report, manifest, receipts, dry_run)
        if report.exit_code():
            raise ContractError(
                "existing copy owner refused retirement; custody retained: "
                + json.dumps(report.steps)
            )
        return {
            "status": "dry-run" if dry_run else "archived",
            "steps": report.steps,
            "digest": approval_digest,
            "copies": len(proposal["copies"]),
            "host_revocation": "UNVERIFIED_EXTERNAL",
            "repository_data_deleted": False,
            "foreign_copies_preserved": proposal["foreign_copies_preserved"],
        }
