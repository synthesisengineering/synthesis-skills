# Travel for in-person commitments

Read this before recording any commitment that has a place, and at each ritual in a workspace that checks
travel. `<cos>` is this skill's folder.

## Why it is a step of its own

A commitment in person has four parts: the time, the place, the way there and the way back. On 2026-11-11 a
principal who owns no car found an evening event 28 miles from home that had been on his calendar for six days
with the first part and half of the second: its location read a town and "address on the card". It had been
carried through three daily plans, a guest's arrival logistics and that morning's day-start. A plan said "you
leave about 6" and a draft to the guest promised "back around 11"; no source gave either time, and the real
trains got him home at 11:48. A rule about realistic travel was already in his preferences, filed under
calendar rebuilds, so nothing ran it when one event was added. The event was personal, so a car could not be
expensed.

## At the ask, before the yes

The same principal, shown the repaired plan, said the trip was a burden he had not seen when he agreed: he had
taken the event to be in his own city, and a late return before an early morning is a cost of its own. The
decision he had been given
named the town and showed no trip. Travel worked out after the yes comes too late to change the answer.

So the trip is worked out before an invitation or an ask that would put the principal somewhere is brought to
them. Do steps 1 to 4 below, then run the slot check with the trip's minutes:

```bash
python3 <cos>/scripts/slot_check.py --start … --end … --events read.json --in-person --travel-before 85 --travel-after 108
```

Its `return` line says when the principal is home; a return past `travel_policy.latest_return` is theirs to
decide. Its `sleep` line compares that with the next morning's first commitment against
`travel_policy.sleep_hours`. Put what the event costs in the decision itself, beside the invitation: door to
door each way, the fare and who pays, the time home, the night it leaves, and what it collides with that day
and the next morning. Then recommend, as [asks-and-decisions.md](asks-and-decisions.md) sets out.

## At intake

Do this whenever an in-person commitment lands, before the calendar write and before the yes goes out: an
RSVP, an invitation the agent accepts, a decision in a plan.

1. **Say who pays.** Personal or business. It decides the mode (`travel_policy.cost`).
2. **Resolve the exact address.** A street number, not a town or "see the invitation". Read the invitation,
   the venue's own page and earlier correspondence; ask the host when none of them gives it.
3. **Model the trip door to door,** from where the principal will be beforehand (home, an office, the event
   before it), with timetables and waits read from a live source for that date and time. Include the walk at
   each end and every wait. Use the principal's modes (`travel_policy.modes`); `"car": false` means the
   principal does not drive. Never take a time from memory, and never shorten a real journey to make a day fit.
4. **Choose the mode by who pays.** A personal trip takes the cheapest reliable public option, with the fare
   bought ahead where that is cheaper. A business trip may take an expensable car where the policy allows it
   and it saves real time.
5. **Put a travel block on each side** of the commitment and the travel line in the commitment's own event
   (the format is below).
6. **Bring it to the principal now when travel changes the answer:** a return after `latest_return`, a night
   shorter than `sleep_hours` before the next morning's first commitment, a trip longer than the event, a
   fare out of proportion to it, or leaving before the end to catch the last reasonable train. Give the times
   and the cost, and write their words on the block's `Decision:` line.
7. **Run the check** (below). With a time still to choose, give `slot_check.py` the trip:
   `--in-person --travel-before <minutes> --travel-after <minutes>`.

## The travel block

One calendar event on each side, so the time is visibly taken. Its title starts with the policy's
`block_title` (`Travel` unless set): the word alone, or followed by a colon, a dash or a direction
(`Travel: to the theatre`, `Travel home`). An event whose title only begins with that word (`Travel
planning workshop`) is an event, with clock times or without, unless it carries a block's lines. Its description carries these lines:

```text
For: Book launch at the Grand Theatre
Paid by: personal
Leave: 17:05 from home
Route: Line 1 to Central Station, the 17:50 Harbor line train
Arrive: 18:30 at 149 Main St, Harbor Town
Backup: the 18:20 train, arriving 19:02
Fare: $15.00 train and $3.00 subway
Ticket: the rail app, before boarding (more on board)
Decision: <the principal's words>        only where step 6 applied
```

`For:` repeats the commitment's title, or its opening words. A block that serves two commitments, the way
from one place to the next, carries a `For:` line for each. A block with no `For:` line serves the one
in-person commitment nearest to it, so name the commitment whenever two stand within a day of each other.
Free text can follow the lines, and a description a connector returns as HTML is read as the text it shows.

The commitment's own description carries one line that says where its travel stands:

```text
Travel: blocks before and after
Travel: local, 12 min walk               within travel_policy.local_minutes
Travel: none, already at the venue for the session before
```

The line is one of those three forms or it excuses nothing: one that only begins like a form
(`locally unavailable`) or mentions one later is flagged, and the blocks are still asked for. `local` needs its
minutes and `none` its reason.

A place that is the principal's home or one of the policy's named `places` (an office with a standing
commute) needs neither blocks nor a line. A named place is known by its address anywhere in the location, or
by its label alone or with a room or a note after it (`Office, 4th floor`). An address is matched whole:
`110 River St` is not the home at `10 River St`.

## The policy

`travel_policy` in the principal's preferences:

