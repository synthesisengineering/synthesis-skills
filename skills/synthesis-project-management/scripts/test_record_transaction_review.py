from pathlib import Path
import os
import sys
import json
import stat
import shutil
import pytest

ROOT = Path(__file__).resolve().parents[3]
PM = ROOT / "skills/synthesis-project-management/scripts"
CTX = ROOT / "skills/synthesis-context-lifecycle/scripts"
sys.path[:0] = [str(PM), str(CTX)]
import record_transaction as rt  # noqa: E402 - candidate sibling modules require source path first
import test_record_transaction as retained  # noqa: E402 - candidate sibling modules require source path first
from test_run_admission import world as _world_fixture  # noqa: E402 - candidate sibling modules require source path first

world = _world_fixture
edits = retained.edits


@pytest.mark.parametrize("change", ["mode", "hardlink", "ancestor-symlink"])
def test_snapshot_revalidates_complete_path_identity(tmp_path, monkeypatch, change):
    parent = tmp_path / "records"
    parent.mkdir()
    target = parent / "plan.md"
    target.write_text("old\n")
    original = rt.os.fstat
    count = 0

    def race(fd):
        nonlocal count
        value = original(fd)
        if value.st_ino == target.stat().st_ino:
            count += 1
            if count == 2:
                if change == "mode":
                    os.chmod(target, 0o600)
                elif change == "hardlink":
                    os.link(target, parent / "alias.md")
                else:
                    parent.rename(tmp_path / "retained-records")
                    parent.symlink_to(
                        tmp_path / "retained-records", target_is_directory=True
                    )
        return value

    monkeypatch.setattr(rt.os, "fstat", race)
    with pytest.raises(rt.RecordTransactionError):
        rt._snapshot(target)


def test_lock_revalidates_ancestor_after_wait(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    original = rt.fcntl.flock
    changed = False

    def race(fd, flags):
        nonlocal changed
        result = original(fd, flags)
        if flags & rt.fcntl.LOCK_EX and not changed:
            changed = True
            project.rename(tmp_path / "retained-project")
            project.symlink_to(tmp_path / "retained-project", target_is_directory=True)
        return result

    monkeypatch.setattr(rt.fcntl, "flock", race)
    with pytest.raises(rt.RecordTransactionError):
        with rt.managed(project, exclusive=True):
            pass


@pytest.mark.parametrize("point", ["after-decision", "after-first", "after-last"])
def test_foreign_mode_or_bytes_never_become_accepted_generation(
    world, edits, monkeypatch, point
):
    original = rt.os.replace
    changed = False

    def race(src, dst):
        nonlocal changed
        result = original(src, dst)
        target = Path(dst)
        wanted = {
            "after-decision": "history.json",
            "after-first": "plan.md",
            "after-last": "REFERENCE.md",
        }[point]
        if target.name == wanted and not changed:
            changed = True
            (world["project"] / "REFERENCE.md").write_text("foreign work survives\n")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(rt.os, "replace", race)
        with pytest.raises(rt.RecordTransactionError):
            retained.apply(world, edits)
    assert (world["project"] / "REFERENCE.md").read_text() == "foreign work survives\n"
    before = retained.originals(world)
    with pytest.raises(rt.RecordTransactionError):
        retained.recover(world)
    assert retained.originals(world) == before
    with pytest.raises(rt.RecordTransactionError):
        with rt.managed(world["project"]):
            pass


@pytest.mark.parametrize("target", ["plan.md", "REFERENCE.md"])
def test_recovery_refuses_source_inode_replacement_with_identical_bytes(
    world, edits, monkeypatch, target
):
    retained.interrupted(world, edits, monkeypatch, 0)
    p = world["project"] / target
    replacement = p.with_suffix(".replacement")
    replacement.write_bytes(p.read_bytes())
    os.chmod(replacement, stat.S_IMODE(p.stat().st_mode))
    os.replace(replacement, p)
    before = retained.originals(world)
    with pytest.raises(rt.RecordTransactionError):
        retained.recover(world)
    assert retained.originals(world) == before


def test_completed_identity_cannot_be_erased_by_later_history_body(
    world, edits, monkeypatch
):
    result = retained.apply(world, edits)
    store = world["project"] / rt.STORE
    shutil.copytree(result["journal"], store / "active")
    (store / "history.json").write_text(
        json.dumps({"schema": 1, "active": None, "completed": {}})
    )
    before = retained.originals(world)
    with pytest.raises(rt.RecordTransactionError):
        retained.recover(world)
    assert retained.originals(world) == before


def test_readonly_barrier_nested_lock_and_mode_integrity(world, edits):
    before = retained.originals(world)
    with rt.managed(world["project"], exclusive=True):
        with rt.managed(world["project"]):
            assert rt.is_managed(world["project"])
    assert retained.originals(world) == before
    with rt.managed(world["project"]):
        with pytest.raises(rt.RecordTransactionError):
            with rt.managed(world["project"], exclusive=True):
                pass


def test_dryrun_preserves_full_project_directory_membership(world, edits):
    p = world["project"]
    before = {
        str(x.relative_to(p)): (x.read_bytes(), stat.S_IMODE(x.stat().st_mode))
        for x in p.rglob("*")
        if x.is_file()
    }
    assert retained.apply(world, edits, dry_run=True)["status"] == "dry-run"
    after = {
        str(x.relative_to(p)): (x.read_bytes(), stat.S_IMODE(x.stat().st_mode))
        for x in p.rglob("*")
        if x.is_file()
    }
    assert before == after and not list(p.glob(".record-transactions*"))
