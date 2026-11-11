"""A calendar write that puts the principal somewhere says how they get there.

On 2026-11-11 an evening event 28 miles from a principal's home had been on his calendar for six days with no
travel time, route or fare. The agent that wrote it was never asked the question. With `in_person_travel` in the
config, a calendar write that creates an event at a place, or gives one a place, is refused unless the call
carries the event's travel line. It reads the call alone, asks for no approval, and an agent satisfies it by
working the trip out. What counts as a place is asked of the chief of staff's own travel check and the
principal's travel policy, so the guard carries no copy of either. No key, no change.
"""

import json

import pytest

from synthesis import approvals, guards

CREATE, MANAGE, APPLE, MANY = ("mcp__workspace__create_event", "mcp__workspace__manage_event",
                               "mcp__apple-calendar__create_event", "mcp__notion__notion-calendar-create-events")
POLICY = {"home": {"label": "Home", "address": "10 River St, Example City"},
          "places": [{"label": "Office", "address": "200 Market St, Example City", "minutes": 35}],
          "local_minutes": 20, "block_title": "Travel", "online": ["zoom", "video call", "phone", "online"]}
PLACE = "The Grand Theatre, 149 Main St, Harbor Town"


@pytest.fixture
def config(tmp_path):
    prefs = tmp_path / "preferences.json"
    prefs.write_text(json.dumps({"timezone": "America/New_York", "travel_policy": POLICY}), encoding="utf-8")
    return {"in_person_travel": {"preferences": str(prefs)}}


def event(location=PLACE, description="", **more):
    return {"summary": "Book launch", "start_time": "2026-11-18T19:00:00", "end_time": "2026-11-18T22:00:00",
            "location": location, "description": description, "send_updates": "none", **more}


def refused(reason) -> bool:
    return bool(reason) and "Travel:" in reason and "how the principal gets there" in reason


def test_an_event_at_a_place_with_no_word_on_travel_is_refused_and_told_what_to_do(config):
    reason = guards.check(CREATE, event(), config)
    assert refused(reason)
    assert "Book launch" in reason and "149 Main St" in reason
    assert "Travel: blocks before and after" in reason and "Travel: local, N min walk" in reason
    assert "needs no approval" in reason and approvals.pending() == []


@pytest.mark.parametrize("line", ["Travel: blocks before and after", "Travel: local, 12 min walk",
                                  "Notes for the evening.\ntravel: none, already there for the session before"])
def test_with_its_travel_line_the_write_goes_on_as_before(config, line):
    assert guards.check(CREATE, event(description=line), config) is None


@pytest.mark.parametrize("line", ["", "Travel:", "Travel: TBD", "Travel: to be confirmed", "We travel light"])
def test_a_line_that_says_nothing_is_no_line(config, line):
    assert refused(guards.check(CREATE, event(description=line), config))


@pytest.mark.parametrize("location", ["", "Home", "Office", "10 River St, Example City", "https://meet.example.com/abc", "Zoom",
                                      "video call", "+1 212 555 0100"])
def test_the_principals_base_and_a_meeting_with_no_place_need_nothing(config, location):
    assert guards.check(CREATE, event(location=location), config) is None


def test_a_travel_block_is_not_itself_asked_for_travel(config):
    block = event(location="Central Station, 1 Station Sq", summary="Travel: to the Grand Theatre")
    assert guards.check(CREATE, block, config) is None


@pytest.mark.parametrize("summary, block", [("Travelogue discussion", False), ("Travelers' dinner", False), ("Travel", True),
                                             ("Travel: to the Grand Theatre", True), ("TRAVEL to the theatre", True)])
def test_only_a_title_that_starts_with_the_block_word_itself_is_a_travel_block(config, summary, block):
    """The third review: any title starting with the letters of the block word was let through, so an ordinary
    event called "Travelogue discussion" needed no travel line."""
    reason = guards.check(CREATE, event(location="Central Station, 1 Station Sq", summary=summary), config)
    assert refused(reason) != block


def test_an_update_is_judged_only_when_it_gives_the_event_a_place(config):
    assert refused(guards.check(MANAGE, {"action": "update", "event_id": "abc", "location": PLACE, "send_updates": "none"}, config))
    assert guards.check(MANAGE, {"action": "update", "event_id": "abc", "summary": "Book launch (moved)", "send_updates": "none"}, config) is None
    assert guards.check(MANAGE, {"action": "update", "event_id": "abc", "location": PLACE, "send_updates": "none",
                                 "description": "Travel: blocks before and after"}, config) is None


