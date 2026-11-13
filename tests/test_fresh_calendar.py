"""A message that names a clock time goes out on a fresh read of the calendar.

2026-11-12: a meeting request offered a time that a new invitation, arrived half an hour earlier, overlapped. The
calendar had been read when the message was drafted, and the draft then waited for its approval. Every send waits
for one, so every offer of a time has that window. The guard cannot know that a message proposes a meeting; it can
know that its words name a clock time and when this session last read a calendar. Measured before it was built
(2026-11-13): of 439 distinct messages to people on 73 days, 144 named a clock time, and the session had read a
calendar in the ten minutes before for 39 of them; of the 35 with words of offering beside the time, for 6.
"""

import json
import time
from datetime import datetime, timedelta, timezone

import pytest

from synthesis import guards, sends

MAIL, SLACK, DRAFT, EVENT = ("mcp__workspace__send_gmail_message", "mcp__slack__slack_send_message",
                             "mcp__workspace__draft_gmail_message", "mcp__workspace__manage_event")
CONFIG = {"send_tools": ["mcp__*__send_gmail_message", "mcp__*__slack_send_message", "mcp__*__draft_gmail_message", "mcp__*__manage_event"],
          "fresh_calendar": {},
          "account_routing": {"default_account": "me@example.com",
                              "workspaces": {"/nowhere": {"account": "me@work.example", "aliases": ["me@alias.example"]}}}}
OFFER = "Would Tuesday at 2:00 pm work for you? I can also do 3:30."


def mail(body=OFFER, **more):
    return {"to": "a@example.com", "subject": "A time to meet", "body": f"<p>{body}</p>", "body_format": "html",
            "user_google_email": "me@example.com", **more}


@pytest.fixture(autouse=True)
def _session(principal):
    global _approve, RECORD, SESSION
    _approve, RECORD = principal, principal.transcript
    RECORD.touch()
    SESSION = {"transcript_path": str(RECORD), "session_id": "S-principal"}


def read_calendar(minutes_ago=1.0, tool="mcp__workspace__get_events", error=False, result=True):
    at = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")
    ident = f"toolu_{time.time_ns()}"
    with RECORD.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "assistant", "timestamp": at, "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": ident, "name": tool, "input": {"time_min": "2026-11-17"}}]}}) + "\n")
        if result:
            handle.write(json.dumps({"type": "user", "timestamp": at, "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": ident, "is_error": error, "content": "[]"}]}}) + "\n")


def age_reads(minutes):
    """Every calendar read in the record, moved that much further back."""
    lines = []
    for line in RECORD.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if any(isinstance(part, dict) and part.get("type") in ("tool_use", "tool_result") for part in entry["message"].get("content") or []
               if isinstance(entry["message"].get("content"), list)):
            then = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")) - timedelta(minutes=minutes)
            entry["timestamp"] = then.isoformat().replace("+00:00", "Z")
        lines.append(json.dumps(entry))
    RECORD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ask(tool=MAIL, given=None, config=CONFIG):
    return guards.check(tool, mail() if given is None else given, config, cwd="/tmp", session=SESSION)


def stale(reason) -> bool:
    return bool(reason) and "names a time" in reason and "calendar" in reason


def ordinary(reason) -> bool:
    return bool(reason) and "approval of this exact message" in reason and "names a time" not in reason


def test_the_rule_is_off_unless_the_config_turns_it_on():
    off = {key: value for key, value in CONFIG.items() if key != "fresh_calendar"}
    assert ordinary(ask(config=off)) and ordinary(ask(config={**CONFIG, "fresh_calendar": False}))


def test_a_message_that_names_a_time_waits_for_a_calendar_read_before_any_code_is_asked():
    reason = ask()
    assert stale(reason) and "2:00 pm" in reason and "identical call again" in reason
    assert "has not read a calendar" in reason and "10 minutes" in reason
    read_calendar(minutes_ago=2)
    reason = ask()
    assert ordinary(reason)                                              # now he is shown a text the check will not change
    _approve(reason)
    assert ask() is None


def test_the_question_is_asked_again_when_the_approved_message_goes_and_the_approval_stands():
    """The incident's window: the read was fresh at the draft and half an hour old at the send."""
    read_calendar(minutes_ago=1)
    reason = ask()
    assert ordinary(reason)
    _approve(reason)
    age_reads(30)
    held = ask()
    assert stale(held) and "31 minutes ago" in held or "30 minutes ago" in held
    assert "stands" in held                                              # the code he typed is not spent by this hold
    read_calendar(minutes_ago=0.1)
    assert ask() is None                                                 # the same approval, after the read


def test_a_code_of_its_own_releases_a_message_whose_time_is_no_calendars():
    """A status note that says when a release went out, or a session with no calendar to read: the principal can
    approve the message as it is, by a code whose request says what it waives."""
    body = "The release went out at 03:38 and every harness is on it."
    held = ask(given=mail(body))
    assert stale(held) and "03:38" in held and "as it is" in held
    _approve(held)
    assert ask(given=mail(body)) is None                                 # no calendar read, and no second code
    assert stale(ask(given=mail(body)))                                  # one approval, one message
    assert stale(ask(given=mail(body + " See you at 4:00 pm.")))         # and it covered that text alone


