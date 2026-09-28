import onboard
import organization


def test_manifest_scoped_receipts_and_cache_have_disjoint_names():
    left = {"org": {"id": "org-one", "workspace": "unit-one"}}
    right = {"org": {"id": "org-two", "workspace": "unit-two"}}
    assert onboard.organization_asset_key(
        left, "notes"
    ) != onboard.organization_asset_key(right, "notes")
    assert onboard.organization_asset_cache(
        left, "skills"
    ) != onboard.organization_asset_cache(right, "skills")
    assert organization.repository_key(
        "https://one.example/team/config.git"
    ) != organization.repository_key("https://two.example/team/config.git")


def test_enrolling_second_org_never_retires_foreign_copy(tmp_path, monkeypatch):
    target = tmp_path / "skills"
    target.mkdir()
    receipts = onboard.Receipts(tmp_path / "receipts.json")
    receipts.data["org_skill_copies"] = {
        str(target / "first-skill"): {
            "repository": "https://one.example/team/skills.git",
            "organization": "org-one",
            "commit": "a" * 40,
            "sha256": "b" * 64,
        }
    }
    calls = []
    monkeypatch.setattr(onboard, "organization_skill_targets", lambda *args: [target])
    monkeypatch.setattr(
        onboard, "retire_org_copy", lambda *args, **kwargs: calls.append(args)
    )
    report = onboard.Report(dry_run=True, as_json=True)
    onboard.phase_org_skills(
        report,
        {"org": {"id": "org-two", "workspace": "unit-two"}, "skills_repos": []},
        receipts,
        True,
    )
    assert not calls


def test_scoped_assets_do_not_search_other_workspace(tmp_path, monkeypatch):
    root = tmp_path / "workspaces"
    (root / "first/notes/.git").mkdir(parents=True)
    monkeypatch.setattr(onboard, "WORKSPACES_ROOT", root)
    monkeypatch.setattr(
        onboard, "origin_url", lambda p: "https://git.example/shared/notes.git"
    )
    assert (
        onboard.find_adoptable(
            "notes", "https://git.example/shared/notes.git", [], workspace="second"
        )
        is None
    )
    assert (
        onboard.find_adoptable(
            "notes", "https://git.example/shared/notes.git", [], workspace="first"
        )
        == root / "first/notes"
    )
