"""Generation-zero public synthetic examples, exercised against real recorder CLI."""
import copy
import json
import pathlib
import subprocess
import sys

SCRIPTS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import build_packet as bp
import record_rulings as rr


def spec():
    return {
        'title': 'Synthetic release choices', 'audience': 'Fixture principal',
        'options': [{'value': 'test', 'label': 'Test the fixture'},
                    {'value': 'hold', 'label': 'Keep the fixture unchanged'}],
        'rows': [{'id': f'R-{i}', 'label': f'Synthetic target {i}',
                  'context': 'Fixture target, never a real service.',
                  'impact': {'accept': 'Run the fixture test.', 'decline': 'Retain the fixture.'},
                  'recommendation': 'test'} for i in range(5)]}


def record(tmp_path, current_spec, summary):
    target = tmp_path / 'artifacts'
    target.mkdir()
    bp.file_packet(current_spec, bp.build(current_spec), target, '2026-09-24')
    paste = tmp_path / 'paste.txt'
    paste.write_text(summary, encoding='utf-8')
    result = subprocess.run([sys.executable, str(SCRIPTS / 'record_rulings.py'),
                             str(paste), '--file-into', str(target)],
                            capture_output=True, text=True)
    return result, list(target.glob('*-rulings.json'))


def test_legitimate_current_positive_control(tmp_path):
    current = spec()
    result, filed = record(tmp_path, current, rr.compose_summary(current, {'R-0': {'choice': 'test'}}))
    assert result.returncode == 0, result.stderr
    assert len(filed) == 1


def test_changed_option_meaning_cannot_reuse_old_response(tmp_path):
    original = spec()
    summary = rr.compose_summary(original, {'R-0': {'choice': 'test'}})
    changed = copy.deepcopy(original)
    changed['options'][0]['consequence'] = 'Publish to a different synthetic target.'
    result, filed = record(tmp_path, changed, summary)
    assert result.returncode == 2, 'changed spec accepted: ' + result.stdout
    assert not filed


def test_duplicate_rows_cannot_become_a_ruling(tmp_path):
    current = spec()
    summary = rr.compose_summary(current, {'R-0': {'choice': 'test'}})
    summary = summary.replace('R-1  Synthetic target 1', 'R-0  Synthetic target 0')
    result, filed = record(tmp_path, current, summary)
    assert result.returncode == 2, 'duplicate rows accepted: ' + result.stdout
    assert not filed


def test_mismatched_row_label_cannot_become_a_ruling(tmp_path):
    current = spec()
    summary = rr.compose_summary(current, {'R-0': {'choice': 'test'}})
    summary = summary.replace('Synthetic target 0', 'Unpresented target')
    result, filed = record(tmp_path, current, summary)
    assert result.returncode == 2, 'mismatched label accepted: ' + result.stdout
    assert not filed


def test_unknown_option_cannot_become_a_ruling(tmp_path):
    current = spec()
    summary = rr.compose_summary(current, {'R-0': {'choice': 'test'}})
    summary = summary.replace('    -> Test the fixture', '    -> Publish all fixtures')
    result, filed = record(tmp_path, current, summary)
    assert result.returncode == 2, 'unknown option accepted: ' + result.stdout
    assert not filed


def test_pasted_record_never_claims_authenticated_authority(tmp_path):
    current = spec()
    result, filed = record(tmp_path, current, rr.compose_summary(current, {'R-0': {'choice': 'test'}}))
    assert result.returncode == 0, result.stderr
    data = json.loads(filed[0].read_text())
    assert data.get('authorization', {}).get('granted') is False
    assert data.get('authorization', {}).get('authentication') == 'unverified'
