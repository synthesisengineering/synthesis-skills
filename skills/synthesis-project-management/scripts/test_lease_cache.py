"""Passive refresh caching never supplies authority or loses recovery evidence."""
from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import coordination as engine
import project_state as state
from test_project_state import board as claim_board, init_repo


@pytest.fixture
def leased(tmp_path, monkeypatch):
    board = tmp_path / "board.md"
    board.write_text(engine.template())
    (tmp_path / "lease.json").write_text(json.dumps({"remote": "fixture-remote"}))
    clock = [1000.0]
    calls = []
    monkeypatch.setattr(time, "time", lambda: clock[0])

    def fetch(config):
        calls.append(config)
        return "a" * 40, engine.template()

    monkeypatch.setattr(engine, "lease_fetch", fetch)
    return SimpleNamespace(board=board, clock=clock, calls=calls)


def test_passive_interval_is_only_opt_in_and_expires_at_five_minutes(leased):
    assert engine.lease_refresh(leased.board)["refreshed"]
    leased.clock[0] += 299.99
    cached = engine.lease_refresh(leased.board, max_age_seconds=300)
    assert cached["cache_hit"] and not cached["refreshed"]
    assert len(leased.calls) == 1
    leased.clock[0] = 1300
    assert engine.lease_refresh(leased.board, max_age_seconds=300)["refreshed"]
    assert len(leased.calls) == 2
    assert engine.lease_refresh(leased.board)["refreshed"]
    assert len(leased.calls) == 3


@pytest.mark.parametrize("change", ["content", "config", "missing", "corrupt", "symlink", "future", "nan", "other-board"])
def test_passive_stamp_cannot_outlive_its_bound_evidence(leased, change, tmp_path):
    engine.lease_refresh(leased.board)
    stamp = engine.lease_stamp_path(leased.board)
    if change == "content":
        leased.board.write_text(engine.template() + "\nlocal change\n")
    elif change == "config":
        (tmp_path / "lease.json").write_text(json.dumps({"remote": "different-remote"}))
    elif change == "missing":
        leased.board.unlink()
    elif change == "corrupt":
        stamp.write_text("{")
    elif change == "symlink":
        retained = tmp_path / "retained-stamp"
        stamp.rename(retained)
        stamp.symlink_to(retained)
    elif change in {"future", "nan"}:
        data = json.loads(stamp.read_text())
        data["fetched_at"] = 2000 if change == "future" else float("nan")
        stamp.write_text(json.dumps(data))
    else:
        other = tmp_path / "other.md"
        other.write_bytes(leased.board.read_bytes())
        engine.lease_stamp_path(other).write_bytes(stamp.read_bytes())
        leased.board = other
    assert engine.lease_refresh(leased.board, max_age_seconds=300)["refreshed"]
    assert len(leased.calls) == 2


def test_failed_forced_fetch_invalidates_previous_passive_success(leased, monkeypatch):
    engine.lease_refresh(leased.board)
    calls = []

    def fail(_config):
        calls.append(True)
        raise RuntimeError("fixture outage")

    monkeypatch.setattr(engine, "lease_fetch", fail)
    assert "fixture outage" in engine.lease_refresh(leased.board)["error"]
    assert "fixture outage" in engine.lease_refresh(leased.board, max_age_seconds=300)["error"]
    assert len(calls) == 2


def test_stamp_write_failure_does_not_turn_successful_fetch_into_cache(leased, monkeypatch):
    monkeypatch.setattr(engine, "_write_lease_stamp", lambda *_a: (_ for _ in ()).throw(OSError("fixture stamp failure")))
    assert engine.lease_refresh(leased.board)["refreshed"]
    assert engine.lease_refresh(leased.board, max_age_seconds=300)["refreshed"]
    assert len(leased.calls) == 2


