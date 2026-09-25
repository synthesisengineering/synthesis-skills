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
    assert 'CURRENT_STATE.json' in receipt['project_files']
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
