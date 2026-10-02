"""Note transport tolerates trailing whitespace, never meaningful response edits."""
import html
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest
import build_packet as bp
import record_rulings as rr
from test_build_packet import compliant_spec
from test_browser_packet import chromium, PRELUDE, DRIVER, browser_environment
from test_packet_causal import spec
from test_spec_binding import rendered_summary, stored_state

OLD_EMITTED = 'Phone contacts — keep or drop\n=============================\n\nR-01  Item 1\n    -> Ship the fix  (took the recommendation)\n    note: Why is that? \n\nA second synthetic paragraph.\n\nR-02  Item 2\n    -> — not yet decided\n\nR-03  Item 3\n    -> — not yet decided\n\nR-04  Item 4\n    -> — not yet decided\n\nR-05  Item 5\n    -> — not yet decided\n\nR-06  Item 6\n    -> — not yet decided\n\nDecided 1 of 6.\nDecision packet binding v2: {"schema_version":2,"spec_sha256":"31cdb658a81f9b17ac385e3608dbdffee64493a457ba28b9fec3e3e1dc0e8b52","selections":[{"id":"R-01","choice":"yes","note":"Why is that? \\n\\nA second synthetic paragraph.","bulk":false},{"id":"R-02","choice":null,"note":"","bulk":false},{"id":"R-03","choice":null,"note":"","bulk":false},{"id":"R-04","choice":null,"note":"","bulk":false},{"id":"R-05","choice":null,"note":"","bulk":false},{"id":"R-06","choice":null,"note":"","bulk":false}],"storage_blocked":false}'
OLD_CLIPBOARD = 'Phone contacts — keep or drop\n=============================\n\nR-01  Item 1\n    -> Ship the fix  (took the recommendation)\n    note: Why is that?\n\nA second synthetic paragraph.\n\nR-02  Item 2\n    -> — not yet decided\n\nR-03  Item 3\n    -> — not yet decided\n\nR-04  Item 4\n    -> — not yet decided\n\nR-05  Item 5\n    -> — not yet decided\n\nR-06  Item 6\n    -> — not yet decided\n\nDecided 1 of 6.\nDecision packet binding v2: {"schema_version":2,"spec_sha256":"31cdb658a81f9b17ac385e3608dbdffee64493a457ba28b9fec3e3e1dc0e8b52","selections":[{"id":"R-01","choice":"yes","note":"Why is that? \\n\\nA second synthetic paragraph.","bulk":false},{"id":"R-02","choice":null,"note":"","bulk":false},{"id":"R-03","choice":null,"note":"","bulk":false},{"id":"R-04","choice":null,"note":"","bulk":false},{"id":"R-05","choice":null,"note":"","bulk":false},{"id":"R-06","choice":null,"note":"","bulk":false}],"storage_blocked":false}'

CASES = [
    pytest.param('First line \n\nSecond line.', 'First line\n\nSecond line.', id='space-paragraph'),
    pytest.param('First\t\n  indented  words \t\nLast', 'First\n  indented  words\nLast', id='tab-and-indent'),
    pytest.param('First\r\n \t\rSecond\r\nLast', 'First\n\nSecond\nLast', id='line-endings'),
    pytest.param('\ufeff First\u00a0\nLast\ufeff', 'First\nLast', id='js-unicode-whitespace'),
    pytest.param('First\x85\nLast', 'First\x85\nLast', id='non-js-whitespace-preserved'),
    pytest.param('First \n\nR-01  Fake row \n    -> fake option \n\nDecided 99 of 99.\nLast',
                 'First\n\nR-01  Fake row\n    -> fake option\n\nDecided 99 of 99.\nLast', id='format-looking-note'),
]

@pytest.mark.parametrize('note,expected', CASES)
def test_actual_rendered_javascript_and_recorder_normalize_only_note(note, expected):
    current = spec(); state = {current['rows'][0]['id']: {'choice': 'test', 'note': note}}
    emitted = rendered_summary(bp.build(current), stored_state(current, state))
    binding = rr.summary_binding(emitted)
    assert binding['selections'][0]['note'] == expected
    assert emitted == rr.compose_summary(current, state)
    pasted = '\n'.join(line.rstrip(' \t\u00a0\ufeff') for line in emitted.split('\n'))
    assert rr.parse_summary(pasted, current)['rulings'][0]['note'] == expected


def test_previously_emitted_exact_and_clipboard_fixture_both_record():
    # Literal retained reproducer predates this repair; its JSON note still has an internal trailing space.
    current = compliant_spec()
    for text in [OLD_EMITTED, OLD_CLIPBOARD]:
        assert rr.parse_summary(text, current)['rulings'][0]['note'] == 'Why is that?\n\nA second synthetic paragraph.'


