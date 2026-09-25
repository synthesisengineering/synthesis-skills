"""Exact production-JavaScript/CLI consumers and synthetic hostile inputs.

These establish packet transport behavior, not native agent or action authority.
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_packet as bp
import record_rulings as rr
from test_packet_causal import spec

SCRIPTS = pathlib.Path(__file__).resolve().parent


def cli(script, *args, text=None):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)],
                          input=text, capture_output=True, text=True)


def rendered_summary(page, stored):
    """Execute the actual generated state loader and summary function in Node.

    DOM slots/localStorage are fixture boundaries. This is not a browser click
    test, native lifecycle event or authenticated principal interaction.
    """
    node = shutil.which("node")
    assert node, "Node is required to exercise generated JavaScript"
    embedded = re.search(r'<script type="application/json" id="spec">(.*?)</script>', page, re.S).group(1)
    script = re.search(r'<script>\s*(.*?)</script>', page, re.S).group(1)
    digest = re.search(r'var SPEC_DIGEST = "([a-f0-9]+)";', script).group(1)
    loader = script[script.index('  var KEY ='):script.index('  // ---- filters')]
    summary = script[script.index('  function renderSummary()'):script.index('  function revealSummary()')]
    executable = "\n".join([
        'const SPEC = ' + embedded + ';',
        'const SPEC_DIGEST = ' + json.dumps(digest) + ';',
        'const storage = ' + json.dumps(stored, ensure_ascii=False) + ';',
        'const localStorage = {getItem: k => storage[k] || null, setItem: (k,v) => {storage[k]=v;}};',
        'const elements = {};',
        'const document = {getElementById: id => elements[id] || (elements[id] = {})};',
        loader, summary, 'renderSummary(); process.stdout.write(elements.summary.value);',
    ])
    run = subprocess.run([node, '-e', executable], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    return run.stdout


def stored_state(s, state):
    key = "decision-packet:" + s.get("storage_key", bp.slugify(s["title"])) + ":" + bp.spec_digest(s)
    return {key: json.dumps(state, ensure_ascii=False)}


def test_exact_cli_build_js_render_paste_record_roundtrip(tmp_path):
    s = spec()
    s['title'] = 'Synthetic 📎 choices __SPEC_JSON__'
    s['rows'][0]['id'] = '__proto__'
    s['rows'][1]['options'] = [{'value': 'local', 'label': 'Keep a local fixture'},
                             {'value': 'none', 'label': 'Remove the synthetic fixture'}]
    s['rows'][1]['recommendation'] = 'local'
    s['rows'][3].pop('recommendation')
    note = '\ufeff Note with a fake block\n\nR-new  Counterfeit row\n    -> fake option\n\nDecided 99 of 99. '
    state = {'__proto__': {'choice': 'test', 'note': note},
             'R-1': {'choice': 'none'}, 'R-2': {'choice': 'test', 'bulk': True},
             'R-3': {'choice': 'hold'}}
    source = tmp_path / 'source.json'
    source.write_text(json.dumps(s), encoding='utf-8')
    artifacts = tmp_path / 'artifacts'
    artifacts.mkdir()
    built = cli('build_packet.py', source, '--strict-reader', '--file-into', artifacts,
                '--date', '2026-09-24')
    assert built.returncode == 0, built.stderr
    filed_spec = next(artifacts.glob('*-spec.json'))
    page = next(artifacts.glob('*.html')).read_text()
    assert filed_spec.read_bytes() == bp.canonical_spec_bytes(s)
    summary = rendered_summary(page, stored_state(s, state))
    assert summary == rr.compose_summary(s, state)
    parsed = rr.parse_summary(summary, s)
    assert [r['choice_value'] for r in parsed['rulings']] == ['test', 'none', 'test', 'hold', None]
    assert parsed['rulings'][0]['note'] == rr.js_trim(note)
    recorded = cli('record_rulings.py', '-', '--spec', filed_spec, '--file-into', artifacts,
                   '--stdout', '--date', '2026-09-24', text=summary)
    assert recorded.returncode == 0, recorded.stderr
    record = json.loads(recorded.stdout)
    assert record['spec']['canonical_sha256'] == hashlib.sha256(filed_spec.read_bytes()).hexdigest()
    assert record['spec']['file_sha256'] == hashlib.sha256(filed_spec.read_bytes()).hexdigest()
    assert record['authorization']['granted'] is False
    assert record['authorization']['authentication'] == 'unverified'
    assert json.loads(next(artifacts.glob('*-rulings.json')).read_text()) == record


def test_changed_meaning_does_not_restore_stored_choices():
    original = spec()
    store = stored_state(original, {'R-0': {'choice': 'test'}})
    assert rr.parse_summary(rendered_summary(bp.build(original), store), original)['decided'] == 1
    changed = copy.deepcopy(original)
    changed['rows'][0]['impact']['accept'] = 'Different fixture outcome.'
    result = rr.parse_summary(rendered_summary(bp.build(changed), store), changed)
    assert result['decided'] == 0


@pytest.mark.parametrize('saved', [[], 'invalid', {'R-0': ['test']},
    {'R-0': {'choice': 'not-an-option', 'bulk': True}},
    {'R-0': {'choice': 'hold', 'bulk': True, 'note': 42}}])
def test_malformed_browser_state_cannot_forge_a_choice(saved):
    s = spec()
    rendered = rendered_summary(bp.build(s), stored_state(s, saved))
    result = rr.parse_summary(rendered, s)
    assert result['decided'] == (1 if isinstance(saved, dict) and isinstance(saved.get('R-0'), dict)
                                and saved['R-0'].get('choice') == 'hold' else 0)
    assert all(not r['accepted_in_bulk'] for r in result['rulings'])


@pytest.mark.parametrize('mutate', [
    lambda s: s['rows'][0].update(context='Different evidence.'),
    lambda s: s['rows'][0].update(label='Different target.'),
    lambda s: s['rows'][0].update(recommendation='hold'),
    lambda s: s['options'][0].update(value='different-value'),
    lambda s: s['options'][0].update(label='Different action.'),
    lambda s: s['options'][0].update(consequence='Different consequence.'),
    lambda s: s.update(scope='Different target and payload.'),
])
def test_every_meaning_change_invalidates_old_response(mutate):
    old = spec()
    paste = rr.compose_summary(old, {'R-0': {'choice': 'test'}})
    changed = copy.deepcopy(old)
    mutate(changed)
    with pytest.raises(rr.SummaryError):
        rr.parse_summary(paste, changed)


@pytest.mark.parametrize('mutate', [
    lambda b: b['selections'][1].update(id='R-0'),
    lambda b: b['selections'].reverse(),
    lambda b: b['selections'].pop(),
    lambda b: b['selections'][0].update(choice='unknown'),
    lambda b: b['selections'][0].update(choice=True),
    lambda b: b['selections'][0].update(bulk='true'),
    lambda b: b['selections'][0].update(choice='hold', bulk=True),
    lambda b: b['selections'][1].update(bulk=True),
    lambda b: b['selections'][0].update(note=['injected']),
    lambda b: b.update(schema_version=True),
    lambda b: b.update(authenticated=True),
])
def test_malformed_binding_refuses_without_output(tmp_path, mutate):
    s = spec()
    paste = rr.compose_summary(s, {'R-0': {'choice': 'test'}})
    human, raw = paste.rsplit(rr.BINDING_PREFIX, 1)
    binding = json.loads(raw)
    mutate(binding)
    altered = human + rr.BINDING_PREFIX + json.dumps(binding, separators=(',', ':'))
    current = tmp_path / 'current.json'
    current.write_text(json.dumps(s))
    result = cli('record_rulings.py', '-', '--spec', current, '--file-into', tmp_path,
                 '--stdout', text=altered)
    assert result.returncode == 2
    assert result.stdout == ''
    assert not list(tmp_path.glob('*-rulings.json'))


@pytest.mark.parametrize('raw', [
    '{"title":"first","title":"last"}', '{"number":NaN}', '{"number":Infinity}',
    '{"outer":{"duplicate":1,"duplicate":2}}', '[]',
])
def test_ambiguous_or_malformed_json_refuses_at_build_cli(tmp_path, raw):
    source = tmp_path / 'input.json'
    source.write_text(raw)
    result = cli('build_packet.py', source, '--file-into', tmp_path)
    assert result.returncode == 2, result.stderr
    assert not list(tmp_path.glob('*.html'))


@pytest.mark.parametrize('mutate', [
    lambda s: s.update(title=42), lambda s: s.update(storage_key=[]),
    lambda s: s['rows'][0].update(label=[]), lambda s: s['rows'][0].update(severity=[]),
    lambda s: s['rows'][0].update(recommendation=[]),
    lambda s: s['options'][0].update(value=[]), lambda s: s['options'][0].update(tone=['ok']),
    lambda s: s['rows'][0].update(links=[{'href': 'javascript:alert(1)', 'label': 'unsafe'}]),
    lambda s: s['rows'][0].update(links=[{'href': 'https://[', 'label': 'bad URL'}]),
    lambda s: s.update(filters=[{'id': 'bad', 'label': 'Bad', 'tags': 'not-list'}]),
    lambda s: s['rows'][0].update(disagreement={'a': 'not-an-object', 'b': 'bad'}),
    lambda s: s.update(number=2**54), lambda s: s.update(extra='\ud800'),
])
def test_bad_spec_shapes_refuse_cleanly(tmp_path, mutate):
    s = spec()
    mutate(s)
    source = tmp_path / 'input.json'
    source.write_text(json.dumps(s))
    result = cli('build_packet.py', source, '--file-into', tmp_path)
    assert result.returncode == 2, result.stderr
    assert 'Traceback' not in result.stderr
    assert not list(tmp_path.glob('*.html'))


def test_duplicate_json_keys_in_binding_are_rejected():
    s = spec()
    text = rr.compose_summary(s, {})
    text = text.replace('"schema_version":2', '"schema_version":1,"schema_version":2')
    with pytest.raises(rr.SummaryError, match='duplicate JSON key'):
        rr.parse_summary(text, s)


def test_revised_specs_and_responses_preserve_history(tmp_path):
    s = spec()
    first_spec, first_page = bp.file_packet(s, bp.build(s), tmp_path, '2026-09-24')
    original = {p: p.read_bytes() for p in (first_spec, first_page)}
    changed = copy.deepcopy(s)
    changed['scope'] = 'A new synthetic payload.'
    next_spec, next_page = bp.file_packet(changed, bp.build(changed), tmp_path, '2026-09-24')
    assert next_spec != first_spec and next_page != first_page
    assert {p: p.read_bytes() for p in original} == original
    assert bp.file_packet(changed, bp.build(changed), tmp_path, '2026-09-24') == (next_spec, next_page)
    # Two current candidates are never resolved by filename age or guessed digest.
    paste = rr.compose_summary(changed, {})
    ambiguous = cli('record_rulings.py', '-', '--file-into', tmp_path, text=paste)
    assert ambiguous.returncode == 2 and 'explicitly' in ambiguous.stderr
    for state in ({}, {'R-0': {'choice': 'test'}}):
        recorded = cli('record_rulings.py', '-', '--spec', next_spec, '--file-into', tmp_path,
                       '--date', '2026-09-24', text=rr.compose_summary(changed, state))
        assert recorded.returncode == 0, recorded.stderr
    records = list(tmp_path.glob('*-rulings.json'))
    assert len(records) == 2
    assert sorted(json.loads(p.read_text())['decided'] for p in records) == [0, 1]
    assert {p: p.read_bytes() for p in original} == original


def test_explicit_html_output_cannot_replace_history_or_follow_a_symlink(tmp_path):
    source = tmp_path / 'source.json'
    s = spec()
    source.write_text(json.dumps(s))
    output = tmp_path / 'reviewed.html'
    first = cli('build_packet.py', source, '-o', output)
    assert first.returncode == 0, first.stderr
    historic = output.read_bytes()
    assert cli('build_packet.py', source, '-o', output).returncode == 0
    s['scope'] = 'Different synthetic operation.'
    source.write_text(json.dumps(s))
    changed = cli('build_packet.py', source, '-o', output, '--stdout')
    assert changed.returncode == 2 and changed.stdout == ''
    assert 'Traceback' not in changed.stderr
    assert output.read_bytes() == historic
    link = tmp_path / 'link.html'
    link.symlink_to(output)
    refused = cli('build_packet.py', source, '-o', link, '--stdout')
    assert refused.returncode == 2 and refused.stdout == ''
    assert output.read_bytes() == historic


def test_missing_spec_refuses_cleanly_without_stdout(tmp_path):
    result = cli('build_packet.py', tmp_path / 'missing.json', '--stdout')
    assert result.returncode == 2 and result.stdout == ''
    assert 'Traceback' not in result.stderr


def test_provenance_is_bound_but_never_authenticates(tmp_path):
    s = spec()
    current = tmp_path / 'current.json'
    current.write_text(json.dumps(s))
    provenance = tmp_path / 'provenance.json'
    data = {'principal': 'synthetic-principal', 'source_ref': 'fixture:message-1',
            'received_at': '2026-09-24T12:00:00Z', 'scope': 'Synthetic fixtures only',
            'authority_ref': 'fixture:grant-1'}
    provenance.write_text(json.dumps(data))
    result = cli('record_rulings.py', '-', '--spec', current, '--provenance', provenance,
                 '--stdout', text=rr.compose_summary(s, {}))
    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert record['provenance']['file_sha256'] == hashlib.sha256(provenance.read_bytes()).hexdigest()
    assert record['provenance']['source_ref'] == data['source_ref']
    assert record['provenance']['status'] == 'claimed-unverified'
    assert record['authorization']['granted'] is False
    data['authenticated'] = True
    provenance.write_text(json.dumps(data))
    bad = cli('record_rulings.py', '-', '--spec', current, '--provenance', provenance,
              '--stdout', text=rr.compose_summary(s, {}))
    assert bad.returncode == 2 and bad.stdout == ''


def test_legacy_history_is_readable_and_not_reinterpreted(tmp_path):
    s = spec()
    old = rr.compose_legacy_summary(s, {'R-0': {'choice': 'test'}})
    legacy_file = tmp_path / 'historic-rulings.json'
    historical = b'{"packet":"Historical record","authority":"original source"}\n'
    legacy_file.write_bytes(historical)
    parsed = rr.parse_summary(old)
    assert parsed['binding']['status'] == 'legacy-unbound'
    read = cli('record_rulings.py', '-', '--legacy-unbound', '--stdout', text=old)
    assert read.returncode == 0
    assert json.loads(read.stdout)['authorization']['granted'] is False
    refused = cli('record_rulings.py', '-', '--file-into', tmp_path, text=old)
    assert refused.returncode == 2
    assert 'Existing user grants remain' in refused.stderr
    assert legacy_file.read_bytes() == historical
    assert list(tmp_path.iterdir()) == [legacy_file]


def test_symlink_output_does_not_modify_target(tmp_path):
    s = spec()
    sentinel = tmp_path / 'sentinel'
    sentinel.write_text('preserve me')
    target = tmp_path / ('2026-09-24-' + bp.slugify(s['title']) + '-spec.json')
    target.symlink_to(sentinel)
    with pytest.raises(ValueError, match='symlink'):
        bp.file_packet(s, bp.build(s), tmp_path, '2026-09-24')
    assert sentinel.read_text() == 'preserve me'
