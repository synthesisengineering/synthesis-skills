"""Optional Console-owner interface; synthetic native capability unit proofs.

Actual controller tests exercise PM/journal authentication. Pure tests below
explicitly inject a synthetic native owner status; none qualifies a host wake.
"""
from copy import deepcopy
import pytest
from test_controller import engine, facade, world, invoke, request, start_request, state_of


def model(monkeypatch):
    import supervision
    state = {'revision': 5, 'status': 'running', 'run_id': 'synthetic-run',
        'contract_digest': 'c'*64, 'profile_digest': 'p'*64,
        'contract': {'authority_refs': ['explicit-service-enrollment']}, 'extensions': {}}
    context = {'state': state, 'now': 2000000000.0, 'plan_digest': 'a'*64,
        'binding': {'session_uuid':'fixture-owner','native_ref':'codex:synthetic',
            'claim_hash':'f'*64,'repository':'/fixture/repo','branch':'main'}}
    monkeypatch.setattr(supervision, 'read_admission_observation', lambda ctx: ctx['binding'])
    monkeypatch.setattr(supervision, '_current', lambda ctx: {'clear': True,
        'job_id': 'native-job', 'lease_expires_at': ctx['now']+3600,
        'wake_receipts': [], 'reasons': []})
    def apply(action, **payload):
        data = supervision.prepare(context, {'action': action, **payload})
        updated = supervision.reduce(context['state'], data, context)
        updated['revision'] += 1
        context['state'] = updated
        return updated
    return supervision, context, apply


def enable(apply):
    return apply('enroll', authority_ref='explicit-service-enrollment',
        max_requests=4, max_attempts=2, lease_seconds=30, backoff_seconds=10)


def test_authenticated_queue_lease_fence_and_cancellation_tombstone(monkeypatch):
    owner, ctx, apply = model(monkeypatch)
    enable(apply)
    apply('request', request_id='q1', job_id='native-job')
    claimed=apply('claim', request_id='q1')
    lease=claimed['extensions']['supervision']['requests']['q1']
    assert lease['status']=='leased' and lease['fence']==1
    assert lease['dispatch']['authority_granted'] is False
    assert lease['dispatch']['state']=='request_only'
    with pytest.raises(ValueError,match='leased'):
        apply('claim',request_id='q1')
    cancelled=apply('cancel',request_id='q1',reason='Operator withdrew this request')
    assert cancelled['extensions']['supervision']['requests']['q1']['status']=='cancelled'
    with pytest.raises(ValueError):apply('request',request_id='q1',job_id='native-job')
    with pytest.raises(ValueError):apply('claim',request_id='q1')
    assert owner.status_view(cancelled)['counts']['cancelled']==1


def test_unknown_native_admission_has_finite_backoff_and_exhaustion(monkeypatch):
    owner,ctx,apply=model(monkeypatch);enable(apply)
    apply('request',request_id='q1',job_id='native-job')
    monkeypatch.setattr(owner,'_current',lambda ctx:{'clear':False,'reasons':['native capability unknown'],
        'job_id':None,'wake_receipts':[],'lease_expires_at':None})
    state=apply('claim',request_id='q1')
    assert state['extensions']['supervision']['requests']['q1']['status']=='backoff'
    with pytest.raises(ValueError,match='backoff'):apply('claim',request_id='q1')
    ctx['now']+=11
    state=apply('claim',request_id='q1')
    assert state['extensions']['supervision']['requests']['q1']['status']=='exhausted'
    with pytest.raises(ValueError):apply('claim',request_id='q1')


def test_expired_lease_needs_readback_and_cannot_replay(monkeypatch):
    owner,ctx,apply=model(monkeypatch);enable(apply)
    apply('request',request_id='q1',job_id='native-job');apply('claim',request_id='q1')
    ctx['now']+=31
    state=apply('reconcile',request_id='q1')
    assert state['extensions']['supervision']['requests']['q1']['status']=='reconcile'
    with pytest.raises(ValueError):apply('claim',request_id='q1')
    monkeypatch.setattr(owner,'_current',lambda ctx:{'clear':True,'reasons':[],'job_id':'native-job',
        'wake_receipts':[{'receipt':'actual-owner-verified-readback','observed_at':ctx['now']}],
        'lease_expires_at':ctx['now']+3600})
    state=apply('reconcile',request_id='q1')
    assert state['extensions']['supervision']['requests']['q1']['status']=='completed'


@pytest.mark.parametrize('change',['owner','contract','profile','instructions'])
def test_enrollment_never_transfers_authority_on_change(monkeypatch,change):
    owner,ctx,apply=model(monkeypatch);enable(apply)
    apply('request',request_id='q1',job_id='native-job')
    if change=='owner':ctx['binding']['claim_hash']='new-owner'
    elif change=='instructions':ctx['plan_digest']='new-instructions'
    else:ctx['state'][change+'_digest']='new-policy'
    with pytest.raises(ValueError,match='binding'):apply('claim',request_id='q1')
    # Cancellation is safe even after a legitimate owner/contract change.
    state=apply('cancel',request_id='q1',reason='Preserve old tombstone')
    assert state['extensions']['supervision']['requests']['q1']['status']=='cancelled'


