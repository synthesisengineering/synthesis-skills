"""Transport contract fixtures. These are synthetic, not native qualification."""
from copy import deepcopy
import pytest


def test_transport_refuses_unqualified_hosts_before_starting_process():
    import native_resume
    for host in ('codex','claude','cursor','unknown'):
        with pytest.raises(ValueError,match='atomic'):
            native_resume.transport_for(host)


@pytest.mark.parametrize('defect',['session','active','fork','workspace','pending'])
def test_resume_requires_exact_idle_unforked_native_owner(defect):
    import native_resume
    grant={'native_session_id':'01990000-0000-7000-8000-000000000022','workspace':'/fixture'}
    reply={'session':{'sessionId':grant['native_session_id'],'status':'idle','activeTurnId':None,
                     'workspaceRoot':'/fixture','forkedFrom':None,'path':'/fixture/log'},'pendingRequests':[]}
    if defect=='session':reply['session']['sessionId']='foreign'
    elif defect=='active':reply['session'].update(status='running',activeTurnId='active')
    elif defect=='fork':reply['session']['forkedFrom']={'sessionId':'original'}
    elif defect=='workspace':reply['session']['workspaceRoot']='/foreign'
    else:reply['pendingRequests']=[{'id':'human-action'}]
    with pytest.raises(ValueError):native_resume.validate_resumed(grant,reply)


def test_valid_exact_resume_is_only_transport_admission():
    import native_resume
    grant={'native_session_id':'01990000-0000-7000-8000-000000000022','workspace':'/fixture'}
    reply={'session':{'sessionId':grant['native_session_id'],'status':'idle','activeTurnId':None,
                     'workspaceRoot':'/fixture','forkedFrom':None,'path':'/fixture/log'},'pendingRequests':[]}
    assert native_resume.validate_resumed(grant,reply)['sessionId']==grant['native_session_id']


def test_uuid7_is_well_formed_and_unique():
    import native_resume
    import uuid
    values={native_resume.command_id() for _ in range(30)}
    assert len(values)==30
    assert all(uuid.UUID(value).version==7 for value in values)


@pytest.mark.parametrize('mode',['bytes','timeout','bad-frame'])
def test_real_subprocess_transport_is_bounded_and_owned(monkeypatch,tmp_path,mode):
    import native_resume as n
    import subprocess,sys,time
    actual=subprocess.Popen
    code={'bytes':"import sys; sys.stderr.write('x'*300000); sys.stderr.flush()",
        'timeout':'import time; time.sleep(30)',
        'bad-frame':"print('[]',flush=True)"}[mode]
    def process(args,**kwargs):return actual([sys.executable,'-c',code],**kwargs)
    monkeypatch.setattr(n.subprocess,'Popen',process)
    rpc=n.MuseConnection('/fixture/binary',tmp_path,timeout=.25,max_bytes=65536)
    try:
        with pytest.raises((ValueError,TimeoutError,EOFError,OSError)):rpc.call('initialize',{})
    finally:rpc.close()
    assert rpc.process.poll() is not None
    assert rpc.process.stdout.closed and rpc.process.stderr.closed


@pytest.mark.parametrize('failure',['queued','wrong-session','cancelled','timeout','changed-binary'])
def test_owned_launch_refuses_bad_admission_and_retains_unknown(monkeypatch,failure):
    import native_resume as n
    from types import SimpleNamespace
    import hashlib,time
    grant={'client':'muse','native_session_id':'01990000-0000-7000-8000-000000000022','workspace':'/fixture',
        'binary':{'path':'/fixture/binary','sha256':'a'*64,'size':4},'max_wall_seconds':30,'max_output_bytes':65536,
        'resume_command_id':n.command_id(),'turn_command_id':n.command_id()}
    calls=[]
    class RPC:
        def __init__(self,*a,**kw):self.wire=hashlib.sha256();self.size=0;self.stderr=b'';self.process=SimpleNamespace(returncode=0);self.deadline=time.monotonic()+30
        def initialize(self):return {}
        def call(self,method,payload):
            calls.append(method)
            if method=='session/resume':return {'session':{'sessionId':'foreign' if failure=='wrong-session' else grant['native_session_id'],
                'status':'idle','activeTurnId':None,'forkedFrom':None,'workspaceRoot':'/fixture','path':'/fixture/log'},'pendingRequests':[]}
            return {'commandId':grant['turn_command_id'],'status':'accepted','disposition':'queued' if failure=='queued' else 'started','startedNewTurn':failure!='queued','turnId':'native-turn'}
        def terminal(self,*args):raise TimeoutError('synthetic native timeout')
        def close(self):pass
    monkeypatch.setattr(n,'MuseConnection',RPC)
    monkeypatch.setattr(n,'binary_identity',lambda path:{**grant['binary'],'sha256':'b'*64} if failure=='changed-binary' else grant['binary'])
    if failure=='changed-binary':
        with pytest.raises(ValueError,match='changed'):n.launch(grant,'fixture',send_admitted=lambda call:call(),cancelled=lambda:False)
        assert calls==[]
    else:
        result=n.launch(grant,'fixture',send_admitted=lambda call:call(),cancelled=lambda:failure=='cancelled')
        assert n.is_observation(result) and result['status']=='unknown' and result['task_accepted'] is False
        if failure in {'cancelled','wrong-session'}:assert 'turn/start' not in calls


