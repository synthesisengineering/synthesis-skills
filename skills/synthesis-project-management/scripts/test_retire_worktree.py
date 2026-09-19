from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).with_name("retire_worktree.py")
CHECKPOINT_SCRIPT = (
    SCRIPT.resolve().parents[2] / "synthesis-repo-guard" / "checkpoint_sync.py"
)
SPEC = importlib.util.spec_from_file_location("retire_worktree", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture(autouse=True)
def isolated_module_state(tmp_path, monkeypatch):
    state = tmp_path / "synthesis-home" / "repo-guard"
    monkeypatch.setattr(MODULE, "STATE_DIR", state)
    monkeypatch.setattr(MODULE, "LIFECYCLE_LOCK", state / "lifecycle.lock")
    monkeypatch.setattr(MODULE, "RETIREMENT_RUNTIME_DIR", state / "retirement-runtime")
    monkeypatch.setattr(MODULE, "RETIREMENT_DIR", state / "retired-worktrees")


def git(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(cwd), *arguments],
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


def commit_and_squash_merge(
    clone: Path, worktree: Path, branch: str = "feature/demo"
) -> None:
    """Land the branch via squash: identical tree, no shared commits."""
    (worktree / "change.txt").write_text("change\n", encoding="utf-8")
    git(worktree, "add", "change.txt")
    git(worktree, "commit", "--quiet", "-m", "change")
    git(worktree, "push", "--quiet", "-u", "origin", branch)
    git(clone, "merge", "--quiet", "--squash", branch)
    git(clone, "commit", "--quiet", "-m", f"squash {branch}")
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


def test_retires_squash_merged_worktree_by_identical_tree(tmp_path: Path) -> None:
    remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_squash_merge(clone, worktree)

    result = retire(
        "--repository",
        str(clone),
        "--worktree",
        str(worktree),
        "--delete-remote",
    )
    assert result.returncode == 0, result.stderr
    assert "identical-tree" in result.stdout
    assert not worktree.exists()
    branches = git(clone, "branch", "--list", "feature/demo").stdout
    assert not branches.strip()
    remote_heads = git(clone, "ls-remote", "--heads", "origin", "feature/demo").stdout
    assert not remote_heads.strip()


def test_refuses_squash_merged_worktree_with_extra_commits(tmp_path: Path) -> None:
    remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_squash_merge(clone, worktree)
    (worktree / "extra.txt").write_text("after squash\n", encoding="utf-8")
    git(worktree, "add", "extra.txt")
    git(worktree, "commit", "--quiet", "-m", "after squash")

    result = retire("--repository", str(clone), "--worktree", str(worktree))
    assert result.returncode == 2
    assert "not fully contained" in result.stderr
    assert worktree.exists()


def stale_upstream_worktree(tmp_path: Path) -> tuple[Path, Path, str]:
    """The branch advanced beyond its upstream but all work reached main."""
    _remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    git(worktree, "push", "--quiet", "-u", "origin", "feature/demo")
    (worktree / "change.txt").write_text("landed change\n", encoding="utf-8")
    git(worktree, "add", "change.txt")
    git(worktree, "commit", "--quiet", "-m", "landed change")
    head = git(worktree, "rev-parse", "HEAD").stdout.strip()
    git(clone, "merge", "--quiet", "--no-edit", "feature/demo")
    git(clone, "push", "--quiet", "origin", "main")
    assert git(clone, "rev-parse", "origin/feature/demo").stdout.strip() != head
    assert git(clone, "rev-parse", "origin/main").stdout.strip() == head
    return clone, worktree, head


def prepare_interrupted_retirement(clone: Path, worktree: Path, head: str) -> Path:
    synthesis_home = worktree.parent.parent / "synthesis-home"
    runtime = synthesis_home / "repo-guard" / "retirement-runtime"
    runtime.mkdir(parents=True)
    digest = hashlib.sha256(CHECKPOINT_SCRIPT.read_bytes()).hexdigest()
    pinned = runtime / f"checkpoint-sync-{digest}.py"
    shutil.copy2(CHECKPOINT_SCRIPT, pinned)
    environment = dict(os.environ, SYNTHESIS_HOME=str(synthesis_home))
    prepared = subprocess.run(
        [sys.executable, str(pinned), "--prepare-worktree-retirement", str(worktree),
         "--retirement-repository", str(clone), "--retirement-head", head,
         "--retirement-remote", "origin", "--retirement-base", "origin/main",
         "--retirement-branch", "feature/demo", "--json"],
        env=environment, capture_output=True, text=True, check=False,
    )
    assert prepared.returncode == 0, prepared.stderr
    intent = Path(json.loads(prepared.stdout)[0]["detail"])
    git(clone, "worktree", "remove", str(worktree))
    return intent


def test_retirement_uses_verified_base_despite_stale_branch_upstream(tmp_path: Path) -> None:
    clone, worktree, _head = stale_upstream_worktree(tmp_path)
    remote_before = git(clone, "ls-remote", "--heads", "origin").stdout

    result = retire("--repository", str(clone), "--worktree", str(worktree),
                    "--base", "origin/main")

    assert result.returncode == 0, result.stderr
    assert not worktree.exists()
    assert not git(clone, "branch", "--list", "feature/demo").stdout.strip()
    assert "branch.feature/demo" not in git(clone, "config", "--local", "--list").stdout
    assert git(clone, "ls-remote", "--heads", "origin").stdout == remote_before


def test_resumed_retirement_uses_intent_base_despite_stale_upstream(tmp_path: Path) -> None:
    clone, worktree, head = stale_upstream_worktree(tmp_path)
    intent = prepare_interrupted_retirement(clone, worktree, head)
    before = json.loads(intent.read_text())
    remote_before = git(clone, "ls-remote", "--heads", "origin").stdout

    result = retire("--repository", str(clone), "--worktree", str(worktree))

    assert result.returncode == 0, result.stderr
    assert "Resumed retirement" in result.stdout
    assert not git(clone, "branch", "--list", "feature/demo").stdout.strip()
    assert json.loads(intent.read_text())["base_oid"] == before["base_oid"]
    assert git(clone, "ls-remote", "--heads", "origin").stdout == remote_before


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


def test_branch_mismatch_refuses_named_and_detached_worktrees(tmp_path: Path) -> None:
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
    result = retire("--repository", str(clone), "--worktree", str(worktree),
                    "--branch", "feature/demo")
    assert result.returncode == 2
    assert "not the expected feature/demo" in result.stderr


@pytest.mark.parametrize("nested", [False, True])
def test_retires_verified_detached_worktree_without_branch_mutation(tmp_path, nested):
    _remote, clone = build_repo(tmp_path)
    driver = clone
    target = tmp_path / "worktrees" / "detached"
    if nested:
        driver = tmp_path / "driver"
        git(clone, "worktree", "add", "-b", "driver", str(driver))
        target = clone / ".claude" / "worktrees" / "detached"
    target.parent.mkdir(parents=True, exist_ok=True)
    git(clone, "worktree", "add", "--detach", str(target), "origin/main")
    git(clone, "fetch", "--quiet", "--prune", "origin")
    refs_before = git(clone, "for-each-ref", "--format=%(refname) %(objectname)").stdout
    config_before = (clone / ".git/config").read_bytes()

    result = retire("--repository", str(driver), "--worktree", str(target),
                    "--base", "origin/main", "--delete-remote")

    assert result.returncode == 0, result.stderr
    assert not target.exists()
    assert "detached" in result.stdout
    assert git(clone, "for-each-ref", "--format=%(refname) %(objectname)").stdout == refs_before
    assert (clone / ".git/config").read_bytes() == config_before
    repeated = retire("--repository", str(driver), "--worktree", str(target),
                      "--base", "origin/main", "--delete-remote")
    assert repeated.returncode == 0, repeated.stderr
    wrong_branch = retire("--repository", str(driver), "--worktree", str(target),
                          "--branch", "main", "--delete-remote")
    assert wrong_branch.returncode == 2
    assert "for detached HEAD, not main" in wrong_branch.stderr
    assert git(clone, "for-each-ref", "--format=%(refname) %(objectname)").stdout == refs_before


def test_unmerged_detached_worktree_is_preserved(tmp_path):
    _remote, clone = build_repo(tmp_path)
    target = tmp_path / "worktrees" / "detached"
    target.parent.mkdir(parents=True)
    git(clone, "worktree", "add", "--detach", str(target), "origin/main")
    (target / "unmerged.txt").write_text("retain detached work\n")
    git(target, "add", "unmerged.txt")
    git(target, "commit", "-m", "unmerged detached work")
    head = git(target, "rev-parse", "HEAD").stdout.strip()

    result = retire("--repository", str(clone), "--worktree", str(target),
                    "--base", "origin/main")

    assert result.returncode == 2
    assert "not fully contained" in result.stderr
    assert target.exists()
    assert git(target, "rev-parse", "HEAD").stdout.strip() == head


def test_no_fetch_escape_hatch_is_rejected(tmp_path: Path) -> None:
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
    assert result.returncode == 2
    assert "unrecognized arguments: --no-fetch" in result.stderr
    assert worktree.exists()


def test_local_verification_base_is_rejected(tmp_path: Path) -> None:
    _remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_merge(clone, worktree)

    result = retire(
        "--repository",
        str(clone),
        "--worktree",
        str(worktree),
        "--base",
        "HEAD",
    )

    assert result.returncode == 2
    assert "remote-tracking ref" in result.stderr
    # The refusal names the accepted form, the value received, and the name
    # the value resolved to — a bare "must be a remote-tracking ref" leaves
    # the caller guessing which of the three went wrong.
    assert "origin/main" in result.stderr
    assert "'HEAD'" in result.stderr
    assert "refs/heads/main" in result.stderr
    assert worktree.exists()


def test_ambiguous_short_base_refusal_carries_git_diagnosis(tmp_path: Path) -> None:
    _remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_merge(clone, worktree)
    # A local branch named origin/main shadows refs/remotes/origin/main. For
    # the short name, rev-parse --symbolic-full-name exits 0, prints nothing,
    # and reports the ambiguity only on stderr.
    git(clone, "branch", "origin/main")

    result = retire(
        "--repository",
        str(clone),
        "--worktree",
        str(worktree),
        "--base",
        "origin/main",
    )

    assert result.returncode == 2
    assert "remote-tracking ref" in result.stderr
    assert "'origin/main'" in result.stderr
    # The refusal carries git's own diagnosis and names the condition it
    # tested, rather than a cause the code never checked.
    assert "is ambiguous" in result.stderr
    assert "bare commit id" not in result.stderr
    # The accepted form it offers must not be the value it just refused.
    assert "for example refs/remotes/origin/main" in result.stderr
    assert worktree.exists()


def test_revision_expression_base_is_rejected(tmp_path: Path) -> None:
    _remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_merge(clone, worktree)

    result = retire(
        "--repository",
        str(clone),
        "--worktree",
        str(worktree),
        "--base",
        "HEAD~0",
    )

    assert result.returncode == 2
    assert "'HEAD~0'" in result.stderr
    # HEAD~0 resolves to a commit but rev-parse --symbolic-full-name has no
    # ref name to print for a revision expression.
    assert "not to a single ref name" in result.stderr
    assert "bare commit id" not in result.stderr
    assert worktree.exists()


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
    assert "retirement preparation or completion failed" in result.stderr
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


def test_staged_reconciler_survives_source_removal(
    tmp_path: Path, monkeypatch
) -> None:
    worktree = tmp_path / "target-worktree"
    target_local = worktree / "skills" / "synthesis-repo-guard" / "checkpoint_sync.py"
    target_local.parent.mkdir(parents=True)
    shutil.copy2(CHECKPOINT_SCRIPT, target_local)
    monkeypatch.setattr(MODULE, "CHECKPOINT_SYNC", target_local)
    monkeypatch.setattr(MODULE, "RETIREMENT_RUNTIME_DIR", tmp_path / "runtime")

    staged = MODULE.stage_reconciler()
    MODULE.verify_reconciler_interface(staged)
    expected = hashlib.sha256(target_local.read_bytes()).hexdigest()

    shutil.rmtree(worktree)
    assert staged.is_file()
    assert hashlib.sha256(staged.read_bytes()).hexdigest() == expected


def test_helper_invoked_from_target_completes_after_target_removal(
    tmp_path: Path,
) -> None:
    _remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    target_helper = (
        worktree
        / "skills"
        / "synthesis-project-management"
        / "scripts"
        / "retire_worktree.py"
    )
    target_reconciler = (
        worktree / "skills" / "synthesis-repo-guard" / "checkpoint_sync.py"
    )
    target_helper.parent.mkdir(parents=True)
    target_reconciler.parent.mkdir(parents=True)
    shutil.copy2(SCRIPT, target_helper)
    shutil.copy2(CHECKPOINT_SCRIPT, target_reconciler)
    retired = worktree / "change.txt"
    retired.write_text("change\n", encoding="utf-8")
    git(worktree, "add", ".")
    git(worktree, "commit", "--quiet", "-m", "change")
    git(worktree, "push", "--quiet", "-u", "origin", "feature/demo")
    git(clone, "merge", "--quiet", "--no-edit", "feature/demo")
    git(clone, "push", "--quiet", "origin", "main")

    synthesis_home = tmp_path / "synthesis-home"
    pending = synthesis_home / "repo-guard" / "pending"
    receipts = synthesis_home / "repo-guard" / "local-handoff"
    pending.mkdir(parents=True)
    receipts.mkdir(parents=True)
    session_id = "session-target-helper"
    name = hashlib.sha256(session_id.encode("utf-8")).hexdigest() + ".json"
    manifest = pending / name
    survivor = clone / "seed.txt"
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
    (receipts / name).write_text("{}\n", encoding="utf-8")
    environment = dict(os.environ)
    environment["SYNTHESIS_HOME"] = str(synthesis_home)

    result = subprocess.run(
        [
            sys.executable,
            str(target_helper),
            "--repository",
            str(clone),
            "--worktree",
            str(worktree),
        ],
        cwd=clone,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not worktree.exists()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["paths"] == [str(survivor)]
    intents = list((synthesis_home / "repo-guard" / "retired-worktrees").glob("*.json"))
    assert len(intents) == 1
    assert json.loads(intents[0].read_text(encoding="utf-8"))["state"] == "completed"


def test_helper_resumes_from_prepared_intent_after_interruption(
    tmp_path: Path,
) -> None:
    _remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_merge(clone, worktree)
    head = git(worktree, "rev-parse", "HEAD").stdout.strip()
    synthesis_home = worktree.parent.parent / "synthesis-home"
    pending = synthesis_home / "repo-guard" / "pending"
    pending.mkdir(parents=True)
    session_id = "session-interrupted-retirement"
    name = hashlib.sha256(session_id.encode("utf-8")).hexdigest() + ".json"
    manifest = pending / name
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": session_id,
                "paths": [str(worktree / "change.txt")],
                "remote_paths": [],
            }
        ),
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["SYNTHESIS_HOME"] = str(synthesis_home)
    digest = hashlib.sha256(CHECKPOINT_SCRIPT.read_bytes()).hexdigest()
    runtime = synthesis_home / "repo-guard" / "retirement-runtime"
    runtime.mkdir(parents=True)
    shutil.copy2(CHECKPOINT_SCRIPT, runtime / f"checkpoint-sync-{digest}.py")
    prepared = subprocess.run(
        [
            sys.executable,
            str(CHECKPOINT_SCRIPT),
            "--prepare-worktree-retirement",
            str(worktree),
            "--retirement-repository",
            str(clone),
            "--retirement-head",
            head,
            "--retirement-remote",
            "origin",
            "--retirement-base",
            "origin/main",
            "--retirement-branch",
            "feature/demo",
            "--json",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert prepared.returncode == 0, prepared.stderr
    intent = Path(json.loads(prepared.stdout)[0]["detail"])
    assert json.loads(intent.read_text(encoding="utf-8"))["state"] == "prepared"
    git(clone, "worktree", "remove", str(worktree))

    resumed = retire("--repository", str(clone), "--worktree", str(worktree))

    assert resumed.returncode == 0, resumed.stderr
    assert "Resumed retirement" in resumed.stdout
    assert not manifest.exists()
    assert json.loads(intent.read_text(encoding="utf-8"))["state"] == "completed"
    assert not git(clone, "branch", "--list", "feature/demo").stdout.strip()

    repeated = retire("--repository", str(clone), "--worktree", str(worktree))
    assert repeated.returncode == 0, repeated.stderr


def test_resume_uses_intent_pinned_reconciler_after_source_changes(
    tmp_path: Path, monkeypatch
) -> None:
    _remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_merge(clone, worktree)
    head = git(worktree, "rev-parse", "HEAD").stdout.strip()
    synthesis_home = worktree.parent.parent / "synthesis-home"
    state = synthesis_home / "repo-guard"
    pending = state / "pending"
    runtime = state / "retirement-runtime"
    retirements = state / "retired-worktrees"
    pending.mkdir(parents=True)
    runtime.mkdir(parents=True)
    session_id = "session-pinned-reconciler"
    name = hashlib.sha256(session_id.encode("utf-8")).hexdigest() + ".json"
    manifest = pending / name
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": session_id,
                "paths": [str(worktree / "change.txt")],
                "remote_paths": [],
            }
        ),
        encoding="utf-8",
    )
    digest = hashlib.sha256(CHECKPOINT_SCRIPT.read_bytes()).hexdigest()
    pinned = runtime / f"checkpoint-sync-{digest}.py"
    shutil.copy2(CHECKPOINT_SCRIPT, pinned)
    environment = dict(os.environ)
    environment["SYNTHESIS_HOME"] = str(synthesis_home)
    prepared = subprocess.run(
        [
            sys.executable,
            str(pinned),
            "--prepare-worktree-retirement",
            str(worktree),
            "--retirement-repository",
            str(clone),
            "--retirement-head",
            head,
            "--retirement-remote",
            "origin",
            "--retirement-base",
            "origin/main",
            "--retirement-branch",
            "feature/demo",
            "--json",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert prepared.returncode == 0, prepared.stderr
    intent = Path(json.loads(prepared.stdout)[0]["detail"])
    git(clone, "worktree", "remove", str(worktree))

    changed_source = tmp_path / "changed-checkpoint-sync.py"
    changed_source.write_text("raise SystemExit('wrong reconciler')\n", encoding="utf-8")
    monkeypatch.setattr(MODULE, "CHECKPOINT_SYNC", changed_source)
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending)
    monkeypatch.setattr(MODULE, "STATE_DIR", state)
    monkeypatch.setattr(MODULE, "LIFECYCLE_LOCK", state / "lifecycle.lock")
    monkeypatch.setattr(MODULE, "RETIREMENT_RUNTIME_DIR", runtime)
    monkeypatch.setattr(MODULE, "RETIREMENT_DIR", retirements)
    monkeypatch.setenv("SYNTHESIS_HOME", str(synthesis_home))

    result = MODULE.resume_retirement(
        clone, worktree, "feature/demo", "origin", delete_remote=False
    )

    assert result == 0
    assert not manifest.exists()
    assert json.loads(intent.read_text(encoding="utf-8"))["state"] == "completed"


def test_resume_refuses_remote_different_from_intent(tmp_path: Path) -> None:
    _remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_merge(clone, worktree)
    head = git(worktree, "rev-parse", "HEAD").stdout.strip()
    synthesis_home = worktree.parent.parent / "synthesis-home"
    pending = synthesis_home / "repo-guard" / "pending"
    pending.mkdir(parents=True)
    session_id = "session-remote-mismatch"
    name = hashlib.sha256(session_id.encode("utf-8")).hexdigest() + ".json"
    manifest = pending / name
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": session_id,
                "paths": [str(worktree / "change.txt")],
                "remote_paths": [],
            }
        ),
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["SYNTHESIS_HOME"] = str(synthesis_home)
    prepared = subprocess.run(
        [
            sys.executable,
            str(CHECKPOINT_SCRIPT),
            "--prepare-worktree-retirement",
            str(worktree),
            "--retirement-repository",
            str(clone),
            "--retirement-head",
            head,
            "--retirement-remote",
            "origin",
            "--retirement-base",
            "origin/main",
            "--retirement-branch",
            "feature/demo",
            "--json",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert prepared.returncode == 0, prepared.stderr
    git(clone, "worktree", "remove", str(worktree))

    result = retire(
        "--repository",
        str(clone),
        "--worktree",
        str(worktree),
        "--remote",
        "other",
    )

    assert result.returncode == 2
    assert "verified against origin, not other" in result.stderr
    assert manifest.exists()
    assert git(clone, "branch", "--list", "feature/demo").stdout.strip()


def test_remote_branch_advance_blocks_delete(tmp_path: Path) -> None:
    remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_merge(clone, worktree)
    expected_head = git(worktree, "rev-parse", "HEAD").stdout.strip()
    git(clone, "worktree", "remove", str(worktree))

    contender = tmp_path / "contender"
    subprocess.run(
        ["git", "clone", "--quiet", str(remote), str(contender)],
        check=True,
        capture_output=True,
    )
    git(contender, "config", "user.email", "test@example.com")
    git(contender, "config", "user.name", "Test")
    git(contender, "checkout", "--quiet", "-b", "feature/demo", "origin/feature/demo")
    (contender / "advanced.txt").write_text("advanced\n", encoding="utf-8")
    git(contender, "add", "advanced.txt")
    git(contender, "commit", "--quiet", "-m", "advanced")
    git(contender, "push", "--quiet", "origin", "feature/demo")
    advanced_head = git(contender, "rev-parse", "HEAD").stdout.strip()

    result = MODULE.cleanup_branch(
        clone,
        "feature/demo",
        "origin",
        expected_head,
        base_ref="refs/remotes/origin/main",
        base_oid=git(clone, "rev-parse", "origin/main").stdout.strip(),
        delete_remote=True,
    )

    assert result == 2
    remote_head = git(clone, "ls-remote", "--heads", "origin", "feature/demo").stdout
    assert remote_head.split()[0] == advanced_head


def test_local_branch_delete_failure_never_touches_remote(tmp_path: Path) -> None:
    _remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    (worktree / "unmerged.txt").write_text("unmerged\n", encoding="utf-8")
    git(worktree, "add", "unmerged.txt")
    git(worktree, "commit", "--quiet", "-m", "unmerged")
    git(worktree, "push", "--quiet", "-u", "origin", "feature/demo")
    expected_head = git(worktree, "rev-parse", "HEAD").stdout.strip()
    git(clone, "worktree", "remove", str(worktree))
    git(clone, "branch", "--unset-upstream", "feature/demo")

    result = MODULE.cleanup_branch(
        clone,
        "feature/demo",
        "origin",
        expected_head,
        base_ref="refs/remotes/origin/main",
        base_oid=git(clone, "rev-parse", "origin/main").stdout.strip(),
        delete_remote=True,
    )

    assert result == 2
    remote_head = git(clone, "ls-remote", "--heads", "origin", "feature/demo").stdout
    assert remote_head.split()[0] == expected_head


def test_remote_delete_uses_compare_and_delete_lease(monkeypatch, tmp_path: Path) -> None:
    expected_head = "a" * 40
    calls: list[tuple[str, ...]] = []

    def fake_run(_repository: Path, *arguments: str, timeout: int = 60):
        del timeout
        calls.append(arguments)
        if arguments[:2] == ("check-ref-format", "--branch"):
            return subprocess.CompletedProcess(arguments, 0, "feature/demo\n", "")
        if arguments[0] in {"check-ref-format", "merge-base"}:
            return subprocess.CompletedProcess(arguments, 0, "", "")
        if arguments[:2] == ("rev-parse", "--verify"):
            return subprocess.CompletedProcess(arguments, 0, f"{expected_head}\n", "")
        if arguments[:3] == ("show-ref", "--verify", "--quiet"):
            return subprocess.CompletedProcess(arguments, 1, "", "")
        if arguments[:2] == ("ls-remote", "--heads"):
            return subprocess.CompletedProcess(
                arguments, 0, f"{expected_head}\trefs/heads/feature/demo\n", ""
            )
        if arguments[0] == "push":
            return subprocess.CompletedProcess(arguments, 0, "", "")
        raise AssertionError(arguments)

    monkeypatch.setattr(MODULE, "run", fake_run)
    monkeypatch.setattr(MODULE, "delete_local_branch", lambda *args, **kwargs: None)

    result = MODULE.cleanup_branch(
        tmp_path,
        "feature/demo",
        "origin",
        expected_head,
        base_ref="refs/remotes/origin/main",
        base_oid=expected_head,
        delete_remote=True,
    )

    assert result == 0
    push = next(arguments for arguments in calls if arguments[0] == "push")
    assert push == (
        "push",
        f"--force-with-lease=refs/heads/feature/demo:{expected_head}",
        "origin",
        ":refs/heads/feature/demo",
    )


def test_local_branch_advance_at_delete_boundary_keeps_branch_and_remote(tmp_path, monkeypatch):
    clone, worktree, head = stale_upstream_worktree(tmp_path)
    git(clone, "worktree", "remove", str(worktree))
    remote_before = git(clone, "ls-remote", "--heads", "origin").stdout
    config_before = (clone / ".git/config").read_bytes()
    tree = git(clone, "rev-parse", f"{head}^{{tree}}").stdout.strip()
    advanced = git(clone, "commit-tree", tree, "-p", head, "-m", "concurrent work").stdout.strip()
    original = MODULE.delete_local_branch

    def advance_then_delete(*args, **kwargs):
        git(clone, "update-ref", "refs/heads/feature/demo", advanced, head)
        return original(*args, **kwargs)

    monkeypatch.setattr(MODULE, "delete_local_branch", advance_then_delete)
    result = MODULE.cleanup_branch(clone, "feature/demo", "origin", head,
        base_ref="refs/remotes/origin/main", base_oid=head, delete_remote=True)

    assert result == 2
    assert git(clone, "rev-parse", "feature/demo").stdout.strip() == advanced
    assert (clone / ".git/config").read_bytes() == config_before
    assert git(clone, "ls-remote", "--heads", "origin").stdout == remote_before


def test_config_lock_contention_preserves_local_branch_and_config(tmp_path):
    clone, worktree, head = stale_upstream_worktree(tmp_path)
    git(clone, "worktree", "remove", str(worktree))
    config_before = (clone / ".git/config").read_bytes()
    lock = clone / ".git/config.lock"
    lock.write_text("foreign lock\n")

    result = MODULE.cleanup_branch(clone, "feature/demo", "origin", head,
        base_ref="refs/remotes/origin/main", base_oid=head, delete_remote=True)

    assert result == 2
    assert git(clone, "rev-parse", "feature/demo").stdout.strip() == head
    assert (clone / ".git/config").read_bytes() == config_before
    assert lock.read_text() == "foreign lock\n"


@pytest.mark.parametrize("kind", ["checked-out", "symbolic", "ref-locked", "wrong-base"])
def test_branch_cleanup_retains_unverified_local_state(tmp_path, kind, capsys):
    clone, worktree, head = stale_upstream_worktree(tmp_path)
    if kind != "checked-out":
        git(clone, "worktree", "remove", str(worktree))
    if kind == "symbolic":
        git(clone, "symbolic-ref", "refs/heads/feature/demo", "refs/heads/main")
    elif kind == "ref-locked":
        (clone / ".git/refs/heads/feature/demo.lock").write_text("foreign ref lock\n")
    base = git(clone, "rev-parse", f"{head}~1").stdout.strip() if kind == "wrong-base" else head
    config_before = (clone / ".git/config").read_bytes()
    remote_before = git(clone, "ls-remote", "--heads", "origin").stdout

    result = MODULE.cleanup_branch(clone, "feature/demo", "origin", head,
        base_ref="refs/remotes/origin/main", base_oid=base, delete_remote=True)

    assert result == 2
    assert git(clone, "rev-parse", "feature/demo").stdout.strip() == head
    assert (clone / ".git/config").read_bytes() == config_before
    assert git(clone, "ls-remote", "--heads", "origin").stdout == remote_before
    if kind == "wrong-base":
        assert f"pinned base refs/remotes/origin/main at {base}" in capsys.readouterr().err
    if kind == "ref-locked":
        assert (clone / ".git/refs/heads/feature/demo.lock").read_text() == "foreign ref lock\n"


@pytest.mark.parametrize("operation", ["worktree-add", "switch"])
def test_native_delete_refuses_checkout_created_after_helper_snapshot(tmp_path, monkeypatch, operation):
    clone, worktree, head = stale_upstream_worktree(tmp_path)
    git(clone, "worktree", "remove", str(worktree))
    original_entries = MODULE.worktree_entries
    checkout = tmp_path / "concurrent-checkout" if operation == "worktree-add" else clone
    injected = False

    def snapshot_then_checkout(repository):
        nonlocal injected
        entries = original_entries(repository)
        if not injected:
            injected = True
            if operation == "worktree-add":
                git(clone, "worktree", "add", str(checkout), "feature/demo")
            else:
                git(clone, "switch", "feature/demo")
        return entries

    monkeypatch.setattr(MODULE, "worktree_entries", snapshot_then_checkout)
    config_before = (clone / ".git/config").read_bytes()
    result = MODULE.cleanup_branch(clone, "feature/demo", "origin", head,
        base_ref="refs/remotes/origin/main", base_oid=head, delete_remote=False)

    assert injected
    assert result == 2
    assert git(clone, "rev-parse", "refs/heads/feature/demo").stdout.strip() == head
    assert git(checkout, "rev-parse", "HEAD").stdout.strip() == head
    assert (clone / ".git/config").read_bytes() == config_before
    assert not git(clone, "for-each-ref", "refs/synthesis-retirement/").stdout.strip()


def test_native_delete_uses_pinned_base_if_branch_and_remote_base_advance(tmp_path, monkeypatch):
    clone, worktree, head = stale_upstream_worktree(tmp_path)
    git(clone, "worktree", "remove", str(worktree))
    tree = git(clone, "rev-parse", f"{head}^{{tree}}").stdout.strip()
    advanced = git(clone, "commit-tree", tree, "-p", head, "-m", "concurrent work").stdout.strip()
    original_run = MODULE.run
    config_before = (clone / ".git/config").read_bytes()
    injected = False

    def advance_before_native_delete(repository, *arguments, **kwargs):
        nonlocal injected
        if arguments[-4:] == ("branch", "-d", "--", "feature/demo"):
            injected = True
            # HEAD and the mutable remote-tracking base both include the new
            # commit. Only the immutable pin can make native deletion refuse.
            for ref in ("refs/heads/feature/demo", "refs/heads/main", "refs/remotes/origin/main"):
                git(clone, "update-ref", ref, advanced, head)
        return original_run(repository, *arguments, **kwargs)

    monkeypatch.setattr(MODULE, "run", advance_before_native_delete)
    result = MODULE.cleanup_branch(clone, "feature/demo", "origin", head,
        base_ref="refs/remotes/origin/main", base_oid=head, delete_remote=True)

    assert injected
    assert result == 2
    assert git(clone, "rev-parse", "feature/demo").stdout.strip() == advanced
    assert (clone / ".git/config").read_bytes() == config_before
    assert not git(clone, "for-each-ref", "refs/synthesis-retirement/").stdout.strip()


@pytest.mark.parametrize("upstream", ["remote", "local", "none", "multiple"])
def test_native_base_selection_handles_upstream_variants_without_persistent_override(tmp_path, upstream):
    clone, worktree, head = stale_upstream_worktree(tmp_path)
    git(clone, "worktree", "remove", str(worktree))
    if upstream == "local":
        git(clone, "config", "branch.feature/demo.remote", ".")
    elif upstream == "none":
        git(clone, "branch", "--unset-upstream", "feature/demo")
    elif upstream == "multiple":
        git(clone, "config", "--add", "branch.feature/demo.merge", "refs/heads/main")
    config = clone / ".git/config"
    prefix = config.read_bytes().split(b'[branch "feature/demo"]', 1)[0]
    sentinel = b'[safety]\n\t# Retain exact unrelated formatting.\n\tmarker = unchanged\n'
    with config.open("ab") as handle:
        handle.write(sentinel)

    result = MODULE.cleanup_branch(clone, "feature/demo", "origin", head,
        base_ref="refs/remotes/origin/main", base_oid=head, delete_remote=False)

    assert result == 0
    assert not git(clone, "branch", "--list", "feature/demo").stdout.strip()
    assert config.read_bytes() == prefix + sentinel
    assert not git(clone, "for-each-ref", "refs/synthesis-retirement/").stdout.strip()


def test_native_base_pin_cleanup_cannot_delete_a_changed_pin(tmp_path, monkeypatch):
    clone, worktree, head = stale_upstream_worktree(tmp_path)
    git(clone, "worktree", "remove", str(worktree))
    seed = git(clone, "rev-parse", f"{head}~1").stdout.strip()
    original_run = MODULE.run
    changed = []

    def replace_before_pin_cleanup(repository, *arguments, **kwargs):
        if arguments[:2] == ("update-ref", "-d") and arguments[2].startswith("refs/synthesis-retirement/"):
            git(clone, "update-ref", arguments[2], seed, head)
            changed.append(arguments[2])
        return original_run(repository, *arguments, **kwargs)

    monkeypatch.setattr(MODULE, "run", replace_before_pin_cleanup)
    result = MODULE.cleanup_branch(clone, "feature/demo", "origin", head,
        base_ref="refs/remotes/origin/main", base_oid=head, delete_remote=False)

    assert result == 2
    assert len(changed) == 1
    assert git(clone, "rev-parse", changed[0]).stdout.strip() == seed


def behind_main_clone(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A merged feature whose main checkout sits one merge behind origin."""
    remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_merge(clone, worktree)
    git(clone, "reset", "--quiet", "--hard", "HEAD~1")
    return remote, clone, worktree


def test_retirement_advances_behind_main_worktree(tmp_path: Path) -> None:
    """Defect 3: retirement lands the main checkout too, not just origin."""
    remote, clone, worktree = behind_main_clone(tmp_path)
    behind = git(clone, "rev-parse", "HEAD").stdout.strip()
    base = git(clone, "rev-parse", "origin/main").stdout.strip()
    assert behind != base

    result = retire("--repository", str(clone), "--worktree", str(worktree))

    assert result.returncode == 0, result.stderr
    assert "Advanced main worktree" in result.stdout
    assert git(clone, "rev-parse", "HEAD").stdout.strip() == base
    assert not worktree.exists()


def test_retirement_refuses_dirty_main_worktree(tmp_path: Path) -> None:
    remote, clone, worktree = behind_main_clone(tmp_path)
    (clone / "uncommitted.txt").write_text("work in progress\n", encoding="utf-8")

    result = retire("--repository", str(clone), "--worktree", str(worktree))

    assert result.returncode == 2
    assert "uncommitted changes" in result.stderr
    assert worktree.exists()
    assert (clone / "uncommitted.txt").is_file()


def test_retirement_refuses_ahead_main_worktree(tmp_path: Path) -> None:
    remote, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    commit_and_merge(clone, worktree)
    (clone / "local-only.txt").write_text("unpushed\n", encoding="utf-8")
    git(clone, "add", "local-only.txt")
    git(clone, "commit", "--quiet", "-m", "local only")

    result = retire("--repository", str(clone), "--worktree", str(worktree))

    assert result.returncode == 2
    assert "ahead of" in result.stderr
    assert worktree.exists()


def test_retirement_refuses_diverged_main_worktree(tmp_path: Path) -> None:
    remote, clone, worktree = behind_main_clone(tmp_path)
    (clone / "diverged.txt").write_text("other line\n", encoding="utf-8")
    git(clone, "add", "diverged.txt")
    git(clone, "commit", "--quiet", "-m", "diverged")

    result = retire("--repository", str(clone), "--worktree", str(worktree))

    assert result.returncode == 2
    assert "cannot fast-forward" in result.stderr
    assert worktree.exists()


def test_retirement_leaves_main_on_other_branch_alone(tmp_path: Path) -> None:
    remote, clone, worktree = behind_main_clone(tmp_path)
    git(clone, "checkout", "--quiet", "-b", "other-work")
    before = git(clone, "rev-parse", "HEAD").stdout.strip()

    result = retire("--repository", str(clone), "--worktree", str(worktree))

    assert result.returncode == 0, result.stderr
    assert "leaving it alone" in result.stdout
    assert git(clone, "rev-parse", "HEAD").stdout.strip() == before
    assert git(clone, "branch", "--show-current").stdout.strip() == "other-work"
    assert not worktree.exists()
