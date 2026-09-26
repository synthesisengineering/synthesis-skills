"""Synthetic producer-shape controls; no private retained history or authority."""
import copy, hashlib, json, sys, tracemalloc
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parent))
import native_observations as no
from test_native_observations import ROOT,source,drain,wire
from test_codex_compacted import compacted,MUTATIONS
from test_native_world_state import settings


def large_context(size=2653719):
 row=compacted();row['ordinal']=1
 value=row['payload'];message=value['replacement_history'][0]
 message['content'][0]['text']='SYNTHETIC INERT HISTORY'
 value['replacement_history']=[copy.deepcopy(message) for _ in range(308)]+value['replacement_history'][1:]
 value['replacement_history_metadata']=[{'client_authored':False} for _ in range(310)]
 body=value['replacement_history'][0]['content'][1]
 body['image_url']=''
 body['image_url']='x'*(size-len(wire(row)))
 assert len(wire(row))==size
 return row


def test_observed_large_compaction_shape_and_cancellation(tmp_path):
 row=large_context();cancel={'type':'event_msg','ordinal':2,'payload':{'type':'turn_aborted','turn_id':'turn'}}
 p,b,cu=source(tmp_path,[row,cancel]);ev,pr,batches=drain(b,cu,no.Limits(page_bytes=65536))
 assert [e['kind'] for e in ev]==['context.compaction','lifecycle.cancelled']
 assert not pr['gaps'] and not pr['diagnostics'] and not pr['usage'] and not pr['pairs']
 d=ev[0]['data'];assert d['replacement_history_count']==310
 assert d['record_digest']==hashlib.sha256(wire(row)).hexdigest()
 assert d['commitment_algorithm']=='codex-compaction-wire-sha256-v1'
 assert not any(k in d for k in ('message_digest','replacement_history_digest','retained_context_digest'))
 assert d['history_replayed'] is False and d['retained_usage_counted'] is False and d['grants_authority'] is False
 assert len(wire(ev[0]))<8192 and 'SYNTHETIC INERT HISTORY' not in json.dumps(ev)
 assert all(x['stream_readback_bytes']<=no.MAX_STREAM_SPAN_BYTES for x in batches)
 result=no.revalidate_observations(b,ev,required_interval=(0,p.stat().st_size),max_bytes=8*1024*1024)
 assert result['status']=='current' and result['negative_coverage']=='CURRENT_BOUNDED_INTERVAL'
 again=copy.deepcopy(pr)
 for batch in batches:again=no.reduce_observations(again,batch)
 assert again==pr


def test_observed_settings_without_active_profile_is_inert(tmp_path):
 row=settings();del row['payload']['thread_settings']['active_permission_profile']
 p,b,cu=source(tmp_path,[row]);ev,pr,_=drain(b,cu)
 assert len(ev)==1 and ev[0]['kind']=='context.settings' and not pr['gaps']
 d=ev[0]['data'];assert not d['grants_authority'] and not d['settings_applied'] and not d['effects_replayed']
 assert no.revalidate_observations(b,ev,required_interval=(0,p.stat().st_size))['status']=='current'


@pytest.mark.parametrize('path,key,value',MUTATIONS)
def test_large_compaction_preserves_closed_owner_schema(tmp_path,path,key,value):
 row=large_context(1200000);at=row
 for part in path:at=at[part]
 at[key]=value
 p,b,cu=source(tmp_path,[row]);ev,pr,_=drain(b,cu)
 assert not ev and pr['gaps']


@pytest.mark.parametrize('value',[None,False,{}, {'id':'x','future':True}])
def test_present_active_profile_is_still_strict(tmp_path,value):
 row=settings();row['payload']['thread_settings']['active_permission_profile']=value
 p,b,cu=source(tmp_path,[row]);ev,pr,_=drain(b,cu);assert not ev and pr['gaps']


@pytest.mark.parametrize('fault',['duplicate','utf8','partial','unknown_body','metadata_nodes','metadata_string','oversize'])
def test_streamed_context_wire_and_memory_refusals(tmp_path,fault):
 row=large_context(1200000)
 if fault=='unknown_body':row['payload']['replacement_history'][-1]['future']='x'*600
 if fault=='metadata_nodes':
  row['payload']['replacement_history']*=4;row['payload']['replacement_history_metadata']*=4
 if fault=='metadata_string':row['payload']['window_id']='x'*513
 if fault=='oversize':row=large_context(no.MAX_STREAM_SPAN_BYTES+1)
 raw=wire(row)
 if fault=='duplicate':raw=raw.replace(b'"window_number":2',b'"window_number":2,"window_number":2')
 if fault=='utf8':raw=raw.replace(b'"image_url":"x',b'"image_url":"\xff',1)
 if fault=='partial':raw=raw[:-2]
 p,b,cu=source(tmp_path,[])
 with p.open('ab') as f:f.write(raw)
 ev,pr,batches=drain(b,cu);assert not ev
 if fault=='partial':assert batches[-1]['cursor']['trusted_through']<p.stat().st_size
 else:assert pr['gaps']


