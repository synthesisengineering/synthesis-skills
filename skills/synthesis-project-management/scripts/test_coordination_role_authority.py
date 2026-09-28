"""Independent role-merge consumer and authority controls; synthetic seats only."""

import sys
import pytest
from test_coordination import (
    MODULE,
    claim_args,
    _claims_of,
    _isolate_client_session_env,
)

__all__ = ["_isolate_client_session_env"]


def setup_owner(tmp_path, monkeypatch, *, canonical=True):
    board = tmp_path / "board" / "active-sessions.md"
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:review-owner")
    args = dict(session_id="OWNER", project="alpha", workspace="/tmp/review-one @ main")
    area = "/tmp/review-one/projects/alpha/CONTEXT.md" if canonical else "virtual:owned"
    assert MODULE.command_claim(claim_args(board, **args, area=area)) == 0
    return board, args, area


@pytest.mark.parametrize("selector", ["legacy", "compact", "omitted"])
def test_authenticated_owner_may_repeat_canonical_context(
    tmp_path, monkeypatch, selector
):
    board, args, area = setup_owner(tmp_path, monkeypatch)
    if selector == "compact":
        args["session_id"] = _claims_of(board).compact_id
    elif selector == "omitted":
        args["session_id"] = None
    before = _claims_of(board)
    claim = claim_args(board, **args, area=area, context_role="contributor")
    # An omitted selector does not omit the CLI's required agent or machine.
    claim.agent = "codex"
    claim.machine = "machine-OWNER"
    assert MODULE.command_claim(claim) == 0
    after = _claims_of(board)
    assert after.context_role == "owner"
    assert after.identity == before.identity
    assert after.claims == before.claims
    assert after.workspaces == before.workspaces


@pytest.mark.parametrize("change", ["foreign", "replace", "cross_project"])
def test_repeated_context_refuses_without_retained_authority(
    tmp_path, monkeypatch, change
):
    board, args, area = setup_owner(tmp_path, monkeypatch)
    before = board.read_bytes()
    if change == "foreign":
        monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:review-foreign")
    if change == "cross_project":
        args["project"] = "beta"
    assert (
        MODULE.command_claim(
            claim_args(
                board,
                **args,
                area=area,
                context_role="contributor",
                replace=change == "replace",
            )
        )
        == 10
    )
    assert board.read_bytes() == before


def test_new_contributor_cannot_claim_canonical_context(tmp_path, monkeypatch):
    board = tmp_path / "board" / "active-sessions.md"
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:new-contributor")
    assert (
        MODULE.command_claim(
            claim_args(
                board,
                session_id="NEW",
                project="alpha",
                workspace="/tmp/review-one @ main",
                area="/tmp/review-one/CONTEXT.md",
                context_role="contributor",
            )
        )
        == 10
    )
    assert not board.exists()


def test_cross_project_does_not_inherit_role(tmp_path, monkeypatch):
    board, args, _ = setup_owner(tmp_path, monkeypatch, canonical=False)
    args["project"] = "beta"
    assert (
        MODULE.command_claim(
            claim_args(board, **args, area="virtual:added", context_role="contributor")
        )
        == 0
    )
    after = _claims_of(board)
    assert after.context_role == "contributor"
    assert after.project == "beta"
    assert after.claims == ["virtual:owned", "virtual:added"]


def test_retained_owner_cannot_take_foreign_scope(tmp_path, monkeypatch):
    board, args, _ = setup_owner(tmp_path, monkeypatch, canonical=False)
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:peer")
    assert (
        MODULE.command_claim(
            claim_args(
                board,
                session_id="PEER",
                project="beta",
                workspace="/tmp/review-two @ main",
                area="virtual:foreign",
                context_role="contributor",
            )
        )
        == 0
    )
    before = board.read_bytes()
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:review-owner")
    assert (
        MODULE.command_claim(
            claim_args(
                board, **args, area="virtual:foreign", context_role="contributor"
            )
        )
        == 10
    )
    assert board.read_bytes() == before


def test_incremental_owner_promotion_still_refuses_second_owner(tmp_path, monkeypatch):
    board, _, _ = setup_owner(tmp_path, monkeypatch, canonical=False)
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:peer")
    args = dict(session_id="PEER", project="alpha", workspace="/tmp/review-two @ main")
    assert (
        MODULE.command_claim(
            claim_args(board, **args, area="virtual:peer", context_role="contributor")
        )
        == 0
    )
    before = board.read_bytes()
    assert (
        MODULE.command_claim(
            claim_args(board, **args, area="virtual:peer", context_role="owner")
        )
        == 10
    )
    assert board.read_bytes() == before


def test_failed_role_replacement_cannot_execute_dependent_effect(tmp_path, monkeypatch):
    board, args, area = setup_owner(tmp_path, monkeypatch)
    claim = claim_args(
        board, **args, area=area, context_role="contributor", replace=True
    )
    marker = tmp_path / "effect.txt"
    claim.then = [
        sys.executable,
        "-c",
        "from pathlib import Path; Path("
        + repr(str(marker))
        + ").write_text('effect')",
    ]
    claim.then_cwd = tmp_path
    claim.then_timeout = 2
    before = board.read_bytes()
    assert MODULE.command_claim(claim) == 10
    assert board.read_bytes() == before
    assert not marker.exists()


def test_claim_cli_preserves_same_native_owner(tmp_path, monkeypatch):
    board, args, area = setup_owner(tmp_path, monkeypatch)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "coordination.py",
            "--board",
            str(board),
            "claim",
            "--id",
            args["session_id"],
            "--agent",
            "codex",
            "--machine",
            "machine-OWNER",
            "--project",
            "alpha",
            "--mode",
            "implementation",
            "--goal",
            "synthetic helper",
            "--workspace",
            args["workspace"],
            "--area",
            area,
            "--context-role",
            "contributor",
        ],
    )
    assert MODULE.main() == 0
    assert _claims_of(board).context_role == "owner"


@pytest.mark.parametrize("foreign", [False, True])
def test_claude_same_host_requires_exact_harness_for_retained_role(
    tmp_path, monkeypatch, foreign
):
    board = tmp_path / "board" / "active-sessions.md"
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "review-harness-owner")
    monkeypatch.setenv("CLAUDE_CODE_HOST_SESSION_ID", "local-shared-review")
    args = dict(
        session_id="CLAUDE", project="alpha", workspace="/tmp/review-claude @ main"
    )
    assert MODULE.command_claim(claim_args(board, **args, area="virtual:one")) == 0
    original = _claims_of(board)
    before = board.read_bytes()
    if foreign:
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "review-harness-foreign")
    # This has the peer's actual command shape, with synthetic identities only.
    helper = claim_args(board, **args, area="virtual:two", context_role="contributor")
    helper.agent = "claude-code"
    helper.mode = "implementation"
    assert MODULE.command_claim(helper) == (10 if foreign else 0)
    if foreign:
        assert board.read_bytes() == before
    else:
        after = _claims_of(board)
        assert after.context_role == "owner"
        assert after.identity == original.identity
        assert after.claims == ["virtual:one", "virtual:two"]
