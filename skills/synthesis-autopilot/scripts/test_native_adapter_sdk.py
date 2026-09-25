"""Public synthetic source controls; none certifies a native installation."""
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import pytest
import native_observations as native

ROOT=Path(__file__).resolve().parents[3]

def capture(client,event,payload,sequence,session='session-public',surface=None):
    return {'type':'synthesis.native_capture','schema_version':1,'client':client,
            'surface':surface or {'cursor':'cursor-ide','copilot':'copilot-cli','opencode':'opencode-sdk-v2'}[client],
            'producer_version':'public-fixture-1','capture_id':'capture-public','sequence':sequence,
            'session_id':session,'event':event,'payload':payload}

def records(client):
    if client=='cursor':
        common={'conversation_id':'session-public','generation_id':'generation-1','cursor_version':'public-fixture-1','workspace_roots':['/public/fixture']}
        return [capture(client,'sessionStart',{**common,'hook_event_name':'sessionStart','session_id':'session-public','is_background_agent':False},0),
                capture(client,'preToolUse',{**common,'hook_event_name':'preToolUse','tool_use_id':'call-1','tool_name':'Shell','tool_input':{'command':'printf public'}},1),
                capture(client,'postToolUse',{**common,'hook_event_name':'postToolUse','tool_use_id':'call-1','tool_name':'Shell','tool_input':{'command':'printf public'},'tool_output':'{"exitCode":0,"stdout":"public"}','duration':1},2),
                capture(client,'stop',{**common,'hook_event_name':'stop','status':'aborted','loop_count':0},3)]
    if client=='copilot':
        common={'sessionId':'session-public','timestamp':1780000000000,'cwd':'/public/fixture'}
        return [capture(client,'sessionStart',{**common,'source':'startup'},0),
                capture(client,'preToolUse',{**common,'toolName':'bash','toolArgs':{'command':'printf public'}},1),
                capture(client,'postToolUse',{**common,'toolName':'bash','toolArgs':{'command':'printf public'},'toolResult':{'resultType':'success','textResultForLlm':'public'}},2),
                capture(client,'sessionEnd',{**common,'reason':'abort'},3)]
    return [capture(client,'session.get',{'id':'session-public','location':{'directory':'/public/fixture'},'title':'Public fixture'},0),
            capture(client,'session.message',{'id':'msg_public','type':'assistant','agent':'build','time':{'created':1,'completed':2},'model':{'providerID':'fixture','modelID':'fixture'},'content':[{'type':'tool','id':'call-1','name':'shell','time':{'created':1,'completed':2},'state':{'status':'completed','input':{'command':'printf public'},'content':[{'type':'text','text':'public'}]}}],'finish':'stop','tokens':{'input':2,'output':3,'reasoning':0,'cache':{'read':0,'write':0}}},1),
            capture(client,'session.execution.interrupted',{'id':'event-public-interrupt','created':3,'type':'session.execution.interrupted','durable':{'aggregateID':'session-public','seq':2,'version':1},'data':{'sessionID':'session-public','reason':'user'}},2)]

def source(tmp_path, client, rows=None):
    path=tmp_path/(client+'.jsonl')
    path.write_bytes(b''.join(json.dumps(x,separators=(',',':')).encode()+b'\n' for x in (rows if rows is not None else records(client))))
    return path

def sdk_tool_rows(call_agent=None,result_agent=None):
    def row(kind,data,identity,agent):
        value={'type':kind,'id':identity,'timestamp':'2026-09-25T00:00:00Z','parentId':None,'data':data}
        if agent is not None:value['agentId']=agent
        return value
    return [row('session.start',{'sessionId':'session-public','copilotVersion':'1.0.88','version':1},'e0',None),
            row('tool.execution_start',{'toolCallId':'shared','toolName':'read','arguments':{}},'e1',call_agent),
            row('tool.execution_complete',{'toolCallId':'shared','success':True,'result':{'content':'public'}},'e2',result_agent)]

@pytest.mark.parametrize('client,variant',[
    ('copilot','missing'),('copilot','root-child'),('copilot','child-root'),('copilot','child-child'),
    ('cursor','generation')])
