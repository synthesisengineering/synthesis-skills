"""Immutable input roles and real native write-boundary compiler fixtures."""
from __future__ import annotations
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture
def boundary():
    return importlib.import_module('delegation_boundary')


@pytest.fixture
def roles(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    inputs = project / 'inputs'
    inputs.mkdir()
    source = inputs / 'source.txt'
    source.write_text('preserve synthetic source\n')
    outputs = project / 'outputs'
    scratch = project / 'scratch'
    outputs.mkdir()
    scratch.mkdir()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    contract = {'schema_version': 1, 'immutable_inputs': [
        {'artifact_id': 'source', 'path': str(source), 'digest': digest}],
        'output_roots': [str(outputs)], 'scratch_root': str(scratch)}
    context = {'binding': {'project_root': str(project)},
               'artifacts': {'source': {'id': 'source', 'path': 'inputs/source.txt', 'digest': digest}}}
    return contract, context, [str(outputs), str(scratch)]


def test_contract_binds_current_artifacts_and_all_writable_roots(boundary, roles):
    contract, context, paths = roles
    assert boundary.validate_file_contract(contract, context, paths) == contract
    boundary.inspect_files(contract)


@pytest.mark.parametrize('change', ['digest', 'foreign', 'unregistered', 'input_output_overlap',
                                     'scratch_input_overlap', 'relative', 'unknown', 'boolean_version',
                                     'output_scratch_overlap', 'unclaimed_output'])
def test_contract_rejects_role_confusion_or_unbound_input(boundary, roles, change):
    contract, context, paths = roles
    contract = copy.deepcopy(contract)
    if change == 'digest': contract['immutable_inputs'][0]['digest'] = '0' * 64
    if change == 'foreign': contract['immutable_inputs'][0]['path'] = '/foreign/source.txt'
    if change == 'unregistered': context['artifacts'] = {}
    if change == 'input_output_overlap': contract['output_roots'] = [str(Path(contract['immutable_inputs'][0]['path']).parent)]
    if change == 'scratch_input_overlap': contract['scratch_root'] = str(Path(contract['immutable_inputs'][0]['path']).parent)
    if change == 'relative': contract['output_roots'] = ['outputs']
    if change == 'unknown': contract['readonly'] = True
    if change == 'boolean_version': contract['schema_version'] = True
    if change == 'output_scratch_overlap': contract['scratch_root'] = contract['output_roots'][0]
    if change == 'unclaimed_output': paths = [contract['scratch_root']]
    with pytest.raises(ValueError): boundary.validate_file_contract(contract, context, paths)


def test_readonly_worker_has_no_forced_mutable_output(boundary, roles):
    contract, context, paths = roles
    contract['output_roots'] = []
    assert boundary.validate_file_contract(contract, context, paths)['output_roots'] == []


@pytest.mark.parametrize('change', ['drift', 'input_symlink', 'output_symlink', 'parent_symlink',
                                     'output_hardlink', 'unknown_hardlink'])
def test_physical_intake_rejects_aliases_and_stale_bytes(boundary, roles, tmp_path, change):
    contract, context, paths = roles
    source = Path(contract['immutable_inputs'][0]['path'])
    out = Path(contract['output_roots'][0])
    if change == 'drift': source.write_text('changed')
    if change == 'input_symlink':
        source.rename(source.with_suffix('.retained')); source.symlink_to(source.with_suffix('.retained'))
    if change == 'output_symlink':
        out.rmdir(); out.symlink_to(tmp_path, target_is_directory=True)
    if change == 'parent_symlink':
        source.parent.rename(source.parent.with_name('retained')); source.parent.symlink_to(source.parent.with_name('retained'), target_is_directory=True)
    if change == 'output_hardlink': os.link(source, out / 'alias')
    if change == 'unknown_hardlink':
        other = tmp_path / 'other'; other.write_text('preserve foreign input'); os.link(other, out / 'alias')
    with pytest.raises(ValueError): boundary.inspect_files(contract)


def test_effect_readback_reports_input_change_without_repair(boundary, roles):
    contract, _, _ = roles
    before = boundary.inspect_files(contract)
    source = Path(contract['immutable_inputs'][0]['path'])
    source.write_text('observed unauthorized mutation')
    result = boundary.inspect_effects(contract, before)
    assert result['preservation'] == 'FAIL'
    assert result['violations']
    assert source.read_text() == 'observed unauthorized mutation'


def test_effect_readback_rejects_output_symlink_alias(boundary, roles):
    contract, _, _ = roles
    before = boundary.inspect_files(contract)
    (Path(contract['output_roots'][0]) / 'alias').symlink_to(contract['immutable_inputs'][0]['path'])
    assert boundary.inspect_effects(contract, before)['preservation'] == 'FAIL'


def test_worker_prompt_exposes_real_roles_and_resource_envelope(boundary, roles):
    contract, _, _ = roles
    text = boundary.worker_prompt('Produce a recovery note', contract,
        deadline='2026-09-24T12:00:00Z', reservation={'id':'worker','amounts':{'wall_millis':120000, 'usd_micros':2000000}})
    assert '2026-09-24T12:00:00Z' in text
    assert '120000' in text and '2000000' in text
    assert contract['immutable_inputs'][0]['path'] in text
    assert contract['immutable_inputs'][0]['digest'] in text
    assert 'execution logs' in text.lower()


def test_collaboration_does_not_claim_an_enforced_native_boundary(boundary):
    result = boundary.capability('collaboration')
    assert result['write_enforcement'] == 'UNAVAILABLE'
    assert result['reason']


def test_native_argv_bounds_cwd_temp_roots_and_retains_model(boundary, roles):
    contract, _, _ = roles
    spec=boundary.native_argv('codex','/fixture/codex',contract,{'model':'configured-model','model_reasoning_effort':'high'})
    joined=' '.join(spec)
    assert '--sandbox workspace-write' in joined
    assert 'exclude_slash_tmp=true' in joined and 'exclude_tmpdir_env_var=true' in joined
    assert 'configured-model' in joined and 'high' in joined
    assert '--dangerously' not in joined
    assert spec[spec.index('-C')+1]==contract['scratch_root']
    assert contract['immutable_inputs'][0]['path'] not in spec


def test_claude_compiler_requires_native_sandbox_and_exact_edit_rules(boundary, roles):
    contract, _, _ = roles
    args=boundary.native_argv('claude','/fixture/claude',contract,{'effort':'high'})
    settings=json.loads(args[args.index('--settings')+1])
    assert settings['sandbox']['enabled'] is True
    assert settings['sandbox']['failIfUnavailable'] is True
    assert settings['sandbox']['allowUnsandboxedCommands'] is False
    assert '--restricted' in args and '--safe-mode' in args
    assert any(rule.startswith('Edit(//') for rule in settings['permissions']['deny'])


def test_muse_compiler_never_calls_default_workspace_policy_enforced(boundary, roles):
    contract,_,_=roles
    with pytest.raises(ValueError,match='boundary'):
        boundary.native_argv('muse','/fixture/muse',contract,{'model':'configured-model','reasoning_effort':'max'})


def test_native_worker_parser_requires_real_completion_and_identity(boundary):
    raw='\n'.join(json.dumps(row) for row in [
        {'type':'system','subtype':'init','session_id':'native-1','model':'unchanged'},
        {'type':'result','subtype':'success','session_id':'native-1','total_cost_usd':0.25,'usage':{'input_tokens':10,'output_tokens':2}}])
    observed=boundary.parse_worker('claude',raw.encode())
    assert observed['producer']=='claude:native-1'
    assert observed['terminal']=='completed'
    assert observed['usage']=={'tokens':12,'usd_micros':250000}
    with pytest.raises(ValueError):boundary.parse_worker('claude',b'{"type":"result","subtype":"success"}')


def test_native_worker_unknown_cost_is_not_zero(boundary):
    raw=b'{"type":"thread.started","thread_id":"actual-thread"}\n{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":2}}\n'
    observed=boundary.parse_worker('codex',raw)
    assert observed['usage']['usd_micros'] is None
    assert observed['usage']['tokens']==12


def test_worker_observation_cannot_be_forged_from_status_words(boundary):
    assert boundary.verify_worker_observation({'preservation':'PASS','terminal':'completed'}, {}) is False


def worker_world(roles):
    from datetime import datetime, timedelta, timezone
    contract,context,paths=roles
    project=Path(context['binding']['project_root'])
    context['project']=str(project)
    context['binding'].update(session_uuid='parent-seat',native_ref='fixture:parent')
    child={'child_id':'worker','mode':'native-cli','client':'claude','disposition':'running',
        'file_contract':contract,'paths':paths,'owner':copy.deepcopy(context['binding']),
        'integration_owner':'parent-seat','deliverables':['Produce a synthetic result'],'reservation_id':'worker-budget'}
    state={'run_id':'run-a','project_id':'project-a','contract_digest':'a'*64,'profile_digest':'b'*64,
        'extensions':{'workflow':{'children':{'worker':child},'budget':{
            'deadline':(datetime.now(timezone.utc)+timedelta(minutes=2)).isoformat(),
            'reservations':{'worker-budget':{'id':'worker-budget','status':'reserved','category':'work','amounts':{'wall_millis':30000,'usd_micros':1000000}}}}}}}
    context['state']=state
    return state,context,project/'resources/autopilot-runs/run-a/native-worker-attempts'


def test_owned_worker_runs_once_and_verifier_rederives_native_artifacts(boundary,roles,tmp_path,monkeypatch):
    """A real local subprocess acts as a labeled native wire fixture; no provider."""
    state,context,runtime=worker_world(roles)
    output=Path(roles[0]['output_roots'][0])/'result.txt'
    script=tmp_path/'fixture-cli'
    script.write_text('#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\nsys.stdin.read()\n'
        +f'Path({str(output)!r}).write_text("synthetic delivered artifact")\n'
        +'print(json.dumps({"type":"system","subtype":"init","session_id":"fixture-native","model":"configured"}))\n'
        +'print(json.dumps({"type":"result","subtype":"success","session_id":"fixture-native","total_cost_usd":0.1,"usage":{"input_tokens":4,"output_tokens":2}}))\n')
    script.chmod(0o700)
    # Runner wire-fixture unit only: real PM authority is exercised separately below.
    monkeypatch.setattr(boundary,'_authorize_worker',lambda context,paths:context['binding'])
    monkeypatch.setattr(boundary,'client_selection',lambda client,env:({'effort':'high'},str(script)))
    data=boundary.run_worker(state,'worker',context,client='claude',runtime_root=runtime,timeout_seconds=10)
    assert data['producer']=='claude:fixture-native'
    assert data['terminal']=='completed' and data['preservation']=='PASS'
    assert data['output_manifest']=={str(output):hashlib.sha256(output.read_bytes()).hexdigest()}
    assert boundary.verify_worker_observation(data,context)
    with pytest.raises(ValueError,match='attempt'):
        boundary.run_worker(state,'worker',context,client='claude',runtime_root=runtime,timeout_seconds=10)
    output.write_text('changed after observation')
    assert boundary.verify_worker_observation(data,context) is False


@pytest.mark.parametrize('change',['foreign_owner','expired_deadline','unreserved','wrong_client','wrong_runtime'])
def test_worker_rejects_invalid_admission_before_native_selection(boundary,roles,tmp_path,monkeypatch,change):
    state,context,runtime=worker_world(roles)
    if change=='foreign_owner':context['binding']['session_uuid']='foreign-seat'
    if change=='expired_deadline':state['extensions']['workflow']['budget']['deadline']='2020-01-01T00:00:00Z'
    if change=='unreserved':state['extensions']['workflow']['budget']['reservations']['worker-budget']['status']='settled'
    if change=='wrong_runtime':runtime=tmp_path/'foreign-runtime'
    client='muse' if change=='wrong_client' else 'claude'
    monkeypatch.setattr(boundary,'client_selection',lambda *args:pytest.fail('Rejected work must not inspect native configuration'))
    with pytest.raises(ValueError):boundary.run_worker(state,'worker',context,client=client,runtime_root=runtime,timeout_seconds=10)


sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'synthesis-project-management/scripts'))
from test_run_admission import world  # noqa: E402,F401


