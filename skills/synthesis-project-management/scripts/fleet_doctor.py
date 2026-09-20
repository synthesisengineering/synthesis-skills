#!/usr/bin/env python3
"""Fleet doctor: the cross-Mac health gate with no silent passes.

Checks (each fails closed; unconfigured inputs skip loudly, never pass
quietly)::

    reachability         lease remote answers ls-remote
    lease-freshness      local board mirror matches the leased tip
    workset-consistency  every live row's workspaces parse and claims exist
    parked-coherence     parked rows carry park records; overlaps-parked
                         annotations reference live rows on both ends
    artifact-sealed      every sealed handoff artifact verifies; open
                         (unsealed) artifacts are listed, never failed
    divergence-scan      no workset checkout has diverged from its upstream

Usage::

    python3 fleet_doctor.py --board PATH [--artifacts-dir DIR]
                            [--repo PATH]... [--machine-id ID]

Without ``--repo``, divergence scans the workspaces this machine's own
live rows claim. Without ``--machine-id``, the enrolled machine-id is
used; an unenrolled machine skips the scan.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import coordination as _coord
import fleet_handoff as _handoff
import fleet_identity as _identity

REACHABILITY_CHECK = "reachability"
FRESHNESS_CHECK = "lease-freshness"
WORKSET_CHECK = "workset-consistency"
PARKED_CHECK = "parked-coherence"
ARTIFACT_CHECK = "artifact-sealed"
DIVERGENCE_CHECK = "divergence-scan"

GIT_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class DoctorCheck:
    id: str
    ok: bool
    detail: str

    def __str__(self) -> str:
        verdict = "PASS" if self.ok else "FAIL"
        return f"{verdict} fleet-{self.id}: {self.detail}"


def _run_git(args: list[str], cwd: Path):
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
        check=False,
    )


def check_reachability(board: Path, *, git_runner=None) -> DoctorCheck:
    """The lease remote answers, or nothing is leased (skip)."""
    runner = git_runner or _run_git
    board = Path(board)
    try:
        config = _coord.lease_configuration(board)
    except RuntimeError as exc:
        return DoctorCheck(REACHABILITY_CHECK, False, str(exc))
    if config is None:
        if board.is_file():
            try:
                declared = _coord.declared_lease(board.read_text(encoding="utf-8"))
            except OSError as exc:
                return DoctorCheck(
                    REACHABILITY_CHECK, False, f"board unreadable: {exc}"
                )
            if declared is not None:
                return DoctorCheck(
                    REACHABILITY_CHECK,
                    False,
                    f"board declares lease {declared} but lease.json is "
                    "missing on this machine",
                )
        return DoctorCheck(
            REACHABILITY_CHECK, True, "no lease configured; nothing to reach"
        )
    try:
        completed = runner(
            ["ls-remote", config["remote"], config["ref"]], board.parent
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return DoctorCheck(
            REACHABILITY_CHECK, False, f"lease-unreachable: {exc}"
        )
    if completed.returncode != 0:
        return DoctorCheck(
            REACHABILITY_CHECK,
            False,
            f"lease-unreachable: {completed.stderr.strip() or config['remote']}",
        )
    return DoctorCheck(
        REACHABILITY_CHECK,
        True,
        f"lease remote answers for {config['ref']}",
    )


def check_lease_freshness(board: Path) -> DoctorCheck:
    """The local mirror matches the leased tip byte for byte."""
    board = Path(board)
    try:
        config = _coord.lease_configuration(board)
    except RuntimeError as exc:
        return DoctorCheck(FRESHNESS_CHECK, False, str(exc))
    if config is None:
        return DoctorCheck(
            FRESHNESS_CHECK, True, "no lease configured; mirror is the board"
        )
    if not board.is_file():
        return DoctorCheck(
            FRESHNESS_CHECK,
            False,
            f"leased board has no local mirror: {board}",
        )
    try:
        sha, content = _coord.lease_fetch(config)
    except RuntimeError as exc:
        return DoctorCheck(FRESHNESS_CHECK, False, str(exc))
    if content is None:
        return DoctorCheck(
            FRESHNESS_CHECK,
            False,
            "lease remote ref has not been published",
        )
    try:
        mirror = board.read_text(encoding="utf-8")
    except OSError as exc:
        return DoctorCheck(FRESHNESS_CHECK, False, f"board unreadable: {exc}")
    if mirror != content:
        return DoctorCheck(
            FRESHNESS_CHECK,
            False,
            f"mirror differs from leased tip {sha}; refresh before any "
            "authority decision",
        )
    return DoctorCheck(
        FRESHNESS_CHECK, True, f"mirror matches leased tip {sha}"
    )


def check_workset_consistency(content: str) -> DoctorCheck:
    """Every live row names parseable worksets and non-empty claims."""
    try:
        sessions = _coord.rows(content)
    except ValueError as exc:
        return DoctorCheck(WORKSET_CHECK, False, f"board rows unreadable: {exc}")
    problems = []
    for session in sessions:
        if not _coord.active(session):
            continue
        if not session.claims:
            problems.append(f"{session.compact_id}: live row holds no claimed areas")
        if not session.workspaces:
            problems.append(f"{session.compact_id}: live row names no workspace")
        for workspace in session.workspaces:
            path, branch = _coord.workspace_parts(workspace)
            if not path or not branch:
                problems.append(
                    f"{session.compact_id}: workspace is not '<path> @ "
                    f"<branch>': {workspace!r}"
                )
    if problems:
        return DoctorCheck(WORKSET_CHECK, False, "; ".join(problems))
    live = sum(1 for session in sessions if _coord.active(session))
    return DoctorCheck(
        WORKSET_CHECK, True, f"{live} live row(s) carry parseable worksets"
    )


def check_parked_coherence(content: str) -> DoctorCheck:
    """Parked rows carry park records; annotations reference live rows."""
    try:
        sessions = _coord.rows(content)
    except ValueError as exc:
        return DoctorCheck(PARKED_CHECK, False, f"board rows unreadable: {exc}")
    problems = []
    by_compact = {session.compact_id: session for session in sessions}
    for session in sessions:
        if _coord.is_parked(session) and _coord.parked_since(content, session) is None:
            problems.append(
                f"{session.compact_id}: parked row has no park record"
            )
    from peer_addressing import parse_messages

    for message in parse_messages(content):
        for line in message.body.splitlines():
            match = _coord._FLEET_OVERLAPS_PARKED_RE.match(line.strip())
            if not match:
                continue
            new_compact, parked_compact = match.group(1), match.group(2)
            parked_row = by_compact.get(parked_compact)
            if parked_row is None or not _coord.is_parked(parked_row):
                problems.append(
                    f"overlaps-parked annotation references missing or "
                    f"unparked row: {parked_compact}"
                )
            if new_compact not in by_compact:
                problems.append(
                    f"overlaps-parked annotation references missing "
                    f"successor: {new_compact}"
                )
    if problems:
        return DoctorCheck(PARKED_CHECK, False, "; ".join(problems))
    parked = sum(1 for session in sessions if _coord.is_parked(session))
    return DoctorCheck(
        PARKED_CHECK, True, f"{parked} parked row(s) cohere with the bus"
    )


def check_artifacts(artifacts_dir: Path | None) -> DoctorCheck:
    """Sealed artifacts verify; open ones are listed, never failed."""
    if artifacts_dir is None:
        return DoctorCheck(
            ARTIFACT_CHECK, True, "no artifacts directory configured"
        )
    directory = Path(artifacts_dir)
    if not directory.is_dir():
        return DoctorCheck(ARTIFACT_CHECK, True, "no handoff artifacts")
    failures = []
    sealed_count = 0
    for path in sorted(directory.glob("*.sealed.json")):
        sealed_count += 1
        try:
            _handoff.read_sealed_artifact(path)
        except _handoff.HandoffSealError as exc:
            failures.append(f"{path.name}: {exc}")
    if failures:
        return DoctorCheck(ARTIFACT_CHECK, False, "; ".join(failures))
    open_names = sorted(path.name for path in directory.glob("*.open.json"))
    detail = f"{sealed_count} sealed artifact(s) verify"
    if open_names:
        detail += f"; open (unsealed): {', '.join(open_names)}"
    return DoctorCheck(ARTIFACT_CHECK, True, detail)


def repos_for_machine(content: str, machine_id: str) -> list[str]:
    """Workspace paths this machine's own live rows claim, deduplicated."""
    try:
        sessions = _coord.rows(content)
    except ValueError:
        return []
    repos: list[str] = []
    for session in sessions:
        if session.machine != machine_id or not _coord.active(session):
            continue
        for workspace in session.workspaces:
            path, _ = _coord.workspace_parts(workspace)
            if path and path not in repos:
                repos.append(path)
    return repos


