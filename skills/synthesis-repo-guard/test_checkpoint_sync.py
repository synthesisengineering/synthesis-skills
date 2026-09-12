from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
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


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path: Path, monkeypatch):
    # Synthetic repositories and lifecycle events must never consult or update
    # the invoking developer's Git hooks, claims, receipts or state directory.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    state = tmp_path / "isolated-synthesis" / "repo-guard"
    for name, path in {
        "STATE_DIR": state, "STATE_FILE": state / "checkpoint-state.json",
        "PENDING_DIR": state / "pending", "LOCAL_HANDOFF_DIR": state / "local-handoff",
        "REMOTE_HANDOFF_STATE": state / "remote-handoff-last.json", "RETIREMENT_DIR": state / "retired-worktrees",
    }.items():
        monkeypatch.setattr(MODULE, name, path)
    monkeypatch.setattr(MODULE, "RETIRED_PENDING_DIR", state / "retired-pending")


def command(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        list(args), cwd=cwd, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def repository(tmp_path: Path) -> tuple[Path, Path, dict]:
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    # Retirement fixtures name origin/main; do not inherit a runner-specific
    # default branch when constructing their synthetic remote.
    command("git", "init", "--bare", "-q", "-b", "main", str(remote))
    command("git", "clone", "-q", str(remote), str(repo))
    hooks = tmp_path / "fixture-hooks"
    hooks.mkdir()
    command("git", "config", "core.hooksPath", str(hooks), cwd=repo)
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


@pytest.fixture
def orphaned_attribution(tmp_path: Path, monkeypatch):
    repo, remote, cfg = repository(tmp_path)
    worktree = tmp_path / "removed-worktree"
    command("git", "worktree", "add", "-qb", "feature/removed", str(worktree), cwd=repo)
    edited = worktree / "projects" / "alpha" / "CONTEXT.md"
    edited.write_text("retained bytes\n", encoding="utf-8")
    command("git", "add", "projects", cwd=worktree)
    command("git", "commit", "-qm", "Update records", cwd=worktree)
    command("git", "merge", "-q", "--no-edit", "feature/removed", cwd=repo)
    command("git", "push", "-q", "origin", "main", cwd=repo)
    state = tmp_path / "fixture-state"
    for name, suffix in (("STATE_DIR", ""), ("PENDING_DIR", "pending"),
                         ("LOCAL_HANDOFF_DIR", "local-handoff"), ("RETIREMENT_DIR", "retired-worktrees")):
        monkeypatch.setattr(MODULE, name, state / suffix)
    MODULE.PENDING_DIR.mkdir(parents=True)
    native = "018f0000-0000-7000-8000-000000000002"
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:" + native)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    own = MODULE.pending_manifest_path(native)
    own.write_text(json.dumps({"schema_version": 2, "session_id": native,
                              "paths": [str(edited)], "remote_paths": [str(edited)]}))
    MODULE.local_handoff_checkpoint({"session_id": native, "cwd": str(worktree)}, cfg)
    receipt = MODULE.LOCAL_HANDOFF_DIR / own.name
    assert json.loads(receipt.read_text())["readiness"] == "LOCAL_READY"
    foreign = MODULE.pending_manifest_path("foreign-session")
    foreign.write_bytes(b"foreign retained evidence, intentionally not parsed")
    command("git", "worktree", "remove", str(worktree), cwd=repo)
    command("git", "branch", "-d", "feature/removed", cwd=repo)
    return repo, worktree, native, own, receipt, foreign


def test_exact_session_recovery_uses_retained_bytes_and_ancestry(orphaned_attribution) -> None:
    repo, worktree, native, own, receipt, foreign = orphaned_attribution
    before = foreign.read_bytes()
    results, touched = MODULE.recover_retired_session(worktree, repo, native, "origin/main", dry_run=False)
    assert results[0]["action"] == "retired-worktree-reconciled"
    assert touched == [own]
    assert not own.exists() and not receipt.exists()
    assert foreign.read_bytes() == before
    # Re-entry uses the completed durable transaction after receipt removal.
    assert MODULE.recover_retired_session(worktree, repo, native, "origin/main", dry_run=False)[0][0]["action"] == "retired-worktree-reconciled"


@pytest.mark.parametrize("damage", ["missing_receipt", "wrong_session", "wrong_hash", "missing_head", "missing_path", "new_attribution", "legacy_unbound", "later_same_paths", "wrong_mode"])
def test_recovery_never_substitutes_canonical_file_existence_for_proof(orphaned_attribution, damage: str) -> None:
    repo, worktree, native, own, receipt, foreign = orphaned_attribution
    data = json.loads(receipt.read_text())
    if damage == "missing_receipt":
        receipt.unlink()
    elif damage == "wrong_session":
        data["session_id"] = "foreign-session"
    elif damage == "wrong_hash":
        data["results"][0]["file_evidence"][0]["sha256"] = "0" * 64
    elif damage == "missing_head":
        data["results"][0].pop("head")
    elif damage == "wrong_mode":
        data["results"][0]["file_evidence"][0]["git_mode"] = "100755"
    elif damage == "missing_path":
        data["results"][0]["file_evidence"] = []
    elif damage == "legacy_unbound":
        data.pop("pending_manifest_sha256")
    elif damage == "later_same_paths":
        manifest = json.loads(own.read_text())
        manifest["updated_at"] = "2026-09-09T23:59:59Z"
        own.write_text(json.dumps(manifest))
    else:
        manifest = json.loads(own.read_text())
        manifest["paths"].append(str(worktree / "unrelated.md"))
        own.write_text(json.dumps(manifest))
    if receipt.exists():
        receipt.write_text(json.dumps(data))
    retained = own.read_bytes(), foreign.read_bytes()
    results, _touched = MODULE.recover_retired_session(worktree, repo, native, "origin/main", dry_run=False)
    assert results[0]["alert"]
    assert (own.read_bytes(), foreign.read_bytes()) == retained


def test_retired_recovery_requires_exact_native_authority(orphaned_attribution, monkeypatch) -> None:
    repo, worktree, native, own, receipt, foreign = orphaned_attribution
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:018f0000-0000-7000-8000-000000000099")
    before = own.read_bytes(), receipt.read_bytes(), foreign.read_bytes()
    results, _ = MODULE.recover_retired_session(worktree, repo, native, "origin/main", dry_run=False)
    assert "authority" in results[0]["alert"]
    assert (own.read_bytes(), receipt.read_bytes(), foreign.read_bytes()) == before


@pytest.mark.parametrize("client", ["cc", "codex"])
def test_recovery_cli_uses_the_actual_parser_and_transaction(orphaned_attribution, monkeypatch, tmp_path: Path, client: str) -> None:
    repo, worktree, native, own, receipt, foreign = orphaned_attribution
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", f"{client}:{native}")
    if client == "cc":
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", native)
    config = tmp_path / "config.yaml"
    config.write_text("repos: []\n")
    arguments = [str(MODULE_PATH), "--config", str(config), "--reconcile-retired-worktree", str(worktree),
                 "--retirement-repository", str(repo), "--retirement-base", "origin/main",
                 "--retirement-session", native, "--json"]
    monkeypatch.setattr(sys, "argv", [*arguments, "--dry-run"])
    before = own.read_bytes(), receipt.read_bytes(), foreign.read_bytes()
    assert MODULE.main() == 0
    assert (own.read_bytes(), receipt.read_bytes(), foreign.read_bytes()) == before
    monkeypatch.setattr(sys, "argv", arguments)
    assert MODULE.main() == 0
    assert not own.exists() and not receipt.exists()
    assert foreign.read_bytes() == before[2]


def test_recovery_preserves_evidence_for_a_second_removed_worktree(orphaned_attribution, tmp_path: Path) -> None:
    repo, worktree, native, own, receipt, foreign = orphaned_attribution
    second = tmp_path / "second-removed-worktree"
    command("git", "worktree", "add", "-qb", "feature/first-again", str(worktree), cwd=repo)
    command("git", "worktree", "add", "-qb", "feature/second", str(second), cwd=repo)
    paths = [str(root / "projects" / "alpha" / "CONTEXT.md") for root in (worktree, second)]
    own.write_text(json.dumps({"schema_version": 2, "session_id": native, "paths": paths, "remote_paths": paths}))
    MODULE.local_handoff_checkpoint({"session_id": native, "cwd": str(worktree)}, MODULE.DEFAULTS)
    command("git", "worktree", "remove", str(worktree), cwd=repo)
    command("git", "worktree", "remove", str(second), cwd=repo)
    assert MODULE.recover_retired_session(worktree, repo, native, "origin/main", dry_run=False)[0][0]["alert"] is None
    assert own.exists() and receipt.exists()
    assert json.loads(own.read_text())["paths"] == [paths[1]]
    assert MODULE.recover_retired_session(second, repo, native, "origin/main", dry_run=False)[0][0]["alert"] is None
    assert not own.exists() and not receipt.exists()


@pytest.mark.parametrize("gap", ["prepared", "replacement", "manifest_removed", "receipt_removed", "completed"])
def test_recovery_replays_every_destructive_boundary(orphaned_attribution, monkeypatch, gap: str) -> None:
    repo, worktree, native, own, receipt, foreign = orphaned_attribution
    atomic, unlink = MODULE.atomic_json, Path.unlink
    interrupted = False

    def write(path, payload):
        nonlocal interrupted
        atomic(path, payload)
        if path.parent == MODULE.RETIREMENT_DIR:
            stage = "completed" if payload["state"] == "completed" else "replacement" if "session_replacement" in payload else "prepared"
            if not interrupted and stage == gap:
                interrupted = True
                raise OSError("fixture interruption")

    def remove(path, *args, **kwargs):
        nonlocal interrupted
        unlink(path, *args, **kwargs)
        stage = "manifest_removed" if path == own else "receipt_removed" if path == receipt else "other"
        if not interrupted and stage == gap:
            interrupted = True
            raise OSError("fixture interruption")

    monkeypatch.setattr(MODULE, "atomic_json", write)
    monkeypatch.setattr(Path, "unlink", remove)
    results, _ = MODULE.recover_retired_session(worktree, repo, native, "origin/main", dry_run=False)
    assert interrupted and results[0]["alert"]
    assert MODULE.recover_retired_session(worktree, repo, native, "origin/main", dry_run=False)[0][0]["alert"] is None
    assert not own.exists() and not receipt.exists()
    assert foreign.read_bytes() == b"foreign retained evidence, intentionally not parsed"


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
    assert "origin/main" in results[0]["alert"]
    assert "HEAD" in results[0]["alert"]
    assert touched == []


def test_retirement_cwd_refusal_names_the_condition_and_next_location(tmp_path: Path, monkeypatch) -> None:
    repo, _remote, _cfg = repository(tmp_path)
    worktree = tmp_path / "current-worktree"
    command("git", "worktree", "add", "-qb", "feature/current", str(worktree), cwd=repo)
    monkeypatch.chdir(worktree)
    with pytest.raises(ValueError, match="current working directory") as exc:
        MODULE.validate_retirement_target(worktree, repo, expect_active=True)
    assert str(repo) in str(exc.value)
    assert worktree.is_dir()


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


# ---------------------------------------------------------------------------
# Stranded entries: a manifest path beneath a worktree that vanished before any
# retirement record or receipt existed. Regressions for the accreting-manifest
# defect (session 2a0f680b…, 2026-09-11).
# ---------------------------------------------------------------------------

DROP_FORM = '--drop-stranded --assert "<why the work is known published>"'


def write_manifest(
    session_id: str, paths: list[str], remote_paths: list[str], extra: dict | None = None
) -> Path:
    manifest = MODULE.pending_manifest_path(session_id)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 2,
        "session_id": session_id,
        "updated_at": "2026-08-31T00:00:00Z",
        "paths": paths,
        "remote_paths": remote_paths,
        **(extra or {}),
    }
    manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return manifest


