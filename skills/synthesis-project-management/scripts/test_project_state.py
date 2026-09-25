from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import project_state as state

import coordination as engine


@pytest.mark.parametrize("reader", [state.read_operational_state, state._load_json])
def test_state_json_shared_size_boundary(tmp_path, monkeypatch, reader):
    monkeypatch.setattr(state, "MAX_STATE_JSON_BYTES", 128)
    path = tmp_path / state.STATE_FILE
    raw = b'{"schema_version": 1}'
    path.write_bytes(raw + b" " * (128 - len(raw)))
    assert reader(path) == {"schema_version": 1}
    assert state._sha_file(path) == hashlib.sha256(path.read_bytes()).hexdigest()
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(state.ProjectStateError, match="128-byte limit"):
        reader(path)
    with pytest.raises(state.ProjectStateError, match="128-byte limit"):
        state._sha_file(path)


@pytest.mark.parametrize("raw", [
    b'{"status": "active", "status": "archived"}',
    b'{"nested": {"value": 1, "value": 2}}',
    b'{"truncated":', b"[]", b"null", b'{} trailing', b'{"invalid": "\xff"}',
    b'{"value": NaN}', b'{"value": Infinity}', b'{"value": 1e309}',
    b'{"nested":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}",
], ids=["duplicate", "nested-duplicate", "truncated", "array", "null", "trailing", "utf8", "nan", "infinity", "float-overflow", "depth"])
def test_state_json_rejects_malformed_objects(tmp_path, raw):
    path = tmp_path / state.STATE_FILE
    path.write_bytes(raw)
    with pytest.raises(state.ProjectStateError):
        state.read_operational_state(path)
    assert path.read_bytes() == raw


def test_state_json_depth_boundary_ignores_escaped_string_content(tmp_path):
    path = tmp_path / state.STATE_FILE
    literal = json.dumps("[{" * 100 + '\\"' + "]}" * 100)
    nested = "[" * (state.MAX_JSON_DEPTH - 1) + literal + "]" * (state.MAX_JSON_DEPTH - 1)
    raw = '{"value":' + nested + "}"
    path.write_text(raw)
    assert state.read_operational_state(path) == json.loads(raw)
    path.write_text('{"value":[' + nested + "]}")
    with pytest.raises(state.ProjectStateError, match="nesting"):
        state.read_operational_state(path)


@pytest.mark.parametrize("kind", ["directory", "symlink", "broken-symlink", "fifo"])
def test_state_json_refuses_nonregular_inputs(tmp_path, kind):
    path = tmp_path / state.STATE_FILE
    if kind == "directory":
        path.mkdir()
    elif kind == "fifo":
        os.mkfifo(path)
    else:
        target = tmp_path / "target.json"
        if kind == "symlink":
            target.write_text("{}")
        path.symlink_to(target)
    with pytest.raises(state.ProjectStateError, match="regular nonsymlink"):
        state.read_operational_state(path)


def test_state_json_refuses_symlink_raced_after_lstat(tmp_path, monkeypatch):
    path = tmp_path / state.STATE_FILE
    path.write_text("{}")
    target = tmp_path / "target.json"
    target.write_text("{}")
    original = os.open

    def replace_then_open(candidate, flags, *args, **kwargs):
        if candidate == path:
            path.unlink()
            path.symlink_to(target)
        return original(candidate, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", replace_then_open)
    with pytest.raises(state.ProjectStateError):
        state.read_operational_state(path)


def test_state_json_actual_read_is_bounded_when_input_grows(tmp_path, monkeypatch):
    path = tmp_path / state.STATE_FILE
    path.write_text("{}")
    reads = []
    original = os.fdopen

    class GrowingFile:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.handle.close()

        def fileno(self):
            return self.handle.fileno()

        def read(self, size):
            reads.append(size)
            with path.open("ab") as writer:
                writer.write(b" " * 256)
            return self.handle.read(size)

    monkeypatch.setattr(os, "fdopen", lambda *args: GrowingFile(original(*args)))
    with pytest.raises(state.ProjectStateError, match="128-byte limit"):
        state.read_json_object(path, max_bytes=128)
    assert reads == [129]


@pytest.mark.parametrize("change", ["replace", "modify"])
def test_state_json_refuses_changed_read_snapshot(tmp_path, monkeypatch, change):
    path = tmp_path / state.STATE_FILE
    path.write_text('{"value": 1}')
    original = os.fstat
    calls = 0

    def change_before_after_stat(fd):
        nonlocal calls
        calls += 1
        if calls == 2:
            if change == "replace":
                replacement = tmp_path / "replacement.json"
                replacement.write_text('{"value": 1}')
                os.replace(replacement, path)
            else:
                before = path.stat()
                path.write_text('{"value": 2}')
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000))
        return original(fd)

    monkeypatch.setattr(os, "fstat", change_before_after_stat)
    with pytest.raises(state.ProjectStateError, match="changed during reading"):
        state.read_operational_state(path)


def test_state_compiler_refuses_oversize_before_changing_project(tmp_path, monkeypatch):
    _repo, project = init_repo(tmp_path)
    parameters = dict(project_id="alpha", phase="planning", status="active",
        controlling_plan="resources/artifacts/plan.md", accepted_baseline="fixture",
        next_actions=["Review"], last_session="2026-09-03", session_id="fixture")
    state.build_operational_state(project, **parameters)
    paths = (project / "CONTEXT.md", project / state.STATE_FILE)
    before = {path: path.read_bytes() for path in paths}
    monkeypatch.setattr(state, "MAX_STATE_JSON_BYTES", 128)
    with pytest.raises(state.ProjectStateError, match="128-byte limit"):
        state.build_operational_state(project, **{**parameters, "phase": "changed"})
    assert {path: path.read_bytes() for path in paths} == before
    assert not list(project.glob(".*.tmp"))


