# Implementation integrity: background

Where this skill sits in the verification chain, the anti-patterns it prevents, and its relationship to other skills, as written in 1.4.1.

Contents:
- Where This Fits — Verification Chain
- Anti-Patterns This Protocol Prevents
- Relationship to Other Skills

## Where This Fits — Verification Chain

Five complementary skills cover verification at different scopes and lifecycle phases:

| Skill | Scope | Cadence | Core question |
|-------|-------|---------|---------------|
| **synthesis-implementation-integrity** (this one) | A single change | After every non-trivial implementation | "Is this change genuinely complete?" |
| **synthesis-code-audit** | A diff (changed code) | After implementation, before or during review | "Does this diff meet quality standards?" |
| **synthesis-preflight** | A branch | Before creating a PR | "Is this branch ready to merge?" |
| **synthesis-pr-review** | A change proposed for merge | Every pull request | "Should this change enter the codebase?" |
| **synthesis-codebase-review** | The entire system | Periodic or at milestones | "Is this system healthy?" |

These are complementary scopes, not five mandatory successive audits. Choose
checks from the task's risks and explicit repository requirements. One review
may satisfy several scopes when it actually covers them; consume that evidence
at the next gate. Broaden to system review when the change creates a concrete
system risk or the user requested it, not because the smaller review passed.

**The critical difference:** Codebase-review evaluates the system as-is. This skill evaluates the delta between what was and what should now be. Codebase-review might give the system a clean bill of health while this skill reveals that the specific change you just made has a missing link. They catch different classes of problems.

## Anti-Patterns This Protocol Prevents

### "Tests Pass, Ship It"
Treating a green test suite as proof of an environment or consumer it never exercised. Verify the missing required boundary, then accept adequate current evidence; do not demand new tests solely because existing tests passed unchanged.

### "I Did the First Two Right, So the Third Is Fine"
Cognitive attention degrades with repetition. The last implementation in a series inherits confidence from earlier successes without inheriting the diligence. The diminishing attention audit catches what familiarity breeds.

### "I'll Come Back to This"
TODO comments and "for now" compromises have an expected lifespan of forever. Code ships with the deferral, the deferral becomes the implementation, and nobody comes back. If it's not acceptable as permanent code, it's not acceptable to ship.

### "The Pattern Is the Same, I Just Copy It"
Copy-paste across components introduces component-specific errors — wrong table names, wrong field types, references to the previous component. The pattern may be identical, but every proper noun changes.

### "It Compiles, Therefore It Works"
Compilation checks syntax and type safety. It does not check that the right data flows to the right place, that migrations exist, that configuration is complete, or that the production environment matches the assumptions the code makes.

## Relationship to Other Skills

This skill is part of a verification chain. Together these skills cover code quality from implementation through system health:

| Skill | Scope | Who runs it | Analogy |
|-------|-------|-------------|---------|
| **implementation-integrity** (this) | Single change | The implementer, on their own work | A pilot's pre-flight checklist |
| **synthesis-code-audit** | A diff (changed code) | The implementer or reviewer | An instrument panel reading |
| **synthesis-preflight** | A branch | The implementer, before PR | A pre-departure clearance |
| **synthesis-pr-review** | Change proposed for merge | A peer reviewer | An inspector's acceptance test |
| **synthesis-codebase-review** | Entire system | An auditor or lead | An annual structural inspection |

**The handoff:** Carry the accepted evidence and unresolved findings into preflight and any required peer review. Preserve distinct independence requirements without rerunning covered checks just to fit another skill's report format. System-wide review follows an actual system-wide risk or requested milestone.

Other related skills:

| Skill | Relationship |
|-------|-------------|
| **synthesis-code-planning** | Plans the approach before implementation; this skill verifies the result after |
| **synthesis-code-integration** | Verifies the merge is safe; this skill verifies the implementation is complete before merge |
| **synthesis-review-triage** | Prioritizes which PR to review next; upstream of pr-review in the review workflow |

This skill is the bridge between "I wrote the code" and "I'd stake my reputation on it." Run it before the code leaves your hands.
