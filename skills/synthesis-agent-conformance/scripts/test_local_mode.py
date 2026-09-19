"""--local mode performs no network, refresh, or pointer writes on any route."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "local_conformance", Path(__file__).with_name("conformance.py")
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _forbidden(name):
    def trip(*args, **kwargs):
        pytest.fail(f"local mode invoked a forbidden boundary: {name}")
    return trip


def _git_repo(path: Path) -> Path:
    subprocess.run(
        ["git", "init", "--quiet", "--initial-branch", "main", str(path)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "core.hooksPath", "/dev/null"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "t@t"], check=True
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "t"], check=True
    )
    (path / "f.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-qm", "init"], check=True
    )
    return path


def _board(tmp_path: Path) -> Path:
    board = tmp_path / "board.md"
    board.write_text(
        "Schema: v4\nLease: /tmp/lease\n\n## Active sessions\n\n"
        "| session uuid | compact id | speakable id v1 | legacy id | machine | project | heartbeat | workspace(s) / branch | claimed areas (advisory lock) | context role | status |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| u-1 | s-1 | sp-1 | l-1 | m | p | 2026-09-19T00:00:00+00:00 | /w @ b | /a/** | owner | active |\n"
        "## Messages\n## Protocol\n",
        encoding="utf-8",
    )
    return board


@pytest.mark.parametrize("local", [False, True])
def test_local_recovery_threads_fetch_and_refresh_flags(
    tmp_path, monkeypatch, local
):
    seen = {}

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(
            status="PASS", selected_head="h", selected_path="p", issues=[]
        )

    monkeypatch.setattr(MODULE, "resolve_durable_project", spy)
    project = tmp_path / "proj"
    project.mkdir()
    board = _board(tmp_path)
    checks = MODULE.project_state_recovery_checks(project, board, local=local)
    assert seen["fetch"] is (not local)
    assert seen["refresh_coordination"] is (not local)
    detail = next(c.detail for c in checks if c.name == "continuity.project-state-recovery")
    assert ("local mode: remote refs as of last fetch" in detail) is local


@pytest.mark.parametrize("local", [False, True])
def test_local_pointer_skips_lease_refresh(tmp_path, monkeypatch, local):
    seen = {}
    repo = _git_repo(tmp_path / "repo")
    branch = subprocess.run(
        ["git", "-C", str(repo), "branch", "--show-current"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    commit = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    pointer = tmp_path / "pointer.json"
    pointer.write_text(json.dumps({
        "project": str(repo), "phase": "x", "status": "active",
        "plan": "p", "activated_at": "t", "source": "s",
        "worktree": str(repo), "branch": branch, "source_commit": commit,
        "owner_session": "u-1", "owner_lease": "L",
    }), encoding="utf-8")

    def spy(p, b, **kwargs):
        seen.update(kwargs)
        return {}, []

    monkeypatch.setattr(MODULE, "load_and_validate", spy)
    monkeypatch.setattr(MODULE, "validate_active_project", lambda *a, **k: [])
    MODULE.pointer_checks(repo, pointer, _board(tmp_path), local=local)
    assert seen["refresh_lease"] is (not local)


@pytest.mark.parametrize("local", [False, True])
def test_local_activate_refuses_before_lock_and_write(
    tmp_path, monkeypatch, local
):
    monkeypatch.setattr(
        MODULE, "project_summary", lambda project: ({"phase": "x"}, [])
    )
    monkeypatch.setattr(
        MODULE, "coordination_sessions", lambda board: {"u-1": {"status": "active"}}
    )
    monkeypatch.setattr(
        MODULE,
        "resolve_coordination_session",
        lambda sessions, owner: {"session_uuid": "u-1", "status": "active"},
    )
    monkeypatch.setattr(MODULE, "lease_url", lambda board: "L")
    monkeypatch.setattr(
        MODULE, "run",
        lambda argv, **k: SimpleNamespace(returncode=0, stdout="/w\n", stderr=""),
    )
    writes = []
    if local:
        monkeypatch.setattr(
            MODULE, "locked_pointer", _forbidden("locked_pointer")
        )
        monkeypatch.setattr(
            MODULE,
            "validate_active_project",
            _forbidden("validate_active_project"),
        )
        monkeypatch.setattr(
            MODULE, "atomic_json_write", _forbidden("atomic_json_write")
        )
    else:
        from contextlib import nullcontext

        monkeypatch.setattr(
            MODULE, "locked_pointer", lambda pointer: nullcontext()
        )
        monkeypatch.setattr(
            MODULE, "validate_active_project", lambda *a, **k: []
        )
        monkeypatch.setattr(
            MODULE,
            "atomic_json_write",
            lambda dest, payload: writes.append(dest),
        )
    pointer = tmp_path / "pointer.json"
    checks = MODULE.activate(
        tmp_path, pointer, owner_session="u-1",
        coordination_board=_board(tmp_path), local=local,
    )
    names = [c.name for c in checks]
    if local:
        assert "handoff.pointer-would-write" in names
        detail = next(c.detail for c in checks if c.name == "handoff.pointer-would-write")
        assert str(pointer) in detail and "owner=u-1" in detail
        assert writes == [] and not pointer.exists()
    else:
        assert "handoff.pointer-written" in names
        assert writes == [pointer]


def test_local_runtime_skips_reachability_probes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        MODULE, "resolve_client_binary", _forbidden("resolve_client_binary")
    )
    monkeypatch.setattr(MODULE, "plugin_inventory", lambda client: (True, "ok"))
    monkeypatch.setattr(MODULE, "direct_public_copies", lambda home: [])
    checks = MODULE.runtime_checks(local=True)
    names = {c.name for c in checks}
    assert "runtime.codex-provider" in names
    assert "runtime.codex-websocket" in names
    for name in ("runtime.codex-provider", "runtime.codex-websocket"):
        check = next(c for c in checks if c.name == name)
        assert check.ok is None and check.required is False
    # Positive control: without local the binary must be resolved.
    seen = []
    monkeypatch.setattr(
        MODULE, "resolve_client_binary", lambda client: seen.append(client) or None
    )
    MODULE.runtime_checks(local=False)
    assert seen == ["codex"]


def test_local_coordination_skips_semantic_doctor(tmp_path, monkeypatch):
    monkeypatch.setattr(MODULE, "run", _forbidden("subprocess"))
    checks = MODULE.coordination_checks(_board(tmp_path), local=True)
    check = next(c for c in checks if c.name == "coordination.semantic-doctor")
    assert check.ok is None and check.required is False
    assert "mirror mtime" in check.detail


def test_local_remote_readiness_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys, "argv",
        ["conformance.py", "continuity", "--project", str(tmp_path),
         "--local", "--readiness", "remote"],
    )
    with pytest.raises(SystemExit, match="cannot combine with --local"):
        MODULE.main()


@pytest.mark.parametrize("local", [False, True])
def test_local_catalog_disables_force_reload(tmp_path, monkeypatch, local):
    seen = {}
    (tmp_path / "skills").mkdir()

    def spy(source_root, home=None, reload=True):
        seen["reload"] = reload
        return {"status": "UNKNOWN", "errors": ["fixture"]}

    monkeypatch.setattr(MODULE, "codex_skill_catalog_audit", spy)
    monkeypatch.setattr(MODULE, "parse_frontmatter", lambda skill: {})
    MODULE.catalog_checks(tmp_path, local=local)
    assert seen["reload"] is (not local)


def test_local_leaves_fetch_head_and_board_untouched(tmp_path, monkeypatch):
    repo = _git_repo(tmp_path / "repo")
    board = _board(tmp_path)
    before = board.read_bytes()
    real_resolve = MODULE.resolve_durable_project

    def guarded(*args, **kwargs):
        assert kwargs.get("fetch") is False
        assert kwargs.get("refresh_coordination") is False
        return real_resolve(*args, **kwargs)

    monkeypatch.setattr(MODULE, "resolve_durable_project", guarded)
    (tmp_path / "index.yaml").write_text("projects: []\n", encoding="utf-8")
    project = tmp_path / "repo"
    MODULE.project_state_recovery_checks(project, board, local=True)
    assert board.read_bytes() == before
    assert not (repo / ".git" / "FETCH_HEAD").exists()
