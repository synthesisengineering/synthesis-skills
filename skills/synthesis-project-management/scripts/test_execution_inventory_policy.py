"""Actual owner controls for typed custody and explicit observation budgets."""
from copy import deepcopy
import os
import socket
import json

import pytest

from test_execution_checkpoint import (checkpoint, world, engine, create, command,
                                       view, build, capture)
from test_controller import facade, invoke, request, start_request, state_of


def policy_value(**limits):
    return {'schema_version': 1, 'kind': 'execution-inventory-policy',
            'limits': {'entries': 10000, 'bytes': 16 * 1024 * 1024,
                       'seconds': 30, 'depth': 128, **limits}}


def materialize(engine, world, **limits):
    state = create(engine, world)
    state = command(engine, world, state, 'input.materialize',
                    {'id': 'inventory-budget', 'value': policy_value(**limits)})
    build(world)
    return state


@pytest.mark.parametrize('kind', ['symlink-file', 'symlink-directory', 'dangling', 'fifo', 'socket'])
def test_retained_special_members_are_bound_without_opening_targets(engine, world, monkeypatch, kind):
    path = world['project'] / 'retained-special'
    outside = world['scratch'] / 'outside'
    connection = None
    if kind == 'fifo': os.mkfifo(path)
    elif kind == 'socket':
        connection = socket.socket(socket.AF_UNIX)
        # The actual socket remains inside the owner fixture; a relative bind
        # avoids platform AF_UNIX address limits on long retained test roots.
        with monkeypatch.context() as local:
            local.chdir(path.parent)
            connection.bind(path.name)
    else:
        if kind == 'symlink-directory': outside.mkdir()
        elif kind == 'symlink-file': outside.write_bytes(b'private target bytes')
        path.symlink_to(outside)
    original = checkpoint._stream_digest
    def forbid(fd, name, info, budget):
        assert name != path.name, 'custody-only member opened as execution input'
        return original(fd, name, info, budget)
    monkeypatch.setattr(checkpoint, '_stream_digest', forbid)
    try:
        state, receipt = capture(engine, world)
        assert receipt['project_files']['body']['custody_only'] == 1
        assert checkpoint.validate_execution_basis(view(engine, world, state), receipt) == ('EXECUTION_BASIS', [])
        if kind == 'symlink-file':
            outside.write_bytes(b'target is outside the execution basis')
            assert checkpoint.validate_execution_basis(view(engine, world, state), receipt) == ('EXECUTION_BASIS', [])
        path.unlink()
        assert checkpoint.validate_execution_basis(view(engine, world, state), receipt)[0] == 'FAIL'
    finally:
        if connection: connection.close()


@pytest.mark.parametrize('damage', ['replace-link', 'replace-fifo', 'late-link', 'late-empty-directory'])
def test_custody_and_directory_mutations_refuse_actual_consumer(engine, world, monkeypatch, damage):
    retained = world['project'] / 'a-special'
    retained.symlink_to('missing-target')
    last = world['project'] / 'z-last'
    last.write_bytes(b'last')
    empty = world['project'] / 'empty-evidence'
    empty.mkdir()
    state, receipt = capture(engine, world)
    context = view(engine, world, state)
    if damage == 'replace-link':
        retained.unlink(); retained.symlink_to('different-target')
    elif damage == 'replace-fifo':
        retained.unlink(); os.mkfifo(retained)
    else:
        original = checkpoint._stream_digest
        def change(fd, name, info, budget):
            digest = original(fd, name, info, budget)
            if name == last.name:
                if damage == 'late-link':
                    retained.unlink(); retained.symlink_to('changed-late')
                else: empty.rmdir()
            return digest
        monkeypatch.setattr(checkpoint, '_stream_digest', change)
    assert checkpoint.validate_execution_basis(context, receipt)[0] == 'FAIL'


@pytest.mark.parametrize('damage', ['add', 'remove', 'mode'])
def test_empty_directory_custody_is_not_omitted(engine, world, damage):
    path = world['project'] / 'empty-evidence'
    path.mkdir()
    state, receipt = capture(engine, world)
    if damage == 'add': (path / 'new-empty').mkdir()
    elif damage == 'remove': path.rmdir()
    else: path.chmod(0o700 if path.stat().st_mode & 0o777 != 0o700 else 0o755)
    assert checkpoint.validate_execution_basis(view(engine, world, state), receipt)[0] == 'FAIL'


def test_current_proof_uses_one_fresh_inventory_not_two(engine, world, monkeypatch):
    state, receipt = capture(engine, world)
    calls = []
    original = checkpoint._inventory
    def counted(*args):
        calls.append(True)
        return original(*args)
    monkeypatch.setattr(checkpoint, '_inventory', counted)
    proof = checkpoint.current_proof(view(engine, world, state), receipt)
    assert proof['scope'] == 'EXECUTION_BASIS' and proof['authority_granted'] is False
    assert len(calls) == 1