def test_the_ordinary_approval_does_not_waive_the_read():
    read_calendar(minutes_ago=1)
    _approve(ask())
    age_reads(45)
    assert stale(ask())
    assert stale(ask())                                                  # asked as often as it is tried, and never spent


@pytest.mark.parametrize("how", ["failed", "no result yet", "a write", "too old"])
def test_only_a_calendar_read_that_succeeded_inside_the_ten_minutes_counts(how):
    if how == "failed":
        read_calendar(error=True)
    elif how == "no result yet":
        read_calendar(result=False)
    elif how == "a write":
        read_calendar(tool="mcp__workspace__manage_event")
    else:
        read_calendar(minutes_ago=11)
    assert stale(ask())
    read_calendar(minutes_ago=9)
    assert ordinary(ask())


@pytest.mark.parametrize("tool", ["mcp__workspace__get_events", "mcp__apple-calendar__list_events", "mcp__apple-calendar__search_events",
                                  "mcp__apple-calendar__list_all_events", "mcp__gcal__get_event", "mcp__workspace__query_freebusy",
                                  "mcp__gcal__suggest_time", "mcp__notion__notion-calendar-list-events"])
def test_each_way_of_reading_a_calendar_is_known(tool):
    read_calendar(tool=tool)
    assert ordinary(ask())


def test_the_config_names_more_tools_that_read_a_calendar():
    read_calendar(tool="mcp__cal__agenda_for_day")
    assert stale(ask())
    assert ordinary(ask(config={**CONFIG, "fresh_calendar": {"reads": ["agenda_for_day"]}}))


@pytest.mark.parametrize("body", ["Does 3:30 suit you?", "Let's say 15:30 on Thursday.", "I'm free at 3 pm.", "How about 11am?",
                                  "Thursday, 3:30 p.m. Eastern.", "The call is at 9:05."])
def test_a_clock_time_in_any_common_form_is_one(body):
    assert stale(ask(given=mail(body)))


@pytest.mark.parametrize("body", ["I'll send the three items on Thursday.", "Version 2.10 is out.", "It costs $15 a seat.",
                                  "Due 2026-11-17.", "The ratio is 16:9 on that screen.", "Thursday afternoon suits me.",
                                  "See section 3 of the plan, pm me if it is unclear."])
def test_what_names_no_clock_time_is_not_held_for_one(body):
    assert ordinary(ask(given=mail(body, subject="A note")))


def test_mail_a_draft_and_a_chat_message_are_held_and_a_calendar_write_is_not_this_rules():
    assert stale(ask(SLACK, {"channel_id": "C1", "message": OFFER}))
    assert stale(ask(DRAFT, mail()))
    event = {"action": "create", "summary": "Sync at 2:00 pm", "start_time": "2030-01-08T14:00:00", "end_time": "2030-01-08T14:30:00",
             "attendees": ["a@example.com"], "user_google_email": "me@example.com"}
    reason = ask(EVENT, event)
    assert reason and "names a time" not in reason                       # an event states its own time: the calendar rules judge it


def test_a_send_window_does_not_waive_the_read():
    config = {**CONFIG, "send_window_signatures": [r"I wrote this with my assistant"]}
    signed = {"channel_id": "C1", "message": OFFER + " I wrote this with my assistant."}
    sends.open_window(1, ["slack"], count=3)
    try:
        assert stale(ask(SLACK, signed, config))
        read_calendar()
        assert ask(SLACK, signed, config) is None                        # the window covers it once the calendar is read
    finally:
        sends.close_window()


@pytest.mark.parametrize("minutes, fresh", [(30, True), (5, False)])
def test_the_minutes_are_a_setting(minutes, fresh):
    read_calendar(minutes_ago=20 if fresh else 7)
    reason = ask(config={**CONFIG, "fresh_calendar": {"minutes": minutes}})
    assert ordinary(reason) if fresh else stale(reason) and f"{minutes} minutes" in reason


@pytest.mark.parametrize("wrong", [None, True, 1, "on", [], {"minutes": 0}, {"minutes": 61}, {"minutes": "ten"}, {"minutes": True},
                                   {"reads": "get_events"}, {"reads": [7]}, {"window": 10}])
def test_a_setting_of_another_shape_refuses_the_send_and_says_why(wrong):
    reason = ask(config={**CONFIG, "fresh_calendar": wrong})
    assert reason and "fresh_calendar" in reason and "approval of this exact message" not in reason


def test_a_session_with_no_record_to_read_is_held_and_can_be_released_by_the_code():
    held = guards.check(MAIL, mail(), CONFIG, cwd="/tmp", session={"transcript_path": "/nowhere/at/all.jsonl", "session_id": "S-principal"})
    assert stale(held) and "as it is" in held
