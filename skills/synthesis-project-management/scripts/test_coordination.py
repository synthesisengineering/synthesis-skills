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


def test_overlap_detects_relative_and_absolute_spellings_of_one_path() -> None:
    assert MODULE.overlaps(
        "ai-knowledge-demo/projects/index.yaml",
        "/home/user/workspaces/demo/ai-knowledge-demo/projects/index.yaml",
    )
    assert MODULE.overlaps(
        "/home/user/workspaces/demo/ai-knowledge-demo/projects/**",
        "ai-knowledge-demo/projects/index.yaml",
    )
    assert MODULE.overlaps(
        "ai-knowledge-demo/projects/demo-project/sessions/2026-07.md",
        "/home/user/workspaces/demo/ai-knowledge-demo/projects/**",
    )


def test_overlap_expands_home_prefixed_claims() -> None:
    home = Path.home()
    assert MODULE.overlaps(
        "~/.claude/skills/**",
        f"{home}/.claude/skills/demo-skill/SKILL.md",
    )


def test_overlap_keeps_distinct_subtrees_apart() -> None:
    assert not MODULE.overlaps(
        "ai-knowledge-demo/daily-plans/**",
        "/home/user/workspaces/demo/ai-knowledge-demo/projects/**",
    )
    assert not MODULE.overlaps(
        "/repos/alpha/**",
        "/repos/beta/**",
    )
    assert not MODULE.overlaps("/repos/alpha/**", "/repos/alphabet/**")
    assert not MODULE.overlaps("repo/docs/**", "repo/does-not-share/**")


def test_overlap_same_form_containment_still_holds() -> None:
    assert MODULE.overlaps("repo/**", "repo/file.md")
    assert MODULE.overlaps("/repos/alpha/**", "/repos/alpha/docs/**")
    assert MODULE.overlaps("bare-glob-**", "bare-glob-**")


def test_mixed_spelling_claims_conflict_on_the_board(tmp_path: Path) -> None:
    board = tmp_path / "coordination" / "active-sessions.md"
    first = claim_args(
        board,
        session_id="A",
        project="project-a",
        workspace="/tmp/worktree-a @ feature/a",
        area="ai-knowledge-demo/projects/index.yaml",
    )
    assert MODULE.command_claim(first) == 0

    second = claim_args(
        board,
        session_id="B",
        project="project-b",
        workspace="/tmp/worktree-b @ feature/b",
        area="/home/user/workspaces/demo/ai-knowledge-demo/projects/index.yaml",
    )
    assert MODULE.command_claim(second) == 10


def lease_machines(tmp_path: Path, count: int = 2) -> list[Path]:
    """Simulate machines sharing one lease remote but no filesystem board."""
    subprocess = __import__("subprocess")
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


def test_lease_shares_claims_across_machines(tmp_path: Path) -> None:
    machine1, machine2 = lease_machines(tmp_path)
    first = claim_args(
        machine1,
        session_id="A",
        project="project-a",
        workspace="/tmp/worktree-a @ feature/a",
        area="/repos/shared/docs/**",
    )
    assert MODULE.command_claim(first) == 0

    conflicting = claim_args(
        machine2,
        session_id="B",
        project="project-b",
        workspace="/tmp/worktree-b @ feature/b",
        area="/repos/shared/docs/guide.md",
    )
    assert MODULE.command_claim(conflicting) == 10

    disjoint = claim_args(
        machine2,
        session_id="B",
        project="project-b",
        workspace="/tmp/worktree-b @ feature/b",
        area="/repos/other/**",
    )
    assert MODULE.command_claim(disjoint) == 0

    assert MODULE.command_release(args(machine1, id="A")) == 0
    retried = claim_args(
        machine2,
        session_id="C",
        project="project-c",
        workspace="/tmp/worktree-c @ feature/c",
        area="/repos/shared/docs/guide.md",
    )
    assert MODULE.command_claim(retried) == 0

    table = MODULE.rows(machine2.read_text(encoding="utf-8"))
    by_id = {row.id: row for row in table}
    assert by_id["A"].status == "released"
    assert by_id["B"].status == "active"
    assert by_id["C"].status == "active"


