from copy import deepcopy
import pytest
import native_opencode as adapter
import native_observations as native
from test_native_adapter_sdk import records,source

def event(kind,data,seq,version=1):return {'id':'evt-'+str(seq),'created':seq,'type':kind,'durable':{'aggregateID':'session-public','seq':seq,'version':version},'data':{'sessionID':'session-public',**data}}
def header():return event('session.created',{'version':'2.0.16','projectID':'project-public','location':{'directory':'/public/fixture'},'slug':'public'},0)
def producer():return adapter.qualify_source(header(),expected_root_session_id='session-public')

def test_real_v2_sequence_fields_carry_through_reader_and_interval(tmp_path):
    rows=[header(),event('session.tool.called',{'assistantMessageID':'msg-1','id':'c1','input':{},'executed':True},1),
          event('session.tool.success',{'assistantMessageID':'msg-1','id':'c1','content':[{'type':'text','text':'public'}],'executed':True},3,2)]
    path=source(tmp_path,'opencode',rows);b,c=native.enroll_source(path,client='opencode',expected_root_session_id='session-public')
    batch=native.read_page(b,c);assert batch['gaps'][0]['lane']=='durable'
    current=native.revalidate_observations(b,[],required_interval=(0,path.stat().st_size))
    assert current['status']!='current' and current['negative_coverage']=='UNKNOWN'

@pytest.mark.parametrize('field,value',[('data',None),('data',[]),('durable',[]),('durable',None),('type',[]),('id',None)])
def test_closed_event_shapes_fail_as_value_errors(field,value):
    row=event('session.execution.interrupted',{'reason':'user'},1);row[field]=value
    with pytest.raises(ValueError):adapter.decode_record(row,producer())

def test_unknown_durable_version_and_cross_session_rejected():
    row=event('session.tool.success',{'id':'c','content':[{'type':'text','text':'x'}],'executed':True},1,1)
    with pytest.raises(ValueError):adapter.decode_record(row,producer())
    row=event('session.execution.interrupted',{'reason':'user','sessionID':'foreign'},1)
    with pytest.raises(ValueError):adapter.decode_record(row,producer())

def test_permission_reply_is_an_observation_with_no_action_authority():
    row={'id':'evt-permission','created':1,'type':'permission.replied','data':{'sessionID':'session-public','requestID':'per-public','reply':'always'}}
    result=adapter.decode_record(row,producer())[0]
    assert result['data']['grants_authority'] is False and result['data']['enforcement_proven'] is False
    for action in ('permission.reply','config.update','goal.set','schedule.create'):
        with pytest.raises(ValueError):adapter.request_shape(action,'session-public')

@pytest.mark.parametrize('session',['../escape','id?target=x','id#fragment','id%2fescape'])
def test_requests_never_accept_path_or_query_injection(session):
    with pytest.raises(ValueError):adapter.request_shape('session.get',session)

def test_current_readback_usage_is_provisional_until_native_terminal_fields():
    header=records('opencode')[0];p=adapter.qualify_source(header,expected_root_session_id='session-public')
    row=records('opencode')[1]
    result=adapter.decode_record(row,p);usage=next(x['data'] for x in result if x['kind']=='usage.snapshot')
    assert usage['countable'] and usage['last']['total_tokens']==5
    row['payload']['time'].pop('completed')
    usage=next(x['data'] for x in adapter.decode_record(row,p) if x['kind']=='usage.snapshot')
    assert usage['phase']=='provisional' and not usage['countable']

@pytest.mark.parametrize('event',['session.text.started','session.text.delta','session.text.ended','session.reasoning.started','session.reasoning.delta','session.reasoning.ended'])
def test_ignored_narration_does_not_hide_malformed_native_records(event):
    row=event_record=globals()['event'](event,{},1)
    with pytest.raises(ValueError):adapter.decode_record(row,producer())

def test_schema_file_content_uses_uri_reference_without_opening_it():
    row=records('opencode')[1];row['payload']['content'][0]['state']['content']=[{'type':'file','mime':'text/plain','uri':'fixture://public-result','name':None}]
    p=adapter.qualify_source(records('opencode')[0],expected_root_session_id='session-public')
    result=adapter.decode_record(row,p)
    assert result[1]['data']['result'][0]['uri']=='fixture://public-result'

