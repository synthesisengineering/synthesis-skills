#!/usr/bin/env python3
"""resume_probe.py — machine-readable project status for fresh resumes.

Reads a knowledge source's project index plus the project directory and
emits the static half of the resumption brief as JSON: identity, goal,
status, newest session, cross-machine changes, and the project format
version the R9 stale-format guard consumes.

Usage:
    resume_probe.py <source-root> <project-id> [--changes N]

Exit 0 with the JSON document on stdout. Exit 2 when the source root
or index is unreadable; exit 3 when the project id is unknown (the
R6 start path). A missing git remote degrades to empty recent_changes,
never an error (R10).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ENGINE_VERSION = "1.0.0"

# v1 layout: CONTEXT.md + REFERENCE.md + sessions/. v2 adds the
# .synthesis-project.yaml marker; unrecognized markers report "unknown".
FORMAT_V1 = ("CONTEXT.md", "REFERENCE.md", "sessions")


def load_index(source_root: Path) -> list[dict]:
    index_path = source_root / "projects" / "index.yaml"
    data = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("projects", [])
    if not isinstance(data, list):
        raise ValueError("projects/index.yaml must hold a project list")
    return [entry for entry in data if isinstance(entry, dict)]


def format_version(project_dir: Path) -> str:
    # Mirrors synthesis-project-management project_format.detect, which is
    # authoritative. Kept local so the probe stays dependency-free.
    if not project_dir.is_dir():
        return "missing"
    marker = project_dir / ".synthesis-project.yaml"
    if marker.is_file():
        try:
            data = yaml.safe_load(marker.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            return "unknown"
        return "v2" if data.get("format_version") == 2 else "unknown"
    present = [(project_dir / name).exists() for name in FORMAT_V1]
    if all(present):
        return "v1"
    return "partial"


def newest_session(project_dir: Path) -> tuple[str | None, str | None]:
    sessions_dir = project_dir / "sessions"
    if not sessions_dir.is_dir():
        return None, None
    files = sorted(sessions_dir.glob("*.md"))
    if not files:
        return None, None
    newest = max(files, key=lambda p: p.stat().st_mtime)
    mtime = datetime.fromtimestamp(newest.stat().st_mtime, tz=timezone.utc)
    return newest.stem, mtime.isoformat()


def recent_changes(source_root: Path, project_id: str, count: int) -> list[dict]:
    try:
        completed = subprocess.run(
            [
                "git", "log", f"-n{count}", "--format=%H%x00%cI%x00%s",
                "--", f"projects/{project_id}",
            ],
            cwd=source_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if completed.returncode != 0:
        return []
    changes = []
    for line in completed.stdout.splitlines():
        fields = line.split("\x00")
        if len(fields) != 3:
            continue
        changes.append({"sha": fields[0][:12], "date": fields[1], "subject": fields[2]})
    return changes


def probe(source_root: Path, project_id: str, count: int = 5) -> dict:
    entries = {str(e.get("id")): e for e in load_index(source_root)}
    if project_id not in entries:
        raise LookupError(f"unknown project id: {project_id}")
    entry = entries[project_id]
    project_dir = source_root / "projects" / project_id
    period, mtime = newest_session(project_dir)
    return {
        "engine": ENGINE_VERSION,
        "id": project_id,
        "name": entry.get("name", project_id),
        "goal": entry.get("description", ""),
        "status": entry.get("status", "unknown"),
        "updated": str(entry.get("last_session") or entry.get("updated", "") or ""),
        "newest_session": period,
        "session_mtime": mtime,
        "format_version": format_version(project_dir),
        "recent_changes": recent_changes(source_root, project_id, count),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit machine-readable project resume status.")
    parser.add_argument("source_root")
    parser.add_argument("project_id")
    parser.add_argument("--changes", type=int, default=5)
    args = parser.parse_args(argv)
    try:
        document = probe(Path(args.source_root), args.project_id, args.changes)
    except (OSError, ValueError) as exc:
        print(f"resume_probe: {exc}", file=sys.stderr)
        return 2
    except LookupError as exc:
        print(f"resume_probe: {exc}", file=sys.stderr)
        return 3
    print(json.dumps(document, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
