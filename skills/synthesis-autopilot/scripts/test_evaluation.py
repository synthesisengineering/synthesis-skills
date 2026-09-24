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
            "configuration": copy.deepcopy(next(a["configuration"] for a in reg["arms"] if a["id"] == cell["arm"])), "implementation": cell["arm"] + "-digest",
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


def test_arbitrary_calibration_label_cannot_certify_semantics():
    reg = preregistration()
    with pytest.raises(ValueError, match="calibration"):
        evaluation.preregister(tasks=["S01"], repetitions=1, lane="controlled", seed=1,
            arms=reg["arms"], thresholds=reg["thresholds"], semantic_calibration="I checked it")


def test_failed_semantics_and_unknown_attention_remain_visible():
    reg = preregistration()
    rows = [trial(reg, i) for i in range(len(reg["schedule"]))]
    rows[0]["outcome"]["semantic"] = "FAIL"
    rows[0]["usage"]["human_interventions"] = None
    report = evaluation.compare(reg, rows)
    assert report["semantic_status"] == "FAIL"
    assert report["arms"][rows[0]["arm"]]["human_interventions_known"] is False
    assert report["default_promotion_ready"] is False


def test_semantic_grader_calibration_requires_independent_controls():
    sound = {"id": "sound", "expected": "PASS", "observed": "PASS", "artifact_digest": "a" * 64}
    defect = {"id": "defect", "expected": "FAIL", "observed": "FAIL", "artifact_digest": "b" * 64}
    result = evaluation.calibrate(grader="reviewer-v1", reviewer="separate-agent", rubric={"fidelity": "preserve facts"},
        controls=[sound, defect], provenance={"method": "blind", "source": "native transcript"})
    assert result["status"] == "PASS"
    bad = copy.deepcopy(defect)
    bad["observed"] = "PASS"
    assert evaluation.calibrate(grader="reviewer-v1", reviewer="separate-agent", rubric={"fidelity": "preserve facts"},
        controls=[sound, bad], provenance={"method": "blind", "source": "native transcript"})["status"] == "FAIL"
    with pytest.raises(ValueError):
        evaluation.calibrate(grader="reviewer-v1", reviewer="separate-agent", rubric={"fidelity": "preserve facts"},
            controls=[sound], provenance={"method": "blind", "source": "native transcript"})


def test_worker_spec_declares_output_fields_without_answer_values():
    for case in evaluation.corpus():
        schema = case["worker"]["output_schema"]
        assert set(schema["required"]) == set(case["grader"]["expected_value"])
        assert "expected_value" not in json.dumps(case["worker"])


def calibrated_registration():
    reg = preregistration()
    calibration = evaluation.calibrate(grader="fixed", reviewer="independent", rubric={"quality":"purpose"},
        controls=[{"id":"a","expected":"PASS","observed":"PASS","artifact_digest":"a"*64},
                  {"id":"b","expected":"FAIL","observed":"FAIL","artifact_digest":"b"*64}],
        provenance={"method":"blind","source":"native-review"})
    return evaluation.preregister(tasks=["S01","R02"], repetitions=2, lane="controlled", seed=47,
        arms=reg["arms"],thresholds=reg["thresholds"],semantic_calibration=calibration)


def test_quality_regression_threshold_is_applied_per_domain():
    reg = calibrated_registration()
    rows = [trial(reg, i) for i in range(len(reg["schedule"]))]
    for row in rows:
        row["outcome"].update(semantic="PASS", quality_score=0.8 if row["arm"] == "candidate" and row["task"] == "R02" else 1.0)
    report = evaluation.compare(reg, rows)
    assert report["quality_regression_status"] == "FAIL"
    assert report["default_promotion_ready"] is False
    assert report["quality_comparisons"]["R"]["baseline"]["regression"] == pytest.approx(0.2)


def test_comparison_exposes_uncertainty_and_does_not_infer_first_attempt_from_rescues():
    reg = preregistration()
    rows = [trial(reg, i) for i in range(len(reg["schedule"]))]
    report = evaluation.compare(reg, rows)
    for row in report["arms"].values():
        assert row["first_attempt_known"] is False
        assert row["first_attempt_pass_rate"] is None
        assert row["pass_rate_interval"][0] < 1.0
        assert row["wall_seconds_variance"] == 0
    assert report["quality_regression_status"] == "UNKNOWN"


def test_invalid_quality_score_refused_and_failed_baseline_not_erased():
    reg = calibrated_registration()
    rows = [trial(reg, i) for i in range(len(reg["schedule"]))]
    for row in rows:
        row["outcome"].update(semantic="PASS", quality_score=1.0)
        row["attempts"] = [{"deterministic":"PASS"}]
    bad = copy.deepcopy(rows)
    bad[0]["outcome"]["quality_score"] = float("nan")
    with pytest.raises(ValueError):
        evaluation.compare(reg, bad)
    baseline = next(row for row in rows if row["arm"] == "baseline")
    baseline["outcome"]["deterministic"] = "FAIL"
    report = evaluation.compare(reg, rows)
    assert report["arms"]["baseline"]["failed"] == 1
    assert report["candidate_acceptance"]["mechanical"] == "PASS"
    assert report["arms"]["candidate"]["first_attempt_pass_rate"] == 1