def test_worker_authority_uses_active_pm_token_and_fresh_exact_paths(boundary,world):
    import run_admission
    from test_run_admission import write_board
    project=world['project'];out=project/'outputs';out.mkdir()
    proof=run_admission.admit_paths(world['board'],'alpha',project,[project],world['actor']['native_payload'])
    context={'project':project,'state':{'project_id':'alpha'},'actor':world['actor'],'binding':proof}
    with pytest.raises(ValueError):boundary._authorize_worker(context,[str(out)])
    with run_admission.admission_scope(proof,world['actor'],project) as token:
        context['admission_observation']=token
        admitted=boundary._authorize_worker(context,[str(out)])
        assert admitted['paths']==[str(out)]
        write_board(world,claims=str(world['plan']))
        with pytest.raises(ValueError):boundary._authorize_worker(context,[str(out)])


@pytest.mark.parametrize('change',['output_ancestor','output_descendant','scratch_ancestor'])
def test_worker_cannot_make_controller_state_writable(boundary,roles,tmp_path,monkeypatch,change):
    state,context,runtime=worker_world(roles)
    child=state['extensions']['workflow']['children']['worker']
    if change=='output_ancestor':child['file_contract']['output_roots']=[str(runtime.parent)]
    if change=='output_descendant':child['file_contract']['output_roots']=[str(runtime/'worker/output')]
    if change=='scratch_ancestor':child['file_contract']['scratch_root']=str(runtime.parent)
    monkeypatch.setattr(boundary,'client_selection',lambda *args:pytest.fail('Cannot select native client for writable controller state'))
    with pytest.raises(ValueError):boundary.run_worker(state,'worker',context,client='claude',runtime_root=runtime,timeout_seconds=10)


