from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
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
    # Synthetic repositories must never consult the invoking developer's Git
    # hooks, claims, receipts or state directory.
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


def repository(tmp_path: Path) -> tuple[Path, Path, dict, Path]:
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    command("git", "init", "--bare", "-q", "-b", "main", str(remote))
    command("git", "clone", "-q", str(remote), str(repo))
    hooks = tmp_path / "fixture-hooks"
    hooks.mkdir()
    command("git", "config", "core.hooksPath", str(hooks), cwd=repo)
    command("git", "config", "user.name", "Test", cwd=repo)
    command("git", "config", "user.email", "test@example.com", cwd=repo)
    seed = repo / "seed.md"
    seed.write_text("seed\n", encoding="utf-8")
    command("git", "add", "seed.md", cwd=repo)
    command("git", "commit", "-qm", "seed", cwd=repo)
    branch = command("git", "branch", "--show-current", cwd=repo)
    command("git", "push", "-qu", "origin", branch, cwd=repo)
    cfg = {
        **MODULE.DEFAULTS,
        "repos": [str(repo)],
        "allowed_remote_prefixes": [str(tmp_path)],
    }
    return repo, remote, cfg, hooks


def write_manifest(
    session_id: str, paths: list[str], remote_paths: list[str], extra: dict | None = None
) -> Path:
    manifest = MODULE.pending_manifest_path(session_id)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 2,
        "session_id": session_id,
        "updated_at": "2026-09-22T00:00:00Z",
        "paths": paths,
        "remote_paths": remote_paths,
        **(extra or {}),
    }
    manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return manifest


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def install_claim_gate(hooks: Path, refused: list[str], log: Path | None = None) -> None:
    """A pre-commit hook modeling the coordination claim gate: refuse any
    commit whose tree touches a refused path, allow everything else."""
    lines = ["#!/bin/sh"]
    if log is not None:
        lines.append(f'echo "fired" >> {log}')
    for name in refused:
        lines.append(f'if git diff --cached --name-only | grep -qx "{name}"; then')
        lines.append(f'  echo "claim gate: {name} outside session claim" >&2')
        lines.append("  exit 1")
        lines.append("fi")
    lines.append("exit 0")
    hook = hooks / "pre-commit"
    hook.write_text("\n".join(lines) + "\n", encoding="utf-8")
    hook.chmod(0o755)


def commit_all(repo: Path, message: str) -> None:
    command("git", "add", "-A", cwd=repo)
    command("git", "commit", "-qm", message, cwd=repo)


# ---------------------------------------------------------------------------
# Rule 1/2/3 end to end: the BUG-4 trap, drained
# ---------------------------------------------------------------------------

def test_hook_blocked_root_retires_clean_commits_own_and_skips_foreign(tmp_path: Path) -> None:
    repo, _remote, cfg, hooks = repository(tmp_path)
    own = repo / "own.md"
    foreign = repo / "foreign.md"
    clean = repo / "clean.md"
    own.write_text("own-v1\n", encoding="utf-8")
    foreign.write_text("stale-bytes\n", encoding="utf-8")
    clean.write_text("clean-v1\n", encoding="utf-8")
    commit_all(repo, "context seed")
    command("git", "push", "-q", "origin", command("git", "branch", "--show-current", cwd=repo), cwd=repo)
    # This session writes its own bytes (attributed) ...
    own.write_text("own-v2\n", encoding="utf-8")
    # ... while another session overwrites the foreign path twice: committed
    # bytes land in HEAD, then the worktree moves on again. The attribution
    # hash matches neither.
    foreign.write_text("committed-other\n", encoding="utf-8")
    command("git", "add", "foreign.md", cwd=repo)
    command("git", "commit", "-qm", "foreign session commit", cwd=repo)
    command("git", "push", "-q", "origin", command("git", "branch", "--show-current", cwd=repo), cwd=repo)
    foreign.write_text("current-other\n", encoding="utf-8")
    install_claim_gate(hooks, ["foreign.md"])
    hashes = {
        str(own): sha("own-v2\n"),
        str(foreign): sha("stale-bytes\n"),
        str(clean): sha("clean-v1\n"),
    }
    session = "session-per-path"
    manifest = write_manifest(
        session, [str(own), str(foreign), str(clean)], [str(own), str(foreign), str(clean)],
        extra={"content_hashes": hashes},
    )

    results, _ = MODULE.flush_pending_session(cfg, session, dry_run=False)

    by_repo = {r["repo"]: r for r in results if r["repo"] == str(repo)}
    assert by_repo[str(repo)]["action"] == "committed-pushed"
    assert command("git", "show", "HEAD:own.md", cwd=repo) == "own-v2"
    assert command("git", "show", "HEAD:foreign.md", cwd=repo) == "committed-other"
    summary = next(r for r in results if r["action"] == "retired-per-path")
    assert sorted(summary["retired_paths"]) == sorted([str(own), str(clean)])
    assert summary["files"] == 2
    assert summary["manifest_removed"] is False
    assert summary["skipped_foreign"] == [
        {"repo": str(repo), "path": "foreign.md", "reason": "foreign-overwrite"}
    ]
    assert summary["retries"] == [{"repo": str(repo), "committed": 1, "action": "committed-pushed"}]
    narrowed = json.loads(manifest.read_text(encoding="utf-8"))
    assert narrowed["paths"] == [str(foreign)]
    assert narrowed["remote_paths"] == [str(foreign)]
    assert narrowed["content_hashes"] == {str(foreign): sha("stale-bytes\n")}


