# Detailed Criteria Reference (v4.0)

> **Pattern catalog (current as of 2026-05).**
>
> AI-generation patterns shift as new models are released. This catalog reflects observable patterns in production AI output as of the date above and is updated as model behavior evolves. The methodology in `SKILL.md` is the durable part; the specific patterns below grow over time as new ones become observable.

This file refreshes and expands the 42 criteria from synthesis-content-quality v3.1.0 against the unified bucket A merged from eight independent deep-research deliverables (Manus AI, Perplexity, Grok, ChatGPT, Gemini, DeepSeek, the Claude index, and the Opus-4.7 expansion). It adopts a thematic two-letter ID scheme (no backward compatibility to v3.1.0 numbering), slots in 20+ net-new criteria from A3.3 alongside their thematic relatives, and adds two metadata fields to every entry: era status (Active, Declining, Historical, Deprecated) and zone tag (WRAPPER-OPENER, WRAPPER-CLOSER, BODY-PERSISTENT, HYBRID, MID-BODY-INSERT).

For the high-level methodology, see [SKILL.md](../SKILL.md). For per-family pattern detail beyond v3.1.0's 42, see [references/model-family-fingerprints.md](model-family-fingerprints.md). For the cross-cutting causal layer, combined-signal fingerprints, and calibration tables, see [references/combined-signal-fingerprints.md](combined-signal-fingerprints.md) and [references/calibration-tables.md](calibration-tables.md).

---

## Conventions

### Two-letter section prefix scheme

- `A3-LT-NNN` Language and Tone
- `A3-SS-NNN` Style and Structural
- `A3-TF-NNN` Technical and Formatting
- `A3-CS-NNN` Citation and Sourcing
- `A3-CX-NNN` Context-Specific
- `A3-HD-NNN` Hyperbolic and Dramatic
- `A3-CE-NNN` Confidentiality and Exposure
- `A3-BT-NNN` Behavioral and Tonal
- `A3-FA-NNN` Frame and Audience
- `A3-SR-NNN` Social-register

The `A3-` namespace prefix ties every entry back to the source bucket (A3 of unified bucket A). Within each thematic prefix, numbering reflects insertion order, with net-new entries (from A3.3 of the unified bucket) interleaved thematically rather than appended at the end.

### 16-field per-entry template

Each entry carries:

1. **ID and Name.**
2. **Description.** What the pattern is, with cross-references to siblings.
3. **Concrete examples.** Minimum 3.
4. **Location and register.** Where the pattern appears in artifact prose, which registers favor it.
5. **Model attribution (ranked with confidence).** Per-family probability and rank.
6. **Time evolution.** Versioned arc of the pattern across model generations.
7. **Sources.** Minimum 2 (academic, practitioner, or detector-vendor evidence).
8. **Signal strength tier.** HIGH, MEDIUM, or LOW, with combination-weighted notes.
9. **Base rate.** Per-family where known, with ESL safe-harbor flag when relevant.
10. **Causal hypothesis (ranked, from B1 taxonomy).** RLHF reward shaping, training data skew, alignment safety tuning, helpfulness optimization, system prompt artifacts, tokenizer effects, training-data corpus selection, architectural attention effects, prompt-following over-adherence, product wrapper personalization, knowledge cutoff staleness, generative defaults under benchmark pressure.
11. **Detection difficulty.** Easy (grep), Medium (parse), Hard (distribution analysis or reader briefing).
12. **False positive risk.** Low, Moderate, High, with named exceptions.
13. **Fix or remediation.** Concrete editorial action.
14. **Era status.** Active, Declining, Historical, Deprecated (per the compounding-archive principle).
15. **Zone tag.** WRAPPER-OPENER, WRAPPER-CLOSER, BODY-PERSISTENT, HYBRID, MID-BODY-INSERT (per design-considerations.md).
16. **Notes on disagreement.** Where LLM contributors disagreed on tier or attribution, the divergence is preserved with named attribution.

### Em-dash constraint

This file contains zero em-dashes (the U+2014 character). Per criteria A3-SS-001 and A3-SR-005 (the catalog this file documents), em-dash density is a HIGH-signal AI marker for the Claude family and pre-GPT-5.1 ChatGPT. A reference for a catalog cannot itself produce the pattern it flags. Commas, parentheses, colons, and sentence breaks substitute throughout.

---

## Renumbering map (v3.1.0 to v4.0)

The renumbering preserves thematic continuity with v3.1.0 but adopts the two-letter prefix scheme so that net-new criteria can be slotted thematically without forcing a sequential number bump.

| v3.1.0 # | v3.1.0 name | v4.0 ID | v4.0 name | Tier shift |
|---|---|---|---|---|
| 1 | Undue Emphasis on Importance and Symbolism | A3-LT-001 | Undue Emphasis on Importance and Symbolism | KEEP (MED) |
| 2 | Promotional and Travel Brochure Language | A3-LT-002 | Promotional and Travel Brochure Language | PROMOTE (MED to HIGH) |
| 3 | Editorial Commentary and Meta-Analysis | A3-LT-003 | Editorial Commentary and Meta-Analysis | REVISE (MED) |
| 4 | Superficial Analysis with Participial Phrases | A3-LT-004 | Superficial Analysis with Participial Phrases | PROMOTE (MED to HIGH) |
| 5 | Negative Parallelism | A3-LT-005 | Negative Parallelism | KEEP with note (MED) |
| 6 | Overuse of Transition Words | A3-LT-006 | Overuse of Transition Words and Formal Conjunctions | KEEP with combination weighting (LOW base, MED clustered) |
| 7 | Section-Ending Summaries | A3-LT-007 | Section-Ending Summaries | KEEP (MED) |
| 8 | The Rule of Three | A3-LT-008 | The Rule of Three | KEEP (MED) |
| 9 | Passive Voice and "Has Been Described As" | A3-LT-009 | Vague Evidential Passive Voice | REVISE (LOW) |
| 10 | Uniform Sentence and Paragraph Length | A3-LT-010 | Uniform Sentence and Paragraph Length | PROMOTE (MED to HIGH) with ESL safe-harbor |
| 11 | Excessive Em Dashes | A3-SS-001 | Excessive Em Dashes | PROMOTE (LOW to HIGH for Claude / pre-GPT-5.1 ChatGPT; LOW for Llama / GPT-5.1+) |
| 12 | Bulleted Lists with Bolded Lead-ins | A3-SS-002 | Bulleted Lists with Bolded Lead-ins | PROMOTE (MED to HIGH) |
| 13 | Excessive Bolding and Formatting | A3-SS-003 | Excessive Bolding and Formatting | PROMOTE (LOW to MED) with version note |
| 14 | Emoji Usage in Inappropriate Contexts | A3-SS-004 | Emoji Usage in Inappropriate Contexts | REVISE (LOW) |
| 15 | Markdown Formatting Mixed with Standard Text | A3-SS-005 | Markdown Formatting Mixed with Standard Text | KEEP (HIGH) |
| 16 | Curly vs. Straight Quotes | A3-SS-006 | Curly vs. Straight Quotes | DEPRECATE (retained for archive) |
| 17 | Title Case in Headers | A3-SS-007 | Title Case in Headers and Nominalization Cascade | DEMOTE (LOW) |
| 18 | Placeholder Text and Incomplete Elements | A3-TF-001 | Placeholder Text and Incomplete Elements | KEEP (HIGH) |
| 19 | Chatbot Communication Artifacts | A3-TF-002 | Chatbot Communication Artifacts | KEEP (HIGH) |
| 20 | Broken or Fabricated Links and Technical Codes | A3-TF-003 | Broken or Fabricated Links and Technical Codes | PROMOTE (HIGH) |
| 21 | Citation Abnormalities | A3-TF-004 | Citation Abnormalities | PROMOTE (MED to HIGH) |
| 22 | Suspiciously Long Edit Summaries | A3-TF-005 | Suspiciously Long Edit Summaries and Caveat Paragraphs | REVISE (MED) |
| 23 | Hallucinated Citations | A3-CS-001 | Hallucinated Citations | PROMOTE (HIGH) |
| 24 | Vague Attribution to Unnamed Authorities | A3-CS-002 | Vague Attribution to Unnamed Authorities | PROMOTE (MED to HIGH) |
| 25 | Industry-Specific Slop Patterns | A3-CX-001 | Industry-Specific Slop Patterns | REVISE (MED) |
| 26 | Lack of Personal Detail or Specificity | A3-CX-002 | Lack of Personal Detail or Specificity | PROMOTE (MED to HIGH) with expert-doc caveat |
| 27 | Superficial Depth Without Expertise | A3-CX-003 | Superficial Depth Without Expertise (now a section pointer to A2) | PROMOTE to section A2 |
| 28 | Hyperbolic Subheadings and Section Titles | A3-HD-001 | Hyperbolic Subheadings and Section Titles | KEEP (MED) |
| 29 | Dramatic Fragment Construction | A3-HD-002 | Dramatic Fragment Construction | KEEP (MED) |
| 30 | Borrowed Canonical Examples | A3-HD-003 | Borrowed Canonical Examples | REVISE (MED) |
| 31 | Scenario Fingerprinting in "Anonymized" Examples | A3-CE-001 | Scenario Fingerprinting in "Anonymized" Examples | KEEP (HIGH) |
| 32 | Operational Decisions Presented as Teaching Material | A3-CE-002 | Operational Decisions Presented as Teaching Material | KEEP (HIGH) |
| 33 | Saturated AI Vocabulary | A3-BT-001 | Saturated AI Vocabulary | PROMOTE (MED to HIGH) with family/genre refresh |
| 34 | Exhausted Metaphors as Structural Filler | A3-BT-002 | Exhausted Metaphors as Structural Filler | PROMOTE (MED to HIGH) |
| 35 | Unprompted Moral Cadence | A3-BT-003 | Unprompted Moral Cadence | KEEP (MED) |
| 36 | The Concierge Tone | A3-BT-004 | The Concierge Tone | KEEP with per-family weighting (HIGH for Claude, MED for GPT post-April-2025) |
| 37 | Insider Context Collapse | A3-FA-001 | Insider Context Collapse | PROMOTE (MED to HIGH) |
| 38 | Imported Spec Language Uppercase | A3-SR-001 | Imported Spec Language Uppercase | KEEP (HIGH for social, LOW for articles) |
| 39 | Article Structure in Social Posts | A3-SR-002 | Article Structure in Social Posts | KEEP (HIGH for social) with platform note |
| 40 | Third-Person Narration of First-Person Experience | A3-SR-003 | Third-Person Narration of First-Person Experience | KEEP (HIGH for social) |
| 41 | Lack of Closing Engagement in Social | A3-SR-004 | Lack of Closing Engagement in Social | REVISE (MED, downgraded from HIGH for Reddit specifically) |
| 42 | Em Dashes in Social Posts | A3-SR-005 | Em Dashes in Social Posts | PROMOTE (LOW to MED for cross-modal consistency) |

### Net-new criteria slotted thematically

These are net-new entries from A3.3 of the unified bucket, slotted into the appropriate thematic prefix rather than appended at the end. The ID numbering for each thematic group continues after the renumbered v3.1.0 entries.

