"""Independent archive closure controls using synthetic bytes and real owners."""

from pathlib import Path
import pytest
from test_native_archive import fixture


def test_added_member_during_final_read_cannot_verify_as_closed(tmp_path, monkeypatch):
    archive, _source, binding, route, home, _raw = fixture(tmp_path)
    manifest = archive.capture(home, binding, route)
    target = tmp_path / "portable"
    archive.export(home, manifest, target)
    assert archive.verify_export(target)["status"] == "PASS"
    original = archive.storage.read_regular
    reads = 0

    def changed(path, *args, **kwargs):
        nonlocal reads
        result = original(path, *args, **kwargs)
        if Path(path) == target / "manifest.json":
            reads += 1
            if reads == 2:
                (target / "unlisted-evidence").write_bytes(
                    b"synthetic unexpected member"
                )
        return result

    monkeypatch.setattr(archive.storage, "read_regular", changed)
    with pytest.raises(ValueError, match="member|changed|inventory|directory"):
        archive.verify_export(target)
    assert reads == 2 and (target / "unlisted-evidence").is_file()


def test_restore_refuses_existing_unlisted_member_before_materialization(tmp_path):
    archive, _source, binding, route, home, raw = fixture(tmp_path)
    manifest = archive.capture(home, binding, route)
    target = tmp_path / "portable"
    archive.export(home, manifest, target)
    destination = tmp_path / "restored"
    destination.mkdir()
    assert archive.verify_export(target)["exact_bytes"] == len(raw)
    (target / "unlisted-evidence").write_bytes(b"synthetic unexpected member")
    with pytest.raises(ValueError, match="unlisted|member"):
        archive.restore_export(destination, target)
    assert list(destination.iterdir()) == []


@pytest.mark.parametrize(
    "fault",
    [
        "attachments-add",
        "attachments-replace",
        "root-replace",
        "body-change",
        "manifest-alias",
    ],
)
def test_all_export_member_directories_are_revalidated_at_final_read(
    tmp_path, monkeypatch, fault
):
    import os
    import hashlib

    archive, source, binding, route, home, raw = fixture(tmp_path)
    attachment = tmp_path / "attachment"
    attachment.write_bytes(b"attachment")
    route["attachments"] = [
        {
            "id": "one",
            "privacy_domain": route["privacy_domain"],
            "status": "capture",
            "path": str(attachment),
            "bytes": 10,
            "sha256": hashlib.sha256(b"attachment").hexdigest(),
        }
    ]
    manifest = archive.capture(home, binding, route)
    target = tmp_path / "portable"
    archive.export(home, manifest, target)
    original = archive.storage.read_regular
    reads = 0

    def changed(path, *args, **kwargs):
        nonlocal reads
        data = original(path, *args, **kwargs)
        if Path(path) == target / "manifest.json":
            reads += 1
            if reads == 2:
                if fault == "attachments-add":
                    (target / "attachments" / "unlisted").write_bytes(b"x")
                elif fault == "attachments-replace":
                    (target / "attachments").rename(tmp_path / "moved-attachments")
                    (target / "attachments").symlink_to(
                        tmp_path / "moved-attachments", target_is_directory=True
                    )
                elif fault == "root-replace":
                    target.rename(tmp_path / "moved-root")
                    target.symlink_to(tmp_path / "moved-root", target_is_directory=True)
                elif fault == "body-change":
                    (target / "native.jsonl").write_bytes(b"changed after its read")
                elif fault == "manifest-alias":
                    os.link(target / "manifest.json", tmp_path / "manifest-link")
        return data

    monkeypatch.setattr(archive.storage, "read_regular", changed)
    with pytest.raises((ValueError, OSError)):
        archive.verify_export(target)
    assert reads == 2


def test_restore_final_read_race_refuses_before_materialization(tmp_path, monkeypatch):
    archive, source, binding, route, home, raw = fixture(tmp_path)
    target = tmp_path / "portable"
    archive.export(home, archive.capture(home, binding, route), target)
    destination = tmp_path / "new-store"
    destination.mkdir()
    original = archive.storage.read_regular
    reads = 0
    writes = []

    def changed(path, *args, **kwargs):
        nonlocal reads
        data = original(path, *args, **kwargs)
        if Path(path) == target / "manifest.json":
            reads += 1
            if reads == 6:
                (target / "unlisted-late").write_bytes(b"retained race")
        return data

    monkeypatch.setattr(archive.storage, "read_regular", changed)
    monkeypatch.setattr(
        archive.storage, "materialize", lambda *args: writes.append(args)
    )
    with pytest.raises(ValueError):
        archive.restore_export(destination, target)
    assert reads == 6 and writes == [] and list(destination.iterdir()) == []


def test_full_supported_attachment_inventory_remains_usable(tmp_path):
    import hashlib

    archive, source, binding, route, home, raw = fixture(tmp_path)
    for n in range(archive.MAX_ATTACHMENTS):
        p = tmp_path / f"att-{n}"
        p.write_bytes(b"x")
        route["attachments"].append(
            {
                "id": f"att-{n}",
                "privacy_domain": route["privacy_domain"],
                "status": "capture",
                "path": str(p),
                "bytes": 1,
                "sha256": hashlib.sha256(b"x").hexdigest(),
            }
        )
    manifest = archive.capture(home, binding, route)
    target = tmp_path / "portable"
    archive.export(home, manifest, target)
    assert archive.verify_export(target)["status"] == "PASS"