def test_submit_ack_is_bounded_inside_owner_lock(monkeypatch):
 import native_resume as n
 import time,hashlib
 from types import SimpleNamespace
 grant={'client':'muse','native_session_id':'01990000-0000-7000-8000-000000000022','workspace':'/fixture',
   'binary':{'path':'/fixture/binary','sha256':'a'*64,'size':4},'max_wall_seconds':900,'max_output_bytes':65536,
   'resume_command_id':n.command_id(),'turn_command_id':n.command_id()}
 class RPC:
  def __init__(self,*a,**kw):
   self.deadline=time.monotonic()+900;self.wire=hashlib.sha256();self.size=0;self.stderr=b'';self.process=SimpleNamespace(returncode=0)
  def initialize(self):return {}
  def call(self,method,payload):
   if method=='session/resume':return {'session':{'sessionId':grant['native_session_id'],'status':'idle','activeTurnId':None,'forkedFrom':None,'workspaceRoot':'/fixture','path':'/fixture/log'},'pendingRequests':[]}
   assert self.deadline-time.monotonic() <= 11, 'native ack must not hold run lock for the entire 900-second turn budget'
   return {'commandId':grant['turn_command_id'],'status':'accepted','disposition':'started','startedNewTurn':True,'turnId':'actual-test-turn'}
  def terminal(self,*args):
   assert self.deadline-time.monotonic()>800, 'ack cap must not truncate the whole authorized turn budget'
   return {'terminal':'completed'}
  def close(self):pass
 monkeypatch.setattr(n,'MuseConnection',RPC)
 monkeypatch.setattr(n,'binary_identity',lambda _:grant['binary'])
 result=n.launch(grant,'synthetic',send_admitted=lambda operation:operation(),cancelled=lambda:False)
 assert result['status']=='native_terminal'


def test_child_does_not_inherit_foreign_native_identity(monkeypatch,tmp_path):
 import native_resume as n
 import subprocess,sys
 real=subprocess.Popen
 seen={}
 def popen(args,**kwargs):
  seen.update(kwargs['env']);return real([sys.executable,'-c','pass'],**kwargs)
 monkeypatch.setenv('CODEX_THREAD_ID','foreign-parent-thread')
 monkeypatch.setenv('SYNTHESIS_CLIENT_SESSION_REF','codex:foreign-parent-thread')
 monkeypatch.setattr(n.subprocess,'Popen',popen)
 rpc=n.MuseConnection('/synthetic',tmp_path,timeout=1,max_bytes=65536)
 rpc.close()
 assert 'CODEX_THREAD_ID' not in seen and 'SYNTHESIS_CLIENT_SESSION_REF' not in seen


# Permanent regressions retained from the same-round independent review.
import json, os, signal, subprocess, sys, time
from pathlib import Path


class IndependentWatchdog(RuntimeError):
    pass


@pytest.mark.parametrize('mode', ['ordinary-timeout', 'server-request-backpressure'])
def test_native_wall_bound_also_covers_server_reply_backpressure(monkeypatch, tmp_path, mode):
    import native_resume as native
    real_popen = subprocess.Popen
    code = 'import time; time.sleep(30)'
    if mode == 'server-request-backpressure':
        code = """import json,time
for identity in range(2000):
 print(json.dumps({'jsonrpc':'2.0','id':identity,'method':'requiresApproval'}),flush=True)
time.sleep(30)
"""
    def child(arguments, **kwargs):
        return real_popen([sys.executable, '-c', code], **kwargs)
    monkeypatch.setattr(native.subprocess, 'Popen', child)
    rpc = native.MuseConnection('/declared/synthetic/stdio-host', tmp_path, timeout=.25, max_bytes=4*1024*1024)
    fired = False
    original_handler = signal.getsignal(signal.SIGALRM)
    def rescue(signum, frame):
        nonlocal fired
        fired = True
        raise IndependentWatchdog('Independent two-second rescue fired; owner wall bound did not')
    signal.signal(signal.SIGALRM, rescue)
    started = time.monotonic()
    signal.setitimer(signal.ITIMER_REAL, 2)
    caught = None
    try:
        rpc.initialize()
    except (TimeoutError, ValueError, OSError, EOFError, IndependentWatchdog) as error:
        caught = str(error)
    finally:
        elapsed = time.monotonic() - started
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, original_handler)
        # This fixture owns exactly this newly created process group. Kill it
        # before buffered stdin.close(), so a defect cannot strand the test.
        if rpc.process.poll() is None:
            os.killpg(rpc.process.pid, signal.SIGKILL)
        rpc.close()
    print(json.dumps({'mode': mode, 'elapsed': elapsed, 'watchdog': fired,
                      'owner_error': caught, 'bytes': rpc.size, 'returncode': rpc.process.returncode}))
    assert caught is not None
    assert not fired, 'bounded native reader deadlocked while sending a refusal to its child'
    assert elapsed < 1.25
    assert rpc.process.poll() is not None