@pytest.mark.parametrize('when',['prior_page','second_pass','last_interval_chunk'])
def test_compaction_rejects_changed_complete_source(tmp_path,monkeypatch,when):
 row=large_context(1200000);p,b,cu=source(tmp_path,[row]);base=no._stable_read;count=0
 def mutate(stream,path,start,length,identity,size):
  nonlocal count
  raw=base(stream,path,start,length,identity,size)
  if start==b['header_length']:count+=1
  if (when=='second_pass' and count==2) or (when=='last_interval_chunk' and start+length==size):
   current=p.read_bytes();p.write_bytes(current.replace(b'"image_url":"x',b'"image_url":"y',1))
  return raw
 if when=='prior_page':
  first=no.read_page(b,cu,limits=no.Limits(page_bytes=400000))
  p.write_bytes(p.read_bytes().replace(b'"image_url":"x',b'"image_url":"y',1))
  ev,pr,_=drain(b,first['cursor']);assert not ev and (pr['gaps'] or pr['diagnostics'])
 elif when=='second_pass':
  monkeypatch.setattr(no,'_stable_read',mutate);ev,pr,_=drain(b,cu)
  assert not ev and (pr['gaps'] or pr['diagnostics'])
 else:
  monkeypatch.setattr(no,'_stable_read',mutate)
  result=no.revalidate_observations(b,[],required_interval=(0,p.stat().st_size),max_bytes=8*1024*1024)
  assert result['status']!='current' and result['negative_coverage']=='UNKNOWN'


def test_stream_physical_accounting_and_bounded_memory(tmp_path,monkeypatch):
 row=large_context();p,b,cu=source(tmp_path,[row]);base=no._open;read_bytes=0;largest=0
 class Count:
  def __init__(self,fp):self.fp=fp
  def __getattr__(self,k):return getattr(self.fp,k)
  def __enter__(self):return self
  def __exit__(self,*args):return self.fp.__exit__(*args)
  def read(self,n=-1):
   nonlocal read_bytes,largest
   assert 0<=n<=no.STREAM_CHUNK_BYTES
   result=self.fp.read(n);read_bytes+=len(result);largest=max(largest,n);return result
 def opened(*args,**kwargs):
  fp,st=base(*args,**kwargs);return Count(fp),st
 monkeypatch.setattr(no,'_open',opened)
 size=len(wire(row));account={'bytes_read':0};tracemalloc.start()
 _,facts,digest=no._stream_command(b,b['header_length'],size,accounting=account)
 _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
 assert account['bytes_read']==read_bytes==4*len(wire(row))
 assert largest==no.STREAM_CHUNK_BYTES and peak<8*1024*1024
 assert facts[0]['data']['record_digest']==digest
 (tmp_path/'memory.json').write_text(json.dumps({'peak_python_bytes':peak,'physical_bytes':read_bytes}))


def test_observed_resize_notice_is_inert_content(tmp_path):
 row=compacted();row['payload']['replacement_history'][0]['internal_chat_message_metadata_passthrough']['content_item_kinds'][0]='images.resize_notice'
 p,b,cu=source(tmp_path,[row]);ev,pr,_=drain(b,cu)
 assert len(ev)==1 and ev[0]['kind']=='context.compaction' and not pr['gaps']
 assert ev[0]['data']['history_replayed'] is False and ev[0]['data']['grants_authority'] is False


@pytest.mark.parametrize('escaped,accepted',[(b'\\ud83d\\ude00',True),(b'\\ud800',False),(b'\\udc00',False),(b'\\ud800x',False),(b'\\ud800\\u0000',False)])
def test_compaction_escaped_unicode_is_complete(tmp_path,escaped,accepted):
 raw=wire(large_context(1200000)).replace(b'"image_url":"x',b'"image_url":"'+escaped,1)
 p,b,cu=source(tmp_path,[])
 with p.open('ab') as f:f.write(raw)
 ev,pr,_=drain(b,cu,no.Limits(page_bytes=65535))
 if accepted:assert len(ev)==1 and not pr['gaps']
 else:assert not ev and pr['gaps']


@pytest.mark.parametrize('size',[no.MAX_RECORD_READBACK_BYTES+1,no.MAX_STREAM_SPAN_BYTES])
def test_exact_large_context_wire_edges(tmp_path,size):
 p,b,cu=source(tmp_path,[large_context(size)]);ev,pr,_=drain(b,cu)
 assert len(ev)==1 and not pr['gaps'] and not pr['diagnostics']


