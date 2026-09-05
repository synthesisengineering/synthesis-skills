"""Real-Git controls for knowledge-checkout ownership across engine replays."""

import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import onboard


@pytest.fixture
def kb(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    home = root / "home"
    home.mkdir()
    for key in list(os.environ):
        if key.startswith("GIT_CONFIG_") or key in {
            "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
            "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        }:
            monkeypatch.delenv(key)
    for key, value in {
        "HOME": str(home), "GIT_CONFIG_GLOBAL": str(root / "gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "Fixture User",
        "GIT_AUTHOR_EMAIL": "fixture@example.test", "GIT_COMMITTER_NAME": "Fixture User",
        "GIT_COMMITTER_EMAIL": "fixture@example.test",
    }.items():
        monkeypatch.setenv(key, value)

    def git(*args, cwd=None):
        result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    source = root / "source"
    source.mkdir()
    git("init", "-q", "-b", "main", cwd=source)
    (source / "content.md").write_text("Initial content.\n")
    hooks = source / ".githooks"
    hooks.mkdir()
    (hooks / "pre-commit").write_text("#!/bin/sh\nexit 0\n")
    (hooks / "pre-commit").chmod(0o755)
    git("add", ".", cwd=source)
    git("commit", "-q", "-m", "Seed fixture", cwd=source)
    remote = root / "remote.git"
    git("clone", "-q", "--bare", str(source), str(remote))
    url = "https://example.test/knowledge.git"
    git("config", "--global", "url.%s.insteadOf" % remote.as_uri(), url)
    workspaces = home / "workspaces"
    monkeypatch.setattr(onboard, "WORKSPACES_ROOT", workspaces)
    monkeypatch.setattr(onboard, "HOME", home)
    manifest = {"org": {"workspace": "example"}, "knowledge_bases": [
        {"name": "knowledge", "repository": url, "local_hooks": True},
    ]}
    receipts_path = root / "receipts.json"
    standard = workspaces / "example/knowledge"

    def clone(path=standard):
        path.parent.mkdir(parents=True, exist_ok=True)
        git("clone", "-q", url, str(path))
        git("config", "core.hooksPath", ".githooks", cwd=path)
        return path

    def advance():
        content = source / "content.md"
        content.write_text(content.read_text() + "Published content.\n")
        git("add", "content.md", cwd=source)
        git("commit", "-q", "-m", "Update fixture", cwd=source)
        git("push", str(remote), "main", cwd=source)
        return git("rev-parse", "HEAD", cwd=source)

    def run(enrolling=False, dry_run=False):
        receipts = onboard.Receipts(receipts_path)
        report = onboard.Report(dry_run=dry_run, as_json=True)
        onboard.phase_kbs(report, manifest, receipts, dry_run, enrolling=enrolling)
        return report, receipts

    return SimpleNamespace(root=root, git=git, clone=clone, advance=advance,
        run=run, standard=standard, url=url, manifest=manifest,
        receipts_path=receipts_path, workspaces=workspaces)


def snapshot(repo):
    """Include index/config bytes, not only worktree content and HEAD."""
    return {str(path.relative_to(repo)): path.read_bytes()
            for path in repo.rglob("*") if path.is_file()}


@pytest.mark.parametrize("location", ["standard", "elsewhere"])
@pytest.mark.parametrize("state", ["untracked-branch", "tracking-branch", "dirty", "detached"])
def test_adopted_checkout_survives_enrollment_and_two_replays(kb, location, state):
    path = kb.standard if location == "standard" else kb.workspaces / "another/knowledge"
    kb.clone(path)
    if state == "untracked-branch":
        kb.git("checkout", "-q", "-b", "work/topic", cwd=path)
    elif state == "tracking-branch":
        kb.git("checkout", "-q", "-b", "work/topic", "--track", "origin/main", cwd=path)
    elif state == "dirty":
        (path / "content.md").write_text("Uncommitted work.\n")
        kb.git("add", "content.md", cwd=path)
        (path / "content.md").write_text("Additional unstaged work.\n")
        (path / "untracked.md").write_text("Untracked work.\n")
    else:
        kb.git("checkout", "-q", "--detach", cwd=path)
    before = snapshot(path)
    report, _ = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    assert snapshot(path) == before
    kb.advance()
    for _ in ("update", "repair"):
        report, receipts = kb.run()
        assert report.exit_code() == 0, report.steps
        assert snapshot(path) == before
        assert any("preserved" in step["detail"] for step in report.steps)
        entry = receipts.data["knowledge_repositories"]["knowledge"]
        assert entry["acquisition"] == "adopted"
        assert entry["path"] == str(path)
        assert entry["repository"] == kb.url


def test_legacy_standard_checkout_is_adopted_not_inferred_created(kb):
    path = kb.clone()
    kb.advance()
    before = snapshot(path)
    report, receipts = kb.run()
    assert report.exit_code() == 0, report.steps
    assert snapshot(path) == before
    assert receipts.data["knowledge_repositories"]["knowledge"]["acquisition"] == "adopted"
    assert onboard.Receipts(kb.receipts_path).data["knowledge_repositories"] == receipts.data["knowledge_repositories"]


def test_created_checkout_records_tracking_and_fast_forwards(kb):
    report, receipts = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    entry = receipts.data["knowledge_repositories"]["knowledge"]
    assert entry == {"path": str(kb.standard), "repository": kb.url,
        "acquisition": "created", "branch": "main", "upstream": "refs/remotes/origin/main"}
    config = (kb.standard / ".git/config").read_bytes()
    target = kb.advance()
    report, _ = kb.run()
    assert report.exit_code() == 0, report.steps
    assert kb.git("rev-parse", "HEAD", cwd=kb.standard) == target
    assert (kb.standard / ".git/config").read_bytes() == config


@pytest.mark.parametrize("change", ["branch", "upstream", "detached", "dirty", "ahead", "diverged"])
def test_created_checkout_preserves_work_when_update_binding_is_not_safe(kb, change):
    report, _ = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    path = kb.standard
    if change == "branch":
        kb.git("checkout", "-q", "-b", "work/topic", "--track", "origin/main", cwd=path)
    elif change == "upstream":
        kb.git("config", "branch.main.remote", ".", cwd=path)
        kb.git("config", "branch.main.merge", "refs/heads/main", cwd=path)
    elif change == "detached":
        kb.git("checkout", "-q", "--detach", cwd=path)
    else:
        (path / "content.md").write_text("Personal work.\n")
        kb.git("add", "content.md", cwd=path)
        if change in {"ahead", "diverged"}:
            kb.git("commit", "-q", "-m", "Local fixture", cwd=path)
    if change in {"branch", "upstream", "detached", "dirty", "diverged"}:
        kb.advance()
    before_head = kb.git("rev-parse", "HEAD", cwd=path)
    before = {name: (path / name).read_bytes() for name in ("content.md", ".git/config", ".git/index")}
    report, _ = kb.run()
    assert report.exit_code() != 0, report.steps
    assert kb.git("rev-parse", "HEAD", cwd=path) == before_head
    assert {name: (path / name).read_bytes() for name in before} == before


@pytest.mark.parametrize("field,value", [("path", "/unexpected/knowledge"),
    ("repository", "https://example.test/other.git"), ("acquisition", "unknown"),
    ("branch", "other"), ("upstream", "refs/remotes/other/main")])
def test_corrupt_or_mismatched_provenance_fails_before_checkout_mutation(kb, field, value):
    report, receipts = kb.run(enrolling=True)
    assert report.exit_code() == 0, report.steps
    receipts.data["knowledge_repositories"]["knowledge"][field] = value
    receipts.save()
    before = snapshot(kb.standard)
    report, _ = kb.run()
    assert report.exit_code() != 0, report.steps
    assert snapshot(kb.standard) == before


def test_wrong_remote_is_not_adopted_or_changed(kb):
    path = kb.clone()
    kb.git("remote", "set-url", "origin", "https://example.test/wrong.git", cwd=path)
    before = snapshot(path)
    report, receipts = kb.run()
    assert report.exit_code() != 0, report.steps
    assert snapshot(path) == before
    assert "knowledge" not in receipts.data.get("knowledge_repositories", {})


def test_adopted_missing_protection_is_reported_without_reconfiguration(kb):
    path = kb.clone()
    kb.git("config", "--unset", "core.hooksPath", cwd=path)
    before = snapshot(path)
    report, _ = kb.run()
    assert report.exit_code() != 0, report.steps
    assert snapshot(path) == before


def test_dry_run_does_not_persist_acquisition_or_touch_checkout(kb):
    path = kb.clone()
    before = snapshot(path)
    report, _ = kb.run(dry_run=True)
    assert report.exit_code() == 0, report.steps
    assert snapshot(path) == before
    assert not kb.receipts_path.exists()


def test_legacy_elsewhere_receipt_does_not_fall_back_to_another_clone(kb):
    elsewhere = kb.workspaces / "elsewhere/knowledge"
    receipts = onboard.Receipts(kb.receipts_path)
    receipts.record_adoption("knowledge", elsewhere)
    receipts.save()
    standard = kb.clone()
    before = snapshot(standard)
    report, _ = kb.run()
    assert report.exit_code() != 0, report.steps
    assert snapshot(standard) == before


@pytest.mark.parametrize("value", [None, [], "unexpected", {"knowledge": None},
    {"knowledge": {"acquisition": "created"}}])
def test_invalid_provenance_inventory_is_not_silently_ignored(kb, value):
    path = kb.clone()
    receipts = onboard.Receipts(kb.receipts_path)
    receipts.data["knowledge_repositories"] = value
    receipts.save()
    before = snapshot(path)
    report, _ = kb.run()
    assert report.exit_code() != 0, report.steps
    assert snapshot(path) == before


def test_symbolic_checkout_is_not_adopted(kb):
    elsewhere = kb.clone(kb.workspaces / "elsewhere/knowledge")
    kb.standard.parent.mkdir(parents=True)
    kb.standard.symlink_to(elsewhere, target_is_directory=True)
    before = snapshot(elsewhere)
    report, _ = kb.run()
    assert report.exit_code() != 0, report.steps
    assert snapshot(elsewhere) == before
