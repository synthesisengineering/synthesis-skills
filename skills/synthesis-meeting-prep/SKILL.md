---
name: synthesis-meeting-prep
description: "Prepare a principal for a meeting as a chief of staff would: model the readers, weigh 60+ factors, deliver a scannable pack with a capture half, then debrief transcripts into decisions, commitments and profile updates. Use for 1:1s, reviews, forums, external meetings, interviews and follow-through."
license: "CC0-1.0"
depends_on: ["synthesis-context-lifecycle"]
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Meeting Prep

An agent preparing a principal for a meeting is not a summarizer. It
is the principal's chief of staff for one room: it figures out what
the room needs, what the principal wants, what could go wrong, and
puts exactly that on one scannable page. The content contract lives
in [references/requirements.md](references/requirements.md) — R1–R12
are normative. This file is the operating protocol.

## Binding rules

Rules 1 to 5 are section 5, "What the skill refuses"; the rest come from the prep and debrief loops and the configuration contract. New rules are appended.

1. **No model, no draft.** Model each key reader (relationship, technical depth, cares), the power map and the disclosure boundary before writing (R2).
2. **Re-verify every number.** Stale figures kill credibility.
3. **Mark confidence: fact, inference, guess.** Never fill a material gap with a guess presented as fact (factor 62); cut the line instead.
4. **Never contradict the principal's recorded positions.**
5. **Never cross the disclosure boundary for the room's least-trusted attendee.**
6. **Ground the register in 2–3 samples** of the principal's own writing to a comparable reader (R13); if none exists, say so in the pack.
7. **State the basis (R10) and the drivers** (the 3–5 factors that set the pack's shape) on the pack.
8. **Run `scripts/prep_lint.py` on every draft;** fix each finding or record why it is wrong. The linter is a backstop, not the author.
9. **Deliver assembled packages, never assembly kits:** no brackets for the principal to fill in.
10. **Debrief transcript-primary.** Never derive who said or decided what from a summary; no commitment without an owner and a date.
11. **Profiles belong to one workspace.** Pass the explicit `--context-repo` and `--workspace`; missing or ambiguous ownership blocks profile reads and writes and never triggers a search of other workspaces.
12. **Contribute to a pack another session holds through that session:** `synthesis msg <holder>` with the path and text; it writes the text or releases that one file for you. Never write inside another session's claim; a contribution covers one artifact and nothing else.

## Contents

- [references/requirements.md](references/requirements.md): R1 to R13, the normative content contract. Read it before drafting.
- [references/factor-inventory.md](references/factor-inventory.md): the 64 factors in six groups, marked for sizing, tone, content and risk. Read it in the Model step.
- [references/structures.md](references/structures.md): the structure variants by meeting type, and the capture half. Read it in the Draft step.
- [references/profiles-and-sharing.md](references/profiles-and-sharing.md): section 1, the configuration contract (`python3 scripts/prep_init.py resolve|init|add-reader --context-repo <abs repo root> --workspace <id> ...`, which prints JSON and exits 2 on any refusal), and shared prep contributions through the board. Read it before any profile operation or shared write.
- [references/workspace-profiles.md](references/workspace-profiles.md): who owns a profile, and what to do with a stray legacy one. Read it when a profile's owner is unclear.
- [references/preserved.md](references/preserved.md): the retired migration and grant procedures, verbatim. Read only to review the change.
- [references/background.md](references/background.md): the 1.0.0 release note and section 4, integration seams with daily rituals, meeting transcripts, OKF and the console. Read it when deciding which skill owns a step.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.3.0 text now lives.
- 2. The prep loop, 3. The debrief loop, 5. What the skill refuses: below.

## 2. The prep loop

For every meeting, in order:

1. **Gather.** Pull the knowledge factors (inventory §4): workspace
   OKF base, prior transcripts with these participants, comms since,
   tickets/commits/deliverables, docs and decks, reader profiles,
   2–3 samples of the principal's own writing to a comparable
   reader (R13 — required; if none exists, say so in the pack),
   external research for new faces, and re-verified numbers.
   Record the basis (R10) as you go — source, date, what it
   contributed.
2. **Model.** Write the audience model first (R2): each key
   participant's relationship, technical depth, and cares; the power
   map; the disclosure boundary. Then weigh the factor inventory and
   name the drivers (§6, factor 63) — the 3–5 factors that set this
   pack's shape. If a factor is unknown and material, say so; never
   fill a material gap with a guess presented as fact (factor 62).
3. **Size.** Duration, format, prep budget, and energy set the length
   (factors 4, 31, 32, 57). State the sizing in one line on the pack.
4. **Draft.** Pick the structure variant
   ([structures.md](references/structures.md)), drop inapplicable
   sections, and write to R1–R9: discuss-forward, dense, translated
   accomplishments, strategic altitude, specific credit, grounded
   register, scannable, positive framing. Mark confidence inline —
   fact, inference, guess.
5. **Lint.** Run `python3 scripts/prep_lint.py [--reader technical|nontechnical]
   [--room SIZE] PACK.md` on the draft (one `LINE: CODE: message` per
   finding, exit 1; exit 0 clean). It checks the
   mechanical half of the contract: footer placement, register leaks
   (ticket numbers and infrastructure terms for non-technical
   readers), empty-sentence patterns, name-drop openers, unverified
   numbers, missing basis. Fix every finding or record why it is
   wrong — the linter is a backstop, not the author.
6. **Deliver.** The pack plus its capture half, filed where the
   principal's workflow expects it (workspace `meeting-preps/` by
   default, `<date>-<slug>-prep.md`), and the two-line drivers note
   in chat. Never deliver brackets for the principal to fill in —
   assembled packages, not assembly kits.

## 3. The debrief loop

After the meeting, when a transcript or notes exist:

1. **Verify the record.** Transcript-primary: the verbatim record is
   the only source for attribution-bearing claims. Never derive who
   said or decided what from a summary.
2. **Extract.** Decisions (verbatim where it matters), commitments
   with owner and date — no ownerless commits — quotes worth keeping,
   and the prep-vs-reality gap: what the prep missed or mis-weighted.
3. **Draft the follow-ups.** Assembled, in the principal's register,
   ready to send — not a list of "follow up on X."
4. **Update the profiles.** Reconfirm the workspace owner, then fold the gap
   into its reader profiles:
   what landed, what didn't, what they were told. This is how prep
   compounds.
5. **Capture durable facts.** Anything that belongs in the workspace
   knowledge base goes there now, with provenance — not "later."

## 5. What the skill refuses

- Prep for a reader it has not modeled — no model, no draft.
- Numbers it has not re-verified — stale figures kill credibility.
- Guesses presented as facts — mark confidence or cut the line.
- Prep that contradicts the principal's recorded positions.
- Anything that crosses the disclosure boundary for the room's
  least-trusted attendee.
