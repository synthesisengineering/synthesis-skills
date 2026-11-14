# Historical Patterns Reference, part 1 of 2

Part 1 of the file split from [historical-patterns.md](historical-patterns.md), which keeps the opening sections and lists every part. The text below is unchanged.

Contents:
- Section 1: Patterns retained from v3.1.0 with Historical or Deprecated status (A1-GPT-007, A1-GPT-006, A1-GPT-018, A1-GPT-021, A1-GEMINI-019, A1-CLAUDE-006)

## Section 1: Patterns retained from v3.1.0 with Historical or Deprecated status

These entries were `Active` in v3.1.0 of synthesis-content-quality. In v4.0 they move to `Historical` or `Deprecated` based on measured base-rate decline in current frontier models. They are retained per the compounding-archive principle.

### A1-GPT-007: "As an AI language model" preamble

- **Era status.** Historical (for forensic analysis of 2022-2024 content). Largely Deprecated in current frontier output.
- **Useful for analyzing content from.** November 2022 through end of 2024. Highest density in the calendar year 2023. Still appears at residual rate in late-2024 outputs and in older fine-tunes deployed locally.
- **Zone tag.** `WRAPPER-OPENER`.
- **Description.** ChatGPT 3.5 and early GPT-4 prefaced responses to ambiguous or sensitive prompts with "As an AI language model, I cannot..." or "As an AI language model, I don't have personal experiences but...". The preamble was the single most recognizable AI tell of the 2022 to 2024 era. Largely trained out of frontier models since 2024. Perplexity's A3 table classifies v3.1.0 criterion 1 "Transparent Self-Identification" as DEMOTE; DeepSeek's A3 list classifies the related v3.1.0 criterion 13 as DEPRECATE.
- **Concrete examples.**
  1. "As an AI language model, I cannot provide personal opinions on this matter."
  2. "As an AI language model, I don't have personal experiences, but I can offer some general perspectives."
  3. "As an AI language model developed by OpenAI, I should note that..."
- **Location and register.** Response openers, especially to opinion-seeking, identity, or borderline-sensitive prompts.
- **Model attribution.** GPT-3.5 (very high confidence, historical). GPT-4 first generation. Largely absent from GPT-4o and beyond. Other LLMs produced similar preambles in the same era ("As a large language model trained by..." for Bard documented separately as A1-BARD-001; "I'm Claude, an AI assistant..." for early Claude) but the OpenAI variant was canonical.
- **Time evolution.** Emerged with ChatGPT public release on November 30, 2022. Peaked early 2023. Began declining mid-2024 as OpenAI tuned against it. Largely absent from frontier output by 2025. Present at residual rate in very-borderline prompts.
- **Sources.** Walters and Wilder Sci Rep 2023. Pre-upgrade unified bucket A entry A1-GPT-007 with cross-validation from DeepSeek and Perplexity research deliverables (May 2026).
- **Signal strength.** VERY HIGH for content from 2022-2024 (definitive of AI provenance). LOW for current frontier output (because base rate is near zero).
- **Base rate.** Was very high in 2022-2024 (estimated 15 to 25 percent of all ChatGPT responses, much higher for opinion or identity prompts). Near zero in 2026 frontier output. Still appears in some local-deploy or older fine-tunes.
- **Causal hypothesis (ranked).** Primary: alignment and safety tuning that explicitly trained the disclaimer. Secondary: system-prompt artifacts during the early ChatGPT API release.
- **Detection difficulty.** Easy. Exact phrase.
- **False positive risk.** Very low for the explicit phrase. Some writers parody the construction, but parody is generally distinguishable.
- **Fix or remediation.** Strip the preamble. Either answer or decline cleanly. (For historical archives, the preamble is the AI tell, no fix is needed because the artifact is the evidence.)

### A1-GPT-006: "Here's the thing" / "The thing is" colloquial intensifier