@pytest.mark.parametrize('field,value',[('is_error',True),('subtype','error_max_budget_usd'),('session_id','different')])
def test_claude_parser_does_not_accept_error_or_changed_identity(boundary,field,value):
    final={'type':'result','subtype':'success','session_id':'native-1','is_error':False}
    final[field]=value
    raw='\n'.join(json.dumps(row) for row in [{'type':'system','subtype':'init','session_id':'native-1','model':'configured'},final])
    observed=boundary.parse_worker('claude',raw.encode())
    assert observed['terminal']!='completed'


def test_inventory_bound_counts_empty_directories(boundary,roles,monkeypatch):
    contract,_,_=roles
    root=Path(contract['output_roots'][0])
    for index in range(3):(root/str(index)).mkdir()
    monkeypatch.setattr(boundary,'MAX_ENTRIES',2)
    with pytest.raises(ValueError):boundary.inspect_files(contract)


def test_inventory_bound_counts_aggregate_bytes(boundary,roles,monkeypatch):
    contract,_,_=roles
    root=Path(contract['output_roots'][0])
    for index in range(3):(root/str(index)).write_bytes(b'x'*10)
    monkeypatch.setattr(boundary,'MAX_TOTAL_BYTES',20,raising=False)
    with pytest.raises(ValueError):boundary.inspect_files(contract)


