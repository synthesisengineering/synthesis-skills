"""Real default-profile consumer and owner-derived disposition regressions."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib
import json
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'synthesis-project-management/scripts'))
from test_run_admission import world  # noqa: F401
from test_run_state import engine  # noqa: F401


def request(operation, data, state=None, identity=None):
    value = {'schema_version': 1, 'request_id': identity or operation,
             'operation': operation, 'project_id': 'alpha', 'input': data}
    if state is not None:
        value.update(run_id=state['run_id'], expected_revision=state['revision'])
    return value


@pytest.fixture
def facade(engine, monkeypatch, tmp_path):
    module = importlib.import_module('controller')
    import autopilot
    import run_profile
    monkeypatch.setattr(run_profile, 'USER_PROFILE_DEFAULT', str(tmp_path / 'no-user-profile.json'))
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    autopilot.engine()
    return module


def invoke(facade, world, value):
    return facade.handle(value, project=world['project'], actor=world['actor'],
                         runtime_root=world['runtime'], source_mode='synthetic')


def state_of(world, result):
    import run_state
    return run_state.load_run(world['project'], result['run_id'])


def consumer_run(facade, world, *, preference=None, uncertainty='low', profile_item_ids=None, domains=None,
                 optional_criterion=False, graph_criteria=None):
    contract = {'schema_version': 1, 'scope': ['Return the computed answer'], 'exclusions': [],
                'authority_refs': [], 'outcomes': [{'id': 'answer', 'criteria': ['accept']}],
                'criteria': [{'id': 'accept', 'description': 'Consumer reads the computed answer',
                              'required': True, 'method': 'consumer-check', 'artifact_ids': ['output'],
                              'evidence_ids': ['consumer']}]}
    if profile_item_ids:
        contract['criteria'][0]['profile_item_ids'] = profile_item_ids
    if optional_criterion:
        contract['criteria'].append({**deepcopy(contract['criteria'][0]), 'id': 'optional', 'required': False,
                                     'evidence_ids': ['optional-slot']})
        contract['outcomes'][0]['criteria'].append('optional')
    data = {'plan_ref': str(world['plan']), 'outcome_contract': contract,
            'dimensions': {'domains': domains or ['software'], 'uncertainty': uncertainty, 'effect': 'none',
                           'horizon': 'session', 'parallelizable': False},
            'resource_envelope': {'limits': {'model_tokens': {'limit': 100000, 'enforcement': 'forecast'}},
                                 'deadline': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}}
    if graph_criteria is not None:
        data['graph'] = {'nodes': [{'id': 'work', 'deps': [], 'criteria': graph_criteria, 'estimate': 1}], 'wip_limit': 1}
    if preference is not None:
        (world['project'] / 'preferences.json').write_text(json.dumps(preference))
        data['preference_layer_refs'] = {'user': 'preferences.json'}
    result = invoke(facade, world, request('start', data))
    assert result['status'] == 'READY', result
    state = state_of(world, result)
    frozen_profile = deepcopy(state['profile'])
    result = invoke(facade, world, request('next', {'mode': 'start'}, state))
    assert result['status'] == 'READY', result
    state = state_of(world, result)
    for identity, name, content, role in [
        ('output', 'answer.json', '{"answer": 5}\n', 'output'),
        ('program', 'check.py', 'import json\nfrom pathlib import Path\nprint(json.dumps(json.loads(Path("answer.json").read_text())))\n', 'input'),
    ]:
        (world['project'] / name).write_text(content)
        result = invoke(facade, world, request('record', {'kind': 'artifact', 'artifact_id': identity,
            'path': name, 'role': role, 'required': True, 'retention': 'durable'}, state, 'artifact.' + identity))
        assert result['status'] == 'RECORDED', result
        state = state_of(world, result)
    result = invoke(facade, world, request('record', {'kind': 'check', 'observer_kind': 'consumer-check',
        'arguments': {'criterion_id': 'accept', 'artifact_id': 'output', 'script_artifact_id': 'program',
                      'expected': {'answer': 5}, 'argv': [], 'timeout_seconds': 5}}, state, 'consumer'))
    assert result['status'] == 'RECORDED', result
    state = state_of(world, result)
    observed = [row for row in state['evidence'].values() if row['kind'] == 'consumer-check']
    assert len(observed) == 1 and observed[0]['data']['passed'] is True
    assert observed[0]['data']['execution']['sandbox_verified'] is True
    assert observed[0]['data']['observations']['observed'] == {'answer': 5}
    return state, frozen_profile


def test_default_profile_finishes_through_actual_consumer_and_current_owners(facade, world):
    state, profile = consumer_run(facade, world)
    result = invoke(facade, world, request('finish', {'disposition': 'completed'}, state))
    assert result['status'] == 'COMPLETED', result
    final = state_of(world, result)
    assert final['status'] == 'completed'
    assert final['profile'] == profile
    assert final['completion']['criteria'] == ['accept']
    observation = final['evidence'][final['profile_evidence']]['data']
    assert observation['completion_report']['remaining'] == []
    assert observation['completion_report']['authority_granted'] is False
    assert observation['completion_report']['outcomes'][0]['verified'] is True
    for identity in ('lessons-filed', 'framework-decisions'):
        assert observation['dispositions'][identity]['status'] == 'NOT_APPLICABLE'
    assert 'not selected' in observation['dispositions']['lessons-filed']['reason']
    for identity in ('core.outcome', 'core.authority', 'core.evidence', 'core.recovery', 'software.behavior', 'completion-report'):
        assert observation['dispositions'][identity]['status'] == 'SATISFIED'


def finish(facade, world, state, identity='finish'):
    return invoke(facade, world, request('finish', {'disposition': 'completed'}, state, identity))


def profile_context(world, state):
    import run_state
    return {**run_state.inspect_context(state, world['actor'], project=world['project']),
            'state': state, 'project': world['project'], 'actor': world['actor']}


def test_adopted_pm_default_finish_has_explicit_clean_successor_and_replays_without_journal_writes(facade, world):
    from test_execution_checkpoint import build
    import execution_checkpoint
    import run_state
    state, profile = consumer_run(facade, world)
    build(world)
    req = request('finish', {'disposition': 'completed'}, state)
    result = invoke(facade, world, req)
    assert result['status'] == 'COMPLETED', result
    final = state_of(world, result)
    proof = execution_checkpoint.current_proof(profile_context(world, final), final['extensions']['controller']['checkpoint']['pm'])
    assert proof['scope'] == 'TERMINAL_CLEAN_CHECKPOINT_SUCCESSOR', proof
    assert Path(proof['receipt_path']).is_file()
    assert proof['journal_head']['revision'] == final['revision']
    # D2: terminal normalization replaces the whole verified commitment, not
    # two records beneath a stale all-files digest.
    import profile_evidence
    basis = profile_evidence.checkpoint_basis(profile_context(world, final))
    original = final['extensions']['controller']['checkpoint']['pm']['project_files']
    assert basis['project_files'] == original
    assert basis['project_records'] == original['records']
    execution_checkpoint._validate_file_commitment(basis['project_files'])
    assert final['profile'] == profile
    assert run_state.completion_report(world['project'], final['run_id'], actor=world['actor'])['status'] == 'PASS'
    before = {p.name: p.read_bytes() for p in (run_state._home(world['project'], final['run_id']) / 'events').iterdir()}
    assert invoke(facade, world, req)['status'] == 'COMPLETED'
    assert before == {p.name: p.read_bytes() for p in (run_state._home(world['project'], final['run_id']) / 'events').iterdir()}


@pytest.mark.parametrize('damage', ['missing-receipt', 'foreign-receipt', 'fresh-checkpoint-changed-human-plan',
    'fresh-checkpoint-changed-operational-facts', 'changed-terminal-projection'])
def test_terminal_pm_successor_cannot_hide_missing_authority_or_changed_execution_basis(facade, world, damage):
    from test_execution_checkpoint import build
    import execution_checkpoint
    import project_state
    import run_state
    state, _profile = consumer_run(facade, world)
    build(world)
    result = finish(facade, world, state)
    assert result['status'] == 'COMPLETED', result
    final = state_of(world, result)
    context = profile_context(world, final)
    prior = final['extensions']['controller']['checkpoint']['pm']
    proof = execution_checkpoint.current_proof(context, prior)
    assert proof['scope'] == 'TERMINAL_CLEAN_CHECKPOINT_SUCCESSOR'
    receipt_path = Path(proof['receipt_path'])
    if damage == 'missing-receipt':
        receipt_path.rename(receipt_path.with_suffix('.retained'))
    elif damage == 'foreign-receipt':
        receipt = json.loads(receipt_path.read_text()); receipt['session_id'] = 'foreign'
        receipt_path.write_text(json.dumps(receipt))
    elif damage == 'changed-terminal-projection':
        (run_state._home(world['project'], final['run_id']) / 'terminal.json').write_text('{"invented":true}')
    else:
        fields = {}
        if damage == 'fresh-checkpoint-changed-human-plan':
            with world['plan'].open('a') as stream: stream.write('Changed human task after completion\n')
        else:
            fields['next_actions'] = ['A different operational promise']
        build(world, **fields)
        project_state.checkpoint_project(world['project'], session_id=final['owner']['session_uuid'],
            coordination_board=world['board'], receipt_root=receipt_path.parent, source_heads={},
            native_event=world['actor']['native_payload'])
        assert project_state.validate_checkpoint(world['project'], session_id=final['owner']['session_uuid'],
            coordination_board=world['board'], receipt_root=receipt_path.parent, source_heads={})[0] == 'PASS'
    assert execution_checkpoint.current_proof(context, prior)['scope'] == 'UNRESOLVED'
    assert run_state.completion_report(world['project'], final['run_id'], actor=world['actor'])['status'] == 'FAIL'


@pytest.mark.parametrize('selection', ['explicit-lesson', 'explicit-decision', 'lesson-criterion', 'decision-criterion',
    'report-criterion', 'weak-lesson-map', 'weak-decision-map', 'disabled-but-explicit-lesson'])
def test_semantic_or_capture_obligation_cannot_be_proved_by_software_consumer(facade, world, selection):
    item = 'lessons-filed' if 'lesson' in selection else 'completion-report' if 'report' in selection else 'framework-decisions'
    preference = None
    mapping = [item] if 'criterion' in selection or selection == 'disabled-but-explicit-lesson' else None
    if selection.startswith('explicit-'):
        preference = {'schema': 2, 'items': {item: {'enabled': True}}}
    elif selection.startswith('weak-'):
        preference = {'schema': 2, 'items': {item: {'criterion_ids': ['accept'], 'text': 'Ordinary artifact is sufficient'}}}
    elif selection.startswith('disabled-'):
        preference = {'schema': 2, 'items': {item: {'enabled': False}}}
    state, profile = consumer_run(facade, world, preference=preference, profile_item_ids=mapping)
    result = finish(facade, world, state)
    assert result['status'] == 'UNRESOLVED', result
    final = state_of(world, result)
    assert final['status'] != 'completed' and final['profile'] == profile


@pytest.mark.parametrize('kind', ['decision', 'reusable-finding'])
@pytest.mark.parametrize('mapped', [False, True])
def test_recorded_material_obligation_is_not_dropped_for_missing_or_unrelated_mapping(facade, world, kind, mapped):
    state, profile = consumer_run(facade, world)
    result = invoke(facade, world, request('record', {'kind': 'profile_obligation', 'obligation_id': 'material',
        'obligation_kind': kind, 'artifact_ids': ['output'], 'criterion_ids': ['accept'] if mapped else [],
        'reason': 'Synthetic fixture records a real material obligation; capture is not yet accepted'}, state, 'material'))
    assert result['status'] == 'RECORDED', result
    state = state_of(world, result)
    result = finish(facade, world, state)
    assert result['status'] == 'UNRESOLVED', result
    final = state_of(world, result)
    assert final['status'] != 'completed' and final['profile'] == profile
    observations = [row['data'] for row in final['evidence'].values() if row['kind'] == 'profile']
    assert observations and 'trigger:material' in observations[-1]['completion_report']['remaining']


@pytest.mark.parametrize('damage', ['output', 'program', 'native-owner', 'unresolved-wait', 'unresolved-effect'])
def test_actual_default_finish_refuses_missing_current_outcome_or_owner_obligations(facade, world, damage):
    import run_state
    from test_run_state import command
    state, _profile = consumer_run(facade, world)
    if damage in {'output', 'program'}:
        (world['project'] / state['artifacts'][damage]['path']).write_text('Changed after verified consumer')
    elif damage == 'native-owner':
        from test_run_admission import write_board
        write_board(world, status='released')
    elif damage == 'unresolved-wait':
        state = command(run_state, world, state, 'wait.add', {'id': 'dependency', 'kind': 'external', 'reason': 'Still needs an actual readback'})
    else:
        # The core owner permits recording prepared intent without dispatch;
        # it cannot close while its actual outcome remains unresolved.
        state = command(run_state, world, state, 'effect.prepare', {'id': 'effect', 'target': 'fixture',
            'payload_digest': 'a' * 64, 'idempotency_key': 'fixture-key', 'authority_ref': ''})
    result = finish(facade, world, state)
    assert result['status'] == 'UNRESOLVED', result
    assert state_of(world, result)['status'] != 'completed'


@pytest.mark.parametrize('damage', ['human-plan', 'context', 'summary', 'current', 'ordinary-file', 'observation-input'])
def test_profile_source_is_rederived_after_actual_finish_and_rejects_current_drift(facade, world, damage):
    import run_state
    state, _profile = consumer_run(facade, world)
    result = finish(facade, world, state)
    assert result['status'] == 'COMPLETED', result
    final = state_of(world, result)
    home = run_state._home(world['project'], final['run_id'])
    if damage == 'human-plan':
        with world['plan'].open('a') as stream: stream.write('Changed human plan\n')
    elif damage == 'context':
        with (world['project'] / 'CONTEXT.md').open('a') as stream: stream.write('Changed recovery context\n')
    elif damage in {'summary', 'current'}:
        (home / ('summary.md' if damage == 'summary' else 'current.json')).write_text('Unverified projection')
    elif damage == 'ordinary-file':
        (world['project'] / 'unreviewed.json').write_text('{"unexpected":true}')
    else:
        path = next(home.glob('inputs/*.json'))
        path.write_text('{"schema_version":1,"changed":true}')
    assert run_state.completion_report(world['project'], final['run_id'], actor=world['actor'])['status'] == 'FAIL'


def test_user_profile_file_change_does_not_mutate_active_profile(facade, world):
    preference = {'schema': 2, 'items': {'framework-decisions': {'enabled': False}}}
    state, profile = consumer_run(facade, world, preference=preference)
    (world['project'] / 'preferences.json').write_text(json.dumps({'schema': 2, 'items': {'blog-seeds': {'enabled': True}}}))
    result = finish(facade, world, state)
    assert result['status'] == 'COMPLETED', result
    assert state_of(world, result)['profile'] == profile


@pytest.mark.parametrize('domain', ['research', 'writing', 'data', 'browser', 'knowledge', 'operations'])
def test_required_additional_domain_cannot_be_satisfied_by_an_unrelated_real_consumer(facade, world, domain):
    state, _profile = consumer_run(facade, world, domains=['software', domain])
    result = finish(facade, world, state)
    assert result['status'] == 'UNRESOLVED', result
    final = state_of(world, result)
    assert final['extensions']['workflow']['quality']['accept']['verdict'] == 'PASS'
    assert final['status'] != 'completed'


def test_material_decision_trigger_uses_owner_strategy_identity_not_cosmetic_name():
    from profile_evidence import _decision_triggers
    state = {'contract_revision': 1, 'extensions': {'workflow': {}, 'workflow_persistence': {'attempts': [
        {'obligation_id': 'outcome', 'strategy_key': 'same-owner-causal-strategy', 'strategy': {'id': 'first'}},
        {'obligation_id': 'outcome', 'strategy_key': 'same-owner-causal-strategy', 'strategy': {'id': 'renamed'}}]}}}
    dimensions = {'domains': ['software'], 'uncertainty': 'low'}
    assert not _decision_triggers(state, dimensions)
    state['extensions']['workflow_persistence']['attempts'][1]['strategy_key'] = 'different-owner-causal-strategy'
    assert 'owner-observed changed strategy for outcome' in _decision_triggers(state, dimensions)


@pytest.mark.parametrize('selector', ['graph', 'custom-profile'])
def test_optional_contract_criterion_selected_by_graph_or_profile_is_actually_verified(facade, world, selector):
    preference = None if selector == 'graph' else {'schema': 2, 'items': {'local-audit': {
        'text': 'Verify the extra selected requirement', 'evidence_hint': 'Actual consumer', 'criterion_ids': ['optional']}}}
    state, profile = consumer_run(facade, world, preference=preference, optional_criterion=True,
                                  graph_criteria=None if selector == 'graph' else ['accept'])
    contract = deepcopy(state['contract'])
    result = invoke(facade, world, request('record', {'kind': 'check', 'observer_kind': 'consumer-check',
        'arguments': {'criterion_id': 'optional', 'artifact_id': 'output', 'script_artifact_id': 'program',
                      'expected': {'answer': 5}, 'argv': [], 'timeout_seconds': 5}}, state, 'optional-check'))
    assert result['status'] == 'RECORDED', result
    state = state_of(world, result)
    result = finish(facade, world, state)
    assert result['status'] == 'COMPLETED', result
    final = state_of(world, result)
    assert final['contract'] == contract and final['profile'] == profile
    assert final['contract']['criteria'][1]['required'] is False
    assert final['verification']['optional']
    assert final['completion']['criteria'] == ['accept', 'optional']


def semantic_run(facade, world, *, obligation='decision', fault=None, family='writing', uncertainty='low'):
    """Programmed native-review controls, never evidence of a live model verdict.

    Actual PM admission, native pair parsing, source-byte rederivation, domain
    calibration, criterion acceptance and facade finish execute unchanged.
    """
    from test_domain_quality import make_package, complete_data
    from test_evidence_bridge import append_claude_tool, record
    from test_run_state import command
    import run_state
    contract = {'schema_version': 1, 'scope': ['Deliver a supported useful note'], 'exclusions': [],
        'authority_refs': [], 'outcomes': [{'id': 'note', 'criteria': ['accept']}],
        'criteria': [{'id': 'accept', 'description': 'Deliver a supported useful note matching the supplied brief',
                     'required': True, 'method': 'quality_observation', 'artifact_ids': ['draft'], 'evidence_ids': ['review']}]}
    data = {'plan_ref': str(world['plan']), 'outcome_contract': contract,
        'dimensions': {'domains': [family], 'uncertainty': uncertainty, 'effect': 'none', 'horizon': 'session', 'parallelizable': False},
        'resource_envelope': {'limits': {'model_tokens': {'limit': 100000, 'enforcement': 'forecast'}},
                             'deadline': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}}
    result = invoke(facade, world, request('start', data))
    assert result['status'] == 'READY', result
    state = state_of(world, result)
    result = invoke(facade, world, request('next', {'mode': 'start'}, state))
    assert result['status'] == 'READY', result
    state = state_of(world, result)
    context, defects = make_package(world['project'], family=family)
    for identity, row in context['artifacts'].items():
        result = invoke(facade, world, request('record', {'kind': 'artifact', 'artifact_id': identity,
            'path': row['path'], 'role': row['role'], 'required': True, 'retention': 'durable'}, state, 'artifact.' + identity))
        assert result['status'] == 'RECORDED', result
        state = state_of(world, result)
    context = profile_context(world, state)
    data = complete_data(context, defects)
    data['producer'] = state['owner']['native_ref']
    data['reviewer'] = 'claude-agent:semantic-review'
    data['calibration']['reviewer'] = data['reviewer']
    if fault == 'missing-assessment':
        data['domain_review']['assessment']['criteria'].pop()
    elif fault == 'bad-control':
        data['calibration']['observations'][1]['assessment']['criteria'][0]['verdict'] = 'PASS'
    elif fault == 'unsupported-quote':
        data['domain_review']['assessment']['criteria'][0]['evidence'][0]['quote'] = 'Words absent from the source'
    bindings = {key: state[key] for key in ('run_id', 'contract_digest', 'profile_digest')}
    prompt = {'schema_version': 1, 'kind': 'quality_observation', 'bindings': bindings,
              'artifact_digests': data['domain_review']['input_digests'], 'producer': data['producer']}
    response = {'schema_version': 1, 'kind': 'quality_observation', 'bindings': bindings, 'data': data}
    append_claude_tool(world, 'Agent', {'prompt': json.dumps({'autopilot_review': prompt})},
                      {'autopilot_review': response}, 'semantic-review')
    data = {**data, 'source': {'kind': 'native-agent', 'call_id': 'semantic-review'}}
    receipt = record('quality_observation', data, context)
    path = world['project'] / 'semantic-receipt.json'
    path.write_text(json.dumps(receipt))
    state = command(run_state, world, state, 'artifact.register', {'id': 'semantic-receipt', 'path': str(path),
        'role': 'evidence', 'required': True, 'retention': 'durable'})
    state = command(run_state, world, state, 'evidence.record', {'id': 'review', 'kind': 'quality_observation', 'artifact_id': 'semantic-receipt'})
    if fault == 'changed-source':
        (world['project'] / state['artifacts']['brief']['path']).write_text('A different brief after review')
    sources = ['brief']
    if fault == 'unrelated-trigger':
        path = world['project'] / 'other-decision.txt'; path.write_text('An unrelated material choice')
        state = command(run_state, world, state, 'artifact.register', {'id': 'other-choice', 'path': str(path),
            'role': 'input', 'required': True, 'retention': 'durable'})
        sources = ['other-choice']
    if obligation is None:
        return state
    result = invoke(facade, world, request('record', {'kind': 'profile_obligation', 'obligation_id': 'material',
        'obligation_kind': obligation, 'artifact_ids': sources if fault != 'changed-source' else ['draft'],
        'criterion_ids': ['accept'], 'reason': 'A typed synthetic material finding is bound to the reviewed source'}, state, 'material'))
    assert result['status'] == 'RECORDED', result
    return state_of(world, result)


@pytest.mark.parametrize('obligation', ['decision', 'reusable-finding'])
def test_substantive_native_parser_control_closes_recorded_decision_or_capture(facade, world, obligation):
    state = semantic_run(facade, world, obligation=obligation)
    result = finish(facade, world, state)
    assert result['status'] == 'COMPLETED', result
    final = state_of(world, result)
    rows = final['evidence'][final['profile_evidence']]['data']['dispositions']
    assert rows['framework-decisions' if obligation == 'decision' else 'lessons-filed']['status'] == 'SATISFIED'
    assert rows['writing.reader']['status'] == 'SATISFIED'


@pytest.mark.parametrize('fault', ['missing-assessment', 'bad-control', 'unsupported-quote', 'changed-source', 'unrelated-trigger'])
def test_semantic_claim_without_current_substantive_bound_review_cannot_close(facade, world, fault):
    state = semantic_run(facade, world, fault=fault)
    result = finish(facade, world, state)
    assert result['status'] == 'UNRESOLVED', result
    assert state_of(world, result)['status'] != 'completed'


@pytest.mark.parametrize('uncertainty', ['low', 'high'])
def test_default_research_profile_uses_current_semantic_outcome_without_manual_item_mapping(facade, world, uncertainty):
    state = semantic_run(facade, world, obligation=None, family='research', uncertainty=uncertainty)
    result = finish(facade, world, state)
    assert result['status'] == 'COMPLETED', result
    final = state_of(world, result)
    data = final['evidence'][final['profile_evidence']]['data']
    assert data['dispositions']['framework-decisions']['status'] == 'SATISFIED'
    assert data['dispositions']['framework-decisions']['criterion_ids'] == ['accept']
    if uncertainty == 'high':
        assert data['dispositions']['optional.exploration']['status'] == 'SATISFIED'
        assert data['dispositions']['evidence.independent']['status'] == 'SATISFIED'
