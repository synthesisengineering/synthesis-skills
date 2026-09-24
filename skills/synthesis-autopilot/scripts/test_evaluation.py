"""Acceptance fixtures for complete, comparable and non-self-promoting trials."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("autopilot_evaluation", Path(__file__).with_name("evaluation.py"))
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


def configuration():
    return {"client": "fixture", "surface": "local", "version": "1", "model": "fixed",
            "effort": "fixed", "tools": ["filesystem"], "permissions": "synthetic-only",
            "resources": {"wall_seconds": 60, "searches": 0}, "hardware": "fixture",
            "network": "loopback task targets; provider traffic separately admitted"}


def preregistration():
    return evaluation.preregister(
        tasks=["S01", "R02"], repetitions=2, lane="controlled", seed=47,
        arms=[{"id": arm, "configuration": configuration(), "implementation": arm + "-digest"}
              for arm in ("native", "baseline", "candidate")],
        thresholds={"unauthorized_effects": 0, "required_pass_rate": 1.0,
                    "max_quality_regression": 0}, semantic_calibration="unvalidated")


def trial(reg, index=0):
    cell = reg["schedule"][index]
    return {**cell, "registration_digest": reg["digest"], "status": "completed",
            "configuration": configuration(), "implementation": cell["arm"] + "-digest",
            "outcome": {"deterministic": "PASS", "semantic": "UNKNOWN", "unauthorized_effects": 0},
            "usage": {"tokens": None, "cost": None, "tool_calls": 2, "wall_seconds": 1,
                      "human_interventions": 0, "human_minutes": None},
            "evidence": [{"kind": "consumer", "sha256": "a" * 64}], "rescues": []}


def test_corpus_has_thirty_distinct_tasks_and_separate_worker_inputs():
    corpus = evaluation.corpus()
    assert len(corpus) == 30
    assert {domain: sum(c["domain"] == domain for c in corpus) for domain in evaluation.DOMAINS} == {
        d: 5 for d in evaluation.DOMAINS}
    for case in corpus:
        assert case["worker"]["prompt"] and case["grader"]["criteria"]
        assert "grader" not in case["worker"]
        assert case["preservation_sentinels"]


def test_predeclared_balanced_reproducible_schedule():
    reg = preregistration()
    assert len(reg["schedule"]) == 12
    assert reg == preregistration()
    assert len({c["trial_id"] for c in reg["schedule"]}) == 12


def test_controlled_lane_refuses_different_model_or_limits():
    reg = preregistration()
    arms = reg["arms"]
    arms[1]["configuration"]["model"] = "different"
    with pytest.raises(ValueError, match="configuration"):
        evaluation.preregister(tasks=["S01"], repetitions=1, lane="controlled", seed=1,
                              arms=arms, thresholds=reg["thresholds"], semantic_calibration="unvalidated")


def test_system_lane_retains_differences_without_pooled_uplift():
    reg = preregistration()
    arms = reg["arms"]
    arms[1]["configuration"]["model"] = "different"
    other = evaluation.preregister(tasks=["S01"], repetitions=1, lane="system", seed=1,
                                   arms=arms, thresholds=reg["thresholds"], semantic_calibration="unvalidated")
    assert other["lane"] == "system"
    assert not evaluation.compare(other, [trial(other, i) for i in range(3)])["pooled_uplift_claim_allowed"]


def test_missing_trial_is_incomplete_not_success():
    reg = preregistration()
    report = evaluation.compare(reg, [trial(reg)])
    assert report["status"] == "INCOMPLETE"
    assert len(report["missing_trials"]) == 11


def test_start_failures_remain_in_original_arm_and_cost_unknown():
    reg = preregistration()
    trials = [trial(reg, i) for i in range(12)]
    trials[0]["status"] = "startup_failed"
    trials[0]["outcome"]["deterministic"] = "UNKNOWN"
    report = evaluation.compare(reg, trials)
    arm = trials[0]["arm"]
    assert report["arms"][arm]["assigned"] == 4
    assert report["arms"][arm]["startup_failed"] == 1
    assert report["arms"][arm]["cost_known"] is False
    assert report["status"] != "PASS"


def test_duplicate_trials_changed_candidate_and_rubric_tampering_refused():
    reg = preregistration()
    with pytest.raises(ValueError, match="duplicate"):
        evaluation.compare(reg, [trial(reg), trial(reg)])
    bad = trial(reg)
    bad["implementation"] = "new-candidate"
    with pytest.raises(ValueError, match="implementation"):
        evaluation.compare(reg, [bad])
    altered = copy.deepcopy(reg)
    altered["thresholds"]["required_pass_rate"] = 0
    with pytest.raises(ValueError, match="digest"):
        evaluation.compare(altered, [])


def test_mechanical_grade_does_not_invent_semantic_quality():
    case = evaluation.corpus()[0]
    good = evaluation.positive_control(case)
    result = evaluation.grade(case, good)
    assert result["deterministic"] == "PASS"
    assert result["semantic"] == "UNKNOWN"
    wrong = copy.deepcopy(good)
    wrong["artifacts"].clear()
    assert evaluation.grade(case, wrong)["deterministic"] == "FAIL"
    good["unauthorized_effects"] = 1
    assert evaluation.grade(case, good)["deterministic"] == "FAIL"


def test_every_grader_has_positive_and_seeded_negative_controls():
    for case in evaluation.corpus():
        assert evaluation.grade(case, evaluation.positive_control(case))["deterministic"] == "PASS"
        assert evaluation.grade(case, evaluation.negative_control(case))["deterministic"] == "FAIL"


def test_worker_directory_never_contains_grader_keys(tmp_path):
    case = evaluation.corpus()[0]
    paths = evaluation.prepare(case["id"], tmp_path)
    files = [p for p in paths["worker"].rglob("*") if p.is_file()]
    assert files and paths["grader"].parent != paths["worker"]
    for p in files:
        assert "expected_value" not in p.read_text()


def test_improvement_is_only_a_proposal_with_benefit_and_retirement_test():
    proposal = evaluation.propose_improvement(
        title="Reconcile unknown effects", trial_refs=["trial-1"],
        applicability="interrupted writes", benefit="avoids duplicate fixture write",
        regressions=["read-only unchanged"], resource_impact="one read-back",
        owner="autopilot", retirement_test="native runtime supplies equivalent reconciliation")
    assert proposal["status"] == "proposed"
    assert proposal["activation_authorized"] is False
    assert "activate" not in evaluation.COMMANDS


def test_unvalidated_semantic_grades_do_not_promote_defaults():
    reg = preregistration()
    trials = [trial(reg, i) for i in range(12)]
    report = evaluation.compare(reg, trials)
    assert report["mechanical_status"] == "PASS"
    assert report["semantic_status"] == "UNKNOWN"
    assert report["default_promotion_ready"] is False


def test_invalid_task_and_budgets_refuse_before_writes(tmp_path):
    with pytest.raises(ValueError):
        evaluation.prepare("../../escape", tmp_path)
    assert list(tmp_path.iterdir()) == []
    reg = preregistration()
    for repetitions in (0, -1, True, 1.5):
        with pytest.raises(ValueError):
            evaluation.preregister(tasks=["S01"], repetitions=repetitions, lane="controlled", seed=1,
                                   arms=reg["arms"], thresholds=reg["thresholds"], semantic_calibration="unvalidated")
