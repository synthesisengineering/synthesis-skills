"""Synthetic controls for complete, bounded command spans and typed context totals."""
import copy,hashlib,json,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parent))
import native_observations as no
import native_codex as c
from test_native_observations import source,wire,drain,completed_item,ROOT,header

def large(size=1200000):
 r=completed_item(size);i=r['payload']['item'];i.update(process_id='1',parsed_cmd=[{'type':'read','cmd':'opaque','name':'x','path':'x'}],source='unified_exec_startup',duration={'secs':0,'nanos':1},formatted_output='');return r

def test_span_current_revalidation_and_cancel(tmp_path):
 r=large();cancel={'type':'event_msg','ordinal':2,'payload':{'type':'turn_aborted','turn_id':'turn'}}
 p,b,cu=source(tmp_path,[r,cancel]);ev,pr,batches=drain(b,cu,no.Limits(page_bytes=65536))
 assert not pr['gaps'] and not pr['diagnostics'];assert len(ev)==2 and ev[-1]['kind']=='lifecycle.cancelled'
 assert ev[0]['data']['record_digest']==hashlib.sha256(wire(r)).hexdigest()
 assert ev[0]['data']['commitment_algorithm']=='codex-command-wire-sha256-v1'
 assert not pr['pairs'] and not pr['usage'];assert not ev[0]['data']['grants_authority']
 assert all(x['record_readback_bytes']<=no.MAX_RECORD_READBACK_BYTES for x in batches)
 assert no.revalidate_observations(b,ev,required_interval=(0,p.stat().st_size),max_bytes=4*1024*1024)['status']=='current'
 again=copy.deepcopy(pr)
 for batch in batches:again=no.reduce_observations(again,batch)
 assert again==pr
 p.write_bytes(p.read_bytes().replace(b'"stdout":"x',b'"stdout":"y',1))
 assert no.revalidate_observations(b,ev,max_bytes=4*1024*1024)['status']=='invalid'

@pytest.mark.parametrize('path,key,value',[((),'future',True),(('payload',),'future',True),(('payload','item'),'future',True),(('payload','item'),'exit_code',True),(('payload','item'),'stdout',{}),(('payload','item'),'command',[]),(('payload','item'),'command',[1]),(('payload','item'),'parsed_cmd',[{'type':'future','cmd':'x'}]),(('payload','item','duration'),'nanos',1000000000),(('payload',),'thread_id','foreign'),(('payload',),'completed_at_ms',0)])
def test_late_schema_refusal(tmp_path,path,key,value):
 r=large();at=r
 for x in path:at=at[x]
 at[key]=value;p,b,cu=source(tmp_path,[r]);ev,pr,_=drain(b,cu)
 assert not ev and pr['gaps']

@pytest.mark.parametrize('fault',['duplicate','unicode','trailing','partial'])
def test_complete_wire_validation(tmp_path,fault):
 raw=wire(large())
 if fault=='duplicate':raw=raw.replace(b'"formatted_output":""',b'"formatted_output":"","stdout":"late"')
 if fault=='unicode':raw=raw.replace(b'"formatted_output":""',b'"formatted_output":"\xff"')
 if fault=='trailing':raw=raw[:-1]+b'false\n'
 if fault=='partial':raw=raw[:-10]
 p,b,cu=source(tmp_path,[])
 with p.open('ab') as f:f.write(raw)
 ev,pr,batches=drain(b,cu,no.Limits(page_bytes=65536));assert not ev
 if fault!='partial':assert pr['gaps']
 else:assert batches[-1]['cursor']['trusted_through']<p.stat().st_size

def test_mutated_prior_page_is_not_old_commitment(tmp_path):
 p,b,cu=source(tmp_path,[large()]);first=no.read_page(b,cu,limits=no.Limits(page_bytes=400000))
 p.write_bytes(p.read_bytes().replace(b'"stdout":"x',b'"stdout":"y',1));ev,pr,_=drain(b,first['cursor'])
 assert not ev and (pr['gaps'] or pr['diagnostics'])

