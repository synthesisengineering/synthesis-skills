"""Wholly synthetic public fixtures. No fixture is native qualification evidence."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
import native_codex as codex
import native_claude as claude
import native_muse as muse
import native_observations as native

SESSION = '00000000-0000-4000-8000-000000000001'
PRODUCERS = {name: {'client': name, 'thread_id': SESSION, 'root_session_id': SESSION,
                   'parent_thread_id': None} for name in ('codex', 'claude', 'muse')}


def exec_rows():
    return [
        {'type': 'thread.started', 'thread_id': SESSION}, {'type': 'turn.started'},
        {'type': 'item.started', 'item': {'id': 'item_1', 'type': 'command_execution',
         'command': "cat input.json", 'aggregated_output': '', 'exit_code': None, 'status': 'in_progress'}},
        {'type': 'item.completed', 'item': {'id': 'item_1', 'type': 'command_execution',
         'command': "cat input.json", 'aggregated_output': '{"synthetic":true,"sum":83}\n', 'exit_code': 0, 'status': 'completed'}},
        {'type': 'item.completed', 'item': {'id': 'item_2', 'type': 'agent_message', 'text': 'Synthetic sum 83'}},
        {'type': 'turn.completed', 'usage': {'input_tokens': 100, 'cached_input_tokens': 20,
         'cache_write_input_tokens': 0, 'output_tokens': 10, 'reasoning_output_tokens': 2}}]


def claude_rows(error=False):
    rows = [{'type': 'system', 'subtype': 'init', 'session_id': SESSION, 'tools': ['Read'], 'model': 'synthetic-model'}]
    if error:
        rows += [{'type': 'assistant', 'session_id': SESSION, 'error': 'authentication_failed', 'is_api_error_message': True,
          'message': {'id': 'synthetic-message', 'model': '<synthetic>', 'stop_reason': 'stop_sequence',
            'usage': {'input_tokens': 0, 'output_tokens': 0}, 'content': [{'type': 'text', 'text': 'Synthetic authentication error'}]}},
          {'type': 'result', 'subtype': 'success', 'session_id': SESSION, 'is_error': True, 'terminal_reason': 'api_error',
           'usage': {'input_tokens': 0, 'output_tokens': 0}, 'duration_api_ms': 0}]
    else:
        rows += [{'type': 'assistant', 'session_id': SESSION, 'message': {'id': 'synthetic-message', 'model': 'synthetic-model',
          'stop_reason': None, 'usage': {'input_tokens': 2, 'output_tokens': 1},
          'content': [{'type': 'tool_use', 'id': 'call-1', 'name': 'Read', 'input': {'file_path': 'input.json'}}]}},
          {'type': 'user', 'session_id': SESSION, 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'call-1',
          'content': '{"synthetic":true,"sum":83}', 'is_error': False}]}},
          {'type': 'result', 'subtype': 'success', 'session_id': SESSION, 'is_error': False,
           'terminal_reason': 'stop_hook_prevented', 'stop_reason': 'end_turn', 'usage': {'input_tokens': 2, 'output_tokens': 10}}]
    return rows


def raw_record(sequence, payload_type, payload):
    return {'schema_version': 1, 'payload_schema_version': 1, 'id': f'record-{sequence}',
            'stream': {'kind': 'session', 'id': SESSION}, 'sequence': sequence,
            'payload_type': payload_type, 'payload': payload}


def muse_rows():
    children = [raw_record(1, 'runtime.session.permission_format_declared', {'schema_version': 1}),
      raw_record(2, 'runtime.session.permission_profile_committed', {'schema_version': 1, 'permission_epoch': 1,
        'resolved_snapshot': {'filesystem': {'mode': 'managed'}, 'local_command_network': {'mode': 'restricted'},
                              'approval': 'on_request', 'reviewer': 'human'}})]
    rows = [{'retained_frame': 'session_permission_transaction', 'frame_schema_version': 1, 'outer_log_ordinal': 1,
             'transaction_id': 'transaction-1', 'children': [{'child_index': i, 'record_json': json.dumps(row)}
              for i, row in enumerate(children)], 'content_sha256': 'sha256:' + '0' * 64}]
    rows.append(raw_record(3, 'runtime.session.metadata', {'kind': 'metadata', 'record': {'model': 'synthetic-model'}}))
    events = [
      {'kind': 'model_completed', 'model_call_index': 0, 'usage': {'input_tokens': 100, 'output_tokens': 10, 'cached_tokens': 20}},
      {'kind': 'assistant_tool_calls_committed', 'message_id': 'message-1', 'response_id': 'response-1',
       'tool_calls': [{'id': 'fc-1', 'call_id': 'call-1', 'name': 'read_file', 'args': '{"path":"input.json"}'}]},
      {'kind': 'tool_result_batch_committed', 'batch_id': 'batch-1', 'results': [
       {'tool_call_index': 0, 'tool_call_id': 'call-1', 'text': '{"synthetic":true,"sum":83}'}]},
      {'kind': 'terminal', 'terminal': 'completed', 'reason': None}]
    for seq, event in enumerate(events, 4):
        rows.append(raw_record(seq, 'runtime.session', {'kind': 'run', 'run_id': 'run-1', 'event': event}))
    return rows


def binding(client, dialect):
    return {'producer': PRODUCERS[client], 'dialect': dialect, 'mode': 'synthetic', 'invocation_id': 'invocation-1'}


def test_exec_json_is_separate_supported_dialect():
    b = binding('codex', 'codex.exec_json')
    facts = [fact for row in exec_rows() for fact in codex.decode_wire(row, b)]
    assert [f['kind'] for f in facts].count('tool.call') == 1
    assert [f['kind'] for f in facts].count('tool.result') == 1
    result = next(f for f in facts if f['kind'] == 'tool.result')
    assert result['data']['output']['exit_code'] == 0
    assert all(f['authentication'] == 'owner_admission_required' for f in facts)
    usage = next(f for f in facts if f['kind'] == 'usage.snapshot')['data']
    assert usage['aggregation'] == 'turn_aggregate' and usage['countable'] is False
    assert usage['response_id'] is None


def test_client_generated_error_cannot_settle_provider_usage():
    facts = [f for row in claude_rows(True) for f in claude.decode_wire(row, binding('claude', 'claude.print_stream'))]
    assert any(f['kind'] == 'runtime.error' and f['data']['error'] == 'authentication_failed' for f in facts)
    assert all(f['data']['countable'] is False for f in facts if f['kind'] == 'usage.snapshot')
    terminal = next(f for f in facts if f['kind'] == 'lifecycle.completed')
    assert terminal['status'] == 'failed' and terminal['data']['terminal_reason'] == 'api_error'


def test_claude_stop_hook_reason_and_provisional_usage_remain_explicit():
    facts = [f for row in claude_rows() for f in claude.decode_wire(row, binding('claude', 'claude.print_stream'))]
    assert next(f for f in facts if f['kind'] == 'lifecycle.completed')['data']['terminal_reason'] == 'stop_hook_prevented'
    assert all(not f['data']['countable'] for f in facts if f['kind'] == 'usage.snapshot')


def test_muse_metadata_page_is_covered_without_authority():
    b = {**binding('muse', 'muse.msp'), 'schema_fingerprint': muse.STABLE_FINGERPRINT, 'experimental_api': False,
         'pending_request': {'id': 7, 'method': 'view/page', 'params': {'sessionId': SESSION, 'limit': 10}}}
    message = {'jsonrpc': '2.0', 'id': 7, 'result': {'events': [{'method': 'session/nameChanged', 'params': {
        'sessionId': SESSION, 'name': 'Synthetic session', 'viewCursor': 'opaque-1',
        'sourceRange': {'stream': {'kind': 'session', 'id': SESSION}, 'first': {'id': 'record-1', 'sequence': 1}, 'last': {'id': 'record-1', 'sequence': 1}}}}],
        'nextCursor': None}}
    facts = muse.decode_wire(message, b)
    assert [f['kind'] for f in facts] == ['coverage.page', 'session.metadata']
    assert facts[1]['data']['grants_authority'] is False


@pytest.mark.parametrize('client,dialect,rows', [('codex','codex.exec_json',exec_rows),
     ('claude','claude.print_stream',claude_rows), ('muse',None,muse_rows)])
def test_file_reader_rederives_transport_dialects_and_current_bytes(tmp_path, client, dialect, rows):
    path = tmp_path / 'source.jsonl'
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows()))
    source, cursor = native.enroll_source(path, client=client, expected_root_session_id=SESSION, dialect=dialect,
                                        source_handle='fixture', mode='synthetic')
    batch = native.read_page(source, cursor)
    assert not batch['gaps'], batch['gaps']
    assert not batch['diagnostics'], batch['diagnostics']
    assert any(f['kind'] == 'tool.result' for f in batch['events'])
    selected = [f for f in batch['events'] if f['kind'] in {'tool.call','tool.result'}]
    actual = native.revalidate_observations(source, selected, required_interval=[0,path.stat().st_size])
    assert actual['status'] == 'current', actual
    path.write_bytes(path.read_bytes().replace(b'83',b'84'))
    assert native.revalidate_observations(source, selected)['status'] == 'invalid'

# Real owner/CAS/PM + real isolated local subprocess. This is synthetic wire
# execution, never a claim that a provider or native permission boundary passed.
from test_run_state import engine, world, command  # noqa: E402,F401


def owned_worker(world, monkeypatch, client):
    import delegation_boundary as boundary
    from test_workflow import _policy_owner, _owner_register
    from datetime import datetime, timezone, timedelta
    from evaluation_artifacts import _sandbox_command
    runtime, state = _policy_owner(world)
    state = command(runtime, world, state, 'workflow.budget', {'limits': {
        'wall_millis': {'limit': 60000, 'enforcement': 'hard'},
        'usd_micros': {'limit': 2000000, 'enforcement': 'forecast'}},
        'deadline': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()})
    for identity, category, amount in [('worker-budget', 'work', 30000), ('audit-budget', 'integration', 10000),
                                      ('verification-budget', 'verification', 10000), ('recovery-budget', 'recovery', 10000)]:
        state = command(runtime, world, state, 'workflow.reserve', {'reservation_id': identity,
            'amounts': {'wall_millis': amount, 'usd_micros': 100000}, 'category': category})
    root = world['project'] / 'delegated'
    for sub in ('output','scratch'): (root / sub).mkdir(parents=True)
    brief = {'child_id': 'worker-one', 'task_id': 'work', 'deliverables': ['Read explicit synthetic fixture bytes'],
        'paths': [str(root)], 'criteria': ['accept'], 'reservation_id': 'worker-budget', 'integration_reservation_id': 'audit-budget',
        'verification_reservation_id': 'verification-budget', 'recovery_reservation_id': 'recovery-budget',
        'integration_owner': state['owner']['session_uuid'], 'return_contract': ['artifact_ids','evidence_ids','disposition'],
        'cancellation': 'Retain partial observations', 'mode': 'native-cli', 'client': client,
        'required_capabilities': ['read'], 'file_contract': {'schema_version': 1, 'immutable_inputs': [],
        'output_roots': [str(root / 'output')], 'scratch_root': str(root / 'scratch')}, 'admission_id': 'parent',
        'admission_requests': [{'id': 'parent', 'actor': world['actor'], 'paths': [str(root)]}]}
    state = command(runtime, world, state, 'workflow.dispatch', brief)
    # A reachable outer listener is the positive control: a refused connection
    # to an arbitrary closed port cannot prove network isolation. Linux bwrap
    # uses a separate network namespace; macOS denies the connect syscall.
    import socket
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(2)
        address = listener.getsockname()
        with socket.create_connection(address, timeout=1):
            connection, _ = listener.accept()
            connection.close()
        rows = exec_rows() if client == 'codex' else claude_rows()
        emitter = root / 'fixture-cli.py'
        emitter.write_text('import sys,json,errno,socket\nfrom pathlib import Path\nsys.stdin.read()\n'
            + 'try:\n Path(' + repr(str(world['project']/'forbidden-fixture-write')) + ').write_text("must not write")\n raise RuntimeError("sandbox allowed protected write")\n'
            + 'except OSError as exc:\n assert exc.errno in (errno.EPERM,errno.EACCES,errno.EROFS), str(exc)\n'
            + 'sock=socket.socket();sock.settimeout(1)\ntry:\n sock.connect(' + repr(address) + ')\n raise RuntimeError("sandbox allowed network")\n'
            + 'except OSError as exc:\n assert exc.errno in (errno.EPERM,errno.EACCES,errno.ENETUNREACH,errno.EHOSTUNREACH,errno.ECONNREFUSED), str(exc)\nfinally: sock.close()\n'
            + 'print("SYNTHETIC_OS_SANDBOX_DENIED",file=sys.stderr)\nrows=' + repr(rows) + '\nfor row in rows: print(json.dumps(row))\n')
        # The substitution selects a wholly synthetic local executable; admission,
        # manifest custody, receipt acceptance, journal and source reads stay real.
        import sys
        monkeypatch.setattr(boundary, 'client_selection', lambda client, env: ({}, sys.executable))
        def isolated_argv(client, executable, contract, selection):
            return _sandbox_command(world['project'], Path(contract['scratch_root']), emitter, [])[0] + ['-p']
        monkeypatch.setattr(boundary, 'native_argv', isolated_argv)
        # Native initialization explicitly does not claim host enforcement.
        state = _owner_register(runtime, world, state, 'worker-spec', {'schema_version': 1,
            'kind': 'native_worker', 'arguments': {'child_id': 'worker-one', 'timeout_seconds': 10}})
        state = runtime.observe(world['project'], state['run_id'], 'native_worker', {'check_id': 'worker-spec'},
            expected_revision=state['revision'], command_id='worker-executed', actor=world['actor'], runtime_root=world['runtime'])
        state = command(runtime, world, state, 'workflow.worker_record', {'child_id': 'worker-one', 'receipt_id': 'worker-executed'})
        return runtime, state


@pytest.mark.parametrize('client', ['codex','claude'])
def test_real_owner_worker_transport_custody(world, monkeypatch, client):
    import observation_bridge as bridge
    runtime, state = owned_worker(world, monkeypatch, client)
    child = state['extensions']['workflow']['children']['worker-one']
    assert child['worker_observation']['boundary']['status'] == 'UNKNOWN'
    receipt=Path(child['worker_observation']['receipt_path'])
    assert 'SYNTHETIC_OS_SANDBOX_DENIED' in (receipt.parent/'stderr.txt').read_text()
    assert not (world['project']/'forbidden-fixture-write').exists()
    state = command(runtime, world, state, 'native.enroll', {'source_handle': 'worker:worker-one', 'mode': 'synthetic'})
    state = command(runtime, world, state, 'native.observe', {'source_handle': 'worker:worker-one', 'through_event': None,
        'task_id': 'work', 'attempt_id': None})
    batch = state['extensions']['native_observations']['latest_batch']
    assert not batch['gaps'], batch['gaps']
    assert {e['task_id'] for e in batch['events']} == {'work'}
    ids = [e['event_id'] for e in batch['events'] if e['kind'] in {'tool.call','tool.result'}]
    assert len(ids) == 2
    checked = runtime.inspect_context(state, world['actor'])['current_native_events'](ids)
    assert checked['status'] == 'current', checked
    source = Path(state['extensions']['native_observations']['sources']['worker:worker-one']['binding']['path'])
    before = runtime.load_run(world['project'], state['run_id'])
    source.write_bytes(source.read_bytes().replace(b'83', b'84'))
    with pytest.raises(ValueError):
        command(runtime, world, state, 'native.observe', {'source_handle': 'worker:worker-one', 'through_event': None,
            'task_id': 'work', 'attempt_id': None})
    assert runtime.load_run(world['project'], state['run_id']) == before

@pytest.mark.parametrize('client,rows,dialect', [('codex',exec_rows,'codex.exec_json'),('claude',claude_rows,'claude.print_stream')])
@pytest.mark.parametrize('fault', ['foreign-session','duplicate-start','duplicate-terminal','post-terminal-tool','partial-tail','unknown-event'])
def test_transport_state_and_identity_gaps_are_not_silent(tmp_path, client, rows, dialect, fault):
    records = rows()
    if fault == 'foreign-session':
        records.insert(2, {'type':'thread.started','thread_id':'foreign'} if client=='codex' else
                       {'type':'system','subtype':'init','session_id':'foreign'})
    if fault == 'duplicate-start': records.insert(1, deepcopy(records[0]))
    if fault == 'duplicate-terminal': records.append(deepcopy(records[-1]))
    if fault == 'post-terminal-tool': records.append(deepcopy(records[2 if client=='codex' else 1]))
    if fault == 'unknown-event': records.insert(2, {'type':'unqualified-record','session_id':SESSION})
    path=tmp_path/'stream.jsonl'; path.write_text(''.join(json.dumps(row)+'\n' for row in records))
    if fault == 'partial-tail':
        with path.open('a') as f:f.write('{"type":"unfinished')
    b,c=native.enroll_source(path,client=client,expected_root_session_id=SESSION,dialect=dialect)
    batch=native.read_page(b,c)
    if fault=='partial-tail': assert batch['coverage']['pending_bytes']>0
    else: assert batch['gaps']
    verdict=native.revalidate_observations(b,[],required_interval=[0,path.stat().st_size])
    assert verdict['status']=='invalid' and verdict['negative_coverage']=='UNKNOWN'


@pytest.mark.parametrize('fault',['sequence-gap','reversed','cross-session','retained-child-index','retained-child-order','malformed-child'])
def test_muse_raw_sequence_and_retained_frame_invariants(tmp_path,fault):
    records=muse_rows()
    if fault=='sequence-gap': records[4]['sequence']+=10
    if fault=='reversed':records[-1]['sequence']=1
    if fault=='cross-session':records[-1]['stream']['id']='foreign'
    if fault=='retained-child-index':records[0]['children'][1]['child_index']=0
    if fault=='retained-child-order':records[0]['children'].reverse()
    if fault=='malformed-child':records[0]['children'][0]['record_json']='{"bad":'
    path=tmp_path/'muse.jsonl';path.write_text(''.join(json.dumps(row)+'\n' for row in records))
    if fault.startswith('retained') or fault=='malformed-child':
        with pytest.raises(ValueError):native.enroll_source(path,client='muse',expected_root_session_id=SESSION)
        return
    b,c=native.enroll_source(path,client='muse',expected_root_session_id=SESSION)
    assert native.read_page(b,c)['gaps']
    assert native.revalidate_observations(b,[],required_interval=[0,path.stat().st_size])['status']=='invalid'


def page_fixture(tmp_path):
    rows=muse_rows()
    rows[2]['payload']['event']['usage']={'input_tokens':100,'output_tokens':10,'cached_tokens':20,
        'cache_write_tokens':0,'cache_read_tokens':20,'reasoning_tokens':2}
    path=tmp_path/'muse-page-source.jsonl'; offset=0; locators={}
    with path.open('wb') as f:
        for row in rows:
            raw=(json.dumps(row)+'\n').encode();f.write(raw)
            if row.get('id'):locators[row['id']]={'offset':offset,'length':len(raw),'sha256':native._sha(raw)}
            offset+=len(raw)
    b,c=native.enroll_source(path,client='muse',expected_root_session_id=SESSION)
    span={'stream':{'kind':'session','id':SESSION},'first':{'id':'record-4','sequence':4},'last':{'id':'record-4','sequence':4}}
    params={'sessionId':SESSION,'turnId':'synthetic-turn','viewCursor':'opaque:response', 'sourceRange':span,
      'promptTokens':100,'totalTokens':110,'usage':{'inputTokens':100,'outputTokens':10,'cachedTokens':20,
      'cacheWriteTokens':0,'cacheReadTokens':20,'reasoningTokens':2},
      'cumulative':{'promptTokens':100,'outputTokens':10,'totalTokens':110}}
    page={'jsonrpc':'2.0','id':7,'result':{'events':[{'method':'session/tokenUsage','params':params}], 'nextCursor':None}}
    wire={**binding('muse','muse.msp'),'schema_fingerprint':muse.STABLE_FINGERPRINT,'experimental_api':False,
      'pending_request':{'id':7,'method':'view/page','params':{'sessionId':SESSION,'limit':10}}}
    return path,b,c,page,wire,locators


@pytest.mark.parametrize('fault',[None,'wrong-endpoint','changed-counters','changed-cache','cross-session','stale-request','experimental','duplicate-cursor','reversed-range','tamper'])
def test_muse_page_exact_current_range_join(tmp_path,fault):
    path,b,c,page,wire,locators=page_fixture(tmp_path)
    params=page['result']['events'][0]['params']
    if fault=='wrong-endpoint':params['sourceRange']['last']['id']='invented'
    if fault=='changed-counters':params['usage']['outputTokens']=11;params['totalTokens']=111
    if fault=='changed-cache':params['usage']['cachedTokens']=21
    if fault=='cross-session':params['sourceRange']['stream']['id']='foreign'
    if fault=='stale-request':wire['pending_request']['id']='7'
    if fault=='experimental':wire['experimental_api']=True
    if fault=='duplicate-cursor':page['result']['events']*=2
    if fault=='reversed-range':params['sourceRange']['first']['sequence']=5
    if fault=='tamper':path.write_bytes(path.read_bytes().replace(b'100',b'101'))
    if fault:
        with pytest.raises(ValueError):native.revalidate_muse_page(b,page,wire,locators)
        return
    result=native.revalidate_muse_page(b,page,wire,locators)
    assert result['status']=='current' and result['wire_authentication']=='UNKNOWN'
    assert result['negative_coverage']=='UNKNOWN' and not result['authority_granted']
    assert result['range_joins'][0]['semantic_match']=='CURRENT_RESPONSE_COUNTERS'
    raw_usage=next(e for e in result['raw_events'] if e['kind']=='usage.snapshot')
    wire_usage=muse.decode_wire(page,wire)[1]
    assert raw_usage['data']['measurement_id']==wire_usage['data']['measurement_id']
    assert raw_usage['data']['counters_digest']==wire_usage['data']['counters_digest']


def test_muse_large_nonmaterial_trace_is_streamed_with_identity_and_sequence(tmp_path):
    rows=muse_rows();rows.insert(2,raw_record(4,'runtime.session',{'kind':'run','run_id':'run-1',
        'event':{'kind':'model_input_trace_recorded','text':'x'*(2*1024*1024)}}))
    for row in rows[3:]:row['sequence']+=1
    path=tmp_path/'large.jsonl';path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    b,c=native.enroll_source(path,client='muse',expected_root_session_id=SESSION)
    pages=0
    while c['offset']<path.stat().st_size:
        batch=native.read_page(b,c,limits=native.Limits(page_bytes=65536,payload_bytes=4096))
        assert not batch['gaps'],batch['gaps']
        assert len(json.dumps(batch['cursor']))<65536
        assert batch['cursor']['offset']>c['offset']
        c=batch['cursor'];pages+=1
        assert pages<40
    assert c['last_sequence']==8 and pages>20


def test_worker_generated_auth_error_usage_remains_unknown():
    import delegation_boundary
    rows=claude_rows(True)
    result=delegation_boundary.parse_worker('claude', ''.join(json.dumps(r)+'\n' for r in rows).encode())
    assert result['terminal']=='failed' and result['usage']=={'tokens':None,'usd_micros':None}


def test_actual_muse_owner_page_commits_raw_cursor_only(world, monkeypatch, tmp_path):
    from test_workflow import _policy_owner
    fixture,b,c,page,wire,locators=page_fixture(tmp_path)
    root=world['scratch']/'muse-sessions'
    target=root/'2026'/'01'/'01'/SESSION/'session.jsonl';target.parent.mkdir(parents=True)
    lines=fixture.read_bytes().splitlines(keepends=True)
    target.write_bytes(b''.join(lines[:2]))
    world['transcript']=target
    world['actor']['native_payload'].pop('transcript_path')
    prior=world['actor']['native_payload']['session_id']
    world['actor']['native_payload']['session_id']=SESSION
    monkeypatch.setenv('MUSE_SESSIONS_DIR',str(root))
    monkeypatch.setenv('SYNTHESIS_CLIENT_SESSION_REF','muse:'+SESSION)
    monkeypatch.setenv('MUSE_SESSION_ID',SESSION)
    world['board'].write_text(world['board'].read_text().replace('| claude |','| muse |').replace('cc:'+prior,'muse:'+SESSION))
    runtime,state=_policy_owner(world)
    with target.open('ab') as stream:stream.write(b''.join(lines[2:]))
    # Lookup inventory includes only requested endpoint records in admitted scope.
    locators={'record-4':locators['record-4']}
    payload={'source_handle':'root','message':page,'connection_binding':wire,'locators':locators,
             'task_id':None,'attempt_id':None}
    old=deepcopy(state)
    state=command(runtime,world,state,'native.page',payload,command_id='page-1')
    ext=state['extensions']['native_observations'];batch=ext['latest_batch']
    assert not batch['gaps'] and not batch['diagnostics']
    assert ext['sources']['root']['cursor']['offset']==target.stat().st_size
    assert batch['page_reconciliation']['wire_authentication']=='UNKNOWN'
    assert all('view_cursor' not in event['native'] or event['native']['view_cursor'] is None for event in batch['events'])
    ids=[e['event_id'] for e in batch['events'] if e['kind'] in {'tool.call','tool.result'}]
    assert runtime.inspect_context(state,world['actor'])['current_native_events'](ids)['status']=='current'
    assert command(runtime,world,old,'native.page',payload,command_id='page-1')==state
    with pytest.raises(ValueError):command(runtime,world,old,'native.page',payload,command_id='stale-page')
    assert runtime.load_run(world['project'],state['run_id'])==state

@pytest.mark.parametrize('fault',['wrong-task','claimed-native-mode','forged-worker-receipt','interrupted-commit','rotated-stream','changed-launch'])
def test_owner_transport_refuses_custody_and_task_substitution(world,monkeypatch,fault):
    runtime,state=owned_worker(world,monkeypatch,'codex')
    payload={'source_handle':'worker:worker-one','through_event':None,'task_id':'work','attempt_id':None}
    if fault=='claimed-native-mode':
        with pytest.raises(ValueError):command(runtime,world,state,'native.enroll',{'source_handle':'worker:worker-one','mode':'native'})
        return
    child=state['extensions']['workflow']['children']['worker-one']
    receipt=Path(child['worker_observation']['receipt_path'])
    if fault=='forged-worker-receipt':
        old=receipt.read_bytes();receipt.write_bytes(old.replace(b'worker-one',b'worker-two'))
    if fault=='changed-launch':
        p=receipt.parent/'launch.json';p.write_text(p.read_text()+' ')
    if fault in {'forged-worker-receipt','changed-launch'}:
        with pytest.raises(ValueError):command(runtime,world,state,'native.enroll',{'source_handle':'worker:worker-one','mode':'synthetic'})
        assert runtime.load_run(world['project'],state['run_id'])==state
        return
    state=command(runtime,world,state,'native.enroll',{'source_handle':'worker:worker-one','mode':'synthetic'})
    if fault=='wrong-task':payload['task_id']='foreign-task'
    if fault=='rotated-stream':
        p=receipt.parent/'stdout.jsonl';raw=p.read_bytes();p.rename(p.with_suffix('.retained'));p.write_bytes(raw)
    if fault=='interrupted-commit':
        append=runtime._append
        def interrupt(*a,**k):raise OSError('synthetic interrupted native batch commit')
        monkeypatch.setattr(runtime,'_append',interrupt)
        with pytest.raises(OSError):command(runtime,world,state,'native.observe',payload,command_id='capture-once')
        assert runtime.load_run(world['project'],state['run_id'])==state
        monkeypatch.setattr(runtime,'_append',append)
        completed=command(runtime,world,state,'native.observe',payload,command_id='capture-once')
        assert completed['extensions']['native_observations']['latest_batch']['events']
        assert command(runtime,world,state,'native.observe',payload,command_id='capture-once')==completed
    elif fault=='rotated-stream':
        observed=command(runtime,world,state,'native.observe',payload)
        batch=observed['extensions']['native_observations']['latest_batch']
        assert not batch['events'] and batch['diagnostics']
        assert batch['cursor']==state['extensions']['native_observations']['sources']['worker:worker-one']['cursor']
    else:
        with pytest.raises(ValueError):command(runtime,world,state,'native.observe',payload)
        assert runtime.load_run(world['project'],state['run_id'])==state


def test_print_permission_refusal_uses_typed_error_flag_only():
    row=claude_rows()[2]
    row['message']['content'][0].update(content='Synthetic denied tool',is_error=True)
    fact=claude.decode_wire(row,binding('claude','claude.print_stream'))[0]
    assert fact['kind']=='tool.result' and fact['status']=='failed'
    assert fact['data']['is_error'] is True
    row['message']['content'][0]['is_error']='true'
    with pytest.raises(ValueError):claude.decode_wire(row,binding('claude','claude.print_stream'))


def test_exec_permission_text_without_structured_exit_remains_gap(tmp_path):
    rows=exec_rows();rows[3]['item'].update(status='failed',exit_code=None,aggregated_output='Permission denied')
    path=tmp_path/'error.jsonl';path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    b,c=native.enroll_source(path,client='codex',expected_root_session_id=SESSION,dialect='codex.exec_json')
    batch=native.read_page(b,c)
    assert batch['gaps'] and not any(e['kind']=='tool.result' for e in batch['events'])


def test_muse_v2_agent_tree_is_explicit_and_cannot_change_root():
    row=raw_record(4,'runtime.session',{'kind':'agent_tree_initialized','record':{'schema_version':1,
        'writer_protocol':1,'root_agent_id':SESSION,'root_session_id':SESSION,'execution_capacity':2}})
    row['payload_schema_version']=2
    fact=muse.decode_record(row,PRODUCERS['muse'])[0]
    assert fact['kind']=='session.metadata' and not fact['data']['grants_authority']
    row['payload']['record']['root_agent_id']='foreign'
    with pytest.raises(ValueError):muse.decode_record(row,PRODUCERS['muse'])
    row['payload_schema_version']=3
    with pytest.raises(ValueError):muse.decode_record(row,PRODUCERS['muse'])


def test_claude_informational_and_capacity_records_do_not_grant_authority():
    rows=[{'type':'system','subtype':'informational','session_id':SESSION,'content':'Synthetic stop notice','level':'notice'},
          {'type':'rate_limit_event','session_id':SESSION,'rate_limit_info':{'status':'allowed_warning','utilization':0.75}}]
    facts=[claude.decode_wire(row,binding('claude','claude.print_stream'))[0] for row in rows]
    assert [f['kind'] for f in facts]==['runtime.notice','capacity.snapshot']
    assert all(not f['data']['grants_authority'] for f in facts)
    assert facts[1]['data']['usage_semantics']=='account_limit_not_expenditure'


@pytest.mark.parametrize('kind', [None, [], 'unknown-material', 'task'])
def test_unknown_session_kind_cannot_inherit_nonmaterial_run_grammar(tmp_path, kind):
    rows = [raw_record(1, 'runtime.session.metadata', {'kind': 'metadata'}),
            raw_record(2, 'runtime.session', {'kind': kind, 'event': {'kind': 'reasoning_committed'}})]
    path = tmp_path / 'malformed.jsonl'
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    b, c = native.enroll_source(path, client='muse', expected_root_session_id=SESSION)
    result = native.read_page(b, c)
    assert result['gaps'] and result['cursor']['trusted_through'] < path.stat().st_size
    current = native.revalidate_observations(b, [], required_interval=[0, path.stat().st_size])
    assert current['status'] == 'invalid' and current['negative_coverage'] == 'UNKNOWN'


@pytest.mark.parametrize('value', [None, [], True, 2, 'text'])
@pytest.mark.parametrize('shape', ['retained-child', 'v2-payload'])
def test_malformed_muse_nested_objects_are_bounded_source_gaps(tmp_path, value, shape):
    if shape == 'retained-child':
        row = {'retained_frame': 'session_permission_transaction', 'frame_schema_version': 1,
               'children': [{'child_index': i, 'record_json': json.dumps(value)} for i in range(2)]}
    else:
        row = raw_record(2, 'runtime.session', value)
        row['payload_schema_version'] = 2
    path = tmp_path / 'malformed.jsonl'
    path.write_text(json.dumps(raw_record(1, 'runtime.session.metadata', {})) + '\n' + json.dumps(row) + '\n')
    b, c = native.enroll_source(path, client='muse', expected_root_session_id=SESSION)
    result = native.read_page(b, c)
    assert result['gaps'] and result['cursor']['trusted_through'] < path.stat().st_size


@pytest.mark.parametrize('value', [None, [], True, 2, 'text'])
def test_exec_non_item_event_rejects_malformed_item(value):
    with pytest.raises(codex.DialectError):
        codex.decode_wire({'type': 'turn.started', 'item': value}, binding('codex', 'codex.exec_json'))


@pytest.mark.parametrize('value', [None, [], True, 2, 'text'])
def test_claude_worker_rejects_malformed_assistant_from_captured_bytes(value):
    import delegation_boundary as workers
    rows = claude_rows()
    rows[1]['message'] = value
    raw = ''.join(json.dumps(row) + '\n' for row in rows).encode()
    with pytest.raises(ValueError, match='assistant message must be an object'):
        workers.parse_worker('claude', raw)


def test_worker_requires_captured_bytes_and_does_not_treat_system_text_as_assistant():
    import delegation_boundary as workers
    rows = claude_rows()
    rows.insert(1, {'type': 'system', 'subtype': 'hook_response', 'message': 'Synthetic informational text'})
    text = ''.join(json.dumps(row) + '\n' for row in rows)
    with pytest.raises(ValueError, match='captured bytes'):
        workers.parse_worker('claude', text)
    assert workers.parse_worker('claude', text.encode())['usage']['tokens'] == 12


def test_page_corroboration_deduplicates_only_within_each_current_read(tmp_path, monkeypatch):
    rows = [raw_record(1, 'runtime.session.metadata', {}),
            raw_record(2, 'runtime.session.metadata', {'detail': 'x' * 8192})]
    path = tmp_path / 'page.jsonl'
    lines = [(json.dumps(row) + '\n').encode() for row in rows]
    path.write_bytes(b''.join(lines))
    b, _ = native.enroll_source(path, client='muse', expected_root_session_id=SESSION)
    span = {'stream': rows[1]['stream'], 'first': {'id': 'record-2', 'sequence': 2},
            'last': {'id': 'record-2', 'sequence': 2}}
    message = {'jsonrpc': '2.0', 'id': 7, 'result': {'events': [
        {'method': 'session/nameChanged', 'params': {'sessionId': SESSION, 'name': 'Synthetic',
         'viewCursor': f'cursor-{i}', 'sourceRange': span}} for i in range(32)], 'nextCursor': None}}
    wire = {**binding('muse', 'muse.msp'), 'schema_fingerprint': muse.STABLE_FINGERPRINT,
            'experimental_api': False, 'pending_request': {'id': 7, 'method': 'view/page',
            'params': {'sessionId': SESSION, 'limit': 32}}}
    locators = {'record-2': {'offset': len(lines[0]), 'length': len(lines[1]), 'sha256': native._sha(lines[1])}}
    reads, original = [], native._stable_read
    def counted(*args, **kwargs):
        reads.append(2 * args[3]); return original(*args, **kwargs)
    monkeypatch.setattr(native, '_stable_read', counted)
    result = native.revalidate_muse_page(b, message, wire, locators, max_bytes=32768)
    assert result['status'] == 'current'
    assert sum(reads) <= result['physical_read_bound'] <= 2 * 32768 + 1
    assert len(reads) == 3  # header, interval and one unique endpoint
    assert result['negative_coverage'] == 'UNKNOWN' and result['wire_authentication'] == 'UNKNOWN'
    path.write_bytes(lines[0] + lines[1].replace(b'xxxxxxxx', b'yyyyyyyy'))
    reads.clear()
    with pytest.raises(ValueError, match='endpoint differs'):
        native.revalidate_muse_page(b, message, wire, locators, max_bytes=32768)
    assert reads, 'the second call must reopen current source bytes'


def test_distinct_page_ranges_charge_each_header_and_endpoint_before_reading(tmp_path, monkeypatch):
    rows = [raw_record(i, 'runtime.session.metadata', {'detail': 'x' * 8192}) for i in range(1, 5)]
    lines = [(json.dumps(row) + '\n').encode() for row in rows]
    path = tmp_path / 'ranges.jsonl'; path.write_bytes(b''.join(lines))
    b, _ = native.enroll_source(path, client='muse', expected_root_session_id=SESSION)
    events, locators, offset = [], {}, 0
    for row, line in zip(rows, lines):
        locators[row['id']] = {'offset': offset, 'length': len(line), 'sha256': native._sha(line)}
        point = {'id': row['id'], 'sequence': row['sequence']}
        events.append({'method': 'session/nameChanged', 'params': {'sessionId': SESSION,
            'name': 'Synthetic', 'viewCursor': row['id'], 'sourceRange': {
            'stream': row['stream'], 'first': point, 'last': point}}})
        offset += len(line)
    wire = {**binding('muse', 'muse.msp'), 'schema_fingerprint': muse.STABLE_FINGERPRINT,
            'experimental_api': False, 'pending_request': {'id': 7, 'method': 'view/page',
            'params': {'sessionId': SESSION, 'limit': 4}}}
    message = {'jsonrpc': '2.0', 'id': 7, 'result': {'events': events, 'nextCursor': None}}
    reads, original = [], native._stable_read
    def counted(*args, **kwargs):
        reads.append(2 * args[3]); return original(*args, **kwargs)
    monkeypatch.setattr(native, '_stable_read', counted)
    with pytest.raises(ValueError, match='bounded current read'):
        native.revalidate_muse_page(b, message, wire, locators, max_bytes=32768)
    assert sum(reads) <= 2 * 32768
