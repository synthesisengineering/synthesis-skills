#!/usr/bin/env python3
"""Resolve controlling plans once for state, handoff checks and hook payloads.

Structured state takes precedence over an explicit CONTEXT declaration.
An explicit no-plan declaration stops selection. Standalone links labeled
"plan", "active plan", "current plan" or "controlling plan" are shorthand
declarations; incidental and historical links are not declarations. A
declaration that cannot be verified never permits a different plan.
Cross-project references must stay inside the same Git worktree. Resolution
only reads local files and Git identity; it never fetches or updates state.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_UNSET = object()
_LINE = re.compile(
    r"^[ \t]*(?:\*\*)?Controlling plan:(?:\*\*)?[ \t]*(.*)$",
    re.MULTILINE | re.IGNORECASE,
)
_LINK = re.compile(r"\[[^\]\n]*\]\((?:<([^>\n]+)>|([^()\n]+))\)")
_ANNOTATED_PATH = re.compile(r"^(.+\.md)(?:[ \t]+\([^()\n]*\))?\.?$", re.IGNORECASE)
_NO_PLAN = re.compile(r"^[ \t]*(?:\*\*)?No active plan(?:[ \t]*(?:\*\*)?[.:—–-]|[ \t]*$)", re.IGNORECASE)
_PLAN_LABEL = re.compile(r"^\[(?:(?:active|current|controlling) )?plan\]", re.IGNORECASE)
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


@dataclass(frozen=True)
class PlanReference:
    declared: str | None
    resolved: Path | None
    value: str
    detail: str
    relative_path: str | None = None


def _invalid(target: object, detail: str) -> PlanReference:
    declared = target if isinstance(target, str) else repr(target)
    return PlanReference(declared, None, declared, f"controlling plan {detail}")


def _repo_root(project: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(project), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, timeout=10,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )
    if result.returncode:
        return None
    return Path(result.stdout.strip()).resolve(strict=True)


def _target(text: str) -> str | None:
    text = text.strip()
    link = _LINK.fullmatch(text)
    if not link:
        # A trailing item annotation describes the declaration, not the file.
        link = _LINK.match(text)
        if link and not re.fullmatch(r"[ \t]+\([^()\n]*\)\.?", text[link.end():]):
            return None
    if link:
        return (link.group(1) or link.group(2)).strip()
    if text.startswith("["):
        return None
    if text.startswith("`") and text.endswith("`"):
        text = text[1:-1]
    match = _ANNOTATED_PATH.fullmatch(text)
    return match.group(1) if match else None


def _symlink_component(path: Path, boundary: Path) -> bool:
    cursor = Path(path.anchor)
    for part in path.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            # OS aliases above the verified worktree (such as temporary
            # directory aliases) do not authorize links within its contents.
            destination = cursor.resolve()
            if (
                cursor.parent.resolve().is_relative_to(boundary)
                or destination == boundary
                or not boundary.is_relative_to(destination)
            ):
                return True
    return False


def resolve_plan_target(project: Path, target: object) -> PlanReference:
    """Validate a raw path and return its portable project-relative identity."""
    if not isinstance(target, str) or not target.strip():
        return _invalid(target, "declaration is empty or is not a path string")
    if any(ord(char) < 32 for char in target) or re.match(
        r"^[A-Za-z][A-Za-z0-9+.-]*:", target
    ):
        return _invalid(target, "must be a local Markdown file, not a URL or control-bearing path")
    if not target.lower().endswith(".md"):
        return _invalid(target, "must name a Markdown file")
    try:
        project = project.resolve(strict=True)
        root = _repo_root(project)
        boundary = root or project
        path = Path(target).expanduser()
        candidates = [path] if path.is_absolute() else [project / path]
        if not path.is_absolute() and root is not None and root != project:
            candidates.append(root / path)
        resolved_paths: set[Path] = set()
        failure = f"is not a readable file: {target}"
        confined_candidate = False
        for candidate in candidates:
            resolved = candidate.resolve()
            if not resolved.is_relative_to(boundary):
                if not confined_candidate:
                    failure = (
                        f"resolves outside the repository: {target}" if root else
                        f"cannot verify a cross-project reference without a repository: {target}"
                    )
                continue
            confined_candidate = True
            failure = f"is not a readable file: {target}"
            if _symlink_component(candidate, boundary):
                return _invalid(target, f"traverses a symlink: {target}")
            if resolved.is_file():
                # Existence alone is not a readable-file check.
                with resolved.open("rb") as handle:
                    handle.read(1)
                resolved_paths.add(resolved)
        if len(resolved_paths) > 1:
            return _invalid(target, f"is ambiguous between project and repository paths: {target}")
        if not resolved_paths:
            return _invalid(target, failure)
        resolved = resolved_paths.pop()
        return PlanReference(
            target, resolved, str(resolved), str(resolved),
            os.path.relpath(resolved, project),
        )
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        return _invalid(target, f"cannot be verified: {exc}")


def locate_plan(
    project: Path, context_text: str, *, controlling_plan: object = _UNSET
) -> PlanReference:
    """Derive a plan, preserving absent versus declared-but-invalid states."""
    if controlling_plan is not _UNSET:
        return resolve_plan_target(project, controlling_plan)
    # Examples inside fenced code are data, not active declarations.
    visible: list[str] = []
    fence: str | None = None
    for line in context_text.splitlines():
        marker = _FENCE.match(line)
        if fence is not None:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
        elif marker:
            fence = marker[1]
        else:
            visible.append(line)
    text = "\n".join(visible)
    declarations = _LINE.findall(text)
    absent = [line for line in visible if _NO_PLAN.match(line)]
    if len(declarations) + len(absent) > 1:
        return _invalid((declarations + absent)[0], "has multiple explicit declarations")
    if absent or (declarations and declarations[0].strip().lower().rstrip(".") == "none"):
        return PlanReference(None, None, "unknown", "CONTEXT.md explicitly declares no active plan")
    if declarations:
        target = _target(declarations[0])
        if target is None:
            return _invalid(declarations[0], "declaration is empty or malformed")
        return resolve_plan_target(project, target)
    # A link embedded in a checklist or paragraph describes a dependency,
    # not project authority. Never rank targets by their path prefix.
    shorthand: list[str] = []
    declaration_section = True
    for line in visible:
        heading = re.match(r"^ {0,3}#{2,6}[ \t]+(.+?)[ \t]*#*[ \t]*$", line)
        if heading:
            declaration_section = bool(re.fullmatch(r"(?:(?:active|current|controlling) )?plan", heading[1], re.IGNORECASE))
        elif declaration_section and _PLAN_LABEL.match(line.strip()):
            shorthand.append(line.strip())
    if len(shorthand) > 1:
        return _invalid(shorthand[0], "has multiple standalone declarations")
    if shorthand:
        target = _target(shorthand[0])
        if target is None:
            return _invalid(shorthand[0], "standalone declaration is malformed")
        return resolve_plan_target(project, target)
    return PlanReference(None, None, "unknown", "CONTEXT.md has no linked plan")
