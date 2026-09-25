#!/usr/bin/env python3
"""Qualification kit for passive native observations, without action authority.

A capture envelope records transport claims; it cannot authenticate its author.
The canonical run journal and PM admission remain the owners of custody. This
kit reads exact current source bytes through native_observations. It never
installs clients, grants permissions, starts models, schedules work or records
an outcome PASS. CLI input/output is bounded strict JSON.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import importlib
import json
import math
from pathlib import Path
import sys

VERSION='native-adapter-sdk-v1'
MAX_BYTES=1024*1024
MAX_NODES=16384
CAPABILITIES=('skill_discovery','native_identity','permission_enforcement','tool_worker',
              'tool_outcome','compaction','cancellation','usage','continuation','recovery')
CAPTURE_FIELDS={'type','schema_version','client','surface','producer_version','capture_id',
                'sequence','session_id','event','payload'}

class DialectError(ValueError):
    pass

def _local_module(name):
    module=importlib.import_module(name)
    if Path(module.__file__).resolve().parent!=Path(__file__).resolve().parent:
        raise DialectError('adapter module belongs to another source tree')
    return module

def object_value(value,name='object'):
    if not isinstance(value,dict): raise DialectError(name+' must be an object')
    return value

def text(value,name='text',maximum=4096,empty=False):
    if not isinstance(value,str) or len(value)>maximum or (not empty and not value.strip()):
        raise DialectError('invalid '+name)
    try:value.encode('utf-8')
    except UnicodeError as exc:raise DialectError('invalid Unicode in '+name) from exc
    return value

def integer(value,name='integer'):
    if type(value) is not int or not 0<=value<=2**63-1:raise DialectError('invalid '+name)
    return value

def boolean(value,name='boolean'):
    if type(value) is not bool:raise DialectError('invalid '+name)
    return value

def bounded(value):
    budget=[0,0]
    def visit(v,depth):
        budget[0]+=1
        if depth>32 or budget[0]>MAX_NODES:raise DialectError('JSON structure bound exceeded')
        if isinstance(v,dict):
            if len(v)>1024:raise DialectError('object bound exceeded')
            for k,x in v.items():
                text(k,'key',512,empty=True);visit(k,depth+1);visit(x,depth+1)
        elif isinstance(v,list):
            if len(v)>1024:raise DialectError('array bound exceeded')
            for x in v:visit(x,depth+1)
        elif isinstance(v,str):
            text(v,'string',MAX_BYTES,empty=True);budget[1]+=len(v.encode())
            if budget[1]>MAX_BYTES:raise DialectError('combined JSON byte bound exceeded')
        elif isinstance(v,float) and not math.isfinite(v):raise DialectError('nonfinite JSON number')
        elif v is not None and not isinstance(v,(bool,int,float)):raise DialectError('non-JSON value')
    visit(value,0)
    return value

def strict_json(raw):
    if not isinstance(raw,bytes) or len(raw)>MAX_BYTES:raise DialectError('strict JSON byte bound exceeded')
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d:raise DialectError('duplicate JSON field')
            d[k]=v
        return d
    try:
        value=json.loads(raw.decode('utf-8'),object_pairs_hook=unique,
             parse_constant=lambda _: (_ for _ in ()).throw(DialectError('nonfinite JSON')))
        bounded(value)
        return object_value(value,'request')
    except (UnicodeError,RecursionError,ValueError) as exc:raise DialectError(str(exc)) from exc

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()).hexdigest()

def unwrap(row,client,*,surfaces):
    bounded(row);object_value(row,'record')
    if row.get('type')!='synthesis.native_capture':return row,None
    if set(row)!=CAPTURE_FIELDS or row['schema_version']!=1 or type(row['schema_version']) is not int or row['client']!=client:
        raise DialectError('invalid capture envelope')
    if row['surface'] not in surfaces:raise DialectError('capture surface mismatch')
    for key in ('producer_version','capture_id','session_id','event'):text(row[key],key)
    integer(row['sequence'],'capture sequence');object_value(row['payload'],'captured payload')
    return row['payload'],row

def capture_record(client,surface,event,payload,*,session_id,producer_version,capture_id,sequence):
    """Wrap exact transport payload; metadata stays an unauthenticated claim."""
    module=_local_module('native_'+text(client,'client',32)) if client in ('cursor','copilot','opencode') else None
    if module is None:raise DialectError('unsupported capture client')
    row={'type':'synthesis.native_capture','schema_version':1,'client':client,'surface':surface,
         'producer_version':producer_version,'capture_id':capture_id,'sequence':sequence,
         'session_id':session_id,'event':event,'payload':deepcopy(payload)}
    unwrap(row,client,surfaces=module.SURFACES)
    return row

def qualify(client,header,*,session,version,surface,schema,parent=None,agent=None,expected_root_session_id,
            expected_thread_id=None,expected_parent_thread_id=None,expected_agent_id=None,capture=None):
    thread=expected_thread_id if expected_thread_id is not None else expected_root_session_id
    text(session,'native session');text(expected_root_session_id,'expected root');text(thread,'expected thread')
    if session!=thread:raise DialectError('native session identity mismatch')
    if session==expected_root_session_id:
        if parent is not None or agent is not None:raise DialectError('root has child lineage')
    elif parent is None or parent==session or expected_parent_thread_id!=parent:
        raise DialectError('child requires exact native parent and admitted owner join')
    if expected_parent_thread_id is not None and parent!=expected_parent_thread_id:raise DialectError('native parent mismatch')
    if expected_agent_id is not None and agent!=expected_agent_id:raise DialectError('native agent mismatch')
    if capture is not None and (capture['session_id']!=session or (version is not None and capture['producer_version']!=version)):
        raise DialectError('capture session or producer version mismatch')
    return {'client':client,'surface':surface,'thread_id':thread,'root_session_id':expected_root_session_id,
            'parent_thread_id':parent,'agent_path':agent,'producer_version':version,'source_schema':schema,
            'capture_id':capture['capture_id'] if capture else None,'adapter_version':VERSION,
            'authentication':'owner_admission_required','root_authority':False}

def check_producer(producer,client,capture=None):
    object_value(producer,'producer')
    if producer.get('client')!=client:raise DialectError('producer client mismatch')
    for key in ('thread_id','root_session_id'):text(producer.get(key),key)
    if capture is not None:
        if (capture['session_id']!=producer['thread_id'] or capture['surface']!=producer['surface']
            or capture['capture_id']!=producer.get('capture_id') or capture['producer_version']!=producer['producer_version']):
            raise DialectError('capture identity, version or surface changed')
    elif producer.get('capture_id') is not None:raise DialectError('capture wrapper removed')

def fact(kind,status,data,row,*,mode,source_locator,call_id=None,call_scope=None,subrecord=0,record_id=None,sequence=None):
    if mode not in ('native','synthetic'):raise DialectError('invalid provenance claim mode')
    if call_id is not None:text(call_id,'call identity')
    if call_scope is not None:
        object_value(call_scope,'native call scope')
        for key,value in call_scope.items():
            text(key,'native scope key')
            if value is not None:text(value,'native scope value')
    capture_sequence=row.get('sequence') if row.get('type')=='synthesis.native_capture' else None
    if capture_sequence is not None:integer(capture_sequence,'capture sequence')
    if sequence is not None:integer(sequence,'native sequence')
    ordinal=capture_sequence if capture_sequence is not None else sequence
    original=row['payload'] if row.get('type')=='synthesis.native_capture' else row
    return {'kind':kind,'status':status,'data':deepcopy(data),'native':{
        'record_id':record_id or row.get('id'),'ordinal':ordinal,'sequence':sequence,
        'capture_sequence':capture_sequence,
        'subrecord':subrecord,'call_id':call_id,'call_scope':deepcopy(call_scope),'parent_call_id':None},
        'native_timestamp':original.get('timestamp',original.get('created')),'source_locator':deepcopy(source_locator),
        'mode':mode,'authentication':'owner_admission_required'}

def usage(client,producer,measurement,last,*,phase='final',aggregation='per_response',raw=None):
    object_value(last,'usage counters')
    for key,value in last.items():integer(value,key)
    countable=phase=='final' and aggregation=='per_response' and measurement is not None and {'input_tokens','output_tokens','total_tokens'}<=last.keys()
    if countable and last['input_tokens']+last['output_tokens']!=last['total_tokens']:raise DialectError('usage total contradiction')
    return {'grammar':client+'.native_usage','scope':{'kind':'native_thread',**{k:producer.get(k) for k in ('thread_id','root_session_id','parent_thread_id')}},
            'units':'tokens','phase':phase,'aggregation':aggregation,'measurement_id':[client,producer['thread_id'],measurement] if measurement else None,
            'countable':countable,'last':last if aggregation=='per_response' else None,'totals':last if aggregation!='per_response' else None,
            'counters_digest':digest(last) if measurement else None,'raw_usage':deepcopy(raw),'scope_nonoverlap':'UNKNOWN','billing_cost':None,
            'missingness':([] if countable else ['incomplete_or_nonfinal_response_measurement'])+['full_execution_tree_not_proven','billing_not_established']}

def inspect_source(path,*,client,session_id,mode='synthetic',max_pages=16,page_bytes=1024*1024):
    """Bounded actual-reader qualification; cursors stay in the existing owner."""
    native=_local_module('native_observations')
    if type(max_pages) is not int or not 1<=max_pages<=16:raise DialectError('invalid page count')
    binding,cursor=native.enroll_source(path,client=client,expected_root_session_id=session_id,mode=mode)
    limits=native.Limits(page_bytes=page_bytes);pages=[];projection=native.empty_projection();events=[]
    for _ in range(max_pages):
        batch=native.read_page(binding,cursor,limits=limits);pages.append(batch);cursor=batch['cursor']
        projection=native.reduce_observations(projection,batch)
        events.extend(batch['events'])
        if len(events)>512:raise DialectError('qualification positive event bound reached; use admitted journal paging')
        if batch['gaps'] or batch['diagnostics'] or batch['coverage']['backlog_bytes']==0:break
    # The decoder's normal event cap also bounds positive revalidation memory.
    if len(events)>512:raise DialectError('qualification positive event bound reached; use admitted journal paging')
    current=native.revalidate_observations(binding,events)
    gaps=[g for p in pages for g in p['gaps']]
    incomplete=bool(gaps or any(p['diagnostics'] for p in pages) or pages[-1]['coverage']['backlog_bytes'] or pages[-1]['coverage']['pending_bytes'])
    return {'schema_version':1,'surface':binding['producer']['surface'],'client':client,'binding':binding,
            'source_status':'CURRENT' if current['status']=='current' and not incomplete else 'UNKNOWN',
            'events':events,'projection':projection,'coverage':[p['coverage'] for p in pages],'gaps':gaps,'diagnostics':[d for p in pages for d in p['diagnostics']],
            'revalidation':current,'native_provenance':'UNKNOWN','mode':mode,'authority_granted':False,
            'qualification_limit':'Current source observations require admitted producer/transport and outcome qualification; mode is a claim.'}

def assess(surface,*,required=(),source_report=None):
    """A capability vector with explicit unmet native qualification conditions.

    No JSON flag, source header or fixture result can promote the native or
    outcome cells. Their authority remains with native admission and actual
    independently verified consumer outcomes, not this source inspection.
    """
    capabilities=_local_module('capabilities')
    registry=capabilities.supported_surfaces()['surfaces']
    text(surface,'surface',128)
    if surface not in registry or 'observation_contract' not in registry[surface]:raise DialectError('surface has no additional adapter contract')
    if not isinstance(required,(tuple,list)) or any(not isinstance(x,str) for x in required) or len(required)>len(CAPABILITIES) or len(set(required))!=len(required) or set(required)-set(CAPABILITIES):raise DialectError('invalid required capability set')
    client=registry[surface]['dialect'];module=_local_module('native_'+client);contract=module.describe_contract()
    if source_report is not None:
        object_value(source_report,'source report')
        if source_report.get('surface')!=surface or source_report.get('client')!=client:raise DialectError('source report scope mismatch')
    cells={}
    for name in CAPABILITIES:
        cells[name]={'documented':contract['capabilities'].get(name,'UNKNOWN'),
                     'implemented':'YES' if name in contract['implemented'] else 'NO',
                     'installed':'UNKNOWN','native':'UNKNOWN','outcome':'UNKNOWN'}
    if client=='copilot':
        cells['permission_enforcement'].update({'documented':'FAIL_OPEN_PATHS','reason':'Command hook timeouts and HTTP hook failures can fail open; no protection claim from registration.'})
    missing=[name for name in required if cells[name]['native']!='PASS' or cells[name]['outcome']!='PASS']
    return {'schema_version':1,'surface':surface,'client':client,'capabilities':cells,'required':list(required),
            'missing':missing,'qualified':False,'authority_granted':False,'contract':contract,
            'actions':[{'capability':name,'condition':'Admitted exact surface/build/account/permissions and current native positive/negative consumer evidence; independently verify outcome.',
                        'human_boundary':name in ('native_identity','permission_enforcement','tool_worker','tool_outcome')} for name in missing],
            'source_observed':source_report is not None,'source_observation_authentication':'owner_admission_required'}

def main():
    try:
        request=strict_json(sys.stdin.buffer.read(MAX_BYTES+1))
        op=request.get('operation')
        if op=='describe' and set(request)=={'operation','surface'}:result=assess(request['surface'])
        elif op=='inspect' and set(request)=={'operation','path','client','session_id','mode'}:
            result=inspect_source(request['path'],client=request['client'],session_id=request['session_id'],mode=request['mode'])
        else:raise DialectError('unsupported operation or fields')
        encoded=json.dumps(result,sort_keys=True,allow_nan=False)
        if len(encoded.encode())>4*MAX_BYTES:raise DialectError('qualification output bound exceeded; use admitted paginated reader')
        print(encoded);return 0
    except (ValueError,OSError,TypeError,KeyError) as exc:
        print(json.dumps({'status':'UNRESOLVED','reason':str(exc)[:2048],'authority_granted':False}));return 2

if __name__=='__main__':raise SystemExit(main())
