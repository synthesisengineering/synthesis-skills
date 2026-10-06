# Calibration Tables, part 2 of 2

Part 2 of the file split from [calibration-tables.md](calibration-tables.md), which keeps the opening sections and lists every part. The text below is unchanged.

Contents:
- B3.3 Framework for calibrating new criteria: Reasoning-chain template for Estimated entries
- B3.4 ESL safe-harbor (Liang et al. arxiv 2304.02819 verified): The mechanical safe-harbor rule; Why this matters editorially; Liang anchor measurements (from arxiv 2304.02819)
- B3.5 Quarterly re-calibration discipline: The empirical anchor; The discipline; Per-family calibration adjustments (ChatGPT contribution)
- B3.6 Zone-conditional notes: Patterns with meaningful BR-artifact-body vs. BR-full-response differential; Detector mode implications; Boundary detection between wrapper and body
- Cross-file references

## B3.3 Framework for calibrating new criteria

Each new A1 or A2 pattern entry should follow this eight-step calibration workflow on entry to the catalog or on quarterly review:

1. **Identify primary and secondary cause.** Map the pattern to the B1 twelve-code causal taxonomy. Rank causes by contribution. A single pattern can have multiple causes (e.g., RLHF reward + training-data skew + system-prompt artifact).

2. **Score SSWP against B3.2 anchors.** Use the closest empirical entry as the calibration reference. High-anchors:
   - A3-23 (Hallucinated citations, 0.95 to 0.99 SSWP, empirical via Walters Wilder 2023, Chelli 2024)
   - A3-33 (Saturated AI vocab cluster, 0.85 to 0.95 SSWP, empirical via Kobak 2406.07016)
   - A3-11 (Em-dashes density above 5/500 words, 0.7 to 0.85 SSWP, empirical via Plagiarism Today June 2025 verified)
   - A1-GPT-002 (Sycophantic opener "Great question!", 0.85 to 0.95 SSWP, empirical via OpenAI Apr 2025 rollback)
   - A2-SUB-001 (The deletion test, 0.85 to 0.95 SSWP when sustained, empirical via Hicks 2024 Frankfurt-bullshit framing)

   Low-anchors:
   - A3-14 (Hollow intensifiers, 0.25 to 0.4 SSWP, estimated)
   - A3-16 (Curly vs straight quotes, 0.25 to 0.4 SSWP, estimated)
   - A1-DEEPSEEK-007 (Different sentence-rhythm baseline, 0.25 to 0.4 SSWP standalone, estimated)

3. **Estimate BR per family with confidence interval.** Sample current frontier outputs from each major family. Sample size: at least 100 outputs per family across at least three prompt categories (essay, technical, conversational). Where empirical anchors exist (Kobak, Walters and Wilder, Chelli, Buchanan/Hill/Shapoval), cite them. Where they do not, provide a reasoning chain and a confidence interval.

4. **Rank per-family frequency.** Which families produce the pattern at the highest rate? Per-family ranking allows targeted detection. Use qualitative tiers (High, Medium, Low) or quantitative ranges depending on data quality.

5. **Label Empirical or Estimated.** Each entry is labeled with provenance. Empirical entries cite the measurement. Estimated entries carry a reasoning chain that includes the closest analogous empirical anchor and the adjustment factor for the differences.

6. **Check combination eligibility.** Is this pattern part of any B2 combo from [combined-signal-fingerprints.md](combined-signal-fingerprints.md)? If so, note the combo IDs. A pattern that participates in multiple high-fidelity combos has higher diagnostic value than one that does not.

7. **Apply ESL safe-harbor.** If the pattern's BR overlaps with ESL writers per Liang 2304.02819, flag for NEGATIVE-marker treatment. See B3.4 below. The cornerstone signature (uniform paragraph length + restricted vocabulary + heavy transitions) is the canonical safe-harbor trigger.

8. **Tag recency and zone.** Note the most recent model version the BR estimate was drawn from. Use 2026-05 as the recency floor for "current." Patterns from older models are flagged Historical with explicit dating. Apply the zone tag: WRAPPER-OPENER, WRAPPER-CLOSER, BODY-PERSISTENT, HYBRID, or MID-BODY-INSERT.

### Reasoning-chain template for Estimated entries

For any Estimated entry, the reasoning chain should answer:

