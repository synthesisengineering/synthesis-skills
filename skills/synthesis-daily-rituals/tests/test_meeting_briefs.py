"""Every meeting the principal plans to attend is briefed at day-start, the earliest first and each before it starts.

The principal asked on 2026-11-20 that same-day meeting prep be a standard, required step of the day-start: the
v2.12.0 meeting-prep step was optional, and day-end prepares only the meetings a workspace flags for lead time.
`meeting_briefs.py` reads the day's calendar read and the workspace's folder of prep packs and says which meetings to
brief (accepted ones, accepted optional ones included, with the principal's part and the invitation's agenda), which
existing pack each refreshes, what stands apart unbriefed (declined meetings, holds, unclear attendance, entries that
are no meeting), and each calendar the read could not cover, as a gap that blocks a clean day-start and never as a
day without meetings. The earliest meeting to brief is named first, with its start. Every meeting here is invented.
Committed before the script.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "meeting_briefs.py"
SKILL = SCRIPT.parents[1]
DAY = "2026-11-24"  # a Tuesday
NOW = f"{DAY}T07:45"
PREFS = {"timezone": "America/New_York", "principal_addresses": ["pat@example.com", "pat@example.org"],
         "calendar_guardian": {"holds": {"title": "Hold"}, "personal_markers": ["#reserved"]}}
READ = [{"id": "pat@example.com", "read": True}]
GAP_TEXT = "its meetings today are unknown, not none, and this day-start is not clean until it is read"


def at(hhmm: str) -> dict:
    return {"dateTime": f"{DAY}T{hhmm}:00-05:00", "timeZone": "America/New_York"}


def me(answer: str = "accepted", **more) -> dict:
    return {"email": "pat@example.com", "displayName": "Pat Example", "self": True, "responseStatus": answer, **more}


def guest(name: str, answer: str = "accepted", **more) -> dict:
    return {"email": f"{name.split()[0].lower()}@example.net", "displayName": name, "responseStatus": answer, **more}


def event(ident: str, title: str, start: str, end: str, *attendees: dict, **more) -> dict:
    return {"id": ident, "summary": title, "start": at(start), "end": at(end), "attendees": list(attendees),
            "calendar": "pat@example.com", **more}


def day_read(*events: dict, calendars=None) -> dict:
    return {"window": {"from": DAY, "through": DAY}, "calendars": READ if calendars is None else calendars, "events": list(events)}


ROADMAP_INVITATION = (
    "<p>The quarter's roadmap with the product leads.</p>"
    "<p><b>Agenda</b><br>1. Welcome and goals (Jordan Rivers, 5 min)<br>"
    "2. Q1 roadmap proposal: Pat Example presents (20 min)<br>"
    "3. Budget ask: a decision on the two added roles (15 min)<br>4. Questions</p>"
    '<p>Deck: <a href="https://docs.example.com/d/q1-roadmap">Q1 roadmap deck</a></p>'
    "<p>-::~:~::~:~:~:~:~:~:~:~:~:~:~::~:~::-<br>Join with Google Meet: https://meet.google.com/abc-defg-hij</p>")
ROADMAP_AGENDA = ["1. Welcome and goals (Jordan Rivers, 5 min)", "2. Q1 roadmap proposal: Pat Example presents (20 min)",
                  "3. Budget ask: a decision on the two added roles (15 min)", "4. Questions"]
ONE_ON_ONE = event("e2", "Pat / Jordan 1:1", "09:00", "09:30", me(), guest("Jordan Rivers"))
ROADMAP = event("e3", "Quarterly roadmap review", "10:00", "11:00", me(), guest("Jordan Rivers"), guest("Sam Taylor"),
                organizer={"email": "sam@example.net"}, description=ROADMAP_INVITATION)
MIXED = day_read(
    event("e1", "Focus: budget memo", "08:00", "08:30"),                                       # no one else on it
    ONE_ON_ONE,                                                                                # the earliest to brief
    ROADMAP,                                                                                   # presents; a lead-time pack
    event("e4", "Architecture forum", "11:30", "12:00", me(optional=True), guest("Riley Chen")),  # accepted, optional
    event("e5", "Hold", "12:00", "13:00"),                                                     # the shield's hold
    event("e6", "Vendor demo: analytics suite", "13:00", "13:30", me("declined"), guest("Casey Morgan")),
    event("e7", "Hiring sync", "14:00", "14:30", me("needsAction"), guest("Jordan Rivers")),
    event("e8", "Offsite planning", "15:00", "16:00", me("tentative"), guest("Sam Taylor")),
    event("e9", "HOLD: partner kickoff", "16:00", "16:30", me(), guest("Dana Fox")),            # a counterpart's placeholder
    {"id": "e10", "summary": "Working from home", "start": {"date": DAY}, "end": {"date": "2026-11-25"},
     "eventType": "workingLocation"},
    calendars=[*READ, {"id": "pat@example.org", "read": False, "error": "the connector's sign-in expired"}])
LEAD_PACK = ("# Quarterly roadmap review\n**When:** 2026-11-24 10:00-11:00\n**Who:** Jordan Rivers, Sam Taylor\n\n"
             "Built at day-end from the last review's transcript.\n")


def write_packs(folder: Path, packs: dict) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in packs.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text, encoding="utf-8")
    return folder


def run(tmp_path: Path, read, *args: str, packs=None, prefs=PREFS, now: str = NOW):
    """The script over a read (None: no file there) and a folder of packs, in a home of its own and the principal's
    zone: preferences only where the test gives them."""
    events = tmp_path / "today.json"
    if read is not None:
        events.write_text(read if isinstance(read, str) else json.dumps(read), encoding="utf-8")
    folder = write_packs(tmp_path / "meeting-preps", {}) if packs is None else packs
    config = []
    if prefs is not None:
        (tmp_path / "preferences.json").write_text(prefs if isinstance(prefs, str) else json.dumps(prefs), encoding="utf-8")
        config = ["--config", str(tmp_path / "preferences.json")]
    done = subprocess.run([sys.executable, str(SCRIPT), "--events", str(events), "--packs", str(folder), *config,
                           "--now", now, *args], capture_output=True, text=True,
                          env={**os.environ, "HOME": str(tmp_path / "home"), "TZ": "America/New_York"})
    return done.returncode, done.stdout, done.stderr


def lines_of(tmp_path: Path, read, *args: str, **kwargs):
    code, out, err = run(tmp_path, read, *args, **kwargs)
    return code, out.splitlines(), err


def json_of(tmp_path: Path, read, *args: str, **kwargs):
    code, out, err = run(tmp_path, read, "--json", *args, **kwargs)
    assert out.strip().startswith("{"), err
    return code, json.loads(out)


# ---- the mixed day ----------------------------------------------------------------------------------------------

def test_a_mixed_day_briefs_what_the_principal_attends_and_names_everything_else_apart(tmp_path):
    """The case the request named: a presenter's agenda, an accepted optional meeting, a lead-time pack to refresh,
    a decline, two holds, two unclear answers, the principal's own time, and a calendar that could not be read."""
    packs = write_packs(tmp_path / "meeting-preps", {
        "2026-11-24-1000-quarterly-roadmap-review.md": LEAD_PACK,
        "2026-11-24-1300-vendor-demo-analytics-suite.md": "# Vendor demo: analytics suite\n**When:** 2026-11-24 13:00\n",
        "2026-11-23-0900-pat-jordan-1-1.md": "# Pat / Jordan 1:1\n**When:** 2026-11-23 09:00\n",  # yesterday's
        "README.md": "# Prep packs\n"})
    code, lines, err = lines_of(tmp_path, MIXED, packs=packs)
    p = str(packs)
    assert (code, err) == (2, "")
    assert lines == [
        "first: 09:00 Pat / Jordan 1:1: brief it and surface it before 09:00 (on the calendars read; 1 not read)",
        f"GAP           pat@example.org: not read (the connector's sign-in expired); {GAP_TEXT}",
        f"BRIEF         09:00-09:30 Pat / Jordan 1:1 · attendee · write {p}/2026-11-24-0900-pat-jordan-1-1.md",
        "              agenda: none in the invitation",
        f"BRIEF         10:00-11:00 Quarterly roadmap review · presents · refresh {p}/2026-11-24-1000-quarterly-roadmap-review.md",
        *[f"              agenda: {line}" for line in ROADMAP_AGENDA],
        "              link: https://docs.example.com/d/q1-roadmap",
        f"BRIEF         11:30-12:00 Architecture forum · optional · write {p}/2026-11-24-1130-architecture-forum.md",
        "              agenda: none in the invitation",
        "UNCLEAR       14:00-14:30 Hiring sync: invited, not answered",
        "UNCLEAR       15:00-16:00 Offsite planning: answered maybe",
        "DECLINED      13:00-13:30 Vendor demo: analytics suite",
        "HOLD          12:00-13:00 Hold",
        "HOLD          16:00-16:30 HOLD: partner kickoff",
        "NOT A MEETING all day Working from home: working location",
        "NOT A MEETING 08:00-08:30 Focus: budget memo: no one else on it",
        f"PACK          {p}/2026-11-24-1300-vendor-demo-analytics-suite.md: no meeting to brief has it "
        "(Vendor demo: analytics suite is declined)",
        "meetings on Tue 2026-11-24: to brief 3 (briefed 0, refresh 1, write 2), unclear 2, declined 1, holds 2, ended 0, "
        "not meetings 2; calendars read 1 of 2, not read 1"]
    assert not list(packs.glob("2026-11-24-0900-*")), "the script writes nothing: the brief is the agent's to write"


