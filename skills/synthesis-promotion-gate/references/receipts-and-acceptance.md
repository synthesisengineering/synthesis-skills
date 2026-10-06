# Promotion gate: receipts and acceptance

Read when consuming or auditing a receipt, when changing the enforcing boundary or adding a representation, or when running the acceptance suite.

Contents:
- Receipt Contract and Unverified Remainder: what a receipt binds, the structured remainder, declared renderer versions
- Acceptance Discipline: the shipped suite, its generation-zero cases, the Round-15 fixture corpus and how to run it

## Receipt Contract and Unverified Remainder

A receipt binds:

- config, marker-policy, surface-manifest, and acceptance-suite hashes;
- whole-source, publishable-range, sidecar, build-command-file, and rendered-output hashes;
- renderer ids and versions, exact input-to-output routes, inspected representations,
  destination projection identity and representation digests, build result, and
  promotion-command result;
- production entry point, enforcing boundary, receipt consumer, and explicit unverified
  remainder.

The unverified remainder is structured. `engine_owned` always names limits the
repository cannot erase; `repository_declared` adds non-empty instance-specific limits.
Configuration can add to this remainder but cannot replace it with `none` or an
equivalent claim.

A static renderer version is a declared fact, not independently discovered runtime
identity. Keep it current in the same change as renderer updates. The gate cannot prove
that an unknown consumer is absent or that remote destination bytes still match after
the supplied command returns; verify those at their own boundary.

## Acceptance Discipline

The shipped `acceptance-suite.yaml` is closed, accepted by the production loader, and
executable. Its generation-zero cases
come from real promotion defects: a sensitive comment in page source, five rendered
scaffolding defects behind a successful build, inline-tag adjacency, frontmatter route
mismatch, a staged page the old selector never inspected, an undeclared output crossing
the boundary, a post-build mutation, an inert policy example, destination-parser
divergence, and acceptance-schema drift. The parse5-derived Round-15 fixture corpus
compares inline, entity, comment, attribute, code, hidden-container, and malformed-input
planes through the production projection protocol. Run it with:

```bash
python3 -m pytest skills/synthesis-promotion-gate/scripts/test_*.py -q
```

A changed enforcing boundary or new representation gets its failing fixture before the
repair. Tests that inspect prose or manifest shape remain diagnostics. Only the
fail-closed `enforce` topology is an enforced gate.
