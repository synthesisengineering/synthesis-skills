"""Bounded parallel observations preserve both native identity bounds."""
from collections import Counter
import os
import threading

import pytest

import claim_scope
from test_claim_scope_cache import checkouts  # noqa: F401


def test_plain_cells_preserve_markup_and_glob_grammar_without_regex_for_plain_input(monkeypatch):
    import itertools
    import re
    sub = re.sub
    def previous(value):
        guarded = value.replace("/**", "/\0GLOB\0").replace("**/", "\0GLOB\0/")
        unbolded = sub(r"\*\*(.+?)\*\*", r"\1", guarded)
        return sub(r"`(.+?)`", r"\1", unbolded).replace("\0GLOB\0", "**").strip()
    fragments = ["", "x", " /path/projects/ ", "/**", "**/", "`text`", "**bold**", "*", "\n", "é"]
    for parts in itertools.product(fragments, repeat=3):
        value = "".join(parts)
        assert claim_scope.plain(value) == previous(value)
    calls = []
    def counted(*args, **kwargs):
        calls.append(1)
        return sub(*args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(claim_scope.re, "sub", counted)
        for value in [" native:session ", "/repo/projects/one", "owner", "2026-09-24T01:00:00Z", "single * glob"]:
            assert claim_scope.plain(value) == value.strip()
    assert calls == []


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


def test_snapshot_reuses_only_exact_lexical_properties_within_one_operation(checkouts, monkeypatch):
    claims = [(str(path / "projects" / name), ()) for path, name in zip(checkouts, ("one", "two"))]
    resolver = claim_scope.ClaimScopeResolver()
    original = claim_scope._parts
    calls = []
    def counted(pattern):
        calls.append(pattern)
        return original(pattern)
    monkeypatch.setattr(claim_scope, "_parts", counted)
    previous = 0
    for _ in range(2):
        with resolver.snapshot(claims):
            assert not resolver.conflicts(claims[0][0], claims[1][0])
            first = len(calls)
            assert first > previous  # No property survives another operation.
            for _ in range(10):
                assert not resolver.conflicts(claims[0][0], claims[1][0])
            assert len(calls) == first
            previous = first


def test_registry_phase_brackets_shared_common_directory_without_reducing_native_config_reads(checkouts, monkeypatch):
    claims = [(str(path / "projects" / name), ()) for path, name in zip(checkouts, ("one", "two"))]
    original_stamp = claim_scope.ClaimScopeResolver._registry_stamp
    original_git = claim_scope.native_git.run
    stamps, commands = [], []
    lock = threading.Lock()
    def stamp(self, common):
        with lock:
            stamps.append(common)
        return original_stamp(self, common)
    def git(command, **kwargs):
        with lock:
            commands.append(command)
        return original_git(command, **kwargs)
    monkeypatch.setattr(claim_scope.ClaimScopeResolver, "_registry_stamp", stamp)
    monkeypatch.setattr(claim_scope.native_git, "run", git)
    resolver = claim_scope.ClaimScopeResolver()
    with resolver.snapshot(claims):
        assert not resolver.conflicts(claims[0][0], claims[1][0])
    assert len(stamps) == 4  # One before/after per common directory at each bound.
    assert len(set(stamps)) == 1
    assert sum("rev-parse" in command for command in commands) == 4
    assert sum("config" in command for command in commands) == 8


@pytest.mark.parametrize("mutation", ["replacement", "in-place-aba"])
def test_registry_phase_refuses_mid_phase_mutation_before_exposing_pair_math(checkouts, monkeypatch, mutation):
    root, sibling = checkouts
    claims = [(str(path / "projects" / name), ()) for path, name in zip(checkouts, ("one", "two"))]
    original = claim_scope.ClaimScopeResolver._native_identity
    first_finished = threading.Event()
    config = root / ".git" / "config"
    initial = config.read_bytes()
    changed = False
    def observed(self, pattern):
        nonlocal changed
        if pattern == claims[0][0]:
            try:
                return original(self, pattern)
            finally:
                first_finished.set()
        assert first_finished.wait(2)
        if not changed:
            changed = True
            info = config.stat()
            if mutation == "replacement":
                replacement = config.with_name("config-replacement")
                replacement.write_bytes(initial)
                replacement.replace(config)
            else:
                config.write_bytes(initial + b"\n[fixture]\n value = intermediate\n")
                config.write_bytes(initial)
                os.utime(config, ns=(info.st_atime_ns, info.st_mtime_ns))
            assert config.read_bytes() == initial
        return original(self, pattern)
    monkeypatch.setattr(claim_scope.ClaimScopeResolver, "_native_identity", observed)
    entered = False
    with pytest.raises(claim_scope.ClaimIdentityError, match="snapshot|registry"):
        with claim_scope.ClaimScopeResolver().snapshot(claims):
            entered = True
    assert changed
    assert not entered


def test_per_prefix_configuration_bracket_refuses_real_global_config_aba(checkouts, tmp_path, monkeypatch):
    root, _ = checkouts
    config = tmp_path / "global.conf"
    initial = "[fixture]\n value = initial\n"
    config.write_text(initial)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    original = claim_scope.native_git.run
    reads = 0
    def git(command, **kwargs):
        nonlocal reads
        result = original(command, **kwargs)
        if "config" in command:
            reads += 1
            # The actual native first read sees A and its post-read sees B.
            # Restoring A before the outer snapshot ends must not conceal it.
            config.write_text("[fixture]\n value = intermediate\n" if reads == 1 else initial)
        return result
    monkeypatch.setattr(claim_scope.native_git, "run", git)
    claim = str(root / "projects" / "one")
    resolver = claim_scope.ClaimScopeResolver()
    with pytest.raises(claim_scope.ClaimIdentityError, match="changed during discovery"):
        with resolver.snapshot([(claim, ())]):
            resolver._identity(claim)
    assert reads == 2
    assert config.read_text() == initial
