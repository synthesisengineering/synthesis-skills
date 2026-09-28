"""Bounded exact one-generation continuation; synthetic bytes, no native run."""

from copy import deepcopy
import hashlib
import pytest
from test_native_archive import fixture


def stream_fixture(tmp_path, *, extra=b"x" * 500000, segment_bytes=131072):
    a, source, binding, route, home, raw = fixture(tmp_path, tail=extra)
    import native_archive_stream as s

    descriptor = s.describe(binding, target_bytes=len(raw), segment_bytes=segment_bytes)
    route = {
        k: v
        for k, v in route.items()
        if k not in {"reviewed_bytes", "reviewed_sha256", "attachments"}
    }
    plan = s.plan(descriptor, route, additional_capacity_bytes=0)
    return s, a, source, binding, home, raw, plan


def test_same_generation_advances_exact_ranges_and_restores_after_source_loss(tmp_path):
    s, a, source, binding, home, raw, plan = stream_fixture(tmp_path)
    retained = {}
    for index in range(len(plan["snapshot"]["segments"])):
        retained[str(index)] = s.capture_segment(home, "original", plan, index)
    assert s.coverage(home, "original", plan, retained)["status"] == "COMPLETE"
    target = tmp_path / "export"
    target.mkdir()
    for index, entry in retained.items():
        s.export_segment(home, "original", plan, entry, target)
    receipt = s.export_manifest(plan, retained, target)
    source.rename(tmp_path / "original-unavailable")
    home.rename(tmp_path / "old-store-unavailable")
    restored = tmp_path / "restored"
    restored.mkdir()
    reloaded = s.restore_bundle(restored, "original", target)
    assert s.coverage(restored, "original", plan, reloaded)["status"] == "COMPLETE"
    assert (
        b"".join(
            s.segment_bytes(restored, "original", plan, e) for e in reloaded.values()
        )
        == raw
    )
    assert receipt["source_required"] is False and receipt["authority_granted"] is False


@pytest.mark.parametrize(
    "fault",
    [
        "gap",
        "overlap",
        "wronghash",
        "wronggeneration",
        "booloffset",
        "excess",
        "unknown",
    ],
)
def test_descriptor_refuses_malformed_ranges(tmp_path, fault):
    s, a, source, binding, home, raw, plan = stream_fixture(tmp_path)
    d = deepcopy(plan["snapshot"])
    if fault == "gap":
        d["segments"][1]["offset"] += 1
    if fault == "overlap":
        d["segments"][1]["offset"] -= 1
    if fault == "wronghash":
        d["segments"][0]["sha256"] = "no"
    if fault == "wronggeneration":
        d["binding"]["generation"] = "wrong"
    if fault == "booloffset":
        d["segments"][0]["offset"] = False
    if fault == "excess":
        d["target_bytes"] = s.MAX_SNAPSHOT_BYTES + 1
    if fault == "unknown":
        d["extra"] = "yes"
    with pytest.raises(ValueError):
        s.validate_plan({**plan, "snapshot": d})


def test_changed_range_refuses_and_keeps_previous_segment(tmp_path):
    s, a, source, binding, home, raw, plan = stream_fixture(tmp_path)
    first = s.capture_segment(home, "original", plan, 0)
    with source.open("r+b") as f:
        f.seek(200000)
        f.write(b"CHANGED")
    with pytest.raises(ValueError):
        s.capture_segment(home, "original", plan, 1)
    assert s.segment_bytes(home, "original", plan, first) == raw[:131072]
    assert s.coverage(home, "original", plan, {"0": first})["status"] == "INCOMPLETE"


def test_append_keeps_the_approved_snapshot_but_does_not_claim_current_eof(tmp_path):
    s, a, source, binding, home, raw, plan = stream_fixture(tmp_path)
    source.write_bytes(raw + b"new bytes beyond approved target")
    retained = {
        str(i): s.capture_segment(home, "original", plan, i)
        for i in range(len(plan["snapshot"]["segments"]))
    }
    report = s.coverage(home, "original", plan, retained)
    assert report["status"] == "COMPLETE" and report["snapshot_bytes"] == len(raw)
    assert report["current_source_eof"] == "NOT_CLAIMED"


