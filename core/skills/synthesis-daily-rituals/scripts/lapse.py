#!/usr/bin/env python3
"""Write a lapse where it belongs, in one step: the row in the workspace's register, and the mark at the item.

    lapse.py --workspace W --as-of YYYY-MM-DD (--id DECAY-ID | --at FILE:LINE)
             --why WHY --affected WHOM --still WHAT [--outcome TEXT] [--lapsed YYYY-MM-DD] [--row-missing | --row LINE]
    lapse.py --workspace W --as-of YYYY-MM-DD (--id DECAY-ID | --at FILE:LINE) --came WHAT-CAME-OF-IT [--row LINE]

A dated item that passes its date with no decision from the principal lapsed. The day-end asked for two things by
hand, a `**Lapsed:**` mark where the item sits and an appended row in the register; an audit of 2026-11-11 found no
script that writes either, nothing that holds one to the other, and no place in a row for whom the lapse affected
or what can still be done. This takes the item, by its Decay ID or by the file and line the sweep prints for one
that has none, and the words only the agent has: why it lapsed, whom that affected, what can still be done. An
item named by its place that has a Decay ID is recorded by that ID.

It appends the row first, to the file the ritual config names (`"lapse_register": "<file>"`): under the register's
last table where that has the seven cells and ends the file, otherwise under a new header of seven. It only ever
appends there, with the register's own line ends, and reads the row back from the file before it says the row is
written. The row's Item cell is the item's title and, in code, its Decay ID: a title's own code is written there
between plain quotes, so the one code span a row of this helper holds is the ID. Its Where cell is a link that
leads to the plan from the folder the register really lies in.

Then the mark, on a line of its own under the item's `**Decays:**` tag: with that line's lead where the tag opens
its line, and as the entry's next line where the tag stands on the item's own line. Before anything is written the
item is read again in its plan by the sweep's own reader, as the plan reads at that moment: its file's last copy,
which is the one the sweep reads, still open, with the date the sweep read and no mark written since. The plan
with its mark is then written beside the plan and read by that same reader, and takes the plan's place only after
the row is written and only if the plan has not changed. One helper writes at a time (a lock in the rituals'
state folder), so two that run together neither start two tables nor write over each other's mark.

A row is never rewritten. What came of a lapse later (it was sent late, the principal let it go) is said with
`--came`: a row for the same lapse, on its day, with that outcome and the rest as the lapse's row has it. It needs
no open item, since by then the item may be closed. The register's review reads a lapse by its last row: rows of
one ID and one day, or, for an item with no ID, rows with one Item cell, one Where cell and one day. Where the rows
`--came` finds are those of more than one item (a mark moves what stands under it, so another item can lapse at a
line one lapsed at), it does not guess: `--row` and a line of the right lapse's rows says which.

Exit 2, with both files as they were: a critical item (it never lapses), an item that is closed or not found (for
an item named by its place, the refusal says where that file's items now stand, since each mark written above an
item moves it down a line), a date that has not passed, a lapse dated ahead of today or before the item's date,
words that say nothing, a gap of the sweep where a copy of the item could stand (a row is permanent, so none is
written from a reading that is not whole; a gap the sweep ties to another item, and a declared folder that holds no
file the sweep could read, do not stand in the way and are counted in what it prints), a plan that changed so that
the item is no longer as the sweep read it, a plan that holds a character some readers take for the end of a line
and an editor does not (its lines are not counted alike), a tag that stands in a table's row (a mark on a line of
its own would break the table), a mark the sweep would not read as the item's, a plan, its folder or a register
this process may not write, a register that is not named or holds no register table, an item whose row and mark
both stand, an item already marked whose row cannot be found (a row written by hand may name it in words:
`--row-missing` says there is none), and an item with no ID that the register holds a row of its title for at
another place: another line of its plan, or another plan that carries a copy of it. Which that row is, is asked
and not guessed, for an item still to be marked and for one already marked: `--row LINE` says it is this lapse's,
`--row-missing` that it is another item's; and a row whose line in this plan still holds a marked item of that
title is that item's, so `--row` naming it is refused. With `--came`: no row to say it of, rows of more than one
item and no `--row`, and a `--row` that is none of them. Exit 1: the row is written and what follows it is not, and
the message says which: the mark could not be put in place (it names the row; run this again with `--row` and that
line, and it writes the mark alone), or the row does not read back as written (look at it first). An interrupt, or
a stop the system asks for, while it runs leaves nothing beside the plan.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(Path(__file__).resolve().parent))
import decay_sweep  # noqa: E402  (it finds the synthesis runtime, or says that it cannot)
import lapse_review  # noqa: E402

rituals = decay_sweep.rituals  # the runtime the sweep found

HEADER = "| Lapsed | Item | Where it waited | Why it lapsed | Outcome | Who it affected | What can still be done |"
TAG = re.compile(r"\*\*Decays:\*\*", re.I)
LEAD = re.compile(r"^(\s*)((?:[-*+]|\d+[.)])\s+)?")  # a line's indent, and its list mark where it opens an entry
OPENS = r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)"  # what stands before an item's title on its first line
RULE = re.compile(r"^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)+\|?\s*$")  # the rule under a table's header, with its outer pipes or without
TARGET = re.compile(r"\]\(<([^>]+)>\)|\]\(([^)\s]+)\)")  # a link's target, as `link` writes it
LINKED = re.compile(r"\[[^\]]*?:(\d+)\]\(")  # the line a Where cell's link names, as `where_cell` writes it
# what Python's reader of lines takes for the end of a line and an editor does not: the sweep counts lines with it
ODD = re.compile("[\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029]|\r(?!\n)")
SHOWN = 8  # how many gaps, or places, a refusal lists before it counts the rest


class Refused(Exception):
    """Nothing is written."""


def _cell(text: str) -> str:
    """Words as one cell of a row: on one line, and no pipe of theirs ends the cell."""
    return " ".join(str(text).split()).replace("|", "\\|")


def title_of(line: str) -> str:
    """An item's title from the line it opens on, inline code and all: its list mark or heading's hashes taken off,
    and a tag on that line, which is no part of its title."""
    opening = re.sub(OPENS, "", line).strip()
    tagged = decay_sweep.FIELD.search(opening)
    return (opening[:tagged.start()] if tagged else opening).strip()


def _title(text: str) -> str:
    """An item's title as a cell's words: its code keeps its words between plain quotes. A row's ID is the last
    code span of its Item cell, so a title's own code is never written there as code (2026-11-13, a review: an item
    with no ID whose title named another item's ID in code was read as that item's lapse, which then got no row)."""
    return _cell(re.sub(r"`+", "'", text))


def link(name: str, target: str) -> str:
    """A Markdown link to a path, between angle brackets where the path holds a space or a bracket."""
    target = target.replace("|", "%7C")
    return f"[{name}](<{target}>)" if re.search(r"[\s()]", target) else f"[{name}]({target})"


def where_cell(register: Path, file, line: int) -> str:
    """The Where cell for a file and a line: a link that leads there from the folder the register lies in, both as
    they really lie (2026-11-13, a review: with the register named through a link, a row's link led nowhere and
    what came of the lapse could not find its row)."""
    real = os.path.realpath(file)
    return link(f"{Path(real).name}:{line}", os.path.relpath(real, os.path.realpath(register.parent)))


def file_of(register: Path, row: dict) -> str:
    """The file a row's Where cell leads to, as it really lies; nothing where the cell holds no link."""
    found = TARGET.search(str(row.get("where", "")))
    return os.path.realpath(os.path.join(os.path.realpath(register.parent), (found[1] or found[2]).replace("%7C", "|"))) if found else ""


