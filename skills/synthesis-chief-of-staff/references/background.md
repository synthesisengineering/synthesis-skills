# Chief of staff: background

Release notes for 1.1.0 to 2.0.0 and the skill's relationship to other skills.

## Release notes

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
