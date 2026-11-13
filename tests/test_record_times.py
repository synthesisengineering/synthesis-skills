"""The time an entry gives for itself is not later than the commit that records it, and is no rounding of the present.

A record's entry states its own time in four places: the line opens with the day and a time, a parenthesis opens
with them, (in a session log) a list item opens with a time under a heading that names the day, or the line opens
with a word for what was done and then the time. Measured on thirty
days of commits to twenty-seven knowledge repositories (2026-11-12): of 688 such stamps, 36 named a minute that had
not come when they were committed and 111 rounded the present ("18:3x", "about 18:35") when the clock could be read.
A time inside an entry's text says nothing of the kind: three in ten of those are later than the commit, and rightly
(a meeting, a deadline, a scheduled wake).
"""

import os
import re
from datetime import datetime, timedelta, timezone

import pytest

from synthesis import commit_check as cc

EST = timezone(timedelta(hours=-5))
try:
    ZONES = bool(cc.ZoneInfo("America/New_York"))
except Exception:  # an interpreter with no zoneinfo, or a machine with no zone data
    ZONES = False
NOW = datetime(2026, 11, 12, 18, 40, 20, tzinfo=EST)  # the commit: 18:40 on the twelfth
LOG = "projects/alpha/sessions/2026-11.md"
RECORD = "projects/alpha/REFERENCE.md"


def said(path, *lines, settings=None, now=NOW, before=()):
    """What the check says of these lines added to one file; `before` stands above them in the file."""
    whole = [*before, *lines]
    added = [(path.encode(), len(before) + number, line.encode()) for number, line in enumerate(lines, 1)]
    return cc.record_times(added, {} if settings is None else settings, now, lambda name: "\n".join(whole))


@pytest.mark.parametrize("line, minutes", [
    ("- **2026-11-12 18:54, the release is out.** Tag and stable agree.", 14),
    ("### 2026-11-12 19:05 — the evening's work", 25),
    ("## 2026-11-12 18:41", 1),
    ("- [x] 2026-11-12 18:45: the suite passed", 5),
    ("2026-11-12T18:54-05:00 merged", 14),
    ("- **2026-11-12 18:45 to 18:55, the review round.**", 15),          # a range is read by its later end
    ("- 2026-11-12, 18:50: told the owner", 10),
    ("- **2026-11-12 at 18:52**, the answer came", 12),
])
def test_a_line_that_opens_with_today_and_a_minute_that_has_not_come_is_refused(line, minutes):
    found = said(RECORD, line)
    assert len(found) == 1 and found[0].startswith(f"{RECORD}:1: ") and f"{minutes} min after" in found[0]
    assert "18:40" in found[0] and "date" in found[0]  # the commit's own minute, and where a time comes from


@pytest.mark.parametrize("line, minutes", [
    ("He approved the move (11-12 18:54: in the question dialog).", 14),
    ("- [ ] 17.3 (added 11-12 18:46, M36 A to F) Each of the six checks", 6),
    ("The connector answers again (as of 2026-11-12 19:10, read from its health check).", 30),
    ("(2026-11-12 18:56) the nine held lines", 16),
])
def test_a_parenthesis_that_opens_with_today_and_a_minute_that_has_not_come_is_refused(line, minutes):
    found = said(RECORD, line)
    assert len(found) == 1 and f"{minutes} min after" in found[0]


@pytest.mark.parametrize("line, minutes", [
    ("### 2026-11-12 18:05 CDT", 25),      # the central clock, whichever season its label names: 19:05 here
    ("### 2026-11-12 17:50 CST", 10),      # an hour behind: 18:50 here
    ("- 2026-11-12 23:45 UTC: the job ran", 5),
    ("- 2026-11-12 23:46Z: the job ran", 6),
    ("(11-12 15:50 PST: their reply)", 10),
    ("- 2026-11-12 18:45 -05:00: pushed", 5),
])
def test_a_zone_the_stamp_names_is_honored(line, minutes):
    if not ZONES and re.search(r"\b[ECMP][SD]T\b", line):
        pytest.skip("no zone data on this machine: a region's label is not read here")
    assert f"{minutes} min after" in said(RECORD, line)[0]
    earlier = {"### 2026-11-12 18:05 CDT": "### 2026-11-12 17:39 CDT", "### 2026-11-12 17:50 CST": "### 2026-11-12 17:40 CST",
               "- 2026-11-12 23:45 UTC: the job ran": "- 2026-11-12 23:40 UTC: the job ran",
               "- 2026-11-12 23:46Z: the job ran": "- 2026-11-12 23:40Z: the job ran",
               "(11-12 15:50 PST: their reply)": "(11-12 15:40 PST: their reply)",
               "- 2026-11-12 18:45 -05:00: pushed": "- 2026-11-12 18:40 -05:00: pushed"}[line]
    assert said(RECORD, earlier) == []


