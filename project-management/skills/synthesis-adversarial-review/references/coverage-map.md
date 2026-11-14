# Coverage map: adversarial review 1.2.1 to 2.0.0

Every part of the 1.2.1 SKILL.md and where it lives now. Nothing was removed at the 2.0.0 prose move, when no script, test, schema, profile or `acceptance-suite.yaml` changed; the v5 script change that followed is in its own section below.

## Why SKILL.md was shaped this way at 2.0.0

At the 2.0.0 prose move, `scripts/protocol_acceptance.py` (run by `test_protocol_contract.py` and `test_review_contract_boundaries.py`) read SKILL.md itself. It required ten section headings in a fixed order (Purpose through Completion Report), specific terms inside each section, the five numbered round stages (`1. **Contract.**` to `5. **Sufficiency.**`) inside Goal-Focused Round, and the one-line domain-contract routing sentence. The whole 1.2.1 protocol is about 13,000 bytes, so it cannot stay in a SKILL.md under 8,000. The Binding rules section therefore used those same headings as `###` subheadings, each holding one or two rules distilled from that section in its own words, and the complete sections moved verbatim to references/protocol.md. The v5 script change below retired that diagnostic, so the subheadings went too; the rules keep their numbers and order, and the table below still says where each section lives.

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
| Finding Ledger, with the `finding_ledger.py init` command | At 2.0.0: references/protocol.md (verbatim); Binding rule 10; the init command repeated in SKILL.md under "Finding ledger command". Since the v5 script change: the markdown findings table in references/protocol.md and SKILL.md "Findings file"; the 1.2.1 section is verbatim in [preserved.md](preserved.md) |
| Bounded Control Depth | references/protocol.md (verbatim); Binding rule 11 |
| Bounded Post-Publication Acceptance, steps 1 to 5 | references/protocol.md (verbatim); Binding rule 12 |
| Agent-Principal Norms | references/protocol.md (verbatim); Binding rule 13 |
| Completion Report | references/protocol.md (verbatim); Binding rule 14 |
| references/domain-review-contract.md, profiles.json, schemas/ | Unchanged at 2.0.0. Since the v5 script change: domain-review-contract.md rewritten around manual checks (old file verbatim in [preserved.md](preserved.md)); profiles.json and schemas/ folded into its tables |

## v5 script changes (2026-10-05)

Verdicts from the v5 code evaluation (`tool-scripts.md`, synthesis-adversarial-review rows), all CUT. Every rule the scripts enforced is kept as prose; [preserved.md](preserved.md) holds the replaced text verbatim.

| Removed | Why | Where its rules live now |
|---|---|---|
| `scripts/finding_ledger.py`, `scripts/test_finding_ledger.py` | Served the old review-and-release loop; v5 rules out ledgers; a markdown findings table does the job | references/protocol.md, "Finding Ledger": the findings-file template, the same states, classifications, authority labels, separate enforcement outcome, follow-up project and append-only transitions; compare-before-write becomes "re-read the row and confirm its prior state", and the resources-directory lock becomes a `synthesis claim` on the file. Binding rule 10 and SKILL.md's "Findings file" |
| `scripts/protocol_acceptance.py`, `scripts/test_protocol_contract.py` | v5's skill-format checker covers skill structure | `tests/test_review_protocol.py` checks the protocol's own terms in references/protocol.md and the router and autopilot facts below. SKILL.md's binding rules lost their `###` subheadings, which existed only for this diagnostic |
| `scripts/review_contract.py`, `scripts/test_review_contract.py`, `scripts/test_review_contract_boundaries.py`, `scripts/test_b11_inventory_boundaries.py`, `scripts/test_review_lessons.py` | No content-work use; served the autopilot review machinery | references/domain-review-contract.md, "Checks the reviewer applies": one rule per former control (instruments, content, calibration, custody, lifecycle, corpus, publication, independence, links, saved outputs), each tagged with the replay shape (F01 to F10 in `test_review_lessons.py`) it answers |
| `references/profiles.json`, `references/schemas/*.schema.json` | Data for `review_contract.py` | The profile table and the records table in references/domain-review-contract.md |
| `acceptance-suite.yaml` | Release acceptance machinery; PR CI is the only gate in v5 | — |

The 2.0.0 tests that read the old autopilot SKILL.md:

- `test_autopilot_tracks_direct_dispatch_and_courier_cost` pinned three facts through `protocol_acceptance.autopilot_errors`: autopilot declares `synthesis-adversarial-review` in `depends_on`; its verify step calls for one complete adversarial review per declared package and fixes substantiated findings; its decisions section links the decision-ownership contract and routes sessions by their existing authenticated addressing. In the rebuilt autopilot (commit 5f535c4) the dependency is still in its SKILL.md frontmatter, the review call and the decision-ownership link are in `references/execution-doctrine.md`, and session-to-session dispatch with courier counting is in `references/delegation.md` (`synthesis msg`, which refuses an address naming none or several sessions). `tests/test_review_protocol.py::test_autopilot_routes_review_to_this_skill` reads those files.
- `test_protocol_acceptance_rejects_token_soup` ran `protocol_acceptance.py` against the autopilot SKILL.md. Removed with the script: it tested the diagnostic, not a fact in either skill.
- `test_acceptance_manifest_classifies_control_authority` read `acceptance-suite.yaml`. Removed with the manifest; the rule it pinned (section-shape checks are diagnostics; only a fail-closed caller is an enforced gate) is in references/protocol.md, "Finding Ledger", and `tests/test_review_protocol.py` checks it there.

Prose changed with the scripts: SKILL.md (description, the opening sentence, rule 10, Contents, "Findings file"), references/protocol.md ("Finding Ledger" and its contents line) and references/domain-review-contract.md (rewritten around manual checks). Python lines: 1,560 before (plus 1,220 of tests), none after.

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
