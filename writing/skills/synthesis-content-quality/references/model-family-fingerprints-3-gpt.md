# Model-Family Fingerprints (A1), part 3 of 6

Part 3 of the file split from [model-family-fingerprints.md](model-family-fingerprints.md), which keeps the opening sections and lists every part. The text below is unchanged.

Contents:
- A1.2 OpenAI GPT family (A1-GPT-001 to A1-GPT-020, 18 entries)

## A1.2 OpenAI GPT family

Models in scope: GPT-4, GPT-4o, GPT-4.1, GPT-5, GPT-5.x, and the o-series reasoning models (o1, o3, o4-mini). Historical entries for pre-instruction-tuning GPT-3, GPT-3.5 "As an AI language model" preamble, and the GPT-3.5/4 "Here's the thing" colloquial intensifier live in [historical-patterns.md](historical-patterns.md). The GPT family has the broadest production-deployment footprint among current frontier families and the deepest published stylometric literature; the 2024 to 2026 detection research corpus is anchored substantially on GPT output.

### A1-GPT-001: "Delve" and the saturated AI vocabulary cluster

- **ID.** A1-GPT-001
- **Name.** "Delve" and the saturated AI vocabulary cluster
- **Description.** GPT family (especially GPT-3.5 and GPT-4 lineages) overproduces a specific cluster of focal words that Kobak et al. (2024) and Matsui et al. (2025) documented at Z-scores above 3.5 in 2024 PubMed corpora. The headline word is "delve" (most-cited example), but the cluster also includes "intricate", "intricately", "leverage", "tapestry", "pivotal", "underscore", "underscores", "underscoring", "in the realm of", "navigate the complexities of", and approximately 100 other focal words documented in Kobak's Science Advances 2025 paper. Per Perplexity's A1-GPT-003 "Landscape Vocabulary Set" the cluster also covers "landscape," "ecosystem," "dynamics," "paradigm," "framework," "solutions," "insights." Per Perplexity's A1-GPT-008 "Innovative and Robust Vocabulary Set" the cluster includes "innovative," "robust," "dynamic," "efficient," "transformative," "seamless," "impactful," "synergistic." ChatGPT's A3 review classifies the v3.1.0 criterion 33 (Saturated AI Vocabulary) as REVISE: keep the idea but refresh the lexicon by family and genre. The Claude expansion's A3 matrix promotes criterion 33 from MED to HIGH.
- **Concrete examples.**
  1. "Let us delve into the intricate dynamics of urban planning."
  2. "This study underscores the pivotal role of microbiota in human health."
  3. "We navigate the complexities of cross-disciplinary research to weave a tapestry of insights."
  4. (Per Perplexity) "The rapidly evolving landscape of AI presents both challenges and opportunities."
  5. (Per Perplexity) "Understanding the ecosystem of stakeholders is essential to effective change management."
  6. (Per Perplexity) "This paradigm shift requires new frameworks for thinking about innovation."
  7. (Per Perplexity) "An innovative approach to customer engagement that delivers robust results."
  8. (Per Perplexity) "The platform provides a seamless, dynamic user experience."
  9. (Per Perplexity) "A transformative solution that drives synergistic outcomes."
- **Location and register.** Universal across registers but densest in academic and explainer prose. Highest base rate in non-native English contexts and in technical/scientific writing. Per Perplexity: business writing, analysis, strategy documents for the landscape cluster; marketing, business, and technology writing for the innovative/robust cluster.
- **Model attribution.** GPT family (very high confidence for GPT-3.5 and GPT-4 lineages). Claude family produces some overlap but at lower density. Per Perplexity: GPT family highest for "landscape," "ecosystem," "paradigm"; Claude uses "realm" and "tapestry" instead; Gemini favors "context" and "considerations." Other frontier models inherit some focal words via shared training corpora but at significantly lower rates.
- **Time evolution.** Emerged sharply with ChatGPT public release in late 2022; peaked in GPT-3.5/4 era (2023 to mid-2024); persistent through GPT-4o; GPT-5 and GPT-5.1 reduced some specific focal words but the broader cluster remains. Perplexity: "Landscape" has been flagged as a GPT-specific tell since 2023; "Innovative/Robust" cluster consistent from GPT-3.5 through GPT-4o; slightly reduced in GPT-4.1.
- **Sources.** `[claude-exec-2026-05-18]`, `[verified-arxiv:2406.07016]` (Kobak et al. "Delving into LLM-assisted writing in biomedical publications through excess vocabulary", confirming 13.5 percent of 2024 biomedical abstracts processed with LLMs, with focal-word frequency anomalies as the detection method). Juzek and Ward COLING 2025 attributes the overrepresentation to RLHF reward shaping specifically. `[cross-validated:manus-ai]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`. Student Village 2024; Originality.ai 2025; "9 Words That Reveal ChatGPT," multiple sources.
- **Signal strength.** HIGH per Claude's tier-shift recommendation (was MEDIUM in v3.1.0 criterion 33, recommended PROMOTE to HIGH). Per Perplexity: MED per word; HIGH for cluster of three or more in 500 words.
- **Base rate (per-family).** Very high in unedited GPT output. Kobak documented 10 percent of 2024 PubMed abstracts using "delve" specifically (vs. baseline of about 0.5 percent in 2020). Saturated cluster appears in estimated 70 to 90 percent of GPT-family essay output.
- **Causal hypothesis (ranked).** Primary: RLHF reward shaping (per Juzek and Ward COLING 2025 specifically attributing "delve" to RLHF). Secondary: training-data skew toward academic corpora that overrepresent these words. Tertiary: feedback loops as LLM-influenced PubMed papers become training data for next-generation models.
- **Detection difficulty.** Easy. Word search with frequency thresholds.
- **False positive risk.** Moderate to high. Academic writers and ESL writers use some focal words at higher baseline rates. Per Liang et al. 2023, this is part of the ESL false-positive trap. The discriminator is density and combination with other markers.
- **Fix or remediation.** Replace each focal word with a more specific or simpler alternative ("examine" or "study" instead of "delve into"; "complex" or "complicated" instead of "intricate"; "use" or "apply" instead of "leverage"). Maintain content; cut the academic-register cosplay.
- **Era status.** Active. Some specific words (e.g., "tapestry") have declined; the broader cluster remains.
- **Zone tag.** BODY-PERSISTENT.