def test_the_mixed_day_as_json_carries_each_part_the_brief_is_built_from(tmp_path):
    packs = write_packs(tmp_path / "meeting-preps", {"2026-11-24-1000-quarterly-roadmap-review.md": LEAD_PACK})
    code, result = json_of(tmp_path, MIXED, packs=packs)
    assert code == 2 and result["clean"] is False and result["date"] == DAY
    assert result["calendars"] == {"read": ["pat@example.com"],
                                   "not_read": [{"id": "pat@example.org", "why": "the connector's sign-in expired"}]}
    first, roadmap, forum = result["brief"]
    assert result["first"] == first and (first["title"], first["at"], first["start"]) == (
        "Pat / Jordan 1:1", "09:00", "2026-11-24T09:00:00-05:00")
    assert (roadmap["presents"], roadmap["organizer"], roadmap["optional"]) == (True, False, False)
    assert roadmap["agenda"] == ROADMAP_AGENDA and roadmap["links"] == ["https://docs.example.com/d/q1-roadmap"]
    assert roadmap["people"] == ["Jordan Rivers", "Sam Taylor"] and roadmap["ids"] == ["e3"]
    assert roadmap["pack"] == {"action": "refresh", "path": str(packs / "2026-11-24-1000-quarterly-roadmap-review.md"),
                               "briefed": None, "moved": None}
    assert (forum["optional"], forum["presents"], forum["pack"]["action"]) == (True, False, "write")
    assert [(e["title"], e["why"]) for e in result["unclear"]] == [("Hiring sync", "invited, not answered"),
                                                                  ("Offsite planning", "answered maybe")]
    assert [e["title"] for e in result["declined"]] == ["Vendor demo: analytics suite"]
    assert [e["title"] for e in result["holds"]] == ["Hold", "HOLD: partner kickoff"]
    assert [(e["title"], e["why"]) for e in result["not_meetings"]] == [("Working from home", "working location"),
                                                                       ("Focus: budget memo", "no one else on it")]
    assert result["ended"] == [] and result["packs_unmatched"] == []


