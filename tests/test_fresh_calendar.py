"""A message that names a clock time goes out on a fresh read of the calendar.

2026-11-12: a meeting request offered a time that a new invitation, arrived half an hour earlier, overlapped. The
calendar had been read when the message was drafted, and the draft then waited for its approval. Every send waits
for one, so every offer of a time has that window. The guard cannot know that a message proposes a meeting; it can
know that its words name a clock time and when this session last read a calendar. Replayed over recorded messages
(2026-11-13): of 445 distinct messages sent to people on 75 days, 145 named a clock time, and the session had read a
calendar in the ten minutes before for 59 of them; of the 37 with words of offering beside the time, for 20.
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


def read_calendar(minutes_ago=1.0, tool="mcp__workspace__get_events", error=False, result=True, stamp=None):
    at = stamp or (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")
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


def test_a_list_of_some_sessions_events_is_no_calendar():
    """A tool that lists a session's events ends as a calendar read does, and is none."""
    read_calendar(tool="mcp__ccd_session_mgmt__list_events")
    read_calendar(tool="mcp__notes__notion-list-session-events")
    assert stale(ask())


def test_the_config_names_more_tools_that_read_a_calendar():
    read_calendar(tool="mcp__cal__agenda_for_day")
    assert stale(ask())
    assert ordinary(ask(config={**CONFIG, "fresh_calendar": {"reads": ["agenda_for_day"]}}))


@pytest.mark.parametrize("body", ["Does 3:30 suit you?", "Let's say 15:30 on Thursday.", "I'm free at 3 pm.", "How about 11am?",
                                  "Thursday, 3:30 p.m. Eastern.", "The call is at 9:05.", "Shall we say 7.30 pm?", "Jeudi 15h30 ?",
                                  "I can do 3:30p.", "Um 14:00h.", "Around 3PMish."])
def test_a_clock_time_in_any_common_form_is_one(body):
    assert stale(ask(given=mail(body)))


@pytest.mark.parametrize("body", ["I'll send the three items on Thursday.", "Version 2.10 is out.", "It costs $15 a seat.",
                                  "Due 2026-11-17.", "The ratio is 16:9 on that screen.", "Thursday afternoon suits me.",
                                  "See section 3 of the plan, pm me if it is unclear.", "The run took 1:23:45 in all.",
                                  "It is at https://example.com/watch?t=1:30 on the page.",
                                  "The job logged 2026-11-13T10:20:00-05:00 and stopped."])
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



# --- after a review round (2026-11-13) ------------------------------------------------------------------------------

ID_NAMED = "mcp__0a1b2c3d-0000-4000-8000-000000000000__"


@pytest.mark.parametrize("tool, given", [
    (ID_NAMED + "reply", {"messageId": "m1", "htmlBody": "<p>Would 3:30 pm work?</p>"}),
    (ID_NAMED + "update_draft", {"draftId": "d1", "htmlBody": "<p>Would 3:30 pm work?</p>"}),
    ("messages_send", {"to": "+15550100", "text": "See you at 3:30 pm"}),
])
def test_a_message_by_a_connector_the_guard_has_no_name_for_is_a_message_too(tool, given):
    """The mail connector's server is named by an id, and its reply names no recipient: the rule had no channel for
    it, so the incident's own kind of message asked only the ordinary code."""
    assert stale(ask(tool, given))


def test_a_calendar_write_and_a_harnesss_own_tool_are_none_of_this_rules(monkeypatch):
    """A mail product's calendar tool has `mail` in its name and was held as a message; the code of its own then
    released a meeting on today without the code a same-day meeting has."""
    from datetime import date
    monkeypatch.setattr(guards, "_today", lambda: date(2026, 11, 9), raising=False)
    config = {**CONFIG, "send_tools": CONFIG["send_tools"] + ["mcp__*__create_event"], "same_day_meetings": {"exempt": []}}
    event = {"summary": "Sync at 2:00 pm", "start_time": "2026-11-09T14:00:00", "end_time": "2026-11-09T14:30:00",
             "attendees": ["a@example.com"], "user_google_email": "me@example.com"}
    reason = ask("mcp__fastmail__create_event", event, config)
    assert "same-day" in reason and "names a time" not in reason
    assert "names a time" not in (ask("SendUserFile", {"files": ["plan.md"], "caption": "The call is at 3:30 pm."}) or "")


