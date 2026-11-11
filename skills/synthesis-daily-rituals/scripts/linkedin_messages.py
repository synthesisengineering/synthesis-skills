#!/usr/bin/env python3
"""Read LinkedIn's conversation list from its saved text, and say how far back the read went.

The list shows, without opening a thread: who, the day (the clock time for today), who spoke last, the whole
last message, unread counts and LinkedIn's own "Reply?" nudge. This reads that text, lists the conversations
that end with someone else, and prints one coverage line. It opens nothing and writes nothing.

    linkedin_messages.py plan --config .agents/linkedin-sync.yaml
    linkedin_messages.py parse --text list.txt --read-at 2026-11-11T09:45:00-05:00
        [--since YYYY-MM-DD] [--opened N] [--json]

`plan` reads the workspace's declaration (`workspace`, `parking_thread`, `inboxes`) and prints the address to
open and, per inbox, the day the last read reached. The address is always the parking thread's: the bare
messaging page opens the newest conversation by itself, which marks an unread one read.

`list.txt` is the conversation list's text as the browser tool returned it (the list alone, or the whole
page). `--since` is the day the last read reached: a read whose oldest conversation is newer than that
stopped short, and its coverage carries no `through`, so the watermark cannot move. Exit 0 for a complete
read, 1 for one that stopped short or could not read an entry, 2 when the text holds no conversation list
or shows a sign-in page or security check.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # the plugin root, which holds synthesis/

END = re.compile(r"^Open the options list in your conversation with (.+)$")
CLOCK = re.compile(r"^(\d{1,2}):(\d{2})\s*([AP])M$", re.I)
DAY = re.compile(r"^([A-Z][a-z]{2})[a-z]*\.? (\d{1,2})(?:, (\d{4}))?$")
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
UNREAD = re.compile(r"^(\d+) new notifications?$")
NUDGE = re.compile(r"^Received .+ ago\. Reply\?$")
STATUS = re.compile(r"^Status is \w+$")
WALL = re.compile(r"security check|sign in|join now|captcha|unusual activity|verify (?:it'?s you|your identity)", re.I)


def stop(message: str):
    print(f"linkedin_messages: {message}", file=sys.stderr)
    raise SystemExit(2)


def when(text: str, read: datetime):
    """The day a list entry shows ("Nov 10", "Jan 3, 2025") or today's clock time ("7:00 AM"); None for anything else."""
    clock, day = CLOCK.match(text), DAY.match(text)
    if clock:
        hour = int(clock[1]) % 12 + (12 if clock[3].upper() == "P" else 0)
        return f"{read.date().isoformat()}T{hour:02d}:{clock[2]}"
    if not day or day[1].lower() not in MONTHS:
        return None
    try:
        found = date(int(day[3] or read.year), MONTHS.index(day[1].lower()) + 1, int(day[2]))
    except ValueError:
        return None
    if not day[3] and found > read.date():  # the list drops the year only for the last twelve months
        found = found.replace(year=found.year - 1)
    return found.isoformat()


def entry(block: list, names: str, read: datetime):
    """One conversation from the lines above its closing sentence, or None when they cannot be read."""
    at = next((i for i in range(1, len(block) - 1) if block[i] == block[i + 1] and when(block[i], read)), None)
    if at is None or STATUS.match(block[at - 1]):
        return None
    found = {"who": block[at - 1], "last": when(block[at], read), "from_me": False, "speaker": None, "kind": "message",
             "unread": 0, "nudge": False, "open": False}
    words = []
    for line in block[at + 2:]:
        count = UNREAD.match(line)
        if count:
            found["unread"] = int(count[1])
        elif NUDGE.match(line):
            found["nudge"] = True
        elif line == ". Active conversation":
            found["open"] = True
        elif line != ". Press return to go to conversation details" and not line.isdigit():
            words.append(line)
    found["preview"] = " ".join(words)
    if found["preview"].startswith("You:"):
        found["from_me"] = True
    elif found["preview"].startswith("InMail"):
        found["kind"] = "inmail"
    else:
        found["speaker"] = (re.match(r"([^:]{1,40}):\s", found["preview"]) or [None, None])[1]
    found["account"] = names[:-len(" and " + found["who"])] if names.endswith(" and " + found["who"]) else None
    return found


