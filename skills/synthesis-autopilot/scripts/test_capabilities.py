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
    assert CAP.stop_response(surface, payload, "unfinished")["decision"] == "block"
    payload["stop_hook_active"] = True
    terminal = CAP.stop_response(surface, payload, "unfinished")
    assert terminal["continue"] is False
    assert terminal.get("decision") != "block"
    assert terminal["systemMessage"].startswith("UNRESOLVED:")


def test_cursor_uses_its_native_contract_and_has_no_terminal_override_claim():
    payload = {"conversation_id": "cursor-1", "generation_id": "generation-1",
               "status": "completed", "loop_count": 0}
    assert CAP.stop_response("cursor-ide", payload, "unfinished") == {"followup_message": "unfinished"}
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
        assert CAP.stop_response("copilot-cli", payload, "unfinished")["decision"] == "block"
        payload["stop_hook_active"] = True
        assert CAP.stop_response("copilot-cli", payload, "unfinished") == {"decision": "allow"}


@pytest.mark.parametrize("payload", [None, {}, {"session_id": "x", "hook_event_name": "Stop", "stop_hook_active": "false"}])
def test_malformed_native_identity_never_creates_a_corrective_turn(payload):
    result = CAP.stop_response("codex-cli", payload, "unverified")
    assert result["continue"] is False
    assert result.get("decision") != "block"


def test_fresh_user_turn_does_not_inherit_native_retry_flag():
    base = {"session_id": "same", "hook_event_name": "Stop", "stop_hook_active": True, "turn_id": "t1"}
    assert CAP.stop_response("codex-cli", base, "unfinished")["continue"] is False
    fresh = {**base, "stop_hook_active": False, "turn_id": "t2"}
    assert CAP.stop_response("codex-cli", fresh, "unfinished")["decision"] == "block"


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
    records["cancelled"] = receipt("continuation-cancellation", job_id="job-1", cancelled=True)
    done = CAP.confirm_cancel(requested, {"receipt": "cancelled"}, ctx)
    assert CAP.continuation_status(done, ctx)["state"] == "cancelled"
    records["late"] = receipt("continuation-wake", job_id="job-1", event_id="wake-late", next_wake_at=NOW + 60)
    late = CAP.observe_wake(done, {"receipt": "late"}, ctx)
    assert CAP.continuation_status(late, ctx)["state"] == "cancelled"
    assert late["extensions"]["capabilities"]["ignored_wakes"][-1]["reason"] == "cancelled"


def test_cancel_failure_remains_actionable_not_confirmed():
    current, records, ctx = configured()
    current = CAP.request_cancel(current, {"reason": "stop"}, ctx)
    records["failed"] = receipt("continuation-cancellation", job_id="job-1", cancelled=False)
    current = CAP.confirm_cancel(current, {"receipt": "failed"}, ctx)
    assert CAP.continuation_status(current, ctx)["state"] == "cancellation_failed"


def test_recovery_capsule_requires_current_resolver_native_claim_and_run_revision():
    records = {"recovery": receipt("recovery", run_revision=3, resolver_receipt="resolver-1",
                                   native_receipt="native-proof", claim_receipt="claim-proof",
                                   remaining=["deliverable-2"], input_receipts=["input-1"])}
    current = CAP.record_recovery(state(), {"receipt": "recovery"}, context(records))
    capsule = current["extensions"]["capabilities"]["recovery"]
    assert capsule["remaining"] == ["deliverable-2"]
    records["recovery"]["data"]["run_revision"] = 2
    with pytest.raises(ValueError):
        CAP.record_recovery(state(), {"receipt": "recovery"}, context(records))


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
    CAP.register_commands(lambda name, reducer, *, allowed_fields: registrations.update({name: (reducer, allowed_fields)}))
    assert {"capability.record", "continuation.register", "continuation.wake", "continuation.cancel",
            "continuation.cancel-confirm", "recovery.record", "delivery.record"} <= set(registrations)
    assert registrations["capability.record"][1] == ("extensions",)
