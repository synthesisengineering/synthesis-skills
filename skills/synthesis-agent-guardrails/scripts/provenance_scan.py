#!/usr/bin/env python3
"""Find chat timestamps and quotes written into records that no source shows.

    provenance_scan.py --since YYYY-MM-DD [--sources DIR]... [PATH ...]

Records: each PATH that is a file, and the files under each PATH that is a folder (default: the
current directory), that sit in transcripts/, daily-plans/ or projects/<id>/sessions/, or are a
project's CONTEXT.md or REFERENCE.md, and changed since the date.
What a record gained since then (against its last commit before the date) is checked: every
Slack timestamp (1234567890.123456, or the p1234567890123456 permalink form) and every
attributed quote (said, wrote, replied ...: "twelve or more characters").

Sources: harness session logs changed since the date (~/.claude/projects and ~/.codex/sessions,
or each --sources DIR). Only what a tool returned or a person typed counts; an agent's own words,
its writes, and a write's echoed result never source themselves. Origin: an agent made up a chat
message by changing a real message's timestamp, and the fake landed in transcripts and context.

Prints each unsourced item as `record: kind value`, then what it read. Exit 0 when everything is
sourced, 1 when something is not, 2 when it could not run. Reads only; writes nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

RECORD = re.compile(r"(^|/)(transcripts/|daily-plans/|projects/[^/]+/sessions/|projects/[^/]+/(CONTEXT|REFERENCE)\.md$)")
STAMP = re.compile(r"\b(\d{10})\.(\d{6})\b|/p(\d{10})(\d{6})\b")
QUOTE = re.compile(r"\b(?:said|says|wrote|writes|replied|asked|told \w+|warned|noted|added)\s*[:,]?\s*"
                   r"(?:\"([^\"\n]{12,400})\"|“([^”\n]{12,400})”)", re.I)
WRITERS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "apply_patch", "write_file", "edit_file", "replace"}
RESULTS = {"tool_result", "function_call_output", "custom_tool_call_output"}
SOURCES = RESULTS | {"user_message", "input_text"}


def stamps(text: str) -> set:
    return {f"{a or c}.{b or d}" for a, b, c, d in STAMP.findall(text)}


def words(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def records(roots: list, since: float):
    """Record files under each root (a root may be one file) changed since the date."""
    for root in roots:
        walk = [(os.path.dirname(root), [], [os.path.basename(root)])] if os.path.isfile(root) else os.walk(root)
        for top, dirs, files in walk:
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
            for name in files:
                path = os.path.join(top, name)
                if RECORD.search(os.path.abspath(path).replace(os.sep, "/")) and name.endswith((".md", ".txt", ".jsonl", ".json")) and os.path.getmtime(path) >= since:
                    yield path


def before(path: str, day: str) -> str:
    """The record as it stood in its last commit before the day ("" when it did not exist)."""
    def git(*args):
        out = subprocess.run(["git", "-C", os.path.dirname(path), *args], capture_output=True, text=True)
        return out.stdout if out.returncode == 0 else ""
    rev = git("rev-list", "-1", f"--before={day} 00:00", "HEAD").strip()
    return git("show", f"{rev}:./{os.path.basename(path)}") if rev else ""


def _source_text(event, writes: set) -> str:
    """The text in one session-log event that a tool returned or a person typed."""
    out = []

    def visit(node, inside):
        if isinstance(node, dict):
            kind = node.get("type") if isinstance(node.get("type"), str) else ""
            ident = str(node.get("id") or node.get("tool_use_id") or node.get("call_id") or "")
            if kind in ("tool_use", "function_call", "custom_tool_call") and node.get("name") in WRITERS:
                writes.add(ident)
                return
            if kind in RESULTS and ident in writes:
                return  # a write's result echoes what was written
            inside = inside or kind in SOURCES or node.get("role") == "user"
            for key, value in node.items():
                if key != "toolUseResult":  # the harness's copy of a tool result, edits included
                    visit(value, inside)
        elif isinstance(node, list):
            for value in node:
                visit(value, inside)
        elif isinstance(node, str) and inside:
            out.append(node)

    visit(event, False)
    return "\n".join(out)


def sourced(needles: dict, dirs: list, since: float) -> tuple[set, int]:
    """(needle keys found in a source, logs read). Each log is searched as raw bytes, and only the
    lines that hold a needle (and the lines that record writes) are parsed."""
    import mmap
    write_line = re.compile(rb'"name":\s*"(?:' + b"|".join(re.escape(w.encode()) for w in WRITERS) + rb')"')
    found, logs = set(), 0
    for directory in dirs:
        for top, _, files in os.walk(os.path.expanduser(directory)):
            for name in files:
                path = os.path.join(top, name)
                if not name.endswith(".jsonl") or os.path.getmtime(path) < since or not os.path.getsize(path):
                    continue
                logs += 1
                with open(path, "rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
                    writes, parsed = set(), {}

                    def line_at(pos):
                        start = data.rfind(b"\n", 0, pos) + 1
                        end = data.find(b"\n", pos)
                        end = len(data) if end < 0 else end
                        if start not in parsed:
                            try:
                                parsed[start] = _source_text(json.loads(data[start:end]), writes)
                            except ValueError:
                                parsed[start] = ""
                        return parsed[start], end

                    for hit in write_line.finditer(data):
                        line_at(hit.start())
                    for key, (probes, test) in needles.items():
                        for probe in probes if key not in found else []:
                            pos = data.find(probe)
                            while pos != -1 and key not in found:
                                text, end = line_at(pos)
                                found.update([key] if test(text) else [])
                                pos = data.find(probe, end)
    return found, logs


def scan(roots: list, day: str, source_dirs: list) -> tuple[list, dict]:
    since = time.mktime(time.strptime(day, "%Y-%m-%d"))
    gained, checked = [], 0
    for path in records(roots, since):
        checked += 1
        with open(path, encoding="utf-8", errors="replace") as handle:
            now = handle.read()
        old = before(path, day)
        gained += [(path, "timestamp", s) for s in sorted(stamps(now) - stamps(old))]
        old_lines = set(old.splitlines())
        for line in (l for l in now.splitlines() if l not in old_lines):
            gained += [(path, "quote", a or b) for a, b in QUOTE.findall(line) if len(words(a or b)) >= 12]
    needles = {}
    for _, kind, value in gained:
        if kind == "timestamp":
            needles[value] = ([value.encode(), b"p" + value.replace(".", "").encode()], lambda t, v=value: v in stamps(t))
        else:
            probe = " ".join(words(value).split()[:8])
            longest = max(re.findall(r"[A-Za-z0-9]+", value), key=len)
            needles[value] = (list(dict.fromkeys(w.encode() for w in (longest, longest.lower(), longest.capitalize(), longest.upper()))),
                              lambda t, p=probe: p in words(t))
    found, logs = sourced(needles, source_dirs, since)
    missing = [(p, k, v if k == "timestamp" else f'"{v[:80]}"') for p, k, v in gained if v not in found]
    return missing, {"records": checked, "session logs": logs}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--since", required=True, help="YYYY-MM-DD: check what records gained from this day on")
    parser.add_argument("--sources", action="append", help="a session log folder; repeat for more (default: Claude Code and Codex)")
    parser.add_argument("paths", nargs="*", default=["."])
    args = parser.parse_args(argv)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.since):
        parser.error("--since takes YYYY-MM-DD")
    sources = args.sources if args.sources is not None else ["~/.claude/projects", "~/.codex/sessions"]
    sources = [s for s in sources if os.path.isdir(os.path.expanduser(s))]
    if not sources:
        print("provenance scan: no session log folder to check against; pass --sources", file=sys.stderr)
        return 2
    found, read = scan(args.paths, args.since, sources)
    for path, kind, value in found:
        print(f"{path}: {kind} {value}")
    print(f"provenance scan since {args.since}: {len(found)} unsourced; read {read['records']} records "
          f"and {read['session logs']} session logs")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
