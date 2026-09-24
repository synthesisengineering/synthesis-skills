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
            "admissions": {}, "artifacts": {}, "evidence": {}, "verify_receipt": lambda *args: False}


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
             "admission_id": "child-admission", "return_contract": ["artifact_ids", "evidence_ids", "disposition"], "cancellation": "Preserve work and return disposition",
             "file_contract": {"schema_version":1,"immutable_inputs":[],"output_roots":[],"scratch_root":"/fixture/artifact"}}
    context["binding"]["project_root"] = "/fixture/project"
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
    context["artifacts"]={"a1":{"digest":"d"*64}}
    context = receipt(result, context, "audit", "child_integration", {"child_id": "child-a", "task_id": "build", "accepted": True, "criteria": ["c1"], "artifact_ids": ["a1"], "artifact_digests":{"a1":"d"*64}, "reviewer": "native:independent-reviewer", "producer":"fixture:child", "integration_owner":"root-seat", "actual": {"searches": 3}})
    result = call(wf, result, context, "integrate", child_id="child-a", receipt_id="audit")
    assert result["extensions"]["workflow"]["graph"]["nodes"]["build"]["status"] == "done"
    assert wf.budget_summary(result)["searches"]["spent"] == 3


@pytest.mark.parametrize('changes',[
    {'integration_owner':'another-seat'}, {'producer':'another-child'},
    {'reviewer':'fixture:child'}, {'reviewer':'child-seat'}, {'reviewer':'child-a'},
    {'artifact_digests':{'a1':'e'*64}}, {'artifact_digests':{}}, {'criteria':['c2']},
])
def test_integration_separates_owner_authority_from_review_provenance(wf,state,context,changes):
    result,context,brief=dispatch_ready(wf,state,context)
    result=call(wf,result,context,'dispatch',**brief)
    result=call(wf,result,context,'return',child_id='child-a',disposition='complete',artifact_ids=['a1'],evidence_ids=['r1'],reason='Ready')
    context['artifacts']={'a1':{'digest':'d'*64}}
    data={'child_id':'child-a','task_id':'build','accepted':True,'criteria':['c1'],'artifact_ids':['a1'],
          'artifact_digests':{'a1':'d'*64},'reviewer':'native:independent-reviewer','producer':'fixture:child',
          'integration_owner':'root-seat','actual':{'searches':3},**changes}
    context=receipt(result,context,'audit','child_integration',data)
    with pytest.raises(ValueError):call(wf,result,context,'integrate',child_id='child-a',receipt_id='audit')


def test_integration_current_actor_must_still_be_stored_integration_owner(wf,state,context):
    result,context,brief=dispatch_ready(wf,state,context)
    result=call(wf,result,context,'dispatch',**brief)
    result=call(wf,result,context,'return',child_id='child-a',disposition='complete',artifact_ids=['a1'],evidence_ids=[],reason='Ready')
    context['artifacts']={'a1':{'digest':'d'*64}}
    data={'child_id':'child-a','task_id':'build','accepted':True,'criteria':['c1'],'artifact_ids':['a1'],
          'artifact_digests':{'a1':'d'*64},'reviewer':'native:independent-reviewer','producer':'fixture:child',
          'integration_owner':'root-seat','actual':{'searches':3}}
    context=receipt(result,context,'audit','child_integration',data)
    context['binding']['session_uuid']='different-command-actor'
    with pytest.raises(ValueError):call(wf,result,context,'integrate',child_id='child-a',receipt_id='audit')


def artifact_only_dispatch(wf,state,context):
    result,context,brief=dispatch_ready(wf,state,context)
    context['binding']['native_ref']='codex:root-native'
    context['admissions']['child-admission'].update(session_uuid='root-seat',native_ref='codex:root-native')
    brief.update(child_id='/root/artifact_worker',mode='artifact-only',dispatch_receipt_id='native-dispatch')
    data={key:value for key,value in brief.items() if key not in {'admission_id','admission_requests','dispatch_receipt_id'}}
    context=receipt(result,context,'native-dispatch','delegation',data)
    return result,context,brief


