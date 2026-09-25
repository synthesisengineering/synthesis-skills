"""Real PM builder/admission/journal fixtures for the narrow execution proof."""
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'synthesis-autopilot/scripts'))
from test_run_admission import world, write_board, SEAT  # noqa: F401
from test_run_state import engine, create, command  # noqa: F401
import project_state
import execution_checkpoint as checkpoint


def build(world, **overrides):
    values = {'project_id': 'alpha', 'phase': 'Execution', 'status': 'active',
        'controlling_plan': 'plan.md', 'accepted_baseline': 'Fixture baseline',
        'next_actions': ['Verify the declared outcome'], 'last_session': '2026-09-25',
        'session_id': SEAT, 'source_heads': {}}
    values.update(overrides)
    return project_state.build_operational_state(world['project'], **values)


def view(engine, world, state):
    return {**engine.inspect_context(state, world['actor'], project=world['project']),
            'state': state, 'project': world['project'], 'actor': world['actor']}


def capture(engine, world):
    state = create(engine, world)
    state = command(engine, world, state, 'input.materialize', {'id': 'original', 'value': {'schema_version': 1, 'kind': 'fixture'}})
    build(world)
    receipt = checkpoint.observe_execution_basis(view(engine, world, state))
    assert receipt['scope'] == 'EXECUTION_BASIS' and receipt['authority_granted'] is False
    return state, receipt


@pytest.mark.parametrize('limit', ['file-size', 'entry-count', 'receipt-size'])
def test_large_retained_evidence_reaches_actual_checkpoint_consumer(engine, world, limit):
    """D2: actual files and journal consumers, no raised production limits."""
    root = world['project'] / 'resources/evidence/retained'
    root.mkdir(parents=True)
    if limit == 'file-size':
        with (root / 'archive.part-000').open('wb') as stream:
            stream.truncate(40 * 1024 * 1024)
    else:
        count = 20100 if limit == 'entry-count' else 9000
        if limit == 'receipt-size':
            root = root / ('a' * 120) / ('b' * 120) / ('c' * 120)
            root.mkdir(parents=True)
        for number in range(count):
            (root / (f'{number:05d}-' + ('r' * 100 if limit == 'receipt-size' else 'evidence'))).write_bytes(b'x')
    state, receipt = capture(engine, world)
    assert len(json.dumps(receipt).encode()) < 64 * 1024
    assert checkpoint.validate_execution_basis(view(engine, world, state), receipt) == ('EXECUTION_BASIS', [])
    import controller
    controller.register(engine)
    state = command(engine, world, state, 'controller.checkpoint', {'reason': 'Retained evidence scale', 'include_pm': True})
    saved = engine.load_run(world['project'], state['run_id'])
    assert saved == state
    pm = saved['extensions']['controller']['checkpoint']['pm']
    assert checkpoint.validate_execution_basis(view(engine, world, saved), pm) == ('EXECUTION_BASIS', [])
    assert len(engine._json(saved)) < engine.MAX_JSON_BYTES


def test_derived_run_writes_advance_with_real_journal_and_immutable_inputs_verified(engine, world):
    state, receipt = capture(engine, world)
    old_state = (world['project'] / 'CURRENT_STATE.json').read_bytes()
    old_context = (world['project'] / 'CONTEXT.md').read_bytes()
    state = command(engine, world, state, 'transition', {'status': 'running'})
    state = command(engine, world, state, 'input.materialize', {'id': 'later', 'value': {'schema_version': 1, 'kind': 'later-fixture'}})
    assert checkpoint.validate_execution_basis(view(engine, world, state), receipt) == ('EXECUTION_BASIS', [])
    assert (world['project'] / 'CURRENT_STATE.json').read_bytes() == old_state
    assert (world['project'] / 'CONTEXT.md').read_bytes() == old_context
    assert project_state.semantic_issues(world['project'])  # Never claim whole-project cleanliness here.
    assert checkpoint.current_proof(view(engine, world, state), receipt)['scope'] == 'EXECUTION_BASIS'
    assert len(receipt['immutable_inputs']) == 1
    assert 'CURRENT_STATE.json' in receipt['project_files']['records']
    assert not list(world['project'].rglob('*receipt*.json'))


