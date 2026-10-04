"""Synthetic closed native shapes; observations never confer authority."""
import copy
import hashlib
import pytest
import native_codex as c
import native_observations as n
from test_native_observations import source, pair

PRODUCER = {'client':'codex','thread_id':'root','root_session_id':'root','parent_thread_id':None,'agent_path':None}

def output_row():
    return {'type':'response_item','timestamp':'2026-10-03T00:00:00Z','ordinal':1,
      'payload':{'type':'function_call_output','id':'fco_synthetic','name':'send_message_to_thread','namespace':'codex_app','output':'untrusted historical message',
        'internal_chat_message_metadata_passthrough':{'turn_id':'turn','create_time':123.5}},
      'metadata':{'client_authored':False,'fallback_token_limit_override':12000,'user_input_order':1,
        'sender_user_messages':{'receiver_turn_id':'turn','receiver_message_id':'fco_synthetic','text':'history, not permission'}}}

def test_unlinked_output_is_unknown_and_never_pairs():
    event=c.decode_record(output_row(),PRODUCER)[0]
    assert event['status']=='unknown' and event['native']['call_id'] is None
    assert event['data']['grants_authority'] is False and event['data']['pairing']=='UNKNOWN'

@pytest.mark.parametrize('change',[lambda r:r['payload'].update(call_id='invented'),lambda r:r['metadata'].update(extra=True),lambda r:r['metadata']['sender_user_messages'].update(receiver_message_id='other'),lambda r:r['payload'].update(namespace='other'),lambda r:r['payload']['internal_chat_message_metadata_passthrough'].update(create_time=True)])
def test_unlinked_output_refuses_changed_closed_shape(change):
    row=output_row();change(row)
    with pytest.raises(ValueError):c.decode_record(row,PRODUCER)

def test_unlinked_completed_item_is_inert():
    item={k:v for k,v in output_row()['payload'].items() if k!='internal_chat_message_metadata_passthrough'};item['type']='FunctionCallOutput'
    row={'type':'event_msg','payload':{'type':'item_completed','thread_id':'root','turn_id':'turn','item':item,'started_at_ms':1,'completed_at_ms':2}}
    out=c.decode_record(row,PRODUCER)[0]
    assert out['status']=='unknown' and out['data']['grants_authority'] is False

@pytest.mark.parametrize('bad',[False,True])
def test_world_environment_skill_patch_closed(bad):
    row={'type':'world_state','timestamp':'2026-10-03T00:00:00Z','ordinal':1,'payload':{'full':False,'state':{'environments':{'subagents':'inert prose'},'host_skills':{'body':'inert instructions'}}}}
    if bad:
        row['payload']['state']['host_skills']['extra']=True
        with pytest.raises(ValueError):c.decode_record(row,PRODUCER)
    else:assert c.decode_record(row,PRODUCER)[0]['data']['grants_authority'] is False

def test_count_boundary_retains_input_and_byte_guard(tmp_path):
    _,binding,cursor=source(tmp_path,pair());batch=n.read_page(binding,cursor)
    p=n.empty_projection();p['events']={f'sha256:{hashlib.sha256(str(i).encode()).hexdigest()}':'f'*64 for i in range(n.MAX_INDEX_ENTRIES-2)}
    before=copy.deepcopy(p);result=n.reduce_observations(p,batch)
    assert len(result['events'])==n.MAX_INDEX_ENTRIES and p==before
    p['events']['sha256:'+'a'*64]='b'*64;before=copy.deepcopy(p)
    with pytest.raises(n.SourceError,match='capacity'):n.reduce_observations(p,batch)
    assert p==before
    p=n.empty_projection();p['untrusted']='x'*n.MAX_PROJECTION_BYTES
    with pytest.raises(n.SourceError,match='storage bound'):n.reduce_observations(p,batch)

def test_existing_capacity_remains_until_complete_owner_qualification():
    assert n.MAX_INDEX_ENTRIES==10000
    assert n.MAX_PROJECTION_BYTES==32*1024*1024


