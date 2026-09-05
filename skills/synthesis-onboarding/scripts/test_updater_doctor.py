"""Read-only doctor consumers for checkout ownership and instruction migration."""

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

import onboard
import system_contract as contract
from test_kb_update_ownership import kb, snapshot  # noqa: F401


@pytest.fixture
def installed(kb, monkeypatch):
    report, receipts = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    public = kb.root / "public"
    organization = kb.root / "organization"
    public_relative = "skills/synthesis-onboarding/references/kernel.example.md"
    organization_relative = ".agents/workspace-instructions.md"
    for root, relative, content in (
        (public, public_relative, "Public fixture instructions.\n"),
        (organization, organization_relative, "Organization fixture instructions.\n"),
    ):
        path = root / relative
        path.parent.mkdir(parents=True)
        path.write_text(content)
        kb.git("init", "-q", "-b", "main", cwd=root)
        kb.git("add", ".", cwd=root)
        kb.git("commit", "-q", "-m", "Seed fixture", cwd=root)
    manifest = {**kb.manifest, "_path": str(organization / ".agents/onboarding.yaml"),
                "skills_repos": [],
                "instruction_sources": [{"path": organization_relative, "required": True}]}
    workspace = kb.standard.parent
    graph = {"schema_version": 1, "sources": [
        {"role": "public", "path": public_relative, "required": True},
        {"role": "organization", "path": organization_relative, "required": True}],
        "output": "AGENTS.md", "claude_adapter": "CLAUDE.md"}
    pair = contract.materialize_instruction_pair(graph,
        {"public": public, "organization": organization}, workspace, generation=1)
    receipts.data["instruction_receipt"] = pair
    receipts.save()
    real_receipts = onboard.Receipts
    monkeypatch.setattr(onboard, "Receipts", lambda *a, **k: real_receipts(kb.receipts_path))
    monkeypatch.setattr(onboard, "source_root", lambda: public)
    # These cases exercise the actual organization and output doctor blocks;
    # unrelated public-plugin and personal-layer selection has separate tests.
    monkeypatch.setattr(onboard, "render_layer_doctor", lambda *a, **k: False)

    def doctor():
        report = onboard.Report(as_json=True)
        code = onboard.doctor(report, manifest, [], onboard.normalize_policy("stable", None))
        return code, report

    def read_receipts():
        return real_receipts(kb.receipts_path)

    return SimpleNamespace(kb=kb, receipts=read_receipts, workspace=workspace,
        manifest=manifest, pair=pair, doctor=doctor)


def assert_read_only_failure(installed):
    before = snapshot(installed.kb.root)
    code, report = installed.doctor()
    assert code == 1, report.steps
    assert any(step["status"] == onboard.ERROR for step in report.steps)
    assert snapshot(installed.kb.root) == before
    return report


def test_current_instruction_and_owned_checkout_doctor_passes_read_only(installed):
    before = snapshot(installed.kb.root)
    code, report = installed.doctor()
    assert code == 0, report.steps
    assert snapshot(installed.kb.root) == before
    assert onboard._organization_probe(installed.manifest, installed.receipts())[0] is True
    assert onboard._knowledge_probe(installed.manifest, installed.receipts())[0] is True


@pytest.mark.parametrize("converted", [False, True], ids=["legacy-duplicate", "legacy-adapter"])
def test_doctor_requires_migration_for_both_legacy_output_forms(installed, converted):
    receipts = installed.receipts()
    agents = (installed.workspace / "AGENTS.md").read_bytes()
    receipts.data["instruction_receipt"]["outputs"]["CLAUDE.md"]["sha256"] = hashlib.sha256(agents).hexdigest()
    if not converted:
        (installed.workspace / "CLAUDE.md").write_bytes(agents)
    receipts.save()
    report = assert_read_only_failure(installed)
    assert any(step["detail"].startswith("workspace instruction migration required")
               for step in report.steps)


@pytest.mark.parametrize("corruption", ["missing", "list", "sources-map", "sources-scalar",
    "sources-null-entry", "sources-bad-role", "outputs-list", "output-null",
    "different-workspace", "wrong-digest"])
