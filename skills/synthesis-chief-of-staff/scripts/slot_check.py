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
Give every event of those days, the principal's own blocks included, with its attendees as the calendar
gives them: an event someone else is on is a meeting, any other is the principal's own time.
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


def hour(policy: dict, key: str) -> time | None:
    """An hour the travel policy gives, None when it gives none. A value that is no time of day stops the check:
    nothing is judged on a guess."""
    value = str(policy.get(key) or "")
    try:
        return time.fromisoformat(value) if value else None
    except ValueError:
        stop(f"travel_policy.{key} is {value!r}, which is no time of day: write it as HH:MM")


def morning_day(home: datetime, starts: time | None = None, since: datetime | None = None) -> date:
    """The day of the morning a return is judged against. With an hour for the morning, the first one still ahead.
    With none, the night is the one that begins on the day the principal gets home, or on the day before when that
    is past midnight; an outing that began and ended on one morning came after the night, so its morning is the
    next day's (a breakfast across town and a call an hour later read as a night of one hour)."""
    if starts is not None:
        return home.date() if home.time() < starts else home.date() + timedelta(days=1)
    past_midnight = home.hour < 12 and not (since is not None and since.date() == home.date())
    return home.date() if past_midnight else home.date() + timedelta(days=1)


def morning_after(home: datetime, entries: list, hours, starts: time | None = None, since: datetime | None = None) -> tuple | None:
    """(start, title, the time between) for the next morning's first entry, when it starts less than `hours` after
    the principal gets home; an entry later the same night is not the morning. `starts` is the hour the policy says
    the morning begins, entry or none (its title is empty): the night ends at the earlier of the two. `since` is
    when the outing began: one that began on an earlier day and ran past that hour, or past the start of that
    morning's first entry, left no night at all (the time between is zero). `entries` are the other entries of the
    read, without the outing's own."""
    day, begins = morning_day(home, starts, since), []
    if starts is not None:
        begins = [(datetime.combine(day, starts, home.tzinfo), "")]
        began = begins[0][0] - timedelta(days=1)  # the last morning that began before the return
        if hours and since is not None and since.date() < began.date():
            return began, "", timedelta(0)
    begun = min(((a, title) for a, title in entries if since is not None and a.date() == day and since < a <= home), default=None)
    if begun and hours:  # that morning's first entry had begun before the return
        return (*begun, timedelta(0))
    first = min(((a, title) for a, title in [*entries, *begins] if a.date() == day and a > home), default=None)
    return (*first, first[0] - home) if first and hours and first[0] - home < timedelta(hours=float(hours)) else None


def first_thing(short: tuple, keeps) -> str:
    """How a short night is said: the next morning's first entry by its title, or the hour the policy gives the
    morning, with the time between; or that the morning had begun before the return."""
    under = f"under the {float(keeps):g} hours the policy keeps"
    if short[2] <= timedelta(0):
        what = f'"{short[1]}" began at {hm(short[0])}' if short[1] else f"the morning began at {hm(short[0])} (the policy's hour)"
        return f"{what} before the return: no night at all, {under}"
    what = f'"{short[1]}" starts {hm(short[0])}' if short[1] else f"the morning starts {hm(short[0])} (the policy's hour)"
    return f"{what} the next morning: {span(short[2])} between, {under}"


