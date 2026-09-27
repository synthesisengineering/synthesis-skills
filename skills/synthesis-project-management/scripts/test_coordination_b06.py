"""Causal controls for exact native addressing and bounded snapshot recovery."""

from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json
import pytest
from test_coordination import MODULE as C
import peer_addressing as P
from coordination_schema import identity_from_uuid


def row(index=1, **overrides):
    identity = identity_from_uuid(f"00000000-0000-7000-8000-{index:012d}")
    args = dict(
        session_uuid=identity.session_uuid,
        compact_id=identity.compact_id,
        speakable_id=identity.speakable_id,
        legacy_id="",
        agent="fixture",
        machine="fleet-local",
        client_ref=f"codex:00000000-0000-4000-8000-{index + 10:012d}",
        project=f"project-{index}",
        started=C.timestamp(),
        heartbeat=C.timestamp(),
        mode="interactive",
        workspaces=[],
        goal="fixture",
        claims=[f"/fixture/{index}"],
        context_role="none",
        status="active",
    )
    args.update(overrides)
    return C.Session(**args)


@pytest.mark.parametrize(
    "schema,seat_machine,expected",
    [(1, "fixture-host", True), (2, "fleet-local", True), (2, "fleet-foreign", False)],
)
def test_legacy_hostname_delivery_requires_consistent_local_seat(
    tmp_path, schema, seat_machine, expected
):
    seat = P.Seat(
        "u",
        "s-1",
        P.CLIENT_CLAUDE,
        seat_machine,
        harness_session_id="native",
        schema=schema,
    )
    registry = tmp_path / "registry"
    registry.mkdir()
    (registry / "1.json").write_text(
        json.dumps(
            {"sessionId": "native", "pid": 1, "messagingSocketPath": "/fixture/socket"}
        )
    )
    probes = []
    lanes = P.delivery_lanes(
        client_ref="ccd:local_fixture",
        compact_id="s-1",
        target_machine="fixture-host",
        local_machine="fleet-local",
        local_hostname="fixture-host",
        seat=seat,
        registry=registry,
        alive=lambda p: probes.append(p) or True,
    )
    assert ("ccd" in lanes) == expected
    assert bool(probes) == expected


def test_fleet_label_is_not_a_local_hostname(tmp_path):
    seat = P.Seat(
        "u",
        "s-1",
        P.CLIENT_CLAUDE,
        "foreign",
        machine_label="fixture-host",
        harness_session_id="native",
    )
    lanes = P.delivery_lanes(
        client_ref="ccd:local_fixture",
        compact_id="s-1",
        target_machine="foreign",
        local_machine="local",
        local_hostname="fixture-host",
        seat=seat,
        registry=tmp_path,
    )
    assert set(lanes) == {"bus"}


