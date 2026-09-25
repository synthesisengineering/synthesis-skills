"""One-shot launch authority prepared by a real native owner in its run journal.

The bearer grants only one exact native resume. A service never becomes the
native issuer: its journal actor is explicitly a prepared-grant consumer. The
issuer selector is used for fresh read-only claim inspection, not impersonation.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import hmac
import json
from pathlib import Path
import sys

import run_state
import supervision
import native_resume
from run_admission import read_admission_observation

MAX_PERMITS=64


def _clock():return datetime.now(timezone.utc)


def validate(payload):
    expected={'permit_id','authority_ref','token_sha256','expires_at','max_wall_seconds','max_output_bytes','native_posture'}
    if not isinstance(payload,dict) or set(payload)!=expected:raise ValueError('launch preparation fields are closed')
    native_resume.posture_arguments(payload['native_posture'])
    run_state._id(payload['permit_id'],'launch permit')
    if not isinstance(payload['authority_ref'],str) or not payload['authority_ref']:raise ValueError('launch authority reference is required')
    value=payload['token_sha256']
    if not isinstance(value,str) or len(value)!=64 or any(x not in '0123456789abcdef' for x in value):raise ValueError('launch requires a SHA256 bearer-token digest')
    if type(payload['max_wall_seconds']) is not int or not 1<=payload['max_wall_seconds']<=900:raise ValueError('launch wall bound must be 1 through 900 seconds')
    if type(payload['max_output_bytes']) is not int or not 65536<=payload['max_output_bytes']<=4*1024*1024:raise ValueError('launch output bound invalid')
    run_state._time(payload['expires_at'])


def prepare(context,payload):
    validate(payload);proof=read_admission_observation(context);state=context['state']
    now=run_state._time(context['now']);expiry=run_state._time(payload['expires_at'])
    if not now<expiry<=now+__import__('datetime').timedelta(hours=1):raise ValueError('launch expiry must be within one hour')
    if state['status'] in run_state.TERMINAL:raise ValueError('terminal run cannot prepare a native launch')
    import workflow
    flow=state.get('extensions',{}).get('workflow',{})
    workflow._admission_open(flow,context)
    if flow.get('budget') and expiry>run_state._time(flow['budget']['deadline']):raise ValueError('launch grant cannot outlive the run resource deadline')
    ext=state.get('extensions',{}).get('supervision',{})
    if ext.get('lifecycle')!='enrolled' or ext.get('binding')!=supervision._binding(context):raise ValueError('current owner must explicitly enroll optional supervision first')
    if payload['authority_ref'] not in state['contract']['authority_refs']:raise ValueError('launch authority is absent from current contract')
    import recovery_capsule
    if recovery_capsule._report(context)['status']!='clear' or any(x['status']=='pending' for x in state['waits'].values()):raise ValueError('native launch requires reconciled effects, inputs, children, instructions and waits')
    rows=deepcopy(state.get('extensions',{}).get('prepared_native_launch',{}).get('permits',{}))
    if payload['permit_id'] in rows:raise ValueError('launch permit identity/tombstone is immutable')
    if len(rows)>=MAX_PERMITS:raise ValueError('retained launch permit capacity reached')
    if any(x['status'] in {'prepared','consumed','submitted','unknown'} for x in rows.values()):raise ValueError('reconcile or cancel the existing exact-session launch before preparing another')
    native_ref=proof['native_ref'];prefix,session=native_ref.split(':',1)
    client={'cc':'claude','codex':'codex','muse':'muse'}.get(prefix)
    if client is None:raise ValueError('unsupported native owner identity')
    binary=native_resume.installed_binary(client) if client=='muse' else None
    selector={'board':str(context['actor']['board']),'native_payload':{key:deepcopy(value) for key,value in context['actor']['native_payload'].items() if key in {'session_id','transcript_path','cwd'}}}
    rows[payload['permit_id']]={**deepcopy(payload),'status':'prepared','prepared_at':context['now'],
        'prepared_revision':state['revision']+1,'issuer':supervision._binding(context),'issuer_selector':selector,
        'client':client,'native_session_id':session,'workspace':proof['repository'],'binary':binary,
        'runtime_root':str(context['runtime_root']),
        'resume_command_id':native_resume.command_id(),'turn_command_id':native_resume.command_id(),
        'artifacts':{key:item['digest'] for key,item in context['artifacts'].items()},
        'ownership_transfer':False,'effect_replay_allowed':False,'task_accepted':False,
        'native_qualification':'Not inferred from owner preparation'}
    return {'permits':rows}


def reduce(state,payload,context):
    result=deepcopy(state);result.setdefault('extensions',{})['prepared_native_launch']={'schema_version':1,'permits':deepcopy(payload['permits'])}
    return result


def prepare_cancel(context,payload):
    read_admission_observation(context)
    if not isinstance(payload,dict) or set(payload)!={'permit_id','reason'} or not isinstance(payload['reason'],str) or not 0<len(payload['reason'])<=4096:raise ValueError('launch cancellation needs exact identity and bounded reason')
    rows=deepcopy(context['state'].get('extensions',{}).get('prepared_native_launch',{}).get('permits',{}))
    if payload['permit_id'] not in rows:raise ValueError('unknown launch permit')
    rows[payload['permit_id']].update(status='cancelled',cancel_reason=payload['reason'],cancelled_at=context['now'])
    return {'permits':rows}


def register(engine):
    engine.register_command('native.launch.prepare',reduce)
    engine.register_preparer('native.launch.prepare',prepare)
    engine.register_command('native.launch.cancel',reduce,terminal_safe=True)
    engine.register_preparer('native.launch.cancel',prepare_cancel)


def _grant(state,permit,token):
    row=state.get('extensions',{}).get('prepared_native_launch',{}).get('permits',{}).get(permit)
    if not isinstance(row,dict) or not isinstance(token,str) or not 32<=len(token)<=256 or not hmac.compare_digest(row['token_sha256'],hashlib.sha256(token.encode()).hexdigest()):raise ValueError('prepared launch bearer is absent or invalid')
    return row


def current_fence(project,state,grant,*,runtime_root=None):
    """Fresh passive issuer inspection: deliberately not native mutation admission."""
    native_resume.posture_arguments(grant.get('native_posture'))
    import recovery_capsule
    selector=grant['issuer_selector']
    import autopilot
    if str(Path(runtime_root or autopilot.default_runtime_root()).absolute())!=grant['runtime_root']:raise ValueError('prepared launch runtime/attribution root changed')
    recovery_capsule.resolve(project,state['project_id'],selector,runtime_root)
    proof=run_state._binding(project,state,selector,readonly=True,passive=True)
    context=run_state._context(project,state,{},proof,actor=selector,purpose='passive-stop')
    head=run_state._last_event(project,state['run_id'])
    context.update(state=state,project=Path(project),actor=selector,journal_head={'revision':state['revision'],'digest':head['digest'],'scope':'full_run'})
    context['current_native_invalidation']=run_state._native_readback(project,state,selector,context['journal_head'],passive=True,invalidation=True)
    if supervision._binding(context)!=grant['issuer']:raise ValueError('prepared native issuer/project/claim/contract/profile/plan fence changed')
    if state['status'] in run_state.TERMINAL:raise ValueError('terminal run cannot launch native work')
    ext=state.get('extensions',{}).get('supervision',{})
    if ext.get('lifecycle')!='enrolled' or ext.get('binding')!=grant['issuer']:raise ValueError('supervision enrollment changed or was stopped')
    if _clock()>=run_state._time(grant['expires_at']):raise ValueError('prepared native launch expired')
    import workflow
    workflow._admission_open(state.get('extensions',{}).get('workflow',{}),context)
    if {key:item['digest'] for key,item in context['artifacts'].items()}!=grant['artifacts']:raise ValueError('launch input/artifact identity set changed')
    if recovery_capsule._report(context)['status']!='clear' or any(row['status']=='pending' for row in state['waits'].values()):raise ValueError('launch requires current reconciliation of native/effects/inputs/children/waits')
    return proof


def attribution_snapshot(project,grant):
    """Called only after the full resolver accepted current attribution."""
    import project_state
    repository=Path(grant['issuer']['repository'])
    relative=Path(project).relative_to(repository).as_posix()
    return {row['path']:row['sha256'] for row in project_state._dirty_project_files(repository,relative)}


def attribute_owned_append(project,state,grant,token,*,runtime_root=None):
    """Delegate to the existing repo-attribution owner, never write manifests here."""
    import autopilot
    import importlib.util
    path=Path(__file__).resolve().parents[2]/'synthesis-repo-guard/checkpoint_sync.py'
    if path.is_symlink() or not path.is_file():raise ValueError('attribution owner is missing or unsafe')
    spec=importlib.util.spec_from_file_location('_prepared_launch_attribution_owner',path)
    owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)
    runtime=Path(runtime_root or autopilot.default_runtime_root()).absolute()
    return owner.record_prepared_native_launch(project=Path(project),run_id=state['run_id'],
        permit_id=grant['permit_id'],token=token,revision=state['revision'],guard_root=runtime.parent/'repo-guard')


def _step(project,run_id,permit,token,phase,*,runtime_root=None,send=None,outcome=None):
    return run_state.prepared_native_launch_step(project,run_id,permit,token,phase,
        runtime_root=runtime_root,send=send,outcome=outcome)


def execute(project,run_id,permit,token,*,runtime_root=None):
    """Finite Console/CLI consumer. No actor argument and no caller-supplied prompt."""
    project=Path(project).absolute();state=run_state.load_run(project,run_id)
    grant=_grant(state,permit,token)
    native_resume.transport_for(grant['client'])
    native_resume.posture_arguments(grant.get('native_posture'))
    _step(project,run_id,permit,token,'reserve',runtime_root=runtime_root)
    state=run_state.load_run(project,run_id);grant=deepcopy(_grant(state,permit,token))
    grant['max_wall_seconds']=min(grant['max_wall_seconds'],max(.01,(run_state._time(grant['expires_at'])-_clock()).total_seconds()))
    prompt=('Resume the existing authorized synthesis autopilot run. Project: '+json.dumps(str(project))+
        '; project id: '+json.dumps(state['project_id'])+'; run id: '+json.dumps(run_id)+
        '. Run the installed synthesis-project-resume protocol, resolve the current project, authenticate your real native identity, '
        'and use controller recover before next. This one-shot continuation grants no new action authority, '
        'no claim takeover, no effect replay, no trust/settings changes, and no permission to ignore a cancellation or changed instructions. '
        'Respect the existing contract, resource bounds and pending decisions. If current admission fails, stop with the exact reason.')
    def cancelled():
        try:
            fresh=run_state.load_run(project,run_id);row=_grant(fresh,permit,token)
            return fresh['status'] in run_state.TERMINAL or row['status']=='cancelled' or fresh.get('extensions',{}).get('supervision',{}).get('lifecycle')!='enrolled'
        except (ValueError,OSError):return True
    def submit(send):return _step(project,run_id,permit,token,'submit',runtime_root=runtime_root,send=send)
    outcome=native_resume.launch(grant,prompt,send_admitted=submit,cancelled=cancelled)
    _step(project,run_id,permit,token,'observe',runtime_root=runtime_root,outcome=outcome)
    return outcome


def status_view(state):
    rows=state.get('extensions',{}).get('prepared_native_launch',{}).get('permits',{})
    return {'schema_version':1,'permits':{key:{field:deepcopy(row.get(field)) for field in
        ('status','client','native_session_id','prepared_revision','expires_at','max_wall_seconds','native_posture','outcome','cancel_reason')} for key,row in rows.items()},
        'scope':'One-shot native transport grant; no task acceptance or ownership transfer',
        'hosts':{'muse':'writer-lease transport','codex':'atomic admission unavailable','claude':'atomic admission unavailable'},
        'survival':{'process_loss':'UNKNOWN','app_exit':'UNKNOWN','logout':'UNKNOWN','reboot':'UNKNOWN','machine_transfer':'UNKNOWN'}}


def main():
    raw=sys.stdin.buffer.read(65537)
    if len(raw)>65536:raise ValueError('prepared launch request too large')
    import autopilot
    request=autopilot._decode_json(raw)
    if not isinstance(request,dict) or set(request)!={'project','run_id','permit_id','token','runtime_root'}:raise ValueError('prepared launch request fields are closed')
    autopilot.engine()
    result=execute(request['project'],request['run_id'],request['permit_id'],request['token'],runtime_root=Path(request['runtime_root']) if request['runtime_root'] else None)
    print(json.dumps(result,sort_keys=True))
    return 0 if result['status']=='native_terminal' else 2


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,TypeError) as exc:
        print(json.dumps({'status':'REFUSED','diagnostic':str(exc)[:4096],'task_accepted':False}));raise SystemExit(2)
