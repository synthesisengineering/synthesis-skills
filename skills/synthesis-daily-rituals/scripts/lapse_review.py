#!/usr/bin/env python3
"""Read a workspace's lapse register for a review: the rows of a window, and what repeats among them.

    lapse_review.py --workspace W --as-of YYYY-MM-DD [--window week|quarter|half|year | --since D [--until D]] [--json]

Each workspace keeps a register of what slipped, one appended row for each item that passed its date with no
decision. The Friday review reads its last fourteen days and the quarterly, six-month and annual reviews their
whole window; until 2026-11-13 no script read it. This prints a review's section from the register: how many
lapses the window holds, what repeats among them (the same item more than once, by the ID its row carries, the
last code span of its Item cell; the weekday a lapse was recorded on, or a place it waited at, three times or
more; how many outcomes are still open), then each lapse's row, newest first, as the register has it. Why a thing
repeats and what to change is the review's to say.

A row is never rewritten, so what came of a lapse later is a later row for the same item on the same day: rows
that carry one ID and one day are one lapse, and its last row is the one read.

The register is the file the ritual config names for the workspace (`"lapse_register": "<file>"`), read from its
tables whose header opens with `Lapsed`: the five-cell form, and the seven-cell form that also says whom a lapse
affected and what can still be done. It writes nothing. A register it cannot read is said, with exit 2, and never
read as empty; a row of the register whose first cell gives no day is said by its line, and never passed over
without a word.
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

rituals = decay_sweep.rituals  # the runtime the sweep found

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


def read_register(path: Path, unread: list | None = None) -> tuple[list[dict], list[tuple[int, int]]]:
    """(every dated row of the register, each of its headers as (its line, its cells)). A table is the register's
    where its header's first cell opens with the word `Lapsed` (`Lapsed`, `Lapsed on`, `Lapsed (day)`, in emphasis
    or not). A row is a line that opens with a pipe and a day (written plainly, in emphasis, in code or as a link's
    text), in such a table, or in a run of table lines with no header of its own beneath one whose first line opens
    with a day: a register is appended to, and rows written beneath the notes under its table are still its rows
    (2026-11-13: read by its first table alone, a real register gave 14 of its 64). In such a run each line of five
    cells or more is a row, whatever the run's first line holds; a line of fewer is too short to be one, and is not
    passed over in silence: its line goes into `unread` (the second review: a run whose first line had four cells was
    passed over whole, its later rows of seven cells included). A run whose first line does not open with a day is
    another table, and is passed over. A line of the register's own table whose first cell gives no day is no row
    and is not passed over in silence either: its line goes into `unread`; a row of four cells there is a row."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise Unread(f"{path} cannot be read ({exc})") from None
    rows, heads, run = [], [], None  # run: "table" under the register's header, "beneath" it with no header, "" another table's
    for number, line in enumerate(lines, 1):
        if not line.lstrip().startswith("|"):
            run = None
            continue
        cells = decay_sweep._cells(line)
        first = re.sub(r"[*_`]", "", re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cells[0])).strip()  # a day in bold, in code or as a link's text
        day, opens = re.match(decay_sweep.DATE, first), run is None
        if opens:  # the run's first line: the register's header, a row beneath the register, or another table's line
            head = bool(re.match(r"(?i)lapsed\b", first))
            run = "table" if head else "beneath" if day and heads else ""
            heads += [(number, len(cells))] if head else []
            if head:
                continue
        if not run or all(re.fullmatch(r":?-*:?", cell) for cell in cells):  # another table's line, or the rule under a header
            continue
        if run == "beneath" and len(cells) < 5:  # under no header, too short to be a row: said by its line, never passed over
            if unread is not None:
                unread.append(number)
            continue
        try:
            rows.append({**dict(zip(CELLS, [decay_sweep.iso_day(day[0]).isoformat(), *cells[1:]])), "line": number})
        except (ValueError, TypeError):  # no day, or one that is on no calendar
            if unread is not None:
                unread.append(number)
    if not heads:
        raise Unread(f"{path} holds no register table: none of its tables has a header that opens with `Lapsed`")
    return rows, heads


def row_id(row: dict) -> str:
    """The Decay ID a row carries: the last code span of its Item cell (a title may hold code of its own before it)."""
    spans = re.findall(r"`([^`]+)`", str(row.get("item", "")))
    return spans[-1] if spans else ""


def lapses(rows: list[dict]) -> list[dict]:
    """One row for each lapse: rows that carry one ID and one day are the lapse and what came of it since, and the
    last of them written is read. Rows with no ID are one lapse where their Item cell, their Where cell and their
    day are the same, which is how what came of such a lapse is written (2026-11-13, a review: each was a lapse of
    its own, so one lapse and two rows of what came of it read as three)."""
    last = {}
    for row in sorted(rows, key=lambda row: row["line"]):
        named = row_id(row)
        last[(named, row["lapsed"]) if named else ("", str(row.get("item", "")).strip(), str(row.get("where", "")).strip(), row["lapsed"])] = row
    return list(last.values())


