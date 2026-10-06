# Promotion gate: configuring the contract

Read when writing or changing `.agents/promotion-gate.yaml`, the marker policy, the surface manifest, the acceptance suite or the destination-projection adapter.

Contents:
- Configure the Contract: the four templates, path and build-command rules, `destination_projection`, publishable-range markers, sidecar globs
- Declared Representations: the six representations and what `dom-text` excludes
- Canonical Marker Policy: one identity per marker, behavioral examples, bounded vocabulary
- Route and Surface Completeness: frontmatter-derived routes and the closed output universe

## Configure the Contract

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

## Declared Representations

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

## Canonical Marker Policy

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

## Route and Surface Completeness

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
