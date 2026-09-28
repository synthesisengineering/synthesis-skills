"""Lossless synthetic evidence; no real transcript export or native acceptance."""

import hashlib
import json
from pathlib import Path
import pytest
import native_observations as no


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def wire(row):
    return json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"


def fixture(tmp_path, rows=None, tail=b""):
    import native_archive as archive

    raw = wire(
        {
            "type": "session_meta",
            "payload": {"id": "root", "session_id": "root", "agent_path": None},
        }
    )
    raw += b"".join(wire(r) for r in (rows or [])) + tail
    source = tmp_path / "source.jsonl"
    source.write_bytes(raw)
    binding, _ = no.enroll_source(
        source, client="codex", expected_root_session_id="root"
    )
    route = {
        "schema_version": 1,
        "project_id": "alpha",
        "privacy_domain": "personal-alpha",
        "retention_class": "permanent",
        "classification": "single-domain-reviewed",
        "source_domains": ["personal-alpha"],
        "source_generation": binding["generation"],
        "reviewed_bytes": len(raw),
        "reviewed_sha256": sha(raw),
        "attachments": [],
    }
    home = tmp_path / "journal"
    home.mkdir()
    return archive, source, binding, route, home, raw


def test_archive_recovers_exact_bytes_without_source_and_keeps_opaque(tmp_path):
    rows = [
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "héllo\nworld"}],
            },
        },
        {
            "type": "response_item",
            "payload": {"type": "reasoning", "encrypted_content": "opaque-value"},
        },
        {"type": "future.record", "arbitrary": {"anything": [1, 2]}},
    ]
    a, source, binding, route, home, raw = fixture(tmp_path, rows, b'{"unfinished":')
    manifest = a.capture(home, binding, route)
    assert a.recover_bytes(home, manifest) == raw
    assert manifest["complete_prefix_bytes"] == raw.rfind(b"\n") + 1
    assert manifest["partial_tail_bytes"] == len(b'{"unfinished":')
    source.rename(tmp_path / "unavailable-original")
    target = tmp_path / "portable"
    result = a.export(home, manifest, target)
    assert (target / "native.jsonl").read_bytes() == raw
    report = a.verify_export(target)
    assert report["exact_bytes"] == len(raw) and report["authority_granted"] is False
    view = [
        json.loads(line)
        for line in (target / "portable.jsonl").read_bytes().splitlines()
    ]
    assert len(view) == 5 and view[-1]["status"] == "partial-tail"
    assert view[2]["status"] == "opaque" and view[3]["status"] == "unknown"
    assert view[1]["record"] == rows[0]
    assert result["manifest_sha256"] == sha((target / "manifest.json").read_bytes())


def test_incremental_archive_preserves_prior_prefix_and_reuses_blocks(tmp_path):
    a, source, binding, route, home, raw = fixture(
        tmp_path, [{"type": "unknown", "x": "x" * 200000}]
    )
    first = a.capture(home, binding, route)
    extra = wire({"type": "future", "x": "new"})
    source.write_bytes(raw + extra)
    next_route = {
        **route,
        "reviewed_bytes": len(raw + extra),
        "reviewed_sha256": sha(raw + extra),
    }
    second = a.capture(home, binding, next_route, previous=first)
    assert (
        a.recover_bytes(home, first) == raw
        and a.recover_bytes(home, second) == raw + extra
    )
    assert second["previous_manifest_sha256"] == a.digest(first)
    assert first["chunks"][:-1] == second["chunks"][: len(first["chunks"]) - 1]
    source.write_bytes(b"X" + (raw + extra)[1:])
    with pytest.raises(ValueError):
        a.capture(home, binding, next_route, previous=second)
    assert a.recover_bytes(home, second) == raw + extra


@pytest.mark.parametrize(
    "fault",
    [
        "mixed",
        "unknown",
        "wronghash",
        "wronggeneration",
        "badlength",
        "boollength",
        "foreignattachment",
        "symlink",
        "hardlink",
        "truncated",
    ],
)
def test_route_and_source_refuse_before_any_archive_write(tmp_path, fault):
    a, source, binding, route, home, raw = fixture(tmp_path)
    if fault == "mixed":
        route["source_domains"].append("engagement-other")
    elif fault == "unknown":
        route["classification"] = "unknown"
    elif fault == "wronghash":
        route["reviewed_sha256"] = "0" * 64
    elif fault == "wronggeneration":
        route["source_generation"] = "0" * 64
    elif fault == "badlength":
        route["reviewed_bytes"] = a.MAX_SOURCE_BYTES + 1
    elif fault == "boollength":
        route["reviewed_bytes"] = True
    elif fault == "foreignattachment":
        route["attachments"] = [
            {"id": "x", "privacy_domain": "other", "status": "not-provided"}
        ]
    elif fault == "symlink":
        source.rename(tmp_path / "other")
        source.symlink_to(tmp_path / "other")
    elif fault == "hardlink":
        (tmp_path / "alias").hardlink_to(source)
    elif fault == "truncated":
        source.write_bytes(raw[:-1])
    with pytest.raises((ValueError, OSError)):
        a.capture(home, binding, route)
    assert list(home.iterdir()) == []


