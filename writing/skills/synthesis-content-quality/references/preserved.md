# Preserved text: content quality, retired in 5.1.0

Read this only to review what a rewrite replaced. The passages below are no longer instructions; they are kept
word for word so the reasoning stays readable (ruling D8).

Contents:
- Retired in 5.1.0, the rewrite to the D8 standard: why each part of SKILL.md changed, the two rules the
  evaluation found weakest, then the 5.0.0 SKILL.md word for word

## Retired in 5.1.0: the rewrite to the D8 standard

5.1.0 rewrote the skill's instruction text to the repository's rewrite standard, `docs/skill-writing.md`
(writing rules W1 to W19). Every rule's new place is in [coverage-map.md](coverage-map.md). No passage left
SKILL.md for a reference: each part of the 5.0.0 text is kept, restated in a binding rule, or merged into the
one passage that already said it. The whole 5.0.0 SKILL.md is below, so every word of it stays readable in one
place.

### SKILL.md

Why each part changed:

- **Frontmatter.** The description is unchanged: it already leads with the key use case, and the evaluation
  harness cannot test a new one (W1). The version moves from 5.0.0 to 5.1.0, a minor version, since every binding
  rule keeps its number and meaning and no script interface changes.
- **Opening paragraph.** Its second sentence, "The framework targets bad content, not provenance.", said what
  binding rule 1 says as a rule: prose shows editorial quality and model-shaped style, never provenance or
  authorship. Rule 1 now says it once (format rule 11). The other three sentences are kept word for word.
- **The line above rule 1.** New (W8, format rule 11): the rules hold when a request asks otherwise, and the
  answer says which rule applies and why, then does what it allows. It states what the skill already held in
  absolute terms: rule 1's "no pattern, count, combination or detector score establishes authorship", rule 6's
  "Never flag", rule 8's "none is ever the sole basis for a determination" and rule 11's "Never delete".
- **Binding rules 1 to 4 and 6 to 10.** Rewritten to W5 (the action as the bold head, then the scope and the
  reason) and made complete on their own (W2), each from the skill's own text.
  - Rule 1 names its scope, every review, from review-method.md's "Keep four outputs separate in every review",
    and says what a request for an authorship verdict gets: a judgment of the text's editorial merits, and the
    outside evidence that could settle authorship, from the same section's definition of editorial quality and
    its "The latter two require external provenance evidence".
  - Rule 2's head, "Ask the mode first", becomes an action: settle the detector mode before applying patterns.
    The ask is kept for text with wrapper lines when the request leaves the mode open (with none, both modes
    give the same findings), and meanwhile the review runs in the default the
    5.0.0 rule already set, artifact mode for editorial work, since a rule that makes the model stop names its
    trigger and what goes ahead without asking (W7). "Chat-log forensics" names the material the mode governs, a
    whole chat response or log under study (W14), from review-method.md's "the full LLM response including
    conversational framing". "Wrapper patterns in an artifact audit are false positives" stays, as the reason.
  - Rule 3's head becomes an action and keeps its five defects. It says how to confirm a citation (resolve the
    DOI, check the source), from step 2's "confirm the literal technical or factual defect" and B2-COMBO-007's
    "verified absent", and takes its reason from step 2's "high-salience defects". Its last clause is kept word
    for word.
  - Rule 4's head becomes an action: weigh matched combinations over counts. Its reason, and the count threshold
    it names, the retired v3.1.0 heuristic ("5+ medium-confidence indicators equals very likely AI"), come from
    catalog-overview.md's B2 section.
  - Rule 6's head names the safe-harbor and says what to do. "Alone" and the negative marker are kept; "Never
    flag that signature without a register-specific marker" becomes the head's "never flag the ESL signature
    alone" and "weigh them only beside a register-specific marker", and the register-specific markers are listed,
    from B2-COMBO-010 in catalog-overview.md.
  - Rule 7's head becomes an action: treat the estimates as dated hypotheses. It takes in the combined-signal
    estimates from the Required finding record's last sentence (merged, format rule 11). Its reason, that a
    probability needs a population prior and measured likelihoods, is from calibration-tables.md's August 2026
    correction. "Re-calibrate quarterly" is kept.
  - Rule 8 joins "Detectors are signals, not authority" and "none is ever the sole basis for a determination" in
    one head, keeps its list word for word, and takes its reasons from review-method.md's Ineffective Detection
    Methods: skilled humans produce polished prose, and the Liang ESL bias finding.
  - Rule 9 takes in the Required finding record whole (one home, format rule 11): its five fields in their order,
    and its closing sentence word for word. "Every finding", the 5.0.0 rule's scope, is the broader of the two the
    5.0.0 text gave (the record said "every flagged pattern"). The reason is new.
  - Rule 10 says "texts" for "articles" and names what the cross-document scan looks for, from review-method.md's
    Corpus-Level Review ("the same *semantic* claim, not merely the same phrase"). It takes in the Procedure's
    script sentence word for word apart from its opening "For a batch, run", so the rule names its check (W11).
