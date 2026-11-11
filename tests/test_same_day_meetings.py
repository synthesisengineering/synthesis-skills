"""A meeting is never put on today by an agent's choice.

On 2026-11-09 an agent staged a meeting into the first open slot of the same day, three days
running, because the requester had suggested "tomorrow or Monday". The principal already
approved every invitation, but nothing in that approval said the meeting was today. With
`same_day_meetings` in the config, a calendar write that starts today and invites someone
else waits for an approval of its own that names it same-day. A hold with no attendees, a
meeting with an exempt attendee, and every config without the key behave as before.
"""

from datetime import date

import pytest

from synthesis import approvals, guards, sends

MANAGE, CREATE = "mcp__workspace__manage_event", "mcp__workspace__create_event"
TODAY, TOMORROW = "2026-11-09", "2026-11-10"
CONFIG = {"send_tools": ["mcp__*__manage_event", "mcp__*__create_event"],
          "same_day_meetings": {"exempt": ["chief@example.com", "*@board.example.com"]},
          "account_routing": {"default_account": "me@example.com",
                              "workspaces": {"/nowhere": {"account": "me@work.example", "aliases": ["me@alias.example"]}}}}


def event(day=TODAY, attendees=("a@example.com",), **more):
    return {"summary": "Follow-up", "start_time": f"{day}T15:00:00", "end_time": f"{day}T15:30:00",
            "attendees": list(attendees), "user_google_email": "me@example.com", **more}


@pytest.fixture(autouse=True)
def _monday(monkeypatch, principal):
    monkeypatch.setattr(guards, "_today", lambda: date(2026, 11, 9), raising=False)
    global _approve
    _approve = principal


def same_day(reason) -> bool:
    return bool(reason) and "same-day" in reason


def test_an_invitation_for_today_waits_for_an_approval_that_says_it_is_today():
    reason = guards.check(CREATE, event(), CONFIG, cwd="/tmp")
    assert same_day(reason) and "today" in reason and "1 other" in reason and "another day" in reason
    _approve(reason)
    assert guards.check(CREATE, event(), CONFIG, cwd="/tmp") is None
    assert same_day(guards.check(CREATE, event(), CONFIG, cwd="/tmp"))  # one approval, one meeting


@pytest.mark.parametrize("attendees, count", [(["a@example.com", "b@example.com"], "2 others"),
                                              ([{"email": "A@example.com", "displayName": "A"}], "1 other."),
                                              ("a@example.com, Someone <b@example.com>", "2 others")])
def test_attendees_are_counted_in_whatever_shape_the_connector_takes(attendees, count):
    reason = guards.check(CREATE, event(attendees=attendees) if isinstance(attendees, list) else {**event(), "attendees": attendees},
                          CONFIG, cwd="/tmp")
    assert same_day(reason) and count in reason


def test_the_ordinary_invitation_approval_does_not_cover_a_meeting_today():
    code = approvals.request("send", {"tool": CREATE, "input": event()}, "an ordinary invitation")
    _approve(f"code {code}")
    assert same_day(guards.check(CREATE, event(), CONFIG, cwd="/tmp"))


def test_a_meeting_on_another_day_takes_the_ordinary_approval():
    reason = guards.check(CREATE, event(TOMORROW), CONFIG, cwd="/tmp")
    assert "approval" in reason and not same_day(reason)
    _approve(reason)
    assert guards.check(CREATE, event(TOMORROW), CONFIG, cwd="/tmp") is None


@pytest.mark.parametrize("attendees", [["chief@example.com"], ["a@example.com", "Chair <chair@board.example.com>"],
                                       [{"email": "CHIEF@example.com"}]])
def test_a_meeting_with_an_exempt_attendee_takes_the_ordinary_approval(attendees):
    reason = guards.check(CREATE, event(attendees=attendees), CONFIG, cwd="/tmp")
    assert "approval" in reason and not same_day(reason)


def test_the_principals_own_addresses_are_not_other_people():
    reason = guards.check(CREATE, event(attendees=["me@work.example", "me@alias.example", "me@example.com"]), CONFIG, cwd="/tmp")
    assert "approval" in reason and not same_day(reason)


def test_a_hold_with_no_attendees_is_untouched():
    hold = {"summary": "Hold", "start_time": f"{TODAY}T15:00:00", "end_time": f"{TODAY}T16:00:00", "send_updates": "none",
            "user_google_email": "me@example.com"}
    assert guards.check(CREATE, hold, CONFIG, cwd="/tmp") is None


def test_without_the_setting_nothing_changes():
    config = {k: v for k, v in CONFIG.items() if k != "same_day_meetings"}
    reason = guards.check(CREATE, event(), config, cwd="/tmp")
    assert "approval" in reason and not same_day(reason)


