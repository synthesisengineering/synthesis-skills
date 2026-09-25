"""Versioned Copilot hook and SDK event observations; no permission emitter."""
from native_adapter_sdk import (DialectError,boolean,bounded,check_producer,fact,integer,
    object_value,qualify,text,unwrap,usage)
ADAPTER_VERSION='copilot-hooks-sdk-v1'
SURFACES=('copilot-cli','copilot-vscode','copilot-cloud')
SUPPORTED_SCHEMAS=('copilot.hooks.camel.v1','copilot.hooks.pascal.v1','copilot.sdk.events.1.0.14','synthesis.native_capture.v1')
HOOKS={'SessionStart':'sessionStart','SessionEnd':'sessionEnd','PreToolUse':'preToolUse','PostToolUse':'postToolUse',
       'PostToolUseFailure':'postToolUseFailure','Stop':'agentStop','SubagentStart':'subagentStart','SubagentStop':'subagentStop',
       'UserPromptSubmit':'userPromptSubmitted','PreCompact':'preCompact','PermissionRequest':'permissionRequest','Notification':'notification'}
HOOK_EVENTS=set(HOOKS.values())|{'errorOccurred'}

def _row(row):
    p,c=unwrap(row,'copilot',surfaces=SURFACES)
    if p.get('type') in ('session.start','tool.execution_start','tool.execution_complete','assistant.usage','abort','session.error','assistant.turn_end','session.shutdown','user.message','session.compaction_start','session.compaction_complete','permission.requested','permission.completed'):
        object_value(p.get('data'),'SDK event data');text(p.get('id'),'SDK event ID');text(p.get('timestamp'),'SDK timestamp')
        if p.get('parentId') is not None:text(p['parentId'],'SDK previous event')
        if c and c['event']!=p['type']:raise DialectError('SDK event label mismatch')
        return p,c,p['type'],'sdk'
    native=p.get('hook_event_name')
    if native is not None:
        text(native,'Pascal hook event')
        if native not in HOOKS:raise DialectError('unsupported PascalCase hook')
        event=HOOKS[native];grammar='pascal'
        if c and c['event'] not in (event,native):raise DialectError('hook capture route mismatch')
    else:
        if c is None:raise DialectError('camelCase hook requires exact configured transport route')
        event=c['event'];grammar='camel'
        if event not in HOOK_EVENTS:raise DialectError('unsupported camelCase hook')
    return p,c,event,grammar

def _session(p,g):return p['data'].get('sessionId') if g=='sdk' and p['type']=='session.start' else p.get('session_id' if g=='pascal' else 'sessionId')

def qualify_source(header,*,expected_root_session_id,expected_thread_id=None,expected_parent_thread_id=None,expected_agent_id=None):
    p,c,event,g=_row(header)
    if event not in ('sessionStart','session.start'):raise DialectError('Copilot source must start with session identity')
    if expected_parent_thread_id is not None or expected_agent_id is not None or p.get('agentId') is not None:raise DialectError('Copilot child source join is not qualified')
    version=p['data'].get('copilotVersion') if g=='sdk' else c['producer_version'] if c else None
    if g=='sdk':
        text(version,'Copilot version');integer(p['data'].get('version'),'event schema version')
        if p['data'].get('detachedFromSpawningParentSessionId') is not None:raise DialectError('detached child cannot become root')
    return qualify('copilot',header,session=_session(p,g),version=version,surface=c['surface'] if c else 'copilot-cli',schema='copilot.sdk.events.1.0.14' if g=='sdk' else 'copilot.hooks.'+g+'.v1',
        expected_root_session_id=expected_root_session_id,expected_thread_id=expected_thread_id,capture=c)