- What is the closest empirical anchor? (Cite from B3.2 or bibliography.md.)
- What is the adjustment factor between the anchor and this pattern? (Why higher or lower SSWP/BR?)
- What is the confidence interval? (e.g., "BR-Claude 30% to 50%, MED confidence" rather than a single point estimate.)
- What would falsify this estimate? (Specific observation that would force re-calibration.)

Example reasoning chain (A1-CLAUDE-001 "It is important to note"):
- Anchor: A1-GPT-001 "Delve" cluster (Kobak 2406.07016, BR 10% for "delve" specifically in 2024 PubMed abstracts).
- Adjustment: "It is important to note" is a phrase rather than a single word, but functions as the same kind of focal-tic. Probability of occurrence per response is higher than any single word from the Kobak cluster because the phrase substitutes for many sentence types.
- Confidence interval: 40% to 60% in Claude analytical output. Tight on direction (Claude more than GPT), loose on absolute magnitude.
- Falsification: A 200-output Claude 4.7 sample across analytical prompts showing fewer than 30% or more than 70% would force re-calibration.

---

## B3.4 ESL safe-harbor (Liang et al. arxiv 2304.02819 verified)

The ESL false-positive trap is one of the structural risks of family-conditional detection. Per Liang et al. 2023 (verified-arxiv:2304.02819, "GPT detectors are biased against non-native English writers"), GPT detectors misclassify a large fraction of non-native English writing as AI-generated. Liang's paper documents misclassification rates of 50% to 70% on TOEFL essay corpus across several commercial detectors. The mechanism: the cornerstone AI signature (uniform paragraph length, restricted vocabulary, heavy transitions) is also the cornerstone ESL signature.

### The mechanical safe-harbor rule

The v4.0 safe-harbor rule is mechanical and absolute:

1. **Any detection of the cornerstone signature** (uniform paragraph length AND restricted vocabulary AND heavy transitions) **must be combined with at least one register-specific AI marker** before flagging as AI. Register-specific markers include:
   - **Focal-word cluster:** saturated AI vocabulary, A3-33; cluster of 3+ from the Kobak focal-word set in 500 words.
   - **Em-dash density:** above 5 per 500 words, A3-11; the body-zone em-dash signature.
   - **System-prompt artifact:** A3-19 chatbot artifacts; A3-15 markdown leakage in plain-text channels; A3-NEW-010 system-prompt artifact bleed.
   - **Chatbot reflex:** A3-36 concierge tone; A1-CLAUDE-009 "I'd be happy to help" / "I appreciate your" openers; A1-GPT-002 sycophantic opener; A1-GEMINI-009 "Absolutely" with follow-on qualification.

2. **Detection of the cornerstone signature alone**, in the absence of register-specific markers, is treated as the NEGATIVE marker B2-COMBO-010 from [combined-signal-fingerprints.md](combined-signal-fingerprints.md). The text is more likely ESL human writing than AI.

3. **Pangram's training discipline.** Per arxiv 2402.14873 (Emi and Spero, cited in Claude exec; not independently verified at expansion time), Pangram's TOEFL hard-negative mining achieved near-zero false-positive rate specifically through this kind of safe-harbor calibration. The v4.0 system replicates the discipline mechanically.

4. **No exception, no escape hatch.** The safe-harbor is a primary structural constraint on the methodology. Any detection methodology that does not implement this discipline is structurally biased against non-native English writers. There is no "but the text looks really AI to me" override.

### Why this matters editorially

When an editor reviews an AI-assisted submission from an ESL author, the cornerstone signature alone will fire on prose that the author wrote themselves. Flagging that prose as AI-generated is a calibration failure that erodes trust in the detector and harms the writer. The register-specific corroboration requirement prevents that failure mechanically.

### Liang anchor measurements (from arxiv 2304.02819)

- GPTZero misclassified 19% of TOEFL essays as AI (sample of 91 TOEFL essays from native Chinese writers).
- Originality.ai misclassified 70%+ of the same TOEFL corpus.
- Crossplag misclassified 60%+ of the same TOEFL corpus.
- The misclassification correlated with measured perplexity differences between native and non-native English prose, not with actual AI generation.

These measurements anchor the safe-harbor rule. v4.0's calibration discipline keeps the false-positive rate on ESL writing at or below the levels Pangram demonstrated achievable through TOEFL hard-negative mining (arxiv 2402.14873).

---

