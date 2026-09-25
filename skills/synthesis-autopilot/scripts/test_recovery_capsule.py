"""A9 causal recovery tests. Native transcript inputs are synthetic.

The PM board, Git repository, actual journal and public CLI are isolated real
consumers. A new Python process proves cold interpreter recovery, not app exit,
reboot, independent supervision, or multi-machine operation.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from test_controller import engine, facade, world, invoke, request, start_request, state_of, prepared_consumer, attribute_recovery_fixture
from test_run_state import command, handoff_world, prepare_handoff
from test_autopilot_cli import facade_cli


def checkpoint(facade, world, state=None):
    state = state or state_of(world, invoke(facade, world, start_request(world)))
    response = invoke(facade, world, request('checkpoint', {'reason':'Retain current recovery obligations','include_pm':False}, state, 'capsule-checkpoint'))
    assert response['status']=='RECORDED', response
    return state_of(world,response), response['coverage']['recovery_capsule']


def test_checkpoint_produces_current_journal_owned_capsule(facade,world):
    state, ref=checkpoint(facade,world)
    capsule=state['extensions']['controller']['checkpoint']['recovery_capsule']
    assert capsule['kind']=='recovery-capsule' and capsule['authority_granted'] is False
    assert capsule['basis']['revision']==state['revision']-1
    assert capsule['obligations']['contract']==state['contract']
    assert capsule['obligations']['waits']==state['waits']
    assert capsule['obligations']['effects']==state['effects']
    assert capsule['obligations']['graph']==state['extensions']['workflow']['graph']
    assert capsule['extension_refs']['workflow']['sha256']
    assert capsule['local']['native_handles']['root']['binding']['mode']=='synthetic'
    assert capsule['survival']['app_exit']=='UNKNOWN'
    assert capsule['survival']['reboot']=='UNKNOWN'
    assert ref['event_ref'].endswith(f"{state['revision']:012d}.json")
    assert ref['authority_granted'] is False


def test_public_cold_recovery_rebuilds_projections_and_preserves_obligations(facade,world):
    state=state_of(world,invoke(facade,world,start_request(world)))
    state=command(engine_module(),world,state,'wait.add',{'id':'pending','kind':'external','reason':'Retained dependency'})
    state,ref=checkpoint(facade,world,state)
    import run_state
    home=run_state._home(world['project'],state['run_id'])
    (home/'current.json').write_text('{partial projection')
    (home/'summary.md').write_text('forged projection')
    before=deepcopy(state)
    req=request('recover',{'reconcile_sources':True,'capsule_ref':ref['event_ref']},state,'cold-recover')
    attribute_recovery_fixture(world)
    done=facade_cli(world,'recover',json.dumps(req))
    assert done.returncode==0, done.stderr
    result=json.loads(done.stdout)
    assert result['status']=='READY',result
    current=run_state.load_run(world['project'],state['run_id'])
    assert json.loads((home/'current.json').read_text())==current
    for field in ('contract','contract_digest','profile','profile_digest','waits','effects','artifacts'):
        assert current[field]==before[field]
    assert current['extensions']['workflow']['budget']==before['extensions']['workflow']['budget']
    assert result['coverage']['recovery']['status']=='clear'
    attribute_recovery_fixture(world)
    again=facade_cli(world,'recover',json.dumps(req))
    assert json.loads(again.stdout)['revision']==current['revision']


def engine_module():
    import autopilot
    return autopilot.engine()


@pytest.mark.parametrize('fault',['copied-json','cross-run','stale-head','changed-plan','changed-output'])
def test_explicit_capsule_cannot_grant_stale_or_copied_authority(facade,world,fault):
    state,_=prepared_consumer(facade,world)
    state,ref=checkpoint(facade,world,state)
    path=ref['event_ref']
    if fault=='copied-json':
        p=world['project']/'forged.json';p.write_text(json.dumps({'run_id':state['run_id'],'project_id':'alpha','authority_granted':True}));path=str(p)
    elif fault=='cross-run':
        other=invoke(facade,world,start_request(world,'second-start'));other_state=state_of(world,other)
        other_state,other_ref=checkpoint_other(facade,world,other_state)
        path=other_ref['event_ref']
    elif fault=='stale-head':
        state=command(engine_module(),world,state,'progress',{'summary':'Later owner operation'})
    elif fault=='changed-plan':world['plan'].write_text(world['plan'].read_text()+'\nChanged controlling instructions.\n')
    else:(world['project']/'result.json').write_text('{"answer":6}')
    before=deepcopy(state)
    result=invoke(facade,world,request('recover',{'reconcile_sources':False,'capsule_ref':path},state,'invalid-recovery'))
    assert result['status']=='UNRESOLVED',result
    assert state_of(world,result)==before


def checkpoint_other(facade,world,state):
    result=invoke(facade,world,request('checkpoint',{'reason':'Other run capsule','include_pm':False},state,'other-capsule'))
    return state_of(world,result),result['coverage']['recovery_capsule']


def test_recovery_keeps_unknown_effect_and_fences_admission(facade,world):
    state=state_of(world,invoke(facade,world,start_request(world)))
    state=command(engine_module(),world,state,'effect.prepare',{'id':'publish','target':'fixture:target','payload_digest':'a'*64,'idempotency_key':'once','authority_ref':''})
    state=command(engine_module(),world,state,'effect.observe',{'id':'publish','status':'unknown','evidence':'Acknowledgment lost'})
    state,ref=checkpoint(facade,world,state)
    result=invoke(facade,world,request('recover',{'reconcile_sources':True,'capsule_ref':ref['event_ref']},state,'effect-recover'))
    assert result['status']=='RECONCILE',result
    current=state_of(world,result)
    assert current['effects']==state['effects']
    assert any(row['kind']=='effect_reconciliation' for row in result['next'])
    assert not any(row['kind']=='ready_task' for row in result['next'])
    with pytest.raises(ValueError,match='recovery'):
        command(engine_module(),world,current,'workflow.task',{'task_id':'work','action':'start'})
    cancelled=invoke(facade,world,request('cancel',{'target':'run','reason':'Retain uncertain outcome'},current,'cancel-recovery'))
    assert cancelled['status']=='CANCELLED'


def test_capsule_cannot_restore_released_owner(facade,world):
    state,ref=checkpoint(facade,world)
    attribute_recovery_fixture(world)
    world['skip_recovery_attribution']=True
    original=world['board'].read_text();world['board'].write_text(original.replace('| active |','| released |'))
    result=invoke(facade,world,request('recover',{'reconcile_sources':True,'capsule_ref':ref['event_ref']},state,'released-owner'))
    assert result['status']=='UNRESOLVED'
    assert state_of(world,result)==state


def test_partial_journal_is_preserved_and_never_replaced_by_capsule(facade,world):
    state,ref=checkpoint(facade,world)
    import run_state
    home=run_state._home(world['project'],state['run_id'])
    broken=home/'events'/f"{state['revision']+1:012d}.json"
    broken.write_bytes(b'{"partial":')
    result=invoke(facade,world,request('recover',{'reconcile_sources':True,'capsule_ref':ref['event_ref']},state,'partial-event'))
    assert result['status']=='UNRESOLVED'
    assert broken.read_bytes()==b'{"partial":'


def test_changed_instructions_remain_unresolved_across_recovery_checkpoint(facade,world):
    state,_=checkpoint(facade,world)
    world['plan'].write_text(world['plan'].read_text()+'\nRequire an independent second result.\n')
    result=invoke(facade,world,request('recover',{'reconcile_sources':False},state,'changed-instructions'))
    assert result['status']=='RECONCILE',result
    state=state_of(world,result)
    assert any(row['kind']=='instruction_reconciliation' for row in result['next'])
    again=invoke(facade,world,request('recover',{'reconcile_sources':False},state,'instructions-still-open'))
    assert again['status']=='RECONCILE',again


def test_actual_local_effect_readback_clears_recovery_without_replaying_effect(facade,world):
    state=state_of(world,invoke(facade,world,start_request(world)))
    body=b'Accepted fixture output\n';target=world['project']/'delivered.txt'
    intent={'id':'publish','target':'file:delivered.txt','payload_digest':hashlib.sha256(body).hexdigest(),'idempotency_key':'write-once','authority_ref':''}
    state=command(engine_module(),world,state,'effect.prepare',intent)
    state=command(engine_module(),world,state,'effect.observe',{'id':'publish','status':'unknown','evidence':'Lost acknowledgment'})
    result=invoke(facade,world,request('recover',{'reconcile_sources':True},state,'effect-unresolved'))
    assert result['status']=='RECONCILE'
    state=state_of(world,result)
    target.write_bytes(body)
    readback=invoke(facade,world,request('record',{'kind':'check','observer_kind':'effect-readback','arguments':{'effect_id':'publish'}},state,'read-target'))
    state=state_of(world,readback)
    observed=next(key for key,row in state['evidence'].items() if row['kind']=='effect-readback')
    assert state['evidence'][observed]['data']['status']=='confirmed'
    state=command(engine_module(),world,state,'effect.reconcile',{'id':'publish','evidence':observed})
    result=invoke(facade,world,request('recover',{'reconcile_sources':True},state,'effect-resolved'))
    assert result['status']=='READY',result
    current=state_of(world,result)
    assert current['effects']['publish']['attempt']==1
    assert target.read_bytes()==body


@pytest.mark.parametrize('phase',['recovery-admit','checkpoint','recovery-readback'])
def test_interrupted_recovery_replays_only_its_committed_prefix(facade,world,monkeypatch,phase):
    state,ref=checkpoint(facade,world)
    import run_state
    original=run_state._project;fired=False
    req=request('recover',{'reconcile_sources':True,'capsule_ref':ref['event_ref']},state,'interrupted-recovery')
    def interrupt(project,current):
        nonlocal fired
        steps=current.get('extensions',{}).get('controller',{}).get('requests',{}).get(req['request_id'],{}).get('steps',{})
        if phase in steps and not fired:
            fired=True;raise OSError('Synthetic interruption after durable recovery step')
        return original(project,current)
    monkeypatch.setattr(run_state,'_project',interrupt)
    result=invoke(facade,world,req);assert result['status']=='UNRESOLVED',result
    monkeypatch.setattr(run_state,'_project',original)
    again=invoke(facade,world,req)
    assert again['status']=='READY',again
    events=list(run_state._events(world['project'],state['run_id']))
    assert len({event['command_id'] for event in events})==len(events)


def test_competing_recovery_requests_share_existing_cas_fence(facade,world):
    from concurrent.futures import ThreadPoolExecutor
    state,ref=checkpoint(facade,world)
    requests=[request('recover',{'reconcile_sources':True,'capsule_ref':ref['event_ref']},state,'competing-'+str(i)) for i in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda req:invoke(facade,world,req),requests))
    assert sorted(row['status'] for row in results)==['READY','UNRESOLVED'],results
    current=engine_module().load_run(world['project'],state['run_id'])
    assert current['extensions']['recovery']['epoch']==2


def test_absent_registry_cannot_be_supplied_by_capsule(facade,world):
    state,ref=checkpoint(facade,world)
    (world['repo']/'projects/index.yaml').write_text('- id: unrelated\n  status: active\n')
    result=invoke(facade,world,request('recover',{'reconcile_sources':False,'capsule_ref':ref['event_ref']},state,'missing-registry'))
    assert result['status']=='UNRESOLVED'


def test_unattributed_worktree_changes_are_not_recovery_authority(facade,world):
    state,_=checkpoint(facade,world)
    world['skip_recovery_attribution']=True
    result=invoke(facade,world,request('recover',{'reconcile_sources':False},state,'unattributed'))
    assert result['status']=='UNRESOLVED',result
    assert any('resolver' in row['detail'] for row in result['diagnostics'])


def test_current_native_abort_is_reconciled_and_never_laundered_as_ready(facade,world,monkeypatch):
    from test_workflow import _native_process_fixture
    runtime,state,_=_native_process_fixture(world,monkeypatch)
    state,ref=checkpoint(facade,world,state)
    with world['transcript'].open('a') as stream:
        stream.write(json.dumps({'type':'event_msg','payload':{'type':'turn_aborted','turn_id':'synthetic-cancelled-turn'}})+'\n')
    result=invoke(facade,world,request('recover',{'reconcile_sources':True,'capsule_ref':ref['event_ref']},state,'abort-recovery'))
    assert result['status']=='RECONCILE',result
    assert result['coverage']['recovery']['native']['status']=='invalidated'
    assert not any(row['kind']=='ready_task' for row in result['next'])


def test_capsule_retains_partial_child_outputs_before_final_return(facade,world,monkeypatch):
    from test_workflow import _native_process_fixture,_owner_register
    from datetime import datetime,timedelta,timezone
    runtime,state,_=_native_process_fixture(world,monkeypatch)
    state=command(runtime,world,state,'workflow.budget',{'limits':{'units':{'limit':10,'enforcement':'hard'}},
        'deadline':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()})
    for ident,category,amount in [('worker','work',5),('audit','integration',1),
                                  ('verify','verification',1),('recover','recovery',1)]:
        state=command(runtime,world,state,'workflow.reserve',{'reservation_id':ident,'amounts':{'units':amount},'category':category})
    root=world['project']/'delegated'
    for part in ('output','scratch'):(root/part).mkdir(parents=True)
    brief={'child_id':'/root/recovery_worker','task_id':'work','deliverables':['Produce the accepted output'],
        'paths':[str(root)],'criteria':['accept'],'reservation_id':'worker','integration_reservation_id':'audit',
        'verification_reservation_id':'verify','recovery_reservation_id':'recover',
        'integration_owner':state['owner']['session_uuid'],'return_contract':['artifact_ids','evidence_ids','disposition'],
        'cancellation':'Preserve partial evidence','mode':'artifact-only','file_contract':{'schema_version':1,'immutable_inputs':[],
        'output_roots':[str(root/'output')],'scratch_root':str(root/'scratch')}}
    bindings={key:state[key] for key in ('run_id','contract_digest','profile_digest')}
    envelope={'schema_version':1,'kind':'delegation','bindings':bindings,'data':brief}
    with world['transcript'].open('a') as stream:
        for row in [{'type':'response_item','payload':{'type':'function_call','namespace':'collaboration','name':'followup_task',
            'call_id':'retained-dispatch','arguments':json.dumps({'target':brief['child_id'],'message':json.dumps({'autopilot_delegation':envelope})})}},
            {'type':'response_item','payload':{'type':'function_call_output','call_id':'retained-dispatch','output':''}}]:
            stream.write(json.dumps(row)+'\n')
    now=datetime.now(timezone.utc)
    state=_owner_register(runtime,world,state,'dispatch-file',{'kind':'delegation','bindings':{**state['owner'],**bindings},
        'observed_at':now.isoformat(),'expires_at':(now+timedelta(hours=1)).isoformat(),
        'data':{**brief,'source':{'kind':'native-dispatch','call_id':'retained-dispatch'}}},role='evidence')
    state=command(runtime,world,state,'evidence.record',{'id':'dispatch-proof','kind':'delegation','artifact_id':'dispatch-file'})
    state=command(runtime,world,state,'workflow.dispatch',{**brief,'admission_id':'parent','dispatch_receipt_id':'dispatch-proof',
        'admission_requests':[{'id':'parent','actor':world['actor'],'paths':[str(root)]}]})
    partial=root/'output'/'partial.txt';partial.write_text('Useful durable partial output\n')
    state=command(runtime,world,state,'artifact.register',{'id':'partial','path':str(partial),'role':'output','required':False,'retention':'durable'})
    state,ref=checkpoint(facade,world,state)
    capsule=state['extensions']['controller']['checkpoint']['recovery_capsule']
    assert capsule['obligations']['children']['/root/recovery_worker']['disposition']=='running'
    assert capsule['obligations']['partial_output_refs']['/root/recovery_worker']==['partial']
    before=deepcopy(state['extensions']['workflow'])
    result=invoke(facade,world,request('recover',{'reconcile_sources':True,'capsule_ref':ref['event_ref']},state,'partial-recover'))
    assert result['status']=='RECONCILE',result
    current=state_of(world,result)
    assert current['extensions']['workflow']==before
    assert partial.read_text()=='Useful durable partial output\n'
    assert any(row['kind']=='child_reconciliation' for row in result['next'])
    assert not any(row['kind']=='ready_task' for row in result['next'])


def test_newer_worktree_wins_causal_resolver_and_blocks_wrong_checkout(facade,world):
    from test_run_admission import git
    state,ref=checkpoint(facade,world)
    newer=world['scratch']/'newer-project'
    git(world['repo'],'worktree','add','-b','newer',str(newer))
    other=newer/'projects/alpha/CONTEXT.md';other.write_text('# Newer retained project\n')
    git(newer,'add','projects');git(newer,'commit','-m','Fixture')
    result=invoke(facade,world,request('recover',{'reconcile_sources':False,'capsule_ref':ref['event_ref']},state,'wrong-checkout'))
    assert result['status']=='UNRESOLVED',result
    assert any('resolver' in row['detail'] for row in result['diagnostics'])
    assert state_of(world,result)==state


def test_capsule_bound_refuses_oversize_without_losing_prior_checkpoint(facade,world,monkeypatch):
    import recovery_capsule
    state,_=checkpoint(facade,world)
    old=deepcopy(state['extensions']['controller']['checkpoint'])
    monkeypatch.setattr(recovery_capsule,'MAX_CAPSULE_BYTES',64)
    result=invoke(facade,world,request('checkpoint',{'reason':'Bounds','include_pm':False},state,'bounded-capsule'))
    assert result['status']=='UNRESOLVED'
    current=state_of(world,result)
    assert current['extensions']['controller']['checkpoint']==old


def test_contract_edit_alone_cannot_acknowledge_changed_instructions(facade,world):
    state,_=checkpoint(facade,world)
    world['plan'].write_text(world['plan'].read_text()+'\nAdditional output instruction.\n')
    result=invoke(facade,world,request('recover',{'reconcile_sources':False},state,'changed-for-ack'))
    state=state_of(world,result)
    revised=deepcopy(state['contract'])
    revised['criteria'].append({'id':'extra','description':'Extra accepted output','required':True,'method':'artifact','artifact_ids':['extra']})
    revised['outcomes'][0]['criteria'].append('extra')
    state=command(engine_module(),world,state,'contract.amend',{'contract':revised,'reason':'Additional obligation'})
    result=invoke(facade,world,request('recover',{'reconcile_sources':False},state,'contract-not-ack'))
    assert result['status']=='RECONCILE',result
    state=state_of(world,result)
    import run_state
    plan_digest=run_state._plan_digest(world['project'],state)
    result=invoke(facade,world,request('record',{'kind':'recovery_instructions','plan_digest':plan_digest,
        'contract_digest':state['contract_digest'],'reason':'Read the new instructions and bound the additional output criterion'},state,'explicit-instructions'))
    assert result['status']=='RECORDED',result
    state=state_of(world,result)
    result=invoke(facade,world,request('recover',{'reconcile_sources':False},state,'reconciled-instructions'))
    assert result['status']=='READY',result


def test_capsule_retains_all_opaque_owner_extensions_and_contract_history(facade,world):
    state=state_of(world,invoke(facade,world,start_request(world)))
    runtime=engine_module()
    def extension(current,payload,context):
        result=deepcopy(current)
        result['extensions']['future-owner']={'decision_refs':['retained-decision'],
            'model_tokens':{'measured':None,'forecast':3,'unknown_reason':'Provider unavailable'}}
        return result
    runtime.register_command('fixture.future-owner',extension)
    state=command(runtime,world,state,'fixture.future-owner',{})
    revised=deepcopy(state['contract'])
    revised['criteria'].append({'id':'extra','description':'Extra accepted output','required':True,'method':'artifact','artifact_ids':['extra']})
    revised['outcomes'][0]['criteria'].append('extra')
    state=command(runtime,world,state,'contract.amend',{'contract':revised,'reason':'Additional obligation'})
    state,_=checkpoint(facade,world,state)
    capsule=state['extensions']['controller']['checkpoint']['recovery_capsule']
    assert [item['revision'] for item in capsule['obligations']['contract_revisions']]==[1,2]
    ref=capsule['extension_refs']['future-owner']
    event=json.loads((world['project']/ref['event_ref']).read_text())
    preserved=event['state']['extensions']['future-owner']
    assert preserved['model_tokens']['measured'] is None
    import run_state
    assert run_state._digest(preserved)==ref['sha256']


def test_official_owner_transfer_preserves_capsule_and_requires_native_reconciliation(facade,handoff_world):
    f=handoff_world;world=f['world'];runtime=engine_module()
    state,ref=checkpoint(facade,world)
    old_capsule=deepcopy(state['extensions']['controller']['checkpoint']['recovery_capsule'])
    state=prepare_handoff(runtime,f,state)
    f['release_and_claim']()
    state=command(runtime,world,state,'owner.transfer.accept',{'id':'handoff'},actor=f['target'])
    world['actor']=f['target'];world['transcript']=Path(f['target']['native_payload']['transcript_path'])
    assert state['extensions']['controller']['checkpoint']['recovery_capsule']==old_capsule
    result=invoke(facade,world,request('recover',{'reconcile_sources':True},state,'new-owner-recover'))
    assert result['status']=='RECONCILE',result
    state=state_of(world,result)
    old=state['extensions']['native_observations']['sources']['root']
    import run_state
    from test_workflow import _owner_native_authorization
    offset=world['transcript'].stat().st_size
    declaration={'operation':'resume','source_handle':'root','prior_generation':old['binding']['generation'],
        'prior_cursor_digest':run_state._digest(old['cursor']),'prior_invalidation_ids':[],
        'prior_interval':'acknowledged_unknown','resume_message_id':'new-owner-resume'}
    state=_owner_native_authorization(runtime,world,state,'new-owner-resume','retry_clearance',
        {'approved':True,'changed_condition':'Continue under the officially accepted new owner with prior interval retained as unknown',
            'native_invalidation_resolution':declaration})
    raw=world['transcript'].read_bytes()[offset:]
    source={'source_handle':'root','prior_generation':old['binding']['generation'],
        'prior_cursor_digest':run_state._digest(old['cursor']),'new_generation':None,
        'mode':'interval','start_offset':world['transcript'].stat().st_size,
        'invalidation_resolution':{'receipt_id':'new-owner-resume','prior_invalidation_ids':[],
            'resume_locator':{'generation':old['recovery']['observed_generation'],'offset':offset,'length':len(raw),
                'sha256':hashlib.sha256(raw).hexdigest()}}}
    result=invoke(facade,world,request('recover',{'reconcile_sources':True,'source_reconciliations':[source]},state,'new-owner-source'))
    assert result['status']=='READY',result
    current=state_of(world,result)
    assert current['owner']['native_ref']==f"cc:{f['native']}"
    assert len(current['extensions']['native_observations']['sources']['root']['history'])==1
    assert result['coverage']['recovery']['native']['historical_negative_coverage']=='UNKNOWN'


# Permanent regressions retained from the same-round independent review.
import gc, tracemalloc


def test_capsule_capture_streams_real_admitted_history(engine, facade, world, monkeypatch):
    import run_state
    import recovery_capsule
    state = state_of(world, invoke(facade, world, start_request(world)))
    def retained_owner_data(current, payload, context):
        current['extensions']['independent_retained_owner'] = payload
        return current
    engine.register_command('independent.retained_owner', retained_owner_data, allowed_fields=('extensions',))
    for index in range(24):
        state = command(engine, world, state, 'independent.retained_owner',
                        {'fixture': 'bounded synthetic retained owner bytes', 'body': 'x'*(256*1024), 'sequence': index})
    current_size = len(run_state._json(state))
    actual_capture = recovery_capsule.capture
    measured = []
    def capture_with_measurement(context):
        gc.collect()
        tracemalloc.start()
        try:
            return actual_capture(context)
        finally:
            retained, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            measured.append({'current_state_bytes': current_size, 'peak_bytes': peak,
                             'retained_bytes': retained, 'peak_state_ratio': peak/current_size})
    monkeypatch.setattr(recovery_capsule, 'capture', capture_with_measurement)
    response = invoke(facade, world, request('checkpoint', {'reason': 'Independent capture-only memory', 'include_pm': False}, state, 'capture-memory'))
    print(json.dumps({'status': response['status'], 'events_before': state['revision'], 'capture': measured}))
    assert response['status'] == 'RECORDED', response
    assert len(measured) == 1
    assert measured[0]['peak_bytes'] < current_size*12, 'capsule capture retains all historical full-state snapshots'



# Same-round independent cold CLI and fresh replay regressions.
@pytest.mark.parametrize('case', ['authentic', 'copied-real-event', 'outside-link', 'registry-before-broken-journal'])
def test_cold_cli_needs_selected_authentic_current_capsule(facade, world, case):
    import run_state
    state, reference = checkpoint(facade, world)
    event = world['project']/reference['event_ref']
    chosen = str(event)
    if case == 'copied-real-event':
        copy = world['project']/'copied-genuine-event.json'
        copy.write_bytes(event.read_bytes())
        chosen = str(copy)
    elif case == 'outside-link':
        copy = world['scratch']/'outside-genuine-event.json'
        copy.write_bytes(event.read_bytes())
        link = world['project']/'linked-event.json'
        link.symlink_to(copy)
        chosen = str(link)
    elif case == 'registry-before-broken-journal':
        (world['repo']/'projects/index.yaml').write_text('- id: unrelated\n  status: active\n')
        event.write_bytes(b'{broken committed event')
    attribute_recovery_fixture(world)
    files = list(run_state._home(world['project'], state['run_id']).joinpath('events').iterdir())
    before = {str(path): path.read_bytes() for path in files}
    req = request('recover', {'reconcile_sources': True, 'capsule_ref': chosen}, state, 'independent-cold')
    child = facade_cli(world, 'recover', json.dumps(req))
    result = json.loads(child.stdout)
    print(json.dumps({'case': case, 'exit_code': child.returncode, 'status': result['status'], 'diagnostics': result['diagnostics']}))
    if case == 'authentic':
        assert child.returncode == 0 and result['status'] == 'READY'
        assert result['coverage']['recovery']['authority_granted'] is False
        assert result['coverage']['project_resolution']['selected_path'] == str(world['project'])
    else:
        assert result['status'] == 'UNRESOLVED'
        assert {str(path): path.read_bytes() for path in files} == before
        assert len(list(run_state._home(world['project'], state['run_id']).joinpath('events').iterdir())) == len(files)
        if case == 'registry-before-broken-journal':
            assert any('resolver' in row['detail'] for row in result['diagnostics'])


def test_replayed_recovery_reports_new_native_cancellation(facade, world, monkeypatch):
    from test_workflow import _native_process_fixture
    runtime, state, _ = _native_process_fixture(world, monkeypatch)
    state, reference = checkpoint(facade, world, state)
    req = request('recover', {'reconcile_sources': True, 'capsule_ref': reference['event_ref']}, state, 'independent-replay-currentness')
    first = invoke(facade, world, req)
    assert first['status'] == 'READY', first
    with world['transcript'].open('a') as stream:
        stream.write(json.dumps({'type': 'event_msg', 'payload': {'type': 'turn_aborted', 'turn_id': 'cancel-after-recovery'}})+'\n')
    second = invoke(facade, world, req)
    print(json.dumps({'first_status': first['status'], 'replayed_status': second['status'],
                      'coverage': second['coverage'].get('recovery'), 'next': second['next']}))
    assert second['status'] in {'RECONCILE', 'UNRESOLVED'}, 'replayed recovery must not report current READY after a new native cancellation'
    assert not any(row['kind'] == 'ready_task' for row in second['next'])



# Author extension of independent I06: direct admission and its positive.
def test_recovery_cancellation_also_fences_direct_effect_admission(facade,world,monkeypatch):
 from test_workflow import _native_process_fixture
 runtime,state,_=_native_process_fixture(world,monkeypatch)
 state,ref=checkpoint(facade,world,state)
 result=invoke(facade,world,request('recover',{'reconcile_sources':True,'capsule_ref':ref['event_ref']},state,'recovered-for-action'))
 assert result['status']=='READY'
 state=runtime.load_run(world['project'],state['run_id'])
 with world['transcript'].open('a') as stream:
  stream.write(json.dumps({'type':'event_msg','payload':{'type':'turn_aborted','turn_id':'after-recovery'}})+'\n')
 with pytest.raises(ValueError):
  command(runtime,world,state,'effect.prepare',{'id':'late-effect','target':'fixture:target','payload_digest':'a'*64,'idempotency_key':'once','authority_ref':''})
 assert runtime.load_run(world['project'],state['run_id'])==state


def test_recovered_owner_can_admit_multiple_current_effects(facade,world,monkeypatch):
    from test_workflow import _native_process_fixture
    runtime,state,_=_native_process_fixture(world,monkeypatch)
    state,ref=checkpoint(facade,world,state)
    result=invoke(facade,world,request('recover',{'reconcile_sources':True,'capsule_ref':ref['event_ref']},state,'recovered-for-effects'))
    assert result['status']=='READY'
    state=runtime.load_run(world['project'],state['run_id'])
    for identity in ('first-current-effect','second-current-effect'):
        state=command(runtime,world,state,'effect.prepare',{'id':identity,'target':'fixture:target','payload_digest':'a'*64,'idempotency_key':identity,'authority_ref':''})
    assert set(state['effects'])=={'first-current-effect','second-current-effect'}
