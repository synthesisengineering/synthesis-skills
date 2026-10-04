"""PM/context recovery projection over the existing authoritative run journal.

Capsules are embedded in existing checkpoint events. They reference retained
state and local evidence; they are neither another authority store nor a grant
to restart a worker, replay an effect, transfer ownership or enable a service.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import run_state
from run_admission import read_admission_observation, safe_path

MAX_CAPSULE_BYTES = 256 * 1024
POINTER = '/state/extensions/controller/checkpoint/recovery_capsule'


def resolve(project, project_id, actor, runtime_root=None):
    """Use the full PM causal resolver before reading a recovery journal."""
    import autopilot
    import project_state
    if not isinstance(actor, dict) or set(actor) != {'board','native_payload'}:
        raise ValueError('recovery resolver requires the existing native actor')
    project = Path(project).absolute()
    runtime = Path(runtime_root or autopilot.default_runtime_root()).expanduser().absolute()
    report = project_state.resolve_project(project_id, project.parent / 'index.yaml',
        repo_guard_root=runtime.parent / 'repo-guard',
        checkpoint_receipt_root=runtime.parent / 'project-checkpoints',
        coordination_board=Path(actor['board']), fetch=False, refresh_coordination=False)
    if report.status not in {'PASS','LOCAL_RECOVERABLE'} or not report.selected_path or Path(report.selected_path) != project.resolve():
        raise ValueError('recovery resolver cannot select this current project: ' + report.status + '; ' + '; '.join(report.issues))
    return {'status': report.status, 'selected_path': report.selected_path,
        'selected_head': report.selected_head, 'selected_tree': report.selected_tree,
        'scope': 'Local causal project resolution; no fetch or mutation', 'authority_granted': False}


def _event_ref(project, state, revision):
    return str((run_state._home(project, state['run_id']) / 'events' / f'{revision:012d}.json').relative_to(Path(project)))


def _journal(context):
    """Verify full history; retain revision metadata and only the final pair.

    Every event contains a full state. A capsule needs contract/profile history
    and its exact parent proof, not a second in-memory copy of the whole journal.
    """
    histories = {'contract': [], 'profile': []}
    identities = {'contract': None, 'profile': None}
    history = run_state._verified_history(Path(context['project']), context['state']['run_id'])
    if history is None:
        events = run_state._events(Path(context['project']), context['state']['run_id'])
        def rows():
            for event in events:
                yield run_state._history_metadata(event), event['state']
    else:
        def rows():
            for row in history['rows']:
                yield row, history['last']['state'] if row is history['rows'][-1] else None
    prior = head = head_state = None
    for event, value in rows():
        prior, head, head_state = head, event, value
        for field in histories:
            identity = (event[field + '_revision'], event[field + '_digest'])
            if identity != identities[field]:
                histories[field].append({'revision': identity[0], 'sha256': identity[1],
                    'journal_revision': event['revision'], 'event_digest': event['digest']})
                identities[field] = identity
    if head is None or head_state != context['state']:
        raise ValueError('recovery capsule requires the exact current verified journal head')
    def metadata(event):
        return None if event is None else {key: event[key] for key in ('revision','digest','command','state_digest')}
    return {'head': metadata(head), 'parent': metadata(prior), 'histories': histories}


def _partial_output_refs(state, project):
    """Registered intermediate bytes stay discoverable before a final return.

    Undeclared/unregistered files and unsaved reasoning are never invented as
    recovered artifacts. Their declared output roots remain in the child brief.
    """
    result = {}
    for identity, child in state.get('extensions', {}).get('workflow', {}).get('children', {}).items():
        roots = [Path(value) for value in child.get('file_contract', {}).get('output_roots', [])]
        result[identity] = sorted({key for key, artifact in state['artifacts'].items()
            if artifact.get('role') == 'output' and any((Path(project) / artifact['path']).is_relative_to(root) for root in roots)}
            | set(child.get('artifact_ids', [])))
    return result


def capture(context):
    """Compile references while the checkpoint's real PM admission is active."""
    proof = read_admission_observation(context)
    state, project = context['state'], Path(context['project'])
    journal = _journal(context)
    head = journal['head']
    extensions = state.get('extensions', {})
    flow = extensions.get('workflow', {})
    native = extensions.get('native_observations', {}).get('sources', {})
    report = run_state.criterion_report(state, context)
    artifacts = {identity: {**deepcopy(record),
        'current_at_capture': identity in context['artifacts']}
        for identity, record in state['artifacts'].items()}
    parent_ref = _event_ref(project, state, state['revision'])
    # Extension references retain all owners, including future decision/resource
    # schemas, without copying recursive earlier capsules or reinterpreting them.
    refs = {key: {'event_ref': parent_ref, 'pointer': '/state/extensions/' + key.replace('~','~0').replace('/','~1'),
                  'sha256': run_state._digest(value)} for key, value in extensions.items()}
    from native_archive import verify_archives
    archive_coverage = verify_archives(project,state)
    import project_state
    from record_succession import material_projection
    material = material_projection(project_state.material_context(project))
    result = {'material_context': material, 'schema_version': 1, 'kind': 'recovery-capsule', 'authority_granted': False,
        'native_archive_coverage': archive_coverage,
        'project_id': state['project_id'], 'run_id': state['run_id'],
        'basis': {'revision': state['revision'], 'event_digest': head['digest'],
            'state_digest': run_state._digest(state), 'plan_digest': context['plan_digest'],
            'contract_digest': state['contract_digest'], 'profile_digest': state['profile_digest']},
        'obligations': {'contract': deepcopy(state['contract']), 'profile': deepcopy(state['profile']),
            'contract_revisions': journal['histories']['contract'], 'profile_revisions': journal['histories']['profile'],
            'authority_refs': deepcopy(state['contract']['authority_refs']),
            'criteria': report, 'waits': deepcopy(state['waits']), 'effects': deepcopy(state['effects']),
            'graph': deepcopy(flow.get('graph')), 'children': deepcopy(flow.get('children', {})),
            'partial_output_refs': _partial_output_refs(state, project),
            'resources': {'owner_ref': refs.get('workflow'),
                          'recorded_budget_ref': {'event_ref': parent_ref, 'pointer': '/state/extensions/workflow/budget',
                                                  'sha256': run_state._digest(flow.get('budget'))},
                          'interpretation': 'Recorded measured, forecast and unknown values retain their owner semantics'}},
        'artifacts': artifacts, 'extension_refs': refs,
        'local': {'project_root': str(project), 'owner': {key: proof[key] for key in
            ('session_uuid','native_ref','project_id','project_root','repository','branch','claim_hash')},
            'plan': state['plan'], 'native_handles': {key: {field: deepcopy(value.get(field)) for field in
                ('binding','cursor','enrollment','recovery','qualification')} for key, value in native.items()}},
        'retention': {'scope': 'References in the same governed project; no automatic export',
            'journal': parent_ref, 'projection_rebuildable': True,
            'unsaved_reasoning': 'UNRECOVERABLE unless already durably retained'},
        'survival': {'state_retained': 'JOURNAL_REFERENCES', 'manual_recovery': 'REQUIRES_CURRENT_ADMISSION',
            'next_turn_automatic': 'UNKNOWN', 'process_loss': 'UNKNOWN', 'app_exit': 'UNKNOWN',
            'logout': 'UNKNOWN', 'reboot': 'UNKNOWN', 'network_outage': 'UNKNOWN',
            'machine_off': 'UNKNOWN', 'machine_transfer': 'UNKNOWN'}}
    if len(run_state._json(result)) > MAX_CAPSULE_BYTES:
        raise ValueError('recovery capsule exceeds bounded reference projection; retain the complete journal')
    return result


