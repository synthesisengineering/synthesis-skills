"""Journal/CAS/source causal tests, using only synthetic actual native files."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from test_run_state import engine, world, create, command  # noqa: F401
from test_controller import facade  # noqa: F401


@pytest.fixture
def bridge(engine):
    module = importlib.import_module('observation_bridge')
    module.register(engine)
    return module


def enroll(engine, world, state):
    return command(engine, world, state, 'native.enroll', {'source_handle': 'root', 'mode': 'synthetic'})


def append(world, *rows):
    with world['transcript'].open('a') as stream:
        for row in rows:
            stream.write(json.dumps(row, separators=(',', ':')) + '\n')


def pair(world, identity='call', output='actual synthetic result'):
    session = world['actor']['native_payload']['session_id']
    return [
        {'type': 'assistant', 'sessionId': session, 'message': {'role': 'assistant', 'content': [
            {'type': 'tool_use', 'id': identity, 'name': 'Read', 'input': {'file_path': 'fixture.txt'}}]}},
        {'type': 'user', 'sessionId': session, 'message': {'role': 'user', 'content': [
            {'type': 'tool_result', 'tool_use_id': identity, 'content': output, 'is_error': False}]}}
    ]


def observe(engine, world, state, **kwargs):
    return command(engine, world, state, 'native.observe', {'source_handle': 'root',
        'through_event': None, 'task_id': None, 'attempt_id': None}, **kwargs)


@pytest.mark.parametrize('kind', [None, 'turn_aborted', 'user_message'])
@pytest.mark.parametrize('position', ['before', 'after'])
def test_owner_journal_large_codex_item_preserves_current_invalidations(bridge, engine, facade, world, monkeypatch, kind, position):
    from test_native_observations import completed_item
    from test_controller import invoke, request, start_request, state_of
    native = world['actor']['native_payload']['session_id']
    home = world['scratch'] / 'fixture-codex'
    directory = home / 'sessions/2026/09/25'; directory.mkdir(parents=True)
    transcript = directory / ('rollout-' + native + '.jsonl')
    transcript.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': native,
        'cwd': str(world['repo'])}}) + '\n')
    world['transcript'] = transcript
    world['actor']['native_payload']['transcript_path'] = str(transcript)
    world['board'].write_text(world['board'].read_text().replace('| claude |', '| codex |').replace('cc:' + native, 'codex:' + native))
    monkeypatch.setenv('CODEX_HOME', str(home))
    monkeypatch.setenv('SYNTHESIS_CLIENT_SESSION_REF', 'codex:' + native)
    started = invoke(facade, world, start_request(world))
    assert started['status'] == 'READY', started
    state = state_of(world, started)
    rows = [completed_item(thread=native)]
    if kind:
        change = {'type': 'event_msg', 'payload': {'type': kind, 'turn_id': 'turn', 'message': 'Pause this task'}}
        rows.insert(0 if position == 'before' else 1, change)
    for ordinal, row in enumerate(rows, 1): row['ordinal'] = ordinal
    append(world, *rows)
    pending = bridge.current_invalidation(engine.inspect_context(state, world['actor']))
    assert pending['status'] == ('invalidated' if kind else 'clear'), pending
    recorded = invoke(facade, world, request('record', {'kind': 'native', 'source_handle': 'root',
        'through_event': None, 'task_id': None, 'attempt_id': None}, state, 'large-record'))
    assert recorded['status'] == 'RECORDED', recorded
    state = state_of(world, recorded)
    source = state['extensions']['native_observations']
    assert not source['latest_batch']['gaps'] and not source['latest_batch']['diagnostics']
    assert len([e for e in source['latest_batch']['events'] if e['kind'] == 'item.observation']) == 1
    current = bridge.current_invalidation(engine.inspect_context(state, world['actor']))
    assert current['status'] == ('invalidated' if kind else 'clear'), current
    assert engine.load_run(world['project'], state['run_id']) == state
    assert state['status'] != 'completed' and not source['projection']['pairs']


def test_current_invalidation_requires_enrollment_and_rechecks_source_bytes(bridge, engine, world):
    state = create(engine, world)
    assert bridge.current_invalidation(engine.inspect_context(state, world['actor']))['status'] == 'unknown'
    state = enroll(engine, world, state)
    assert bridge.current_invalidation(engine.inspect_context(state, world['actor']))['status'] == 'clear'
    session = world['actor']['native_payload']['session_id']
    append(world, {'type': 'user', 'uuid': 'cancel-message', 'sessionId': session,
        'message': {'role': 'user', 'content': 'Pause this task.'}})
    assert bridge.current_invalidation(engine.inspect_context(state, world['actor']))['status'] == 'invalidated'
    state = observe(engine, world, state)
    assert bridge.current_invalidation(engine.inspect_context(state, world['actor']))['status'] == 'invalidated'
    old = world['transcript'].read_bytes()
    world['transcript'].write_bytes(old.replace(b'Pause this task.', b'Other fake text.'))
    assert bridge.current_invalidation(engine.inspect_context(state, world['actor']))['status'] == 'unknown'
    assert engine.load_run(world['project'], state['run_id']) == state


@pytest.mark.parametrize('fault', [None, 'receipt', 'frontier', 'prior-ids', 'source-tamper'])
def test_native_resume_window_requires_exact_current_user_clearance(bridge, engine, world, fault):
    import autopilot
    import hashlib
    import native_observations
    from test_workflow import _owner_native_authorization
    runtime = autopilot.engine()
    state = enroll(runtime, world, create(runtime, world))
    session = world['actor']['native_payload']['session_id']
    append(world, {'type': 'user', 'uuid': 'pause-message', 'sessionId': session,
        'message': {'role': 'user', 'content': 'Pause the earlier instruction.'}})
    state = observe(runtime, world, state)
    prior = bridge.current_invalidation(runtime.inspect_context(state, world['actor']))
    assert prior['status'] == 'invalidated'
    ids = sorted(row['event_id'] for row in prior['invalidations'])
    old = deepcopy(state['extensions']['native_observations']['sources']['root'])
    offset = world['transcript'].stat().st_size
    declaration = {'operation': 'resume', 'source_handle': 'root',
        'prior_generation': old['binding']['generation'], 'prior_cursor_digest': native_observations._digest(old['cursor']),
        'prior_invalidation_ids': ids, 'prior_interval': 'acknowledged_unknown', 'resume_message_id': 'resume-message'}
    state = _owner_native_authorization(runtime, world, state, 'resume-message', 'retry_clearance',
        {'approved': True, 'changed_condition': 'Resume the admitted task after the retained pause.',
         'native_invalidation_resolution': declaration})
    raw = world['transcript'].read_bytes()[offset:]
    spec = {**{key: declaration[key] for key in ('prior_generation', 'prior_cursor_digest')},
        'new_generation': None, 'mode': 'interval', 'start_offset': offset + len(raw),
        'invalidation_resolution': {'receipt_id': 'resume-message', 'prior_invalidation_ids': ids,
            'resume_locator': {'generation': old['binding']['generation'], 'offset': offset,
                'length': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}}}
    if fault == 'receipt': spec['invalidation_resolution']['receipt_id'] = 'invented'
    if fault == 'frontier': spec['start_offset'] -= 1
    if fault == 'prior-ids': spec['invalidation_resolution']['prior_invalidation_ids'] = []
    if fault in {'receipt', 'frontier', 'prior-ids'}:
        with pytest.raises(ValueError):
            command(runtime, world, state, 'native.reconcile', {'source_handle': 'root', 'reconciliation': spec})
        assert runtime.load_run(world['project'], state['run_id']) == state
        return
    resumed = command(runtime, world, state, 'native.reconcile', {'source_handle': 'root', 'reconciliation': spec})
    checked = bridge.current_invalidation(runtime.inspect_context(resumed, world['actor']))
    assert checked['status'] == 'clear', checked
    assert checked['acknowledged_prior_interval']['coverage'] == 'UNKNOWN'
    assert resumed['extensions']['native_observations']['sources']['root']['history']
    if fault == 'source-tamper':
        world['transcript'].write_bytes(world['transcript'].read_bytes().replace(b'Resume the admitted', b'Revoke the admitted'))
        assert bridge.current_invalidation(runtime.inspect_context(resumed, world['actor']))['status'] == 'unknown'
    else:
        append(world, {'type': 'user', 'uuid': 'new-pause', 'sessionId': session,
            'message': {'role': 'user', 'content': 'Pause again.'}})
        assert bridge.current_invalidation(runtime.inspect_context(resumed, world['actor']))['status'] == 'invalidated'


@pytest.mark.parametrize('cancelled', [False, True])
def test_large_benign_history_catches_up_without_losing_known_invalidation(bridge, engine, world, cancelled):
    state = enroll(engine, world, create(engine, world))
    session = world['actor']['native_payload']['session_id']
    if cancelled:
        append(world, {'type': 'user', 'uuid': 'retained-pause', 'sessionId': session,
            'message': {'role': 'user', 'content': 'Pause the earlier task.'}})
        state = observe(engine, world, state)
    for index in range(25):
        append(world, {'type': 'assistant', 'sessionId': session, 'message': {'role': 'assistant',
            'content': [{'type': 'text', 'text': 'x' * 50000}]}})
    assert bridge.current_invalidation(engine.inspect_context(state, world['actor']))['status'] == 'unknown'
    pages = 0
    while True:
        state = observe(engine, world, state)
        pages += 1
        source = state['extensions']['native_observations']['sources']['root']
        if not source['coverage']['backlog_bytes']:
            break
        assert pages < 4
    assert pages >= 2
    result = bridge.current_invalidation(engine.inspect_context(state, world['actor']))
    assert result['status'] == ('invalidated' if cancelled else 'clear'), result
    assert result['historical_negative_coverage'] == 'UNKNOWN'
    assert sum(row['bytes_read'] for row in result['coverage']) < 2048


def test_enrollment_frontier_precedes_only_new_observed_work(bridge, engine, world):
    append(world, *pair(world, 'before'))
    prior_extent = world['transcript'].stat().st_size
    state = enroll(engine, world, create(engine, world))
    source = state['extensions']['native_observations']['sources']['root']
    assert source['cursor']['enrolled_from'] == prior_extent
    assert source['binding']['mode'] == 'synthetic'
    append(world, *pair(world, 'after'))
    state = observe(engine, world, state)
    batch = state['extensions']['native_observations']['latest_batch']
    assert {event['native']['call_id'] for event in batch['events']} == {'after'}
    assert 'work before enrollment' in batch['coverage']['unobservable']
    assert all(event['authentication'] == 'owner_admission_required' for event in batch['events'])


def test_batch_and_cursor_commit_together_across_interruption(bridge, engine, world, monkeypatch):
    state = enroll(engine, world, create(engine, world))
    append(world, *pair(world))
    before = deepcopy(state)
    original = engine._append
    def fail_append(*args, **kwargs):
        raise OSError('synthetic before append')
    monkeypatch.setattr(engine, '_append', fail_append)
    with pytest.raises(OSError):
        observe(engine, world, state, command_id='batch-once')
    assert engine.load_run(world['project'], state['run_id']) == before
    monkeypatch.setattr(engine, '_append', original)
    state = observe(engine, world, state, command_id='batch-once')
    assert state['extensions']['native_observations']['latest_batch']['events']
    replay = observe(engine, world, before, command_id='batch-once')
    assert replay == state


def test_current_projection_is_not_cursor_authority(bridge, engine, world):
    state = enroll(engine, world, create(engine, world))
    fake = deepcopy(state)
    fake['extensions']['native_observations']['sources']['root']['cursor']['offset'] = 9999999
    path = engine._home(world['project'], state['run_id']) / 'current.json'
    path.write_text(json.dumps(fake))
    append(world, *pair(world))
    actual = observe(engine, world, state)
    batch = actual['extensions']['native_observations']['latest_batch']
    assert len(batch['events']) == 2
    assert batch['coverage']['backlog_bytes'] == 0


@pytest.mark.parametrize('change', ['rotation', 'truncation'])
def test_source_generation_change_never_silently_advances_cursor(bridge, engine, world, change):
    state = enroll(engine, world, create(engine, world))
    append(world, *pair(world))
    state = observe(engine, world, state)
    cursor = deepcopy(state['extensions']['native_observations']['sources']['root']['cursor'])
    path = world['transcript']
    raw = path.read_bytes()
    if change == 'rotation':
        path.rename(path.with_suffix('.retained'))
        path.write_bytes(raw)
    else:
        path.write_bytes(raw.splitlines(keepends=True)[0])
    result = observe(engine, world, state)
    extension = result['extensions']['native_observations']
    assert extension['sources']['root']['cursor'] == cursor
    assert extension['latest_batch']['diagnostics']


def test_event_consumption_reopens_same_size_source_bytes(bridge, engine, world):
    from run_admission import admission_scope
    state = enroll(engine, world, create(engine, world))
    append(world, *pair(world, output='original'))
    state = observe(engine, world, state)
    events = state['extensions']['native_observations']['latest_batch']['events']
    ids = [event['event_id'] for event in events]
    def consume():
        proof = engine._binding(world['project'], state, world['actor'], readonly=True)
        with admission_scope(proof, world['actor'], world['project']) as token:
            return bridge.current_events({'project': world['project'], 'state': state, 'actor': world['actor'],
                'binding': proof, 'admission_observation': token}, ids)
    assert consume()['status'] == 'current'
    path = world['transcript']
    raw = path.read_bytes()
    path.write_bytes(raw.replace(b'original', b'tampered'))
    assert path.stat().st_size == len(raw)
    assert consume()['status'] == 'invalid'


def test_forged_admission_boolean_cannot_consume(bridge, engine, world):
    state = create(engine, world)
    with pytest.raises(ValueError):
        bridge.current_events({'project': world['project'], 'state': state, 'actor': world['actor'],
                               'binding': state['owner'], 'admission_observation': True}, [])


def test_idle_and_missed_notifications_use_one_incremental_cursor(bridge, engine, world):
    state = enroll(engine, world, create(engine, world))
    append(world, *pair(world, 'one'))
    state = observe(engine, world, state)
    count = len(state['extensions']['native_observations']['event_index'])
    idle = observe(engine, world, state)
    assert idle['extensions']['native_observations']['latest_batch']['bytes_read'] == 0
    assert len(idle['extensions']['native_observations']['event_index']) == count
    append(world, *pair(world, 'missed'))
    caught_up = observe(engine, world, idle)
    assert len(caught_up['extensions']['native_observations']['event_index']) == count + 2


@pytest.mark.parametrize('passive', [False, True])
def test_native_readback_reacquires_admission_and_rejects_changed_head(bridge, engine, world, passive):
    from test_run_admission import write_board
    state = enroll(engine, world, create(engine, world))
    append(world, *pair(world))
    state = observe(engine, world, state)
    ids = [event['event_id'] for event in state['extensions']['native_observations']['latest_batch']['events']]
    context = (engine.inspect_owned_runs(world['actor'], runtime_root=world['runtime'])[0][1]
               if passive else engine.inspect_context(state, world['actor'], project=world['project']))
    reader = context['current_native_events']
    assert callable(reader) and 'admission_observation' not in context
    assert reader(ids)['status'] == 'current'
    raw = world['transcript'].read_bytes()
    world['transcript'].write_bytes(raw.replace(b'actual synthetic result', b'changed synthetic bytes'))
    assert reader(ids)['status'] == 'invalid'
    world['transcript'].write_bytes(raw)
    write_board(world, status='released')
    with pytest.raises(ValueError):
        reader(ids)
    write_board(world)
    command(engine, world, state, 'progress', {'summary': 'Current state advanced'})
    with pytest.raises(ValueError, match='current authoritative|head changed'):
        reader(ids)


def test_child_enrollment_requires_actual_dispatch_and_revalidates_it_on_consumption(world, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from test_workflow import _native_process_fixture, _owner_register
    from test_native_codex import COUNTS
    runtime, state, _ = _native_process_fixture(world, monkeypatch)
    state = command(runtime, world, state, 'workflow.budget', {'limits': {'units': {'limit': 10, 'enforcement': 'hard'}},
        'deadline': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()})
    for identity, category, units in [('worker', 'work', 5), ('audit', 'integration', 1), ('verify', 'verification', 1), ('recover', 'recovery', 1)]:
        state = command(runtime, world, state, 'workflow.reserve', {'reservation_id': identity,
            'amounts': {'units': units}, 'category': category})
    root = world['project'] / 'delegated'
    for name in ('output', 'scratch'):
        (root / name).mkdir(parents=True)
    brief = {'child_id': '/root/worker', 'task_id': 'work', 'deliverables': ['Produce reviewed output'],
        'paths': [str(root)], 'criteria': ['accept'], 'reservation_id': 'worker', 'integration_reservation_id': 'audit', 'verification_reservation_id': 'verify', 'recovery_reservation_id': 'recover',
        'integration_owner': state['owner']['session_uuid'], 'return_contract': ['artifact_ids', 'evidence_ids', 'disposition'],
        'cancellation': 'Retain partial evidence and return', 'mode': 'artifact-only',
        'file_contract': {'schema_version': 1, 'immutable_inputs': [], 'output_roots': [str(root / 'output')],
                          'scratch_root': str(root / 'scratch')}}
    binding = {key: state[key] for key in ('run_id', 'contract_digest', 'profile_digest')}
    envelope = {'schema_version': 1, 'kind': 'delegation', 'bindings': binding, 'data': brief}
    append(world, {'type': 'response_item', 'payload': {'type': 'function_call', 'namespace': 'collaboration',
        'name': 'followup_task', 'call_id': 'dispatch-child', 'arguments': json.dumps({'target': '/root/worker',
            'message': json.dumps({'autopilot_delegation': envelope})})}},
        {'type': 'response_item', 'payload': {'type': 'function_call_output', 'call_id': 'dispatch-child', 'output': ''}})
    stamp = datetime.now(timezone.utc)
    state = _owner_register(runtime, world, state, 'dispatch-file', {'kind': 'delegation',
        'bindings': {**state['owner'], **binding}, 'observed_at': stamp.isoformat(),
        'expires_at': (stamp + timedelta(hours=1)).isoformat(),
        'data': {**brief, 'source': {'kind': 'native-dispatch', 'call_id': 'dispatch-child'}}}, role='evidence')
    state = command(runtime, world, state, 'evidence.record', {'id': 'dispatch-proof', 'kind': 'delegation', 'artifact_id': 'dispatch-file'})
    state = command(runtime, world, state, 'workflow.dispatch', {**brief, 'admission_id': 'parent',
        'dispatch_receipt_id': 'dispatch-proof', 'admission_requests': [{'id': 'parent', 'actor': world['actor'], 'paths': [str(root)]}]})
    native_root = world['actor']['native_payload']['session_id']
    child = '01990000-0000-7000-8000-000000000044'
    def token(thread):
        return {'type': 'token_usage_record', 'payload': {'thread_id': thread, 'session_id': native_root,
            'turn_id': 'turn', 'root_turn_id': 'root-turn', 'response_id': 'response-' + thread,
            'usage': COUNTS, 'turn_token_usage': COUNTS, 'thread_token_usage': COUNTS}}
    path = world['transcript'].parent / ('child-' + child + '.jsonl')
    path.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': child, 'session_id': native_root,
        'parent_thread_id': native_root, 'agent_path': '/root/worker'}}) + '\n' + json.dumps(token(child)) + '\n')
    append(world, token(native_root))
    state = observe(runtime, world, state)
    payload = {'source_handle': 'child:/root/worker', 'through_event': None, 'task_id': 'work', 'attempt_id': None}
    duplicate = path.with_name('ambiguous-child.jsonl')
    duplicate.write_bytes(path.read_bytes())
    with pytest.raises(ValueError, match='absent or ambiguous'):
        command(runtime, world, state, 'native.observe', payload)
    assert runtime.load_run(world['project'], state['run_id']) == state
    duplicate.unlink()
    state = command(runtime, world, state, 'native.observe', payload)
    extension = state['extensions']['native_observations']
    events = extension['latest_batch']['events']
    assert len(events) == 1 and events[0]['producer']['thread_id'] == child
    assert events[0]['producer']['root_session_id'] == native_root
    assert events[0]['data']['scope_nonoverlap'] == 'UNKNOWN'
    assert extension['sources']['root']['binding']['producer']['thread_id'] != child
    reader = runtime.inspect_context(state, world['actor'], project=world['project'])['current_native_events']
    assert reader([events[0]['event_id']])['status'] == 'current'
    with path.open('a') as stream:
        stream.write(json.dumps({'type': 'event_msg', 'payload': {'type': 'turn_aborted', 'turn_id': 'child-turn'}}) + '\n')
    import observation_bridge
    context = runtime.inspect_context(state, world['actor'], project=world['project'])
    assert observation_bridge.current_invalidation(context)['status'] == 'clear'
    child_status = observation_bridge.current_invalidation(context, source_handle='child:/root/worker')
    assert child_status['status'] == 'invalidated', child_status
    assert all(event['producer']['thread_id'] == child for event in child_status['invalidations'])
    raw = world['transcript'].read_bytes()
    world['transcript'].write_bytes(raw.replace(b'"name":"followup_task"', b'"name":"exec_command"'))
    with pytest.raises(ValueError, match='source-backed delegation'):
        reader([events[0]['event_id']])


def reconcile(engine, world, state, spec=None):
    payload = {'source_handle': 'root'}
    if spec is not None:
        payload['reconciliation'] = spec
    return command(engine, world, state, 'native.reconcile', payload)


def reconciliation_spec(source, mode='carry', **extra):
    import native_observations
    return {'prior_generation': source['binding']['generation'],
            'prior_cursor_digest': native_observations._digest(source['cursor']),
            'new_generation': source.get('recovery', {}).get('observed_generation'),
            'mode': mode, **extra}


def test_rotation_discovery_preserves_frontier_and_copy_carry_reads_current_ranges(bridge, engine, world):
    state = enroll(engine, world, create(engine, world))
    append(world, *pair(world))
    state = observe(engine, world, state)
    source = deepcopy(state['extensions']['native_observations']['sources']['root'])
    path = world['transcript']
    raw = path.read_bytes()
    path.rename(path.with_suffix('.retained'))
    path.write_bytes(raw)
    discovered = reconcile(engine, world, state)
    old = discovered['extensions']['native_observations']['sources']['root']
    assert old['cursor'] == source['cursor'] and old['history'] == []
    assert old['recovery']['status'] == 'binding_required'
    state = reconcile(engine, world, discovered, reconciliation_spec(old))
    carried = state['extensions']['native_observations']['sources']['root']
    assert carried['binding']['generation'] != source['binding']['generation']
    assert {k: v for k, v in carried['cursor'].items() if k != 'generation'} == {
        k: v for k, v in source['cursor'].items() if k != 'generation'}
    assert carried['history'][0]['cursor'] == source['cursor']
    assert carried['reconciliation']['continuity']['prior_positive_generation'] == 'not relabeled'
    append(world, *pair(world, 'after-rotation'))
    state = observe(engine, world, state)
    assert {row['native']['call_id'] for row in state['extensions']['native_observations']['latest_batch']['events']} == {'after-rotation'}


def test_copy_carry_refuses_same_size_tampering_then_explicit_interval_remains_unknown(bridge, engine, world):
    state = enroll(engine, world, create(engine, world))
    append(world, *pair(world, output='original'))
    state = observe(engine, world, state)
    original = deepcopy(state['extensions']['native_observations']['sources']['root'])
    path = world['transcript']
    raw = path.read_bytes()
    path.rename(path.with_suffix('.retained'))
    path.write_bytes(raw.replace(b'original', b'modified'))
    state = reconcile(engine, world, state)
    source = state['extensions']['native_observations']['sources']['root']
    with pytest.raises(ValueError, match='range differs'):
        reconcile(engine, world, state, reconciliation_spec(source))
    assert engine.load_run(world['project'], state['run_id']) == state
    state = reconcile(engine, world, state, reconciliation_spec(source, 'interval', start_offset=original['cursor']['offset']))
    source = state['extensions']['native_observations']['sources']['root']
    assert source['cursor']['enrolled_from'] == original['cursor']['offset']
    assert source['reconciliation']['continuity']['historical_interval'] == 'UNKNOWN'
    assert source['history'][0]['cursor'] == original['cursor']


def test_same_inode_truncation_gets_explicit_logical_generation(bridge, engine, world):
    state = enroll(engine, world, create(engine, world))
    append(world, *pair(world))
    state = observe(engine, world, state)
    original = deepcopy(state['extensions']['native_observations']['sources']['root'])
    raw = world['transcript'].read_bytes().splitlines(keepends=True)[0]
    world['transcript'].write_bytes(raw)
    state = reconcile(engine, world, state)
    source = state['extensions']['native_observations']['sources']['root']
    assert source['recovery']['observed_generation'] != original['binding']['generation']
    state = reconcile(engine, world, state, reconciliation_spec(source, 'interval', start_offset=len(raw)))
    source = state['extensions']['native_observations']['sources']['root']
    assert source['binding']['inode'] == original['binding']['inode']
    assert source['binding']['source_epoch']
    assert source['cursor']['offset'] == len(raw)
    assert source['history'][0]['cursor'] == original['cursor']


def test_explicit_interval_recovery_advances_multiple_bounded_pages_without_erasing_history(bridge, engine, world):
    state = enroll(engine, world, create(engine, world))
    append(world, *pair(world, 'retained-old'))
    state = observe(engine, world, state)
    old = deepcopy(state['extensions']['native_observations']['sources']['root'])
    old_ids = list(state['extensions']['native_observations']['event_index'])
    path = world['transcript']
    header = path.read_bytes().splitlines(keepends=True)[0]
    path.rename(path.with_suffix('.retained'))
    path.write_bytes(header)
    session = world['actor']['native_payload']['session_id']
    for _ in range(7):
        append(world, {'type': 'assistant', 'sessionId': session, 'message': {'role': 'assistant',
            'content': [{'type': 'text', 'text': 'x' * 200000}]}})
    append(world, *pair(world, 'new-generation'))
    state = reconcile(engine, world, state)
    source = state['extensions']['native_observations']['sources']['root']
    state = reconcile(engine, world, state, reconciliation_spec(source, 'interval', start_offset=len(header)))
    offsets, reads, total_reads = [], [], []
    for _ in range(4):
        state = observe(engine, world, state)
        batch = state['extensions']['native_observations']['latest_batch']
        offsets.append(batch['cursor']['offset'])
        reads.append(batch['source_bytes_read'])
        total_reads.append(batch['bytes_read'])
        if batch['coverage']['backlog_bytes'] == 0:
            break
    assert len(offsets) == 2 and offsets[0] < offsets[1] == path.stat().st_size
    assert max(reads) <= 1024 * 1024
    assert max(total_reads) <= 2 * (1024 * 1024 + 256 * 1024 + len(header))
    source = state['extensions']['native_observations']['sources']['root']
    assert source['history'][0]['cursor'] == old['cursor']
    assert source['reconciliation']['continuity']['historical_interval'] == 'UNKNOWN'
    assert all(identity in state['extensions']['native_observations']['event_index'] for identity in old_ids)
    reader = engine.inspect_context(state, world['actor'], project=world['project'])['current_native_events']
    assert reader(old_ids)['status'] == 'invalid'
    current_ids = [row['event_id'] for row in state['extensions']['native_observations']['latest_batch']['events']]
    assert reader(current_ids)['status'] == 'current'


def test_reconciliation_rejects_changed_frontier_and_mid_record_offset(bridge, engine, world):
    state = enroll(engine, world, create(engine, world))
    source = state['extensions']['native_observations']['sources']['root']
    spec = reconciliation_spec(source, 'interval', start_offset=1)
    with pytest.raises(ValueError, match='boundary'):
        reconcile(engine, world, state, spec)
    spec.update(start_offset=0, prior_cursor_digest='0' * 64)
    with pytest.raises(ValueError, match='prior frontier'):
        reconcile(engine, world, state, spec)
    assert engine.load_run(world['project'], state['run_id']) == state
