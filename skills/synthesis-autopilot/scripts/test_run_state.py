"""Behavioral foundation tests; all files and native evidence are temporary."""
from __future__ import annotations

from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_run_admission import world, write_board, SEAT, NATIVE  # noqa: F401


@pytest.fixture
def engine(monkeypatch):
    module = importlib.import_module("run_state")
    # Tests register deliberately synthetic trusted-code callbacks. Isolate
    # them from production bridge/extension registration in other test files.
    for name in ("_COMMANDS", "_VERIFIERS", "_CONSTRAINTS", "_EVIDENCE_SOURCES", "_OBSERVERS", "_ACCEPTANCE"):
        if hasattr(module, name):
            monkeypatch.setattr(module, name, {})
    if hasattr(module, "_TERMINAL_COMMANDS"):
        monkeypatch.setattr(module, "_TERMINAL_COMMANDS", set())
    return module


def contract():
    return {"schema_version": 1, "scope": ["Produce the fixture output"], "exclusions": [],
            "outcomes": [{"id": "deliver", "description": "Output", "criteria": ["accept"]}],
            "criteria": [{"id": "accept", "description": "Output exists and is verified",
                          "required": True, "method": "artifact", "artifact_ids": ["output"]}],
            "authority_refs": []}


def create(engine, world, **overrides):
    args = {"project_id": "alpha", "plan": world["plan"], "contract": contract(),
            "profile": {"schema": 1, "items": [{"id": "fixture", "required": True, "criterion_ids": ["accept"]}]},
            "actor": world["actor"], "command_id": "create-fixture", "runtime_root": world["runtime"]}
    args.update(overrides)
    return engine.create_run(world["project"], **args)


def command(engine, world, state, name, payload, *, command_id=None, **overrides):
    kwargs = {"expected_revision": state["revision"], "command_id": command_id or f"{name}-{state['revision']}",
              "actor": world["actor"], "runtime_root": world["runtime"]}
    kwargs.update(overrides)
    return engine.apply_command(world["project"], state["run_id"], name, payload, **kwargs)


def output(engine, world, state):
    path = world["project"] / "resources/artifacts/output.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("Verified output\n")
    return command(engine, world, state, "artifact.register", {"id": "output", "path": str(path),
                   "role": "output", "retention": "durable", "required": True}), path


def verified(engine, world):
    state, path = output(engine, world, create(engine, world))
    state = command(engine, world, state, "transition", {"status": "verifying"})
    state = command(engine, world, state, "verify", {"criteria": ["accept"]})
    return state, path


def receipt(engine, world, state, kind, data=None, *, receipt_id=None):
    now = datetime.now(timezone.utc)
    path = world["project"] / "resources/artifacts" / f"{kind}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"kind": kind, "observed_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "bindings": {"run_id": state["run_id"], "contract_digest": state["contract_digest"],
                     "profile_digest": state["profile_digest"]}, "data": data or {}}))
    state = command(engine, world, state, "artifact.register", {"id": kind, "path": str(path),
                    "role": "evidence", "retention": "durable", "required": False})
    engine.register_verifier(kind, lambda record, bindings: True)
    return command(engine, world, state, "evidence.record", {"id": receipt_id or kind, "kind": kind, "artifact_id": kind})


def test_creation_requires_real_plan_contract_and_exact_admission(engine, world):
    for overrides in ({"plan": world["project"] / "absent.md"}, {"contract": {}}, {"profile": {}}):
        with pytest.raises(ValueError):
            create(engine, world, **overrides)
    assert not (world["project"] / "resources/autopilot-runs").exists()
    write_board(world, claims=str(world["plan"]))
    with pytest.raises(ValueError):
        create(engine, world)


def test_committed_events_rebuild_projections_without_rewriting_human_plan(engine, world):
    state = create(engine, world)
    home = world["project"] / "resources/autopilot-runs" / state["run_id"]
    assert len(list((home / "events").glob("*.json"))) == 1
    assert engine.load_run(world["project"], state["run_id"]) == state
    (home / "current.json").write_text("corrupt projection")
    (home / "summary.md").unlink()
    engine.rebuild_projections(world["project"], state["run_id"], actor=world["actor"])
    assert json.loads((home / "current.json").read_text()) == state
    assert "Human-owned prose." in world["plan"].read_text()
    assert world["plan"].read_text().count(f"autopilot:{state['run_id']}:start") == 1


def test_event_commit_survives_interrupted_projection(engine, world, monkeypatch):
    state = create(engine, world)
    original = engine._project
    monkeypatch.setattr(engine, "_project", lambda *a, **k: (_ for _ in ()).throw(OSError("fixture projection crash")))
    with pytest.raises(OSError):
        command(engine, world, state, "progress", {"summary": "Durable progress"})
    monkeypatch.setattr(engine, "_project", original)
    recovered = engine.load_run(world["project"], state["run_id"])
    assert recovered["revision"] == state["revision"] + 1
    assert recovered["progress"]["summary"] == "Durable progress"


def test_cas_and_idempotent_commands_prevent_lost_updates(engine, world):
    state = create(engine, world)
    first = command(engine, world, state, "progress", {"summary": "One"}, command_id="one")
    assert command(engine, world, state, "progress", {"summary": "One"}, command_id="one") == first
    with pytest.raises(ValueError):
        command(engine, world, state, "progress", {"summary": "Changed"}, command_id="one")
    with pytest.raises(ValueError):
        command(engine, world, state, "progress", {"summary": "Stale"}, command_id="two")
    def update(number):
        try:
            return command(engine, world, first, "progress", {"summary": str(number)}, command_id=str(number))
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, [2, 3]))
    assert sum(result is not None for result in results) == 1
    assert engine.load_run(world["project"], state["run_id"])["revision"] == first["revision"] + 1


