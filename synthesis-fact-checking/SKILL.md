---
name: synthesis-fact-checking
description: >
  Systematic fact-checking for articles, blog posts, news content, and AI-synthesized
  material. v2.0 adds nine new protocol sections covering nested attribution, paraphrase
  drift, composite quotes, position-shifting, source-translation drift, URL rot vs
  hallucination, AI-generated synthetic sources, citation laundering chains, and
  tool-specific hallucination patterns by LLM family. Use when asked to: fact-check,
  verify claims, verify sources, check accuracy, citation verification, review factual
  accuracy, validate references, audit AI-summarized content.
license: "CC0-1.0"
depends_on: ["synthesis-content-quality"]
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Fact-Check Process for Articles and AI-Synthesized Content

## Purpose

This skill provides a repeatable process for verifying factual accuracy of articles, blog posts, and news content before publication. v2.0 is specifically calibrated for the recursive-contamination problem: AI-generated text now constitutes a plurality of newly indexed English-language web pages (per Ahrefs measurement of newly indexed pages in April 2025), which means AI outputs become source material for the next generation of AI outputs and human research. Multi-source confidence requires graph independence, not raw count.

The companion skill, [synthesis-content-quality](../synthesis-content-quality/SKILL.md), addresses stylistic and substantive quality. This skill addresses factual correctness.

## What v2.0 adds

- **Nine new protocol sections (C1)** for the structural gaps in v1.1.0: nested attribution, paraphrase boundary drift, composite quotes, position-shifting, source-translation drift, URL rot vs hallucination, AI-generated synthetic sources, citation laundering chains, tool-specific hallucination patterns. Full detail in [references/detailed-protocols.md](references/detailed-protocols.md).
- **Per-family hallucination signatures.** Claude over-produces plausible-seeming DOIs; GPT invents URLs on real domains; Gemini drifts to vague "studies show"; DeepSeek language-mixes under reasoning; Llama fabricates above approximately 32K context per RIKER benchmark; Grok fabricates X/Twitter quotes. Family-conditional detection is the bucket-C parallel to bucket-A's family-conditional stylistic detection. Full detail in [references/per-family-hallucination-signatures.md](references/per-family-hallucination-signatures.md).
- **Graph-independence revision to section 2** (Multi-Source Confidence Framework). Citation laundering chains collapse cross-source corroboration to a single AI-generated upstream. Confidence conditions on graph independence, not on raw count. Full detail in [references/citation-laundering-detection.md](references/citation-laundering-detection.md).
- **Section 4 refresh.** Updated examples from 2025-2026 production incidents: Mostafavi sanction ($10,000), Goldberg Segalla sanction ($59,500 total), Chicago Sun-Times summer reading list, Springer "Mastering ML" book retraction, BBC/EBU 45 percent significant-issues rate, Topaz et al. May 2026 Lancet letter (1 in 277 PubMed papers referencing fabricated paper, twelvefold rise from 2023), Damien Charlotin's database of 1,455+ sanctioned legal cases, Mata v. Avianca, Stanford RegLab Magesh measurement (17 to 33 percent legal-AI hallucination rate). Full incident archive in [references/production-incident-archive.md](references/production-incident-archive.md).
- **Section 4f demote.** Hallucinated citations as a single bucket is demoted. The failure mode splits into the C1-URLROT-001 / C1-SYNTH-001 / C1-LAUNDER-001 trio plus residual pure-fabrication.

The methodology in v1.1.0 (the tier system, the confidence-based evaluation process, the verification hierarchy) is preserved. v2.0 refreshes the catalog under the same methodology.

---

## Process Overview

1. Claim Extraction
2. Multi-Source Confidence Assessment (with graph independence per v2.0)
3. Verification by Source Hierarchy
4. Common Error Pattern Detection (4a through 4g, refreshed)
5. **Nine new protocol sections for v2.0 (C1)**
6. **Per-family hallucination signatures (v2.0)**
7. Quote Verification (with nested attribution per v2.0)
8. Study Verification
9. Temporal Verification (if backdated)
10. Translation-Pass Re-Verification
11. Documentation
12. Pre-Publish Checklist

