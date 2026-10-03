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


def test_owner_references_skip_unrelated_payload_reads(tmp_path, monkeypatch):
    own = snapshot(tmp_path, session="ours")
    foreign = [snapshot(tmp_path, session="foreign-" + str(i), suffix=str(i)) for i in range(12)]
    for path in foreign:
        data = json.loads(path.read_bytes()); data["dirty"] = {"large": "x" * 262144}
        path.write_text(json.dumps(data))
    originals = {path: path.read_bytes() for path in [own, *foreign]}
    before = {path: p._identity(path.stat()) for path in originals}
    assert p.index_retained(tmp_path) == {"indexed": 13, "unchanged": 0, "payloads_moved": 0}
    assert p.index_retained(tmp_path) == {"indexed": 0, "unchanged": 13, "payloads_moved": 0}
    calls = []
    original = p.read_regular
    def observed(path, **kwargs):
        if path.parent == own.parent and path.suffix == ".json":
            calls.append(path)
        return original(path, **kwargs)
    monkeypatch.setattr(p, "read_regular", observed)
    selected = p.selected_snapshots(own.parent, "ours")
    assert [row[0] for row in selected] == [own]
    assert calls == [own]
    assert all(path.read_bytes() == raw and p._identity(path.stat()) == before[path]
               for path, raw in originals.items())


@pytest.mark.parametrize("mutation", ["bad-mac", "foreign-name", "extra-field", "symlink", "bad-mode"])
def test_owner_reference_refusals_preserve_payloads(tmp_path, mutation):
    path = snapshot(tmp_path)
    p.index_retained(tmp_path)
    reference = p._owner_path(path)
    original = path.read_bytes()
    if mutation == "symlink":
        kept = tmp_path / "retained-ref"; reference.rename(kept); reference.symlink_to(kept)
    elif mutation == "bad-mode":
        reference.chmod(0o644)
    else:
        data = json.loads(reference.read_bytes())
        if mutation == "bad-mac": data["mac"] = "0" * 64
        elif mutation == "foreign-name": data["body"]["snapshot"] = "foreign.json"
        else: data["body"]["private"] = True
        reference.write_text(json.dumps(data))
    with pytest.raises((ValueError, RuntimeError)):
        p.selected_snapshots(path.parent, "someone-else")
    assert path.read_bytes() == original


def test_stale_and_missing_reference_reconcile_explicitly_without_losing_ownership(tmp_path):
    path = snapshot(tmp_path, session="before")
    p.index_retained(tmp_path)
    data = json.loads(path.read_bytes()); data["session_id"] = "after"
    path.write_text(json.dumps(data))
    raw = path.read_bytes()
    assert [row[0] for row in p.selected_snapshots(path.parent, "after")] == [path]
    assert p.selected_snapshots(path.parent, "before") == []
    assert p.index_retained(tmp_path)["indexed"] == 1
    assert path.read_bytes() == raw
    new = snapshot(tmp_path, session="after", suffix="new")
    assert {row[0] for row in p.selected_snapshots(path.parent, "after")} == {path, new}


def test_old_start_lineage_and_recent_delta_are_both_selected(tmp_path):
    old = snapshot(tmp_path, session="ours", suffix="old", age=10000000)
    data = json.loads(old.read_bytes()); data["started_at"] = 100
    old.write_text(json.dumps(data))
    recent = snapshot(tmp_path, session="ours", suffix="recent", age=1)
    data = json.loads(recent.read_bytes()); data["started_at"] = 200; data["changed"] = ["/fixture/projects/ours/CONTEXT.md"]
    recent.write_text(json.dumps(data))
    p.index_retained(tmp_path)
    selected = p.selected_snapshots(old.parent, "ours")
    assert {row[0] for row in selected} == {old, recent}
    assert min(row[1]["started_at"] for row in selected) == 100
    assert any(row[1].get("changed") for row in selected)


def test_unclassified_or_oversize_legacy_records_refuse_without_deletion(tmp_path, monkeypatch):
    path = snapshot(tmp_path)
    original = path.read_bytes()
    monkeypatch.setattr(p, "SNAPSHOT_TOTAL_BYTES", len(original) - 1)
    with pytest.raises(ValueError, match="byte ceiling"):
        p.selected_snapshots(path.parent, "ended")
    assert path.read_bytes() == original
    monkeypatch.setattr(p, "SNAPSHOT_TOTAL_BYTES", 100000)
    path.write_text('{"session_id":"ended","session_id":"foreign"}')
    with pytest.raises(ValueError, match="duplicate"):
        p.selected_snapshots(path.parent, "ended")
    assert path.exists()


