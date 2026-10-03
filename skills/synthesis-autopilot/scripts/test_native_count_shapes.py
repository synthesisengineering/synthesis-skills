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