def test_archive_preserves_malformed_records_and_attachment_coverage(tmp_path):
    a, source, binding, route, home, raw = fixture(tmp_path)
    raw += b"{bad JSON}\n" + wire(
        {"type": "unknown", "attachment": {"path": "missing"}}
    )
    source.write_bytes(raw)
    item = tmp_path / "image.bin"
    item.write_bytes(b"\x00\xffsynthetic")
    route.update(
        reviewed_bytes=len(raw),
        reviewed_sha256=sha(raw),
        attachments=[
            {
                "id": "image",
                "privacy_domain": "personal-alpha",
                "status": "capture",
                "path": str(item),
                "bytes": item.stat().st_size,
                "sha256": sha(item.read_bytes()),
            },
            {
                "id": "missing",
                "privacy_domain": "personal-alpha",
                "status": "not-provided",
            },
        ],
    )
    manifest = a.capture(home, binding, route)
    assert a.recover_bytes(home, manifest) == raw
    assert manifest["attachments"][1]["status"] == "not-provided"
    source.unlink()
    item.unlink()
    a.export(home, manifest, tmp_path / "export")
    assert (tmp_path / "export/attachments/image").read_bytes() == b"\x00\xffsynthetic"
    assert a.verify_export(tmp_path / "export")["attachment_discovery"] == "UNKNOWN"
    view = [
        json.loads(line)
        for line in (tmp_path / "export/portable.jsonl").read_bytes().splitlines()
    ]
    assert view[1]["status"] == "malformed" and view[1]["raw_sha256"] == sha(
        b"{bad JSON}\n"
    )


def test_changed_attachment_does_not_publish_anything(tmp_path):
    a, source, binding, route, home, raw = fixture(tmp_path)
    f = tmp_path / "a"
    f.write_bytes(b"changed")
    route["attachments"] = [
        {
            "id": "a",
            "privacy_domain": "personal-alpha",
            "status": "capture",
            "path": str(f),
            "bytes": 7,
            "sha256": "0" * 64,
        }
    ]
    with pytest.raises(ValueError):
        a.capture(home, binding, route)
    assert list(home.iterdir()) == []


def test_corrupt_missing_or_extra_export_never_verifies(tmp_path):
    a, source, binding, route, home, raw = fixture(tmp_path)
    manifest = a.capture(home, binding, route)
    for fault in ("corrupt", "missing", "extra", "symlink"):
        target = tmp_path / fault
        a.export(home, manifest, target)
        f = target / "native.jsonl"
        if fault == "corrupt":
            f.write_bytes(b"X" + raw[1:])
        elif fault == "missing":
            f.unlink()
        elif fault == "extra":
            (target / "unlisted").write_bytes(b"x")
        else:
            f.unlink()
            f.symlink_to(source)
        with pytest.raises((ValueError, OSError)):
            a.verify_export(target)


def test_export_never_overwrites_and_corrupt_cas_preserves_prior_evidence(tmp_path):
    a, source, binding, route, home, raw = fixture(tmp_path)
    manifest = a.capture(home, binding, route)
    target = tmp_path / "export"
    target.mkdir()
    (target / "foreign").write_bytes(b"keep")
    with pytest.raises((ValueError, OSError)):
        a.export(home, manifest, target)
    assert (target / "foreign").read_bytes() == b"keep"
    block = home / "state-blocks/v1" / (manifest["chunks"][0]["sha256"] + ".json")
    block.write_bytes(b"changed")
    with pytest.raises(ValueError):
        a.recover_bytes(home, manifest)


def test_source_change_between_full_passes_refuses_before_cas(tmp_path, monkeypatch):
    a, source, binding, route, home, raw = fixture(tmp_path)
    original = a._source_pass
    count = 0

    def altered(*args, **kwargs):
        nonlocal count
        result = original(*args, **kwargs)
        count += 1
        if count == 1:
            source.write_bytes(raw + b"append")
        return result

    monkeypatch.setattr(a, "_source_pass", altered)
    with pytest.raises(ValueError):
        a.capture(home, binding, route)
    assert list(home.iterdir()) == []


