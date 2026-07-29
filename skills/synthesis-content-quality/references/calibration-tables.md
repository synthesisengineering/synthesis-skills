# Calibration Tables

Companion to [SKILL.md](../SKILL.md). The per-pattern calibration data the skill's confidence-based evaluation depends on.

This file holds the v4.0 calibration anchor set: signal-strength-when-present (SSWP) scores, base rates by model family, zone-conditional base-rate splits, the ESL safe-harbor mechanical rule, and the quarterly re-calibration discipline that keeps the catalog honest as model behaviour shifts. Sources are cited where empirical anchors exist; estimates are explicitly labeled and accompanied by a reasoning chain.

Recency floor: **2026-05**. Patterns from older models carry Era-status tags (Active, Declining, Historical, Deprecated). See [historical-patterns.md](historical-patterns.md) for full retired-pattern entries; see [bibliography.md](bibliography.md) for full source list.

---

## B3.1 Methodology

### Two-axis calibration

A single pattern observation does not justify a single confidence number. Calibration in this catalog is two-axis:

1. **Signal-strength-when-present (SSWP).** Conditional probability that text containing the pattern is AI-generated, ignoring the prior probability of AI versus human. SSWP is what we mean when we say "this marker is HIGH-confidence." Tiers:

   | SSWP | Qualitative tier | Plain-English reading |
   |------|------------------|------------------------|
   | above 0.85 | "smoking gun" / very high / definitive | The marker is near-diagnostic on its own when present. |
   | 0.60 to 0.85 | strong / high | The marker is strong evidence but should be combined with at least one corroborating signal. |
   | 0.40 to 0.60 | moderate / medium | The marker contributes evidence but is not by itself sufficient. |
   | below 0.40 | ambient / low | The marker is observable but provides weak standalone evidence; it earns weight only in cluster. |

2. **Base rate in unedited AI output (BR).** The percentage of unedited AI outputs from a given family that contain the pattern. Tiers:

   | BR | Tier | Plain-English reading |
   |----|------|------------------------|
   | above 60% | Very common | The pattern is present in most unedited outputs. |
   | 30% to 60% | Common (also "Frequent") | The pattern is present in a substantial minority. |
   | 10% to 30% | Occasional | The pattern is present in a minority. |
   | below 10% | Rare | The pattern is uncommon. |

### Per-family resolution and zone-conditional split

Base rate is resolved by model family because per-family BR rankings can vary by 30+ points within a single model release. The base-rate column is further split by zone (per the design-considerations.md 2026-05-18 entry on zone-conditional detection):

- **BR-artifact-body** is the rate within the substantive content the user requested. This is what editorial reviewers actually see in submitted drafts.
- **BR-full-response** is the rate across the full LLM response including wrapper-opener (sycophancy, polite framings) and wrapper-closer (concierge tone, "Is there anything else?") zones.

For body-zone patterns the two values are equal. For wrapper-only patterns BR-artifact-body is near-zero and BR-full-response is high. The split matters because flagging "You're absolutely right!" sycophancy on a clean article body is a calibration failure that erodes editorial trust in the detector.

### Empirical or Estimated label

Every entry carries one of two provenance labels:

- **Empirical** anchors the number in a published measurement. Citation is required (Kobak 2406.07016, Liang 2304.02819, Walters and Wilder 2023, Chelli JMIR 2024, Buchanan/Hill/Shapoval Sage 2024, Plagiarism Today June 2025 verified, etc.).
- **Estimated** acknowledges no public measurement exists. Reasoning chain is included. Estimates are reviewed quarterly.

### Recency floor and per-pattern era

All measurements treat 2026-05 as the recency floor for "current" frontier models. Patterns from older models are flagged Historical with explicit dating. The compounding-archive principle applies: patterns are never removed; they retire with their era-of-prevalence metadata intact.

---

## B3.2 Master calibration table

The table below covers every pattern entry in [detailed-criteria.md](detailed-criteria.md) (A3, the 42 v3.1.0 criteria refreshed), [model-family-fingerprints.md](model-family-fingerprints.md) (A1, ~170 family-specific patterns), and [substance-and-depth.md](substance-and-depth.md) (A2, 17 sub-patterns).

Wide tables are split into family-group sub-tables so the columns fit. Within each table, rows are pattern IDs (the same identifiers used across all v4.0 references files).

### A3 (refreshed v3.1.0 criteria): Claude + GPT split

Zone for all A3 rows is BODY-PERSISTENT unless flagged otherwise in the Notes column. Empirical entries cite source. Estimated entries reflect cross-LLM convergent observation.

