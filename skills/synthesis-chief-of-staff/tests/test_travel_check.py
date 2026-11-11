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


def test_an_entry_with_no_start_is_passed_over_and_the_rest_are_judged(tmp_path):
    code, report = check(tmp_path, [{"summary": "A note with no time", "location": "Somewhere 5"}, LAUNCH])
    assert code == 1 and report["in_person"] == 1 and report["events"][0]["summary"].startswith("Book launch")


# --- found on a real week's calendar read (2026-11-11), each as a test that failed first ----------------

def test_a_block_that_names_no_commitment_belongs_to_the_one_nearest_to_it(tmp_path):
    """A morning session and an evening event on one day: the evening's blocks, which name no commitment, were
    taken for the morning's too, so the morning looked half provided for."""
    morning = event("Training session", "08:15", "09:15", "Riverside Gym, 40 Dock St, Harbor Town", "Travel: blocks before and after")
    unnamed = lambda block, text: dict(block, description="\n".join(row for row in text.splitlines() if not row.startswith("For:")))  # noqa: E731
    code, report = check(tmp_path, [morning, RESOLVED, unnamed(GOING, OUT), unnamed(RETURNING, BACK)])
    assert code == 1
    assert lacks(report) == []  # the evening is whole
    missing = " | ".join(lacks(report, "Training session"))
    assert "no travel block before it" in missing and "no travel block after it" in missing and "has no" not in missing


def test_a_description_written_as_html_is_read_line_by_line(tmp_path):
    """Calendar connectors often return a description as HTML, where a line break is a tag."""
    html = lambda text: "<p>" + "<br>".join(f"<b>{row.split(':', 1)[0]}:</b>{row.split(':', 1)[1]}" for row in text.splitlines()) + "</p>"  # noqa: E731
    going = dict(GOING, description=html(OUT).replace("$15.00 train and", "$15.00 train &amp; "))
    returning = dict(RETURNING, description=BACK.replace("\n", "<br/>\n"))
    resolved = dict(RESOLVED, description="<div>Doors at 18:45.</div><div>Travel: blocks before and after</div>")
    code, report = check(tmp_path, [resolved, going, returning])
    assert code == 0, report
    trip = next(e for e in report["events"] if e["summary"].startswith("Book launch"))
    assert trip["paid_by"] == "personal" and trip["leave"] == "17:05"


# --- after a second model's review of the check (2026-11-11), each as a test that failed first ------------

DINNER = event("Dinner at Rosa's", "19:00", "20:00", "Rosa's, 12 Quay St, Harbor Town", "Travel: blocks before and after")
SHOW = event("Late show", "20:30", "22:00", "The Grand Theatre, 149 Main St, Harbor Town", "Travel: blocks before and after")
LAUNCH_NAME = "Book launch at the Grand Theatre"


def named(block, *titles):
    """The block with its `For:` line replaced by one for each title given; none given, a block that names nothing."""
    rows = [row for row in block["description"].splitlines() if not row.startswith("For:")]
    return dict(block, description="\n".join([f"For: {title}" for title in titles] + rows))


def test_one_pair_of_blocks_does_not_cover_two_places(tmp_path):
    """Out before the first and home after the second leaves the way between them unwritten."""
    code, report = check(tmp_path, [DINNER, SHOW, named(GOING), named(RETURNING)])
    assert code == 1 and report["flagged"] == 2, report
    assert any("no travel block after it" in item for item in lacks(report, "Dinner at Rosa's"))
    assert any("no travel block before it" in item for item in lacks(report, "Late show"))


def test_a_block_between_two_places_names_both_and_serves_both(tmp_path):
    between = named(event("Travel: Rosa's to the Grand Theatre", "20:02", "20:14", "", OUT), "Dinner at Rosa's", "Late show")
    code, report = check(tmp_path, [DINNER, SHOW, named(GOING, "Dinner at Rosa's"), between, named(RETURNING, "Late show")])
    assert code == 0, report
    alone = named(between, "Late show")  # named for one of them, it is that one's only
    code, report = check(tmp_path, [DINNER, SHOW, named(GOING, "Dinner at Rosa's"), alone, named(RETURNING, "Late show")])
    assert code == 1 and lacks(report, "Late show") == []
    assert any("no travel block after it" in item for item in lacks(report, "Dinner at Rosa's"))


