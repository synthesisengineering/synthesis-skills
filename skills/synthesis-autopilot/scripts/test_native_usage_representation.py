"""Synthetic resource storage controls; no native or provider authority."""
from copy import deepcopy
import base64
import hashlib
import zlib

import pytest
import resource_policy as owner


def state():
    return {'extensions': {'workflow': {'budget': {'limits': {'model_tokens': {'limit': 100000, 'enforcement': 'hard'}},
        'native_token_resource': 'model_tokens', 'reservations': {'keep': {'actual': None, 'amounts': {'model_tokens': 300}}}}}}}


def event(i, *, response=None, amount=7, final=True):
    producer = {'client': 'codex', 'root_session_id': 'synthetic-root', 'thread_id': 'synthetic-root',
        'parent_thread_id': None, 'adapter_version': 'synthetic-v1', 'authentication': 'owner_admission_required'}
    native = {'generation': 'a' * 64, 'offset': i * 1024, 'length': 1024, 'sha256': hashlib.sha256(str(i).encode()).hexdigest(),
        'ordinal': i, 'sequence': i, 'subrecord': 0, 'record_id': None, 'call_id': None, 'parent_call_id': None, 'source_handle': 'root'}
    counts = {'input_tokens': amount - 2, 'output_tokens': 2, 'total_tokens': amount}
    return {'kind': 'usage.snapshot', 'event_id': 'sha256:' + hashlib.sha256(('event'+str(i)).encode()).hexdigest(),
        'producer': producer, 'native': native, 'mode': 'synthetic', 'data': {
            'measurement_id': ['codex', 'synthetic-root', str(i if response is None else response)] if final else None,
            'countable': final, 'aggregation': 'per_response', 'last': counts,
            'counters_digest': owner._digest(counts), 'scope_nonoverlap': 'UNKNOWN',
            'missingness': ['full_execution_tree_not_proven'], 'totals': counts,
            'scope': {'thread': 'synthetic-root'}, 'grammar': 'synthetic', 'phase': 'final' if final else 'unknown'}}


def ledger(s):
    return s['extensions']['workflow']['budget']


def test_compact_usage_roundtrip_preserves_all_counter_decisions():
    s = state()
    owner.ingest_native(s, 'root', {'events': [event(i, final=i % 2 == 0) for i in range(80)]})
    saved = deepcopy(s)
    logical = owner.usage_projection(ledger(s)['native_usage'])
    old = deepcopy(s); ledger(old)['native_usage'] = logical
    assert owner.native_view(s) == owner.native_view(old)
    assert owner.require_native_headroom(s['extensions']['workflow']) is None
    assert owner.require_native_headroom(old['extensions']['workflow']) is None
    assert owner.usage_projection(owner._store_usage(logical)) == logical
    assert s == saved
    for x in (s, old):
        ledger(x)['limits']['model_tokens']['limit'] = 7
        with pytest.raises(ValueError, match='lower bound'):
            owner.require_native_headroom(x['extensions']['workflow'])


def test_repeated_provenance_exceeds_old_storage_but_compact_fits():
    s = state(); budget = deepcopy(ledger(s))
    owner.ingest_native(s, 'root', {'events': [event(i, final=i % 2 == 0) for i in range(7000)]})
    packed = ledger(s)['native_usage']; logical = owner.usage_projection(packed)
    assert len(owner._usage_bytes(logical)) > owner.MAX_USAGE_BYTES
    assert len(owner._usage_bytes(packed)) <= owner.MAX_USAGE_BYTES
    assert len(logical['joined_events']) == 7000
    assert len(logical['measurements']) == len(logical['unknown_events']) == 3500
    assert {k:v for k,v in ledger(s).items() if k != 'native_usage'} == budget
    assert owner.MAX_MEASUREMENTS == 10000 and owner.MAX_USAGE_BYTES == 2 * 1024 * 1024


