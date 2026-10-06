#!/usr/bin/env python3
"""resume_probe.py — machine-readable project status for fresh resumes.

Reads a knowledge source's project index plus the project directory and
emits the static half of the resumption brief as JSON: identity, goal,
status, newest session and cross-machine changes.

Usage:
    resume_probe.py <source-root> <project-id> [--changes N]

Exit 0 with the JSON document on stdout. Exit 2 when the source root
or index is unreadable; exit 3 when the project id is unknown (the
R6 start path). A missing git remote degrades to empty recent_changes,
never an error (R10). Standard library only.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # the plugin root, which holds synthesis/
from synthesis.yamlish import load  # noqa: E402

ENGINE_VERSION = "2.0.0"


def load_index(source_root: Path) -> list[dict]:
    """Each project's entry in projects/index.yaml, under `projects:` or as a bare list, read by the
    plugin's YAML reader: folded (`>`) and literal (`|`) values, nested lists and maps included."""
    data = load((source_root / "projects" / "index.yaml").read_text(encoding="utf-8"))
    items = data.get("projects") if isinstance(data, dict) else data
    return [entry for entry in (items if isinstance(items, list) else []) if isinstance(entry, dict) and entry.get("id")]


def _text(entry: dict, key: str, default: str) -> str:
    value = entry.get(key)
    return default if value is None else str(value).strip()


def newest_session(project_dir: Path) -> tuple[str | None, str | None]:
    sessions_dir = project_dir / "sessions"
    if not sessions_dir.is_dir():
        return None, None
    files = sorted(
        p for p in sessions_dir.glob("*.md") if p.name != "INDEX.md"
    )
    if not files:
        return None, None
    # The newest period is the latest name (YYYY-MM); recency is the latest write to any session file.
    mtime = datetime.fromtimestamp(max(p.stat().st_mtime for p in files), tz=timezone.utc)
    return files[-1].stem, mtime.isoformat()


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
        "name": _text(entry, "name", project_id),
        "goal": _text(entry, "description", ""),
        "status": _text(entry, "status", "unknown"),
        "updated": str(entry.get("last_session") or entry.get("updated", "") or ""),
        "newest_session": period,
        "session_mtime": mtime,
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