def test_a_region_label_is_read_by_the_zone_it_names_and_one_this_machine_cannot_resolve_passes(monkeypatch):
    try:
        cc.ZoneInfo("America/New_York")
    except Exception:  # no zone data here, or no zoneinfo: the second half below is this machine's whole case
        assert said(RECORD, "- **2026-11-12 18:54 ET, done.**") == []
        return
    assert "14 min after" in said(RECORD, "- **2026-11-12 18:54 ET, done.**")[0]      # eastern time, the commit's own zone
    assert "14 min after" in said(RECORD, "- **2026-11-12 17:54 CT, done.**")[0]
    assert said(RECORD, "- **2026-11-12 18:30 ET, done.**") == []
    monkeypatch.setattr(cc, "ZoneInfo", None)  # a system with no zone data
    assert said(RECORD, "- **2026-11-12 18:54 ET, done.**") == []                      # what cannot be read is not refused
    assert "14 min after" in said(RECORD, "- **2026-11-12 18:54, done.**")[0]         # and one with no label still is


@pytest.mark.parametrize("line", [
    "- **2026-11-12 18:3x, pushed the branch.**",
    "(11-12 about 18:35: merged)",
    "(11-12 around 18:30, the reply)",
    "- 2026-11-12 ~18:40: asked",
    "- 2026-11-12 18:40ish: asked",
    "(11-12 roughly 18:25: the run ended)",                                 # fifteen minutes back, to the minute
    "- **2026-11-12 18:5x, the release.**",                                 # rounded, and not yet come
    "(11-12 about 19:00: the call)",
])
def test_a_rounding_of_the_present_is_refused(line):
    found = said(RECORD, line)
    assert len(found) == 1 and "rounds" in found[0] and "18:40" in found[0]


@pytest.mark.parametrize("line", [
    "- **2026-11-12 18:40, pushed the branch.**",                           # the commit's own minute
    "- **2026-11-12 18:39, pushed the branch.**",
    "### 2026-11-12 09:15 — morning",
    "(11-12 about 17:00: the call with the owner)",                         # a moment long past may be all the writer knows
    "- **2026-11-12 18:2x, the run ended.**",                               # 18:20 at the earliest: more than fifteen minutes back
    "(11-12 around 18:24, the reply)",
    "- **2026-11-11 23:50, yesterday's last entry.**",                      # another day's entry
    "(11-13 09:00: the review is booked)",                                  # tomorrow is a plan, not a record
    "(2025-11-12 19:00: a year ago today)",
    "- The meeting moved to 19:30 today (2026-11-12), and the deadline is 23:59.",   # times inside the text
    "- [ ] Review at 20:00 with the owner",
    "- Released at 22:12 on 11-12; the doctor read 72 ms.",
    "The wake fires at 19:21 (hourly, cron 250c5c33).",
    "- **2026-11-12, the release is out.** At 19:00 the seats are told.",   # the day opens the line, the time does not
    "Version 18:54 of the build (2026-11-12).",
    "",
])
def test_what_is_no_stamp_of_today_later_than_now_passes(line):
    assert said(RECORD, line) == []


def test_a_list_item_that_opens_with_a_time_is_an_entrys_stamp_only_in_a_session_log_under_todays_heading():
    today, yesterday = ["## 2026-11-12 — the board requests", ""], ["## 2026-11-11", ""]
    assert "14 min after" in said(LOG, "- 18:54 ET: pushed the branch", before=today)[0]
    assert "14 min after" in said(LOG, "- **18:54 EST, board:** told the seat", before=today)[0]
    assert "rounds" in said(LOG, "- 18:3x: pushed the branch", before=today)[0]
    assert said(LOG, "- 18:40: pushed the branch", before=today) == []
    assert said(LOG, "- 18:54: pushed the branch", before=yesterday) == []           # a heading that names another day
    assert said(LOG, "- 18:54: pushed the branch", before=["# Sessions", ""]) == []   # or no day at all
    assert said(LOG, "- 18:54: pushed", before=today + ["### 2026-11-10, carried over", ""]) == []   # the nearest dated heading decides
    assert "14 min after" in said(LOG, "- 18:54: pushed", before=today + ["### What was done", ""])[0]  # an undated one does not
    # Anywhere else such a line is a schedule: a plan, a meeting's preparation, a ritual's notes.
    for path in ("daily-plans/2026-11-12.md", "projects/alpha/CONTEXT.md", "meetings/2026-11-12-prep.md"):
        assert said(path, "- 19:30 dinner with the board", before=today) == []