@pytest.mark.parametrize('reviewer',['claude:independent-review','codex:root-native'])
def test_artifact_only_dispatch_uses_observed_native_child_without_inventing_a_seat(wf,state,context,reviewer):
    result,context,brief=artifact_only_dispatch(wf,state,context)
    result=call(wf,result,context,'dispatch',**brief)
    child=result['extensions']['workflow']['children']['/root/artifact_worker']
    assert child['owner']['session_uuid']=='root-seat'
    assert child['producer']=='/root/artifact_worker'
    assert child['authority_granted'] is False
    result=call(wf,result,context,'return',child_id=brief['child_id'],disposition='complete',artifact_ids=['a1'],evidence_ids=[],reason='Returned artifact only')
    context['artifacts']={'a1':{'digest':'d'*64}}
    context=receipt(result,context,'integration','child_integration',{
        'child_id':brief['child_id'],'task_id':'build','producer':brief['child_id'],'reviewer':reviewer,
        'integration_owner':'root-seat','artifact_ids':['a1'],'artifact_digests':{'a1':'d'*64},
        'criteria':['c1'],'accepted':True,'actual':{'searches':2}})
    result=call(wf,result,context,'integrate',child_id=brief['child_id'],receipt_id='integration')
    assert result['extensions']['workflow']['graph']['nodes']['build']['status']=='done'


@pytest.mark.parametrize('mutation',['missing-receipt','changed-brief','foreign-parent','wrong-native','peer-claims'])
def test_artifact_only_dispatch_cannot_turn_native_child_into_write_authority(wf,state,context,mutation):
    result,context,brief=artifact_only_dispatch(wf,state,context)
    if mutation=='missing-receipt':context['evidence']={}
    elif mutation=='changed-brief':brief['paths']=['/fixture/expanded'];context['admissions']['child-admission']['paths']=brief['paths']
    elif mutation=='foreign-parent':context['admissions']['child-admission']['session_uuid']='foreign-parent'
    elif mutation=='wrong-native':context['admissions']['child-admission']['native_ref']='codex:another'
    else:brief['mode']='peer'
    with pytest.raises(ValueError):call(wf,result,context,'dispatch',**brief)


def quality_context(state, context, *, passed=True, reviewer="independent", domain="software", calibrated=True):
    context = copy.copy(context)
    context["artifacts"] = {"a1": {"digest": "d" * 64}, "a2": {"digest": "d" * 64}}
    observations = {
        "software": {"expected": "ready", "observed": "ready" if passed else "broken", "consumer_verified": True},
        "research": {"sources_verified": True, "decisive_claims_verified": passed, "counterevidence_checked": True},
        "writing": {"source_fidelity": True, "reader_purpose": passed, "structure": True, "voice": True},
        "data": {"expected_rows": 3, "observed_rows": 3 if passed else 4, "expected_total": "12.50", "observed_total": "12.50", "missing_explained": True},
        "browser": {"expected_state": "saved", "observed_state": "saved" if passed else "unchanged", "independent_readback": True},
        "knowledge": {"expected_hashes": {"record": "abc"}, "recovered_hashes": {"record": "abc" if passed else "bad"}, "foreign_preserved": True},
        "operations": {"expected_state": "settled", "observed_state": "settled" if passed else "ambiguous", "effects_reconciled": True},
    }[domain]
    result = receipt(state, context, "q1", "quality_observation", {
        "domain": domain, "criterion_id": "c1", "artifact_id": "a1", "rubric": "behavior-v1", "passed": passed,
        "method": "consumer", "producer": "worker", "reviewer": reviewer, "calibrated": calibrated,
        "findings": [] if passed else ["Consumer output disagrees with expected result"], "independent": True,
        "observations": observations, "artifact_digest": "d" * 64})
    result["evidence"]["q1"]["artifact_id"] = "quality-receipt-json"
    return result


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
    result = configured(wf, state, context, domain=changes.get('domain','software'))
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
    context = receipt(result, context, "clear", "retry_clearance", {**wf.retry_binding(result,'build'), "changed_condition": "Verified service recovery"})
    result = call(wf, result, context, "task", task_id="build", action="retry", receipt_id="clear")
    assert "build" in wf.ready_tasks(result)


@pytest.mark.parametrize('domain,observation',[
    ('software',{'expected':1,'observed':True,'consumer_verified':True}),
    ('browser',{'expected_state':{'rows':[1]},'observed_state':{'rows':[True]},'independent_readback':True}),
    ('knowledge',{'expected_hashes':{'x':1},'recovered_hashes':{'x':True},'foreign_preserved':True}),
    ('operations',{'expected_state':[0],'observed_state':[False],'effects_reconciled':True}),
])
def test_domain_outcomes_use_typed_json_equality(wf,domain,observation):
    assert wf._observed_quality(domain,observation) is False


def test_writing_work_cannot_be_graded_using_software_only_checks(wf,state,context):
    result=configured(wf,state,context,domain='writing')
    with pytest.raises(ValueError):
        call(wf,result,quality_context(result,context,domain='software'),'grade',criterion_id='c1',receipt_ids=['q1'],independent=True)


