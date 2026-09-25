"""Decisive uncertainty uses actual local execution, never supplied confidence."""
from copy import deepcopy
import hashlib
import json

import pytest

from test_domain_quality import actual_consumer_fixture
from test_controller import engine, facade, world, request, start_request, invoke, state_of  # noqa: F401


def module():
    import decision_uncertainty
    return decision_uncertainty


def question():
    return {"id": "denominator", "decision": "Select the reported mean", "why_decisive": "Using missing rows changes the recommendation",
            "if_supported": "Retain the observed-value calculation", "if_refuted": "Repair the denominator and recheck",
            "affected_criteria": ["accept"], "observation_check_id": "consumer-spec", "cost_rank": 1,
            "expected_supported": {"reported_mean": 3, "recomputed_mean": 3.0, "coverage": "2/4"},
            "expected_refuted": {"reported_mean": 1.5, "recomputed_mean": 3.0, "coverage": "2/4"}}


def registered(context):
    du = module()
    value = du.prepare_question(context, question())
    context["state"] = du.register_question(context["state"], value, context)
    return context


@pytest.mark.parametrize("reported,branch", [(3, "supported"), (1.5, "refuted")])
def test_actual_observation_selects_branch_including_negative_result(tmp_path, reported, branch):
    context, _, _, _ = actual_consumer_fixture(tmp_path, reported)
    registered(context)
    du = module()
    before = deepcopy(context["state"])
    assert du.status_view(before, context)["status"] == "unresolved"
    proof = du.prepare_resolution(context, {"id": "denominator", "receipt_id": "actual-consumer"})
    context["state"] = du.resolve_question(before, proof, context)
    view = du.status_view(context["state"], context)
    assert view["status"] == "clear"
    assert view["resolved"][0]["branch"] == branch
    assert du.status_view(context["state"])["status"] == "unknown"
    assert before["extensions"]["decision_uncertainty"]["items"]["denominator"]["resolutions"] == []


@pytest.mark.parametrize("identity", ["source", "program", "consumer-spec", "draft"])
def test_changed_observation_dependency_reopens_exact_criteria(tmp_path, identity):
    context, _, _, record = actual_consumer_fixture(tmp_path)
    registered(context)
    du = module()
    proof = du.prepare_resolution(context, {"id": "denominator", "receipt_id": "actual-consumer"})
    context["state"] = du.resolve_question(context["state"], proof, context)
    immutable = deepcopy(context["state"])
    path = tmp_path / context["artifacts"][identity]["path"]
    path.write_bytes(path.read_bytes() + b"\n")
    context["artifacts"][identity]["digest"] = hashlib.sha256(path.read_bytes()).hexdigest()
    view = du.status_view(context["state"], context)
    assert view["status"] == "unresolved"
    assert view["affected_criteria"] == ["accept"]
    assert context["state"] == immutable
    assert record["data"]["input_digests"][identity] != context["artifacts"][identity]["digest"]


@pytest.mark.parametrize("mutation", ["same-branches", "same-predictions", "unknown-criterion", "confidence", "foreign-check"])
def test_question_rejects_nondiscriminating_or_unbound_facts(tmp_path, mutation):
    context, _, _, _ = actual_consumer_fixture(tmp_path)
    value = question()
    if mutation == "same-branches": value["if_refuted"] = value["if_supported"]
    if mutation == "same-predictions": value["expected_refuted"] = value["expected_supported"]
    if mutation == "unknown-criterion": value["affected_criteria"] = ["invented"]
    if mutation == "confidence": value["confidence"] = 0.99
    if mutation == "foreign-check": value["observation_check_id"] = "source"
    with pytest.raises(ValueError): module().prepare_question(context, value)


