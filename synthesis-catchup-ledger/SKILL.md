---
name: synthesis-catchup-ledger
description: Reconcile pending, missed, and incomplete commitments after any gap in the daily-ritual cadence (travel, family visits, crunch weeks). Sweeps daily plans, transcripts, and project context over an arbitrary window; classifies every surfaced item (including expired-for-learning); produces a dated catch-up ledger document; routes survivors without flooding the daily plan. Use when asked to: catch up on missed tasks, sweep pending items, catch-up ledger, reconcile backlog, what did I miss, post-vacation catch-up, falling behind recovery.
---

# Synthesis Catch-up Ledger

**Version 0.2.0** (2026-07-07)

> **Consumer note (v0.2.0):** synthesis-console v0.14+ renders ledgers live at
> `/ledger` — it classifies H2 sections by the heading keywords used in this
> skill's output sections ("Do now", "Verify before re-adding", "Done late",
> "Expired", "Released") and reads per-row state from a `State` table column
> when present. Ledger files live at `<knowledge-root>/catchup-ledgers/YYYY-MM-DD.md`.
> If this skill's section vocabulary or table shapes change, update the
> console's `src/parsers/ledger.ts` + `docs/cockpit-design.md` in the same
> session — producer and consumer must change together.

## The problem

Falling behind is part of life. Travel, family visits, illness, and crunch weeks interrupt the daily-ritual cadence, and the interruption itself is never the failure. The failure mode is silent: commitments made before the gap decay invisibly, because every existing artifact is scoped to a unit of time that assumes continuity. Daily plans capture one day's intent. Weekly loose-ends reviews (synthesis-daily-rituals v2.8.0) assume Fridays happen. Project CONTEXT files capture project state, not personal commitments. When the cadence breaks, nothing reconciles what was promised against what happened.

The result, observed repeatedly in practice: items survive as anxiety rather than as records. The person knows they're behind but not on what, so the backlog feels larger than it is, and genuinely-expired items consume attention that live items need.

## What this skill produces

A **catch-up ledger**: one dated markdown document that reconciles an arbitrary look-back window (2 weeks, 6 weeks, a quarter) into classified, routed, honest state. The ledger is the accounting close for a period of interrupted attention. After reading it, the person knows: what still needs doing (prioritized), what got done late (credit recorded), what died (with the lesson extracted), and what was never theirs to carry (released).

## Design rationale (thinking-framework summary)

- **First principles:** untracked decay is invisible; the missing primitive is periodic reconciliation, distinct from daily planning.
- **Systems:** sources → deterministic scan → judgment classification → routing → ratchet. The ratchet marker (last-sweep date in the ledger) makes sweeps compose instead of re-scanning history.
- **Complexity:** commitment states are not binary; the taxonomy below names six distinct states because each routes differently.
- **Analogy:** mark-and-sweep garbage collection for commitments. Roots = the source artifacts; live objects = items still referenced and still valuable; collection = explicit release with lesson extraction. Also: an accounting reconciliation — hence "ledger."
- **Design:** the reader experience is one document, kindest-possible honesty, biggest-leverage items first. Expired items get a *learning* section, not a guilt section.

## Classification taxonomy

Every surfaced item gets exactly one state:

| State | Meaning | Routing |
|-------|---------|---------|
| **DONE-LATE** | Completed after its intended window | Record in ledger (credit + pattern data); no further action |
| **OPEN-ACTIONABLE** | Still doable; value substantially intact | Top of ledger; feed into daily plans gradually (see Routing) |
| **OPEN-DECAYING** | Still doable but value eroding with time | Ledger with explicit do-by date; first claim on the next work block |
| **DELEGATED-UNVERIFIED** | Handed to someone; completion never confirmed | Verify before re-adding; one check message or ticket-status read |
| **OBSOLETE** | Events mooted it | Annotate in place at the original source; record in ledger; release |
| **EXPIRED → LESSON** | The window closed; it cannot be done now | Extract the learning (what signal was missed, what would have caught it); record; explicitly release |

