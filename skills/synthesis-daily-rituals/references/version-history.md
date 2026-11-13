# Daily rituals — version history and rationale

The operating checklists live in [SKILL.md](../SKILL.md). This file keeps the
release-by-release record of why each rule exists — the incidents, the
design choices, the config schemas each version introduced — so the main
document can stay within the repository's 500-line budget without losing
the reasoning. Newest first.

## v3.10.0 — What other people rely on

v3.10.0 (2026-11-12) adds a health check of everything a person other than the principal relies
on. A workspace declares each one as `relied_on` in the ritual config, with who relies on it and
the command that says whether it is healthy, and `relied_on.py` runs them: whatever is down prints
first, a check still running at its timeout is stopped with everything it started, and an entry
that cannot be run as written counts as down. Day-start, each mid-day sync and day-end run it
first, in every mode. A `DOWN` line is the first thing in the plan, under
`## Down: needs your attention`, and in the reply to the principal, ahead of the critical
deadlines (binding rule 16). It is an incident: the principal is told first, with who is affected
and what the fix is, and the people affected are told only on the principal's approval. A test
set up on a principal's own laptop had been given to two colleagues, who came to rely on it. It
stopped when the app that ran it restarted, two scheduled check-ins ran afterwards without looking
at it, and it was found hours later by accident. The rule in prose had not held, so the check is a
command each ritual runs. An autopilot run checks the same at every wake (synthesis-autopilot
4.1.0).

## v3.9.0 — Travel for in-person events

v3.9.0 (2026-11-11) makes travel a mechanical part of the rituals. A workspace turns the check on
with `travel_check` in the ritual config. Day-start, mid-day and day-end then run
`travel_check.py` (in synthesis-chief-of-staff) over that day and the six after, put each flagged
event in the plan under `## Travel: needs your attention`, and read the live source again for the
travel blocks of today and tomorrow. `ritual_state.py record` takes the result as `--travel` and
refuses without it, with one for other days, or while it holds an event that lacks its travel. A
leaving or returning time in a plan or draft comes from a travel block. An evening event 28 miles
from a principal's home had been carried through three plans and a day-start with no way to get
there, and two estimated times had gone out.

The same release reads the plan's choices. The invitation to that evening had been put to the
principal as a bare accept or decline, with no recommendation and no trip, and he said yes.
`ritual_state.py record` now reads the day's plan in each declared plan folder and refuses while an
open item that offers options has no `Recommendation:` line, or, when it is an accept-or-decline or
carries a `Commits:` line, no `Consequences:` line (binding rule 15, `plan-format.md`). A travel
result must also agree with itself: its dates are read as dates, and its counts and verdict are
checked against its events.

## v3.8.0 — LinkedIn messages; deadlines that live in drafts

v3.8.0 (2026-11-11) adds LinkedIn messages as a declared surface: `linkedin_messages.py` reads the
conversation list's saved text, lists the conversations that end with someone else and states how
far back the read went; the `linkedin` watermark moves only with a complete read. Both inboxes are
read, the focused one and the other one, where messages from people the account is not connected
to are filed; each has its own address and its own watermark target. The read opens LinkedIn's
new-message view, because the bare messaging page opens the newest conversation by
itself and marks it read, and it stops at a named day, because the list loads older conversations
for as long as it is scrolled ([linkedin-messages.md](linkedin-messages.md)). A principal had found
messages there that no ritual had shown him. The deadline sweep also reads folders a workspace declares as
`records_dirs` (drafts, a ledger): nine draft files and a ledger carried their own `**Decays:**`
lines and were never read. A plan outranks a record.

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
