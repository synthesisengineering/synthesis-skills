from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).with_name("retire_worktree.py")
CHECKPOINT_SCRIPT = (
    SCRIPT.resolve().parents[2] / "synthesis-repo-guard" / "checkpoint_sync.py"
)
SPEC = importlib.util.spec_from_file_location("retire_worktree", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


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

    result = MODULE.cleanup_branch(
        tmp_path,
        "feature/demo",
        "origin",
        expected_head,
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
