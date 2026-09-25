"""OpenCode V2 native events/readbacks, pinned to client schema 2.0.16.

V1 CLI and V2 services are distinct surfaces. SSE is live-only; a reconnect is
not historical coverage. Durable sequence gaps remain gaps in the shared reader.
"""
from native_adapter_sdk import (DialectError,boolean,bounded,check_producer,fact,integer,
    object_value,qualify,text,unwrap,usage)
ADAPTER_VERSION='opencode-v2-2.0.16'
SURFACES=('opencode-cli','opencode-sdk-v2')
SUPPORTED_SCHEMAS=('opencode.v2.events.2.0.16','opencode.v2.readback.2.0.16','synthesis.native_capture.v1')
EVENTS=frozenset(('session.created','session.execution.started','session.execution.succeeded','session.execution.failed',
 'session.execution.interrupted','session.tool.input.started','session.tool.input.ended','session.tool.called','session.tool.success','session.tool.failed',
 'session.step.started','session.step.ended','session.step.failed','session.usage.recorded','session.usage.updated',
 'session.compaction.started','session.compaction.ended','session.compaction.failed','session.inbox.delivered',
 'session.inbox.cancelled','permission.asked','permission.replied','session.text.started','session.text.delta','session.text.ended',
 'session.reasoning.started','session.reasoning.delta','session.reasoning.ended','session.status','session.idle','session.shell.started','session.shell.ended'))
READBACKS=frozenset(('session.get','session.message'))

def _error(value):
    value=object_value(value,'native structured error')
    text(value.get('type'),'error type');text(value.get('message'),'error message',1024*1024,empty=True)
    if 'status' in value:integer(value['status'],'error status')


def _native_data(event,data):
    """Validate the implemented fields of the pinned native event grammar."""
    if event=='session.created':
        for key in ('projectID','slug','version'):text(data.get(key),key)
        location=object_value(data.get('location'),'native location');text(location.get('directory'),'location directory')
    if event in ('session.execution.failed','session.step.failed','session.compaction.failed'):_error(data.get('error'))
    if event.startswith('session.compaction.'):
        if data.get('reason') not in ('auto','manual'):raise DialectError('unsupported compaction reason')
        if not event.endswith('failed'):text(data.get('recent'),'recent context',1024*1024,empty=True)
        if event.endswith('ended'):text(data.get('text'),'compaction text',1024*1024,empty=True)
    if event.startswith('session.step.') or event.startswith('session.tool.'):
        text(data.get('assistantMessageID'),'assistant message ID')
    if event=='session.step.started':
        text(data.get('agent'),'native agent');integer(data.get('started'),'step start')
        model=object_value(data.get('model'),'native model');text(model.get('id'),'model ID');text(model.get('providerID'),'provider ID')
    if event.startswith('session.inbox.'):text(data.get('inboxID'),'inbox ID')
    if event=='session.usage.updated':_tokens(data.get('tokens'))
    if event in ('session.step.ended','session.usage.recorded','session.usage.updated'):
        value=data.get('cost')
        if isinstance(value,bool) or not isinstance(value,(int,float)) or value<0:raise DialectError('native cost field malformed; billing remains unqualified')
    if event=='permission.asked':
        text(data.get('id'),'permission ID');text(data.get('action'),'permission action')
        resources=data.get('resources')
        if not isinstance(resources,list):raise DialectError('permission resources must be an array')
        for value in resources:text(value,'permission resource')
    if event=='permission.replied':text(data.get('requestID'),'permission request ID')
    if event=='session.status':
        status=object_value(data.get('status'),'session status')
        if status.get('type') not in ('idle','busy','retry'):raise DialectError('unknown session status')
        if status['type']=='retry':
            integer(status.get('attempt'),'retry attempt');integer(status.get('next'),'retry deadline');text(status.get('message'),'retry message')


def _row(row):
    p,c=unwrap(row,'opencode',surfaces=SURFACES)
    if c and c['event'] in READBACKS:return p,c,c['event'],None
    event=text(p.get('type'),'V2 event type')
    if event not in EVENTS:raise DialectError('unsupported OpenCode V2 event')
    if c and c['event']!=event:raise DialectError('OpenCode capture event mismatch')
    text(p.get('id'),'event identity');integer(p.get('created'),'event timestamp')
    data=object_value(p.get('data'),'V2 event data');text(data.get('sessionID'),'V2 session identity')
    _native_data(event,data)
    durable=p.get('durable')
    if event.startswith('session.') and event not in ('session.usage.updated','session.text.delta','session.reasoning.delta','session.status','session.idle'):
        durable=object_value(durable,'durable source locator')
    sequence=None
    if durable is not None:
        object_value(durable,'durable source locator')
        if set(durable)!={'aggregateID','seq','version'} or durable['aggregateID']!=data['sessionID']:raise DialectError('durable aggregate mismatch')
        sequence=integer(durable['seq'],'native durable sequence')
        version=2 if event in ('session.tool.success','session.tool.failed') else 1
        if type(durable['version']) is not int or durable['version']!=version:raise DialectError('unsupported durable event version')
    return p,c,event,sequence

