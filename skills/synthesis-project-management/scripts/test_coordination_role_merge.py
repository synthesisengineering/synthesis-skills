"""Incremental helper claims cannot silently demote their authenticated seat."""

from pathlib import Path

import pytest
from test_coordination import (
    MODULE,
    claim_args,
    _claims_of,
    _isolate_client_session_env,
)

__all__ = ["_isolate_client_session_env"]


@pytest.mark.parametrize(
    "held,requested,expected",
    [
        ("owner", "contributor", "owner"),
        ("owner", "none", "owner"),
        ("contributor", "none", "contributor"),
        ("none", "contributor", "contributor"),
        ("none", "owner", "owner"),
        ("contributor", "owner", "owner"),
    ],
)
def test_incremental_same_seat_preserves_strongest_context_role(
    tmp_path, monkeypatch, capsys, held, requested, expected
):
    board = tmp_path / "coordination" / "active-sessions.md"
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:owner-a")
    args = dict(session_id="A", project="project-a", workspace="/tmp/repo-a @ main")
    assert (
        MODULE.command_claim(
            claim_args(board, **args, area="scope/a.md", context_role=held)
        )
        == 0
    )
    assert (
        MODULE.command_claim(
            claim_args(board, **args, area="scope/b.md", context_role=requested)
        )
        == 0
    )
    current = _claims_of(board)
    assert current.context_role == expected
    assert current.claims == ["scope/a.md", "scope/b.md"]
    if held != requested and expected == held:
        assert "context role" in capsys.readouterr().out


def test_helper_reclaim_keeps_owned_context_and_new_worktree(tmp_path, monkeypatch):
    board = tmp_path / "coordination" / "active-sessions.md"
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:owner-a")
    first = claim_args(
        board,
        session_id="A",
        project="project-a",
        workspace="/tmp/repo-a @ main",
        area="/tmp/repo-a/projects/alpha/CONTEXT.md",
    )
    assert MODULE.command_claim(first) == 0
    helper = claim_args(
        board,
        session_id="A",
        project="project-a",
        workspace="/tmp/repo-b @ feature/b",
        area="/tmp/repo-b/src",
        context_role="contributor",
    )
    assert MODULE.command_claim(helper) == 0
    current = _claims_of(board)
    assert current.context_role == "owner"
    assert current.claims == [
        str(Path(first.area[0]).resolve()), str(Path(helper.area[0]).resolve())
    ]
    assert current.workspaces == [first.workspace[0], helper.workspace[0]]
    assert MODULE.validate_sessions([current]) == []


def test_explicit_replace_can_narrow_role_after_releasing_context(
    tmp_path, monkeypatch
):
    board = tmp_path / "coordination" / "active-sessions.md"
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:owner-a")
    args = dict(session_id="A", project="project-a", workspace="/tmp/repo-a @ main")
    assert (
        MODULE.command_claim(claim_args(board, **args, area="/tmp/repo-a/CONTEXT.md"))
        == 0
    )
    assert (
        MODULE.command_claim(
            claim_args(
                board,
                **args,
                area="/tmp/repo-a/src",
                context_role="contributor",
                replace=True,
            )
        )
        == 0
    )
    assert _claims_of(board).context_role == "contributor"
    assert _claims_of(board).claims == ["/tmp/repo-a/src"]


def test_foreign_native_cannot_merge_the_owners_role_or_claims(tmp_path, monkeypatch):
    board = tmp_path / "coordination" / "active-sessions.md"
    args = dict(session_id="A", project="project-a", workspace="/tmp/repo-a @ main")
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:owner-a")
    assert MODULE.command_claim(claim_args(board, **args, area="scope/a.md")) == 0
    before = board.read_bytes()
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:foreign-b")
    assert (
        MODULE.command_claim(
            claim_args(board, **args, area="scope/b.md", context_role="contributor")
        )
        == 10
    )
    assert board.read_bytes() == before