def test_only_affected_task_is_stopped_and_cancellation_remains_available(tmp_path):
    context, _, _, _ = actual_consumer_fixture(tmp_path)
    registered(context)
    du = module()
    context["state"]["extensions"]["workflow"] = {"graph": {"nodes": {
        "work": {"criteria": ["accept"]}, "independent": {"criteria": ["other"]}}}}
    with pytest.raises(ValueError, match="uncertainty"):
        du.validate_command(context["state"], "workflow.task", {"task_id": "work", "action": "start"}, context)
    du.validate_command(context["state"], "workflow.task", {"task_id": "independent", "action": "start"}, context)
    du.validate_command(context["state"], "close", {"status": "cancelled"}, context)
    with pytest.raises(ValueError, match="uncertainty"):
        du.validate_command(context["state"], "close", {"status": "completed"}, context)


@pytest.mark.parametrize("task,criteria,blocked", [
    ("work", ["accept"], True), ("work", ["other"], True),
    ("independent", ["accept"], True), ("independent", ["other"], False)])
def test_delegation_admission_checks_graph_and_child_acceptance(task, criteria, blocked, tmp_path):
    context, _, _, _ = actual_consumer_fixture(tmp_path)
    registered(context)
    context["state"]["extensions"]["workflow"] = {"graph": {"nodes": {
        "work": {"criteria": ["accept"]}, "independent": {"criteria": ["other"]}}}}
    payload = {"task_id": task, "criteria": criteria}
    if blocked:
        with pytest.raises(ValueError, match="uncertainty"):
            module().validate_command(context["state"], "workflow.dispatch", payload, context)
    else:
        module().validate_command(context["state"], "workflow.dispatch", payload, context)
    module().validate_command(context["state"], "workflow.child", {"action": "cancel"}, context)


def test_resolution_cannot_be_self_attested_or_rebound(tmp_path):
    context, _, _, record = actual_consumer_fixture(tmp_path)
    registered(context)
    du = module()
    with pytest.raises(ValueError):
        du.prepare_resolution(context, {"id": "denominator", "receipt_id": "actual-consumer", "branch": "supported"})
    context["verify_receipt"] = lambda *args: False
    with pytest.raises(ValueError, match="current|authenticated"):
        du.prepare_resolution(context, {"id": "denominator", "receipt_id": "actual-consumer"})


def test_uncertainty_is_controller_registered_and_no_items_is_clear(facade, world):
    response = invoke(facade, world, start_request(world))
    assert response["coverage"]["decision_uncertainty"]["status"] == "clear"
    import run_state
    assert "decision.question" in run_state._COMMANDS
    assert "decision.resolve" in run_state._COMMANDS
    assert "decision.uncertainty" in run_state._CONSTRAINTS


def test_explicit_revision_retains_prior_question_and_exact_negative_proof(tmp_path):
    context, _, _, _ = actual_consumer_fixture(tmp_path, 1.5)
    registered(context)
    du = module()
    proof = du.prepare_resolution(context, {"id": "denominator", "receipt_id": "actual-consumer"})
    context["state"] = du.resolve_question(context["state"], proof, context)
    prior = deepcopy(context["state"]["extensions"]["decision_uncertainty"]["items"]["denominator"])
    amended = question(); amended["why_decisive"] = "The operator now needs a corrected report with the original discrepancy retained"
    payload = {"id": "denominator", "expected_question_digest": du.question_digest(prior), "question": amended,
               "reason": "Apply the new operator requirement while preserving the prior failed result"}
    prepared = du.prepare_revision(context, payload)
    context["state"] = du.revise_question(context["state"], prepared, context)
    current = context["state"]["extensions"]["decision_uncertainty"]["items"]["denominator"]
    assert current["resolutions"] == []
    assert current["prior_versions"][-1]["question"] == {key: value for key, value in prior.items() if key != "prior_versions"}
    assert current["prior_versions"][-1]["question"]["resolutions"][0]["branch"] == "refuted"
    with pytest.raises(ValueError, match="changed|stale"):
        du.prepare_revision(context, payload)