def test_interrupted_native_worker_keeps_partial_provider_evidence(boundary,roles,tmp_path,monkeypatch):
    state,context,runtime=worker_world(roles)
    script=tmp_path/'fixture-timeout-cli'
    script.write_text('#!/usr/bin/env python3\nimport json,sys,time\nsys.stdin.read()\nprint(json.dumps({"type":"system","subtype":"init","session_id":"began-provider","model":"configured"}),flush=True)\ntime.sleep(10)\n')
    script.chmod(0o700)
    monkeypatch.setattr(boundary,'_authorize_worker',lambda context,paths:context['binding'])
    monkeypatch.setattr(boundary,'client_selection',lambda client,env:({'effort':'high'},str(script)))
    data=boundary.run_worker(state,'worker',context,client='claude',runtime_root=runtime,timeout_seconds=0.1)
    assert data['terminal']=='timed_out'
    raw=(runtime/'worker/stdout.jsonl').read_text()
    assert 'began-provider' in raw
    assert data['usage']['usd_micros'] is None


def test_worker_deadline_reaps_observed_detached_child_and_preserves_unrelated(boundary,roles,tmp_path,monkeypatch):
    import subprocess, signal, time
    state,context,runtime=worker_world(roles)
    pidfile=Path(roles[0]['output_roots'][0])/'detached.pid'
    script=tmp_path/'fixture-detached-cli'
    script.write_text('#!/usr/bin/env python3\nimport subprocess,sys,time,json\nfrom pathlib import Path\nsys.stdin.read()\n'
        +'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(20)"],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n'
        +f'Path({str(pidfile)!r}).write_text(str(p.pid))\n'
        +'print(json.dumps({"type":"system","subtype":"init","session_id":"observed-detached","model":"configured"}),flush=True)\ntime.sleep(20)\n')
    script.chmod(0o700)
    monkeypatch.setattr(boundary,'_authorize_worker',lambda context,paths:context['binding'])
    monkeypatch.setattr(boundary,'client_selection',lambda client,env:({'effort':'high'},str(script)))
    unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(20)'])
    child_pid=None
    try:
        data=boundary.run_worker(state,'worker',context,client='claude',runtime_root=runtime,timeout_seconds=0.5)
        child_pid=int(pidfile.read_text())
        status=subprocess.run(['ps','-o','stat=','-p',str(child_pid)],capture_output=True,text=True,timeout=3).stdout.strip()
        assert not status or status.startswith('Z'), 'Owned detached child survived deadline'
        assert unrelated.poll() is None, 'Unrelated positive control must remain untouched'
        assert data['terminal']=='timed_out'
        manifest=json.loads(Path(data['receipt_path']).read_text())
        assert manifest['process_cleanup']['cleanup_verified'] is True
        assert child_pid in manifest['process_cleanup']['terminated_pids']
    finally:
        unrelated.terminate();unrelated.wait(timeout=3)
        if child_pid:
            try:os.kill(child_pid,signal.SIGKILL)
            except ProcessLookupError:pass


