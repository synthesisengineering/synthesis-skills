# Content quality: the catalog at section level

The map of the pattern catalog (sections A1, A2, A3) and the cross-cutting layer (B1 causes, B2 combinations, B3 calibration), with the headline patterns of each and links to the files that hold every entry. Moved verbatim from SKILL.md 4.2.0. Read it to decide which catalog file to open.

Contents:
- The Pattern Catalog: the generated preservation inventory; Section A1 model-family fingerprinting (headline pattern and count per family); Section A2 substance and depth (the 17 tests and the August 2026 additions); Section A3 the 76 refreshed criteria by prefix, with the August 2026 additions and current-model prototypes.
- The Cross-Cutting Layer: B1 causal layer (the twelve-code taxonomy); B2 combined-signal fingerprints (the high-yield combos); B3 two-axis calibration (SSWP and BR, the ESL safe-harbor, quarterly re-calibration).

## The Pattern Catalog

The full catalog has approximately 180 patterns organized across four sections. Each pattern carries the 14-field template plus era status (Active / Declining / Historical / Deprecated) and zone tag. Full per-pattern detail lives in [references/](./) subfiles linked below.

**Generated preservation inventory.** The August 2026 no-removals fixture counts 108 active A1 headers, 17 A2 headers, 76 A3 headers, and 86 B2 headers before historical and nonstandard records. The earlier approximation remains as a historical description; executable preservation tests use the source corpus as the baseline.

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

Full per-pattern detail: [references/model-family-fingerprints.md](model-family-fingerprints.md).

Historical entries for retired family-era markers (Bard "As a large language model trained by..." preamble, GPT-3.5 "As an AI language model" preamble, GPT-3.5 "Here's the thing" intensifier, pre-instruction-tuning GPT-3, early Llama 1 / 2, early Grok 1, early DeepSeek V1 / V2, early Mistral 7B / Mixtral, early Qwen 1 / 2) live in [references/historical-patterns.md](historical-patterns.md). These patterns are largely trained out of current frontier models but remain valuable for forensic analysis of older published content per the compounding-archive principle.

### Section A2: Substance and Depth Detection

Promoted from a single sub-criterion in v3.1.0 (Superficial Depth) to a full top-level section in v4.0. 17 sub-patterns grounded in:

- Frankfurt, *On Bullshit* (2005)
- Hicks, Humphries, Slater, "ChatGPT is Bullshit" (Ethics and Information Technology 26:38, 2024)
- Pennycook et al., Bullshit Receptivity Scale (Judgment and Decision Making 10(6), 2015)
- Sourati et al. 2025 homogenization survey
- Padmakumar and He (2024) on output diversity loss

The 17 sub-patterns: `A2-SUB-001` The deletion test, `A2-SUB-002` The specificity test, `A2-SUB-003` Load-bearing claim count, `A2-SUB-004` Novelty signal, `A2-SUB-005` Insight-to-word ratio, `A2-SUB-006` The any-company test, `A2-SUB-007` Hedging as substance evasion, `A2-SUB-008` Survey-without-claim pattern, `A2-SUB-009` Generic insight, `A2-SUB-010` Both-sides-without-position, `A2-SUB-011` Pseudo-profundity, `A2-SUB-012` Conclusion-shaped paragraphs that do not conclude, `A2-SUB-013` Frictionless-transition padding, plus four additional from cross-LLM contributions.

The most useful editorial capability of v4.0 is the **A2-SUB-001 deletion test**: if a sentence or paragraph can be removed from the piece without losing any claim, evidence, or transition, it is Frankfurt-style bullshit. The any-company test (`A2-SUB-006`) and load-bearing claim count (`A2-SUB-003`) round out a 5-minute editorial pass that catches most slop regardless of authorship.

Full detail and the five-minute editorial workflow: [references/substance-and-depth.md](substance-and-depth.md). Zone tag: BODY-PERSISTENT for all A2 sub-patterns (substance is about what the artifact says).

**August 2026 additive entries.** `A2-SUB-018` Source-detail attenuation and `A2-SUB-019` Plausible-mechanism substitution extend the model-agnostic editorial layer. They describe loss of decisive source detail and unsupported replacement of a real mechanism; neither is an authorship cue.

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