---

## 1. Claim Extraction

Before verifying anything, extract every verifiable claim from the draft into a structured checklist.

### Claim Categories

| Category | What to look for | Example |
|----------|-----------------|---------|
| **Statistics / Numbers** | Percentages, dollar amounts, headcounts, growth rates | "67 percent of workers reported reduced burnout" |
| **Study Names** | Named research papers, reports, surveys | "The Stanford HAI 2024 AI Index Report" |
| **Author Names** | Researchers, executives, experts quoted or cited | "Erik Brynjolfsson and colleagues" |
| **Dates** | Publication years, event dates, timeframes | "A 2023 study found..." |
| **Direct Quotes** | Any text in quotation marks attributed to a person | 'As Jensen Huang noted, "..."' |
| **Organization Names** | Companies, unions, agencies, universities | "The Bureau of Labor Statistics" |
| **Causal Claims** | Assertions that X caused Y, or X leads to Y | "Automation led to a 40 percent increase in output" |
| **Comparative Claims** | Rankings, "first," "largest," "fastest-growing" | "The largest study of its kind" |
| **URLs and DOIs (v2.0)** | Any cited URL, DOI, ISBN, or persistent identifier | "doi:10.1038/s41586-2023-XXXXX" |
| **Nested attributions (v2.0)** | Quotes that pass through multiple speakers | "As X told Y, '...'" |

### Extraction Process

1. Read the draft paragraph by paragraph.
2. For each paragraph, identify every claim that could be verified or falsified.
3. Record each claim in a checklist (see Documentation Template below).
4. Do not skip claims that "sound right": those are often the ones subtly wrong.

---

## 2. Multi-Source Confidence Framework (REVISED for v2.0)

When synthesizing from multiple research sources, the degree of agreement between sources provides a useful signal: but only when the sources are graph-independent. Three "sources" that all trace back to a single AI-generated upstream are single-sourced, regardless of count.

### Confidence Levels

| Source Agreement | Graph Independence | Confidence | Required Action |
|-----------------|-------------------|------------|-----------------|
| **3+ graph-independent sources agree** | Verified | Very high | Still verify against primary. |
| **2 graph-independent sources agree** | Verified | High | Verify numbers, names, framing. |
| **N sources agree, single upstream** | Not independent | Single-sourced | Treat as 1-source claim. Verify primary upstream. |
| **1 source cites the claim** | N/A | Moderate | Must verify before including. |
| **Sources conflict** | N/A | Low | Go to primary. |

### Graph independence check (new in v2.0)

For multi-source claims, build a citation graph: each source's own citation chain back to its upstream. If multiple paths converge on a single AI-generated upstream (blog post, content farm article, AI-summarized content), the claim is single-sourced. See [references/citation-laundering-detection.md](references/citation-laundering-detection.md) for the full graph-traversal protocol.

### Why this revision matters

Per Topaz et al. May 2026 Lancet letter (cited; verification flagged), 1 in 277 PubMed papers in 2026 referenced a fabricated paper, a twelvefold rise from 2023. The laundering mechanism through indexed academic databases is real. Multi-source confidence in v1.1.0 assumed graph independence implicitly; v2.0 makes it explicit.

---

## 3. Verification Hierarchy

### Source Quality Ranking

1. **Primary sources.** Original journal paper, official report, press release, direct statement. Standard against which all claims should be verified.
2. **Authoritative secondary sources.** Reporting by established news organizations citing primary sources. Useful when primary is paywalled.
3. **Tertiary sources.** Other blog posts, summaries, encyclopedia entries. Helpful for locating primaries, never the final verification.
4. **LLM training data / AI research outputs.** What you are fact-checking, not what you fact-check against.

### What to Verify by Claim Type

**For statistics:** the number itself; the framing of what the number measures; the time period covered; the entity that produced the number.

**For academic studies:** see the Study Verification Protocol (section 8).

**For quotes:** see the Quote Verification Protocol (section 7) plus C1-NESTED-001, C1-COMPOSITE-001, C1-PARAPH-001 in references/detailed-protocols.md.