### A1-GPT-002: Sycophantic opener ("Great question!", "Certainly!", "Absolutely!")

- **ID.** A1-GPT-002
- **Name.** Sycophantic opener
- **Description.** GPT family responses, especially in dialogue, open with enthusiastic acknowledgment ("Great question!", "Excellent point!", "I love this question!") and proceed with an instructive cadence that frames the response as teaching. Per `[perplexity]`'s A1-GPT-001 "Sycophantic Opener," GPT-4o and earlier GPT models open assistant responses with affirmative interjections that acknowledge the request before addressing it: "Certainly!", "Absolutely!", "Great question!", "Of course!", "I'd be happy to help with that." The cadence often includes "Let's break this down" or "Here's what's happening" early in the response. Gemini's A1-GPT-001 "Pseudo-Empathetic Affirmation" captures the related "I completely understand your concern" variant. DeepSeek's A1-GPT-003 catalogs "Certainly!" / "Of course!" as extremely common GPT openers.
- **Concrete examples.**
  1. "Great question! Let's break this down step by step..."
  2. "Excellent point! Here's what's happening under the hood..."
  3. "I love this question! There are actually several layers to consider..."
  4. (Per Perplexity) "Certainly! Here's a breakdown of the key considerations..."
  5. (Per Perplexity) "Absolutely, that's a great approach. Let me walk you through..."
  6. (Per Perplexity) "Of course! I'd be happy to help you draft that email."
  7. (Per Gemini) "I completely understand your concern regarding the sudden latency spike."
  8. (Per Gemini) "That is an incredibly sharp observation about the fragile supply chain dynamics."
  9. (Per Gemini) "I am right here to help you navigate this complex, multi-tiered architecture."
- **Location and register.** Response openers in dialogue; pedagogical and explainer registers. Perplexity: Response openers in conversational and assistant contexts. Gemini: First sentence of responses, particularly following user corrections or error reports.
- **Model attribution.** GPT family (very high confidence). The specific "Great question!" reflex was the signature ChatGPT tell from 2023 onward. OpenAI's April 2025 sycophancy rollback reduced the rate but the pattern persists. Claude has a similar but distinct reflex ("You're absolutely right!" per A1-CLAUDE-003). Per Perplexity: GPT-4o (highest); present but reduced in GPT-4.1 and later. Not characteristic of Claude 4, Gemini, or Llama 4. Effectively faded in GPT-5. Per Gemini: OpenAI GPT-5.4 (High), GPT-5.5 (Medium); escalated significantly in GPT-4o voice-optimized training.
- **Time evolution.** Emerged with ChatGPT launch; high density through 2023-2024; partial reduction after April 2025 sycophancy rollback; remains present in 2026. Strong in GPT-3.5 through GPT-4o per Perplexity. Measurably reduced in GPT-4.1 and o-series. Effectively faded in GPT-5.
- **Sources.** `[claude-exec-2026-05-18]`, `[verified-arxiv:2310.13548]` (Sharma et al. sycophancy in five production assistants confirms sycophancy as a structural feature of RLHF-trained models). `[cross-validated:perplexity]`, `[cross-validated:manus-ai]`, `[cross-validated:deepseek]`, `[cross-validated:gemini]`. Student Village forum catalog 2024; LinkedIn practitioner lists 2025; Originality.ai 2025.
- **Signal strength.** HIGH for the explicit opener; MEDIUM for the broader instructive cadence. Per Perplexity: HIGH (strong family signal; Claude and Gemini do not produce this at comparable rates). Per Gemini: 88 percent confidence for pseudo-empathetic affirmation specifically.
- **Base rate (per-family).** High in unedited GPT dialogue (estimated 30 to 50 percent of multi-turn responses opened with "Great question!" or variant before the April 2025 rollback; estimated 15 to 25 percent after). Per Perplexity: HIGH in GPT-4o; LOW in GPT-5. Per Gemini: 312 occurrences per 1,000 conversational turns (VTI-derived figure, single-LLM-sourced, unverified at merge time).
- **Causal hypothesis (ranked).** Primary: RLHF helpfulness optimization. Secondary: human preference data favoring warm openers. Tertiary: system-prompt artifacts in OpenAI's personality v2 tuning. Gemini adds: chat-format conversational tuning prioritizing simulated human connection.
- **Detection difficulty.** Easy. Exact phrase.
- **False positive risk.** Low. Per Perplexity: LOW. Human writers do not typically open paragraphs or responses with "Certainly!" in professional writing.
- **Fix or remediation.** Strip the opener. Start with substance.
- **Era status.** Active but Declining (post April 2025 rollback).
- **Zone tag.** WRAPPER-OPENER.

