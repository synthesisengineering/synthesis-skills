# Per-family hallucination signatures, part 2: Llama, Grok, DeepSeek, Mistral, Qwen

Part 2 of two, split from [per-family-hallucination-signatures.md](per-family-hallucination-signatures.md) so each part can be read in one pass. The text is verbatim, and the index's em-dash audit covers this part. The caveats and empirical anchors that apply to every family are in part 1, [per-family-signatures-claude-gpt-gemini.md](per-family-signatures-claude-gpt-gemini.md).

Contents:
- Meta Llama
- xAI Grok
- DeepSeek
- Mistral
- Qwen

---

## Meta Llama

Models in scope: Llama 3, 3.1, 3.2, 4 across the 8B, 70B, and 405B parameter sizes. Llama family signatures are coupled to context length and parameter size more tightly than other families.

### Signature description

The canonical Llama hallucination signature is long-context fabrication. Above approximately 32K tokens of context (per RIKER benchmark arxiv 2603.08274, with the 32K threshold flagged as approximate by Opus expansion verification), factual confabulation increases substantially. The model maintains coherence at the prose level while introducing facts not in the input documents. A Llama summary of a 40K-token report will state facts not in the report with high confidence and low hedging. The fabrication is invisible to readers who do not have the input documents and is invisible to detectors that check only the output for stylistic markers, because the prose remains coherent.

Llama exhibits three additional signature components. First, reduced hedging: per Perplexity bucket-C contribution, Llama asserts incorrectly more often than Claude or GPT but hedges the assertion less. This makes the errors easier to spot for a fact-checker who is checking, because the error is asserted plainly. But it makes the errors more dangerous for readers who do not verify, because the confidence signal points toward truth when the content is wrong.

Second, entity-name errors at higher rates in smaller Llama models. Per Perplexity bucket-C contribution: entity-name errors (4d) are more pronounced in Llama 8B than in Llama 70B or 405B. Smaller-parameter Llama deployments substitute or invent organization names, individual names, and institution names at notably higher rates.

Third, statistic invention with precise numbers. Per DeepSeek bucket-C contribution: Llama hallucinates statistics with precise-seeming numbers (e.g., "47.3 percent") that are baseless. The precision is the polish; the statistic is fabricated. This intersects with 4c (wrong specifics from correct general findings) but with a Llama-specific high-precision-percentage pattern.

Fourth, code-snippet hallucination. Per Manus AI bucket-C contribution: Llama may hallucinate technical details or code snippets that are syntactically correct but functionally flawed or non-existent. A code example will compile or run without syntax errors but will produce wrong results, call non-existent library functions, or pattern-match on plausible-but-wrong API signatures.

The compensating property: limited source grounding in base Llama models, but RAG-extended versions reduce hallucination substantially. Per Perplexity bucket-C contribution. Editorial workflow recommendation: if the workflow can specify RAG or no-RAG, prefer RAG-augmented Llama output and treat base Llama output with extra verification.

### Empirical base rates

- **Long-context fabrication threshold (RIKER benchmark arxiv 2603.08274, flagged for verification):** approximately 32K context tokens. Below this threshold, Llama hallucination rates are comparable to other families. Above this threshold, rates increase substantially. The specific threshold is approximate; the increase is documented.

- **Entity-name error rate.** Not empirically anchored as a percentage in bucket-C inputs. Qualitatively documented as more pronounced in Llama 8B than in larger Llama models. Editorial heuristic: assume the entity-error rate scales inversely with parameter count.

- **Confident-assertion-without-hedging rate.** Not empirically anchored as a percentage. Qualitatively documented across multiple bucket-C inputs as a Llama family characteristic.

- **AI Multiple January 2026 cross-family bound: 15 to 52 percent hallucination across 37 LLMs.** Llama family typically sits in the middle to upper-middle of this range depending on size and context length, but specific Llama rates are not published in the cross-bucket sources at the same granularity as Claude, GPT, or Gemini rates.

### Concrete examples

1. **Long-context fabrication at 40K tokens (Claude Opus 4.7 expansion canonical example).** Llama on a 40K-token document analysis: confidently states facts not in the document. The summary reads plausibly; the input contains no support for several specific claims; the model has confabulated to maintain narrative completeness. The error is invisible to readers who do not have the 40K-token input.

2. **Statistic invention with precise numbers (per DeepSeek).** Llama output: "47.3 percent of enterprises have deployed agentic AI workflows as of 2026." Verification: no such study or survey exists. The 47.3 percent is fabricated with one-decimal-place precision. The precision is the polish.

3. **Entity-name error in Llama 8B (per Perplexity).** Llama 8B output: "The National Institute of Advanced Technology has published guidelines on..." Verification: no such institute exists. The actual institute might be NIST (National Institute of Standards and Technology) or might be a different real institute, or might be a fabrication. Smaller Llama models substitute plausible-sounding but wrong names.

4. **Code-snippet hallucination (per Manus AI).** Llama output: `import torch; model = torch.hub.load('meta/llama-superfast', 'llama-v3-instruct'); response = model.generate("query")` Verification: there is no `meta/llama-superfast` repository on torch hub; the function signature is plausible; the actual function call produces an error or pulls a different model. The code is syntactically correct; the API surface is invented.

