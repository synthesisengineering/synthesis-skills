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
