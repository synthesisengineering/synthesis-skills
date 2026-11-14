# Scope, stopping rule and the integrity report

When to run the protocol, how far to take it, when to stop, and how to record the verdict, as written in 1.4.1.

Contents:
- Where verification ends, autopilot task contracts, verification custody
- When to Invoke
- Scope and stopping rule
- The Integrity Report: the template and the severity scale

## Where verification ends

Verification has an endpoint: every applicable required criterion is supported,
findings are resolved by their proper owner, and any required delivery read-back
is complete. Passing adequate checks is evidence to use, not a reason to invent
another round of scrutiny. Preserve failures and unknowns honestly.

For autopilot task contracts, use the owning [software](autopilot-software-quality.md) and [data/document](autopilot-data-quality.md) methods. Inspect the executed consumer's code and expectation as well as its result; a disconnected or fixed-answer check is a substantive defect. Semantic calibration cannot certify execution, and execution cannot certify that the chosen check answers the user's question.

---

Before verification, follow [verification custody](../../synthesis-implementation-integrity/references/verification-custody.md): use an isolated copy by default; shared-checkout checks must restore only their own authenticated changes, preserving concurrent edits and unresolved evidence.

## When to Invoke

Run this protocol:

- **After completing any non-trivial implementation** — before declaring it done
- **After adding a field, column, or property** that flows through multiple system layers
- **After implementing the same pattern across multiple components** — the last one gets the least attention
- **For schema, config, or deployment changes** — verify the actual migration, configuration and target-environment criteria; green unit tests alone do not establish them
- **When someone (human or AI) says "it's done"** — use this to give an evidence-based answer

Skip for trivial changes (typo fixes, comment updates, single-line config edits).

## Scope and stopping rule

Read the current change and its acceptance criteria. Select the relevant passes
below, recording genuinely inapplicable ones with a reason. Missing required
evidence is unresolved, never N/A. Explicit repository and user gates still run.

Read the implementation and the checks, including actual execution and skipped
coverage. Exercise real boundary behavior where a mock would hide the relevant
risk. Use existing tests when they already discriminate correct from defective
behavior; add tests for uncovered behavior. Compilation, fixture success and
live delivery establish different facts.

After a repair, rerun its reproducer and affected checks plus every gate the
repository requires. Preserve valid evidence for unchanged inputs and consumers.
Further investigation needs a specific unresolved criterion or counterexample.
A new reviewer or renewed feeling of uncertainty alone does not reopen accepted
work. When the required evidence is complete, return the verdict and advance to
the authorized delivery step.

## The Integrity Report

Record the verdict, applicable coverage, findings and remaining gate in the existing handoff or review record. Use the format below when useful; a second standalone report is unnecessary when that information already exists:

```
## Implementation Integrity Report

**Change:** [One-line description]
**Date:** YYYY-MM-DD

### Verdict: PASS / ISSUES FOUND / INCOMPLETE

### Passes Completed
- [x] Chain Completeness
- [x] Placeholder Detection
- [x] Test Honesty
- [x] Environment Parity
- [ ] Diminishing Attention (single implementation — not applicable)
- [x] Companion Changes
- [x] Boundary Verification

### Findings

| # | Pass | Finding | Severity | Action |
|---|------|---------|----------|--------|
| 1 | Chain | `timing_seconds` not on OutputModel | Critical | Add column to model |
| 2 | Environment | No migration for existing output table | Critical | Add idempotent ALTER TABLE |
| 3 | Test Honesty | No test asserts on timing value | Medium | Add assertion |

### Verdict Notes
[Brief explanation of verdict and any caveats]
```

**Severity:**
- **Critical** — production will break or data will be lost
- **High** — production may break under specific, realistic conditions
- **Medium** — functionality degraded but not broken
- **Low** — quality or maintainability concern, not a runtime issue