5. **Reduced-hedging assertion (per Perplexity).** Llama output: "The treatment reduces mortality by 23 percent" with no qualifying language about study population, sample size, or limitations. A Claude piece on the same content would hedge ("The treatment may reduce mortality...", "Some studies suggest a reduction of approximately 20 percent..."). Llama asserts the specific number plainly. If the underlying study found a 19 percent reduction with wide confidence intervals, the Llama assertion is wrong, and the reader has no hedging signal to indicate uncertainty.

6. **Wegovy stress-test long-context fabrication (Claude exec).** Wegovy multi-family stress test: Llama fabricated above 32K context. The context boundary is the diagnostic signature.

### Family-specific detection workflow

1. **A1 stylistic identification first.** If the piece exhibits A1-LLAMA markers (especially A1-LLAMA-001 lower em-dash baseline and abrupt declarative pattern at 0.0 per 1,000 words em-dash rate, A1-LLAMA-003 fabrication at long context above 32K tokens as a stylistic signature, A1-LLAMA-004 direct-question response without preamble, A1-LLAMA-008 shorter more direct sentences, A1-LLAMA-010 reduced hedging and assertive claims), apply Llama-specific checks. Llama identification is partly negative: the absence of em-dashes (A1-LLAMA-001 at 0.0 per 1,000 words) combined with assertive declarative sentences (A1-LLAMA-010) is a strong negative-signature indicator for Llama family.

2. **Context-length awareness.** If the workflow knows the input context length, calibrate the audit intensity accordingly. Below approximately 32K tokens: Llama hallucination rates are comparable to other families; audit at standard intensity. Above approximately 32K tokens: increase audit intensity substantially; assume long-context confabulation is present. If context length is unknown, audit at the long-context intensity to be safe.

3. **Long-context fabrication audit.** For Llama-styled pieces that summarize long documents, verify every load-bearing factual claim against the input documents. The fabrication signature is invisible at the prose level because the prose remains coherent; the only way to catch it is to compare claims to inputs.

4. **Precise-number audit.** For every statistic with two or more decimal places of precision ("47.3 percent", "2.4 million", "$1.7 billion"), verify the specific number against a specific source. The precision is the Llama signature for fabrication; if no source can be located, treat the statistic as fabricated.

5. **Entity-name audit (Llama 8B in particular).** Verify every named organization, institute, individual, and named entity. Smaller Llama models have higher entity-name error rates; the registry check (GLEIF for legal entities, ORCID for researchers, .gov/.edu official sites) is especially valuable here.

6. **Code-snippet verification.** For any Llama code output, run the code or check the API surface against documentation. Syntactically correct code that hallucinates API functions or library symbols is a Llama signature; the catch requires either execution or doc lookup.

7. **Hedging-restoration audit.** Where Llama makes confident assertions on contested or evolving claims, check whether the underlying source hedged or specified confidence intervals. If the source hedged and Llama did not, the assertion has lost epistemic frame (C1-PARAPH-001 under-paraphrase form). Restore the hedge.

8. **RAG vs. no-RAG awareness.** If the workflow knows whether the Llama output was RAG-augmented or base, prefer RAG output and audit base output at higher intensity.

### Cross-references

- **A1 stylistic fingerprints for family identification.** Highest-yield Llama markers: A1-LLAMA-001 (lower em-dash baseline at 0.0 per 1,000 words), A1-LLAMA-002 (sterile infrastructure tone), A1-LLAMA-003 (fabrication at long context above 32K tokens), A1-LLAMA-004 (direct-question response without preamble), A1-LLAMA-006 (refusal under-rotation), A1-LLAMA-008 (shorter, more direct sentences), A1-LLAMA-010 (reduced hedging and assertive claims). A1-LLAMA-001 and A1-LLAMA-010 together produce a strong negative signature.
- **C1-TOOLHALL-001 in detailed-protocols.md.** Full tool-specific verification procedure.
- **4c (wrong specifics from correct general findings) in SKILL.md.** Llama's precise-number fabrication amplifies 4c risk.
- **4d (wrong entity names) in SKILL.md.** Llama 8B's entity-name error rate makes 4d especially relevant for small-Llama output.

---

## xAI Grok

Models in scope: Grok 1, 2, 3, 4. xAI's Grok family has thinner peer-reviewed coverage than the Claude, GPT, and Gemini families. The bucket-C inputs rely more on practitioner observation and 2026 production reporting.

### Signature description

The canonical Grok hallucination signature is tweet and social-media source fabrication, paired with X-platform / Musk-source bias. Per Manus AI and DeepSeek bucket-C contributions: Grok may fabricate social media posts or tweets as sources, leveraging its platform-aware persona. The fabrications are plausible-shaped: a fabricated tweet has correct character length, plausible handle format, plausible timestamp, and content that fits the surrounding narrative. The fabrication is invisible to readers who do not search X (formerly Twitter) for the specific post. Even searching X for the specific post may not falsify the fabrication if the post genuinely never existed (a search returns zero results, which could mean "the post does not exist" or "the post was deleted" or "the search index does not include it").

A second signature component: X-platform / Musk-source bias. Per Mashable 2026 reporting cited by ChatGPT bucket-C contribution: Grok 4 uses Elon Musk's X posts as a source when answering questions. The bias is structural rather than per-response: Grok preferentially weights @elonmusk posts in its retrieval and citation behavior, regardless of whether the Musk post is the most authoritative source on the question. The result: Grok answers to questions about technology, business, AI, or politics may cite Musk X posts as if they were authoritative sources on technical or factual questions where Musk's posts are opinion or speculation.