@pytest.mark.parametrize('damage', ['context', 'structured', 'plan-human', 'plan-own-block', 'current-projection',
    'summary-projection', 'missing-projection', 'input-original', 'input-new', 'other-run', 'unregistered-input',
    'ordinary-json', 'symlink-file', 'symlink-directory', 'prefix-journal', 'foreign-claim', 'source-head'])
def test_execution_basis_refuses_current_byte_projection_and_owner_damage(engine, world, damage):
    other = world['project'] / 'resources/autopilot-runs/other-run/retained.json'
    other.parent.mkdir(parents=True)
    other.write_text('{"retained":true}')
    state, receipt = capture(engine, world)
    state = command(engine, world, state, 'transition', {'status': 'running'})
    state = command(engine, world, state, 'input.materialize', {'id': 'later', 'value': {'schema_version': 1, 'kind': 'later-fixture'}})
    context = view(engine, world, state)
    home = engine._home(world['project'], state['run_id'])
    if damage in {'context', 'structured', 'ordinary-json'}:
        path = world['project'] / {'context': 'CONTEXT.md', 'structured': 'CURRENT_STATE.json', 'ordinary-json': 'new.json'}[damage]
        path.write_text(path.read_text() + '\nChanged human material\n' if path.exists() else '{"unreviewed":true}')
    elif damage.startswith('plan'):
        text = world['plan'].read_text()
        world['plan'].write_text(text + 'Human change\n' if damage == 'plan-human' else text.replace('Revision: ', 'Wrong revision: '))
    elif damage.endswith('projection'):
        name = 'current.json' if damage == 'current-projection' else 'summary.md'
        if damage == 'missing-projection':
            (home / name).rename(home / 'displaced-summary.md')
        else:
            (home / name).write_text('Not the journal derivation')
    elif damage.startswith('input-'):
        identity = 'original' if damage == 'input-original' else 'later'
        (world['project'] / state['artifacts'][identity]['path']).write_text('{"different":true}')
    elif damage == 'other-run':
        other.write_text('{"retained":false}')
    elif damage == 'unregistered-input':
        (home / 'inputs' / ('a' * 64 + '.json')).write_text('{"unregistered":true}')
    elif damage.startswith('symlink'):
        target = world['scratch'] / 'external'
        if damage == 'symlink-directory':
            target.mkdir()
        else:
            target.write_text('Foreign bytes')
        (world['project'] / 'redirect').symlink_to(target, target_is_directory=target.is_dir())
    elif damage == 'prefix-journal':
        path = home / 'events/000000000001.json'
        event = json.loads(path.read_text()); event['command_digest'] = 'f' * 64
        path.write_text(json.dumps(event))
    elif damage == 'foreign-claim':
        write_board(world, status='released')
    elif damage == 'source-head':
        # Current PM builder fields cannot be changed after the bound capture.
        adopted = json.loads((world['project'] / 'CURRENT_STATE.json').read_text())
        adopted['source_heads'] = {str(world['repo']): '0' * 40}
        (world['project'] / 'CURRENT_STATE.json').write_text(json.dumps(adopted))
    status, issues = checkpoint.validate_execution_basis(context, receipt)
    assert status == 'FAIL' and issues, (damage, status, issues)


def test_capture_requires_current_builder_and_does_not_refresh_it_silently(engine, world):
    state = create(engine, world)
    build(world)
    state = command(engine, world, state, 'transition', {'status': 'running'})
    before = (world['project'] / 'CURRENT_STATE.json').read_bytes()
    with pytest.raises(ValueError, match='not current'):
        checkpoint.observe_execution_basis(view(engine, world, state))
    assert (world['project'] / 'CURRENT_STATE.json').read_bytes() == before


def test_execution_scope_or_head_cannot_be_substituted(engine, world):
    state, receipt = capture(engine, world)
    for key, value in [('scope', 'LOCAL_READY'), ('authority_granted', True), ('journal_head', {'revision': 1, 'digest': 'f' * 64})]:
        wrong = deepcopy(receipt); wrong[key] = value
        assert checkpoint.validate_execution_basis(view(engine, world, state), wrong)[0] == 'FAIL'