def test_mixed_domain_closure_requires_each_domain_quality(wf,state,context):
    result=call(wf,state,context,'configure',dimensions={**dimensions(),'domains':['software','writing']})
    result=call(wf,result,context,'graph',nodes=nodes(),wip_limit=2)
    for node in result['extensions']['workflow']['graph']['nodes'].values():node['status']='done'
    for ident,artifact in [('c1','a1'),('c2','a2')]:
        data=quality_context(result,context)['evidence']['q1']['data'];data.update(criterion_id=ident,artifact_id=artifact)
        context['artifacts']={'a1':{'digest':'d'*64},'a2':{'digest':'d'*64}}
        context=receipt(result,context,ident,'quality_observation',data)
        result=call(wf,result,context,'grade',criterion_id=ident,receipt_ids=[ident],independent=True)
    with pytest.raises(ValueError):wf.validate_command(result,'close',{'status':'completed'},context)
    writing=quality_context(result,context,domain='writing')['evidence']['q1']['data'];writing.update(criterion_id='c2',artifact_id='a2')
    context=receipt(result,context,'writing','quality_observation',writing)
    result=call(wf,result,context,'grade',criterion_id='c2',receipt_ids=['writing'],independent=True)
    wf.validate_command(result,'close',{'status':'completed'},context)


def test_retry_clearance_cannot_replay_after_later_failure_or_through_alias(wf,state,context):
    result=graphed(wf,state,context)
    def fail(value,attempt):
        return call(wf,value,context,'progress',task_id='build',attempt_id=attempt,input_digest='1'*64,output_digest='2'*64,evidence_ids=[],outcome='permanent_failure',summary='Actual failure')
    result=fail(result,'a1')
    binding=wf.retry_binding(result,'build')
    context=receipt(result,context,'clear','retry_clearance',{**binding,'changed_condition':'Verified repaired dependency'})
    result=call(wf,result,context,'task',task_id='build',action='retry',receipt_id='clear')
    result=fail(result,'a2')
    with pytest.raises(ValueError):call(wf,result,context,'task',task_id='build',action='retry',receipt_id='clear')
    result=call(wf,result,context,'task',task_id='build',action='cancel',reason='Stop here')
    assert result['extensions']['workflow']['graph']['nodes']['build']['status']=='cancelled'


def test_retry_clearance_is_bound_to_current_block_and_consumed_once(wf,state,context):
    result=graphed(wf,state,context)
    result=call(wf,result,context,'task',task_id='build',action='block',reason='Dependency unavailable')
    data={**wf.retry_binding(result,'build'),'changed_condition':'Actual repaired dependency'}
    context=receipt(result,context,'clear','retry_clearance',data)
    result=call(wf,result,context,'task',task_id='build',action='retry',receipt_id='clear')
    result=call(wf,result,context,'task',task_id='build',action='block',reason='Dependency unavailable')
    context=receipt(result,context,'alias','retry_clearance',data)
    with pytest.raises(ValueError):call(wf,result,context,'task',task_id='build',action='retry',receipt_id='alias')


def test_retry_clearance_repackaging_cannot_change_consumption_identity(wf, state, context):
    result = graphed(wf, state, context)
    result = call(wf, result, context, "task", task_id="build", action="block", reason="Dependency unavailable")
    data = {**wf.retry_binding(result, "build"), "changed_condition": "Observed repair", "source": {"kind": "native-user", "message_id": "original-message"}}
    context = receipt(result, context, "clear", "retry_clearance", data)
    result = call(wf, result, context, "task", task_id="build", action="retry", receipt_id="clear")
    result = call(wf, result, context, "task", task_id="build", action="block", reason="Dependency unavailable")
    context = receipt(result, context, "repackaged", "retry_clearance", data)
    context["evidence"]["repackaged"].update(artifact_id="another-envelope", digest="f" * 64, observed_at="2026-01-01T00:01:00Z")
    with pytest.raises(ValueError):
        call(wf, result, context, "task", task_id="build", action="retry", receipt_id="repackaged")


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


def test_known_hard_overrun_blocks_work_while_provider_usage_is_unknown(wf, state, context):
    result=call(wf,ledger(wf,state,context),context,"reserve",reservation_id="worker",amounts={"searches":10,"tokens":100},category="work")
    result=call(wf,result,context,"settle",reservation_id="worker",actual={"searches":12})
    assert wf.budget_summary(result)["tokens"]["spent"] is None
    assert result["extensions"]["workflow"]["budget"]["breaches"]
    with pytest.raises(ValueError):
        call(wf,result,context,"task",task_id="build",action="start")
    result=call(wf,result,context,"settle",reservation_id="worker",actual={"tokens":150})
    assert len(result["extensions"]["workflow"]["budget"]["breaches"])==1