@pytest.mark.parametrize("start", [
    {"start_time": f"{TODAY}T15:00:00-05:00"}, {"startTime": f"{TODAY}T15:00"}, {"start": f"{TODAY} 15:00"},
    {"start": {"dateTime": f"{TODAY}T15:00:00-05:00", "timeZone": "America/New_York"}}, {"start": {"date": TODAY}},
    {"events": [{"title": "Later", "start": f"{TOMORROW}T10:00", "attendees": ["a@example.com"]},
                {"title": "Now", "start": f"{TODAY}T16:00", "attendees": ["b@example.com"]}]},
])
def test_every_shape_of_start_is_read(start):
    call = {"summary": "Follow-up", "user_google_email": "me@example.com", **start}
    call.setdefault("attendees", ["a@example.com"]) if "events" not in call else None
    assert same_day(guards.check(CREATE, call, CONFIG, cwd="/tmp"))


def test_a_connector_that_names_its_tool_with_hyphens_is_read_too():
    call = {"events": [{"title": "Now", "start": f"{TODAY}T16:00", "attendees": [{"email": "b@example.com"}]}]}
    assert same_day(guards.check("mcp__planner__planner-calendar-create-events", call, CONFIG, cwd="/tmp"))


def test_a_start_given_in_another_zone_counts_when_it_is_today_here(monkeypatch):
    import time
    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    try:  # 01:00 UTC on the 10th is 20:00 on the 9th in New York
        assert same_day(guards.check(CREATE, event(start_time="2026-11-10T01:00:00Z"), CONFIG, cwd="/tmp"))
    finally:
        monkeypatch.undo()
        time.tzset()


def test_moving_a_meeting_to_today_counts_and_an_update_that_sets_no_start_does_not():
    move = {"action": "update", "event_id": "e1", "start_time": f"{TODAY}T16:00:00", "attendees": ["a@example.com"],
            "user_google_email": "me@example.com"}
    assert same_day(guards.check(MANAGE, move, CONFIG, cwd="/tmp"))
    retitle = {"action": "update", "event_id": "e1", "summary": "Follow-up (30 min)", "attendees": ["a@example.com"],
               "user_google_email": "me@example.com"}
    reason = guards.check(MANAGE, retitle, CONFIG, cwd="/tmp")
    assert "approval" in reason and not same_day(reason)


def test_moving_an_existing_meeting_to_today_counts_though_the_call_names_no_guests():
    """The guests are on the event, not in the call; only a write that emails no one is exempt."""
    for tool, call in ((MANAGE, {"action": "update", "event_id": "e1", "start_time": f"{TODAY}T16:00:00"}),
                       ("mcp__gcal__update_event", {"eventId": "e1", "startTime": f"{TODAY}T16:00:00"}),
                       ("mcp__planner__planner-calendar-update-events",
                        {"updates": [{"updateType": "UPDATE", "event": {"eventId": "e1"},
                                      "update": {"period": {"type": "DATE_TIME", "start": {"dateTime": f"{TODAY}T16:00:00"}}}}]})):
        reason = guards.check(tool, {**call, "user_google_email": "me@example.com"}, CONFIG, cwd="/tmp")
        assert same_day(reason) and "moves" in reason, (tool, reason)
    quiet = {"action": "update", "event_id": "e1", "start_time": f"{TODAY}T16:00:00", "send_updates": "none",
             "user_google_email": "me@example.com"}
    assert guards.check(MANAGE, quiet, CONFIG, cwd="/tmp") is None


def test_people_being_removed_and_rooms_are_not_invited_guests():
    call = {"eventId": "e1", "summary": "Focus", "removedAttendeeEmails": ["a@example.com"], "user_google_email": "me@example.com"}
    reason = guards.check("mcp__gcal__update_event", call, CONFIG, cwd="/tmp")
    assert "approval" in reason and not same_day(reason)  # no start in the call, and nobody added
    room = event(attendees=[{"email": "c_18abc@resource.calendar.google.com", "resource": True}])
    reason = guards.check(CREATE, room, CONFIG, cwd="/tmp")
    assert "approval" in reason and not same_day(reason)


def test_participants_are_guests_too():
    call = {"summary": "Follow-up", "start_time": f"{TODAY}T15:00:00", "participants": ["a@example.com"]}
    assert same_day(guards.check(CREATE, call, CONFIG, cwd="/tmp"))


def test_a_local_time_with_a_named_zone_is_read_in_that_zone(monkeypatch):
    import time
    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    try:  # 00:30 on the 10th in Tokyo is 10:30 on the 9th in New York
        call = {"summary": "Follow-up", "startTime": "2026-11-10T00:30:00", "timeZone": "Asia/Tokyo", "attendees": [{"email": "a@example.com"}]}
        assert same_day(guards.check("mcp__gcal__create_event", call, {**CONFIG, "send_tools": ["mcp__gcal__*"]}, cwd="/tmp"))
        later = {**call, "startTime": "2026-11-10T23:30:00"}  # 09:30 on the 10th in New York
        assert not same_day(guards.check("mcp__gcal__create_event", later, {**CONFIG, "send_tools": ["mcp__gcal__*"]}, cwd="/tmp"))
    finally:
        monkeypatch.undo()
        time.tzset()


