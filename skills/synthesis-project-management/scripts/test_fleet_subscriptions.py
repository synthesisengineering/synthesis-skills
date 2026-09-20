"""Machine workspace subscriptions in the commit gate.

A machine may only commit staged paths its subscriptions cover. Refusals
name the machine and the needed subscription; ``--override-subscription``
escapes once with a board-logged reason. An unenrolled fleet (no registry)
passes, so single-machine history keeps working.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import coordination as MODULE
import fleet_identity as FI
import fleet_subscriptions as SUBS


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    for name in (
        "SYNTHESIS_CLIENT_SESSION_REF",
        "SYNTHESIS_COORDINATION_SESSION",
        "CLAUDE_CODE_HOST_SESSION_ID",
        "CLAUDE_CODE_SESSION_ID",
        "CLAUDE_PID",
        "CLAUDECODE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(tmp_path / "fleet"))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:owner-subs")


def args(board: Path, **values):
    return type("Args", (), {"board": board, **values})()


def claim_args(board, *, session_id, project, workspace, area, machine="mac-a"):
    return args(
        board,
        id=session_id,
        agent=f"agent-{session_id}",
        machine=machine,
        project=project,
        mode="autonomous",
        goal=f"goal-{session_id}",
        workspace=[workspace],
        area=[area],
        context_role="owner",
        replace=False,
        client_ref=None,
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
        ["git", "config", "user.email", "test@example.com"],
        cwd=root,
        check=True,
    )
    return root


def git(root: Path, *arguments: str):
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def claim_staged_repository(board: Path, root: Path):
    request = claim_args(
        board,
        session_id="A",
        project="project-a",
        workspace=f"{root} @ main",
        area=f"{root}/claimed/**",
    )
    assert MODULE.command_claim(request) == 0
    return MODULE.rows(board.read_text(encoding="utf-8"))[0]


def check_staged_args(board, root, *, override_subscription=None):
    return args(
        board,
        id="A",
        repository=root,
        active_project_file=root / "active-project.json",
        override_reason=None,
        override_subscription=override_subscription,
        json=True,
    )


def enroll_machine(fleet_dir: Path, label: str = "mac-a") -> str:
    machine_id = FI.mint_machine_id(fleet_dir)
    FI.enroll_self(label=label, role="primary", directory=fleet_dir)
    return machine_id


def write_subscriptions(fleet_dir: Path, machine_id: str, areas: list[str]):
    SUBS.write_registry(
        {
            "schema_version": 1,
            "subscriptions": {
                machine_id: {"label": "mac-a", "areas": areas}
            },
        },
        fleet_dir,
    )


def stage(root: Path, relative: str):
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("staged\n", encoding="utf-8")
    assert git(root, "add", relative).returncode == 0


def test_unenrolled_fleet_passes_without_registry(tmp_path, capsys):
    root = staged_repository(tmp_path)
    stage(root, "claimed/inside.md")
    board = tmp_path / "active-sessions.md"
    claim_staged_repository(board, root)
    capsys.readouterr()

    assert MODULE.command_check_staged(check_staged_args(board, root)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["enforcement_outcome"] == "passed-inside-claim"
    assert "subscription_override" not in payload["receipt"]


def test_subscribed_paths_pass(tmp_path, capsys):
    fleet_dir = tmp_path / "fleet"
    machine_id = enroll_machine(fleet_dir)
    write_subscriptions(fleet_dir, machine_id, [f"{tmp_path}/repo/**"])
    root = staged_repository(tmp_path)
    stage(root, "claimed/inside.md")
    board = tmp_path / "active-sessions.md"
    claim_staged_repository(board, root)
    capsys.readouterr()

    assert MODULE.command_check_staged(check_staged_args(board, root)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["enforcement_outcome"] == "passed-inside-claim"


def test_unsubscribed_paths_refuse_naming_machine_and_subscription(
    tmp_path, capsys
):
    fleet_dir = tmp_path / "fleet"
    machine_id = enroll_machine(fleet_dir)
    write_subscriptions(fleet_dir, machine_id, [f"{tmp_path}/repo/docs/**"])
    root = staged_repository(tmp_path)
    stage(root, "claimed/inside.md")
    board = tmp_path / "active-sessions.md"
    claim_staged_repository(board, root)
    capsys.readouterr()

    assert MODULE.command_check_staged(check_staged_args(board, root)) == 10
    payload = json.loads(capsys.readouterr().out)
    assert payload["enforcement_outcome"] == "refused-unsubscribed-workspace"
    assert payload["issues_authority_receipt"] is False
    assert payload["outside_paths"] == ["claimed/inside.md"]
    assert "mac-a" in payload["detail"]
    assert machine_id in payload["detail"]
    assert "Needed subscription" in payload["detail"]
    assert "--override-subscription" in payload["detail"]


def test_unlisted_machine_refuses_loudly(tmp_path, capsys):
    fleet_dir = tmp_path / "fleet"
    machine_id = enroll_machine(fleet_dir, label="mac-b")
    other_id = "12345678-1234-4234-8234-1234567890ab"
    SUBS.write_registry(
        {
            "schema_version": 1,
            "subscriptions": {other_id: {"label": "mac-a", "areas": ["/tmp/**"]}},
        },
        fleet_dir,
    )
    root = staged_repository(tmp_path)
    stage(root, "claimed/inside.md")
    board = tmp_path / "active-sessions.md"
    claim_staged_repository(board, root)
    capsys.readouterr()

    assert MODULE.command_check_staged(check_staged_args(board, root)) == 10
    payload = json.loads(capsys.readouterr().out)
    assert payload["enforcement_outcome"] == "refused-unsubscribed-workspace"
    assert machine_id in payload["detail"]
    assert "not listed in subscriptions.json" in payload["detail"]


def test_malformed_registry_fails_closed(tmp_path, capsys):
    fleet_dir = tmp_path / "fleet"
    enroll_machine(fleet_dir)
    (fleet_dir / "subscriptions.json").write_text(
        '{"schema_version": 99}', encoding="utf-8"
    )
    root = staged_repository(tmp_path)
    stage(root, "claimed/inside.md")
    board = tmp_path / "active-sessions.md"
    claim_staged_repository(board, root)
    capsys.readouterr()

    assert MODULE.command_check_staged(check_staged_args(board, root)) == 10
    payload = json.loads(capsys.readouterr().out)
    assert payload["enforcement_outcome"] == "unverifiable-subscriptions"


def test_override_subscription_passes_and_logs_on_board(tmp_path, capsys):
    fleet_dir = tmp_path / "fleet"
    machine_id = enroll_machine(fleet_dir)
    write_subscriptions(fleet_dir, machine_id, [f"{tmp_path}/repo/docs/**"])
    root = staged_repository(tmp_path)
    stage(root, "claimed/inside.md")
    board = tmp_path / "active-sessions.md"
    claim_staged_repository(board, root)
    capsys.readouterr()

    request = check_staged_args(
        board, root, override_subscription="hotfix on unsubscribed path"
    )
    assert MODULE.command_check_staged(request) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["enforcement_outcome"] == "passed-inside-claim"
    override = payload["receipt"]["subscription_override"]
    assert override["reason"] == "hotfix on unsubscribed path"
    assert override["paths"] == ["claimed/inside.md"]

    body = board.read_text(encoding="utf-8")
    assert "recorded-subscription-override" in body
    assert "hotfix on unsubscribed path" in body
    assert "claimed/inside.md" in body
    assert machine_id in body


def test_subscription_patterns_expand_home_and_repo_relative(tmp_path):
    root = tmp_path / "repo"
    assert SUBS.pattern_authorizes_path(
        f"{root}/claimed/**", root, "claimed/inside.md"
    )
    assert SUBS.pattern_authorizes_path("claimed/**", root, "claimed/inside.md")
    assert not SUBS.pattern_authorizes_path(
        f"{root}/docs/**", root, "claimed/inside.md"
    )
    assert SUBS.pattern_authorizes_path(
        "~/workspaces/personal/**",
        root,
        "claimed/inside.md",
    ) is False
