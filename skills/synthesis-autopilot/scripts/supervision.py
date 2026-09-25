"""Optional supervision intents owned by the existing PM-admitted run journal.

The existing Console process may read this finite projection. It cannot mint a
native actor, acquire a claim, launch a provider or infer a dead-owner transfer.
Only an authenticated native submitter may mutate these intents through the
ordinary controller. Queue leases are admission fences, never proof of a wake.
"""
from copy import deepcopy

import capabilities
import run_state
from run_admission import read_admission_observation

SCHEMA_VERSION = 1
MAX_REQUESTS = 64
KEYS = ('session_uuid', 'native_ref', 'claim_hash', 'repository', 'branch')


def _binding(context):
    return {**{key: context['binding'][key] for key in KEYS},
        **{key: context['state'][key] for key in ('run_id','contract_digest','profile_digest')},
        'plan_digest': context['plan_digest']}


def _current(context):
    """Current owner evidence, not a service-supplied boolean or success flag."""
    import recovery_capsule
    state = context['state']
    report = recovery_capsule._report(context)
    status = capabilities.continuation_status(state, context)
    job = state.get('extensions', {}).get('capabilities', {}).get('continuation', {})
    reasons = [row['kind'] for row in report['pending']]
    if status.get('continuation_verified') is not True:
        reasons.append('native continuation is ' + status['state'])
    if any(row['status']=='pending' for row in state['waits'].values()):
        reasons.append('unresolved run wait')
    return {'clear': not reasons, 'reasons': reasons, 'native': status,
        'job_id': job.get('job_id'), 'lease_expires_at': job.get('lease_expires_at'),
        'wake_receipts': deepcopy(job.get('wakes', []))}


def validate(payload):
    if not isinstance(payload,dict) or not isinstance(payload.get('action'),str):
        raise ValueError('supervision needs a typed action')
    fields = {
        'enroll': {'authority_ref','max_requests','max_attempts','lease_seconds','backoff_seconds'},
        'request': {'request_id','job_id'}, 'claim': {'request_id'},
        'reconcile': {'request_id'}, 'cancel': {'request_id','reason'},
        'stop': {'reason'}, 'uninstall': {'reason'},
    }
    action=payload['action']
    if action not in fields or set(payload)!={'action',*fields[action]}:
        raise ValueError('unsupported supervision action or fields')
    for key in fields[action]-{'max_requests','max_attempts','lease_seconds','backoff_seconds'}:
        if not isinstance(payload[key],str) or not payload[key].strip() or len(payload[key])>4096:
            raise ValueError('supervision text must be nonempty and bounded')
    if 'request_id' in payload:run_state._id(payload['request_id'],'supervision request')
    if action=='enroll':
        for key,limit in (('max_requests',MAX_REQUESTS),('max_attempts',5),('lease_seconds',300),('backoff_seconds',3600)):
            if type(payload[key]) is not int or not 1<=payload[key]<=limit:
                raise ValueError('supervision bound is invalid: '+key)


