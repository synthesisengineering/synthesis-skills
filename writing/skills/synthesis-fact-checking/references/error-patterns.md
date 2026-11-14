# Fact-checking: error patterns, C1 protocols, family signatures

Sections 4, 5 and 6 of the fact-check process, verbatim apart from link paths adjusted for this folder. Section numbers are the ones other documents cite. Each summary points to the reference file with the full protocol.

Contents:
- 4. Common Error Patterns: 4a wrong framing, 4b conflated findings, 4c wrong specifics, 4d wrong entity names, 4e misattribution, 4f hallucinated citations (split into C1 protocols) with the canonical 2025-2026 incidents, 4g outdated data
- 5. The nine C1 protocol sections: one-paragraph summaries
- 6. Per-Family Hallucination Signatures: summary for eight model families

## 4. Common Error Patterns (REFRESHED for v2.0)

The most frequent error types in fact-checking AI-synthesized content, with 2025-2026 production examples.

### 4a. Wrong Framing of Correct Numbers

The number is right, the description of what it measures is wrong.

**Example:** Draft says "$4.4 trillion in productivity growth potential"; source says "$4.4 trillion in economic value added." The number is correct; the characterization is not.

**How to catch:** When verifying a statistic, do not just confirm the number. Read the sentence in the primary source and compare full framing.

**2025-2026 example.** Treatment outcome from a single-cohort study reframed as a general population effect in AI summaries; revenue growth from a specific quarter presented as annual growth.

### 4b. Conflating Related but Distinct Findings

Two findings from the same source merged into one.

**Example:** "96 percent of companies are reinvesting productivity gains from AI" conflates "96 percent of companies experienced productivity gains" (one finding) with "companies are reinvesting gains" (a separate, qualitative finding without a percentage).

**How to catch:** When a claim attributes both a number and a qualitative description to the same source, verify they belong to the same finding.

**2025-2026 example.** Confusing GPT-4 hallucination rates with GPT-4o; conflating Claude 3 Sonnet performance with Claude 4.

### 4c. Wrong Specifics from Correct General Findings

Direction is right, specific number is wrong.

**Example:** Draft says "67 percent of workers reported reduced burnout"; source says 71 percent reported reduced burnout, 67 percent came from a different metric.

**How to catch:** When verifying a specific number, confirm it belongs to the exact finding described.

### 4d. Incorrect Organization or Entity Names

Wrong name for an organization; parent/subsidiary confusion.

**How to catch:** Verify organization names against official materials.

**2025-2026 example.** "Institute for Digital Trust" cited as research source when no such institute exists; "The Cybersecurity Foundation" cited when source named a different organization.

### 4e. Misattributing Quotes or Examples to Wrong Entities

Two examples from different entities attributed to one entity. Cross-reference C1-NESTED-001 for nested attribution failure modes.

**How to catch:** For any claim combining a concrete example with a quote, verify both originate from the same entity.

**2025-2026 example.** Quote attributed to one CEO actually said by another; statement attributed to a paper's lead author actually in the paper's appendix written by a co-author.

### 4f. Hallucinated Citations (DEMOTED to split bucket in v2.0)

In v1.1.0, this was a single bucket. v2.0 splits it into:

- **C1-URLROT-001** (URL rot vs hallucination distinction): cited URLs that fail to resolve. Hallucinated (fabricated, never existed) versus rotted (real-but-changed) require different remediation. See [references/detailed-protocols-sources.md](detailed-protocols-sources.md) section C1-URLROT-001.
- **C1-SYNTH-001** (AI-generated synthetic sources): citations to "studies," "experts," or "news articles" that turn out to be AI-generated content presented as authoritative. See detailed-protocols.md.
- **C1-LAUNDER-001** (Citation laundering chains): citations that trace back to a single AI-generated upstream. See [references/citation-laundering-detection.md](citation-laundering-detection.md).
- **Residual pure-fabrication.** DOIs that resolve to nothing, papers that do not exist, authors who do not exist. The rump 4f after the three new C1 sections take their share. Apply Study Verification Protocol (section 8).

**Canonical 2025-2026 incidents** (full detail in [references/production-incident-archive.md](production-incident-archive.md)):

- **Mostafavi sanction (2025).** $10,000 sanction in California 2nd District Court of Appeal Div 3, Sept 2025. 21 of 23 quotes in legal filing fabricated.
- **Goldberg Segalla sanction (2025).** $59,500 total ($10,000 attorney + $49,500 firm), Cook County, Dec 9 2025.
- **Damien Charlotin's database.** 1,455 sanctioned legal cases involving AI-fabricated citations as of 2025.
- **Chicago Sun-Times summer reading list (May 18, 2025).** 10 of 15 books listed did not exist. Buscaglia / King Features Syndicate.
- **Springer "Mastering Machine Learning" book (April 2025, retracted Aug 2025).** Madhavan, $169. Two-thirds of sampled citations fabricated.
- **BBC/EBU report (October 2025).** 45 percent of AI-generated news responses contained significant issues; 76 percent for Gemini.
- **Topaz et al. May 2026 Lancet letter.** 1 in 277 PubMed papers in 2026 referencing a fabricated paper, twelvefold rise from 2023.
- **Stanford RegLab Magesh measurement.** 17 to 33 percent legal-AI hallucination rate with RAG. 202 queries, JELS 2025.