def decode_record(row,producer,*,mode='synthetic',source_locator=None):
    p,c,event,g=_row(row);check_producer(producer,'copilot',c)
    session=_session(p,g)
    if session is not None and session!=producer['thread_id']:raise DialectError('Copilot session mismatch')
    if g!='sdk' and session is None:raise DialectError('hook lacks native session identity')
    def f(kind,status,data,**kw):return fact(kind,status,data,row,mode=mode,source_locator=source_locator,record_id=p.get('id'),
        call_scope={'schema':'copilot.agent','session_id':producer['thread_id'],'agent_id':p.get('agentId')} if g=='sdk' else None,**kw)
    if g=='sdk':
        d=p['data'];agent=p.get('agentId')
        if event=='abort' and d.get('reason') not in ('user_initiated','remote_command','user_abort','autopilot_credit_limit'):
            raise DialectError('unsupported native abort reason')
        if event=='user.message':text(d.get('content'),'native user message',1024*1024,empty=True)
        if event=='assistant.turn_end':text(d.get('turnId'),'native turn ID')
        if event=='session.error':
            text(d.get('errorType'),'native error type');text(d.get('message'),'native error message',1024*1024,empty=True)
        if event=='session.compaction_complete':boolean(d.get('success'),'compaction success')
        if event=='session.shutdown':
            text(d.get('shutdownType'),'shutdown type');integer(d.get('sessionStartTime'),'session start time')
            object_value(d.get('codeChanges'),'shutdown changes');object_value(d.get('modelMetrics'),'shutdown model metrics')
            duration=d.get('totalApiDurationMs')
            if isinstance(duration,bool) or not isinstance(duration,(int,float)) or duration<0:raise DialectError('invalid API duration')
        if event.startswith('permission.'):
            text(d.get('requestId'),'permission request ID')
            if event=='permission.requested':
                request=object_value(d.get('permissionRequest'),'native permission request');text(request.get('kind'),'permission kind')
            else:
                result=object_value(d.get('result'),'native permission result')
                if result.get('kind') not in ('approved','approved-for-session','approved-for-location','cancelled','denied-by-rules',
                    'denied-no-approval-rule-and-could-not-request-from-user','denied-interactively-by-user',
                    'denied-by-content-exclusion-policy','denied-by-permission-request-hook'):
                    raise DialectError('unsupported permission result')
        if agent is not None:text(agent,'native child');
        if event=='session.start':
            if d.get('sessionId')!=producer['thread_id'] or d.get('copilotVersion')!=producer['producer_version']:raise DialectError('SDK source header changed')
            return []
        if 'sessionId'in d and d['sessionId']!=producer['thread_id']:raise DialectError('SDK event session mismatch')
        scope={'native_agent_id':agent,'root_authority':False,'previous_event_id':p.get('parentId')}
        if event=='tool.execution_start':
            call=text(d.get('toolCallId'),'tool identity');tool=text(d.get('toolName'),'tool name')
            return [f('tool.call','observed',{'tool':tool,'arguments':d.get('arguments'),**scope,'permission_granted':False},call_id=call)]
        if event=='tool.execution_complete':
            call=text(d.get('toolCallId'),'tool identity');ok=boolean(d.get('success'),'success')
            if 'result'in d:object_value(d['result'],'tool result')
            if 'error'in d:object_value(d['error'],'tool error')
            return [f('tool.result','observed' if ok else 'failed',{'result':d.get('result'),'error':d.get('error'),'native_success_reported':ok,'outcome_pass':False,**scope},call_id=call)]
        if event=='assistant.usage':
            last={}
            for source,key in (('inputTokens','input_tokens'),('outputTokens','output_tokens'),('cacheReadTokens','cached_input_tokens'),('cacheWriteTokens','cache_write_tokens')):
                if source in d:last[key]=integer(d[source],source)
            if {'input_tokens','output_tokens'}<=last.keys():last['total_tokens']=last['input_tokens']+last['output_tokens']
            measurement=d.get('apiCallId')
            if measurement is not None:text(measurement,'API call ID')
            data=usage('copilot',producer,measurement,last,raw=d)
            if agent is not None:
                data['scope'].update({'kind':'native_child','agent_id':agent})
                if data['measurement_id'] is not None:data['measurement_id']=['copilot',producer['root_session_id'],producer['thread_id'],agent,measurement]
            return [f('usage.snapshot','observed',data)]
        if event=='abort':return [f('child.cancelled' if agent else 'lifecycle.cancelled','observed',{'native_status':'aborted','native_data':d,**scope})]
        if event=='user.message':return [f('message.user','observed',{'native_data':d,'grants_authority':False,'human_identity_proven':False,**scope})]
        if event.startswith('permission.'):return [f('permission.observation','observed',{'native_data':d,'grants_authority':False,'enforcement_proven':False,**scope})]
        if event=='session.error':return [f('lifecycle.error','observed',{'native_data':d,'portable_completion':False,**scope})]
        if event.startswith('session.compaction'):return [f('context.compaction','observed',{'native_event':event,'native_data':d,'recovery_proven':False})]
        return [f('child.lifecycle' if agent else 'lifecycle.stopped','observed',{'native_event':event,'native_data':d,'portable_completion':False,**scope})]
    key=lambda camel,pascal:p.get(pascal if g=='pascal' else camel)
    if event=='sessionStart':return []
    if event in ('preToolUse','postToolUse','postToolUseFailure'):
        tool=text(key('toolName','tool_name'),'tool name');args=key('toolArgs','tool_input')
        # Hook documentation does not supply a unique tool-call ID. Do not
        # manufacture one by matching names, arguments or adjacent timestamps.
        data={'tool':tool,'arguments':args,'call_pairing':'UNKNOWN','outcome_pass':False}
        if event=='preToolUse':return [f('tool.call','observed',{**data,'permission_granted':False})]
        if event=='postToolUseFailure':return [f('tool.result','failed',{**data,'error':text(p.get('error'),'error',1024*1024,empty=True)})]
        result=object_value(key('toolResult','tool_result'),'tool result')
        if result.get('result_type' if g=='pascal' else 'resultType')!='success':raise DialectError('unsupported successful hook result')
        text(result.get('text_result_for_llm' if g=='pascal' else 'textResultForLlm'),'tool text',1024*1024,empty=True)
        return [f('tool.result','observed',{**data,'result':result,'native_success_reported':True})]
    if event=='sessionEnd':
        if p.get('reason') not in ('complete','error','abort','timeout','user_exit'):raise DialectError('unsupported session end reason')
        return [f('lifecycle.cancelled' if p['reason'] in ('abort','user_exit') else 'lifecycle.session_end','observed',{'native_status':p['reason'],'portable_completion':False})]
    if event in ('agentStop','subagentStop'):
        boolean(p.get('stop_hook_active'),'repeat flag')
        reason=key('stopReason','stop_reason')
        if reason is not None and reason!='end_turn':raise DialectError('unsupported Stop reason')
        return [f('child.stopped' if event=='subagentStop' else 'lifecycle.stopped','observed',{'native_status':'end_turn','portable_completion':False})]
    if event=='userPromptSubmitted':return [f('message.user','observed',{'text':text(p.get('prompt'),'prompt',1024*1024,empty=True),'grants_authority':False,'human_identity_proven':False})]
    if event=='permissionRequest':return [f('permission.request','observed',{'native_request':p,'grants_authority':False,'enforcement_proven':False})]
    if event=='preCompact':return [f('context.compaction','observed',{'native_record':p,'recovery_proven':False})]
    if event=='subagentStart':return [f('child.started','observed',{'native_record':p,'root_authority':False,'child_custody':'UNKNOWN'})]
    if event in ('notification','errorOccurred'):return [f('native.notification','observed',{'native_record':p})]
    raise DialectError('unsupported Copilot grammar')

