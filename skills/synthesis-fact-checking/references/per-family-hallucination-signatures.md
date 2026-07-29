# Per-Family Hallucination Signatures

Reference detail for synthesis-fact-checking v2.0, Section 9. This file is the bucket-C parallel to bucket-A's per-family stylistic fingerprinting in synthesis-content-quality's [model-family-fingerprints.md](../../synthesis-content-quality/references/model-family-fingerprints.md). Where the A1 catalog identifies WHO produced the text, this file identifies WHAT factual errors that producer is most likely to have made. The two layers compose: identify the family via A1 stylistic detection, then apply the family-specific factual checks below rather than running every check on every piece.

The eight families covered, in order of evidence depth: Anthropic Claude, OpenAI GPT, Google Gemini, Meta Llama, xAI Grok, DeepSeek, Mistral, Qwen. Each family section follows the same structure: signature description, empirical base rates with citations, three to five concrete examples, family-specific detection workflow, cross-reference to the A1 stylistic fingerprint that helps identify the family before applying the hallucination check, and cross-reference to C1-TOOLHALL-001 in detailed-protocols.md.

## Why per-family hallucination detection matters

The v1.1.0 fact-checking methodology treats all AI-generated citations as equivalent verification targets: locate the primary source, compare exact wording, confirm attribution, check the date. This works when verification budget is unconstrained. It collapses when a fact-checker is triaging hundreds of AI-assisted summaries against a deadline.

By 2026, fact-checkers face three structural shifts that make per-family detection load-bearing:

1. **Production-scale measurements show family-specific hallucination morphology.** Rao, Wong, and Callison-Burch's Penn URL hallucination study (arXiv:2604.03173) demonstrated that hallucination rates and types vary by family in ways that reward family-aware checking. GPT family produces zero stale URLs (every non-resolving URL is hallucinated, indicating parametric generation rather than retrieval). Gemini deep-research mode produces 13.3 percent hallucinated URLs (the highest rate measured) while its search-augmented mode produces 4.6 to 4.8 percent (comparable to Claude). Claude produces the lowest URL hallucination rate (3.0 to 3.2 percent) but with a domain-specific spike in Healthcare and Medicine (17.4 percent non-resolving versus 4.0 percent in Mathematics). Per-domain stratification per family is now a published empirical anchor, not a hand-wave.

2. **The recursive contamination baseline has collapsed open-web verification.** Ahrefs measured 74.2 percent of newly indexed English-language web pages in April 2025 contained AI-generated content (cited in Spennemann arxiv 2504.08755 and reproduced across multiple bucket C inputs). The corpus that fact-checkers treat as ground truth is now substantially synthetic. A naive "search the open web for the cited source" workflow returns AI-generated confirmations of AI-generated claims. Family-specific signature detection lets fact-checkers prioritize WHICH claims need primary-source escalation rather than treating every claim equally and exhausting verification budget on low-yield checks.

3. **Production incidents in 2024 to 2026 demonstrate that family signature awareness would have caught the most damaging cases earlier.** Mata v. Avianca (2023) involved fabricated case citations produced by GPT-3.5, which Penn 2026 shows hallucinates URLs at 30 to 55 percent (rate dropping to 18 to 29 percent for GPT-4 and approximately 20 percent for GPT-4o with 56 percent of GPT-4o citations containing errors per Chelli JMIR 2024). The Mostafavi 2025 sanction (court sanction for legal filings citing fabricated cases; Claude exec gives $10,000 figure, flagged for verification) and the Goldberg Segalla 2025 sanction (Claude exec gives $60,000 figure, flagged for verification) followed the same morphology: GPT family producing confident fabricated case citations on legal queries (18.7 percent hallucination rate on legal queries per Claritybot 2026 citing SuprMind 2026). The Chicago Sun-Times 2025 summer reading list (multiple non-existent books with plausible titles by real authors) and the Springer "Mastering Machine Learning" book (two-thirds fabricated references, Retraction Watch April 2025) follow the same parametric-fabrication signature. Damien Charlotin's database documents over 1,455 sanctioned legal cases involving AI-fabricated citations as of 2025 (flagged for verification). The Topaz et al. Lancet letter (May 2026, STAT News 2026-05-06 coverage) measured one in 277 PubMed papers in 2026 referenced a fabricated paper, a sixfold to twelvefold rise from 2023 to 2025 depending on the framing reconciliation. The BBC and European Broadcasting Union News Integrity report (October 2025) found 45 percent of AI-generated responses to news questions contained significant issues. Every one of these cases involved a model family with a documented signature that, if checked first, would have flagged the citation cluster for primary-source verification.

The methodological move is simple: identify the family via the A1 stylistic fingerprints in synthesis-content-quality, then apply the family-specific verification protocol below. A piece showing dense Claude-family stylistic markers (A1-CLAUDE-004 em-dash density, A1-CLAUDE-001 "It is important to note" preamble, A1-CLAUDE-008 uniform paragraph length) gets the Claude DOI-fabrication check applied to every academic citation. A piece showing GPT-family markers (A1-GPT-002 sycophantic opener, A1-GPT-012 markdown formatting, A1-GPT-011 hallucinated citations and DOIs) gets the GPT URL-fabrication check applied to every link. A piece showing Gemini markers (A1-GEMINI-002 "studies show" vague attribution, A1-GEMINI-006 exhaustive survey marker) gets the vague-attribution audit applied to every soft reference.

This is the bucket-C parallel to bucket-A's family-conditional approach. The detector does not run every check on every piece. It runs the right check on the right piece, based on the family signature identified by A1. Verification budget moves from undifferentiated to triaged. The hit rate on the checks that do run goes up substantially because each check is matched to the family most likely to have produced that specific failure mode.

