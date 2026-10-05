# Preflight: where it fits

How preflight relates to the other verification skills, and who owns the decisions after it.

## Where This Fits

| Skill | Scope | When to use |
|-------|-------|-------------|
| **implementation-integrity** | Self-verification of a single implementation | After completing work — "Is my code genuinely complete?" |
| **code-audit** | 10-dimension quality scan of a diff | After implementation — systematic quality measurement |
| **preflight** (this one) | Branch readiness gate | Before creating a PR — "Is this branch ready?" |

**The handoff:** Implement and verify the change, reconcile branch readiness, then create the PR and complete required peer review. These scopes may share evidence; invoking another skill does not require another audit.

Preflight consumes current implementation-integrity and audit evidence. It checks that the evidence covers the exact proposed branch state and required consumers; it does not repeat an unchanged review merely to produce another report. A readiness verdict does not grant merge, release or deployment authority. Apply the shared [decision-ownership contract](../../synthesis-thinking-framework/references/decision-ownership.md) and the action owner's existing gate.