@pytest.mark.parametrize("consumer", ["semantic", "doctor"])
def test_broken_state_symlink_is_invalid_evidence_not_legacy_absence(tmp_path, consumer):
    _repo, project = init_repo(tmp_path)
    state.build_operational_state(project, project_id="alpha", phase="planning", status="active",
        controlling_plan="resources/artifacts/plan.md", accepted_baseline="fixture",
        next_actions=["Review"], last_session="2026-09-03", session_id="fixture")
    assert state.semantic_issues(project) == []
    path = project / state.STATE_FILE
    path.unlink()
    path.symlink_to(tmp_path / "missing-state.json")
    if consumer == "semantic":
        assert any("regular nonsymlink" in issue for issue in state.semantic_issues(project))
    else:
        doctor = (Path(__file__).resolve().parents[2] / "synthesis-context-lifecycle"
                  / "scripts" / "context_doctor.py")
        result = subprocess.run([sys.executable, "-B", str(doctor), "--project", str(project),
            "--readiness", "local", "--no-report-cache", "--json"], capture_output=True, text=True)
        report = json.loads(result.stdout)
        assert result.returncode == 1 and report["ok"] is False
        assert any(finding["check"] == "semantic-current-state" and finding["severity"] == "defect"
                   and "regular nonsymlink" in finding["message"] for finding in report["findings"])
    assert path.is_symlink() and not path.exists()


@pytest.mark.parametrize("client", ["codex", "claude"])
@pytest.mark.parametrize("repeat", [False, True])
def test_stop_feedback_is_bounded_without_accepting_failed_checkpoint(
    client: str, repeat: bool, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    native = "018f0000-0000-7000-8000-000000000001"
    payload = {"hook_event_name": "Stop", "session_id": native,
               "turn_id": "fixture-turn", "stop_hook_active": repeat}
    monkeypatch.setattr(state, "observer_native_identity", lambda _payload: (client, native))
    code = state._emit_checkpoint_hook("UNKNOWN", ["fixture checkpoint is unresolved"], payload)
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert code == 0
    report = json.loads(output["systemMessage"].removeprefix("PROJECT_CHECKPOINT_JSON: "))
    assert report == {"status": "UNKNOWN", "issues": ["fixture checkpoint is unresolved"],
                      "checkpoint_accepted": False}
    # An unreserved first Stop cannot request another turn either.
    assert output["continue"] is False
    assert "unresolved" in output["stopReason"]
    assert "decision" not in output and "reason" not in output


@pytest.mark.parametrize("payload", [{}, {"hook_event_name": "Stop"},
    {"hook_event_name": "Stop", "session_id": "fixture", "stop_hook_active": "false"}])
def test_stop_unidentifiable_failure_is_terminal(payload, capsys) -> None:
    assert state._emit_checkpoint_hook("UNKNOWN", ["identity unavailable"], payload) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["continue"] is False
    assert output.get("decision") != "block"
    assert '"checkpoint_accepted": false' in output["systemMessage"]


@pytest.mark.parametrize("verdict", ["PASS", "NOT_APPLICABLE"])
def test_repeated_stop_still_evaluates_and_reports_healthy_checkpoint(verdict, capsys) -> None:
    payload = {"hook_event_name": "Stop", "session_id": "018f0000-0000-7000-8000-000000000001",
               "stop_hook_active": True}
    assert state._emit_checkpoint_hook(verdict, [], payload) == 0
    output = json.loads(capsys.readouterr().out)
    assert "continue" not in output
    assert "decision" not in output
    assert f'"status": "{verdict}"' in output["systemMessage"]


def test_non_stop_checkpoint_failure_retains_nonzero_contract(capsys) -> None:
    assert state._emit_checkpoint_hook("FAIL", ["fixture failure"], {"hook_event_name": "SessionStart"}) == 2
    captured = capsys.readouterr()
    assert '"checkpoint_accepted": false' in json.loads(captured.out)["systemMessage"]
    assert "fixture failure" in captured.err


def test_stop_failure_remains_terminal_when_shared_adapter_cannot_import(monkeypatch, capsys) -> None:
    import builtins
    original = builtins.__import__

    def missing_adapter(name, *args, **kwargs):
        if name == "release_runtime":
            raise ImportError("fixture missing Stop adapter")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_adapter)
    payload = {"hook_event_name": "Stop", "session_id": "018f0000-0000-7000-8000-000000000001",
               "stop_hook_active": False}
    assert state._emit_checkpoint_hook("FAIL", ["fixture failure"], payload) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["continue"] is False
    assert output.get("decision") != "block"
    assert '"checkpoint_accepted": false' in output["systemMessage"]


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
        "# Board\nSchema: v4\n\n## Active sessions\n\n"
        "| session uuid | compact id | speakable id v1 | legacy id | agent | machine | client session ref | project | "
        "started | heartbeat | mode | workspace(s) / branch | goal | claimed areas (advisory lock) | context role | status |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    body = "".join(
        f"| {session} | {compact} | words-1 | | agent | machine | tool:{session} | {project} | "
        f"2026-09-03T12:00:00-04:00 | 2026-09-03T12:00:00-04:00 | interactive | {workspace} | fixture | "
        f"{workspace}/projects/{project}/** | owner | active |\n"
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


