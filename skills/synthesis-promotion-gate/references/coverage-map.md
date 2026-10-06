# Coverage map: promotion gate 1.0.0 to 2.0.0

Every part of the 1.0.0 SKILL.md and where it lives now. Nothing was removed, and no line needed rewording, so the coverage check finds every old line verbatim.

| 1.0.0 section | Now |
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
