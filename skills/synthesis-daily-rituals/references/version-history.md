# Daily rituals — version history and rationale

The operating checklists live in [SKILL.md](../SKILL.md). This file keeps the
release-by-release record of why each rule exists — the incidents, the
design choices, the config schemas each version introduced — so the main
document can stay within the repository's 500-line budget without losing
the reasoning. Newest first.

## v3.7.0 — Critical deadlines

v3.7.0 (2026-11-11) adds the `**Critical:**` tag for a deadline whose miss cannot be undone. On
2026-11-06 an enrollment window closed with its item still open: seen three weeks ahead, it had
been carried as a line in daily email reviews, one row among two hundred in a decision packet and
one dated item among a hundred, written up as optional, never calendared and never escalated. The
deadline sweep now reports critical items apart from the dated list, leading from seven days out,
due an alert at three days and one day, never lapsed, closed only when a closing mark carries
evidence; it also lists untagged items that read like a critical class. `ritual_state.py record`
refuses while one is past due, refuses a clean outcome over plans it could not read whole, and
needs each workspace to declare its plan folders in the ritual config. The 16:55 nudge sounds the
same alert on a day with no ritual. The rules are in [critical-deadlines.md](critical-deadlines.md).
The ritual procedure moved, word for word, from SKILL.md into [procedure.md](procedure.md) to make
room for the binding rule. `sync_watermark.py` writes its store under a lock: two workers advancing
at once had each rewritten the file from their own reading and lost 27 of 632 advances.

## v3.0.0 — Rewritten for synthesis v5

v3.0.0 (2026-10-05) rewrites the skill in the v5 format: a short SKILL.md with binding rules and
a contents list, and the checklists in files read when each is needed ([day-start.md](day-start.md),
[day-end.md](day-end.md), [mid-day-and-modes.md](mid-day-and-modes.md),
[weekly-and-longer.md](weekly-and-longer.md)). The rituals use the v5 commands: the board
(`synthesis who`, `synthesis inbox`), `synthesis doctor`, the context records doctor and
`synthesis handoff`. Scripts run as plain `python3` on the standard library, with a small YAML
reader so they work on Apple's Python. The acquisition receipts that gated every watermark are
gone (2026-10-01: connector syncs ran but bookmarks stopped advancing), as are the verified
launcher, worker artifact custody, credential-path inventories (the commit check refuses
credential file names instead) and the day-end installer (`synthesis install` lays out the
launcher and nudge). The ritual log and the watermark store move under the v5 home. Day-end
gains the native-memory sweep, the provenance scan and the lapse register. Every rule kept, and
every rule retired with its reason: [coverage-map.md](coverage-map.md).

## Earlier versions

- [version-history-2.27-to-2.45.md](version-history-2.27-to-2.45.md): 2.27.0 to 2.45.1 (watermarks, ritual state, the PR queue, mailboxes, ownership routing, concurrent seats, acquisition evidence).
- [version-history-2.3-to-2.26.md](version-history-2.3-to-2.26.md): 2.3.0 to 2.26.0 (lead-time preps, desk and workers, plan storage separation, Calendar Guardian, day-end closure, cockpit mode, draft conventions) and the rationale notes and principles.