def test_a_wrapped_line_that_happens_to_begin_with_a_time_is_no_entry():
    """Replayed over thirty days of real commits before it shipped, the first form of this check refused five lines
    of session logs that were the wrapped rest of a sentence and began with a time by chance (a call at 20:00, a
    message at 15:17:44), 55 to 1,015 minutes "after" their commits. An entry opens with a mark: a list item or a
    heading. A line set in from the margin with no mark continues the line above it."""
    today = ["## 2026-11-12 — the day-end", "", "- The sweep found four items, the last of them due at"]
    for rest in ("  20:00 ET), 15 re-dated to Monday with reasons; 9 new items.",
                 "  18:56:31); the second by chat after the first was refused;",
                 "  19:00 and 20:30, Monday at 17:00, all eastern.",
                 "    ~18:40 the second run began, by the log's own count",
                 "  2026-11-12 19:30 with the owner, and the notes go to the project.",
                 "  about 18:35 the reply came"):
        assert said(LOG, rest, before=today) == [], rest
    assert said(RECORD, "  2026-11-12 19:30 with the owner, and the notes go to the project.", before=today) == []
    for unmarked in ("19:30 dinner with the board", "~18:40 the second run began"):       # at the margin, and no list item
        assert said(LOG, unmarked, before=today[:2]) == [], unmarked
    # A list item set in under another is still a list item, and a heading that opens with a time is an entry.
    assert "14 min after" in said(LOG, "  - 18:54: pushed the branch", before=today)[0]
    assert "14 min after" in said(LOG, "#### 18:54 EST — the push", before=today)[0]
    assert "rounds" in said(LOG, "  * **18:3x**, told the seat", before=today)[0]
    assert "14 min after" in said(RECORD, "2026-11-12 18:54 the release went out.")[0]     # a dated line at the margin opens an entry


def test_only_markdown_records_are_read_and_transcripts_and_skipped_folders_are_not():
    late = "- **2026-11-12 18:54, done.**"
    assert said("projects/alpha/notes.MD", late) != []
    for path in ("projects/alpha/notes.txt", "synthesis/guards.py", "data/log.jsonl",
                 "transcripts/2026/11/2026-11-12-standup.md", "projects/alpha/transcripts/call.md"):
        assert said(path, late) == [], path                                   # a transcript's lines carry other people's times
    skip = {"skip": ["daily-plans/**", "*/drafts/*"]}
    assert said("daily-plans/2026-11-12.md", late, settings=skip) == []
    assert said("projects/drafts/reply.md", late, settings=skip) == []
    assert said(RECORD, late, settings=skip) != []
    assert said("projects/alpha/notes.markdown", late) != []
    for path in ("Transcripts/call.md", "projects/alpha/meeting-transcripts/2026-11-12.md"):
        assert said(path, late) == [], path                                   # whatever a folder of transcripts is called
    for folder in ("daily-plans", "daily-plans/", "./daily-plans", "projects/alpha"):   # a folder from the root, as it is written
        assert said(f"{folder.strip('./')}/2026-11-12.md", late, settings={"skip": [folder]}) == [], folder
    assert said("projects/daily-plans-old/x.md", late, settings={"skip": ["daily-plans"]}) != []       # and no other that begins like it


def test_the_check_runs_only_where_the_config_turns_it_on_and_a_setting_of_another_shape_is_refused():
    late = [(RECORD.encode(), 1, b"- **2026-11-12 18:54, done.**")]
    assert cc.record_times(late, False, NOW, lambda name: "") == []          # no key, or false: the check does not run
    assert cc.record_times(late, {}, NOW, lambda name: "") != []
    for wrong in (None, True, 0, "", "on", ["x"], [], {"skip": "daily-plans/**"}, {"skip": [7]}):  # `null` is no way to say off
        with pytest.raises(cc.Refused, match="record_times"):
            cc.record_times(late, wrong, NOW, lambda name: "")
    for key in ("enabled", "on", "skips", "only"):  # 2026-11-13, a review: `{"enabled": false}` turned the check on
        with pytest.raises(cc.Refused, match=f'"{key}"'):
            cc.record_times(late, {key: False, "skip": []}, NOW, lambda name: "")


def test_each_stamp_of_a_line_is_judged_and_a_line_that_is_not_text_is_passed_over():
    found = said(RECORD, "- **2026-11-12 18:54, done** (11-12 18:50: told; 11-12 18:20: asked)")
    assert len(found) == 2 and "14 min after" in found[0] and "10 min after" in found[1]
    odd = [(RECORD.encode(), 1, b"\xff\xfe- 2026-11-12 18:54 \xff")]
    assert isinstance(cc.record_times(odd, {}, NOW, lambda name: ""), list)


