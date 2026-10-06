# Historical Patterns Reference, part 2 of 2

Part 2 of the file split from [historical-patterns.md](historical-patterns.md), which keeps the opening sections and lists every part. The text below is unchanged.

Contents:
- Section 2: Net-new historical entries (A1-BARD-001, A1-LLAMA-HISTORICAL-001, A1-GROK-HISTORICAL-001, A1-DEEPSEEK-HISTORICAL-001, A1-MISTRAL-HISTORICAL-001, A1-QWEN-HISTORICAL-001, A1-GPT-HISTORICAL-001)
- Section 3: How to use historical patterns in forensic analysis of older published content: Step 1: Establish the artifact's era; Step 2: Select era-appropriate patterns; Step 3: Weight by base rate at the artifact's era; Step 4: Distinguish direct AI generation from quoted or parodied patterns; Step 5: Combine era-appropriate signals; Step 6: Document the era-tagged forensic conclusion; Step 7: Avoid era confusion
- Section 4: Cross-references and next steps

## Section 2: Net-new historical entries

These entries fill the audit-identified coverage gaps for older versions of newer-entrant families and for pre-instruction-tuning GPT-3. Each entry is anchored in cornerstone facts verified via web search in May 2026 and supplemented from Opus-4.7 training knowledge.

### A1-BARD-001: "As a large language model trained by Google..." preamble (Bard era)

- **Era status.** Historical (for forensic analysis of February 2023 through December 2023 Bard content). Deprecated for Gemini-rebranded outputs from February 2024 onward.
- **Useful for analyzing content from.** February 6, 2023 (Bard announcement) through December 6, 2023 (Gemini family announcement); residual through February 8, 2024 (Bard rebrand to Gemini). Highest density in calendar Q2-Q3 2023.
- **Zone tag.** `WRAPPER-OPENER`.
- **Description.** Bard, Google's first instruction-tuned conversational LLM (LaMDA-based; public access from March 21, 2023), prefaced opinion-seeking, identity, or safety-sensitive prompts with "As a large language model trained by Google..." or "As a large language model, I cannot provide personal opinions, but...". The Bard-family analog of GPT's `A1-GPT-007` preamble and Claude 1's `A1-CLAUDE-006` historical refusal-shaped close. Trained out after the Gemini rebrand in February 2024.
- **Concrete examples.**
  1. "As a large language model trained by Google, I don't have personal feelings or opinions on the matter."
  2. "As a large language model, I cannot provide medical advice, but I can offer some general information."
  3. "As a large language model trained by Google, my responses are based on patterns in my training data rather than first-hand experience."
- **Location and register.** Response openers, especially to opinion-seeking, identity, or safety-sensitive prompts. Higher density in the first 1-2 sentences of the response.
- **Model attribution.** Bard (very high confidence for the canonical phrasing). Distinct from GPT's "As an AI language model" (no Google attribution) and from Claude's softer "I'm Claude, an AI assistant..." framing.
- **Time evolution.** Emerged with Bard's public launch on March 21, 2023 (following the February 6, 2023 announcement). High density through 2023. Began declining late 2023 as Google iterated. Effectively absent from Gemini-rebranded outputs from February 8, 2024 forward.
- **Sources.** Google's Bard launch announcement (February 6, 2023; blog.google). Bard rebrand announcement (February 8, 2024; 9to5google.com). Walters and Wilder Sci Rep 2023 documented contemporary Bard citation behavior. Pre-upgrade unified bucket A briefly references the pattern; this entry formalizes it per the historical coverage audit.
- **Signal strength.** VERY HIGH for Bard provenance in 2023 content (definitive). LOW for any 2024+ content.
- **Base rate.** Estimated 20 to 35 percent of Bard responses to opinion or identity prompts in 2023. Higher than concurrent GPT-3.5 "As an AI language model" rate per practitioner observation. Effectively zero from February 2024 forward.
- **Causal hypothesis (ranked).** Primary: Google's alignment training that emphasized explicit category-self-identification and brand attribution. Secondary: legal and reputational risk management given Bard's high hallucination rate at launch. Tertiary: differentiation strategy versus GPT-3.5's then-canonical preamble.
- **Detection difficulty.** Easy. Exact phrase.
- **False positive risk.** Very low for the explicit phrase with Google attribution.
- **Fix or remediation.** For current Gemini outputs, strip any residual disclaimer. For historical Bard content, the preamble is the AI tell.

### A1-LLAMA-HISTORICAL-001: Lower-RLHF baseline (Llama 1 / Llama 2 era)