# --- found by an independent review of the first version (2026-11-11) -----------------------------


def test_a_tool_named_move_event_is_held_too():
    call = {"event_id": "e1", "start_time": f"{TODAY}T16:00:00", "user_google_email": "me@example.com"}
    assert same_day(guards.check("mcp__calendar__move_event", call, CONFIG, cwd="/tmp"))
    later = guards.check("mcp__calendar__move_event", {**call, "start_time": f"{TOMORROW}T16:00:00"}, CONFIG, cwd="/tmp")
    assert later and "approval" in later and not same_day(later)  # moving a meeting notifies its guests


def test_guests_nested_inside_the_call_are_not_a_quiet_write():
    call = {"event": {"summary": "Follow-up", "start": f"{TODAY}T15:00", "attendees": ["a@example.com"]}, "send_updates": "none"}
    assert same_day(guards.check(CREATE, call, CONFIG, cwd="/tmp"))
    tomorrow = {"event": {"summary": "Follow-up", "start": f"{TOMORROW}T15:00", "attendees": ["a@example.com"]}, "send_updates": "none"}
    assert "approval" in guards.check(CREATE, tomorrow, CONFIG, cwd="/tmp")  # adding guests is never quiet


def test_only_a_guests_address_can_exempt_a_meeting_and_only_its_own_meeting():
    named_like = event(attendees=[{"email": "guest@example.com", "displayName": "chief@example.com"}])
    assert same_day(guards.check(CREATE, named_like, CONFIG, cwd="/tmp"))
    batch = {"events": [{"title": "With the chief", "start": f"{TODAY}T10:00", "attendees": [{"email": "chief@example.com"}]},
                        {"title": "With a guest", "start": f"{TODAY}T16:00", "attendees": [{"email": "b@example.com"}]}]}
    reason = guards.check("mcp__planner__planner-calendar-create-events", batch, CONFIG, cwd="/tmp")
    assert same_day(reason) and "1 other" in reason
    graph = event(attendees=[{"emailAddress": {"address": "chief@example.com", "name": "The Chief"}, "type": "required"}])
    assert not same_day(guards.check(CREATE, graph, CONFIG, cwd="/tmp"))


def test_a_time_zone_this_machine_cannot_read_is_sent_back_rather_than_guessed(monkeypatch):
    import time
    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    try:  # 09:00 on the 10th in Tokyo is 19:00 on the 9th in New York; the name is a Windows one
        call = {"subject": "Follow-up", "start": {"dateTime": "2026-11-10T09:00:00", "timeZone": "Tokyo Standard Time"},
                "attendees": [{"emailAddress": {"address": "a@example.com"}}]}
        reason = guards.check(CREATE, call, CONFIG, cwd="/tmp")
        assert reason and "Tokyo Standard Time" in reason and "offset" in reason and "approve" not in reason
        far = {**call, "start": {"dateTime": "2026-11-13T09:00:00", "timeZone": "Tokyo Standard Time"}}
        ordinary = guards.check(CREATE, far, CONFIG, cwd="/tmp")
        assert "approval" in ordinary and "Tokyo Standard Time" not in ordinary  # four days out cannot be today anywhere
    finally:
        monkeypatch.undo()
        time.tzset()


def test_an_update_that_sets_an_empty_guest_list_names_no_guests():
    hold = {"action": "update", "event_id": "e1", "start_time": f"{TODAY}T16:00:00", "attendees": [], "user_google_email": "me@example.com"}
    reason = guards.check(MANAGE, hold, CONFIG, cwd="/tmp")
    assert "approval" in reason and not same_day(reason)


@pytest.mark.parametrize("start", ["0001-01-01T00:00:00+14:00", "9999-12-31T23:59:59-12:00", "2026-13-45T99:99", "", "today"])
def test_no_start_makes_the_guard_raise(start):
    reason = guards.check(CREATE, event(start_time=start), CONFIG, cwd="/tmp")
    assert reason and "approval" in reason


def test_a_send_window_never_covers_a_meeting_today():
    config = {**CONFIG, "send_window_signatures": ["Helperbot"]}
    sends.open_window(1, ["calendar"], count=5)
    signed = {"description": "Agenda attached. Helperbot, sent under standing direction"}
    assert guards.check(CREATE, event(TOMORROW, **signed), config, cwd="/tmp") is None  # the window covers it
    assert same_day(guards.check(CREATE, event(**signed), config, cwd="/tmp"))


@pytest.mark.parametrize("broken", ["yes", {"exempt": "chief@example.com"}, {"exempt": [1]}])
def test_a_setting_that_cannot_be_read_blocks_calendar_writes_and_nothing_else(broken):
    config = {**CONFIG, "same_day_meetings": broken}
    reason = guards.check(CREATE, event(TOMORROW), config, cwd="/tmp")
    assert "same_day_meetings" in reason and "approve" not in reason
    assert "same_day_meetings" not in (guards.check("mcp__slack__slack_send_message", {"channel_id": "C1", "message": "Hello."}, config) or "")
