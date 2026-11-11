#!/usr/bin/env python3
"""Check that every in-person commitment in a calendar read has its travel worked out.

A commitment with a place has four parts: the time, the place, the way there and the way back. On
2026-11-11 a principal who owns no car found an evening event 28 miles from home that had been on
his calendar for six days with only the first, and half of the second ("address on the card").
Given a saved calendar read and the principal's travel policy, this lists each in-person event in
the days asked for with what it lacks: an exact address, its travel line, a travel block on each
side, a line of a block, an arrival before the start, and the cases that are the principal's to
decide (a return that leaves early or gets home late, a car on a personal trip). It plans no trip
and reads no timetable: an agent does that from a live source. It reads two files and writes nothing.

    travel_check.py --events read.json [--from YYYY-MM-DD] [--days 7] [--today YYYY-MM-DD]
        [--config ~/.synthesis/chief-of-staff/preferences.json] [--json]

`read.json` is the calendar read `slot_check.py` takes, each event with its `location` and
`description` as well. A travel block is an event whose title starts with the policy's
`block_title`, with labeled lines in its description: `For:`, `Paid by:`, `Leave:`, `Route:`,
`Arrive:`, `Backup:`, `Fare:`, `Ticket:`, and `Decision:` where the principal decided something.
The commitment's own description says where its travel stands on a `Travel:` line: blocks, or
`local, N min walk`, or `none, <why>`. Exit 0 when every in-person event is whole, 1 when one is
flagged, 2 when it was not shown enough to judge (no policy, a read that does not cover the days).
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical
sys.path.insert(0, str(Path(__file__).resolve().parent))
import slot_check as slot  # noqa: E402  the same calendar read, read the same way

LINES = ("Paid by", "Leave", "Route", "Arrive", "Backup", "Fare", "Ticket")
LABEL = re.compile(r"(?im)^\s*(For|Paid by|Leave|Route|Arrive|Backup|Fare|Ticket|Decision|Travel)\s*:[ \t]*(.*)$")
EMPTY = re.compile(r"(?i)\s*(?:tbd|tbc|tba|tk|n/?a|unknown|to be (?:confirmed|decided|determined|announced)|\?+|-+)?\s*")
BREAK = re.compile(r"(?i)<br\s*/?>|</(?:p|div|li|tr|h\d)>")  # a connector may return a description as HTML
CAR = re.compile(r"(?i)\b(?:car|uber|lyft|taxi|cab|rideshare|ride[ -]share|limo|car service)\b")
NEAR = timedelta(hours=12)  # farther than this from every commitment, a block with no `For:` line belongs to none
ASK = "the principal's decision, written on a `Decision:` line of that block"


def stop(message: str):
    raise SystemExit(f"travel_check: {message}")


def lines(description: str) -> dict:
    """The labeled lines of a description, a placeholder counting as no line. HTML is read as the text it shows."""
    text = html.unescape(re.sub(r"<[^<>]+>", "", BREAK.sub("\n", description or "")))
    return {label.lower(): value.strip() for label, value in LABEL.findall(text) if not EMPTY.fullmatch(value)}


def place(location: str, policy: dict) -> str:
    """'' for no place (empty, a link, a number to call, an online meeting), 'base' for the home or a named
    place with a standing route, 'away' for anywhere else."""
    text = " ".join(str(location or "").split())
    low = text.lower()
    online = [str(w).lower() for w in policy.get("online") or []]
    if (not text or "://" in low or low.startswith("www.") or re.fullmatch(r"[\d\s()+.-]{7,}", text)
            or any(re.search(rf"\b{re.escape(w)}\b", low) for w in online)):
        return ""
    bases = [slot.part(policy, "home"), *[p for p in policy.get("places") or [] if isinstance(p, dict)]]
    for base in bases:
        label, address = str(base.get("label") or "").lower(), str(base.get("address") or "").lower()
        if (label and low == label) or (address and address in low):
            return "base"
    return "away"


def judge(args, config: dict, read: dict) -> dict:
    policy = slot.part(config, "travel_policy")
    if not policy:
        stop("the preferences hold no travel_policy: no policy, no check")
    zone = ZoneInfo(str(config.get("timezone") or "UTC"))
    today = date.fromisoformat(args.today) if args.today else datetime.now(zone).date()
    first = date.fromisoformat(args.start) if args.start else today
    last = first + timedelta(days=args.days - 1)
    window = read.get("window") if isinstance(read, dict) else None
    if not isinstance(window, dict) or not window.get("from") or not window.get("through"):
        stop('the calendar read must say which days it covers: {"window": {"from": ..., "through": ...}, "events": [...]}')
    if window["from"] > first.isoformat() or window["through"] < last.isoformat():
        stop(f"the calendar read does not cover {first} through {last} (it covers {window['from']} through {window['through']}); "
             "read the calendar for those days first")
    title = str(policy.get("block_title") or "Travel").lower()
    blocks, commitments = [], []
    for entry in read.get("events") or []:
        try:
            a, b = slot.moment(entry.get("start"), zone), slot.moment(entry.get("end"), zone)
        except SystemExit as exc:
            stop(str(exc.code).split(": ", 1)[-1])
        summary, said = str(entry.get("summary") or "an event"), lines(entry.get("description"))
        if re.match(rf"{re.escape(title)}\b", summary.lower()):
            blocks += [{"start": a, "end": b, "said": said}] if a and b else []
            continue
        raw = entry.get("start")
        try:
            day = a.date() if a else date.fromisoformat(str(raw.get("date") if isinstance(raw, dict) else raw)[:10])
        except ValueError:
            continue  # an entry with no start is not an event this can place on a day
        if place(entry.get("location"), policy) == "away":
            commitments.append({"summary": summary, "start": a, "end": b, "day": day, "said": said,
                                "location": " ".join(str(entry.get("location")).split())})
    timed = [c for c in commitments if c["start"]]
    for block in blocks:  # a block that names no commitment belongs to the one it stands nearest to, and to no other
        near = min(timed, key=lambda c: min(abs(c["start"] - block["end"]), abs(block["start"] - c["end"])), default=None)
        block["beside"] = near if near and min(abs(near["start"] - block["end"]), abs(block["start"] - near["end"])) <= NEAR else None
    commitments = [c for c in commitments if first <= c["day"] <= last]
    early, local = int(policy.get("arrive_early_minutes", 15)), int(policy.get("local_minutes", 15))
    latest = str(policy.get("latest_return") or "")
    events = []
    for c in sorted(commitments, key=lambda c: (c["day"], c["start"] or datetime.min.replace(tzinfo=zone))):
        lacks, found = [], {"summary": c["summary"], "start": c["start"].isoformat() if c["start"] else c["day"].isoformat(),
                            "location": c["location"]}
        if not re.search(r"\d", c["location"]):
            lacks.append(f'no exact address: the location reads "{c["location"]}"')
        travel = c["said"].get("travel", "")
        minutes = re.search(r"(?i)\blocal\b\D*(\d+)\s*min", travel)
        if not travel:
            lacks.append("no travel line in the event: `Travel: blocks before and after`, or `Travel: local, N min walk`")
        if re.match(r"(?i)local\b", travel) and not minutes:
            lacks.append("the travel line says local and gives no minutes")
        elif minutes and int(minutes[1]) > local:
            lacks.append(f"{minutes[1]} minutes is over the {local} the policy calls local: it needs travel blocks")
        if minutes or re.match(r"(?i)(?:local|none\b\W+\w)", travel):
            events.append({**found, "lacks": lacks})
            continue
        if not c["start"]:
            lacks += ["the event holds no clock times, so its blocks cannot be checked: give it times"] if travel else []
            events.append({**found, "lacks": lacks})
            continue
        named = [b for b in blocks if b["said"].get("for") and (b["said"]["for"].lower() in c["summary"].lower()
                                                                or c["summary"].lower() in b["said"]["for"].lower())]
        loose = [b for b in blocks if not b["said"].get("for") and b["beside"] is c]
        before = max((b for b in named + loose if b["start"] < c["start"]), key=lambda b: b["start"], default=None)
        after = min((b for b in named + loose if b["start"] >= c["start"]), key=lambda b: b["start"], default=None)
        for side, block in (("before", before), ("after", after)):
            if not block:
                lacks.append(f"no travel block {side} it (leave, route, arrive, backup, fare, ticket)")
                continue
            lacks += [f"the block {side} has no `{line}:` line" for line in LINES if not block["said"].get(line.lower())]
            if (CAR.search(block["said"].get("route", "")) and "personal" in block["said"].get("paid by", "").lower()
                    and not block["said"].get("decision")):
                lacks.append(f"a car on a personal trip (the block {side}): {ASK}")
        if before:
            gap = int((c["start"] - before["end"]).total_seconds() // 60)
            if gap < 0:
                lacks.append(f"the block before arrives {slot.hm(before['end'])}, after the {slot.hm(c['start'])} start")
            elif gap < early:
                lacks.append(f"the block before arrives {slot.hm(before['end'])}, {gap} minutes before the start; the policy asks for {early}")
            found.update(leave=slot.hm(before["start"]), paid_by=before["said"].get("paid by", ""))
        if after:
            decided = bool(after["said"].get("decision"))
            if after["start"] < c["end"] and not decided:
                lacks.append(f"the block after leaves {slot.hm(after['start'])}, before the {slot.hm(c['end'])} end: {ASK}")
            late = latest and (after["end"].date() > c["start"].date() or after["end"].time() > time.fromisoformat(latest))
            if late and not decided:
                lacks.append(f"home at {slot.hm(after['end'])}, after {latest}: {ASK}")
            found.update(home=slot.hm(after["end"]))
        events.append({**found, "lacks": lacks})
    flagged = sum(bool(e["lacks"]) for e in events)
    return {"window": {"from": first.isoformat(), "through": last.isoformat()}, "in_person": len(events), "flagged": flagged,
            "verdict": "REFUSE" if flagged else "OK", "events": events}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--events", required=True, type=Path, help="the saved calendar read, with the days it covers")
    parser.add_argument("--from", dest="start", help="the first day to judge, YYYY-MM-DD; defaults to today")
    parser.add_argument("--days", type=int, default=7, help="how many days to judge, the first included")
    parser.add_argument("--today", help="YYYY-MM-DD; defaults to today in the principal's zone")
    parser.add_argument("--config", type=Path, default=Path.home() / ".synthesis" / "chief-of-staff" / "preferences.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        stop(f"the principal's preferences cannot be read ({exc}); no preferences, no check")
    try:
        read = json.loads(args.events.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        stop(f"the calendar read cannot be read ({exc})")
    result = judge(args, config if isinstance(config, dict) else {}, read)
    if args.json:
        print(json.dumps(result, indent=2))
        return 1 if result["flagged"] else 0
    count, flagged = result["in_person"], result["flagged"]
    print(f"travel: {count} in-person event{'s' * (count != 1)} from {result['window']['from']} through {result['window']['through']}; "
          + ("none lacks its travel" if not flagged else "1 lacks its travel" if flagged == 1 else f"{flagged} lack their travel"))
    for e in result["events"]:
        at = datetime.fromisoformat(e["start"]) if "T" in e["start"] else date.fromisoformat(e["start"])
        when = at.strftime("%a %Y-%m-%d %H:%M") if isinstance(at, datetime) else at.strftime("%a %Y-%m-%d") + " all day"
        print(f"  {'REFUSE' if e['lacks'] else 'OK':<7} {when} {e['summary']}"
              + (f" (leave {e['leave']}, home {e['home']})" if e.get("leave") and e.get("home") and not e["lacks"] else ""))
        for item in e["lacks"]:
            print(f"          - {item}")
    return 1 if flagged else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit as exc:
        if isinstance(exc.code, str):
            print(exc.code, file=sys.stderr)
            sys.exit(2)
        raise
