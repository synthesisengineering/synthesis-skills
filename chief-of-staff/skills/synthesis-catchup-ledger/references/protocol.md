# Catch-up ledger: the protocol

The six protocol steps with the ledger template, the tone requirements and the configuration, moved verbatim from the 0.3.0 SKILL.md. The console consumer note sits with them because it governs the template's headings. Read it when running a sweep.

Contents:
- The console consumer note: which headings and columns synthesis-console parses
- Protocol: Step 1 anchor and bound the window, Step 2 mechanical scan, Step 3 judgment pass, Step 4 write the ledger (template), Step 5 route, Step 6 record readiness
- Tone requirements for the ledger
- Configuration

## Console consumer note

> **Consumer note (v0.2.0):** synthesis-console v0.14+ renders ledgers live at
> `/ledger` — it classifies H2 sections by the heading keywords used in this
> skill's output sections ("Do now", "Verify before re-adding", "Done late",
> "Expired", "Released") and reads per-row state from a `State` table column
> when present. Ledger files live at `<knowledge-root>/catchup-ledgers/YYYY-MM-DD.md`.
> If this skill's section vocabulary or table shapes change, update the
> console's `src/parsers/ledger.ts` + `docs/cockpit-design.md` in the same
> session — producer and consumer must change together.

## Protocol

### Step 1 — Anchor and bound the window

Run `date` for today's authoritative date. Choose the window start: the later of (a) the user-requested look-back, (b) the ratchet marker in the most recent prior ledger (if one exists). Record both in the ledger header. Never trust in-context impressions of "how long it's been" — verify against `git log` per the temporal-verification discipline (synthesis-checkpoint).

### Step 2 — Mechanical scan (bundled script)

Run the bundled scanner over the daily-plans directory:

```bash
python3 catchup_scan.py <daily_plans_dir> --start YYYY-MM-DD --end YYYY-MM-DD
```

The script emits, grouped by file: unchecked task items under priority headings, draft blocks lacking a `**Sent:**` marker, decision headings lacking a `**Decided:**` marker, and the contents of carryover/backlog/waiting sections. It is a CANDIDATE GENERATOR, not the truth — items it surfaces may already be resolved in sources it cannot see (a Slack thread, a merged PR, a meeting decision).

Items and carryover lines are previews: a line longer than the preview width ends `…[truncated: N chars, open L<n>]`. Treat that preview as a pointer and open the line before any claim depends on it. (Field case, 2026-08-18: a preview cut to "`gchat-sync.yaml` n" was completed as "not created"; the word was "needs", the file existed, and five days of messages went unread behind the invented gap.)

### Step 3 — Judgment pass over wider sources

For each scan candidate AND for commitments visible in sources the script does not parse, cross-check current truth before classifying:

- Local transcripts (Slack channels/DMs, meeting transcripts) for: "I'll …" commitments by the person, asks directed at the person, and replies that resolved items after the plan was written.
- Project CONTEXT/session logs for items marked open that later sessions closed.
- Live systems where cheap (ticket status, PR state, message threads) — per the cache-vs-truth discipline, the artifact trail is a cache; verify before classifying anything DELEGATED-UNVERIFIED or DONE-LATE.
- **Cross-project items: the OWNING project's CONTEXT wins (v0.2.1).** Before classifying an item that belongs to another project — a decision, an approval, a delegated task tracked elsewhere — read that project's CONTEXT.md, not index.yaml descriptions, roll-up summaries, or a third project's mention of it. Secondary caches lose to the owner's working memory. (Field case: an approval recorded in the owning CONTEXT while a stale index description still said "pending" — the ledger briefly carried the wrong state.)

Classification requires a source citation (file path or permalink) per item. No item enters the ledger from memory alone.

### Step 4 — Write the ledger

Location: `{action_plan_repo}/catchup-ledgers/YYYY-MM-DD.md` (sibling convention to `daily-plans/`). Structure:

```markdown
# Catch-up Ledger — YYYY-MM-DD

**Window:** YYYY-MM-DD → YYYY-MM-DD (N weeks) · **Trigger:** [gap description]
**Sources scanned:** [list with counts]
**Ratchet:** next sweep starts at YYYY-MM-DD

## Do now (OPEN-ACTIONABLE + OPEN-DECAYING, priority order)
[The shortlist that feeds daily plans. Decaying items carry a do-by date.]

## Verify before re-adding (DELEGATED-UNVERIFIED)
[Item · who has it · one-line verification step]

## Done late (credit + pattern data)
[Item · intended window · actual completion · gap]

## Expired — learning extracted
[Item · window closed when · missed signal · change (or "none — right call was to drop")]

## Released (OBSOLETE)
[Item · what mooted it · source annotated Y/N]

## Patterns observed
[2-5 sentences: what classes of items decay fastest, where detection lagged, what the cadence break actually cost — and what it didn't.]
```

### Step 5 — Route, don't flood

- The daily plan receives ONLY today's slice of OPEN-ACTIONABLE/OPEN-DECAYING (3-7 items), plus a one-line pointer to the ledger. Dumping the full ledger into a daily plan recreates the unreadable-backlog problem the ledger exists to solve.
- OBSOLETE items get annotated at their original source (same convention as the Weekly Loose-Ends Review) so future scans skip them.
- EXPIRED lessons that generalize beyond the period get promoted to the lessons directory; period-specific ones stay in the ledger.
- Update the ratchet marker so the next sweep is incremental.

### Step 6 — Record readiness

Leave the ledger and annotated sources session-attributed and locally receipted. Publish their exact paths during explicit remote handoff or day-end under the repository policy; never use broad staging.

## Tone requirements for the ledger

The ledger is written for a person recovering from a busy stretch, not for an auditor. Requirements: lead with what's actionable, not with what was missed; state expirations as facts with lessons, never as failures; record done-late items as completions, not as tardiness; keep the patterns section observational. One sentence of perspective is appropriate; extended commentary is not.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `daily_plans_path` | `daily-plans/` | Scanned by the bundled script |
| `ledger_path` | `catchup-ledgers/` | Output location, sibling to daily plans |
| `default_window_weeks` | 6 | When the user doesn't specify and no ratchet exists |
| `plan_feed_size` | 3-7 items | Max OPEN items routed into any single daily plan |