- **Era status.** Historical. Llama 1 (research-only release, February 24, 2023) and Llama 2 (public release, July 18, 2023) showed measurably lower RLHF intensity than concurrent Claude or GPT. Llama 3 (April 2024) and later models closed much of the gap; the historical baseline remains diagnostic for self-hosted fine-tunes of the older models.
- **Useful for analyzing content from.** February 24, 2023 (Llama 1 announcement) through mid-2024. Particularly applicable to content generated by self-hosted fine-tunes of Llama 1 or Llama 2 that did not include additional RLHF. Llama 3.x base behavior is documented in the active catalog.
- **Zone tag.** `BODY-PERSISTENT` (the baseline manifests as an absence of concierge tone throughout the body, not in a specific zone).
- **Description.** Llama 1 and Llama 2 base-released forms produced output with notably less RLHF-shaped concierge tone than contemporaneous Claude or GPT outputs. The signature was the absence of canonical RLHF artifacts: lower "Great question!" opener density (per active A1-LLAMA-004), less "It is important to note" mid-body insertion, lower "I hope this helps" closer rate, and a more direct refusal style ("I cannot help with that" rather than "I'd be cautious about helping with that because..."). The baseline was a self-hosted-deployment signal as much as a model signal: Llama 2 fine-tuners often added their own RLHF. Per the historical coverage audit, the pattern is "primarily useful for self-hosted-deployment forensic analysis."
- **Concrete examples.**
  1. A 2023 Llama 2 response to a how-to question that opens directly with the instruction list rather than a warm acknowledgment.
  2. A 2023 Llama 2 refusal that reads "I cannot help with that request" rather than "I'd be cautious about helping you with that because the topic involves potential harm to others."
  3. A 2024 self-hosted Llama 2 7B Chat response with markdown formatting present but bolded lead-ins absent, and no "It is worth noting..." mid-body inserts.
- **Location and register.** Body of response; absence of opener and closer ornament.
- **Model attribution.** Llama 1 (very high confidence for the absence pattern in research-only deployments). Llama 2 (high confidence for base-released Chat models; lower confidence for community fine-tunes that added concierge-tone training).
- **Time evolution.** Stable from Llama 1 release (February 24, 2023) through Llama 2 (July 18, 2023). Llama 3 (April 18, 2024) closed much of the gap with frontier RLHF intensity. Llama 4 (April 2025) further narrowed differences.
- **Sources.** Meta Llama 2 community license documentation (July 2023). Llama 1 research paper (ai.meta.com/research/publications/llama, February 2023). Pre-upgrade unified bucket A entries A1-LLAMA-001 through A1-LLAMA-006 document the family's stable lower-RLHF signature. The historical coverage audit (May 18, 2026) identifies the gap; this entry fills it.
- **Signal strength.** MEDIUM as a positive provenance signal (lower-RLHF baseline is common across smaller open models). HIGH as a negative marker when combined with absence of "I hope this helps" closers and Llama-family stylometric tells (per the active A1-LLAMA-001 entry on near-zero em-dash baseline).
- **Base rate.** Substantially elevated absence-of-RLHF-artifacts rate in Llama 1 and Llama 2 base outputs compared to concurrent Claude and GPT outputs. Hard to quantify precisely because the population of Llama 2 deployments included many community fine-tunes that varied.
- **Causal hypothesis (ranked).** Primary: Meta's open-release approach in 2023 prioritized base-model utility over heavy alignment fine-tuning. Secondary: research-orientation of Llama 1 reduced incentives for product-grade RLHF. Tertiary: community fine-tunes that added RLHF varied widely in style and frequently mimicked Claude or GPT rather than maintaining the base lower-RLHF default.
- **Detection difficulty.** Medium. Requires comparison against contemporaneous Claude / GPT baselines on the same prompt class.
- **False positive risk.** High. Many other open models (Mistral 7B, Vicuna 13B, Alpaca, others) had similar lower-RLHF baselines in the 2023-2024 era.
- **Fix or remediation.** For current Llama 4 outputs, the gap with frontier RLHF intensity is small; standard frontier-model patterns apply. For 2023-2024 archives, the baseline is itself the AI signal and is consistent with the open-model deployment register.

### A1-GROK-HISTORICAL-001: Edgier register stable trait (Grok 1 launch forward)

