"""A8 causal and acceptance fixtures; every native file is synthetic."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_controller import facade, world, engine, invoke, request, start_request, state_of
from test_workflow import wf, state, context, dispatch_ready, call


def test_default_controller_exposes_separate_unknown_and_estimated_resources(facade, world):
    response = invoke(facade, world, start_request(world))
    accounting = response['coverage']['resources']
    assert accounting['billable_cost'] is None
    assert accounting['native']['aggregate_tree_usage'] is None
    assert accounting['human_effort']['active_review_minutes'] is None
    assert accounting['limits']['model_tokens']['enforcement_scope'] == 'owner_admission_forecast'


def test_default_controller_selects_direct_without_changing_quality(facade, world):
    response = invoke(facade, world, start_request(world))
    state = state_of(world, response)
    selection = response['coverage']['execution_policy']
    assert selection['shape'] == 'direct_verified'
    assert selection['authority_granted'] is False
    assert selection['invariants']['contract_digest'] == state['contract_digest']
    assert selection['invariants']['profile_digest'] == state['profile_digest']


def test_fanout_refuses_unfunded_verification_and_recovery(wf, state, context):
    current, context, payload = dispatch_ready(wf, state, context)
    payload.pop('verification_reservation_id', None)
    payload.pop('recovery_reservation_id', None)
    with pytest.raises(ValueError, match='verification|recovery|completion'):
        call(wf, current, context, 'dispatch', **payload)


def test_actual_native_usage_reaches_journal_resource_projection(facade, world):
    response = invoke(facade, world, start_request(world))
    current = state_of(world, response)
    session = world['actor']['native_payload']['session_id']
    row = {'type': 'assistant', 'sessionId': session, 'message': {'role': 'assistant',
        'id': 'response-one', 'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': 'fixture'}],
        'usage': {'input_tokens': 7, 'output_tokens': 3}}}
    with world['transcript'].open('a') as stream:
        stream.write(json.dumps(row)+'\n')
    recorded = invoke(facade, world, request('record', {'kind': 'native', 'source_handle': 'root',
        'through_event': None, 'task_id': None, 'attempt_id': None}, current, 'usage'))
    state = state_of(world, recorded)
    accounting = recorded['coverage']['resources']
    assert accounting['native']['by_producer']['root']['distinct_response_tokens'] == 10
    assert accounting['native']['by_producer']['root']['mode'] == 'synthetic'
    assert accounting['native']['aggregate_tree_usage'] is None
    assert state['extensions']['workflow']['budget']['native_usage']['measurements']


def _claude_usage(world, identity='one', amount=10, *, final=True):
    row = {'type': 'assistant', 'sessionId': world['actor']['native_payload']['session_id'],
        'message': {'role': 'assistant', 'id': identity, 'stop_reason': 'end_turn' if final else None,
            'content': [{'type': 'text', 'text': 'synthetic response'}],
            'usage': {'input_tokens': amount - 2, 'output_tokens': 2}}}
    with world['transcript'].open('a') as stream:
        stream.write(json.dumps(row)+'\n')


def _record_native(facade, world, state, identity):
    result = invoke(facade, world, request('record', {'kind': 'native', 'source_handle': 'root',
        'through_event': None, 'task_id': None, 'attempt_id': None}, state, identity))
    assert result['status'] == 'RECORDED', result
    return state_of(world, result), result


@pytest.mark.parametrize('finals', [[True, True], [False, True], [True, False, True]])
def test_real_native_response_dedup_and_provisional_reconciliation(facade, world, finals):
    state = state_of(world, invoke(facade, world, start_request(world)))
    for index, final in enumerate(finals):
        _claude_usage(world, final=final)
        state, response = _record_native(facade, world, state, 'native-' + str(index))
    view = response['coverage']['resources']['native']['by_producer']['root']
    assert view['distinct_responses'] == 1
    assert view['distinct_response_tokens'] == 10
    assert view['unresolved_measurements'] == []
    import run_state
    assert run_state.load_run(world['project'], state['run_id'])['extensions']['workflow']['budget'] == state['extensions']['workflow']['budget']


def test_conflicting_native_response_is_retained_and_blocks_new_work(facade, world):
    state = state_of(world, invoke(facade, world, start_request(world)))
    _claude_usage(world, amount=10)
    state, _ = _record_native(facade, world, state, 'first')
    _claude_usage(world, amount=11)
    state, response = _record_native(facade, world, state, 'contradiction')
    assert response['coverage']['resources']['native']['conflicts']
    assert response['coverage']['resources']['native']['by_producer']['root']['distinct_response_tokens'] == 10
    blocked = invoke(facade, world, request('next', {'mode': 'start'}, state, 'blocked'))
    assert blocked['status'] == 'UNRESOLVED'
    assert state_of(world, blocked)['extensions']['workflow']['graph']['nodes']['work']['status'] == 'pending'


def test_native_token_lower_bound_blocks_admission_without_claiming_provider_enforcement(facade, world):
    req = start_request(world)
    req['input']['resource_envelope']['limits']['model_tokens'] = {'limit': 10, 'enforcement': 'hard'}
    state = state_of(world, invoke(facade, world, req))
    _claude_usage(world, amount=10)
    # No manual observe: the actual next consumer catches up before admission.
    response = invoke(facade, world, request('next', {'mode': 'start'}, state, 'limited'))
    assert response['status'] == 'UNRESOLVED', response
    assert response['coverage']['resources']['limits']['model_tokens']['provider_hard_limit_enforced'] is False
    assert state_of(world, response)['extensions']['workflow']['graph']['nodes']['work']['status'] == 'pending'


def _reservation(identity, amount, category='work', parent=None):
    row = {'reservation_id': identity, 'amounts': {'model_tokens': amount}, 'category': category}
    if parent is not None:
        row['parent_id'] = parent
    return row


def test_actual_controller_full_tree_interrupted_debt_and_reconciliation(facade, world):
    import workflow
    state = state_of(world, invoke(facade, world, start_request(world)))
    rows = [_reservation('root', 100), _reservation('child', 60, parent='root'),
            _reservation('grandchild', 30, parent='child'), _reservation('integration', 20, 'integration'),
            _reservation('verify', 20, 'verification'), _reservation('recovery', 20, 'recovery')]
    plan = request('record', {'kind': 'resource_plan', 'reservations': rows}, state, 'resource-plan')
    response = invoke(facade, world, plan)
    assert response['status'] == 'RECORDED', response
    current = state_of(world, response)
    assert invoke(facade, world, plan)['revision'] == current['revision']
    assert workflow.budget_summary(current)['model_tokens']['committed'] == 160
    def settle(identity, actual):
        nonlocal current
        result = invoke(facade, world, request('record', {'kind': 'resource_settle',
            'reservation_id': identity, 'actual': actual}, current, 'settle-' + identity + '-' + str(current['revision'])))
        assert result['status'] == 'RECORDED', result
        current = state_of(world, result)
        return result
    settle('grandchild', None)
    assert workflow.budget_summary(current)['model_tokens']['committed'] == 160
    settle('grandchild', {'model_tokens': 17})
    settle('child', {'model_tokens': 11})
    result = settle('root', {'model_tokens': 7})
    view = result['coverage']['resources']
    assert view['limits']['model_tokens']['known_spent'] == 35
    assert view['limits']['model_tokens']['committed'] == 95
    assert view['tree']['root']['subtree_known_reported_actual']['model_tokens'] == 35
    assert view['tree']['child']['subtree_known_reported_actual']['model_tokens'] == 28
    assert view['limits']['model_tokens']['measurement_provenance'].startswith('owner_reported')
    assert view['native']['aggregate_tree_usage'] is None
    assert view['billable_cost'] is None
    refused = invoke(facade, world, request('record', {'kind': 'resource_settle',
        'reservation_id': 'grandchild', 'actual': {'model_tokens': 0}}, current, 'rewrite'))
    assert refused['status'] == 'UNRESOLVED'
    assert state_of(world, refused) == current


@pytest.mark.parametrize('fault', ['duplicate', 'overrun', 'foreign_parent', 'bool_amount'])
def test_resource_bundle_is_atomic_and_cannot_create_authority(facade, world, fault):
    req = start_request(world)
    req['input']['resource_envelope']['limits']['model_tokens'] = {'limit': 100, 'enforcement': 'hard'}
    state = state_of(world, invoke(facade, world, req))
    rows = [_reservation('root', 90)]
    rows += {'duplicate': [_reservation('root', 1)], 'overrun': [_reservation('other', 11)],
             'foreign_parent': [_reservation('child', 2, parent='missing')],
             'bool_amount': [_reservation('invalid', True)]}[fault]
    result = invoke(facade, world, request('record', {'kind': 'resource_plan', 'reservations': rows}, state, 'bad-plan'))
    assert result['status'] == 'UNRESOLVED', result
    assert state_of(world, result) == state
    assert not state['extensions']['workflow']['budget']['reservations']


@pytest.mark.parametrize('field', ['integration_reservation_id', 'verification_reservation_id', 'recovery_reservation_id'])
def test_fanout_reserves_cannot_be_refunded_before_child_audit(wf, state, context, field):
    current, context, brief = dispatch_ready(wf, state, context)
    current = call(wf, current, context, 'dispatch', **brief)
    with pytest.raises(ValueError, match='audit'):
        call(wf, current, context, 'settle', reservation_id=brief[field], actual={'searches': 0})
    interrupted = call(wf, current, context, 'settle', reservation_id=brief[field], actual=None)
    assert wf.budget_summary(interrupted)['searches']['committed'] == 9


@pytest.mark.parametrize('dimensions,shape', [
    ({}, 'direct_verified'), ({'uncertainty': 'high'}, 'investigate_deliver'),
    ({'domains': ['software', 'research']}, 'investigate_deliver'),
    ({'horizon': 'reboot'}, 'durable_program'), ({'effect': 'external'}, 'durable_program')])
def test_shape_choice_retains_contract_profile_model_effort(wf, state, context, dimensions, shape):
    from test_workflow import configured, dimensions as defaults
    from resource_policy import select_policy
    state['contract']['model'] = 'explicit-provider-model'
    state['contract']['reasoning_effort'] = 'explicit-effort'
    current = configured(wf, state, context, **dimensions)
    before = deepcopy(current)
    choice = select_policy(current)
    assert choice['shape'] == shape
    assert current == before
    assert choice['authority_granted'] is False and choice['acceptance_changed'] is False
    assert choice['invariants']['contract_digest'] == state['contract_digest']
    if dimensions.get('horizon') == 'reboot':
        assert choice['obligations'][0]['kind'] == 'observed_survival_required'


def test_stable_preference_and_hysteresis_require_real_work_boundary(wf, state, context):
    from test_workflow import graphed
    from resource_policy import select_policy
    current = graphed(wf, state, context)
    flow = current['extensions']['workflow']
    first = select_policy(current, {'mode': 'stable', 'shape': 'direct_verified'})
    assert first['shape'] == 'direct_verified'
    flow['execution_policy'] = first
    with pytest.raises(ValueError, match='immutable'):
        select_policy(current, {'mode': 'adaptive'})
    flow.pop('execution_policy')
    flow['profile']['dimensions']['uncertainty'] = 'high'
    flow['execution_policy'] = select_policy(current)
    flow['profile']['dimensions']['uncertainty'] = 'low'
    flow['graph']['nodes'] = {'simple': {'id': 'simple', 'deps': [], 'status': 'pending'}}
    assert select_policy(current)['shape'] == 'investigate_deliver'
    flow['graph']['nodes']['simple']['status'] = 'done'
    assert select_policy(current)['shape'] == 'direct_verified'


def test_controller_policy_is_journaled_and_stable_preference_not_an_authority(facade, world):
    req = start_request(world)
    req['input']['execution_policy'] = {'mode': 'stable', 'shape': 'investigate_deliver'}
    response = invoke(facade, world, req)
    assert response['status'] == 'READY', response
    state = state_of(world, response)
    original_contract, original_profile = deepcopy(state['contract']), deepcopy(state['profile'])
    result = invoke(facade, world, request('record', {'kind': 'execution_policy'}, state, 'choose-again'))
    final = state_of(world, result)
    assert result['coverage']['execution_policy']['shape'] == 'investigate_deliver'
    assert final['contract'] == original_contract and final['profile'] == original_profile
    assert len(final['extensions']['workflow']['execution_policy']['history']) == 1


def _codex_owner(world, monkeypatch):
    from test_workflow import _policy_owner
    native = world['actor']['native_payload']['session_id']
    home = world['scratch'] / 'codex-resource-fixture'
    transcript = home / 'sessions' / ('rollout-' + native + '.jsonl')
    transcript.parent.mkdir(parents=True)
    transcript.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': native, 'cwd': str(world['repo'])}})+'\n')
    world['transcript'] = transcript
    world['actor']['native_payload']['transcript_path'] = str(transcript)
    world['board'].write_text(world['board'].read_text().replace('| claude |', '| codex |').replace('cc:'+native, 'codex:'+native))
    monkeypatch.setenv('CODEX_HOME', str(home))
    monkeypatch.setenv('SYNTHESIS_CLIENT_SESSION_REF', 'codex:'+native)
    return _policy_owner(world)


def _usage_row(root, thread, response, amount, cumulative=None):
    counters = {'input_tokens': amount-2, 'output_tokens': 2, 'total_tokens': amount}
    return {'type': 'token_usage_record', 'payload': {'thread_id': thread, 'session_id': root,
        'turn_id': 'turn', 'root_turn_id': 'root-turn', 'response_id': response, 'usage': counters,
        'turn_token_usage': counters, 'thread_token_usage': cumulative or counters}}


def _append_path(path, *rows):
    with path.open('a') as stream:
        for row in rows:
            stream.write(json.dumps(row)+'\n')


def _owner_budget(runtime, world, state):
    from datetime import datetime, timedelta, timezone
    from test_run_state import command
    return command(runtime, world, state, 'workflow.budget', {'limits': {'model_tokens': {'limit': 1000, 'enforcement': 'forecast'}},
        'deadline': (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()})


def _delegate(runtime, world, state, child, task, stem, *, parent=None):
    from datetime import datetime, timedelta, timezone
    from test_run_state import command
    from test_workflow import _owner_register
    directory = world['project'] / ('delegated-' + stem)
    for name in ('output', 'scratch'):
        (directory / name).mkdir(parents=True)
    brief = {'child_id': child, 'task_id': task, 'deliverables': ['Produce verified artifact'],
        'paths': [str(directory)], 'criteria': ['accept'], 'reservation_id': stem,
        'integration_reservation_id': stem+'-integration', 'verification_reservation_id': stem+'-verification',
        'recovery_reservation_id': stem+'-recovery', 'integration_owner': state['owner']['session_uuid'],
        'return_contract': ['artifact_ids', 'evidence_ids', 'disposition'], 'cancellation': 'Retain work and unknown debt',
        'mode': 'artifact-only', 'file_contract': {'schema_version': 1, 'immutable_inputs': [],
            'output_roots': [str(directory/'output')], 'scratch_root': str(directory/'scratch')}}
    if parent is not None:
        brief['parent_child_id'] = parent
    binding = {key: state[key] for key in ('run_id', 'contract_digest', 'profile_digest')}
    envelope = {'schema_version': 1, 'kind': 'delegation', 'bindings': binding, 'data': brief}
    _append_path(world['transcript'],
        {'type': 'response_item', 'payload': {'type': 'function_call', 'namespace': 'collaboration',
            'name': 'followup_task', 'call_id': 'dispatch-'+stem, 'arguments': json.dumps({'target': child,
                'message': json.dumps({'autopilot_delegation': envelope})})}},
        {'type': 'response_item', 'payload': {'type': 'function_call_output', 'call_id': 'dispatch-'+stem, 'output': ''}})
    now = datetime.now(timezone.utc)
    state = _owner_register(runtime, world, state, 'dispatch-file-'+stem, {'kind': 'delegation',
        'bindings': {**state['owner'], **binding}, 'observed_at': now.isoformat(),
        'expires_at': (now+timedelta(hours=1)).isoformat(),
        'data': {**brief, 'source': {'kind': 'native-dispatch', 'call_id': 'dispatch-'+stem}}}, role='evidence')
    state = command(runtime, world, state, 'evidence.record', {'id': 'dispatch-proof-'+stem, 'kind': 'delegation',
        'artifact_id': 'dispatch-file-'+stem})
    return command(runtime, world, state, 'workflow.dispatch', {**brief, 'admission_id': 'parent',
        'dispatch_receipt_id': 'dispatch-proof-'+stem,
        'admission_requests': [{'id': 'parent', 'actor': world['actor'], 'paths': [str(directory)]}]})


@pytest.mark.parametrize('fault', [None, 'wrong_parent', 'missing_parent', 'parent_header_changed', 'foreign_root', 'symlink'])
def test_real_root_child_grandchild_custody_and_usage(world, monkeypatch, fault):
    import resource_policy
    from test_run_state import command
    runtime, state = _codex_owner(world, monkeypatch)
    state = _owner_budget(runtime, world, state)
    state = command(runtime, world, state, 'workflow.graph', {'reason': 'Declared independent leaf task', 'wip_limit': 2,
        'nodes': [{'id': 'work', 'deps': [], 'criteria': ['accept'], 'estimate': 1},
                  {'id': 'leaf', 'deps': [], 'criteria': ['accept'], 'estimate': 1}]})
    reservations = [_reservation('worker', 600)] + [_reservation('worker-'+name, 50, name)
        for name in ('integration', 'verification', 'recovery')]
    reservations += [_reservation('leaf', 200, parent='worker')] + [_reservation('leaf-'+name, 50, name, parent='worker')
        for name in ('integration', 'verification', 'recovery')]
    state = command(runtime, world, state, 'workflow.resource_plan', {'reservations': reservations})
    state = _delegate(runtime, world, state, '/root/worker', 'work', 'worker')
    root = world['actor']['native_payload']['session_id']
    child = '01990000-0000-7000-8000-000000000041'
    grandchild = '01990000-0000-7000-8000-000000000042'
    child_path = world['transcript'].with_name('child.jsonl')
    child_header = {'type': 'session_meta', 'payload': {'id': child, 'session_id': root,
        'parent_thread_id': root, 'agent_path': '/root/worker'}}
    child_path.write_text(json.dumps(child_header)+'\n')
    _append_path(child_path, _usage_row(root, child, 'child-response', 20))
    if fault != 'missing_parent':
        state = command(runtime, world, state, 'native.observe', {'source_handle': 'child:/root/worker',
            'through_event': None, 'task_id': 'work', 'attempt_id': None})
    state = _delegate(runtime, world, state, '/root/worker/leaf', 'leaf', 'leaf', parent='/root/worker')
    leaf_path = world['transcript'].with_name('leaf.jsonl')
    leaf_header = {'type': 'session_meta', 'payload': {'id': grandchild, 'session_id': 'foreign' if fault == 'foreign_root' else root,
        'parent_thread_id': root if fault == 'wrong_parent' else child, 'agent_path': '/root/worker/leaf'}}
    leaf_path.write_text(json.dumps(leaf_header)+'\n')
    _append_path(leaf_path, _usage_row(root, grandchild, 'leaf-response', 30))
    _append_path(world['transcript'], _usage_row(root, root, 'root-response', 10))
    if fault == 'parent_header_changed':
        child_path.write_text(child_path.read_text().replace(child, '01990000-0000-7000-8000-000000000099'))
    if fault == 'symlink':
        retained = leaf_path.with_suffix('.retained'); leaf_path.rename(retained); leaf_path.symlink_to(retained)
    payload = {'source_handle': 'child:/root/worker/leaf', 'through_event': None, 'task_id': 'leaf', 'attempt_id': None}
    if fault is not None:
        with pytest.raises((ValueError, OSError)):
            command(runtime, world, state, 'native.observe', payload)
        assert runtime.load_run(world['project'], state['run_id']) == state
        return
    state = command(runtime, world, state, 'native.observe', payload)
    state = command(runtime, world, state, 'native.observe', {'source_handle': 'root', 'through_event': None, 'task_id': None, 'attempt_id': None})
    view = resource_policy.summary(state)
    assert [view['native']['by_producer'][name]['distinct_response_tokens'] for name in
            ('root', 'child:/root/worker', 'child:/root/worker/leaf')] == [10, 20, 30]
    assert view['native']['by_producer']['child:/root/worker/leaf']['parent'] == 'child:/root/worker'
    assert view['native']['known_response_counter_sum'] == 60
    assert view['native']['aggregate_tree_usage'] is None  # owner cannot prove scope nonoverlap
    assert view['limits']['model_tokens']['committed'] == 750
    assert runtime.load_run(world['project'], state['run_id']) == state


def test_actual_cumulative_reset_restart_never_refunds_or_double_counts(world, monkeypatch):
    import resource_policy
    from test_run_state import command
    runtime, state = _codex_owner(world, monkeypatch)
    state = _owner_budget(runtime, world, state)
    root = world['actor']['native_payload']['session_id']
    sequence = [('a', 10, 10), ('b', 15, 25), ('b', 15, 25), ('c', 5, 5), ('d', 7, 12)]
    for index, (identity, amount, cumulative) in enumerate(sequence):
        totals = {'input_tokens': cumulative-2, 'output_tokens': 2, 'total_tokens': cumulative}
        _append_path(world['transcript'], _usage_row(root, root, identity, amount, totals))
        state = command(runtime, world, state, 'native.observe', {'source_handle': 'root',
            'through_event': None, 'task_id': None, 'attempt_id': None})
        state = runtime.load_run(world['project'], state['run_id'])
    view = resource_policy.native_view(state)
    assert view['by_producer']['root']['distinct_responses'] == 4
    assert view['by_producer']['root']['distinct_response_tokens'] == 37
    lane = view['by_producer']['root']['cumulative_lanes'][0]
    assert lane['epochs'] == 2 and lane['reset_debt'] is True
    assert lane['unknown_baseline'] is True and lane['known_delta']['total_tokens'] == 22
    assert view['aggregate_tree_usage'] is None


def test_usage_before_budget_reconciles_from_exact_journal_and_rejects_tampering(world, monkeypatch):
    from test_run_state import command
    import resource_policy
    runtime, state = _codex_owner(world, monkeypatch)
    root = world['actor']['native_payload']['session_id']
    _append_path(world['transcript'], _usage_row(root, root, 'before-budget', 11))
    state = command(runtime, world, state, 'native.observe', {'source_handle': 'root', 'through_event': None,
        'task_id': None, 'attempt_id': None})
    ids = [row['event_id'] for row in state['extensions']['native_observations']['latest_batch']['events'] if row['kind'] == 'usage.snapshot']
    state = _owner_budget(runtime, world, state)
    assert resource_policy.native_view(state)['by_producer']['root']['distinct_response_tokens'] is None
    state = command(runtime, world, state, 'workflow.resource_observe', {'event_ids': ids})
    assert resource_policy.native_view(state)['by_producer']['root']['distinct_response_tokens'] == 11
    state = command(runtime, world, state, 'workflow.resource_observe', {'event_ids': ids})
    assert resource_policy.native_view(state)['by_producer']['root']['distinct_response_tokens'] == 11
    old = world['transcript'].read_bytes()
    world['transcript'].write_bytes(old.replace(b'before-budget', b'forged-budget'))
    with pytest.raises(ValueError):
        command(runtime, world, state, 'workflow.resource_observe', {'event_ids': ids})
    assert runtime.load_run(world['project'], state['run_id']) == state


def test_old_response_readback_is_projection_idempotent_after_later_counters(world, monkeypatch):
    from test_run_state import command
    runtime, state = _codex_owner(world, monkeypatch)
    state = _owner_budget(runtime, world, state)
    root = world['actor']['native_payload']['session_id']
    saved_ids = []
    for identity, count in [('one', 10), ('two', 20)]:
        _append_path(world['transcript'], _usage_row(root, root, identity, count))
        state = command(runtime, world, state, 'native.observe', {'source_handle': 'root',
            'through_event': None, 'task_id': None, 'attempt_id': None})
        if identity == 'one':
            saved_ids = [event['event_id'] for event in state['extensions']['native_observations']['latest_batch']['events']]
    budget = deepcopy(state['extensions']['workflow']['budget'])
    state = command(runtime, world, state, 'workflow.resource_observe', {'event_ids': saved_ids})
    assert state['extensions']['workflow']['budget'] == budget


def test_native_generation_rotation_keeps_measurement_identity_and_debt(world, monkeypatch):
    import native_observations
    import resource_policy
    from test_run_state import command
    runtime, state = _codex_owner(world, monkeypatch)
    state = _owner_budget(runtime, world, state)
    state = command(runtime, world, state, 'workflow.reserve', _reservation('interrupted', 100))
    state = command(runtime, world, state, 'workflow.settle', {'reservation_id': 'interrupted', 'actual': None})
    root = world['actor']['native_payload']['session_id']
    _append_path(world['transcript'], _usage_row(root, root, 'same', 12))
    state = command(runtime, world, state, 'native.observe', {'source_handle': 'root', 'through_event': None, 'task_id': None, 'attempt_id': None})
    old = deepcopy(state['extensions']['native_observations']['sources']['root'])
    path = world['transcript']
    retained = path.with_suffix('.old')
    path.rename(retained)
    path.write_bytes(retained.read_bytes())
    # An explicit source interval can acknowledge unknown history, not erase it.
    state = command(runtime, world, state, 'native.reconcile', {'source_handle': 'root', 'reconciliation': {
        'prior_generation': old['binding']['generation'], 'prior_cursor_digest': native_observations._digest(old['cursor']),
        'new_generation': None, 'mode': 'interval', 'start_offset': 0}})
    state = command(runtime, world, state, 'native.observe', {'source_handle': 'root', 'through_event': None, 'task_id': None, 'attempt_id': None})
    view = resource_policy.summary(state)
    assert view['native']['by_producer']['root']['distinct_response_tokens'] == 12
    assert len(view['native']['by_producer']['root']['cumulative_lanes']) == 2
    assert view['limits']['model_tokens']['committed'] == 100
    assert view['limits']['model_tokens']['spent'] is None
    assert view['native']['aggregate_tree_usage'] is None


def test_native_projection_capacity_fails_before_advancing_source(world, monkeypatch):
    import resource_policy
    from test_run_state import command
    runtime, state = _codex_owner(world, monkeypatch)
    state = _owner_budget(runtime, world, state)
    root = world['actor']['native_payload']['session_id']
    _append_path(world['transcript'], _usage_row(root, root, 'one', 10), _usage_row(root, root, 'two', 20))
    monkeypatch.setattr(resource_policy, 'MAX_MEASUREMENTS', 1)
    with pytest.raises(ValueError, match='capacity'):
        command(runtime, world, state, 'native.observe', {'source_handle': 'root', 'through_event': None, 'task_id': None, 'attempt_id': None})
    assert runtime.load_run(world['project'], state['run_id']) == state


def test_budget_cannot_relabel_native_tokens_as_currency(wf, state, context):
    from test_workflow import configured
    current = configured(wf, state, context)
    with pytest.raises(ValueError, match='token resource'):
        call(wf, current, context, 'budget', limits={'usd_micros': {'limit': 100, 'enforcement': 'forecast'}},
            deadline='2026-01-02T00:00:00Z', native_token_resource='usd_micros')


def test_operator_effort_report_is_current_bound_optional_and_not_measured(facade, world):
    from test_run_state import command
    from test_workflow import _owner_register
    import autopilot
    state = state_of(world, invoke(facade, world, start_request(world)))
    report = {'schema_version': 1, 'id': 'operator-one', 'kind': 'operator_reported_human_effort',
        'run_id': state['run_id'], 'start_revision': 0, 'end_revision': state['revision'],
        'metrics': {'active_review_minutes': 2.5, 'avoidable_questions': 0}}
    state = _owner_register(autopilot.engine(), world, state, 'human-report', report)
    response = invoke(facade, world, request('record', {'kind': 'human_effort', 'artifact_id': 'human-report'}, state, 'human'))
    assert response['status'] == 'RECORDED', response
    final = state_of(world, response)
    view = response['coverage']['resources']
    assert view['human_effort']['active_review_minutes'] is None
    assert view['human_effort_reporting']['known_reported']['active_review_minutes'] == 2.5
    assert view['human_effort_reporting']['known_reported']['avoidable_questions'] == 0
    assert view['human_effort_reporting']['known_reported']['interruptions'] is None
    assert view['human_effort_reporting']['reports']['operator-one']['source_current'] is True
    duplicate = invoke(facade, world, request('record', {'kind': 'human_effort', 'artifact_id': 'human-report'}, final, 'human-again'))
    assert duplicate['status'] == 'RECORDED'
    assert duplicate['coverage']['resources']['human_effort_reporting']['known_reported']['active_review_minutes'] == 2.5
    path = world['project']/'human-report.json'
    path.write_text(path.read_text().replace('2.5', '9.5'))
    current = state_of(world, duplicate)
    refused = invoke(facade, world, request('record', {'kind': 'human_effort', 'artifact_id': 'human-report'}, current, 'human-forged'))
    assert refused['status'] == 'UNRESOLVED'
    assert state_of(world, refused) == current


@pytest.mark.parametrize('fault', ['foreign_run', 'measured_claim', 'overlap', 'future_interval', 'negative', 'boolean'])
def test_effort_report_cannot_invent_measurement_or_double_count(facade, world, fault):
    from test_workflow import _owner_register
    import autopilot
    state = state_of(world, invoke(facade, world, start_request(world)))
    report = {'schema_version': 1, 'id': 'operator', 'kind': 'operator_reported_human_effort',
        'run_id': state['run_id'], 'start_revision': 0, 'end_revision': state['revision'], 'metrics': {'interruptions': 1}}
    if fault == 'overlap':
        state = _owner_register(autopilot.engine(), world, state, 'earlier-report', report)
        response = invoke(facade, world, request('record', {'kind': 'human_effort', 'artifact_id': 'earlier-report'}, state, 'earlier'))
        assert response['status'] == 'RECORDED', response
        state = state_of(world, response)
        report['id'] = 'overlap'
    if fault == 'foreign_run': report['run_id'] = 'foreign'
    if fault == 'measured_claim': report['kind'] = 'measured_human_effort'
    if fault == 'future_interval': report['end_revision'] = 10000
    if fault == 'negative': report['metrics']['interruptions'] = -1
    if fault == 'boolean': report['metrics']['interruptions'] = True
    state = _owner_register(autopilot.engine(), world, state, 'bad-report', report)
    response = invoke(facade, world, request('record', {'kind': 'human_effort', 'artifact_id': 'bad-report'}, state, 'bad-effort'))
    assert response['status'] == 'UNRESOLVED'
    assert state_of(world, response) == state


def test_exact_native_transport_alias_is_not_another_response(world, monkeypatch):
    import resource_policy
    from test_run_state import command
    runtime, state = _codex_owner(world, monkeypatch)
    state = _owner_budget(runtime, world, state)
    root = world['actor']['native_payload']['session_id']
    _append_path(world['transcript'], _usage_row(root, root, 'shared-response', 18))
    state = command(runtime, world, state, 'native.observe', {'source_handle': 'root', 'through_event': None, 'task_id': None, 'attempt_id': None})
    batch = deepcopy(state['extensions']['native_observations']['latest_batch'])
    # Pure reducer boundary fixture: the transport alias is already normalized;
    # production callers must pass through the native owner before this join.
    batch['events'][0]['event_id'] = 'sha256:'+'a'*64
    batch['events'][0]['native']['source_handle'] = 'transport-alias'
    resource_policy.ingest_native(state, 'transport-alias', batch)
    usage = state['extensions']['workflow']['budget']['native_usage']
    assert len(usage['measurements']) == 1 and usage['conflicts'] == {}
    measured = next(iter(usage['measurements'].values()))
    assert measured['tokens'] == 18 and len(measured['observations']) == 2
    assert {row['source_handle'] for row in measured['observations']} == {'root', 'transport-alias'}


def test_human_effort_report_has_a_bounded_source_read(facade, world):
    from test_run_state import command
    import autopilot
    state = state_of(world, invoke(facade, world, start_request(world)))
    report = {'schema_version': 1, 'id': 'too-large', 'kind': 'operator_reported_human_effort',
        'run_id': state['run_id'], 'start_revision': 0, 'end_revision': state['revision'], 'metrics': {'interruptions': 1}}
    path = world['project']/'large-effort.json'
    path.write_text(json.dumps(report)+' '*(128*1024))
    state = command(autopilot.engine(), world, state, 'artifact.register', {'id': 'large-effort', 'path': str(path),
        'role': 'input', 'required': False, 'retention': 'durable'})
    response = invoke(facade, world, request('record', {'kind': 'human_effort', 'artifact_id': 'large-effort'}, state, 'oversized'))
    assert response['status'] == 'UNRESOLVED'
    assert state_of(world, response) == state


def test_explicit_stable_preference_survives_core_reconfiguration(wf, state, context):
    from test_workflow import graphed, dimensions
    from resource_policy import select_policy
    current = graphed(wf, state, context)
    current['extensions']['workflow']['execution_policy'] = select_policy(current, {'mode': 'stable', 'shape': 'investigate_deliver'})
    current['contract_digest'] = 'c'*64
    current['profile_digest'] = 'd'*64
    rebound = call(wf, current, context, 'configure', dimensions=dimensions(), reason='Accepted core contract amendment')
    with pytest.raises(ValueError, match='immutable'):
        select_policy(rebound, {'mode': 'adaptive'})
    assert select_policy(rebound)['shape'] == 'investigate_deliver'


def declared(value, reason='Synthetic admitted classification'):
    return {'value': value, 'provenance': {'kind': 'admitted_request', 'reason': reason}, 'confidence': 'high'}


@pytest.mark.parametrize('size,duration,uncertainty,shape', [
    ('large', 'long', 'low', 'durable_program'),
    ('small', 'short', 'high', 'investigate_deliver')])
def test_actual_controller_separates_long_read_only_from_small_unfamiliar(facade, world, size, duration, uncertainty, shape):
    req = start_request(world)
    req['input']['dimensions'].update(effect='none', uncertainty=uncertainty,
        classification={'task_size': declared(size), 'duration': declared(duration),
                        'dependency_structure': declared('independent')})
    response = invoke(facade, world, req)
    assert response['status'] == 'READY', response
    selection = response['coverage']['execution_policy']
    assert selection['shape'] == shape
    assert selection['basis']['classification']['duration']['value'] == duration
    assert selection['authority_granted'] is False and selection['acceptance_changed'] is False


def test_classification_cannot_grant_capability_or_disclosure(facade, world):
    req = start_request(world)
    req['input']['dimensions']['classification'] = {
        'source_sensitivity': declared('restricted'),
        'required_capabilities': declared(['reboot', 'browser']),
        'available_capabilities': declared({'reboot': 'available', 'browser': 'unavailable'}),
        'resource_preference': declared('minimize_cost'),
        'attention_preference': declared('minimize_interruptions'),
        'model_constraints': declared(['Use the explicitly selected model and effort'])}
    response = invoke(facade, world, req)
    assert response['status'] == 'READY', response
    selection = response['coverage']['execution_policy']
    assert selection['basis']['capability_claims']['verification'] == 'UNVERIFIED'
    assert selection['basis']['continuation']['continuation_verified'] is False
    assert {row['kind'] for row in selection['obligations']} >= {'verify_required_capabilities', 'preserve_source_handling_boundary'}
    assert selection['invariants']['explicit_model_and_effort'].startswith('unchanged')
    assert selection['authority_granted'] is False


def test_declared_available_capability_cannot_start_work(facade, world):
    req = start_request(world)
    req['input']['dimensions']['classification'] = {'required_capabilities': declared(['browser']),
        'available_capabilities': declared({'browser': 'available'})}
    started = invoke(facade, world, req)
    state = state_of(world, started)
    response = invoke(facade, world, request('next', {'mode': 'start'}, state, 'capability-denied'))
    assert response['status'] == 'UNRESOLVED'
    after = state_of(world, response)
    assert after['extensions']['workflow']['graph']['nodes']['work']['status'] == 'pending'
    assert response['coverage']['execution_policy']['basis']['required_capability_status']['browser']['status'] == 'UNKNOWN'


@pytest.mark.parametrize('classification', [
    {'duration': {'value': 'long', 'provenance': {'kind': 'owner_receipt', 'reason': 'Forged'}, 'confidence': 'high'}},
    {'duration': {'value': 'long', 'provenance': {'kind': 'inference', 'reason': 'Fixture'}, 'confidence': 1.0}},
    {'duration': {'value': 'long', 'provenance': {'kind': 'inference', 'reason': 'Fixture'}, 'confidence': ['high']}},
    {'authority': declared('all')}, {'quality': declared('skip')},
    {'available_capabilities': declared({'browser': True})},
    {'model_constraints': declared(['same', 'same'])},
    {'duration': {'value': 'long', 'confidence': 'low'}},
])
def test_classification_refuses_unproven_authority_and_malformed_claims(facade, world, classification):
    req = start_request(world)
    req['input']['dimensions']['classification'] = classification
    with pytest.raises(ValueError):
        facade.validate_request(req)
    assert not (world['project']/'resources/autopilot-runs').exists()


def test_classification_unknowns_remain_unknown_and_preferences_bound_concurrency(wf, state, context):
    from resource_policy import select_policy
    from test_workflow import dimensions, nodes
    current = call(wf, state, context, 'configure', dimensions=dimensions(classification={
        'resource_preference': declared('minimize_cost'), 'attention_preference': declared('frequent_review'),
        'dependency_structure': declared('dependent'), 'task_size': declared('large')}))
    current = call(wf, current, context, 'graph', nodes=nodes(), wip_limit=2)
    chosen = select_policy(current)
    assert chosen['shape'] == 'investigate_deliver'
    assert chosen['preferences']['wip_limit'] == 1
    assert chosen['preferences']['checkpoint'] == 'task_and_consequential_boundaries'
    assert chosen['basis']['classification']['duration']['value'] is None
    assert chosen['basis']['classification']['duration']['confidence'] == 'unknown'
    assert chosen['basis']['capability_claims']['verification'] == 'UNVERIFIED'


def _normalized_bound_event(identity, amount, offset, *, thread='root', mode='synthetic', cumulative=False, grammar='fixture'):
    """Already admitted reducer input; does not claim native source custody."""
    return {'kind': 'usage.snapshot', 'event_id': identity, 'mode': mode,
        'producer': {'client': 'codex', 'root_session_id': 'root', 'thread_id': thread, 'parent_thread_id': None},
        'native': {'generation': 'one', 'offset': offset, 'length': 10, 'sha256': 'a' * 64},
        'data': {'measurement_id': ['codex', thread, identity], 'countable': not cumulative,
            'aggregation': 'cumulative_snapshot' if cumulative else 'per_response',
            'last': None if cumulative else {'total_tokens': amount},
            'totals': {'total_tokens': amount} if cumulative else None,
            'counters_digest': identity, 'scope': {'client': 'codex', 'root_session_id': 'root', 'thread_id': thread},
            'grammar': grammar, 'phase': 'final', 'missingness': []}}


def _bound_state(limit=10):
    return {'extensions': {'workflow': {'budget': {'limits': {'model_tokens': {'limit': limit, 'enforcement': 'hard'}},
        'native_token_resource': 'model_tokens'}}}}


@pytest.mark.parametrize('second_handle', ['root', 'alias-of-root'])
def test_native_producer_lower_bound_ignores_capture_handle_partition(second_handle):
    import resource_policy as policy
    value = _bound_state()
    policy.ingest_native(value, 'root', {'events': [_normalized_bound_event('first', 6, 100)]})
    policy.ingest_native(value, second_handle, {'events': [_normalized_bound_event('second', 6, 200)]})
    with pytest.raises(ValueError, match='lower bound'):
        policy.require_native_headroom(value['extensions']['workflow'])
    assert policy.native_view(value)['aggregate_tree_usage'] is None


@pytest.mark.parametrize('distinction', ['alias', 'thread', 'mode', 'cumulative', 'cumulative-grammar'])
def test_lower_bound_never_adds_overlapping_alternative_scopes(distinction):
    import resource_policy as policy
    value = _bound_state()
    first = _normalized_bound_event('first', 6, 100)
    if distinction == 'cumulative-grammar':
        first = _normalized_bound_event('base', 1, 100, cumulative=True)
        policy.ingest_native(value, 'root', {'events': [first, _normalized_bound_event('delta', 7, 200, cumulative=True)]})
        second = [_normalized_bound_event('other-base', 1, 100, cumulative=True, grammar='other'),
                  _normalized_bound_event('other-delta', 7, 200, cumulative=True, grammar='other')]
    else:
        policy.ingest_native(value, 'root', {'events': [first]})
        if distinction == 'alias':
            duplicate = deepcopy(first); duplicate['event_id'] = 'capture-alias'; duplicate['native']['offset'] = 300
            second = [duplicate]
        elif distinction == 'thread':
            second = [_normalized_bound_event('second', 6, 200, thread='separate-child')]
        elif distinction == 'mode':
            second = [_normalized_bound_event('second', 6, 200, mode='native')]
        else:
            second = [_normalized_bound_event('base', 1, 100, cumulative=True),
                      _normalized_bound_event('delta', 7, 200, cumulative=True)]
    policy.ingest_native(value, 'another-capture', {'events': second})
    policy.require_native_headroom(value['extensions']['workflow'])
    assert policy.native_view(value)['billable_cost'] is None


@pytest.mark.parametrize('kind', [[], {}, 1, True, None])
def test_controller_malformed_classification_is_a_typed_refusal(facade, world, kind):
    req = start_request(world)
    req['input']['dimensions']['classification'] = {'duration': {'value': 'long',
        'provenance': {'kind': kind, 'reason': 'Malformed independent boundary case'}, 'confidence': 'high'}}
    before = sorted(world['project'].rglob('events.jsonl'))
    with pytest.raises(ValueError, match='provenance'):
        invoke(facade, world, req)
    assert sorted(world['project'].rglob('events.jsonl')) == before


def test_actual_cumulative_delta_blocks_work_after_journal_reload(world, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from test_run_state import command
    import resource_policy as policy
    runtime, current = _codex_owner(world, monkeypatch)
    current = command(runtime, world, current, 'workflow.budget', {
        'limits': {'model_tokens': {'limit': 10, 'enforcement': 'hard'}},
        'deadline': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()})
    for total in [5, 17]:
        counters = {'input_tokens': total - 2, 'output_tokens': 2, 'total_tokens': total}
        row = {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {
            'total_token_usage': counters, 'last_token_usage': counters}}}
        _append_path(world['transcript'], row)
        current = command(runtime, world, current, 'native.observe', {'source_handle': 'root',
            'through_event': None, 'task_id': None, 'attempt_id': None})
        current = runtime.load_run(world['project'], current['run_id'])
    view = policy.native_view(current)
    assert view['known_response_counter_sum'] is None
    lane = view['by_producer']['root']['cumulative_lanes'][0]
    assert lane['unknown_baseline'] is True and lane['known_delta']['total_tokens'] == 12
    before = deepcopy(current)
    with pytest.raises(ValueError, match='lower bound'):
        command(runtime, world, current, 'workflow.task', {'task_id': 'work', 'action': 'start'})
    assert runtime.load_run(world['project'], current['run_id']) == before
    # Read-only reconciliation reuses the real retained source and cannot reset
    # the admission lower bound or invent a paid-usage total.
    ids = [event['event_id'] for event in current['extensions']['native_observations']['latest_batch']['events']]
    current = command(runtime, world, current, 'workflow.resource_observe', {'event_ids': ids})
    with pytest.raises(ValueError, match='lower bound'):
        command(runtime, world, current, 'workflow.task', {'task_id': 'work', 'action': 'start'})
    old = world['transcript'].read_text()
    world['transcript'].write_text(old.replace('"total_tokens": 17', '"total_tokens": 18'))
    with pytest.raises(ValueError):
        command(runtime, world, current, 'workflow.resource_observe', {'event_ids': ids})
    assert runtime.load_run(world['project'], current['run_id']) == current


def test_reconfigured_workflow_keeps_retained_tree_topology(wf, state, context):
    from resource_policy import native_view
    from test_workflow import configured, dimensions
    current = configured(wf, state, context)
    flow = current['extensions']['workflow']
    flow['children'] = {ident: {'child_id': ident, 'mode': 'artifact-only',
        'disposition': 'complete', 'audit_status': 'accepted', 'reservation_id': reserve,
        'parent_child_id': parent} for ident, parent, reserve in [
        ('/root/worker', None, 'work'), ('/root/worker/leaf', '/root/worker', 'leaf')]}
    current['contract_digest'] = 'e'*64
    rebound = call(wf, current, context, 'configure', dimensions=dimensions(), reason='Accepted amended outcome')
    view = native_view(rebound)
    assert view['by_producer']['child:/root/worker/leaf']['parent'] == 'child:/root/worker'
    assert view['by_producer']['child:/root/worker/leaf']['reservation_id'] == 'leaf'
    assert view['by_producer']['child:/root/worker/leaf']['complete_usage'] is None


def test_reconfiguration_cannot_reuse_prior_child_identity(wf, state, context):
    current, context, payload = dispatch_ready(wf, state, context)
    current['extensions']['workflow']['retained_children'] = [{'child_id': payload['child_id']}]
    with pytest.raises(ValueError, match='retained execution tree'):
        call(wf, current, context, 'dispatch', **payload)