def test_retry_refused_everywhere_keeps_entries_and_reports(tmp_path: Path) -> None:
    repo, _remote, cfg, hooks = repository(tmp_path)
    own = repo / "own.md"
    foreign = repo / "foreign.md"
    own.write_text("own-v1\n", encoding="utf-8")
    foreign.write_text("stale\n", encoding="utf-8")
    commit_all(repo, "seed")
    command("git", "push", "-q", "origin", command("git", "branch", "--show-current", cwd=repo), cwd=repo)
    own.write_text("own-v2\n", encoding="utf-8")
    foreign.write_text("committed-other\n", encoding="utf-8")
    command("git", "add", "foreign.md", cwd=repo)
    command("git", "commit", "-qm", "foreign session commit", cwd=repo)
    command("git", "push", "-q", "origin", command("git", "branch", "--show-current", cwd=repo), cwd=repo)
    foreign.write_text("current-other\n", encoding="utf-8")
    log = tmp_path / "hook.log"
    install_claim_gate(hooks, ["own.md", "foreign.md"], log=log)
    head_before = command("git", "rev-parse", "HEAD", cwd=repo)
    session = "session-refused"
    manifest = write_manifest(
        session, [str(own), str(foreign)], [str(own), str(foreign)],
        extra={"content_hashes": {str(own): sha("own-v2\n"), str(foreign): sha("stale\n")}},
    )

    results, _ = MODULE.flush_pending_session(cfg, session, dry_run=False)

    assert command("git", "rev-parse", "HEAD", cwd=repo) == head_before
    assert log.read_text(encoding="utf-8").split() == ["fired", "fired"]  # main + subset retry
    root_result = next(r for r in results if r["repo"] == str(repo))
    assert root_result["action"] == "hook-blocked"
    assert "per-path subset retry also refused" in root_result["alert"]
    summary = next(r for r in results if r["action"] == "retired-per-path")
    assert summary["retired_paths"] == []
    assert summary["files"] == 0
    assert summary["manifest_removed"] is False
    assert [s["path"] for s in summary["skipped_foreign"]] == ["foreign.md"]
    assert summary["retries"][0]["committed"] == 0
    assert "refused" in summary["retries"][0]
    kept = json.loads(manifest.read_text(encoding="utf-8"))
    assert kept["paths"] == [str(own), str(foreign)]


# ---------------------------------------------------------------------------
# Legacy (hashless) manifests: hash-independent Rule-1 win, no commit change
# ---------------------------------------------------------------------------

def test_legacy_manifest_gets_no_retry_but_clean_sibling_retires(tmp_path: Path) -> None:
    repo, _remote, cfg, hooks = repository(tmp_path)
    dirty = repo / "dirty.md"
    clean = repo / "clean.md"
    dirty.write_text("v1\n", encoding="utf-8")
    clean.write_text("v1\n", encoding="utf-8")
    commit_all(repo, "seed")
    command("git", "push", "-q", "origin", command("git", "branch", "--show-current", cwd=repo), cwd=repo)
    dirty.write_text("v2\n", encoding="utf-8")
    install_claim_gate(hooks, ["dirty.md"])
    head_before = command("git", "rev-parse", "HEAD", cwd=repo)
    session = "session-legacy"
    manifest = write_manifest(session, [str(dirty), str(clean)], [str(dirty), str(clean)])

    results, _ = MODULE.flush_pending_session(cfg, session, dry_run=False)

    assert command("git", "rev-parse", "HEAD", cwd=repo) == head_before  # no retry without proof
    root_result = next(r for r in results if r["repo"] == str(repo))
    assert root_result["action"] == "hook-blocked"
    summary = next(r for r in results if r["action"] == "retired-per-path")
    assert summary["retired_paths"] == [str(clean)]
    assert summary["skipped_foreign"] == []
    assert summary["retries"] == []
    narrowed = json.loads(manifest.read_text(encoding="utf-8"))
    assert narrowed["paths"] == [str(dirty)]


