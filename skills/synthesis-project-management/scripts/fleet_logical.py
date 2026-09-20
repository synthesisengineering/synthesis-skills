#!/usr/bin/env python3
"""Logical repo-qualified claim resolution for fleet use.

Design: 2026-09-19-fleet-architecture.md section 2.3. With both Macs checking
out the same repos at the same ``~``-relative paths, textual claims coincide;
where checkouts differ (worktrees, renamed dirs), overlap MUST be evaluated
on (repo remote URL + branch + repo-relative path), not on the absolute
string. Unresolvable paths (a deleted worktree on the other Mac) fail closed
as conflicting rather than disjoint.

This module is pure resolution: it never reads the board. The handoff engine
(``fleet_handoff``) and the fleet doctor (``fleet_doctor``) call it to compare
claims whose absolute spellings disagree across Macs.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

GIT_TIMEOUT_SECONDS = 30


class FleetLogicalError(ValueError):
    """A workspace or claim that cannot be resolved to a repo identity."""


def normalize_remote_url(url: str) -> str:
    """One canonical spelling for a git remote URL.

    Trailing slashes and a single trailing ``.git`` are stripped so
    ``https://host/org/repo`` and ``https://host/org/repo.git`` compare
    equal. Comparison itself is case-sensitive: hosts are case-insensitive
    but repo paths need not be, and conflating them would be wrong.
    """
    text = (url or "").strip().rstrip("/")
    if text.endswith(".git"):
        text = text[: -len(".git")]
    return text.rstrip("/")


def workspace_parts(workspace: str) -> tuple[str, str]:
    """Split a ``<path> @ <branch>`` workspace claim into its halves."""
    text = (workspace or "").strip()
    if " @ " in text:
        path, branch = text.rsplit(" @ ", 1)
        return path.strip(), branch.strip()
    return text, "unknown"


def _run_git(args: list[str], cwd: Path, *, timeout: float = GIT_TIMEOUT_SECONDS):
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def resolve_workspace_identity(
    workspace: str, *, git_runner=None
) -> tuple[str, str] | None:
    """Resolve a workspace to ``(remote_url, branch)``.

    The branch is the workspace's *declared* branch (the ``@ branch`` half),
    not the checkout's current branch: the claim names the line of work, and
    a destination on a detached HEAD still means the same scope. The remote
    URL comes from the checkout's ``remote.origin.url``. Returns None when
    the path is missing, is not a git checkout, or has no origin remote —
    callers treat None as conflicting (fail closed).
    """
    path_text, branch = workspace_parts(workspace)
    if not path_text or not branch:
        return None
    runner = git_runner or _run_git
    try:
        completed = runner(
            ["config", "--get", "remote.origin.url"], Path(path_text).expanduser()
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    remote = normalize_remote_url(completed.stdout.strip())
    if not remote:
        return None
    return remote, branch


def logical_workspace_conflict(left: str, right: str, *, git_runner=None) -> bool:
    """Whether two workspaces name the same repo line on any Mac.

    Same normalized ``(remote_url, branch)`` at different absolute paths is
    the fleet's core alias: Mac B's ``~/workspaces/kb`` and Mac A's
    ``~/workspaces/kb`` are one repo. Either side unresolvable (deleted
    worktree, missing remote) fails closed as conflicting.
    """
    left_identity = resolve_workspace_identity(left, git_runner=git_runner)
    right_identity = resolve_workspace_identity(right, git_runner=git_runner)
    if left_identity is None or right_identity is None:
        return True
    return left_identity == right_identity


def repo_relative_path(claim_path: str, checkout: str) -> str | None:
    """The repo-relative form of an absolute claim inside a checkout.

    Returns None when the claim is not absolute, when the checkout does not
    exist, or when the claim escapes the checkout. Glob suffixes (``**``,
    ``*``) survive: only the literal prefix resolves against the filesystem.
    """
    if not claim_path or not os.path.isabs(claim_path):
        return None
    checkout_path = os.path.realpath(os.path.expanduser(checkout))
    if not os.path.isdir(checkout_path):
        return None
    literal = claim_path
    for token in ("*", "?", "["):
        index = literal.find(token)
        if index >= 0:
            literal = literal[:index]
    literal = literal.rstrip("/") or "/"
    resolved = os.path.realpath(literal) if os.path.exists(literal) else literal
    try:
        relative = os.path.relpath(resolved, checkout_path)
    except ValueError:
        return None
    if relative.startswith(".."):
        return None
    remainder = claim_path[len(literal):]
    glued = relative if not remainder else relative.rstrip("/") + remainder
    return glued


def _segments_intersect(left: str, right: str) -> bool:
    import fnmatch

    if not any(c in left + right for c in "*?["):
        return left == right
    points = {1, ord("_"), 0x10FFFF}
    for character in left + right:
        points.update(
            p
            for p in (ord(character) - 1, ord(character), ord(character) + 1)
            if 0 < p <= 0x10FFFF
        )
    alphabet = [chr(p) for p in points if chr(p) != "/"]
    pending = [(0, 0, False)]
    seen = set()
    while pending:
        i, j, consumed = pending.pop()
        if (i, j, consumed) in seen:
            continue
        seen.add((i, j, consumed))
        if i == len(left) and j == len(right) and consumed:
            return True
        if i < len(left) and left[i] == "*":
            pending.append((i + 1, j, consumed))
        if j < len(right) and right[j] == "*":
            pending.append((i, j + 1, consumed))
        if (
            i < len(left)
            and j < len(right)
            and any(
                fnmatch.fnmatchcase(c, left[i]) and fnmatch.fnmatchcase(c, right[j])
                for c in alphabet
            )
        ):
            pending.append(
                (
                    i if left[i] == "*" else i + 1,
                    j if right[j] == "*" else j + 1,
                    True,
                )
            )
    return False


def _patterns_intersect(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    pending = [(0, 0)]
    seen = set()
    while pending:
        i, j = pending.pop()
        if (i, j) in seen:
            continue
        seen.add((i, j))
        if i == len(left) and j == len(right):
            return True
        if i < len(left) and left[i] == "**":
            pending.append((i + 1, j))
        if j < len(right) and right[j] == "**":
            pending.append((i, j + 1))
        if i < len(left) and j < len(right) and _segments_intersect(
            "*" if left[i] == "**" else left[i],
            "*" if right[j] == "**" else right[j],
        ):
            pending.append(
                (
                    i if left[i] == "**" else i + 1,
                    j if right[j] == "**" else j + 1,
                )
            )
    return False


def _relative_parts(pattern: str) -> tuple[str, ...]:
    parts = tuple(
        part for part in pattern.strip("/").split("/") if part and part != "."
    )
    if any(c in pattern for c in "*?["):
        return parts
    return (*parts, "**")


def relative_patterns_intersect(left: str, right: str) -> bool:
    """Glob intersection on repo-relative claim patterns."""
    return _patterns_intersect(_relative_parts(left), _relative_parts(right))


def logical_claim_conflict(
    left_claim: str,
    right_claim: str,
    left_workspaces: tuple[str, ...] | list[str] = (),
    right_workspaces: tuple[str, ...] | list[str] = (),
    *,
    git_runner=None,
) -> bool:
    """Whether two claims collide on (remote, branch, repo-relative path).

    Each absolute claim resolves through the workspace checkout that contains
    it: same normalized ``(remote_url, branch)`` plus intersecting
    repo-relative patterns is a conflict even when the absolute spellings
    share nothing. Either side unresolvable fails closed as conflicting.
    Relative (already repo-relative) claims on the same workspace identity
    compare directly; claims with no workspace context are out of scope and
    report no logical conflict (the textual check owns them).
    """
    left_workspaces = list(left_workspaces or ())
    right_workspaces = list(right_workspaces or ())
    if not left_workspaces or not right_workspaces:
        return False
    for left_workspace in left_workspaces:
        left_path, _ = workspace_parts(left_workspace)
        left_identity = resolve_workspace_identity(
            left_workspace, git_runner=git_runner
        )
        if left_identity is None:
            return True
        for right_workspace in right_workspaces:
            right_path, _ = workspace_parts(right_workspace)
            right_identity = resolve_workspace_identity(
                right_workspace, git_runner=git_runner
            )
            if right_identity is None:
                return True
            if left_identity != right_identity:
                continue
            left_relative = (
                repo_relative_path(left_claim, left_path)
                if os.path.isabs(left_claim)
                else left_claim
            )
            right_relative = (
                repo_relative_path(right_claim, right_path)
                if os.path.isabs(right_claim)
                else right_claim
            )
            if left_relative is None or right_relative is None:
                return True
            if relative_patterns_intersect(left_relative, right_relative):
                return True
    return False
