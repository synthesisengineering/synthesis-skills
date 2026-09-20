"""Fleet shared board plane: concurrent claims, logical identity, fenced reads.

Covers FLEET-AC-04 (concurrent cross-Mac claims: exactly one wins, the loser
sees the winner's machine label + compact id), FLEET-AC-05 (same repo+branch
at different absolute paths still conflicts via logical resolution), and
FLEET-AC-06 (a dead lease remote fails authority reads loudly within the git
timeout — never a silent mirror fallback).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import coordination as MODULE
import fleet_identity as FI
import fleet_logical as LOGICAL


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    for name in (
        "SYNTHESIS_CLIENT_SESSION_REF",
        "CLAUDE_CODE_HOST_SESSION_ID",
        "CLAUDE_CODE_SESSION_ID",
        "CLAUDE_PID",
        "CLAUDECODE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(tmp_path / "fleet"))


def args(board: Path, **values):
    return type("Args", (), {"board": board, **values})()


def claim_args(board, *, session_id, project, workspace, area, machine=None):
    return args(
        board,
        id=session_id,
        agent=f"agent-{session_id}",
        machine=machine or f"machine-{session_id}",
        project=project,
        mode="autonomous",
        goal=f"goal-{session_id}",
        workspace=[workspace],
        area=[area],
        context_role="owner",
        replace=False,
        client_ref=None,
    )


def lease_machines(tmp_path: Path, count: int = 2) -> list[Path]:
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "--quiet", str(remote)],
        check=True,
        capture_output=True,
    )
    boards = []
    for index in range(1, count + 1):
        directory = tmp_path / f"machine{index}"
        directory.mkdir()
        (directory / "lease.json").write_text(
            json.dumps({"remote": str(remote)}), encoding="utf-8"
        )
        boards.append(directory / "active-sessions.md")
    return boards


def enroll(label: str, directory: Path, *, role: str = "secondary") -> str:
    machine_id = FI.mint_machine_id(directory)
    FI.enroll_self(label=label, role=role, directory=directory)
    return machine_id


def enroll_secondary(label: str, directory: Path, primary_dir: Path) -> str:
    """Enroll a secondary Mac against a synced copy of the fleet registry."""
    import shutil

    machine_id = FI.mint_machine_id(directory)
    shutil.copyfile(
        FI.registry_path(primary_dir), FI.registry_path(directory)
    )
    FI.enroll_self(label=label, role="secondary", directory=directory)
    return machine_id


def test_concurrent_cross_mac_claims_name_the_winner_fleet_ac_04(
    tmp_path, monkeypatch, capsys
):
    board_a, board_b = lease_machines(tmp_path)
    fleet_a = tmp_path / "fleet-a"
    fleet_b = tmp_path / "fleet-b"
    enroll("mac-a", fleet_a, role="primary")
    enroll_secondary("mac-b", fleet_b, fleet_a)

    # Same second, overlapping areas, two Macs: the first CAS lands.
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(fleet_a))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:owner-ac04-a")
    first = claim_args(
        board_a,
        session_id="A",
        project="project-a",
        workspace="/tmp/wt-ac04-a @ feature/shared",
        area="/repos/shared/docs/**",
        machine="mac-a",
    )
    assert MODULE.command_claim(first) == 0
    winner = MODULE.rows(board_a.read_text(encoding="utf-8"))[0]
    assert winner.machine_label == "mac-a"

    # The loser's CAS retry re-reads the newer board and refuses — naming
    # the winner's (machine label, compact id), not just the paths.
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(fleet_b))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:owner-ac04-b")
    second = claim_args(
        board_b,
        session_id="B",
        project="project-b",
        workspace="/tmp/wt-ac04-b @ feature/other",
        area="/repos/shared/docs/guide.md",
        machine="mac-b",
    )
    capsys.readouterr()
    assert MODULE.command_claim(second) == 10
    err = capsys.readouterr().err
    assert "mac-a" in err
    assert winner.compact_id in err

    # Exactly one claim landed on the shared plane: the loser pulls and sees
    # only the winner's row (its own refused claim wrote no mirror).
    assert MODULE.lease_refresh(board_b).get("refreshed") is True
    active = [
        row
        for row in MODULE.rows(board_b.read_text(encoding="utf-8"))
        if MODULE.active(row)
    ]
    assert [row.compact_id for row in active] == [winner.compact_id]


def init_checkout(path: Path, remote: str) -> Path:
    path.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "--quiet", str(path)], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(path), "remote", "add", "origin", remote],
        check=True,
        capture_output=True,
    )
    return path


def test_same_repo_branch_at_different_paths_conflicts_fleet_ac_05(tmp_path):
    remote = str(tmp_path / "origin.git")
    subprocess.run(
        ["git", "init", "--bare", "--quiet", remote],
        check=True,
        capture_output=True,
    )
    checkout_a = init_checkout(tmp_path / "mac-a-checkout", remote)
    checkout_b = init_checkout(tmp_path / "mac-b-checkout", remote)
    assert checkout_a != checkout_b

    workspace_a = f"{checkout_a} @ feature/x"
    workspace_b = f"{checkout_b} @ feature/x"
    claim_a = f"{checkout_a}/docs/**"
    claim_b = f"{checkout_b}/docs/guide.md"

    # Textual overlap sees nothing: the absolute spellings share no prefix.
    assert not MODULE.overlaps(claim_a, claim_b)

    # Logical resolution keys on (remote URL, branch, repo-relative path).
    assert LOGICAL.logical_workspace_conflict(workspace_a, workspace_b) is True
    assert (
        LOGICAL.logical_claim_conflict(
            claim_a, claim_b, [workspace_a], [workspace_b]
        )
        is True
    )

    # Different branches of the same repo are different lines of work.
    assert (
        LOGICAL.logical_claim_conflict(
            claim_a, claim_b, [workspace_a], [f"{checkout_b} @ feature/y"]
        )
        is False
    )

    # A different remote is a different repo, even at a confusable path.
    other_remote = str(tmp_path / "other.git")
    subprocess.run(
        ["git", "init", "--bare", "--quiet", other_remote],
        check=True,
        capture_output=True,
    )
    checkout_c = init_checkout(tmp_path / "mac-c-checkout", other_remote)
    assert (
        LOGICAL.logical_claim_conflict(
            claim_a,
            f"{checkout_c}/docs/guide.md",
            [workspace_a],
            [f"{checkout_c} @ feature/x"],
        )
        is False
    )

    # A deleted worktree on the other Mac fails closed as conflicting.
    import shutil

    shutil.rmtree(checkout_b)
    assert LOGICAL.logical_workspace_conflict(workspace_a, workspace_b) is True
    assert (
        LOGICAL.logical_claim_conflict(
            claim_a, claim_b, [workspace_a], [workspace_b]
        )
        is True
    )


def test_authority_reads_fail_closed_without_mirror_fallback_fleet_ac_06(
    tmp_path,
):
    directory = tmp_path / "mac-b"
    directory.mkdir()
    (directory / "lease.json").write_text(
        json.dumps({"remote": str(tmp_path / "missing-remote.git")}),
        encoding="utf-8",
    )
    board = directory / "active-sessions.md"
    # A stale-but-plausible mirror: an authority read must never bless it.
    board.write_text(MODULE.template(), encoding="utf-8")

    started = time.monotonic()
    with pytest.raises(RuntimeError, match="lease.*(unreachable|refresh failed)"):
        MODULE.require_fresh_board(board)
    with pytest.raises(RuntimeError, match="lease.*(unreachable|ref)"):
        MODULE._check_staged_board_snapshot(board)
    assert time.monotonic() - started < 30