def test_retained_v1_migrates_once_without_changing_observations_or_debt():
    s = state(); owner.ingest_native(s, 'root', {'events': [event(1)]})
    old = owner.usage_projection(ledger(s)['native_usage']); ledger(s)['native_usage'] = deepcopy(old)
    owner.ingest_native(s, 'root', {'events': [event(1)]})
    assert ledger(s)['native_usage']['schema_version'] == 2
    assert owner.usage_projection(ledger(s)['native_usage']) == old
    before = deepcopy(s)
    owner.ingest_native(s, 'root', {'events': [event(1)]})
    assert s == before
    owner.ingest_native(s, 'alias', {'events': [event(2, response=1)]})
    logical = owner.usage_projection(ledger(s)['native_usage'])
    assert len(logical['measurements']) == 1
    assert len(next(iter(logical['measurements'].values()))['observations']) == 2
    owner.ingest_native(s, 'root', {'events': [event(3, response=1, amount=8)]})
    logical = owner.usage_projection(ledger(s)['native_usage'])
    assert logical['conflicts'] and next(iter(logical['measurements'].values()))['tokens'] == 7
    with pytest.raises(ValueError, match='contradiction'):
        owner.require_native_headroom(s['extensions']['workflow'])


@pytest.mark.parametrize('fault', ['hash', 'size', 'boolean', 'codec', 'extra', 'base64', 'trailing', 'short_bound', 'json_noncanonical'])
def test_corrupt_or_unbounded_resource_representation_refuses(fault):
    s = state(); owner.ingest_native(s, 'root', {'events': [event(1)]})
    p = deepcopy(ledger(s)['native_usage'])
    segment = next(iter(p['measurements'].values()))
    if fault == 'hash': p['expanded_sha256'] = '0'*64
    elif fault == 'size': p['expanded_bytes'] = 32*1024*1024+1
    elif fault == 'boolean': segment['bytes'] = True
    elif fault == 'codec': p['codec'] = 'other'
    elif fault == 'extra': p['authority'] = True
    elif fault == 'base64': segment['payload'] += '!'
    elif fault == 'trailing': segment['payload'] = base64.b64encode(base64.b64decode(segment['payload'])+b'trailing').decode()
    elif fault == 'short_bound': segment['bytes'] = 10
    else:
        raw = zlib.decompress(base64.b64decode(segment['payload']))+b'\n'
        segment.update(payload=base64.b64encode(zlib.compress(raw)).decode(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    ledger(s)['native_usage'] = p; before = deepcopy(s)
    with pytest.raises(ValueError): owner.ingest_native(s, 'root', {'events': [event(2)]})
    assert s == before
    with pytest.raises(ValueError): owner.native_view(s)


@pytest.mark.parametrize('bound', ['count', 'bytes'])
def test_representation_refusal_keeps_last_resource_state(monkeypatch, bound):
    s = state(); owner.ingest_native(s, 'root', {'events': [event(1)]}); before = deepcopy(s)
    if bound == 'count': monkeypatch.setattr(owner, 'MAX_MEASUREMENTS', 1)
    else: monkeypatch.setattr(owner, 'MAX_USAGE_BYTES', len(owner._usage_bytes(ledger(s)['native_usage'])))
    with pytest.raises(ValueError, match='capacity'):
        owner.ingest_native(s, 'root', {'events': [event(2)]})
    assert s == before


@pytest.mark.parametrize('raw', [b'{"x":'+b'['*33+b'0'+b']'*33+b'}', b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":"\xff"}'])
def test_expansion_depth_duplicates_nonfinite_utf8_refuse(raw):
    with pytest.raises(ValueError): owner._bounded_usage_json(raw)


def test_expansion_work_bound_precedes_object_allocation(monkeypatch):
    monkeypatch.setattr(owner, 'MAX_MEASUREMENTS', 1)
    with pytest.raises(ValueError, match='structured expansion'):
        owner._bounded_usage_json(b'{"x":['+b'0,'*256+b'0]}')


def test_join_reconstruction_refuses_missing_or_duplicated_witness():
    s = state(); owner.ingest_native(s, 'root', {'events': [event(1)]})
    logical = owner.usage_projection(ledger(s)['native_usage'])
    missing = deepcopy(logical); missing['joined_events'] = {}
    with pytest.raises(ValueError, match='join disagrees'): owner._store_usage(missing)
    duplicate = deepcopy(logical)
    row = next(iter(duplicate['measurements'].values()))
    row['observations'].append(deepcopy(row['observations'][0]))
    with pytest.raises(ValueError, match='retained resource observation'): owner._store_usage(duplicate)


def test_append_keeps_completed_provenance_segment_bytes():
    s = state(); first = event(1); second = event(2)
    second['native']['offset'] = 8 * 1024 * 1024 + 10
    owner.ingest_native(s, 'root', {'events': [first]})
    old = deepcopy(ledger(s)['native_usage']['measurements'])
    owner.ingest_native(s, 'root', {'events': [second]})
    assert all(ledger(s)['native_usage']['measurements'][k] == v for k,v in old.items())
    assert len(ledger(s)['native_usage']['measurements']) == 2


@pytest.mark.parametrize('fault', ['wrong_bucket', 'duplicate_bucket', 'bad_part_hash', 'zero_segment', 'foreign_field'])
def test_resource_segment_membership_is_closed(fault):
    s = state(); owner.ingest_native(s, 'root', {'events': [event(1)]})
    p = deepcopy(ledger(s)['native_usage']); key = next(iter(p['measurements']))
    if fault == 'wrong_bucket': p['measurements']['wrong'] = p['measurements'].pop(key)
    elif fault == 'duplicate_bucket': p['measurements']['duplicate'] = deepcopy(p['measurements'][key])
    elif fault == 'bad_part_hash': p['measurements'][key]['sha256'] = '0' * 64
    elif fault == 'zero_segment': p['measurements'][key]['bytes'] = 0
    else: p['measurements'][key]['authority'] = True
    with pytest.raises(ValueError): owner.usage_projection(p)


@pytest.mark.parametrize('body', [b'[1]', b'null', b'3', b'"value"'])
def test_nonobject_segments_refuse_at_actual_consumers(body):
    s = state(); owner.ingest_native(s, 'root', {'events': [event(1)]})
    p = ledger(s)['native_usage']; segment = next(iter(p['measurements'].values()))
    segment.update(bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),payload=base64.b64encode(zlib.compress(body)).decode())
    before = deepcopy(s)
    with pytest.raises(ValueError): owner.native_view(s)
    with pytest.raises(ValueError): owner.ingest_native(s, 'root', {'events': [event(2)]})
    assert s == before


def test_writer_checks_structured_bound_before_resource_assignment():
    s = state(); owner.ingest_native(s, 'root', {'events': [event(1)]}); before = deepcopy(s)
    bad = event(2)
    nested = []
    for _ in range(40): nested = [nested]
    bad['producer']['invalid_nested'] = nested
    with pytest.raises(ValueError, match='structured expansion'):
        owner.ingest_native(s, 'root', {'events': [bad]})
    assert s == before


def test_retained_native_index_composes_with_existing_usage_debt(tmp_path):
    import native_observations as native
    from test_native_observations import source, response_usage, usage, tokens
    changed = response_usage('same-response', 20); changed['payload']['usage'] = tokens(11)
    _, binding, cursor = source(tmp_path, [response_usage('same-response', 10), changed, usage(10), usage(4)])
    batch = native.read_page(binding, cursor)
    old_state, new_state = state(), state(); prior_budget = deepcopy(ledger(new_state))
    old = native.reduce_observations(native.empty_projection(), batch)
    new = native.reduce_observations(native.retained_projection(native.empty_projection()), batch, event_limit=100)
    owner.ingest_native(old_state, 'root', batch); owner.ingest_native(new_state, 'root', batch)
    assert old_state == new_state
    assert owner.usage_projection(ledger(new_state)['native_usage'])['conflicts']
    assert {k:v for k,v in ledger(new_state).items() if k != 'native_usage'} == prior_budget
    assert {k:v for k,v in new.items() if k not in {'events','schema_version'}} == {k:v for k,v in old.items() if k not in {'events','schema_version'}}
    with pytest.raises(ValueError, match='contradiction'): owner.require_native_headroom(new_state['extensions']['workflow'])