def qualify_source(header,*,expected_root_session_id,expected_thread_id=None,expected_parent_thread_id=None,expected_agent_id=None):
    p,c,e,seq=_row(header)
    if e=='session.created':data=p['data'];session=data['sessionID'];version=text(data.get('version'),'native source version');parent=data.get('parentID')
    elif e=='session.get':session=text(p.get('id'),'session ID');parent=p.get('parentID');version=c['producer_version']
    else:raise DialectError('OpenCode source must begin with session.created or exact session readback')
    if parent is not None:text(parent,'parent session')
    if expected_agent_id is not None:raise DialectError('OpenCode source agent-path join is not implemented')
    return qualify('opencode',header,session=session,version=version,surface=c['surface'] if c else 'opencode-sdk-v2',
        schema='opencode.v2.readback.2.0.16' if e=='session.get' else 'opencode.v2.events.2.0.16',parent=parent,
        expected_root_session_id=expected_root_session_id,expected_thread_id=expected_thread_id,
        expected_parent_thread_id=expected_parent_thread_id,capture=c)

def _tokens(value):
    v=object_value(value,'token counters');cache=object_value(v.get('cache'),'cache counters')
    if set(v)!={'input','output','reasoning','cache'} or set(cache)!={'read','write'}:raise DialectError('unknown OpenCode counter vector')
    counts={k:integer(v[k],k) for k in ('input','output','reasoning')}
    read=integer(cache['read'],'cache read');write=integer(cache['write'],'cache write')
    return {'input_tokens':counts['input'],'output_tokens':counts['output'],'total_tokens':counts['input']+counts['output'],
            'reasoning_output_tokens':counts['reasoning'],'cached_input_tokens':read,'cache_write_tokens':write}

def _content(value):
    if not isinstance(value,list) or not value:raise DialectError('tool content must be a nonempty array')
    for part in value:
        object_value(part,'tool content block')
        if part.get('type')=='text':text(part.get('text'),'tool text',1024*1024,empty=True)
        elif part.get('type')=='file':
            # Preserve a typed reference; never open a native supplied path.
            text(part.get('mime'),'file MIME');text(part.get('uri'),'file URI')
            if part.get('name') is not None:text(part['name'],'file name')
        else:raise DialectError('unsupported tool content block')
    return value