def test_completion_checks_bodies_and_whole_digest_not_receipts(tmp_path):
    s, a, source, binding, home, raw, plan = stream_fixture(tmp_path)
    retained = {
        str(i): s.capture_segment(home, "original", plan, i)
        for i in range(len(plan["snapshot"]["segments"]))
    }
    fake = deepcopy(plan)
    fake["snapshot"]["target_sha256"] = "f" * 64
    with pytest.raises(ValueError):
        s.coverage(home, "original", fake, retained)
    p = (
        s.partition(home, "original", plan, 0)
        / "state-blocks/v1"
        / (retained["0"]["chunks"][0]["sha256"] + ".json")
    )
    p.write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        s.coverage(home, "original", plan, retained)


def test_budget_is_finite_exact_and_default_does_not_expand(tmp_path):
    s, a, source, binding, home, raw, plan = stream_fixture(tmp_path)
    assert s.admit_capacity({}, plan) == s.DEFAULT_CAPACITY_BYTES
    invalid = deepcopy(plan)
    invalid["additional_capacity_bytes"] = True
    with pytest.raises(ValueError):
        s.validate_plan(invalid)
    state = {"extensions": {"native_archive_streams": {"x": {"plan": plan}}}}
    monkey = deepcopy(plan)
    monkey["snapshot"]["target_bytes"] = s.DEFAULT_CAPACITY_BYTES
    with pytest.raises(ValueError):
        s.admit_capacity(state, monkey)


@pytest.mark.parametrize("fault", ["missing", "extra", "corrupt", "symlink"])
def test_export_custody_refuses_incomplete_or_changed_bundle(tmp_path, fault):
    s, a, source, binding, home, raw, plan = stream_fixture(tmp_path)
    retained = {
        str(i): s.capture_segment(home, "original", plan, i)
        for i in range(len(plan["snapshot"]["segments"]))
    }
    target = tmp_path / "export"
    target.mkdir()
    for e in retained.values():
        s.export_segment(home, "original", plan, e, target)
    s.export_manifest(plan, retained, target)
    member = target / "segment-000000" / "native.bin"
    if fault == "missing":
        member.rename(target / "missing")
    if fault == "extra":
        (target / "unexpected").write_bytes(b"x")
    if fault == "corrupt":
        member.write_bytes(b"changed")
    if fault == "symlink":
        member.rename(target / "body")
        member.symlink_to(target / "body")
    with pytest.raises((ValueError, OSError)):
        s.verify_bundle(target)


def test_exact_reconstruction_larger_than_687_mib_uses_one_generation(tmp_path):
    import native_archive_stream as s

    a, source, binding, route, home, raw = fixture(tmp_path)
    target_bytes = 700 * 1024**2 + 73
    with source.open("ab") as out:
        chunk = b"bounded-synthetic-native-evidence\n" * (1024 * 8)
        remaining = target_bytes - len(raw)
        while remaining:
            take = min(remaining, len(chunk))
            out.write(chunk[:take])
            remaining -= take
    descriptor = s.describe(binding, target_bytes=target_bytes)
    route = {
        k: v
        for k, v in route.items()
        if k not in {"reviewed_bytes", "reviewed_sha256", "attachments"}
    }
    p = s.plan(
        descriptor,
        route,
        additional_capacity_bytes=target_bytes - s.DEFAULT_CAPACITY_BYTES,
    )
    assert s.admit_capacity({}, p) == target_bytes
    entries = {
        str(i): s.capture_segment(home, "large", p, i, admitted=target_bytes)
        for i in range(len(descriptor["segments"]))
    }
    assert (
        len(entries) > 1
        and s.coverage(home, "large", p, entries)["status"] == "COMPLETE"
    )
    out = tmp_path / "portable"
    out.mkdir()
    for e in entries.values():
        s.export_segment(home, "large", p, e, out)
    s.export_manifest(p, entries, out)
    source.rename(tmp_path / "original-unavailable")
    home.rename(tmp_path / "old-store-unavailable")
    new = tmp_path / "new-store"
    new.mkdir()
    restored = s.restore_bundle(new, "large", out, admitted=target_bytes)
    digest = hashlib.sha256()
    count = 0
    for key in sorted(restored, key=int):
        body = s.segment_bytes(new, "large", p, restored[key])
        digest.update(body)
        count += len(body)
    assert count == target_bytes and digest.hexdigest() == descriptor["target_sha256"]
    assert s.verify_bundle(out)["snapshot_bytes"] == target_bytes