def test_resolve_reports_registered_muse_and_only_verified_lanes(
    tmp_path, monkeypatch, capsys
):
    board = tmp_path / "board.md"
    r = row(client_ref="muse:native-fixture")
    board.write_text(C.replace_table(C.template(), [r]))
    monkeypatch.setattr(C, "require_fresh_board", lambda _: None)
    args = SimpleNamespace(
        board=board,
        to=r.compact_id,
        include_released=False,
        role=None,
        stale_after_minutes=60,
        json=True,
        no_receipt=True,
        local_machine="fleet-local",
    )
    assert C.command_resolve(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["matches"][0]["client_ref"] == "muse:native-fixture"
    assert "no registered" not in result["matches"][0]["delivery"]
    assert (
        result["matches"][0]["delivery"] == "board message bus; no verified direct lane"
    )


@pytest.mark.parametrize("foreign", [False, True])
def test_resolve_never_promises_unverified_direct_lane(
    tmp_path, monkeypatch, capsys, foreign
):
    board = tmp_path / "board.md"
    r = row(machine="remote" if foreign else "local")
    board.write_text(C.replace_table(C.template(), [r]))
    monkeypatch.setattr(C, "require_fresh_board", lambda _: None)
    args = SimpleNamespace(
        board=board,
        to=r.compact_id,
        include_released=False,
        role=None,
        stale_after_minutes=60,
        json=True,
        no_receipt=True,
        local_machine="local",
    )
    assert C.command_resolve(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert ("codex" in result["matches"][0]["delivery"]) == (not foreign)


@pytest.mark.parametrize(
    "changes,overlap,expected_calls",
    [(1, False, 2), (2, False, 2), (1, True, 2), (0, True, 1)],
)
def test_passive_resnapshot_is_once_and_retains_real_overlap(
    monkeypatch, changes, overlap, expected_calls
):
    own = row()
    peer = row(2, claims=["/fixture/1" if overlap else "/fixture/2"])
    calls = []

    @contextmanager
    def snapshot(self, claims, focus=None):
        calls.append(1)
        yield set(claims)
        if len(calls) <= changes:
            raise C.claim_scope.RegistryAddition("fixture registry changed")

    monkeypatch.setattr(C.claim_scope.ClaimScopeResolver, "snapshot", snapshot)
    issues = C.validate_passive_paths([own, peer], own, [Path("/fixture/1")])
    assert len(calls) == expected_calls
    assert bool(issues) == (changes == 2 or overlap)
    if changes == 2:
        assert "unverifiable" in ";".join(issues)
    if changes == 1 and overlap:
        assert "overlaps" in ";".join(issues)


@pytest.mark.parametrize(
    "client,prefix",
    [(P.CLIENT_CODEX, "codex:"), (P.CLIENT_CLAUDE, "cc:"), (P.CLIENT_MUSE, "muse:")],
)
def test_stop_honor_uses_native_hook_identity_not_ambient_shell(
    monkeypatch, tmp_path, client, prefix
):
    import project_state as S

    native = "00000000-0000-4000-8000-000000000023"
    # Each fixture represents one real harness. Other inherited harness hints
    # must not turn the positive control into a contradictory-client event.
    for key in (
        "SYNTHESIS_HOOK_CLIENT",
        "CODEX_THREAD_ID",
        "CLAUDECODE",
        "CLAUDE_CODE_SESSION_ID",
        "CLAUDE_CODE_HOST_SESSION_ID",
        "MUSE_SESSION_ID",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", prefix + "ambient-other")
    calls = []
    monkeypatch.setattr(C, "honor_open_requests", lambda *a, **k: calls.append((a, k)))
    S._honor_release_requests_at_stop(
        tmp_path / "board.md",
        {"session uuid": row().session_uuid},
        {"session_id": native, "cwd": str(tmp_path)},
    )
    assert len(calls) == 1
    assert calls[0][1]["caller_identity"].harness_session_id == native
    assert calls[0][1]["caller_identity"].client == client


def test_inbox_legacy_alias_collision_never_selects_foreign_honor_row(
    monkeypatch, tmp_path
):
    import board_inbox as I

    own = row(2)
    foreign = row(1)
    own = replace(own, legacy_id=foreign.compact_id)
    board = tmp_path / "board.md"
    board.write_text(
        C.replace_table(C.template(), [foreign, own]) + "\nrelease-request\n"
    )
    identity = P.SelfIdentity(client=P.CLIENT_CODEX, harness_session_id="native")
    seat = P.Seat(
        own.session_uuid,
        own.compact_id,
        P.CLIENT_CODEX,
        "local",
        harness_session_id="native",
    )
    monkeypatch.setattr(I, "identity_from_hook", lambda *_: identity)
    monkeypatch.setattr(I, "seat_for_identity", lambda *_a, **_k: seat)
    monkeypatch.setattr(I, "unread_messages", lambda *_a, **_k: [])
    calls = []
    monkeypatch.setattr(
        C, "honor_open_requests", lambda *a, **k: calls.append((a, k)) or []
    )
    I.inbox_text({}, board=board, refresh_coordination=False)
    assert calls[0][0][1] == own.session_uuid


@pytest.mark.parametrize("changes,expected_error", [(1, False), (2, True)])
def test_broad_project_scope_reobserves_entire_set_once(
    monkeypatch, tmp_path, changes, expected_error
):
    scope = C.claim_scope
    project = tmp_path / "projects" / "one"
    project.mkdir(parents=True)
    claims = [
        (str(project / "CONTEXT.md"), ()),
        (str(tmp_path / "projects" / "two"), ()),
    ]
    calls = []

    @contextmanager
    def snapshot(self, values, focus=None):
        calls.append(list(values))
        yield set(values)
        if len(calls) <= changes:
            raise scope.RegistryAddition("changed fixture registry")

    monkeypatch.setattr(scope.ClaimScopeResolver, "snapshot", snapshot)
    if expected_error:
        with pytest.raises(scope.ClaimIdentityError):
            scope.project_claim_overlaps(project, claims)
    else:
        assert scope.project_claim_overlaps(project, claims) == [True, False]
    assert len(calls) == 2 and calls[0] == calls[1]


def test_claim_then_refusal_never_runs_dependent_command(tmp_path, monkeypatch):
    from test_coordination import claim_args

    board = tmp_path / "board.md"
    r = row(claims=["synthetic:reserved"])
    board.write_text(C.replace_table(C.template(), [r]))
    args = claim_args(
        board,
        session_id="new",
        project="new",
        workspace="/fixture @ main",
        area="synthetic:reserved",
        context_role="none",
    )
    args.then = ["unexpected"]
    args.then_cwd = tmp_path
    args.then_timeout = 60
    import coordination_process

    monkeypatch.setattr(
        coordination_process,
        "run",
        lambda *_a, **_k: pytest.fail("effect after failed claim"),
    )
    assert C.command_claim(args) != 0


def test_claim_then_success_uses_owned_claim_and_propagates_failure(
    tmp_path, monkeypatch
):
    from test_coordination import claim_args
    import sys

    board = tmp_path / "board.md"
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:fixture-native")
    args = claim_args(
        board,
        session_id="new",
        project="new",
        workspace=f"{tmp_path} @ main",
        area=str(tmp_path / "owned"),
        context_role="none",
    )
    args.then = [
        sys.executable,
        "-c",
        'from pathlib import Path;Path("effect").write_text("done");raise SystemExit(7)',
    ]
    (tmp_path / "owned").mkdir()
    args.then_cwd = tmp_path / "owned"
    args.then_timeout = 60
    assert C.command_claim(args) == 7
    assert (tmp_path / "owned" / "effect").read_text() == "done"
    assert C.rows(board.read_text())[0].status == "active"


def test_non_registry_identity_error_never_retries(monkeypatch):
    calls = []

    @contextmanager
    def snapshot(*_a, **_k):
        calls.append(1)
        raise C.claim_scope.ClaimIdentityError("configuration changed")
        yield

    monkeypatch.setattr(C.claim_scope.ClaimScopeResolver, "snapshot", snapshot)
    with pytest.raises(C.claim_scope.ClaimIdentityError, match="configuration changed"):
        C.validate_passive_paths([row()], row(), [Path("/fixture/1")])
    assert calls == [1]


def test_real_registered_worktree_addition_reobserves_whole_batch(
    tmp_path, monkeypatch
):
    from test_claim_scope_cache import git

    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(
        root,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "--allow-empty",
        "-m",
        "Fixture",
    )
    sibling = tmp_path / "sibling"
    git(root, "worktree", "add", "-b", "sibling", str(sibling))
    project = root / "projects" / "one"
    project.mkdir(parents=True)
    (sibling / "projects" / "one").mkdir(parents=True)
    scope = C.claim_scope
    real = scope.ClaimScopeResolver.conflicts
    changes = []
    snapshots = []
    original_snapshot = scope.ClaimScopeResolver.snapshot

    @contextmanager
    def snapshot(self, *a, **k):
        snapshots.append(1)
        with original_snapshot(self, *a, **k) as result:
            yield result

    def add(self, *a, **k):
        result = real(self, *a, **k)
        if not changes:
            changes.append(1)
            git(root, "worktree", "add", "-b", "newpeer", str(tmp_path / "newpeer"))
        return result

    monkeypatch.setattr(scope.ClaimScopeResolver, "snapshot", snapshot)
    monkeypatch.setattr(scope.ClaimScopeResolver, "conflicts", add)
    assert scope.project_claim_overlaps(
        project, [(str(sibling / "projects" / "one" / "CONTEXT.md"), ())]
    ) == [True]
    assert len(snapshots) == 2 and changes == [1]


def test_registry_retry_class_does_not_accept_removal_replacement_or_config():
    scope = C.claim_scope
    import stat

    directory = stat.S_IFDIR | 0o755
    regular = stat.S_IFREG | 0o644
    marker = (1, 2, regular, 4, 5, b"fixture")
    entry = ("old", (1, 3, directory), marker, marker, None)
    registry = (1, 2, directory, 4, 5, None)
    base = ((1, 2, directory), marker, None, registry, (entry,))
    addition = (
        base[0],
        base[1],
        None,
        (1, 2, directory, 8, 9, None),
        (entry, ("new", (1, 7, directory), marker, marker, None)),
    )
    assert scope._registry_addition(base, addition)
    assert not scope._registry_addition(addition, base)
    assert not scope._registry_addition(
        base, (base[0], (1, 2, 3, 4, 99, b"changed"), None, addition[3], addition[4])
    )
    assert not scope._registry_addition(
        base, (base[0], base[1], None, (1, 8, 3, 8, 9, None), addition[4])
    )
    replaced = ("old", (1, 99, 4), marker, marker, None)
    assert not scope._registry_addition(
        base, (*addition[:4], (replaced, addition[4][1]))
    )


@pytest.mark.parametrize("argv", [[], [""], ["a\0b"], "bad", [7]])
def test_invalid_dependent_argv_refuses_before_claim(tmp_path, monkeypatch, argv):
    from test_coordination import claim_args

    board = tmp_path / "board.md"
    args = claim_args(
        board,
        session_id="new",
        project="one",
        workspace=f"{tmp_path} @ main",
        area=str(tmp_path / "owned"),
        context_role="none",
    )
    args.then = argv
    args.then_cwd = tmp_path
    args.then_timeout = 60
    monkeypatch.setattr(
        C,
        "locked_update",
        lambda *_a, **_k: pytest.fail("invalid argv reached board mutation"),
    )
    assert C.command_claim(args) == 10 and not board.exists()


def test_new_worktree_after_listing_before_discovery_recheck(tmp_path, monkeypatch):
    from test_claim_scope_cache import git

    scope = C.claim_scope
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(
        root,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "--allow-empty",
        "-m",
        "Fixture",
    )
    project = root / "projects" / "one"
    project.mkdir(parents=True)
    sibling = tmp_path / "sibling"
    git(root, "worktree", "add", "-b", "sibling", str(sibling))
    claim = sibling / "projects" / "one" / "CONTEXT.md"
    claim.parent.mkdir(parents=True)
    real = scope.native_git.run
    changed = []

    def execute(command, **kw):
        result = real(command, **kw)
        if "worktree" in command and "list" in command and not changed:
            changed.append(1)
            git(root, "worktree", "add", "-b", "peer", str(tmp_path / "peer"))
        return result

    monkeypatch.setattr(scope.native_git, "run", execute)
    result = scope.project_claim_overlaps(project, [(str(claim), ())])[0]
    assert result is True and changed == [1]


def test_stop_honor_contradictory_native_client_hints_never_releases(
    monkeypatch, tmp_path
):
    import project_state as S

    monkeypatch.setenv("CODEX_THREAD_ID", "codex-fixture")
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "cc:claude-fixture")
    monkeypatch.setattr(
        C,
        "honor_open_requests",
        lambda *a, **k: pytest.fail("contradictory event released a claim"),
    )
    S._honor_release_requests_at_stop(
        tmp_path / "board.md",
        {"session uuid": row().session_uuid},
        {"session_id": "native-event", "cwd": str(tmp_path)},
    )
