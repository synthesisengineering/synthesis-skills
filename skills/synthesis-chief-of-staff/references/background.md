# Chief of staff: background

Release notes for 1.1.0 to 2.0.0 and the skill's relationship to other skills.

## Release notes

**Version 2.3.0** (2026-11-11) adds travel for in-person commitments. `scripts/travel_check.py` reads a
calendar read and the `travel_policy` in the preferences and lists each in-person event with what its
travel lacks: an exact address, the event's travel line, a block on each side with every line a traveler
needs, an arrival early enough, and the cases the principal settles (a return that leaves early or ends
late, a car on a personal trip). `slot_check.py` takes `--travel-before` and `--travel-after` and counts
the trip as taken time; `--in-person` with neither is refused. Binding rule 13 and
[in-person-travel.md](in-person-travel.md) hold the step. An evening 28 miles from a principal's home had
sat on his calendar for six days with no way to get there. Shown the repaired plan, he said the trip was
a burden he had not seen when he agreed, and that a chief of staff would have warned him. So the trip is
worked out at the ask: with the trip's minutes, `slot_check.py` says when the principal is home and what the
night leaves (`travel_policy.latest_return`, `sleep_hours`), and `travel_check.py` sends a short night to
the principal as it does a late return. Binding rule 14 and [asks-and-decisions.md](asks-and-decisions.md)
set what every ask carries: what it costs, a recommendation, and a plain challenge when the costs outweigh
the event. To make room in SKILL.md, the prime
directive's four points moved word for word to
[meetings-correspondence-travel.md](meetings-correspondence-travel.md).

**Version 2.2.0** (2026-11-11) adds scheduling on the principal's terms and critical deadlines.
`scripts/slot_check.py` judges every proposed time before it is offered: never today unless the
principal asks, a deep-work block kept, the day's meeting load, placement beside existing
meetings, an existing meeting with the same people first, and a requester's deadline read as
their preference (2026-11-09: a follow-up was staged into the same day three days running). A
deadline whose miss cannot be undone is tagged and calendared the day it is first seen and
closes only on evidence (2026-11-06: an enrollment window closed unanswered). The scheduling
steps moved, word for word, from SKILL.md into [scheduling-protocol.md](scheduling-protocol.md)
to make room for the two binding rules.

**Version 2.0.0** (v5, 2026-10-05) removes `scripts/overlap.py` and the
shared time-block layer it read: no seat ever published the layer, and
scheduling now reads each account's calendar through its own connector, with
the v5 account-routing guard choosing the account. `holds_state.py` drops its
in-file self-test (pytest covers it) and the finished one-time `migrate`, and
gains recurring-instance releases: `--instance YYYY-MM-DD` releases one day,
`--series` the whole series, and a bare release of a recurring hold is refused
(lesson 2026-09-03). The 1.3.0 text that described the layer is in
[preserved.md](preserved.md).

**Version 1.3.0** (2026-09-20) adds the shared time-block layer and the
`scripts/overlap.py` cross-owner overlap service (§3): scheduling checks
consume every seat's published blocks, not just the seat's own reachable
accounts. Nothing here writes to a calendar.

**Version 1.2.0** (2026-09-01) ships
`preferences.example.json` and a guided `synthesis-onboarding init` interview.
Both create the private path below without copying any person's rules from a
reference machine. The onboarding validator checks the required scheduling,
tier, and calendar-guardian shape before the layer is reported installed.

**Version 1.1.0** (2026-08-12)

## Related

- The message-guard skill (the v5 send guard) holds every send or draft this
  skill prepares until the principal approves that exact call, and scans its
  register.
- The daily-rituals skill runs the day-start/day-end cadence this skill's
  ledger and calendar review plug into.
- A principal's private overlay skill may extend this one with
  relationship-specific practice for a human EA; this skill is the doctrine
  layer both agent and overlay share.
