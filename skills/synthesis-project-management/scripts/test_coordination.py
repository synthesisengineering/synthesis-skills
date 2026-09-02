from __future__ import annotations

import importlib.util
import ast
import json
import platform
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml


MODULE_PATH = Path(__file__).with_name("coordination.py")
SPEC = importlib.util.spec_from_file_location("coordination", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


@pytest.fixture(autouse=True)
def _isolate_client_session_env(monkeypatch):
    """Keep the suite hermetic: a developer shell inside a real client session
    carries that session's ref, which would register one seat on every
    simulated session and trip the duplicate-ref refusal."""
    monkeypatch.delenv("SYNTHESIS_CLIENT_SESSION_REF", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_HOST_SESSION_ID", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.delenv("CLAUDECODE", raising=False)


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


def staged_repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(
        ["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=root, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=root, check=True
    )
    return root


def git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def claim_staged_repository(
    board: Path,
    root: Path,
    *,
    session_id: str = "A",
    workspace: str | None = None,
    area: str | None = None,
):
    request = claim_args(
        board,
        session_id=session_id,
        project="project-a",
        workspace=workspace or f"{root} @ main",
        area=area or f"{root}/claimed/**",
    )
    assert MODULE.command_claim(request) == 0
    return MODULE.rows(board.read_text(encoding="utf-8"))[0]


def check_staged_args(
    board: Path,
    root: Path,
    *,
    session_id: str | None = "A",
    active_project_file: Path | None = None,
    override_reason: str | None = None,
):
    return args(
        board,
        id=session_id,
        repository=root,
        active_project_file=(active_project_file or root / "active-project.json"),
        override_reason=override_reason,
        json=True,
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
    assert "Schema: v4" in text
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
    strict = args(board, sender="B", to="A", text="Sequencing update.")
    assert MODULE.command_message(strict) == 10
    message = args(
        board, sender="B", to="A", text="Sequencing update.", free_address=True
    )
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


def test_r4_staged_paths_inside_claim_issue_bound_receipt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = staged_repository(tmp_path)
    claimed = root / "claimed"
    claimed.mkdir()
    (claimed / "inside.md").write_text("inside\n", encoding="utf-8")
    assert git(root, "add", "claimed/inside.md").returncode == 0
    board = tmp_path / "coordination" / "active-sessions.md"
    session = claim_staged_repository(board, root)
    capsys.readouterr()

    assert MODULE.command_check_staged(check_staged_args(board, root)) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["control_class"] == "enforced-gate"
    assert payload["enforcement_outcome"] == "passed-inside-claim"
    assert payload["issues_authority_receipt"] is True
    assert payload["receipt"]["session_uuid"] == session.session_uuid
    assert payload["receipt"]["repository"] == str(root)
    assert payload["receipt"]["branch"] == "main"
    assert payload["receipt"]["enforcement_outcome"] == "passed-inside-claim"
    assert payload["receipt"]["outside_paths"] == []
    assert payload["receipt"]["staged_paths"] == ["claimed/inside.md"]
    assert payload["receipt"]["staged_tree"] == git(root, "write-tree").stdout.strip()
    assert payload["unverified_remainder"]


def test_r4_staged_path_outside_claim_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = staged_repository(tmp_path)
    (root / "outside.md").write_text("outside\n", encoding="utf-8")
    assert git(root, "add", "outside.md").returncode == 0
    board = tmp_path / "active-sessions.md"
    claim_staged_repository(board, root)
    capsys.readouterr()

    assert MODULE.command_check_staged(check_staged_args(board, root)) == 10
    payload = json.loads(capsys.readouterr().out)

    assert payload["enforcement_outcome"] == "refused-outside-claim"
    assert payload["issues_authority_receipt"] is False
    assert payload["outside_paths"] == ["outside.md"]
    assert "isolated worktree" in payload["remediation"]


def test_r4_rename_from_unclaimed_path_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = staged_repository(tmp_path)
    (root / "unclaimed.md").write_text("baseline\n", encoding="utf-8")
    assert git(root, "add", "unclaimed.md").returncode == 0
    assert git(root, "commit", "-m", "Baseline").returncode == 0
    (root / "claimed").mkdir()
    assert git(root, "mv", "unclaimed.md", "claimed/renamed.md").returncode == 0
    board = tmp_path / "active-sessions.md"
    claim_staged_repository(board, root)
    capsys.readouterr()

    assert MODULE.command_check_staged(check_staged_args(board, root)) == 10
    payload = json.loads(capsys.readouterr().out)

    assert payload["enforcement_outcome"] == "refused-outside-claim"
    assert payload["outside_paths"] == ["unclaimed.md"]


def test_r4_active_pointer_resolves_committing_session(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # AGENT HEURISTIC: this fixture exercises pointer fallback, so the caller's
    # real coordination identity must not silently replace the fixture input.
    monkeypatch.delenv("SYNTHESIS_COORDINATION_SESSION", raising=False)
    root = staged_repository(tmp_path)
    (root / "claimed").mkdir()
    (root / "claimed" / "inside.md").write_text("inside\n", encoding="utf-8")
    assert git(root, "add", "claimed/inside.md").returncode == 0
    board = tmp_path / "active-sessions.md"
    session = claim_staged_repository(board, root)
    pointer = tmp_path / "active-project.json"
    pointer.write_text(
        json.dumps({"owner_session": session.session_uuid}), encoding="utf-8"
    )
    capsys.readouterr()

    request = check_staged_args(
        board, root, session_id=None, active_project_file=pointer
    )
    assert MODULE.command_check_staged(request) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["selector_source"] == "active-project"
    assert payload["receipt"]["session_uuid"] == session.session_uuid


def test_r4_recorded_override_binds_reason_and_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = staged_repository(tmp_path)
    (root / "outside.md").write_text("outside\n", encoding="utf-8")
    assert git(root, "add", "outside.md").returncode == 0
    board = tmp_path / "active-sessions.md"
    claim_staged_repository(board, root)
    capsys.readouterr()

    request = check_staged_args(
        board,
        root,
        override_reason="Urgent repair with explicit operator accountability",
    )
    assert MODULE.command_check_staged(request) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["enforcement_outcome"] == "recorded-override"
    assert payload["issues_authority_receipt"] is True
    assert payload["receipt"]["enforcement_outcome"] == "recorded-override"
    assert payload["receipt"]["outside_paths"] == ["outside.md"]
    assert payload["receipt"]["override_reason"].startswith("Urgent repair")
    assert payload["receipt"]["staged_paths"] == ["outside.md"]
    board_text = board.read_text(encoding="utf-8")
    assert "recorded-staged-claim-override" in board_text
    assert "Urgent repair with explicit operator accountability" in board_text
    assert "outside.md" in board_text


def test_r4_inactive_session_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = staged_repository(tmp_path)
    (root / "claimed").mkdir()
    (root / "claimed" / "inside.md").write_text("inside\n", encoding="utf-8")
    assert git(root, "add", "claimed/inside.md").returncode == 0
    board = tmp_path / "active-sessions.md"
    claim_staged_repository(board, root)
    assert MODULE.command_release(args(board, id="A", active_project_file=None)) == 0
    capsys.readouterr()

    assert MODULE.command_check_staged(check_staged_args(board, root)) == 10
    payload = json.loads(capsys.readouterr().out)

    assert payload["enforcement_outcome"] == "refused-inactive-session"
    assert payload["issues_authority_receipt"] is False


def test_r4_lease_fence_cannot_resurrect_released_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = staged_repository(tmp_path)
    claimed = root / "claimed"
    claimed.mkdir()
    (claimed / "inside.md").write_text("inside\n", encoding="utf-8")
    assert git(root, "add", "claimed/inside.md").returncode == 0
    machine1, machine2 = lease_machines(tmp_path)
    claim_staged_repository(machine1, root)
    capsys.readouterr()

    original_fetch = MODULE.lease_fetch
    raced = False

    def release_after_stale_fetch(config):
        nonlocal raced
        sha, content = original_fetch(config)
        if not raced:
            raced = True
            assert MODULE.command_release(args(machine2, id="A")) == 0
        return sha, content

    monkeypatch.setattr(MODULE, "lease_fetch", release_after_stale_fetch)

    exit_code = MODULE.command_check_staged(
        check_staged_args(machine1, root)
    )
    output = capsys.readouterr().out
    payload = json.loads(output[output.index("{") :])

    assert raced is True
    assert exit_code == 10
    assert payload["enforcement_outcome"] == "refused-inactive-session"
    assert MODULE.rows(machine1.read_text(encoding="utf-8"))[0].status == "released"


def test_r4_unregistered_worktree_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = staged_repository(tmp_path)
    (root / "inside.md").write_text("inside\n", encoding="utf-8")
    assert git(root, "add", "inside.md").returncode == 0
    board = tmp_path / "active-sessions.md"
    claim_staged_repository(
        board,
        root,
        workspace=f"{tmp_path / 'different-worktree'} @ main",
        area=f"{root}/**",
    )
    capsys.readouterr()

    assert MODULE.command_check_staged(check_staged_args(board, root)) == 10
    payload = json.loads(capsys.readouterr().out)

    assert payload["enforcement_outcome"] == "refused-unregistered-worktree"
    assert "isolated worktree" in payload["remediation"]
    assert "claim" in payload["remediation"]


def test_r4_workspace_conflict_names_isolated_worktree_remedy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    board = tmp_path / "active-sessions.md"
    first = claim_args(
        board,
        session_id="A",
        project="project-a",
        workspace="/tmp/shared-worktree @ feature/shared",
        area="/tmp/one/**",
    )
    second = claim_args(
        board,
        session_id="B",
        project="project-b",
        workspace="/tmp/shared-worktree @ feature/shared",
        area="/tmp/two/**",
    )
    assert MODULE.command_claim(first) == 0
    capsys.readouterr()

    assert MODULE.command_claim(second) == 10
    error = capsys.readouterr().err

    assert "isolated worktree" in error
    assert "distinct branch" in error
    assert "claim" in error


def test_r4_missing_board_is_unverifiable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = staged_repository(tmp_path)
    (root / "inside.md").write_text("inside\n", encoding="utf-8")
    assert git(root, "add", "inside.md").returncode == 0
    board = tmp_path / "missing-board.md"

    assert MODULE.command_check_staged(check_staged_args(board, root)) == 10
    payload = json.loads(capsys.readouterr().out)

    assert payload["control_class"] == "enforced-gate"
    assert payload["enforcement_outcome"] == "unverifiable-missing-board"
    assert payload["issues_authority_receipt"] is False
    assert payload["unverified_remainder"]


def test_r4_glob_claim_does_not_authorize_deeper_sibling_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = staged_repository(tmp_path)
    nested = root / "claimed" / "nested"
    nested.mkdir(parents=True)
    (nested / "outside.txt").write_text("outside\n", encoding="utf-8")
    assert git(root, "add", "claimed/nested/outside.txt").returncode == 0
    board = tmp_path / "active-sessions.md"
    claim_staged_repository(
        board,
        root,
        area=f"{root}/claimed/*.md",
    )
    capsys.readouterr()

    assert MODULE.command_check_staged(check_staged_args(board, root)) == 10
    payload = json.loads(capsys.readouterr().out)

    assert payload["enforcement_outcome"] == "refused-outside-claim"
    assert payload["outside_paths"] == ["claimed/nested/outside.txt"]


def test_r4_symlink_alias_claim_matches_resolved_worktree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = staged_repository(tmp_path)
    claimed = root / "claimed"
    claimed.mkdir()
    (claimed / "inside.md").write_text("inside\n", encoding="utf-8")
    assert git(root, "add", "claimed/inside.md").returncode == 0
    alias = tmp_path / "repo-alias"
    alias.symlink_to(root, target_is_directory=True)
    board = tmp_path / "active-sessions.md"
    claim_staged_repository(
        board,
        root,
        workspace=f"{alias} @ main",
        area=f"{alias}/claimed/**",
    )
    capsys.readouterr()

    assert MODULE.command_check_staged(check_staged_args(board, alias)) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["enforcement_outcome"] == "passed-inside-claim"
    assert payload["outside_paths"] == []


def test_r4_acceptance_manifest_is_closed_and_resolvable() -> None:
    skill_root = Path(__file__).resolve().parents[1]
    manifest = yaml.safe_load(
        (skill_root / "acceptance-suite.yaml").read_text(encoding="utf-8")
    )

    assert manifest["schema"] == 1
    assert manifest["membership"] == "closed"
    declared = {case["fixture"] for case in manifest["cases"]}
    discovered: set[str] = set()
    for relative in (
        "scripts/test_coordination.py",
        "../synthesis-git-hooks/scripts/test_pre_commit.py",
    ):
        path = (skill_root / relative).resolve()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "test_r4_"
            ):
                discovered.add(f"{relative}::{node.name}")

    assert declared == discovered
    assert {case["control_class"] for case in manifest["cases"]} <= {
        "enforced-gate",
        "acceptance-test",
        "diagnostic",
    }

# --- stale-claim review ---------------------------------------------------
#
# A dead session's `active` row does not merely clutter the board: it denies
# work to every future claim that overlaps it. The one property that must not
# regress is that this surface NEVER mutates. An agent able to release another
# session's claim on a timer would turn the advisory lock into a suggestion.


def _stale_board(tmp_path, heartbeat, worktree, status="active"):
    board = tmp_path / "board.md"
    board.write_text(
        "Schema: v3\n## Active sessions\n"
        "| 01a01155-25a0-7c39-9af2-505104044949 | s-aaaa-bbbb-cccc | a-b-c-d-00001 |  | "
        f"Claude Code | {platform.node()} | proj | 2026-08-01T00:00:00+00:00 | {heartbeat} | "
        f"interactive | {worktree} | goal | area/** | owner | {status} |\n"
        "\n## Messages\n\n## Protocol\n"
    )
    return board


def _run_stale(board, *args):
    return subprocess.run(
        [sys.executable, str(MODULE_PATH), "--board", str(board), "stale", *args],
        capture_output=True, text=True)


def test_stale_claim_is_surfaced_with_release_command(tmp_path):
    board = _stale_board(tmp_path, "2026-01-01T00:00:00+00:00", str(tmp_path))
    r = _run_stale(board, "--threshold", "1")
    assert r.returncode == 0
    assert "s-aaaa-bbbb-cccc" in r.stdout
    assert "release --id s-aaaa-bbbb-cccc" in r.stdout


def test_stale_review_never_mutates_the_board(tmp_path):
    """The release decision belongs to the user. This surface reports only."""
    board = _stale_board(tmp_path, "2026-01-01T00:00:00+00:00", str(tmp_path))
    before = board.read_text()
    _run_stale(board, "--threshold", "1")
    assert board.read_text() == before


def test_missing_worktree_is_reported_as_likely_gone(tmp_path):
    """A vanished worktree is close to proof; elapsed time alone is not."""
    board = _stale_board(tmp_path, "2026-01-01T00:00:00+00:00",
                         str(tmp_path / "gone"))
    r = _run_stale(board, "--threshold", "1")
    assert "LIKELY GONE" in r.stdout
    assert "no longer exists" in r.stdout


def test_present_worktree_is_not_called_gone(tmp_path):
    board = _stale_board(tmp_path, "2026-01-01T00:00:00+00:00", str(tmp_path))
    r = _run_stale(board, "--threshold", "1")
    assert "LIKELY GONE" not in r.stdout
    assert "may be a live session" in r.stdout


def test_released_rows_are_not_surfaced(tmp_path):
    board = _stale_board(tmp_path, "2026-01-01T00:00:00+00:00", str(tmp_path),
                         status="released")
    r = _run_stale(board, "--threshold", "1")
    assert "s-aaaa-bbbb-cccc" not in r.stdout


def test_fresh_claim_is_not_surfaced(tmp_path):
    fresh = datetime.now(timezone.utc).isoformat()
    board = _stale_board(tmp_path, fresh, str(tmp_path))
    r = _run_stale(board, "--threshold", "1")
    assert "No claims to resolve" in r.stdout


def test_missing_board_exits_zero(tmp_path):
    r = _run_stale(tmp_path / "absent.md", "--threshold", "1")
    assert r.returncode == 0


def test_json_mode_is_machine_readable(tmp_path):
    board = _stale_board(tmp_path, "2026-01-01T00:00:00+00:00", str(tmp_path / "gone"))
    r = _run_stale(board, "--threshold", "1", "--json")
    data = json.loads(r.stdout)
    assert data["stale_total"] == 1
    assert data["shown"][0]["worktree_gone"] is True


# --- peer-session resolution (schema v4 client refs) -----------------------
#
# The board is the only join between coordination identity and each client's
# native delivery handle. These tests pin the whole contract: registration at
# claim time, one row per client seat, fail-closed ambiguity in resolve, and
# the staged v3→v4 migration that keeps older parsers alive on shared boards.


def seatless_claim(board, project, workspace, area, agent="seat"):
    return args(
        board,
        id=None,
        agent=agent,
        machine="machine-seat",
        project=project,
        mode="interactive",
        goal=f"goal-{project}",
        workspace=[workspace],
        area=[area],
        context_role="owner",
    )


def resolve_args(board, to, **overrides):
    values = {
        "to": to,
        "role": None,
        "include_released": False,
        "stale_after_minutes": 240,
        "json": False,
    }
    values.update(overrides)
    return args(board, **values)


def test_claim_registers_detected_client_ref(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_HOST_SESSION_ID", "local_feed-beef")
    board = tmp_path / "board.md"
    request = claim_args(
        board,
        session_id="A",
        project="project-a",
        workspace="/tmp/wt-a @ feature/a",
        area="repo-a/**",
    )
    assert MODULE.command_claim(request) == 0
    row = MODULE.rows(board.read_text(encoding="utf-8"))[0]
    assert row.client_ref == "ccd:local_feed-beef"
    assert "| ccd:local_feed-beef |" in board.read_text(encoding="utf-8")


def test_generic_ref_env_overrides_client_specific(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_HOST_SESSION_ID", "local_feed-beef")
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:0a0a-1b1b")
    board = tmp_path / "board.md"
    assert (
        MODULE.command_claim(
            seatless_claim(board, "project-a", "/tmp/wt-a @ feature/a", "repo-a/**")
        )
        == 0
    )
    assert MODULE.rows(board.read_text(encoding="utf-8"))[0].client_ref == (
        "codex:0a0a-1b1b"
    )


def test_claim_reuses_active_row_for_same_client_seat(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_HOST_SESSION_ID", "local_feed-beef")
    board = tmp_path / "board.md"
    assert (
        MODULE.command_claim(
            seatless_claim(board, "project-a", "/tmp/wt-a @ feature/a", "repo-a/**")
        )
        == 0
    )
    first = MODULE.rows(board.read_text(encoding="utf-8"))[0]
    assert (
        MODULE.command_claim(
            seatless_claim(board, "project-b", "/tmp/wt-b @ feature/b", "repo-b/**")
        )
        == 0
    )
    table = MODULE.rows(board.read_text(encoding="utf-8"))
    assert len(table) == 1
    assert table[0].session_uuid == first.session_uuid
    assert table[0].project == "project-b"


def test_second_seat_with_same_ref_and_selector_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_HOST_SESSION_ID", "local_feed-beef")
    board = tmp_path / "board.md"
    first = claim_args(
        board,
        session_id="A",
        project="project-a",
        workspace="/tmp/wt-a @ feature/a",
        area="repo-a/**",
    )
    assert MODULE.command_claim(first) == 0
    second = claim_args(
        board,
        session_id="B",
        project="project-b",
        workspace="/tmp/wt-b @ feature/b",
        area="repo-b/**",
    )
    assert MODULE.command_claim(second) == 10


def test_explicit_invalid_client_ref_refuses(tmp_path):
    board = tmp_path / "board.md"
    request = seatless_claim(
        board, "project-a", "/tmp/wt-a @ feature/a", "repo-a/**"
    )
    request.client_ref = "not a scheme ref"
    assert MODULE.command_claim(request) == 10
    assert not board.exists()


def _v3_board(tmp_path):
    board = tmp_path / "board.md"
    board.write_text(
        "# Coordination\n\nSchema: v3\n\n## Active sessions\n\n"
        + MODULE.table_header(MODULE.V3_COLUMNS)
        + "\n\n## Messages\n\n---\n\n## Protocol\n",
        encoding="utf-8",
    )
    return board


def test_v3_board_keeps_schema_until_explicit_migrate(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_HOST_SESSION_ID", "local_feed-beef")
    board = _v3_board(tmp_path)
    assert (
        MODULE.command_claim(
            seatless_claim(board, "project-a", "/tmp/wt-a @ feature/a", "repo-a/**")
        )
        == 0
    )
    text = board.read_text(encoding="utf-8")
    assert "Schema: v3" in text
    assert "ccd:" not in text
    row = MODULE.rows(text)[0]
    assert row.client_ref == ""

    assert MODULE.command_migrate(args(board)) == 0
    migrated = board.read_text(encoding="utf-8")
    assert "Schema: v4" in migrated
    assert "| client session ref |" in migrated

    request = seatless_claim(
        board, "project-a", "/tmp/wt-a @ feature/a", "repo-a/**"
    )
    request.id = row.compact_id
    assert MODULE.command_claim(request) == 0
    assert "ccd:local_feed-beef" in board.read_text(encoding="utf-8")


def test_resolve_unique_project_target(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_CODE_HOST_SESSION_ID", "local_feed-beef")
    board = tmp_path / "board.md"
    assert (
        MODULE.command_claim(
            seatless_claim(board, "project-a", "/tmp/wt-a @ feature/a", "repo-a/**")
        )
        == 0
    )
    assert MODULE.command_resolve(resolve_args(board, "project-a")) == 0
    output = capsys.readouterr().out
    assert "ccd send_message to session_id local_feed-beef" in output


def test_resolve_by_bare_local_ref(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_CODE_HOST_SESSION_ID", "local_feed-beef")
    board = tmp_path / "board.md"
    assert (
        MODULE.command_claim(
            seatless_claim(board, "project-a", "/tmp/wt-a @ feature/a", "repo-a/**")
        )
        == 0
    )
    capsys.readouterr()
    request = resolve_args(board, "local_feed-beef", json=True)
    assert MODULE.command_resolve(request) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["matched_by"] == "client-ref"
    assert payload["matches"][0]["client_ref"] == "ccd:local_feed-beef"


def test_resolve_ambiguity_refuses_instead_of_broadcasting(tmp_path, capsys):
    board = tmp_path / "board.md"
    owner = claim_args(
        board,
        session_id="A",
        project="project-a",
        workspace="/tmp/wt-a @ feature/a",
        area="repo-a/impl/**",
    )
    assert MODULE.command_claim(owner) == 0
    helper = claim_args(
        board,
        session_id="B",
        project="project-a",
        workspace="/tmp/wt-b @ feature/b",
        area="repo-a/docs/**",
        context_role="contributor",
    )
    assert MODULE.command_claim(helper) == 0
    assert MODULE.command_resolve(resolve_args(board, "project-a")) == 20
    err = capsys.readouterr().err
    assert "do not broadcast" in err
    assert (
        MODULE.command_resolve(resolve_args(board, "project-a", role="owner"))
        == 0
    )


def test_resolve_unknown_target_points_to_board_bus(tmp_path, capsys):
    board = tmp_path / "board.md"
    assert (
        MODULE.command_claim(
            seatless_claim(board, "project-a", "/tmp/wt-a @ feature/a", "repo-a/**")
        )
        == 0
    )
    assert MODULE.command_resolve(resolve_args(board, "project-zz")) == 21
    err = capsys.readouterr().err
    assert "board message bus" in err
    assert "do not guess" in err


def test_message_to_registered_project_renders_sessions_address(tmp_path):
    board = tmp_path / "board.md"
    assert (
        MODULE.command_claim(
            seatless_claim(board, "project-a", "/tmp/wt-a @ feature/a", "repo-a/**")
        )
        == 0
    )
    message = args(board, sender="ops", to="project-a", text="Handoff ready.")
    assert MODULE.command_message(message) == 0
    text = board.read_text(encoding="utf-8")
    assert "→ project-a sessions," in text
    suffixed = args(
        board, sender="ops", to="project-a sessions", text="Second note."
    )
    assert MODULE.command_message(suffixed) == 0


def test_status_json_reports_client_ref_and_board_schema(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("CLAUDE_CODE_HOST_SESSION_ID", "local_feed-beef")
    board = tmp_path / "board.md"
    assert (
        MODULE.command_claim(
            seatless_claim(board, "project-a", "/tmp/wt-a @ feature/a", "repo-a/**")
        )
        == 0
    )
    capsys.readouterr()
    status = args(
        board, json=True, strict=False, stale_after_minutes=240
    )
    assert MODULE.command_status(status) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["board_schema"] == 4
    assert payload["sessions"][0]["client_ref"] == "ccd:local_feed-beef"


def test_peer_resolution_documented_on_public_surfaces() -> None:
    """The protocol must live on every public maintenance surface, not only
    in code — undocumented mechanisms get rediscovered as folklore."""
    repo = Path(__file__).resolve().parents[3]
    skill_dir = repo / "skills" / "synthesis-project-management"
    surfaces = {
        repo / "README.md": "resolve",
        repo / "CHANGELOG.md": "client session ref",
        skill_dir / "SKILL.md": "client session ref",
        skill_dir / "references" / "parallel-agent-protocol.md": (
            "Addressing a peer session"
        ),
        skill_dir / "references" / "session-identity.md": "client session ref",
        repo / "skills" / "synthesis-message-guard" / "SKILL.md": (
            "peer_send_resolution"
        ),
    }
    for path, marker in surfaces.items():
        assert marker in path.read_text(encoding="utf-8"), (
            f"{path.name} does not document {marker!r}"
        )


def test_conformance_board_check_accepts_declared_v3_and_v4(tmp_path) -> None:
    """The parity checker must accept both declared schemas during the staged
    migration window, and still reject anything older."""
    conformance_path = (
        Path(__file__).resolve().parents[2]
        / "synthesis-agent-conformance"
        / "scripts"
        / "conformance.py"
    )
    spec = importlib.util.spec_from_file_location(
        "conformance_for_board_check", conformance_path
    )
    assert spec and spec.loader
    conformance = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = conformance
    spec.loader.exec_module(conformance)

    def board_with(schema_line: str) -> Path:
        board = tmp_path / f"board-{schema_line.split('v')[-1]}.md"
        columns = (
            MODULE.TABLE_COLUMNS
            if schema_line.endswith("v4")
            else MODULE.V3_COLUMNS
        )
        board.write_text(
            f"# Coordination\n\n{schema_line}\n\n## Active sessions\n\n"
            + MODULE.table_header(columns)
            + "\n\n## Messages\n\n---\n\n## Protocol\n",
            encoding="utf-8",
        )
        return board

    def schema_check(board: Path) -> bool:
        checks = conformance.coordination_checks(board, required=False)
        return next(
            check.ok
            for check in checks
            if check.name == "coordination.active-table-schema"
        )

    assert schema_check(board_with("Schema: v4"))
    assert schema_check(board_with("Schema: v3"))
    assert not schema_check(board_with("Schema: v2"))


def test_skill_document_stays_within_repo_budget() -> None:
    """AGENTS.md: keep SKILL.md below 500 lines; detailed material lives in
    references/. The 2026-09-01 restructure moved formats, rationale, and
    mechanics out of the main document; this pins the budget, keeps the
    load-bearing rules in the main document, verifies each moved block still
    exists in its reference, and requires every content reference to be
    linked so nothing becomes an orphan."""
    skill_dir = Path(__file__).resolve().parents[1]
    skill = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert len(skill.splitlines()) < 500, "SKILL.md broke the 500-line budget"

    for rule_anchor in (
        "### Cross-Agent Session Coordination",
        "addresses are resolved, never guessed",
        "Generic verbs are banned",
        "Archive FIRST, delete second",
        "## Project Discovery",
        "Git-index collisions.",
    ):
        assert rule_anchor in skill, f"load-bearing rule left SKILL.md: {rule_anchor}"

    refs = skill_dir / "references"
    for reference_name, marker in (
        ("records-and-conventions.md", "Single-tool."),
        ("records-and-conventions.md", "adds ceremony, not information"),
        ("records-and-conventions.md", "type: incident"),
        ("records-and-conventions.md", "this is provenance, not telemetry"),
        ("codex-dispatch.md", "Reading additional input from stdin"),
        ("parallel-agent-protocol.md", "selector precedence"),
        ("parallel-agent-protocol.md", "active-project-history"),
        ("parallel-agent-protocol.md", "SYNTHESIS_HANDOFF_SELF"),
        ("parallel-agent-protocol.md", "resumable intent"),
    ):
        text = (refs / reference_name).read_text(encoding="utf-8")
        assert marker in text, f"moved block missing from {reference_name}: {marker}"

    for reference in refs.glob("*.md"):
        if reference.name == "session-words-v1.LICENSE.md":
            continue
        assert reference.name in skill, f"unlinked reference: {reference.name}"


# --- engine/board version skew and section hygiene (4.78.0) ------------------


def _claimed_board(tmp_path, *, schema=None, padding=0):
    board = tmp_path / "board.md"
    assert (
        MODULE.command_claim(
            seatless_claim(board, "project-a", "/tmp/wt-a @ feature/a", "repo-a/**")
        )
        == 0
    )
    text = board.read_text(encoding="utf-8")
    if schema is not None:
        text = re.sub(r"(?m)^Schema: v\d+$", f"Schema: v{schema}", text, count=1)
    if padding:
        text = text.replace(
            "## Active sessions\n", "## Active sessions\n" + "\n" * padding, 1
        )
    board.write_text(text, encoding="utf-8")
    return board


def test_rows_refuses_a_board_newer_than_the_engine(tmp_path, capsys):
    """The 2026-09-01 incident inverted: a stale engine must diagnose itself
    instead of reporting the shared board as corrupt, and must never rewrite
    a board written by a newer engine."""
    newer = MODULE.SCHEMA_VERSION + 1
    board = _claimed_board(tmp_path, schema=newer)
    text = board.read_text(encoding="utf-8")

    with pytest.raises(ValueError) as caught:
        MODULE.rows(text)
    message = str(caught.value)
    assert f"schema v{newer}" in message
    assert f"newer than this engine's v{MODULE.SCHEMA_VERSION}" in message
    assert "coordination.py" in message  # the remedy names an engine path

    assert MODULE.command_doctor(args(board)) == 1
    assert "newer than this engine" in capsys.readouterr().err
    assert board.read_text(encoding="utf-8") == text  # untouched


def test_wider_rows_than_the_engine_knows_name_the_newer_engine(tmp_path):
    board = _claimed_board(tmp_path)
    text = board.read_text(encoding="utf-8")
    row_uuid = MODULE.rows(text)[0].session_uuid
    lines = text.splitlines()
    index = next(i for i, line in enumerate(lines) if row_uuid in line)
    lines[index] = lines[index] + " future-column |"

    with pytest.raises(ValueError) as caught:
        MODULE.rows("\n".join(lines))
    message = str(caught.value)
    assert f"{len(MODULE.V4_COLUMNS) + 1} columns" in message
    assert "written by a newer engine" in message

    lines[index] = "| " + " | ".join(["x"] * (len(MODULE.V1_COLUMNS) + 1)) + " |"
    with pytest.raises(ValueError) as narrower:
        MODULE.rows("\n".join(lines))
    assert "malformed row" in str(narrower.value)


def test_replace_table_collapses_padding_and_stays_fixed(tmp_path):
    """Every rewrite used to grow the blank run under the heading by one line;
    a rewrite now emits a fixed-shape section and is idempotent."""
    board = _claimed_board(tmp_path, padding=500)
    text = board.read_text(encoding="utf-8")

    once = MODULE.replace_table(text, MODULE.rows(text))
    section = once.split("## Active sessions\n", 1)[1].split("## Messages", 1)[0]
    assert section.startswith("\n| session uuid |")
    assert section.endswith("|\n\n")
    assert len(once.splitlines()) == len(text.splitlines()) - 500

    twice = MODULE.replace_table(once, MODULE.rows(once))
    assert twice == once


def test_engine_remedy_names_the_newest_cached_engine(tmp_path):
    cache = tmp_path / "plugins" / "synthesis-skills"
    relative = Path("skills") / "synthesis-project-management" / "scripts" / "coordination.py"
    for version in ("4.74.1", "4.78.0", "4.9.0"):
        script = cache / version / relative
        script.parent.mkdir(parents=True)
        script.write_text("#\n", encoding="utf-8")

    stale = MODULE.engine_remedy(cache / "4.74.1" / relative)
    assert str(cache / "4.78.0" / relative) in stale
    assert "4.9.0" not in stale  # numeric ordering, not lexical

    newest = MODULE.engine_remedy(cache / "4.78.0" / relative)
    assert "newest installed" in newest and "refresh the plugin" in newest

    outside = MODULE.engine_remedy(tmp_path / "src" / "coordination.py")
    assert "not from a versioned plugin cache" in outside


def test_version_skew_documented_on_public_surfaces():
    skill_root = MODULE_PATH.parents[1]
    repo_root = MODULE_PATH.parents[3]
    identity = (skill_root / "references" / "session-identity.md").read_text(
        encoding="utf-8"
    )
    assert "## Engine older than board" in identity
    assert "than the running engine" in identity
    template = (skill_root / "references" / "active-sessions-template.md").read_text(
        encoding="utf-8"
    )
    assert "Schema: v4" in template
    assert "| client session ref |" in template
    changelog = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [4.78.0]" in changelog
    assert "names the engine to run" in changelog


def test_cli_presents_a_refusal_as_one_error_line(tmp_path):
    board = _claimed_board(tmp_path, schema=MODULE.SCHEMA_VERSION + 1)
    done = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--board", str(board), "status"],
        capture_output=True, text=True, check=False,
    )
    assert done.returncode == 1
    assert done.stderr.startswith("error: board declares schema v")
    assert "Traceback" not in done.stderr


def test_every_command_notes_a_newer_installed_engine(tmp_path):
    """The resolved-path foot-gun: a session keeps a versioned path for hours
    while releases ship. Every invocation from an older cached engine now says
    so on stderr, naming the newer path, without changing its behavior."""
    cache = tmp_path / "plugins" / "synthesis-skills"
    relative = Path("skills") / "synthesis-project-management" / "scripts"
    older = cache / "4.80.0" / relative
    older.mkdir(parents=True)
    for name in ("coordination.py", "coordination_schema.py", "pointer_lock.py", "peer_addressing.py"):
        (older / name).write_bytes((MODULE_PATH.parent / name).read_bytes())
    newer = cache / "4.81.0" / relative
    newer.mkdir(parents=True)
    (newer / "coordination.py").write_text("#\n", encoding="utf-8")

    done = subprocess.run(
        [sys.executable, str(older / "coordination.py"), "--board", str(tmp_path / "board.md"), "doctor"],
        capture_output=True, text=True, check=False,
    )
    assert "note: this coordination engine is 4.80.0 but 4.81.0 is installed" in done.stderr
    assert str(newer / "coordination.py") in done.stderr

    current = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--board", str(tmp_path / "board.md"), "doctor"],
        capture_output=True, text=True, check=False,
    )
    assert "note: this coordination engine" not in current.stderr