def test_other_connectors_field_names_are_read(config):
    apple = {"title": "Book launch", "start_date": "18 November 2026 at 7:00 PM", "location": PLACE, "notes": ""}
    assert refused(guards.check(APPLE, apple, config))
    assert not refused(guards.check(APPLE, dict(apple, notes="Travel: blocks before and after"), config))  # on to the send approval
    batch = {"events": [event(description="Travel: blocks before and after"), event(summary="Dinner", location="Corner Bistro, 22 River St")]}
    reason = guards.check(MANY, batch, config)
    assert refused(reason) and "Dinner" in reason and "Book launch" not in reason  # each event of a batch is judged by itself


def test_without_the_key_nothing_changes():
    assert guards.check(CREATE, event(), {}) is None


@pytest.mark.parametrize("broken", ["missing", "not json", "no policy"])
def test_a_policy_it_cannot_read_refuses_the_write_and_says_why(tmp_path, broken):
    prefs = tmp_path / "preferences.json"
    if broken == "not json":
        prefs.write_text("{", encoding="utf-8")
    elif broken == "no policy":
        prefs.write_text(json.dumps({"timezone": "UTC"}), encoding="utf-8")
    reason = guards.check(CREATE, event(), {"in_person_travel": {"preferences": str(prefs)}})
    assert reason and "travel policy" in reason and "cannot be read" in reason and not refused(reason)


def test_a_tool_that_is_not_a_calendar_write_is_not_judged(config):
    assert guards.check("mcp__workspace__get_events", {"location": PLACE}, config) is None
    assert guards.check("mcp__maps__search_places", {"location": PLACE, "query": "theatre"}, config) is None


# --- after a second model's review of the guard (2026-11-11), each as a test that failed first -------------

def bare() -> dict:
    return {key: value for key, value in event().items() if key != "location"}


@pytest.mark.parametrize("where", [
    {"where": PLACE}, {"place": PLACE}, {"venue": PLACE},
    {"location": {"displayName": "The Grand Theatre", "address": {"street": "149 Main St", "city": "Harbor Town"}}},
    {"locations": [{"displayName": PLACE}]},
])
def test_a_place_under_another_name_or_in_another_shape_is_still_a_place(config, where):
    assert refused(guards.check(CREATE, {**bare(), **where}, config))
    assert guards.check(CREATE, {**bare(), **where, "description": "Travel: blocks before and after"}, config) is None


def test_what_is_not_the_events_place_is_not_read_as_one(config):
    online = {"location": {"displayName": "Online meeting", "locationType": "default", "uniqueIdType": "private"}}
    assert guards.check_travel(CREATE, {**bare(), **online}, config) is None
    guest = {"attendees": [{"emailAddress": {"address": "pat@example.com", "name": "Pat Example"}}]}
    assert guards.check_travel(CREATE, {**bare(), **guest}, config) is None  # an attendee's address is not where the event is


@pytest.mark.parametrize("location", ["Zoom Hall, 149 Main St, Harbor Town", "149 Main St, Harbor Town (or join by phone)",
                                      "The Grand Theatre, 149 Main St (map: https://maps.example.com/x)"])
def test_a_street_address_is_a_place_whatever_else_the_location_says(config, location):
    assert refused(guards.check(CREATE, event(location=location), config))


@pytest.mark.parametrize("description", ["<p>Notes for the evening</p><br>Travel: local, 12 min walk",
                                         "<div>Doors at 18:45</div><div>Travel: blocks before and after</div>",
                                         "Agenda attached<br/>Travel:&nbsp;none, already there for the session before"])
def test_a_travel_line_in_a_description_written_as_html_is_read(config, description):
    assert guards.check(CREATE, event(description=description), config) is None


def test_a_street_number_that_only_contains_the_home_number_is_another_address(config):
    """The second review: home at 10 River St, and an event at 110 River St passed as home."""
    assert refused(guards.check(CREATE, event(location="110 River St, Example City"), config))
    assert guards.check(CREATE, event(location="10 River St, Example City"), config) is None


@pytest.mark.parametrize("line", ["Travel: locally unavailable", "Travel: by car", "Travel: none", "Travel: 80 min train; local transfer, 5 min walk"])
def test_a_line_that_is_not_one_of_the_three_forms_is_no_travel_line(config, line):
    assert refused(guards.check(CREATE, event(description=line), config))