def test_owner_reconciliation_and_prune_keep_live_and_archived_custody(tmp_path):
    ended = snapshot(tmp_path, session="ended")
    live = snapshot(tmp_path, session="live", suffix="live")
    p.index_retained(tmp_path)
    raw = {path: path.read_bytes() for path in (ended, live)}
    assert run(tmp_path, [row("ended"), row("live", "active")])["archived"] == 1
    assert not ended.exists() and not p._owner_path(ended).exists()
    assert live.read_bytes() == raw[live] and p._owner_path(live).exists()
    assert [item[0] for item in p.selected_snapshots(live.parent, "live")] == [live]
    [archived] = list((tmp_path / "tool-snapshots.archive").glob("*/*.json"))
    assert archived.read_bytes() == raw[ended]


def test_selected_read_serializes_concurrent_append(tmp_path, monkeypatch):
    import threading
    first = snapshot(tmp_path, session="ours")
    p.index_retained(tmp_path)
    entered, release, written = threading.Event(), threading.Event(), threading.Event()
    original = p.read_regular
    errors = []
    result = []
    def reading(path, **kwargs):
        if path == first:
            entered.set()
            assert release.wait(3)
        return original(path, **kwargs)
    monkeypatch.setattr(p, "read_regular", reading)
    def reader():
        try: result.extend(p.selected_snapshots(first.parent, "ours"))
        except BaseException as exc: errors.append(exc)
    def writer():
        try:
            with p.locked(first.parent / ".snapshot.lock", deadline=p.time.monotonic() + 3):
                new = snapshot(tmp_path, session="ours", suffix="new")
                p.publish_owner_reference(new, "ours")
                written.set()
        except BaseException as exc: errors.append(exc)
    reading_thread = threading.Thread(target=reader); reading_thread.start()
    assert entered.wait(3)
    writing_thread = threading.Thread(target=writer); writing_thread.start()
    assert not written.wait(0.05)
    release.set(); reading_thread.join(3); writing_thread.join(3)
    assert not reading_thread.is_alive() and not writing_thread.is_alive() and not errors
    assert [row[0] for row in result] == [first]
    assert len(p.selected_snapshots(first.parent, "ours")) == 2


def test_selected_read_lock_and_listing_are_finite(tmp_path, monkeypatch):
    path = snapshot(tmp_path)
    monkeypatch.setattr(p, "SNAPSHOT_FILES", 0)
    with pytest.raises(ValueError, match="count ceiling"):
        p.selected_snapshots(path.parent, "ended")
    with p.locked(path.parent / ".snapshot.lock"):
        monkeypatch.setattr(p, "SNAPSHOT_SECONDS", 0.02)
        with pytest.raises(RuntimeError, match="time ceiling"):
            p.selected_snapshots(path.parent, "ended")
    assert path.exists()


def test_foreign_payload_changed_during_reference_selection_refuses(tmp_path, monkeypatch):
    path = snapshot(tmp_path, session="foreign")
    p.index_retained(tmp_path)
    original = p._reference
    def race(candidate, key=None):
        result = original(candidate, key)
        if candidate == path:
            data = json.loads(path.read_bytes()); data["session_id"] = "ours"
            path.write_text(json.dumps(data))
        return result
    monkeypatch.setattr(p, "_reference", race)
    with pytest.raises(RuntimeError, match="changed"):
        p.selected_snapshots(path.parent, "ours")
    assert json.loads(path.read_bytes())["session_id"] == "ours"


def test_uncooperative_append_is_not_a_complete_snapshot_listing(tmp_path, monkeypatch):
    path = snapshot(tmp_path, session="ours")
    p.index_retained(tmp_path)
    original = p.read_regular
    added = []
    def race(candidate, **kwargs):
        result = original(candidate, **kwargs)
        if candidate == path and not added:
            added.append(snapshot(tmp_path, session="ours", suffix="late"))
        return result
    monkeypatch.setattr(p, "read_regular", race)
    with pytest.raises(RuntimeError, match="directory changed"):
        p.selected_snapshots(path.parent, "ours")
    assert added[0].exists() and path.exists()


