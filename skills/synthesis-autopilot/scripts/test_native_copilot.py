from copy import deepcopy
import pytest
import native_copilot as adapter
from test_native_adapter_sdk import records,capture

def producer():return adapter.qualify_source(records('copilot')[0],expected_root_session_id='session-public')
def sdk(event,data,identity='event-1',parent=None,**extra):return {'type':event,'id':identity,'parentId':parent,'timestamp':'2026-01-01T00:00:00Z','data':data,**extra}
def sdk_producer():return adapter.qualify_source(sdk('session.start',{'sessionId':'session-public','copilotVersion':'1.0.88','version':1,'producer':'copilot-agent'}),expected_root_session_id='session-public')

def test_hooks_without_call_ids_are_never_paired_by_adjacent_arguments():
    p=producer();call=adapter.decode_record(records('copilot')[1],p)[0];result=adapter.decode_record(records('copilot')[2],p)[0]
    assert call['native']['call_id'] is None and result['native']['call_id'] is None
    assert result['data']['call_pairing']=='UNKNOWN'

def test_camel_route_is_required_and_pascal_route_cannot_conflict():
    with pytest.raises(ValueError):adapter.decode_record(records('copilot')[1]['payload'],producer())
    row=records('copilot')[1];row['payload']['hook_event_name']='PostToolUse'
    with pytest.raises(ValueError):adapter.decode_record(row,producer())

@pytest.mark.parametrize('value',[None,[],True,'x',0])
def test_bad_result_objects_are_bounded_refusals(value):
    row=records('copilot')[2];row['payload']['toolResult']=value
    with pytest.raises(ValueError):adapter.decode_record(row,producer())

@pytest.mark.parametrize('value',[None,[],True,'x',0])
def test_sdk_payload_objects_are_bounded_refusals(value):
    with pytest.raises(ValueError):adapter.decode_record(sdk('assistant.usage',value),sdk_producer())

def test_sdk_pairs_real_native_ids_and_usage_identity_is_provider_call():
    p=sdk_producer()
    a=adapter.decode_record(sdk('tool.execution_start',{'toolCallId':'c1','toolName':'bash','arguments':{'command':'printf public'}}),p)[0]
    b=adapter.decode_record(sdk('tool.execution_complete',{'toolCallId':'c1','success':True,'result':{'content':'public'}}),p)[0]
    assert a['native']['call_id']==b['native']['call_id']=='c1'
    row=sdk('assistant.usage',{'apiCallId':'response-1','inputTokens':2,'outputTokens':3})
    u=adapter.decode_record(row,p)[0]['data'];assert u['countable'] and u['last']['total_tokens']==5
    assert u['measurement_id']==['copilot','session-public','response-1'] and u['billing_cost'] is None
    row['data'].pop('apiCallId');assert not adapter.decode_record(row,p)[0]['data']['countable']

def test_sdk_child_cancel_is_subordinate_and_fractional_usage_refused():
    p=sdk_producer();row=sdk('abort',{'reason':'user_initiated'},agentId='child-1')
    assert adapter.decode_record(row,p)[0]['kind']=='child.cancelled'
    row=sdk('assistant.usage',{'apiCallId':'r','inputTokens':2.5,'outputTokens':3})
    with pytest.raises(ValueError):adapter.decode_record(row,p)

def test_documented_timeout_gap_survives_every_surface_contract():
    contract=adapter.describe_contract();assert contract['capabilities']['permission_enforcement']=='FAIL_OPEN_PATHS'
    assert contract['native_acceptance']=='UNKNOWN' and contract['authority_granted'] is False

@pytest.mark.parametrize('bad',[[],{},False,2])
def test_malformed_pascal_event_is_a_typed_refusal(bad):
    row=records('copilot')[0];row['payload']['hook_event_name']=bad
    with pytest.raises(ValueError):adapter.qualify_source(row,expected_root_session_id='session-public')

def test_child_response_usage_has_distinct_measurement_scope_without_tree_total():
    p=sdk_producer();data={'apiCallId':'response-reused','inputTokens':2,'outputTokens':3}
    root=adapter.decode_record(sdk('assistant.usage',data),p)[0]['data']
    child=adapter.decode_record(sdk('assistant.usage',data,agentId='child-public'),p)[0]['data']
    assert root['measurement_id']!=child['measurement_id']
    assert child['scope']['kind']=='native_child' and child['scope_nonoverlap']=='UNKNOWN'

@pytest.mark.parametrize('kind',['abort','user.message','session.error','assistant.turn_end','session.shutdown','session.compaction_complete','permission.requested','permission.completed'])
def test_sdk_material_event_requires_pinned_semantic_fields(kind):
    with pytest.raises(ValueError):adapter.decode_record(sdk(kind,{}),sdk_producer())


def test_native_abort_reason_and_permission_result_are_closed_non_authority():
    p=sdk_producer()
    for reason in ('user_initiated','remote_command','user_abort','autopilot_credit_limit'):
        assert adapter.decode_record(sdk('abort',{'reason':reason}),p)[0]['kind']=='lifecycle.cancelled'
    for reason in ('user',True,None,{}):
        with pytest.raises(ValueError):adapter.decode_record(sdk('abort',{'reason':reason}),p)
    permitted=adapter.decode_record(sdk('permission.completed',{'requestId':'request-public','result':{'kind':'approved'},'decisionSource':'human_response'}),p)[0]
    assert permitted['data']['grants_authority'] is False and permitted['data']['enforcement_proven'] is False