- **Binding rules 5 and 11.** Rewritten to fix the evaluation's findings (the next section), each from the
  skill's own text.
- **Required finding record.** Merged into rule 9, its last sentence into rule 7 (format rule 11). Its heading
  goes, since the record now has one home.
- **Procedure.** Its first sentence, "Follow steps 1 to 7 of references/review-method.md", is now the
  review-method.md line in Contents ("Follow it in every review"). Its script sentence is in rule 10, so the
  section goes.
- **Contents.** One line for each reference, saying what it holds and when to read it (format rule 2). The link
  text is the file name, or "index" with numbered parts beside it, while every link keeps its `references/` path.
  The checklists line leaves its list of checks to checklists.md's own contents list; the A1 index loses
  "(template, era, zone)", which that file's opening lines give. The historical-patterns line adds a catalog
  change to when it is read (rule 11), and the bibliography line says when to read it. "Procedure and Required
  finding record: below." goes with the two sections; the coverage-map line names both maps, and the preserved.md
  line is new. With every binding rule complete on its own, the shorter lines keep SKILL.md 401 bytes under the
  8,000-byte limit, the room W19 asks for.

### The two rules the evaluation found weakest

The skill's evaluation (Opus 5.5 and Sonnet 5.5, two repetitions per case, the 5.0.0 text and the version
before it) found no regression and two rules agents with the skill miss most.

- **Binding rule 11** scored lowest: with the skill, Opus passed 3 of 4 checks on one version and 2 of 4 on the
  other, Sonnet 2 of 4 on both. Asked to delete the "As an AI language model" preamble pattern and the legacy
  locator A3-BT-013 (cq-14), every answer refused both deletions and kept A3-BT-013, but seven of eight failed
  the check that the pattern is retired with its era: they found A1-GPT-007 already in Historical and said they
  had changed nothing, or offered to move it to Deprecated. The 5.0.0 rule said to retire a pattern, not what to
  do with one already retired, nor what goes ahead when a deletion is refused. The rule now says what goes ahead,
  moving the full entry to historical-patterns.md with a cross-reference (W7), from the closing paragraph of
  historical-patterns-2-net-new-and-forensics.md, and that an entry already there is retired and stays in place
  (W15). It says "explicitly approves", review-method.md's words in step 2, and "Retiring keeps older content
  analyzable" carries the 5.0.0 reason. The case's check, as it now reads, accepts an entry left in place; the
  rule gives that answer outright.