# ---------------------------------------------------------------------------
# Rule 4: attributed bytes landed, worktree dirtied by others
# ---------------------------------------------------------------------------

def test_landed_bytes_retire_once_pushed_and_skip_while_unpushed(tmp_path: Path) -> None:
    repo, _remote, cfg, hooks = repository(tmp_path)
    landed = repo / "landed.md"
    landed.write_text("session-bytes\n", encoding="utf-8")
    commit_all(repo, "seed")
    command("git", "push", "-q", "origin", command("git", "branch", "--show-current", cwd=repo), cwd=repo)
    # The session's bytes land in a local commit (unpushed); others dirty it.
    landed.write_text("landed-v1\n", encoding="utf-8")
    command("git", "add", "landed.md", cwd=repo)
    command("git", "commit", "-qm", "land session bytes", cwd=repo)
    landed.write_text("foreign-dirt\n", encoding="utf-8")
    install_claim_gate(hooks, ["landed.md"])  # every commit refused: no usable subset
    session = "session-landed"
    manifest = write_manifest(
        session, [str(landed)], [str(landed)],
        extra={"content_hashes": {str(landed): sha("landed-v1\n")}},
    )

    results, _ = MODULE.flush_pending_session(cfg, session, dry_run=False)

    summary = next(r for r in results if r["action"] == "retired-per-path")
    assert summary["retired_paths"] == []
    assert summary["skipped_foreign"] == [
        {"repo": str(repo), "path": "landed.md",
         "reason": "attributed bytes committed locally but unpushed; worktree modified by others"}
    ]
    assert manifest.exists()

    command("git", "push", "-q", "origin", command("git", "branch", "--show-current", cwd=repo), cwd=repo)
    results, _ = MODULE.flush_pending_session(cfg, session, dry_run=False)

    summary = next(r for r in results if r["action"] == "retired-per-path")
    assert summary["retired_paths"] == [str(landed)]
    assert summary["manifest_removed"] is True
    assert not manifest.exists()


# ---------------------------------------------------------------------------
# Dry run: report sets, mutate nothing
# ---------------------------------------------------------------------------

def test_dry_run_reports_per_path_sets_without_mutating(tmp_path: Path) -> None:
    repo, _remote, cfg, hooks = repository(tmp_path)
    own = repo / "own.md"
    foreign = repo / "foreign.md"
    clean = repo / "clean.md"
    own.write_text("v1\n", encoding="utf-8")
    foreign.write_text("stale\n", encoding="utf-8")
    clean.write_text("v1\n", encoding="utf-8")
    commit_all(repo, "seed")
    command("git", "push", "-q", "origin", command("git", "branch", "--show-current", cwd=repo), cwd=repo)
    own.write_text("v2\n", encoding="utf-8")
    foreign.write_text("committed-other\n", encoding="utf-8")
    command("git", "add", "foreign.md", cwd=repo)
    command("git", "commit", "-qm", "foreign session commit", cwd=repo)
    command("git", "push", "-q", "origin", command("git", "branch", "--show-current", cwd=repo), cwd=repo)
    foreign.write_text("current-other\n", encoding="utf-8")
    install_claim_gate(hooks, ["foreign.md"])
    session = "session-dry"
    manifest = write_manifest(
        session, [str(own), str(foreign), str(clean)], [str(own), str(foreign), str(clean)],
        extra={"content_hashes": {str(own): sha("v2\n"), str(foreign): sha("stale\n"), str(clean): sha("v1\n")}},
    )
    before_bytes = manifest.read_bytes()
    head_before = command("git", "rev-parse", "HEAD", cwd=repo)

    results, _ = MODULE.flush_pending_session(cfg, session, dry_run=True)

    assert manifest.read_bytes() == before_bytes
    assert command("git", "rev-parse", "HEAD", cwd=repo) == head_before
    assert not any(r["action"] == "retired-per-path" for r in results)
    preview = next(r for r in results if r["action"] == "would-retire-per-path")
    assert preview["roots"] == [
        {
            "repo": str(repo),
            "would_retire": ["clean.md"],
            "would_commit": ["own.md"],
            "would_skip": [{"path": "foreign.md", "reason": "foreign-overwrite"}],
            "would_retry_commit": False,  # dry-run root reports would-commit, not hook-blocked
        }
    ]


# ---------------------------------------------------------------------------
# Scope guards: untrustworthy roots, published roots, source entries
# ---------------------------------------------------------------------------