def stranded_state(tmp_path: Path) -> tuple[Path, Path]:
    """A worktrees directory outside every git working tree, and a worktree
    root beneath it that no longer exists."""
    worktrees = tmp_path / ".worktrees"
    worktrees.mkdir()
    assert MODULE.git(worktrees, "rev-parse", "--show-toplevel")[0] != 0  # positive control
    return worktrees, worktrees / "gone-20260831"


def configured_repository(tmp_path: Path, name: str) -> tuple[Path, Path]:
    remote = tmp_path / f"{name}-remote.git"
    repo = tmp_path / name
    command("git", "init", "--bare", "-q", "-b", "main", str(remote))
    command("git", "clone", "-q", str(remote), str(repo))
    command("git", "config", "core.hooksPath", str(tmp_path / "fixture-hooks"), cwd=repo)
    command("git", "config", "user.name", "Test", cwd=repo)
    command("git", "config", "user.email", "test@example.com", cwd=repo)
    context = repo / "projects" / "alpha" / "CONTEXT.md"
    context.parent.mkdir(parents=True)
    context.write_text("one\n", encoding="utf-8")
    command("git", "add", "projects/alpha/CONTEXT.md", cwd=repo)
    command("git", "commit", "-qm", "seed", cwd=repo)
    command("git", "push", "-qu", "origin", "main", cwd=repo)
    return repo, remote