**For URLs:** apply the C1-URLROT-001 protocol: distinguish hallucinated, stale, redirected, retracted, paywalled, updated. See [references/detailed-protocols.md](references/detailed-protocols.md).

**For organization names:** verify exact name; check for parent/subsidiary confusion; verify organization exists and is described accurately.

**For causal claims:** verify the cited source actually asserts causation, not correlation; check whether the source's hedged language ("may," "could," "associated with") has been strengthened in the draft.

---

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

- **C1-URLROT-001** (URL rot vs hallucination distinction): cited URLs that fail to resolve. Hallucinated (fabricated, never existed) versus rotted (real-but-changed) require different remediation. See [references/detailed-protocols.md](references/detailed-protocols.md) section C1-URLROT-001.
- **C1-SYNTH-001** (AI-generated synthetic sources): citations to "studies," "experts," or "news articles" that turn out to be AI-generated content presented as authoritative. See detailed-protocols.md.
- **C1-LAUNDER-001** (Citation laundering chains): citations that trace back to a single AI-generated upstream. See [references/citation-laundering-detection.md](references/citation-laundering-detection.md).
- **Residual pure-fabrication.** DOIs that resolve to nothing, papers that do not exist, authors who do not exist. The rump 4f after the three new C1 sections take their share. Apply Study Verification Protocol (section 8).

**Canonical 2025-2026 incidents** (full detail in [references/production-incident-archive.md](references/production-incident-archive.md)):

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

The nine new protocol sections address structural gaps in v1.1.0 that have become urgent under the 2025-2026 recursive-contamination problem. Each section has full detail (failure modes, worked examples, detection protocol, sources, remediation) in [references/detailed-protocols.md](references/detailed-protocols.md).

### Section summary

- **C1-NESTED-001.** Second-party and third-party quote handling. Quotes that pass through multiple speakers have multiple drift points. Detection protocol: trace attribution chain back to original speaker.
- **C1-PARAPH-001.** Paraphrase boundary drift (bidirectional). Source's epistemic frame lost in summary; quotation marks added to non-quoted paraphrase. Per the 500-summary audit cited in research (source flagged for verification), 11 percent of AI-generated news summaries contained composite quotes and 8 percent added quotation marks.
- **C1-COMPOSITE-001.** Composite quotes. Non-contiguous source fragments stitched into a single quoted utterance. Detection: verify exact word sequence appears in source as one continuous quote.
- **C1-POSSHIFT-001.** Position-shifting (framing drift). Source's stated position shifted toward more balanced framing than source held. Common with Claude-family due to constitutional-AI training toward balanced presentation.
- **C1-TRANS-001.** Source-translation drift. AI-translated quotes from non-English sources without professional translation cited; translation-of-translation chains undocumented.
- **C1-URLROT-001.** URL rot versus hallucination distinction. Six-category taxonomy: HALLUCINATED, STALE, REDIRECTED, RETRACTED, PAYWALLED, UPDATED. Each requires different remediation.
- **C1-SYNTH-001.** AI-generated synthetic sources. Citations to "studies" that are AI blog posts; "experts" that are synthetic identities; "news articles" that are content-farm output. Per Retrieval Collapse research (arxiv 2602.16136 cited; verification flagged), 67 percent pool contamination yields 80 percent exposure contamination.
- **C1-LAUNDER-001.** Citation laundering chains. Apparent multi-source corroboration collapses to single AI-generated upstream. Full graph-traversal protocol in [references/citation-laundering-detection.md](references/citation-laundering-detection.md).
- **C1-TOOLHALL-001.** Tool-specific hallucination patterns. Per-family signatures: Claude DOI fabrication, GPT URL fabrication, Gemini vague attribution, DeepSeek language-mixing, Llama long-context fabrication, Grok tweet fabrication. See section 6 below and [references/per-family-hallucination-signatures.md](references/per-family-hallucination-signatures.md).

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

Full per-family detail with detection workflows, empirical anchors, and worked examples: [references/per-family-hallucination-signatures.md](references/per-family-hallucination-signatures.md).