| Key | What it holds |
|---|---|
| `home` | `label`, `address`, `area`: where a trip starts unless the calendar says otherwise |
| `places` | named places with a standing route: `label`, `address`, `minutes`, `route` |
| `car` | `false` when the principal does not drive |
| `modes` | the modes the principal uses |
| `local_minutes` | a walk or ride this short needs a line and no blocks |
| `arrive_early_minutes` | how long before the start the outbound block must arrive |
| `latest_return` | a return after this hour is the principal's to decide |
| `sleep_hours` | the hours the principal keeps between getting home and the next morning's first commitment; a shorter night is theirs to decide, and a commitment already begun when they get home leaves no night at all. With no `morning_starts`, an outing that begins and ends on one morning is judged against the next night. No key, no rule |
| `morning_starts` | the hour the principal's morning begins whether or not the calendar holds an entry then (a workout, a routine nobody schedules). The night ends at the earlier of this hour and the first entry, and an outing that began on an earlier day and ran past this hour left no night at all. Without it, a morning with no entry costs nothing the check can see |
| `cost` | `personal` and `business`: the rule for each, in words |
| `block_title` | the word a travel block's title starts with |
| `online` | words that mark a location as not a place |

## The check

```bash
python3 <cos>/scripts/travel_check.py --events read.json [--from YYYY-MM-DD] [--days 7] [--today YYYY-MM-DD] [--json]
```

`read.json` is the calendar read `slot_check.py` takes, each event with its `location` and `description`.

```text
travel: 2 in-person events from 2026-11-11 through 2026-11-17; 1 lacks its travel
  REFUSE  Wed 2026-11-11 19:00 Book launch at the Grand Theatre
          - no exact address: the location reads "Harbor Town (address on the invitation)"
          - no travel line in the event: `Travel: blocks before and after`, or `Travel: local, N min walk`
          - no travel block before it (leave, route, arrive, backup, fare, ticket)
          - no travel block after it (leave, route, arrive, backup, fare, ticket)
  OK      Fri 2026-11-13 12:30 Lunch with the board chair (leave 11:40, home 14:35)
```

It flags: no exact address; no travel line; a missing block; a block without one of its lines (a placeholder
such as "TBD" is no line); an outbound block that arrives after the start or less than
`arrive_early_minutes` before it; and four things only the principal settles, each cleared by a `Decision:`
line on the block: a return that leaves before the end, a return that ends after `latest_return`, a night
shorter than `sleep_hours` before the next morning's first commitment, and a car on a personal trip.

What it takes each word to mean:

- **An exact address** is a house number with its street, or a postcode with its town (`149 Main St`,
  `10115 Berlin`), or a number in one part and a name in another (`Calle Mayor, 5`). A venue whose name ends
  in a number (`Studio 54`), a room, suite or floor (`Room 4, Harbor Town`) and a time of day are not one. A location that holds a street address is a place
  whatever else it says: an online word in a venue's name, a map link beside it.
- **The days it judges** are every day a commitment covers. One under way when the days begin is judged for
  its way back, and its way there is left to a read that holds its start. An all-day event counts on each day
  it covers and needs its travel line; give it clock times to have its blocks checked. When the morning
  after a return holds an all-day commitment at a place, the night cannot be judged from the read: the
  event that returns the evening before lacks that, until the all-day one is given its times or the
  return's block carries the principal's `Decision:`.
- **Whose a block is** follows its `For:` lines, as above (quotes around a title do not matter). When a block
  beside an event belongs to another, the report says whose it is. One event read from two calendars is one
  event.
- **A block in another form** (an entry beside the event titled like a trip, such as "Return from …", without
  the block's title or its lines) is named in the event's line as its travel in another form. It does not
  count as a block: no route, fare or backup can be read from it. Rewrite it in the labeled form.
- **The next morning's first commitment** is the earliest timed entry of the day after, a trip included. Exit 0 when every in-person event is whole, 1 when one is flagged, 2 when it was not
shown enough (no `travel_policy`, a read that does not cover the days, events that are not a list of entries,
a read it cannot make sense of). `--json` gives the same per event,
with `leave`, `home` and `paid_by` taken from the blocks.

It plans nothing and reads no timetable: steps 2 to 4 are the agent's, from a live source. It cannot tell
that a route is wrong, only that one is written down.

## At the calendar write

Where the synthesis config carries `in_person_travel`, the guard refuses a calendar write that creates an
event at a place, or gives one a place (under `location`, `where`, `place` or `venue`, written out or as a
structure), when the call carries no `Travel:` line. It asks for no approval:
do steps 1 to 5 above and make the call again. It reads the call alone, so it cannot see whether the blocks
exist; the check above does (synthesis-message-guard, `references/config.md`, "A meeting at a place").

## In the daily rituals

A workspace turns the check on in the ritual config (`<synthesis home>/rituals/config.json`), under the
workspace or under `defaults`: `"travel_check": true`, or `{"days": N}` to look N days ahead where 7 is not
right. Each ritual of that workspace then runs the check on a fresh calendar read and puts what it flags in
the plan, and `ritual_state.py record` takes the result as `--travel <the --json output>`. It refuses with no
result, with one whose first day is not the day being recorded, with one that covers too few days, and while
the result holds an event that lacks its travel (synthesis-daily-rituals, binding rule 14).

## The day before and the morning of

Read the live source again for each block of that day and the next: the same train still runs, at the same
time, with no service change. Update the block when it moved and tell the principal what changed. A
timetable read a week ago is a cache.

## Every later use reads the block

A plan, a guest's logistics, a draft that says when the principal leaves or returns: each takes the time from
the travel block and says which block. None of them writes an estimate ("about 6", "back around 11").
