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
9. **Releases need executable acceptance, extracted values and boundary authority,** as the three sections below set out. A verifier is evidence; it never grants approval.

## Contents

- [references/scope-and-report.md](references/scope-and-report.md): when to invoke, the scope and stopping rule, verification custody and autopilot methods, and the integrity report template with severities. Read it at the start of every verification and when recording the verdict.
- [references/passes.md](references/passes.md): the seven integrity passes and the five-minute quick check. Read the passes that fit the change; use the quick check for small ones.
- [references/domain-checks.md](references/domain-checks.md): checklists for database/ORM, API, frontend/UI, configuration and deployment. Read the one the change touches.
- [references/verification-custody.md](references/verification-custody.md): verifying in a shared workspace. Read it before any verification.
- [references/autopilot-software-quality.md](references/autopilot-software-quality.md) and [references/autopilot-data-quality.md](references/autopilot-data-quality.md): outcome review methods for autopilot task contracts.
- [references/background.md](references/background.md): the verification chain, anti-patterns, and related skills. Read it when choosing between this skill and preflight, code-audit, pr-review or codebase-review.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.4.1 text now lives.
- Executable Acceptance Manifests, Extract, Do Not Restate, Authority Lives at the Boundary: below.

## Executable Acceptance Manifests

For a non-trivial release, prose that says which tests passed is an
author-written claim ledger, not executable acceptance evidence. Declare the
acceptance universe in a machine-consumed manifest and execute it with
`acceptance_suite.py run` at the release boundary.

The manifest must declare `membership: closed`, a `production_entry_point`, an
`enforcing_boundary`, any state-changing `receipt_consumer`, the
`expected_status` for each case, and an explicit `unverified_remainder`. Every
case names the defect that motivated it and a runnable fixture. Every changed
production surface names at least one case, and every declared case maps back
to a changed surface. The enforcing boundary supplies the change base and
derives the actual base-to-head file universe from Git; schema-2 acceptance
requires exact equality between that authoritative universe and
`changed_surfaces`. The manifest does not get to declare its own completeness.
For a defect-pinning change, preserve evidence that the fixture commit predates
the green implementation; a test added after the code cannot prove that it
would have caught the original gap.

Run every declared case to a terminal state and distinguish pass, expected
failure, unexpected failure, execution error, and not-run coverage. A closed
manifest makes the measured universe explicit; it does not prove behavior
outside that universe or turn the author into an independent reviewer.

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
when the state-changing consumer refuses the operation without a fresh,
matching, transaction-bound receipt from the declared verifier. Record the
receipt consumer, the enforcing operation, and the metadata class so an
acceptance-test result cannot masquerade as an authority grant.

The consumer generates a one-use transaction identifier, supplies the
authoritative Git base, and recomputes the head commit, tree, manifest digest,
changed-path set, and changed-path digest after execution. It proceeds only
when the parsed result binds every one of those fields, all declared cases are
terminal and matched, and the worktree remains clean. Process exit status by
itself is not receipt consumption.

A verifier can establish membership, execution, polarity, and coverage for its
declared universe. It does not manufacture approval, disclosure authority, or
permission for the state change it precedes; those remain with their owning
boundary and principal.
