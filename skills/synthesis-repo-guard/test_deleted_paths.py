"""Deleted child directories must not erase a valid repository boundary."""
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "deleted_path_checkpoint", Path(__file__).with_name("checkpoint_sync.py")
)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-b", "main")
    return root.resolve()


def test_removed_cache_parent_still_resolves_its_repository(tmp_path):
    root = repo(tmp_path)
    target = root / "scripts" / "__pycache__" / "fixture.pyc"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"generated fixture")
    assert MODULE.repo_root_for_path(target) == root  # positive control
    target.unlink()
    target.parent.rmdir()
    assert MODULE.repo_root_for_path(target) == root
    assert MODULE.file_evidence(target)["state"] == "deleted-or-missing"
    assert not target.parent.exists()


def test_missing_multiple_child_directories_resolve_inside_live_repository(tmp_path):
    root = repo(tmp_path)
    assert MODULE.repo_root_for_path(root / "removed" / "children" / "file") == root


def test_missing_repository_does_not_resolve_from_unrelated_workspace(tmp_path):
    root = repo(tmp_path)
    assert MODULE.repo_root_for_path(root / "present") == root
    assert MODULE.repo_root_for_path(tmp_path / "missing-repository" / "file") is None


@pytest.mark.parametrize("dangling", [False, True])
def test_symlink_ancestor_is_not_a_repository_boundary(tmp_path, dangling):
    root = repo(tmp_path)
    alias = tmp_path / "alias"
    alias.symlink_to(root / "missing" if dangling else root, target_is_directory=True)
    assert MODULE.repo_root_for_path(alias / "file") is None


def test_missing_registered_nested_worktree_cannot_fall_into_parent_repo(tmp_path):
    root = repo(tmp_path)
    nested = root / "nested"
    git(root, "worktree", "add", "--orphan", "-b", "nested", str(nested))
    assert MODULE.repo_root_for_path(nested / "file") == nested
    # Model interruption, not the sanctioned retirement workflow. This exact
    # synthetic directory is inside this test's freshly created repository.
    assert nested.parent == root and (nested / ".git").is_file()
    shutil.rmtree(nested)
    assert MODULE.repo_root_for_path(nested / "removed" / "file") is None


def test_deleted_path_resolution_fails_when_worktree_inventory_is_unavailable(tmp_path, monkeypatch):
    root = repo(tmp_path)
    monkeypatch.setattr(MODULE, "listed_worktree_roots", lambda _repo: ([], "unavailable"))
    assert MODULE.repo_root_for_path(root / "missing-parent" / "file") is None


def test_local_receipt_preserves_missing_file_evidence_without_restoring_it(tmp_path, monkeypatch):
    root = repo(tmp_path)
    target = root / "scripts" / "removed" / "cache.pyc"
    (root / "scripts").mkdir()
    state = tmp_path / "state"
    pending = state / "pending"
    pending.mkdir(parents=True)
    monkeypatch.setattr(MODULE, "STATE_DIR", state)
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending)
    monkeypatch.setattr(MODULE, "LOCAL_HANDOFF_DIR", state / "receipts")
    manifest = MODULE.pending_manifest_path("deleted-path-fixture")
    content = {"schema_version": 2, "session_id": "deleted-path-fixture",
               "paths": [str(target)], "remote_paths": []}
    manifest.write_text(json.dumps(content))
    original_git = MODULE.git

    def fixture_git(path, *args, **kwargs):
        # This fixture tests file resolution/receipt semantics, not commits.
        # Real Git resolves the repository; fixed read-only HEAD metadata
        # avoids creating commits in the synthetic repository.
        if args == ("branch", "--show-current"):
            return 0, "main", ""
        if args == ("rev-parse", "HEAD"):
            return 0, "a" * 40, ""
        return original_git(path, *args, **kwargs)

    monkeypatch.setattr(MODULE, "git", fixture_git)
    results, observed = MODULE.local_handoff_checkpoint(
        {"session_id": "deleted-path-fixture", "cwd": str(root)}, MODULE.DEFAULTS
    )
    assert observed == manifest
    assert results[0]["action"] == "local-ready"
    assert results[0]["file_evidence"] == [{"path": str(target), "state": "deleted-or-missing"}]
    assert json.loads(manifest.read_text()) == content
    assert not target.parent.exists()
