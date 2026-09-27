import importlib.util
import os
import sys
from pathlib import Path
import pytest

P = Path(__file__).with_name("ritual_workers.py")
spec = importlib.util.spec_from_file_location("root_ritual_workers", P)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def test_genuinely_absent_registry_is_single_session(tmp_path):
    assert m.load_workers(tmp_path / "absent.yaml") == {}


def test_broken_registered_link_is_not_absence(tmp_path):
    p = tmp_path / "workers.yaml"
    p.symlink_to(tmp_path / "missing-owner.yaml")
    with pytest.raises((m.RitualWorkersError, OSError)):
        m.load_workers(p)


@pytest.mark.parametrize("mutation", ["mode", "hardlink", "ancestor", "name"])
def test_final_path_identity_is_verified(tmp_path, monkeypatch, mutation):
    parent = tmp_path / "artifact"
    parent.mkdir()
    p = parent / "today.md"
    p.write_text("valid")
    p.chmod(0o600)
    real = m.os.fstat
    calls = 0

    def probe(fd):
        nonlocal calls
        st = real(fd)
        if st.st_ino == p.stat().st_ino:
            calls += 1
            if calls == 2:
                if mutation == "mode":
                    p.chmod(0o666)
                elif mutation == "hardlink":
                    os.link(p, parent / "alias")
                elif mutation == "ancestor":
                    moved = tmp_path / "moved"
                    parent.rename(moved)
                    parent.symlink_to(moved, target_is_directory=True)
                else:
                    p.rename(parent / "old")
                    p.write_text("replacement")
                    p.chmod(0o600)
        return st

    monkeypatch.setattr(m.os, "fstat", probe)
    with pytest.raises((m.RitualWorkersError, OSError)):
        m.read_regular(p, 100)


def test_normal_owned_artifact_roundtrip(tmp_path):
    p = tmp_path / "a"
    p.write_bytes(b"ordinary")
    p.chmod(0o600)
    assert m.read_regular(p, 100) == b"ordinary"


def test_verified_owner_registry_link_is_supported(tmp_path):
    target = tmp_path / "owner.yaml"
    target.write_text("contract_version: 1\nworkers: {}\n")
    target.chmod(0o600)
    p = tmp_path / "workers.yaml"
    p.symlink_to(target)
    assert m.load_workers(p) == {}


def test_disappearing_selected_registry_is_not_absence(tmp_path, monkeypatch):
    p = tmp_path / "workers.yaml"
    p.write_text("contract_version: 1\nworkers: {}\n")

    def vanished(*args, **kwargs):
        raise FileNotFoundError("selected registry disappeared")

    monkeypatch.setattr(m, "read_regular", vanished)
    with pytest.raises(m.RitualWorkersError):
        m.load_workers(p)


def test_explicit_parent_traversal_is_refused(tmp_path):
    p = tmp_path / "a"
    p.mkdir()
    f = tmp_path / "ordinary"
    f.write_text("value")
    f.chmod(0o600)
    with pytest.raises(m.RitualWorkersError):
        m.read_regular(p / ".." / "ordinary", 100)
