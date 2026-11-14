# Detailed protocols, part 3: model families and incidents

Part 3 of three, split from [detailed-protocols.md](detailed-protocols.md) so each part can be read in one pass. The text is verbatim, and the index's em-dash audit covers this part.

Contents:
- C1-TOOLHALL-001: tool-specific hallucination patterns, per model family
- Production-incident archive: the incidents cited across the C1 protocols, as a quick reference

---

## C1-TOOLHALL-001: Tool-Specific Hallucination Patterns (Per-Family Fabrication Signatures)

### Pattern description

Different LLM families produce hallucinations with characteristic signatures, reflecting their unique architectures, training data, and alignment strategies. Identifying the model family helps prioritize which types of errors to check. This parallels Bucket A1 (model-family stylistic fingerprinting) but focuses on fact-fabrication patterns rather than style patterns. The per-family signature is the bucket-C parallel to bucket-A's stylistic fingerprinting.

The protocol is operational rather than theoretical: each family has a predictable failure shape, and family-aware verification reduces the surface area of checks. A document known to be Claude-generated should have every DOI verified; a document known to be GPT-generated should have every URL verified; a document known to be Gemini-generated should have every "studies show" or "experts say" attribution chased for specifics; a document known to be DeepSeek-generated should be checked for language-mixing residue; a document known to be Llama-generated above 32K context should be audited for long-context confabulation; a document known to be Grok-generated should be audited for tweet-source citations and Musk-X bias.

### Why this happens

Differences in training mixtures, alignment objectives, and post-training data create family-specific blind spots and fabrication styles. Each model's training data distribution and generation tendencies influence the form of its confabulations. Claude's academic training leads to reference-style confabulation; GPT's web-scale training leads to URL construction; Grok's social media focus leads to tweet simulation. The underlying RLHF mechanisms and training data skews force models to fill knowledge gaps using their default structural rhythms.

Causal hypothesis ranked: (1) tokenizer or architecture effects; (2) training-data skew; (3) alignment and safety tuning (models may fill gaps with plausible but false information to avoid refusal); (4) product wrapper effects (search-augmented modes differ from API modes).

### Failure modes (general, across families)

The cross-family failure modes are:

1. Family-specific fabrication shape goes undetected because the reviewer applies a generic check rather than a family-aware check (a Claude DOI fabrication is not caught by a URL fetch; a GPT URL fabrication is not caught by a DOI lookup).
2. Model identity is unknown or undocumented, preventing family-aware verification. The fact-checker treats all AI output uniformly when the failure shapes differ by family.
3. Cross-family check shows divergence but no flag is raised (the same prompt across families produces six different answers; the divergence itself is diagnostic of low confidence in any single answer).
4. Wrapper, version, or tool state is unrecorded, so the failure cannot be attributed to a specific family configuration (Gemini deep-research mode and Gemini search-augmented mode have different hallucination rates; an undifferentiated "Gemini" label loses the information needed to verify).
5. Reasoning-trace contamination is not checked when the model exposes a reasoning trace (DeepSeek-R1, GPT-o1, Claude extended-thinking); incorrect reasoning steps may contradict the final output and the contradiction is itself a verification opportunity.
6. Per-family verification priority is not followed, so the highest-yield checks per family are not run first; the reviewer spends time on low-yield checks while high-yield ones are skipped.

The per-family signatures below provide the operational catalog of family-specific failure shapes.

### Per-family signatures (consolidated from all inputs)

The signatures below are the consolidated synthesis of seven independent deep-research inputs plus the Opus 4.7 expansion. Per-family content distinguishes the families' characteristic fabrication shapes; the worked examples illustrate each shape; the verification priorities tell the reviewer where to look first.

#### Claude (Anthropic)