def test_lease_compare_and_swap_retries_after_concurrent_advance(
    tmp_path: Path, monkeypatch
) -> None:
    machine1, machine2 = lease_machines(tmp_path)
    original_publish = MODULE.lease_publish
    state = {"raced": False}

    def racing_publish(config, board_name, content, expected_sha):
        if not state["raced"]:
            state["raced"] = True
            competing = claim_args(
                machine2,
                session_id="X",
                project="project-x",
                workspace="/tmp/worktree-x @ feature/x",
                area="/repos/unrelated/**",
            )
            assert MODULE.command_claim(competing) == 0
        return original_publish(config, board_name, content, expected_sha)

    monkeypatch.setattr(MODULE, "lease_publish", racing_publish)
    first = claim_args(
        machine1,
        session_id="A",
        project="project-a",
        workspace="/tmp/worktree-a @ feature/a",
        area="/repos/shared/**",
    )
    assert MODULE.command_claim(first) == 0

    table = MODULE.rows(machine1.read_text(encoding="utf-8"))
    identifiers = {row.id for row in table}
    assert identifiers == {"A", "X"}


def test_lease_unreachable_remote_fails_closed(tmp_path: Path) -> None:
    directory = tmp_path / "machine1"
    directory.mkdir()
    (directory / "lease.json").write_text(
        json.dumps({"remote": str(tmp_path / "missing-remote.git")}),
        encoding="utf-8",
    )
    board = directory / "active-sessions.md"
    request = claim_args(
        board,
        session_id="A",
        project="project-a",
        workspace="/tmp/worktree-a @ feature/a",
        area="/repos/shared/**",
    )
    assert MODULE.command_claim(request) == 10
    assert not board.exists()


def test_lease_bootstrap_publishes_existing_local_board(tmp_path: Path) -> None:
    machine1, machine2 = lease_machines(tmp_path)
    (machine1.parent / "lease.json").unlink()
    local_only = claim_args(
        machine1,
        session_id="A",
        project="project-a",
        workspace="/tmp/worktree-a @ feature/a",
        area="/repos/shared/**",
    )
    assert MODULE.command_claim(local_only) == 0

    (machine1.parent / "lease.json").write_text(
        json.dumps({"remote": str(tmp_path / "remote.git")}), encoding="utf-8"
    )
    second = claim_args(
        machine1,
        session_id="B",
        project="project-b",
        workspace="/tmp/worktree-b @ feature/b",
        area="/repos/other/**",
    )
    assert MODULE.command_claim(second) == 0

    conflicting = claim_args(
        machine2,
        session_id="C",
        project="project-c",
        workspace="/tmp/worktree-c @ feature/c",
        area="/repos/shared/inner/**",
    )
    assert MODULE.command_claim(conflicting) == 10


