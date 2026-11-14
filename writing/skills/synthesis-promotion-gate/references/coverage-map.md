# Coverage map: promotion gate 1.0.0 to 2.0.0

Every part of the 1.0.0 SKILL.md and where it lives now. At the 2.0.0 prose move nothing was removed and no line needed rewording. The v5 script change that followed retired most of the engine; its section below says what replaced what, and [preserved.md](preserved.md) holds the whole 2.0.0 text verbatim, so the coverage check still finds every 1.0.0 line.

| 1.0.0 section | At 2.0.0 (see the v5 section below for now) |
|---|---|
| Frontmatter description | Shortened to under 300 characters; keeps the mechanism (isolated build, frontmatter-derived routes, destination-parser representations, receipts bound to exact inputs, revalidation before promotion) and the triggers publication gates, rendered-output inspection, publishable-range contracts and promotion receipts. The dropped trigger "outward-surface cleanliness" is covered by "rendered-output inspection" |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type`, `license` | Kept (the modular installer and the source checks read them); version bumped to 2.0.0; `format: v5` added |
| Title | SKILL.md (verbatim) |
| Doctrine | SKILL.md (verbatim); binding rules 1 and 2 distill it |
| Two Commands, Two Authority Classes | SKILL.md (verbatim, both commands unchanged); binding rules 3 and 4 distill it |
| Configure the Contract | references/configuration.md (verbatim); binding rule 5 distills the projection rule |
| Declared Representations | references/configuration.md (verbatim); binding rule 6 names all six |
| Canonical Marker Policy | references/configuration.md (verbatim); binding rule 8 |
| Route and Surface Completeness | references/configuration.md (verbatim); binding rule 7 |
| Receipt Contract and Unverified Remainder | references/receipts-and-acceptance.md (verbatim); binding rule 9 |
| Acceptance Discipline, with its pytest command | references/receipts-and-acceptance.md (verbatim); the command is repeated in SKILL.md "Tests"; binding rule 10 |

## Text a test reads from SKILL.md

`scripts/test_skill_contract.py` reads these from SKILL.md, so they stay there: "A successful build is not a publication-safety signal", "acceptance-test", "enforced-gate", "authority_receipt: false", "unverified remainder" (binding rule 9), "does not decide whether ordinary prose is appropriate to disclose" (Doctrine), and `dom-text`, `dom-heading-text`, `html-comments`, `raw-page-source`, "frontmatter" and "Directory-name substring selection is forbidden" (binding rules 6 and 7).

## Scripts, templates and tests

`scripts/`, `templates/`, `fixtures/`, `acceptance-suite.yaml` and `agents/openai.yaml` are unchanged.

## v5 script changes (2026-10-05)

The v5 code evaluation (`tool-scripts.md`, row `synthesis-promotion-gate/scripts/promotion_gate.py`) ruled SLIM: "About 100 lines: scan the built `dist/` for configured markers, called by `build.sh` before the R3.2-approved deploy." Scenario E96: a site build whose rendered pages carry a configured internal marker in text, an HTML comment or raw source is refused before publishing.

| 2.0.0 part | Now |
|---|---|
| `promotion_gate.py` (1,406 lines): isolated build, frontmatter routes, destination-projection adapter, publishable range, sidecars, receipts, `check` and `enforce` | `promotion_gate.py` (113 lines): `promotion_gate.py <dist> --config <json>`, scanning every built file in four views; exit 0, 1 or 2 |
| The six representations | `dom-text` became `text`, `dom-heading-text` `headings`, `html-comments` `comments`, `raw-page-source` `source`. `publishable-source` and `sidecar-flags` judged inputs, not built output; the scan judges only what ships, and draft text outside the published range never reaches `dist/` unless the build puts it there, where the scan sees it |
| `destination_projection` (call the destination's own parser) | A small HTML reader held to the 1.0 corpus that parse5 7.3.0 generated (`fixtures/destination-representations.yaml`, now the `CORPUS` table in `tests/test_promotion_gate.py`, every case kept). Binding rule 5 keeps the lesson: the destination's parser is the arbiter, and a disagreement becomes a corpus case before the fix |
| Marker policy (YAML: identity, rationale, provenance, positive and negative examples, per-representation patterns) | JSON markers with one pattern and a list of views (`templates/promotion-markers.example.json`, the same three markers as the old example minus the sidecar one); the examples still run at load. Provenance moved into the rationale line |
| Route and surface completeness (frontmatter routes, a closed output universe, the surface manifest) | Retired: the scan reads every built file that matches the globs, so an undeclared page is scanned rather than refused, and there is no route list to drift. An empty scan refuses |
| Receipts (hash-bound inputs, outputs, routes; `acceptance-test` versus `enforced-gate`; candidate revalidation; the snapshot passed to the promotion command) | Retired: the deploy is a v5 production deploy, held by the deploy guard until the principal approves that exact command (single use). Binding rule 2 |
| The structured unverified remainder | Binding rule 8 |
| `acceptance-suite.yaml`, `templates/acceptance-suite.example.yaml`, `promotion-gate.example.yaml`, `surface-manifest.example.yaml`, `marker-policy.example.yaml` | Removed; PR CI runs `tests/` |
| `scripts/test_promotion_gate.py` (896 lines), `scripts/test_skill_contract.py` | `tests/test_promotion_gate.py`: the corpus, the five round-two defects behind a successful build, the comment found as comment and source, adjacency, the inert-policy and negative-example refusals, empty and missing output, symlinks, and the router reachability check. Tests of the build isolation, routes, receipts, snapshot and adapter identity left with that machinery |

Prose: SKILL.md rewritten around the scan (description, binding rules, Contents, "Run it", "Tests"); references/configuration.md rewritten for the JSON config; references/receipts-and-acceptance.md removed. All three 2.0.0 texts are verbatim in [preserved.md](preserved.md). Python lines: 1,406 before (plus 1,009 of tests), 113 after.

## The 1.0.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-promotion-gate
description: "Configure and run a fail-closed publication promotion gate that builds in isolation, derives output routes from frontmatter, consumes identity-bound representations from the destination parser or renderer, binds receipts to exact inputs and renderer surfaces, and permits a state-changing promotion command only after immediate revalidation. Use for publication gates, outward-surface cleanliness, rendered-output inspection, publishable-range contracts, or promotion receipts."
license: "Apache-2.0"
depends_on: ["synthesis-grounding-discipline", "synthesis-implementation-integrity"]
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