The EXPIRED category is the one most systems omit and the one that matters most for learning. An expired item is data about detection latency, not a character flaw. Each expired entry answers: what was the opportunity, when did the window close, what earlier signal existed, and what (if anything) should change so the same class of item surfaces sooner next time. If nothing should change — sometimes the right call was to drop it — say so and release it cleanly.

## When to run

- After any gap of 2+ missed daily rituals (the primary trigger).
- On request: "catch me up on everything from the past N weeks."
- Quarterly, as hygiene, even when the cadence held — long-running items drift below daily-plan visibility.
- NOT as a substitute for the Friday Weekly Loose-Ends Review (synthesis-daily-rituals Day-End Step 10). That review is the steady-state 14-day forward-looking catch; this skill is the recovery tool for broken cadence and the deep-look tool for long windows. They share the classification mindset; this skill adds the learning category, the arbitrary window, and the standalone artifact.

## Protocol

### Step 1 — Anchor and bound the window

Run `date` for today's authoritative date. Choose the window start: the later of (a) the user-requested look-back, (b) the ratchet marker in the most recent prior ledger (if one exists). Record both in the ledger header. Never trust in-context impressions of "how long it's been" — verify against `git log` per the temporal-verification discipline (synthesis-checkpoint).

### Step 2 — Mechanical scan (bundled script)

Run the bundled scanner over the daily-plans directory:

```bash
python3 catchup_scan.py <daily_plans_dir> --start YYYY-MM-DD --end YYYY-MM-DD
```

The script emits, grouped by file: unchecked task items under priority headings, draft blocks lacking a `**Sent:**` marker, decision headings lacking a `**Decided:**` marker, and the contents of carryover/backlog/waiting sections. It is a CANDIDATE GENERATOR, not the truth — items it surfaces may already be resolved in sources it cannot see (a Slack thread, a merged PR, a meeting decision).

### Step 3 — Judgment pass over wider sources

For each scan candidate AND for commitments visible in sources the script does not parse, cross-check current truth before classifying:

- Local transcripts (Slack channels/DMs, meeting transcripts) for: "I'll …" commitments by the person, asks directed at the person, and replies that resolved items after the plan was written.
- Project CONTEXT/session logs for items marked open that later sessions closed.
- Live systems where cheap (ticket status, PR state, message threads) — per the cache-vs-truth discipline, the artifact trail is a cache; verify before classifying anything DELEGATED-UNVERIFIED or DONE-LATE.

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

### Step 6 — Commit

Commit and push the ledger (and any annotated sources) in the same invocation, per the standard commit protocol: stage only files this invocation touched, never `git add -A`.

## Tone requirements for the ledger

The ledger is written for a person recovering from a busy stretch, not for an auditor. Requirements: lead with what's actionable, not with what was missed; state expirations as facts with lessons, never as failures; record done-late items as completions, not as tardiness; keep the patterns section observational. One sentence of perspective is appropriate; extended commentary is not.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `daily_plans_path` | `daily-plans/` | Scanned by the bundled script |
| `ledger_path` | `catchup-ledgers/` | Output location, sibling to daily plans |
| `default_window_weeks` | 6 | When the user doesn't specify and no ratchet exists |
| `plan_feed_size` | 3-7 items | Max OPEN items routed into any single daily plan |

## Relationship to neighboring skills

- **synthesis-daily-rituals** — the Weekly Loose-Ends Review (Day-End Step 10) is the steady-state catch; this skill is the broken-cadence recovery + long-window deep look. A daily ritual that detects 2+ missed days should suggest invoking this skill.
- **synthesis-checkpoint** — provides the date/state verification used in Step 1.
- **synthesis-context-lifecycle** — project-scoped memory management; this skill is person-scoped commitment management. The ledger may cite CONTEXT files but never replaces them.
- **synthesis-slack-sync / synthesis-meeting-transcripts** — produce the transcript sources Step 3 reads. Run syncs BEFORE the sweep so classification works from current truth.