@pytest.mark.parametrize(
    "fault", ["symlink", "hardlink", "truncate", "header", "generation"]
)
def test_source_identity_and_unique_file_guards_remain_active(tmp_path, fault):
    import os

    s, a, source, binding, home, raw, plan = stream_fixture(tmp_path)
    if fault == "symlink":
        source.rename(tmp_path / "real")
        source.symlink_to(tmp_path / "real")
    if fault == "hardlink":
        os.link(source, tmp_path / "alias")
    if fault == "truncate":
        source.write_bytes(raw[:100])
    if fault == "header":
        source.write_bytes(b"X" + raw[1:])
    if fault == "generation":
        plan["snapshot"]["binding"]["generation"] = "changed"
    with pytest.raises((ValueError, OSError)):
        s.capture_segment(home, "original", plan, 0)
    assert not (home / "native-archive-streams").exists()


@pytest.mark.parametrize("fault", ["line_ordinal", "boundary"])
def test_whole_verification_refuses_fictional_framing_even_with_correct_raw_hash(
    tmp_path, fault
):
    s, a, source, binding, home, raw, plan = stream_fixture(tmp_path)
    if fault == "line_ordinal":
        plan["snapshot"]["segments"][1]["line_ordinal"] += 1
    else:
        plan["snapshot"]["segments"][1]["starts_at_line"] = not plan["snapshot"][
            "segments"
        ][1]["starts_at_line"]
    with pytest.raises(ValueError):
        entries = {
            str(i): s.capture_segment(home, "original", plan, i)
            for i in range(len(plan["snapshot"]["segments"]))
        }
        s.coverage(home, "original", plan, entries)


def test_retained_orphans_count_before_another_write(tmp_path, monkeypatch):
    s, a, source, binding, home, raw, plan = stream_fixture(tmp_path)
    root = home / "native-archive-streams" / "prior"
    root.mkdir(parents=True)
    (root / "orphan").write_bytes(b"o" * 1024)
    with pytest.raises(ValueError):
        s.capture_segment(home, "original", plan, 0, admitted=1)
    assert (root / "orphan").read_bytes() == b"o" * 1024
    assert not s.partition(home, "original", plan, 0).exists()


def test_manifest_alias_and_final_marker_interruption_are_never_complete(
    tmp_path, monkeypatch
):
    import os

    s, a, source, binding, home, raw, plan = stream_fixture(tmp_path)
    entries = {
        str(i): s.capture_segment(home, "original", plan, i)
        for i in range(len(plan["snapshot"]["segments"]))
    }
    target = tmp_path / "portable"
    target.mkdir()
    for e in entries.values():
        s.export_segment(home, "original", plan, e, target)
    manifest = target / "segment-000000" / "manifest.json"
    os.link(manifest, tmp_path / "manifest-alias")
    with pytest.raises(ValueError):
        s.export_manifest(plan, entries, target)
    assert not (target / "manifest.json").exists()


def test_explicit_deadlines_refuse_without_inferred_completion(tmp_path, monkeypatch):
    s, a, source, binding, home, raw, plan = stream_fixture(tmp_path)
    ticks = iter([0, 121])
    monkeypatch.setattr(s.time, "monotonic", lambda: next(ticks))
    with pytest.raises(ValueError, match="deadline"):
        s.describe(binding, target_bytes=len(raw))
    assert not (home / "native-archive-streams").exists()


def test_segment_view_offsets_ordinals_and_opaque_records_are_exact(tmp_path):
    import json

    s, a, source, binding, home, raw, plan = stream_fixture(tmp_path, extra=b"")
    rows = []
    for n in range(1500):
        rows.append(
            json.dumps(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": "message " + str(n)}
                        ],
                    },
                }
            ).encode()
            + b"\n"
        )
    source.write_bytes(raw + b"".join(rows))
    snapshot = s.describe(
        binding, target_bytes=source.stat().st_size, segment_bytes=65536
    )
    plan = s.plan(snapshot, plan["route"])
    entries = {
        str(i): s.capture_segment(home, "original", plan, i)
        for i in range(len(snapshot["segments"]))
    }
    assert s.coverage(home, "original", plan, entries)["status"] == "COMPLETE"
    for e in entries.values():
        body = s.segment_bytes(home, "original", plan, e)
        view = [json.loads(x) for x in s._portable(body, plan, e["spec"]).splitlines()]
        for row in view:
            assert (
                row["raw_sha256"]
                == hashlib.sha256(
                    source.read_bytes()[row["offset"] : row["offset"] + row["bytes"]]
                ).hexdigest()
            )
            for event in row.get("events", []):
                assert event["native"]["offset"] == row["offset"]
    assert any(not spec["starts_at_line"] for spec in snapshot["segments"][1:])
