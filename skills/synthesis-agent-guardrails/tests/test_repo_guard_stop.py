from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parent.parent / "hooks" / "codex" / "repo_guard_stop.py"
SPEC = importlib.util.spec_from_file_location("repo_guard_stop", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


@pytest.fixture(autouse=True)
def verified_runtime_command(monkeypatch):
    monkeypatch.setattr(MODULE, "public_command", lambda script, arguments:
        [sys.executable, "-B", str(Path("/verified-runtime/skills") / script), *arguments])
    # Hooks ship disabled by default; these tests exercise behavior with the gate open.
    monkeypatch.setattr(MODULE, "hook_enabled", lambda name: True)


def invoke(monkeypatch, capsys, cwd: Path) -> str:
    monkeypatch.setattr(
        MODULE.sys,
        "stdin",
        io.StringIO(json.dumps({"cwd": str(cwd), "hook_event_name": "Stop",
                               "session_id": "guard-stop-fixture", "stop_hook_active": False})),
    )
    assert MODULE.main() == 0
    return capsys.readouterr().out


def invoke_with_session(monkeypatch, capsys, cwd: Path, session_id: str) -> str:
    monkeypatch.setattr(
        MODULE.sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {"cwd": str(cwd), "hook_event_name": "Stop", "session_id": session_id,
                 "stop_hook_active": False}
            )
        ),
    )
    assert MODULE.main() == 0
    return capsys.readouterr().out


def test_non_git_directory_is_a_clean_noop(tmp_path, monkeypatch, capsys) -> None:
    def unavailable(*args):
        raise ValueError("runtime unavailable")
    monkeypatch.setattr(MODULE, "public_command", unavailable)
    assert invoke(monkeypatch, capsys, tmp_path) == ""


def test_git_repo_blocks_when_verified_runtime_is_unavailable(tmp_path, monkeypatch, capsys) -> None:
    (tmp_path / ".git").mkdir()
    def unavailable(*args):
        raise ValueError("runtime unavailable")
    monkeypatch.setattr(MODULE, "public_command", unavailable)
    monkeypatch.setattr(MODULE, "git_root", lambda cwd: ("git", tmp_path))
    output = json.loads(invoke(monkeypatch, capsys, tmp_path))
    assert output["continue"] is False
    assert "failed to execute inside" in output["stopReason"]
    assert "decision" not in output


def test_git_repo_blocks_when_guard_execution_fails(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(MODULE, "git_root", lambda cwd: ("git", tmp_path))
    monkeypatch.setattr(
        MODULE,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 2, "", "broken"),
    )
    output = json.loads(invoke(monkeypatch, capsys, tmp_path))
    assert output["continue"] is False
    assert "exit 2" in output["stopReason"]
    assert "decision" not in output


def test_git_repo_passes_after_successful_guard(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(MODULE, "git_root", lambda cwd: ("git", tmp_path))
    monkeypatch.setattr(
        MODULE,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )
    assert invoke(monkeypatch, capsys, tmp_path) == ""


def test_git_repo_allows_reported_local_only_state(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(MODULE, "git_root", lambda cwd: ("git", tmp_path))
    monkeypatch.setattr(
        MODULE,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 1, "[]", ""),
    )

    assert invoke(monkeypatch, capsys, tmp_path) == ""


def test_pending_context_runs_checkpoint_before_repo_detector(
    tmp_path, monkeypatch, capsys
) -> None:
    pending_dir = tmp_path / "pending"
    pending_dir.mkdir()
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending_dir)
    monkeypatch.setattr(MODULE, "git_root", lambda cwd: ("not-git", None))
    session_id = "session-a"
    MODULE.pending_manifest(session_id).write_text("{}\n", encoding="utf-8")
    observed = []

    def successful_run(args, **kwargs):
        observed.append((args, kwargs.get("input_text")))
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(MODULE, "run", successful_run)

    assert invoke_with_session(monkeypatch, capsys, tmp_path, session_id) == ""
    assert observed
    assert "checkpoint_sync.py" in " ".join(observed[0][0])
    assert json.loads(observed[0][1])["session_id"] == session_id


def test_pending_context_blocks_when_local_receipt_cannot_be_written(
    tmp_path, monkeypatch, capsys
) -> None:
    pending_dir = tmp_path / "pending"
    pending_dir.mkdir()
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending_dir)
    session_id = "session-b"
    MODULE.pending_manifest(session_id).write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        MODULE,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 1, "", "offline"),
    )

    output = json.loads(invoke_with_session(monkeypatch, capsys, tmp_path, session_id))
    assert output["decision"] == "block"
    assert "Local project handoff evidence" in output["reason"]