def day_of(flag: str, value: str):
    try:
        return decay_sweep.iso_day(value)
    except ValueError as exc:
        raise Refused(f"{flag} {value!r} is no calendar day ({exc})") from None


def _at(at: str) -> tuple:
    file, _, line = at.rpartition(":")
    if not file or not line.isdigit():
        raise Refused(f"--at {at!r} is no FILE:LINE: give the file and line the sweep prints for the item")
    return os.path.realpath(os.path.expanduser(file)), int(line)


def find(report: dict, wanted_id: str | None, at: str | None, as_of) -> dict:
    """The open dated item asked for, whose date has passed; or a refusal that says what stands in the way."""
    moved = ""
    if wanted_id:
        named, mine = f"with the Decay ID `{wanted_id}`", lambda row: row.get("identity") == f"id:{wanted_id}"
    else:
        where, line = _at(at)
        named, mine = f"at {at}", lambda row: os.path.realpath(row["path"]) == where and row["line"] == line
        theirs = [f"{Path(row['path']).name}:{row['line']} ({row['title']})" for row in report["due"]
                  if os.path.realpath(row["path"]) == where and row["due_date"] < as_of.isoformat()]
        if theirs:  # a mark is a line: what stands under it is a line lower than the sweep printed before it
            moved = (". Each mark written above an item moves it down a line: the items of that file whose date has passed now stand at "
                     + ", ".join(theirs[:SHOWN]) + f" and {len(theirs) - SHOWN} more" * (len(theirs) > SHOWN))
    if any(mine(row) for row in report["critical"]["open"]):
        raise Refused(f"the item {named} is a critical deadline, and a critical item never lapses: it stays open until "
                      "evidence or the principal's own words close it. Ask the principal")
    row = next((row for row in report["due"] if mine(row)), None)
    if row is None or row["due_date"] >= as_of.isoformat():
        ahead = row or next((row for row in report["ahead"] if mine(row)), None)
        if ahead:
            raise Refused(f"the date of the item {named} ({ahead['due_date']}) has not passed on {as_of}: an item lapses "
                          "once its date is behind it")
        raise Refused(f"no open item {named} among this workspace's dated items: closed, never dated, or not there{moved}")
    return row