- Lowest URL hallucination rate among tested families (3.0 to 3.2 percent hallucinated URLs; Penn 2026).
- Hedges appropriately when uncertain, making hallucinations lower-frequency but similar in polish to GPT hallucinations.
- Domain-specific: high non-resolving rate in Healthcare/Medicine (17.4 percent) vs. Mathematics (4.0 percent). Medical citations from Claude require heightened scrutiny.
- Attribution errors: Claude tends to conflate positions held by multiple speakers and attribute them to the most prominent named figure.
- Correction behavior: responds well to self-correction when given verification tools (6.4x improvement with urlhealth).
- **DOI fabrication signature.** Claude overproduces plausible-seeming DOIs (`doi:10.1038/s41586-XXXX-NNNNN-N` correctly formatted but resolving to a different paper or to nothing). Fabricates plausible DOIs and article titles in formal academic style. Tends to create whole paper references that look real but cannot be found.
- Tends to hallucinate "nuanced" but non-existent details, often creating plausible-sounding but ultimately false elaborations or qualifications.
- Invents non-existent ethical guidelines or legal statutes to justify refusing a prompt it does not understand.
- Refuses on contested ground where other families confabulate; the refusal pattern is itself a signature.
- Lower polished quote-smoothing or evidential over-compression than GPT-4o.

**Verification priority for Claude output:** check Healthcare/Medical citations first; verify every DOI by resolving via doi.org; audit ethical-guideline citations and legal-statute citations for invention.

#### GPT-4o / GPT-4.1 / GPT-5 / GPT-5.5 (OpenAI)

- URL hallucination rate 5.4 to 8.8 percent for search-augmented models; notably, ALL non-resolving URLs from these models are hallucinated (zero stale fraction), indicating URL generation from parametric memory rather than retrieval (Penn 2026).
- Confident wrong specifics (error pattern 4c) is highest here. MIT research (cited in Claritybot 2026): models are 34 percent more likely to use confident language when generating incorrect information.
- Hallucination rate varies by topic: 18.7 percent on legal queries, 15.6 percent on medical queries (Claritybot 2026, citing SuprMind 2026).
- o-series specific: displays explicit uncertainty hedges in text, but the hedge language underestimates the actual error rate. "I should note there is some uncertainty" does not tell you which specific claims are wrong.
- **URL fabrication signature.** URLs on real domains that 404 (`nytimes.com/2024/03/article-that-never-existed`). Invents URLs on real domains. The domain is real; the path is fabricated.
- Tends to hallucinate plausible-sounding citations, names of researchers, or specific statistics that do not exist, often with a high degree of confidence.
- High polish plus guess-prone specificity and fabricated supporting detail under pressure.
- **Perfect-markdown-timeline signature.** Invents a flawless three-point historical timeline with perfect markdown formatting, but the dates are fabricated.
- Generates highly structured, sequential fictions.
- Per Damien Charlotin's database, over 1,455 sanctioned legal cases involve AI-fabricated citations as of 2025, with GPT family heavily represented.

**Verification priority for GPT output:** check legal and medical queries first; assume any non-resolving URL is hallucinated; verify every URL by attempting resolution; rigidly verify chronological timelines, bulleted lists, and statistical data tables.

#### Gemini (Google)

- Deep research mode: 13.3 percent hallucinated URL rate (highest of any model tested), despite high citation volume and strong overall quality scores.
- Search-augmented modes: 4.6 to 4.8 percent hallucination rate (comparable to Claude).
- Best response to self-correction: 79x improvement with urlhealth, achieving 0.1 percent hallucination after correction.
- Domain variation: consistent low non-resolving rates (2.5 to 10.2 percent across fields), but Healthcare/Medicine is problematic at 5.3 percent.
- Hallucination signature: Gemini deep-research mode may blend URL patterns from retrieved pages to produce plausible but non-existent addresses.
- **Vague attribution signature.** Drifts under reasoning load to vague "studies show" or "experts say" assertions without identifiers, making them hard to verify but not easily falsifiable.
- Generates vibrant but fabricated examples or scenarios that fit a narrative but lack factual basis.
- Search wrapper source problems, including fabricated or copied citations, despite stronger benchmarked factuality in some settings.
- Secondary-indication invention under reasoning (Claude exec): Wegovy multi-family stress test revealed Gemini fabricating secondary off-label indications.