# ---- coverage: a calendar not read is a gap, never a day without meetings ----------------------------------------

def test_a_read_in_which_no_calendar_was_read_is_a_gap_and_never_no_meetings(tmp_path):
    code, lines, _ = lines_of(tmp_path, day_read(calendars=[{"id": "pat@example.com", "read": False, "error": "timed out"}]))
    assert code == 2
    assert lines[0] == "first: none on the calendars read; 1 not read, so today's meetings are unknown, not none"
    assert lines[1] == f"GAP           pat@example.com: not read (timed out); {GAP_TEXT}"
    assert lines[-1].endswith("calendars read 0 of 1, not read 1")
    assert not any("no meeting" in line for line in lines)


def test_a_calendar_whose_read_is_not_stated_was_not_read(tmp_path):
    code, lines, _ = lines_of(tmp_path, day_read(ONE_ON_ONE, calendars=[*READ, {"id": "pat@example.org"}]))
    assert code == 2 and f"GAP           pat@example.org: not read; {GAP_TEXT}" in lines


def test_a_whole_read_with_nothing_to_brief_says_so_with_its_denominator(tmp_path):
    code, lines, _ = lines_of(tmp_path, day_read(event("e1", "Focus: budget memo", "08:00", "08:30")))
    assert code == 0 and lines[0] == "first: none: no meeting to brief today; calendars read 1 of 1"


