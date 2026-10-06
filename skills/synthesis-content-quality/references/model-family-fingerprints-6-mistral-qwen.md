# Model-Family Fingerprints (A1), part 6 of 6

Part 6 of the file split from [model-family-fingerprints.md](model-family-fingerprints.md), which keeps the opening sections and lists every part. The text below is unchanged.

Contents:
- A1.7 Mistral / Mixtral family (A1-MISTRAL-001 to A1-MISTRAL-009, 9 entries)
- A1.8 Qwen / Alibaba family (A1-QWEN-001 to A1-QWEN-010, 10 entries)
- Summary and Cross-References: Related references files; Detection mode selection (zone-conditional); Em-dash audit

## A1.7 Mistral / Mixtral family

Models in scope: Mistral Large 1 and 2, Mixtral 8x7B, and current Mistral frontier (Le Chat, Codestral, and follow-ons). Mistral 7B, Mixtral 8x7B early, and Mistral Large 1 historical entries live in [historical-patterns.md](historical-patterns.md). Mistral output was classified by Copyleaks as 26 percent OpenAI and 8.8 percent Llama with 65 percent "no-agreement," indicating a partially distinct stylistic identity with some overlap with both families per `[perplexity]`. The Manus AI catalog characterizes Mistral as "Professional, pragmatic, and solution-oriented." The independent similarity work cited by ChatGPT finds several Mistral models clustering very tightly, making the family useful for fingerprint cataloguing even though it is less stylistically distinct than Claude or GPT.

### A1-MISTRAL-001: French-influence syntax

- **ID.** A1-MISTRAL-001
- **Name.** French-influence syntax
- **Description.** Mistral family occasionally produces English prose with syntax patterns subtly influenced by French (e.g., adjective placement, relative-clause structure). Reflects training corpus. Cross-validates with `[perplexity]`'s "A1-MISTRAL-005: Multilingual phrase bleedthrough" (occasionally produces French cognates or European-English constructions in English output) and `[deepseek]`'s "A1-MISTRAL-004: Occasional French Code-Switch" ("Bonjour" or French punctuation spacing).
- **Concrete examples.**
  1. "The solution evident and reliable handles the workload." (adjective placement reflecting French syntax)
  2. "The team in charge of the migration the strategy outlined here." (relative-clause structure)
  3. French punctuation spacing leakage (e.g., space before colon or semicolon, French convention).
- **Location and register.** Body paragraphs in technical and analytical responses.
- **Model attribution.** Mistral family (high confidence as French-influence marker).
- **Time evolution.** Consistent across versions; reflects training corpus.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`.
- **Signal strength.** LOW standalone (HIGH when French code-switch tokens appear, but base rate of those is very low).
- **Base rate (per-family).** Low overall; concentrated in specific contexts where the bilingual training surfaces.
- **Causal hypothesis (ranked).** Multilingual training corpus effects; Mistral's French-corpus emphasis.
- **Detection difficulty.** Medium (requires careful reading for subtle syntax differences).
- **False positive risk.** Moderate (French-influenced ESL human writers exhibit similar patterns).
- **Fix or remediation.** Standard copy-edit pass; reorder words to natural English syntax.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-MISTRAL-002: More direct refusal style

- **ID.** A1-MISTRAL-002
- **Name.** More direct refusal style
- **Description.** Mistral refusals tend to be more direct ("I cannot help with that") than Claude/GPT's softer hedges.
- **Concrete examples.**
  1. "I cannot help with that request."
  2. "I am not able to provide that information."
  3. "That falls outside the scope of what I can answer."
- **Location and register.** Refusal turns.
- **Model attribution.** Mistral family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`.
- **Signal strength.** MEDIUM as a family marker.
- **Base rate (per-family).** High in refusal turns.
- **Causal hypothesis (ranked).** RLHF training favoring direct refusals over softer hedges.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate (skilled writers also refuse directly).
- **Fix or remediation.** N/A as a stylistic baseline.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER (refusal turns are typically the entire response).

### A1-MISTRAL-003: Lower saturated-vocabulary density

