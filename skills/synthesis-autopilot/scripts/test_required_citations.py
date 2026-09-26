"""Required citation retention exercised through the production CLI and observer."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'synthesis-project-management/scripts'))
from test_run_admission import world  # noqa: F401
from test_autopilot_cli import create, cli
import required_citations as citations


def command(world, state, name, payload, ident=None):
    request = world['scratch'] / 'citation-command.json'
    request.write_text(json.dumps(payload))
    return cli(world, 'command', '--project', str(world['project']), '--run-id', state['run_id'],
        '--name', name, '--payload', str(request), '--expected-revision', str(state['revision']),
        '--command-id', ident or name)


def ready(world, files=()):
    state = create(world)
    output = world['project'] / 'output.txt'; output.write_text('Actual output\n')
    for index, path in enumerate((output, *files)):
        result = command(world, state, 'artifact.register', {'id': 'output' if not index else f'evidence-{index}',
            'path': str(path), 'role': 'output' if not index else 'evidence', 'retention': 'durable', 'required': True}, f'register-{index}')
        assert result.returncode == 0, result.stderr
        state = json.loads(result.stdout)
    for name, payload in [('transition', {'status': 'verifying'}), ('verify', {'criteria': ['accept']})]:
        result = command(world, state, name, payload)
        assert result.returncode == 0, result.stderr
        state = json.loads(result.stdout)
    return state


def close(world, state, status='completed'):
    return command(world, state, 'close', {'status': status, **({'reason': 'Incomplete qualification retained'} if status != 'completed' else {})})


@pytest.mark.parametrize('style', ['absolute', 'relative', 'file-uri', 'angle-spaces', 'reference'])
def test_required_citation_to_registered_durable_file_completes(world, style):
    evidence = world['project'] / 'resources' / 'evidence with spaces.txt'
    evidence.parent.mkdir(exist_ok=True); evidence.write_text('retained acceptance\n')
    from os.path import relpath
    if style == 'absolute': target = str(evidence).replace(' ', '%20')
    elif style == 'relative': target = relpath(evidence, world['plan'].parent).replace(' ', '%20')
    elif style == 'file-uri': target = evidence.as_uri()
    else: target = '<' + str(evidence) + '>'
    text = f'Required acceptance evidence: [report]({target}).\n'
    if style == 'reference': text = f'Required acceptance evidence: [report][retained].\n\n[retained]: {target}\n'
    world['plan'].write_text(world['plan'].read_text() + '\n' + text)
    state = ready(world, [evidence]); result = close(world, state)
    assert result.returncode == 0, result.stderr
    finished = json.loads(result.stdout)
    assert finished['status'] == 'completed'
    assert finished['completion']['required_citation_artifacts']['evidence-1'] == hashlib.sha256(evidence.read_bytes()).hexdigest()


@pytest.mark.parametrize('problem', ['scratch', 'missing', 'unregistered', 'remote', 'broken-syntax'])
def test_required_citation_failure_preserves_revision_and_can_close_incomplete(world, problem):
    path = world['scratch'] / 'scratch.txt'; path.write_text('only copy')
    target = str(path)
    if problem == 'missing': target = str(world['project'] / 'missing.txt')
    if problem == 'unregistered':
        path = world['project'] / 'unregistered.txt'; path.write_text('not registered'); target = str(path)
    if problem == 'remote': target = 'https://example.invalid/report'
    text = f'Required acceptance evidence: [report]({target}).\n'
    if problem == 'broken-syntax': text = 'Required acceptance evidence: [report][undefined].\n'
    world['plan'].write_text(world['plan'].read_text() + '\n' + text)
    state = ready(world); result = close(world, state)
    assert result.returncode != 0
    assert 'UNKNOWN' in result.stderr
    result = close(world, state, 'incomplete')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['status'] == 'incomplete'


def test_required_packet_transitively_refuses_scratch_and_supports_retained_bundle(world):
    packet = world['project'] / 'packet.md'
    scratch = world['scratch'] / 'sole.txt'; scratch.write_text('sole required copy')
    packet.write_text(f'## Required recovery inputs\n\n[script]({scratch})\n')
    world['plan'].write_text(world['plan'].read_text() + f'\nRequired acceptance evidence: [packet]({packet}).\n')
    state = ready(world, [packet]); result = close(world, state)
    assert result.returncode != 0 and 'UNKNOWN' in result.stderr


def test_registered_bundle_and_manifest_are_ordinary_durable_inputs(world):
    # A verified retained bundle is addressed by its actual durable bytes;
    # merely mentioning an archive does not prove an unretained scratch path.
    bundle = world['project'] / 'retained.tar'; bundle.write_bytes(b'fixture retained bundle')
    packet = world['project'] / 'packet.md'
    packet.write_text(f'## Required recovery inputs\n\n[bundle]({bundle})\n\n## Historical discussion\n[old scratch](/tmp/no-authority)\n')
    world['plan'].write_text(world['plan'].read_text() + f'\nRequired acceptance evidence: [packet]({packet}).\n')
    result = close(world, ready(world, [packet, bundle]))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('mutation', ['changed', 'symlink', 'parent-symlink', 'missing'])
def test_registered_citation_tamper_is_not_accepted(world, mutation):
    directory = world['project'] / 'evidence'; directory.mkdir()
    evidence = directory / 'proof.txt'; evidence.write_text('retained proof')
    world['plan'].write_text(world['plan'].read_text() + f'\nRequired acceptance evidence: [proof]({evidence}).\n')
    state = ready(world, [evidence])
    if mutation == 'changed': evidence.write_text('changed proof')
    elif mutation == 'missing': evidence.unlink()
    elif mutation == 'symlink':
        saved = world['scratch'] / 'foreign.txt'; saved.write_text('retained proof')
        evidence.unlink(); evidence.symlink_to(saved)
    else:
        saved = world['scratch'] / 'moved'; directory.rename(saved); directory.symlink_to(saved, target_is_directory=True)
    result = close(world, state)
    assert result.returncode != 0


def test_ordinary_links_fenced_examples_and_comments_do_not_form_obligations(world):
    world['plan'].write_text(world['plan'].read_text() + '\nHistorical [link](/tmp/missing).\n\n```md\nRequired acceptance evidence: [example](/tmp/example)\n```\n<!-- Required evidence: [old](/tmp/old) -->\n')
    result = close(world, ready(world))
    assert result.returncode == 0, result.stderr


def observe(tmp_path, text, records=None):
    plan = tmp_path / 'plan.md'; plan.write_text(text)
    digest = hashlib.sha256(text.rstrip().encode()).hexdigest()
    return citations.observe_required_citations(tmp_path, plan, records or {}, expected_plan_digest=digest)


def test_ambiguous_and_unsupported_declarations_are_unknown(tmp_path):
    for text in ('Required evidence: pending\n', 'Required evidence: [a](path(with).txt)\n',
                 'Required evidence: [a][b]\n\n[b]: one\n[b]: two\n'):
        assert observe(tmp_path, text)['status'] == 'UNKNOWN'


def test_citation_work_limits_refuse_without_mutation(tmp_path, monkeypatch):
    file = tmp_path / 'input.txt'; file.write_text('retained')
    record = {'input': {'path': 'input.txt', 'digest': hashlib.sha256(file.read_bytes()).hexdigest(), 'retention': 'durable'}}
    text = 'Required evidence: [one](input.txt) [two](input.txt)\n'
    monkeypatch.setattr(citations, 'MAX_CITATIONS', 1)
    assert observe(tmp_path, text, record)['status'] == 'UNKNOWN'
    monkeypatch.setattr(citations, 'MAX_CITATIONS', 1024)
    monkeypatch.setattr(citations, 'MAX_BYTES', 5)
    assert observe(tmp_path, text, record)['status'] == 'UNKNOWN'


def test_plan_digest_race_is_unknown(tmp_path):
    plan = tmp_path / 'plan.md'; plan.write_text('changed plan')
    result = citations.observe_required_citations(tmp_path, plan, {}, expected_plan_digest='0' * 64)
    assert result['status'] == 'UNKNOWN'


def test_required_packet_cycle_is_bounded(tmp_path):
    a = tmp_path / 'a.md'; b = tmp_path / 'b.md'
    a.write_text('Required evidence: [b](b.md)\n'); b.write_text('Required evidence: [a](a.md)\n')
    records = {p.stem: {'path': p.name, 'digest': hashlib.sha256(p.read_bytes()).hexdigest(), 'retention': 'durable'} for p in (a,b)}
    result = observe(tmp_path, 'Required evidence: [a](a.md)\n', records)
    assert result['status'] == 'PASS' and result['documents'] == 3


@pytest.mark.parametrize('prefix', ['- ', '* ', '1. ', '**', '## '])
def test_explicit_required_markers_in_lists_and_headings_are_observed(tmp_path, prefix):
    suffix = '**' if prefix == '**' else ''
    text = f'{prefix}Required acceptance evidence{suffix}: [lost](/tmp/lost)\n'
    assert observe(tmp_path, text)['status'] == 'UNKNOWN'


def test_registered_packet_changed_during_observation_is_unknown(tmp_path, monkeypatch):
    packet = tmp_path / 'packet.md'; packet.write_text('No required child evidence.\n')
    digest = hashlib.sha256(packet.read_bytes()).hexdigest()
    read = citations._read
    def mutation(path, remaining):
        if path == packet:
            packet.write_text('Required evidence: [lost](/tmp/lost)\n')
        return read(path, remaining)
    monkeypatch.setattr(citations, '_read', mutation)
    result = observe(tmp_path, 'Required evidence: [packet](packet.md)\n',
        {'packet': {'path': 'packet.md', 'digest': digest, 'retention': 'durable'}})
    assert result['status'] == 'UNKNOWN'
    assert 'changed' in result['issues'][0]


def test_maximum_document_count_refuses_a_finite_chain(tmp_path, monkeypatch):
    a = tmp_path / 'a.md'; a.write_text('Required evidence: [next](b.md)\n')
    b = tmp_path / 'b.md'; b.write_text('retained end')
    records = {p.stem: {'path': p.name, 'digest': hashlib.sha256(p.read_bytes()).hexdigest(), 'retention': 'durable'} for p in (a,b)}
    monkeypatch.setattr(citations, 'MAX_DOCUMENTS', 2)
    result = observe(tmp_path, 'Required evidence: [a](a.md)\n', records)
    assert result['status'] == 'UNKNOWN' and 'document-count' in result['issues'][0]


def test_completion_report_observes_citations_without_mutation(world):
    world['plan'].write_text(world['plan'].read_text() + '\nRequired evidence: [lost](/tmp/lost)\n')
    state = ready(world)
    import autopilot
    engine = autopilot.engine()
    before = engine.load_run(world['project'], state['run_id'])
    report = engine.completion_report(world['project'], state['run_id'], actor=world['actor'])
    assert report['status'] == 'FAIL' and any('UNKNOWN' in issue for issue in report['issues'])
    assert engine.load_run(world['project'], state['run_id']) == before


def test_plan_digest_keeps_exact_generated_region_normalization():
    import re
    samples = ['plain\n', 'before\n<!-- autopilot:abc:start -->\ntext\n<!-- autopilot:abc:end -->\nafter\n',
        '<!-- autopilot:abc:start -->\nmissing end\n',
        '\n<!-- autopilot:abc:start -->\none\n<!-- autopilot:def:start -->\ntwo\n<!-- autopilot:abc:end -->\nthree\n']
    for text in samples:
        prior = re.sub(r'\n?<!-- autopilot:[0-9a-f-]+:start -->\n.*?<!-- autopilot:[0-9a-f-]+:end -->\n?', '', text, flags=re.S)
        assert citations.plan_text_digest(text) == hashlib.sha256(prior.rstrip().encode()).hexdigest()


def test_malformed_large_markup_is_bounded_in_an_isolated_process():
    import subprocess
    code = "import required_citations as c; t='Required evidence: '+ '['*200000;\ntry: c._declarations(t)\nexcept ValueError: pass\nassert c._without_comments('<!--'*200000)==''; assert c._body('<!-- autopilot:abc:start -->\\n'*50000)"
    result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).parent,
        env={**__import__('os').environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2] / 'synthesis-project-management/scripts')},
        capture_output=True, text=True, timeout=3)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('form', [
    '__Required evidence:__ {link}',
    '## Required evidence ##\n{link}',
    '## __Required evidence__ ##\n{link}',
])
@pytest.mark.parametrize('retained', [False, True])
def test_markdown_marker_formatting_keeps_required_citation_obligation(world, form, retained):
    evidence = world['project'] / 'formatted-proof.txt'
    evidence.write_text('Current durable evidence\n')
    world['plan'].write_text(world['plan'].read_text() + '\n' +
        form.format(link=f'[proof]({evidence})') + '\n')
    state = ready(world, [evidence] if retained else [])
    result = close(world, state)
    if retained:
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)['completion']['required_citation_artifacts'] == {
            'evidence-1': hashlib.sha256(evidence.read_bytes()).hexdigest()}
    else:
        assert result.returncode != 0
        assert 'UNKNOWN' in result.stderr
        incomplete = close(world, state, 'incomplete')
        assert incomplete.returncode == 0, incomplete.stderr


def test_closing_heading_hashes_do_not_turn_historical_prose_into_authority(world):
    world['plan'].write_text(world['plan'].read_text() +
        '\n## Historical required evidence ##\n[old](/tmp/non-authoritative)\n')
    assert close(world, ready(world)).returncode == 0


def test_long_heading_whitespace_is_bounded_without_regex_backtracking():
    import subprocess
    code = "import required_citations as c; assert c._declarations('## Historical'+' '*1000000+'tail') == []; assert c._declarations('## Historical'+' '*1000000+'###') == []"
    result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).parent,
        env={**__import__('os').environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2] / 'synthesis-project-management/scripts')},
        capture_output=True, text=True, timeout=3)
    assert result.returncode == 0, result.stderr


def test_unreferenced_historical_definitions_do_not_create_a_closure_obligation(world):
    world['plan'].write_text(world['plan'].read_text() +
        '\nHistorical [old][history].\n\n[history]: /tmp/old-one\n[history]: /tmp/old-two\n')
    result = close(world, ready(world))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['completion']['required_citation_artifacts'] == {}


def test_conflicting_required_reference_definitions_refuse_actual_closure(world):
    world['plan'].write_text(world['plan'].read_text() +
        '\nRequired evidence: [report][proof]\n\n[proof]: /tmp/one\n[proof]: /tmp/two\n')
    state = ready(world)
    result = close(world, state)
    assert result.returncode != 0 and 'UNKNOWN' in result.stderr
    assert close(world, state, 'incomplete').returncode == 0
