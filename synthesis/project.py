"""Project continuity (R1): find a project, brief a session on it, hand it off."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from synthesis import board, paths

BRIEF_LIMIT = 6000
STATE_BLOCK = re.compile(r"<!-- synthesis-current-state:start -->(.*?)<!-- synthesis-current-state:end -->", re.S)


def roots() -> list[Path]:
    configured = paths.config().get("knowledge_roots")
    if configured:
        return [Path(os.path.expanduser(r)) for r in configured]
    workspaces = Path.home() / "workspaces"
    return sorted(workspaces.glob("*/ai-knowledge-*")) if workspaces.is_dir() else []


def find(project_id: str) -> Path | None:
    matches = [r / "projects" / project_id for r in roots() if (r / "projects" / project_id).is_dir()]
    return matches[0] if len(matches) == 1 else None


def brief(project_dir: Path) -> str:
    """What a session must have in context to continue: the directive, then current state."""
    parts = []
    directive = project_dir / "PRIME-DIRECTIVE.md"
    if directive.is_file():
        parts.append(directive.read_text(encoding="utf-8").strip())
    context = project_dir / "CONTEXT.md"
    if context.is_file():
        text = context.read_text(encoding="utf-8")
        block = STATE_BLOCK.search(text)
        parts.append("Current state (CONTEXT.md):\n" + (block.group(1).strip() if block else "\n".join(text.splitlines()[:60])))
    text = f"Active project: {project_dir.name} ({project_dir})\n\n" + "\n\n".join(parts)
    return text if len(text) <= BRIEF_LIMIT else text[: BRIEF_LIMIT - 40] + "\n[... read the files for the rest]"


def check(project_dir: Path, *, max_context_lines: int = 150) -> list[str]:
    problems = []
    context = project_dir / "CONTEXT.md"
    if not context.is_file():
        problems.append("CONTEXT.md is missing")
    elif len(context.read_text(encoding="utf-8").splitlines()) > max_context_lines:
        problems.append(f"CONTEXT.md is over {max_context_lines} lines; move history to sessions/ or REFERENCE.md")
    return problems


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def handoff(session_id: str, message: str = "Update project records") -> list[str]:
    """Commit and push the changes inside this session's claims (R1.4). Claims are the attribution."""
    session = board.load(session_id)
    if session is None or not session.claims:
        return ["nothing claimed, nothing to hand off"]
    report = []
    by_repo: dict[Path, list[str]] = {}
    for claim in session.claims:
        base = Path(claim[:-3] if claim.endswith("/**") else claim)
        top = _git(base if base.is_dir() else base.parent, "rev-parse", "--show-toplevel")
        if top.returncode == 0:
            by_repo.setdefault(Path(top.stdout.strip()), []).append(str(base))
    for repo, claimed in by_repo.items():
        _git(repo, "add", "--", *claimed)
        if _git(repo, "diff", "--cached", "--quiet", "--", *claimed).returncode == 0:
            report.append(f"{repo}: nothing changed")
            continue
        commit = _git(repo, "commit", "-m", message, "--", *claimed)
        push = _git(repo, "push") if commit.returncode == 0 else commit
        report.append(f"{repo}: " + ("committed and pushed" if push.returncode == 0 else (push.stderr or push.stdout).strip()))
    return report
