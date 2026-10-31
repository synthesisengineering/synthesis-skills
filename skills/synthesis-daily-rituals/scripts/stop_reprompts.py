#!/usr/bin/env python3
"""Count the replies the Stop hook sent back over a window, by check, from the agent-conversation archive.

The v5 Stop hook sends a reply back once when it defers work in shortcut phrasing, quotes words no tool surfaced
this session, or names a file without a clickable link. Each send-back is a second draft the principal reads, and
a check that fires week after week names a habit to fix where it starts: the skill, instruction or phrasing that
produces it, not the reply. The weekly review reads this count (the principal's ask, 2026-10-30).

A send-back is found in the archive `synthesis sessions` keeps: Claude Code records it as a "Stop hook feedback"
line and as a blocking-error record with the same time, so the two count once. Exit 0 always: a surface, not a gate.

Usage:
    stop_reprompts.py                                   # the last 7 days, every workspace
    stop_reprompts.py --workspace rajiv --since 2026-10-24 --until 2026-10-30 [--json]
"""
import argparse
import collections
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

MARK = "Before this reply goes out, revise it: "
CHECKS = {  # the Stop hook's own labels (synthesis/reply_check.py), and the short names this report uses
    "lazy-shortcut phrasing": "shortcut phrasing",
    "quotes not found in this session's record": "unsourced quotes",
    "files named without a clickable link": "file links",
}
HARNESSES = ("claude-code", "codex", "muse")


def archive_root() -> Path:
    return Path(os.environ.get("SYNTHESIS_HOME") or Path.home() / ".synthesis" / "v5").expanduser() / "sessions"


def _reported(value):
    """The hook's own words inside its JSON report of a blocking error."""
    if isinstance(value, dict):
        return next((found for found in map(_reported, value.values()) if found), None)
    return value if isinstance(value, str) and MARK in value else None


def send_backs(root: Path, since: date, until: date, workspaces: list) -> dict:
    """{(workspace, session folder, time): the problems the hook named} for each send-back in the window. A session
    is filed under the month it started, so a file is skipped by its last write, never by its folder's month."""
    found, start = {}, datetime.combine(since, datetime.min.time()).timestamp()
    for path in sorted(root.glob("*/*/*/transcript-*.jsonl")):
        workspace, folder = path.parts[-4], path.parts[-2]
        if (workspaces and workspace not in workspaces) or path.stat().st_mtime < start:
            continue
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if MARK not in line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                when, text = str(record.get("at") or ""), str(record.get("text") or "")
                if record.get("kind") != "system" or MARK not in text or not since.isoformat() <= when[:10] <= until.isoformat():
                    continue
                if record.get("source") == "hook_blocking_error":  # the same words inside the hook's JSON report
                    try:
                        text = _reported(json.loads(text)) or ""
                    except ValueError:
                        continue
                if MARK in text:
                    found.setdefault((workspace, folder, when), text.split(MARK, 1)[1])
    return found


def report(found: dict, since: date, until: date) -> dict:
    checks, harnesses, named = collections.Counter(), collections.Counter(), collections.Counter()
    for (_, folder, _), problems in found.items():
        harnesses[next((h for h in HARNESSES if folder.startswith(h + "-")), "other")] += 1
        for label, short in CHECKS.items():
            if label in problems:
                checks[short] += 1
                if short != "unsourced quotes":  # the phrase or file itself recurs; a quote rarely does
                    listed = problems.split(label + ": ", 1)[1].split(". ", 1)[0] if label + ": " in problems else ""
                    items = (item.strip(' "') for item in re.split(r",\s*", listed))
                    named.update(short + ": " + item for item in items if item)
    return {"since": since.isoformat(), "until": until.isoformat(), "replies": len(found),
            "sessions": len({(w, f) for w, f, _ in found}), "checks": dict(checks.most_common()),
            "harnesses": dict(harnesses.most_common()), "most_named": [[k, n] for k, n in named.most_common(5) if n > 1]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--since", type=date.fromisoformat, help="first day (default: 6 days before --until)")
    parser.add_argument("--until", type=date.fromisoformat, default=date.today(), help="last day (default: today)")
    parser.add_argument("--workspace", action="append", default=[], help="only this workspace (repeatable)")
    parser.add_argument("--archive", type=Path, default=None, help="the sessions archive (default: ~/.synthesis/v5/sessions)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    since = args.since or args.until - timedelta(days=6)
    root = args.archive or archive_root()
    if not root.is_dir():
        print(f"Stop-hook send-backs: no archive at {root}; run `synthesis sessions export` first.")
        return 0
    result = report(send_backs(root, since, args.until, args.workspace), since, args.until)
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    print(f"Stop-hook send-backs, {result['since']} to {result['until']}: {result['replies']} replies in "
          f"{result['sessions']} sessions.")
    if result["replies"]:
        print("  " + " · ".join(f"{k} {n}" for k, n in result["checks"].items()))
        print("  by harness: " + ", ".join(f"{k} {n}" for k, n in result["harnesses"].items()))
        for item, count in result["most_named"]:
            print(f"  repeated: {item} ({count})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