def test_a_day_with_every_calendar_read_exits_0_and_unclear_attendance_alone_exits_1(tmp_path):
    code, lines, _ = lines_of(tmp_path, day_read(ONE_ON_ONE, ROADMAP))
    assert code == 0 and lines[0] == "first: 09:00 Pat / Jordan 1:1: brief it and surface it before 09:00"
    unanswered = event("e7", "Hiring sync", "14:00", "14:30", me("needsAction"), guest("Jordan Rivers"))
    code, lines, _ = lines_of(tmp_path, day_read(ONE_ON_ONE, unanswered))
    assert code == 1 and "UNCLEAR       14:00-14:30 Hiring sync: invited, not answered" in lines


# ---- unreadable input is refused, and nothing is judged ---------------------------------------------------------

def broken(tmp_path: Path, case: str):
    """(read, keyword arguments of run, words the refusal says) for each way an input cannot be read."""
    good = day_read(ONE_ON_ONE)
    return {
        "no read": (None, {}, "cannot be read"),
        "not json": ("{calendars", {}, "cannot be read"),
        "a list": ([good], {}, "not one JSON object"),
        "no window": ({**good, "window": None}, {}, "which days it covers"),
        "another day": ({**good, "window": {"from": "2026-11-23", "through": "2026-11-23"}}, {}, "does not cover 2026-11-24"),
        "no calendars": ({k: v for k, v in good.items() if k != "calendars"}, {}, "which calendars it covers"),
        "empty calendars": ({**good, "calendars": []}, {}, "which calendars it covers"),
        "events not a list": ({**good, "events": {"e2": ONE_ON_ONE}}, {}, "not a list of entries"),
        "a start that is no time": (day_read({**ONE_ON_ONE, "start": {"dateTime": "nine o'clock"}}), {}, "no date or time"),
        "attendees not a list": (day_read({**ONE_ON_ONE, "attendees": "Pat, Jordan"}), {}, "not a list of people"),
        "no packs folder": (good, {"packs": tmp_path / "missing"}, "is not a folder"),
        "a file for a folder": (good, {"packs": write_packs(tmp_path / "x", {"f.md": ""}) / "f.md"}, "is not a folder"),
        "a pack that is not text": (good, {"packs": write_packs(tmp_path / "bad", {})}, "cannot be read"),
        "no preferences": (good, {"prefs": "{not json"}, "preferences"),
        "preferences not an object": (good, {"prefs": "[1]"}, "not one JSON object"),
        "a zone that is none": (good, {"prefs": {**PREFS, "timezone": "Mars/Olympus_Mons"}}, "time zone"),
        "addresses not a list": (good, {"prefs": {**PREFS, "principal_addresses": "pat@example.com"}}, "a list"),
        "a marker that is a word": (good, {"prefs": {**PREFS, "calendar_guardian": {"personal_markers": ["training"]}}},
                                    "plain word"),  # it would hide "Training with the team", as slot_check.py refuses
        "a now that is no time": (good, {"now": "soon"}, "time zone or --now"),
    }[case]


