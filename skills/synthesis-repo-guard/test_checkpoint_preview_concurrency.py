"""Read-only previews must not monopolize attribution writers' locks."""

import fcntl
import json
import os
import threading

import pytest

from test_checkpoint_sync import MODULE, isolated_runtime  # noqa: F401
from test_checkpoint_sync import _observed_process_group


@pytest.mark.parametrize("scope", ["all", "session"])
def test_preview_analysis_releases_writer_locks_and_refuses_changed_manifest(tmp_path, monkeypatch, scope):
    MODULE.PENDING_DIR.mkdir(parents=True)
    manifest = MODULE.pending_manifest_path("synthetic-owner")
    original = {"schema_version": 1, "session_id": "synthetic-owner", "paths": [], "remote_paths": []}
    manifest.write_text(json.dumps(original))
    entered, release = threading.Event(), threading.Event()
    results, failures = [], []
    def slow_analysis(_grouped):
        entered.set()
        assert release.wait(5)
        return {}
    monkeypatch.setattr(MODULE, "source_groups_remote_ready", slow_analysis)
    def preview():
        try:
            result = (MODULE.flush_all_pending({}, dry_run=True) if scope == "all" else
                      MODULE.flush_pending_session({}, "synthetic-owner", dry_run=True))
            results.append(result)
        except BaseException as exc:
            failures.append(exc)
    thread = threading.Thread(target=preview)
    thread.start()
    lifecycle = owner = None
    try:
        assert entered.wait(5)
        lifecycle = MODULE.open_lock_file(MODULE.lifecycle_lock_path())
        fcntl.flock(lifecycle, fcntl.LOCK_SH | fcntl.LOCK_NB)
        owner = MODULE.open_lock_file(manifest.with_suffix(".lock"))
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest.write_text(json.dumps({**original, "updated_at": "synthetic-progress"}))
    finally:
        if owner is not None:
            os.close(owner)
        if lifecycle is not None:
            os.close(lifecycle)
        release.set()
        thread.join(5)
    assert not thread.is_alive()
    assert not results
    assert len(failures) == 1 and "changed" in str(failures[0])
    assert json.loads(manifest.read_text())["updated_at"] == "synthetic-progress"


def test_shared_preview_cannot_upgrade_to_mutation_authority(tmp_path):
    with MODULE.lifecycle_lock(shared=True, timeout=1):
        with pytest.raises(ValueError, match="upgrade"):
            with MODULE.lifecycle_lock():
                pytest.fail("read-only scope became mutation authority")


def test_publication_still_excludes_writers_during_analysis(tmp_path, monkeypatch):
    MODULE.PENDING_DIR.mkdir(parents=True)
    manifest = MODULE.pending_manifest_path("synthetic-owner")
    manifest.write_text(json.dumps({"schema_version": 1, "session_id": "synthetic-owner", "paths": [], "remote_paths": []}))
    checked = []
    def analysis(_grouped):
        descriptor = MODULE.open_lock_file(MODULE.lifecycle_lock_path())
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
            checked.append(True)
        finally:
            os.close(descriptor)
        return {}
    monkeypatch.setattr(MODULE, "source_groups_remote_ready", analysis)
    MODULE.flush_all_pending({}, dry_run=False)
    assert checked == [True]


def test_global_preview_refuses_new_manifest_but_preserves_it(tmp_path, monkeypatch):
    MODULE.PENDING_DIR.mkdir(parents=True)
    manifest = MODULE.pending_manifest_path("arriving-owner")
    raw = json.dumps({"schema_version": 1, "session_id": "arriving-owner", "paths": [], "remote_paths": []})
    def analysis(_grouped):
        manifest.write_text(raw)
        return {}
    monkeypatch.setattr(MODULE, "source_groups_remote_ready", analysis)
    with pytest.raises(ValueError, match="set changed"):
        MODULE.flush_all_pending({}, dry_run=True)
    assert manifest.read_text() == raw


@pytest.mark.parametrize("mutation", ["replace", "unlink", "symlink"])
def test_preview_refuses_disappeared_or_replaced_manifest(tmp_path, monkeypatch, mutation):
    MODULE.PENDING_DIR.mkdir(parents=True)
    manifest = MODULE.pending_manifest_path("synthetic-owner")
    raw = json.dumps({"schema_version": 1, "session_id": "synthetic-owner", "paths": [], "remote_paths": []})
    manifest.write_text(raw)
    foreign = tmp_path / "foreign.json"
    foreign.write_text(raw)
    def analysis(_grouped):
        manifest.unlink()
        if mutation == "replace":
            manifest.write_text(raw)
        elif mutation == "symlink":
            manifest.symlink_to(foreign)
        return {}
    monkeypatch.setattr(MODULE, "source_groups_remote_ready", analysis)
    with pytest.raises(ValueError, match="changed"):
        MODULE.flush_pending_session({}, "synthetic-owner", dry_run=True)
    assert foreign.read_text() == raw


def test_manifest_preview_lock_wait_uses_finite_shared_deadline(tmp_path, monkeypatch):
    MODULE.PENDING_DIR.mkdir(parents=True)
    manifest = MODULE.pending_manifest_path("synthetic-owner")
    manifest.write_text(json.dumps({"schema_version": 1, "session_id": "synthetic-owner", "paths": [], "remote_paths": []}))
    descriptor = MODULE.open_lock_file(manifest.with_suffix(".lock"))
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    clock = [0.0]
    monkeypatch.setattr(MODULE.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(MODULE.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    try:
        results, loaded = MODULE.flush_all_pending({}, dry_run=True)
    finally:
        os.close(descriptor)
    assert loaded == []
    assert any("time ceiling" in (item.get("alert") or "") for item in results)
    assert 10 <= clock[0] < 10.1


def test_stable_preview_does_not_write_manifest_or_publication(tmp_path, monkeypatch):
    MODULE.PENDING_DIR.mkdir(parents=True)
    manifest = MODULE.pending_manifest_path("synthetic-owner")
    raw = json.dumps({"schema_version": 1, "session_id": "synthetic-owner", "paths": [], "remote_paths": []})
    manifest.write_text(raw)
    monkeypatch.setattr(MODULE, "source_groups_remote_ready", lambda _: {})
    results, loaded = MODULE.flush_pending_session({}, "synthetic-owner", dry_run=True)
    assert loaded == [manifest]
    assert not any(item.get("alert") for item in results)
    assert manifest.read_text() == raw
    assert not (MODULE.STATE_DIR / "publication").exists()


def test_test_recorder_preserves_unknown_group_after_child_exit(monkeypatch):
    def exited(_pid):
        raise ProcessLookupError("synthetic child has exited")
    monkeypatch.setattr(os, "getpgid", exited)
    assert _observed_process_group(12345) is None