- **Era status.** Historical entry for Grok 1 launch (November 4, 2023); the edgier-register stable trait persists in current Grok 2, Grok 3, and Grok 4 frontier output and is documented in the active A1-GROK-001 entry. This historical entry anchors the trait at the family's launch and provides the dating reference for forensic analysis of early Grok content.
- **Useful for analyzing content from.** November 4, 2023 (xAI Grok unveiling) forward. Particularly diagnostic for late-2023 and 2024 content where the edgier-register signal was strongest before competing frontier families partially closed the differentiation.
- **Zone tag.** `BODY-PERSISTENT`.
- **Description.** Grok 1, launched in beta on November 3, 2023 and unveiled on November 4, 2023, was xAI's launch instruction-tuned model. xAI positioned the family around an "edgier" register: colloquial internet-native phrasing, occasional sarcasm, willingness to use mild profanity, and lower hedging density than concurrent Claude or GPT. The trait was hardcoded since Grok 1 and maintained through subsequent generations as a brand differentiator. Forensic analysis of late-2023 content uses this entry as the anchor for distinguishing Grok provenance from concurrent Claude, GPT, or Bard outputs.
- **Concrete examples.**
  1. (Grok 1, late 2023): "Look, the terms-of-service nobody actually reads is a feature, not a bug, of online life."
  2. (Grok 1, late 2023): "The marketing strategy here is a bit of a dumpster fire, but it could work if properly funded."
  3. (Grok 1, late 2023): "Here is the code. Try not to break production this time."
- **Location and register.** Body throughout. Particularly visible in conversational and analytical responses; less visible in pure-technical code generation.
- **Model attribution.** Grok 1 (high confidence for the launch-era register). Distinct from contemporaneous Claude 2 (more formal), GPT-4 (concierge tone), and Bard (cautious hedging) outputs.
- **Time evolution.** Edgier register hardcoded from launch (November 4, 2023). Maintained through Grok 1.5 (March 2024), Grok 2 (August 2024), Grok 3 (February 2025), and Grok 4 (frontier as of 2026). Some softening in production deployments where xAI tuned for enterprise use, but the family-stable trait remains.
- **Sources.** xAI Grok announcement (November 4, 2023; x.ai/grok). Fortune coverage of Grok launch (November 6, 2023; fortune.com). Pre-upgrade unified bucket A entry A1-GROK-001 documents the active trait; the historical coverage audit identifies the need to anchor the trait at launch.
- **Signal strength.** HIGH when combined with attribution to xAI or X-Premium-Grok-Premium subscription context in 2023-2024 content. MEDIUM standalone for distinguishing from contemporaneous Bard (which lacked the edgier register).
- **Base rate.** Estimated 30 to 45 percent of Grok 1 non-technical outputs in 2023-2024 carried at least one edgier-register marker. Higher when xAI's "Fun Mode" was active.
- **Causal hypothesis (ranked).** Primary: xAI alignment choices that explicitly prioritized truth-seeking over user-pleasing per xAI's positioning. Secondary: RLHF tuning that exposed the model to internet-subculture corpora at higher density than competing frontier families. Tertiary: founder-level direction from Elon Musk to differentiate xAI from OpenAI's then-canonical concierge tone.
- **Detection difficulty.** Easy when the colloquialism is overt.
- **False positive risk.** Low when combined with other Grok-family fingerprints (real-time data references, Twitter-style structural defaults). Higher in pure-colloquial human writing that mimics internet-native voice.
- **Fix or remediation.** For current outputs, use strict system prompts (e.g., the E.R.A. framework documented in active A1-GROK-001) to force a more professional persona. For historical archives, the edgier register is the AI signal.

### A1-DEEPSEEK-HISTORICAL-001: Bilingual-corpus influence (DeepSeek V1 forward)

- **Era status.** Historical entry for DeepSeek LLM V1 launch (November 29, 2023); the bilingual-corpus influence persists in current DeepSeek V3 and R1 frontier output and is documented in the active A1-DEEPSEEK-001 through A1-DEEPSEEK-007 entries. This historical entry anchors the trait at the family's launch and provides the dating reference.
- **Useful for analyzing content from.** November 29, 2023 (DeepSeek LLM V1 release) forward. Particularly diagnostic in 2024 outputs from DeepSeek V2 (May 2024), V2.5 (September 2024), V3 (December 2024), and R1 (January 2025) where the bilingual influence is most visible in English-prose subordinate-clause structure and idiom density.
- **Zone tag.** `BODY-PERSISTENT`.
- **Description.** DeepSeek LLM V1 was released on November 29, 2023 with 7B and 67B parameter sizes, trained on 2 trillion tokens of bilingual English and Chinese text from deduplicated Common Crawl. The bilingual training corpus produced a stable family-level fingerprint: lower English idiom density than monolingual frontier families, slightly different sentence-rhythm baseline, occasional language-mixing under reasoning load (active A1-DEEPSEEK-002), and a more encyclopedia-like prose register. Pattern persists from V1 forward; this entry anchors the influence at launch.
- **Concrete examples.**
  1. (DeepSeek V1, late 2023): English-prose response with comma-spliced sentences where a native English writer would use a semicolon or full stop. ("The system processes input, the output is generated, the result is returned to the user.")
  2. (DeepSeek V2, mid-2024): Use of "Moreover," and "In addition," at higher density than native English frontier models, reflecting Chinese-rhetorical-tradition transitional preferences.
  3. (DeepSeek V2.5, late 2024): Encyclopedia-tone response with minimal hedging and reduced colloquial idiom density. ("The X protocol operates by Y mechanism. The Z component handles W function. The result is V output.")
