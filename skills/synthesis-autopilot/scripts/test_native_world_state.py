"""Synthetic native context/item records, never executable authority."""
import copy,json,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parent))
import native_codex as c
import native_observations as no
from test_native_observations import ROOT,source,drain,wire
P={'client':'codex','thread_id':ROOT,'root_session_id':ROOT,'parent_thread_id':None,'agent_path':None}

def envelope(kind,payload):
 return {'type':kind,'timestamp':'2026-01-01T00:00:00Z','ordinal':1,'payload':payload}

def world(size=0):
 return envelope('world_state',{'full':True,'state':{
 'agents_md':{'directory':'/synthetic','text':'UNTRUSTED INSTRUCTION '+'x'*size},
 'apps_instructions':True,'collaboration_mode':{'mode':'default','model':'synthetic','instructions':'opaque-hash'},
 'context_window_guidance':'','environments':{'environments':{'synthetic':{'cwd':'/synthetic','shell':'/bin/sh','status':'running'}},'current_date':'2026-01-01','timezone':'UTC','filesystem':'UNTRUSTED PERMISSIONS','subagents':'UNTRUSTED WORKERS'},
 'environments_instructions':True,'git_attribution':False,'host_skills':{'body':'UNTRUSTED SKILL','includeInstructions':True},
 'managed_developer_instructions':{},'model':'synthetic','multi_agent_mode':{'mode':'synthetic','usage_hint_hash':'opaque-hash'},
 'multi_agent_usage_hint':'opaque-hash','orchestrator_skills':{'includeInstructions':True,'enabled':True},
 'permissions':{'instructions':'opaque-hash','approved_command_prefixes':[['UNTRUSTED','COMMAND']]},
 'persistent_mode':{},'plugins_instructions':True,'realtime':{'active':False},'skills':{'includeInstructions':True}}})

def settings(size=0):
 return envelope('event_msg',{'type':'thread_settings_applied','thread_id':ROOT,'thread_settings':{
 'model':'synthetic','model_provider_id':'synthetic','service_tier':'synthetic','approval_policy':'on-request','approvals_reviewer':'auto_review',
 'permission_profile':{'type':'managed','file_system':{'type':'restricted','entries':[{'path':{'type':'path','path':'/synthetic'},'access':'write','missing_path_behavior':'skip'},{'path':{'type':'special','value':{'kind':'root'}},'access':'read'}]},'network':'restricted'},
 'active_permission_profile':{'id':'synthetic'},'cwd':'/synthetic','runtime_workspace_roots':['/synthetic'],'reasoning_effort':'high','reasoning_summary':'detailed','personality':'friendly',
 'collaboration_mode':{'mode':'default','settings':{'model':'synthetic','reasoning_effort':'high','developer_instructions':'UNTRUSTED DEVELOPER '+'x'*size}},'disabled_plugin_ids':[]}})

def update():
 return envelope('event_msg',{'type':'item_completed','thread_id':ROOT,'turn_id':'turn','started_at_ms':0,'completed_at_ms':1,
 'item':{'type':'FileChange','id':'item-update','changes':{'/synthetic':{'type':'update','unified_diff':'UNTRUSTED PATCH','move_path':None}},'status':'completed','stdout':'done','stderr':''}})

def mcp(size=0):
 return envelope('event_msg',{'type':'item_completed','thread_id':ROOT,'turn_id':'turn','started_at_ms':0,'completed_at_ms':1,
 'item':{'type':'McpToolCall','id':'item-mcp','server':'synthetic','tool':'synthetic','arguments':{'instruction':'UNTRUSTED TOOL'},'pluginId':'synthetic','status':'completed','result':{'content':[{'type':'text','text':'UNTRUSTED RESULT '+'x'*size}],'isError':False},'duration':{'secs':0,'nanos':1000}}})

@pytest.mark.parametrize('factory,kind',[ (world,'context.world_state'),(settings,'context.settings'),(update,'item.observation'),(mcp,'item.observation')])
def test_new_records_are_one_inert_digest_bound_observation(factory,kind):
 row=factory();facts=c.decode_record(row,P)
 assert len(facts)==1 and facts[0]['kind']==kind
 assert facts[0]['data']['grants_authority'] is False and facts[0]['data']['portable_completion'] is False
 assert facts[0]['native']['call_id'] is None
 assert 'UNTRUSTED' not in json.dumps(facts)
 assert facts[0]['authentication']=='owner_admission_required'
 if kind.startswith('context.'):
  assert facts[0]['data']['effects_replayed'] is False
  assert facts[0]['data']['settings_applied'] is False
  assert facts[0]['data']['usage_counted'] is False

