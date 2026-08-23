from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("checkpoint_sync.py")
SPEC = importlib.util.spec_from_file_location("checkpoint_sync", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def command(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        list(args), cwd=cwd, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def repository(tmp_path: Path) -> tuple[Path, Path, dict]:
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    command("git", "init", "--bare", "-q", str(remote))
    command("git", "clone", "-q", str(remote), str(repo))
    command("git", "config", "user.name", "Test", cwd=repo)
    command("git", "config", "user.email", "test@example.com", cwd=repo)
    context = repo / "projects" / "alpha" / "CONTEXT.md"
    context.parent.mkdir(parents=True)
    context.write_text("one\n", encoding="utf-8")
    unrelated = repo / "unrelated.md"
    unrelated.write_text("one\n", encoding="utf-8")
    command("git", "add", "projects/alpha/CONTEXT.md", "unrelated.md", cwd=repo)
    command("git", "commit", "-qm", "seed", cwd=repo)
    branch = command("git", "branch", "--show-current", cwd=repo)
    command("git", "push", "-qu", "origin", branch, cwd=repo)
    cfg = {
        **MODULE.DEFAULTS,
        "repos": [str(repo)],
        "allowed_remote_prefixes": [str(tmp_path)],
    }
    return repo, remote, cfg


def test_resolve_config_accepts_current_schema_without_legacy_timers(
    tmp_path: Path,
) -> None:
    config = tmp_path / "checkpoint-sync.yaml"
    config.write_text("repos: []\nrepo_globs: []\n", encoding="utf-8")

    resolved = MODULE.resolve_config(config)

    assert resolved["repos"] == []
    assert "quiescence_minutes" not in resolved
    assert "throttle_minutes" not in resolved


def test_explicit_checkpoint_commits_only_session_paths(tmp_path: Path) -> None:
    repo, _remote, cfg = repository(tmp_path)
    context = repo / "projects" / "alpha" / "CONTEXT.md"
    unrelated = repo / "unrelated.md"
    context.write_text("two\n", encoding="utf-8")
    unrelated.write_text("two\n", encoding="utf-8")

    result = MODULE.checkpoint_explicit_paths(repo, [context], cfg, dry_run=False)

    assert result["action"] == "committed-pushed"
    assert command("git", "show", "HEAD:projects/alpha/CONTEXT.md", cwd=repo) == "two"
    assert command("git", "show", "HEAD:unrelated.md", cwd=repo) == "one"
    status = command("git", "status", "--porcelain", cwd=repo)
    assert "unrelated.md" in status


def test_configured_identity_accepts_feature_worktree(tmp_path: Path) -> None:
    repo, _remote, cfg = repository(tmp_path)
    worktree = tmp_path / "worktree"
    command("git", "worktree", "add", "-qb", "feature/test", str(worktree), cwd=repo)

    ok, detail = MODULE.configured_repo_identity(worktree, cfg)

    assert ok, detail


def test_new_branch_is_published_and_manifest_is_removed(tmp_path: Path, monkeypatch) -> None:
    repo, _remote, cfg = repository(tmp_path)
    command("git", "switch", "-qc", "feature/new", cwd=repo)
    context = repo / "projects" / "alpha" / "CONTEXT.md"
    context.write_text("branch\n", encoding="utf-8")
    pending = tmp_path / "state" / "pending"
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending)
    pending.mkdir(parents=True)
    manifest = MODULE.pending_manifest_path("session-a")
    manifest.write_text(
        json.dumps({"schema_version": 1, "session_id": "session-a", "paths": [str(context)]}),
        encoding="utf-8",
    )

    results, observed = MODULE.flush_all_pending(cfg, dry_run=False)

    assert observed == [manifest]
    assert results[0]["action"] == "committed-pushed"
    assert not manifest.exists()
    assert command("git", "show-ref", "--verify", "refs/remotes/origin/feature/new", cwd=repo)


def test_exact_session_flush_ignores_and_preserves_unrelated_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    repo, _remote, cfg = repository(tmp_path)
    context = repo / "projects" / "alpha" / "CONTEXT.md"
    context.write_text("scoped\n", encoding="utf-8")
    pending = tmp_path / "state" / "pending"
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending)
    pending.mkdir(parents=True)
    selected = MODULE.pending_manifest_path("session-selected")
    selected.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": "session-selected",
                "paths": [str(context)],
                "remote_paths": [str(context)],
            }
        ),
        encoding="utf-8",
    )
    unrelated = MODULE.pending_manifest_path("session-unrelated")
    unrelated.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": "session-unrelated",
                "paths": [str(tmp_path / "unavailable" / "missing.md")],
                "remote_paths": [],
            }
        ),
        encoding="utf-8",
    )

    results, observed = MODULE.flush_pending_session(
        cfg, "session-selected", dry_run=False
    )

    assert observed == [selected]
    assert not any(result.get("alert") for result in results)
    assert not selected.exists()
    assert unrelated.exists()
    assert command("git", "show", "HEAD:projects/alpha/CONTEXT.md", cwd=repo) == "scoped"