@pytest.mark.parametrize('mode', ['valid', 'wrong-ack', 'active-resume', 'missing-range', 'empty-range', 'foreign-range', 'empty-cursor', 'wrong-session-type'])
def test_exact_native_wire_submission_and_terminal_source_binding(monkeypatch, tmp_path, mode):
    import native_resume as native
    identity = '01990000-0000-7000-8000-000000000022'
    wire = tmp_path/'submitted.jsonl'
    code = """import sys,json
mode,workspace,identity,wire=sys.argv[1:]
for raw in sys.stdin:
 request=json.loads(raw)
 with open(wire,'a') as stream:stream.write(json.dumps(request)+'\\n')
 method=request.get('method')
 if method=='initialized':continue
 result={}
 if method=='session/resume':
  session={'sessionId':identity,'status':'running' if mode=='active-resume' else 'idle','activeTurnId':None,'workspaceRoot':workspace,'forkedFrom':None,'path':workspace+'/native-fixture.jsonl'}
  result={'session':[] if mode=='wrong-session-type' else session,'pendingRequests':[]}
 if method=='turn/start':
  turn=request['params']['commandId']
  result={'commandId':'foreign-command' if mode=='wrong-ack' else turn,'status':'accepted','disposition':'started','startedNewTurn':True,'turnId':turn}
 print(json.dumps({'jsonrpc':'2.0','id':request['id'],'result':result}),flush=True)
 if method=='turn/start':
  source={'stream':{'kind':'session','id':'foreign-session' if mode=='foreign-range' else identity},'first':{'id':'native-record','sequence':4},'last':{'id':'native-record','sequence':4}}
  terminal={'sessionId':identity,'turnId':turn,'terminal':'completed','viewCursor':'' if mode=='empty-cursor' else 'v:'+identity+':4','sourceRange':{} if mode=='empty-range' else source}
  if mode=='missing-range':terminal.pop('sourceRange')
  print(json.dumps({'jsonrpc':'2.0','method':'turn/completed','params':terminal}),flush=True)
"""
    actual = subprocess.Popen
    observed_process = []
    def fake_native(arguments, **kwargs):
        assert arguments == ['/declared/synthetic-native', 'serve']
        assert kwargs['cwd'] == str(tmp_path)
        process = actual([sys.executable, '-u', '-c', code, mode, str(tmp_path), identity, str(wire)], **kwargs)
        observed_process.append(process)
        return process
    grant = {'client': 'muse', 'native_session_id': identity, 'workspace': str(tmp_path),
        'binary': {'path': '/declared/synthetic-native', 'sha256': 'a'*64, 'size': 4},
        'max_wall_seconds': 2, 'max_output_bytes': 65536,
        'resume_command_id': native.command_id(), 'turn_command_id': native.command_id()}
    monkeypatch.setattr(native.subprocess, 'Popen', fake_native)
    monkeypatch.setattr(native, 'binary_identity', lambda _: dict(grant['binary']))
    result = None
    raised = None
    try:
        result = native.launch(grant, 'Declared synthetic prompt', send_admitted=lambda send: send(), cancelled=lambda: False)
    except Exception as error:
        raised = (type(error).__name__, str(error))
    frames = [json.loads(line) for line in wire.read_text().splitlines()]
    print(json.dumps({'mode': mode, 'result': result, 'raised': raised,
                      'methods': [row['method'] for row in frames]}))
    assert all(process.poll() is not None for process in observed_process)
    assert raised is None, 'malformed native response must yield bounded typed UNKNOWN'
    assert native.is_observation(result) and result['task_accepted'] is False
    if mode == 'valid':
        assert result['status'] == 'native_terminal'
        assert [row['method'] for row in frames] == ['initialize', 'initialized', 'session/resume', 'turn/start']
        assert frames[-1]['params'] == {'commandId': grant['turn_command_id'], 'sessionId': identity,
            'ifBusy': 'queue', 'input': [{'type': 'text', 'text': 'Declared synthetic prompt'}]}
    else:
        assert result['status'] == 'unknown', 'malformed or foreign native source reference cannot establish a verified terminal'