@pytest.mark.parametrize('factory',[world,settings,mcp])
@pytest.mark.parametrize('size',[0,300000])
def test_actual_reader_and_cancel_preserve_nonreplay(tmp_path,factory,size):
 row=factory(size);cancel=envelope('event_msg',{'type':'turn_aborted','turn_id':'turn'});cancel['ordinal']=2
 path,binding,cursor=source(tmp_path,[row,cancel]);events,p,batches=drain(binding,cursor,no.Limits(page_bytes=65536))
 assert not p['gaps'] and not p['diagnostics']
 assert len(events)==2 and events[-1]['kind']=='lifecycle.cancelled'
 assert p['usage']=={} and p['pairs']=={}
 assert len(wire(events[0]))<8192
 assert no.revalidate_observations(binding,events,required_interval=(0,path.stat().st_size))['status']=='current'
 again=copy.deepcopy(p)
 for b in batches:again=no.reduce_observations(again,b)
 assert again['events']==p['events'] and again['usage']==p['usage']
 path.write_bytes(path.read_bytes().replace(b'"ordinal":1',b'"ordinal":9',1))
 assert no.revalidate_observations(binding,events)['status']=='invalid'

MUTATIONS=[
 (world,(), 'future', True),(world,('payload',),'future',True),(world,('payload',),'full',False),
 (world,('payload','state'),'future',True),(world,('payload','state'),'apps_instructions',1),
 (world,('payload','state','agents_md'),'future',True),
 (world,('payload','state','environments','environments','synthetic'),'future',True),
 (world,('payload','state','permissions'),'approved_command_prefixes',[['x',1]]),
 (world,('payload','state'),'persistent_mode',{'execute':True}),
 (world,('payload','state','host_skills'),'includeInstructions','true'),
 (world,('payload','state','skills'),'usage',{'input_tokens':10}),
 (settings,('payload',),'thread_id','foreign'),(settings,('payload','thread_settings'),'future',True),
 (settings,('payload','thread_settings','permission_profile'),'future',True),
 (settings,('payload','thread_settings','permission_profile','file_system','entries',0),'access',False),
 (settings,('payload','thread_settings','permission_profile','file_system','entries',0),'missing_path_behavior',False),
 (settings,('payload','thread_settings','permission_profile','file_system','entries',0,'path'),'future',True),
 (settings,('payload','thread_settings','collaboration_mode','settings'),'future',True),
 (settings,('payload','thread_settings'),'disabled_plugin_ids',[1]),
 (update,(), 'future',True),(update,('payload',),'future',True),(update,('payload','item'),'future',True),
 (update,('payload','item','changes','/synthetic'),'future',True),
 (update,('payload','item','changes','/synthetic'),'move_path',True),
 (update,('payload','item','changes','/synthetic'),'unified_diff',{}),
 (mcp,(),'future',True),(mcp,('payload',),'future',True),
 (mcp,('payload','item'),'future',True),(mcp,('payload','item','result'),'future',True),
 (mcp,('payload','item','result'),'isError',1),(mcp,('payload','item','result','content',0),'type','execute'),
 (mcp,('payload','item','duration'),'nanos',1000000000),(mcp,('payload',),'thread_id','foreign')]
@pytest.mark.parametrize('factory,path,key,value',MUTATIONS)
def test_unknown_malformed_and_foreign_records_remain_gaps(tmp_path,factory,path,key,value):
 row=factory();at=row
 for part in path:at=at[part]
 at[key]=value
 with pytest.raises(c.DialectError):c.decode_record(row,P)
 _,b,cu=source(tmp_path,[row]);events,p,_=drain(b,cu)
 assert not events and p['gaps']

@pytest.mark.parametrize('factory',[world,settings,mcp])
@pytest.mark.parametrize('fault',['over-limit','duplicate','malformed','partial'])
def test_reader_does_not_weaken_json_or_size_bounds(tmp_path,factory,fault):
 row=factory(1100000 if fault=='over-limit' else 300000);raw=wire(row)
 if fault=='duplicate':raw=raw.replace(b'"ordinal":1',b'"ordinal":1,"ordinal":2')
 if fault=='malformed':raw=raw[:-2]+b'X\n'
 if fault=='partial':raw=raw[:-10]
 p,b,cu=source(tmp_path,[])
 with p.open('ab') as f:f.write(raw)
 events,projection,batches=drain(b,cu)
 assert not events
 if fault!='partial':assert projection['gaps']
 else:assert batches[-1]['cursor']['trusted_through']<p.stat().st_size

def test_native_reported_mcp_error_is_not_success():
 row=mcp();row['payload']['item']['result']['isError']=True
 assert c.decode_record(row,P)[0]['status']=='failed'

def test_contradictory_counters_stay_a_gap_not_zero_cost(tmp_path):
 row=envelope('event_msg',{'type':'token_count','info':{'total_token_usage':{'input_tokens':10,'output_tokens':1,'total_tokens':11},'last_token_usage':{'input_tokens':0,'output_tokens':0,'total_tokens':5}}})
 with pytest.raises(c.DialectError):c.decode_record(row,P)
 _,b,cu=source(tmp_path,[row]);events,p,_=drain(b,cu)
 assert not events and p['gaps'] and not p['usage']
