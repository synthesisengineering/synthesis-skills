#!/usr/bin/env python3
"""Validation primitives for the leased active-project pointer.

The pointer and same-machine continuity share one record contract: an
uncommitted project edit is acceptable exactly when a session-attributed
pending manifest records it. The attribution primitives live here so the
pointer validator and the continuity checks cannot drift apart.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_MANAGEMENT_SCRIPTS_DIR = (
    Path(__file__).resolve().parents[2]
    / "synthesis-project-management"
    / "scripts"
)
if str(PROJECT_MANAGEMENT_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_MANAGEMENT_SCRIPTS_DIR))

from coordination_schema import (
    SessionIdentity,
    parse_table_rows,
    row_identity,
    selector_matches,
)

TERMINAL_STATUSES = {"released", "complete", "completed", "closed"}


def repo_guard_state_root() -> Path:
    """Root of the session-attributed local handoff state."""
    return (
        Path(os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis")))
        / "repo-guard"
    )


def porcelain_paths(output: str, repo_root: Path) -> set[Path]:
    """Resolve `git status --porcelain=v1` lines to absolute paths."""
    paths: set[Path] = set()
    for line in output.splitlines():
        if len(line) < 4:
            continue
        value = line[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        value = value.strip().strip('"')
        if value:
            paths.add((repo_root / value).resolve(strict=False))
    return paths


def manifest_records_project(data: dict[str, object], project: Path) -> bool:
    """True when a pending manifest records any path inside the project."""
    project_root = project.resolve()
    values = data.get("remote_paths", data.get("paths", []))
    if not isinstance(values, list):
        return False
    for value in values:
        try:
            Path(str(value)).expanduser().resolve(strict=False).relative_to(
                project_root
            )
            return True
        except (OSError, ValueError):
            continue
    return False


def project_pending_manifests(
    project: Path, state_root: Path
) -> list[tuple[Path, dict]]:
    """Validated pending session manifests that record this project."""
    pending = state_root / "pending"
    found: list[tuple[Path, dict]] = []
    if not pending.is_dir():
        return found
    for path in sorted(pending.glob("*.json")):
        if path.is_symlink():
            raise ValueError(f"pending handoff manifest is a symlink: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        session_id = data.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise ValueError(f"pending handoff manifest has no session id: {path}")
        if not isinstance(data.get("paths"), list):
            raise ValueError(f"pending handoff manifest paths are invalid: {path}")
        if "remote_paths" in data and not isinstance(data.get("remote_paths"), list):
            raise ValueError(
                f"pending handoff manifest remote_paths are invalid: {path}"
            )
        expected = hashlib.sha256(session_id.encode("utf-8")).hexdigest() + ".json"
        if path.name != expected:
            raise ValueError(f"pending handoff manifest name mismatch: {path}")
        if manifest_records_project(data, project):
            found.append((path, data))
    return found


def unattributed_dirty_issues(
    project: Path,
    repo_root: Path,
    porcelain_output: str,
    state_root: Path,
) -> list[str]:
    """Apply the local-continuity attribution rule to a dirty project record.

    Same-machine continuity accepts a stopped or interrupted task whose
    uncommitted project edits are all recorded by session-attributed pending
    manifests (`LOCAL_READY` with a current Stop receipt, `LOCAL_RECOVERABLE`
    without one). The pointer accepts exactly that state. Any dirty path
    without an attributed manifest still fails closed.
    """
    dirty = porcelain_paths(porcelain_output, repo_root)
    try:
        manifests = project_pending_manifests(project, state_root)
    except (OSError, ValueError, TypeError) as exc:
        return [f"project attribution check failed: {exc}"]
    if not manifests:
        return [
            "project record has uncommitted or untracked changes with no "
            "session-attributed pending manifest"
        ]
    attributed = {
        Path(str(value)).expanduser().resolve(strict=False)
        for _, data in manifests
        for value in data.get("paths", [])
    }
    unattributed = sorted(dirty - attributed)
    if unattributed:
        preview = ", ".join(str(path) for path in unattributed[:5])
        return [
            "project record has unattributed uncommitted or untracked changes: "
            + preview
        ]
    return []


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
    for row in parse_table_rows(text):
        identity = row_identity(row)
        state = {
            "session_uuid": identity.session_uuid or identity.legacy_id,
            "compact_id": identity.compact_id,
            "speakable_id": identity.speakable_id,
            "legacy_id": identity.legacy_id,
            "heartbeat": row.get("heartbeat", row.get("started", "")),
            "workspace": row.get("workspace(s) / branch", ""),
            "areas": row.get("claimed areas (advisory lock)", ""),
            "context_role": row.get("context role", "none").lower(),
            "status": row.get("status", "").lower(),
        }
        for selector in identity.selectors():
            result[selector] = state
    return result


def resolve_session(
    states: dict[str, dict[str, str]], selector: str
) -> dict[str, str] | None:
    """Resolve UUID, compact, speakable, or legacy forms without ambiguity."""
    direct = states.get(selector)
    if direct is not None:
        return direct
    matches: dict[int, dict[str, str]] = {}
    for state in states.values():
        identity = SessionIdentity(
            state["session_uuid"],
            state["compact_id"],
            state["speakable_id"],
            state["legacy_id"],
        )
        if selector_matches(identity, selector):
            matches[id(state)] = state
    if len(matches) > 1:
        raise ValueError(f"ambiguous coordination session selector: {selector}")
    return next(iter(matches.values())) if matches else None


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
    problems = payload.get("problems")
    if not isinstance(problems, list):
        return "coordination lease refresh returned invalid problem evidence"
    if problems:
        return "coordination board is invalid after lease refresh: " + "; ".join(
            str(problem) for problem in problems
        )
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
        # Board rows conventionally annotate entries — "repo @ branch (new
        # branch)". The trailing parenthetical is commentary, not branch name.
        branch = re.sub(r"\s*\([^()]*\)$", "", branch.strip())
        claims.append((Path(path.strip()).expanduser(), branch))
    return claims


def validate(
    payload: dict[str, object],
    board: Path,
    *,
    stale_after_minutes: int = 240,
    now: datetime | None = None,
    refresh_lease: bool = True,
    state_root: Path | None = None,
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
    try:
        owner_state = resolve_session(sessions(board), owner)
    except ValueError as exc:
        issues.append(str(exc))
        owner_state = None
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
        project_status = _run(
            [
                "git",
                "-C",
                str(worktree),
                "-c",
                "core.quotePath=false",
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--",
                str(project),
            ]
        )
        if project_status.returncode != 0:
            issues.append(
                "project cleanliness check failed: "
                + (project_status.stderr.strip() or f"exit={project_status.returncode}")
            )
        elif project_status.stdout.strip():
            toplevel = _run(
                ["git", "-C", str(worktree), "rev-parse", "--show-toplevel"]
            )
            repo_root = (
                Path(toplevel.stdout.strip())
                if toplevel.returncode == 0 and toplevel.stdout.strip()
                else worktree
            )
            issues.extend(
                unattributed_dirty_issues(
                    project,
                    repo_root,
                    project_status.stdout,
                    repo_guard_state_root() if state_root is None else state_root,
                )
            )
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
            remote_refs = _run(
                [
                    "git",
                    "-C",
                    str(worktree),
                    "for-each-ref",
                    "--format=%(refname)",
                    "--contains",
                    actual_head,
                    "refs/remotes/",
                ]
            )
            if remote_refs.returncode != 0:
                issues.append(
                    "remote reachability check failed: "
                    + (remote_refs.stderr.strip() or f"exit={remote_refs.returncode}")
                )
            elif not remote_refs.stdout.strip():
                issues.append(
                    f"worktree HEAD {actual_head} is not reachable from any fetched remote ref"
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
    pointer: Path,
    board: Path,
    *,
    stale_after_minutes: int = 240,
    state_root: Path | None = None,
) -> tuple[dict[str, object], list[str]]:
    if pointer.is_symlink():
        return {}, [f"active-project pointer must not be a symlink: {pointer}"]
    try:
        payload = json.loads(pointer.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"active-project pointer is unreadable: {pointer}: {exc}"]
    return payload, validate(
        payload,
        board,
        stale_after_minutes=stale_after_minutes,
        state_root=state_root,
    )
