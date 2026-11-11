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
