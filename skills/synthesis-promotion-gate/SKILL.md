---
name: synthesis-promotion-gate
description: "Configure and run a fail-closed promotion gate: isolated build, frontmatter-derived routes, destination-parser representations, receipts bound to exact inputs, revalidation before promotion. Use for publication gates, rendered-output inspection, publishable-range contracts or promotion receipts."
license: "Apache-2.0"
depends_on: ["synthesis-grounding-discipline", "synthesis-implementation-integrity"]
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Promotion Gate

Inspects outgoing publication artifacts, in the representations the destination exposes, before a promotion command may change publication state.

## Binding rules

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

## Contents

- [references/configuration.md](references/configuration.md): the four templates, paths, build and projection commands, range markers, sidecars, the six representations, marker policy and route completeness. Read it when writing or changing the contract or an adapter.
- [references/receipts-and-acceptance.md](references/receipts-and-acceptance.md): what a receipt binds, the structured unverified remainder, and the acceptance suite and fixture corpus. Read it when consuming a receipt or changing the engine.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.0.0 text now lives (ruling D8).
- Doctrine, Two Commands, Tests: below.

## Doctrine

A successful build is not a publication-safety signal. A build establishes that a
renderer accepted its inputs. Promotion requires a second judgment over the outgoing
artifacts, in the representations the destination exposes.

This skill supplies that boundary for configured promotion scaffolding. It does not
decide whether ordinary prose is appropriate to disclose, prove that an undeclared
consumer does not exist, or grant publication or deployment permission. Those approval
gates remain in force. A clean receipt is evidence only for the exact policy, inputs,
renderers, routes, representations, and command recorded in it.

## Two Commands, Two Authority Classes

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

## Tests

`python3 -m pytest skills/synthesis-promotion-gate/scripts/test_*.py -q` runs the shipped acceptance suite and fixture corpus (details in references/receipts-and-acceptance.md). Tests that inspect prose or manifest shape are diagnostics; only the fail-closed `enforce` topology is an enforced gate.
