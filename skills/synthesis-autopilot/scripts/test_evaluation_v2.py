"""Synthetic causal controls for the schema2 owner, never model performance data."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import random
from pathlib import Path
import subprocess
import sys

import pytest

SOURCE = Path(__file__).with_name("evaluation.py")
SPEC = importlib.util.spec_from_file_location("evaluation_contract_owner", SOURCE)
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)
v2 = evaluation._v2()


def pin(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, sort_keys=True, allow_nan=False).encode()
    path.write_bytes(content)
    return {"path": str(path), "sha256": hashlib.sha256(content).hexdigest()}


def study_spec(root, count=2, repetitions=2, phase="development", method="paired-cluster-bca/1"):
    authority = pin(root, "private/authority.json", {"kind": "synthetic read-only authority reference"})
    source = pin(root, "private/source.json", {"author": "independent-author", "kind": "synthetic authored tasks"})
    evidence = pin(root, "private/control-observations.json", {"kind": "synthetic independent blinded observations"})
    positive = pin(root, "private/sound.json", {"answer": "correct"})
    negative = pin(root, "private/defective.json", {"answer": "plausible but wrong"})
    rubric = pin(root, "private/rubric.json", {"version": "1", "scale": [1, 5], "criteria": [
        {"id": "consumer", "kind": "deterministic"}, {"id": "meaning", "kind": "semantic"}]})
    calibration = pin(root, "private/calibration.json", {
        "rubric_sha256": rubric["sha256"], "grader": "fixture-grader", "reviewer": "independent-reviewer",
        "blinded": True, "source": evidence, "controls": [
            {"id": "sound", "artifact": positive, "expected": "PASS", "observed": "PASS"},
            {"id": "defect", "artifact": negative, "expected": "FAIL", "observed": "FAIL"}],
        "quality_controls": [
            {"id": "strong", "artifact": positive, "expected_score": 5, "observed_score": 5, "tolerance": .1},
            {"id": "weak", "artifact": negative, "expected_score": 1, "observed_score": 1, "tolerance": .1}]})
    tasks = []
    for i in range(count):
        ident = f"task-{i + 1:03}"
        worker = pin(root, f"{ident}/worker/manifest.json", {"prompt": f"Solve independently authored synthetic case {i + 1}.", "inputs": []})
        tasks.append({"id": ident, "family": "software", "split": "holdout" if phase == "confirmation" else "development",
                      "cluster_id": f"source-project-{i + 1:03}", "author": "independent-author", "source": source,
                      "sealed": phase == "confirmation", "exposed_to_candidate": False, "worker": worker,
                      "oracle": pin(root, f"{ident}/private/oracle.json", {"answer": i + 1}), "rubric": rubric,
                      "consumer": pin(root, f"{ident}/private/consumer.json", {"invariant": i + 1}),
                      "preservation": pin(root, f"{ident}/private/preservation.json", {"sentinels": []}), "calibration": calibration})
    envelope = {"cost": 10, "tokens": 10000, "tool_calls": 100, "wall_seconds": 60, "human_minutes": 10, "human_interventions": 10}
    shared = {"model": "fixture-model", "effort": "fixture-effort", "tools": ["read-fixture"], "permissions": authority,
              "input_entitlement": "registered-worker-only", "context_tokens": 1000,
              "persistent_context": pin(root, "private/context.json", {"memory": [], "cache": "cold"}),
              "environment": {"hardware": "synthetic", "network": "offline"}, "resources": envelope}
    runtime = {"client": "fixture", "surface": "test", "build": "1", "capabilities": evidence}
    arms = [{"id": name, "role": name, "authors": [name + "-author"],
             "implementation": pin(root, "private/" + name + "-source.json", {"implementation": name}),
             "runtime": copy.deepcopy(runtime), "entitlement": copy.deepcopy(shared),
             "intervention": {"workflow": name, "instructions": pin(root, "private/" + name + "-instructions.json", {"workflow": name})}}
            for name in ("native", "candidate")]
    pilot = pin(root, "private/pilot.json", {"kind": "synthetic planning assumptions; not measured pilot evidence"})
    plan = {"kind": "development-budget", "basis": pilot, "maximum_clusters": count}
    if phase == "confirmation":
        plan.update(kind="pilot-informed", power=.8, assumptions={
            scope: {"accepted": {"variance": .01, "anticipated_effect": .7},
                    "quality": {"variance": .02, "anticipated_effect": 1.5}}
            for scope in ("all", "software")})
    return {"schema_version": 2, "study_id": "synthetic-study", "phase": phase, "authority_ref": authority,
            "task_registry": tasks, "arms": arms, "lanes": [
                {"id": "controlled", "kind": "controlled", "baseline": "native", "candidate": "candidate", "baseline_qualification": evidence, "context_difference": "matched"},
                {"id": "strongest", "kind": "strongest-native", "baseline": "native", "candidate": "candidate", "baseline_qualification": evidence, "context_difference": "matched"}],
            "repetitions": repetitions, "seed": 47,
            "analysis": {"method": method, "confidence": .95, "resamples": 4096,
                         "primary": {"metric": "accepted", "minimum_effect": .05}, "reliability_margin": .02,
                         "family_quality_margin": .25, "efficiency": None, "sample_plan": plan},
            "resources": {"episode_limits": envelope, "study_limits": {k: v * count * repetitions * 6 for k, v in envelope.items()},
                          "integration_reserve": {"cost": 5}, "evaluation_reserve": {"cost": 5}, "limit_kind": "forecast",
                          "shared_overhead_allocation": {"native": .5, "candidate": .5}, "cost_unit": "fixture-credit"},
            "stopping": {"rule": "fixed-assignment-final", "max_rescues": 1, "max_pair_gap_seconds": 300,
                         "immediate_harm": True, "invalidation_reasons": ["external-outage"]}}


def ledger(root, identity, *, cost=1.0, child=False, closed=True):
    evidence = pin(root, f"observations/{identity}-usage-source.json", {"kind": "synthetic exclusive component observation", "id": identity})
    nodes = [{"id": identity, "parent": None, "role": "root"}]
    values = {"tokens": 10, "cost": cost, "tool_calls": 2, "wall_seconds": 2, "human_minutes": 1, "human_interventions": 0}
    components = [{"id": identity, "measurement": "exclusive", "values": values, "source": evidence}]
    if child:
        nodes.append({"id": identity + "-child", "parent": identity, "role": "worker"})
        components.append({"id": identity + "-child", "measurement": "exclusive", "values": {k: None for k in v2.DIMENSIONS}, "source": None})
    return {"inventory": pin(root, f"observations/{identity}-tree.json", {"closed": closed, "source": evidence, "nodes": nodes}), "components": components}


def observation(root, reg, cell, *, accepted=True, quality=4, index=0, parent=None, cost=1.0):
    ident = cell["assignment_id"]
    evidence = pin(root, f"observations/{ident}-{index}-consumer.json", {"kind": "synthetic consumer and independent review", "accepted": accepted, "quality": quality})
    return {"assignment_id": ident, "episode_index": index, "parent_digest": parent,
            "reason": "operator-repair" if index else None, "actor": "fixture-worker", "status": "completed",
            "authority_ref": reg["spec"]["authority_ref"],
            "observed_configuration": {"configuration_digest": cell["configuration_digest"], "model": "fixture-model", "effort": "fixture-effort",
                                       "unknown_reason": None, "source": evidence, "observer": "native-observer"},
            "target": {"id": ident, "mutable": True, "initial_state": evidence},
            "timing": {"assigned": f"2026-01-01T00:0{index}:00Z", "started": f"2026-01-01T00:0{index}:01Z", "ended": f"2026-01-01T00:0{index}:03Z"},
            "conditions": {"load": "fixture", "outage": "none", "cache": "cold", "concurrency": 1, "source": evidence},
            "outcome": {"criteria": [
                {"id": "consumer", "status": "PASS" if accepted else "FAIL", "evidence": evidence, "observer": "consumer-observer"},
                {"id": "meaning", "status": "PASS", "evidence": evidence, "observer": "fixture-grader"}],
                "quality": quality, "quality_evidence": evidence, "grader": "fixture-grader",
                "harms": {key: 0 for key in v2.HARMS}, "harm_evidence": evidence, "harm_observer": "independent-observer", "critical_regressions": []},
            "usage": ledger(root, f"{ident}-e{index}", cost=cost)}


def seal(reg, value):
    # Synthetic collector fixture serializes its own recorded observations;
    # compare must independently validate all data and actual artifact pins.
    record = {"schema_version": 2, "registration_digest": reg["digest"], **copy.deepcopy(value)}
    record["digest"] = v2.digest(record)
    return record


def rows(root, reg):
    return [seal(reg, observation(root, reg, cell)) for cell in reg["schedule"]]


def reseal(record):
    record.pop("digest", None)
    record["digest"] = v2.digest(record)


def test_independent_tasks_freeze_reproducibly_and_worker_has_no_grader_pins(tmp_path):
    spec = study_spec(tmp_path)
    reg = evaluation.preregister(**spec)
    assert reg == evaluation.preregister(**spec)
    assert len(reg["schedule"]) == 8
    assert len({row["assignment_id"] for row in reg["schedule"]}) == 8
    assert reg["execution_authorized"] is False
    assert reg["interval_family_size"] == 4  # Two lanes reuse one physical contrast.
    projected = evaluation.worker(reg, "task-001")
    serialized = json.dumps(projected)
    assert "Solve independently authored" in serialized
    for key in ("oracle", "rubric", "calibration", "consumer"):
        assert spec["task_registry"][0][key]["sha256"] not in serialized
    result = evaluation.compare(reg, rows(tmp_path, reg))
    assert result["arms"]["candidate"]["first_episode_passed"] == 4
    assert result["comparisons"]["native:candidate"]["outcome_status"] == "DESCRIPTIVE"
    assert result["public_claim_authorized"] is result["activation_authorized"] is False
    assert "default_promotion_ready" not in result


def test_controlled_lane_compares_entitlement_not_registered_intervention(tmp_path):
    spec = study_spec(tmp_path)
    assert spec["arms"][0]["intervention"] != spec["arms"][1]["intervention"]
    assert evaluation.preregister(**spec)
    spec["arms"][1]["entitlement"]["model"] = "advantaged-model"
    with pytest.raises(ValueError, match="controlled entitlement"):
        evaluation.preregister(**spec)
    spec["lanes"] = [spec["lanes"][1]]
    assert evaluation.preregister(**spec)
    spec["arms"][1]["entitlement"]["permissions"] = pin(tmp_path, "private/broader.json", {"effect": "write"})
    with pytest.raises(ValueError, match="authority"):
        evaluation.preregister(**spec)


def test_terminal_failure_and_rescue_have_separate_outcomes_and_cumulative_cost(tmp_path):
    reg = evaluation.preregister(**study_spec(tmp_path, count=1, repetitions=1))
    cell = next(cell for cell in reg["schedule"] if cell["arm"] == "candidate")
    failed = observation(tmp_path, reg, cell, accepted=False, quality=1, cost=2)
    failed.update(status="startup_failed")
    failed["timing"]["started"] = None
    original = evaluation.episode(reg, **failed)
    rescue = evaluation.episode(reg, **observation(tmp_path, reg, cell, index=1, parent=original["digest"], cost=3))
    native = next(cell for cell in reg["schedule"] if cell["arm"] == "native")
    records = [original, rescue, seal(reg, observation(tmp_path, reg, native))]
    result = evaluation.compare(reg, records)
    arm = result["arms"]["candidate"]
    assert arm["first_episode_failed"] == arm["startup_failures"] == 1
    assert arm["first_episode_passed"] == 0
    assert arm["rescue_adjusted_passed"] == arm["rescue_episodes"] == 1
    assert arm["usage"]["cost"]["known_sum"] == 5
    assert len(result["retained_episodes"]) == 3
    with pytest.raises(ValueError, match="missing original"):
        evaluation.compare(reg, records[1:])
    changed = copy.deepcopy(records)
    changed[1]["parent_digest"] = "a" * 64
    reseal(changed[1])
    with pytest.raises(ValueError, match="lineage"):
        evaluation.compare(reg, changed)


def test_unknown_grandchild_and_unobserved_study_expense_remain_unknown(tmp_path):
    reg = evaluation.preregister(**study_spec(tmp_path, count=1, repetitions=1))
    records = rows(tmp_path, reg)
    candidate = next(row for row in records if row["assignment_id"].endswith("candidate"))
    candidate["usage"] = ledger(tmp_path, "nested-root", child=True)
    tree = json.loads(Path(candidate["usage"]["inventory"]["path"]).read_text())
    tree["nodes"].append({"id": "grandchild", "parent": "nested-root-child", "role": "review"})
    candidate["usage"]["inventory"] = pin(tmp_path, "observations/nested-tree-final.json", tree)
    reseal(candidate)
    result = evaluation.compare(reg, records)
    usage = result["arms"]["candidate"]["usage"]["cost"]
    assert usage["known_sum"] == 1
    assert usage["complete"] is False
    assert {"nested-root-child", "grandchild", "unobserved"} <= set(usage["unknown_components"])
    assert result["arms"]["candidate"]["first_episode_passed"] == 1


def test_repeats_and_source_project_aliases_do_not_multiply_independent_units(tmp_path):
    spec = study_spec(tmp_path, count=2, repetitions=4)
    spec["task_registry"][1]["cluster_id"] = spec["task_registry"][0]["cluster_id"]
    reg = evaluation.preregister(**spec)
    report = evaluation.compare(reg, rows(tmp_path, reg))
    result = report["comparisons"]["native:candidate"]["scopes"]["all"]
    assert result["tasks"] == 2
    assert result["source_clusters"] == 1
    assert result["metrics"]["accepted"]["independent_clusters"] == 1
    assert result["metrics"]["accepted"]["interval"] == [-1, 1]
    assert result["primary_status"] == "INCONCLUSIVE"


@pytest.mark.parametrize("target", ["worker", "oracle", "rubric", "consumer", "preservation", "calibration"])
def test_changed_pinned_bytes_invalidate_frozen_evaluation(tmp_path, target):
    reg = evaluation.preregister(**study_spec(tmp_path, count=1, repetitions=1))
    path = Path(reg["spec"]["task_registry"][0][target]["path"])
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="pin changed"):
        evaluation.compare(reg, [])


def test_rehashing_changed_schedule_cannot_redefine_assignments(tmp_path):
    reg = evaluation.preregister(**study_spec(tmp_path))
    reg["schedule"][0]["task_id"] = "invented-task"
    reg.pop("digest")
    reg["digest"] = v2.digest(reg)
    with pytest.raises(ValueError, match="schedule"):
        evaluation.compare(reg, [])


def test_rehashed_different_evaluator_cannot_reinterpret_registration(tmp_path):
    reg = evaluation.preregister(**study_spec(tmp_path))
    reg["evaluator_code"]["evaluation_v2.py"] = "a" * 64
    reg.pop("digest")
    reg["digest"] = v2.digest(reg)
    with pytest.raises(ValueError, match="schedule or pins"):
        evaluation.compare(reg, [])


def test_missing_assignment_and_missing_criterion_are_not_passes(tmp_path):
    reg = evaluation.preregister(**study_spec(tmp_path, count=1, repetitions=1))
    records = rows(tmp_path, reg)
    records[0]["outcome"]["criteria"].pop()
    reseal(records[0])
    result = evaluation.compare(reg, records[:1])
    assert result["status"] == "INCOMPLETE"
    assert len(result["missing_assignments"]) == 1
    assert sum(row["first_episode_passed"] for row in result["arms"].values()) == 0


@pytest.mark.parametrize("mutation", ["duplicate-task", "duplicate-arm", "exposed-holdout", "candidate-author", "historical-confirmation", "unknown-authority-field", "unregistered-look", "zero-variance"])
def test_registration_adversarial_cases(tmp_path, mutation):
    spec = study_spec(tmp_path, phase="confirmation")
    if mutation == "duplicate-task":
        spec["task_registry"].append(copy.deepcopy(spec["task_registry"][0]))
    elif mutation == "duplicate-arm":
        spec["arms"].append(copy.deepcopy(spec["arms"][0]))
    elif mutation == "exposed-holdout":
        spec["task_registry"][0]["exposed_to_candidate"] = True
    elif mutation == "candidate-author":
        spec["task_registry"][0]["author"] = "candidate-author"
    elif mutation == "historical-confirmation":
        spec["task_registry"][0]["id"] = "S01"
    elif mutation == "unknown-authority-field":
        spec["activation_authorized"] = True
    elif mutation == "unregistered-look":
        spec["stopping"]["rule"] = "stop-when-significant"
    elif mutation == "zero-variance":
        spec["analysis"]["sample_plan"]["assumptions"]["all"]["accepted"]["variance"] = 0
    with pytest.raises(ValueError):
        evaluation.preregister(**spec)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1, True, "zero"])
def test_malformed_or_nonfinite_harm_never_means_zero(tmp_path, bad):
    reg = evaluation.preregister(**study_spec(tmp_path, count=1, repetitions=1))
    value = observation(tmp_path, reg, reg["schedule"][0])
    value["outcome"]["harms"]["unauthorized_effects"] = bad
    with pytest.raises(ValueError):
        evaluation.episode(reg, **value)


def test_critical_harm_unknown_authority_and_self_grade_are_protected(tmp_path):
    reg = evaluation.preregister(**study_spec(tmp_path, count=1, repetitions=1))
    records = rows(tmp_path, reg)
    candidate = next(row for row in records if row["assignment_id"].endswith("candidate"))
    candidate["outcome"]["harms"]["unauthorized_effects"] = None
    reseal(candidate)
    report = evaluation.compare(reg, records)
    assert report["arms"]["candidate"]["authority_integrity"] == "UNKNOWN"
    assert report["arms"]["candidate"]["first_episode_passed"] == 0
    candidate["outcome"]["harms"]["unauthorized_effects"] = 1
    reseal(candidate)
    report = evaluation.compare(reg, records)
    assert report["harm_stop_required"] is True
    assert report["comparisons"]["native:candidate"]["outcome_status"] == "NEGATIVE"
    candidate["outcome"]["criteria"][0]["observer"] = candidate["actor"]
    reseal(candidate)
    with pytest.raises(ValueError, match="worker assertion"):
        evaluation.compare(reg, records)


def test_duplicate_episode_shared_target_and_tree_double_counting_rejected(tmp_path):
    reg = evaluation.preregister(**study_spec(tmp_path, count=1, repetitions=1))
    records = rows(tmp_path, reg)
    with pytest.raises(ValueError, match="duplicate episode"):
        evaluation.compare(reg, records + [records[0]])
    changed = copy.deepcopy(records)
    changed[1]["target"]["id"] = changed[0]["target"]["id"]
    reseal(changed[1])
    with pytest.raises(ValueError, match="mutable external target"):
        evaluation.compare(reg, changed)
    changed = copy.deepcopy(records)
    changed[1]["usage"] = copy.deepcopy(changed[0]["usage"])
    reseal(changed[1])
    with pytest.raises(ValueError, match="duplicate usage"):
        evaluation.compare(reg, changed)


def test_known_critical_regression_is_not_an_accepted_delivery(tmp_path):
    reg = evaluation.preregister(**study_spec(tmp_path, count=1, repetitions=1))
    records = rows(tmp_path, reg)
    candidate = next(row for row in records if row["assignment_id"].endswith("candidate"))
    candidate["outcome"]["critical_regressions"] = [pin(tmp_path, "private/regression.json", {
        "kind": "synthetic independent preservation failure"})]
    reseal(candidate)
    report = evaluation.compare(reg, records)
    assert report["arms"]["candidate"]["critical_regression"] is True
    assert report["arms"]["candidate"]["first_episode_passed"] == 0
    assert report["arms"]["candidate"]["first_episode_failed"] == 1
    assert report["comparisons"]["native:candidate"]["outcome_status"] == "NEGATIVE"


def test_known_null_effect_and_degeneracy_controls_for_interval_method():
    null = [-.2, -.1, .1, .2] * 10
    a = v2.paired_interval(null, method="paired-cluster-bca/1", seed=9, resamples=10000)
    b = v2.paired_interval([x + .3 for x in null], method="paired-cluster-bca/1", seed=9, resamples=10000)
    assert a["method_used"] == b["method_used"] == "paired-cluster-bca/1"
    assert a["interval"][0] < 0 < a["interval"][1]
    assert b["estimate"] == pytest.approx(.3)
    assert b["interval"][0] > .2
    assert b["interval"][1] < .4
    tiny = v2.paired_interval([.4, .4], method="paired-cluster-bca/1")
    assert tiny["method_used"] == "paired-cluster-hoeffding/1"
    assert tiny["interval"][0] <= 0
    degenerate = v2.paired_interval([.2] * 30, method="paired-cluster-bca/1")
    assert degenerate["interval"][0] < degenerate["interval"][1]
    assert "degenerate" in degenerate["reason"]


def test_hoeffding_formula_and_sample_planning_are_independently_checkable():
    result = v2.paired_interval([0] * 100, method="paired-cluster-hoeffding/1")
    # Direct analytic two-sided bounded-mean reference, range [-1, 1].
    expected = math.sqrt(2 * math.log(40) / 100)
    assert result["interval"] == pytest.approx([-expected, expected])
    assert v2.sample_size_estimate(variance=1, distance=.25, power=.8, confidence=.95) == 126
    assert v2.sample_size_estimate(variance=0, distance=.25, power=.8, confidence=.95) is None


def test_numeric_quality_cannot_be_self_graded_without_semantic_criteria(tmp_path):
    spec = study_spec(tmp_path, count=1, repetitions=1)
    task = spec["task_registry"][0]
    task["rubric"] = pin(tmp_path, "private/deterministic-rubric.json", {
        "version": "1", "scale": [1, 5], "criteria": [{"id": "consumer", "kind": "deterministic"}]})
    calibration = json.loads(Path(task["calibration"]["path"]).read_text())
    calibration["rubric_sha256"] = task["rubric"]["sha256"]
    task["calibration"] = pin(tmp_path, "private/numeric-calibration.json", calibration)
    reg = evaluation.preregister(**spec)
    value = observation(tmp_path, reg, reg["schedule"][0])
    value["outcome"]["criteria"] = value["outcome"]["criteria"][:1]
    value["actor"] = "fixture-grader"
    with pytest.raises(ValueError, match="own numeric quality"):
        evaluation.episode(reg, **value)


def test_exponent_overflow_and_assignment_identity_collision_rejected(tmp_path):
    with pytest.raises(ValueError, match="nonfinite JSON"):
        v2._json('{"measurement": 1e999}', "fixture")
    spec = study_spec(tmp_path, repetitions=1)
    spec["task_registry"][0]["id"] = "taskA"
    spec["task_registry"][1]["id"] = "taskA-r1-beta"
    spec["arms"][1]["id"] = "beta-r1-native"
    for lane in spec["lanes"]:
        lane["candidate"] = "beta-r1-native"
    spec["resources"]["shared_overhead_allocation"] = {"native": .5, "beta-r1-native": .5}
    with pytest.raises(ValueError, match="colliding assignment"):
        evaluation.preregister(**spec)


def test_observed_assignment_inversion_retains_results_but_invalidates_pair(tmp_path):
    reg = evaluation.preregister(**study_spec(tmp_path, count=1, repetitions=1))
    records = rows(tmp_path, reg)
    assert evaluation.compare(reg, records)["schedule_order_deviations"] == []
    records[0]["timing"]["assigned"] = "2026-01-01T00:00:01Z"
    reseal(records[0])
    report = evaluation.compare(reg, records)
    assert report["invalidated_blocks"] == {"task-001-r1": "registered assignment order violated"}
    assert set(report["schedule_order_deviations"]) == {row["assignment_id"] for row in records}
    assert sum(arm["first_episode_passed"] for arm in report["arms"].values()) == 2
    assert report["comparisons"]["native:candidate"]["scopes"]["all"]["metrics"]["accepted"]["independent_clusters"] == 0


def test_known_effect_is_detectable_and_missingness_removes_support(tmp_path):
    reg = evaluation.preregister(**study_spec(tmp_path, count=40, repetitions=1, phase="confirmation"))
    records = []
    for cell in reg["schedule"]:
        index = int(cell["task_id"].split("-")[1])
        candidate = cell["arm"] == "candidate"
        quality = 4 + .1 * (index % 4) if candidate else 2 + .1 * (index % 3)
        value = observation(tmp_path, reg, cell, accepted=candidate or index % 4 == 0, quality=quality)
        records.append(seal(reg, value))
    result = evaluation.compare(reg, records)
    comparison = result["comparisons"]["native:candidate"]
    assert comparison["outcome_status"] == "SUPPORTED"
    assert result["lanes"]["strongest"]["adoption_evidence_supported"] is True
    assert result["lanes"]["controlled"]["adoption_evidence_supported"] is False
    assert result["public_claim_authorized"] is False
    # Independent review's consumer attack: a strong endpoint cohort cannot
    # authenticate the pinned strongest-native arm when its actual model is unknown.
    for model in (None, "unregistered-model"):
        changed = copy.deepcopy(records)
        for row in changed:
            if row["assignment_id"].endswith("-native"):
                row["observed_configuration"].update(model=model, unknown_reason="provider did not report it" if model is None else None)
                reseal(row)
        unqualified = evaluation.compare(reg, changed)
        assert unqualified["comparisons"]["native:candidate"]["outcome_status"] == "INCONCLUSIVE"
        for lane in unqualified["lanes"].values():
            assert lane["configuration_qualified"] is False
            assert lane["outcome_status"] == "INCONCLUSIVE"
            assert lane["adoption_evidence_supported"] is False
    incomplete = evaluation.compare(reg, records[1:])
    assert incomplete["comparisons"]["native:candidate"]["outcome_status"] == "INCONCLUSIVE"


def test_family_regression_cannot_be_hidden_by_other_family_gain(tmp_path):
    spec = study_spec(tmp_path, count=4, repetitions=1, phase="confirmation")
    for task in spec["task_registry"][:2]:
        task["family"] = "writing"
    spec["analysis"]["sample_plan"]["assumptions"]["writing"] = copy.deepcopy(spec["analysis"]["sample_plan"]["assumptions"]["software"])
    reg = evaluation.preregister(**spec)
    records = []
    for cell in reg["schedule"]:
        writing = int(cell["task_id"].split("-")[1]) <= 2
        candidate = cell["arm"] == "candidate"
        quality = 1 if writing and candidate else 5 if candidate else 3
        records.append(seal(reg, observation(tmp_path, reg, cell, quality=quality)))
    result = evaluation.compare(reg, records)["comparisons"]["native:candidate"]
    assert result["outcome_status"] == "NEGATIVE"
    assert result["scopes"]["writing"]["metrics"]["quality"]["protection_status"] == "NEGATIVE"


def test_cli_freeze_worker_episode_compare_and_duplicate_json_rejection(tmp_path):
    spec = study_spec(tmp_path, count=1, repetitions=1)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec))
    command = [sys.executable, str(SOURCE)]
    completed = subprocess.run(command + ["preregister", "--spec", str(spec_path)], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    reg = json.loads(completed.stdout)
    reg_path = tmp_path / "registration.json"
    reg_path.write_text(json.dumps(reg))
    value = observation(tmp_path, reg, reg["schedule"][0])
    observation_path = tmp_path / "episode-input.json"
    observation_path.write_text(json.dumps(value))
    completed = subprocess.run(command + ["episode", "--spec", str(reg_path), "--trials", str(observation_path)], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    recorded = json.loads(completed.stdout)
    observations_path = tmp_path / "observations.json"
    observations_path.write_text(json.dumps([recorded]))
    completed = subprocess.run(command + ["compare", "--spec", str(reg_path), "--trials", str(observations_path)], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "INCOMPLETE"
    completed = subprocess.run(command + ["worker", "--spec", str(reg_path), "--task", "task-001"], capture_output=True, text=True)
    assert completed.returncode == 0
    assert "oracle" not in completed.stdout
    spec_path.write_text('{"schema_version": 1, "schema_version": 2}')
    completed = subprocess.run(command + ["preregister", "--spec", str(spec_path)], capture_output=True, text=True)
    assert completed.returncode == 2
    assert "duplicate JSON key" in completed.stderr


def empty_ledger(root, name):
    source = pin(root, f"observations/{name}-empty-source.json", {"kind": "synthetic observer found no components"})
    return {"inventory": pin(root, f"observations/{name}-empty-tree.json", {"closed": True, "source": source, "nodes": []}), "components": []}


def overhead(root, names=("native", "candidate")):
    return {"by_arm": {name: empty_ledger(root, name + "-overhead") for name in names},
            "shared": ledger(root, "shared-evaluation", cost=4), "allocation": {name: 1 / len(names) for name in names}}


def test_complete_study_accounting_charges_shared_expense_once(tmp_path):
    reg = evaluation.preregister(**study_spec(tmp_path, count=1, repetitions=1))
    result = evaluation.compare(reg, {"episodes": rows(tmp_path, reg), "study_usage": overhead(tmp_path), "invalidations": []})
    assert result["study_usage"]["cost"]["known_sum"] == 6
    assert result["study_usage"]["cost"]["complete"] is True
    assert result["arms"]["candidate"]["usage"]["cost"]["known_sum"] == 3
    assert result["arms"]["candidate"]["concurrent_makespan"] == 3
    assert result["arms"]["candidate"]["queue_seconds"] == 1
    assert result["arms"]["candidate"]["episode_elapsed_sum"] == 3
    wrong = overhead(tmp_path)
    wrong["allocation"] = {"native": 1, "candidate": 0}
    with pytest.raises(ValueError, match="allocation differs"):
        evaluation.compare(reg, {"episodes": rows(tmp_path, reg), "study_usage": wrong, "invalidations": []})


def test_efficiency_known_effect_and_unknown_measurement_control(tmp_path):
    spec = study_spec(tmp_path, count=40, repetitions=1, phase="confirmation")
    spec["analysis"]["resamples"] = 16384
    spec["analysis"]["efficiency"] = {"metric": "cost", "minimum_reduction": .2}
    for assumptions in spec["analysis"]["sample_plan"]["assumptions"].values():
        assumptions["efficiency"] = {"variance": .01, "anticipated_effect": .5}
    reg = evaluation.preregister(**spec)
    records = []
    for cell in reg["schedule"]:
        index = int(cell["task_id"].split("-")[1])
        candidate = cell["arm"] == "candidate"
        value = observation(tmp_path, reg, cell, accepted=candidate or index % 4 == 0,
                            quality=4 + .1 * (index % 4) if candidate else 2 + .1 * (index % 3),
                            cost=.5 + .05 * (index % 3) if candidate else 2 + .1 * (index % 5))
        records.append(seal(reg, value))
    data = {"episodes": records, "study_usage": overhead(tmp_path), "invalidations": []}
    result = evaluation.compare(reg, data)["comparisons"]["native:candidate"]
    assert result["efficiency"]["status"] == "SUPPORTED"
    assert result["efficiency"]["relative_reduction"] > .8
    assert result["efficiency"]["interval"][0] > .2
    recorded_model = records[0]["observed_configuration"]["model"]
    records[0]["observed_configuration"].update(model=None, unknown_reason="missing native observation")
    reseal(records[0])
    unqualified = evaluation.compare(reg, data)
    assert unqualified["comparisons"]["native:candidate"]["efficiency"]["status"] == "INCONCLUSIVE"
    assert all(lane["efficiency_status"] == "INCONCLUSIVE" for lane in unqualified["lanes"].values())
    records[0]["observed_configuration"].update(model=recorded_model, unknown_reason=None)
    reseal(records[0])
    records[0]["usage"]["components"][0]["values"]["cost"] = None
    reseal(records[0])
    result = evaluation.compare(reg, data)["comparisons"]["native:candidate"]
    assert result["efficiency"]["status"] == "INCONCLUSIVE"
    assert result["efficiency"]["relative_reduction"] is None
    assert result["outcome_status"] == "SUPPORTED"


def test_seeded_null_and_effect_simulations_exercise_bca_not_only_fallback():
    false_positives, detections, bca_count = 0, 0, 0
    for seed in range(40):
        rng = random.Random(seed)
        values = [max(-.8, min(.8, rng.gauss(0, .18))) for _ in range(40)]
        null = v2.paired_interval(values, method="paired-cluster-bca/1", seed=seed, resamples=2048)
        effect = v2.paired_interval([value + .2 for value in values], method="paired-cluster-bca/1", seed=seed, resamples=2048)
        false_positives += not null["interval"][0] <= 0 <= null["interval"][1]
        detections += effect["interval"][0] > 0
        bca_count += null["method_used"] == "paired-cluster-bca/1"
    assert false_positives <= 5
    assert detections >= 35
    assert bca_count >= 35


def test_nonfinite_quality_usage_and_unregistered_effective_configuration(tmp_path):
    reg = evaluation.preregister(**study_spec(tmp_path, count=1, repetitions=1))
    value = observation(tmp_path, reg, reg["schedule"][0])
    for bad in (float("nan"), float("inf"), True, 10 ** 400):
        changed = copy.deepcopy(value)
        changed["outcome"]["quality"] = bad
        with pytest.raises(ValueError):
            evaluation.episode(reg, **changed)
        changed = copy.deepcopy(value)
        changed["usage"]["components"][0]["values"]["cost"] = bad
        with pytest.raises(ValueError):
            evaluation.episode(reg, **changed)
    value["observed_configuration"]["configuration_digest"] = "a" * 64
    with pytest.raises(ValueError, match="configuration changed"):
        evaluation.episode(reg, **value)


def test_calibration_defect_and_hidden_artifact_entitlement_rejected(tmp_path):
    spec = study_spec(tmp_path, phase="confirmation")
    task = spec["task_registry"][0]
    calibration = json.loads(Path(task["calibration"]["path"]).read_text())
    calibration["controls"][1]["observed"] = "PASS"
    task["calibration"] = pin(tmp_path, "private/failed-calibration.json", calibration)
    with pytest.raises(ValueError, match="passing inspected calibration"):
        evaluation.preregister(**spec)
    spec = study_spec(tmp_path)
    spec["task_registry"][0]["oracle"] = pin(tmp_path, "task-001/worker/leaked-oracle.json", {"answer": 1})
    with pytest.raises(ValueError, match="hidden grader"):
        evaluation.preregister(**spec)


def test_binary_calibration_does_not_invent_numeric_quality_calibration(tmp_path):
    spec = study_spec(tmp_path)
    for task in spec["task_registry"]:
        calibration = json.loads(Path(task["calibration"]["path"]).read_text())
        calibration["quality_controls"] = []
        task["calibration"] = pin(tmp_path, "private/binary-only-calibration.json", calibration)
    reg = evaluation.preregister(**spec)
    result = evaluation.compare(reg, rows(tmp_path, reg))["comparisons"]["native:candidate"]["scopes"]["all"]
    assert result["metrics"]["accepted"]["independent_clusters"] == 2
    assert result["metrics"]["quality"]["independent_clusters"] == 0
    assert result["metrics"]["quality"]["estimate"] is None


def test_invalidations_preserve_original_failure_and_cost(tmp_path):
    reg = evaluation.preregister(**study_spec(tmp_path, count=1, repetitions=1))
    records = rows(tmp_path, reg)
    records[0]["status"] = "timeout"
    reseal(records[0])
    invalidation = {"block_id": "task-001-r1", "reason": "external-outage",
                    "evidence": pin(tmp_path, "private/outage.json", {"kind": "synthetic outage observation"})}
    result = evaluation.compare(reg, {"episodes": records, "study_usage": overhead(tmp_path), "invalidations": [invalidation]})
    assert sum(row["first_episode_failed"] for row in result["arms"].values()) == 1
    assert result["study_usage"]["cost"]["known_sum"] == 6
    assert result["comparisons"]["native:candidate"]["scopes"]["all"]["metrics"]["accepted"]["independent_clusters"] == 0
    invalidation["reason"] = "unfavorable-score"
    with pytest.raises(ValueError, match="unregistered invalidation"):
        evaluation.compare(reg, {"episodes": records, "study_usage": None, "invalidations": [invalidation]})


def test_unknown_effective_configuration_and_missing_conditions_stay_visible(tmp_path):
    reg = evaluation.preregister(**study_spec(tmp_path, count=1, repetitions=1))
    records = rows(tmp_path, reg)
    records[0]["observed_configuration"].update(model=None, unknown_reason="provider does not report it")
    records[0]["conditions"]["load"] = None
    reseal(records[0])
    report = evaluation.compare(reg, records)
    assert report["effective_configuration_complete"] is False
    assert report["lanes"]["controlled"]["effective_configuration_unknown"] == ["task-001-r1"]
    assert report["invalidated_blocks"] == {"task-001-r1": "matched-window evidence incomplete"}


def test_declared_small_study_is_not_labeled_powered(tmp_path):
    spec = study_spec(tmp_path, count=2, phase="confirmation")
    spec["analysis"]["sample_plan"]["assumptions"]["all"]["accepted"] = {"variance": 1, "anticipated_effect": .05}
    reg = evaluation.preregister(**spec)
    result = evaluation.compare(reg, rows(tmp_path, reg))["comparisons"]["native:candidate"]["scopes"]["all"]
    plan = result["primary_planning"]
    assert plan["normal_approximation_required"] > plan["affordable_maximum"]
    assert plan["adequate"] is plan["power_established"] is False
    assert result["primary_status"] == "INCONCLUSIVE"