### A1-GPT-003: Section-ending summary sentence

- **ID.** A1-GPT-003
- **Name.** Section-ending summary sentence
- **Description.** GPT, particularly 4o, ends each section of a multi-section response with a sentence that summarizes what the section just argued. This is sibling to A1-CLAUDE-007 but more pronounced in GPT.
- **Concrete examples.**
  1. (After a section on database choices) "In summary, choose Postgres if you need ACID compliance and SQL; choose Redis if you need low-latency in-memory access."
  2. (After a section on testing strategies) "These three testing approaches together provide comprehensive coverage."
  3. (After a section on architecture) "The architecture decisions above set the foundation for the implementation choices we'll cover next."
- **Location and register.** Mid-document section closers.
- **Model attribution.** GPT family (high confidence, especially 4o). Claude produces similar but less mechanically; Gemini variable.
- **Time evolution.** Stable across GPT versions through GPT-5.1.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:manus-ai]`, `[cross-validated:perplexity]`.
- **Signal strength.** HIGH in combination with bolded lead-ins and saturated vocabulary; MEDIUM standalone.
- **Base rate (per-family).** High in unedited GPT 4o long-form (estimated 70 to 85 percent of multi-section responses).
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling for clear structure. Secondary: training-data skew toward academic and tutorial prose where section recaps are common.
- **Detection difficulty.** Easy.
- **False positive risk.** Low to moderate.
- **Fix or remediation.** Cut the recap. The reader just read the section.
- **Era status.** Active.
- **Zone tag.** MID-BODY-INSERT for mid-document section closers; WRAPPER-CLOSER for the final response closer. Practically: HYBRID with mid-body bias.

### A1-GPT-004: "It's not just X, it's Y" construction

- **ID.** A1-GPT-004
- **Name.** "It's not just X, it's Y" construction
- **Description.** GPT uses a specific rhetorical move: stating that something is not merely the surface understanding but is actually something deeper or more significant. The construction often runs "It's not just X, it's Y" or "This isn't simply X, it's Y." The framing inflates significance and is a tell of the pseudo-profundity register. Closely related to v3.1.0 criterion 5 "Negative Parallelism" (the "not X but Y" construction); Manus AI catalog keeps criterion 5 as is, ChatGPT's review classifies it as DEMOTE (still real, but weaker as a standalone tell), and the Claude expansion promotes it from MED to HIGH on the grounds that "preference data directly reinforces antithesis."
- **Concrete examples.**
  1. "It's not just a tool, it's a paradigm shift in how we think about workflow automation."
  2. "This isn't simply about cost savings; it's about reimagining the entire customer experience."
  3. "The migration isn't just a technical change, it's an organizational transformation."
- **Location and register.** Body paragraphs, especially in marketing, business, and motivational registers.
- **Model attribution.** GPT family (very high confidence, especially 4 and 4o). Claude produces similar constructions but less mechanically. Marketing-tuned LLM products amplify this further.
- **Time evolution.** Present from GPT-3.5 forward; high density through 4o; partially reduced in GPT-5.1 personality update but still present.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:perplexity]`, `[cross-validated:manus-ai]`. Pennycook et al. BSRS provides the pseudo-profundity framework.
- **Signal strength.** HIGH especially in marketing register; MEDIUM in analytical register.
- **Base rate (per-family).** High in marketing and motivational GPT output (estimated 40 to 60 percent of responses to "explain the impact of X" prompts).
- **Causal hypothesis (ranked).** Primary: training-data skew toward marketing and motivational corpora. Secondary: RLHF reward modeling that may favor "elevated" framings.
- **Detection difficulty.** Easy. Construction is searchable.
- **False positive risk.** Moderate. Skilled essayists and op-ed writers use this construction; the discriminator is density.
- **Fix or remediation.** State what the thing actually is and what it does. Skip the elevation.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT (Active GPT focal cluster).

### A1-GPT-005: "While X, it's also worth noting Y" balanced framing

- **ID.** A1-GPT-005
- **Name.** "While X, it's also worth noting Y" balanced framing
- **Description.** GPT family uses balanced framings similar to A1-CLAUDE-002 but with a different connective pattern. The construction often runs "While X, it's also worth noting that Y" or "On the surface X, but in reality Y." The function is similar: hedge by presenting multiple perspectives. Perplexity's A1-GPT-012 "Hedge-Then-Assert Structure" captures the related pattern: GPT structures arguments as acknowledge complexity, hedge, then assert the claim that was hedged. The structure produces the appearance of nuance while delivering the same conclusion the unhedged version would have.
- **Concrete examples.**
  1. "While the data suggests improvement, it's worth noting that the sample size is small."
  2. "On the surface, this looks like a clear win. But there are several caveats worth considering."
  3. "Although the approach has merit, we should also acknowledge some limitations."
  4. (Per Perplexity) "While the evidence is not conclusive, and experts disagree on several key points, most studies suggest that X is the better approach."
  5. (Per Perplexity) "It's difficult to generalize across all situations, but in the majority of cases, Y tends to produce better outcomes."
