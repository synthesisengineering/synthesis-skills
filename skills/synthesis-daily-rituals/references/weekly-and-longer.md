# The Weekly Loose-Ends Review, and Quarterly and Longer Reviews

Read when the weekly review is owed (the session-start ritual line or
`ritual_state.py query weekly-review --workspace <W>` says so), and when running a quarterly,
six-month or annual review. `<rituals>` is this skill's folder.

Contents: When the weekly review is owed · Scope · Sources to scan · Classify each item · Output
requirements · Slipped through: the lapse register · Quarterly, six-month and annual reviews ·
Why the weekly review exists.

## When the weekly review is owed

**Owed-weekly gating (replaces the v2.8.0 Friday-only rule).** The review is owed once per week per workspace, anchored to Friday, and tracked as `weekly-review` records in the append-only ritual log. Run `python3 <rituals>/scripts/ritual_state.py query weekly-review --workspace <W>`: it answers `owed: false` when the latest review is dated on/after the most recent Friday, and then skip this step silently. When it answers `owed: true`, run the scan below — in whichever ritual notices first (Day-Start Step 1 checks the same condition), in any day-end mode including Quick Close — then record it:
`python3 <rituals>/scripts/ritual_state.py record --direction weekly-review --workspace <W> --date <the Friday this review satisfies>`.

**Record the obligation, not the day of the labor.** A review pulled forward to Thursday is recorded with Friday's date, because the marker names the obligation discharged. On 2026-08-20 a review done deliberately early was recorded as 2026-08-20; Friday was 2026-08-21, so every ritual for a week reported the review as owed, inviting either a wasted re-run or a trained-in habit of ignoring the flag. A review run late (Saturday, or Monday after a missed Friday) is recorded with the Friday it satisfies as well.

A `synthesis-catchup-ledger` sweep on/after that Friday counts as the week's review (record its date); and if this scan finds 2+ consecutive missed rituals, suggest running that skill — it is the recovery tool for broken cadence. This decoupling exists because a Friday-evening-only review is disabled by exactly the skip it is meant to catch.

## Scope

**Scope: past 14 calendar days.** Look back from today through 14 days ago. This captures the current week + the previous week — enough to surface items deferred across one weekend boundary, which is the typical failure mode.

## Sources to scan (read each one; do not infer)

- [ ] **Calendar Guardian — week and month horizons (v2.20.0).** Part of the owed-weekly review, so a skipped Friday still gets caught by the same gating:
  - **Week ahead:** sweep all configured calendars for collisions, overcommitted days (config thresholds), unanswered RSVPs, and prep-less meetings — while there is still time to move things. Flag every lead-time meeting (`.agents/meeting-preps.yaml`) in the coming week so research that needs more than a day starts early (v2.26.0). Candidates-to-move come with drafted notes, same contract as the nightly review.
  - **Month ahead:** scan for anything needing lead time — travel, conferences, deadlines, visits. Any commitment that should start an absence-coordination notification clock (its `notify_on_commit` cohort, or a lead-time deadline inside the coming month) gets flagged NOW; this scan is what makes "people hear as soon as it is known" true in practice rather than in intention.
- [ ] **The pull-request queue for this workspace's own repos (v2.35.0).** Run `python3 <rituals>/scripts/pr_queue_scan.py --workspace <W>`. It reads the workspace's `.agents/repos.yaml` — the same declaration the source-code sync uses — and reports, oldest first: review requests naming the principal, their own open PRs, and PRs in the declared repos that nobody else was asked to review (where dependency bots land). **Scope follows the manifest, so each workspace's review sees only its own repos** and no second list has to be maintained. The scan is deliberately NOT filtered by `ritual_sync`: that flag governs whether a working copy is fast-forwarded, which is a different question from whether a repo has a request waiting on a human — skill sources and context repos carry `ritual_sync: no` and still have PRs. It exits 0 always and names every repo it could not read, because **an unscanned queue must never read as an empty one**. Since v2.36.0 the scan dispatches by origin host: `bitbucket.org` repositories are scanned through the `pr_queue` helper the synthesis-bitbucket skill ships, and any other non-GitHub host stays NOT SCANNED with the host named as the reason. Origin: on 2026-08-28 the review reported one waiting-on item past seven days while a review request naming the principal sat 139 days old, unseen — the review had not missed it, it had not looked. The gap was written down that day and stayed open until 2026-09-05 because the day that found it never closed.
- [ ] `daily-plans/YYYY-MM-DD.md` for the past 14 calendar days. In each plan, look for:
  - Drafts (`### Draft N: ...`) without a following `**Sent:**` marker — these are unsent and the deadline already passed
  - Items under `## Priority Tasks → Do today — not negotiable` that lack a completion marker (✅ or "DONE" or strikethrough)
  - Existing `## Carryover open items` / `## Stale targets` sections — these are last week's loose ends that may or may not still be relevant
  - Anything under `## Decisions needed` that did not get a decision recorded