def decode_record(row,producer,*,mode='synthetic',source_locator=None):
    p,c,event,seq=_row(row);check_producer(producer,'opencode',c)
    d=p.get('data') if event not in READBACKS else p
    if event not in READBACKS and d['sessionID']!=producer['thread_id']:raise DialectError('OpenCode session mismatch')
    def f(kind,status,data,**kw):return fact(kind,status,data,row,mode=mode,source_locator=source_locator,record_id=p.get('id'),sequence=seq,**kw)
    if event=='session.created':
        if d.get('parentID')!=producer.get('parent_thread_id') or d.get('version')!=producer['producer_version']:raise DialectError('source lineage/version changed')
        return []
    if event=='session.get':
        if d.get('id')!=producer['thread_id'] or d.get('parentID')!=producer.get('parent_thread_id'):raise DialectError('session readback identity mismatch')
        return []
    if event=='session.message':
        # Readback custody binds the session request. The payload's message ID
        # alone never authenticates a session or a claimed provider response.
        if d.get('type')!='assistant':raise DialectError('unsupported message readback')
        mid=text(d.get('id'),'assistant message ID');parts=d.get('content')
        if not isinstance(parts,list) or len(parts)>64:raise DialectError('assistant content exceeds the bounded 64-part readback; retain reference and page through its owner')
        time=object_value(d.get('time'),'message time');integer(time.get('created'),'created')
        if 'completed'in time:integer(time['completed'],'completed')
        facts=[]
        for index,part in enumerate(parts):
            object_value(part,'assistant content')
            if part.get('type') in ('text','reasoning'):
                text(part.get('text'),'assistant text',1024*1024,empty=True);continue
            if part.get('type')!='tool':raise DialectError('unsupported assistant content')
            call=text(part.get('id'),'tool ID');name=text(part.get('name'),'tool name');state=object_value(part.get('state'),'tool state')
            status=state.get('status')
            if status not in ('streaming','running','completed','error'):raise DialectError('unsupported tool state')
            if status=='streaming':continue
            args=object_value(state.get('input'),'tool input')
            facts.append(f('tool.call','observed',{'tool':name,'arguments':args,'permission_granted':False},call_id=call,subrecord=index*2))
            if status in ('completed','error'):
                content=_content(state.get('content')) if status=='completed' or 'content'in state else None
                if status=='error':object_value(state.get('error'),'structured tool error')
                facts.append(f('tool.result','failed' if status=='error' else 'observed',{'result':content,'error':state.get('error'),'outcome_pass':False,'native_success_reported':status=='completed'},call_id=call,subrecord=index*2+1))
        if 'tokens'in d:
            counts=_tokens(d['tokens']);phase='final' if 'completed'in time and d.get('finish') in ('stop','length','tool-calls','content-filter','error','unknown') else 'provisional'
            facts.append(f('usage.snapshot','observed',usage('opencode',producer,mid,counts,phase=phase,raw=d['tokens']),subrecord=len(parts)*2))
        return facts
    if event=='session.tool.input.started':return [f('tool.identity','observed',{'tool':text(d.get('name'),'tool name'),'assistant_message_id':text(d.get('assistantMessageID'),'message ID')},call_id=text(d.get('id'),'tool ID'))]
    if event=='session.tool.called':
        call=text(d.get('id'),'tool ID');object_value(d.get('input'),'tool input');boolean(d.get('executed'),'executed')
        return [f('tool.call','observed',{'arguments':d['input'],'native_executed':d['executed'],'tool_name':'requires tool.identity join','permission_granted':False},call_id=call)]
    if event in ('session.tool.success','session.tool.failed'):
        call=text(d.get('id'),'tool ID');boolean(d.get('executed'),'executed')
        content=_content(d.get('content')) if event=='session.tool.success' or 'content'in d else None
        if event=='session.tool.failed':_error(d.get('error'))
        return [f('tool.result','failed' if event.endswith('failed') else 'observed',{'result':content,'error':d.get('error'),'native_executed':d['executed'],'outcome_pass':False},call_id=call)]
    if event=='session.step.ended':
        finish=d.get('finish')
        if finish not in ('stop','length','tool-calls','content-filter','error','unknown'):raise DialectError('unsupported finish')
        mid=text(d.get('assistantMessageID'),'message ID');counts=_tokens(d.get('tokens'))
        return [f('usage.snapshot','observed',usage('opencode',producer,mid,counts,raw=d['tokens']))]
    if event=='session.usage.recorded':
        if d.get('source') not in ('title','compaction'):raise DialectError('unsupported usage source')
        return [f('usage.snapshot','observed',usage('opencode',producer,p['id'],_tokens(d.get('tokens')),raw=d['tokens']))]
    if event=='session.usage.updated':return [f('usage.snapshot','observed',{'grammar':'opencode.session_usage_updated','aggregation':'aggregate_view','phase':'unknown','countable':False,'measurement_id':None,'last':None,'totals':None,'raw_usage':d,'scope_nonoverlap':'UNKNOWN','billing_cost':None,'missingness':['aggregate_is_not_an_additive_response']})]
    if event=='session.execution.interrupted':
        if d.get('reason') not in ('user','shutdown','superseded','inactivity'):raise DialectError('unsupported interruption reason')
        return [f('lifecycle.cancelled','observed',{'native_status':'interrupted','reason':d['reason']})]
    if event.startswith('session.execution.') or event in ('session.status','session.idle'):
        return [f('lifecycle.observation','observed',{'native_event':event,'native_data':d,'portable_completion':False})]
    if event.startswith('session.compaction.'):
        return [f('context.compaction','observed',{'native_event':event,'native_data':d,'recovery_proven':False})]
    if event.startswith('permission.'):
        if event=='permission.replied' and d.get('reply') not in ('once','always','reject'):raise DialectError('unsupported native permission reply')
        return [f('permission.observation','observed',{'native_event':event,'native_data':d,'grants_authority':False,'enforcement_proven':False})]
    if event.startswith('session.inbox.'):
        return [f('native.inbox','observed',{'native_event':event,'native_data':d,'human_identity_proven':False,'grants_authority':False})]
    if event.startswith('session.shell.'):
        shell=object_value(d.get('shell'),'native shell');call=text(shell.get('id'),'shell ID')
        for key in ('command','cwd','shell','file'):text(shell.get(key),'shell '+key)
        metadata=object_value(shell.get('metadata'),'shell metadata')
        if metadata.get('sessionID')!=producer['thread_id']:raise DialectError('shell native session mismatch')
        timing=object_value(shell.get('time'),'shell time');integer(timing.get('started'),'shell start')
        if 'pid' in shell:integer(shell['pid'],'shell PID')
        if event.endswith('started'):
            if shell.get('status')!='running':raise DialectError('shell start is not running')
            return [f('tool.call','observed',{'tool':'shell','arguments':{'command':shell['command'],'cwd':shell['cwd']},'execution_origin':'native_direct_shell','permission_granted':False},call_id=call)]
        if shell.get('status') not in ('exited','timeout','killed'):raise DialectError('shell terminal state missing')
        integer(timing.get('completed'),'shell completion')
        code=shell.get('exit')
        if type(code) is not int or not -(2**31)<=code<2**31:raise DialectError('shell exit code is unknown or malformed')
        output=object_value(d.get('output'),'shell output');text(output.get('output'),'shell stdout',1024*1024,empty=True)
        cursor=integer(output.get('cursor'),'output cursor');size=integer(output.get('size'),'output size')
        if boolean(output.get('truncated'),'output truncation') or cursor!=size or len(output['output'].encode())!=size:
            raise DialectError('shell material output incomplete; retain native reference and reconcile its missing range')
        return [f('tool.result','failed' if code or shell['status']!='exited' else 'observed',{'result':{'exit_code':code,'output':output['output'],'shell_status':shell['status']},'execution_origin':'native_direct_shell','outcome_pass':False,'permission_enforcement':'UNKNOWN'},call_id=call)]
    if event.startswith(('session.text.','session.reasoning.')):
        text(d.get('assistantMessageID'),'assistant message');integer(d.get('ordinal'),'narrative ordinal')
        if event.endswith('delta'):text(d.get('delta'),'narrative delta',1024*1024,empty=True)
        if event.endswith('ended'):text(d.get('text'),'narrative text',1024*1024,empty=True)
        return []
    if event in ('session.tool.input.ended','session.step.started'):
        text(d.get('assistantMessageID'),'assistant message')
        if event=='session.tool.input.ended':text(d.get('id'),'tool ID');text(d.get('text'),'raw tool input',1024*1024,empty=True)
        return []
    if event=='session.step.failed':return [f('lifecycle.error','observed',{'native_data':d,'portable_completion':False})]
    raise DialectError('unsupported OpenCode event')