def test_span_bound_is_finite(tmp_path):
 p,b,cu=source(tmp_path,[large(4300000)]);ev,pr,_=drain(b,cu);assert not ev and pr['gaps']

def counter():
 zero={k:0 for k in c.COUNTERS};zero['total_tokens']=57
 return {'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':10,'output_tokens':1,'total_tokens':11},'last_token_usage':zero,'model_context_window':1000}}}

def test_context_estimate_is_not_measured_zero_cost(tmp_path):
 p,b,cu=source(tmp_path,[counter()]);ev,pr,_=drain(b,cu);assert not pr['gaps'];d=ev[0]['data']
 assert d['last'] is None and d['countable'] is False
 assert d['context_token_estimate']['total_tokens']==57
 assert d['context_token_estimate']['breakdown_status']=='not_reported'
 assert 'context_estimate_not_response_usage' in d['missingness']
 lane=next(iter(pr['usage'].values()));assert lane['response_usage_sum']=={} and lane['billing_cost'] is None and not lane['complete']

@pytest.mark.parametrize('field,value',[('input_tokens',1),('output_tokens',1),('cached_input_tokens',True),('total_tokens',-1)])
def test_other_counter_contradictions_stay_refused(tmp_path,field,value):
 r=counter();r['payload']['info']['last_token_usage'][field]=value
 p,b,cu=source(tmp_path,[r]);ev,pr,_=drain(b,cu);assert not ev and pr['gaps']

def test_evidenced_list_files_then_read_is_qualified(tmp_path):
 r=large();r['payload']['item']['parsed_cmd'].insert(0,{'type':'list_files','cmd':'opaque','path':'synthetic'})
 p,b,cu=source(tmp_path,[r]);ev,pr,_=drain(b,cu);assert len(ev)==1 and not pr['gaps']

@pytest.mark.parametrize('page_size',[1024,65535,65536,262145])
def test_utf8_and_escape_splits_have_complete_same_digest(tmp_path,page_size):
 r=large();r['payload']['item']['stdout']='x'*1050000+'\\\"\n😀é'*2000
 raw=(json.dumps(r,separators=(',',':'),ensure_ascii=False)+'\n').encode('utf8')
 p,b,cu=source(tmp_path,[])
 with p.open('ab') as f:f.write(raw)
 ev,pr,batches=drain(b,cu,no.Limits(page_bytes=page_size));assert len(ev)==1 and not pr['gaps']
 assert ev[0]['data']['record_digest']==hashlib.sha256(raw).hexdigest()
 assert max(len(json.dumps(batch['cursor'].get('span_commitment'))) for batch in batches)<1600

def test_wire_span_work_yields_and_never_skips_cancel(tmp_path):
 rows=[large(1500000),large(1500000),large(1500000)]
 for i,row in enumerate(rows):row['ordinal']=i+1
 rows.append({'type':'event_msg','ordinal':4,'payload':{'type':'turn_aborted','turn_id':'turn'}})
 p,b,cu=source(tmp_path,rows);ev,pr,batches=drain(b,cu,no.Limits(page_bytes=4*1024*1024))
 assert len(ev)==4 and not pr['gaps'] and ev[-1]['kind']=='lifecycle.cancelled'
 assert all(batch['stream_readback_bytes']<=4*1024*1024 for batch in batches)

@pytest.mark.parametrize('action',['rotate','truncate'])
def test_source_identity_loss_never_reuses_old_commitment(tmp_path,action):
 p,b,cu=source(tmp_path,[large()]);first=no.read_page(b,cu,limits=no.Limits(page_bytes=400000))
 if action=='rotate':
  raw=p.read_bytes();p.rename(p.with_suffix('.retained'));p.write_bytes(raw)
 else:p.write_bytes(p.read_bytes()[:100])
 batch=no.read_page(b,first['cursor']);assert batch['diagnostics'] and not batch['events']