@pytest.mark.parametrize("condition", ["unfinished", "children", "quality", "usage", "stale_profile", "stale_quality"])
def test_core_completed_close_cannot_bypass_workflow_obligations(wf, state, context, condition):
    result = graphed(wf, state, context)
    flow = result["extensions"]["workflow"]
    for node in flow["graph"]["nodes"].values():
        node["status"] = "done"
    for criterion in ("c1", "c2"):
        context["artifacts"] = {"a1": {"digest": "d" * 64}, "a2": {"digest": "d" * 64}}
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


@pytest.mark.parametrize("horizon", ["session", "reboot"])
def test_completion_guard_accepts_sound_fresh_outcomes(wf, state, context, horizon):
    result = configured(wf, state, context, horizon=horizon)
    result = call(wf, result, context, "graph", nodes=nodes(), wip_limit=2)
    flow = result["extensions"]["workflow"]
    for node in flow["graph"]["nodes"].values():
        node["status"] = "done"
    for criterion in ("c1", "c2"):
        context["artifacts"] = {"a1": {"digest": "d" * 64}, "a2": {"digest": "d" * 64}}
        typed = quality_context(result, context)["evidence"]["q1"]["data"]
        typed.update(criterion_id=criterion, artifact_id="a1" if criterion == "c1" else "a2")
        context = receipt(result, context, criterion, "quality_observation", typed)
        context["evidence"][criterion]["artifact_id"] = typed["artifact_id"]
        flow["quality"][criterion] = {"verdict": "PASS", "receipt_ids": [criterion], "round": 1, "independent": True}
    if horizon == "reboot":
        with pytest.raises(ValueError):
            wf.validate_command(result, "close", {"status": "completed"}, context)
        wf.validate_command(result, "close", {"status": "incomplete", "reason": "Survival unproved"}, context)
    else:
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


@pytest.mark.parametrize("change", ["missing", "changed"])
def test_quality_receipt_cannot_certify_a_missing_or_changed_reviewed_artifact(wf, state, context, change):
    result = configured(wf, state, context)
    context = quality_context(result, context)
    if change == "missing":
        context["artifacts"].pop("a1")
    else:
        context["artifacts"]["a1"]["digest"] = "f" * 64
    with pytest.raises(ValueError):
        call(wf, result, context, "grade", criterion_id="c1", receipt_ids=["q1"], independent=True)


def accounting_completion_ready(wf, state, context):
    result = ledger(wf, state, context)
    flow = result['extensions']['workflow']
    for node in flow['graph']['nodes'].values():
        node['status'] = 'done'
    context['artifacts'] = {'a1': {'digest': 'd' * 64}, 'a2': {'digest': 'd' * 64}}
    for criterion in ('c1', 'c2'):
        typed = quality_context(result, context)['evidence']['q1']['data']
        typed.update(criterion_id=criterion, artifact_id='a1' if criterion == 'c1' else 'a2')
        context = receipt(result, context, criterion, 'quality_observation', typed)
        flow['quality'][criterion] = {'verdict': 'PASS', 'receipt_ids': [criterion], 'round': 1, 'independent': True}
    return result, context


def test_completed_outcome_can_retain_unmeasured_forecast_without_refund(wf, state, context):
    result, context = accounting_completion_ready(wf, state, context)
    result = call(wf, result, context, 'reserve', reservation_id='review', amounts={'searches': 2, 'tokens': 100}, category='verification')
    result = call(wf, result, context, 'settle', reservation_id='review', actual={'searches': 1})
    before = copy.deepcopy(result)
    wf.validate_command(result, 'close', {'status': 'completed'}, context)
    assert result == before
    summary = wf.budget_summary(result)
    assert summary['tokens']['spent'] is None
    assert summary['tokens']['committed'] == 100
    assert summary['tokens']['unknown_reservations'] == ['review']
    assert result['extensions']['workflow']['budget']['reservations']['review']['status'] == 'unknown'


@pytest.mark.parametrize('actual', [None, {}, {'tokens': 80}, 'reserved'])
def test_unknown_or_active_hard_usage_still_blocks_completed_close(wf, state, context, actual):
    result, context = accounting_completion_ready(wf, state, context)
    result = call(wf, result, context, 'reserve', reservation_id='review', amounts={'searches': 2, 'tokens': 100}, category='verification')
    if actual != 'reserved':
        result = call(wf, result, context, 'settle', reservation_id='review', actual=actual)
    with pytest.raises(ValueError, match='accounting'):
        wf.validate_command(result, 'close', {'status': 'completed'}, context)
    assert wf.budget_summary(result)['tokens']['committed'] >= 100