def test_a_commit_is_refused_for_a_stamp_ahead_of_it_and_passes_once_the_time_is_the_clocks(tmp_path, monkeypatch):
    import subprocess
    repo = tmp_path / "kb"
    (repo / "projects" / "alpha" / "sessions").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    monkeypatch.chdir(repo)
    record, log = repo / RECORD, repo / LOG
    record.write_text("# Reference\n\n- **2026-11-12 18:54, written ahead.**\n", encoding="utf-8")
    log.write_text("## 2026-11-12\n\n- 18:3x: a guess at the present\n- 18:39: read from the clock\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], check=True)
    assert cc.problems({}, "S1", str(repo), now=NOW)[0] == []                 # off until the config turns it on
    found = cc.problems({"record_times": {}}, "S1", str(repo), now=NOW)[0]
    assert len(found) == 2 and found[0].startswith(f"{RECORD}:3: ") and found[1].startswith(f"{LOG}:3: ")
    record.write_text("# Reference\n\n- **2026-11-12 18:40, written from the clock.**\n", encoding="utf-8")
    log.write_text("## 2026-11-12\n\n- 18:40: the present, as the clock gives it\n- 18:39: read from the clock\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], check=True)
    assert cc.problems({"record_times": {}}, "S1", str(repo), now=NOW)[0] == []


# --- after the first review round (2026-11-13) --------------------------------------------------------------------
# Counted over the replay's 153 refusals, every stamp that was later than its commit stood at most 30 minutes ahead.
# What the review showed refused wrongly stood far off: a deadline, a schedule, a zone read as local, a merge from
# another zone. The bound is the rule.

@pytest.mark.parametrize("line", [
    "- [x] Send the draft (due 2026-11-12 23:59)",
    "The job is set (next run 2026-11-12 19:21).",
    "- the room (booked for 11-12 19:30)",
    "- the review (moved to 11-12 19:30, with the owner)",
    "- the call (11-12 19:30 to 20:30)",
    "- 2026-11-12 23:59 submit the form",
    "### 2026-11-12 19:30 Board call",
    "- **2026-11-12 19:11, a plan for later.**",                             # 31 minutes ahead
    "- 2026-11-12 23:30 IST: pushed",                                        # hours off, whatever the zone
    "2026-11-12 23:41:07,123 - worker - ERROR the job failed",
    "- 2026-11-12 12:30 am: the nightly run",                                # half past midnight, long past
])
def test_a_time_more_than_half_an_hour_ahead_is_no_mistaken_stamp(line):
    assert said(RECORD, line) == []


def test_the_bound_is_thirty_minutes_after_and_a_rounding_fifteen_before():
    assert "30 min after" in said(RECORD, "- **2026-11-12 19:10, done.**")[0]
    assert said(RECORD, "- **2026-11-12 19:11, done.**") == []
    assert "rounds" in said(RECORD, "- **2026-11-12 about 19:10, done.**")[0]
    assert said(RECORD, "- **2026-11-12 about 19:15, the call.**") == []
    today = ["## 2026-11-12 — the day", ""]
    for line in ("- 19:30 call the owner", "- 23:59 tonight is the deadline", "### 19:30 Board call", "  - 19:30 call the owner"):
        assert said(LOG, line, before=today) == [], line


@pytest.mark.parametrize("line", [
    "- the owner (call 11-12 19:00)", "- the draft (due 2026-11-12 18:55)", "The job (next run 2026-11-12 18:50).",
    "- the room (booked for 11-12 19:00)", "- the review (moved to 11-12 18:55)", "- (at 11-12 18:50 the call starts)",
    "- (by 2026-11-12 19:00, the answer is due)",
])
def test_a_parenthesis_that_opens_with_an_events_words_gives_the_events_time(line):
    """`(call 11-12 19:30)` follows the refusal's own advice, the event's words before its time, and was refused (a
    review, 2026-11-13). A parenthesis is an entry's stamp where it opens with the day, or with one word that says
    what was done then."""
    assert said(RECORD, line) == []


@pytest.mark.parametrize("lead", ["added", "written", "updated", "extended", "deleted", "found", "run", "sent", "as of", "current to", "shown",
                                  "Updated", "As of", "updated:", "closed", "probed", "searched", "released", "verified"])
def test_a_parenthesis_that_opens_with_what_was_done_then_is_a_stamp(lead):
    assert "6 min after" in said(RECORD, f"- the list ({lead} 11-12 18:46, in the plan)")[0]


@pytest.mark.parametrize("word", ["scheduled", "rescheduled", "planned", "expected", "booked", "postponed", "proposed", "offered", "promised",
                                  "declined", "confirmed", "between", "when", "open", "then", "set", "reticulated"])
def test_a_parenthesis_is_a_stamp_only_behind_a_word_the_check_knows(word):
    """A review, 2026-11-13: any word that ended in -ed, -en or -wn made the parenthesis a stamp, so
    `(scheduled 11-12 18:55)` was refused twenty minutes before the call it names. The words are a closed list, each
    saying what was done at that time; a word that is not on it is read as naming the event."""
    assert said(RECORD, f"- Vendor call ({word} 2026-11-12 18:55)") == []


@pytest.mark.parametrize("line", [
    "- [ ] 2026-11-12 18:54 submit the form",
    "1. [ ] 2026-11-12 18:54: call the owner",
])
def test_an_unchecked_box_is_a_plan(line):
    assert said(RECORD, line) == []
    assert said(LOG, "- [ ] 18:54 call the owner", before=["## 2026-11-12", ""]) == []
    assert "14 min after" in said(RECORD, line.replace("[ ]", "[x]"))[0]                  # ticked, it says when it was done
    assert "6 min after" in said(RECORD, "- [ ] 17.3 (added 11-12 18:46) the six checks")[0]   # and an item's own stamp is still one


def test_a_code_fence_is_not_read():
    """A log line pasted into a fence opens with a day and a time, in whatever zone the log keeps."""
    before = ["# Reference", "", "The job's log:", "", "```"]
    inside = ["2026-11-12 18:54:07,123 - worker - ERROR the job failed", "  - 2026-11-12 18:50", "```", "", "- **2026-11-12 18:54, read after the fence.**"]
    found = said(RECORD, *inside, before=before)
    assert len(found) == 1 and found[0].startswith(f"{RECORD}:10: ")
    assert said(RECORD, "- 2026-11-12 18:54 a line", before=["~~~text"]) == []
    assert "14 min after" in said(RECORD, "- 2026-11-12 18:54 a line", before=["```", "x", "```", ""])[0]


@pytest.mark.parametrize("label", ["IST", "CET", "BST", "AEST", "CEST", "JST", "HKT"])
def test_a_zone_the_check_does_not_know_lets_the_stamp_pass(label):
    assert said(RECORD, f"- **2026-11-12 18:54 {label}, done.**") == []


@pytest.mark.parametrize("word", ["TEST", "POST", "SENT", "START", "ALERT:", "DRAFT", "NEXT", "pt 2 of the plan", "et al. signed"])
def test_a_word_after_the_time_is_no_zone(word):
    """A review, 2026-11-13: any capital word ending in T after the time was taken for a zone the check does not
    know, so `18:54 TEST passed` passed; and `et` or `pt` in lower case was read as a region."""
    assert "14 min after" in said(RECORD, f"- 2026-11-12 18:54 {word}")[0]


def test_a_standard_or_daylight_label_names_its_regions_clock():
    """`10:25 EST` written in July means 10:25 on the eastern clock: people keep the winter label all year. Read as
    five hours behind UTC it stood an hour ahead, and a commit made half an hour after it was refused (a review,
    2026-11-13)."""
    try:
        cc.ZoneInfo("America/New_York")
    except Exception:
        pytest.skip("no zone data on this machine: a region's label is not read here")
    summer = datetime(2026, 7, 15, 11, 0, 20, tzinfo=timezone(timedelta(hours=-4)))
    assert said(RECORD, "- 2026-07-15 10:25 EST pushed", now=summer) == []
    assert "10 min after" in said(RECORD, "- 2026-07-15 11:10 EST pushed", now=summer)[0]
    assert "10 min after" in said(RECORD, "- 2026-07-15 08:10 PST pushed", now=summer)[0]
    assert "10 min after" in said(RECORD, "- 2026-11-12 18:50 EDT pushed")[0]             # and the summer label in winter


def test_a_twelve_hour_clock_written_with_dots_is_read():
    assert "14 min after" in said(RECORD, "- **2026-11-12 6:54 p.m., done.**")[0]
    assert "14 min after" in said(RECORD, "- **2026-11-12 6:54 P.M., done.**")[0]
    assert said(RECORD, "- **2026-11-12 6:54 a.m., done.**") == []
    morning = NOW.replace(hour=6)
    assert said(RECORD, "- **2026-11-12 6:54 p.m., done.**", now=morning) == []           # read as the morning, it was refused
    assert "14 min after" in said(RECORD, "- **2026-11-12 6:54 a.m., done.**", now=morning)[0]


def test_a_hyphen_between_the_day_and_the_time_is_read():
    assert "6 min after" in said(RECORD, "- 2026-11-12 - 18:46: asked")[0]


NOTES = "projects/alpha/resources/artifacts/weekly-sync.md"


@pytest.mark.parametrize("line", ["### 2026-11-12 18:30–19:00 Weekly sync", "- 2026-11-12 18:30 to 19:00 standup",
                                  "(2026-11-12 18:25-18:55: the call)", "## 2026-11-12 18:40 - 19:10"])
def test_a_span_that_holds_the_present_is_not_ahead_of_it(line):
    """A review, 2026-11-13: a meeting's notes, written while it ran under a heading that gives its hours, were
    refused for the hour it ends. A span that began and has not ended holds the present."""
    assert said(NOTES, line) == []


def test_a_span_that_has_not_begun_and_a_rounded_end_are_still_read():
    assert "20 min after" in said(NOTES, "### 2026-11-12 18:45–19:00 Weekly sync")[0]
    assert "rounds" in said(NOTES, "- 2026-11-12 18:25 to 18:4x: the round")[0]


def test_in_a_session_log_a_span_ends_when_its_entry_is_written():
    """A session log's entry gives the hours it covers, and the later one is now: thirty days of real commits held
    six such spans, in session logs, whose end had not come (2026-11-13)."""
    assert "15 min after" in said(LOG, "### 2026-11-12 18:25 to 18:55 — the review round")[0]
    assert "15 min after" in said(LOG, "- 18:25–18:55 the review round", before=("## 2026-11-12",))[0]


def test_the_refusal_of_a_rounding_says_where_an_events_time_goes():
    """`- ~18:30 the build broke`, written ten minutes on: nobody knows that minute, and "write the minute `date`
    prints" would put a false one there (a review, 2026-11-13)."""
    (found,) = said(LOG, "- ~18:30 the build broke", before=("## 2026-11-12",))
    assert "`date`" in found and "after the words" in found


def test_a_heading_inside_a_code_fence_names_no_day_and_front_matter_is_read_as_the_rest_is():
    """Front matter is read: in thirty days of real commits one record kept its notes there, stamps and all, and
    none held a time to come (2026-11-13)."""
    assert len(said(RECORD, "note: told the owner (11-12 18:54, by mail)", "---", before=("---", "kind: state"))) == 1
    assert said(LOG, "- 18:54 asked", before=("## 2026-11-11", "```", "## 2026-11-12", "```")) == []
    assert len(said(LOG, "- 18:54 asked", before=("## 2026-11-12", "```", "## 2026-11-11", "```"))) == 1


def _repo(tmp_path, monkeypatch):
    import subprocess
    repo = tmp_path / "kb"
    repo.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)

    def git(*words):
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *words], check=True, capture_output=True, text=True).stdout
    git("init", "-q", "-b", "main")
    (repo / "a.md").write_text("# A\n", encoding="utf-8")
    git("add", "-A"); git("commit", "-q", "-m", "one")
    git("checkout", "-q", "-b", "other")
    (repo / "b.md").write_text("- **2026-11-12 18:54, written on the other branch.**\n", encoding="utf-8")
    git("add", "-A"); git("commit", "-q", "-m", "two")
    git("checkout", "-q", "main")
    return repo, git


