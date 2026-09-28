from pathlib import Path
import hashlib
import json
import sys
import pytest

S = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(S / "synthesis-onboarding/scripts"),
    str(S / "synthesis-project-management/scripts"),
]
import onboard  # noqa: E402 - exact sibling source is selected before importing the owner
import team_retirement as tr  # noqa: E402 - exact sibling source is selected before importing the owner
from system_contract import SystemState  # noqa: E402 - exact sibling source is selected before importing the owner
from test_team_contract import contract  # noqa: E402 - exact sibling source is selected before importing the owner


def fixture(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    state = SystemState(home)
    monkeypatch.setattr(onboard, "HOME", home)
    monkeypatch.setattr(onboard, "STATE_DIR", state.state_dir)
    d = contract()
    d["governance"]["mirror_owner"] = "p-two"
    d["people"][0]["status"] = "retired"
    d["seats"][0]["occupancies"][0]["closed"] = "2026-09-26T00:00:00Z"
    d["people"][2]["custodians"] = ["p-two"]
    d["governance"]["departures"] = [
        {
            "id": "departure-one",
            "person": "p-one",
            "at": "2026-09-26T00:00:00Z",
            "approved_by": "p-two",
            "approval_digest": "a" * 64,
            "native_ref": "cc:synthetic",
            "observation_digest": "b" * 64,
        }
    ]
    p = tmp_path / "team.json"
    p.write_text(json.dumps(d))
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    m = {
        "version": 2,
        "org": {"id": "org-one", "workspace": "unit-one"},
        "team_contract": {"path": "team.json", "sha256": sha},
        "skills_repos": [],
        "instruction_sources": [{"path": "rules.md"}],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(m))
    selection = {"person": "p-one", "requested": [], "team_digest": sha}
    receipts = onboard.Receipts(state.state_dir / "receipts.json")
    copies = {}
    for name, person in [("departed", "p-one"), ("retained", "p-two")]:
        f = home / ".agents/skills" / name
        f.mkdir(parents=True)
        (f / "SKILL.md").write_text("synthetic " + name)
        (f / ".source.json").write_text(
            json.dumps(
                {
                    "source_type": "organization",
                    "source_repo": "https://git.example/org/skills",
                }
            )
        )
        copies[str(f)] = {
            "repository": "https://git.example/org/skills",
            "organization": "org-one",
            "deletion_unit": "unit-one",
            "principal": person,
            "commit": "a" * 40,
            "sha256": onboard.paths_digest([f]),
        }
    receipts.data["org_skill_copies"] = copies
    receipts.save()
    return state, path, selection, home, receipts


def test_actual_archive_owner_preserves_foreign_and_source(tmp_path, monkeypatch):
    state, path, selection, home, r = fixture(tmp_path, monkeypatch)
    foreign = (home / ".agents/skills/retained/SKILL.md").read_bytes()
    plan = tr.plan(state, path, selection)
    assert len(plan["copies"]) == 1
    out = tr.apply(state, plan, approval_digest=plan["digest"])
    assert out["status"] == "archived"
    assert not (home / ".agents/skills/departed").exists()
    assert (home / ".agents/skills/retained/SKILL.md").read_bytes() == foreign
    archives = list(
        (state.state_dir / "backups").glob("*/org-skills/departed/SKILL.md")
    )
    assert len(archives) == 1 and archives[0].read_text() == "synthetic departed"
    assert path.exists()
    assert len(onboard.Receipts(r.path).data["org_skill_copies"]) == 1


@pytest.mark.parametrize(
    "attack", ["principal", "tamper", "declaration", "stale", "approval", "symlink"]
)
def test_actual_retirement_refuses_without_any_move(tmp_path, monkeypatch, attack):
    state, path, selection, home, r = fixture(tmp_path, monkeypatch)
    plan = tr.plan(state, path, selection)
    if attack == "principal":
        r.data["org_skill_copies"][str(home / ".agents/skills/departed")].pop(
            "principal"
        )
        r.save()
    if attack == "tamper":
        (home / ".agents/skills/departed/SKILL.md").write_text("changed")
    if attack == "declaration":
        (path.parent / "team.json").write_text("{}")
    if attack == "stale":
        plan["expires_at"] = "2020-01-01T00:00:00Z"
        plan["digest"] = tr.digest({k: v for k, v in plan.items() if k != "digest"})
    if attack == "approval":
        plan["digest"] = "f" * 64
    if attack == "symlink":
        target = path.parent / "team.json"
        target.rename(path.parent / "saved.json")
        target.symlink_to("saved.json")
    with pytest.raises((ValueError, RuntimeError, OSError)):
        tr.apply(state, plan, approval_digest=plan["digest"])
    assert (home / ".agents/skills/departed").exists() and (
        home / ".agents/skills/retained"
    ).exists()
