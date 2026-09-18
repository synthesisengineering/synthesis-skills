"""Discovery reuse is transaction-local and respects Git administrative changes."""
from pathlib import Path
import subprocess

import pytest

import claim_scope


def git(root, *args):
    return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


@pytest.fixture
def checkouts(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "--allow-empty", "-m", "Fixture")
    sibling = tmp_path / "sibling"
    git(root, "worktree", "add", "-b", "sibling", str(sibling))
    for checkout in (root, sibling):
        for name in ("one", "two", "three"):
            (checkout / "projects" / name).mkdir(parents=True)
    return root, sibling


def test_discovery_reprobes_new_scopes_and_reuses_one_listing_per_configuration(checkouts, monkeypatch):
    root, sibling = checkouts
    original = claim_scope.subprocess.run
    calls = []

    def counting(command, **kwargs):
        calls.append(command)
        return original(command, **kwargs)

    monkeypatch.setattr(claim_scope.subprocess, "run", counting)
    resolver = claim_scope.ClaimScopeResolver()
    for checkout in checkouts:
        for name in ("one", "two", "three"):
            common, discovered = resolver._identity(str(checkout / "projects" / name))
            assert discovered == str(checkout.resolve())
            assert common == str((root / ".git").resolve())
    assert sum("rev-parse" in c for c in calls) == 6
    # Git reports the main checkout's config origin relatively and the linked
    # checkout's absolutely; distinct native provenance gets its own listing.
    assert sum("worktree" in c for c in calls) == 2
    resolver._identity(str(root / "projects" / "one"))
    assert sum("rev-parse" in c for c in calls) == 7
    fresh = claim_scope.ClaimScopeResolver()
    fresh._identity(str(root / "projects" / "one"))
    assert sum("worktree" in c for c in calls) == 4


@pytest.mark.parametrize("repeat_scope", [False, True])
def test_worktree_configuration_change_cannot_reuse_identity(checkouts, tmp_path, repeat_scope):
    root, sibling = checkouts
    replacement = tmp_path / "replacement"
    replacement.mkdir()
    git(root, "config", "extensions.worktreeConfig", "true")
    git(sibling, "config", "--worktree", "core.worktree", str(sibling))
    config = root / ".git" / "worktrees" / "sibling" / "config.worktree"
    resolver = claim_scope.ClaimScopeResolver()
    assert resolver._identity(str(sibling / "projects" / "one"))[1] == str(sibling.resolve())
    # In-place content change leaves the registry directory markers unchanged.
    config.write_text("[core]\n\tworktree = " + str(replacement) + "\n")
    assert git(sibling, "rev-parse", "--show-toplevel").strip() == str(replacement.resolve())
    with pytest.raises(claim_scope.ClaimIdentityError, match="not uniquely registered"):
        resolver._identity(str(sibling / "projects" / ("one" if repeat_scope else "two")))


@pytest.mark.parametrize("configuration", ["worktree-include", "global-include"])
@pytest.mark.parametrize("repeat_scope", [False, True])
def test_invalid_included_configuration_cannot_reuse_identity(checkouts, tmp_path, monkeypatch, configuration, repeat_scope):
    root, sibling = checkouts
    include = tmp_path / "identity.conf"
    include.write_text("[fixture]\n\tvalid = true\n")
    if configuration.startswith("worktree"):
        git(root, "config", "extensions.worktreeConfig", "true")
        git(sibling, "config", "--worktree", "include.path", str(include))
    else:
        global_config = tmp_path / "global.conf"
        global_config.write_text('[includeIf "gitdir:' + str(root / ".git" / "worktrees") + '/"]\n\tpath = ' + str(include) + "\n")
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    resolver = claim_scope.ClaimScopeResolver()
    assert resolver._identity(str(sibling / "projects" / "one"))[1] == str(sibling.resolve())
    include.write_text("[unterminated section\n")
    with pytest.raises(claim_scope.ClaimIdentityError):
        resolver._identity(str(sibling / "projects" / ("one" if repeat_scope else "two")))


def test_effective_configuration_change_invalidates_registration_cache(checkouts, tmp_path, monkeypatch):
    root, sibling = checkouts
    config = tmp_path / "global.conf"
    config.write_text("[fixture]\n\tvalue = one\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    resolver = claim_scope.ClaimScopeResolver()
    resolver._identity(str(root / "projects" / "one"))
    original = claim_scope.subprocess.run
    calls = []
    def counting(command, **kwargs):
        calls.append(command)
        return original(command, **kwargs)
    monkeypatch.setattr(claim_scope.subprocess, "run", counting)
    config.write_text("[fixture]\n\tvalue = two\n")
    resolver._identity(str(root / "projects" / "two"))
    assert sum("worktree" in c for c in calls) == 1


def test_environment_configuration_change_invalidates_registration_cache(checkouts, monkeypatch):
    root, _ = checkouts
    resolver = claim_scope.ClaimScopeResolver()
    resolver._identity(str(root / "projects" / "one"))
    original = claim_scope.subprocess.run
    calls = []
    def counting(command, **kwargs):
        calls.append(command)
        return original(command, **kwargs)
    monkeypatch.setattr(claim_scope.subprocess, "run", counting)
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "fixture.changed")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "yes")
    resolver._identity(str(root / "projects" / "one"))
    assert sum("rev-parse" in c for c in calls) == 1
    assert sum("worktree" in c for c in calls) == 1