def test_growth_retains_pending_frame_and_normalizes_only_after_newline(tmp_path):
 raw=wire(large());p,b,cu=source(tmp_path,[])
 with p.open('ab') as f:f.write(raw[:-1])
 ev,pr,batches=drain(b,cu);assert not ev and not pr['gaps']
 with p.open('ab') as f:f.write(b'\n')
 next_batch=no.read_page(b,batches[-1]['cursor']);assert len(next_batch['events'])==1 and not next_batch['gaps']

def test_mutation_during_second_current_pass_invalidates(tmp_path,monkeypatch):
 p,b,cu=source(tmp_path,[large()]);base=no._stable_read;read_count=0
 def mutate(stream,path,start,length,identity,size):
  nonlocal read_count
  raw=base(stream,path,start,length,identity,size)
  if start==len(wire(header())):
   read_count+=1
   if read_count==2:p.write_bytes(p.read_bytes().replace(b'"stdout":"x',b'"stdout":"y',1))
  return raw
 monkeypatch.setattr(no,'_stable_read',mutate)
 ev,pr,_=drain(b,cu);assert not ev and (pr['gaps'] or pr['diagnostics'])

@pytest.mark.parametrize('mutation',['timestamp','array-bound','duration-type','bool-time','trailing-duplicate','foreign-session','unknown-status'])
def test_span_semantic_metadata_controls(tmp_path,mutation):
 r=large()
 if mutation=='timestamp':r['timestamp']='2026-99-99T99:00:00Z'
 if mutation=='array-bound':r['payload']['item']['command']=['x']*257
 if mutation=='duration-type':r['payload']['item']['duration']['secs']=1.2
 if mutation=='bool-time':r['payload']['started_at_ms']=False
 if mutation=='trailing-duplicate':r['payload']['item']['parsed_cmd']=[{'type':'list_files','cmd':'x','path':'x','name':'bad'}]
 if mutation=='foreign-session':r['session_id']='foreign'
 if mutation=='unknown-status':r['payload']['item']['status']='future'
 p,b,cu=source(tmp_path,[r]);ev,pr,_=drain(b,cu)
 if mutation=='unknown-status':assert ev[0]['status']=='unknown'
 else:assert not ev and pr['gaps']

def test_context_estimate_cannot_relax_measured_response_or_cumulative_arithmetic(tmp_path):
 r=counter();bad=copy.deepcopy(r);bad['payload']['info']['total_token_usage']['total_tokens']=12
 p,b,cu=source(tmp_path,[bad]);ev,pr,_=drain(b,cu);assert not ev and pr['gaps']
 measured={'type':'token_usage_record','payload':{'thread_id':ROOT,'session_id':ROOT,'response_id':'response','turn_id':'turn','root_turn_id':'root-turn','usage':r['payload']['info']['last_token_usage'],'thread_token_usage':None,'turn_token_usage':None}}
 p,b,cu=source(tmp_path,[measured],suffix='measured');ev,pr,_=drain(b,cu);assert not ev and pr['gaps']

def test_estimate_replay_and_later_measured_usage_are_not_double_counted(tmp_path):
 from test_native_codex import COUNTS
 estimate=counter();measured={'type':'token_usage_record','payload':{'thread_id':ROOT,'session_id':ROOT,'response_id':'response','turn_id':'turn','root_turn_id':'root-turn','usage':COUNTS,'thread_token_usage':None,'turn_token_usage':None}}
 p,b,cu=source(tmp_path,[estimate,measured]);ev,pr,batches=drain(b,cu);assert not pr['gaps']
 again=copy.deepcopy(pr)
 for batch in batches:again=no.reduce_observations(again,batch)
 assert again==pr
 lanes=list(pr['usage'].values());assert sum(x['response_usage_sum'].get('total_tokens',0) for x in lanes)==COUNTS['total_tokens']
 assert all(x['billing_cost'] is None and x['complete'] is False for x in lanes)
 assert sum(x['unknown_measurements'] for x in lanes)==1

