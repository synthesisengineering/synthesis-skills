#!/usr/bin/env python3
"""Plan the day-start's same-day meeting briefs from a saved calendar read and the workspace's prep packs.

Every meeting the principal plans to attend gets a brief at day-start, the earliest first and each before it starts
(the principal's ruling, 2026-11-20): the v2.12.0 meeting-prep step was optional, and day-end prepares only the
meetings a workspace flags for lead time. This reads the day's calendar read and the folder of prep packs and prints:

  first:         the earliest meeting still to brief, with its start
  GAP            a calendar the read did not cover: its meetings are unknown, not none, and the day-start is not clean
  BRIEF          each meeting the principal plans to attend (accepted, accepted optional ones included, or organized
                 by the principal), in start order, with their part in it (organizer, optional, presents), the agenda
                 and links of the invitation, and the pack to refresh, the path to write or the brief written today
  UNCLEAR        invited and not answered, answered maybe, not among the attendees, or answered both ways
  DECLINED, HOLD, ENDED, NOT A MEETING (no one else on it, out of office, focus time, all day and free, cancelled)
  PACK           a pack of today that no meeting to brief has

    meeting_briefs.py --events today.json --packs <folder of prep packs> [--name NAME ...]
        [--config ~/.synthesis/chief-of-staff/preferences.json] [--now YYYY-MM-DDTHH:MM] [--json]

`today.json` is the calendar read: {"window": {"from": D, "through": D}, "calendars": [{"id", "read": true or false,
"error"}], "events": [...]}, each event as the connector gives it: `id`, `iCalUID`, `summary`, `start` and `end` (ISO
strings or {"dateTime"} / {"date"}), `status`, `eventType`, `transparency`, `organizer`, `attendees` (each with `email`,
`displayName`, `responseStatus`, `optional`, `self`, `resource`) and `description`. The preferences give `timezone`,
`principal_addresses`, the hold title and the personal markers (synthesis-chief-of-staff); `--name` adds the principal's
name as agendas write it. It reads those and the packs of the day, and writes nothing. Exit 0: every calendar read and
no answer waits. 1: a meeting's attendance is unclear. 2: a calendar was not read (the report still prints), or an
input cannot be read, so nothing is judged and one line on the error stream says why.
"""
from __future__ import annotations

import argparse
import fnmatch
import html
import json
import re
import sys
import unicodedata
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle

BREAK = re.compile(r"(?i)<br\s*/?>|</(?:div|li|tr|h\d)>")
PARAGRAPH = re.compile(r"(?i)</(?:p|ul|ol|table)>")  # a paragraph's end is a blank line, as the invitation shows it
AGENDA = re.compile(r"(?i)^\W*agenda\b[\W_]*(.*)$")
ITEM = re.compile(r"^(?:[-*•–]\s|\(?\d{1,2}[.)]\s|[a-z][.)]\s|\d{1,2}[:.]\d{2}\b)")
STOP = re.compile(r"(?i)^(?:[-=_~:*]{5,}|\W*(?:join|dial|meeting id|passcode|password|microsoft teams|zoom|google meet|webex)\b)")
LABEL = re.compile(r"^\w[\w /&'-]{0,30}:$")  # a line that only names a section, as `Notes:` does
URL = re.compile(r"https?://[^\s<>\"')\]]+")
JOIN = re.compile(r"(?i)^https?://(?:[\w-]+\.)*(?:zoom\.us|meet\.google\.com|teams\.microsoft\.com|teams\.live\.com|webex\.com|"
                  r"support\.google\.com|calendar\.google\.com|aka\.ms)(?:[/:?#]|$)")  # a way into the call, not its material
PRESENTING = re.compile(r"(?i)\b(?:present(?:s|ing|er|ers|ation)?|demo(?:s|ing)?|walk(?:s|ing)?[ -]?through|speak(?:s|er|ers|ing)?|"
                        r"lead(?:s|ing)?|read[ -]?out|report(?:s|ing)?[ -]out|pitch(?:es|ing)?)\b")
