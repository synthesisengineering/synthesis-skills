"""New records use the real transaction owner and exact synthetic admission."""

import os
from pathlib import Path
import pytest
from test_record_transaction import world as _world, apply, recover, write_board

import record_transaction as rt

world = _world


def requests():
    return [
        {"file": name, "create": {"text": "# Derived\n", "mode": 0o600}}
        for name in ("marker.json", "index.md")
    ]


def test_additive_absent_dryrun_and_commit(world):
    p = world["project"]
    original = (p / "CONTEXT.md").read_bytes()
    assert apply(world, requests(), dry_run=True)["changed"] is False
    assert not (p / rt.STORE).exists()
    result = apply(world, requests())
    assert result["status"] == "committed"
    assert (p / "marker.json").read_text() == "# Derived\n"
    assert (p / "CONTEXT.md").read_bytes() == original
    with pytest.raises(rt.RecordTransactionError):
        apply(world, requests())


@pytest.mark.parametrize("where", ["before-link", "after-link", "after-unlink"])
def test_creation_interruption_recovery(world, monkeypatch, where):
    link = rt.os.link
    unlink = Path.unlink

    def interrupted_link(src, dst, **kwargs):
        if Path(dst).name == "marker.json":
            if where == "before-link":
                raise OSError("fixture interruption")
            result = link(src, dst, **kwargs)
            if where == "after-link":
                raise OSError("fixture interruption")
            return result
        return link(src, dst, **kwargs)

    def interrupted_unlink(path, *args, **kwargs):
        result = unlink(path, *args, **kwargs)
        if where == "after-unlink" and path.name == "0.staged":
            raise OSError("fixture interruption")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(rt.os, "link", interrupted_link)
        patch.setattr(Path, "unlink", interrupted_unlink)
        with pytest.raises(OSError):
            apply(world, requests())
    assert recover(world)["status"] == "committed"
    assert (world["project"] / "marker.json").stat().st_nlink == 1


@pytest.mark.parametrize(
    "change", ["foreign-target", "third-link", "changed-mode", "noauthority"]
)
def test_recovery_preserves_foreign_creation(world, monkeypatch, change):
    link = rt.os.link

    def stop(src, dst, **kwargs):
        if change != "foreign-target":
            link(src, dst, **kwargs)
        raise OSError("fixture")

    with monkeypatch.context() as patch:
        patch.setattr(rt.os, "link", stop)
        with pytest.raises(OSError):
            apply(world, requests())
    p = world["project"]
    target = p / "marker.json"
    if change == "foreign-target":
        target.write_text("foreign")
    elif change == "third-link":
        os.link(target, p / "foreign-link")
    elif change == "changed-mode":
        target.chmod(0o644)
    else:
        write_board(world, claims=str(p / "CONTEXT.md"))
    before = target.read_bytes()
    mode = target.stat().st_mode
    with pytest.raises(rt.RecordTransactionError):
        recover(world)
    assert target.read_bytes() == before and target.stat().st_mode == mode
    assert not (p / "index.md").exists()


def test_new_target_race_never_overwrites(world, monkeypatch):
    link = rt.os.link

    def race(src, dst, **kwargs):
        Path(dst).write_text("foreign")
        return link(src, dst, **kwargs)

    monkeypatch.setattr(rt.os, "link", race)
    with pytest.raises(FileExistsError):
        apply(world, requests())
    assert (world["project"] / "marker.json").read_text() == "foreign"