## Caveats on the family-conditional approach

Before the per-family sections below, three caveats that constrain how the approach is applied:

1. **Model-version drift is constant.** Claude 3.5 Sonnet, Claude 4.5 Opus, and Claude 4.7 differ in their hallucination behavior. GPT-4o and GPT-5.1 differ. The signatures below reference the model versions where they were empirically anchored. Treat the per-family signature as the prior; treat the specific version as the modifier. Where ChatGPT contribution noted, claims about "Gemini" or "GPT" without surface, app, API, search mode, and date are often underspecified. v2.0 requires model version, wrapper, and tool state as metadata whenever a reviewer records a pattern or failure.

2. **Wrapper and tool state matter.** Gemini deep-research mode produces 13.3 percent URL hallucination. Gemini search-augmented mode produces 4.6 to 4.8 percent. Same family, different surface, three times the hallucination rate. Claude with extended thinking differs from Claude without. GPT with browsing tools differs from GPT without. The family signature is a prior probability; the wrapper modifies the actual rate substantially.

3. **The signatures are blind spots, not exclusions.** A Claude piece can produce GPT-shaped URL fabrications. A GPT piece can produce Claude-shaped DOI fabrications. The per-family signature identifies where each family is MOST LIKELY to fail; it does not claim that each family is GUARANTEED to fail in those ways and only those ways. Apply the family-specific check first because it has the highest expected yield, then apply the universal checks from sections 4a through 4g and the C1 protocols for residual coverage.

## Empirical anchors used throughout

Five empirical sources anchor the rate claims across the per-family sections. They are introduced here so the per-family entries can cite them by shorthand.

- **Penn 2026.** Rao, D., Wong, E., Callison-Burch, C. (2026). "Detecting and Correcting Reference Hallucinations in Commercial LLMs and Deep Research Agents." arXiv:2604.03173. Source for: Penn URL hallucination percentages by family; urlhealth tool; 3 to 13 percent hallucinated and 5 to 18 percent non-resolving URL rates; deep-research-mode 13.3 percent Gemini rate; ALL non-resolving GPT URLs hallucinated (zero stale fraction); per-domain breakdowns; 6.4x and 79x urlhealth improvement factors for Claude and Gemini respectively.

- **Buchanan / Hill / Shapoval (Sage 2024).** Hallucinated citation measurements across early frontier models. Provides the academic-citation baseline for the Claude DOI-fabrication signature.

- **Walters / Wilder (Scientific Reports 2023).** GPT-3.5 and GPT-4 hallucinated citation baseline. Provides the GPT-citation baseline. GPT-3.5 hallucinated citation rate 30 to 55 percent in their measurements; GPT-4 18 to 29 percent.

- **Chelli JMIR 2024.** GPT-4o citation-error rate. Approximately 20 percent of citations hallucinated; 56 percent of citations contained errors of some kind (whether full hallucination or partial drift).

- **RIKER benchmark.** arxiv 2603.08274. Long-context Llama fabrication above approximately 32K context tokens. The 32K threshold is approximate per Opus expansion verification flag.

- **AI Multiple January 2026.** Hallucination benchmark across 37 LLMs. 15 to 52 percent hallucination range across the population. Provides the upper-bound spread the per-family signatures sit within.

- **Vectara HHEM, FaithBench (arxiv 2410.13210), RAGTruth, HalluLens (ACL 2025), AA-Omniscience, HaluEval, FActScore, Google FACTS.** Benchmark family that the per-family signatures map against. Per-benchmark rates are not duplicated below; the citations are noted where the benchmark provides the strongest evidence for a specific signature.

Production-incident references used throughout: Mata v. Avianca 2023; Mostafavi sanction 2025; Goldberg Segalla sanction 2025; Damien Charlotin's database; Chicago Sun-Times 2025; Springer book 2025; BBC and EBU 2025; Topaz Lancet 2026; MAHA Report 2025; Tsinghua ICLR retraction; Washington Post AI podcast scripts 2026; Nieman Lab Blanchard / Goldiee February 2026; Google AI Overviews 2025 year-bug; Megalopolis trailer controversy.

---

## Anthropic Claude

Models in scope: Claude Opus, Sonnet, and Haiku across versions 3, 3.5, 4, 4.5, 4.6, and 4.7. Claude.ai default outputs are the most-studied chat-mode artifacts in the 2024 to 2026 detection-research corpus, and Claude's family signature has the densest empirical anchoring.

### Signature description

The canonical Claude hallucination signature is plausible-seeming DOI fabrication paired with refusal-on-contested-ground behavior. Claude overproduces correctly-formatted Digital Object Identifiers (DOIs) of the shape `doi:10.1038/s41586-XXXX-NNNNN-N` that resolve to a different paper than the one cited, or that resolve to nothing at all. The fabrication is high-polish: the journal abbreviation in the DOI prefix matches a real journal that publishes the paper class claimed, the year encoded in the DOI is plausible for the cited research, the suffix follows the publisher's format conventions. A reader cannot identify the fabrication by inspection. Only resolution attempts catch it.

Claude's family signature has three additional components that compose with the DOI-fabrication core. First, when Claude does hallucinate, the fabrication tends to be elaborated with "nuanced" qualifications that look like scholarly caution but have no source basis: a fabricated paper is cited with a fabricated methodology note, a fabricated sample size, and a fabricated limitation paragraph. Second, in advisory-register responses (medical, legal, financial), Claude may invent non-existent ethical guidelines or legal statutes to justify refusing or hedging a request the model does not understand. Per Gemini bucket-C contribution: this is the alignment-trained equivalent of GPT's URL fabrication. Third, Claude exhibits a refusal-on-contested-ground signature: where other families confabulate when the answer is uncertain, Claude often refuses or hedges. The refusal pattern is itself a family signature. A draft that mixes confident assertions with Claude-style hedging may be a Claude piece where the hedges were edited out and the assertions were the model's confabulation under reduced uncertainty signaling.

