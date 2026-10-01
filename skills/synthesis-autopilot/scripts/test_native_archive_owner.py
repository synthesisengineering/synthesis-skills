# ruff: noqa: F811
# Pytest fixture imports are deliberately reused as injected argument names.
"""Real isolated PM, journal and file consumers; native inputs are fixtures."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import pytest
from test_controller import facade, world, invoke, start_request, state_of  # noqa: F401
from test_run_state import command, engine  # noqa: F401
from test_evidence_bridge import record
import native_archive as archive


def authorize(world, state, payload, action, *, role="user", identity="authorization"):
    import autopilot

    engine = autopilot.engine()
    data = {
        "approved": True,
        "action": action,
        "request_sha256": archive.digest(
            {k: v for k, v in payload.items() if k != "authorization"}
        ),
    }
    envelope = {
        "autopilot_authorization": {
            "schema_version": 1,
            "kind": "authority",
            "bindings": {
                k: state[k] for k in ("run_id", "contract_digest", "profile_digest")
            },
            "data": data,
        }
    }
    event = {
        "type": role,
        "uuid": identity,
        "sessionId": world["actor"]["native_payload"]["session_id"],
        "message": {"role": role, "content": json.dumps(envelope)},
    }
    with world["transcript"].open("a") as stream:
        stream.write(json.dumps(event) + "\n")
    context = engine.inspect_context(state, world["actor"], project=world["project"])
    receipt = record(
        "authority",
        {**data, "source": {"kind": "native-user", "message_id": identity}},
        {**context, "state": state, "now": datetime.now(timezone.utc).isoformat()},
    )
    path = world["project"] / (identity + ".json")
    path.write_text(json.dumps(receipt))
    state = command(
        engine,
        world,
        state,
        "artifact.register",
        {
            "id": identity,
            "path": str(path),
            "role": "evidence",
            "required": False,
            "retention": "durable",
        },
    )
    state = command(
        engine,
        world,
        state,
        "evidence.record",
        {"id": identity, "kind": "authority", "artifact_id": identity},
    )
    return state, {**payload, "authorization": identity}


def setup(facade, world):
    state = state_of(world, invoke(facade, world, start_request(world)))
    binding = state["extensions"]["native_observations"]["sources"]["root"]["binding"]
    raw = world["transcript"].read_bytes()
    route = {
        "schema_version": 1,
        "project_id": "alpha",
        "privacy_domain": "personal-alpha",
        "retention_class": "permanent",
        "classification": "single-domain-reviewed",
        "source_domains": ["personal-alpha"],
        "source_generation": binding["generation"],
        "reviewed_bytes": len(raw),
        "reviewed_sha256": hashlib.sha256(raw).hexdigest(),
        "attachments": [],
    }
    return (
        state,
        {
            "archive_id": "original",
            "source_id": "root",
            "route": route,
            "authorization": "approval",
        },
        raw,
    )


def test_real_managed_capture_and_export_need_fresh_exact_authority(facade, world):
    import autopilot

    engine = autopilot.engine()
    state, payload, raw = setup(facade, world)
    with pytest.raises(ValueError):
        command(engine, world, state, "native.archive.capture", payload)
    state, payload = authorize(world, state, payload, "native.archive.capture")
    result = command(engine, world, state, "native.archive.capture", payload)
    entry = result["extensions"]["native_archives"]["original"]
    assert (
        entry["authority_granted"] is False
        and entry["manifest"]["captured_mode"] == "synthetic"
    )
    assert (
        archive.recover_bytes(
            engine._home(world["project"], state["run_id"]), entry["manifest"]
        )
        == raw
    )
    export = {
        "archive_id": "original",
        "manifest_sha256": entry["manifest_sha256"],
        "authorization": "export",
    }
    result, export = authorize(
        world, result, export, "native.archive.export", identity="export-authorization"
    )
    exported = command(engine, world, result, "native.archive.export", export)
    path = exported["extensions"]["native_archives"]["original"]["export"]["path"]
    assert archive.verify_export(path)["source_required"] is False
    from pathlib import Path

    assert (Path(path) / "native.jsonl").read_bytes() == raw
    again = command(engine, world, result, "native.archive.export", export)
    assert again == exported


@pytest.mark.parametrize(
    "fault",
    [
        "assistant-memory",
        "tool-memory",
        "changed-project",
        "changed-route",
        "released-seat",
        "changed-registry",
        "changed-source",
        "extra-field",
    ],
)
def test_recalled_archive_authority_never_crosses_actual_boundary(facade, world, fault):
    import autopilot

    engine = autopilot.engine()
    state, payload, raw = setup(facade, world)
    role = {"assistant-memory": "assistant", "tool-memory": "tool"}.get(fault, "user")
    state, payload = authorize(
        world, state, payload, "native.archive.capture", role=role
    )
    if fault == "changed-project":
        payload["route"]["project_id"] = "foreign"
    elif fault == "changed-route":
        payload["route"]["privacy_domain"] = "foreign"
    elif fault == "released-seat":
        world["board"].write_text(
            world["board"].read_text().replace("| active |", "| released |")
        )
    elif fault == "changed-registry":
        (world["repo"] / "projects/index.yaml").write_text(
            "- id: other\n  status: active\n"
        )
    elif fault == "changed-source":
        world["transcript"].write_bytes(
            world["transcript"]
            .read_bytes()
            .replace(b'"type": "user"', b'"type": "none"', 1)
        )
    elif fault == "extra-field":
        payload["memory_says_approved"] = True
    before = engine.load_run(world["project"], state["run_id"])
    with pytest.raises(ValueError):
        command(engine, world, state, "native.archive.capture", payload)
    assert engine.load_run(world["project"], state["run_id"]) == before
    assert not before["extensions"].get("native_archives")


def test_managed_restore_never_restores_old_owner_or_permissions(facade, world):
    import autopilot
    from pathlib import Path

    engine = autopilot.engine()
    state, payload, raw = setup(facade, world)
    state, payload = authorize(world, state, payload, "native.archive.capture")
    state = command(engine, world, state, "native.archive.capture", payload)
    manifest = state["extensions"]["native_archives"]["original"]["manifest"]
    target = world["project"] / "portable-input"
    archive.export(engine._home(world["project"], state["run_id"]), manifest, target)
    state = command(
        engine,
        world,
        state,
        "artifact.register",
        {
            "id": "export-input",
            "path": str(target / "manifest.json"),
            "role": "input",
            "retention": "durable",
            "required": False,
        },
    )
    req = {
        "archive_id": "restored",
        "manifest_artifact_id": "export-input",
        "manifest_sha256": archive._sha((target / "manifest.json").read_bytes()),
        "authorization": "restore",
    }
    state, req = authorize(
        world, state, req, "native.archive.restore", identity="restore-authorization"
    )
    before = deepcopy(state)
    result = command(engine, world, state, "native.archive.restore", req)
    for key in ("owner", "contract", "profile", "effects", "handoff"):
        assert result.get(key) == before.get(key)
    restored = result["extensions"]["native_archives"]["restored"]
    assert restored["manifest"] == manifest and restored["authority_granted"] is False
    assert (Path(target) / "native.jsonl").read_bytes() == raw


def test_missing_archive_blocks_remain_recovery_obligations(facade, world):
    import autopilot

    engine = autopilot.engine()
    state, payload, raw = setup(facade, world)
    state, payload = authorize(world, state, payload, "native.archive.capture")
    state = command(engine, world, state, "native.archive.capture", payload)
    entry = state["extensions"]["native_archives"]["original"]
    block = (
        engine._home(world["project"], state["run_id"])
        / "state-blocks/v1"
        / (entry["manifest"]["chunks"][0]["sha256"] + ".json")
    )
    block.rename(block.with_suffix(".retained-corruption-fixture"))
    recovered = command(engine, world, state, "recovery.admit", {"capsule_ref": None})
    report = recovered["extensions"]["recovery"]["report"]
    assert report["status"] == "reconcile"
    assert any(
        x["kind"] == "artifact_reconciliation" and x.get("archive_id") == "original"
        for x in report["pending"]
    )
    with pytest.raises(ValueError, match="recovery"):
        command(
            engine,
            world,
            recovered,
            "effect.prepare",
            {
                "id": "publication",
                "target": "file:output",
                "payload_digest": "a" * 64,
                "idempotency_key": "once",
                "authority_ref": "",
            },
        )


def test_managed_restore_enforces_aggregate_capacity_before_copy(
    facade, world, monkeypatch
):
    import autopilot

    engine = autopilot.engine()
    state, payload, raw = setup(facade, world)
    state, payload = authorize(world, state, payload, "native.archive.capture")
    state = command(engine, world, state, "native.archive.capture", payload)
    manifest = state["extensions"]["native_archives"]["original"]["manifest"]
    target = world["project"] / "portable-input"
    archive.export(engine._home(world["project"], state["run_id"]), manifest, target)
    state = command(
        engine,
        world,
        state,
        "artifact.register",
        {
            "id": "export-input",
            "path": str(target / "manifest.json"),
            "role": "input",
            "retention": "durable",
            "required": False,
        },
    )
    req = {
        "archive_id": "restored",
        "manifest_artifact_id": "export-input",
        "manifest_sha256": archive._sha((target / "manifest.json").read_bytes()),
        "authorization": "restore",
    }
    state, req = authorize(
        world, state, req, "native.archive.restore", identity="restore-authorization"
    )
    monkeypatch.setattr(archive, "MAX_ARCHIVE_BYTES", len(raw), raising=False)
    before = deepcopy(state)
    with pytest.raises(ValueError, match="aggregate"):
        command(engine, world, state, "native.archive.restore", req)
    assert engine.load_run(world["project"], state["run_id"]) == before


def test_changed_prefix_manifest_cannot_reuse_restore_approval(facade, world):
    import autopilot

    owner = autopilot.engine()
    state, payload, raw = setup(facade, world)
    state, payload = authorize(world, state, payload, "native.archive.capture")
    state = command(owner, world, state, "native.archive.capture", payload)
    manifest = state["extensions"]["native_archives"]["original"]["manifest"]
    target = world["project"] / "portable"
    archive.export(owner._home(world["project"], state["run_id"]), manifest, target)
    registered = {
        "id": "portable",
        "path": str(target / "manifest.json"),
        "role": "evidence",
        "required": False,
        "retention": "durable",
    }
    state = command(owner, world, state, "artifact.register", registered)
    restore = {
        "archive_id": "recovered",
        "manifest_artifact_id": "portable",
        "manifest_sha256": archive._sha((target / "manifest.json").read_bytes()),
        "authorization": "restore-plan",
    }
    state, restore = authorize(
        world, state, restore, "native.archive.restore", identity="restore-plan"
    )
    changed = json.loads((target / "manifest.json").read_bytes())
    changed["codec_at_export"] = "0" * 64
    (target / "manifest.json").write_text(json.dumps(changed))
    assert archive.verify_export(target)["status"] == "PASS"
    state = command(owner, world, state, "artifact.register", registered)
    with pytest.raises(ValueError):
        command(owner, world, state, "native.archive.restore", restore)
    fresh = {
        **restore,
        "manifest_sha256": archive._sha((target / "manifest.json").read_bytes()),
    }
    state, fresh = authorize(
        world, state, fresh, "native.archive.restore", identity="fresh-restore"
    )
    state = command(owner, world, state, "native.archive.restore", fresh)
    assert state["extensions"]["native_archives"]["recovered"]["manifest"] == manifest
    assert archive.verify_archives(world["project"], state)["status"] == "PASS"


def test_prefix_authorized_manifest_cannot_change_at_restore_boundary(
    facade, world, monkeypatch
):
    import autopilot

    owner = autopilot.engine()
    state, payload, raw = setup(facade, world)
    state, payload = authorize(world, state, payload, "native.archive.capture")
    state = command(owner, world, state, "native.archive.capture", payload)
    manifest = state["extensions"]["native_archives"]["original"]["manifest"]
    target = world["project"] / "portable"
    archive.export(owner._home(world["project"], state["run_id"]), manifest, target)
    registered = {
        "id": "portable",
        "path": str(target / "manifest.json"),
        "role": "evidence",
        "required": False,
        "retention": "durable",
    }
    state = command(owner, world, state, "artifact.register", registered)
    request = {
        "archive_id": "recovered",
        "manifest_artifact_id": "portable",
        "manifest_sha256": hashlib.sha256(
            (target / "manifest.json").read_bytes()
        ).hexdigest(),
        "authorization": "restore-plan",
    }
    state, request = authorize(
        world, state, request, "native.archive.restore", identity="restore-plan"
    )
    original = archive.restore_export
    materialize = archive.storage.materialize
    writes = []
    restoring = [False]

    def changed_after_admission(*args, **kwargs):
        value = json.loads((target / "manifest.json").read_bytes())
        value["codec_at_export"] = "0" * 64
        (target / "manifest.json").write_text(json.dumps(value))
        assert archive.verify_export(target)["status"] == "PASS"
        restoring[0] = True
        try:
            return original(*args, **kwargs)
        finally:
            restoring[0] = False

    def observed_write(*args, **kwargs):
        if restoring[0]:
            writes.append(True)
        return materialize(*args, **kwargs)

    monkeypatch.setattr(archive, "restore_export", changed_after_admission)
    monkeypatch.setattr(archive.storage, "materialize", observed_write)
    error = None
    try:
        command(owner, world, state, "native.archive.restore", request)
    except ValueError as exc:
        error = exc
    assert writes == [], "changed approved input reached evidence materialization"
    assert error is not None, "changed approved manifest must refuse"