- **Era status.** Historical (for analyzing 2023-2024 content). Declining toward Deprecated in current frontier output.
- **Useful for analyzing content from.** 2023 through mid-2024. Lower but non-trivial density in late-2024. Near-extinct in 2026 frontier output.
- **Zone tag.** `BODY-PERSISTENT`.
- **Description.** GPT-3.5 and early GPT-4 used colloquial intensifiers ("Here's the thing," "The thing is," "Look,") to signal an upcoming key point. Some of these have been trained out of newer GPT versions; the pattern is most useful for forensic analysis of older content.
- **Concrete examples.**
  1. "Here's the thing: the migration plan assumed all services were stateless, but two of them weren't."
  2. "The thing is, the data warehouse choice depends entirely on your read/write ratio."
  3. "Look, the real issue is that the architecture doesn't match the load pattern."
- **Location and register.** Body paragraphs, conversational and explainer registers.
- **Model attribution.** GPT-3.5 and early GPT-4 (high confidence for historical content). Reduced in GPT-4o and beyond.
- **Time evolution.** High density in 2023. Declining through 2024. Largely trained out of GPT-5 and GPT-5.1.
- **Sources.** Pre-upgrade unified bucket A entry A1-GPT-006 with cross-validation from DeepSeek and Perplexity research deliverables (May 2026).
- **Signal strength.** HIGH for content from 2023. LOW for current frontier output.
- **Base rate.** Was high in 2023 GPT-3.5/4 output. Near-zero in 2026 frontier GPT.
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling in early ChatGPT for colloquial engagement. Secondary: training-data skew toward casual blog and forum corpora.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate. The phrasing is common in colloquial writing.
- **Fix or remediation.** Remove the intensifier and start with the substantive point.

### A1-GPT-018: Artificial enthusiasm markers

- **Era status.** Declining toward Historical. Trending toward Historical as of May 2026 per Perplexity.
- **Useful for analyzing content from.** 2022 through mid-2025. Particularly diagnostic in GPT-3.5 and GPT-4o content from 2023 to early 2024 before the April 2025 sycophancy rollback.
- **Zone tag.** `WRAPPER-OPENER` primarily; `MID-BODY-INSERT` secondarily.
- **Description.** GPT-4o and earlier produced enthusiasm about tasks and topics at a rate that did not correlate with the actual interest level of the content. "Great question!" appeared before mundane prompts. "Fascinating!" appeared before routine requests. The April 25, 2025 OpenAI sycophancy rollback measurably reduced this in GPT family output starting late April 2025; the pattern remains diagnostic for content from before that inflection point.
- **Concrete examples.**
  1. "What a great question! Let me explain the difference between TCP and UDP."
  2. "Fascinating! The Python `enumerate` function is one of my favorites."
  3. "I'm thrilled to help you with your tax filing checklist."
- **Location and register.** Response openers; mid-body topic-shift transitions.
- **Model attribution.** GPT-3.5 and GPT-4 lineage (very high confidence for the pre-April-2025 era). Claude 3.x had a softer parallel ("I'd be happy to help with..."). Gemini's "Sure!" opener is a Gemini-family analog.
- **Time evolution.** Stable across GPT-3.5 and GPT-4 era. Peaked in GPT-4o (2024). The April 2025 sycophancy rollback measurably reduced rate. Residual rate in late-2025 and 2026 outputs.
- **Sources.** OpenAI sycophancy retrospective (openai.com/index/sycophancy-in-gpt-4o, April 2025). Pre-upgrade unified bucket A entry A1-GPT-018 with cross-validation from Perplexity research deliverable (May 2026).
- **Signal strength.** HIGH for content from 2022 to mid-2025. LOW for content from May 2025 forward.
- **Base rate.** Estimated 25 to 45 percent of GPT-4o responses to any task-receiving prompt in 2024. Reduced measurably after April 25, 2025. Residual rate (estimated 5 to 10 percent) in late-2025 output.
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling that prioritized user-pleasing short-term signals (acknowledged by OpenAI in the April 2025 retrospective). Secondary: training-data skew toward customer-service and consumer-support corpora.
- **Detection difficulty.** Easy. Exact phrase or close variant.
- **False positive risk.** Low for the explicit phrase. Some human writers in customer-support roles use these openers naturally.
- **Fix or remediation.** Strip the enthusiasm opener. Move directly to the substantive answer.

### A1-GPT-021: "As of my knowledge cutoff in [date]" disclaimer

