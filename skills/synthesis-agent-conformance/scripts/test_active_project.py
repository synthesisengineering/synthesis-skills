#!/usr/bin/env python3
"""Tests for leased active-project pointer validation."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from active_project import load_and_validate, validate


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def fixture(tmp_path: Path) -> tuple[dict[str, object], Path]:
    worktree = tmp_path / "repo"
    worktree.mkdir()
    git(worktree, "init", "--initial-branch", "feature/test")
    git(worktree, "config", "user.email", "test@example.com")
    git(worktree, "config", "user.name", "Test")
    project = worktree / "projects" / "test"
    project.mkdir(parents=True)
    plan = project / "plan.md"
    plan.write_text("# Plan\n", encoding="utf-8")
    git(worktree, "add", ".")
    git(worktree, "commit", "-m", "test")
    head = git(worktree, "rev-parse", "HEAD")
    git(worktree, "update-ref", "refs/remotes/origin/main", head)
    now = datetime.now().astimezone()
    board = tmp_path / "active-sessions.md"
    board.write_text(
        "# Coordination\n\nSchema: v2\nLease: https://example.test/coordination.git\n"
        "## Active sessions\n\n"
        "| id | agent | machine | project | started | heartbeat | mode | workspace(s) / branch | goal | claimed areas (advisory lock) | context role | status |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        f"| A | Codex | mac | test | {now.isoformat()} | {now.isoformat()} | autonomous | {worktree} @ feature/test | work | {project}/** | owner | active |\n\n"
        "## Messages\n\n---\n\n## Protocol\n",
        encoding="utf-8",
    )
    payload: dict[str, object] = {
        "project": str(project),
        "plan": str(plan),
        "worktree": str(worktree),
        "branch": "feature/test",
        "source_commit": head,
        "owner_session": "A",
        "owner_lease": "https://example.test/coordination.git",
    }
    return payload, board


def test_valid_pointer_has_no_issues(tmp_path: Path) -> None:
    payload, board = fixture(tmp_path)

    assert validate(payload, board) == []


def test_pointer_rejects_missing_plan_worktree_and_wrong_owner(tmp_path: Path) -> None:
    payload, board = fixture(tmp_path)
    payload["plan"] = str(tmp_path / "missing-plan.md")
    payload["worktree"] = str(tmp_path / "missing-worktree")
    payload["owner_session"] = "B"

    issues = validate(payload, board)

    assert any("controlling plan is missing" in issue for issue in issues)
    assert any("worktree is missing" in issue for issue in issues)
    assert any("owner session is not active" in issue for issue in issues)


def test_pointer_rejects_expired_owner_lease(tmp_path: Path) -> None:
    payload, board = fixture(tmp_path)
    future = datetime.now().astimezone() + timedelta(hours=5)

    issues = validate(payload, board, now=future)

    assert any("owner session lease expired" in issue for issue in issues)


def test_pointer_rejects_implausible_future_heartbeat(tmp_path: Path) -> None:
    payload, board = fixture(tmp_path)
    past = datetime.now().astimezone() - timedelta(hours=1)

    issues = validate(payload, board, now=past)

    assert any("heartbeat is in the future" in issue for issue in issues)


def test_pointer_owner_must_hold_canonical_context_role(tmp_path: Path) -> None:
    payload, board = fixture(tmp_path)
    board.write_text(
        board.read_text(encoding="utf-8").replace("| owner | active |", "| contributor | active |"),
        encoding="utf-8",
    )

    issues = validate(payload, board)

    assert any("does not hold canonical context role" in issue for issue in issues)


def test_pointer_rejects_branch_behind_origin_main(tmp_path: Path) -> None:
    payload, board = fixture(tmp_path)
    worktree = Path(str(payload["worktree"]))
    tree = git(worktree, "rev-parse", "HEAD^{tree}")
    child = subprocess.run(
        ["git", "-C", str(worktree), "commit-tree", tree, "-p", "HEAD", "-m", "next"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    git(worktree, "update-ref", "refs/remotes/origin/main", child)

    issues = validate(payload, board)

    assert any("behind local origin/main" in issue for issue in issues)


def test_pointer_file_must_not_be_a_symlink(tmp_path: Path) -> None:
    payload, board = fixture(tmp_path)
    target = tmp_path / "target.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    pointer = tmp_path / "active-project.json"
    pointer.symlink_to(target)

    loaded, issues = load_and_validate(pointer, board)

    assert loaded == {}
    assert issues == [f"active-project pointer must not be a symlink: {pointer}"]


def test_pointer_rejects_symlinked_or_outside_project_paths(tmp_path: Path) -> None:
    payload, board = fixture(tmp_path)
    worktree = Path(str(payload["worktree"]))
    external = tmp_path / "external"
    external.mkdir()
    external_project = external / "project"
    external_project.mkdir()
    external_plan = external / "plan.md"
    external_plan.write_text("# External\n", encoding="utf-8")
    linked_project = worktree / "linked-project"
    linked_project.symlink_to(external_project, target_is_directory=True)
    payload["project"] = str(linked_project)
    payload["plan"] = str(external_plan)

    issues = validate(payload, board)

    assert any("project path must not be a symlink" in issue for issue in issues)
    assert any("project directory is outside pointer worktree" in issue for issue in issues)
    assert any("controlling plan is outside project directory" in issue for issue in issues)
