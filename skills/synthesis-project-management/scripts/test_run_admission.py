"""Admission fixtures use real temporary Git, board grammar, and native evidence."""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from board_grammar import V4_COLUMNS
from coordination_schema import identity_from_uuid

SEAT = "01990000-0000-7000-8000-000000000011"
NATIVE = "01990000-0000-7000-8000-000000000022"


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def write_board(world, *, claims=None, workspace=None, status="active", native=NATIVE,
                heartbeat=None, duplicate=False):
    # Ordinary active claims must not silently become advisory when the
    # calendar crosses the production staleness horizon.
    if heartbeat is None:
        heartbeat = datetime.now(timezone.utc).isoformat()
    identity = identity_from_uuid(SEAT)
    values = [SEAT, identity.compact_id, identity.speakable_id, "", "claude", "fixture-machine",
              f"cc:{native}", "alpha", "2026-09-23T12:00:00Z", heartbeat, "interactive",
              workspace or f"{world['repo']} @ main", "fixture", claims or f"{world['project']}/**",
              "owner", status]
    row = "| " + " | ".join(values) + " |\n"
    world["board"].write_text("# Board\nSchema: v4\n\n## Active sessions\n\n| " +
                              " | ".join(V4_COLUMNS) + " |\n|" + "---|" * len(V4_COLUMNS) +
                              "\n" + row + (row if duplicate else "") + "\n## Messages\n\n## Protocol\n")


@pytest.fixture
def world(tmp_path, monkeypatch):
    for name in ("SYNTHESIS_CLIENT_SESSION_REF", "SYNTHESIS_COORDINATION_SESSION",
                 "SYNTHESIS_COORDINATION_BOARD", "SYNTHESIS_COORDINATION_LEASE_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    repo = tmp_path / "repository"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    hooks = tmp_path / "fixture-hooks"
    hooks.mkdir()
    git(repo, "config", "core.hooksPath", str(hooks))
    project = repo / "projects" / "alpha"
    project.mkdir(parents=True)
    (repo / "projects" / "index.yaml").write_text("- id: alpha\n  status: active\n")
    (project / "CONTEXT.md").write_text("# Fixture\nControlling plan: plan.md\n")
    plan = project / "plan.md"
    plan.write_text("# Fixture plan\n\nHuman-owned prose.\n")
    git(repo, "add", "projects")
    git(repo, "commit", "-m", "Fixture")
    claude = tmp_path / "fixture-claude"
    transcript = claude / "projects" / "fixture" / f"{NATIVE}.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(json.dumps({"type": "user", "sessionId": NATIVE}) + "\n")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", f"cc:{NATIVE}")
    board = tmp_path / "board" / "active-sessions.md"
    board.parent.mkdir()
    payload = {"hook_event_name": "Stop", "stop_hook_active": False, "session_id": NATIVE,
               "transcript_path": str(transcript), "cwd": str(repo)}
    result = {"repo": repo, "project": project, "plan": plan, "board": board,
              "actor": {"board": str(board), "native_payload": payload}, "transcript": transcript,
              "runtime": tmp_path / "runtime", "scratch": tmp_path}
    write_board(result)
    return result


def admission(world, paths=None, **kwargs):
    module = importlib.import_module("run_admission")
    return module.admit_paths(world["board"], "alpha", world["project"],
                              paths or [world["plan"]], world["actor"]["native_payload"], **kwargs)


def test_admission_binds_real_native_seat_exact_worktree_and_claim(world):
    proof = admission(world)
    assert proof["session_uuid"] == SEAT
    assert proof["native_ref"] == f"cc:{NATIVE}"
    assert proof["repository"] == str(world["repo"].resolve())
    assert proof["branch"] == "main"
    assert len(proof["claim_hash"]) == 64


def test_native_binding_parses_each_fresh_complete_board_once(world, monkeypatch):
    module = importlib.import_module("run_admission")
    original = module.parse_table_rows
    parsed = []
    def counted(text, **kwargs):
        parsed.append(text)
        return original(text, **kwargs)
    monkeypatch.setattr(module, "parse_table_rows", counted)
    monkeypatch.setattr(module.coordination, "parse_table_rows", counted)
    for count in (1, 2):
        assert module.native_binding(world["board"], world["actor"]["native_payload"], readonly=True)["session_uuid"] == SEAT
        assert len(parsed) == count
    text = world["board"].read_text()
    world["board"].write_text(text.replace("\n## Messages", "\n| malformed foreign row |\n\n## Messages"))
    with pytest.raises(ValueError):
        module.native_binding(world["board"], world["actor"]["native_payload"], readonly=True)
    assert len(parsed) == 3


