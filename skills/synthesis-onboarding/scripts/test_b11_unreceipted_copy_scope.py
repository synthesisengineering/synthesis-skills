"""Matching Git source bytes prove content, not a deletion-unit copy owner."""

from pathlib import Path
import os
import sys
import json
import subprocess

PUBLIC = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PUBLIC / "skills/synthesis-onboarding/scripts"))
import onboard  # noqa: E402 - exact source owner bound above


def fixture(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    source = tmp_path / "source"
    source.mkdir()
    skills = home / "skills"
    skills.mkdir()
    env = dict(
        os.environ,
        HOME=str(home),
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="Fixture",
        GIT_AUTHOR_EMAIL="fixture@example.invalid",
        GIT_COMMITTER_NAME="Fixture",
        GIT_COMMITTER_EMAIL="fixture@example.invalid",
    )

    def git(*args, input=None):
        return (
            subprocess.run(
                ["git", "-C", str(source), *args],
                input=input,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                timeout=10,
                check=True,
            )
            .stdout.decode()
            .strip()
        )

    git("init", "--initial-branch=main")
    p = source / "skills/example/SKILL.md"
    p.parent.mkdir(parents=True)
    p.write_text("# Example\nExact fixture bytes.\n")
    git("add", "skills/example/SKILL.md")
    tree = git("write-tree")
    commit = git("commit-tree", tree, input=b"Fixture source\n")
    git("update-ref", "refs/heads/main", commit)
    target = skills / "example"
    target.mkdir()
    (target / "SKILL.md").write_bytes(p.read_bytes())
    (target / ".source.json").write_text(
        json.dumps(
            {
                "source_type": "organization",
                "source_repo": "https://git.example/team/skills.git",
                "source_path": "skills/example/SKILL.md",
                "source_commit": commit,
            }
        )
    )
    monkeypatch.setattr(onboard, "HOME", home)
    monkeypatch.setattr(onboard, "organization_skill_targets", lambda *a: [skills])
    monkeypatch.setattr(onboard, "organization_asset_cache", lambda *a: source)
    monkeypatch.setattr(onboard, "clone_or_update", lambda *a, **k: onboard.OK)
    calls = []
    original_run = onboard.run

    def run(args, **kwargs):
        calls.append(args)
        if args[0] == "git":
            return original_run(args, **kwargs)
        assert args[-1] == "status", "This fixture must never reach install"
        return 0, "", ""

    monkeypatch.setattr(onboard, "run", run)
    manifest = {
        "org": {"id": "org-one", "workspace": "new-unit"},
        "skills_repos": [
            {
                "name": "catalog",
                "repository": "https://git.example/team/skills.git",
                "capability": "skills-install",
            }
        ],
    }
    receipts = onboard.Receipts(home / "receipts.json")
    return manifest, receipts, target, source, calls


def test_unreceipted_matching_source_not_adopted_as_new_unit(tmp_path, monkeypatch):
    manifest, receipts, target, source, calls = fixture(tmp_path, monkeypatch)
    original = {p.name: p.read_bytes() for p in target.iterdir()}
    report = onboard.Report(dry_run=False, as_json=True)
    onboard.phase_org_skills(report, manifest, receipts, False)
    assert {p.name: p.read_bytes() for p in target.iterdir()} == original
    assert str(target) not in receipts.data.get("org_skill_copies", {}), (
        "Matching source cannot establish missing organization/deletion-unit custody"
    )
    assert report.exit_code() != 0


def test_scoped_current_receipt_positive(tmp_path, monkeypatch):
    manifest, receipts, target, source, calls = fixture(tmp_path, monkeypatch)
    metadata = {
        "organization": "org-one",
        "workspace": "new-unit",
        "deletion_unit": "new-unit",
        "repository": manifest["skills_repos"][0]["repository"],
        "commit": json.loads((target / ".source.json").read_text())["source_commit"],
        "sha256": onboard.paths_digest([target]),
    }
    receipts.data["org_skill_copies"] = {str(target): metadata}
    report = onboard.Report(dry_run=False, as_json=True)
    onboard.phase_org_skills(report, manifest, receipts, False)
    assert report.exit_code() == 0
    assert str(target) in receipts.data["org_skill_copies"]
