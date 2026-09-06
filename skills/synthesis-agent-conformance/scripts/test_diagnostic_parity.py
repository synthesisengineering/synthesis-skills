"""Parity probes compare unread inboxes without acknowledging their delivery."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPTS = Path(__file__).resolve().parent
PM_SCRIPTS = SCRIPTS.parents[1] / "synthesis-project-management" / "scripts"
for directory in (SCRIPTS, PM_SCRIPTS):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

SPEC = importlib.util.spec_from_file_location("diagnostic_conformance", SCRIPTS / "conformance.py")
assert SPEC and SPEC.loader
CONFORMANCE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CONFORMANCE
SPEC.loader.exec_module(CONFORMANCE)

import coordination  # noqa: E402
from peer_addressing import watermark_path  # noqa: E402


SESSION_ID = "11111111-1111-4111-8111-111111111111"
SESSION_REF = f"codex:{SESSION_ID}"
DIRECT_MESSAGE = "Direct review evidence is ready."
PROJECT_MESSAGE = "The project checkpoint is ready."


def file_state(path: Path) -> tuple[bytes, int] | None:
    """Include the modification time so rewriting identical bytes also fails."""
    return (path.read_bytes(), path.stat().st_mtime_ns) if path.exists() else None


def git(repo: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *arguments], check=True, text=True, capture_output=True
    )


@pytest.fixture
def inbox_project(tmp_path: Path, monkeypatch):
    """Real seat and bus operations, confined to a temporary machine root."""
    for name in tuple(os.environ):
        if name.startswith(("SYNTHESIS_", "CLAUDE", "CODEX_", "XDG_", "GIT_")):
            monkeypatch.delenv(name, raising=False)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SYNTHESIS_HOME", str(home / ".synthesis"))
    monkeypatch.setenv("CODEX_HOME", str(home / ".codex"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home / ".claude"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / ".local" / "state"))
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.setenv("SYNTHESIS_PEER_REGISTRY", str(home / "peer-registry"))

    repo = tmp_path / "repository"
    project = repo / "projects" / "example-project"
    plan = project / "resources" / "artifacts" / "example-plan.md"
    plan.parent.mkdir(parents=True)
    (project / "sessions").mkdir()
    (project / "CONTEXT.md").write_text(
        "**Phase:** Ready\n**Status:** Paused\n\n"
        "[plan](resources/artifacts/example-plan.md)\n\n"
        "## What's Next\n\n1. [ ] Verify the release.\n", encoding="utf-8"
    )
    (project / "REFERENCE.md").write_text("# Reference\n", encoding="utf-8")
    plan.write_text("# Plan\n", encoding="utf-8")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "core.hooksPath", "/dev/null")
    git(repo, "add", "projects")
    git(repo, "commit", "-qm", "Fixture checkpoint")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.chdir(tmp_path)

    board = home / ".synthesis" / "coordination" / "active-sessions.md"

    def claim(project_name: str, native_ref: str):
        monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", native_ref)
        request = SimpleNamespace(
            board=board, id=None, agent="agent", machine="fixture-machine",
            project=project_name, mode="interactive", goal="Verify the fixture",
            workspace=[f"{tmp_path / project_name} @ feature/{project_name}"],
            area=[str(tmp_path / project_name)],
            context_role="owner",
        )
        assert coordination.command_claim(request) == 0
        return next(row for row in coordination.rows(board.read_text(encoding="utf-8"))
                    if row.project == project_name)

    sender = claim("sender-project", "codex:22222222-2222-4222-8222-222222222222")
    recipient = claim(project.name, SESSION_REF)
    for target, message in ((recipient.compact_id, DIRECT_MESSAGE),
                            (project.name, PROJECT_MESSAGE),
                            (sender.compact_id, "Not addressed to the recipient.")):
        assert coordination.command_message(SimpleNamespace(
            board=board, sender=sender.compact_id, to=target, text=message
        )) == 0

    pointer = home / "active-project.json"
    # Exercise the existing pointer-fallback path as well as stopped recovery:
    # no remote lease is fabricated to make a fixture pointer authoritative.
    pointer.write_text(json.dumps({"project": str(project)}), encoding="utf-8")
    return SimpleNamespace(
        root=tmp_path, home=home, repo=repo, project=project, plan=plan,
        board=board, pointer=pointer, cursor=watermark_path(board, SESSION_REF),
        summary={"phase": "Ready", "status": "Paused", "plan": str(plan)},
    )


def compare(kind: str, fixture) -> tuple[bool, str]:
    if kind == "active":
        return CONFORMANCE.payload_parity(fixture.pointer, fixture.board)
    return CONFORMANCE.stopped_payload_parity(fixture.project, fixture.summary, fixture.board)


def capture_real_children(monkeypatch, *, transform=None, driver: str | None = None):
    """Observe real CLI envelopes; optional faults are isolated test controls."""
    real_run = CONFORMANCE.run
    observed = []

    def run(command, *args, **kwargs):
        executed = command
        if driver is not None:
            script_index = next(i for i, value in enumerate(command)
                                if str(value).endswith("session_context.py"))
            executed = [sys.executable, "-B", "-c", driver,
                        *command[script_index:]]
        result = real_run(executed, *args, **kwargs)
        observed.append(result)
        if transform is not None and result.returncode == 0:
            return transform(command, result)
        return result

    monkeypatch.setattr(CONFORMANCE, "run", run)
    return observed


def context(result: subprocess.CompletedProcess[str]) -> str:
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize("kind", ["active", "stopped"])
@pytest.mark.parametrize("existing_cursor", [False, True])
def test_parity_repeats_without_consuming_unread_messages(
    inbox_project, monkeypatch, kind, existing_cursor
) -> None:
    fixture = inbox_project
    if existing_cursor:
        fixture.cursor.parent.mkdir(parents=True)
        fixture.cursor.write_text(
            '{"seen": ["historical-message"], "updated_at": "2026-01-01T00:00:00Z"}\n',
            encoding="utf-8",
        )
    original_cursor = file_state(fixture.cursor)
    original_board = file_state(fixture.board)
    observed = capture_real_children(monkeypatch)
    outcomes = [compare(kind, fixture), compare(kind, fixture)]

    # Assert preservation first: a retry turning green after acknowledgement
    # must never conceal the original state-consuming false negative.
    assert file_state(fixture.cursor) == original_cursor
    assert file_state(fixture.board) == original_board
    assert len(observed) == 4
    for result in observed:
        message = context(result)
        assert "2 unread message(s)" in message
        assert DIRECT_MESSAGE in message and PROJECT_MESSAGE in message
        assert "Not addressed to the recipient." not in message
    assert all(ok for ok, _ in outcomes), outcomes


# Execute the real lifecycle entry point while excluding the unrelated remote
# currency service. The inbox remains its production implementation.
LIFECYCLE_DRIVER = """
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]).parent))
import session_context
session_context.sessionstart_notice = lambda root: None
sys.argv = sys.argv[1:]
raise SystemExit(session_context.main())
"""


@pytest.mark.parametrize("event", ["SessionStart", "UserPromptSubmit"])
def test_normal_lifecycle_delivers_and_marks_once(inbox_project, event) -> None:
    fixture = inbox_project
    payload = json.dumps({"session_id": SESSION_ID, "hook_event_name": event,
                          "cwd": str(fixture.project)})
    command = [sys.executable, "-B", "-c", LIFECYCLE_DRIVER,
               str(SCRIPTS / "session_context.py"), "--format", "codex",
               "--active-project-file", str(fixture.home / "missing-pointer.json"),
               "--coordination-board", str(fixture.board)]
    first = CONFORMANCE.run(command, input_text=payload)
    assert DIRECT_MESSAGE in context(first) and PROJECT_MESSAGE in context(first)
    cursor_after_delivery = file_state(fixture.cursor)
    assert cursor_after_delivery is not None
    second = CONFORMANCE.run(command, input_text=payload)
    assert DIRECT_MESSAGE not in context(second) and PROJECT_MESSAGE not in context(second)
    assert file_state(fixture.cursor) == cursor_after_delivery


@pytest.mark.parametrize("kind", ["active", "stopped"])
@pytest.mark.parametrize("difference", ["inbox", "core"])
def test_parity_still_rejects_client_specific_context_differences(
    inbox_project, monkeypatch, kind, difference
) -> None:
    def transform(command, result):
        if command[command.index("--format") + 1] != "codex":
            return result
        envelope = json.loads(result.stdout)
        message = envelope["hookSpecificOutput"]["additionalContext"]
        if difference == "inbox":
            # Add a real envelope field difference even on the broken baseline,
            # whose second invocation has already consumed the original inbox.
            message += "\nCoordination board inbox: client-specific delivery differs."
        else:
            message += "\nCurrent status: Conflicting client-specific state."
        envelope["hookSpecificOutput"]["additionalContext"] = message
        return subprocess.CompletedProcess(result.args, result.returncode,
                                           json.dumps(envelope), result.stderr)

    capture_real_children(monkeypatch, transform=transform)
    ok, detail = compare(kind, inbox_project)
    assert not ok, detail
    assert "diverge" in detail


INBOX_ERROR_DRIVER = """
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]).parent))
import session_context
import board_inbox
def broken_inbox(*args, **kwargs):
    raise OSError("fixture inbox dependency unavailable")
board_inbox.inbox_text = broken_inbox
sys.argv = sys.argv[1:]
raise SystemExit(session_context.main())
"""


@pytest.mark.parametrize("kind", ["active", "stopped"])
def test_inbox_dependency_error_cannot_become_equal_successful_payloads(
    inbox_project, monkeypatch, kind
) -> None:
    observed = capture_real_children(monkeypatch, driver=INBOX_ERROR_DRIVER)
    ok, detail = compare(kind, inbox_project)
    assert not ok, detail
    assert observed and observed[0].returncode != 0
    assert "fixture inbox dependency unavailable" in detail
