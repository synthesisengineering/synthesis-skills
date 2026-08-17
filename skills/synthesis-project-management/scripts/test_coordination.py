from __future__ import annotations

import importlib.util
import json
import sys
import threading
import uuid
from pathlib import Path

import pytest


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


def test_uuidv7_aliases_are_exact_reversible_views_of_random_material() -> None:
    first = uuid.UUID("019fff79-5858-7993-a329-b301bccf5d62")
    # Change only the 48-bit millisecond timestamp. The human aliases must not
    # inherit it.
    second = uuid.UUID(int=(first.int & ((1 << 80) - 1)) | (0x123456789ABC << 80))

    first_identity = MODULE.new_identity([])
    assert uuid.UUID(first_identity.session_uuid).version == 7
    token = MODULE.new_identity.__globals__["alias_token"](
        first_identity.session_uuid
    )
    schema = sys.modules["coordination_schema"]
    assert schema.decode_compact(first_identity.compact_id) == token
    assert schema.decode_speakable(first_identity.speakable_id) == token
    assert schema.identity_from_uuid(first).compact_id == schema.identity_from_uuid(second).compact_id
    assert schema.identity_from_uuid(first).speakable_id == schema.identity_from_uuid(second).speakable_id


def test_word_alias_v1_is_fixed_and_unambiguous() -> None:
    schema = sys.modules["coordination_schema"]
    words = schema.session_words()

    assert len(words) == len(set(words)) == 2048
    assert len({word[:4] for word in words}) == 2048


def test_claim_without_human_supplied_id_allocates_all_identities(tmp_path: Path) -> None:
    board = tmp_path / "active-sessions.md"
    request = claim_args(
        board,
        session_id="placeholder",
        project="project-a",
        workspace="/tmp/worktree-a @ feature/a",
        area="repo-a/**",
    )
    request.id = None

    assert MODULE.command_claim(request) == 0
    [session] = MODULE.rows(board.read_text(encoding="utf-8"))
    assert uuid.UUID(session.session_uuid).version == 7
    assert session.compact_id.startswith("s-")
    assert session.speakable_id.count("-") == 4
    assert session.legacy_id == ""


def test_every_identity_form_selects_the_same_session(tmp_path: Path) -> None:
    board = tmp_path / "active-sessions.md"
    request = claim_args(
        board,
        session_id="AX",
        project="project-a",
        workspace="/tmp/worktree-a @ feature/a",
        area="repo-a/**",
    )
    assert MODULE.command_claim(request) == 0
    [session] = MODULE.rows(board.read_text(encoding="utf-8"))

    for selector in (
        session.session_uuid,
        session.compact_id,
        session.speakable_id,
        session.legacy_id,
    ):
        assert MODULE.command_heartbeat(args(board, id=selector)) == 0
    assert MODULE.command_release(args(board, id=session.speakable_id)) == 0
    assert MODULE.rows(board.read_text(encoding="utf-8"))[0].status == "released"


def test_unmatched_strong_selector_does_not_create_a_session(tmp_path: Path) -> None:
    board = tmp_path / "active-sessions.md"
    first = claim_args(
        board,
        session_id="A",
        project="project-a",
        workspace="/tmp/worktree-a @ feature/a",
        area="repo-a/**",
    )
    assert MODULE.command_claim(first) == 0
    [session] = MODULE.rows(board.read_text(encoding="utf-8"))
    replacement = session.compact_id[:-1] + (
        "0" if session.compact_id[-1] != "0" else "1"
    )
    second = claim_args(
        board,
        session_id=replacement,
        project="project-b",
        workspace="/tmp/worktree-b @ feature/b",
        area="repo-b/**",
    )

    assert MODULE.command_claim(second) == 10
    assert len(MODULE.rows(board.read_text(encoding="utf-8"))) == 1


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
    assert next(row for row in table if row.legacy_id == "A").status == "released"
    assert next(row for row in table if row.legacy_id == "B").status == "active"


def test_release_leaves_pointer_without_matching_board_lease(tmp_path: Path) -> None:
    board = tmp_path / "coordination" / "active-sessions.md"
    claim = claim_args(
        board,
        session_id="A",
        project="project-a",
        workspace="/tmp/worktree-a @ feature/a",
        area="repo/**",
    )
    assert MODULE.command_claim(claim) == 0
    pointer = tmp_path / "active-project.json"
    pointer.write_text(
        json.dumps(
            {
                "owner_session": "A",
                "owner_lease": "https://example.test/other.git",
                "project": "/tmp/project-a",
            }
        ),
        encoding="utf-8",
    )

    assert MODULE.command_release(
        args(board, id="A", active_project_file=pointer)
    ) == 0

    assert pointer.exists()
    assert not (tmp_path / "active-project-history").exists()


