# Bringing the principal an ask

Read this before putting any invitation, request or choice in front of the principal: in a daily plan, a
decision packet or a message. `<cos>` is this skill's folder.

## Why a choice needs a view

On 2026-10-30 a daily plan put an invitation to its principal as "Option A: Accept / Option B: Decline". It
named the town and nothing else: no recommendation, no trip, no cost, no time home. He said yes. Twelve days
later the evening turned out to be three hours of travel away, with a return near midnight before an early
morning. His words: a human chief of staff would have warned him, challenged him, and made sure he saw the
consequences of what he was signing up for.

A choice put with no view is not neutral. It defaults to yes, and it hands the analysis to the one person whose
time the seat exists to protect.

## What every ask carries

1. **What it costs.** The consequences that would change the answer, in the principal's terms: the time it
   takes with its travel door to door, the money and who pays, when they are home, the night it leaves before
   the next morning's first commitment, and what it collides with that day and the next morning. For anything
   at a place, work the trip out first ([in-person-travel.md](in-person-travel.md), "At the ask"); the slot
   check gives the time home and the night.
2. **A recommendation.** Which answer you would give and why. "Either" and "your call" are not one.
3. **A plain challenge when the costs outweigh the event,** even when the principal leans yes: "I'd decline:
   three hours of travel and home near midnight before a 07:30 session, for a two-hour event."

A request for a fact only the principal has (a preference, a number) is a question, not a choice, and needs no
recommendation. A choice between answers always does.

## The shape, in a plan

```text
### 2. The book launch on Wednesday, 7 to 10 PM, in Harbor Town
**Option A:** Accept
**Option B:** Decline
**Consequences:** 1 h 25 min each way by train, $32 round trip and not expensable, home at 23:48 before a
07:30 session on Thursday; it is also the night a guest arrives.
**Recommendation:** **B**, decline: three hours of travel and a midnight return for a two-hour event.
```

An item that would commit the principal's time and is not worded as accept or decline carries a
`**Commits:**` line saying what it takes (`**Commits:** the living room, Monday to Saturday`), so that its
consequences are asked for too.

## What checks it

- **The ritual record** (synthesis-daily-rituals): `ritual_state.py record` reads the day's plan in each plan
  folder the workspace declares and refuses while an open item that offers options has no `Recommendation:`
  line, or, when it is an accept-or-decline or carries `Commits:`, no `Consequences:` line.
- **The decision packet** (synthesis-decision-packet): the generator refuses a row that recommends nothing,
  unless it is blind, and `--strict-reader` requires each row's `impact` both ways.
- **The slot check** (`<cos>/scripts/slot_check.py`): with the trip's minutes, its `return` and `sleep` lines
  give the time home and the night, to copy into the consequences.

None of these can judge whether a recommendation is right or a challenge was owed. They make sure one was
written.