def reference(state, project):
    capsule = state.get('extensions', {}).get('controller', {}).get('checkpoint', {}).get('recovery_capsule')
    if capsule is None:
        return None
    revision = capsule['basis']['revision'] + 1
    return {'event_ref': _event_ref(Path(project), state, revision), 'pointer': POINTER,
        'sha256': run_state._digest(capsule), 'journal_revision': revision,
        'authority_granted': False, 'current_head': state['revision'] == revision}


def _validate_resource_reference(project, state, capsule):
    resources = capsule.get('obligations', {}).get('resources', {})
    embedded = {'owner_ref', 'recorded_budget', 'interpretation'}
    referenced = {'owner_ref', 'recorded_budget_ref', 'interpretation'}
    if not isinstance(resources, dict) or set(resources) not in (embedded, referenced):
        raise ValueError('capsule requires exactly one complete resource representation')
    basis = capsule['basis']['revision']
    expected_path = _event_ref(project, state, basis)
    if set(resources) == referenced:
        ref = resources['recorded_budget_ref']
        if (not isinstance(ref, dict) or set(ref) != {'event_ref', 'pointer', 'sha256'}
                or ref['event_ref'] != expected_path or ref['pointer'] != '/state/extensions/workflow/budget'):
            raise ValueError('capsule budget reference differs from its authenticated parent')
    parent = run_state._read(safe_path(project / expected_path, project))
    if (parent.get('digest') != capsule['basis']['event_digest']
            or run_state._digest(parent['state']) != capsule['basis']['state_digest']):
        raise ValueError('capsule resource parent differs from its authenticated basis')
    flow = parent['state'].get('extensions', {}).get('workflow')
    expected_owner = None if flow is None else {'event_ref': expected_path, 'pointer': '/state/extensions/workflow', 'sha256': run_state._digest(flow)}
    budget = (flow or {}).get('budget')
    if (resources.get('owner_ref') != expected_owner
            or set(resources) == referenced and ref['sha256'] != run_state._digest(budget)
            or set(resources) == embedded and resources['recorded_budget'] != budget):
        raise ValueError('capsule resource reference failed owner/digest validation')


