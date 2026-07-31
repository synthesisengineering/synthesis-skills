#!/usr/bin/env python3
"""Shared parsing helpers for synthesis project context."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


CHECKLIST = re.compile(r"^(?:[-*]|\d+\.)\s+\[([ xX])\]\s+")


def _git(project: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(project), *arguments],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def record_freshness(project: Path) -> tuple[bool, str]:
    """Compare the local project record with its last-fetched upstream.

    A checkout left behind by another machine or session reports a stale
    phase, status, and plan with full confidence; both clients resume from
    whatever the record file says. This counts upstream commits that touch
    the project subtree but are absent locally. It never touches the
    network — the comparison is against the already-fetched remote-tracking
    ref, so run `git fetch` first when currency matters.
    """
    inside = _git(project, "rev-parse", "--show-toplevel")
    if inside.returncode != 0:
        return False, inside.stderr.strip() or "not inside a git repository"
    upstream = _git(
        project, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
    )
    if upstream.returncode != 0:
        return True, "no upstream configured; freshness not comparable"
    upstream_name = upstream.stdout.strip()
    behind = _git(
        project, "rev-list", "--count", f"HEAD..{upstream_name}", "--", str(project)
    )
    if behind.returncode != 0:
        return False, behind.stderr.strip() or "freshness comparison failed"
    count = int(behind.stdout.strip() or "0")
    if count == 0:
        return True, f"record current with fetched {upstream_name}"
    return False, (
        f"project record is {count} commit(s) behind fetched {upstream_name}; "
        "pull the checkout before trusting phase, status, or plan"
    )


def extract(context: str, key: str) -> str:
    """Extract a bold metadata field from CONTEXT.md."""
    match = re.search(rf"^\*\*{re.escape(key)}:\*\*\s*(.+)$", context, re.MULTILINE)
    return match.group(1).strip() if match else "unknown"


def next_actions(context: str, limit: int = 5) -> list[str]:
    """Return pending What's Next checklist items, including continuations."""
    match = re.search(
        r"^## What's Next[^\n]*\n(.*?)(?=^## |\Z)",
        context,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return []

    lines = [line.strip() for line in match.group(1).splitlines()]
    items: list[tuple[bool, list[str]]] = []
    current: tuple[bool, list[str]] | None = None
    for line in lines:
        item = CHECKLIST.match(line)
        if item:
            if current is not None:
                items.append(current)
            current = (item.group(1).lower() == "x", [line])
        elif current is not None and line:
            current[1].append(line)
    if current is not None:
        items.append(current)

    pending = [" ".join(parts) for done, parts in items if not done]
    return pending[:limit]
