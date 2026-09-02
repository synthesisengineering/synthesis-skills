"""The board inbox hook: addressed messages reach the seat they name, once, in both clients."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import board_inbox as INBOX  # noqa: E402
import coordination as ENGINE  # noqa: E402

ME_SID = "11111111-1111-4111-8111-111111111111"
ME_ENV = {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": ME_SID, "CLAUDE_CODE_HOST_SESSION_ID": "local_me"}


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    for name in ("SYNTHESIS_CLIENT_SESSION_REF", "CLAUDE_CODE_HOST_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CLAUDE_PID", "CLAUDECODE"):
        monkeypatch.delenv(name, raising=False)


def args(board: Path, **values):
    return type("Args", (), {"board": board, **values})()


def claim(board: Path, project: str, env: dict, monkeypatch):
    for key in ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_HOST_SESSION_ID", "SYNTHESIS_CLIENT_SESSION_REF"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    request = args(board, id=None, agent="agent", machine="m1", project=project, mode="interactive", goal="g", workspace=[f"/tmp/wt-{project} @ feature/{project}"], area=[f"repo-{project}/**"], context_role="owner")
    assert ENGINE.command_claim(request) == 0
    return [row for row in ENGINE.rows(board.read_text(encoding="utf-8")) if row.project == project][0]


@pytest.fixture
def board(tmp_path, monkeypatch):
    path = tmp_path / "board.md"
    other = claim(path, "project-o", {}, monkeypatch)
    me = claim(path, "project-m", ME_ENV, monkeypatch)
    assert ENGINE.command_message(args(path, sender=other.compact_id, to=me.compact_id, text="Handoff: the review is yours.")) == 0
    assert ENGINE.command_message(args(path, sender=other.compact_id, to="project-m", text="For every project-m session.")) == 0
    assert ENGINE.command_message(args(path, sender=other.compact_id, to=other.compact_id, text="Not for me.")) == 0
    return path


def test_inbox_delivers_once_to_the_named_seat(board, tmp_path) -> None:
    payload = {"session_id": ME_SID, "hook_event_name": "UserPromptSubmit", "cwd": "/tmp"}
    text = INBOX.inbox_text(payload, board=board, pointer=tmp_path / "pointer.json", environ=ME_ENV)
    assert "2 unread message(s)" in text
    assert "Handoff: the review is yours." in text and "For every project-m session." in text
    assert "Not for me." not in text
    assert INBOX.inbox_text(payload, board=board, pointer=tmp_path / "pointer.json", environ=ME_ENV) == ""


def test_project_history_before_the_claim_is_not_delivered_to_a_new_seat(tmp_path, monkeypatch) -> None:
    """An earlier seat of the project received a message weeks ago; a seat
    claimed today must not see it as unread, while a message posted after
    its claim is delivered."""
    path = tmp_path / "board.md"
    other = claim(path, "project-o", {}, monkeypatch)
    earlier = claim(path, "project-m", {}, monkeypatch)
    assert ENGINE.command_message(args(path, sender=other.compact_id, to="project-m", text="Posted before the seat existed.")) == 0
    assert ENGINE.command_release(args(path, id=earlier.compact_id)) == 0
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"(### → project-m sessions, from \S+ — )\S+", r"\g<1>2026-01-01T00:00:00-05:00", text, count=1)
    path.write_text(text, encoding="utf-8")
    me = claim(path, "project-m", ME_ENV, monkeypatch)
    assert ENGINE.command_message(args(path, sender=other.compact_id, to="project-m", text="Posted after the claim.")) == 0
    delivered = INBOX.inbox_text({"session_id": ME_SID}, board=path, pointer=tmp_path / "pointer.json", environ=ME_ENV)
    assert "Posted after the claim." in delivered
    assert "Posted before the seat existed." not in delivered
    assert "1 unread message(s)" in delivered
    assert me.project == "project-m"


def test_unseated_session_gets_project_messages_from_the_active_pointer(board, tmp_path) -> None:
    pointer = tmp_path / "pointer.json"
    pointer.write_text(json.dumps({"project": "/kb/projects/project-m"}), encoding="utf-8")
    stranger = {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "99999999-9999-4999-8999-999999999999"}
    text = INBOX.inbox_text({"session_id": stranger["CLAUDE_CODE_SESSION_ID"]}, board=board, pointer=pointer, environ=stranger)
    assert "For every project-m session." in text and "Handoff" not in text


def test_codex_session_learns_its_identity(board, tmp_path) -> None:
    text = INBOX.inbox_text({"session_id": "0a0a0a0a-1b1b-4c1c-8d1d-2e2e2e2e2e2e"}, board=board, pointer=tmp_path / "pointer.json", environ={"CODEX_HOME": "/x"})
    assert "SYNTHESIS_CLIENT_SESSION_REF=codex:0a0a0a0a-1b1b-4c1c-8d1d-2e2e2e2e2e2e" in text


def test_no_session_id_means_silence(board, tmp_path) -> None:
    assert INBOX.inbox_text({}, board=board, pointer=tmp_path / "pointer.json", environ={}) == ""


def test_hook_process_emits_additional_context_json_or_nothing(board, tmp_path) -> None:
    script = SCRIPTS_DIR / "board_inbox.py"
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE") and k != "SYNTHESIS_CLIENT_SESSION_REF"}
    env.update(ME_ENV)
    payload = json.dumps({"session_id": ME_SID, "hook_event_name": "UserPromptSubmit"})
    first = subprocess.run([sys.executable, str(script), "--board", str(board), "--active-project-file", str(tmp_path / "pointer.json"), "--hook"], input=payload, capture_output=True, text=True, env=env)
    assert first.returncode == 0, first.stderr
    data = json.loads(first.stdout)
    assert data["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "2 unread message(s)" in data["hookSpecificOutput"]["additionalContext"]
    second = subprocess.run([sys.executable, str(script), "--board", str(board), "--active-project-file", str(tmp_path / "pointer.json"), "--hook"], input=payload, capture_output=True, text=True, env=env)
    assert second.returncode == 0 and second.stdout == ""


def test_session_context_appends_the_inbox(board, tmp_path) -> None:
    conformance = SCRIPTS_DIR.parents[1] / "synthesis-agent-conformance" / "scripts" / "session_context.py"
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE") and k != "SYNTHESIS_CLIENT_SESSION_REF"}
    env.update(ME_ENV)
    env["SYNTHESIS_PUBLIC_SESSIONSTART_RECEIPT"] = str(tmp_path / "receipt.json")
    payload = json.dumps({"session_id": ME_SID, "hook_event_name": "SessionStart", "cwd": str(tmp_path)})
    run = subprocess.run([sys.executable, str(conformance), "--active-project-file", str(tmp_path / "pointer.json"), "--coordination-board", str(board), "--format", "claude"], input=payload, capture_output=True, text=True, env=env)
    assert run.returncode == 0, run.stderr
    context = json.loads(run.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "Coordination board inbox: 2 unread" in context