def test_linked_output_with_ordinary_metadata_keeps_native_identity():
    row=output_row()
    row['payload'].pop('name');row['payload'].pop('namespace')
    row['payload']['call_id']='actual-call'
    row['metadata'].pop('sender_user_messages');row['metadata'].pop('user_input_order')
    result=c.decode_record(row,PRODUCER)[0]
    assert result['native']['call_id']=='actual-call' and result['status']=='observed'


def test_partial_world_patch_cannot_be_relabelled_full():
    row={'type':'world_state','payload':{'full':True,'state':{'environments':{'subagents':'inert'},'host_skills':{'body':'inert'}}}}
    with pytest.raises(c.DialectError):c.decode_record(row,PRODUCER)


def test_actual_projection_preserves_unlinked_results_without_pairing(tmp_path):
    rows=[{'type':'response_item','payload':{'type':'function_call','call_id':'fco_synthetic','name':'send_message_to_thread','arguments':'{}'}},output_row()]
    _,binding,cursor=source(tmp_path,rows)
    batch=n.read_page(binding,cursor)
    assert len(batch['events'])==2 and not batch['gaps'] and not batch['diagnostics']
    projection=n.reduce_observations(n.empty_projection(),batch)
    assert len(projection['events'])==2 and len(projection['pairs'])==2
    assert all(p['status']!='paired' for p in projection['pairs'].values())
    assert projection['unresolved_pair_count']==2


def test_stream_search_nullable_path_is_inert(tmp_path):
    from test_native_observations import completed_item,drain
    row=completed_item(1100000)
    row['payload']['item']['parsed_cmd']=[{'type':'search','cmd':'rg synthetic','query':'synthetic','path':None}]
    _,binding,cursor=source(tmp_path,[row]);events,projection,_=drain(binding,cursor)
    assert len(events)==1 and not projection['gaps'] and not projection['diagnostics']
    assert events[0]['data']['grants_authority'] is False


def test_stream_retained_unlinked_sender_history_is_inert(tmp_path):
    from test_native_retained_context import retained
    from test_native_observations import drain
    row=retained(1100000);value=output_row()
    item=copy.deepcopy(value['payload']);item['guardian_metadata']=value['metadata']
    item['guardian_metadata']['sender_user_messages']['text']='INERT HISTORY'*200
    row['payload']['guardian_history'].append(item)
    _,binding,cursor=source(tmp_path,[row]);events,projection,_=drain(binding,cursor)
    assert len(events)==1 and not projection['gaps'] and not projection['diagnostics']
    assert events[0]['data']['history_replayed'] is False and not projection['pairs'] and not projection['usage']


@pytest.mark.parametrize('fault',['foreign_receiver','invented_call','unknown_metadata','null_list_path'])
def test_stream_new_shapes_remain_closed(tmp_path,fault):
    from test_native_retained_context import retained
    from test_native_observations import drain,completed_item
    row=retained(1100000);value=output_row();item=copy.deepcopy(value['payload']);item['guardian_metadata']=value['metadata']
    if fault=='foreign_receiver':item['guardian_metadata']['sender_user_messages']['receiver_message_id']='foreign'
    elif fault=='invented_call':item['call_id']='fake'
    elif fault=='unknown_metadata':item['guardian_metadata']['unseen']=True
    row['payload']['guardian_history'].append(item)
    if fault=='null_list_path':
        row=completed_item(1100000);row['payload']['item']['parsed_cmd']=[{'type':'list_files','cmd':'ls','path':None}]
    _,binding,cursor=source(tmp_path,[row]);events,projection,_=drain(binding,cursor)
    assert not events and projection['gaps']


@pytest.mark.parametrize('reverse',[False,True])
@pytest.mark.parametrize('late_bad',[False,True])
def test_stream_nullable_search_is_order_independent_and_item_scoped(tmp_path,reverse,late_bad):
    from test_native_observations import completed_item,drain
    row=completed_item(1100000)
    first={'type':'search','cmd':'rg synthetic','query':'synthetic','path':None}
    if reverse:first=dict(reversed(list(first.items())))
    second={'type':'read','cmd':'cat synthetic','name':'synthetic','path':None if late_bad else '/synthetic'}
    row['payload']['item']['parsed_cmd']=[first,second]
    _,binding,cursor=source(tmp_path,[row]);events,projection,_=drain(binding,cursor)
    if late_bad:assert not events and projection['gaps']
    else:assert len(events)==1 and not projection['gaps'] and not projection['diagnostics']