def test_exact_session_dry_run_preserves_all_manifests(
    tmp_path: Path, monkeypatch
) -> None:
    repo, _remote, cfg = repository(tmp_path)
    context = repo / "projects" / "alpha" / "CONTEXT.md"
    context.write_text("preview\n", encoding="utf-8")
    pending = tmp_path / "state" / "pending"
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending)
    pending.mkdir(parents=True)
    selected = MODULE.pending_manifest_path("session-preview")
    selected.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": "session-preview",
                "paths": [str(context)],
                "remote_paths": [str(context)],
            }
        ),
        encoding="utf-8",
    )
    unrelated = MODULE.pending_manifest_path("session-other")
    unrelated.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": "session-other",
                "paths": [str(context)],
                "remote_paths": [str(context)],
            }
        ),
        encoding="utf-8",
    )

    results, observed = MODULE.flush_pending_session(
        cfg, "session-preview", dry_run=True
    )

    assert observed == [selected]
    assert not any(result.get("alert") for result in results)
    assert selected.exists()
    assert unrelated.exists()


def test_exact_session_flush_rejects_manifest_identity_mismatch(
    tmp_path: Path, monkeypatch
) -> None:
    _repo, _remote, cfg = repository(tmp_path)
    pending = tmp_path / "state" / "pending"
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending)
    pending.mkdir(parents=True)
    selected = MODULE.pending_manifest_path("session-expected")
    selected.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": "session-different",
                "paths": [],
                "remote_paths": [],
            }
        ),
        encoding="utf-8",
    )

    results, observed = MODULE.flush_pending_session(
        cfg, "session-expected", dry_run=False
    )

    assert observed == []
    assert results[0]["action"] == "failed"
    assert "mismatch" in results[0]["alert"]
    assert selected.exists()


def test_exact_session_flush_rejects_blank_or_oversized_identity(
    tmp_path: Path, monkeypatch
) -> None:
    _repo, _remote, cfg = repository(tmp_path)
    pending = tmp_path / "state" / "pending"
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending)

    blank_results, blank_manifests = MODULE.flush_pending_session(
        cfg, "   ", dry_run=False
    )
    large_results, large_manifests = MODULE.flush_pending_session(
        cfg, "é" * 257, dry_run=False
    )

    assert blank_manifests == []
    assert blank_results[0]["action"] == "failed"
    assert large_manifests == []
    assert large_results[0]["action"] == "failed"
    assert not pending.exists()


def test_local_handoff_records_evidence_without_committing_or_pushing(
    tmp_path: Path, monkeypatch
) -> None:
    repo, _remote, cfg = repository(tmp_path)
    context = repo / "projects" / "alpha" / "CONTEXT.md"
    context.write_text("local only\n", encoding="utf-8")
    pending = tmp_path / "state" / "pending"
    receipts = tmp_path / "state" / "local-handoff"
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending)
    monkeypatch.setattr(MODULE, "LOCAL_HANDOFF_DIR", receipts)
    pending.mkdir(parents=True)
    manifest = MODULE.pending_manifest_path("session-local")
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "session_id": "session-local",
                "paths": [str(context)],
            }
        ),
        encoding="utf-8",
    )
    before = command("git", "rev-parse", "HEAD", cwd=repo)

    results, observed = MODULE.local_handoff_checkpoint(
        {"session_id": "session-local", "cwd": str(repo)}, cfg
    )

    assert observed == manifest
    assert results[0]["action"] == "local-ready"
    assert command("git", "rev-parse", "HEAD", cwd=repo) == before
    assert "CONTEXT.md" in command("git", "status", "--porcelain", cwd=repo)
    assert manifest.exists()
    receipt = next(receipts.glob("*.json"))
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["readiness"] == "LOCAL_READY"
    assert payload["results"][0]["file_evidence"][0]["sha256"]


