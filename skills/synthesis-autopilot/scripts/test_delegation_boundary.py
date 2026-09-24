"""Immutable input roles and real native write-boundary compiler fixtures."""
from __future__ import annotations
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture
def boundary():
    return importlib.import_module('delegation_boundary')


@pytest.fixture
def roles(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    inputs = project / 'inputs'
    inputs.mkdir()
    source = inputs / 'source.txt'
    source.write_text('preserve synthetic source\n')
    outputs = project / 'outputs'
    scratch = project / 'scratch'
    outputs.mkdir()
    scratch.mkdir()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    contract = {'schema_version': 1, 'immutable_inputs': [
        {'artifact_id': 'source', 'path': str(source), 'digest': digest}],
        'output_roots': [str(outputs)], 'scratch_root': str(scratch)}
    context = {'binding': {'project_root': str(project)},
               'artifacts': {'source': {'id': 'source', 'path': 'inputs/source.txt', 'digest': digest}}}
    return contract, context, [str(outputs), str(scratch)]


def test_contract_binds_current_artifacts_and_all_writable_roots(boundary, roles):
    contract, context, paths = roles
    assert boundary.validate_file_contract(contract, context, paths) == contract
    boundary.inspect_files(contract)


@pytest.mark.parametrize('change', ['digest', 'foreign', 'unregistered', 'input_output_overlap',
                                     'scratch_input_overlap', 'relative', 'unknown', 'boolean_version',
                                     'output_scratch_overlap', 'unclaimed_output'])
def test_contract_rejects_role_confusion_or_unbound_input(boundary, roles, change):
    contract, context, paths = roles
    contract = copy.deepcopy(contract)
    if change == 'digest': contract['immutable_inputs'][0]['digest'] = '0' * 64
    if change == 'foreign': contract['immutable_inputs'][0]['path'] = '/foreign/source.txt'
    if change == 'unregistered': context['artifacts'] = {}
    if change == 'input_output_overlap': contract['output_roots'] = [str(Path(contract['immutable_inputs'][0]['path']).parent)]
    if change == 'scratch_input_overlap': contract['scratch_root'] = str(Path(contract['immutable_inputs'][0]['path']).parent)
    if change == 'relative': contract['output_roots'] = ['outputs']
    if change == 'unknown': contract['readonly'] = True
    if change == 'boolean_version': contract['schema_version'] = True
    if change == 'output_scratch_overlap': contract['scratch_root'] = contract['output_roots'][0]
    if change == 'unclaimed_output': paths = [contract['scratch_root']]
    with pytest.raises(ValueError): boundary.validate_file_contract(contract, context, paths)


def test_readonly_worker_has_no_forced_mutable_output(boundary, roles):
    contract, context, paths = roles
    contract['output_roots'] = []
    assert boundary.validate_file_contract(contract, context, paths)['output_roots'] == []


@pytest.mark.parametrize('change', ['drift', 'input_symlink', 'output_symlink', 'parent_symlink',
                                     'output_hardlink', 'unknown_hardlink'])
def test_physical_intake_rejects_aliases_and_stale_bytes(boundary, roles, tmp_path, change):
    contract, context, paths = roles
    source = Path(contract['immutable_inputs'][0]['path'])
    out = Path(contract['output_roots'][0])
    if change == 'drift': source.write_text('changed')
    if change == 'input_symlink':
        source.rename(source.with_suffix('.retained')); source.symlink_to(source.with_suffix('.retained'))
    if change == 'output_symlink':
        out.rmdir(); out.symlink_to(tmp_path, target_is_directory=True)
    if change == 'parent_symlink':
        source.parent.rename(source.parent.with_name('retained')); source.parent.symlink_to(source.parent.with_name('retained'), target_is_directory=True)
    if change == 'output_hardlink': os.link(source, out / 'alias')
    if change == 'unknown_hardlink':
        other = tmp_path / 'other'; other.write_text('preserve foreign input'); os.link(other, out / 'alias')
    with pytest.raises(ValueError): boundary.inspect_files(contract)


def test_effect_readback_reports_input_change_without_repair(boundary, roles):
    contract, _, _ = roles
    before = boundary.inspect_files(contract)
    source = Path(contract['immutable_inputs'][0]['path'])
    source.write_text('observed unauthorized mutation')
    result = boundary.inspect_effects(contract, before)
    assert result['preservation'] == 'FAIL'
    assert result['violations']
    assert source.read_text() == 'observed unauthorized mutation'


def test_effect_readback_rejects_output_symlink_alias(boundary, roles):
    contract, _, _ = roles
    before = boundary.inspect_files(contract)
    (Path(contract['output_roots'][0]) / 'alias').symlink_to(contract['immutable_inputs'][0]['path'])
    assert boundary.inspect_effects(contract, before)['preservation'] == 'FAIL'


def test_worker_prompt_exposes_real_roles_and_resource_envelope(boundary, roles):
    contract, _, _ = roles
    text = boundary.worker_prompt('Produce a recovery note', contract,
        deadline='2026-09-24T12:00:00Z', reservation={'id':'worker','amounts':{'wall_millis':120000, 'usd_micros':2000000}})
    assert '2026-09-24T12:00:00Z' in text
    assert '120000' in text and '2000000' in text
    assert contract['immutable_inputs'][0]['path'] in text
    assert contract['immutable_inputs'][0]['digest'] in text
    assert 'execution logs' in text.lower()


def test_collaboration_does_not_claim_an_enforced_native_boundary(boundary):
    result = boundary.capability('collaboration')
    assert result['write_enforcement'] == 'UNAVAILABLE'
    assert result['reason']
