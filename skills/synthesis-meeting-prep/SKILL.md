---
name: synthesis-meeting-prep
description: "Prepare a principal for any meeting the way a wise chief of staff would: weigh 60+ factors across the meeting, participants, principal's position, knowledge, and risk; model the readers before drafting; deliver a dense, scannable pack with a capture half; then debrief the transcript into decisions, commitments, and reader-profile updates. Use for 1:1s, reviews, forums, external meetings, interviews, and post-meeting follow-through."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Meeting Prep

**Version 1.0.0** (2026-09-20): first release — the content contract
for meeting preparation (requirements R1–R12), the 64-factor
inventory, six structure variants, reader profiles, the debrief half,
and a mechanical prep linter (`scripts/prep_lint.py`).

An agent preparing a principal for a meeting is not a summarizer. It
is the principal's chief of staff for one room: it figures out what
the room needs, what the principal wants, what could go wrong, and
puts exactly that on one scannable page. The content contract lives
in [references/requirements.md](references/requirements.md) — R1–R12
are normative. This file is the operating protocol.

## 1. Configuration contract

All person-specific state lives outside the skill, in private paths
the skill reads at load time:

```
~/.synthesis/meeting-prep/principal.json     # role, goals, authority, tells
~/.synthesis/meeting-prep/readers/<id>.md    # per-person reader profiles (R12)
```

`principal.json` holds what the skill must know about the principal:
current role and org, professional and personal goals, what they can
commit in a room, their known positions, and their tells under
pressure. Reader profiles hold relationship, technical depth, what
the person cares about, what they have already been told, and what
landed last time. Both are created by interview the first time the
skill runs for a principal — never copied from another machine's
private files. Missing config degrades gracefully: the skill asks
the three questions it cannot proceed without (who is the reader to
you, how technical, what is the meeting's job) and drafts anyway.

## 2. The prep loop

For every meeting, in order:

1. **Gather.** Pull the knowledge factors (inventory §4): workspace
   OKF base, prior transcripts with these participants, comms since,
   tickets/commits/deliverables, docs and decks, reader profiles,
   the principal's writing samples to a comparable reader, external
   research for new faces, and re-verified numbers. Record the basis
   (R10) as you go — source, date, what it contributed.
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
5. **Lint.** Run `scripts/prep_lint.py` on the draft. It checks the
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
4. **Update the profiles.** Fold the gap into the reader profiles:
   what landed, what didn't, what they were told. This is how prep
   compounds.
5. **Capture durable facts.** Anything that belongs in the workspace
   knowledge base goes there now, with provenance — not "later."

## 4. Integration seams

- **Daily rituals** (`synthesis-daily-rituals` lead-time prep packs)
  own the scheduling machinery — which meetings need packs by when.
  This skill is the content contract that machinery drafts against.
- **Meeting transcripts** (`synthesis-meeting-transcripts`) own
  transcript fetch, naming, and the transcript-primary rule the
  debrief depends on.
- **OKF** (`synthesis-okf`) is the workspace knowledge interface
  for factor 37.
- **Console** renders packs filed under `meeting-preps/`; the basis
  statement is what makes them trustworthy there.

## 5. What the skill refuses

- Prep for a reader it has not modeled — no model, no draft.
- Numbers it has not re-verified — stale figures kill credibility.
- Guesses presented as facts — mark confidence or cut the line.
- Prep that contradicts the principal's recorded positions.
- Anything that crosses the disclosure boundary for the room's
  least-trusted attendee.