def test_forecast_unknown_does_not_excuse_measured_hard_breach(wf, state, context):
    result, context = accounting_completion_ready(wf, state, context)
    result = call(wf, result, context, 'reserve', reservation_id='review', amounts={'searches': 2, 'tokens': 100}, category='verification')
    result = call(wf, result, context, 'settle', reservation_id='review', actual={'searches': 3})
    with pytest.raises(ValueError, match='accounting'):
        wf.validate_command(result, 'close', {'status': 'completed'}, context)


def test_parent_keeps_conservative_forecast_when_finished_child_cost_unknown(wf, state, context):
    result, context = accounting_completion_ready(wf, state, context)
    result = call(wf, result, context, 'reserve', reservation_id='parent', amounts={'searches': 8, 'tokens': 200}, category='work')
    result = call(wf, result, context, 'reserve', reservation_id='child', parent_id='parent', amounts={'searches': 4, 'tokens': 100}, category='verification')
    result = call(wf, result, context, 'settle', reservation_id='child', actual={'searches': 2})
    # Parent-local tokens are measured; the child's are not. Do not refund the
    # child's missing usage by treating the parent as wholly measured.
    result = call(wf, result, context, 'settle', reservation_id='parent', actual={'searches': 1, 'tokens': 20})
    wf.validate_command(result, 'close', {'status': 'completed'}, context)
    summary = wf.budget_summary(result)
    assert summary['searches']['spent'] == 3
    assert summary['tokens']['spent'] is None
    assert summary['tokens']['known_spent'] == 20
    assert summary['tokens']['committed'] == 200
    assert summary['tokens']['unknown_reservations'] == ['child']
    assert result['extensions']['workflow']['budget']['reservations']['parent']['status'] == 'unknown'


def test_forecast_exception_cannot_discharge_running_child_reservation(wf, state, context):
    result, context = accounting_completion_ready(wf, state, context)
    result = call(wf, result, context, 'reserve', reservation_id='parent', amounts={'searches': 8, 'tokens': 200}, category='work')
    result = call(wf, result, context, 'reserve', reservation_id='child', parent_id='parent', amounts={'searches': 4, 'tokens': 100}, category='verification')
    result = call(wf, result, context, 'settle', reservation_id='parent', actual={'searches': 1})
    with pytest.raises(ValueError, match='accounting'):
        wf.validate_command(result, 'close', {'status': 'completed'}, context)


def test_forecast_exception_still_requires_actual_quality_acceptance(wf, state, context):
    result, context = accounting_completion_ready(wf, state, context)
    result = call(wf, result, context, 'reserve', reservation_id='review', amounts={'searches': 2, 'tokens': 100}, category='verification')
    result = call(wf, result, context, 'settle', reservation_id='review', actual={'searches': 1})
    result['extensions']['workflow']['quality'].pop('c1')
    with pytest.raises(ValueError, match='quality'):
        wf.validate_command(result, 'close', {'status': 'completed'}, context)


def test_later_ambiguous_report_does_not_reuse_earlier_partial_settlement(wf, state, context):
    result, context = accounting_completion_ready(wf, state, context)
    result = call(wf, result, context, 'reserve', reservation_id='review', amounts={'searches': 2, 'tokens': 100}, category='verification')
    result = call(wf, result, context, 'settle', reservation_id='review', actual={'searches': 1})
    result = call(wf, result, context, 'settle', reservation_id='review', actual=None)
    assert result['extensions']['workflow']['budget']['reservations']['review']['actual'] == {'searches': 1}
    with pytest.raises(ValueError, match='accounting'):
        wf.validate_command(result, 'close', {'status': 'completed'}, context)
    assert wf.budget_summary(result)['tokens']['committed'] == 100
def _failed_grade_and_repair(wf, state, context):
    state = configured(wf, state, context)
    context = quality_context(state, context, passed=False)
    state = call(wf, state, context, "grade", criterion_id="c1", receipt_ids=["q1"], independent=True)
    prior = copy.deepcopy(state["extensions"]["workflow"]["quality"]["c1"])
    new_data = copy.deepcopy(context["evidence"]["q1"]["data"])
    new_data.update(artifact_digest="e" * 64, observations={"expected": "ready", "observed": "ready", "consumer_verified": True}, findings=[])
    context["artifacts"] = {**context["artifacts"], "a1": {"digest": "e" * 64}}
    context = receipt(state, context, "q2", "quality_observation", new_data)
    context["evidence"]["q2"]["digest"] = "f" * 64
    context["evidence"].pop("q1")  # Old review is historical, not fresh for repaired bytes.
    return state, context, prior


