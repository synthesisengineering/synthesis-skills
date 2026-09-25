"""Real PM/journal permit controls; native fixture inputs remain synthetic."""
from copy import deepcopy
import hashlib
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest
from test_controller import engine,facade,world,invoke,request,start_request,state_of,attribute_recovery_fixture

TOKEN='isolated-fixture-token-0123456789abcdef0123456789abcdef'


def prepared(facade,world):
    import prepared_native_launch as owner
    seed=start_request(world)
    seed['input']['outcome_contract']['authority_refs']=['explicit-service-enrollment']
    state=state_of(world,invoke(facade,world,seed))
    state=state_of(world,invoke(facade,world,request('record',{'kind':'supervision','action':'enroll',
        'authority_ref':'explicit-service-enrollment','max_requests':4,'max_attempts':2,
        'lease_seconds':30,'backoff_seconds':10},state,'enroll')))
    payload={'kind':'launch_prepare','permit_id':'permit1','authority_ref':'explicit-service-enrollment',
        'token_sha256':hashlib.sha256(TOKEN.encode()).hexdigest(),
        'expires_at':(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat(),
        'max_wall_seconds':60,'max_output_bytes':65536}
    result=invoke(facade,world,request('record',payload,state,'prepare-launch'))
    assert result['status']=='RECORDED',result
    return state_of(world,result)


def test_current_native_owner_prepares_exact_one_shot_without_service_actor(facade,world):
    state=prepared(facade,world)
    grant=state['extensions']['prepared_native_launch']['permits']['permit1']
    assert grant['status']=='prepared'
    assert grant['issuer']['native_ref']==state['owner']['native_ref']
    assert grant['native_session_id']==world['actor']['native_payload']['session_id']
    assert 'token' not in grant and TOKEN not in str(state)
    assert grant['ownership_transfer'] is False


@pytest.mark.parametrize('change',['token','plan','registry','released','terminal','effect','wait','cancelled','expiry'])
def test_service_rejects_stale_or_self_authorized_launch_without_native_call(engine,facade,world,monkeypatch,change):
    import prepared_native_launch as owner
    import native_resume
    from test_run_admission import write_board
    state=prepared(facade,world)
    token=TOKEN
    if change=='token':token='wrong-token'
    elif change=='plan':world['plan'].write_text(world['plan'].read_text()+'Changed instructions.\n')
    elif change=='registry':(world['repo']/'projects/index.yaml').write_text('- id: foreign\n')
    elif change=='released':write_board(world,status='released')
    elif change=='terminal':invoke(facade,world,request('cancel',{'target':'run','reason':'cancel'},state,'cancel'))
    elif change=='cancelled':invoke(facade,world,request('record',{'kind':'launch_cancel','permit_id':'permit1','reason':'cancel'},state,'cancel'))
    elif change=='effect':
        from test_run_state import command
        command(engine,world,state,'effect.prepare',{'id':'unsafe','target':'fixture:target','payload_digest':'a'*64,'idempotency_key':'same','authority_ref':''})
    elif change=='wait':
        from test_run_state import command
        command(engine,world,state,'wait.add',{'id':'human','kind':'user','reason':'human decision'})
    else:monkeypatch.setattr(owner,'_clock',lambda:datetime.now(timezone.utc)+timedelta(days=1))
    called=[]
    monkeypatch.setattr(native_resume,'launch',lambda *a,**kw:called.append(True))
    monkeypatch.setattr(native_resume,'transport_for',lambda client:'synthetic-fixture-transport')
    attribute_recovery_fixture(world) if change!='released' else None
    with pytest.raises((ValueError,OSError)):
        owner.execute(world['project'],state['run_id'],'permit1',token,runtime_root=world['runtime'])
    assert not called


def test_unqualified_host_is_refused_without_spending_permit(facade,world):
    import prepared_native_launch as owner
    state=prepared(facade,world);attribute_recovery_fixture(world)
    with pytest.raises(ValueError,match='atomic'):
        owner.execute(world['project'],state['run_id'],'permit1',TOKEN,runtime_root=world['runtime'])
    assert state_of(world,{'run_id':state['run_id']})==state


def synthetic_transport(monkeypatch,world):
    """Synthetic native output, real PM/CAS and deterministic transport seam."""
    import native_resume
    monkeypatch.setattr(native_resume,'transport_for',lambda client:'synthetic-fixture-transport')
    calls=[]
    def launch(grant,prompt,*,send_admitted,cancelled):
        calls.append(grant['permit_id'])
        assert 'controller recover' in prompt and not cancelled()
        ack=send_admitted(lambda:{'commandId':grant['turn_command_id'],'status':'accepted',
            'disposition':'started','startedNewTurn':True,'turnId':'synthetic-turn'})
        return native_resume._observation({'status':'native_terminal','task_accepted':False,'admission':ack,
            'terminal':{'terminal':'completed','fixture':'synthetic'},'native_session_id':grant['native_session_id']})
    monkeypatch.setattr(native_resume,'launch',launch)
    return calls


def test_real_owner_journal_consumes_once_and_labels_service_actor(facade,world,monkeypatch):
    import prepared_native_launch as owner
    import run_state
    state=prepared(facade,world);attribute_recovery_fixture(world)
    calls=synthetic_transport(monkeypatch,world)
    result=owner.execute(world['project'],state['run_id'],'permit1',TOKEN,runtime_root=world['runtime'])
    assert result['status']=='native_terminal' and result['task_accepted'] is False
    events=list(run_state._events(world['project'],state['run_id']))
    service=[row for row in events if row['command'] in {'native.launch.reserve','native.launch.submit','native.launch.observe'}]
    assert len(service)==3
    assert all(row['actor']['kind']=='prepared-native-launch' and row['actor']['native_actor_authenticated'] is False for row in service)
    assert service[-1]['state']['owner']==state['owner']
    assert service[-1]['state']['status']!= 'completed'
    with pytest.raises(ValueError,match='replay'):
        owner.execute(world['project'],state['run_id'],'permit1',TOKEN,runtime_root=world['runtime'])
    assert calls==['permit1']


def test_interrupted_after_reservation_never_blindly_replays(facade,world,monkeypatch):
    import prepared_native_launch as owner
    import native_resume
    import run_state
    state=prepared(facade,world);attribute_recovery_fixture(world)
    monkeypatch.setattr(native_resume,'transport_for',lambda client:'synthetic-fixture-transport')
    original=run_state._project
    def fail(project,value):
        if value.get('extensions',{}).get('prepared_native_launch',{}).get('permits',{}).get('permit1',{}).get('status')=='consumed':raise OSError('synthetic crash after durable reservation')
        return original(project,value)
    monkeypatch.setattr(run_state,'_project',fail)
    with pytest.raises(OSError):owner.execute(world['project'],state['run_id'],'permit1',TOKEN,runtime_root=world['runtime'])
    monkeypatch.setattr(run_state,'_project',original)
    with pytest.raises(ValueError,match='replay'):owner.execute(world['project'],state['run_id'],'permit1',TOKEN,runtime_root=world['runtime'])


def test_concurrent_consumers_can_submit_only_one_native_turn(facade,world,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import prepared_native_launch as owner
    state=prepared(facade,world);attribute_recovery_fixture(world)
    calls=synthetic_transport(monkeypatch,world)
    def consume():
        try:return owner.execute(world['project'],state['run_id'],'permit1',TOKEN,runtime_root=world['runtime'])['status']
        except ValueError:return 'refused'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:consume(),range(2)))
    assert sorted(results)==['native_terminal','refused']
    assert calls==['permit1']


