# Grounding discipline: when to apply, and the self-check

When the binding rules apply, when they do not, and the twelve questions to ask before an output ships, one per rule and in the rules' order. Read it before sending an output that states a fact, records an event or claims an absence. The binding rules in SKILL.md govern where this file and they differ.

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
