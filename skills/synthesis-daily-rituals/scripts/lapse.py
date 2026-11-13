#!/usr/bin/env python3
"""Write a lapse where it belongs, in one step: the row in the workspace's register, and the mark at the item.

    lapse.py --workspace W --as-of YYYY-MM-DD (--id DECAY-ID | --at FILE:LINE)
             --why WHY --affected WHOM --still WHAT [--outcome TEXT] [--lapsed YYYY-MM-DD]

A dated item that passes its date with no decision from the principal lapsed. The day-end asked for two things by
hand, a `**Lapsed:**` mark where the item sits and an appended row in the register; an audit of 2026-11-11 found no
script that writes either, nothing that holds one to the other, and no place in a row for whom the lapse affected
or what can still be done. This takes the item, by its Decay ID or by the file and line the sweep prints for one
that has none, and the words only the agent has: why it lapsed, whom that affected, what can still be done.

It appends the row first, to the file the ritual config names (`"lapse_register": "<file>"`): under the register's
last table where that has the seven cells and ends the file, otherwise under a new header of seven. It only ever
appends there, and reads the row back from the file before it says the row is written. Then it writes the mark on
the line after the item's `**Decays:**` tag. A mark that already stands for that date is left as it is, and a row
already there is not written twice. One helper writes at a time (a lock in the rituals' state folder), so two
that run together neither start two tables nor write over each other's mark.

It refuses, with exit 2 and both files as they were: a critical item (it never lapses), an item that is closed or
not found, a date that has not passed, a lapse dated ahead of today or before the item's date, words that say
nothing, a register that is not named or holds no register table, and an item whose row and mark both stand.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(Path(__file__).resolve().parent))
import decay_sweep  # noqa: E402  (it finds the synthesis runtime, or says that it cannot)
import lapse_review  # noqa: E402

rituals = decay_sweep.rituals  # the runtime the sweep found

HEADER = "| Lapsed | Item | Where it waited | Why it lapsed | Outcome | Who it affected | What can still be done |"
TAG = re.compile(r"\*\*Decays:\*\*", re.I)


class Refused(Exception):
    """Nothing is written."""


def _cell(text: str) -> str:
    """Words as one cell of a row: on one line, and no pipe of theirs ends the cell."""
    return " ".join(str(text).split()).replace("|", "\\|")


def find(report: dict, wanted_id: str | None, at: str | None, as_of) -> dict:
    """The open dated item asked for, whose date has passed; or a refusal that says what stands in the way."""
    if wanted_id:
        named, mine = f"with the Decay ID `{wanted_id}`", lambda row: row.get("identity") == f"id:{wanted_id}"
    else:
        file, _, line = at.rpartition(":")
        if not file or not line.isdigit():
            raise Refused(f"--at {at!r} is no FILE:LINE: give the file and line the sweep prints for the item")
        where = os.path.realpath(os.path.expanduser(file))
        named, mine = f"at {file}:{line}", lambda row: os.path.realpath(row["path"]) == where and row["line"] == int(line)
    if any(mine(row) for row in report["critical"]["open"]):
        raise Refused(f"the item {named} is a critical deadline, and a critical item never lapses: it stays open until "
                      "evidence or the principal's own words close it. Ask the principal")
    row = next((row for row in report["due"] if mine(row)), None)
    if row is None or row["due_date"] >= as_of.isoformat():
        ahead = row or next((row for row in report["ahead"] if mine(row)), None)
        if ahead:
            raise Refused(f"the date of the item {named} ({ahead['due_date']}) has not passed on {as_of}: an item lapses "
                          "once its date is behind it")
        unread = f"; {len(report['gaps'])} thing(s) in its plans could not be read (decay_sweep.py lists each)" * bool(report["gaps"])
        raise Refused(f"no open item {named} among this workspace's dated items: closed, never dated, or not there{unread}")
    return row


def titled(row: dict) -> str:
    """The item's title as its plan writes it (the sweep's own copy has lost any inline code)."""
    text = Path(row["path"]).read_text(encoding="utf-8")
    block = next((block for block in decay_sweep.item_blocks(text, []) if any(number == row["line"] for number, _ in block)), None)
    first = next((number for number, line in block if line.strip()), row["line"]) if block else row["line"]
    return re.sub(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)", "", text.splitlines()[first - 1]).strip()


def append_row(register: Path, heads: list, row: str) -> int:
    """Append the row, under the last table where that is the register's seven-cell one and ends the file, else
    under a new header; the line it was written on. Nothing already in the file is rewritten."""
    text = register.read_text(encoding="utf-8")
    lines = text.splitlines()
    last, cells = heads[-1]
    under = cells == 7 and text.endswith("\n") and lines and all(line.lstrip().startswith("|") for line in lines[last - 1:])
    added = ("" if text.endswith("\n") or not text else "\n") + ("" if under else f"\n{HEADER}\n{'|---' * 7}|\n") + row + "\n"
    with open(register, "a", encoding="utf-8") as file:
        file.write(added)
    return len((text + added).splitlines())


def read_back(rows: list, line: int, cells: list) -> bool:
    """Whether the register, read again, holds the row on that line with its day and each cell as written."""
    found = next((row for row in rows if row["line"] == line), None)
    return bool(found) and [str(found.get(name, "")).strip() for name in lapse_review.CELLS] == cells


def mark(plan: Path, line: int, text: str, seen) -> int:
    """Write the mark on the line after the item's Decays tag, with that line's own lead; the line it stands on.
    The plan is replaced whole, so it is not written if it changed since it was read."""
    with open(plan, encoding="utf-8", newline="") as file:  # each line's own end is kept as it is
        lines = file.read().splitlines(keepends=True)
    tag = TAG.search(lines[line - 1]) if 0 < line <= len(lines) else None
    stat = plan.stat()
    if not tag or (stat.st_size, stat.st_mtime_ns, stat.st_ino) != seen:
        raise OSError(f"{plan} changed while this ran")
    ending = "\r\n" if lines[line - 1].endswith("\r\n") else "\n"
    if not lines[line - 1].endswith(("\n", "\r")):  # the tag ends the file with no line end: the mark then does
        lines[line - 1], ending = lines[line - 1] + "\n", ""
    lines.insert(line, lines[line - 1][:tag.start()] + text + ending)
    tmp = plan.with_name(f".{plan.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as file:
            file.write("".join(lines))
        shutil.copymode(plan, tmp)
        os.replace(tmp, plan)
    finally:
        tmp.unlink(missing_ok=True)
    return line + 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--as-of", required=True, help="verified current calendar date, YYYY-MM-DD")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--id", help="the item's Decay ID")
    which.add_argument("--at", help="FILE:LINE of its Decays tag, as the sweep prints it, for an item with no ID")
    parser.add_argument("--why", required=True, help="why it lapsed")
    parser.add_argument("--affected", required=True, help="whom the lapse affected")
    parser.add_argument("--still", required=True, help="what can still be done")
    parser.add_argument("--outcome", default="open", help="what came of it (default: open)")
    parser.add_argument("--lapsed", help="the day it is recorded as lapsed (default: --as-of)")
    args = parser.parse_args(argv)
    try:
        import fcntl
        rituals.state_dir().mkdir(parents=True, exist_ok=True)
        lock = open(rituals.state_dir() / "lapse.lock", "a")
        fcntl.flock(lock, fcntl.LOCK_EX)  # held until this process ends
    except (OSError, ValueError) as exc:
        print(f"lapse: the lock that keeps two lapses from being written at once cannot be taken ({exc})", file=sys.stderr)
        return 2
    try:
        as_of = decay_sweep.iso_day(args.as_of)
        lapsed = decay_sweep.iso_day(args.lapsed) if args.lapsed else as_of
        words = {name: _cell(getattr(args, name)) for name in ("why", "affected", "still")}
        for name, said in words.items():
            if not said:
                raise Refused(f"--{name} says nothing: a row is for a later review to learn from, so each of the three is said")
        if lapsed > as_of:
            raise Refused(f"--lapsed {lapsed} is ahead of the day this is written ({as_of})")
        register = lapse_review.register_path(args.workspace)
        rows, heads = lapse_review.read_register(register)
        roots = decay_sweep.declared(rituals.config(), args.workspace)
        if not roots:
            raise Refused(f"{args.workspace} declares no plan folders in the ritual config, so no item of its can be found")
        item = find(decay_sweep.collect(roots, as_of, args.workspace), args.id, args.at, as_of)
        if lapsed.isoformat() < item["due_date"]:
            raise Refused(f"--lapsed {lapsed} is before its date ({item['due_date']}): an item lapses once its date is behind it")
        plan = Path(item["path"])
        stat = plan.stat()
        where = f"[{plan.name}:{item['line']}]({_cell(os.path.relpath(plan, register.parent))})"
        code = f"`{args.id}`" if args.id else ""
        there = next((row for row in rows if row["lapsed"] >= item["due_date"] and (
            code in row.get("item", "") if code else row.get("where", "").strip() == where)), None)
        if there and not item["unannounced"]:
            raise Refused(f"this lapse already has a row ({register}:{there['line']}) and its mark at the item: nothing is written")
    except (Refused, lapse_review.Unread, ValueError, OSError) as exc:
        print(f"lapse: {exc}", file=sys.stderr)
        return 2
    said = []
    if there:
        said.append(f"row: already there ({register}:{there['line']})")
    else:
        cells = [lapsed.isoformat(), " ".join(filter(None, [_cell(titled(item)), code])), where, words["why"],
                 _cell(args.outcome) or "open", words["affected"], words["still"]]
        wrote = append_row(register, heads, f"| {' | '.join(cells)} |")
        if not read_back(lapse_review.read_register(register)[0], wrote, cells):
            print(f"lapse: a row was appended at {register}:{wrote} and does not read back as written; look at it before "
                  "anything else is written there. The mark was not written", file=sys.stderr)
            return 1
        said.append(f"row: {register}:{wrote}")
    if item["unannounced"]:
        try:
            wrote = mark(plan, item["line"], f"**Lapsed:** {lapsed} — {' '.join(args.why.split())}", (stat.st_size, stat.st_mtime_ns, stat.st_ino))
        except OSError as exc:
            print("\n".join(said), file=sys.stdout)
            print(f"lapse: the mark was not written ({exc}); run this again and it writes the mark alone", file=sys.stderr)
            return 1
        said.append(f"mark: {plan}:{wrote}")
    else:
        said.append("mark: already marked (a Lapsed mark for that date or a later one stands on a copy of the item)")
    print("\n".join(said))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
