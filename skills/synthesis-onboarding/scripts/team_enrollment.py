"""Select declared organization assets before existing enrollment owners act.

The desired-state organization entry owns principal_selection. It is machine
configuration, not a shared roster edit, account grant or authentication receipt.
"""

from __future__ import annotations
import copy
import importlib.util
from pathlib import Path
import re


def _contract_owner():
    path = (
        Path(__file__).resolve().parents[2]
        / "synthesis-project-management/scripts/team_contract.py"
    )
    spec = importlib.util.spec_from_file_location("_onboarding_team_contract", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def select_manifest(manifest, selection):
    declared = manifest.get("team_contract")
    if declared is None:
        if selection is not None:
            raise ValueError(
                "principal selection requires the organization team contract"
            )
        return copy.deepcopy(manifest)
    if not isinstance(declared, dict) or set(declared) != {"path", "sha256"}:
        raise ValueError("team_contract requires an exact relative path and digest")
    path = declared["path"]
    if not isinstance(path, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.json", path
    ):
        raise ValueError(
            "team contract must be a named JSON file beside the tracked manifest"
        )
    if not isinstance(selection, dict) or set(selection) != {
        "person",
        "requested",
        "team_digest",
    }:
        raise ValueError(
            "team enrollment needs persisted principal_selection in desired organization state"
        )
    if selection["team_digest"] != declared["sha256"]:
        raise ValueError(
            "team contract changed; review and explicitly renew the principal selection"
        )
    owner = _contract_owner()
    document = owner.load(
        Path(manifest["_path"]).parent / path, expected_digest=declared["sha256"]
    )
    if (
        document["organization"] != manifest["org"]["id"]
        or document["deletion_unit"] != manifest["org"]["workspace"]
    ):
        raise ValueError(
            "team contract organization or deletion unit differs from enrollment target"
        )
    plan = owner.entitlement_plan(
        document, selection["person"], requested=selection["requested"]
    )
    declared_ids = {entry["id"]: entry["kind"] for entry in document["entitlements"]}
    observed = set()
    result = copy.deepcopy(manifest)
    for key, kind in (
        ("skills_repos", "skills"),
        ("knowledge_bases", "knowledge-base"),
    ):
        result[key] = []
        for entry in manifest.get(key) or []:
            eid = entry.get("entitlement")
            if (
                not isinstance(eid, str)
                or eid in observed
                or declared_ids.get(eid) != kind
            ):
                raise ValueError(
                    "every team asset must bind one unique entitlement of the matching kind"
                )
            observed.add(eid)
            if kind == "knowledge-base":
                from organization import canonical_remote

                entitlement = next(
                    e for e in document["entitlements"] if e["id"] == eid
                )
                repository = next(
                    r
                    for r in document["repositories"]
                    if r["id"] == entitlement["repository"]
                )
                if canonical_remote(entry["repository"]) != canonical_remote(
                    repository["remote"]
                ):
                    raise ValueError(
                        "knowledge asset remote differs from its declared audience-bound repository"
                    )
            if eid in plan["selected"]:
                result[key].append(copy.deepcopy(entry))
    if observed != set(declared_ids):
        raise ValueError(
            "team entitlement inventory and organization asset inventory differ"
        )
    result["_team_selection"] = {**copy.deepcopy(selection), **plan}
    # No cached roster may authorize effects after a changed declaration.
    owner.load(
        Path(manifest["_path"]).parent / path, expected_digest=declared["sha256"]
    )
    return result