def test_unrelated_criterion_change_preserves_question_but_affected_change_reopens(tmp_path):
    context, _, _, _ = actual_consumer_fixture(tmp_path)
    registered(context)
    du = module()
    proof = du.prepare_resolution(context, {"id": "denominator", "receipt_id": "actual-consumer"})
    context["state"] = du.resolve_question(context["state"], proof, context)
    # This fixture keeps receipt authentication fixed to isolate criterion
    # closure behavior. The full engine independently invalidates old receipts
    # on a contract amendment; it must then collect a fresh execution receipt.
    context["state"]["contract"]["criteria"].append({"id": "other", "description": "Independent work"})
    assert du.status_view(context["state"], context)["status"] == "clear"
    context["state"]["contract"]["criteria"][0]["description"] = "Changed accepted output"
    assert du.status_view(context["state"], context)["affected_criteria"] == ["accept"]


def test_diagnostic_capture_never_substitutes_for_declared_research_judgment(tmp_path):
    import profile_evidence
    context, _, _, _ = actual_consumer_fixture(tmp_path)
    registered(context)
    reasons = profile_evidence._decision_triggers(context["state"], {"domains": ["research"], "uncertainty": "high"})
    assert set(reasons) == {"registered decisive uncertainty", "research or recommendation domain", "declared material uncertainty"}


def test_ordinary_controller_observation_resolves_and_capture_survives_finish(facade, world):
    from test_controller import prepared_consumer
    state, _ = prepared_consumer(facade, world)
    actual = next(row for row in state["evidence"].values() if row["kind"] == "consumer-check")
    value = question()
    value.update(observation_check_id=actual["data"]["check_id"], expected_supported={"answer": 5}, expected_refuted={"answer": 9})
    response = invoke(facade, world, request("record", {"kind": "uncertainty", "question": value}, state, "decisive-question"))
    assert response["status"] == "RECORDED", response
    state = state_of(world, response)
    assert response["coverage"]["decision_uncertainty"]["status"] == "unresolved"
    response = invoke(facade, world, request("finish", {"disposition": "completed"}, state, "unresolved-finish"))
    assert response["status"] == "UNRESOLVED", response
    state = state_of(world, response)
    response = invoke(facade, world, request("record", {"kind": "uncertainty_observe", "id": value["id"],
        "receipt_id": actual["id"]}, state, "observe-answer"))
    assert response["status"] == "RECORDED", response
    state = state_of(world, response)
    assert response["coverage"]["decision_uncertainty"]["status"] == "clear"
    response = invoke(facade, world, request("finish", {"disposition": "completed"}, state, "resolved-finish"))
    assert response["status"] == "COMPLETED", response
    final = state_of(world, response)
    profile = final["evidence"][final["profile_evidence"]]["data"]
    assert profile["dispositions"]["framework-decisions"]["status"] == "SATISFIED"
    assert final["extensions"]["decision_uncertainty"]["items"]["denominator"]["resolutions"]


def test_real_contract_steering_invalidates_prior_decision_observation(facade, world):
    import run_state
    from test_run_state import command
    from test_controller import prepared_consumer
    state, _ = prepared_consumer(facade, world)
    actual = next(row for row in state["evidence"].values() if row["kind"] == "consumer-check")
    value = question()
    value.update(observation_check_id=actual["data"]["check_id"], expected_supported={"answer": 5}, expected_refuted={"answer": 9})
    response = invoke(facade, world, request("record", {"kind": "uncertainty", "question": value}, state, "steering-question"))
    assert response["status"] == "RECORDED", response
    state = state_of(world, response)
    response = invoke(facade, world, request("record", {"kind": "uncertainty_observe", "id": value["id"],
        "receipt_id": actual["id"]}, state, "steering-observation"))
    assert response["status"] == "RECORDED", response
    state = state_of(world, response)
    assert response["coverage"]["decision_uncertainty"]["status"] == "clear"
    revised = deepcopy(state["contract"])
    revised["criteria"].append({"id": "added", "description": "Verify the operator's additional output obligation",
        "required": True, "method": "artifact", "artifact_ids": ["output"]})
    revised["outcomes"][0]["criteria"].append("added")
    state = command(run_state, world, state, "contract.amend", {"contract": revised, "reason": "Additional accepted obligation"})
    response = invoke(facade, world, request("next", {"mode": "inspect"}, state, "after-steering"))
    assert response["coverage"]["decision_uncertainty"]["status"] == "unresolved", response
    assert response["coverage"]["decision_uncertainty"]["affected_criteria"] == ["accept"]
    response = invoke(facade, world, request("finish", {"disposition": "completed"}, state, "steered-finish"))
    assert response["status"] == "UNRESOLVED", response


