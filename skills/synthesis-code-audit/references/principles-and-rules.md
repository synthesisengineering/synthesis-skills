# Code audit: where it fits, principles and rules

The skill's place among the three code-evaluation skills, then the full text of its principles and rules. Binding rules in SKILL.md summarize both lists.

## Where This Fits

Three engineering skills evaluate code at different scopes:

| Skill | Scope | When to use |
|-------|-------|-------------|
| **code-audit** (this one) | Quality scan of a diff | After implementation, standalone or as input to preflight/pr-review |
| **pr-review** | Judgment-based delta review | Every PR, before peer approval or lead integration |
| **codebase-review** | Full system audit (16 categories, tiered) | Periodic health check or major milestone |

Code-audit produces findings. PR-review produces a verdict that may consume those findings. Codebase-review catches systemic patterns that no single diff reveals.

## Principles

1. **Fresh base branch.** Compare against an up-to-date base ref. Stale base branches cause false positives (flagging code already addressed upstream) and false negatives (missing new context on the base that changes interpretation).

2. **Read files in full, not just diff hunks.** A diff hunk shows what changed. The surrounding file shows whether the change makes sense in context. Always read changed files in their entirety.

3. **Independent judgment with complete requirements.** Give the reviewer the frozen artifact universe, user outcome, acceptance criteria, exclusions and applicable decisions. Avoid priming the verdict with the producer's preferred explanation. Independence means rederiving the result against the actual requirements, not hiding the requirements. Challenge a mistaken premise with evidence and route any amendment to its decision owner.

4. **State the reviewed scope and consequences.** Grade the changed behavior and its affected consumers. A defect that prevents the promised outcome remains a blocker even when its lines predate the diff. Record unrelated findings separately without claiming that unreviewed code is clean. Apply stronger project rules, including fix-while-touching requirements, where present.

## Rules

- Always compare against a fresh base ref — never compare against a stale local ref
- Read changed files in full, not just diff hunks — context matters
- Check project convention documentation and apply project-specific rules explicitly
- Do not flag style nits in code that was not changed by this diff
- Retain outcome-blocking defects regardless of introduction date; distinguish unrelated findings and honor stronger project maintenance rules
- Bind reused findings to the actual diff, required consumer and evidence inputs. Changed material reopens the affected judgment; a new report is unnecessary when those bindings remain current.
- If the audit is invoked by another workflow (preflight, PR review), return findings to that workflow for decision-making