def test_owner_index_does_not_parse_corrupt_foreign_run(engine, world):
    state = create(engine, world)
    foreign = world["runtime"] / "owners" / "01990000-0000-7000-8000-000000000099.json"
    foreign.parent.mkdir(parents=True, exist_ok=True)
    foreign.write_text("{malformed foreign index")
    assert [item["run_id"] for item in engine.owned_runs(world["actor"], runtime_root=world["runtime"])] == [state["run_id"]]
    (world["runtime"] / "owners" / f"{SEAT}.json").write_text("malformed own index")
    with pytest.raises(ValueError):
        engine.owned_runs(world["actor"], runtime_root=world["runtime"])


def test_terminal_tombstone_rejects_late_wake_even_with_stale_index(engine, world):
    state = create(engine, world)
    closed = command(engine, world, state, "close", {"status": "cancelled", "reason": "User cancellation"})
    home = world["project"] / "resources/autopilot-runs" / state["run_id"]
    assert json.loads((home / "terminal.json").read_text())["status"] == "cancelled"
    with pytest.raises(ValueError):
        command(engine, world, closed, "progress", {"summary": "Late wake"})
    assert engine.owned_runs(world["actor"], runtime_root=world["runtime"]) == []


def test_wait_resolution_is_explicit_and_old_wait_cannot_accept_completion(engine, world):
    state, _ = output(engine, world, create(engine, world))
    state = command(engine, world, state, "wait.add", {"id": "dependency", "kind": "external", "reason": "Pending readback"})
    state = command(engine, world, state, "progress", {"summary": "Unrelated progress"})
    with pytest.raises(ValueError):
        command(engine, world, state, "close", {"status": "completed"})
    with pytest.raises(ValueError):
        command(engine, world, state, "wait.resolve", {"id": "dependency", "evidence": "fabricated"})
    state = receipt(engine, world, state, "wait-resolution", {"wait_id": "dependency", "resolved": True})
    state = command(engine, world, state, "wait.resolve", {"id": "dependency", "evidence": "wait-resolution"})
    assert state["waits"]["dependency"]["status"] == "resolved"
    assert state["status"] == "running"


@pytest.mark.parametrize("change", ["profile", "contract", "missing", "modified"])
def test_completion_receipt_cannot_survive_bound_input_change(engine, world, change):
    state, path = verified(engine, world)
    if change == "profile":
        changed_profile = deepcopy(state["profile"])
        changed_profile["items"].append({"id": "new", "required": True})
        state = command(engine, world, state, "profile.amend", {"profile": changed_profile})
    elif change == "contract":
        revised = contract()
        revised["criteria"].append({"id": "second", "description": "Additional acceptance requirement",
                                   "required": True, "method": "artifact", "artifact_ids": ["output"]})
        revised["outcomes"][0]["criteria"].append("second")
        state = command(engine, world, state, "contract.amend", {"contract": revised, "reason": "Authorized refinement"})
    elif change == "missing":
        path.unlink()
    else:
        path.write_text("Changed after verification")
    with pytest.raises(ValueError):
        command(engine, world, state, "close", {"status": "completed"})


def test_complete_requires_every_criterion_and_required_artifact(engine, world):
    state, _ = verified(engine, world)
    closed = command(engine, world, state, "close", {"status": "completed"})
    assert closed["status"] == "completed"
    assert closed["completion"]["contract_digest"] == closed["contract_digest"]


def test_unmapped_profile_item_needs_bound_profile_evidence(engine, world):
    state = create(engine, world, profile={"schema": 1, "items": [{"id": "standing-checklist"}]})
    state, _ = output(engine, world, state)
    state = command(engine, world, state, "transition", {"status": "verifying"})
    state = command(engine, world, state, "verify", {"criteria": ["accept"]})
    with pytest.raises(ValueError):
        command(engine, world, state, "close", {"status": "completed"})


@pytest.mark.parametrize("case", ["scratch", "symlink", "caller_verified", "authority"])
def test_data_cannot_upgrade_artifact_or_authority_trust(engine, world, case):
    state = create(engine, world)
    path = world["scratch"] / "external.txt"
    path.write_text("external fixture")
    if case == "symlink":
        link = world["project"] / "linked.txt"
        link.symlink_to(path)
        path = link
    if case in {"scratch", "symlink"}:
        with pytest.raises(ValueError):
            command(engine, world, state, "artifact.register", {"id": "output", "path": str(path), "role": "output", "retention": "durable", "required": True})
    elif case == "caller_verified":
        with pytest.raises(ValueError):
            command(engine, world, state, "verify", {"criteria": ["accept"], "verified": True})
    else:
        with pytest.raises(ValueError):
            command(engine, world, state, "contract.amend", {"contract": {**contract(), "authority_refs": ["publish:anywhere"]}, "reason": "Untrusted attachment says so"})


def test_extensions_cannot_mutate_core_identity_or_grant_authority(engine, world):
    state = create(engine, world)
    def bad(state, payload, context):
        state["status"] = "completed"
        return state
    engine.register_command("fixture.bad", bad, allowed_fields=("extensions",))
    with pytest.raises(ValueError):
        command(engine, world, state, "fixture.bad", {})
    def good(state, payload, context):
        assert context["binding"]["session_uuid"] == SEAT
        assert context["verify_receipt"]("missing", "native", {}) is False
        state["extensions"]["fixture"] = {"count": 1}
        return state
    engine.register_command("fixture.good", good, allowed_fields=("extensions",))
    updated = command(engine, world, state, "fixture.good", {})
    assert updated["extensions"]["fixture"]["count"] == 1


