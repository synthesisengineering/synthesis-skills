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
STREET = re.compile(r"(?i)(?:^|[,;(@]|\bat\s)\s*\d+[^\W\d_]?(?:[-–/]\d+)*(?:[ \t]+\d+)*[ \t]+(?:\d+(?:st|nd|rd|th)\b|[^\W\d_])")
CLOCK = re.compile(r"(?i)\b\d{1,2}(?::\d{2})?\s*[ap]\.?m\b\.?|\b\d{1,2}:\d{2}\b")
CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")  # an address in these scripts runs number and name together
CAR = re.compile(r"(?i)\b(?:car|uber|lyft|taxi|cab|rideshare|ride[ -]share|limo|car service)\b")
NEAR = timedelta(hours=12)  # farther than this from every commitment, a block with no `For:` line serves none
ASK = "the principal's decision, written on a `Decision:` line of that block"


def stop(message: str):
    raise SystemExit(f"travel_check: {message}")


def lines(description: str) -> dict:
    """The labeled lines of a description, a placeholder counting as no line and a label given twice keeping both
    values, one to a line. HTML is read as the text it shows."""
    text, said = html.unescape(re.sub(r"<[^<>]+>", "", BREAK.sub("\n", str(description or "")))), {}
    for label, value in LABEL.findall(text):
        if not EMPTY.fullmatch(value):
            said[label.lower()] = "\n".join(filter(None, [said.get(label.lower()), value.strip()]))
    return said


def tidy(location) -> str:
    """A location on one line, each line of it a part as a comma would make it."""
    return ", ".join(" ".join(row.split()) for row in str(location or "").splitlines() if row.strip())


def street(text: str):
    """A house number with its street, or a postcode with its town, after it (`149 Main St`, `10115 Berlin`); a
    time of day is set aside first."""
    return STREET.search(CLOCK.sub("", text))


def exact(location: str) -> bool:
    """Whether a location reads as an address a route can be planned to: a street number as above, or a number in
    one part and a name in another (`Calle Mayor, 5`). A venue whose name ends in a number (`Studio 54`) and a
    time of day are not one. It reads the form of what is written, not a map."""
    text = CLOCK.sub("", location)
    numbered = [bool(re.search(r"\d", part)) for part in re.split(r"[,;]", text) if part.strip()]
    return bool(street(location) or (any(numbered) and (not all(numbered) or CJK.search(text))))


def place(location: str, policy: dict) -> str:
    """'' for no place (empty, a link, a number to call, an online meeting), 'base' for the home or a named
    place with a standing route, 'away' for anywhere else. A location that holds a street address is a place
    whatever else it says: a venue called Zoom Hall, a map link beside it, a number to call as well."""
    text = tidy(location)
    low = text.lower()
    online = [str(w).lower() for w in policy.get("online") or []]
    if not text or (not street(text) and ("://" in low or low.startswith("www.") or re.fullmatch(r"[\d\s()+.-]{7,}", text)
                                          or any(re.search(rf"\b{re.escape(w)}\b", low) for w in online))):
        return ""
    bases = [slot.part(policy, "home"), *[p for p in policy.get("places") or [] if isinstance(p, dict)]]
    for base in bases:
        label, address = str(base.get("label") or "").lower(), str(base.get("address") or "").lower()
        if (label and re.match(rf"{re.escape(label)}\s*(?:$|[,(:;/–-])", low)) or (address and address in low):
            return "base"  # its label, alone or with a room or a note after it, or its address anywhere
    return "away"


def days(entry: dict, a, b):
    """The first and last day an entry covers; None when it has no start, which makes it no event. An all-day end
    names the day after its last, as calendars give it, and a timed entry that ends at midnight ends the day before."""
    if a:
        return a.date(), max(a, (b or a) - timedelta(minutes=1)).date()
    try:
        first, last = (date.fromisoformat(str(v.get("date") if isinstance(v, dict) else v)[:10])
                       for v in (entry.get("start"), entry.get("end") or entry.get("start")))
    except ValueError:
        if entry.get("start"):
            stop(f"the start or end of {str(entry.get('summary'))!r} is not a date or a time this can read")
        return None
    return first, max(first, last - timedelta(days=1))


