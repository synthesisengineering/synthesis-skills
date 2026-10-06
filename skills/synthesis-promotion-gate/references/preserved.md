# Promotion gate: preserved text

Contents:
- Why this text was retired
- SKILL.md 2.0.0 before the script change (whole body)
- references/configuration.md 2.0.0 (whole file)
- references/receipts-and-acceptance.md 2.0.0 (whole file)

## Why this text was retired

The v5 code evaluation (`tool-scripts.md`, row `synthesis-promotion-gate/scripts/promotion_gate.py`)
ruled SLIM: "About 100 lines: scan the built `dist/` for configured markers, called by
`build.sh` before the R3.2-approved deploy." The 1,406-line engine had been built during
the book-review publication rounds (4.51.0, 2026-08-26) and was never wired into any
site's `build.sh`. What it did beyond the scan (an isolated build, frontmatter-derived
routes and a closed output universe, a destination-parser adapter, publishable-range and
sidecar inputs, hash-bound receipts, a `check`/`enforce` split and an acceptance manifest)
served a promotion command no site used. The scan's lessons stay in the new SKILL.md and
references/configuration.md: the build is not a safety signal, the gate is evidence and not
permission, refuse rather than warn, name the view judged, one identity per marker with
behavioral examples, the destination's own parser as the arbiter of what a reader sees,
and an unverified remainder that is never "none". Everything below is verbatim.

## SKILL.md 2.0.0 (body)

### Synthesis Promotion Gate

Inspects outgoing publication artifacts, in the representations the destination exposes, before a promotion command may change publication state.

### Binding rules

1. **A successful build is not a publication-safety signal.** Promotion needs a second judgment over the outgoing artifacts.
2. **The gate is evidence, not permission.** Publication and deployment approval gates stay in force; a clean receipt covers only what it records.
3. **Only `enforce` may change publication state.** `check` issues an `acceptance-test` receipt; only a clean `enforce` whose command returns zero issues an `enforced-gate` receipt.
4. **Refuse, never warn:** a dirty artifact, missing route, changed input or policy, failed build or failed promotion command refuses the transition.
5. **The destination parser judges.** `destination_projection` calls the repository's own parser or renderer and matches `expected_identity` exactly; a hand parser is a contract violation.
6. **Name the representation actually judged:** `publishable-source`, `dom-text`, `dom-heading-text`, `html-comments`, `raw-page-source` or `sidecar-flags`. `dom-text` is not all browser-visible text.
7. **Routes come from frontmatter** and the renderer's route template. Directory-name substring selection is forbidden, and the output universe is closed.
8. **One canonical identity per marker;** every projection must match a positive example and reject every negative one.
9. **The unverified remainder is never `none`.** Configuration may add to it, never replace it.
10. **A failing fixture comes before the repair** for a changed enforcing boundary or a new representation.

### Contents

- [references/configuration.md](references/configuration.md): the four templates, paths, build and projection commands, range markers, sidecars, the six representations, marker policy and route completeness. Read it when writing or changing the contract or an adapter.
- [references/receipts-and-acceptance.md](references/receipts-and-acceptance.md): what a receipt binds, the structured unverified remainder, and the acceptance suite and fixture corpus. Read it when consuming a receipt or changing the engine.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.0.0 text now lives (ruling D8).
- Doctrine, Two Commands, Tests: below.

### Doctrine

A successful build is not a publication-safety signal. A build establishes that a
renderer accepted its inputs. Promotion requires a second judgment over the outgoing
artifacts, in the representations the destination exposes.

This skill supplies that boundary for configured promotion scaffolding. It does not
decide whether ordinary prose is appropriate to disclose, prove that an undeclared
consumer does not exist, or grant publication or deployment permission. Those approval
gates remain in force. A clean receipt is evidence only for the exact policy, inputs,
renderers, routes, representations, and command recorded in it.

### Two Commands, Two Authority Classes

`check` builds and inspects but cannot change publication state:

```bash
python3 skills/synthesis-promotion-gate/scripts/promotion_gate.py check \
  --config .agents/promotion-gate.yaml \
  --receipt .agents/receipts/promotion-check.json
```

Its receipt is an `acceptance-test`, with `authority_receipt: false`.

`enforce` is the production entry point. It builds into an isolated temporary root,
captures each expected output exactly once, inspects those captured bytes, closes the
output universe, materializes a separate content snapshot, writes a candidate receipt,
and re-hashes the contract and snapshot immediately before the boundary. It then
invokes the supplied promotion command. The command must carry both
`{candidate_receipt}` and `{output_root}` as literal arguments; the gate substitutes
the exact receipt and captured-snapshot paths.

```bash
python3 skills/synthesis-promotion-gate/scripts/promotion_gate.py enforce \
  --config .agents/promotion-gate.yaml \
  --receipt .agents/receipts/promotion-enforced.json \
  -- python3 tools/promote.py {candidate_receipt} {output_root}
```

Only a clean `enforce` run whose supplied command returns zero issues an
`enforced-gate` receipt with `authority_receipt: true`. A dirty artifact, missing route,
changed input, changed policy, failed build, or failed promotion command refuses the
transition. The receipt withholds matched content and records a digest instead.

### Tests

`python3 -m pytest skills/synthesis-promotion-gate/scripts/test_*.py -q` runs the shipped acceptance suite and fixture corpus (details in references/receipts-and-acceptance.md). Tests that inspect prose or manifest shape are diagnostics; only the fail-closed `enforce` topology is an enforced gate.

