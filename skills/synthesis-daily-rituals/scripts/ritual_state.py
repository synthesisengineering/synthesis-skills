#!/usr/bin/env python3
"""Record and query daily-ritual state: one append-only log, every view per workspace.

There is no mutable state file. On 2026-09-02 one seat's close overwrote
another's single `last_day_end` slot; a lock would not have helped, because the
second writer still replaces the slot. So records are appended and every view
is derived. Each record carries two clocks: `date`, the logical workday opened
or closed (required, never inferred: a close written at 01:30 belongs to the
day before), and `ts`, when it was written. On 2026-09-14 an unscoped weekly
review query let one workspace's Friday review silence every other workspace,
so every view answers for one workspace, and an empty `--workspace ""` (an
unset shell variable) is refused rather than read as "all workspaces".

    ritual_state.py record --direction day-end --workspace W --date YYYY-MM-DD \\
        [--mode quick] [--outcome clean] [--session ID] [--pointer FILE] [--count sent=3]
    ritual_state.py query summary|last|open|streak|weekly-review [--workspace W] [--json]

The log is `<synthesis home>/rituals/history.jsonl` (`RITUAL_STATE_DIR` or
`--state-dir` points elsewhere, to exercise a copy). Derivations live in the
plugin's `synthesis/rituals.py`, which the SessionStart line and the nudge share.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

_PLUGIN = Path(__file__).resolve().parents[3]
for _root in (_PLUGIN, Path(os.environ.get("SYNTHESIS_HOME") or Path.home() / ".synthesis" / "v5") / "current"):
    if (_root / "synthesis" / "rituals.py").is_file():
        sys.path.insert(0, str(_root))
        break
from synthesis import rituals  # noqa: E402

MAX_RECORD_BYTES = 2048  # structured data only; the narrative belongs in the session log
DIRECTIONS = ("day-start", "day-end", "weekly-review")
OUTCOMES = ("clean", "complete", "completed", "success", "partial", "failed", "skipped", "blocked", "degraded")
VIEWS = ("summary", "last", "open", "streak", "weekly-review")


def refuse(message: str) -> None:
    raise SystemExit(f"ritual_state: {message}")


def check_workspace(value: str | None, form: str) -> None:
    if value is not None and not value.strip():
        refuse(f"--workspace {value!r} is empty, the shape an unset shell variable produces; it is "
               f"neither a workspace nor an omission, so it is refused. Accepted form: {form}")


def append(record: dict) -> None:
    """Append one bounded line under an exclusive lock; refuse an unsafe or interrupted log."""
    line = (json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    if len(line) > MAX_RECORD_BYTES:
        refuse(f"record is {len(line)} bytes, over {MAX_RECORD_BYTES}; put prose in the session log "
               "and point to it with --pointer")
    path = rituals.state_dir() / "history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        size = os.fstat(fd).st_size
        if size and os.pread(fd, 1, size - 1) != b"\n":
            refuse(f"{path} ends in an interrupted line; it is left as found for you to reconcile")
        written = os.write(fd, line)
        os.fsync(fd)
        if written != len(line) or os.pread(fd, len(line), size) != line:
            refuse(f"the append to {path} did not read back whole; inspect the tail before retrying")
    finally:
        os.close(fd)


def cmd_record(args) -> int:
    check_workspace(args.workspace, "record --direction <direction> --workspace <workspace> --date YYYY-MM-DD")
    try:
        date.fromisoformat(args.date)
    except ValueError:
        refuse(f"--date {args.date!r} is not YYYY-MM-DD; the logical workday is required and never inferred")
    if args.mode == "migration":
        refuse("mode 'migration' marks old bookkeeping and cannot be written")
    record = {"ts": datetime.now().astimezone().isoformat(timespec="seconds"), "date": args.date,
              "direction": args.direction, "workspace": args.workspace, "mode": args.mode,
              "outcome": args.outcome}
    record.update({k: v for k, v in (("session", args.session), ("pointer", args.pointer),
                                     ("note", args.note)) if v})
    counts = {}
    for pair in args.count or []:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            refuse(f"--count expects key=value, got {pair!r}")
        counts[key] = int(value) if value.lstrip("-").isdigit() else value
    if counts:
        record["counts"] = counts
    append(record)
    print(f"recorded {args.direction} {args.workspace} {args.date} ({args.outcome})")
    return 0


def row(records: list[dict], cfg: dict, workspace: str, today: date) -> dict:
    end, start = rituals.last(records, workspace), rituals.last(records, workspace, "day-start")
    review = rituals.last(records, workspace, "weekly-review")
    return {"last_day_end": {k: end[k] for k in ("date", "mode", "outcome") if k in end} if end else None,
            "last_day_start": {k: start[k] for k in ("date", "mode") if k in start} if start else None,
            "streak": rituals.streak(records, cfg, workspace, today),
            "last_weekly_review": review["date"] if review else None,
            "weekly_review_owed": rituals.weekly_owed(records, workspace, today)}


def cmd_query(args) -> int:
    check_workspace(args.workspace, f"query {args.view} --workspace <workspace>")
    records, bad = rituals.read()
    try:
        cfg = rituals.config()
    except ValueError as exc:
        refuse(f"{exc}; refusing to guess")
    today = date.fromisoformat(args.today) if args.today else date.today()
    named = sorted({r["workspace"] for r in records if r.get("workspace") not in (None, "", "unknown")})
    workspace, inferred = args.workspace, False
    if args.view in ("streak", "weekly-review") and not workspace:
        if args.view == "streak" or len(named) != 1:
            refuse(f"query {args.view} needs --workspace: the log holds records for {len(named)} workspaces "
                   f"({', '.join(named) or 'none'}), so none can be assumed, and one workspace must not answer "
                   f"for another. Accepted form: query {args.view} --workspace <workspace>")
        workspace, inferred = named[0], True
    if args.view == "streak":
        out: dict = {"workspace": workspace, "streak": rituals.streak(records, cfg, workspace, today)}
    elif args.view == "weekly-review":
        review = rituals.last(records, workspace, "weekly-review")
        out = {"workspace": workspace, "last_weekly_review": review["date"] if review else None,
               "owed": rituals.weekly_owed(records, workspace, today)}
        out.update({"workspace_inferred": True} if inferred else {})
    else:
        out = {}
        if args.view in ("summary", "last"):
            out["workspaces"] = {w: row(records, cfg, w, today) for w in ([workspace] if workspace else named)}
        if args.view in ("summary", "open"):
            out["open_workdays"] = [{"workspace": w, "date": d}
                                    for w, d in rituals.open_days(records, today, workspace)]
    unnamed = sum(1 for r in records if r.get("workspace") in (None, "", "unknown"))
    out.update({k: v for k, v in (("records_without_workspace", unnamed), ("malformed_lines", bad)) if v})
    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0
    for name, view in (out.get("workspaces") or {}).items():
        end = view["last_day_end"]
        print(f"  {name:14} close {end['date'] if end else '—':10}  streak "
              f"{'n/a' if view['streak'] is None else view['streak']:<4}  weekly "
              f"{view['last_weekly_review'] or '—'}{'  OWED' if view['weekly_review_owed'] else ''}")
    for item in out.get("open_workdays", []):
        print(f"  OPEN  {item['workspace']:14} {item['date']} (started, never closed)")
    if "last_weekly_review" in out:
        print(f"  last weekly review ({workspace}): {out['last_weekly_review'] or '—'}"
              f"{'  OWED' if out['owed'] else ''}{'  (the only workspace in the log)' if inferred else ''}")
    if "streak" in out:
        print(f"  streak ({workspace}): {'n/a' if out['streak'] is None else out['streak']}")
    if unnamed:
        print(f"  {unnamed} record(s) name no workspace (written before records were stamped); "
              "every view leaves them out")
    if bad:
        print(f"  {bad} malformed line(s) in the log")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state-dir", help="read and write another log directory")
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("record", help="append one ritual record")
    rec.add_argument("--direction", required=True, choices=DIRECTIONS)
    rec.add_argument("--workspace", required=True)
    rec.add_argument("--date", required=True, help="the logical workday, YYYY-MM-DD")
    rec.add_argument("--mode", default="full")
    rec.add_argument("--outcome", default="clean", choices=OUTCOMES)
    rec.add_argument("--session")
    rec.add_argument("--pointer", help="the session log that holds the narrative")
    rec.add_argument("--note")
    rec.add_argument("--count", action="append", metavar="KEY=VALUE")
    rec.set_defaults(fn=cmd_record)
    query = sub.add_parser("query", help="derive a view")
    query.add_argument("view", choices=VIEWS)
    query.add_argument("--workspace")
    query.add_argument("--today", help="YYYY-MM-DD, to ask about another day")
    query.add_argument("--json", action="store_true")
    query.set_defaults(fn=cmd_query)
    args = parser.parse_args(argv)
    if args.state_dir:
        os.environ["RITUAL_STATE_DIR"] = args.state_dir
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