## B3.5 Quarterly re-calibration discipline

### The empirical anchor

GPT-5.1's anti-em-dash personalization shifted Claude vs. ChatGPT BR rankings by 30+ points within a single release. Em-dash overuse moved from "GPT signature" to "Claude signature" in calendar weeks. Calibration drifts. Recalibration is mandatory at a quarterly cadence.

### The discipline

1. **Quarterly cadence.** Every quarter, sample current frontier outputs from each major family and update the BR columns of the B3.2 master calibration table. Sample size: at least 100 outputs per family across at least three prompt categories (essay, technical, conversational).

2. **Era-status updates.** Patterns whose BR has dropped significantly get era-status updates. The progression is Active → Declining → Historical. Patterns are never removed; they are retired with their era-of-prevalence metadata intact. Compounding-archive principle: historical patterns retain diagnostic value for older content and for explicit dating purposes (see [historical-patterns.md](historical-patterns.md)).

3. **Documented era transitions:**
   - **A1-GPT-007 "As an AI language model" preamble:** 15-25% in 2023; near-zero in 2026. Retired to Historical.
   - **A1-GPT-002 sycophantic opener (GPT-4o variant):** 60-80% in 2024; 15-25% in 2026 post-April 2025 sycophancy rollback. Active but Declining.
   - **A1-GPT-001 GPT-5.1 em-dash density:** 70-80% in early 2025; 30-50% post-2025-personalization. Active but Declining (em-dash overuse moved from primary-GPT to primary-Claude signature).
   - **A1-LLAMA-historical era patterns (Llama 1 and 2):** Historical for analyzing 2023 era content; current Llama 4 baseline differs.
   - **A1-GEMINI-019 / Bard "I'm still learning, but..." self-deprecation:** Deprecated in Gemini 2.5 Pro but still appears in some contexts. Historical.
   - **A1-GROK-historical Grok 1 patterns:** Historical for analyzing 2023-2024 era content.
   - **A1-DEEPSEEK-historical V1/V2 patterns:** Historical for V1/V2 era; current R1 and V3 patterns differ.
   - **A1-QWEN-historical Qwen 1/2 patterns:** Historical for analyzing pre-Qwen 3 content.
   - **A1-MISTRAL-historical Mistral 7B / Mixtral patterns:** Historical for analyzing 2023-2024 era content.
   - **A1-BARD-historical (pre-Gemini Bard):** Bard 91% hallucinated citation rate per Walters Wilder 2023 anchors the family historical baseline.
   - **Reddit-voice simulation (A3-41 social-register):** weakening as Reddit corpus improves and models train against the distinctive markers.

4. **Cross-family contamination flag.** Per Copyleaks 2025, 74.2% of DeepSeek output was classified as OpenAI by their detector. Some family attributions are unreliable without ensemble methods or additional signals. Flag patterns with cross-family contamination for ensemble-only detection. The flag applies to:
   - DeepSeek family: apply A1-GPT-* patterns with full confidence; rely on A1-DEEPSEEK-001 (`<think>` leakage), A1-DEEPSEEK-002 (language mixing), and A1-DEEPSEEK-010 (LaTeX in non-technical) for definitive DeepSeek attribution.
   - Mistral family: per Copyleaks 26% classified as OpenAI, 8.8% as Llama. Apply A1-GPT-* and A1-LLAMA-* with caution; rely on A1-MISTRAL-001 (French syntax) and A1-MISTRAL-005 (open-source register) for definitive attribution.

5. **Recency floor.** 2026-05 is the recency floor for "current" frontier models. The v3.1.0 references file dates itself 2026-05 and is the recency floor for retrospective calibration.

6. **Re-calibration triggers beyond quarterly.**
   - Major model releases (Claude 5, GPT-6, Gemini 4, Llama 5): immediate re-calibration of all family-specific BR columns within 30 days of release.
   - Sycophancy rollbacks, personality version bumps, anti-watermark personalizations: re-calibration of affected criteria within 14 days.
   - Major detection-tool publications (Pangram, Originality.ai, GPTZero, Copyleaks): re-validate against any cross-published BR figures within 30 days.

### Per-family calibration adjustments (ChatGPT contribution)

Recent evidence supports five broad family-level calibration adjustments:

