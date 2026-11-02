#!/usr/bin/env python3
"""List the lessons written into project records since a date instead of into a lessons folder.

A lesson belongs in its knowledge repository's top-level `lessons/` folder, one file each, where later sessions
search for it. Sessions sometimes write one into a project record instead: a "Lessons" heading in a session log, a
**Lesson:** line in CONTEXT.md, a lessons document under resources/. On 2026-11-02 a sweep of one corpus found 165
such sections and 71 such lines with no link to a lessons file, and the principal asked for every lesson to be stored
in the usual place.

This reads each repository's `projects/` records changed since the date, committed or not, and prints every lesson
heading or label added since then whose section links to no lessons folder. Day-end moves each one into `lessons/`,
or leaves one that is not a lesson. Exit 0 always: a surface, not a gate.

Usage:
    stray_lessons.py --since 2026-10-30 --repo ~/workspaces/<W>/ai-knowledge-<W> [--repo ...] [--json]
"""
import argparse
import collections
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

HEADING = re.compile(r"^(#{1,6}) .*\blessons?\b", re.I)
LABEL = re.compile(r"^\s*(?:[-*] )?\*\*(?:[\w'-]+ )?lessons?\b[^*\n]*\*\*", re.I)  # **Lesson:**, **Key lessons:**


def _git(repo, *args):
    run = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return run.stdout if run.returncode == 0 else None


def _marker(line):
    return bool(HEADING.match(line) or LABEL.match(line))


def _section(lines, i):
    """The lines a marker covers: a heading's section, a list item's own lines, or a label's paragraph."""
    heading, item = HEADING.match(lines[i]), re.match(r"^(\s*)[-*] ", lines[i])
    end = i + 1
    while end < len(lines):
        line, level = lines[end], re.match(r"^(#{1,6}) ", lines[end])
        if heading:
            if level and len(level.group(1)) <= len(heading.group(1)):
                break
        elif not line.strip() or level or (item and re.match(rf"^\s{{0,{len(item.group(1))}}}[-*] ", line)):
            break
        end += 1
    return "\n".join(lines[i:end])


def strays(repo, since):
    """Lesson markers added under `projects/` since the date whose sections link to no lessons folder, or None."""
    repo = Path(repo).expanduser()
    if _git(repo, "rev-parse", "--git-dir") is None:
        return None
    base = (_git(repo, "rev-list", "-1", f"--before={since.isoformat()} 00:00", "HEAD") or "").strip()
    listed = _git(repo, "diff", "--name-only", "-z", base, "--", "projects") if base else ""
    listed = (listed or "") + (_git(repo, "ls-files", "-z", "--others", "--exclude-standard", "--", "projects") or "")
    if not base:
        listed += _git(repo, "ls-files", "-z", "--", "projects") or ""
    found = []
    for path in sorted({p for p in listed.split("\0") if p.endswith(".md") and (repo / p).is_file()}):
        before = (_git(repo, "show", f"{base}:{path}") or "") if base else ""
        old = collections.Counter(line for line in before.splitlines() if _marker(line))
        lines = (repo / path).read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            if not _marker(line):
                continue
            if old[line]:
                old[line] -= 1
            elif "lessons/" not in _section(lines, i):
                found.append({"repo": repo.name, "path": path, "line": i + 1, "text": line.strip()[:120]})
    return found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--since", type=date.fromisoformat, required=True, help="the last day-end's date")
    parser.add_argument("--repo", action="append", required=True, help="a knowledge repository (repeatable)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    found, unread = [], []
    for repo in args.repo:
        result = strays(repo, args.since)
        if result is None:
            unread.append(repo)
        else:
            found += result
    if args.json:
        print(json.dumps({"since": args.since.isoformat(), "strays": found, "unread": unread}, indent=2))
        return 0
    print(f"Lessons written outside a lessons folder since {args.since}: {len(found)}.")
    for stray in found:
        print(f"  {stray['repo']}/{stray['path']}:{stray['line']}  {stray['text']}")
    for repo in unread:
        print(f"  not read: {repo} (not a git repository)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
