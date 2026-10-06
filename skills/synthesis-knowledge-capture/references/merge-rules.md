# Knowledge capture: merge, routing, reconciliation and provenance rules

The full text behind binding rules 1 to 8. Read when merging a fact, choosing its tier, resolving a contradiction with the corpus, or recording its source.

Contents:
- Merge discipline: the four hard rules
- Confidentiality routing
- Reconcile, never blind-flip: staleness, axis, ambiguity
- Provenance

## Merge discipline — the four hard rules

1. **Scan first, always.** No write without a completed `kb_scan.py` for every
   entity involved. The scan is the difference between merging and littering.
2. **In place, not append.** Stable facts are corrected where they live. A new
   concept file is for a genuinely new unit of knowledge, not for a fact that
   updates an existing one.
3. **Reconcile, never blind-flip.** When a new fact contradicts the corpus, the
   contradiction is data, not a mandate to overwrite. See below.
4. **No fact without a source.** Every merged claim cites its in-session origin.
   If you cannot name who said it or which tool surfaced it, you cannot write it
   — the same provenance bar the rest of the synthesis stack enforces.

## Confidentiality routing

- **Default to the most private tier that fits.** When unsure whether a fact
  belongs in a shared corpus, it does not. Route it private and flag the
  question.
- **Split neutral from candid.** Org-structure facts (title, reporting line,
  who owns a product) are usually fine for a shared internal KB. Candid framing
  (why someone left, a performance read, negotiation posture) is not — that is
  private, always, regardless of how the fact was learned.
- **A public repo takes no confidential term.** If the target is a public repo,
  the config's confidential-term list is a hard filter: any fact containing one
  is rerouted to a private target or dropped, never sanitized-and-shipped.
- **Learned-in-a-shared-channel is not permission.** Where a fact was surfaced
  does not set where it may be stored. The confidentiality tier of the *fact*
  governs, per config.

## Reconcile, never blind-flip

When a new fact contradicts what the corpus already says, stop and resolve the
*shape* of the disagreement before writing:

- **Staleness** — the corpus is simply out of date. Update in place; the old
  framing is wrong now.
- **Axis** — both are true on different axes (a person can lead a business unit
  *and* report through a commercial line; a title and a functional role are not
  the same statement). Add the new axis; leave the still-true one.
- **Ambiguity in the new fact** — the sentence that delivered the fact may
  parse two ways. Resolve the antecedent with the person who stated it before
  editing. A blind flip on a misread injects an error the corpus did not have.

The cost asymmetry is the whole rule: re-reading and asking one question is
cheap; a wrong edit propagated into a shared corpus is expensive and quiet.

## Provenance

- Each merge writes a `log.md` line: date, the concept(s) touched, the fact, and
  the in-session source.
- For a fact whose truth a future reader must trust or re-check, record the
  source explicitly in the concept too (`*Source: …*`), matching the corpus's
  existing citation style.
- Treat the knowledge base as a cache, not the source of truth. A concept's
  `timestamp` records when it was last believed correct, not when it was last
  true. Re-verify before propagating a load-bearing fact outward.
