#!/usr/bin/env python3
"""Pure native adapters and evidence-bound continuation/recovery reducers.

This module is not a scheduler or a receipt issuer. The shared engine supplies
content-verified evidence and a trusted verifier in ``context``. A tool response,
queued message, saved transcript, or caller's ``verified`` flag cannot prove a
future wake. Static support describes implementation; admission requires fresh
observations of the particular client surface.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from datetime import datetime
from typing import Any, Callable, TypedDict


class NativeEvent(TypedDict):
    surface: str
    session_id: str
    event_id: str | None
    repeat_count: int
    status: str


class Admission(TypedDict):
    admitted: bool
    surface: str
    horizon: str
    reasons: list[str]


HORIZONS = ("in_session", "turn_end", "process_death", "app_exit", "logout",
            "reboot", "offline", "machine_transfer")
TERMINAL_RUNS = frozenset({"closed", "complete", "completed", "incomplete", "cancelled", "abandoned"})
MAX_EVENTS = 512
BINDING_KEYS = ("project_id", "project_root", "session_uuid", "native_ref",
                "claim_hash", "repository", "branch")


def _surface(level: str, dialect: str | None, mechanisms: tuple[str, ...] = (),
             *, terminal: bool = False) -> dict:
    return {"level": level, "dialect": dialect, "mechanisms": list(mechanisms),
            "terminal_precedence": terminal, "native_acceptance": "observation-required"}


# The sole autopilot supported-surface inventory. These levels must not be
# promoted from prose, adapter unit tests, or another surface's native receipt.
_REGISTRY = {
    "schema_version": 1,
    "surfaces": {
        "claude-code-cli": _surface("native", "claude", ("claude-session-cron",), terminal=True),
        "claude-code-desktop": _surface("native", "claude", ("claude-desktop-schedule", "claude-session-cron"), terminal=True),
        "codex-cli": _surface("native", "codex", terminal=True),
        "codex-desktop": _surface("native", "codex", ("codex-heartbeat", "codex-automation"), terminal=True),
        "muse-cli": _surface("native", "muse", terminal=True),
        "cursor-ide": _surface("skill-only", "cursor"),
        "cursor-cli": _surface("skill-only", "cursor"),
        "cursor-cloud": _surface("skill-only", "cursor"),
        "copilot-cli": _surface("skill-only", "copilot"),
        "copilot-vscode": _surface("skill-only", "copilot"),
        "copilot-cloud": _surface("skill-only", "copilot"),
        "opencode-cli": _surface("observation-only", "opencode"),
        "opencode-sdk-v2": _surface("observation-only", "opencode"),
        "hermes": _surface("prospective", None),
    },
}


def supported_surfaces() -> dict:
    """Return independent data suitable for doctor, installers and docs."""
    result = copy.deepcopy(_REGISTRY)
    for entry in result["surfaces"].values():
        if entry["dialect"] in {"cursor", "copilot", "opencode"}:
            entry["observation_contract"] = {"sdk": "native-adapter-sdk-v1",
                "authority_granted": False, "native_acceptance": "UNKNOWN",
                "permission_enforcement": "FAIL_OPEN_PATHS" if entry["dialect"] == "copilot" else "qualification-required"}
    return result


def _entry(surface: str) -> dict:
    if not isinstance(surface, str) or surface not in _REGISTRY["surfaces"]:
        raise ValueError("unknown client surface")
    return _REGISTRY["surfaces"][surface]


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError(f"{name} must be a non-empty bounded string")
    return value


def _time(value: Any) -> float:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamp must be an aware ISO date") from exc
        if parsed.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        value = parsed.timestamp()
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("timestamp must be finite")
    return float(value)


def normalize_event(surface: str, payload: dict) -> NativeEvent:
    """Translate native syntax, without claiming authenticated ownership."""
    dialect = _entry(surface)["dialect"]
    if not isinstance(payload, dict) or dialect is None or dialect == "opencode":
        raise ValueError("native Stop adapter or payload unavailable")
    if dialect == "cursor":
        if payload.get("hook_event_name", "stop") not in {"stop", "subagentStop"}:
            raise ValueError("not a Cursor Stop event")
        session = payload.get("conversation_id")
        repeat = payload.get("loop_count")
        status = payload.get("status")
        if type(repeat) is not int or not 0 <= repeat <= 1000000:
            raise ValueError("Cursor loop_count must be a nonnegative integer")
        if status not in {"completed", "aborted", "error"}:
            raise ValueError("invalid Cursor Stop status")
        event_id = payload.get("generation_id")
    else:
        session = payload.get("sessionId") if dialect == "copilot" and "sessionId" in payload else payload.get("session_id")
        if dialect == "copilot" and "sessionId" in payload and "session_id" in payload and payload["sessionId"] != payload["session_id"]:
            raise ValueError("conflicting native session identities")
        if dialect != "copilot" and payload.get("hook_event_name") not in {"Stop", "SubagentStop"}:
            raise ValueError("not a native Stop event")
        if dialect == "copilot" and payload.get("hook_event_name", "Stop") not in {"Stop", "agentStop", "SubagentStop", "subagentStop"}:
            raise ValueError("not a Copilot Stop event")
        if type(payload.get("stop_hook_active")) is not bool:
            raise ValueError("native repeat flag is absent or invalid")
        repeat = int(payload["stop_hook_active"])
        status = "completed"
        event_id = payload.get("turn_id") or payload.get("prompt_id")
    _text(session, "native session identity")
    if event_id is not None:
        _text(event_id, "native event identity")
    return {"surface": surface, "session_id": session, "event_id": event_id,
            "repeat_count": repeat, "status": status}


def stop_response(surface: str, payload: dict, reason: str | None = None,
                  *, terminal: bool = False, policy_disposition: dict | None = None) -> dict:
    """Bound Synthesis-owned feedback using only the native output dialect.

    Cursor and Copilot do not gain a global terminal override from this adapter.
    Their limitations remain in the registry even when our own retry is stopped.
    """
    dialect = _entry(surface)["dialect"]
    try:
        event = normalize_event(surface, payload)
        eligible = (isinstance(policy_disposition, dict) and policy_disposition.get("action") == "corrective"
                    and policy_disposition.get("allow_attempt") is True
                    and policy_disposition.get("authority_granted") is False
                    and policy_disposition.get("completion_granted") is False
                    and isinstance(policy_disposition.get("reservation"), dict))
        terminal = terminal or not eligible or event["status"] != "completed"
    except ValueError:
        terminal = True
        reason = reason or "Native Stop input is unverified; protection remains unresolved."
    if not reason:
        return {}
    _text(reason, "Stop diagnostic")
    if dialect == "cursor":
        return {} if terminal else {"followup_message": reason}
    if dialect == "copilot":
        return {"decision": "allow"} if terminal else {"decision": "block", "reason": reason}
    if dialect not in {"claude", "codex", "muse"}:
        raise ValueError("surface has no native Stop emitter")
    result = {"systemMessage": reason if reason.startswith("UNRESOLVED: ") else "UNRESOLVED: " + reason}
    if terminal:
        result.update({"continue": False, "stopReason": reason})
    else:
        result.update({"decision": "block", "reason": reason, "_synthesis_policy": policy_disposition["reservation"]})
    return result


def _fields(payload: dict, required: set[str], optional: set[str] | None = None) -> None:
    if not isinstance(payload, dict) or not required <= payload.keys() or set(payload) - required - (optional or set()):
        raise ValueError("invalid command payload fields")


def _binding(state: dict, context: dict) -> dict:
    binding = context.get("binding")
    if not isinstance(binding, dict) or set(BINDING_KEYS) - binding.keys():
        raise ValueError("authenticated project/native/claim binding is unavailable")
    for key in BINDING_KEYS[:-2]:
        _text(binding[key], key)
    if binding["repository"] is not None or binding["branch"] is not None:
        _text(binding["repository"], "repository")
        _text(binding["branch"], "branch")
    result = {key: copy.deepcopy(binding[key]) for key in BINDING_KEYS}
    result["run_id"] = _text(state.get("run_id"), "run identity")
    for key in ("contract_digest", "profile_digest"):
        if key in state:
            result[key] = state[key]
    return result


def _proof(state: dict, context: dict, reference: str, kind: str) -> dict:
    _text(reference, "receipt reference")
    bindings = _binding(state, context)
    verifier = context.get("verify_receipt")
    try:
        verified = callable(verifier) and verifier(reference, kind, bindings) is True
    except Exception as exc:
        raise ValueError("receipt verification failed") from exc
    if not verified:
        raise ValueError("receipt is not independently verified")
    proof = context.get("evidence", {}).get(reference)
    if not isinstance(proof, dict) or proof.get("kind") != kind or not isinstance(proof.get("data"), dict):
        raise ValueError("typed receipt evidence unavailable")
    if any(proof.get("bindings", {}).get(key) != value for key, value in bindings.items()):
        raise ValueError("receipt belongs to another run, project, native session or claim")
    now = _time(context.get("now"))
    if _time(proof.get("observed_at")) > now or _time(proof.get("expires_at")) <= now:
        raise ValueError("receipt is expired or from the future")
    return copy.deepcopy(proof)


def _copy(state: dict) -> tuple[dict, dict]:
    result = copy.deepcopy(state)
    ext = result.setdefault("extensions", {}).setdefault("capabilities", {})
    if not isinstance(ext, dict):
        raise ValueError("invalid capability extension state")
    ext.setdefault("schema_version", 1)
    if ext["schema_version"] != 1:
        raise ValueError("unsupported capability state schema")
    return result, ext


def _current(state: dict) -> dict:
    ext = state.get("extensions", {}).get("capabilities", {})
    if not isinstance(ext, dict) or ext.get("schema_version", 1) != 1:
        raise ValueError("unsupported capability state schema")
    return ext


def receipt_fingerprint(proof: dict) -> str:
    """Bind historical intake to the entire immutable, validated envelope."""
    return hashlib.sha256(json.dumps(proof, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _remember_native(ext: dict, reference: str, proof: dict, context: dict) -> None:
    saved = ext.setdefault("native_intakes", {})
    fingerprint = receipt_fingerprint(proof)
    if reference in saved:
        if saved[reference]["fingerprint"] != fingerprint:
            raise ValueError("admitted native receipt cannot be substituted")
        return
    if len(saved) >= MAX_EVENTS:
        raise ValueError("native intake evidence capacity reached")
    saved[reference] = {"fingerprint": fingerprint, "recorded_at": context["now"]}


def record_capability(state: dict, payload: dict, context: dict) -> dict:
    _fields(payload, {"surface", "receipt"})
    _entry(payload["surface"])
    proof = _proof(state, context, payload["receipt"], "capability")
    data = proof["data"]
    if data.get("surface") != payload["surface"] or not isinstance(data.get("capabilities"), dict):
        raise ValueError("capability receipt has the wrong surface or shape")
    capabilities = data["capabilities"]
    for key in ("native_identity", "registration_readback", "wake_observation", "cancellation_readback", "independent_observer", "terminal_precedence"):
        if key in capabilities and type(capabilities[key]) is not bool:
            raise ValueError("capability booleans must be exact")
    for key in ("survival", "mechanisms"):
        if not isinstance(capabilities.get(key), list) or not all(isinstance(v, str) for v in capabilities[key]):
            raise ValueError("capability horizons and mechanisms must be lists")
    if set(capabilities["survival"]) - set(HORIZONS):
        raise ValueError("unknown survival horizon")
    result, ext = _copy(state)
    ext.setdefault("observations", {})[payload["surface"]] = {"receipt": payload["receipt"], "observed_at": proof["observed_at"]}
    _remember_native(ext, payload["receipt"], proof, context)
    return result


def admission(state: dict, surface: str, horizon: str, context: dict) -> Admission:
    entry = _entry(surface)
    if horizon not in HORIZONS:
        raise ValueError("unknown continuation horizon")
    reasons = []
    if entry["level"] == "prospective":
        reasons.append("native integration is prospective")
    if horizon != "in_session":
        if entry["level"] != "native":
            reasons.append("native integration has not been released for this surface")
        reference = _current(state).get("observations", {}).get(surface, {}).get("receipt")
        try:
            proof = _proof(state, context, reference, "capability")
            data = proof["data"]
            if data.get("surface") != surface:
                raise ValueError("capability receipt surface mismatch")
            capabilities = data["capabilities"]
            for key in ("native_identity", "registration_readback", "wake_observation", "cancellation_readback", "independent_observer"):
                if capabilities.get(key) is not True:
                    reasons.append("unverified " + key)
            if horizon not in capabilities.get("survival", []):
                reasons.append("unverified survival horizon: " + horizon)
            if not set(capabilities.get("mechanisms", [])) & set(entry["mechanisms"]):
                reasons.append("no implemented, observed native continuation facility")
        except (ValueError, KeyError, TypeError):
            reasons.append("fresh independently verified capability evidence unavailable")
    return {"admitted": not reasons, "surface": surface, "horizon": horizon, "reasons": reasons}


def continuation_request(surface: str, horizon: str, state: dict, context: dict) -> dict:
    """Describe existing host work; a request is explicitly not registration."""
    check = admission(state, surface, horizon, context)
    return {**check, "state": "request_only", "run_id": state.get("run_id"),
            "mechanisms": list(_entry(surface)["mechanisms"]),
            "required_receipt_kind": "continuation-registration"}


def register_continuation(state: dict, payload: dict, context: dict) -> dict:
    _fields(payload, {"receipt", "horizon"})
    if state.get("status") in TERMINAL_RUNS:
        raise ValueError("closed run cannot register continuation")
    proof = _proof(state, context, payload["receipt"], "continuation-registration")
    data = proof["data"]
    surface = data.get("surface")
    check = admission(state, surface, payload["horizon"], context)
    if payload["horizon"] == "in_session" or not check["admitted"]:
        raise ValueError("unattended continuation is not admitted: " + "; ".join(check["reasons"]))
    job_id = _text(data.get("job_id"), "native job identity")
    old = _current(state).get("continuation")
    if old and old.get("status") not in {"cancelled"}:
        if old.get("registration_receipt") == payload["receipt"]:
            return copy.deepcopy(state)
        raise ValueError("a continuation owner already exists; reconcile or confirm cancellation first")
    if data.get("mechanism") not in _entry(surface)["mechanisms"]:
        raise ValueError("unimplemented native continuation mechanism")
    capability_ref = _current(state)["observations"][surface]["receipt"]
    capabilities = _proof(state, context, capability_ref, "capability")["data"]["capabilities"]
    if data["mechanism"] not in capabilities["mechanisms"]:
        raise ValueError("native continuation facility has not been observed")
    observer = _text(data.get("observer_id"), "independent observer identity")
    owner = _text(data.get("owner"), "continuation owner")
    if observer == owner:
        raise ValueError("worker cannot be its own independent observer")
    now = _time(context["now"])
    wake = _time(data.get("next_wake_at"))
    expires = _time(data.get("lease_expires_at"))
    if not now < wake < expires <= _time(proof["expires_at"]):
        raise ValueError("invalid observed wake deadline or lease expiry")
    result, ext = _copy(state)
    if old:
        _append(ext.setdefault("retired_jobs", []), copy.deepcopy(old))
    ext["continuation"] = {"job_id": job_id, "surface": surface, "mechanism": data["mechanism"],
        "owner": owner, "observer_id": observer, "binding": _binding(state, context),
        "horizon": payload["horizon"], "registration_receipt": payload["receipt"],
        "lease_receipt": payload["receipt"], "renewals": [],
        "registered_at": now, "next_wake_at": wake, "lease_expires_at": expires,
        "status": "registered", "wakes": [], "wake_grace_seconds": 30}
    _remember_native(ext, payload["receipt"], proof, context)
    return result


def _job(state: dict, context: dict) -> dict:
    job = _current(state).get("continuation")
    if not isinstance(job, dict):
        raise ValueError("no registered native continuation")
    if job.get("binding") != _binding(state, context):
        raise ValueError("continuation ownership or contract binding changed")
    return job


def _append(records: list, value: dict) -> None:
    if len(records) >= MAX_EVENTS:
        raise ValueError("continuation evidence capacity reached; reconcile before adding events")
    records.append(value)


def renew_continuation(state: dict, payload: dict, context: dict) -> dict:
    """Extend a live same-pair lease using new native readback, never a wake."""
    _fields(payload, {"receipt"})
    job = _job(state, context)
    now = _time(context["now"])
    if (state.get("status") in TERMINAL_RUNS or job["status"] not in {"registered", "observed"}
            or now >= job["lease_expires_at"]
            or now > job["next_wake_at"] + job["wake_grace_seconds"]):
        raise ValueError("only a live, non-overdue continuation lease can be renewed")
    proof = _proof(state, context, payload["receipt"], "continuation-renewal")
    data = proof["data"]
    if any(data.get(key) != job[key] for key in ("job_id", "surface", "mechanism", "owner", "observer_id")):
        raise ValueError("renewal must preserve the same native pair and owner")
    if data.get("registration_receipt") != job["registration_receipt"]:
        raise ValueError("renewal changed its original registration")
    if any(item["receipt"] == payload["receipt"] for item in job.get("renewals", [])):
        if _current(state).get("native_intakes", {}).get(payload["receipt"], {}).get("fingerprint") != receipt_fingerprint(proof):
            raise ValueError("renewal history receipt was substituted")
        return copy.deepcopy(state)
    previous = job.get("lease_receipt", job["registration_receipt"])
    if data.get("previous_lease_receipt") != previous:
        raise ValueError("renewal must extend the currently admitted lease receipt")
    if not admission(state, job["surface"], job["horizon"], context)["admitted"]:
        raise ValueError("renewal capability is not currently admitted")
    capability_ref = _current(state)["observations"][job["surface"]]["receipt"]
    capability = _proof(state, context, capability_ref, "capability")
    original = _proof(state, context, job["registration_receipt"], "continuation-registration")
    prior_proof = _proof(state, context, previous,
        "continuation-registration" if previous == job["registration_receipt"] else "continuation-renewal")
    readback = _time(data.get("readback_at"))
    expires = _time(data.get("lease_expires_at"))
    if (not 0 <= now - readback <= 300 or not job["lease_expires_at"] < expires
            or expires > min(readback + 300, _time(proof["expires_at"]), _time(capability["expires_at"]),
                             _time(original["expires_at"]), _time(prior_proof["expires_at"]))):
        raise ValueError("renewal exceeds a required receipt expiry or five-minute readback lease")
    result, ext = _copy(state)
    current = ext["continuation"]
    _append(current.setdefault("renewals", []), {"receipt": payload["receipt"], "previous_lease_receipt": previous,
        "recorded_at": context["now"], "lease_expires_at": expires})
    current.update(lease_receipt=payload["receipt"], lease_expires_at=expires)
    _remember_native(ext, payload["receipt"], proof, context)
    return result


def observe_wake(state: dict, payload: dict, context: dict) -> dict:
    _fields(payload, {"receipt"})
    job = _job(state, context)
    proof = _proof(state, context, payload["receipt"], "continuation-wake")
    data = proof["data"]
    retired = next((item for item in _current(state).get("retired_jobs", [])
                    if item["job_id"] == data.get("job_id")), None)
    if data.get("job_id") != job["job_id"] and retired is None:
        raise ValueError("wake belongs to another native job")
    event_id = _text(data.get("event_id"), "native wake event")
    ext = _current(state)
    if any(item["event_id"] == event_id and item["job_id"] == data["job_id"]
           for item in job["wakes"] + ext.get("ignored_wakes", [])):
        return copy.deepcopy(state)
    result, ext = _copy(state)
    current = ext["continuation"]
    native_at = data.get("native_observed_at", proof["observed_at"])
    entry = {"event_id": event_id, "job_id": data["job_id"], "receipt": payload["receipt"], "observed_at": native_at}
    reason = None
    if retired is not None and data["job_id"] != job["job_id"]:
        reason = "retired_job"
    elif state.get("status") in TERMINAL_RUNS:
        reason = "run_closed"
    elif job["status"] in {"cancelled", "cancellation_pending", "cancellation_failed"}:
        reason = job["status"]
    elif _time(context["now"]) >= job["lease_expires_at"]:
        reason = "lease_expired"
    elif state.get("extensions", {}).get("workflow_persistence", {}).get("decisions"):
        from workflow import stop_feedback_status
        if stop_feedback_status(state, context)["action"] != "eligible":
            reason = "policy_wait"
    if reason:
        _append(ext.setdefault("ignored_wakes", []), {**entry, "reason": reason})
        return result
    if job.get("renewals") and data.get("source", {}).get("lease_receipt") != job["lease_receipt"]:
        raise ValueError("wake must bind the currently admitted renewed lease")
    observed = _time(native_at)
    next_wake = _time(data.get("next_wake_at"))
    if observed < job["registered_at"] or not observed < next_wake < job["lease_expires_at"]:
        raise ValueError("wake chronology or next observed deadline is invalid")
    if job["wakes"] and observed < _time(job["wakes"][-1]["observed_at"]):
        raise ValueError("out-of-order wake requires reconciliation")
    _append(current["wakes"], entry)
    current.update({"status": "observed", "next_wake_at": next_wake})
    _remember_native(ext, payload["receipt"], proof, context)
    return result


def continuation_status(state: dict, context: dict) -> dict:
    job = _current(state).get("continuation")
    if state.get("status") in TERMINAL_RUNS:
        return {"state": "closed", "continuation_verified": False,
                "cleanup_required": bool(job and job.get("status") != "cancelled"),
                "cleanup_state": job.get("status") if job else "none"}
    if not job:
        return {"state": "unregistered", "continuation_verified": False}
    try:
        _job(state, context)
    except ValueError as exc:
        return {"state": "ownership_changed", "continuation_verified": False, "reason": str(exc)}
    status = job["status"]
    if (status not in {"cancelled", "cancellation_pending", "cancellation_failed"}
            and state.get("extensions", {}).get("workflow_persistence", {}).get("decisions")):
        from workflow import stop_feedback_status
        if stop_feedback_status(state, context)["action"] != "eligible":
            return {"state": "policy_wait", "continuation_verified": False,
                    "cleanup_required": True, "cleanup_state": status, "job_id": job["job_id"]}
    if status not in {"cancelled", "cancellation_pending", "cancellation_failed"}:
        now = _time(context["now"])
        if now >= job["lease_expires_at"]:
            status = "expired"
        elif now > job["next_wake_at"] + job["wake_grace_seconds"]:
            status = "overdue"
        elif not admission(state, job["surface"], job["horizon"], context)["admitted"]:
            status = "capability_unverified"
        elif not job["wakes"]:
            status = "awaiting_first_wake"
    return {"state": status, "job_id": job["job_id"], "next_wake_at": job["next_wake_at"],
            "continuation_verified": status == "observed", "observed_wakes": len(job["wakes"])}


def request_cancel(state: dict, payload: dict, context: dict) -> dict:
    _fields(payload, {"reason"})
    _text(payload["reason"], "cancellation reason")
    _job(state, context)
    result, ext = _copy(state)
    if ext["continuation"]["status"] == "cancelled":
        return result
    ext["continuation"].update({"status": "cancellation_pending", "cancel_reason": payload["reason"],
                                 "cancel_requested_at": context["now"]})
    return result


def confirm_cancel(state: dict, payload: dict, context: dict) -> dict:
    _fields(payload, {"receipt"})
    job = _job(state, context)
    if job["status"] not in {"cancellation_pending", "cancellation_failed", "cancelled"}:
        raise ValueError("cancellation was not requested")
    proof = _proof(state, context, payload["receipt"], "continuation-cancellation")
    data = proof["data"]
    if data.get("job_id") != job["job_id"] or type(data.get("cancelled")) is not bool:
        raise ValueError("cancellation receipt has wrong native job or result")
    if _time(proof["observed_at"]) < _time(job["cancel_requested_at"]):
        raise ValueError("cancellation readback predates its request")
    if job["status"] == "cancelled" and not data["cancelled"]:
        raise ValueError("cannot replace confirmed cancellation with contradictory evidence")
    result, ext = _copy(state)
    ext["continuation"].update({"status": "cancelled" if data["cancelled"] else "cancellation_failed",
                                "cancellation_receipt": payload["receipt"]})
    return result


def record_recovery(state: dict, payload: dict, context: dict) -> dict:
    _fields(payload, {"receipt"})
    proof = _proof(state, context, payload["receipt"], "recovery")
    data = proof["data"]
    if type(data.get("run_revision")) is not int or data["run_revision"] != state.get("revision"):
        raise ValueError("recovery capsule is for another run revision")
    for key, kind in (("resolver_receipt", "project-resolution"), ("native_receipt", "native-identity"), ("claim_receipt", "claim-ownership")):
        _proof(state, context, data.get(key), kind)
    for key in ("remaining", "input_receipts"):
        if not isinstance(data.get(key), list) or not all(isinstance(v, str) and v for v in data[key]):
            raise ValueError("recovery obligations and inputs must be explicit lists")
    for reference in data["input_receipts"]:
        _proof(state, context, reference, "working-input")
    result, ext = _copy(state)
    ext["recovery"] = {**data, "receipt": payload["receipt"], "binding": _binding(state, context),
                       "observed_at": proof["observed_at"], "recorded_revision": state["revision"] + 1}
    return result


def wait_binding(state: dict) -> dict:
    """Bind notifications to the exact unresolved questions and dependencies."""
    waits = state.get("waits", {})
    if not isinstance(waits, dict):
        raise ValueError("invalid wait inventory")
    pending = {key: item for key, item in waits.items() if item.get("status") == "pending"}
    digest = hashlib.sha256(json.dumps(pending, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return {"wait_ids": sorted(pending), "wait_digest": digest, "run_revision": state["revision"]}


def wait_delivery_status(state: dict, context: dict) -> dict:
    """Historical notification never satisfies changed or unobserved waits."""
    binding = wait_binding(state)
    result = {"delivered": False, **binding, "receipt": None}
    if state.get("status") != "waiting_user" or not binding["wait_ids"]:
        return result
    for delivery in _current(state).get("deliveries", {}).values():
        try:
            proof = _proof(state, context, delivery["receipt"], "delivery")
            data = proof["data"]
            if (data.get("status") in {"delivered", "acknowledged"}
                    and delivery["status"] == data["status"]
                    and data.get("wait_ids") == binding["wait_ids"]
                    and data.get("wait_digest") == binding["wait_digest"]
                    and data.get("run_revision") == delivery.get("run_revision")
                    and type(data.get("run_revision")) is int
                    and data["run_revision"] <= state["revision"]):
                result.update(delivered=True, receipt=delivery["receipt"])
                return result
        except (KeyError, TypeError, ValueError):
            continue
    return result


def record_delivery(state: dict, payload: dict, context: dict) -> dict:
    _fields(payload, {"receipt"})
    proof = _proof(state, context, payload["receipt"], "delivery")
    data = proof["data"]
    identity = _text(data.get("delivery_id"), "delivery identity")
    _text(data.get("channel"), "delivery channel")
    if data.get("status") not in {"queued", "delivered", "acknowledged", "failed", "unknown", "suppressed"}:
        raise ValueError("invalid observed delivery state")
    wait_fields = {"wait_ids", "wait_digest", "run_revision"}
    wait_data = {}
    if wait_fields & data.keys():
        binding = wait_binding(state)
        if (not wait_fields <= data.keys()
                or any(data[key] != binding[key] for key in ("wait_ids", "wait_digest"))
                or type(data.get("run_revision")) is not int
                or not 0 <= data["run_revision"] <= state["revision"]):
            raise ValueError("delivery does not bind the current unresolved waits and revision")
        # Evidence registration advances the journal without changing the wait.
        # Preserve the observed revision; never predict a future revision.
        wait_data = {key: data[key] for key in wait_fields}
    result, ext = _copy(state)
    deliveries = ext.setdefault("deliveries", {})
    old = deliveries.get(identity)
    if old:
        if old["channel"] != data["channel"] or _time(proof["observed_at"]) < _time(old["observed_at"]):
            raise ValueError("delivery identity or chronology mismatch")
        if old["status"] == "acknowledged" and data["status"] != "acknowledged":
            raise ValueError("cannot regress acknowledged delivery")
        if old["status"] == "delivered" and data["status"] in {"queued", "unknown"}:
            raise ValueError("cannot regress delivered receipt to an unobserved state")
    if not old and len(deliveries) >= MAX_EVENTS:
        raise ValueError("delivery evidence capacity reached")
    recorded_at = context["now"]
    if old and old.get("receipt") == payload["receipt"] and old.get("receipt_digest") == proof["digest"]:
        recorded_at = old.get("recorded_at", recorded_at)
    deliveries[identity] = {"delivery_id": identity, "channel": data["channel"], "status": data["status"],
                            "receipt": payload["receipt"], "receipt_digest": proof["digest"],
                            "recorded_at": recorded_at, "observed_at": proof["observed_at"], **wait_data}
    return result


def status_view(state: dict, context: dict) -> dict:
    ext = _current(state)
    recovery = ext.get("recovery") or {}
    recovered = False
    try:
        if state.get("revision") in {recovery.get("run_revision"), recovery.get("recorded_revision")}:
            _proof(state, context, recovery.get("receipt"), "recovery")
            recovered = recovery.get("binding") == _binding(state, context)
    except ValueError:
        pass
    return {"run_id": state.get("run_id"), "run_status": state.get("status"),
            "continuation": continuation_status(state, context),
            "remaining": copy.deepcopy(recovery.get("remaining")) if recovered else None,
            "deliveries": copy.deepcopy(list(ext.get("deliveries", {}).values())),
            "recovery_receipt": recovery.get("receipt"),
            "recovery_status": "verified" if recovered else "unverified"}


def alert_intent(state: dict, visibility: dict) -> dict:
    """Privacy-safe intent only; a host must report actual delivery separately."""
    _fields(visibility, {"ui_available", "user_blocker", "muted"})
    if any(type(v) is not bool for v in visibility.values()):
        raise ValueError("visibility and mute flags must be exact booleans")
    needed = visibility["user_blocker"] and not visibility["ui_available"]
    return {"independent_alert_required": needed, "audio": needed and not visibility["muted"],
            "state": "intent_only", "run_id": state.get("run_id"),
            "public_message": "An action needs your attention. Open the task for details." if needed else ""}


def register_commands(register_command: Callable) -> None:
    """Register pure extension reducers with the shared serialized engine."""
    for name, reducer in {
        "capability.record": record_capability,
        "continuation.register": register_continuation,
        "continuation.renew": renew_continuation,
        "continuation.wake": observe_wake,
        "continuation.cancel": request_cancel,
        "continuation.cancel-confirm": confirm_cancel,
        "recovery.record": record_recovery,
        "delivery.record": record_delivery,
    }.items():
        register_command(name, reducer, allowed_fields=("extensions",),
                         terminal_safe=name in {"continuation.wake", "continuation.cancel",
                                                "continuation.cancel-confirm", "delivery.record"})


def validate_horizon(state: dict, horizon: str, context: dict) -> None:
    """Require observed evidence for a workflow's mandatory survival horizon."""
    job = _job(state, context)
    if job.get("horizon") != horizon or not admission(state, job["surface"], horizon, context)["admitted"]:
        raise ValueError("required continuation survival horizon has not been observed")
    registered = _proof(state, context, job["registration_receipt"], "continuation-registration")
    if registered["data"].get("job_id") != job["job_id"] or not job.get("wakes"):
        raise ValueError("required continuation lacks its observed registration and wake")
    for wake in job["wakes"]:
        observed = _proof(state, context, wake["receipt"], "continuation-wake")
        if observed["data"].get("job_id") != job["job_id"] or observed["data"].get("event_id") != wake["event_id"]:
            raise ValueError("observed continuation wake no longer matches this job")