@pytest.mark.parametrize('mutation',['countermissing','counterextra','cumulativebad','counterfloat','counterbool'])
def test_context_shape_exception_is_exact(tmp_path,mutation):
 r=counter();info=r['payload']['info'];last=info['last_token_usage']
 if mutation=='countermissing':last.pop('cache_write_input_tokens')
 if mutation=='counterextra':last['future_counter']=0
 if mutation=='cumulativebad':info['total_token_usage']['input_tokens']=8
 if mutation=='counterfloat':last['reasoning_output_tokens']=0.0
 if mutation=='counterbool':last['reasoning_output_tokens']=False
 p,b,cu=source(tmp_path,[r]);ev,pr,_=drain(b,cu);assert not ev and pr['gaps']

def test_no_cumulative_context_shape_counts_one_unknown_measurement(tmp_path):
 r=counter();r['payload']['info']['total_token_usage']=None
 p,b,cu=source(tmp_path,[r]);ev,pr,_=drain(b,cu)
 assert not pr['gaps'] and sum(l['unknown_measurements'] for l in pr['usage'].values())==1
 assert all(not l['response_usage_sum'] and l['billing_cost'] is None for l in pr['usage'].values())

def test_bounded_revalidation_never_reads_complete_large_body(tmp_path,monkeypatch):
 p,b,cu=source(tmp_path,[large(2140000)]);ev,pr,_=drain(b,cu)
 base=no._stable_read;largest=0
 def read(stream,path,start,length,identity,size):
  nonlocal largest
  largest=max(largest,length);assert length<=no.STREAM_CHUNK_BYTES
  return base(stream,path,start,length,identity,size)
 monkeypatch.setattr(no,'_stable_read',read)
 r=no.revalidate_observations(b,ev,required_interval=(0,p.stat().st_size),max_bytes=8*1024*1024)
 assert r['status']=='current' and largest==no.STREAM_CHUNK_BYTES

@pytest.mark.parametrize('location',['type','payload','item','duration'])
def test_unknown_duplicate_late_fields_all_levels(tmp_path,location):
 raw=wire(large())
 if location=='type':raw=raw[:-2]+b',"type":"event_msg"}\n'
 if location=='payload':raw=raw[:-3]+b',"type":"item_completed"}}\n'
 if location=='item':raw=raw.replace(b'"formatted_output":""',b'"formatted_output":"","future":{"grant":true}')
 if location=='duration':raw=raw.replace(b'"nanos":1',b'"nanos":1,"nanos":2')
 p,b,cu=source(tmp_path,[])
 with p.open('ab') as f:f.write(raw)
 ev,pr,_=drain(b,cu);assert not ev and pr['gaps']

def test_partial_commitment_cannot_forge_gapless_coverage(tmp_path):
 p,b,cu=source(tmp_path,[large()]);batch=no.read_page(b,cu,limits=no.Limits(page_bytes=400000))
 nextcu=batch['cursor'];nextcu['span_commitment']['length']-=1
 with pytest.raises(no.SourceError):no.read_page(b,nextcu)

def test_many_ignored_interval_frames_do_not_reduce_legitimate_coverage(tmp_path):
 filler={'type':'event_msg','payload':{'type':'agent_reasoning','text':'opaque'}}
 p,b,cu=source(tmp_path,[filler]*700+[large()]);ev,pr,_=drain(b,cu)
 assert len(ev)==1 and not pr['gaps']
 assert no.revalidate_observations(b,ev,required_interval=(0,p.stat().st_size),max_bytes=4*1024*1024)['status']=='current'