def test_flush_reports_stranded_entry_and_still_evaluates_other_repositories(
    tmp_path: Path,
) -> None:
    repo, _remote, cfg = repository(tmp_path)
    context = repo / "projects" / "alpha" / "CONTEXT.md"
    context.write_text("published\n", encoding="utf-8")
    worktrees, missing_root = stranded_state(tmp_path)
    stranded = missing_root / "lessons" / "note.md"
    session = "session-stranded"
    manifest = write_manifest(session, [str(context), str(stranded)], [str(context), str(stranded)])

    results, observed = MODULE.flush_pending_session(cfg, session, dry_run=False)

    assert observed == [manifest]
    by_action = {result["action"]: result for result in results}
    entry = by_action["stranded"]
    assert entry["repo"] == str(stranded)
    assert str(missing_root) in entry["alert"]
    assert f"--flush-session {session} {DROP_FORM}" in entry["alert"]
    assert entry["drop_eligible"] is True
    assert entry["evidence"]["nearest_existing_ancestor"] == str(worktrees)
    assert entry["evidence"]["missing_worktree_root"] == str(missing_root)
    assert "failed" not in by_action
    assert by_action["committed-pushed"]["repo"] == str(repo)
    assert command("git", "show", "HEAD:projects/alpha/CONTEXT.md", cwd=repo) == "published"
    # The published repository's entries retire; the stranded entry stays visible.
    assert json.loads(manifest.read_text(encoding="utf-8"))["paths"] == [str(stranded)]


def test_stranded_entry_with_retained_receipt_names_session_reconcile_remedy(
    tmp_path: Path,
) -> None:
    _repo, _remote, cfg = repository(tmp_path)
    _worktrees, missing_root = stranded_state(tmp_path)
    stranded = missing_root / "projects" / "alpha" / "CONTEXT.md"
    session = "018f0000-0000-7000-8000-00000000000a"
    manifest = write_manifest(session, [str(stranded)], [str(stranded)])
    receipt = MODULE.LOCAL_HANDOFF_DIR / manifest.name
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps({
        "schema_version": 1, "readiness": "LOCAL_READY", "session_id": session,
        "pending_manifest": str(manifest),
        "pending_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "results": [{"repo": str(missing_root), "name": missing_root.name, "action": "local-ready",
                     "branch": "feature/gone", "head": "a" * 40, "files": 1,
                     "file_evidence": [], "alert": None}],
    }), encoding="utf-8")
    before = manifest.read_bytes(), receipt.read_bytes()

    results, _ = MODULE.flush_pending_session(cfg, session, dry_run=False)

    entry = next(result for result in results if result["action"] == "stranded")
    assert entry["drop_eligible"] is False
    assert f"--reconcile-retired-worktree {missing_root} --retirement-session {session}" in entry["alert"]
    assert "--retirement-head" not in entry["alert"]
    assert "--drop-stranded" not in entry["alert"]
    assert entry["evidence"]["local_handoff_receipt_head"] == "a" * 40
    # Retained evidence outranks an assertion: the drop leaves this entry alone.
    dropped, _ = MODULE.flush_pending_session(
        cfg, session, dry_run=False, drop_stranded=True, assertion="published elsewhere"
    )
    assert {result["action"] for result in dropped} == {"no-stranded-entries", "stranded"}
    assert (manifest.read_bytes(), receipt.read_bytes()) == before
    assert not MODULE.RETIRED_PENDING_DIR.exists()