@pytest.mark.parametrize("case", ["no read", "not json", "a list", "no window", "another day", "no calendars",
                                  "empty calendars", "events not a list", "a start that is no time", "attendees not a list",
                                  "no packs folder", "a file for a folder", "a pack that is not text", "no preferences",
                                  "preferences not an object", "a zone that is none", "a now that is no time",
                                  "addresses not a list", "a marker that is a word"])
def test_an_input_that_cannot_be_read_is_refused_and_nothing_is_judged(tmp_path, case):
    read, kwargs, says = broken(tmp_path, case)
    if case == "a pack that is not text":
        (kwargs["packs"] / "2026-11-24-0900-pat-jordan-1-1.md").write_bytes(b"# Pat / Jordan 1:1\n\xff\xfe\n")
    code, out, err = run(tmp_path, read, **kwargs)
    assert (code, out) == (2, ""), (case, out, err)
    assert len(err.strip().splitlines()) == 1 and err.startswith("meeting_briefs: ") and says in err, (case, err)
    assert "Traceback" not in err


def test_a_read_that_cannot_say_who_the_principal_is_is_refused(tmp_path):
    """No attendee marked `self` and no address in the preferences: every meeting would read as one the principal is
    not on, so nothing is judged."""
    anonymous = event("e2", "Pat / Jordan 1:1", "09:00", "09:30", {"email": "pat@example.com", "responseStatus": "accepted"},
                      guest("Jordan Rivers"))
    code, out, err = run(tmp_path, day_read(anonymous), prefs={"timezone": "America/New_York"})
    assert (code, out) == (2, "") and "cannot be told" in err
    code, lines, _ = lines_of(tmp_path, day_read(anonymous))  # the preferences' address says who the principal is
    assert code == 0 and lines[0].startswith("first: 09:00 Pat / Jordan 1:1")


def test_missing_preferences_at_the_default_place_leave_the_self_mark_to_say_who_the_principal_is(tmp_path):
    """No preferences file in the home: the `self` mark says who the principal is, and the machine's zone tells time."""
    code, lines, _ = lines_of(tmp_path, day_read(ONE_ON_ONE), prefs=None, now=f"{DAY}T07:45-05:00")
    assert code == 0 and lines[0] == "first: 09:00 Pat / Jordan 1:1: brief it and surface it before 09:00"


# ---- packs: refresh what exists, never write a second -------------------------------------------------------------

def test_a_pack_built_for_another_time_is_refreshed_and_the_move_is_named(tmp_path):
    packs = write_packs(tmp_path / "meeting-preps", {
        "2026-11-24-0900-exec-weekly.md": "# Exec weekly\n**When:** 2026-11-24 09:00-10:00\n"})
    moved = event("e11", "Exec weekly", "10:00", "11:00", me(), guest("Jordan Rivers"))
    code, lines, _ = lines_of(tmp_path, day_read(moved), packs=packs)
    assert code == 0 and lines[1] == (f"BRIEF         10:00-11:00 Exec weekly · attendee · refresh {packs}/2026-11-24-0900-exec-weekly.md"
                                      "; moved: the pack says 09:00 and the calendar 10:00")


def test_a_brief_written_today_reads_as_briefed_and_the_next_meeting_is_first(tmp_path):
    packs = write_packs(tmp_path / "meeting-preps", {
        "2026-11-24-0900-pat-jordan-1-1.md": "# Pat / Jordan 1:1\n**When:** 2026-11-24 09:00\n**Briefed:** 2026-11-24 07:58\n",
        "2026-11-24-1000-quarterly-roadmap-review.md": LEAD_PACK + "**Briefed:** 2026-11-23 18:10\n"})  # at last night's close
    code, lines, _ = lines_of(tmp_path, day_read(ONE_ON_ONE, ROADMAP), packs=packs)
    assert code == 0
    assert lines[0] == "first: 10:00 Quarterly roadmap review: brief it and surface it before 10:00"
    assert lines[1] == f"BRIEF         09:00-09:30 Pat / Jordan 1:1 · attendee · briefed {packs}/2026-11-24-0900-pat-jordan-1-1.md at 07:58"
    assert f"refresh {packs}/2026-11-24-1000-quarterly-roadmap-review.md" in lines[3]
    assert lines[-1].startswith("meetings on Tue 2026-11-24: to brief 2 (briefed 1, refresh 1, write 0)")
    (packs / "2026-11-24-1000-quarterly-roadmap-review.md").write_text(LEAD_PACK + "**Briefed:** 2026-11-24 08:20\n", encoding="utf-8")
    code, lines, _ = lines_of(tmp_path, day_read(ONE_ON_ONE, ROADMAP), packs=packs)
    assert lines[0] == "first: none left: every meeting to brief is briefed, the earliest at 09:00"