def test_full_reader_never_pairs_missing_or_different_native_call_scope(tmp_path,client,variant):
    rows=records(client)
    if variant=='root-child':rows=sdk_tool_rows(None,'child-a')
    elif variant=='child-root':rows=sdk_tool_rows('child-a',None)
    elif variant=='child-child':rows=sdk_tool_rows('child-a','child-b')
    elif variant=='generation':rows[2]['payload']['generation_id']='generation-2'
    path=source(tmp_path,client,rows)
    binding,cursor=native.enroll_source(path,client=client,expected_root_session_id='session-public')
    batch=native.read_page(binding,cursor);assert not batch['gaps']
    projected=native.reduce_observations(native.empty_projection(),batch)
    assert projected['pairs'] and not any(p['status']=='paired' for p in projected['pairs'].values())
    assert projected['unresolved_pair_count']>0
    assert native.revalidate_observations(binding,batch['events'])['status']=='current'

@pytest.mark.parametrize('client,agent',[('copilot',None),('copilot','child-a'),('cursor',None)])
def test_full_reader_exact_native_call_scope_pairs_and_revalidates(tmp_path,client,agent):
    rows=sdk_tool_rows(agent,agent) if client=='copilot' else records(client)
    path=source(tmp_path,client,rows)
    binding,cursor=native.enroll_source(path,client=client,expected_root_session_id='session-public')
    batch=native.read_page(binding,cursor)
    projected=native.reduce_observations(native.empty_projection(),batch)
    assert [p['status'] for p in projected['pairs'].values()]==['paired']
    events=[e for e in batch['events'] if e['kind'] in ('tool.call','tool.result')]
    assert events[0]['native']['call_scope']==events[1]['native']['call_scope']
    assert native.revalidate_observations(binding,events)['status']=='current'
    changed=json.loads(json.dumps(events));changed[0]['native']['call_scope']['session_id']='foreign'
    assert native.revalidate_observations(binding,changed)['status']!='current'

@pytest.mark.parametrize('client',['cursor','copilot','opencode'])
def test_actual_reader_consumes_additional_client_and_revalidates_bytes(tmp_path,client):
    path=source(tmp_path,client)
    binding,cursor=native.enroll_source(path,client=client,expected_root_session_id='session-public',mode='synthetic')
    page=native.read_page(binding,cursor)
    assert not page['gaps'],page
    assert any(e['kind']=='tool.result' for e in page['events'])
    assert all(e['mode']=='synthetic' and e['authentication']=='owner_admission_required' for e in page['events'])
    current=native.revalidate_observations(binding,page['events'])
    assert current['status']=='current',current
    raw=path.read_bytes();assert b'public' in raw
    path.write_bytes(raw.replace(b'printf public',b'printf tamper'))
    assert native.revalidate_observations(binding,page['events'])['status']!='current'

@pytest.mark.parametrize('client',['cursor','copilot','opencode'])
def test_unknown_malformed_and_cross_session_records_are_reader_gaps(tmp_path,client):
    rows=records(client);rows.append(capture(client,'unknown.future',{'sessionId':'session-public'},len(rows)))
    path=source(tmp_path,client,rows)
    binding,cursor=native.enroll_source(path,client=client,expected_root_session_id='session-public',mode='synthetic')
    page=native.read_page(binding,cursor);assert page['gaps']
    for bad in (None,[],4,{'type':'synthesis.native_capture','payload':[]}):
        module=importlib.import_module('native_'+client)
        with pytest.raises(ValueError):module.decode_record(bad,binding['producer'])
    rows=records(client);rows[1]['session_id']='foreign'
    path=source(tmp_path,client,rows)
    binding,cursor=native.enroll_source(path,client=client,expected_root_session_id='session-public',mode='synthetic')
    assert native.read_page(binding,cursor)['gaps']

@pytest.mark.parametrize('client',['cursor','copilot','opencode'])
def test_sdk_inspection_preserves_unknown_native_authority_and_required_gates(tmp_path,client):
    sdk=importlib.import_module('native_adapter_sdk')
    path=source(tmp_path,client)
    report=sdk.inspect_source(path,client=client,session_id='session-public',mode='synthetic')
    assert report['source_status']=='CURRENT'
    assert report['native_provenance']=='UNKNOWN'
    assert report['authority_granted'] is False
    qualified=sdk.assess(report['surface'],required=['native_identity','permission_enforcement','tool_outcome'],source_report=report)
    assert qualified['qualified'] is False and qualified['missing']
    assert all(qualified['capabilities'][key]['native']!='PASS' for key in qualified['capabilities'])

