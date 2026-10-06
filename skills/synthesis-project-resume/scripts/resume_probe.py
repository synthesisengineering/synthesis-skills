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
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ENGINE_VERSION = "2.0.0"


def _scalar(raw: str) -> str:
    raw = raw.strip()
    quoted = re.match(r"""(["'])(.*?)\1\s*(?:#.*)?$""", raw)
    return quoted.group(2) if quoted else re.sub(r"\s+#.*$", "", raw)


def load_index(source_root: Path) -> list[dict]:
    """Each project's top-level fields from projects/index.yaml, under `projects:` or as a bare list.

    Folded (`>`) and literal (`|`) values are read; nested lists and maps are skipped.
    """
    text = (source_root / "projects" / "index.yaml").read_text(encoding="utf-8")
    bare = not re.search(r"^projects:", text, re.M)
    entries: list[dict] = []
    started, item_indent, field_indent, block = bare, None, None, None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            if block and not line.strip():
                block[2].append("")
            continue
        indent, body = len(line) - len(line.lstrip()), line.strip()
        if block and indent > block[3]:
            block[2].append(body)
            continue
        if block:
            entries[-1][block[0]] = (" " if block[1] == ">" else "\n").join(block[2]).strip()
            block = None
        if not started:
            started = body.startswith("projects:")
            continue
        if indent == 0 and not body.startswith("-") and entries:
            break  # the next top-level key
        if body.startswith("- ") and (item_indent is None or indent == item_indent):
            entries.append({})
            item_indent, field_indent, body = indent, indent + 2, body[2:]
        elif not entries or indent != field_indent:
            continue
        key, colon, value = body.partition(":")
        if colon and re.fullmatch(r"[A-Za-z_][\w-]*", key.strip()):
            if value.strip() in (">", "|", ">-", "|-"):
                block = (key.strip(), value.strip()[0], [], field_indent)
            elif value.strip():
                entries[-1][key.strip()] = _scalar(value)
    if block:
        entries[-1][block[0]] = (" " if block[1] == ">" else "\n").join(block[2]).strip()
    if not started:
        raise ValueError("projects/index.yaml must hold a project list")
    return [entry for entry in entries if entry.get("id")]


def newest_session(project_dir: Path) -> tuple[str | None, str | None]:
    sessions_dir = project_dir / "sessions"
    if not sessions_dir.is_dir():
        return None, None
    files = sorted(
        p for p in sessions_dir.glob("*.md") if p.name != "INDEX.md"
    )
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