@pytest.mark.parametrize(
    "recorded",
    [
        "Candidate 4.95.7 is under verification, not released.",
        "Release candidate v4.95.7 remains under verification.",
        "Planned release: v4.95.7.",
        "v4.95.7 is not released.",
        "Target release v4.95.7, pending publication.",
        "Documentation example: v9.0.0.",
        "CI verified candidate v4.95.7; publication pending.",
    ],
)
def test_unreleased_or_reference_versions_do_not_claim_release_currency(
    tmp_path: Path, recorded: str,
) -> None:
    _repo, project = init_repo(tmp_path, version="4.95.6")
    context = project / "CONTEXT.md"
    context.write_text(context.read_text(encoding="utf-8") + "\n" + recorded + "\n")

    issues = state.semantic_issues(project)

    assert not any("older than later recorded release" in issue for issue in issues)
    assert recorded in context.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "recorded",
    [
        "Candidate v4.95.8 is not released; later release shipped: v4.95.7.",
        "Released v4.95.7; planned candidate v4.95.8.",
        "v4.95.7 shipped; v4.95.8 is not released.",
        "Released v4.95.7 and candidate v4.95.8.",
        "Candidate v4.95.8, released v4.95.7.",
        "Released v4.95.7, with v4.95.8 planned.",
    ],
)
def test_mixed_candidate_and_shipped_assertions_keep_actual_release_evidence(
    tmp_path: Path, recorded: str,
) -> None:
    _repo, project = init_repo(tmp_path, version="4.95.6")
    context = project / "CONTEXT.md"
    context.write_text(context.read_text(encoding="utf-8") + "\n" + recorded + "\n")

    issues = state.semantic_issues(project)

    assert [issue for issue in issues if "older than later recorded release" in issue] == [
        "current release 4.95.6 is older than later recorded release 4.95.7"
    ]


def test_structured_candidate_description_preserves_accepted_release_baseline(
    tmp_path: Path,
) -> None:
    _repo, project = init_repo(tmp_path, version="4.95.6")
    context = project / "CONTEXT.md"
    context.write_text(
        "# Context\n\nCandidate 4.95.7 is authored; public release remains pending.\n",
        encoding="utf-8",
    )
    baseline = (
        "4.95.6 dual-client reload accepted; 4.95.7 runtime and preserved-change "
        "candidate under verification, not released"
    )
    state.build_operational_state(
        project,
        project_id="alpha",
        phase="Runtime currency and held-change integration in progress",
        status="active",
        controlling_plan="resources/artifacts/plan.md",
        accepted_baseline=baseline,
        next_actions=["Complete candidate verification and public release"],
        last_session="2026-09-03",
        session_id="018f0000-0000-7000-8000-000000000001",
    )

    issues = state.semantic_issues(project)

    assert not issues
    assert baseline in context.read_text(encoding="utf-8")


def test_future_phase_candidate_cannot_mask_stale_structured_accepted_baseline(
    tmp_path: Path,
) -> None:
    _repo, project = init_repo(tmp_path, version="4.95.6")
    context = project / "CONTEXT.md"
    context.write_text(
        "# Context\n\nLater release shipped: v4.95.7.\n", encoding="utf-8",
    )
    state.build_operational_state(
        project,
        project_id="alpha",
        phase="Verify release candidate v4.95.8, not released",
        status="active",
        controlling_plan="resources/artifacts/plan.md",
        accepted_baseline="4.95.6 accepted release",
        next_actions=["Complete candidate verification"],
        last_session="2026-09-03",
        session_id="018f0000-0000-7000-8000-000000000001",
    )

    issues = state.semantic_issues(project)

    assert [issue for issue in issues if "older than later recorded release" in issue] == [
        "current release 4.95.6 is older than later recorded release 4.95.7"
    ]


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
    from coordination_schema import identity_from_uuid

    repo, _project = init_repo(tmp_path)
    identity = identity_from_uuid("018f0000-0000-7000-8000-000000000001")
    claims = board(
        tmp_path / "board.md",
        [(identity.session_uuid, identity.compact_id, "alpha", str(repo))],
    )
    claims.write_text(claims.read_text(encoding="utf-8").replace("words-1", identity.speakable_id), encoding="utf-8")
    # This is a remote failure test, not a rejection of a valid local board.
    (claims.parent / "lease.json").write_text(json.dumps({"remote": str(tmp_path / "missing-lease.git")}))
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


@pytest.mark.parametrize("change", ["edit", "delete"])
def test_cross_project_plan_change_invalidates_clean_checkpoint(tmp_path: Path, change: str) -> None:
    repo, project = init_repo(tmp_path)
    plan = repo / "projects" / "program" / "resources" / "artifacts" / "work-plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# Parent plan\n", encoding="utf-8")
    session = "018f0000-0000-7000-8000-000000000001"
    claims = board(tmp_path / "board.md", [(session, "s-abcd-efgh-jkmn", "alpha", str(repo))])
    receipts = tmp_path / "receipts"
    state.build_operational_state(
        project, project_id="alpha", phase="release 1.0.0", status="active",
        controlling_plan="../program/resources/artifacts/work-plan.md", accepted_baseline="1.0.0",
        next_actions=["finish"], last_session="2026-09-03", session_id=session,
    )
    state.checkpoint_project(project, session_id=session, coordination_board=claims, receipt_root=receipts)
    assert state.validate_checkpoint(project, session_id=session, coordination_board=claims, receipt_root=receipts) == ("PASS", [])
    if change == "edit":
        plan.write_text("# Changed parent plan\n", encoding="utf-8")
    else:
        plan.unlink()
    verdict, issues = state.validate_checkpoint(project, session_id=session, coordination_board=claims, receipt_root=receipts)
    assert verdict == "LOCAL_RECOVERABLE"
    assert any("plan" in issue or "durable project files" in issue for issue in issues)