@pytest.mark.parametrize("state", ["prepared", "completed"])
def test_stranded_entry_named_by_retirement_intent_points_at_the_intent(
    tmp_path: Path, state: str
) -> None:
    repo, _remote, cfg = repository(tmp_path)
    _worktrees, missing_root = stranded_state(tmp_path)
    session = "session-intent"
    manifest = write_manifest(session, [str(missing_root / "x.md")], [])
    MODULE.RETIREMENT_DIR.mkdir(parents=True)
    intent = MODULE.RETIREMENT_DIR / ("1" * 64 + ".json")
    intent.write_text(json.dumps({
        "schema_version": 2, "state": state, "worktree": str(missing_root), "repository": str(repo),
        "head": "b" * 40, "base_ref": "refs/remotes/origin/main", "base_oid": "c" * 40,
    }), encoding="utf-8")
    before = manifest.read_bytes()

    results, _ = MODULE.flush_pending_session(
        cfg, session, dry_run=False, drop_stranded=True, assertion="known published"
    )

    entry = next(result for result in results if result["action"] == "stranded")
    assert entry["drop_eligible"] is False
    assert str(intent) in entry["alert"]
    if state == "prepared":
        assert f"--complete-worktree-retirement {intent}" in entry["alert"]
    else:
        assert (f"--reconcile-retired-worktree {missing_root} --retirement-repository {repo} "
                f"--retirement-head {'b' * 40} --retirement-base refs/remotes/origin/main") in entry["alert"]
    assert manifest.read_bytes() == before
    assert not MODULE.RETIRED_PENDING_DIR.exists()


def test_local_handoff_records_stranded_entry_without_aborting_other_repositories(
    tmp_path: Path,
) -> None:
    repo, _remote, cfg = repository(tmp_path)
    context = repo / "projects" / "alpha" / "CONTEXT.md"
    context.write_text("local\n", encoding="utf-8")
    _worktrees, missing_root = stranded_state(tmp_path)
    session = "session-local-stranded"
    manifest = write_manifest(session, [str(context), str(missing_root / "lessons" / "note.md")], [str(context)])

    results, observed = MODULE.local_handoff_checkpoint({"session_id": session, "cwd": str(repo)}, cfg)

    assert observed == manifest
    assert [result["action"] for result in results] == ["stranded", "local-ready"]
    assert results[0]["drop_eligible"] is True
    assert results[1]["repo"] == str(repo) and results[1]["head"]
    payload = json.loads((MODULE.LOCAL_HANDOFF_DIR / manifest.name).read_text(encoding="utf-8"))
    assert payload["readiness"] == "BLOCKED"
    assert [result["action"] for result in payload["results"]] == ["stranded", "local-ready"]


def test_local_handoff_preserves_receipt_that_retains_stranded_worktree_evidence(
    tmp_path: Path,
) -> None:
    repo, _remote, cfg = repository(tmp_path)
    context = repo / "projects" / "alpha" / "CONTEXT.md"
    context.write_text("local\n", encoding="utf-8")
    _worktrees, missing_root = stranded_state(tmp_path)
    session = "018f0000-0000-7000-8000-00000000000b"
    manifest = write_manifest(session, [str(context), str(missing_root / "x.md")], [str(context)])
    receipt = MODULE.LOCAL_HANDOFF_DIR / manifest.name
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps({
        "schema_version": 1, "readiness": "LOCAL_READY", "session_id": session,
        "pending_manifest": str(manifest), "pending_manifest_sha256": "0" * 64,
        "results": [{"repo": str(missing_root), "name": missing_root.name, "action": "local-ready",
                     "branch": "feature/gone", "head": "a" * 40, "files": 1, "file_evidence": [], "alert": None}],
    }), encoding="utf-8")
    before = receipt.read_bytes()

    results, _ = MODULE.local_handoff_checkpoint({"session_id": session, "cwd": str(repo)}, cfg)

    assert [result["action"] for result in results] == ["stranded", "local-ready"]
    assert results[0]["drop_eligible"] is False
    assert "retained local-handoff receipt" in results[0]["alert"]
    assert receipt.read_bytes() == before


@pytest.mark.parametrize(
    "assertion",
    [None, "", "  \n\t", "\u00a0\u3000\u2028\u0085", "\u200b", "\u200b\u200c\u200d", "\ufeff"],
)
def test_drop_stranded_refuses_blank_assertion(tmp_path: Path, assertion: str | None) -> None:
    _repo, _remote, cfg = repository(tmp_path)
    _worktrees, missing_root = stranded_state(tmp_path)
    session = "session-no-assert"
    manifest = write_manifest(session, [str(missing_root / "x.md")], [])
    before = manifest.read_bytes()

    results, observed = MODULE.flush_pending_session(
        cfg, session, dry_run=False, drop_stranded=True, assertion=assertion
    )

    assert observed == []
    assert results[0]["action"] == "failed"
    assert "non-blank --assert" in results[0]["alert"]
    assert f"--flush-session {session} {DROP_FORM}" in results[0]["alert"]
    assert manifest.read_bytes() == before
    assert not MODULE.RETIRED_PENDING_DIR.exists()