def test_doctor_handles_malformed_instruction_receipts_without_traceback(installed, corruption):
    receipts = installed.receipts()
    pair = receipts.data["instruction_receipt"]
    if corruption == "missing":
        del receipts.data["instruction_receipt"]
    elif corruption == "list":
        receipts.data["instruction_receipt"] = ["invalid"]
    elif corruption == "sources-map":
        pair["sources"] = {"public": {}}
    elif corruption == "sources-scalar":
        pair["sources"] = 17
    elif corruption == "sources-null-entry":
        pair["sources"] = [None]
    elif corruption == "sources-bad-role":
        pair["sources"][0]["role"] = []
    elif corruption == "outputs-list":
        pair["outputs"] = []
    elif corruption == "output-null":
        pair["outputs"]["CLAUDE.md"] = None
    elif corruption == "different-workspace":
        pair["outputs"]["CLAUDE.md"]["path"] = str(installed.kb.root / "other/CLAUDE.md")
    else:
        pair["outputs"]["CLAUDE.md"]["sha256"] = "a" * 64
    receipts.save()
    assert_read_only_failure(installed)


def test_adopted_feature_branch_and_private_work_remain_unchanged_during_doctor(installed):
    receipts = installed.receipts()
    kb = installed.kb
    receipts.data["knowledge_repositories"].pop("knowledge")
    receipts.record_knowledge_repository("knowledge", kb.standard, kb.url, "adopted")
    kb.git("checkout", "-q", "-b", "work/topic", cwd=kb.standard)
    (kb.standard / "untracked.md").write_text("Uncommitted fixture content.\n")
    before = snapshot(kb.root)
    code, report = installed.doctor()
    assert code == 0, report.steps
    assert snapshot(kb.root) == before
    assert onboard._organization_probe(installed.manifest, installed.receipts())[0] is True


@pytest.mark.parametrize("corruption", ["unknown-ownership", "invalid-inventory", "invalid-adoption",
    "invalid-entry", "wrong-path", "wrong-remote", "branch-drift", "upstream-drift", "dirty"])
def test_doctor_and_both_probes_fail_closed_on_knowledge_ownership(installed, corruption):
    receipts = installed.receipts()
    kb = installed.kb
    if corruption == "unknown-ownership":
        receipts.data.pop("knowledge_repositories")
    elif corruption == "invalid-inventory":
        receipts.data["knowledge_repositories"] = []
    elif corruption == "invalid-adoption":
        receipts.data["adopted_repos"] = []
    elif corruption == "invalid-entry":
        receipts.data["knowledge_repositories"]["knowledge"] = None
    elif corruption == "wrong-path":
        receipts.data["knowledge_repositories"]["knowledge"]["path"] = str(kb.root / "elsewhere")
    elif corruption == "wrong-remote":
        kb.git("remote", "set-url", "origin", "https://example.test/wrong.git", cwd=kb.standard)
    elif corruption == "branch-drift":
        kb.git("checkout", "-q", "-b", "work/topic", "--track", "origin/main", cwd=kb.standard)
    elif corruption == "upstream-drift":
        kb.git("config", "branch.main.remote", ".", cwd=kb.standard)
    else:
        (kb.standard / "content.md").write_text("Work in progress.\n")
    receipts.save()
    assert_read_only_failure(installed)
    before = snapshot(kb.root)
    assert onboard._organization_probe(installed.manifest, installed.receipts())[0] is False
    assert onboard._knowledge_probe(installed.manifest, installed.receipts())[0] is False
    assert snapshot(kb.root) == before


@pytest.mark.parametrize("corruption", ["null", "list", "scalar", "entry-null",
    "entry-list", "entry-empty", "repository-type", "digest-type", "path-relative"])
