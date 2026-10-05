"""Fresh dirty-scan closure and work bounds on real filesystem leaves."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import os
import subprocess
import pytest
import project_state as state


def inventory(monkeypatch, root, names):
    raw = b"".join(b"?? " + os.fsencode("project/" + name) + b"\0" for name in names)
    monkeypatch.setattr(state, "_run", lambda *a, **k: subprocess.CompletedProcess(a, 0, raw, b""))
    return lambda: state._dirty_project_files(root, "project")


def descriptors(monkeypatch):
    original = state.os
    active = set()
    opened = []
    peak = [0]
    proxy = SimpleNamespace(**vars(original))
    def capture(fd):
        active.add(fd)
        peak[0] = max(peak[0], len(active))
        return fd
    def open_file(name, flags, *a, **k):
        opened.append((name, flags))
        return capture(original.open(name, flags, *a, **k))
    def duplicate(fd):
        return capture(original.dup(fd))
    def close(fd):
        original.close(fd)
        active.remove(fd)
    proxy.open, proxy.dup, proxy.close = open_file, duplicate, close
    monkeypatch.setattr(state, "os", proxy)
    return original, proxy, active, opened, peak


def test_shared_directory_admissions_keep_every_leaf_and_depth_bound(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    parent = root / "project/deep/parent"
    parent.mkdir(parents=True)
    names = [f"deep/parent/leaf-{i:03}" for i in range(80)]
    for i, name in enumerate(names):
        (root / "project" / name).write_bytes((str(i) + "\n").encode() * 7)
    scan = inventory(monkeypatch, root, names)
    original, proxy, active, opened, peak = descriptors(monkeypatch)
    rows = scan()
    assert len(rows) == len(names)
    assert all(row["sha256"] == hashlib.sha256(Path(row["path"]).read_bytes()).hexdigest() for row in rows)
    assert [row["path"] for row in rows] == sorted(str(root / "project" / n) for n in names)
    directory_opens = sum(bool(flags & os.O_DIRECTORY) for _, flags in opened)
    assert directory_opens == len(parent.parts)
    assert peak[0] <= len(parent.parts) + 2
    assert not active


@pytest.mark.parametrize("change", ["replace", "symlink"])
def test_later_leaf_cannot_hide_earlier_parent_replacement(tmp_path, monkeypatch, change):
    root = tmp_path.resolve()
    parent = root / "project/parent"
    parent.mkdir(parents=True)
    (parent / "a").write_text("first")
    (parent / "b").write_text("second")
    scan = inventory(monkeypatch, root, ["parent/a", "parent/b"])
    original = state._dirty_leaf_snapshot
    def capture(path, **kwargs):
        result = original(path, **kwargs)
        if path.name == "a":
            parent.rename(root / "retained-parent")
            if change == "replace":
                parent.mkdir()
            else:
                parent.symlink_to(root / "retained-parent", target_is_directory=True)
        return result
    monkeypatch.setattr(state, "_dirty_leaf_snapshot", capture)
    _, _, active, _, _ = descriptors(monkeypatch)
    with pytest.raises(state.ProjectStateError, match="ancestor changed"):
        scan()
    assert not active


def test_missing_parent_appearing_after_deleted_leaf_refuses(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    (root / "project").mkdir()
    (root / "project/last").write_text("last")
    scan = inventory(monkeypatch, root, ["missing/a", "last"])
    original = state._dirty_leaf_snapshot
    def capture(path, **kwargs):
        result = original(path, **kwargs)
        if path.name == "a":
            (root / "project/missing").mkdir()
        return result
    monkeypatch.setattr(state, "_dirty_leaf_snapshot", capture)
    _, _, active, _, _ = descriptors(monkeypatch)
    with pytest.raises(state.ProjectStateError, match="ancestor changed"):
        scan()
    assert not active


@pytest.mark.parametrize("failure", ["read", "cancel"])
def test_scan_releases_current_chain_on_every_leaf_failure(tmp_path, monkeypatch, failure):
    root = tmp_path.resolve()
    parent = root / "project/parent"
    parent.mkdir(parents=True)
    (parent / "a").write_text("bytes")
    scan = inventory(monkeypatch, root, ["parent/a"])
    _, proxy, active, _, _ = descriptors(monkeypatch)
    class Cancelled(BaseException):
        pass
    error = OSError("synthetic read failure") if failure == "read" else Cancelled()
    def fail(*a, **k):
        raise error
    proxy.read = fail
    with pytest.raises((state.ProjectStateError, OSError, Cancelled)):
        scan()
    assert not active


def test_reopened_parent_keeps_its_original_identity(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    for dirname in ["a", "b"]:
        (root / "project" / dirname).mkdir(parents=True)
    for name in ["a/first", "b/middle", "a/last"]:
        (root / "project" / name).write_text(name)
    scan = inventory(monkeypatch, root, ["a/first", "b/middle", "a/last"])
    original = state._dirty_leaf_snapshot
    def capture(path, **kwargs):
        result = original(path, **kwargs)
        if path.name == "middle":
            (root / "project/a").rename(root / "retained-a")
            (root / "project/a").mkdir()
            (root / "project/a/last").write_text("foreign")
        return result
    monkeypatch.setattr(state, "_dirty_leaf_snapshot", capture)
    _, _, active, _, _ = descriptors(monkeypatch)
    with pytest.raises(state.ProjectStateError, match="ancestor changed"):
        scan()
    assert not active


def test_new_scan_reads_changed_bytes_without_prior_observation(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    (root / "project").mkdir()
    leaf = root / "project/leaf"
    leaf.write_bytes(b"before")
    scan = inventory(monkeypatch, root, ["leaf"])
    before = scan()
    leaf.write_bytes(b"after")
    after = scan()
    assert before[0]["sha256"] == hashlib.sha256(b"before").hexdigest()
    assert after[0]["sha256"] == hashlib.sha256(b"after").hexdigest()
    assert before != after


@pytest.mark.parametrize("relative", ["../outside", "projectish/outside"])
def test_lexical_project_scope_never_accepts_prefix_collision(tmp_path, monkeypatch, relative):
    root = tmp_path.resolve()
    raw = b"?? " + os.fsencode(relative) + b"\0"
    monkeypatch.setattr(state, "_run", lambda *a, **k: subprocess.CompletedProcess(a, 0, raw, b""))
    with pytest.raises(state.ProjectStateError):
        state._dirty_project_files(root, "project")


def test_shared_parent_does_not_rebuild_root_chain_for_each_leaf(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    parent = root / "project/deep/parent"
    parent.mkdir(parents=True)
    names = [f"deep/parent/leaf-{i}" for i in range(40)]
    for name in names:
        (root / "project" / name).write_text(name)
    scan = inventory(monkeypatch, root, names)
    original = Path.__truediv__
    root_joins = []
    def joined(path, part):
        if str(path) == path.anchor:
            root_joins.append(part)
        return original(path, part)
    monkeypatch.setattr(Path, "__truediv__", joined)
    assert len(scan()) == 40
    assert len(root_joins) == 1


def test_repeated_normalization_avoids_path_reconstruction(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    target = root / "target"
    target.mkdir()
    alias = root / "alias"
    alias.symlink_to(target, target_is_directory=True)
    original = state.Path
    calls = []
    def counted(value):
        calls.append(value)
        return original(value)
    monkeypatch.setattr(state, "Path", counted)
    observed = state._ManifestPathObservations()
    spelling = str(alias / "leaf")
    expected = str(target / "leaf")
    assert observed(spelling) == expected
    first_calls = len(calls)
    for _ in range(200):
        assert observed(spelling) == expected
    assert len(calls) == first_calls
    observed.verify()


@pytest.mark.parametrize("change", ["retarget", "missing"])
def test_memoized_normalization_keeps_closure_and_next_request_fresh(tmp_path, change):
    root = tmp_path.resolve()
    old, new = root / "old", root / "new"
    old.mkdir()
    new.mkdir()
    parent = root / "parent"
    if change == "retarget":
        parent.symlink_to(old, target_is_directory=True)
    spelling = str(parent / "leaf")
    observed = state._ManifestPathObservations()
    prior = observed(spelling)
    if change == "retarget":
        parent.unlink()
    parent.symlink_to(new, target_is_directory=True)
    assert observed(spelling) == prior
    with pytest.raises(state.ProjectStateError, match="manifest parent changed"):
        observed.verify()
    fresh = state._ManifestPathObservations()
    assert fresh(spelling) == str(new / "leaf")
    fresh.verify()
