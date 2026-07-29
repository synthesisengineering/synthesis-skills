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
  version: 4.0.0
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Content Quality

A systematic methodology for evaluating writing quality and identifying slop, with or without AI involvement. The framework targets bad content, not provenance. Ethically authored AI-collaborated content can be excellent; styled empty human content is slop. This skill detects slop.

The methodology is durable. The catalog refreshes as model behavior shifts and as new patterns emerge in production output. v4.0 adds model-family fingerprinting across eight families, a substance and depth section grounded in the Frankfurt-Pennycook-Hicks-Humphries-Slater framework, a cross-cutting causal-and-calibration layer, and zone-conditional detection. The compounding-archive principle means patterns are never deleted: when newer model versions train a pattern out, the catalog tags it Historical and retains it for forensic analysis of older published content.

## Where this skill fits in the writing-quality family

This skill catches AI-generation patterns and substance failures specifically. Three sibling skills handle adjacent concerns:

- **`synthesis-content-quality`** (this skill, v4.0): AI/LLM-generation patterns, substance and depth, calibration. Refreshes with new model releases.
- [`synthesis-writing-pitfalls`](../synthesis-writing-pitfalls/SKILL.md): Universal human-source bad-writing patterns (cringe, throat-clearing, caveat overload, cliché reliance). Stable across decades.
- [`synthesis-writing-craft`](../synthesis-writing-craft/SKILL.md): Positive principles from the writing-craft tradition.

Use all three together for a comprehensive quality pass. Use this one alone when the focus is specifically slop in AI-collaborated or AI-generated content.

## When to Use This Skill

- Reviewing AI-assisted drafts before publication.
- Editing content that may contain unrevised AI output.
- Building or calibrating AI content detection tools.
- Training writers or editors on content quality standards.
- Performing editorial review of submitted content.
- Forensic analysis of older published content for AI authorship signals (use Historical and Deprecated era patterns).

## Core Philosophy

Slop is the enemy, not just AI. The tool catches AI-generation patterns specifically (by model family, with empirical anchors), and also catches slop in human-written content. AI-assisted content creation is legitimate and valuable. The distinction that matters is not "did AI help write this" but "is this worth publishing." Both questions get answered, on separate axes.

Three categories of AI-collaborated content:

- **Unedited AI output.** Raw generation copied and published without human refinement. Often fails substance and depth tests. The pattern catalog catches this efficiently.
- **AI-augmented work.** Human expertise enhanced by AI capabilities with proper oversight. Passes substance tests when the human contribution is real.
- **Systematic human-AI collaboration.** Methodical integration where humans maintain judgment, add genuine expertise, and ensure quality. Indistinguishable from skilled human writing on substance; sometimes carries minor stylistic AI fingerprints from the final draft pass.

The goal is quality assessment. Detection requires pattern recognition across multiple indicators. No single indicator proves AI generation definitively, and many AI-collaborated pieces are excellent content.

## Zones and Detector Modes

The LLM produces a single continuous token stream. It does not structurally separate "conversational wrapper" from "produced artifact." But RLHF training systematically produces a three-zone shape: warm opener, substantive body, warm closer. Patterns concentrate in different zones at different rates.

### Three zones in LLM responses