def test_stop_and_uninstall_preserve_requests_and_diagnostics(monkeypatch):
    owner,ctx,apply=model(monkeypatch);enable(apply)
    apply('request',request_id='q1',job_id='native-job')
    state=apply('stop',reason='Stop optional supervision')
    assert state['extensions']['supervision']['lifecycle']=='stopped'
    with pytest.raises(ValueError):apply('claim',request_id='q1')
    state=apply('uninstall',reason='Remove optional enrollment')
    assert state['extensions']['supervision']['lifecycle']=='uninstalled'
    assert owner.status_view(state)['counts']['cancelled']==1
    assert owner.status_view(state)['automatic_launch']=='UNAVAILABLE'


def test_controller_refuses_fabricated_service_authority_without_journal_write(facade,world):
    state=state_of(world,invoke(facade,world,start_request(world)))
    req=request('record',{'kind':'supervision','action':'enroll',
        'authority_ref':'invented-service-permission','max_requests':4,'max_attempts':2,
        'lease_seconds':30,'backoff_seconds':10},state,'service-enroll')
    result=invoke(facade,world,req)
    assert result['status']=='UNRESOLVED',result
    assert any('authority' in row['detail'] for row in result['diagnostics']),result
    assert state_of(world,result)==state


def test_actual_controller_journals_queue_and_refuses_unknown_native_launch(facade,world):
    seed=start_request(world)
    seed['input']['outcome_contract']['authority_refs']=['explicit-service-enrollment']
    state=state_of(world,invoke(facade,world,seed))
    for number,data in enumerate([
        {'action':'enroll','authority_ref':'explicit-service-enrollment','max_requests':4,'max_attempts':2,'lease_seconds':30,'backoff_seconds':10},
        {'action':'request','request_id':'q1','job_id':'unobserved-native-job'},
        {'action':'claim','request_id':'q1'},
    ]):
        result=invoke(facade,world,request('record',{'kind':'supervision',**data},state,'service-'+str(number)))
        assert result['status']=='RECORDED',result
        state=state_of(world,result)
    view=result['coverage']['supervision']
    assert view['requests']['q1']['status']=='backoff'
    assert view['automatic_launch']=='UNAVAILABLE'
    assert view['authority_granted'] is False
    assert any('native' in reason for reason in view['requests']['q1']['diagnostics'])
    result=invoke(facade,world,request('record',{'kind':'supervision','action':'cancel','request_id':'q1','reason':'No provider operation occurred'},state,'service-cancel'))
    assert result['coverage']['supervision']['counts']['cancelled']==1


@pytest.mark.parametrize('field,value',[('max_requests',65),('max_attempts',0),('max_attempts',True),('lease_seconds',301),('backoff_seconds',3601)])
def test_enrollment_bounds_are_enforced(monkeypatch,field,value):
    owner,ctx,apply=model(monkeypatch)
    values={'authority_ref':'explicit-service-enrollment','max_requests':4,'max_attempts':2,'lease_seconds':30,'backoff_seconds':10}
    values[field]=value
    with pytest.raises(ValueError):apply('enroll',**values)


def test_actual_terminal_run_can_stop_optional_enrollment(facade,world):
    seed=start_request(world);seed['input']['outcome_contract']['authority_refs']=['explicit-service-enrollment']
    state=state_of(world,invoke(facade,world,seed))
    for n,values in enumerate([
        {'action':'enroll','authority_ref':'explicit-service-enrollment','max_requests':4,'max_attempts':2,'lease_seconds':30,'backoff_seconds':10},
        {'action':'request','request_id':'q1','job_id':'native-job'},
    ]):
        response=invoke(facade,world,request('record',{'kind':'supervision',**values},state,'setup-'+str(n)))
        assert response['status']=='RECORDED',response
        state=state_of(world,response)
    response=invoke(facade,world,request('cancel',{'target':'run','reason':'End run'},state,'close-run'))
    assert response['status']=='CANCELLED'
    state=state_of(world,response)
    response=invoke(facade,world,request('record',{'kind':'supervision','action':'stop','reason':'Stop retained optional intents'},state,'stop-after-close'))
    assert response['status']=='CANCELLED',response
    assert response['coverage']['supervision']['counts']['cancelled']==1
    state=state_of(world,response)
    denied=invoke(facade,world,request('record',{'kind':'supervision','action':'request','request_id':'q2','job_id':'new-job'},state,'terminal-request'))
    assert denied['status']=='UNRESOLVED',denied
    assert state_of(world,denied)==state


def test_one_native_job_cannot_have_two_active_request_intents(monkeypatch):
    owner,ctx,apply=model(monkeypatch);enable(apply)
    apply('request',request_id='q1',job_id='native-job')
    with pytest.raises(ValueError,match='job'):
        apply('request',request_id='q2',job_id='native-job')
