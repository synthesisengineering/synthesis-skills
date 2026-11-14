# Per-family hallucination signatures, part 1: why, caveats, anchors; Claude, GPT, Gemini

Part 1 of two, split from [per-family-hallucination-signatures.md](per-family-hallucination-signatures.md) so each part can be read in one pass. The text is verbatim, and the index's em-dash audit covers this part. Read the first three sections once; then read the section for the family that produced the draft.

Contents:
- Why per-family hallucination detection matters
- Caveats on the family-conditional approach
- Empirical anchors used throughout
- Anthropic Claude
- OpenAI GPT
- Google Gemini

---

## Why per-family hallucination detection matters

The v1.1.0 fact-checking methodology treats all AI-generated citations as equivalent verification targets: locate the primary source, compare exact wording, confirm attribution, check the date. This works when verification budget is unconstrained. It collapses when a fact-checker is triaging hundreds of AI-assisted summaries against a deadline.

By 2026, fact-checkers face three structural shifts that make per-family detection load-bearing:

1. **Production-scale measurements show family-specific hallucination morphology.** Rao, Wong, and Callison-Burch's Penn URL hallucination study (arXiv:2604.03173) demonstrated that hallucination rates and types vary by family in ways that reward family-aware checking. GPT family produces zero stale URLs (every non-resolving URL is hallucinated, indicating parametric generation rather than retrieval). Gemini deep-research mode produces 13.3 percent hallucinated URLs (the highest rate measured) while its search-augmented mode produces 4.6 to 4.8 percent (comparable to Claude). Claude produces the lowest URL hallucination rate (3.0 to 3.2 percent) but with a domain-specific spike in Healthcare and Medicine (17.4 percent non-resolving versus 4.0 percent in Mathematics). Per-domain stratification per family is now a published empirical anchor, not a hand-wave.

2. **The recursive contamination baseline has collapsed open-web verification.** Ahrefs measured 74.2 percent of newly indexed English-language web pages in April 2025 contained AI-generated content (cited in Spennemann arxiv 2504.08755 and reproduced across multiple bucket C inputs). The corpus that fact-checkers treat as ground truth is now substantially synthetic. A naive "search the open web for the cited source" workflow returns AI-generated confirmations of AI-generated claims. Family-specific signature detection lets fact-checkers prioritize WHICH claims need primary-source escalation rather than treating every claim equally and exhausting verification budget on low-yield checks.

3. **Production incidents in 2024 to 2026 demonstrate that family signature awareness would have caught the most damaging cases earlier.** Mata v. Avianca (2023) involved fabricated case citations produced by GPT-3.5, which Penn 2026 shows hallucinates URLs at 30 to 55 percent (rate dropping to 18 to 29 percent for GPT-4 and approximately 20 percent for GPT-4o with 56 percent of GPT-4o citations containing errors per Chelli JMIR 2024). The Mostafavi 2025 sanction (court sanction for legal filings citing fabricated cases; Claude exec gives $10,000 figure, flagged for verification) and the Goldberg Segalla 2025 sanction (Claude exec gives $60,000 figure, flagged for verification) followed the same morphology: GPT family producing confident fabricated case citations on legal queries (18.7 percent hallucination rate on legal queries per Claritybot 2026 citing SuprMind 2026). The Chicago Sun-Times 2025 summer reading list (multiple non-existent books with plausible titles by real authors) and the Springer "Mastering Machine Learning" book (two-thirds fabricated references, Retraction Watch April 2025) follow the same parametric-fabrication signature. Damien Charlotin's database documents over 1,455 sanctioned legal cases involving AI-fabricated citations as of 2025 (flagged for verification). The Topaz et al. Lancet letter (May 2026, STAT News 2026-05-06 coverage) measured one in 277 PubMed papers in 2026 referenced a fabricated paper, a sixfold to twelvefold rise from 2023 to 2025 depending on the framing reconciliation. The BBC and European Broadcasting Union News Integrity report (October 2025) found 45 percent of AI-generated responses to news questions contained significant issues. Every one of these cases involved a model family with a documented signature that, if checked first, would have flagged the citation cluster for primary-source verification.

The methodological move is simple: identify the family via the A1 stylistic fingerprints in synthesis-content-quality, then apply the family-specific verification protocol below. A piece showing dense Claude-family stylistic markers (A1-CLAUDE-004 em-dash density, A1-CLAUDE-001 "It is important to note" preamble, A1-CLAUDE-008 uniform paragraph length) gets the Claude DOI-fabrication check applied to every academic citation. A piece showing GPT-family markers (A1-GPT-002 sycophantic opener, A1-GPT-012 markdown formatting, A1-GPT-011 hallucinated citations and DOIs) gets the GPT URL-fabrication check applied to every link. A piece showing Gemini markers (A1-GEMINI-002 "studies show" vague attribution, A1-GEMINI-006 exhaustive survey marker) gets the vague-attribution audit applied to every soft reference.

This is the bucket-C parallel to bucket-A's family-conditional approach. The detector does not run every check on every piece. It runs the right check on the right piece, based on the family signature identified by A1. Verification budget moves from undifferentiated to triaged. The hit rate on the checks that do run goes up substantially because each check is matched to the family most likely to have produced that specific failure mode.

---

## Caveats on the family-conditional approach

Before the per-family sections below, three caveats that constrain how the approach is applied:

1. **Model-version drift is constant.** Claude 3.5 Sonnet, Claude 4.5 Opus, and Claude 4.7 differ in their hallucination behavior. GPT-4o and GPT-5.1 differ. The signatures below reference the model versions where they were empirically anchored. Treat the per-family signature as the prior; treat the specific version as the modifier. Where ChatGPT contribution noted, claims about "Gemini" or "GPT" without surface, app, API, search mode, and date are often underspecified. v2.0 requires model version, wrapper, and tool state as metadata whenever a reviewer records a pattern or failure.

2. **Wrapper and tool state matter.** Gemini deep-research mode produces 13.3 percent URL hallucination. Gemini search-augmented mode produces 4.6 to 4.8 percent. Same family, different surface, three times the hallucination rate. Claude with extended thinking differs from Claude without. GPT with browsing tools differs from GPT without. The family signature is a prior probability; the wrapper modifies the actual rate substantially.

3. **The signatures are blind spots, not exclusions.** A Claude piece can produce GPT-shaped URL fabrications. A GPT piece can produce Claude-shaped DOI fabrications. The per-family signature identifies where each family is MOST LIKELY to fail; it does not claim that each family is GUARANTEED to fail in those ways and only those ways. Apply the family-specific check first because it has the highest expected yield, then apply the universal checks from sections 4a through 4g and the C1 protocols for residual coverage.

---

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
