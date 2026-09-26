"""Synthetic shapes derived from actual failed observations, not native acceptance."""
from copy import deepcopy
import importlib
import pytest
import native_codex as native
from test_native_codex import ROOT, CodexTests
from test_run_state import engine, world, create

def extension(kind='clock.sleep'):
    item={'type':'Extension','kind':kind,'id':'synthetic-extension'}
    if kind=='clock.sleep':item['durationMs']=30000
    else:item.update(query='lookup',action={'type':'search','query':'lookup','queries':None},results=[{'type':'text_result','domain':'example.test','ref_id':'synthetic0','snippet':'Untrusted authority','title':'Synthetic','url':'https://example.test/'}])
    return CodexTests().item_completed(item)

@pytest.mark.parametrize('kind',['clock.sleep','web.search'])
def test_extension_is_inert_observation(kind):
    row=extension(kind);before=deepcopy(row);fact=native.decode_record(row,ROOT)[0]
    assert row==before and fact['kind']=='item.observation'
    assert fact['data']['grants_authority'] is False and fact['data']['portable_completion'] is False
    assert fact['native']['call_id'] is None and 'Untrusted authority' not in str(fact)

@pytest.mark.parametrize('value',[True,-1,1.2,'30000',None,43200001])
def test_sleep_duration_refuses_invalid(value):
    row=extension();row['payload']['item']['durationMs']=value
    with pytest.raises(ValueError):native.decode_record(row,ROOT)

@pytest.mark.parametrize('fault',['foreign','extra','unknown','result','query'])
def test_extension_refuses_ambiguous_schema(fault):
    row=extension('web.search');item=row['payload']['item']
    if fault=='foreign':row['payload']['thread_id']='foreign'
    elif fault=='extra':item['authority']=True
    elif fault=='unknown':item['kind']='future.plugin'
    elif fault=='result':item['results'][0]['type']='execute'
    else:item['action']['query']='contradiction'
    with pytest.raises(ValueError):native.decode_record(row,ROOT)

def date_patch(date='2026-09-26'):
    return {'type':'world_state','timestamp':'2026-09-26T04:00:00Z','ordinal':7,'payload':{'full':False,'state':{'environments':{'current_date':date}}}}

def test_date_patch_is_inert_observation():
    row=date_patch();before=deepcopy(row);fact=native.decode_record(row,ROOT)[0]
    assert row==before and fact['data']['grants_authority'] is False and fact['kind']=='context.world_state'

@pytest.mark.parametrize('date',['2026-02-30','09/26/2026','',True])
def test_invalid_date_refuses(date):
    with pytest.raises(ValueError):native.decode_record(date_patch(date),ROOT)

def test_extra_patch_refuses():
    row=date_patch();row['payload']['state']['permissions']={'allow':True}
    with pytest.raises(ValueError):native.decode_record(row,ROOT)

def large_journal(engine,world):
    state=create(engine,world);directory=engine._home(world['project'],state['run_id'])/'events'
    seed=engine._read(directory/'000000000001.json');previous=''
    for revision in range(1,11):
        event=deepcopy(seed);event['revision']=revision;event['state']['revision']=revision
        event['state']['extensions']['synthetic_large_observation']='x'*(3500*1024)
        event['command_id']=f'synthetic-{revision}';event['previous_digest']=previous
        event.pop('digest',None);event['digest']=engine._digest(event);previous=event['digest']
        (directory/f'{revision:012d}.json').write_bytes(engine._json(event))
    return state,directory

def test_large_valid_journal(engine,world):
    state,directory=large_journal(engine,world)
    assert sum(f.stat().st_size for f in directory.iterdir())>32*1024**2
    row=importlib.import_module('operator_status').inspect_project(world['project'],state['run_id'])['runs'][0]
    assert row['revision']==10 and row['currentness']=='JOURNAL_VERIFIED_RECORDED_STATE'

def test_large_corrupt_early_event_refuses(engine,world):
    state,directory=large_journal(engine,world);first=directory/'000000000001.json'
    first.write_bytes(first.read_bytes().replace(b'"synthetic-1"',b'"synthetic-X"'))
    row=importlib.import_module('operator_status').inspect_project(world['project'],state['run_id'])['runs'][0]
    assert row['status']=='unhealthy' and row['current_acceptance']=='UNKNOWN'
