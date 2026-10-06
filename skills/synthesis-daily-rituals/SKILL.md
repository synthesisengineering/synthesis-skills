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
  version: "3.0.0"
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
6. **Record every ritual,** in every mode, with `ritual_state.py record` and the logical workday as `--date`. A weekly review done early is recorded with the Friday it satisfies.
7. **Nothing sends without the principal's approval of the exact text.** Every draft is grounded in primary sources and re-checked against the live thread at send time.
8. **Workspace content stays in that workspace's records,** so deleting the workspace erases it; the person-side plan is a shell with pointers.
9. **Banners and spoken alerts carry counts and a pointer only,** never a client, repo, workspace or person name, and honor `~/.synthesis/quiet-audio`. Speakers are overheard and banners are screen-shared.
10. **Observe around live sessions:** claim only the files you write, fast-forward only unheld branches, never repair or re-run another session's work, release claims at the end.
11. **Native memory stays on.** Durable entries move into synthesis records archive-first; raw memory files are never deleted or edited.

## Contents

- **Procedure** (below): each ritual's order and commands. Read every time.
- [references/day-start.md](references/day-start.md): the full Day-Start checklist, Steps 1 to 8. Read at day-start.
- [references/day-end.md](references/day-end.md): modes and Steps 1 to 11, with the memory sweep, provenance scan and publishing. Read at day-end.
- [references/mid-day-and-modes.md](references/mid-day-and-modes.md): mid-day sync, observer and concurrent-sessions modes, audio alerts. Read on a sync request or when a mode applies.
- [references/weekly-and-longer.md](references/weekly-and-longer.md): the weekly loose-ends review, the lapse register, quarterly and longer reviews. Read when a review is owed.
- [references/scripts.md](references/scripts.md): each script's command line, output and exit codes. Read before running one.
- [references/plan-format.md](references/plan-format.md): the daily plan's structure and the section names the console reads. Read before writing a plan.
- [references/draft-grounding.md](references/draft-grounding.md): grounding, formatting, numbering and temporal checks for drafts. Read before any draft.
- [references/sync-watermarks.md](references/sync-watermarks.md): the watermark contract and the Google Chat target set. Read before any sync.
- [references/decay-sweep.md](references/decay-sweep.md): deadline tags, identity and the sweep's coverage. Read at Day-End Step 4b.
- [references/mailbox-manifest.md](references/mailbox-manifest.md): `.agents/mailboxes.yaml` and the mailbox states. Read before an email sweep.
- [references/ownership-routing.md](references/ownership-routing.md): which workspace owns an item, and which side of a conflict moves. Read at the catch-up read.
- [references/ritual-worker-contract.md](references/ritual-worker-contract.md): desk and workers, artifacts, plan storage separation. Read when a workers registry exists.
- [references/version-history.md](references/version-history.md), [references/version-history-2.27-to-2.45.md](references/version-history-2.27-to-2.45.md), [references/version-history-2.3-to-2.26.md](references/version-history-2.3-to-2.26.md): why each rule exists. Read when a reason matters.
- [references/coverage-map.md](references/coverage-map.md): where every 2.45.1 rule lives now. [references/preserved.md](references/preserved.md) (what was retired and why), [references/preserved-skill-v2-part1.md](references/preserved-skill-v2-part1.md), [references/preserved-skill-v2-part2.md](references/preserved-skill-v2-part2.md) and [references/preserved-retired-references.md](references/preserved-retired-references.md) keep the old text verbatim. Read only to review the rewrite.

## Procedure

`<rituals>` is this skill's folder; `<W>` the workspace (its folder under `~/workspaces/`). Scripts run with plain `python3`, standard library only.

**Day-start** ([day-start.md](references/day-start.md)): `date`; `synthesis who`, `synthesis inbox`; `synthesis doctor`; `python3 <synthesis-context-lifecycle>/scripts/context_doctor.py --root <knowledge root>` (exit 0 healthy, 1 defects, 2 cannot tell); `python3 <rituals>/scripts/portfolio_review.py` (at most three stale projects as decisions); `ritual_state.py query summary --workspace <W>` and `query weekly-review`; context optimization; `repo_state.py --workspace-root ~/workspaces/<W> --fetch --ff`; channel sync under the watermark gate (Slack, Chat via `gchat_preflight.py`, email via `mailboxes.py`, documents, meeting transcripts); inbox hygiene; catch-up read with ownership routing; `pr_queue_scan.py --workspace <W>`; the day plan with decay tags; morning messages; `ritual_state.py record --direction day-start`.

**Mid-day sync** ([mid-day-and-modes.md](references/mid-day-and-modes.md)): every declared surface, every target re-read, the same gate.

**Day-end** ([day-end.md](references/day-end.md)): ask f, q or o; final capture under the gate; source sync; integration sweep; tomorrow's calendar review; `decay_sweep.py` and the send-or-release pass with lapses recorded; lessons keep or drop; the native-memory sweep; `python3 <synthesis-agent-guardrails>/scripts/provenance_scan.py --since <today> <files written today>`; context capture with stamped open items `(as of YYYY-MM-DD, review Nd)`; `ritual_state.py record --direction day-end`; the weekly review if owed; then `synthesis handoff` per project worked, the records doctor with `--project`, and `repo_state.py --discover ~/workspaces/<W>` for anything stranded.

**Desk** (only with a workers registry): `python3 <rituals>/scripts/ritual_workers.py coverage` prints the coverage line that opens every brief.

Every script's exact command line, what it prints and its exit codes: [scripts.md](references/scripts.md).

The v5 install puts the `day-end` launcher (`day-end -q` opens a harness on the ritual) beside the runtime; `install.py --day-end` loads the weekday 16:55 nudge: one fixed banner unless every workspace expected to close today has closed.
