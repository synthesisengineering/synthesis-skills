"""Creation reservations never become general write authority."""

from pathlib import Path
import subprocess
import pytest
from test_coordination import MODULE as C
import create_worktree as W
from test_coordination_b06 import row


def git(root, *args):
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.fixture
def world(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(
        repo,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "--allow-empty",
        "-m",
        "Fixture",
    )
    own = row(claims=[str(repo / "source")])
    board = tmp_path / "board.md"
    board.write_text(C.replace_table(C.template(), [own]))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", own.client_ref)
    for key in (
        "CLAUDE_CODE_SESSION_ID",
        "CLAUDE_CODE_HOST_SESSION_ID",
        "MUSE_SESSION_ID",
        "CLAUDECODE",
    ):
        monkeypatch.delenv(key, raising=False)
    return board, own, repo, tmp_path / "new-tree"


def test_create_reserves_before_mutation_without_granting_edits(world, monkeypatch):
    board, own, repo, target = world
    board.read_text()
    real = W._git
    seen = []

    def inspect(*a):
        current = C.rows(board.read_text())[0]
        assert "create:" + str(target) in current.claims
        assert C._absolute_claim_pattern("create:" + str(target), repo) is None
        seen.append(1)
        return real(*a)

    monkeypatch.setattr(W, "_git", inspect)
    result = W.create(board, own.compact_id, target, repo, "feature/fixture")
    assert result["status"] == "created-awaiting-workspace-and-edit-claim" and seen == [
        1
    ]
    current = C.rows(board.read_text())[0]
    assert (
        current.claims == own.claims and "create:" + str(target) not in current.claims
    )
    assert current.workspaces == own.workspaces
    assert not C._workspace_registered(current, target, "feature/fixture")
    assert git(target, "branch", "--show-current").strip() == "feature/fixture"
    assert C.validate_sessions(C.rows(board.read_text())) == []


@pytest.mark.parametrize("foreign_claim", ["physical", "reservation", "ancestor"])
def test_creation_collision_stops_every_dependent_effect(
    world, monkeypatch, foreign_claim
):
    board, own, repo, target = world
    area = {
        "physical": str(target),
        "reservation": "create:" + str(target),
        "ancestor": str(target.parent),
    }[foreign_claim]
    foreign = row(2, claims=[area])
    board.write_text(C.replace_table(C.template(), [own, foreign]))
    before = board.read_bytes()
    monkeypatch.setattr(
        W, "_git", lambda *_: pytest.fail("dependent Git ran after refused claim")
    )
    with pytest.raises((ValueError, RuntimeError), match="refused"):
        W.create(board, own.compact_id, target, repo, "feature/fixture")
    assert not target.exists() and board.read_bytes() == before


@pytest.mark.parametrize("identity", ["missing", "foreign", "legacy-alias"])
def test_creation_needs_exact_native_identity(world, monkeypatch, identity):
    board, own, repo, target = world
    before = board.read_bytes()
    if identity == "missing":
        monkeypatch.delenv("SYNTHESIS_CLIENT_SESSION_REF")
    else:
        monkeypatch.setenv(
            "SYNTHESIS_CLIENT_SESSION_REF",
            "codex:" + ("foreign" if identity == "foreign" else own.compact_id),
        )
    with pytest.raises(ValueError, match="exact native owner"):
        W.create(board, own.compact_id, target, repo, "feature/fixture")
    assert not target.exists() and board.read_bytes() == before


@pytest.mark.parametrize("unsafe", ["symlink", "existing", "traversal"])
def test_unsafe_target_refuses_without_effect(world, unsafe):
    board, own, repo, target = world
    if unsafe == "symlink":
        alias = target.parent / "alias"
        alias.symlink_to(target.parent, target_is_directory=True)
        target = alias / "new-tree"
    elif unsafe == "existing":
        target.mkdir()
    else:
        target = target.parent / "repo" / ".." / "new-tree"
    before = board.read_bytes()
    with pytest.raises((ValueError, OSError)):
        W.create(board, own.compact_id, target, repo, "feature/fixture")
    assert board.read_bytes() == before


def test_git_failure_preserves_reservation_and_partial_tree(world, monkeypatch):
    board, own, repo, target = world
    monkeypatch.setattr(
        W, "_git", lambda *_: subprocess.CompletedProcess([], 1, "", "fixture failed")
    )
    with pytest.raises(ValueError, match="partial work retained"):
        W.create(board, own.compact_id, target, repo, "feature/fixture")
    assert target.is_dir()
    assert "create:" + str(target) in C.rows(board.read_text())[0].claims


def test_changed_ancestry_refuses(world, monkeypatch):
    board, own, repo, target = world
    parent = target.parent / "parent"
    parent.mkdir()
    target = parent / "new"
    real = C.locked_update

    def changed(*a, **k):
        real(*a, **k)
        parent.rename(parent.with_name("retained"))
        parent.mkdir()

    monkeypatch.setattr(C, "locked_update", changed)
    with pytest.raises(ValueError, match="ancestry changed"):
        W.create(board, own.compact_id, target, repo, "feature/fixture")
    assert not target.exists()


def test_reservation_alone_is_not_edit_authority_and_preserves_foreign_row(world):
    board, own, repo, target = world
    foreign = row(2, claims=[str(target.parent / "elsewhere")])
    board.write_text(C.replace_table(C.template(), [own, foreign]))
    before_foreign = C.rows(board.read_text())[1]
    W.reserve(board, own.compact_id, target, repo)
    current = C.rows(board.read_text())
    assert current[1] == before_foreign and not target.exists()
    assert current[0].workspaces == own.workspaces
    assert C._absolute_claim_pattern("create:" + str(target), repo) is None
    assert C.claim_scope.ClaimScopeResolver().conflicts(
        "create:" + str(target), str(target / "file")
    )


def test_removed_reservation_before_effect_refuses(world, monkeypatch):
    board, own, repo, target = world
    real = W.reserve

    def interrupted(*a, **kw):
        result = real(*a, **kw)
        board.write_text(C.replace_table(C.template(), [own]))
        return result

    monkeypatch.setattr(W, "reserve", interrupted)
    monkeypatch.setattr(
        W, "_git", lambda *_: pytest.fail("Git ran after reservation removed")
    )
    with pytest.raises(ValueError, match="removed before execution"):
        W.create(board, own.compact_id, target, repo, "fixture")
    assert not target.exists()


def test_concurrent_creators_one_effect_no_foreign_release(world):
    import os
    import sys

    board, own, repo, target = world
    other = row(2, claims=[str(repo / "other")])
    board.write_text(C.replace_table(C.template(), [own, other]))
    commands = []
    processes = []
    for identity in (own, other):
        env = os.environ.copy()
        env["SYNTHESIS_CLIENT_SESSION_REF"] = identity.client_ref
        command = [
            sys.executable,
            str(Path(W.__file__)),
            "--board",
            str(board),
            "--session",
            identity.compact_id,
            "--repository",
            str(repo),
            "--target",
            str(target),
            "--branch",
            "fixture-" + identity.compact_id,
        ]
        commands.append(command)
        processes.append(
            subprocess.Popen(
                command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
        )
    outputs = []
    try:
        outputs = [p.communicate(timeout=15) for p in processes]
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
            p.wait(timeout=3)
    assert sorted(p.returncode for p in processes) == [0, 10], outputs
    sessions = C.rows(board.read_text())
    assert sessions == [
        own,
        other,
    ]  # Success and refusal both preserve every original field.
    assert target.is_dir() and not any(
        any(c.startswith("create:") for c in r.claims) for r in sessions
    )


def test_creation_board_contention_has_finite_refusal(world):
    import fcntl
    import os
    import sys

    board, own, repo, target = world
    lock = board.parent / ".active-sessions.lock"
    with lock.open("a+") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        env = os.environ.copy()
        env["SYNTHESIS_CLIENT_SESSION_REF"] = own.client_ref
        p = subprocess.Popen(
            [
                sys.executable,
                str(Path(W.__file__)),
                "--board",
                str(board),
                "--session",
                own.compact_id,
                "--repository",
                str(repo),
                "--target",
                str(target),
                "--branch",
                "fixture",
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            try:
                out, err = p.communicate(timeout=6.5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=2)
                pytest.fail("creation owner waited beyond board lock budget")
            assert p.returncode == 10, (out, err)
            assert b"lock" in err and not target.exists()
        finally:
            if p.poll() is None:
                p.kill()
            p.wait(timeout=2)


def test_creation_never_expands_relative_claim_through_new_workspace(world):
    from dataclasses import replace

    board, own, repo, target = world
    own = replace(own, claims=["src/**"], workspaces=[f"{repo} @ main"])
    board.write_text(C.replace_table(C.template(), [own]))
    before = C.rows(board.read_text())[0]
    assert not C._workspace_registered(before, target, "fixture")
    W.create(board, own.compact_id, target, repo, "fixture")
    after = C.rows(board.read_text())[0]
    assert after.claims == before.claims and after.workspaces == before.workspaces
    assert not (
        C._workspace_registered(after, target, "fixture")
        and not C._outside_claim(after, target, ["src/secret.py"])
    )