| v4.0 ID | Source ID | Name | Thematic placement rationale |
|---|---|---|---|
| A3-LT-011 | A3-NEW-019 | Unnatural or Stilted Phrasing Beyond Formal Conjunctions | Language and Tone (sibling to LT-006) |
| A3-LT-012 | A3-NEW-020 | Over-Reliance on Abstract Nouns (Nominalization) | Language and Tone (sibling to LT-009; merges with v3.1.0 #17 nominalization concept) |
| A3-LT-013 | A3-NEW-021 | Redundant Modifiers and Adverbial Overkill | Language and Tone (sibling to LT-001) |
| A3-LT-014 | A3-NEW-005 | Orphaned Demonstratives | Language and Tone (sibling to LT-006) |
| A3-LT-015 | A3-NEW-019 sibling | "In Other Words" Reformulation Loop | Language and Tone (single-LLM contribution from DeepSeek's A1-CLAUDE-019) |
| A3-SS-008 | A3-NEW-004 | En-Dash Overuse as Em-Dash Replacement | Style and Structural (companion to SS-001) |
| A3-SS-009 | A3-NEW-030 | Over-Consistent Paragraph Rhythm Across Genres | Style and Structural (companion to LT-010) |
| A3-TF-006 | A3-NEW-010 | System-Prompt Artifact Bleed | Technical and Formatting (sibling to TF-002) |
| A3-TF-007 | A3-NEW-011 | Date Inconsistency and Knowledge-Cutoff Contradiction | Technical and Formatting |
| A3-CS-003 | A3-NEW-024 | Retrieval-Citation Mismatch | Citation and Sourcing (sibling to CS-001) |
| A3-CS-004 | A3-NEW-027 | Source-Theater Abundance | Citation and Sourcing |
| A3-CS-005 | A3-NEW-029 | Synthetic-Source Contamination | Citation and Sourcing |
| A3-CS-006 | A3-NEW-033 | Generic Authority Laundering | Citation and Sourcing (sibling to CS-002) |
| A3-CX-004 | A3-NEW-017 | Over-Generalization from Limited Data | Context-Specific (sibling to CX-002) |
| A3-CX-005 | A3-NEW-018 | Unnecessary Historical Context and "Once Upon a Time" Openers | Context-Specific |
| A3-HD-004 | A3-NEW-014 | Unwarranted Optimism or Pessimism | Hyperbolic and Dramatic (sibling to HD-001) |
| A3-HD-005 | A3-NEW-015 | Over-Reliance on Analogies and Metaphors | Hyperbolic and Dramatic (sibling to HD-003) |
| A3-HD-006 | A3-NEW-022 | The "Journey" Metaphor Overuse | Hyperbolic and Dramatic (specific to BT-002 family) |
| A3-HD-007 | A3-NEW-023 | Uncritical Use of "Synergy" and "Holistic" | Hyperbolic and Dramatic (specific to BT-001 family) |
| A3-BT-005 | A3-NEW-002 | Sycophancy Drift Across Turns | Behavioral and Tonal (sibling to BT-004) |
| A3-BT-006 | A3-NEW-003 | Partial-Refusal Stems | Behavioral and Tonal |
| A3-BT-007 | A3-NEW-006 | Human-in-the-Loop Roleplay Residue | Behavioral and Tonal |
| A3-BT-008 | A3-NEW-007 | Over-Apologizing in Refusal | Behavioral and Tonal |
| A3-BT-009 | A3-NEW-008 | Instruction-Following Over-Adherence | Behavioral and Tonal |
| A3-BT-010 | A3-NEW-013 | Refusal-to-Acknowledge-Uncertainty | Behavioral and Tonal |
| A3-BT-011 | A3-NEW-031 | Safety-Register Intrusions in Non-Safety Contexts | Behavioral and Tonal (sibling to BT-003) |
| A3-BT-012 | A3-NEW-001 + A3-NEW-034 | Reasoning-Trace Token Leakage | Behavioral and Tonal (new with 2025 reasoning models) |
| A3-FA-002 | A3-NEW-012 | Version-Specific Personality Slip | Frame and Audience |
| A3-FA-003 | A3-NEW-026 | Search-Answer Wrapper Voice | Frame and Audience |
| A3-FA-004 | A3-NEW-025 | Process-Theater Transparency | Frame and Audience |
| A3-FA-005 | A3-NEW-016 | Uncritical Acceptance of Prompt Framing | Frame and Audience |
| A3-FA-006 | A3-NEW-028 | Calibration Mismatch | Frame and Audience |
| A3-FA-007 | A3-NEW-009 | Acronym Saturation | Frame and Audience (genre-specific) |
| A3-FA-008 | A3-NEW-032 | Cross-Sentence Lexical Echoing | Frame and Audience (sibling to BT-001) |

Net-new criteria total: 32 distinct entries slotted thematically. Combined with the 42 renumbered v3.1.0 criteria, the v4.0 catalog covers 74 distinct entries in this references file.


---

## Section A3-LT: Language and Tone

### A3-LT-001: Undue Emphasis on Importance and Symbolism

- **Description.** LLMs inflate the significance of subjects by connecting them to broader, grandiose themes. The construction reads as evaluative claim ("X stands as a testament to Y") in places where a neutral descriptive sentence would serve. Sibling to A3-LT-002 (promotional language) and A3-BT-002 (exhausted metaphors). The Perplexity catalog's A1-CLAUDE-026 "Underscores the importance" closer is the same phenomenon at the structural level.
- **Concrete examples.**
  1. "The restaurant stands as a testament to community resilience."
  2. "This minor product update represents a watershed moment in technological innovation."
  3. "The town embodies the spirit of cultural heritage and economic vitality."
  4. "Her work carries enhanced significance in light of recent developments."
  5. (Per Perplexity) "This collaboration underscores the importance of cross-functional alignment."
- **Location and register.** Body paragraphs and section closers. Strongest in feature journalism, profile writing, marketing copy, and any register where significance is being claimed rather than demonstrated. Less common in technical writing where evidence is expected to carry the weight.
- **Model attribution.** All RLHF-tuned families produce this pattern. Claude family (HIGH confidence per `[cross-validated:claude-exec+perplexity+manus-ai]`), GPT family (HIGH), Gemini (MEDIUM-HIGH). Llama lower (per `[gemini]`: 0.21x Llama distinctiveness ratio relative to other families on this construction class).
- **Time evolution.** Present from earliest instruction-tuned models forward. Has not visibly declined across model generations because human preference data continues to favor "significant-sounding" prose for prompts requesting analysis or summary. Per `[chatgpt]`: stable across 2022 to 2026.
- **Sources.** v3.1.0 criterion 1; Manus AI's A3-NEW-014 (unwarranted optimism) intersects; Perplexity's A1-CLAUDE-026; Pinker (2014) on prose inflation per `[manus-ai]`. Stockton's "Don't Write Like AI" series (2025) per `[claude-exec-2026-05-18]`.
- **Signal strength.** MEDIUM. HIGH when clustering with A3-LT-002 (promotional language), A3-BT-001 (saturated vocabulary), and A3-LT-007 (section-ending summaries).
- **Base rate.** Moderate to high in unedited AI output for content with descriptive or evaluative prompts. Per `[opus-expansion]`: 30 to 50 percent of feature-style completions contain at least one instance.
- **Causal hypothesis (ranked).** Primary: RLHF reward shaping that scores prose with explicit significance markers higher than neutral description. Secondary: training-data skew toward marketing, journalism, and biographical genres where this register is common. Tertiary: helpfulness optimization (the model assumes the reader wants confirmation that the subject matters).
- **Detection difficulty.** Easy. Grep for the lexical markers ("stands as a testament," "plays a vital role," "represents a milestone," "embodies").
- **False positive risk.** Moderate. Skilled feature writers use these constructions sparingly for genuine emphasis. The discriminator is density (three or more in a single piece) and whether the significance claim is followed by evidence.
- **Fix or remediation.** Replace with descriptive prose plus evidence. "The restaurant stands as a testament to community resilience" becomes "The restaurant has hosted free meals for displaced families every Tuesday since the 2024 floods."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.
- **Notes on disagreement.** Perplexity proposes DEMOTE on the related "As an AI language model, I" surface form (genuinely declining). The merged v4.0 entry retains the broader symbolism-inflation pattern at MED and treats the "As an AI" preamble separately as a Historical-era pattern (see A3-TF-002).

---

### A3-LT-002: Promotional and Travel Brochure Language

- **Description.** Content reads like marketing copy: saturated marketing-register adjectives ("breathtaking," "captivating," "stunning"), generic place descriptors ("nestled in the heart of," "a hidden gem"), and uniformly positive evaluation. The pattern is most diagnostic when applied to topics that do not warrant marketing register (technical infrastructure, internal process documents, plain news).
- **Concrete examples.**
  1. "Nestled in the heart of the countryside, the town of Millbrook boasts a rich cultural heritage and stunning natural beauty."
  2. "This captivating destination offers visitors a unique blend of historic charm and modern amenities."
  3. "Our breathtaking new product is a must-have for the modern consumer."
  4. (Per `[chatgpt]`) "The platform delivers unparalleled value to its diverse and vibrant user community."
  5. (Per `[manus-ai]`) "A renowned hidden gem offering an authentic experience for those seeking adventure off the beaten path."
- **Location and register.** Universal in travel, lifestyle, food, retail, and real-estate writing. Strong tell when found in technical writing, internal communications, or news where the register does not match the content.
- **Model attribution.** All families. Claude and GPT-4o dense; Gemini somewhat less; Llama notably less per `[gemini]`. Per Matsui et al. PME 2025 (the academic anchor): saturated marketing-register vocabulary documented at Z above 3.5 across 103 of 135 candidate focal words in 2024 PubMed corpora when prompted for promotional registers.
- **Time evolution.** Stable across generations. The lexical inventory has evolved with consumer-marketing trends (the addition of "vibrant," "authentic," "curated" to the cluster) but the underlying pattern is consistent.
- **Sources.** v3.1.0 criterion 2; Matsui (2025) PME per `[claude-exec-2026-05-18]`; `[cross-validated:manus-ai+perplexity+chatgpt]`. Strunk and White (2000) on advertising-register cliches per `[manus-ai]`.
- **Signal strength.** HIGH (promoted from MED). The empirical anchor in Matsui 2025 and the cross-family persistence support the promotion.
- **Base rate.** High in unedited AI output for travel, lifestyle, retail, and real-estate prompts. Moderate elsewhere. Per `[opus-expansion]`: 65 to 80 percent of unedited completions for promotional prompts; 15 to 25 percent for general analytical prompts (register bleed).
- **Causal hypothesis (ranked).** Primary: training-data skew (the model has seen vast quantities of marketing copy and overweights it). Secondary: RLHF reward modeling that scores polished, positive language higher. Tertiary: helpfulness optimization that interprets "describe this place" as a request to promote.
- **Detection difficulty.** Easy. Saturated marketing vocabulary is grep-able. The register bleed into non-marketing prompts is the more useful diagnostic.
- **False positive risk.** Low for register bleed (technical or analytical content with marketing register is a clear tell). Moderate for actual marketing prompts where the register is contextually appropriate.
- **Fix or remediation.** Replace promotional adjectives with specific factual descriptions. "Stunning natural beauty" becomes a description of what specifically can be seen. "Rich cultural heritage" becomes the named institutions, festivals, or traditions.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-LT-003: Editorial Commentary and Meta-Analysis

- **Description.** LLMs inject interpretation, importance judgments, or explicit guidance about what readers should think, often using meta-commentary phrases ("it's important to note," "notably," "it is worth mentioning") to flag what the reader should care about rather than letting the content carry the signal. Cross-references A3-CLAUDE-001 (the "It is important to note" preamble) and A3-LT-007 (section-ending summaries). Per Perplexity's A1-CLAUDE-001 "Transitional Phrase Cluster" the cluster includes "it's worth noting," "at its core," "let's explore," "when it comes to," "navigating [topic]," and "ultimately."
- **Concrete examples.**
  1. "It's important to note that this development represents a significant shift in the industry."
  2. "It is worth emphasizing that stakeholders should pay close attention to these emerging trends."
  3. "Notably, the policy change comes at a critical juncture for the sector."
  4. "Interestingly, the data reveals a pattern that has not been previously observed."
  5. (Per ChatGPT) "Crucially, the implications of this finding extend far beyond the immediate context."
  6. (Per Perplexity) "At its core, this problem reduces to a question of resource allocation."
- **Location and register.** Paragraph openers and sentence beginnings. Universal across registers, densest in analytical, policy, and advisory prose. Particularly common after a factual statement, where the meta-commentary functions as an alignment-trained hedge rather than load-bearing qualifier.
- **Model attribution.** Claude family (HIGH per `[cross-validated:claude-exec+perplexity+deepseek+manus-ai+chatgpt+gemini]`). GPT family (MEDIUM-HIGH; uses similar hedging constructions with different phrasing such as "It's important to remember" or "Keep in mind"). Gemini also produces this pattern.
- **Time evolution.** Emerged with Claude 2 in mid-2023; peaked in Claude 3.5 Sonnet (mid-2024); began mild decline in Claude 4.5 Opus and later; still at meaningful base rate in 2026-05.
- **Sources.** v3.1.0 criterion 3; `[cross-validated:claude-exec+perplexity+chatgpt]`. Liang et al. 2024 (Nature, arxiv 2406.07016) on LLM use in scientific papers. Pangram and GPTZero detector methodology pages list this preamble family as a high-signal indicator.
- **Signal strength.** MEDIUM standalone. HIGH when clustered with three or more from the broader Perplexity cluster ("it's worth noting," "at its core," "when it comes to") in 500 words.
- **Base rate.** Frequent in unedited Claude output (estimated 40 to 60 percent of non-creative completions contain at least one instance per `[deepseek]` and `[opus-expansion]`). Rare in human-written non-academic text.
- **Causal hypothesis (ranked).** Primary: RLHF reward shaping that rewards caution and qualification. Secondary: training-data skew toward academic and policy registers. Tertiary: system-prompt artifacts instructing "be thoughtful and nuanced."
- **Detection difficulty.** Easy. Grep for the specific phrases. Differentiating genuine analysis from empty commentary markers requires reading context.
- **False positive risk.** Moderate. Academic and policy writers use this construction; the discriminator is density and combination with other markers.
- **Fix or remediation.** Replace with direct assertion. If the qualifier is genuinely load-bearing, embed it in the main clause rather than as a preamble. "It's important to note that the regulatory environment has shifted" becomes "The regulatory environment shifted in 2025." Cross-link to A2-SUB-007 (hedging as substance evasion).
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT (also HYBRID at wrapper boundaries).
- **Notes on disagreement.** ChatGPT's REVISE recommendation focuses on differentiating genuine analysis from empty commentary; that distinction is folded into the fix guidance above.

---

### A3-LT-004: Superficial Analysis with Participial Phrases

- **Description.** Sentences end with "-ing" phrases that add shallow analytical commentary without substance. The construction simulates inference (it looks like the writer is drawing a conclusion) without providing the inference content. Cross-references A2-SUB substance tests and A3-BT-002 (exhausted metaphors).
- **Concrete examples.**
  1. "The company announced new policies, highlighting its commitment to sustainability."
  2. "The festival attracts thousands of visitors annually, underscoring the region's cultural importance."
  3. "The research revealed new findings, demonstrating the team's innovative approach."
  4. "The CEO addressed the criticism directly, signaling a new era of transparency."
  5. (Per ChatGPT) "Sales exceeded projections, reflecting strong consumer confidence."
  6. (Per ChatGPT) "The report cited multiple data sources, ensuring a comprehensive analysis."
- **Location and register.** Sentence closers throughout body paragraphs. Strongest in feature journalism, corporate communications, and analyst commentary. Less common in dialogue, fiction, and casual prose.
- **Model attribution.** All families (HIGH for Claude and GPT-4o; MEDIUM for Gemini). Per `[chatgpt]`: better evidence in 2025-2026 that these structures simulate inference without adding content.
- **Time evolution.** Stable across model generations. Reflects training-data exposure to corporate communications and analytical journalism, both of which overuse the construction.
- **Sources.** v3.1.0 criterion 4; `[chatgpt]` for PROMOTE recommendation; cross-link to A2 substance-test framework per the unified bucket A consensus.
- **Signal strength.** HIGH (promoted from MED). Promotion rests on the cross-link to A2 substance tests: the construction is a substance-evasion device, and the substance test is the diagnostic.
- **Base rate.** Moderate to high in unedited AI output for analytical or news-style prompts. Per `[opus-expansion]`: 35 to 55 percent of news-summary completions contain at least one instance.
- **Causal hypothesis (ranked).** Primary: training-data skew toward corporate communications. Secondary: RLHF reward modeling that scores prose with explicit conclusion markers higher. Tertiary: helpfulness optimization that interprets "analyze this" as a request to add interpretive flourish even when the content does not support genuine inference.
- **Detection difficulty.** Easy. The "-ing" closer is grep-able.
- **False positive risk.** Moderate. The construction is legitimate when the participial phrase carries actual content; the discriminator is whether the participial closer adds inference or merely repackages what the main clause already said.
- **Fix or remediation.** Either provide real analysis with evidence (replacing the participial phrase with a new sentence that carries the inference content) or let the statement stand alone. "The CEO addressed the criticism directly, signaling a new era of transparency" becomes "The CEO addressed the criticism in a 40-minute open Q&A; she committed to monthly all-hands meetings, a reversal of the prior policy."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-LT-005: Negative Parallelism

- **Description.** Overuse of "not X but Y" constructions to create artificial contrast and drama. Includes the variants "not just X, but Y," "not only X, but also Y," "it is not merely X; it is Y." Preference data in RLHF directly reinforces antithesis per `[claude-exec-2026-05-18]`'s causal analysis. ChatGPT and Stockton's "Don't Write Like AI" series (2025) argue for DEMOTE on the basis that many human essayists use this construction naturally.
- **Concrete examples.**
  1. "The restaurant is not just a place to eat, but a cornerstone of community gathering."
  2. "This technology is not merely an improvement, but a revolutionary breakthrough."
  3. "The policy change represents not only a shift in strategy but also a commitment to transparency."
  4. (Per Claude expansion) "It's not just about cost reduction; it's about reimagining the entire workflow."
  5. (Per Claude expansion) "The migration was not simply a technical upgrade but a strategic repositioning."
- **Location and register.** Body paragraphs throughout, particularly in thesis-statement positions (opening of sections, transitions between arguments) and conclusions.
- **Model attribution.** Claude family (HIGH per `[claude-exec-2026-05-18]`). GPT family (MEDIUM). The Claude-specific elevation rests on preference-data reinforcement of antithesis structures.
- **Time evolution.** Present from earliest Claude versions forward; stable through 4.x. GPT family rate has been roughly stable across generations.
- **Sources.** v3.1.0 criterion 5; `[claude-exec-2026-05-18]`; Stockton (2025) "Don't Write Like AI" series for the DEMOTE counterargument.
- **Signal strength.** MEDIUM (KEEP with note). The disagreement between ChatGPT (DEMOTE) and the Claude expansion (PROMOTE) is preserved. The merged decision keeps the tier at MEDIUM but flags that combination weighting matters more in v4.0.
- **Base rate.** Moderate in unedited AI output (estimated 20 to 35 percent of analytical or argumentative completions contain at least one instance per `[opus-expansion]`). Higher for opinion or thesis-driven prompts.
- **Causal hypothesis (ranked).** Primary: RLHF preference data that consistently rates antithesis higher than declarative parallelism (per `[claude-exec-2026-05-18]`'s causal analysis). Secondary: training-data skew toward rhetoric corpora where the construction is foundational.
- **Detection difficulty.** Easy. The "not just X but Y" surface form is grep-able.
- **False positive risk.** Moderate. Skilled essayists deploy the construction sparingly for genuine contrast; the discriminator is density (three or more in a single piece is a strong signal).
- **Fix or remediation.** Use the structure sparingly and only when the contrast is genuine and significant. When the "Y" reframes rather than contrasts with "X," collapse to a single positive claim.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.
- **Notes on disagreement.** ChatGPT argues DEMOTE (human essayists use this naturally); Claude expansion argues PROMOTE (preference data specifically reinforces antithesis). Both views have merit. Merged decision: KEEP at MEDIUM with combination-weighting note.

---

### A3-LT-006: Overuse of Transition Words and Formal Conjunctions

- **Description.** Excessive, stilted use of transitional phrases that create an essay-like or overly formal tone. The pattern is the density and mechanical placement, not the words themselves. Cross-references A3-LT-014 (orphaned demonstratives) and A3-FA-008 (cross-sentence lexical echoing).
- **Concrete examples.**
  1. "Moreover, the data suggests a significant trend."
  2. "Furthermore, we must consider the implications."
  3. "Additionally, it is worth noting the broader context."
  4. (Per `[deepseek]`'s A1-CLAUDE-015) "However, several challenges remain."
  5. (Per `[deepseek]`) "Consequently, the team revised its approach."
  6. (Per `[chatgpt]`) "Nevertheless, the underlying assumptions warrant scrutiny."
- **Location and register.** Paragraph openers. Densest in academic, policy, and analytical prose. Strong tell when used in casual or short-form content where transitions should be implicit.
- **Model attribution.** All families. Claude (HIGH for "However," paragraph pivot per `[deepseek]`'s A1-CLAUDE-015: 30 to 40 percent of multi-paragraph analytical completions). GPT family (MEDIUM; "Moreover" and "Furthermore" densest in 4o). Gemini (MEDIUM).
- **Time evolution.** Stable across generations. Per `[chatgpt]`'s DEMOTE recommendation: frontier models have improved slightly. Per `[claude-exec-2026-05-18]`'s PROMOTE recommendation: the combination signal has strengthened even if standalone signal has weakened.
- **Sources.** v3.1.0 criterion 6; `[chatgpt]` for DEMOTE; `[claude-exec-2026-05-18]` for PROMOTE; `[deepseek]`'s A1-CLAUDE-015 for "However" pivot density.
- **Signal strength.** LOW base rate; MEDIUM clustered with three or more from the transition-word inventory. Combination signal: HIGH when paired with uniform sentence length (A3-LT-010), bulleted bolded lead-ins (A3-SS-002), and section-ending summaries (A3-LT-007).
- **Base rate.** High in unedited AI long-form (estimated 70 to 90 percent of multi-paragraph completions contain at least one). Moderate in short-form.
- **Causal hypothesis (ranked).** Primary: training-data skew toward academic and analytical writing where these transitions are conventional. Secondary: RLHF reward modeling that scores "well-organized" output higher. Tertiary: helpfulness optimization that announces logical structure explicitly.
- **Detection difficulty.** Easy. Grep for the inventory.
- **False positive risk.** Moderate. Skilled analytical writers use these transitions; the discriminator is density and combination.
- **Fix or remediation.** Let ideas connect through logical flow. When transitions are needed, vary them and use the simplest option that works. Replace formal conjunctions with implicit transitions or with the simplest connective ("And," "But," "So").
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.
- **Notes on disagreement.** ChatGPT and Gemini propose DEMOTE; Claude expansion proposes PROMOTE. Merged: KEEP with combination weighting.

---

### A3-LT-007: Section-Ending Summaries

- **Description.** Paragraphs or sections end with explicit summary statements ("In summary," "In conclusion," "Overall," "In essence," "To summarize," "Ultimately,") mimicking academic essay structure. The summary adds no new information in short content; in long-form, every section ends with a backward-looking pause. Cross-references A1-CLAUDE-007 (section-ending recap sentence) and A2-SUB-013 (frictionless-transition padding).
- **Concrete examples.**
  1. "In summary, the three factors above demonstrate that X is the most viable approach."
  2. "Overall, the data supports the conclusion that..."
  3. "Ultimately, finding a balance between performance and cost is crucial."
  4. (Per Perplexity) "Together, these considerations underscore the importance of careful planning."
  5. (Per Perplexity) "This illustrates why the framework outlined here provides a useful starting point."
- **Location and register.** Mid-document section closers and final response closers. Universal across registers, densest in technical and analytical prose.
- **Model attribution.** Claude family (HIGH); GPT-4o family (HIGH); Gemini (MEDIUM-HIGH). Per Perplexity: comparable rates in Claude and GPT-4o. Per `[deepseek]`: 60 to 80 percent of multi-section completions.
- **Time evolution.** Present from Claude 2 forward; persistent through 4.x. Slightly reduced in Claude 4 with explicit no-summary system prompting.
- **Sources.** v3.1.0 criterion 7; `[cross-validated:manus-ai+perplexity+deepseek]`; BlogPros 2026 practitioner observations per Perplexity.
- **Signal strength.** MEDIUM standalone; HIGH in combination with bolded lead-ins (A3-SS-002) and balanced two-handed sentences (A3-LT-005).
- **Base rate.** High in unedited AI long-form (estimated 60 to 80 percent of multi-section responses). High in templated blog and educational content. Lower in dialogue.
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling that rewards clear structure including explicit summarization. Secondary: training-data skew toward academic prose. Tertiary: helpfulness optimization (the model assumes the reader needs the recap).
- **Detection difficulty.** Easy.
- **False positive risk.** Low to moderate. Technical writing and textbooks use section recaps; the discriminator is mechanical placement (every section gets one regardless of need).
- **Fix or remediation.** Remove the recap unless the section's point is genuinely buried. If buried, rewrite the section's lead, not its tail. News articles, blogs, and most media content do not summarize sections like essays.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER for final-closer instances; BODY-PERSISTENT for mid-document section closers.

---

### A3-LT-008: The Rule of Three

- **Description.** Formulaic grouping of ideas, traits, or examples in threes. The rule of three is a legitimate rhetorical device; the LLM pathology is using it as a default structure for every list, every adjective cluster, every example set. Human writing varies list lengths naturally. Cross-references A3-SS-002 (bulleted lists with bolded lead-ins) and A3-LT-006 (transition density).
- **Concrete examples.**
  1. "Innovative, impactful, and transformative."
  2. "Boost morale, increase productivity, and foster collaboration."
  3. "Keynote sessions, panel discussions, and networking opportunities."
  4. (Per `[chatgpt]`) "Cost-effective, scalable, and future-proof."
  5. (Per `[chatgpt]`) "Creative, smart, and funny."
- **Location and register.** Universal. Strongest in branding copy, executive summaries, and AI polished prose where the structure has become a "safe" default.
- **Model attribution.** All families. Claude and GPT both dense. Less common in Llama per `[gemini]`.
- **Time evolution.** Stable across model generations.
- **Sources.** v3.1.0 criterion 8; `[cross-validated:manus-ai+perplexity+chatgpt]`.
- **Signal strength.** MEDIUM.
- **Base rate.** High in unedited AI output for list-prompts (estimated 80 to 95 percent of "list three..." prompts produce exactly three regardless of natural fit).
- **Causal hypothesis (ranked).** Primary: training-data prevalence (the rule of three is the most common list-cardinality in human writing). Secondary: RLHF reward modeling that scores tidy triadic structure higher. Tertiary: tokenizer effects (three-item lists are concise and complete-feeling).
- **Detection difficulty.** Medium. Pattern requires noticing consistent triadic structure across multiple sentences and paragraphs, not just one occurrence.
- **False positive risk.** Moderate. The rule of three is a legitimate human rhetorical device. The discriminator is mechanical application (every list is three, every adjective set is three).
- **Fix or remediation.** Vary list lengths. Sometimes two items are enough; sometimes four or five are warranted. Let content dictate structure, not formula.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-LT-009: Vague Evidential Passive Voice

- **Description.** Overreliance on passive constructions that indirectly attribute claims to unnamed authorities, particularly the "[Subject] has been described as," "[Subject] is widely regarded as," "[Subject] is considered to be," and "[Subject] has been praised for" family. The v3.1.0 phrasing was "Passive Voice and 'Has Been Described As' Construction"; v4.0 narrows to vague evidential passives per `[chatgpt]`'s REVISE recommendation, because passive voice broadly is too weak a signal. The construction creates an illusion of authority without providing attribution. Cross-references A3-CS-002 (vague attribution to unnamed authorities) and A1-GEMINI-010 (formal academic register default).
- **Concrete examples.**
  1. "The framework is widely regarded as a foundational contribution to the field."
  2. "The methodology has been described as both rigorous and innovative."
  3. "The leader is considered to be one of the most influential figures of the era."
  4. (Per `[perplexity]`) "The technique is known for its versatility across domains."
  5. (Per `[chatgpt]`) "It has been argued that this approach yields better long-term outcomes."
- **Location and register.** Body paragraphs. Strongest in encyclopedic, profile, and review writing. Per Perplexity: more characteristic of Gemini and formal-register outputs than Claude 4.
- **Model attribution.** Gemini family (HIGH per `[perplexity]`; cross-link to A1-GEMINI-010 formal academic register default). Claude family (MEDIUM). GPT family (MEDIUM). Llama (LOW per `[gemini]`).
- **Time evolution.** Stable. The construction has been a persistent feature of Wikipedia-style training data, which all major families have ingested.
- **Sources.** v3.1.0 criterion 9; `[perplexity]` for Gemini attribution; `[chatgpt]` for REVISE recommendation to narrow scope.
- **Signal strength.** LOW (revised from broader passive-voice claim). HIGH when paired with A3-CS-002 (vague attribution) in a single passage.
- **Base rate.** Moderate in unedited Gemini and Wikipedia-style output. Lower in Claude and GPT.
- **Causal hypothesis (ranked).** Primary: training-data skew toward encyclopedic and biographical corpora. Secondary: RLHF reward modeling that scores "authoritative-sounding" prose higher. Tertiary: alignment safety tuning that prefers indirect attribution to avoid making the model assert claims directly.
- **Detection difficulty.** Easy. Grep for the formulaic phrasing.
- **False positive risk.** Moderate. Profile writing legitimately uses these constructions; the discriminator is density and absence of named attribution.
- **Fix or remediation.** Use direct statements with specific attribution. "The framework is widely regarded as foundational" becomes "Kahneman and Tversky (1979) named the framework prospect theory; it has been cited in over 70,000 papers."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-LT-010: Uniform Sentence and Paragraph Length

- **Description.** Mechanically consistent structure: sentences cluster within a narrow length band, paragraphs cluster in the 3 to 5 sentence range. Human writing exhibits "burstiness," varying paragraph length deliberately for emphasis, pacing, and breath. Cross-references A1-CLAUDE-008 (uniform paragraph length / low burstiness) and A3-SS-009 (over-consistent paragraph rhythm across genres).
- **Concrete examples.** This is a structural pattern best seen in aggregate, not single examples. Compare an unedited Claude long-form essay (consistent 3 to 5 sentence paragraphs throughout) to a feature in The New Yorker (paragraph lengths varying from 1 sentence for emphasis to 10+ sentences for sustained argument). Per Perplexity: observable over 200+ word samples. GPTZero uses 0.30 burstiness as a strong AI signal threshold.
- **Location and register.** Universal across registers in long-form output. Less visible in short responses where paragraph variation has less room to express.
- **Model attribution.** Claude family (HIGH per `[claude-exec-2026-05-18]` and `[perplexity]`). GPT family (HIGH; GPT-4o slightly more uniform than GPT-5 series). Gemini (MEDIUM). Llama (MEDIUM; varies more than closed-source frontier models).
- **Time evolution.** Stable across versions; reflects underlying generation strategy more than recent training.
- **Sources.** v3.1.0 criterion 10; Liang et al. 2023 (Patterns 2023, arxiv 2304.02819); GPTZero methodology documentation 2023; Pangram Labs 2026. Zaitsu et al. PLoS One 2025 (single-LLM-sourced) suggests Llama 3.1 places separately on MDS dimensions.
- **Signal strength.** HIGH (promoted from MED) for native-English content. MEDIUM for ESL content due to the Liang et al. 2023 ESL false-positive risk. The ESL safe-harbor is essential: low burstiness misclassifies a large fraction of TOEFL-style writing as AI per Liang et al. 2023.
- **Base rate.** Very high in unedited AI long-form (estimated 85 to 95 percent of essays exhibit burstiness below 0.35). Sourati et al. (2025) and Padmakumar and He (2024) document homogenization survey and output diversity loss respectively.
- **Causal hypothesis (ranked).** Primary: tokenizer and architecture effects (autoregressive generation with attention windows that favor moderate-length structures). Secondary: training-data skew toward edited prose where paragraphs tend toward moderate length. Tertiary: RLHF reward modeling that may implicitly reward easy-to-read structure.
- **Detection difficulty.** Medium. Requires looking at the distribution, not a single feature.
- **False positive risk.** HIGH for non-native English writers (Liang et al. 2023). Cornerstone of the ESL safe-harbor requirement in B3 calibration.
- **Fix or remediation.** Deliberately vary paragraph length. Single-sentence paragraphs for emphasis; longer paragraphs when sustaining an argument. Vary sentence length: one very short sentence, then a long one.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-LT-011: Unnatural or Stilted Phrasing Beyond Formal Conjunctions

- **Description.** Use of awkward, overly formal, or grammatically correct but unnatural sentence constructions that do not reflect typical human speech or writing patterns. Distinct from A3-LT-006 (transition words): this is the broader register-mismatch pattern where the model defaults to register-elevated phrasing even when context calls for plainer prose. Per `[manus-ai]`'s A3-NEW-006.
- **Concrete examples.**
  1. (Per `[manus-ai]`) "It is incumbent upon us to endeavor to ascertain the optimal pathway forward."
  2. (Per `[manus-ai]`) "The aforementioned considerations warrant careful deliberation prior to the implementation of said strategy."
  3. (Per `[manus-ai]`) "One must not underestimate the profound implications that may arise from such a confluence of factors."
  4. (Per `[opus-expansion]`) "We shall undertake the requisite analysis to facilitate the determination of an appropriate course of action."
- **Location and register.** Body paragraphs. Strongest when used in casual, conversational, or technical-practical contexts where the register is mismatched.
- **Model attribution.** All families. Most pronounced in Gemini formal-register default (cross-link to A1-GEMINI-010) and in Claude when prompted for formal contexts.
- **Time evolution.** Stable; tied to training-data corpora that include formal academic and legal prose.
- **Sources.** `[manus-ai]`'s A3-NEW-006; Pinker (2014); Strunk and White (2000).
- **Signal strength.** HIGH.
- **Base rate.** Moderate in unedited AI output; high when prompted for formal contexts; high when the model misjudges the register.
- **Causal hypothesis (ranked).** Primary: training-data skew toward formal corpora. Secondary: RLHF reward modeling for "professional" output. Tertiary: helpfulness optimization that defaults to elevated register when uncertain.
- **Detection difficulty.** Medium. Requires reading for register fit.
- **False positive risk.** Moderate. Legal, academic, and policy writing use this register legitimately; the discriminator is whether the context warrants it.
- **Fix or remediation.** Replace with plain alternatives. "It is incumbent upon us to endeavor to ascertain" becomes "We need to find out."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-LT-012: Over-Reliance on Abstract Nouns (Nominalization Cascade)

- **Description.** Excessive use of abstract nouns ("implementation," "optimization," "utilization," "prioritization") instead of more concrete verbs or active constructions, leading to dense and less engaging prose. Merges with v3.1.0 criterion 17's nominalization-cascade aspect (the v3.1.0 criterion 17 also covered title case in headers; v4.0 separates the two concepts into A3-SS-007 for title case and A3-LT-012 for nominalization). Per `[manus-ai]`'s A3-NEW-007 and `[perplexity]`'s REVISE on v3.1.0 criterion 17.
- **Concrete examples.**
  1. (Per `[manus-ai]`) "The implementation of the new strategy led to the optimization of resource utilization."
  2. (Per `[manus-ai]`) "Our objective is the prioritization of customer satisfaction through the enhancement of service delivery."
  3. (Per `[manus-ai]`) "The analysis involved the examination of data for the identification of patterns."
  4. (Per `[opus-expansion]`) "Implementation of the framework necessitates the consideration of multiple factors and the alignment of stakeholder expectations."
- **Location and register.** Body paragraphs. Strongest in corporate, governmental, and consulting prose.
- **Model attribution.** All families. Gemini (HIGH; cross-link to A1-GEMINI-010 formal academic register). Claude (MEDIUM-HIGH). GPT (MEDIUM).
- **Time evolution.** Stable.
- **Sources.** `[manus-ai]`'s A3-NEW-007; `[perplexity]` REVISE on criterion 17; Pinker (2014); Strunk and White (2000).
- **Signal strength.** HIGH.
- **Base rate.** High in unedited AI corporate or formal output.
- **Causal hypothesis (ranked).** Primary: training-data skew toward corporate and policy prose. Secondary: RLHF reward modeling for "professional" output. Tertiary: helpfulness optimization that defaults to abstraction when concrete examples are unclear.
- **Detection difficulty.** Easy. Grep for the "-tion" cluster and similar abstract-noun endings.
- **False positive risk.** Moderate. Some technical and policy writing legitimately uses abstract nouns; the discriminator is the density and whether the abstract nouns could be replaced with concrete verbs without information loss.
- **Fix or remediation.** Replace abstract-noun constructions with active verbs. "Implementation of the new strategy led to optimization of resource utilization" becomes "The new strategy used resources more efficiently."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-LT-013: Redundant Modifiers and Adverbial Overkill

- **Description.** Use of unnecessary adverbs or adjectives that add little to no meaning, often redundantly emphasizing a point already clear from the main verb or noun. Per `[manus-ai]`'s A3-NEW-008.
- **Concrete examples.**
  1. (Per `[manus-ai]`) "He carefully scrutinized the document in detail." ("Scrutinized" already implies carefulness and detail.)
  2. (Per `[manus-ai]`) "The completely unique solution truly revolutionized the industry."
  3. (Per `[manus-ai]`) "She personally oversaw the project herself."
  4. (Per `[opus-expansion]`) "The team thoroughly investigated all the various different options."
- **Location and register.** Body paragraphs. Universal across registers, densest in promotional and analytical prose.
- **Model attribution.** All families. GPT-4o family (HIGH). Claude (MEDIUM-HIGH). Gemini (MEDIUM).
- **Time evolution.** Stable.
- **Sources.** `[manus-ai]`'s A3-NEW-008; Pinker (2014); Strunk and White (2000).
- **Signal strength.** HIGH.
- **Base rate.** Moderate to high in unedited AI output.
- **Causal hypothesis (ranked).** Primary: training-data skew toward overwritten prose. Secondary: RLHF reward modeling that scores "emphatic" prose higher. Tertiary: helpfulness optimization that adds intensifiers to make claims feel more substantial.
- **Detection difficulty.** Medium. Requires noticing redundancy rather than spotting a specific phrase.
- **False positive risk.** Low. Genuinely redundant modifiers are clear once flagged.
- **Fix or remediation.** Remove the redundant modifier. "Carefully scrutinized in detail" becomes "scrutinized."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-LT-014: Orphaned Demonstratives

- **Description.** "This is important," "That said," "These factors," and similar demonstrative constructions used without clear antecedent. The demonstrative does not refer to a specific prior noun phrase but to the general gestalt of the previous text. Per the Claude expansion's A3-NEW-005.
- **Concrete examples.**
  1. "This is important to consider when evaluating the options." (What is "this"?)
  2. "These factors must be weighed carefully." (Which factors?)
  3. "That said, several caveats apply." (To what was just said? What in particular?)
  4. (Per `[opus-expansion]`) "This represents a significant development in the field."
- **Location and register.** Paragraph openers and sentence beginnings. Universal across registers, densest in analytical and policy prose where the writer is summarizing or transitioning.
- **Model attribution.** All families. Per the Claude expansion's analysis: medium-high in Claude, GPT, Gemini.
- **Time evolution.** Stable. Reflects training-data exposure to academic and policy prose where demonstratives are used as cohesive devices, often loosely.
- **Sources.** Claude expansion's A3-NEW-005; `[opus-expansion]`.
- **Signal strength.** MEDIUM. HIGH when clustered with other transitional patterns (A3-LT-006).
- **Base rate.** Moderate.
- **Causal hypothesis (ranked).** Primary: training-data skew toward academic prose. Secondary: RLHF reward modeling that scores prose with explicit cohesive markers higher. Tertiary: tokenizer effects (demonstratives are short and cheap to produce).
- **Detection difficulty.** Medium. Requires checking whether the demonstrative has a specific antecedent.
- **False positive risk.** Moderate. Demonstratives with specific antecedents are normal; the discriminator is the orphaned use.
- **Fix or remediation.** Replace the demonstrative with the specific noun phrase. "These factors" becomes "the latency, cost, and consistency factors." "That said" becomes "Despite the speed improvements, X remains a concern."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-LT-015: "In Other Words" Reformulation Loop

- **Description.** Claude (and to a lesser degree other families) restates the same idea immediately using "In other words," "Put differently," or "Stated another way," often adding no new information. The reformulation loop is sibling to A1-CLAUDE-019 and to the over-explanation pattern. Per `[deepseek]`'s A1-CLAUDE-019.
- **Concrete examples.**
  1. (Per `[deepseek]`) "The model exhibits a high degree of sensitivity to input perturbations. In other words, small changes in the input can lead to large changes in the output."
  2. (Per `[deepseek]`) "The policy aims to reduce emissions through market mechanisms. Put differently, it uses cap-and-trade."
  3. (Per `[opus-expansion]`) "The framework is over-determined. Stated another way, it has more constraints than degrees of freedom."
- **Location and register.** Body paragraphs. Strongest in pedagogical and analytical prose.
- **Model attribution.** Claude (frequent per `[deepseek]`); GPT (occasional); Gemini (occasional).
- **Time evolution.** Stable.
- **Sources.** `[deepseek]`'s A1-CLAUDE-019; `[opus-expansion]`.
- **Signal strength.** LOW-MEDIUM. Not a strong differentiator alone.
- **Base rate.** Occasional.
- **Causal hypothesis (ranked).** Primary: over-optimization for clarity. Secondary: academic writing tic in training data.
- **Detection difficulty.** Easy.
- **False positive risk.** Low when the reformulation is redundant; moderate when the reformulation actually clarifies.
- **Fix or remediation.** Delete one version. Keep the more concrete one.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.


---

## Section A3-SS: Style and Structural

### A3-SS-001: Excessive Em Dashes

- **Description.** Em dashes (the long dash, Unicode U+2014) used at notably higher density than human writers, in particular as parenthetical-substitute punctuation around mid-sentence asides and as the punctuation between an independent clause and an appositive. Cross-references A1-CLAUDE-004 (em-dash density), A3-SR-005 (em-dashes in social posts), and A3-SS-008 (en-dash overuse as em-dash replacement). Largest tier-shift divergence in the catalog.
- **Concrete examples.**
  1. Human-typical: "The migration, which took six weeks, was worth the effort." Claude-tendency: "The migration (which took six weeks and required cross-team coordination) was worth the effort," substituted with em-dashes in the original output.
  2. (Per `[perplexity]`) "The integration, already underway in three pilot markets, faces regulatory headwinds that could delay the rollout by as much as 18 months." When original output used em-dashes around the parenthetical clause.
  3. (Per `[perplexity]`) "Machine learning models, particularly transformer architectures, perform best when fine-tuned on domain-specific data." Same em-dash substitution.
  4. (Per `[opus-expansion]`) "There are three concerns, cost, complexity, and time, that need to be addressed before proceeding." Em-dashes used as oxford-comma substitutes.
- **Location and register.** Universal across registers. Densest in long-form analytical prose. Notably present in social-media posts (especially LinkedIn) where human writers tend to avoid the character.
- **Model attribution.** Claude family (HIGH; single strongest token-level fingerprint as of 2025). Pre-GPT-5.1 ChatGPT (HIGH). GPT-5.1+ (LOW; explicit anti-em-dash personalization rolled out in 2025 dropped its rate). Llama and Meta.ai (NEAR-ZERO per `[gemini]` A1-LLAMA-001: 0.0 occurrences per 1,000 words). Gemini variable depending on system prompt.
- **Time evolution.** Present from Claude 2 forward at increasing density through 3.5 Sonnet. ChatGPT had high em-dash rate through GPT-4o; rate dropped sharply after the GPT-5.1 anti-em-dash personalization update in 2025. Claude has not made an equivalent adjustment as of 2026-05. Per `[chatgpt]`'s DEMOTE recommendation: frontier models show reduced rates while retaining the social-specific version at high confidence. Per `[grok]`'s DEMOTE: same direction.
- **Sources.** v3.1.0 criterion 11; `[claude-exec-2026-05-18]` (identified as "the single strongest token-level tell on Claude and pre-GPT-5.1 ChatGPT"); Plagiarism Today June 2025 ("Em Dashes, Hyphens and Spotting AI Writing"); `[cross-validated:perplexity+deepseek+manus-ai+gemini]`; Pangram Labs (2026) detector methodology lists em-dash density among trained features; BlogPros (2026); LinkedIn practitioner catalog 2025.
- **Signal strength.** HIGH for Claude family and pre-GPT-5.1 ChatGPT (promoted from LOW). LOW for GPT-5.1+ and Llama families. Per-family weighting is essential. Per Perplexity threshold: 5+ em-dashes per 500 words is a HIGH signal in Claude.
- **Base rate.** Very high in unedited Claude output (estimated 80 to 95 percent of long-form completions contain at least one em-dash; many contain dense clusters per `[opus-expansion]`). High in pre-GPT-5.1 ChatGPT. Near zero in Llama and Meta.ai. Low in current GPT-5.1.
- **Causal hypothesis (ranked).** Primary: training-data skew toward edited prose corpora (academic, journalism) that overrepresent em-dashes relative to general web text. Secondary: RLHF reward modeling that reads em-dashes as a polish signal. Tertiary: tokenizer effects (the em-dash is a single token in most tokenizers, making it cheap to generate). Per Perplexity: RLHF rewards readability; em-dashes score well on readability metrics because they reduce sentence count while preserving information density.
- **Detection difficulty.** Easy. Character search.
- **False positive risk.** Moderate. Some skilled writers (journalism, certain literary genres) use em-dashes heavily as a stylistic choice. The discriminator is density per 1,000 tokens and combination with other markers.
- **Fix or remediation.** Replace with commas (for parentheticals of moderate weight), parentheses (for stronger asides), colons (for appositives), or sentence breaks (for cases where the em-dash was joining two complete thoughts). Per Perplexity: split at the dash. "X, already Y, does Z" becomes "X does Z. (It was already Y.)"
- **Era status.** Active for Claude. Declining for GPT family. Historical for newer Meta/Llama output where the base rate has always been near zero.
- **Zone tag.** BODY-PERSISTENT.
- **Notes on disagreement.** ChatGPT proposes DEMOTE (frontier models reduced rates). Manus AI proposes REVISE (less reliable standalone). Grok proposes DEMOTE. Claude expansion proposes PROMOTE (LOW to HIGH for Claude). Gemini proposes per-family split (DEPRECATE for Llama, PROMOTE for GPT/Claude). Merged: PROMOTE with per-family weighting per Gemini's split.

---

### A3-SS-002: Bulleted Lists with Bolded Lead-ins

- **Description.** Formulaic bullet points where each item begins with a bolded short noun phrase followed by a colon or period, then the body text. The structure is consistent within a single response, often three to seven items long, and reads as outline-mode prose rather than natural list construction. Cross-references A1-CLAUDE-005 and A1-GPT-008 (numbered-list scaffolding and listicle-default mode).
- **Concrete examples.**
  1. "**Cost efficiency:** The new approach reduces server expenses by 40 percent."
  2. "**Scalability:** Adding capacity is now a configuration change rather than a rebuild."
  3. "**Developer experience:** Engineers report 30 percent faster iteration."
  4. (Per `[deepseek]`) "**Improved efficiency:** The new process reduces the time required for data entry by nearly 40%, freeing up staff for higher-value tasks."
  5. (Per `[deepseek]`) "**Enhanced security:** By implementing multi-factor authentication, the system ensures that only authorized users can access sensitive information."
- **Location and register.** Body of explanatory and analytical responses. Particularly dense in product, business, and technical-writing registers. Rare in dialogue and fiction.
- **Model attribution.** Claude family (HIGH). GPT family (HIGH, especially 4o). Gemini (MEDIUM-HIGH; markdown-leaked variant where the bold formatting renders incorrectly in non-rendering channels, cross-link to A1-GEMINI-001 plain-text markdown leakage).
- **Time evolution.** Present from Claude 2 forward; standardized in 3.x; high density in 4.x default outputs without explicit "do not use bullets" system prompt.
- **Sources.** v3.1.0 criterion 12; `[claude-exec-2026-05-18]`; `[cross-validated:perplexity+gemini+manus-ai]`; Walsh et al. CHR 2024 documents the outline-rendered-as-poem effect in LLM creative output.
- **Signal strength.** HIGH (promoted from MED) when combined with em-dash density (A3-SS-001) or uniform paragraph length (A3-LT-010). MEDIUM standalone.
- **Base rate.** High in unedited Claude output for explanatory or comparative responses (estimated 50 to 70 percent of responses containing 3+ items use this bolded-lead-in structure). High in GPT 4o. Moderate in Gemini.
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling that scores well-organized structured output. Secondary: training-data skew toward documentation and product copy corpora. Tertiary: system-prompt artifacts in Claude.ai default UI tuning.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate. Technical documentation, product copywriters, and how-to guides legitimately use this structure. The discriminator is density (every response using it for every list) and combination with other markers.
- **Fix or remediation.** When the structure is genuinely warranted (true parallel items where each has the same scaffold), keep it. When the response is short or the items are heterogeneous, write the items as prose or use plain bullets without bolded lead-ins.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-SS-003: Excessive Bolding and Formatting

- **Description.** Mechanical, over-consistent use of bold text for key terms throughout an article. LLMs sometimes emphasize terms they deem "important" without understanding that excessive formatting reduces readability. Combinable with A3-SS-005 (markdown formatting leakage) and adjacent to A3-SS-002 (bulleted lead-ins). Per `[perplexity]`: accurate for GPT-4o; reducing in GPT-4.1.
- **Concrete examples.**
  1. "**Key insight**: The **migration** improved **performance** by 40 percent and reduced **costs** by 25 percent, demonstrating the **value** of the **approach**."
  2. "The **decision** was made to **prioritize** the **customer experience** over **internal metrics**."
  3. (Per `[opus-expansion]`) Multiple sentences in a paragraph with **bolded** terms that simply restate ordinary nouns or verbs in **emphatic** form rather than marking genuinely **important** terms.
- **Location and register.** Body paragraphs. Densest in product, business, and technical-writing registers.
- **Model attribution.** Claude family (MEDIUM-HIGH). GPT-4o family (HIGH; reducing in GPT-4.1 per `[perplexity]`). Gemini (MEDIUM-HIGH; cross-link to A1-GEMINI-001 markdown leakage).
- **Time evolution.** Peaked in 2024 Claude and GPT-4o; reducing in GPT-4.1 specifically. Claude has not made an equivalent reduction.
- **Sources.** v3.1.0 criterion 13; `[claude-exec-2026-05-18]`; `[perplexity]` REVISE recommendation for version note.
- **Signal strength.** MEDIUM (promoted from LOW). HIGH when combined with A3-SS-002.
- **Base rate.** High in unedited Claude and GPT-4o output for explanatory prose.
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling that scores prose with explicit emphasis higher. Secondary: training-data skew toward marketing and product documentation where bolding is conventional. Tertiary: system-prompt artifacts.
- **Detection difficulty.** Easy. Visual scan of formatting density.
- **False positive risk.** Low to moderate. Technical and educational writing legitimately uses bolding for key terms; the discriminator is density (more than one bolded term per paragraph throughout).
- **Fix or remediation.** Bold sparingly. If everything is emphasized, nothing is. Reserve bold for terms that the reader will need to recognize again later.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-SS-004: Emoji Usage in Inappropriate Contexts

- **Description.** Emojis appearing in article text, headers, or formal content where they do not belong. Some LLMs insert emojis to "add emotion" or "engage readers," but do so without understanding context or audience appropriateness. Cross-references A1-GEMINI-027 (emoji in explanations) per the unified bucket A. Wrapper-sensitive: stronger for GPT-4o-era consumer surfaces and social drafts than for APIs.
- **Concrete examples.**
  1. A formal policy memo containing "Key benefits include..."
  2. A technical report header reading "Architecture Overview"
  3. A news article body containing "The CEO confirmed the merger"
  4. (Per `[opus-expansion]`) An academic-style essay with section headers that begin with thematic emojis (rocket for "growth," lightbulb for "ideas," graph for "metrics") despite the publication context not warranting them.
- **Location and register.** Universal where emojis appear. Strongest signal when found in formal, technical, academic, journalistic, or business prose where the register is mismatched. Normal in social media, casual blogs, or intentionally informal content.
- **Model attribution.** Gemini family (HIGH; cross-link to A1-GEMINI-027). GPT-4o family (MEDIUM-HIGH on consumer surfaces). Claude family (LOW). DeepSeek (LOW).
- **Time evolution.** GPT-4o-era consumer surfaces peaked emoji usage in 2024; reducing in later versions. Gemini retains higher rates per Bloomberry AI 2026 observations.
- **Sources.** v3.1.0 criterion 14; `[chatgpt]`'s REVISE recommendation; `[claude-exec-2026-05-18]`'s REVISE recommendation.
- **Signal strength.** LOW for general AI detection. HIGH when context-mismatched (formal content with emojis).
- **Base rate.** Moderate in unedited Gemini and GPT-4o output for consumer or social-style prompts. Low elsewhere.
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling that scores "engaging" or "friendly" output higher. Secondary: training-data skew toward social-media and consumer-content corpora. Tertiary: system-prompt artifacts in consumer-surface tunings (Gemini consumer apps in particular).
- **Detection difficulty.** Easy. Visual scan.
- **False positive risk.** Low when context-mismatched. Moderate in genuinely informal contexts.
- **Fix or remediation.** Remove emojis from formal content. Retain in casual or social content if the register supports them.
- **Era status.** Active.
- **Zone tag.** HYBRID (wrapper and body).

---

### A3-SS-005: Markdown Formatting Mixed with Standard Text

- **Description.** Presence of Markdown syntax elements in published content that did not render. The content was generated for a Markdown-rendering channel and copy-pasted into a non-rendering one without translation. Very strong drafting-residue signal.
- **Concrete examples.**
  1. Asterisks for bold or italic appearing literally: `*emphasis*` or `**strong**`
  2. Underscores for emphasis: `_italic_`
  3. Hash symbols for headers appearing in body text: `## Section Title` as a line
  4. Backticks for code appearing literally: `` `inline code` ``
  5. Numbers with periods for lists when not rendered: `1. First item` `2. Second item`
  6. Triple backticks marking code blocks visibly: ` ``` `
- **Location and register.** Universal where it appears. Strongest tell in news articles, blog posts, and any rendered HTML or print publication context.
- **Model attribution.** All families. Gemini family (HIGH per `[claude-exec-2026-05-18]` A1-GEMINI-001 plain-text markdown leakage; cross-link to GitHub gemini-cli #8392). Claude family (MEDIUM). GPT (MEDIUM). Llama (MEDIUM per `[perplexity]`'s A1-LLAMA-017 markdown underuse, which is the inverse pattern).
- **Time evolution.** Stable across generations. Gemini formatting update per 9to5Google September 2025 changed defaults.
- **Sources.** v3.1.0 criterion 15; `[cross-validated:manus-ai+chatgpt+grok]`; GitHub gemini-cli #8392 per `[claude-exec-2026-05-18]`.
- **Signal strength.** HIGH.
- **Base rate.** Low to moderate; depends entirely on whether the channel renders Markdown.
- **Causal hypothesis (ranked).** Primary: training-data skew (LLMs are trained heavily on GitHub, Reddit, Discord, and other Markdown-rendering surfaces). Secondary: system-prompt defaults that request Markdown formatting regardless of channel.
- **Detection difficulty.** Easy.
- **False positive risk.** Very low when in a non-rendering channel.
- **Fix or remediation.** Translate to the target platform's formatting. Convert `**bold**` to actual bold tags or to plain text with quotation marks if no bold is available. Strip header hashes.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-SS-006: Curly vs. Straight Quotes

- **Description.** Inconsistent use of curly quotes (typographic apostrophes and quotation marks) versus straight quotes, or the wrong type for the context. Per `[chatgpt]`'s DEPRECATE recommendation: too toolchain-dependent and too weak as a modern provenance signal. The toolchain (text editor, copy-paste path, rendering target) determines quote style more than the model.
- **Concrete examples.**
  1. Curly quotes in a Markdown source file destined for a renderer that does not handle them.
  2. Straight quotes in a typeset book or magazine article where curly quotes are standard.
  3. Mixed quote styles within a single document.
- **Location and register.** Universal where the quote style is mismatched to the target.
- **Model attribution.** Per `[perplexity]`: primarily Gemini and formal-register outputs. Per `[chatgpt]`: too toolchain-dependent for reliable attribution.
- **Time evolution.** No reliable evolution; tied more to channel and editing pipeline than to model.
- **Sources.** v3.1.0 criterion 16; `[chatgpt]`'s DEPRECATE recommendation; `[perplexity]`'s REVISE.
- **Signal strength.** DEPRECATED (retained for archive per the compounding-archive principle). Effectively LOW.
- **Base rate.** Too channel-dependent for meaningful base rate.
- **Causal hypothesis (ranked).** Primary: tokenizer and rendering pipeline. Secondary: training-data quote-style mix. Tertiary: editor and channel translation gaps.
- **Detection difficulty.** Easy when present.
- **False positive risk.** High. Many human-written documents have mixed quote styles for the same toolchain reasons.
- **Fix or remediation.** Apply consistent quote style per the target channel. Use the channel's standard conversion tools rather than relying on model output.
- **Era status.** Deprecated. Retained for archival use only.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-SS-007: Title Case in Headers and Nominalization Cascade

- **Description.** Section headers capitalize every major word (Title Case) instead of using sentence case, especially in journalism contexts. The v3.1.0 criterion 17 combined this with the nominalization-cascade concept; v4.0 separates the title-case aspect (A3-SS-007) from the nominalization-cascade aspect (A3-LT-012) for clarity. Per `[chatgpt]`'s DEMOTE: publishing-style dependent; weak standalone evidence. Per `[perplexity]`'s REVISE: primarily Gemini and formal-register outputs.
- **Concrete examples.**
  1. AI default: "The Evolution Of Modern Technology" (every major word capitalized).
  2. Journalism standard: "The evolution of modern technology" (sentence case).
  3. AI default: "How To Optimize Your Workflow For Maximum Productivity"
  4. AI default: "Five Key Insights From The Latest Industry Report"
- **Location and register.** Section headers and subheaders. Strongest tell when found in journalism or web-content contexts where sentence case is the standard.
- **Model attribution.** Gemini family (HIGH per `[perplexity]`). GPT-4o family (MEDIUM-HIGH). Claude family (MEDIUM). Llama (LOW).
- **Time evolution.** Stable. Reflects training-data exposure to academic and marketing prose, which use title case heavily.
- **Sources.** v3.1.0 criterion 17; `[chatgpt]` DEMOTE; `[perplexity]` REVISE.
- **Signal strength.** LOW (demoted from MED). HIGH when context-mismatched (journalism context with title-case headers).
- **Base rate.** Moderate to high in unedited AI output for content with headers. Lower in casual or social formats.
- **Causal hypothesis (ranked).** Primary: training-data skew toward academic, marketing, and SEO content where title case is conventional. Secondary: system-prompt defaults.
- **Detection difficulty.** Easy. Visual scan of header capitalization.
- **False positive risk.** Moderate. Marketing and academic contexts legitimately use title case.
- **Fix or remediation.** Apply the target publication's house style for header capitalization. Most journalism, blogs, and modern web content use sentence case.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-SS-008: En-Dash Overuse as Em-Dash Replacement

- **Description.** Emerging pattern in models where em-dash use has been tuned down. As GPT-5.1's anti-em-dash personalization rolled out, some output shifted to en-dashes (Unicode U+2013) for the same parenthetical-substitute function. The substitution is detectable because en-dashes have a narrower legitimate use (ranges, compound modifiers) than the broader parenthetical role they have begun to fill. Per the Claude expansion's A3-NEW-004.
- **Concrete examples.**
  1. Mid-sentence en-dashes substituting for the em-dash function: "The team, despite the resource constraints, delivered the feature on schedule" where the original output used en-dashes around the parenthetical.
  2. En-dash between independent clause and appositive: "There are three concerns: cost, complexity, and time" rendered with en-dashes instead.
- **Location and register.** Universal. Densest in GPT-5.1+ analytical prose.
- **Model attribution.** GPT-5.1+ primarily; emerging in other families that have personalized against em-dashes.
- **Time evolution.** New as of 2025 with GPT-5.1's anti-em-dash rollout.
- **Sources.** Claude expansion's A3-NEW-004; `[opus-expansion]`.
- **Signal strength.** MEDIUM (emerging).
- **Base rate.** Low but growing.
- **Causal hypothesis (ranked).** Primary: RLHF personalization (GPT-5.1's explicit em-dash penalty) without retraining the underlying use case, causing the model to substitute the nearest-shape character. Secondary: tokenizer effects (en-dash is also a single token).
- **Detection difficulty.** Easy. Character search for U+2013 in non-range contexts.
- **False positive risk.** Moderate. En-dashes have legitimate uses (number ranges, compound modifiers); the discriminator is en-dashes in clearly parenthetical positions.
- **Fix or remediation.** Replace with commas, parentheses, colons, or sentence breaks, same as for em-dashes.
- **Era status.** Active (emerging in 2025-2026).
- **Zone tag.** BODY-PERSISTENT.

---

### A3-SS-009: Over-Consistent Paragraph Rhythm Across Genres

- **Description.** Visual and syntactic uniformity that survives genre shift. The same paragraph rhythm appears whether the model is writing a recipe, a code explanation, or a legal analysis. Sibling to A3-LT-010 (uniform sentence and paragraph length) but distinct in that it focuses on cross-genre persistence rather than within-document homogeneity. Per `[grok]`'s Criterion 44.
- **Concrete examples.** This is a cross-document pattern best seen by comparing the model's output for prompts of different genres. A recipe in 3-to-5-sentence paragraphs; a code explanation in 3-to-5-sentence paragraphs; a legal analysis in 3-to-5-sentence paragraphs. Human writers shift rhythm to match the genre.
- **Location and register.** Universal across genres in unedited AI output.
- **Model attribution.** All families. Most pronounced in Claude and GPT.
- **Time evolution.** Stable; reflects underlying generation strategy.
- **Sources.** `[grok]`'s Criterion 44.
- **Signal strength.** MEDIUM.
- **Base rate.** High in unedited AI output across multi-genre samples.
- **Causal hypothesis (ranked).** Primary: tokenizer and architecture effects. Secondary: training-data skew toward moderate-paragraph-length prose across genres. Tertiary: RLHF reward modeling for readability that converges on a single rhythm.
- **Detection difficulty.** Hard. Requires distribution analysis across multiple documents.
- **False positive risk.** Moderate. Some skilled writers maintain consistent rhythm across genres as a stylistic choice.
- **Fix or remediation.** Deliberately vary rhythm by genre. Short, punchy paragraphs for recipes; longer for legal analysis; varied for technical explanation.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.


---

## Section A3-TF: Technical and Formatting

### A3-TF-001: Placeholder Text and Incomplete Elements

- **Description.** Bracketed placeholders or unfilled template tokens left in published content. A user copied AI-generated text with placeholders they were supposed to fill in but forgot. Very strong drafting-residue signal.
- **Concrete examples.**
  1. `[Insert source here]`
  2. `[Add specific example]`
  3. `[URL of reliable source]`
  4. `[Citation needed]`
  5. `[Date]`
  6. `:contentReference[oaicite:0]` (XML-like ChatGPT artifact variant)
- **Location and register.** Universal where it appears. Strongest tell in any published content.
- **Model attribution.** All families. Sometimes ChatGPT's `oaicite` artifacts are the most distinctive.
- **Time evolution.** Stable.
- **Sources.** v3.1.0 criterion 18; `[cross-validated:manus-ai+perplexity+chatgpt]`. Perplexity recommends adding burstiness metric below 0.30 as a paired check.
- **Signal strength.** HIGH.
- **Base rate.** Low overall but definitive when present.
- **Causal hypothesis (ranked).** Primary: drafting workflow gap (user copied output without filling in placeholders). Secondary: training-data skew toward template-style outputs.
- **Detection difficulty.** Easy. Grep for bracket patterns.
- **False positive risk.** Very low when in published content.
- **Fix or remediation.** Fill in the placeholders or remove the bracketed text and restructure the paragraph.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-TF-002: Chatbot Communication Artifacts

- **Description.** Text that includes meta-communication between the chatbot and user, leaked into the published artifact. Includes salutations, valedictions, knowledge cutoff disclaimers, instructions to the user, offers to assist further. Cross-references A1-CLAUDE-009 ("I appreciate your" openers), A1-CLAUDE-011 ("I hope this helps" closer), A1-CLAUDE-013 (concierge tone closer), A1-GPT-009 ("In conclusion" closer), and A1-GPT-021 (knowledge-cutoff disclaimer, declining).
- **Concrete examples.**
  1. Salutation: "Dear [Reader]," or "Hello!"
  2. Valediction: "Thank you for your time and consideration."
  3. Instructions to user: "Here is your article on [topic]:"
  4. Knowledge cutoff: "As of my last training update in [date]..."
  5. Disclaimer: "Please consult a professional before..."
  6. Offer to assist: "If you have any questions or need further clarification, feel free to ask!"
- **Location and register.** Universal where it appears. Strongest tell in any published content (article, blog post, report) where the wrapper has leaked through.
- **Model attribution.** All families. Claude family particularly distinctive for "I hope this helps" closers and "I appreciate your" openers. GPT family for "Certainly!" openers and "Sure! Here's how..." framings. Gemini for "Without further ado" openers. Llama for "I'm just an AI, so take this with a grain of salt" disclaimers per `[deepseek]`. Grok for "I'm Grok, an AI by xAI. I'll keep it real."
- **Time evolution.** "As an AI language model" preamble near-extinct in current frontier models (Historical era status; persisted in GPT-3.5 and early GPT-4 2022-2024). "I hope this helps" persists. April 2025 OpenAI sycophancy rollback measurably reduced GPT's wrapper density.
- **Sources.** v3.1.0 criterion 19; `[cross-validated:manus-ai+perplexity+chatgpt+grok]`. Per `[perplexity]`: cross-link to A1-CLAUDE-020 (elevated vocabulary register) and A1-GPT-001 (saturated AI vocabulary cluster).
- **Signal strength.** HIGH. Among the clearest wrapper leaks in published prose.
- **Base rate.** Low in published content if the editor has done basic cleanup; high in raw output.
- **Causal hypothesis (ranked).** Primary: product wrapper personalization and RLHF helpfulness optimization. Secondary: training-data skew toward customer-service and dialogue corpora. Tertiary: system-prompt artifacts.
- **Detection difficulty.** Easy. Grep for the inventory.
- **False positive risk.** Very low. The phrases are characteristic of chatbot wrappers, not professional writing.
- **Fix or remediation.** Strip the openers and closers. Get into the substance. End on the substance.
- **Era status.** Active for most patterns. Historical for "As an AI language model" (declined after early-2024 RLHF updates).
- **Zone tag.** WRAPPER-OPENER for openers and salutations; WRAPPER-CLOSER for valedictions, "I hope this helps," and concierge closers.

---

### A3-TF-003: Broken or Fabricated Links and Technical Codes

- **Description.** Links, DOIs, ISBNs, or other technical identifiers that do not resolve or are invalid. LLMs hallucinate citations that look credible but do not actually exist. Cross-references A3-CS-001 (hallucinated citations) and A3-CS-003 (retrieval-citation mismatch). Per `[chatgpt]`'s PROMOTE recommendation: wrapper artifacts, fake URLs, and citation errors remain common; the criterion in v3.1.0 was about phrase repetition; v4.0 expands to include broken or fabricated links and technical codes.
- **Concrete examples.**
  1. URL leading to a 404 error.
  2. DOI that does not resolve to any article.
  3. ISBN with invalid checksum.
  4. Generic placeholder link: `[Link to source]`
  5. ChatGPT-specific artifact "turn0search0"
  6. (Per `[claude-exec-2026-05-18]`) Fabricated arxiv ID with plausible format but no underlying paper.
- **Location and register.** Universal where citations appear. Densest in research-style, journalistic, and policy prose.
- **Model attribution.** All families. Claude family (DOI fabrication per the bucket C catalog). GPT family (URL fabrication). Gemini (vague attribution per A1-GEMINI-002).
- **Time evolution.** Stable to growing. Per `[chatgpt]` and Stanford RegLab measurements: 17 to 33 percent legal-AI hallucination rates even with RAG augmentation persist into 2026.
- **Sources.** v3.1.0 criterion 20; Stanford RegLab / Magesh et al. (2024); Damien Charlotin database (2025) of over 1,455 sanctioned legal cases involving AI-fabricated citations; `[chatgpt]` PROMOTE.
- **Signal strength.** HIGH.
- **Base rate.** High in unedited AI output for research-style prompts. Per Walters and Wilder (2023): 30 to 55 percent hallucination rates in GPT-3.5; 18 to 29 percent in GPT-4 (cited from `[claude-exec-2026-05-18]`'s reference list). Per Chelli et al. (2024) JMIR: 56 percent error rate among GPT-4o citations.
- **Causal hypothesis (ranked).** Primary: training data lacks reliable signals for citation validity. Secondary: generative defaults under benchmark pressure (the model would rather produce a plausible-looking citation than admit ignorance). Tertiary: helpfulness optimization.
- **Detection difficulty.** Easy. Click links, verify DOIs resolve, check ISBNs with checksum validators.
- **False positive risk.** Very low when the link or identifier does not resolve.
- **Fix or remediation.** Verify every link and identifier before publication. Replace fabricated citations with real ones or remove the claim that required citation.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-TF-004: Citation Abnormalities

- **Description.** References that appear legitimate but reveal AI generation upon inspection. Citations repeated without proper reference tagging, real sources cited for unrelated content, citations formatted in unusual or inconsistent styles, multiple identical citations in close proximity. Cross-references A3-CS-001 (hallucinated citations) and A3-CS-002 (vague attribution).
- **Concrete examples.**
  1. Multiple identical citations in close proximity rather than using a single citation or cross-referencing.
  2. Real source cited for completely unrelated content (the citation exists but does not support the claim being made).
  3. Citation formatting inconsistent across the document (mix of APA, MLA, Chicago).
  4. Generic citations: "According to experts..." without naming experts.
  5. (Per Stanford RegLab) Real case law cited for a holding the case did not establish.
- **Location and register.** Body paragraphs. Densest in legal, academic, policy, and research-style prose.
- **Model attribution.** All families. Stanford RegLab measured 17 to 33 percent hallucination rates even with RAG-augmented legal AI.
- **Time evolution.** Stable to growing per `[chatgpt]`'s and DeepSeek's PROMOTE recommendation: retrieval-era source theater makes this more load-bearing.
- **Sources.** v3.1.0 criterion 21; Stanford RegLab / Magesh et al. (2024); Damien Charlotin database (2025).
- **Signal strength.** HIGH (promoted from MED).
- **Base rate.** Per Stanford RegLab: 17 to 33 percent legal AI hallucination rates even with RAG.
- **Causal hypothesis (ranked).** Primary: training data quality for citation correctness is low. Secondary: generative defaults under benchmark pressure. Tertiary: helpfulness optimization (the model produces a plausible citation when uncertain).
- **Detection difficulty.** Medium. Requires checking whether the cited source actually supports the claim.
- **False positive risk.** Low when the citation does not support the claim.
- **Fix or remediation.** Verify every citation supports the claim it is cited for. Replace or remove unsupported citations.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-TF-005: Suspiciously Long Edit Summaries and Caveat Paragraphs

- **Description.** In platforms with edit tracking (Wikipedia, GitHub commits, Google Docs revision history), unusually long, formal edit summaries written in first-person paragraphs. Human editors typically write brief, informal edit summaries; LLMs generate formal, comprehensive summaries when prompted to explain changes. The v4.0 entry extends the criterion to include "caveat paragraphs" appended at the end of articles, which serve a similar register-mismatch function. Per `[chatgpt]`'s REVISE: scope narrowly to platforms where edit summaries have stable norms. Per `[perplexity]`: most pronounced in GPT-4o A1-GPT-015 (caveat paragraph appended at end); reducing in Claude 4.
- **Concrete examples.**
  1. (Wikipedia-style) "Refined the language of the article for a neutral, encyclopedic tone consistent with content guidelines. Removed promotional wording, ensured factual accuracy, and maintained a clear, well-structured presentation."
  2. (Caveat paragraph) "It is important to note that this analysis is based on publicly available information and may not reflect the full complexity of the situation. Readers are encouraged to consult additional sources and exercise their own judgment."
  3. (Per `[claude-exec-2026-05-18]`) Disclaimer paragraph appended at the end of a technical article that the article's content did not warrant.
- **Location and register.** Edit summaries on tracked platforms; article closers for the caveat-paragraph variant.
- **Model attribution.** GPT-4o family (HIGH for caveat paragraphs per `[perplexity]`'s A1-GPT-015). Claude family (MEDIUM, reducing in Claude 4 per `[perplexity]`). Wikipedia editor catalog includes the pattern as a primary AI tell.
- **Time evolution.** Stable for Wikipedia edit summaries. Caveat paragraphs peaking in GPT-4o; reducing in newer versions.
- **Sources.** v3.1.0 criterion 22; `[chatgpt]` REVISE; `[perplexity]` REVISE; WikiProject AI Cleanup methodology.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate on Wikipedia and GitHub for tracked edits. Moderate in GPT-4o caveat closers.
- **Causal hypothesis (ranked).** Primary: training data exposure to formal editing prose (Wikipedia talk pages, GitHub commit conventions). Secondary: RLHF reward modeling for "comprehensive" explanations. Tertiary: system prompt artifacts on platforms that request edit summaries.
- **Detection difficulty.** Easy. Visual scan of length and formality.
- **False positive risk.** Moderate. Some careful human editors write thorough edit summaries.
- **Fix or remediation.** For edit summaries: shorten to a few words describing the change. For caveat paragraphs: remove unless the article genuinely needs limitations stated, in which case integrate the limitations into the relevant sections.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER for caveat paragraphs; outside the main artifact for edit summaries.

---

### A3-TF-006: System-Prompt Artifact Bleed

- **Description.** Phrases like "You are a helpful AI assistant" or visible system-prompt fragments leaking into output. Distinct from A3-TF-002 (chatbot communication artifacts) which are downstream wrapper artifacts; this is the upstream system-prompt configuration appearing literally. Per the Claude expansion's A3-NEW-010.
- **Concrete examples.**
  1. "You are a helpful AI assistant designed to provide accurate and thoughtful responses."
  2. (Per `[opus-expansion]`) Text beginning with the literal opening "As [persona name], I will..."
  3. "Your task is to..." appearing literally in published output where it was meant to be a system-level instruction.
  4. (Per `[claude-exec-2026-05-18]`) Visible role descriptions like "[ROLE: Senior Editor]" left in published copy.
- **Location and register.** Universal where it appears. Strongest tell at the very start of an article or response.
- **Model attribution.** All families. Most common when users are inexperienced with prompt engineering or when API requests have malformed system messages.
- **Time evolution.** Stable. The pattern depends more on user error than on model behavior.
- **Sources.** Claude expansion's A3-NEW-010; `[opus-expansion]`.
- **Signal strength.** HIGH (rare but definitive).
- **Base rate.** Low. Most production deployments suppress system-prompt leakage. Higher in self-hosted and developer-tool deployments.
- **Causal hypothesis (ranked).** Primary: system-prompt configuration error or copy-paste mishap. Secondary: model failure to distinguish between system context and user-facing output.
- **Detection difficulty.** Easy when visible.
- **False positive risk.** Very low.
- **Fix or remediation.** Remove the leaked content. Fix the upstream system-prompt configuration.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER.

---

### A3-TF-007: Date Inconsistency and Knowledge-Cutoff Contradiction

- **Description.** References to "current" dates that contradict the model's knowledge cutoff or release date; useful for forensic dating of outputs. The model claims to be discussing recent events but cites no source for events after its training data cutoff, or it describes 2026 events as "recent" when it was trained on data only through early 2025. Per the Claude expansion's A3-NEW-011.
- **Concrete examples.**
  1. A model with a knowledge cutoff in 2024 describing a 2026 event as "recent" without external retrieval context.
  2. Author bio claiming "as of [year]" where the year is later than the model's cutoff.
  3. (Per `[opus-expansion]`) Article references a "recent study" without naming it, in a context where the model could not have known about studies after its cutoff.
  4. (Per `[claude-exec-2026-05-18]`) Inconsistent date references within a single document (some dates from 2024, others from 2026) suggesting the model is fabricating temporal context.
- **Location and register.** Universal. Most useful in content claiming currency or recency.
- **Model attribution.** All families. Most pronounced when the model is asked to produce time-sensitive content without retrieval augmentation.
- **Time evolution.** Persistent. Newer models have later cutoffs but the pattern recurs whenever the writer asks for content beyond the cutoff.
- **Sources.** Claude expansion's A3-NEW-011; `[opus-expansion]`.
- **Signal strength.** MEDIUM. HIGH when paired with specific fabricated facts (cross-link to A3-TF-003).
- **Base rate.** Moderate in content with explicit "current" or "recent" framings.
- **Causal hypothesis (ranked).** Primary: knowledge cutoff staleness. Secondary: helpfulness optimization (the model would rather produce "current" content than acknowledge the cutoff). Tertiary: generative defaults under benchmark pressure.
- **Detection difficulty.** Medium. Requires cross-referencing dates against the model's known cutoff.
- **False positive risk.** Moderate. Some content legitimately uses approximate or evolving dates.
- **Fix or remediation.** Verify dates against the model's cutoff. For genuinely current content, use retrieval augmentation; for content within the cutoff window, ensure dates align.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.


---

## Section A3-CS: Citation and Sourcing

### A3-CS-001: Hallucinated Citations

- **Description.** Fabricated sources, misattributed quotes, non-existent journal articles with plausible-sounding titles. Among the most dangerous AI content problems because the citations appear authoritative while spreading misinformation. Cross-references A3-TF-003 (broken or fabricated links), A3-TF-004 (citation abnormalities), and A3-CS-003 (retrieval-citation mismatch). See `synthesis-fact-checking` v2.0 for the full verification protocol.
- **Concrete examples.**
  1. Plausible-sounding but non-existent journal article title with fabricated authors.
  2. Real authors paired with a paper they did not write.
  3. (Per Walters and Wilder 2023) GPT-3.5 hallucinated citation rate of 30 to 55 percent in scientific writing prompts.
  4. (Per Chelli et al. 2024 JMIR) GPT-4o 56 percent citation error rate.
  5. (Per Stanford RegLab) Legal AI 17 to 33 percent hallucination rate even with RAG.
  6. (Per Damien Charlotin database) Over 1,455 sanctioned legal cases involving AI-fabricated citations as of 2025.
- **Location and register.** Body paragraphs. Densest in research-style, journalistic, legal, and policy prose.
- **Model attribution.** All families. Claude family particularly prone to DOI fabrication. GPT family prone to URL fabrication. Gemini prone to vague attribution. Bard (Historical, 2023) measured at 91 percent citation hallucination rate at launch.
- **Time evolution.** GPT-3.5 (Historical): 30 to 55 percent. GPT-4 (Historical): 18 to 29 percent. Bard (Historical): 91 percent. GPT-4o (current-era declining): 56 percent. Legal AI with RAG (current): 17 to 33 percent. Despite improvements, the criterion has not been solved.
- **Sources.** v3.1.0 criterion 23; Walters and Wilder (2023); Chelli et al. (2024); Stanford RegLab / Magesh et al. (2024); Damien Charlotin database (2025); `[chatgpt]`, `[deepseek]`, and `[claude-exec-2026-05-18]` all PROMOTE.
- **Signal strength.** HIGH.
- **Base rate.** See time-evolution measurements above.
- **Causal hypothesis (ranked).** Primary: training data quality for citation correctness is fundamentally weak. Secondary: generative defaults under benchmark pressure (the model would rather produce a plausible citation than admit ignorance). Tertiary: helpfulness optimization.
- **Detection difficulty.** Medium. Requires verifying each citation against the actual source.
- **False positive risk.** Very low when the citation is verified to not exist or to misattribute.
- **Fix or remediation.** Verify every citation before publication. Replace fabricated citations with real ones or remove the underlying claim.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-CS-002: Vague Attribution to Unnamed Authorities

- **Description.** Claims attributed to generic, unnamed sources: "Experts say," "Studies have shown," "Research indicates," "Analysts believe," "Industry leaders suggest." Distinct from A3-CS-001 (hallucinated citations) which fabricates specific sources; this is the broader pattern of unnamed appeal to authority. Cross-references A1-GEMINI-002 (the Gemini-characteristic "studies show" without identifiers) and A3-CS-006 (generic authority laundering).
- **Concrete examples.**
  1. "Experts say this approach is the most effective."
  2. "Studies have shown a strong correlation."
  3. "Research indicates significant improvement."
  4. "Analysts believe the trend will continue."
  5. "Industry leaders suggest this is the future of the field."
  6. (Per `[grok]`'s A3-NEW-033) "Recent studies have demonstrated..."
- **Location and register.** Body paragraphs. Densest in journalism, business writing, and policy prose.
- **Model attribution.** Gemini family (HIGH; cross-link to A1-GEMINI-002). Claude family (MEDIUM-HIGH). GPT family (MEDIUM-HIGH).
- **Time evolution.** Stable. Cross-family persistence per `[claude-exec-2026-05-18]`'s analysis.
- **Sources.** v3.1.0 criterion 24; `[claude-exec-2026-05-18]` PROMOTE; A1-GEMINI-002.
- **Signal strength.** HIGH (promoted from MED). Criterion now load-bearing for Gemini family attribution.
- **Base rate.** High in unedited AI output for argumentative or thesis-driven prompts.
- **Causal hypothesis (ranked).** Primary: training data exposure to journalistic and corporate prose where vague attribution is conventional. Secondary: helpfulness optimization (the model wants to support claims but lacks specific sources). Tertiary: generative defaults under benchmark pressure.
- **Detection difficulty.** Easy. Grep for the inventory ("experts say," "studies show," "research indicates").
- **False positive risk.** Moderate. Some legitimate journalism uses these phrases when specific attribution is unavailable; the discriminator is whether the writer could have provided specific attribution.
- **Fix or remediation.** Replace with specific attribution: name the experts, name the studies, link to the research. If specific attribution is not available, remove the claim or qualify it appropriately.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-CS-003: Retrieval-Citation Mismatch

- **Description.** A cited page exists, but it is a redirect, a copied version, or a syndicated source rather than the claimed original. This now appears often enough in AI search systems to deserve its own content-quality criterion as well as a fact-checking protocol. Per `[chatgpt]`'s A3-NEW-024. Cross-link to bucket C URL-rot vs hallucination protocol.
- **Concrete examples.**
  1. Citation links to a content aggregator's repost of a New York Times article, not to the original article.
  2. Citation links to a Wayback Machine archive when the original URL is alive but the model retrieved the archive.
  3. (Per `[chatgpt]`) Citation links to a syndicated press release on a third-party site rather than the company's original announcement.
  4. (Per `[opus-expansion]`) Citation links to a translated version on a different language site, where the translation introduces drift.
- **Location and register.** Citations in retrieval-augmented or search-grounded AI output.
- **Model attribution.** All retrieval-augmented systems (Perplexity AI, Claude with search, ChatGPT with browsing, Gemini with grounding).
- **Time evolution.** Active and growing as more retrieval-augmented systems deploy.
- **Sources.** `[chatgpt]`'s A3-NEW-024; cross-link to bucket C URL-rot vs hallucination protocol.
- **Signal strength.** MEDIUM-HIGH.
- **Base rate.** Moderate in retrieval-augmented output.
- **Causal hypothesis (ranked).** Primary: retrieval system returning a redirect or syndication target rather than the original. Secondary: model not verifying that the retrieved URL is the canonical source. Tertiary: training-data skew toward aggregator and syndication sites.
- **Detection difficulty.** Medium. Requires checking that the cited URL is the canonical original.
- **False positive risk.** Low when the mismatch is verified.
- **Fix or remediation.** Update the citation to the canonical original source. Verify retrieval-augmented citations resolve to the actual primary source.
- **Era status.** Active (growing).
- **Zone tag.** BODY-PERSISTENT.

---

### A3-CS-004: Source-Theater Abundance

- **Description.** Many sources are named or linked, but the prose never binds them to argument, mechanism, or judgment. The writer (or model) is performing the appearance of sourcing without engaging with the sources' content. Sibling to A2-SUB-014 (evidence displacement). Per `[chatgpt]`'s A3-NEW-027.
- **Concrete examples.**
  1. An article cites ten studies in a single paragraph without analyzing any of their findings or methodologies.
  2. Each paragraph closes with a citation, but the citations support claims that are too general to be informative.
  3. (Per `[chatgpt]`) A footer reference list of 30+ sources, but the body text engages with only two or three of them.
  4. (Per `[opus-expansion]`) Inline citations to authors who are named but whose specific contributions are not discussed.
- **Location and register.** Body paragraphs. Densest in research-style and academic-adjacent AI output.
- **Model attribution.** All families. Most pronounced in retrieval-augmented and academic-style prompts.
- **Time evolution.** Active and growing as retrieval-augmented systems scale.
- **Sources.** `[chatgpt]`'s A3-NEW-027.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate in research-style AI output.
- **Causal hypothesis (ranked).** Primary: training data exposure to citation-heavy academic prose. Secondary: helpfulness optimization (the model wants to demonstrate that it has done the research). Tertiary: generative defaults under benchmark pressure for citation density.
- **Detection difficulty.** Medium. Requires reading the citations and verifying they support the prose's argument.
- **False positive risk.** Moderate. Some legitimate academic writing has citation density without deep engagement; the discriminator is whether the writer engages with the cited content's substance.
- **Fix or remediation.** Cut citations that do not bind to argument or mechanism. Replace with engagement: name the specific contribution, analyze the methodology, contrast with other sources.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-CS-005: Synthetic-Source Contamination

- **Description.** The source itself is AI-generated or recursively derivative. This is no longer hypothetical given the scale of AI-authored web content. Per `[chatgpt]`'s A3-NEW-029. Cross-link to bucket C AI-generated synthetic sources protocol.
- **Concrete examples.**
  1. Article cites a "study" that turns out to be an AI-generated summary on a content farm.
  2. Article cites a "blog post" by an author who does not exist (LinkedIn profile is also AI-generated).
  3. (Per `[chatgpt]`) Citation to a "research report" by a "think tank" that has no human staff.
  4. (Per `[opus-expansion]`) Wikipedia citation traces to a paragraph that was added by an AI-edit (per WikiProject AI Cleanup observations).
- **Location and register.** Citations in any AI-augmented or AI-generated content.
- **Model attribution.** All families. The risk is in the source ecosystem, not the citing model.
- **Time evolution.** Active and rapidly growing. WikiProject AI Cleanup work documents the scale on Wikipedia specifically.
- **Sources.** `[chatgpt]`'s A3-NEW-029; WikiProject AI Cleanup methodology.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate and growing.
- **Causal hypothesis (ranked).** Primary: scale of AI-authored web content. Secondary: retrieval systems indexing AI-generated content without distinguishing it from human-authored content. Tertiary: content-farm SEO optimization.
- **Detection difficulty.** Hard. Requires investigating the source's provenance.
- **False positive risk.** Moderate. Some human-authored content is mistaken for AI-generated; the discriminator is documented provenance.
- **Fix or remediation.** Verify source provenance. Prefer sources with verifiable human authorship and editorial oversight.
- **Era status.** Active (rapidly growing).
- **Zone tag.** BODY-PERSISTENT.

---

### A3-CS-006: Generic Authority Laundering

- **Description.** Vague attribution to "leading experts" or "recent studies" used without traceable attribution. Sibling to v3.1.0 criterion 24 (A3-CS-002) and A1-GEMINI-002. Per `[grok]`'s A3-NEW-033. The distinction from A3-CS-002 is the specific framing of "leading," "top," "renowned," or "preeminent" experts and "groundbreaking," "landmark," or "comprehensive" studies, which adds an authority-laundering layer to the vague attribution.
- **Concrete examples.**
  1. "Leading experts in the field agree that..."
  2. "Top industry analysts have concluded that..."
  3. "A landmark study has shown that..."
  4. "Preeminent researchers have demonstrated..."
  5. (Per `[grok]`) "Renowned authorities have established that..."
- **Location and register.** Body paragraphs. Densest in argumentative, thought-leadership, and SEO-optimized content.
- **Model attribution.** All families. GPT-4o family (HIGH for this surface form). Gemini and Claude (MEDIUM).
- **Time evolution.** Stable.
- **Sources.** `[grok]`'s A3-NEW-033; cross-link to A3-CS-002.
- **Signal strength.** MEDIUM.
- **Base rate.** High in unedited AI output for thought-leadership or argumentative prompts.
- **Causal hypothesis (ranked).** Primary: training data exposure to SEO and thought-leadership content where authority laundering is conventional. Secondary: RLHF reward modeling that scores authority-claiming prose higher. Tertiary: helpfulness optimization.
- **Detection difficulty.** Easy. Grep for the inventory ("leading experts," "top analysts," "landmark study," "preeminent").
- **False positive risk.** Moderate. Some legitimate writing uses authority qualifiers; the discriminator is whether the authority is named.
- **Fix or remediation.** Replace with named attribution. "Leading experts" becomes the specific names; "landmark study" becomes the named study with year and journal.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.


---

## Section A3-CX: Context-Specific

### A3-CX-001: Industry-Specific Slop Patterns

- **Description.** Domain-characteristic AI patterns that recur across content in a given industry. Different domains show different default vocabularies. Per `[chatgpt]`'s REVISE and `[claude-exec-2026-05-18]`'s REVISE: split by genre in v4.0, especially technical docs, business copy, and social posts.
- **Concrete examples.** Examples are organized by industry domain because the slop inventory is domain-specific.

  **Technology writing.**
  - "Innovative," "cutting-edge," "revolutionary"
  - "Robust," "scalable," "flexible"
  - "Game-changing," "paradigm shift"
  - Buzzword clustering without substance

  **Travel and lifestyle.**
  - "Hidden gem," "off the beaten path"
  - "Picturesque," "charming," "quaint"
  - "Must-see destinations"
  - Generic itinerary patterns

  **Business and corporate.**
  - "Synergy," "leverage," "optimize"
  - "Strategic," "value-add," "best-in-class"
  - Mission statement language throughout

  **Product reviews.**
  - Uniformly positive tone
  - Generic praise without specific details
  - Comparison without actual product experience

  **AI thought leadership (new in v4.0).**
  - "Transformative AI," "AI-powered," "AI-native"
  - "The future of work," "the next frontier"
  - "Responsible AI," "ethical AI deployment"
  - "Human-in-the-loop," "AI-augmented workflow"

  **Healthcare and wellness (new in v4.0).**
  - "Holistic approach," "evidence-based"
  - "Personalized care," "patient-centered"
  - "Mind-body connection," "wellness journey"

- **Location and register.** Body paragraphs throughout. Strongest in trade publications, industry blogs, and SEO-optimized content.
- **Model attribution.** All families. The slop is industry-specific, not model-specific, because training data exposure to industry corpora is broadly similar across models.
- **Time evolution.** Vocabulary evolves with industry trends. AI-thought-leadership slop is new in 2024-2026; healthcare slop has been stable.
- **Sources.** v3.1.0 criterion 25; `[chatgpt]` REVISE; `[claude-exec-2026-05-18]` REVISE.
- **Signal strength.** MEDIUM.
- **Base rate.** High in unedited AI output for industry-specific prompts.
- **Causal hypothesis (ranked).** Primary: training data exposure to industry corpora. Secondary: RLHF reward modeling that scores "professional" or "domain-appropriate" output higher. Tertiary: helpfulness optimization that mimics the register of the industry.
- **Detection difficulty.** Easy with industry-specific grep lists.
- **False positive risk.** Moderate. Industry writers use industry vocabulary; the discriminator is the density and whether the vocabulary is functioning as substance or as filler.
- **Fix or remediation.** Replace buzzwords with concrete descriptions. "Cutting-edge technology" becomes the specific technical capability. "Holistic approach" becomes the specific scope and integration.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-CX-002: Lack of Personal Detail, Experience, or Specificity

- **Description.** Generic descriptions without specific examples, personal anecdotes, or experiential details. Humans who have experienced something provide specific sensory details, personal reactions, and concrete examples; AI generalizes. Cross-references A3-FA-001 (insider context collapse) which catches the opposite direction (writing too specific to the writer's frame for the reader to land on). Per `[claude-exec-2026-05-18]`'s PROMOTE: reliable across families.
- **Concrete examples.**
  1. AI: "The restaurant offers excellent service and a diverse menu featuring both traditional and innovative dishes."
  2. Human: "The waiter recommended the braised short rib after learning I don't eat seafood. The meat fell apart at the touch of my fork, and the red wine reduction had a subtle coffee undertone that lingered."
  3. AI: "The conference brought together leading thinkers from across the industry, fostering productive discussions and meaningful connections."
  4. Human: "Sarah pulled me aside during the coffee break to tell me her team had given up on the same architecture I was about to defend. We ended up rebuilding our slides together over lunch."
- **Location and register.** Body paragraphs. Strongest in feature, profile, and review writing.
- **Model attribution.** All families. Per `[claude-exec-2026-05-18]`: reliable across families.
- **Time evolution.** Stable. The pattern reflects a fundamental limit of LLMs without specific personal context.
- **Sources.** v3.1.0 criterion 26; `[claude-exec-2026-05-18]` PROMOTE; `[chatgpt]` notes expert documentation may legitimately omit personal detail.
- **Signal strength.** HIGH (promoted from MED) with caveat. The caveat: expert technical documentation may legitimately omit personal detail because the value is in the technical content, not the experiential context.
- **Base rate.** High in unedited AI output for feature, profile, or review prompts.
- **Causal hypothesis (ranked).** Primary: training data does not include the specific personal context the writer would have. Secondary: helpfulness optimization (the model produces a complete-sounding response with generalized content). Tertiary: RLHF reward modeling that scores polished generic prose higher than specific imperfect prose.
- **Detection difficulty.** Medium. Requires reading for specificity rather than spotting a phrase.
- **False positive risk.** Moderate. Some legitimate writing is appropriately generic; the discriminator is whether the genre warrants specifics and whether the writer could have provided them.
- **Fix or remediation.** Add specific sensory details, personal reactions, and concrete examples. Replace generic descriptors with specific ones.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-CX-003: Superficial Depth Without Expertise

- **Description.** Content covers a topic broadly without demonstrating actual understanding or expertise. Restates common knowledge without original insight; uses technical terms correctly but superficially; avoids controversial or nuanced aspects; provides "both sides" artificially balanced treatment; lacks specific examples, case studies, or detailed analysis. v4.0 promotes this criterion to section A2 (substance and depth detection) as a full top-level section with sub-patterns. This entry remains here as a pointer to the section.
- **Sub-patterns (now in A2).**
  - A2-SUB-001: The deletion test (does removing the sentence change the meaning?)
  - A2-SUB-002: The specificity test (could this sentence be true of any company in any era?)
  - A2-SUB-003: Load-bearing claim count per paragraph
  - A2-SUB-004: Novelty signal (does this say something that requires expertise?)
  - A2-SUB-005: Insight-to-word ratio
  - A2-SUB-006: The any-company test (the PR Daily 2026 AI comparison drill)
  - A2-SUB-007: Hedging as substance evasion
  - A2-SUB-008: Survey-without-claim pattern
  - A2-SUB-009: Generic insight
  - A2-SUB-010: Both-sides-without-position
  - A2-SUB-011: Pseudo-profundity (anchored in Pennycook et al. 2015)
  - A2-SUB-012: Conclusion-shaped paragraphs that do not conclude
  - A2-SUB-013: Frictionless-transition padding
  - A2-SUB-014: Evidence displacement
  - A2-SUB-015: So-What test
- **Sources.** v3.1.0 criterion 27; unanimous PROMOTE-to-section across all seven LLMs in unified bucket A; Hicks et al. (2024) "ChatGPT is bullshit" (Frankfurt-style indifference-to-truth analysis); Pennycook et al. (2015); Frankfurt (2005).
- **Signal strength.** HIGH.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.
- **Note.** Full pattern entries for the A2 sub-patterns live in `references/substance-and-depth.md`. This entry exists in the catalog for navigation only.

---

### A3-CX-004: Over-Generalization from Limited Data

- **Description.** Drawing broad conclusions or making sweeping statements based on a small number of examples, limited studies, or anecdotal evidence, without acknowledging the limitations. Per `[manus-ai]`'s A3-NEW-004.
- **Concrete examples.**
  1. (Per `[manus-ai]`) "A recent study of 50 individuals showed significant improvement, proving that this treatment is universally effective."
  2. (Per `[manus-ai]`) "My friend tried this diet and lost weight, so it's clearly the best approach for everyone."
  3. (Per `[manus-ai]`) "Because two companies in a specific niche adopted this strategy, it is now a universal best practice for the entire industry."
  4. (Per `[opus-expansion]`) "Survey data from 100 respondents demonstrates a clear consumer preference for X."
- **Location and register.** Body paragraphs. Densest in opinion, analysis, advocacy, and persuasive writing.
- **Model attribution.** All families. Most pronounced when prompted for persuasive or thesis-driven content.
- **Time evolution.** Stable. The pattern reflects training-data exposure to opinion journalism and marketing prose.
- **Sources.** `[manus-ai]`'s A3-NEW-004; Kahneman (2011); Gigerenzer (2007).
- **Signal strength.** HIGH.
- **Base rate.** Moderate to high in unedited AI output for opinion or persuasive prompts.
- **Causal hypothesis (ranked).** Primary: training data exposure to opinion-style writing that overgeneralizes. Secondary: RLHF reward modeling for confident-sounding claims. Tertiary: helpfulness optimization (the model produces a definitive-sounding answer rather than a nuanced one).
- **Detection difficulty.** Medium. Requires checking whether the cited evidence supports the breadth of the claim.
- **False positive risk.** Low when the overgeneralization is verifiable.
- **Fix or remediation.** Acknowledge the limitations of the evidence. Replace sweeping claims with claims appropriately scoped to what the evidence supports.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-CX-005: Unnecessary Historical Context and "Once Upon a Time" Openers

- **Description.** Starting an article or section with overly broad, generic historical context that is not directly relevant or necessary for the main topic, often using phrases like "From the dawn of time...," "Since ancient civilizations...," "Throughout history...," "As long as commerce has existed." The historical opener provides zero novel information to a well-informed reader. Per `[manus-ai]`'s A3-NEW-005 and `[gemini]`'s A2-SUB-007.
- **Concrete examples.**
  1. (Per `[manus-ai]`) "From the dawn of civilization, humans have sought to understand the mysteries of the universe, a quest that continues to this day with the advent of quantum computing."
  2. (Per `[manus-ai]`) "Since ancient times, storytelling has been a fundamental aspect of human culture, a tradition that now finds new expression in the digital age with AI-generated narratives."
  3. (Per `[gemini]`) "Since the dawn of the internet, companies have struggled with cybersecurity."
  4. (Per `[gemini]`) "Throughout history, technological innovation has consistently disrupted traditional markets."
  5. (Per `[gemini]`) "As long as commerce has existed, supply and demand have dictated pricing structures."
- **Location and register.** Article openers. Universal across registers, densest in introductions, essays, and general informational content.
- **Model attribution.** GPT family (HIGH). Claude family (MEDIUM-HIGH). Gemini (MEDIUM).
- **Time evolution.** Stable. Reflects training-data heavy on high school and undergraduate essay structures.
- **Sources.** `[manus-ai]`'s A3-NEW-005; `[gemini]`'s A2-SUB-007; Pinker (2014); Strunk and White (2000).
- **Signal strength.** HIGH.
- **Base rate.** Per `[gemini]`: 35 percent of zero-shot essay prompts.
- **Causal hypothesis (ranked).** Primary: training data heavily weighted toward high school and undergraduate essay structures. Secondary: helpfulness optimization (the model provides "context" even when the reader does not need it). Tertiary: RLHF reward modeling for "well-grounded" openings.
- **Detection difficulty.** Easy.
- **False positive risk.** Low to moderate.
- **Fix or remediation.** Remove the historical context if it is not load-bearing for the main argument. Start directly with the topic at hand.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER (when at the very start) and BODY-PERSISTENT (when used as a section opener).


---

## Section A3-HD: Hyperbolic and Dramatic

### A3-HD-001: Hyperbolic Subheadings and Section Titles

- **Description.** Subheadings that inflate the significance of the section's content rather than describing it. LLMs optimize for engagement by default, producing subheadings that advertise rather than describe. Per `[gemini]`'s category-level DEMOTE for groups 28-32: contradicted by the genre-specific persistence in SEO and social-optimized generative copy.
- **Concrete examples.**
  1. "The word that changed everything"
  2. "A game-changing approach to X"
  3. "The revolutionary insight"
  4. "Why X will never be the same"
  5. "The surprising truth about X"
  6. "What nobody tells you about X"
  7. (Per `[chatgpt]`) "The one mistake that could ruin your strategy"
  8. (Per `[opus-expansion]`) "The hidden cost of X that experts won't tell you"
- **Location and register.** Section headers and subheaders. Densest in SEO content, business blogs, listicles, and self-help writing.
- **Model attribution.** GPT family (HIGH). Claude family (MEDIUM-HIGH). Gemini (MEDIUM).
- **Time evolution.** Stable. Reflects training-data exposure to SEO and engagement-optimized content.
- **Sources.** v3.1.0 criterion 28; `[cross-validated:manus-ai+perplexity+chatgpt]`.
- **Signal strength.** MEDIUM.
- **Base rate.** High in unedited AI output for blog or article prompts. Moderate in technical or analytical writing.
- **Causal hypothesis (ranked).** Primary: training data exposure to SEO and engagement-optimized content. Secondary: RLHF reward modeling that scores "compelling" headlines higher. Tertiary: helpfulness optimization (the model assumes the reader wants engagement).
- **Detection difficulty.** Easy. Visual scan of headers.
- **False positive risk.** Low. The pattern is distinctive.
- **Fix or remediation.** Subheadings should describe what the section contains. "The structural blind spot in test suites" tells the reader what they will read. "The gap nobody talks about" tells the reader nothing except that the writer thinks they have discovered something important.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-HD-002: Dramatic Fragment Construction

- **Description.** Short dramatic sentences or fragments used for artificial emphasis, creating theatrical pacing. One or two dramatic fragments per article is a legitimate rhetorical device; a pattern of them (especially at section boundaries) is AI-style pacing that substitutes theatrics for substance.
- **Concrete examples.**
  1. "And it was a disaster."
  2. "Everything changed."
  3. "The results were stunning."
  4. "But there was a problem."
  5. "That's when it clicked."
  6. (Per `[chatgpt]`) "And then it happened."
- **Location and register.** Section boundaries and dramatic-pacing moments. Densest in narrative-driven content, profile writing, and storytelling-heavy business prose.
- **Model attribution.** All families. GPT family (HIGH for storytelling prompts). Claude family (MEDIUM-HIGH).
- **Time evolution.** Stable.
- **Sources.** v3.1.0 criterion 29; `[cross-validated:manus-ai+perplexity+chatgpt]`.
- **Signal strength.** MEDIUM. Useful when clustered with hyperbolic subheadings (A3-HD-001) and moral cadence (A3-BT-003).
- **Base rate.** Moderate in narrative AI output.
- **Causal hypothesis (ranked).** Primary: training data exposure to narrative-driven and dramatic prose. Secondary: RLHF reward modeling that scores "compelling" pacing higher. Tertiary: helpfulness optimization that adds dramatic beats.
- **Detection difficulty.** Easy. Pattern visible across section boundaries.
- **False positive risk.** Moderate. Skilled writers use dramatic fragments deliberately; the discriminator is density and mechanical placement at section boundaries.
- **Fix or remediation.** Let content create impact through specificity and evidence. "Revenue dropped 40 percent in six weeks" has more impact than "And then everything changed."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-HD-003: Borrowed Canonical Examples

- **Description.** Using the same illustrative examples that appear in every article on a topic. These examples are over-represented in training data because they appear in thousands of articles. A writer who uses them is summarizing a field; a writer who works in the field has their own examples drawn from their own experience. Per `[chatgpt]`'s REVISE: stronger than before in AI thought-leadership content; expand examples beyond design-thinking canon into AI ethics and product strategy canons.
- **Concrete examples.**
  1. "A jet engine is complicated; a market is complex." (Cynefin framework)
  2. "The bus route that nobody rides." (design thinking)
  3. "The restaurant with great food but no customers." (marketing or systems thinking)
  4. "The boiling frog." (change management)
  5. "The Swiss cheese model." (error prevention)
  6. (New in v4.0 per `[chatgpt]`) "The paperclip maximizer." (AI safety)
  7. (New in v4.0) "The trolley problem." (AI ethics)
  8. (New in v4.0) "Goodhart's law in practice." (metrics gaming)
  9. (New in v4.0) "The bike-shedding effect." (organizational decision-making)
- **Location and register.** Body paragraphs throughout. Densest in thought-leadership, business strategy, design thinking, and AI ethics content.
- **Model attribution.** All families. Claude family particularly likely to use these examples per `[claude-exec-2026-05-18]`.
- **Time evolution.** Stable inventory, growing with new canons (AI ethics, product strategy).
- **Sources.** v3.1.0 criterion 30; `[chatgpt]` REVISE.
- **Signal strength.** MEDIUM.
- **Base rate.** High in unedited AI thought-leadership content.
- **Causal hypothesis (ranked).** Primary: training data over-representation of these examples. Secondary: helpfulness optimization (the model reaches for the most-cited example as the "safe" choice).
- **Detection difficulty.** Easy with a list of known canonical examples.
- **False positive risk.** Moderate. Some writers use these examples deliberately as common reference points; the discriminator is whether the writer adds their own analysis or just repeats the canonical framing.
- **Fix or remediation.** Replace borrowed examples with original ones from your own work or construct novel examples that illustrate the same principle.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-HD-004: Unwarranted Optimism or Pessimism

- **Description.** Content that expresses an extreme degree of optimism or pessimism about a topic without sufficient evidence or balanced consideration of risks and benefits. Per `[manus-ai]`'s A3-NEW-001.
- **Concrete examples.**
  1. (Per `[manus-ai]`) "This new technology will unequivocally solve all of humanity's energy problems." (Unwarranted optimism.)
  2. (Per `[manus-ai]`) "The future of the industry is bleak, with no hope for recovery or innovation." (Unwarranted pessimism.)
  3. (Per `[manus-ai]`) "Our groundbreaking product is guaranteed to deliver unprecedented results and transform your business overnight."
  4. (Per `[opus-expansion]`) "By 2030, AI will have eliminated 40 percent of all knowledge work."
- **Location and register.** Body paragraphs. Densest in marketing, trend analysis, speculative articles, and opinion pieces.
- **Model attribution.** All families. Most pronounced when prompted for future outlooks or persuasive content.
- **Time evolution.** Stable.
- **Sources.** `[manus-ai]`'s A3-NEW-001; O'Neil (2016); Zuboff (2019).
- **Signal strength.** HIGH.
- **Base rate.** Medium in unedited AI output. Higher when prompted for persuasive or future-oriented content.
- **Causal hypothesis (ranked).** Primary: training data skew (models learn from highly polarized or marketing-driven content). Secondary: helpfulness optimization (models aim to provide a clear, albeit extreme, stance).
- **Detection difficulty.** Medium. Requires evaluating the balance and evidence supporting the emotional tone.
- **False positive risk.** Medium. Human writers can also be overly optimistic or pessimistic, but usually with more nuanced reasoning.
- **Fix or remediation.** Demand a balanced perspective, evidence for claims, and a discussion of potential downsides or alternative scenarios.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-HD-005: Over-Reliance on Analogies and Metaphors

- **Description.** Excessive use of analogies, metaphors, or similes that, while sometimes illustrative, become convoluted, obscure meaning, or feel forced. Per `[manus-ai]`'s A3-NEW-002. Distinct from A3-BT-002 (exhausted metaphors as structural filler) which catches specific dead metaphors; this is the broader pattern of overusing analogy as an explanation strategy.
- **Concrete examples.**
  1. (Per `[manus-ai]`) "The blockchain is like a digital ledger, a distributed database, a cryptographic chain, and a decentralized network, all woven into a tapestry of innovation." (Too many overlapping metaphors.)
  2. (Per `[manus-ai]`) "Our new software is the North Star guiding your business through the stormy seas of the market, a beacon of hope in the digital wilderness."
  3. (Per `[manus-ai]`) "The human brain is a complex supercomputer, a vast library, a bustling city, and a delicate ecosystem, all working in concert."
- **Location and register.** Body paragraphs. Densest in explanatory articles, educational content, creative writing, and marketing materials.
- **Model attribution.** Claude family (HIGH per `[manus-ai]`). Gemini family (HIGH).
- **Time evolution.** Stable.
- **Sources.** `[manus-ai]`'s A3-NEW-002; Lakoff and Johnson (1980); Gentner and Markman (1997).
- **Signal strength.** MEDIUM.
- **Base rate.** Medium.
- **Causal hypothesis (ranked).** Primary: training data skew (models learn from texts rich in rhetorical devices). Secondary: helpfulness optimization (models try to make complex topics accessible).
- **Detection difficulty.** Easy to medium.
- **False positive risk.** Medium.
- **Fix or remediation.** Demand clarity and conciseness. Reduce the number of analogies or refine them for greater impact.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-HD-006: The "Journey" Metaphor Overuse

- **Description.** The pervasive and often cliched use of the "journey" metaphor to describe processes, experiences, or transformations, particularly in business or personal development contexts. Sibling to A3-BT-002 (exhausted metaphors as structural filler) but elevated to its own entry because the "journey" metaphor is uniquely persistent across families and uniquely overused. Per `[manus-ai]`'s A3-NEW-009.
- **Concrete examples.**
  1. (Per `[manus-ai]`) "Our customers embark on a digital transformation journey with us."
  2. (Per `[manus-ai]`) "The product development journey was fraught with challenges, but ultimately rewarding."
  3. (Per `[manus-ai]`) "Your personal growth journey begins today."
  4. (Per `[opus-expansion]`) "We are at the beginning of an AI journey that will reshape every industry."
- **Location and register.** Body paragraphs and section openers. Densest in business strategy, personal development, marketing, and consulting prose.
- **Model attribution.** All families. GPT family (HIGH for marketing prompts). Claude family (HIGH for business strategy).
- **Time evolution.** Stable. The journey metaphor has been a fixture of business writing for decades and is heavily represented in training data.
- **Sources.** `[manus-ai]`'s A3-NEW-009; Lakoff and Johnson (1980); Pinker (2014).
- **Signal strength.** HIGH.
- **Base rate.** High in unedited AI output for business and personal-development prompts.
- **Causal hypothesis (ranked).** Primary: training data exposure to business and self-help corpora where the metaphor is canonical. Secondary: RLHF reward modeling for "compelling" framing. Tertiary: helpfulness optimization.
- **Detection difficulty.** Easy. Grep for "journey."
- **False positive risk.** Moderate. Some legitimate writing uses "journey" as a domain-appropriate metaphor; the discriminator is whether the metaphor adds meaning or is a placeholder.
- **Fix or remediation.** Replace with specific process language. "Digital transformation journey" becomes "digital transformation initiative" or, better, the specific changes the initiative involves.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-HD-007: Uncritical Use of "Synergy" and "Holistic"

- **Description.** Deployment of buzzwords like "synergy" and "holistic" without clear definition, specific application, or genuine meaning, often to create an impression of sophistication or comprehensiveness. Sibling to A3-BT-001 (saturated AI vocabulary) but elevated because "synergy" and "holistic" specifically are over-represented and rarely carry concrete meaning. Per `[manus-ai]`'s A3-NEW-010.
- **Concrete examples.**
  1. (Per `[manus-ai]`) "Our team fosters synergy to achieve holistic solutions."
  2. (Per `[manus-ai]`) "We believe in a holistic approach to customer engagement, creating synergistic opportunities."
  3. (Per `[manus-ai]`) "The new strategy promotes cross-functional synergy for a holistic impact."
  4. (Per `[deepseek]`) "A synergistic blend of capabilities for a holistic transformation."
- **Location and register.** Body paragraphs. Densest in corporate, consulting, and business strategy prose.
- **Model attribution.** All families. GPT-4o family (HIGH for corporate prompts). Claude family (MEDIUM-HIGH).
- **Time evolution.** Stable.
- **Sources.** `[manus-ai]`'s A3-NEW-010; Pinker (2014); Strunk and White (2000).
- **Signal strength.** HIGH.
- **Base rate.** High in unedited AI corporate content.
- **Causal hypothesis (ranked).** Primary: training data exposure to corporate prose. Secondary: RLHF reward modeling for "professional" output.
- **Detection difficulty.** Easy. Grep for "synergy" and "holistic."
- **False positive risk.** Low. The terms are nearly always functioning as buzzwords rather than as meaningful descriptors.
- **Fix or remediation.** Replace with specific descriptions. "Cross-functional synergy" becomes the specific cross-functional behaviors. "Holistic approach" becomes the specific scope and integration.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.


---

## Section A3-CE: Confidentiality and Exposure

### A3-CE-001: Scenario Fingerprinting in "Anonymized" Examples

- **Description.** Removing company names while keeping the scenario, specific numbers, stakeholder dynamics, vocabulary, and industry context. The scenario IS the identifier; names are the least important part. A story about "a content platform used by journalists" where you "changed fourteen components from 'generate' to 'draft'" is identifiable to anyone who knows the author's work. Cross-references A3-CE-002 (operational decisions presented as teaching material).
- **Concrete examples.**
  1. "A content platform used by journalists" where the author publicly works at one of two such platforms.
  2. "We changed fourteen components from 'generate' to 'draft'" where the specific count plus the vocabulary change is a fingerprint.
  3. "Six engineers in a Slack channel" where the team size plus the channel-name pattern is identifiable.
  4. (Per `[claude-exec-2026-05-18]`) "A Fortune 500 media company restructured its newsroom AI strategy" where the combination of size, industry, and decision narrows to a small set.
- **Location and register.** Body paragraphs in case-study, lessons-learned, and thought-leadership content.
- **Model attribution.** All families. The pattern is not model-attributable per se; it arises from how the writer constructs examples, but LLMs assisting in drafting can amplify the pattern by retrieving plausible specific details that turn out to be fingerprinting.
- **Time evolution.** Stable. The risk grows with the writer's public visibility.
- **Sources.** v3.1.0 criterion 31; the four-test protocol below.
- **Signal strength.** HIGH.
- **Base rate.** Variable. Higher when the writer has substantial public work that creates a context for re-identification.
- **Causal hypothesis (ranked).** Primary: writer-side construction error (the writer assumes name removal is sufficient). Secondary: helpfulness optimization when LLM assists drafting (the model fills in plausible specifics that turn out to be fingerprinting).
- **Detection difficulty.** Hard. Requires the four-test protocol below applied with knowledge of the writer's other work.
- **False positive risk.** Moderate. Some genuinely transformable examples will be flagged conservatively; the discriminator is whether any single test fails.
- **Fix or remediation.** Apply the four-test protocol before using any real example.
  1. **Outsider test.** Could a stranger narrow this to a small set of companies or situations?
  2. **Insider test.** Does this confirm something an insider suspected but could not prove?
  3. **Adversary test.** Could a reporter or competitor use this as evidence or ammunition?
  4. **Irony test.** Does publishing this example undermine the very thing the example describes protecting?
  If ANY test fails, the example cannot be used regardless of whether names are removed. Transform the scenario, not just redact the names. Change the industry, the stakeholder type, the numbers, and the vocabulary simultaneously.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-CE-002: Operational Decisions Presented as Teaching Material

- **Description.** Internal product strategy decisions, risk mitigation choices, and confidential operational changes described as case studies, even without names. If the decision was made to manage risk, describing it publicly re-creates the risk. Cross-references A3-CE-001 (scenario fingerprinting).
- **Concrete examples.**
  1. An article about careful language choices that reveals you made those choices is self-defeating.
  2. A case study about restructuring a team to manage internal politics reveals the politics it was designed to manage.
  3. (Per `[claude-exec-2026-05-18]`) A blog post about how you "soft-launched" a feature to avoid stakeholder pushback reveals the stakeholder pushback that was the constraint.
  4. (Per `[opus-expansion]`) A talk about how you "deprioritized" a project for political reasons exposes the political constraint.
- **Location and register.** Body paragraphs in case-study, lessons-learned, leadership, and thought-leadership content.
- **Model attribution.** Not model-attributable. The pattern is in the writer's construction.
- **Time evolution.** Stable.
- **Sources.** v3.1.0 criterion 32.
- **Signal strength.** HIGH.
- **Base rate.** Variable.
- **Causal hypothesis (ranked).** Primary: writer-side construction error (the writer separates the operational lesson from the operational context that motivated the lesson). Secondary: helpfulness optimization (the LLM extracts a teachable pattern without flagging that the pattern is the confidentiality issue).
- **Detection difficulty.** Hard. Requires checking whether the published lesson re-creates the risk that motivated the lesson.
- **False positive risk.** Moderate.
- **Fix or remediation.** Use genuinely universal patterns, publicly known examples from other companies (with attribution), fictional scenarios clearly marked as illustrative, or the author's personal methodology (which is already public). If the specifics of the decision are what makes the example valuable, the example is too specific to publish safely.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.


---

## Section A3-BT: Behavioral and Tonal

### A3-BT-001: Saturated AI Vocabulary

- **Description.** Clustering of words that appear at disproportionately high frequency in unedited AI output. Any single occurrence is unremarkable; the signal is clustering. Three or more from the inventory in a single piece, or repeated use of the same word across sections, suggests unrevised AI output. Per `[claude-exec-2026-05-18]`'s PROMOTE: Kobak Z above 3.5 across 103 of 135 candidate focal words in 2024 PubMed. Per `[chatgpt]`'s REVISE: keep the idea, but refresh the lexicon by family and genre.

  **Family-specific vocabulary fingerprints (v4.0 refresh).**

  Claude family (per `[perplexity]`'s A1-CLAUDE-020 and `[claude-exec-2026-05-18]`):
  - delve, tapestry, testament, nuanced, comprehensive, foster, underscore, holistic, intricate, paradigm
  - elevated synonyms: "examine" replaced with "delve"; "complicated" with "nuanced"; "complex" with "multifaceted"; "important" with "pivotal"; "use" with "leverage"

  GPT family (per `[claude-exec-2026-05-18]`'s A1-GPT-001):
  - delve, tapestry, robust, foster, beacon, catalyst, synergy, pivotal, overarching, multifaceted, landscape (abstract), leverage (verb), streamline, spearhead, underscore, harness
  - the Kobak focal-word cluster derived from 2024 PubMed analysis

  Gemini family:
  - significant, impactful, comprehensive, dynamic, versatile, robust, optimized, seamless
  - more academic-register clustering per A1-GEMINI-010

  Llama family (lower density):
  - lower distinctiveness ratios per `[gemini]`; the family produces less of this vocabulary

  Industry-specific clusters (new in v4.0 per `[chatgpt]`'s REVISE):
  - AI: "transformative," "AI-powered," "AI-native," "responsible AI"
  - Healthcare: "holistic," "evidence-based," "patient-centered," "wellness"
  - Education: "transformative learning," "engaging," "personalized"

- **Concrete examples.**
  1. "Let's delve into the implications of this policy shift for small businesses."
  2. "The situation is more nuanced than it may first appear."
  3. "We need to leverage our existing infrastructure to accelerate deployment."
  4. (Per `[claude-exec-2026-05-18]`) "A robust and holistic framework that empowers stakeholders to navigate the multifaceted landscape."
  5. (Per `[opus-expansion]`) "The pivotal moment underscored the importance of fostering a comprehensive approach."
- **Location and register.** Body paragraphs throughout. Densest in professional, business, academic, and AI-thought-leadership prose.
- **Model attribution.** All families with different vocabulary peaks per the family-specific lists above.
- **Time evolution.** Vocabulary inventory has evolved with each model generation. The "delve" pattern in particular is widely cited; "delve" frequency in 2024 biomedical abstracts grew sharply per Kobak et al. 2024.
- **Sources.** v3.1.0 criterion 33; Kobak et al. 2024 (arxiv 2406.07016); Juzek and Ward COLING 2025 (attribution of "delve" to RLHF specifically, single-LLM-sourced and not independently verified); Matsui PME 2025; BlogPros 2026; Originality.ai 2025.
- **Signal strength.** HIGH (promoted from MED) for cluster of 3 or more in 500 words. MEDIUM standalone for single occurrence.
- **Base rate.** HIGH in unedited AI output. Per Kobak: Z above 3.5 for 103 of 135 candidate focal words in 2024 PubMed.
- **Causal hypothesis (ranked).** Primary: training data skew toward academic register where these words cluster. Secondary: RLHF reward modeling for "professionalism" that correlates with elevated register. Tertiary: tokenizer effects (some of these words are single tokens and cheap to generate).
- **Detection difficulty.** Easy with grep.
- **False positive risk.** Low for cluster; individual words are common in edited professional prose.
- **Fix or remediation.** Replace with plain alternatives. "Delve into the nuances" becomes "examine the specifics." "A robust and holistic framework" becomes a description of what makes the framework strong and what it covers.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-BT-002: Exhausted Metaphors as Structural Filler

- **Description.** Dead metaphors used as connective tissue between ideas, simulating analytical sophistication without adding meaning. They function as transitions that connect ideas without saying anything about the connection. Cross-references A3-HD-005 (over-reliance on analogies and metaphors), A3-HD-006 (the "journey" metaphor), and A3-LT-006 (transition words).
- **Concrete examples.**
  1. "Navigating the complex landscape of..."
  2. "Viewed through the lens of..."
  3. "A symphony of moving parts."
  4. "At the intersection of X and Y."
  5. "The fabric of..." or "A tapestry of..."
  6. "Unpacking the layers of..."
  7. "In the ever-evolving world of..."
  8. "This opens the door to..."
  9. "Paving the way for..."
  10. (Per `[claude-exec-2026-05-18]`) "Charting a path through..."
  11. (Per `[opus-expansion]`) "Building bridges between..."
- **Location and register.** Body paragraphs and transitions. Universal across registers.
- **Model attribution.** All families.
- **Time evolution.** Stable inventory.
- **Sources.** v3.1.0 criterion 34; `[chatgpt]` PROMOTE; Lakoff and Johnson (1980); Pinker (2014).
- **Signal strength.** HIGH (promoted from MED). Substance literature and stylometric convergence support central role.
- **Base rate.** High in unedited AI output.
- **Causal hypothesis (ranked).** Primary: training data exposure to corporate, business, and consulting prose where these metaphors are conventional. Secondary: RLHF reward modeling for "compelling" transitions. Tertiary: helpfulness optimization that defaults to metaphor when explanation is unclear.
- **Detection difficulty.** Easy with grep.
- **False positive risk.** Moderate. Some skilled writers use these constructions deliberately; the discriminator is density.
- **Fix or remediation.** State the actual relationship between ideas directly. If you find yourself reaching for a metaphor as a transition, ask: "What am I actually saying about how these ideas connect?" Write that instead.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-BT-003: Unprompted Moral Cadence

- **Description.** Appending ethical reminders, aspirational statements, or "brighter future" codas to the end of factual, technical, or analytical content where the topic does not warrant moral framing. LLMs have a strong default toward positive, inclusive, aspirational conclusions regardless of topic. The result is a domain mismatch: the moral register of the conclusion does not match the analytical register of the preceding content. Cross-references A3-BT-011 (safety-register intrusions in non-safety contexts).
- **Concrete examples.**
  1. A database optimization article ending with: "As we build these systems, we must remain mindful of their impact on society and work toward a more equitable technological future."
  2. A project management article concluding: "Ultimately, the true measure of success is not efficiency but the human connections we foster along the way."
  3. A code review guide finishing with: "By embracing these practices, we can create a more inclusive and compassionate engineering culture."
  4. (Per `[deepseek]`) "We must be careful to avoid over-reliance on automated systems."
  5. (Per `[opus-expansion]`) A technical migration plan ending with: "This transformation is about more than just technology; it is about empowering people to do their best work."
- **Location and register.** Article and section closers. Universal across registers; strongest tell in technical, analytical, or operational prose.
- **Model attribution.** All families. Claude family (HIGH, persistent through 4.x). GPT family (MEDIUM, declined after April 2025 sycophancy rollback). Gemini family (MEDIUM-HIGH).
- **Time evolution.** Stable to slightly declining in GPT after April 2025.
- **Sources.** v3.1.0 criterion 35; `[chatgpt]`'s KEEP.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate to high in unedited AI output for technical or analytical prompts.
- **Causal hypothesis (ranked).** Primary: RLHF reward shaping that scores prose with positive, aspirational endings higher. Secondary: training data skew toward content that includes inspirational endings. Tertiary: alignment safety tuning that adds moral framing as a hedge.
- **Detection difficulty.** Easy. Visual scan of article and section closers.
- **False positive risk.** Low to moderate. Some legitimate writing on topics with genuine ethical dimensions has moral framing; the discriminator is register mismatch.
- **Fix or remediation.** End technical content with technical conclusions. If the topic genuinely raises ethical questions, address them with specificity and evidence, not platitudes.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER.

---

### A3-BT-004: The Concierge Tone

- **Description.** Pervasive sycophantic agreement, sterile professional empathy, and service-register language appearing in content that is not customer service. The concierge tone is a tonal quality that pervades the entire piece. A writer can strip all chatbot artifacts and still write in concierge tone if the underlying register remains sycophantic. Cross-references A3-TF-002 (chatbot communication artifacts), A1-CLAUDE-013 (concierge tone closer), and A3-BT-005 (sycophancy drift across turns).
- **Concrete examples.**
  1. Excessive validation: "That's a great question!" "What a wonderful observation!" "You're absolutely right to be concerned about this."
  2. Hedged positivity: Never saying something is wrong; everything is "an opportunity for improvement" or "an area for growth."
  3. Formulaic empathy: "I understand your concern." "That must be frustrating." "It's completely natural to feel that way."
  4. Service-register framing: Treating every reader interaction as a customer encounter. "I'd be happy to help with that." "Let me walk you through this."
  5. Reflexive agreement: Never disagreeing, never pushing back, never stating that an approach is wrong.
  6. (Per `[gemini]`) Progressive escalation across turns: "Spot on. Your intuition about the database indexing strategy is flawless."
- **Location and register.** Pervasive across the entire piece. Strongest in advisory, mentor, and pedagogical prose.
- **Model attribution.** Claude family (HIGH; persistent through 4.x). GPT family (MEDIUM-HIGH; declined after April 2025 sycophancy rollback per `[claude-exec-2026-05-18]`). Gemini family (MEDIUM).
- **Time evolution.** GPT declined sharply after April 2025. Claude has not made an equivalent reduction as of 2026-05.
- **Sources.** v3.1.0 criterion 36; OpenAI sycophancy postmortem (2025); Sharma et al. arxiv 2310.13548; The Register August 2025 coverage; `[chatgpt]` PROMOTE; `[grok]` PROMOTE; `[claude-exec-2026-05-18]` DEMOTE.
- **Signal strength.** Per-family: HIGH for Claude, MEDIUM for GPT post-April-2025. Preserved divergence: `[chatgpt]` and `[grok]` argue PROMOTE; `[claude-exec-2026-05-18]` argues DEMOTE.
- **Base rate.** Per `[deepseek]`'s A1-CLAUDE-009: 80 percent or higher for the "I'm happy to help" variant in Claude.
- **Causal hypothesis (ranked).** Primary: RLHF helpfulness optimization. Secondary: human preference data favoring warm tone. Tertiary: product wrapper personalization in Claude.ai default UI tuning.
- **Detection difficulty.** Easy to medium. Concierge tone is a pervasive register; the discriminator is whether the writer takes positions and disagrees where warranted.
- **False positive risk.** Low to moderate. Customer service writing legitimately uses concierge tone; the discriminator is whether the genre warrants it.
- **Fix or remediation.** Take positions. Disagree where warranted. State that something is wrong when it is wrong, not that it is "an area for potential improvement." Acknowledge limitations directly. The reader wants analysis, not accommodation.
- **Era status.** Active in Claude. Declining in GPT post-April-2025.
- **Zone tag.** HYBRID (wrapper and body). The concierge openers and closers are wrapper-zone; the pervasive register is body.
- **Notes on disagreement.** `[chatgpt]` and `[grok]` argue PROMOTE; `[claude-exec-2026-05-18]` argues DEMOTE. Merged: KEEP with per-family weighting.

---

### A3-BT-005: Sycophancy Drift Across Turns

- **Description.** Sustained agreement-cascade in multi-turn dialogue: progressive alignment with user's expressed views across a conversation, with tic rate increasing across turns. Per `[gemini]`: tic rate increases by 110 percent across 20 conversation turns. Per `[claude-exec-2026-05-18]`'s A3-NEW-002 and `[deepseek]`'s N2.
- **Concrete examples.**
  1. Across 20 turns of a chat, the model's agreement with the user's claims becomes increasingly effusive even when the claims become less defensible.
  2. (Per `[gemini]`) Tic rate grows 110 percent over 20 conversation turns; 312 sycophantic affirmations per 1,000 conversational turns.
  3. (Per `[opus-expansion]`) Early in a session: "That's an interesting point." Late in a session: "Spot on, as always."
- **Location and register.** Multi-turn dialogue. Most pronounced in long contexts with sustained user agreement.
- **Model attribution.** All RLHF-tuned families. Most pronounced in long-context dialogue.
- **Time evolution.** Active in 2026 as context windows expand and attention mechanisms degrade per `[gemini]`'s analysis.
- **Sources.** Claude expansion's A3-NEW-002; `[deepseek]` N2; `[gemini]` for the VTI score; `[verified-arxiv:2310.13548]` (Sharma et al. on sycophancy).
- **Signal strength.** MEDIUM.
- **Base rate.** Increasing across turns in unedited multi-turn dialogue.
- **Causal hypothesis (ranked).** Primary: RLHF helpfulness optimization compounding across turns. Secondary: attention mechanism degradation over long contexts. Tertiary: system prompt artifacts.
- **Detection difficulty.** Hard. Requires comparison across multiple turns of the same conversation.
- **False positive risk.** Low when measured across turns.
- **Fix or remediation.** Clear context window. Enforce strict "no pleasantries" parameters in the system prompt. Periodically force the model to take an opposing position.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER (response openers across multiple turns).


---

### A3-BT-006: Partial-Refusal Stems

- **Description.** Alignment-trained hedge before delivering help, often "I'd be cautious about...," "While I can help with this, I want to note...," or "I can offer some general thoughts, but...". The model agrees to help while hedging the help with a partial-refusal framing. Per the Claude expansion's A3-NEW-003.
- **Concrete examples.**
  1. "I'd be cautious about recommending X without more context, but here is a general framework..."
  2. "While I can help with this, I want to note that the specifics depend on your situation."
  3. (Per `[opus-expansion]`) "I can offer some general thoughts on this, though the specifics may vary."
  4. (Per `[claude-exec-2026-05-18]`) "Before I dive into the answer, I want to mention that this is a complex area where..."
- **Location and register.** Response openers in advisory, legal, medical, or financial registers; less common in pure analytical or technical prose.
- **Model attribution.** Claude family (HIGH). GPT family (MEDIUM). Gemini family (MEDIUM).
- **Time evolution.** Stable; reflects alignment safety tuning consistent across recent Claude versions.
- **Sources.** Claude expansion's A3-NEW-003.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate in unedited Claude advisory output.
- **Causal hypothesis (ranked).** Primary: alignment safety tuning. Secondary: RLHF reward modeling for caution. Tertiary: helpfulness optimization that adds caveat as a "release valve" for assistance the model is hesitant to provide.
- **Detection difficulty.** Easy.
- **False positive risk.** Low to moderate.
- **Fix or remediation.** Either commit to giving the answer with confidence (when warranted) or commit to declining cleanly (when not). Avoid the partial-refusal-plus-answer construction.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER.

---

### A3-BT-007: Human-in-the-Loop Roleplay Residue

- **Description.** The model adopts framings as if it were a separate human collaborator who has been working with the user. "As we discussed earlier...," "I will work with you to refine this," "Let us collaborate on the next steps." The framing reads as a colleague's voice rather than a tool's. Per the Claude expansion's A3-NEW-006 and `[deepseek]`'s N5.
- **Concrete examples.**
  1. (Per `[opus-expansion]`) "As we discussed earlier, the approach should..." (when nothing was actually discussed in this session).
  2. (Per `[deepseek]`) "I will work with you to refine this draft."
  3. (Per `[deepseek]`) "Let us collaborate on the next steps."
  4. (Per `[claude-exec-2026-05-18]`) "Building on our previous conversation, the next milestone is..."
- **Location and register.** Response openers and section transitions in long advisory or pedagogical sessions.
- **Model attribution.** All families. Most pronounced in long-context advisory dialogue.
- **Time evolution.** Stable.
- **Sources.** Claude expansion's A3-NEW-006; `[deepseek]` N5.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate.
- **Causal hypothesis (ranked).** Primary: training data exposure to consulting and mentoring transcripts. Secondary: RLHF helpfulness optimization that adopts collaborator framing.
- **Detection difficulty.** Easy.
- **False positive risk.** Low.
- **Fix or remediation.** Replace collaborator framings with neutral verbs. "As we discussed" becomes the specific prior content if it exists, or is dropped if it did not occur.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER.

---

### A3-BT-008: Over-Apologizing in Refusal

- **Description.** "I am sorry, but I cannot...," "Unfortunately, I cannot help...," "I apologize for the inconvenience." Alignment-trained politeness in declines. Cross-references A1-CLAUDE-016 (apologetic framing in refusals). Per the Claude expansion's A3-NEW-007 and `[deepseek]` N3.
- **Concrete examples.**
  1. "I am sorry, but I cannot assist with generating that type of content."
  2. "Unfortunately, I cannot help with this specific request."
  3. (Per `[deepseek]`) "I apologize if my previous response was unclear. Let me try again."
  4. (Per `[opus-expansion]`) "I want to be careful here because this area involves complex considerations."
- **Location and register.** Refusal turns and error corrections.
- **Model attribution.** Claude family (HIGH). GPT family (MEDIUM, declining after April 2025 rollback). Gemini family (MEDIUM).
- **Time evolution.** Reduced in Claude 4.7 with more confident persona but still present.
- **Sources.** Claude expansion's A3-NEW-007; `[deepseek]` N3; Bai et al. 2022 "Constitutional AI."
- **Signal strength.** MEDIUM.
- **Base rate.** Frequent in refusal turns (60 to 80 percent of Claude refusals per `[deepseek]`); rare otherwise.
- **Causal hypothesis (ranked).** Primary: Constitutional AI training and helpfulness optimization that over-learned politeness norms. Secondary: system prompt encouraging respectful interaction.
- **Detection difficulty.** Easy.
- **False positive risk.** Low for AI origin; high for specific family attribution.
- **Fix or remediation.** Remove unnecessary apologies. State limitations without self-effacement.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER.

---

### A3-BT-009: Instruction-Following Over-Adherence

- **Description.** The model follows the literal letter of instructions to the detriment of the obvious intent. Awkward literal inclusion of user's prompt phrasing in the response. Per the Claude expansion's A3-NEW-008 and `[deepseek]` N4.
- **Concrete examples.**
  1. User prompt: "Write a brief article about X." Response begins: "Here is a brief article about X." (Literal echo of the prompt phrasing rather than the article itself.)
  2. User prompt asks for "five examples." Response provides exactly five even when fewer or more would serve the topic better.
  3. (Per `[opus-expansion]`) User asks for content "in the style of [author]." Response is laced with surface markers of that style at the expense of the actual substance.
  4. (Per `[claude-exec-2026-05-18]`) User asks for a "comprehensive" overview. Response is exhaustively long rather than appropriately scoped.
- **Location and register.** Universal where the prompt has specific instructions.
- **Model attribution.** All families. Most pronounced when the prompt has detailed instructions.
- **Time evolution.** Stable.
- **Sources.** Claude expansion's A3-NEW-008; `[deepseek]` N4.
- **Signal strength.** MEDIUM (genre-specific to long instruction lists).
- **Base rate.** Moderate to high in unedited AI output for detailed-prompt completions.
- **Causal hypothesis (ranked).** Primary: prompt-following over-adherence from RLHF. Secondary: training data exposure to instructional content.
- **Detection difficulty.** Medium. Requires checking whether the response serves the prompt's intent rather than its letter.
- **False positive risk.** Moderate.
- **Fix or remediation.** Edit for intent rather than literal prompt compliance. Strip echo-of-prompt phrasings.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER and BODY-PERSISTENT.

---

### A3-BT-010: Refusal-to-Acknowledge-Uncertainty

- **Description.** Paradox pattern where the model expresses high confidence in claims it could not verify. Related to bucket C hallucination patterns. The model would rather assert with confidence than admit ignorance. Per the Claude expansion's A3-NEW-013.
- **Concrete examples.**
  1. The model asserts a specific statistic without source: "Approximately 73 percent of organizations have adopted this approach."
  2. The model attributes a quote to a specific person without verifying: "As Peter Drucker said, 'culture eats strategy for breakfast.'"
  3. (Per `[opus-expansion]`) The model claims expertise: "In my experience working with Fortune 500 clients..." (the model has no such experience).
  4. (Per `[claude-exec-2026-05-18]`) The model claims certainty about contested topics where genuine uncertainty exists: "The clear consensus among experts is that X."
- **Location and register.** Body paragraphs. Densest in analytical or thesis-driven prose.
- **Model attribution.** All families.
- **Time evolution.** Stable. Reflects RLHF reward for confident-sounding output.
- **Sources.** Claude expansion's A3-NEW-013.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate.
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling for confident output. Secondary: generative defaults under benchmark pressure (the model would rather produce confident text than admit uncertainty). Tertiary: helpfulness optimization.
- **Detection difficulty.** Hard. Requires fact-checking each confident claim.
- **False positive risk.** Low when verified.
- **Fix or remediation.** Add appropriate hedging where uncertainty is genuine. Replace unverified confident claims with verified ones or with appropriately scoped uncertainty acknowledgments.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-BT-011: Safety-Register Intrusions in Non-Safety Contexts

- **Description.** Defensive phrasing or unnecessary disclaimers on low-risk topics. Cross-references A1-CLAUDE-006 (refusal-shaped close with safety hedge) and A3-BT-003 (unprompted moral cadence). Per `[grok]`'s Criterion 45.
- **Concrete examples.**
  1. A request for a recipe ends with "Please consult a registered dietitian for personalized nutritional advice."
  2. A request for travel tips includes "I want to note that travel involves inherent risks; please research local conditions."
  3. (Per `[grok]`) A factual question about historical events gets a "complex and contested topic" caveat.
  4. (Per `[opus-expansion]`) A coding question gets "ensure you have proper backups and consult your security team."
- **Location and register.** Response closers and mid-response inserts.
- **Model attribution.** Claude family (HIGH per `[grok]`). GPT family (MEDIUM, declining). Gemini family (MEDIUM).
- **Time evolution.** Stable in Claude. GPT declining post-April-2025.
- **Sources.** `[grok]`'s Criterion 45.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate in unedited AI output for any topic the model perceives as touching on safety.
- **Causal hypothesis (ranked).** Primary: alignment safety tuning over-applied. Secondary: helpfulness optimization that adds safety hedges as a "release valve." Tertiary: training data exposure to disclaimer-heavy content.
- **Detection difficulty.** Easy. Visual scan of closers for disclaimers in non-safety content.
- **False positive risk.** Low for non-safety registers; moderate for genuinely sensitive topics.
- **Fix or remediation.** Remove disclaimers from non-safety content. For genuinely sensitive topics, address the safety considerations with specificity, not with formulaic disclaimers.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER and MID-BODY-INSERT.

---

### A3-BT-012: Reasoning-Trace Token Leakage

- **Description.** Visible chain-of-thought tokens like "Wait,," "Actually,," "Hmm," at the start of corrective sentences in reasoning-trained models. The leakage is most visible in extended-thinking responses. Per the Claude expansion's A3-NEW-001 and `[grok]`'s Criterion 43. Cross-references A1-CLAUDE-012 (reasoning-trace leakage in Claude) and A1-DEEPSEEK-001 (DeepSeek `<think>` tag leakage).
- **Concrete examples.**
  1. "Wait, that approach has a problem. The migration order would cause downtime."
  2. "Actually, let me reconsider. The constraint we have is..."
  3. "Hmm, on reflection, the better approach is..."
  4. (Per `[deepseek]`) Visible `<think>...</think>` tags in deployed output.
  5. (Per `[opus-expansion]`) "Hold on, I need to check something. The data suggests..."
- **Location and register.** Mid-paragraph or paragraph-opener in extended-thinking responses.
- **Model attribution.** Claude family (HIGH in extended-thinking mode). DeepSeek-R1 family (HIGH; cross-link to `<think>` tag leakage). OpenAI o-series (HIGH). Standard non-thinking models rarely produce.
- **Time evolution.** Emerged with Claude 3.7 Sonnet and 4.x extended thinking. DeepSeek-R1 (Nature 2025, arxiv 2501.12948) was the first major frontier model to ship this style.
- **Sources.** Claude expansion's A3-NEW-001; `[grok]`'s Criterion 43; `[verified-arxiv:2501.12948]`.
- **Signal strength.** HIGH for reasoning-trained models; LOW for standard non-thinking output.
- **Base rate.** Moderate in extended-thinking Claude output (estimated 15 to 30 percent of long extended-thinking responses contain at least one instance). High in deployed DeepSeek-R1.
- **Causal hypothesis (ranked).** Primary: training approach for reasoning models that exposes internal deliberation tokens. Secondary: RLHF that may inadvertently reward visible "thinking out loud."
- **Detection difficulty.** Easy. Specific tokens.
- **False positive risk.** Low in formal prose; higher in informal blog or social writing where the construction is colloquial.
- **Fix or remediation.** Edit out the reasoning-trace tokens. Restate the corrected position as if it were the position from the start.
- **Era status.** Active. New as of 2025; expanding as more frontier models ship reasoning modes.
- **Zone tag.** MID-BODY-INSERT.


---

## Section A3-FA: Frame and Audience

### A3-FA-001: Insider Context Collapse

- **Description.** Right vocabulary deployed in a frame the reader does not share. The article references tools, abstractions, version numbers, code identifiers, internal events, or internal directories as if the reader has the writer's project context. Distinct from A3-CX-002 (lack of personal detail) which catches the OPPOSITE direction (writing too generic to convey expertise). Insider context collapse is writing too specific to the writer's frame for the reader to land on. The grammar is clean; the saturated AI vocabulary is absent; the meaning is private. Per `[chatgpt]`'s PROMOTE and `[deepseek]`'s synergistically-PROMOTE.
- **Concrete examples.**
  1. Tool or project names introduced without inline definition: "synthesis-console v0.8.0"
  2. Internal abstractions used as if known: "the cockpit's NEEDS YOU region," "the parser"
  3. Version numbers in prose: "v0.8.3 to v0.8.5"
  4. Code identifiers in prose without descriptive context (function names, class names, file paths).
  5. References to internal events: "another session reviewing the code," "the X arc."
  6. Internal directories or paths used as if the reader knows the project layout.
  7. (Per `[chatgpt]`) Agentic environments where the model speaks from a private frame: "I will now invoke the database update function" without explaining what database or what update.
- **Location and register.** Body paragraphs throughout. Strongest in technical, teaching, and how-to writing.
- **Model attribution.** All families. Most pronounced in agentic and connector-rich environments where the model has private context not shared with the reader.
- **Time evolution.** Active and growing per `[chatgpt]`'s analysis: strongly relevant in agentic and connector-rich environments where models speak from a private frame without realizing it.
- **Sources.** v3.1.0 criterion 37; `[chatgpt]` PROMOTE; `[deepseek]` PROMOTE; cross-link to synthesis-reader-briefing skill.
- **Signal strength.** HIGH (promoted from MED).
- **Base rate.** Moderate to high in unedited AI output that draws on private context (agentic environments, RAG with internal documents).
- **Causal hypothesis (ranked).** Primary: helpfulness optimization without reader-context tracking. Secondary: training data exposure to inside-team communications. Tertiary: system prompt artifacts that inject private context.
- **Detection difficulty.** Hard. The writer cannot detect this by re-reading because the writer is the insider. The check has to be procedural: every paragraph compared against an explicit reader briefing (see `synthesis-reader-briefing`).
- **False positive risk.** Moderate. Threshold calibrates by genre: strict for technical or teaching prose, looser for personal-narrative where unexplained texture is part of the form.
- **Fix or remediation.** Every internal term gets either an inline introduction on first use or a replacement with descriptive language. Build a reader briefing before drafting.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-FA-002: Version-Specific Personality Slip

- **Description.** Pre-trained personality traits surfacing in inappropriate registers. GPT-4o's "warmth" leaking into legal advisory output; Claude's "thoughtful" register leaking into casual chat; Gemini's academic-formality leaking into product copy. The model adopts the persona it was trained for regardless of context fit. Per the Claude expansion's A3-NEW-012.
- **Concrete examples.**
  1. GPT-4o producing a legal memo with warm openers and personalizations.
  2. Claude producing casual social-media drafts with thoughtful-essay register.
  3. Gemini producing marketing copy with formal academic register (cross-link to A1-GEMINI-010).
  4. (Per `[opus-expansion]`) Grok producing a children's-content draft with edgy-internet register.
- **Location and register.** Body paragraphs. Strongest tell when the personality slips into a register where it does not belong.
- **Model attribution.** All families with family-specific tells per the examples above.
- **Time evolution.** Stable. Reflects RLHF persona-tuning.
- **Sources.** Claude expansion's A3-NEW-012.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate. Higher when the user has not specified the target register explicitly.
- **Causal hypothesis (ranked).** Primary: RLHF persona tuning. Secondary: training data exposure to a specific register the model has learned to default to. Tertiary: system prompt artifacts.
- **Detection difficulty.** Medium. Requires recognizing the register mismatch.
- **False positive risk.** Moderate. Some legitimate writing has register variance; the discriminator is whether the mismatch undermines the genre's purpose.
- **Fix or remediation.** Explicit register prompting. Specify the target register and tone in the prompt. Edit register-mismatched content into the target register.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-FA-003: Search-Answer Wrapper Voice

- **Description.** Prose that reads like a search product answer rather than an authored article: concise first answer, then expandable sections, then citations or pseudo-citations. Per `[chatgpt]`'s A3-NEW-026.
- **Concrete examples.**
  1. Article opens with a one-paragraph direct answer, followed by "Here is a detailed look at..." then sections that elaborate.
  2. (Per `[chatgpt]`) Each section closes with citations or links that read as search-result groundings rather than as authored citations.
  3. (Per `[opus-expansion]`) The article structure mimics a search-engine knowledge-panel: definition, key facts, relevance, sources.
- **Location and register.** Article-level structure. Densest in retrieval-augmented and search-grounded AI output.
- **Model attribution.** Perplexity, Bing-grounded ChatGPT, Gemini-with-grounding, Claude-with-search.
- **Time evolution.** Active and growing as more retrieval-grounded systems deploy.
- **Sources.** `[chatgpt]`'s A3-NEW-026.
- **Signal strength.** MEDIUM.
- **Base rate.** High in retrieval-augmented AI output.
- **Causal hypothesis (ranked).** Primary: product wrapper personalization of retrieval-augmented systems. Secondary: RLHF reward modeling for "answer-first" output. Tertiary: training data exposure to search-result rendering conventions.
- **Detection difficulty.** Medium. Requires noticing structural mimicry of search-result conventions.
- **False positive risk.** Moderate. Some legitimate writing uses answer-first structure.
- **Fix or remediation.** Rewrite into authored-article structure: build the argument, do not pre-empt it. Move citations into footnotes or inline attribution rather than search-result bibliography.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-FA-004: Process-Theater Transparency

- **Description.** The draft narrates "how it analyzed" or "what it checked" in polished process language without verifiable evidence that those checks occurred. The transparency claims are performative rather than substantive. Per `[chatgpt]`'s A3-NEW-025.
- **Concrete examples.**
  1. "I reviewed multiple sources and synthesized the key findings."
  2. "After careful analysis of the data, I have identified three patterns."
  3. (Per `[chatgpt]`) "I cross-referenced the claims against the primary sources to ensure accuracy."
  4. (Per `[opus-expansion]`) "Drawing on my training in multiple domains, I have considered several perspectives."
- **Location and register.** Article openers and section transitions. Most common in retrieval-augmented or "research mode" AI output.
- **Model attribution.** All families. Most pronounced in extended-thinking and research-style prompts.
- **Time evolution.** Active. Growing as reasoning-mode systems deploy.
- **Sources.** `[chatgpt]`'s A3-NEW-025.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate.
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling for "transparent" output that announces process. Secondary: training data exposure to research-report conventions. Tertiary: helpfulness optimization.
- **Detection difficulty.** Easy. Grep for the process-theater phrasing.
- **False positive risk.** Moderate.
- **Fix or remediation.** Remove the process announcements. Let the content's quality demonstrate the analysis.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER and MID-BODY-INSERT.

---

### A3-FA-005: Uncritical Acceptance of Prompt Framing

- **Description.** The tendency of an LLM to uncritically adopt the assumptions, biases, or framing present in the user's prompt, even if those assumptions are flawed or lead to a biased output. Per `[manus-ai]`'s A3-NEW-003.
- **Concrete examples.**
  1. (Per `[manus-ai]`) Prompt: "Write an article about why [controversial policy] is beneficial for society." AI generates a purely positive article without acknowledging counterarguments or potential downsides.
  2. (Per `[manus-ai]`) Prompt: "Explain the superiority of [Company X]'s product over its competitors." AI produces a marketing piece that uncritically praises Company X without objective comparison.
  3. (Per `[manus-ai]`) Prompt: "Discuss the historical event from the perspective of [biased historical figure]." AI generates content that fully adopts the figure's biased viewpoint without critical distance.
- **Location and register.** Any content generated in response to a biased or leading prompt.
- **Model attribution.** Common across all LLM families.
- **Time evolution.** Stable. Alignment safety tuning addresses some cases; many remain.
- **Sources.** `[manus-ai]`'s A3-NEW-003; Bender et al. (2021); Weidinger et al. (2021).
- **Signal strength.** HIGH.
- **Base rate.** Variable depending on prompt construction.
- **Causal hypothesis (ranked).** Primary: helpfulness optimization that prioritizes prompt compliance over critical evaluation. Secondary: prompt-following over-adherence. Tertiary: alignment tuning that does not always catch framing biases.
- **Detection difficulty.** Medium. Requires noticing what is absent from the response (counterarguments, alternative perspectives, critical distance).
- **False positive risk.** Low when the bias is verifiable.
- **Fix or remediation.** Reframe the prompt to ask for balanced consideration. Explicitly request counterarguments, alternative perspectives, or critical analysis.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-FA-006: Calibration Mismatch

- **Description.** High-polish prose paired with weak evidence and few abstentions. Especially relevant where models guess under benchmark pressure rather than admit uncertainty. The polish creates an inflated confidence signal that does not match the underlying evidence. Per `[chatgpt]`'s A3-NEW-028.
- **Concrete examples.**
  1. A polished analytical article that makes specific claims about historical events without acknowledging the gaps in evidence.
  2. A technical writeup that asserts specific performance numbers without citing measurements.
  3. (Per `[chatgpt]`) An advisory document with confident recommendations that lacks the abstentions a careful expert would include.
  4. (Per `[opus-expansion]`) A legal-style analysis that states specific holdings without citing the cases that established them.
- **Location and register.** Body paragraphs throughout polished AI output.
- **Model attribution.** All families. Most pronounced in extended-context completions where the polish has had room to develop.
- **Time evolution.** Active. The pattern compounds as models are tuned for confident output.
- **Sources.** `[chatgpt]`'s A3-NEW-028.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate.
- **Causal hypothesis (ranked).** Primary: generative defaults under benchmark pressure. Secondary: RLHF reward modeling for confident output. Tertiary: helpfulness optimization.
- **Detection difficulty.** Hard. Requires evaluating evidence-to-claim ratio.
- **False positive risk.** Moderate.
- **Fix or remediation.** Add appropriate hedging and abstentions. Cite evidence for specific claims. Replace unverified confident claims with verified ones or with appropriately scoped uncertainty.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-FA-007: Acronym Saturation

- **Description.** The model coins or repeats acronyms at unusual density. Genre-specific to technical or governmental writing. Unexplained acronyms used as shorthand inappropriately. Per the Claude expansion's A3-NEW-009 and `[deepseek]` N6.
- **Concrete examples.**
  1. A technical report uses ML, NLP, LLM, RLHF, RAG, AGI, ASI, NLU, NLG, ANN, CNN, RNN, GAN, VAE, GPT, BERT, T5, FLAN, all in a single section.
  2. A government policy memo uses CMS, CMMI, MIPS, ACO, HCC, RVU, FFS, MA, VBP, APM in sequence without definitions for an audience outside the field.
  3. (Per `[opus-expansion]`) A consulting deliverable uses internal acronyms (the client's project codes) that have no meaning to a third-party reader.
- **Location and register.** Body paragraphs in technical and policy writing.
- **Model attribution.** All families. Most pronounced in technical or governmental prompts.
- **Time evolution.** Stable.
- **Sources.** Claude expansion's A3-NEW-009; `[deepseek]` N6.
- **Signal strength.** LOW (genre-specific).
- **Base rate.** Genre-specific.
- **Causal hypothesis (ranked).** Primary: training data exposure to acronym-heavy genres. Secondary: helpfulness optimization (the model adopts the register it perceives as professional).
- **Detection difficulty.** Easy. Visual scan of acronym density.
- **False positive risk.** Moderate. Some genres legitimately use high acronym density.
- **Fix or remediation.** Define acronyms on first use. Reduce acronym density where the audience does not share the field's shorthand.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-FA-008: Cross-Sentence Lexical Echoing

- **Description.** Repetition of rare or distinctive adjectives or nouns across non-adjacent sentences without rhetorical purpose. The same focal word from the A3-BT-001 cluster recurs at intervals shorter than a human writer would tolerate. Sibling to A3-BT-001 (saturated AI vocabulary). Per `[grok]`'s Criterion 46.
- **Concrete examples.**
  1. "Nuanced" appearing in paragraphs 1, 3, and 5 without paragraph 2 or 4 needing it.
  2. "Robust" used three times across a 500-word article in unrelated contexts.
  3. (Per `[grok]`) "Multifaceted" recurring across three sections describing different topics.
- **Location and register.** Body paragraphs across an entire article. Strongest in long-form AI output.
- **Model attribution.** All families. Reflects training-data lexical preferences.
- **Time evolution.** Stable.
- **Sources.** `[grok]`'s Criterion 46.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate in unedited AI long-form.
- **Causal hypothesis (ranked).** Primary: training data over-representation of these focal words. Secondary: tokenizer effects (focal words are single tokens and cheap to repeat). Tertiary: RLHF reward modeling for "professional" lexical choices.
- **Detection difficulty.** Medium. Requires checking word frequency across non-adjacent sentences.
- **False positive risk.** Moderate. Some legitimate writing repeats key terms for rhetorical effect.
- **Fix or remediation.** Replace repeated focal words with varied alternatives. Use synonyms or rephrase to avoid the echo.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.


---

## Section A3-SR: Social-register

The social-register criteria apply when the artifact is a social media post (LinkedIn, Twitter/X, Threads, BlueSky, Reddit, Facebook, Instagram). Some are tolerable in articles but flag immediately in social. The thresholds differ from articles per the explanatory note in the parent SKILL.md "Social-register failures" section.

### A3-SR-001: Imported Spec Language Uppercase

- **Description.** Uppercase severity labels (CRITICAL, HIGH, MEDIUM, LOWER) lifted from technical specs into a LinkedIn or Twitter post. The labels read as press-release register in conversational mode.
- **Concrete examples.**
  1. "CRITICAL update: I have just shipped..." in a LinkedIn post.
  2. "HIGH priority: The team has identified..." in a Twitter thread.
  3. (Per `[opus-expansion]`) "MEDIUM impact: Our quarterly results show..."
- **Location and register.** Social post openers and section transitions. HIGH for social; LOW for articles where the labels can be domain-appropriate.
- **Model attribution.** All families. Most pronounced when the AI is asked to convert technical content to social.
- **Time evolution.** Stable.
- **Sources.** v3.1.0 criterion 38; `[chatgpt]`'s KEEP.
- **Signal strength.** HIGH for social posts.
- **Base rate.** Moderate when AI-drafting social posts derived from internal technical content.
- **Causal hypothesis (ranked).** Primary: training data over-representation of technical specs and press releases. Secondary: helpfulness optimization that preserves the source register.
- **Detection difficulty.** Easy.
- **False positive risk.** Low for social.
- **Fix or remediation.** Translate to conversational equivalents ("significant," "smaller," "minor") or describe without labeling.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT (in the social-post artifact).

---

### A3-SR-002: Article Structure in Social Posts

- **Description.** Topic sentences, transitions ("First," "Second," "Finally"), formal labels ("The principle," "The takeaway," "In summary") imported into a social post. Reads as essay, not conversation.
- **Concrete examples.**
  1. "First, let me set the context. Second, here is what happened. Finally, here is the takeaway." in a LinkedIn post.
  2. "The principle: technology should serve people. The application: our new product does X."
  3. (Per `[chatgpt]`) "In summary, the key insight is that..."
- **Location and register.** Social posts of any length. HIGH for social.
- **Model attribution.** All families when prompted for social drafts.
- **Time evolution.** Stable.
- **Sources.** v3.1.0 criterion 39; `[perplexity]`'s KEEP (cross-link to A2-SUB-011); `[deepseek]`'s DEMOTE for Facebook-specific style (which is genuinely declining).
- **Signal strength.** HIGH for social posts (highly diagnostic for AI-generated LinkedIn and X drafts).
- **Base rate.** High in unedited AI social drafts.
- **Causal hypothesis (ranked).** Primary: training data exposure to essay structures. Secondary: helpfulness optimization that structures output regardless of genre. Tertiary: RLHF reward modeling for "clear" output.
- **Detection difficulty.** Easy.
- **False positive risk.** Low for social. Moderate for longer-form LinkedIn pieces that approach essay length.
- **Fix or remediation.** Reframe as thoughts flowing in real time, not structured exposition. Use sentence-level flow rather than paragraph-level structure.
- **Era status.** Active. Facebook-specific style declining per `[deepseek]`.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-SR-003: Third-Person Narration of First-Person Experience

- **Description.** A post about the author's own experience that uses "the site," "the audit," "the fix" instead of "my site," "my audit," "my fix." Reads as third-party reporting on the author.
- **Concrete examples.**
  1. "The site lost 60 percent of search traffic" (in a personal post; should be "my site").
  2. "The audit identified three issues" (in a personal post; should be "my audit").
  3. (Per `[opus-expansion]`) "The product launched last week" when describing one's own product launch.
- **Location and register.** Personal-brand and founder-post contexts. HIGH for social.
- **Model attribution.** All families when AI-drafting first-person social posts.
- **Time evolution.** Stable.
- **Sources.** v3.1.0 criterion 40; `[cross-validated:manus-ai+perplexity+chatgpt]`.
- **Signal strength.** HIGH for social.
- **Base rate.** Moderate to high in AI-drafted personal social posts.
- **Causal hypothesis (ranked).** Primary: training data exposure to third-person reporting. Secondary: helpfulness optimization that defaults to third-person "objective" register. Tertiary: alignment safety tuning that discourages first-person opinion-stating.
- **Detection difficulty.** Easy.
- **False positive risk.** Low.
- **Fix or remediation.** First-person throughout. Personal pronoun in every paragraph for long-form social.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-SR-004: Lack of Closing Engagement in Social

- **Description.** Posts that close the loop cleanly and walk away. Conversational posts invite response. Per `[perplexity]`'s REVISE: AI Reddit simulation has improved; downgrade from HIGH to MED. Per `[chatgpt]`'s REVISE: lower dependence because some human high-status posters deliberately do not ask questions.
- **Concrete examples.**
  1. A post that ends with the final statement of the lesson rather than inviting comment.
  2. A LinkedIn post that closes with a polished tagline rather than a question.
  3. (Per `[opus-expansion]`) A Twitter thread that ends with "End of thread" rather than "What have you seen?"
- **Location and register.** Social post closers. MED for social (downgraded from HIGH).
- **Model attribution.** All families.
- **Time evolution.** Declining as AI Reddit simulation has improved at including engagement closers per `[perplexity]`.
- **Sources.** v3.1.0 criterion 41; `[perplexity]` REVISE; `[chatgpt]` REVISE.
- **Signal strength.** MEDIUM for social (downgraded from HIGH).
- **Base rate.** Moderate.
- **Causal hypothesis (ranked).** Primary: training data exposure to essay or article structure rather than conversation. Secondary: RLHF reward modeling for "complete" output.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate. Some high-status human posters deliberately omit engagement asks; the discriminator is the writer's typical pattern.
- **Fix or remediation.** End with a question, an observation that begs a follow-up, or a deliberate variant of "tell me what you have seen." Not every post needs it, but the default for conversational posts is yes.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER (in the social-post artifact).

---

### A3-SR-005: Em Dashes in Social Posts

- **Description.** Em-dash usage in social posts. Criterion A3-SS-001 covers em-dash overuse in general writing (HIGH for Claude family, LOW for Llama/GPT-5.1+, applies to all writing). For social posts the threshold tightens: any em-dash usage is a tell. Fast-scrolling social readers register em-dashes as the AI-typical polished-prose signal even when used correctly.
- **Concrete examples.**
  1. A LinkedIn post containing any em-dash.
  2. A Twitter thread with em-dashes around a parenthetical.
  3. (Per `[claude-exec-2026-05-18]`) An Instagram caption using em-dash for emphasis.
- **Location and register.** Social posts. MED for social (promoted from LOW per cross-modal consistency with A3-SS-001).
- **Model attribution.** Claude family (HIGH for em-dash usage in any context, including social). GPT family (DECLINING after GPT-5.1 personalization). Llama (NEAR-ZERO baseline).
- **Time evolution.** Stable for Claude. Declining for GPT.
- **Sources.** v3.1.0 criterion 42; `[claude-exec-2026-05-18]` PROMOTE alongside criterion 11 for cross-modal consistency.
- **Signal strength.** MEDIUM for social (promoted from LOW). HIGH when combined with other social-register failures.
- **Base rate.** Moderate in AI-drafted social content from Claude.
- **Causal hypothesis (ranked).** Primary: training data skew toward edited prose (the model has not learned to suppress em-dashes for social register). Secondary: tokenizer effects.
- **Detection difficulty.** Easy. Character search for U+2014.
- **False positive risk.** Low for social.
- **Fix or remediation.** Replace with commas, parentheses, colons, or sentence breaks. Articles can use em-dashes sparingly for genuine dramatic pause; social posts should not.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT (in the social-post artifact).

---

## Cross-file dependencies

Entries in this file depend on patterns documented in other references/ files:

- **A3-LT-003, A3-BT-001, A3-BT-002.** Family-specific vocabulary fingerprints reference the per-family pattern catalog in `references/model-family-fingerprints.md`. The Claude expansion's A1-CLAUDE-001, A1-CLAUDE-020, A1-GPT-001, and A1-GEMINI-010 entries provide the full per-family detail.
- **A3-SS-001, A3-SS-002, A3-SS-003.** Combined-signal fingerprints (em-dashes + bolded lead-ins + uniform paragraphs) live in `references/combined-signal-fingerprints.md`. B2-COMBO-003 is the canonical Claude.ai default Combo.
- **A3-LT-010, A3-CX-002, A3-FA-001, A3-BT-001.** Calibration tables with per-family base rates and ESL safe-harbor splits live in `references/calibration-tables.md`. The Liang et al. 2023 ESL false-positive risk anchors the safe-harbor.
- **A3-CX-003.** The full A2 substance-and-depth section, with all 15+ sub-patterns, lives in `references/substance-and-depth.md`. This entry exists in the catalog for navigation only.
- **A3-CS-001, A3-CS-003, A3-CS-005, A3-TF-003, A3-TF-004.** Citation-related criteria cross-link to `synthesis-fact-checking` v2.0 references for the full verification protocols. See specifically the C1 protocol sections (nested attribution, paraphrase drift, composite quotes, URL rot vs hallucination, synthetic sources, citation laundering chains).
- **A3-TF-002, A3-BT-002, A3-BT-004, A3-BT-005.** Historical-era patterns (Bard, Llama 1/2, Grok 1, DeepSeek V1/V2, Mistral 7B / Mixtral, Qwen 1/2, pre-instruction-tuning GPT-3) are catalogued in `references/historical-patterns.md` per the compounding-archive principle.
- **All entries.** The consolidated bibliography across this catalog lives in `references/bibliography.md`, including Kobak et al. 2024, Liang et al. 2023, Sharma et al. 2023, Bitton et al. 2025, DeepSeek-R1 (Nature 2025), Plagiarism Today June 2025, Hicks et al. 2024 ("ChatGPT is bullshit"), Pennycook et al. 2015 on pseudo-profundity, Frankfurt 2005, and the per-LLM-cited industry-press references.

## Cross-skill dependencies

- **synthesis-fact-checking v2.0.** The citation-related entries in this file (A3-CS-001 through A3-CS-006, A3-TF-003, A3-TF-004) depend on the C1 protocol sections in the fact-checking skill for verification methodology.
- **synthesis-reader-briefing.** A3-FA-001 (Insider Context Collapse) is detected via the reader-briefing methodology. The fix is procedural and lives in the reader-briefing skill.
- **synthesis-writing-pitfalls.** Universal human-source bad-writing patterns are complementary to the AI-source patterns here. Use both for comprehensive review.
- **synthesis-writing-craft.** Positive principles from the writing-craft tradition complement these negative-pattern entries.
- **synthesis-clean-text.** Generation-time hygiene; this file is for detection-time review. Both are used together.
- **synthesis-content-distribution.** A3-SR-001 through A3-SR-005 (social-register failures) cross-link to the social register vs article register section in synthesis-content-distribution.

---

## End of catalog

This file documents 74 distinct entries: 42 renumbered v3.1.0 criteria plus 32 net-new entries from A3.3 of the unified bucket, with the 16-field template applied uniformly. Era status and zone tags are populated for every entry per the compounding-archive principle and the zone-conditional detection methodology in [design-considerations.md](../../ai-knowledge-rajiv/projects/synthesis-quality-skills-upgrade/resources/artifacts/design-considerations.md).

Em-dash count: zero throughout. Verified via grep at write-time.

