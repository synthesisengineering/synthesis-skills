#!/usr/bin/env python3
"""Single source of truth for locating a project's controlling plan.

CONTEXT.md can declare its controlling plan three ways, in precedence
order:

1. An explicit ``Controlling plan:`` line naming an absolute or
   repo-relative path — optionally as a markdown link, optionally with a
   trailing parenthetical annotation such as ``(item 2.1)``.
2. A relative markdown link that climbs out of the project directory
   (``../program/resources/artifacts/x-work-plan.md``): a bounded arc
   governed by its parent program's work plan.
3. The legacy project-local link form ``(resources/artifacts/...plan...md)``.

Every consumer — conformance's project summary, the stopped-task payload
builders — must derive the plan through :func:`locate_plan` so the
derivations cannot drift; the two pre-existing per-site regexes had
already drifted (case sensitivity) when this module replaced them.

Declared-but-unresolvable plans fail closed: ``resolved`` stays ``None``
and ``detail`` names the reason, including a relative target that
resolves outside the repository.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

PLAN_LINE_PATTERN = re.compile(
    r"^(?:\*\*)?Controlling plan:(?:\*\*)?\s*(.+)$", re.MULTILINE
)
PLAN_LINE_LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
PLAN_LOCAL_LINK_PATTERN = re.compile(
    r"\((resources/artifacts/[^)\n]*plan[^)\n]*\.md)\)", re.IGNORECASE
)
PLAN_RELATIVE_LINK_PATTERN = re.compile(
    r"\(((?:\.\./)+[^)\s]*plan[^)\s]*\.md)\)", re.IGNORECASE
)


@dataclass
class PlanReference:
    """One project's controlling-plan derivation.

    ``declared`` is the raw declared target (None when CONTEXT.md declares
    nothing). ``resolved`` is the existing file the declaration resolves
    to, or None when the declaration cannot be satisfied. ``value`` is the
    string consumers publish (summary field, payload line): the resolved
    path, the declared target when unresolvable, or ``"unknown"``. The
    legacy project-local form keeps its historical unresolved
    project-joined ``value`` so existing pointer comparisons stay stable.
    """

    declared: str | None
    resolved: Path | None
    value: str
    detail: str
    legacy_local: bool = False


def _declared_target(remainder: str) -> str:
    remainder = remainder.strip()
    link = PLAN_LINE_LINK_PATTERN.search(remainder)
    if link:
        return link.group(1)
    remainder = re.sub(r"\s*\([^)]*\)\s*$", "", remainder)
    return remainder.rstrip(".").strip()


def _repo_root(project: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(project), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return Path(result.stdout.strip()).resolve()


def _resolve_declared(project: Path, target: str) -> tuple[Path | None, str]:
    expanded = Path(target).expanduser()
    if expanded.is_absolute():
        resolved = expanded.resolve()
        if resolved.is_file():
            return resolved, str(resolved)
        return None, f"declared controlling plan is not a file: {target}"
    repo_root = _repo_root(project)
    bases = [project]
    if repo_root is not None:
        bases.append(repo_root)
    for base in bases:
        resolved = (base / expanded).resolve()
        if not resolved.is_file():
            continue
        if repo_root is None:
            return None, (
                "cannot verify the declared controlling plan stays inside "
                f"the repository: {target}"
            )
        if not resolved.is_relative_to(repo_root):
            return None, (
                f"declared controlling plan resolves outside the repository: {target}"
            )
        return resolved, str(resolved)
    return None, f"declared controlling plan is not a file: {target}"


def locate_plan(project: Path, context_text: str) -> PlanReference:
    line = PLAN_LINE_PATTERN.search(context_text)
    declared = _declared_target(line.group(1)) if line else None
    if not declared:
        relative = PLAN_RELATIVE_LINK_PATTERN.search(context_text)
        if relative:
            declared = relative.group(1)
    if declared:
        resolved, detail = _resolve_declared(project, declared)
        value = str(resolved) if resolved is not None else declared
        return PlanReference(declared, resolved, value, detail)
    local = PLAN_LOCAL_LINK_PATTERN.search(context_text)
    if local:
        plan = project / local.group(1)
        exists = plan.is_file()
        return PlanReference(
            declared=local.group(1),
            resolved=plan if exists else None,
            value=str(plan),
            detail=str(plan) if exists else f"active plan is missing: {plan}",
            legacy_local=True,
        )
    return PlanReference(None, None, "unknown", "CONTEXT.md has no linked plan")
