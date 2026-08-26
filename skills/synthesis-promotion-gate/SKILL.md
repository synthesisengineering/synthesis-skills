---
name: synthesis-promotion-gate
description: "Configure and run a fail-closed publication promotion gate that builds in isolation, derives output routes from frontmatter, inspects declared destination representations, binds receipts to exact inputs and renderer surfaces, and permits a state-changing promotion command only after immediate revalidation. Use for publication gates, outward-surface cleanliness, rendered-output inspection, publishable-range contracts, or promotion receipts."
license: "Apache-2.0"
depends_on: ["synthesis-grounding-discipline", "synthesis-implementation-integrity"]
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Promotion Gate

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
inspects every frontmatter-derived route, writes a candidate receipt, re-hashes the
contract and artifacts immediately before the boundary, then invokes the supplied
promotion command. The command must carry both `{candidate_receipt}` and
`{output_root}` as literal arguments; the gate substitutes their exact temporary paths.

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

## Configure the Contract

Start from the three files under `templates/`:

- `promotion-gate.example.yaml` becomes `.agents/promotion-gate.yaml`.
- `marker-policy.example.yaml` is the one canonical marker identity and projection file.
- `surface-manifest.example.yaml` enumerates every consuming renderer and its version.

The gate refuses unknown configuration keys. Paths are project-relative, cannot escape
the project, and cannot traverse symlink components. The build command is an argument
list, never a shell string, and must receive `{output_root}` so the inspected build is
isolated from a repository's ordinary output directory.

Every input must contain exactly one configured publishable-range start marker and one
end marker. The receipt binds both the whole-source hash and the extracted-range hash.
Draft material may exist outside that range; it earns no path into a rendered output.

Sidecar globs close a second input channel. A marker projected to `sidecar-flags` refuses
promotion when an attestation, review record, or other declared sidecar remains
unresolved even if the page itself is clean.

## Declared Representations

Name the representation actually judged. The engine supports:

- `publishable-source`: the exact source bytes between the range markers;
- `dom-text`: non-comment DOM text nodes in document order, with inline adjacency
  preserved and no invented separators; raw-text elements are excluded explicitly;
- `dom-heading-text`: each heading's DOM text with inline adjacency preserved;
- `html-comments`: comment nodes, separate from displayed text;
- `raw-page-source`: the generated HTML bytes decoded as UTF-8;
- `sidecar-flags`: the complete text of each file matched by a configured sidecar glob.

Do not label `dom-text` as browser-visible text. This implementation uses Python's
`html.parser`, records its runtime version in the receipt, and declares its exclusions.
When a destination needs another semantic channel—accessible attributes, feed fields,
search documents, or a renderer-specific DOM—extend the engine and add a motivating
fixture before adding that representation to a live configuration.

## Canonical Marker Policy

Each marker identity appears once with a threat rationale, provenance, positive and
negative examples, and representation-specific regex projections. Surface predicates
may differ; identity and rationale may not be copied into separate lists. This allows a
heading-only projection to reject an internal section while ordinary prose containing
the same words remains valid.

The policy is a bounded vocabulary, not a semantic disclosure model. Keep patterns tied
to observed pipeline scaffolding. If a proposed pattern matches ordinary language,
repair its structural projection or remove it; approval fatigue is not safety.

## Route and Surface Completeness

The surface manifest is the canonical declared renderer set. For each input consumed by
each renderer, the gate computes the output route from frontmatter and the renderer's
route template. Directory-name substring selection is forbidden. Duplicate routes,
inputs consumed by no renderer, and expected outputs absent after the build are
refusals. Every renderer in the manifest must have one matching `inspected_surfaces`
entry; neither side may silently contain an extra renderer.

A build can contain unrelated pages. The receipt lists those as `unscoped_outputs`; it
does not claim to have inspected them. If they consume the promotion inputs, add the
renderer and routes to the surface manifest.

## Receipt Contract and Unverified Remainder

A receipt binds:

- config, marker-policy, surface-manifest, and acceptance-suite hashes;
- whole-source, publishable-range, sidecar, build-command-file, and rendered-output hashes;
- renderer ids and versions, exact input-to-output routes, inspected representations,
  parser identity, build result, and promotion-command result;
- production entry point, enforcing boundary, receipt consumer, and explicit unverified
  remainder.

A static renderer version is a declared fact, not independently discovered runtime
identity. Keep it current in the same change as renderer updates. The gate cannot prove
that an unknown consumer is absent or that remote destination bytes still match after
the supplied command returns; verify those at their own boundary.

## Acceptance Discipline

The shipped `acceptance-suite.yaml` is closed and executable. Its generation-zero cases
come from real promotion defects: a sensitive comment in page source, five rendered
scaffolding defects behind a successful build, inline-tag adjacency, frontmatter route
mismatch, and a staged page the old selector never inspected. Run it with:

```bash
python3 -m pytest skills/synthesis-promotion-gate/scripts/test_*.py -q
```

A changed enforcing boundary or new representation gets its failing fixture before the
repair. Tests that inspect prose or manifest shape remain diagnostics. Only the
fail-closed `enforce` topology is an enforced gate.