@pytest.mark.parametrize('damage', ['root', 'body', 'count', 'record', 'algorithm', 'partial', 'old-schema'])
def test_compact_receipt_tampering_never_passes_actual_consumer(engine, world, damage):
    state, receipt = capture(engine, world)
    wrong = deepcopy(receipt)
    files = wrong['project_files']
    if damage == 'root': files['sha256'] = 'f' * 64
    elif damage == 'body': files['body']['sha256'] = 'f' * 64
    elif damage == 'count': files['body']['files'] = True
    elif damage == 'record': files['records']['CONTEXT.md'] = 'f' * 64
    elif damage == 'algorithm': files['algorithm'] = 'unqualified-algorithm'
    elif damage == 'partial': del files['body']
    else: wrong['schema_version'] = 1
    assert checkpoint.validate_execution_basis(view(engine, world, state), wrong)[0] == 'FAIL'


@pytest.mark.parametrize('damage', ['changed', 'deleted', 'renamed', 'added'])
def test_compact_membership_binds_every_preserved_file(engine, world, damage):
    retained = world['project'] / 'retained.bin'
    retained.write_bytes(b'original')
    state, receipt = capture(engine, world)
    if damage == 'changed': retained.write_bytes(b'changed!')
    elif damage == 'deleted': retained.unlink()
    elif damage == 'renamed': retained.rename(retained.with_name('renamed.bin'))
    else: retained.with_name('extra.bin').write_bytes(b'original')
    assert checkpoint.validate_execution_basis(view(engine, world, state), receipt)[0] == 'FAIL'


@pytest.mark.parametrize('resource', ['entries', 'bytes', 'time', 'depth'])
def test_inventory_resource_saturation_returns_no_partial_proof(engine, world, monkeypatch, resource):
    state, _ = capture(engine, world)
    context = view(engine, world, state)
    if resource == 'entries': monkeypatch.setattr(checkpoint, 'MAX_SCAN_ENTRIES', 1)
    elif resource == 'bytes': monkeypatch.setattr(checkpoint, 'MAX_SCAN_BYTES', 1)
    elif resource == 'depth': monkeypatch.setattr(checkpoint, 'MAX_SCAN_DEPTH', 0)
    else:
        tick = iter(range(10000))
        monkeypatch.setattr(checkpoint.time, 'monotonic', lambda: next(tick))
        monkeypatch.setattr(checkpoint, 'MAX_SCAN_SECONDS', 0.5)
    before = engine.load_run(world['project'], state['run_id'])
    with pytest.raises(ValueError, match='budget'): checkpoint._inventory(context)
    assert engine.load_run(world['project'], state['run_id']) == before


@pytest.mark.parametrize('damage', ['earlier-file', 'added-member', 'removed-member', 'directory-swap'])
def test_inventory_detects_changes_after_an_earlier_member_was_hashed(engine, world, monkeypatch, damage):
    a, z = world['project'] / 'a-retained', world['project'] / 'z-retained'
    a.write_bytes(b'original'); z.write_bytes(b'last')
    state, _ = capture(engine, world)
    context = view(engine, world, state)
    original = checkpoint._stream_digest
    def change(fd, name, info, budget):
        result = original(fd, name, info, budget)
        if name == z.name:
            if damage == 'earlier-file': a.write_bytes(b'changed!')
            elif damage == 'added-member': (world['project'] / 'a-added').write_bytes(b'new')
            elif damage == 'removed-member': a.unlink()
            else:
                directory = world['project'] / 'resources'
                directory.rename(directory.with_name('displaced'))
                directory.mkdir()
        return result
    monkeypatch.setattr(checkpoint, '_stream_digest', change)
    with pytest.raises((ValueError, OSError)): checkpoint._inventory(context)