def test_configuration_change_during_identity_discovery_refuses(checkouts, tmp_path, monkeypatch):
    root, _ = checkouts
    config = tmp_path / "global.conf"
    config.write_text("[fixture]\n\tvalue = one\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    original = claim_scope.subprocess.run
    def changing(command, **kwargs):
        result = original(command, **kwargs)
        if "rev-parse" in command:
            config.write_text("[fixture]\n\tvalue = two\n")
        return result
    monkeypatch.setattr(claim_scope.subprocess, "run", changing)
    with pytest.raises(claim_scope.ClaimIdentityError, match="changed during discovery"):
        claim_scope.ClaimScopeResolver()._identity(str(root / "projects" / "one"))


def test_bounded_comparison_snapshot_probes_each_scope_at_both_bounds(checkouts, monkeypatch):
    root, sibling = checkouts
    claims = [(str(root / "projects" / "one"), ()), (str(sibling / "projects" / "two"), ())]
    original = claim_scope.subprocess.run
    calls = []
    def counting(command, **kwargs):
        calls.append(command)
        return original(command, **kwargs)
    monkeypatch.setattr(claim_scope.subprocess, "run", counting)
    resolver = claim_scope.ClaimScopeResolver()
    with resolver.snapshot(claims):
        for _ in range(20):
            assert not resolver.conflicts(claims[0][0], claims[1][0])
    assert sum("rev-parse" in c for c in calls) == 4


def test_same_checkout_prefixes_share_a_verified_identity_boundary(checkouts, monkeypatch):
    original = claim_scope.subprocess.run
    calls = []
    def counting(command, **kwargs):
        calls.append(command)
        return original(command, **kwargs)
    monkeypatch.setattr(claim_scope.subprocess, "run", counting)
    claims = [(str(root / "projects" / name), ()) for root in checkouts for name in ("one", "two", "three")]
    resolver = claim_scope.ClaimScopeResolver()
    with resolver.snapshot(claims):
        for path, _ in claims:
            assert resolver._identity(path)[1] in {str(root) for root in checkouts}
    assert sum("rev-parse" in command for command in calls) == 4


def test_nested_marker_in_nonrepresentative_prefix_invalidates_group(checkouts):
    root, _ = checkouts
    one, two = root / "projects/one", root / "projects/two"
    resolver = claim_scope.ClaimScopeResolver()
    with pytest.raises(claim_scope.ClaimIdentityError, match="snapshot"):
        with resolver.snapshot([(str(one), ()), (str(two), ())]):
            git(two, "init", "-b", "nested")


@pytest.mark.parametrize("name,value", [("GIT_CEILING_DIRECTORIES", "projects"), ("GIT_DISCOVERY_ACROSS_FILESYSTEM", "0")])
def test_discovery_environment_keeps_exact_prefix_semantics(checkouts, monkeypatch, name, value):
    root, _ = checkouts
    prefix = root / "projects/one"
    monkeypatch.setenv(name, str(root / value) if value == "projects" else value)
    assert claim_scope.ClaimScopeResolver._identity_prefix(str(prefix)) == str(prefix)
    if name == "GIT_CEILING_DIRECTORIES":
        with pytest.raises(claim_scope.ClaimIdentityError):
            claim_scope.ClaimScopeResolver()._identity(str(prefix))


@pytest.mark.parametrize("mutation", ["worktree-config", "include", "nested", "registration"])
def test_comparison_snapshot_refuses_mid_batch_identity_changes(checkouts, tmp_path, monkeypatch, mutation):
    root, sibling = checkouts
    include = tmp_path / "include.conf"
    include.write_text("[fixture]\n\tvalue = one\n")
    global_config = tmp_path / "global.conf"
    global_config.write_text("[include]\n\tpath = " + str(include) + "\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    git(root, "config", "extensions.worktreeConfig", "true")
    git(sibling, "config", "--worktree", "core.worktree", str(sibling))
    left, right = str(root / "projects" / "one"), str(sibling / "projects" / "two")
    resolver = claim_scope.ClaimScopeResolver()
    with pytest.raises(claim_scope.ClaimIdentityError, match="snapshot"):
        with resolver.snapshot([(left, ()), (right, ())]):
            assert not resolver.conflicts(left, right)
            if mutation == "worktree-config":
                config = root / ".git/worktrees/sibling/config.worktree"
                config.write_text("[core]\n\tworktree = " + str(tmp_path) + "\n")
            elif mutation == "include":
                include.write_text("[fixture]\n\tvalue = two\n")
            elif mutation == "nested":
                git(Path(right), "init", "-b", "main")
            else:
                admin = root / ".git/worktrees/sibling"
                admin.rename(admin.with_name("retained"))
            # Pair math can finish, but its provisional result cannot escape.
            assert not resolver.conflicts(left, right)


def _snapshot_validation_fixture(coordination, checkouts, tmp_path, monkeypatch):
    root, sibling = checkouts
    config = tmp_path / "global.conf"
    config.write_text("[fixture]\n\tvalue = one\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    def session(label, claim):
        return coordination.Session(session_uuid="", compact_id="", speakable_id="", legacy_id=label,
            agent="Codex", machine="fixture", project=label, started="2026-01-01T00:00:00Z",
            heartbeat="2026-01-01T00:00:00Z", mode="active", workspaces=[], goal="fixture",
            claims=[claim], context_role="none", status="active")
    sessions = [session("fixture-a", str(root / "projects" / "one")), session("fixture-b", str(sibling / "projects" / "two"))]
    return sessions, config


def test_board_validation_cannot_swallow_persistent_snapshot_failure(checkouts, tmp_path, monkeypatch):
    # Defect 4 changed the semantics this test pins: a mid-check change that
    # SETTLES is revalidated clean (see the settle test below). Genuinely
    # unstable ground — a change on EVERY attempt — must still report. The
    # mutation therefore toggles to a fresh value per call instead of once.
    import coordination
    sessions, config = _snapshot_validation_fixture(
        coordination, checkouts, tmp_path, monkeypatch)
    original = coordination.claim_scope.ClaimScopeResolver.conflicts
    state = {"calls": 0}
    def changing(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        state["calls"] += 1
        config.write_text(f"[fixture]\n\tvalue = v{state['calls']}\n")
        return result
    monkeypatch.setattr(coordination.claim_scope.ClaimScopeResolver, "conflicts", changing)
    assert any("snapshot" in problem for problem in coordination.validate_sessions(sessions))


def test_board_validation_accepts_settled_mid_check_change(checkouts, tmp_path, monkeypatch):
    # The defect-4 case: a peer write lands mid-validation (attempt 1 trips),
    # the world is then stable, and the retry revalidates clean. A healthy
    # advance must not report as corruption.
    import coordination
    sessions, config = _snapshot_validation_fixture(
        coordination, checkouts, tmp_path, monkeypatch)
    original = coordination.claim_scope.ClaimScopeResolver.conflicts
    state = {"mutated": False}
    def changing_once(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        if not state["mutated"]:
            state["mutated"] = True
            config.write_text("[fixture]\n\tvalue = two\n")
        return result
    monkeypatch.setattr(coordination.claim_scope.ClaimScopeResolver, "conflicts", changing_once)
    assert coordination.validate_sessions(sessions) == []


def test_nested_repository_is_never_absorbed_by_cached_ancestor(checkouts):
    root, _ = checkouts
    resolver = claim_scope.ClaimScopeResolver()
    resolver._identity(str(root / "projects" / "one"))
    nested = root / "projects" / "two"
    git(nested, "init", "-b", "main")
    common, discovered = resolver._identity(str(nested))
    assert discovered == str(nested.resolve())
    assert common == str((nested / ".git").resolve())


def test_registration_removal_invalidates_same_transaction(checkouts):
    root, sibling = checkouts
    resolver = claim_scope.ClaimScopeResolver()
    resolver._identity(str(sibling / "projects" / "one"))
    # Retain all worktree bytes while removing only its administrative identity.
    admin = Path((sibling / ".git").read_text().strip().removeprefix("gitdir: "))
    admin.rename(admin.with_name(admin.name + ".retained"))
    with pytest.raises(claim_scope.ClaimIdentityError):
        resolver._identity(str(sibling / "projects" / "two"))
    assert (sibling / "projects" / "one").is_dir()


def test_new_registered_worktree_refreshes_common_discovery(checkouts, tmp_path):
    root, _ = checkouts
    resolver = claim_scope.ClaimScopeResolver()
    resolver._identity(str(root / "projects" / "one"))
    third = tmp_path / "third"
    git(root, "worktree", "add", "-b", "third", str(third))
    common, _ = resolver._identity(str(third))
    assert str(third.resolve()) in resolver.registered[common]