def validate_command(state: dict, command: str, payload: dict, context: dict) -> None:
    """Completion checks explicit contract evidence, not an invented policy.

    Incomplete/cancelled tombstones are always permitted by this constraint.
    Outstanding native cleanup remains visible and uses terminal-safe reducers.
    """
    if command != "close" or payload.get("status") != "completed":
        return
    owned_kinds = {"capability", "continuation-registration", "continuation-renewal", "continuation-wake",
                   "continuation-cancellation", "recovery", "delivery"}
    ext = _current(state)
    jobs = ([ext["continuation"]] if ext.get("continuation") else []) + ext.get("retired_jobs", [])
    for criterion in state.get("contract", {}).get("criteria", []):
        kind = criterion.get("method")
        if not criterion.get("required") or kind not in owned_kinds:
            continue
        references = criterion.get("evidence_ids")
        if not isinstance(references, list) or not references:
            raise ValueError("required native criterion has no bound evidence")
        for reference in references:
            proof = _proof(state, context, reference, kind)
            data = proof["data"]
            if kind.startswith("continuation-"):
                job = next((job for job in jobs if job["job_id"] == data.get("job_id")), None)
                if job is None:
                    raise ValueError("required continuation evidence has no recorded native job")
                if kind == "continuation-wake" and not any(wake["receipt"] == reference for wake in job["wakes"]):
                    raise ValueError("required wake was not observed by the run")
                if kind == "continuation-renewal" and not any(item["receipt"] == reference for item in job.get("renewals", [])):
                    raise ValueError("required renewal was not admitted by the run")
                if kind == "continuation-cancellation" and (job["status"] != "cancelled" or data.get("cancelled") is not True):
                    raise ValueError("required native cancellation is not confirmed")
            elif kind == "recovery":
                for field, component_kind in (("resolver_receipt", "project-resolution"),
                                              ("native_receipt", "native-identity"),
                                              ("claim_receipt", "claim-ownership")):
                    _proof(state, context, data.get(field), component_kind)
                if not isinstance(data.get("input_receipts"), list):
                    raise ValueError("required recovery inputs are unknown")
                for input_reference in data["input_receipts"]:
                    _proof(state, context, input_reference, "working-input")