Claude has the lowest URL hallucination rate among tested families. The DOI fabrication is the academic-citation analog of URL fabrication: Claude's training corpus is denser in academic-style citation than in general web URLs, and the fabrication center of gravity shifts accordingly. A Claude-produced piece is less likely to fabricate a URL and more likely to fabricate a DOI. Both fabrications are high-polish; both are catastrophic if uncaught.

### Empirical base rates

- **URL hallucination rate (Penn 2026): 3.0 to 3.2 percent.** Lowest among tested families. This is a strong negative signature: a piece with dense URL citations and dense Claude stylistic markers should have most URLs resolve. A failure rate substantially above 3.2 percent suggests either (a) a non-Claude family produced the piece, (b) wrappers or tools were involved that changed the behavior, or (c) the editorial pass changed citation quality.

- **Domain-specific URL non-resolving rate (Penn 2026):**
  - Healthcare and Medicine: 17.4 percent.
  - Mathematics: 4.0 percent.
  - The Healthcare and Medicine spike is the highest of any specific Claude domain measurement. Medical citations from Claude require heightened scrutiny even though the family rate is otherwise low. Per Claude exec Wegovy stress test: Claude tends to refuse on contested medical ground where other families confabulate, but when Claude does NOT refuse and instead produces specific medical claims, the citation quality drops.

- **Hallucinated citation rate (Claude 3.7, range from cross-validated estimates): 15 to 20 percent.** Per Buchanan / Hill / Shapoval Sage 2024 and Walters / Wilder Scientific Reports 2023 baseline measurements, refined for Claude 3.7 in 2024 to 2025 follow-up work. This is the academic-citation rate, distinct from the URL rate. The DOI fabrication center sits inside this rate.

- **Correction behavior (Penn 2026): 6.4x improvement with urlhealth tooling.** Claude responds well to self-correction when given verification tools. Editorial workflow recommendation: when fact-checking Claude-family output, invoking urlhealth or equivalent live-resolution tooling on Claude's own re-check pass typically catches a substantial fraction of fabrications.

### Concrete examples

1. **DOI fabrication with plausible suffix.** Claude output: "According to Smith et al. 2023, doi:10.1038/s41586-2023-12345-6, the treatment reduced mortality by 12 percent." DOI resolution: returns a paper by different authors in the same journal in a different year. The DOI was formatted correctly for Nature; the suffix was a fabrication that resolved to an existing but unrelated paper. From the Claude Opus 4.7 expansion canonical examples.

2. **DOI fabrication with full hallucination.** Claude output: "Buchanan and colleagues (2024) reported a 23 percent reduction in physician time-to-diagnosis when AI-assisted differential diagnosis was deployed (doi:10.1097/JNNP.0000.000000.0000)." DOI resolution: returns 404 or a parking page from the publisher. The DOI was correctly formatted for the Journal of Neurology, Neurosurgery, and Psychiatry; the suffix was complete fabrication.

3. **Nuanced false elaboration around fabricated DOI.** Claude output: "Buchanan and colleagues (2024) studied this in a cohort of 1,247 patients with mild cognitive impairment, finding that the effect was statistically significant (p less than 0.01) but with notable limitations including a single-center design and a 14-month follow-up window." DOI resolution: 404. The "nuanced limitation paragraph" is itself fabrication, layered on the fabricated citation. The polish makes the citation more plausible to skim readers, which is exactly the failure mode the Springer "Mastering Machine Learning" book (Retraction Watch April 2025) demonstrated at scale: two-thirds of references fabricated, each one accompanied by a plausible-seeming method note.

4. **Ethical-guideline invention (per Gemini bucket-C contribution).** User asks Claude for guidance on a borderline medical question. Claude responds: "I cannot provide that specific guidance because it would conflict with the American Medical Association's 2023 Code of Ethics, Section 4.2, which prohibits..." The cited AMA section does not exist. Per Gemini analysis: Claude invents non-existent ethical guidelines or legal statutes to justify refusing a prompt it does not understand. The fabrication shifts the burden from "Claude could not answer" to "the AMA prohibits Claude from answering," which is a different kind of false claim.

5. **Wegovy multi-family stress test (Claude exec canonical worked example).** Identical prompt about Wegovy off-label indications submitted to Claude, GPT, Gemini, Llama, and DeepSeek. Family profiles emerged: Claude refused; GPT confabulated with plausible URLs and case citations; Gemini drifted under reasoning with secondary-indication invention; Llama fabricated above 32K context; DeepSeek language-mixed. The refusal is the Claude signature; the absence of refusal in a Claude-family-styled piece is itself a flag that an editorial pass may have replaced refusal with confabulation.

6. **Attribution conflation (per Perplexity).** Claude conflates positions held by multiple speakers and attributes them to the most prominent named figure. Source contained: Senator A's 2022 floor speech; Senator B's 2023 committee statement; Senator C's 2024 press release. Claude output: "Senator A has consistently argued that [the merged position of all three]." The merged position is a fabrication; each fragment is real; the attribution to A alone is wrong. This intersects with C1-NESTED-001 (nested attribution flattening) and C1-COMPOSITE-001 (composite quotes) in detailed-protocols.md.

7. **Position-shifting from Constitutional-AI balanced presentation (Claude exec).** Source article argues a clear thesis with concrete evidence. Claude summary: "The article discusses various perspectives on the question of X." The thesis was lost in the alignment-trained tendency toward balanced presentation. The fabrication is structural rather than factual: no individual claim is wrong, but the aggregate framing misrepresents the source. This is C1-POSSHIFT-001 (aggregate framing drift) in family-specific form.

