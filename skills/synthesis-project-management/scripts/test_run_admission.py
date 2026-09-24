"""Admission fixtures use real temporary Git, board grammar, and native evidence."""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from board_grammar import V4_COLUMNS
from coordination_schema import identity_from_uuid

SEAT = "01990000-0000-7000-8000-000000000011"
NATIVE = "01990000-0000-7000-8000-000000000022"


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def write_board(world, *, claims=None, workspace=None, status="active", native=NATIVE,
                heartbeat="2026-09-23T12:00:00Z", duplicate=False):
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


def test_claim_digest_changes_on_revocation_but_not_heartbeat(world):
    first = admission(world)
    write_board(world, heartbeat="2026-09-23T13:00:00Z")
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
    write_board(world, heartbeat="2026-09-23T15:00:00Z")
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