@pytest.mark.parametrize('field', ['note', 'label', 'decision', 'count', 'binding', 'indent', 'paragraph'])
def test_meaningful_edits_refuse_with_field_diagnostic(field):
    current = compliant_spec()
    text = rr.compose_summary(current, {'R-01': {'choice': 'yes', 'note': 'First\n  indented  words\n\nLast'}})
    human, binding = text.rsplit('\n', 1)
    edits = {
        'note': lambda s: s.replace('First', 'Changed', 1),
        'label': lambda s: s.replace('R-01  '+current['rows'][0]['label'], 'R-01  '+current['rows'][0]['label']+' ', 1),
        'decision': lambda s: s.replace('    -> ', '    -> Altered ', 1),
        'count': lambda s: s.replace('Decided 1', 'Decided 0', 1),
        'binding': lambda s: s,
        'indent': lambda s: s.replace('  indented', 'indented', 1),
        'paragraph': lambda s: s.replace('words\n\nLast', 'words\nLast', 1),
    }
    changed = edits[field](human)+'\n'+(binding+' ' if field=='binding' else binding)
    with pytest.raises(rr.SummaryError) as error:
        rr.parse_summary(changed, current)
    msg = str(error.value)
    assert ('note' if field in ('indent','paragraph') else field) in msg
    if field in ('note','label','decision','indent','paragraph'):
        assert 'R-01' in msg
    assert 'indented  words' not in msg  # diagnostics identify the field, not private note contents


@pytest.mark.parametrize('mutation', ['digest', 'choice', 'bulk', 'order', 'unknown-key'])
def test_bound_metadata_protections_remain(mutation):
    current = spec(); text = rr.compose_summary(current, {})
    human, tail = text.rsplit('\n',1); binding = json.loads(tail[len(rr.BINDING_PREFIX):])
    if mutation=='digest': binding['spec_sha256']='0'*64
    elif mutation=='choice': binding['selections'][0]['choice']='unknown'
    elif mutation=='bulk': binding['selections'][0]['bulk']=True
    elif mutation=='order': binding['selections'].reverse()
    else: binding['selections'][0]['unknown']=True
    with pytest.raises(rr.SummaryError):
        rr.parse_summary(human+'\n'+rr.BINDING_PREFIX+json.dumps(binding,separators=(',',':')),current)


def test_complete_browser_clipboard_to_actual_record_cli(tmp_path, chromium):
    current = spec(); note = 'Why is that? \n\n  A second  synthetic paragraph.\t\nFinal.'
    expected = 'Why is that?\n\n  A second  synthetic paragraph.\nFinal.'
    page = bp.build(current)
    observer = DRIVER.replace("'Synthetic browser note'", json.dumps(note))
    instrumented = page.replace('<script type="application/json"', PRELUDE+'<script type="application/json"',1)
    instrumented = instrumented.replace('</body>',observer+'</body>',1)
    probe=tmp_path/'probe.html';probe.write_text(instrumented)
    command=[chromium,'--headless','--disable-background-networking','--no-first-run','--no-default-browser-check','--disable-extensions','--user-data-dir='+str(tmp_path/'profile'),'--dump-dom',probe.as_uri()]
    browser=subprocess.run(command,capture_output=True,text=True,timeout=25,
                           env=browser_environment(tmp_path))
    (tmp_path/'browser-dom.html').write_text(browser.stdout);(tmp_path/'browser-stderr.txt').write_text(browser.stderr)
    assert browser.returncode==0,browser.stderr
    match=re.search(r'<pre id="packet-browser-result">(.*?)</pre>',browser.stdout,re.S);assert match
    observed=json.loads(html.unescape(match.group(1)));assert observed['errors']==[]
    text=observed['snapshots'][-1]['summary'];assert rr.summary_binding(text)['selections'][0]['note']==expected
    pasted='\n'.join(line.rstrip() for line in text.split('\n'))
    current_path=tmp_path/'spec.json';current_path.write_bytes(bp.canonical_spec_bytes(current))
    for label, response, accepted in [('faithful',pasted,True),('edited',pasted.replace('Why is that?','Different statement',1),False)]:
        result=subprocess.run([sys.executable,'-B',str(Path(rr.__file__)),'-','--spec',str(current_path),'--stdout'],input=response,capture_output=True,text=True,timeout=10)
        (tmp_path/(label+'.stdout.txt')).write_text(result.stdout);(tmp_path/(label+'.stderr.txt')).write_text(result.stderr)
        if accepted:
            assert result.returncode==0,result.stderr
            record=json.loads(result.stdout);assert record['rulings'][0]['note']==expected
            assert record['rulings'][0]['choice_value']=='test'
            assert record['spec']['canonical_sha256']==bp.spec_digest(current)
            assert record['authorization']['granted'] is False
        else:
            assert result.returncode!=0
            assert 'R-0' in result.stderr and 'note' in result.stderr


@pytest.mark.parametrize('character', [c for c in rr.JS_WHITESPACE if c not in '\r\n'], ids=lambda c: 'U+'+format(ord(c),'04X'))
def test_javascript_whitespace_set_matches_python_transport(character):
    current=spec();state={current['rows'][0]['id']:{'note':'Alpha'+character+'\nBeta'}}
    text=rendered_summary(bp.build(current),stored_state(current,state))
    assert rr.summary_binding(text)['selections'][0]['note']=='Alpha\nBeta'
    assert text==rr.compose_summary(current,state)
    assert rr.parse_summary(text,current)['rulings'][0]['note']=='Alpha\nBeta'