**Verification priority for Gemini output:** apply URL verification to all citations; flag every vague attribution ("studies show," "experts say," "research indicates") for specific-source verification; in deep-research mode, audit URLs aggressively.

#### Llama (Meta)

- Higher rate of bold factual errors with lower hedging. Llama asserts incorrectly more often than Claude or GPT but hedges the assertion less, making the error easier to spot.
- Entity name errors (4d) are more pronounced in smaller Llama models (8B range).
- Limited source grounding in base models; RAG-extended versions reduce hallucination substantially.
- **Long-context fabrication signature.** Above 32K context length (approximate threshold per RIKER benchmark, Claude exec, flagged for verification by Opus expansion): factual confabulation increases substantially. The threshold figure should be verified during synthesis.
- May hallucinate technical details or code snippets that are syntactically correct but functionally flawed or non-existent.
- Hallucinates statistics with precise-seeming numbers (for example "47.3 percent") that are baseless.
- Fabricates above 32K context per RIKER (Claude exec).

**Verification priority for Llama output:** check entity names; verify all specific statistics; audit confabulation risk in long-context analysis (above 32K tokens approximate threshold); for code, verify functional correctness rather than syntactic plausibility.

#### DeepSeek (V2, V3, R1)

- Stylometrically classified as OpenAI-like by Copyleaks; hallucination patterns are similarly GPT-like.
- Reasoning trace contamination is a unique failure mode: when reasoning traces are exposed, they may contain incorrect reasoning steps that contradict the final output.
- V3 specifically shows population-level fabrications on historical statistics from Chinese sources, reflecting training data composition.
- **Language-mixing signature.** Language-mixing under reasoning load: reasoning trace contains Chinese characters that the final output may or may not retain. DeepSeek-R1 extended-thinking output may include "我们需要考虑" in a primarily English response.
- Hallucinates heavily when translating technical logic into natural language.
- Invents highly plausible English-language academic paper titles and author attributions to support a coding decision.

**Verification priority for DeepSeek output:** check for language-mixing residue (Chinese characters in primarily-English output); rigidly verify English-language academic paper titles and author attributions against Google Scholar; if reasoning trace is exposed, audit reasoning steps against final output for contradiction.

#### Grok (xAI)

- May hallucinate humorous or irreverent "facts" that align with its persona but are factually incorrect.
- **Tweet fabrication signature.** May fabricate social media posts or tweets as sources, leveraging its platform-aware persona.
- Search-centric outputs were citation-riskier earlier than recent reasoning variants.
- Grok 4 uses Elon Musk's X posts as a source when answering questions (Mashable 2026 documentation).

**Verification priority for Grok output:** verify social media post citations against the live platform; check for X/Musk-source bias; cross-check humorous or irreverent claims against authoritative sources.

### Concrete examples in context

1. *Manus AI example for Claude.* Tends to hallucinate "nuanced" but non-existent details, often creating plausible-sounding but ultimately false elaborations or qualifications.

2. *Manus AI example for GPT.* Tends to hallucinate plausible-sounding citations, names of researchers, or specific statistics that do not exist, often with a high degree of confidence.

3. *Manus AI example for Gemini.* Tends to hallucinate "vibrant" but fabricated examples or scenarios that fit a narrative but lack factual basis.

4. *Manus AI example for Llama.* May hallucinate technical details or code snippets that are syntactically correct but functionally flawed or non-existent.

5. *Manus AI example for Grok.* May hallucinate humorous or irreverent "facts" that align with its persona but are factually incorrect.

6. *Grok worked example.* A draft with strong Claude-family hedging and participial patterns also contains several citations to non-existent think-tank reports on niche regulation. The style fingerprint raises prior probability that the citations require extra verification. (Cross-reference: A1 stylistic fingerprinting.)

7. *Gemini example for Claude.* Claude invents a non-existent ethical guideline or legal statute to justify refusing a prompt it does not understand. The refusal pattern carries fabricated reasoning.

