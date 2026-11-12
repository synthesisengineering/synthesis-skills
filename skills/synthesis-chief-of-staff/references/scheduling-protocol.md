# Scheduling protocol

Read before proposing, placing or re-staging any meeting. The five numbered steps under "The
steps" were the Scheduling protocol section of SKILL.md until 2.2.0 (2026-11-11) and moved here
word for word; the sections after them are new in 2.2.0.

Contents: The steps · On the principal's terms · The slot check · Staged meetings · The guard
behind it · Why.

## The steps

1. **Read the principal's calendar FIRST.** No scheduling sentence is written
   before the actual calendar for the window is fetched. An agent with
   calendar access that asks the counterpart for their availability has the
   relationship backwards. Read every account the principal schedules from,
   each through its own connector (the account-routing guard sends calendar
   calls to the account that owns the workspace). An account or calendar the
   agent cannot read is an unanswered question, not a free window — name it
   before proposing anything inside it, and ask the principal for that
   window rather than assuming it is open.
2. **Propose, never solicit.** Offer 2–3 concrete windows from the
   principal's calendar that already respect protected hours, buffer rules,
   and prep time — or route through the principal's human assistant per
   config. Asking the counterpart to "send times" hands them the calendar and
   converts the principal into the accommodating party. (The principal may
   choose that posture deliberately for someone senior; the agent never
   defaults to it.)
3. **Respect the config's timing floors** — earliest meeting hour, same-day
   rules, latency norms. A request answered gracefully next week nearly
   always beats one answered obsequiously today.
4. **Build in preparation.** If the meeting needs a pre-read, research on a
   new contact, or a prep pack, the offered windows must leave room for that
   work to happen first — prep time is real time.
5. **Deadlines change math, not posture.** When the subject has a real date
   (a launch, a season, a filing), acknowledge the date and pick the earliest
   window that honors it WITH preparation — still on the principal's terms.

## On the principal's terms

When the principal agrees to meet, or commits to set a meeting up, that is a yes to the meeting.
It is not a yes to the earliest free slot. The agent sets the time to suit the principal's
calendar and protect their deep work; the requester's timing is accommodated only for the people
the config's tiers say it binds for.

- **Never add a meeting to today** unless the principal asks for it. The principal plans the day
  the night before and in the morning; a same-day addition breaks that plan.
- **Keep at least one deep-work block every day.** A day already carrying its meeting load takes
  nothing more.
- **Look first for an existing touchpoint:** a standing 1:1, a recurring sync the person already
  attends, or one meeting that folds together several small asks with the same person. A new
  meeting is the last resort.
- **Place a new meeting beside existing ones,** so it does not split a free block, within the
  next few business days. The first open half hour is a reflex, not a choice.
- **A requester's deadline is their preference.** "By Tuesday" and "tomorrow or Monday" say when
  it would suit them. Unless their timing binds, the principal's calendar decides, and the note
  offers the principal's time warmly.
- **Invitation text states the meeting's purpose.** It never explains the time by the other
  person's urgency.
- **A recommendation never argues that a meeting cannot move** because someone who is not senior
  to the principal asked for it.
- **The test:** would a human chief of staff who protects the principal's time have booked it?

## The slot check

Run it on every time before proposing or placing it, and show its verdict with the proposal:

```bash
python3 scripts/slot_check.py --start 2026-11-12T14:00 --end 2026-11-12T14:30 --events read.json \
    --attendee a@example.com --requester a@example.com --deadline 2026-11-13
```

`read.json` is the calendar read the agent already made (binding rule 4), saved with the days it
covers: `{"window": {"from": "2026-11-11", "through": "2026-11-18"}, "events": [{"start", "end",
"summary", "attendees"}]}`. `start` and `end` are ISO strings or the connector's own
`{"dateTime": ...}` and `{"date": ...}`. Read every calendar the principal schedules from into
it, for the slot's day and the seven days after today. `--today` names the date when it is not
this machine's; `--config` another preferences file; `--json` prints the same result as JSON.

```text
slot Thu 2026-11-12 15:30-16:00: REVIEW
  OK      same day: 1 day(s) out
  OK      protected hours: outside protected hours
  OK      working hours: inside working hours 09:00-17:00
  OK      deep work: 1 free block(s) of 120 minutes or more remain, the first 09:00-13:00
  OK      meeting load: 1.50 hours of meetings that day with this one (limit 5)
  REVIEW  placement: it splits the free block 14:00-17:00: place it beside an existing meeting, or at an edge of that block
  OK      existing touchpoint: no meeting with the same people from 2026-11-11 through 2026-11-18
  NOTE    deadline: the requester's date (2026-11-13) is their preference; the principal's calendar decides
```