def test_plain_json_cannot_mint_native_transport_observation(facade,world,monkeypatch):
    import prepared_native_launch as owner
    import run_state,native_resume
    state=prepared(facade,world);attribute_recovery_fixture(world)
    monkeypatch.setattr(native_resume,'transport_for',lambda client:'synthetic-fixture-transport')
    owner._step(world['project'],state['run_id'],'permit1',TOKEN,'reserve',runtime_root=world['runtime'])
    with pytest.raises(ValueError,match='observation'):
        owner._step(world['project'],state['run_id'],'permit1',TOKEN,'observe',runtime_root=world['runtime'],
            outcome={'status':'native_terminal','task_accepted':False,'native_session_id':world['actor']['native_payload']['session_id']})


def test_cancellation_between_reserve_and_submit_prevents_send(facade,world,monkeypatch):
    import prepared_native_launch as owner
    import native_resume
    state=prepared(facade,world);attribute_recovery_fixture(world)
    monkeypatch.setattr(native_resume,'transport_for',lambda client:'synthetic-fixture-transport')
    current=owner._step(world['project'],state['run_id'],'permit1',TOKEN,'reserve',runtime_root=world['runtime'])
    result=invoke(facade,world,request('record',{'kind':'launch_cancel','permit_id':'permit1','reason':'cancel before native action'},current,'cancel-late'))
    assert result['status']=='RECORDED'
    called=[]
    with pytest.raises(ValueError,match='replay'):
        owner._step(world['project'],state['run_id'],'permit1',TOKEN,'submit',runtime_root=world['runtime'],send=lambda:called.append(True))
    assert not called