@pytest.mark.parametrize('damage', ['growth', 'replacement', 'truncation', 'partial-read', 'symlink', 'mode'])
def test_streaming_file_reader_preserves_race_and_partial_refusals(tmp_path, monkeypatch, damage):
    import os
    path = tmp_path / 'binary'
    path.write_bytes(b'original' * (checkpoint.CHUNK_BYTES // 4))
    actual = os.fdopen
    class ChangingFile:
        def __init__(self, stream): self.stream, self.changed = stream, False
        def __enter__(self): self.stream.__enter__(); return self
        def __exit__(self, *args): return self.stream.__exit__(*args)
        def fileno(self): return self.stream.fileno()
        def read(self, size):
            assert size <= checkpoint.CHUNK_BYTES
            if not self.changed:
                self.changed = True
                if damage == 'growth':
                    with path.open('ab') as stream: stream.write(b'growth')
                elif damage == 'replacement':
                    replacement = path.with_name('replacement'); replacement.write_bytes(path.read_bytes()); replacement.replace(path)
                elif damage == 'truncation':
                    with path.open('wb'): pass
                elif damage == 'symlink':
                    saved = path.with_name('saved'); path.rename(saved); path.symlink_to(saved)
                elif damage == 'mode': path.chmod(0o600 if path.stat().st_mode & 0o777 != 0o600 else 0o644)
                else: return b''
            return self.stream.read(size)
    monkeypatch.setattr(checkpoint.os, 'fdopen', lambda *args, **kwargs: ChangingFile(actual(*args, **kwargs)))
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises((ValueError, OSError)):
            checkpoint._stream_digest(fd, path.name, path.stat(), checkpoint._ScanBudget())
    finally: os.close(fd)


def test_special_file_never_blocks_inventory(engine, world):
    import os
    state, _ = capture(engine, world)
    os.mkfifo(world['project'] / 'named-pipe')
    with pytest.raises(ValueError, match='regular files'):
        checkpoint._inventory(view(engine, world, state))


@pytest.mark.parametrize('size', [0, 1024, 256 * 1024])
def test_execution_read_requests_observed_size_plus_one_not_global_maximum(tmp_path, monkeypatch, size):
    import os
    path = tmp_path / 'bounded-read.bin'
    path.write_bytes(b'x' * size)
    actual = os.fdopen
    requested = []
    class TracedFile:
        def __init__(self, stream): self.stream = stream
        def __enter__(self): self.stream.__enter__(); return self
        def __exit__(self, *args): return self.stream.__exit__(*args)
        def fileno(self): return self.stream.fileno()
        def read(self, count): requested.append(count); return self.stream.read(count)
    monkeypatch.setattr(checkpoint.os, 'fdopen', lambda *args, **kwargs: TracedFile(actual(*args, **kwargs)))
    assert checkpoint._read(path) == b'x' * size
    assert requested == [size + 1]


@pytest.mark.parametrize('damage', ['growth', 'replacement', 'oversized', 'symlink'])
def test_execution_observed_size_bound_preserves_inode_and_growth_refusal(tmp_path, monkeypatch, damage):
    import os
    path = tmp_path / 'bounded-read.bin'
    path.write_bytes(b'initial')
    if damage == 'oversized':
        with path.open('wb') as stream: stream.truncate(checkpoint.MAX_FILE_BYTES + 1)
    elif damage == 'symlink':
        target = tmp_path / 'actual'; path.rename(target); path.symlink_to(target)
    actual = os.fdopen
    class ChangingFile:
        def __init__(self, stream): self.stream = stream
        def __enter__(self): self.stream.__enter__(); return self
        def __exit__(self, *args): return self.stream.__exit__(*args)
        def fileno(self): return self.stream.fileno()
        def read(self, count):
            if damage == 'growth':
                with path.open('ab') as writer: writer.write(b'grew')
            elif damage == 'replacement':
                replacement = path.with_name('replacement'); replacement.write_bytes(b'initial'); replacement.replace(path)
            return self.stream.read(count)
    monkeypatch.setattr(checkpoint.os, 'fdopen', lambda *args, **kwargs: ChangingFile(actual(*args, **kwargs)))
    with pytest.raises(ValueError): checkpoint._read(path)
    assert path.exists()