def test_local_handoff_rejects_dangling_manifest_symlink(
    tmp_path: Path, monkeypatch
) -> None:
    _repo, _remote, cfg = repository(tmp_path)
    pending = tmp_path / "state" / "pending"
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending)
    pending.mkdir(parents=True)
    MODULE.pending_manifest_path("session-symlink").symlink_to(tmp_path / "missing")

    results, _manifest = MODULE.local_handoff_checkpoint(
        {"session_id": "session-symlink", "cwd": str(tmp_path)}, cfg
    )

    assert results[0]["action"] == "failed"
    assert "symlink" in results[0]["alert"]


def test_reconcile_retired_worktree_repairs_prior_removal(
    tmp_path: Path, monkeypatch
) -> None:
    repo, _remote, _cfg = repository(tmp_path)
    worktree = tmp_path / "retired-worktree"
    command("git", "worktree", "add", "-qb", "feature/retired", str(worktree), cwd=repo)
    retired_path = worktree / "change.txt"
    retired_path.write_text("change\n", encoding="utf-8")
    command("git", "add", "change.txt", cwd=worktree)
    command("git", "commit", "-qm", "change", cwd=worktree)
    head = command("git", "rev-parse", "HEAD", cwd=worktree)
    command("git", "merge", "-q", "--no-edit", "feature/retired", cwd=repo)
    branch = command("git", "branch", "--show-current", cwd=repo)
    command("git", "push", "-q", "origin", branch, cwd=repo)

    pending = tmp_path / "state" / "pending"
    receipts = tmp_path / "state" / "local-handoff"
    retirements = tmp_path / "state" / "retired-worktrees"
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending)
    monkeypatch.setattr(MODULE, "LOCAL_HANDOFF_DIR", receipts)
    monkeypatch.setattr(MODULE, "RETIREMENT_DIR", retirements)
    pending.mkdir(parents=True)
    receipts.mkdir(parents=True)
    manifest = MODULE.pending_manifest_path("session-retired")
    survivor = repo / "projects" / "alpha" / "CONTEXT.md"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": "session-retired",
                "paths": [str(retired_path), str(survivor)],
                "remote_paths": [str(survivor)],
            }
        ),
        encoding="utf-8",
    )
    receipt = receipts / manifest.name
    receipt.write_text("{}\n", encoding="utf-8")
    command("git", "worktree", "remove", str(worktree), cwd=repo)

    results, touched = MODULE.reconcile_retired_worktree(
        worktree, repo, head, "origin/main", dry_run=False
    )

    assert results[0]["action"] == "retired-worktree-reconciled"
    assert touched == [manifest]
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["paths"] == [str(survivor)]
    assert not receipt.exists()
    assert len(list(retirements.glob("*.json"))) == 1


def test_reconcile_retired_worktree_removes_retired_only_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    repo, _remote, _cfg = repository(tmp_path)
    worktree = tmp_path / "retired-only-worktree"
    command("git", "worktree", "add", "-qb", "feature/retired-only", str(worktree), cwd=repo)
    retired_path = worktree / "change.txt"
    retired_path.write_text("change\n", encoding="utf-8")
    command("git", "add", "change.txt", cwd=worktree)
    command("git", "commit", "-qm", "change", cwd=worktree)
    head = command("git", "rev-parse", "HEAD", cwd=worktree)
    command("git", "merge", "-q", "--no-edit", "feature/retired-only", cwd=repo)
    branch = command("git", "branch", "--show-current", cwd=repo)
    command("git", "push", "-q", "origin", branch, cwd=repo)

    pending = tmp_path / "state" / "pending"
    receipts = tmp_path / "state" / "local-handoff"
    retirements = tmp_path / "state" / "retired-worktrees"
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending)
    monkeypatch.setattr(MODULE, "LOCAL_HANDOFF_DIR", receipts)
    monkeypatch.setattr(MODULE, "RETIREMENT_DIR", retirements)
    pending.mkdir(parents=True)
    receipts.mkdir(parents=True)
    manifest = MODULE.pending_manifest_path("session-retired-only")
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": "session-retired-only",
                "paths": [str(retired_path)],
                "remote_paths": [str(retired_path)],
            }
        ),
        encoding="utf-8",
    )
    receipt = receipts / manifest.name
    receipt.write_text("{}\n", encoding="utf-8")
    command("git", "worktree", "remove", str(worktree), cwd=repo)

    results, touched = MODULE.reconcile_retired_worktree(
        worktree, repo, head, "origin/main", dry_run=False
    )

    assert results[0]["action"] == "retired-worktree-reconciled"
    assert touched == [manifest]
    assert not manifest.exists()
    assert not receipt.exists()
    assert len(list(retirements.glob("*.json"))) == 1


