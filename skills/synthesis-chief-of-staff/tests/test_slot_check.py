"""The slot check: the verdict that goes with every time an agent proposes or places.

On 2026-11-09 a principal found a week of his open time filled with other people's requests:
a follow-up staged into the half hour after his leadership weekly, on the same day, three days
running, because the requester had suggested "tomorrow or Monday"; a demo in the first slot
three calendars shared, explained by the requester's "by Tuesday". His preferences already said
times are proposed on his terms. These tests pin the check that now runs before any time is
proposed: never today, a deep-work block kept, the day's load, placement beside existing
meetings, an existing touchpoint first, and a requester's deadline read as their preference.
Committed before the script.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "slot_check.py"
CONFIG = {
    "timezone": "America/New_York",
    "working_hours": {"start": "09:00", "end": "17:00"},
    "protected_hours": [{"start": "09:00", "end": "11:00", "label": "maker morning"}],
    "tiers": {"priority": ["chief@example.com", "*@board.example.com"], "peer": [], "vendor": []},
    "meeting_defaults": {"same_day_meetings": False},
    "calendar_guardian": {"thresholds": {"max_meeting_hours_per_day": 5, "min_maker_blocks_per_day": 1,
                                         "max_consecutive_meetings": 3, "maker_block_minutes": 120},
                          "holds": {"title": "Hold"}},
}
THURSDAY = "2026-11-12"


def meeting(day, start, end, summary="Sync", attendees=()):
    return {"start": f"{day}T{start}", "end": f"{day}T{end}", "summary": summary, "attendees": list(attendees)}


def check(tmp_path, start, end, events=(), *args, day=THURSDAY, today="2026-11-10", window=("2026-11-10", "2026-11-18"), config=CONFIG):
    prefs, read = tmp_path / "preferences.json", tmp_path / "events.json"
    if config is not None:
        prefs.write_text(json.dumps(config), encoding="utf-8")
    read.write_text(json.dumps({"window": {"from": window[0], "through": window[1]}, "events": list(events)} if window else list(events)),
                    encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPT), "--start", f"{day}T{start}", "--end", f"{day}T{end}", "--events", str(read),
                           "--config", str(prefs), "--today", today, "--json", *args], capture_output=True, text=True)
    return done.returncode, (json.loads(done.stdout) if done.stdout.strip().startswith("{") else done.stdout + done.stderr)


def levels(report) -> dict:
    return {c["check"]: c["level"] for c in report["checks"]}


def detail(report, name) -> str:
    return next(c["detail"] for c in report["checks"] if c["check"] == name)


QUIET_DAY = [meeting(THURSDAY, "13:00", "14:00", "Staff meeting")]


def test_a_slot_beside_an_existing_meeting_on_a_later_day_is_fine(tmp_path):
    code, got = check(tmp_path, "14:00", "14:30", QUIET_DAY, "--attendee", "a@example.com")
    assert code == 0 and got["verdict"] == "OK", got
    assert levels(got)["same day"] == "OK" and "Staff meeting" in detail(got, "placement")


def test_today_is_refused(tmp_path):
    code, got = check(tmp_path, "14:00", "14:30", QUIET_DAY, "--attendee", "a@example.com", today=THURSDAY)
    assert code == 1 and got["verdict"] == "REFUSE" and levels(got)["same day"] == "REFUSE"
    assert "unless the principal asks" in detail(got, "same day")


def test_today_is_allowed_for_someone_whose_timing_binds_or_when_the_config_allows_same_day(tmp_path):
    code, got = check(tmp_path, "14:00", "14:30", QUIET_DAY, "--attendee", "chief@example.com", today=THURSDAY)
    assert code == 0 and levels(got)["same day"] == "OK"
    relaxed = {**CONFIG, "meeting_defaults": {"same_day_meetings": True}}
    code, got = check(tmp_path, "14:00", "14:30", QUIET_DAY, "--attendee", "a@example.com", today=THURSDAY, config=relaxed)
    assert code == 0 and levels(got)["same day"] == "OK"


def test_a_meeting_staged_into_the_same_day_three_days_running_is_refused_each_day(tmp_path):
    """The replay: staged on the 5th for the 5th, carried to the 6th for the 6th, then to the 9th for the 9th."""
    for day in ("2026-11-05", "2026-11-06", "2026-11-09"):
        after_weekly = [meeting(day, "13:00", "14:00", "Leadership weekly")]
        code, got = check(tmp_path, "14:00", "14:30", after_weekly, "--attendee", "a@example.com", "--requester", "a@example.com",
                          "--deadline", "2026-11-09", day=day, today=day, window=(day, "2026-11-16"))
        assert code == 1 and got["verdict"] == "REFUSE", (day, got)
        assert levels(got)["deadline"] == "NOTE" and "preference" in detail(got, "deadline")


def test_the_last_deep_work_block_of_the_day_is_kept(tmp_path):
    open_mornings = {**CONFIG, "protected_hours": []}
    busy = [meeting(THURSDAY, "11:00", "12:00"), meeting(THURSDAY, "12:00", "13:00", "Lunch"),
            meeting(THURSDAY, "16:00", "17:00", "Review")]  # free: 09:00-11:00 and 13:00-16:00
    code, got = check(tmp_path, "14:00", "14:30", busy, "--attendee", "a@example.com", config=open_mornings)
    assert code == 0 and levels(got)["deep work"] == "OK", got   # the morning block still stands
    morning_gone = busy + [meeting(THURSDAY, "09:30", "11:00", "Workshop")]
    code, got = check(tmp_path, "14:00", "14:30", morning_gone, "--attendee", "a@example.com", config=open_mornings)
    assert code == 1 and levels(got)["deep work"] == "REFUSE" and "13:00" in detail(got, "deep work")
    code, got = check(tmp_path, "15:30", "16:00", morning_gone, "--attendee", "a@example.com", config=open_mornings)
    assert code == 0 and levels(got)["deep work"] == "OK", got   # 13:00-15:30 is still two and a half hours


def test_a_day_already_carrying_its_meeting_load_gets_nothing_more(tmp_path):
    full = [meeting(THURSDAY, "11:00", "13:00"), meeting(THURSDAY, "13:00", "15:45", "Offsite")]  # 4 h 45 min
    code, got = check(tmp_path, "15:45", "16:15", full, "--attendee", "a@example.com")
    assert code == 1 and levels(got)["meeting load"] == "REFUSE" and "5.2" in detail(got, "meeting load")


def test_a_slot_in_the_middle_of_a_free_block_is_sent_back_for_a_better_place(tmp_path):
    code, got = check(tmp_path, "15:30", "16:00", QUIET_DAY, "--attendee", "a@example.com")
    assert code == 0 and got["verdict"] == "REVIEW" and levels(got)["placement"] == "REVIEW"
    assert "14:00" in detail(got, "placement") and "beside" in detail(got, "placement")


def test_an_existing_meeting_with_the_same_person_comes_before_a_new_one(tmp_path):
    week = QUIET_DAY + [meeting("2026-11-13", "10:00", "10:30", "Weekly 1:1", ["A@example.com", "me@example.com"])]
    code, got = check(tmp_path, "14:00", "14:30", week, "--attendee", "a@example.com")
    assert code == 0 and got["verdict"] == "REVIEW"
    assert levels(got)["existing touchpoint"] == "REVIEW" and "Weekly 1:1" in detail(got, "existing touchpoint")
    code, got = check(tmp_path, "14:00", "14:30", week, "--attendee", "someone-else@example.com")
    assert levels(got)["existing touchpoint"] == "OK"


def test_a_deadline_binds_only_for_someone_whose_timing_binds(tmp_path):
    code, got = check(tmp_path, "14:00", "14:30", QUIET_DAY, "--requester", "a@example.com", "--deadline", "2026-11-11")
    assert code == 0 and levels(got)["deadline"] == "NOTE"
    code, got = check(tmp_path, "14:00", "14:30", QUIET_DAY, "--requester", "chair@board.example.com", "--deadline", "2026-11-11")
    assert code == 1 and levels(got)["deadline"] == "REFUSE" and "2026-11-11" in detail(got, "deadline")


def test_protected_hours_are_refused_unless_the_persons_timing_binds(tmp_path):
    code, got = check(tmp_path, "10:00", "10:30", QUIET_DAY, "--attendee", "a@example.com")
    assert code == 1 and levels(got)["protected hours"] == "REFUSE" and "maker morning" in detail(got, "protected hours")
    code, got = check(tmp_path, "10:00", "10:30", QUIET_DAY, "--attendee", "chief@example.com")
    assert levels(got)["protected hours"] == "OK"


def test_protected_hours_written_as_prose_are_named_as_unchecked(tmp_path):
    prose = {**CONFIG, "protected_hours": {"maker_mornings": "Protect 09:00-11:00 for maker's work."}}
    code, got = check(tmp_path, "14:00", "14:30", QUIET_DAY, "--attendee", "a@example.com", config=prose)
    assert code == 0 and levels(got)["protected hours"] == "NOTE" and "check them yourself" in detail(got, "protected hours")


def test_the_agents_own_holds_and_all_day_markers_count_as_free_time(tmp_path):
    shielded = [meeting(THURSDAY, "11:00", "13:00", "Hold"), {"start": {"date": THURSDAY}, "end": {"date": "2026-11-13"}, "summary": "Conference"},
                meeting(THURSDAY, "13:00", "14:00", "Staff meeting")]
    code, got = check(tmp_path, "14:00", "14:30", shielded, "--attendee", "a@example.com")
    assert code == 0 and got["verdict"] == "OK", got


def test_times_given_with_another_offset_are_read_in_the_principals_zone(tmp_path):
    events = [{"start": {"dateTime": f"{THURSDAY}T18:00:00+00:00"}, "end": {"dateTime": f"{THURSDAY}T19:00:00Z"}, "summary": "Staff meeting"}]
    code, got = check(tmp_path, "14:00", "14:30", events, "--attendee", "a@example.com")  # 18:00 UTC is 13:00 in New York
    assert code == 0 and "Staff meeting" in detail(got, "placement")


@pytest.mark.parametrize("why, kwargs", [
    ("the calendar read does not cover", {"window": ("2026-11-13", "2026-11-18")}),
    ("which days", {"window": None}),
    ("preferences", {"config": None}),
])
def test_it_refuses_to_judge_what_it_was_not_shown(tmp_path, why, kwargs):
    code, got = check(tmp_path, "14:00", "14:30", QUIET_DAY, "--attendee", "a@example.com", **kwargs)
    assert code == 2 and why in got


def test_the_text_report_leads_with_the_verdict(tmp_path):
    prefs, read = tmp_path / "preferences.json", tmp_path / "events.json"
    prefs.write_text(json.dumps(CONFIG), encoding="utf-8")
    read.write_text(json.dumps({"window": {"from": THURSDAY, "through": "2026-11-18"}, "events": QUIET_DAY}), encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPT), "--start", f"{THURSDAY}T14:00", "--end", f"{THURSDAY}T14:30", "--events", str(read),
                           "--config", str(prefs), "--today", THURSDAY, "--attendee", "a@example.com"], capture_output=True, text=True)
    lines = done.stdout.splitlines()
    assert done.returncode == 1 and lines[0] == "slot Thu 2026-11-12 14:00-14:30: REFUSE"
    assert any(line.startswith("  REFUSE  same day:") for line in lines)


# --- a slot that needs a trip (2026-11-11) ------------------------------------------------------
# An in-person meeting takes the time to get there and back as well as its own. A slot that looked free was
# judged without either, so the travel is now part of what the slot takes.

def test_the_trip_counts_as_taken_time(tmp_path):
    code, report = check(tmp_path, "14:30", "15:30", QUIET_DAY, "--travel-before", "45", "--travel-after", "45")
    assert code == 1 and levels(report)["travel"] == "REFUSE"
    assert "the trip there (13:45-14:30) overlaps Staff meeting" in detail(report, "travel")
    code, report = check(tmp_path, "15:00", "16:00", QUIET_DAY, "--travel-before", "45", "--travel-after", "45")
    assert levels(report)["travel"] == "OK" and "14:15-15:00 there, 16:00-16:45 back" in detail(report, "travel")
    code, report = check(tmp_path, "11:30", "12:15", QUIET_DAY, "--travel-before", "30", "--travel-after", "50")
    assert levels(report)["travel"] == "REFUSE" and "the trip back (12:15-13:05) overlaps Staff meeting" in detail(report, "travel")


def test_the_deep_work_block_is_judged_with_the_trip_in_it(tmp_path):
    day = [meeting(THURSDAY, "09:30", "10:30", "Standup"), meeting(THURSDAY, "11:00", "12:00", "Review"),
           meeting(THURSDAY, "16:00", "17:00", "Wrap-up")]
    code, report = check(tmp_path, "15:00", "15:30", day)          # 12:00-15:00 stays free: three hours
    assert levels(report)["deep work"] == "OK"
    code, report = check(tmp_path, "15:00", "15:30", day, "--travel-before", "75")  # 13:45 on is the trip: 1 h 45 left
    assert code == 1 and levels(report)["deep work"] == "REFUSE"


def test_a_slot_with_no_trip_has_no_travel_line_and_an_in_person_slot_must_give_one(tmp_path):
    code, report = check(tmp_path, "15:00", "16:00", QUIET_DAY)
    assert "travel" not in levels(report)
    code, said = check(tmp_path, "15:00", "16:00", QUIET_DAY, "--in-person")
    assert code == 2 and "--travel-before" in said and "work out the trip first" in said
    code, report = check(tmp_path, "15:00", "16:00", QUIET_DAY, "--in-person", "--travel-before", "10", "--travel-after", "10")
    assert code in (0, 1) and levels(report)["travel"] == "OK"


# --- what an evening away costs, seen at the ask (2026-11-11) ----------------------------------------------
# A principal said yes to an evening event without seeing the trip: three hours of travel and home near midnight
# before an early morning. With the trip's minutes given, the check now says when the principal is home, and
# sends a return past the policy's latest hour or a night shorter than the policy keeps to the principal.

RESTED = {**CONFIG, "travel_policy": {"latest_return": "23:00", "sleep_hours": 8}}
EARLY = [meeting("2026-11-13", "07:30", "08:30", "Training session")]
EVENING = ("--in-person", "--travel-before", "85", "--travel-after", "108")


def test_an_evening_away_shows_when_the_principal_is_home_and_what_the_night_leaves(tmp_path):
    code, report = check(tmp_path, "19:00", "22:00", EARLY, *EVENING, config=RESTED)
    assert levels(report)["return"] == "REVIEW" and "home at 23:48, after 23:00" in detail(report, "return")
    assert levels(report)["sleep"] == "REVIEW"
    assert "Training session" in detail(report, "sleep") and "07:30" in detail(report, "sleep") and "7 h 42 min" in detail(report, "sleep")
    assert report["verdict"] != "OK"


def test_a_trip_that_is_home_in_time_says_so(tmp_path):
    code, report = check(tmp_path, "12:00", "13:00", EARLY, "--in-person", "--travel-before", "30", "--travel-after", "30", config=RESTED)
    assert levels(report)["return"] == "OK" and "home at 13:30" in detail(report, "return")
    assert levels(report)["sleep"] == "OK"


def test_without_the_policys_hours_only_the_time_home_is_shown(tmp_path):
    code, report = check(tmp_path, "19:00", "22:00", EARLY, *EVENING)
    assert levels(report)["return"] == "OK" and "home at 23:48" in detail(report, "return") and "sleep" not in levels(report)


def test_a_read_that_ends_before_the_next_morning_cannot_judge_the_night(tmp_path):
    code, report = check(tmp_path, "19:00", "22:00", [], *EVENING, config=RESTED, window=("2026-11-10", "2026-11-12"))
    assert levels(report)["sleep"] == "NOTE" and "2026-11-13" in detail(report, "sleep")


# --- the morning begins whether or not the calendar says so (2026-11-11) -----------------------------------
# The night was measured to the next morning's first calendar entry, so a late return cost nothing the check could
# see when the morning held none: a principal's mornings began at a fixed hour with no entry. The policy can say
# when the morning starts, and the night ends at the earlier of that hour and the first entry.

MORNING = {**CONFIG, "travel_policy": {"latest_return": "23:00", "sleep_hours": 8, "morning_starts": "06:30"}}


def test_a_morning_with_no_entry_still_begins_at_the_policys_hour(tmp_path):
    code, report = check(tmp_path, "19:00", "22:00", [], *EVENING, config=MORNING)          # home 23:48, so 6 h 42 min
    assert levels(report)["sleep"] == "REVIEW"
    assert "the morning starts 06:30" in detail(report, "sleep") and "6 h 42 min" in detail(report, "sleep")
    code, report = check(tmp_path, "19:00", "22:00", EARLY, *EVENING, config=MORNING)       # an entry at 07:30: the earlier of the two
    assert "the morning starts 06:30" in detail(report, "sleep") and "Training session" not in detail(report, "sleep")
    sooner = [meeting("2026-11-13", "05:45", "06:15", "Airport check-in")]
    code, report = check(tmp_path, "19:00", "22:00", sooner, *EVENING, config=MORNING)
    assert "Airport check-in" in detail(report, "sleep") and "05:45" in detail(report, "sleep")
    code, report = check(tmp_path, "12:00", "13:00", [], "--in-person", "--travel-before", "30", "--travel-after", "30", config=MORNING)
    assert levels(report)["sleep"] == "OK"                                                   # home at 13:30: the night is whole


def test_the_policys_hour_judges_the_night_even_when_the_read_ends_before_the_morning(tmp_path):
    code, report = check(tmp_path, "19:00", "22:00", [], *EVENING, config=MORNING, window=("2026-11-10", "2026-11-12"))
    assert levels(report)["sleep"] == "REVIEW" and "the morning starts 06:30" in detail(report, "sleep")
    code, report = check(tmp_path, "12:00", "13:00", [], "--in-person", "--travel-before", "30", "--travel-after", "30",
                         config=MORNING, window=("2026-11-10", "2026-11-12"))
    assert levels(report)["sleep"] == "NOTE"                                                 # long enough by the policy; an entry could be earlier


@pytest.mark.parametrize("key, value", [("latest_return", "10pm"), ("morning_starts", "6am"), ("morning_starts", "25:00")])
def test_a_policy_hour_that_is_no_time_of_day_is_not_judged(tmp_path, key, value):
    """A value that is no time of day raised an error that left the script with the exit code of a refusal. The
    check says which key it could not read and exits 2: nothing is judged on a guess."""
    unreadable = {**CONFIG, "travel_policy": {"latest_return": "23:00", "sleep_hours": 8, key: value}}
    code, said = check(tmp_path, "19:00", "22:00", [], *EVENING, config=unreadable)
    assert code == 2 and key in said and "HH:MM" in said


def test_a_return_after_the_morning_has_begun_leaves_no_night(tmp_path):
    """The fourth review: home at or after the hour the morning starts was read as a whole night, since only a
    morning still ahead was looked for."""
    for back in ("600", "630"):                                                              # 19:00 to 21:00, then home at 07:00 and 07:30
        code, report = check(tmp_path, "19:00", "21:00", [], "--in-person", "--travel-before", "30", "--travel-after", back,
                             config={**CONFIG, "travel_policy": {"sleep_hours": 8, "morning_starts": "07:00"}})
        assert levels(report)["sleep"] == "REVIEW" and "07:00" in detail(report, "sleep"), back


# --- the meeting load counts meetings (2026-11-11) -------------------------------------------------------------
# A Friday noon slot was refused at 7.08 hours of meetings against a limit of 5. Most of those hours were the
# principal's own blocks (a morning routine, training, rituals, reserved holds); with meetings only the day held
# 2.58. The same read feeds the free-time checks, where those blocks belong, so leaving them out of the read is no
# fix: the load has to tell a meeting from a block.

OWN = {**CONFIG, "protected_hours": [], "principal_addresses": ["me@example.com", "*@me.example.org"],
       "calendar_guardian": {**CONFIG["calendar_guardian"], "personal_markers": ["#reserved"]}}
BLOCKS = [meeting(THURSDAY, "06:30", "08:30", "Training"), meeting(THURSDAY, "09:00", "10:00", "Morning ritual"),
          meeting(THURSDAY, "12:00", "13:00", "Lunch with the coach #reserved", ["coach@example.com"]),
          meeting(THURSDAY, "16:30", "17:00", "Review my week", ["me@example.com", "self@me.example.org"]),
          {"start": f"{THURSDAY}T17:00", "end": f"{THURSDAY}T18:00", "summary": "Evening ritual",
           "attendees": [{"email": "owner@elsewhere.example", "self": True}]}]
MEETINGS = [meeting(THURSDAY, "10:00", "11:00", "Planning", ["a@example.com"]),
            meeting(THURSDAY, "15:00", "16:30", "Review", ["b@example.com", "me@example.com"])]


def test_the_principals_own_blocks_are_not_meeting_hours(tmp_path):
    code, got = check(tmp_path, "13:30", "14:00", BLOCKS + MEETINGS, "--attendee", "c@example.com", config=OWN)
    said = detail(got, "meeting load")
    assert levels(got)["meeting load"] == "OK" and "3.00 hours" in said, said                 # 1 h, 1 h 30 min and this half hour
    assert "5 of the day's 7 events" in said and "own" in said, said                          # and it says what it left out
    more = MEETINGS + [meeting(THURSDAY, "11:00", "13:30", "Offsite", ["d@example.com"])]
    code, got = check(tmp_path, "13:30", "14:00", BLOCKS[:2] + more, "--attendee", "c@example.com", config=OWN)
    assert code == 1 and levels(got)["meeting load"] == "REFUSE" and "5.50 hours" in detail(got, "meeting load")


def test_a_read_that_names_no_one_else_counts_every_event_and_says_so(tmp_path):
    bare = [meeting(THURSDAY, "11:00", "13:00"), meeting(THURSDAY, "13:00", "15:45", "Offsite")]
    code, got = check(tmp_path, "15:45", "16:15", bare, "--attendee", "a@example.com")
    said = detail(got, "meeting load")
    assert code == 1 and levels(got)["meeting load"] == "REFUSE" and "5.25 hours" in said
    assert "names no one else" in said, said


def test_own_blocks_still_count_as_taken_time(tmp_path):
    day = [meeting(THURSDAY, "09:00", "12:00", "Writing block"), meeting(THURSDAY, "12:30", "17:00", "Training camp"),
           meeting("2026-11-13", "10:00", "10:30", "Planning", ["a@example.com"])]
    code, got = check(tmp_path, "12:00", "12:30", day, "--attendee", "c@example.com", config=OWN)
    assert levels(got)["meeting load"] == "OK" and "0.50 hours" in detail(got, "meeting load")
    assert code == 1 and levels(got)["deep work"] == "REFUSE", got                           # the day has no free block left


# --- protected windows beside prose (2026-11-11) -----------------------------------------------------------------
# A principal's preferences described protected hours in prose that another reader depends on, so the check could
# only say "check them yourself", and his night rule (in bed by an hour, nothing before another) bound nothing.
# Windows can now stand inside that section beside the prose; what stays in prose is still named as unchecked.

NIGHT = {**CONFIG, "protected_hours": {
    "maker_mornings": "Protect 09:00-11:00 for deep work. Strongly minimize meetings in this window.",
    "hard_floor": "No meetings before 10:00 unless the requester's timing binds.",
    "windows": [{"start": "21:00", "end": "24:00", "label": "the night", "source": "sleep.ordinary_nights"},
                {"start": "00:00", "end": "10:00", "label": "nothing before ten", "source": "protected_hours.hard_floor"}]}}


def test_windows_inside_a_section_of_prose_are_checked_and_the_prose_is_still_named(tmp_path):
    code, got = check(tmp_path, "21:30", "22:00", QUIET_DAY, "--attendee", "a@example.com", config=NIGHT)
    assert code == 1 and levels(got)["protected hours"] == "REFUSE" and "the night" in detail(got, "protected hours")
    code, got = check(tmp_path, "08:00", "08:30", QUIET_DAY, "--attendee", "a@example.com", config=NIGHT)
    assert code == 1 and "nothing before ten" in detail(got, "protected hours") and "00:00-10:00" in detail(got, "protected hours")
    code, got = check(tmp_path, "08:00", "08:30", QUIET_DAY, "--attendee", "chief@example.com", config=NIGHT)
    assert levels(got)["protected hours"] == "OK"                                             # someone whose timing binds
    code, got = check(tmp_path, "14:00", "14:30", QUIET_DAY, "--attendee", "a@example.com", config=NIGHT)
    said = detail(got, "protected hours")
    assert levels(got)["protected hours"] == "NOTE" and "maker_mornings" in said and "hard_floor" not in said, said   # the window stands for that line


def test_a_slot_that_runs_past_midnight_meets_the_next_days_windows(tmp_path):
    late = {**NIGHT, "protected_hours": {"windows": [{"start": "00:00", "end": "06:00", "label": "the small hours"}]}}
    done = subprocess.run([sys.executable, str(SCRIPT), "--start", f"{THURSDAY}T23:30", "--end", "2026-11-13T00:30", "--events",
                           str(tmp_path / "events.json"), "--config", str(tmp_path / "preferences.json"), "--today", "2026-11-10", "--json"],
                          capture_output=True, text=True) if check(tmp_path, "14:00", "14:30", QUIET_DAY, config=late) else None
    got = json.loads(done.stdout)
    assert done.returncode == 1 and levels(got)["protected hours"] == "REFUSE" and "the small hours" in detail(got, "protected hours")


def test_a_window_that_is_no_time_of_day_stops_the_check(tmp_path):
    wrong = {**CONFIG, "protected_hours": {"windows": [{"start": "9pm", "end": "24:00"}]}}
    code, got = check(tmp_path, "14:00", "14:30", QUIET_DAY, "--attendee", "a@example.com", config=wrong)
    assert code == 2 and "9pm" in got and "HH:MM" in got
