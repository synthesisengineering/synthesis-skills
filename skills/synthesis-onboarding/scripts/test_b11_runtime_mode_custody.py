"""The existing installer finalizes only its retained exact runtime inode."""
import os
from pathlib import Path

import pytest

import onboard
from system_contract import ContractError
from test_b11_component_payload import personal_phase


def fixture(tmp_path):
    target = tmp_path / "selected" / "runtime.py"
    target.parent.mkdir()
    target.write_text("expected released bytes\n")
    target.chmod(0o600)
    foreign = tmp_path / "foreign.py"
    foreign.write_text("foreign retained bytes\n")
    foreign.chmod(0o600)
    return target, foreign


def test_exact_source_mode_positive(tmp_path):
    target, _ = fixture(tmp_path)
    onboard.finalize_guard_runtime_mode(target, target.read_text())
    assert target.stat().st_mode & 0o777 == 0o755
    assert target.read_text() == "expected released bytes\n"


@pytest.mark.parametrize("kind", ["link", "hardlink", "content", "oversized", "relative"])
def test_invalid_mode_target_preserves_foreign_and_original(tmp_path, kind):
    target, foreign = fixture(tmp_path)
    content = target.read_text()
    if kind == "link":
        target.rename(target.with_name("retained.py"))
        target.symlink_to(foreign)
    elif kind == "hardlink":
        os.link(target, tmp_path / "retained-hardlink.py")
    elif kind == "content":
        content = "unmatched bytes"
    elif kind == "oversized":
        content = "x" * (4 * 1024 * 1024 + 1)
    elif kind == "relative":
        target = Path("not-an-absolute-target.py")
    with pytest.raises((ContractError, OSError, ValueError)):
        onboard.finalize_guard_runtime_mode(target, content)
    assert foreign.stat().st_mode & 0o777 == 0o600
    assert foreign.read_text() == "foreign retained bytes\n"
    if kind not in {"link", "relative"}:
        assert target.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("mutation", ["final-path", "ancestor", "content"])
def test_prewrite_change_refuses_without_mode_effect(tmp_path, monkeypatch, mutation):
    target, foreign = fixture(tmp_path)
    content = target.read_text()
    original = os.read
    observed = []
    def read(fd, size):
        raw = original(fd, size)
        if raw and not observed:
            observed.append(mutation)
            if mutation == "final-path":
                target.rename(target.with_name("retained.py"))
                target.symlink_to(foreign)
            elif mutation == "ancestor":
                parent = target.parent
                retained = parent.with_name("retained-dir")
                parent.rename(retained)
                parent.symlink_to(retained, target_is_directory=True)
            else:
                target.write_text("concurrently edited bytes\n")
        return raw
    monkeypatch.setattr(os, "read", read)
    with pytest.raises((ContractError, OSError, ValueError)):
        onboard.finalize_guard_runtime_mode(target, content)
    assert observed
    assert target.stat().st_mode & 0o777 == 0o600
    assert foreign.stat().st_mode & 0o777 == 0o600


def test_late_fd_write_never_changes_replacement_referent(tmp_path, monkeypatch):
    target, foreign = fixture(tmp_path)
    content = target.read_text()
    original = os.fchmod
    observed = []
    def fchmod(fd, mode):
        target.rename(target.with_name("retained.py"))
        target.symlink_to(foreign)
        observed.append(fd)
        original(fd, mode)
    monkeypatch.setattr(os, "fchmod", fchmod)
    with pytest.raises((ContractError, OSError, ValueError)):
        onboard.finalize_guard_runtime_mode(target, content)
    assert observed
    assert foreign.stat().st_mode & 0o777 == 0o600
    assert foreign.read_text() == "foreign retained bytes\n"
    assert target.with_name("retained.py").read_text() == content


def test_actual_phase_never_uses_path_chmod_for_engine_or_parser(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("runtime path-following chmod is forbidden")
    monkeypatch.setattr(Path, "chmod", forbidden)
    message, report = personal_phase(tmp_path, monkeypatch)
    assert not [step for step in report.steps if step["status"] == onboard.ERROR]
    assert (message / "message_guard.py").stat().st_mode & 0o777 == 0o755


@pytest.mark.parametrize("kind", ["directory", "fifo"])
def test_nonregular_mode_target_refuses_without_enumeration(tmp_path, monkeypatch, kind):
    target = tmp_path / "invalid-target"
    if kind == "directory":
        target.mkdir()
        (target / "sentinel").write_text("retained")
    else:
        os.mkfifo(target, 0o600)
    observed = []
    def no_enumeration(*args, **kwargs):
        observed.append(True)
        raise AssertionError("nonregular runtime must refuse before traversal")
    monkeypatch.setattr(Path, "rglob", no_enumeration)
    with pytest.raises((ContractError, OSError, ValueError)):
        onboard.finalize_guard_runtime_mode(target, "expected")
    assert not observed
    if kind == "directory":
        assert (target / "sentinel").read_text() == "retained"