PREFIX = re.compile(r"(?i)^(?:meeting\s+)?(?:prep(?:aration)?|brief(?:ing)?|pack)\s*(?:for\b|[:\-–—])\s*")
PACK = re.compile(r"^(\d{4}-\d{2}-\d{2})-(?:([01]\d|2[0-3])([0-5]\d)-)?(.+?)(?:-prep)?\.md$")
HEADER = {key: re.compile(rf"(?im)^\s*(?:\*\*)?{key}:(?:\*\*)?[ \t]*(.*)$") for key in ("When", "Event", "Briefed")}
CLOCK = re.compile(r"(?i)\b([01]?\d|2[0-3]):([0-5]\d)\b(?:\s*([ap])\.?m\b)?")
NOT_MEETINGS = {"outofoffice": "out of office", "focustime": "focus time", "workinglocation": "working location",
                "birthday": "birthday"}
ANSWERS = {"accepted": "accepted", "organizer": "accepted", "declined": "declined", "tentative": "tentative",
           "tentativelyaccepted": "tentative", "needsaction": "needsaction", "notresponded": "needsaction",
           "none": "needsaction", "pending": "needsaction", "unknown": "needsaction", "": "needsaction"}
WHY = {"needsaction": "invited, not answered", "tentative": "answered maybe", None: "not among its attendees",
       "both": "accepted on one calendar and declined on another"}
STATE = {"declined": "declined", "holds": "a hold", "unclear": "of unclear attendance", "ended": "over",
         "not_meetings": "not a meeting"}
GROUPS = (("UNCLEAR", "unclear"), ("DECLINED", "declined"), ("HOLD", "holds"), ("ENDED", "ended"),
          ("NOT A MEETING", "not_meetings"))


def stop(message: str):
    raise SystemExit(f"meeting_briefs: {message}")


def moment(value, zone, what: str):
    """(time, day) of a start or end in the principal's zone; an all-day entry gives a day and no time."""
    if isinstance(value, dict):
        value = value.get("dateTime") or value.get("date_time") or value.get("date")
    text = str(value or "").strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return None, date.fromisoformat(text)
        text = re.sub(r"(\d{2}:\d{2}:\d{2})\.\d+", r"\1", text.replace(" ", "T", 1))  # Python 3.9 reads no 7-digit fraction
        found = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError:
        stop(f'"{what}" starts or ends at {value!r}, which is no date or time this can read: save the read again')
    found = (found.astimezone(zone) if found.tzinfo else found.replace(tzinfo=zone)).replace(second=0, microsecond=0)
    return found, found.date()


def plain(description) -> str:
    """The invitation as the lines it shows: HTML read as text, a paragraph's end as a blank line."""
    text = re.sub(r"(?i)<li\b[^>]*>", "\n- ", PARAGRAPH.sub("\n\n", BREAK.sub("\n", str(description or ""))))
    return html.unescape(re.sub(r"<[^<>]+>", "", text)).replace("\xa0", " ")


def agenda_of(text: str) -> list:
    """The lines under a line that says Agenda (and what that line itself lists), up to a separator, the joining
    details, a line that names another section, or a blank line that no further item follows."""
    lines = [" ".join(line.split()) for line in text.splitlines()]
    for n, line in enumerate(lines):
        head = AGENDA.match(line)
        if not head:
            continue
        found, rest = [head[1]] if head[1] else [], lines[n + 1:]
        for i, row in enumerate(rest):
            if not row and not ITEM.match(next((r for r in rest[i + 1:] if r), "")):
                break
            if row and (STOP.match(row) or LABEL.match(row) or AGENDA.match(row)):
                break
            found += [row] if row else []
        return found[:40]
    return []


def links_of(description) -> list:
    """The invitation's links to its material, in order, without the ways into the call."""
    raw = str(description or "")
    found = re.findall(r"(?i)href\s*=\s*[\"']([^\"']+)[\"']", raw) + URL.findall(html.unescape(re.sub(r"<[^<>]+>", " ", raw)))
    links = []
    for link in (html.unescape(f).rstrip(".,;:") for f in found):
        if link.lower().startswith(("http://", "https://")) and not JOIN.match(link) and link not in links:
            links.append(link)
    return links[:10]


