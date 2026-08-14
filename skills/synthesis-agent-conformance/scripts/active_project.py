#!/usr/bin/env python3
"""Validation primitives for the leased active-project pointer."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

TERMINAL_STATUSES = {"released", "complete", "completed", "closed"}


def lease_url(board: Path) -> str | None:
    try:
        match = re.search(
            r"^Lease:\s*(\S+)\s*$",
            board.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    except OSError:
        return None
    return match.group(1) if match else None


def sessions(board: Path) -> dict[str, dict[str, str]]:
    try:
        text = board.read_text(encoding="utf-8")
    except OSError:
        return {}
    result: dict[str, dict[str, str]] = {}
    inside = False
    for line in text.splitlines():
        if line.strip() == "## Active sessions":
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if not inside or not line.startswith("|"):
            continue
        columns = [re.sub(r"[*`]", "", value).strip() for value in line.split("|")[1:-1]]
        if len(columns) != 12 or columns[0] in {"id", "----"} or set(columns[0]) == {"-"}:
            continue
        result[columns[0]] = {
            "heartbeat": columns[5],
            "workspace": columns[7],
            "areas": columns[9],
            "context_role": columns[10],
            "status": columns[11].lower(),
        }
    return result


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _refresh_leased_board(board: Path) -> str | None:
    """Refresh the board from its canonical lease, returning an error if unsafe.

    The Markdown board is only a local mirror when ``lease.json`` exists.  Run
    the source-shipped coordination helper so pointer validation never accepts
    a released or transferred owner from stale local state.
    """
    coordination = (
        Path(__file__).resolve().parents[2]
        / "synthesis-project-management"
        / "scripts"
        / "coordination.py"
    )
    if not coordination.is_file():
        return f"coordination lease helper is unavailable: {coordination}"
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(coordination),
                "--board",
                str(board),
                "status",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"coordination lease refresh failed: {exc}"
    if result.returncode != 0:
        return (
            "coordination lease refresh failed: "
            + (result.stderr.strip() or result.stdout.strip() or f"exit={result.returncode}")
        )
    try:
        payload = json.loads(result.stdout)
        lease = payload["lease"]
    except (KeyError, TypeError, ValueError) as exc:
        return f"coordination lease refresh returned invalid evidence: {exc}"
    if not isinstance(lease, dict) or not lease.get("configured"):
        return "coordination lease is not configured on this machine"
    if lease.get("error") or not lease.get("refreshed"):
        return "coordination lease refresh failed: " + str(
            lease.get("error") or "remote mirror was not refreshed"
        )
    return None


def _workspace_claims(value: str) -> list[tuple[Path, str]]:
    claims: list[tuple[Path, str]] = []
    for item in re.split(r"[,;]|<br\s*/?>", value):
        clean = item.strip()
        if " @ " not in clean:
            continue
        path, branch = clean.rsplit(" @ ", 1)
        claims.append((Path(path.strip()).expanduser(), branch.strip()))
    return claims


def validate(
    payload: dict[str, object],
    board: Path,
    *,
    stale_after_minutes: int = 240,
    now: datetime | None = None,
    refresh_lease: bool = True,
) -> list[str]:
    """Return every reason the pointer is unsafe to inject."""
    issues: list[str] = []
    required = (
        "project",
        "plan",
        "worktree",
        "branch",
        "source_commit",
        "owner_session",
        "owner_lease",
    )
    missing = [field for field in required if not payload.get(field)]
    if missing:
        issues.append("missing pointer fields: " + ", ".join(missing))
        return issues

    project = Path(str(payload["project"])).expanduser()
    plan = Path(str(payload["plan"])).expanduser()
    worktree = Path(str(payload["worktree"])).expanduser()
    for label, path in (("project", project), ("plan", plan), ("worktree", worktree)):
        if not path.is_absolute():
            issues.append(f"{label} path is not absolute: {path}")
        if path.is_symlink():
            issues.append(f"{label} path must not be a symlink: {path}")
    if not project.is_dir():
        issues.append(f"project directory is missing: {project}")
    if not plan.is_file():
        issues.append(f"controlling plan is missing: {plan}")
    if not worktree.is_dir():
        issues.append(f"worktree is missing: {worktree}")
    if project.is_dir() and worktree.is_dir():
        try:
            project.resolve().relative_to(worktree.resolve())
        except ValueError:
            issues.append(f"project directory is outside pointer worktree: {project}")
    if plan.is_file() and project.is_dir():
        try:
            plan.resolve().relative_to(project.resolve())
        except ValueError:
            issues.append(f"controlling plan is outside project directory: {plan}")

    if refresh_lease:
        refresh_error = _refresh_leased_board(board)
        if refresh_error:
            issues.append(refresh_error)

    configured_lease = lease_url(board)
    if not configured_lease:
        issues.append(f"coordination lease is unavailable: {board}")
    elif payload.get("owner_lease") != configured_lease:
        issues.append(
            f"pointer lease {payload.get('owner_lease')!r} does not match {configured_lease!r}"
        )

    owner = str(payload["owner_session"])
    owner_state = sessions(board).get(owner)
    if not owner_state or owner_state["status"] in TERMINAL_STATUSES:
        issues.append(f"owner session is not active: {owner}")
    else:
        if owner_state["context_role"] != "owner":
            issues.append(
                f"owner session does not hold canonical context role: {owner}={owner_state['context_role']}"
            )
        claimed_workspace = any(
            claimed_path.resolve() == worktree.resolve()
            and claimed_branch == str(payload["branch"])
            for claimed_path, claimed_branch in _workspace_claims(
                owner_state["workspace"]
            )
        )
        if not claimed_workspace:
            issues.append(
                f"owner session {owner} does not claim exact pointer worktree and branch "
                f"{worktree} @ {payload['branch']}"
            )
        try:
            heartbeat = datetime.fromisoformat(owner_state["heartbeat"])
            reference = now or datetime.now(timezone.utc)
            if heartbeat.tzinfo is None:
                heartbeat = heartbeat.replace(tzinfo=timezone.utc)
            age_minutes = (reference - heartbeat).total_seconds() / 60
            if age_minutes < -5:
                issues.append(
                    f"owner session heartbeat is in the future: {owner} by {int(-age_minutes)} minutes"
                )
            elif age_minutes > stale_after_minutes:
                issues.append(
                    f"owner session lease expired: {owner} heartbeat is {int(age_minutes)} minutes old"
                )
        except ValueError:
            issues.append(f"owner session heartbeat is invalid: {owner_state['heartbeat']!r}")

    if worktree.is_dir():
        head = _run(["git", "-C", str(worktree), "rev-parse", "HEAD"])
        branch = _run(["git", "-C", str(worktree), "branch", "--show-current"])
        if head.returncode != 0:
            issues.append(f"worktree git identity unavailable: {head.stderr.strip()}")
        else:
            actual_head = head.stdout.strip()
            recorded_commit = str(payload["source_commit"])
            ancestry = _run(
                [
                    "git",
                    "-C",
                    str(worktree),
                    "merge-base",
                    "--is-ancestor",
                    recorded_commit,
                    actual_head,
                ]
            )
            if ancestry.returncode == 1:
                issues.append(
                    f"pointer source commit {recorded_commit} is not an ancestor of "
                    f"worktree HEAD {actual_head}"
                )
            elif ancestry.returncode != 0:
                issues.append(
                    "pointer ancestry check failed: "
                    + (ancestry.stderr.strip() or f"exit={ancestry.returncode}")
                )
        actual_branch = branch.stdout.strip()
        if branch.returncode != 0 or actual_branch != payload.get("branch"):
            issues.append(
                f"pointer branch {payload.get('branch')!r} is not worktree branch {actual_branch!r}"
            )
        upstream = _run(
            ["git", "-C", str(worktree), "rev-parse", "--verify", "origin/main"]
        )
        if upstream.returncode != 0:
            issues.append("local canonical ref origin/main is unavailable")
        else:
            behind = _run(
                ["git", "-C", str(worktree), "rev-list", "--count", "HEAD..origin/main"]
            )
            if behind.returncode != 0:
                issues.append(f"behind-main check failed: {behind.stderr.strip()}")
            elif int(behind.stdout.strip() or "0") > 0:
                issues.append(
                    f"worktree is {behind.stdout.strip()} commit(s) behind local origin/main"
                )
    return issues


def load_and_validate(
    pointer: Path, board: Path, *, stale_after_minutes: int = 240
) -> tuple[dict[str, object], list[str]]:
    if pointer.is_symlink():
        return {}, [f"active-project pointer must not be a symlink: {pointer}"]
    try:
        payload = json.loads(pointer.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"active-project pointer is unreadable: {pointer}: {exc}"]
    return payload, validate(
        payload, board, stale_after_minutes=stale_after_minutes
    )
