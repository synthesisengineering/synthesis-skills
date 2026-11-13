#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""A test's teardown list: what a test set up, written down as each thing is made, so that ending the test means
running the list (2026-11-12: a stopped test left an entry in a client's config and a key marked for removal, with
no list to run and nothing to say so the next day).

    teardown.py add "<what was set up>" --remove "<how it is removed>" [--test "<the test it belongs to>"]
    teardown.py list
    teardown.py done <number>

`add` answers with the item's number; `done` takes one number and says what it took off. The list is
`<synthesis home>/teardown.jsonl`, and it is a log: `add` and `done` each append one line, and nothing in it is ever
written again. So a number is never given twice, and a line written into the file by hand stays as it was written:
`list` shows it, and only a hand takes it out. `synthesis doctor` warns while a thing on the list is not taken off.
Nothing here runs what `--remove` says: those are words for whoever takes the thing down. Exit 0; 1 when `done` finds
nothing still in place by that number, or when the list cannot be read or written (one line says why); 2 for words
it cannot take.
"""

import argparse
import fcntl
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def listed() -> Path:
    return Path(os.environ.get("SYNTHESIS_HOME") or Path.home() / ".synthesis" / "v5") / "teardown.jsonl"


def plain(text) -> str:
    """Words as a terminal may print them: what it would obey, or take for a line's end, is shown as a mark."""
    return "".join(ch if ch.isprintable() else "?" for ch in str(text))


def read(text: str) -> tuple:
    """(what is still in place, by number; every number ever given; the lines that are no item of the list)."""
    items, closed, other = {}, set(), []
    for line in text.split("\n"):  # a line ends at a newline only: a separator inside a hand-written line is part of it
        try:
            row = json.loads(line)
        except ValueError:
            row = None
        if isinstance(row, dict) and type(row.get("done")) is int:
            closed.add(row["done"])
        elif isinstance(row, dict) and type(row.get("id")) is int and isinstance(row.get("what"), str):
            items[row["id"]] = row
        elif line.strip():
            other.append(line)
    return {number: row for number, row in items.items() if number not in closed}, set(items), other


def said(text: str) -> str:
    if not text.strip():
        raise argparse.ArgumentTypeError("say it in words")
    return plain(" ".join(text.split()))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="teardown.py", description=__doc__.split("\n\n")[0])
    verbs = parser.add_subparsers(dest="verb", required=True)
    add = verbs.add_parser("add", help="write down a thing a test is about to set up")
    add.add_argument("what", type=said)
    add.add_argument("--remove", type=said, required=True, help="how it is removed, in words")
    add.add_argument("--test", default="", help="the test it belongs to")
    verbs.add_parser("list", help="what is still in place")
    done = verbs.add_parser("done", help="take one thing off the list, by its number, once it is gone")
    done.add_argument("number", type=int)
    args = parser.parse_args(argv)
    path, now = listed(), datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        if args.verb == "list":  # read only: it needs nothing it could write
            text = ""
            if os.path.lexists(path):
                with open(path, encoding="utf-8-sig", errors="replace") as source:
                    text = source.read()
            left, _, other = read(text)
            for number, row in sorted(left.items()):
                print(f"{number}  {plain(row.get('at', ''))[:16]}  {plain(row['what'])}  (remove: {plain(row.get('remove', 'not said'))})"
                      + (f"  [{plain(row['test'])}]" if row.get("test") else ""))
            for line in other:
                print(f"?  {plain(line)}")
            if not left and not other:
                print("nothing a test set up is left in place")
            return 0
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a+b") as log:  # appended to, never written again
            fcntl.flock(log, fcntl.LOCK_EX)  # one writer at a time: two sessions may end their tests together
            log.seek(0)
            before = log.read()
            left, given, _ = read(before.decode("utf-8-sig", "replace"))
            if args.verb == "add":
                number = max(given | {0}) + 1
                row = {"id": number, "at": now, "what": args.what, "remove": args.remove, "test": plain(" ".join(args.test.split()))}
                answer = f"{number}  {args.what}  (remove: {args.remove}); when it is gone: teardown.py done {number}"
            elif args.number not in left:
                print(f"no item {args.number} is still in place on the list: `teardown.py list` shows what is", file=sys.stderr)
                return 1
            else:
                row, answer = {"done": args.number, "at": now}, f"taken off: {args.number}  {plain(left[args.number]['what'])}"
            log.write((b"" if before[-1:] in (b"", b"\n") else b"\n") + json.dumps(row, ensure_ascii=False).encode("utf-8") + b"\n")
            log.flush()
        print(answer)  # said once it is written
    except OSError as error:
        print(f"{path}: the teardown list cannot be {'read' if args.verb == 'list' else 'written'} ({error.strerror or error}), so "
              + ("what is left in place is not known" if args.verb == "list" else "nothing was changed"), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
