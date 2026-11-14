# Detailed Criteria Reference (v4.0)

This file is split by section so that each file fits one read. The opening sections stay here; the rest is in the parts below, in order.

Contents:
- In this file: Conventions (prefix scheme, 16-field template, em-dash constraint) and the renumbering map (v3.1.0 to v4.0).
- Part 1, [detailed-criteria-1-lt.md](detailed-criteria-1-lt.md): Section A3-LT: Language and Tone (A3-LT-001 to A3-LT-015, 15 entries)
- Part 2, [detailed-criteria-2-ss-tf.md](detailed-criteria-2-ss-tf.md): Section A3-SS: Style and Structural (A3-SS-001 to A3-SS-011, 11 entries); Section A3-TF: Technical and Formatting (A3-TF-001 to A3-TF-008, 8 entries)
- Part 3, [detailed-criteria-3-cs-cx-hd-ce.md](detailed-criteria-3-cs-cx-hd-ce.md): Section A3-CS: Citation and Sourcing (A3-CS-001 to A3-CS-006, 6 entries); Section A3-CX: Context-Specific (A3-CX-001 to A3-CX-005, 5 entries); Section A3-HD: Hyperbolic and Dramatic (A3-HD-001 to A3-HD-007, 7 entries); Section A3-CE: Confidentiality and Exposure (A3-CE-001 to A3-CE-002, 2 entries)
- Part 4, [detailed-criteria-4-bt.md](detailed-criteria-4-bt.md): Section A3-BT: Behavioral and Tonal (A3-BT-001 to A3-BT-014, 13 entries)
- Part 5, [detailed-criteria-5-fa-sr.md](detailed-criteria-5-fa-sr.md): Section A3-FA: Frame and Audience (A3-FA-001 to A3-FA-011, 11 entries); Section A3-SR: Social-register (A3-SR-001 to A3-SR-005, 5 entries); Cross-file dependencies; Cross-skill dependencies; End of catalog

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