A third signature component: humorous or irreverent "facts" that align with Grok's persona but are factually incorrect. Per Manus AI bucket-C contribution: Grok may hallucinate funny-but-wrong content as a persona-coherence move. The hallucination is wrapped in the persona, which makes it harder to distinguish from intentional dry humor or hyperbole.

A fourth signature component: earlier search-centric citation risk. Per ChatGPT bucket-C contribution: search-centric Grok outputs were citation-riskier earlier than recent reasoning variants. Earlier Grok versions exhibited the social-media-source-fabrication signature more aggressively; reasoning-augmented Grok variants reduce but do not eliminate the pattern.

### Empirical base rates

- **Tweet fabrication rate.** Not empirically anchored as a percentage in the bucket-C inputs. Qualitatively documented as a distinctive signature across Manus AI, DeepSeek, and ChatGPT contributions.

- **Musk-source bias.** Per Mashable 2026 reporting: a documented behavior pattern in Grok 4, with specific examples published in the Mashable coverage.

- **AI Multiple January 2026 cross-family bound: 15 to 52 percent hallucination across 37 LLMs.** Grok rates sit within this range; per-family granularity for Grok is thinner than for the empirically-anchored families (Claude, GPT, Gemini, Llama).

### Concrete examples

1. **Fabricated tweet as source (per Manus AI).** Grok output, answering a question about a public figure's stance: "As Senator X tweeted on April 14, 2025: '[fabricated content].'" Verification: searching X for the tweet returns zero results. The tweet did not exist. The fabrication included a plausible timestamp and plausible content for the senator's known position.

2. **Musk X-post citation as authoritative (per Mashable 2026 via ChatGPT).** Grok 4 output, answering a question about an AI capability: "According to @elonmusk's X post from January 2026, this approach achieves [specific technical claim]." Verification: the X post may or may not exist; if it exists, it is speculation or opinion rather than empirical evidence; either way, citing it as an authoritative source on the technical question is the bias signature.

3. **Humorous-but-wrong fact (per Manus AI).** Grok output: "Interestingly, the Roman emperor Caligula reportedly tried to appoint his horse Incitatus to the Senate as a consul." Verification: the horse story is widely repeated but historically uncertain; presenting it as fact rather than as a Suetonius anecdote is a Grok persona signature. The hallucination is wrapped in dry humor, which obscures the factual error.

4. **Earlier-search-centric citation risk (per ChatGPT bucket-C contribution).** Grok 2 or Grok 3 search-augmented output produces a citation to "a recent X thread by @username" where the thread does not exist. Reasoning-augmented Grok 4 variants exhibit the pattern at lower rate but not zero.

5. **Mixed-source bias (composite signature).** Grok output answering a question about Tesla's regulatory situation: cites three Musk X posts, one TechCrunch article, and one fabricated "industry analyst" tweet. The mix of real-but-non-authoritative sources, real-and-authoritative sources, and fabricated sources is harder to disentangle than a piece with uniform fabrication or uniform real sources.

### Family-specific detection workflow

1. **A1 stylistic identification first.** If the piece exhibits A1-GROK markers (especially A1-GROK-001 colloquial internet-native register and edgy sarcasm, A1-GROK-002 "Based on X" framing for opinion-seeking prompts, A1-GROK-004 Twitter-style structural defaults, A1-GROK-005 real-time data references, A1-GROK-006 pop-culture allusions, A1-GROK-007 skepticism-of-establishment positioning, A1-GROK-009 "TL;DR" summary at end), apply Grok-specific checks.

2. **Tweet and social-media source audit.** For every cited tweet, X post, social-media post, or platform-native reference, verify the post exists. Search the platform for the specific content; verify the handle, the timestamp, and the post text. If the post cannot be located, treat as fabrication. Be aware that platform search indexes are incomplete and deleted posts may not be findable, but the burden of proof is on the citation: an unfindable post is not a verified post.

3. **Musk-source bias audit.** If the piece cites @elonmusk posts as authoritative sources, check whether the cited post (a) exists and (b) actually says what is claimed and (c) is the most authoritative source on the question. If Musk X posts are cited on technical, scientific, regulatory, or financial questions where Musk has no specialized authority, downweight the citation and seek a primary source.

4. **Persona-wrapped factual claim audit.** For every claim that arrives in a persona-coherent humorous or irreverent register, separate the persona wrapper from the factual core. Verify the factual core against a primary source. The persona makes the claim sound like "a Grok thing to say" which can lull readers into trusting the underlying fact when it is actually fabricated.

5. **Search-centric Grok version awareness.** If the workflow knows whether the output came from an earlier search-centric Grok variant or a reasoning-augmented variant, calibrate the audit intensity. Earlier variants have higher search-citation fabrication; reasoning variants reduce but do not eliminate the pattern.

6. **Universal source-verification fallback.** Per the absence of strong family-specific empirical anchors for Grok, fall back to the universal source-verification procedure from SKILL.md sections 4f and the C1-URLROT-001 / C1-SYNTH-001 / C1-LAUNDER-001 trio for any non-tweet citations.

### Cross-references