---

## 7. Quote Verification Protocol

Direct quotes carry high credibility with readers. A fabricated or misattributed quote damages trust disproportionately.

### Verification Steps

1. **Verify the quote exists.** Search for the exact quote (or a distinctive phrase) using quotation marks to force exact-match results. If no results appear, the quote may be fabricated.
2. **Verify exact wording.** Compare word-for-word against the primary source. Small changes ("can" vs "could," "will" vs "may") alter meaning.
3. **Verify correct attribution.** Confirm the named person actually said or wrote the quote. Famous quotes are frequently misattributed.
4. **Verify the context.** Read surrounding text in the original source to confirm the quote means what the draft implies.
5. **Verify nested attribution (v2.0).** If the quote passes through a speaker chain (X told Y who reported in source Z), apply the C1-NESTED-001 protocol: trace to the original speaker, compare verbatim, flag drift at each layer.
6. **Verify against composite (v2.0).** Check that the quote is one continuous utterance in the source, not assembled from non-contiguous fragments. Apply the C1-COMPOSITE-001 protocol.
7. **Verify against paraphrase boundary drift (v2.0).** Check that words inside quotation marks actually appear in quotation marks in the source, and that paraphrased material does NOT carry added quotation marks. Apply C1-PARAPH-001.

### Red Flags

- A quote too perfectly aligned with the article's thesis (real quotes are messier).
- A quote that cannot be found anywhere on the web.
- A quote attributed to a famous person that sounds like something they would say but has no verifiable origin.
- A quote appearing in AI research outputs but not in any primary source.
- A quote where the speaker chain has not been traced (apply C1-NESTED-001).

---

## 8. Study Verification Protocol

Academic studies and research reports are among the most commonly hallucinated or misrepresented elements in AI-synthesized content.

### Verification Steps

1. **Verify the study exists.** Search by title, authors, institution. Use Google Scholar, publisher's website, institution's publications page.
2. **Verify the working paper or publication number.** If a specific paper number is cited, confirm it matches.
3. **Verify ALL author names.** Check first and last names. AI outputs sometimes add, remove, or swap authors.
4. **Verify the journal or publisher.** Confirm the paper was published where the draft says.
5. **Verify sample size and methodology.** Confirm against the paper.
6. **Verify the specific findings cited.** Direction of finding, magnitude, framing, caveats or limitations.
7. **Check for retraction, correction, or supersession.** Search Retraction Watch or the journal's errata page.
8. **Apply per-family hallucination signature check (v2.0).** If the article uses Claude family, scrutinize DOIs. If GPT, scrutinize URLs. If Gemini, scrutinize attribution specificity. See section 6.

### When the Study Cannot Be Found

If you cannot locate a cited study after thorough search:
- It may be hallucinated. Remove the citation.
- If the underlying claim matters, find a different verifiable source.
- If no verifiable source exists, remove the claim or hedge explicitly ("some researchers have suggested...").

---

## 9. Temporal Verification (for Backdated Articles)

When writing or revising an article with a publication date in the past, temporal integrity must be maintained.

### Rules

1. **All cited sources must predate the article's stated publication date.**
2. **External sources that postdate the article date require an explicit "Updated on" note.**
3. **Time-relative language must be accurate relative to the article date.** "Recently," "this year," "last month," "emerging."
4. **Do not cite preliminary data if final data was available by the article date.**

### Common Temporal Errors

- Calling a 2022 report "recent" in an article dated 2025.
- Citing a December 2024 source in an article dated November 2024.
- Using "the emerging field of..." for something well-established by the article date.
- Describing future events as future when they have already occurred by the article date.

---

## 10. Translation-Pass Re-Verification

Apply this protocol when an article has been through a de-jargoning, anonymization, or accessibility pass: any pass that replaces precision-bearing terms with vaguer prose for the benefit of a wider audience.

The translation pass introduces its own accuracy hazard. The pre-translation prose was precise and verifiable. The post-translation prose is accessible: and may no longer be true.

### Why this is a distinct fact-check step