def shell_records():
    info={'id':'shell-public','status':'running','command':'printf PUBLIC_NATIVE_FIXTURE','cwd':'/public/fixture','shell':'/bin/sh','file':'/public/fixture/output','metadata':{'sessionID':'session-public','background':True},'time':{'started':1},'pid':123}
    end={**info,'status':'exited','exit':0,'time':{'started':1,'completed':2}}
    return [header(),event('session.shell.started',{'shell':info},1),event('session.shell.ended',{'shell':end,'output':{'output':'PUBLIC_NATIVE_FIXTURE','cursor':21,'size':21,'truncated':False}},2)]

def test_native_shell_session_pair_flows_through_actual_reader(tmp_path):
    path=source(tmp_path,'opencode',shell_records());b,c=native.enroll_source(path,client='opencode',expected_root_session_id='session-public')
    page=native.read_page(b,c);assert not page['gaps']
    assert [e['kind'] for e in page['events']]==['tool.call','tool.result']
    assert page['events'][0]['native']['call_id']==page['events'][1]['native']['call_id']=='shell-public'
    result=page['events'][1]['data'];assert result['result']['exit_code']==0 and result['result']['output']=='PUBLIC_NATIVE_FIXTURE'
    assert result['outcome_pass'] is False and result['execution_origin']=='native_direct_shell'
    assert native.revalidate_observations(b,page['events'])['status']=='current'

@pytest.mark.parametrize('fault',['truncated','foreign','exit-bool','missing-exit','bad-output','counter-overrun'])
def test_native_shell_incomplete_or_cross_session_result_is_a_gap(tmp_path,fault):
    rows=shell_records();data=rows[-1]['data']
    if fault=='truncated':data['output']['truncated']=True
    if fault=='foreign':data['shell']['metadata']['sessionID']='foreign'
    if fault=='exit-bool':data['shell']['exit']=True
    if fault=='missing-exit':data['shell'].pop('exit')
    if fault=='bad-output':data['output']['output']=[]
    if fault=='counter-overrun':data['output']['cursor']=999
    path=source(tmp_path,'opencode',rows);b,c=native.enroll_source(path,client='opencode',expected_root_session_id='session-public')
    page=native.read_page(b,c);assert page['gaps']
    assert not any(e['kind']=='tool.result' for e in page['events'])

@pytest.mark.parametrize('kind',['session.execution.failed','session.compaction.started','session.compaction.ended','session.compaction.failed','session.step.started','session.step.failed','session.inbox.delivered','session.inbox.cancelled','session.usage.updated','session.status','permission.asked','permission.replied'])
def test_material_event_requires_documented_payload_fields(kind):
    row=event(kind,{},1)
    if kind.startswith('permission.') or kind in ('session.usage.updated','session.status'):row.pop('durable')
    with pytest.raises(ValueError):adapter.decode_record(row,producer())


def test_compaction_status_and_permission_positive_fields_remain_non_authoritative():
    p=producer()
    compact=event('session.compaction.ended',{'reason':'manual','text':'Public summary','recent':'Public recent context'},1)
    assert adapter.decode_record(compact,p)[0]['data']['recovery_proven'] is False
    row=event('session.status',{'status':{'type':'retry','attempt':1,'message':'public retry','next':2}},2);row.pop('durable')
    assert adapter.decode_record(row,p)[0]['data']['portable_completion'] is False

@pytest.mark.parametrize('sequence,expected',[(2,'current'),(3,'invalid')])
def test_current_suffix_revalidation_binds_prior_owner_sequence_lanes(tmp_path,sequence,expected):
    import json
    rows=shell_records();rows[-1]['durable']['seq']=sequence
    path=source(tmp_path,'opencode',rows);b,c=native.enroll_source(path,client='opencode',expected_root_session_id='session-public')
    start=len(b''.join(json.dumps(r,separators=(',',':')).encode()+b'\n' for r in rows[:2]))
    result=native.revalidate_observations(b,[],required_interval=(start,path.stat().st_size),prior_sequences={'durable':1})
    assert result['status']==expected
    if sequence==3:assert result['negative_coverage']=='UNKNOWN'


def test_transport_and_native_durable_ordinals_remain_separate():
    from test_native_adapter_sdk import capture
    h=capture('opencode','session.created',header(),10);h['producer_version']='2.0.16'
    p=adapter.qualify_source(h,expected_root_session_id='session-public')
    row=capture('opencode','session.execution.interrupted',event('session.execution.interrupted',{'reason':'user'},1),11);row['producer_version']='2.0.16'
    fact=adapter.decode_record(row,p)[0]
    assert fact['native']['ordinal']==11 and fact['native']['capture_sequence']==11 and fact['native']['sequence']==1
    assert adapter.record_sequences(row,p)=={'capture':11,'durable':1}