- **Anthropic Claude models** remain unusually strong on uncertainty management and low hallucination rates relative to peers, so style criteria should often weigh slightly less and substance criteria slightly more.
- **OpenAI GPT family members** often combine high polish with stronger guessing pressure, so calibration-mismatch (A3-NEW-028) and source-theater (A3-NEW-027) criteria should weigh more.
- **Gemini** needs stronger wrapper notes because its consumer and search surfaces create different citation behaviors than its base model capability would suggest. A1-GEMINI-001 (plain-text markdown leak) remains its single strongest channel-specific signal.
- **Meta Llama, Mistral, Qwen, and other open-weight families** require heavier wrapper and fine-tune caveats because provider voice is partially preserved but deployment variance is much larger.
- **DeepSeek** requires dated annotations because some once-useful fingerprints (e.g., mixed-language glitches per A1-DEEPSEEK-002) were explicitly reduced in later updates.

---

## B3.6 Zone-conditional notes

Most patterns are BODY-PERSISTENT (substantive content, anywhere in body), meaning BR-artifact-body and BR-full-response are equal. The patterns where the two values differ meaningfully are catalogued here.

### Patterns with meaningful BR-artifact-body vs. BR-full-response differential

| Pattern | Zone tag | BR-body | BR-full | Differential | Why it matters |
|---------|----------|----------|----------|---------------|----------------|
| A1-GPT-002 Sycophantic opener ("Great question!", "Certainly!") | WRAPPER-OPENER | 5-15% | 70-90% (GPT-4o) | 4x to 6x | **Largest BR split in catalog.** Flagging sycophancy on a clean article body is a calibration failure. |
| A1-CLAUDE-003 "You're absolutely right!" agent reflex | WRAPPER-OPENER | 5-10% | 25-45% agent contexts; 30-55% multi-turn | 5x to 8x | Agent-specific; appears even when user has made no claim to be right about. |
| A1-CLAUDE-009 "I appreciate your" / "Thank you for" openers | WRAPPER-OPENER | 5-15% | 30-50% multi-turn; DeepSeek observed 80%+ for "I'm happy to help" | 4x to 8x | Politeness ritual; concentrated in opener zone. |
| A1-CLAUDE-011 "I hope this helps" closer | WRAPPER-CLOSER | 5-15% | 60-80% multi-turn | 6x to 12x | Largest closer-zone signal in the Claude family. |
| A1-CLAUDE-013 Concierge tone closer | WRAPPER-CLOSER | 5-15% | 50-70% | 4x to 7x | The Claude wrapper-closer fingerprint. |
| A3-19 Chatbot communication artifacts | HYBRID (wrapper-heavy) | 5-15% | 50-80% conversational deployments | 5x to 15x | Distinct from criteria 36/concierge tone: this is the structural tell. |
| A3-36 Concierge tone | HYBRID (wrapper-heavy) | 15-25% (GPT post-rollback); 50-70% (Claude still active) | 50-80% across families | 1.5x to 4x | The general tonal pattern; less zone-localized than the structural opener/closer markers but still elevated in wrapper. |
| A1-GPT-007 "As an AI language model" preamble (HISTORICAL) | WRAPPER-OPENER | near-zero current | 15-25% (2022-2024 baseline) | historical | The canonical 2022-2024 wrapper-opener; near-zero current. |
| A1-GEMINI-004 "Let's dive in" / "Without further ado" opener | WRAPPER-OPENER | 5-15% | 20-40% substantive prompts | 2x to 4x | |
| A1-GEMINI-009 "Absolutely" opener with follow-on qualification | WRAPPER-OPENER | 5-15% | HIGH Gemini | 3x to 5x | |
| A1-GPT-009 "In conclusion" / "To wrap up" closer | WRAPPER-CLOSER (mild) | 30-50% | 60-80% multi-paragraph | 1.5x to 2x | More body-mid-document than pure wrapper; included for completeness. |
| A1-GPT-017 "I'd Be Happy To" service register | WRAPPER-CLOSER | 5-15% | HIGH GPT-4o assistant contexts | 3x to 6x | |
| A1-GPT-019 Enthusiastic sign-offs ("I hope this helps! Let me know if you need anything else.") | WRAPPER-CLOSER | 5-15% | HIGH GPT-4o, persists in GPT-5 | 4x to 8x | |
| A3-NEW-010 System-prompt artifact bleed ("You are a helpful AI assistant") | WRAPPER-OPENER | near-zero | LOW BR overall but definitive when present | high diagnostic value | Rare but smoking-gun. |
| A1-CLAUDE-006 Refusal-shaped close with safety hedge (advisory contexts) | WRAPPER-CLOSER | 40-50% general; 70-90% advisory prompts | 50-70% general; 80-95% advisory | 1.2x to 2x | Closer-localized but extends into body for advisory-register substantive content. |
| A1-DEEPSEEK-001 `<think>` tag leakage | MID-BODY-INSERT | LOW (API misconfiguration only) | LOW | distinct zone | Mid-body insert; not wrapper. |
| A1-QWEN-001 CJK punctuation slips | MID-BODY-INSERT | LOW | LOW | distinct zone | Mid-body insert; Unicode-detectable. |
| A1-CLAUDE-012 Reasoning-trace "Wait" / "Actually" leakage | MID-BODY-INSERT | 15-30% extended-thinking | 15-30% | mid-body | |
| A1-GEMINI-007 Encrypted thought leakage | MID-BODY-INSERT | ~4% custom API wrappers | ~4% | mid-body | Single-LLM-sourced; flagged for verification. |
| A3-NEW-002 Sycophancy drift across turns | HYBRID | rate increases 110% across 20 turns | full-response amplified | turn-amplified | Multi-turn cumulative. |
| A3-NEW-026 Search-answer wrapper voice | HYBRID | full-piece structural shape | full-piece | structural | Wrapper-shape across the whole artifact. |