def test_large_compaction_keeps_existing_accounting_and_prior_gap(tmp_path):
 from test_codex_compacted import usage,COUNTS
 measured={'type':'token_usage_record','payload':usage()}
 row=large_context(1200000)
 for key in ('usage','turn_token_usage','thread_token_usage'):
  row['payload']['latest_token_usage_record'][key]={k:0 for k in COUNTS}
 p,b,cu=source(tmp_path,[measured,{'type':'future','payload':{}},row,measured])
 ev,pr,batches=drain(b,cu)
 assert pr['gaps'] and batches[-1]['cursor']['first_gap'] is not None
 lane=next(iter(pr['usage'].values()))
 assert lane['response_usage_sum']==COUNTS and lane['epoch_count']==1 and lane['billing_cost'] is None
 again=copy.deepcopy(pr)
 for batch in batches:again=no.reduce_observations(again,batch)
 assert again==pr


@pytest.mark.parametrize('fault',['unknown','missing_permission_profile'])
def test_omitted_active_profile_does_not_relax_other_settings(tmp_path,fault):
 row=settings();value=row['payload']['thread_settings'];del value['active_permission_profile']
 if fault=='unknown':value['future']=True
 else:del value['permission_profile']
 p,b,cu=source(tmp_path,[row]);ev,pr,_=drain(b,cu);assert not ev and pr['gaps']


def test_unicode_pair_validation_survives_serialized_chunk_boundaries():
 raw=b'{"body":"'+b'\\ud83d\\ude00'+b'"}'
 state=None
 for byte in raw:
  parser=no._StreamJSON(state);parser.feed(bytes([byte]));state=json.loads(json.dumps(parser.s))
 assert parser.finish()
 for invalid in (b'\\ud800',b'\\udc00',b'\\ud800\\ud800'):
  parser=no._StreamJSON()
  for byte in b'{"body":"'+invalid+b'"}':parser.feed(bytes([byte]))
  assert not parser.finish()


@pytest.mark.parametrize('value',[None,False,1,[],"invalid",["active_permission_profile"]])
@pytest.mark.parametrize('entrypoint',["direct_owner","source_reader"])
def test_malformed_settings_container_is_a_dialect_gap(tmp_path,value,entrypoint):
 import native_codex as codex
 from test_native_world_state import P
 row=settings();row['payload']['thread_settings']=value
 if entrypoint=='direct_owner':
  with pytest.raises(codex.DialectError):codex.decode_record(row,P)
 else:
  p,b,cu=source(tmp_path,[row]);ev,pr,batches=drain(b,cu)
  assert not ev and pr['gaps'] and not pr['diagnostics']
  assert pr['gaps'][0]['code']=='unobservable_record'
  assert batches[-1]['cursor']['first_gap'] is not None



@pytest.mark.parametrize("prior_version",["codex-dialect-v8","codex-dialect-v9"])
def test_current_decoder_requires_explicit_prior_generation_reconciliation(tmp_path,monkeypatch,prior_version):
 import native_codex as codex
 from test_codex_compacted import usage
 # Hold source fingerprints constant to isolate the human-readable dialect
 # version guard. Source hashes independently guard a deployed code change.
 with monkeypatch.context() as prior:
  prior.setattr(codex,'ADAPTER_VERSION',prior_version)
  p,b,cu=source(tmp_path,[{'type':'token_usage_record','payload':usage()},
                         {'type':'future','payload':{}}])
  ev,projection,batches=drain(b,cu)
  old_cursor=copy.deepcopy(batches[-1]['cursor'])
 assert b['producer']['adapter_version']==prior_version
 snapshot=copy.deepcopy((b,old_cursor,projection))
 assert projection['gaps'] and projection['usage'] and old_cursor['first_gap'] is not None
 # A new observation cannot be translated through the prior generation.
 with p.open('ab') as stream:stream.write(wire(settings()))
 refused=no.read_page(b,old_cursor)
 assert not refused['events'] and refused['consumed_range'] is None
 assert refused['cursor']==old_cursor and refused['source_generation']==b['generation']
 assert any('producer binding changed' in item['detail'] for item in refused['diagnostics'])
 current=no.revalidate_observations(b,ev,required_interval=(0,p.stat().st_size))
 assert current['status']=='invalid' and current['negative_coverage']=='UNKNOWN'
 reduced=no.reduce_observations(projection,refused)
 assert reduced['gaps']==projection['gaps'] and reduced['usage']==projection['usage']
 assert (b,old_cursor,projection)==snapshot
 # A separately requested candidate enrollment starts at the beginning, keeps
 # the old generation intact and supplies no authority to discard its gap.
 fresh,fresh_cursor=no.enroll_source(p,client='codex',expected_root_session_id=ROOT)
 assert fresh['producer']['adapter_version']=='codex-dialect-v10'
 assert fresh['generation']!=b['generation'] and fresh_cursor['offset']==0
 assert fresh['authentication']=='owner_admission_required'
 assert (b,old_cursor,projection)==snapshot
