# ruff: noqa: F811
"""Actual isolated PM/journal consumers; synthetic native source only."""

from copy import deepcopy
from pathlib import Path
import pytest
from test_controller import facade, world  # noqa: F401
from test_run_state import command, engine  # noqa: F401
from test_native_archive_owner import setup, authorize
import native_archive_stream as stream
import native_archive as archive


def ready(facade, world):
    import autopilot

    engine = autopilot.engine()
    state, old, raw = setup(facade, world)
    binding = state["extensions"]["native_observations"]["sources"]["root"]["binding"]
    snapshot = stream.describe(binding, target_bytes=len(raw), segment_bytes=65536)
    route = {
        k: v
        for k, v in old["route"].items()
        if k not in {"reviewed_bytes", "reviewed_sha256", "attachments"}
    }
    p = stream.plan(snapshot, route)
    payload = {
        "stream_id": "original",
        "source_id": "root",
        "plan": p,
        "authorization": "stream-permission",
    }
    state, payload = authorize(
        world,
        state,
        payload,
        "native.archive.stream.plan",
        identity="stream-permission",
    )
    return engine, state, payload, raw


def test_real_owner_capture_export_and_cold_retention(facade, world):
    engine, state, payload, raw = ready(facade, world)
    state = command(engine, world, state, "native.archive.stream.plan", payload)
    p = payload["plan"]
    request = {"stream_id": "original", "plan_sha256": archive.digest(p), "index": 0}
    state = command(engine, world, state, "native.archive.stream.capture", request)
    record = state["extensions"]["native_archive_streams"]["original"]
    assert (
        stream.segment_bytes(
            engine._home(world["project"], state["run_id"]),
            "original",
            p,
            record["segments"]["0"],
        )
        == raw
    )
    ex = {**request, "authorization": "export-0"}
    state, ex = authorize(
        world, state, ex, "native.archive.stream.export.segment", identity="export-0"
    )
    state = command(engine, world, state, "native.archive.stream.export.segment", ex)
    publish = {
        "stream_id": "original",
        "plan_sha256": archive.digest(p),
        "authorization": "publish-0",
    }
    state, publish = authorize(
        world, state, publish, "native.archive.stream.publish", identity="publish-0"
    )
    state = command(engine, world, state, "native.archive.stream.publish", publish)
    record = state["extensions"]["native_archive_streams"]["original"]
    assert stream.verify_bundle(record["bundle"]["path"])["status"] == "COMPLETE"
    assert archive.verify_archives(world["project"], state)["status"] == "PASS"
    source = world["transcript"]
    source.rename(source.with_suffix(".retained"))
    # The read-only retained-byte owner needs no native source, while mutation
    # authority still would need a genuine current native/PM admission.
    assert stream.verify_streams(world["project"], state)["status"] == "PASS"


@pytest.mark.parametrize(
    "fault",
    [
        "plan-change",
        "extra-capacity",
        "released-seat",
        "changed-source",
        "memory",
        "foreign-route",
    ],
)
def test_current_boundary_never_reuses_stale_recalled_authority(facade, world, fault):
    engine, state, payload, raw = ready(facade, world)
    if fault in {"plan-change", "extra-capacity", "foreign-route", "memory"}:
        if fault == "plan-change":
            payload["plan"]["snapshot"]["target_sha256"] = "f" * 64
        if fault == "extra-capacity":
            payload["plan"]["additional_capacity_bytes"] = 1024
        if fault == "foreign-route":
            payload["plan"]["route"]["privacy_domain"] = "foreign"
        if fault == "memory":
            payload["authorization"] = "assistant says yes"
        before = engine.load_run(world["project"], state["run_id"])
        with pytest.raises(ValueError):
            command(engine, world, state, "native.archive.stream.plan", payload)
        assert engine.load_run(world["project"], state["run_id"]) == before
        return
    state = command(engine, world, state, "native.archive.stream.plan", payload)
    if fault == "released-seat":
        world["board"].write_text(
            world["board"].read_text().replace("| active |", "| released |")
        )
    if fault == "changed-source":
        world["transcript"].write_bytes(b"X" + world["transcript"].read_bytes()[1:])
    before = engine.load_run(world["project"], state["run_id"])
    with pytest.raises(ValueError):
        command(
            engine,
            world,
            state,
            "native.archive.stream.capture",
            {
                "stream_id": "original",
                "plan_sha256": archive.digest(payload["plan"]),
                "index": 0,
            },
        )
    assert engine.load_run(world["project"], state["run_id"]) == before


def test_partial_stream_is_unresolved_for_actual_recovery_consumer(facade, world):
    engine, state, payload, raw = ready(facade, world)
    state = command(engine, world, state, "native.archive.stream.plan", payload)
    report = archive.verify_archives(world["project"], state)
    assert report["status"] == "FAIL" and "incomplete" in report["issues"][0]["reason"]