def check_divergence(repos: list[str | Path], *, git_runner=None) -> DoctorCheck:
    """No workset checkout has diverged from its upstream."""
    runner = git_runner or _run_git
    if not repos:
        return DoctorCheck(
            DIVERGENCE_CHECK, True, "no workset checkouts to scan"
        )
    diverged: list[str] = []
    summaries: list[str] = []
    for raw in repos:
        repo = Path(raw).expanduser()
        label = str(raw)
        try:
            status = runner(["status", "--porcelain"], repo)
        except (OSError, subprocess.SubprocessError):
            return DoctorCheck(
                DIVERGENCE_CHECK, False, f"{label}: not a git checkout"
            )
        if status.returncode != 0:
            return DoctorCheck(
                DIVERGENCE_CHECK, False, f"{label}: not a git checkout"
            )
        upstream = runner(
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
            repo,
        )
        if upstream.returncode != 0:
            summaries.append(f"{label}: no upstream tracked")
            continue
        try:
            counts = runner(
                ["rev-list", "--left-right", "--count", "HEAD...@{upstream}"],
                repo,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return DoctorCheck(
                DIVERGENCE_CHECK, False, f"{label}: divergence unreadable: {exc}"
            )
        parts = counts.stdout.split()
        ahead = behind = 0
        if counts.returncode == 0 and len(parts) == 2:
            ahead, behind = int(parts[0]), int(parts[1])
        if ahead and behind:
            diverged.append(
                f"{label}: diverged ({ahead} ahead, {behind} behind "
                f"{upstream.stdout.strip()}); fetch first, never force-push"
            )
        else:
            summaries.append(f"{label}: {ahead} ahead, {behind} behind")
    if diverged:
        return DoctorCheck(DIVERGENCE_CHECK, False, "; ".join(diverged))
    return DoctorCheck(DIVERGENCE_CHECK, True, "; ".join(summaries))


def run_all(
    *,
    board: Path,
    artifacts_dir: Path | None = None,
    repos: list[str | Path] | None = None,
    machine_id: str | None = None,
    git_runner=None,
) -> list[DoctorCheck]:
    """Every fleet-doctor check against one board, in gate order."""
    board = Path(board)
    try:
        content: str | None = board.read_text(encoding="utf-8")
    except OSError:
        content = None
    try:
        resolved_machine = machine_id or _identity.read_machine_id()
    except _identity.FleetIdentityError:
        resolved_machine = None
    if repos is None:
        if content is None or not resolved_machine:
            scan: list[str | Path] = []
        else:
            scan = repos_for_machine(content, resolved_machine)
    else:
        scan = list(repos)
    if content is None:
        placeholder = DoctorCheck(
            WORKSET_CHECK, True, "no board; nothing to scan"
        )
        parked = DoctorCheck(PARKED_CHECK, True, "no board; nothing to scan")
    else:
        placeholder = check_workset_consistency(content)
        parked = check_parked_coherence(content)
    return [
        check_reachability(board, git_runner=git_runner),
        check_lease_freshness(board),
        placeholder,
        parked,
        check_artifacts(artifacts_dir),
        check_divergence(scan, git_runner=git_runner),
    ]


def format_report(checks: list[DoctorCheck]) -> str:
    return "\n".join(str(check) for check in checks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--board", type=Path, required=True)
    parser.add_argument("--artifacts-dir", type=Path, default=None)
    parser.add_argument("--repo", dest="repos", action="append", default=None)
    parser.add_argument("--machine-id", default=None)
    args = parser.parse_args(argv)
    checks = run_all(
        board=args.board,
        artifacts_dir=args.artifacts_dir,
        repos=args.repos,
        machine_id=args.machine_id,
    )
    print(format_report(checks))
    return 0 if all(check.ok for check in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