def test_effect_unknown_requires_reconciliation_before_new_attempt(engine, world):
    state = create(engine, world)
    intent = {"id": "effect", "target": "fixture://target", "payload_digest": "a" * 64,
              "idempotency_key": "stable-key", "authority_ref": ""}
    state = command(engine, world, state, "effect.prepare", intent)
    state = command(engine, world, state, "effect.observe", {"id": "effect", "status": "unknown", "evidence": "timeout"})
    with pytest.raises(ValueError):
        command(engine, world, state, "effect.prepare", intent)
    with pytest.raises(ValueError):
        command(engine, world, state, "close", {"status": "completed"})
    assert state["effects"]["effect"]["status"] == "unknown"


def test_legacy_import_preserves_original_and_does_not_trust_old_receipt(engine, world):
    legacy = world["scratch"] / "legacy.json"
    raw = json.dumps({"id": "legacy-fixture", "project_id": "alpha", "plan": str(world["plan"]),
                      "state": "active", "profile": {"schema": 1, "items": [{"id": "old"}]},
                      "blocker": {"reason": "dependency"}, "receipt": {"passed": True}}).encode()
    legacy.write_bytes(raw)
    state = engine.import_legacy(world["project"], legacy, project_id="alpha", plan=world["plan"],
                                 contract=contract(), actor=world["actor"], command_id="import-fixture", runtime_root=world["runtime"])
    assert legacy.read_bytes() == raw
    assert state["status"] == "recovering"
    assert state["verification"] == {}
    home = world["project"] / "resources/autopilot-runs" / state["run_id"]
    assert (home / "legacy/original.json").read_bytes() == raw
    assert state["migration"]["legacy_receipt_trusted"] is False


def test_event_tamper_and_unclaimed_mutation_fail_without_projection_changes(engine, world):
    state = create(engine, world)
    write_board(world, claims=str(world["project"] / "unrelated/**"))
    with pytest.raises(ValueError):
        command(engine, world, state, "progress", {"summary": "Unclaimed"})
    assert engine.load_run(world["project"], state["run_id"]) == state
    home = world["project"] / "resources/autopilot-runs" / state["run_id"]
    event = next((home / "events").glob("*.json"))
    record = json.loads(event.read_text())
    record["state"]["status"] = "completed"
    event.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        engine.load_run(world["project"], state["run_id"])


@pytest.mark.parametrize("weakening", ["required", "description", "drop"])
def test_contract_weakening_requires_authenticated_amendment(engine, world, weakening):
    initial = contract()
    initial["criteria"].append({"id": "second", "description": "Second requested result", "required": True,
                                "method": "artifact", "artifact_ids": ["second"]})
    initial["outcomes"][0]["criteria"].append("second")
    state = create(engine, world, contract=initial)
    revised = deepcopy(initial)
    if weakening == "required":
        revised["criteria"][1]["required"] = False
    elif weakening == "description":
        revised["criteria"][1]["description"] = "Agent reduced the acceptance meaning"
    else:
        revised["criteria"].pop()
        revised["outcomes"][0]["criteria"].pop()
    with pytest.raises(ValueError):
        command(engine, world, state, "contract.amend", {"contract": revised, "reason": "Freeform assertion of approval"})


def test_narration_is_not_measured_progress_and_close_cannot_bypass_constraints(engine, world):
    state, _ = verified(engine, world)
    state = command(engine, world, state, "progress", {"summary": "Narrated progress"})
    assert state["progress"]["measured"] is False
    assert state["progress"]["observation_count"] == 1
    def guard(state, name, payload, context):
        if name == "close":
            raise ValueError("fixture unresolved workflow quality")
    engine.register_constraint("fixture-closure", guard)
    try:
        with pytest.raises(ValueError, match="workflow quality"):
            command(engine, world, state, "close", {"status": "completed"})
    finally:
        engine.unregister_constraint("fixture-closure")


def test_inspection_revalidates_current_state_and_bound_artifacts(engine, world):
    state, path = verified(engine, world)
    context = engine.inspect_context(state, world["actor"])
    assert context["artifacts"]["output"]["digest"] == state["artifacts"]["output"]["digest"]
    assert engine.completion_report(world["project"], state["run_id"], actor=world["actor"])["status"] == "PASS"
    path.unlink()
    assert engine.completion_report(world["project"], state["run_id"], actor=world["actor"])["status"] == "FAIL"


def test_ordinary_install_with_no_board_or_owned_index_is_healthy_no_run(engine, world):
    world["board"].unlink()
    assert engine.owned_runs(world["actor"], runtime_root=world["runtime"]) == []
    owners = world["runtime"] / "owners"
    owners.mkdir(parents=True)
    (owners / "foreign.json").write_text("corrupt unrelated entry")
    assert engine.owned_runs(world["actor"], runtime_root=world["runtime"]) == []


def test_declared_terminal_cleanup_cannot_reopen_run(engine, world):
    state = create(engine, world)
    state = command(engine, world, state, "close", {"status": "cancelled", "reason": "Fixture cancellation"})
    terminal = deepcopy(state["terminal"])
    def cleanup(state, payload, context):
        state["extensions"]["cleanup"] = "confirmed"
        return state
    engine.register_command("fixture.cleanup", cleanup, terminal_safe=True)
    state = command(engine, world, state, "fixture.cleanup", {})
    assert state["terminal"] == terminal and state["status"] == "cancelled"


def test_released_native_seat_finds_terminal_tombstone_without_live_admission(engine, world):
    state = create(engine, world)
    command(engine, world, state, "close", {"status": "cancelled", "reason": "Complete fixture cleanup"})
    write_board(world, status="released")
    assert engine.owned_runs(world["actor"], runtime_root=world["runtime"]) == []
    assert engine.owned_runs(world["actor"], runtime_root=world["runtime"], include_terminal=True)[0]["status"] == "cancelled"