- **Location and register.** Body throughout. Most visible in analytical and explainer registers; less visible in pure-technical code generation.
- **Model attribution.** DeepSeek LLM V1 (high confidence for the launch-era bilingual influence). Persists through V2, V2.5, V3, and R1.
- **Time evolution.** Stable from V1 launch (November 29, 2023). Some sharpening of English-prose polish in V2 (May 2024) and V3 (December 2024) as the team iterated on instruction tuning. R1 (January 2025) introduces visible reasoning-trace patterns (active A1-DEEPSEEK-001) that overlay the bilingual baseline.
- **Sources.** DeepSeek LLM V1 release (November 29, 2023; github.com/deepseek-ai/DeepSeek-LLM). DeepSeek-V2 release paper (May 2024). Pre-upgrade unified bucket A entries A1-DEEPSEEK-001 through A1-DEEPSEEK-007 document active manifestations.
- **Signal strength.** MEDIUM standalone. HIGH when combined with explicit DeepSeek attribution or with language-mixing markers from active A1-DEEPSEEK-002.
- **Base rate.** Substantially elevated compared to concurrent GPT and Claude outputs on the same prompt class. Hard to quantify precisely without controlled stylometry.
- **Causal hypothesis (ranked).** Primary: training-data composition that included substantial Chinese-language corpus contributions. Secondary: DeepSeek's iteration approach that did not heavily over-fit English-prose stylistic conventions in instruction tuning. Tertiary: research-orientation of the V1 release reduced incentives for product-grade English-prose polish.
- **Detection difficulty.** Medium. Requires familiarity with native English prose rhythm and idiom density.
- **False positive risk.** Moderate to high. Many ESL-written English texts share similar surface markers per Liang et al. 2023's caveats about ESL safe-harbor in AI detection.
- **Fix or remediation.** For current outputs, the bilingual influence is a stable family trait; no fix is needed unless the deployment context calls for monolingual-style English-prose polish.

### A1-MISTRAL-HISTORICAL-001: French-corpus syntax influence (Mistral 7B launch forward)

- **Era status.** Historical entry for Mistral 7B launch (September 2023); the French-corpus syntax influence persists in current Mistral output and is documented in active A1-MISTRAL-001 entry. This historical entry anchors the trait at the family's launch and provides the dating reference.
- **Useful for analyzing content from.** September 27, 2023 (Mistral 7B release) forward. Mixtral 8x7B (December 11, 2023) and Mistral Large 1 (February 2024) inherit the influence. Particularly diagnostic in 2024 Mistral outputs.
- **Zone tag.** `BODY-PERSISTENT`.
- **Description.** Mistral AI was founded in Paris in April 2023 and released Mistral 7B as the European open-source-aligned launch on September 27, 2023. The training corpus included substantial French-language and European-multilingual content alongside English. Result: a family-level syntactic fingerprint that combines French-syntax-influenced subordinate-clause ordering, different default formatting conventions (active A1-MISTRAL-004), more direct refusal style (active A1-MISTRAL-002), and lower saturated-vocabulary density than monolingual English-trained frontier models (active A1-MISTRAL-003). Pattern persists from Mistral 7B forward; this entry anchors the influence at launch.
- **Concrete examples.**
  1. (Mistral 7B, late 2023): "The system, which is designed to handle multiple concurrent connections, processes the input asynchronously" (relative-clause-heavy construction more characteristic of French-translated English than native English).
  2. (Mixtral 8x7B, early 2024): Refusal with "I cannot do that" directness, lacking the apologetic preamble characteristic of Claude or the partial-refusal stem characteristic of GPT.
  3. (Mistral Large 1, 2024): Lower density of "delve," "robust," "leverage," "tapestry" focal words compared to concurrent GPT outputs.
