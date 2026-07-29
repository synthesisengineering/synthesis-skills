# Historical Patterns Reference

> **Compounding-archive companion file.** This is the long-tail catalog of patterns whose era of prevalence has passed for current frontier models but remains diagnostic for forensic analysis of older AI-generated content. The patterns are retained (not deleted) and tagged with their era of prevalence, base rates by year, and the dates during which each is a reliable signal.

---

## Preface: the compounding-archive principle

The synthesis-content-quality catalog grows over time. Some patterns that were canonical AI tells in 2023 are now near-extinct in current frontier models because the labs that built those models trained the patterns out. The temptation, when a pattern fades, is to delete it from the catalog so the catalog stays lean and current.

This catalog does not delete. It retires.

A 2026 newsroom editor reviewing a 2023 article for AI provenance needs the 2023 catalog, not the 2026 one. A media-history researcher studying the early ChatGPT era needs to read content with the era-appropriate lens. A litigator examining a 2024 deposition exhibit needs the patterns that were diagnostic in 2024, regardless of which patterns are diagnostic today. Deleting trained-out patterns from the catalog would erase the very tools those audiences need.

The catalog therefore operates on a compounding-archive principle: every pattern that ever earned a place stays in the catalog forever, with explicit era-of-prevalence metadata. Patterns move from `Active` (still prevalent in current frontier models) to `Declining` (still occurs but at much lower base rate) to `Historical` (largely trained out of post-X models but still useful for forensic analysis of content from that pattern's era) to `Deprecated` (effectively absent from current models, retained for archival use only). Patterns never move to `Deleted`.

This file collects every pattern currently at `Historical` or `Deprecated` status, plus net-new historical entries that fill audit-identified gaps in coverage of older model families. Each entry carries a "useful for analyzing content from" date range so an editor can map the pattern to the era of the artifact they are auditing.

The methodology in [SKILL.md](../SKILL.md) is the durable part. The active-pattern catalog in [detailed-criteria.md](detailed-criteria.md) and the model-family fingerprints in [model-family-fingerprints.md](model-family-fingerprints.md) are refreshed as model behavior shifts. This file is the depth dimension that makes the catalog work across the entire LLM era from 2020 to today, not only on the current crop.

---

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
