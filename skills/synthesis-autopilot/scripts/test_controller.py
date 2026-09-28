"""Fixture-first controller regressions. All PM/native data are synthetic."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib
import json
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parents[1] / 'synthesis-project-management/scripts'))
from test_run_admission import world as world  # noqa: E402
from test_run_state import engine as engine, contract  # noqa: E402

__all__ = ["engine", "world"]


@pytest.fixture
def facade(engine):
    module = importlib.import_module('controller')
    import autopilot
    autopilot.engine()
    return module


def request(operation, values, state=None, identity=None):
    value = {'schema_version': 1, 'request_id': identity or operation,
             'operation': operation, 'project_id': 'alpha', 'input': values}
    if state:
        value.update(run_id=state['run_id'], expected_revision=state['revision'])
    return value


def start_request(world, identity='start'):
    return request('start', {'plan_ref': str(world['plan']), 'outcome_contract': contract(),
        'dimensions': {'domains': ['software'], 'uncertainty': 'low', 'effect': 'local-reversible',
                       'horizon': 'session', 'parallelizable': False},
        'resource_envelope': {'limits': {'model_tokens': {'limit': 100000, 'enforcement': 'forecast'}},
                              'deadline': (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()},
        'graph': {'nodes': [{'id': 'work', 'deps': [], 'criteria': ['accept'], 'estimate': 1}],
                  'wip_limit': 1}}, identity=identity)


def invoke(facade, world, value):
    if value['operation'] == 'recover' and not world.get('skip_recovery_attribution'):
        attribute_recovery_fixture(world)
    return facade.handle(value, project=world['project'], actor=world['actor'],
                         runtime_root=world['runtime'], source_mode='synthetic')


def attribute_recovery_fixture(world):
    """Synthetic guard attribution for actual isolated fixture writes only.

    Production recovery never creates this evidence. The fixture has no live
    repo guard; enumerate and hash its real dirty files to exercise PM's full
    resolver instead of replacing it with a selected-path stub.
    """
    import project_state
    import os
    import tempfile
    import run_state
    directory=world['runtime'].parent/'repo-guard/pending'
    directory.mkdir(parents=True,exist_ok=True)
    dirty=project_state._dirty_project_files(world['repo'],'projects/alpha')
    identity=run_state.native_binding(world['board'],world['actor']['native_payload'])['session_uuid']
    fd,path=tempfile.mkstemp(prefix='.synthetic-',dir=directory)
    with os.fdopen(fd,'w') as stream:
        stream.write(json.dumps({'schema_version':2,'session_id':identity,
            'paths':[row['path'] for row in dirty], 'path_hashes':{row['path']:row['sha256'] for row in dirty}}))
    os.replace(path,directory/'synthetic-fixture.json')


def state_of(world, response):
    import run_state
    return run_state.load_run(world['project'], response['run_id'])


def test_start_commits_real_owner_state_and_replay_keeps_prefix(facade, world):
    original_plan = world['plan'].read_text()
    req = start_request(world)
    first = invoke(facade, world, req)
    state = state_of(world, first)
    assert first['status'] == 'READY'
    assert state['extensions']['workflow']['graph']['nodes']['work']['status'] == 'pending'
    assert state['owner']['native_ref'].startswith('cc:')
    assert original_plan.strip() in world['plan'].read_text()
    second = invoke(facade, world, req)
    assert state_of(world, second) == state
    changed = deepcopy(req)
    changed['input']['resource_envelope']['limits']['model_tokens']['limit'] += 1
    assert invoke(facade, world, changed)['status'] == 'UNRESOLVED'
    assert state_of(world, first) == state


def test_replayed_start_cannot_change_synthetic_provenance_claim(facade, world):
    req = start_request(world)
    first = invoke(facade, world, req)
    state = state_of(world, first)
    changed = facade.handle(req, project=world['project'], actor=world['actor'],
                            runtime_root=world['runtime'], source_mode='native')
    assert changed['status'] == 'UNRESOLVED'
    assert state_of(world, first) == state
    assert state['extensions']['native_observations']['sources']['root']['binding']['mode'] == 'synthetic'


@pytest.mark.parametrize('interrupt', ['create', 'configure', 'budget', 'graph'])
def test_start_interruption_committed_prefix_resumes(facade, world, monkeypatch, interrupt):
    import run_state
    req = start_request(world)
    original = run_state._project
    fired = False
    def interrupted(project, state):
        nonlocal fired
        flow = state.get('extensions', {}).get('workflow', {})
        reached = (interrupt == 'create' or
                   interrupt == 'configure' and bool(flow) or
                   interrupt == 'budget' and 'budget' in flow or
                   interrupt == 'graph' and 'graph' in flow)
        if reached and not fired:
            fired = True
            raise OSError('synthetic interruption after durable journal commit')
        return original(project, state)
    monkeypatch.setattr(run_state, '_project', interrupted)
    first = invoke(facade, world, req)
    assert first['status'] == 'UNRESOLVED'
    monkeypatch.setattr(run_state, '_project', original)
    final = invoke(facade, world, req)
    assert final['status'] == 'READY'
    journal = list(run_state._events(world['project'], final['run_id']))
    assert len({row['command_id'] for row in journal}) == len(journal)


def test_stale_revision_changes_no_owner_state(facade, world):
    response = invoke(facade, world, start_request(world))
    state = state_of(world, response)
    stale = request('record', {'kind': 'note', 'summary': 'Unmeasured note'}, state)
    stale['expected_revision'] -= 1
    assert invoke(facade, world, stale)['status'] == 'UNRESOLVED'
    assert state_of(world, response) == state


def test_note_is_not_measured_progress_and_next_uses_actual_frontier(facade, world):
    response = invoke(facade, world, start_request(world))
    state = state_of(world, response)
    response = invoke(facade, world, request('next', {'mode': 'start'}, state))
    state = state_of(world, response)
    assert state['extensions']['workflow']['graph']['nodes']['work']['status'] == 'running'
    response = invoke(facade, world, request('record', {'kind': 'note', 'summary': 'Narration'}, state))
    state = state_of(world, response)
    assert state['progress']['measured'] is False
    assert not state['extensions']['workflow']['progress']
    assert not state['evidence']


def test_read_only_without_actor_never_mutates_or_certifies(facade, world):
    value = start_request(world)
    response = facade.handle(value, project=world['project'], actor=None, runtime_root=world['runtime'])
    assert response['status'] == 'UNRESOLVED'
    assert not (world['project'] / 'resources/autopilot-runs').exists()
    response = invoke(facade, world, value)
    state = state_of(world, response)
    explained = facade.handle(request('explain', {'view': 'run'}, state), project=world['project'])
    assert explained['coverage']['owner_admission'] == 'UNVERIFIED'
    assert state_of(world, response) == state


def test_cancel_tombstone_survives_late_native_events(facade, world):
    response = invoke(facade, world, start_request(world))
    state = state_of(world, response)
    response = invoke(facade, world, request('cancel', {'target': 'run', 'reason': 'Stop synthetic task'}, state))
    state = state_of(world, response)
    terminal = deepcopy(state['terminal'])
    assert state['status'] == 'cancelled'
    with world['transcript'].open('a') as stream:
        stream.write(json.dumps({'type': 'user', 'sessionId': world['actor']['native_payload']['session_id'],
                                 'message': {'role': 'user', 'content': 'late synthetic message'}}) + '\n')
    response = invoke(facade, world, request('record', {'kind': 'native', 'source_handle': 'root',
        'through_event': None, 'task_id': None, 'attempt_id': None}, state, identity='late'))
    after = state_of(world, response)
    assert after['status'] == 'cancelled' and after['terminal'] == terminal
    assert response['status'] in {'CANCELLED', 'RECORDED'}


@pytest.mark.parametrize('raw', [b'{"schema_version":1,"schema_version":1}', b'{"x":NaN}',
                               b'{"x":Infinity}', b'[]', b'{"schema_version":true}',
                               b'{' + b' ' * (256 * 1024) + b'}'],
                         ids=['duplicate', 'nan', 'infinity', 'array', 'boolean-schema', 'oversize'])
def test_strict_bounded_request_json(facade, raw):
    with pytest.raises(ValueError):
        facade.decode_request(raw)


@pytest.mark.parametrize('extra', ['approved', 'passed', 'callback', 'producer', 'command'])
def test_request_cannot_add_authority_fields(facade, world, extra):
    value = start_request(world)
    value['input'][extra] = True
    with pytest.raises(ValueError):
        facade.validate_request(value)


def test_finish_cannot_close_unobserved_work(facade, world):
    response = invoke(facade, world, start_request(world))
    state = state_of(world, response)
    response = invoke(facade, world, request('finish', {'disposition': 'completed'}, state))
    assert response['status'] == 'UNRESOLVED'
    state = state_of(world, response)
    assert state['status'] != 'completed' and response['next']
    response = invoke(facade, world, request('finish', {'disposition': 'incomplete', 'reason': 'Synthetic scope unfinished'}, state, 'incomplete'))
    assert response['status'] == 'INCOMPLETE'


def prepared_consumer(facade, world, *, expected=5, observed=5):
    req = start_request(world)
    criterion = req['input']['outcome_contract']['criteria'][0]
    criterion.update(method='consumer-check', evidence_ids=['accept-slot'])
    response = invoke(facade, world, req)
    assert response['status'] == 'READY', response
    state = state_of(world, response)
    response = invoke(facade, world, request('next', {'mode': 'start'}, state))
    assert response['status'] == 'READY', response
    for identity, name, content, role in [
        ('output', 'result.json', json.dumps({'answer': observed}), 'output'),
        ('program', 'check.py', 'import json\nfrom pathlib import Path\nprint(json.dumps(json.loads(Path("result.json").read_text())))\n', 'input')]:
        path = world['project'] / name
        path.write_text(content)
        state = state_of(world, response)
        response = invoke(facade, world, request('record', {'kind': 'artifact', 'artifact_id': identity,
            'path': str(path), 'role': role, 'required': role == 'output', 'retention': 'durable'}, state, 'artifact-' + identity))
        assert response['status'] == 'RECORDED', response
    state = state_of(world, response)
    req = request('record', {'kind': 'check', 'observer_kind': 'consumer-check', 'arguments': {
        'criterion_id': 'accept', 'artifact_id': 'output', 'script_artifact_id': 'program',
        'expected': {'answer': expected}, 'argv': [], 'timeout_seconds': 2}}, state, 'consumer')
    response = invoke(facade, world, req)
    assert response['status'] == 'RECORDED', response
    return state_of(world, response), req


def test_real_consumer_output_is_retained_with_no_caller_pass(facade, world):
    state, req = prepared_consumer(facade, world)
    records = [row for row in state['evidence'].values() if row['kind'] == 'consumer-check']
    assert len(records) == 1
    data = records[0]['data']
    assert data['execution']['returncode'] == 0 and data['execution']['sandbox_verified'] is True
    assert data['observations']['observed'] == {'answer': 5} and data['passed'] is True
    assert data['independent'] is False
    assert invoke(facade, world, req)['revision'] == state['revision']


def test_failed_actual_consumer_never_closes(facade, world):
    state, _ = prepared_consumer(facade, world, observed=9)
    response = invoke(facade, world, request('finish', {'disposition': 'completed'}, state))
    assert response['status'] == 'UNRESOLVED'
    state = state_of(world, response)
    assert state['status'] != 'completed'
    assert any(row['kind'] == 'consumer-check' and row['data']['passed'] is False for row in state['evidence'].values())


def test_later_failed_consumer_is_not_hidden_by_json_key_order(facade, world):
    import run_state
    state, original = prepared_consumer(facade, world)
    first = 'controller.' + run_state._digest(['consumer', 'observe:check'])
    identity = next('later-check-' + str(index) for index in range(100)
        if 'controller.' + run_state._digest(['later-check-' + str(index), 'observe:check']) < first)
    values = deepcopy(original['input'])
    values['arguments']['expected'] = {'answer': 9}
    response = invoke(facade, world, request('record', values, state, identity))
    assert response['status'] == 'RECORDED', response
    state = state_of(world, response)
    reports = [row for row in state['evidence'].values() if row['kind'] == 'consumer-check']
    assert len(reports) == 2 and {row['data']['passed'] for row in reports} == {False, True}
    response = invoke(facade, world, request('finish', {'disposition': 'completed'}, state))
    assert response['status'] == 'UNRESOLVED', response
    state = state_of(world, response)
    assert state['status'] != 'completed'
    assert state['extensions']['workflow']['quality']['accept']['verdict'] == 'FAIL'


def test_successful_default_consumer_finishes_through_real_profile_owner(facade, world):
    state, _ = prepared_consumer(facade, world)
    response = invoke(facade, world, request('finish', {'disposition': 'completed'}, state))
    assert response['status'] == 'COMPLETED', response
    assert response['coverage']['completion_report']
    current = state_of(world, response)
    assert current['extensions']['workflow']['graph']['nodes']['work']['status'] == 'done'
    import run_state
    assert run_state.criterion_report(current, run_state.inspect_context(current, world['actor']))['criteria'][0]['status'] == 'PASS'


@pytest.mark.parametrize('adopted', [False, True])
def test_terminal_finish_replay_uses_current_acceptance_without_repeating_effects(facade, world, monkeypatch, adopted):
    import run_state
    if adopted:
        adopt_pm(world)
    state, _ = prepared_consumer(facade, world)
    req = request('finish', {'disposition': 'completed'}, state)
    first = invoke(facade, world, req)
    assert first['status'] == 'COMPLETED', first
    terminal = state_of(world, first)
    home = run_state._home(world['project'], terminal['run_id'])
    snapshot = {str(p): p.read_bytes() for p in home.rglob('*') if p.is_file()}
    def forbidden(*args, **kwargs):
        raise AssertionError('Terminal replay may not repeat effects or rewrite the journal/projections')
    monkeypatch.setattr(run_state, '_append', forbidden)
    monkeypatch.setattr(run_state, '_project', forbidden)
    same = invoke(facade, world, req)
    assert same['status'] == 'COMPLETED', same
    original = (world['project'] / 'result.json').read_bytes()
    (world['project'] / 'result.json').write_text('{"answer":666}')
    stale = invoke(facade, world, req)
    assert stale['status'] == 'UNRESOLVED', stale
    assert stale['coverage']['current_acceptance']['status'] == 'FAIL'
    assert state_of(world, stale) == terminal
    assert {str(p): p.read_bytes() for p in home.rglob('*') if p.is_file()} == snapshot
    (world['project'] / 'result.json').write_bytes(original)
    restored = invoke(facade, world, req)
    assert restored['status'] == 'COMPLETED', restored


@pytest.mark.parametrize('observed', [False, True])
def test_typed_native_abort_refuses_default_finish(facade, world, monkeypatch, observed):
    native = world['actor']['native_payload']['session_id']
    directory = world['scratch'] / 'codex-cancel' / 'sessions/2026/09/25'
    directory.mkdir(parents=True)
    transcript = directory / ('rollout-' + native + '.jsonl')
    transcript.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': native,
        'cwd': str(world['repo'])}}) + '\n')
    world['transcript'] = transcript
    world['actor']['native_payload']['transcript_path'] = str(transcript)
    world['board'].write_text(world['board'].read_text().replace('| claude |', '| codex |').replace('cc:' + native, 'codex:' + native))
    monkeypatch.setenv('CODEX_HOME', str(world['scratch'] / 'codex-cancel'))
    monkeypatch.setenv('SYNTHESIS_CLIENT_SESSION_REF', 'codex:' + native)
    state, _ = prepared_consumer(facade, world)
    with transcript.open('a') as stream:
        stream.write(json.dumps({'type': 'event_msg', 'payload': {'type': 'turn_aborted',
            'turn_id': 'synthetic-aborted-turn'}}) + '\n')
    if observed:
        result = invoke(facade, world, request('record', {'kind': 'native', 'source_handle': 'root',
            'through_event': None, 'task_id': None, 'attempt_id': None}, state, 'observed-abort'))
        state = state_of(world, result)
    result = invoke(facade, world, request('finish', {'disposition': 'completed'}, state))
    assert result['status'] == 'UNRESOLVED', result
    assert state_of(world, result)['status'] != 'completed'


def test_completed_next_replay_keeps_original_task_selection(facade, world):
    response = invoke(facade, world, start_request(world))
    req = request('next', {'mode': 'start'}, state_of(world, response))
    first = invoke(facade, world, req)
    assert first['status'] == 'READY'
    replay = invoke(facade, world, req)
    assert replay['status'] == 'READY' and replay['revision'] == first['revision']
    changed = deepcopy(req)
    changed['input']['task_id'] = 'other'
    assert invoke(facade, world, changed)['status'] == 'UNRESOLVED'


def test_recover_rebuilds_tampered_projection_and_retains_native_cursor(facade, world):
    import run_state
    response = invoke(facade, world, start_request(world))
    state = state_of(world, response)
    home = run_state._home(world['project'], state['run_id'])
    original = deepcopy(state['extensions']['native_observations']['sources']['root']['cursor'])
    (home / 'current.json').write_text('{"forged":true}')
    req = request('recover', {'reconcile_sources': False}, state)
    response = invoke(facade, world, req)
    assert response['status'] == 'READY', response
    current = state_of(world, response)
    assert json.loads((home / 'current.json').read_text()) == current
    assert current['extensions']['native_observations']['sources']['root']['cursor'] == original
    assert invoke(facade, world, req)['revision'] == current['revision']


def test_stale_recover_does_not_write_projection(facade, world):
    import run_state
    response = invoke(facade, world, start_request(world))
    state = state_of(world, response)
    home = run_state._home(world['project'], state['run_id'])
    (home / 'current.json').write_text('retained corrupt projection')
    req = request('recover', {'reconcile_sources': False}, state)
    req['expected_revision'] -= 1
    response = invoke(facade, world, req)
    assert response['status'] == 'UNRESOLVED'
    assert (home / 'current.json').read_text() == 'retained corrupt projection'


def test_changed_finish_request_after_committed_prefix_is_rejected(facade, world):
    state, _ = prepared_consumer(facade, world)
    req = request('finish', {'disposition': 'completed'}, state)
    response = invoke(facade, world, req)
    after = state_of(world, response)
    changed = deepcopy(req)
    changed['input'] = {'disposition': 'incomplete', 'reason': 'Changed replay cannot alter intent'}
    assert invoke(facade, world, changed)['status'] == 'UNRESOLVED'
    assert state_of(world, response) == after
    replay = invoke(facade, world, req)
    assert not any('different input' in row['detail'] for row in replay['diagnostics']), replay


def test_partial_source_tail_refuses_admission_until_writer_completes_record(facade, world):
    response = invoke(facade, world, start_request(world))
    with world['transcript'].open('ab') as stream:
        stream.write(b'{"type":"user"')
    state = state_of(world, response)
    req = request('checkpoint', {'reason': 'Partial source', 'include_pm': False}, state)
    response = invoke(facade, world, req)
    assert response['status'] == 'UNRESOLVED'
    assert any('native session' in row['detail'] for row in response['diagnostics'])
    assert response['coverage']['owner_admission'] == 'UNVERIFIED'
    assert state_of(world, response) == state
    session = world['actor']['native_payload']['session_id']
    with world['transcript'].open('ab') as stream:
        stream.write((',"sessionId":' + json.dumps(session) + ',"message":{"role":"user","content":"complete"}}\n').encode())
    retried = invoke(facade, world, req)
    assert retried['status'] == 'RECORDED', retried
    assert retried['coverage']['native']['root']['coverage']['pending_bytes'] == 0


def test_replayed_request_still_needs_live_owner(facade, world):
    from test_run_admission import write_board
    response = invoke(facade, world, start_request(world))
    state = state_of(world, response)
    req = request('record', {'kind': 'note', 'summary': 'Historical note'}, state)
    first = invoke(facade, world, req)
    before = state_of(world, first)
    write_board(world, status='released')
    assert invoke(facade, world, req)['status'] == 'UNRESOLVED'
    assert state_of(world, first) == before


def test_profile_trigger_is_immutable_current_intent_not_acceptance(facade, world):
    response = invoke(facade, world, start_request(world))
    path = world['project'] / 'finding.txt'
    path.write_text('A source-backed synthetic finding')
    response = invoke(facade, world, request('record', {'kind': 'artifact', 'artifact_id': 'finding',
        'path': str(path), 'role': 'input', 'required': False, 'retention': 'durable'}, state_of(world, response), 'finding-file'))
    req = request('record', {'kind': 'profile_obligation', 'obligation_id': 'finding',
        'obligation_kind': 'reusable-finding', 'artifact_ids': ['finding'], 'criterion_ids': [],
        'reason': 'Observed reusable finding needs capture'}, state_of(world, response), 'finding-trigger')
    response = invoke(facade, world, req)
    assert response['status'] == 'RECORDED', response
    state = state_of(world, response)
    row = state['extensions']['controller']['profile_obligations']['finding']
    assert row['artifact_digests'] == {'finding': state['artifacts']['finding']['digest']}
    assert not row['criterion_ids'] and not state['evidence'] and not state['verification']
    changed = deepcopy(req)
    changed.update(request_id='changed-trigger', expected_revision=state['revision'])
    changed['input']['criterion_ids'] = ['accept']
    assert invoke(facade, world, changed)['status'] == 'UNRESOLVED'
    assert state_of(world, response) == state


def test_profile_trigger_rejects_stale_source_bytes(facade, world):
    state, _ = prepared_consumer(facade, world)
    (world['project'] / 'result.json').write_text('{"answer":99}')
    response = invoke(facade, world, request('record', {'kind': 'profile_obligation',
        'obligation_id': 'decision', 'obligation_kind': 'decision', 'artifact_ids': ['output'],
        'criterion_ids': ['accept'], 'reason': 'Current rationale required'}, state, 'decision'))
    assert response['status'] == 'UNRESOLVED'
    assert 'profile_obligations' not in state_of(world, response)['extensions']['controller']


def adopt_pm(world):
    import project_state
    from run_admission import native_binding
    proof = native_binding(world['board'], world['actor']['native_payload'])
    return project_state.build_operational_state(world['project'], project_id='alpha', phase='verification',
        status='active', controlling_plan='plan.md', accepted_baseline='Synthetic current fixture',
        next_actions=['Verify the declared output through its actual consumer.'], last_session='Synthetic session',
        session_id=proof['session_uuid'], source_heads={})


def test_adopted_pm_final_checkpoint_follows_last_terminal_write(facade, world):
    import project_state
    import run_state
    adopt_pm(world)
    state, _ = prepared_consumer(facade, world)
    req = request('finish', {'disposition': 'completed'}, state)
    response = invoke(facade, world, req)
    assert response['status'] == 'COMPLETED', response
    final = state_of(world, response)
    intent = final['extensions']['controller']['closure_intent']
    assert not Path(intent['receipt_root']).is_relative_to(world['project'])
    assert response['coverage']['closure_postamble']['status'] == 'PASS'
    status, issues = project_state.validate_checkpoint(world['project'], session_id=final['owner']['session_uuid'],
        coordination_board=world['board'], receipt_root=Path(intent['receipt_root']), source_heads={})
    assert status == 'PASS', issues
    assert run_state.completion_report(world['project'], final['run_id'], actor=world['actor'])['status'] == 'PASS'


@pytest.mark.parametrize('boundary', ['before-checkpoint', 'after-checkpoint'])
def test_terminal_postamble_retry_never_replays_consumer_or_journal(facade, world, monkeypatch, boundary):
    import project_state
    import run_state
    adopt_pm(world)
    state, _ = prepared_consumer(facade, world)
    req = request('finish', {'disposition': 'completed'}, state)
    original = project_state.checkpoint_project
    def interrupted(*args, **kwargs):
        if boundary == 'after-checkpoint':
            original(*args, **kwargs)
        raise OSError('Synthetic final checkpoint interruption')
    monkeypatch.setattr(project_state, 'checkpoint_project', interrupted)
    first = invoke(facade, world, req)
    assert first['status'] == 'UNRESOLVED', first
    final = state_of(world, first)
    assert final['status'] == 'completed'
    assert first['coverage']['closure_postamble']['status'] == 'PENDING'
    home = run_state._home(world['project'], final['run_id'])
    snapshot = {str(path): path.read_bytes() for path in home.rglob('*') if path.is_file()}
    monkeypatch.setattr(project_state, 'checkpoint_project', original)
    def forbidden(*args, **kwargs):
        raise AssertionError('Terminal retry may not append journal or replay projections/effects')
    monkeypatch.setattr(run_state, '_append', forbidden)
    monkeypatch.setattr(run_state, '_project', forbidden)
    retry = invoke(facade, world, req)
    assert retry['status'] == 'COMPLETED', retry
    assert state_of(world, retry) == final
    assert {str(path): path.read_bytes() for path in home.rglob('*') if path.is_file()} == snapshot


def test_generation_recover_requires_exact_prior_binding_and_preserves_history(facade, world):
    import native_observations
    from test_observation_bridge import pair, append
    response = invoke(facade, world, start_request(world))
    append(world, *pair(world))
    response = invoke(facade, world, request('record', {'kind': 'native', 'source_handle': 'root',
        'through_event': None, 'task_id': None, 'attempt_id': None}, state_of(world, response), 'before-rotation'))
    state = state_of(world, response)
    old = deepcopy(state['extensions']['native_observations']['sources']['root'])
    path = world['transcript']
    raw = path.read_bytes()
    path.rename(path.with_suffix('.retained'))
    path.write_bytes(raw)
    response = invoke(facade, world, request('recover', {'reconcile_sources': True}, state, 'discover-rotation'))
    assert response['status'] == 'RECONCILE', response
    state = state_of(world, response)
    current = state['extensions']['native_observations']['sources']['root']
    assert current['cursor'] == old['cursor']
    row = {'source_handle': 'root', 'prior_generation': old['binding']['generation'],
        'prior_cursor_digest': native_observations._digest(old['cursor']),
        'new_generation': current['recovery']['observed_generation'], 'mode': 'carry'}
    response = invoke(facade, world, request('recover', {'reconcile_sources': True, 'source_reconciliations': [row]}, state, 'carry-rotation'))
    assert response['status'] == 'READY', response
    current = state_of(world, response)['extensions']['native_observations']['sources']['root']
    assert current['history'][0]['cursor'] == old['cursor']
    assert current['cursor']['offset'] == old['cursor']['offset']


HISTORY_LIMITS = {"steps": 128, "bytes": 512 * 1024 * 1024, "sources": 8, "wall_millis": 120000}


def historical_fixture(facade, engine, world, monkeypatch, *, shape=None):
    from test_native_replay import broken_history, original_cursor_shape, src
    from test_run_state import command
    import workflow
    import native_observations as native
    if shape:
        old = original_cursor_shape(engine, world, monkeypatch, shape)
    else:
        old = broken_history(engine, world, monkeypatch, cancel=True, separate_cancel=True)
    workflow.register_commands(engine.register_command)
    old = command(engine, world, old, "workflow.configure", {"dimensions": {
        "domains": ["software"], "uncertainty": "low", "effect": "local-reversible", "horizon": "session", "parallelizable": False}})
    old = command(engine, world, old, "workflow.budget", {"limits": {"model_tokens": {"limit": 10000, "enforcement": "forecast"}},
        "deadline": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()})
    for identity, actual in (("known", {"model_tokens": 23}), ("unknown", None)):
        old = command(engine, world, old, "workflow.reserve", {"reservation_id": identity, "category": "work", "amounts": {"model_tokens": 100}})
        old = command(engine, world, old, "workflow.settle", {"reservation_id": identity, "actual": actual})
    old = command(engine, world, old, "close", {"status": "incomplete", "reason": "Retained original interval"})
    event = engine._read(engine._home(world["project"], old["run_id"]) / "events" / f"{old['revision']:012d}.json")
    subject = {"run_id": old["run_id"], "revision": old["revision"], "event_digest": event["digest"],
        "state_digest": engine._digest(old), "source_handle": "root", "source_digest": native._digest(src(old))}
    current = state_of(world, invoke(facade, world, start_request(world, "current-interval")))
    return old, current, subject


def history_request(current, subject, identity="history", limits=None):
    return request("recover", {"reconcile_sources": True, "historical_subject": subject,
        "replay_limits": limits or HISTORY_LIMITS}, current, identity)


@pytest.mark.parametrize("shape", [None, "partial", "unequal"])
def test_current_run_qualifies_historical_subject_without_replacing_lineage(facade, engine, world, monkeypatch, shape):
    import native_observations as native
    old, current, subject = historical_fixture(facade, engine, world, monkeypatch, shape=shape)
    old_bytes = {str(path): path.read_bytes() for path in engine._home(world["project"], old["run_id"]).rglob("*") if path.is_file()}
    req = history_request(current, subject)
    response = invoke(facade, world, req)
    final = state_of(world, response)
    row = final["extensions"]["native_history"][native._digest(subject)]
    assert row["status"] == "complete", response
    assert row["source"]["cursor"]["offset"] == world["transcript"].stat().st_size
    assert row["subject_terminal"] == old["terminal"]
    assert row["subject_budget_digest"] == native._digest(old["extensions"]["workflow"]["budget"])
    assert row["authority_granted"] is False and row["effects_replayed"] is False
    assert row["native_acceptance"] == row["negative_coverage"] == "UNKNOWN"
    assert row["validation_bytes_charged"] > 0 and row["steps"] > 1
    if shape is None:
        assert row["prior_invalidation_count"] > 0
    assert final["extensions"]["workflow"]["budget"] == current["extensions"]["workflow"]["budget"]
    assert final["extensions"]["native_observations"] == current["extensions"]["native_observations"]
    for key in ("contract", "profile", "artifacts", "effects", "plan"):
        assert final[key] == current[key]
    assert not final.get("successor")
    assert engine.load_run(world["project"], old["run_id"]) == old
    assert all(Path(name).read_bytes() == data for name, data in old_bytes.items())
    assert state_of(world, invoke(facade, world, req)) == final


@pytest.mark.parametrize("fault", ["state_digest", "event_digest", "source_digest", "revision", "self", "open"])
def test_historical_subject_refuses_forged_stale_or_open_binding(facade, engine, world, monkeypatch, fault):
    import native_observations as native
    old, current, subject = historical_fixture(facade, engine, world, monkeypatch)
    if fault in {"state_digest", "event_digest", "source_digest"}:
        subject[fault] = "0" * 64
    elif fault == "revision":
        subject["revision"] -= 1
    else:
        event = engine._read(engine._home(world["project"], current["run_id"]) / "events" / f"{current['revision']:012d}.json")
        subject.update(run_id=current["run_id"], revision=current["revision"], state_digest=engine._digest(current), event_digest=event["digest"],
            source_digest=native._digest(current["extensions"]["native_observations"]["sources"]["root"]))
        if fault == "open":
            current = state_of(world, invoke(facade, world, start_request(world, "another-current")))
    response = invoke(facade, world, history_request(current, subject))
    assert response["status"] == "UNRESOLVED", response
    assert not state_of(world, response)["extensions"].get("native_history")
    assert engine.load_run(world["project"], old["run_id"]) == old


@pytest.mark.parametrize("fault", ["source", "journal", "allowance", "expired"])
def test_historical_validation_cannot_resume_changed_custody_or_reset_allowance(facade, engine, world, monkeypatch, fault):
    import native_observations as native
    import observation_bridge
    from test_run_state import command
    old, current, subject = historical_fixture(facade, engine, world, monkeypatch)
    current = command(engine, world, current, "native.history", {"subject": subject, "limits": HISTORY_LIMITS})
    retained = deepcopy(current)
    if fault == "source":
        with world["transcript"].open("a") as stream:
            stream.write(" ")
    elif fault == "journal":
        path = engine._home(world["project"], old["run_id"]) / "events" / "000000000001.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif fault == "expired":
        monkeypatch.setattr(observation_bridge, "_history_tick", lambda record: (_ for _ in ()).throw(ValueError("deadline exhausted")))
    limits = deepcopy(HISTORY_LIMITS)
    if fault == "allowance":
        limits["steps"] += 1
    with pytest.raises(ValueError):
        command(engine, world, current, "native.history", {"subject": subject, "limits": limits})
    assert engine.load_run(world["project"], current["run_id"]) == retained
    row = retained["extensions"]["native_history"][native._digest(subject)]
    assert row["steps"] == 1


@pytest.mark.parametrize("fault", ["step", "byte"])
def test_historical_validation_limits_are_persistent_across_requests(facade, engine, world, monkeypatch, fault):
    import native_observations as native
    old, current, subject = historical_fixture(facade, engine, world, monkeypatch)
    limits = deepcopy(HISTORY_LIMITS)
    limits["steps" if fault == "step" else "bytes"] = 1
    response = invoke(facade, world, history_request(current, subject, limits=limits))
    assert response["status"] == "UNRESOLVED"
    final = state_of(world, response)
    if fault == "step":
        row = deepcopy(final["extensions"]["native_history"][native._digest(subject)])
        assert row["steps"] == 1
        retry = invoke(facade, world, history_request(final, subject, "another-request", limits))
        assert retry["status"] == "UNRESOLVED"
        assert state_of(world, retry)["extensions"]["native_history"][native._digest(subject)] == row
    else:
        assert not final["extensions"].get("native_history")
    assert engine.load_run(world["project"], old["run_id"]) == old


@pytest.mark.parametrize("client", ["claude", "codex"])
def test_historical_identity_is_its_own_not_the_current_actor(facade, engine, world, monkeypatch, client):
    from test_native_replay import src
    old, unused, subject = historical_fixture(facade, engine, world, monkeypatch)
    previous = world["actor"]["native_payload"]["session_id"]
    identity = "01990000-0000-7000-8000-000000000099"
    home = world["scratch"] / "current-native"
    if client == "claude":
        path = home / "projects/fixture" / (identity + ".jsonl")
        row = {"type": "user", "sessionId": identity, "cwd": str(world["repo"]),
            "message": {"role": "user", "content": "Synthetic current owner"}}
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
        ref = "cc:" + identity
    else:
        path = home / "sessions/2026/09/28" / ("rollout-" + identity + ".jsonl")
        row = {"type": "session_meta", "payload": {"id": identity, "cwd": str(world["repo"])}}
        monkeypatch.setenv("CODEX_HOME", str(home))
        ref = "codex:" + identity
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(row) + "\n")
    world["actor"]["native_payload"].update(session_id=identity, transcript_path=str(path))
    world["transcript"] = path
    world["board"].write_text(world["board"].read_text().replace("cc:" + previous, ref).replace("| claude |", "| " + client + " |"))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", ref)
    current = state_of(world, invoke(facade, world, start_request(world, "new-native-current")))
    response = invoke(facade, world, history_request(current, subject))
    assert response["coverage"]["historical_subject"]["status"] == "complete", response
    assert response["coverage"]["historical_subject"]["invalidation_status"] == "invalidated"
    assert src(state_of(world, response))["binding"]["producer"]["root_session_id"] == identity
    assert src(old)["binding"]["producer"]["root_session_id"] == previous
    assert engine.load_run(world["project"], old["run_id"]) == old


@pytest.mark.parametrize("fault", ["source", "subject", "board"])
def test_historical_commit_rechecks_late_source_subject_and_authority(facade, engine, world, monkeypatch, fault):
    import observation_bridge
    from test_run_state import command
    from test_observation_bridge import append, pair
    old, current, subject = historical_fixture(facade, engine, world, monkeypatch)
    reducer = observation_bridge._reduce_history
    def mutate(state, prepared, context):
        result = reducer(state, prepared, context)
        if fault == "source":
            append(world, *pair(world, "concurrent"))
        elif fault == "subject":
            path = engine._home(world["project"], old["run_id"]) / "events" / ".run-new"
            path.write_text("retained incomplete staging")
        else:
            world["board"].write_text(world["board"].read_text().replace("| active |", "| complete |"))
        return result
    monkeypatch.setitem(engine._COMMANDS, "native.history", mutate)
    with pytest.raises(ValueError):
        command(engine, world, current, "native.history", {"subject": subject, "limits": HISTORY_LIMITS})
    assert engine.load_run(world["project"], current["run_id"]) == current


def test_historical_committed_page_survives_projection_interruption(facade, engine, world, monkeypatch):
    from test_run_state import command
    old, current, subject = historical_fixture(facade, engine, world, monkeypatch)
    original = engine._project
    monkeypatch.setattr(engine, "_project", lambda *a, **k: (_ for _ in ()).throw(OSError("projection interrupted")))
    with pytest.raises(OSError, match="projection interrupted"):
        command(engine, world, current, "native.history", {"subject": subject, "limits": HISTORY_LIMITS}, command_id="historical-cold")
    monkeypatch.setattr(engine, "_project", original)
    recovered = engine.load_run(world["project"], current["run_id"])
    assert recovered["revision"] == current["revision"] + 1
    assert command(engine, world, current, "native.history", {"subject": subject, "limits": HISTORY_LIMITS}, command_id="historical-cold") == recovered
    assert engine.load_run(world["project"], old["run_id"]) == old


def test_historical_partial_user_record_retains_newly_decoded_cancellation(facade, engine, world, monkeypatch):
    import test_native_replay
    from test_observation_bridge import append
    original_append = test_native_replay.append
    def replace_final(target, *rows):
        converted = []
        for row in rows:
            if row.get("message", {}).get("content") == [{"type": "text", "text": "5" * 200000}]:
                row = {"type": "user", "sessionId": target["actor"]["native_payload"]["session_id"],
                    "message": {"role": "user", "content": "Pause this task. " + "x" * 200000}}
            converted.append(row)
        original_append(target, *converted)
    monkeypatch.setattr(test_native_replay, "append", replace_final)
    old, current, subject = historical_fixture(facade, engine, world, monkeypatch, shape="partial")
    # A later source record is explicitly outside the historical qualification.
    append(world, {"type": "user", "sessionId": world["actor"]["native_payload"]["session_id"],
        "message": {"role": "user", "content": "Later unrelated source text"}})
    response = invoke(facade, world, history_request(current, subject))
    assert "historical_subject" in response["coverage"], response
    row = response["coverage"]["historical_subject"]
    assert row["status"] == "complete", response
    assert row["prior_invalidation_count"] == 0
    assert row["invalidation_status"] == "invalidated"
    assert row["observed_offset"] < world["transcript"].stat().st_size
    assert "source" not in row and "journal_witnesses" not in row
    assert "derived_projection" not in row and "cursor" not in row
    assert row["authority_granted"] is False
    assert engine.load_run(world["project"], old["run_id"]) == old


@pytest.mark.parametrize("cancel", [False, True])
@pytest.mark.parametrize("default_limits", [False, True])
def test_current_recovery_finishes_captured_partial_snapshot(facade, engine, world, monkeypatch, cancel, default_limits):
    from test_native_replay import original_cursor_shape, src
    from test_observation_bridge import append
    import observation_bridge
    state = original_cursor_shape(engine, world, monkeypatch, "partial")
    if cancel:
        append(world, {"type": "user", "sessionId": world["actor"]["native_payload"]["session_id"],
            "message": {"role": "user", "content": "Pause this task."}})
    data = {"reconcile_sources": True}
    if not default_limits:
        data["replay_limits"] = HISTORY_LIMITS
    response = invoke(facade, world, request("recover", data, state, "partial-current"))
    assert response["coverage"]["replay_driver"]["status"] == "complete", response
    current = state_of(world, response)
    assert src(current)["cursor"]["offset"] == src(current)["cursor"]["frame_start"] == world["transcript"].stat().st_size
    verdict = observation_bridge.current_invalidation(engine.inspect_context(current, world["actor"]))
    assert verdict["status"] == ("invalidated" if cancel else "clear")


def test_exhausted_historical_allowance_refuses_before_subject_io(facade, engine, world, monkeypatch):
    import observation_bridge
    old, current, subject = historical_fixture(facade, engine, world, monkeypatch)
    limits = {**HISTORY_LIMITS, "steps": 1}
    original = observation_bridge._history_head
    reads = []
    def counted(*args, **kwargs):
        reads.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(observation_bridge, "_history_head", counted)
    response = invoke(facade, world, history_request(current, subject, limits=limits))
    assert response["status"] == "UNRESOLVED", response
    assert len(reads) == 1
    saved = state_of(world, response)
    for name in ("retry-a", "retry-b"):
        reads.clear()
        req = history_request(saved, subject, limits=limits)
        req["request_id"] = name
        response = invoke(facade, world, req)
        assert response["status"] == "UNRESOLVED", response
        assert reads == []
        saved = state_of(world, response)