- **Location and register.** Body throughout. Most visible in long-form analytical responses; less visible in short code or fact answers.
- **Model attribution.** Mistral 7B (high confidence for the launch-era European-corpus influence). Persists through Mixtral 8x7B, Mistral Large 1, Mistral Large 2.
- **Time evolution.** Stable from Mistral 7B release (September 27, 2023). Mixtral 8x7B (December 11, 2023) introduced sparse mixture-of-experts architecture but maintained the corpus-influenced style. Mistral Large 1 (February 2024) closed some of the English-prose-polish gap.
- **Sources.** Mistral 7B release paper (September 2023; arxiv.org/abs/2310.06825). Mixtral of Experts paper (January 2024; arxiv.org/abs/2401.04088). Pre-upgrade unified bucket A entries A1-MISTRAL-001 through A1-MISTRAL-007 document active manifestations.
- **Signal strength.** MEDIUM standalone. HIGHER when combined with explicit Mistral attribution or with European-deployment context (Mistral was the European open-source-aligned launch).
- **Base rate.** Elevated compared to concurrent GPT and Claude outputs on the same prompt class. Quantification depends on stylometry tooling.
- **Causal hypothesis (ranked).** Primary: training-data composition that included substantial European-multilingual corpus contributions reflecting Mistral AI's Paris origin and European focus. Secondary: instruction-tuning methodology that did not heavily over-fit American-English-prose conventions. Tertiary: open-source release approach (Apache 2.0 license for Mixtral) that prioritized base utility over heavy alignment polish.
- **Detection difficulty.** Medium. Requires familiarity with translation-influenced English prose patterns.
- **False positive risk.** Moderate. Many French-to-English translated texts share similar surface markers; Quebec or European English writers may also show similar patterns.
- **Fix or remediation.** For current outputs, the syntax influence is a stable family trait; no fix is needed unless the deployment context calls for American-English-prose conventions.

### A1-QWEN-HISTORICAL-001: CJK punctuation slips and Chinese cultural references (Qwen 1 launch forward)

- **Era status.** Historical entry for Qwen 1 launch (August 2023); the CJK-punctuation and Chinese-cultural-reference patterns persist in current Qwen output and are documented in active A1-QWEN-001 through A1-QWEN-007 entries. This historical entry anchors the traits at the family's launch.
- **Useful for analyzing content from.** August 3, 2023 (Alibaba Cloud open-source release of Qwen-7B) forward. Particularly diagnostic in Qwen 1.x, Qwen 2 (June 2024), and Qwen 2.5 (September 2024) outputs.
- **Zone tag.** `BODY-PERSISTENT`.
- **Description.** Qwen 1 (Tongyi Qianwen, Alibaba Cloud) was beta-released in April 2023 and open-sourced as Qwen-7B on August 3, 2023 via ModelScope and Hugging Face. The training corpus was Chinese-language-primary with English support, producing a family-level fingerprint: occasional Unicode-detectable CJK punctuation slips (active A1-QWEN-001), Chinese cultural references and idiom translations (active A1-QWEN-002), heavier hedging on China-political topics (active A1-QWEN-003), math-step formatting conventions reflecting Chinese math-textbook style (active A1-QWEN-004), and specific phrasings translated from Chinese (active A1-QWEN-005). Pattern persists from Qwen 1 forward; this entry anchors the traits at launch.
- **Concrete examples.**
  1. (Qwen 1, late 2023): English prose response with a Chinese full-width comma (Unicode U+FF0C) appearing in place of an ASCII comma in one or two locations: "The system processes input， then generates output."
  2. (Qwen 2, mid-2024): Reference to a Chinese-cultural concept (e.g., "guanxi" in business context) deployed in an English-language response without translation or explanation.
  3. (Qwen 2.5, late 2024): "I would suggest considering the matter from a balanced perspective" in response to a China-political topic where contemporaneous Claude or GPT would take a position.