def test_revoked_owner_cannot_append_late_transport_observation(facade,world,monkeypatch):
 import prepared_native_launch as owner
 import native_resume as native
 import run_state
 from test_run_admission import write_board
 state=prepared(facade,world);attribute_recovery_fixture(world)
 state=owner._step(world['project'],state['run_id'],'permit1',TOKEN,'reserve',runtime_root=world['runtime'])
 original=owner.attribution_snapshot
 def snapshot(project,grant):
  value=original(project,grant);write_board(world,status='released');return value
 monkeypatch.setattr(owner,'attribution_snapshot',snapshot)
 with pytest.raises(ValueError):
  owner._step(world['project'],state['run_id'],'permit1',TOKEN,'observe',runtime_root=world['runtime'],
   outcome=native._observation({'status':'unknown','task_accepted':False,'native_session_id':world['actor']['native_payload']['session_id']}))
 assert run_state.load_run(world['project'],state['run_id'])==state, 'late transport observation committed after native issuer lost ownership'


# Permanent regressions retained from the same-round independent review.
import json
from test_run_state import command


def exact_prepared(engine, facade, world):
    seed = start_request(world)
    seed['input']['outcome_contract']['authority_refs'] = ['explicit-service-enrollment']
    state = state_of(world, invoke(facade, world, seed))
    state = state_of(world, invoke(facade, world, request('record', {'kind': 'supervision', 'action': 'enroll',
        'authority_ref': 'explicit-service-enrollment', 'max_requests': 4, 'max_attempts': 2,
        'lease_seconds': 30, 'backoff_seconds': 10}, state, 'enroll')))
    path = world['project']/'original-controlling-input.txt'
    path.write_text('Original exact task input.\n')
    state = command(engine, world, state, 'artifact.register', {
        'id': 'original-input', 'path': str(path), 'role': 'input', 'retention': 'durable', 'required': True})
    state = state_of(world, invoke(facade, world, request('record', {
        'kind': 'launch_prepare', 'permit_id': 'permit1', 'authority_ref': 'explicit-service-enrollment',
        'token_sha256': hashlib.sha256(TOKEN.encode()).hexdigest(),
        'expires_at': (datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat(),
        'max_wall_seconds': 60, 'max_output_bytes': 65536}, state, 'prepare-launch')))
    assert state['extensions']['prepared_native_launch']['permits']['permit1']['artifacts']
    return state


@pytest.mark.parametrize('change', ['new-registered-input', 'changed-existing-input', 'ordinary-progress'])
def test_exact_input_set_bound_by_grant_is_not_silently_extended(engine, facade, world, change):
    import prepared_native_launch as owner
    import run_state
    state = exact_prepared(engine, facade, world)
    original_inputs = dict(state['artifacts'])
    if change == 'new-registered-input':
        path = world['project']/'new-controlling-input.txt'
        path.write_text('New task input arrived after exact native launch preparation.\n')
        state = command(engine, world, state, 'artifact.register', {
            'id': 'new-input', 'path': str(path), 'role': 'input', 'retention': 'durable', 'required': True})
    elif change == 'changed-existing-input':
        row = state['artifacts']['original-input']
        path = world['project']/row['path']
        path.write_bytes(path.read_bytes()+b'\nchanged-bound-input\n')
    else:
        state = command(engine, world, state, 'progress', {'summary': 'Current owner retained a factual progress note.'})
    attribute_recovery_fixture(world)
    before = run_state.load_run(world['project'], state['run_id'])
    refusal = None
    try:
        owner._step(world['project'], state['run_id'], 'permit1', TOKEN, 'reserve', runtime_root=world['runtime'])
    except (ValueError, OSError) as error:
        refusal = str(error)
    after = run_state.load_run(world['project'], state['run_id'])
    print(json.dumps({'change': change, 'before_revision': before['revision'], 'after_revision': after['revision'],
                      'old_inputs': sorted(original_inputs), 'current_inputs': sorted(after['artifacts']), 'refusal': refusal}))
    if change == 'ordinary-progress':
        assert refusal is None
        assert after['revision'] == before['revision']+1
    else:
        assert refusal is not None, 'prepared exact-input grant silently admitted a changed registered input set'
        assert after == before