def is_ignored_projection(projected,producer):return False

def describe_contract():
    return {'client':'copilot','adapter_version':ADAPTER_VERSION,'supported_schemas':list(SUPPORTED_SCHEMAS),
        'native_acceptance':'UNKNOWN','authority_granted':False,'implemented':['native_identity','tool_worker','compaction','cancellation','usage','recovery'],
        'capabilities':{key:'YES' for key in ('skill_discovery','native_identity','tool_worker','tool_outcome','compaction','cancellation','usage','recovery')}|{'permission_enforcement':'FAIL_OPEN_PATHS','continuation':'SURFACE_SPECIFIC'},
        'limits':['Command preToolUse timeouts and HTTP errors/timeouts fail open; native registration is not protection',
            'Cloud permissions and lifecycle differ from CLI; no cloud qualification inherited',
            'Hook tool pairs lack call IDs; only SDK toolCallId permits pairing','SDK parentId is retained, but full linked-history coverage requires owner reconciliation',
            'Observed native usage is not billing or whole-tree cost','No action, permission, Stop continuation or scheduling output is emitted']}


def record_sequences(row, producer):
    p, capture, event, grammar = _row(row)
    check_producer(producer, "copilot", capture)
    result = {"capture": capture["sequence"]} if capture else {}
    return result