The standard fact-check (sections 1-8) verifies that claims match source material. The translation pass happens AFTER that verification, when accessibility editing rephrases verified claims. The rephrasing can:

1. **Generalize what was specific.** "v0.8.0" replaced by "the first version" is wrong if earlier versions existed.
2. **Soften what was definite.** Specific function descriptions replaced by layer-level abstractions that may not be accurate.
3. **Lose load-bearing precision.** Specific metrics rephrased generally may obscure results the argument depended on.
4. **Convert verified facts into approximations the writer cannot defend.**

### Procedure

1. **List the changes.** During the translation pass, keep a list of every replacement: original term, replacement, reason.
2. **Re-verify each entry against the source.** For every replacement, ask: is the new wording true at its new level of precision?
3. **Flag soft drift.** Replacements that lose precision without losing truth are fine. Replacements that change truth conditions are not fine.
4. **Restore precision when the translation breaks the claim.** If the rephrasing makes a claim wrong, restructure rather than restore the original term.

### Worked example

Original: "I shipped synthesis-console v0.8.0 with the cockpit view of my daily plan."

De-jargoning replaced: "synthesis-console v0.8.0" → "the first version of the dashboard."

Re-verification flagged: the dashboard had been shipping for many versions before v0.8.0; v0.8.0 added the cockpit view as a new feature, not as the dashboard's first version. The replacement was wrong.

Restored: "I shipped the cockpit view of the daily plan as a new feature." Preserves accessibility (no version number) while keeping the claim true.

---

## 11. Documentation Template

Create a `review-log.md` file alongside the draft to document the fact-checking process.

### Template

```markdown
# Fact-Check Review Log

**Article:** [Title]
**Article Date:** [Publication date]
**Reviewer:** [Name]
**Review Date:** [Date]
**Sources Used for Synthesis:** [List]

## Claims Reviewed

### Claim 1: [Brief description]
- **Draft text:** "[Exact text]"
- **Status:** Verified / Needs Correction / Cannot Verify / Removed
- **Source:** [Primary source with URL or citation]
- **Finding:** [What verification revealed]
- **Correction applied:** [What changed]

[Continue for all claims]

## Editorial Decisions

- [Decision 1]
- [Decision 2]

## Summary

- Total claims reviewed: [N]
- Verified as stated: [N]
- Corrected: [N]
- Removed: [N]
- Cannot verify (hedged): [N]
```

---

## 12. Pre-Publish Checklist

### Factual Accuracy

- [ ] All statistics verified against primary sources (number AND framing)
- [ ] All study names verified (title, authors, publisher, paper number)
- [ ] All study findings verified (direction, magnitude, framing match source)
- [ ] All direct quotes verified for exact wording against primary source
- [ ] All direct quotes verified for correct attribution
- [ ] All organization names verified against official sources
- [ ] No conflated findings: each claim maps to a single finding in a single source
- [ ] No hallucinated citations: every cited source exists and says what the draft claims

### v2.0 Additions

- [ ] Multi-source claims pass graph independence check (no single AI upstream)
- [ ] Nested-attribution quotes traced to original speaker (C1-NESTED-001)
- [ ] No composite quotes (C1-COMPOSITE-001)
- [ ] No paraphrase boundary drift (C1-PARAPH-001)
- [ ] No position-shifting from source's stated position (C1-POSSHIFT-001)
- [ ] Source-language translations checked (C1-TRANS-001)
- [ ] URL classification applied for each cited URL (C1-URLROT-001 six-category taxonomy)
- [ ] No AI-generated synthetic sources (C1-SYNTH-001: experts verified, studies verified, publication venues verified)
- [ ] Citation laundering check on multi-source claims (C1-LAUNDER-001)
- [ ] Family-specific hallucination check applied if source LLM is known (C1-TOOLHALL-001)

### Temporal Integrity (if backdated)

- [ ] All cited sources predate the article's publication date
- [ ] Any post-date sources marked with "Updated on" notes
- [ ] Time-relative language accurate relative to article date
- [ ] No references to events or data postdating article without notation