| Check | REFUSE when | REVIEW when | Reads from the preferences |
|---|---|---|---|
| same day | the slot is today (or past) and no attendee's timing binds | | `meeting_defaults.same_day_meetings` (true allows today) |
| protected hours | it overlaps a protected window and no attendee's timing binds | | `protected_hours`: `[{"start": "09:00", "end": "11:00", "days": [0, 1, 2, 3, 4], "label": "..."}]` (`days` optional, Monday is 0; `24:00` ends a day), or a section that holds that list as `windows` beside lines of prose. Prose is named as unchecked unless a window gives the line as its `source` |
| working hours | | it falls outside them | `working_hours.start`, `.end` |
| deep work | it leaves fewer free blocks of the set length than the day must keep, the trip there and back counted as taken | | `calendar_guardian.thresholds.maker_block_minutes` (default 120), `.min_maker_blocks_per_day` (1) |
| travel | the trip there or back runs through another event (only with `--travel-before` or `--travel-after`) | | |
| return | | home after `travel_policy.latest_return`: the principal's decision (only with `--travel-after`; the line always gives the time home) | |
| sleep | | less than `travel_policy.sleep_hours` between getting home and the next morning's first commitment, or the hour `travel_policy.morning_starts` gives the morning if that is earlier | the read ends before the next morning and the policy's hour leaves the night long enough |
| meeting load | the day's meetings with this one exceed the limit. A meeting is an event someone else is on: the principal's own blocks (no other attendee, or a title carrying a personal marker) are taken time for every other check and are not counted, and the line says how many were left out. A read that names no one else on any event counts each one, and says so | | `.max_meeting_hours_per_day` (5), `.personal_markers` (titles, for example `["#reserved"]`), `principal_addresses` (the principal's own, patterns allowed) |
| placement | | it sits in the middle of a free block long enough for deep work, away from any meeting | |
| existing touchpoint | | a meeting with one of the same people is already on the calendar within the look-ahead | `.touchpoint_days` (7) |
| deadline | the requester's timing binds and the slot is after their date | | |

**A meeting in person takes the trip as well.** Give the minutes door to door on each side with `--travel-before` and
`--travel-after`; `--in-person` with neither is refused (exit 2) until the trip is worked out. The trip itself is planned
and recorded as [in-person-travel.md](in-person-travel.md) says.

Whose timing binds: the addresses and patterns (`*@board.example.com`) in `tiers.priority`. A
tier entry that is a name, or protected hours written as prose, cannot be matched; the report
says so with a NOTE and the agent checks those by hand. The agent's own holds (events titled as
`calendar_guardian.holds.title`) and all-day markers count as free time. The title is the whole
test: an event titled exactly that is read as a hold whoever made it and whoever is on it, so the
title is one no meeting carries, and a hold that became a meeting is retitled.

REFUSE (exit 1): choose another time; do not put the slot to the principal as an option. REVIEW
(exit 0): fix what it names, or say in the proposal why this slot is still the right one. It
exits 2, and judges nothing, when the preferences are missing or the calendar read does not
cover the slot's day.

## Staged meetings

A meeting drafted but not yet sent is staged. Each day it is carried forward, check its slot
again with that day's date: a slot that was two days out when drafted becomes today and is
refused. Never move a staged meeting into the first open slot of the day it is carried to;
propose a later day that passes the check, or use an existing touchpoint. On 2026-11-09 one
follow-up had been staged on the 5th for the 5th, carried to the 6th for the 6th, and carried
again to the 9th for the 9th.

## The guard behind it

With `same_day_meetings` in the synthesis config, the send guard holds any calendar write that
starts today and invites someone else until the principal types a code for that same-day meeting
(`synthesis-message-guard`, references/config.md). The slot check runs before any call is made,
so the guard's hold is the backstop, not the plan.

## Why

Over one week an agent filled a principal's open time with other people's requests as fast as it
could: a demo in the first afternoon slot three calendars shared, with an invitation explaining
that the requester wanted it "by Tuesday"; a follow-up in the half hour after his leadership
weekly, on the same day, because the other person had suggested "tomorrow or Monday". The morning
plan then defended both as unable to move. His preferences already said times are proposed on his
terms. His correction: he needs time for deep work every day, and agreeing to someone's request
for a meeting means he sets it up, on his terms and at his convenience.