def place(where: str) -> str:
    """The folder a row's locator names: of a link's target (between angle brackets where it holds a space), a code
    span or a bare path, whichever stands first; a folder named for a year, a month or a day (`2026-11-13`, `2026-11`,
    or in digits alone, `2026`, `11`, `13`) is passed over for the one it stands in, which says what kind of record it
    was (the second review: `plans/2026/11/2026-11-13.md` gave `11`)."""
    found = re.search(r"\]\(<([^>]+)>\)|\]\(([^)\s]+)\)|`([^`]+)`|((?:[\w.~-]+/)+[\w.-]+)", where)
    path = re.sub(r":\d+$", "", next((part for part in found.groups() if part), "")) if found else ""
    folders = [part for part in Path(path).parts[:-1] if part not in ("..", ".", "/") and not re.fullmatch(r"\d{4}(?:-\d{2}){0,2}|\d{1,2}", part)]
    return folders[-1] if folders else ""


def patterns(rows: list[dict]) -> dict:
    items = Counter(row_id(row) for row in rows if row_id(row))
    days = Counter(date.fromisoformat(row["lapsed"]).strftime("%A") for row in rows)
    places = Counter(name for row in rows for name in [place(row.get("where", ""))] if name)
    return {"item": {k: n for k, n in items.most_common() if n > 1}, "weekday": {k: n for k, n in days.most_common() if n >= REPEATS},
            "place": {k: n for k, n in places.most_common() if n >= REPEATS},
            "open": sum(bool(OPEN.match(row.get("outcome", ""))) for row in rows)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--as-of", required=True, help="verified current calendar date, YYYY-MM-DD")
    parser.add_argument("--window", choices=sorted(WINDOWS), help="week, the default, is the last fourteen days")
    parser.add_argument("--since", help="the window's first day, in place of --window")
    parser.add_argument("--until", help="the window's last day (default: --as-of)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    unread: list = []
    try:
        if args.window and args.since:
            raise Unread("--window and --since both say where the window starts: give one of them")
        days = {}
        for flag in ("as_of", "since", "until"):
            try:
                days[flag] = decay_sweep.iso_day(getattr(args, flag)) if getattr(args, flag) else None
            except ValueError as exc:
                raise Unread(f"--{flag.replace('_', '-')} {getattr(args, flag)!r} is no calendar day ({exc})") from None
        as_of, until = days["as_of"], days["until"] or days["as_of"]
        since = days["since"] or until - timedelta(days=WINDOWS[args.window or "week"] - 1)
        if until < since:
            raise Unread(f"the window ends ({until}) before it starts ({since})")
        path = register_path(args.workspace)
        rows, _ = read_register(path, unread)
    except (Unread, ValueError) as exc:
        print(f"lapse_review: {exc}", file=sys.stderr)
        return 2
    inside = sorted((row for row in lapses(rows) if since.isoformat() <= row["lapsed"] <= until.isoformat()),
                    key=lambda row: (row["lapsed"], row["line"]), reverse=True)
    found = patterns(inside)
    if args.json:
        print(json.dumps({"register": str(path), "since": since.isoformat(), "until": until.isoformat(), "total": len(rows),
                          "unread": unread, "rows": inside, "patterns": found}, indent=2))
        return 0
    print(f"Slipped through: {len(inside)} lapse{'s' * (len(inside) != 1)} from {since} to {until} "
          f"({len(rows)} row{'s' * (len(rows) != 1)} in the register)")
    if unread:
        print(f"{len(unread)} row(s) of the register could not be read, each giving no day in its first cell or, beneath the "
              f"register's table under no header of its own, holding fewer than five cells: lines {', '.join(map(str, unread))}")
    if not inside:
        return 0
    said = ([f"  the same item more than once: {', '.join(f'`{k}` ({n})' for k, n in found['item'].items())}"] if found["item"] else []) + (
        [f"  the weekday it was recorded on: {', '.join(f'{k} ({n})' for k, n in found['weekday'].items())}"] if found["weekday"] else []) + (
        [f"  where it waited: {', '.join(f'{k} ({n})' for k, n in found['place'].items())}"] if found["place"] else []) + (
        [f"  outcome still open: {found['open']} of {len(inside)}"] if found["open"] else [])
    print("\n".join(["Patterns:", *said] if said else ["Patterns: none repeats"]))
    print("Rows, newest first:")
    lines = path.read_text(encoding="utf-8").splitlines()
    print("\n".join(f"  {lines[row['line'] - 1].strip()}" for row in inside))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
