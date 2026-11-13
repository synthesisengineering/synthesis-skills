#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""A test's teardown list: what a test set up, written down as each thing is made, so that ending the test means
running the list (2026-11-12: a stopped test left an entry in a client's config and a key marked for removal, with
no list to run and nothing to say so the next day).

    teardown.py add "<what was set up>" --remove "<how it is removed>" [--test "<the test it belongs to>"]
    teardown.py list
    teardown.py done <number>

`add` answers with the item's number; `done` takes one number and says what it took off. The list is
`<synthesis home>/teardown.jsonl`, and `synthesis doctor` warns while a line of it remains. Nothing here runs what
`--remove` says: those are words for whoever takes the thing down. A line written into the file by hand is kept and
shown. Exit 0, or 1 when `done` finds no item by that number, or 2 for words it cannot take.
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


def read(path: Path) -> list:
    """Each line of the list: an item (a dict with its number), or the line itself where it is no item."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines() if path.is_file() else ():
        try:
            row = json.loads(line)
        except ValueError:
            row = None
        rows.append(row if isinstance(row, dict) and isinstance(row.get("id"), int) else line)
    return [row for row in rows if row != ""]


def said(text: str) -> str:
    if not text.strip():
        raise argparse.ArgumentTypeError("say it in words")
    return " ".join(text.split())


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
    path = listed()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(".lock"), "w") as lock:  # one writer at a time: two sessions may end their tests together
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows = read(path)
        if args.verb == "list":
            for row in rows:
                print(f"{row['id']}  {str(row.get('at', ''))[:16]}  {row.get('what')}  (remove: {row.get('remove')})"
                      + (f"  [{row['test']}]" if row.get("test") else "") if isinstance(row, dict) else f"?  {row}")
            if not rows:
                print("nothing a test set up is left in place")
            return 0
        if args.verb == "add":
            number = max([row["id"] for row in rows if isinstance(row, dict)] + [0]) + 1
            rows.append({"id": number, "at": datetime.now().astimezone().isoformat(timespec="seconds"), "what": args.what,
                         "remove": args.remove, "test": " ".join(args.test.split())})
            print(f"{number}  {args.what}  (remove: {args.remove}); when it is gone: teardown.py done {number}")
        else:
            gone = [row for row in rows if isinstance(row, dict) and row["id"] == args.number]
            if not gone:
                print(f"no item {args.number} on the list: `teardown.py list` shows what is", file=sys.stderr)
                return 1
            rows = [row for row in rows if row is not gone[0]]
            print(f"taken off: {args.number}  {gone[0].get('what')}")
        fresh = path.with_suffix(".new")
        fresh.write_text("".join((json.dumps(row, ensure_ascii=False) if isinstance(row, dict) else row) + "\n" for row in rows), encoding="utf-8")
        os.replace(fresh, path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