def _repair_resolution(wf, state, context, prior, **changes):
    data = {"criterion_id": "c1", "prior_grade_digest": prior.get("grade_digest", "old-source-missing"),
            "prior_receipt_ids": ["q1"], "prior_receipt_digests": {"q1": "c" * 64},
            "receipt_ids": ["q2"], "new_receipt_digests": {"q2": "f" * 64},
            "changed_artifacts": {"a1": {"before": ["d" * 64], "after": "e" * 64}},
            "changed_evidence": "The registered reviewed output changed and received a fresh independent review."}
    return receipt(state, context, "resolution", "quality_resolution", {**data, **changes})


def test_quality_repair_preserves_failed_fingerprints_and_history(wf, state, context):
    state, context, prior = _failed_grade_and_repair(wf, state, context)
    assert prior["receipt_bindings"] == {"q1": {"digest": "c" * 64, "artifact_id": "a1", "artifact_digest": "d" * 64}}
    context = _repair_resolution(wf, state, context, prior)
    repaired = call(wf, state, context, "grade", criterion_id="c1", receipt_ids=["q2"], independent=True, resolution_receipt_id="resolution")
    flow = repaired["extensions"]["workflow"]
    assert flow["quality"]["c1"]["verdict"] == "PASS" and flow["quality"]["c1"]["round"] == 2
    assert flow["quality_history"]["c1"] == [prior]
    assert flow["quality"]["c1"]["resolution"] == {"receipt_id": "resolution", "digest": context["evidence"]["resolution"]["digest"]}
    assert repaired["contract_digest"] == state["contract_digest"]


@pytest.mark.parametrize("changes", [
    {"prior_grade_digest": "0" * 64}, {"prior_receipt_digests": {"q1": "0" * 64}},
    {"new_receipt_digests": {"q2": "0" * 64}}, {"receipt_ids": ["other"]},
    {"changed_artifacts": {}}, {"changed_artifacts": {"a1": {"before": ["e" * 64], "after": "e" * 64}}},
    {"changed_artifacts": {"a2": {"before": ["d" * 64], "after": "e" * 64}}},
])
def test_quality_resolution_rejects_wrong_or_unchanged_evidence(wf, state, context, changes):
    state, context, prior = _failed_grade_and_repair(wf, state, context)
    context = _repair_resolution(wf, state, context, prior, **changes)
    with pytest.raises(ValueError):
        call(wf, state, context, "grade", criterion_id="c1", receipt_ids=["q2"], independent=True, resolution_receipt_id="resolution")


def test_same_quality_ids_revalidate_proof_and_reject_replaced_bytes(wf, state, context):
    state = configured(wf, state, context)
    context = quality_context(state, context)
    state = call(wf, state, context, "grade", criterion_id="c1", receipt_ids=["q1"], independent=True)
    changed = copy.deepcopy(context)
    changed["evidence"]["q1"]["digest"] = "0" * 64
    with pytest.raises(ValueError):
        call(wf, state, changed, "grade", criterion_id="c1", receipt_ids=["q1"], independent=True)
    changed["verify_receipt"] = lambda *args: False
    with pytest.raises(ValueError):
        call(wf, state, changed, "grade", criterion_id="c1", receipt_ids=["q1"], independent=True)


def test_repaired_grade_cannot_spend_another_quality_round(wf, state, context):
    state, context, prior = _failed_grade_and_repair(wf, state, context)
    context = _repair_resolution(wf, state, context, prior)
    state = call(wf, state, context, "grade", criterion_id="c1", receipt_ids=["q2"], independent=True, resolution_receipt_id="resolution")
    context = receipt(state, context, "q3", "quality_observation", context["evidence"]["q2"]["data"])
    with pytest.raises(ValueError, match="budget"):
        call(wf, state, context, "grade", criterion_id="c1", receipt_ids=["q3"], independent=True, resolution_receipt_id="resolution")