### 4g. Outdated or Superseded Data

Older figures used when newer data is available; preliminary findings cited that were revised in final publication.

**How to catch:** For recurring reports (annual indexes, quarterly surveys), check if a more recent edition exists. For working papers, check for final version.

---

## 5. Nine New Protocol Sections for v2.0 (C1)

The nine new protocol sections address structural gaps in v1.1.0 that have become urgent under the 2025-2026 recursive-contamination problem. Each section has full detail (failure modes, worked examples, detection protocol, sources, remediation) in [references/detailed-protocols.md](detailed-protocols.md).

### Section summary

- **C1-NESTED-001.** Second-party and third-party quote handling. Quotes that pass through multiple speakers have multiple drift points. Detection protocol: trace attribution chain back to original speaker.
- **C1-PARAPH-001.** Paraphrase boundary drift (bidirectional). Source's epistemic frame lost in summary; quotation marks added to non-quoted paraphrase. Per the 500-summary audit cited in research (source flagged for verification), 11 percent of AI-generated news summaries contained composite quotes and 8 percent added quotation marks.
- **C1-COMPOSITE-001.** Composite quotes. Non-contiguous source fragments stitched into a single quoted utterance. Detection: verify exact word sequence appears in source as one continuous quote.
- **C1-POSSHIFT-001.** Position-shifting (framing drift). Source's stated position shifted toward more balanced framing than source held. Common with Claude-family due to constitutional-AI training toward balanced presentation.
- **C1-TRANS-001.** Source-translation drift. AI-translated quotes from non-English sources without professional translation cited; translation-of-translation chains undocumented.
- **C1-URLROT-001.** URL rot versus hallucination distinction. Six-category taxonomy: HALLUCINATED, STALE, REDIRECTED, RETRACTED, PAYWALLED, UPDATED. Each requires different remediation.
- **C1-SYNTH-001.** AI-generated synthetic sources. Citations to "studies" that are AI blog posts; "experts" that are synthetic identities; "news articles" that are content-farm output. Per Retrieval Collapse research (arxiv 2602.16136 cited; verification flagged), 67 percent pool contamination yields 80 percent exposure contamination.
- **C1-LAUNDER-001.** Citation laundering chains. Apparent multi-source corroboration collapses to single AI-generated upstream. Full graph-traversal protocol in [references/citation-laundering-detection.md](citation-laundering-detection.md).
- **C1-TOOLHALL-001.** Tool-specific hallucination patterns. Per-family signatures: Claude DOI fabrication, GPT URL fabrication, Gemini vague attribution, DeepSeek language-mixing, Llama long-context fabrication, Grok tweet fabrication. See section 6 below and [references/per-family-hallucination-signatures.md](per-family-hallucination-signatures.md).

---

## 6. Per-Family Hallucination Signatures (v2.0)

Different LLM families fabricate facts in distinctive ways. Knowing the source family (via the A1 stylistic detection in the companion synthesis-content-quality skill) lets fact-checkers apply the most-effective family-specific check rather than running every check on every piece.

### Family signature summary

- **Anthropic Claude.** Plausible-seeming DOIs (correctly formatted but resolving to a different paper or to nothing). Claude 3.7 hallucinated citation rate 15-20 percent per Buchanan/Hill/Shapoval Sage 2024 (cited; verification flagged). Check every DOI.
- **OpenAI GPT.** URLs on real domains that 404. GPT-3.5 30-55 percent of citations hallucinated (Walters and Wilder Sci Rep 2023, cited); GPT-4 18-29 percent; GPT-4o approximately 20 percent with 56 percent of those containing errors per Chelli JMIR 2024 (cited). Check every URL.
- **Google Gemini.** Vague attribution ("studies show," "research indicates") without specific source. Detect via the absence of named citations, not by checking citations that do not exist.
- **Meta Llama.** Above approximately 32K-token context, factual confabulation increases substantially per RIKER benchmark (cited; verification flagged). For long-context analysis, audit the factual claims for source independence.
- **xAI Grok.** Tweet/X-source bias; fabricated quotes attributed to social media; over-reliance on X corpus as authoritative. Verify any social-media-cited quote.
- **DeepSeek.** Language-mixing under reasoning load. Chinese characters appearing unexpectedly in English output. The `<think>` tag leakage in R1 outputs is itself diagnostic.
- **Mistral.** Less heavily documented. Note European-corpus citation bias and more direct refusal style (less hedge-wrapped fabrications).
- **Qwen.** Chinese-source bias; CJK-language sources cited but not English-translated; less hallucination on Chinese-language facts.

Full per-family detail with detection workflows, empirical anchors, and worked examples: [references/per-family-hallucination-signatures.md](per-family-hallucination-signatures.md).