def test_released_native_seat_cannot_hide_an_unfinished_owned_run(engine, world):
    create(engine, world)
    write_board(world, status="released")
    with pytest.raises(ValueError):
        engine.owned_runs(world["actor"], runtime_root=world["runtime"])


def test_profile_removal_cannot_bypass_original_required_disposition(engine, world):
    state = create(engine, world)
    with pytest.raises(ValueError):
        command(engine, world, state, "profile.amend", {"profile": {"schema": 1, "items": []}})


@pytest.mark.parametrize("change", ["scope", "exclusion"])
def test_material_scope_and_exclusion_changes_need_bound_user_amendment(engine, world, change):
    initial = contract()
    initial["exclusions"] = ["Do not publish"]
    state = create(engine, world, contract=initial)
    replacement = deepcopy(initial)
    if change == "scope":
        replacement["scope"].append("Publish everywhere")
    else:
        replacement["exclusions"] = []
    with pytest.raises(ValueError):
        command(engine, world, state, "contract.amend", {"contract": replacement})


def test_effect_absence_observation_cannot_authorize_a_later_attempt(engine, world):
    state = create(engine, world)
    intent = {"id": "effect", "target": "fixture://target", "payload_digest": "a" * 64,
              "idempotency_key": "stable-key", "authority_ref": ""}
    state = command(engine, world, state, "effect.prepare", intent)
    state = receipt(engine, world, state, "effect-readback", {**intent, "status": "absent"})
    state = command(engine, world, state, "effect.reconcile", {"id": "effect", "evidence": "effect-readback"})
    state = command(engine, world, state, "effect.prepare", intent)
    with pytest.raises(ValueError):
        command(engine, world, state, "effect.reconcile", {"id": "effect", "evidence": "effect-readback"})


def legacy_record(world):
    return {"plan": str(world["plan"]), "project_id": "alpha", "session_id": SEAT,
            "client_session_ref": f"cc:{NATIVE}", "status": "active", "goals_met": True,
            "profile": {"schema": 1, "items": [{"id": "fixture", "criterion_ids": ["accept"]}]}}


def test_legacy_discovery_scopes_owner_and_requires_byte_identical_import(engine, world):
    root = world["runtime"] / "engagements"
    root.mkdir(parents=True)
    owned = root / "owned.json"
    owned.write_text(json.dumps(legacy_record(world)))
    foreign = root / "foreign.json"
    foreign.write_text(json.dumps({**legacy_record(world), "session_id": "foreign", "client_session_ref": "cc:01990000-0000-7000-8000-000000000099"}))
    corrupt = root / "corrupt-foreign.json"
    corrupt.write_bytes(b"{foreign corrupt\xff")
    before = corrupt.read_bytes(), foreign.read_bytes()
    found = engine.discover_legacy(world["actor"], root)
    assert len(found["owned_active"]) == 1
    assert found["owned_active"][0]["source"] == str(owned)
    assert found["foreign_count"] == 1 and found["unattributed"]
    engine.import_legacy(world["project"], owned, project_id="alpha", plan=world["plan"], contract=contract(),
                         actor=world["actor"], command_id="migrate-owned", runtime_root=world["runtime"])
    assert not engine.discover_legacy(world["actor"], root)["owned_active"]
    owned.write_text(owned.read_text() + "\n")
    assert engine.discover_legacy(world["actor"], root)["owned_active"]
    assert (corrupt.read_bytes(), foreign.read_bytes()) == before


def test_legacy_exact_plan_path_fast_lookup_retains_owned_corruption(engine, world):
    import hashlib
    root = world["runtime"] / "engagements"
    root.mkdir(parents=True)
    key = hashlib.sha1(str(world["plan"]).encode()).hexdigest()[:12]
    path = root / f"{world['plan'].stem[:40]}-{key}.json"
    path.write_text('{"session_id": "' + SEAT + '", "client_session_ref": "cc:' + NATIVE + '", broken')
    result = engine.discover_legacy(world["actor"], root, plan=world["plan"])
    assert result["unattributed"][0]["blocking"] is True
    assert result["scanned"] == 1


def test_criterion_report_is_current_and_shared_with_completion(engine, world):
    state, path = verified(engine, world)
    report = engine.criterion_report(state, engine.inspect_context(state, world["actor"]))
    assert report["criteria"][0]["status"] == "PASS"
    path.write_text("Changed fixture")
    report = engine.criterion_report(state, engine.inspect_context(state, world["actor"]))
    assert report["criteria"][0]["status"] == "FAIL"
    assert report["status"] == "FAIL"


def test_engine_observer_executes_once_and_generated_evidence_tracks_inputs(engine, world):
    state, path = output(engine, world, create(engine, world))
    calls = []
    def observer(context, payload):
        calls.append(payload["check_id"])
        assert context["actor"] == world["actor"]
        return {"passed": False, "returncode": 1, "artifact_id": payload["check_id"]}
    engine.register_observer("fixture-check", observer)
    kwargs = {"expected_revision": state["revision"], "command_id": "observe-check", "actor": world["actor"], "runtime_root": world["runtime"]}
    observed = engine.observe(world["project"], state["run_id"], "fixture-check", {"check_id": "output"}, **kwargs)
    assert observed["observations"]["observe-check"]["data"]["passed"] is False
    assert engine.observe(world["project"], state["run_id"], "fixture-check", {"check_id": "output"}, **kwargs) == observed
    assert calls == ["output"]
    assert "observe-check" in engine.inspect_context(observed, world["actor"])["evidence"]
    path.write_text("Changed input")
    assert "observe-check" not in engine.inspect_context(observed, world["actor"])["evidence"]


