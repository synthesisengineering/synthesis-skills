---
name: synthesis-implementation-integrity
description: "Verify an implementation is genuinely complete before calling it done: trace data chains, find placeholders, audit test honesty, check environment parity and boundaries. Use to verify implementation, check completeness, answer is this done, or run an integrity, self-review, pre-PR or ship check."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Implementation Integrity

Verify that the implementation satisfies the user's outcome through its actual
consumers. Tests establish only the behavior they exercise; inspect the changed
data paths, deployment assumptions and required boundaries that those tests do
not cover. Find and repair concrete gaps, then make an acceptance decision.

## Binding rules

1. **Verify the outcome through its actual consumers.** Tests establish only the behavior they exercise; inspect the changed data paths, deployment assumptions and boundaries they do not cover.
2. **Follow [verification custody](references/verification-custody.md):** an isolated copy by default; shared-checkout checks restore only their own authenticated changes, preserving concurrent edits.
3. **Missing required evidence is unresolved, never N/A.** Record a genuinely inapplicable pass with its reason; explicit repository and user gates still run.
4. **A skip is not a pass.** Read what was skipped; when a security, data-integrity or irreversibility claim rests on it, run the skipped test.
5. **Trace every new data element through every layer,** and verify the Nth implementation in a series with first-item diligence.
6. **A bare `TODO` or "for now" does not ship.** If it is not acceptable as permanent code, it is not acceptable to ship; an intentional scope boundary is documented.
7. **Verification has an endpoint.** When the required evidence is complete, return the verdict and advance; reopen accepted work only for a specific unresolved criterion or counterexample.
8. **For autopilot task contracts, use the [software](references/autopilot-software-quality.md) and [data/document](references/autopilot-data-quality.md) methods.** A disconnected or fixed-answer check is a substantive defect.
9. **Releases need executable acceptance (PR CI on the exact head), extracted values and boundary authority,** as the three sections below set out. A verifier is evidence; it never grants approval.

## Contents

- [references/scope-and-report.md](references/scope-and-report.md): when to invoke, the scope and stopping rule, verification custody and autopilot methods, and the integrity report template with severities. Read it at the start of every verification and when recording the verdict.
- [references/passes.md](references/passes.md): the seven integrity passes and the five-minute quick check. Read the passes that fit the change; use the quick check for small ones.
- [references/domain-checks.md](references/domain-checks.md): checklists for database/ORM, API, frontend/UI, configuration and deployment. Read the one the change touches.
- [references/verification-custody.md](references/verification-custody.md): verifying in a shared workspace. Read it before any verification.
- [references/autopilot-software-quality.md](references/autopilot-software-quality.md) and [references/autopilot-data-quality.md](references/autopilot-data-quality.md): outcome review methods for autopilot task contracts.
- [references/background.md](references/background.md): the verification chain, anti-patterns, and related skills. Read it when choosing between this skill and preflight, code-audit, pr-review or codebase-review.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.4.1 text and each script change now lives.
- [references/preserved.md](references/preserved.md): the acceptance-manifest and receipt text v5 replaced, verbatim. Read only to review the change.
- Executable Acceptance, Extract, Do Not Restate, Authority Lives at the Boundary: below.

## Executable Acceptance

For a non-trivial change, prose that says which tests passed is an
author-written claim ledger, not executable acceptance evidence. Acceptance is
the tests that pull-request CI runs on the exact head commit: in v5, PR CI is
the only release gate, and nothing merges or releases until it passes.

Every changed production surface names at least one test that exercises it
through its real entry point, and every test the change adds maps back to a
changed surface. The pull request's diff against its base, not the author's
list, is the universe of changed surfaces; the author does not get to declare
their own completeness. The PR description names the production entry point,
the enforcing boundary, any state-changing consumer, and the unverified
remainder: what the tests do not exercise. For a defect-pinning change,
preserve evidence that the fixture commit predates the green implementation
(commit the failing test first, or keep its failing run); a test added after
the code cannot prove that it would have caught the original gap.

Read every test to a terminal state and distinguish pass, expected failure,
unexpected failure, error, skipped and not run; a skip is not a pass. Green CI
makes the measured universe explicit; it does not prove behavior outside that
universe or turn the author into an independent reviewer.

## Extract, Do Not Restate

When a verifier needs a value already owned by another artifact, extract it
from the authoritative source at verification time. A second hand-maintained
copy is another source of truth, not corroboration. Two checks that restate the
same author's interpretation preserve the same shared author blind spot and
can agree while the real source disagrees.

If the authoritative source cannot be parsed or reached, report the dimension
as unverifiable. Do not substitute a remembered value, a prose summary, or a
parallel parser whose input was copied from the same claim.

## Authority Lives at the Boundary

A standalone verifier is evidence, not enforcement. Enforcement exists only
when the state-changing operation itself refuses without the required evidence:
in v5, a merge refuses without passing PR CI, the send and deploy guards refuse
without the principal's single-use approval code for that exact action, and the
commit check refuses credentials and unapproved disclosures. Record which
boundary enforces each claim, so an acceptance-test result cannot masquerade as
an authority grant. A process exit status, a green badge someone else reports,
or a pasted log is not the boundary's own check.

A verifier can establish membership, execution, polarity, and coverage for its
declared universe. It does not manufacture approval, disclosure authority, or
permission for the state change it precedes; those remain with their owning
boundary and principal.
