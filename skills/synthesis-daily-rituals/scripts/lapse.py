#!/usr/bin/env python3
"""Write a lapse where it belongs, in one step: the row in the workspace's register, and the mark at the item.

    lapse.py --workspace W --as-of YYYY-MM-DD (--id DECAY-ID | --at FILE:LINE)
             --why WHY --affected WHOM --still WHAT [--outcome TEXT] [--lapsed YYYY-MM-DD] [--row-missing]
    lapse.py --workspace W --as-of YYYY-MM-DD (--id DECAY-ID | --at FILE:LINE) --came WHAT-CAME-OF-IT

A dated item that passes its date with no decision from the principal lapsed. The day-end asked for two things by
hand, a `**Lapsed:**` mark where the item sits and an appended row in the register; an audit of 2026-11-11 found no
script that writes either, nothing that holds one to the other, and no place in a row for whom the lapse affected
or what can still be done. This takes the item, by its Decay ID or by the file and line the sweep prints for one
that has none, and the words only the agent has: why it lapsed, whom that affected, what can still be done.

It appends the row first, to the file the ritual config names (`"lapse_register": "<file>"`): under the register's
last table where that has the seven cells and ends the file, otherwise under a new header of seven. It only ever
appends there, with the register's own line ends, and reads the row back from the file before it says the row is
written. Then it writes the mark on a line of its own under the item's `**Decays:**` tag: with that line's lead
where the tag opens its line, and as the entry's next line where the tag stands on the item's own line. The item
is found again in its plan as the plan reads at that moment, so a plan that changed since the sweep read it takes
the mark where the item now sits, or is refused. One helper writes at a time (a lock in the rituals' state
folder), so two that run together neither start two tables nor write over each other's mark.

A row is never rewritten. What came of a lapse later (it was sent late, the principal let it go) is said with
`--came`: a row for the same lapse, on its day, with that outcome and the rest as the lapse's row has it. It needs
no open item, since by then the item may be closed, and the register's review reads a lapse by its last row.

Exit 2, with both files as they were: a critical item (it never lapses), an item that is closed or not found, a
date that has not passed, a lapse dated ahead of today or before the item's date, words that say nothing, a sweep
that did not take every source in full (a row is permanent, so none is written from a reading that is not whole),
a plan that changed so that the item is no longer where it was, a tag that stands in a table's row (a mark on a
line of its own would break the table), a plan or a register this process may not write, a register that is not
named or holds no register table, an item whose row and mark both stand, and an item already
marked whose row cannot be found by its ID (a row written by hand may name it in words: `--row-missing` says there
is none). Exit 1: the row is written and what follows it is not, and the message says which: the mark could not be
written (run this again, and it writes the mark alone), or the row does not read back as written (look at it first).
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
LEAD = re.compile(r"^(\s*)((?:[-*+]|\d+[.)])\s+)?")  # a line's indent, and its list mark where it opens an entry
OPENS = r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)"  # what stands before an item's title on its first line


class Refused(Exception):
    """Nothing is written."""


def _cell(text: str) -> str:
    """Words as one cell of a row: on one line, and no pipe of theirs ends the cell."""
    return " ".join(str(text).split()).replace("|", "\\|")


def link(name: str, target: str) -> str:
    """A Markdown link to a path, between angle brackets where the path holds a space or a bracket."""
    target = target.replace("|", "%7C")
    return f"[{name}](<{target}>)" if re.search(r"[\s()]", target) else f"[{name}]({target})"


def _at(at: str) -> tuple:
    file, _, line = at.rpartition(":")
    if not file or not line.isdigit():
        raise Refused(f"--at {at!r} is no FILE:LINE: give the file and line the sweep prints for the item")
    return os.path.realpath(os.path.expanduser(file)), int(line)


def find(report: dict, wanted_id: str | None, at: str | None, as_of) -> dict:
    """The open dated item asked for, whose date has passed; or a refusal that says what stands in the way."""
    if wanted_id:
        named, mine = f"with the Decay ID `{wanted_id}`", lambda row: row.get("identity") == f"id:{wanted_id}"
    else:
        where, line = _at(at)
        named, mine = f"at {at}", lambda row: os.path.realpath(row["path"]) == where and row["line"] == line
    if any(mine(row) for row in report["critical"]["open"]):
        raise Refused(f"the item {named} is a critical deadline, and a critical item never lapses: it stays open until "
                      "evidence or the principal's own words close it. Ask the principal")
    row = next((row for row in report["due"] if mine(row)), None)
    if row is None or row["due_date"] >= as_of.isoformat():
        ahead = row or next((row for row in report["ahead"] if mine(row)), None)
        if ahead:
            raise Refused(f"the date of the item {named} ({ahead['due_date']}) has not passed on {as_of}: an item lapses "
                          "once its date is behind it")
        raise Refused(f"no open item {named} among this workspace's dated items: closed, never dated, or not there")
    return row


def locate(item: dict, wanted_id: str | None) -> dict:
    """The item in its plan as the plan reads now: the line of its Decays tag, its title and the plan's lines, with
    what the file was when it was read. It is found again by what it is, its Decay ID, or for an item with none the
    title and date the sweep read at that line: the plan may have changed since the sweep read it (2026-11-13, a
    review: an item written above it while the sweep ran, and the mark and the row went to another item)."""
    plan = Path(item["path"])
    stat = plan.stat()
    with open(plan, encoding="utf-8", newline="") as file:  # each line's own end is kept as it is
        text = file.read()
    found = []
    for block in decay_sweep.item_blocks(text, []):
        fields = {}
        for number, line in block:
            match = decay_sweep.FIELD.search(line)
            if match:
                fields.setdefault(match[1].lower(), (number, match[2].strip()))
        first, opening = next(((number, line) for number, line in block if line.strip()), block[0])
        if "decays" in fields and (fields.get("decay id", (0, ""))[1] == wanted_id if wanted_id else (
                fields["decays"][0] == item["line"] and re.sub(OPENS, "", opening).strip() == item["title"]
                and fields["decays"][1].lstrip("~").startswith(item["due_date"]))):
            found.append((fields["decays"][0], first))
    if len(found) != 1:
        raise Refused(f"{plan} changed while this ran: the item is {'there more than once' if found else 'no longer where the sweep read it'}. "
                      "Nothing was written; run this again")
    lines = text.splitlines(keepends=True)
    if lines[found[0][0] - 1].lstrip().startswith("|"):  # a mark is a line of its own, and there it would cut the table in two
        raise Refused(f"the item's Decays tag stands in a table's row ({plan}:{found[0][0]}), where a mark on a line of its own would "
                      "break the table. Write the item as an entry with its tag beneath it, or mark it by hand in that row; nothing was written")
    opening = re.sub(OPENS, "", lines[found[0][1] - 1]).strip()  # as written, inline code and all
    tagged = decay_sweep.FIELD.search(opening)  # a tag on the item's own line is no part of its title
    return {"plan": plan, "seen": (stat.st_size, stat.st_mtime_ns, stat.st_ino), "lines": lines, "tag": found[0][0],
            "title": (opening[:tagged.start()] if tagged else opening).strip()}


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


def mark(found: dict, text: str) -> int:
    """Write the mark on a line of its own under the item's Decays tag; the line it stands on. The plan is replaced
    whole, so it is not written if it changed since it was read."""
    plan, lines, at = found["plan"], list(found["lines"]), found["tag"]
    stat, tag = plan.stat(), TAG.search(lines[at - 1])
    if not tag or (stat.st_size, stat.st_mtime_ns, stat.st_ino) != found["seen"]:
        raise OSError(f"{plan} changed while this ran")
    ending = "\r\n" if lines[at - 1].endswith("\r\n") else "\n"
    if not lines[at - 1].endswith(("\n", "\r")):  # the tag ends the file with no line end: the mark then does
        lines[at - 1], ending = lines[at - 1] + "\n", ""
    lines.insert(at, lead(lines[at - 1], tag.start()) + text + ending)
    tmp = plan.with_name(f".{plan.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as file:
            file.write("".join(lines))
        shutil.copymode(plan, tmp)
        os.replace(tmp, plan)
    finally:
        tmp.unlink(missing_ok=True)
    return at + 1


def came(args, register: Path, rows: list) -> list:
    """The cells of the row that says what came of a lapse already in the register: the lapse's own newest row, with
    its outcome replaced."""
    if any(value is not None for value in (args.why, args.affected, args.still, args.outcome, args.lapsed)) or args.row_missing:
        raise Refused("--came takes the item alone: the lapse's own row has its day, its why, whom it affected and what could be done")
    said = _cell(args.came)
    if not said:
        raise Refused("--came says nothing: say what came of the lapse")
    if args.id:
        named, mine = f"that names `{args.id}`", [row for row in rows if lapse_review.row_id(row) == args.id]
    else:
        file, line = _at(args.at)
        where = link(f"{Path(file).name}:{line}", os.path.relpath(file, os.path.realpath(register.parent)))
        named, mine = f"for {args.at}", [row for row in rows if row.get("where", "").strip() == where]
    if not mine:
        raise Refused(f"{register} holds no row {named}: what came of a lapse is said of one the register already holds")
    last = max(mine, key=lambda row: (row["lapsed"], row["line"]))
    if str(last.get("outcome", "")).strip() == said:
        raise Refused(f"the row at {register}:{last['line']} already says that")
    return [last["lapsed"], *(str(last.get(name, "")).strip() for name in ("item", "where", "why")), said,
            *(str(last.get(name, "")).strip() or "—" for name in ("affected", "still"))]


def main(argv=None) -> int:
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
    parser.add_argument("--row-missing", action="store_true", help="the item is already marked and the register holds no row for it: append one")
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
    there = found = item = None
    try:
        as_of = decay_sweep.iso_day(args.as_of)
        register = lapse_review.register_path(args.workspace)
        rows, heads = lapse_review.read_register(register)
        if not os.access(register, os.W_OK):
            raise Refused(f"{register} may not be written by this process, so nothing was written")
        if args.came is not None:
            cells = came(args, register, rows)
        else:
            lapsed = decay_sweep.iso_day(args.lapsed) if args.lapsed else as_of
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
            unread = {}
            for gap in report["gaps"]:
                unread.setdefault(str(gap["path"]) or "(no folder declared)", gap["reason"])
            if unread:  # a later copy that closes the item, or gives it a new date, may be in what was not read
                raise Refused(f"{len(unread)} source(s) were not taken in full by the sweep, and a row is permanent, so no lapse is "
                              "written from a reading that is not whole:\n" + "\n".join(f"  {path}: {why}" for path, why in list(unread.items())[:5])
                              + f"\n  and {len(unread) - 5} more" * (len(unread) > 5) + "\nMend each (decay_sweep.py lists them), then run this again")
            item = find(report, args.id, args.at, as_of)
            if lapsed.isoformat() < item["due_date"]:
                raise Refused(f"--lapsed {lapsed} is before its date ({item['due_date']}): an item lapses once its date is behind it")
            found = locate(item, args.id)
            plan = found["plan"]
            if not os.access(plan, os.W_OK):
                raise Refused(f"{plan} may not be written by this process, so its mark cannot be written and nothing was written")
            where = link(f"{plan.name}:{found['tag']}", os.path.relpath(plan, register.parent))
            there = next((row for row in rows if row["lapsed"] >= item["due_date"] and (
                lapse_review.row_id(row) == args.id if args.id else row.get("where", "").strip() == where)), None)
            if there and not item["unannounced"]:
                raise Refused(f"this lapse already has a row ({register}:{there['line']}) and its mark at the item: nothing is written. "
                              "What came of it since is said with --came")
            if not there and not item["unannounced"] and not args.row_missing:
                raise Refused(f"the item is already marked Lapsed, and {register} holds no row that names it"
                              + (f" by `{args.id}`" if args.id else " at that file and line")
                              + ". A row written by hand may name it in other words: if one stands there, nothing is to be written. If "
                              "none does, run this again with --row-missing")
            cells = [lapsed.isoformat(), " ".join(filter(None, [_cell(found["title"]), f"`{args.id}`" if args.id else ""])), where,
                     words["why"], _cell(args.outcome or "") or "open", words["affected"], words["still"]]
    except (Refused, lapse_review.Unread, ValueError, OSError) as exc:
        print(f"lapse: {exc}", file=sys.stderr)
        return 2
    said = []
    if there:
        said.append(f"row: already there ({register}:{there['line']})")
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
            said.append(f"mark: {found['plan']}:{mark(found, f'**Lapsed:** {lapsed} — ' + ' '.join(args.why.split()))}")
        except OSError as exc:
            print("\n".join(said))
            print(f"lapse: the row is written and the mark is not ({exc}); run this again, and it writes the mark alone", file=sys.stderr)
            return 1
    else:
        said.append("mark: already marked (a Lapsed mark for that date or a later one stands on a copy of the item)")
    print("\n".join(said))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
