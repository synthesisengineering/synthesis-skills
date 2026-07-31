from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).with_name("retire_worktree.py")


def git(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *arguments],
        capture_output=True,
        text=True,
        check=True,
    )


def retire(*arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(cwd) if cwd else None,
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
