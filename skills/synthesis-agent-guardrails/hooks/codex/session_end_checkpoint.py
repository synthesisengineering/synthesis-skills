#!/usr/bin/env python3
"""Write a bounded, atomic Codex SessionEnd repository checkpoint.

Codex caps SessionEnd commands at three seconds. Workspace-wide repository
scans therefore belong to Synthesis Console and day-end, where they are
observable and can take the time they need. This hook records fast local
evidence for the ending session so the lifecycle event is not lost.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
HOOKS_ROOT = HOOKS_DIR.parent
if str(HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(HOOKS_ROOT))
from _settings import doctor_prologue, hook_enabled  # noqa: E402

HOOK_NAME = "session_end_checkpoint"
DEFAULT_STATE = (
    Path.home() / ".synthesis" / "repo-guard" / "session-end-last.json"
)
EVIDENCE_BUDGET_SECONDS = 1.5
GIT_CALL_MAX_SECONDS = 0.35


def run_git(cwd: str, args: list[str], deadline: float) -> tuple[int, str]:
    remaining = deadline - time.monotonic()
    if remaining <= 0.05:
        return 2, ""
    try:
        result = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True,
            text=True,
            timeout=min(GIT_CALL_MAX_SECONDS, max(0.05, remaining - 0.02)),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 2, ""
    return result.returncode, result.stdout.strip()


def has_git_marker(cwd: str) -> bool | None:
    try:
        current = Path(cwd).resolve(strict=True)
    except OSError:
        return None
    if not current.is_dir():
        return None
    return any((candidate / ".git").exists() for candidate in (current, *current.parents))


def repo_evidence(cwd: str, deadline: float) -> dict[str, object]:
    marker = has_git_marker(cwd)
    code, root = run_git(cwd, ["rev-parse", "--show-toplevel"], deadline)
    if code != 0 or not root:
        return {"state": "not-git" if marker is False else "unverifiable"}

    status_code, status = run_git(root, ["status", "--porcelain=v1"], deadline)
    head_code, head = run_git(root, ["rev-parse", "HEAD"], deadline)
    upstream_code, upstream = run_git(
        root, ["rev-list", "--left-right", "--count", "HEAD...@{upstream}"], deadline
    )
    evidence: dict[str, object] = {
        "state": "verified" if status_code == head_code == 0 else "unverifiable",
        "root": root,
        "dirty": bool(status) if status_code == 0 else None,
        "head": head if head_code == 0 else None,
        "upstream_counts": upstream if upstream_code == 0 else None,
    }
    return evidence


def atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def doctor() -> int:
    lines, _healthy = doctor_prologue(HOOK_NAME)
    lines.append(f"default_state={DEFAULT_STATE}")
    lines.append(f"evidence_budget_seconds={EVIDENCE_BUDGET_SECONDS}")
    lines.append(f"git_call_max_seconds={GIT_CALL_MAX_SECONDS}")
    print("\n".join(lines))
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if "--doctor" in argv:
        return doctor()
    if not hook_enabled(HOOK_NAME):
        return 0

    started = time.monotonic()
    evidence_deadline = started + EVIDENCE_BUDGET_SECONDS
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"invalid SessionEnd payload: {exc}", file=sys.stderr)
        return 1

    cwd = str(payload.get("cwd") or "")
    record: dict[str, object] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "session_id": str(payload.get("session_id") or "unknown"),
        "reason": str(payload.get("reason") or "other"),
        "cwd": cwd,
        "repository": repo_evidence(cwd, evidence_deadline) if cwd else {"state": "not-git"},
    }
    record["elapsed_ms"] = round((time.monotonic() - started) * 1000, 2)
    destination = Path(
        os.environ.get("SYNTHESIS_SESSION_END_STATE", str(DEFAULT_STATE))
    ).expanduser()
    try:
        atomic_json(destination, record)
    except OSError as exc:
        print(f"could not write SessionEnd checkpoint {destination}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