### Translation-Pass Integrity (if applied)

- [ ] Every term replaced via de-jargoning re-verified against source material
- [ ] No claim asserts something the source does not
- [ ] Vague descriptors accurate at the new level of precision

### Documentation

- [ ] Review log documents every claim checked
- [ ] Corrections recorded in review log
- [ ] Editorial decisions documented
- [ ] Claims that cannot be verified removed or hedged appropriately

### Cross-Check with Content-Quality Skill

- [ ] Article reviewed against synthesis-content-quality v4.0 for stylistic issues
- [ ] No vague attributions remain ("experts say," "studies show") unless explicitly hedged
- [ ] No placeholder text (`[source needed]`, `TODO`, `VERIFY`) remains in draft

---

## 13. Quick Decision Tree

When encountering a claim during fact-checking:

```
Is the claim verifiable?
+-- No -> Opinion or argument. No verification needed (but check for embedded claims).
+-- Yes ->
    Can you find a primary source?
    +-- Yes ->
    |   Does the primary source confirm the claim exactly?
    |   +-- Yes ->
    |   |   Is the cited source AI-generated content presented as primary?
    |   |   +-- Yes -> Apply C1-SYNTH-001. The source is not primary; re-source.
    |   |   +-- No ->
    |   |       Are multi-source claims graph-independent?
    |   |       +-- Yes -> Verified.
    |   |       +-- No -> Treat as single-sourced; verify upstream.
    |   +-- No ->
    |       Is the discrepancy in the number, the framing, or both?
    |       +-- Number -> Correct the number.
    |       +-- Framing -> Correct the framing.
    |       +-- Both -> Rewrite the claim from primary.
    |       Apply C1-PARAPH-001 (paraphrase drift), C1-POSSHIFT-001 (position-shifting).
    +-- No ->
        URL provided?
        +-- Yes -> Apply C1-URLROT-001 (six-category check). Classify as hallucinated, stale, redirected, retracted, paywalled, or updated.
        +-- No ->
            Can you find a credible secondary source?
            +-- Yes -> Verify against secondary, note limitation.
            +-- No ->
                Is the claim essential to the article?
                +-- Yes -> Find alternative source, or hedge explicitly.
                +-- No -> Remove the claim.
```

---

## Related Skills

- [`synthesis-content-quality`](../synthesis-content-quality/SKILL.md) v4.0: Companion skill for stylistic and substantive quality. Family-conditional A1 detection feeds the per-family hallucination check (section 6) in this skill.
- [`synthesis-writing-pitfalls`](../synthesis-writing-pitfalls/SKILL.md): Universal human-source bad-writing patterns.
- [`synthesis-writing-craft`](../synthesis-writing-craft/SKILL.md): Positive writing principles.
- [`synthesis-reader-briefing`](../synthesis-reader-briefing/SKILL.md): Pre-writing audience analysis.
- [`synthesis-article-writing`](../synthesis-article-writing/SKILL.md): End-to-end article workflow with quality gates.

## References

Detailed catalog content lives in the [references/](references/) subfolder:

- [detailed-protocols.md](references/detailed-protocols.md): All nine C1 protocol sections with full failure modes, worked examples, and detection procedures.
- [per-family-hallucination-signatures.md](references/per-family-hallucination-signatures.md): Detailed per-family signature catalog with empirical anchors.
- [citation-laundering-detection.md](references/citation-laundering-detection.md): Graph-traversal protocol for detecting citation laundering chains.
- [production-incident-archive.md](references/production-incident-archive.md): Documented 2024-2026 production incidents (Mostafavi, Goldberg Segalla, Chicago Sun-Times, Springer book, BBC/EBU, Topaz Lancet, and others) with detection lessons.
- [bibliography.md](references/bibliography.md): Consolidated bibliography with verification status.

---

Part of the [synthesis writing](https://synthesiswriting.org) craft. The methodology is durable. The catalog refreshes as AI-generated content reshapes the source ecosystem. Newsroom fact-checkers, journalism integrity organizations, and academic citation auditors are the audience this skill serves.