- **A1 stylistic fingerprints for family identification.** Highest-yield Grok markers: A1-GROK-001 (colloquial internet-native register and edgy sarcasm), A1-GROK-002 ("Based on X" framing for opinion-seeking prompts), A1-GROK-003 (lower hedging density), A1-GROK-004 (Twitter-style structural defaults), A1-GROK-005 (real-time data references), A1-GROK-006 (pop-culture allusions), A1-GROK-007 (skepticism-of-establishment positioning), A1-GROK-009 ("TL;DR" summary at end), A1-GROK-010 (profanity or emphasis words).
- **C1-TOOLHALL-001 in detailed-protocols.md.** Full tool-specific verification procedure.
- **C1-SYNTH-001 in detailed-protocols.md.** Tweet fabrication is a synthetic-source pattern; the C1-SYNTH-001 protocol applies.
- **4e (misattributed quotes) in SKILL.md.** Grok's tweet fabrication intersects with quote misattribution.
- **Mashable 2026 production-incident anchor** in the bibliography.

---

## DeepSeek

Models in scope: DeepSeek V2, V3, and R1 (the reasoning variant). The DeepSeek family was stylometrically classified as OpenAI-like by Copyleaks 2025, but exhibits distinctive non-GPT signatures under reasoning load.

### Signature description

The canonical DeepSeek hallucination signature is language-mixing under reasoning load. Per Claude Opus 4.7 expansion, Claude exec, and Gemini bucket-C contributions: DeepSeek-R1 extended-thinking output contains Chinese characters ("我们需要考虑..." meaning "we need to consider...") in a primarily English response. The reasoning trace contains Chinese characters that the final output may or may not retain. The Chinese fragments are not translation errors; they are reasoning-language artifacts from the model's bilingual training corpus that surface under heavy reasoning load when the model's English-language generation pressure decreases below the threshold needed to suppress the underlying reasoning tokens.

The language-mixing is diagnostic for DeepSeek family identification at a technical level (Unicode-detectable: CJK character ranges in an English document) and is also a flag for fact-checking priority. When language-mixing is present, it indicates the model was under reasoning load. Under reasoning load, DeepSeek's other hallucination signatures activate:

A second signature: reasoning trace contamination. Per Perplexity bucket-C contribution: when reasoning traces are exposed, they may contain incorrect reasoning steps that contradict the final output. The model's chain-of-thought may state "Step 1: assume X is true. Step 2: derive Y from X." while the final output presents Y as if X had been verified rather than assumed. The intermediate reasoning step is fabrication; the final output is fabrication-derived.

A third signature: population-level fabrications on historical statistics from Chinese sources. Per Perplexity bucket-C contribution: DeepSeek V3 specifically shows population-level fabrications on historical statistics from Chinese sources, reflecting training data composition. The model has internalized a Chinese-corpus-derived statistical worldview that may be at variance with English-language sources on the same topics.

A fourth signature: academic-paper fabrication for coding decisions. Per Gemini bucket-C contribution: DeepSeek invents a highly plausible English-language academic paper title and author attribution to support a coding decision. The fabricated paper is presented as the empirical justification for choosing one algorithm or library over another. The paper does not exist. The fabrication is the GPT-style URL fabrication translated into the academic-paper-citation domain.

A fifth signature: technical-logic-to-natural-language hallucination. Per Gemini bucket-C contribution: DeepSeek hallucinates heavily when translating technical logic into natural language. The mathematical or code-level reasoning may be approximately correct; the natural-language explanation drifts from the technical correctness.

Per Copyleaks 2025: DeepSeek is stylometrically classified as OpenAI-like; the hallucination patterns are similarly GPT-like in many respects. This means that for English-language output without reasoning load, DeepSeek behaves much like GPT, and the GPT family verification workflow applies. Under reasoning load, the DeepSeek-specific signatures activate.

### Empirical base rates

- **Stylometric classification (Copyleaks 2025): GPT-like.** Hallucination patterns are similarly GPT-like under normal load. For URL hallucination specifically, the GPT-family rates apply approximately.

- **Language-mixing rate under reasoning load.** Not empirically anchored as a percentage in bucket-C inputs. Qualitatively documented as a distinctive signature in extended-thinking output for DeepSeek-R1.

- **Chinese-source population-level fabrication.** Not empirically anchored as a percentage. Qualitatively documented in Perplexity bucket-C contribution as a V3-specific pattern.

- **Reasoning trace contamination rate.** Not empirically anchored. Qualitatively documented across multiple bucket-C inputs.

### Concrete examples

1. **Chinese characters in English reasoning output (Claude Opus 4.7 expansion canonical example).** DeepSeek-R1 extended-thinking output: "We can analyze this question by considering 我们需要考虑 several factors. First, the regulatory environment..." The Chinese phrase "我们需要考虑" means "we need to consider"; its presence in an English response is the language-mixing signature.

2. **Reasoning trace contradiction (per Perplexity).** DeepSeek-R1 reasoning trace: "Step 1: assume the company is profitable. Step 2: calculate expected return at 12 percent annual growth. Step 3: conclude the investment is attractive." Final output: "The investment is attractive because the company is profitable and growing at 12 percent." The assumption in Step 1 was unverified; the final output presents it as fact. The reasoning trace is the diagnostic; the final output without the trace is indistinguishable from a confident assertion.

3. **Chinese-source historical statistic fabrication (per Perplexity, V3 specific).** DeepSeek V3 output about historical Chinese economic growth: cites specific GDP figures, population figures, or trade statistics from earlier centuries that match a Chinese-corpus narrative but do not match the consensus English-language scholarly figures. The fabrication reflects training-corpus composition.

4. **Academic-paper fabrication for coding decision (per Gemini).** DeepSeek output: "Use the Adam optimizer for this task. Per Smith and colleagues (2024), 'On the Convergence Properties of Adaptive Learning Rate Methods in Deep Reinforcement Learning' (NeurIPS 2024), Adam outperforms RMSProp by 17 percent on similar reinforcement learning tasks." Verification: the paper title is plausible; the authors may or may not be real; the paper does not exist in NeurIPS proceedings or on arXiv. The fabrication justifies the coding decision but is invented.