def test_matching_session_and_lease_recoverably_archive_pointer(tmp_path: Path) -> None:
    pointer = tmp_path / "active-project.json"
    lease = "https://example.test/coordination.git"
    pointer.write_text(
        json.dumps(
            {
                "owner_session": "A",
                "owner_lease": lease,
                "project": "/tmp/project-a",
            }
        ),
        encoding="utf-8",
    )

    archived = MODULE.archive_owned_pointer(pointer, "A", lease)

    assert archived is not None and archived.is_file()
    assert not pointer.exists()
    assert json.loads(archived.read_text(encoding="utf-8"))["project"] == "/tmp/project-a"


def test_archive_filename_is_safe_for_separator_bearing_session_id(tmp_path: Path) -> None:
    pointer = tmp_path / "active-project.json"
    lease = "https://example.test/coordination.git"
    session_id = "agent/../../other|session"
    pointer.write_text(
        json.dumps({"owner_session": session_id, "owner_lease": lease}),
        encoding="utf-8",
    )

    archived = MODULE.archive_owned_pointer(pointer, session_id, lease)

    assert archived is not None and archived.is_file()
    assert archived.parent == tmp_path / "active-project-history"
    assert "/" not in archived.name
    assert "|" not in archived.name


def test_release_refuses_symlinked_active_pointer_archive(tmp_path: Path) -> None:
    pointer = tmp_path / "active-project.json"
    lease = "https://example.test/coordination.git"
    pointer.write_text(
        json.dumps({"owner_session": "A", "owner_lease": lease}),
        encoding="utf-8",
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "active-project-history").symlink_to(outside, target_is_directory=True)

    try:
        MODULE.archive_owned_pointer(pointer, "A", lease)
    except ValueError as exc:
        assert "archive must not be a symlink" in str(exc)
    else:
        raise AssertionError("symlinked archive root was accepted")
    assert pointer.is_file()


def test_release_rechecks_owner_after_waiting_for_pointer_writer(tmp_path: Path) -> None:
    pointer = tmp_path / "active-project.json"
    lease = "https://example.test/coordination.git"
    pointer.write_text(
        json.dumps({"owner_session": "A", "owner_lease": lease}),
        encoding="utf-8",
    )
    result: list[Path | None] = []
    done = threading.Event()

    def release_a() -> None:
        result.append(MODULE.archive_owned_pointer(pointer, "A", lease))
        done.set()

    with MODULE.locked_pointer(pointer):
        thread = threading.Thread(target=release_a)
        thread.start()
        assert not done.wait(0.1)
        pointer.write_text(
            json.dumps({"owner_session": "B", "owner_lease": lease}),
            encoding="utf-8",
        )

    thread.join(timeout=2)
    assert done.is_set()
    assert result == [None]
    assert json.loads(pointer.read_text(encoding="utf-8"))["owner_session"] == "B"


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
    assert "Schema: v3" in text
    assert "Keep this handoff." in text
    assert uuid.UUID(migrated[0].session_uuid).version == 7
    assert migrated[0].legacy_id == "A"
    assert migrated[0].compact_id.startswith("s-")
    assert migrated[0].speakable_id.count("-") == 4
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


def test_doctor_accepts_valid_v3_board(tmp_path: Path) -> None:
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


def test_doctor_rejects_alias_not_derived_from_uuid(tmp_path: Path) -> None:
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
    text = board.read_text(encoding="utf-8")
    [session] = MODULE.rows(text)
    replacement = session.compact_id[:-1] + (
        "0" if session.compact_id[-1] != "0" else "1"
    )
    board.write_text(text.replace(session.compact_id, replacement), encoding="utf-8")

    assert MODULE.command_doctor(args(board)) == 1


def test_allocator_rejects_cross_representation_alias_collision() -> None:
    first = MODULE.new_identity([], legacy_id="A")

    # The allocator treats a Crockford-equivalent legacy alias as occupied.
    with pytest.raises(ValueError, match="already in use"):
        MODULE.new_identity([first], legacy_id=first.compact_id.upper())


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
    by_id = {row.legacy_id: row for row in table}
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
    identifiers = {row.legacy_id for row in table}
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
    assert {row.legacy_id for row in table} == {"A"}

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
