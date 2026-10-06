# Coverage map: content quality 4.2.0 to 5.0.0

Every part of the 4.2.0 SKILL.md and of every 4.2.0 reference file, and where it lives now (ruling D8). Nothing was removed, so there is no preserved.md.

Contents:
- SKILL.md sections and their new homes.
- Reference files: sizes, splits and the coverage-check result for each.
- Lines the coverage check reported, and why.
- Tests and the slop-detection manifest.
- The 4.2.0 frontmatter, quoted whole.
- The 4.2.0 lines with old link paths, quoted whole.

## SKILL.md sections

| 4.2.0 section | Now |
|---|---|
| Frontmatter description (eight-line keyword list) | Rewritten to 296 characters. It keeps the strongest triggers: content quality, slop detection, AI content audits, editorial review, publishing standards, model-family fingerprints with the family names, substance and depth, combined signals, two-axis calibration, ESL safe-harbor. Zone-conditional detection, causal-layer attribution and the compounding-archive principle stay in the text (binding rules 2 and 11, catalog-overview.md). The opening claim "The most comprehensive open-source slop detection system available" was left out of the description because a description says when to use the skill; the old text is quoted below |
| Frontmatter `license`, `depends_on: []`, `author`, `source_repo`, `source_type` | Kept: the installer and the source checks read them |
| Frontmatter `version: 4.2.0` | `5.0.0`, with `format: v5` added |
| Title and first paragraph | SKILL.md (verbatim) |
| Second paragraph (durable methodology, v4.0 additions, compounding archive) | references/background.md (verbatim); binding rule 11 |
| Where this skill fits in the writing-quality family | references/background.md (verbatim apart from two link paths) |
| When to Use This Skill | references/background.md (verbatim) |
| Core Philosophy | references/background.md (verbatim apart from one link path) |
| Four-axis inference boundary (August 2026 additive prototype) | references/review-method.md (verbatim); binding rule 1 |
| Zones and Detector Modes | references/review-method.md (verbatim); binding rule 2 |
| The Pattern Catalog: inventory note, Sections A1, A2, A3 and their August 2026 entries | references/catalog-overview.md (verbatim apart from link paths); binding rules 5 and 11 |
| The Cross-Cutting Layer: B1, B2, B3 | references/catalog-overview.md (verbatim apart from link paths); binding rules 4, 6 and 7 |
| Confidence-Based Evaluation Process, steps 1 to 7 | references/review-method.md (verbatim); binding rules 2 to 6 and 11; the Procedure section of SKILL.md points to the steps |
| Required finding record | SKILL.md (verbatim): test_additive_upgrade_contract reads its closing sentence from SKILL.md; binding rule 9 |
| What This Framework Does NOT Catch On Its Own | references/review-method.md (verbatim apart from link paths) |
| Corpus-Level Review (v4.2) | references/review-method.md (verbatim apart from the script link path); binding rule 10; SKILL.md's Procedure adds the command line and what it prints |
| Ineffective Detection Methods | references/review-method.md (verbatim); binding rule 8 |
| Systematic Revision Process for Creators | references/checklists.md (verbatim) |
| Quick-Reference Checklist (phrases, vocabulary, metaphors, subheadings, combined signals, A2 quick-check, stranger-read, anonymization, ESL safe-harbor check, Human Touch test) | references/checklists.md (verbatim apart from one link path) |
| Related Skills | references/background.md (verbatim apart from link paths) |
| References (the list of reference files) | references/background.md (verbatim apart from link paths); SKILL.md's Contents now lists every file, including the split parts |
| Closing rule and line ("Part of the synthesis writing craft...") | references/background.md (verbatim) |

No heading was renamed. New headings: `## Binding rules`, `## Contents`, `## Procedure` in SKILL.md, and the title, intro and contents list at the top of each new or split reference file.

## Reference files

Five files were larger than one read (about 60 KB). Each was split by section, verbatim: the file under the old name keeps its opening sections and gains a contents list naming its parts, and each part holds the following sections unchanged behind a short title and contents list. Parts sit in the same folder as the old file, so links inside the moved text still resolve, and a link to a split file lands on its index. The old line order holds across the index and its parts in sequence.

