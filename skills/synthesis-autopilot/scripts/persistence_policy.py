"""Pure failure admission shared by workflow and protective native consumers.

This module performs no I/O and owns no journal, scheduler, clock, permission or
receipt verifier. Its JSON-shaped inputs are projections built by existing
owners *after* authenticating source evidence, current PM/action admission and
the entire run journal. A source digest, evidence ID or completeness status is
a binding to that verification, not authentication supplied by this module.
Owners must recheck cancellation/admission at commit and atomically reserve a
Stop correction ID before emitting corrective feedback.

Input contracts (schema_version=1, additional fields rejected):

* classify_failure(outcome, coverage): outcome identifies one native attempt,
  exact source, run revision and stable obligation/subject. Strategy identity
  uses method/intervention/discriminator digests; rationale prose never resets
  it. relevant_state.facts contains the owner's fixed cause-relevant fields,
  not timestamps, revision counters, diagnostic wording or unrelated outputs.
  Coverage binds that exact event/source/generation to a verifier's evidence.
* decide_attempt(condition, retained_attempts, rearm, admission): history is an
  object with all normalized attempts and admitted rearm records in the run,
  plus full_run coverage binding its counts/digest to the current journal head.
  The condition is the latest relevant attempt, either already retained or at
  the next revision. A proposed rearm is at the next revision; an admitted rearm
  is replayed from history. Caller-supplied epoch/counter resets are forbidden.
  Admission supplies current verified owner/resource/effect state. UNKNOWN is
  a refusal. No result grants action authority or certifies completion.
* stop_disposition(decision, native_event, latch_status): returns host-neutral
  terminal/corrective/deny instructions, never a native mutation allow. A latch
  may suppress a correction; only a current owner-verified decision may permit
  one. latch_status.owner_readback is a fresh read from the existing owner,
  separate from persisted deny-only latch fields. It binds the committed
  decision, journal, current admission and native session. Existing adapters
  translate the output to their native wire schema.

Rearm records bind the exact prior failed attempt/digest and an unused source
proof. The original attempts remain in the input and journal; no function
deletes, rewrites or returns a replacement history. Genuine condition/strategy
change opens a new epoch without changing cumulative failed-attempt counts.
Successful evidence, including a disproved hypothesis, spends no failure unit.
An outcome of blocked means no attempt executed and also spends no unit;
failure and ambiguous_effect describe executed unsuccessful/uncertain attempts.

All strings, fact trees and collection inputs have structural safety bounds.
The history bound matches the existing run journal's 10,000-event capacity;
exceeding it raises a storage-capacity error, never retry exhaustion. Ordinary
work has no observation, grade-round or lifetime-clearance policy ceiling.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from typing import Any


SCHEMA = 1
MAX_HISTORY_RECORDS = 10_000
MAX_REFERENCES = 256
MAX_FACT_BYTES = 32_768
MAX_INTEGER = 10**15
FAILURE_FAMILIES = frozenset({
    "runtime_dependency", "malformed_identity", "ownership_stale_or_foreign",
    "policy_denial", "human_input", "provider_outage", "transient_tool",
    "permanent_tool", "ambiguous_effect", "quality_failure", "review_disagreement",
    "coverage_unknown", "unclassified",
})
TRANSIENT = frozenset({"provider_outage", "transient_tool"})
QUALITY = frozenset({"quality_failure", "review_disagreement"})
OUTCOMES = frozenset({"artifact", "evidence", "failure", "blocked", "ambiguous_effect", "cancelled"})
REARM_KINDS = frozenset({"state_change", "strategy_change", "runtime_restored", "identity_restored",
    "ownership_changed", "authority_changed", "human_response", "effect_reconciled", "quality_repair",
    "explicit_instruction"})
_STRATEGY_FIELDS = {"method_digest", "intervention_digest", "discriminator_digest", "rationale_ref"}
_OUTCOME_FIELDS = {"schema_version", "run_id", "task_id", "obligation_id", "attempt_id", "event_id",
    "revision", "source_digest", "bindings_digest", "outcome", "subject_digest", "strategy",
    "relevant_state", "evidence_ids", "failure_family", "effect_id", "grade_digest"}
_DERIVED_FIELDS = {"family", "failure_id", "failure_digest", "strategy_key", "condition_digest", "coverage"}
_REARM_FIELDS = {"schema_version", "event_id", "source_digest", "revision", "run_id", "obligation_id",
    "bindings_digest", "failure_id", "prior_failure_digest", "prior_attempt_id", "kind", "strategy",
    "relevant_state", "evidence_ids", "effect_id", "effect_status", "quality_resolution"}


class PolicyError(ValueError):
    """Malformed, contradictory or unbound input; callers must fail closed."""


def _object(value: Any, fields: set[str], *, optional: set[str] = frozenset()) -> dict:
    if not isinstance(value, dict) or set(value) - fields - optional or fields - set(value):
        raise PolicyError("Invalid fields; required: " + ", ".join(sorted(fields)))
    if "schema_version" in fields and (type(value["schema_version"]) is not int or value["schema_version"] != SCHEMA):
        raise PolicyError("Unsupported policy schema")
    return value


def _text(value: Any, *, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise PolicyError("Expected nonempty bounded text without control characters")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise PolicyError("Text is not valid UTF-8") from exc
    return value


def _id(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}", value):
        raise PolicyError("Expected bounded identifier")
    return value


def _integer(value: Any, *, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value <= MAX_INTEGER:
        raise PolicyError("Expected bounded integer")
    return value


def _hash(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise PolicyError("Expected SHA-256 digest")
    return value


def _digest(value: Any) -> str:
    try:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    except (ValueError, TypeError, UnicodeError) as exc:
        raise PolicyError("Policy input is not canonical JSON") from exc


def _choice(value: Any, choices: set[str] | frozenset[str]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise PolicyError("Unknown policy value")
    return value


def _refs(value: Any, *, nonempty: bool = True, hashes: bool = False, maximum: int = MAX_REFERENCES) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum or (nonempty and not value):
        raise PolicyError("Expected bounded evidence references")
    for item in value:
        (_hash if hashes else _id)(item)
    if len(set(value)) != len(value):
        raise PolicyError("Duplicate evidence references")
    return sorted(value)


def _facts(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        raise PolicyError("Relevant-state tree is too deep")
    if isinstance(value, dict):
        if len(value) > 128:
            raise PolicyError("Relevant-state object is too large")
        return {_id(key): _facts(item, depth + 1) for key, item in value.items()}
    if isinstance(value, list):
        if len(value) > 128:
            raise PolicyError("Relevant-state list is too large")
        return [_facts(item, depth + 1) for item in value]
    if isinstance(value, str):
        return _text(value)
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        if abs(value) > MAX_INTEGER:
            raise PolicyError("Relevant-state integer is too large")
        return value
    if type(value) is float and math.isfinite(value) and abs(value) <= MAX_INTEGER:
        return int(value) if value.is_integer() else value
    raise PolicyError("Relevant state requires bounded finite JSON values")


def _state(value: Any) -> dict:
    _object(value, {"facts", "evidence_ids"})
    if not isinstance(value["facts"], dict) or not value["facts"]:
        raise PolicyError("Relevant state requires named causal facts")
    facts = _facts(value["facts"])
    if len(json.dumps(facts, sort_keys=True, allow_nan=False).encode()) > MAX_FACT_BYTES:
        raise PolicyError("Relevant-state storage capacity exceeded")
    return {"facts": facts, "evidence_ids": _refs(value["evidence_ids"])}


def _strategy(value: Any) -> dict:
    _object(value, _STRATEGY_FIELDS)
    return {key: (_id(value[key]) if key == "rationale_ref" else _hash(value[key])) for key in sorted(value)}


def _strategy_key(value: dict) -> str:
    return _digest({key: value[key] for key in sorted(_STRATEGY_FIELDS - {"rationale_ref"})})


def _causal_fields(value: dict, prefix: tuple = ()) -> set[tuple]:
    """Fixed dictionary fields cannot disappear inside a nested cause either."""
    fields = set()
    for key, item in value.items():
        path = (*prefix, key)
        fields.add(path)
        if isinstance(item, dict):
            fields.update(_causal_fields(item, path))
    return fields


def failure_key(run_id: str, obligation_id: str, family: str, subject: str) -> str:
    """Identify the causal obligation independently of task/revision/wording."""
    return _digest({"schema_version": SCHEMA, "run_id": _id(run_id), "obligation_id": _id(obligation_id),
                    "family": _choice(family, FAILURE_FAMILIES), "subject_digest": _hash(subject)})


def classify_failure(verified_outcome: dict, coverage: dict) -> dict:
    """Normalize one owner-verified observation; no string-based error guessing."""
    _object(verified_outcome, _OUTCOME_FIELDS, optional={"summary"})
    if "summary" in verified_outcome:
        _text(verified_outcome["summary"])
    # Validate structure before copying nested caller data; an over-depth tree
    # must raise PolicyError rather than exhaust deepcopy's recursion stack.
    result = {key: verified_outcome[key] for key in _OUTCOME_FIELDS}
    for key in ("run_id", "task_id", "obligation_id", "attempt_id", "event_id"):
        _id(result[key])
    for key in ("source_digest", "bindings_digest", "subject_digest"):
        _hash(result[key])
    _integer(result["revision"], minimum=1)
    _choice(result["outcome"], OUTCOMES)
    result["strategy"] = _strategy(result["strategy"])
    result["relevant_state"] = _state(result["relevant_state"])
    result["evidence_ids"] = _refs(result["evidence_ids"])
    if result["effect_id"] is not None:
        _id(result["effect_id"])
    if result["grade_digest"] is not None:
        _hash(result["grade_digest"])
    _object(coverage, {"schema_version", "status", "event_id", "source_digest", "generation", "evidence_id"})
    _choice(coverage["status"], {"complete", "incomplete", "conflict", "unknown"})
    for key in ("event_id", "generation", "evidence_id"):
        _id(coverage[key])
    if coverage["event_id"] != result["event_id"] or _hash(coverage["source_digest"]) != result["source_digest"]:
        raise PolicyError("Coverage does not bind this exact native event")
    original = result["failure_family"]
    if result["outcome"] in {"artifact", "evidence", "cancelled"}:
        if original is not None:
            raise PolicyError("Successful/cancelled observation cannot assert a failure family")
        family = "cancelled" if result["outcome"] == "cancelled" else "productive_work"
    else:
        family = _choice(original, FAILURE_FAMILIES)
    if result["outcome"] == "ambiguous_effect" and family != "ambiguous_effect":
        raise PolicyError("Ambiguous outcome requires its effect failure family")
    if family == "ambiguous_effect" and result["effect_id"] is None:
        raise PolicyError("Ambiguous effect requires its retained intent identity")
    if family in QUALITY and result["grade_digest"] is None:
        raise PolicyError("Quality failure requires the exact retained grade")
    if coverage["status"] != "complete" and family not in {"cancelled", "ambiguous_effect", "runtime_dependency", "malformed_identity"}:
        family = "coverage_unknown"
    result.update(family=family, strategy_key=_strategy_key(result["strategy"]),
                  condition_digest=_digest(result["relevant_state"]["facts"]), coverage=copy.deepcopy(coverage))
    result["failure_id"] = (failure_key(result["run_id"], result["obligation_id"], family, result["subject_digest"])
                            if family in FAILURE_FAMILIES else None)
    result["failure_digest"] = _digest({key: result[key] for key in (
        "run_id", "obligation_id", "attempt_id", "outcome", "family", "subject_digest", "strategy_key",
        "condition_digest", "effect_id", "grade_digest")})
    return result


def _condition(value: Any) -> dict:
    _object(value, _OUTCOME_FIELDS | _DERIVED_FIELDS)
    normalized = classify_failure({key: value[key] for key in _OUTCOME_FIELDS}, value["coverage"])
    if value != normalized:
        raise PolicyError("Normalized condition was replaced or reinterpreted")
    return normalized


def _rearm(value: Any) -> dict:
    _object(value, _REARM_FIELDS)
    result = dict(value)
    for key in ("event_id", "run_id", "obligation_id", "prior_attempt_id"):
        _id(result[key])
    for key in ("source_digest", "bindings_digest", "failure_id", "prior_failure_digest"):
        _hash(result[key])
    _integer(result["revision"], minimum=1)
    _choice(result["kind"], REARM_KINDS)
    result["strategy"] = _strategy(result["strategy"])
    result["relevant_state"] = _state(result["relevant_state"])
    result["evidence_ids"] = _refs(result["evidence_ids"])
    if result["effect_id"] is not None:
        _id(result["effect_id"])
    if result["effect_status"] is not None:
        _choice(result["effect_status"], {"absent", "failed_retryable", "confirmed", "cancelled"})
    if result["quality_resolution"] is not None:
        proof = result["quality_resolution"]
        _object(proof, {"mode", "prior_grade_digest", "receipt_id", "digest"})
        _choice(proof["mode"], {"repair_plan", "grade_resolution"})
        _hash(proof["prior_grade_digest"])
        _id(proof["receipt_id"])
        _hash(proof["digest"])
        result["quality_resolution"] = dict(proof)
    if result["kind"] != "effect_reconciled" and result["effect_status"] is not None:
        raise PolicyError("Only effect reconciliation can supply an effect disposition")
    if result["kind"] != "quality_repair" and result["quality_resolution"] is not None:
        raise PolicyError("Only quality repair can supply a grade resolution")
    return result


def _history(value: Any, run_id: str) -> tuple[list, list, dict]:
    _object(value, {"schema_version", "attempts", "rearms", "coverage"})
    for key in ("attempts", "rearms"):
        if not isinstance(value[key], list):
            raise PolicyError("History requires retained record lists")
    if len(value["attempts"]) + len(value["rearms"]) > MAX_HISTORY_RECORDS:
        raise PolicyError("Retained history storage capacity exceeded; preserve and reconcile with its owner")
    coverage = value["coverage"]
    _object(coverage, {"schema_version", "status", "scope", "run_id", "head_revision", "head_digest",
                       "attempt_count", "rearm_count", "projection_digest", "evidence_id"})
    _choice(coverage["status"], {"complete", "incomplete", "conflict", "unknown"})
    if coverage["scope"] != "full_run" or coverage["run_id"] != run_id:
        raise PolicyError("History must be the owner's full run projection")
    _integer(coverage["head_revision"])
    _hash(coverage["head_digest"])
    _id(coverage["evidence_id"])
    for field, records in (("attempt_count", "attempts"), ("rearm_count", "rearms")):
        if _integer(coverage[field]) != len(value[records]):
            raise PolicyError("Retained history count differs from its coverage")
    attempts = [_condition(item) for item in value["attempts"]]
    rearms = [_rearm(item) for item in value["rearms"]]
    projected = {key: value[key] for key in ("attempts", "rearms")}
    if _hash(coverage["projection_digest"]) != _digest(projected):
        raise PolicyError("Retained history digest differs from its coverage")
    for item in attempts + rearms:
        if item["run_id"] != run_id or item["revision"] > coverage["head_revision"]:
            raise PolicyError("Retained event is outside the covered run/revision")
    return attempts, rearms, coverage


def _admission(value: Any, run_id: str, coverage: dict) -> dict:
    _object(value, {"schema_version", "run_id", "bindings_digest", "journal_head_digest", "journal_revision",
        "identity", "runtime", "ownership", "authority", "resources", "storage", "cancelled", "terminal",
        "unresolved_effect_ids", "evidence_ids"})
    _id(value["run_id"])
    _hash(value["journal_head_digest"])
    _integer(value["journal_revision"])
    if value["run_id"] != run_id or value["journal_head_digest"] != coverage["head_digest"] or value["journal_revision"] != coverage["head_revision"]:
        raise PolicyError("Admission does not bind the covered journal head")
    _hash(value["bindings_digest"])
    for key in ("cancelled", "terminal"):
        if type(value[key]) is not bool:
            raise PolicyError("Cancellation/terminal state requires exact booleans")
    for key, choices in (("identity", {"verified", "missing", "malformed", "unknown"}),
        ("runtime", {"verified", "missing", "unverified", "unknown"}),
        ("ownership", {"admitted", "stale", "foreign", "unknown"}),
        ("authority", {"admitted", "denied", "unknown"}),
        ("resources", {"available", "exhausted", "unknown"}),
        ("storage", {"available", "exhausted", "unknown"})):
        _choice(value[key], choices)
    _refs(value["unresolved_effect_ids"], nonempty=False)
    _refs(value["evidence_ids"])
    return value


def _dedupe_attempts(attempts: list[dict]) -> list[dict]:
    events, identities, revisions, unique = {}, {}, {}, []
    for item in sorted(attempts, key=lambda entry: entry["revision"]):
        event = item["event_id"]
        # Native source identity cannot be reused with changed bytes or meaning.
        event_binding = (item["source_digest"], item["failure_digest"])
        if event in events and events[event] != event_binding:
            raise PolicyError("Native event has conflicting retained source evidence")
        events[event] = event_binding
        identity = (item["obligation_id"], item["attempt_id"])
        position = (item["obligation_id"], item["revision"])
        if position in revisions and revisions[position] != identity:
            raise PolicyError("Distinct attempts in one obligation need distinct revisions for causal order")
        revisions[position] = identity
        if identity in identities:
            if identities[identity] != item["failure_digest"]:
                raise PolicyError("One attempt has conflicting outcome evidence")
            continue
        identities[identity] = item["failure_digest"]
        unique.append(item)
    return unique


def _admit_rearm(record: dict, bucket: dict, consumed: set[str]) -> None:
    prior = bucket["latest"]
    if (record["failure_id"] != prior["failure_id"] or record["prior_failure_digest"] != prior["failure_digest"]
            or record["prior_attempt_id"] != prior["attempt_id"] or record["obligation_id"] != prior["obligation_id"]
            or record["revision"] <= prior["revision"]):
        raise PolicyError("Rearm does not bind the latest exact failed attempt")
    if bucket["last_rearm"] and prior["revision"] < bucket["last_rearm"]["revision"]:
        raise PolicyError("Prior failure was already rearmed; an intervening attempt is required")
    proof_keys = {"source:" + record["source_digest"]}
    proof_keys.update("evidence:" + item for item in record["evidence_ids"])
    proof_keys.update("state:" + item for item in record["relevant_state"]["evidence_ids"])
    if record["quality_resolution"]:
        proof_keys.add("quality:" + record["quality_resolution"]["digest"])
    if proof_keys & consumed:
        raise PolicyError("Rearm source proof was consumed; a receipt alias cannot replay it")
    family, kind = prior["family"], record["kind"]
    allowed = {
        "runtime_dependency": {"runtime_restored"}, "malformed_identity": {"identity_restored"},
        "ownership_stale_or_foreign": {"ownership_changed"}, "policy_denial": {"authority_changed"},
        "human_input": {"human_response"}, "ambiguous_effect": {"effect_reconciled"},
        "quality_failure": {"quality_repair"}, "review_disagreement": {"quality_repair"},
        "coverage_unknown": {"state_change"}, "unclassified": {"state_change", "strategy_change"},
    }.get(family, {"state_change", "strategy_change"})
    if kind not in allowed and not (kind == "explicit_instruction" and family not in QUALITY | {"ambiguous_effect"}):
        raise PolicyError("Failure family requires its owning resolution: " + family)
    changed_strategy = _strategy_key(record["strategy"]) != prior["strategy_key"]
    before, after = prior["relevant_state"]["facts"], record["relevant_state"]["facts"]
    if _causal_fields(before) != _causal_fields(after):
        raise PolicyError("Rearm must retain the complete causal fact field set")
    changed_state = _digest(after) != prior["condition_digest"]
    if kind == "strategy_change" and not changed_strategy:
        raise PolicyError("Reworded strategy is not a changed method or discriminator")
    if kind not in {"strategy_change", "explicit_instruction", "effect_reconciled", "quality_repair"} and not changed_state:
        raise PolicyError("Rearm requires a relevant state change, not fresh wording or receipt IDs")
    if family == "ambiguous_effect":
        if record["effect_id"] != prior["effect_id"] or record["effect_status"] is None:
            raise PolicyError("Effect reconciliation does not bind the exact retained intent")
    elif record["effect_id"] is not None:
        raise PolicyError("Unrelated effect reference cannot clear a failure")
    if family in QUALITY:
        proof = record["quality_resolution"]
        if not proof or proof["prior_grade_digest"] != prior["grade_digest"]:
            raise PolicyError("Quality resolution does not bind the retained failed grade")
        if proof["mode"] == "repair_plan" and not changed_strategy:
            raise PolicyError("Quality repair plan requires an admitted different approach or method")
        if proof["mode"] == "grade_resolution" and not changed_state:
            raise PolicyError("Quality grade resolution requires changed output state")
    # Only actual admission records can advance an epoch. Never trust an epoch
    # supplied by the caller, a new task ID, or an amended profile binding.
    bucket["epoch"] += 1
    bucket["epoch_attempts"] = set()
    bucket["last_rearm"] = copy.deepcopy(record)
    consumed.update(proof_keys)


def _replay(attempts: list[dict], rearms: list[dict]) -> tuple[dict, set[str]]:
    buckets, consumed, rearm_events = {}, set(), set()
    attempt_events = {item["event_id"] for item in attempts}
    attempt_positions = {(item["obligation_id"], item["revision"]) for item in attempts}
    sequence = [(item["revision"], 1, item) for item in attempts]
    sequence += [(item["revision"], 0, item) for item in rearms]
    for _, kind, item in sorted(sequence, key=lambda row: row[:2]):
        if kind == 0:
            if item["event_id"] in rearm_events | attempt_events:
                raise PolicyError("Admitted rearm event identity is replayed")
            if (item["obligation_id"], item["revision"]) in attempt_positions:
                raise PolicyError("A rearm and its next attempt require distinct committed revisions")
            rearm_events.add(item["event_id"])
            bucket = buckets.get(item["failure_id"])
            if bucket is None:
                raise PolicyError("Rearm lost its retained prior failure")
            _admit_rearm(item, bucket, consumed)
        elif item["family"] in FAILURE_FAMILIES:
            bucket = buckets.setdefault(item["failure_id"], {"epoch": 0, "attempts": set(),
                "epoch_attempts": set(), "latest": item, "last_rearm": None})
            if item["outcome"] in {"failure", "ambiguous_effect"}:
                bucket["attempts"].add(item["attempt_id"])
                bucket["epoch_attempts"].add(item["attempt_id"])
            bucket["latest"] = item
    return buckets, consumed


def decide_attempt(condition: dict, retained_attempts: dict, rearm: dict | None, admission: dict) -> dict:
    """Decide the next step from the full admitted projection without mutation.

    resources=available must be computed by the resource owner, including the
    deadline, measured breaches, unknown reservations and integration reserve.
    It is never inferred from an observation/attempt count here.
    """
    current = _condition(condition)
    attempts, rearms, coverage = _history(retained_attempts, current["run_id"])
    owner = _admission(admission, current["run_id"], coverage)
    retained_event = next((item for item in attempts if item["event_id"] == current["event_id"]), None)
    if retained_event is None and current["bindings_digest"] != owner["bindings_digest"]:
        raise PolicyError("New condition does not bind current admission")
    # Retained observations keep their original grade-time/attempt bindings
    # across reconfiguration. The new admission and any rearm bind today's
    # contract; rewriting old observation bytes would erase evidence.
    if retained_event is None and current["revision"] != coverage["head_revision"] + 1:
        raise PolicyError("New condition must occupy the next admitted revision")
    if retained_event is not None and retained_event != current:
        raise PolicyError("Current condition conflicts with its retained native event")
    if any(item["revision"] > current["revision"] and item["obligation_id"] == current["obligation_id"]
           for item in attempts):
        raise PolicyError("Current condition predates later retained work")
    all_attempts = _dedupe_attempts(attempts + [current])
    all_buckets, consumed = _replay(all_attempts, rearms)
    relevant = {key: value for key, value in all_buckets.items()
                if value["latest"]["obligation_id"] == current["obligation_id"]}
    # The full history is retained and validated, including independent nodes.
    cancelled = owner["cancelled"] or any(item["family"] == "cancelled" and item["obligation_id"] == current["obligation_id"]
                                         for item in all_attempts)
    accepted_rearm = None
    latest_bucket = max(relevant.values(), key=lambda item: item["latest"]["revision"], default=None)

    def answer(action: str, reason: str, *, allow: bool = False, bucket: dict | None = None,
               requirements: tuple[str, ...] = (), basis: str = "blocked") -> dict:
        selected = bucket or latest_bucket
        latest = selected["latest"] if selected else current
        epoch = selected["epoch"] if selected else 0
        failed = sum(len(item["attempts"]) for item in relevant.values())
        diagnostic_family = latest["family"] if reason in {
            "bounded_transient_retry", "unchanged_failure", "verified_rearm"} else reason
        diagnostic = _digest({"run_id": current["run_id"], "obligation_id": current["obligation_id"],
            "failure_id": latest["failure_id"], "condition_epoch": epoch,
            "family": diagnostic_family})
        correction = _digest({"run_id": current["run_id"], "obligation_id": current["obligation_id"],
            "failure_id": latest["failure_id"], "condition_epoch": epoch, "basis": basis,
            "condition_digest": current["condition_digest"] if basis == "progress" else latest["condition_digest"],
            "strategy_key": current["strategy_key"] if basis == "progress" else latest["strategy_key"],
            "epoch_failures": len(selected["epoch_attempts"]) if selected else 0})
        result = {"schema_version": SCHEMA, "run_id": current["run_id"], "obligation_id": current["obligation_id"],
            "revision": max(coverage["head_revision"], current["revision"],
                            accepted_rearm["revision"] if accepted_rearm else 0),
            "bindings_digest": owner["bindings_digest"],
            "journal_head_digest": coverage["head_digest"], "journal_revision": coverage["head_revision"],
            "admission_digest": _digest(owner),
            "history_digest": coverage["projection_digest"], "failure_id": latest["failure_id"],
            "diagnostic_id": diagnostic, "correction_id": correction, "condition_epoch": epoch,
            "action": action, "reason_code": reason, "allow_attempt": allow, "emit_diagnostic": basis != "progress",
            "not_before": None, "rearm_requirements": list(requirements),
            "evidence_ids": sorted(set(current["evidence_ids"] + owner["evidence_ids"] + [coverage["evidence_id"]])),
            "continuation_cleanup_required": not allow, "failed_attempts": failed,
            "epoch_failures": len(selected["epoch_attempts"]) if selected else 0,
            "accepted_rearm": copy.deepcopy(accepted_rearm), "basis": basis,
            "authority_granted": False, "completion_granted": False}
        result["decision_digest"] = _digest(result)
        return result

    if cancelled:
        return answer("cancelled", "cancelled")
    if owner["terminal"]:
        return answer("wait", "terminal_run")
    for field, expected, reason in (("identity", "verified", "malformed_identity"),
        ("runtime", "verified", "runtime_dependency"), ("ownership", "admitted", "ownership_stale_or_foreign"),
        ("authority", "admitted", "policy_denial")):
        if owner[field] != expected:
            return answer("wait", reason, requirements=(reason,))
    if owner["resources"] != "available":
        return answer("resource_exhausted" if owner["resources"] == "exhausted" else "wait", "resource_" + owner["resources"])
    if owner["storage"] != "available":
        return answer("wait", "storage_" + owner["storage"])
    if coverage["status"] != "complete" or current["coverage"]["status"] != "complete":
        return answer("wait", "coverage_unknown", requirements=("complete_source_coverage",))
    if rearm is not None:
        if retained_event is None:
            raise PolicyError("Rearm requires a committed retained prior observation")
        candidate = _rearm(rearm)
        if (candidate["run_id"] != current["run_id"] or candidate["obligation_id"] != current["obligation_id"]
                or candidate["bindings_digest"] != owner["bindings_digest"]
                or candidate["revision"] != coverage["head_revision"] + 1):
            raise PolicyError("Rearm does not bind this run, admission and next revision")
        bucket = relevant.get(candidate["failure_id"])
        if bucket is None:
            raise PolicyError("Rearm requires its retained failure")
        if candidate["event_id"] in {item["event_id"] for item in all_attempts + rearms}:
            raise PolicyError("Rearm native event identity is already retained")
        _admit_rearm(candidate, bucket, consumed)
        accepted_rearm = candidate
    if owner["unresolved_effect_ids"]:
        return answer("reconcile", "ambiguous_effect", requirements=("effect_owner_readback",))
    # A stronger restriction wins over any eligible retry in another family.
    eligible = []
    for bucket in sorted(relevant.values(), key=lambda item: item["latest"]["revision"], reverse=True):
        latest = bucket["latest"]
        family, count = latest["family"], len(bucket["epoch_attempts"])
        last_rearm = bucket["last_rearm"]
        if count == 0 and last_rearm and latest["revision"] < last_rearm["revision"]:
            if family == "ambiguous_effect" and last_rearm["effect_status"] in {"confirmed", "cancelled"}:
                return answer("wait", "effect_already_resolved", bucket=bucket)
            eligible.append((bucket, "repair" if family in QUALITY else "retry", "rearm"))
            continue
        if family == "ambiguous_effect":
            return answer("reconcile", family, bucket=bucket, requirements=("effect_owner_readback",))
        if family in QUALITY:
            return answer("repair", family, bucket=bucket, requirements=("exact_quality_resolution",))
        if family not in TRANSIENT:
            return answer("wait", family, bucket=bucket, requirements=("owning_condition_resolution",))
        if latest["outcome"] == "blocked":
            return answer("wait", family, bucket=bucket, requirements=("owning_condition_resolution",))
        if count >= 2:
            return answer("quarantined", "unchanged_failure", bucket=bucket, requirements=("verified_rearm",))
        eligible.append((bucket, "retry", "bounded_retry"))
    if accepted_rearm is not None:
        bucket = relevant[accepted_rearm["failure_id"]]
        return answer("repair" if bucket["latest"]["family"] in QUALITY else "retry", "verified_rearm",
                      allow=True, bucket=bucket, basis="rearm")
    if current["family"] == "productive_work":
        return answer("continue", "productive_work", allow=True, basis="progress")
    if eligible:
        bucket, action, basis = eligible[0]
        return answer(action, "verified_rearm" if basis == "rearm" else "bounded_transient_retry",
                      allow=True, bucket=bucket, basis=basis)
    return answer("wait", "coverage_unknown", requirements=("typed_condition_evidence",))


def _decision(value: Any) -> dict:
    fields = {"schema_version", "run_id", "obligation_id", "revision", "bindings_digest", "history_digest",
        "journal_head_digest", "journal_revision", "admission_digest",
        "failure_id", "diagnostic_id", "correction_id", "condition_epoch", "action", "reason_code", "allow_attempt",
        "emit_diagnostic", "not_before", "rearm_requirements", "evidence_ids", "continuation_cleanup_required",
        "failed_attempts", "epoch_failures", "accepted_rearm", "basis", "authority_granted", "completion_granted",
        "decision_digest"}
    _object(value, fields)
    for key in ("run_id", "obligation_id", "reason_code"):
        _id(value[key])
    for key in ("bindings_digest", "history_digest", "journal_head_digest", "admission_digest",
                "diagnostic_id", "correction_id", "decision_digest"):
        _hash(value[key])
    if value["failure_id"] is not None:
        _hash(value["failure_id"])
    for key in ("revision", "journal_revision", "condition_epoch", "failed_attempts", "epoch_failures"):
        _integer(value[key])
    for key in ("allow_attempt", "emit_diagnostic", "continuation_cleanup_required"):
        if type(value[key]) is not bool:
            raise PolicyError("Stop decision requires exact booleans")
    _choice(value["action"], {"continue", "retry", "repair", "wait", "reconcile", "quarantined", "cancelled", "resource_exhausted"})
    _choice(value["basis"], {"progress", "bounded_retry", "rearm", "blocked"})
    _refs(value["rearm_requirements"], nonempty=False)
    _refs(value["evidence_ids"], maximum=MAX_REFERENCES * 2 + 1)
    if value["accepted_rearm"] is not None:
        _rearm(value["accepted_rearm"])
    if (value["authority_granted"] is not False or value["completion_granted"] is not False
            or value["not_before"] is not None
            or value["epoch_failures"] > value["failed_attempts"]
            or value["revision"] < value["journal_revision"]
            or value["continuation_cleanup_required"] == value["allow_attempt"]
            or value["emit_diagnostic"] == (value["basis"] == "progress")
            or value["decision_digest"] != _digest({key: item for key, item in value.items() if key != "decision_digest"})):
        raise PolicyError("Stop decision is internally inconsistent")
    allowed = {
        ("continue", "productive_work", "progress"),
        ("retry", "bounded_transient_retry", "bounded_retry"),
        ("retry", "verified_rearm", "rearm"),
        ("repair", "verified_rearm", "rearm"),
    }
    if value["allow_attempt"]:
        if (value["action"], value["reason_code"], value["basis"]) not in allowed or value["rearm_requirements"]:
            raise PolicyError("Stop decision cannot authorize its requested correction")
    elif value["basis"] != "blocked" or value["action"] in {"continue", "retry"}:
        raise PolicyError("Blocked decision contains an affirmative disposition")
    return value


def _current_readback(value: Any, decision: dict, session_id: str) -> bool:
    """An ephemeral verified owner projection, never read from the latch file."""
    if value is None:
        return False
    _object(value, {"schema_version", "status", "run_id", "native_session_id", "bindings_digest",
        "decision_digest", "admission_digest", "journal_head_digest", "journal_revision", "history_digest",
        "cancelled", "terminal", "evidence_id"})
    _choice(value["status"], {"verified", "unknown"})
    for key in ("run_id", "evidence_id"):
        _id(value[key])
    _text(value["native_session_id"])
    for key in ("bindings_digest", "decision_digest", "admission_digest", "journal_head_digest", "history_digest"):
        _hash(value[key])
    _integer(value["journal_revision"])
    for key in ("cancelled", "terminal"):
        if type(value[key]) is not bool:
            raise PolicyError("Owner Stop readback requires exact booleans")
    return (value["status"] == "verified" and not value["cancelled"] and not value["terminal"]
            and value["native_session_id"] == session_id
            and all(value[key] == decision[key] for key in ("run_id", "bindings_digest", "decision_digest",
                    "admission_digest", "journal_head_digest", "journal_revision", "history_digest")))


def stop_disposition(decision: dict | None, native_event: dict, latch_status: dict) -> dict:
    """Return host-neutral feedback; only the existing emitter writes the wire.

    A corrective return must be atomically consumed by correction_id before the
    host receives it. The latch records denials/consumption, never authority.
    Native repeat bits and fresh turn IDs cannot bypass consumed corrections.
    """
    event_name = native_event.get("hook_event_name") if isinstance(native_event, dict) else None
    result = {"schema_version": SCHEMA, "action": "terminal", "allow_attempt": False,
              "emit_diagnostic": True, "diagnostic_id": None, "correction_id": None,
              "reason_code": "unverified_stop", "authority_granted": False, "completion_granted": False}
    if event_name in {"PreToolUse", "PermissionRequest"}:
        return {**result, "action": "deny", "reason_code": "premutation_guard"}
    if event_name not in {"Stop", "SubagentStop"} or type(native_event.get("stop_hook_active")) is not bool:
        return result
    try:
        _text(native_event.get("session_id"))
    except PolicyError:
        return result
    if decision is None:
        return {**result, "reason_code": "runtime_dependency"}
    _decision(decision)
    _object(latch_status, {"schema_version", "status", "run_id", "diagnostic_ids", "correction_ids", "quarantined", "owner_readback"})
    _id(latch_status["run_id"])
    _choice(latch_status["status"], {"verified", "reconstructed", "missing", "corrupt", "unwritable", "unknown"})
    diagnostics = _refs(latch_status["diagnostic_ids"], nonempty=False, hashes=True, maximum=MAX_HISTORY_RECORDS)
    corrections = _refs(latch_status["correction_ids"], nonempty=False, hashes=True, maximum=MAX_HISTORY_RECORDS)
    if not isinstance(latch_status["quarantined"], list) or len(latch_status["quarantined"]) > MAX_HISTORY_RECORDS:
        raise PolicyError("Invalid latch storage capacity")
    result.update(diagnostic_id=decision["diagnostic_id"], correction_id=decision["correction_id"],
                  emit_diagnostic=decision["emit_diagnostic"] and decision["diagnostic_id"] not in diagnostics,
                  reason_code=decision["reason_code"])
    if latch_status["status"] not in {"verified", "reconstructed"} or latch_status["run_id"] != decision["run_id"]:
        return {**result, "reason_code": "unverified_latch", "emit_diagnostic": True}
    if (decision["revision"] != decision["journal_revision"] or decision["accepted_rearm"] is not None
            or not _current_readback(latch_status["owner_readback"], decision, native_event["session_id"])):
        return {**result, "reason_code": "unverified_current_decision"}
    for item in latch_status["quarantined"]:
        _object(item, {"failure_id", "condition_epoch"})
        _hash(item["failure_id"])
        _integer(item["condition_epoch"])
        if item["failure_id"] == decision["failure_id"] and item["condition_epoch"] >= decision["condition_epoch"]:
            return {**result, "reason_code": "quarantined"}
    if not decision["allow_attempt"] or decision["correction_id"] in corrections:
        return result
    # The native bit is not a run-wide failure counter. At this point fresh
    # owner readback and durable non-consumption establish this exact grant;
    # earlier successful corrections cannot spend a new failure's allowance.
    # Without those proofs we already returned terminal, regardless of the bit.
    return {**result, "action": "corrective", "allow_attempt": True}