### Detector mode implications

- **Artifact mode (default for editorial use):** apply only BODY-PERSISTENT, HYBRID, and MID-BODY-INSERT patterns. Skip WRAPPER-OPENER and WRAPPER-CLOSER. False-positive rate stays low when only the artifact is being audited.
- **Full-response mode (forensic chat-log analysis):** apply all patterns including wrapper-only.
- **Reporting clarity:** detection reports should explicitly distinguish "no wrapper detected (artifact-only mode)" from "wrapper present, no sycophancy markers." A report that says "sycophancy detected" for a piece that contains only the artifact body is a calibration failure.

### Boundary detection between wrapper and body

When both wrapper and body are present in a single input, common boundary markers include:

- A sentence that names the substantive task ("Here's the migration plan you asked about:").
- An explicit transition ("Let me get into it:", "Diving in:").
- The start of a structured section header or bullet list.
- The end of the polite opener and the start of declarative content.

The heuristics are conservative: when in doubt, expand the wrapper boundary. False-positive cost (missing a wrapper-zone marker) is lower than false-positive cost (flagging body content with a wrapper-only pattern).

---

## Cross-file references

- [SKILL.md](../SKILL.md): main skill entry point; consult for the methodology and confidence-based evaluation process the calibration here supports.
- [detailed-criteria.md](detailed-criteria.md): full per-pattern entries for the 42 v3.1.0 criteria (A3), refreshed for v4.0 with era metadata and zone tags.
- [model-family-fingerprints.md](model-family-fingerprints.md): full A1 per-family pattern entries with the 14-field per-pattern template.
- [substance-and-depth.md](substance-and-depth.md): full A2 sub-pattern entries anchored in Frankfurt/Pennycook/Hicks-Humphries-Slater.
- [combined-signal-fingerprints.md](combined-signal-fingerprints.md): B2 inventory of 86 high-fidelity combined-signal fingerprints. The combination signals referenced throughout this file (B2-COMBO-003 default Claude.ai combo, B2-COMBO-010 ESL safe-harbor NEGATIVE marker, B2-COMBO-021 personality-v2 GPT opener) are catalogued there.
- [historical-patterns.md](historical-patterns.md): historical and deprecated patterns with era-of-prevalence metadata; consult for forensic dating of older content.
- [bibliography.md](bibliography.md): consolidated bibliography with verification status. The empirical anchors cited throughout this file (Kobak 2406.07016, Liang 2304.02819, Walters and Wilder 2023, Chelli JMIR 2024, Buchanan/Hill/Shapoval Sage 2024, Plagiarism Today June 2025 verified, PLoS One Zaitsu et al. 2025, GPTZero methodology, Pangram Labs 2026, Turnitin 2026, Copyleaks 2025) all resolve there.

---

Part of the [synthesis writing](https://synthesiswriting.org) craft. Calibration is the difference between a detector and a guess.