def bears(found: dict, identity: str) -> bool:
    """Whether a gap of the sweep could hide a copy of this item or change how it is read. One the sweep ties to
    another item by its Decay ID is that item's own line, and a declared folder that holds no file at all hides
    nothing; every other gap may (2026-11-13, a review: any gap stopped every lapse of the seat)."""
    return found.get("identity", identity) == identity and found.get("files") != 0


def listed(gaps: list) -> str:
    lines = [f"  {found['path'] or '(no folder declared)'}{':%d' % found['line'] if found.get('line') else ''}: {found['reason']}" for found in gaps]
    return "\n".join(lines[:SHOWN]) + f"\n  and {len(lines) - SHOWN} more" * (len(lines) > SHOWN)


def sweep_reads(path: Path, name: str, as_of) -> list:
    """One plan as the sweep reads it today: its dated items, each with whether it is closed, its date, and the day
    its newest Lapsed mark speaks of. `name` gives the day a plan's own name says, for a mark that gives none."""
    named = decay_sweep.RECORD.match(name)
    try:
        day = decay_sweep.iso_day(named[1]) if named else as_of
    except ValueError:
        day = as_of
    return decay_sweep.parse_plan(path, day, 0, as_of, {"gaps": [], "scanned": []})


def pick(entries: list, wanted_id: str | None, line: int, title: str):
    """The item among a plan's entries: by its Decay ID the file's last copy, which is the one the sweep reads; with
    no ID, the entry whose tag stands on that line under that title."""
    mine = [entry for entry in entries if (entry["identity"] == f"id:{wanted_id}" if wanted_id else
                                           entry["identity"].startswith("source:") and entry["line"] == line and entry["title"] == title)]
    return mine[-1] if mine else None


def in_table(lines: list, at: int) -> bool:
    """Whether a line stands in a table: it opens with a pipe, or it holds one and the run of such lines around it
    has a table's rule (a row need not be written with its outer pipes)."""
    if lines[at - 1].lstrip().startswith("|"):
        return True
    if "|" not in lines[at - 1]:
        return False
    low = high = at - 1
    while low > 0 and "|" in lines[low - 1]:
        low -= 1
    while high + 1 < len(lines) and "|" in lines[high + 1]:
        high += 1
    return any(RULE.match(row) for row in lines[low:high + 1])