@pytest.mark.parametrize("bring", [("merge", "--squash", "other"), ("cherry-pick", "-n", "other"), ("cherry-pick", "other"),
                                   ("rebase", "stopped to edit")])
def test_a_commit_that_brings_lines_written_before_is_not_judged(bring, tmp_path, monkeypatch):
    """A review, 2026-11-13: a squash merge and a cherry-pick bring lines that were judged when they were first
    committed, as a merge does, and were judged again by the clock of the replay."""
    repo, git = _repo(tmp_path, monkeypatch)
    if bring == ("cherry-pick", "other"):  # one that stops on a conflict and is finished by hand
        (repo / "b.md").write_text("here first\n", encoding="utf-8")
        git("add", "-A"); git("commit", "-q", "-m", "three")
        import subprocess
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *bring], capture_output=True)
        (repo / "b.md").write_text("- **2026-11-12 18:54, written on the other branch.**\n", encoding="utf-8")
        git("add", "-A")
    elif bring[0] == "rebase":  # a rebase stopped for an edit keeps its folder and no message file
        (repo / ".git" / "rebase-merge").mkdir()
        (repo / "b.md").write_text("- **2026-11-12 18:54, written on the other branch.**\n", encoding="utf-8")
        git("add", "-A")
    else:
        git(*bring)
    assert "b.md" in git("diff", "--cached", "--name-only")
    assert cc.problems({"record_times": {}}, "S1", str(repo), now=NOW)[0] == []