Full per-criterion detail with all 16 fields (14 base + era + zone): [references/detailed-criteria.md](detailed-criteria.md), which also includes a renumbering map from v3.1.0 numbers to the new IDs.

**August 2026 additive entries.** `A3-SS-010` Disproportionate structure and `A3-FA-009` Voice normalization record two cross-model editorial harms without assigning them to a provider family.

**August 2026 current-model prototypes.** `A3-SS-011` Current-Claude deliverable padding, `A3-TF-008` Current tool/XML/reference residue, `A3-BT-014` text-only intent without authorized action, `A3-FA-010` private working-language leakage, and `A3-FA-011` non-material work/correction chronology extend the catalog additively. They use dated model-and-surface scope, preserve counterexamples, publish no prevalence estimates, and never establish authorship alone. `A3-BT-013` remains reserved as the legacy system-prompt-bleed locator.

The dated evidence ledger and controlled-test quarantine live in [references/current-model-candidates.md](current-model-candidates.md). Candidates in quarantine are research inputs, not active tells.

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

Full per-criterion attribution: [references/calibration-tables.md](calibration-tables.md) (causal column).

### B2: Combined-Signal Fingerprints

The v3.1.0 heuristic ("5+ medium-confidence indicators equals very likely AI") is replaced with 86 specific combinations where co-occurrence can be more informative than a raw count. The inherited catalog's exact false-positive estimates were not produced from a preserved labeled corpus and must not be treated as measured performance. Keep the combinations as editorial and research hypotheses; validate them on the target genre and population before making any provenance inference.

High-yield combos to know:

- **`B2-COMBO-001` ChatGPT 4o research combination.** Saturated vocab + exhausted metaphors + section-ending summary. The inherited below-1-percent estimate is unvalidated and non-operational.
- **`B2-COMBO-003` Claude.ai research combination.** Em-dashes (high density) + bulleted bolded lead-ins + uniform paragraph length. The inherited below-0.5-percent estimate is unvalidated and non-operational.
- **`B2-COMBO-007` Fake-expertise stack.** Vague attribution + hallucinated citation + generic insight. Definitive when the citation can be verified absent.
- **`B2-COMBO-010` ESL false-positive trap (NEGATIVE marker).** Uniform paragraph length + restricted vocabulary + heavy transitions. The cornerstone signature for AI is also the cornerstone signature for non-native English writing per Liang et al. 2023. This combination is a **NEGATIVE marker**: do not flag as AI unless combined with at least one register-specific AI marker (saturated vocabulary cluster, em-dash density, system-prompt artifact, chatbot reflex).

Full catalog of all 86 combos: [references/combined-signal-fingerprints.md](combined-signal-fingerprints.md).

### B3: Two-Axis Calibration

Each criterion is split into two axes:

- **SSWP (legacy Signal Strength When Present).** An inherited ordinal research score, not `P(AI | pattern)` and not an authorship probability. A posterior probability requires a population prior plus a measured likelihood for AI and relevant human comparison classes. Preserve the old 0.0-to-1.0 values as dated hypotheses until a labeled corpus supports recalibration; use the qualitative editorial tier, evidence status, context, and counterexamples in reviews.
- **BR (legacy Base Rate).** A dated per-family occurrence estimate, split for zone-conditional patterns into BR-artifact-body and BR-full-response. Treat an entry as measured only when its exact model, surface, task distribution, sample size, collection date, and source are preserved; otherwise it is an unvalidated estimate.

The split reveals that some widely cited markers (em-dash density) have very high signal strength but plummeting base rate in newer GPT models, while others (uniform paragraph length) have moderate signal strength but very high base rate that overlaps with ESL writing.

**ESL safe-harbor (structural requirement).** Per Liang et al. arxiv 2304.02819 (verified), GPT detectors misclassify a large fraction of non-native English writing as AI-generated. Any detection that triggers the cornerstone signature must be combined with at least one register-specific AI marker. Calibration discipline: hard-negative-mine against TOEFL-style writing.

**Quarterly re-calibration.** Per the GPT-5.1 anti-em-dash personalization that shifted Claude vs. ChatGPT BR rankings by 30+ points in a single release, calibration drifts. Re-calibrate every quarter.

Full per-family per-criterion table: [references/calibration-tables.md](calibration-tables.md).
