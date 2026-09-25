"""Controller recover commits remain visible even after its own lease CAS."""
from copy import deepcopy
from test_controller_leased_readback import leased_world
from test_controller import facade, world, engine, invoke, start_request, state_of, request


def test_recovery_after_manual_refresh_returns_current_owner_context(facade, leased_world):
    import coordination
    import run_state
    w = leased_world
    started = invoke(facade, w, start_request(w))
    state = state_of(w, started)
    assert state['status'] == 'running'
    # The original implementation fails its final start output after commits.
    # A real PM refresh provides the same positive prerequisite on both versions.
    assert coordination.lease_refresh(w['board'])['refreshed']
    inspected = invoke(facade, w, request('next', {'mode': 'inspect'}, state, 'before'))
    assert inspected['status'] == 'READY', inspected['diagnostics']
    before = deepcopy(state)
    result = invoke(facade, w, request('recover', {'reconcile_sources': False}, state, 'recover-specific'))
    after = state_of(w, result)
    saved = after['extensions']['controller']['requests']['recover-specific']['steps']
    assert {'recovery-admit', 'checkpoint', 'recovery-readback'} <= set(saved)
    assert after['revision'] > before['revision']
    for name in ('owner', 'effects', 'profile', 'contract'):
        assert after[name] == before[name]
    assert result['status'] != 'UNRESOLVED', result['diagnostics']
    assert result['coverage']['recovery']['external_currentness'] == 'CURRENT_OWNER_READBACK'