def test_drop_stranded_cli_refuses_wrong_combinations(tmp_path: Path, monkeypatch, capsys) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("repos: []\n", encoding="utf-8")
    base = [str(MODULE_PATH), "--config", str(config)]
    for argv in (
        [*base, "--flush-session", "s", "--drop-stranded"],
        [*base, "--flush-session", "s", "--drop-stranded", "--assert", " "],
        [*base, "--flush-session", "s", "--drop-stranded", "--assert", "\u200b"],
        [*base, "--flush-session", "s", "--drop-stranded", "--assert", "\ufeff"],
        [*base, "--flush-session", "s", "--assert", "x"],
        [*base, "--flush-pending", "--drop-stranded", "--assert", "x"],
        [*base, "--drop-stranded", "--assert", "x"],
    ):
        monkeypatch.setattr(sys, "argv", argv)
        assert MODULE.main() == 2, argv
        assert f"--flush-session SESSION_ID {DROP_FORM}" in capsys.readouterr().err, argv
    assert not MODULE.RETIRED_PENDING_DIR.exists()
    assert not MODULE.REMOTE_HANDOFF_STATE.exists()


def test_drop_stranded_refuses_when_worktree_root_exists_at_drop_time(
    tmp_path: Path, monkeypatch
) -> None:
    _repo, _remote, cfg = repository(tmp_path)
    _worktrees, missing_root = stranded_state(tmp_path)
    session = "session-reappeared"
    manifest = write_manifest(session, [str(missing_root / "x.md")], [])
    before = manifest.read_bytes()
    original = MODULE.classify_stranded_entry

    def reappearing(*args, **kwargs):
        record = original(*args, **kwargs)
        if record is not None:
            missing_root.mkdir(exist_ok=True)  # the worktree returns between classification and the drop
        return record

    monkeypatch.setattr(MODULE, "classify_stranded_entry", reappearing)

    results, _ = MODULE.flush_pending_session(
        cfg, session, dry_run=False, drop_stranded=True, assertion="known published"
    )

    failed = next(result for result in results if result["action"] == "failed")
    assert str(missing_root) in failed["alert"] and "exists now" in failed["alert"]
    assert manifest.read_bytes() == before
    assert not MODULE.RETIRED_PENDING_DIR.exists()


def test_drop_stranded_writes_append_only_ledger_and_narrows_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    repo, _remote, cfg = repository(tmp_path)
    source = repo / "src" / "feature.py"
    source.parent.mkdir()
    source.write_text("local only\n", encoding="utf-8")  # uncommitted source keeps the manifest blocked
    worktrees, missing_root = stranded_state(tmp_path)
    mirrored = missing_root / "projects" / "alpha" / "CONTEXT.md"  # tracked at HEAD of the configured repo
    orphan = missing_root / "lessons" / "orphan.md"
    session = "session-drop"
    manifest = write_manifest(
        session, [str(source), str(mirrored), str(orphan)], [str(mirrored)],
        extra={"retired_worktrees": [{"note": "history"}]},
    )
    monkeypatch.setenv("SYNTHESIS_COORDINATION_SESSION", "s-test-seat")
    monkeypatch.setenv("CLAUDE_CODE_HOST_SESSION_ID", "host-1234")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("SYNTHESIS_CLIENT_SESSION_REF", raising=False)
    before_digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    assertion = "both files were merged to main on 2026-08-31"

    results, observed = MODULE.flush_pending_session(
        cfg, session, dry_run=False, drop_stranded=True, assertion=assertion
    )

    assert observed == [manifest]
    by_action = {result["action"]: result for result in results}
    assert by_action["dropped-stranded"]["files"] == 2
    assert "source-local-only" in by_action
    assert "stranded" not in by_action
    ledger = Path(by_action["dropped-stranded"]["ledger"])
    assert ledger.parent == MODULE.RETIRED_PENDING_DIR
    assert re.fullmatch(rf"{manifest.stem}-stranded-\d{{8}}T\d{{6}}Z\.json", ledger.name)
    record = json.loads(ledger.read_text(encoding="utf-8"))
    assert record["schema_version"] == 1
    assert record["session_id"] == session
    assert record["manifest"] == str(manifest)
    assert record["manifest_sha256_before"] == before_digest
    assert record["dropped_paths"] == [str(mirrored), str(orphan)]
    assert record["assertion"] == assertion
    assert record["acting_identity"] == {
        "SYNTHESIS_COORDINATION_SESSION": "s-test-seat",
        "CLAUDE_CODE_HOST_SESSION_ID": "host-1234",
    }
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", record["dropped_at"])
    evidence = {item["path"]: item for item in record["evidence"]}
    assert evidence[str(mirrored)]["nearest_existing_ancestor"] == str(worktrees)
    assert evidence[str(mirrored)]["missing_worktree_root"] == str(missing_root)
    assert evidence[str(mirrored)]["retirement_intent_named_worktree"] is False
    assert evidence[str(mirrored)]["local_handoff_receipt_named_worktree"] is False
    canonical = evidence[str(mirrored)]["canonical_copy"]
    assert Path(canonical["repository"]).resolve() == repo.resolve()
    assert canonical["relative_path"] == "projects/alpha/CONTEXT.md"
    assert canonical["blob_oid"] == command("git", "rev-parse", "HEAD:projects/alpha/CONTEXT.md", cwd=repo)
    assert canonical["head"] == command("git", "rev-parse", "HEAD", cwd=repo)
    assert evidence[str(orphan)]["canonical_copy"] is None
    narrowed = json.loads(manifest.read_text(encoding="utf-8"))
    assert narrowed["paths"] == [str(source)]
    assert narrowed["remote_paths"] == []
    assert narrowed["session_id"] == session
    assert narrowed["retired_worktrees"] == [{"note": "history"}]
    assert narrowed["dropped_stranded"][0]["ledger"] == str(ledger)
    # Append-only: a record path that already exists is never overwritten.
    second = MODULE.append_only_json(ledger, {"probe": True})
    assert second != ledger and second.parent == ledger.parent
    assert json.loads(ledger.read_text(encoding="utf-8")) == record
    assert json.loads(second.read_text(encoding="utf-8")) == {"probe": True}


