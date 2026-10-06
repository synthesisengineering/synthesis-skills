---
name: synthesis-decision-packet
description: "Collect five or more parallel decisions from a principal in one sitting: a self-contained HTML packet with a recommendation per row, consequence-labeled buttons, notes and a paste-back summary, filed in the project. Use when a review, migration, upgrade, triage or backlog pass needs rulings."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Decision Packet

When N unresolved decisions belong to the principal, collecting them one at a time
scales poorly. The measurement that produced this skill is blunt: **26 rounds of per-item
conversation produced 0 of 30 decisions. One packet produced 30 of 30, in one pass, in one
paste.**

**The property to preserve above all others: the principal's cost scales with the number of
*sittings*, not the number of *items*.**

## Binding rules

Rules 1 to 6 are the six load-bearing properties in their original order, so "the sixth load-bearing property" still resolves. Later rules come from the other sections; new rules are appended.

1. **Self-contained rows:** item, recommendation, reasoning, link. The principal never leaves the packet to decide.
2. **Mark the recommendation on the control; never pre-select it.** A packet that opens decided reports decisions nobody made.
3. **A free-text note box on every row,** beside the buttons. Never force the principal into your option set.
4. **Local persistence keyed by exact spec and item.** A change anywhere in the spec starts fresh choices.
5. **The packet generates the paste-able summary,** so the person never composes the structure.
6. **File in the owning project's `resources/artifacts/`, never only as a chat artifact:** `build_packet.py --file-into` files spec and page; `record_rulings.py` files the rulings.
7. **Only decisions that belong to the principal.** Execute constraint-determined choices and resolve delegated technical choices yourself.
8. **The reader contract: a packet is a stranger-read document.** Name the `audience`, use plain labels, state `impact` both ways, label options by what pressing them does, gloss terms of art, and build every packet for a principal with `--strict-reader`.
9. **Generate from a data array; never hand-author rows or hand-edit generator output.** The context doctor fails unverifiable packet pages.
10. **Surface disagreement and prior positions with exact sources; never converge first,** and recommend against your own prior work where that is true.
11. **Open every generated packet before handing it over.** Both permanent defects were found by loading the page, not reading the source.
12. **A recorded ruling authorizes nothing** (`authorization.granted: false`). The action owner checks principal, scope and exact target before acting.
13. **Show the complete material** for correspondence, code, images, media or documents in `review_assets`; external references are never fetched.

## Contents

- [references/authoring.md](references/authoring.md): the six properties in full, review material, prior positions, content requirements, the reader contract. Read it before writing any spec.
- [references/filing-and-authority.md](references/filing-and-authority.md): the commands, filing, recording rulings, schema-2 records, provenance and action authority, retiring a packet. Read it when generating, filing or recording.
- [references/enforcement.md](references/enforcement.md): integrity markers, what the generator refuses, the two permanent fixtures. Read it when a build is refused, the doctor flags a packet, or before changing the generator.
- [references/review-assets.md](references/review-assets.md): the review-asset contract. Read it before constructing `review_assets`.
- [references/worked-example.md](references/worked-example.md): a complete spec, the filed copies, the paste and its rulings file. Read it before your first packet.
- [references/background.md](references/background.md): the origin measurement, relationship to autopilot, adversarial review and the handoff queue (`synthesis-project-management/scripts/handoff.py`), changelog, related skills. Read it when choosing between this skill and a neighbor.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.8.0 text now lives.
- When to use it, When NOT to use it, Use: below.

## When to use it

First apply [decision ownership](../synthesis-thinking-framework/references/decision-ownership.md).
Packets collect decisions that actually belong to the principal. Execute choices
already determined by constraints and resolve delegated technical choices without
putting them back into a questionnaire. Honor an explicit supervised review request.
Existing user grants remain usable within their scope; the new record format does
not require the user to repeat them.

Load when you owe your principal **five or more parallel decisions of the same shape**, each
needing supporting context, where you have a defensible recommendation per item and the decisions
matter enough to deserve attention but are too numerous for per-item conversation.

Natural fits: review findings to fix or waive · dependency bumps to take or hold · drafts to
publish, edit, or kill · files to migrate or leave · flaky tests to quarantine or fix · features
to build now, later, or never · candidates to advance on a defined rubric.

## When NOT to use it

- **Fewer than about five decisions.** Just ask in chat. The generator refuses below five without
  `--allow-small`.
- **The decisions are not parallel in shape.** A packet of unlike questions is a form, and a form
  is worse than a conversation.
- **You have no recommendation per item.** Then the packet is a questionnaire and *your analysis
  is not finished*. Do the analysis. The generator refuses a packet where no row carries a
  recommendation.

The failure mode of a good pattern is over-application. These three limits are the skill.

## Use

```bash
python3 scripts/build_packet.py --schema              # the spec format
python3 scripts/build_packet.py spec.json -o packet.html --strict-reader
python3 scripts/build_packet.py spec.json --stdout    # to a pipe
python3 scripts/build_packet.py spec.json --strict-reader \
    --file-into PROJECT/resources/artifacts/         # + <date>-<slug>-spec.json, <date>-<slug>.html
python3 scripts/record_rulings.py paste.txt \
    --spec PROJECT/resources/artifacts/<date>-<slug>-spec.json \
    --file-into PROJECT/resources/artifacts/         # -> <date>-<slug>-rulings.json
```