def test_a_pack_is_found_by_its_event_line_or_its_title_and_a_second_pack_is_named(tmp_path):
    packs = write_packs(tmp_path / "meeting-preps", {
        "2026-11-24-0900-jordan.md": "# Jordan, weekly\n**When:** 09:00\n**Event:** `e2`\n",            # renamed, same event
        "2026-11-24-quarterly-roadmap-review-prep.md": "# Prep: Quarterly roadmap review\n**When:** 10:00 am\n",
        "2026-11-24-1000-quarterly-roadmap-review.md": LEAD_PACK,
        "2026-11-24-1500-board-dinner.md": "# Board dinner\n"})
    code, result = json_of(tmp_path, day_read(ONE_ON_ONE, ROADMAP), packs=packs)
    assert [b["pack"]["path"] for b in result["brief"]] == [str(packs / "2026-11-24-0900-jordan.md"),
                                                            str(packs / "2026-11-24-1000-quarterly-roadmap-review.md")]
    assert result["packs_unmatched"] == [
        {"path": str(packs / "2026-11-24-1500-board-dinner.md"), "why": "no meeting today has its title"},
        {"path": str(packs / "2026-11-24-quarterly-roadmap-review-prep.md"),
         "why": f"a second pack for Quarterly roadmap review, whose brief is {packs}/2026-11-24-1000-quarterly-roadmap-review.md"}]


def test_a_new_brief_never_lands_on_a_file_already_there(tmp_path):
    packs = write_packs(tmp_path / "meeting-preps", {"2026-11-24-0900-sync.md": "# Sync\n**When:** 09:00\n"})
    one = event("s1", "Sync", "09:00", "09:30", me(), guest("Jordan Rivers"), iCalUID="one@example.net")
    two = event("s2", "Sync", "09:00", "09:30", me(), guest("Sam Taylor"), iCalUID="two@example.net")
    code, result = json_of(tmp_path, day_read(one, two), packs=packs)
    assert [(b["pack"]["action"], Path(b["pack"]["path"]).name) for b in result["brief"]] == [
        ("refresh", "2026-11-24-0900-sync.md"), ("write", "2026-11-24-0900-sync-2.md")]


# ---- what the principal's answer and the clock say -----------------------------------------------------------------

def test_a_meeting_over_is_not_briefed_and_one_under_way_is_first(tmp_path):
    code, lines, _ = lines_of(tmp_path, day_read(ONE_ON_ONE, ROADMAP), now=f"{DAY}T10:15")
    assert lines[0] == "first: 10:00 Quarterly roadmap review: under way until 11:00; brief it now"
    assert "ENDED         09:00-09:30 Pat / Jordan 1:1" in lines and not any("BRIEF         09:00" in line for line in lines)


def test_one_meeting_on_two_calendars_is_one_meeting(tmp_path):
    both = [{"id": "pat@example.com", "read": True}, {"id": "pat@example.org", "read": True}]
    work = event("w1", "Partner review", "13:00", "14:00", me(), guest("Dana Fox"), iCalUID="pr@example.net")
    home = {**work, "id": "h1", "calendar": "pat@example.org",
            "attendees": [{"email": "pat@example.org", "responseStatus": "needsAction"}, guest("Dana Fox")]}
    code, result = json_of(tmp_path, day_read(work, home, calendars=both))
    assert code == 0 and [(b["title"], b["ids"], b["calendars"]) for b in result["brief"]] == [
        ("Partner review", ["w1", "pr@example.net", "h1"], ["pat@example.com", "pat@example.org"])]
    declined = {**home, "attendees": [{"email": "pat@example.org", "responseStatus": "declined"}, guest("Dana Fox")]}
    code, result = json_of(tmp_path, day_read(work, declined, calendars=both))
    assert code == 1 and [(e["title"], e["why"]) for e in result["unclear"]] == [
        ("Partner review", "accepted on one calendar and declined on another")]