def is_ignored_projection(projected,producer):return False

def request_shape(operation,session_id,*,message_id=None):
    """Read/interrupt transport plans only; no execution or permission replies."""
    text(session_id,'session ID',256)
    if any(x in session_id for x in ('/','?','#','%')):raise DialectError('unsafe session ID')
    if operation=='session.get':return {'method':'GET','path':'/api/session/'+session_id,'authority_granted':False}
    if operation=='session.message':
        text(message_id,'message ID',256)
        if any(x in message_id for x in ('/','?','#','%')):raise DialectError('unsafe message ID')
        return {'method':'GET','path':'/api/session/'+session_id+'/message/'+message_id,'authority_granted':False}
    if operation=='session.interrupt':return {'method':'POST','path':'/api/session/'+session_id+'/interrupt','authority_granted':False,'requires_owner_action_admission':True}
    raise DialectError('operation not supported; permission/config/scheduler mutations belong to their owners')

def describe_contract():
    return {'client':'opencode','adapter_version':ADAPTER_VERSION,'supported_schemas':list(SUPPORTED_SCHEMAS),
        'schema_package':'@opencode/client@2.0.16','native_acceptance':'UNKNOWN','authority_granted':False,
        'implemented':['native_identity','tool_worker','compaction','cancellation','usage','recovery'],
        'capabilities':{k:'YES' for k in ('skill_discovery','native_identity','permission_enforcement','tool_worker','tool_outcome','compaction','cancellation','usage','recovery')}|{'continuation':'OWNER_REQUIRED'},
        'limits':['V1 CLI cannot qualify V2 contracts','Live event subscriptions do not replay or reconnect automatically',
            'Durable seq must remain contiguous; missing data is a reader gap','Tool names require input-start identity join',
            'V2 network and embedded hosts have separate lifetime/transport qualification','No permission reply, config/trust, Goal or scheduler action is emitted']}


def record_sequences(row, producer):
    p, capture, event, native_sequence = _row(row)
    check_producer(producer, "opencode", capture)
    result = {"capture": capture["sequence"]} if capture else {}
    if native_sequence is not None: result["durable"] = native_sequence
    return result