## references/configuration.md 2.0.0

### Promotion gate: configuring the contract

Read when writing or changing `.agents/promotion-gate.yaml`, the marker policy, the surface manifest, the acceptance suite or the destination-projection adapter.

Contents:
- Configure the Contract: the four templates, path and build-command rules, `destination_projection`, publishable-range markers, sidecar globs
- Declared Representations: the six representations and what `dom-text` excludes
- Canonical Marker Policy: one identity per marker, behavioral examples, bounded vocabulary
- Route and Surface Completeness: frontmatter-derived routes and the closed output universe

### Configure the Contract

Start from the four files under `templates/`:

- `promotion-gate.example.yaml` becomes `.agents/promotion-gate.yaml`.
- `marker-policy.example.yaml` is the one canonical marker identity and projection file.
- `surface-manifest.example.yaml` enumerates every consuming renderer and its version.
- `acceptance-suite.example.yaml` declares the closed, production-consumable cases for
  the repository instance.

The gate refuses unknown configuration keys. Paths are project-relative, cannot escape
the project, and cannot traverse symlink components. The build command is an argument
list, never a shell string, and must receive `{output_root}` so the inspected build is
isolated from a repository's ordinary output directory.

`destination_projection` is a second argument-list command. It receives one JSON batch on
standard input containing the exact captured HTML for every route and returns the strict
schema-1 representation batch. It must call the repository's destination parser or
renderer; substituting a hand parser is a contract violation. Its reported parser,
parser-version, and renderer identity must exactly match `expected_identity`. The gate
binds the adapter command-file hashes, executes it once over the closed route universe,
and refuses missing, duplicate, additional, malformed, or identity-mismatched projection
rows. **AGENT HEURISTIC:** this strict adapter protocol is the generic public seam chosen
for D2; the repository-owned adapter is the per-repository instance.

Every input must contain exactly one configured publishable-range start marker and one
end marker. The receipt binds both the whole-source hash and the extracted-range hash.
Draft material may exist outside that range; it earns no path into a rendered output.

Sidecar globs close a second input channel. A marker projected to `sidecar-flags` refuses
promotion when an attestation, review record, or other declared sidecar remains
unresolved even if the page itself is clean.

### Declared Representations

Name the representation actually judged. The engine supports:

- `publishable-source`: the exact source bytes between the range markers;
- `dom-text`: the destination projector's displayed-prose text regions, with inline
  adjacency preserved and no matching invented across structural regions;
- `dom-heading-text`: each destination-projected heading's text with inline adjacency
  preserved;
- `html-comments`: comment nodes, separate from displayed text;
- `raw-page-source`: the generated HTML bytes decoded as UTF-8;
- `sidecar-flags`: the complete text of each file matched by a configured sidecar glob.

Do not label `dom-text` as all browser-visible or accessible text. The projector's declared
representation excludes accessible attributes, code, non-displayed containers, CSS
layout, accessibility-tree computation, and client-side mutation unless a repository
explicitly extends the protocol and acceptance corpus for those channels. The engine does
not carry a fallback HTML parser: if the destination projection is unavailable or its
identity differs, the run refuses.
When a destination needs another semantic channel—accessible attributes, feed fields,
search documents, or a renderer-specific DOM—extend the engine and add a motivating
fixture before adding that representation to a live configuration.

### Canonical Marker Policy

Each marker identity appears once with a threat rationale, provenance, positive and
negative examples, and representation-specific regex projections. Surface predicates
may differ; identity and rationale may not be copied into separate lists. This allows a
heading-only projection to reject an internal section while ordinary prose containing
the same words remains valid.

The loader executes the canonical examples against every projection: each projection
must match at least one positive example and must reject every negative example. A
schema-valid but behaviorally empty projection is an invalid policy.

The policy is a bounded vocabulary, not a semantic disclosure model. Keep patterns tied
to observed pipeline scaffolding. If a proposed pattern matches ordinary language,
repair its structural projection or remove it; approval fatigue is not safety.

### Route and Surface Completeness

The surface manifest is the canonical declared renderer set. For each input consumed by
each renderer, the gate computes the output route from frontmatter and the renderer's
route template. Directory-name substring selection is forbidden. Duplicate routes,
inputs consumed by no renderer, and expected outputs absent after the build are
refusals. Expected output paths cannot traverse symlinks; the gate never inspects bytes
outside its isolated build root. Every renderer in the manifest must have one matching
`inspected_surfaces`
entry; neither side may silently contain an extra renderer.

The build output universe is closed: it must equal the frontmatter-derived route set.
An additional file is `unscoped-rendered-output` and refuses the run before the output
root can reach a promotion command. If another page belongs in the transaction, add
its input, renderer, and route to the declared contract.

## references/receipts-and-acceptance.md 2.0.0

### Promotion gate: receipts and acceptance

Read when consuming or auditing a receipt, when changing the enforcing boundary or adding a representation, or when running the acceptance suite.

Contents:
- Receipt Contract and Unverified Remainder: what a receipt binds, the structured remainder, declared renderer versions
- Acceptance Discipline: the shipped suite, its generation-zero cases, the Round-15 fixture corpus and how to run it

### Receipt Contract and Unverified Remainder

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

### Acceptance Discipline

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
