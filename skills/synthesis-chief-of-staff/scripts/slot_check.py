#!/usr/bin/env python3
"""Judge one proposed meeting time against the principal's terms, before it is offered or placed.

A yes to a meeting is not a yes to the earliest free slot (2026-11-09: a follow-up was staged into
the first open half hour of the same day, three days running, to suit the requester). Given the
slot, the calendar read that covers its day and the principal's preferences, this prints one
verdict and the reason for each check: same day, protected hours, working hours, the deep-work
block left, the day's meeting load, placement beside existing meetings, an existing meeting with
the same people, and whose deadline binds. A meeting in person takes the trip there and back as
well: give the minutes on each side and they count as taken time (2026-11-11: an evening 28 miles
away was placed with no travel time at all). It reads two files and writes nothing.

    slot_check.py --start 2026-11-12T14:00 --end 2026-11-12T14:30 --events read.json
        [--attendee a@example.com ...] [--requester a@example.com] [--deadline YYYY-MM-DD]
        [--in-person] [--travel-before MINUTES] [--travel-after MINUTES]
        [--today YYYY-MM-DD] [--config ~/.synthesis/chief-of-staff/preferences.json] [--json]

`read.json` is the calendar read, saved with the days it covers:
`{"window": {"from": "YYYY-MM-DD", "through": "YYYY-MM-DD"}, "events": [{"start", "end", "summary",
"attendees"}]}`; `start` and `end` are ISO strings or the connector's `{"dateTime"}` / `{"date"}`.
Exit 0 for OK or REVIEW, 1 for REFUSE, 2 when it was not shown enough to judge.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ORDER = {"OK": 0, "NOTE": 0, "REVIEW": 1, "REFUSE": 2}
BESIDE = timedelta(minutes=15)  # a gap this short still counts as next to a meeting
ADDRESS = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def stop(message: str):
    raise SystemExit(f"slot_check: {message}")


def moment(value, zone: ZoneInfo):
    """A start or end in the principal's zone; None for an all-day entry, which holds no clock time."""
    if isinstance(value, dict):
        value = value.get("dateTime") or value.get("date_time") or value.get("date")
    if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00").replace(" ", "T", 1))
    except ValueError:
        stop(f"{value!r} is not a time this can read; write YYYY-MM-DDTHH:MM")
    return (parsed.astimezone(zone) if parsed.tzinfo else parsed.replace(tzinfo=zone)).replace(second=0, microsecond=0)


def part(holder: dict, name: str) -> dict:
    """A section of the preferences, or {} when it is absent or written another way."""
    return holder[name] if isinstance(holder.get(name), dict) else {}


def hm(value: datetime) -> str:
    return value.strftime("%H:%M")


