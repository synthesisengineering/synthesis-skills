---
name: synthesis-preplan
description: "Lock architecture decisions for a ticket or issue with real design choices: resolve delegated technical choices, ask structured questions for the user's, and hand a reviewable decision set to the planning step. Use to preplan, pre-plan a ticket, lock decisions, or list its open design questions."
license: "CC0-1.0"
user-invocable: true
depends_on: ["synthesis-code-audit"]
metadata:
  author: "Emil Peñalo"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Preplan — Architecture-Decision Locker

Resolves architectural choices on tickets or issues, records their owners and evidence, and hands a decision set to the planning step. Use Q&A for choices the user owns; decide technical choices inside delegated work.

## Binding rules

Rules 1 to 8 are the 1.1.0 rules, in their order.

1. **Don't skip the source-of-truth fetch.** Ticket comments, parent branches, and project docs frequently contain the decisions you'd otherwise re-litigate. Read them.
2. **Don't author the plan inside this skill.** The skill's job is locked decisions + the handoff prompt; the planner authors the commit breakdown. Persisting the planner's returned plan to a file in Step 6 is not authoring — do that.
3. **Two durable artifacts: the decision summary file and the plan document.** Both survive context compaction; the conversation log and the planner's output do not. Step 5 writes the decisions; Step 6 writes the plan to `plans/<ticket-slug>-plan.md` after the planner returns (many planners cannot write files themselves, so the orchestrator must).
4. **Carry the execution contract in the handoff.** Show the prompt; wait only at the review points the controlling instruction requires. A planner must inherit delegation as well as any explicit supervised pauses.
5. **Lean don't dictate.** Every open question has a recommendation; every recommendation can be redirected with one word.
6. **Reverse leans freely when pushed back on with a real argument.** Depth mode often exposes flaws in the initial framing. Reconsider honestly rather than defending the original lean.
7. **The commit-by-commit workflow lives at [references/commit-by-commit.md](references/commit-by-commit.md).** The handoff template references it; don't duplicate the rules inside the handoff.
8. **State the execution lane before touching a file.** The single-commit lane at [references/single-commit.md](references/single-commit.md) owns the routing test. Naming the lane and its reason is Step 2's job; inheriting one silently is what that artifact exists to prevent.
9. **Check each decision before locking it:** against what downstream tickets consume, for what its mechanism makes unobservable, and whether the outcome it prevents is a defect at all. A criterion satisfied by fiat is not met.

## Contents

- [references/workflow.md](references/workflow.md): Steps 1 to 6 in full (grounding, assessment, preliminary plan, the Q&A loop, the decision summary file, the handoff), the Q&A rubric with its three checks, and skip-Q&A behavior. Read it at the start of every preplan and follow it step by step.
- [references/plan-document-format.md](references/plan-document-format.md): the required plan shape and the rules for its gates (by reference, negative branches, test sufficiency, branch-wide reconciliation, provisional numbers). Read it in Step 6 before persisting the plan, and when reviewing a plan's gates.
- [references/commit-by-commit.md](references/commit-by-commit.md): the multi-commit execution workflow the planner and executor follow. Read it when the lane is commit-by-commit; its path fills `{WORKFLOW_DOC_PATH}`.
- [references/single-commit.md](references/single-commit.md): the routing test and the single-commit lane. Read it in Step 2 to choose the lane.
- [assets/handoff-template.md](assets/handoff-template.md): the planner prompt filled in Step 6.
- [references/background.md](references/background.md): why decisions come first and where this skill sits beside code-planning and preflight. Read it when choosing between them.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.1.0 text now lives.
- Decision ownership and execution mode, When to use, When not to use, Soft-fail behaviors, Acknowledgments: below.

## Decision ownership and execution mode

Apply the shared [decision ownership contract](../synthesis-thinking-framework/references/decision-ownership.md) before asking or locking a choice. Record `supervised` or `delegated`, its controlling instruction, delegated scope and remaining approval gates. User and project instructions take precedence over this workflow's defaults. Existing grants remain usable within their scope; preferences and packet records do not create authority.

For an explicitly supervised preplanning session, pause at the assessment, decision summary and handoff review points below. For delegated work, publish those artifacts as checkpoints and continue through technical choices without another approval. An explicit user-requested pause remains binding in either mode. Keep the same verification and independent audit obligations.

## When to use

Heuristic: a competent engineer could reasonably implement this ticket in three or more valid ways AND the choice has long-term consequences. Apply for:

- Backend infrastructure / substrate tickets (the ones with "Open questions for implementer" sections)
- Cross-cutting changes (schema + code + ops surface all touched)
- Tickets with real architectural alternatives, not just "implement X"
- Privacy / security-sensitive tickets where defaults matter
- Tickets stacked on in-flight work where the parent's choices constrain the child

## When not to use

Skip for:
- Simple bug fixes (plan directly, or no plan at all)
- UI tweaks, copy changes, dependency bumps
- Tickets with one obvious implementation path
- Things already designed in the current conversation that just need to be executed

If the task is ambiguous, inspect its constraints and existing design first; ask only when missing information materially changes the requested outcome.

## Soft-fail behaviors

- **Tracker unavailable** → warn, ask user to paste ticket body + comments inline, proceed.
- **No predecessor branch information** → warn, proceed with what's available.
- **Project lenses unspecified** → apply none unless the user states them explicitly.
- **No agent-instruction file** → no project-specific rules applied; use only general conventions.

In every soft-fail case, name what's missing in one sentence so the user knows to fill the gap. Don't silently drop quality.

## Acknowledgments

This skill was proposed by [Emil Peñalo](https://github.com/EPenaloColon)
([issue #4](https://github.com/synthesisengineering/synthesis-skills/issues/4)),
whose proposal shaped the decision-locking loop it runs.