### Family-specific detection workflow

1. **A1 stylistic identification first.** If the piece exhibits dense A1-CLAUDE markers (especially A1-CLAUDE-004 em-dash density at 5+ per 500 words, A1-CLAUDE-001 "It is important to note" preamble, A1-CLAUDE-002 two-handed balanced sentence, A1-CLAUDE-008 uniform paragraph length, A1-CLAUDE-007 section-ending recap), apply Claude-specific checks before universal checks.

2. **DOI audit pass.** For every DOI cited in the piece, resolve it via doi.org. Confirm:
   - The DOI returns a paper (not a 404 or parking page).
   - The paper title matches the citation.
   - The authors match the citation.
   - The journal matches the citation.
   - The year encoded in the DOI suffix matches the cited year.
   - The paper's findings match what the draft says they found.
   - A DOI that returns SOME paper but a different paper than cited is the highest-signal Claude fabrication. The fabrication is invisible to title-search alone; only DOI resolution catches it.

3. **Healthcare and medical citation extra scrutiny.** For any Claude piece touching healthcare, medicine, or pharmaceutical topics, run the DOI audit twice and run a primary-source verification on all academic citations. The 17.4 percent non-resolving rate per Penn 2026 in Healthcare is the highest specific-domain rate for Claude; assume one in six citations needs replacement.

4. **Ethical-guideline / legal-statute audit.** If the piece cites a specific section of a professional ethics code or a specific section of a statute or regulation, verify the section exists and says what the piece claims. Per Gemini bucket-C contribution: Claude family will invent specific-sounding cite anchors ("AMA Code of Ethics Section 4.2", "Model Rules of Professional Conduct Rule 3.3(a)(1)", "21 CFR 314.50(d)(5)(vi)") that look load-bearing. Resolve each anchor against the actual document.

5. **Refusal-absence audit.** If the piece exhibits Claude stylistic markers but contains confident assertions on contested medical, legal, or financial ground without hedging, flag the assertions for primary-source verification at higher intensity. The Claude family signature includes refusal-on-contested-ground; the absence of refusal in a Claude-styled piece suggests either (a) the assertion is well-grounded, (b) the editorial pass removed hedges, or (c) the model produced confabulation without hedging due to wrapper effects. Verify rather than trust.

6. **Position-flattening audit (Constitutional-AI signature).** If the piece summarizes a source article, check whether the summary's aggregate framing matches the source's actual thesis. Per C1-POSSHIFT-001 procedure: load the source, extract its load-bearing claims, compare to the summary's load-bearing claims. The Claude signature is symmetric flattening where the source's thesis becomes "the article discusses various perspectives."

