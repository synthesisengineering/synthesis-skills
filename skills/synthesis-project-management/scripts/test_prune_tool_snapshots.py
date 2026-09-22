from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
import prune_tool_snapshots as p


NOW = 2_000_000_000


def snapshot(root, session="ended", age=90000, suffix="a"):
    directory = root / "tool-snapshots"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (hashlib.sha256((session + suffix).encode()).hexdigest() + ".json")
    path.write_text(json.dumps({"schema_version": 1, "session_id": session, "workdir": "/fixture",
                                "repo": "/fixture", "dirty": {"retained": "bytes"}}))
    os.utime(path, (NOW - age, NOW - age))
    return path


def row(session, status="released"):
    return SimpleNamespace(client_ref="codex:" + session, status=status)


def run(root, rows, **kwargs):
    return p.prune_locked(root, rows, now=NOW, **kwargs)


def test_retired_old_snapshot_is_verified_and_moved(tmp_path):
    path = snapshot(tmp_path)
    raw = path.read_bytes()
    result = run(tmp_path, [row("ended")])
    assert result["archived"] == 1 and not path.exists()
    [saved] = list((tmp_path / "tool-snapshots.archive").glob("*/*.json"))
    assert saved.read_bytes() == raw
    assert run(tmp_path, [row("ended")])["archived"] == 0


@pytest.mark.parametrize("reason", ["active", "unknown", "recent", "future", "pending", "ambiguous"])
def test_live_or_uncertain_snapshot_is_preserved(tmp_path, reason):
    path = snapshot(tmp_path, age=10 if reason == "recent" else (-10 if reason == "future" else 90000))
    rows = [row("ended", "active" if reason == "active" else "released")]
    if reason == "unknown": rows = []
    if reason == "ambiguous": rows += [row("ended", "active")]
    if reason == "pending":
        (tmp_path / "pending").mkdir()
        (tmp_path / "pending" / (hashlib.sha256(b"ended").hexdigest() + ".json")).write_text("retained")
    before = path.read_bytes()
    assert run(tmp_path, rows)["archived"] == 0
    assert path.read_bytes() == before


@pytest.mark.parametrize("kind", ["corrupt", "symlink", "directory_symlink"])
def test_corrupt_or_redirected_evidence_is_not_removed(tmp_path, kind):
    path = snapshot(tmp_path)
    if kind == "corrupt": path.write_text("{")
    if kind == "symlink":
        target = tmp_path / "retained"; target.write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(target)
    if kind == "directory_symlink":
        path.parent.rename(tmp_path / "retained"); path.parent.symlink_to(tmp_path / "retained", target_is_directory=True)
    if kind == "directory_symlink":
        with pytest.raises(RuntimeError, match="symlink"):
            run(tmp_path, [row("ended")])
    else:
        assert run(tmp_path, [row("ended")])["archived"] == 0
    assert path.exists()


def test_copy_failure_preserves_original(tmp_path, monkeypatch):
    path = snapshot(tmp_path)
    monkeypatch.setattr(p, "write_archive", lambda *args: (_ for _ in ()).throw(OSError("fixture disk failure")))
    with pytest.raises(OSError): run(tmp_path, [row("ended")])
    assert path.exists()


def test_existing_archive_collision_is_not_overwritten(tmp_path):
    path = snapshot(tmp_path)
    destination = p.archive_destination(tmp_path, path, path.read_bytes(), path.stat().st_mtime)
    destination.parent.mkdir(parents=True)
    destination.write_text("foreign retained")
    with pytest.raises(RuntimeError, match="collision"):
        run(tmp_path, [row("ended")])
    assert destination.read_text() == "foreign retained" and path.exists()


def test_changed_snapshot_after_copy_is_preserved(tmp_path, monkeypatch):
    path = snapshot(tmp_path)
    original = p.write_archive
    def racing(destination, raw):
        original(destination, raw)
        path.write_text("replacement retained")
    monkeypatch.setattr(p, "write_archive", racing)
    with pytest.raises(RuntimeError, match="changed"):
        run(tmp_path, [row("ended")])
    assert path.read_text() == "replacement retained"


def test_dry_run_has_no_archive_write(tmp_path):
    path = snapshot(tmp_path)
    result = run(tmp_path, [row("ended")], dry_run=True)
    assert result["eligible"] == 1 and result["archived"] == 0 and path.exists()
    assert not (tmp_path / "tool-snapshots.archive").exists()