def test_invalid_stop_payload_fails_closed(monkeypatch, capsys) -> None:
    monkeypatch.setattr(MODULE.sys, "stdin", io.StringIO("not-json"))

    assert MODULE.main() == 0
    output = json.loads(capsys.readouterr().out)

    assert output["continue"] is False
    assert "invalid" in output["stopReason"]
    assert "UNRESOLVED" in output["systemMessage"]


def test_dangling_pending_manifest_symlink_fails_closed(
    tmp_path, monkeypatch, capsys
) -> None:
    pending_dir = tmp_path / "pending"
    pending_dir.mkdir()
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending_dir)
    session_id = "session-symlink"
    MODULE.pending_manifest(session_id).symlink_to(tmp_path / "missing")

    output = json.loads(invoke_with_session(monkeypatch, capsys, tmp_path, session_id))

    assert output["decision"] == "block"
    assert "unsafe symlink" in output["reason"]


@pytest.mark.parametrize("terminal", [False, True])
def test_pending_checkpoint_failure_payload_is_not_normalized_to_success(
    tmp_path, monkeypatch, capsys, terminal
) -> None:
    pending_dir = tmp_path / "pending"
    pending_dir.mkdir()
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending_dir)
    monkeypatch.setattr(MODULE, "git_root", lambda cwd: ("not-git", None))
    session_id = "checkpoint-json-failure"
    MODULE.pending_manifest(session_id).write_text("{}\n", encoding="utf-8")
    response = ({"continue": False, "stopReason": "checkpoint unavailable"}
                if terminal else {"decision": "block", "reason": "checkpoint unresolved"})
    response["systemMessage"] = "UNRESOLVED: checkpoint guard did not verify"
    monkeypatch.setattr(MODULE, "run", lambda *args, **kwargs:
                        subprocess.CompletedProcess([], 0, json.dumps(response), ""))
    output = json.loads(invoke_with_session(monkeypatch, capsys, tmp_path, session_id))
    assert output == response


def test_repeated_failed_stop_halts_without_requesting_another_turn(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(MODULE, "git_root", lambda cwd: ("git", tmp_path))
    monkeypatch.setattr(MODULE, "run", lambda *args, **kwargs:
                        subprocess.CompletedProcess([], 2, "", "unavailable"))
    monkeypatch.setattr(MODULE.sys, "stdin", io.StringIO(json.dumps({
        "cwd": str(tmp_path), "hook_event_name": "Stop", "session_id": "repeat-fixture",
        "stop_hook_active": True,
    })))
    assert MODULE.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["continue"] is False
    assert "decision" not in output
    assert "UNRESOLVED" in output["systemMessage"]


@pytest.mark.parametrize("field,value", [
    ("session_id", ...), ("session_id", None), ("session_id", ""), ("session_id", 42),
    ("stop_hook_active", ...), ("stop_hook_active", None), ("stop_hook_active", "false"),
    ("stop_hook_active", 0), ("hook_event_name", ...), ("hook_event_name", "PreToolUse"),
])
def test_direct_stop_refuses_invalid_native_identity_before_repository_inspection(
    tmp_path, monkeypatch, capsys, field, value
):
    payload = {"cwd": str(tmp_path), "session_id": "native-identity-fixture",
               "hook_event_name": "Stop", "stop_hook_active": False}
    if value is ...:
        payload.pop(field)
    else:
        payload[field] = value
    inspections = []
    monkeypatch.setattr(MODULE, "git_root", lambda cwd: (inspections.append(cwd) or "git", tmp_path))
    monkeypatch.setattr(MODULE, "run", lambda *args, **kwargs:
                        subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr(MODULE.sys, "stdin", io.StringIO(json.dumps(payload)))
    assert MODULE.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["continue"] is False
    assert "identity" in output["stopReason"]
    assert "decision" not in output
    assert not inspections


def test_checkpoint_execution_exception_is_terminal_infrastructure_failure(tmp_path, monkeypatch, capsys):
    pending = tmp_path / "pending"
    pending.mkdir()
    monkeypatch.setattr(MODULE, "PENDING_DIR", pending)
    session_id = "checkpoint-execution-failure"
    MODULE.pending_manifest(session_id).write_text("{}\n", encoding="utf-8")

    def unavailable(*args, **kwargs):
        raise OSError("checkpoint could not start")

    monkeypatch.setattr(MODULE, "run", unavailable)
    output = json.loads(invoke_with_session(monkeypatch, capsys, tmp_path, session_id))
    assert output["continue"] is False
    assert "could not run at Stop" in output["stopReason"]
    assert "decision" not in output
