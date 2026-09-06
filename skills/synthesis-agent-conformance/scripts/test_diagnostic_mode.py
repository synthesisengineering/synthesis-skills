"""Diagnostic rendering never invokes lifecycle mutation boundaries."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "diagnostic_session_context", Path(__file__).with_name("session_context.py")
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
import active_project  # noqa: E402


@pytest.mark.parametrize("fallback", [False, True])
def test_diagnostic_main_suppresses_lifecycle_writes(tmp_path, monkeypatch, capsys, fallback):
    pointer = tmp_path / "pointer.json"
    if fallback:
        pointer.write_text("{}", encoding="utf-8")
    calls = []

    def forbidden(*args, **kwargs):
        pytest.fail("diagnostic invoked a lifecycle mutation boundary")

    def build(candidate, board, cwd, **kwargs):
        assert kwargs == {"diagnostic": True}
        assert os.environ["GIT_OPTIONAL_LOCKS"] == "0"
        calls.append(candidate)
        if fallback and candidate == pointer:
            raise ValueError("fixture invalid pointer")
        return "Project context"

    def inbox(message, payload, board, **kwargs):
        assert kwargs == {"diagnostic": True}
        return message + "\nUnread messages"

    monkeypatch.setattr(MODULE, "record_live_receipt", forbidden)
    monkeypatch.setattr(MODULE, "append_currency_notice", forbidden)
    monkeypatch.setattr(MODULE, "build", build)
    monkeypatch.setattr(MODULE, "append_inbox", inbox)
    monkeypatch.setenv("GIT_OPTIONAL_LOCKS", "1")
    monkeypatch.setattr(sys, "argv", ["session_context.py", "--diagnostic", "--format", "codex",
                                    "--active-project-file", str(pointer)])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "session_id": "11111111-1111-4111-8111-111111111111",
        "hook_event_name": "SessionStart", "cwd": str(tmp_path),
        "transcript_path": str(tmp_path / "native.jsonl"),
    })))
    assert MODULE.main() == 0
    output = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert "Project context" in output and "Unread messages" in output
    assert len(calls) == (2 if fallback else 1)


@pytest.mark.parametrize("diagnostic", [False, True])
def test_project_resolver_policy_is_explicit(tmp_path, monkeypatch, diagnostic):
    project = tmp_path / "projects" / "example-project"
    project.mkdir(parents=True)
    (project.parent / "index.yaml").write_text("projects: []\n", encoding="utf-8")
    board = tmp_path / "coordination" / "active-sessions.md"
    board.parent.mkdir()
    board.write_text("fixture", encoding="utf-8")
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path))
    calls = []

    def resolve(*args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(status="PASS", selected_path=str(project), issues=[])

    monkeypatch.setattr(MODULE, "resolve_project", resolve)
    assert MODULE.reconciled_project(project, diagnostic=diagnostic) == (project, [])
    assert calls[0]["fetch"] is (not diagnostic)
    assert calls[0]["fast_forward_canonical"] is (not diagnostic)
    assert calls[0]["refresh_coordination"] is (not diagnostic)


@pytest.mark.parametrize("refresh", [False, True])
def test_pointer_loader_preserves_refresh_policy(tmp_path, monkeypatch, refresh):
    pointer = tmp_path / "pointer.json"
    pointer.write_text("{}", encoding="utf-8")
    calls = []

    def validate(*args, **kwargs):
        calls.append(kwargs)
        return []

    monkeypatch.setattr(active_project, "validate", validate)
    assert active_project.load_and_validate(pointer, tmp_path / "board", refresh_lease=refresh) == ({}, [])
    assert calls[0]["refresh_lease"] is refresh


@pytest.mark.parametrize("diagnostic", [False, True])
def test_build_threads_policy_through_active_pointer(tmp_path, monkeypatch, diagnostic):
    project = tmp_path / "project"
    project.mkdir()
    (project / "CONTEXT.md").write_text("# Context\n", encoding="utf-8")
    pointer = tmp_path / "pointer.json"
    pointer.write_text("{}", encoding="utf-8")
    calls = []

    def load(*args, **kwargs):
        assert kwargs.get("refresh_lease", True) is (not diagnostic)
        return {"project": str(project)}, []

    def append(lines, candidate, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(MODULE, "load_and_validate", load)
    monkeypatch.setattr(MODULE, "append_project_context", append)
    MODULE.build(pointer, tmp_path / "board", pending_handoffs=tmp_path / "pending", diagnostic=diagnostic)
    assert calls == [{"label": "Active synthesis project", "diagnostic": diagnostic}]