def test_a_message_that_went_on_one_code_spends_the_other():
    """With the ordinary code typed and the read grown old, the code of its own released the message, and the
    ordinary grant stayed live: an identical call after a fresh read went a second time on it."""
    read_calendar(minutes_ago=1)
    first = ask()
    assert ordinary(first)
    _approve(first)
    age_reads(30)
    held = ask()
    assert stale(held)
    _approve(held)
    assert ask() is None
    read_calendar(minutes_ago=0.1)
    assert ordinary(ask())                                               # a second copy asks again
    other = mail("Would 4:15 pm on Thursday work for you?")
    age_reads(30)
    held = ask(given=other)                                              # the code of its own is asked for and not typed
    assert stale(held)
    read_calendar(minutes_ago=0.1)
    again = ask(given=other)
    assert ordinary(again)
    _approve(again)
    assert ask(given=other) is None
    age_reads(30)
    waiting = _approve(held, grant=False)                                # the earlier request went with the message: its code opens nothing
    from synthesis import approvals
    assert waiting not in approvals.pending()


def test_the_code_of_its_own_releases_the_message_whatever_the_read_then_is():
    held = ask()
    _approve(held)
    read_calendar(minutes_ago=0.1)
    assert ask() is None                                                 # he approved this text as it is
    age_reads(30)
    assert stale(ask())


@pytest.mark.parametrize("tool", ["mcp__sentry__search_events", "mcp__github__list_events", ID_NAMED + "list_events"])
def test_a_tool_that_only_ends_like_a_calendar_read_is_none(tool):
    """Any name that ended in `list_events` or `search_events` counted, an error tracker's and a repository's
    among them. A calendar's tool says so in its name, or the setting names it."""
    read_calendar(tool=tool)
    assert stale(ask())


@pytest.mark.parametrize("reads", [[ID_NAMED + "list_events"], ["mcp__0a1b2c3d-*__list_events"], ["list_events"]])
def test_the_setting_names_a_calendar_tool_by_its_whole_name_a_pattern_or_its_end(reads):
    read_calendar(tool=ID_NAMED + "list_events")
    assert ordinary(ask(config={**CONFIG, "fresh_calendar": {"reads": reads}}))


def test_a_read_dated_ahead_of_the_clock_is_no_read_of_the_last_minutes_and_a_time_with_no_zone_is_universal():
    read_calendar(minutes_ago=-120)
    assert stale(ask())
    read_calendar(stamp=(datetime.now(timezone.utc) - timedelta(minutes=2)).replace(tzinfo=None).isoformat())
    assert ordinary(ask())


def test_many_reads_that_failed_cost_one_look_at_the_record(pace):
    with RECORD.open("a", encoding="utf-8") as handle:
        for n in range(3000):
            handle.write(json.dumps({"type": "assistant", "timestamp": "2026-11-13T09:00:00.000Z", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": f"toolu_{n:05}", "name": "mcp__workspace__get_events", "input": {}}]}}) + "\n")
            handle.write(json.dumps({"type": "user", "timestamp": "2026-11-13T09:00:01.000Z", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": f"toolu_{n:05}", "is_error": n % 2 == 0, "content": "x" * 600}]}}) + "\n")
    begun = time.perf_counter()
    assert stale(ask())
    assert time.perf_counter() - begun < 0.6 * pace


def test_in_a_harness_whose_record_the_guard_does_not_read_the_hold_says_so(tmp_path):
    """In Codex and Muse the read is never seen, so the hold asked for a read that could not clear it."""
    rollout = tmp_path / "rollout-2026-11-13T09-00-00-0a1b2c3d.jsonl"
    rollout.write_text(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "type": "response_item",
                                   "payload": {"type": "function_call", "name": "get_events", "call_id": "c1", "arguments": "{}"}}) + "\n", encoding="utf-8")
    held = guards.check(MAIL, mail(), CONFIG, cwd="/tmp", session={"transcript_path": str(rollout), "session_id": "S-principal"})
    assert stale(held) and "cannot see" in held and "as it is" in held and "make this identical call again:" not in held


def test_a_text_sent_from_the_shell_that_names_a_time_is_held():
    command = """osascript -e 'tell application "Messages" to send "See you at 3:30 pm" to buddy "+15550100"'"""
    held = guards.check("Bash", {"command": command}, CONFIG, cwd="/tmp", session=SESSION)
    assert stale(held) and "3:30 pm" in held
    read_calendar(minutes_ago=0.1)
    reason = guards.check("Bash", {"command": command}, CONFIG, cwd="/tmp", session=SESSION)
    assert reason and "posts to messages" in reason and "names a time" not in reason
    quiet = """osascript -e 'tell application "Messages" to send "On my way" to buddy "+15550100"'"""
    assert "names a time" not in guards.check("Bash", {"command": quiet}, CONFIG, cwd="/tmp", session=SESSION)