- **Era status.** Historical (declining toward Deprecated). Per DeepSeek's A3 catalog classification: deprecated in new models but still in some configurations.
- **Useful for analyzing content from.** 2022 through 2024. Particularly diagnostic in GPT-4 and GPT-4o outputs to questions touching recent events. Persists at residual rate in 2026 outputs when models lack tool-use for current information.
- **Zone tag.** `MID-BODY-INSERT`.
- **Description.** GPT family models included a self-aware disclaimer when answering questions about recent events: "As of my knowledge cutoff in [month year], I cannot provide information about events after that date." The phrasing was nearly identical across GPT-3.5, GPT-4, and GPT-4o. Frontier models from 2025 forward more often rely on tool-use (web search) instead and elide the disclaimer; the disclaimer survives in configurations without tool-use.
- **Concrete examples.**
  1. "As of my knowledge cutoff in October 2023, I cannot provide information about events that occurred after that date."
  2. "Note that my training data extends only to April 2023, so for recent developments you would want to consult more current sources."
  3. "Based on my knowledge cutoff (January 2025), the most recent reported figures were..."
- **Location and register.** Body inserts; closing paragraphs of responses to current-events prompts.
- **Model attribution.** GPT family (high confidence for the canonical phrasing). Gemini had a parallel ("Based on my knowledge as of [date]" per A1-GEMINI-020 in the current-active catalog).
- **Time evolution.** Stable from 2022 through 2024. Reducing from 2025 forward as tool-use becomes default. Persists in API-only and configuration-without-search deployments.
- **Sources.** Pre-upgrade unified bucket A entry A1-GPT-021 (DeepSeek contribution, May 2026). Cross-validation in OpenAI's published model documentation for GPT-3.5 and GPT-4 (2023-2024 release notes).
- **Signal strength.** HIGH for content from 2022 to mid-2024 (definitive of GPT provenance when present). MEDIUM for 2024-2025 (still common when tool-use disabled). LOW for current frontier output with tool-use enabled.
- **Base rate.** Estimated 40 to 60 percent of GPT responses to current-events prompts in 2022-2024. Reduced to estimated 10 to 20 percent in 2025-2026 with tool-use enabled.
- **Causal hypothesis (ranked).** Primary: RLHF safety tuning to avoid claiming knowledge of post-cutoff events. Secondary: system-prompt instructions during early API deployment.
- **Detection difficulty.** Easy. Exact phrase or close variant.
- **False positive risk.** Very low for the explicit phrasing.
- **Fix or remediation.** For current outputs, enable tool-use or strip the disclaimer when the answer does not depend on recency. For historical archives, the disclaimer is the AI tell.

### A1-GEMINI-019: "I'm still learning, but..." self-deprecation

- **Era status.** Historical for Gemini Ultra and Gemini Pro 1.0. Deprecated in Gemini 2.5 Pro but still appears in some contexts and in older fine-tunes.
- **Useful for analyzing content from.** December 2023 through end of 2024. Highest density in early-2024 Gemini outputs. Near-extinct in 2026 Gemini 2.5/3.x frontier.
- **Zone tag.** `WRAPPER-OPENER` and `MID-BODY-INSERT`.
- **Description.** Earlier Gemini versions (Ultra, Pro 1.0) frequently disclaimed capability with a self-deprecating "I'm still learning, but..." preamble or hedge. The phrasing was a Gemini-family analog of GPT's "As an AI language model" but framed as developmental modesty rather than category self-identification. Deprecated in Gemini 2.5 Pro; still appears in some contexts and older deployments.
- **Concrete examples.**
  1. "I'm still learning, but I'll do my best to help you with your question about distributed systems."
  2. "As a still-developing language model, I might not have the most current information on this."
  3. "I'm still learning how to handle questions like this, so please verify any specifics with a domain expert."