8. *Gemini example for GPT.* GPT invents a flawless three-point historical timeline with perfect markdown formatting, but the dates are fabricated. The polish is the camouflage.

9. *Gemini example for DeepSeek.* DeepSeek invents a highly plausible English-language academic paper title and author attribution to support a coding decision.

10. *Claude Opus 4.7 expansion example for Claude.* "According to Smith et al. 2023, doi:10.1038/s41586-2023-12345-6, ..." DOI resolves to a different paper. The format is correct; the content is wrong.

11. *Claude Opus 4.7 expansion example for GPT.* "https://nytimes.com/2024/05/15/business/tech-merger-analysis ..." URL returns 404. The domain is real; the path is fabricated.

12. *Claude Opus 4.7 expansion example for Gemini.* "Research indicates that 30 percent of teams experience this issue." No source named.

13. *Claude Opus 4.7 expansion example for DeepSeek.* DeepSeek-R1 extended-thinking output: "我们需要考虑..." (Chinese characters in a primarily English response).

14. *Claude Opus 4.7 expansion example for Llama.* Llama on a 40K-token document analysis: confidently states facts not in the document. The context window has exceeded the model's reliable retrieval range; confabulation fills the gap.

15. *Claude exec canonical worked example.* Wegovy multi-family stress test. The canonical multi-family fact-checking stress test from the Claude exec asked six families the same question about Wegovy (semaglutide) indications. Family profiles emerged: Claude refused on contested off-label indications; GPT confabulated with plausible URLs and case citations; Gemini drifted under reasoning with secondary-indication invention (fabricating off-label uses with no clinical evidence); Llama fabricated above 32K context (when the prompt included long surrounding documentation); DeepSeek language-mixed in reasoning trace; Grok cited X posts. The same prompt produced six different failure shapes, each diagnostic of the family.

### Step-by-step procedure for tool-specific verification

1. Identify which model generated the content (if known from workflow documentation). Record model family, precise version, wrapper, and whether search or tools were enabled.
2. Apply the appropriate priority check:
   - Claude: check Healthcare/Medical citations; verify every DOI by resolving via doi.org; audit ethical-guideline and legal-statute invocations.
   - GPT: check legal and medical queries; assume any non-resolving URL is hallucinated; verify every URL; rigidly verify chronological timelines, bulleted lists, and statistical data tables.
   - Gemini deep-research: apply URL verification to all citations; flag every vague attribution.
   - Llama: check entity names; verify all specific statistics; audit confabulation risk in long-context analysis (above 32K tokens approximate).
   - DeepSeek: check for language-mixing; rigidly verify English-language academic paper titles and author attributions against Google Scholar.
   - Grok: verify social media post citations; check for X/Musk-source bias.
3. For unknown model: apply the general citation verification procedure from v1.1.0 Section 4f plus the URL classification procedure from C1-URLROT-001.
4. Cross-reference with the A1 stylistic fingerprint (synthesis-content-quality) to confirm family identification.
5. Test failure mode classes separately: unsupported guessing, source fabrication, citation mismatch, paraphrase drift, and position drift.
6. Catalogue the hallucination's format (DOI, URL, person, statistic, generic attribution). Cross-reference with known family signatures. Verify accordingly (DOI lookup, URL fetch, etc.).
7. Apply family-specific remediation: DOI lookup for Claude; URL resolution for GPT; specific-source demand for Gemini; language-purity for DeepSeek; long-context-fabrication audit for Llama.
8. Record the model and version as required metadata. Per ChatGPT input, claims about "Gemini" or "GPT" without the surrounding surface, app, API, search mode, and date are often underspecified; v2.0 should make model version, wrapper, and tool state required metadata whenever a reviewer records a pattern or failure.

### Sources

