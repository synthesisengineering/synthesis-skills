# Fact-checking: verification steps

Sections 1, 2, 3, 7, 8 and 13 of the fact-check process, verbatim apart from link paths adjusted for this folder. Section numbers are the ones other documents cite. Sections 4 to 6 are in [error-patterns.md](error-patterns.md), 9 and 10 in [temporal-and-translation.md](temporal-and-translation.md), 11 and 12 in [review-log-and-checklist.md](review-log-and-checklist.md).

Contents:
- 1. Claim Extraction: claim categories and the extraction process
- 2. Multi-Source Confidence Framework: confidence levels, the graph-independence check, circular grounding through the author's own doctrine, why the revision matters
- 3. Verification Hierarchy: source quality ranking and what to verify by claim type
- 7. Quote Verification Protocol: verification steps and red flags
- 8. Study Verification Protocol: verification steps and what to do when a study cannot be found
- 13. Quick Decision Tree: routing any claim from "is it verifiable?" to verified, corrected, hedged or removed

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

For multi-source claims, build a citation graph: each source's own citation chain back to its upstream. If multiple paths converge on a single AI-generated upstream (blog post, content farm article, AI-summarized content), the claim is single-sourced. See [references/citation-laundering-detection.md](citation-laundering-detection.md) for the full graph-traversal protocol.

### Circular grounding through the author's own doctrine (v2.1)

A convergence case the graph must catch: the "supporting source" is a document the author or their organization wrote **from the same claim** (a published skill, methodology page, style guide). "The claim also appears in our doctrine" is the claim republished, not independent evidence; propagation cannot upgrade source grade. Grade such citations **derivative** (terminal class DERIVATIVE-SELF in [references/citation-laundering-detection.md](citation-laundering-detection.md)) and require an author-independent primary before confidence rises.

### Why this revision matters

Per Topaz et al. May 2026 Lancet letter (cited; verification flagged), 1 in 277 PubMed papers in 2026 referenced a fabricated paper, a twelvefold rise from 2023. The laundering mechanism through indexed academic databases is real. Multi-source confidence in v1.1.0 assumed graph independence implicitly; v2.0 makes it explicit.

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

**For URLs:** apply the C1-URLROT-001 protocol: distinguish hallucinated, stale, redirected, retracted, paywalled, updated. See [references/detailed-protocols-sources.md](detailed-protocols-sources.md).

**For organization names:** verify exact name; check for parent/subsidiary confusion; verify organization exists and is described accurately.

**For causal claims:** verify the cited source actually asserts causation, not correlation; check whether the source's hedged language ("may," "could," "associated with") has been strengthened in the draft.

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
