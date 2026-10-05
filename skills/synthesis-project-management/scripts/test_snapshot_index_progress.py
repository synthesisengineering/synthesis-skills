"""Bounded snapshot indexing must not repeatedly spend work on completed files."""

from collections import Counter
import hashlib

import pytest

import prune_tool_snapshots as p
from test_prune_tool_snapshots import snapshot


def test_index_authenticates_existing_references_with_one_key_observation(tmp_path, monkeypatch):
    paths = [snapshot(tmp_path, session="owner-" + str(index)) for index in range(20)]
    p.index_retained(tmp_path)
    before = {path: path.read_bytes() for path in paths}
    original = p._owner_key
    calls = []
    def key(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(p, "_owner_key", key)
    assert p.index_retained(tmp_path) == {"indexed": 0, "unchanged": 20, "payloads_moved": 0}
    assert len(calls) <= 2
    assert all(path.read_bytes() == raw for path, raw in before.items())


def test_index_reads_unindexed_payload_once(tmp_path, monkeypatch):
    paths = [snapshot(tmp_path, session="owner-" + str(index)) for index in range(3)]
    read = p.read_regular
    calls = Counter()
    def observed(path, **kwargs):
        if path in paths:
            calls[path] += 1
        return read(path, **kwargs)
    monkeypatch.setattr(p, "read_regular", observed)
    assert p.index_retained(tmp_path)["indexed"] == 3
    assert calls == {path: 1 for path in paths}


def test_index_retains_authenticated_prefix_when_next_payload_expires(tmp_path, monkeypatch):
    paths = sorted(snapshot(tmp_path, session="owner-" + str(index)) for index in range(3))
    before = {path: path.read_bytes() for path in paths}
    original = p.publish_owner_reference
    calls = []
    def publish(path, session_id, *, deadline=None):
        calls.append(path)
        if len(calls) == 2:
            raise RuntimeError("snapshot observation exceeded its time ceiling; evidence retained")
        return original(path, session_id, deadline=deadline)
    monkeypatch.setattr(p, "publish_owner_reference", publish)
    with pytest.raises(RuntimeError, match="time ceiling"):
        p.index_retained(tmp_path)
    assert p._owner_path(paths[0]).is_file()
    assert not p._owner_path(paths[1]).exists()
    assert all(path.read_bytes() == raw for path, raw in before.items())
    monkeypatch.setattr(p, "publish_owner_reference", original)
    assert p.index_retained(tmp_path) == {"indexed": 2, "unchanged": 1, "payloads_moved": 0}
    assert all(p._reference(path)["owner"] for path in paths)


def test_index_key_replacement_refuses_without_deleting_snapshots(tmp_path, monkeypatch):
    path = snapshot(tmp_path)
    p.index_retained(tmp_path)
    before = path.read_bytes()
    reference = p._reference
    def changed(*args, **kwargs):
        result = reference(*args, **kwargs)
        (path.parent / ".owner-key").write_bytes(b"x" * 32)
        return result
    monkeypatch.setattr(p, "_reference", changed)
    with pytest.raises((RuntimeError, ValueError), match="key"):
        p.index_retained(tmp_path)
    assert path.read_bytes() == before


def test_maintenance_derives_owner_but_explicit_wrong_owner_still_refuses(tmp_path):
    path = snapshot(tmp_path, session="correct-owner")
    before = path.read_bytes()
    with pytest.raises((RuntimeError, ValueError), match="owner|session"):
        p.publish_owner_reference(path, "different-owner")
    p.publish_owner_reference(path, None)
    assert p._reference(path)["owner"] == hashlib.sha256(b"correct-owner").hexdigest()
    assert path.read_bytes() == before


def test_index_current_references_still_share_ten_second_observation(tmp_path, monkeypatch):
    paths = [snapshot(tmp_path, session="owner-" + str(index)) for index in range(20)]
    p.index_retained(tmp_path)
    original = p._reference
    clock = [0.0]
    monkeypatch.setattr(p.time, "monotonic", lambda: clock[0])
    def slow_reference(*args, **kwargs):
        clock[0] += 0.6
        return original(*args, **kwargs)
    monkeypatch.setattr(p, "_reference", slow_reference)
    with pytest.raises(RuntimeError, match="time ceiling"):
        p.index_retained(tmp_path)
    assert 10 <= clock[0] < 11
    assert all(path.is_file() and p._owner_path(path).is_file() for path in paths)