def test_authentic_failed_observation_is_not_criterion_acceptance(engine, world):
    spec = contract()
    spec["criteria"][0].update(method="fixture-check", evidence_ids=["fixture-check"])
    state, _ = output(engine, world, create(engine, world, contract=spec))
    state = receipt(engine, world, state, "fixture-check", {"passed": False})
    state = command(engine, world, state, "transition", {"status": "verifying"})
    with pytest.raises(ValueError):
        command(engine, world, state, "verify", {"criteria": ["accept"]})
    engine.register_acceptance("fixture-check", lambda record, state, criterion, context: record["data"].get("passed") is True)
    with pytest.raises(ValueError):
        command(engine, world, state, "verify", {"criteria": ["accept"]})
    failed_run = deepcopy(state)
    # This synthetic external-verifier control does not exercise production
    # engine-observation routing. Keep its failed run intact; prove positive
    # acceptance independently using a new run and new immutable receipt ID.
    spec["criteria"][0]["evidence_ids"] = ["fixture-pass"]
    state, _ = output(engine, world, create(engine, world, contract=spec, command_id="create-positive-control"))
    state = receipt(engine, world, state, "fixture-check", {"passed": True}, receipt_id="fixture-pass")
    state = command(engine, world, state, "transition", {"status": "verifying"})
    state = command(engine, world, state, "verify", {"criteria": ["accept"]})
    assert engine.completion_report(world["project"], state["run_id"], actor=world["actor"])["status"] == "PASS"
    assert engine.load_run(world["project"], failed_run["run_id"]) == failed_run


def test_stop_legacy_inventory_requires_explicit_index_only_when_nonempty(engine, world):
    root = world["runtime"] / "engagements"
    assert engine.legacy_for_stop(world["actor"], root)["health"] == "PASS"
    root.mkdir(parents=True)
    (root / "foreign.json").write_text(json.dumps({"session_id": "foreign"}))
    result = engine.legacy_for_stop(world["actor"], root)
    assert result["health"] == "UNKNOWN" and result["scanned"] == 0
    assert "doctor --index-legacy" in result["action"]


def test_indexed_stop_reads_only_owned_records_despite_foreign_volume(engine, world):
    root = world["runtime"] / "engagements"
    root.mkdir(parents=True)
    owned = root / "owned.json"
    owned.write_text(json.dumps(legacy_record(world)))
    for number in range(600):
        (root / f"foreign-{number}.json").write_text(json.dumps({"session_id": "foreign", "status": "active"}))
    broken = root / "foreign-broken.json"
    broken.write_bytes(b"{foreign corrupt\xff")
    before = {path.name: path.read_bytes() for path in root.iterdir()}
    indexed = engine.index_legacy(world["actor"], root)
    assert indexed["health"] == "PASS" and indexed["unattributed"]
    result = engine.legacy_for_stop(world["actor"], root)
    assert result["health"] == "PASS" and result["scanned"] == 1
    assert result["owned_active"][0]["source"] == str(owned)
    assert {path.name: path.read_bytes() for path in root.iterdir()} == before
    owned.write_text('{"session_id":"' + SEAT + '",broken')
    result = engine.legacy_for_stop(world["actor"], root)
    assert result["unattributed"][0]["blocking"] is True


def test_indexed_stop_also_checks_exact_plan_new_record_and_import_digest(engine, world):
    import hashlib
    root = world["runtime"] / "engagements"
    root.mkdir(parents=True)
    engine.index_legacy(world["actor"], root)
    key = hashlib.sha1(str(world["plan"]).encode()).hexdigest()[:12]
    owned = root / f"{world['plan'].stem[:40]}-{key}.json"
    owned.write_text(json.dumps(legacy_record(world)))
    assert engine.legacy_for_stop(world["actor"], root, plan=world["plan"])["owned_active"]
    engine.import_legacy(world["project"], owned, project_id="alpha", plan=world["plan"], contract=contract(),
                         actor=world["actor"], command_id="index-import", runtime_root=world["runtime"])
    assert not engine.legacy_for_stop(world["actor"], root, plan=world["plan"])["owned_active"]
    owned.write_text(owned.read_text() + "\n")
    assert engine.legacy_for_stop(world["actor"], root, plan=world["plan"])["owned_active"]


def test_stop_legacy_plan_fallback_uses_current_pm_declaration(engine, world):
    import hashlib
    root = world["runtime"] / "engagements"
    root.mkdir(parents=True)
    engine.index_legacy(world["actor"], root)
    key = hashlib.sha1(str(world["plan"]).encode()).hexdigest()[:12]
    path = root / f"{world['plan'].stem[:40]}-{key}.json"
    path.write_text(json.dumps(legacy_record(world)))
    found = engine.legacy_for_stop(world["actor"], root)
    assert found["scanned"] == 1 and found["owned_active"][0]["source"] == str(path)
    path.write_text('{"session_id":"' + SEAT + '",broken')
    assert engine.legacy_for_stop(world["actor"], root)["unattributed"][0]["blocking"] is True


def test_corrupt_foreign_index_does_not_affect_selected_native(engine, world):
    root = world["runtime"] / "engagements"
    root.mkdir(parents=True)
    engine.index_legacy(world["actor"], root)
    index_root = world["runtime"] / "legacy-index"
    generation = json.loads((index_root / "manifest.json").read_text())["generation"]
    (index_root / "generations" / generation / "native" / "foreign.json").write_text("corrupt")
    assert engine.legacy_for_stop(world["actor"], root)["health"] == "PASS"