def _selected_capsule(context, ref):
    project, state = Path(context['project']), context['state']
    if not isinstance(ref, str) or not ref or len(ref) > 4096:
        raise ValueError('recovery capsule reference must name its existing journal event')
    target = Path(ref)
    target = safe_path(target if target.is_absolute() else project / target, project)
    journal = _journal(context)
    selected = journal['head']
    if target != project / _event_ref(project, state, selected['revision']) or selected.get('command') != 'controller.checkpoint':
        raise ValueError('recovery capsule must be the selected run\'s authentic checkpoint event; copied JSON grants no authority')
    if selected['revision'] != state['revision']:
        raise ValueError('recovery capsule is stale relative to the current journal head')
    capsule = state.get('extensions', {}).get('controller', {}).get('checkpoint', {}).get('recovery_capsule')
    if not isinstance(capsule, dict) or capsule.get('schema_version') != 1 or capsule.get('kind') != 'recovery-capsule' or capsule.get('authority_granted') is not False:
        raise ValueError('selected checkpoint lacks an owned recovery capsule')
    index = capsule.get('basis', {}).get('revision')
    if type(index) is not int or index < 1 or index + 1 != selected['revision']:
        raise ValueError('recovery capsule journal basis is invalid')
    parent = journal['parent']
    if (parent is None or parent['revision'] != index or capsule.get('project_id') != state['project_id'] or capsule.get('run_id') != state['run_id']
            or capsule['basis']['event_digest'] != parent['digest']
            or capsule['basis']['state_digest'] != parent['state_digest']):
        raise ValueError('recovery capsule basis does not match its retained authoritative parent')
    for key in ('contract_digest','profile_digest'):
        if capsule['basis'][key] != state[key]:
            raise ValueError('recovery capsule contract/profile changed')
    if capsule['basis']['plan_digest'] != context['plan_digest']:
        raise ValueError('recovery capsule controlling instructions changed')
    if any(identity not in context['artifacts'] or context['artifacts'][identity]['digest'] != row['digest']
           for identity, row in capsule['artifacts'].items()):
        raise ValueError('recovery capsule artifact/input identities changed or are unavailable')
    _validate_resource_reference(project, state, capsule)
    return capsule


