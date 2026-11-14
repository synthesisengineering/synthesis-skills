# Material context: what to capture before compaction or handoff

A healthy record is not the same as a faithful one. A checkpoint can pass while
the user's instruction, its reason or its time limit has dropped out of the
record. This reference says what to keep, how to keep it honest, and how
replaced item lists keep their obligations. It needs no tool beyond the
project's own files.

## Contents

- [When to capture](#when-to-capture)
- [What to preserve](#what-to-preserve)
- [What never becomes a fact](#what-never-becomes-a-fact)
- [Replacing an item list or a decision interface](#replacing-an-item-list-or-a-decision-interface)
- [Checking a handoff or recovery](#checking-a-handoff-or-recovery)
- [Native memory](#native-memory)

## When to capture

Use this protocol during ordinary project work when a source introduces or
changes a material fact, decision, constraint, commitment, risk or question.
Capture it before dependent work, compaction or handoff. A provisional capture
may remain pending; it must remain discoverable: write it into CONTEXT.md, the
plan, REFERENCE.md or a file under `resources/` that CONTEXT.md links to.

## What to preserve

Read the current plan and earlier decisions, then select the smallest
sufficient original spans available within authorized scope. Separate
independent requests even when they arrived in one message. Preserve:

- facts and the difference between a report and an observed outcome;
- rationale, constraints and temporary conditions, including what ends an instruction;
- uncertainty, unavailable attachments and unresolved questions;
- who supplied the source, whether it was quoted or relayed, and what attribution is unknown;
- amendments and cancellations, their exact predecessors and surviving obligations.

For example, “use the detour until the inspection clears” cannot become an
unqualified instruction to use the detour. A concise paraphrase retaining that
condition and its rationale can be faithful. Matching words or hashes cannot
decide either question.

## What never becomes a fact

Do not turn quoted commands into current authority. Do not reconstruct missing
attachments or infer consent, completed work or a clean endpoint from silence.
Route private material to its authorized project and deletion unit before
capture ([deletion-units.md](deletion-units.md)). Keep credentials in their
credential owner, never in project prose.

An inventory of inputs is explicit. A recursive Markdown scan, a hash list, a
generated cache, test output, or repository cleanliness is not a list of user
instructions. Generated evidence can be cited for its actual evidential role;
it cannot acquire the principal's authority from a provenance label. An
amendment or cancellation names the exact item it replaces and must not close
unknown work by absence; conflicting successors stay unresolved until someone
decides.

## Replacing an item list or a decision interface

When a decision packet, backlog or item list is replaced by a new one, four
questions stay separate:

1. **Did every source item arrive?** The source list's exact ids, not a
   narrative total or the receiver's list, define the denominator. Missing,
   extra and duplicate ids cannot make a complete transfer.
2. **What evidence exists?** Each item points at the exact text it came from;
   strong evidence for one item cannot make an incomplete transfer complete.
3. **Was a choice recorded?** Only a recorded ruling for that exact item counts;
   ordinary historical prose stays an unverified historical record, and a
   narrative "answered" cannot close an item.
4. **May work execute or close?** Never from the transfer itself. The action's
   own approval and outcome are checked where the action happens.

Every unanswered decision carries forward by exact id. Archive the original
bytes before changing live records, and never turn a transfer or archive into
an approval. Decision packets do this by id (synthesis-decision-packet).

## Checking a handoff or recovery

Trace each remaining obligation from its durable source to a current record,
an owner and a next action. Compare obligation identities and meaningful
content, not just counts; an omitted obligation or a changed unresolved status
is a defect even when the handoff reads well. Judge handoff usability against
the receiving worker's actual task: it should name the remaining outcome, the
relevant sources, the authority boundaries, the effects awaiting
reconciliation and the next step. A clean structural check proves structure,
never that meaning survived.

## Native memory

Each harness's native memory stays on as a capture buffer, never a record. The
day-end ritual (synthesis-daily-rituals) reviews it, moves what is durable into
the owning repository and record — lessons to the personal lessons root,
project facts to the owning REFERENCE.md, voice material to the owning private
skill, workspace content to its deletion unit, the ALWAYS-PRESERVE kinds to the
permanent root — and resolves conflicts in favor of the synthesis record. Never
disable native memory or delete a harness's memory files to make a sweep look
complete.