def test_unpredicted_actual_result_remains_open_and_negative_evidence_survives(tmp_path):
    context, _, _, record = actual_consumer_fixture(tmp_path, 4)
    registered(context)
    du = module()
    before = deepcopy(record)
    with pytest.raises(ValueError, match="neither predicted"):
        du.prepare_resolution(context, {"id": "denominator", "receipt_id": "actual-consumer"})
    assert du.status_view(context["state"], context)["status"] == "unresolved"
    assert record == before and record["data"]["passed"] is False


def test_decisive_questions_follow_declared_relative_observation_order(tmp_path):
    context, _, _, _ = actual_consumer_fixture(tmp_path)
    registered(context)
    du = module()
    cheaper = {**question(), "id": "cheap-check", "cost_rank": 0}
    context["state"] = du.register_question(context["state"], du.prepare_question(context, cheaper), context)
    assert [row["id"] for row in du.status_view(context["state"], context)["open"]] == ["cheap-check", "denominator"]


def test_direct_question_revision_rejects_nonobject_question(tmp_path):
    context, _, _, _ = actual_consumer_fixture(tmp_path)
    registered(context)
    du = module()
    item = context["state"]["extensions"]["decision_uncertainty"]["items"]["denominator"]
    with pytest.raises(ValueError, match="question|uncertainty"):
        du.prepare_revision(context, {"id": "denominator", "expected_question_digest": du.question_digest(item),
            "question": None, "reason": "Malformed direct engine input"})


@pytest.mark.parametrize("stdout,accepted", [("null", True), ("not JSON", False)])
def test_null_prediction_requires_actual_decoded_observation(tmp_path, stdout, accepted):
    import consumer_checks
    import domain_quality
    context, _, _, record = actual_consumer_fixture(tmp_path)
    program = tmp_path / context["artifacts"]["program"]["path"]
    program.write_text("print(" + repr(stdout) + ")\n")
    spec = tmp_path / context["artifacts"]["consumer-spec"]["path"]
    value = json.loads(spec.read_text()); value["expected"] = None; spec.write_text(json.dumps(value))
    for identity, path in (("program", program), ("consumer-spec", spec)):
        context["artifacts"][identity]["digest"] = hashlib.sha256(path.read_bytes()).hexdigest()
    actual = consumer_checks.observe(context, {"check_id": "consumer-spec"})
    record.update(data=actual, digest=domain_quality.digest(actual))
    context["state"]["observations"]["actual-consumer"] = {**record, "artifact_digests": actual["input_digests"]}
    du = module()
    q = {**question(), "expected_supported": None, "expected_refuted": {"counterexample": True}}
    context["state"] = du.register_question(context["state"], du.prepare_question(context, q), context)
    if accepted:
        proof = du.prepare_resolution(context, {"id": q["id"], "receipt_id": "actual-consumer"})
        assert proof["resolution"]["branch"] == "supported"
    else:
        with pytest.raises(ValueError, match="healthy bounded"):
            du.prepare_resolution(context, {"id": q["id"], "receipt_id": "actual-consumer"})
        assert du.status_view(context["state"], context)["status"] == "unresolved"
