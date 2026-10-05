"""Retirement claim cleanup must scale with the board and survive a closed owner.

Two production failures motivate these controls. A board whose complete
``status --json`` reply exceeded the retained runtime's output ceiling made
claim narrowing unreadable, so every retry refused after the worktree was
already removed. And once that owner's seat was released, no caller could
authenticate as it, so the retained retirement could never finish.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace

import pytest

import coordination
import retirement_runtime as runtime
from test_retire_worktree import COORDINATION, MODULE, SCRIPT, _interrupted_retirement_fixture, git
# The autouse isolation fixture keeps in-process retirement state and native
# identity inside tmp_path; it must apply to this module too.
from test_retire_worktree import isolated_module_state  # noqa: F401
from test_retirement_runtime import capture, source_in_target


def _status(board):
    completed = subprocess.run([sys.executable, str(COORDINATION), "--board", str(board), "status", "--json"],
                               capture_output=True, text=True, env=dict(os.environ))
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


def _owner_cells(board, session_uuid):
    [row] = [row for row in json.loads(_status(board))["sessions"] if row["session_uuid"] == session_uuid]
    return row["claims"], row["workspaces"], row["status"]


def _inflate(board, rows=600):
    """Append released foreign seats through the owner's own serializer."""
    text = board.read_text(encoding="utf-8")
    sessions = coordination.rows(text)
    template = sessions[0]
    filler = " ".join(["historical released seat goal"] * 60)
    released = [replace(template, session_uuid="", compact_id="", speakable_id="", legacy_id="",
                        client_ref="", status="released", workspaces=[],
                        claims=[f"/synthetic/released/{index}/**"],
                        goal=f"synthetic seat {index}: {filler}")
                for index in range(rows)]
    board.write_text(coordination.replace_table(text, sessions + released), encoding="utf-8")


def _release(board, row, tmp_path):
    env = dict(os.environ, SYNTHESIS_CLIENT_SESSION_REF="test:caller",
               SYNTHESIS_COORDINATION_SESSION=row["compact_id"])
    completed = subprocess.run([sys.executable, str(COORDINATION), "--board", str(board), "release",
                                "--session", row["compact_id"],
                                "--active-project-file", str(tmp_path / "active-project.json")],
                               capture_output=True, text=True, env=env)
    assert completed.returncode == 0, completed.stderr


def test_oversized_board_retirement_narrows_through_row_sized_read(tmp_path):
    clone, target, board, row, env, cmd = source_in_target(tmp_path)
    _inflate(board)
    # Positive control: this board reproduces the defect. The complete owner
    # reply exceeds the bounded transport, and an unprojected retained read fails.
    assert len(_status(board).encode()) > runtime.INVOKE_OUTPUT_BYTES
    store = tmp_path / "control-store"
    digest = runtime.stage(SCRIPT.parent.parent, store)
    with pytest.raises(ValueError, match="output ceiling"):
        runtime.invoke(store, digest, board, ["status", "--json"])
    projected = runtime.invoke(store, digest, board, ["status", "--json"], select=row["session_uuid"])
    assert projected.returncode == 0, projected.stdout
    assert len(projected.stdout.encode()) < 64 * 1024
    assert json.loads(projected.stdout)["session"]["session_uuid"] == row["session_uuid"]

    result = capture(tmp_path, "oversized-retire", cmd, env, clone)
    assert result.returncode == 0, result.stderr
    assert not target.exists()
    assert "narrowed 1 area(s), 1 workspace(s)" in result.stdout
    assert _owner_cells(board, row["session_uuid"]) == ([str(clone / "seed.txt")], [f"{clone} @ main"], "active")


def _resume_argv(repo, worktree, board):
    return [str(SCRIPT), "--repository", str(repo), "--worktree", str(worktree),
            "--branch", "feature/demo", "--board", str(board), "--delete-remote"]


def test_released_owner_lets_any_caller_finish_retained_retirement(tmp_path, monkeypatch, capsys):
    repo, worktree, board, row = _interrupted_retirement_fixture(tmp_path, monkeypatch)
    _release(board, row, tmp_path)
    before = board.read_bytes()
    capsys.readouterr()
    # A different native session with no seat export finishes the retained
    # retirement: the released owner holds no live claims to narrow.
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "test:different")
    monkeypatch.delenv("SYNTHESIS_COORDINATION_SESSION")
    monkeypatch.setattr(sys, "argv", _resume_argv(repo, worktree, board))
    assert MODULE.main() == 0
    output = capsys.readouterr().out
    assert f"claim owner {row['session_uuid']} is released" in output
    assert "nothing narrowed" in output
    assert board.read_bytes() == before
    assert not git(repo, "branch", "--list", "feature/demo").stdout.strip()
    assert not git(repo, "ls-remote", "--heads", "origin", "feature/demo").stdout.strip()


def test_absent_owner_row_finishes_without_narrowing(tmp_path, monkeypatch, capsys):
    repo, worktree, board, row = _interrupted_retirement_fixture(tmp_path, monkeypatch)
    text = board.read_text(encoding="utf-8")
    remaining = [session for session in coordination.rows(text) if session.session_uuid != row["session_uuid"]]
    board.write_text(coordination.replace_table(text, remaining), encoding="utf-8")
    before = board.read_bytes()
    capsys.readouterr()
    monkeypatch.delenv("SYNTHESIS_COORDINATION_SESSION")
    monkeypatch.setattr(sys, "argv", _resume_argv(repo, worktree, board))
    assert MODULE.main() == 0
    assert f"claim owner {row['session_uuid']} is absent" in capsys.readouterr().out
    assert board.read_bytes() == before


def test_active_owner_still_requires_its_native_proof(tmp_path, monkeypatch):
    repo, worktree, board, row = _interrupted_retirement_fixture(tmp_path, monkeypatch)
    before = board.read_bytes()
    monkeypatch.delenv("SYNTHESIS_COORDINATION_SESSION")
    monkeypatch.setattr(sys, "argv", _resume_argv(repo, worktree, board))
    assert MODULE.main() == 2
    assert board.read_bytes() == before
    assert git(repo, "branch", "--list", "feature/demo").stdout.strip()
    assert git(repo, "ls-remote", "--heads", "origin", "feature/demo").stdout.strip()


@pytest.mark.parametrize("reply", [
    "{}",
    '{"session": null, "active": true}',
    '{"session": null, "active": 0}',
    '{"session": {"session_uuid": "u", "status": "active", "claims": []}, "active": true}',
    '{"session": null, "active": false, "board": "extra"}',
    "not json",
], ids=["empty", "absent-active", "non-boolean", "missing-workspaces", "extra-field", "not-json"])
def test_row_projection_shape_is_exact(tmp_path, monkeypatch, reply):
    monkeypatch.setattr(runtime, "invoke", lambda *a, **k: subprocess.CompletedProcess([], 0, reply, ""))
    with pytest.raises(ValueError):
        runtime.row(tmp_path, "0" * 64, tmp_path / "board.md", "s-0000-0000-0000")


def test_row_projection_refuses_unreadable_board_and_empty_selector(tmp_path):
    store = tmp_path / "store"
    digest = runtime.stage(SCRIPT.parent.parent, store)
    with pytest.raises(ValueError):
        runtime.row(store, digest, tmp_path / "missing" / "active-sessions.md", "s-0000-0000-0000")
    with pytest.raises(ValueError):
        runtime.row(store, digest, tmp_path / "board.md", " ")