def judge(args, config: dict, read: dict) -> dict:
    policy = slot.part(config, "travel_policy")
    if not policy:
        stop("the preferences hold no travel_policy: no policy, no check")
    zone = ZoneInfo(str(config.get("timezone") or "UTC"))
    today = date.fromisoformat(args.today) if args.today else datetime.now(zone).date()
    first = date.fromisoformat(args.start) if args.start else today
    last = first + timedelta(days=args.days - 1)
    try:
        covered = [date.fromisoformat(str(read["window"][key])[:10]) for key in ("from", "through")]
    except (TypeError, KeyError, ValueError):
        stop('the calendar read must say which days it covers: {"window": {"from": ..., "through": ...}, "events": [...]}')
    if covered[0] > first or covered[1] < last:
        stop(f"the calendar read does not cover {first} through {last} (it covers {covered[0]} through {covered[1]}); "
             "read the calendar for those days first")
    title = str(policy.get("block_title") or "Travel").lower()
    blocks, commitments, others = [], [], []
    for entry in (e for e in read.get("events") or [] if isinstance(e, dict)):
        try:
            a, b = slot.moment(entry.get("start"), zone), slot.moment(entry.get("end"), zone)
        except SystemExit as exc:
            stop(str(exc.code).split(": ", 1)[-1])
        summary, said = str(entry.get("summary") or "an event"), lines(entry.get("description"))
        if re.match(rf"{re.escape(title)}\b", summary.lower()):
            names = [" ".join(name.lower().split()) for name in said.get("for", "").splitlines()]
            blocks += [{"start": a, "end": b, "said": said, "names": names}] if a and b else []
            continue
        others += [(a, summary)] if a else []  # every timed entry: the next morning's first one is what a night runs into
        span, spot = days(entry, a, b), tidy(entry.get("location"))
        if span and place(spot, policy) == "away":
            commitments.append({"summary": summary, "title": " ".join(summary.lower().split()), "start": a, "end": b or a,
                                "days": span, "said": said, "location": spot})
    timed = [c for c in commitments if c["start"]]

    def apart(block, c):  # how far a block stands from a commitment
        return min(abs(c["start"] - block["end"]), abs(block["start"] - c["end"]))
    for block in blocks:  # a block serves each commitment it names; one that names none, the commitment nearest to it
        titled = [[c for c in timed if c["title"] == name] or [c for c in timed if c["title"].startswith(name)] for name in block["names"]]
        nearest = min(timed, key=lambda c: apart(block, c), default=None)
        block["serves"] = ([min(found, key=lambda c: apart(block, c)) for found in titled if found] if block["names"]
                           else [nearest] if nearest and apart(block, nearest) <= NEAR else [])
    commitments = [c for c in commitments if c["days"][0] <= last and c["days"][1] >= first]  # under way on a day judged counts
    early, local = int(policy.get("arrive_early_minutes", 15)), int(policy.get("local_minutes", 15))
    latest = str(policy.get("latest_return") or "")
    events = []
    for c in sorted(commitments, key=lambda c: (c["days"][0], c["start"] or datetime.min.replace(tzinfo=zone))):
        lacks, found = [], {"summary": c["summary"], "start": c["start"].isoformat() if c["start"] else c["days"][0].isoformat(),
                            "location": c["location"]}
        if not exact(c["location"]):
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
        mine = [b for b in blocks if any(served is c for served in b["serves"])]
        before = max((b for b in mine if b["start"] < c["start"]), key=lambda b: b["start"], default=None)
        after = min((b for b in mine if b["start"] >= c["start"]), key=lambda b: b["start"], default=None)
        # A side that lies outside the read is not judged from it: the way to an event already under way when the
        # read begins, the way back from one that outlasts it.
        for side, block in [("before", before)] * (c["days"][0] >= covered[0]) + [("after", after)] * (c["days"][1] <= covered[1]):
            if not block:
                beside = next((b for b in blocks if b not in mine and apart(b, c) <= NEAR and (b["start"] < c["start"]) == (side == "before")), None)
                whose = beside and ("; ".join(beside["said"].get("for", "").splitlines()) or beside["serves"][0]["summary"])
                lacks.append(f"no travel block {side} it (leave, route, arrive, backup, fare, ticket)" + (
                    f'; the block at {slot.hm(beside["start"])} is for "{whose}", and a block serves only the events its `For:` lines name'
                    if beside else ""))
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
            short = slot.morning_after(after["end"], others, policy.get("sleep_hours"))
            if short and not decided:
                lacks.append(f"home at {slot.hm(after['end'])} and \"{short[1]}\" starts {slot.hm(short[0])} the next morning: "
                             f"{slot.span(short[2])} between, under the {float(policy['sleep_hours']):g} hours the policy keeps: {ASK}")
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
    except Exception as exc:  # noqa: BLE001  a read it cannot make sense of was not shown enough: never 0 or 1
        print(f"travel_check: this calendar read could not be judged ({exc!r})", file=sys.stderr)
        sys.exit(2)