def test_a_block_named_for_another_event_is_not_this_ones(tmp_path):
    launch = dict(RESOLVED, summary="Book launch")
    code, report = check(tmp_path, [launch, named(GOING, "Book launch planning lunch"), named(RETURNING, "Book launch planning lunch")])
    assert code == 1, report
    missing = " | ".join(lacks(report, "Book launch"))
    assert "no travel block before it" in missing and "no travel block after it" in missing
    assert "Book launch planning lunch" in missing  # and it says whose the block beside it is


def test_a_block_may_name_its_event_by_the_opening_words_of_its_title(tmp_path):
    code, report = check(tmp_path, [RESOLVED, named(GOING, "book launch"), named(RETURNING, "Book  launch at the Grand")])
    assert code == 0, report


def test_events_with_one_title_each_take_the_blocks_nearest_them(tmp_path):
    again = dict(RESOLVED, start="2026-11-13T19:00", end="2026-11-13T22:00")
    code, report = check(tmp_path, [RESOLVED, GOING, RETURNING, again])
    assert code == 1 and report["flagged"] == 1, report
    later = next(e for e in report["events"] if e["start"].startswith("2026-11-13"))
    assert any("no travel block before it" in item for item in later["lacks"])


@pytest.mark.parametrize("location", ["Studio 54", "Pier 39", "Room 4, Floor 12", "Harbor Town, 7 pm", "Main entrance, 18:30"])
def test_a_number_in_a_venues_name_or_a_time_is_not_an_address(tmp_path, location):
    code, report = check(tmp_path, [dict(RESOLVED, location=location), GOING, RETURNING])
    assert code == 1 and any("no exact address" in item for item in lacks(report)), report


@pytest.mark.parametrize("location", ["149 Main St", "Hauptstraße 5, 10115 Berlin", "Kungsgatan 44, 111 35 Stockholm", "Calle Mayor, 5, Madrid",
                                      "12, MG Road, Bengaluru 560001", "405 5th Ave, New York", "東京都千代田区丸の内1丁目9-1",
                                      "The Grand Theatre\n149 Main St\nHarbor Town", "Doors at 149 Main St"])
def test_an_address_is_read_as_one_however_its_country_writes_it(tmp_path, location):
    code, report = check(tmp_path, [dict(RESOLVED, location=location), GOING, RETURNING])
    assert code == 0, report


def test_an_online_word_in_a_venues_name_does_not_hide_its_address(tmp_path):
    code, report = check(tmp_path, [event("Town meeting", "19:00", "21:00", "Zoom Hall, 149 Main St, Harbor Town")])
    assert code == 1 and report["in_person"] == 1, report
    code, report = check(tmp_path, [event("Stand-up", "09:00", "09:15", "Zoom, passcode 12345")])
    assert code == 0 and report["in_person"] == 0, report


def test_an_event_under_way_when_the_days_begin_is_judged_for_its_way_back(tmp_path):
    workshop = {"summary": "Overnight workshop", "start": "2026-11-10T23:00", "end": "2026-11-11T20:00",
                "location": "The Grand Theatre, 149 Main St, Harbor Town", "description": "Travel: blocks before and after"}
    code, report = check(tmp_path, [workshop])  # the read starts on the 11th
    assert code == 1 and report["in_person"] == 1, report
    missing = " | ".join(lacks(report, "Overnight workshop"))
    assert "no travel block after it" in missing and "block before" not in missing  # the way there is behind it, outside this read
    code, report = check(tmp_path, [workshop], window=("2026-11-10", "2026-11-18"))
    assert "no travel block before it" in " | ".join(lacks(report, "Overnight workshop"))  # a read that holds its start shows both


def test_an_all_day_event_that_began_earlier_counts_on_the_days_it_covers(tmp_path):
    offsite = {"summary": "Offsite", "start": {"date": "2026-11-09"}, "end": {"date": "2026-11-13"}, "location": "The Lodge, 3 Lake Rd, Harbor Town"}
    code, report = check(tmp_path, [offsite])
    assert code == 1 and report["in_person"] == 1, report
    over = dict(offsite, end={"date": "2026-11-11"})  # an all-day end names the day after its last
    assert check(tmp_path, [over])[1]["in_person"] == 0


