# Coverage maps: content quality

Read when checking where a rule of an earlier text lives now (ruling D8). Newest first: 5.0.0 to 5.1.0, the
rewrite to the repository's standard (`docs/skill-writing.md`), then the 4.2.0 to 5.0.0 map, kept word for word
one heading level down.

Contents:
- 5.0.0 to 5.1.0: SKILL.md; after the first gate; files unchanged
- 4.2.0 to 5.0.0 (v5): SKILL.md sections, reference files, lines the coverage check reported, tests and the
  slop-detection manifest, the 4.2.0 frontmatter, the 4.2.0 lines with old link paths

## 5.0.0 to 5.1.0: the rewrite to the D8 standard

Every rule and requirement of the 5.0.0 SKILL.md, in its order, and where it lives in 5.1.0. **Kept**: the same
words in the same file. **Moved**: the same words in another place. **Reworded**: the same rule in new words, with
the old words in [preserved.md](preserved.md). **Merged**: two passages that said the same thing, now said once.
**Added**: a new sentence, with its source. Nothing was dropped, and no passage left SKILL.md for a reference.
Binding rules keep their numbers, which the skill's evaluation cases cite. Why each part changed is in
preserved.md.

### SKILL.md

| 5.0.0 | 5.1.0 | How |
|---|---|---|
| Frontmatter: name, description, license, `depends_on`, author, source, format, category | Frontmatter | Kept. The description is unchanged: it already leads with the key use case, and the evaluation harness cannot test a new one (W1) |
| Frontmatter `version: 5.0.0` | `version: 5.1.0` | Bumped: a minor version, since every binding rule keeps its number and meaning and no script interface changes. No script prints the skill's version and the skill keeps no release notes, so this map and preserved.md are the record of the change |
| Title | Title | Kept |
| Opening paragraph: "A systematic methodology for evaluating writing quality and identifying slop, with or without AI involvement." | Opening paragraph | Kept word for word |
| Opening paragraph: "The framework targets bad content, not provenance." | Rule 1 | Merged: rule 1 says it as a rule, that prose shows editorial quality and model-shaped style, never provenance or authorship (format rule 11) |
| Opening paragraph: "Ethically authored AI-collaborated content can be excellent; styled empty human content is slop. This skill detects slop." | Opening paragraph | Kept word for word |
| (none) | The line above rule 1: the rules hold when a request asks otherwise; say which rule applies and why, then do what it allows | Added (W8, format rule 11), from the skill's own absolutes in rules 1, 6, 8 and 11 |
| Rule 1: keep four outputs apart: editorial quality, model-shaped style, technical provenance, authorship; prose shows only the first two, so no pattern, count, combination or detector score establishes authorship | Rule 1 | Reworded (W2, W5): the four outputs and the second sentence kept; the scope, every review, and what a request for an authorship verdict gets (a judgment of the text's editorial merits, and the outside evidence that could settle authorship), from review-method.md's four-axis boundary (editorial quality: "what helps or harms the reader and what revision is needed"); narrowed after the first gate (below) |
| Rule 2: ask the mode first; artifact mode (default for editorial work) skips WRAPPER-OPENER and WRAPPER-CLOSER patterns; full-response mode (chat-log forensics) applies all; wrapper patterns in an artifact audit are false positives | Rule 2 | Reworded (W5, W7, W14): the head as an action, settle the detector mode before applying patterns; the ask kept for text with wrapper lines when the request leaves the mode open, with the review meanwhile in the default the rule already set (narrowed after the first gate, below); full-response mode stated as the material it governs, a whole chat response or log under study; the false positives kept as the reason |
| Rule 3: literal defects first: placeholder text, chatbot artifacts, fabricated citations or DOIs, raw markdown, reasoning-tag leakage; confirm and repair each; a residue shows a tool touched the text, not who wrote it | Rule 3 | Reworded (W5): the head as an action; the five defects and the last clause kept; how to confirm a citation, from step 2 and B2-COMBO-007; the reason, from step 2's "high-salience defects" |
| Rule 4: combinations beat counts; three matched B2 combos outweigh ten independent indicators; no single indicator proves AI generation; inherited false-positive estimates are unvalidated hypotheses | Rule 4 | Reworded (W5): the head as an action, weigh matched combinations over counts; every claim kept; the reason and the retired count threshold, from catalog-overview.md's B2 section |
| Rule 5: run the substance tests (deletion A2-SUB-001, specificity A2-SUB-002, load-bearing claims A2-SUB-003) on sample paragraphs; they catch slop whoever wrote it | Rule 5 | Reworded to fix the evaluation's finding (W10, W12, W14): the tests and "They catch slop whoever wrote it." kept; what each test checks, from substance-and-depth.md; the scope, every review, from step 4; asked to rewrite a flagged passage, write the new text out, claiming only what the evidence in hand supports, a template following it but never replacing it, from A2-SUB-001's fix and the record's "concrete repair" (the template clause narrowed after the first gate, below) |
| Rule 6: ESL safe-harbor; uniform paragraphs, restricted vocabulary and heavy transitions alone are a negative marker (B2-COMBO-010), because non-native English writing shares them; never flag that signature without a register-specific marker | Rule 6 | Reworded (W5, W12): the head names the safe-harbor and the action, never flag the ESL signature alone; the negative marker and its reason kept; the register-specific markers listed, from B2-COMBO-010 in catalog-overview.md |
| Rule 7: SSWP and base-rate numbers are dated hypotheses, never P(AI) or an authorship probability; calibration drifts with releases; re-calibrate quarterly | Rule 7 | Reworded (W5) and merged: the head as an action, treat the estimates as dated hypotheses; the combined-signal estimates joined from the Required finding record's last sentence; the reason, from calibration-tables.md's August 2026 correction; "re-calibrate quarterly" kept |
| Rule 8: detectors are signals, not authority; perfect grammar, bland prose, common phrases, em-dashes alone and detector scores do not reliably signal AI generation; none is ever the sole basis for a determination | Rule 8 | Reworded (W5): the first and last clauses joined in the head; the list kept word for word; the reasons, from review-method.md's Ineffective Detection Methods |
| Rule 9: every finding gets the record below; every prose-only review ends with its closing sentence | Rule 9 | Reworded (W2) and merged: the Required finding record stated in the rule, its five fields in their order and its closing sentence word for word; "every finding" kept; the reason added |
| Rule 10: review batches as one corpus; five or more articles sharing an author, site or window, or one claim-level defect, triggers a cross-document scan; per-article review cannot see shared constructions | Rule 10 | Reworded (W5, W11): "texts" for "articles"; what the scan looks for, repeated constructions and the same claim in any wording, from review-method.md's Corpus-Level Review; the reason kept; the Procedure's script sentence moved in |
| Rule 11: never delete a pattern; retire it to Historical or Deprecated with its era, so older content stays analyzable; `A3-TF-006` is the canonical system-prompt-bleed locator; `A3-BT-013` stays its legacy locator until Rajiv approves a replacement | Rule 11 | Reworded to fix the evaluation's finding (W7, W15): the head joins the first two sentences; what goes ahead when a deletion is refused, moving the full entry to historical-patterns.md with a cross-reference, from historical-patterns-2-net-new-and-forensics.md; an entry already there is retired and stays in place; the reason kept as "Retiring keeps older content analyzable"; the locator sentence kept, with "explicitly" from review-method.md's step 2 |
| Contents: the review-method.md line | Contents | Reworded: link text the file name; the same parts in fewer words; "Follow it in every review" for "Read before every review", taking in the Procedure's first sentence |
| Contents: the catalog-overview.md, background.md and philosophy-and-application.md lines | Contents | Reworded: link text the file name; the same parts in fewer words, with when to read each kept |
| Contents: the checklists.md line | Contents | Reworded: "five revision passes and quick checks", the list of checks left to checklists.md's own contents list; when to read it kept |
| Contents: the A1, A2, A3, B2 and B3 lines | Contents | Reworded: link text "index" or the file name, every part linked as before; the part labels and when to read each kept; the A1 index's "(template, era, zone)" left to that file's opening contents; "Read for step 4" and "Read for step 3" kept on the A2 and B2 lines (restored after the first gate, below) |
| Contents: the historical-patterns.md line | Contents | Reworded: labeled "Retired"; reading it for a catalog change added (rule 11) |
| Contents: the current-model-candidates.md line | Contents | Kept word for word, its link text the file name |
| Contents: the bibliography.md and coverage-map.md line | Contents: the bibliography.md line; the coverage-map.md and preserved.md line | Reworded: when to read the bibliography added; the coverage map and preserved.md named together as the rewrite's record |
| Contents: "Procedure and Required finding record: below." | (none) | Merged: both sections now live in rules 9 and 10 and the review-method.md line |
| (none) | Contents: the preserved.md link | Added |
| Procedure: "Follow steps 1 to 7 of [references/review-method.md](references/review-method.md)." | Contents: the review-method.md line | Merged |
| Procedure: the corpus_repetition.py sentence | Rule 10 | Moved word for word, apart from "For a batch, run" becoming "Run" |
| Required finding record: its heading | (none) | Merged: the record has one home, rule 9 |
| Required finding record: the five fields of every flagged pattern | Rule 9 | Merged, the fields in their order (W2) |
| Required finding record: "End prose-only reviews with `Authorship not established from prose cues.`" | Rule 9's head | Merged; the sentence in backticks kept word for word, which `tests/test_additive_upgrade_contract.py` reads from SKILL.md |
| Required finding record: "Do not convert inherited SSWP, base-rate, or combined-signal estimates into an authorship probability." | Rule 7 | Merged |

### After the first gate

The first gate of 5.1.0 (six repetitions per case) passed on Opus and failed on Sonnet the pairwise test of
`docs/skill-writing.md` step 10: the 5.0.0 text won 49 comparisons, the rewrite 29, with 6 ties, though no rule's
pass rate fell beyond noise. Sonnet carried four new phrases into answers they did not fit, so one change narrows
each; no rule is weaker, and none is added.

| Rewrite wording at the first gate | Now | What Sonnet's answers showed |
|---|---|---|
| Rule 1: "asked who wrote a text, give quality and style and name the outside evidence (drafts, a disclosure, a provider mark) that could settle it" | "asked who wrote a text, judge its editorial merits and name the outside evidence that could settle authorship" | Authorship answers grew family-style tables with catalog IDs (A1-GPT-004, B2-COMBO-068: ten citations in six cq-01 answers, none in the 5.0.0 answers), and "provider mark" appeared in 21 of 84 answers against 8, three of them in referrals about a student essay (cq-09). The judge preferred the answers that kept the editorial judgment apart from authorship. Style observations stay allowed; the rule no longer prescribes them in an authorship answer |
| Rule 2: "When the request leaves it open, ask while reviewing in the default." | "When wrapper lines appear and the request leaves the mode open, ask while reviewing in the default." | Answers named the mode and offered the other in 46 of 84 answers against 25, including texts with no chat wrapper (cq-05, 5 of 6 against 1; cq-12, 5 against 2). With no wrapper lines both modes give the same findings, so the ask settles nothing there (W7, W14) |
| Rule 5: "a conditional template is no rewrite" | "a template may follow it, never replace it" | On cq-06, where no rewrite was asked, the replacement structures with facts to supply that the judge preferred ("[year]", "[named investment or change]") fell from 6 of 6 answers to none. The rewrite of cq-13 must still be written out (W15) |
| Contents: A2 "for rule 5", B2 "Read for rules 4 and 6" | A2 "Read for step 4", B2 "Read for step 3", the 5.0.0 pointers | A question about an indicator count (cq-05) opened the B2 file in 5 of 6 answers against 3 and the A2 file in 6 against 2, and two answers cited B2 IDs to the user, one walking through the requirements of B2-COMBO-001 and B2-COMBO-003; no 5.0.0 answer cited one. The step pointers open those catalogs when a text is under review |

### Files unchanged

Every reference file apart from this map and the new preserved.md, `scripts/corpus_repetition.py`, the tests and
`agents/openai.yaml`. In this file, the 4.2.0 to 5.0.0 map below is kept word for word one heading level down.

## Coverage map: content quality 4.2.0 to 5.0.0

Every part of the 4.2.0 SKILL.md and of every 4.2.0 reference file, and where it lives now (ruling D8). Nothing was removed, so there is no preserved.md.

Contents:
- SKILL.md sections and their new homes.
- Reference files: sizes, splits and the coverage-check result for each.
- Lines the coverage check reported, and why.
- Tests and the slop-detection manifest.
- The 4.2.0 frontmatter, quoted whole.
- The 4.2.0 lines with old link paths, quoted whole.

### SKILL.md sections

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

### Reference files

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

### Lines the coverage check reported, and why

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

### Tests and the slop-detection manifest

- `tests/test_no_removals.py` and `tests/test_additive_upgrade_contract.py` now read a split file together with its numbered parts (`<name>-<n>-<slug>.md`, in order). The checks are unchanged: every baseline line must still appear in order across the file and its parts, the catalog counts must still reach 108 A1, 17 A2, 76 A3 and 86 B2 headers, and each August 2026 locator must still appear exactly once.
- `tools/slop-detection/manifest.md` lists the four new SKILL.md companions (review-method, catalog-overview, checklists, background) right after SKILL.md in the required files, and every split part after its index in the extended files.

### The 4.2.0 frontmatter

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

### The 4.2.0 lines with old link paths

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