@pytest.mark.parametrize("client", ["cc", "codex"])
def test_lifecycle_hook_issues_session_bound_clean_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client: str
) -> None:
    repo, project = init_repo(tmp_path)
    session = "018f0000-0000-7000-8000-000000000001"
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", f"{client}:{session}")
    claims = board(tmp_path / "board.md", [(session, "s-abcd-efgh-jkmn", "alpha", str(repo))])
    claims.write_text(claims.read_text().replace(f"tool:{session}", f"{client}:{session}"))
    receipts = tmp_path / "receipts"
    payload = native_hook_fixture(tmp_path, monkeypatch, client, session, repo)
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
        payload,
        coordination_board=claims,
        receipt_root=receipts,
        refresh_coordination=False,
    )
    assert (verdict, issues) == ("PASS", [])
    receipt = json.loads(next(receipts.glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["session_id"] == session
    assert receipt["project_id"] == "alpha"


@pytest.mark.parametrize("client", ["cc", "codex"])
def test_lifecycle_hook_refuses_semantically_incomplete_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client: str
) -> None:
    repo, project = init_repo(tmp_path)
    session = "018f0000-0000-7000-8000-000000000001"
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", f"{client}:{session}")
    claims = board(tmp_path / "board.md", [(session, "s-abcd-efgh-jkmn", "alpha", str(repo))])
    claims.write_text(claims.read_text().replace(f"tool:{session}", f"{client}:{session}"))
    payload = native_hook_fixture(tmp_path, monkeypatch, client, session, repo)
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
        payload,
        coordination_board=claims,
        receipt_root=tmp_path / "receipts",
        refresh_coordination=False,
    )
    assert verdict == "FAIL"
    assert any("changed" in issue for issue in issues)


def native_hook_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client: str, native: str, cwd: Path) -> dict:
    if client == "cc":
        root = tmp_path / ".claude"
        transcript = root / "projects" / "fixture" / f"{native}.jsonl"
        record = {"type": "user", "sessionId": native}
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(root))
    else:
        root = tmp_path / ".codex"
        transcript = root / "sessions" / "fixture.jsonl"
        record = {"type": "session_meta", "payload": {"id": native}}
        monkeypatch.setenv("CODEX_HOME", str(root))
    transcript.parent.mkdir(parents=True)
    transcript.write_text(json.dumps(record) + "\n")
    return {"session_id": native, "cwd": str(cwd), "transcript_path": str(transcript)}


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
        lambda _path, **_kw: "coordination lease refresh failed: fixture outage",
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