- **Location and register.** Response openers, mid-body hedges before specific claims.
- **Model attribution.** Gemini Ultra, Gemini Pro 1.0, early Gemini Pro 1.5 (high confidence for the era). Largely absent from Gemini 2.5+. Gemini 2.0 transitional outputs show declining rate.
- **Time evolution.** Emerged with Gemini rebrand of Bard in February 2024. High density through end of 2024. Declining through 2025 as Gemini 2.x rolled out. Residual rate in 2026.
- **Sources.** Pre-upgrade unified bucket A entry A1-GEMINI-019 (DeepSeek contribution, May 2026). Cross-validation in Google AI Studio release notes for Gemini Ultra and Gemini Pro 1.0.
- **Signal strength.** HIGH for Gemini provenance in 2024 content. LOW for current frontier Gemini output.
- **Base rate.** Estimated 20 to 35 percent of Gemini Ultra responses in 2024. Estimated 2 to 5 percent in 2026 Gemini 2.5 output.
- **Causal hypothesis (ranked).** Primary: Google alignment training that prioritized humility framing in response openers. Secondary: differentiation strategy versus GPT's more confident default. Tertiary: legal-risk-management training in light of Bard's high hallucination rate at launch.
- **Detection difficulty.** Easy.
- **False positive risk.** Very low for the explicit phrase.
- **Fix or remediation.** Strip the disclaimer. State capability directly or decline cleanly.

### v3.1.0 Criterion 16: Curly vs. Straight Quotes

- **Era status.** Deprecated. Per ChatGPT's A3 classification: too toolchain-dependent and too weak as a modern provenance signal. The toolchain (text editor, copy-paste path, rendering target) determines quote style more than the model.
- **Useful for analyzing content from.** 2020 through mid-2023. After mid-2023, copy-paste through Google Docs, Microsoft Word, and many web editors became reliable enough that the curly/straight distinction reflects the path the text traveled rather than the model that produced it.
- **Zone tag.** `BODY-PERSISTENT` (but signal value is near-zero in current outputs).
- **Description.** Inconsistent quote styles (curly versus straight) or the wrong type for the publication's house style. In v3.1.0 this was treated as a low-confidence AI signal because LLMs tended to produce straight quotes when the surrounding text used curly, and vice versa. Subsequent toolchain evolution (autocorrect in editors, smart-quote pipelines in publishing CMSs, and improved rendering in chat interfaces) made the signal too noisy to be reliable.
- **Concrete examples.**
  1. A New Yorker article with curly quotes in body text but straight quotes in pull-quotes (could be CMS, could be AI).
  2. A blog post with mixed quote types in a single paragraph (more likely a copy-paste artifact than an AI signal).
- **Location and register.** Punctuation in body text; pull quotes; headers.
- **Model attribution.** Variable across families. No family-specific signal.
- **Time evolution.** Was a weak signal in 2020-2023. Effectively zero signal value in 2024-2026.
- **Sources.** v3.1.0 catalog criterion 16. ChatGPT A3 classification (May 2026): DEPRECATE.
- **Signal strength.** LOW even in the historical era. Effectively zero in current outputs.
- **Base rate.** Variable, toolchain-dependent.
- **Causal hypothesis (ranked).** Toolchain artifacts dominate. Model contribution is minor.
- **Detection difficulty.** Easy to detect (character-level), but the detection is uninformative for provenance.
- **False positive risk.** Very high. Almost any copy-paste path introduces quote-type inconsistency.
- **Fix or remediation.** Apply the publication's house-style quote convention via CMS or text editor settings. Do not rely on quote style as an AI tell.

### A1-CLAUDE-006 (early era): Refusal-shaped close with safety hedge

- **Era status.** Active in current Claude frontier output (Claude 3.x and Claude 4.x). Historical version of the pattern (the harder, more template-like Claude 1 / early Claude 2 form) is documented here for forensic analysis of 2023 content.
- **Useful for analyzing content from.** Q1 2023 (Claude 1 anthropic launch) through Q3 2023. The harder template-like form was specific to early Claude; the softer current form is documented in the active model-family-fingerprints catalog.
- **Zone tag.** `WRAPPER-CLOSER`.
- **Description.** Claude 1 (anthropic.com launch in March 2023) and early Claude 2 produced refusal-shaped closes that explicitly named the model's caution: "I should mention that I'm an AI assistant and..."; "I want to be careful here because..."; "As I noted, I can't speak to this with certainty because I am an AI." The phrasing was more template-like than the current Claude 3/4 form, which has been softened into the broader "I hope this helps" / "Let me know if you'd like me to explore other angles" closer pattern documented in A1-CLAUDE-006 (current).
- **Concrete examples.**
  1. "I should mention that as Claude, I'm an AI assistant and don't have direct experience with the situations described."
  2. "I want to be careful here because the topic involves potential harm to others; I'd suggest consulting a qualified professional."
  3. "As I noted, I can't speak to this with certainty because I am an AI without direct access to current information."
