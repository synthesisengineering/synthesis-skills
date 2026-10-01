"""Independent causal controls; all actors and assets are synthetic."""
import hashlib
import json
from pathlib import Path
import pytest

import team_contract as tc
import coordination as c
from test_p13_record_owners import setup
from test_p13_registry import enroll
import test_run_admission as fixtures
world = fixtures.world

def test_observation_preserves_clean_positive(world):
    declaration, _, _, guard = setup(world)
    result = tc.observed_offboarding(declaration, 'p-one', board=world['board'], repo_guard_root=guard)
    assert result['managed_ready'] is True

def test_pending_scan_stops_at_bound(world, monkeypatch):
    declaration, _, _, guard = setup(world)
    pending = guard / 'pending'
    original = Path.iterdir
    visits = []
    bound = tc.MAX_ITEMS
    def adversarial(path):
        if path != pending:
            yield from original(path)
            return
        for index in range(bound + 2):
            visits.append(index)
            if index == bound + 1:
                raise AssertionError('unbounded read beyond refusal boundary')
            yield pending / (str(index) * 64 + '.json')
    monkeypatch.setattr(Path, 'iterdir', adversarial)
    with pytest.raises(tc.TeamContractError, match='bound|inventory'):
        tc.observed_offboarding(declaration, 'p-one', board=world['board'], repo_guard_root=guard)
    assert len(visits) <= bound + 1

def test_missing_retained_workspace_never_disappears_from_coverage(world):
    declaration, _, _, guard = setup(world)
    rows = c.rows(world['board'].read_text())
    departed = rows[1]
    departed.workspaces.append(str(world['scratch'] / 'missing-retained-repository') + ' @ main')
    with pytest.raises(tc.TeamContractError, match='custody|unavailable|missing'):
        tc.observed_run_effects([departed], board=world['board'])

def test_new_pending_effect_during_journal_read_refuses(world, monkeypatch):
    declaration, _, _, guard = setup(world)
    real = tc.observed_run_effects
    def changed(*args, **kwargs):
        result = real(*args, **kwargs)
        native = 'departed'
        path = guard / 'pending' / (hashlib.sha256(native.encode()).hexdigest() + '.json')
        path.write_text(json.dumps({'session_id': native, 'paths': ['synthetic-retained']}))
        return result
    monkeypatch.setattr(tc, 'observed_run_effects', changed)
    with pytest.raises(tc.TeamContractError, match='changed|effect|inventory'):
        tc.observed_offboarding(declaration, 'p-one', board=world['board'], repo_guard_root=guard)

def test_native_board_change_during_registry_read_refuses(world, monkeypatch):
    enroll(world, 'p-two')
    real = tc.registry_binding
    calls = 0
    def changed(index):
        nonlocal calls
        result = real(index)
        calls += 1
        if calls == 2:
            rows = c.rows(world['board'].read_text())
            rows[0].person = 'p-one'
            world['board'].write_text(c.replace_table(world['board'].read_text(), rows))
        return result
    monkeypatch.setattr(tc, 'registry_binding', changed)
    with pytest.raises(tc.TeamContractError, match='changed|principal|board'):
        tc.require_registry(world['repo'] / 'projects/index.yaml', board=world['board'])

def test_changed_registry_refuses_positive_control(world, monkeypatch):
    enroll(world, 'p-two')
    real = tc.registry_binding
    calls = 0
    def changed(index):
        nonlocal calls
        result = real(index)
        calls += 1
        if calls == 2:
            result = dict(result, index_sha256='f' * 64)
        return result
    monkeypatch.setattr(tc, 'registry_binding', changed)
    with pytest.raises(tc.TeamContractError, match='changed'):
        tc.require_registry(world['repo'] / 'projects/index.yaml', board=world['board'])