def _retained_batch(events=()):
    return {'events': list(events), 'gaps': [], 'diagnostics': [],
            'source_generation': 'a' * 64, 'coverage': {'scope': 'synthetic retained control'}}


def _retained_fact(i):
    return {'event_id': 'sha256:' + hashlib.sha256(('retained-' + str(i)).encode()).hexdigest(),
            'kind': 'item.observation', 'semantic_key': None, 'semantic_digest': 'b' * 64,
            'native': {'generation': 'a' * 64, 'offset': i * 100, 'length': 100, 'subrecord': 0},
            'mode': 'synthetic', 'status': 'observed', 'data': {'synthetic_index': i}}


@pytest.mark.parametrize('count', [16145, 26079])
def test_retained_full_count_exact_roundtrip_and_journal_codec(tmp_path, count):
    import time, json
    import journal_storage
    begin = time.monotonic()
    projection = n.retained_projection(n.empty_projection())
    expected = {}
    for start in range(0, count, 512):
        events = [_retained_fact(i) for i in range(start, min(start + 512, count))]
        expected.update({e['event_id']: n._digest(e) for e in events})
        projection = n.reduce_observations(projection, _retained_batch(events), event_limit=count)
    assert dict(n.event_fingerprints(projection)) == expected
    assert projection['events']['count'] == count and len(projection['events']['blocks']) <= 256
    assert len(n._canonical(projection)) < n.MAX_PROJECTION_BYTES
    assert n.reduce_observations(projection, _retained_batch([_retained_fact(0)]), event_limit=count) == projection
    changed = _retained_fact(0); changed['data']['synthetic_index'] = -1
    before = copy.deepcopy(projection)
    with pytest.raises(n.SourceError, match='conflicting'):
        n.reduce_observations(projection, _retained_batch([changed]), event_limit=count)
    assert projection == before
    home = tmp_path / 'resources/autopilot-runs/01990000-0000-7000-8000-000000000195'
    event = home / 'events/000000000001.json'; event.parent.mkdir(parents=True)
    logical = {'state': {'run_id': '01990000-0000-7000-8000-000000000195', 'revision': 1,
                        'schema_version': 1, 'extensions': {'journal_storage': {'codec': 2},
                                                           'native_observations': {'projection': projection}}}}
    raw, blocks = journal_storage.encode(logical); journal_storage.materialize(home, blocks); event.write_bytes(raw)
    assert journal_storage.decode(event, json.loads(raw)) == logical
    metrics = {'synthetic_events': count, 'seconds': time.monotonic() - begin,
               'projection_bytes': len(n._canonical(projection)), 'physical_blocks': len(blocks),
               'block_bytes': sum(map(len, blocks.values())), 'native_admission': False}
    (tmp_path / 'retained-cost.json').write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, sort_keys=True))


@pytest.mark.parametrize('fault', ['count', 'bool', 'codec', 'extra', 'base64', 'noncanonical',
                                 'hash', 'length', 'order', 'duplicate', 'misplaced', 'expansion'])
