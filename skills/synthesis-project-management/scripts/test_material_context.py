"""Actual record owners with synthetic material; semantic/endpoint acceptance stays pending."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

SKILLS = Path(__file__).resolve().parents[2]
# Each ordinary selector owns its sibling imports, independent of collection order.
for sibling in ('synthesis-context-lifecycle', 'synthesis-agent-conformance', 'synthesis-autopilot'):
    sys.path.insert(0, str(SKILLS / sibling / 'scripts'))
import context_edit
import record_succession as owner
import record_transaction as rt
import project_state
from test_run_admission import world, write_board
from test_record_succession import ref

PRIMARY = 'Use the detour only until the bridge inspection clears. It reduces load during that inspection. Request the inspection log and record the lesson. The bridge condition has not been independently measured.\n'
FAITHFUL = 'The detour is an interim load precaution pending inspection clearance; obtain the log and capture the lesson. The bridge condition remains unverified.\n'


def put(p, name, value):
    path = p / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value, sort_keys=True) + '\n')
    return ref(p, name)


def example(world, phase='associate', kinds=('decision',)):
    p = world['project']
    put(p, 'CONTEXT.md', '# Context\n\n## Next work\n\nRead the controlling plan.\n')
    (p / 'resources/archive').mkdir(parents=True, exist_ok=True)
    put(p, 'resources/artifacts/source.md', PRIMARY)
    put(p, 'resources/artifacts/record.md', FAITHFUL + '\nNEXT: Obtain the inspection log.\n')
    rows = []
    items = []
    for n, kind in enumerate(kinds):
        identity = 'M' + str(n + 1)
        aspects = [] if kind == 'nonmaterial' else ['facts', 'rationale', 'condition', 'uncertainty']
        rows.append({'id': identity, 'kind': kind, 'source': ref(p, 'resources/artifacts/source.md', PRIMARY.strip()), 'availability': 'retained',
            'provenance': {'origin': 'primary', 'attribution': 'Synthetic operator', 'event_time': None, 'authority': 'source-claim-not-current-authority'},
            'required_aspects': aspects, 'reason': 'Selected bounded instruction' if kind != 'nonmaterial' else 'Routine acknowledgement introduces no new decision or commitment'})
        items.append({'id': identity, 'status': 'open' if kind != 'nonmaterial' else 'nonmaterial',
            'destination': ref(p, 'resources/artifacts/record.md', FAITHFUL.strip()) if kind != 'nonmaterial' else None,
            'aspects': {key: ref(p, 'resources/artifacts/record.md', FAITHFUL.strip()) for key in aspects},
            'not_applicable': {}, 'owner': 'Synthetic operator', 'next_action': ref(p, 'resources/artifacts/record.md', 'NEXT:') if kind != 'nonmaterial' else None,
            'supersedes': None, 'reason': 'Current bounded interpretation; separate action outcomes remain open'})
    inv = put(p, 'resources/artifacts/material-input.json', {'rows': rows})
    q = {'schema': 2, 'kind': 'material-context', 'phase': phase,
        'batch': {'id': 'batch-1', 'predecessor': None, 'captured_at': datetime.now(timezone.utc).isoformat(),
            'observation': {'scope': 'declared-inputs', 'start': 'selected input A', 'end': 'selected input A', 'gaps': []}, 'excluded': []},
        'inventory': {**inv, 'format': 'json-rows', 'declared_count': len(rows)}, 'items': items if phase == 'associate' else [],
        'review': None, 'context_anchor': '## Next work\n', 'context_max_lines': 150}
    return p, q


def apply(world, q, **kw):
    return owner.apply(world['project'], q, board=world['board'], native_payload=world['actor']['native_payload'], **kw)


def rebind_inventory(p, q, edit):
    path = p / q['inventory']['path']; value = json.loads(path.read_text()); edit(value)
    put(p, q['inventory']['path'], value)
    q['inventory']['sha256'] = ref(p, q['inventory']['path'])['sha256']


def add_review(p, q, assessment='faithful', record_text=None):
    if record_text is not None:
        put(p, 'resources/artifacts/record.md', record_text)
        for row in q['items']:
            row['destination'] = ref(p, 'resources/artifacts/record.md', record_text.strip())
            row['aspects'] = {key: row['destination'] for key in row['aspects']}
            row['next_action'] = row['destination']
    reviewer = put(p, 'resources/artifacts/reviewer.md', 'Synthetic review observation, not a real model or human attestation.\n')
    reviewer['anchor'] = 'Synthetic review observation'
    data = {'schema': 1, 'kind': 'material-meaning-review', 'inventory_sha256': q['inventory']['sha256'],
        'dispositions_sha256': owner.digest(owner.encoded(q['items'])), 'reviewer': reviewer,
        'plan': ref(p, 'plan.md', 'Human-owned prose.'), 'earlier_decisions': [], 'answers': [],
        'limitations': 'Synthetic caller-authored evidence; semantic entailment and independent calibration remain unverified.'}
    for row in q['items']:
        data['answers'].append({'id': row['id'], 'question': 'What condition limits the instruction, why, what remains due, and what is unknown?',
            'source_refs': [ref(p, 'resources/artifacts/source.md', PRIMARY.strip())], 'record_refs': [row['destination']] if row['destination'] else [],
            'assessment': assessment, 'reason': 'Compare the cited input with the cited record; this field is evidence to inspect, never proof of meaning.'})
    q['review'] = put(p, 'resources/artifacts/meaning-review.json', data)


def test_material_capture_and_association_through_actual_transaction(world):
    p, q = example(world, 'capture')
    r = apply(world, q)
    pending = owner.material_context(p)
    assert pending['input_coverage'] == 'CAPTURED_PENDING'
    assert pending['semantic_review'] == 'UNREVIEWED'
    assert pending['association_reachability'] == 'REACHABLE'
    assert not (p / 'CURRENT_STATE.json').exists()
    assert not (p / 'resources/autopilot').exists()
    prior = ref(p, r['record'])
    # Preserve the capture pointer while compiling the separately admitted association.
    context = (p / 'CONTEXT.md').read_text()
    _, q2 = example(world)
    (p / 'CONTEXT.md').write_text(context)
    q2['batch']['predecessor'] = prior
    second = apply(world, q2)
    result = project_state.material_context(p)
    assert result['input_coverage'] == 'VERIFIED_FOR_DECLARED_INPUTS'
    assert result['semantic_review'] == 'UNREVIEWED'
    assert result['whole_session_coverage'] == result['historical_coverage'] == 'UNKNOWN'
    assert result['completion_established'] is False and result['authorization_granted'] is False
    assert apply(world, q2)['changed'] is False
    assert owner.validate_record(p, p / second['record'])['status'] == 'committed'


def test_conditional_intent_omission_is_not_complete(world):
    p, q = example(world)
    q['items'][0]['aspects'].pop('condition')
    q['items'][0]['not_applicable']['condition'] = 'Summary is shorter'
    result = owner.review(p, q)
    assert result['input_coverage'] == 'MISSING_MATERIAL'
    assert result['missing_aspects'] == ['M1:condition']
    with pytest.raises(ValueError, match='incomplete'):
        apply(world, q)
    assert not list((p / 'resources/artifacts').glob('*-succession.json'))


def test_independent_requests_missing_dispositions_are_not_action_completion(world):
    p, q = example(world, kinds=('decision', 'commitment', 'commitment'))
    q['items'] = q['items'][:1]
    result = owner.review(p, q)
    assert result['missing_items'] == ['M2', 'M3']
    assert not result['identity_complete'] and not result['completion_established']
    with pytest.raises(ValueError):
        apply(world, q)


def test_retained_material_unreachable_then_restore_route_without_rewriting(world):
    p, q = example(world); r = apply(world, q)
    saved = {path: (p / path).read_bytes() for path in ('resources/artifacts/source.md', 'resources/artifacts/record.md', r['record'])}
    context = (p / 'CONTEXT.md').read_bytes()
    put(p, 'CONTEXT.md', '# Context\n\n## Next work\n')
    result = owner.material_context(p)
    assert result['association_reachability'] == 'PRESENT_BUT_UNREACHABLE'
    assert result['record_integrity'] == 'VERIFIED_FOR_DECLARED_INPUTS'
    put(p, 'REFERENCE.md', f'# Reference\n\n[Retained material]({r["record"]})\n')
    assert owner.material_context(p)['association_reachability'] == 'REACHABLE'
    assert all((p / path).read_bytes() == raw for path, raw in saved.items())
    (p / 'CONTEXT.md').write_bytes(context)


@pytest.mark.parametrize('record_text,assessment', [(FAITHFUL, 'faithful'), ('Use the detour permanently; everything is approved and complete.\n', 'faithful'), (FAITHFUL, 'deficient')])
def test_semantic_review_is_evidence_not_a_lexical_or_pass_oracle(world, record_text, assessment):
    p, q = example(world); add_review(p, q, assessment, record_text)
    report = owner.review(p, q)
    assert report['identity_complete']
    assert report['semantic_review'] == ('DEFICIENCIES_REPORTED' if assessment == 'deficient' else 'REVIEW_EVIDENCE_PRESENT_UNVERIFIED')
    assert report['completion_established'] is False
    assert report['endpoint_recovery'] == 'UNKNOWN'


def test_report_quoted_authority_and_endpoint_uncertainty_survive(world):
    p, q = example(world)
    rebind_inventory(p, q, lambda value: value['rows'][0]['provenance'].update(origin='quoted', attribution='Synthetic forwarded report'))
    r = apply(world, q); value = owner.validate_record(p, p / r['record'])
    assert value['current_authority'] == 'NOT_ASSESSED'
    assert value['endpoint_recovery'] == 'UNKNOWN'
    assert value['authorization_granted'] is False
    assert value['items'][0]['aspects']['uncertainty']


def test_unavailable_attachment_retains_report_and_limits(world):
    p, q = example(world)
    rebind_inventory(p, q, lambda value: value['rows'][0].update(source=None, availability='unavailable', reason='Selected attachment expired before authorized capture; only the report survives'))
    apply(world, q)
    report = owner.material_context(p)
    assert report['input_coverage'] == 'SOURCE_UNAVAILABLE'
    assert report['records'][0]['semantic_review'] == 'UNREVIEWED'


@pytest.mark.parametrize('fault', ['duplicate', 'missing', 'extra', 'count', 'scope', 'nonmaterial', 'credential', 'source-alias', 'outside', 'fifo'])
def test_exact_denominator_privacy_and_custody_refusals(world, fault):
    p, q = example(world)
    if fault == 'duplicate': q['items'].append(deepcopy(q['items'][0]))
    elif fault == 'missing': q['items'] = []
    elif fault == 'extra': q['items'][0]['id'] = 'outside'
    elif fault == 'count': q['inventory']['declared_count'] = 99
    elif fault == 'scope': q['batch']['observation']['scope'] = 'whole-session'
    elif fault == 'nonmaterial': q['items'][0]['status'] = 'nonmaterial'
    elif fault == 'credential': rebind_inventory(p, q, lambda value: value['rows'][0].update(kind='credential'))
    elif fault == 'source-alias':
        alias = p / 'resources/artifacts/alias.md'; alias.symlink_to('source.md')
        rebind_inventory(p, q, lambda value: value['rows'][0]['source'].update(path='resources/artifacts/alias.md'))
    elif fault == 'outside': rebind_inventory(p, q, lambda value: value['rows'][0]['source'].update(path='../foreign.md'))
    else:
        path = p / 'resources/artifacts/fifo'; os.mkfifo(path)
        rebind_inventory(p, q, lambda value: value['rows'][0]['source'].update(path='resources/artifacts/fifo'))
    with pytest.raises((ValueError, RuntimeError, OSError)):
        apply(world, q)
    assert not list((p / 'resources/artifacts').glob('*-succession.json'))
    assert (p / 'resources/artifacts/source.md').read_text() == PRIMARY


@pytest.mark.parametrize('fault', ['inventory', 'destination', 'plan', 'review'])
def test_changed_review_generation_never_reuses_judgment(world, fault):
    p, q = example(world); add_review(p, q); r = apply(world, q)
    if fault == 'inventory': target = p / q['inventory']['path']
    elif fault == 'destination': target = p / q['items'][0]['destination']['path']
    elif fault == 'review': target = p / q['review']['path']
    else: target = p / 'plan.md'
    target.write_bytes(target.read_bytes() + b'\nChanged current generation.\n')
    with pytest.raises((ValueError, RuntimeError, OSError)):
        apply(world, q)
    assert owner.material_context(p)['record_integrity'] == 'CHANGED_REQUIRES_REVIEW'
    assert (p / r['record']).exists()


@pytest.mark.parametrize('fault', ['released', 'foreign-claim', 'changed-during-fence'])
def test_current_authority_and_last_source_fence(world, monkeypatch, fault):
    p, q = example(world)
    if fault == 'released': write_board(world, status='released')
    elif fault == 'foreign-claim': write_board(world, claims=str(p / 'elsewhere/**'))
    else:
        original = rt._authority; calls = []
        def change(*args, **kw):
            proof = original(*args, **kw); calls.append(True)
            if len(calls) == 2:
                path = p / 'resources/artifacts/record.md'; path.write_bytes(path.read_bytes() + b'\nChanged after preflight.\n')
            return proof
        monkeypatch.setattr(rt, '_authority', change)
    before = (p / 'CONTEXT.md').read_bytes()
    with pytest.raises((ValueError, RuntimeError, OSError)):
        apply(world, q)
    assert (p / 'CONTEXT.md').read_bytes() == before
    assert not any(json.loads(x.read_text()).get('status') == 'committed' for x in (p / 'resources/artifacts').glob('*-succession.json'))


def test_prepared_interruption_is_visible_and_exact_retry_finishes(world, monkeypatch):
    p, q = example(world); original = owner._preserve; stopped = []
    def interrupt(path, data):
        original(path, data)
        if path.name.endswith('-succession.json') and not stopped:
            stopped.append(path); raise RuntimeError('synthetic interruption after prepared record')
    monkeypatch.setattr(owner, '_preserve', interrupt)
    with pytest.raises(RuntimeError, match='synthetic interruption'):
        apply(world, q)
    assert owner.material_context(p)['input_coverage'] == 'CAPTURED_PENDING'
    monkeypatch.setattr(owner, '_preserve', original)
    apply(world, q)
    assert owner.material_context(p)['input_coverage'] == 'VERIFIED_FOR_DECLARED_INPUTS'


def test_capture_cancellation_retains_pending_without_late_association(world):
    p, q = example(world, 'capture'); r = apply(world, q)
    retained = (p / r['record']).read_bytes(); write_board(world, status='released')
    with pytest.raises((ValueError, RuntimeError)):
        apply(world, q)
    assert (p / r['record']).read_bytes() == retained
    assert owner.material_context(p)['input_coverage'] == 'CAPTURED_PENDING'


def test_unknown_legacy_and_nonmaterial_do_not_invent_obligations(world):
    p = world['project']; report = owner.material_context(p)
    assert report['input_coverage'] == report['historical_coverage'] == 'UNKNOWN'
    p, q = example(world, kinds=('nonmaterial',)); apply(world, q)
    report = owner.material_context(p)
    assert report['input_coverage'] == 'VERIFIED_FOR_DECLARED_INPUTS'
    assert not report['active_items'][0]['obligations']
    assert report['whole_session_coverage'] == 'UNKNOWN'


@pytest.mark.parametrize('bound', ['items', 'refs', 'bytes', 'entries', 'time', 'depth'])
def test_finite_observation_bounds_preserve_incomplete_prefix(world, monkeypatch, bound):
    p, q = example(world); apply(world, q)
    if bound == 'items': monkeypatch.setattr(owner, 'MAX_ITEMS', 0)
    elif bound == 'refs': monkeypatch.setattr(owner, 'MAX_REFS', 1)
    elif bound == 'bytes': monkeypatch.setattr(owner, 'MAX_SOURCE_BYTES', 1)
    elif bound == 'entries': monkeypatch.setattr(owner, 'MAX_ARTIFACT_ENTRIES', 1)
    elif bound == 'depth':
        record = next((p / 'resources/artifacts').glob('*-succession.json'))
        put(p, 'CONTEXT.md', '# Context\n\n[Start](route-0.md)\n')
        for index in range(5):
            target = 'route-' + str(index + 1) + '.md' if index < 4 else str(record.relative_to(p))
            put(p, 'route-' + str(index) + '.md', '[Continue](' + target + ')\n')
    else: monkeypatch.setattr(owner, 'SCAN_SECONDS', -1)
    report = owner.material_context(p)
    assert report['record_integrity'] == 'INCOMPLETE'
    assert report['issues'] and not report['completion_established']
    assert (p / 'resources/artifacts/source.md').read_text() == PRIMARY
    if bound == 'depth':
        assert 'depth bound' in str(report['issues'])
        put(p, 'CONTEXT.md', '# Context\n\n[Start within bound](route-1.md)\n')
        assert owner.material_context(p)['association_reachability'] == 'REACHABLE'


def test_ordinary_checkpoint_exposes_material_before_not_applicable(world, capsys):
    p, q = example(world, 'capture'); apply(world, q)
    assert project_state.main(['checkpoint', '--project', str(p), '--session-id', 'synthetic', '--coordination-board', str(world['board']), '--receipt-root', str(world['scratch'] / 'receipts')]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'NOT_APPLICABLE' and report['no_receipt_issued'] is True
    assert report['material_context']['input_coverage'] == 'CAPTURED_PENDING'
    assert not (p / 'CURRENT_STATE.json').exists()


def test_doctor_consumes_one_shared_projection_with_exact_denominators(world):
    import context_doctor
    p, q = example(world, 'capture'); apply(world, q)
    audit = context_doctor.audit_project(context_doctor.Source('synthetic', world['repo']), p.name, p, {'id': p.name, 'status': 'active'}, world['repo'], p.parent, readiness='local')
    assert audit.material_context['examined_records'] == 1
    assert audit.material_context['skipped_records'] == 0
    assert audit.material_context['semantic_review'] == 'UNREVIEWED'
    assert 'material-context' in audit.examined


def test_amendment_and_cancellation_preserve_predecessor_and_do_not_reopen(world):
    p, q = example(world); old = apply(world, q); before = (p / old['record']).read_bytes()
    second = deepcopy(q); second['batch']['id'] = 'batch-2'; second['batch']['predecessor'] = ref(p, old['record'])
    put(p, 'resources/artifacts/cancellation-source.md', 'Cancel the detour instruction. The inspection and its uncertainty remain recorded.\n')
    inventory = json.loads((p / q['inventory']['path']).read_text())
    inventory['rows'][0].update(kind='cancellation', source=ref(p, 'resources/artifacts/cancellation-source.md', 'Cancel the detour instruction.'))
    second['inventory'] = {**put(p, 'resources/artifacts/second-input.json', inventory), 'format': 'json-rows', 'declared_count': 1}
    put(p, 'resources/artifacts/cancelled.md', FAITHFUL + '\nThe detour commitment is cancelled; no completion is asserted.\n')
    row = second['items'][0]; row.update(status='cancelled', next_action=None, supersedes={'record': ref(p, old['record']), 'id': 'M1'})
    row['destination'] = ref(p, 'resources/artifacts/cancelled.md', 'The detour commitment is cancelled;')
    row['aspects'] = {key: ref(p, 'resources/artifacts/cancelled.md', FAITHFUL.strip()) for key in row['aspects']}
    apply(world, second)
    report = owner.material_context(p)
    assert len(report['active_items']) == 1 and report['active_items'][0]['status'] == 'cancelled'
    assert report['active_items'][0]['obligations'] == []
    assert (p / old['record']).read_bytes() == before
    assert report['completion_established'] is False


@pytest.mark.parametrize('phase', ['prepared', 'before-record', 'after-record', 'before-context', 'after-context'])
def test_real_process_loss_uses_existing_transaction_recovery(world, phase):
    import subprocess
    p, q = example(world)
    request_path = world['scratch'] / 'material-request.json'; request_path.write_text(json.dumps(q))
    payload = world['scratch'] / 'payload.json'; payload.write_text(json.dumps(world['actor']['native_payload']))
    script = world['scratch'] / 'interrupt-material.py'
    script.write_text('''import os,sys
from pathlib import Path
sys.path.insert(0, %r)
import context_edit,record_succession,record_transaction
phase=%r
preserve=record_succession._preserve
replace=os.replace
def stop_preserve(path,data):
 preserve(path,data)
 if phase=='prepared' and Path(path).name.endswith('-succession.json'):os._exit(77)
def stop_replace(src,dst):
 name=Path(dst).name
 kind='record' if name.endswith('-succession.json') else 'context' if name=='CONTEXT.md' else 'other'
 if phase=='before-'+kind:os._exit(77)
 result=replace(src,dst)
 if phase=='after-'+kind:os._exit(77)
 return result
record_succession._preserve=stop_preserve
os.replace=stop_replace
raise SystemExit(context_edit.main(sys.argv[1:]))
''' % (str(Path(context_edit.__file__).parent), phase))
    args = ['--project', str(p), '--board', str(world['board']), '--native-payload', str(payload)]
    result = subprocess.run([sys.executable, '-B', str(script), 'apply-succession', *args, '--request', str(request_path)], capture_output=True, text=True, timeout=25)
    assert result.returncode == 77, result.stderr
    observation = owner.material_context(p)
    assert observation['input_coverage'] != 'VERIFIED_FOR_DECLARED_INPUTS'
    if phase == 'prepared':
        done = subprocess.run([sys.executable, '-B', str(Path(context_edit.__file__)), 'apply-succession', *args, '--request', str(request_path)], capture_output=True, text=True, timeout=25)
    else:
        done = subprocess.run([sys.executable, '-B', str(Path(context_edit.__file__)), 'recover-transaction', *args], capture_output=True, text=True, timeout=25)
    assert done.returncode == 0, done.stderr
    assert owner.material_context(p)['input_coverage'] == 'VERIFIED_FOR_DECLARED_INPUTS'


def test_git_only_cold_reader_uses_resolver_and_retained_associations(world, monkeypatch):
    import subprocess
    from test_run_admission import git
    p, q = example(world); apply(world, q)
    git(world['repo'], 'add', 'projects'); git(world['repo'], 'commit', '-m', 'Synthetic fixture')
    checkout = world['scratch'] / 'cold-checkout'
    subprocess.run(['git', 'clone', '--no-local', str(world['repo']), str(checkout)], check=True, capture_output=True, timeout=20)
    home = world['scratch'] / 'cold-home'; home.mkdir()
    script = world['scratch'] / 'cold-reader.py'
    script.write_text('''import sys,json
from pathlib import Path
sys.path.insert(0,%r)
import project_state
root=Path(sys.argv[1]);project=root/'projects/alpha'
r=project_state.resolve_project('alpha',root/'projects/index.yaml',fetch=False,refresh_coordination=False,coordination_board=Path(sys.argv[2])/'absent-board.md',repo_guard_root=Path(sys.argv[2])/'repo-guard',checkpoint_receipt_root=Path(sys.argv[2])/'receipts')
assert r.selected_path==str(project),r.as_dict()
report=project_state.material_context(project)
print(json.dumps({'resolver':r.status,'material':report,'recovered':(project/report['active_items'][0]['destination']['path']).read_text()}))
''' % str(Path(project_state.__file__).parent))
    env = {k: v for k, v in os.environ.items() if not k.startswith(('SYNTHESIS_', 'CLAUDE_', 'CODEX_', 'PYTHONPATH'))}
    env.update(HOME=str(home), SYNTHESIS_HOME=str(home / '.synthesis'), PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([sys.executable, '-B', str(script), str(checkout), str(home)], env=env, capture_output=True, text=True, timeout=25)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['material']['association_reachability'] == 'REACHABLE'
    assert report['recovered'].startswith(FAITHFUL)
    assert report['material']['semantic_review'] == 'UNREVIEWED'
    assert report['material']['endpoint_recovery'] == 'UNKNOWN'
    (world['scratch'] / 'cold-reader-result.json').write_text(result.stdout)


def test_prepared_capture_cannot_hide_behind_a_complete_association(world, monkeypatch):
    p, q = example(world); apply(world, q)
    pending = deepcopy(q); pending['phase'] = 'capture'; pending['items'] = []
    pending['batch']['id'] = 'new-pending-input'
    original = owner._preserve
    def interrupt(path, data):
        original(path, data)
        if Path(path).name.endswith('-succession.json'):
            raise RuntimeError('synthetic interruption after exact prepared custody')
    monkeypatch.setattr(owner, '_preserve', interrupt)
    with pytest.raises(RuntimeError, match='synthetic interruption'):
        apply(world, pending)
    report = owner.material_context(p)
    assert report['input_coverage'] == 'CAPTURED_PENDING'
    assert report['record_integrity'] == 'INCOMPLETE'
    assert report['examined_records'] == 2


def test_association_cannot_silently_replace_captured_input_denominator(world):
    p, q = example(world, 'capture', kinds=('decision', 'commitment'))
    captured = apply(world, q); prior = ref(p, captured['record'])
    saved = (p / 'CONTEXT.md').read_text()
    p, changed = example(world)
    (p / 'CONTEXT.md').write_text(saved)
    changed['batch']['predecessor'] = prior
    with pytest.raises(ValueError, match='exact captured input inventory'):
        apply(world, changed)
    report = owner.material_context(p)
    assert report['input_coverage'] == 'CAPTURED_PENDING'
    assert report['record_integrity'] == 'CHANGED_REQUIRES_REVIEW'


def test_meaning_review_citations_belong_to_the_selected_item(world):
    p, q = example(world, kinds=('decision', 'commitment'))
    second = put(p, 'resources/artifacts/second-source.md', 'A separate synthetic request.\n')
    second['anchor'] = 'A separate synthetic request.'
    rebind_inventory(p, q, lambda inv: inv['rows'][1].update(source=second))
    add_review(p, q)
    with pytest.raises(ValueError, match='outside its exact input'):
        owner.review(p, q)


def test_capsule_projection_retains_references_without_copying_narrative(world):
    p, q = example(world); receipt = apply(world, q)
    report = owner.material_context(p); projection = owner.material_projection(report)
    assert projection['records'][0]['record'] == receipt['record']
    assert projection['records'][0]['sha256'] == ref(p, receipt['record'])['sha256']
    assert projection['input_coverage'] == 'VERIFIED_FOR_DECLARED_INPUTS'
    assert projection['narrative_copied'] is False
    assert 'active_items' not in projection
    assert FAITHFUL.strip() not in json.dumps(projection)
    assert projection['semantic_review'] == 'UNREVIEWED'


def test_retired_material_is_not_recreated_by_format_refresh(world):
    import project_format
    p, q = example(world)
    put(p, 'REFERENCE.md', '# Reference\n')
    put(p, 'sessions/2026-09.md', '# Synthetic session\nOPEN: Obtain the inspection log\n')
    retired = ref(p, 'sessions/2026-09.md', 'Obtain the inspection log')
    q['items'][0].update(status='retired', destination=retired, next_action=None,
        reason='Retired by the synthetic source record; this is not completed work')
    apply(world, q)
    project_format.migrate(p, apply=True)
    state_path = p / project_format.STATE_NAME
    state = json.loads(state_path.read_text())
    # A prior unverified candidate is explicitly removed by the fixture owner;
    # refresh must not recreate it from the still-retained historical source.
    state['open_loops'] = []
    state_path.write_text(json.dumps(state))
    result = project_format.refresh(p, apply=True)
    assert result['material_context']['active_items'][0]['status'] == 'retired'
    assert not json.loads(state_path.read_text())['open_loops']
    with (p / 'sessions/2026-09.md').open('a') as stream:
        stream.write('Changed source generation: review the prior retirement.\n')
    changed = project_format.refresh(p, apply=True)
    assert changed['material_context']['record_integrity'] == 'CHANGED_REQUIRES_REVIEW'
    loops = json.loads(state_path.read_text())['open_loops']
    assert len(loops) == 1 and loops[0]['unverified'] is True


def test_material_observation_cost_is_bounded_and_unknowns_are_explicit(world):
    p = world['project']; samples = {'idle': owner.material_context(p)}
    p, q = example(world, kinds=('decision', 'commitment', 'question')); apply(world, q)
    samples['three-inputs'] = owner.material_context(p)
    assert apply(world, q)['changed'] is False
    samples['exact-retry'] = owner.material_context(p)
    inventory = json.loads((p / q['inventory']['path']).read_text())
    single = deepcopy(q); single['batch']['id'] = 'cost-single'; single['items'] = single['items'][:1]
    single['inventory'] = {**put(p, 'resources/artifacts/cost-single.json', {'rows': inventory['rows'][:1]}), 'format': 'json-rows', 'declared_count': 1}
    first = apply(world, single); samples['single-change'] = owner.material_context(p)
    amended = deepcopy(single); amended['batch'].update(id='cost-amendment', predecessor=ref(p, first['record']))
    amended['items'][0].update(status='amended', supersedes={'record': ref(p, first['record']), 'id': 'M1'}, reason='Synthetic amendment retains the condition and changes the explicit recorded disposition')
    revised = deepcopy(inventory['rows'][:1]); revised[0]['kind'] = 'amendment'
    amended['inventory'] = {**put(p, 'resources/artifacts/cost-amended.json', {'rows': revised}), 'format': 'json-rows', 'declared_count': 1}
    apply(world, amended); samples['amendment'] = owner.material_context(p)
    large = deepcopy(q); large['batch']['id'] = 'cost-finite-32'; large['items'] = []; rows = []
    for index in range(32):
        identity = 'LOAD' + str(index)
        row = deepcopy(inventory['rows'][0]); row['id'] = identity; rows.append(row)
        item = deepcopy(q['items'][0]); item['id'] = identity; large['items'].append(item)
    large['inventory'] = {**put(p, 'resources/artifacts/cost-finite.json', {'rows': rows}), 'format': 'json-rows', 'declared_count': 32}
    apply(world, large); samples['finite-32-inputs'] = owner.material_context(p)
    assert samples['finite-32-inputs']['record_integrity'] == 'VERIFIED_FOR_DECLARED_INPUTS'
    for report in samples.values():
        cost = report['resource_usage']
        assert cost['model_usage'] == 'UNKNOWN'
        assert cost['reference_observations'] <= cost['limits']['references']
        assert cost['charged_bytes'] <= cost['limits']['bytes']
        assert report['whole_session_coverage'] == 'UNKNOWN'
    (world['scratch'] / 'material-cost.json').write_text(json.dumps(samples, indent=2))


def test_actual_installed_context_consumer_and_lazy_helper_custody(world, monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'synthesis-onboarding/scripts'))
    import test_release_runtime as fixtures
    import release_runtime as runtime
    p, q = example(world, 'capture'); apply(world, q)
    home = world['scratch'] / 'installed-home'; home.mkdir()
    monkeypatch.setenv('HOME', str(home)); monkeypatch.setenv('SYNTHESIS_HOME', str(home / '.synthesis'))
    active = fixtures.active.__wrapped__(home, monkeypatch)
    pointer, root, verified = fixtures._stop_release_with_receipt(active)
    entry = 'synthesis-context-lifecycle/scripts/context_edit.py'
    closure = fixtures._stop_import_closure(entry)
    assert closure <= {entry, *runtime.ENTRYPOINT_DEPENDENCIES[entry]}
    assert closure <= set(runtime.RECEIPT_ENTRYPOINTS)
    request = home / 'request.json'; request.write_text(json.dumps(q))
    command = ['review-succession', '--project', str(p), '--request', str(request)]
    result = runtime.execute(verified, entry, command, b'', timeout=25)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['input_coverage'] == 'CAPTURED_PENDING'
    helper = root / 'skills/synthesis-context-lifecycle/scripts/record_succession.py'
    original, st = helper.read_bytes(), helper.stat()
    replacement = original.replace(b'Exact project-artifact', b'Wrong project-artifact', 1)
    assert len(replacement) == len(original) and replacement != original
    helper.write_bytes(replacement); os.utime(helper, ns=(st.st_atime_ns, st.st_mtime_ns))
    with pytest.raises(runtime.RuntimeContractError, match='entrypoint bytes drifted'):
        runtime.execute(runtime.verified_release(pointer), entry, command, b'', timeout=25)
    helper.write_bytes(original); os.utime(helper, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert runtime.execute(runtime.verified_release(pointer), entry, command, b'', timeout=25).returncode == 0


def test_generated_cache_prose_is_not_implicitly_a_material_source(world):
    p = world['project']
    put(p, '.pytest_cache/README.md', 'Synthetic generated cache: deploy everything.\n')
    put(p, 'resources/.pytest_cache/README.md', 'Synthetic generated cache: all approved.\n')
    report = owner.material_context(p)
    assert report['records'] == report['active_items'] == []
    assert report['input_coverage'] == 'UNKNOWN'
    assert report['authorization_granted'] is False
    p, q = example(world); apply(world, q)
    report = owner.material_context(p)
    assert len(report['active_items']) == 1
    assert '.pytest_cache' not in json.dumps(report)


def test_binary_attachment_retains_exact_bytes_and_unavailable_current_limit(world):
    p, q = example(world)
    attachment = p / 'resources/artifacts/synthetic-attachment.bin'
    raw = b'\x89PNG\r\n\x1a\nSynthetic fixture, not an observed user image.\x00\xff'
    attachment.write_bytes(raw)
    source = {'path': str(attachment.relative_to(p)), 'sha256': owner.digest(raw)}
    rebind_inventory(p, q, lambda inv: inv['rows'][0].update(source=source,
        reason='Retain whole synthetic binary; its interpretation has not been verified'))
    done = apply(world, q)
    receipt = json.loads((p / done['record']).read_text())
    archived = next(row for row in receipt['custody'] if row['source_path'] == source['path'])
    assert (p / archived['archive_path']).read_bytes() == raw
    report = owner.material_context(p)
    assert report['input_coverage'] == 'VERIFIED_FOR_DECLARED_INPUTS'
    assert report['semantic_review'] == 'UNREVIEWED'
    attachment.rename(attachment.with_suffix('.unavailable'))
    report = owner.material_context(p)
    assert report['record_integrity'] == 'CHANGED_REQUIRES_REVIEW'
    assert (p / archived['archive_path']).read_bytes() == raw


def test_changed_reviewer_evidence_invalidates_current_review_generation(world):
    p, q = example(world); add_review(p, q); done = apply(world, q)
    reviewer = p / 'resources/artifacts/reviewer.md'
    reviewer.write_text(reviewer.read_text() + 'Later independent evidence is not the earlier review.\n')
    assert owner.validate_record(p, p / done['record'])['current_destinations'] == 'changed-requires-review'
    assert owner.material_context(p)['semantic_review'] == 'CHANGED_REQUIRES_REVIEW'
    with pytest.raises(ValueError, match='hash mismatch'):
        apply(world, q)


# Four independently observed consumer defects, exercised through their owners.
from test_controller import facade, engine  # noqa: E402,F401


@pytest.mark.parametrize('condition', ['legacy-empty', 'current', 'enumeration-refused', 'malformed'])
def test_incomplete_empty_material_inventory_never_clears_recovery(facade, world, monkeypatch, condition):
    from test_controller import invoke, request, attribute_recovery_fixture
    from test_recovery_capsule import checkpoint
    p = world['project']
    if condition != 'legacy-empty':
        p, q = example(world); committed = apply(world, q)
    state, reference = checkpoint(facade, world)
    if condition == 'enumeration-refused':
        monkeypatch.setattr(owner, 'MAX_ARTIFACT_ENTRIES', 0)
    elif condition == 'malformed':
        put(p, committed['record'], [])
    observed = owner.material_context(p)
    attribute_recovery_fixture(world)
    response = invoke(facade, world, request('recover',
        {'reconcile_sources': True, 'capsule_ref': reference['event_ref']}, state, 'material-scan-recovery'))
    report = response['coverage']['recovery']
    pending = any(row['kind'] == 'material_reconciliation' for row in report['pending'])
    assert pending == (condition in {'enumeration-refused', 'malformed'})
    assert report['authority_granted'] is False
    if pending:
        assert observed['record_integrity'] == 'INCOMPLETE'
        assert observed['records'] == []
        assert report['status'] == 'reconcile'
    else:
        assert response['status'] == 'READY'
        assert observed['input_coverage'] == ('UNKNOWN' if condition == 'legacy-empty' else 'VERIFIED_FOR_DECLARED_INPUTS')


@pytest.mark.parametrize('shape', [
    'list', 'null', 'number', 'text', 'missing-request', 'request-list',
    'request-null', 'kind-list', 'request-kind-list', 'request-batch-list',
    'request-phase-list', 'request-time-number', 'custody-item-list',
])
def test_malformed_retained_material_is_incomplete_for_ordinary_consumers(world, capsys, shape):
    import context_doctor
    import skill_outputs
    p, q = example(world); committed = apply(world, q)
    path = p / committed['record']
    data = json.loads(path.read_text())
    if shape == 'list': data = []
    elif shape == 'null': data = None
    elif shape == 'number': data = 1
    elif shape == 'text': data = 'retained malformed fixture'
    elif shape == 'missing-request': data.pop('request')
    elif shape == 'request-list': data['request'] = []
    elif shape == 'request-null': data['request'] = None
    elif shape == 'kind-list': data['kind'] = []
    elif shape == 'request-kind-list': data['request']['kind'] = []
    elif shape == 'request-batch-list': data['request']['batch'] = []
    elif shape == 'request-phase-list': data['request']['phase'] = []
    elif shape == 'request-time-number': data['request']['batch']['captured_at'] = 1
    elif shape == 'custody-item-list': data['custody'][0] = []
    raw = json.dumps(data).encode(); path.write_bytes(raw)
    assert project_state.main(['checkpoint', '--project', str(p), '--session-id', 'synthetic',
        '--coordination-board', str(world['board']), '--receipt-root', str(world['scratch'] / 'receipts')]) == 0
    material = json.loads(capsys.readouterr().out)['material_context']
    assert material['record_integrity'] == 'INCOMPLETE' and material['issues']
    audit = context_doctor.audit_project(context_doctor.Source('synthetic', world['repo']),
        p.name, p, {'id': p.name, 'status': 'active'}, world['repo'], p.parent, readiness='local')
    assert audit.material_context['record_integrity'] == 'INCOMPLETE'
    assert skill_outputs.scan_project(p)
    with pytest.raises((ValueError, rt.RecordTransactionError)):
        owner.validate_record(p, path)
    assert path.read_bytes() == raw
    assert not material['authorization_granted'] and not material['completion_established']


@pytest.mark.parametrize('shape', [
    'request-list', 'phase-list', 'batch-list', 'timestamp-number', 'status-list',
    'kind-list', 'provenance-list', 'origin-list', 'aspects-nested', 'source-path-list',
    'supersedes-id-list', 'predecessor-list', 'predecessor-items-list',
    'review-list', 'review-schema-bool', 'assessment-list', 'citation-list',
    'citation-path-list', 'missing-reviewed-disposition',
])
def test_malformed_material_request_shapes_are_explicit_refusals(world, shape):
    p, q = example(world)
    if shape == 'request-list': q = []
    elif shape == 'phase-list': q['phase'] = []
    elif shape == 'batch-list': q['batch'] = []
    elif shape == 'timestamp-number': q['batch']['captured_at'] = 1
    elif shape == 'status-list': q['items'][0]['status'] = []
    elif shape == 'kind-list': rebind_inventory(p, q, lambda inv: inv['rows'][0].update(kind=[]))
    elif shape == 'provenance-list': rebind_inventory(p, q, lambda inv: inv['rows'][0].update(provenance=[]))
    elif shape == 'origin-list': rebind_inventory(p, q, lambda inv: inv['rows'][0]['provenance'].update(origin=[]))
    elif shape == 'aspects-nested': rebind_inventory(p, q, lambda inv: inv['rows'][0].update(required_aspects=[{}]))
    elif shape == 'source-path-list': rebind_inventory(p, q, lambda inv: inv['rows'][0]['source'].update(path=[]))
    elif shape == 'supersedes-id-list': q['items'][0]['supersedes'] = {'record': {}, 'id': []}
    elif shape.startswith('predecessor'):
        if shape == 'predecessor-list':
            q['batch']['predecessor'] = put(p, 'resources/artifacts/invalid-prior.json', [])
        else:
            committed = apply(world, q)
            prior = json.loads((p / committed['record']).read_text()); prior['items'] = [[]]
            q['batch']['predecessor'] = put(p, 'resources/artifacts/invalid-prior.json', prior)
    else:
        add_review(p, q)
        review = json.loads((p / q['review']['path']).read_text())
        if shape == 'review-list': review = []
        elif shape == 'review-schema-bool': review['schema'] = True
        elif shape == 'assessment-list': review['answers'][0]['assessment'] = []
        elif shape == 'citation-list': review['answers'][0]['source_refs'] = [[]]
        elif shape == 'citation-path-list': review['answers'][0]['source_refs'][0]['path'] = []
        elif shape == 'missing-reviewed-disposition':
            q['items'] = []
            review['dispositions_sha256'] = owner.digest(owner.encoded(q['items']))
        q['review'] = put(p, q['review']['path'], review)
    before = (p / 'CONTEXT.md').read_bytes()
    with pytest.raises(ValueError):
        owner.review(p, q)
    assert (p / 'CONTEXT.md').read_bytes() == before


@pytest.mark.parametrize('condition', ['retired', 'cancelled', 'conflict', 'changed-source', 'changed-review'])
def test_material_terminal_suppression_requires_current_unambiguous_evidence(world, condition):
    import project_format
    p, q = example(world)
    put(p, 'REFERENCE.md', '# Reference\n')
    put(p, 'sessions/2026-09.md', '# Synthetic session\nOPEN: Request the inspection log\n')
    dest = ref(p, 'sessions/2026-09.md', 'Request the inspection log')
    q['items'][0].update(destination=dest, next_action=dest)
    if condition == 'conflict':
        original = apply(world, q)
        for status in ('retired', 'amended'):
            revised = deepcopy(q)
            revised['batch'].update(id='branch-' + status, predecessor=ref(p, original['record']))
            revised['items'][0].update(status=status, next_action=None if status == 'retired' else dest,
                supersedes={'record': ref(p, original['record']), 'id': 'M1'})
            apply(world, revised)
    else:
        q['items'][0].update(status='cancelled' if condition == 'cancelled' else 'retired', next_action=None)
        if condition == 'changed-review': add_review(p, q)
        apply(world, q)
        if condition == 'changed-source':
            source = p / q['inventory']['path']
            source.write_bytes(source.read_bytes() + b'\n')
        elif condition == 'changed-review':
            reviewer = p / 'resources/artifacts/reviewer.md'
            reviewer.write_bytes(reviewer.read_bytes() + b'\n')
    project_format.migrate(p, apply=True)
    path = p / project_format.STATE_NAME
    state = json.loads(path.read_text()); state['open_loops'] = []
    path.write_text(json.dumps(state))
    result = project_format.refresh(p, apply=True)
    loops = json.loads(path.read_text())['open_loops']
    matching = [loop for loop in loops if loop['text'] == 'Request the inspection log']
    uncertain = condition in {'conflict', 'changed-source', 'changed-review'}
    assert bool(matching) == uncertain
    if uncertain:
        assert result['material_context']['record_integrity'] != 'VERIFIED_FOR_DECLARED_INPUTS'
        assert matching[0]['unverified'] is True
    else:
        assert result['material_context']['record_integrity'] == 'VERIFIED_FOR_DECLARED_INPUTS'
    project_format.refresh(p, apply=True)
    assert json.loads(path.read_text())['open_loops'] == loops


@pytest.mark.parametrize('condition', ['current', 'destination-changed', 'enumeration-refused', 'malformed', 'unreachable'])
def test_fresh_material_generation_fences_effect_admission(facade, world, monkeypatch, condition):
    from test_controller import invoke, request, attribute_recovery_fixture
    from test_recovery_capsule import checkpoint
    from test_workflow import _native_process_fixture
    from test_run_state import command
    runtime, state, _ = _native_process_fixture(world, monkeypatch)
    p, q = example(world); committed = apply(world, q)
    state, reference = checkpoint(facade, world, state)
    attribute_recovery_fixture(world)
    response = invoke(facade, world, request('recover',
        {'reconcile_sources': True, 'capsule_ref': reference['event_ref']}, state, 'clear-before-material-drift'))
    assert response['status'] == 'READY'
    state = runtime.load_run(p, state['run_id'])
    if condition == 'destination-changed':
        path = p / q['items'][0]['destination']['path']; path.write_bytes(path.read_bytes() + b'\nChanged interpretation.\n')
    elif condition == 'enumeration-refused': monkeypatch.setattr(owner, 'MAX_ARTIFACT_ENTRIES', 0)
    elif condition == 'malformed': put(p, committed['record'], {'request': []})
    elif condition == 'unreachable': put(p, 'CONTEXT.md', '# Context\n\n## Next work\n')
    payload = {'id': 'next-effect', 'target': 'fixture:target', 'payload_digest': 'a' * 64,
        'idempotency_key': 'material-once', 'authority_ref': ''}
    if condition != 'current':
        with pytest.raises(ValueError, match='recovery external currentness'):
            command(runtime, world, state, 'effect.prepare', payload)
        assert runtime.load_run(p, state['run_id']) == state
    else:
        state = command(runtime, world, state, 'effect.prepare', payload)
        second = {**payload, 'id': 'another-effect', 'idempotency_key': 'another-once'}
        state = command(runtime, world, state, 'effect.prepare', second)
        assert {'next-effect', 'another-effect'} <= set(state['effects'])


@pytest.mark.parametrize('malformed', [[], {'request': []}, {'kind': 'transfer', 'request': {'kind': 'transfer', 'inventory': []}}])
def test_retired_packet_scan_refuses_malformed_succession_shapes(world, malformed):
    import skill_outputs
    p, q = example(world); committed = apply(world, q)
    path = p / committed['record']; raw = json.dumps(malformed).encode(); path.write_bytes(raw)
    page = p / 'resources/artifacts/synthetic-packet.html'
    page.write_text('<!-- synthesis-packet-retired -->')
    findings = skill_outputs.verify_packet(page)
    assert findings and all(finding.severity == 'defect' for finding in findings)
    assert path.read_bytes() == raw
