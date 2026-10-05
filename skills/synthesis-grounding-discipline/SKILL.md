---
name: synthesis-grounding-discipline
description: "Keep agent output tied to evidence: record only what a source surfaced, re-verify cached facts, prove absence with a positive control, never complete truncated output, and validate paths before writes or deletes. Use before recording, quoting, claiming absence or deleting."
license: "Apache-2.0"
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  format: v5
---

# Synthesis Grounding Discipline

Twelve checks that stop an agent from claiming more than its evidence supports. Apply them at the moments where a plausible claim and a true one come apart.

## Binding rules

Numbers are load-bearing: other skills cite them. New rules are appended, never inserted.

1. **Record open loops as open.** Never record an event that fills a narrative gap without an external source; "sent, awaiting reply" is a complete fact. A false closure stops anyone from checking again.
2. **No quote without a tool result from this session.** The same goes for attributed acts ("she approved"). Made-up attribution puts words in a real person's mouth.
3. **Context files, plans and memories are caches.** Re-verify a load-bearing fact against the live system before it enters any output, and name the command class used.
4. **Name the layer.** Runtime state and infrastructure-as-code state are different truths; reconcile which layer each party checked before retracting anything.
5. **Read the evidence in hand first.** A screenshot, pasted error or log outranks every hypothesis.
6. **Count before generalizing.** "All", "none", "dominant" are counts; show the command that counted.
7. **A negative finding needs a positive control** through the same mechanism, and is scoped to what was tested, not to the world.
8. **Truncated output decides what to open, never what to claim.** Never complete a cut string.
9. **Zero search results prove nothing.** Do a bounded direct read of the primary source and state its bounds.
10. **Verify a write target before writing.** Locate it, confirm its identity (`git remote -v`), and ask when several match.
11. **Destructive operations:** move, verify, then delete; `git mv`/`git rm` in repos; kill by PID, never a loose `pkill -f`; read before stream-editing; validate every recursive-delete target independently; represent "no target" as `None`, never an empty path.
12. **Archived history is not current state.** Reconcile anything from an import against the newest material held elsewhere before calling it open.

## Contents

- [references/catalog.md](references/catalog.md): the full text of rules 1 to 12, each with the real failure it prevented and its procedure. Read it when applying a rule for the first time in a session, or when a case is unclear.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.x text now lives (ruling D8).
- Why this exists, When to apply, The self-check, Relationship to other skills, The underlying principle: below.

## Why this exists

A discipline for keeping AI-agent output anchored to external evidence. The failure family it catches is the mirror image of the one [synthesis-anti-shortcuts](../synthesis-anti-shortcuts/SKILL.md) catches: anti-shortcuts stops the agent from doing less than the work requires; grounding discipline stops the agent from claiming more than the evidence supports. Both are narrative-quality optimizations working against external truth — one dismisses real concerns to keep the story tidy, the other invents satisfying completions to keep the story moving.

The shapes in this catalog are universal to LLM agents, not quirks of one model or one workflow. A language model generates the most plausible continuation. Most of the time the plausible and the true coincide, which is exactly what makes the divergent cases dangerous: a fabricated reply reads like a real one, a stale cached fact reads like a fresh one, a null result from a broken probe reads like a verified absence. None of these announce themselves. The only defense is procedural — a set of checks applied at the moments where plausibility and truth come apart.

This skill is that set. Each catalog entry names the rule, the failure shape it prevents (with one anonymized incident vignette — every entry here was paid for in production), and the compliance procedure. A closing self-check compresses the catalog into the questions to ask before any output ships.

For [decisive uncertainty](../synthesis-thinking-framework/references/decisive-uncertainty.md), bind the question to the source that can change the decision. Exact quotes establish presence; a reviewer must still establish support. An executed observation can refute a prediction without becoming a successful acceptance result. Preserve those negative results, source generations and limitations when the plan changes.

## When to Apply