- **Location and register.** Body paragraphs, analytical registers.
- **Model attribution.** GPT family (high confidence). Claude uses the explicit "on the one hand / on the other hand" form more often. Both families produce subtler "While X" framings. Perplexity: GPT-4o and Claude (both high); Gemini less so.
- **Time evolution.** Stable across GPT versions.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:perplexity]`, `[cross-validated:manus-ai]`, `[cross-validated:deepseek]`. BlogPros 2026 per Perplexity.
- **Signal strength.** MEDIUM standalone; HIGH in combination with other GPT markers.
- **Base rate (per-family).** High in analytical GPT output (estimated 50 to 70 percent of long analytical responses contain at least one instance).
- **Causal hypothesis (ranked).** Primary: RLHF reward shaping for nuanced presentation. Secondary: training-data skew toward academic argument structures.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate. Academic writers use this construction.
- **Fix or remediation.** Take a position. If both sides genuinely need representation, articulate the tension with concrete consequences.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

(A1-GPT-006 and A1-GPT-007 are Historical-era patterns. Their entries live in [historical-patterns.md](historical-patterns.md). A1-GPT-006 is the "Here's the thing" / "The thing is" colloquial intensifier from GPT-3.5 and early GPT-4. A1-GPT-007 is the "As an AI language model" preamble. Cross-references are preserved in the historical file. They are not repeated here because the era status filter for this file is Active or Declining only.)

### A1-GPT-008: Numbered-list scaffolding and listicle-default mode

- **ID.** A1-GPT-008
- **Name.** Numbered-list scaffolding and listicle-default mode
- **Description.** GPT family, especially 4o, structures responses as numbered lists even when the content does not benefit from enumeration. Per Perplexity's A1-GPT-013 "Listicle-Default Mode," GPT converts prose questions into bullet-pointed or numbered lists even when the question calls for reasoning, narrative, or analysis. The list format delivers parallel surface structure but bypasses causal reasoning. Gemini's A1-GPT-003 "Tripartite Markdown Transition" frames the related pattern: a rigid transition mechanism where the model signals an upcoming list using a colon, invariably followed by exactly three bullet points or numbered items. DeepSeek's A1-GPT-004 captures "Structured Numbered Lists with Bold Headers" (the "1. Header: Explanation" format).
- **Concrete examples.**
  1. Best seen in aggregate. Compare any GPT-4o response to "What should I think about when choosing X?" (almost always a numbered list of 3 to 7 items) to how a human would naturally answer (often prose with maybe one or two embedded examples).
  2. (Per Perplexity, asked "Why did the Roman Empire fall?") "**Reasons the Roman Empire Fell:** 1. Military overextension. 2. Economic difficulties. 3. Political instability. 4. External pressures."
  3. (Per Gemini) "This cloud architecture introduces three critical vulnerabilities:"
  4. (Per Gemini) "To mitigate this systemic risk, consider the following primary strategies:"
  5. (Per Gemini) "The financial data suggests several converging factors:"
- **Location and register.** Body of responses; pedagogical and decision-support registers. Per Gemini: mid-body transitions, analytical reports, and executive summaries.
- **Model attribution.** GPT family (very high confidence, especially 4o). Claude does this less by default but more with explicit prompting. Per Gemini: OpenAI GPT-5.5 (High), OpenAI o3 (Medium); a durable artifact of GPT structuring since GPT-3.5, persisting through the o-series reasoning models due to fundamental training data distributions.
- **Time evolution.** Emerged with GPT-3.5; high density through 4 and 4o; persistent in 5.1.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:manus-ai]`, `[cross-validated:perplexity]`, `[cross-validated:gemini]`, `[cross-validated:deepseek]`.
- **Signal strength.** MEDIUM standalone; HIGH in combination with bolded lead-ins. Per Gemini: 60 percent confidence for the tripartite-list variant specifically.
- **Base rate (per-family).** Very high in GPT-4o decision-support output (estimated 75 to 90 percent of responses to "what should I consider..." prompts). Per Gemini: found in 70 percent of instructional and analytical responses for the three-item-list variant.
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling for "structured" output. Secondary: training-data skew toward how-to and tutorial corpora. Gemini adds: system prompt artifacts prioritizing readability; markdown-saturated training data enforcing rigid structural rhythms.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate. Genuine list content warrants list structure. Per Gemini: HIGH (standard business writing relies heavily on tripartite lists).
- **Fix or remediation.** Use prose for prose-shaped content; reserve enumeration for genuinely parallel items. Per Gemini: convert the bullet points into a continuous narrative paragraph or manually alter the item count to break the predictable rhythm.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GPT-009: "In conclusion" / "To wrap up" final closer

- **ID.** A1-GPT-009
- **Name.** "In conclusion" / "To wrap up" final closer
- **Description.** GPT family closes long-form responses with an explicit "In conclusion," "To wrap up," "In summary," or "To recap" lead-in to the final paragraph. The closer signals the end of the response in a way that fluent writers avoid. Maps to v3.1.0 criterion 7 (Section-Ending Summaries).
- **Concrete examples.**
  1. "In conclusion, the migration is worth doing, with the caveats noted above."
  2. "To wrap up, the three main considerations are cost, performance, and team capacity."
  3. "In summary, this approach offers significant benefits but requires careful planning."
- **Location and register.** Final response paragraph; universal across registers but densest in academic and analytical prose.
- **Model attribution.** GPT family (high confidence). Claude produces similar closers but uses "Overall," or "Taken together," more often. Gemini variable.
- **Time evolution.** Stable across GPT versions.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:manus-ai]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Very high in GPT long-form output (estimated 60 to 80 percent of multi-paragraph responses).
- **Causal hypothesis (ranked).** Primary: training-data skew toward academic conventions (the five-paragraph essay structure with explicit conclusion lead-in). Secondary: RLHF reward modeling that may reward "clear structure."
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate. Academic writers use these closers.
- **Fix or remediation.** End on substance. If a recap is genuinely warranted, lead with the substantive conclusion, not the structural signal "in conclusion."
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER.

