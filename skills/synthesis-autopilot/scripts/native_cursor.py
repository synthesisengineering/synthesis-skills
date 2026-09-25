"""Cursor hook-v1 observations. Hook configuration is not permission evidence."""
from native_adapter_sdk import (DialectError,boolean,bounded,check_producer,digest,fact,
    integer,object_value,qualify,strict_json,text,unwrap)

ADAPTER_VERSION='cursor-hooks-v1'
SURFACES=('cursor-ide','cursor-cli','cursor-cloud')
SUPPORTED_SCHEMAS=('cursor.hooks.v1','synthesis.native_capture.v1')
EVENTS=frozenset(('sessionStart','sessionEnd','preToolUse','postToolUse','postToolUseFailure',
    'beforeSubmitPrompt','preCompact','stop','subagentStart','subagentStop','beforeShellExecution',
    'beforeMCPExecution','afterShellExecution','afterMCPExecution','afterFileEdit','afterAgentResponse','afterAgentThought'))

def _row(row):
    payload,capture=unwrap(row,'cursor',surfaces=SURFACES)
    event=text(payload.get('hook_event_name'),'hook event')
    if event not in EVENTS:raise DialectError('unsupported Cursor hook event')
    if capture and capture['event']!=event:raise DialectError('capture hook event mismatch')
    text(payload.get('conversation_id'),'conversation identity')
    text(payload.get('generation_id'),'generation identity')
    text(payload.get('cursor_version'),'Cursor version')
    roots=payload.get('workspace_roots')
    if not isinstance(roots,list) or not roots or len(roots)>64:raise DialectError('invalid Cursor workspace roots')
    for root in roots:text(root,'workspace root')
    return payload,capture,event

def qualify_source(header,*,expected_root_session_id,expected_thread_id=None,expected_parent_thread_id=None,expected_agent_id=None):
    p,c,e=_row(header)
    if e!='sessionStart':raise DialectError('Cursor source must begin with actual sessionStart')
    if p.get('session_id')!=p['conversation_id']:raise DialectError('Cursor native session identity mismatch')
    boolean(p.get('is_background_agent'),'background agent flag')
    if expected_parent_thread_id is not None or expected_agent_id is not None:raise DialectError('Cursor child source custody needs separate native qualification')
    return qualify('cursor',header,session=p['conversation_id'],version=p['cursor_version'],surface=c['surface'] if c else 'cursor-ide',
        schema='cursor.hooks.v1',expected_root_session_id=expected_root_session_id,expected_thread_id=expected_thread_id,capture=c)

