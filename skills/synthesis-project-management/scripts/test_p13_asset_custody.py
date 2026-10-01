from pathlib import Path
import sys

S = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(S / "synthesis-onboarding/scripts"))
sys.path.insert(0, str(S / "synthesis-project-management/scripts"))
import onboard  # noqa: E402 - exact sibling source is selected before importing the owner


def test_actual_copy_owner_does_not_retire_other_principal(tmp_path, monkeypatch):
    target = tmp_path / "skills"
    target.mkdir()
    receipts = onboard.Receipts(tmp_path / "receipts.json")
    receipts.data["org_skill_copies"] = {
        str(target / "first-skill"): {
            "repository": "https://git.example/org/skills",
            "organization": "org-one",
            "deletion_unit": "unit-one",
            "principal": "p-one",
            "commit": "a" * 40,
            "sha256": "b" * 64,
        }
    }
    called = []
    monkeypatch.setattr(onboard, "organization_skill_targets", lambda *a: [target])
    monkeypatch.setattr(onboard, "retire_org_copy", lambda *a, **k: called.append(a))
    onboard.phase_org_skills(
        onboard.Report(dry_run=True, as_json=True),
        {
            "org": {"id": "org-one", "workspace": "unit-one"},
            "_team_selection": {"person": "p-two"},
            "skills_repos": [],
        },
        receipts,
        True,
    )
    assert not called


def test_actual_copy_owner_exact_principal_is_selected(tmp_path, monkeypatch):
    target = tmp_path / "skills"
    target.mkdir()
    receipts = onboard.Receipts(tmp_path / "receipts.json")
    receipts.data["org_skill_copies"] = {
        str(target / "first-skill"): {
            "repository": "https://git.example/org/skills",
            "organization": "org-one",
            "deletion_unit": "unit-one",
            "principal": "p-one",
            "commit": "a" * 40,
            "sha256": "b" * 64,
        }
    }
    called = []
    monkeypatch.setattr(onboard, "organization_skill_targets", lambda *a: [target])
    monkeypatch.setattr(onboard, "retire_org_copy", lambda *a, **k: called.append(a))
    onboard.phase_org_skills(
        onboard.Report(dry_run=True, as_json=True),
        {
            "org": {"id": "org-one", "workspace": "unit-one"},
            "_team_selection": {"person": "p-one"},
            "skills_repos": [],
        },
        receipts,
        True,
    )
    assert len(called) == 1
