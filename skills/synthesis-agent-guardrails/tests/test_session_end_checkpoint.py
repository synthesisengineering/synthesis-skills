from __future__ import annotations

import json
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path


SCRIPT = Path(__file__).parent.parent / "hooks" / "codex" / "session_end_checkpoint.py"
SPEC = importlib.util.spec_from_file_location("session_end_checkpoint", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def run_hook(cwd: Path, destination: Path) -> tuple[subprocess.CompletedProcess[str], float]:
    payload = {
        "session_id": "test-session",
        "cwd": str(cwd),
        "hook_event_name": "SessionEnd",
        "reason": "other",
    }
    config = destination.parent / "hooks.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        json.dumps({"hooks": {"session_end_checkpoint": {"enabled": True}}}),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["SYNTHESIS_SESSION_END_STATE"] = str(destination)
    env["GUARDRAILS_HOOKS_CONFIG"] = str(config)
    started = time.monotonic()
    result = subprocess.run(
        ["python3", str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=3,
        check=False,
    )
    return result, time.monotonic() - started


def test_non_git_session_end_writes_bounded_checkpoint(tmp_path: Path) -> None:
    destination = tmp_path / "state" / "last.json"
    result, elapsed = run_hook(tmp_path, destination)
    assert result.returncode == 0, result.stderr
    assert elapsed < 3
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["repository"]["state"] == "not-git"
    assert payload["session_id"] == "test-session"


def test_git_session_end_captures_dirty_state(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    # AGENT HEURISTIC: this fixture tests SessionEnd evidence, not user-level
    # commit hooks. Keep its synthetic seed commit hermetic when the real
    # coordination gate is configured globally.
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "core.hooksPath", "/dev/null"],
        check=True,
    )
    (tmp_path / "tracked.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "tracked.txt"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "test",
        ],
        check=True,
    )
    (tmp_path / "tracked.txt").write_text("two\n", encoding="utf-8")
    destination = tmp_path / "last.json"
    result, elapsed = run_hook(tmp_path, destination)
    assert result.returncode == 0, result.stderr
    assert elapsed < 3
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["repository"]["state"] == "verified"
    assert payload["repository"]["dirty"] is True


def test_git_failure_with_marker_is_unverifiable(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(MODULE, "run_git", lambda *_args: (128, ""))

    evidence = MODULE.repo_evidence(tmp_path, time.monotonic() + 1)

    assert evidence["state"] == "unverifiable"


def test_missing_cwd_is_unverifiable(tmp_path: Path) -> None:
    evidence = MODULE.repo_evidence(
        str(tmp_path / "missing"), time.monotonic() + 1
    )

    assert evidence["state"] == "unverifiable"


def test_git_calls_share_one_bounded_deadline(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    observed: list[float] = []

    def slow_run(*_args, **kwargs):
        observed.append(float(kwargs["timeout"]))
        raise subprocess.TimeoutExpired("git", kwargs["timeout"])

    monkeypatch.setattr(MODULE.subprocess, "run", slow_run)
    deadline = time.monotonic() + 0.2

    evidence = MODULE.repo_evidence(str(tmp_path), deadline)

    assert evidence["state"] == "unverifiable"
    assert observed and max(observed) <= MODULE.GIT_CALL_MAX_SECONDS
