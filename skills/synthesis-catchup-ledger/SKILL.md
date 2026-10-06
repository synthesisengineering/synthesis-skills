---
name: synthesis-catchup-ledger
description: "Reconcile missed and pending commitments after a break in the daily-ritual cadence: sweep plans, transcripts and context over any window, classify every item into a dated catch-up ledger, and route survivors without flooding the plan. Use for post-vacation catch-up or what did I miss."
license: "CC0-1.0"
depends_on: ["synthesis-daily-rituals", "synthesis-project-management", "synthesis-context-lifecycle"]
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Catch-up Ledger

Reconcile what was promised against what happened after a break in the daily-ritual cadence. What this skill produces:

A **catch-up ledger**: one dated markdown document that reconciles an arbitrary look-back window (2 weeks, 6 weeks, a quarter) into classified, routed, honest state. The ledger is the accounting close for a period of interrupted attention. After reading it, the person knows: what still needs doing (prioritized), what got done late (credit recorded), what died (with the lesson extracted), and what was never theirs to carry (released).

## Binding rules

1. **Bound the window with verified time.** Run `date`; start at the later of the requested look-back and the last ledger's ratchet marker; check elapsed time against `git log`, never impressions.
2. **The scanner is a candidate generator, not the truth.** Cross-check every candidate against current sources before classifying it.
3. **Every item gets exactly one state:** DONE-LATE, OPEN-ACTIONABLE, OPEN-DECAYING, DELEGATED-UNVERIFIED, OBSOLETE, or EXPIRED → LESSON. Each routes differently.
4. **No item enters the ledger without a source citation** (file path or permalink). Nothing from memory alone.
5. **For another project's item, the owning project's CONTEXT.md wins** over index descriptions, roll-ups and third-party mentions.
6. **An expired item is data about detection latency, not a character flaw.** Extract the lesson, then release it explicitly.
7. **Route, don't flood.** The daily plan gets only today's 3-7 open items plus a pointer to the ledger.
8. **Annotate OBSOLETE items at their source and update the ratchet marker,** so the next sweep is incremental.
9. **Keep the template's section headings and table shapes.** synthesis-console parses them; a change there updates the console in the same session.
10. **Write for a person recovering from a busy stretch, not an auditor:** lead with what is actionable; record done-late items as completions.
11. **Publish exact paths only;** never use broad staging.
12. **A truncated preview is a pointer, never content.** The scanner marks every cut line `…[truncated: N chars, open L<n>]`; open that line before quoting or classifying it. A preview cut to one letter was once completed as the opposite of what the file said.

## Contents

- [references/protocol.md](references/protocol.md): the console consumer note, Steps 1 to 6 with the ledger template, tone requirements, configuration. Read it when running a sweep.
- [references/background.md](references/background.md): the problem, the design rationale, and the neighboring skills. Read it once, or when choosing between this skill and the Weekly Loose-Ends Review.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 0.3.0 text now lives.
- Classification taxonomy, When to run, Protocol in brief: below.

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

## Protocol in brief

The steps in full, with the ledger template, are in references/protocol.md.

1. **Step 1 — Anchor and bound the window.**
2. **Step 2 — Mechanical scan (bundled script).** It prints, grouped by file, unchecked tasks, drafts without `**Sent:**`, decisions without `**Decided:**` and carryover sections, then totals; a line too long for its preview ends `…[truncated: N chars, open L<n>]`. Exit 0 when the scan completes, 2 on bad arguments.

   ```bash
   python3 catchup_scan.py <daily_plans_dir> --start YYYY-MM-DD --end YYYY-MM-DD
   ```

3. **Step 3 — Judgment pass over wider sources:** transcripts, project context, live systems where cheap. Run Slack and transcript syncs first.
4. **Step 4 — Write the ledger** at `{action_plan_repo}/catchup-ledgers/YYYY-MM-DD.md`.
5. **Step 5 — Route, don't flood.**
6. **Step 6 — Record readiness.**
