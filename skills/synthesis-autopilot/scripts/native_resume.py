"""Bounded exact-session native transport. Protocol outcomes are not task grades.

Muse's writer lease is required before sending a queued turn. Other transports
remain unavailable until they provide an atomic same-session ownership seam.
No permissions, trust settings, provider, model or approval mode are changed.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
import uuid
import re
import shutil

_OBSERVATION_KEY=object()


class TransportObservation(dict):
    def __init__(self,value,*,key):
        if key is not _OBSERVATION_KEY:raise ValueError('transport observations come from the owned native operation')
        super().__init__(value);self._key=key


def _observation(value):
    return TransportObservation(value,key=_OBSERVATION_KEY)


def is_observation(value):
    return isinstance(value,TransportObservation) and value._key is _OBSERVATION_KEY


def command_id():
    value=(int(time.time()*1000)<<80) | (7<<76) | (int.from_bytes(os.urandom(2),'big')&0xfff)<<64
    value|=(2<<62)|(int.from_bytes(os.urandom(8),'big')&((1<<62)-1))
    return str(uuid.UUID(int=value))


def transport_for(client):
    if client!='muse':
        raise ValueError('native atomic exact-session ownership is not qualified for '+str(client))
    return 'muse-msp-writer-lease'


def installed_binary(client):
    transport_for(client)
    launcher=shutil.which('muse')
    if not launcher:raise ValueError('installed Muse executable is unavailable')
    path=Path(launcher).resolve()
    with path.open('rb') as stream:prefix=stream.read(2)
    if prefix==b'#!':
        version=(path.parent/'.muse-version').read_text().strip()
        if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+-R[0-9]+(?:\.[0-9]+)?',version):
            raise ValueError('installed Muse binary version selector is invalid')
        path=path.parent/('muse-bin-'+version)
    return binary_identity(path)


def binary_identity(path):
    path=Path(path).expanduser().absolute()
    if path.is_symlink() or not path.is_file() or not os.access(path,os.X_OK):
        raise ValueError('native executable must be a current nonsymlink executable file')
    with path.open('rb') as stream:
        first=stream.read(4)
        if first not in (b'\x7fELF',b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca'):
            raise ValueError('native transport binds the installed binary, not a mutable launcher script')
        digest=hashlib.sha256(first)
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return {'path':str(path),'sha256':digest.hexdigest(),'size':path.stat().st_size}


def validate_resumed(grant,reply):
    if not isinstance(reply,dict) or not isinstance(reply.get('session'),dict):
        raise ValueError('native resume response has no typed session object')
    session=reply['session']
    if (session.get('sessionId')!=grant['native_session_id'] or session.get('status')!='idle'
        or 'activeTurnId' not in session or session['activeTurnId'] is not None
        or 'forkedFrom' not in session or session['forkedFrom'] is not None or session.get('workspaceRoot')!=grant['workspace']
        or not isinstance(session.get('path'),str) or not session['path']
        or reply.get('pendingRequests')!=[]):
        raise ValueError('native resume did not acquire the exact idle session without pending human requests')
    return session


def validate_terminal(data,session,turn):
    """Accept only supported exact-session durable terminal provenance."""
    if (not isinstance(data,dict) or data.get('sessionId')!=session or data.get('turnId')!=turn
        or not isinstance(data.get('terminal'),str) or data['terminal'] not in {'completed','failed','cancelled'}
        or not isinstance(data.get('viewCursor'),str) or not 0<len(data['viewCursor'])<=4096):
        raise ValueError('native terminal has invalid identity, disposition or cursor')
    source=data.get('sourceRange')
    if not isinstance(source,dict) or set(source)!={'stream','first','last'}:
        raise ValueError('native terminal lacks a typed durable source range')
    if source['stream'] not in ({'kind':'session','id':session},{'kind':'run','id':turn}):
        raise ValueError('native terminal source belongs to another or unsupported stream')
    for name in ('first','last'):
        row=source[name]
        if (not isinstance(row,dict) or set(row)!={'id','sequence'}
            or not isinstance(row['id'],str) or not 0<len(row['id'])<=512
            or type(row['sequence']) is not int or row['sequence']<0):
            raise ValueError('native terminal source position is malformed')
    first,last=source['first'],source['last']
    if last['sequence']<first['sequence'] or first['sequence']==last['sequence'] and first['id']!=last['id']:
        raise ValueError('native terminal source range is reversed or contradictory')
    for name in ('durationMs','timeToFirstTokenMs'):
        if name in data and (type(data[name]) is not int or data[name]<0):
            raise ValueError('native terminal contains invalid measured duration')
    return data


def _decode_frame(raw):
    def pairs(values):
        result={}
        for key,value in values:
            if key in result:raise ValueError('native protocol contains duplicate fields')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda value:(_ for _ in ()).throw(ValueError('native protocol contains nonfinite JSON')))


class RPCError(ValueError):
    def __init__(self,error):
        self.error=error
        super().__init__('native RPC refused: '+json.dumps(error,sort_keys=True)[:4096])


class MuseConnection:
    """One bounded stdio connection; its own process group is the only signal target."""
    def __init__(self,binary,workspace,*,timeout=120,max_bytes=1024*1024,extra_args=()):
        self.deadline=time.monotonic()+timeout;self.max_bytes=max_bytes
        self.size=0;self.buffer=b'';self.frames=[];self.notifications=[];self.stderr=bytearray()
        self.wire=hashlib.sha256();self.next_id=0;self.outgoing=bytearray();self.sent_bytes=0
        environment=dict(os.environ,MUSE_NO_AUTO_UPDATE='1')
        # A native child establishes its own identity. A parent's hook/seat
        # hints are not transferable and must not poison that authentication.
        for name in ('CODEX_THREAD_ID','CLAUDE_CODE_SESSION_ID','CLAUDE_CODE_HOST_SESSION_ID',
                     'CLAUDE_PID','CLAUDECODE','MUSE_SESSION_ID','SYNTHESIS_CLIENT_SESSION_REF',
                     'SYNTHESIS_COORDINATION_SESSION'):
            environment.pop(name,None)
        self.process=subprocess.Popen([str(binary),'serve',*extra_args],cwd=workspace,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=environment,start_new_session=True,bufsize=0)
        os.set_blocking(self.process.stdin.fileno(),False)
        self.selector=selectors.DefaultSelector()
        self.selector.register(self.process.stdout,selectors.EVENT_READ,'stdout')
        self.selector.register(self.process.stderr,selectors.EVENT_READ,'stderr')

    def send(self,value):
        raw=(json.dumps(value,separators=(',',':'))+'\n').encode()
        if len(raw)>256*1024 or self.sent_bytes+len(self.outgoing)+len(raw)>self.max_bytes:
            raise ValueError('native transport input bound reached')
        self.outgoing.extend(raw)
        self._flush_outgoing()

    def _flush_outgoing(self):
        # Never block the reader on an approval reply. An uncooperative host
        # may fill its stdin while still filling stdout; both directions share
        # the same bounded event loop, and no buffered close can flush forever.
        while self.outgoing:
            if time.monotonic()>=self.deadline:raise TimeoutError('native transport wall bound reached')
            try:
                written=os.write(self.process.stdin.fileno(),self.outgoing)
            except BlockingIOError:
                break
            if written<=0:raise EOFError('native transport input closed')
            self.sent_bytes+=written;del self.outgoing[:written]
        registered=self.process.stdin in [key.fileobj for key in self.selector.get_map().values()]
        if self.outgoing and not registered:
            self.selector.register(self.process.stdin,selectors.EVENT_WRITE,'stdin')
        elif not self.outgoing and registered:
            self.selector.unregister(self.process.stdin)

    def _read(self,seconds=.2):
        if time.monotonic()>=self.deadline:raise TimeoutError('native transport wall bound reached')
        for key,_ in self.selector.select(min(seconds,max(0,self.deadline-time.monotonic()))):
            if key.data=='stdin':
                self._flush_outgoing();continue
            raw=os.read(key.fileobj.fileno(),65536)
            if not raw:
                self.selector.unregister(key.fileobj)
                continue
            self.size+=len(raw)
            if self.size>self.max_bytes:raise ValueError('native transport output bound reached')
            self.wire.update(key.data.encode()+b'\0'+raw)
            if key.data=='stderr':self.stderr.extend(raw);continue
            self.buffer+=raw
            if len(self.buffer)>256*1024:raise ValueError('native transport frame bound reached')
            while b'\n' in self.buffer:
                line,self.buffer=self.buffer.split(b'\n',1)
                if not line:continue
                frame=_decode_frame(line)
                if not isinstance(frame,dict):raise ValueError('native protocol frame is not an object')
                if frame.get('jsonrpc')!='2.0':raise ValueError('native protocol version mismatch')
                if frame.get('id') is not None:
                    if type(frame['id']) not in (int,str):raise ValueError('native protocol request identity is malformed')
                    if 'method' in frame:
                        # Unknown server request receives no fabricated human approval.
                        self.send({'jsonrpc':'2.0','id':frame['id'],'error':{'code':-32601,'message':'Unattended client cannot supply this action'}})
                    else:self.frames.append(frame)
                else:self.notifications.append(frame)
            if len(self.frames)+len(self.notifications)>4096:raise ValueError('native frame count bound reached')
        if self.process.poll() is not None and not any(key.data in {'stdout','stderr'} for key in self.selector.get_map().values()):
            raise EOFError('native transport closed before a verified terminal response')

    def call(self,method,params):
        self.next_id+=1;identity=self.next_id
        self.send({'jsonrpc':'2.0','id':identity,'method':method,'params':params})
        while True:
            for index,frame in enumerate(self.frames):
                if type(frame.get('id')) is int and frame['id']==identity:
                    self.frames.pop(index)
                    if 'error' in frame:raise RPCError(frame['error'])
                    if not isinstance(frame.get('result'),dict):raise ValueError('native result is not an object')
                    return frame['result']
            self._read()

    def initialize(self):
        reply=self.call('initialize',{'clientInfo':{'name':'synthesis_supervision','version':'1'},
            'capabilities':{'experimentalApi':False,'requestedCapabilities':[],'userInputDialogs':False}})
        self.send({'jsonrpc':'2.0','method':'initialized'})
        return reply

    def terminal(self,session,turn,cancelled):
        cancelled_once=False
        while True:
            while self.notifications:
                frame=self.notifications.pop(0);data=frame.get('params',{})
                if not isinstance(data,dict):raise ValueError('native notification parameters are not an object')
                if frame.get('method')=='turn/completed' and data.get('sessionId')==session and data.get('turnId')==turn:
                    return validate_terminal(data,session,turn)
            if cancelled() and not cancelled_once:
                self.call('turn/cancel',{'commandId':command_id(),'sessionId':session,'turnId':turn})
                cancelled_once=True
            self._read()

    def close(self):
        try:self.process.stdin.close()
        except (OSError,ValueError):pass
        try:self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(self.process.pid,signal.SIGTERM)
            try:self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid,signal.SIGKILL);self.process.wait(timeout=2)
        self.selector.close()
        self.process.stdout.close()
        self.process.stderr.close()


def launch(grant,prompt,*,send_admitted,cancelled):
    transport_for(grant['client'])
    if binary_identity(grant['binary']['path'])!=grant['binary']:
        raise ValueError('native executable changed after owner preparation')
    rpc=MuseConnection(grant['binary']['path'],grant['workspace'],timeout=grant['max_wall_seconds'],max_bytes=grant['max_output_bytes'])
    outcome={'status':'unknown','task_accepted':False,'native_session_id':grant['native_session_id']}
    try:
        rpc.initialize()
        resumed=rpc.call('session/resume',{'commandId':grant['resume_command_id'],
            'sessionId':grant['native_session_id'],'excludeItems':True})
        session=validate_resumed(grant,resumed)
        outcome['native_source_path']=session['path']
        if cancelled():raise ValueError('prepared launch was cancelled before native turn')
        def send():
            original_deadline=rpc.deadline
            rpc.deadline=min(original_deadline,time.monotonic()+10)
            try:
                result=rpc.call('turn/start',{'commandId':grant['turn_command_id'],
                    'sessionId':grant['native_session_id'],'ifBusy':'queue',
                    'input':[{'type':'text','text':prompt}]})
            finally:
                rpc.deadline=original_deadline
            if (result.get('commandId')!=grant['turn_command_id'] or result.get('status')!='accepted'
                or result.get('disposition')!='started' or result.get('startedNewTurn') is not True
                or not isinstance(result.get('turnId'),str) or not 0<len(result['turnId'])<=512):
                raise ValueError('native turn admission is uncertain; do not retry')
            return result
        ack=send_admitted(send)
        outcome['turn_id']=ack['turnId'];outcome['admission']=ack
        terminal=rpc.terminal(grant['native_session_id'],ack['turnId'],cancelled)
        outcome.update(status='native_terminal',terminal=terminal)
    except (ValueError,OSError,EOFError,TimeoutError) as exc:
        outcome.update(status='unknown',diagnostic=str(exc)[:4096])
        if isinstance(exc,RPCError):outcome['rpc_error']=exc.error
        # Owned subprocess termination below is not evidence of native/provider cancellation.
        outcome['cancellation_outcome']='UNKNOWN'
    finally:
        rpc.close()
        outcome.update(wire_sha256=rpc.wire.hexdigest(),output_bytes=rpc.size,
            stderr_sha256=hashlib.sha256(rpc.stderr).hexdigest(),process_exit=rpc.process.returncode)
    return _observation(outcome)