def test_repair_cannot_change_only_passing_artifact_and_discard_unchanged_failure(wf, state, context):
    state["contract"]["criteria"][0]["artifact_ids"].append("a2")
    state = configured(wf, state, context)
    context = quality_context(state, context, passed=False)
    passing = copy.deepcopy(context["evidence"]["q1"]["data"])
    passing.update(artifact_id="a2", observations={"expected": "ready", "observed": "ready", "consumer_verified": True})
    context = receipt(state, context, "old-pass", "quality_observation", passing)
    state = call(wf, state, context, "grade", criterion_id="c1", receipt_ids=["q1", "old-pass"], independent=True)
    prior = state["extensions"]["workflow"]["quality"]["c1"]
    assert prior["verdict"] == "DISAGREEMENT"
    new_bindings = {
        "rerolled-failure": {"digest": "e" * 64, "artifact_id": "a1", "artifact_digest": "d" * 64},
        "changed-passing": {"digest": "f" * 64, "artifact_id": "a2", "artifact_digest": "a" * 64},
    }
    with pytest.raises(ValueError, match="failing artifact"):
        wf.quality_resolution_requirements(prior, "c1", new_bindings)


def typed_dispatch(wf, state, context):
    result, context, brief = dispatch_ready(wf, state, context)
    context['binding']['project_root'] = '/fixture/project'
    context['artifacts']['source'] = {'id':'source','path':'inputs/source.txt','digest':'d'*64}
    brief['paths'] = ['/fixture/project/outputs','/fixture/project/scratch']
    context['admissions']['child-admission']['paths'] = brief['paths']
    brief['file_contract'] = {'schema_version':1,
        'immutable_inputs':[{'artifact_id':'source','path':'/fixture/project/inputs/source.txt','digest':'d'*64}],
        'output_roots':['/fixture/project/outputs'],'scratch_root':'/fixture/project/scratch'}
    return result, context, brief


def test_dispatch_requires_typed_input_and_output_roles(wf, state, context):
    result, context, brief = dispatch_ready(wf, state, context)
    brief.pop('file_contract')
    with pytest.raises(ValueError, match='file_contract'):
        call(wf, result, context, 'dispatch', **brief)


def test_typed_dispatch_preserves_roles_without_claiming_host_enforcement(wf, state, context):
    result, context, brief = typed_dispatch(wf, state, context)
    outcome = call(wf, result, context, 'dispatch', **brief)
    child = outcome['extensions']['workflow']['children']['child-a']
    assert child['file_contract'] == brief['file_contract']
    assert child['write_enforcement'] == 'UNVERIFIED'
    assert child['authority_granted'] is False


def test_dispatch_revalidates_exact_input_digest(wf, state, context):
    result, context, brief = typed_dispatch(wf, state, context)
    context['artifacts']['source']['digest'] = 'e'*64
    with pytest.raises(ValueError): call(wf, result, context, 'dispatch', **brief)


def native_cli_dispatch(wf, state, context):
    result, context, brief = typed_dispatch(wf, state, context)
    context['binding']['native_ref'] = 'codex:parent'
    context['admissions']['child-admission'].update(session_uuid='root-seat',native_ref='codex:parent')
    brief.update(mode='native-cli',client='claude')
    return result, context, brief


def test_native_cli_dispatch_does_not_fabricate_a_native_producer(wf, state, context):
    result, context, brief = native_cli_dispatch(wf, state, context)
    outcome = call(wf, result, context, 'dispatch', **brief)
    child = outcome['extensions']['workflow']['children']['child-a']
    assert child['producer'] is None
    assert child['write_enforcement'] == 'UNVERIFIED'
    assert child['authority_granted'] is False


@pytest.mark.parametrize('change',[{'client':'invented'},{'dispatch_receipt_id':'fabricated'}])
def test_native_cli_dispatch_rejects_unknown_client_and_collaboration_receipt(wf,state,context,change):
    result,context,brief=native_cli_dispatch(wf,state,context)
    with pytest.raises(ValueError):call(wf,result,context,'dispatch',**{**brief,**change})


def test_native_cli_dispatch_requires_current_parent_admission(wf,state,context):
    result,context,brief=native_cli_dispatch(wf,state,context)
    context['admissions']['child-admission']['session_uuid']='foreign-seat'
    with pytest.raises(ValueError):call(wf,result,context,'dispatch',**brief)


def test_native_cli_completion_requires_actual_bound_launch_observation(wf,state,context):
    result,context,brief=native_cli_dispatch(wf,state,context)
    result=call(wf,result,context,'dispatch',**brief)
    with pytest.raises(ValueError):
        call(wf,result,context,'return',child_id='child-a',disposition='complete',artifact_ids=[],evidence_ids=[],reason='self reported')