def test_a_read_it_cannot_make_sense_of_is_not_a_verdict(tmp_path):
    """Exit 1 means an event lacks its travel; a read whose shape breaks the check must not look like that."""
    odd = {"summary": None, "start": "2026-11-11T19:00", "end": "2026-11-11T18:00", "location": {"street": "149 Main St"}, "description": 7}
    code, said = check(tmp_path, [odd, "a stray string", {"summary": "Travel: x", "start": "2026-11-11T17:00", "end": "2026-11-11T18:00",
                                                           "description": ["For: nothing"]}])
    assert code in (1, 2) and "Traceback" not in str(said), said
    code, said = check(tmp_path, [dict(RESOLVED, start={"dateTime": 5})])
    assert code == 2 and "Traceback" not in str(said), said


def test_a_named_place_is_known_by_its_label_with_a_room_or_a_note_after_it(tmp_path):
    """His real week: "the gym (main floor), <his building>" was read as somewhere away."""
    events = [event("Stand-up", "09:00", "09:30", "Office, 4th floor"), event("Review", "10:00", "11:00", "Office (east wing)"),
              event("Movers", "12:00", "13:00", "Home - ring twice")]
    code, report = check(tmp_path, events)
    assert code == 0 and report["in_person"] == 0, report
    for elsewhere in ("Home Depot, 40 W 23rd St, Example City", "Officers' Club, 9 Fort Rd, Example City"):
        code, report = check(tmp_path, [event("Errand", "09:00", "10:00", elsewhere)])
        assert code == 1 and report["in_person"] == 1, report


# --- sleep is a cost (2026-11-11) --------------------------------------------------------------------------
# The principal, shown the plan for that evening: the trip was a burden he had not seen when he said yes, and a
# short night before an early morning is a cost of its own. The policy can say how many hours he keeps between
# getting home and the next morning's first commitment; a shorter night is his to decide, like a late return.

def test_a_short_night_before_an_early_commitment_goes_to_the_principal(tmp_path):
    rested = {**CONFIG, "travel_policy": {**POLICY, "sleep_hours": 8}}
    early = event("Training session", "07:00", "08:00", "Office", day="2026-11-12")  # home 23:20, so 7 h 40 min
    code, report = check(tmp_path, [RESOLVED, GOING, RETURNING, early], config=rested)
    assert code == 1, report
    night = next(item for item in lacks(report) if "home at 23:20" in item)
    assert '"Training session" starts 07:00 the next morning' in night and "7 h 40 min" in night and "8 hours" in night and "decision" in night
    decided = dict(RETURNING, description=BACK + '\nDecision: "worth it, and I will start late on Friday"')
    assert check(tmp_path, [RESOLVED, GOING, decided, early], config=rested)[0] == 0
    later = dict(early, start="2026-11-12T08:00", end="2026-11-12T09:00")
    assert check(tmp_path, [RESOLVED, GOING, RETURNING, later], config=rested)[0] == 0       # 8 h 40 min is enough
    assert check(tmp_path, [RESOLVED, GOING, RETURNING, early])[0] == 0                       # no sleep_hours, no rule
    same_day = event("Call", "23:40", "23:55", "", day=DAY)                                   # later the same night is not the morning
    assert check(tmp_path, [RESOLVED, GOING, RETURNING, same_day], config=rested)[0] == 0


def test_the_policys_morning_counts_when_the_calendar_holds_no_entry(tmp_path):
    """A principal's mornings began at a fixed hour with nothing on the calendar, so the night after a late return
    looked whole (2026-11-11). `morning_starts` is that hour."""
    rested = {**CONFIG, "travel_policy": {**POLICY, "sleep_hours": 8, "morning_starts": "06:30"}}
    code, report = check(tmp_path, [RESOLVED, GOING, RETURNING], config=rested)             # home 23:20, so 7 h 10 min
    assert code == 1, report
    night = next(item for item in lacks(report) if "home at 23:20" in item)
    assert "the morning starts 06:30" in night and "7 h 10 min" in night and "8 hours" in night and "decision" in night
    decided = dict(RETURNING, description=BACK + '\nDecision: "worth it, and the morning starts late"')
    assert check(tmp_path, [RESOLVED, GOING, decided], config=rested)[0] == 0
    later = {**CONFIG, "travel_policy": {**POLICY, "sleep_hours": 8, "morning_starts": "07:30"}}
    assert check(tmp_path, [RESOLVED, GOING, RETURNING], config=later)[0] == 0               # 8 h 10 min is enough