def test_drop_stranded_dry_run_reports_and_writes_nothing(tmp_path: Path) -> None:
    repo, _remote, cfg = repository(tmp_path)
    source = repo / "src" / "feature.py"
    source.parent.mkdir()
    source.write_text("local only\n", encoding="utf-8")
    _worktrees, missing_root = stranded_state(tmp_path)
    session = "session-dry-drop"
    manifest = write_manifest(
        session, [str(source), str(missing_root / "a.md"), str(missing_root / "b.md")], [str(missing_root / "a.md")]
    )
    before = manifest.read_bytes()

    results, observed = MODULE.flush_pending_session(
        cfg, session, dry_run=True, drop_stranded=True, assertion="known published"
    )

    assert observed == [manifest]
    by_action = {result["action"]: result for result in results}
    assert by_action["would-drop-stranded"]["files"] == 2
    assert "stranded" not in by_action
    assert "source-local-only" in by_action
    assert manifest.read_bytes() == before
    assert not MODULE.RETIRED_PENDING_DIR.exists()
    assert not MODULE.LOCAL_HANDOFF_DIR.exists()


def test_drop_stranded_cli_retires_an_all_stranded_manifest(tmp_path: Path, monkeypatch) -> None:
    _worktrees, missing_root = stranded_state(tmp_path)
    session = "session-cli-drop"
    manifest = write_manifest(session, [str(missing_root / "a.md")], [str(missing_root / "a.md")])
    config = tmp_path / "config.yaml"
    config.write_text("repos: []\n", encoding="utf-8")
    argv = [str(MODULE_PATH), "--config", str(config), "--flush-session", session,
            "--drop-stranded", "--assert", "a.md is lessons/a.md at origin/main", "--json"]

    monkeypatch.setattr(sys, "argv", [*argv, "--dry-run"])
    assert MODULE.main() == 0
    assert manifest.exists()
    assert not MODULE.RETIRED_PENDING_DIR.exists()

    monkeypatch.setattr(sys, "argv", argv)
    assert MODULE.main() == 0
    assert not manifest.exists()
    assert len(list(MODULE.RETIRED_PENDING_DIR.glob("*.json"))) == 1
    state = json.loads(MODULE.REMOTE_HANDOFF_STATE.read_text(encoding="utf-8"))
    assert state["readiness"] == "REMOTE_READY"
    assert state["session_id"] == session


def test_flush_retires_published_repositories_and_keeps_blocked_entries(tmp_path: Path) -> None:
    repo, _remote, cfg = repository(tmp_path)
    second, second_remote = configured_repository(tmp_path, "second")
    cfg = {**cfg, "repos": [str(repo), str(second)]}
    published = repo / "projects" / "alpha" / "CONTEXT.md"
    published.write_text("published\n", encoding="utf-8")
    blocked = second / "projects" / "alpha" / "CONTEXT.md"
    blocked.write_text("blocked\n", encoding="utf-8")
    command("git", "remote", "set-url", "origin", str(second_remote) + "-missing", cwd=second)
    session = "session-partial"
    manifest = write_manifest(session, [str(published), str(blocked)], [str(published), str(blocked)])

    results, _ = MODULE.flush_pending_session(cfg, session, dry_run=False)

    by_repo = {result["repo"]: result for result in results if result["repo"] in {str(repo), str(second)}}
    assert by_repo[str(repo)]["action"] == "committed-pushed"
    assert by_repo[str(second)]["action"] == "committed-no-push"
    summary = next(result for result in results if result["action"] == "retired-repositories")
    assert summary["retired_repositories"] == [str(repo)]
    assert summary["files"] == 1
    assert summary["manifest_removed"] is False
    assert summary["alert"] is None
    narrowed = json.loads(manifest.read_text(encoding="utf-8"))
    assert narrowed["paths"] == [str(blocked)]
    assert narrowed["remote_paths"] == [str(blocked)]

    command("git", "remote", "set-url", "origin", str(second_remote), cwd=second)
    results, _ = MODULE.flush_pending_session(cfg, session, dry_run=False)

    assert next(r for r in results if r["repo"] == str(second))["action"] == "pushed-stranded"
    summary = next(result for result in results if result["action"] == "retired-repositories")
    assert summary["retired_repositories"] == [str(second)]
    assert summary["manifest_removed"] is True
    assert not manifest.exists()
    assert not any(result.get("alert") for result in results)


def test_deleted_file_inside_existing_repository_is_deleted_or_missing_not_stranded(
    tmp_path: Path,
) -> None:
    repo, _remote, cfg = repository(tmp_path)
    removed = repo / "projects" / "alpha" / "removed" / "note.md"  # its directory is gone, its repository is not
    session = "session-deleted"
    manifest = write_manifest(session, [str(removed)], [str(removed)])

    local, _ = MODULE.local_handoff_checkpoint({"session_id": session, "cwd": str(repo)}, cfg)
    assert local[0]["action"] == "local-ready"
    assert local[0]["file_evidence"] == [{"path": str(removed), "state": "deleted-or-missing"}]

    results, _ = MODULE.flush_pending_session(cfg, session, dry_run=False)
    assert [result["action"] for result in results] == ["clean", "retired-repositories"]
    assert not manifest.exists()