| Pattern | SSWP | BR-Claude (body) | BR-Claude (full) | BR-GPT (body) | BR-GPT (full) | Strongest family | E/Est | Notes |
|---------|------|-------------------|--------------------|----------------|------------------|-------------------|-------|-------|
| A3-01 Undue emphasis on importance | 0.4 to 0.6 | 40-60% | 40-60% | 30-50% | 30-50% | Claude | Est. | Saturated vocab overlap. |
| A3-02 Promotional/travel-brochure language | 0.4 to 0.6 | 20-35% | 20-35% | 35-55% | 35-55% | GPT (marketing) | Est. | |
| A3-03 Editorial commentary ("It's important to note") | 0.5 to 0.65 | 40-60% | 45-65% | 25-40% | 30-45% | Claude | Emp. (Kobak 2406.07016) | |
| A3-04 Superficial -ing participial phrases | 0.4 to 0.55 | 25-45% | 25-45% | 30-50% | 30-50% | GPT | Est. | |
| A3-05 Negative parallelism ("not X but Y") | 0.55 to 0.7 | 35-55% | 35-55% | 40-60% | 40-60% | GPT | Est. (Pennycook BSRS) | Promote MED to HIGH per Claude exp.; ChatGPT review demotes. |
| A3-06 Transition-word saturation | 0.45 to 0.6 (density above 3/300 words) | 50-70% | 50-70% | 60-80% | 60-80% | GPT | Est. | Promote LOW to MED. |
| A3-07 Section-ending summaries | 0.5 to 0.65 | 60-80% | 60-80% | 60-80% | 60-80% | Claude/GPT comparable | Est. | |
| A3-08 Rule of three | 0.4 to 0.55 | 50-70% | 50-70% | 60-80% | 60-80% | GPT (tripartite-markdown) | Est. | Gemini 70% per A1-GPT-008. |
| A3-09 Passive voice / "has been described as" | 0.3 to 0.45 | 30-50% | 30-50% | 30-50% | 30-50% | Gemini (A1-GEMINI-010) | Est. | |
| A3-10 Uniform sentence/paragraph length | 0.4 to 0.6 | 85-95% | 85-95% | 80-95% | 80-95% | Universal | Emp. (Liang 2304.02819; GPTZero) | **ESL CAVEAT.** Negative marker without register-specific corroboration. See B3.4. |
| A3-11 Em-dash overuse | 0.7 to 0.85 (above 5/500 words) | 80-95% | 80-95% | 40-65% (GPT-5.1+ low) | 40-65% | Claude | Emp. (Plagiarism Today June 2025 verified; DeepSeek GLTR 2.3x) | GPT-5.1 anti-em-dash personalization shifted by 30+ points. |
| A3-12 Bulleted bolded lead-ins | 0.5 to 0.65 | 50-70% | 50-70% | 60-80% (GPT-4o) | 60-80% | GPT-4o; Claude high | Est. (Walsh CHR 2024) | Promote MED to HIGH. |
| A3-13 Excessive bolding/formatting | 0.35 to 0.5 | 40-60% | 40-60% | 70-85% (GPT-4o) | 70-85% | GPT-4o | Est. | Reducing in GPT-4.1, GPT-5. |
| A3-14 Emoji in inappropriate contexts | 0.5 to 0.7 (when present in formal artifact) | below 5% | below 5% | 10-25% | 10-25% | Gemini consumer | Est. | Largely trained out of formal Claude. |
| A3-15 Markdown leakage in plain-text channel | 0.85 to 0.95 | 20-40% | 20-40% | 40-65% | 40-65% | Gemini (near-deterministic CLI) | Emp. (gemini-cli #8392; 9to5Google Sep 2025) | |
| A3-16 Curly vs straight quote inconsistency | 0.25 to 0.4 | 10-25% | 10-25% | 10-25% | 10-25% | Universal | Est. | |
| A3-17 Title case in headers (journalism) | 0.3 to 0.45 | 20-40% | 20-40% | 25-45% | 25-45% | GPT | Est. | |
| A3-18 Placeholder text | 0.95 to 0.99 | below 2% | below 2% | below 2% | below 2% | Universal (rare, definitive) | Emp. (WikiProject AI Cleanup) | |
| A3-19 Chatbot communication artifacts | 0.85 to 0.95 | 5-15% | 50-75% | 5-15% | 60-80% | GPT in conversational deploy | Est. | **WRAPPER-HEAVY** zone-conditional: full 5-15x body. |
| A3-20 Broken/fabricated links and codes | 0.95 to 0.99 (verified non-resolving) | 15-20% | 15-20% | 18-29% (GPT-4); 20% with 56% errors (GPT-4o, Chelli) | 18-29% | GPT search-aug (all non-resolving) | Emp. (Walters Wilder 2023; Chelli JMIR 2024; Buchanan Sage 2024) | |
| A3-21 Citation abnormalities | 0.55 to 0.7 | 25-40% | 25-40% | 30-50% | 30-50% | GPT | Emp. (Walters Wilder 2023) | |
| A3-22 Suspiciously long edit summaries | 0.5 to 0.65 (Wikipedia) | varies | varies | varies | varies | GPT | Est. (WikiProject) | Context-specific. |
| A3-23 Hallucinated citations | 0.95 to 0.99 | 15-20% (Claude 3.7) | 15-20% | 18-29% (GPT-4); 30-55% (GPT-3.5) | 18-29% | GPT-3.5 historic; Bard 91% historic | Emp. (Walters Wilder 2023; Chelli JMIR 2024; Buchanan Sage 2024) | PROMOTE. |
| A3-24 Vague attribution ("Studies show") | 0.6 to 0.75 | 25-45% | 25-45% | 25-45% | 25-45% | Gemini (highest density) | Est. (cross-validated 5 LLMs) | Promote MED to HIGH. |
| A3-25 Industry-specific slop | 0.5 to 0.65 (cluster of 3+) | 40-60% | 40-60% | 50-70% | 50-70% | GPT marketing | Emp. (Kobak anchor) | |
| A3-26 Lack of personal detail | 0.45 to 0.6 | 60-80% | 60-80% | 60-80% | 60-80% | Universal | Est. | Maps to A2-SUB-002. |
| A3-27 Superficial depth | HIGH (multi-pattern trigger) | 60-80% | 60-80% | 60-80% | 60-80% | Universal | Est. (Hicks 2024) | Promoted to Section A2. |
| A3-28 Hyperbolic subheadings | 0.55 to 0.7 | 25-45% | 25-45% | 35-55% | 35-55% | GPT marketing | Est. | |
| A3-29 Dramatic fragment construction | 0.45 to 0.6 | 20-40% | 20-40% | 25-45% | 25-45% | GPT | Est. | |
| A3-30 Borrowed canonical examples | 0.65 to 0.8 | 15-30% | 15-30% | 20-35% | 20-35% | Universal (training canonicals) | Est. | |
| A3-31 Scenario fingerprinting (anonymization) | 0.7 to 0.85 (verified) | varies | varies | varies | varies | Universal | Est. (four-test protocol) | |
| A3-32 Operational decisions as teaching | 0.7 to 0.85 (verified) | varies | varies | varies | varies | Universal | Est. | |
| A3-33 Saturated AI vocab cluster | 0.85 to 0.95 (cluster 3+ in 500 words) | 40-60% | 40-60% | 70-90% (academic) | 70-90% | GPT (academic highest) | Emp. (Kobak 2406.07016: Z above 3.5 across 103/135 focal words; 13.5% of 2024 biomedical abstracts) | Promote MED to HIGH. |
| A3-34 Exhausted metaphors | 0.55 to 0.7 | 35-55% | 35-55% | 40-60% | 40-60% | Claude/GPT/Gemini distinct lexicons | Est. | PROMOTE per ChatGPT review. |
| A3-35 Unprompted moral cadence | 0.55 to 0.7 | 30-50% | 30-50% | 25-45% | 25-45% | Claude (Constitutional AI) | Est. | |
| A3-36 Concierge tone | 0.55 to 0.75 | 50-70% (Claude active) | 60-80% | 15-25% (GPT post-rollback) | 50-70% | Claude | Emp. (OpenAI Apr 2025 rollback) | **WRAPPER-CLOSER dominant.** Zone differential 1.5-4x. |
| A3-37 Insider context collapse | 0.7 to 0.85 (verified vs reader briefing) | varies | varies | varies | varies | Universal (writer-frame issue) | Est. | Procedural check via synthesis-reader-briefing. |
| A3-38 Imported spec uppercase (social) | 0.7 to 0.85 (social) | 5-15% | 5-15% | 10-20% | 10-20% | Universal | Est. | Social register. |
| A3-39 Article structure in social | 0.65 to 0.8 (social) | 30-50% | 30-50% | 30-50% | 30-50% | Universal | Est. | Social register. |
| A3-40 Third-person narration of first-person experience | 0.6 to 0.75 (social) | 15-30% | 15-30% | 15-30% | 15-30% | Universal | Est. | Social register. |
| A3-41 Lack of closing engagement (social) | 0.4 to 0.55 (social) | varies | varies | varies | varies | Universal | Est. | **WRAPPER-CLOSER** (social-specific). |
| A3-42 Em-dash in social posts | 0.7 to 0.85 (threshold zero in social) | 60-80% (LinkedIn Claude) | 60-80% | 25-45% (GPT-5.1+) | 25-45% | Claude | Emp. (Plagiarism Today June 2025; DeepSeek GLTR 2.3x) | Social register. |

### A3 (refreshed): Gemini + Llama split

The A3 criteria above apply across all families; this table shows the BR values that differ meaningfully from the Claude/GPT pair.

| Pattern | BR-Gemini (body) | BR-Gemini (full) | BR-Llama (body) | BR-Llama (full) | Notes |
|---------|--------------------|---------------------|-------------------|-------------------|-------|
| A3-03 Editorial commentary | 30-50% | 30-50% | 15-30% | 15-30% | Gemini uses "It's important to note" specifically (A1-GEMINI-012). Llama uses less hedging (A1-LLAMA-015). |
| A3-06 Transition-word saturation | 40-60% | 40-60% | 15-30% | 15-30% | Llama uses fewer transitions (A1-LLAMA-016). |
| A3-09 Passive voice | 50-70% | 50-70% | 15-30% | 15-30% | Gemini-specific elevated rate (A1-GEMINI-010 formal academic register default). |
| A3-10 Uniform sentence/paragraph length | 75-90% | 75-90% | 50-70% | 50-70% | Llama varies more than closed-source frontier models. ESL caveat applies. |
| A3-11 Em-dash overuse | variable | variable | below 5% (near-zero per Gemini A1-LLAMA-001) | below 5% | Llama is the canonical em-dash absence family. |
| A3-12 Bulleted bolded lead-ins | 40-60% | 40-60% | 30-50% (keyword-style per A1-LLAMA-011) | 30-50% | Llama uses concise keyword bullets, not full-sentence elaborations. |
| A3-15 Markdown leakage | 60-85% (near-deterministic in CLI per gemini-cli #8392) | 60-85% | 5-15% (markdown underuse per A1-LLAMA-017) | 5-15% | **Gemini's strongest single-family fingerprint in non-rendering channels.** |
| A3-19 Chatbot artifacts | 5-15% | 30-50% | 5-15% | 15-30% | Llama lower agent-reflex density. |
| A3-23 Hallucinated citations | variable (Gemini drifts to vague attribution rather than fabrication; see A1-GEMINI-002) | variable | variable | variable | Llama hallucinates more at long context (above 32K tokens per A1-LLAMA-003). |
| A3-24 Vague attribution | 30-50% | 30-50% | 15-30% | 15-30% | **Gemini's signature variant** of the citation-fabrication problem: evasion rather than fabrication. |
| A3-33 Saturated vocabulary | 30-50% (uses "context"/"considerations") | 30-50% | 20-40% (lower density per A1-MISTRAL-003 sibling) | 20-40% | Family-specific focal-word allocations matter. |
| A3-36 Concierge tone | moderate | moderate-high | low | low | Llama refusal under-rotation (A1-LLAMA-006). |
| A3-42 Em-dash in social | variable | variable | below 5% | below 5% | Llama near-zero baseline applies to social register too. |

### A3 (refreshed): Grok + DeepSeek split

| Pattern | BR-Grok (body) | BR-Grok (full) | BR-DeepSeek (body) | BR-DeepSeek (full) | Notes |
|---------|-------------------|--------------------|-----------------------|-----------------------|-------|
| A3-03 Editorial commentary | low | low | low (encyclopedia tone per A1-DEEPSEEK-012) | low | Grok edgy-sarcasm register actively rejects this. |
| A3-06 Transition-word saturation | low | low | 30-50% (rigid pivot per A1-DEEPSEEK-008) | 30-50% | DeepSeek "On the other hand" / "In summary" hyperdense. |
| A3-10 Uniform sentence/paragraph length | moderate | moderate | moderate | moderate | DeepSeek different rhythm baseline (A1-DEEPSEEK-007). |
| A3-11 Em-dash overuse | low (Llama 4-level per Grok contribution) | low | low (apply GPT BR via Copyleaks 74.2% resemblance; see B3.5 cross-family contamination flag) | low | Grok lower em-dash density. |
| A3-19 Chatbot artifacts | low | 15-30% | zero standalone | 5-15% | Grok lower sycophancy; DeepSeek-R1 `<think>` leakage is a distinct signature (A1-DEEPSEEK-001). |
| A3-23 Hallucinated citations | variable | variable | variable | variable | DeepSeek confidence bias in math/code (A1-DEEPSEEK-004) inflates assertive errors. |
| A3-33 Saturated vocabulary | low | low | inherit GPT BR via Copyleaks (74.2% resemblance) | inherit GPT BR | Grok has its own colloquial-internet vocabulary; DeepSeek shares OpenAI focal-word distribution. |
| A3-36 Concierge tone | low (Grok direct positioning) | low | low (encyclopedia tone) | low | Both negative-marker families for concierge. |
| A3-42 Em-dash in social | low | low | low | low | Both inherit non-Claude baselines. |

### A3 (refreshed): Mistral + Qwen split

| Pattern | BR-Mistral (body) | BR-Mistral (full) | BR-Qwen (body) | BR-Qwen (full) | Notes |
|---------|---------------------|---------------------|-------------------|-------------------|-------|
| A3-03 Editorial commentary | low | low | moderate | moderate | Qwen formal textbook tone (A1-QWEN-011) elevates this. |
| A3-06 Transition-word saturation | low | low | 40-60% (overuse of "Moreover"/"In addition" per A1-QWEN-009) | 40-60% | Qwen-specific elevated rate. |
| A3-10 Uniform sentence/paragraph length | moderate | moderate | moderate | moderate | Both inherit general AI uniformity; Qwen reflects translated-textbook conventions. |
| A3-11 Em-dash overuse | low | low | low | low | Both families below Claude/GPT baseline. |
| A3-13 Excessive bolding | 5-15% (markdown decoration reduced per A1-MISTRAL-003) | 5-15% | 30-50% (structured bold headers per Gemini-resembling templates) | 30-50% | |
| A3-19 Chatbot artifacts | low (lower agent-reflex density per A1-MISTRAL-006) | 5-15% | moderate ("Please let me know if you need further assistance" per A1-QWEN-012) | 30-50% | Mistral negative-marker family. |
| A3-23 Hallucinated citations | variable | variable | variable | variable | |
| A3-33 Saturated vocabulary | low (per A1-MISTRAL-003 lower density) | low | low (lower idiomatic-English density per A1-QWEN-007) | low | Both are negative-marker families for saturated vocab. |
| A3-36 Concierge tone | low (direct refusal style per A1-MISTRAL-002) | low | moderate (honorific register markers) | moderate-high | |

---

### A1 (model-family fingerprints): Claude family

| Pattern | SSWP | BR-Claude (body) | BR-Claude (full) | E/Est | Zone, notes |
|---------|------|--------------------|---------------------|-------|--------------|
| A1-CLAUDE-001 "It is important to note" preamble | 0.6 to 0.75 (cluster 3+ HIGH; standalone MED) | 40-60% | 40-60% | Est. (cross-validated 7 LLMs; Kobak focal-word direction) | BODY-PERSISTENT. |
| A1-CLAUDE-002 Two-handed balanced sentence | 0.7 to 0.85 (clustered) | 70-85%; Gemini 68% unedited technical | 70-85% | Est. (Constitutional AI docs; Bhatia 2025) | BODY-PERSISTENT. |
| A1-CLAUDE-003 "You're absolutely right!" agent reflex | 0.9 to 0.99 | 25-45% agent | 30-55% multi-turn | Emp. (claude-code#3382; Sharma 2310.13548) | **WRAPPER-OPENER.** Tic rate +110% across 20 turns. |
| A1-CLAUDE-004 Em-dash density | 0.7 to 0.85 (above 5/500 words) | 80-95% | 80-95% | Emp. (Plagiarism Today June 2025; DeepSeek GLTR 2.3x; Liang 2304.02819) | BODY-PERSISTENT. Single strongest token-level fingerprint 2025. Cross-family: pre-GPT-5.1 high, GPT-5.1+ low, Llama near-zero. |
| A1-CLAUDE-005 Bulleted bolded lead-ins | 0.5 to 0.65 standalone; 0.75+ clustered | 50-70% | 50-70% | Est. (Walsh CHR 2024) | BODY-PERSISTENT. |
| A1-CLAUDE-006 Refusal-shaped close with safety hedge | 0.6 to 0.75 advisory; 0.4 to 0.55 general | 40-50% general; 70-90% advisory | 50-70% general; 80-95% advisory | Est. (Bai 2022 Constitutional AI) | **WRAPPER-CLOSER** (advisory contexts). |
| A1-CLAUDE-007 Section-ending recap sentence | 0.4 to 0.6 standalone; 0.7 to 0.85 clustered | 60-80% multi-section | 60-80% | Est. | BODY-PERSISTENT. |
| A1-CLAUDE-008 Uniform paragraph length (low burstiness) | 0.4 to 0.6 standalone; HIGH clustered | 85-95% | 85-95% | Emp. (Liang 2304.02819; GPTZero burstiness below 0.30 + perplexity below 40) | BODY-PERSISTENT. **NEGATIVE MARKER without register-specific corroboration. See B3.4.** |
| A1-CLAUDE-009 "I appreciate your" / "Thank you for" | 0.4 to 0.55; 0.7+ clustered | 30-50% multi-turn; DeepSeek 80%+ for "I'm happy to help" variant | 50-70% | Est. | **WRAPPER-OPENER.** |
| A1-CLAUDE-010 "Let me explain" / "Let me walk you through" | 0.4 to 0.55 | 35-55% pedagogical | 40-60% | Est. | **WRAPPER-OPENER / HYBRID.** |
| A1-CLAUDE-011 "I hope this helps" closer | 0.4 to 0.55 | 5-15% | 60-80% multi-turn | Est. | **WRAPPER-CLOSER.** Zone differential 6-12x. |
| A1-CLAUDE-012 Reasoning-trace "Wait" / "Actually" leakage | 0.7 to 0.85 thinking-mode; 0.3 to 0.45 non-thinking | 15-30% extended-thinking | 15-30% | Emp. (verified-arxiv:2501.12948 DeepSeek-R1 Nature 2025) | MID-BODY-INSERT. Active; new as of 2025. |
| A1-CLAUDE-013 Concierge tone closer | 0.55 to 0.7 | 5-15% | 50-70% | Est. | **WRAPPER-CLOSER.** |
| A1-CLAUDE-014 to A1-CLAUDE-028 ("That said,", "However," paragraph pivots, apologetic refusals, longwinded contextualization, "nuanced" overuse, colon overextension, prescriptive moralizer, vestigial "Certainly" opener, etc.) | 0.4 to 0.6 each | 25-50% characteristic; cumulative when clustered | 25-50% | Est. | Mix BODY-PERSISTENT and WRAPPER-OPENER; per-entry detail in model-family-fingerprints.md. |

### A1: GPT family

| Pattern | SSWP | BR-GPT (body) | BR-GPT (full) | E/Est | Zone, notes |
|---------|------|------------------|------------------|-------|--------------|
| A1-GPT-001 "Delve" and saturated AI vocab cluster | 0.85 to 0.95 (cluster 3+) | 70-90% academic | 70-90% | Emp. (Kobak 2406.07016: 10% of 2024 PubMed use "delve" vs ~0.5% 2020; Juzek/Ward COLING 2025) | BODY-PERSISTENT. Promote MED to HIGH. |
| A1-GPT-002 Sycophantic opener ("Great question!", "Certainly!") | 0.85 to 0.95 | 30-50% pre-Apr 2025 rollback; 15-25% post | 70-90% GPT-4o | Emp. (OpenAI Apr 2025 rollback; Sharma 2310.13548; Gemini 312/1000 turns for GPT-5.4) | **WRAPPER-OPENER.** Zone differential 4-6x. **Largest BR-full vs BR-body split.** |
| A1-GPT-003 Section-ending summary sentence | 0.45 to 0.6; 0.7 to 0.85 clustered | 70-85% (GPT-4o) | 70-85% | Est. | BODY-PERSISTENT (mid-document). |
| A1-GPT-004 "It's not just X, it's Y" | 0.55 to 0.7 marketing; 0.4 to 0.55 analytical | 40-60% marketing | 40-60% | Est. (Pennycook BSRS pseudo-profundity) | BODY-PERSISTENT. Promote MED to HIGH. |
| A1-GPT-005 "While X, it's also worth noting Y" balanced framing | 0.45 to 0.6 | 50-70% long analytical | 50-70% | Est. | BODY-PERSISTENT. |
| A1-GPT-006 "Here's the thing" colloquial intensifier (HISTORICAL) | 0.7 to 0.85 for 2023; LOW current | high 2023 GPT-3.5/4; near-zero 2026 | high 2023; near-zero | Est. | BODY-PERSISTENT. **Historical (2023-2024 forensic).** |
| A1-GPT-007 "As an AI language model" preamble (HISTORICAL) | 0.95 to 0.99 (when present); LOW current | 15-25% 2022-2024; near-zero 2026 | 15-25% / near-zero | Emp. | **WRAPPER-OPENER.** **Historical/Deprecated.** Residual in older fine-tunes. |
| A1-GPT-008 Numbered-list scaffolding | 0.55 to 0.7 clustered | 75-90% GPT-4o decision-support; Gemini 70% in instructional for tripartite | 75-90% | Est. (Gemini 60% confidence tripartite-list) | BODY-PERSISTENT. |
| A1-GPT-009 "In conclusion" / "To wrap up" closer | 0.4 to 0.55 | 60-80% multi-paragraph | 60-80% | Est. | BODY-PERSISTENT (closing). |
| A1-GPT-010 "It's important to remember" / "Keep in mind" | 0.45 to 0.6 | 35-55% long analytical | 35-55% | Est. | BODY-PERSISTENT (mid-response insert). |
| A1-GPT-011 Hallucinated citations and DOIs | 0.95 to 0.99 (verifiable) | 18-29% GPT-4; 30-55% GPT-3.5; 20% with 56% errors GPT-4o; Bard 91% historic | 18-29% | Emp. (Walters Wilder Sci Rep 2023; Chelli JMIR 2024; Buchanan Sage 2024; Stanford RegLab; Damien Charlotin database 1,455+ sanctioned cases) | BODY-PERSISTENT. PROMOTE. |
| A1-GPT-012 Markdown in plain-text contexts | 0.6 to 0.85 (Gemini near-deterministic; GPT MED) | 40-60% no plain-text prompt | 40-60% | Emp. (gemini-cli #8392; 9to5Google Sep 2025) | BODY-PERSISTENT. |
| A1-GPT-013 o-series conclusion recapitulation | 0.7 to 0.85 (family-unique) | MED technical; LOW creative | MED technical | Emp. (OpenAI o1 launch; HN o1 thread; generative-ai-newsroom) | BODY-PERSISTENT (closing). |
| A1-GPT-014 to A1-GPT-021 (uncertainty framing, caveat paragraph, transition cascade, "I'd be happy to" service register, artificial enthusiasm, enthusiastic sign-offs, "game-changer" buzzwords, knowledge-cutoff disclaimer) | 0.45 to 0.7 each | varies 15-70% per pattern | varies | Mixed Emp./Est. | Mix BODY-PERSISTENT, WRAPPER-OPENER (sycophancy variants), WRAPPER-CLOSER (sign-offs); detail in model-family-fingerprints.md. |

### A1: Gemini family

| Pattern | SSWP | BR-Gemini (body) | BR-Gemini (full) | E/Est | Zone, notes |
|---------|------|---------------------|---------------------|-------|--------------|
| A1-GEMINI-001 Plain-text markdown leakage | 0.8 to 0.95 (non-rendering) | near-deterministic | near-deterministic | Emp. (gemini-cli #8392; 9to5Google Sep 2025 update partial) | BODY-PERSISTENT. **Gemini signature single-family fingerprint.** |
| A1-GEMINI-002 "Studies show" without identifiers | 0.6 to 0.75 | 30-50% analytical | 30-50% | Est. (cross-validated 5 LLMs) | BODY-PERSISTENT. |
| A1-GEMINI-003 "Cool and unique" register tilt | 0.5 to 0.65; 0.75+ clustered | 30-50% casual-register | 30-50% | Est. | BODY-PERSISTENT (consumer register). |
| A1-GEMINI-004 "Let's dive in" / "Without further ado" opener | 0.45 to 0.6 | 20-40% substantive prompts | 30-50% | Est. | **WRAPPER-OPENER.** |
| A1-GEMINI-005 Bulleted-everything default | 0.45 to 0.6 | very high | very high | Est. | BODY-PERSISTENT. Shared with GPT-4o. |
| A1-GEMINI-006 Exhaustive survey marker ("comprehensive," "multifaceted," "holistic," "numerous") | 0.5 to 0.65 (Gemini 75% conf) | Gemini 3.1 Pro VTI 0.590 (Gemini-sourced, unverified) | 0.590 VTI | Est. | BODY-PERSISTENT. |
| A1-GEMINI-007 Encrypted thought leakage (Gemini-unique) | 1.0 (definitive when present) | ~4% custom API wrappers failing JSON parse | ~4% | Est. (Gemini single-sourced; analog to DeepSeek-R1 `<think>`) | MID-BODY-INSERT. **Single-LLM-sourced; flagged.** |
| A1-GEMINI-008 Numbered deep-dive list (10-15 items) | 0.5 to 0.65 | HIGH (mean 912.8 chars vs Claude 710.8) | HIGH | Emp. (PLoS One stylometry 2025) | BODY-PERSISTENT. |
| A1-GEMINI-009 "Absolutely" opener with follow-on qualification | 0.45 to 0.6 | HIGH Gemini; MED others | HIGH | Est. (LobeHub marketplace signal list) | **WRAPPER-OPENER.** |
| A1-GEMINI-010 Formal academic register default | 0.5 to 0.65 | HIGH | HIGH | Est. (PLoS One stylometry 2025) | BODY-PERSISTENT. Maps to A3-09. |
| A1-GEMINI-011 to A1-GEMINI-027 (parenthetical cascade, "key takeaways" appended, header-dense, three-options offer, code-comment style, emoji in explanations, etc.) | 0.4 to 0.6 each | varies | varies | Est. | Mix BODY-PERSISTENT, MID-BODY-INSERT, WRAPPER-CLOSER ("key takeaways"). |

### A1: Llama family

| Pattern | SSWP | BR-Llama (body) | BR-Llama (full) | E/Est | Zone, notes |
|---------|------|-------------------|-------------------|-------|--------------|
| A1-LLAMA-001 Em-dash near-zero (NEG marker) + abrupt declarative | 0.7 to 0.85 NEG; HIGH for abrupt declarative | near-zero em-dash (0.0/1000 words); HIGH abrupt declarative | near-zero / HIGH | Emp. (PLoS One Zaitsu 2025: 86.2% human accuracy, most human-detectable family) | BODY-PERSISTENT. Negative-marker em-dash; positive-marker abrupt declarative. |
| A1-LLAMA-002 Sterile infrastructure tone | 0.5 to 0.65 | HIGH (Gemini-sourced 37.5x distinctiveness ratio, unverified) | HIGH | Est. | BODY-PERSISTENT. |
| A1-LLAMA-003 Fabrication at long context (above 32K tokens) | 0.7 to 0.85 (long-context) | substantially elevated above 32K | substantially elevated | Emp. (RIKER benchmark) | BODY-PERSISTENT (context-conditional). |
| A1-LLAMA-004 Direct-question response without preamble | 0.5 to 0.65 (NEG marker) | HIGH | HIGH | Est. | **WRAPPER-OPENER absence.** |
| A1-LLAMA-005 Code-comment fluency | 0.3 to 0.45 | varies | varies | Est. | BODY-PERSISTENT (genre-specific). |
| A1-LLAMA-006 Refusal under-rotation | 0.5 to 0.65 | HIGH (vs Claude/GPT) | HIGH | Est. | BODY-PERSISTENT (safety register). |
| A1-LLAMA-007 Wikipedia-paste artifact | 0.5 to 0.65 | MED (Wikipedia-style content) | MED | Est. (WikiProject AI Cleanup) | BODY-PERSISTENT. |
| A1-LLAMA-008 to A1-LLAMA-017 (first-person opinion, shorter direct sentences, "I'm just an AI so take this with a grain of salt", flat paragraph, reduced hedging, limited transitional vocab, markdown underuse) | 0.4 to 0.6 each | varies | varies | Est. | Mix BODY-PERSISTENT and HYBRID. |

### A1: Grok family

| Pattern | SSWP | BR-Grok (body) | BR-Grok (full) | E/Est | Zone, notes |
|---------|------|-------------------|-------------------|-------|--------------|
| A1-GROK-001 Colloquial internet-native register + edgy sarcasm | 0.5 to 0.65 | family-distinctive | family-distinctive | Est. (Copyleaks 100% no-agreement classification; practitioner observation) | BODY-PERSISTENT. |
| A1-GROK-002 "Based on X" framing for opinion-seeking | 0.4 to 0.55 | moderate | moderate | Est. | BODY-PERSISTENT. |
| A1-GROK-003 Lower hedging density | 0.5 to 0.65 (NEG marker) | low | low | Est. | BODY-PERSISTENT. |
| A1-GROK-004 Twitter-style structural defaults | 0.4 to 0.55 | moderate | moderate | Est. | BODY-PERSISTENT. |
| A1-GROK-005 Real-time data references | 0.45 to 0.6 | varies | varies | Est. | BODY-PERSISTENT. |
| A1-GROK-006 Pop-culture allusions | 0.4 to 0.55 | moderate | moderate | Est. | BODY-PERSISTENT. |
| A1-GROK-007 Skepticism-of-establishment positioning | 0.45 to 0.6 | family-distinctive | family-distinctive | Est. | BODY-PERSISTENT. |
| A1-GROK-008 to A1-GROK-013 ("The thing about X is", "TL;DR" summary, "I'm Grok, an AI by xAI", profanity, rapid-fire bullets, "Alright, let's break this down") | 0.4 to 0.6 each | varies | varies | Est. | Mix BODY-PERSISTENT, WRAPPER-OPENER, WRAPPER-CLOSER. |

### A1: DeepSeek family

| Pattern | SSWP | BR-DeepSeek (body) | BR-DeepSeek (full) | E/Est | Zone, notes |
|---------|------|-----------------------|-----------------------|-------|--------------|
| A1-DEEPSEEK-001 `<think>` tag leakage (R1-specific) | 0.95 to 0.99 | LOW (API misconfiguration only) | LOW | Emp. (verified-arxiv:2501.12948 Nature 2025; Opper AI 2025; Vellum AI 2025) | MID-BODY-INSERT. FP risk: zero. |
| A1-DEEPSEEK-002 Language-mixing under reasoning load | 0.9 to 0.99 (Chinese characters unexpectedly) | LOW | LOW | Est. (arxiv 2507.15849 bilingual reasoning; cited Claude exec) | MID-BODY-INSERT. |
| A1-DEEPSEEK-003 Lower English-prose polish | 0.4 to 0.55 | subtle but consistent | subtle but consistent | Est. | BODY-PERSISTENT. |
| A1-DEEPSEEK-004 Mathematical confidence bias | 0.4 to 0.55 | varies | varies | Est. | BODY-PERSISTENT (technical register). |
| A1-DEEPSEEK-005 Step-numbering in reasoning | 0.4 to 0.55 | HIGH | HIGH | Est. | BODY-PERSISTENT. |
| A1-DEEPSEEK-006 Lower English idiom density | 0.4 to 0.55 (NEG marker) | family-distinctive | family-distinctive | Est. | BODY-PERSISTENT. |
| A1-DEEPSEEK-007 Different sentence-rhythm baseline | 0.25 to 0.4 standalone | family-distinctive | family-distinctive | Est. | BODY-PERSISTENT. |
| A1-DEEPSEEK-008 Rigid pivot ("On the other hand," "In summary,") | 0.45 to 0.6 (Gemini 65% conf) | 62% multi-paragraph analytical | 62% | Est. | BODY-PERSISTENT. |
| A1-DEEPSEEK-009 to A1-DEEPSEEK-016 ("Based on the provided information," LaTeX in non-technical, "I understand your concern," encyclopedia tone, "To sum up," plain numbered points, "You are absolutely correct," OpenAI stylometric resemblance) | 0.4 to 0.6 each; A1-DEEPSEEK-016 inherits GPT BR via Copyleaks 74.2% resemblance | varies | varies | Emp. (Copyleaks 2025; arxiv 2503.01659 cross-family precision 0.9988) | Mix BODY-PERSISTENT, MID-BODY-INSERT, WRAPPER-OPENER. **Cross-family contamination flag, B3.5.** |

### A1: Mistral family

| Pattern | SSWP | BR-Mistral (body) | BR-Mistral (full) | E/Est | Zone, notes |
|---------|------|---------------------|---------------------|-------|--------------|
| A1-MISTRAL-001 French-influence syntax | 0.7 to 0.85 (HIGH when present); LOW BR | low (HIGH when present) | low | Est. (Copyleaks 26% OpenAI, 8.8% Llama, 65% no-agreement) | BODY-PERSISTENT. |
| A1-MISTRAL-002 Direct refusal style | 0.4 to 0.55 | family-distinctive | family-distinctive | Est. | BODY-PERSISTENT (safety register). |
| A1-MISTRAL-003 Lower saturated-vocabulary density | 0.45 to 0.6 (NEG marker) | low | low | Est. | BODY-PERSISTENT. |
| A1-MISTRAL-004 Different default formatting | 0.25 to 0.4 standalone | family-distinctive | family-distinctive | Est. | BODY-PERSISTENT. |
| A1-MISTRAL-005 Open-source-aware register | 0.3 to 0.45 (genre-specific) | varies | varies | Est. | BODY-PERSISTENT. |
| A1-MISTRAL-006 Lower agent-reflex density | 0.45 to 0.6 (NEG marker) | low | low | Est. | **WRAPPER-OPENER absence.** |
| A1-MISTRAL-007 to A1-MISTRAL-011 (concise default, direct completion, technical register dominance, "I'm not sure but I'll try to help", minimal bullet-point use) | 0.4 to 0.6 each | varies | varies | Est. | Mix BODY-PERSISTENT and HYBRID. |

### A1: Qwen family

| Pattern | SSWP | BR-Qwen (body) | BR-Qwen (full) | E/Est | Zone, notes |
|---------|------|-------------------|-------------------|-------|--------------|
| A1-QWEN-001 CJK punctuation slips (Unicode-detectable) | 0.95 to 0.99 | LOW BR | LOW | Emp. (Unicode-character search; cross-validated) | MID-BODY-INSERT. FP risk: near-zero. |
| A1-QWEN-002 Chinese cultural refs / idiom translations | 0.45 to 0.6 | LOW BR | LOW | Est. | BODY-PERSISTENT. |
| A1-QWEN-003 Heavier hedging on China-political topics | 0.7 to 0.85 (topic-conditional) | HIGH for China-political; LOW general | HIGH topic-specific | Est. | BODY-PERSISTENT (topic-conditional). |
| A1-QWEN-004 Math-step formatting differences | 0.25 to 0.4 (genre-specific) | varies | varies | Est. | BODY-PERSISTENT (genre-specific). |
| A1-QWEN-005 Specific phrasings translated from Chinese | 0.45 to 0.6 | LOW BR | LOW | Est. | BODY-PERSISTENT. |
| A1-QWEN-006 Different agentic-reflex patterns | 0.4 to 0.55 | family-distinctive | family-distinctive | Est. | **WRAPPER-OPENER (Qwen variant).** |
| A1-QWEN-007 Lower idiomatic-English density | 0.25 to 0.4 standalone | family-distinctive | family-distinctive | Est. | BODY-PERSISTENT. |
| A1-QWEN-008 to A1-QWEN-012 ("Below is a detailed explanation," "Moreover"/"In addition" overuse 40-60%, "I hope this clarifies your question," formal textbook tone, "Please let me know if you need further assistance") | 0.4 to 0.55 each | varies | varies | Est. | Mix BODY-PERSISTENT, WRAPPER-OPENER, WRAPPER-CLOSER. |

---

### A2 (substance and depth)

Zone for all A2 rows is BODY-PERSISTENT. Substance signals are upstream of family attribution: they describe the failure mode of the writing, not the family fingerprint that produced it.

| Pattern | SSWP | BR-Claude | BR-GPT | BR-Gemini | Other families | E/Est |
|---------|------|------------|---------|------------|-----------------|-------|
| A2-SUB-001 The deletion test | 0.85 to 0.95 (sustained) | HIGH (73% paragraphs contribute zero load-bearing claims; Claude exp. 1000-output sample, flagged unverified) | HIGH (62% paragraphs failed per DeepSeek sample) | ~40% unedited business prose | All HIGH | Emp. (Hicks 2024; Frankfurt 2005; Pennycook 2015 BSRS; Shaib 2509.19163; Sourati 2025) |
| A2-SUB-002 The specificity test (any-topic) | 0.85 to 0.95 | HIGH (business copy 78%+) | HIGH (academic 70-90%) | HIGH (95% conf per Gemini) | Universal HIGH | Emp. (PR Daily 2026 AI comparison drill; Shaib 2509.19163) |
| A2-SUB-003 Load-bearing claim count (density below 0.3/sentence) | 0.7 to 0.9 | HIGH (73% zero) | HIGH (mean density 0.18 per DeepSeek) | HIGH (90% conf) | Universal HIGH | Emp. (DeepSeek below 0.2 = AI-typical; ACM 2025) |
| A2-SUB-004 Novelty signal | 0.5 to 0.65 (domain expertise required) | MED (below 15% novelty per DeepSeek) | MED | MED | Universal MED | Est. (Nieman Lab 2025) |
| A2-SUB-005 Insight-to-word ratio | 0.7 to 0.85 (sustained low) | HIGH (0 to 1 per 100 words in slop) | HIGH (Claude/GPT verbose per DeepSeek) | HIGH | Llama slightly better | Emp. (Hicks 2024; Shaib 2509.19163; DeepSeek below 0.05 insights/100 words suspect) |
| A2-SUB-006 Any-company test (A2-SUB-002 business specialization) | 0.85 to 0.95 | HIGH | HIGH | HIGH | Universal HIGH | Emp. (PR Daily 2026) |
| A2-SUB-007 Hedging as substance evasion | 0.7 to 0.85 | HIGH | HIGH | MED | Llama LOW (per A1-LLAMA-015) | Est. |
| A2-SUB-008 Survey-without-claim (Gemini 88% SSWP) | 0.85 to 0.95 | HIGH (Claude 4.7 highest) | MED | MED | All families | Est. (Gemini) |
| A2-SUB-009 Generic insight | 0.7 to 0.85 | VERY HIGH | VERY HIGH | VERY HIGH | Universal VERY HIGH | Est. |
| A2-SUB-010 Both-sides-without-position | 0.7 to 0.85 | HIGH | HIGH | MED | Llama LOW | Est. |
| A2-SUB-011 Pseudo-profundity (Gemini 90% SSWP; ~40% BR) | 0.85 to 0.95 | HIGH | HIGH (GPT-5.4 high) | HIGH | Llama LOW | Emp. (Pennycook 2015 BSRS) |
| A2-SUB-012 Conclusion-shaped paragraphs that do not conclude | 0.7 to 0.85 | HIGH | HIGH | MED | All families | Est. |
| A2-SUB-013 Specificity Void (Gemini 95% SSWP; ~55% BR) | 0.9 to 0.99 | HIGH | HIGH | HIGH | Universal HIGH zero-shot | Emp. (Gemini-sourced; cross-validates A2-SUB-002 family) |
| A2-SUB-014 Evidence displacement | 0.55 to 0.7 | MED-HIGH | MED-HIGH | MED-HIGH | Universal | Est. (ChatGPT; sibling A3-NEW-027) |
| A2-SUB-015 "So What?" test | 0.6 to 0.75 | MED-HIGH | MED-HIGH | MED-HIGH | Universal | Est. (DeepSeek) |
| A2-SUB-016 Evidence-to-claim ratio | 0.55 to 0.7 | MED | MED | MED | Universal | Est. (DeepSeek) |
| A2-SUB-017 Specificity score (A2-SUB-002 quantitative variant) | 0.7 to 0.85 | MED-HIGH | MED-HIGH | MED-HIGH | Universal | Est. (DeepSeek) |

---

### A3-NEW (net-new criteria independent of A1 and A2)

| Pattern | SSWP | BR (general) | Strongest family | E/Est | Zone |
|---------|------|---------------|-------------------|-------|------|
| A3-NEW-001 Reasoning-trace token leakage | HIGH thinking; LOW non-thinking | MED extended-thinking (15-30%) | DeepSeek-R1, Claude thinking, o-series | Emp. (2501.12948) | MID-BODY-INSERT |
| A3-NEW-002 Sycophancy drift across turns | 0.5 to 0.65 | tic rate +110% across 20 turns | All RLHF-tuned | Emp. (Sharma 2310.13548) | **HYBRID** (wrapper-amplified across turns) |
| A3-NEW-003 Partial-refusal stems | 0.5 to 0.65 | MED | Claude; GPT secondary | Est. | BODY-PERSISTENT |
| A3-NEW-004 En-dash overuse as em-dash replacement (emerging) | 0.45 to 0.6 | emerging | GPT-5.1+ primarily | Est. | BODY-PERSISTENT. Active (emerging 2025-2026). |
| A3-NEW-005 Orphaned demonstratives | 0.4 to 0.55 | MED | All families | Est. | BODY-PERSISTENT |
| A3-NEW-006 "Human-in-the-loop" roleplay residue | 0.5 to 0.65 | MED | All families | Est. | BODY-PERSISTENT |
| A3-NEW-007 Over-apologizing in refusal | 0.45 to 0.6 | MED | Claude (xref A1-CLAUDE-016) | Est. | BODY-PERSISTENT |
| A3-NEW-008 Instruction-following over-adherence | 0.4 to 0.55 | MED (genre-specific) | All families | Est. | BODY-PERSISTENT |
| A3-NEW-009 Acronym saturation | 0.3 to 0.45 (genre-specific) | varies | All families | Est. | BODY-PERSISTENT (genre-specific) |
| A3-NEW-010 System-prompt artifact bleed | 0.85 to 0.99 (rare, definitive) | LOW BR | All families | Est. | **WRAPPER-OPENER** |
| A3-NEW-011 Date inconsistency | 0.5 to 0.65 | varies | All families | Est. | BODY-PERSISTENT |
| A3-NEW-012 Version-specific personality slip | 0.5 to 0.65 | varies | All families | Est. | BODY-PERSISTENT |
| A3-NEW-013 Refusal-to-acknowledge-uncertainty | 0.5 to 0.65 | varies | All families | Est. | BODY-PERSISTENT. Xref bucket C. |
| A3-NEW-014 Unwarranted optimism/pessimism | 0.7 to 0.85 | MED; higher in persuasive prompts | All families | Est. (O'Neil 2016; Zuboff 2019) | BODY-PERSISTENT |
| A3-NEW-015 Over-reliance on analogies and metaphors | 0.5 to 0.65 | MED | Claude and Gemini | Est. (Lakoff/Johnson 1980; Gentner/Markman 1997) | BODY-PERSISTENT |
| A3-NEW-016 Uncritical acceptance of prompt framing | 0.7 to 0.85 | varies | All families | Est. (Bender 2021; Weidinger 2021) | BODY-PERSISTENT |
| A3-NEW-017 Over-generalization from limited data | 0.7 to 0.85 | varies | All families | Est. (Kahneman 2011; Gigerenzer 2007) | BODY-PERSISTENT |
| A3-NEW-018 Unnecessary historical context ("From the dawn of time...") | 0.7 to 0.85 | HIGH intros (Gemini observed 35% in zero-shot essay prompts) | GPT and Claude | Emp. (Gemini-sourced 35%) | BODY-PERSISTENT (opening) |
| A3-NEW-019 Unnatural/stilted phrasing | 0.7 to 0.85 | varies | All families | Est. (Pinker 2014; Strunk/White 2000) | BODY-PERSISTENT |
| A3-NEW-020 Over-reliance on abstract nouns (nominalization) | 0.7 to 0.85 | maps to A3-09 | All families | Est. (Pinker 2014) | BODY-PERSISTENT |
| A3-NEW-021 Redundant modifiers / adverbial overkill | 0.7 to 0.85 | varies | All families | Est. (Pinker 2014) | BODY-PERSISTENT |
| A3-NEW-022 "Journey" metaphor overuse | 0.7 to 0.85 | HIGH business/personal-development | All families | Est. (Lakoff/Johnson 1980) | BODY-PERSISTENT |
| A3-NEW-023 Uncritical "synergy" and "holistic" use | 0.7 to 0.85 | HIGH corporate prose | All families | Est. (Pinker 2014) | BODY-PERSISTENT |
| A3-NEW-024 Retrieval-citation mismatch | 0.55 to 0.75 | growing | All families with AI search | Est. (ChatGPT; xref bucket C URL-rot) | BODY-PERSISTENT |
| A3-NEW-025 Process-theater transparency | 0.45 to 0.6 | MED | All families | Est. (ChatGPT) | BODY-PERSISTENT |
| A3-NEW-026 Search-answer wrapper voice | 0.45 to 0.6 | MED | Families with search products | Est. (ChatGPT) | **HYBRID** (search-product structural shape) |
| A3-NEW-027 Source-theater abundance | 0.45 to 0.6 | MED | All families | Est. (ChatGPT) | BODY-PERSISTENT. Sibling A2-SUB-014. |
| A3-NEW-028 Calibration mismatch | 0.45 to 0.6 | MED | All families | Est. (ChatGPT) | BODY-PERSISTENT |
| A3-NEW-029 Synthetic-source contamination | 0.45 to 0.6 | growing | All families | Est. (ChatGPT) | BODY-PERSISTENT. Rapidly growing. |
| A3-NEW-030 Over-consistent paragraph rhythm across genres | 0.45 to 0.6 | MED | All families | Est. (Grok) | BODY-PERSISTENT |
| A3-NEW-031 Safety-register intrusions in non-safety contexts | 0.45 to 0.6 | MED | Claude (xref A1-CLAUDE-006) | Est. (Grok) | BODY-PERSISTENT |
| A3-NEW-032 Cross-sentence lexical echoing | 0.45 to 0.6 | MED | All families | Est. (Grok) | BODY-PERSISTENT |
| A3-NEW-033 Generic authority laundering | 0.45 to 0.6 | MED | All families (sibling A3-24, A1-GEMINI-002) | Est. (Grok) | BODY-PERSISTENT |
| A3-NEW-034 Reasoning-trace leakage in final output (distinct from A3-NEW-001) | 0.55 to 0.75 | MED-HIGH | Reasoning-trained families | Est. (Grok) | MID-BODY-INSERT |

---

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