@pytest.mark.parametrize('client',['cursor','copilot','opencode'])
def test_sequence_hole_and_duplicate_conflict_do_not_make_complete_coverage(tmp_path,client):
    rows=records(client);rows[2]['sequence']=7
    path=source(tmp_path,client,rows)
    b,c=native.enroll_source(path,client=client,expected_root_session_id='session-public',mode='synthetic')
    assert native.read_page(b,c)['gaps']


def test_sdk_cli_is_bounded_strict_json_and_never_runs_an_action(tmp_path):
    script=ROOT/'skills/synthesis-autopilot/scripts/native_adapter_sdk.py'
    for body in ('[]','{"operation":"describe","operation":"execute"}','{"operation":"execute","command":"echo no"}'):
        done=subprocess.run([sys.executable,str(script)],input=body,capture_output=True,text=True,timeout=3)
        assert done.returncode!=0
        result=json.loads(done.stdout);assert result['status']=='UNRESOLVED' and result['authority_granted'] is False


def test_all_additional_surfaces_exist_in_canonical_registry_and_no_native_promotion():
    import capabilities
    surfaces=capabilities.supported_surfaces()['surfaces']
    for name in ('cursor-ide','cursor-cli','cursor-cloud','copilot-cli','copilot-vscode','copilot-cloud','opencode-cli','opencode-sdk-v2'):
        entry=surfaces[name]
        assert entry['level']!='native'
        assert entry['observation_contract']['authority_granted'] is False
        assert entry['observation_contract']['native_acceptance']=='UNKNOWN'

@pytest.mark.parametrize('client',['cursor','copilot','opencode'])
def test_current_reader_partial_oversized_rotation_and_forged_capture_are_honest(tmp_path,client):
    from copy import deepcopy
    path=source(tmp_path,client)
    b,c=native.enroll_source(path,client=client,expected_root_session_id='session-public')
    raw=path.read_bytes();path.write_bytes(raw[:-2]);page=native.read_page(b,c)
    assert page['coverage']['pending_bytes'] and page['coverage']['negative_coverage']=='UNKNOWN'
    path.write_bytes(raw);completed=native.read_page(b,page['cursor']);assert not completed['gaps']
    old=path.with_suffix('.old');path.rename(old);path.write_bytes(raw)
    rotated=native.read_page(b,completed['cursor']);assert rotated['diagnostics'] and rotated['cursor']==completed['cursor']
    oversized=records(client);oversized[-1]['payload']['material']='x'*4000
    path=source(tmp_path,client,oversized);b,c=native.enroll_source(path,client=client,expected_root_session_id='session-public')
    page=native.read_page(b,c,limits=native.Limits(page_bytes=8192,payload_bytes=2048))
    assert page['gaps'] and page['coverage']['negative_coverage']=='UNKNOWN'
    forged=records(client);forged[1]['capture_id']='other-capture';path=source(tmp_path,client,forged)
    b,c=native.enroll_source(path,client=client,expected_root_session_id='session-public');assert native.read_page(b,c)['gaps']

@pytest.mark.parametrize('client',['cursor','copilot','opencode'])
def test_sequence_lanes_survive_paging_and_refuse_reordered_replay(tmp_path,client):
    rows=records(client);path=source(tmp_path,client,rows)
    b,c=native.enroll_source(path,client=client,expected_root_session_id='session-public')
    batch=native.read_page(b,c,limits=native.Limits(page_bytes=1024,events=1));assert not batch['gaps']
    assert batch['cursor'].get('dialect_sequences')
    rows.append(dict(rows[1]));path.write_bytes(b''.join(json.dumps(x).encode()+b'\n' for x in rows))
    # Fresh enrollment isolates record-order failure from an unrelated prefix rewrite.
    b,c=native.enroll_source(path,client=client,expected_root_session_id='session-public');assert native.read_page(b,c)['gaps']