def test_a_setting_of_null_is_refused_and_a_config_without_the_key_runs_nothing(tmp_path, monkeypatch):
    repo, git = _repo(tmp_path, monkeypatch)
    (repo / "d.md").write_text("- **2026-11-12 18:54, written ahead.**\n", encoding="utf-8")
    git("add", "-A")
    assert cc.problems({}, "S1", str(repo), now=NOW)[0] == []
    assert cc.problems({"record_times": False}, "S1", str(repo), now=NOW)[0] == []
    with pytest.raises(cc.Refused, match="record_times"):
        cc.problems({"record_times": None}, "S1", str(repo), now=NOW)


@pytest.mark.parametrize("line, minutes", [
    ("- **2026-11-12 18:54 est, done.**", 14), ("- **2026-11-12 18:54 Est, done.**", 14),
    ("- 2026-11-13 00:54 UTC+1: pushed", 14), ("- 2026-11-12 15:54 UTC-08:00: pushed", 14), ("- 2026-11-12 23:54 GMT: pushed", 14),
    ("- 2026-11-13T00:05Z merged", 25),                                       # tomorrow by its own zone's calendar, and not yet come
    ("- **2026-11-12 18:54 done**", 14),                                      # a word after the time is no zone
])
def test_a_stamp_is_placed_by_its_own_day_in_its_own_zone(line, minutes):
    assert f"{minutes} min after" in said(RECORD, line)[0]


