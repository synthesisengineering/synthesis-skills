"""The time an entry gives for itself is not later than the commit that records it, and is no rounding of the present.

A record's entry states its own time in three places: the line opens with the day and a time, a parenthesis opens
with them, or (in a session log) a list item opens with a time under a heading that names the day. Measured on thirty
days of commits to twenty-seven knowledge repositories (2026-11-12): of 688 such stamps, 36 named a minute that had
not come when they were committed and 111 rounded the present ("18:3x", "about 18:35") when the clock could be read.
A time inside an entry's text says nothing of the kind: three in ten of those are later than the commit, and rightly
(a meeting, a deadline, a scheduled wake).
"""

from datetime import datetime, timedelta, timezone

import pytest

from synthesis import commit_check as cc

EST = timezone(timedelta(hours=-5))
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
    ("- **2026-11-12 18:25 to 18:55, the review round.**", 15),          # a range is read by its later end
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
    ("### 2026-11-12 19:05 CDT", 25),      # 19:05 where the offset is five hours: the same minute as here
    ("### 2026-11-12 17:50 CST", 10),      # an hour behind: 18:50 here
    ("- 2026-11-12 23:45 UTC: the job ran", 5),
    ("- 2026-11-12 23:46Z: the job ran", 6),
    ("(11-12 15:50 PST: their reply)", 10),
    ("- 2026-11-12 18:45 -05:00: pushed", 5),
])
def test_a_zone_the_stamp_names_is_honored(line, minutes):
    assert f"{minutes} min after" in said(RECORD, line)[0]
    earlier = {"### 2026-11-12 19:05 CDT": "### 2026-11-12 18:39 CDT", "### 2026-11-12 17:50 CST": "### 2026-11-12 17:40 CST",
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


def test_the_check_runs_only_where_the_config_turns_it_on_and_a_setting_of_another_shape_is_refused():
    late = [(RECORD.encode(), 1, b"- **2026-11-12 18:54, done.**")]
    assert cc.record_times(late, None, NOW, lambda name: "") == []           # no key: the check does not run
    assert cc.record_times(late, {}, NOW, lambda name: "") != []
    for wrong in (True, "on", ["x"], {"skip": "daily-plans/**"}, {"skip": [7]}):
        with pytest.raises(cc.Refused, match="record_times"):
            cc.record_times(late, wrong, NOW, lambda name: "")


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
