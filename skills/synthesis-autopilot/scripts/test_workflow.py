"""Behavioral fixtures for bounded, I/O-free autopilot workflow reducers."""
from __future__ import annotations

import copy
import importlib
import importlib.util
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"))
from test_run_admission import world  # noqa: F401


@pytest.fixture
def wf():
    path = Path(__file__).with_name("workflow.py")
    spec = importlib.util.spec_from_file_location("workflow_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def state():
    return {
        "schema_version": 1, "run_id": "run-a", "project_id": "project-a",
        "revision": 0, "status": "running", "contract_revision": 1,
        "profile_revision": 1, "contract_digest": "a" * 64,
        "profile_digest": "b" * 64,
        "contract": {
            "schema_version": 1, "scope": ["local fixture"], "exclusions": ["publish"],
            "outcomes": [{"id": "o1", "description": "Correct local artifact", "criteria": ["c1", "c2"]}],
            "criteria": [
                {"id": "c1", "description": "Functional result", "required": True, "method": "test", "artifact_ids": ["a1"]},
                {"id": "c2", "description": "Consumer inspection", "required": True, "method": "consumer", "artifact_ids": ["a2"]},
            ], "authority_refs": [],
        }, "extensions": {"foreign": {"sentinel": "preserve"}},
    }


@pytest.fixture
def context():
    return {"now": "2026-01-01T00:00:00Z", "binding": {"session_uuid": "root-seat", "project_id": "project-a"},
            "admissions": {}, "evidence": {}, "verify_receipt": lambda *args: False}


def call(wf, state, context, command, **payload):
    commands = {}
    wf.register_commands(lambda name, reducer, **options: commands.setdefault(name, (reducer, options)))
    reducer, options = commands["workflow." + command]
    assert options["allowed_fields"] == ("extensions",)
    before = copy.deepcopy(state)
    result = reducer(state, payload, context)
    assert state == before, "Reducers must not mutate their input"
    assert {k: v for k, v in result.items() if k != "extensions"} == {k: v for k, v in state.items() if k != "extensions"}
    assert result["extensions"]["foreign"] == state["extensions"]["foreign"]
    return result


def dimensions(domain="software", **changes):
    return {"domains": [domain], "uncertainty": "low", "effect": "local-reversible", "horizon": "session",
            "parallelizable": True, **changes}


def configured(wf, state, context, **changes):
    return call(wf, state, context, "configure", dimensions=dimensions(**changes), layers=[])


def nodes():
    return [
        {"id": "build", "deps": [], "criteria": ["c1"], "estimate": 2},
        {"id": "inspect", "deps": ["build"], "criteria": ["c2"], "estimate": 4},
        {"id": "independent", "deps": [], "criteria": ["c2"], "estimate": 1},
    ]


def graphed(wf, state, context):
    return call(wf, configured(wf, state, context), context, "graph", nodes=nodes(), wip_limit=2)


def receipt(state, context, ident, kind, data, **bindings):
    context = copy.copy(context)
    context["evidence"] = {**context["evidence"], ident: {
        "id": ident, "kind": kind, "artifact_id": "a1", "digest": "c" * 64,
        "observed_at": context["now"], "expires_at": "2026-01-02T00:00:00Z",
        "bindings": {"run_id": state["run_id"], "contract_digest": state["contract_digest"], "profile_digest": state["profile_digest"], **bindings},
        "data": data,
    }}
    context["verify_receipt"] = lambda ident, kind, bindings: ident in context["evidence"] and context["evidence"][ident]["kind"] == kind and all(context["evidence"][ident]["bindings"].get(k) == v for k, v in bindings.items())
    return context


@pytest.mark.parametrize("domain,check", [("software", "software.behavior"), ("research", "research.sources"),
                                         ("writing", "writing.reader"), ("data", "data.reconcile"),
                                         ("browser", "browser.outcome"), ("knowledge", "knowledge.recovery"),
                                         ("operations", "operations.reconcile")])
def test_adaptive_domain_obligations_do_not_grant_authority(wf, state, context, domain, check):
    result = configured(wf, state, context, domain=domain)
    profile = result["extensions"]["workflow"]["profile"]
    assert profile["checks"][check]["status"] == "required"
    assert profile["checks"]["core.authority"]["status"] == "required"
    assert profile["authority_granted"] is False


@pytest.mark.parametrize("field,value", [("parallelizable", "yes"), ("uncertainty", "magic"), ("domains", []), ("unknown", True)])
def test_invalid_dimensions_fail_without_guessing(wf, state, context, field, value):
    with pytest.raises(ValueError):
        call(wf, state, context, "configure", dimensions=dimensions(**{field: value}), layers=[])


def test_personal_check_and_disabled_optional_provenance_survive(wf, state, context):
    result = call(wf, state, context, "configure", dimensions=dimensions(), layers=[
        {"source": "user", "checks": {"custom.lesson": {"enabled": True, "description": "Capture reusable evidence"},
                                         "optional.exploration": {"enabled": False, "reason": "User requested direct repair"}}}])
    checks = result["extensions"]["workflow"]["profile"]["checks"]
    assert checks["custom.lesson"]["status"] == "enabled"
    assert checks["custom.lesson"]["provenance"][-1]["source"] == "user"
    assert checks["optional.exploration"]["status"] == "disabled_by_instruction"
    with pytest.raises(ValueError):
        call(wf, state, context, "configure", dimensions=dimensions(), layers=[{"source": "project", "checks": {"core.authority": {"enabled": False, "reason": "Untrusted grant"}}}])


def test_live_reprofile_requires_typed_core_amendment_and_no_lost_work(wf, state, context):
    result = configured(wf, state, context)
    with pytest.raises(ValueError):
        call(wf, result, context, "configure", dimensions=dimensions(domain="research"), layers=[])
    amended = copy.deepcopy(result)
    amended["profile_revision"] += 1
    amended["profile_digest"] = "d" * 64
    result = call(wf, amended, context, "configure", dimensions=dimensions(domain="research"), layers=[], reason="Approved profile amendment")
    assert result["extensions"]["workflow_history"][0]["profile"]["checks"]["software.behavior"]["status"] == "required"


def test_graph_critical_path_wip_and_independent_ready_work(wf, state, context):
    result = graphed(wf, state, context)
    assert wf.ready_tasks(result) == ["build", "independent"]
    result = call(wf, result, context, "task", task_id="build", action="start")
    result = call(wf, result, context, "task", task_id="build", action="block", reason="Await source fixture")
    assert wf.ready_tasks(result) == ["independent"]
    with pytest.raises(ValueError):
        call(wf, result, context, "task", task_id="inspect", action="start")


@pytest.mark.parametrize("bad_nodes", [
    [{"id": "x", "deps": ["x"], "criteria": ["c1", "c2"], "estimate": 1}],
    [{"id": "x", "deps": ["missing"], "criteria": ["c1", "c2"], "estimate": 1}],
    [{"id": "x", "deps": [], "criteria": ["unapproved"], "estimate": 1}],
    [{"id": "x", "deps": [], "criteria": ["c1"], "estimate": 1}],
    [{"id": "x", "deps": [], "criteria": ["c1", "c2"], "estimate": True}],
])
def test_invalid_or_expanding_graphs_rejected(wf, state, context, bad_nodes):
    with pytest.raises(ValueError):
        call(wf, configured(wf, state, context), context, "graph", nodes=bad_nodes, wip_limit=2)


def test_graph_amendment_cannot_drop_running_or_completed_work(wf, state, context):
    result = call(wf, graphed(wf, state, context), context, "task", task_id="build", action="start")
    with pytest.raises(ValueError):
        call(wf, result, context, "graph", nodes=[nodes()[2]], wip_limit=2, reason="Rewrite")
    with pytest.raises(ValueError):
        call(wf, result, context, "graph", nodes=[{**nodes()[0], "deps": ["independent"]}, *nodes()[1:]], wip_limit=2, reason="Rewrite active node")


def test_completion_requires_bound_evidence_not_status_text(wf, state, context):
    result = call(wf, graphed(wf, state, context), context, "task", task_id="build", action="start")
    with pytest.raises(ValueError):
        call(wf, result, context, "task", task_id="build", action="complete", receipt_id="self-certified")
    context = receipt(result, context, "r1", "task_completion", {"task_id": "build", "criteria": ["c1"]})
    result = call(wf, result, context, "task", task_id="build", action="complete", receipt_id="r1")
    assert wf.ready_tasks(result) == ["inspect", "independent"]


def ledger(wf, state, context, limit=10):
    return call(wf, graphed(wf, state, context), context, "budget", limits={
        "searches": {"limit": limit, "enforcement": "hard"},
        "tokens": {"limit": None, "enforcement": "forecast"}}, deadline="2026-01-01T01:00:00Z")


def test_nested_reservations_conserve_run_limit_and_integration_headroom(wf, state, context):
    result = ledger(wf, state, context)
    result = call(wf, result, context, "reserve", reservation_id="integration", amounts={"searches": 2}, category="integration")
    result = call(wf, result, context, "reserve", reservation_id="parent", amounts={"searches": 8}, category="work")
    result = call(wf, result, context, "reserve", reservation_id="child", amounts={"searches": 6}, category="work", parent_id="parent")
    with pytest.raises(ValueError):
        call(wf, result, context, "reserve", reservation_id="sibling", amounts={"searches": 3}, category="work", parent_id="parent")
    with pytest.raises(ValueError):
        call(wf, result, context, "reserve", reservation_id="extra", amounts={"searches": 1}, category="work")
    result = call(wf, result, context, "settle", reservation_id="child", actual={"searches": 3})
    result = call(wf, result, context, "settle", reservation_id="parent", actual={"searches": 1})
    summary = wf.budget_summary(result)
    assert summary["searches"]["spent"] == 4
    assert summary["searches"]["available"] == 4
    assert summary["tokens"]["enforcement"] == "forecast"
    result = call(wf, result, context, "reserve", reservation_id="recovery", amounts={"searches": 4}, category="recovery")
    assert wf.budget_summary(result)["searches"]["available"] == 0


def test_unknown_usage_stays_reserved_until_reconciled(wf, state, context):
    result = call(wf, ledger(wf, state, context), context, "reserve", reservation_id="worker", amounts={"searches": 10}, category="work")
    result = call(wf, result, context, "settle", reservation_id="worker", actual=None)
    assert wf.budget_summary(result)["searches"]["available"] == 0
    assert wf.budget_summary(result)["searches"]["unknown_reservations"] == ["worker"]
    result = call(wf, result, context, "settle", reservation_id="worker", actual={"searches": 4})
    assert wf.budget_summary(result)["searches"]["available"] == 6
    with pytest.raises(ValueError):
        call(wf, result, context, "settle", reservation_id="worker", actual={"searches": 2})


@pytest.mark.parametrize("amount", [-1, True, 1.5, "2"])
def test_malformed_resource_units_rejected(wf, state, context, amount):
    with pytest.raises(ValueError):
        call(wf, ledger(wf, state, context), context, "reserve", reservation_id="bad", amounts={"searches": amount}, category="work")


def dispatch_ready(wf, state, context):
    result = ledger(wf, state, context)
    result = call(wf, result, context, "reserve", reservation_id="integrate", amounts={"searches": 2}, category="integration")
    result = call(wf, result, context, "reserve", reservation_id="worker", amounts={"searches": 5}, category="work")
    context = copy.deepcopy(context)
    context["admissions"] = {"child-admission": {"project_id": "project-a", "project_root": "/fixture/project", "session_uuid": "child-seat",
                                               "native_ref": "fixture:child", "claim_hash": "f" * 64, "repository": "/fixture", "branch": "feature/fixture", "paths": ["/fixture/artifact"]}}
    brief = {"child_id": "child-a", "task_id": "build", "deliverables": ["Produce artifact"], "paths": ["/fixture/artifact"],
             "criteria": ["c1"], "reservation_id": "worker", "integration_reservation_id": "integrate", "integration_owner": "root-seat",
             "admission_id": "child-admission", "return_contract": ["artifact_ids", "evidence_ids", "disposition"], "cancellation": "Preserve work and return disposition"}
    return result, context, brief


def test_dispatch_binds_fresh_child_admission_and_exact_brief(wf, state, context):
    result, context, brief = dispatch_ready(wf, state, context)
    result = call(wf, result, context, "dispatch", **brief)
    assert result["extensions"]["workflow"]["children"]["child-a"]["owner"]["session_uuid"] == "child-seat"
    assert result["extensions"]["workflow"]["children"]["child-a"]["authority_granted"] is False
    assert result["extensions"]["workflow"]["graph"]["nodes"]["build"]["status"] == "running"


@pytest.mark.parametrize("change", [{"paths": ["/fixture/foreign"]}, {"deliverables": ["x"] * 6}, {"criteria": ["c2"]},
                                     {"admission_id": "self-asserted"}, {"integration_reservation_id": "worker"}, {"integration_owner": "absent"}])
def test_dispatch_rejects_unowned_unfunded_or_expanded_brief(wf, state, context, change):
    result, context, brief = dispatch_ready(wf, state, context)
    with pytest.raises(ValueError):
        call(wf, result, context, "dispatch", **{**brief, **change})


@pytest.mark.parametrize("disposition", ["complete", "partial", "failed", "blocked", "cancelled"])
def test_all_child_returns_preserve_artifacts_and_require_integration_audit(wf, state, context, disposition):
    result, context, brief = dispatch_ready(wf, state, context)
    result = call(wf, result, context, "dispatch", **brief)
    result = call(wf, result, context, "return", child_id="child-a", disposition=disposition,
                  artifact_ids=["retained-work"], evidence_ids=[], reason="Reported worker disposition")
    child = result["extensions"]["workflow"]["children"]["child-a"]
    assert child["disposition"] == disposition
    assert child["artifact_ids"] == ["retained-work"]
    assert child["audit_status"] == "required"
    assert result["extensions"]["workflow"]["graph"]["nodes"]["build"]["status"] != "done"
    with pytest.raises(ValueError):
        call(wf, result, context, "settle", reservation_id="worker", actual={"searches": 0})


def test_integration_needs_independent_bound_evidence_and_accounts_worker_usage(wf, state, context):
    result, context, brief = dispatch_ready(wf, state, context)
    result = call(wf, result, context, "dispatch", **brief)
    result = call(wf, result, context, "return", child_id="child-a", disposition="complete", artifact_ids=["a1"], evidence_ids=["r1"], reason="Ready")
    context = receipt(result, context, "audit", "child_integration", {"child_id": "child-a", "task_id": "build", "accepted": True, "criteria": ["c1"], "artifact_ids": ["a1"], "reviewer": "root-seat", "actual": {"searches": 3}})
    result = call(wf, result, context, "integrate", child_id="child-a", receipt_id="audit")
    assert result["extensions"]["workflow"]["graph"]["nodes"]["build"]["status"] == "done"
    assert wf.budget_summary(result)["searches"]["spent"] == 3


def quality_context(state, context, *, passed=True, reviewer="independent", domain="software", calibrated=True):
    observations = {
        "software": {"expected": "ready", "observed": "ready" if passed else "broken", "consumer_verified": True},
        "research": {"sources_verified": True, "decisive_claims_verified": passed, "counterevidence_checked": True},
        "writing": {"source_fidelity": True, "reader_purpose": passed, "structure": True, "voice": True},
        "data": {"expected_rows": 3, "observed_rows": 3 if passed else 4, "expected_total": "12.50", "observed_total": "12.50", "missing_explained": True},
        "browser": {"expected_state": "saved", "observed_state": "saved" if passed else "unchanged", "independent_readback": True},
        "knowledge": {"expected_hashes": {"record": "abc"}, "recovered_hashes": {"record": "abc" if passed else "bad"}, "foreign_preserved": True},
        "operations": {"expected_state": "settled", "observed_state": "settled" if passed else "ambiguous", "effects_reconciled": True},
    }[domain]
    return receipt(state, context, "q1", "quality_observation", {
        "domain": domain, "criterion_id": "c1", "artifact_id": "a1", "rubric": "behavior-v1", "passed": passed,
        "method": "consumer", "producer": "worker", "reviewer": reviewer, "calibrated": calibrated,
        "findings": [] if passed else ["Consumer output disagrees with expected result"], "independent": True,
        "observations": observations})


def test_quality_pass_fail_and_unknown_are_distinct(wf, state, context):
    result = configured(wf, state, context)
    for passed, verdict in [(True, "PASS"), (False, "FAIL")]:
        observed = call(wf, result, quality_context(result, context, passed=passed), "grade", criterion_id="c1", receipt_ids=["q1"], independent=True)
        assert observed["extensions"]["workflow"]["quality"]["c1"]["verdict"] == verdict
    observed = call(wf, result, context, "grade", criterion_id="c1", receipt_ids=[], independent=True)
    assert observed["extensions"]["workflow"]["quality"]["c1"]["verdict"] == "UNKNOWN"


@pytest.mark.parametrize("domain", ["software", "research", "writing", "data", "browser", "knowledge", "operations"])
@pytest.mark.parametrize("passed", [True, False])
def test_domain_evaluators_detect_seeded_defects_and_pass_sound_work(wf, state, context, domain, passed):
    result = configured(wf, state, context, domain=domain)
    context = quality_context(result, context, domain=domain, passed=passed)
    result = call(wf, result, context, "grade", criterion_id="c1", receipt_ids=["q1"], independent=True)
    assert result["extensions"]["workflow"]["quality"]["c1"]["verdict"] == ("PASS" if passed else "FAIL")


def test_claimed_quality_pass_cannot_override_measured_consumer_failure(wf, state, context):
    result = configured(wf, state, context)
    context = quality_context(result, context, passed=False)
    context["evidence"]["q1"]["data"]["passed"] = True
    result = call(wf, result, context, "grade", criterion_id="c1", receipt_ids=["q1"], independent=True)
    assert result["extensions"]["workflow"]["quality"]["c1"]["verdict"] == "FAIL"


@pytest.mark.parametrize("changes", [{"reviewer": "worker"}, {"calibrated": False, "domain": "writing"}])
def test_consensus_or_uncalibrated_semantic_grade_cannot_certify(wf, state, context, changes):
    result = configured(wf, state, context)
    context = quality_context(result, context, **changes)
    observed = call(wf, result, context, "grade", criterion_id="c1", receipt_ids=["q1"], independent=True)
    assert observed["extensions"]["workflow"]["quality"]["c1"]["verdict"] == "UNKNOWN"


def test_quality_disagreement_is_visible_and_resolution_is_bounded(wf, state, context):
    result = configured(wf, state, context)
    context = quality_context(result, context)
    negative = {**context["evidence"]["q1"]["data"], "passed": False, "findings": ["Seeded defect"], "observations": {"expected": "ready", "observed": "broken", "consumer_verified": True}}
    context = receipt(result, context, "q2", "quality_observation", negative)
    result = call(wf, result, context, "grade", criterion_id="c1", receipt_ids=["q1", "q2"], independent=True)
    assert result["extensions"]["workflow"]["quality"]["c1"]["verdict"] == "DISAGREEMENT"
    with pytest.raises(ValueError):
        call(wf, result, context, "grade", criterion_id="c1", receipt_ids=["q1"], independent=True)


def test_reworded_progress_is_not_progress_and_retry_is_bounded(wf, state, context):
    result = graphed(wf, state, context)
    payload = {"task_id": "build", "attempt_id": "attempt-1", "input_digest": "1" * 64, "output_digest": "2" * 64,
               "evidence_ids": [], "outcome": "transient_failure", "summary": "Connection unavailable"}
    result = call(wf, result, context, "progress", **payload)
    assert wf.retry_decision(result, "build")["action"] == "retry"
    result = call(wf, result, context, "progress", **{**payload, "attempt_id": "attempt-2", "summary": "Still unavailable, trying again"})
    decision = wf.retry_decision(result, "build")
    assert decision["action"] == "wait"
    assert decision["condition"]
    assert result["extensions"]["workflow"]["progress"]["build"][-1]["meaningful"] is False
    assert wf.ready_tasks(result) == ["independent"]


@pytest.mark.parametrize("outcome,action", [("ambiguous_effect", "reconcile"), ("authority_blocked", "wait"), ("permanent_failure", "change_strategy")])
def test_nontransient_failure_never_gets_blind_retry(wf, state, context, outcome, action):
    result = graphed(wf, state, context)
    result = call(wf, result, context, "progress", task_id="build", attempt_id="a", input_digest="1" * 64,
                  output_digest="2" * 64, evidence_ids=[], outcome=outcome, summary="Evidence required")
    assert wf.retry_decision(result, "build")["action"] == action


def test_useful_negative_evidence_counts_but_unverified_evidence_does_not(wf, state, context):
    result = graphed(wf, state, context)
    payload = {"task_id": "build", "attempt_id": "a", "input_digest": "1" * 64, "output_digest": "2" * 64,
               "evidence_ids": ["e1"], "outcome": "evidence", "summary": "Bounded source contradicts hypothesis"}
    with pytest.raises(ValueError):
        call(wf, result, context, "progress", **payload)
    context = receipt(result, context, "e1", "progress_observation", {"task_id": "build", "negative_finding": True})
    result = call(wf, result, context, "progress", **payload)
    assert result["extensions"]["workflow"]["progress"]["build"][-1]["meaningful"] is True


def test_deadline_and_core_amendment_stop_admission_without_destroying_work(wf, state, context):
    result = ledger(wf, state, context)
    late = {**context, "now": "2026-01-01T02:00:00Z"}
    with pytest.raises(ValueError):
        call(wf, result, late, "reserve", reservation_id="late", amounts={"searches": 1}, category="work")
    result["contract_digest"] = "e" * 64
    with pytest.raises(ValueError):
        call(wf, result, context, "task", task_id="build", action="start")


def test_unknown_payload_fields_cannot_smuggle_authority_or_bypass_checks(wf, state, context):
    with pytest.raises(ValueError):
        call(wf, state, context, "configure", dimensions=dimensions(), layers=[], publish=True)


def test_measured_overrun_is_recorded_and_blocks_new_admission(wf, state, context):
    result = call(wf, ledger(wf, state, context), context, "reserve", reservation_id="worker", amounts={"searches": 10}, category="work")
    result = call(wf, result, context, "settle", reservation_id="worker", actual={"searches": 12})
    assert wf.budget_summary(result)["searches"]["spent"] == 12
    assert wf.budget_summary(result)["searches"]["available"] == -2
    assert result["extensions"]["workflow"]["budget"]["breaches"]
    with pytest.raises(ValueError):
        call(wf, result, context, "task", task_id="build", action="start")


def test_amendment_does_not_reset_spent_budget(wf, state, context):
    result = call(wf, ledger(wf, state, context), context, "reserve", reservation_id="work", amounts={"searches": 10}, category="work")
    result = call(wf, result, context, "settle", reservation_id="work", actual={"searches": 6})
    result["profile_digest"] = "f" * 64
    result["profile_revision"] += 1
    result = call(wf, result, context, "configure", dimensions=dimensions(domain="research"), reason="Typed core amendment")
    assert wf.budget_summary(result)["searches"]["spent"] == 6
    assert wf.budget_summary(result)["searches"]["available"] == 4


def test_child_cancellation_preserves_reservation_and_work_until_acknowledged(wf, state, context):
    result, context, brief = dispatch_ready(wf, state, context)
    result = call(wf, result, context, "dispatch", **brief)
    result = call(wf, result, context, "cancel_child", child_id="child-a", reason="Owner requested stop")
    child = result["extensions"]["workflow"]["children"]["child-a"]
    assert child["cancellation_requested"] is True
    assert child["disposition"] == "running"
    assert wf.budget_summary(result)["searches"]["available"] == 3
    result = call(wf, result, context, "return", child_id="child-a", disposition="cancelled", artifact_ids=["retained"], evidence_ids=[], reason="Stop acknowledged")
    assert result["extensions"]["workflow"]["children"]["child-a"]["artifact_ids"] == ["retained"]


def test_verified_changed_condition_unlocks_blocked_task_within_attempt_budget(wf, state, context):
    result = graphed(wf, state, context)
    for number in range(2):
        result = call(wf, result, context, "progress", task_id="build", attempt_id=f"a{number}", input_digest="1" * 64,
                      output_digest="2" * 64, evidence_ids=[], outcome="transient_failure", summary="Unavailable")
    context = receipt(result, context, "clear", "retry_clearance", {"task_id": "build", "changed_condition": "Verified service recovery"})
    result = call(wf, result, context, "task", task_id="build", action="retry", receipt_id="clear")
    assert "build" in wf.ready_tasks(result)


def test_profile_required_independence_cannot_be_disabled_per_grade(wf, state, context):
    result = configured(wf, state, context, uncertainty="high")
    context = quality_context(result, context, reviewer="worker")
    result = call(wf, result, context, "grade", criterion_id="c1", receipt_ids=["q1"], independent=False)
    assert result["extensions"]["workflow"]["quality"]["c1"]["verdict"] == "UNKNOWN"


def test_forecast_overrun_is_measured_without_claiming_hard_enforcement(wf, state, context):
    result = call(wf, ledger(wf, state, context), context, "reserve", reservation_id="worker", amounts={"tokens": 2}, category="work")
    result = call(wf, result, context, "settle", reservation_id="worker", actual={"tokens": 20})
    assert wf.budget_summary(result)["tokens"]["spent"] == 20
    assert wf.budget_summary(result)["tokens"]["enforcement"] == "forecast"


def test_omitted_hard_usage_cannot_refund_a_reservation_as_zero(wf, state, context):
    result = call(wf, ledger(wf, state, context), context, "reserve", reservation_id="worker", amounts={"searches": 10}, category="work")
    result = call(wf, result, context, "settle", reservation_id="worker", actual={})
    assert wf.budget_summary(result)["searches"]["available"] == 0
    assert wf.budget_summary(result)["searches"]["spent"] is None
    assert wf.budget_summary(result)["searches"]["unknown_reservations"] == ["worker"]
    result = call(wf, result, context, "settle", reservation_id="worker", actual={"searches": 0})
    assert wf.budget_summary(result)["searches"]["available"] == 10


def test_unreported_provider_forecast_is_unknown_not_zero(wf, state, context):
    result = call(wf, ledger(wf, state, context), context, "reserve", reservation_id="worker", amounts={"searches": 2, "tokens": 100}, category="work")
    result = call(wf, result, context, "settle", reservation_id="worker", actual={"searches": 1})
    summary = wf.budget_summary(result)
    assert summary["searches"]["spent"] == 1
    assert summary["tokens"]["spent"] is None
    assert summary["tokens"]["known_spent"] == 0
    assert summary["tokens"]["unknown_reservations"] == ["worker"]
    assert result["extensions"]["workflow"]["budget"]["reservations"]["worker"]["status"] == "unknown"
    result = call(wf, result, context, "settle", reservation_id="worker", actual={"searches": 1, "tokens": 150})
    assert wf.budget_summary(result)["tokens"]["spent"] == 150


def test_partial_usage_reconciliation_cannot_rewrite_known_usage(wf, state, context):
    result = call(wf, ledger(wf, state, context), context, "reserve", reservation_id="worker", amounts={"searches": 2, "tokens": 100}, category="work")
    result = call(wf, result, context, "settle", reservation_id="worker", actual={"searches": 1})
    with pytest.raises(ValueError):
        call(wf, result, context, "settle", reservation_id="worker", actual={"searches": 0, "tokens": 100})


@pytest.mark.parametrize("condition", ["unfinished", "children", "quality", "usage", "stale_profile", "stale_quality"])
def test_core_completed_close_cannot_bypass_workflow_obligations(wf, state, context, condition):
    result = graphed(wf, state, context)
    flow = result["extensions"]["workflow"]
    for node in flow["graph"]["nodes"].values():
        node["status"] = "done"
    for criterion in ("c1", "c2"):
        typed = quality_context(result, context)["evidence"]["q1"]["data"]
        typed["criterion_id"] = criterion
        typed["artifact_id"] = "a1" if criterion == "c1" else "a2"
        context = receipt(result, context, criterion, "quality_observation", typed)
        context["evidence"][criterion]["artifact_id"] = typed["artifact_id"]
        flow["quality"][criterion] = {"verdict": "PASS", "receipt_ids": [criterion], "round": 1, "independent": True}
    if condition == "unfinished":
        flow["graph"]["nodes"]["build"]["status"] = "blocked"
    elif condition == "children":
        flow["children"]["lost"] = {"disposition": "running", "audit_status": "required"}
    elif condition == "quality":
        flow["quality"]["c1"]["verdict"] = "UNKNOWN"
    elif condition == "usage":
        flow["budget"] = {"reservations": {"lost": {"status": "unknown"}}}
    elif condition == "stale_profile":
        result["profile_digest"] = "e" * 64
    elif condition == "stale_quality":
        context["evidence"].pop("c1")
    with pytest.raises(ValueError):
        wf.validate_command(result, "close", {"status": "completed"}, context)
    wf.validate_command(result, "close", {"status": "incomplete", "reason": "Preserved work"}, context)


def test_completion_guard_accepts_sound_fresh_outcomes(wf, state, context):
    result = graphed(wf, state, context)
    flow = result["extensions"]["workflow"]
    for node in flow["graph"]["nodes"].values():
        node["status"] = "done"
    for criterion in ("c1", "c2"):
        typed = quality_context(result, context)["evidence"]["q1"]["data"]
        typed.update(criterion_id=criterion, artifact_id="a1" if criterion == "c1" else "a2")
        context = receipt(result, context, criterion, "quality_observation", typed)
        context["evidence"][criterion]["artifact_id"] = typed["artifact_id"]
        flow["quality"][criterion] = {"verdict": "PASS", "receipt_ids": [criterion], "round": 1, "independent": True}
    wf.validate_command(result, "close", {"status": "completed"}, context)


def test_real_engine_transactions_enforce_workflow_close_guard(wf, world, monkeypatch):
    from test_run_state import create, command, output
    engine = importlib.import_module("run_state")
    monkeypatch.setattr(engine, "_COMMANDS", {})
    monkeypatch.setattr(engine, "_CONSTRAINTS", {})
    wf.register_commands(engine.register_command)
    wf.register_constraints(engine.register_constraint)
    state, _ = output(engine, world, create(engine, world))
    state = command(engine, world, state, "workflow.configure", {"dimensions": dimensions()})
    state = command(engine, world, state, "workflow.graph", {"nodes": [{"id": "work", "deps": [], "criteria": ["accept"], "estimate": 1}], "wip_limit": 1})
    state = command(engine, world, state, "transition", {"status": "verifying"})
    state = command(engine, world, state, "verify", {"criteria": ["accept"]})
    before = engine.load_run(world["project"], state["run_id"])
    with pytest.raises(ValueError, match="unfinished task"):
        command(engine, world, state, "close", {"status": "completed"})
    assert engine.load_run(world["project"], state["run_id"]) == before
    state = command(engine, world, state, "close", {"status": "incomplete", "reason": "Retained unfinished work"})
    assert state["extensions"]["workflow"]["graph"]["nodes"]["work"]["status"] == "pending"