def test_a_stamp_just_past_midnight_is_read_and_yesterdays_last_minutes_pass():
    late = datetime(2026, 11, 12, 23, 55, 10, tzinfo=EST)
    assert "15 min after" in said(RECORD, "- **2026-11-13 00:10, done.**", now=late)[0]
    early = datetime(2026, 11, 13, 0, 5, 10, tzinfo=EST)
    assert said(RECORD, "- **2026-11-12 23:58, done.**", now=early) == []
    assert "10 min after" in said(RECORD, "- 2026-11-13 12:15 am: the nightly run", now=early)[0]


@pytest.mark.parametrize("line", [
    "- [2026-11-12 18:54] pushed the branch", "- **2026-11-12** 18:54 pushed the branch", "- 2026-11-12: 18:54 pushed",
    "- 2026-11-12 \u2014 18:54 pushed", "- Thu 2026-11-12 18:54 pushed", "- Thursday, 2026-11-12 18:54 pushed",
    "1) 2026-11-12 18:54 pushed", "- 2026-11-12 6:54 pm: pushed", "- 2026-11-12 6:54 PM pushed",
])
def test_more_ways_of_writing_a_stamp_are_read(line):
    assert "14 min after" in said(RECORD, line)[0]


@pytest.mark.parametrize("line", ["- 2026-11-12 18:40-ish: asked", "- 2026-11-12 c. 18:35: asked", "- 2026-11-12 18:35 (approx.): asked"])
def test_more_ways_of_rounding_are_read_and_the_refusal_quotes_the_rounding(line):
    found = said(RECORD, line)
    assert len(found) == 1 and "rounds" in found[0]
    assert "`about 18:35" in said(RECORD, "(11-12 about 18:35: merged)")[0]


def test_a_line_with_no_mark_opens_an_entry_only_where_it_begins_a_paragraph():
    wrapped = ["The owner asked to meet, and the notes are due on"]
    assert said(RECORD, "2026-11-12 18:54 with the plan attached.", before=wrapped) == []
    assert "14 min after" in said(RECORD, "2026-11-12 18:54 the release went out.", before=wrapped + [""])[0]


def test_each_file_is_read_once_and_a_long_run_of_spaces_costs_nothing():
    """`setdefault` read the file again for every line (a review, 2026-11-13): moving a session log made one git
    process for each of its entries, and 7,000 of them ran out the check's time."""
    import time
    reads, today = [], ["## 2026-11-12", ""]
    lines = [f"- 18:{n % 40:02d}: entry {n}" for n in range(3000)]
    added = [(LOG.encode(), len(today) + n, line.encode()) for n, line in enumerate(lines, 1)]

    def read(name):
        reads.append(name)
        return "\n".join(today + lines)
    start = time.monotonic()
    cc.record_times(added, {}, NOW, read)
    assert reads == [LOG] and time.monotonic() - start < 2
    start = time.monotonic()
    assert said(RECORD, "- " + " " * 20000 + "x 18:54", "*" * 20000 + " x 2026-11-12 18:54", "(" + "a " * 20000 + "11-12 18:54)") == []
    assert time.monotonic() - start < 1
    assert cc.record_times([(RECORD.encode(), 1, b"- no time on this line")], {}, NOW, lambda name: reads.append("again") or "") == []
    assert reads == [LOG]                                                     # a file with no time on its added lines is not opened


