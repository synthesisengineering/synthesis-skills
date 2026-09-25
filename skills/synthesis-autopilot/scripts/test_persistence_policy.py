"""Consumer scenarios for pure persistence admission; no native I/O is claimed."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

import persistence_policy as policy


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def observed(number=1, *, outcome="failure", family="transient_tool", facts=None,
             strategy=None, obligation="criterion-a", task="task-a", **changes):
    raw = {
        "schema_version": 1, "run_id": "run-a", "task_id": task, "obligation_id": obligation,
        "attempt_id": f"attempt-{number}", "event_id": f"event-{number}", "revision": number,
        "source_digest": sha(["native", number]), "bindings_digest": sha("binding"),
        "outcome": outcome, "subject_digest": sha("consumer-target"),
        "strategy": strategy or {"method_digest": sha("method"), "intervention_digest": sha("intervention"),
                                 "discriminator_digest": sha("discriminator"), "rationale_ref": "plan-rationale"},
        "relevant_state": {"facts": {"service": "unavailable"} if facts is None else facts,
                           "evidence_ids": [f"state-{number}"]},
        "evidence_ids": [f"proof-{number}"], "failure_family": family,
        "effect_id": "effect-a" if family == "ambiguous_effect" else None,
        "grade_digest": sha(["grade", number]) if family in {"quality_failure", "review_disagreement"} else None,
    }
    if outcome in {"artifact", "evidence", "cancelled"}:
        raw["failure_family"] = None
    raw.update(changes)
    coverage = {"schema_version": 1, "status": "complete", "event_id": raw["event_id"],
                "source_digest": raw["source_digest"], "generation": "generation-a", "evidence_id": "coverage-proof"}
    return policy.classify_failure(raw, coverage)


def history(attempts=(), rearms=(), *, status="complete"):
    attempts, rearms = list(attempts), list(rearms)
    revision = max([0, *(x["revision"] for x in attempts), *(x["revision"] for x in rearms)])
    return {"schema_version": 1, "attempts": attempts, "rearms": rearms,
            "coverage": {"schema_version": 1, "status": status, "scope": "full_run",
                "run_id": "run-a", "head_revision": revision, "head_digest": sha(["journal", revision]),
                "attempt_count": len(attempts), "rearm_count": len(rearms),
                "projection_digest": sha({"attempts": attempts, "rearms": rearms}),
                "evidence_id": "journal-coverage-proof"}}


def admission(hist, **changes):
    value = {"schema_version": 1, "run_id": "run-a", "bindings_digest": sha("binding"),
             "journal_head_digest": hist["coverage"]["head_digest"], "journal_revision": hist["coverage"]["head_revision"],
             "identity": "verified", "runtime": "verified", "ownership": "admitted", "authority": "admitted",
             "resources": "available", "storage": "available", "cancelled": False, "terminal": False,
             "unresolved_effect_ids": [], "evidence_ids": ["owner-admission-proof"]}
    value.update(changes)
    return value


def decide(condition, attempts=(), rearms=(), rearm=None, **gates):
    hist = history(attempts, rearms)
    return policy.decide_attempt(condition, hist, rearm, admission(hist, **gates))


def rearm_for(condition, revision, *, kind="state_change", facts=None, strategy=None, **changes):
    result = {"schema_version": 1, "event_id": f"rearm-{revision}", "source_digest": sha(["rearm-source", revision]),
        "revision": revision, "run_id": condition["run_id"], "obligation_id": condition["obligation_id"],
        "bindings_digest": sha("binding"), "failure_id": condition["failure_id"],
        "prior_failure_digest": condition["failure_digest"], "prior_attempt_id": condition["attempt_id"],
        "kind": kind, "strategy": copy.deepcopy(strategy or condition["strategy"]),
        "relevant_state": {"facts": {"service": "available"} if facts is None else facts,
                           "evidence_ids": [f"readback-{revision}"]},
        "evidence_ids": [f"rearm-evidence-{revision}"], "effect_id": condition["effect_id"],
        "effect_status": None, "quality_resolution": None}
    if kind == "quality_repair":
        result["quality_resolution"] = {"mode": "grade_resolution", "prior_grade_digest": condition["grade_digest"],
                                        "receipt_id": f"resolution-{revision}", "digest": sha(["resolution", revision])}
    result.update(changes)
    return result


def latch(decision=None, **changes):
    value = {"schema_version": 1, "status": "verified", "run_id": "run-a",
             "diagnostic_ids": [], "correction_ids": [], "quarantined": [],
             "owner_readback": None}
    if decision is not None:
        value["owner_readback"] = {
            "schema_version": 1, "status": "verified", "run_id": "run-a",
            "native_session_id": "native-a", "bindings_digest": decision["bindings_digest"],
            "decision_digest": decision["decision_digest"], "admission_digest": decision["admission_digest"],
            "journal_head_digest": decision["journal_head_digest"], "journal_revision": decision["journal_revision"],
            "history_digest": decision["history_digest"], "cancelled": False, "terminal": False,
            "evidence_id": "current-owner-readback"}
    value.update(changes)
    return value


def stop_event(**changes):
    return {"hook_event_name": "Stop", "session_id": "native-a", "stop_hook_active": False, **changes}


def committed(condition, attempts=(), rearms=()):
    """The owner has committed the observation before consulting Stop."""
    return decide(condition, [*attempts, condition], rearms)


def test_twelve_then_thirty_two_meaningful_results_do_not_exhaust_failure_allowance():
    retained = []
    for index in range(1, 33):
        item = observed(index, outcome="evidence", facts={"measured": index})
        decision = decide(item, retained)
        assert decision["allow_attempt"] is True
        assert decision["action"] == "continue"
        assert decision["failed_attempts"] == 0
        retained.append(item)
    assert len(retained) == 32


def test_initial_failure_gets_one_correction_then_quarantine_without_wording_identity():
    first, second = observed(), observed(2, summary="The same outage, described differently")
    assert decide(first)["action"] == "retry"
    result = decide(second, [first])
    assert result["action"] == "quarantined"
    assert result["failed_attempts"] == 2
    assert result["allow_attempt"] is False


def test_one_diagnostic_identity_covers_all_unchanged_failures_in_an_epoch():
    first, second = observed(), observed(2)
    third = observed(3, summary="A new wording does not create a new diagnostic")
    decisions = [decide(first), decide(second, [first]), decide(third, [first, second])]
    assert len({item["diagnostic_id"] for item in decisions}) == 1
    accepted = decide(third, [first, second, third], rearm=rearm_for(third, 4))
    assert accepted["diagnostic_id"] != decisions[0]["diagnostic_id"]


def test_successful_evidence_does_not_reset_or_spend_an_existing_failure_allowance():
    first = observed()
    useful = observed(2, outcome="evidence", facts={"service": "unavailable"})
    result = decide(useful, [first])
    assert result["failed_attempts"] == 1
    second_failure = observed(3)
    assert decide(second_failure, [first, useful])["action"] == "quarantined"


def test_native_event_alias_and_multiple_results_for_one_attempt_charge_once():
    first = observed()
    alias = observed(2, attempt_id=first["attempt_id"])
    assert decide(alias, [first])["failed_attempts"] == 1
    assert decide(first, [first])["failed_attempts"] == 1


def test_task_rename_new_binding_and_state_cosmetics_cannot_reset_quarantine():
    first, second = observed(), observed(2)
    same = observed(3, task="renamed-after-reconfigure", bindings_digest=sha("new-binding"),
                    strategy={**first["strategy"], "rationale_ref": "new-wording"})
    result = decide(same, [first, second], bindings_digest=sha("new-binding"))
    assert result["failure_id"] == first["failure_id"]
    assert result["action"] == "quarantined"
    assert result["failed_attempts"] == 3


def test_independent_obligation_remains_ready_next_to_quarantined_work():
    first, second = observed(), observed(2)
    other = observed(3, outcome="artifact", obligation="criterion-b", facts={"output": "ready"})
    assert decide(other, [first, second])["allow_attempt"] is True


def test_changed_state_rearm_is_bound_consumed_and_keeps_all_failure_counts():
    first, second = observed(), observed(2)
    retry = rearm_for(second, 3)
    result = decide(second, [first, second], rearm=retry)
    assert result["allow_attempt"] is True
    assert result["condition_epoch"] == 1
    assert result["failed_attempts"] == 2
    assert result["epoch_failures"] == 0
    admitted = result["accepted_rearm"]
    later = observed(4)
    next_result = decide(later, [first, second], [admitted])
    assert next_result["failed_attempts"] == 3
    assert next_result["epoch_failures"] == 1
    assert next_result["action"] == "retry"
    with pytest.raises(policy.PolicyError, match="consum|replay|revision|latest"):
        decide(later, [first, second, later], [admitted], rearm={**retry, "event_id": "receipt-alias", "revision": 5})


@pytest.mark.parametrize("change", ["wording", "same_facts", "wrong_prior", "drop_fact", "old_binding"])
def test_rearm_rejects_cosmetics_missing_cause_and_wrong_failure(change):
    first = observed(facts={"service": "unavailable", "region": "a"})
    retry = rearm_for(first, 2, facts={"service": "unavailable", "region": "a"})
    if change == "wording":
        retry["strategy"]["rationale_ref"] = "new-description"
    elif change == "wrong_prior":
        retry["prior_failure_digest"] = "0" * 64
    elif change == "drop_fact":
        retry["relevant_state"]["facts"] = {"service": "available"}
    elif change == "old_binding":
        retry["bindings_digest"] = "0" * 64
    with pytest.raises(policy.PolicyError):
        decide(first, [first], rearm=retry)


def test_informed_changed_strategy_admits_a_different_discriminator():
    first = observed(family="permanent_tool")
    assert decide(first)["allow_attempt"] is False
    strategy = {**first["strategy"], "method_digest": sha("different-method"),
                "discriminator_digest": sha("different-measurable-test"), "rationale_ref": "source-backed-plan"}
    retry = rearm_for(first, 2, kind="strategy_change", facts=first["relevant_state"]["facts"], strategy=strategy)
    assert decide(first, [first], rearm=retry)["allow_attempt"] is True


def test_four_quality_generations_allow_three_exact_evidence_bound_repairs():
    attempts, rearms = [], []
    revision = 1
    for remaining in (["a", "b", "c"], ["b", "c"], ["c"]):
        grade = observed(revision, family="quality_failure", facts={"failed_findings": remaining})
        attempts.append(grade)
        assert decide(grade, attempts, rearms)["allow_attempt"] is False
        retry = rearm_for(grade, revision + 1, kind="quality_repair", facts={"failed_findings": remaining[1:]})
        result = decide(grade, attempts, rearms, rearm=retry)
        assert result["action"] == "repair" and result["allow_attempt"] is True
        rearms.append(result["accepted_rearm"])
        revision += 2
    passed = observed(revision, outcome="artifact", facts={"failed_findings": []})
    result = decide(passed, attempts, rearms)
    assert result["allow_attempt"] is True
    assert result["failed_attempts"] == 3
    assert len(attempts) == len(rearms) == 3


def test_quality_rearm_requires_existing_owner_resolution_of_exact_failed_grade():
    first = observed(family="quality_failure", facts={"failed_findings": ["a"]})
    retry = rearm_for(first, 2, kind="quality_repair", facts={"failed_findings": []})
    retry["quality_resolution"]["prior_grade_digest"] = sha("another-grade")
    with pytest.raises(policy.PolicyError, match="grade"):
        decide(first, [first], rearm=retry)


@pytest.mark.parametrize("family", ["runtime_dependency", "malformed_identity", "ownership_stale_or_foreign",
                                   "policy_denial", "human_input", "permanent_tool", "unclassified"])
def test_nontransient_families_never_receive_a_blind_retry(family):
    assert decide(observed(family=family))["allow_attempt"] is False


@pytest.mark.parametrize("gate,value,action", [("cancelled", True, "cancelled"), ("terminal", True, "wait"),
    ("identity", "missing", "wait"), ("runtime", "missing", "wait"), ("ownership", "foreign", "wait"),
    ("authority", "denied", "wait"), ("resources", "exhausted", "resource_exhausted"),
    ("resources", "unknown", "wait"), ("storage", "exhausted", "wait")])
def test_current_owner_gates_precede_progress_and_rearm(gate, value, action):
    result = decide(observed(outcome="artifact", facts={"output": "ready"}), **{gate: value})
    assert result["allow_attempt"] is False and result["action"] == action
    assert result["failed_attempts"] == 0


def test_cancellation_tombstone_cannot_be_erased_by_later_owner_boolean():
    cancelled = observed(outcome="cancelled")
    later = observed(2, outcome="artifact")
    assert decide(later, [cancelled], cancelled=False)["action"] == "cancelled"


def test_effect_ambiguity_survives_other_progress_and_changed_strategy():
    first = observed(family="ambiguous_effect", outcome="ambiguous_effect")
    retry = rearm_for(first, 2, kind="strategy_change", strategy={**first["strategy"], "method_digest": sha("new")})
    with pytest.raises(policy.PolicyError, match="effect"):
        decide(first, [first], rearm=retry)
    result = decide(observed(2, outcome="artifact"), [first], unresolved_effect_ids=["effect-a"])
    assert result["action"] == "reconcile" and result["allow_attempt"] is False


def test_reconciled_absent_effect_is_retryable_but_confirmed_effect_is_not_reissued():
    first = observed(outcome="ambiguous_effect", family="ambiguous_effect")
    retry = rearm_for(first, 2, kind="effect_reconciled", effect_status="absent")
    assert decide(first, [first], rearm=retry)["allow_attempt"] is True
    confirmed = {**retry, "effect_status": "confirmed"}
    assert decide(first, [first], rearm=confirmed)["allow_attempt"] is False


@pytest.mark.parametrize("status", ["incomplete", "conflict", "unknown"])
def test_incomplete_run_projection_cannot_exonerate_history(status):
    item = observed(outcome="artifact")
    hist = history(status=status)
    result = policy.decide_attempt(item, hist, None, admission(hist))
    assert result["allow_attempt"] is False
    assert result["reason_code"] == "coverage_unknown"


@pytest.mark.parametrize("mutation", ["boolean_only", "count", "digest", "head", "source_conflict"])
def test_internally_inconsistent_history_is_rejected(mutation):
    item = observed()
    hist = history([item])
    owner = admission(hist)
    if mutation == "boolean_only":
        hist["coverage"] = {"complete": True}
    elif mutation == "count":
        hist["coverage"]["attempt_count"] += 1
    elif mutation == "digest":
        hist["coverage"]["projection_digest"] = "0" * 64
    elif mutation == "head":
        owner["journal_head_digest"] = "0" * 64
    else:
        altered = observed(2, event_id=item["event_id"])
        hist = history([item, altered])
        owner = admission(hist)
    with pytest.raises(policy.PolicyError):
        policy.decide_attempt(item, hist, None, owner)


def test_decision_and_inputs_are_pure_and_cannot_grant_authority():
    item = observed()
    hist = history()
    owner = admission(hist)
    before = copy.deepcopy((item, hist, owner))
    result = policy.decide_attempt(item, hist, None, owner)
    assert (item, hist, owner) == before
    assert result["authority_granted"] is False and result["completion_granted"] is False


def test_stop_correction_is_single_use_across_fresh_native_wakes():
    decision = committed(observed())
    first = policy.stop_disposition(decision, stop_event(), latch(decision))
    assert first["action"] == "corrective"
    consumed = latch(decision, correction_ids=[first["correction_id"]], diagnostic_ids=[first["diagnostic_id"]])
    repeated = policy.stop_disposition(decision, stop_event(stop_hook_active=True), consumed)
    new_wake = policy.stop_disposition(decision, stop_event(), consumed)
    assert repeated["action"] == new_wake["action"] == "terminal"
    assert repeated["emit_diagnostic"] is new_wake["emit_diagnostic"] is False


def test_stop_productive_progress_can_continue_beyond_native_repeat_bit():
    first = observed(outcome="artifact", facts={"artifact": "one"})
    first_decision = committed(first)
    emitted = policy.stop_disposition(first_decision, stop_event(), latch(first_decision))
    second = observed(2, outcome="artifact", facts={"artifact": "two"})
    decision = committed(second, [first])
    result = policy.stop_disposition(decision, stop_event(stop_hook_active=True),
                                      latch(decision, correction_ids=[emitted["correction_id"]]))
    assert result["action"] == "corrective"


def test_new_source_identity_without_new_progress_cannot_reinject_stop():
    first = observed(outcome="evidence", facts={"artifact": "one"})
    first_decision = committed(first)
    emitted = policy.stop_disposition(first_decision, stop_event(), latch(first_decision))
    alias = observed(2, outcome="evidence", facts={"artifact": "one"})
    decision = committed(alias, [first])
    result = policy.stop_disposition(decision, stop_event(), latch(decision, correction_ids=[emitted["correction_id"]]))
    assert result["action"] == "terminal"


@pytest.mark.parametrize("status", ["missing", "corrupt", "unwritable", "unknown"])
def test_stop_latch_never_creates_affirmative_admission(status):
    decision = committed(observed())
    assert policy.stop_disposition(decision, stop_event(), latch(decision, status=status))["action"] == "terminal"


@pytest.mark.parametrize("native", [{}, {"hook_event_name": "Stop", "session_id": "", "stop_hook_active": False},
    {"hook_event_name": "Stop", "session_id": "native", "stop_hook_active": "false"}])
def test_stop_missing_native_identity_is_terminal(native):
    assert policy.stop_disposition(decide(observed()), native, latch())["action"] == "terminal"


@pytest.mark.parametrize("event", ["PreToolUse", "PermissionRequest"])
def test_stop_policy_cannot_authorize_or_terminalize_a_premutation_guard(event):
    result = policy.stop_disposition(decide(observed()), stop_event(hook_event_name=event), latch())
    assert result["action"] == "deny"
    assert "continue" not in result and result["allow_attempt"] is False


def test_missing_helper_can_use_terminal_bootstrap_without_an_engine_decision():
    result = policy.stop_disposition(None, stop_event(), latch())
    assert result["action"] == "terminal" and result["allow_attempt"] is False


@pytest.mark.parametrize("bad", [True, -1, 1.5, "1"])
def test_revision_is_a_bounded_integer_not_a_coerced_number(bad):
    with pytest.raises(policy.PolicyError):
        observed(revision=bad)


def test_classification_rejects_unknown_fields_and_unbounded_content():
    with pytest.raises(policy.PolicyError):
        observed(verified=True)
    with pytest.raises(policy.PolicyError):
        observed(summary="x" * 4097)


def test_replayed_source_byte_conflict_is_not_a_new_failure_family():
    with pytest.raises(policy.PolicyError):
        observed(family="new-error-wording")


def test_blocked_work_and_incomplete_positive_evidence_are_not_executed_failures():
    blocked = observed(outcome="blocked", family="human_input")
    result = decide(blocked)
    assert result["failed_attempts"] == 0 and result["allow_attempt"] is False
    positive = observed(outcome="evidence")
    raw = {key: value for key, value in positive.items() if key not in {
        "family", "failure_id", "failure_digest", "strategy_key", "condition_digest", "coverage"}}
    partial = policy.classify_failure(raw, {**positive["coverage"], "status": "incomplete"})
    result = decide(partial)
    assert result["failed_attempts"] == 0 and result["allow_attempt"] is False


def test_one_prior_failure_cannot_admit_repeated_rearms_before_another_attempt():
    first = observed()
    accepted = decide(first, [first], rearm=rearm_for(first, 2))["accepted_rearm"]
    with pytest.raises(policy.PolicyError, match="already|intervening"):
        decide(first, [first], [accepted], rearm=rearm_for(first, 3))


def test_renaming_receipt_source_cannot_reuse_rearm_evidence():
    first = observed()
    accepted = decide(first, [first], rearm=rearm_for(first, 2))["accepted_rearm"]
    failed_again = observed(3)
    replay = rearm_for(failed_again, 4, evidence_ids=accepted["evidence_ids"])
    with pytest.raises(policy.PolicyError, match="consum|replay"):
        decide(failed_again, [first, failed_again], [accepted], rearm=replay)


def test_dropping_a_nested_causal_fact_is_not_a_repair():
    first = observed(facts={"service": {"status": "down", "region": "a"}})
    retry = rearm_for(first, 2, facts={"service": {"status": "up"}})
    with pytest.raises(policy.PolicyError, match="causal"):
        decide(first, [first], rearm=retry)


def test_numeric_rendering_change_is_not_changed_causal_state():
    first = observed(facts={"version": 1})
    retry = rearm_for(first, 2, facts={"version": 1.0})
    with pytest.raises(policy.PolicyError, match="state change"):
        decide(first, [first], rearm=retry)


def test_a_rearm_cannot_be_proposed_without_a_committed_prior_observation():
    first = observed()
    with pytest.raises(policy.PolicyError, match="retained|committed"):
        decide(first, rearm=rearm_for(first, 1))


@pytest.mark.parametrize("field", ["journal_revision", "cancelled", "terminal"])
def test_owner_fields_are_exact_types(field):
    item = observed()
    hist = history([item])
    owner = admission(hist, **{field: True if field == "journal_revision" else 0})
    with pytest.raises(policy.PolicyError):
        policy.decide_attempt(item, hist, None, owner)


@pytest.mark.parametrize("field,value", [
    ("decision_digest", "0" * 64), ("journal_head_digest", "0" * 64),
    ("admission_digest", "0" * 64), ("journal_revision", 0),
    ("history_digest", "0" * 64), ("bindings_digest", "0" * 64),
    ("cancelled", True), ("terminal", True), ("status", "unknown"),
    ("native_session_id", "different-native-session")])
def test_stop_requires_current_owner_readback_not_a_cached_valid_decision(field, value):
    decision = committed(observed())
    current = latch(decision)
    current["owner_readback"][field] = value
    assert policy.stop_disposition(decision, stop_event(), current)["action"] == "terminal"


def test_stop_requires_committed_policy_input_and_readback():
    item = observed()
    pending = decide(item)
    assert policy.stop_disposition(pending, stop_event(), latch(pending))["action"] == "terminal"
    decision = committed(item)
    assert policy.stop_disposition(decision, stop_event(), latch())["action"] == "terminal"


def test_a_proposed_rearm_cannot_reinject_before_its_journal_commit():
    item = observed()
    proposed = decide(item, [item], rearm=rearm_for(item, 2))
    assert policy.stop_disposition(proposed, stop_event(), latch(proposed))["action"] == "terminal"
    admitted = proposed["accepted_rearm"]
    after_commit = decide(item, [item], [admitted])
    assert policy.stop_disposition(after_commit, stop_event(stop_hook_active=True), latch(after_commit))["action"] == "corrective"


@pytest.mark.parametrize("field,value", [
    ("condition_epoch", True), ("epoch_failures", -1), ("failed_attempts", "1"),
    ("emit_diagnostic", 1), ("continuation_cleanup_required", "false"),
    ("not_before", 0), ("action", "cancelled"), ("basis", "blocked"),
    ("reason_code", "cancelled"), ("rearm_requirements", ["x"] * 257),
    ("evidence_ids", []), ("revision", False)])
def test_self_checksummed_but_inconsistent_stop_decision_is_rejected(field, value):
    decision = committed(observed())
    decision[field] = value
    decision["decision_digest"] = sha({key: val for key, val in decision.items() if key != "decision_digest"})
    with pytest.raises(policy.PolicyError):
        policy.stop_disposition(decision, stop_event(), latch(decision))


def test_storage_capacity_error_does_not_masquerade_as_attempt_exhaustion():
    item = observed(outcome="evidence")
    hist = history([item] * (policy.MAX_HISTORY_RECORDS + 1))
    with pytest.raises(policy.PolicyError, match="storage capacity"):
        policy.decide_attempt(item, hist, None, admission(hist))


def test_unverified_latch_cannot_suppress_the_unresolved_diagnostic():
    decision = committed(observed())
    corrupt = latch(decision, status="corrupt", diagnostic_ids=[decision["diagnostic_id"]])
    result = policy.stop_disposition(decision, stop_event(), corrupt)
    assert result["action"] == "terminal" and result["emit_diagnostic"] is True


def test_state_cycling_with_reused_readback_is_not_new_evidence():
    first = observed(facts={"service": "a"})
    to_b = decide(first, [first], rearm=rearm_for(first, 2, facts={"service": "b"}))["accepted_rearm"]
    second = observed(3, facts={"service": "b"})
    to_a = rearm_for(second, 4, facts={"service": "a"})
    to_a["relevant_state"]["evidence_ids"] = to_b["relevant_state"]["evidence_ids"]
    with pytest.raises(policy.PolicyError, match="consum|replay"):
        decide(second, [first, second], [to_b], rearm=to_a)


def test_quality_resolution_proof_cannot_be_reissued_under_a_new_receipt_id():
    first = observed(family="quality_failure", facts={"issues": ["a", "b"]})
    repair = rearm_for(first, 2, kind="quality_repair", facts={"issues": ["b"]})
    admitted = decide(first, [first], rearm=repair)["accepted_rearm"]
    later = observed(3, family="quality_failure", facts={"issues": ["b"]})
    replay = rearm_for(later, 4, kind="quality_repair", facts={"issues": []})
    replay["quality_resolution"]["digest"] = admitted["quality_resolution"]["digest"]
    with pytest.raises(policy.PolicyError, match="consum|replay"):
        decide(later, [first, later], [admitted], rearm=replay)


def test_missing_prior_attempt_cannot_be_hidden_by_recomputing_projection_counts_and_hash():
    first = observed()
    accepted = decide(first, [first], rearm=rearm_for(first, 2))["accepted_rearm"]
    later = observed(3)
    with pytest.raises(policy.PolicyError, match="lost|prior"):
        decide(later, [], [accepted])


def test_distinct_attempts_need_unambiguous_causal_order_within_one_obligation():
    first = observed()
    collision = observed(2, revision=1)
    with pytest.raises(policy.PolicyError, match="revision|order"):
        decide(collision, [first, collision])


def test_cross_kind_native_event_identity_collision_is_rejected():
    first = observed()
    retry = rearm_for(first, 2, event_id=first["event_id"])
    with pytest.raises(policy.PolicyError, match="event|identity"):
        decide(first, [first], rearm=retry)


def test_policy_imports_and_classifies_without_site_packages_or_an_installed_runtime():
    script = (
        "import runpy, sys; module = runpy.run_path(sys.argv[1]); "
        "print(module['failure_key']('r', 'o', 'transient_tool', '0' * 64))"
    )
    run = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", script,
                          str(Path(policy.__file__).resolve())], text=True, capture_output=True, check=False)
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == policy.failure_key("r", "o", "transient_tool", "0" * 64)


def test_stop_readback_latch_and_decision_remain_unchanged():
    decision = committed(observed())
    current, event = latch(decision), stop_event()
    before = copy.deepcopy((decision, event, current))
    first = policy.stop_disposition(decision, event, current)
    second = policy.stop_disposition(decision, event, current)
    assert first == second
    assert (decision, event, current) == before


def test_untrusted_deep_state_is_rejected_before_copying_it():
    deeply_nested = {"leaf": "value"}
    for _ in range(2000):
        deeply_nested = {"nested": deeply_nested}
    with pytest.raises(policy.PolicyError, match="deep"):
        observed(facts=deeply_nested)


@pytest.mark.parametrize("facts", [{"value": float("nan")}, {"value": float("inf")},
                                  {"value": "\ud800"}, {"value": "x" * 4097}])
def test_state_is_bounded_finite_json(facts):
    with pytest.raises(policy.PolicyError):
        observed(facts=facts)


@pytest.mark.parametrize("family,kind", [
    ("runtime_dependency", "runtime_restored"), ("malformed_identity", "identity_restored"),
    ("ownership_stale_or_foreign", "ownership_changed"), ("policy_denial", "authority_changed"),
    ("human_input", "human_response"), ("coverage_unknown", "state_change"),
    ("unclassified", "state_change")])
def test_protected_family_requires_a_fresh_resolution_from_its_existing_owner(family, kind):
    first = observed(family=family)
    assert decide(first)["allow_attempt"] is False
    repair = rearm_for(first, 2, kind=kind)
    result = decide(first, [first], rearm=repair)
    assert result["allow_attempt"] is True and result["failed_attempts"] == 1


@pytest.mark.parametrize("gate,value", [("cancelled", True), ("terminal", True),
    ("runtime", "unverified"), ("identity", "unknown"), ("ownership", "stale"),
    ("authority", "denied"), ("resources", "unknown"), ("storage", "unknown")])
def test_new_rearm_cannot_override_current_owner_restrictions(gate, value):
    first = observed()
    result = decide(first, [first], rearm=rearm_for(first, 2), **{gate: value})
    assert result["allow_attempt"] is False and result["accepted_rearm"] is None
    assert result["condition_epoch"] == 0


@pytest.mark.parametrize("field", ["condition_epoch", "failure_count", "reset", "retry_clearances"])
def test_caller_cannot_inject_a_history_reset(field):
    first = observed()
    hist = history([first])
    hist[field] = 0
    with pytest.raises(policy.PolicyError):
        policy.decide_attempt(first, hist, None, admission(hist))


def test_conflicting_source_in_another_obligation_cannot_be_hidden_by_a_fresh_current_result():
    first = observed()
    changed_source = observed(2, event_id=first["event_id"])
    latest = observed(3, outcome="evidence", obligation="independent")
    with pytest.raises(policy.PolicyError, match="conflicting.*source"):
        decide(latest, [first, changed_source])


def test_a_corrected_outcome_cannot_replace_negative_evidence_for_the_same_attempt():
    failed = observed()
    passed_alias = observed(2, outcome="artifact", attempt_id=failed["attempt_id"])
    with pytest.raises(policy.PolicyError, match="conflicting outcome"):
        decide(passed_alias, [failed])


def test_first_failure_after_productive_native_corrections_gets_its_own_single_correction():
    useful = observed(outcome="evidence", facts={"service": "measured"})
    prior = committed(useful)
    failed = observed(2)
    current = committed(failed, [useful])
    retained = latch(current, correction_ids=[prior["correction_id"]])
    result = policy.stop_disposition(current, stop_event(stop_hook_active=True), retained)
    assert result["action"] == "corrective"
    retained["correction_ids"].append(result["correction_id"])
    assert policy.stop_disposition(current, stop_event(), retained)["action"] == "terminal"


def test_admitted_repair_plan_can_start_before_any_repaired_output_or_passing_grade_exists():
    failed = observed(family="quality_failure", facts={"failed_findings": ["a", "b"]})
    different = {**failed["strategy"], "intervention_digest": sha("patch-bound-to-findings-a-and-b"),
                 "discriminator_digest": sha("check-named-failed-criteria")}
    repair = rearm_for(failed, 2, kind="quality_repair", facts=failed["relevant_state"]["facts"], strategy=different)
    repair["quality_resolution"]["mode"] = "repair_plan"
    result = decide(failed, [failed], rearm=repair)
    assert result["action"] == "repair" and result["allow_attempt"] is True
    assert result["failed_attempts"] == 1 and result["completion_granted"] is False
    assert failed["relevant_state"]["facts"]["failed_findings"] == ["a", "b"]


def test_grade_resolution_cannot_claim_a_new_output_from_strategy_change_alone():
    failed = observed(family="quality_failure", facts={"failed_findings": ["a"]})
    repair = rearm_for(failed, 2, kind="quality_repair", facts=failed["relevant_state"]["facts"],
                       strategy={**failed["strategy"], "method_digest": sha("different")})
    with pytest.raises(policy.PolicyError, match="output|state"):
        decide(failed, [failed], rearm=repair)


def test_a_repair_plan_requires_a_changed_method_and_cannot_be_reworded():
    failed = observed(family="quality_failure", facts={"failed_findings": ["a"]})
    repair = rearm_for(failed, 2, kind="quality_repair", facts=failed["relevant_state"]["facts"])
    repair["quality_resolution"]["mode"] = "repair_plan"
    with pytest.raises(policy.PolicyError, match="approach|method"):
        decide(failed, [failed], rearm=repair)


def test_rebinding_keeps_old_observation_bytes_and_requires_current_rearm_admission():
    first, second = observed(), observed(2)
    original = copy.deepcopy([first, second])
    current_binding = sha("amended-contract")
    still_blocked = decide(second, [first, second], bindings_digest=current_binding)
    assert still_blocked["action"] == "quarantined"
    repair = rearm_for(second, 3, bindings_digest=current_binding)
    allowed = decide(second, [first, second], rearm=repair, bindings_digest=current_binding)
    assert allowed["allow_attempt"] is True and allowed["failed_attempts"] == 2
    assert [first, second] == original


def test_new_observation_cannot_be_admitted_on_old_contract_bindings():
    with pytest.raises(policy.PolicyError, match="bind"):
        decide(observed(), bindings_digest=sha("amended-contract"))
