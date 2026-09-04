from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest

import project_state as state


def run(*args: str, cwd: Path) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def write_project(repo: Path, project_id: str = "alpha", version: str = "1.0.0") -> Path:
    project = repo / "projects" / project_id
    (project / "sessions").mkdir(parents=True, exist_ok=True)
    (project / "resources" / "artifacts").mkdir(parents=True, exist_ok=True)
    (repo / "projects" / "index.yaml").write_text(
        f"- id: {project_id}\n  status: active\n  last_session: '2026-09-01'\n",
        encoding="utf-8",
    )
    (project / "REFERENCE.md").write_text("# Reference\n", encoding="utf-8")
    (project / "sessions" / "2026-09.md").write_text(
        "### 2026-09-03 — current\n", encoding="utf-8"
    )
    (project / "resources" / "artifacts" / "plan.md").write_text(
        "# Plan\n", encoding="utf-8"
    )
    (project / "CONTEXT.md").write_text(
        "\n".join(
            [
                "# Context",
                "",
                f"**Phase:** release {version}",
                "**Status:** Active",
                "**Last session:** 2026-09-03",
                "",
                "[controlling plan](resources/artifacts/plan.md)",
                "",
                "## Baseline history",
                f"Accepted release snapshot: v{version}.",
                "",
                "## Handoff history",
                f"Snapshot recorded 2026-09-03 (v{version}).",
                "",
                "## What's Next",
                "- [ ] finish",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return project


def init_repo(root: Path, version: str = "1.0.0") -> tuple[Path, Path]:
    remote = root / "remote.git"
    repo = root / "repo"
    hooks = root / "fixture-hooks"
    hooks.mkdir()
    run("git", "init", "--bare", str(remote), cwd=root)
    run("git", "init", "-b", "main", str(repo), cwd=root)
    run("git", "config", "user.email", "fixture@example.invalid", cwd=repo)
    run("git", "config", "user.name", "Fixture", cwd=repo)
    run("git", "config", "core.hooksPath", str(hooks), cwd=repo)
    project = write_project(repo, version=version)
    run("git", "add", "projects", cwd=repo)
    run("git", "commit", "-m", "Initial project state", cwd=repo)
    run("git", "remote", "add", "origin", str(remote), cwd=repo)
    run("git", "push", "-u", "origin", "main", cwd=repo)
    run("git", "symbolic-ref", "HEAD", "refs/heads/main", cwd=remote)
    return repo, project


def commit_version(repo: Path, project: Path, version: str) -> str:
    text = (project / "CONTEXT.md").read_text(encoding="utf-8")
    text = text.replace("v1.0.0", f"v{version}").replace("release 1.0.0", f"release {version}")
    (project / "CONTEXT.md").write_text(text, encoding="utf-8")
    run("git", "add", str(project.relative_to(repo)), cwd=repo)
    run("git", "commit", "-m", "Advance project state", cwd=repo)
    return run("git", "rev-parse", "HEAD", cwd=repo)


def board(path: Path, rows: list[tuple[str, str, str, str]]) -> Path:
    header = (
        "# Board\nLease: file:///fixture\n\n## Active sessions\n\n"
        "| Session UUID | Compact ID | Speakable ID | Client session ref | Project | "
        "Workspace(s) / branch | Claimed areas (advisory lock) | Context role | Started | Heartbeat | Status |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    body = "".join(
        f"| {session} | {compact} | words-1 | tool:{session} | {project} | {workspace} | "
        f"{workspace}/projects/{project}/** | owner | 2026-09-03T12:00:00-04:00 | 2026-09-03T12:00:00-04:00 | active |\n"
        for session, compact, project, workspace in rows
    )
    path.write_text(header + body + "\n## Messages\n\n## Protocol\n", encoding="utf-8")
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_positive_controls_discover_canonical_worktree_ref_manifest_receipt_pointer_and_claim(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    state_root = tmp_path / "state"
    (state_root / "pending").mkdir(parents=True)
    (state_root / "local-handoff").mkdir(parents=True)
    manifest = {"schema_version": 2, "session_id": "session-a", "paths": [str(project / "CONTEXT.md")]}
    (state_root / "pending" / (hashlib.sha256(b"session-a").hexdigest() + ".json")).write_text(json.dumps(manifest), encoding="utf-8")
    (state_root / "local-handoff" / (hashlib.sha256(b"session-a").hexdigest() + ".json")).write_text(json.dumps({"session_id": "session-a", "readiness": "LOCAL_READY", "results": []}), encoding="utf-8")
    checkpoint_receipts = tmp_path / "checkpoint-receipts"
    checkpoint_receipts.mkdir()
    (checkpoint_receipts / "bound.json").write_text(
        json.dumps({"session_id": "session-a", "project_id": "alpha"}),
        encoding="utf-8",
    )
    pointer = tmp_path / "active.json"
    pointer.write_text(json.dumps({"project": str(project)}), encoding="utf-8")
    claims = board(tmp_path / "board.md", [("018f0000-0000-7000-8000-000000000001", "s-abcd-efgh-jkmn", "alpha", str(repo))])
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", repo_guard_root=state_root, checkpoint_receipt_root=checkpoint_receipts, coordination_board=claims, pointer=pointer, fetch=False)
    assert {item.source for item in report.candidates} >= {"canonical", "worktree", "ref", "manifest", "receipt", "checkpoint-receipt", "pointer", "claim"}


def test_canonical_behind_isolated_worktree_selects_newer_without_mutation(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    worktree = tmp_path / "newer"
    run("git", "worktree", "add", "-b", "feature/newer", str(worktree), cwd=repo)
    newer_project = worktree / "projects" / "alpha"
    newer = commit_version(worktree, newer_project, "2.0.0")
    original = run("git", "rev-parse", "HEAD", cwd=repo)
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=False)
    assert report.status == "PASS"
    assert report.selected_path == str(newer_project.resolve())
    assert report.selected_head == newer
    assert run("git", "rev-parse", "HEAD", cwd=repo) == original


def test_safe_fast_forward_preserves_unrelated_untracked_file(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    peer = tmp_path / "peer"
    run("git", "clone", str(tmp_path / "remote.git"), str(peer), cwd=tmp_path)
    run("git", "config", "user.email", "fixture@example.invalid", cwd=peer)
    run("git", "config", "user.name", "Fixture", cwd=peer)
    run("git", "config", "core.hooksPath", str(tmp_path / "fixture-hooks"), cwd=peer)
    newer = commit_version(peer, peer / "projects" / "alpha", "2.0.0")
    run("git", "push", "origin", "main", cwd=peer)
    unrelated = repo / "notes.local"
    unrelated.write_text("preserve\n", encoding="utf-8")
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=True, fast_forward_canonical=True)
    assert report.selected_head == newer
    assert unrelated.read_text(encoding="utf-8") == "preserve\n"


def test_fast_forward_refuses_non_upstream_local_ref(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    worktree = tmp_path / "newer"
    run("git", "worktree", "add", "-b", "feature/newer", str(worktree), cwd=repo)
    newer_project = worktree / "projects" / "alpha"
    newer = commit_version(worktree, newer_project, "2.0.0")
    run("git", "worktree", "remove", str(worktree), cwd=repo)
    original = run("git", "rev-parse", "HEAD", cwd=repo)
    report = state.resolve_project(
        "alpha",
        repo / "projects" / "index.yaml",
        fetch=True,
        fast_forward_canonical=True,
    )
    assert report.selected_head == newer
    assert report.selected_path is None
    assert any("not a fetched remote ref" in issue for issue in report.issues)
    assert run("git", "rev-parse", "HEAD", cwd=repo) == original


def test_local_ahead_is_selected_and_remote_ahead_is_selected_after_fetch(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    local = commit_version(repo, project, "2.0.0")
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=False)
    assert report.selected_head == local
    run("git", "reset", "--hard", "origin/main", cwd=repo)
    peer = tmp_path / "peer"
    run("git", "clone", str(tmp_path / "remote.git"), str(peer), cwd=tmp_path)
    run("git", "config", "user.email", "fixture@example.invalid", cwd=peer)
    run("git", "config", "user.name", "Fixture", cwd=peer)
    run("git", "config", "core.hooksPath", str(tmp_path / "fixture-hooks"), cwd=peer)
    remote = commit_version(peer, peer / "projects" / "alpha", "3.0.0")
    run("git", "push", "origin", "main", cwd=peer)
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=True)
    assert report.selected_head == remote


def test_diverged_project_states_fail_closed(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    run("git", "checkout", "-b", "feature/a", cwd=repo)
    commit_version(repo, project, "2.0.0")
    run("git", "checkout", "main", cwd=repo)
    commit_version(repo, project, "3.0.0")
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=False)
    assert report.status == "CONFLICT"
    assert any("diverg" in issue.lower() for issue in report.issues)


def test_deleted_registered_worktree_is_reported_not_ignored(tmp_path: Path) -> None:
    repo, _project = init_repo(tmp_path)
    raw_gitdir = Path(run("git", "rev-parse", "--git-common-dir", cwd=repo))
    gitdir = (repo / raw_gitdir).resolve() if not raw_gitdir.is_absolute() else raw_gitdir.resolve()
    metadata = gitdir / "worktrees" / "gone"
    metadata.mkdir(parents=True)
    (metadata / "gitdir").write_text(str(tmp_path / "gone" / ".git") + "\n", encoding="utf-8")
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=False)
    assert report.status == "UNKNOWN"
    assert any("missing worktree" in issue.lower() for issue in report.issues)


def test_dirty_attributed_project_file_is_local_recoverable(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    context = project / "CONTEXT.md"
    context.write_text(context.read_text(encoding="utf-8") + "interrupted\n", encoding="utf-8")
    state_root = tmp_path / "state"
    pending = state_root / "pending"
    pending.mkdir(parents=True)
    session = "session-a"
    payload = {"schema_version": 2, "session_id": session, "paths": [str(context)], "path_hashes": {str(context): sha(context)}}
    (pending / (hashlib.sha256(session.encode()).hexdigest() + ".json")).write_text(json.dumps(payload), encoding="utf-8")
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", repo_guard_root=state_root, fetch=False)
    assert report.status == "LOCAL_RECOVERABLE"
    assert report.selected_path == str(project.resolve())


def test_dirty_state_on_older_head_conflicts_with_newer_committed_state(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    newer_worktree = tmp_path / "newer"
    run("git", "worktree", "add", "-b", "feature/newer", str(newer_worktree), cwd=repo)
    commit_version(newer_worktree, newer_worktree / "projects" / "alpha", "2.0.0")
    context = project / "CONTEXT.md"
    context.write_text(context.read_text(encoding="utf-8") + "interrupted\n", encoding="utf-8")
    state_root = tmp_path / "state"
    pending = state_root / "pending"
    pending.mkdir(parents=True)
    session = "session-a"
    payload = {
        "schema_version": 2,
        "session_id": session,
        "paths": [str(context)],
        "path_hashes": {str(context): sha(context)},
    }
    (pending / (hashlib.sha256(session.encode()).hexdigest() + ".json")).write_text(
        json.dumps(payload), encoding="utf-8"
    )
    report = state.resolve_project(
        "alpha", repo / "projects" / "index.yaml", repo_guard_root=state_root, fetch=False
    )
    assert report.status == "CONFLICT"
    assert any("older" in issue.lower() for issue in report.issues)


def test_two_attributed_dirty_worktrees_with_different_hashes_conflict(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    other = tmp_path / "other"
    run("git", "worktree", "add", "-b", "feature/other", str(other), cwd=repo)
    paths = [project / "CONTEXT.md", other / "projects" / "alpha" / "CONTEXT.md"]
    paths[0].write_text(paths[0].read_text(encoding="utf-8") + "a\n", encoding="utf-8")
    paths[1].write_text(paths[1].read_text(encoding="utf-8") + "b\n", encoding="utf-8")
    root = tmp_path / "state" / "pending"
    root.mkdir(parents=True)
    for index, path in enumerate(paths):
        session = f"session-{index}"
        payload = {"schema_version": 2, "session_id": session, "paths": [str(path)], "path_hashes": {str(path): sha(path)}}
        (root / (hashlib.sha256(session.encode()).hexdigest() + ".json")).write_text(json.dumps(payload), encoding="utf-8")
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", repo_guard_root=root.parent, fetch=False)
    assert report.status == "CONFLICT"


def test_absent_pointer_does_not_block_and_stale_pointer_cannot_override(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", pointer=tmp_path / "absent.json", fetch=False)
    assert report.selected_path == str(project.resolve())
    stale = tmp_path / "stale.json"
    stale.write_text(json.dumps({"project": str(tmp_path / "gone")}), encoding="utf-8")
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", pointer=stale, fetch=False)
    assert report.selected_path == str(project.resolve())
    assert any("pointer" in issue.lower() for issue in report.issues)


def test_stale_index_date_is_derived_as_a_warning_not_selected_truth(tmp_path: Path) -> None:
    repo, _project = init_repo(tmp_path)
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=False)
    assert report.status == "PASS"
    assert any("last_session" in issue and "2026-09-03" in issue for issue in report.issues)


def test_future_date_in_session_body_does_not_advance_derived_session(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    (project / "sessions" / "2026-09.md").write_text(
        "### 2026-09-03 — current\n\nNext review: 2026-09-30.\n",
        encoding="utf-8",
    )
    report = state.resolve_project(
        "alpha", repo / "projects" / "index.yaml", fetch=False
    )
    assert any("derived value is 2026-09-03" in issue for issue in report.issues)
    assert not any("2026-09-30" in issue for issue in report.issues)


def test_internal_version_contradiction_is_semantic_failure(tmp_path: Path) -> None:
    _repo, project = init_repo(tmp_path)
    context = project / "CONTEXT.md"
    context.write_text(context.read_text(encoding="utf-8").replace("**Phase:** release 1.0.0", "**Phase:** current release 1.0.0") + "\nLater release shipped: v4.0.0.\n", encoding="utf-8")
    issues = state.semantic_issues(project)
    assert any("current" in issue.lower() and "4.0.0" in issue for issue in issues)


def test_structured_state_rejects_uncompiled_current_prose(tmp_path: Path) -> None:
    _repo, project = init_repo(tmp_path)
    context = project / "CONTEXT.md"
    context.write_text(
        context.read_text(encoding="utf-8")
        + "\n## Current handoff\n\n*State as of: 2026-09-03 (v0.9.0 installed)*\n",
        encoding="utf-8",
    )
    reference = project / "reference"
    reference.mkdir()
    (reference / "baselines.md").write_text(
        "# Baselines\n\n## Current reconciled baseline\n\nRelease v0.9.0.\n",
        encoding="utf-8",
    )
    state.build_operational_state(
        project,
        project_id="alpha",
        phase="release 1.0.0",
        status="active",
        controlling_plan="resources/artifacts/plan.md",
        accepted_baseline="1.0.0",
        next_actions=["finish"],
        last_session="2026-09-03",
        session_id="018f0000-0000-7000-8000-000000000001",
    )

    issues = state.semantic_issues(project)

    assert any(
        "uncompiled current-state prose" in issue and "CONTEXT.md" in issue
        for issue in issues
    )
    assert any(
        "uncompiled current-state prose" in issue
        and "reference/baselines.md" in issue
        for issue in issues
    )


def test_structured_state_rejects_setext_and_punctuated_current_labels(
    tmp_path: Path,
) -> None:
    _repo, project = init_repo(tmp_path)
    context = project / "CONTEXT.md"
    context.write_text(
        context.read_text(encoding="utf-8")
        + "\nAccepted baseline:\n------------------\n\nRelease v0.9.0.\n"
        + "\n## Current handoff:\n\n**State as of — v0.9.0**\n",
        encoding="utf-8",
    )
    reference = project / "reference"
    reference.mkdir()
    (reference / "baselines.md").write_text(
        "# Baselines\n\nNext checkpoint:\n================\n\nRelease v0.9.0.\n",
        encoding="utf-8",
    )
    state.build_operational_state(
        project,
        project_id="alpha",
        phase="release 1.0.0",
        status="active",
        controlling_plan="resources/artifacts/plan.md",
        accepted_baseline="1.0.0",
        next_actions=["finish"],
        last_session="2026-09-03",
        session_id="018f0000-0000-7000-8000-000000000001",
    )

    issues = state.semantic_issues(project)

    assert any(
        "uncompiled current-state prose" in issue
        and "CONTEXT.md" in issue
        and "line(s) 24, 29, 31" in issue
        for issue in issues
    )
    assert any(
        "uncompiled current-state prose" in issue
        and "reference/baselines.md" in issue
        and "line(s) 3" in issue
        for issue in issues
    )


def test_structured_state_allows_explicitly_historical_snapshots(tmp_path: Path) -> None:
    _repo, project = init_repo(tmp_path)
    context = project / "CONTEXT.md"
    context.write_text(
        "# Context\n\n## Handoff history\n\n"
        "Release v0.9.0 was accepted previously.\n"
        "current client-health checks were recorded in that historical snapshot.\n",
        encoding="utf-8",
    )
    reference = project / "reference"
    reference.mkdir()
    (reference / "baselines.md").write_text(
        "# Baselines\n\n## Accepted baselines — through 2026-08-18\n\n"
        "Release v0.9.0.\n",
        encoding="utf-8",
    )
    state.build_operational_state(
        project,
        project_id="alpha",
        phase="release 1.0.0",
        status="active",
        controlling_plan="resources/artifacts/plan.md",
        accepted_baseline="1.0.0",
        next_actions=["finish"],
        last_session="2026-09-03",
        session_id="018f0000-0000-7000-8000-000000000001",
    )

    assert not any(
        "uncompiled current-state prose" in issue
        for issue in state.semantic_issues(project)
    )


def test_checkpoint_requires_context_refresh_after_source_head_changes(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    claims = board(tmp_path / "board.md", [("018f0000-0000-7000-8000-000000000001", "s-abcd-efgh-jkmn", "alpha", str(repo))])
    receipt_root = tmp_path / "receipts"
    source = tmp_path / "source"
    source.mkdir()
    run("git", "init", "-b", "main", cwd=source)
    run("git", "config", "user.email", "fixture@example.invalid", cwd=source)
    run("git", "config", "user.name", "Fixture", cwd=source)
    run("git", "config", "core.hooksPath", str(tmp_path / "fixture-hooks"), cwd=source)
    (source / "code.txt").write_text("one\n", encoding="utf-8")
    run("git", "add", "code.txt", cwd=source)
    run("git", "commit", "-m", "source one", cwd=source)
    head = run("git", "rev-parse", "HEAD", cwd=source)
    state.build_operational_state(project, project_id="alpha", phase="release 1.0.0", status="active", controlling_plan="resources/artifacts/plan.md", accepted_baseline="1.0.0", next_actions=["finish"], last_session="2026-09-03", session_id="018f0000-0000-7000-8000-000000000001", source_heads={str(source): head})
    state.checkpoint_project(project, session_id="018f0000-0000-7000-8000-000000000001", coordination_board=claims, receipt_root=receipt_root, source_heads={str(source): head})
    (source / "code.txt").write_text("two\n", encoding="utf-8")
    run("git", "add", "code.txt", cwd=source)
    run("git", "commit", "-m", "source two", cwd=source)
    newer = run("git", "rev-parse", "HEAD", cwd=source)
    verdict, issues = state.validate_checkpoint(project, session_id="018f0000-0000-7000-8000-000000000001", coordination_board=claims, receipt_root=receipt_root, source_heads={str(source): newer})
    assert verdict == "FAIL"
    assert any("source" in issue.lower() for issue in issues)


def test_operational_state_compiles_and_validates_bounded_context(tmp_path: Path) -> None:
    _repo, project = init_repo(tmp_path)
    payload = state.build_operational_state(
        project,
        project_id="alpha",
        phase="release 1.0.0",
        status="active",
        controlling_plan="resources/artifacts/plan.md",
        accepted_baseline="1.0.0",
        next_actions=["finish"],
        last_session="2026-09-03",
        session_id="018f0000-0000-7000-8000-000000000001",
    )
    context = (project / "CONTEXT.md").read_text(encoding="utf-8")
    assert context.count("<!-- synthesis-current-state:start -->") == 1
    assert "**Phase:** release 1.0.0" in context
    assert not state.semantic_issues(project)
    (project / "CONTEXT.md").write_text(
        context.replace("**Phase:** release 1.0.0", "**Phase:** release 0.9.0", 1),
        encoding="utf-8",
    )
    assert any("compiled" in issue for issue in state.semantic_issues(project))
    assert any("changed after" in issue for issue in state.semantic_issues(project))
    assert payload["content_hashes"]["CONTEXT.md"] != sha(project / "CONTEXT.md")


def test_semantic_state_detects_stale_hashed_reference(tmp_path: Path) -> None:
    _repo, project = init_repo(tmp_path)
    state.build_operational_state(
        project,
        project_id="alpha",
        phase="release 1.0.0",
        status="active",
        controlling_plan="resources/artifacts/plan.md",
        accepted_baseline="1.0.0",
        next_actions=["finish"],
        last_session="2026-09-03",
        session_id="018f0000-0000-7000-8000-000000000001",
    )
    (project / "REFERENCE.md").write_text("# Reference\n\nchanged\n", encoding="utf-8")
    assert any("changed after" in issue for issue in state.semantic_issues(project))


@pytest.mark.parametrize("writer,receiver", [("adapter-a", "adapter-b"), ("adapter-b", "adapter-a")])
def test_handoff_directions_share_one_receipt_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    writer: str,
    receiver: str,
) -> None:
    repo, project = init_repo(tmp_path)
    session = "018f0000-0000-7000-8000-000000000001"
    claims = board(tmp_path / "board.md", [(session, "s-abcd-efgh-jkmn", "alpha", str(repo))])
    receipt_root = tmp_path / "receipts"
    state.build_operational_state(project, project_id="alpha", phase="release 1.0.0", status="active", controlling_plan="resources/artifacts/plan.md", accepted_baseline="1.0.0", next_actions=["finish"], last_session="2026-09-03", session_id=session)
    monkeypatch.setenv("SYNTHESIS_LIFECYCLE_ADAPTER", writer)
    receipt = state.checkpoint_project(project, session_id=session, coordination_board=claims, receipt_root=receipt_root)
    assert receipt["writer_adapter"] == writer
    monkeypatch.setenv("SYNTHESIS_LIFECYCLE_ADAPTER", receiver)
    verdict, issues = state.validate_checkpoint(project, session_id=session, coordination_board=claims, receipt_root=receipt_root)
    assert (verdict, issues) == ("PASS", [])


def test_clean_stop_passes_and_interrupted_stop_is_recoverable_not_clean(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    session = "018f0000-0000-7000-8000-000000000001"
    claims = board(tmp_path / "board.md", [(session, "s-abcd-efgh-jkmn", "alpha", str(repo))])
    receipts = tmp_path / "receipts"
    state.build_operational_state(project, project_id="alpha", phase="release 1.0.0", status="active", controlling_plan="resources/artifacts/plan.md", accepted_baseline="1.0.0", next_actions=["finish"], last_session="2026-09-03", session_id=session)
    state.checkpoint_project(project, session_id=session, coordination_board=claims, receipt_root=receipts)
    assert state.validate_checkpoint(project, session_id=session, coordination_board=claims, receipt_root=receipts)[0] == "PASS"
    (project / "REFERENCE.md").write_text("interrupted\n", encoding="utf-8")
    assert state.validate_checkpoint(project, session_id=session, coordination_board=claims, receipt_root=receipts)[0] == "LOCAL_RECOVERABLE"


def test_unrelated_dirty_and_staged_files_survive_recovery(tmp_path: Path) -> None:
    repo, _project = init_repo(tmp_path)
    (repo / "unrelated.txt").write_text("staged\n", encoding="utf-8")
    run("git", "add", "unrelated.txt", cwd=repo)
    (repo / "other.local").write_text("dirty\n", encoding="utf-8")
    before = run("git", "status", "--porcelain=v1", cwd=repo)
    state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=False, fast_forward_canonical=True)
    assert run("git", "status", "--porcelain=v1", cwd=repo) == before


def test_unrelated_project_session_does_not_block_checkpoint(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    session = "018f0000-0000-7000-8000-000000000001"
    claims = board(tmp_path / "board.md", [(session, "s-abcd-efgh-jkmn", "alpha", str(repo)), ("018f0000-0000-7000-8000-000000000002", "s-npqr-stuv-wxyz", "beta", str(tmp_path / "elsewhere"))])
    state.build_operational_state(project, project_id="alpha", phase="release 1.0.0", status="active", controlling_plan="resources/artifacts/plan.md", accepted_baseline="1.0.0", next_actions=["finish"], last_session="2026-09-03", session_id=session)
    receipt = state.checkpoint_project(project, session_id=session, coordination_board=claims, receipt_root=tmp_path / "receipts")
    assert receipt["session_id"] == session


def test_unreachable_remote_is_unknown_not_green(tmp_path: Path) -> None:
    repo, _project = init_repo(tmp_path)
    run("git", "remote", "set-url", "origin", str(tmp_path / "missing.git"), cwd=repo)
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=True)
    assert report.status == "UNKNOWN"
    assert any("fetch" in issue.lower() for issue in report.issues)


def test_unreachable_coordination_lease_is_unknown_not_green(tmp_path: Path) -> None:
    repo, _project = init_repo(tmp_path)
    claims = board(
        tmp_path / "board.md",
        [("018f0000-0000-7000-8000-000000000001", "s-abcd-efgh-jkmn", "alpha", str(repo))],
    )
    report = state.resolve_project(
        "alpha",
        repo / "projects" / "index.yaml",
        coordination_board=claims,
        fetch=False,
        refresh_coordination=True,
    )
    assert report.status == "UNKNOWN"
    assert any("lease refresh" in issue.lower() for issue in report.issues)


def test_installed_newer_than_loaded_registry_is_a_live_plane_failure(tmp_path: Path) -> None:
    repo, _project = init_repo(tmp_path)
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=False)
    report.planes.update({"source": "PASS", "installed": "PASS", "live": "FAIL"})
    assert report.selected_path is not None
    assert report.planes == {"source": "PASS", "installed": "PASS", "live": "FAIL", "continuity": "PASS"}


def test_lifecycle_hook_issues_session_bound_clean_receipt(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    session = "018f0000-0000-7000-8000-000000000001"
    claims = board(tmp_path / "board.md", [(session, "s-abcd-efgh-jkmn", "alpha", str(repo))])
    receipts = tmp_path / "receipts"
    state.build_operational_state(
        project,
        project_id="alpha",
        phase="release 1.0.0",
        status="active",
        controlling_plan="resources/artifacts/plan.md",
        accepted_baseline="1.0.0",
        next_actions=["finish"],
        last_session="2026-09-03",
        session_id=session,
    )
    verdict, issues = state.checkpoint_hook(
        {"session_id": session, "cwd": str(repo)},
        coordination_board=claims,
        receipt_root=receipts,
        refresh_coordination=False,
    )
    assert (verdict, issues) == ("PASS", [])
    receipt = json.loads(next(receipts.glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["session_id"] == session
    assert receipt["project_id"] == "alpha"


def test_lifecycle_hook_refuses_semantically_incomplete_stop(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    session = "018f0000-0000-7000-8000-000000000001"
    claims = board(tmp_path / "board.md", [(session, "s-abcd-efgh-jkmn", "alpha", str(repo))])
    state.build_operational_state(
        project,
        project_id="alpha",
        phase="release 1.0.0",
        status="active",
        controlling_plan="resources/artifacts/plan.md",
        accepted_baseline="1.0.0",
        next_actions=["finish"],
        last_session="2026-09-03",
        session_id=session,
    )
    (project / "CONTEXT.md").write_text("# stale after work\n", encoding="utf-8")
    verdict, issues = state.checkpoint_hook(
        {"session_id": session, "cwd": str(repo)},
        coordination_board=claims,
        receipt_root=tmp_path / "receipts",
        refresh_coordination=False,
    )
    assert verdict == "FAIL"
    assert any("changed" in issue for issue in issues)


def test_lifecycle_hook_fails_closed_when_lease_cannot_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _project = init_repo(tmp_path)
    session = "018f0000-0000-7000-8000-000000000001"
    claims = board(
        tmp_path / "board.md",
        [(session, "s-abcd-efgh-jkmn", "alpha", str(repo))],
    )
    monkeypatch.setattr(
        state,
        "_refresh_coordination_board",
        lambda _path: "coordination lease refresh failed: fixture outage",
    )
    verdict, issues = state.checkpoint_hook(
        {"session_id": session, "cwd": str(repo)},
        coordination_board=claims,
        receipt_root=tmp_path / "receipts",
    )
    assert verdict == "FAIL"
    assert issues == ["coordination lease refresh failed: fixture outage"]


def test_project_state_reliability_release_contract_is_coherent() -> None:
    root = Path(__file__).resolve().parents[3]
    versions = {
        json.loads((root / path).read_text(encoding="utf-8"))["version"]
        for path in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json")
    }
    assert len(versions) == 1
    version = versions.pop()
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    newest = next(line for line in changelog.splitlines() if line.startswith("## ["))
    assert newest.startswith(f"## [{version}] - ")
    assert f"Release **{version}**" in (root / "README.md").read_text(encoding="utf-8")
    hooks = json.loads((root / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for group in hooks["hooks"]["Stop"]
        for hook in group["hooks"]
    ]
    assert any(command.endswith("project_state.py hook") for command in commands)
    # The reliability tranche shipped these skills at these versions; later
    # releases may bump any of them, so the contract is a floor, never a
    # literal to re-pin by hand (a hand-pinned literal broke the first
    # release after this test was written).
    floors = {
        "synthesis-project-management": (2, 12, 0),
        "synthesis-context-lifecycle": (1, 18, 0),
        "synthesis-agent-conformance": (1, 9, 1),
        "synthesis-autopilot": (2, 1, 0),
        "synthesis-repo-guard": (2, 4, 0),
    }
    for skill, floor in floors.items():
        text = (root / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        match = re.search(r'^\s*version:\s*"(\d+)\.(\d+)\.(\d+)"\s*$', text, re.M)
        assert match, f"{skill} declares no semantic version"
        declared = tuple(int(part) for part in match.groups())
        assert declared >= floor, f"{skill} {declared} is below the reliability floor {floor}"
