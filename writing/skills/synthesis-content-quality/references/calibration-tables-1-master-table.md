# Calibration Tables, part 1 of 2

Part 1 of the file split from [calibration-tables.md](calibration-tables.md), which keeps the opening sections and lists every part. The text below is unchanged.

Contents:
- B3.2 Master calibration table: A3 (refreshed v3.1.0 criteria): Claude + GPT split; A3 (refreshed): Gemini + Llama split; A3 (refreshed): Grok + DeepSeek split; A3 (refreshed): Mistral + Qwen split; A1 (model-family fingerprints): Claude family; A1: GPT family; A1: Gemini family; A1: Llama family; A1: Grok family; A1: DeepSeek family; A1: Mistral family; A1: Qwen family; A2 (substance and depth); A3-NEW (net-new criteria independent of A1 and A2)

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