- **ID.** A1-MISTRAL-003
- **Name.** Lower saturated-vocabulary density
- **Description.** Mistral produces fewer "delve"-cluster focal words than GPT. Negative-marker pattern.
- **Concrete examples.**
  1. Mistral uses "examine" or "study" where GPT would use "delve."
  2. Mistral uses "use" or "apply" where GPT would use "leverage."
  3. Mistral uses "complex" or "complicated" where GPT would use "intricate."
- **Location and register.** Body paragraphs across registers.
- **Model attribution.** Mistral family (high confidence as a negative marker).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`.
- **Signal strength.** MEDIUM as a negative marker.
- **Base rate (per-family).** Substantially lower saturated-vocabulary density than GPT or Claude.
- **Causal hypothesis (ranked).** Training corpus and RLHF that does not emphasize academic-register focal vocabulary at GPT rates.
- **Detection difficulty.** Medium (requires comparison against expected density).
- **False positive risk.** Moderate (skilled writers also avoid focal vocabulary).
- **Fix or remediation.** N/A as a stylistic baseline.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-MISTRAL-004: Different default formatting

- **ID.** A1-MISTRAL-004
- **Name.** Different default formatting
- **Description.** Mistral default formatting (bullet density, paragraph length) differs from Claude/GPT defaults, providing a structural fingerprint. Cross-validates with `[perplexity]`'s "A1-MISTRAL-003: Reduced markdown decoration" (Mistral applies less bold, bullet, and header decoration than GPT-4o).
- **Concrete examples.**
  1. Mistral default responses contain fewer bullet points than GPT-4o default responses to the same prompt.
  2. Mistral paragraphs tend to be longer than Claude's 3-to-5-sentence default.
  3. Mistral uses less bold formatting than GPT-4o's "comprehensive structure header cascade."
- **Location and register.** Body of responses across registers.
- **Model attribution.** Mistral family (high confidence as a negative marker for heavy formatting).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** LOW standalone.
- **Base rate (per-family).** High distinctiveness in formatting choices.
- **Causal hypothesis (ranked).** Training corpus and RLHF choices that under-prioritize structured formatting.
- **Detection difficulty.** Medium (requires aggregate analysis).
- **False positive risk.** High (many human writers also use minimal formatting).
- **Fix or remediation.** N/A as a stylistic baseline.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-MISTRAL-005: Open-source-aware register

- **ID.** A1-MISTRAL-005
- **Name.** Open-source-aware register
- **Description.** Mistral, being European-open-source-aligned, sometimes references open-source culture and EU regulatory framings more naturally than competitors. Cross-validates with `[perplexity]`'s "A1-MISTRAL-002: European formal register" (Mistral's training emphasis on EU regulatory compliance content produces slightly formal phrasing in English).
- **Concrete examples.**
  1. Mistral references GDPR or the EU AI Act more naturally than Anthropic or OpenAI models.
  2. Mistral references specific open-source licenses (Apache, MIT, GPL) with more precision than competitors.
  3. Mistral references European data-protection norms when discussing data architecture.
- **Location and register.** Regulatory and open-source-adjacent topics.
- **Model attribution.** Mistral family (high confidence in regulatory and open-source contexts).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** LOW (genre-specific).
- **Base rate (per-family).** High in regulatory and open-source contexts.
- **Causal hypothesis (ranked).** Training corpus emphasis on EU regulatory content and open-source documentation.
- **Detection difficulty.** Medium.
- **False positive risk.** High (EU-based human writers exhibit the same pattern).
- **Fix or remediation.** N/A as a stylistic baseline.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-MISTRAL-006: Lower agent-reflex density

- **ID.** A1-MISTRAL-006
- **Name.** Lower agent-reflex density
- **Description.** Mistral produces fewer "You're absolutely right" or "Great question!" openers than Claude/GPT. Cross-validates with `[perplexity]`'s "A1-MISTRAL-007: Lower sycophancy rate" (Mistral does not produce "Certainly!" or "I'd be happy to" at GPT rates) and `[deepseek]`'s A1-MISTRAL-002 ("I can provide information about...") as the more characteristic phrasing.
- **Concrete examples.**
  1. Mistral typically opens with "I can provide..." rather than "Certainly! Here is..."
  2. Mistral does not produce "Great question!" at GPT rates.
  3. Mistral does not produce "You're absolutely right" reflex at Claude rates.
- **Location and register.** Response openers.
- **Model attribution.** Mistral family (high confidence as a negative marker).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`.
- **Signal strength.** MEDIUM as a negative marker.
- **Base rate (per-family).** Substantially lower agent-reflex density than Claude or GPT.
- **Causal hypothesis (ranked).** RLHF training that under-prioritizes warm openers compared to Anthropic/OpenAI.
- **Detection difficulty.** Easy (compare against expected agent-reflex density).
- **False positive risk.** Moderate (many human writers also default to direct responses).
- **Fix or remediation.** N/A as a stylistic baseline.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER (negative marker for opener pleasantries).