def test_reconcile_retired_worktree_refuses_unpublished_head(
    tmp_path: Path, monkeypatch
) -> None:
    repo, _remote, _cfg = repository(tmp_path)
    worktree = tmp_path / "unpublished-worktree"
    command("git", "worktree", "add", "-qb", "feature/unpublished", str(worktree), cwd=repo)
    retired_path = worktree / "change.txt"
    retired_path.write_text("change\n", encoding="utf-8")
    command("git", "add", "change.txt", cwd=worktree)
    command("git", "commit", "-qm", "change", cwd=worktree)
    head = command("git", "rev-parse", "HEAD", cwd=worktree)
    pending = tmp_path / "state" / "pending"
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending)
    pending.mkdir(parents=True)
    manifest = MODULE.pending_manifest_path("session-unpublished")
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": "session-unpublished",
                "paths": [str(retired_path)],
                "remote_paths": [],
            }
        ),
        encoding="utf-8",
    )
    command("git", "worktree", "remove", str(worktree), cwd=repo)

    results, touched = MODULE.reconcile_retired_worktree(
        worktree, repo, head, "origin/main", dry_run=False
    )

    assert results[0]["action"] == "retirement-reconcile-failed"
    assert "not contained" in results[0]["alert"]
    assert touched == []
    assert manifest.exists()


def test_retirement_intent_resumes_after_removal_gap(tmp_path: Path, monkeypatch) -> None:
    repo, _remote, _cfg = repository(tmp_path)
    worktree = tmp_path / "resumable-worktree"
    command("git", "worktree", "add", "-qb", "feature/resumable", str(worktree), cwd=repo)
    retired_path = worktree / "change.txt"
    retired_path.write_text("change\n", encoding="utf-8")
    command("git", "add", "change.txt", cwd=worktree)
    command("git", "commit", "-qm", "change", cwd=worktree)
    head = command("git", "rev-parse", "HEAD", cwd=worktree)
    command("git", "merge", "-q", "--no-edit", "feature/resumable", cwd=repo)
    branch = command("git", "branch", "--show-current", cwd=repo)
    command("git", "push", "-q", "origin", branch, cwd=repo)

    state = tmp_path / "state"
    pending = state / "pending"
    receipts = state / "local-handoff"
    retirements = state / "retired-worktrees"
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending)
    monkeypatch.setattr(MODULE, "LOCAL_HANDOFF_DIR", receipts)
    monkeypatch.setattr(MODULE, "RETIREMENT_DIR", retirements)
    pending.mkdir(parents=True)
    session_id = "session-resumable"
    manifest = MODULE.pending_manifest_path(session_id)
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": session_id,
                "paths": [str(retired_path)],
                "remote_paths": [],
            }
        ),
        encoding="utf-8",
    )

    with MODULE.lifecycle_lock():
        prepared, intent, _touched = MODULE.prepare_retirement_intent(
            worktree,
            repo,
            head,
            "origin",
            "origin/main",
            expect_active=True,
            dry_run=False,
        )
    assert prepared["action"] == "retirement-prepared"
    assert intent is not None
    assert json.loads(intent.read_text(encoding="utf-8"))["state"] == "prepared"

    command("git", "worktree", "remove", str(worktree), cwd=repo)
    with MODULE.lifecycle_lock():
        completed, touched = MODULE.complete_retirement_intent(intent)

    assert completed["action"] == "retired-worktree-reconciled"
    assert touched == [manifest]
    assert not manifest.exists()
    assert json.loads(intent.read_text(encoding="utf-8"))["state"] == "completed"