def test_the_principals_own_meeting_is_attended_and_one_they_are_not_on_is_unclear(tmp_path):
    own = event("o1", "Design review", "09:00", "10:00", guest("Jordan Rivers", "needsAction"),
                organizer={"email": "pat@example.com", "self": True})
    other = event("o2", "Team lunch", "12:00", "13:00", guest("Sam Taylor"), organizer={"email": "sam@example.net"})
    code, lines, _ = lines_of(tmp_path, day_read(own, other))
    assert code == 1
    assert lines[1].startswith("BRIEF         09:00-10:00 Design review · organizer · write ")
    assert "UNCLEAR       12:00-13:00 Team lunch: not among its attendees" in lines


def test_entries_that_are_no_meeting_are_named_with_why_and_a_busy_all_day_meeting_is_briefed(tmp_path):
    workshop = {"id": "a1", "summary": "Strategy workshop", "start": {"date": DAY}, "end": {"date": "2026-11-25"},
                "attendees": [me(), guest("Jordan Rivers")]}
    holiday = {**workshop, "id": "a2", "summary": "Office closed", "transparency": "transparent"}
    code, lines, _ = lines_of(tmp_path, day_read(
        workshop, holiday,
        event("n1", "Quarterly planning", "09:00", "10:00", me(), guest("Sam Taylor"), status="cancelled"),
        event("n2", "Out of office", "10:00", "12:00", eventType="outOfOffice"),
        event("n3", "Deep work", "13:00", "15:00", eventType="focusTime"),
        event("n4", "Coaching #reserved", "15:00", "16:00", me(), guest("Riley Chen")),
        event("n5", "[Hold] Offsite", "16:00", "17:00"),
        event("n6", "Hold for the board", "17:00", "17:30", me(), guest("Dana Fox")),
        event("n7", "Holdings review", "17:30", "18:00", me(), guest("Casey Morgan"))))
    assert lines[0] == "first: all day Strategy workshop: brief it and surface it now"
    assert lines[1].startswith("BRIEF         all day Strategy workshop · attendee · write ")
    assert any(line.startswith("BRIEF         17:30-18:00 Holdings review") for line in lines)
    assert [line for line in lines if line.startswith(("NOT A MEETING", "HOLD"))] == [
        "HOLD          16:00-17:00 [Hold] Offsite",
        "HOLD          17:00-17:30 Hold for the board",
        "NOT A MEETING all day Office closed: all day, shown as free",
        "NOT A MEETING 09:00-10:00 Quarterly planning: cancelled",
        "NOT A MEETING 10:00-12:00 Out of office: out of office",
        "NOT A MEETING 13:00-15:00 Deep work: focus time",
        "NOT A MEETING 15:00-16:00 Coaching #reserved: the principal's own (#reserved)"]


def test_the_principal_presents_where_the_agenda_or_a_presenting_line_names_them_and_a_mention_is_no_part(tmp_path):
    listed = event("p1", "Ops review", "09:00", "10:00", me(), guest("Sam Taylor"),
                   description="Agenda\n\n- Incidents (Sam)\n\n- Hiring plan (Pat)\n\nNotes:\nPat, please read the deck first.")
    named = event("p2", "Launch readiness", "10:00", "11:00", me(), guest("Sam Taylor"),
                  description="<ul><li>Presenter: Pat</li></ul>")
    mentioned = event("p3", "Budget sync", "11:00", "12:00", me(), guest("Sam Taylor"),
                      description="Pat, please read the deck first: https://docs.example.com/d/budget.")
    code, result = json_of(tmp_path, day_read(listed, named, mentioned), "--name", "Pat")
    assert [(b["title"], b["presents"]) for b in result["brief"]] == [
        ("Ops review", True), ("Launch readiness", True), ("Budget sync", False)]
    assert result["brief"][0]["agenda"] == ["- Incidents (Sam)", "- Hiring plan (Pat)"]
    assert result["brief"][2]["links"] == ["https://docs.example.com/d/budget"] and result["brief"][2]["agenda"] == []
    code, result = json_of(tmp_path, day_read(listed, named, mentioned))  # without the name, only "Pat Example" is theirs
    assert [b["presents"] for b in result["brief"]] == [False, False, False]