def _report(context):
    """Fresh reconciliation diagnostics; no provider action or inferred death."""
    from observation_bridge import current_invalidation
    state = context['state']
    pending = []
    from native_archive import verify_archives
    archive_coverage = verify_archives(context['project'],state)
    for issue in archive_coverage['issues']:
        pending.append({'owner':'native archive owner','kind':'artifact_reconciliation',
            'archive_id':issue['archive_id'],'reason':issue['reason']})
    for identity in sorted(set(state['artifacts']) - set(context['artifacts'])):
        pending.append({'owner': 'artifact owner', 'kind': 'artifact_reconciliation', 'artifact_id': identity})
    for identity, item in state['effects'].items():
        if item['status'] in {'prepared','unknown','retryable'}:
            pending.append({'owner': 'action owner', 'kind': 'effect_reconciliation', 'effect_id': identity,
                'status': item['status'], 'instruction': 'Read current target through its owner; do not repeat or infer outcome'})
    for identity, intent in state.get('native_execution', {}).items():
        if intent.get('status') == 'pending':
            pending.append({'owner': 'run_state', 'kind': 'native_intent_reconciliation',
                'intent_id': identity, 'child_id': intent['child_id'], 'phase': intent.get('phase', 'unbound historical custody'),
                'instruction': 'Use controller recover to inspect the original observer lease and source-verified retained receipt; do not relaunch. Missing custody remains an unresolved effect, including after incomplete close.'})
    for identity, child in state.get('extensions', {}).get('workflow', {}).get('children', {}).items():
        if child.get('disposition') == 'running':
            pending.append({'owner': 'workflow', 'kind': 'child_reconciliation', 'child_id': identity,
                'artifact_ids': _partial_output_refs(state, context['project'])[identity],
                'instruction': 'Retain partial outputs and establish actual worker state before reassignment'})
    old = state.get('extensions', {}).get('controller', {}).get('checkpoint', {}).get('recovery_capsule')
    if old and old['basis']['plan_digest'] != context['plan_digest']:
        pending.append({'owner': 'contract owner', 'kind': 'instruction_reconciliation',
            'basis_contract_digest': old['basis']['contract_digest'],
            'basis_plan_digest': old['basis']['plan_digest'],
            'observed_plan_digest': context['plan_digest'],
            'instruction': 'Controlling instructions changed; bind the intended contract before work resumes'})
    prior = state.get('extensions', {}).get('recovery', {}).get('report', {})
    # A diagnostic checkpoint is not an authorization to adopt new instructions.
    # Keep that unknown across checkpoints and unrelated contract amendments.
    # A current admitted owner must explicitly reconcile the exact instructions;
    # that operation cannot expand the contract's action authority.
    for issue in prior.get('pending', []):
        if (issue['kind'] == 'instruction_reconciliation'
                and issue['basis_plan_digest'] != context['plan_digest']
                and not any(row['kind'] == 'instruction_reconciliation' for row in pending)):
            pending.append(deepcopy(issue))
    native = current_invalidation(context)
    ack = state.get('extensions', {}).get('recovery', {}).get('instruction_ack')
    if ack and ack['binding'] == _instruction_binding(context) and native['status'] == 'clear':
        pending = [row for row in pending if row['kind'] != 'instruction_reconciliation']
    if native['status'] != 'clear':
        pending.append({'owner': 'observation_bridge', 'kind': 'native_reconciliation', 'status': native['status']})
    import project_state
    from record_succession import material_projection, material_needs_reconciliation
    material = material_projection(project_state.material_context(context['project']))
    if material_needs_reconciliation(material):
        pending.append({'owner': 'context_edit', 'kind': 'material_reconciliation', 'reason': 'Current declared material is pending, changed or unreachable; no authority fence is cleared'})
    return {'material_context': material, 'status': 'reconcile' if pending else 'clear', 'pending': pending,
        'native': native, 'criteria': run_state.criterion_report(state, context),
        'authority_granted': False, 'fence': {key: context['binding'][key] for key in
            ('session_uuid','native_ref','claim_hash','repository','branch')},
        'journal_revision': state['revision'], 'scope': 'Current project-local recovery admission; no continuation or survival qualification'}


