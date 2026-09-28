from pathlib import Path
import sys
import json
import copy
import hashlib
import pytest

ROOT = Path(__file__).resolve().parents[3]
PM = ROOT / "skills/synthesis-project-management/scripts"
ON = ROOT / "skills/synthesis-onboarding/scripts"
sys.path[:0] = [str(ON), str(PM)]
import team_enrollment as te  # noqa: E402 - source-bound import follows path/bootstrap initialization
from test_team_contract import contract  # noqa: E402 - source-bound import follows path/bootstrap initialization


def package(tmp_path):
    d = contract()
    d["repositories"][0]["remote"] = "https://git.example/org/notes"
    d["entitlements"] = [
        {
            "id": "notes",
            "kind": "knowledge-base",
            "required": True,
            "roles": [],
            "repository": "repo-one",
        },
        {"id": "design", "kind": "skills", "required": False, "roles": ["editor"]},
    ]
    p = tmp_path / "team.json"
    p.write_text(json.dumps(d))
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    m = {
        "version": 2,
        "org": {"id": "org-one", "name": "Synthetic", "workspace": "unit-one"},
        "team_contract": {"path": "team.json", "sha256": digest},
        "ecosystem": {},
        "skills_repos": [
            {
                "name": "design",
                "repository": "https://git.example/org/design",
                "capability": "skills-install",
                "entitlement": "design",
            }
        ],
        "knowledge_bases": [
            {
                "name": "notes",
                "repository": "https://git.example/org/notes",
                "entitlement": "notes",
            }
        ],
        "instruction_sources": [{"path": "rules.md"}],
        "_path": str(tmp_path / "manifest.yaml"),
    }
    s = {"person": "p-one", "requested": [], "team_digest": digest}
    return m, s, p


def test_role_plan_filters_actual_install_manifest(tmp_path):
    m, s, _ = package(tmp_path)
    out = te.select_manifest(m, s)
    assert (
        out["skills_repos"] == []
        and len(out["knowledge_bases"]) == 1
        and len(m["skills_repos"]) == 1
    )
    assert out["_team_selection"]["access_verified"] is False
    s["requested"] = ["design"]
    assert len(te.select_manifest(m, s)["skills_repos"]) == 1


@pytest.mark.parametrize(
    "change",
    [
        lambda m, s: m["knowledge_bases"][0].pop("entitlement"),
        lambda m, s: s.update(person="p-two", requested=["design"]),
        lambda m, s: s.update(team_digest="f" * 64),
        lambda m, s: m["skills_repos"].append(copy.deepcopy(m["skills_repos"][0])),
        lambda m, s: m["team_contract"].update(path="../team.json"),
    ],
)
def test_incomplete_foreign_or_duplicate_refuses(tmp_path, change):
    m, s, _ = package(tmp_path)
    change(m, s)
    with pytest.raises(ValueError):
        te.select_manifest(m, s)


def test_missing_selection_or_changed_source_refuses(tmp_path):
    m, s, p = package(tmp_path)
    with pytest.raises(ValueError):
        te.select_manifest(m, None)
    p.write_text(p.read_text() + " ")
    with pytest.raises(ValueError):
        te.select_manifest(m, s)


def test_solo_manifest_retains_identity_and_rejects_unbound_selection():
    m = {"org": {"id": "solo"}}
    assert te.select_manifest(m, None) == m
    with pytest.raises(ValueError):
        te.select_manifest(m, {"person": "p-one"})


def test_private_companion_never_selected_for_another_principal(tmp_path):
    m, s, p = package(tmp_path)
    d = json.loads(p.read_text())
    d["repositories"][0].update(
        audience="private",
        readers=["p-two"],
        remote=m["knowledge_bases"][0]["repository"],
    )
    d["entitlements"][0]["repository"] = "repo-one"
    p.write_text(json.dumps(d))
    s["team_digest"] = m["team_contract"]["sha256"] = hashlib.sha256(
        p.read_bytes()
    ).hexdigest()
    assert te.select_manifest(m, s)["knowledge_bases"] == []
    s["requested"] = ["notes"]
    with pytest.raises(ValueError):
        te.select_manifest(m, s)


def test_asset_cannot_substitute_foreign_remote(tmp_path):
    m, s, p = package(tmp_path)
    d = json.loads(p.read_text())
    d["entitlements"][0]["repository"] = "repo-one"
    d["repositories"][0]["remote"] = "https://git.example/private/other"
    p.write_text(json.dumps(d))
    s["team_digest"] = m["team_contract"]["sha256"] = hashlib.sha256(
        p.read_bytes()
    ).hexdigest()
    with pytest.raises(ValueError):
        te.select_manifest(m, s)