def test_explicit_immutable_policy_reaches_checkpoint_owner_and_survives_owned_progress(engine, world, monkeypatch):
    import controller
    controller.register(engine)
    state = materialize(engine, world)
    monkeypatch.setattr(checkpoint, 'MAX_SCAN_ENTRIES', 1)
    with pytest.raises(ValueError, match='budget'):
        checkpoint.observe_execution_basis(view(engine, world, state))
    state = command(engine, world, state, 'controller.checkpoint',
                    {'reason': 'Bounded complete inventory', 'include_pm': True,
                     'inventory_policy_id': 'inventory-budget'})
    receipt = state['extensions']['controller']['checkpoint']['pm']
    assert receipt['inventory_policy']['limits'] == policy_value()['limits']
    assert receipt['inventory_policy']['digest'] == state['artifacts']['inventory-budget']['digest']
    assert checkpoint.validate_execution_basis(view(engine, world, state), receipt) == ('EXECUTION_BASIS', [])
    state = command(engine, world, state, 'transition', {'status': 'running'})
    state = command(engine, world, state, 'controller.checkpoint',
                    {'reason': 'Recovery retains the processing policy without claiming a PM proof', 'include_pm': False})
    assert state['extensions']['controller']['checkpoint']['pm'] is None
    assert state['extensions']['controller']['checkpoint']['inventory_policy_id'] == 'inventory-budget'
    state = command(engine, world, state, 'controller.checkpoint',
                    {'reason': 'Selected immutable policy remains explicit in the journal', 'include_pm': True})
    later = state['extensions']['controller']['checkpoint']['pm']
    assert later['inventory_policy'] == receipt['inventory_policy']
    with pytest.raises(ValueError, match='budget'):
        command(engine, world, state, 'controller.checkpoint',
                {'reason': 'Restore defaults', 'include_pm': True, 'inventory_policy_id': None})


@pytest.mark.parametrize('limits', [{'entries': 0}, {'entries': True}, {'entries': 4000001},
                                  {'bytes': 2**37}, {'seconds': 301}, {'depth': 129},
                                  {'seconds': 0}, {'seconds': 0.5}])
def test_invalid_explicit_budget_cannot_raise_defaults(engine, world, limits):
    state = materialize(engine, world, **limits)
    with pytest.raises(ValueError, match='policy'):
        checkpoint.observe_execution_basis(view(engine, world, state), 'inventory-budget')


@pytest.mark.parametrize('damage', ['limits', 'digest', 'input-id', 'captured-input', 'input-bytes', 'default', 'removed'])
def test_policy_substitution_refuses_actual_consumer(engine, world, damage):
    state = materialize(engine, world)
    receipt = checkpoint.observe_execution_basis(view(engine, world, state), 'inventory-budget')
    reloaded = json.loads(json.dumps(receipt, sort_keys=True))
    assert checkpoint.validate_execution_basis(view(engine, world, state), reloaded) == ('EXECUTION_BASIS', [])
    wrong = deepcopy(receipt)
    if damage == 'limits': wrong['inventory_policy']['limits']['entries'] += 1
    elif damage == 'digest': wrong['inventory_policy']['digest'] = 'f' * 64
    elif damage == 'input-id': wrong['inventory_policy']['input_id'] = 'unregistered'
    elif damage == 'captured-input': wrong['immutable_inputs'].clear()
    elif damage == 'default': wrong['inventory_policy'] = None
    elif damage == 'removed': del wrong['inventory_policy']
    else: (world['project'] / wrong['inventory_policy']['path']).write_bytes(b'{}')
    assert checkpoint.validate_execution_basis(view(engine, world, state), wrong)[0] == 'FAIL'


@pytest.mark.parametrize('dimension', ['entries', 'bytes'])
def test_selected_policy_still_refuses_partial_inventory(engine, world, dimension):
    state = materialize(engine, world, **{dimension: 1})
    with pytest.raises(ValueError, match='budget'):
        checkpoint.observe_execution_basis(view(engine, world, state), 'inventory-budget')


def test_selected_policy_reaches_public_facade_without_bypassing_owner(facade, engine, world, monkeypatch):
    response = invoke(facade, world, start_request(world))
    state = state_of(world, response)
    state = command(engine, world, state, 'input.materialize',
                    {'id': 'inventory-budget', 'value': policy_value()})
    build(world)
    monkeypatch.setattr(checkpoint, 'MAX_SCAN_ENTRIES', 1)
    with pytest.raises(ValueError, match='inventory policy requires'):
        invoke(facade, world, request('checkpoint', {'reason': 'Invalid selection',
            'include_pm': False, 'inventory_policy_id': 'inventory-budget'}, state, 'invalid-selection'))
    assert engine.load_run(world['project'], state['run_id']) == state
    response = invoke(facade, world, request('checkpoint', {'reason': 'Explicit complete inventory',
        'include_pm': True, 'inventory_policy_id': 'inventory-budget'}, state, 'policy-checkpoint'))
    assert response['status'] == 'RECORDED', response
    final = state_of(world, response)
    receipt = final['extensions']['controller']['checkpoint']['pm']
    assert receipt['inventory_policy']['input_id'] == 'inventory-budget'
    assert checkpoint.validate_execution_basis(view(engine, world, final), receipt) == ('EXECUTION_BASIS', [])