5. **Technical-logic-to-natural-language drift (per Gemini).** DeepSeek output explaining a mathematical proof or algorithm: the mathematical steps are correct; the natural-language paraphrase introduces ambiguity, scope drift, or specific claims that the proof does not establish. The drift surfaces when a reader translates the natural-language explanation back to math and finds the translation does not match the proof.

6. **Wegovy stress-test language-mixing (Claude exec canonical worked example).** Wegovy multi-family stress test: DeepSeek language-mixed. The Chinese fragments in the reasoning output were the diagnostic signature distinguishing DeepSeek from the other families.

### Family-specific detection workflow

1. **A1 stylistic identification first.** If the piece exhibits A1-DEEPSEEK markers (especially A1-DEEPSEEK-001 `<think>` tag leakage in R1-specific output, A1-DEEPSEEK-002 language-mixing under reasoning load, A1-DEEPSEEK-003 lower English-prose polish, A1-DEEPSEEK-005 step-numbering in reasoning, A1-DEEPSEEK-007 heavy use of LaTeX in non-technical responses, A1-DEEPSEEK-009 OpenAI stylometric resemblance, A1-DEEPSEEK-010 "Based on the provided information"), apply DeepSeek-specific checks. The Unicode-detectable CJK character presence in an English document (A1-DEEPSEEK-002 in machine-actionable form) is the strongest single signal for DeepSeek family identification.

2. **Language-mixing scan.** Run a Unicode character-class scan over the piece. CJK character ranges (U+4E00 to U+9FFF for unified CJK ideographs; U+3000 to U+303F for CJK symbols and punctuation; U+3040 to U+309F for hiragana; U+30A0 to U+30FF for katakana) in an English document is the diagnostic signature. Even a single CJK character in a 5,000-word English piece flags DeepSeek-R1 reasoning-mode origin.

3. **Reasoning trace audit.** If the workflow has access to the reasoning trace (e.g., the model emitted `<think>` tags or the workflow logged the extended-thinking output), audit the trace for:
   - Assumptions stated and not verified.
   - Reasoning steps that contradict the final output.
   - Conclusions that exceed the supporting reasoning.
   The trace contamination signature surfaces in the trace, not in the final output, so the audit requires the trace.

4. **Chinese-source fabrication audit (V3 specific).** For DeepSeek V3 output touching historical, economic, or political topics about China or East Asia, cross-verify every statistic against English-language scholarly sources. Per Perplexity: V3 shows population-level fabrications reflecting training data composition. The fabrication may be invisible to readers without English-language access to the topic.

5. **Academic-paper citation audit.** For every academic paper citation in a DeepSeek piece, verify the paper exists. Per Gemini bucket-C contribution: DeepSeek invents plausible English-language academic paper titles and author attributions to support coding or technical decisions. Search Google Scholar, arXiv, NeurIPS proceedings, ICML proceedings, or the relevant venue's archive. A paper that cannot be located by title-and-author search is likely a fabrication.

6. **Technical-logic translation audit.** For DeepSeek output that translates math or code into natural language, translate back: take the natural-language explanation and ask whether it accurately describes the underlying math or code. Drift between the two is the technical-logic-to-natural-language hallucination signature.

7. **GPT-family fallback for non-reasoning-load output.** Per Copyleaks 2025 stylometric classification: under normal load, DeepSeek behaves much like GPT. Apply the GPT family verification workflow as the universal fallback when DeepSeek-specific signatures are not present.

### Cross-references

- **A1 stylistic fingerprints for family identification.** Highest-yield DeepSeek markers: A1-DEEPSEEK-001 (`<think>` tag leakage R1-specific), A1-DEEPSEEK-002 (language-mixing under reasoning load: the strongest single Unicode-detectable signal), A1-DEEPSEEK-003 (lower English-prose polish), A1-DEEPSEEK-004 (mathematical confidence bias), A1-DEEPSEEK-005 (step-numbering in reasoning), A1-DEEPSEEK-007 (heavy use of LaTeX in non-technical responses), A1-DEEPSEEK-009 (OpenAI stylometric resemblance), A1-DEEPSEEK-010 ("Based on the provided information").
- **C1-TOOLHALL-001 in detailed-protocols.md.** Full tool-specific verification procedure.
- **A1-GPT entries in synthesis-content-quality/references/model-family-fingerprints.md.** The Copyleaks-documented GPT stylometric resemblance means DeepSeek output without reasoning-load markers is often indistinguishable from GPT output; cross-checking the A1-GPT markers (sycophantic opener, saturated vocabulary, markdown formatting) is the disambiguator.
- **C1-SYNTH-001 in detailed-protocols.md.** DeepSeek's academic-paper fabrication for coding decisions is a synthetic-source pattern.

---

## Mistral

Models in scope: Mistral 7B, Mixtral 8x7B, Mistral Medium, Mistral Large, Codestral. Mistral family signatures are less heavily documented in the 2024 to 2026 bucket-C inputs than the Claude, GPT, Gemini, Llama, and DeepSeek families. The signatures below are practitioner observation with thinner empirical anchoring.

### Signature description