@pytest.mark.parametrize("failure", ["unreachable", "unpublished", "missing_config"])
def test_fresh_board_failure_prevents_any_snapshot_move(tmp_path, monkeypatch, failure):
    path = snapshot(tmp_path / "repo-guard")
    board = tmp_path / "coordination/active-sessions.md"
    board.parent.mkdir()
    board.write_text("fixture retained board")
    def fetch(config):
        if failure == "unreachable": raise RuntimeError("fixture network failure")
        return "", None
    fake = SimpleNamespace(lease_configuration=lambda _: None if failure == "missing_config" else {},
                           lease_fetch=fetch, declared_lease=lambda _: "fixture remote")
    # Configuration normally contains a remote; an empty mapping isn't valid.
    if failure != "missing_config": fake.lease_configuration = lambda _: {"remote": "fixture"}
    monkeypatch.setattr(p, "coordination", lambda: fake)
    with pytest.raises(RuntimeError):
        p.prune(board, tmp_path / "repo-guard")
    assert path.exists()


def test_archive_directory_entries_are_durable_before_original_removal(tmp_path, monkeypatch):
    path = snapshot(tmp_path)
    events = []
    real_sync, real_unlink = p.sync_directory, Path.unlink
    def sync(directory):
        events.append(directory)
        return real_sync(directory)
    def remove(candidate, *args, **kwargs):
        if candidate == path:
            assert tmp_path in events and tmp_path / "tool-snapshots.archive" in events
        return real_unlink(candidate, *args, **kwargs)
    monkeypatch.setattr(p, "sync_directory", sync)
    monkeypatch.setattr(Path, "unlink", remove)
    assert run(tmp_path, [row("ended")])["archived"] == 1


def test_pruner_waiting_for_publication_never_owns_board_lock(tmp_path, monkeypatch):
    import contextlib
    import fcntl
    import threading
    root = tmp_path / "repo-guard"
    (root / "tool-snapshots").mkdir(parents=True)
    board = tmp_path / "coordination/active-sessions.md"
    board.parent.mkdir()
    board.write_text("fixture board")
    board_lock = board.parent / ".active-sessions.lock"
    board_lock.touch()
    fake = SimpleNamespace(lease_configuration=lambda _: None, declared_lease=lambda _: None,
                           rows=lambda *_args, **_kwargs: [])
    monkeypatch.setattr(p, "coordination", lambda: fake)
    import sys
    monkeypatch.setitem(sys.modules, "coordination_archive", SimpleNamespace(
        load_months=lambda *_: {}, local_months=lambda _: {}, decode_month=lambda *_: []))
    pending = threading.Event()
    original = p.locked
    errors = []
    @contextlib.contextmanager
    def observe(path):
        if path == root / "lifecycle.lock": pending.set()
        with original(path): yield
    monkeypatch.setattr(p, "locked", observe)
    def worker():
        try: p.prune(board, root)
        except BaseException as exc: errors.append(exc)
    with original(root / "lifecycle.lock"):
        thread = threading.Thread(target=worker)
        thread.start()
        assert pending.wait(3)
        descriptor = os.open(board_lock, os.O_RDWR)
        available = True
        try:
            try: fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: available = False
        finally: os.close(descriptor)
    thread.join(3)
    assert not thread.is_alive() and not errors
    assert available, "checkpoint publication must be able to take board lock while holding lifecycle"


def test_archive_retry_reestablishes_durability_before_source_removal(tmp_path, monkeypatch):
    path = snapshot(tmp_path)
    original_sync = p.sync_directory
    def interrupted(_): raise OSError("fixture interrupted before directory durability")
    monkeypatch.setattr(p, "sync_directory", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        run(tmp_path, [row("ended")])
    assert path.exists()
    [saved] = list((tmp_path / "tool-snapshots.archive").glob("*/*.json"))
    assert saved.read_bytes() == path.read_bytes()
    durable = []
    def sync(directory):
        durable.append(directory)
        return original_sync(directory)
    monkeypatch.setattr(p, "sync_directory", sync)
    original_unlink = Path.unlink
    def remove(candidate, *args, **kwargs):
        if candidate == path:
            assert all(directory in durable for directory in
                       (saved.parent, saved.parent.parent, tmp_path))
        return original_unlink(candidate, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", remove)
    assert run(tmp_path, [row("ended")])["archived"] == 1


def test_coordination_resolves_the_sibling_module(monkeypatch):
    import sys
    monkeypatch.setattr(sys, "path", sys.path.copy())
    for name in ("coordination", "coordination_archive"):
        monkeypatch.setitem(sys.modules, name, None)
        monkeypatch.delitem(sys.modules, name)
    module = p.coordination()
    assert Path(module.__file__).resolve() == Path(p.__file__).resolve().parent / "coordination.py"