def locate(item: dict, wanted_id: str | None, as_of) -> dict:
    """The item in its plan as the plan reads now: the line of its Decays tag, its title and the plan's lines, with
    what the file was when it was read. It is read again by the sweep's own reader and must still be what the sweep
    listed: there, open, with that date, and with no mark written since (2026-11-13, two reviews: an item written
    above it while the sweep ran, and the mark and the row went to another item; an item closed or given a later
    date in that moment still got both)."""
    plan = Path(item["path"])
    before = plan.stat()
    with open(plan, encoding="utf-8", newline="") as file:  # each line's own end is kept as it is
        text = file.read()
    entry = pick(sweep_reads(plan, plan.name, as_of), wanted_id, item["line"], item["title"])
    after = plan.stat()
    seen = (before.st_size, before.st_mtime_ns, before.st_ino)
    if seen != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise Refused(f"{plan} was being written while this read it. Nothing was written; run this again")
    if entry is None:
        raise Refused(f"{plan} changed while this ran: the item is no longer where the sweep read it. Nothing was written; run this again")
    if entry["closed"] or entry["invalid"] or entry["due_date"] != item["due_date"] or (
            item["unannounced"] and entry["lapsed_on"] >= item["due_date"]):
        raise Refused(f"{plan} changed while this ran: the item at line {entry['line']} is no longer as the sweep read it (closed, given "
                      "another date, or marked since). Nothing was written; run this again")
    odd = ODD.search(text)
    if odd:  # the third review: such a character in the tag's line put the mark in its middle and glued the rest on
        raise Refused(f"{plan} holds a character that some readers take for the end of a line and an editor does not "
                      f"({odd[0]!r}, at line {text.count(chr(10), 0, odd.start()) + 1} as an editor counts), so its lines are not counted "
                      "alike. Replace it with a space or a line's end, and run this again; nothing was written")
    lines = text.splitlines(keepends=True)
    if in_table(lines, entry["line"]):  # a mark is a line of its own, and there it would cut the table in two
        raise Refused(f"the item's Decays tag stands in a table's row ({plan}:{entry['line']}), where a mark on a line of its own would "
                      "break the table. Write the item as an entry with its tag beneath it, or mark it by hand in that row; nothing was written")
    block = next(block for block in decay_sweep.item_blocks(text, []) if any(number == entry["line"] for number, _ in block))
    first = next((number for number, line in block if line.strip()), block[0][0])
    return {"plan": plan, "seen": seen, "lines": lines, "text": text, "tag": entry["line"], "title": title_of(lines[first - 1])}


def occupant(file: str, line: int):
    """The title of the item whose Decays tag stands at that line of the file now, or None: no such item, or no file
    to read (by the time what came of a lapse is said, its item may be closed or gone)."""
    try:
        with open(file, encoding="utf-8", newline="") as handle:
            text = handle.read()
    except (OSError, UnicodeError):
        return None
    lines = text.splitlines(keepends=True)
    for block in decay_sweep.item_blocks(text, []):
        if any(number == line and number <= len(lines) and TAG.search(lines[number - 1]) for number, _ in block):
            return title_of(lines[next((number for number, raw in block if raw.strip()), block[0][0]) - 1])
    return None


def held_by(register: Path, row: dict, found: dict):
    """The line of this plan a row names, where that line still holds a marked item of the row's title other than this
    one: the row is that item's. None where the row names another file, this item's own line, or no such item."""
    named = LINKED.search(str(row.get("where", "")))
    if file_of(register, row) != os.path.realpath(found["plan"]) or not named or int(named[1]) == found["tag"]:
        return None
    line = int(named[1])
    for block in decay_sweep.item_blocks(found["text"], []):
        if any(number == line for number, _ in block):
            first = next((number for number, text in block if text.strip()), block[0][0])
            marked = any((decay_sweep.FIELD.search(text) or [None, ""])[1].lower() == "lapsed" for _, text in block)
            same = lapse_review.plain(_title(title_of(found["lines"][first - 1]))) == lapse_review.plain(row.get("item"))
            return line if marked and same else None
    return None


def append_row(register: Path, heads: list, row: str) -> int:
    """Append the row, under the last table where that is the register's seven-cell one and ends the file, else
    under a new header, in the register's own line ends; the line it was written on. Nothing already in the file is
    rewritten."""
    with open(register, encoding="utf-8", newline="") as file:
        text = file.read()
    end, lines = "\r\n" if "\r\n" in text else "\n", text.splitlines()
    last, cells = heads[-1]
    under = cells == 7 and len(lines) >= last and all(line.lstrip().startswith("|") for line in lines[last - 1:])
    added = ("" if not text or text.endswith(("\n", "\r")) else end) + ("" if under else f"{end}{HEADER}{end}{'|---' * 7}|{end}") + row + end
    with open(register, "a", encoding="utf-8", newline="") as file:
        file.write(added)
    return len((text + added).splitlines())