def test_malformed_skill_copy_inventory_cannot_escape_doctor(installed, corruption):
    receipts = installed.receipts()
    path = str(installed.kb.workspaces.parent / ".agents/skills/example-skill")
    metadata = {"repository": "https://example.test/skills.git", "commit": "a" * 40,
                "sha256": "b" * 64}
    value = {path: metadata}
    if corruption == "null":
        value = None
    elif corruption == "list":
        value = []
    elif corruption == "scalar":
        value = 17
    elif corruption == "entry-null":
        value[path] = None
    elif corruption == "entry-list":
        value[path] = []
    elif corruption == "entry-empty":
        value[path] = {}
    elif corruption == "repository-type":
        metadata["repository"] = []
    elif corruption == "digest-type":
        metadata["sha256"] = []
    else:
        value = {"relative-path": metadata}
    receipts.data["org_skill_copies"] = value
    receipts.save()
    assert_read_only_failure(installed)


def git_artifact(installed, name):
    kb = installed.kb
    value = Path(kb.git("rev-parse", "--git-path", name, cwd=kb.standard))
    path = value if value.is_absolute() else kb.standard / value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("Retained fixture state.\n")
    return path


@pytest.mark.parametrize("consumer", ["doctor", "update"])
@pytest.mark.parametrize("artifact", [".synthesis-index-fixture", ".synthesis-index-fixture.recovery.json",
    ".synthesis-index-fixture.lock", "HEAD.lock", "index.lock", "refs/heads/main.lock"])
def test_created_pending_git_state_remains_non_green_without_mutation(installed, consumer, artifact):
    git_artifact(installed, artifact)
    before = snapshot(installed.kb.root)
    if consumer == "doctor":
        assert_read_only_failure(installed)
        assert onboard._organization_probe(installed.manifest, installed.receipts())[0] is False
    else:
        report, _ = installed.kb.run()
        assert report.exit_code() != 0, report.steps
    assert snapshot(installed.kb.root) == before


@pytest.mark.parametrize("consumer", ["doctor", "update"])
@pytest.mark.parametrize("artifact", [".synthesis-index-fixture.recovery.json", "HEAD.lock", "index.lock", "refs/heads/main.lock"])
def test_adopted_git_state_is_not_owned_or_changed(installed, consumer, artifact):
    receipts = installed.receipts()
    receipts.data["knowledge_repositories"].pop("knowledge")
    receipts.record_knowledge_repository("knowledge", installed.kb.standard, installed.kb.url, "adopted")
    git_artifact(installed, artifact)
    before = snapshot(installed.kb.root)
    if consumer == "doctor":
        code, report = installed.doctor()
        assert code == 0, report.steps
    else:
        report, _ = installed.kb.run()
        assert report.exit_code() == 0, report.steps
    assert snapshot(installed.kb.root) == before


@pytest.mark.parametrize("consumer", ["doctor", "update"])
def test_git_administrative_symlink_redirection_is_refused(installed, consumer):
    kb = installed.kb
    index = Path(kb.git("rev-parse", "--git-path", "index", cwd=kb.standard))
    index = index if index.is_absolute() else kb.standard / index
    destination = kb.root / "redirected-index"
    destination.write_bytes(index.read_bytes())
    index.unlink()
    index.symlink_to(destination)
    before = snapshot(kb.root)
    if consumer == "doctor":
        assert_read_only_failure(installed)
    else:
        report, _ = kb.run()
        assert report.exit_code() != 0, report.steps
    assert index.is_symlink()
    assert snapshot(kb.root) == before


@pytest.mark.parametrize("consumer", ["doctor", "update"])
def test_git_paths_find_pending_state_after_administrative_directory_move(installed, consumer):
    kb = installed.kb
    admin = kb.root / "separate-git"
    kb.git("init", "-q", "--separate-git-dir", str(admin), cwd=kb.standard)
    assert (kb.standard / ".git").is_file()
    artifact = git_artifact(installed, ".synthesis-index-fixture.recovery.json")
    assert artifact.parent == admin
    before = snapshot(kb.root)
    if consumer == "doctor":
        assert_read_only_failure(installed)
    else:
        report, _ = kb.run()
        assert report.exit_code() != 0, report.steps
    assert snapshot(kb.root) == before