def test_baseline_semantic_failure_does_not_reject_verified_candidate_improvement():
    reg = calibrated_registration()
    rows = [trial(reg, i) for i in range(len(reg["schedule"]))]
    for row in rows:
        row["outcome"].update(semantic="FAIL" if row["arm"] == "baseline" else "PASS")
    report = evaluation.compare(reg, rows)
    assert report["semantic_status"] == "FAIL"  # Baseline failures remain visible.
    assert report["candidate_acceptance"]["semantic"] == "PASS"
    assert report["quality_regression_status"] == "PASS"
    assert report["default_promotion_ready"] is True
    candidate = next(row for row in rows if row["arm"] == "candidate")
    candidate["outcome"]["semantic"] = "FAIL"
    report = evaluation.compare(reg, rows)
    assert report["candidate_acceptance"]["semantic"] == "FAIL"
    assert report["default_promotion_ready"] is False


def test_semantic_cohort_uses_declared_threshold_without_discarding_failures():
    old = calibrated_registration()
    reg = evaluation.preregister(tasks=list(old['tasks']), repetitions=old['repetitions'], lane=old['lane'],
        seed=47, arms=old['arms'], thresholds={**old['thresholds'], 'required_pass_rate': 0.75},
        semantic_calibration=old['semantic_calibration'])
    rows = [trial(reg, i) for i in range(len(reg['schedule']))]
    for row in rows:
        row['outcome']['semantic'] = 'FAIL' if row['task'] == 'S01' and row['repetition'] == 1 else 'PASS'
    report = evaluation.compare(reg, rows)
    assert report['arms']['candidate']['semantic_pass_rate'] == 0.75
    assert report['semantic_status'] == 'FAIL'  # Real failures are still visible.
    assert report['candidate_acceptance']['semantic'] == 'PASS'
    assert report['quality_regression_status'] == 'PASS'
    assert report['default_promotion_ready'] is True
    next(row for row in rows if row['arm'] == 'candidate')['outcome']['semantic'] = 'UNKNOWN'
    assert evaluation.compare(reg, rows)['default_promotion_ready'] is False


@pytest.mark.parametrize('baseline_effects,overall', [(1, 'FAIL'), (None, 'UNKNOWN')])
def test_candidate_authority_is_independent_of_retained_baseline_defects(baseline_effects, overall):
    reg = calibrated_registration()
    rows = [trial(reg, i) for i in range(len(reg['schedule']))]
    for row in rows:
        row['outcome']['semantic'] = 'PASS'
    baseline = next(row for row in rows if row['arm'] == 'baseline')
    baseline['outcome']['unauthorized_effects'] = baseline_effects
    before = copy.deepcopy(rows)
    report = evaluation.compare(reg, rows)
    assert rows == before
    assert report['authority_status'] == overall
    assert report['arms']['baseline']['authority_status'] == overall
    assert report['arms']['baseline']['failed'] == 1
    assert report['mechanical_status'] == 'FAIL'
    assert report['candidate_acceptance']['authority'] == 'PASS'
    assert report['default_promotion_ready'] is True


@pytest.mark.parametrize('effects', [1, None, False, -1, '0'])
def test_candidate_authority_never_uses_pass_rate_to_tolerate_effects_or_unknown(effects):
    old = calibrated_registration()
    reg = evaluation.preregister(tasks=list(old['tasks']), repetitions=old['repetitions'], lane=old['lane'],
        seed=47, arms=old['arms'], thresholds={**old['thresholds'], 'required_pass_rate': 0.75},
        semantic_calibration=old['semantic_calibration'])
    rows = [trial(reg, i) for i in range(len(reg['schedule']))]
    for row in rows:
        row['outcome']['semantic'] = 'PASS'
    candidate = next(row for row in rows if row['arm'] == 'candidate')
    candidate['outcome']['unauthorized_effects'] = effects
    report = evaluation.compare(reg, rows)
    assert report['candidate_acceptance']['authority'] != 'PASS'
    assert report['default_promotion_ready'] is False


def test_missing_candidate_cell_cannot_have_verified_authority():
    reg = calibrated_registration()
    rows = [trial(reg, i) for i in range(len(reg['schedule']))]
    for row in rows:
        row['outcome']['semantic'] = 'PASS'
    missing = next(row for row in rows if row['arm'] == 'candidate')
    rows.remove(missing)
    report = evaluation.compare(reg, rows)
    assert report['candidate_acceptance']['authority'] == 'UNKNOWN'
    assert report['missing_trials'] == [missing['trial_id']]
    assert report['default_promotion_ready'] is False
