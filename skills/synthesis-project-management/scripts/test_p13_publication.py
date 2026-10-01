from pathlib import Path
import hashlib
import importlib.util
import json
import sys

S = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(S / "synthesis-project-management/scripts"))
from test_team_contract import contract  # noqa: E402 - exact sibling source is selected before importing the owner

spec = importlib.util.spec_from_file_location(
    "p13_publish_guard", S / "synthesis-agent-guardrails/guards/publish_guard.py"
)
pg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pg)
sys.path.insert(0, str(S / "synthesis-agent-guardrails/tests"))


import test_publish_guard_artifacts as candidate_fixtures  # noqa: E402 - explicit sibling fixture owner

candidate = candidate_fixtures.candidate


def enrolled(tmp_path, monkeypatch, candidate, person="p-two", layers=None):
    path, binding, artifact = candidate
    d = contract()
    d["policy"]["restriction_ids"] = ["human-publication"]
    source = tmp_path / "team.json"
    source.write_text(json.dumps(d))
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    cfg = Path(pg.config_path())
    cfg.write_text(
        json.dumps(
            {
                "auto_deploy_repos": [binding["repo"]],
                "team_contracts": [
                    {
                        "repository": binding["repo"],
                        "path": str(source),
                        "sha256": sha,
                        "person": person,
                        "policy_layers": layers or [],
                    }
                ],
            }
        )
    )
    return source


def test_ineligible_principal_actual_approval_refused(candidate, tmp_path, monkeypatch):
    enrolled(tmp_path, monkeypatch, candidate, "p-one")
    assert (
        pg.approve_deployment(str(candidate[0]), "Synthetic action", "Yes synthetic")
        == 2
    )


def test_eligible_and_exact_owner_still_consumes_once(candidate, tmp_path, monkeypatch):
    enrolled(tmp_path, monkeypatch, candidate)
    assert (
        pg.approve_deployment(str(candidate[0]), "Synthetic action", "Yes synthetic")
        == 0
    )
    assert pg.consume_deployment(str(candidate[0])) == 0
    assert pg.consume_deployment(str(candidate[0])) == 2


def test_changed_role_source_or_forged_ledger_refuses(candidate, tmp_path, monkeypatch):
    source = enrolled(tmp_path, monkeypatch, candidate)
    assert (
        pg.approve_deployment(str(candidate[0]), "Synthetic action", "Yes synthetic")
        == 0
    )
    source.write_text(source.read_text() + " ")
    assert pg.consume_deployment(str(candidate[0])) == 2


def test_conflicting_layer_cannot_widen_team_role(candidate, tmp_path, monkeypatch):
    enrolled(
        tmp_path,
        monkeypatch,
        candidate,
        layers=[
            {
                "restriction_ids": [],
                "approval_roles": {"publish": ["editor"]},
                "minimum_reader": 6,
            }
        ],
    )
    assert (
        pg.approve_deployment(str(candidate[0]), "Synthetic action", "Yes synthetic")
        == 2
    )
