from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("coordination.py")
SPEC = importlib.util.spec_from_file_location("coordination", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def args(board: Path, **values):
    return type("Args", (), {"board": board, **values})()


def claim_args(
    board: Path,
    *,
    session_id: str,
    project: str,
    workspace: str,
    area: str,
    context_role: str = "owner",
):
    return args(
        board,
        id=session_id,
        agent=session_id,
        machine=f"machine-{session_id}",
        project=project,
        mode="autonomous",
        goal=f"goal-{session_id}",
        workspace=[workspace],
        area=[area],
        context_role=context_role,
    )


def test_claim_conflict_message_heartbeat_and_release(tmp_path: Path) -> None:
    board = tmp_path / "coordination" / "active-sessions.md"
    first = claim_args(
        board,
        session_id="A",
        project="project-a",
        workspace="/tmp/worktree-a @ feature/a",
        area="repo/**",
    )
    assert MODULE.command_claim(first) == 0

    second = claim_args(
        board,
        session_id="B",
        project="project-b",
        workspace="/tmp/worktree-b @ feature/b",
        area="repo/file.md",
    )
    assert MODULE.command_claim(second) == 10

    message = args(board, sender="B", to="A", text="Please release repo/file.md.")
    assert MODULE.command_message(message) == 0
    assert "Please release repo/file.md." in board.read_text(encoding="utf-8")

    before = MODULE.rows(board.read_text(encoding="utf-8"))[0].heartbeat
    assert MODULE.command_heartbeat(args(board, id="A")) == 0
    after = MODULE.rows(board.read_text(encoding="utf-8"))[0].heartbeat
    assert after >= before

    assert MODULE.command_release(args(board, id="A")) == 0
    assert MODULE.command_claim(second) == 0
    table = MODULE.rows(board.read_text(encoding="utf-8"))
    assert next(row for row in table if row.id == "A").status == "released"
    assert next(row for row in table if row.id == "B").status == "active"


def test_different_projects_and_worktrees_run_in_parallel(tmp_path: Path) -> None:
    board = tmp_path / "active-sessions.md"
    first = claim_args(
        board,
        session_id="A",
        project="project-a",
        workspace="/tmp/repo-a @ feature/a",
        area="repo-a/**",
    )
    second = claim_args(
        board,
        session_id="B",
        project="project-b",
        workspace="/tmp/repo-b @ feature/b",
        area="repo-b/**",
    )

    assert MODULE.command_claim(first) == 0
    assert MODULE.command_claim(second) == 0
    assert len(MODULE.rows(board.read_text(encoding="utf-8"))) == 2


def test_same_project_owner_and_contributor_can_use_isolated_slices(
    tmp_path: Path,
) -> None:
    board = tmp_path / "active-sessions.md"
    owner = claim_args(
        board,
        session_id="owner",
        project="shared-project",
        workspace="/tmp/repo-owner @ feature/owner",
        area="repo/backend/**",
    )
    contributor = claim_args(
        board,
        session_id="contributor",
        project="shared-project",
        workspace="/tmp/repo-contributor @ feature/contributor",
        area="repo/frontend/**",
        context_role="contributor",
    )

    assert MODULE.command_claim(owner) == 0
    assert MODULE.command_claim(contributor) == 0


def test_same_project_rejects_two_context_owners(tmp_path: Path) -> None:
    board = tmp_path / "active-sessions.md"
    first = claim_args(
        board,
        session_id="A",
        project="shared-project",
        workspace="/tmp/repo-a @ feature/a",
        area="repo/backend/**",
    )
    second = claim_args(
        board,
        session_id="B",
        project="shared-project",
        workspace="/tmp/repo-b @ feature/b",
        area="repo/frontend/**",
    )

    assert MODULE.command_claim(first) == 0
    assert MODULE.command_claim(second) == 10


def test_contributor_cannot_claim_canonical_context(tmp_path: Path) -> None:
    board = tmp_path / "active-sessions.md"
    contributor = claim_args(
        board,
        session_id="B",
        project="shared-project",
        workspace="/tmp/repo-b @ feature/b",
        area="ai-knowledge/projects/shared-project/CONTEXT.md",
        context_role="contributor",
    )

    assert MODULE.command_claim(contributor) == 10
    assert not board.exists()


def test_same_worktree_is_refused_even_for_nonoverlapping_projects(
    tmp_path: Path,
) -> None:
    board = tmp_path / "active-sessions.md"
    first = claim_args(
        board,
        session_id="A",
        project="project-a",
        workspace="/tmp/shared @ feature/a",
        area="repo/backend/**",
    )
    second = claim_args(
        board,
        session_id="B",
        project="project-b",
        workspace="/tmp/shared @ feature/b",
        area="repo/frontend/**",
    )

    assert MODULE.command_claim(first) == 0
    assert MODULE.command_claim(second) == 10


def test_same_repo_branch_is_refused_across_worktrees(tmp_path: Path) -> None:
    board = tmp_path / "active-sessions.md"
    first = claim_args(
        board,
        session_id="A",
        project="project-a",
        workspace="/tmp/one/shared-repo @ feature/shared",
        area="repo/backend/**",
    )
    second = claim_args(
        board,
        session_id="B",
        project="project-b",
        workspace="/tmp/two/shared-repo @ feature/shared",
        area="repo/frontend/**",
    )

    assert MODULE.command_claim(first) == 0
    assert MODULE.command_claim(second) == 10


def test_v1_board_migrates_without_losing_messages(tmp_path: Path) -> None:
    board = tmp_path / "active-sessions.md"
    board.write_text(
        "# Coordination\n\n"
        "## Active sessions\n\n"
        "| id | agent | started | mode | goal | claimed areas (advisory lock) | status |\n"
        "|----|-------|---------|------|------|--------------------------------|--------|\n"
        "| A | Claude | 2026-07-29 | interactive | work | repo-a/** | active |\n\n"
        "## Messages\n\n"
        "### → B, from A — 2026-07-29\n\nKeep this handoff.\n\n"
        "---\n\n## Protocol\n",
        encoding="utf-8",
    )

    assert MODULE.command_migrate(args(board)) == 0
    text = board.read_text(encoding="utf-8")
    migrated = MODULE.rows(text)
    assert "Schema: v2" in text
    assert "Keep this handoff." in text
    assert migrated[0].id == "A"
    assert migrated[0].project == "unknown"
    assert migrated[0].claims == ["repo-a/**"]


def test_status_json_reports_stale_legacy_session(tmp_path: Path, capsys) -> None:
    board = tmp_path / "active-sessions.md"
    board.write_text(
        MODULE.template().replace(
            MODULE.TABLE_HEADER,
            MODULE.TABLE_HEADER
            + "\n| A | Claude | unknown | unknown | yesterday | yesterday | "
            "interactive |  | work | repo/** | none | active |",
        ),
        encoding="utf-8",
    )
    command = args(
        board,
        json=True,
        strict=False,
        stale_after_minutes=240,
    )

    assert MODULE.command_status(command) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["sessions"][0]["stale"] is True


def test_doctor_accepts_valid_v2_board(tmp_path: Path) -> None:
    board = tmp_path / "active-sessions.md"
    assert MODULE.command_claim(
        claim_args(
            board,
            session_id="A",
            project="project-a",
            workspace="/tmp/repo-a @ feature/a",
            area="repo-a/**",
        )
    ) == 0

    assert MODULE.command_doctor(args(board)) == 0


def test_message_accepts_annotated_protocol_heading(tmp_path: Path) -> None:
    board = tmp_path / "active-sessions.md"
    board.write_text(
        MODULE.template().replace(
            "## Protocol\n",
            "## Protocol (formalized)\n",
        ),
        encoding="utf-8",
    )
    message = args(board, sender="B", to="A", text="Sequencing update.")
    assert MODULE.command_message(message) == 0
    text = board.read_text(encoding="utf-8")
    assert "Sequencing update." in text
    assert "## Protocol (formalized)" in text
