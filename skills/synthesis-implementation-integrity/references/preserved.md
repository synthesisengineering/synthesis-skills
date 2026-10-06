# Implementation integrity: preserved text

Text replaced on 2026-10-05 when `scripts/acceptance_suite.py` was retired (v5
code verdict: REPLACE, "PR CI running pytest is the only gate", v5 principle 5
and R7.3). The rules that outlive the tool, a closed and defect-pinned
acceptance universe, red before green, terminal states, and enforcement only
at the state-changing boundary, are in the rewritten SKILL.md sections. The
1.4.1 text below is verbatim.

Why the manifest existed: releases were gated on a "closed acceptance
manifest" of pytest cases run in batches, whose receipt the release command
consumed (lesson 2026-09-19, fleet night run: "acceptance manifests are
per-PR"). In v5 the pull request's own CI run on the exact head is that
evidence, and the merge is the boundary that consumes it.

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