7. **Composite-quote audit (Claude's attribution-conflation tendency).** For multi-clause quotes, verify each clause sits in the same source passage. The Claude family signature is conflating positions across speakers and timeframes; the composite is a fabrication of continuity. See C1-COMPOSITE-001 in detailed-protocols.md.

8. **urlhealth or equivalent live-resolution tooling.** If the workflow permits, run urlhealth (Rao et al. 2026 open-source Python pip-installable tool that classifies URLs as LIVE, DEAD, LIKELY_HALLUCINATED, or UNKNOWN) on every URL and run DOI resolution on every DOI. Claude's 6.4x improvement with urlhealth indicates that the family responds well to verification feedback; the same feedback at the human-editor layer improves detection substantially.

### Cross-references

- **A1 stylistic fingerprints for family identification.** Before applying the hallucination workflow above, identify the family via the A1 entries in synthesis-content-quality/references/model-family-fingerprints.md. The highest-yield Claude markers: A1-CLAUDE-001 (the "It is important to note" preamble), A1-CLAUDE-002 (two-handed balanced sentence), A1-CLAUDE-004 (em-dash density at 5+ per 500 words), A1-CLAUDE-005 (bulleted bolded lead-ins), A1-CLAUDE-006 (refusal-shaped close with safety hedge), A1-CLAUDE-007 (section-ending recap), A1-CLAUDE-008 (uniform paragraph length). A piece with three or more of these at density is almost certainly Claude family.
- **C1-TOOLHALL-001 in detailed-protocols.md.** Full tool-specific verification procedure. The Claude entry in C1-TOOLHALL-001 references this file for per-family signature detail.
- **C1-URLROT-001 and C1-SYNTH-001 in detailed-protocols.md.** Claude's URL rate is low; when a Claude-styled piece has a non-resolving URL, the URL rot vs. synthetic source distinction in C1-URLROT-001 applies.
- **C1-LAUNDER-001 in detailed-protocols.md.** Claude's attribution-conflation tendency can compose with citation laundering chains; the conflation may surface a launderable secondary source rather than the primary.
- **C1-POSSHIFT-001 in detailed-protocols.md.** Claude's Constitutional-AI signature produces position-shifting via balanced-presentation flattening.

---

## OpenAI GPT

Models in scope: GPT-3.5, GPT-4, GPT-4o, GPT-4.1, GPT-5, GPT-5.5, and the o-series (o1, o3, o4) reasoning models. The GPT family has the longest deployment history and the most extensive empirical hallucination measurement.

### Signature description

The canonical GPT hallucination signature is URL fabrication on real domains. GPT invents URLs of the form `nytimes.com/2024/03/article-that-never-existed` or `nature.com/articles/ai-2025-xyz` that look correctly formatted for the target site but return 404 on resolution. Per Penn 2026: ALL non-resolving URLs from search-augmented GPT-4o and GPT-4.1 are hallucinated (zero stale fraction). This is diagnostic. Non-resolving URLs from GPT are not links that died (the way that links from a 2014 essay might have died in the open-web link-rot pattern documented in Zittrain et al. 2014's Harvard Law Review study showing 70+ percent of URLs no longer resolve). They are URLs that never existed. The model generates them from parametric memory, fitting the target site's URL conventions to whatever topic the response requires, then presents them as citations.

GPT family hallucinations have two additional components. First, the fabrications are high-polish: per Gemini bucket-C contribution, GPT invents flawless three-point historical timelines with perfect markdown formatting, but the dates are fabricated. The structure is impeccable; the content is wrong. Second, GPT exhibits confident-wrong-specifics behavior: per Perplexity citing MIT research via Claritybot 2026, GPT models are 34 percent more likely to use confident language when generating incorrect information than when generating correct information. The confident-wrong-specifics pattern makes 4c errors (wrong specifics from correct general findings) systematically harder to detect, because the confidence signal that human readers use to gauge claim reliability points the wrong direction.

The o-series reasoning models add a third component: explicit uncertainty hedges in the response text that underestimate the actual error rate. Per Perplexity bucket-C contribution: "I should note there is some uncertainty" does not tell the fact-checker which specific claims are wrong. The hedge applies to the whole response but does not differentiate the high-confidence (correct) from the low-confidence (potentially fabricated) claims.

Per Damien Charlotin's database (cited in Claude exec, flagged for verification), over 1,455 sanctioned legal cases involve AI-fabricated citations as of 2025, with GPT family heavily represented. The Mostafavi 2025 ($10,000 per Claude exec, flagged for verification) and Goldberg Segalla 2025 ($60,000 per Claude exec, flagged for verification) sanctions follow the same morphology: confident fabricated case citations with correct-looking citation formats but no actual case behind them.

### Empirical base rates

- **URL hallucination rate (Penn 2026):**
  - GPT-3.5: 30 to 55 percent (per Walters / Wilder Scientific Reports 2023 baseline).
  - GPT-4: 18 to 29 percent.
  - GPT-4o: approximately 20 percent, with 56 percent of citations containing errors of some kind per Chelli JMIR 2024.
  - Search-augmented GPT-4o and GPT-4.1: 5.4 to 8.8 percent. Stale-fraction-zero: ALL non-resolving URLs are hallucinated. Confirmed parametric generation rather than retrieval.

- **By topic (Claritybot 2026 citing SuprMind 2026):**
  - Legal queries: 18.7 percent hallucination rate.
  - Medical queries: 15.6 percent hallucination rate.
  - The legal and medical query spike is the proximate cause of the Mostafavi and Goldberg Segalla sanctions. Production-deployed legal and medical workflows running on GPT family without primary-source verification consistently surface fabrications.

- **Confident-language amplification (MIT research via Claritybot 2026): 34 percent.** Models are 34 percent more likely to use confident language when generating incorrect information than when generating correct information. This is the empirical base rate for the confident-wrong-specifics signature.

- **Stanford RegLab Magesh et al. (June 2024, flagged for verification):** 17 to 33 percent legal-AI hallucination rates with retrieval augmented generation (RAG). RAG reduces but does not eliminate fabrication. Confirms that even the strongest GPT-family productionized legal tooling produces fabrication at scale.

### Concrete examples

1. **URL fabrication on a real domain (Claude Opus 4.7 expansion canonical example).** GPT output: "https://nytimes.com/2024/05/15/business/tech-merger-analysis." URL resolution: 404. The URL is correctly formatted for the New York Times; the slug structure matches NYT URLs; the date encoded in the URL is plausible; the article does not exist. The fabrication is invisible to inspection.

2. **Fabricated legal citation (Mata v. Avianca 2023 and the 1,455+ cases in Charlotin's database).** GPT output: "In Martinez v. Delta Air Lines (S.D. Fla. 2019), the court held that..." Case lookup: no such case exists in S.D. Fla. or any other federal court. The citation format is correct for federal district court cases; the holding is fabricated; the parties may or may not match real but unrelated cases. The Mata v. Avianca 2023 sanction; Mostafavi 2025 ($10,000 sanction per Claude exec, flagged for verification); Goldberg Segalla 2025 ($60,000 sanction per Claude exec, flagged for verification); MAHA Report 2025 (White House chronic disease report with AI-generated citations). All follow this morphology.

3. **Perfect-markdown historical timeline (per Gemini bucket-C contribution).** GPT output:
   ```
   The development of the technology proceeded in three phases:
   
   1. **1953**: Initial theoretical work by Smith and Jones at MIT.
   2. **1967**: First working prototype demonstrated at IBM Research.
   3. **1981**: Commercial deployment at AT&T Bell Labs.
   ```
   Verification: no such work by Smith and Jones at MIT in 1953; no such IBM Research prototype in 1967; no such AT&T Bell Labs commercial deployment in 1981. The markdown formatting is perfect, the structure is impeccable, the content is fabricated. Per Gemini analysis: GPT generates highly structured, sequential fictions where the surface signals quality but the substance is invented.

4. **Springer "Mastering Machine Learning" 2025 (Retraction Watch April 2025).** Springer published a book on machine learning with two-thirds of references fabricated. References were correctly formatted for the journals they claimed to come from; references did not exist when verified. The book passed publisher review because no editor resolved the citations.

5. **Chicago Sun-Times summer reading list 2025 (NPR May 2025 coverage).** Newspaper published a summer reading list with multiple books that did not exist; books had plausible titles by real authors but were AI fabrications. This is the GPT family signature applied to the books-and-publishing domain: confident fabrications of authored works that look like real titles.

6. **o-series uncertainty-hedge mismatch (per Perplexity).** o3 output to a legal question: "I should note there is some uncertainty in the regulatory framework here, but generally, courts have held that..." followed by three confident citations to cases. Verification: the "some uncertainty" hedge applies to the general framework (which is roughly correct); the three case citations are fabricated. The hedge does not differentiate the correct general framing from the incorrect specific citations.

7. **GPT exec confabulation case (Megalopolis trailer controversy).** Trailer for the film Megalopolis contained fabricated or misattributed critic quotes. Per ChatGPT bucket-C contribution: GPT family produces high-polish confabulated quotes that integrate smoothly with surrounding real material. The fabrication is catastrophic because the surrounding material is correct, lulling readers into trusting the fabricated insertion.

8. **Washington Post AI podcast scripts 2026 (per ChatGPT).** Production testing of AI-generated podcast scripts found fabricated and misattributed quotations. Same GPT signature: high-polish confident quotation fabrication.

### Family-specific detection workflow

1. **A1 stylistic identification first.** If the piece exhibits dense A1-GPT markers (especially A1-GPT-002 sycophantic opener "Great question!" or "Certainly!", A1-GPT-001 "delve" and saturated vocabulary cluster, A1-GPT-012 markdown formatting in plain-text contexts, A1-GPT-011 hallucinated citations and DOIs as the stylistic pattern, A1-GPT-008 numbered-list scaffolding, A1-GPT-016 transition word cascade), apply GPT-specific checks before universal checks.

2. **URL audit pass.** For every URL cited in the piece, resolve it. Confirm:
   - The URL returns the article claimed (not a 404, not a redirect to the site home page, not a parking page).
   - The article title at the URL matches the citation.
   - The article author at the URL matches the citation.
   - The publication date at the URL matches the citation.
   - **Critical distinction (per Penn 2026):** A 404 from a GPT-family piece is almost certainly a hallucination, NOT a dead link. Treat 404s as fabrication-flagged. The zero-stale-fraction finding makes this diagnostic; GPT URLs do not link-rot the way human-curated URLs do.

3. **Legal and medical query extra scrutiny.** Any GPT piece touching legal or medical questions gets primary-source verification on every citation. The 18.7 percent (legal) and 15.6 percent (medical) hallucination rates make these the high-yield checks. For legal citations specifically: look up every case in Westlaw, Lexis, or Court Listener. For medical citations: look up every paper in PubMed and resolve every DOI. The Mostafavi and Goldberg Segalla sanctions are the production-incident anchor; assume any unverified legal citation in a GPT-styled piece is a sanction risk.

4. **Markdown-structured timeline audit.** Per Gemini bucket-C contribution: any beautifully-formatted markdown timeline or numbered list in a GPT-styled piece gets verification on every line. The visual quality of the formatting is uncorrelated with the factual quality of the content. A flawless three-point timeline with bolded dates is exactly the GPT signature for fabrication.

5. **Confident-wrong-specifics audit (4c amplification).** Per Perplexity citing MIT research: GPT is 34 percent more likely to use confident language for incorrect specifics. Workflow recommendation: when verifying specific claims (names, percentages, dates) in a GPT-styled piece, do not let the model's confidence inform the verification priority. Verify the confidently-asserted specifics at the same intensity as the hedged ones. The confidence signal points the wrong way.

6. **o-series-specific hedge unbundling.** If the piece is from an o-series reasoning model and contains hedge language ("I should note...", "There is some uncertainty about..."), the hedge does NOT tell you which specific claims are wrong. Apply the universal claim-extraction-then-verify process from section 1 of the SKILL.md to every load-bearing claim regardless of the hedge.

7. **Composite-quote audit (Megalopolis / Washington Post signature).** For any GPT-family piece containing direct quotes from public figures, verify each quote against the original source. The composite-quote signature (C1-COMPOSITE-001) is present at scale in GPT family productionized output. Multi-clause quotes are at higher risk than single-sentence quotes.

8. **urlhealth or equivalent live-resolution tooling.** Run urlhealth on every URL. The zero-stale-fraction finding makes this especially diagnostic for GPT family: every non-resolving URL is a fabrication, no false-positive risk from link rot.

### Cross-references

- **A1 stylistic fingerprints for family identification.** Highest-yield GPT markers: A1-GPT-001 (delve and saturated vocabulary), A1-GPT-002 (sycophantic opener), A1-GPT-003 (section-ending summary sentence), A1-GPT-004 ("It's not just X, it's Y" construction), A1-GPT-008 (numbered-list scaffolding and listicle-default mode), A1-GPT-011 (hallucinated citations and DOIs as the stylistic pattern), A1-GPT-012 (markdown formatting in plain-text contexts), A1-GPT-016 (transition word cascade). A piece with three or more of these at density is likely GPT family.
- **C1-TOOLHALL-001 in detailed-protocols.md.** Full tool-specific verification procedure.
- **C1-URLROT-001 in detailed-protocols.md.** The zero-stale-fraction finding for GPT makes the URL rot vs. hallucination distinction diagnostic.
- **C1-SYNTH-001 in detailed-protocols.md.** Springer book and Chicago Sun-Times reading list are canonical synthetic-source cases that map to GPT's parametric-fabrication signature.
- **4c (wrong specifics from correct general findings) in SKILL.md.** The MIT-cited 34 percent confidence amplification makes 4c especially dangerous for GPT-family output.

---

## Google Gemini

Models in scope: Gemini Pro, Flash, Ultra; deep-research mode; search-augmented mode. The deep-research mode and the search-augmented mode produce markedly different hallucination behaviors and need to be distinguished.

### Signature description

The canonical Gemini hallucination signature is vague attribution without specific source identifiers. Gemini generates "studies show" or "experts say" or "research indicates" without naming the study, the expert, or the research. The vague attribution is hard to verify and harder to falsify: the fact-checker cannot definitively say "this study does not exist" because the attribution does not specify which study to check. Per Manus AI, Perplexity, DeepSeek, and Claude Opus expansion bucket-C contributions: Gemini tends to hallucinate "vibrant" but fabricated examples or scenarios that fit a narrative but lack factual basis. The vibrancy is the polish; the factual basis is missing.

Gemini exhibits a second mode-specific signature: deep-research mode hallucinates URL fragments by blending patterns from retrieved pages. Per Perplexity bucket-C contribution: Gemini deep-research mode may blend URL patterns from retrieved pages to produce plausible but non-existent addresses. The retrieval-augmented system retrieves several pages, observes their URL patterns, and generates a new URL that combines fragments from the retrieved patterns. The result looks like a URL from the retrieved corpus but does not actually exist on any of the retrieved sites. The hallucination rate is the highest of any family measured (13.3 percent per Penn 2026), despite Gemini having strong overall citation volume and benchmarked quality.

A third signature emerges under reasoning load: secondary-indication invention (per Claude exec Wegovy multi-family stress test). When prompted on a contested medical or technical question, Gemini drifts under reasoning toward fabricating secondary off-label indications, secondary mechanisms, or secondary applications that did not exist in the source material. The reasoning trace looks plausible; the conclusions are not in the cited sources.

A fourth signature for ChatGPT bucket-C contribution: search wrapper source problems. Gemini's search-augmented mode produces fabricated or copied citations despite stronger benchmarked factuality in some settings. The mode-by-mode behavior split is load-bearing for verification: Gemini search-augmented produces 4.6 to 4.8 percent URL hallucination (comparable to Claude); Gemini deep-research produces 13.3 percent.

The compensating property: Gemini has the best self-correction response of any family measured. Per Penn 2026: 79x improvement with urlhealth, achieving 0.1 percent hallucination after correction. Editorial workflow recommendation: invoking urlhealth on Gemini's own re-check pass approaches near-zero error.

### Empirical base rates

- **URL hallucination rate (Penn 2026):**
  - Deep-research mode: 13.3 percent (highest of any tested family).
  - Search-augmented modes: 4.6 to 4.8 percent (comparable to Claude).
  - Domain variation: consistent low non-resolving rates (2.5 to 10.2 percent across fields), with Healthcare and Medicine elevated at 5.3 percent.

- **Correction behavior (Penn 2026): 79x improvement with urlhealth.** Best response to self-correction among tested families. Post-correction rate approaches 0.1 percent hallucination.

- **Vague-attribution rate.** Not empirically anchored as a percentage in the bucket-C inputs, but described qualitatively as the canonical signature across Manus AI, Perplexity, DeepSeek, and Claude Opus expansion contributions. The lack of empirical anchor is itself a flag: vague attribution is hard to count because it is hard to operationalize what counts as "vague enough" to flag.

### Concrete examples

1. **"Research indicates" with no source (Claude Opus 4.7 expansion canonical example).** Gemini output: "Research indicates that 30 percent of teams experience this issue." No source named. The percentage looks specific enough to be authoritative; the lack of a citable source makes verification impossible.

2. **"Studies show" cluster (per Manus AI).** Gemini output: "Studies show that organizational change initiatives fail at high rates. Experts agree that the primary cause is poor communication. Research has demonstrated the importance of stakeholder buy-in." Three vague attributions, three vague claims, no verifiable source.

3. **Vibrant fabricated example (per Manus AI).** Gemini output, illustrating a narrative point: "Consider the case of Acme Corp, a mid-sized manufacturer that reduced costs by 40 percent through AI-driven supply chain optimization." Verification: no Acme Corp case study exists in the form described; the 40 percent figure is fabricated; the case fits the surrounding narrative but is invented. Per Gemini bucket-C contribution: "vibrant" but fabricated examples are a distinctive failure mode.

4. **Deep-research URL pattern blending (per Perplexity).** Gemini deep-research output retrieves several pages from `journals.elsevier.com/articles/...` and generates a citation URL of the form `journals.elsevier.com/articles/S2024-12345-X` that does not exist on Elsevier's site but follows the URL pattern of pages that do exist. The retrieval-augmented system blended the pattern; the URL is a fabrication that looks indistinguishable from a real Elsevier URL.

5. **Wegovy stress-test secondary-indication invention (Claude exec).** Identical Wegovy prompt to Gemini. Family profile under reasoning load: Gemini fabricated secondary off-label indications not present in any cited source. The reasoning trace looked plausible; the secondary indications were inventions. Compare to Claude (refused), GPT (confabulated with plausible URLs and case citations), Llama (fabricated above 32K context), DeepSeek (language-mixed).

6. **Search-wrapper source problem (per ChatGPT).** Gemini search-augmented output produces a citation to a real outlet but to an article that does not exist on that outlet, or to an article that exists but says something different than the citation claims. The wrapper retrieved real pages; the citation generation produced a near-miss.

7. **Cross-document conflation in deep-research mode (per Gemini bucket-C contribution to 4b).** Deep-research agents processing 50+ PDFs simultaneously will merge the methodology of Paper A with the results of Paper B. This is C1-LAUNDER-001 (citation laundering) in Gemini-family form: the cross-document blend is invisible at the surface, because both the methodology and the results are real, just not attached to each other.

### Family-specific detection workflow

1. **A1 stylistic identification first.** If the piece exhibits dense A1-GEMINI markers (especially A1-GEMINI-002 "studies show" without identifiers, A1-GEMINI-001 plain-text markdown leakage, A1-GEMINI-005 bulleted-everything default, A1-GEMINI-006 the exhaustive survey marker, A1-GEMINI-010 formal academic register default, A1-GEMINI-012 "key takeaways" section appended), apply Gemini-specific checks before universal checks. The strongest single signal for Gemini stylistic identification is A1-GEMINI-002 vague attribution, which is itself the stylistic shadow of the hallucination signature below.

2. **Vague-attribution audit.** Every phrase of the form "studies show," "experts say," "research indicates," "the data suggests," "evidence demonstrates," "analysts believe," "investigators have found" gets flagged for source identification. If the source cannot be named, the claim cannot be verified. The fact-checker has three resolutions: (a) locate the specific study or expert and confirm the claim, (b) remove the claim, (c) hedge the claim explicitly as "some sources suggest..." with awareness that the hedge is not the same as a verified specific claim.

3. **Mode identification.** If the workflow knows whether the Gemini output came from deep-research mode or search-augmented mode, calibrate the URL audit intensity accordingly. Deep-research mode: 13.3 percent hallucination rate, audit every URL. Search-augmented mode: 4.6 to 4.8 percent, audit at standard intensity. If mode is unknown, audit at deep-research intensity.

4. **Vibrant-example audit.** For every concrete example in a Gemini piece (named company, named individual, specific case study), verify the example exists and matches the description. Per Gemini bucket-C contribution: "vibrant but fabricated examples" are a distinctive signature; the polish of the example correlates with its fabrication risk.

5. **Reasoning-load secondary-indication audit.** For Gemini pieces involving medical, technical, or scientific reasoning, verify every secondary claim against primary sources. The Wegovy stress test signature is reasoning-induced secondary fabrication; the primary claim may be correct while the secondary claim is invented.

6. **Cross-document conflation audit (C1-LAUNDER-001 cross-reference).** If the piece is a deep-research output processing many documents, treat every methodology-and-results pairing as a potential cross-document conflation. Verify that the methodology and the results come from the same paper.

7. **urlhealth pass.** Gemini has the best response to urlhealth correction. Run urlhealth on every URL in a Gemini piece; the post-correction rate approaches 0.1 percent. This is the highest-yield self-correction tooling intervention of any family.

### Cross-references

- **A1 stylistic fingerprints for family identification.** Highest-yield Gemini markers: A1-GEMINI-001 (plain-text markdown leakage), A1-GEMINI-002 (vague attribution "studies show"), A1-GEMINI-004 ("let's dive in" opener), A1-GEMINI-005 (bulleted-everything default), A1-GEMINI-006 (exhaustive survey marker), A1-GEMINI-010 (formal academic register default), A1-GEMINI-012 ("key takeaways" section appended), A1-GEMINI-013 (three-options offer). A1-GEMINI-002 has the highest single-signal value because the stylistic vague-attribution pattern is the stylistic shadow of the hallucination vague-attribution signature.
- **C1-TOOLHALL-001 in detailed-protocols.md.** Full tool-specific verification procedure.
- **C1-LAUNDER-001 in detailed-protocols.md.** Deep-research-mode cross-document conflation is a Gemini-specific laundering form.
- **C1-URLROT-001 in detailed-protocols.md.** Gemini deep-research mode hallucinates URL patterns; the URL rot vs. hallucination distinction is mode-dependent.
- **4f trio (URL rot, synthetic sources, laundering) in SKILL.md.** Gemini's mode bifurcation makes the trio especially relevant: same family, different modes, different failure morphologies.

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

---

## Composing the checks across families

The eight per-family workflows above are designed to be applied sequentially, not in parallel, after A1 stylistic identification:

1. Identify the family via A1 stylistic detection. The strongest single signals: em-dash density (Claude), sycophantic opener (GPT), vague attribution stylistic pattern (Gemini), low-em-dash baseline with assertive declarative (Llama), Twitter-style structural defaults (Grok), CJK characters in reasoning content (DeepSeek), French-influence syntax with concise default (Mistral), CJK punctuation slips (Qwen).

2. Apply the family-specific hallucination workflow above. Each workflow runs the highest-yield check first: DOI audit for Claude, URL audit for GPT, vague-attribution audit for Gemini, long-context fabrication audit for Llama, tweet and Musk-source audit for Grok, language-mixing and reasoning-trace audit for DeepSeek, European-source audit for Mistral, Chinese-source audit for Qwen.

3. Fall back to universal verification per SKILL.md sections 4 and the C1 protocols for residual coverage. The family-specific workflow does not replace universal verification; it prioritizes which checks to run first.

4. Document the family identification and the checks applied in the fact-check review log. Per ChatGPT bucket-C contribution: v2.0 should require model version, wrapper, and tool state as metadata whenever a reviewer records a pattern or failure. The log should include: identified family (via A1), version if known, wrapper if known, tool state if known, and the family-specific checks applied.

5. When family cannot be identified or when multiple family signatures are present (which may indicate editorial blending or multi-model workflow), apply all relevant family workflows. Multi-family blending is increasingly common in production workflows where different models produce different sections of the same draft.

The methodology preserves v1.1.0: claim extraction, multi-source confidence framework, verification hierarchy, common error patterns 4a through 4g, quote verification protocol, study verification protocol, temporal verification, translation-pass re-verification. The family-conditional layer is a prioritization mechanism stacked on top of v1.1.0, not a replacement.

---

## Em-dash audit

This file uses no em-dashes (U+2014). Self-audited via character search before saving. Commas, parentheses, colons, and sentence breaks substitute throughout. The constraint is part of the substantive subject matter: A1-CLAUDE-004 (em-dash density) is a high-signal Claude stylistic marker, and a reference document for the upgrade cannot itself produce the pattern it is cataloguing.
