"""The travel check: an in-person commitment is not on the calendar until its travel is.

On 2026-11-11 a principal who owns no car found an evening event, 28 miles from home, that had sat on his
calendar for six days with no travel time, no route and no fare. Its location read a town and "address on the
card". It had been carried through three daily plans, a guest's arrival logistics and that morning's day-start,
and no step had asked how he would get there or get home. A rule about realistic travel was in his preferences,
filed under something else, so nothing ran it. These tests pin the check that now runs wherever a commitment
with a place is recorded: an exact address, a travel block on each side with every line a traveler needs, the
arithmetic between them, and the two cases that go to the principal. The fixture is that evening, made up.
Committed before the script.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "travel_check.py"
POLICY = {
    "home": {"label": "Home", "address": "10 River St, Example City", "area": "Riverside, Example City"},
    "places": [{"label": "Office", "address": "200 Market St, Example City", "minutes": 35, "route": "Line 4 to Market St"}],
    "car": False,
    "modes": ["subway", "bus", "commuter rail", "ferry", "bike share", "walk"],
    "local_minutes": 20,
    "arrive_early_minutes": 15,
    "latest_return": "23:30",
    "cost": {"personal": "the cheapest reliable public option, bought ahead", "business": "an expensable car where it saves real time"},
    "block_title": "Travel",
    "online": ["zoom", "teams", "meet", "phone", "call", "online", "virtual"],
}
CONFIG = {"timezone": "America/New_York", "travel_policy": POLICY}
DAY = "2026-11-11"
OUT = ("For: Book launch at the Grand Theatre\nPaid by: personal\nLeave: 17:05 from Home\n"
       "Route: Line 1 to Central Station, the 17:50 Harbor line train\nArrive: 18:30 at 149 Main St, Harbor Town\n"
       "Backup: the 18:20 train, arriving 19:02\nFare: $15.00 train and $3.00 subway\nTicket: the rail app, before boarding")
BACK = ("For: Book launch at the Grand Theatre\nPaid by: personal\nLeave: 22:13 from Harbor Town station\n"
        "Route: the 22:13 Harbor line train to Central Station, Line 1 home\nArrive: 23:20 at Home\n"
        "Backup: the 23:13 train\nFare: $11.00 train and $3.00 subway\nTicket: the rail app, before boarding")


def event(summary, start, end, location="", description="", day=DAY):
    return {"summary": summary, "start": f"{day}T{start}", "end": f"{day}T{end}", "location": location, "description": description}


LAUNCH = event("Book launch at the Grand Theatre", "19:00", "22:00", "Harbor Town (address on the invitation)")
RESOLVED = event("Book launch at the Grand Theatre", "19:00", "22:00", "The Grand Theatre, 149 Main St, Harbor Town",
                 "Travel: blocks before and after")
GOING = event("Travel: to the Grand Theatre", "17:05", "18:30", "", OUT)
RETURNING = event("Travel: home from the Grand Theatre", "22:13", "23:20", "", BACK)


def check(tmp_path, events, *args, config=CONFIG, window=("2026-11-11", "2026-11-18"), today="2026-11-11"):
    prefs, read = tmp_path / "preferences.json", tmp_path / "events.json"
    if config is not None:
        prefs.write_text(json.dumps(config), encoding="utf-8")
    read.write_text(json.dumps({"window": {"from": window[0], "through": window[1]}, "events": list(events)} if window else list(events)),
                    encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPT), "--events", str(read), "--config", str(prefs), "--today", today, "--json", *args],
                          capture_output=True, text=True)
    return done.returncode, (json.loads(done.stdout) if done.stdout.strip().startswith("{") else done.stdout + done.stderr)


def lacks(report, summary="Book launch at the Grand Theatre") -> list:
    return next(e["lacks"] for e in report["events"] if e["summary"] == summary)


def test_that_evening_is_flagged_for_its_address_and_both_blocks(tmp_path):
    code, report = check(tmp_path, [LAUNCH])
    assert code == 1 and report["verdict"] == "REFUSE"
    missing = " | ".join(lacks(report))
    assert "exact address" in missing and "address on the invitation" in missing
    assert "travel line" in missing and "block before" in missing and "block after" in missing
    assert report["in_person"] == 1 and report["flagged"] == 1


def test_it_passes_once_the_address_and_both_blocks_exist(tmp_path):
    code, report = check(tmp_path, [RESOLVED, GOING, RETURNING])
    assert code == 0, report
    assert report["verdict"] == "OK" and lacks(report) == [] and report["in_person"] == 1  # a travel block is not a commitment
    trip = next(e for e in report["events"] if e["summary"].startswith("Book launch"))
    assert trip["leave"] == "17:05" and trip["home"] == "23:20" and trip["paid_by"] == "personal"


@pytest.mark.parametrize("line", ["For", "Paid by", "Leave", "Route", "Arrive", "Backup", "Fare", "Ticket"])
def test_a_block_missing_a_line_a_traveler_needs_is_flagged_by_that_line(tmp_path, line):
    thin = dict(GOING, description="\n".join(row for row in OUT.splitlines() if not row.startswith(line + ":")))
    code, report = check(tmp_path, [RESOLVED, thin, RETURNING])
    if line == "For":  # a block that names no commitment is still found by standing next to it
        assert code == 0, report
    else:
        assert code == 1 and any(f"the block before has no `{line}:` line" in item for item in lacks(report))


@pytest.mark.parametrize("vague", ["TBD", "tbc", "to be confirmed", "?", "ask at the desk"])
def test_a_line_that_says_nothing_is_no_line(tmp_path, vague):
    thin = dict(GOING, description=OUT.replace("Backup: the 18:20 train, arriving 19:02", f"Backup: {vague}"))
    code, report = check(tmp_path, [RESOLVED, thin, RETURNING])
    assert (code == 1) == (vague != "ask at the desk")  # words are taken as given; placeholders are not


def test_an_arrival_after_the_start_or_too_close_to_it_is_flagged(tmp_path):
    late = dict(GOING, start=f"{DAY}T18:00", end=f"{DAY}T19:10")
    code, report = check(tmp_path, [RESOLVED, late, RETURNING])
    assert code == 1 and any("arrives 19:10, after the 19:00 start" in item for item in lacks(report))
    tight = dict(GOING, end=f"{DAY}T18:50")
    code, report = check(tmp_path, [RESOLVED, tight, RETURNING])
    assert code == 1 and any("arrives 18:50, 10 minutes before the start; the policy asks for 15" in item for item in lacks(report))


def test_a_return_that_leaves_before_the_end_is_flagged(tmp_path):
    early = dict(RETURNING, start=f"{DAY}T21:30")
    code, report = check(tmp_path, [RESOLVED, GOING, early])
    assert code == 1 and any("leaves 21:30, before the 22:00 end" in item for item in lacks(report))
    said = dict(early, description=BACK + "\nDecision: leaving at 21:30, before the end, for the earlier train")
    code, report = check(tmp_path, [RESOLVED, GOING, said])
    assert code == 0, report  # leaving early is the principal's to decide, and here it is decided


def test_a_return_after_the_latest_hour_goes_to_the_principal(tmp_path):
    late = dict(RETURNING, end=f"{DAY}T23:48", description=BACK.replace("Arrive: 23:20", "Arrive: 23:48"))
    code, report = check(tmp_path, [RESOLVED, GOING, late])
    assert code == 1 and any("home at 23:48, after 23:30" in item and "decision" in item for item in lacks(report))
    decided = dict(late, description=late["description"] + "\nDecision: \"the 22:13 is fine\"")
    code, report = check(tmp_path, [RESOLVED, GOING, decided])
    assert code == 0, report


def test_a_car_on_a_personal_trip_needs_the_principals_decision(tmp_path):
    car = dict(GOING, description=OUT.replace("Route: Line 1 to Central Station, the 17:50 Harbor line train", "Route: a rideshare door to door"))
    code, report = check(tmp_path, [RESOLVED, car, RETURNING])
    assert code == 1 and any("a car on a personal trip" in item for item in lacks(report))
    business = dict(car, description=car["description"].replace("Paid by: personal", "Paid by: business"))
    code, report = check(tmp_path, [RESOLVED, business, dict(RETURNING, description=BACK.replace("personal", "business"))])
    assert code == 0, report


def test_a_place_within_the_local_walk_needs_a_line_and_no_blocks(tmp_path):
    near = event("Dinner with Sam", "19:00", "21:00", "Corner Bistro, 22 River St, Example City", "Travel: local, 6 min walk")
    code, report = check(tmp_path, [near])
    assert code == 0 and lacks(report, "Dinner with Sam") == []
    far = dict(near, description="Travel: local, 35 min walk")
    code, report = check(tmp_path, [far])
    assert code == 1 and any("35 minutes is over the 20 the policy calls local" in item for item in lacks(report, "Dinner with Sam"))
    silent = dict(near, description="")
    code, report = check(tmp_path, [silent])
    assert code == 1 and any("travel line" in item for item in lacks(report, "Dinner with Sam"))


def test_home_a_named_place_and_an_online_meeting_need_nothing(tmp_path):
    events = [event("Movers", "09:00", "10:00", "Home"),
              event("Plumber", "10:00", "11:00", "10 River St, Example City"),
              event("Staff meeting", "13:00", "14:00", "Office"),
              event("Board call", "15:00", "16:00", "https://meet.example.com/abc"),
              event("Catch-up", "16:00", "16:30", "Zoom"),
              event("Focus", "11:00", "13:00", "")]
    code, report = check(tmp_path, events)
    assert code == 0 and report["in_person"] == 0 and report["flagged"] == 0, report


def test_only_the_days_asked_for_are_judged_and_the_read_must_cover_them(tmp_path):
    later = dict(LAUNCH, start="2026-11-25T19:00", end="2026-11-25T22:00")
    code, report = check(tmp_path, [later], "--days", "7")
    assert code == 0 and report["in_person"] == 0  # two weeks out is not in a 7-day look
    code, said = check(tmp_path, [LAUNCH], "--days", "14")
    assert code == 2 and "does not cover" in said  # a read to 11-18 cannot answer for 14 days
    code, said = check(tmp_path, [LAUNCH], window=None)
    assert code == 2 and "which days it covers" in said


def test_no_policy_is_not_a_pass(tmp_path):
    code, said = check(tmp_path, [LAUNCH], config={"timezone": "America/New_York"})
    assert code == 2 and "travel_policy" in said
    code, said = check(tmp_path, [LAUNCH], config=None)
    assert code == 2 and "preferences" in said


def test_the_text_report_names_each_event_and_what_it_lacks(tmp_path):
    prefs, read = tmp_path / "preferences.json", tmp_path / "events.json"
    prefs.write_text(json.dumps(CONFIG), encoding="utf-8")
    read.write_text(json.dumps({"window": {"from": "2026-11-11", "through": "2026-11-18"}, "events": [LAUNCH]}), encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPT), "--events", str(read), "--config", str(prefs), "--today", "2026-11-11"],
                          capture_output=True, text=True)
    lines = done.stdout.splitlines()
    assert done.returncode == 1
    assert lines[0] == "travel: 1 in-person event from 2026-11-11 through 2026-11-17; 1 lacks its travel"
    assert lines[1].startswith("  REFUSE  Wed 2026-11-11 19:00 Book launch at the Grand Theatre")
    assert any(line.startswith("          - no exact address") for line in lines)


def test_an_all_day_event_with_a_place_is_asked_for_its_line(tmp_path):
    fair = {"summary": "Trade fair", "start": {"date": "2026-11-13"}, "end": {"date": "2026-11-14"}, "location": "Hall 3, 1 Expo Way, Harbor Town"}
    code, report = check(tmp_path, [fair])
    assert code == 1 and any("travel line" in item for item in lacks(report, "Trade fair"))
    code, report = check(tmp_path, [dict(fair, description="Travel: blocks before and after")])
    assert code == 1 and any("holds no clock times" in item for item in lacks(report, "Trade fair"))