@pytest.mark.parametrize("change", ["disjoint", "inactive", "wrong_branch", "wrong_native", "duplicate", "registry"])
def test_admission_refuses_location_without_current_exact_authority(world, change):
    if change == "disjoint":
        write_board(world, claims=str(world["project"] / "elsewhere/**"))
    elif change == "inactive":
        write_board(world, status="released")
    elif change == "wrong_branch":
        write_board(world, workspace=f"{world['repo']} @ foreign")
    elif change == "wrong_native":
        write_board(world, native="01990000-0000-7000-8000-000000000099")
    elif change == "duplicate":
        write_board(world, duplicate=True)
    else:
        (world["repo"] / "projects/index.yaml").write_text("- id: other\n  status: active\n")
    with pytest.raises(ValueError):
        admission(world)


def test_segment_glob_does_not_authorize_nested_path(world):
    write_board(world, claims=f"{world['project']}/*")
    with pytest.raises(ValueError):
        admission(world, [world["project"] / "nested/file.md"])
    write_board(world, claims=f"{world['project']}/**")
    assert admission(world, [world["project"] / "nested/file.md"])


def test_native_transcript_spoof_and_symlink_are_rejected(world):
    original = world["transcript"].read_bytes()
    world["transcript"].write_text(json.dumps({"type": "user", "sessionId": SEAT}) + "\n")
    with pytest.raises(ValueError):
        admission(world)
    world["transcript"].write_bytes(original)
    outside = world["scratch"] / "outside"
    outside.mkdir()
    (world["project"] / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        admission(world, [world["project"] / "linked/escaped.md"])


def test_admission_observation_is_single_operation_and_cannot_be_serialized_or_rebound(world):
    from copy import deepcopy
    module = importlib.import_module("run_admission")
    proof = admission(world, readonly=True)
    with module.admission_scope(proof, world["actor"], world["project"]) as token:
        context = {"admission_observation": token, "actor": world["actor"], "project": world["project"], "binding": dict(proof)}
        assert module.read_admission_observation(context) == proof
        assert deepcopy(token) is token
        with pytest.raises(TypeError):
            json.dumps(token)
        changed = deepcopy(context)
        changed["binding"]["claim_hash"] = "invented"
        with pytest.raises(ValueError):
            module.read_admission_observation(changed)
        changed = deepcopy(context)
        changed["actor"]["native_payload"]["session_id"] = "foreign"
        with pytest.raises(ValueError):
            module.read_admission_observation(changed)
    with pytest.raises(ValueError):
        module.read_admission_observation(context)
    with pytest.raises(ValueError):
        with module.admission_scope(proof, world["actor"], world["project"]):
            pass
    with pytest.raises(ValueError):
        with module.admission_scope(dict(proof), world["actor"], world["project"]):
            pass


def test_passive_snapshot_ignores_read_access_time_but_rejects_actual_content_change(world, monkeypatch):
    module = importlib.import_module("run_admission")
    original_stat = Path.stat
    calls = []
    def stat_with_read_atime(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        if path == world["board"]:
            calls.append(1)
            values = list(result)
            values[7] += len(calls)
            return os.stat_result(values)
        return result
    monkeypatch.setattr(Path, "stat", stat_with_read_atime)
    assert module._snapshot(world["board"], readonly=True).startswith("# Board")
    monkeypatch.setattr(Path, "stat", original_stat)
    original_read = Path.read_text
    def read_then_mutate(path, *args, **kwargs):
        result = original_read(path, *args, **kwargs)
        if path == world["board"]:
            path.write_text(result + "\nConcurrent fixture board edit\n")
        return result
    monkeypatch.setattr(Path, "read_text", read_then_mutate)
    with pytest.raises(ValueError, match="changed"):
        module._snapshot(world["board"], readonly=True)


def test_claim_digest_changes_on_revocation_but_not_heartbeat(world):
    first = admission(world)
    write_board(world)
    assert admission(world, expected_claim_hash=first["claim_hash"])["claim_hash"] == first["claim_hash"]
    write_board(world, claims=f"{world['project']}/plan.md")
    with pytest.raises(ValueError):
        admission(world, expected_claim_hash=first["claim_hash"])


def test_linked_worktree_is_not_the_claimed_worktree(world):
    linked = world["scratch"] / "linked-worktree"
    git(world["repo"], "worktree", "add", "-b", "linked", str(linked))
    module = importlib.import_module("run_admission")
    with pytest.raises(ValueError):
        module.admit_paths(world["board"], "alpha", linked / "projects/alpha",
                           [linked / "projects/alpha/plan.md"], world["actor"]["native_payload"])


def test_readonly_admission_never_fetches_or_creates_lock_and_requires_valid_cache(world, monkeypatch):
    module = importlib.import_module("run_admission")
    import coordination
    def forbidden(*args, **kwargs):
        raise AssertionError("passive observation attempted remote mutation")
    monkeypatch.setattr(coordination, "lease_update", forbidden)
    monkeypatch.setattr(coordination, "lease_fetch", forbidden)
    assert admission(world, readonly=True)
    assert not (world["board"].parent / ".active-sessions.lock").exists()
    config_path = world["board"].parent / coordination.LEASE_CONFIG_NAME
    config_path.write_text(json.dumps({"remote": "fixture://remote", "ref": "refs/heads/coordination",
                                       "repository": str(world["scratch"] / "fixture-lease.git")}))
    with pytest.raises(ValueError, match="passive|stale|cache"):
        admission(world, readonly=True)
    config = coordination.lease_configuration(world["board"])
    coordination._write_lease_stamp(world["board"], config, "a" * 40)
    assert admission(world, readonly=True)
    write_board(world)
    with pytest.raises(ValueError):
        admission(world, readonly=True)


def test_overlapping_active_peer_claim_is_not_silently_admitted(world):
    other = identity_from_uuid("01990000-0000-7000-8000-000000000033")
    text = world["board"].read_text()
    own = next(line for line in text.splitlines() if line.startswith(f"| {SEAT} |"))
    first = identity_from_uuid(SEAT)
    peer = own.replace(SEAT, other.session_uuid).replace(first.compact_id, other.compact_id).replace(first.speakable_id, other.speakable_id).replace(NATIVE, "01990000-0000-7000-8000-000000000044")
    world["board"].write_text(text.replace(own, own + "\n" + peer))
    with pytest.raises(ValueError, match="overlap|context"):
        admission(world)


def test_polyrepo_targets_require_each_exact_worktree_branch_and_path_claim(world):
    source = world["scratch"] / "source-repository"
    source.mkdir()
    git(source, "init", "-b", "feature")
    target = source / "module.py"
    target.write_text("fixture = True\n")
    write_board(world, claims=f"{world['project']}/**; {target}",
                workspace=f"{world['repo']} @ main; {source} @ feature")
    proof = admission(world, [world["plan"], target])
    assert proof["target_workspaces"][str(target)]["branch"] == "feature"
    write_board(world, claims=f"{world['project']}/**; {target}",
                workspace=f"{world['repo']} @ main; {source} @ wrong")
    with pytest.raises(ValueError):
        admission(world, [world["plan"], target])
    write_board(world, claims=f"{world['project']}/**; {source}/elsewhere.py",
                workspace=f"{world['repo']} @ main; {source} @ feature")
    with pytest.raises(ValueError):
        admission(world, [world["plan"], target])


def _hold_authority_lock(board, seconds):
    """A separate real flock owner; no shared Python lock mock."""
    script = '''import fcntl,sys,time
from pathlib import Path
board=Path(sys.argv[1])
with (board.parent/'.active-sessions.lock').open('a+') as handle:
 fcntl.flock(handle.fileno(),fcntl.LOCK_EX)
 print('locked',flush=True)
 time.sleep(float(sys.argv[2]))
 board.write_text(board.read_text()+'\\nHolder finished its fenced operation.\\n')
'''
    process = subprocess.Popen([sys.executable, '-c', script, str(board), str(seconds)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert process.stdout.readline().strip() == 'locked'
    return process


def _finish_lock_holder(process):
    if process.poll() is None: process.terminate()
    process.wait(timeout=5)
    process.stdout.close(); process.stderr.close()


def test_mutation_snapshot_waits_for_existing_lease_owner_past_generic_five_seconds(world, monkeypatch):
    import time
    module = importlib.import_module('run_admission')
    config = {'remote': 'fixture-only'}
    monkeypatch.setattr(module.coordination, 'lease_configuration', lambda _: config)
    calls = []
    def fenced(board, received, operation, *, require_fence):
        assert require_fence is True and received == config
        assert 'Holder finished' in board.read_text()
        calls.append(operation(board.read_text()))
    monkeypatch.setattr(module.coordination, 'lease_update', fenced)
    holder = _hold_authority_lock(world['board'], 5.3)
    started = time.monotonic()
    try:
        text = module._snapshot(world['board'])
    finally:
        _finish_lock_holder(holder)
    assert 5.1 <= time.monotonic() - started < 12
    assert calls == [text] and 'Holder finished' in text


def test_mutation_snapshot_uses_two_existing_git_deadlines_as_bounded_queue_budget(world, monkeypatch):
    from contextlib import contextmanager
    module = importlib.import_module('run_admission')
    monkeypatch.setattr(module.coordination, 'LEASE_GIT_TIMEOUT', 2)
    monkeypatch.setattr(module.coordination, 'LEASE_RETRIES', 3)
    received = []
    @contextmanager
    def recorded(path, *, timeout=None):
        received.append((path, timeout)); yield
    monkeypatch.setattr(module, 'bounded_lock', recorded)
    monkeypatch.setattr(module.coordination, 'lease_configuration', lambda _: None)
    module._snapshot(world['board'])
    assert received == [(world['board'].parent / '.active-sessions.lock', 2 * 2)]


def test_snapshot_deadline_still_rejects_live_holder_without_running_lease_or_bypassing_lock(world, monkeypatch):
    import time
    module = importlib.import_module('run_admission')
    original = module.bounded_lock
    # Scale only the wait duration, after proving the production budget arrives.
    def scaled(path, *, timeout=None):
        assert timeout == 2 * module.coordination.LEASE_GIT_TIMEOUT
        return original(path, timeout=.05)
    monkeypatch.setattr(module, 'bounded_lock', scaled)
    monkeypatch.setattr(module.coordination, 'lease_update', lambda *a, **k: pytest.fail('lock deadline must not bypass authority'))
    holder = _hold_authority_lock(world['board'], 10)
    started = time.monotonic()
    try:
        with pytest.raises(module.AdmissionError, match='timed out'):
            module._snapshot(world['board'])
        assert time.monotonic() - started < 1
    finally:
        _finish_lock_holder(holder)


def test_passive_snapshot_remains_nonblocking_while_mutation_owner_holds_lock(world):
    import time
    module = importlib.import_module('run_admission')
    holder = _hold_authority_lock(world['board'], 10)
    started = time.monotonic()
    try:
        assert module._snapshot(world['board'], readonly=True).startswith('# Board')
        assert time.monotonic() - started < 1
    finally:
        _finish_lock_holder(holder)


def passive_inspection(world, paths=None):
    module = importlib.import_module("run_admission")
    return module.inspect_paths(world["board"], "alpha", world["project"],
                                paths or [world["plan"]], world["actor"]["native_payload"])


def add_passive_peer(world, claim, *, number=33, workspace=None, **changes):
    """Real board rows, with no fabricated proof or native callback."""
    from copy import deepcopy
    import coordination
    sessions = coordination.rows(world["board"].read_text())
    peer = deepcopy(next(session for session in sessions if session.session_uuid == SEAT))
    peer.session_uuid = f"01990000-0000-7000-8000-{number:012d}"
    identity = identity_from_uuid(peer.session_uuid)
    peer.compact_id, peer.speakable_id = identity.compact_id, identity.speakable_id
    peer.client_ref = f"cc:01990000-0000-7000-9000-{number:012d}"
    peer.project, peer.context_role = "foreign", "none"
    peer.claims = [str(claim)]
    peer.workspaces = [workspace or f"{world['repo']} @ main"]
    for key, value in changes.items():
        setattr(peer, key, value)
    world["board"].write_text(coordination.replace_table(world["board"].read_text(), sessions + [peer]))
    return peer


def test_passive_inspection_is_scoped_not_mutation_authority(world):
    module = importlib.import_module("run_admission")
    proof = passive_inspection(world)
    assert proof["purpose"] == "passive-stop"
    assert proof["paths"] == [str(world["plan"])]
    assert proof["global_board_validated"] is False
    with pytest.raises(ValueError, match="purpose|passive|admission"):
        with module.admission_scope(proof, world["actor"], world["project"]):
            pass
    with module.admission_scope(proof, world["actor"], world["project"], purpose="passive-stop") as token:
        context = {"actor": world["actor"], "project": world["project"], "binding": dict(proof),
                   "admission_observation": token}
        assert module.read_admission_observation(context)["purpose"] == "passive-stop"
    with pytest.raises(ValueError):
        module.read_admission_observation(context)
    with pytest.raises(ValueError):
        with module.admission_scope(dict(proof), world["actor"], world["project"], purpose="passive-stop"):
            pass


def test_passive_foreign_conflict_is_isolated_but_full_read_and_mutation_still_refuse(world):
    foreign = world["repo"] / "projects/foreign/file.md"
    add_passive_peer(world, foreign)
    add_passive_peer(world, foreign, number=44)
    before = world["board"].read_bytes()
    assert passive_inspection(world)["session_uuid"] == SEAT
    assert world["board"].read_bytes() == before
    for readonly in (False, True):
        with pytest.raises(ValueError, match="overlap"):
            admission(world, readonly=readonly)


def test_passive_does_not_probe_unrelated_unreadable_foreign_claim_identity(world, monkeypatch):
    import claim_scope
    foreign = world["scratch"] / "retired/projects/foreign/file.md"
    add_passive_peer(world, foreign)
    original = claim_scope.ClaimScopeResolver._native_identity
    calls = []
    def observed(resolver, pattern):
        calls.append(pattern)
        assert "retired" not in pattern, "unrelated unreadable claim was probed"
        return original(resolver, pattern)
    monkeypatch.setattr(claim_scope.ClaimScopeResolver, "_native_identity", observed)
    assert passive_inspection(world)["purpose"] == "passive-stop"
    assert calls and len(calls) >= 2  # Fresh native entry and exit, not a cached/no-op path.


@pytest.mark.parametrize("kind", ["exact", "ancestor", "wildcard", "relative", "symlink", "sibling"])
def test_passive_rejects_each_relevant_physical_or_logical_claim(world, kind):
    claim, workspace = world["plan"], None
    if kind == "ancestor":
        claim = world["project"]
    elif kind == "wildcard":
        claim = str(world["repo"] / "projects/*/*.md")
    elif kind == "relative":
        claim = "projects/alpha/*.md"
    elif kind == "symlink":
        alias = world["scratch"] / "alias"
        alias.symlink_to(world["project"], target_is_directory=True)
        claim = alias / "plan.md"
    elif kind == "sibling":
        sibling = world["scratch"] / "sibling"
        git(world["repo"], "worktree", "add", "-b", "sibling", str(sibling))
        claim, workspace = sibling / "projects/alpha/plan.md", f"{sibling} @ sibling"
    add_passive_peer(world, claim, workspace=workspace)
    with pytest.raises(ValueError, match="overlap|conflict"):
        passive_inspection(world)


def test_passive_nested_repository_is_not_a_metadata_alias(world):
    nested = world["repo"] / "projects/foreign"
    nested.mkdir()
    git(nested, "init", "-b", "main")
    target = nested / "projects/alpha/plan.md"
    target.parent.mkdir(parents=True)
    target.write_text("Independent nested repository\n")
    add_passive_peer(world, target, workspace=f"{nested} @ main")
    assert passive_inspection(world)["purpose"] == "passive-stop"


@pytest.mark.parametrize("scope", ["metadata", "checkout-root"])
def test_passive_unregistered_linked_claim_remains_an_unresolved_possible_alias(world, scope):
    sibling = world["scratch"] / "retired-linked"
    git(world["repo"], "worktree", "add", "-b", "retired", str(sibling))
    directory = world["repo"] / ".git/worktrees/retired-linked"
    directory.rename(world["scratch"] / "retained-registration")
    claim = sibling / "projects/alpha/plan.md" if scope == "metadata" else sibling
    add_passive_peer(world, claim, workspace=f"{sibling} @ retired")
    with pytest.raises(ValueError, match="identity|unverifiable"):
        passive_inspection(world)


def test_passive_virtual_claim_is_not_path_authority_but_own_alias_still_refuses(world):
    add_passive_peer(world, "coordination:foreign")
    assert passive_inspection(world)["purpose"] == "passive-stop"
    add_passive_peer(world, "coordination:another", number=44,
                     compact_id=identity_from_uuid(SEAT).compact_id)
    with pytest.raises(ValueError, match="ambiguous|selector"):
        passive_inspection(world)


def passive_foreign_checkout(world):
    foreign = world["scratch"] / "foreign-checkout"
    foreign.mkdir()
    git(foreign, "init", "-b", "main")
    git(foreign, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "core.hooksPath=/dev/null", "commit", "--allow-empty", "-m", "Fixture")
    add_passive_peer(world, foreign, workspace=f"{foreign} @ main")
    return foreign


def test_passive_foreign_broad_identity_uses_two_fresh_negative_native_queries(world, monkeypatch):
    import claim_scope
    foreign = passive_foreign_checkout(world)
    original, calls = claim_scope.native_git.run, []
    def observed(argv, **kwargs):
        if "-C" in argv and argv[argv.index("-C") + 1] == str(foreign):
            calls.append(tuple(argv[argv.index("-C") + 2:]))
        return original(argv, **kwargs)
    monkeypatch.setattr(claim_scope.native_git, "run", observed)
    for count in (2, 4):
        assert passive_inspection(world)["purpose"] == "passive-stop"
        assert calls == [("rev-parse", "--path-format=absolute", "--git-common-dir", "--show-toplevel")] * count


@pytest.mark.parametrize("mutation", ["same-common-pointer", "invalid-config"])
def test_passive_negative_native_classification_is_bracketed_and_cannot_hide_alias(world, monkeypatch, mutation):
    import claim_scope
    foreign = passive_foreign_checkout(world)
    original, changed = claim_scope.native_git.run, []
    def observed(argv, **kwargs):
        result = original(argv, **kwargs)
        if (not changed and "-C" in argv and argv[argv.index("-C") + 1] == str(foreign)
                and "rev-parse" in argv):
            changed.append(True)
            if mutation == "same-common-pointer":
                (foreign / ".git").rename(world["scratch"] / "retained-foreign-git")
                (foreign / ".git").write_text(f"gitdir: {world['repo'] / '.git'}\n")
            else:
                (foreign / ".git/config").write_text("[invalid fixture configuration\n")
        return result
    monkeypatch.setattr(claim_scope.native_git, "run", observed)
    with pytest.raises(ValueError, match="identity|snapshot|changed|unverifiable"):
        passive_inspection(world)
    assert changed


@pytest.mark.parametrize("change", ["claim", "branch", "released", "native", "duplicate", "context"])
def test_passive_cannot_hide_own_admission_or_ambiguity_failure(world, change):
    if change == "claim":
        write_board(world, claims=str(world["project"] / "other/**"))
    elif change == "branch":
        write_board(world, workspace=f"{world['repo']} @ foreign")
    elif change == "released":
        write_board(world, status="released")
    elif change == "native":
        write_board(world, native="01990000-0000-7000-8000-000000000099")
    elif change == "duplicate":
        write_board(world, duplicate=True)
    else:
        add_passive_peer(world, world["project"] / "other.md", project="alpha", context_role="owner")
    with pytest.raises(ValueError):
        passive_inspection(world)


@pytest.mark.parametrize("mutation", ["configuration", "registration", "physical"])
def test_passive_scope_verdict_cannot_escape_changed_observation_bounds(world, monkeypatch, mutation):
    import claim_scope
    sibling = world["scratch"] / "sibling"
    git(world["repo"], "worktree", "add", "-b", "sibling", str(sibling))
    alias = world["scratch"] / "alias"
    alias.symlink_to(sibling / "projects/alpha", target_is_directory=True)
    add_passive_peer(world, alias / "plan.md", workspace=f"{sibling} @ sibling")
    original = claim_scope.ClaimScopeResolver.conflicts
    changed = []
    def observed(resolver, *args, **kwargs):
        result = original(resolver, *args, **kwargs)
        if not changed:
            changed.append(True)
            if mutation == "configuration":
                git(world["repo"], "config", "fixture.changed", "yes")
            elif mutation == "registration":
                directory = world["repo"] / ".git/worktrees/sibling"
                directory.rename(directory.with_name("moved"))
            else:
                alias.unlink()
                alias.symlink_to(world["project"], target_is_directory=True)
        return result
    monkeypatch.setattr(claim_scope.ClaimScopeResolver, "conflicts", observed)
    with pytest.raises(ValueError, match="snapshot|changed|identity"):
        passive_inspection(world)
    assert changed


def test_noncreating_lock_never_creates_or_truncates_paths(tmp_path,monkeypatch):
    module=importlib.import_module('run_admission')
    path=tmp_path/'existing.lock';path.write_text('retained lock bytes')
    original=os.open;opened=[]
    def observe(target,flags,*args,**kwargs):
        opened.append(flags)
        assert not flags & (os.O_CREAT|os.O_TRUNC)
        return original(target,flags,*args,**kwargs)
    monkeypatch.setattr(module.os,'open',observe)
    monkeypatch.setattr(Path,'mkdir',lambda *args,**kwargs:pytest.fail('Noncreating lock must not mkdir'))
    with module.bounded_lock(path,create=False):pass
    assert opened and path.read_text()=='retained lock bytes'


@pytest.mark.parametrize('shape',['missing','symlink','fifo','directory','ancestor_symlink'])
def test_noncreating_lock_rejects_nonregular_or_absent_paths(tmp_path,shape):
    module=importlib.import_module('run_admission')
    path=tmp_path/'lock'
    if shape=='symlink':
        other=tmp_path/'other';other.write_text('retained');path.symlink_to(other)
    elif shape=='fifo':os.mkfifo(path)
    elif shape=='directory':path.mkdir()
    elif shape=='ancestor_symlink':
        real=tmp_path/'real';real.mkdir();(real/'lock').write_text('retained')
        alias=tmp_path/'alias';alias.symlink_to(real,target_is_directory=True);path=alias/'lock'
    with pytest.raises(module.AdmissionError):
        with module.bounded_lock(path,create=False,timeout=.05):pytest.fail('Unsafe lock acquired')
    if shape=='missing':assert not path.exists()


@pytest.mark.parametrize('shape',['deleted','replacement','symlink','fifo'])
def test_noncreating_lock_rejects_substitution_before_open(tmp_path,monkeypatch,shape):
    module=importlib.import_module('run_admission')
    path=tmp_path/'lock';path.write_text('retained')
    original=os.open;changed=[]
    def substitute(target,flags,*args,**kwargs):
        if Path(target)==path and not changed:
            path.rename(tmp_path/'retained-lock');changed.append(True)
            if shape=='replacement':path.write_text('different inode')
            elif shape=='symlink':path.symlink_to(tmp_path/'retained-lock')
            elif shape=='fifo':os.mkfifo(path)
        return original(target,flags,*args,**kwargs)
    monkeypatch.setattr(module.os,'open',substitute)
    with pytest.raises(module.AdmissionError):
        with module.bounded_lock(path,create=False,timeout=.05):pytest.fail('Replaced lock acquired')
    assert changed and (tmp_path/'retained-lock').read_text()=='retained'
    if shape=='deleted':assert not path.exists()


def test_noncreating_lock_rejects_replacement_while_waiting(tmp_path,monkeypatch):
    module=importlib.import_module('run_admission')
    path=tmp_path/'lock';path.write_text('retained')
    original=module.fcntl.flock;calls=[]
    def changed_during_wait(fd,flags):
        if flags & module.fcntl.LOCK_NB and not calls:
            calls.append(True);path.rename(tmp_path/'retained-lock');path.write_text('different inode')
            raise BlockingIOError()
        return original(fd,flags)
    monkeypatch.setattr(module.fcntl,'flock',changed_during_wait)
    with pytest.raises(module.AdmissionError):
        with module.bounded_lock(path,create=False,timeout=.05):pytest.fail('Stale lock acquired')
    assert calls