### A1-GPT-010: "It's important to remember" / "Keep in mind" reminders

- **ID.** A1-GPT-010
- **Name.** "It's important to remember" / "Keep in mind" reminders
- **Description.** GPT family inserts mid-response reminders that the reader should "remember" or "keep in mind" some qualifier. The reminders are an alignment-trained safety release similar to A1-CLAUDE-001 but framed as reminders rather than notes. Per DeepSeek's A1-GPT-006 ("It's important to remember that..."), a GPT variant of the cautionary preamble.
- **Concrete examples.**
  1. "It's important to remember that this advice depends on your specific situation."
  2. "Keep in mind that these performance numbers were measured on a particular hardware configuration."
  3. "Remember that the underlying assumptions may not hold for all use cases."
- **Location and register.** Mid-response qualifying inserts; universal across analytical and advisory registers.
- **Model attribution.** GPT family (high confidence). Claude has the "It is important to note" sibling (A1-CLAUDE-001).
- **Time evolution.** Stable across GPT versions.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:perplexity]`, `[cross-validated:manus-ai]`, `[cross-validated:deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** High in analytical and advisory GPT output (estimated 35 to 55 percent of long responses).
- **Causal hypothesis (ranked).** Primary: RLHF safety tuning. Secondary: refusal-avoidance behavior. Tertiary: training-data skew toward documentation and explainer prose.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate. The phrasing is common in tutorial writing.
- **Fix or remediation.** Cut. If the qualifier is genuinely important, embed in the main clause.
- **Era status.** Active.
- **Zone tag.** MID-BODY-INSERT.

### A1-GPT-011: Hallucinated citations and DOIs (style fingerprint)

- **ID.** A1-GPT-011
- **Name.** Hallucinated citations and DOIs (style fingerprint, mechanism in bucket C)
- **Description.** GPT family fabricates plausible-looking citations: author names, journal titles, DOIs, page numbers. The fabrications follow real bibliographic conventions (correct author/year structure, plausible journal acronyms, well-formed DOI prefixes). This is the stylistic fingerprint that signals possible fabrication. The detection mechanism and remediation protocol live in bucket C (synthesis-fact-checking). Maps to v3.1.0 criterion 23 (Hallucinated Citations) and criterion 21 (Citation Abnormalities).
- **Concrete examples.**
  1. "(Smith et al., 2019)" appearing in a response where Smith et al. 2019 with that finding does not exist.
  2. "doi:10.1038/s41586-023-01234-5" formatted correctly but resolving to a different paper or to nothing.
  3. "Journal of Computational Linguistics, vol. 45, no. 3, pp. 234-256" with the right format but the wrong content.
- **Location and register.** Citations within analytical, academic, and explainer prose.
- **Model attribution.** GPT family (very high confidence, especially 3.5 and 4 first generation). Claude family produces hallucinated citations too, with a notable variant: Claude over-produces plausible-seeming DOIs specifically. Gemini drifts to vague "studies show" assertions without identifiers (see A1-GEMINI-002). All families exhibit this; the pattern is structural to autoregressive generation.
- **Time evolution.** Present from GPT-3 forward; very high density in 3.5/4; reduced but not eliminated in 4o; reduced further with RAG-augmented deployments. Per Stanford RegLab measurements, legal-AI with RAG still hallucinates citations at 17 to 33 percent. Damien Charlotin's database now contains over 1,455 sanctioned legal cases involving AI-fabricated citations as of 2025 per Claude exec.
- **Sources.** `[claude-exec-2026-05-18]`, `[opus-expansion]` for the family-specific variants. Buchanan, Hill, and Shapoval (Sage 2024) measured hallucinated citation rates across multiple LLMs. Walters and Wilder (Scientific Reports 2023) measured the GPT-3.5/4 baseline. Chelli et al. (JMIR 2024) measured a 56 percent error rate among GPT-4o citations. `[cross-validated:perplexity]`, `[cross-validated:deepseek]`. ChatGPT's review classifies criteria 23 (Hallucinated Citations) as PROMOTE; the Claude expansion concurs.
- **Signal strength.** VERY HIGH per Claude's tier-shift recommendation (was MEDIUM for criteria 21 and 23 in v3.1.0; recommended PROMOTE both to HIGH).
- **Base rate (per-family).** Per family: GPT-3.5 30 to 55 percent of citations hallucinated (Walters and Wilder); GPT-4 18 to 29 percent; GPT-4o approximately 20 percent with 56 percent of those containing errors per Chelli; Claude 3.7 15 to 20 percent; Bard 91 percent (early measurement).
- **Causal hypothesis (ranked).** Primary: tokenizer and architecture effects (autoregressive token-by-token generation produces plausible bibliographic strings without verification). Secondary: training-data skew toward bibliographic corpora that the model has memorized at a surface level. Tertiary: helpfulness optimization that drives the model to produce a citation even when no real citation supports the claim.
- **Detection difficulty.** Hard for the citation existing; easy for the bibliographic style fingerprint (the way the citation is constructed and inserted).
- **False positive risk.** Low for the existence check (real citations exist or do not). Moderate for the style fingerprint (real writers also use bibliographic conventions).
- **Fix or remediation.** Verify every citation before publication. Use citation-management tools that cross-check existence. For known-bad LLM outputs, remove the citation and the claim it supports, then re-source the claim.
- **Era status.** Active. Improving slowly with RAG augmentation but far from solved.
- **Zone tag.** BODY-PERSISTENT.

### A1-GPT-012: Markdown formatting in plain-text contexts

- **ID.** A1-GPT-012
- **Name.** Markdown formatting in plain-text contexts
- **Description.** GPT family generates markdown formatting (asterisks for bold, hyphens for bullets, hashes for headers) in contexts where the rendering target is plain text (e.g., terminal output, plain-text email). The formatting leaks through and is visible as literal markdown characters rather than rendered formatting. Perplexity's A1-GPT-002 "Comprehensive Structure Header Cascade" frames the related pattern: GPT-4o defaults to markdown headers (##, ###) even in contexts where plain prose would serve better. Perplexity's A1-GPT-006 "Bold-Text Emphasis Cascade" captures the bolding density. Maps to v3.1.0 criterion 15 (Markdown Formatting Mixed with Standard Text).
- **Concrete examples.**
  1. (In a plain-text email reply) "**Important**: Please confirm receipt by EOD."
  2. (In a terminal output) "## Next Steps\n- Update the schema\n- Run the migration"
  3. (In a plain-text Slack DM that does not render markdown for that channel) "*This is intended as emphasis but renders as literal asterisks.*"
  4. (Per Perplexity) A 200-word email response formatted as: "## Overview\n## Key Points\n## Next Steps"
  5. (Per Perplexity) A creative writing prompt response that includes "## Narrative Arc\n## Character Development"
  6. (Per Perplexity) "**Machine learning** models rely on **large datasets** to produce **accurate predictions** through **iterative training**."
- **Location and register.** Plain-text channels; chat interfaces with limited rendering; terminal outputs.
- **Model attribution.** GPT family (high confidence). Gemini family has a notably stronger version of this pattern, near-deterministic per GitHub gemini-cli #8392 (per Claude's exec summary; not independently verified at expansion time). Claude family also produces it but at lower density.
- **Time evolution.** Persistent across GPT versions; partial mitigation via system-prompt instructions. Strong in GPT-4o; reducing in GPT-4.1 and GPT-5 for the bold-text emphasis specifically per Perplexity.
- **Sources.** `[claude-exec-2026-05-18]` (notes Gemini's plain-text markdown leakage as a near-deterministic signal). `[cross-validated:perplexity]`, `[cross-validated:gemini]`. `[opus-expansion]` for the GPT-specific variant.
- **Signal strength.** HIGH for Gemini in non-rendering channels; MEDIUM for GPT.
- **Base rate (per-family).** High when system-prompt does not include explicit "plain text only" instruction.
- **Causal hypothesis (ranked).** Primary: training-data skew toward markdown-rich corpora (GitHub, Stack Overflow, documentation). Secondary: RLHF reward modeling that may reward "structured" formatting. Tertiary: tokenizer effects (markdown characters are cheap single tokens).
- **Detection difficulty.** Easy. Unicode/character search for leftover markdown.
- **False positive risk.** Low.
- **Fix or remediation.** Strip the markdown. If rendering is desired, fix the channel. If plain text is desired, instruct the model accordingly.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GPT-013: o-series conclusion recapitulation

- **ID.** A1-GPT-013
- **Name.** o-series conclusion recapitulation
- **Description.** Per `[perplexity]`'s A1-GPT-004, OpenAI o1, o3, and o4-mini produce a distinctive structural artifact: after a reasoning-heavy body, the final paragraphs number and restate each conclusion, often as "1. X. 2. Y. 3. Z." The pattern is a surface trace of chain-of-thought reasoning that bleeds into the visible output.
- **Concrete examples.**
  1. "In summary: 1. The primary cause is resource contention. 2. The secondary effect is latency increase. 3. The recommended mitigation is sharding."
  2. "To recap the key points: First, [X]. Second, [Y]. Third, [Z]."
  3. "Conclusions: 1) System overload from peak load. 2) Insufficient buffer capacity. 3) Cascading failure pattern."
- **Location and register.** Closing paragraphs; technical analysis; any context involving extended reasoning.
- **Model attribution.** o-series exclusively. Not observed in GPT-4o, Claude, or Gemini at comparable rates.
- **Time evolution.** Introduced with o1 (September 2024). Present through o4-mini (May 2026).
- **Sources.** Hacker News thread on o1 (2024); generative-ai-newsroom.com analysis; practitioner documentation per Perplexity. `[cross-validated:deepseek]` for the related "o-Series Chain-of-Thought Artifacts."
- **Signal strength.** HIGH (family-unique).
- **Base rate (per-family).** MED in technical contexts; LOW in creative contexts.
- **Causal hypothesis (ranked).** Chain-of-thought training creates numbered-step reward shaping; the summarization move at the end mirrors the "verify your reasoning" pattern in training data.
- **Detection difficulty.** Easy.
- **False positive risk.** LOW. Human technical writers may enumerate conclusions but not with this specific regularity.
- **Fix or remediation.** Rewrite conclusion as prose that advances the argument rather than restating it.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER (o-series).

### A1-GPT-014: Uncertainty framing in reasoning traces (o-series)

- **ID.** A1-GPT-014
- **Name.** Uncertainty framing in reasoning traces (o-series)
- **Description.** Per `[perplexity]`'s A1-GPT-005, o-series models produce visible hedging within reasoning that bleeds into outputs: "I should note that," "It's important to acknowledge," "There's some uncertainty here about." The hedges are calibrated to the reasoning process, not the output, and create an overly hedged surface text.
- **Concrete examples.**
  1. "I should note that the specific figure may have changed since my training cutoff."
  2. "It's important to acknowledge that this analysis assumes stable market conditions."
  3. "There's some uncertainty about the exact mechanism, but the general pattern holds."
- **Location and register.** Analysis and explanation; appears throughout rather than only at uncertain claims.
- **Model attribution.** o-series; also present in Claude 3.5+ (different phrasing: "I'm not certain but...").
- **Time evolution.** Introduced with o1; persists.
- **Sources.** OpenAI blog on o1 reasoning; Hacker News practitioner discussion per Perplexity.
- **Signal strength.** MED alone.
- **Base rate (per-family).** MED.
- **Causal hypothesis (ranked).** RLHF reward for epistemic calibration; reasoning models trained to surface uncertainty.
- **Detection difficulty.** Medium.
- **False positive risk.** Medium. Careful human writers do flag genuine uncertainty.
- **Fix or remediation.** Keep uncertainty flags for genuinely uncertain claims; remove hedges on established facts.
- **Era status.** Active.
- **Zone tag.** MID-BODY-INSERT.

### A1-GPT-015: Caveat paragraph appended at end

- **ID.** A1-GPT-015
- **Name.** Caveat paragraph appended at end
- **Description.** Per `[perplexity]`'s A1-GPT-007, GPT-4o appends a disclaimer or caveat paragraph after the substantive content, covering topics like "consult a professional," "this does not constitute advice," or "your situation may differ." The paragraph appears even when the content is entirely factual and no professional consultation is warranted. The Manus AI catalog assigns this to v3.1.0 criterion 22 as REVISE; the Claude expansion's A3 matrix lists it as still valid with refresh.
- **Concrete examples.**
  1. (After a recipe) "Please note that nutritional values may vary based on specific ingredients and preparation methods. Consult a registered dietitian for personalized advice."
  2. (After a code example) "This example is for illustrative purposes only. Always test code in a staging environment before deploying to production."
  3. (After a general explanation) "Please note that this is a general overview. Specific situations may vary, and professional consultation is recommended for any consequential decisions."
- **Location and register.** Response closers; all genres.
- **Model attribution.** GPT-4o (highest); present in Claude with different phrasing; reduced in GPT-4.1.
- **Time evolution.** Strong in GPT-3.5 and GPT-4; reducing in later models.
- **Sources.** Practitioner observation; refusal-avoidance alignment documentation per Perplexity.
- **Signal strength.** MED.
- **Base rate (per-family).** HIGH in GPT-4o; MED in GPT-4.1+.
- **Causal hypothesis (ranked).** Alignment and safety tuning; refusal-avoidance behavior that appends disclaimers rather than refusing.
- **Detection difficulty.** Easy.
- **False positive risk.** Low. Human writers may add disclaimers but not with this formulaic consistency.
- **Fix or remediation.** Delete if content is factual. Keep only if the specific context genuinely requires professional consultation.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER.

### A1-GPT-016: Transition word cascade

- **ID.** A1-GPT-016
- **Name.** Transition word cascade
- **Description.** Per `[perplexity]`'s A1-GPT-009, GPT prose deploys formal transition words at a frequency that exceeds normal editorial practice: "Furthermore," "Moreover," "Additionally," "Consequently," "Notably," "Importantly," "Undoubtedly," "Nevertheless," "Notwithstanding." The words appear at the start of paragraphs and sentences that would flow naturally without them. Maps to v3.1.0 criterion 6 (Overuse of Transition Words). DeepSeek's A1-GPT-010 captures the "Additionally," / "Furthermore," sentence-initial pattern. The Claude expansion promotes criterion 6 from LOW to MED.
- **Concrete examples.**
  1. "Furthermore, the data suggests that early intervention is more cost-effective. Moreover, the long-term outcomes are measurably better."
  2. "Additionally, it is worth noting that the trend is accelerating. Consequently, businesses must act now."
  3. "Notably, the third option offers a balance. Importantly, this balance does not come without trade-offs."
- **Location and register.** All argumentative and analytical prose.
- **Model attribution.** GPT family (highest); present in all LLMs at elevated rates vs. human writing.
- **Time evolution.** Consistent. ChatGPT A3 review: DEMOTE (frontier models improved here; treat as low-value unless paired with uniform structure and section-ending summaries).
- **Sources.** Student Village 2024; Originality.ai 2025 per Perplexity.
- **Signal strength.** MED per word; HIGH for density (three or more per 300 words).
- **Base rate (per-family).** HIGH.
- **Causal hypothesis (ranked).** Primary: training data skew toward academic writing where formal transitions are conventionally required. Secondary: RLHF reward for "logical flow."
- **Detection difficulty.** Easy.
- **False positive risk.** Medium. Academic writers legitimately use these.
- **Fix or remediation.** Read each transition aloud and ask whether it adds meaning. "Furthermore" typically does not.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GPT-017: "I'd Be Happy To" service register

- **ID.** A1-GPT-017
- **Name.** "I'd Be Happy To" service register
- **Description.** Per `[perplexity]`'s A1-GPT-010, GPT models phrase willingness to help using customer-service register: "I'd be happy to," "I'd be glad to," "Feel free to ask," "Don't hesitate to reach out." The phrasing persists into technical and professional contexts where it is tonally incongruous. Maps to v3.1.0 criterion 36 (The Concierge Tone).
- **Concrete examples.**
  1. "I'd be happy to help you draft that legal brief."
  2. "Feel free to ask if you'd like me to expand on any of these points."
  3. "Don't hesitate to reach out if you have further questions about the API."
- **Location and register.** Response closers; assistant contexts.
- **Model attribution.** GPT-4o (highest); present in Claude less frequently; effectively absent from Gemini.
- **Time evolution.** Strong in GPT-3.5 and GPT-4o; reduced in GPT-4.1.
- **Sources.** LinkedIn practitioner lists; Originality.ai 2025 per Perplexity.
- **Signal strength.** HIGH (family-specific phrasing).
- **Base rate (per-family).** HIGH in GPT-4o; MED in GPT-4.1.
- **Causal hypothesis (ranked).** RLHF reward for helpfulness; annotators rate service-register as "helpful."
- **Detection difficulty.** Easy.
- **False positive risk.** LOW. Human professional writers rarely use this phrasing in documents.
- **Fix or remediation.** Delete. If a next-step offer is warranted, write it specifically: "I can also draft the follow-up email if you want."
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER.

### A1-GPT-018: Artificial enthusiasm markers

- **ID.** A1-GPT-018
- **Name.** Artificial enthusiasm markers
- **Description.** Per `[perplexity]`'s A1-GPT-011, GPT-4o produces enthusiasm about tasks and topics at a rate that doesn't correlate with the actual interest level of the content. "Great question!" appears before mundane prompts. "Fascinating!" appears before routine requests. Trending toward historical as of May 2026 per Perplexity. Maps to v3.1.0 criterion 36 (The Concierge Tone).
- **Concrete examples.**
  1. "Great question! The difference between TCP and UDP is..."
  2. "What a fascinating topic! Depreciation accounting works as follows..."
  3. "Excellent! Here is the JSON schema you requested..."
- **Location and register.** Response openers in conversational contexts.
- **Model attribution.** GPT-4o (highest); effectively trained out of GPT-5.
- **Time evolution.** Strong in GPT-4o; reduced in GPT-4.1; largely absent in GPT-5.
- **Sources.** LinkedIn practitioner lists 2025; practitioner community observation per Perplexity.
- **Signal strength.** HIGH (when present it is strongly indicative).
- **Base rate (per-family).** HIGH in GPT-4o; LOW in GPT-5.
- **Causal hypothesis (ranked).** RLHF reward for perceived engagement.
- **Detection difficulty.** Easy.
- **False positive risk.** LOW.
- **Fix or remediation.** Delete.
- **Era status.** Declining toward Historical.
- **Zone tag.** WRAPPER-OPENER.

### A1-GPT-019: Enthusiastic sign-offs

- **ID.** A1-GPT-019
- **Name.** Enthusiastic sign-offs
- **Description.** Per `[deepseek]`'s A1-GPT-002, GPT ends many responses with a cheerful, customer-service style closer ("I hope this helps!", "Let me know if you need anything else!"). Claude is more formal; Grok casual; Llama similar but less effusive. GPT-5 still does it.
- **Concrete examples.**
  1. "I hope this helps! Let me know if you need anything else."
  2. "Feel free to ask if you have more questions about this approach!"
  3. "Glad to help. Reach out anytime if you need clarification!"
- **Location and register.** Response closers.
- **Model attribution.** GPT family (high). Claude has the "I hope this helps" variant per A1-CLAUDE-011.
- **Time evolution.** Consistent through GPT-5.
- **Sources.** `[deepseek]`.
- **Signal strength.** HIGH.
- **Base rate (per-family).** Very high in unedited GPT dialogue.
- **Causal hypothesis (ranked).** RLHF helpfulness optimization; service-register annotation incentives.
- **Detection difficulty.** Easy.
- **False positive risk.** Low to moderate (customer service writing legitimately uses these).
- **Fix or remediation.** Strip the closer.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER.

### A1-GPT-020: "Game-changer" and buzzword overuse

- **ID.** A1-GPT-020
- **Name.** "Game-changer" and buzzword overuse
- **Description.** Per `[deepseek]`'s A1-GPT-008, GPT-4o and GPT-5 sometimes adopt a breathless marketing tone, describing features as "a game-changer" or "revolutionary." Distinct from Claude's cautious language. Maps to v3.1.0 criterion 28 (Hyperbolic Subheadings and Section Titles) and criterion 1 (Undue Emphasis on Importance and Symbolism).
- **Concrete examples.**
  1. "This is a game-changer for the industry."
  2. "A revolutionary approach to data management."
  3. "Truly groundbreaking work in the field of distributed systems."
- **Location and register.** Marketing, business, and product writing.
- **Model attribution.** GPT-4o and GPT-5 (both).
- **Time evolution.** Stable across GPT versions.
- **Sources.** `[deepseek]`.
- **Signal strength.** LOW but pattern helps family ID.
- **Base rate (per-family).** Moderate in marketing-register outputs.
- **Causal hypothesis (ranked).** Training data skew toward marketing and PR corpora.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate (marketing writers use these terms).
- **Fix or remediation.** Replace with specific descriptions of what makes the thing notable. "Game-changer" becomes "reduces costs by 40 percent" or "eliminates the manual reconciliation step."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---