def test_observer_stop_resolves_muse_session_from_store_without_transcript_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = "019fff79-5858-7993-a329-b301bccf5d01"
    log = (
        tmp_path / "muse-sessions" / "2026" / "09" / "17"
        / session_id / "session.jsonl"
    )
    log.parent.mkdir(parents=True)
    log.write_text(
        json.dumps({"stream": {"kind": "session", "id": session_id}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MUSE_SESSIONS_DIR", str(tmp_path / "muse-sessions"))
    assert state._observer_native_identity({"session_id": session_id}) == (
        "muse",
        session_id,
    )
    with pytest.raises(state.ProjectStateError, match="transcript path"):
        state._observer_native_identity(
            {"session_id": "019fff79-5858-7993-a329-b301bccf5d02"}
        )


def _stop_args(board: Path, **values):
    return type("Args", (), {"board": board, **values})()


def test_stop_honors_open_release_requests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # S13 layer 2: the Stop hook answers open requests best-effort; the
    # reply blocks on the bus are the record.
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    board = tmp_path / "board.md"
    area = f"{repo}/claimed/**"
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:holder-x")
    assert engine.command_claim(_stop_args(
        board, id=None, agent="agent", machine="m1", project="project-h",
        mode="interactive", goal="g", workspace=[f"{repo} @ main"],
        area=[area], context_role="owner",
    )) == 0
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:requester-x")
    assert engine.command_claim(_stop_args(
        board, id=None, agent="agent", machine="m1", project="project-q",
        mode="interactive", goal="g", workspace=["/tmp/repo-q @ main"],
        area=["elsewhere/**"], context_role="owner",
    )) == 0
    holder = [row for row in engine.rows(board.read_text(encoding="utf-8")) if row.project == "project-h"][0]
    assert engine.command_request_narrow(_stop_args(
        board, holder=holder.compact_id, area=[area], reason="need it",
    )) == 0
    [req] = engine.open_release_requests(board.read_text(encoding="utf-8"))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:holder-x")
    state._honor_release_requests_at_stop(
        board, {"session uuid": holder.session_uuid},
        {"hook_event_name": "Stop", "cwd": str(repo)},
    )
    assert engine.parse_release_replies(board.read_text(encoding="utf-8")) == {req.id: "narrowed"}
    # A row without identity never crashes the hook.
    state._honor_release_requests_at_stop(board, {}, {"hook_event_name": "Stop"})


def _claim_row(project, areas="", workspaces="", session="s-test"):
    return {
        "project": project,
        "claimed areas (advisory lock)": areas,
        "workspace(s) / branch": workspaces,
        "session uuid": session,
    }


def test_project_from_claim_ignores_phantom_registry_dirs(tmp_path, monkeypatch):
    """Intake 31: a claimed root whose projects/ merely carries an index.yaml
    must not manufacture a candidate that collides with the real dir."""
    knowledge = tmp_path / "knowledge"
    (knowledge / "projects").mkdir(parents=True)
    (knowledge / "projects" / "index.yaml").write_text("csa-x:\n  status: active\n")
    real = tmp_path / "real" / "projects" / "csa-x"
    real.mkdir(parents=True)
    seen = []
    monkeypatch.setattr(
        state, "checkpoint_applicability",
        lambda project: seen.append(Path(project)) or ("APPLICABLE", []),
    )
    row = _claim_row("csa-x", areas=f"{knowledge} @ main",
                     workspaces=f"{real} @ main")
    assert state._project_from_claim(row) == real.resolve()
    assert seen == [real.resolve()]


def test_project_from_claim_error_names_candidates(tmp_path):
    first = tmp_path / "a" / "projects" / "proj"
    second = tmp_path / "b" / "projects" / "proj"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    row = _claim_row("proj", areas=f"{first},{second}")
    with pytest.raises(state.ProjectStateError) as exc:
        state._project_from_claim(row)
    assert str(first.resolve()) in str(exc.value)
    assert str(second.resolve()) in str(exc.value)


def test_project_from_claim_explicit_phantom_keeps_old_admission(tmp_path, monkeypatch):
    """An explicitly claimed .../projects/<id> that does not exist yet keeps
    the old admission (intake flow claims before first write)."""
    ghost = tmp_path / "repo" / "projects" / "newbie"
    (tmp_path / "repo" / "projects").mkdir(parents=True)
    seen = []
    monkeypatch.setattr(
        state, "checkpoint_applicability",
        lambda project: seen.append(Path(project)) or ("APPLICABLE", []),
    )
    row = _claim_row("newbie", areas=str(ghost))
    assert state._project_from_claim(row) == ghost.resolve()
    assert seen == [ghost.resolve()]


def test_project_from_claim_without_projects_returns_none(tmp_path):
    bare = tmp_path / "bare"
    bare.mkdir()
    row = _claim_row("proj", areas=str(bare))
    assert state._project_from_claim(row) is None


@pytest.mark.parametrize("passive", [False, True])
def test_local_only_board_refresh_uses_existing_coordination_authority(tmp_path, passive):
    claims = tmp_path / "coordination" / "active-sessions.md"
    claims.parent.mkdir()
    claims.write_text(engine.template())
    assert engine.require_fresh_board(claims) == {"configured": False}
    assert state._refresh_coordination_board(claims, passive_stop=passive) is None


def test_hook_default_honors_explicit_board_environment(tmp_path, monkeypatch):
    claims = tmp_path / "isolated" / "board.md"
    monkeypatch.setenv("SYNTHESIS_COORDINATION_BOARD", str(claims))
    assert state._parser().parse_args(["hook"]).coordination_board == claims
    explicit = tmp_path / "explicit.md"
    assert state._parser().parse_args(["hook", "--coordination-board", str(explicit)]).coordination_board == explicit


@pytest.mark.parametrize("lease", [
    {"configured": True, "refreshed": False},
    {"configured": True, "error": "offline"},
    {"configured": True, "cache_hit": True, "age_seconds": 300},
    {"configured": False, "error": "unreadable"},
    {},
])
def test_board_refresh_still_rejects_unproven_or_failed_authority(tmp_path, monkeypatch, lease):
    monkeypatch.setattr(state.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(
        args[0], 0, json.dumps({"lease": lease, "problems": []}), ""))
    assert state._refresh_coordination_board(tmp_path / "board.md", passive_stop=True) is not None


def working_digest_fixture(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    deep = "/".join(["deep"] + [f"level-{i:02}" for i in range(24)] + ["雪.txt"])
    contents = {
        ".gitignore": b"ignored/\n",
        ".hidden": b"hidden\x00bytes",
        "a/child.txt": b"child",
        "a.txt": b"sibling with a shared prefix",
        deep: "deep Unicode content: café\n".encode(),
        "ignored/output.bin": bytes(range(256)),
        "nested/.pytest_cache/state.json": b'{"cached":true}',
        "z-last.md": b"last\n",
    }
    for name, content in contents.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    for name in (".git/HEAD", "nested/.git/objects/ignored"):
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"Git metadata is excluded")
    external = tmp_path / "outside.txt"
    external.write_bytes(b"external file target")
    external_dir = tmp_path / "outside-directory"
    external_dir.mkdir()
    (external_dir / "not-traversed.txt").write_bytes(b"directory link is not traversed")
    (project / "link-internal").symlink_to("z-last.md")
    (project / "link-external").symlink_to(external)
    (project / "link-directory").symlink_to(external_dir, target_is_directory=True)
    (project / "link-missing").symlink_to(tmp_path / "missing-target")
    contents["link-internal"] = contents["z-last.md"]
    contents["link-external"] = external.read_bytes()
    # Path ordering compares path components, so a/child precedes a.txt.
    order = [".gitignore", ".hidden", "a/child.txt", "a.txt", deep,
             "ignored/output.bin", "link-external", "link-internal",
             "nested/.pytest_cache/state.json", "z-last.md"]
    return project, contents, order


def expected_working_digest(contents, order):
    entries = [(name, hashlib.sha256(contents[name]).hexdigest()) for name in order]
    return hashlib.sha256(json.dumps(entries, separators=(",", ":")).encode()).hexdigest()


@pytest.mark.parametrize("root_form", ["absolute", "relative", "current", "symlink"])
def test_working_digest_preserves_complete_coverage_and_order(tmp_path, monkeypatch, root_form):
    project, contents, order = working_digest_fixture(tmp_path)
    if root_form == "relative":
        monkeypatch.chdir(tmp_path)
        project = Path("project")
    elif root_form == "current":
        monkeypatch.chdir(project)
        project = Path(".")
    elif root_form == "symlink":
        alias = tmp_path / "project-alias"
        alias.symlink_to(project, target_is_directory=True)
        project = alias
    observed = []
    original = state._sha_file
    monkeypatch.setattr(state, "_sha_file", lambda path: observed.append(path) or original(path))
    assert state._working_digest(project) == expected_working_digest(contents, order)
    assert observed == [project / name for name in order]


@pytest.mark.parametrize("change", ["changed", "new", "deleted", "symlink-target"])
def test_working_digest_recomputes_changed_new_deleted_and_linked_content(tmp_path, change):
    project, contents, order = working_digest_fixture(tmp_path)
    before = state._working_digest(project)
    assert before == expected_working_digest(contents, order)
    if change == "changed":
        contents["a.txt"] = b"changed bytes"
        (project / "a.txt").write_bytes(contents["a.txt"])
    elif change == "new":
        contents["new-untracked.txt"] = b"new untracked bytes"
        (project / "new-untracked.txt").write_bytes(contents["new-untracked.txt"])
        order.insert(order.index("z-last.md"), "new-untracked.txt")
    elif change == "deleted":
        (project / "a.txt").unlink()
        del contents["a.txt"]
        order.remove("a.txt")
    else:
        contents["link-external"] = b"changed external file target"
        (tmp_path / "outside.txt").write_bytes(contents["link-external"])
    after = state._working_digest(project)
    assert after == expected_working_digest(contents, order)
    assert after != before


def test_working_digest_rereads_every_included_file_independently(tmp_path, monkeypatch):
    project, contents, order = working_digest_fixture(tmp_path)
    reads = []
    original = state._sha_file
    monkeypatch.setattr(state, "_sha_file", lambda path: reads.append(path) or original(path))
    assert state._working_digest(project) == expected_working_digest(contents, order)
    assert state._working_digest(project) == expected_working_digest(contents, order)
    assert reads == [project / name for name in order] * 2


@pytest.mark.parametrize("depth", [0, 32])
def test_working_digest_avoids_per_file_relative_ancestor_walks(tmp_path, monkeypatch, depth):
    project = tmp_path / "project"
    project.mkdir()
    parent = project.joinpath(*(f"level-{i:02}" for i in range(depth)))
    parent.mkdir(parents=True, exist_ok=True)
    for index in range(8):
        (parent / f"file-{index}.txt").write_bytes(str(index).encode())
    calls = {"relative_to": 0, "parents": 0}
    original_relative = Path.relative_to
    original_parents = Path.parents.fget

    def relative(self, *args, **kwargs):
        calls["relative_to"] += 1
        return original_relative(self, *args, **kwargs)

    def parents(self):
        calls["parents"] += 1
        return original_parents(self)

    with monkeypatch.context() as isolated:
        isolated.setattr(Path, "relative_to", relative)
        isolated.setattr(Path, "parents", property(parents))
        digest = state._working_digest(project)
    assert len(digest) == 64
    assert calls == {"relative_to": 0, "parents": 0}


@pytest.mark.parametrize("root_form", ["absolute", "current"])
def test_working_digest_rejects_non_descendant_from_traversal(tmp_path, monkeypatch, root_form):
    project = tmp_path / "project"
    project.mkdir()
    other = tmp_path / "project-sibling" / "file.txt"
    other.parent.mkdir()
    other.write_bytes(b"must not enter this digest")
    if root_form == "current":
        monkeypatch.chdir(project)
        project = Path(".")
    original = getattr(state, "_project_paths", lambda path, pattern=None: path.rglob(pattern or "*"))

    def traversal(path, pattern=None):
        return iter([other]) if path == project else original(path, pattern)

    monkeypatch.setattr(state, "_project_paths", traversal, raising=False)
    with pytest.raises(ValueError):
        state._working_digest(project)


@pytest.mark.parametrize("root_form", ["absolute", "relative", "current", "symlink"])
@pytest.mark.parametrize("plan", [None, "UPPER.MD", "z-target.md"])
def test_content_hashes_preserve_complete_selection_names_and_reads(tmp_path, monkeypatch, root_form, plan):
    project = tmp_path / "project"
    project.mkdir()
    deep = "/".join(["deep"] + [f"level-{i:02}" for i in range(24)] + ["雪.md"])
    contents = {
        ".hidden.md": b"hidden", ".git/notes.md": b"included Markdown",
        "a/child.md": b"child", "a.md": b"sibling", deep: "café\n".encode(),
        "ignored/note.md": b"ignored by Git only", "z-target.md": b"target",
        "UPPER.MD": b"explicit plan", "other.txt": b"not Markdown",
        ".gitignore": b"ignored/\n",
    }
    for name, content in contents.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (project / "a-alias.md").symlink_to("z-target.md")
    (project / "z-alias.md").symlink_to("z-target.md")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "not-traversed.md").write_bytes(b"outside directory")
    (project / "directory.md").symlink_to(outside, target_is_directory=True)
    (project / "broken.md").symlink_to(tmp_path / "missing.md")
    canonical = project.resolve()
    if root_form == "relative":
        monkeypatch.chdir(tmp_path)
        project = Path("project")
    elif root_form == "current":
        monkeypatch.chdir(project)
        project = Path(".")
    elif root_form == "symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(project, target_is_directory=True)
        project = alias
    selected = [name for name in contents if name.endswith(".md")]
    expected = {name: hashlib.sha256(contents[name]).hexdigest() for name in selected}
    if plan:
        expected[plan] = hashlib.sha256(contents[plan]).hexdigest()
    expected = dict(sorted(expected.items()))
    order = sorted(project / name for name in [*selected, "a-alias.md", "z-alias.md"])
    if plan:
        order.append(canonical / plan)
    reads = []
    original = state._sha_file
    monkeypatch.setattr(state, "_sha_file", lambda path: reads.append(path) or original(path))
    assert state._content_hashes(project, plan) == expected
    assert state._content_hashes(project, plan) == expected
    assert reads == order * 2


@pytest.mark.parametrize("change", ["changed", "new", "deleted", "linked-target"])
def test_content_hashes_recompute_each_file_set_and_content(tmp_path, change):
    project = tmp_path / "project"
    project.mkdir()
    target = project / "target.md"
    target.write_bytes(b"original")
    (project / "alias.md").symlink_to("target.md")
    other = project / "other.md"
    other.write_bytes(b"other")
    before = state._content_hashes(project)
    expected = {"other.md": hashlib.sha256(b"other").hexdigest(),
                "target.md": hashlib.sha256(b"original").hexdigest()}
    assert before == expected
    if change == "changed":
        other.write_bytes(b"changed")
        expected["other.md"] = hashlib.sha256(b"changed").hexdigest()
    elif change == "new":
        (project / "new.md").write_bytes(b"new")
        expected["new.md"] = hashlib.sha256(b"new").hexdigest()
    elif change == "deleted":
        other.unlink()
        del expected["other.md"]
    else:
        (project / "alias.md").write_bytes(b"linked change")
        expected["target.md"] = hashlib.sha256(b"linked change").hexdigest()
    assert state._content_hashes(project) == dict(sorted(expected.items()))
    assert expected != before


@pytest.mark.parametrize("plan", [None, "middle.md"])
def test_content_hashes_keep_alias_order_and_final_plan_overwrite(tmp_path, monkeypatch, plan):
    project = tmp_path / "project"
    project.mkdir()
    target = project / "middle.md"
    target.write_bytes(b"revision-0")
    (project / "a-alias.md").symlink_to("middle.md")
    (project / "z-alias.md").symlink_to("middle.md")
    reads = []
    original = state._sha_file

    def changing_file(path):
        digest = original(path)
        reads.append(path.name)
        target.write_bytes(f"revision-{len(reads)}".encode())
        return digest

    monkeypatch.setattr(state, "_sha_file", changing_file)
    expected_order = ["a-alias.md", "middle.md", "z-alias.md"] + (["middle.md"] if plan else [])
    expected = hashlib.sha256(f"revision-{len(expected_order) - 1}".encode()).hexdigest()
    assert state._content_hashes(project, plan) == {"middle.md": expected}
    assert reads == expected_order


@pytest.mark.parametrize("depth", [0, 32])
def test_content_hashes_use_constant_root_resolution_without_ancestor_walks(tmp_path, monkeypatch, depth):
    project = tmp_path / "project"
    parent = project.joinpath(*(f"level-{i:02}" for i in range(depth)))
    parent.mkdir(parents=True)
    files = [parent / f"file-{i}.md" for i in range(8)]
    for path in files:
        path.write_bytes(path.name.encode())
    resolves, reads = [], []
    walks = {"relative_to": 0, "parents": 0}
    original_resolve, original_relative = Path.resolve, Path.relative_to
    original_parents, original_hash = Path.parents.fget, state._sha_file

    def resolve(path, *args, **kwargs):
        resolves.append(path)
        return original_resolve(path, *args, **kwargs)

    def relative(path, *args, **kwargs):
        walks["relative_to"] += 1
        return original_relative(path, *args, **kwargs)

    def parents(path):
        walks["parents"] += 1
        return original_parents(path)

    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(Path, "relative_to", relative)
    monkeypatch.setattr(Path, "parents", property(parents))
    monkeypatch.setattr(state, "_sha_file", lambda path: reads.append(path) or original_hash(path))
    result = state._content_hashes(project)
    assert len(result) == 8
    assert reads == sorted(files)
    assert [path for path in resolves if path != project] == sorted(files)
    assert resolves.count(project) == 2
    assert walks == {"relative_to": 0, "parents": 0}


def test_content_hashes_reject_outside_resolved_target_before_read(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "project-sibling" / "outside.md"
    outside.parent.mkdir()
    outside.write_bytes(b"must not be read")
    (project / "outside.md").symlink_to(outside)
    reads = []
    monkeypatch.setattr(state, "_sha_file", lambda path: reads.append(path) or "unexpected")
    with pytest.raises(ValueError):
        state._content_hashes(project)
    assert reads == []


@pytest.mark.parametrize("phase", ["markdown", "plan", "empty"])
def test_content_hashes_reject_root_retarget_after_last_read(tmp_path, monkeypatch, phase):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    project = tmp_path / "project"
    project.symlink_to(first, target_is_directory=True)
    plan = "UPPER.MD" if phase == "plan" else None
    if phase != "empty":
        (first / (plan or "note.md")).write_bytes(b"first root")
    original_hash = state._sha_file
    original_paths = getattr(state, "_project_paths", lambda path, pattern=None: path.rglob(pattern or "*"))

    def retarget():
        project.unlink()
        project.symlink_to(second, target_is_directory=True)

    def hash_then_retarget(path):
        digest = original_hash(path)
        retarget()
        return digest

    def empty_then_retarget(path, pattern=None):
        yield from original_paths(path, pattern)
        retarget()

    if phase == "empty":
        monkeypatch.setattr(state, "_project_paths", empty_then_retarget, raising=False)
    else:
        monkeypatch.setattr(state, "_sha_file", hash_then_retarget)
    with pytest.raises((ValueError, state.ProjectStateError)):
        state._content_hashes(project, plan)
    assert project.resolve() == second


def traversal_corpus(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    for name in (".md", "line\nbreak.md", "UPPER.MD", ".hidden/note.md",
                 ".git/inside.md", "a/inside.md", "a.md", "folder.md/child.md",
                 "雪.md", "other.bin"):
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
    (project / "alias.md").symlink_to("a.md")
    (project / "broken.md").symlink_to(tmp_path / "missing.md")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "outside.md").write_bytes(b"unvisited")
    (project / "directory.md").symlink_to(outside, target_is_directory=True)
    (project / "cycle").symlink_to(project, target_is_directory=True)
    return project


@pytest.mark.parametrize("consumer", ["_content_hashes", "_working_digest"])
@pytest.mark.parametrize("root_form", ["absolute", "relative", "current", "symlink"])
def test_hash_traversal_matches_retained_rglob_corpus(tmp_path, monkeypatch, consumer, root_form):
    project = traversal_corpus(tmp_path)
    if root_form == "relative":
        monkeypatch.chdir(tmp_path)
        project = Path("project")
    elif root_form == "current":
        monkeypatch.chdir(project)
        project = Path(".")
    elif root_form == "symlink":
        alias = tmp_path / "root-alias"
        alias.symlink_to(project, target_is_directory=True)
        project = alias
    if consumer == "_content_hashes":
        paths = sorted(set(path for path in project.rglob("*.md") if path.is_file()))
        expected = dict(sorted({str(path.resolve().relative_to(project.resolve())): sha(path)
                                for path in paths}.items()))
        assert ".md" in expected and "line\nbreak.md" in expected
        assert ".git/inside.md" in expected
    else:
        paths = [path for path in sorted(item for item in project.rglob("*") if item.is_file())
                 if ".git" not in path.parts]
        entries = [(str(path.relative_to(project)), sha(path)) for path in paths]
        expected = hashlib.sha256(json.dumps(entries, separators=(",", ":")).encode()).hexdigest()
    reads = []
    original = state._sha_file
    monkeypatch.setattr(state, "_sha_file", lambda path: reads.append(path) or original(path))
    assert getattr(state, consumer)(project) == expected
    assert reads == paths


@pytest.mark.parametrize("consumer", ["_content_hashes", "_working_digest"])
def test_hash_traversal_scans_each_directory_once_per_fresh_pass(tmp_path, monkeypatch, consumer):
    project = traversal_corpus(tmp_path)
    directories = {project, project / ".hidden", project / ".git", project / "a", project / "folder.md"}
    import collections
    scans, active = [], []
    original_scan, original_is_file = state.os.scandir, Path.is_file

    class Scan:
        def __init__(self, path):
            assert not active, "a directory iterator remained open while descending"
            self.path = Path(path)
            self.iterator = original_scan(path)

        def __enter__(self):
            active.append(self.path)
            scans.append(self.path)
            return self.iterator

        def __exit__(self, *args):
            self.iterator.close()
            active.remove(self.path)

    def is_file(path):
        assert not active, "a directory iterator remained open during file selection"
        return original_is_file(path)

    monkeypatch.setattr(state.os, "scandir", Scan)
    monkeypatch.setattr(Path, "is_file", is_file)
    first = getattr(state, consumer)(project)
    assert collections.Counter(scans) == {path: 1 for path in directories}
    assert getattr(state, consumer)(project) == first
    assert collections.Counter(scans) == {path: 2 for path in directories}
    assert not active


@pytest.mark.parametrize("consumer", ["_content_hashes", "_working_digest"])
@pytest.mark.parametrize("failure", ["open", "iterate", "classify", "is_file"])
def test_hash_traversal_does_not_accept_incomplete_io(tmp_path, monkeypatch, consumer, failure):
    project = tmp_path / "project"
    child = project / "child"
    child.mkdir(parents=True)
    leaf = child / "note.md"
    leaf.write_bytes(b"must be accounted for")
    original_scan, original_is_file = state.os.scandir, Path.is_file
    opened, closed = [], []

    class Entry:
        def __init__(self, entry):
            self.entry = entry

        def __getattr__(self, name):
            return getattr(self.entry, name)

        def is_dir(self, *args, **kwargs):
            if failure == "classify" and self.name == "child":
                raise PermissionError("fixture directory classification denied")
            return self.entry.is_dir(*args, **kwargs)

    class Scan:
        def __init__(self, path):
            self.path = Path(path)
            if failure == "open" and self.path == child:
                raise PermissionError("fixture directory open denied")
            self.iterator = original_scan(path)

        def __enter__(self):
            opened.append(self.path)
            return self

        def __iter__(self):
            return self

        def __next__(self):
            entry = next(self.iterator)
            if failure == "iterate" and self.path == child:
                raise PermissionError("fixture directory iteration denied")
            return Entry(entry)

        def __exit__(self, *args):
            self.iterator.close()
            closed.append(self.path)

    def is_file(path):
        if failure == "is_file" and path == leaf:
            raise PermissionError("fixture file stat denied")
        return original_is_file(path)

    monkeypatch.setattr(state.os, "scandir", Scan)
    monkeypatch.setattr(Path, "is_file", is_file)
    with pytest.raises(OSError):
        getattr(state, consumer)(project)
    assert len(opened) == len(closed)


@pytest.mark.parametrize("consumer", ["_content_hashes", "_working_digest"])
def test_hash_traversal_rechecks_file_type_after_enumeration(tmp_path, monkeypatch, consumer):
    project = tmp_path / "project"
    project.mkdir()
    leaf = project / "changed.md"
    leaf.write_bytes(b"was a file")
    original = Path.is_file
    checked, reads = [], []

    def is_file(path):
        if path == leaf and not checked:
            leaf.unlink()
            leaf.mkdir()
            checked.append(path)
        return original(path)

    monkeypatch.setattr(Path, "is_file", is_file)
    monkeypatch.setattr(state, "_sha_file", lambda path: reads.append(path) or "unexpected")
    result = getattr(state, consumer)(project)
    assert result == ({} if consumer == "_content_hashes" else hashlib.sha256(b"[]").hexdigest())
    assert checked == [leaf]
    assert reads == []


@pytest.mark.parametrize("consumer", ["_content_hashes", "_working_digest"])
def test_hash_traversal_rejects_queued_directory_replaced_by_link(tmp_path, monkeypatch, consumer):
    project = tmp_path / "project"
    child = project / "child"
    child.mkdir(parents=True)
    target = tmp_path / "outside"
    target.mkdir()
    (target / "foreign.txt").write_bytes(b"must not be traversed")
    original = state.os.scandir
    changed, scanned = [], []

    class Entry:
        def __init__(self, entry):
            self.entry = entry

        def __getattr__(self, name):
            return getattr(self.entry, name)

        def is_dir(self, *args, **kwargs):
            result = self.entry.is_dir(*args, **kwargs)
            if self.name == "child" and not changed:
                child.rmdir()
                child.symlink_to(target, target_is_directory=True)
                changed.append(child)
            return result

    class Scan:
        def __init__(self, path):
            self.path = Path(path)
            scanned.append(self.path)
            self.iterator = original(path)

        def __enter__(self):
            return self

        def __iter__(self):
            return self

        def __next__(self):
            return Entry(next(self.iterator))

        def __exit__(self, *args):
            self.iterator.close()

    monkeypatch.setattr(state.os, "scandir", Scan)
    with pytest.raises((OSError, state.ProjectStateError)):
        getattr(state, consumer)(project)
    assert changed == [child]
    assert child not in scanned
