"""Native capability, continuation and recovery contracts (no live services)."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import importlib.util
import sys
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "autopilot_capabilities", Path(__file__).with_name("capabilities.py"))
assert SPEC and SPEC.loader
CAP = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CAP
SPEC.loader.exec_module(CAP)

NOW = 2000000000
BINDING = {"project_id": "fixture", "project_root": "/fixture/project",
           "native_ref": "codex:native-1", "session_uuid": "seat-1",
           "claim_hash": "b" * 64, "repository": "/fixture/repo", "branch": "main"}


def state():
    return {"run_id": "run-1", "revision": 3, "status": "active", "extensions": {}}


def receipt(kind, **claims):
    observed = claims.pop("observed_at", NOW - 5)
    expires = claims.pop("expires_at", NOW + 300)
    return {"kind": kind, "bindings": {"run_id": "run-1", **BINDING},
            "artifact_id": "artifact-proof", "digest": "a" * 64,
            "observed_at": datetime.fromtimestamp(observed, timezone.utc).isoformat(),
            "expires_at": datetime.fromtimestamp(expires, timezone.utc).isoformat(),
            "data": claims}


def context(receipts=None, **updates):
    records = receipts or {}

    def verify(ref, kind, bindings):
        # The production bridge supplies verified, content-bound receipts.
        # Payload fields never become that trusted bridge.
        if ref not in records:
            raise ValueError("receipt unavailable")
        found = records[ref]
        assert kind == found["kind"]
        assert all(found["bindings"].get(k) == v for k, v in bindings.items())
        return True

    result = {"now": NOW, "binding": dict(BINDING), "verify_receipt": verify,
              "evidence": records, **updates}
    result["now"] = datetime.fromtimestamp(result["now"], timezone.utc).isoformat()
    return result


def capability_receipt(surface="codex-desktop", **updates):
    return receipt("capability", surface=surface, capabilities={
        "native_identity": True, "registration_readback": True,
        "wake_observation": True, "cancellation_readback": True,
        "independent_observer": True, "terminal_precedence": True,
        "survival": ["turn_end"], "mechanisms": ["codex-heartbeat"],
    }, **updates)


def configured():
    records = {"cap": capability_receipt(), "registered": receipt(
        "continuation-registration", surface="codex-desktop", job_id="job-1",
        mechanism="codex-heartbeat", next_wake_at=NOW + 30,
        lease_expires_at=NOW + 200, observer_id="observer-1", owner="native-host")}
    ctx = context(records)
    initial = CAP.record_capability(state(), {"surface": "codex-desktop", "receipt": "cap"}, ctx)
    registered = CAP.register_continuation(initial, {"receipt": "registered", "horizon": "turn_end"}, ctx)
    return registered, records, ctx


def renewal_fixture():
    current, records, _ = configured()
    records['cap']['expires_at'] = datetime.fromtimestamp(NOW + 1000, timezone.utc).isoformat()
    records['registered']['expires_at'] = datetime.fromtimestamp(NOW + 1000, timezone.utc).isoformat()
    records['renew'] = receipt('continuation-renewal', observed_at=NOW + 10, expires_at=NOW + 1000,
        surface='codex-desktop', job_id='job-1', mechanism='codex-heartbeat',
        owner='native-host', observer_id='observer-1', lease_expires_at=NOW + 310,
        readback_at=NOW + 10, registration_receipt='registered', previous_lease_receipt='registered')
    return current, records, context(records, now=NOW + 10)


def test_renewal_preserves_actual_wakes_and_next_deadline_without_claiming_a_wake():
    current, records, ctx = renewal_fixture()
    prior = copy.deepcopy(current['extensions']['capabilities']['continuation'])
    renewed = CAP.renew_continuation(current, {'receipt': 'renew'}, ctx)
    job = renewed['extensions']['capabilities']['continuation']
    assert job['lease_expires_at'] == NOW + 310
    assert job['lease_receipt'] == 'renew'
    for key in ('registered_at', 'registration_receipt', 'next_wake_at', 'wakes', 'status', 'binding'):
        assert job[key] == prior[key]
    assert CAP.continuation_status(renewed, ctx)['continuation_verified'] is False
    records['wake-renewed'] = receipt('continuation-wake', observed_at=NOW + 15,
        job_id='job-1', event_id='later', native_observed_at=NOW + 15, next_wake_at=NOW + 90,
        source={'lease_receipt': 'renew'})
    renewed = CAP.observe_wake(renewed, {'receipt': 'wake-renewed'}, context(records, now=NOW + 16))
    assert len(renewed['extensions']['capabilities']['continuation']['wakes']) == 1
    assert CAP.renew_continuation(renewed, {'receipt': 'renew'}, context(records, now=NOW + 17)) == renewed


@pytest.mark.parametrize('fault', ['expired', 'overdue', 'cancelled', 'cancellation_pending', 'terminal',
    'owner', 'job_id', 'observer_id', 'mechanism', 'surface', 'previous', 'registration', 'ttl',
    'capability_expiry', 'registration_expiry', 'no_extension', 'future_readback', 'foreign_binding'])
def test_renewal_cannot_reset_or_weaken_current_authority_or_lease(fault):
    current, records, ctx = renewal_fixture()
    data = records['renew']['data']; job = current['extensions']['capabilities']['continuation']
    if fault == 'expired': ctx = context(records, now=NOW + 200)
    elif fault == 'overdue': ctx = context(records, now=NOW + 61)
    elif fault in {'cancelled', 'cancellation_pending'}: job['status'] = fault
    elif fault == 'terminal': current['status'] = 'cancelled'
    elif fault in {'owner', 'job_id', 'observer_id', 'mechanism', 'surface'}: data[fault] = 'foreign'
    elif fault == 'previous': data['previous_lease_receipt'] = 'another'
    elif fault == 'registration': data['registration_receipt'] = 'another'
    elif fault == 'ttl': data['lease_expires_at'] = NOW + 311
    elif fault == 'capability_expiry': records['cap']['expires_at'] = datetime.fromtimestamp(NOW + 250, timezone.utc).isoformat()
    elif fault == 'registration_expiry': records['registered']['expires_at'] = datetime.fromtimestamp(NOW + 250, timezone.utc).isoformat()
    elif fault == 'no_extension': data['lease_expires_at'] = NOW + 200
    elif fault == 'future_readback': data['readback_at'] = NOW + 11
    elif fault == 'foreign_binding': ctx['binding']['native_ref'] = 'foreign'
    before = copy.deepcopy(current)
    with pytest.raises(ValueError): CAP.renew_continuation(current, {'receipt': 'renew'}, ctx)
    assert current == before


def test_renewed_job_rejects_wake_bound_to_superseded_lease_and_keeps_duplicates_idempotent():
    current, records, ctx = renewal_fixture()
    current = CAP.renew_continuation(current, {'receipt': 'renew'}, ctx)
    records['wake'] = receipt('continuation-wake', observed_at=NOW + 15, job_id='job-1',
        event_id='event-1', native_observed_at=NOW + 15, next_wake_at=NOW + 90,
        source={'lease_receipt': 'registered'})
    with pytest.raises(ValueError): CAP.observe_wake(current, {'receipt': 'wake'}, context(records, now=NOW + 16))
    records['wake']['data']['source']['lease_receipt'] = 'renew'
    current = CAP.observe_wake(current, {'receipt': 'wake'}, context(records, now=NOW + 16))
    assert CAP.observe_wake(current, {'receipt': 'wake'}, context(records, now=NOW + 17)) == current
    records['late'] = receipt('continuation-wake', observed_at=NOW + 18, job_id='job-1',
        event_id='event-older', native_observed_at=NOW + 14, next_wake_at=NOW + 80,
        source={'lease_receipt': 'renew'})
    with pytest.raises(ValueError): CAP.observe_wake(current, {'receipt': 'late'}, context(records, now=NOW + 18))


def test_renewal_cannot_outlive_its_previous_renewal_receipt():
    current, records, ctx = renewal_fixture()
    records['renew']['expires_at'] = datetime.fromtimestamp(NOW + 315, timezone.utc).isoformat()
    current = CAP.renew_continuation(current, {'receipt': 'renew'}, ctx)
    records['renew-again'] = receipt('continuation-renewal', observed_at=NOW + 20, expires_at=NOW + 1000,
        surface='codex-desktop', job_id='job-1', mechanism='codex-heartbeat', owner='native-host',
        observer_id='observer-1', lease_expires_at=NOW + 320, readback_at=NOW + 20,
        registration_receipt='registered', previous_lease_receipt='renew')
    with pytest.raises(ValueError):
        CAP.renew_continuation(current, {'receipt': 'renew-again'}, context(records, now=NOW + 20))


def test_registry_separates_native_portability_and_prospective_support():
    registry = CAP.supported_surfaces()
    assert registry["schema_version"] == 1
    surfaces = registry["surfaces"]
    assert surfaces["muse-cli"]["level"] == "native"
    assert surfaces["cursor-ide"]["level"] == "skill-only"
    assert surfaces["copilot-cli"]["level"] == "skill-only"
    assert surfaces["hermes"]["level"] == "prospective"
    surfaces["muse-cli"]["level"] = "mutated"
    assert CAP.supported_surfaces()["surfaces"]["muse-cli"]["level"] == "native"


@pytest.mark.parametrize("surface", ["claude-code-cli", "codex-cli", "codex-desktop", "muse-cli"])
def test_native_repeat_signal_and_terminal_override(surface):
    payload = {"hook_event_name": "Stop", "session_id": "native-1",
               "stop_hook_active": False, "turn_id": "turn-1"}
    normalized = CAP.normalize_event(surface, payload)
    assert normalized["session_id"] == "native-1"
    assert normalized["repeat_count"] == 0
    assert CAP.stop_response(surface, payload, "unfinished")["continue"] is False
    payload["stop_hook_active"] = True
    terminal = CAP.stop_response(surface, payload, "unfinished")
    assert terminal["continue"] is False
    assert terminal.get("decision") != "block"
    assert terminal["systemMessage"].startswith("UNRESOLVED:")


def test_cursor_uses_its_native_contract_and_has_no_terminal_override_claim():
    payload = {"conversation_id": "cursor-1", "generation_id": "generation-1",
               "status": "completed", "loop_count": 0}
    assert CAP.stop_response("cursor-ide", payload, "unfinished") == {}
    payload["loop_count"] = 1
    assert CAP.stop_response("cursor-ide", payload, "unfinished") == {}
    payload["loop_count"] = 0
    payload["status"] = "aborted"
    assert CAP.stop_response("cursor-ide", payload, "unfinished") == {}
    assert not CAP.supported_surfaces()["surfaces"]["cursor-ide"]["terminal_precedence"]


def test_copilot_normalizes_both_event_spellings_without_unsupported_output():
    for payload in [{"sessionId": "copilot-1", "stop_hook_active": False},
                    {"session_id": "copilot-1", "hook_event_name": "Stop", "stop_hook_active": False}]:
        assert CAP.normalize_event("copilot-cli", payload)["session_id"] == "copilot-1"
        assert CAP.stop_response("copilot-cli", payload, "unfinished") == {"decision": "allow"}
        payload["stop_hook_active"] = True
        assert CAP.stop_response("copilot-cli", payload, "unfinished") == {"decision": "allow"}


@pytest.mark.parametrize("payload", [None, {}, {"session_id": "x", "hook_event_name": "Stop", "stop_hook_active": "false"}])
def test_malformed_native_identity_never_creates_a_corrective_turn(payload):
    result = CAP.stop_response("codex-cli", payload, "unverified")
    assert result["continue"] is False
    assert result.get("decision") != "block"


def test_fresh_wake_cannot_reset_an_unauthenticated_retry():
    base = {"session_id": "same", "hook_event_name": "Stop", "stop_hook_active": True, "turn_id": "t1"}
    assert CAP.stop_response("codex-cli", base, "unfinished")["continue"] is False
    fresh = {**base, "stop_hook_active": False, "turn_id": "t2"}
    assert CAP.stop_response("codex-cli", fresh, "unfinished")["continue"] is False


def test_missing_receipt_cannot_self_attest_capability():
    with pytest.raises(ValueError):
        CAP.record_capability(state(), {"surface": "codex-desktop", "receipt": "invented", "verified": True}, context())


def test_observation_must_match_surface_and_not_be_expired_or_future():
    for claims in [{"surface": "codex-cli"}, {"expires_at": NOW}, {"observed_at": NOW + 1}]:
        records = {"bad": capability_receipt(**claims)}
        with pytest.raises(ValueError):
            CAP.record_capability(state(), {"surface": "codex-desktop", "receipt": "bad"}, context(records))


def test_in_session_is_not_unattended_and_unknown_horizon_is_refused():
    assert CAP.admission(state(), "codex-cli", "in_session", context())["admitted"]
    assert not CAP.admission(state(), "codex-cli", "turn_end", context())["admitted"]
    with pytest.raises(ValueError):
        CAP.admission(state(), "codex-cli", "forever", context())


def test_verified_native_registration_does_not_fabricate_first_wake():
    current, _, ctx = configured()
    job = current["extensions"]["capabilities"]["continuation"]
    assert job["status"] == "registered"
    assert job["wakes"] == []
    assert CAP.continuation_status(current, ctx)["state"] == "awaiting_first_wake"
    assert CAP.admission(current, "codex-desktop", "turn_end", ctx)["admitted"]
    assert not CAP.admission(current, "codex-desktop", "app_exit", ctx)["admitted"]


def test_unattended_requires_independent_observer_and_cancellation_readback():
    for missing in ["independent_observer", "cancellation_readback", "native_identity"]:
        evidence = capability_receipt()
        evidence["data"]["capabilities"][missing] = False
        ctx = context({"cap": evidence})
        current = CAP.record_capability(state(), {"surface": "codex-desktop", "receipt": "cap"}, ctx)
        assert not CAP.admission(current, "codex-desktop", "turn_end", ctx)["admitted"]


def test_registration_cannot_replace_an_active_continuation_owner():
    current, records, ctx = configured()
    records["second"] = copy.deepcopy(records["registered"])
    records["second"]["data"]["job_id"] = "job-2"
    with pytest.raises(ValueError):
        CAP.register_continuation(current, {"receipt": "second", "horizon": "turn_end"}, ctx)


def test_observed_wakes_are_deduplicated_and_not_replayed_after_close():
    current, records, _ = configured()
    records["wake"] = receipt("continuation-wake", job_id="job-1", event_id="wake-1",
                              observed_at=NOW + 30, next_wake_at=NOW + 60)
    ctx = context(records, now=NOW + 31)
    observed = CAP.observe_wake(current, {"receipt": "wake"}, ctx)
    repeated = CAP.observe_wake(observed, {"receipt": "wake"}, ctx)
    assert repeated == observed
    assert len(observed["extensions"]["capabilities"]["continuation"]["wakes"]) == 1
    observed["status"] = "closed"
    records["late"] = copy.deepcopy(records["wake"])
    records["late"]["data"]["event_id"] = "wake-2"
    late = CAP.observe_wake(observed, {"receipt": "late"}, ctx)
    assert late["status"] == "closed"
    assert CAP.continuation_status(late, ctx)["state"] == "closed"
    assert late["extensions"]["capabilities"]["ignored_wakes"][-1]["reason"] == "run_closed"


def test_missed_wake_and_expiry_do_not_report_healthy_continuation():
    current, _, _ = configured()
    assert CAP.continuation_status(current, context(now=NOW + 61))["state"] == "overdue"
    assert CAP.continuation_status(current, context(now=NOW + 201))["state"] == "expired"


def test_revoked_claim_blocks_wake_without_reassigning_ownership():
    current, records, _ = configured()
    records["wake"] = receipt("continuation-wake", job_id="job-1", event_id="wake-1", next_wake_at=NOW + 60)
    ctx = context(records, binding={**BINDING, "claim_hash": "c" * 64})
    with pytest.raises(ValueError):
        CAP.observe_wake(current, {"receipt": "wake"}, ctx)


def test_cancel_requested_is_not_cancelled_until_native_readback():
    current, records, ctx = configured()
    requested = CAP.request_cancel(current, {"reason": "principal stopped the run"}, ctx)
    assert CAP.continuation_status(requested, ctx)["state"] == "cancellation_pending"
    records["cancelled"] = receipt("continuation-cancellation", job_id="job-1", cancelled=True, observed_at=NOW)
    done = CAP.confirm_cancel(requested, {"receipt": "cancelled"}, ctx)
    assert CAP.continuation_status(done, ctx)["state"] == "cancelled"
    records["late"] = receipt("continuation-wake", job_id="job-1", event_id="wake-late", next_wake_at=NOW + 60)
    late = CAP.observe_wake(done, {"receipt": "late"}, ctx)
    assert CAP.continuation_status(late, ctx)["state"] == "cancelled"
    assert late["extensions"]["capabilities"]["ignored_wakes"][-1]["reason"] == "cancelled"


def test_cancel_failure_remains_actionable_not_confirmed():
    current, records, ctx = configured()
    current = CAP.request_cancel(current, {"reason": "stop"}, ctx)
    records["failed"] = receipt("continuation-cancellation", job_id="job-1", cancelled=False, observed_at=NOW)
    current = CAP.confirm_cancel(current, {"receipt": "failed"}, ctx)
    assert CAP.continuation_status(current, ctx)["state"] == "cancellation_failed"


def test_recovery_capsule_requires_current_resolver_native_claim_and_run_revision():
    records = {"recovery": receipt("recovery", run_revision=3, resolver_receipt="resolver-1",
                                   native_receipt="native-proof", claim_receipt="claim-proof",
                                   remaining=["deliverable-2"], input_receipts=["input-1"]),
               "resolver-1": receipt("project-resolution"), "native-proof": receipt("native-identity"),
               "claim-proof": receipt("claim-ownership"), "input-1": receipt("working-input")}
    current = CAP.record_recovery(state(), {"receipt": "recovery"}, context(records))
    capsule = current["extensions"]["capabilities"]["recovery"]
    assert capsule["remaining"] == ["deliverable-2"]
    records["recovery"]["data"]["run_revision"] = 2
    with pytest.raises(ValueError):
        CAP.record_recovery(state(), {"receipt": "recovery"}, context(records))


def test_invalid_event_is_not_reported_healthy_when_diagnostic_is_omitted():
    assert CAP.stop_response("codex-cli", {})["continue"] is False
    assert CAP.stop_response("cursor-ide", {}) == {}


def test_registration_facility_must_be_observed_not_just_statically_known():
    current, records, ctx = configured()
    del current["extensions"]["capabilities"]["continuation"]
    records["registered"]["data"]["mechanism"] = "codex-automation"
    with pytest.raises(ValueError):
        CAP.register_continuation(current, {"receipt": "registered", "horizon": "turn_end"}, ctx)


def test_recovery_rejects_missing_or_stale_component_receipt():
    records = {"recovery": receipt("recovery", run_revision=3, resolver_receipt="absent",
                                   native_receipt="absent", claim_receipt="absent",
                                   remaining=[], input_receipts=[])}
    with pytest.raises(ValueError):
        CAP.record_recovery(state(), {"receipt": "recovery"}, context(records))


def test_cancellation_readback_before_request_is_not_confirmation():
    current, records, ctx = configured()
    current = CAP.request_cancel(current, {"reason": "stop"}, ctx)
    records["stale"] = receipt("continuation-cancellation", job_id="job-1", cancelled=True)
    with pytest.raises(ValueError):
        CAP.confirm_cancel(current, {"receipt": "stale"}, ctx)


def test_recovery_summary_is_unknown_after_a_later_revision():
    current = state()
    current["revision"] = 8
    current["extensions"] = {"capabilities": {"recovery": {
        "run_revision": 3, "recorded_revision": 4, "remaining": ["old"], "receipt": "old"}}}
    assert CAP.status_view(current, context())["remaining"] is None
    assert CAP.status_view(current, context())["recovery_status"] == "unverified"


def test_capability_evidence_expiry_cannot_leave_continuation_verified():
    current, _, ctx = configured()
    future = {**ctx, "now": datetime.fromtimestamp(NOW + 301, timezone.utc).isoformat()}
    assert not CAP.admission(current, "codex-desktop", "turn_end", future)["admitted"]


def test_late_wake_from_retired_job_cannot_change_new_owner_deadline():
    current, records, ctx = configured()
    current = CAP.request_cancel(current, {"reason": "replace completed schedule"}, ctx)
    records["cancelled"] = receipt("continuation-cancellation", job_id="job-1", cancelled=True, observed_at=NOW)
    current = CAP.confirm_cancel(current, {"receipt": "cancelled"}, ctx)
    records["replacement"] = copy.deepcopy(records["registered"])
    records["replacement"]["data"]["job_id"] = "job-2"
    current = CAP.register_continuation(current, {"receipt": "replacement", "horizon": "turn_end"}, ctx)
    records["late"] = receipt("continuation-wake", job_id="job-1", event_id="late-old", next_wake_at=NOW + 80)
    after = CAP.observe_wake(current, {"receipt": "late"}, ctx)
    assert after["extensions"]["capabilities"]["continuation"] == current["extensions"]["capabilities"]["continuation"]
    assert after["extensions"]["capabilities"]["ignored_wakes"][-1]["reason"] == "retired_job"


def test_cursor_non_stop_payload_cannot_request_followup():
    payload = {"hook_event_name": "preToolUse", "conversation_id": "c", "generation_id": "g",
               "loop_count": 0, "status": "completed"}
    assert CAP.stop_response("cursor-ide", payload, "unfinished") == {}


def test_non_git_project_can_use_authenticated_receipts():
    binding = {**BINDING, "repository": None, "branch": None}
    evidence = capability_receipt()
    evidence["bindings"].update(binding)
    ctx = context({"cap": evidence}, binding=binding)
    current = CAP.record_capability(state(), {"surface": "codex-desktop", "receipt": "cap"}, ctx)
    assert CAP.admission(current, "codex-desktop", "turn_end", ctx)["admitted"]


def test_delivery_does_not_confuse_queued_with_received_and_preserves_mute():
    records = {"queue": receipt("delivery", delivery_id="delivery-1", channel="host-ui", status="queued"),
               "received": receipt("delivery", delivery_id="delivery-1", channel="host-ui", status="delivered")}
    current = CAP.record_delivery(state(), {"receipt": "queue"}, context(records))
    assert CAP.status_view(current, context())["deliveries"][0]["status"] == "queued"
    current = CAP.record_delivery(current, {"receipt": "received"}, context(records))
    assert CAP.status_view(current, context())["deliveries"][0]["status"] == "delivered"
    intent = CAP.alert_intent(current, {"ui_available": False, "user_blocker": True, "muted": True})
    assert intent["audio"] is False
    assert intent["independent_alert_required"] is True
    assert "fixture" not in intent["public_message"]


def test_reducers_are_pure_and_registered_with_bounded_payload_fields():
    before = state()
    ctx = context({"cap": capability_receipt()})
    after = CAP.record_capability(before, {"surface": "codex-desktop", "receipt": "cap"}, ctx)
    assert before == state()
    assert after != before
    registrations = {}
    CAP.register_commands(lambda name, reducer, *, allowed_fields, terminal_safe=False:
        registrations.update({name: (reducer, allowed_fields, terminal_safe)}))
    assert {"capability.record", "continuation.register", "continuation.wake", "continuation.cancel",
            "continuation.cancel-confirm", "recovery.record", "delivery.record"} <= set(registrations)
    assert registrations["capability.record"][1] == ("extensions",)
    assert registrations["continuation.cancel-confirm"][2] is True
    assert registrations["continuation.register"][2] is False


def test_terminal_status_retains_pending_native_cleanup():
    current, _, ctx = configured()
    current = CAP.request_cancel(current, {"reason": "stop"}, ctx)
    current["status"] = "incomplete"
    status = CAP.continuation_status(current, ctx)
    assert status["state"] == "closed"
    assert status["cleanup_required"] is True
    assert status["cleanup_state"] == "cancellation_pending"


def test_close_constraint_requires_only_explicit_capability_criteria():
    current, _, ctx = configured()
    current["contract"] = {"criteria": [{"id": "output", "method": "artifact", "required": True}]}
    current["status"] = "completed"
    CAP.validate_command(current, "close", {"status": "completed"}, ctx)
    current["contract"]["criteria"].append({"id": "wake", "method": "continuation-wake",
                                              "required": True, "evidence_ids": ["missing"]})
    with pytest.raises(ValueError):
        CAP.validate_command(current, "close", {"status": "completed"}, ctx)
    CAP.validate_command(current, "close", {"status": "cancelled"}, ctx)


def waiting_state():
    current = state()
    current["status"] = "waiting_user"
    current["waits"] = {"review": {"id": "review", "kind": "user", "status": "pending", "reason": "Review output", "at": "2033-05-18T03:33:00+00:00"}}
    return current


def test_wait_delivery_requires_current_wait_binding_and_fresh_source():
    current = waiting_state()
    binding = CAP.wait_binding(current)
    records = {"notice": receipt("delivery", delivery_id="notice-1", channel="host-ui", status="delivered", **binding)}
    current = CAP.record_delivery(current, {"receipt": "notice"}, context(records))
    assert CAP.wait_delivery_status(current, context(records))["delivered"]
    assert not CAP.wait_delivery_status(current, context({}))["delivered"]
    records["notice"]["expires_at"] = datetime.fromtimestamp(NOW - 1, timezone.utc).isoformat()
    assert not CAP.wait_delivery_status(current, context(records))["delivered"]


def test_old_notification_cannot_silence_new_or_changed_unresolved_waits():
    current = waiting_state()
    binding = CAP.wait_binding(current)
    records = {"notice": receipt("delivery", delivery_id="notice-1", channel="host-ui", status="delivered", **binding)}
    current = CAP.record_delivery(current, {"receipt": "notice"}, context(records))
    current["waits"]["review"]["reason"] = "Review changed output"
    assert not CAP.wait_delivery_status(current, context(records))["delivered"]
    current = waiting_state()
    current = CAP.record_delivery(current, {"receipt": "notice"}, context(records))
    current["waits"]["approval"] = {"id": "approval", "kind": "user", "status": "pending", "reason": "Approve deployment"}
    assert not CAP.wait_delivery_status(current, context(records))["delivered"]


def test_unbound_or_queued_delivery_is_not_current_wait_notification():
    current = waiting_state()
    for data in ({}, CAP.wait_binding(current)):
        records = {"notice": receipt("delivery", delivery_id="notice-1", channel="host-ui", status="queued", **data)}
        recorded = CAP.record_delivery(current, {"receipt": "notice"}, context(records))
        assert not CAP.wait_delivery_status(recorded, context(records))["delivered"]
    records = {"notice": receipt("delivery", delivery_id="notice-1", channel="host-ui", status="delivered")}
    recorded = CAP.record_delivery(current, {"receipt": "notice"}, context(records))
    assert not CAP.wait_delivery_status(recorded, context(records))["delivered"]
    assert not CAP.wait_delivery_status(state(), context(records))["delivered"]


def test_delivery_refuses_partial_or_mismatched_wait_bindings():
    current = waiting_state()
    binding = CAP.wait_binding(current)
    for changes in ({"wait_ids": []}, {"wait_digest": "f" * 64}, {"run_revision": current["revision"] + 1}):
        records = {"notice": receipt("delivery", delivery_id="notice-1", channel="host-ui", status="delivered", **{**binding, **changes})}
        with pytest.raises(ValueError):
            CAP.record_delivery(current, {"receipt": "notice"}, context(records))


def test_required_horizon_closure_needs_matching_observed_job_not_a_label():
    current, records, _ = configured()
    with pytest.raises(ValueError):
        CAP.validate_horizon(current, "reboot", context(records))
    job = current["extensions"]["capabilities"]["continuation"]
    records["cap"]["data"]["capabilities"]["survival"].append("reboot")
    job["horizon"] = "reboot"
    with pytest.raises(ValueError):
        CAP.validate_horizon(current, "reboot", context(records))
    records["wake"] = receipt("continuation-wake", job_id="job-1", event_id="wake-1", observed_at=NOW + 30, next_wake_at=NOW + 60)
    current = CAP.observe_wake(current, {"receipt": "wake"}, context(records, now=NOW + 31))
    current["status"] = "completed"
    CAP.validate_horizon(current, "reboot", context(records, now=NOW + 31))
    records.pop("wake")
    with pytest.raises(ValueError):
        CAP.validate_horizon(current, "reboot", context(records, now=NOW + 31))


def test_explain_keeps_worker_operations_distinct_from_root_support():
    import json, subprocess
    command=[sys.executable,str(Path(__file__).with_name('autopilot.py')),'explain']
    rows=json.loads(subprocess.run(command,capture_output=True,text=True,check=True).stdout)['surfaces']
    for surface in ('claude-code-cli','codex-cli'):
        worker=rows[surface]['native_worker']
        assert set(worker['operations'])=={'read','write','edit','shell'}
        assert worker['write_enforcement']!='ENFORCED'
    muse=rows['muse-cli']
    assert muse['level']=='native'
    assert 'shell' not in muse['native_worker']['operations']
    assert muse['native_worker']['write_enforcement']!='ENFORCED'
    assert rows['cursor-cli']['native_worker']['status']=='UNAVAILABLE'
    selected=json.loads(subprocess.run(command+['--surface','muse-cli'],capture_output=True,text=True,check=True).stdout)
    assert selected['native_worker']==muse['native_worker']


@pytest.mark.parametrize("repeat", [False, True])
def test_translator_preserves_reserved_policy_correction_independent_of_repeat_bit(repeat):
    # This is an internal owner-to-launcher envelope. The separate launcher
    # acceptance proves a shaped assertion cannot substitute for its journal.
    proof = {"schema_version": 1, "run_id": "fixture", "correction_id": "a" * 64}
    disposition = {"action": "corrective", "allow_attempt": True, "authority_granted": False,
                   "completion_granted": False, "reservation": proof}
    result = CAP.stop_response("codex-cli", {"hook_event_name": "Stop", "session_id": "native",
        "stop_hook_active": repeat}, "Productive work remains", policy_disposition=disposition)
    assert result["decision"] == "block" and result["_synthesis_policy"] == proof
    denied = CAP.stop_response("codex-cli", {"hook_event_name": "Stop", "session_id": "native",
        "stop_hook_active": repeat}, "Cancelled", policy_disposition={**disposition, "action": "terminal"})
    assert denied["continue"] is False and "_synthesis_policy" not in denied


def test_late_scheduler_wake_cannot_reinject_unverified_policy_or_erase_cancel():
    current, records, ctx = configured()
    current['extensions']['workflow_persistence'] = {'decisions': {'missing-owner': {'allow_attempt': True}}}
    records['late'] = receipt('continuation-wake', job_id='job-1', event_id='late-after-policy',
        native_observed_at=NOW, next_wake_at=NOW + 60)
    current = CAP.observe_wake(current, {'receipt': 'late'}, context(records))
    assert current['extensions']['capabilities']['continuation']['wakes'] == []
    assert current['extensions']['capabilities']['ignored_wakes'][-1]['reason'] == 'policy_wait'
    status = CAP.continuation_status(current, context(records))
    assert status['state'] == 'policy_wait' and status['cleanup_required']
    current = CAP.request_cancel(current, {'reason': 'No admitted continuation'}, context(records))
    records['late2'] = receipt('continuation-wake', job_id='job-1', event_id='late-after-cancel',
        native_observed_at=NOW, next_wake_at=NOW + 60)
    current = CAP.observe_wake(current, {'receipt': 'late2'}, context(records))
    assert current['extensions']['capabilities']['ignored_wakes'][-1]['reason'] == 'cancellation_pending'
    assert CAP.continuation_status(current, context(records))['state'] == 'cancellation_pending'


def test_additional_client_observation_registry_does_not_admit_continuation():
    import capabilities
    """Source decoding and fresh native continuation remain separate owners."""
    for name in ('cursor-ide','cursor-cli','cursor-cloud','copilot-cli','copilot-vscode','copilot-cloud','opencode-cli','opencode-sdk-v2'):
        entry=capabilities.supported_surfaces()['surfaces'][name]
        assert entry['level']!='native'
        assert entry['observation_contract']['native_acceptance']=='UNKNOWN'
        assert entry['observation_contract']['authority_granted'] is False


def test_observation_only_opencode_cannot_be_normalized_as_claude_stop():
    for name in ('opencode-cli','opencode-sdk-v2'):
        with pytest.raises(ValueError):CAP.normalize_event(name,{'hook_event_name':'Stop','session_id':'foreign','stop_hook_active':False})