def clock(day: date, text: str, zone: ZoneInfo) -> datetime:
    """An hour of a day; 24:00 is the midnight that ends it. A value that is no time of day stops the check."""
    text, late = str(text).strip(), str(text).strip() == "24:00"
    try:
        return datetime.combine(day + timedelta(days=late), time.fromisoformat("00" + text[2:] if late else text), zone)
    except ValueError:
        stop(f"{text!r} in the preferences is no time of day: write it as HH:MM")


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

    # A meeting is an event someone else is on. The principal's own blocks (a routine, training, a reserved hold)
    # are taken time for every other check and no part of the meeting load (2026-11-11: a day read 7.08 hours of
    # meetings against a limit of 5, and 4.5 of them were the principal's own).
    own = [str(address).lower() for address in config.get("principal_addresses") or []]
    marks = [str(mark).lower() for mark in guardian.get("personal_markers") or []]
    worded = [mark for mark in marks if not re.search(r"[^\w\s]", mark)]
    if worded:  # a word would hide every meeting whose title carries it (a marker `training`, "Training with the team")
        stop(f"calendar_guardian.personal_markers holds {worded[0]!r}, a plain word a meeting's title might carry: a marker is a "
             "tag the principal puts on their own blocks, such as #reserved")
    events, joined, marked = [], set(), set()
    for entry in read.get("events") or []:
        a, b = moment(entry.get("start"), zone), moment(entry.get("end"), zone)
        if a and b and b > a and str(entry.get("summary") or "").strip().lower() != hold:
            title, guests = str(entry.get("summary") or "a meeting"), entry.get("attendees") or []
            who = {x.lower() for x in ADDRESS.findall(json.dumps(guests))}
            me = {x.lower() for g in guests if isinstance(g, dict) and g.get("self") for x in ADDRESS.findall(json.dumps(g))}
            events.append((a, b, title, who))
            joined |= {(a, b, title)} if any(not any(fnmatch.fnmatchcase(p, e) for e in own) for p in who - me) else set()
            marked |= {(a, b, title)} if any(re.search(rf"(?<!\w){re.escape(mark)}(?!\w)", title.lower()) for mark in marks) else set()
    # An event is taken time on each day it covers: a block from 23:00 the night before is part of this morning,
    # and a trip back past midnight meets the next day's first entry. The slot's own hour, when the read holds it,
    # is the event being checked again.
    others = [(a, b, s) for a, b, s, _ in events if (a, b) != (start, end)]
    dawn = datetime.combine(start.date(), time.min, zone)
    dusk = dawn + timedelta(days=1)
    that_day = [(a, b, s) for a, b, s in others if a < dusk and b > dawn]
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

    # Protected hours are a list of windows, or a section that holds a `windows` list beside lines of prose another
    # reader depends on. A line of prose is named as unchecked unless a window gives it as its `source`.
    protected = config.get("protected_hours") or []
    windows = protected.get("windows") or [] if isinstance(protected, dict) else protected
    prose = sorted(k for k, v in protected.items() if isinstance(v, str) and not k.startswith("_") and not any(
        str(w.get("source") or "").split(".")[-1] == k for w in windows if isinstance(w, dict))) if isinstance(protected, dict) else []
    unread = f"the preferences describe protected hours in prose ({', '.join(prose)}), which this cannot read: check them yourself"
    if isinstance(windows, list) and (windows or not prose) and all(isinstance(p, dict) and p.get("start") and p.get("end") for p in windows):
        hit = next((p for day in sorted({start.date(), end.date()}) for p in windows if day.weekday() in p.get("days", range(7))
                    and start < clock(day, p["end"], zone) and end > clock(day, p["start"], zone)), None)
        if hit and not binds:
            add("protected hours", "REFUSE", f"inside protected hours {hit['start']}-{hit['end']}"
                + (f" ({hit['label']})" if hit.get("label") else ""))
        elif hit or not prose:
            add("protected hours", "OK", "inside protected hours, for someone whose timing binds" if hit else "outside protected hours")
        else:
            add("protected hours", "NOTE", f"outside the protected windows; {unread}")
    else:
        add("protected hours", "NOTE", unread if prose else "the preferences describe protected hours in a form this cannot read: check them yourself")

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
        there = next((s for a, b, s in others if out and a < start and b > start - out), None)
        home = next((s for a, b, s in others if back and a < end + back and b > end), None)
        add("travel", "REFUSE" if there or home else "OK",
            f"the trip there ({hm(start - out)}-{hm(start)}) overlaps {there}" if there
            else f"the trip back ({hm(end)}-{hm(end + back)}) overlaps {home}" if home
            else f"{hm(start - out)}-{hm(start)} there, {hm(end)}-{hm(end + back)} back, clear of other events")
    if back:  # what the evening costs is seen before the yes: when the principal is home, and what the night leaves
        policy, home = part(config, "travel_policy"), end + back
        latest, keeps = hour(policy, "latest_return"), policy.get("sleep_hours")
        late = latest and (home.date() > start.date() or home.time() > latest)
        add("return", "REVIEW" if late else "OK", f"home at {hm(home)}" + (
            f", after {latest:%H:%M}: the principal's decision, made with the trip in front of them" if late else ""))
        morning = morning_day(home, hour(policy, "morning_starts"), start - out)
        short = morning_after(home, [(a, s) for a, _, s in others], keeps, hour(policy, "morning_starts"), start - out)
        if keeps and short:  # short by an entry the read holds, or by the hour the policy says the morning starts
            add("sleep", "REVIEW", f"home at {hm(home)} and {first_thing(short, keeps)}: the principal's decision")
        elif keeps and window["through"] < morning.isoformat():
            add("sleep", "NOTE", f"the calendar read ends before {morning}, so the night cannot be judged: read through that day")
        elif keeps:
            add("sleep", "OK", f"{float(keeps):g} hours or more between getting home and the next morning's first commitment")

    counted = [e for e in that_day if e not in marked and (e in joined or not joined)]  # a read that names no one else tells no block from a meeting
    load = sum(((min(b, dusk) - max(a, dawn)).total_seconds() for a, b, _ in counted), (end - start).total_seconds()) / 3600
    most, left = float(limits.get("max_meeting_hours_per_day", 5)), len(that_day) - len(counted)
    add("meeting load", "REFUSE" if load > most else "OK", f"{load:.2f} hours of meetings that day with this one (limit {most:g})" + (
        f"; {left} of the day's {len(that_day)} events are the principal's own blocks and are not counted" if left else "") + (
        "; the read names no one else on any event, so each is counted as a meeting" if counted and not joined else ""))

    near = next((s for a, b, s in that_day if abs(start - b) <= BESIDE or abs(a - end) <= BESIDE), None)
    block = next((g for g in free_blocks([(a, b) for a, b, _ in that_day], opens, closes) if g[0] <= start and end <= g[1]), None)
    over = next(((a, b, s) for a, b, s in others if a < end and b > start), None)
    if over:  # on top of another event: never placed as if the time were free
        add("placement", "REVIEW", f"it overlaps {over[2]} ({hm(over[0])}-{hm(over[1])}): the principal's decision, or another time")
    elif near:
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
