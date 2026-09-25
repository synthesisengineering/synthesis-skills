"""Derive fixed profile obligations from current evidence owners.

This module never writes state, grants authority, rates thought from prose, or
turns a file's existence into an outcome. The engine persists observations and
rederives them through its evidence bridge; custom obligations name criteria.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from workflow import CORE_CHECKS, DOMAINS

PERSONAL_IDS = frozenset({'end-to-end', 'framework-decisions', 'plan-current',
    'project-files-current', 'verify-before-done', 'lessons-filed', 'blog-seeds', 'completion-report'})
DOMAIN_IDS = {domain + '.' + check: domain for domain, check in DOMAINS.items()}
CANONICAL_IDS = PERSONAL_IDS | frozenset(CORE_CHECKS) | frozenset(DOMAIN_IDS) | frozenset({
    'evidence.independent', 'effect.reconciliation', 'continuation.survival', 'optional.exploration'})
CONDITIONAL_IDS = frozenset({'framework-decisions', 'lessons-filed', 'optional.exploration'})
VERDICTS = frozenset({'SATISFIED', 'NOT_APPLICABLE', 'UNRESOLVED'})


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _bindings(state):
    return {key: state[key] for key in ('run_id', 'contract_digest', 'profile_digest')}


def _criteria_for_items(state):
    result = {}
    for criterion in state['contract']['criteria']:
        for identity in criterion.get('profile_item_ids', []):
            result.setdefault(identity, set()).add(criterion['id'])
    return result


def _selected(item):
    """An explicit enable/always override selects the optional obligation."""
    selected = False
    for row in item.get('history', []):
        if row.get('source') == 'shipped':
            continue
        if 'enabled' in row.get('fields', []):
            selected = row.get('enabled') is True
        if 'applicability' in row.get('fields', []):
            selected = row.get('applicability', item.get('applicability')) == 'always'
    return selected


def _current_hashes(context, identities):
    from evidence_bridge import _current_artifacts
    return _current_artifacts(context, identities)


def checkpoint_basis(context):
    """Stable task/recovery facts; observer input specs are journal bookkeeping."""
    from execution_checkpoint import _inventory
    state, project = context['state'], Path(context['project'])
    flow = state.get('extensions', {}).get('workflow', {})
    identities = {key for key, row in state['artifacts'].items() if not row.get('managed_input')}
    present = identities & set(context['artifacts'])
    files, _inputs, _events = _inventory(context)
    records = {name: files[name] for name in ('CONTEXT.md', 'CURRENT_STATE.json') if name in files}
    # A normal post-terminal PM build can explicitly succeed the execution
    # proof. The original source observation remains reproducible only after
    # that current whole-project owner proves the exact successor.
    checkpoint = state.get('extensions', {}).get('controller', {}).get('checkpoint', {})
    pm = checkpoint.get('pm')
    if state['status'] == 'completed' and isinstance(pm, dict):
        from execution_checkpoint import current_proof
        if current_proof(context, pm)['scope'] == 'TERMINAL_CLEAN_CHECKPOINT_SUCCESSOR':
            records = {name: pm['project_files'][name] for name in records}
            files.update(records)
    return {'schema_version': 1, 'bindings': _bindings(state), 'plan_digest': context['plan_digest'],
        'artifact_digests': _current_hashes(context, present), 'missing_artifacts': sorted(identities - present),
        'project_records': records, 'project_files': files,
        'waits': deepcopy(state['waits']), 'effects': deepcopy(state['effects']),
        'graph': deepcopy(flow.get('graph', {})), 'children': deepcopy(flow.get('children', {})),
        'quality': deepcopy(flow.get('quality', {})),
        'profile_obligations': deepcopy(state.get('extensions', {}).get('controller', {}).get('profile_obligations', {}))}


def _quality(context, statuses):
    """Re-run the existing domain grade owner on its current receipt bytes."""
    from workflow import grade
    state = context['state']
    flow = state.get('extensions', {}).get('workflow', {})
    accepted = {}
    for identity, previous in flow.get('quality', {}).items():
        if statuses.get(identity) != 'PASS' or previous.get('verdict') != 'PASS':
            continue
        try:
            candidate = deepcopy(state)
            candidate['extensions']['workflow']['quality'].pop(identity)
            refreshed = grade(candidate, {'criterion_id': identity, 'receipt_ids': previous['receipt_ids'],
                'independent': previous['independent']}, {**context, 'quality_readonly': True})['extensions']['workflow']['quality'][identity]
            if refreshed['verdict'] != 'PASS' or refreshed['receipt_bindings'] != previous['receipt_bindings']:
                continue
            accepted[identity] = {reference: context['evidence'][reference]
                                  for reference in previous['receipt_ids']}
        except (ValueError, KeyError, TypeError, OSError):
            continue
    return accepted


def _semantic(identities, statuses, quality):
    """Substantive reasoning uses the calibrated semantic owner, not artifacts."""
    return bool(identities) and all(statuses.get(identity) == 'PASS' and any(
        record['data'].get('domain') in {'research', 'writing'} and record['data'].get('calibrated') is True
        and isinstance(record['data'].get('domain_review'), dict)
        for record in quality.get(identity, {}).values()) for identity in identities)


def _captured(identities, statuses, quality):
    # A verified knowledge recovery/readback can prove capture of accepted bytes;
    # semantic writing/research proof can additionally assess their meaning.
    return bool(identities) and all(statuses.get(identity) == 'PASS' and any(
        record['data'].get('domain') == 'knowledge' or
        (record['data'].get('domain') in {'research', 'writing'} and record['data'].get('calibrated') is True
         and isinstance(record['data'].get('domain_review'), dict))
        for record in quality.get(identity, {}).values()) for identity in identities)


def _trigger_accepted(trigger, statuses, quality):
    refs = set(trigger.get('criterion_ids', []))
    accepted = _semantic(refs, statuses, quality) if trigger['kind'] == 'decision' else _captured(refs, statuses, quality)
    if not accepted:
        return False
    reviewed = set()
    for identity in refs:
        for record in quality.get(identity, {}).values():
            data = record['data']
            reviewed.add(data.get('artifact_id'))
            reviewed.update(data.get('artifact_digests', {}))
            reviewed.update(data.get('domain_review', {}).get('input_digests', {}))
    return set(trigger['artifact_digests']) <= reviewed


def _decision_triggers(state, dimensions):
    flow = state.get('extensions', {}).get('workflow', {})
    reasons = []
    if dimensions.get('uncertainty') == 'high':
        reasons.append('declared material uncertainty')
    if 'research' in dimensions.get('domains', []):
        reasons.append('research or recommendation domain')
    if state.get('contract_revision', 1) > 1:
        reasons.append('accepted contract amendment')
    for identity, attempts in flow.get('progress', {}).items():
        strategies = {row.get('strategy_id', row.get('input_digest')) for row in attempts}
        strategies.discard(None)
        if len(strategies) > 1:
            reasons.append('changed strategy for ' + identity)
        if any(row.get('outcome') in {'permanent_failure', 'ambiguous_effect'} for row in attempts):
            reasons.append('material unresolved approach for ' + identity)
    persistence = state.get('extensions', {}).get('workflow_persistence', {})
    strategies = {}
    for attempt in persistence.get('attempts', []):
        identity = attempt['obligation_id']
        strategies.setdefault(identity, set()).add(attempt['strategy_key'])
        if attempt.get('family') in {'permanent_tool', 'ambiguous_effect', 'review_disagreement'}:
            reasons.append('recorded material condition for ' + identity)
    for identity, variants in strategies.items():
        if len(variants) > 1:
            reasons.append('owner-observed changed strategy for ' + identity)
    return sorted(set(reasons))


def _pm_current(context, checkpoint, basis):
    """Use the adopted PM owner when present; do not invent adoption or a PASS."""
    if 'CONTEXT.md' not in basis['project_records']:
        return False, 'Current project context is missing.'
    import project_state
    try:
        applicability, _issues = project_state.checkpoint_applicability(Path(context['project']))
    except (project_state.ProjectStateError, ValueError, OSError) as exc:
        return False, str(exc)
    if applicability == 'NOT_APPLICABLE':
        return True, 'Current admitted context and run recovery basis; structured PM state is not adopted.'
    payload = checkpoint.get('pm')
    if not isinstance(payload, dict):
        return False, 'Adopted PM state needs its current owner checkpoint.'
    from execution_checkpoint import validate_execution_basis
    status, issues = validate_execution_basis(context, payload)
    return status == 'EXECUTION_BASIS', 'Verified PM execution basis; whole-project cleanliness is a separate final owner checkpoint.' if status == 'EXECUTION_BASIS' else '; '.join(issues)


def observe_profile(context, report):
    """Observe every enabled obligation without weakening its fixed semantics."""
    from evidence_bridge import _fresh
    from run_state import criterion_report
    from run_profile import validate_profile_contract
    proof = _fresh(context)
    state = context['state']
    validate_profile_contract(state['profile'], state['contract'])
    if not isinstance(report, dict) or report != criterion_report(state, context):
        raise ValueError('Profile disposition requires the current owner criterion report')
    statuses = {row['id']: row['status'] for row in report['criteria']}
    criteria = {row['id']: row for row in state['contract']['criteria']}
    required = {key for key, row in criteria.items() if row['required']}
    flow = state.get('extensions', {}).get('workflow', {})
    if flow.get('bindings') != _bindings(state):
        raise ValueError('Current workflow is not bound to the immutable profile and contract')
    dimensions = flow['profile']['dimensions']
    if state['profile'].get('adaptive', {}).get('dimensions', dimensions) != dimensions:
        raise ValueError('Workflow dimensions differ from the effective profile')
    quality = _quality(context, statuses)
    outcomes_ok = bool(required) and all(statuses.get(key) == 'PASS' and key in quality for key in required)
    domain_proofs = {domain: sorted(key for key, rows in quality.items() if key in required and any(
        record['data'].get('domain') == domain for record in rows.values())) for domain in dimensions['domains']}
    basis = checkpoint_basis(context)
    controller = state.get('extensions', {}).get('controller', {})
    checkpoint = controller.get('checkpoint', {})
    checkpoint_ok = checkpoint.get('basis') == basis and not basis['missing_artifacts']
    pm_ok, pm_reason = _pm_current(context, checkpoint, basis) if checkpoint_ok else (False, 'Current recovery checkpoint is absent or stale.')
    graph_done = bool(flow.get('graph', {}).get('nodes')) and all(
        row['status'] == 'done' for row in flow['graph']['nodes'].values())
    waits = sorted(key for key, row in state['waits'].items() if row['status'] == 'pending')
    effects = []
    effect_evidence = []
    for identity, effect in state['effects'].items():
        reference = effect.get('evidence')
        if (effect['status'] in {'prepared', 'unknown', 'retryable'} or not reference
                or not context['verify_receipt'](reference, 'effect-readback', _bindings(state))):
            effects.append(identity)
        else:
            effect_evidence.append(reference)
    owner = {key: proof[key] for key in ('session_uuid', 'native_ref', 'project_id', 'claim_hash')}
    mapped = _criteria_for_items(state)
    triggers = controller.get('profile_obligations', {})
    trigger_rows = {'decision': [], 'reusable-finding': []}
    trigger_stale = set()
    trigger_unresolved = set()
    for identity, trigger in triggers.items():
        if trigger.get('kind') not in trigger_rows or trigger.get('bindings') != _bindings(state):
            trigger_stale.add(identity)
            continue
        hashes = trigger.get('artifact_digests', {})
        if not hashes or _current_hashes(context, set(hashes)) != hashes:
            trigger_stale.add(identity)
        if not _trigger_accepted(trigger, statuses, quality):
            trigger_unresolved.add(identity)
        trigger_rows[trigger['kind']].append(trigger)
    decision_reasons = _decision_triggers(state, dimensions)
    if trigger_rows['decision']:
        decision_reasons.append('recorded material decision')
    semantic_required = {key for key in required if _semantic({key}, statuses, quality)}
    decision_refs = set(mapped.get('framework-decisions', set()))
    for item in state['profile']['items']:
        if item['id'] == 'framework-decisions':
            decision_refs.update(item.get('criterion_ids', []))
    for trigger in trigger_rows['decision']:
        decision_refs.update(trigger.get('criterion_ids', []))
    if not decision_refs:
        decision_refs = semantic_required
    rows = {}
    for item in state['profile']['items']:
        identity = item['id']
        refs = set(item.get('criterion_ids', [])) | mapped.get(identity, set())
        applicable_triggers = trigger_rows['decision'] if identity == 'framework-decisions' else trigger_rows['reusable-finding'] if identity == 'lessons-filed' else []
        refs.update(ref for trigger in applicable_triggers for ref in trigger.get('criterion_ids', []))
        refs_ok = all(statuses.get(key) == 'PASS' for key in refs)
        status, reason = 'UNRESOLVED', 'Required current owner evidence is unavailable.'
        if identity in {'core.outcome', 'core.evidence', 'end-to-end', 'verify-before-done'}:
            if outcomes_ok:
                status, reason = 'SATISFIED', 'All required outcomes have current criterion-bound domain evidence.'
        elif identity in DOMAIN_IDS:
            domain = DOMAIN_IDS[identity]
            if domain in dimensions['domains'] and domain_proofs.get(domain):
                status, reason = 'SATISFIED', 'Current accepted domain evidence covers ' + domain + '.'
        elif identity == 'core.authority':
            if not effects:
                status, reason = 'SATISFIED', 'Current PM/native ownership admitted; recorded effects reconciled by their owner. No action authority is granted.'
        elif identity in {'core.recovery', 'plan-current', 'project-files-current'}:
            if checkpoint_ok and pm_ok:
                status, reason = 'SATISFIED', pm_reason
        elif identity == 'effect.reconciliation':
            if not effects:
                status, reason = 'SATISFIED', 'Every recorded effect has a current terminal owner readback.'
        elif identity == 'evidence.independent':
            if outcomes_ok and all(all(record['data'].get('independent') is True and
                    record['data'].get('producer') != record['data'].get('reviewer')
                    for record in quality[key].values()) for key in required):
                status, reason = 'SATISFIED', 'Current independent domain receipts cover every required criterion.'
        elif identity == 'continuation.survival':
            try:
                from capabilities import validate_horizon
                validate_horizon(state, dimensions['horizon'], context)
                status, reason = 'SATISFIED', 'The continuation owner verifies the required survival horizon.'
            except (ValueError, KeyError, OSError):
                pass
        elif identity in {'framework-decisions', 'optional.exploration'}:
            needed = bool(identity == 'optional.exploration' or decision_reasons or refs or _selected(item) or item.get('applicability') == 'always' and identity == 'framework-decisions')
            if needed and not refs:
                refs = set(semantic_required)
            if not needed:
                status, reason = 'NOT_APPLICABLE', 'Direct admitted work has no recorded material choice, amendment, competing strategy, or selected decision obligation.'
            elif _semantic(refs, statuses, quality) and not any(row['id'] in trigger_stale | trigger_unresolved for row in applicable_triggers):
                status, reason = 'SATISFIED', 'Current calibrated semantic evidence assesses the bound decision or investigation.'
            else:
                reason = 'Substantive bound reasoning evidence is required: ' + ', '.join(decision_reasons or ['explicit decision or exploration obligation']) + '.'
        elif identity == 'lessons-filed':
            needed = bool(applicable_triggers or refs or _selected(item) or item.get('applicability') == 'always')
            if not needed:
                status, reason = 'NOT_APPLICABLE', 'Optional lesson capture was not selected and no reusable finding was recorded; no assertion about absence of reusable insight.'
            elif _captured(refs, statuses, quality) and not any(row['id'] in trigger_stale | trigger_unresolved for row in applicable_triggers):
                status, reason = 'SATISFIED', 'The selected lesson or recorded reusable finding has current accepted capture evidence.'
            else:
                reason = 'Selected lesson capture or a recorded reusable finding needs bound accepted capture evidence.'
        elif identity == 'completion-report':
            # The observation below is itself the factual report, persisted by
            # the engine and returned by the facade. Custom report criteria add
            # semantic obligations; they cannot be proved by a named file.
            if outcomes_ok and (not refs or _semantic(refs, statuses, quality)):
                status, reason = 'SATISFIED', 'Factual outcome/evidence/remaining-obligation report derived from current owners.'
        elif identity == 'blog-seeds':
            if _semantic(refs, statuses, quality):
                status, reason = 'SATISFIED', 'Explicitly selected seed deliverable has current semantic acceptance.'
        elif refs and refs_ok:
            status, reason = 'SATISFIED', 'Explicit custom criterion mapping has current accepted verification.'
        if refs and not refs_ok:
            status, reason = 'UNRESOLVED', 'Explicit criterion mappings add requirements and are not currently satisfied.'
        rows[identity] = {'status': status, 'reason': reason, 'criterion_ids': sorted(refs),
            'evidence_ids': sorted({ref for key in refs for ref in quality.get(key, {})})}
    contractual = []
    if decision_reasons and not _semantic(decision_refs, statuses, quality):
        contractual.append('material-decision:substantive-reasoning')
    for identity, refs in mapped.items():
        if identity in {'framework-decisions', 'completion-report', 'blog-seeds'} and not _semantic(refs, statuses, quality):
            contractual.append('contract-obligation:' + identity)
        if identity == 'lessons-filed' and not _captured(refs, statuses, quality):
            contractual.append('contract-obligation:' + identity)
    remaining = sorted([key for key, row in rows.items() if row['status'] == 'UNRESOLVED'] + contractual +
                       ['wait:' + key for key in waits] + ['effect:' + key for key in effects] +
                       ['trigger:' + key for key in trigger_stale | trigger_unresolved] +
                       ([] if graph_done else ['workflow:unfinished-tasks']))
    completion = {'schema_version': 1, 'bindings': _bindings(state), 'scope': 'declared outcomes and current owner evidence',
        'outcomes': [{**deepcopy(row), 'verified': all(statuses.get(key) == 'PASS' and key in quality for key in row['criteria'])}
                     for row in state['contract']['outcomes']],
        'criteria': [{'id': key, 'description': row['description'], 'status': statuses.get(key, 'UNKNOWN'),
                      'evidence_ids': sorted(quality.get(key, {}))} for key, row in criteria.items()],
        'remaining': remaining, 'profile_dispositions': deepcopy(rows), 'authority_granted': False}
    return {'satisfied_items': sorted(key for key, row in rows.items() if row['status'] == 'SATISFIED'),
            'dispositions': rows, 'artifact_digests': basis['artifact_digests'], 'completion_report': completion,
            'owner_binding': owner, 'recovery_basis_digest': _digest(basis)}


def accept_profile(data, state):
    """Validate rederived disposition shape; source verification owns its truth."""
    if not isinstance(data, dict) or not isinstance(data.get('dispositions'), dict):
        return False
    items = {item['id']: item for item in state['profile']['items']}
    rows = data['dispositions']
    if set(rows) != set(items):
        return False
    satisfied = []
    for identity, item in items.items():
        row = rows[identity]
        if not isinstance(row, dict) or row.get('status') not in VERDICTS or not row.get('reason'):
            return False
        if row['status'] == 'SATISFIED':
            satisfied.append(identity)
        elif row['status'] != 'NOT_APPLICABLE' or identity not in CONDITIONAL_IDS or item.get('required', True):
            return False
    return sorted(satisfied) == data.get('satisfied_items') and not data.get('completion_report', {}).get('remaining', ['missing'])