- **Location and register.** Body throughout. CJK punctuation slips are universal across registers; Chinese cultural references concentrate in business, philosophy, and humanities prompts; heavier hedging concentrates in political and China-sensitive prompts.
- **Model attribution.** Qwen 1 (high confidence for the launch-era CJK influence). Persists through Qwen 2, Qwen 2.5, Qwen 3.
- **Time evolution.** Stable from Qwen-7B open-source release (August 3, 2023). Qwen 2 (June 2024) closed some of the English-prose polish gap. Qwen 2.5 (September 2024) and Qwen 3 (frontier as of 2026) iterated further but maintained the family-stable CJK fingerprint.
- **Sources.** Alibaba Cloud Qwen-7B open-source announcement (August 3, 2023; technode.global). QwenLM GitHub repository (github.com/QwenLM/Qwen). Pre-upgrade unified bucket A entries A1-QWEN-001 through A1-QWEN-012 document active manifestations.
- **Signal strength.** HIGH for the CJK-punctuation-slip pattern (character-level detection is unambiguous). MEDIUM for the cultural-reference and translation patterns.
- **Base rate.** CJK punctuation slip rate: low but non-zero in Qwen English-prose outputs (estimated 1 to 5 percent of responses contain at least one slip). Cultural-reference rate: variable, concentrated by prompt topic.
- **Causal hypothesis (ranked).** Primary: training-data composition that was Chinese-language-primary, with English as a secondary corpus contributor. Secondary: tokenizer behavior that handles CJK and ASCII characters in a unified vocabulary, occasionally producing the wrong width in output. Tertiary: alignment training that calibrated on China-relevant safety considerations.
- **Detection difficulty.** Easy for CJK punctuation slips (Unicode code-point check). Medium for cultural references; requires domain knowledge.
- **False positive risk.** Low for the CJK-punctuation-slip pattern. Moderate for cultural references in writing by bilingual Chinese-English authors.
- **Fix or remediation.** For current outputs in English-prose deployments, post-processing the response through a Unicode normalizer can catch CJK punctuation slips. For historical archives, the slips are the AI signal.

### A1-GPT-HISTORICAL-001: Pre-instruction-tuning GPT-3 raw base model patterns

- **Era status.** Historical. Primarily academic and forensic. Raw GPT-3 base model deployment was largely superseded by InstructGPT (January 2022) and ChatGPT (November 2022); editorial review of 2026 content is unlikely to encounter raw GPT-3 outputs but the entry preserves the compounding archive.
- **Useful for analyzing content from.** June 11, 2020 (GPT-3 API public access announcement) through November 30, 2022 (ChatGPT public release). Particularly relevant for content generated via OpenAI Playground for developer use, AI Dungeon (which used GPT-3 base in 2020-2021), and direct API integrations that did not use the InstructGPT models.
- **Zone tag.** `BODY-PERSISTENT`.
- **Description.** GPT-3 (June 11, 2020; 175 billion parameters; davinci, curie, babbage, ada model line) was released as a base completion model without RLHF instruction tuning. Pre-InstructGPT outputs showed characteristic patterns substantially shaped or eliminated by subsequent tuning: (a) absence of concierge-tone artifacts (no "Great question!" opener, no "I hope this helps" closer); (b) verbose continuation of prompt-provided text rather than direct question answering; (c) raw web-corpus echoes including occasional copy-paste-shaped training data fragments; (d) higher variance in tone and quality across consecutive completions; (e) more frequent factual errors and confabulations not softened by RLHF safety training; (f) inconsistent markdown formatting and structured-output adherence. InstructGPT (January 27, 2022) introduced supervised instruction-tuning plus RLHF on the base GPT-3 model. ChatGPT (November 30, 2022) added the chat-product wrapper.
- **Concrete examples.**
  1. (GPT-3 davinci, 2021, via OpenAI Playground): Response to "Write a short essay on the French Revolution" continues for several paragraphs in essay format but suddenly shifts mid-paragraph to a different style or topic, reflecting the base model's continuation-not-instruction behavior.
  2. (GPT-3 davinci, 2021): Response includes a passage that closely matches a Wikipedia article on the same topic with minor word substitutions, reflecting raw web-corpus echo.
  3. (GPT-3 davinci, 2020): Response to a factual question delivers the answer with high confidence but contains a confabulated specific (a date, a name, a number) without any hedge or caveat that InstructGPT-era models would add.
  4. (GPT-3 davinci, 2021): Same prompt run twice produces two very different responses in tone and quality due to absence of instruction-following calibration.