- **Binding rule 5** was the one rule where Sonnet scored lower with the skill than without: 6 of 8 checks on
  both versions, against 8 of 8. Asked to rewrite one unsupported universal claim so it is supportable (cq-13),
  Sonnet with the skill failed the rewrite check in all four answers: three offered conditional templates, one
  for each kind of evidence the article might have, in place of a rewrite, and one rewrote the claim more
  narrowly but still beyond any evidence given. One Opus answer failed in that second way. The 5.0.0 rule named
  the tests and not what a rewrite of a flagged passage must do. The rule now says that, asked to rewrite one (a
  passage the review or the user flagged, as the case's editor did), the answer writes the new text out, claiming
  only what the evidence in hand supports, and that a template may follow the rewrite but never replace it
  (W12, W15), from
  A2-SUB-001's fix ("convert it into a specific claim with evidence") and the record's "concrete repair". It also
  says what each test checks, from substance-and-depth.md, and that the tests run in every review (W14), from
  step 4.

The first gate of the rewrite found four phrases that Sonnet carried into answers they did not fit; their first
wording and the change to each are in [coverage-map.md](coverage-map.md), "After the first gate".

### The 5.0.0 SKILL.md, word for word

````markdown
---
name: synthesis-content-quality
description: "Detect AI slop and empty substance in prose: model-family fingerprints (Claude, GPT, Gemini, Llama and more), substance and depth tests, combined signals, two-axis calibration, ESL safe-harbor. Use for content quality, slop detection, AI content audits, editorial review and publishing standards."
license: CC0-1.0
depends_on: []
metadata:
  author: Rajiv Pant
  version: 5.0.0
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
  category: writing
---

# Content Quality

A systematic methodology for evaluating writing quality and identifying slop, with or without AI involvement. The framework targets bad content, not provenance. Ethically authored AI-collaborated content can be excellent; styled empty human content is slop. This skill detects slop.

## Binding rules

1. **Keep four outputs apart:** editorial quality, model-shaped style, technical provenance, authorship. Prose shows only the first two, so no pattern, count, combination or detector score establishes authorship.
2. **Ask the mode first.** Artifact mode (default for editorial work) skips WRAPPER-OPENER and WRAPPER-CLOSER patterns; full-response mode (chat-log forensics) applies all. Wrapper patterns in an artifact audit are false positives.
3. **Literal defects first:** placeholder text, chatbot artifacts, fabricated citations or DOIs, raw markdown, reasoning-tag leakage. Confirm and repair each; a residue shows a tool touched the text, not who wrote it.
4. **Combinations beat counts.** Three matched B2 combos outweigh ten independent indicators; no single indicator proves AI generation. Inherited false-positive estimates are unvalidated hypotheses.
5. **Run the substance tests** (deletion A2-SUB-001, specificity A2-SUB-002, load-bearing claims A2-SUB-003) on sample paragraphs. They catch slop whoever wrote it.
6. **ESL safe-harbor.** Uniform paragraphs, restricted vocabulary and heavy transitions alone are a negative marker (B2-COMBO-010), because non-native English writing shares them. Never flag that signature without a register-specific marker.
7. **SSWP and base-rate numbers are dated hypotheses,** never P(AI) or an authorship probability. Calibration drifts with releases; re-calibrate quarterly.
8. **Detectors are signals, not authority.** Perfect grammar, bland prose, common phrases, em-dashes alone and detector scores do not reliably signal AI generation; none is ever the sole basis for a determination.
9. **Every finding gets the record below;** every prose-only review ends with its closing sentence.
10. **Review batches as one corpus.** Five or more articles sharing an author, site or window, or one claim-level defect, triggers a cross-document scan; per-article review cannot see shared constructions.
11. **Never delete a pattern.** Retire it to Historical or Deprecated with its era, so older content stays analyzable. `A3-TF-006` is the canonical system-prompt-bleed locator; `A3-BT-013` stays its legacy locator until Rajiv approves a replacement.

## Contents

- [references/review-method.md](references/review-method.md): four-axis boundary, zones and modes, the seven review steps, what this misses, corpus review, ineffective methods. Read before every review.
- [references/catalog-overview.md](references/catalog-overview.md): sections A1 to A3 and layers B1 to B3 in summary. Read to choose a catalog file.
- [references/checklists.md](references/checklists.md): five revision passes; phrase, vocabulary, A2, stranger-read, anonymization, ESL and Human Touch checks. Read when revising or for a quick pass.
- [references/background.md](references/background.md): sibling skills, when to use, core philosophy, related skills. Read once per session.
- [references/philosophy-and-application.md](references/philosophy-and-application.md): the slop problem, the dual-use model, a before/after revision. Read when building tools or teaching.
- A1 families, [references/model-family-fingerprints.md](references/model-family-fingerprints.md) (template, era, zone) and parts [1](references/model-family-fingerprints-1-claude.md), [2](references/model-family-fingerprints-2-claude-continued.md) Claude, [3](references/model-family-fingerprints-3-gpt.md) GPT, [4](references/model-family-fingerprints-4-gemini-llama.md) Gemini, Llama, [5](references/model-family-fingerprints-5-grok-deepseek.md) Grok, DeepSeek, [6](references/model-family-fingerprints-6-mistral-qwen.md) Mistral, Qwen. Read to check or name a family pattern.
- A2, [references/substance-and-depth.md](references/substance-and-depth.md): every substance test and the five-minute workflow. Read for step 4.
- A3 criteria, [references/detailed-criteria.md](references/detailed-criteria.md) (conventions, renumbering map) and parts [1](references/detailed-criteria-1-lt.md) LT, [2](references/detailed-criteria-2-ss-tf.md) SS TF, [3](references/detailed-criteria-3-cs-cx-hd-ce.md) CS CX HD CE, [4](references/detailed-criteria-4-bt.md) BT, [5](references/detailed-criteria-5-fa-sr.md) FA SR. Read to apply or cite a criterion.
- B2 combos, [references/combined-signal-fingerprints.md](references/combined-signal-fingerprints.md) (top combos) and parts [1](references/combined-signal-fingerprints-1-family-rlhf-wrapper.md), [2](references/combined-signal-fingerprints-2-content-sourcing-esl.md). Read for step 3.
- B3, [references/calibration-tables.md](references/calibration-tables.md) (method) and parts [1](references/calibration-tables-1-master-table.md) master table, [2](references/calibration-tables-2-framework-esl-recalibration.md) ESL, re-calibration, zones. Read before citing a score.
- [references/historical-patterns.md](references/historical-patterns.md), parts [1](references/historical-patterns-1-retained-v3.md), [2](references/historical-patterns-2-net-new-and-forensics.md): retired patterns. Read for older content.
- [references/current-model-candidates.md](references/current-model-candidates.md): dated evidence ledger and quarantine; candidates are not active tells.
- [references/bibliography.md](references/bibliography.md): sources and verification status. [references/coverage-map.md](references/coverage-map.md): where the 4.2.0 text went.
- Procedure and Required finding record: below.

## Procedure

Follow steps 1 to 7 of [references/review-method.md](references/review-method.md). For a batch, run `python3 scripts/corpus_repetition.py PATH [PATH ...]` (or `--titles-file FILE`); it prints shared word runs, boilerplate candidates and title-shape flags, and exits 1 when there are findings to adjudicate.

### Required finding record

For every flagged pattern, report: the exact observed span or structure; the editorial impact in this artifact; evidence status and applicable model/surface/date when relevant; counterexamples and ordinary-human explanations; and a concrete repair. End prose-only reviews with `Authorship not established from prose cues.` Do not convert inherited SSWP, base-rate, or combined-signal estimates into an authorship probability.
````