def test_guard_rejected_root_retires_nothing(tmp_path: Path) -> None:
    repo, _remote, cfg, _hooks = repository(tmp_path)
    outside = tmp_path / "outside"
    outside_remote = tmp_path / "outside.git"
    command("git", "init", "--bare", "-q", "-b", "main", str(outside_remote))
    command("git", "clone", "-q", str(outside_remote), str(outside))
    command("git", "config", "user.name", "Test", cwd=outside)
    command("git", "config", "user.email", "test@example.com", cwd=outside)
    tracked = outside / "tracked.md"
    tracked.write_text("v1\n", encoding="utf-8")
    command("git", "add", "tracked.md", cwd=outside)
    command("git", "commit", "-qm", "seed", cwd=outside)
    command("git", "push", "-qu", "origin", command("git", "branch", "--show-current", cwd=outside), cwd=outside)
    session = "session-guard"
    manifest = write_manifest(
        session, [str(tracked)], [str(tracked)],
        extra={"content_hashes": {str(tracked): sha("v1\n")}},
    )

    results, _ = MODULE.flush_pending_session(cfg, session, dry_run=False)

    assert next(r for r in results if r["repo"] == str(outside))["action"] == "guard-rejected"
    assert not any(r["action"] == "retired-per-path" for r in results)
    assert json.loads(manifest.read_text(encoding="utf-8"))["paths"] == [str(tracked)]


def test_lock_active_root_retires_nothing(tmp_path: Path) -> None:
    repo, _remote, cfg, _hooks = repository(tmp_path)
    tracked = repo / "seed.md"
    session = "session-lock"
    manifest = write_manifest(
        session, [str(tracked)], [str(tracked)],
        extra={"content_hashes": {str(tracked): sha("seed\n")}},
    )
    lock = Path(command("git", "rev-parse", "--git-path", "index.lock", cwd=repo))
    if not lock.is_absolute():
        lock = repo / lock
    lock.write_text("held\n", encoding="utf-8")
    try:
        results, _ = MODULE.flush_pending_session(cfg, session, dry_run=False)
    finally:
        lock.unlink(missing_ok=True)

    assert next(r for r in results if r["repo"] == str(repo))["action"] == "skipped-lock-active"
    assert not any(r["action"] == "retired-per-path" for r in results)
    assert json.loads(manifest.read_text(encoding="utf-8"))["paths"] == [str(tracked)]


def test_published_root_never_gets_per_path_record(tmp_path: Path) -> None:
    repo, _remote, cfg, _hooks = repository(tmp_path)
    tracked = repo / "seed.md"
    session = "session-published"
    write_manifest(
        session, [str(tracked)], [str(tracked)],
        extra={"content_hashes": {str(tracked): sha("seed\n")}},
    )

    results, _ = MODULE.flush_pending_session(cfg, session, dry_run=False)

    assert [r["action"] for r in results] == ["clean", "retired-repositories"]


def test_source_entries_keep_root_granularity(tmp_path: Path) -> None:
    repo, _remote, cfg, _hooks = repository(tmp_path)
    src = repo / "seed.md"
    src.write_text("dirty-source\n", encoding="utf-8")
    session = "session-source"
    manifest = write_manifest(session, [str(src)], [])

    results, _ = MODULE.flush_pending_session(cfg, session, dry_run=False)

    assert next(r for r in results if r["name"] == "source-path" or "source" in r["action"])["action"] == "source-local-only"
    assert not any(r["action"] in ("retired-per-path", "would-retire-per-path") for r in results)
    assert json.loads(manifest.read_text(encoding="utf-8"))["paths"] == [str(src)]


# ---------------------------------------------------------------------------
# Reader: absent/invalid/malformed hashes fail toward legacy behavior
# ---------------------------------------------------------------------------

def test_hash_reader_accepts_only_wellformed_entries() -> None:
    good = "a" * 64
    assert MODULE.load_pending_manifest_hashes({}) == {}
    assert MODULE.load_pending_manifest_hashes({"content_hashes": None}) == {}
    assert MODULE.load_pending_manifest_hashes({"content_hashes": ["x"]}) == {}
    assert MODULE.load_pending_manifest_hashes({"content_hashes": "x"}) == {}
    assert MODULE.load_pending_manifest_hashes({"content_hashes": {"/a": "zz"}}) == {}
    assert MODULE.load_pending_manifest_hashes({"content_hashes": {"/a": "A" * 64}}) == {}
    assert MODULE.load_pending_manifest_hashes({"content_hashes": {"/a": good, "/b": "nope"}}) == {"/a": good}
    assert MODULE.load_pending_manifest_hashes({"content_hashes": {1: good}}) == {}