def test_worker_prompt_retains_child_role_and_exact_checks(boundary,roles):
    text=boundary.worker_prompt('Produce an artifact',roles[0],deadline='2026-09-24T12:00:00Z',
        reservation={'id':'work','amounts':{'wall_millis':1000}},checks=[{'id':'output','description':'Exact output bytes'}])
    assert 'parent owns' in text.lower()
    assert 'exact output bytes' in text.lower()
    assert 'do not run a new session start' in text.lower()
    assert 'aggregate reporting' in text.lower()


def test_partial_native_start_keeps_identity_without_inventing_usage(boundary):
    raw=b'{"type":"system","subtype":"init","session_id":"started-before-timeout","model":"configured"}\n'
    parsed=boundary.parse_worker('claude',raw,allow_incomplete=True)
    assert parsed['producer']=='claude:started-before-timeout'
    assert parsed['terminal']=='failed'
    assert parsed['usage']=={'tokens':None,'usd_micros':None}


def test_claude_boundary_requires_exact_native_init_readback(boundary,roles):
    contract,_,_=roles
    init={'type':'system','subtype':'init','session_id':'started','model':'model',
        'tools':['Read','Write','Edit','Bash'],'permissionMode':'default','cwd':contract['scratch_root']}
    config={'client':'claude','file_contract':contract,'selected':{'model':'model','effort':'high'}}
    assert boundary.native_boundary_readback(config,[init])['status']=='ENFORCED'
    for field,value in [('tools',['Read','Write','Bash','Agent']),('permissionMode','bypassPermissions'),('cwd','/foreign')]:
        bad={**init,field:value}
        assert boundary.native_boundary_readback(config,[bad])['status']!='ENFORCED'
    assert boundary.native_boundary_readback(config,[])['status']=='UNKNOWN'


def test_native_environment_failure_cannot_claim_healthy_enforcement(boundary,roles):
    contract,_,_=roles
    config={'client':'claude','file_contract':contract,'selected':{'model':'model','effort':'high'}}
    rows=[{'type':'system','subtype':'init','session_id':'started','model':'model','tools':['Read','Write','Edit','Bash'],'permissionMode':'default','cwd':contract['scratch_root']},
        {'type':'user','message':{'content':[{'type':'tool_result','is_error':True,'content':'sandbox enforcement unavailable'}]}}]
    assert boundary.native_boundary_readback(config,rows)['status']=='UNKNOWN'


def test_codex_readback_requires_exact_native_turn_permissions(boundary,roles):
    contract,_,_=roles
    config={'client':'codex','file_contract':contract,'selected':{'model':'model','model_reasoning_effort':'high'}}
    turn={'type':'turn_context','payload':{'cwd':contract['scratch_root'],'model':'model','effort':'high',
        'approval_policy':'never','sandbox_policy':{'type':'workspace-write','writable_roots':contract['output_roots'],
        'network_access':False,'exclude_slash_tmp':True,'exclude_tmpdir_env_var':True}}}
    assert boundary.native_boundary_readback(config,[turn])['status']=='ENFORCED'
    turn['payload']['sandbox_policy']['writable_roots'].append('/foreign')
    assert boundary.native_boundary_readback(config,[turn])['status']=='UNKNOWN'