| 4.2.0 file | 4.2.0 size | Now | Coverage check |
|---|---|---|---|
| detailed-criteria.md | 212,735 bytes, 2,198 lines | Index (conventions and renumbering map) plus 5 parts: 1-lt (A3-LT), 2-ss-tf (A3-SS, A3-TF), 3-cs-cx-hd-ce (A3-CS, A3-CX, A3-HD, A3-CE), 4-bt (A3-BT), 5-fa-sr (A3-FA, A3-SR, cross-file and cross-skill dependencies, end of catalog) | All lines found verbatim |
| model-family-fingerprints.md | 245,340 bytes, 2,610 lines | Index (how to read this file) plus 6 parts: 1-claude (A1-CLAUDE-001 to 013), 2-claude-continued (A1-CLAUDE-014 to 028), 3-gpt, 4-gemini-llama, 5-grok-deepseek, 6-mistral-qwen (with the summary and cross-references) | All lines found verbatim |
| combined-signal-fingerprints.md | 94,053 bytes, 1,167 lines | Index (why combinations matter, how to read, top high-yield combos) plus 2 parts: 1-family-rlhf-wrapper, 2-content-sourcing-esl (with the historical, GPT-5-stripped, convergent, cross-reference and self-audit sections). The index lists which B2-COMBO IDs each part holds | All lines found verbatim |
| calibration-tables.md | 63,596 bytes, 543 lines | Index (B3.1 methodology) plus 2 parts: 1-master-table (B3.2), 2-framework-esl-recalibration (B3.3 to B3.6 and cross-file references) | All lines found verbatim |
| historical-patterns.md | 63,166 bytes, 447 lines | Index (preface) plus 2 parts: 1-retained-v3 (Section 1), 2-net-new-and-forensics (Sections 2 to 4) | All lines found verbatim |
| substance-and-depth.md | 54,967 bytes, 533 lines | Unchanged apart from a contents list after the title (fits one read) | All lines found verbatim |
| bibliography.md | 25,447 bytes, 269 lines | Unchanged apart from a contents list after the title | All lines found verbatim |
| philosophy-and-application.md | 8,698 bytes, 210 lines | Unchanged apart from a contents list after the title | All lines found verbatim |
| current-model-candidates.md | 4,745 bytes, 69 lines | Unchanged (under 150 lines) | All lines found verbatim |

New reference files made from SKILL.md text: review-method.md, catalog-overview.md, checklists.md, background.md, and this map.

## Lines the coverage check reported, and why

Run against `origin/main`, `v5-skill-coverage-check.py` reported 37 lines of the 4.2.0 SKILL.md until the record block at the end of this map quoted them. All 37 are text moved from SKILL.md into references/ with the wording unchanged and only a relative link adjusted, because a link written for SKILL.md breaks one folder down (`../synthesis-x/SKILL.md` became `../../synthesis-x/SKILL.md`, `references/x.md` became `x.md`, `references/` became `./`, `scripts/` became `../scripts/`):

- Where this skill fits: the writing-pitfalls and writing-craft bullets (background.md).
- Core Philosophy: "The full philosophical layer..." (background.md).
- The Pattern Catalog and The Cross-Cutting Layer: "The full catalog has approximately 180 patterns...", the "Full per-pattern detail", "Historical entries for retired family-era markers...", "Full detail and the five-minute editorial workflow", "Full per-criterion detail with all 16 fields", "The dated evidence ledger...", "Full per-criterion attribution", "Full catalog of all 86 combos" and "Full per-family per-criterion table" lines (catalog-overview.md).
- What This Framework Does NOT Catch: the five bullets with skill links (review-method.md).
- Corpus-Level Review: the "Mechanical support" paragraph (review-method.md).
- Quick-Reference Checklist: "See criterion `A3-FA-001`..." (checklists.md).
- Related Skills: all nine bullets (background.md).
- References: the lead-in line and all eight file bullets (background.md).

No reference file line was reported.

## Tests and the slop-detection manifest

- `tests/test_no_removals.py` and `tests/test_additive_upgrade_contract.py` now read a split file together with its numbered parts (`<name>-<n>-<slug>.md`, in order). The checks are unchanged: every baseline line must still appear in order across the file and its parts, the catalog counts must still reach 108 A1, 17 A2, 76 A3 and 86 B2 headers, and each August 2026 locator must still appear exactly once.
- `tools/slop-detection/manifest.md` lists the four new SKILL.md companions (review-method, catalog-overview, checklists, background) right after SKILL.md in the required files, and every split part after its index in the extended files.

