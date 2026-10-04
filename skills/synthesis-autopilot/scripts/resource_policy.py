"""Resource projections and execution selection under the existing run owner.

There is no store or provider API here. Native batches are accepted only by the
registered observation reducer. Estimates, owner reports, observed counters and
billing are deliberately different fields. A historical counter is not a claim
that the unobserved execution tree, an invoice, or the provider is controlled.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import base64
import zlib
import re
import json

MAX_MEASUREMENTS = 10000
MAX_USAGE_BYTES = 2 * 1024 * 1024
SHAPES = ('direct_verified', 'investigate_deliver', 'durable_program')
HUMAN_FIELDS = ('active_review_minutes', 'avoidable_questions', 'repeated_approvals',
                'message_courier_crossings', 'interruptions', 'diagnosis_repair_minutes')



CLASSIFICATION_CHOICES = {
    'task_size': {'small', 'medium', 'large', 'unknown'},
    'duration': {'short', 'long', 'unknown'},
    'dependency_structure': {'independent', 'dependent', 'multiple_owners', 'unknown'},
    'consequence': {'low', 'high', 'unknown'},
    'reversibility': {'reversible', 'irreversible', 'unknown'},
    'source_sensitivity': {'public', 'private', 'restricted', 'unknown'},
    'resource_preference': {'balanced', 'minimize_cost', 'minimize_latency', 'unknown'},
    'attention_preference': {'balanced', 'minimize_interruptions', 'frequent_review', 'unknown'},
    'required_capabilities': None, 'available_capabilities': None,
    'model_constraints': None, 'tool_constraints': None,
}


def classify_dimensions(value=None):
    """Validate declared planning facts, never authority or capability proof.

    Provenance identifies the admitted declaration or an inference. It cannot
    impersonate an owner receipt. Missing dimensions stay explicitly unknown.
    Native capability verification remains exclusively with its existing owner.
    """
    if value is None:
        value = {}
    if not isinstance(value, dict) or set(value) - CLASSIFICATION_CHOICES.keys():
        raise ValueError('Unknown task classification dimension')
    result = {}
    for name, choices in CLASSIFICATION_CHOICES.items():
        if name not in value:
            result[name] = {'value': None, 'provenance': {'kind': 'unknown', 'reason': 'No classification supplied'}, 'confidence': 'unknown'}
            continue
        row = value[name]
        if not isinstance(row, dict) or set(row) != {'value', 'provenance', 'confidence'}:
            raise ValueError('Classification requires value, provenance and confidence')
        provenance = row['provenance']
        if (not isinstance(provenance, dict) or set(provenance) != {'kind', 'reason'}
                or not isinstance(provenance['kind'], str)
                or provenance['kind'] not in {'admitted_request', 'inference', 'unknown'}
                or not isinstance(provenance['reason'], str) or not provenance['reason'].strip()
                or len(provenance['reason']) > 2048
                or not isinstance(row['confidence'], str) or row['confidence'] not in {'high', 'medium', 'low', 'unknown'}):
            raise ValueError('Invalid bounded classification provenance or confidence')
        observed = row['value']
        if choices is not None:
            if not isinstance(observed, str) or observed not in choices:
                raise ValueError('Invalid task classification: ' + name)
        elif name == 'available_capabilities':
            if (not isinstance(observed, dict) or len(observed) > 32
                    or any(not isinstance(key, str) or not key.strip() or len(key) > 128
                           or not isinstance(status, str) or status not in {'available', 'unavailable', 'unknown'} for key, status in observed.items())):
                raise ValueError('Invalid declared capability availability')
        elif (not isinstance(observed, list) or len(observed) > 32
              or any(not isinstance(item, str) or not item.strip() or len(item) > 2048 for item in observed)
              or len(set(observed)) != len(observed)):
            raise ValueError('Invalid bounded classification list')
        result[name] = deepcopy(row)
    return result

def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _tokens(counts):
    if not isinstance(counts, dict):
        return None
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise ValueError('Invalid normalized native counters')
    # Native dialects own total semantics. Cache/reasoning subcounters are never
    # added to a reported total. A missing total is only an input/output subtotal.
    if 'total_tokens' in counts:
        return counts['total_tokens']
    if {'input_tokens', 'output_tokens'} <= counts.keys():
        return counts['input_tokens'] + counts['output_tokens']
    return None


def empty_usage():
    return {'schema_version': 1, 'measurements': {}, 'cumulative': {}, 'conflicts': {},
            'unknown_events': {}, 'source_handles': [], 'joined_events': {}}


# The resource owner stores exactly the same projection using a bounded lossless
# representation. This is not a new counter, charge, provenance source or store.
# Repeated producer/locator field names dominated the former 2MiB payload. The
# journal authenticates these bytes; the digest below validates representation
# integrity, not independent authority. Logical expansion keeps the existing
# observation projection ceiling, while the resource storage limit stays 2MiB.
def _usage_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


_USAGE_STRUCTURE = re.compile(rb'"(?:[^"\\]|\\.)*"|[{}\[\],:]')


def _bounded_usage_json(raw, work_counter=None):
    # Count structural work before json.loads allocates containers. String
    # contents do not contribute nesting or separators. The existing native
    # parser then rejects duplicate keys, invalid UTF8, nonfinite values and
    # malformed JSON. These limits add a finite expansion gate, not authority.
    from native_observations import _json
    depth = 0
    if work_counter is None:
        work_counter = [0]
    for match in _USAGE_STRUCTURE.finditer(raw):
        token = match.group()
        if token.startswith(b'"'):
            continue
        work_counter[0] += 1
        if token in (b'{', b'['): depth += 1
        elif token in (b'}', b']'): depth -= 1
        if depth > 32 or work_counter[0] > MAX_MEASUREMENTS * 256:
            raise ValueError('Native resource structured expansion exceeds bound')
    return _json(raw)


def usage_projection(stored):
    """Expand only this journal owner's bounded, authenticated representation.

    The full expanded digest preserves every observation and counter. It does
    not authenticate a native source independently of the existing journal.
    """
    from native_observations import MAX_PROJECTION_BYTES
    if stored is None:
        return empty_usage()
    if not isinstance(stored, dict):
        raise ValueError('Invalid native resource projection')
    if len(_usage_bytes(stored)) > MAX_USAGE_BYTES:
        raise ValueError('Resource projection exceeds bounded journal capacity')
    if stored.get('schema_version') == 1:
        value = deepcopy(stored)
    else:
        fields = {'schema_version', 'codec', 'expanded_bytes', 'expanded_sha256',
                  'measurements', 'unknown_events', 'cumulative', 'conflicts', 'source_handles'}
        if (set(stored) != fields or type(stored.get('schema_version')) is not int
                or stored['schema_version'] != 2 or stored['codec'] != 'provenance-pages-zlib-v1'
                or type(stored['expanded_bytes']) is not int
                or not 0 < stored['expanded_bytes'] <= MAX_PROJECTION_BYTES
                or not isinstance(stored['expanded_sha256'], str)
                or any(not isinstance(stored[name], dict) for name in ('measurements', 'unknown_events', 'cumulative', 'conflicts'))
                or not isinstance(stored['source_handles'], list)):
            raise ValueError('Invalid native resource representation')
        value = {k: deepcopy(stored[k]) for k in ('cumulative', 'conflicts', 'source_handles')}
        value.update(schema_version=1, measurements={}, unknown_events={})
        remaining = MAX_PROJECTION_BYTES
        work = [0]
        try:
            for name in ('measurements', 'unknown_events'):
                if len(stored[name]) > MAX_MEASUREMENTS:
                    raise ValueError('Native resource segment capacity exceeded')
                for key, segment in stored[name].items():
                    if (not isinstance(key, str) or not isinstance(segment, dict)
                            or set(segment) != {'bytes', 'sha256', 'payload'}
                            or type(segment['bytes']) is not int
                            or not 0 < segment['bytes'] <= remaining
                            or not isinstance(segment['sha256'], str)
                            or not isinstance(segment['payload'], str)):
                        raise ValueError('Invalid native resource segment')
                    decoder = zlib.decompressobj()
                    raw = decoder.decompress(base64.b64decode(segment['payload'], validate=True), segment['bytes'] + 1)
                    if (not decoder.eof or decoder.unused_data or decoder.unconsumed_tail
                            or len(raw) != segment['bytes']
                            or hashlib.sha256(raw).hexdigest() != segment['sha256']):
                        raise ValueError('Native resource segment integrity mismatch')
                    remaining -= len(raw)
                    rows = _bounded_usage_json(raw, work)
                    if _usage_bytes(rows) != raw or not rows:
                        raise ValueError('Noncanonical native resource segment')
                    if len(value[name]) + len(rows) > MAX_MEASUREMENTS:
                        raise ValueError('Resource measurement capacity reached')
                    for ident, row in rows.items():
                        if ident in value[name] or _usage_bucket(row) != key:
                            raise ValueError('Duplicate or misplaced native resource observation')
                        value[name][ident] = row
            value['joined_events'] = _derived_joined(value)
            expanded = _usage_bytes(value)
            if (len(expanded) != stored['expanded_bytes']
                    or hashlib.sha256(expanded).hexdigest() != stored['expanded_sha256']):
                raise ValueError('Native resource representation integrity mismatch')
        except (zlib.error, UnicodeError, TypeError, RecursionError, KeyError) as exc:
            raise ValueError('Invalid native resource representation') from exc
    keys = set(empty_usage())
    if (not isinstance(value, dict) or set(value) != keys
            or type(value.get('schema_version')) is not int or value['schema_version'] != 1
            or any(not isinstance(value[name], dict) for name in keys - {'schema_version', 'source_handles'})
            or not isinstance(value['source_handles'], list)):
        raise ValueError('Invalid expanded native resource projection')
    _usage_counts(value)
    return value


def _usage_bucket(row):
    # Source coordinates, not map size or insertion order, keep completed pages
    # byte-stable across append, cold load, aliases and generation transitions.
    # Eight 1MiB source-coordinate pages form one provenance segment; this does
    # not change the reader page limit or read any bytes from the source.
    if not isinstance(row, dict) or not isinstance(row.get('locator'), dict):
        raise ValueError('Invalid native resource provenance')
    parts = [row.get(k) for k in ('source_handle', 'mode', 'generation')]
    offset = row['locator'].get('offset')
    if (any(not isinstance(x, str) or not x for x in parts)
            or type(offset) is not int or offset < 0):
        raise ValueError('Invalid native resource provenance')
    return _digest([*parts, offset // (8 * 1024 * 1024)])




def _usage_counts(usage):
    if (len(usage['joined_events']) > MAX_MEASUREMENTS
            or sum(len(usage[key]) for key in ('measurements', 'cumulative', 'conflicts', 'unknown_events')) > MAX_MEASUREMENTS):
        raise ValueError('Resource measurement capacity reached; preserve the unadvanced native cursor')


def _derived_joined(usage):
    """Exact redundant-index reconstruction; no event or alias is retired."""
    if any(not isinstance(usage.get(k), dict) for k in ('measurements', 'unknown_events')):
        raise ValueError('Invalid native resource tables')
    joined = {}
    def add(event_id, handle):
        if (not isinstance(event_id, str) or not isinstance(handle, str)
                or event_id in joined or len(joined) >= MAX_MEASUREMENTS):
            raise ValueError('Invalid or excessive retained resource observation')
        joined[event_id] = handle
    for row in usage['measurements'].values():
        if not isinstance(row, dict) or not isinstance(row.get('observations'), list):
            raise ValueError('Invalid retained resource measurement')
        for item in row['observations']:
            if not isinstance(item, dict) or set(item) != {'source_handle', 'event_id', 'generation', 'offset', 'length', 'sha256'}:
                raise ValueError('Invalid retained resource locator')
            add(item['event_id'], item['source_handle'])
    for ident, row in usage['unknown_events'].items():
        if not isinstance(row, dict) or row.get('event_id') != ident:
            raise ValueError('Invalid retained unknown resource observation')
        add(ident, row.get('source_handle'))
    return joined


def _store_usage(usage):
    from native_observations import MAX_PROJECTION_BYTES
    _usage_counts(usage)
    raw = _usage_bytes(usage)
    if len(raw) > MAX_PROJECTION_BYTES:
        raise ValueError('Expanded resource projection exceeds observation capacity')
    if _derived_joined(usage) != usage['joined_events']:
        raise ValueError('Native resource join disagrees with retained observations')
    stored = {k: deepcopy(usage[k]) for k in ('cumulative', 'conflicts', 'source_handles')}
    stored.update(schema_version=2, codec='provenance-pages-zlib-v1',
                  expanded_bytes=len(raw), expanded_sha256=hashlib.sha256(raw).hexdigest())
    work = [0]
    for name in ('measurements', 'unknown_events'):
        pages = {}
        for key, row in usage[name].items():
            pages.setdefault(_usage_bucket(row), {})[key] = row
        stored[name] = {}
        for key, rows in pages.items():
            encoded = _usage_bytes(rows)
            _bounded_usage_json(encoded, work)
            stored[name][key] = {'bytes': len(encoded), 'sha256': hashlib.sha256(encoded).hexdigest(),
                                'payload': base64.b64encode(zlib.compress(encoded)).decode('ascii')}
    if len(_usage_bytes(stored)) > MAX_USAGE_BYTES:
        raise ValueError('Resource projection exceeds bounded journal capacity')
    return stored

def ingest_native(state, handle, batch):
    """Join an owner-prepared native batch in the SAME journal transaction.

    Duplicate response identities survive cursor resets and process restarts.
    Cumulative lanes retain baseline debt and never add their counters to the
    response sum. Counter decreases start another unknown epoch, not a refund.
    """
    ledger = state.get('extensions', {}).get('workflow', {}).get('budget')
    if ledger is None:
        return
    usage = usage_projection(ledger.get('native_usage'))
    for event in batch['events']:
        if event['kind'] != 'usage.snapshot':
            continue
        if event['event_id'] in usage['joined_events']:
            continue
        usage['joined_events'][event['event_id']] = handle
        data = event['data']
        provenance = {'source_handle': handle, 'producer': deepcopy(event['producer']),
                      'mode': event['mode'], 'generation': event['native']['generation'],
                      'event_id': event['event_id'], 'locator': deepcopy(event['native'])}
        if handle not in usage['source_handles']:
            usage['source_handles'].append(handle)
            usage['source_handles'].sort()
        identity = data.get('measurement_id')
        if identity and data.get('countable') is True and data.get('aggregation') == 'per_response':
            key = _digest([event['mode'], identity])
            counters = deepcopy(data.get('last'))
            measured = {**provenance, 'identity': deepcopy(identity), 'counters': counters,
                        'tokens': _tokens(counters), 'counters_digest': data.get('counters_digest'),
                        'scope_nonoverlap': data.get('scope_nonoverlap', 'UNKNOWN'),
                        'observations': [{'source_handle': handle, 'event_id': event['event_id'],
                            **{name: event['native'][name] for name in ('generation', 'offset', 'length', 'sha256')}}],
                        'missingness': deepcopy(data.get('missingness', []))}
            previous = usage['measurements'].get(key)
            if previous is None:
                usage['measurements'][key] = measured
            else:
                previous['observations'].extend(measured['observations'])
                producer_keys = ('client', 'root_session_id', 'thread_id', 'parent_thread_id')
                if previous['counters'] != counters or any(previous['producer'].get(name) != measured['producer'].get(name) for name in producer_keys):
                    # Keep the original charge and a durable contradiction.
                    # Capture/transport aliases with the same qualified native
                    # identity retain all locators without another charge.
                    usage['conflicts'][key] = {'prior_event_id': previous['event_id'],
                        'event_id': event['event_id'], 'reason': 'response identity has conflicting counters or producer'}
        else:
            usage['unknown_events'][event['event_id']] = {
                **provenance, 'measurement_identity': deepcopy(identity),
                'reason': 'no final unique response counters', 'phase': data.get('phase')}
        totals = data.get('totals')
        if totals is not None:
            _tokens(totals)
            key = _digest([event['mode'], data['scope'], data['grammar'], event['native']['generation']])
            lane = usage['cumulative'].setdefault(key, {'source_handle': handle,
                'scope': deepcopy(data['scope']), 'mode': event['mode'], 'grammar': data['grammar'],
                'epochs': 0, 'generation': None, 'latest': None, 'known_delta': {},
                'last_offset': -1, 'last_event_id': None, 'unknown_baseline': True,
                'reset_debt': False, 'out_of_order': False})
            offset, generation = event['native']['offset'], event['native']['generation']
            if lane['last_event_id'] == event['event_id']:
                continue
            if lane['generation'] == generation and offset <= lane['last_offset']:
                lane['out_of_order'] = True
                continue
            old = lane['latest']
            reset = old is None or generation != lane['generation'] or old.keys() != totals.keys() or any(totals[k] < old[k] for k in old)
            if reset:
                lane['epochs'] += 1
                lane['reset_debt'] = lane['reset_debt'] or old is not None
            else:
                for name, amount in totals.items():
                    lane['known_delta'][name] = lane['known_delta'].get(name, 0) + amount - old[name]
            lane.update(latest=deepcopy(totals), generation=generation,
                        last_offset=offset, last_event_id=event['event_id'])
    # Assign only after all representation/count/byte checks succeed.
    ledger['native_usage'] = _store_usage(usage) if usage['joined_events'] else empty_usage()


def native_view(state):
    flow = state.get('extensions', {}).get('workflow', {})
    usage = usage_projection(flow.get('budget', {}).get('native_usage'))
    sources = state.get('extensions', {}).get('native_observations', {}).get('sources', {})
    children = {row['child_id']: row for row in flow.get('retained_children', [])}
    children.update(flow.get('children', {}))
    def child_handle(key):
        mode = children[key].get('mode', 'peer')
        return ('worker:' if mode == 'native-cli' else 'child:' if mode == 'artifact-only' else 'peer:') + key
    by_handle = {child_handle(key): row for key, row in children.items()}
    handles = {'root'} | set(sources) | set(by_handle) | set(usage['source_handles'])
    result = {}
    grouped = {}
    for row in usage['measurements'].values():
        grouped.setdefault(row['source_handle'], []).append(row)
    finals = {(_digest(row['identity']), row['mode'], row['source_handle']) for row in usage['measurements'].values()}
    for handle in sorted(handles):
        source = sources.get(handle)
        rows = grouped.get(handle, [])
        lanes = [row for row in usage['cumulative'].values() if row['source_handle'] == handle]
        child = by_handle.get(handle)
        unresolved = [key for key, row in usage['unknown_events'].items() if row['source_handle'] == handle
            and (_digest(row['measurement_identity']), row['mode'], handle) not in finals]
        mode = source['binding']['mode'] if source else (rows[0]['mode'] if rows else None)
        result[handle] = {'parent': (child_handle(child['parent_child_id']) if child and child.get('parent_child_id') in children else 'root') if handle != 'root' else None,
            'reservation_id': child.get('reservation_id') if child else None,
            'mode': mode, 'distinct_responses': len(rows),
            'distinct_response_tokens': sum(row['tokens'] for row in rows if row['tokens'] is not None) if rows else None,
            'response_counters': {name: sum(row['counters'].get(name, 0) for row in rows)
                                  for name in sorted({key for row in rows for key in (row['counters'] or {})})},
            'cumulative_lanes': deepcopy(lanes), 'unresolved_measurements': sorted(unresolved),
            'coverage': deepcopy(source.get('coverage')) if source else None,
            'enrollment': deepcopy(source.get('enrollment')) if source else None,
            'source_recovery': deepcopy(source.get('recovery')) if source else None,
            'scope_nonoverlap': 'UNKNOWN', 'complete_usage': None}
    return {'by_producer': result, 'aggregate_tree_usage': None, 'billable_cost': None,
        'conflicts': deepcopy(usage['conflicts']),
        'known_response_counter_sum': sum(row['tokens'] for row in usage['measurements'].values() if row['tokens'] is not None)
            if usage['measurements'] else None,
        'missingness': ['full_execution_tree_not_proven', 'producer_scope_nonoverlap_not_proven',
                        'billing_not_observed', 'pre_enrollment_and_post_terminal_usage_not_measured'],
        'interpretation': 'Distinct observed response counters; cumulative lanes are alternatives, never additive. '
                          'Input/output subtotals exclude unclassified cache extras. This is not whole-tree billed usage.'}


def summary(state, context=None):
    import workflow
    flow = state.get('extensions', {}).get('workflow', {})
    ledger = flow.get('budget')
    if ledger is None:
        return {'status': 'UNCONFIGURED', 'billable_cost': None, 'native': native_view(state),
                'human_effort': {key: None for key in HUMAN_FIELDS}, 'limits': {}, 'tree': {}}
    limits = workflow.budget_summary(state)
    for name, row in limits.items():
        row['enforcement_scope'] = 'owner_admission_' + row['enforcement']
        row['provider_hard_limit_enforced'] = False
        row['reported_actual'] = row['spent']
        row['estimated_reserved'] = sum(r['amounts'].get(name, 0) for r in ledger['reservations'].values() if r['parent_id'] is None)
        row['measurement_provenance'] = 'owner_reported_settlement; native counters are separate'
    tree = {}
    for ident, row in ledger['reservations'].items():
        tree[ident] = {**deepcopy(row), 'own_reported_actual': deepcopy(row['actual']),
            'subtree_known_reported_actual': {name: workflow._consumed(ledger, row, name) for name in ledger['limits']},
            'subtree_committed': {name: workflow._committed(ledger, row, name) for name in ledger['limits']}}
    reports = deepcopy(ledger.get('human_effort_reports', {}))
    for row in reports.values():
        artifact = (context or {}).get('artifacts', {}).get(row['artifact_id'])
        row['source_current'] = None if context is None else bool(artifact and artifact['digest'] == row['artifact_digest'])
    human = {'reports': reports, 'scope': 'explicit nonoverlapping reported intervals only; unreported intervals remain unknown',
             'known_reported': {name: (sum(row['metrics'][name] for row in reports.values() if row['metrics'][name] is not None)
                                      if any(row['metrics'][name] is not None for row in reports.values()) else None) for name in HUMAN_FIELDS}}
    return {'status': 'RECONCILIATION_REQUIRED' if usage_projection(ledger.get('native_usage'))['conflicts'] else 'TRACKING_WITH_EXPLICIT_UNKNOWNS', 'limits': limits, 'tree': tree,
        'human_effort_reporting': human,
        'native': native_view(state), 'billable_cost': None,
        'human_effort': {key: None for key in HUMAN_FIELDS},
        'control_cost': {'journal_revisions': state.get('revision'),
                         'controller_requests': len(state.get('extensions', {}).get('controller', {}).get('requests', {})),
                         'controller_committed_steps': sum(len(row.get('steps', {})) for row in state.get('extensions', {}).get('controller', {}).get('requests', {}).values()),
                         'policy_changes': len(flow.get('execution_policy', {}).get('history', [])),
                         'billable_tokens': None},
        'interpretation': 'Nested envelopes are counted once at their roots; direct settlement units are reported, '
                          'not provider-measured. Unknown interrupted debt remains committed.'}


def require_native_headroom(flow):
    ledger = flow.get('budget')
    if not ledger:
        return
    usage = usage_projection(ledger.get('native_usage'))
    if usage['conflicts']:
        raise ValueError('Native resource contradiction requires reconciliation before more work')
    # A confirmed individual producer lower bound alone can establish an
    # overrun without asserting that producer scopes never overlap. Capture
    # handles are provenance aliases, not distinct producers. Cumulative deltas
    # are alternative lower bounds: never add them to response measurements,
    # other cumulative lanes, or manual settlement of the same native spend.
    mapping = ledger.get('native_token_resource')
    policy = ledger['limits'].get(mapping)
    if not policy or policy['enforcement'] != 'hard':
        return
    measured = {}
    for row in usage['measurements'].values():
        if row['tokens'] is not None:
            key = _digest([row['mode'], {name: row['producer'].get(name) for name in
                ('client', 'root_session_id', 'thread_id', 'parent_thread_id')}])
            measured[key] = measured.get(key, 0) + row['tokens']
    bounds = list(measured.values())
    for lane in usage['cumulative'].values():
        delta = _tokens(lane['known_delta'])
        if delta is not None:
            bounds.append(delta)
    if bounds and max(bounds) >= policy['limit']:
        raise ValueError('Observed native token lower bound exhausts owner admission limit')


def require_completion_reserves(flow, payload):
    ledger = flow.get('budget', {}).get('reservations', {})
    selected = [payload.get(key + '_reservation_id') for key in ('integration', 'verification', 'recovery')]
    if len(set(selected + [payload['reservation_id']])) != 4:
        raise ValueError('Distinct completion, verification and recovery reservations required')
    for category, ident in zip(('integration', 'verification', 'recovery'), selected):
        row = ledger.get(ident)
        if not row or row['category'] != category or row['status'] != 'reserved' or not any(row['amounts'].values()):
            raise ValueError('Reserve ' + category + ' headroom before dispatch')
        worker = ledger.get(payload['reservation_id'], {})
        if any(amount > 0 and row['amounts'].get(name, 0) <= 0 for name, amount in worker.get('amounts', {}).items()):
            raise ValueError('Completion reserves must cover every worker resource dimension')
        if any(child.get(category + '_reservation_id') == ident for child in flow['children'].values()):
            raise ValueError('Completion reservation already assigned to another child')
    parent_id = payload.get('parent_child_id')
    if payload.get('mode') == 'artifact-only' and payload['child_id'].count('/') > 2 and parent_id is None:
        raise ValueError('Grandchild requires an explicit admitted parent identity')
    if parent_id is not None:
        parent = flow['children'].get(parent_id)
        if not parent or parent['disposition'] != 'running' or parent['audit_status'] != 'required':
            raise ValueError('Grandchild requires an active admitted parent')
        if payload.get('mode') == 'artifact-only' and payload['child_id'].rsplit('/', 1)[0] != parent_id:
            raise ValueError('Grandchild native identity does not descend from the admitted parent')
        for ident in [payload['reservation_id']] + selected:
            if ledger.get(ident, {}).get('parent_id') != parent['reservation_id']:
                raise ValueError('Grandchild work and completion reserves must stay in the parent envelope')



def required_capability_status(state, context=None):
    """Resolve only capabilities with an existing current proof owner.

    Arbitrary declared tool names remain unknown. No declaration, including a
    claimed availability, can manufacture an executable facility or permission.
    """
    flow = state['extensions']['workflow']
    facts = classify_dimensions(flow['profile']['dimensions'].get('classification'))
    required = facts['required_capabilities']['value'] or []
    result = {name: {'status': 'UNKNOWN', 'owner': 'capabilities'} for name in required}
    if not required or context is None:
        return result
    try:
        from capabilities import continuation_status
        observation = continuation_status(state, context)
        job = state.get('extensions', {}).get('capabilities', {}).get('continuation', {})
        name = 'continuation:' + str(job.get('horizon'))
        if name in result and observation.get('continuation_verified') is True:
            result[name] = {'status': 'VERIFIED', 'owner': 'capabilities',
                            'job_id': job['job_id'], 'horizon': job['horizon']}
    except (ImportError, KeyError, TypeError, ValueError):
        pass
    return result


def require_execution_capabilities(state, context):
    missing = [name for name, row in required_capability_status(state, context).items() if row['status'] != 'VERIFIED']
    if missing:
        raise ValueError('Required execution capabilities remain unverified: ' + ', '.join(missing))

def policy_basis(state, context=None):
    flow = state['extensions']['workflow']
    dims = flow['profile']['dimensions']
    nodes = flow.get('graph', {}).get('nodes', {})
    uncertainty = {'status': 'unresolved' if dims['uncertainty'] == 'high' else 'clear',
                   'source': 'admitted_workflow_dimensions', 'confidence': None}
    if state.get('extensions', {}).get('decision_uncertainty', {}).get('items'):
        try:
            from decision_uncertainty import status_view
            uncertainty = {**status_view(state, context), 'source': 'decision_uncertainty_owner', 'confidence': None}
        except (ImportError, ValueError, KeyError):
            uncertainty = {'status': 'unknown', 'source': 'decision_uncertainty_owner_unavailable', 'confidence': None}
    continuation = {'state': 'unknown', 'continuation_verified': False}
    if context is not None:
        try:
            from capabilities import continuation_status
            continuation = continuation_status(state, context)
        except (ValueError, KeyError, ImportError):
            pass
    ledger = flow.get('budget', {})
    classification = classify_dimensions(dims.get('classification'))
    return {'dimensions': deepcopy(dims), 'classification': classification, 'uncertainty': uncertainty,
        'capability_claims': {'required': classification['required_capabilities']['value'],
            'declared_available': classification['available_capabilities']['value'],
            'verification': 'UNVERIFIED', 'authority_granted': False},
        'continuation': continuation, 'required_capability_status': required_capability_status(state, context),
        'resource_limits': deepcopy(ledger.get('limits', {})),
        'unknown_reservations': sorted(key for key, row in ledger.get('reservations', {}).items() if row['status'] == 'unknown'),
        'cost_observability': 'unknown; no native invoice or billing proof',
        'dependency_edges': sorted([ident, dep] for ident, node in nodes.items() for dep in node['deps']),
        'completed_units': sorted(ident for ident, node in nodes.items() if node['status'] == 'done'),
        'blocked_units': sorted(ident for ident, node in nodes.items() if node['status'] == 'blocked'),
        'active_children': sorted(key for key, row in flow.get('children', {}).items() if row['audit_status'] != 'accepted'),
        'pending_waits': sorted(key for key, row in state.get('waits', {}).items() if row['status'] == 'pending'),
        'unreconciled_effects': sorted(key for key, row in state.get('effects', {}).items() if row['status'] in {'prepared', 'unknown', 'retryable'}),
        'graph_wip_limit': flow.get('graph', {}).get('wip_limit', 1),
        'running_units': sorted(key for key, row in nodes.items() if row['status'] == 'running')}


def select_policy(state, preference=None, context=None):
    flow = state['extensions']['workflow']
    previous = flow.get('execution_policy')
    preference = deepcopy(preference if preference is not None else (previous or {}).get('preference', {'mode': 'adaptive'}))
    if (not isinstance(preference, dict) or set(preference) - {'mode', 'shape'}
            or preference.get('mode') not in {'adaptive', 'stable'}
            or (preference['mode'] == 'stable') != ('shape' in preference)
            or 'shape' in preference and preference['shape'] not in SHAPES):
        raise ValueError('Execution preference requires adaptive mode or an explicit stable shape')
    if previous and preference != previous['preference']:
        raise ValueError('Execution preference is immutable for this run; explicit reconfiguration required')
    basis = policy_basis(state, context)
    dims = basis['dimensions']
    facts = {name: row['value'] for name, row in basis['classification'].items()}
    reasons = []
    if (dims['horizon'] == 'reboot' or dims['effect'] == 'external' or basis['pending_waits'] or basis['active_children'] or basis['unreconciled_effects']
            or facts['duration'] == 'long' or facts['dependency_structure'] == 'multiple_owners'
            or facts['consequence'] == 'high' or facts['reversibility'] == 'irreversible'):
        candidate = 'durable_program'
        reasons.append('Long duration, survival, owner coordination, waiting or consequential reconciliation requires durable execution')
    elif dims['uncertainty'] == 'high' or basis['uncertainty']['status'] != 'clear' or len(dims['domains']) > 1 or basis['dependency_edges'] or basis['blocked_units'] or facts['dependency_structure'] == 'dependent':
        candidate = 'investigate_deliver'
        reasons.append('Current uncertainty, domain integration or dependent work needs bounded investigation')
    else:
        candidate = 'direct_verified'
        reasons.append('Bounded reversible work has no unresolved investigation or durable coordination requirement')
    reasons.append('Declared task size and duration are separate from uncertainty; missing classification remains unknown')
    reasons.append('Source sensitivity, declared capability availability and model/tool constraints do not grant authority or verify availability')
    if facts['available_capabilities'] and any(value != 'available' for value in facts['available_capabilities'].values()):
        reasons.append('Declared unavailable or unknown capabilities require owner verification or an admitted alternative before dependent work')
    selected = candidate
    if preference['mode'] == 'stable':
        selected = preference['shape']
        reasons.append('The admitted stable workflow preference is fixed; acceptance and capability gates still apply')
    elif previous and SHAPES.index(candidate) < SHAPES.index(previous['shape']):
        useful_unit = bool(set(basis['completed_units']) - set(previous['basis']['completed_units']))
        owner_resolution = (previous['basis']['uncertainty']['status'] != 'clear' and basis['uncertainty']['status'] == 'clear'
                            and basis['uncertainty']['source'] == 'decision_uncertainty_owner')
        if not useful_unit and not owner_resolution:
            selected = previous['shape']
            reasons.append('Retain the current shape until a completed useful unit or current decisive resolution justifies reducing coordination')
    invariants = {key: state[key] for key in ('run_id', 'contract_digest', 'profile_digest')}
    invariants['explicit_model_and_effort'] = 'unchanged; no model/provider/effort selection is performed'
    limit = basis['graph_wip_limit'] if selected != 'direct_verified' and dims['parallelizable'] else 1
    if facts['resource_preference'] == 'minimize_cost' or facts['source_sensitivity'] == 'restricted':
        limit = 1
        reasons.append('Cost preference or restricted-source handling bounds new concurrency without changing required verification')
    limit = max(limit, len(basis['running_units']))
    history = deepcopy((previous or {}).get('history', []))
    if previous is None or selected != previous['shape']:
        history.append({'from': previous['shape'] if previous else None, 'to': selected,
            'revision': state.get('revision', 0) + 1, 'basis_digest': _digest(basis), 'reasons': reasons})
    if len(history) > 256:
        raise ValueError('Execution policy history capacity reached')
    obligations = []
    if any(row['status'] != 'VERIFIED' for row in basis['required_capability_status'].values()):
        obligations.append({'owner': 'capabilities', 'kind': 'verify_required_capabilities',
                            'capabilities': facts['required_capabilities'], 'status': 'UNVERIFIED'})
    if facts['source_sensitivity'] in {'private', 'restricted'}:
        obligations.append({'owner': 'run_state', 'kind': 'preserve_source_handling_boundary',
                            'sensitivity': facts['source_sensitivity'], 'disclosure_authorized': False})
    if facts['attention_preference'] is not None:
        reasons.append('Attention preference changes presentation and checkpoint cadence only; existing approval and quality gates remain binding')
    if dims['horizon'] == 'reboot' and not basis['continuation']['continuation_verified']:
        obligations.append({'owner': 'capabilities', 'kind': 'observed_survival_required', 'horizon': dims['horizon']})
    if basis['unknown_reservations']:
        obligations.append({'owner': 'workflow', 'kind': 'reconcile_resource_debt', 'reservations': basis['unknown_reservations']})
    return {'schema_version': 1, 'shape': selected, 'candidate': candidate, 'preference': preference,
        'obligations': obligations,
        'basis': basis, 'basis_digest': _digest(basis), 'invariants': invariants,
        'preferences': {'wip_limit': limit, 'checkpoint': 'task_and_consequential_boundaries' if facts['attention_preference'] == 'frequent_review' else 'consequential_boundaries' if selected == 'durable_program' else 'task_boundaries',
                        'investigation': selected != 'direct_verified'},
        'reasons': reasons, 'history': history, 'authority_granted': False,
        'acceptance_changed': False, 'quality_tier': 'unchanged'}