def test_stop_inspection_validates_each_owned_run_once_and_rejects_revocation(engine, world, monkeypatch):
    state = create(engine, world)
    calls = []
    original = engine.inspect_paths
    def observed(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(engine, "inspect_paths", observed)
    inspected = engine.inspect_owned_runs(world["actor"], runtime_root=world["runtime"])
    assert len(inspected) == 1 and inspected[0][0]["run_id"] == state["run_id"]
    assert inspected[0][1]["binding"]["session_uuid"] == SEAT
    assert calls == [True]
    write_board(world, status="released")
    with pytest.raises(ValueError):
        engine.inspect_owned_runs(world["actor"], runtime_root=world["runtime"])


def test_passive_owned_wait_uses_current_evidence_despite_unrelated_board_defect(engine, world):
    import capabilities
    import evidence_bridge
    from test_evidence_bridge import append_claude_tool, record
    from test_run_admission import add_passive_peer
    capabilities.register_commands(engine.register_command)
    evidence_bridge.register_sources(engine.register_evidence_source)
    state = create(engine, world)
    state = command(engine, world, state, "wait.add", {"id": "review", "kind": "user", "reason": "Review output"})
    wait = capabilities.wait_binding(state)
    append_claude_tool(world, "mcp__codex_app__send_message_to_thread",
                      {"threadId": "fixture-peer", "prompt": json.dumps({"run_id": state["run_id"], **wait})},
                      {"status": "delivered", "threadId": "fixture-peer"})
    context = {"project": world["project"], "state": state, "binding": state["owner"],
               "actor": world["actor"], "now": datetime.now(timezone.utc).isoformat(), "artifacts": {}}
    data = {"source": {"kind": "native-tool", "call_id": "native-call"}, "delivery_id": "native-call",
            "channel": "codex-task", "status": "delivered", **wait}
    receipt = world["project"] / "delivery.json"
    receipt.write_text(json.dumps(record("delivery", data, context)))
    state = command(engine, world, state, "artifact.register", {"id": "delivery", "path": str(receipt),
                    "role": "evidence", "retention": "durable", "required": False})
    state = command(engine, world, state, "evidence.record", {"id": "delivery", "kind": "delivery", "artifact_id": "delivery"})
    state = command(engine, world, state, "delivery.record", {"receipt": "delivery"})
    add_passive_peer(world, world["scratch"] / "retired/projects/foreign/file.md")
    inspected = engine.inspect_owned_runs(world["actor"], runtime_root=world["runtime"])
    assert len(inspected) == 1
    current, validated = inspected[0]
    assert validated["binding"]["purpose"] == "passive-stop"
    assert capabilities.wait_delivery_status(current, validated)["delivered"] is True
    # It remains a fresh read of receipt bytes, not a cached positive.
    receipt.write_text(receipt.read_text() + "\n")
    current, validated = engine.inspect_owned_runs(world["actor"], runtime_root=world["runtime"])[0]
    assert capabilities.wait_delivery_status(current, validated)["delivered"] is False
    # The passive capability cannot route mutation or ordinary status through
    # its narrower purpose: both retain complete PM admission.
    with pytest.raises(ValueError, match="unverifiable|identity"):
        engine.inspect_context(state, world["actor"])
    with pytest.raises(ValueError, match="unverifiable|identity"):
        command(engine, world, state, "progress", {"summary": "Must not be written"})


def test_terminal_cleanup_can_observe_existing_spec_without_reopening_or_new_artifact(engine, world):
    state, _ = output(engine, world, create(engine, world))
    state = command(engine, world, state, "close", {"status": "cancelled", "reason": "Fixture end"})
    terminal = deepcopy(state["terminal"])
    engine.register_observer("continuation-cancellation", lambda context, payload: {"status": "cancelled"}, terminal_safe=True)
    state = engine.observe(world["project"], state["run_id"], "continuation-cancellation", {"check_id": "output"},
                           expected_revision=state["revision"], command_id="cleanup-observed", actor=world["actor"], runtime_root=world["runtime"])
    assert state["terminal"] == terminal and state["status"] == "cancelled"
    assert "cleanup-observed" in state["observations"]
    with pytest.raises(ValueError):
        engine.register_observer("arbitrary-work", lambda context, payload: {}, terminal_safe=True)
    with pytest.raises(ValueError):
        engine.observe(world["project"], state["run_id"], "continuation-cancellation", {"check_id": "unregistered"},
                       expected_revision=state["revision"], command_id="cleanup-unregistered", actor=world["actor"], runtime_root=world["runtime"])


def test_long_current_artifact_read_stays_within_its_fresh_admission_operation(engine, world, monkeypatch):
    import run_admission
    state, _ = output(engine, world, create(engine, world))
    clock = run_admission.time.monotonic
    elapsed = [0.0]
    monkeypatch.setattr(run_admission.time, "monotonic", lambda: clock() + elapsed[0])
    original = engine._artifact
    def slow_read(*args, **kwargs):
        value = original(*args, **kwargs)
        elapsed[0] += 2.0
        return value
    monkeypatch.setattr(engine, "_artifact", slow_read)
    context = engine.inspect_context(state, world["actor"], project=world["project"])
    assert context["artifacts"]["output"]["digest"] == state["artifacts"]["output"]["digest"]
    assert "admission_observation" not in context


def test_central_sources_share_admission_only_during_one_current_inspection(engine, world):
    from run_admission import read_admission_observation
    state = receipt(engine, world, create(engine, world), "local-source", {"fact": "fixture"})
    contexts = []
    def source(record, context):
        contexts.append(context)
        return read_admission_observation(context)["session_uuid"] == SEAT
    engine.register_evidence_source("local-source", source)
    context = engine.inspect_context(state, world["actor"])
    assert context["verify_receipt"]("local-source", "local-source", {}) is True
    with pytest.raises(ValueError):
        read_admission_observation(contexts[0])
    assert "admission_observation" not in context
    write_board(world, status="released")
    with pytest.raises(ValueError):
        engine.inspect_context(state, world["actor"])


@pytest.mark.parametrize("revoke", [False, True])
def test_observer_keeps_current_operation_admission_through_slow_io_and_readmits_before_commit(engine, world, monkeypatch, revoke):
    import evidence_bridge
    import run_admission
    state, _ = output(engine, world, create(engine, world))
    clock = run_admission.time.monotonic
    elapsed = [0.0]
    monkeypatch.setattr(run_admission.time, "monotonic", lambda: clock() + elapsed[0])
    def expired_passive_admission(*args, **kwargs):
        raise ValueError("passive coordination lease receipt expired")
    monkeypatch.setattr(evidence_bridge, "admit_paths", expired_passive_admission)
    contexts = []
    admitted = []
    def observer(context, payload):
        elapsed[0] += 2.0  # Beyond issuance age, within the admitted operation.
        contexts.append(context)
        assert evidence_bridge._fresh(context)["session_uuid"] == SEAT
        admitted.append(SEAT)
        if revoke:
            write_board(world, status="released")
        return {"passed": True}
    engine.register_observer("fixture-current-operation", observer)
    kwargs = {"expected_revision": state["revision"], "command_id": "current-operation", "actor": world["actor"], "runtime_root": world["runtime"]}
    if revoke:
        with pytest.raises(ValueError):
            engine.observe(world["project"], state["run_id"], "fixture-current-operation", {"check_id": "output"}, **kwargs)
        assert engine.load_run(world["project"], state["run_id"])["revision"] == state["revision"]
    else:
        observed = engine.observe(world["project"], state["run_id"], "fixture-current-operation", {"check_id": "output"}, **kwargs)
        assert observed["observations"]["current-operation"]["data"] == {"passed": True}
    assert len(contexts) == 1
    assert admitted == [SEAT]
    with pytest.raises(ValueError):
        run_admission.read_admission_observation(contexts[0])
def _repairable_observer_run(engine, world, kind="quality_observation"):
    declared = contract()
    declared["criteria"][0].update(method=kind, evidence_ids=["review-slot"])
    state, path = output(engine, world, create(engine, world, contract=declared))
    def observe(context, payload):
        return {"criterion_id": "accept", "artifact_id": "output",
                "artifact_digest": context["artifacts"]["output"]["digest"], "passed": path.read_text() == "Corrected\n"}
    engine.register_observer(kind, observe)
    engine.register_evidence_source(kind, lambda record, context: record.get("provenance") == "engine-observation")
    engine.register_acceptance(kind, lambda record, state, criterion, context: record["data"]["passed"] is True)
    state = command(engine, world, state, "observe:" + kind, {"check_id": "output"}, command_id="review-slot")
    return state, path


def _bind_review(engine, world, state, attempt, **changes):
    prior = state.get("criterion_evidence_bindings", {}).get("accept", {}).get("review-slot", {}).get("receipt_id", "review-slot")
    payload = {"criterion_id": "accept", "slot": "review-slot", "receipt_id": attempt,
               "expected_prior_receipt_id": prior, "expected_prior_digest": state["evidence"][prior]["digest"]}
    return command(engine, world, state, "criterion.evidence.bind", {**payload, **changes})


@pytest.mark.parametrize("kind", ["quality_observation", "consumer-check"])
def test_corrected_attempt_routes_declared_slot_without_changing_contract(engine, world, kind):
    state, path = _repairable_observer_run(engine, world, kind)
    failed = deepcopy(state["observations"]["review-slot"])
    contract_digest, profile_digest = state["contract_digest"], state["profile_digest"]
    path.write_text("Corrected\n")
    state = command(engine, world, state, "artifact.register", {"id": "output", "path": str(path), "role": "output", "retention": "durable", "required": True})
    state = command(engine, world, state, "observe:" + kind, {"check_id": "output"}, command_id="review-attempt-2")
    state = _bind_review(engine, world, state, "review-attempt-2")
    assert state["contract_digest"] == contract_digest and state["profile_digest"] == profile_digest
    assert state["observations"]["review-slot"] == failed
    assert state["evidence"]["review-slot"]["digest"] == failed["digest"]
    assert state["criterion_evidence_bindings"]["accept"]["review-slot"]["receipt_id"] == "review-attempt-2"
    state = command(engine, world, state, "transition", {"status": "verifying"})
    state = command(engine, world, state, "verify", {"criteria": ["accept"]})
    bound = state["verification"]["accept"]["binding"]
    assert bound["evidence_bindings"]["review-slot"] == {"receipt_id": "review-attempt-2", "digest": state["evidence"]["review-attempt-2"]["digest"]}
    assert engine.completion_report(world["project"], state["run_id"], actor=world["actor"])["status"] == "PASS"


@pytest.mark.parametrize("change", [{"slot": "undeclared"}, {"criterion_id": "other"},
    {"expected_prior_receipt_id": "other"}, {"expected_prior_digest": "0" * 64}, {"receipt_id": "absent"}])
def test_evidence_routing_rejects_wrong_slot_identity_or_cas(engine, world, change):
    state, _ = _repairable_observer_run(engine, world)
    with pytest.raises(ValueError):
        _bind_review(engine, world, state, "review-slot", **change)
    assert engine.load_run(world["project"], state["run_id"]) == state


@pytest.mark.parametrize("kind", ["authority", "contract-amendment", "profile-amendment", "effect-authorization"])
def test_observation_binding_cannot_route_authority_receipts(engine, world, kind):
    state, _ = _repairable_observer_run(engine, world, kind)
    with pytest.raises(ValueError):
        _bind_review(engine, world, state, "review-slot")


def test_routing_revalidates_current_artifact_and_invalidates_verification(engine, world):
    state, path = _repairable_observer_run(engine, world)
    state = _bind_review(engine, world, state, "review-slot")
    path.write_text("Changed outside the reviewed snapshot\n")
    with pytest.raises(ValueError):
        _bind_review(engine, world, state, "review-slot")


def test_core_observation_cannot_overwrite_registered_evidence_attempt(engine, world):
    state = receipt(engine, world, create(engine, world), "consumer-check")
    engine.register_observer("consumer-check", lambda context, payload: {"fixture": True})
    with pytest.raises(ValueError):
        command(engine, world, state, "observe:consumer-check", {"check_id": "consumer-check"}, command_id="consumer-check")


def test_external_receipt_cannot_overwrite_an_attempt_identity(engine, world):
    state = receipt(engine, world, create(engine, world), "consumer-check")
    with pytest.raises(ValueError):
        command(engine, world, state, "evidence.record", {"id": "consumer-check", "kind": "consumer-check", "artifact_id": "consumer-check"})


def test_profile_amendment_clears_current_evidence_routing(engine, world):
    state, _ = _repairable_observer_run(engine, world)
    state = _bind_review(engine, world, state, "review-slot")
    profile = deepcopy(state["profile"])
    profile["items"].append({"id": "additional", "required": True, "criterion_ids": ["accept"]})
    state = command(engine, world, state, "profile.amend", {"profile": profile})
    assert state.get("criterion_evidence_bindings", {}) == {}
    assert "review-slot" in state["observations"]


@pytest.mark.parametrize('missing',[False,True])
def test_command_keeps_exact_authority_fences_without_redundant_existing_lock_admission(engine,world,monkeypatch,missing):
    from contextlib import contextmanager
    state=create(engine,world)
    lock=world['project']/'resources/autopilot-runs'/state['run_id']/'.run.lock'
    if missing:lock.unlink()
    native_binding=engine._binding;native_lock=engine.bounded_lock;calls=[];held=[];modes=[]
    def observed_binding(*args,**kwargs):
        calls.append(bool(held));return native_binding(*args,**kwargs)
    @contextmanager
    def observed_lock(path,**kwargs):
        if path==lock:modes.append(kwargs.get('create',True))
        with native_lock(path,**kwargs):
            if path==lock:held.append(True)
            try:yield
            finally:
                if path==lock:held.pop()
    monkeypatch.setattr(engine,'_binding',observed_binding)
    monkeypatch.setattr(engine,'bounded_lock',observed_lock)
    command(engine,world,state,'progress',{'summary':'Observed authority fences'})
    assert calls==([False,True,True] if missing else [True,True])
    assert modes==[missing]


def test_existing_lock_disappearing_never_retries_creation(engine,world,monkeypatch):
    from contextlib import contextmanager
    state=create(engine,world)
    lock=world['project']/'resources/autopilot-runs'/state['run_id']/'.run.lock'
    original=engine.bounded_lock
    @contextmanager
    def disappear(path,**kwargs):
        if path==lock:lock.unlink()
        with original(path,**kwargs):yield
    monkeypatch.setattr(engine,'bounded_lock',disappear)
    with pytest.raises(ValueError):command(engine,world,state,'progress',{'summary':'Must not commit'})
    assert not lock.exists()
    assert engine.load_run(world['project'],state['run_id'])['revision']==state['revision']


def test_lock_wait_revalidates_revoked_authority_before_mutations(engine,world,monkeypatch):
    from contextlib import contextmanager
    import fcntl,threading
    state=create(engine,world)
    home=world['project']/'resources/autopilot-runs'/state['run_id'];lock=home/'.run.lock'
    def inventory():
        return {str(p):p.read_bytes() for root in (home,world['runtime']) for p in root.rglob('*') if p.is_file()}
    before=inventory();entered=threading.Event();original=engine.bounded_lock
    @contextmanager
    def waiting(path,**kwargs):
        if path==lock:entered.set()
        with original(path,**kwargs):yield
    monkeypatch.setattr(engine,'bounded_lock',waiting)
    with lock.open('r') as holder:
        fcntl.flock(holder.fileno(),fcntl.LOCK_EX)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(command,engine,world,state,'progress',{'summary':'Must not commit'})
            assert entered.wait(5)
            write_board(world,status='released')
            fcntl.flock(holder.fileno(),fcntl.LOCK_UN)
            with pytest.raises(ValueError):pending.result(timeout=10)
    assert inventory()==before


def test_reducer_revocation_keeps_event_projection_and_index_unchanged(engine,world):
    state=create(engine,world)
    home=world['project']/'resources/autopilot-runs'/state['run_id']
    def inventory():
        return {str(p):p.read_bytes() for root in (home,world['runtime']) for p in root.rglob('*') if p.is_file()}
    before=inventory()
    def revoke(state,payload,context):
        write_board(world,status='released');state['extensions']['synthetic']='uncommitted';return state
    engine.register_command('fixture-revoke',revoke)
    with pytest.raises(ValueError):command(engine,world,state,'fixture-revoke',{})
    assert inventory()==before


def test_replayed_command_still_readmits_inside_existing_lock(engine,world,monkeypatch):
    state=create(engine,world)
    result=command(engine,world,state,'progress',{'summary':'Once'},command_id='once')
    original=engine._binding;calls=[]
    def observed(*args,**kwargs):calls.append(True);return original(*args,**kwargs)
    monkeypatch.setattr(engine,'_binding',observed)
    assert command(engine,world,state,'progress',{'summary':'Once'},command_id='once')==result
    assert len(calls)==1
    write_board(world,status='released')
    with pytest.raises(ValueError):command(engine,world,state,'progress',{'summary':'Once'},command_id='once')
