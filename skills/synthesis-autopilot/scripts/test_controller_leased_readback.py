"""Real local Git-leased board; synthetic transcript, no native/provider calls."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest
from test_controller import facade, world, engine, start_request, invoke, request, state_of


@pytest.fixture
def leased_world(world):
    import coordination
    remote = world['scratch'] / 'remote.git'
    subprocess.run(['git', 'init', '--bare', '--quiet', str(remote)], check=True)
    (world['board'].parent / 'lease.json').write_text(json.dumps({'remote': str(remote)}))
    config = coordination.lease_configuration(world['board'])
    original = world['board'].read_text()
    coordination.lease_update(world['board'], config, lambda _: original)
    assert coordination.lease_refresh(world['board'])['refreshed']
    world['lease_config'] = config
    return world


def filesystem_snapshot(world):
    roots = [world['project'], world['board'].parent, world['runtime']]
    return {str(p): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
            for root in roots if root.exists() for p in root.rglob('*') if p.is_file()}


def test_successful_start_and_recovery_return_fresh_owner_readback(facade, leased_world):
    import coordination
    w = leased_world
    started = invoke(facade, w, start_request(w))
    assert started['status'] == 'READY', started['diagnostics']
    state = state_of(w, started)
    before = deepcopy(state)
    recovered = invoke(facade, w, request('recover', {'reconcile_sources': False}, state, 'recover'))
    assert recovered['status'] != 'UNRESOLVED', recovered['diagnostics']
    assert recovered['coverage']['recovery']['external_currentness'] == 'CURRENT_OWNER_READBACK'
    after = state_of(w, recovered)
    for key in ('owner', 'effects', 'contract', 'profile'):
        assert after[key] == before[key]
    for key, value in before['extensions']['workflow']['budget'].items():
        assert after['extensions']['workflow']['budget'][key] == value
    assert coordination._cached_lease_refresh(w['board'], w['lease_config'], 300) is not None
    # Replay consumes no duplicate journal event or resource reservation.
    repeated = invoke(facade, w, request('recover', {'reconcile_sources': False}, state, 'recover'))
    assert repeated['status'] != 'UNRESOLVED'
    assert state_of(w, repeated) == after


def test_inspect_and_stop_refuse_stale_stamp_without_refresh_or_writes(facade, leased_world, monkeypatch):
    import coordination
    import run_state
    w = leased_world
    started = invoke(facade, w, start_request(w))
    state = state_of(w, started)
    coordination._invalidate_lease_stamp(w['board'])
    before = filesystem_snapshot(w)
    def forbidden(*a, **kw):
        raise AssertionError('read-only consumer attempted a coordination refresh')
    monkeypatch.setattr(coordination, 'lease_fetch', forbidden)
    inspected = invoke(facade, w, request('next', {'mode': 'inspect'}, state, 'inspect'))
    assert inspected['status'] == 'UNRESOLVED'
    assert 'snapshot is stale' in inspected['diagnostics'][0]['detail']
    with pytest.raises(ValueError, match='snapshot is stale'):
        run_state._binding(w['project'], state, w['actor'], readonly=True, passive=True)
    assert filesystem_snapshot(w) == before


def test_fresh_manual_pm_status_then_readonly_inspect_is_a_positive_control(facade, leased_world):
    import coordination
    w = leased_world
    started = invoke(facade, w, start_request(w))
    state = state_of(w, started)
    # Reproduce the invalidation directly with the real owner CAS.
    coordination.lease_update(w['board'], w['lease_config'], lambda text: text, require_fence=True)
    assert coordination._cached_lease_refresh(w['board'], w['lease_config'], 300) is None
    assert coordination.lease_refresh(w['board'])['refreshed']
    before = filesystem_snapshot(w)
    inspected = invoke(facade, w, request('next', {'mode': 'inspect'}, state, 'inspect'))
    assert inspected['status'] == 'READY', inspected['diagnostics']
    assert filesystem_snapshot(w) == before


def test_postcommit_remote_loss_reports_retained_revision_and_exact_replay(facade, leased_world, monkeypatch):
    import coordination
    w = leased_world
    started = invoke(facade, w, start_request(w))
    state = state_of(w, started)
    req = request('record', {'kind': 'note', 'summary': 'Retain this committed note'}, state, 'note')
    remote = Path(w['lease_config']['remote'])
    unavailable = remote.with_name('unavailable-remote.git')
    original = facade._Transaction.reconcile_readback
    def unavailable_after_commit(tx):
        if tx.request['request_id'] == 'note' and remote.exists():
            remote.rename(unavailable)
        return original(tx)
    monkeypatch.setattr(facade._Transaction, 'reconcile_readback', unavailable_after_commit)
    failed = invoke(facade, w, req)
    after = state_of(w, failed)
    assert failed['status'] == 'UNRESOLVED'
    assert failed['revision'] == state['revision'] + 1
    assert len(failed['committed_event_ids']) == 1
    assert 'owner readback refresh unavailable' in failed['diagnostics'][0]['detail']
    assert 'committed journal remains retained' in failed['diagnostics'][0]['detail']
    assert not coordination.lease_stamp_path(w['board']).exists()
    assert after['effects'] == state['effects']
    assert after['extensions']['workflow']['budget'] == state['extensions']['workflow']['budget']
    unavailable.rename(remote)
    monkeypatch.setattr(facade._Transaction, 'reconcile_readback', original)
    replay = invoke(facade, w, req)
    assert replay['status'] == 'RECORDED', replay['diagnostics']
    assert state_of(w, replay) == after


def test_postcommit_owner_release_is_not_hidden_by_refresh(facade, leased_world, monkeypatch):
    import coordination
    w = leased_world
    started = invoke(facade, w, start_request(w))
    state = state_of(w, started)
    req = request('record', {'kind': 'note', 'summary': 'Committed before release'}, state, 'release-race')
    original = facade._Transaction.reconcile_readback
    def release_after_commit(tx):
        if tx.request['request_id'] == 'release-race':
            coordination.lease_update(w['board'], w['lease_config'],
                lambda text: text.replace('| owner | active |', '| owner | released |'), require_fence=True)
        return original(tx)
    monkeypatch.setattr(facade._Transaction, 'reconcile_readback', release_after_commit)
    failed = invoke(facade, w, req)
    assert failed['status'] == 'UNRESOLVED'
    assert failed['revision'] == state['revision'] + 1
    assert failed['coverage']['owner_admission'] != 'VERIFIED'
    assert 'native' in failed['diagnostics'][0]['detail']
    after = state_of(w, failed)
    for key in ('owner', 'effects', 'contract', 'profile'):
        assert after[key] == state[key]


def test_readback_closure_does_not_reuse_owner_refresh_after_invalidation(facade, leased_world):
    import coordination
    w = leased_world
    started = invoke(facade, w, start_request(w))
    state = state_of(w, started)
    tx = facade._Transaction(request('record', {'kind': 'note', 'summary': 'Unused'}, state),
        w['project'], w['actor'], w['runtime'], 'synthetic')
    context = tx.context()
    coordination.lease_update(w['board'], w['lease_config'], lambda text: text, require_fence=True)
    before = filesystem_snapshot(w)
    with pytest.raises(ValueError, match='snapshot is stale'):
        context['current_native_invalidation']()
    assert filesystem_snapshot(w) == before


def test_owner_refresh_lock_contention_is_bounded_and_does_not_change_journal(facade, leased_world, monkeypatch):
    import coordination
    import fcntl
    import run_admission
    import time
    w = leased_world
    started = invoke(facade, w, start_request(w))
    state = state_of(w, started)
    before = filesystem_snapshot(w)
    monkeypatch.setattr(coordination, 'LEASE_GIT_TIMEOUT', 0.025)
    with (w['board'].parent / '.active-sessions.lock').open('r+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        start = time.monotonic()
        with pytest.raises(ValueError, match='owner readback refresh unavailable'):
            run_admission.reconcile_readback(w['board'])
        assert time.monotonic() - start < 1
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    assert filesystem_snapshot(w) == before
    assert state_of(w, started) == state


def test_missing_lease_configuration_cannot_fall_back_to_local_admission(facade, leased_world):
    import run_admission
    w = leased_world
    (w['board'].parent / 'lease.json').rename(w['board'].parent / 'held-lease.json')
    with pytest.raises(ValueError, match='lease.json is missing'):
        run_admission.reconcile_readback(w['board'])


@pytest.mark.parametrize('adopted', [False, True])
def test_leased_completion_uses_real_existing_consumers_and_replay(facade, leased_world, monkeypatch, adopted):
    from test_controller import test_terminal_finish_replay_uses_current_acceptance_without_repeating_effects
    test_terminal_finish_replay_uses_current_acceptance_without_repeating_effects(
        facade, leased_world, monkeypatch, adopted)


def test_unretained_fresh_stamp_reports_unavailable_not_current(facade, leased_world, monkeypatch):
    import coordination
    import run_admission
    w = leased_world
    def cannot_write(*args, **kwargs):
        raise OSError('synthetic cache permission failure')
    monkeypatch.setattr(coordination, '_write_lease_stamp', cannot_write)
    with pytest.raises(ValueError, match='fresh PM snapshot could not be retained'):
        run_admission.reconcile_readback(w['board'])
    assert not coordination.lease_stamp_path(w['board']).exists()


def test_passive_native_readback_cannot_request_owner_reconciliation(facade, leased_world):
    import run_state
    w = leased_world
    started = invoke(facade, w, start_request(w))
    state = state_of(w, started)
    before = filesystem_snapshot(w)
    with pytest.raises(ValueError, match='passive Stop readback cannot reconcile'):
        run_state._native_readback(w['project'], state, w['actor'], {}, passive=True, owner_reconcile=True)
    assert filesystem_snapshot(w) == before


def test_owner_reconciliation_cannot_hide_intervening_journal_append(facade, leased_world, monkeypatch):
    import run_admission
    import run_state
    w = leased_world
    started = invoke(facade, w, start_request(w))
    state = state_of(w, started)
    last = list(run_state._events(w['project'], state['run_id']))[-1]
    read = run_state._native_readback(w['project'], state, w['actor'],
        {'revision': state['revision'], 'digest': last['digest'], 'scope': 'full_run'},
        invalidation=True, owner_reconcile=True)
    original = run_admission.reconcile_readback
    def concurrent_append(board):
        updated = run_state.apply_command(w['project'], state['run_id'], 'progress',
            {'summary': 'Concurrent owner event'}, expected_revision=state['revision'],
            command_id='concurrent', actor=w['actor'], runtime_root=w['runtime'])
        assert updated['revision'] == state['revision'] + 1
        return original(board)
    monkeypatch.setattr(run_state, 'reconcile_readback', concurrent_append)
    with pytest.raises(ValueError, match='journal head changed|current authoritative journal state'):
        read()
    assert state_of(w, started)['revision'] == state['revision'] + 1