def test_export_final_manifest_is_absent_on_interruption(tmp_path, monkeypatch):
    a, source, binding, route, home, raw = fixture(tmp_path)
    manifest = a.capture(home, binding, route)
    original = a._write_new
    calls = 0

    def fault(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic interruption")
        return original(*args, **kwargs)

    monkeypatch.setattr(a, "_write_new", fault)
    target = tmp_path / "export"
    with pytest.raises(OSError):
        a.export(home, manifest, target)
    assert not (target / "manifest.json").exists()
    assert a.recover_bytes(home, manifest) == raw


def test_export_restores_exact_original_bytes_into_new_store_without_source(tmp_path):
    a, source, binding, route, home, raw = fixture(
        tmp_path, [{"type": "unknown", "x": "full material"}]
    )
    manifest = a.capture(home, binding, route)
    target = tmp_path / "export"
    a.export(home, manifest, target)
    source.rename(tmp_path / "source-gone")
    home.rename(tmp_path / "store-gone")
    recovered = tmp_path / "recovered-store"
    recovered.mkdir()
    restored = a.restore_export(recovered, target)
    assert restored == manifest
    assert a.recover_bytes(recovered, restored) == raw
    assert restored["authority_granted"] is False


def test_import_corruption_does_not_create_objects(tmp_path):
    a, source, binding, route, home, raw = fixture(tmp_path)
    manifest = a.capture(home, binding, route)
    target = tmp_path / "export"
    a.export(home, manifest, target)
    (target / "portable.jsonl").write_bytes(b"forged")
    recovered = tmp_path / "recovered"
    recovered.mkdir()
    with pytest.raises(ValueError):
        a.restore_export(recovered, target)
    assert list(recovered.iterdir()) == []


def test_portable_view_preflight_enforces_output_bound_before_cas(
    tmp_path, monkeypatch
):
    a, source, binding, route, home, raw = fixture(
        tmp_path, [{"type": "unknown", "text": "x" * 4096}]
    )
    monkeypatch.setattr(a, "MAX_EXPORT_BYTES", len(raw))
    with pytest.raises(ValueError, match="portable|export"):
        a.capture(home, binding, route)
    assert list(home.iterdir()) == []


def test_export_rejects_boolean_schema_and_bad_codec_digest(tmp_path):
    a, source, binding, route, home, raw = fixture(tmp_path)
    manifest = a.capture(home, binding, route)
    for index, field, value in [
        (0, "schema_version", True),
        (1, "codec_at_export", "unbound"),
    ]:
        target = tmp_path / str(index)
        a.export(home, manifest, target)
        envelope = json.loads((target / "manifest.json").read_bytes())
        envelope[field] = value
        (target / "manifest.json").write_text(json.dumps(envelope))
        with pytest.raises(ValueError):
            a.verify_export(target)


def test_source_ancestor_replacement_is_not_same_directory_proof(tmp_path, monkeypatch):
    a, source, binding, route, home, raw = fixture(tmp_path)
    parent = tmp_path / "ancestor"
    parent.mkdir()
    inside = parent / "inside"
    inside.mkdir()
    path = inside / "source.jsonl"
    path.write_bytes(raw)
    original = a.storage._same_directory
    switched = False

    def swap_then_check(directory, fd):
        nonlocal switched
        if Path(directory) == inside and not switched:
            switched = True
            parent.rename(tmp_path / "retained-ancestor")
            parent.symlink_to(tmp_path / "retained-ancestor", target_is_directory=True)
        return original(directory, fd)

    monkeypatch.setattr(a.storage, "_same_directory", swap_then_check)
    with pytest.raises((ValueError, OSError)):
        a._source_pass(path, len(raw))
    assert (tmp_path / "retained-ancestor/inside/source.jsonl").read_bytes() == raw


def test_large_and_structurally_bad_records_remain_exact(tmp_path):
    a, source, binding, route, home, raw = fixture(tmp_path)
    frames = [
        wire({"type": "response_item", "payload": None}),
        wire({"type": "response_item", "payload": []}),
        b'{"duplicate":1,"duplicate":2}\n',
        b"\xff\n",
        wire({"type": "unknown", "text": "x" * (a.INLINE_RECORD_BYTES + 1)}),
    ]
    raw += b"".join(frames)
    source.write_bytes(raw)
    route.update(reviewed_bytes=len(raw), reviewed_sha256=sha(raw))
    manifest = a.capture(home, binding, route)
    view = list(a.portable_rows(raw, manifest))
    assert a.recover_bytes(home, manifest) == raw
    assert len(view) == 6 and view[-1]["status"] == "external-body"
    assert view[-2]["status"] == "malformed" and view[-3]["status"] == "malformed"
    assert all(
        row["raw_sha256"] == sha(raw[row["offset"] : row["offset"] + row["bytes"]])
        for row in view
    )


def test_export_binds_current_normalizer_separately_from_capture(tmp_path, monkeypatch):
    archive, source, binding, route, home, raw = fixture(tmp_path)
    manifest = archive.capture(home, binding, route)
    before = manifest["normalizer_sha256"]
    monkeypatch.setattr(archive.native, "ADAPTER_SHA256", "b" * 64)
    target = tmp_path / "export"
    archive.export(home, manifest, target)
    envelope = json.loads((target / "manifest.json").read_bytes())
    assert envelope["archive"]["normalizer_sha256"] == before
    assert envelope["normalizer_at_export"] == "b" * 64
    assert archive.verify_export(target)["authority_granted"] is False