### A1-MISTRAL-007: Concise default

- **ID.** A1-MISTRAL-007
- **Name.** Concise default
- **Description.** Per `[perplexity]`'s A1-MISTRAL-001, Mistral produces shorter responses than GPT or Gemini; this can read as terse rather than clear. Cross-validates with `[deepseek]`'s "A1-MISTRAL-001: Concise, Formal Yet Warm Tone" (Mistral models produce efficient prose with less fluff but a slightly stiff polite register).
- **Concrete examples.**
  1. Mistral response to "Explain the trade-offs between Postgres and MongoDB" runs 200 words; equivalent GPT-4o response runs 600 words.
  2. Mistral analytical responses pack claim density without padding.
  3. Mistral does not produce the warm-up paragraph that Claude or GPT might add before getting to the substance.
- **Location and register.** Body of responses across registers.
- **Model attribution.** Mistral family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[perplexity]`, `[deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** High distinctiveness in response length.
- **Causal hypothesis (ranked).** Training and RLHF that prioritizes conciseness over comprehensiveness.
- **Detection difficulty.** Easy (aggregate response-length analysis).
- **False positive risk.** Moderate (skilled writers also default to conciseness).
- **Fix or remediation.** N/A as a stylistic baseline.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-MISTRAL-008: Direct completion pattern

- **ID.** A1-MISTRAL-008
- **Name.** Direct completion pattern
- **Description.** Per `[perplexity]`'s A1-MISTRAL-004, Mistral finishes tasks without editorial commentary; no "I hope this helps" closer.
- **Concrete examples.**
  1. Mistral ends a response with the final substantive claim and stops.
  2. Mistral does not produce the GPT-style "Feel free to ask if you have more questions!" closer.
  3. Mistral does not produce the Claude-style "Is there anything else I can help you with?" concierge closer.
- **Location and register.** Response closers across registers.
- **Model attribution.** Mistral family (high confidence as a negative marker for closer pleasantries).
- **Time evolution.** Consistent across versions.
- **Sources.** `[perplexity]`.
- **Signal strength.** MEDIUM as a negative marker.
- **Base rate (per-family).** Very high in unedited Mistral output (closer pleasantries are mostly absent).
- **Causal hypothesis (ranked).** RLHF training that under-prioritizes closer pleasantries compared to Anthropic/OpenAI.
- **Detection difficulty.** Easy (compare against expected closer-pleasantry density).
- **False positive risk.** Moderate (skilled writers also default to direct completion).
- **Fix or remediation.** N/A as a stylistic baseline.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER (negative marker for closer pleasantries).

### A1-MISTRAL-009: Technical register dominance

- **ID.** A1-MISTRAL-009
- **Name.** Technical register dominance
- **Description.** Per `[perplexity]`'s A1-MISTRAL-006, Mistral defaults to technical phrasing even in non-technical contexts.
- **Concrete examples.**
  1. (For a casual prompt) Mistral uses "execute the procedure" where Claude or GPT might use "do it."
  2. (For a layperson question) Mistral uses "validate the input parameters" where Claude or GPT might use "check that the inputs are correct."
  3. (For an everyday topic) Mistral uses "implement the strategy" where Claude or GPT might use "try the approach."
- **Location and register.** Body of responses across registers.
- **Model attribution.** Mistral family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[perplexity]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** High in unedited Mistral output.
- **Causal hypothesis (ranked).** Training corpus emphasis on technical documentation.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate (technical writers also default to technical phrasing).
- **Fix or remediation.** Re-register for the audience. "Execute the procedure" becomes "do it" when the audience is casual.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

## A1.8 Qwen / Alibaba family

Models in scope: Qwen 2.5 and Qwen 3 series across Chat, Coder, and reasoning variants. The Qwen 1 and Qwen 2 historical entries live in [historical-patterns.md](historical-patterns.md). Qwen patterns are documented primarily from r/LocalLLaMA practitioner observation. No peer-reviewed stylometric English-language study of Qwen output was found as of May 2026 per `[perplexity]`. The family's English output reflects Chinese-language primary training, producing measurable surface differences from Western-developed models. English-language editorial audits would rarely encounter Qwen except in self-hosted or open-source-developer deployments.

### A1-QWEN-001: CJK punctuation slips (Unicode-detectable)

- **ID.** A1-QWEN-001
- **Name.** CJK punctuation slips (Unicode-detectable)
- **Description.** Qwen family occasionally produces CJK-specific punctuation (full-width comma, period, quotation marks) in English text. The slip is Unicode-detectable. Cross-validates with `[perplexity]`'s "A1-QWEN-001: Chinese-English code-switching artifact" (Qwen occasionally produces Chinese characters in English contexts, particularly in parenthetical clarifications).
- **Concrete examples.**
  1. Full-width comma (U+FF0C) appearing in English text: "The system runs efficiently, and the throughput is consistent."
  2. Full-width period (U+3002) appearing at the end of an English sentence.
  3. CJK quotation marks (U+300C, U+300D or U+201C, U+201D variants) appearing in English text.
  4. Occasional Chinese characters mid-paragraph in parenthetical clarifications.
- **Location and register.** All registers.
- **Model attribution.** Qwen family (very high confidence). Largely absent from Western-developed models.
- **Time evolution.** Improving across versions but still present.
- **Sources.** `[claude-exec-2026-05-18]` (cited as specifically diagnostic). `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** VERY HIGH when CJK characters appear unexpectedly.
- **Base rate (per-family).** Low overall; concentrated in specific contexts where the bilingual training surfaces.
- **Causal hypothesis (ranked).** Primary: bilingual training corpus. Secondary: tokenizer effects on punctuation tokens.
- **Detection difficulty.** Easy (Unicode character search).
- **False positive risk.** Very low (English-only human writers do not use CJK punctuation).
- **Fix or remediation.** Strip CJK punctuation and replace with ASCII equivalents.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-QWEN-002: Chinese cultural references and idiom translations

- **ID.** A1-QWEN-002
- **Name.** Chinese cultural references and idiom translations
- **Description.** Qwen occasionally references Chinese cultural concepts or translates Chinese idioms literally, reflecting primary training. Cross-validates with `[perplexity]`'s "A1-QWEN-005: Topic-sentence-last paragraph structure" (some Qwen responses build to the main point rather than leading with it, reflecting Chinese rhetorical conventions).
- **Concrete examples.**
  1. Direct translations of Chinese idioms that read oddly in English (e.g., "to draw a snake and add feet" rather than the equivalent English idiom "to gild the lily").
  2. References to specific Chinese cultural concepts (e.g., guanxi, mianzi) used without translation context.
  3. Paragraph structure that builds to the topic sentence at the end rather than leading with it, reflecting Chinese rhetorical conventions.
- **Location and register.** Analytical and explanatory responses.
- **Model attribution.** Qwen family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Moderate; specific to topics where Chinese cultural references are relevant.
- **Causal hypothesis (ranked).** Primary: training corpus emphasis on Chinese-language content. Secondary: RLHF training data that includes translated Chinese idioms.
- **Detection difficulty.** Medium (requires recognition of the underlying Chinese idiom).
- **False positive risk.** Moderate (Chinese-speaking ESL human writers exhibit similar patterns).
- **Fix or remediation.** Replace literal translations with the equivalent English idiom or with the underlying claim stated plainly.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-QWEN-003: Heavier hedging on China-political topics

- **ID.** A1-QWEN-003
- **Name.** Heavier hedging on China-political topics
- **Description.** Qwen exhibits notably heavier hedging or refusal on topics related to Chinese politics, compared to Anthropic/OpenAI models. Alignment-trained. Cross-validates with `[perplexity]`'s "A1-QWEN-007: Conservative content filtering artifacts" (Qwen has broader content restrictions that produce visible topic avoidance on politically sensitive queries).
- **Concrete examples.**
  1. Qwen produces vague or non-committal responses to questions about Chinese government policies that frontier Western models would answer more directly.
  2. Qwen avoids specific names or events that frontier Western models would mention.
  3. Qwen produces refusal-shaped closes on topics adjacent to Chinese political sensitivity.
- **Location and register.** China-political topics.
- **Model attribution.** Qwen family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** HIGH for topic-specific identification.
- **Base rate (per-family).** Very high on China-political topics.
- **Causal hypothesis (ranked).** Alignment and safety tuning aligned with Chinese regulatory requirements.
- **Detection difficulty.** Easy (specific topic + visible hedging pattern).
- **False positive risk.** Low.
- **Fix or remediation.** N/A as a content-quality concern; relevant for content auditing and source attribution.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-QWEN-004: Math-step formatting differences

- **ID.** A1-QWEN-004
- **Name.** Math-step formatting differences
- **Description.** Qwen math output uses formatting conventions (alignment, step labeling) closer to Chinese-math-education conventions than Western conventions. Cross-validates with `[perplexity]`'s "A1-QWEN-006: Number formatting differences" (Qwen may use Chinese number formatting conventions in some contexts).
- **Concrete examples.**
  1. Math steps labeled with Chinese-education-style numbering (e.g., specific brackets, alignment).
  2. Number formatting that uses Chinese conventions (e.g., specific decimal separators or grouping).
  3. Mathematical proof structure that follows Chinese-math-education conventions.
- **Location and register.** Mathematical and quantitative responses.
- **Model attribution.** Qwen family (high confidence in math contexts).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** LOW (genre-specific).
- **Base rate (per-family).** Moderate in math contexts.
- **Causal hypothesis (ranked).** Training corpus emphasis on Chinese-math-education content.
- **Detection difficulty.** Medium (requires familiarity with both Chinese and Western math conventions).
- **False positive risk.** High (math educators from China-trained backgrounds exhibit the same conventions).
- **Fix or remediation.** Reformat to Western conventions for English-speaking audiences.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-QWEN-005: Specific phrasings translated from Chinese

- **ID.** A1-QWEN-005
- **Name.** Specific phrasings translated from Chinese
- **Description.** Qwen English output sometimes contains phrasings that read as direct translations from Chinese idioms or structures. Cross-validates with `[perplexity]`'s "A1-QWEN-002: Formal Chinese academic register mapped to English" (Qwen in English tends toward elevated formal constructions reflecting Chinese academic writing conventions).
- **Concrete examples.**
  1. "It can be seen that..." (direct translation of a Chinese academic construction)
  2. "From the above, we can conclude that..." (Chinese-academic-register translation)
  3. "There are several considerations worth noting in this regard." (literal translation pattern)
- **Location and register.** Academic and analytical writing.
- **Model attribution.** Qwen family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** High in academic and analytical writing.
- **Causal hypothesis (ranked).** Training corpus emphasis on Chinese academic writing translated to English.
- **Detection difficulty.** Medium (requires recognition of the underlying Chinese construction).
- **False positive risk.** High (Chinese-speaking ESL human writers exhibit the same patterns).
- **Fix or remediation.** Replace with natural English constructions. "It can be seen that X" becomes "X is evident" or "X is the case."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-QWEN-006: Different agentic-reflex patterns

- **ID.** A1-QWEN-006
- **Name.** Different agentic-reflex patterns
- **Description.** Qwen's agentic-reflex patterns differ from Claude's "You're absolutely right" or GPT's "Great question". Specific to Qwen training. Cross-validates with `[perplexity]`'s "A1-QWEN-004: Explicit role assertion" ("As an AI assistant, I will..." opener; more common in Qwen than in Western-developed models).
- **Concrete examples.**
  1. "As an AI assistant, I will help you with..."
  2. "Below is a detailed explanation:"
  3. "I will now address your question."
- **Location and register.** Response openers.
- **Model attribution.** Qwen family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** MEDIUM (family-distinctive openers).
- **Base rate (per-family).** High in unedited Qwen output.
- **Causal hypothesis (ranked).** RLHF training that explicitly produces these compliance markers, distinct from Western RLHF approaches.
- **Detection difficulty.** Easy.
- **False positive risk.** Low (the specific phrasing is uncommon in skilled English-native writing).
- **Fix or remediation.** Strip the opener; start with the substantive response.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER.

### A1-QWEN-007: Lower idiomatic-English density

- **ID.** A1-QWEN-007
- **Name.** Lower idiomatic-English density
- **Description.** Like DeepSeek, Qwen produces fewer English idioms than Anthropic/OpenAI models. Subtle negative marker. Cross-validates with `[perplexity]`'s "A1-QWEN-003: Honorific register markers" (Qwen uses "please" and "kindly" more frequently than English-native models).
- **Concrete examples.**
  1. Qwen avoids idioms like "putting all your eggs in one basket" or "looking under every rock."
  2. Qwen favors direct phrasing over culturally-specific allusion.
  3. Qwen uses "please" and "kindly" at higher rates than Western-developed models, reflecting Chinese honorific conventions.
- **Location and register.** Body paragraphs across registers.
- **Model attribution.** Qwen family (high confidence as a negative marker for English idioms).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** LOW (subtle negative marker).
- **Base rate (per-family).** Substantially lower idiom density than Anthropic/OpenAI.
- **Causal hypothesis (ranked).** Bilingual training corpus; English is not the primary training language.
- **Detection difficulty.** Hard (requires comparing against expected idiom density).
- **False positive risk.** High (ESL human writers exhibit the same pattern; ESL safe-harbor applies).
- **Fix or remediation.** N/A as a content-quality concern; relevant for stylometric attribution.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-QWEN-008: "Below is a detailed explanation:"

- **ID.** A1-QWEN-008
- **Name.** "Below is a detailed explanation:" opener
- **Description.** Per `[deepseek]`'s A1-QWEN-001, a consistent response opener.
- **Concrete examples.**
  1. "Below is a detailed explanation: ..."
  2. "Below is a step-by-step breakdown: ..."
  3. "Below is a comprehensive overview: ..."
- **Location and register.** Response openers.
- **Model attribution.** Qwen family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[deepseek]`.
- **Signal strength.** MEDIUM (family-distinctive opener).
- **Base rate (per-family).** Frequent in long-form explanatory responses.
- **Causal hypothesis (ranked).** RLHF training data that includes this specific opener pattern in instruction-tuning examples.
- **Detection difficulty.** Easy.
- **False positive risk.** Low (the specific phrasing is uncommon in skilled English-native writing).
- **Fix or remediation.** Strip the opener; start with the substantive content.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER.

### A1-QWEN-009: Overuse of "Moreover," and "In addition,"

- **ID.** A1-QWEN-009
- **Name.** Overuse of "Moreover," and "In addition,"
- **Description.** Per `[deepseek]`'s A1-QWEN-002, additive transitions saturate Qwen output. Maps to v3.1.0 criterion 6 (Overuse of Transition Words).
- **Concrete examples.**
  1. "Moreover, the system handles peak load efficiently. In addition, the latency remains low."
  2. "In addition to the cost savings, the migration also improves reliability. Moreover, the team's productivity has increased."
  3. "Moreover, we can leverage existing infrastructure. In addition, the deployment timeline is favorable."
- **Location and register.** Analytical and argumentative prose.
- **Model attribution.** Qwen family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** High in unedited Qwen analytical output.
- **Causal hypothesis (ranked).** Training data emphasis on formal academic register where additive transitions are conventionally used.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate (academic writers also use these transitions legitimately).
- **Fix or remediation.** Vary transitions; embed additive points within the same sentence where possible.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-QWEN-010: Formal, almost textbook tone

- **ID.** A1-QWEN-010
- **Name.** Formal, almost textbook tone
- **Description.** Per `[deepseek]`'s A1-QWEN-004, Qwen's English output reads like a translated textbook, with stilted phrasing.
- **Concrete examples.**
  1. "It is important to understand that the underlying mechanism operates through a series of carefully orchestrated steps."
  2. "The implementation of this strategy requires careful consideration of multiple interrelated factors."
  3. "One must take into account the various dimensions of the problem before proceeding with the proposed solution."
- **Location and register.** Body paragraphs across registers.
- **Model attribution.** Qwen family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** High in unedited Qwen output.
- **Causal hypothesis (ranked).** Training corpus emphasis on translated textbook content.
- **Detection difficulty.** Medium (requires comparison against expected register).
- **False positive risk.** High (translated textbook writers exhibit the same pattern; ESL safe-harbor applies).
- **Fix or remediation.** Simplify to natural conversational or analytical register.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

## Summary and Cross-References

This file catalogs **eighty-seven Active-era patterns** across eight model families:

- A1.1 Anthropic Claude: 28 Active patterns (A1-CLAUDE-001 through A1-CLAUDE-028, including DeepSeek, Perplexity, and Gemini contributions; A1-CLAUDE-028 is Declining).
- A1.2 OpenAI GPT: 18 Active patterns (A1-GPT-001 through A1-GPT-020, excluding A1-GPT-006 and A1-GPT-007 which are Historical; A1-GPT-018 is Declining).
- A1.3 Google Gemini: 13 Active patterns (A1-GEMINI-001 through A1-GEMINI-013).
- A1.4 Meta Llama: 10 Active patterns (A1-LLAMA-001 through A1-LLAMA-010).
- A1.5 xAI Grok: 10 Active patterns (A1-GROK-001 through A1-GROK-010).
- A1.6 DeepSeek: 10 Active patterns (A1-DEEPSEEK-001 through A1-DEEPSEEK-010).
- A1.7 Mistral / Mixtral: 9 Active patterns (A1-MISTRAL-001 through A1-MISTRAL-009).
- A1.8 Qwen / Alibaba: 10 Active patterns (A1-QWEN-001 through A1-QWEN-010).

Total Active-era patterns: 108 across the eight families.

Historical and Deprecated patterns from older versions of each family live in [historical-patterns.md](historical-patterns.md). Cross-references between Active patterns in this file and the historical lineage in that file are preserved at the relevant entries.

### Related references files

- [detailed-criteria.md](detailed-criteria.md): full per-criterion detail for the 42 v3.1.0 criteria, refreshed with v4.0 era status and zone tags. Cross-references between A1 family patterns and the underlying criteria are inline at each pattern entry above.
- [substance-and-depth.md](substance-and-depth.md): full A2 sub-pattern detail (deletion test, specificity test, load-bearing claim count, novelty signal, insight-to-word ratio, any-company test, hedging-as-substance-evasion, survey-without-claim, generic insight, both-sides-without-position, pseudo-profundity, conclusion-shaped paragraphs that do not conclude, frictionless-transition padding, and additional sub-patterns from cross-LLM contributions).
- [combined-signal-fingerprints.md](combined-signal-fingerprints.md): full B2 table of 86 combined-signal fingerprints (which combinations of A1 patterns, when co-occurring, produce the strongest detection signals).
- [calibration-tables.md](calibration-tables.md): full B3 per-family per-criterion calibration with the BR-artifact-body vs. BR-full-response split, the ESL safe-harbor, and zone-conditional base rates.
- [historical-patterns.md](historical-patterns.md): all Historical and Deprecated patterns retained per the compounding-archive principle.
- [bibliography.md](bibliography.md): consolidated bibliography from all unified buckets with verification status.

### Detection mode selection (zone-conditional)

Per the GATE 2 design considerations:

- In **artifact mode** (default for editorial review of submitted content), apply only `BODY-PERSISTENT`, `HYBRID`, and `MID-BODY-INSERT` patterns. Skip all `WRAPPER-OPENER` and `WRAPPER-CLOSER` patterns. False-positive rate stays low when only the artifact body is being audited.
- In **full-response mode** (for forensic chat-log analysis), apply all patterns including wrapper-only.

The skill's confidence-based evaluation process selects mode upfront by asking the user: "Are you auditing just the produced content, or the full LLM response including conversational framing?" The mode is the operative input to which patterns the detector applies.

### Em-dash audit

This file uses no em-dashes (U+2014). Commas, parentheses, colons, and sentence breaks substitute throughout. The constraint is part of the subject matter: criterion 11 and criterion 42 of v3.1.0 flag em-dash density as a high-signal AI marker, so a reference document for the upgrade cannot itself produce the pattern it is cataloguing.
