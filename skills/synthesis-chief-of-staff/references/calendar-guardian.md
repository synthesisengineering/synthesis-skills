# Calendar guardian

The calendar guardian (v1.1.0) as written in 1.3.0: look-ahead horizons, the next-day review, the same-day shield with its holds ledger, and the config keys. The daily-rituals skill runs it on its cadence; this file owns what each pass checks.

Contents:
- Calendar guardian: the three parts and who owns the cadence
- The horizons: next working day, week ahead, month ahead
- The next-day review: checks 1 to 7, including the overcommitment check
- The same-day shield: hold events, the `holds_state.py` commands, the append-only ledger, expiry, routing
- Config keys: the `calendar_guardian` block

## Calendar guardian (v1.1.0)

A human EA team working around the clock would not *check* the calendar; they
would *hold a perimeter* around it. Guardianship has three parts — look-ahead
at fixed horizons, active defense of open time, and a quality bar applied to
every entry — and it runs on the daily-rituals cadence (day-start and day-end
steps reference this section; the rituals own *when*, this section owns *what*).

### The horizons

Each horizon answers a different question. Do not blur them.

| When | Horizon | The question |
|---|---|---|
| Every day-end | The next working day (plus the weekend, on the last working day of the week) | *Can tomorrow actually be lived as booked?* |
| Last working day of the week | The week ahead | *Where are the collisions and the crunches, while there is still time to move things?* |
| Last working day of the week | The month ahead | *What is approaching that needs lead time — travel, deadlines, absences whose notification clocks should start now?* |

The month-ahead pass is where this section meshes with absence coordination:
a commitment spotted four weeks out is what triggers `notify_on_commit` while
notification is still early, cheap, and conflict-preventing.

### The next-day review — a checklist, not a glance

For every entry on tomorrow's calendar:

1. **Is it real?** Resolve mirror blocks («Busy») to their originating event.
   Flag entries that are placeholders for plans that fell through.
2. **Is it answered?** Unanswered RSVPs on tomorrow's meetings are a hygiene
   failure visible to every other attendee. Surface them for decision.
3. **Is it prepared?** Every meeting should have its prep artifact or an
   explicit "no prep needed." A meeting with neither goes on the decisions
   list — prep it or question attending it.
4. **Does it have a desired outcome?** (This skill's meeting bar.) A recurring
   meeting is not exempt; it is the most likely to have quietly lost its point.
5. **Does the day obey the principal's shape?** Protected blocks intact, floor
   respected, formats correct, after-hours entries visible to the family
   calendar per config.
6. **Is it physically possible?** Back-to-backs across locations, video calls
   with no gap, time-zone arithmetic on anything involving travel. Verify
   against the clock, not against impressions.

Then the day as a whole:

7. **Overcommitment check, against config thresholds.** Total meeting hours,
   count of context switches, and surviving maker blocks. When a day exceeds
   thresholds, do not merely report it — **name the candidates to move**,
   ranked by the triage tiers, with a drafted reschedule note for each. A
   warning without candidates delegates the thinking back to the principal.

The review's output feeds the day plan's calendar section; anything needing
the principal's call goes to the plan's decisions region, one line each.

### The same-day shield — holds, not hopes

The config's same-day rule (no same-day meetings except VIP tiers or explicit
approval) is policy; open calendar space silently repeals it, because an open
slot is an invitation anyone with scheduling access can accept. The shield
makes the policy mechanical:

- At the day-start ritual, place **hold events** over the day's remaining open
  windows; at day-end, over the next day's. Title them generically ("Hold");
  mark them busy.
- **Track every hold the agent creates in the holds ledger.** The agent
  releases or moves **only holds it created, matched by id** — never any event
  it merely believes is a hold. This is the invariant that makes the shield
  safe to automate, and `scripts/holds_state.py` is the only way to touch it.
  Never hand-edit the ledger, and never decide releasability by reading it:

  ```bash
  holds_state.py record place --id <event-id> --by <seat> --calendar <cal> \
      --title "Hold" --kind same-day-shield \
      --start 2026-09-04T14:00:00-04:00 --end 2026-09-04T16:00:00-04:00 \
      --purpose "why this window is worth defending"
  holds_state.py is-releasable <event-id>   # exit 0 = the agent placed it
  holds_state.py record release --id <event-id> --by <seat> --reason "..."
  holds_state.py query current              # what is held today
  holds_state.py query expired              # calendar debt to clear
  ```

- **Ask `is-releasable`; do not judge.** Exit 1 means no `place` event exists
  for that id, so the agent did not create it: leave the event alone and ask
  the principal. This is the whole invariant, answered mechanically rather
  than from an agent's recollection of what it did earlier.
- **The ledger is an append-only event log** (`holds/events.jsonl`), because
  more than one seat runs the principal's rituals against one calendar. Its
  predecessor was a single JSON array that every seat read, modified and
  rewrote; under concurrent seats that loses holds outright, and a lost
  `place` record makes a real calendar event permanently unreleasable. Events
  are appended, never rewritten, so seats cannot overwrite one another.
- Holds **expire automatically** at the end of their day, computed from the
  window — which is why `--start`/`--end` are ISO-8601 with an offset and not
  prose. A hold that outlives its purpose is calendar debt and erodes trust in
  every real entry; `query expired` names them.
- A request that hits the shield is not refused; it is **routed**: VIP tiers
  pass per config, everything else becomes a proposal for a later slot, in
  this skill's scheduling voice. The shield converts ambush into triage.
- Protected personal blocks (training, rituals, family time) are **not**
  holds. They are real commitments and are never released for anything below
  the config's override tiers. The difference is exactly why holds carry ids.

### Config keys

Under `calendar_guardian` in the private preferences file:

```json
{
  "calendar_guardian": {
    "thresholds": {
      "max_meeting_hours_per_day": 5,
      "min_maker_blocks_per_day": 1,
      "max_consecutive_meetings": 3
    },
    "holds": {
      "title": "Hold",
      "ledger": "~/.synthesis/chief-of-staff/holds/events.jsonl",
      "expire": "end-of-day"
    },
    "same_day_exceptions": "reuse the tiers section",
    "weekly_review_day": "Friday"
  }
}
```

Thresholds are the principal's to tune; the defaults above are a starting
point, not a claim about anyone's ideal day.