- [ ] Each active project's `CONTEXT.md` "Open Items" / "Decisions Needed" / "Open Questions" sections — flag items whose surrounding text has not changed in 14+ days
- [ ] Each active project's `## Waiting On Others` table — flag rows whose "Last asked" / "Asked at" timestamp is >7 days ago (one full work-week without a follow-up signals the ask got buried or forgotten)
- [ ] `sessions/YYYY-MM.md` for the current AND previous calendar month — scan for explicit personal commitments (the principal saying "I'll do X tomorrow" or "I'll send Y by EOD") and verify each has a matching completion record. Pattern-match on first-person future-tense verbs in the principal's own text, not in quoted teammate messages.
- [ ] **The lapse register's last 14 days** (see "Slipped through" below).

## Classify each surfaced item

- **STILL RELEVANT** → carry into Monday by appending to Friday's daily plan `## Carried Items` section in the canonical format the cockpit reads. Include: the item description, the original date it surfaced, the original source (which plan / which CONTEXT.md / which Slack thread). This is what Monday's day-start picks up.
- **OBSOLETE** → annotate IN PLACE on the original source file with a one-line reason (e.g., "obviated by Y on YYYY-MM-DD", "stakeholder OOO through Z", "decision moot post-X"). These items stop appearing in future weekly reviews because they're now marked. Do NOT delete — the annotation is the record that the item was triaged.
- **AMBIGUOUS** → surface to the user with a brief context block. They decide carry-forward vs close. Do not guess; for items that touch other people's commitments or strategic direction, the user must be the one to call it.

An item whose date passed with no decision is not OBSOLETE by default: mark it `**Lapsed:**` at its source and give it a register row (Day-End Step 4b) before classifying it.

## Output requirements

- [ ] Add a `## Weekly Loose-Ends Review` section to today's (Friday's) daily plan. Structure: scan summary at top (count of items by classification + per-source breakdown), then the explicit STILL RELEVANT list (these are what Monday picks up), then OBSOLETE-with-reason list (audit trail), then AMBIGUOUS list (decision queue for the user), then **Slipped through**.
- [ ] If items in STILL RELEVANT need to be tracked across the weekend, populate today's daily plan `## Carried Items` section. (Monday's plan, when created, will pull from there as part of normal day-start.)
- [ ] Annotate OBSOLETE items in their ORIGINAL source files (not in this review section) so they get marked once and stay marked.
- [ ] Leave every changed plan and annotation on disk under this session's claims; Day-End Step 11 publishes the final day-end batch.

**Failure mode to avoid:** writing a `## Weekly Loose-Ends Review` section header without actually scanning the sources. The value is in the scan. If sources have not been read in this invocation, do not write the section — note "Weekly Loose-Ends Review skipped — scan not performed this invocation" in the plan and surface the gap to the user.

## Slipped through: the lapse register

Each workspace keeps a lapse register in its own records (the workspace instructions name the file). It is **permanent history: append rows, never remove or rewrite them.** One row per item that slipped:

- it passed its date with no decision from the principal (**lapsed**), or
- it sat past its date until the principal let it go (**let go after its date**).

Rows are facts, each with a pointer to where the item waited: `| Lapsed | Item | Where it waited | Why it lapsed | Outcome |`. A row added in error is corrected by a dated note beneath the table, never by deleting it.

The weekly review reads the register for its 14-day window and lists every row under **Slipped through**, with where each one waited and any pattern that repeats (the same kind of item, the same source, the same day of the week). Origin, 2026-10-01: an event-bound decision passed with no answer and was logged as "released", which hid the slip from the review it exists to inform.

## Quarterly, six-month and annual reviews

These read the lapse register for their whole window, so a longer review shows what slipped through the cracks and which patterns persist. The principal asked for this on 2026-10-05. No script runs them: whichever session runs one starts from the register.

- [ ] Read every register row in the window, plus the weekly reviews' **Slipped through** sections.
- [ ] Group the rows by pattern: the kind of item (acknowledgment, event decision, reply, registration), the source where it waited (a plan section, a context ledger, a thread), the weekday, and what was happening (travel, illness, a launch week).
- [ ] For each pattern that repeats, name one change that would have caught it (a decay tag at creation, an earlier do-by, a calendar block, a delegate), and put it to the principal as a decision. Never change a rule on the principal's behalf.
- [ ] Record the review with the window, counts by pattern and the decisions asked, in the principal's records, and point to it from that day's plan.

## Why the weekly review exists

This step exists because work falls through the cracks during a week. A missed close-of-business ritual means the next day's plan doesn't pick up the open threads from the day before. By Friday, several items can be stranded invisibly. The Friday review catches these BEFORE the weekend disconnects fresh context, and assembles a clean carryover list for Monday.

**Idempotency:** if a Friday review was missed and the agent runs this step on a later weekday, the scan still works because it's date-bounded (past 14 calendar days from today), not weekday-bounded. The Friday-default is about WHEN it normally fires; the scan output is meaningful on any day.