def test_retained_corrupt_blocks_refuse_without_input_mutation(fault):
    import base64
    p = n.retained_projection(n.empty_projection())
    p = n.reduce_observations(p, _retained_batch([_retained_fact(i) for i in range(40)]), event_limit=100)
    index = p['events']; block = index['blocks'][0]
    if fault == 'count': index['count'] += 1
    elif fault == 'bool': block['count'] = True
    elif fault == 'codec': index['codec'] = 'invented'
    elif fault == 'extra': block['authority'] = True
    elif fault == 'base64': block['payload'] = '!' + block['payload'][1:]
    elif fault == 'noncanonical': block['payload'] += '\n'
    elif fault == 'hash': block['sha256'] = '0' * 64
    elif fault == 'length': block['payload'] = base64.b64encode(b'x' * 64).decode()
    elif fault == 'order': index['blocks'].reverse()
    elif fault == 'duplicate':
        raw = base64.b64decode(block['payload']); raw = raw[:64] + raw
        block.update(count=block['count'] + 1, payload=base64.b64encode(raw).decode(), sha256=hashlib.sha256(raw).hexdigest()); index['count'] += 1
    elif fault == 'misplaced':
        raw = base64.b64decode(block['payload']); raw = bytes([(raw[0] + 1) % 256]) + raw[1:]
        block.update(payload=base64.b64encode(raw).decode(), sha256=hashlib.sha256(raw).hexdigest())
    else: block['count'] = n.MAX_INDEX_ENTRIES + 1
    before = copy.deepcopy(p)
    with pytest.raises(n.SourceError): n.reduce_observations(p, _retained_batch(), event_limit=100)
    assert p == before


def test_retained_skewed_prefix_keeps_per_block_limit_and_prior_state():
    events = {f'sha256:00{i:062x}': 'a' * 64 for i in range(n.MAX_INDEX_ENTRIES)}
    p = n.empty_projection(); p['events'] = events
    p = n.retained_projection(p); before = copy.deepcopy(p)
    e = _retained_fact(0); e['event_id'] = f'sha256:00{n.MAX_INDEX_ENTRIES:062x}'
    with pytest.raises(n.SourceError, match='block capacity'):
        n.reduce_observations(p, _retained_batch([e]), event_limit=n.MAX_INDEX_ENTRIES + 1)
    assert p == before


@pytest.mark.parametrize('limit', [None, True, 0, 1, 524289])
def test_retained_explicit_total_event_allowance_cannot_be_omitted_or_expanded(limit):
    p = n.retained_projection(n.empty_projection())
    p = n.reduce_observations(p, _retained_batch([_retained_fact(0), _retained_fact(1)]), event_limit=2)
    before = copy.deepcopy(p)
    with pytest.raises(n.SourceError): n.reduce_observations(p, _retained_batch(), event_limit=limit)
    assert p == before and n.MAX_INDEX_ENTRIES == 10000 and n.MAX_PROJECTION_BYTES == 32 * 1024**2


def test_retained_encoding_is_deterministic_and_preserves_non_index_fields():
    p = n.empty_projection(); p['events'] = {_retained_fact(i)['event_id']: n._digest(_retained_fact(i)) for i in range(40)}
    p['diagnostics'] = [{'code': 'prior_unknown'}]; p['gaps'] = [{'code': 'prior_gap'}]
    q = copy.deepcopy(p); q['events'] = dict(reversed(list(q['events'].items())))
    a, b = n.retained_projection(p), n.retained_projection(q)
    assert a == b and dict(n.event_fingerprints(a)) == p['events']
    assert {k:v for k,v in a.items() if k not in {'events','schema_version'}} == {k:v for k,v in p.items() if k not in {'events','schema_version'}}
    assert p['schema_version'] == 1 and n.retained_projection(a) == a


def test_retained_aggregate_byte_guard_counts_encoded_projection(monkeypatch):
    p = n.retained_projection(n.empty_projection()); before = copy.deepcopy(p)
    monkeypatch.setattr(n, 'MAX_PROJECTION_BYTES', len(n._canonical(p)) + 100)
    with pytest.raises(n.SourceError, match='capacity'):
        n.reduce_observations(p, _retained_batch([_retained_fact(0), _retained_fact(1)]), event_limit=2)
    assert p == before


def test_retained_interrupted_reduction_does_not_partially_publish(monkeypatch):
    p = n.retained_projection(n.empty_projection()); before = copy.deepcopy(p)
    def interrupted(*args): raise KeyboardInterrupt('synthetic interruption during semantic reduction')
    monkeypatch.setattr(n, '_usage', interrupted)
    first, second = _retained_fact(0), _retained_fact(1); second['kind'] = 'usage.snapshot'
    with pytest.raises(KeyboardInterrupt): n.reduce_observations(p, _retained_batch([first, second]), event_limit=2)
    assert p == before