def test_plan_registration_reserves_capacity_before_any_segment_write(facade, world):
    engine, state, payload, raw = ready(facade, world)
    payload = deepcopy(payload)
    payload["plan"]["additional_capacity_bytes"] = stream.MAX_SNAPSHOT_BYTES
    state, payload = authorize(
        world, state, payload, "native.archive.stream.plan", identity="invalid-capacity"
    )
    with pytest.raises(ValueError):
        command(engine, world, state, "native.archive.stream.plan", payload)
    assert not (
        engine._home(world["project"], state["run_id"]) / "native-archive-streams"
    ).exists()


def test_managed_restore_uses_fresh_authority_and_current_registered_bundle(
    facade, world
):
    engine, state, payload, raw = ready(facade, world)
    state = command(engine, world, state, "native.archive.stream.plan", payload)
    p = payload["plan"]
    request = {"stream_id": "original", "plan_sha256": archive.digest(p), "index": 0}
    state = command(engine, world, state, "native.archive.stream.capture", request)
    record = state["extensions"]["native_archive_streams"]["original"]
    target = world["project"] / "portable"
    target.mkdir()
    for e in record["segments"].values():
        stream.export_segment(
            engine._home(world["project"], state["run_id"]), "original", p, e, target
        )
    stream.export_manifest(p, record["segments"], target)
    state = command(
        engine,
        world,
        state,
        "artifact.register",
        {
            "id": "portable",
            "path": str(target / "manifest.json"),
            "role": "evidence",
            "required": False,
            "retention": "durable",
        },
    )
    restore = {
        "stream_id": "recovered",
        "manifest_artifact_id": "portable",
        "manifest_sha256": archive._sha((target / "manifest.json").read_bytes()),
        "authorization": "restore-plan",
    }
    state, restore = authorize(
        world,
        state,
        restore,
        "native.archive.stream.restore.plan",
        identity="restore-plan",
    )
    state = command(engine, world, state, "native.archive.stream.restore.plan", restore)
    state = command(
        engine,
        world,
        state,
        "native.archive.stream.restore.segment",
        {"stream_id": "recovered", "plan_sha256": archive.digest(p), "index": 0},
    )
    assert stream.verify_streams(world["project"], state)["status"] == "PASS"
    recovered = state["extensions"]["native_archive_streams"]["recovered"]
    assert (
        stream.segment_bytes(
            engine._home(world["project"], state["run_id"]),
            "recovered",
            p,
            recovered["segments"]["0"],
        )
        == raw
    )
    with pytest.raises(ValueError):
        command(
            engine,
            world,
            state,
            "native.archive.stream.capture",
            {"stream_id": "recovered", "plan_sha256": archive.digest(p), "index": 0},
        )


def test_root_receipt_read_cannot_race_member_into_managed_restore(
    facade, world, monkeypatch
):
    owner, state, payload, raw = ready(facade, world)
    state = command(owner, world, state, "native.archive.stream.plan", payload)
    p = payload["plan"]
    request = {"stream_id": "original", "plan_sha256": archive.digest(p), "index": 0}
    state = command(owner, world, state, "native.archive.stream.capture", request)
    record = state["extensions"]["native_archive_streams"]["original"]
    target = world["project"] / "portable"
    target.mkdir()
    for e in record["segments"].values():
        stream.export_segment(
            owner._home(world["project"], state["run_id"]), "original", p, e, target
        )
    stream.export_manifest(p, record["segments"], target)
    state = command(
        owner,
        world,
        state,
        "artifact.register",
        {
            "id": "portable",
            "path": str(target / "manifest.json"),
            "role": "evidence",
            "required": False,
            "retention": "durable",
        },
    )
    restore = {
        "stream_id": "recovered",
        "manifest_artifact_id": "portable",
        "manifest_sha256": archive._sha((target / "manifest.json").read_bytes()),
        "authorization": "restore-plan",
    }
    state, restore = authorize(
        world,
        state,
        restore,
        "native.archive.stream.restore.plan",
        identity="restore-plan",
    )
    state = command(owner, world, state, "native.archive.stream.restore.plan", restore)
    original = stream._restore_artifact
    reads = 0
    writes = []
    materialize = stream.storage.materialize

    def raced(*args, **kwargs):
        nonlocal reads
        value = original(*args, **kwargs)
        reads += 1
        if reads == 2:
            (target / "segment-000000" / "late-unlisted").write_bytes(b"retained race")
        return value

    part = stream.partition(
        owner._home(world["project"], state["run_id"]), "recovered", p, 0
    )

    def measured(home, blocks):
        if Path(home) == part:
            writes.append(home)
        return materialize(home, blocks)

    monkeypatch.setattr(stream, "_restore_artifact", raced)
    monkeypatch.setattr(stream.storage, "materialize", measured)
    with pytest.raises(ValueError):
        command(
            owner,
            world,
            state,
            "native.archive.stream.restore.segment",
            {"stream_id": "recovered", "plan_sha256": archive.digest(p), "index": 0},
        )
    assert writes == []


