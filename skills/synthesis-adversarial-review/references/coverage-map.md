# Coverage map: adversarial review 1.2.1 to 2.0.0

Every part of the 1.2.1 SKILL.md and where it lives now. Nothing was removed. No script, test, schema, profile or `acceptance-suite.yaml` changed.

## Why SKILL.md is shaped this way

`scripts/protocol_acceptance.py` (run by `test_protocol_contract.py` and `test_review_contract_boundaries.py`) reads SKILL.md itself. It requires ten section headings in a fixed order (Purpose through Completion Report), specific terms inside each section, the five numbered round stages (`1. **Contract.**` to `5. **Sufficiency.**`) inside Goal-Focused Round, and the one-line domain-contract routing sentence. The whole 1.2.1 protocol is about 13,000 bytes, so it cannot stay in a SKILL.md under 8,000. The Binding rules section therefore uses those same headings as `###` subheadings, each holding one or two rules distilled from that section in its own words, and the complete sections move verbatim to references/protocol.md. The diagnostic passes on the new SKILL.md, including its mutation control (removing the domain-contract path is still refused).

| 1.2.1 section | Now |
|---|---|
| Frontmatter description (398 characters) | Shortened to 294 characters, keeping "bounded", "differently shaped agents", "principal's outcome", artifact-complete rounds, production-topology handoffs, concessions, the fail-closed finding ledger, sufficiency rulings, post-publication acceptance, and the triggers adversarial, cross-agent and red-team review. The full text is quoted below |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type` | Kept: synthesis-onboarding's modular installer reads `depends_on`, and the `source.skill-contract` check in synthesis-agent-conformance reads the metadata keys |
| Title | SKILL.md (verbatim), followed by a new one-line purpose |
| "Before freezing or accepting a package, apply the mandatory [domain contracts and replay scorecard]..." | SKILL.md (verbatim, still one line, as the diagnostic requires) |
| Purpose (four paragraphs) | references/protocol.md (verbatim apart from two link paths, below); Binding rules 1 to 3 |
| Before Round One: Proportionality Contract | references/protocol.md (verbatim); Binding rule 4 |
| Roles and Blind-Spot Rotation | references/protocol.md (verbatim); Binding rule 5 |
| Adjudication and Separation of Duties, with the revisit trigger | references/protocol.md (verbatim); Binding rule 6 |
| Goal-Focused Round, stages 1 to 5 and the two closing paragraphs | references/protocol.md (verbatim); Binding rules 7 and 8. Rule 7 carries the five stages, shortened, under the same numbered bold labels |
| Sidecars, Evidence, and Handoff Topology | references/protocol.md (verbatim); Binding rule 9 |
| Finding Ledger, with the `finding_ledger.py init` command | references/protocol.md (verbatim); Binding rule 10. The init command is also repeated in SKILL.md under "Finding ledger command", so the script's exact command line is in SKILL.md |
| Bounded Control Depth | references/protocol.md (verbatim); Binding rule 11 |
| Bounded Post-Publication Acceptance, steps 1 to 5 | references/protocol.md (verbatim); Binding rule 12 |
| Agent-Principal Norms | references/protocol.md (verbatim); Binding rule 13 |
| Completion Report | references/protocol.md (verbatim); Binding rule 14 |
| references/domain-review-contract.md, profiles.json, schemas/ | Unchanged (domain-review-contract.md is 98 lines, so no contents list was needed); all are listed in Contents |

## Lines the coverage check reports, and why

Before this map existed, `v5-skill-coverage-check.py` reported two lines; this map quotes the second one whole, so it now reports one. Both are Purpose paragraphs moved into `references/protocol.md` whose links gained one `../` so they still resolve; the wording is unchanged:

- `For [typed domain review](../synthesis-autopilot/references/domain-quality.md), freeze the accepted requirement...` now links `../../synthesis-autopilot/references/domain-quality.md`. Binding rule 3 in SKILL.md keeps the original link.
- `Apply the shared [decision ownership contract](../synthesis-thinking-framework/references/decision-ownership.md).` now links `../../synthesis-thinking-framework/references/decision-ownership.md`. Binding rule 2 in SKILL.md keeps the original link.

## The 1.2.1 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-adversarial-review
description: "Run bounded, differently-shaped-agent adversarial review against the principal's outcome, with artifact-complete rounds, production-topology handoffs, explicit concessions, a fail-closed finding ledger, sufficiency rulings, and independent post-publication acceptance. Use for adversarial review, cross-agent review, red-team collaboration, review rounds, finding-ledger work, or reviewer handoffs."
license: "Apache-2.0"
depends_on: ["synthesis-grounding-discipline", "synthesis-anti-shortcuts", "synthesis-project-management"]
metadata:
  author: "Rajiv Pant"
  version: "1.2.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