def test_configured_unpublished_remote_cannot_validate_local_authority(leased, monkeypatch):
    monkeypatch.setattr(engine, "lease_fetch", lambda _c: ("", None))
    result = engine.lease_refresh(leased.board)
    assert not result["refreshed"] and "published" in result["error"]
    assert not engine.lease_stamp_path(leased.board).exists()


def test_commit_authority_cannot_bootstrap_unpublished_remote_from_local_claims(leased, monkeypatch):
    monkeypatch.setattr(engine, "lease_fetch", lambda _c: ("", None))
    monkeypatch.setattr(engine, "lease_publish", lambda *_a: pytest.fail("authority read cannot publish retained local claims"))
    with pytest.raises(RuntimeError, match="published"):
        engine._check_staged_board_snapshot(leased.board)


@pytest.mark.parametrize("command", ["resolve", "inbox"])
def test_authoritative_read_refuses_failed_refresh_before_delivery(leased, monkeypatch, command, capsys):
    engine.lease_refresh(leased.board)
    monkeypatch.setattr(engine, "lease_fetch", lambda _c: (_ for _ in ()).throw(RuntimeError("fixture outage")))
    request = SimpleNamespace(board=leased.board)
    assert getattr(engine, "command_" + command)(request) != 0
    assert "fixture outage" in capsys.readouterr().err


def test_missing_configuration_of_declared_board_refuses_refresh(tmp_path):
    board = tmp_path / "board.md"
    board.write_text(engine.ensure_lease_declaration(engine.template(), "fixture-remote"))
    assert "missing" in engine.lease_refresh(board)["error"]


def test_check_staged_keeps_identity_cas_even_with_fresh_stamp(leased, monkeypatch):
    engine.lease_refresh(leased.board)
    calls = []
    monkeypatch.setattr(engine, "lease_publish", lambda *a: (calls.append(a) or True, ""))
    snapshot = engine._check_staged_board_snapshot(leased.board)
    assert snapshot and len(calls) == 1 and len(leased.calls) == 2


def test_noop_mutation_skips_publish_but_explicit_authority_fence_does_not(leased, monkeypatch):
    content = engine.ensure_lease_declaration(engine.template(), "fixture-remote")
    monkeypatch.setattr(engine, "lease_fetch", lambda _c: ("a" * 40, content))
    calls = []
    monkeypatch.setattr(engine, "lease_publish", lambda *a: (calls.append(a) or True, ""))
    engine.locked_update(leased.board, lambda current: current)
    assert calls == []
    assert leased.board.read_text() == content
    engine.locked_update(leased.board, lambda current: current, require_fence=True)
    assert len(calls) == 1


def test_direct_checkpoint_cannot_issue_receipt_from_unreachable_local_mirror(tmp_path):
    repo, project = init_repo(tmp_path)
    session = "018f0000-0000-7000-8000-000000000001"
    claims = claim_board(tmp_path / "board.md", [(session, "unused", "alpha", str(repo))])
    state.build_operational_state(project, project_id="alpha", phase="release 1.0.0", status="active", controlling_plan="resources/artifacts/plan.md", accepted_baseline="1.0.0", next_actions=["finish"], last_session="2026-09-03", session_id=session)
    (tmp_path / "lease.json").write_text(json.dumps({"remote": str(tmp_path / "missing.git")}))
    with pytest.raises(state.ProjectStateError, match="lease"):
        state.checkpoint_project(project, session_id=session, coordination_board=claims, receipt_root=tmp_path / "receipts")
    assert not (tmp_path / "receipts").exists()


@pytest.mark.parametrize("passive,age,accepted", [(True, 0, True), (True, 299.99, True), (True, 300, False), (True, -1, False), (True, float("nan"), False), (False, 1, False)])
def test_project_refresh_accepts_cache_only_for_bounded_passive_mode(tmp_path, monkeypatch, passive, age, accepted):
    calls = []
    def run(command, **_kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps({"problems": [], "lease": {"configured": True, "refreshed": False, "cache_hit": True, "age_seconds": age}}))
    monkeypatch.setattr(state.subprocess, "run", run)
    issue = state._refresh_coordination_board(tmp_path / "board.md", passive_stop=passive)
    assert (issue is None) == accepted
    assert ("--passive-stop" in calls[0]) == passive


