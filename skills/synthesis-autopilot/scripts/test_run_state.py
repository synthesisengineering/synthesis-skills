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
    for name in ("_COMMANDS", "_VERIFIERS", "_CONSTRAINTS", "_EVIDENCE_SOURCES"):
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


def receipt(engine, world, state, kind, data=None):
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
    return command(engine, world, state, "evidence.record", {"id": kind, "kind": kind, "artifact_id": kind})


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