def read_back(rows: list, line: int, cells: list) -> bool:
    """Whether the register, read again, holds the row on that line with its day and each cell as written."""
    found = next((row for row in rows if row["line"] == line), None)
    return bool(found) and [str(found.get(name, "")).strip() for name in lapse_review.CELLS] == cells


def lead(line: str, tag: int) -> str:
    """What stands before a mark written under this tag: the tag line's own lead where the tag opens its line; where
    the tag stands on the item's own line, an entry's next line, as far in as the entry's text, and nothing under a
    heading (2026-11-13, a review: with everything before the tag as its lead, the mark was a second copy of the
    item, which took the Decay ID with it)."""
    before, opened = line[:tag], LEAD.match(line[:tag])
    return before if not before[opened.end():].strip() else opened[1] + " " * len(opened[2] or "")


def prepare(found: dict, text: str, reads) -> tuple:
    """The plan with the mark on a line of its own under the item's Decays tag, written beside the plan and not yet
    in its place: (that file, the line the mark stands on). It is read by the sweep's own reader first (`reads`
    says whether the item there carries the mark), so a mark that would stand as an entry of its own, and leave the
    item unannounced for the next run to mark again, is refused before anything is written; so is a folder that
    takes no file."""
    plan, lines, at = found["plan"], list(found["lines"]), found["tag"]
    tag = TAG.search(lines[at - 1])
    if not tag:
        raise Refused(f"{plan}:{at} holds no Decays tag as it is written. Nothing was written")
    ending = "\r\n" if lines[at - 1].endswith("\r\n") else "\n"
    if not lines[at - 1].endswith(("\n", "\r")):  # the tag ends the file with no line end: the mark then does
        lines[at - 1], ending = lines[at - 1] + "\n", ""
    lines.insert(at, lead(lines[at - 1], tag.start()) + text + ending)
    tmp = plan.with_name(f".{plan.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as file:
            file.write("".join(lines))
        shutil.copymode(plan, tmp)
        attached = reads(tmp)
    except OSError as exc:
        _gone(tmp)
        raise Refused(f"{plan.parent} may not be written by this process ({exc}), so the mark cannot be written and nothing was written") from None
    except BaseException:  # an interrupt while it is read back: nothing is left beside the plan (the third review)
        _gone(tmp)
        raise
    if not attached:
        _gone(tmp)
        raise Refused(f"a mark written under the tag at {plan}:{at} would not be read as that item's: the sweep would take it for an entry "
                      "of its own, and the item would stay unannounced. Write the item's fields on lines of their own beneath it, or mark it "
                      "by hand; nothing was written")
    return tmp, at + 1


def place(found: dict, tmp: Path) -> None:
    """Put the marked plan in the plan's place. The plan is replaced whole, so not if it changed since it was read."""
    plan = found["plan"]
    stat = plan.stat()
    if (stat.st_size, stat.st_mtime_ns, stat.st_ino) != found["seen"]:
        raise OSError(f"{plan} changed while this ran")
    os.replace(tmp, plan)


def _gone(tmp) -> None:
    try:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    except OSError:
        pass


def came(args, register: Path, rows: list) -> list:
    """The cells of the row that says what came of a lapse already in the register: the lapse's own newest row, with
    its outcome replaced. Where the rows found are those of more than one lapse, `--row` says which, by a line of its
    rows; with none, the newest lapse of one item is taken, and two items are never guessed between (the third
    review: a mark moves what stands under it, so a second item lapsed at the place a first one had, and what came of
    the first was written as the second's)."""
    if any(value is not None for value in (args.why, args.affected, args.still, args.outcome, args.lapsed)) or args.row_missing:
        raise Refused("--came takes the item alone, and --row for which of its lapses: the lapse's own row has its day, its why, whom "
                      "it affected and what could be done")
    said = _cell(args.came)
    if not said:
        raise Refused("--came says nothing: say what came of the lapse")
    if args.id:
        named, mine = f"that names `{args.id}`", [row for row in rows if lapse_review.row_id(row) == args.id]
    else:
        where = lapse_review.plain(where_cell(register, *_at(args.at)))
        named, mine = f"for {args.at}", [row for row in rows if lapse_review.plain(row.get("where")) == where]
    if not mine:
        raise Refused(f"{register} holds no row {named}: what came of a lapse is said of one the register already holds")
    if args.row is not None:
        chosen = next((row for row in mine if row["line"] == args.row), None)
        if chosen is None:
            raise Refused(f"--row {args.row}: {register}:{args.row} is no row {named}. Nothing was written")
        mine = [row for row in mine if lapse_review.lapse_key(row) == lapse_review.lapse_key(chosen)]
    else:
        last = {lapse_review.lapse_key(row): row for row in sorted(mine, key=lambda row: row["line"])}
        choices = "\n".join(f"  --row {row['line']}: {row['lapsed']} {str(row.get('item', '')).strip()}" for row in last.values())
        if len({lapse_review.plain(row.get("item")) for row in mine}) > 1:
            raise Refused(f"the rows {named} are those of more than one item (a mark moves what stands under it, so another item can lapse "
                          f"at a line one lapsed at). Say which lapse this is of, with --row and a line of its rows:\n{choices}\nNothing was written")
        holds = None if args.id else occupant(*_at(args.at))
        if holds is not None and lapse_review.plain(_title(holds)) != lapse_review.plain(mine[0].get("item")):
            raise Refused(f"{args.at} now holds another item ({_title(holds)}) than the one whose lapse is recorded for that place, which has "
                          f"moved or gone since. If what came is of that lapse, say so with --row:\n{choices}\nIf it is of the item there now, "
                          "the register holds no lapse of it to say it of. Nothing was written")
    last = max(mine, key=lambda row: (row["lapsed"], row["line"]))
    if str(last.get("outcome", "")).strip() == said:
        raise Refused(f"the row at {register}:{last['line']} already says that")
    return [last["lapsed"], *(str(last.get(name, "")).strip() for name in ("item", "where", "why")), said,
            *(str(last.get(name, "")).strip() or "—" for name in ("affected", "still"))]


def standing(args, register: Path, rows: list, item: dict, wanted: str | None, named: str, where: str, found: dict):
    """The row this lapse already has in the register, if it has one. By its Decay ID where the item has one. With
    no ID a row is this lapse's by its title, its file and its line. A row of its title at another place (another
    line of this plan: a run wrote the row and not the mark, and the item moved since; or another plan, for a copy
    of the item there) may be this lapse's or another item's, and which is not guessed, for an item still to be
    marked or one already marked: `--row` says it is this lapse's, `--row-missing` that it is another item's. A row
    whose line in this plan still holds a marked item of that title is that item's, and `--row` naming it is refused
    (2026-11-13, two reviews: a second row for one lapse; a mark left with no row on a refusal that said both stood;
    two lapses under one row; a copy in an older plan given a second row)."""
    mine = [row for row in rows if row["lapsed"] >= item["due_date"] and (
        lapse_review.row_id(row) == wanted if wanted else
        not lapse_review.row_id(row) and lapse_review.plain(row.get("item")) == lapse_review.plain(named) and file_of(register, row))]
    if args.row is not None:
        there = next((row for row in mine if row["line"] == args.row), None)
        if there is None:
            raise Refused(f"--row {args.row}: {register}:{args.row} is no row of this lapse (a row that names this item, of its date "
                          f"{item['due_date']} or later). Nothing was written")
        if not item["unannounced"]:
            raise Refused(f"--row {args.row} names the row of a lapse whose mark is still to be written, and this item is already marked. "
                          "Nothing was written")
        holder = None if wanted else held_by(register, there, found)
        if holder:
            raise Refused(f"--row {args.row}: line {holder} of {found['plan']}, which that row names, still holds an item of this title, marked "
                          "lapsed: the row is that item's. If this item's lapse has no row, run this again with --row-missing. Nothing was written")
        return there
    if wanted:
        return mine[0] if mine else None
    here = [row for row in mine if lapse_review.plain(row.get("where")) == lapse_review.plain(where)]
    if here:
        return here[-1]
    if mine and not args.row_missing:
        places = ", ".join(f"{register}:{row['line']}" for row in mine[:SHOWN])
        if item["unannounced"]:
            raise Refused(f"{register} holds a row for an item of this title, of its date or later, at another place ({places}). If that row is this "
                          "lapse's (a run wrote the row and not the mark, and the item has moved since; or the row is a copy's of this item in "
                          f"another plan), run this again with --row {mine[-1]['line']}; if it is another item's, with --row-missing. Nothing was written")
        raise Refused(f"the item is already marked Lapsed, and {register} holds a row for an item of this title at another place ({places}). If "
                      "that row is this lapse's, nothing is to be written; if it is another item's, run this again with --row-missing to write this "
                      "lapse's row. Nothing was written")
    return None


def main(argv=None) -> int:
    """A stop the system asks for (SIGTERM) is an interrupt while this runs, so what it wrote beside the plan is taken
    away on the way out (the third review: such a stop ended the process with no cleanup); the handler there before
    is put back when it ends."""
    try:
        before = signal.signal(signal.SIGTERM, signal.default_int_handler)
    except ValueError:  # not the main thread: the caller's own handling stands
        return _run(argv)
    try:
        return _run(argv)
    finally:
        signal.signal(signal.SIGTERM, before)


def _run(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--as-of", required=True, help="verified current calendar date, YYYY-MM-DD")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--id", help="the item's Decay ID")
    which.add_argument("--at", help="FILE:LINE of its Decays tag, as the sweep prints it, for an item with no ID")
    parser.add_argument("--why", help="why it lapsed")
    parser.add_argument("--affected", help="whom the lapse affected")
    parser.add_argument("--still", help="what can still be done")
    parser.add_argument("--outcome", help="what has come of it by now (default: open)")
    parser.add_argument("--lapsed", help="the day it is recorded as lapsed (default: --as-of)")
    rowed = parser.add_mutually_exclusive_group()
    rowed.add_argument("--row-missing", action="store_true", help="the register holds no row for this lapse (the item is already marked, "
                       "or a row of its title is another item's): append one")
    rowed.add_argument("--row", type=int, metavar="LINE", help="the register's line that already holds this lapse's row (from a run that "
                       "wrote the row and not the mark, or for a copy of the item in another plan): write the mark alone. With --came: "
                       "a line of the rows of the lapse it is said of")
    parser.add_argument("--came", help="what came of a lapse the register already holds: appends a row for the same lapse")
    args = parser.parse_args(argv)
    try:
        import fcntl
        rituals.state_dir().mkdir(parents=True, exist_ok=True)
        lock = open(rituals.state_dir() / "lapse.lock", "a")
        fcntl.flock(lock, fcntl.LOCK_EX)  # held until this process ends
    except (OSError, ValueError) as exc:
        print(f"lapse: the lock that keeps two lapses from being written at once cannot be taken ({exc})", file=sys.stderr)
        return 2
    there = found = item = tmp = None
    passed = 0  # gaps of the sweep that are another item's own, or a folder with no file
    try:
        as_of = day_of("--as-of", args.as_of)
        register = lapse_review.register_path(args.workspace)
        rows, heads = lapse_review.read_register(register)
        if not os.access(register, os.W_OK):
            raise Refused(f"{register} may not be written by this process, so nothing was written")
        if args.came is not None:
            cells = came(args, register, rows)
        else:
            lapsed = day_of("--lapsed", args.lapsed) if args.lapsed else as_of
            words = {name: _cell(getattr(args, name) or "") for name in ("why", "affected", "still")}
            for name, said in words.items():
                if not said:
                    raise Refused(f"--{name} says nothing: a row is for a later review to learn from, so each of the three is said")
            if lapsed > as_of:
                raise Refused(f"--lapsed {lapsed} is ahead of the day this is written ({as_of})")
            roots = decay_sweep.declared(rituals.config(), args.workspace)
            if not roots:
                raise Refused(f"{args.workspace} declares no plan folders in the ritual config, so no item of its can be found")
            report = decay_sweep.collect(roots, as_of, args.workspace)
            try:
                item = find(report, args.id, args.at, as_of)
            except Refused as exc:  # what was not read may be where it stands
                raise Refused(f"{exc}" + (f"\nThe sweep left {len(report['gaps'])} gap(s), and the item may stand in what it did not take in "
                                          f"full:\n{listed(report['gaps'])}" if report["gaps"] else "")) from None
            # a later copy that closes the item, or gives it a new date, may be in what was not read
            unread = [found for found in report["gaps"] if bears(found, item["identity"])]
            passed = len(report["gaps"]) - len(unread)
            if unread:
                raise Refused(f"the sweep left {len(unread)} gap(s) where a copy of this item could stand, so its sources were not taken in full, "
                              f"and a row is permanent: no lapse is written from a reading that is not whole:\n{listed(unread)}\n"
                              "Mend each (decay_sweep.py lists them), then run this again")
            wanted = args.id or (item["identity"][3:] if item["identity"].startswith("id:") else None)  # named by its place, recorded by its ID
            if lapsed.isoformat() < item["due_date"]:
                raise Refused(f"--lapsed {lapsed} is before its date ({item['due_date']}): an item lapses once its date is behind it")
            found = locate(item, wanted, as_of)
            plan = found["plan"]
            if not os.access(plan, os.W_OK) or not os.access(plan.parent, os.W_OK | os.X_OK):  # the mark is written beside the plan and put in its place
                raise Refused(f"{plan} may not be written by this process (the file, or the folder it is replaced in), so its mark cannot be "
                              "written and nothing was written")
            where = where_cell(register, plan, found["tag"])
            named = " ".join(filter(None, [_title(found["title"]), f"`{wanted}`" if wanted else ""]))
            there = standing(args, register, rows, item, wanted, named, where, found)
            if there and not item["unannounced"]:
                raise Refused(f"this lapse already has a row ({register}:{there['line']}) and its mark at the item: nothing is written. "
                              "What came of it since is said with --came")
            if not there and not item["unannounced"] and not args.row_missing:
                raise Refused(f"the item is already marked Lapsed, and {register} holds no row that names it"
                              + (f" by `{wanted}`" if wanted else " by its title and file")
                              + ". A row written by hand may name it in other words: if one stands there, nothing is to be written. If "
                              "none does, run this again with --row-missing")
            cells = [lapsed.isoformat(), named, where, words["why"], _cell(args.outcome or "") or "open", words["affected"], words["still"]]
            if item["unannounced"]:
                def reads(marked: Path) -> bool:
                    entry = pick(sweep_reads(marked, plan.name, as_of), wanted, found["tag"], item["title"])
                    return bool(entry) and not entry["invalid"] and entry["lapsed_on"] >= item["due_date"]
                tmp, marked_at = prepare(found, f"**Lapsed:** {lapsed} — " + " ".join(args.why.split()), reads)
    except (Refused, lapse_review.Unread, ValueError, OSError) as exc:
        _gone(tmp)
        print(f"lapse: {exc}", file=sys.stderr)
        return 2
    said = []
    try:
        if there:
            wrote = there["line"]
            said.append(f"row: already there ({register}:{wrote})")
        else:
            try:
                wrote = append_row(register, heads, f"| {' | '.join(cells)} |")
            except OSError as exc:
                print(f"lapse: {register} could not be written ({exc}): nothing was written", file=sys.stderr)
                return 2
            if not read_back(lapse_review.read_register(register)[0], wrote, cells):
                print(f"lapse: a row was appended at {register}:{wrote} and does not read back as written; look at it before "
                      "anything else is written there. The mark was not written", file=sys.stderr)
                return 1
            said.append(f"row: {register}:{wrote}")
        if item is None:
            pass  # what came of a lapse: the item's own marks are the agent's to write
        elif item["unannounced"]:
            try:
                place(found, tmp)
            except OSError as exc:
                print("\n".join(said))
                print(f"lapse: the row is written ({register}:{wrote}) and the mark is not ({exc}); run this again with --row {wrote}, and it "
                      "writes the mark alone", file=sys.stderr)
                return 1
            said.append(f"mark: {found['plan']}:{marked_at}")
        else:
            said.append("mark: already marked (a Lapsed mark for that date or a later one stands on a copy of the item)")
        if passed:
            said.append(f"note: {passed} gap(s) of the sweep did not stand in the way, each another item's own line or a declared folder "
                        "with no file (decay_sweep.py lists them)")
    finally:
        _gone(tmp)
    print("\n".join(said))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
