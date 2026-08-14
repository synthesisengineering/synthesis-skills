from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).with_name("retire_worktree.py")
SPEC = importlib.util.spec_from_file_location("retire_worktree", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def git(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *arguments],
        capture_output=True,
        text=True,
        check=True,
    )


def retire(*arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    worktree = Path(arguments[arguments.index("--worktree") + 1])
    synthesis_home = worktree.parent.parent / "synthesis-home"
    environment = dict(os.environ)
    environment["SYNTHESIS_HOME"] = str(synthesis_home)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(cwd) if cwd else None,
        env=environment,
    )


def build_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A clone with an origin bare remote and one commit on main."""
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "--quiet", "--initial-branch", "main", str(remote)],
        check=True,
        capture_output=True,
    )
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "--quiet", str(remote), str(clone)],
        check=True,
        capture_output=True,
    )
    git(clone, "config", "user.email", "test@example.com")
    git(clone, "config", "user.name", "Test")
    (clone / "seed.txt").write_text("seed\n", encoding="utf-8")
    git(clone, "add", "seed.txt")
    git(clone, "commit", "--quiet", "-m", "seed")
    git(clone, "push", "--quiet", "origin", "main")
    return remote, clone


def add_feature_worktree(
    tmp_path: Path, clone: Path, name: str = "feature/demo"
) -> Path:
    worktree = tmp_path / "worktrees" / name.replace("/", "-")
    worktree.parent.mkdir(parents=True, exist_ok=True)
    git(clone, "worktree", "add", str(worktree), "-b", name)
    git(worktree, "config", "user.email", "test@example.com")
    git(worktree, "config", "user.name", "Test")
    return worktree


def commit_and_merge(clone: Path, worktree: Path, branch: str = "feature/demo") -> None:
    (worktree / "change.txt").write_text("change\n", encoding="utf-8")
    git(worktree, "add", "change.txt")
    git(worktree, "commit", "--quiet", "-m", "change")
    git(worktree, "push", "--quiet", "-u", "origin", branch)
    git(clone, "merge", "--quiet", "--no-edit", branch)
    git(clone, "push", "--quiet", "origin", "main")


def test_retires_merged_worktree_and_branches(tmp_path: Path) -> None:
    remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_merge(clone, worktree)

    result = retire(
        "--repository",
        str(clone),
        "--worktree",
        str(worktree),
        "--delete-remote",
    )
    assert result.returncode == 0, result.stderr
    assert not worktree.exists()
    branches = git(clone, "branch", "--list", "feature/demo").stdout
    assert not branches.strip()
    remote_heads = git(clone, "ls-remote", "--heads", "origin", "feature/demo").stdout
    assert not remote_heads.strip()


def test_refuses_unmerged_branch(tmp_path: Path) -> None:
    remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    (worktree / "unmerged.txt").write_text("pending\n", encoding="utf-8")
    git(worktree, "add", "unmerged.txt")
    git(worktree, "commit", "--quiet", "-m", "pending")

    result = retire("--repository", str(clone), "--worktree", str(worktree))
    assert result.returncode == 2
    assert "not fully contained" in result.stderr
    assert worktree.exists()


def test_refuses_dirty_worktree(tmp_path: Path) -> None:
    remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_merge(clone, worktree)
    (worktree / "loose.txt").write_text("uncommitted\n", encoding="utf-8")

    result = retire("--repository", str(clone), "--worktree", str(worktree))
    assert result.returncode == 2
    assert "not clean" in result.stderr
    assert worktree.exists()


def test_refuses_main_worktree_and_wrong_repository(tmp_path: Path) -> None:
    remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_merge(clone, worktree)

    result = retire("--repository", str(clone), "--worktree", str(clone))
    assert result.returncode == 2
    assert "main worktree" in result.stderr

    other_remote, other_clone = build_repo(tmp_path / "other")
    result = retire("--repository", str(other_clone), "--worktree", str(worktree))
    assert result.returncode == 2
    assert "not a worktree of" in result.stderr


def test_refuses_when_cwd_is_inside_target(tmp_path: Path) -> None:
    remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_merge(clone, worktree)

    result = retire(
        "--repository",
        str(clone),
        "--worktree",
        str(worktree),
        cwd=worktree,
    )
    assert result.returncode == 2
    assert "current directory" in result.stderr
    assert worktree.exists()


def test_branch_mismatch_and_detached_head_refuse(tmp_path: Path) -> None:
    remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_merge(clone, worktree)

    result = retire(
        "--repository",
        str(clone),
        "--worktree",
        str(worktree),
        "--branch",
        "feature/other",
    )
    assert result.returncode == 2
    assert "not the expected" in result.stderr

    git(worktree, "checkout", "--quiet", "--detach")
    result = retire("--repository", str(clone), "--worktree", str(worktree))
    assert result.returncode == 2
    assert "not on a local branch" in result.stderr


def test_no_fetch_verifies_against_last_fetched_state(tmp_path: Path) -> None:
    remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_merge(clone, worktree)

    result = retire(
        "--repository",
        str(clone),
        "--worktree",
        str(worktree),
        "--no-fetch",
    )
    assert result.returncode == 0, result.stderr
    assert not worktree.exists()


def test_retirement_reconciles_session_manifest_and_invalidates_receipt(
    tmp_path: Path,
) -> None:
    _remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_merge(clone, worktree)
    synthesis_home = worktree.parent.parent / "synthesis-home"
    pending = synthesis_home / "repo-guard" / "pending"
    receipts = synthesis_home / "repo-guard" / "local-handoff"
    pending.mkdir(parents=True)
    receipts.mkdir(parents=True)
    session_id = "session-retirement"
    name = hashlib.sha256(session_id.encode("utf-8")).hexdigest() + ".json"
    manifest = pending / name
    survivor = clone / "seed.txt"
    retired = worktree / "change.txt"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": session_id,
                "paths": [str(retired), str(survivor)],
                "remote_paths": [str(survivor)],
            }
        ),
        encoding="utf-8",
    )
    receipt = receipts / name
    receipt.write_text("{}\n", encoding="utf-8")

    result = retire("--repository", str(clone), "--worktree", str(worktree))

    assert result.returncode == 0, result.stderr
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["paths"] == [str(survivor)]
    assert payload["remote_paths"] == [str(survivor)]
    assert payload["retired_worktrees"][0]["worktree"] == str(worktree.resolve())
    assert not receipt.exists()
    records = list((synthesis_home / "repo-guard" / "retired-worktrees").glob("*.json"))
    assert len(records) == 1
    assert json.loads(records[0].read_text(encoding="utf-8"))["paths_removed"] == 1


def test_invalid_manifest_blocks_retirement_before_worktree_removal(
    tmp_path: Path,
) -> None:
    _remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_merge(clone, worktree)
    synthesis_home = worktree.parent.parent / "synthesis-home"
    pending = synthesis_home / "repo-guard" / "pending"
    pending.mkdir(parents=True)
    (pending / "invalid.json").write_text("not-json\n", encoding="utf-8")

    result = retire("--repository", str(clone), "--worktree", str(worktree))

    assert result.returncode == 2
    assert "reconciliation preflight failed" in result.stderr
    assert worktree.exists()


def test_invalid_retirement_history_blocks_removal(tmp_path: Path) -> None:
    _remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_merge(clone, worktree)
    synthesis_home = worktree.parent.parent / "synthesis-home"
    pending = synthesis_home / "repo-guard" / "pending"
    pending.mkdir(parents=True)
    session_id = "session-invalid-history"
    name = hashlib.sha256(session_id.encode("utf-8")).hexdigest() + ".json"
    (pending / name).write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": session_id,
                "paths": [str(worktree / "change.txt")],
                "remote_paths": [],
                "retired_worktrees": "invalid",
            }
        ),
        encoding="utf-8",
    )

    result = retire("--repository", str(clone), "--worktree", str(worktree))

    assert result.returncode == 2
    assert "retired_worktrees history is invalid" in result.stderr
    assert worktree.exists()


def test_reconciler_resolution_survives_target_worktree_removal(
    tmp_path: Path, monkeypatch
) -> None:
    repository = tmp_path / "repository"
    worktree = tmp_path / "target-worktree"
    canonical = (
        repository / "skills" / "synthesis-repo-guard" / "checkpoint_sync.py"
    )
    target_local = worktree / "skills" / "synthesis-repo-guard" / "checkpoint_sync.py"
    canonical.parent.mkdir(parents=True)
    target_local.parent.mkdir(parents=True)
    canonical.write_text("# canonical\n", encoding="utf-8")
    target_local.write_text("# target local\n", encoding="utf-8")
    monkeypatch.setattr(MODULE, "CHECKPOINT_SYNC", target_local)

    assert MODULE.checkpoint_sync_path(repository, worktree) == canonical.resolve()

    canonical.unlink()
    assert MODULE.checkpoint_sync_path(repository, worktree) is None