def prepare(context, payload):
    if not isinstance(payload, dict) or set(payload) != {'capsule_ref'} or (payload['capsule_ref'] is not None and not isinstance(payload['capsule_ref'], str)):
        raise ValueError('recovery admission accepts only an optional journal capsule reference')
    read_admission_observation(context)
    _journal(context)
    retained = context['state'].get('extensions', {}).get('controller', {}).get('checkpoint', {}).get('recovery_capsule')
    if retained is not None:
        _validate_resource_reference(Path(context['project']), context['state'], retained)
    if payload['capsule_ref'] is not None:
        _selected_capsule(context, payload['capsule_ref'])
    return {'capsule_ref': payload['capsule_ref'], 'report': _report(context)}


def record(state, prepared, context):
    result = deepcopy(state)
    previous = result.setdefault('extensions', {}).get('recovery', {})
    result['extensions']['recovery'] = {'schema_version': 1, 'epoch': previous.get('epoch', 0) + 1,
        'basis_revision': state['revision'], 'admitted_revision': state['revision'] + 1,
        **deepcopy(prepared)}
    if 'instruction_ack' in previous:
        result['extensions']['recovery']['instruction_ack'] = deepcopy(previous['instruction_ack'])
    return result


def _instruction_binding(context):
    return {**{key:context['binding'][key] for key in ('session_uuid','native_ref','claim_hash','repository','branch')},
        'plan_digest':context['plan_digest'],'contract_digest':context['state']['contract_digest'],
        'profile_digest':context['state']['profile_digest']}


def prepare_instruction_ack(context,payload):
    if not isinstance(payload,dict) or set(payload)!={'plan_digest','contract_digest','reason'}:
        raise ValueError('instruction reconciliation needs exact current plan, contract and reason')
    if not isinstance(payload['reason'],str) or not 1<=len(payload['reason'].strip())<=4096:
        raise ValueError('instruction reconciliation needs a bounded explanation')
    read_admission_observation(context)
    _journal(context)
    if 'report' not in context['state'].get('extensions',{}).get('recovery',{}):
        raise ValueError('reconcile the current recovery report before acknowledging instructions')
    if payload['plan_digest']!=context['plan_digest'] or payload['contract_digest']!=context['state']['contract_digest']:
        raise ValueError('instruction reconciliation cannot adopt stale instructions or another contract')
    from observation_bridge import current_invalidation
    if current_invalidation(context)['status']!='clear':
        raise ValueError('instruction reconciliation cannot override native cancellation or unavailable current source')
    return {'binding':_instruction_binding(context),'reason':payload['reason'],
        'journal_revision':context['state']['revision']+1,'authority_granted':False,
        'scope':'Current owner read and reconciled instructions within the existing contract; no new approval'}


def record_instruction_ack(state,prepared,context):
    result=deepcopy(state)
    result.setdefault('extensions',{}).setdefault('recovery',{})['instruction_ack']=deepcopy(prepared)
    return result


def validate_command(state, command, payload, context):
    recovery = state.get('extensions', {}).get('recovery')
    if recovery is None:
        return
    work = (command == 'workflow.dispatch' or command == 'effect.prepare'
            or command == 'workflow.task' and payload.get('action') in {'start','retry','complete'}
            or command == 'close' and payload.get('status') == 'completed')
    if work:
        if recovery['report']['status'] != 'clear':
            raise ValueError('recovery reconciliation remains pending; retain effects and children before work admission')
        # An admitted recovery is a journal fact, not a lease on external truth.
        # Recheck native cancellation, instruction, artifact and material currentness at
        # the actual command boundary. Newly admitted effects/children remain
        # with their own workflow owners and do not reopen a completed recovery.
        external = {'native_reconciliation','instruction_reconciliation','artifact_reconciliation','material_reconciliation'}
        observed = {**context, 'state': state, 'project': Path(context['binding']['project_root'])}
        if any(row['kind'] in external for row in _report(observed)['pending']):
            raise ValueError('recovery external currentness changed; reconcile before work admission')


def register(engine):
    engine.register_command('recovery.admit', record)
    engine.register_preparer('recovery.admit', prepare)
    engine.register_constraint('recovery.reconciliation', validate_command)
    engine.register_command('recovery.instructions',record_instruction_ack)
    engine.register_preparer('recovery.instructions',prepare_instruction_ack)