def test_missing_registered_nested_worktree_stays_failed_not_stranded(tmp_path: Path) -> None:
    repo, _remote, cfg = repository(tmp_path)
    nested = repo / "nested"
    command("git", "worktree", "add", "-q", "--orphan", "-b", "nested", str(nested), cwd=repo)
    assert nested.parent == repo and (nested / ".git").is_file()
    shutil.rmtree(nested)  # interruption, not the sanctioned retirement workflow
    session = "session-nested"
    manifest = write_manifest(session, [str(nested / "file.md")], [str(nested / "file.md")])

    results, _ = MODULE.flush_pending_session(cfg, session, dry_run=False)

    assert results[0]["action"] == "failed"
    assert "not inside an available git worktree" in results[0]["alert"]
    assert manifest.exists()


# ---------------------------------------------------------------------------
# Repair round (2026-09-11): a git probe that cannot answer, or answers while
# a .git entry is visible in the ancestor chain, must never make a live
# repository's deleted file drop-eligible; a receipt bound to an older digest
# must name a remedy that runs; an assertion of invisible characters is blank.
# ---------------------------------------------------------------------------

GIT_UNAVAILABLE = [(-1, "", "timeout"), (-1, "", "git not found")]


def toplevel_probe_returning(monkeypatch, outcome: tuple[int, str, str]) -> None:
    """Fail only ``git rev-parse --show-toplevel``; every other git call is real."""
    original = MODULE.git

    def patched(repo, *args, **kwargs):
        if args[:2] == ("rev-parse", "--show-toplevel"):
            return outcome
        return original(repo, *args, **kwargs)

    monkeypatch.setattr(MODULE, "git", patched)


@pytest.mark.parametrize("outcome", GIT_UNAVAILABLE)
def test_stop_reports_git_unavailability_as_failed_not_stranded(
    tmp_path: Path, monkeypatch, outcome: tuple[int, str, str]
) -> None:
    repo, _remote, cfg = repository(tmp_path)
    removed = repo / "projects" / "alpha" / "removed" / "note.md"  # directory gone, repository intact
    session = "session-git-unavailable"
    manifest = write_manifest(session, [str(removed)], [str(removed)])
    toplevel_probe_returning(monkeypatch, outcome)

    results, observed = MODULE.local_handoff_checkpoint({"session_id": session, "cwd": str(repo)}, cfg)

    assert observed == manifest
    assert [result["action"] for result in results] == ["failed"]
    assert results[0]["alert"].startswith("stranded classification unavailable: ")
    assert f"git is unavailable for {removed.parent.parent}: {outcome[2]}" in results[0]["alert"]
    assert "--drop-stranded" not in results[0]["alert"]
    assert not (MODULE.LOCAL_HANDOFF_DIR / manifest.name).exists()


@pytest.mark.parametrize("outcome", GIT_UNAVAILABLE)
def test_drop_stranded_never_drops_a_live_repository_when_git_is_unavailable(
    tmp_path: Path, monkeypatch, outcome: tuple[int, str, str]
) -> None:
    repo, _remote, cfg = repository(tmp_path)
    removed = repo / "projects" / "alpha" / "removed" / "note.md"
    session = "session-git-unavailable-drop"
    manifest = write_manifest(session, [str(removed)], [str(removed)])
    before = manifest.read_bytes()
    toplevel_probe_returning(monkeypatch, outcome)

    results, observed = MODULE.flush_pending_session(
        cfg, session, dry_run=False, drop_stranded=True, assertion="the note was merged on 2026-09-01"
    )

    assert observed == [manifest]
    actions = [result["action"] for result in results]
    assert set(actions) == {"failed"}, actions
    assert all(f"git is unavailable for {removed.parent.parent}: {outcome[2]}" in result["alert"] for result in results)
    assert manifest.read_bytes() == before
    assert not MODULE.RETIRED_PENDING_DIR.exists()


def test_visible_git_directory_keeps_a_refused_probe_out_of_stranded(tmp_path: Path, monkeypatch) -> None:
    """git can refuse a live repository (safe.directory, a damaged gitdir) with a
    non-zero status; the ancestor chain still shows repo/.git, so the existing
    handling applies and nothing is drop-eligible."""
    repo, _remote, cfg = repository(tmp_path)
    removed = repo / "projects" / "alpha" / "removed" / "note.md"
    session = "session-refused-probe"
    manifest = write_manifest(session, [str(removed)], [str(removed)])
    before = manifest.read_bytes()
    assert (repo / ".git").is_dir()  # positive control for the ancestor-chain test
    toplevel_probe_returning(monkeypatch, (128, "", "fatal: detected dubious ownership in repository"))

    assert MODULE.classify_stranded_entry(removed, session, manifest, MODULE.StrandedEvidence()) is None
    stop, _ = MODULE.local_handoff_checkpoint({"session_id": session, "cwd": str(repo)}, cfg)
    assert [result["action"] for result in stop] == ["failed"]
    assert "not inside an available git worktree" in stop[0]["alert"]
    results, _ = MODULE.flush_pending_session(
        cfg, session, dry_run=False, drop_stranded=True, assertion="known published"
    )
    assert {result["action"] for result in results} == {"no-stranded-entries", "failed"}
    assert manifest.read_bytes() == before
    assert not MODULE.RETIRED_PENDING_DIR.exists()