def slug(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")[:60].rstrip("-") or "meeting"


def norm(title) -> str:
    return " ".join(re.sub(r"\W+", " ", PREFIX.sub("", str(title or "").strip()).casefold()).split())


def is_hold(title: str, word: str) -> bool:
    """A hold: titled with the hold word alone, in brackets, or followed by a colon, a dash or `for` (`HOLD: kickoff`,
    `Hold for the board`); `Holdings review` is a meeting."""
    word = re.escape(word.strip() or "Hold")
    return bool(re.match(rf"(?i)\s*(?:[\[(]\s*{word}\s*[\])]|{word}(?=\s*$|\s*[:\-–—|/]|\s+for\b))", title))


def mine(person, addresses: list) -> bool:
    if not isinstance(person, dict):
        return False
    email = str(person.get("email") or "").strip().lower()
    return person.get("self") is True or bool(email) and any(fnmatch.fnmatchcase(email, a) for a in addresses)


def combine(said: set, organizer: bool):
    """The principal's answer over every copy of the meeting: None when no copy lists them."""
    if {"accepted", "declined"} <= said:
        return "both"
    for answer in ("accepted", "declined"):
        if answer in said:
            return answer
    if organizer and said <= {"needsaction"}:
        return "accepted"  # the principal's own meeting, which the calendar leaves unanswered
    return "tentative" if "tentative" in said else "needsaction" if "needsaction" in said else min(said, default=None)


def read_events(read: dict, zone, day: date, addresses: list) -> list:
    """Today's events, one record per meeting however many calendars carry it."""
    merged = {}
    for entry in read["events"]:
        title = " ".join(str(entry.get("summary") or "(no title)").split())
        start, first = moment(entry.get("start"), zone, title)
        end, last = moment(entry.get("end") or entry.get("start"), zone, title)
        if start is None:
            last = max(first, last - timedelta(days=1))  # a calendar gives an all-day end as the day after its last
        if not (start.date() == day if start else first <= day <= last):
            continue
        people = entry.get("attendees") or []
        if not isinstance(people, list) or not all(isinstance(p, dict) for p in people):
            stop(f'the attendees of "{title}" are not a list of people: save the read again as the connector gives them')
        me = [p for p in people if mine(p, addresses)]
        key = (str(entry.get("iCalUID") or norm(title)), start or first, end or last)
        record = merged.setdefault(key, {
            "title": title, "start": start, "end": end or start, "day": first, "last": last, "ids": [], "calendars": [], "said": set(),
            "others": {}, "names": set(), "organizer": False, "optional": False, "description": "", "cancelled": True,
            "type": str(entry.get("eventType") or "").lower(), "free": str(entry.get("transparency") or "").lower() == "transparent"})
        record["ids"] += [str(entry[k]) for k in ("id", "iCalUID") if entry.get(k) and str(entry[k]) not in record["ids"]]
        record["calendars"] += [str(entry["calendar"])] if entry.get("calendar") and entry["calendar"] not in record["calendars"] else []
        record["said"] |= {ANSWERS.get(re.sub(r"[\s_-]", "", str(p.get("responseStatus") or "")).lower(),
                                       f"other:{p.get('responseStatus')}") for p in me}
        record["others"].update({str(p.get("email") or p.get("displayName")).lower(): str(p.get("displayName") or p.get("email"))
                                 for p in people if p not in me and not p.get("resource") and (p.get("email") or p.get("displayName"))})
        record["names"] |= {str(p["displayName"]).strip() for p in me if str(p.get("displayName") or "").strip()}
        record["organizer"] |= mine(entry.get("organizer"), addresses) or any(p.get("organizer") is True for p in me)
        record["optional"] |= any(p.get("optional") is True for p in me)
        record["cancelled"] &= str(entry.get("status") or "").lower() == "cancelled"
        record["description"] = max(record["description"], str(entry.get("description") or ""), key=len)
    return sorted(merged.values(), key=lambda r: (r["start"] or datetime.combine(day, time.min, zone), r["title"]))


def classify(record: dict, now: datetime, hold: str, markers: list):
    """(group, why) for one meeting: brief, unclear, declined, holds, ended or not_meetings."""
    marked = next((m for m in markers if re.search(rf"(?i)(?<!\w){re.escape(m)}(?!\w)", record["title"])), None)
    if record["cancelled"]:
        return "not_meetings", "cancelled"
    if record["type"] in NOT_MEETINGS:
        return "not_meetings", NOT_MEETINGS[record["type"]]
    if is_hold(record["title"], hold):
        return "holds", ""
    if marked or not record["others"]:
        return "not_meetings", f"the principal's own ({marked})" if marked else "no one else on it"
    if record["start"] is None and record["free"]:
        return "not_meetings", "all day, shown as free"
    answer = combine(record["said"], record["organizer"])
    if answer == "declined":
        return "declined", ""
    if record["start"] is not None and record["end"] <= now:
        return "ended", ""
    if answer == "accepted":
        return "brief", ""
    return "unclear", WHY.get(answer) or f"answered {str(answer).split(':', 1)[-1]}"


def packs_of(folder: Path, day: date) -> list:
    """The prep packs of the day, by their file's name: `YYYY-MM-DD-HHMM-slug.md` or `YYYY-MM-DD-slug-prep.md`."""
    if not folder.is_dir():
        stop(f"the packs folder {folder} is not a folder: name the workspace's folder of prep packs, or make it first")
    packs = []
    for path in sorted(folder.rglob(f"{day.isoformat()}-*.md")):
        name = PACK.match(path.name)
        if not name or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            stop(f"the pack {path} cannot be read ({exc}): a pack that cannot be read cannot be refreshed, and another "
                 "written beside it would lose it")
        head = {key: (rule.search(text) or [None, ""])[1].strip() for key, rule in HEADER.items()}
        clock = CLOCK.search(head["When"])
        hour = clock and (int(clock[1]) % 12 + 12 * (clock[3].lower() == "p") if clock[3] else int(clock[1]))
        briefed = re.match(r"(\d{4}-\d{2}-\d{2})(?:[ T](\d{1,2}:\d{2}))?", head["Briefed"])
        packs.append({"path": path, "slug": name[4], "title": norm(next((line[2:] for line in text.splitlines()
                                                                        if line.startswith("# ")), "")),
                      "event": head["Event"].split()[0].strip("`") if head["Event"] else "", "briefed": briefed and briefed.groups(),
                      "at": f"{name[2]}:{name[3]}" if name[2] else clock and f"{hour:02d}:{clock[2]}"})
    return packs


def assign(briefs: list, packs: list, folder: Path, day: date) -> list:
    """Give each meeting to brief its pack (by the pack's Event line, then by title or file name at the same start,
    then at another start, which says it moved), or the path its brief is written at; the packs left over."""
    left = list(packs)
    for rank in range(3):
        for b in briefs:
            same = [p for p in left if not b.get("pack") and (p["event"] in b["ids"] if rank == 0 else (
                p["title"] == norm(b["title"]) or p["slug"] == slug(b["title"])) and (rank == 2 or p["at"] in (b["at"], None)))]
            if same:
                left.remove(same[0])
                b["pack"] = same[0]
    written = set()
    for b in briefs:
        found = b.pop("pack", None)
        moved = found and found["at"] and b["at"] and found["at"] != b["at"]
        if found:
            today = found["briefed"] and found["briefed"][0] == day.isoformat() and not moved
            b["pack"] = {"action": "briefed" if today else "refresh", "path": str(found["path"]),
                         "briefed": (found["briefed"][1] or "") if today else None, "moved": moved and (
                             f"the pack says {found['at']} and the calendar {b['at']}") or None}
            continue
        stem = f"{day.isoformat()}-" + (b["at"].replace(":", "") + "-" if b["at"] else "") + slug(b["title"])
        name = next(f"{stem}{n}.md" for n in [""] + [f"-{i}" for i in range(2, 99)]
                    if f"{stem}{n}" not in written and not (folder / f"{stem}{n}.md").exists())  # never over a file there
        written.add(name[:-3])
        b["pack"] = {"action": "write", "path": str(folder / name), "briefed": None, "moved": None}
    return left


def judge(args, read, prefs: dict) -> dict:
    guardian = prefs.get("calendar_guardian") if isinstance(prefs.get("calendar_guardian"), dict) else {}
    holds = guardian.get("holds") if isinstance(guardian.get("holds"), dict) else {}
    hold, markers = str(holds.get("title") or "Hold"), [str(m) for m in guardian.get("personal_markers") or [] if str(m).strip()]
    addresses = [str(a).strip().lower() for a in prefs.get("principal_addresses") or [] if str(a).strip()]
    try:
        zone = ZoneInfo(str(prefs["timezone"])) if prefs.get("timezone") else datetime.now().astimezone().tzinfo
        now = datetime.fromisoformat(args.now) if args.now else datetime.now(zone)
    except (KeyError, ValueError) as exc:  # a zone the system does not know, or a --now that is no time
        stop(f"the time zone or --now cannot be read ({exc!r})")
    now = now.astimezone(zone) if now.tzinfo else now.replace(tzinfo=zone)
    day = now.date()
    if not isinstance(read, dict):
        stop("the calendar read is not one JSON object: today's meetings are unknown, which is a gap, not a day without meetings")
    try:
        if not date.fromisoformat(str(read["window"]["from"])[:10]) <= day <= date.fromisoformat(str(read["window"]["through"])[:10]):
            stop(f"the calendar read does not cover {day}: read the calendars for today and save the read again")
    except (TypeError, KeyError, ValueError):
        stop('the calendar read must say which days it covers: {"window": {"from": ..., "through": ...}}')
    calendars = read.get("calendars")
    if not isinstance(calendars, list) or not calendars or not all(isinstance(c, dict) and c.get("id") for c in calendars):
        stop('the calendar read does not say which calendars it covers: list each one the workspace owns, '
             '{"id": ..., "read": true}, or "read": false with the "error" its connector gave')
    if not isinstance(read.get("events"), list) or not all(isinstance(e, dict) for e in read["events"]):
        stop('the calendar read\'s "events" is not a list of entries: save the read again')
    selves = [p for e in read["events"] for p in [*(e.get("attendees") or []), e.get("organizer")] if isinstance(p, dict) and p.get("self") is True]
    if not (addresses or selves) and any(e.get("attendees") for e in read["events"]):
        stop("no attendee in the read is marked as the principal (`self`) and the preferences give no principal_addresses, "
             "so whose attendance this is cannot be told")
    records = read_events(read, zone, day, addresses)
    names = {n.strip() for n in args.name if n.strip()} | {n for r in records for n in r["names"]}
    known = names | {a for a in addresses if not re.search(r"[*?\[]", a)} | {str(p.get("email")).lower() for p in selves if p.get("email")}
    spoken = [re.compile(rf"(?i)(?<!\w){re.escape(n)}(?!\w)") for n in sorted(known)]  # the principal, as a line names them
    result = {"date": day.isoformat(), "now": now.isoformat(), "timezone": str(zone),
              "calendars": {"read": [str(c["id"]) for c in calendars if c.get("read") is True],
                            "not_read": [{"id": str(c["id"]), "why": str(c.get("error") or c.get("why") or "").strip()}
                                         for c in calendars if c.get("read") is not True]},
              "brief": [], "unclear": [], "declined": [], "holds": [], "ended": [], "not_meetings": []}
    for record in records:
        group, why = classify(record, now, hold, markers)
        at = record["start"] and record["start"].strftime("%H:%M")
        shown = {"title": record["title"], "start": (record["start"] or record["day"]).isoformat(),
                 "end": (record["end"] or record["last"]).isoformat(), "all_day": record["start"] is None, "at": at,
                 "until": record["end"] and record["end"].strftime("%H:%M"), "ids": record["ids"], "calendars": record["calendars"]}
        if group != "brief":
            result[group].append({**shown, **({"why": why} if why else {})})
            continue
        text = plain(record["description"])
        agenda = agenda_of(text)
        presents = any(m.search(line) for m in spoken for line in agenda) or any(
            m.search(line) and PRESENTING.search(line) for m in spoken for line in text.splitlines())
        result["brief"].append({**shown, "organizer": record["organizer"], "optional": record["optional"], "presents": presents,
                                "under_way": bool(record["start"] and record["start"] <= now), "agenda": agenda,
                                "links": links_of(record["description"]), "people": sorted(record["others"].values())})
    left = assign(result["brief"], packs_of(Path(args.packs), day), Path(args.packs), day)
    result["packs_unmatched"] = []
    for pack in left:
        twin = next((b for b in result["brief"] if pack["title"] == norm(b["title"]) or pack["slug"] == slug(b["title"])), None)
        other = next(((g, e) for g in STATE for e in result[g] if pack["event"] in e["ids"] or pack["title"] == norm(e["title"])
                      or pack["slug"] == slug(e["title"])), None)
        result["packs_unmatched"].append({"path": str(pack["path"]), "why": (
            f"a second pack for {twin['title']}, whose brief is {twin['pack']['path']}" if twin else
            f"no meeting to brief has it ({other[1]['title']} is {STATE[other[0]]})" if other else "no meeting today has its title")})
    result["first"] = next((b for b in result["brief"] if b["pack"]["action"] != "briefed"), None)
    result["clean"] = not result["calendars"]["not_read"]
    return result


def report(result: dict) -> list:
    """The text form: the earliest meeting to brief first, then each gap, each brief and each line apart."""
    read, gaps, briefs = result["calendars"]["read"], result["calendars"]["not_read"], result["brief"]
    of_read = f" (on the calendars read; {len(gaps)} not read)" if gaps else ""
    first = result["first"]
    if first and first["all_day"]:
        lines = [f"first: all day {first['title']}: brief it and surface it now{of_read}"]
    elif first:
        lines = [f"first: {first['at']} {first['title']}: " + (f"under way until {first['until']}; brief it now" if first["under_way"]
                                                               else f"brief it and surface it before {first['at']}") + of_read]
    elif briefs:
        lines = [f"first: none left: every meeting to brief is briefed, the earliest at {briefs[0]['at'] or 'all day'}{of_read}"]
    elif gaps:
        lines = [f"first: none on the calendars read; {len(gaps)} not read, so today's meetings are unknown, not none"]
    else:
        lines = [f"first: none: no meeting to brief today; calendars read {len(read)} of {len(read)}"]

    def entry(word: str, e: dict) -> str:
        return f"{word:<13} " + (f"{e['at']}-{e['until']}" if e["at"] else "all day") + f" {e['title']}"
    lines += [f"{'GAP':<13} {g['id']}: not read" + (f" ({g['why']})" if g["why"] else "") + "; its meetings today are unknown, "
              "not none, and this day-start is not clean until it is read" for g in gaps]
    for b in briefs:
        role = ", ".join(r for r in ("organizer", "optional", "presents") if b[r]) or "attendee"
        pack = b["pack"]
        lines.append(entry("BRIEF", b) + f" · {role} · {pack['action']} {pack['path']}"
                     + (f" at {pack['briefed']}" if pack["briefed"] else "") + (f"; moved: {pack['moved']}" if pack["moved"] else ""))
        lines += [" " * 14 + f"agenda: {line}" for line in b["agenda"]] or [" " * 14 + "agenda: none in the invitation"]
        lines += [" " * 14 + f"link: {link}" for link in b["links"]]
    for word, group in GROUPS:
        lines += [entry(word, e) + (f": {e['why']}" if e.get("why") else "") for e in result[group]]
    lines += [f"{'PACK':<13} {p['path']}: {p['why']}" for p in result["packs_unmatched"]]
    count = {a: sum(b["pack"]["action"] == a for b in briefs) for a in ("briefed", "refresh", "write")}
    lines.append(f"meetings on {date.fromisoformat(result['date']):%a %Y-%m-%d}: to brief {len(briefs)} (briefed {count['briefed']}, "
                 f"refresh {count['refresh']}, write {count['write']}), " + ", ".join(
                     f"{name} {len(result[group])}" for name, group in (("unclear", "unclear"), ("declined", "declined"),
                                                                       ("holds", "holds"), ("ended", "ended"),
                                                                       ("not meetings", "not_meetings")))
                 + f"; calendars read {len(read)} of {len(read) + len(gaps)}" + (f", not read {len(gaps)}" if gaps else ""))
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--events", required=True, type=Path, help="the saved calendar read, with its window and calendars")
    parser.add_argument("--packs", required=True, help="the workspace's folder of prep packs (meeting-preps/)")
    parser.add_argument("--name", action="append", default=[], help="the principal's name as agendas write it; repeat it")
    parser.add_argument("--config", type=Path, help="the principal's preferences (default ~/.synthesis/chief-of-staff/preferences.json)")
    parser.add_argument("--now", help="YYYY-MM-DDTHH:MM in the principal's zone; defaults to now")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    config = args.config or Path.home() / ".synthesis" / "chief-of-staff" / "preferences.json"
    prefs = {}
    if args.config or config.exists():
        try:
            prefs = json.loads(config.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            stop(f"the preferences {config} cannot be read ({exc})")
        if not isinstance(prefs, dict):
            stop(f"the preferences {config} are not one JSON object")
    try:
        read = json.loads(args.events.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        stop(f"the calendar read {args.events} cannot be read ({exc}): today's meetings are unknown, which is a gap, "
             "not a day without meetings")
    result = judge(args, read, prefs)
    print(json.dumps(result, indent=2, default=str) if args.json else "\n".join(report(result)))
    return 2 if result["calendars"]["not_read"] else 1 if result["unclear"] else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit as exc:
        if isinstance(exc.code, str):
            print(exc.code, file=sys.stderr)
            sys.exit(2)
        raise
    except Exception as exc:  # noqa: BLE001  a read it cannot make sense of was not shown enough: never 0 or 1
        print(f"meeting_briefs: this read could not be judged ({exc!r})", file=sys.stderr)
        sys.exit(2)
