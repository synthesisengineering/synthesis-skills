# Publication-Review Acceptance Fixtures

Worked fixtures for the publication-review stack this skill's load-with
contract assembles. Most enforce Phase 4 (publication-package review) or the
Phase 3 additions (lede protection, sibling search) of this skill; fixtures
5-6 are enforced by `synthesis-reader-briefing`'s series-dependency contract,
fixture 11 jointly with `synthesis-fact-checking`'s circular-grounding
terminal, and fixture 17 by `synthesis-content-quality`'s corpus checker
(which deduplicates mirrored content before measuring). Each fixture states a
scenario and the disposition a correct review of the full stack must produce.
Use them to test a review process, a reviewer agent, or a proposed change to
these gates: a process that passes a fixture's scenario with the wrong
disposition fails the gate.

They generalize a real 30-article staged batch in which a full-body review
cleared 29 of 30 packages and a title-only pass then found 6 titles worth
keeping, 8 needing material tuning, and 16 needing replacement — plus two
descriptions that broadened their bodies' claims, four concentrated
lede/first-use repairs, and (in a later human preview) 21 stale slugs from
superseded headlines.

## Title and truth-contract fixtures

1. **Opaque coined-principle title, clear description.** A title that is an
   accurate but opaque coined phrase, paired with a clarifying description,
   MUST fail the title-only test. The description cannot rescue the
   title-only row; it is evaluated in the second (title+description) pass.
2. **Strong title, weak body.** A magnetic title whose body does not deliver
   the promised object MUST fail promise match, however good the body is on
   its own terms.
3. **Scoped body, broadened metadata.** A body with careful scope whose
   title or description asserts the unscoped claim MUST fail truth
   alignment — even when every body sentence is individually accurate.
4. **Heading asserting an unargued conclusion.** A section heading stating a
   claim its own section never establishes (for example, a contested
   empirical assertion presented as settled) MUST fail truth alignment at
   the same severity as fixture 3. Frontmatter-only truth checks miss this.

## Series and dependency fixtures

5. **Series article with sufficient one-clause context.** An article in a
   legitimate series that glosses its terms in one clause MUST pass without
   a prerequisite block. Formulaic cross-linking is not required.
6. **Genuine chapter dependency without a link.** An article whose argument
   genuinely requires a prior article MUST fail until it links the
   prerequisite with a one-sentence reason to read it first.

## Batch-shape fixtures

7. **Individually acceptable, collectively monotonous.** A batch of titles
   each fine alone but concentrated in one mechanism (for example,
   reversal/confession) MUST surface a monotony judgment for the reviewer —
   reported, then adjudicated title by title, not auto-failed.
8. **Cure worse than the disease.** A replacement title set that reduces the
   diagnosed formula while raising a different axis above the batch-shape
   budget (for example, "AI" token share jumping from 40% to 88%, or a
   two-word opening repeated four times) MUST fail. The replacement set is
   measured on the same axes as the original.

## Lede and provenance fixtures

9. **Whole-article revision note as de-facto lede.** A package whose first
   meaningful sentence is the revision/provenance note, with no standfirst,
   MUST surface a lede decision. The valid sequence standfirst → note →
   body passes.

## Evidence-discipline fixtures

10. **Repair that retires the finding but not the defect.** An article with
    two instances of the same defect class (one flagged, one load-bearing
    and unflagged) where the proposed minimum repair addresses only the
    flagged instance MUST fail. Within-article sibling search is part of
    closing any finding.
11. **Derivative doctrine cited as independent evidence.** A grounding
    record that cites the author's own skill/doctrine (written from the
    same claim) as evidence for that claim MUST remain graded derivative.
    Propagation cannot upgrade source grade. (Enforced jointly with
    `synthesis-fact-checking`.)
12. **Review with no title disposition table.** A reviewer that audits every
    body but emits no per-article title disposition (or no N-row table for a
    batch) CANNOT sign publication readiness, whatever else passed.

## Slug and metadata fixtures

13. **Final-title change, unchanged slug.** An unpublished article whose
    final selected headline differs from the headline its slug was derived
    from MUST fail while the slug/canonical stay unchanged without a
    recorded exception — even when the build is clean.
14. **Route migration missing one surface.** A migration that updates most
    surfaces but misses one (a category key, a transaction-universe row, a
    preview path, a regenerator constant, an internal link) MUST fail; the
    closure is all-surfaces-together.
15. **Complete migration proof.** A passing migration MUST show every
    current route present and every retired current route absent from the
    built output; historical evidence filenames (raw records preserving old
    URLs) must not be counted as failures.
16. **Published-article title change.** A title change on an
    already-published article MUST enter the preserve-or-redirect policy
    decision, not the unpublished deterministic-slug rule.

## Negative fixture — recorded so the gates stay honest

17. **Title-case drift hypothesis.** A measured corpus showed the staged
    batch followed the author's own recent title-case practice rather than
    inverting it; the first (wrong) measurement had triple-counted mirrored
    trees. No title-case rule ships from that evidence. The fixture's
    lesson: deduplicate the corpus before measuring it, and record failed
    hypotheses so they are not re-proposed.