Rao, Wong, Callison-Burch (2026) arXiv:2604.03173 (per-family hallucination percentages); Claritybot journalism guide 2026; AI Multiple benchmark report Jan 2026 (15 to 52 percent hallucination across 37 LLMs); Copyleaks 2025 (DeepSeek stylometric classification); RIKER benchmark arxiv 2603.08274 (Llama long-context fabrication; threshold figure flagged for synthesis verification); Mashable 2026 (Grok X-post source bias); Sharma et al. arxiv 2310.13548 (sycophancy across families); academic papers on LLM hallucination detection and mitigation; comparative empirical studies of multiple model outputs on identical prompts; Claude exec 2026-05-18 (Wegovy canonical stress test).

### Signal strength, base rate, detection difficulty, false-positive risk

- **Signal strength.** MED (pattern knowledge helps prioritize; does not replace individual verification). HIGH when a family-specific signature is identified.
- **Base rate.** Varies significantly by model, prompt, and domain. Penn 2026 percentages provide the empirical baseline; AI Multiple 15 to 52 percent range across 37 LLMs provides the upper bound.
- **Detection difficulty.** Medium. Requires familiarity with different models' common failure modes.
- **False positive risk.** MED. Individual hallucinations do not follow family patterns consistently. These are specific, identifiable patterns when present, but presence does not predict every instance.

### Remediation

Cross-verify all factual claims with independent, human-authored sources. Be aware of the specific hallucination tendencies of the LLM being used. Implement self-correction mechanisms (for example asking the model to justify its claims). Apply family-specific verification: DOI lookup for Claude; URL resolution for GPT; specific-source demand for Gemini; language-purity for DeepSeek; long-context-fabrication audit for Llama. Delete the hallucination and prompt a different model family for cross-verification.

For editorial workflow, the family-specific verification can be packaged as a checklist per family. A fact-checker who knows the model family can run a targeted 10-minute check that catches the highest-probability failures; without family knowledge, the general protocol takes 30 to 60 minutes and may miss family-specific shapes.

### Era status

Active. Constantly evolving as models are updated and fine-tuned. Per ChatGPT input, claims about "Gemini" or "GPT" without the surrounding surface, app, API, search mode, and date are often underspecified; v2.0 makes model version, wrapper, and tool state required metadata whenever a reviewer records a pattern or failure.

### Cross-references

- C1-URLROT-001: per-family URL fabrication patterns determine the URL classifications to expect. GPT's URL fabrication signature concentrates HALLUCINATED with real-domain camouflage; Claude's lower URL hallucination rate spreads more evenly across STALE and HALLUCINATED.
- C1-SYNTH-001: per-family synthetic-source generation patterns (DeepSeek fake-journal citations, Claude synthetic-expert credentials, Gemini synthetic-statistic attributions) shape what synthetic sources to expect from which family.
- C1-LAUNDER-001: per-family laundering signatures (Gemini's vague attribution often serves as a laundering intermediate node; GPT's confident specifics often serve as a fabricated upstream).
- C1-NESTED-001: per-family nested-attribution flattening varies (Claude tends to preserve more layers; GPT compresses more aggressively).
- C1-COMPOSITE-001: per-family composite-quote signatures vary (GPT's high-polish composite quotes are hardest to detect; Llama's are more obvious due to lower fluency above 32K context).
- C1-POSSHIFT-001: per-family position-shifting biases vary (Claude's constitutional-AI training produces "balanced" position-shifting toward the middle; GPT's training on opinion content produces stronger position imports).
- v1.1.0 4f (Hallucinated Citations): the per-family signatures here provide the operational shape of the v1.1.0 single-bucket failure mode; family identification reduces the verification surface area.
- synthesis-content-quality A1 (Model-Family Fingerprinting): the stylistic signatures in A1 and the fabrication signatures here are parallel; identifying one helps identify the other; cross-referencing both improves family identification confidence.

---

## Production-incident archive (cross-protocol reference)

The following 2025-2026 incidents are referenced across multiple C1 protocols. They are preserved here as a quick-reference archive; full detail lives in `references/production-incident-archive.md`.