def prepare(context,payload):
    validate(payload)
    read_admission_observation(context)
    state=context['state']; now=capabilities._time(context['now'])
    action=payload['action']
    old=state.get('extensions',{}).get('supervision')
    if state['status'] in run_state.TERMINAL and action not in {'cancel','stop','uninstall','reconcile'}:
        raise ValueError('closed run cannot enroll or request supervision')
    if action=='enroll':
        if payload['authority_ref'] not in state['contract']['authority_refs']:
            raise ValueError('explicit service enrollment authority is absent from the current contract')
        if old and any(row['status'] in {'leased','reconcile'} for row in old['requests'].values()):
            raise ValueError('reconcile or cancel outstanding leases before changing enrollment')
        if old and len(old['requests'])>payload['max_requests']:
            raise ValueError('new enrollment cannot discard retained request tombstones')
        updated={**deepcopy(old or {}),'schema_version':SCHEMA_VERSION,'lifecycle':'enrolled',
            'binding':_binding(context),'config':{key:value for key,value in payload.items() if key!='action'},
            'enrolled_at':now,'requests':deepcopy((old or {}).get('requests',{})),
            'epoch':(old or {}).get('epoch',0),'last_event':{'action':action,'at':now}}
        return {'extension':updated}
    if not old:raise ValueError('optional supervision is not enrolled')
    updated=deepcopy(old)
    if action in {'stop','uninstall'}:
        updated['lifecycle']='stopped' if action=='stop' else 'uninstalled'
        for row in updated['requests'].values():
            if row['status'] not in {'completed','cancelled'}:
                row.update(status='cancelled',cancelled_at=now,cancel_reason=payload['reason'])
        updated['last_event']={'action':action,'reason':payload['reason'],'at':now}
        return {'extension':updated}
    identity=payload['request_id']; rows=updated['requests']
    if action=='cancel':
        if identity not in rows:raise ValueError('unknown supervision request')
        if rows[identity]['status']!='completed':
            rows[identity].update(status='cancelled',cancelled_at=now,cancel_reason=payload['reason'])
        return {'extension':updated}
    if updated['lifecycle']!='enrolled':raise ValueError('optional supervision is stopped or uninstalled')
    if updated['binding']!=_binding(context):
        raise ValueError('supervision enrollment binding changed; only the current owner may explicitly re-enroll')
    if action=='request':
        if identity in rows:raise ValueError('supervision request identity/tombstone is immutable')
        if any(row['job_id']==payload['job_id'] and row['status'] not in {'completed','cancelled'} for row in rows.values()):
            raise ValueError('native job already has an unresolved supervision request; reconcile its existing identity')
        if len(rows)>=updated['config']['max_requests']:raise ValueError('supervision queue capacity reached; retain existing diagnostics')
        rows[identity]={'request_id':identity,'job_id':payload['job_id'],'status':'queued',
            'created_at':now,'attempts':0,'fence':None,'next_attempt_at':now,'diagnostics':[]}
        return {'extension':updated}
    if identity not in rows:raise ValueError('unknown supervision request')
    row=rows[identity]
    if action=='claim':
        if row['status'] not in {'queued','backoff'}:raise ValueError('supervision request is '+row['status']+'; it cannot be replayed')
        if now<row['next_attempt_at']:raise ValueError('supervision backoff has not elapsed')
        current=_current(context)
        reasons=deepcopy(current['reasons'])
        if current['job_id']!=row['job_id']:reasons.append('expected native job changed or is absent')
        row['attempts']+=1
        if not current['clear'] or reasons:
            row['status']='exhausted' if row['attempts']>=updated['config']['max_attempts'] else 'backoff'
            row['next_attempt_at']=now+updated['config']['backoff_seconds']*2**(row['attempts']-1)
            row['diagnostics']=reasons
        else:
            updated['epoch']+=1
            row.update(status='leased',fence=updated['epoch'],claimed_at=now,
                lease_expires_at=min(now+updated['config']['lease_seconds'],current['lease_expires_at']),
                wake_basis=[item['receipt'] for item in current['wake_receipts']],diagnostics=[])
            row['dispatch']={'state':'request_only','authority_granted':False,
                'automatic_launch':'UNAVAILABLE','job_id':row['job_id'],'request_id':identity,
                'fence':row['fence'],'journal_revision':state['revision']+1,
                'binding':_binding(context),'valid_until':row['lease_expires_at'],
                'effect_replay_allowed':False,'ownership_transfer':False}
    else:
        if row['status'] not in {'leased','reconcile'}:raise ValueError('only an admitted lease may reconcile native readback')
        current=_current(context)
        fresh=[item for item in current['wake_receipts'] if item['receipt'] not in row['wake_basis']
            and capabilities._time(item['observed_at'])>=row['claimed_at']]
        if current['clear'] and current['job_id']==row['job_id'] and fresh:
            row.update(status='completed',completed_at=now,completion_receipts=[item['receipt'] for item in fresh])
        else:
            row.update(status='reconcile',diagnostics=['No current independently verified subsequent native wake; never replay an uncertain delivery',*current['reasons']])
    updated['last_event']={'action':action,'request_id':identity,'at':now}
    return {'extension':updated}


def reduce(state,payload,context):
    result=deepcopy(state)
    result.setdefault('extensions',{})['supervision']=deepcopy(payload['extension'])
    return result


def status_view(state):
    """Finite read-only projection; external state is rechecked at admission."""
    ext=state.get('extensions',{}).get('supervision')
    rows=deepcopy((ext or {}).get('requests',{}))
    counts={kind:sum(item['status']==kind for item in rows.values())
        for kind in ('queued','leased','backoff','reconcile','exhausted','completed','cancelled')}
    return {'schema_version':SCHEMA_VERSION,'lifecycle':(ext or {}).get('lifecycle','not_enrolled'),
        'journal_revision':state['revision'],'requests':rows,'counts':counts,
        'automatic_launch':'UNAVAILABLE','authority_granted':False,
        'scope':'Recorded queue and lease state only; fresh authenticated native submission required for mutation',
        'survival':{'app_exit':'UNKNOWN','logout':'UNKNOWN','reboot':'UNKNOWN','machine_transfer':'UNKNOWN'},
        'upgrade':{'schema_supported':not ext or ext.get('schema_version')==SCHEMA_VERSION,
            'rule':'Stop, retain tombstones, install reviewed owner code, re-enroll through current native admission'}}


def register(engine):
    # The preparer admits only cancellation, cleanup or readback after closure;
    # no terminal enrollment, request or lease can reopen the run.
    engine.register_command('supervision.action',reduce,terminal_safe=True)
    engine.register_preparer('supervision.action',prepare)
