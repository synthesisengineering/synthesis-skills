---
name: synthesis-decision-packet
description: "Collect five or more parallel decisions from a principal in one sitting: a self-contained HTML packet with a recommendation per row, consequence-labeled buttons, notes and a paste-back summary, filed in the project. Use when a review, migration, upgrade, triage or backlog pass needs rulings."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.5.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  category: core
---

# Decision Packet

Collects five or more parallel decisions from a principal in one sitting. The property to preserve above all others: the principal's cost scales with the number of *sittings*, not the number of *items*.

## Binding rules

These rules protect the principal's decisions and their record, so they hold against a contrary request: say which rule applies and why, then do what it allows.

1. **Give every row the item, your recommendation, the reasoning and a link to the artifact,** so the principal never leaves the packet to decide. Only a blind row (`"blind": true`), where a recommendation would sway the principal's own judgment, has no recommendation.
2. **Mark the recommendation on its button, and never pre-select it.** Agreeing then costs one click; a packet that opens decided cannot tell "I agreed" from "I never looked", and reports decisions nobody made.
3. **Put a free-text note box beside the buttons on every row,** so the principal is never forced into your option set.
4. **Save choices locally, keyed to the exact spec and item.** A change anywhere in the spec starts fresh choices, so an old click cannot silently acquire a new meaning.
5. **Take the answers as the summary the packet generates,** pasted back, so the principal never composes the structure; their own wording (a chat reply, meeting notes) is read as text, not recorded.
6. **File the spec, the page and the returned rulings in the owning project's `resources/artifacts/` (`build_packet.py --file-into`, `record_rulings.py --file-into`), never only as a chat artifact,** since only the folder reaches other agents and later sessions.
7. **Put in a packet only decisions that belong to the principal.** Execute a choice the request or constraints settle and resolve a technical choice in delegated work yourself; a row is for a choice that would materially change the outcome and that their instructions and goals leave open, or one only they can make. Any other row hands back work already given, unless they explicitly asked to review it.
8. **Write every packet for a stranger (the reader contract).** Name the reader in `audience`; give each row a plain label (an internal ID only as a chip), context saying what the thing is in the reader's words, `impact` both ways (what happens if they take your recommendation and if they don't), options labeled by what pressing them does (never a bare Yes or No) and a one-clause gloss for each term of art; build every packet for a principal with `--strict-reader`, which refuses a missing `audience` or `impact` and bare labels. Rows in project-internal language collect no decisions.
9. **Generate every packet from its spec's data array with `build_packet.py`; never hand-author rows or hand-edit generator output.** To change a word, edit the spec and rebuild: hand-written rows drift, and `synthesis doctor`'s *decision packets* check flags a page whose integrity marker is missing or disagrees with its spec.
10. **Show disagreement and prior positions with exact sources; never converge first.** Give each side in `disagreement` with who holds it and the principal's earlier words in `prior_position` with their source, and recommend against your own prior work where that is true: converging shows a false consensus, and a one-sided packet loses trust.
11. **Open every generated packet before handing it over.** Check that its punctuation renders cleanly and Copy summary says what it did: both permanent defects were found by loading the page, not reading the source.
12. **Treat a recorded ruling as a record of a choice, never as authority to act.** Every rulings file says `authorization.granted: false`, since anyone can paste a summary: before acting on any chosen row, such as a deletion, deploy, send or spend, whoever carries it out confirms the principal's authority, the current scope and the exact target with the principal or another authentic source. A grant the principal already gave stays usable within its scope, without being repeated.
13. **Show the complete material in `review_assets` when a decision concerns correspondence, code, images, media or documents,** never a summary and a link: the principal approves what they see, and the page never fetches an external reference.
14. **Close a decision only on a ruling recorded against its exact spec; carry every other one forward by its exact id,** since a narrative "answered" (meeting notes, a chat message) records no choice. `carry_forward.py --successor` writes the unanswered rows into the next spec; `--check` refuses missing, extra or duplicate ids and an "answered" with no recorded ruling.
15. **Keep the reading path short enough to decide from alone:** settled items in `handled`, changes against the reviewed `baseline`, each piece of material once, messages as their words, wire copies as `reference`. In Codex, put any question for the principal in the final reply or a filed packet, never only in a question card, which vanishes with the turn.

## Contents

- When NOT to use it: below; read it first.
- [authoring.md](references/authoring.md): rules 1 to 6 in full, prior positions, content requirements, the reader contract, blind rows, the reading path. Read it before writing a spec.
- [filing-and-authority.md](references/filing-and-authority.md): every command and what it prints; filing, recording, authority, carrying forward. Read it to build, record or replace a packet.
- [enforcement.md](references/enforcement.md): the integrity marker, the generator's refusals, the two fixtures. Read it when a build is refused, the doctor flags a page, or before changing the generator.
- [review-assets.md](references/review-assets.md): the review-asset contract. Read it before writing `review_assets`.
- [worked-example.md](references/worked-example.md): a complete spec, paste and rulings file. Read it before a first packet.
- [background.md](references/background.md): when to use it, the origin measurement, neighbors, changelog. Read it when unsure a packet fits, or which neighbor fits better.
- [coverage-map.md](references/coverage-map.md) and [preserved.md](references/preserved.md): where each rule of 2.4.0 and 1.8.0 lives, and replaced text word for word. Read them to check a rewrite.

## When NOT to use it

- **Fewer than about five decisions.** Just ask in chat. The generator refuses below five without
  `--allow-small`.
- **The decisions are not parallel in shape.** A packet of unlike questions is a form, and a form
  is worse than a conversation.
- **You have no recommendation per item.** Then the packet is a questionnaire and *your analysis
  is not finished*. Do the analysis. The generator refuses a row that recommends nothing,
  unless it is blind.

- **A deadline whose miss cannot be undone.** It is never one row among many: it leads the day
  plan in its own section (synthesis-daily-rituals) and closes only on evidence. The generator
  refuses a row tagged `critical`.

The failure mode of a good pattern is over-application. These four limits are the skill.