def test_lease_status_reports_refresh_failure_in_strict_mode(
    tmp_path: Path, capsys
) -> None:
    machine1, _ = lease_machines(tmp_path)
    request = claim_args(
        machine1,
        session_id="A",
        project="project-a",
        workspace="/tmp/worktree-a @ feature/a",
        area="/repos/shared/**",
    )
    assert MODULE.command_claim(request) == 0

    (machine1.parent / "lease.json").write_text(
        json.dumps({"remote": str(tmp_path / "now-gone.git")}), encoding="utf-8"
    )
    capsys.readouterr()
    exit_code = MODULE.command_status(
        args(machine1, json=True, strict=True, stale_after_minutes=240)
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 10
    assert payload["lease"]["configured"] is True
    assert payload["lease"]["refreshed"] is False
    assert any("lease refresh failed" in problem for problem in payload["problems"])


def test_lease_doctor_verifies_remote_sync(tmp_path: Path, capsys) -> None:
    machine1, machine2 = lease_machines(tmp_path)
    request = claim_args(
        machine1,
        session_id="A",
        project="project-a",
        workspace="/tmp/worktree-a @ feature/a",
        area="/repos/shared/**",
    )
    assert MODULE.command_claim(request) == 0
    assert MODULE.command_doctor(args(machine1)) == 0
    captured = capsys.readouterr()
    assert "lease in sync" in captured.out

    advance = claim_args(
        machine2,
        session_id="B",
        project="project-b",
        workspace="/tmp/worktree-b @ feature/b",
        area="/repos/other/**",
    )
    assert MODULE.command_claim(advance) == 0
    assert MODULE.command_doctor(args(machine1)) == 1
    captured = capsys.readouterr()
    assert "differs from the lease remote" in captured.err

    assert (
        MODULE.command_status(
            args(machine1, json=False, strict=False, stale_after_minutes=240)
        )
        == 0
    )
    assert MODULE.command_doctor(args(machine1)) == 0


def test_lease_declares_itself_in_board_content(tmp_path: Path) -> None:
    machine1, machine2 = lease_machines(tmp_path)
    request = claim_args(
        machine1,
        session_id="A",
        project="project-a",
        workspace="/tmp/worktree-a @ feature/a",
        area="/repos/shared/**",
    )
    assert MODULE.command_claim(request) == 0
    remote = str(tmp_path / "remote.git")
    assert MODULE.declared_lease(machine1.read_text(encoding="utf-8")) == remote

    follower = claim_args(
        machine2,
        session_id="B",
        project="project-b",
        workspace="/tmp/worktree-b @ feature/b",
        area="/repos/other/**",
    )
    assert MODULE.command_claim(follower) == 0
    assert MODULE.declared_lease(machine2.read_text(encoding="utf-8")) == remote


def test_declared_board_without_config_refuses_mutation(tmp_path: Path) -> None:
    machine1, _ = lease_machines(tmp_path)
    request = claim_args(
        machine1,
        session_id="A",
        project="project-a",
        workspace="/tmp/worktree-a @ feature/a",
        area="/repos/shared/**",
    )
    assert MODULE.command_claim(request) == 0

    (machine1.parent / "lease.json").unlink()
    late = claim_args(
        machine1,
        session_id="B",
        project="project-b",
        workspace="/tmp/worktree-b @ feature/b",
        area="/repos/other/**",
    )
    assert MODULE.command_claim(late) == 10
    table = MODULE.rows(machine1.read_text(encoding="utf-8"))
    assert {row.id for row in table} == {"A"}

    assert MODULE.command_doctor(args(machine1)) == 1


def test_lease_disable_publishes_and_retires_config(tmp_path: Path) -> None:
    machine1, machine2 = lease_machines(tmp_path)
    request = claim_args(
        machine1,
        session_id="A",
        project="project-a",
        workspace="/tmp/worktree-a @ feature/a",
        area="/repos/shared/**",
    )
    assert MODULE.command_claim(request) == 0

    assert MODULE.command_lease_disable(args(machine1, local_only=False)) == 0
    assert not (machine1.parent / "lease.json").exists()
    assert any(
        candidate.name.startswith("lease.json.disabled-")
        for candidate in machine1.parent.iterdir()
    )
    assert MODULE.declared_lease(machine1.read_text(encoding="utf-8")) is None

    unleased = claim_args(
        machine1,
        session_id="B",
        project="project-b",
        workspace="/tmp/worktree-b @ feature/b",
        area="/repos/other/**",
    )
    assert MODULE.command_claim(unleased) == 0

    refreshed = MODULE.lease_fetch(
        {
            "remote": str(tmp_path / "remote.git"),
            "ref": MODULE.LEASE_DEFAULT_REF,
            "repository": machine2.parent / ".lease-repo",
        }
    )
    assert refreshed[1] is not None
    assert MODULE.declared_lease(refreshed[1]) is None


def test_lease_disable_local_only_requires_absent_config(tmp_path: Path) -> None:
    machine1, _ = lease_machines(tmp_path)
    request = claim_args(
        machine1,
        session_id="A",
        project="project-a",
        workspace="/tmp/worktree-a @ feature/a",
        area="/repos/shared/**",
    )
    assert MODULE.command_claim(request) == 0

    assert MODULE.command_lease_disable(args(machine1, local_only=True)) == 10

    (machine1.parent / "lease.json").unlink()
    assert MODULE.command_lease_disable(args(machine1, local_only=True)) == 0
    assert MODULE.declared_lease(machine1.read_text(encoding="utf-8")) is None
    follow_up = claim_args(
        machine1,
        session_id="B",
        project="project-b",
        workspace="/tmp/worktree-b @ feature/b",
        area="/repos/other/**",
    )
    assert MODULE.command_claim(follow_up) == 0


def test_semicolon_separated_claims_still_conflict(tmp_path: Path) -> None:
    board = tmp_path / "coordination" / "active-sessions.md"
    legacy = claim_args(
        board,
        session_id="A",
        project="project-a",
        workspace="/tmp/worktree-a @ feature/a",
        area="repo-one/notes/**; repo-two/daily/**",
    )
    assert MODULE.command_claim(legacy) == 0
    parsed = MODULE.rows(board.read_text(encoding="utf-8"))[0]
    assert len(parsed.claims) == 2

    overlapping = claim_args(
        board,
        session_id="B",
        project="project-b",
        workspace="/tmp/worktree-b @ feature/b",
        area="/home/user/workspaces/demo/repo-two/daily/plan.md",
    )
    assert MODULE.command_claim(overlapping) == 10