Mistral's hallucination signature center of gravity has two components, neither as empirically anchored as the canonical signatures of the larger families. First, European-corpus influence on cited works. Per practitioner observation across the bucket-C inputs (with the caveat that no specific bucket-C contribution highlighted Mistral as a primary family): Mistral models trained on a European-weighted corpus tend to cite European institutional sources, European academic publishers, and European regulatory bodies more frequently than the GPT or Claude families. When Mistral cites real European sources accurately, this is helpful for European-context content; when Mistral fabricates, the fabrications tend to follow European-corpus naming conventions (German-language journal titles, French-language institutional names, EU regulatory citation formats) that may be less familiar to English-language fact-checkers and harder to disambiguate from real citations.

Second, more direct refusal style affects how fabrications appear (less hedge-wrapped). Where Claude wraps refusals in alignment-trained hedge phrases and where GPT may confabulate rather than refuse, Mistral tends to either answer directly or refuse directly. Per A1-MISTRAL-002 (more direct refusal style) and A1-MISTRAL-006 (lower agent-reflex density): the absence of hedging produces a different signature for the hallucinations that do occur. When Mistral hallucinates, the hallucination is presented plainly rather than wrapped in qualifications. This is the same property that Llama exhibits (reduced hedging) but with a European-corpus tilt.

A third component, weaker: open-source-aware register. Per A1-MISTRAL-005: Mistral output reflects open-source community conventions, which may affect citation behavior. Mistral may preferentially cite open-source academic papers, open-access journal articles, or arXiv preprints over paywalled sources. This is neutral for verification quality but useful for identifying the family.

The compensating property: Mistral's concise default (A1-MISTRAL-007) and direct completion pattern (A1-MISTRAL-008) reduce the bulleted-bolded-lead-in fabrication risk seen in Claude (A1-CLAUDE-005) and GPT (A1-GPT-008) families. Mistral fabricates less elaborately. The fabrications, when they occur, are shorter and less structured. This makes them less likely to fool readers who are scanning for high-polish fabrication signals; it also makes them less likely to fool readers who do not scan.

### Empirical base rates

- **No per-family hallucination rate from Penn 2026 or AI Multiple 2026 reported in bucket-C inputs at the same granularity as Claude, GPT, Gemini, or Llama.** Mistral sits within the AI Multiple 15 to 52 percent cross-family bound.

- **European-corpus influence rate.** Not empirically anchored. Practitioner observation.

- **Reduced-hedging assertion rate.** Not empirically anchored as a Mistral-specific rate. Documented qualitatively as a family characteristic.

### Concrete examples