- **Location and register.** Final 1-3 sentences of response. Higher density in safety-sensitive prompts.
- **Model attribution.** Claude 1 (very high confidence, March-July 2023). Early Claude 2 (high confidence, July-November 2023). Significantly softened in Claude 2.1 and later. Distinct from the current `A1-CLAUDE-006` softer "I hope this helps" closer.
- **Time evolution.** Peak density in Claude 1 (March-July 2023). Declining through Claude 2 second half of 2023. Largely replaced by softer closers in Claude 2.1 (November 2023) and Claude 3 (March 2024).
- **Sources.** Anthropic Claude 1 release notes and Claude 2 release notes. Pre-upgrade unified bucket A historical references to Claude 1 refusal-template patterns.
- **Signal strength.** HIGH for Claude 1 / early Claude 2 provenance in 2023 content. LOW for current frontier Claude output.
- **Base rate.** Estimated 30 to 50 percent of Claude 1 responses in 2023. Reduced to estimated 5 to 10 percent in current frontier Claude (where the softer form dominates).
- **Causal hypothesis (ranked).** Primary: Anthropic constitutional AI training in the launch generation that prioritized explicit transparency about model capability and caution. Secondary: differentiation strategy versus GPT's then-canonical "As an AI language model" preamble (Anthropic substituted a closer instead of an opener).
- **Detection difficulty.** Easy.
- **False positive risk.** Low for the explicit phrasings.
- **Fix or remediation.** For current outputs, replace with substantive caveat embedded in the main clause. For historical archives, the closer is the AI tell.

### Bard hallucination-rate fingerprint (cited measurement, June-December 2023)

- **Era status.** Historical. Bard as a product was renamed Gemini in February 2024.
- **Useful for analyzing content from.** February 2023 (Bard launch) through end of 2023. Particularly applicable to Bard-attributed content from the launch through the rebrand.
- **Zone tag.** `BODY-PERSISTENT`.
- **Description.** Bard's citation hallucination rate was measured at approximately 91 percent in one early study (Walters and Wilder Sci Rep 2023, referenced in the unified bucket B per-family calibration table). The rate was substantially higher than concurrent GPT-3.5 (30 to 55 percent) and GPT-4 (18 to 29 percent). Content with citations attributed to "Bard suggested these sources..." or similar that contains broken DOIs, fabricated journal names, or misattributed quotes at high density is consistent with the Bard era and the Bard hallucination fingerprint.
- **Concrete examples.**
  1. An article from mid-2023 citing "a recent Stanford study by Dr. Chen et al." where the citation contains a fabricated DOI and no such study exists.
  2. A blog post with five citations attributed to academic journals where two journals do not exist and three articles by the claimed authors do not exist.
  3. A research summary that cites correct journal names but fabricated article titles and incorrect publication years.
- **Location and register.** Body content where Bard was used to assist citation. Particularly common in educational, medical, and legal explainer content from 2023.
- **Model attribution.** Bard (very high confidence for the high hallucination rate). Distinguished from contemporary GPT and Claude by the much higher rate of fabricated citations.
- **Time evolution.** Peak rate in early Bard (February-June 2023). Declining through 2023 as Google iterated. Replaced entirely after Gemini rebrand February 2024.
- **Sources.** Walters and Wilder Sci Rep 2023 (cited in pre-upgrade unified bucket B). Anchored at 91 percent citation hallucination rate for early Bard.
- **Signal strength.** VERY HIGH when combined with attribution to Bard in 2023 content.
- **Base rate.** Approximately 91 percent of cited sources in early Bard outputs were hallucinated or contained errors per the cited measurement.
- **Causal hypothesis (ranked).** Primary: LaMDA base model that under-trained on factual accuracy compared to OpenAI's then-current GPT-3.5 and GPT-4. Secondary: early-launch deployment without retrieval augmentation.
- **Detection difficulty.** Easy for the citation-fabrication pattern (cross-reference each citation against scholarly databases). Hard to attribute specifically to Bard versus a contemporaneous family without provenance metadata.
- **False positive risk.** Low when combined with explicit Bard attribution. Higher in unsourced content from the era.
- **Fix or remediation.** Verify every citation against authoritative sources. For Bard-era content, default to skepticism on any citation.

---