- **WRAPPER-OPENER (first 1-3 sentences).** Sycophantic acknowledgments (Claude's "You're absolutely right!", GPT's "Great question!"), polite framings ("Let me walk you through this"), warm acknowledgments ("Thank you for raising this").
- **BODY-PERSISTENT (substantive content the user requested).** Em-dash density, saturated vocabulary, balanced two-handed hedging, bulleted bolded lead-ins, mid-section recaps.
- **WRAPPER-CLOSER (final 1-3 sentences).** "I hope this helps!", "Is there anything else I can help with?", "Feel free to ask if you have more questions."

Some patterns are HYBRID (appear in both zones at meaningful rates: em-dashes, focal vocabulary, uniform paragraph length). Some are MID-BODY-INSERT (safety-hedge inserts that appear mid-paragraph, not at openers or closers).

### Detector mode selection

The detector operates in two modes depending on what the user is auditing:

- **Artifact mode (default for editorial use).** Apply BODY-PERSISTENT, HYBRID, and MID-BODY-INSERT patterns. Skip WRAPPER-OPENER and WRAPPER-CLOSER patterns. False-positive rate stays low when the user is auditing only the published artifact.
- **Full-response mode (for forensic chat-log analysis).** Apply all patterns including wrapper-zone patterns.

Newsroom editors reviewing AI-assisted submissions almost always work in artifact mode: writers copy-paste the article, not the chat transcript that produced it. Forensic chat-log auditors and researchers work in full-response mode.

Each pattern in the catalog carries an explicit zone tag. The detector workflow should ask the user upfront: "Are you auditing just the produced content, or the full LLM response including conversational framing?" Then apply the appropriate pattern subset.

## The Pattern Catalog

The full catalog has approximately 180 patterns organized across four sections. Each pattern carries the 14-field template plus era status (Active / Declining / Historical / Deprecated) and zone tag. Full per-pattern detail lives in [references/](references/) subfiles linked below.

### Section A1: Model-Family Fingerprinting

Patterns specific to one LLM family. Top-tier coverage produced 38 patterns across Claude, GPT, and Gemini. Second-tier coverage added patterns across Llama, Grok, DeepSeek, Mistral, and Qwen. Total approximately 100 active patterns plus historical entries for retired family-era markers.

| Family | Headline pattern | Active pattern count |
|--------|-------------------|---------------------:|
| Anthropic Claude (A1.1) | `A1-CLAUDE-003` "You're absolutely right!" agent reflex (GitHub anthropics/claude-code#3382 documents the pattern qualitatively; the count claim in some research is not in the cited issue) | 28 |
| OpenAI GPT (A1.2) | `A1-GPT-001` "Delve" saturated-vocabulary cluster (Kobak et al. arxiv 2406.07016, 13.5 percent of 2024 biomedical abstracts) | 18 |
| Google Gemini (A1.3) | `A1-GEMINI-001` Plain-text markdown leakage (near-deterministic in non-rendering channels) | 13 |
| Meta Llama (A1.4) | `A1-LLAMA-001` Near-zero em-dash baseline (useful as a negative marker) | 10 |
| xAI Grok (A1.5) | `A1-GROK-001` Colloquial internet-native register | 10 |
| DeepSeek (A1.6) | `A1-DEEPSEEK-001` `<think>` tag reasoning-trace leakage in R1 outputs | 10 |
| Mistral (A1.7) | `A1-MISTRAL-001` French-corpus syntax influence | 9 |
| Qwen (A1.8) | `A1-QWEN-001` CJK punctuation slips (Unicode-detectable) | 10 |

Full per-pattern detail: [references/model-family-fingerprints.md](references/model-family-fingerprints.md).

Historical entries for retired family-era markers (Bard "As a large language model trained by..." preamble, GPT-3.5 "As an AI language model" preamble, GPT-3.5 "Here's the thing" intensifier, pre-instruction-tuning GPT-3, early Llama 1 / 2, early Grok 1, early DeepSeek V1 / V2, early Mistral 7B / Mixtral, early Qwen 1 / 2) live in [references/historical-patterns.md](references/historical-patterns.md). These patterns are largely trained out of current frontier models but remain valuable for forensic analysis of older published content per the compounding-archive principle.

### Section A2: Substance and Depth Detection

Promoted from a single sub-criterion in v3.1.0 (Superficial Depth) to a full top-level section in v4.0. 17 sub-patterns grounded in:

- Frankfurt, *On Bullshit* (2005)
- Hicks, Humphries, Slater, "ChatGPT is Bullshit" (Ethics and Information Technology 26:38, 2024)
- Pennycook et al., Bullshit Receptivity Scale (Judgment and Decision Making 10(6), 2015)
- Sourati et al. 2025 homogenization survey
- Padmakumar and He (2024) on output diversity loss

The 17 sub-patterns: `A2-SUB-001` The deletion test, `A2-SUB-002` The specificity test, `A2-SUB-003` Load-bearing claim count, `A2-SUB-004` Novelty signal, `A2-SUB-005` Insight-to-word ratio, `A2-SUB-006` The any-company test, `A2-SUB-007` Hedging as substance evasion, `A2-SUB-008` Survey-without-claim pattern, `A2-SUB-009` Generic insight, `A2-SUB-010` Both-sides-without-position, `A2-SUB-011` Pseudo-profundity, `A2-SUB-012` Conclusion-shaped paragraphs that do not conclude, `A2-SUB-013` Frictionless-transition padding, plus four additional from cross-LLM contributions.

The most useful editorial capability of v4.0 is the **A2-SUB-001 deletion test**: if a sentence or paragraph can be removed from the piece without losing any claim, evidence, or transition, it is Frankfurt-style bullshit. The any-company test (`A2-SUB-006`) and load-bearing claim count (`A2-SUB-003`) round out a 5-minute editorial pass that catches most slop regardless of authorship.

Full detail and the five-minute editorial workflow: [references/substance-and-depth.md](references/substance-and-depth.md). Zone tag: BODY-PERSISTENT for all A2 sub-patterns (substance is about what the artifact says).

### Section A3: Refreshed Pattern Catalog (the 76 criteria)

The v3.1.0 catalog of 42 criteria has been refreshed with consolidated tier-shift recommendations from the unified research and supplemented with 34 net-new criteria. Total 76 criteria, renumbered thematically (no v3.1.0 number preservation per the no-backward-compat principle). Two-letter prefixes group by theme:

- **A3-LT (Language and Tone), 15 criteria.** Includes `A3-LT-001` Undue emphasis on importance and symbolism, `A3-LT-002` Promotional and travel-brochure language, `A3-LT-003` Editorial commentary and meta-analysis, `A3-LT-004` Superficial analysis with participial phrases, `A3-LT-005` Negative parallelism, `A3-LT-006` Overuse of transition words, `A3-LT-007` Section-ending summaries, `A3-LT-008` The rule of three, `A3-LT-009` Passive voice and "has been described as", `A3-LT-010` Uniform sentence and paragraph length, plus 5 net-new entries.
- **A3-SS (Style and Structural), 9 criteria.** Includes `A3-SS-001` Excessive em-dashes (tier shift: per-family weighting; HIGH for Claude and pre-GPT-5.1 ChatGPT, LOW for current GPT-5.1 and Llama), `A3-SS-002` Bulleted lists with bolded lead-ins, `A3-SS-003` Excessive bolding and formatting, `A3-SS-004` Emoji usage in inappropriate contexts, `A3-SS-005` Markdown formatting mixed with standard text, `A3-SS-006` Curly vs. straight quotes, `A3-SS-007` Title case in headers, plus 2 net-new.
- **A3-TF (Technical and Formatting), 7 criteria.** Placeholder text, chatbot artifacts, broken or fabricated links, citation abnormalities, suspiciously long edit summaries, plus 2 net-new.
- **A3-CS (Citation and Sourcing), 6 criteria.** Hallucinated citations (PROMOTE to HIGH), vague attribution (PROMOTE to HIGH), plus 4 net-new including ChatGPT's retrieval-era criteria (source theater, calibration mismatch, synthetic-source contamination).
- **A3-CX (Context-Specific), 5 criteria.** Industry slop, lack of personal detail, superficial depth (formally promoted to A2 section but stub retained for compatibility), plus 2 net-new.
- **A3-HD (Hyperbolic and Dramatic), 7 criteria.** Hyperbolic subheadings, dramatic fragment construction, borrowed canonical examples, plus 4 net-new including the "journey" metaphor cluster.
- **A3-CE (Confidentiality and Exposure), 2 criteria.** Scenario fingerprinting, operational decisions as teaching material.
- **A3-BT (Behavioral and Tonal), 12 criteria.** Saturated AI vocabulary (PROMOTE to HIGH per Kobak et al. and Juzek and Ward), exhausted metaphors, unprompted moral cadence, concierge tone (DEMOTE to MED post April 2025 OpenAI sycophancy rollback for GPT; remains HIGH for Claude), plus 8 net-new including reasoning-trace token leakage, sycophancy drift, partial-refusal stems.
- **A3-FA (Frame and Audience), 8 criteria.** Insider context collapse, plus 7 net-new including ChatGPT and Grok retrieval-era and structural-uniformity entries.
- **A3-SR (Social-Register), 5 criteria.** Imported spec language uppercase, article structure in social posts, third-person narration of first-person experience, lack of closing engagement, em-dashes in social posts.

Full per-criterion detail with all 16 fields (14 base + era + zone): [references/detailed-criteria.md](references/detailed-criteria.md), which also includes a renumbering map from v3.1.0 numbers to the new IDs.

## The Cross-Cutting Layer

v4.0 adds three cross-cutting fields applied to every pattern in the catalog. This is what transforms the catalog from a checklist into a diagnostic tool.

### B1: Causal Layer

Each pattern is annotated with its likely origin in a twelve-code taxonomy:

- `RHF` RLHF reward shaping
- `TDS-acad` / `TDS-corp` / `TDS-soc` / `TDS-instr` / `TDS-news` Training data skew (academic, corporate, social, instructional, news)
- `AST` Alignment / safety tuning
- `RAB` Refusal-avoidance behavior
- `HO` Helpfulness optimization
- `SPA` System-prompt artifacts
- `TAE` Tokenizer / architecture effects
- `PWE` Product-wrapper effects

Knowing the cause predicts the pattern's evolution: patterns rooted in RLHF reward shaping may be trained out next generation; patterns rooted in tokenizer effects persist as long as the architecture does.

Full per-criterion attribution: [references/calibration-tables.md](references/calibration-tables.md) (causal column).

### B2: Combined-Signal Fingerprints

The v3.1.0 heuristic ("5+ medium-confidence indicators equals very likely AI") is replaced with 86 specific combinations where co-occurrence is a stronger signal than count. Combined-signal detection drops false-positive rates by an order of magnitude versus count-based detection.

High-yield combos to know:

- **`B2-COMBO-001` ChatGPT 4o tell.** Saturated vocab + exhausted metaphors + section-ending summary. False-positive rate below 1 percent at full co-occurrence.
- **`B2-COMBO-003` Claude.ai default.** Em-dashes (high density) + bulleted bolded lead-ins + uniform paragraph length. False-positive rate below 0.5 percent. Strongest single-family fingerprint as of 2026-05.
- **`B2-COMBO-007` Fake-expertise stack.** Vague attribution + hallucinated citation + generic insight. Definitive when the citation can be verified absent.
- **`B2-COMBO-010` ESL false-positive trap (NEGATIVE marker).** Uniform paragraph length + restricted vocabulary + heavy transitions. The cornerstone signature for AI is also the cornerstone signature for non-native English writing per Liang et al. 2023. This combination is a **NEGATIVE marker**: do not flag as AI unless combined with at least one register-specific AI marker (saturated vocabulary cluster, em-dash density, system-prompt artifact, chatbot reflex).

Full catalog of all 86 combos: [references/combined-signal-fingerprints.md](references/combined-signal-fingerprints.md).

### B3: Two-Axis Calibration

Each criterion is split into two axes:

- **SSWP (Signal Strength When Present).** A 0.0 to 1.0 score representing the conditional probability that text containing the pattern is AI-generated. SSWP above 0.85 is "smoking gun"; 0.6 to 0.85 is "strong"; 0.4 to 0.6 is "moderate"; below 0.4 is "ambient."
- **BR (Base Rate).** Per-family percentage. Split for zone-conditional patterns into BR-artifact-body and BR-full-response.

The split reveals that some widely cited markers (em-dash density) have very high signal strength but plummeting base rate in newer GPT models, while others (uniform paragraph length) have moderate signal strength but very high base rate that overlaps with ESL writing.

**ESL safe-harbor (structural requirement).** Per Liang et al. arxiv 2304.02819 (verified), GPT detectors misclassify a large fraction of non-native English writing as AI-generated. Any detection that triggers the cornerstone signature must be combined with at least one register-specific AI marker. Calibration discipline: hard-negative-mine against TOEFL-style writing.

**Quarterly re-calibration.** Per the GPT-5.1 anti-em-dash personalization that shifted Claude vs. ChatGPT BR rankings by 30+ points in a single release, calibration drifts. Re-calibrate every quarter.

Full per-family per-criterion table: [references/calibration-tables.md](references/calibration-tables.md).

## Confidence-Based Evaluation Process

### Step 1: Select detector mode

Ask: artifact-only or full-response? Apply the corresponding pattern subset (zone tags filter the catalog).

### Step 2: Check for smoking-gun indicators (SSWP above 0.85)

- Placeholder text or chatbot artifacts (A3-TF).
- Hallucinated citations or fabricated DOIs (A3-CS).
- Raw markdown formatting in plain-text channels.
- Family-specific signatures: `<think>` tag leakage (DeepSeek-R1), CJK punctuation slips (Qwen), language-mixing (DeepSeek).
- System-prompt artifact bleed (catalog entry A3-BT-013).

If any present: very likely unedited AI output.

### Step 3: Apply combined-signal fingerprints

Check for the highest-yield B2 combos given the genre. For analytical / explanatory prose, check `B2-COMBO-001` (ChatGPT 4o tell), `B2-COMBO-003` (Claude.ai default), `B2-COMBO-007` (fake-expertise stack). For business / marketing, add `B2-COMBO-004` (marketing copy AI signature) and `B2-COMBO-016` (consulting register).

Combined-signal detection beats count-based detection: three matched combos is stronger than ten matched independent indicators.

### Step 4: Apply substance and depth tests (A2)

Run the deletion test (`A2-SUB-001`), the specificity test (`A2-SUB-002`), and the load-bearing claim count (`A2-SUB-003`) on a sample of paragraphs. This step catches slop regardless of authorship; it is the most useful single check for newsroom editors.

### Step 5: Check ESL safe-harbor

If the piece's signature is uniform paragraphs + restricted vocabulary + heavy transitions, check whether any register-specific AI marker is also present. If not, the piece is likely non-native English human writing; do NOT flag as AI.

### Step 6: Assess overall pattern

Combine the per-step signals into a confidence assessment. Per-family attribution where possible.

### Step 7: Consider context

- Is this from an established author with a portfolio?
- Does other work by this author show similar patterns?
- Is the publication known for quality control?
- Was AI assistance disclosed? If so, are the patterns consistent with declared methodology?

## What This Framework Does NOT Catch On Its Own

The catalog detects slop patterns (saturated vocabulary, hyperbolic patterns, mechanical transitions, hallucinated citations), substance failures (deletion-test failure, generic insight, both-sides without commit), human-shaped generic writing (lack of personal detail), and frame-level insider collapse (insider context collapse).

It does not, on its own, catch:

- **Upstream framing failures.** Articles where the writer never asked the audience question and the draft inherits the source material's frame. Prevention is upstream: [`synthesis-reader-briefing`](../synthesis-reader-briefing/SKILL.md). Criterion A3-FA-001 detects the failure in finished drafts; the briefing prevents it before drafting begins.
- **Errors of omission relative to the briefing.** The article passes every quality check and still does not deliver what the briefing promised. The Insight Quality lens in [`synthesis-article-writing`](../synthesis-article-writing/SKILL.md) is the closer fit.
- **Voice mismatch.** The article is technically correct but does not sound like the author. Use [`synthesis-voice-profiler`](../synthesis-voice-profiler/SKILL.md).
- **Strategic positioning errors.** A correct article in the wrong publication on the wrong topic at the wrong moment. Use [`synthesis-content-framing`](../synthesis-content-framing/SKILL.md).
- **Fact-checking gaps.** Use the companion skill [`synthesis-fact-checking`](../synthesis-fact-checking/SKILL.md) v2.0 for nested attribution, paraphrase drift, composite quotes, position-shifting, source-translation drift, URL rot vs hallucination, AI-generated synthetic sources, citation laundering chains, and tool-specific hallucination patterns.

## Ineffective Detection Methods

These do NOT reliably signal AI generation:

- **Perfect grammar.** Skilled humans and professional editors produce polished prose.
- **"Bland" prose.** Corporate communications from humans can sound formulaic.
- **Common phrases.** "Rich cultural heritage" exists in human writing too.
- **Em dashes alone.** Professional writers use them frequently. The signal is density combined with other markers, weighted per family (HIGH for Claude, LOW for Llama, declining for GPT-5.1+).
- **Technical terminology.** Experts naturally use jargon.
- **Watermarking detection.** No frontier model uses reliable text watermarking as of 2026-05. Claims of watermark-based detection are unreliable.
- **AI detectors as authority.** Pangram, GPTZero, Originality, Copyleaks, Turnitin all produce useful signals but should never be the sole basis for a determination. The Liang ESL bias finding applies to most commercial detectors.

## Systematic Revision Process for Creators

When using AI to assist content creation, revise through these five passes:

1. **Eliminate formulaic patterns.** Vary sentence and paragraph length. Reduce mechanical rule of three. Remove promotional language and editorial commentary. Replace generic descriptions with specifics. Cut wrapper-zone language (sycophantic openers, concierge closers) if it leaked into the artifact.

2. **Apply the A2 substance tests.** Run the deletion test on every paragraph: if removing it changes nothing, delete it. Apply the any-company test to business content. Count load-bearing claims; aim for 3+ per 100 words in substantive prose.

3. **Verify and enhance sourcing.** Check all citations exist and are relevant (use synthesis-fact-checking C1-URLROT-001 and C1-SYNTH-001 protocols). Add specific attribution. Include original research or first-hand sources.

4. **Inject personality and voice.** Use natural transitions. Vary rhetorical structures. Include humor or perspective where appropriate. Let imperfections remain if they sound natural. Apply zone awareness: strip wrapper-zone patterns ("You're absolutely right", "I hope this helps") even if they read warmly.

5. **Apply the Human Touch test.** Would a reader recognize this as distinctly yours? Does it include knowledge only you would have? Does it sound like how you actually write? Would anyone else write it exactly this way? Have you added genuine value beyond what AI provided?

## Quick-Reference Checklist

### High-Risk Phrases (any context)

- "stands as a testament to," "plays a vital/significant role"
- "rich cultural heritage," "breathtaking," "nestled in the heart of"
- "it's important to note," "it is worth mentioning," "one cannot overlook"
- "not only... but also," "it's not just X, it's Y"
- "Moreover," "Furthermore," "Additionally," "Nevertheless" (especially in clusters)
- "In summary," "In conclusion," "Overall," "In essence"

### High-Risk Vocabulary (flag when 3+ cluster in a single piece)

- delve, tapestry, nuanced, robust, foster, beacon, catalyst
- synergy, pivotal, overarching, multifaceted, landscape (abstract)
- leverage (verb), streamline, spearhead, underscore, harness
- intricate, navigate the complexities of, in the realm of

### Exhausted Metaphor Phrases

- "navigating the complex landscape of..."
- "viewed through the lens of..."
- "a symphony of moving parts"
- "at the intersection of X and Y"
- "the fabric of..." / "a tapestry of..."
- "unpacking the layers of..."
- "Ultimately, finding a balance between X and Y is crucial"

### High-Risk Subheading Patterns

- "The X that changed everything"
- "A game-changing approach to..."
- "The revolutionary/transformative..."
- "Why X will never be the same"
- "The surprising truth about..."
- "What nobody tells you about..."

### Highest-Yield Combined Signals (per family)

When seen together, these combinations indicate the named family with low false-positive rate:

- **Claude family:** em-dash density + bolded lead-ins + uniform paragraphs (B2-COMBO-003).
- **GPT-4o:** saturated vocab + exhausted metaphor + section-ending summary (B2-COMBO-001).
- **Gemini:** plain-text markdown leakage + vague attribution + "cool/neat/unique" register (B2-COMBO-012 plus GEMINI signatures).
- **GPT-5.1 stripped:** zero em-dashes + low concierge tone + still-present focal vocabulary + rule-of-three + uniform paragraphs (B2-COMBO-025).

### A2 Substance Quick-Check (5 minutes)

Run on three sample paragraphs from any piece:

- [ ] **Deletion test** (`A2-SUB-001`): could this paragraph be removed without losing claim, evidence, or transition?
- [ ] **Specificity test** (`A2-SUB-002`): would this sentence apply equally to any subject in its genre?
- [ ] **Any-company test** (`A2-SUB-006`): if this is business content, would this paragraph apply equally to any company?
- [ ] **Load-bearing claim count** (`A2-SUB-003`): how many sentences carry claims the rest of the piece depends on?
- [ ] **Pseudo-profundity check** (`A2-SUB-011`): does any sentence sound deep but say nothing on inspection?

### Stranger-Read Patterns (Before Publishing)

Threshold calibrates by genre per the reader briefing: strict for technical or teaching content, looser for personal narrative.

- [ ] Tool or project name appears without inline definition on first use
- [ ] Internal abstraction used without prior introduction
- [ ] Version number appears in prose
- [ ] Code identifier in prose without descriptive context
- [ ] Reference to internal events without explanation
- [ ] Internal directory or path used as if reader knows the project layout

See criterion `A3-FA-001` (insider context collapse) and [`synthesis-reader-briefing`](../synthesis-reader-briefing/SKILL.md).

### Anonymization Checks (Before Publishing)

- [ ] Outsider test: could a stranger narrow this to a small set of companies?
- [ ] Insider test: does this confirm something an insider suspected?
- [ ] Adversary test: could a reporter use this as evidence?
- [ ] Irony test: does publishing this undermine what the example describes protecting?
- [ ] Are specific numbers (14 components, 6 engineers) identifying?
- [ ] Are stakeholder dynamics identifying?
- [ ] Are vocabulary choices (exact terminology changes) identifying?

### ESL Safe-Harbor Check

Before flagging a piece as AI-generated based on uniform-paragraphs + restricted-vocab + heavy-transitions, verify at least one of these register-specific AI markers is also present:

- [ ] Saturated AI vocabulary cluster (3+ from the focal-word list)
- [ ] Em-dash density (per-family calibrated)
- [ ] System-prompt artifact bleed
- [ ] Chatbot reflex (sycophancy opener, concierge closer)
- [ ] Hallucinated citation or fabricated DOI

If none, the piece is likely non-native English human writing. Do not flag.

### The Human Touch Test

Before publishing AI-assisted content:

1. Would a reader recognize this as distinctly mine?
2. Does it include knowledge only I would have?
3. Does it sound like how I actually write?
4. Would anyone else write it exactly this way?
5. Have I added genuine value beyond what AI provided?

If you cannot answer yes to most of these, revise further.

## Related Skills

This skill is the AI-pattern-and-substance arm of the writing-quality family:

- [`synthesis-writing-pitfalls`](../synthesis-writing-pitfalls/SKILL.md): Universal human-source bad-writing patterns (cringe, throat-clearing, caveat overload, sentence-level weakness, cliché reliance, stilted formality).
- [`synthesis-writing-craft`](../synthesis-writing-craft/SKILL.md): Positive writing principles from the writing-craft tradition.
- [`synthesis-reader-briefing`](../synthesis-reader-briefing/SKILL.md): Pre-writing audience analysis (prevents insider context collapse upstream).
- [`synthesis-article-writing`](../synthesis-article-writing/SKILL.md): End-to-end article workflow with quality gates.
- [`synthesis-article-refresh`](../synthesis-article-refresh/SKILL.md): Refresh and revitalize older articles.
- [`synthesis-voice-profiler`](../synthesis-voice-profiler/SKILL.md): Generate a structured voice profile.
- [`synthesis-fact-checking`](../synthesis-fact-checking/SKILL.md) v2.0: Companion skill for citation, quote, and source verification with per-family hallucination signatures.
- [`synthesis-clean-text`](../synthesis-clean-text/SKILL.md): Remove watermarks and statistical fingerprints from generated text.

## References

Detailed catalog content lives in the [references/](references/) subfolder:

- [detailed-criteria.md](references/detailed-criteria.md): All 76 A3 criteria with 16-field detail and renumbering map from v3.1.0.
- [model-family-fingerprints.md](references/model-family-fingerprints.md): All A1 patterns across 8 families.
- [substance-and-depth.md](references/substance-and-depth.md): All 17 A2 sub-patterns with 5-minute editorial workflow.
- [combined-signal-fingerprints.md](references/combined-signal-fingerprints.md): All 86 B2 combos.
- [calibration-tables.md](references/calibration-tables.md): Two-axis calibration with per-family per-zone tables and ESL safe-harbor.
- [historical-patterns.md](references/historical-patterns.md): Historical and Deprecated patterns for forensic analysis of older content.
- [bibliography.md](references/bibliography.md): Consolidated bibliography with verification status.

---

Part of the [synthesis writing](https://synthesiswriting.org) craft. The methodology is durable. The catalog refreshes as model behavior shifts. Newsrooms and editorial workflows are the audience this skill serves.