def test_a_merge_is_not_judged(tmp_path, monkeypatch):
    """A merge brings lines that were judged when they were committed, on another machine or in another zone. An
    entry committed at 18:54 eastern blocked a merge made at 16:05 pacific, and no approval clears this check."""
    import subprocess
    repo = tmp_path / "kb"
    repo.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)

    def git(*words):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *words], check=True, capture_output=True)
    git("init", "-q", "-b", "main")
    (repo / "a.md").write_text("# A\n", encoding="utf-8")
    git("add", "-A"); git("commit", "-q", "-m", "one")
    git("checkout", "-q", "-b", "other")
    (repo / "b.md").write_text("- **2026-11-12 18:54, written on the other branch.**\n", encoding="utf-8")
    git("add", "-A"); git("commit", "-q", "-m", "two")
    git("checkout", "-q", "main")
    (repo / "c.md").write_text("# C\n", encoding="utf-8")
    git("add", "-A"); git("commit", "-q", "-m", "three")
    git("merge", "--no-commit", "--no-ff", "other")
    assert cc.problems({"record_times": {}}, "S1", str(repo), now=NOW)[0] == []
    git("commit", "-q", "-m", "merged")
    (repo / "d.md").write_text("- **2026-11-12 18:54, written ahead.**\n", encoding="utf-8")
    git("add", "-A")
    assert len(cc.problems({"record_times": {}}, "S1", str(repo), now=NOW)[0]) == 1      # and the next commit is judged as any other


# --- a line that opens with what was done, and then its time (2026-11-13) --------------------------------------------
# The morning the check went on, a seat committed `**Revised Fri 07:1x ET:** ...` at 07:11 and nothing was said: the
# line opens with a word, then a weekday with no date, then the time, and the check read a stamp only where a line or
# a parenthesis opens with the day and the time. Counted over thirty days of commits: 110 added lines open with one
# of the check's own words for what was done and then a time, and 28 of them round it or stand a few minutes ahead.

@pytest.mark.parametrize("line", [
    "**Revised Thu 18:4x ET:** the guard's hold was read and the draft changed.",
    "**Revised Thu 18:45 ET:** the guard's hold was read and the draft changed.",
    "Written 18:52: the plan for the week.",
    "- Released about 18:40.",
    "### Built 2026-11-12 18:47",
    "**Revised on Thursday, 11-12 at 18:4x:** the second paragraph.",
    "Updated: 18:50, after the call.",
    "* _Checked at 18:4x_ against the console.",
    "Sent Thursday 18:55 to the three of them.",
])
def test_a_line_that_opens_with_what_was_done_and_then_its_time_is_an_entrys_stamp(line):
    for path in (RECORD, "drafts/2026-11-12-a-reply.md", LOG):
        found = said(path, line)
        assert len(found) == 1 and found[0].startswith(f"{path}:1: "), (path, line, found)


@pytest.mark.parametrize("line", [
    "**Revised Thu 18:38 ET:** the guard's hold was read.",                # the clock's minute, or before it
    "Written 18:40: the plan for the week.",
    "**Revised Wed 18:45 ET:** yesterday's change.",                       # a weekday that is not today's is another day
    "**Revised Fri 18:4x ET:** to be done tomorrow.",
    "Released 19:30 on the stable branch.",                                # more than half an hour ahead: a plan
    "Standup 18:45 with the team.",                                        # a word that says nothing was done
    "Meeting Thu 18:45, room 2.",
    "Thu 18:45 standup.",                                                  # a weekday first: a schedule's line
    "Revision 18:45 is the one to read.",
    "- [ ] Sent 18:45 to the three of them.",                              # an unchecked box is a plan
    "Revised the draft at 18:45 and sent it.",                             # the time stands inside the sentence
    "Released v5.12.0 at 18:45.",
])
def test_what_is_no_such_stamp_or_is_no_later_than_the_clock_passes(line):
    for path in (RECORD, "drafts/2026-11-12-a-reply.md"):
        assert said(path, line) == [], (path, line)


def test_a_wrapped_line_that_begins_with_such_a_word_opens_no_entry():
    wrapped = ("The draft went through three rounds and was then", "revised 18:45 by the second reader.")
    assert said(RECORD, wrapped[1], before=(wrapped[0],)) == []
    assert len(said(RECORD, "Revised 18:45 by the second reader.", before=("The draft went through three rounds.", ""))) == 1