@pytest.mark.parametrize("outcome", [None, *GIT_UNAVAILABLE])
def test_genuine_missing_worktree_root_classifies_stranded_only_with_a_working_git(
    tmp_path: Path, monkeypatch, outcome: tuple[int, str, str] | None
) -> None:
    worktrees, missing_root = stranded_state(tmp_path)
    path = missing_root / "lessons" / "note.md"
    session = "session-positive-control"
    manifest = write_manifest(session, [str(path)], [str(path)])
    assert not any((candidate / ".git").exists() for candidate in (worktrees, *worktrees.parents))
    if outcome is None:
        record = MODULE.classify_stranded_entry(path, session, manifest, MODULE.StrandedEvidence())
        assert record["action"] == "stranded" and record["drop_eligible"] is True
        assert record["evidence"]["missing_worktree_root"] == str(missing_root)
        return
    toplevel_probe_returning(monkeypatch, outcome)
    with pytest.raises(ValueError, match=f"git is unavailable for {re.escape(str(worktrees))}: {outcome[2]}"):
        MODULE.classify_stranded_entry(path, session, manifest, MODULE.StrandedEvidence())


def test_stranded_entry_with_stale_receipt_digest_names_a_head_remedy_that_runs(
    tmp_path: Path, monkeypatch
) -> None:
    repo, _remote, cfg = repository(tmp_path)
    worktree = tmp_path / "retired-worktree"
    command("git", "worktree", "add", "-qb", "feature/retired", str(worktree), cwd=repo)
    retired_path = worktree / "change.txt"
    retired_path.write_text("change\n", encoding="utf-8")
    command("git", "add", "change.txt", cwd=worktree)
    command("git", "commit", "-qm", "change", cwd=worktree)
    head = command("git", "rev-parse", "HEAD", cwd=worktree)
    command("git", "merge", "-q", "--no-edit", "feature/retired", cwd=repo)
    command("git", "push", "-q", "origin", "main", cwd=repo)
    command("git", "worktree", "remove", str(worktree), cwd=repo)
    session = "018f0000-0000-7000-8000-00000000000c"
    survivor = repo / "projects" / "alpha" / "CONTEXT.md"
    manifest = write_manifest(session, [str(retired_path), str(survivor)], [str(survivor)])
    receipt = MODULE.LOCAL_HANDOFF_DIR / manifest.name
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps({
        "schema_version": 1, "readiness": "LOCAL_READY", "session_id": session,
        "pending_manifest": str(manifest), "pending_manifest_sha256": "0" * 64,  # the manifest accreted since
        "results": [{"repo": str(worktree), "name": worktree.name, "action": "local-ready",
                     "branch": "feature/retired", "head": head, "files": 1, "file_evidence": [], "alert": None}],
    }), encoding="utf-8")
    head_form = (
        f"--reconcile-retired-worktree {worktree} --retirement-repository <owning repository> "
        f"--retirement-head {head} --retirement-base <fetched remote ref such as origin/main>"
    )

    results, _ = MODULE.flush_pending_session(cfg, session, dry_run=True)

    entry = next(result for result in results if result["action"] == "stranded")
    assert entry["drop_eligible"] is False
    assert "binds an older attribution digest" in entry["alert"]
    assert entry["remedy"] == head_form and f"accepted form: {head_form}" in entry["alert"]
    assert "--retirement-session" not in entry["remedy"]
    assert entry["evidence"]["local_handoff_receipt_head"] == head
    # The session-bound form the alert no longer names is refused for this receipt ...
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", session)
    monkeypatch.delenv("SYNTHESIS_CLIENT_SESSION_REF", raising=False)
    refused, _ = MODULE.recover_retired_session(worktree, repo, session, "origin/main", dry_run=True)
    assert "lacks current attribution-digest evidence" in refused[0]["alert"]
    # ... and the named form runs.
    reconciled, touched = MODULE.reconcile_retired_worktree(worktree, repo, head, "origin/main", dry_run=False)
    assert reconciled[0]["alert"] is None
    assert reconciled[0]["action"] == "retired-worktree-reconciled"
    assert touched == [manifest]
    assert json.loads(manifest.read_text(encoding="utf-8"))["paths"] == [str(survivor)]


def test_stranded_entry_with_blocked_receipt_names_the_head_remedy(tmp_path: Path) -> None:
    _repo, _remote, cfg = repository(tmp_path)
    _worktrees, missing_root = stranded_state(tmp_path)
    session = "018f0000-0000-7000-8000-00000000000d"
    manifest = write_manifest(session, [str(missing_root / "x.md")], [])
    receipt = MODULE.LOCAL_HANDOFF_DIR / manifest.name
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps({
        "schema_version": 1, "readiness": "BLOCKED", "session_id": session,
        "pending_manifest": str(manifest),
        "pending_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "results": [{"repo": str(missing_root), "name": missing_root.name, "action": "local-ready",
                     "branch": "feature/gone", "head": "d" * 40, "files": 1, "file_evidence": [], "alert": None}],
    }), encoding="utf-8")

    results, _ = MODULE.flush_pending_session(cfg, session, dry_run=True)

    entry = next(result for result in results if result["action"] == "stranded")
    assert entry["drop_eligible"] is False
    assert "records readiness BLOCKED" in entry["alert"]
    assert "--retirement-session" not in entry["remedy"]
    assert f"--retirement-head {'d' * 40}" in entry["remedy"]
    assert f"accepted form: {entry['remedy']}" in entry["alert"]
