"""Actual retirement planner must bind both org and deletion-unit identity."""

from pathlib import Path
import sys
import copy

PUBLIC = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PUBLIC / "skills/synthesis-onboarding/scripts"))
import onboard  # noqa: E402 - exact source owner bound above


def test_same_org_other_or_unknown_deletion_unit_does_not_retire(tmp_path, monkeypatch):
    target = tmp_path / "skills"
    target.mkdir()
    receipts = onboard.Receipts(tmp_path / "receipts.json")
    old = {
        "repository": "https://git.example/team/skills.git",
        "organization": "org-one",
        "commit": "a" * 40,
        "sha256": "b" * 64,
    }
    # Original B11 writes only org identity; no deletion-unit attribution is available.
    receipts.data["org_skill_copies"] = {str(target / "first-skill"): old}
    prior = copy.deepcopy(receipts.data)
    calls = []
    monkeypatch.setattr(onboard, "organization_skill_targets", lambda *a: [target])
    monkeypatch.setattr(onboard, "retire_org_copy", lambda *a, **k: calls.append(a))
    report = onboard.Report(dry_run=True, as_json=True)
    onboard.phase_org_skills(
        report,
        {"org": {"id": "org-one", "workspace": "other-unit"}, "skills_repos": []},
        receipts,
        True,
    )
    assert not calls, (
        "An org-only receipt cannot authorize retirement in a new deletion-unit namespace"
    )
    assert receipts.data == prior


def test_distinct_org_retirement_positive(tmp_path, monkeypatch):
    target = tmp_path / "skills"
    target.mkdir()
    receipts = onboard.Receipts(tmp_path / "receipts.json")
    receipts.data["org_skill_copies"] = {
        str(target / "first-skill"): {
            "repository": "https://git.example/team/skills.git",
            "organization": "org-one",
            "commit": "a" * 40,
            "sha256": "b" * 64,
        }
    }
    calls = []
    monkeypatch.setattr(onboard, "organization_skill_targets", lambda *a: [target])
    monkeypatch.setattr(onboard, "retire_org_copy", lambda *a, **k: calls.append(a))
    onboard.phase_org_skills(
        onboard.Report(dry_run=True, as_json=True),
        {"org": {"id": "org-two", "workspace": "other-unit"}, "skills_repos": []},
        receipts,
        True,
    )
    assert not calls