def test_owner_publication_pins_parent_descriptor(tmp_path, monkeypatch):
    path = snapshot(tmp_path)
    p.index_retained(tmp_path)
    owners = p._owner_path(path).parent
    retained = owners.with_name("retained-owners")
    original = os.replace
    changed = []
    def race(source, destination, **kwargs):
        if str(source).startswith(".owner-") and not changed:
            owners.rename(retained); owners.mkdir(mode=0o700)
            changed.append(True)
        return original(source, destination, **kwargs)
    monkeypatch.setattr(os, "replace", race)
    raw = path.read_bytes()
    with pytest.raises(RuntimeError, match="parent changed"):
        p.publish_owner_reference(path, "ended")
    assert changed and path.read_bytes() == raw
    assert not list(owners.iterdir())
    assert list(retained.iterdir())


def test_owner_key_change_refuses_selection_and_preserves_payload(tmp_path, monkeypatch):
    path = snapshot(tmp_path, session="ours")
    p.index_retained(tmp_path)
    original = p.read_regular
    def race(candidate, **kwargs):
        result = original(candidate, **kwargs)
        if candidate == path:
            (path.parent / ".owner-key").write_bytes(b"x" * 32)
        return result
    monkeypatch.setattr(p, "read_regular", race)
    raw = path.read_bytes()
    with pytest.raises(RuntimeError, match="key changed"):
        p.selected_snapshots(path.parent, "ours")
    assert path.read_bytes() == raw


def test_selected_growth_cannot_cross_remaining_byte_budget(tmp_path, monkeypatch):
    path = snapshot(tmp_path, session="ours")
    budget = path.stat().st_size + 1
    monkeypatch.setattr(p, "SNAPSHOT_TOTAL_BYTES", budget)
    original = p.read_regular
    limits = []
    def grow(candidate, **kwargs):
        if candidate == path:
            limits.append(kwargs["limit"])
            data = json.loads(path.read_bytes()); data["dirty"]["larger"] = "x" * 10000
            path.write_text(json.dumps(data))
        return original(candidate, **kwargs)
    monkeypatch.setattr(p, "read_regular", grow)
    with pytest.raises(ValueError, match="byte ceiling"):
        p.selected_snapshots(path.parent, "ours")
    assert limits == [budget]
    assert path.stat().st_size > budget


def test_selected_lock_parent_replacement_cannot_create_foreign_lock(tmp_path, monkeypatch):
    path = snapshot(tmp_path, session="ours")
    p.index_retained(tmp_path)
    directory = path.parent
    retained = tmp_path / "retained-snapshots"
    changed = []
    original = os.open
    def race(name, flags, *args, **kwargs):
        if Path(name).name == ".snapshot.lock" and not changed:
            directory.rename(retained); directory.mkdir()
            changed.append(True)
        return original(name, flags, *args, **kwargs)
    monkeypatch.setattr(os, "open", race)
    with pytest.raises(RuntimeError, match="parent changed"):
        p.selected_snapshots(directory, "ours")
    assert changed and not list(directory.iterdir())
    assert (retained / path.name).exists()


def test_owner_publication_expiry_after_parse_preserves_prior_reference(tmp_path, monkeypatch):
    path = snapshot(tmp_path)
    p.index_retained(tmp_path)
    reference = p._owner_path(path)
    before = path.read_bytes(), reference.read_bytes()
    clock = [10.0]
    original = p._strict_json
    def parsed(raw):
        result = original(raw); clock[0] = 12.0; return result
    monkeypatch.setattr(p.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(p, "_strict_json", parsed)
    with pytest.raises(RuntimeError, match="time ceiling"):
        p.publish_owner_reference(path, "ended", deadline=11.0)
    assert (path.read_bytes(), reference.read_bytes()) == before


def test_index_propagates_original_deadline_into_publication(tmp_path, monkeypatch):
    path = snapshot(tmp_path)
    raw = path.read_bytes()
    clock = [10.0]; deadlines = []
    original = p.publish_owner_reference
    def delayed(path, session_id, *, deadline=None):
        deadlines.append(deadline); clock[0] = 21.0
        return original(path, session_id, deadline=deadline)
    monkeypatch.setattr(p.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(p, "publish_owner_reference", delayed)
    with pytest.raises(RuntimeError, match="time ceiling"):
        p.index_retained(tmp_path)
    assert deadlines == [20.0] and path.read_bytes() == raw
    assert not p._owner_path(path).exists()