## The 4.2.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-content-quality
description: >
  The most comprehensive open-source slop detection system available. Catches AI-generation
  patterns by model family (Claude, GPT, Gemini, Llama, Grok, DeepSeek, Mistral, Qwen),
  substance and depth failures (beautiful word salad), and the full v3.1.0 catalog
  refreshed. Includes causal-layer attribution, combined-signal fingerprints, two-axis
  calibration, ESL safe-harbor, and zone-conditional detection (artifact mode vs full-response
  mode). Spans the entire LLM era through the compounding-archive principle. Use for
  content quality, slop detection, AI content auditing, editorial review, content
  improvement, and publishing standards.
license: CC0-1.0
depends_on: []
metadata:
  author: Rajiv Pant
  version: 4.2.0
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

## The 4.2.0 lines with old link paths

The 37 lines listed above exactly as 4.2.0 had them, so the coverage check and synthesis-content-quality's no-removals test can match each one. The links here are written for SKILL.md's folder and are kept only as a record.

```markdown
- [`synthesis-writing-pitfalls`](../synthesis-writing-pitfalls/SKILL.md): Universal human-source bad-writing patterns (cringe, throat-clearing, caveat overload, cliché reliance). Stable across decades.
- [`synthesis-writing-craft`](../synthesis-writing-craft/SKILL.md): Positive principles from the writing-craft tradition.
The full philosophical layer — the quality problem and the five characteristics of AI slop, the dual-use (GAN-dynamic) improvement model, application guidance for detection-tool builders and for readers, the path from "was this AI?" to "is this good?", and a concrete before/after revision example — lives in [references/philosophy-and-application.md](references/philosophy-and-application.md). It is the frame the catalog operates inside; read it when building tools on this skill or teaching the methodology.
The full catalog has approximately 180 patterns organized across four sections. Each pattern carries the 14-field template plus era status (Active / Declining / Historical / Deprecated) and zone tag. Full per-pattern detail lives in [references/](references/) subfiles linked below.
Full per-pattern detail: [references/model-family-fingerprints.md](references/model-family-fingerprints.md).
Historical entries for retired family-era markers (Bard "As a large language model trained by..." preamble, GPT-3.5 "As an AI language model" preamble, GPT-3.5 "Here's the thing" intensifier, pre-instruction-tuning GPT-3, early Llama 1 / 2, early Grok 1, early DeepSeek V1 / V2, early Mistral 7B / Mixtral, early Qwen 1 / 2) live in [references/historical-patterns.md](references/historical-patterns.md). These patterns are largely trained out of current frontier models but remain valuable for forensic analysis of older published content per the compounding-archive principle.
Full detail and the five-minute editorial workflow: [references/substance-and-depth.md](references/substance-and-depth.md). Zone tag: BODY-PERSISTENT for all A2 sub-patterns (substance is about what the artifact says).
Full per-criterion detail with all 16 fields (14 base + era + zone): [references/detailed-criteria.md](references/detailed-criteria.md), which also includes a renumbering map from v3.1.0 numbers to the new IDs.
The dated evidence ledger and controlled-test quarantine live in [references/current-model-candidates.md](references/current-model-candidates.md). Candidates in quarantine are research inputs, not active tells.
Full per-criterion attribution: [references/calibration-tables.md](references/calibration-tables.md) (causal column).
Full catalog of all 86 combos: [references/combined-signal-fingerprints.md](references/combined-signal-fingerprints.md).
Full per-family per-criterion table: [references/calibration-tables.md](references/calibration-tables.md).
- **Upstream framing failures.** Articles where the writer never asked the audience question and the draft inherits the source material's frame. Prevention is upstream: [`synthesis-reader-briefing`](../synthesis-reader-briefing/SKILL.md). Criterion A3-FA-001 detects the failure in finished drafts; the briefing prevents it before drafting begins.
- **Errors of omission relative to the briefing.** The article passes every quality check and still does not deliver what the briefing promised. The Insight Quality lens in [`synthesis-article-writing`](../synthesis-article-writing/SKILL.md) is the closer fit.
- **Voice mismatch.** The article is technically correct but does not sound like the author. Use [`synthesis-voice-profiler`](../synthesis-voice-profiler/SKILL.md).
- **Strategic positioning errors.** A correct article in the wrong publication on the wrong topic at the wrong moment. Use [`synthesis-content-framing`](../synthesis-content-framing/SKILL.md).
- **Fact-checking gaps.** Use the companion skill [`synthesis-fact-checking`](../synthesis-fact-checking/SKILL.md) v2.0 for nested attribution, paraphrase drift, composite quotes, position-shifting, source-translation drift, URL rot vs hallucination, AI-generated synthetic sources, citation laundering chains, and tool-specific hallucination patterns.
**Mechanical support:** [scripts/corpus_repetition.py](scripts/corpus_repetition.py) takes a corpus (files, directories, or a titles list), reports maximal word-run repetition across documents with thresholds that survive ordinary English (function-word runs filtered, short overlaps ignored, high-document-frequency runs classified separately as boilerplate candidates), and measures batch title shape against the default budget (repeated two-word openings, watch-token concentration, imperative/second-person share). Judgment stays with the reviewer: quotes, deliberate refrains, and series boilerplate are legitimate repetition, and title-mechanism classification (reversal, negation, coined principle) is reviewer work the tool deliberately does not attempt. When a monotony diagnosis produces a replacement title set, measure the replacement on the same axes — a cure measured only against the disease it names is not measured. Batch-gate doctrine lives in [`synthesis-article-writing`](../synthesis-article-writing/SKILL.md) Phase 4. Nothing the tool reports establishes authorship.
See criterion `A3-FA-001` (insider context collapse) and [`synthesis-reader-briefing`](../synthesis-reader-briefing/SKILL.md).
- [`synthesis-writing-pitfalls`](../synthesis-writing-pitfalls/SKILL.md): Universal human-source bad-writing patterns (cringe, throat-clearing, caveat overload, sentence-level weakness, cliché reliance, stilted formality).
- [`synthesis-writing-craft`](../synthesis-writing-craft/SKILL.md): Positive writing principles from the writing-craft tradition.
- [`synthesis-reader-briefing`](../synthesis-reader-briefing/SKILL.md): Pre-writing audience analysis (prevents insider context collapse upstream).
- [`synthesis-article-writing`](../synthesis-article-writing/SKILL.md): End-to-end article workflow with quality gates.
- [`synthesis-article-refresh`](../synthesis-article-refresh/SKILL.md): Refresh and revitalize older articles.
- [`synthesis-voice-profiler`](../synthesis-voice-profiler/SKILL.md): Generate a structured voice profile.
- [`synthesis-fact-checking`](../synthesis-fact-checking/SKILL.md) v2.0: Companion skill for citation, quote, and source verification with per-family hallucination signatures.
- [`synthesis-clean-text`](../synthesis-clean-text/SKILL.md): Enforce clean-character and no-hidden-marker requirements, audit inspectable text properties, and state the boundary on unverifiable statistical marks.
- [`synthesis-text-provenance`](../synthesis-text-provenance/SKILL.md): Select hosted or local/open-weight generation paths, preserve manifests, audit text integrity, and report authorized provenance signals. It does not treat editorial rewriting as verified removal of a provider mark.
Detailed catalog content lives in the [references/](references/) subfolder:
- [philosophy-and-application.md](references/philosophy-and-application.md): The dual-use philosophy, characteristics of AI slop, application guidance for tool builders and readers, and the before/after revision example (restored pre-migration framing layer).
- [detailed-criteria.md](references/detailed-criteria.md): All 76 A3 criteria with 16-field detail and renumbering map from v3.1.0.
- [model-family-fingerprints.md](references/model-family-fingerprints.md): All A1 patterns across 8 families.
- [substance-and-depth.md](references/substance-and-depth.md): All 17 A2 sub-patterns with 5-minute editorial workflow.
- [combined-signal-fingerprints.md](references/combined-signal-fingerprints.md): All 86 B2 combos.
- [calibration-tables.md](references/calibration-tables.md): Two-axis calibration with per-family per-zone tables and ESL safe-harbor.
- [historical-patterns.md](references/historical-patterns.md): Historical and Deprecated patterns for forensic analysis of older content.
- [bibliography.md](references/bibliography.md): Consolidated bibliography with verification status.
```