def test_retirement_completion_rejects_reconciler_digest_mismatch(
    tmp_path: Path, monkeypatch
) -> None:
    repo, _remote, _cfg = repository(tmp_path)
    worktree = tmp_path / "digest-mismatch-worktree"
    command("git", "worktree", "add", "-qb", "feature/digest", str(worktree), cwd=repo)
    changed = worktree / "change.txt"
    changed.write_text("change\n", encoding="utf-8")
    command("git", "add", "change.txt", cwd=worktree)
    command("git", "commit", "-qm", "change", cwd=worktree)
    head = command("git", "rev-parse", "HEAD", cwd=worktree)
    command("git", "merge", "-q", "--no-edit", "feature/digest", cwd=repo)
    branch = command("git", "branch", "--show-current", cwd=repo)
    command("git", "push", "-q", "origin", branch, cwd=repo)

    state = tmp_path / "state"
    monkeypatch.setattr(MODULE, "PENDING_DIR", state / "pending")
    monkeypatch.setattr(MODULE, "LOCAL_HANDOFF_DIR", state / "local-handoff")
    monkeypatch.setattr(MODULE, "RETIREMENT_DIR", state / "retired-worktrees")
    MODULE.PENDING_DIR.mkdir(parents=True)
    manifest = MODULE.pending_manifest_path("session-digest-mismatch")
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": "session-digest-mismatch",
                "paths": [str(changed)],
                "remote_paths": [],
            }
        ),
        encoding="utf-8",
    )

    with MODULE.lifecycle_lock():
        _prepared, intent, _touched = MODULE.prepare_retirement_intent(
            worktree,
            repo,
            head,
            "origin",
            "origin/main",
            expect_active=True,
            dry_run=False,
        )
    assert intent is not None
    payload = json.loads(intent.read_text(encoding="utf-8"))
    payload["reconciler_sha256"] = "0" * 64
    intent.write_text(json.dumps(payload), encoding="utf-8")
    command("git", "worktree", "remove", str(worktree), cwd=repo)

    with MODULE.lifecycle_lock():
        with pytest.raises(ValueError, match="pinned reconciler"):
            MODULE.complete_retirement_intent(intent)

    assert manifest.exists()


def test_retirement_recovery_rejects_local_base_ref(tmp_path: Path, monkeypatch) -> None:
    repo, _remote, _cfg = repository(tmp_path)
    worktree = tmp_path / "local-base-worktree"
    command("git", "worktree", "add", "-qb", "feature/local-base", str(worktree), cwd=repo)
    command("git", "worktree", "remove", str(worktree), cwd=repo)
    monkeypatch.setattr(MODULE, "PENDING_DIR", tmp_path / "state" / "pending")
    monkeypatch.setattr(MODULE, "LOCAL_HANDOFF_DIR", tmp_path / "state" / "local-handoff")
    monkeypatch.setattr(MODULE, "RETIREMENT_DIR", tmp_path / "state" / "retired-worktrees")
    head = command("git", "rev-parse", "HEAD", cwd=repo)

    results, touched = MODULE.reconcile_retired_worktree(
        worktree, repo, head, "HEAD", dry_run=False
    )

    assert results[0]["action"] == "retirement-reconcile-failed"
    assert "remote-tracking ref" in results[0]["alert"]
    assert touched == []


def test_lifecycle_lock_serializes_threads(tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / "state"
    monkeypatch.setattr(MODULE, "PENDING_DIR", state / "pending")
    monkeypatch.setattr(MODULE, "LOCAL_HANDOFF_DIR", state / "local-handoff")
    monkeypatch.setattr(MODULE, "RETIREMENT_DIR", state / "retired-worktrees")
    entered = threading.Event()

    def contender() -> None:
        with MODULE.lifecycle_lock():
            entered.set()

    with MODULE.lifecycle_lock():
        thread = threading.Thread(target=contender)
        thread.start()
        assert not entered.wait(0.1)
    thread.join(timeout=2)
    assert entered.is_set()


def test_lifecycle_lock_rejects_symlinked_state_ancestor(
    tmp_path: Path, monkeypatch
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    monkeypatch.setattr(MODULE, "PENDING_DIR", linked / "pending")
    monkeypatch.setattr(MODULE, "LOCAL_HANDOFF_DIR", linked / "local-handoff")
    monkeypatch.setattr(MODULE, "RETIREMENT_DIR", linked / "retired-worktrees")

    with pytest.raises(ValueError, match="symlink component"):
        with MODULE.lifecycle_lock():
            pass


def test_offline_push_preserves_local_commit_and_manifest(tmp_path: Path, monkeypatch) -> None:
    repo, remote, cfg = repository(tmp_path)
    context = repo / "projects" / "alpha" / "CONTEXT.md"
    context.write_text("offline\n", encoding="utf-8")
    command("git", "remote", "set-url", "origin", str(remote) + "-missing", cwd=repo)
    pending = tmp_path / "state" / "pending"
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending)
    pending.mkdir(parents=True)
    manifest = MODULE.pending_manifest_path("session-b")
    manifest.write_text(
        json.dumps({"schema_version": 1, "session_id": "session-b", "paths": [str(context)]}),
        encoding="utf-8",
    )

    results, _ = MODULE.flush_all_pending(cfg, dry_run=False)

    assert results[0]["action"] == "committed-no-push"
    assert results[0]["alert"]
    assert manifest.exists()
    assert command("git", "status", "--porcelain", cwd=repo) == ""


def test_remote_flush_commits_new_context_file_without_staged_collisions(
    tmp_path: Path, monkeypatch
) -> None:
    repo, _remote, cfg = repository(tmp_path)
    created = repo / "projects" / "alpha" / "resources" / "artifacts" / "plan.md"
    created.parent.mkdir(parents=True)
    created.write_text("plan\n", encoding="utf-8")
    unrelated = repo / "unrelated.md"
    unrelated.write_text("staged elsewhere\n", encoding="utf-8")
    command("git", "add", "unrelated.md", cwd=repo)
    pending = tmp_path / "state" / "pending"
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending)
    pending.mkdir(parents=True)
    manifest = MODULE.pending_manifest_path("session-new")
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": "session-new",
                "paths": [str(created)],
                "remote_paths": [str(created)],
            }
        ),
        encoding="utf-8",
    )

    results, _ = MODULE.flush_all_pending(cfg, dry_run=False)

    assert results[0]["action"] == "committed-pushed"
    assert command(
        "git", "show", "HEAD:projects/alpha/resources/artifacts/plan.md", cwd=repo
    ) == "plan"
    assert command("git", "diff", "--cached", "--name-only", cwd=repo) == "unrelated.md"


