from pathlib import Path
import pytest
import delegation_boundary as owner
from test_managed_permissions import managed


class UnsafeOpen(AssertionError):
    pass


@pytest.mark.parametrize("fault", [None, "file-link", "ancestor-link"])
def test_delegated_read_never_follows_replacement_after_initial_stat(
    tmp_path, monkeypatch, fault
):
    parent = tmp_path / "admitted"
    parent.mkdir()
    target = parent / "input"
    target.write_bytes(b"synthetic admitted")
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "input").write_bytes(b"synthetic foreign")
    original_stat = Path.lstat
    original_open = Path.open
    changed = []

    def lstat(path, *a, **kw):
        result = original_stat(path, *a, **kw)
        if path == target and fault and not changed:
            changed.append(True)
            if fault == "file-link":
                target.rename(parent / "retained-input")
                target.symlink_to(foreign / "input")
            else:
                parent.rename(tmp_path / "retained-parent")
                parent.symlink_to(foreign, target_is_directory=True)
        return result

    def guarded_open(path, *a, **kw):
        if path == target and changed:
            raise UnsafeOpen(
                "Unbounded pathname read attempted after admitted path replacement"
            )
        return original_open(path, *a, **kw)

    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(Path, "open", guarded_open)
    if fault:
        with pytest.raises((ValueError, OSError)):
            owner._file(target)
        assert changed
    else:
        assert owner._file(target)["links"] == 1


@pytest.mark.parametrize("fault", ["grow", "mode", "pathname", "ancestor"])
def test_held_delegated_file_rejects_change_during_read(tmp_path, monkeypatch, fault):
    parent = tmp_path / "admitted"
    parent.mkdir()
    target = parent / "input"
    target.write_bytes(b"exact synthetic")
    original = owner.os.read
    changed = []

    def read(fd, count):
        raw = original(fd, count)
        if not changed:
            changed.append(True)
            if fault == "grow":
                with target.open("ab") as stream:
                    stream.write(b"new bytes")
            elif fault == "mode":
                target.chmod(0o700)
            elif fault == "pathname":
                target.rename(parent / "retained")
                target.write_bytes(b"exact synthetic")
            else:
                parent.rename(tmp_path / "retained")
                parent.mkdir()
                (parent / "input").write_bytes(b"exact synthetic")
        return raw

    monkeypatch.setattr(owner.os, "read", read)
    with pytest.raises((ValueError, OSError)):
        owner._file(target)
    assert changed


@pytest.mark.parametrize("limit", [True, -1, owner.MAX_FILE_BYTES + 1, 2])
def test_delegated_read_limit_refuses_before_content_open(tmp_path, monkeypatch, limit):
    target = tmp_path / "input"
    target.write_bytes(b"abc")

    def forbidden(*a, **kw):
        raise AssertionError("Invalid bound reached content read")

    monkeypatch.setattr(owner.os, "read", forbidden)
    with pytest.raises(ValueError):
        owner._read_file(target, limit=limit)


def test_delegated_regular_read_keeps_empty_and_hardlink_metadata(tmp_path):
    import os

    target = tmp_path / "empty"
    target.write_bytes(b"")
    os.link(target, tmp_path / "other")
    raw, metadata = owner._read_file(target, limit=0)
    assert raw == b"" and metadata["links"] == 2


__all__ = ["managed"]


def test_managed_profile_consumes_only_descriptor_bound_policy_bytes(
    managed, monkeypatch
):
    import managed_permissions

    contract = managed[0]["file_contract"]
    profile = Path(contract["permissions"]["source"]["path"])
    original = Path.read_bytes

    def read(path):
        if path == profile:
            raise AssertionError("Managed profile used second pathname read")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    assert (
        managed_permissions.inspect(contract)["source"]["digest"]
        == contract["permissions"]["source"]["digest"]
    )
