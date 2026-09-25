from copy import deepcopy
import pytest
import native_cursor as adapter
from test_native_adapter_sdk import records,capture

def producer():return adapter.qualify_source(records('cursor')[0],expected_root_session_id='session-public')

def test_abort_is_explicit_root_invalidation_but_subagent_abort_is_not():
    rows=records('cursor');p=producer()
    assert adapter.decode_record(rows[-1],p)[0]['kind']=='lifecycle.cancelled'
    child=deepcopy(rows[-1]);child['event']=child['payload']['hook_event_name']='subagentStop'
    result=adapter.decode_record(child,p)
    assert result[0]['kind']=='child.stopped' and result[0]['data']['portable_completion'] is False

@pytest.mark.parametrize('bad',[None,[],0,'x',True,{}, {'payload':None}])
def test_malformed_native_root_never_crashes_or_becomes_an_event(bad):
    with pytest.raises(ValueError):adapter.decode_record(bad,producer())

@pytest.mark.parametrize('field,bad',[('tool_output','not JSON'),('tool_output','[]'),('tool_output','{"exitCode":true}'),('tool_output','{"exitCode":0,"exitCode":1}'),('tool_use_id',None),('tool_input',[]),('cursor_version','foreign'),('conversation_id','foreign')])
def test_result_type_and_identity_controls(field,bad):
    row=records('cursor')[2];row['payload'][field]=bad
    with pytest.raises(ValueError):adapter.decode_record(row,producer())

def test_permission_observation_cannot_grant_even_if_native_payload_says_allow():
    row=records('cursor')[1];row['event']=row['payload']['hook_event_name']='beforeShellExecution';row['payload'].update(permission='allow',sandbox=True)
    event=adapter.decode_record(row,producer(),mode='native')[0]
    assert event['authentication']=='owner_admission_required'
    assert event['data']['grants_authority'] is False and event['data']['enforcement_proven'] is False

def test_usage_is_not_inferred_from_duration_or_text():
    row=records('cursor')[2];row['payload']['duration']=100000;row['payload']['tool_output']='{"stdout":"100 tokens billed"}'
    assert not any(x['kind']=='usage.snapshot' for x in adapter.decode_record(row,producer()))

def test_large_material_cannot_be_ignored_from_a_projection():
    assert adapter.is_ignored_projection({'type':'unknown'},producer()) is False

@pytest.mark.parametrize('field,value',[('session_id','foreign'),('is_background_agent','yes')])
def test_session_native_identity_and_background_flags_are_typed(field,value):
    row=records('cursor')[0];row['payload'].update(session_id='session-public',is_background_agent=False);row['payload'][field]=value
    with pytest.raises(ValueError):adapter.qualify_source(row,expected_root_session_id='session-public')

@pytest.mark.parametrize('event',['afterAgentResponse','afterAgentThought'])
@pytest.mark.parametrize('bad',[None,[],{},False])
def test_ignored_narration_requires_actual_text_grammar(event,bad):
    row=records('cursor')[1];row['event']=row['payload']['hook_event_name']=event;row['payload']['text']=bad
    with pytest.raises(ValueError):adapter.decode_record(row,producer())

@pytest.mark.parametrize('reason',['aborted','user_close','window_close'])
def test_session_end_cancel_cannot_disappear(reason):
    row=records('cursor')[0];row['event']=row['payload']['hook_event_name']='sessionEnd'
    row['payload'].update(session_id='session-public',reason=reason,duration_ms=20,is_background_agent=False,final_status='aborted')
    assert adapter.decode_record(row,producer())[0]['kind']=='lifecycle.cancelled'