def test_remote_flush_waits_until_source_paths_are_published(
    tmp_path: Path, monkeypatch
) -> None:
    repo, _remote, cfg = repository(tmp_path)
    context = repo / "projects" / "alpha" / "CONTEXT.md"
    source = repo / "src" / "feature.py"
    source.parent.mkdir()
    source.write_text("one\n", encoding="utf-8")
    command("git", "add", "src/feature.py", cwd=repo)
    command("git", "commit", "-qm", "source seed", cwd=repo)
    branch = command("git", "branch", "--show-current", cwd=repo)
    command("git", "push", "-q", "origin", branch, cwd=repo)
    context.write_text("context two\n", encoding="utf-8")
    source.write_text("source two\n", encoding="utf-8")
    pending = tmp_path / "state" / "pending"
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending)
    pending.mkdir(parents=True)
    manifest = MODULE.pending_manifest_path("session-source")
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": "session-source",
                "paths": [str(context), str(source)],
                "remote_paths": [str(context)],
            }
        ),
        encoding="utf-8",
    )

    results, _ = MODULE.flush_all_pending(cfg, dry_run=False)

    assert any(result["action"] == "source-local-only" for result in results)
    assert manifest.exists()
    assert command("git", "show", "HEAD:projects/alpha/CONTEXT.md", cwd=repo) == "context two"


def test_existing_remote_branch_that_is_behind_blocks_readiness(
    tmp_path: Path,
) -> None:
    repo, remote, _cfg = repository(tmp_path)
    branch = command("git", "branch", "--show-current", cwd=repo)
    other = tmp_path / "other"
    command("git", "clone", "-q", "--no-checkout", str(remote), str(other))
    command("git", "switch", "-q", branch, cwd=other)
    command("git", "config", "user.name", "Other", cwd=other)
    command("git", "config", "user.email", "other@example.com", cwd=other)
    new_file = other / "new.md"
    new_file.write_text("remote\n", encoding="utf-8")
    command("git", "add", "new.md", cwd=other)
    command("git", "commit", "-qm", "remote", cwd=other)
    command("git", "push", "-q", "origin", branch, cwd=other)

    result = MODULE.finish_sync(
        repo, branch, {"repo": str(repo), "name": repo.name}, committed=False, dry_run=False
    )

    assert result["action"] == "behind"
    assert result["alert"]


def test_flush_rejects_symlinked_manifest_lock(tmp_path: Path, monkeypatch) -> None:
    _repo, _remote, cfg = repository(tmp_path)
    pending = tmp_path / "state" / "pending"
    pending.mkdir(parents=True)
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending)
    session_id = "session-lock"
    manifest = MODULE.pending_manifest_path(session_id)
    manifest.write_text(
        json.dumps({"session_id": session_id, "paths": []}), encoding="utf-8"
    )
    manifest.with_suffix(".lock").symlink_to(tmp_path / "elsewhere")

    results, observed = MODULE.flush_all_pending(cfg, dry_run=False)

    assert observed == []
    assert results[0]["action"] == "failed"
    assert manifest.exists()