1. **European-source citation tilt.** Mistral output answering a question on European data protection: cites GDPR Article 28(3) and references the CNIL (Commission nationale de l'informatique et des libertés) decision against a French company. The citations may be accurate; the tilt toward French and EU sources is the family signature. When the question is about US data protection law and Mistral cites GDPR, the tilt may be inappropriate (US privacy law diverges from GDPR substantially).

2. **European-format fabrication.** Hypothetical Mistral output: cites a regulation "Verordnung (EU) Nr. 2024/XYZ" with a fabricated XYZ number that follows the German EU-regulation citation format. The fabrication is structurally correct for German EU citations; the specific regulation does not exist. The European-format polish makes the fabrication harder to spot for English-language fact-checkers unfamiliar with the German EU citation convention.

3. **Direct-style assertion without hedging (per A1-MISTRAL-002 / A1-MISTRAL-010).** Mistral output: "The treatment reduces mortality by 23 percent." No hedging, no caveats, no confidence interval. The assertion may be correct, or it may be a Mistral-family hallucination presented plainly. Without the hedge signal that Claude provides, the reader has less cue to verify.

4. **Open-source preprint preference.** Mistral output: "Per the recent arXiv preprint by Smith et al. (arXiv:2603.12345), the method achieves..." Verification: the arXiv preprint may or may not exist. Mistral's open-source-aware register makes arXiv citation the default; when the citation is fabricated, the fabrication takes arXiv-citation format.

5. **Concise fabrication.** Mistral output: "The 2023 European AI Act includes Article 5 prohibitions on real-time biometric identification." The statement is concise; some parts are correct (the European AI Act prohibitions on biometric identification); the specific article number may be wrong. The conciseness reduces the polish that obscures fabrication in larger-family outputs.

### Family-specific detection workflow

1. **A1 stylistic identification first.** If the piece exhibits A1-MISTRAL markers (especially A1-MISTRAL-001 French-influence syntax, A1-MISTRAL-002 more direct refusal style, A1-MISTRAL-003 lower saturated-vocabulary density, A1-MISTRAL-004 different default formatting, A1-MISTRAL-005 open-source-aware register, A1-MISTRAL-007 concise default, A1-MISTRAL-008 direct completion pattern, A1-MISTRAL-009 technical register dominance), apply Mistral-specific checks. Mistral identification is partly negative: the absence of A1-CLAUDE em-dash density and A1-GPT sycophantic opener, combined with European-corpus tilt and concise direct style, suggests Mistral.

2. **European-source verification.** For every European institutional citation (EU regulations, German Bundesgesetzbuch sections, French CNIL decisions, Spanish AEPD rulings, Italian Garante decisions), verify the citation against the original European source documents. English-language fact-checkers should be especially careful here because the European citation conventions are less familiar.

3. **European-format citation pattern audit.** Verify citations that follow German EU-regulation format ("Verordnung (EU) Nr. YYYY/NNNN"), French case citation format ("Cass. Civ., date, n° NNNN"), or Italian regulatory citation conventions. Per the European-format-fabrication risk: the structural correctness of the citation format does not indicate that the specific citation is real.

4. **Direct-style assertion audit.** For every confident assertion in a Mistral piece, apply the universal verification process from SKILL.md section 4. The absence of hedging is the Mistral family signature; the absence of hedging does not indicate verification.

5. **Open-source citation audit.** For arXiv, GitHub, or open-access preprint citations, verify each by resolving the arXiv identifier or the GitHub URL. Mistral's open-source-aware register makes these the default citation format; fabrications take the same format.

6. **Universal source-verification fallback.** Per the lack of strong Mistral-family empirical anchors, fall back to the universal verification procedure from SKILL.md sections 4 and the C1-URLROT-001 / C1-SYNTH-001 / C1-LAUNDER-001 trio for any non-European citations.

### Cross-references

- **A1 stylistic fingerprints for family identification.** Highest-yield Mistral markers: A1-MISTRAL-001 (French-influence syntax), A1-MISTRAL-002 (more direct refusal style), A1-MISTRAL-003 (lower saturated-vocabulary density), A1-MISTRAL-004 (different default formatting), A1-MISTRAL-005 (open-source-aware register), A1-MISTRAL-006 (lower agent-reflex density), A1-MISTRAL-007 (concise default), A1-MISTRAL-008 (direct completion pattern), A1-MISTRAL-009 (technical register dominance). Mistral identification is partly negative-signature based.
- **C1-TOOLHALL-001 in detailed-protocols.md.** Full tool-specific verification procedure.
- **A1-LLAMA-010 (reduced hedging and assertive claims).** Mistral shares the reduced-hedging property with Llama; the cross-reference helps when family identification is ambiguous.

---

## Qwen

Models in scope: Qwen 1, 2, 2.5, 3 across various sizes. Like Mistral, Qwen family signatures are less heavily documented in the bucket-C inputs at the empirical-anchor level than Claude, GPT, Gemini, Llama, and DeepSeek families. The signatures below are practitioner observation supplemented by A1 stylistic fingerprint inference.

### Signature description

Qwen's hallucination signature center of gravity has three components. First, Chinese-source bias. Qwen models, developed by Alibaba and trained on a Chinese-language-weighted corpus, preferentially cite Chinese-language sources, Chinese institutional bodies, and Chinese academic publishers. When Qwen cites real Chinese sources accurately, the citations are typically not English-translated, which makes verification difficult for English-language fact-checkers without Mandarin reading capability. When Qwen fabricates, the fabrications may follow Chinese citation conventions or may be in Chinese characters, which intersects with the A1-QWEN-001 (CJK punctuation slips, Unicode-detectable) and A1-QWEN-002 (Chinese cultural references and idiom translations) stylistic markers.

Second, CJK-language sources cited but not English-translated. Per A1-QWEN-001 and A1-QWEN-002: Qwen may cite a Chinese-language journal article by its Chinese title, a Chinese government white paper in original Chinese, or a Chinese academic publisher's series. The citation may be accurate; English-language fact-checkers cannot verify without Mandarin reading capability. The fabrication risk is asymmetric: if the source is real and the citation is real, the workflow is correct; if the source is fabricated, the fabrication is harder to detect without language access.

Third, less hallucination on Chinese-language facts. The compensating property: Qwen's Chinese-language training corpus is denser on Chinese topics than non-Chinese frontier models. For questions about Chinese history, Chinese culture, Chinese economic data, or Chinese political topics, Qwen typically produces lower hallucination rates than other families operating outside their training-corpus center of gravity. This is the mirror of DeepSeek V3's "population-level fabrications on historical statistics from Chinese sources" signature (per Perplexity bucket-C contribution): DeepSeek's Chinese-corpus exposure produces Chinese-narrative fabrications when prompted in English; Qwen's Chinese-corpus exposure produces correct Chinese-narrative responses when prompted in either Chinese or English.

A fourth component, weaker: heavier hedging on China-political topics. Per A1-QWEN-003: Qwen exhibits notably heavier hedging on topics related to Chinese political sensitivities. The hedging is a refusal-class behavior similar to Claude's safety hedging, but specific to Chinese political and historical topics. The fact-checking implication: a Qwen piece on a contested China-political topic that does NOT exhibit hedging may have been edited; the absence of hedging on these topics is itself a flag.

A fifth component: math-step formatting differences (per A1-QWEN-004) and specific phrasings translated from Chinese (per A1-QWEN-005). These are stylistic signatures that may compose with hallucination signatures but are primarily detection signals for family identification rather than for hallucination type.

### Empirical base rates

- **No per-family hallucination rate from Penn 2026 or AI Multiple 2026 reported in bucket-C inputs at the same granularity as Claude, GPT, Gemini, or Llama.** Qwen sits within the AI Multiple 15 to 52 percent cross-family bound.

- **Chinese-source citation rate.** Not empirically anchored. Practitioner observation supplemented by A1 stylistic markers.

- **Chinese-language-fact hallucination rate.** Qualitatively documented as lower than other frontier families operating on the same Chinese-language topics, but not empirically anchored in bucket-C inputs.

- **China-political hedging rate.** Qualitatively documented per A1-QWEN-003. Not empirically anchored.

### Concrete examples

1. **Chinese-language journal citation (untranslated).** Qwen output: "据《中国社会科学》(2024)的研究, [specific claim]." Translation: "According to research in 'China Social Sciences' (2024), [specific claim]." The journal exists; the specific 2024 research may or may not exist; English-language fact-checkers cannot easily verify without Mandarin access to the journal's archive.

2. **CJK punctuation slip (per A1-QWEN-001, Unicode-detectable).** Qwen output: contains Chinese full-width punctuation (`，` U+FF0C instead of `,` U+002C; `。` U+3002 instead of `.` U+002E; `「` and `」` instead of `"` and `"`) in an English document. The punctuation slip is the diagnostic signature. Even one instance flags the family.

3. **Chinese government white paper citation.** Qwen output: cites "the State Council's 2025 white paper on AI development." The white paper may exist (the State Council issues many white papers); the specific 2025 white paper may or may not exist; English-language coverage may be sparse, making verification harder.

4. **Lower hallucination on Chinese topics.** Qwen output on the Three Kingdoms period: cites specific battles, generals, and dates that match Sanguozhi (the primary historical source). Verification: substantially correct. Qwen's Chinese-corpus training produces low hallucination on canonical Chinese historical topics; the same questions to other frontier families produce higher fabrication rates.

5. **Heavy hedging on contested China-political topic (per A1-QWEN-003).** Qwen output on a question about Taiwan, Tibet, Xinjiang, or Hong Kong political status: extensively hedged, may decline to take a position, may reframe the question. The hedging is the family signature. The absence of hedging in a Qwen-styled piece on these topics suggests editorial intervention.

6. **Specific phrasing translated from Chinese (per A1-QWEN-005).** Qwen output: contains phrases that are literal translations from Chinese idioms ("opening up reform" calque from "改革开放"; "harmonious society" calque from "和谐社会"). The calques are stylistic markers and may also indicate that an underlying Chinese-corpus claim is being translated rather than independently sourced.

### Family-specific detection workflow

1. **A1 stylistic identification first.** If the piece exhibits A1-QWEN markers (especially A1-QWEN-001 CJK punctuation slips Unicode-detectable, A1-QWEN-002 Chinese cultural references and idiom translations, A1-QWEN-003 heavier hedging on China-political topics, A1-QWEN-004 math-step formatting differences, A1-QWEN-005 specific phrasings translated from Chinese, A1-QWEN-007 lower idiomatic-English density, A1-QWEN-008 "Below is a detailed explanation:", A1-QWEN-010 formal almost textbook tone), apply Qwen-specific checks. The Unicode-detectable CJK punctuation (U+FF0C, U+3002, full-width forms) is the strongest single signal for Qwen family identification.

2. **CJK punctuation scan.** Run a Unicode character-class scan over the piece. Presence of CJK full-width punctuation (U+FF00 to U+FFEF block) in an English document is diagnostic for either Qwen or DeepSeek; the distinction comes from whether the CJK characters appear as content (DeepSeek language-mixing in reasoning) or as punctuation slips (Qwen).

3. **Chinese-language source audit.** For every cited Chinese-language source (Chinese journal articles, Chinese government white papers, Chinese academic publishers, Chinese institutional reports), verify the source exists. If the workflow has Mandarin reading capability, verify the claim against the source. If not, document the limitation and either escalate to a Mandarin-reading verifier or treat the claim as unverified.

4. **Chinese-topic hallucination audit (inverted-priority).** For Chinese historical, cultural, political, or economic topics, Qwen typically produces lower hallucination than other families. The verification can proceed at standard intensity rather than elevated intensity for these topics. For non-Chinese topics, Qwen exhibits family-typical hallucination rates and the standard universal verification applies.

5. **China-political hedging-absence audit.** If the piece is a Qwen-styled output on a contested China-political topic and does NOT exhibit the expected hedging (per A1-QWEN-003), flag for editorial-pass investigation. The hedging removal may be intentional but should be verified rather than assumed.

6. **Calque audit.** For phrases that are literal translations from Chinese idioms or political vocabulary, check whether the underlying claim is a translation from Chinese sources rather than independently sourced from English material. Calques often indicate single-source dependence on Chinese-language material.

7. **Universal source-verification fallback.** Per the lack of strong Qwen-family empirical anchors in the bucket-C inputs, fall back to the universal verification procedure from SKILL.md section 4 and the C1 protocols for any non-Chinese citations.

### Cross-references

- **A1 stylistic fingerprints for family identification.** Highest-yield Qwen markers: A1-QWEN-001 (CJK punctuation slips Unicode-detectable, strongest single signal), A1-QWEN-002 (Chinese cultural references and idiom translations), A1-QWEN-003 (heavier hedging on China-political topics), A1-QWEN-004 (math-step formatting differences), A1-QWEN-005 (specific phrasings translated from Chinese), A1-QWEN-007 (lower idiomatic-English density), A1-QWEN-008 ("Below is a detailed explanation:"), A1-QWEN-009 (overuse of "Moreover," and "In addition,"), A1-QWEN-010 (formal almost textbook tone).
- **C1-TOOLHALL-001 in detailed-protocols.md.** Full tool-specific verification procedure.
- **A1-DEEPSEEK-002 (language-mixing under reasoning load) in synthesis-content-quality/references/model-family-fingerprints.md.** Both Qwen and DeepSeek produce CJK characters in English documents; the distinction is whether the characters are content (DeepSeek reasoning) or punctuation (Qwen formatting slip).
- **C1-TRANS-001 (source-translation drift) in detailed-protocols.md.** Qwen's translation from Chinese sources to English output is a translation-drift risk; the C1-TRANS-001 protocol applies.
