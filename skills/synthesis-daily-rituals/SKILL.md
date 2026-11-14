---
name: synthesis-daily-rituals
description: "Day-start, day-end, mid-day sync and the weekly review: sync every declared channel, mailbox and repo, sweep deadlines and lapses, plan and close the day. Use for: day start, day end, morning routine, end of day, quick close, daily ritual, weekly review, sync channels."
license: "Apache-2.0"
depends_on:
  - synthesis-context-lifecycle
  - synthesis-project-management
  - synthesis-slack-sync
  - synthesis-checkpoint
metadata:
  author: "Rajiv Pant"
  version: "3.17.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Daily Rituals

The principal's day-start, day-end, the syncs between them and the weekly review: close the gap
between what happened and what the principal knows, plan the day, and close it so nothing owed
slips silently. Each workspace runs its own; a project supplement may add repos and channels.

## Binding rules

1. **Anchor the date first** with `date`; every record uses that date, never memory or a commit time. The model has no clock, and a commit can land overnight.
2. **The declared lists decide:** every repo with `ritual_sync: yes`, every surface and every mailbox the workspace declares, every run. Never judge what "feels active"; a judgment layer let a repo drift unseen for six weeks.
3. **A run proves its own coverage:** open with `sync_watermark.py begin`, take every window from `window`, gate with `status --since run`. A read from this morning is not current now (2026-09-01: a 09:15 read hid a 09:27 answer).
4. **Every repo, mailbox and target lands in one named state with a denominator;** unscanned never reads as empty, and any surface not swept is named.
5. **Nothing decay-tagged passes its date silently:** send (on the principal's approval), re-date with a reason, or release. An item that passed its date with no decision is marked Lapsed and gets an append-only lapse-register row.
6. **Record every ritual,** in every mode, with `ritual_state.py record` and the logical workday as `--date`; a date after today is refused. A weekly review done early is recorded with the Friday it satisfies.
7. **Nothing sends without the principal's approval of the exact text.** Every draft is grounded in primary sources and re-checked against the live thread at send time.
8. **Workspace content stays in that workspace's records,** so deleting the workspace erases it; the person-side plan is a shell with pointers.
9. **Banners and spoken alerts carry counts and a pointer only,** never a client, repo, workspace or person name, and honor `~/.synthesis/quiet-audio`. Speakers are overheard and banners are screen-shared.
10. **Observe around live sessions:** claim only the files you write, fast-forward only unheld branches, never repair or re-run another session's work, release claims at the end.
11. **Native memory stays on.** Durable entries move into synthesis records archive-first; raw memory files are never deleted or edited.
12. **A critical deadline is never one item among many.** Tag a deadline whose miss cannot be undone `**Critical:** <class>` the day it is first seen. From seven days out it opens every plan and brief in its own section; it never lapses and closes only on evidence or the principal's own words; `ritual_state.py record` refuses while one is past due. An enrollment window once closed as one dated row among a hundred.
13. **LinkedIn's conversation list is read from the new-message view, never the bare messaging page,** which opens the newest conversation and marks it read. Scroll back to the day the plan names and stop there. Open a thread only when its preview cannot show whether something is owed, and name each one opened.
14. **An in-person event is not planned until its travel is.** Where the workspace checks travel, each ritual runs `travel_check.py` over the days ahead, no ritual is recorded while an event lacks its travel, and a leaving or returning time in a plan or draft is taken from a travel block, never estimated (2026-11-11).
15. **A choice in the plan is put with a recommendation, and with what it costs when it would commit the principal's time.** `ritual_state.py record` refuses while an open item that offers options lacks either (2026-11-11).
16. **What another person relies on is checked first, at every ritual:** run `relied_on.py`. A `DOWN` line opens the plan and the reply before anything else. It is an incident: the principal is told first, the people affected only on the principal's approval. A `NOT CHECKED` line is said first too, never read as all clear. A test two colleagues relied on once stopped, unseen through two check-ins.

## Contents

- [references/procedure.md](references/procedure.md): each ritual's order and commands. Read every time.
- [references/day-start.md](references/day-start.md): the full Day-Start checklist, Steps 1 to 8. Read at day-start.
- [references/day-end.md](references/day-end.md): modes and Steps 1 to 11, with the memory sweep, provenance scan and publishing. Read at day-end.
- [references/mid-day-and-modes.md](references/mid-day-and-modes.md): mid-day sync, observer and concurrent-sessions modes, audio alerts. Read on a sync request or when a mode applies.
- [references/weekly-and-longer.md](references/weekly-and-longer.md): the weekly loose-ends review, the lapse register, quarterly and longer reviews. Read when a review is owed.
- [references/scripts.md](references/scripts.md): each script's command line, output and exit codes. Read before running one.
- [references/plan-format.md](references/plan-format.md): the daily plan's structure and the section names the console reads. Read before writing a plan.
- [references/draft-grounding.md](references/draft-grounding.md): grounding, formatting, numbering and temporal checks for drafts. Read before any draft.
- [references/sync-watermarks.md](references/sync-watermarks.md): the watermark contract and the Google Chat target set. Read before any sync.
- [references/decay-sweep.md](references/decay-sweep.md): deadline tags, identity and the sweep's coverage. Read at Day-End Step 4b.
- [references/critical-deadlines.md](references/critical-deadlines.md): the Critical tag, its section in the plan, alerts, closure on evidence, and the plan folders each workspace declares. Read at day-start, at every sweep, and the day such a deadline is first seen.
- [references/linkedin-messages.md](references/linkedin-messages.md): LinkedIn messages as a declared surface: the declaration, the read from the new-message view, the coverage line, what is owed. Read before a sync in a workspace that declares it.
- [references/mailbox-manifest.md](references/mailbox-manifest.md): `.agents/mailboxes.yaml` and the mailbox states. Read before an email sweep.
- [references/ownership-routing.md](references/ownership-routing.md): which workspace owns an item, and which side of a conflict moves. Read at the catch-up read.
- [references/ritual-worker-contract.md](references/ritual-worker-contract.md): desk and workers, artifacts, plan storage separation. Read when a workers registry exists.
- [references/version-history.md](references/version-history.md), [references/version-history-2.27-to-2.45.md](references/version-history-2.27-to-2.45.md), [references/version-history-2.3-to-2.26.md](references/version-history-2.3-to-2.26.md): why each rule exists. Read when a reason matters.
- [references/coverage-map.md](references/coverage-map.md): the rewrite's record, with `references/preserved.md`, `references/preserved-skill-v2-part1.md`, `references/preserved-skill-v2-part2.md` and `references/preserved-retired-references.md`.

## Procedure

Each ritual's order and commands, with the scripts they run: [references/procedure.md](references/procedure.md). Read it every time, then the ritual's own checklist.