def parse(text: str, read: datetime, since: str = "", opened: int = 0) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    ends = [i for i, line in enumerate(lines) if END.match(line)]
    if not ends:
        stop("no conversation list in this text" + (": it looks like a sign-in page or a security check; stop and tell the "
                                                    "principal" if WALL.search(text) else ". Save the list's text and read again"))
    threads, unreadable, start = [], 0, 0
    for end in ends:
        found = entry(lines[start:end], END.match(lines[end])[1], read)
        if start == 0 and found:  # what sits above the first entry is the page, where a wall would show
            head = lines[:lines.index(found["who"])]
            if any(WALL.search(line) for line in head):
                stop("the page shows a sign-in or security check above the list; stop and tell the principal")
        unreadable += found is None
        threads += [found] if found else []
        start = end + 1
    accounts = {t.pop("account") for t in threads} - {None}
    oldest = min((t["last"][:10] for t in threads), default=None)
    short = bool(since and oldest and oldest > since)
    complete = bool(threads) and not unreadable and not short
    owed = [t for t in threads if not t["from_me"]]
    unread, asked = sum(t["unread"] for t in threads), sum(t["nudge"] for t in owed)
    line = (f"LinkedIn messages: {len(threads)} conversation{'s' * (len(threads) != 1)} read from the list, back to {oldest}; "
            f"{len(owed)} end with someone else ({unread} unread, LinkedIn asks for a reply on {asked}); "
            f"{opened or 'none'} opened"
            + (f"; {unreadable} could not be read" if unreadable else "")
            + (f"; the read stops short of {since}: scroll the list further and read again" if short else ""))
    return {"read_at": read.isoformat(), "account": accounts.pop() if len(accounts) == 1 else None, "threads": threads, "owed": owed,
            "coverage": {"threads": len(threads), "oldest": oldest, "unreadable": unreadable, "since": since or None,
                         "complete": complete, "through": read.isoformat() if complete else None},
            "line": line}


def plan(config: Path) -> list:
    """What a read opens and how far back it must reach, from the workspace's declaration."""
    import sync_watermark as watermarks
    from synthesis.yamlish import load
    try:
        declared = load(config.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        stop(f"cannot read the declaration {config} ({exc})")
    declared = declared if isinstance(declared, dict) else {}
    workspace, inboxes = declared.get("workspace"), declared.get("inboxes", ["focused"])
    thread = re.search(r"(?:/messaging/thread/)?([\w=+-]{8,})/?$", str(declared.get("parking_thread") or "").strip())
    if not isinstance(workspace, str) or not workspace.strip():
        stop(f"{config} names no workspace")
    if not thread:
        stop(f"{config} names no parking_thread: a dormant conversation whose opening changes nothing. Without one the "
             "read would load the bare messaging page, which opens the newest conversation and marks it read")
    if not isinstance(inboxes, list) or not inboxes or not all(isinstance(i, str) and i.strip() for i in inboxes):
        stop(f"{config}: inboxes is a list of the list views to read, for example [focused]")
    lines = [f"open  https://www.linkedin.com/messaging/thread/{thread[1]}/  (the parking thread; never the bare messaging page)"]
    for inbox in inboxes:
        last = watermarks.window(workspace, "linkedin", inbox)["from"]
        lines.append(f"read  {inbox}: read through {last[:10]}; scroll back to that day and pass --since {last[:10]}" if last
                     else f"read  {inbox}: never read; scroll back two weeks")
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan", help="what to open and how far back to read").add_argument("--config", required=True, type=Path)
    read = sub.add_parser("parse", help="read the saved text of the conversation list")
    read.add_argument("--text", required=True, type=Path)
    read.add_argument("--read-at", required=True, help="when the list was read, ISO-8601 with its offset")
    read.add_argument("--since", default="", help="the day the last read reached, YYYY-MM-DD")
    read.add_argument("--opened", type=int, default=0, help="how many threads this read opened (each marks one read)")
    read.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "plan":
        print("\n".join(plan(args.config)))
        return 0
    try:
        moment = datetime.fromisoformat(args.read_at.replace("Z", "+00:00"))
        text = args.text.read_text(encoding="utf-8")
    except (ValueError, OSError) as exc:
        stop(f"cannot read --read-at or --text ({exc})")
    if args.since and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.since):
        stop("--since is a day, YYYY-MM-DD")
    result = parse(text, moment, args.since, args.opened)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result["line"])
        for t in result["owed"]:
            marks = [m for m in ("InMail" if t["kind"] == "inmail" else "", f"{t['unread']} unread" if t["unread"] else "",
                                 "LinkedIn asks for a reply" if t["nudge"] else "") if m]
            print(f"  {t['last'][:10]} {t['who']}: {t['preview'][:200]}" + (f"  [{', '.join(marks)}]" if marks else ""))
    return 0 if result["coverage"]["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