# ---- the rituals run it ---------------------------------------------------------------------------------------------

COMMAND = "python3 -s <rituals>/scripts/meeting_briefs.py --events"


def reference(name: str) -> str:
    return (SKILL / "references" / name).read_text(encoding="utf-8")


def step(text: str, number: str) -> str:
    return text.split(f"\n## {number}. ")[1].split("\n## ")[0]


def test_day_start_carries_the_required_step_right_after_step_1_with_the_earliest_brief_before_the_sync():
    """A mechanism nobody is told to run is not a control: the day-start's own checklist carries the step."""
    day_start = reference("day-start.md")
    assert day_start.index("\n## 1. ") < day_start.index("\n## 1a. ") < day_start.index("\n## 2. ")
    briefs = " ".join(step(day_start, "1a").split())
    for words in (COMMAND, "`first:`", "`GAP`", "unknown, not none", "synthesis-meeting-prep", "`**Purpose:**`",
                  "`**Decision or ask:**`", "`refresh <pack>`", "never write a second", "`**Briefed:**`", "`**Event:**`",
                  "private", "`UNCLEAR`", "`DECLINED`", "`HOLD`", "`## 📋 Prep packs`", "before its start", "before Step 2"):
        assert words in briefs, words
    assert COMMAND in step(day_start, "4"), "the rest are briefed after the catch-up read's calendar read"
    assert "meeting_briefs.py" in step(day_start, "6") and "`## 📋 Prep packs`" in step(day_start, "6")
    record = " ".join(step(day_start, "8").split())
    assert "`GAP`" in record and "--outcome partial" in record
    assert "1a Same-day meeting briefs" in day_start.split("\n## 1. ")[0]


def test_the_procedure_and_the_scripts_page_name_it():
    procedure = next(line for line in reference("procedure.md").splitlines() if line.startswith("**Day-start**"))
    assert "meeting_briefs.py" in procedure
    row = next((line for line in reference("scripts.md").splitlines()
                if line.startswith("| `python3 -s <rituals>/scripts/meeting_briefs.py --events")), "")
    for words in ("`first:", "`GAP", "`BRIEF`", "`UNCLEAR`", "`DECLINED`", "`HOLD`", "`PACK`", "| 0 ", "; 1 ", "; 2 "):
        assert words in row, words


def test_nothing_still_describes_same_day_prep_as_optional_without_pointing_at_the_required_step():
    history = reference("version-history-2.3-to-2.26.md")
    for heading in ("\n## v2.12.0 — ", "\n## v2.26.0 — "):
        assert "Step 1a" in history.split(heading)[1].split("\n## ")[0], heading
    lead_time = next(line for line in reference("day-end.md").splitlines() if "**Lead-time prep packs" in line)
    assert "Step 1a" in lead_time
    plan = reference("plan-format.md")
    assert "Step 1a" in plan.split("\n## ")[0] and "## 📋 Prep packs" in plan and "**Prep packs section**" in plan


def test_the_skill_binds_it():
    """SKILL.md's binding rules may be all a model reads after a compaction, so the step is bound there too."""
    rules = (SKILL / "SKILL.md").read_text(encoding="utf-8").split("## Binding rules")[1].split("## Contents")[0]
    rule = next((line for line in rules.splitlines() if "`meeting_briefs.py`" in line), "")
    assert rule.startswith("18. ") and "the earliest first" in rule and "never a day without meetings" in rule