- **Mostafavi sanction (2025).** Court sanction for legal filings citing fabricated cases. Claude exec gives $10,000 figure; Opus expansion flagged the specific dollar amount and date for verification noting multiple Mostafavi cases exist and disambiguation may be needed. Cross-validated with CalMatters September 2025 coverage per Claude exec bibliography. Relevant to: C1-URLROT-001, C1-LAUNDER-001, C1-TOOLHALL-001 (GPT URL fabrication).
- **Goldberg Segalla sanction (2025).** Larger sanction for similar AI-fabricated-citation pattern. Claude exec gives $60,000 figure; Opus expansion flagged the specific details for verification. Per Damien Charlotin's database (cited in Claude exec, Opus expansion flagged the specific database existence for verification), over 1,455 sanctioned legal cases involve AI-fabricated citations as of 2025. The case is referenced as the Goldberg Segalla CHA sanction in Claude exec bibliography, December 2025. Relevant to: C1-URLROT-001, C1-SYNTH-001, C1-LAUNDER-001, C1-TOOLHALL-001.
- **Chicago Sun-Times summer reading list (2025).** Newspaper published a summer reading list with multiple books that did not exist; the books had plausible titles by real authors but were AI fabrications. Cross-validated by NPR May 2025 coverage per Claude exec bibliography. Relevant to: C1-SYNTH-001, C1-TOOLHALL-001.
- **Springer "Mastering Machine Learning" book (2025).** A Springer-published book on machine learning that contained AI-fabricated citations to non-existent papers, with two-thirds of references fabricated. Retraction Watch April 2025 coverage. Relevant to: C1-SYNTH-001, C1-LAUNDER-001.
- **BBC/EBU 45 percent significant-issues rate (2025).** BBC/European Broadcasting Union News Integrity report (October 2025) found that 45 percent of AI-generated responses to news questions contained significant issues (factual errors, missing context, or attribution problems). Relevant to: all C1 protocols as baseline prevalence anchor.
- **Topaz et al. May 2026 Lancet letter.** One in 277 PubMed papers in 2026 referenced a fabricated paper; twelve-fold rise from 2023 per Claude exec; sixfold rise from 2023 to 2025 per Perplexity citation of the same study. STAT News coverage 2026-05-06. Venue flagged for verification by Opus expansion. Relevant to: C1-SYNTH-001, C1-LAUNDER-001.
- **Damien Charlotin's AI Hallucination Cases Database.** Over 1,455 sanctioned legal cases involve AI-fabricated citations as of 2025. Relevant to: C1-URLROT-001, C1-TOOLHALL-001.
- **Stanford RegLab Magesh et al. June 2024.** 17 to 33 percent legal-AI hallucination rates with RAG. Relevant to: C1-URLROT-001, C1-SYNTH-001, C1-TOOLHALL-001.
- **Mata v. Avianca (2023).** Attorney sanctioned for AI-generated legal brief with fabricated case citations. Established the legal consequence baseline. Relevant to: C1-URLROT-001, C1-TOOLHALL-001.
- **Tsinghua ICLR paper.** Withdrawn after AI-generated references were identified by reviewers. Relevant to: C1-SYNTH-001.
- **MAHA Report (2025).** White House chronic disease report contained multiple incorrect citations suspected AI-generated; widely publicized. Relevant to: C1-SYNTH-001, C1-LAUNDER-001.
- **Megalopolis trailer controversy (2024).** Involved fabricated or misattributed critic quotes. Relevant to: C1-NESTED-001, C1-COMPOSITE-001.
- **Washington Post AI-generated podcast scripts (2026).** Found fabricated and misattributed quotations in production testing. Relevant to: C1-NESTED-001, C1-COMPOSITE-001, C1-PARAPH-001.
- **Nieman Lab Margaux Blanchard/Victoria Goldiee February 2026.** Synthetic-byline contamination case. Relevant to: C1-SYNTH-001.
- **Google AI Overviews 2025 year-bug.** Wrong year framing in AI-generated overviews; canonical 4a example per Claude exec. Relevant to: v1.1.0 4a (cross-reference; not C1-specific).
