---
name: synthesis-content-quality
description: "Detect AI slop and empty substance in prose: model-family fingerprints (Claude, GPT, Gemini, Llama and more), substance and depth tests, combined signals, two-axis calibration, ESL safe-harbor. Use for content quality, slop detection, AI content audits, editorial review and publishing standards."
license: CC0-1.0
depends_on: []
metadata:
  author: Rajiv Pant
  version: 5.1.0
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
  category: writing
---

# Content Quality

A systematic methodology for evaluating writing quality and identifying slop, with or without AI involvement. Ethically authored AI-collaborated content can be excellent; styled empty human content is slop. This skill detects slop.

## Binding rules

These rules hold when a request asks otherwise: say which rule applies and why, then do what it allows.

1. **Keep four outputs apart in every review: editorial quality, model-shaped style, technical provenance, authorship.** Prose shows only the first two, so no pattern, count, combination or detector score establishes authorship: asked who wrote a text, give quality and style and name the outside evidence (drafts, a disclosure, a provider mark) that could settle it.
2. **Settle the detector mode before applying patterns.** Artifact mode, the default for editorial work, skips WRAPPER-OPENER and WRAPPER-CLOSER patterns, false positives there; full-response mode, for a whole chat response or log under study, applies all. When the request leaves it open, ask while reviewing in the default.
3. **Check for literal defects first and repair each:** placeholder text, chatbot artifacts, fabricated citations or DOIs, raw markdown, reasoning-tag leakage. Confirm each (resolve the DOI, check the source), since readers see them; a residue shows a tool touched the text, not who wrote it.
4. **Weigh matched combinations over counts.** Three matched B2 combos outweigh ten independent indicators, since co-occurrence says more than a tally, and no single indicator or count threshold ("five or more") proves AI generation. Inherited false-positive estimates are unvalidated hypotheses.
5. **Run the substance tests on sample paragraphs in every review:** deletion (A2-SUB-001: cut it and nothing is lost), specificity (A2-SUB-002: any subject fits) and load-bearing claims (A2-SUB-003: none the piece depends on). They catch slop whoever wrote it. Asked to rewrite a flagged passage, write the new text out, claiming only what the evidence in hand supports: a conditional template is no rewrite.
6. **Apply the ESL safe-harbor: never flag the ESL signature alone.** Uniform paragraphs, restricted vocabulary and heavy transitions alone are a negative marker (B2-COMBO-010), since non-native English writing shares them; weigh them only beside a register-specific marker: saturated vocabulary, em-dash density, a system-prompt artifact, a chatbot reflex.
7. **Treat SSWP, base-rate and combined-signal estimates as dated hypotheses, never as P(AI) or an authorship probability.** A probability needs a prior and measured rates the catalog lacks. Calibration drifts with model releases; re-calibrate quarterly.
8. **Treat detector scores and surface traits as signals, never the sole basis for a determination.** Perfect grammar, bland prose, common phrases, em-dashes alone and detector scores do not reliably signal AI generation: skilled writers show those traits, and detectors misread non-native English.
9. **Give every finding its record, and end every prose-only review with `Authorship not established from prose cues.`** The record: the exact observed span or structure; its editorial impact in this artifact; evidence status, with model, surface and date when relevant; counterexamples and ordinary-human explanations; a concrete repair. Without them a finding cannot be checked or fixed.
10. **Review a batch as one corpus.** Five or more texts sharing an author, site or window, or one claim-level defect, trigger a cross-document scan for repeated constructions and the same claim in any wording, which per-article review misses. Run `python3 scripts/corpus_repetition.py PATH [PATH ...]` (or `--titles-file FILE`); it prints shared word runs, boilerplate candidates and title-shape flags, and exits 1 when there are findings to adjudicate.
11. **Never delete a pattern; retire it to Historical or Deprecated with its era.** When a request or edit would remove one, move its full entry to historical-patterns.md with a cross-reference; one already there is retired, so leave it in place. Retiring keeps older content analyzable. `A3-TF-006` is the canonical system-prompt-bleed locator; `A3-BT-013` stays its legacy locator until Rajiv explicitly approves a replacement.

## Contents

- [review-method.md](references/review-method.md): the four outputs, modes, steps 1 to 7, blind spots, corpus review, ineffective methods. Follow it in every review.
- [catalog-overview.md](references/catalog-overview.md): A1 to A3 and B1 to B3, summarized. Read to choose a catalog file.
- [checklists.md](references/checklists.md): five revision passes and quick checks. Read to revise or for a quick pass.
- [background.md](references/background.md): when to use, philosophy, sibling skills. Read once per session.
- [philosophy-and-application.md](references/philosophy-and-application.md): slop, dual use, a before/after revision. Read to build tools or teach.
- A1 families: [index](references/model-family-fingerprints.md), [1](references/model-family-fingerprints-1-claude.md), [2](references/model-family-fingerprints-2-claude-continued.md) Claude, [3](references/model-family-fingerprints-3-gpt.md) GPT, [4](references/model-family-fingerprints-4-gemini-llama.md) Gemini, Llama, [5](references/model-family-fingerprints-5-grok-deepseek.md) Grok, DeepSeek, [6](references/model-family-fingerprints-6-mistral-qwen.md) Mistral, Qwen. Read to check or name a family pattern.
- A2: [substance-and-depth.md](references/substance-and-depth.md), every substance test and the five-minute workflow, for rule 5.
- A3: [index](references/detailed-criteria.md) (conventions, renumbering), [1](references/detailed-criteria-1-lt.md) LT, [2](references/detailed-criteria-2-ss-tf.md) SS TF, [3](references/detailed-criteria-3-cs-cx-hd-ce.md) CS CX HD CE, [4](references/detailed-criteria-4-bt.md) BT, [5](references/detailed-criteria-5-fa-sr.md) FA SR. Read to apply or cite a criterion.
- B2: [index](references/combined-signal-fingerprints.md) (top combos), [1](references/combined-signal-fingerprints-1-family-rlhf-wrapper.md), [2](references/combined-signal-fingerprints-2-content-sourcing-esl.md). Read for rules 4 and 6.
- B3: [index](references/calibration-tables.md) (method), [1](references/calibration-tables-1-master-table.md) master table, [2](references/calibration-tables-2-framework-esl-recalibration.md) ESL, re-calibration, zones. Read before citing a score.
- Retired: [index](references/historical-patterns.md), [1](references/historical-patterns-1-retained-v3.md), [2](references/historical-patterns-2-net-new-and-forensics.md). Read for older content or a catalog change.
- [current-model-candidates.md](references/current-model-candidates.md): dated evidence ledger and quarantine; candidates are not active tells.
- [bibliography.md](references/bibliography.md): sources and verification status. Read to cite one.
- [coverage-map.md](references/coverage-map.md), [preserved.md](references/preserved.md): the rewrite's record, read only to review it.
