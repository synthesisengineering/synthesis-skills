"""Actual Git merge commits must enter the existing commit guard owner."""
from pathlib import Path

import pytest

from test_pre_commit import (
    doctor, doctor_harness, engine_copy, r4_board_claim,
    r4_policy, repository, run,
)


def merge_repository(tmp_path: Path, *, path: str = "claimed/topic.txt", content: str = "topic\n"):
    root, env = repository(tmp_path)
    initial_branch = run(root, "git", "branch", "--show-current").stdout.strip()
    assert run(root, "git", "switch", "-c", "topic").returncode == 0
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    assert run(root, "git", "add", path).returncode == 0
    # Fixture history predates installation of the guard being tested.
    assert run(root, "git", "-c", "core.hooksPath=/dev/null", "commit", "-m", "Topic fixture").returncode == 0
    assert run(root, "git", "switch", initial_branch).returncode == 0
    (root / "local.txt").write_text("local\n")
    assert run(root, "git", "add", "local.txt").returncode == 0
    assert run(root, "git", "-c", "core.hooksPath=/dev/null", "commit", "-m", "Local fixture").returncode == 0
    engine = tmp_path / "engine"
    engine_copy(engine)
    board = tmp_path / "coordination" / "active-sessions.md"
    r4_board_claim(board, root, engine)
    r4_policy(Path(env["SYNTHESIS_GIT_HOOK_CONFIG"]), board)
    env["SYNTHESIS_COORDINATION_SESSION"] = "A"
    assert run(root, "git", "config", "core.hooksPath", str(engine)).returncode == 0
    return root, env, engine


def merge(root, env):
    before = run(root, "git", "rev-parse", "HEAD").stdout.strip()
    result = run(root, "git", "merge", "--no-ff", "topic", "-m", "Merge fixture", env=env)
    after = run(root, "git", "rev-parse", "HEAD").stdout.strip()
    return result, before, after


def test_clean_merge_refuses_outside_claim_before_head_changes(tmp_path):
    root, env, _ = merge_repository(tmp_path, path="outside.txt")
    result, before, after = merge(root, env)
    assert result.returncode != 0, result.stdout + result.stderr
    assert before == after
    assert "refused-outside-claim" in result.stdout + result.stderr


def test_clean_merge_inside_claim_consumes_existing_bound_receipt(tmp_path):
    root, env, _ = merge_repository(tmp_path)
    result, before, after = merge(root, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert before != after
    assert len(run(root, "git", "show", "-s", "--format=%P", "HEAD").stdout.split()) == 2
    assert "authority receipt consumed" in result.stdout + result.stderr
    assert (root / "claimed/topic.txt").read_text() == "topic\n"


def test_clean_merge_refuses_wrong_branch_binding(tmp_path):
    root, env, _ = merge_repository(tmp_path)
    assert run(root, "git", "switch", "-c", "unclaimed-branch").returncode == 0
    result, before, after = merge(root, env)
    assert result.returncode != 0
    assert before == after
    assert "coordination authority refused" in result.stderr


def test_clean_merge_refuses_missing_selected_session(tmp_path):
    root, env, _ = merge_repository(tmp_path)
    env["SYNTHESIS_COORDINATION_SESSION"] = "no-such-seat"
    result, before, after = merge(root, env)
    assert result.returncode != 0
    assert before == after
    assert "coordination authority refused" in result.stderr


def test_clean_merge_runs_content_scanner_after_claim_pass(tmp_path):
    root, env, _ = merge_repository(tmp_path, content="new confidential content\n")
    result, before, after = merge(root, env)
    assert result.returncode != 0
    assert before == after
    assert "authority receipt consumed" in result.stdout + result.stderr
    assert "SENSITIVE PATTERN DETECTED" in result.stdout + result.stderr


def test_clean_merge_runs_required_repo_delegate(tmp_path):
    root, env, _ = merge_repository(tmp_path)
    (root / ".githooks").mkdir()
    (root / ".githooks/required").write_text("required\n")
    hook = root / ".githooks/pre-commit"
    hook.write_text("#!/bin/sh\nprintf 'fixture delegate refusal\\n' >&2\nexit 23\n")
    hook.chmod(0o755)
    result, before, after = merge(root, env)
    assert result.returncode != 0
    assert before == after
    assert "fixture delegate refusal" in result.stderr


@pytest.mark.parametrize("damage", ["missing", "not-executable", "directory"])
def test_merge_entry_refuses_unavailable_commit_owner(tmp_path, damage):
    root, env, engine = merge_repository(tmp_path)
    commit = engine / "pre-commit"
    if damage == "not-executable":
        commit.chmod(0o644)
    else:
        commit.unlink()
        if damage == "directory":
            commit.mkdir()
    result, before, after = merge(root, env)
    assert result.returncode != 0
    assert before == after
    assert "MERGE COMMIT BLOCKED" in result.stderr


@pytest.mark.parametrize("damage", ["missing", "not-executable"])
def test_doctor_reports_missing_merge_entry_as_unprotected(tmp_path, damage):
    installed, _, env = doctor_harness(tmp_path)
    hook = installed / "pre-merge-commit"
    if damage == "missing":
        hook.unlink()
    else:
        hook.chmod(0o644)
    result = doctor(installed, env, tmp_path)
    assert result.returncode != 0
    assert "pre-merge-commit" in result.stdout
    assert "without this gate" in result.stdout
