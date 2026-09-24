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
    claims = [(str(path / "projects/one"), ()) for path in checkouts]
    with resolver.snapshot(claims):
        assert not resolver.conflicts(claims[0][0], claims[1][0])
    assert Counter(pattern for _, pattern in calls) == {claim: 2 for claim, _ in claims}
    by_pattern = {pattern: {ident for ident, seen in calls if seen == pattern} for pattern, _ in claims}
    assert all(len(identities) == 1 for identities in by_pattern.values())
    assert len(set.union(*by_pattern.values())) == 2
    assert id(resolver) not in set.union(*by_pattern.values())