# --- the second review round (2026-11-11), each as a test that failed first --------------------------------

def test_a_street_number_that_only_contains_the_home_number_is_another_address(tmp_path):
    code, report = check(tmp_path, [event("Dinner", "19:00", "21:00", "110 River St, Example City")])
    assert code == 1 and report["in_person"] == 1, report
    code, report = check(tmp_path, [event("Plumber", "19:00", "21:00", "10 River St, Example City")])
    assert code == 0 and report["in_person"] == 0, report


@pytest.mark.parametrize("line", ["Travel: locally unavailable", "Travel: 80 min train; local transfer, 5 min walk",
                                  "Travel: by car", "Travel: nonexistent", "Travel: local"])
def test_a_travel_line_that_is_not_one_of_its_three_forms_excuses_nothing(tmp_path, line):
    code, report = check(tmp_path, [dict(RESOLVED, description=line)])
    missing = " | ".join(lacks(report))
    assert code == 1 and "travel line" in missing, report
    if line != "Travel: local":
        assert "no travel block before it" in missing and "no travel block after it" in missing


@pytest.mark.parametrize("events", ["unreadable events", ["a broken event"], {"an": "object"}, [None], [RESOLVED, 7]])
def test_events_that_are_not_a_list_of_entries_cannot_be_judged(tmp_path, events):
    prefs, read = tmp_path / "preferences.json", tmp_path / "events.json"
    prefs.write_text(json.dumps(CONFIG), encoding="utf-8")
    read.write_text(json.dumps({"window": {"from": "2026-11-11", "through": "2026-11-18"}, "events": events}), encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPT), "--events", str(read), "--config", str(prefs), "--today", DAY, "--json"],
                          capture_output=True, text=True)
    assert done.returncode == 2 and "Traceback" not in done.stderr, done.stdout + done.stderr


@pytest.mark.parametrize("location", ["Room 4, Harbor Town", "The Grand Theatre, Room 4", "Harbor Town, Suite 12", "Floor 3, The Annex"])
def test_a_room_and_a_town_are_not_an_address(tmp_path, location):
    code, report = check(tmp_path, [dict(RESOLVED, location=location), GOING, RETURNING])
    assert code == 1 and any("no exact address" in item for item in lacks(report)), report


def test_a_for_line_in_quotes_names_its_event_and_one_event_on_two_calendars_is_one_event(tmp_path):
    quoted = [named(GOING, '"Book launch at the Grand Theatre"'), named(RETURNING, "\u201cBook launch at the Grand Theatre\u201d.")]
    code, report = check(tmp_path, [RESOLVED, dict(RESOLVED), *quoted])  # the same event read from two calendars
    assert code == 0 and report["in_person"] == 1, report


def test_the_next_mornings_first_commitment_may_be_a_trip(tmp_path):
    rested = {**CONFIG, "travel_policy": {**POLICY, "sleep_hours": 8}}
    dawn = event("Travel: to the airport", "05:30", "06:30", "", OUT, day="2026-11-12")
    code, report = check(tmp_path, [RESOLVED, GOING, RETURNING, dawn], config=rested)
    assert code == 1 and any("Travel: to the airport" in item and "05:30" in item for item in lacks(report)), report


def test_punctuation_does_not_make_another_event_or_another_address(tmp_path):
    marked = [named(GOING, "Book launch at the Grand Theatre."), named(RETURNING, "Book launch at the Grand Theatre:")]
    code, report = check(tmp_path, [RESOLVED, *marked])
    assert code == 0, report
    code, report = check(tmp_path, [event("Plumber", "09:00", "10:00", "10 River St., Example City")])  # the home, with a full stop
    assert code == 0 and report["in_person"] == 0, report
