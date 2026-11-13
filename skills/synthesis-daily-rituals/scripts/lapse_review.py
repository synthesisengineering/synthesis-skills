#!/usr/bin/env python3
"""Read a workspace's lapse register for a review: the rows of a window, and what repeats among them.

    lapse_review.py --workspace W --as-of YYYY-MM-DD [--window week|quarter|half|year | --since D [--until D]] [--json]

Each workspace keeps a register of what slipped, one appended row for each item that passed its date with no
decision. The Friday review reads its last fourteen days and the quarterly, six-month and annual reviews their
whole window; until 2026-11-13 no script read it. This prints a review's section from the register: how many rows
the window holds, what repeats among them (the same item more than once, by the ID its row carries; a weekday or a
place it waited at, three times or more; how many outcomes are still open), then the rows, newest first, as the
register has them. Why a thing repeats and what to change is the review's to say.

The register is the file the ritual config names for the workspace (`"lapse_register": "<file>"`), read from its
tables whose header opens with `Lapsed`: the five-cell form, and the seven-cell form that also says whom a lapse
affected and what can still be done. It writes nothing. A register it cannot read is said, with exit 2, and never
read as empty.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(Path(__file__).resolve().parent))
import decay_sweep  # noqa: E402  (it finds the synthesis runtime, or says that it cannot)
from synthesis import rituals  # noqa: E402

WINDOWS = {"week": 14, "quarter": 92, "half": 183, "year": 366}  # days, the day of the review included
CELLS = ("lapsed", "item", "where", "why", "outcome", "affected", "still")  # the register's columns, in its order
OPEN = re.compile(r"(?i)^[\W_]*(?:$|open\b|pending\b|none\b|tbd\b|not yet\b)")  # an outcome that says nothing has come of it
REPEATS = 3  # a weekday or a place is a pattern from three rows; the same item lapsing twice already is one


class Unread(Exception):
    """The register cannot be read: it is said, never taken for a register with no rows."""


def register_path(workspace: str) -> Path:
    """The file the ritual config names as this workspace's lapse register."""
    try:
        named = rituals.settings(rituals.config(), workspace).get("lapse_register")
    except (ValueError, OSError, TypeError) as exc:
        raise Unread(f"the ritual config cannot be read ({exc})") from None
    where = f'{rituals.state_dir() / "config.json"}, under workspaces.{workspace}'
    if not isinstance(named, str) or not named:
        raise Unread(f'{workspace} names no lapse register: in {where}, write "lapse_register": "<the register\'s file>"')
    path = Path(os.path.expanduser(named))
    if not path.is_absolute():
        raise Unread(f"{workspace} names its lapse register {named!r} from no fixed place: in {where}, write it from the root (`/`) "
                     "or from the home folder (`~`)")
    if not path.is_file():
        raise Unread(f"{path} is no file, so {workspace}'s lapse register cannot be read")
    return path


def read_register(path: Path) -> tuple[list[dict], list[tuple[int, int]]]:
    """(every dated row of the register, each of its headers as (its line, its cells)). A table is the register's
    where its header opens with `Lapsed`. A row is a line that opens with a pipe and a day, in such a table or in a
    run of lines with no header of its own after one: a register is appended to, and rows written beneath the notes
    under its table are still its rows (2026-11-13: read by its first table alone, a real register gave 14 of its
    64). A table with a header of its own that is not the register's is passed over."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise Unread(f"{path} cannot be read ({exc})") from None
    rows, heads, run = [], [], None  # run: whether the lines of this run of table lines are the register's
    for number, line in enumerate(lines, 1):
        if not line.lstrip().startswith("|"):
            run = None
            continue
        cells = decay_sweep._cells(line)
        day = re.match(decay_sweep.DATE, cells[0])
        if run is None:  # the run's first line: the register's header, a row that continues it, or another table's header
            head = re.sub(r"[*_`]", "", cells[0]).strip().lower() == "lapsed"
            run = head or bool(day and heads)
            heads += [(number, len(cells))] if head else []
        if run and day:
            try:
                rows.append({**dict(zip(CELLS, [decay_sweep.iso_day(day[0]).isoformat(), *cells[1:]])), "line": number})
            except ValueError:
                pass  # a first cell that only looks like a day is no row
    if not heads:
        raise Unread(f"{path} holds no register table: none of its tables has a header that opens with `Lapsed`")
    return rows, heads


def place(where: str) -> str:
    """The folder a row's locator names: of a link's target, a code span or a bare path, whichever stands first."""
    found = re.search(r"\]\(([^)\s]+)\)|`([^`]+)`|((?:[\w.~-]+/)+[\w.-]+)", where)
    path = re.sub(r":\d+$", "", next((part for part in found.groups() if part), "")) if found else ""
    return Path(path).parent.name if "/" in path else ""


def patterns(rows: list[dict]) -> dict:
    items = Counter(found[1] for row in rows for found in [re.search(r"`([^`]+)`", row.get("item", ""))] if found)
    days = Counter(date.fromisoformat(row["lapsed"]).strftime("%A") for row in rows)
    places = Counter(name for row in rows for name in [place(row.get("where", ""))] if name)
    return {"item": {k: n for k, n in items.most_common() if n > 1}, "weekday": {k: n for k, n in days.most_common() if n >= REPEATS},
            "place": {k: n for k, n in places.most_common() if n >= REPEATS},
            "open": sum(bool(OPEN.match(row.get("outcome", ""))) for row in rows)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--as-of", required=True, help="verified current calendar date, YYYY-MM-DD")
    parser.add_argument("--window", choices=sorted(WINDOWS), default="week", help="week is the last fourteen days")
    parser.add_argument("--since", help="the window's first day, in place of --window")
    parser.add_argument("--until", help="the window's last day (default: --as-of)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        as_of = decay_sweep.iso_day(args.as_of)
        until = decay_sweep.iso_day(args.until) if args.until else as_of
        since = decay_sweep.iso_day(args.since) if args.since else until - timedelta(days=WINDOWS[args.window] - 1)
        if until < since:
            raise Unread(f"the window ends ({until}) before it starts ({since})")
        path = register_path(args.workspace)
        rows, _ = read_register(path)
    except (Unread, ValueError) as exc:
        print(f"lapse_review: {exc}", file=sys.stderr)
        return 2
    inside = sorted((row for row in rows if since.isoformat() <= row["lapsed"] <= until.isoformat()),
                    key=lambda row: (row["lapsed"], row["line"]), reverse=True)
    found = patterns(inside)
    if args.json:
        print(json.dumps({"register": str(path), "since": since.isoformat(), "until": until.isoformat(), "total": len(rows),
                          "rows": inside, "patterns": found}, indent=2))
        return 0
    print(f"Slipped through: {len(inside)} rows from {since} to {until} (of {len(rows)} in the register)")
    if not inside:
        return 0
    said = ([f"  the same item more than once: {', '.join(f'`{k}` ({n})' for k, n in found['item'].items())}"] if found["item"] else []) + (
        [f"  weekday: {', '.join(f'{k} ({n})' for k, n in found['weekday'].items())}"] if found["weekday"] else []) + (
        [f"  where it waited: {', '.join(f'{k} ({n})' for k, n in found['place'].items())}"] if found["place"] else []) + (
        [f"  outcome still open: {found['open']} of {len(inside)}"] if found["open"] else [])
    print("\n".join(["Patterns:", *said] if said else ["Patterns: none repeats"]))
    print("Rows, newest first:")
    lines = path.read_text(encoding="utf-8").splitlines()
    print("\n".join(f"  {lines[row['line'] - 1].strip()}" for row in inside))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