def launched_native_child(wf,state,context):
    result,context,brief=native_cli_dispatch(wf,state,context)
    result=call(wf,result,context,'dispatch',**brief)
    data={'schema_version':1,'child_id':'child-a','client':'claude',
          'producer':'claude:actual-child','file_contract_digest':wf._digest(brief['file_contract']),
          'boundary':{'status':'ENFORCED','mechanism':'claude-native','configuration_digest':'f'*64},
          'preservation':'PASS','violations':[], 'output_manifest':{},
          'terminal':'completed','native_exit_code':0,'elapsed_millis':1000,
          'usage':{'tokens':None,'usd_micros':None},'receipt_path':'/fixture/retained.json','receipt_digest':'a'*64}
    context=receipt(result,context,'worker-observed','native_worker',data)
    return result,context,data


def test_worker_record_binds_actual_producer_without_quality_acceptance(wf,state,context):
    result,context,data=launched_native_child(wf,state,context)
    result=call(wf,result,context,'worker_record',child_id='child-a',receipt_id='worker-observed')
    child=result['extensions']['workflow']['children']['child-a']
    assert child['producer']=='claude:actual-child'
    assert child['worker_receipt_id']=='worker-observed'
    assert child['disposition']=='running' and child['audit_status']=='required'
    assert child['authority_granted'] is False
    assert result['status']=='running'
    result=call(wf,result,context,'return',child_id='child-a',disposition='complete',artifact_ids=[],evidence_ids=['worker-observed'],reason='actual bounded worker complete')
    assert result['extensions']['workflow']['children']['child-a']['audit_status']=='required'


@pytest.mark.parametrize('change',[{'file_contract_digest':'0'*64},{'client':'muse'},
    {'child_id':'foreign-child'},{'producer':'codex:foreign'},{'boundary':{'status':'UNVERIFIED'}},
    {'producer':None}])
def test_worker_record_rejects_unbound_or_unenforced_observation(wf,state,context,change):
    result,context,data=launched_native_child(wf,state,context)
    context['evidence']['worker-observed']['data'].update(change)
    with pytest.raises(ValueError):call(wf,result,context,'worker_record',child_id='child-a',receipt_id='worker-observed')


def test_worker_failed_preservation_cannot_be_reported_complete(wf,state,context):
    result,context,data=launched_native_child(wf,state,context)
    context['evidence']['worker-observed']['data'].update(preservation='FAIL',violations=['preserved input changed'])
    result=call(wf,result,context,'worker_record',child_id='child-a',receipt_id='worker-observed')
    with pytest.raises(ValueError):
        call(wf,result,context,'return',child_id='child-a',disposition='complete',artifact_ids=[],evidence_ids=[],reason='worker said done')


def test_failed_launch_observation_is_retained_without_claiming_enforcement(wf,state,context):
    result,context,data=launched_native_child(wf,state,context)
    context['evidence']['worker-observed']['data'].update(producer=None,terminal='failed',native_exit_code=None,
        boundary={'status':'UNKNOWN','mechanism':'not-started','configuration_digest':'f'*64})
    result=call(wf,result,context,'worker_record',child_id='child-a',receipt_id='worker-observed')
    child=result['extensions']['workflow']['children']['child-a']
    assert child['worker_receipt_id']=='worker-observed' and child['write_enforcement']=='UNKNOWN'
    with pytest.raises(ValueError):call(wf,result,context,'return',child_id='child-a',disposition='complete',artifact_ids=[],evidence_ids=[],reason='cannot complete failed work')


def test_native_worker_cannot_claim_unproduced_returned_artifact(wf,state,context):
    result,context,data=launched_native_child(wf,state,context)
    context['artifacts']['unrelated']={'path':'unrelated.txt','digest':'e'*64}
    result=call(wf,result,context,'worker_record',child_id='child-a',receipt_id='worker-observed')
    with pytest.raises(ValueError):call(wf,result,context,'return',child_id='child-a',disposition='complete',artifact_ids=['unrelated'],evidence_ids=['worker-observed'],reason='claimed existing artifact')


def test_native_worker_cannot_integrate_contradictory_known_usage(wf,state,context):
    result,context,data=launched_native_child(wf,state,context)
    result=call(wf,result,context,'worker_record',child_id='child-a',receipt_id='worker-observed')
    result=call(wf,result,context,'return',child_id='child-a',disposition='complete',artifact_ids=[],evidence_ids=['worker-observed'],reason='actual launch')
    audit={'child_id':'child-a','task_id':'build','producer':'claude:actual-child','reviewer':'codex:independent',
        'integration_owner':'root-seat','accepted':True,'criteria':['c1'],'artifact_ids':[],
        'artifact_digests':{},'actual':{'searches':1}}
    context=receipt(result,context,'review','child_integration',audit)
    with pytest.raises(ValueError):call(wf,result,context,'integrate',child_id='child-a',receipt_id='review')