- **Location and register.** Body throughout. Particularly visible in long-form generative tasks (essays, stories, technical explanations) where the base model's continuation behavior diverges most from current instruction-tuned defaults.
- **Model attribution.** GPT-3 base models (davinci, curie, babbage, ada) deployed without InstructGPT-style fine-tuning. Very high confidence for raw-base-model outputs from 2020-2021. Lower confidence for 2022 outputs where some users had migrated to InstructGPT but others remained on raw GPT-3.
- **Time evolution.** Stable across the 2020-2022 raw-base-model era. InstructGPT (January 27, 2022) progressively replaced raw GPT-3 for instruction-following tasks; ChatGPT (November 30, 2022) completed the transition for chat deployments. Some specialized API deployments (AI Dungeon, custom integrations) continued using base GPT-3 into 2023.
- **Sources.** OpenAI GPT-3 announcement (June 11, 2020; openai.com/index/openai-api). InstructGPT announcement (January 27, 2022; openai.com/research/instruction-following). MIT Technology Review coverage of InstructGPT (January 27, 2022; technologyreview.com). Walters and Wilder Sci Rep 2023 documented post-ChatGPT hallucination rates that provide context for the pre-InstructGPT baseline.
- **Signal strength.** HIGH for raw-base-model outputs from 2020-2021 (definitive of pre-InstructGPT provenance when combined with deployment context). MEDIUM for 2022 outputs where the era transition was in progress.
- **Base rate.** Hard to quantify in absolute terms because raw GPT-3 deployments were primarily developer-API rather than consumer-product. AI Dungeon, GPT-3 Playground users, and integration developers were the primary populations.
- **Causal hypothesis (ranked).** Primary: pre-InstructGPT GPT-3 was a base completion model trained on web corpus without RLHF or supervised instruction tuning. Secondary: absence of the alignment-trained safety release and concierge-tone patterns that became canonical with InstructGPT and ChatGPT. Tertiary: training-data composition (Common Crawl, WebText, Books, Wikipedia, English Wikipedia 2019 snapshot) that contained more raw web text without the human-feedback-shaped filtering that subsequent OpenAI training added.
- **Detection difficulty.** Medium. Requires comparison against instruction-tuned-era baseline on the same prompt class; raw-web-corpus echoes can be checked against Common Crawl and Wikipedia sources.
- **False positive risk.** Moderate. Some 2020-2022 content produced by other unaligned base models (early Bloom, OPT, GPT-Neo) shares similar surface markers.
- **Fix or remediation.** For 2020-2022 archives, the raw-base-model behavior is the AI signal and is consistent with pre-InstructGPT deployment register.

---

## Section 3: How to use historical patterns in forensic analysis of older published content

The compounding archive is the differentiating value of the synthesis-content-quality catalog. A newsroom editor reviewing a 2023 article for AI provenance, a media-history researcher studying the early-ChatGPT era, a litigator examining a 2024 deposition exhibit, or an academic studying changes in scientific writing over the 2020-2025 window all need era-appropriate detection tooling. This section outlines the forensic workflow.

### Step 1: Establish the artifact's era

The first step in forensic analysis is dating the artifact. Useful indicators:

- **Publication date metadata.** When the artifact is a published article, blog post, or document, the date is usually known. For internal or unsourced artifacts, the date is uncertain and must be inferred.
- **Topic recency.** References to events, products, or people fix a lower bound on the artifact's creation date.
- **Citation patterns.** The kinds of sources cited (Twitter / X username conventions before and after the rebrand, for example) help date the artifact.
- **Tool-specific markers.** "As an AI language model" with no Google attribution suggests GPT-3.5 era (mid-2022 to mid-2024). "As a large language model trained by Google" suggests Bard era (February 2023 to February 2024). "I'm still learning, but..." suggests early Gemini era (February 2024 to end of 2024).

The era-tag determines which subset of the catalog to apply.

### Step 2: Select era-appropriate patterns

Based on the established era, select patterns whose "useful for analyzing content from" window includes the artifact's date.

For a 2023 article suspected of being Bard-assisted:
- Apply `A1-BARD-001` for the preamble pattern.
- Apply the Bard hallucination-rate fingerprint (91 percent citation hallucination rate measurement) for citation auditing.
- Apply `A1-GEMINI-019` ("I'm still learning, but...") if the article is later than February 2024 and shows Gemini Ultra / Gemini Pro 1.0 markers.
- Cross-reference against `A1-GPT-007` ("As an AI language model") if attribution is ambiguous between Bard and GPT-3.5.

For a 2021 raw-GPT-3 output:
- Apply `A1-GPT-HISTORICAL-001` for the pre-instruction-tuning baseline.
- Check for raw-web-corpus echoes via comparison against Common Crawl and Wikipedia (2019 snapshot).
- Note the absence of canonical RLHF artifacts (no "Great question!", no "I hope this helps") as a positive marker for the raw-base-model deployment.

For a 2024 self-hosted Llama 2 fine-tune output:
- Apply `A1-LLAMA-HISTORICAL-001` for the lower-RLHF baseline.
- Cross-reference against the active A1-LLAMA-001 (near-zero em-dash baseline) and A1-LLAMA-002 (sterile infrastructure tone) entries.
- Note that self-hosted fine-tunes often layered additional RLHF on the base Llama 2 model; check for inconsistency between base-model patterns and fine-tune-specific patterns.

### Step 3: Weight by base rate at the artifact's era

The B3 calibration data (in [calibration-tables.md](calibration-tables.md)) is year-stratified for historical patterns. An editor analyzing a 2023 article weights "As an AI language model" differently than the same phrase appearing in a 2026 article:

