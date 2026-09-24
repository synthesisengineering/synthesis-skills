"""Bounded parallel observations preserve both native identity bounds."""
from collections import Counter
import threading

import claim_scope
from test_claim_scope_cache import checkouts  # noqa: F401


def test_independent_prefixes_observe_in_parallel_with_isolated_resolvers_at_both_bounds(checkouts, monkeypatch):
    original = claim_scope.ClaimScopeResolver._native_identity
    rendezvous = threading.Barrier(2, timeout=2)
    calls = []
    lock = threading.Lock()
    def observed(self, pattern):
        with lock:
            calls.append((id(self), pattern))
        rendezvous.wait()
        return original(self, pattern)
    monkeypatch.setattr(claim_scope.ClaimScopeResolver, "_native_identity", observed)
    resolver = claim_scope.ClaimScopeResolver()
    claims = [(str(path / "projects" / name), ()) for path, name in zip(checkouts, ("one", "two"))]
    with resolver.snapshot(claims):
        assert not resolver.conflicts(claims[0][0], claims[1][0])
    assert Counter(pattern for _, pattern in calls) == {claim: 2 for claim, _ in claims}
    by_pattern = {pattern: {ident for ident, seen in calls if seen == pattern} for pattern, _ in claims}
    assert all(len(identities) == 1 for identities in by_pattern.values())
    assert len(set.union(*by_pattern.values())) == 2
    assert id(resolver) not in set.union(*by_pattern.values())


def test_snapshot_pair_math_reuses_exact_observed_paths_and_rechecks_on_exit(checkouts, monkeypatch):
    claims = [(str(path / "projects" / name), ()) for path, name in zip(checkouts, ("one", "two"))]
    resolver = claim_scope.ClaimScopeResolver()
    original = resolver._identity_prefix
    calls = []
    def observed(pattern):
        calls.append(pattern)
        return original(pattern)
    monkeypatch.setattr(resolver, "_identity_prefix", observed)
    with resolver.snapshot(claims):
        entry_count = len(calls)
        for _ in range(10):
            assert not resolver.conflicts(claims[0][0], claims[1][0])
        assert len(calls) == entry_count
    assert len(calls) > entry_count
