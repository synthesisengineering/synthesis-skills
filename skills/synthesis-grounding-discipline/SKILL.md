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
- [references/background.md](references/background.md): why this discipline exists, how it relates to anti-shortcuts, checkpoint, fact-checking, implementation-integrity and slack-sync, and the principle under all twelve rules. Read it once per session, or when deciding between this skill and a sibling.
- When to apply, The self-check: below.

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