- Before recording any event, decision, message, or state change into a durable file (context files, session logs, transcripts, plans, reports)
- Before quoting or paraphrasing anything attributed to another person
- Before propagating a fact from a context file, plan, memory, or earlier conversation into any output
- Before reporting that something is absent, missing, unsent, undecided, or nonexistent
- Before writing into a directory or deleting anything
- Whenever a claim about external system state (reviews, deploys, CI, tickets, branches) is about to enter a draft

## When NOT to Apply

- Internal reasoning and ideation — speculation inside your own analysis is fine; recording the speculation as if it were an observed fact is not
- Explicitly-labeled hypotheticals ("if the reviewer has approved, then...") where the conditional framing is preserved in the output
- Content the user supplied directly in the current conversation — the user's own statements need no tool citation (though claims about systems still get re-verified before propagating outward)

## The Self-Check

Before sending any output that states a fact, records an event, or claims an absence:

1. **Every recorded event:** does it have an external source, or does it close a narrative loop by imagination? Open loops get recorded as open.
2. **Every quote and attribution:** is there a tool result in this session to cite? No citation, no quote.
3. **Every fact about external system state:** learned this session via a verifying command, or propagated from a cache? Cache → verify first, and name the command class.
4. **Every configuration claim:** which layer — runtime or IaC? Is the layer named in the claim?
5. **Any artifact in hand** (screenshot, pasted error, log): read before theorizing?
6. **Every quantifier over a corpus** ("all," "none," "dominant," "standard"): is the count attached, with the command that produced it?
7. **Every negative finding:** did a positive control exercise the exact mechanism? Is the claim scoped to the instrument ("X returns zero for Y") rather than the world ("none exists")?
8. **Every string used as evidence:** complete, or truncated? Truncated → open the source before any claim depends on it.
9. **Every zero-result search:** followed by a bounded direct read with stated bounds?
10. **Every write target:** located and identity-verified with a command?
11. **Every destructive operation:** target validated independently, sentinel non-path-typed, move-verify-delete order respected?
12. **Every claim drawn from an archive or backfill:** reconciled against the newest material held elsewhere, and scoped to where you actually looked?

If any answer is wrong, fix the grounding before sending — not after.

## Relationship to Other Skills

- **[synthesis-anti-shortcuts](../synthesis-anti-shortcuts/SKILL.md)** — The effort-side sibling. Anti-shortcuts catches deferral, dismissal, and false consultation; this skill catches fabrication, stale propagation, and false absence. An output can fail both at once — a confabulated "already done" is simultaneously a shortcut and a grounding failure.
- **[synthesis-checkpoint](../synthesis-checkpoint/SKILL.md)** — The session-state instance of cache-vs-truth: verified time, git history, and context files re-synced on drift signals. Checkpoint covers "where are we"; this skill covers every fact leaving the session in an output.
- **[synthesis-fact-checking](../synthesis-fact-checking/SKILL.md)** — Verifies claims in *content being reviewed*; this skill governs claims the *agent itself* is about to make.
- **[synthesis-implementation-integrity](../synthesis-implementation-integrity/SKILL.md)** — Post-implementation verification that work is actually complete. Its "never claim a check that did not run" is this discipline applied to self-reports.
- **[synthesis-slack-sync](../synthesis-slack-sync/SKILL.md)** — Carries the messaging-platform instance of rules 2, 7, and 9: transcripts-first lookups, provenance for synced content, and bounded reads for absence claims.

## The Underlying Principle

Every entry in this catalog is one mechanism: **a claim's plausibility is not its evidence.** LLM agents are plausibility engines — that is what generation is — so the plausible-but-unverified claim is the native failure mode, the thing the system produces when nothing intervenes. The intervention cannot be "try to be accurate," because the confabulated reply, the stale approval, the mis-aimed probe, and the completed truncation all *feel* accurate from the inside.

The intervention is structural: bind every class of claim to the class of evidence that grounds it — a tool citation for quotes, a verifying command for system state, a count for quantifiers, a positive control for absences, a listing for existence, an independent validation for destructive targets. When the evidence class is missing, the claim does not ship. The agent that applies this discipline is not the one that never errs; it is the one whose errors cannot silently reach an output.