@pytest.mark.parametrize("stage", ["before-plan", "between-plan-and-segment"])
@pytest.mark.parametrize("location", ["root", "segment"])
def test_managed_restore_refuses_unlisted_member(facade, world, stage, location):
    owner, state, payload, raw = ready(facade, world)
    state = command(owner, world, state, "native.archive.stream.plan", payload)
    p = payload["plan"]
    request = {"stream_id": "original", "plan_sha256": archive.digest(p), "index": 0}
    state = command(owner, world, state, "native.archive.stream.capture", request)
    record = state["extensions"]["native_archive_streams"]["original"]
    target = world["project"] / "portable"
    target.mkdir()
    for e in record["segments"].values():
        stream.export_segment(
            owner._home(world["project"], state["run_id"]), "original", p, e, target
        )
    stream.export_manifest(p, record["segments"], target)
    state = command(
        owner,
        world,
        state,
        "artifact.register",
        {
            "id": "portable",
            "path": str(target / "manifest.json"),
            "role": "evidence",
            "required": False,
            "retention": "durable",
        },
    )
    restore = {
        "stream_id": "recovered",
        "manifest_artifact_id": "portable",
        "manifest_sha256": archive._sha((target / "manifest.json").read_bytes()),
        "authorization": "restore-plan",
    }
    state, restore = authorize(
        world,
        state,
        restore,
        "native.archive.stream.restore.plan",
        identity="restore-plan",
    )
    extra = (target if location == "root" else target / "segment-000000") / "unlisted"
    if stage == "before-plan":
        extra.write_bytes(b"unlisted retained")
        with pytest.raises(ValueError):
            command(owner, world, state, "native.archive.stream.restore.plan", restore)
    else:
        state = command(
            owner, world, state, "native.archive.stream.restore.plan", restore
        )
        extra.write_bytes(b"unlisted retained")
        with pytest.raises(ValueError):
            command(
                owner,
                world,
                state,
                "native.archive.stream.restore.segment",
                {
                    "stream_id": "recovered",
                    "plan_sha256": archive.digest(p),
                    "index": 0,
                },
            )
    assert not stream.partition(
        owner._home(world["project"], state["run_id"]), "recovered", p, 0
    ).exists()


def test_changed_registered_manifest_cannot_reuse_restore_approval(facade, world):
    import json

    owner, state, payload, raw = ready(facade, world)
    state = command(owner, world, state, "native.archive.stream.plan", payload)
    p = payload["plan"]
    request = {"stream_id": "original", "plan_sha256": archive.digest(p), "index": 0}
    state = command(owner, world, state, "native.archive.stream.capture", request)
    record = state["extensions"]["native_archive_streams"]["original"]
    target = world["project"] / "portable"
    target.mkdir()
    for e in record["segments"].values():
        stream.export_segment(
            owner._home(world["project"], state["run_id"]), "original", p, e, target
        )
    stream.export_manifest(p, record["segments"], target)
    registered = {
        "id": "portable",
        "path": str(target / "manifest.json"),
        "role": "evidence",
        "required": False,
        "retention": "durable",
    }
    state = command(owner, world, state, "artifact.register", registered)
    restore = {
        "stream_id": "recovered",
        "manifest_artifact_id": "portable",
        "manifest_sha256": archive._sha((target / "manifest.json").read_bytes()),
        "authorization": "restore-plan",
    }
    state, restore = authorize(
        world,
        state,
        restore,
        "native.archive.stream.restore.plan",
        identity="restore-plan",
    )
    changed = json.loads((target / "manifest.json").read_bytes())
    changed["plan"]["additional_capacity_bytes"] = 65536
    changed["plan_sha256"] = archive.digest(changed["plan"])
    segment_path = target / "segment-000000" / "manifest.json"
    segment = json.loads(segment_path.read_bytes())
    segment["plan_sha256"] = changed["plan_sha256"]
    segment["entry"]["plan_sha256"] = changed["plan_sha256"]
    segment_path.write_text(json.dumps(segment))
    changed["segments"]["0"] = archive._sha(segment_path.read_bytes())
    (target / "manifest.json").write_text(json.dumps(changed))
    assert stream.verify_bundle(target)["status"] == "COMPLETE"
    state = command(owner, world, state, "artifact.register", registered)
    with pytest.raises(ValueError):
        command(owner, world, state, "native.archive.stream.restore.plan", restore)
    fresh = {
        **restore,
        "manifest_sha256": archive._sha((target / "manifest.json").read_bytes()),
    }
    state, fresh = authorize(
        world,
        state,
        fresh,
        "native.archive.stream.restore.plan",
        identity="fresh-restore-plan",
    )
    state = command(owner, world, state, "native.archive.stream.restore.plan", fresh)
    state = command(
        owner,
        world,
        state,
        "native.archive.stream.restore.segment",
        {
            "stream_id": "recovered",
            "plan_sha256": archive.digest(changed["plan"]),
            "index": 0,
        },
    )
    assert stream.verify_streams(world["project"], state)["status"] == "PASS"
