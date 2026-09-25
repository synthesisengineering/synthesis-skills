"""Retained desktop identity evidence selects recovery, never active authority."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "synthesis-project-management/scripts"))
from test_run_admission import world, NATIVE, SEAT, write_board
from test_run_state import engine


def desktop(world, status="active"):
    from peer_addressing import write_seat, SelfIdentity, CLIENT_CLAUDE
    from coordination_schema import identity_from_uuid
    root = world["runtime"] / "engagements"
    root.mkdir(parents=True)
    key = hashlib.sha1(str(world["plan"]).encode()).hexdigest()[:12]
    path = root / f"{world['plan'].stem[:40]}-{key}.json"
    path.write_text(json.dumps({"client_session_ref": "ccd:local_fixture", "session_id": SEAT,
        "status": status, "plan": str(world["plan"]), "pending": ["retained obligation"]}))
    seat = write_seat(world["board"], session_uuid=SEAT, compact_id=identity_from_uuid(SEAT).compact_id,
        machine="fixture-machine", identity=SelfIdentity(client=CLIENT_CLAUDE,
        harness_session_id=NATIVE, host_session_id="local_fixture"), status="active")
    return root, path, seat


@pytest.mark.parametrize("status", ["active", "closed"])
def test_verified_desktop_alias_survives_sidecar_release_without_grant(engine, world, status):
    import autopilot
    root, path, seat = desktop(world, status)
    engine.index_legacy(world["actor"], root, runtime_root=world["runtime"])
    seat.unlink()  # Official PM release removes this sidecar.
    write_board(world, status="released")
    before = {str(p): p.read_bytes() for p in world["runtime"].rglob("*") if p.is_file()}
    for repeat in (False, True, False):
        world["actor"]["native_payload"]["stop_hook_active"] = repeat
        found = engine.legacy_for_stop(world["actor"], root, runtime_root=world["runtime"])
        if status == "active":
            assert found["owned_active"] or any(row["blocking"] for row in found["unattributed"])
            result = autopilot.stop_result(world["actor"], runtime_root=world["runtime"])
            assert result["continue"] is False and result.get("decision") != "block"
        else:
            assert autopilot.stop_result(world["actor"], runtime_root=world["runtime"]) == {}
        assert {str(p): p.read_bytes() for p in world["runtime"].rglob("*") if p.is_file()} == before
    from run_admission import admit_paths
    with pytest.raises(ValueError):
        admit_paths(world["board"], "alpha", world["project"], [world["plan"]], world["actor"]["native_payload"])


def test_erased_preindex_binding_is_unknown_only_for_explicit_selected_plan(engine, world):
    import autopilot
    root, path, seat = desktop(world)
    saved = path.read_bytes()
    seat.unlink()
    write_board(world, status="released")
    report = engine.index_legacy(world["actor"], root, runtime_root=world["runtime"])
    assert any(item["source"] == str(path) and item["status"] == "UNKNOWN" for item in report["unattributed"])
    # No attribution may be invented for an arbitrary desktop record, and
    # foreign unknown records cannot become this session's Stop obligation.
    assert autopilot.stop_result(world["actor"], runtime_root=world["runtime"]) == {}
    selected = engine.legacy_for_stop(world["actor"], root, plan=world["plan"], runtime_root=world["runtime"])
    assert not selected["owned_active"]
    assert any(item["blocking"] and "binding" in item["reason"] for item in selected["unattributed"])
    assert saved == path.read_bytes()


@pytest.mark.parametrize("fault", ["foreign-native", "wrong-host", "symlink", "malformed", "wrong-client"])
def test_desktop_alias_needs_exact_sidecar_binding(engine, world, fault):
    import autopilot
    root, path, seat = desktop(world)
    value = json.loads(seat.read_text())
    if fault == "foreign-native": value["harness_session_id"] = "01990000-0000-7000-8000-000000000099"
    elif fault == "wrong-host": value["host_session_id"] = "local_foreign"
    elif fault == "wrong-client": value["client"] = "codex"
    if fault == "symlink":
        external = world["scratch"] / "retained-sidecar.json"
        seat.rename(external); seat.symlink_to(external)
    else:
        seat.write_text("{malformed" if fault == "malformed" else json.dumps(value))
    write_board(world, status="released")
    engine.index_legacy(world["actor"], root, runtime_root=world["runtime"])
    assert autopilot.stop_result(world["actor"], runtime_root=world["runtime"]) == {}


@pytest.mark.parametrize("status", ["active", "closed"])
def test_reindex_cannot_erase_prior_verified_desktop_selection(engine, world, status):
    import autopilot
    root, path, seat = desktop(world, status)
    engine.index_legacy(world["actor"], root, runtime_root=world["runtime"])
    seat.unlink(); write_board(world, status="released")
    source = path.read_bytes()
    for _ in range(2):
        report = engine.index_legacy(world["actor"], root, runtime_root=world["runtime"])
        result = autopilot.stop_result(world["actor"], runtime_root=world["runtime"])
        if status == "active":
            assert result["continue"] is False
            assert result.get("decision") != "block"
        else:
            assert result == {} and report["unattributed"] == []
        assert path.read_bytes() == source


@pytest.mark.parametrize("fault", ["corrupt", "changed-host", "symlink", "missing"])
def test_retained_desktop_selected_source_drift_stays_unresolved(engine, world, fault):
    import autopilot
    root, path, seat = desktop(world)
    engine.index_legacy(world["actor"], root, runtime_root=world["runtime"])
    seat.unlink(); write_board(world, status="released")
    if fault == "corrupt": path.write_text("{broken")
    elif fault == "changed-host":
        value = json.loads(path.read_text()); value["client_session_ref"] = "ccd:local_changed"
        path.write_text(json.dumps(value))
    elif fault == "symlink":
        outside = world["scratch"] / "retained-legacy.json"
        path.rename(outside); path.symlink_to(outside)
    else: path.unlink()
    for _ in range(2):
        result = autopilot.stop_result(world["actor"], runtime_root=world["runtime"])
        assert result["continue"] is False and result.get("decision") != "block"
        engine.index_legacy(world["actor"], root, runtime_root=world["runtime"])


def test_desktop_stop_never_rescans_sidecars_or_global_legacy(engine, world, monkeypatch):
    root, path, seat = desktop(world)
    engine.index_legacy(world["actor"], root, runtime_root=world["runtime"])
    seat.unlink(); write_board(world, status="released")
    def forbidden(*args, **kwargs):
        pytest.fail("Stop must consume indexed native selectors only")
    monkeypatch.setattr(engine, "_desktop_legacy_binding", forbidden)
    monkeypatch.setattr(Path, "glob", forbidden)
    assert engine.legacy_for_stop(world["actor"], root, runtime_root=world["runtime"])["owned_active"]


def test_erased_closed_desktop_record_never_creates_recovery_warning(engine, world):
    import autopilot
    root, path, seat = desktop(world, "closed")
    seat.unlink(); write_board(world, status="released")
    report = engine.index_legacy(world["actor"], root, runtime_root=world["runtime"])
    assert report["unattributed"] == []
    for repeat in (False, True, False):
        world["actor"]["native_payload"]["stop_hook_active"] = repeat
        assert autopilot.stop_result(world["actor"], runtime_root=world["runtime"]) == {}
        selected = engine.legacy_for_stop(world["actor"], root, plan=world["plan"], runtime_root=world["runtime"])
        assert not selected["owned_active"] and not selected["unattributed"]


def test_older_scan_cannot_erase_binding_committed_before_its_lock(engine, world, monkeypatch):
    """Deterministic interleaving: another index sees the last live sidecar."""
    from contextlib import contextmanager
    import autopilot
    root, path, seat = desktop(world)
    sidecar = seat.read_bytes()
    seat.unlink()  # This outer scan starts without the native mapping.
    original_lock = engine.bounded_lock
    interleave = True

    @contextmanager
    def index_between_scan_and_commit(lock, *args, **kwargs):
        nonlocal interleave
        if interleave and Path(lock).name == ".index.lock":
            interleave = False
            seat.write_bytes(sidecar)
            engine.index_legacy(world["actor"], root, runtime_root=world["runtime"])
            seat.unlink()
            write_board(world, status="released")
        with original_lock(lock, *args, **kwargs):
            yield

    monkeypatch.setattr(engine, "bounded_lock", index_between_scan_and_commit)
    engine.index_legacy(world["actor"], root, runtime_root=world["runtime"])
    assert not interleave
    found = engine.legacy_for_stop(world["actor"], root, runtime_root=world["runtime"])
    assert len(found["owned_active"]) == 1
    assert autopilot.stop_result(world["actor"], runtime_root=world["runtime"])["continue"] is False


@pytest.mark.parametrize("status", ["active", "closed"])
@pytest.mark.parametrize("selector", ["modern-seat", "native-reference"])
def test_alternative_selector_cannot_override_retained_desktop_binding(engine, world, status, selector):
    """D0-STOP-REVIEW-1: contradictory historical identity stays unresolved."""
    import autopilot
    if selector == "modern-seat":
        from test_run_state import create, command
        modern = create(engine, world)
        command(engine, world, modern, "close", {"status": "cancelled", "reason": "Fixture closure"})
    root, path, seat = desktop(world, status)
    engine.index_legacy(world["actor"], root, runtime_root=world["runtime"])
    seat.unlink(); write_board(world, status="released")
    record = json.loads(path.read_text())
    if selector == "modern-seat":
        record["client_session_ref"] = "ccd:foreign-host"
    else:
        record["client_session_ref"] = "cc:" + NATIVE
        record["session_id"] = "01990000-0000-7000-8000-000000000099"
    path.write_text(json.dumps(record))
    before = {str(p): p.read_bytes() for p in world["runtime"].rglob("*") if p.is_file()}
    for repeat in (False, True, False):
        world["actor"]["native_payload"]["stop_hook_active"] = repeat
        found = engine.legacy_for_stop(world["actor"], root, runtime_root=world["runtime"])
        assert not found["owned_active"] and not found["owned_terminal"]
        assert any(row["blocking"] for row in found["unattributed"])
        result = autopilot.stop_result(world["actor"], runtime_root=world["runtime"])
        assert result["continue"] is False and result.get("decision") != "block"
        assert before == {str(p): p.read_bytes() for p in world["runtime"].rglob("*") if p.is_file()}