def span(gap: timedelta) -> str:
    hours, minutes = divmod(int(gap.total_seconds() // 60), 60)
    return f"{hours} h {minutes:02d} min"


def morning_after(home: datetime, entries: list, hours) -> tuple | None:
    """(start, title, the time between) for the next morning's first entry, when it starts less than `hours` after
    the principal gets home. The night is the one that begins on the day they get home, or on the day before when
    that is past midnight; an entry later the same night is not the morning."""
    night = home.date() if home.hour >= 12 else home.date() - timedelta(days=1)
    first = min(((a, title) for a, title in entries if a.date() == night + timedelta(days=1) and a > home), default=None)
    return (*first, first[0] - home) if first and hours and first[0] - home < timedelta(hours=float(hours)) else None


def clock(day: date, text: str, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, time.fromisoformat(text), zone)


def free_blocks(busy: list, start: datetime, end: datetime) -> list:
    """The gaps in [start, end) that no busy span covers."""
    gaps, cursor = [], start
    for a, b in sorted(busy):
        if a > cursor:
            gaps.append((cursor, min(a, end)))
        cursor = max(cursor, b)
        if cursor >= end:
            break
    return [(a, b) for a, b in gaps + ([(cursor, end)] if cursor < end else []) if b > a]


def judge(args, config: dict, read: dict) -> dict:
    zone = ZoneInfo(str(config.get("timezone") or "UTC"))
    start, end = moment(args.start, zone), moment(args.end, zone)
    if not start or not end or end <= start:
        stop("--start and --end need clock times, the end after the start")
    today = date.fromisoformat(args.today) if args.today else datetime.now(zone).date()
    out, back = timedelta(minutes=args.travel_before), timedelta(minutes=args.travel_after)
    if args.in_person and not (out or back):
        stop("an in-person slot needs its travel minutes on each side (--travel-before, --travel-after): work out the trip first")
    window = read.get("window") if isinstance(read, dict) else None
    if not isinstance(window, dict) or not window.get("from") or not window.get("through"):
        stop('the calendar read must say which days it covers: {"window": {"from": ..., "through": ...}, "events": [...]}')
    if not window["from"] <= start.date().isoformat() <= window["through"]:
        stop(f"the calendar read does not cover {start.date()} (it covers {window['from']} through {window['through']}); "
             "read the calendar for that day first")
    guardian, tiers = part(config, "calendar_guardian"), part(config, "tiers")
    limits, hold = part(guardian, "thresholds"), str(part(guardian, "holds").get("title") or "Hold").lower()
    senior = [str(e).lower() for name in ("priority", "above") for e in tiers.get(name) or [] if "@" in str(e)]
    people = {a.lower() for a in [*args.attendee, *([args.requester] if args.requester else [])]}
    binds = sorted(p for p in people if any(fnmatch.fnmatchcase(p, e) for e in senior))

    events = []
    for entry in read.get("events") or []:
        a, b = moment(entry.get("start"), zone), moment(entry.get("end"), zone)
        if a and b and b > a and str(entry.get("summary") or "").strip().lower() != hold:
            events.append((a, b, str(entry.get("summary") or "a meeting"),
                           {x.lower() for x in ADDRESS.findall(json.dumps(entry.get("attendees") or []))}))
    that_day = [(a, b, s) for a, b, s, _ in events if a.date() == start.date() and (a, b) != (start, end)]
    checks = []

    def add(check: str, level: str, detail: str) -> None:
        checks.append({"check": check, "level": level, "detail": detail})

    same_day_ok = bool(part(config, "meeting_defaults").get("same_day_meetings"))
    if start.date() < today:
        add("same day", "REFUSE", f"{start.date()} has passed")
    elif start.date() == today and not same_day_ok and not binds:
        add("same day", "REFUSE", "this is today: a meeting is not added to today unless the principal asks for it")
    else:
        add("same day", "OK", f"today, for someone whose timing binds ({', '.join(binds)})" if start.date() == today and binds
            else "today, which the preferences allow" if start.date() == today else f"{(start.date() - today).days} day(s) out")

    protected = config.get("protected_hours") or []
    if isinstance(protected, list) and all(isinstance(p, dict) and p.get("start") and p.get("end") for p in protected):
        hit = next((p for p in protected if start.weekday() in p.get("days", range(7))
                    and start < clock(start.date(), p["end"], zone) and end > clock(start.date(), p["start"], zone)), None)
        if hit and not binds:
            add("protected hours", "REFUSE", f"inside protected hours {hit['start']}-{hit['end']}"
                + (f" ({hit['label']})" if hit.get("label") else ""))
        else:
            add("protected hours", "OK", "inside protected hours, for someone whose timing binds" if hit else "outside protected hours")
    else:
        add("protected hours", "NOTE", "the preferences describe protected hours in prose, which this cannot read: check them yourself")

    hours = part(config, "working_hours")
    opens, closes = clock(start.date(), hours.get("start", "09:00"), zone), clock(start.date(), hours.get("end", "17:00"), zone)
    outside = start < opens or end > closes
    add("working hours", "REVIEW" if outside else "OK", f"{'outside' if outside else 'inside'} working hours {hm(opens)}-{hm(closes)}")

    need, blocks = int(limits.get("maker_block_minutes", 120)), int(limits.get("min_maker_blocks_per_day", 1))
    long_enough = lambda gaps: [g for g in gaps if g[1] - g[0] >= timedelta(minutes=need)]  # noqa: E731
    before = long_enough(free_blocks([(a, b) for a, b, _ in that_day], opens, closes))
    after = long_enough(free_blocks([(a, b) for a, b, _ in that_day] + [(start - out, end + back)], opens, closes))
    if len(after) < blocks:
        broke = next((g for g in before if g not in after), None)
        add("deep work", "REFUSE", (f"it would break the day's last {need}-minute free block ({hm(broke[0])}-{hm(broke[1])})" if broke
                                    else f"the day has no {need}-minute free block left, so it takes nothing more"))
    else:
        add("deep work", "OK", f"{len(after)} free block(s) of {need} minutes or more remain, the first {hm(after[0][0])}-{hm(after[0][1])}")

    if out or back:  # the trip is taken time: it may not run through another event
        there = next((s for a, b, s in that_day if out and a < start and b > start - out), None)
        home = next((s for a, b, s in that_day if back and a < end + back and b > end), None)
        add("travel", "REFUSE" if there or home else "OK",
            f"the trip there ({hm(start - out)}-{hm(start)}) overlaps {there}" if there
            else f"the trip back ({hm(end)}-{hm(end + back)}) overlaps {home}" if home
            else f"{hm(start - out)}-{hm(start)} there, {hm(end)}-{hm(end + back)} back, clear of other events")
    if back:  # what the evening costs is seen before the yes: when the principal is home, and what the night leaves
        policy, home = part(config, "travel_policy"), end + back
        latest, keeps = str(policy.get("latest_return") or ""), policy.get("sleep_hours")
        late = latest and (home.date() > start.date() or home.time() > time.fromisoformat(latest))
        add("return", "REVIEW" if late else "OK", f"home at {hm(home)}" + (
            f", after {latest}: the principal's decision, made with the trip in front of them" if late else ""))
        morning = (home.date() if home.hour >= 12 else home.date() - timedelta(days=1)) + timedelta(days=1)
        short = morning_after(home, [(a, s) for a, _, s, _ in events], keeps)
        if keeps and window["through"] < morning.isoformat():
            add("sleep", "NOTE", f"the calendar read ends before {morning}, so the night cannot be judged: read through that day")
        elif keeps:
            add("sleep", "REVIEW" if short else "OK", f"home at {hm(home)} and \"{short[1]}\" starts {hm(short[0])} the next morning: "
                f"{span(short[2])} between, under the {float(keeps):g} hours the policy keeps: the principal's decision" if short
                else f"{float(keeps):g} hours or more between getting home and the next morning's first commitment")

    load = sum(((b - a).total_seconds() for a, b, _ in that_day), (end - start).total_seconds()) / 3600
    most = float(limits.get("max_meeting_hours_per_day", 5))
    add("meeting load", "REFUSE" if load > most else "OK", f"{load:.2f} hours of meetings that day with this one (limit {most:g})")

    near = next((s for a, b, s in that_day if abs(start - b) <= BESIDE or abs(a - end) <= BESIDE), None)
    block = next((g for g in free_blocks([(a, b) for a, b, _ in that_day], opens, closes) if g[0] <= start and end <= g[1]), None)
    if near:
        add("placement", "OK", f"beside {near}")
    elif start - opens <= BESIDE or closes - end <= BESIDE or not block or block[1] - block[0] < timedelta(minutes=need):
        add("placement", "OK", "at an edge of the day or in a gap too short for deep work")
    else:
        add("placement", "REVIEW", f"it splits the free block {hm(block[0])}-{hm(block[1])}: place it beside an existing meeting, "
                                   "or at an edge of that block")

    horizon = today + timedelta(days=int(limits.get("touchpoint_days", 7)))
    met = [(a, s) for a, b, s, who in events if today <= a.date() <= horizon and (a, b) != (start, end) and who & people]
    if met:
        add("existing touchpoint", "REVIEW", "already meeting the same people: "
            + "; ".join(f"{s} on {a.strftime('%a %Y-%m-%d %H:%M')}" for a, s in sorted(met)[:3])
            + ". Use that meeting, or fold this ask into it, before adding another")
    else:
        add("existing touchpoint", "OK", f"no meeting with the same people from {today} through {horizon}")

    if args.deadline:
        requester_binds = bool(args.requester) and args.requester.lower() in binds
        if requester_binds and start.date().isoformat() > args.deadline:
            add("deadline", "REFUSE", f"the requester's timing binds and this is after their date ({args.deadline})")
        elif requester_binds:
            add("deadline", "OK", f"on or before {args.deadline}, for a requester whose timing binds")
        else:
            add("deadline", "NOTE", f"the requester's date ({args.deadline}) is their preference; the principal's calendar decides")

    names = [str(e) for name in ("priority", "above") for e in tiers.get(name) or [] if "@" not in str(e)]
    if names:
        add("tiers", "NOTE", f"{len(names)} tier entr{'y is a name' if len(names) == 1 else 'ies are names'}, not an address, "
                             "so this cannot match them: check those people yourself")
    verdict = max((c["level"] for c in checks), key=ORDER.get)
    return {"slot": {"start": start.isoformat(), "end": end.isoformat()},
            "verdict": "OK" if ORDER[verdict] == 0 else verdict, "checks": checks}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--events", required=True, type=Path, help="the saved calendar read, with the days it covers")
    parser.add_argument("--attendee", action="append", default=[])
    parser.add_argument("--requester")
    parser.add_argument("--deadline", help="the requester's date, YYYY-MM-DD")
    parser.add_argument("--in-person", action="store_true", help="the meeting is at a place: the travel minutes are required")
    parser.add_argument("--travel-before", type=int, default=0, help="minutes door to door to get there")
    parser.add_argument("--travel-after", type=int, default=0, help="minutes door to door to get back")
    parser.add_argument("--today", help="YYYY-MM-DD; defaults to today in the principal's zone")
    parser.add_argument("--config", type=Path, default=Path.home() / ".synthesis" / "chief-of-staff" / "preferences.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        stop(f"the principal's preferences cannot be read ({exc}); no preferences, no scheduling")
    try:
        read = json.loads(args.events.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        stop(f"the calendar read cannot be read ({exc})")
    result = judge(args, config if isinstance(config, dict) else {}, read)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        start, end = datetime.fromisoformat(result["slot"]["start"]), datetime.fromisoformat(result["slot"]["end"])
        print(f"slot {start.strftime('%a %Y-%m-%d')} {hm(start)}-{hm(end)}: {result['verdict']}")
        for c in result["checks"]:
            print(f"  {c['level']:<7} {c['check']}: {c['detail']}")
    return 1 if result["verdict"] == "REFUSE" else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit as exc:
        if isinstance(exc.code, str):
            print(exc.code, file=sys.stderr)
            sys.exit(2)
        raise