@pytest.mark.parametrize('client',['cursor','copilot','opencode'])
def test_malformed_nested_types_never_raise_untyped_errors_or_grant_authority(client):
    from copy import deepcopy
    module=importlib.import_module('native_'+client);original=records(client)
    p=module.qualify_source(original[0],expected_root_session_id='session-public')
    def paths(value,prefix=()):
        if isinstance(value,dict):
            for k,v in value.items():
                yield prefix+(k,)
                if isinstance(v,dict):yield from paths(v,prefix+(k,))
    for row in original:
        for path in paths(row):
            for bad in (None,[],{},True,0):
                value=deepcopy(row);target=value
                for key in path[:-1]:target=target[key]
                target[path[-1]]=bad
                try:events=module.decode_record(value,p,mode='synthetic')
                except ValueError:continue
                assert isinstance(events,list)
                for event in events:
                    assert event['authentication']=='owner_admission_required' and event['mode']=='synthetic'
                    assert event['data'].get('grants_authority') is not True
                    assert event['data'].get('outcome_pass') is not True


def test_assessment_does_not_promote_native_claims_and_rejects_untyped_required():
    import native_adapter_sdk as sdk
    for required in ([{}],[None],[True],['native_identity','native_identity'],['unknown']):
        with pytest.raises(ValueError):sdk.assess('opencode-sdk-v2',required=required)
    report=sdk.assess('opencode-sdk-v2',required=['tool_outcome'],source_report={'surface':'opencode-sdk-v2','client':'opencode','native_provenance':'VERIFIED','authority_granted':True,'source_status':'PASS'})
    assert report['qualified'] is False and report['capabilities']['tool_outcome']['native']=='UNKNOWN'


def test_transient_reader_diagnostic_cannot_be_reported_current(tmp_path,monkeypatch):
    import native_adapter_sdk as sdk
    path=source(tmp_path,'cursor');real=native.read_page
    def observed_failure(*args,**kwargs):
        batch=real(*args,**kwargs);batch['diagnostics'].append({'code':'source_unavailable','detail':'read admission unavailable'});return batch
    monkeypatch.setattr(native,'read_page',observed_failure)
    report=sdk.inspect_source(path,client='cursor',session_id='session-public')
    assert report['source_status']=='UNKNOWN' and report['diagnostics']


from test_run_state import engine,world,create,command

@pytest.mark.parametrize('client',['cursor','copilot','opencode'])
def test_real_journal_admission_does_not_accept_an_additional_client_header_as_root(engine,world,client):
    import observation_bridge
    observation_bridge.register(engine);state=create(engine,world)
    before=world['transcript'].read_bytes()
    world['transcript'].write_bytes(b''.join(json.dumps(r).encode()+b'\n' for r in records(client)))
    with pytest.raises(ValueError):command(engine,world,state,'native.enroll',{'source_handle':'root','mode':'native'})
    assert engine.load_run(world['project'],state['run_id'])==state
    world['transcript'].write_bytes(before)
    changed=command(engine,world,state,'native.enroll',{'source_handle':'root','mode':'synthetic'})
    assert changed['revision']==state['revision']+1
    assert changed['extensions']['native_observations']['sources']['root']['binding']['producer']['client']=='claude'

@pytest.mark.parametrize('module',['native_cursor','capabilities','native_observations'])
def test_sdk_refuses_a_cached_module_from_a_different_installation(tmp_path,monkeypatch,module):
    import native_adapter_sdk as sdk
    imported=importlib.import_module(module)
    monkeypatch.setattr(imported,'__file__',str(tmp_path/'foreign'/Path(imported.__file__).name))
    with pytest.raises(ValueError,match='source tree'):
        if module=='native_observations':sdk.inspect_source(source(tmp_path,'cursor'),client='cursor',session_id='session-public')
        else:sdk.assess('cursor-ide')


def test_capture_retains_native_timestamp_instead_of_inventing_ingestion_time():
    import native_copilot
    rows=records('copilot');p=native_copilot.qualify_source(rows[0],expected_root_session_id='session-public')
    fact=native_copilot.decode_record(rows[1],p)[0]
    assert fact['native_timestamp']==rows[1]['payload']['timestamp']