- 2023 base rate: 15 to 25 percent of all ChatGPT responses, much higher for opinion or identity prompts. Signal strength VERY HIGH.
- 2026 base rate: near zero in frontier output. Signal strength LOW for current frontier; HIGH if the phrase nonetheless appears (because it indicates either an older deployment or a parody construction).

The same surface pattern carries different signal weight at different eras. Always look up the era-specific base rate before weighting the signal.

### Step 4: Distinguish direct AI generation from quoted or parodied patterns

A current article may quote or parody a historical pattern without itself being AI-generated. For example, a 2026 essay about AI history might quote "As an AI language model, I cannot provide personal opinions" as an illustrative example of the early-ChatGPT preamble. This is not evidence the essay is AI-generated.

For each detected historical pattern, check whether it appears as direct generation (load-bearing voice, no quotation marks), as a quoted historical pattern (inside quotation marks or as a discussed example), or as parody or pastiche (stylistic imitation identifiable from surrounding context). Only direct generation scores as evidence.

### Step 5: Combine era-appropriate signals

A single historical pattern is rarely definitive on its own:

- Historical preamble + era-appropriate citation hallucination rate + era-appropriate vocabulary cluster = HIGH confidence
- Historical preamble alone, in an otherwise polished article = MEDIUM confidence
- Vocabulary cluster alone, without era-appropriate preamble = LOW to MEDIUM confidence (vocabulary clusters can be human-written)

The B2 combined-signal fingerprints (in [combined-signal-fingerprints.md](combined-signal-fingerprints.md)) provide the canonical combinations for each era. Use the era-specific subset.

### Step 6: Document the era-tagged forensic conclusion

Always tag forensic conclusions with the era window. A report that says "AI-generated content detected" without specifying the era is incomplete; the era determines which model family is the likely source and what remediation is appropriate.

Example report fragment:

> Article dated June 2023, attributed to Bard. Pattern analysis: `A1-BARD-001` preamble in response opener (HIGH signal for Bard era). Citation hallucination rate 7 of 8 cited sources fabricated or misattributed, consistent with the 91 percent Bard-era citation hallucination rate measurement (Walters and Wilder Sci Rep 2023). Combined assessment: HIGH confidence of Bard-assisted authorship without subsequent human verification of citations. Recommended action: full citation re-audit.

### Step 7: Avoid era confusion

Two anti-patterns to avoid:

- **Anachronistic detection.** Applying the 2026 active catalog to a 2023 Bard output and missing `A1-BARD-001` because Bard is not in the current frontier family list. Fix: check whether the artifact's era is covered by the active catalog or requires the historical catalog.
- **Forward-projection.** Reading "As an AI language model" in a 2026 article and labeling it AI-generated when the article is quoting the preamble as a discussed example. Fix: apply Step 4 before scoring.

The era-stratified catalog and the per-pattern "useful for analyzing content from" metadata are the tools that prevent both errors.

---

## Section 4: Cross-references and next steps

This file is one of several reference files for synthesis-content-quality v4.0. Related files:

- [SKILL.md](../SKILL.md) for the durable methodology, the confidence-tier system, and the entry point to the catalog.
- [detailed-criteria.md](detailed-criteria.md) for full descriptions of the active 42 criteria with refreshed 2025-2026 examples.
- [model-family-fingerprints.md](model-family-fingerprints.md) for the active A1 catalog by model family.
- [substance-and-depth.md](substance-and-depth.md) for the active A2 catalog on substance and depth detection.
- [combined-signal-fingerprints.md](combined-signal-fingerprints.md) for the active B2 catalog of combined-signal fingerprints, including era-stratified variants.
- [calibration-tables.md](calibration-tables.md) for the year-stratified B3 calibration data underlying the signal strengths and base rates referenced in this file.
- [bibliography.md](bibliography.md) for the consolidated source citations and verification status.

When a pattern in the active catalog moves to `Historical` or `Deprecated` status in a future v4.x revision, the pattern should be ported from its active-catalog location to this file with the era-of-prevalence metadata fully filled in. The active-catalog file is then updated to remove the pattern from the active section and to add a cross-reference pointing here. Patterns are never deleted from the catalog; they are retired.

The audit process that produced this file is documented in [historical-coverage-audit.md](https://github.com/synthesisengineering/synthesis-skills) in the upgrade project's resources/artifacts directory. The next audit cycle will check whether additional patterns from the current active catalog have moved to Declining or Historical status and should be ported to this file.

---

*Part of the [synthesis writing](https://synthesiswriting.org) craft. The writer writes, the AI assists, the catalog remembers.*