def test_estimate_preserves_valid_cumulative_delta_and_prior_unknowns(tmp_path):
 before=counter();before['payload']['info']['last_token_usage']={'input_tokens':1,'output_tokens':1,'total_tokens':2}
 after=counter();after['payload']['info']['total_token_usage']={'input_tokens':15,'output_tokens':2,'total_tokens':17}
 p,b,cu=source(tmp_path,[before,after]);ev,pr,_=drain(b,cu);assert not pr['gaps']
 lane=next(iter(pr['usage'].values()));assert lane['known_delta']=={'input_tokens':5,'output_tokens':1,'total_tokens':6}
 assert lane['unknown_measurements']==1 and lane['response_usage_sum']=={} and not lane['complete']
 assert lane['baseline']==before['payload']['info']['total_token_usage']

@pytest.mark.parametrize('bad',['boolean','array','object','nonfinite'])
def test_integer_last_total_not_context_string_or_other_type(tmp_path,bad):
 r=counter();r['payload']['info']['last_token_usage']['total_tokens']={'boolean':True,'array':[1],'object':{},'nonfinite':'Infinity'}[bad]
 p,b,cu=source(tmp_path,[r]);ev,pr,_=drain(b,cu);assert not ev and pr['gaps']

def test_current_span_fails_when_wire_allowance_is_insufficient(tmp_path):
 p,b,cu=source(tmp_path,[large()]);ev,pr,_=drain(b,cu);assert len(ev)==1
 v=no.revalidate_observations(b,ev,max_bytes=1024*1024)
 assert v['status']=='unknown' and v['negative_coverage']=='UNKNOWN' and not v['events']


def test_review_nonzero_interval_counts_boundary_byte(tmp_path,monkeypatch):
 p,b,cu=source(tmp_path,[large()]);ev,_,_=drain(b,cu)
 actual=0;original=no._open
 class Counted:
  def __init__(self,stream):self.stream=stream
  def read(self,*args):
   nonlocal actual
   data=self.stream.read(*args);actual+=len(data);return data
  def __getattr__(self,name):return getattr(self.stream,name)
  def __enter__(self):return self
  def __exit__(self,*args):self.stream.close()
 def counted(*args):
  stream,info=original(*args);return Counted(stream),info
 monkeypatch.setattr(no,'_open',counted)
 observed=no.revalidate_observations(b,ev,required_interval=(b['header_length'],p.stat().st_size),max_bytes=4*1024*1024)
 assert observed['status']=='current'
 assert observed['bytes_read']==actual

@pytest.mark.parametrize('total,accepted',[(2**63-1,True),(2**63,False)])
def test_review_context_estimate_matches_producer_i64(tmp_path,total,accepted):
 row=counter();row['payload']['info']['last_token_usage']['total_tokens']=total
 p,b,cu=source(tmp_path,[row]);events,projection,_=drain(b,cu)
 assert bool(events)==accepted and bool(projection['gaps'])!=accepted

@pytest.mark.parametrize('change',['rewrite','append'])
def test_interval_cannot_assemble_across_source_snapshot_change(tmp_path,monkeypatch,change):
 r=completed_item(70000);r['payload']['item']['stderr']='b'
 old=wire(r);new=old.replace(b'"stdout":"x',b'"stdout":"y',1).replace(b'"stderr":"b"',b'"stderr":"z"',1)
 assert old!=new and len(old)==len(new)
 p,b,cu=source(tmp_path,[r]);original=no._stable_read;changed=False
 def mutate(stream,path,start,length,identity,size):
  nonlocal changed
  raw=original(stream,path,start,length,identity,size)
  if start==b['header_length'] and length==no.STREAM_CHUNK_BYTES and not changed:
   changed=True
   if change=='rewrite':p.write_bytes(wire(header())+new)
   else:
    with p.open('ab') as tail:tail.write(wire({'type':'event_msg','ordinal':2,'payload':{'type':'turn_aborted','turn_id':'turn'}}))
  return raw
 monkeypatch.setattr(no,'_stable_read',mutate)
 result=no.revalidate_observations(b,[],required_interval=(b['header_length'],p.stat().st_size),max_bytes=200000)
 assert changed and result['status']=='invalid'
 assert result['negative_coverage']=='UNKNOWN' and result['interval_events']==[]