def decode_record(row,producer,*,mode='synthetic',source_locator=None):
    p,c,event=_row(row);check_producer(producer,'cursor',c)
    if p['conversation_id']!=producer['thread_id'] or p['cursor_version']!=producer['producer_version']:raise DialectError('Cursor source identity/version mismatch')
    def f(kind,status,data,**kw):return fact(kind,status,data,row,mode=mode,source_locator=source_locator,
        call_scope={'schema':'cursor.generation','session_id':p['conversation_id'],'generation_id':p['generation_id']},**kw)
    if event=='sessionStart':
        if p.get('session_id')!=producer['thread_id']:raise DialectError('Cursor native session identity mismatch')
        boolean(p.get('is_background_agent'),'background agent flag')
        return []
    if event=='preToolUse':
        tool=text(p.get('tool_name'),'tool name');call=text(p.get('tool_use_id'),'tool identity');args=object_value(p.get('tool_input'),'tool input')
        return [f('tool.call','observed',{'tool':tool,'arguments':args,'permission_granted':False},call_id=call)]
    if event=='postToolUse':
        tool=text(p.get('tool_name'),'tool name');call=text(p.get('tool_use_id'),'tool identity');object_value(p.get('tool_input'),'tool input')
        result=strict_json(text(p.get('tool_output'),'tool output',1024*1024,empty=True).encode())
        if 'exitCode' in result and (type(result['exitCode']) is not int or not -(2**31)<=result['exitCode']<2**31):raise DialectError('invalid native exit code')
        return [f('tool.result','observed',{'tool':tool,'result':result,'native_success_reported':True,'outcome_pass':False},call_id=call)]
    if event=='postToolUseFailure':
        call=text(p.get('tool_use_id'),'tool identity');tool=text(p.get('tool_name'),'tool');object_value(p.get('tool_input'),'tool input')
        error=text(p.get('error_message'),'tool error',1024*1024,empty=True)
        if p.get('failure_type') not in ('error','timeout','permission_denied'):raise DialectError('unsupported failure type')
        interrupted=boolean(p.get('is_interrupt'),'interrupt flag')
        rows=[f('tool.result','failed',{'tool':tool,'error':error,'failure_type':p['failure_type'],'is_interrupt':interrupted,'outcome_pass':False},call_id=call)]
        if interrupted:rows.append(f('lifecycle.cancelled','observed',{'native_status':'interrupted','scope':'native_session'},subrecord=1))
        return rows
    if event=='stop':
        integer(p.get('loop_count'),'loop count')
        if p.get('status') not in ('completed','aborted','error'):raise DialectError('unsupported Stop status')
        return [f('lifecycle.cancelled' if p['status']=='aborted' else 'lifecycle.stopped','observed',
                  {'native_status':p['status'],'loop_count':p['loop_count'],'portable_completion':False})]
    if event=='beforeSubmitPrompt':
        return [f('message.user','observed',{'text':text(p.get('prompt'),'prompt',1024*1024,empty=True),'grants_authority':False,'human_identity_proven':False})]
    if event=='preCompact':return [f('context.compaction','observed',{'native_event':event,'recovery_proven':False})]
    if event=='subagentStart':
        if p.get('parent_conversation_id')!=producer['thread_id']:raise DialectError('subagent parent mismatch')
        return [f('child.started','observed',{'child_id':text(p.get('subagent_id'),'child identity'),'parent_id':p['parent_conversation_id'],
            'tool_call_id':text(p.get('tool_call_id'),'dispatch call'),'root_authority':False})]
    if event=='subagentStop':
        if p.get('status') not in ('completed','error','aborted'):raise DialectError('unsupported child status')
        return [f('child.stopped','observed',{'native_status':p['status'],'child_identity':'UNKNOWN','portable_completion':False})]
    if event in ('beforeShellExecution','beforeMCPExecution'):
        return [f('permission.request','observed',{'native_event':event,'native_request':p,'grants_authority':False,'enforcement_proven':False})]
    if event in ('afterShellExecution','afterMCPExecution'):
        return [f('tool.unpaired_result','observed',{'native_event':event,'native_result':p,'call_pairing':'UNKNOWN','outcome_pass':False})]
    if event=='afterFileEdit':return [f('artifact.changed','observed',{'native_event':event,'native_record':p,'current_artifact_bytes':'UNKNOWN'})]
    if event=='sessionEnd':
        if p.get('session_id')!=producer['thread_id']:raise DialectError('Cursor session end identity mismatch')
        if p.get('reason') not in ('completed','aborted','error','window_close','user_close'):raise DialectError('unsupported session end reason')
        boolean(p.get('is_background_agent'),'background agent flag');integer(p.get('duration_ms'),'session duration')
        text(p.get('final_status'),'final status')
        return [f('lifecycle.cancelled' if p['reason'] in ('aborted','window_close','user_close') else 'lifecycle.session_end','observed',{'native_event':event,'native_record':p,'portable_completion':False})]
    if event in ('afterAgentResponse','afterAgentThought'):
        # Fully typed ordinary narration carries no action or outcome truth.
        text(p.get('text'),'narration',1024*1024,empty=True)
        if 'duration_ms' in p:integer(p['duration_ms'],'thought duration')
        return []
    raise DialectError('unsupported Cursor grammar')

def is_ignored_projection(projected,producer):
    return False

def describe_contract():
    return {'client':'cursor','adapter_version':ADAPTER_VERSION,'supported_schemas':list(SUPPORTED_SCHEMAS),
        'events':sorted(EVENTS),'native_acceptance':'UNKNOWN','authority_granted':False,
        'implemented':['native_identity','tool_worker','compaction','cancellation','recovery'],
        'capabilities':{'skill_discovery':'YES','native_identity':'YES','permission_enforcement':'CONDITIONAL_FAIL_CLOSED_CONFIGURATION',
            'tool_worker':'YES','tool_outcome':'YES','compaction':'YES','cancellation':'YES','usage':'UNKNOWN','continuation':'SURFACE_SPECIFIC','recovery':'YES'},
        'limits':['Hook capture is passive and requires owner-admitted transport','Cursor failClosed must be configured and tested on the exact surface',
            'preToolUse ask is not enforced; no approval or allow output is emitted','No provider token accounting schema is claimed',
            'Cloud job survival and browser outcomes require separate native evidence','SubagentStop without native child ID cannot cancel the root']}


def record_sequences(row, producer):
    p, capture, event = _row(row)
    check_producer(producer, "cursor", capture)
    result = {"capture": capture["sequence"]} if capture else {}
    return result