def test_unchanged_board_has_no_backup_or_write(tmp_path):
    board = tmp_path / "board.md"
    board.write_text("same\n")
    before = board.stat().st_mtime_ns
    engine.write_board(board, "same\n")
    assert board.stat().st_mtime_ns == before
    assert not (tmp_path / "backups").exists()


@pytest.mark.parametrize("count", [199, 200, 204])
def test_backup_retention_is_bounded_and_preserves_foreign_files(tmp_path, count):
    board = tmp_path / "board.md"
    board.write_text("before\n")
    backups = tmp_path / "backups"
    backups.mkdir()
    for n in range(count):
        (backups / f"board.md.20990101T000000{n:06d}.bak").write_text(str(n))
    retained = [backups / "other.md.20000101T000000000001.bak", backups / "board.md.personal.bak"]
    for path in retained:
        path.write_text("retained")
    link = backups / "board.md.20000101T000000000002.bak"
    link.symlink_to(retained[0])
    engine.write_board(board, "after\n")
    own = [p for p in backups.iterdir() if p.name.startswith("board.md.") and p not in retained and not p.is_symlink()]
    assert len(own) == 200
    assert any(p.read_text() == "before\n" for p in own), "clock rollback must retain the just-created recovery copy"
    assert board.read_text() == "after\n"
    assert all(p.read_text() == "retained" for p in retained) and link.is_symlink()


def test_backup_directory_symlink_refuses_without_touching_destination(tmp_path):
    board = tmp_path / "board.md"
    board.write_text("before\n")
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (tmp_path / "backups").symlink_to(foreign, target_is_directory=True)
    with pytest.raises(OSError, match="symlink"):
        engine.write_board(board, "after\n")
    assert board.read_text() == "before\n" and not list(foreign.iterdir())


def test_failed_backup_is_not_counted_as_verified_recovery(tmp_path, monkeypatch):
    board = tmp_path / "board.md"
    board.write_text("before\n")
    def fail_copy(_source, target):
        Path(target).write_text("partial")
        raise OSError("fixture copy failure")
    monkeypatch.setattr(engine.shutil, "copy2", fail_copy)
    with pytest.raises(OSError, match="fixture copy failure"):
        engine.write_board(board, "after\n")
    assert board.read_text() == "before\n"
    assert not list((tmp_path / "backups").glob("*.bak"))


def test_mirror_failure_retains_verified_backup_without_pruning(tmp_path, monkeypatch):
    board = tmp_path / "board.md"
    board.write_text("before\n")
    original = engine.os.replace
    def fail_mirror(source, target):
        if Path(target) == board:
            raise OSError("fixture mirror failure")
        return original(source, target)
    monkeypatch.setattr(engine.os, "replace", fail_mirror)
    monkeypatch.setattr(engine, "_prune_board_backups", lambda *_a: pytest.fail("failed replacement must not prune"))
    with pytest.raises(OSError, match="fixture mirror failure"):
        engine.write_board(board, "after\n")
    assert board.read_text() == "before\n"
    assert [p.read_text() for p in (tmp_path / "backups").glob("*.bak")] == ["before\n"]


def test_pruning_failure_reports_successful_mutation_separately(tmp_path, monkeypatch, capsys):
    board = tmp_path / "board.md"
    board.write_text("before\n")
    monkeypatch.setattr(engine, "_prune_board_backups", lambda *_a: (_ for _ in ()).throw(OSError("fixture pruning failure")))
    engine.write_board(board, "after\n")
    assert board.read_text() == "after\n"
    assert "maintenance warning" in capsys.readouterr().err
