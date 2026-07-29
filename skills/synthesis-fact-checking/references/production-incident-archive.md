# Production Incident Archive (2023 to 2026)

**Companion file to:** `synthesis-fact-checking/SKILL.md` v2.0
**Last updated:** 2026-05-18
**Scope:** documented production incidents in which AI-generated content escaped human verification and reached publication, the courts, a paying audience, or peer review. Each entry records what was published, what specifically failed in the writer's or editor's fact-checking, which v2.0 protocol would have caught it, lessons for newsroom editors and fact-checkers, and verification notes for each cornerstone fact.

Every entry is a discrete catalog section. This file is a reference, not a narrative. Cross-references to `references/detailed-protocols.md` use the C1 IDs from v2.0 of the SKILL. Cross-references to v2.0 SKILL.md sections 4a through 4g (the refreshed Common Error Patterns) cite the C2 IDs.

Honest verification labels matter more than impressive incident counts. Where a fact has been independently verified during the writing of this file, it is recorded as `[verified 2026-05-18]` with the source. Where it has not, it is flagged with `[unverified at expansion]`, `[partially verified]`, or `[opus-expansion-unverified]` per the upgrade plan's verification protocol.

---

## Table of Incidents

| # | Incident | Year | Domain | Cornerstone protocol |
|---|----------|------|--------|----------------------|
| 1 | Mata v. Avianca | 2023 | Legal filing | C1-URLROT-001, C1-LAUNDER-001, 4f residual fabrication |
| 2 | Mostafavi sanction (California Court of Appeal) | 2025 | Legal filing | C1-URLROT-001, C1-LAUNDER-001, 4f residual fabrication |
| 3 | Goldberg Segalla / Chicago Housing Authority sanction | 2025 | Legal filing | C1-URLROT-001, C1-LAUNDER-001, 4f residual fabrication |
| 4 | Damien Charlotin's AI Hallucination Cases Database | 2025 onward | Legal meta-dataset | Cross-cutting: C1-URLROT-001, C1-LAUNDER-001, C1-SYNTH-001 |
| 5 | Chicago Sun-Times "Heat Index" summer reading list | 2025 | Newspaper feature | C1-SYNTH-001, 4d (entity), 4f residual fabrication |
| 6 | Springer Nature "Mastering Machine Learning" book | 2025 | Academic publishing | C1-LAUNDER-001, 4f residual fabrication |
| 7 | BBC and EBU "News Integrity in AI Assistants" report | 2025 | Cross-platform measurement | C1-URLROT-001, C1-NESTED-001, C1-PARAPH-001 |
| 8 | Topaz et al. Lancet letter on fabricated biomedical references | 2026 | Academic publishing | C1-SYNTH-001, C1-LAUNDER-001 |
| 9 | Stanford RegLab Magesh et al. measurements | 2024 | Legal-AI tool measurement | C1-URLROT-001, C1-TOOLHALL-001 |
| 10 | Tsinghua / Georgia Tech BrainMIND ICLR submission | 2025 | Academic publishing | C1-SYNTH-001, 4f residual fabrication |
| 11 | MAHA Report (White House chronic disease report) | 2025 | Government report | C1-LAUNDER-001, 4f residual fabrication, 4d entity |
| 12 | Megalopolis trailer fabricated critic quotes | 2024 | Marketing | C1-COMPOSITE-001, C1-PARAPH-001, 4e attribution |
| 13 | Washington Post "Your Personal Podcast" AI scripts | 2025 to 2026 | News product | C1-NESTED-001, C1-PARAPH-001, C1-COMPOSITE-001, 4e |
| 14 | Nieman Lab synthetic-byline cases (Blanchard, Goldiee) | 2025 to 2026 | News bylines | C1-SYNTH-001, C1-COMPOSITE-001, 4d entity |
| 15 | Google AI Overviews year bug | 2025 | Search product | 4g temporal drift, C1-TOOLHALL-001 |

---

## 1. Mata v. Avianca, Inc.

**Date.** June 22, 2023 (sanctions order). Underlying motion filed March 1, 2023.
**Venue.** United States District Court for the Southern District of New York. Judge P. Kevin Castel.
**Citation.** *Mata v. Avianca, Inc.*, 678 F. Supp. 3d 443 (S.D.N.Y. 2023).
**Domain.** Legal filing (federal civil case, personal injury).

### What happened

Roberto Mata filed a personal injury suit in February 2022 against Avianca Airlines after a metal beverage cart struck his knee on an international flight. When Avianca moved to dismiss the case on statute-of-limitations grounds tied to the Montreal Convention, Mata's counsel at Levidow, Levidow and Oberman filed an opposition brief citing prior cases including *Varghese v. China Southern Airlines*, *Martinez v. Delta Airlines*, *Shaboon v. Egyptair*, *Petersen v. Iran Air*, *Estate of Durden v. KLM Royal Dutch Airlines*, and *Miller v. United Airlines*. Avianca's counsel could not find any of these cases. Neither could the court.

Attorney Steven A. Schwartz had used ChatGPT to research the brief. When the court ordered him to produce the cases he had cited, he returned to ChatGPT, asked for full text excerpts, and submitted what the model produced. The submitted excerpts were fabrications layered on top of fabrications. Judge Castel imposed a $5,000 sanction jointly and severally on Schwartz, partner Peter LoDuca who had signed the brief, and the firm.

### What specifically failed in fact-checking

Three independent failures stacked.

First, Schwartz did not verify any of the cases ChatGPT produced. He asked the model whether the cases were real and accepted the model's confirmation as evidence. No primary-source check (case law database, court docket, Westlaw, Lexis) was performed.

Second, when Avianca's counsel and the court flagged the gap, Schwartz returned to the same tool that had produced the fabrications and asked it to produce the case text. He was asking the model that wrote the fiction to confirm its own fiction.

Third, partner LoDuca signed the brief without independently verifying the cited authority. The signing attorney was not the user of ChatGPT but is bound by Federal Rule of Civil Procedure 11 to verify what he signs.

### Which v2.0 protocol would have caught it

- **4f residual pure-fabrication (post-split).** Every cited authority must exist. A primary-source check via a case law database (Westlaw, Lexis, CourtListener, PACER) before filing would have surfaced the fabrications immediately. None of the cited cases existed in any case law database.
- **C1-LAUNDER-001 (citation laundering chains).** Schwartz built a one-source chain that converged on a single LLM upstream. The "confirmation" round was the same upstream confirming itself. The graph-independence test in C1-LAUNDER-001 would have classified the corroboration as zero-source.
- **C1-URLROT-001 (URL rot vs. hallucination distinction).** Although the failure is canonically a pure-fabrication case (no URLs to rot), the protocol's classification step (no Wayback record exists → classify as HALLUCINATED) is the correct shape: the cases have no record in any case law database, archive, or court docket.

### Lessons for newsroom editors and fact-checkers

1. The signing attorney, the editing editor, and the publishing publisher are each independently responsible for verifying the cited authority. Verification cannot be delegated to the original author or to the tool that produced the citation.
2. Asking a model to verify its own output is not verification. It is the same upstream answering twice.
3. Primary-source verification is mandatory for every citation, not for a sample. A 23 of 23 verification rate is the baseline; anything less is the Mata pattern.
4. The case established the legal-consequence baseline. Subsequent legal-AI cases (Mostafavi, Goldberg Segalla) are not surprises; they are foreseeable repetitions.

### Sources

- *Mata v. Avianca, Inc.*, 678 F. Supp. 3d 443 (S.D.N.Y. 2023) [verified 2026-05-18 via Justia: https://law.justia.com/cases/federal/district-courts/new-york/nysdce/1:2022cv01461/575368/54/].
- CNN Business, "Lawyer apologizes for fake court citations from ChatGPT," 2023-05-27 [verified 2026-05-18].
- Wikipedia, "Mata v. Avianca, Inc." [verified 2026-05-18].
- $5,000 sanction figure [verified 2026-05-18].

---

## 2. Mostafavi sanction (California Second District Court of Appeal)

**Date.** Approximately September 12, 2025 (Division Three of the Second District Court of Appeal opinion). [verified 2026-05-18 via CalMatters 2025-09 coverage].
**Venue.** California Court of Appeal, Second Appellate District, Division Three.
**Domain.** Legal filing (state appellate brief in an employment matter).

### What happened

Attorney Amir Mostafavi filed an appellate brief in a wage-and-hour and harassment case. The trial court had granted summary judgment against his client on the ground that the plaintiff was an independent contractor rather than an employee. Mostafavi's appellate brief contained 23 quoted case citations in the opening brief. Of those 23, the panel found that 21 were fabricated by generative AI. The reply brief contained additional fabrications.

Per published reporting, Mostafavi used ChatGPT to "enhance" the brief, then ran the output through Claude, Gemini, and Grok for verification. None of the four models surfaced the fabrications. The panel imposed a $10,000 sanction and referred Mostafavi to the State Bar of California. The opinion was the first published California Court of Appeal opinion sanctioning a lawyer for AI hallucinations.

### What specifically failed in fact-checking

The verification design was the core failure. Mostafavi treated cross-model agreement as verification: if all four models accepted the citations, the citations must be real. This is the exact pattern C1-LAUNDER-001 addresses. Three or four LLMs agreeing on a fabricated case do not constitute independent corroboration. They share training data, share fine-tuning patterns, share helpfulness-optimization biases, and in this domain produce mutually reinforcing fabrications.

The cross-model "check" is the canonical failure of the multi-source confidence framework in section 2 of the v1.1.0 SKILL when graph independence is not verified. v2.0 makes graph independence (not raw count) the condition.

### Which v2.0 protocol would have caught it

- **C1-LAUNDER-001 (citation laundering chains).** Three or four LLM outputs converging on the same citations is single-sourced when all four trace to overlapping training data. The graph-independence test would have surfaced the convergence and downgraded the corroboration confidence to single-source.
- **C1-TOOLHALL-001 (tool-specific hallucination patterns).** Each of the four models has a known fabrication signature in the legal domain. Per-family priority checks (verify every URL for GPT, verify every DOI for Claude, verify every "study" with a Google Scholar search for Gemini) would have prompted Mostafavi to take the citations to a case-law database rather than to another model.
- **4f residual pure-fabrication.** Direct case-law database verification (Westlaw, Lexis, CourtListener) was never performed. The cases do not exist in any database.

### Lessons for newsroom editors and fact-checkers

1. Cross-LLM agreement is not verification. The v1.1.0 multi-source framework's "3 to 4 sources cite the same claim → very high confidence, still verify against primary source" rule is the load-bearing word. Without primary-source verification, the high confidence is illusory.
2. v2.0's revision to multi-source confidence requires graph independence, not raw count. Three sources that all trace to one upstream are single-sourced.
3. The legal-domain hallucination rate of 17 to 33 percent (Stanford RegLab Magesh et al., 2024; see incident 9) is the floor when retrieval-augmented generation is in use. Without RAG, the rates are higher. Cross-LLM checks do not lower this floor.
4. The "first published opinion" status of this case means the doctrine is now binding in California. Other state appellate courts will follow.

### Sources

- CalMatters, "California issues historic fine over lawyer's ChatGPT fabrications," September 2025: https://calmatters.org/economy/technology/2025/09/chatgpt-lawyer-fine-ai-regulation/ [verified 2026-05-18].
- Daily Journal, "State Court of Appeal issues 1st opinion sanctioning lawyer for AI 'hallucinations'" [verified 2026-05-18].
- Daily Journal, "Four AIs, 21 fabrications, one $10,000 sanction" [verified 2026-05-18].
- Metropolitan News-Enterprise, "$10,000 Sanction Imposed Based on Fake Quotes in Briefs," 2025-09-15 [verified 2026-05-18].
- $10,000 sanction figure [verified 2026-05-18]. The exact case caption is not present in the public reporting consulted [unverified at expansion]. The date is published reporting's "10 days ago from September 22" framing rather than a docket-confirmed date [partially verified].

---

## 3. Goldberg Segalla / Chicago Housing Authority sanction

**Date.** December 9, 2025 (sanctions order).
**Venue.** Cook County Circuit Court, Illinois. Judge Thomas Cushing presiding.
**Domain.** Legal filing (state civil case, lead paint poisoning).

### What happened

The Chicago Housing Authority was the defendant in a lead-paint-poisoning suit involving two children at 7715 N. Marshfield Avenue in Rogers Park. In January 2026, a Cook County jury found the CHA liable and awarded over $24 million in damages. After the verdict, the CHA's attorneys at Goldberg Segalla filed a post-trial motion seeking reconsideration. The motion cited *Mack v. Anderson*, an Illinois Supreme Court case the lawyers represented as directly supporting their argument. *Mack v. Anderson* does not exist.

The fabricated citation was the visible failure. The court's subsequent review found "a pattern of repetitive and continuous misrepresentations" beyond the single citation. Judge Cushing imposed $59,500 in sanctions: $10,000 against attorney Larry Mason (lead counsel who signed the motion) and $49,500 against the firm. The judge described the conduct as "a serious failure," citing "the inexcusable submission of false authority and factual arguments to the court, the subsequent misrepresentations about the extent of the improper conduct, and the failure to take prompt responsibility for errors once discovered."

Attorney Danielle Malaty, who used ChatGPT to generate the citation and did not verify it, was fired from Goldberg Segalla in June 2025. She was subsequently sanctioned in a separate case in July 2025 in which two of her court filings contained 12 hallucinated case citations.

### What specifically failed in fact-checking

Two failures, both shared with Mata.

First, Malaty asked ChatGPT for a supporting Illinois Supreme Court case, accepted the model's output, and inserted it into the motion. No primary-source check via Westlaw, Lexis, or the Illinois Supreme Court's own opinions database was performed. Per the court record, Malaty told the judge she "did not think ChatGPT could create fictitious legal citations."

Second, the signing attorney (Mason) did not independently verify the cited authority. The downstream review process at Goldberg Segalla did not flag the citation. The pattern repeated across multiple filings before the court surfaced it.

### Which v2.0 protocol would have caught it

- **4f residual pure-fabrication.** A 30-second Westlaw or Lexis search would have surfaced the absence of *Mack v. Anderson*. The Illinois Supreme Court's published opinions are searchable. The case does not exist.
- **C1-LAUNDER-001 (citation laundering chains).** The "corroboration" chain consisted of one prompt to one model. Graph independence would have classified the claim as zero-source.
- **C1-TOOLHALL-001 (tool-specific hallucination patterns).** GPT family models confabulate plausible case names with high confidence in legal domains. The per-family priority check (verify every URL, verify every citation) would have flagged the case for primary-source verification.

### Lessons for newsroom editors and fact-checkers

1. The Mata pattern (incident 1) reached an AmLaw 200 firm two and a half years later. The 30-month interval is not a sign of progress. It is a sign that institutional verification protocols did not respond to a high-visibility cautionary precedent.
2. The $59,500 sanction (compared to Mata's $5,000) marks the calibration of judicial impatience. Subsequent firm-level sanctions will be larger.
3. Termination of the immediate user (Malaty) did not resolve the institutional failure. The firm-level $49,500 sanction reflects the firm-level failure to verify before signing.
4. The pattern of "repetitive and continuous misrepresentations" the court found means the review protocol was not just absent on the citation, it was absent across the case. Newsrooms and firms with similar AI tooling should audit the corpus, not just the surface-flagged document.

### Sources

- Chicago Sun-Times, "Attorney and law firm for Chicago Housing Authority sanctioned nearly $60,000 for using ChatGPT in court case," 2025-12-09: https://chicago.suntimes.com/the-watchdogs/2025/12/09/goldberg-segalla-law-firm-cha-sanctioned-60-000-ai-chatgpt-lead-paint-court-case [verified 2026-05-18].
- Above the Law, "Biglaw AI Apocalypse Brews As One Fake Case Turns Into Litany Of False Cites," July 2025 [verified 2026-05-18].
- The Real Deal Chicago, "Housing authority lawyer cites fake AI-generated case in court filing," 2025-07-18 [verified 2026-05-18].
- $59,500 total sanction ($10,000 + $49,500) [verified 2026-05-18]. The originating brief in this archive cited "$60,000 approximate"; the precise figure is $59,500.

---

## 4. Damien Charlotin's AI Hallucination Cases Database

**Date.** Database launched and maintained from 2024 onward; cited counts here are as of late 2025 and early 2026.
**Venue.** Independent database; Charlotin is a researcher at HEC's Smart Lab and a practitioner at Pelekan Data Consulting in Paris.
**Domain.** Legal meta-dataset.

### What happened

Charlotin maintains the most comprehensive public database of court cases where AI hallucinations have been addressed by judges. The database tracks cases worldwide, searchable by country, party, AI tool, and outcome. As of the most recent count this archive could verify, the database contains 1,455 cases. The count continues to grow; daily updates reflect new sanctioned filings.

A separate reporting in April 2026 (Reason / Volokh Conspiracy) documented 17 U.S. court decisions noting suspected AI hallucinations filed on a single day (March 31, 2026), suggesting the rate is accelerating.

Charlotin has developed an automated reference checker (PelAIkan) and a related AI Evidence Database.

### What this incident documents (it is a meta-record, not a single-case failure)

The database is itself the evidence base for the claim that AI fabrication in legal filings is now a routine failure pattern, not an isolated incident. It supports the empirical grounding for v2.0's structural change (the demotion of 4f as a single bucket and the split into C1-URLROT, C1-SYNTH, C1-LAUNDER plus residual pure-fabrication).

### Which v2.0 protocol the database supports

- **C1-URLROT-001 (URL rot vs. hallucination distinction).** The classification taxonomy (HALLUCINATED, STALE, REDIRECTED, RETRACTED, PAYWALLED, UPDATED) is grounded in the database's cases.
- **C1-SYNTH-001 (AI-generated synthetic sources).** The database tracks not just citation hallucinations but also cases where AI-generated content was treated as primary evidence.
- **C1-LAUNDER-001 (citation laundering chains).** The database's growth rate suggests that the laundering mechanism (LLM output entering legal databases, being cited, becoming "precedent") is operating at scale.

### Lessons for newsroom editors and fact-checkers

1. The base rate is high enough that "this could not happen to us" is not a defensible assumption. The database includes cases from firms ranging from solo practitioners to AmLaw 200.
2. The verification cost (Westlaw search per citation) is low relative to the sanction risk. The economics are not borderline; they are obvious.
3. The database is itself a resource: editors can search by AI tool to understand which models tend to produce which fabrication signatures. This supports C1-TOOLHALL-001.

### Sources

- Damien Charlotin, "AI Hallucination Cases Database": https://www.damiencharlotin.com/hallucinations/ [verified 2026-05-18].
- 1,455 cases figure [verified 2026-05-18].
- Reason / Volokh Conspiracy, "In One Day (Mar. 31), 17 U.S. Court Decisions Noting Suspected AI Hallucinations in Court Filings," 2026-04-06 [verified 2026-05-18].
- Stanford CyberLaw, "Who's Submitting AI-Tainted Filings in Court?" 2025-10 [verified 2026-05-18].

---

## 5. Chicago Sun-Times "Heat Index" summer reading list

**Date.** Published May 18, 2025 in the "Heat Index: Your Guide to the Best of Summer" supplement.
**Venue.** Chicago Sun-Times; supplement distributed with the Sunday print edition.
**Domain.** Newspaper feature (syndicated content).

### What happened

The Sun-Times published a 64-page summer supplement, "Heat Index," with a 15-title summer reading list. Ten of the 15 recommended titles did not exist. The fabricated titles included Isabel Allende's "Tidewater Dreams" (described as her "first climate fiction novel") and Percival Everett's "The Rainmakers" (set in a "near-future American West where artificially induced rain has become a luxury commodity"). The titles were attributed to real authors and were stylistically consistent with each author's actual catalog. Real titles on the list included Ray Bradbury's "Dandelion Wine," Jess Walter's "Beautiful Ruins," and Françoise Sagan's "Bonjour Tristesse."

Freelance writer Marco Buscaglia produced the supplement under license to King Features Syndicate. Buscaglia used AI to assist his research and acknowledged after the incident that he did not fact-check the AI output. King Features distributed the supplement to the Sun-Times and at least one other newspaper. NPR's May 20 coverage triggered the broader response.

### What specifically failed in fact-checking

Four failures stacked.

First, at the writer level: Buscaglia did not perform the basic verification step of checking each book against the author's published catalog. A 30-second search per title against Goodreads, Amazon, the publisher's catalog, or even the author's own website would have surfaced every fabrication.

Second, at the syndicator level: King Features distributed the supplement without verification.

Third, at the newspaper level: the Sun-Times published the supplement without independent verification of syndicated content. The newspaper's editorial workflow treated syndicated copy as pre-verified.

Fourth, the failure was simultaneous across multiple outlets (the Philadelphia Inquirer's print edition also carried the supplement per some reporting). The syndication model failed the same way at each outlet because no outlet performed the verification step the syndicator assumed someone else had performed.

### Which v2.0 protocol would have caught it

- **C1-SYNTH-001 (AI-generated synthetic sources).** The "books" themselves are synthetic sources: AI-generated entities presented as primary evidence (in this case, primary cultural artifacts). The trace-back procedure (verify the cited work's basic provenance via a credible bibliographic database) would have surfaced the absence of each fabricated title in Goodreads, WorldCat, Amazon, or the publisher's catalog.
- **4d (incorrect organization or entity names) per v2.0 refresh.** The fabricated titles are entity-name fabrications layered onto real authors. The registry-check requirement (verify via the publisher's catalog and the author's own website) would have caught the fabrications. Net synthesis from C2-4D-001: niche/rebranded/synthetic entity confusion has worsened; this incident is a case-in-point.
- **4f residual pure-fabrication.** The titles are pure fabrications, not stale citations. No archive version of the books exists because the books were never written.

### Lessons for newsroom editors and fact-checkers

1. Syndicated content is not pre-verified. The publishing outlet is responsible for the content it distributes, including content licensed from a syndicator.
2. AI-generated cultural recommendations (books, films, restaurants, products, locations) carry an especially high fabrication risk because the surface form (a plausible title by a real author) does not trigger the verification reflex. The reflex needs to be trained on the form, not on the trigger.
3. The remediation step ("verify every cited book against its author's catalog") is cheap. The cost of skipping it (subscriber trust, syndication contract review, advertising-side fallout) is large.
4. The incident was a six-month leading indicator for the Washington Post AI podcast failure (incident 13). Both incidents involved AI-generated cultural or quote-bearing content distributed at scale without per-item verification.

### Sources

- NPR, "How an AI-generated summer reading list got published in major newspapers," 2025-05-20 [verified 2026-05-18].
- Chicago Sun-Times, "Syndicated content in Sun-Times special section included AI-generated misinformation," 2025-05-20 [verified 2026-05-18].
- CBC News, "Chicago newspaper prints a summer reading list. The problem? The books don't exist," 2025-05 [verified 2026-05-18].
- Snopes fact-check confirming the AI-generated supplement [verified 2026-05-18].

---

## 6. Springer Nature "Mastering Machine Learning" book

**Date.** Published April 2025. Retracted following Retraction Watch coverage; Springer formally announced retraction in August 2025.
**Venue.** Springer Nature (academic publisher).
**Domain.** Academic publishing (textbook).

### What happened

Springer Nature published "Mastering Machine Learning: From Basics to Advanced" by Govindakumar Madhavan in April 2025. The book was priced at $169 for the ebook edition. Within weeks of publication, multiple academics whose names appeared in the book's references reported that the works attributed to them did not exist or were misattributed. Retraction Watch audited 18 of the book's 46 citations and found that two-thirds of them either referenced nonexistent papers or misattributed authorship and publication sources.

Springer Nature initially acknowledged the situation in a statement: "We are aware of the text and are currently looking into it." Following sustained press coverage (Retraction Watch, The Bookseller, Slashdot, Digital Watch), Springer announced its intent to retract on July 16, 2025, and formally retracted on or about August 4, 2025. The book was withdrawn from circulation.

Madhavan did not confirm whether AI tools were used to produce the content, but the citation morphology (plausible-sounding titles, real authors, fabricated DOIs and journal venues) is the canonical signature of LLM-generated reference lists. Springer's AI-use policies require authors to declare AI involvement beyond basic copyediting; the book contained no such declaration.

### What specifically failed in fact-checking

The failure chain begins at the author and runs through the publisher's editorial review.

Author level: Madhavan submitted citations that, on the face of the text, could be sampled and verified in minutes via Google Scholar or CrossRef. Two-thirds of the sampled citations did not survive that verification step. Either the author did not perform the verification step or did not understand it was necessary.

Publisher level: Springer's editorial review did not catch a two-thirds fabrication rate in the reference list. A 5 to 10 citation sample at any stage of the editorial workflow would have surfaced the pattern with near-certainty. The review process either did not perform the sample or did not require the verification.

### Which v2.0 protocol would have caught it

- **4f residual pure-fabrication.** A Google Scholar or CrossRef search on the sampled citations would have surfaced the fabrications. The Springer Mastering ML pattern is the textbook (no pun intended) case of pure fabrication: real authors, plausible titles, real-sounding journals, no DOI resolution, no Scholar record.
- **C1-LAUNDER-001 (citation laundering chains).** The fabrications were inserted into a book that would be cited by other AI tools, downstream LLMs, and human researchers as a textbook source. The laundering chain begins at the book's publication. The detection difficulty rises for every downstream citation: by the time the fabrications appear in a master's thesis citing this textbook, the trace-back chain is two hops long.
- **C1-SYNTH-001 (AI-generated synthetic sources).** The book itself, after publication and indexing in Springer's catalog, became an AI-generated synthetic source that later AI tools would treat as a primary text on machine learning.

### Lessons for newsroom editors and fact-checkers

1. Editorial workflows that rely on the author's verification are not workflows. They are signatures on the author's verification. The publisher must independently sample-verify citations.
2. The two-thirds fabrication rate is the rate after editorial review. The rate before editorial review (the rate in the unedited manuscript) is presumably even higher. The signal from this incident is that publishers' AI-use disclosures are not enforceable without sample audits.
3. The book was priced at $169 and entered Springer's catalog as a reference text. Downstream readers and other AI tools will cite it. The damage propagates after the retraction.
4. Springer's response (retract, restate AI-use policy) is the correct response. The systemic issue is that the policy was already in place before the book was published and the policy did not catch the book.

### Sources

- Retraction Watch, "Springer Nature book on machine learning is full of made-up citations," 2025-06-30: https://retractionwatch.com/2025/06/30/springer-nature-book-on-machine-learning-is-full-of-made-up-citations/ [verified 2026-05-18].
- Retraction Watch, "Springer Nature to retract machine learning book following Retraction Watch coverage," 2025-07-16 [verified 2026-05-18].
- Retraction Watch, "Springer Nature retracts book with fake citations. Help us find more cases like this," 2025-08-04 [verified 2026-05-18].
- The Bookseller, "Springer Nature retracts Machine Learning book after citations 'reference works that don't exist'" [verified 2026-05-18].
- Citation audit fraction (two-thirds of 18 sampled citations) [verified 2026-05-18]. The unified bucket C cited the fraction as "two-thirds of references fabricated"; Retraction Watch's sample was 18 of 46 citations checked. The two-thirds figure applies to the 18 checked, not to all 46 citations in the book.

---

## 7. BBC and European Broadcasting Union "News Integrity in AI Assistants" report

**Date.** Released October 21, 2025.
**Venue.** Joint study by the European Broadcasting Union (EBU) and the BBC. 22 public service media organizations across 18 countries participated.
**Domain.** Cross-platform measurement (consumer AI assistants).

### What happened

The EBU and BBC organized one of the largest cross-market evaluations of AI assistant accuracy on news questions. Professional journalists from 22 public service media organizations in 18 countries, working in 14 languages, evaluated more than 3,000 AI responses against criteria including accuracy, sourcing, opinion/fact distinction, and contextual completeness. The platforms tested included OpenAI's ChatGPT, Microsoft's Copilot, Google's Gemini, and Perplexity.

Headline finding: 45 percent of AI responses contained at least one significant issue. 81 percent contained some form of problem. Sourcing was the single largest failure mode: 31 percent of responses showed significant sourcing problems (missing, misattributed, or misleading citations). Gemini was the least reliable tool measured, with significant issues in 76 percent of its responses, primarily due to poor sourcing. Approximately one-fifth of responses contained major accuracy issues, including hallucinations and outdated information.

The study is not an "incident" in the single-publication sense. It is the empirical evidence base for a class of incidents: every reader who used an AI assistant to get news on the days the study sampled was in the population the 45 percent rate applied to. The study quantifies the prevalence the other entries in this archive document case-by-case.

### What this incident documents

The base rate of significant issues in AI news responses is approximately 45 percent in mid-to-late 2025. The base rate of sourcing failures is approximately 31 percent. The worst-performing platform (Gemini) had a 76 percent significant-issue rate.

### Which v2.0 protocol would have caught it (or rather, which v2.0 protocol the data supports)

- **C1-NESTED-001 (nested attribution).** Sourcing failures include misattribution and missing citations, both of which are nested-attribution failures.
- **C1-PARAPH-001 (paraphrase boundary drift).** "Misleading citations" includes paraphrase drift, in which the AI paraphrase does not accurately represent the source.
- **C1-URLROT-001 (URL rot vs. hallucination distinction).** Missing citations is the symptom; the distinction between hallucinated and stale is the diagnostic step.
- **C1-TOOLHALL-001 (tool-specific hallucination patterns).** Gemini's 76 percent significant-issue rate is consistent with the Penn 2026 finding (13.3 percent hallucinated URL rate in Gemini deep-research mode). The per-family fingerprint shows in the cross-platform measurement.

### Lessons for newsroom editors and fact-checkers

1. The 45 percent significant-issue rate sets the lower bound for editorial expectations. An editor reviewing AI-generated content should expect to find a significant issue in roughly half the AI responses.
2. The 31 percent sourcing-failure rate sets the expectation specifically for citations. Roughly one in three citations in AI output has a problem.
3. Gemini's 76 percent rate is not a one-time finding; it is consistent with prior measurements (Penn 2026's 13.3 percent deep-research URL hallucination rate, the highest in their sample). For newsrooms using Gemini-based tools for research, the per-family priority check (verify every citation; flag every vague "studies show" attribution) is mandatory.
4. The study's methodology (professional journalists evaluating against accuracy and sourcing criteria in 14 languages) is replicable. Newsroom editors should consider running internal audits against the same protocol.

### Sources

- EBU and BBC, "News Integrity in AI Assistants" report, October 2025: https://www.ebu.ch/research/open/report/news-integrity-in-ai-assistants and toolkit at https://www.ebu.ch/Report/MIS-BBC/NI_AI_2025.pdf [verified 2026-05-18].
- Al Jazeera, "AI models misrepresent news events nearly half the time, study says," 2025-10-22 [verified 2026-05-18].
- CBC News, "Top AI assistants misrepresent news content, study finds" [verified 2026-05-18].
- The Register, "AI chatbots flub news nearly half the time, BBC study finds," 2025-10-24 [verified 2026-05-18].
- 45 percent significant-issue rate, 31 percent sourcing failures, 76 percent Gemini significant-issue rate [verified 2026-05-18].

---

## 8. Topaz et al. Lancet letter on fabricated biomedical references

**Date.** Published May 7, 2026 in *The Lancet* as a letter to the editor.
**Venue.** *The Lancet* (peer-reviewed medical journal). Lead author Maxim Topaz, Columbia University Data Science Institute.
**Domain.** Academic publishing (biomedical literature).

### What happened

Topaz and colleagues audited approximately 2.5 million PubMed-indexed papers for fabricated references. The audit used AI tooling to "distinguish genuine fabrications from formatting discrepancies such as informally abbreviated titles." References were verified against PubMed, CrossRef, OpenAlex, and Google Scholar. References not found in any of the four databases were classified as fabricated.

The audit identified 4,406 fabricated references across 2,810 papers. 91 percent of the affected papers contained only one or two fake references. The trend over time:

- 2023: 1 in 2,828 papers contained a fabricated reference
- 2025: 1 in 458 papers
- 2026 (first seven weeks): 1 in 277 papers

This is a 12-fold rise over two years (from 2023 to first seven weeks of 2026). Earlier reporting from the same research group framed the rise as "sixfold from 2023 to 2025"; the 12-fold figure incorporates the 2026 acceleration. The two framings (sixfold and twelvefold) refer to overlapping but distinct time windows. The 12-fold rise is the cumulative growth from 2023 to early 2026; the sixfold rise is from 2023 to end of 2025. v2.0 of the fact-checking SKILL should use the 12-fold figure when citing the full window and the 1-in-277 figure when citing the 2026 rate; flag both framings if the surrounding prose creates ambiguity.

Topaz's group located the sharpest increase in mid-2024, coincident with the broader uptake of AI writing tools in academic workflows.

### What specifically failed (across the 2,810 affected papers)

For each affected paper, the failure chain has three layers.

First, the author submitted a manuscript with at least one fabricated reference. The reference was likely produced by an LLM tool used during writing or reference compilation; the citation morphology (plausible authors, plausible titles, no DOI resolution or no PubMed record) is the canonical signature.

Second, the manuscript passed peer review. Peer reviewers did not perform the basic verification step (PubMed search, CrossRef DOI resolution) on the cited references. This is consistent with the editorial review failure seen at Springer (incident 6) at the journal scale.

Third, the manuscript was published and indexed in PubMed. Once indexed, the fabricated reference becomes a target for downstream citation in other papers, creating a laundering chain.

### Which v2.0 protocol would have caught it

- **C1-SYNTH-001 (AI-generated synthetic sources).** The fabricated references are synthetic sources presented as real biomedical literature. The trace-back procedure (verify the cited work's basic provenance via PubMed, CrossRef, OpenAlex, Google Scholar) is exactly the verification protocol Topaz's group ran. The 1-in-277 rate represents papers where this protocol was not run before publication.
- **C1-LAUNDER-001 (citation laundering chains).** Once a paper with a fabricated reference is indexed in PubMed, downstream papers can cite it. The laundering chain grows hop-by-hop, and the trace-back cost grows correspondingly.
- **4f residual pure-fabrication.** The fabrications are pure-fabrication failures: references that exist in no database, with no archive record, and no resolving DOI.

### Lessons for newsroom editors and fact-checkers

1. The biomedical-publication rate is the closest available proxy for "what happens to text when editorial review is at its most rigorous." Even peer-reviewed, PubMed-indexed publications have a 1-in-277 fabrication rate in early 2026. The non-peer-reviewed and non-indexed corpus is presumably higher.
2. The 12-fold rise over two years is a leading-indicator measurement, not a static one. By the time the v2.0 SKILL is shipped, the rate is likely higher than 1-in-277.
3. The 91 percent of affected papers contained only one or two fake references means the pattern is not whole-citation-list fabrication; it is selective insertion. The verification protocol must operate at the per-citation level, not at the per-manuscript level.
4. The mid-2024 inflection point coincides with the uptake of long-context LLMs in academic workflows. This is the empirical anchor for v2.0's per-family hallucination signatures (C1-TOOLHALL-001) and per-domain priority checks. Medical citation domains require heightened scrutiny.

### Sources

- Topaz, M. et al. (2026). "Fabricated citations: an audit across 2.5 million biomedical papers." *The Lancet*, letter, May 7, 2026 [verified 2026-05-18 via Retraction Watch and Nature coverage; primary Lancet URL https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(26)00798-1/abstract returned 403 on automated fetch but exists as a published letter].
- Retraction Watch, "One in 277 PubMed-indexed papers in 2026 shows fabricated references, says analysis," 2026-05-07 [verified 2026-05-18].
- Nature, "Surge in fake citations uncovered by audit of 2.5 million biomedical-science papers," 2026 [verified 2026-05-18].
- The Scientist, "One in 277 Biomedical Papers Carry Fake References," 2026 [verified 2026-05-18].
- CIDRAP and EurekAlert reporting [verified 2026-05-18].
- 1-in-277 rate, 12-fold rise, 4,406 fabricated references, 2,810 affected papers [verified 2026-05-18].

---

## 9. Stanford RegLab Magesh et al. measurements

**Date.** Preprint May 2024; subsequently peer-reviewed and published in the *Journal of Empirical Legal Studies*, 2025.
**Venue.** Stanford RegLab and Stanford HAI. Authors: Varun Magesh, Faiz Surani, Matthew Dahl, Mirac Suzgun, Christopher D. Manning, Daniel E. Ho.
**Domain.** Legal-AI tool measurement.

### What happened

The Stanford team performed the first preregistered empirical evaluation of commercial legal AI tools. They tested three products: LexisNexis's Lexis+ AI, Thomson Reuters's Ask Practical Law AI, and Thomson Reuters's Westlaw AI-Assisted Research. The test set consisted of 202 legal queries, with responses hand-scored by legal experts.

Headline finding: the tested legal-AI tools hallucinated on between 17 percent and 33 percent of queries. Westlaw AI-Assisted Research had the highest rate at approximately 33 percent, roughly twice the rate of Lexis+ AI. All three products had been marketed as "hallucination-free" or "RAG-grounded" by their vendors. The measurement falsified the vendor claim.

A related study by Dahl et al. (also from Stanford) found broader legal-domain LLM hallucination rates of 58 to 88 percent in general-purpose models (not RAG-augmented), establishing the rate floor when RAG is not in use.

### What this incident documents

Retrieval-augmented generation does not eliminate hallucination. Even with primary-source retrieval from authoritative legal databases, hallucination rates remain in the double-digit-percent range. The vendor claim of "hallucination-free" RAG is empirically false at the rates measured.

### Which v2.0 protocol the measurement supports

- **C1-TOOLHALL-001 (tool-specific hallucination patterns).** The 17 to 33 percent rate is the empirical anchor for the Claude vs. GPT vs. Gemini per-family hallucination signatures. RAG-augmented legal tools fabricate at measurable rates; the per-family signatures explain the differential.
- **C1-LAUNDER-001 (citation laundering chains).** RAG retrieves real cases, but the model's generated synthesis can still produce fabricated holdings, fabricated quotations, and fabricated propositions even when the underlying case is real. The laundering happens within a single response, not across responses.
- **4f residual pure-fabrication.** The headline rate is the rate of pure fabrication in legal-AI tools that vendors had marketed as immune to fabrication.

### Lessons for newsroom editors and fact-checkers

1. "RAG-grounded" or "retrieval-augmented" or "uses our proprietary database" is not a substitute for verification. The 17 to 33 percent rate is the rate after RAG.
2. The Westlaw and Lexis+ products are not exotic configurations. They are flagship commercial legal-AI tools used by every major firm. The rate measured in the Stanford study is the rate at industry-leading tooling.
3. Newsroom editors should not assume that AI tools labeled as "research-grade" or "fact-checked" have lower hallucination rates than generic LLMs. The vendor marketing claim is not the empirical rate.
4. The follow-on Dahl et al. measurement (58 to 88 percent legal-domain hallucination without RAG) establishes the floor. The 17 to 33 percent RAG-augmented rate is the improvement, not the absolute.

### Sources

- Magesh, V., Surani, F., Dahl, M., Suzgun, M., Manning, C. D., and Ho, D. E. (2024). "Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools." Stanford RegLab preprint; subsequently published *Journal of Empirical Legal Studies*, 2025 [verified 2026-05-18 via Stanford RegLab publication page: https://reglab.stanford.edu/publications/hallucination-free-assessing-the-reliability-of-leading-ai-legal-research-tools/].
- Stanford HAI, "AI on Trial: Legal Models Hallucinate in 1 out of 6 (or More) Benchmarking Queries" [verified 2026-05-18].
- Stanford Law School, "Hallucinating Law: Legal Mistakes with Large Language Models are Pervasive," 2024-01-11 [verified 2026-05-18].
- GitHub reglab/legal_hallucinations repository for Dahl et al., 2024 [verified 2026-05-18].
- 17 to 33 percent rate, 202 queries, Westlaw 33 percent rate [verified 2026-05-18].

---

## 10. Tsinghua / Georgia Tech BrainMIND ICLR submission

**Date.** Submitted to ICLR 2025; withdrawn after reviewer flagging.
**Venue.** International Conference on Learning Representations (ICLR), top-tier machine learning conference.
**Domain.** Academic publishing (peer-reviewed conference submission).

### What happened

Researchers at the Georgia Institute of Technology and Tsinghua University submitted a paper titled "BrainMIND" to ICLR. The paper promised an interpretable mapping of brain activity. Reviewers found that the reference list contained completely fabricated titles and placeholder names like "Jane Doe" as co-authors. A reviewer flagged the obvious LLM-generated reference list and issued a "Strong Reject" recommendation. The authors revised the manuscript and references, but additional errors surfaced. The authors withdrew the paper.

This is one of several documented cases of fabricated citations at top-tier ML venues including NeurIPS and ICLR; BrainMIND is the most-discussed instance.

### What specifically failed in fact-checking

Author-level failure: the manuscript was submitted with a reference list containing "Jane Doe" placeholder author names. The reference list was not even spot-checked by the authors before submission. The use of placeholder names suggests the references were generated by an LLM with the placeholder substitution incomplete or that the authors did not review the model output.

Peer-review-level absorption: the reference-list failure was caught by reviewers, but not before the manuscript reached the review stage. The submission process treated the reference list as the author's responsibility to verify; no submission-side check was performed.

### Which v2.0 protocol would have caught it

- **C1-SYNTH-001 (AI-generated synthetic sources).** The references are synthetic sources. The trace-back procedure would have surfaced the "Jane Doe" placeholder names and the absence of the cited papers from Google Scholar, OpenAlex, or arXiv.
- **4f residual pure-fabrication.** The references are pure fabrications. A Google Scholar search would have caught the placeholder names immediately.
- **C1-TOOLHALL-001 (tool-specific hallucination patterns).** The pattern (fabricated references with placeholder names) is consistent with LLM-generated reference lists where the model's training data contains "Jane Doe" as a generic placeholder.

### Lessons for newsroom editors and fact-checkers

1. Top-tier peer review at ML conferences is the closest available proxy for "what happens to text when expert technical review is the most rigorous." Even at this venue, fabricated reference lists pass into the review queue. The verification gap is at the submission step, not at the review step.
2. The "Jane Doe" placeholder name is a visible signal that should have been caught by a 30-second review of the reference list. The fact that it was not caught suggests authors were not reviewing model output before submission.
3. NeurIPS and ICLR have documented AI-hallucinated citations passing into accepted papers. The conference acceptance is not the verification floor; it is the post-review state.
4. The lesson for newsrooms publishing technical commentary: if top-tier ML peer review can miss fabricated references, generic editorial review will miss them too. Citation verification is the editor's responsibility, not the author's.

### Sources

- The Decoder, "Frustrated authors withdraw papers after realizing their reviewers are just lazy LLMs" [verified 2026-05-18].
- arxiv 2602.15871 "CheckIfExist: Detecting Citation Hallucinations in the Era of AI-Generated Content" [verified 2026-05-18].
- arxiv 2602.00319 "Detecting AI-Generated Content in Academic Peer Reviews" [verified 2026-05-18].
- "Artificial intelligence in the retraction spotlight: trends, causes and consequences of withdrawn AI literature through a systematic bibliometric review," PMC12864414 [verified 2026-05-18].
- BrainMIND specific incident details (Georgia Tech + Tsinghua co-authorship, "Jane Doe" placeholder names, ICLR submission and withdrawal) [partially verified]. The named paper title "BrainMIND" appears in The Decoder reporting; the exact ICLR submission docket is not in the consulted reporting [partially verified at expansion].

---

## 11. MAHA Report (White House chronic disease report)

**Date.** Initial version released May 2025; corrected version released following press coverage.
**Venue.** "Make America Healthy Again" Commission report on chronic disease, issued by the Department of Health and Human Services under Secretary Robert F. Kennedy Jr.
**Domain.** Government report.

### What happened

The MAHA Report was released as the White House's authoritative document on chronic disease in children. The initial version contained 522 footnotes to scientific research. The Washington Post and NOTUS investigated the citations and found multiple problems:

- At least 37 footnotes contained the marker "oaicite," an OpenAI citation-generation indicator. The marker's presence in the published report indicates the citations were generated by ChatGPT and the generation artifacts were not stripped before publication.
- At least 37 footnotes appeared multiple times (duplicate citations of the same source).
- At least seven cited studies do not exist.
- Multiple cited studies have wrong authors attributed.

After press coverage, HHS released a corrected version. NOTUS reported that the corrected version removed the citations to non-existent studies but introduced new errors.

### What specifically failed in fact-checking

Three failures stacked.

First, the writing process: at least 37 citations in a government report retained the "oaicite" marker, which is the LLM citation-generation artifact. The marker should have been stripped by any minimally competent review process. Its presence indicates the report was generated with LLM tooling and the model output was inserted without review.

Second, the editorial review: a citation-by-citation verification of the 522 footnotes would have surfaced both the duplicate citations and the seven non-existent studies. Either the verification did not happen or the threshold for "found at least one error" was higher than 7-out-of-522.

Third, the institutional process: the report was issued by a federal commission. The signatures on the report represent a federal commission's endorsement of its accuracy. No subsequent retraction was issued; the document was "corrected" in place.

### Which v2.0 protocol would have caught it

- **4f residual pure-fabrication.** A PubMed or Google Scholar search on the seven non-existent studies would have surfaced them. The duplicate-citation pattern is detectable by a simple unique-count check on the footnote list.
- **C1-TOOLHALL-001 (tool-specific hallucination patterns).** The "oaicite" marker is the GPT family's citation-generation signature. A document containing the marker has a high prior probability that the surrounding citations are LLM-generated and require per-citation verification.
- **C1-LAUNDER-001 (citation laundering chains).** The report's policy weight means downstream documents will cite it. Each fabricated citation now has a federal government source citing it; the laundering chain begins at the report's publication.
- **4d (incorrect organization or entity names) per v2.0 refresh.** The wrong-author attributions are entity-name failures. The registry-check requirement (verify researcher identities via ORCID, verify journal venues via the publisher's catalog) would have caught them.

### Lessons for newsroom editors and fact-checkers

1. The "oaicite" marker is a free signal. Any document containing the marker has presumptively been touched by LLM citation generation. A grep-style check on the document before publication catches this.
2. Federal commission reports do not undergo external peer review. The internal editorial review is the only verification step. When the internal review does not perform per-citation checks, the publication is the verification.
3. Trust in government health communications is the resource at risk. The MAHA Report's fabrications damaged the report's evidentiary weight regardless of the underlying policy substance. The verification protocol exists because the consequences of skipping it are not bounded by the size of the editorial error.
4. The "correction" pattern (remove the surfaced fabrications, leave the rest) is not sufficient. A document with seven surfaced fabrications has presumably uncounted unsurfaced fabrications.

### Sources

- Washington Post, "White House MAHA report may have garbled science by using AI, experts say," 2025-05-29 [verified 2026-05-18].
- Washington Post, "The evidence of AI in the White House's MAHA report," 2025-05-30 [verified 2026-05-18].
- PolitiFact, "Fake citations in MAHA report likely AI-generated," 2025-05-30 [verified 2026-05-18].
- Science (AAAS), "Trump officials downplay fake citations in high-profile report on children's health" [verified 2026-05-18].
- Wikipedia, "MAHA report" [verified 2026-05-18].
- 522 footnotes, 37 duplicate footnotes, at least 7 non-existent studies, "oaicite" marker presence [verified 2026-05-18].

---

## 12. Megalopolis trailer fabricated critic quotes

**Date.** Trailer released and recalled August 22, 2024.
**Venue.** Lionsgate; trailer for Francis Ford Coppola's film "Megalopolis."
**Domain.** Marketing (theatrical film trailer).

### What happened

Lionsgate released a trailer for Coppola's "Megalopolis." The trailer used a rhetorical strategy of citing real critics' historical negative reviews of Coppola's prior work to position the film as a misunderstood masterpiece. The trailer included quotes attributed to Andrew Sarris (The Village Voice), Pauline Kael (The New Yorker), Vincent Canby, Roger Ebert, and other named critics. The quotes were attached to specific Coppola films (The Godfather, Apocalypse Now, Dracula). None of the cited quotes appeared in the named critics' actual reviews of those films. The Roger Ebert quote ("a triumph of style over substance") was a real Ebert quote, but it was from his 1989 review of "Batman," not from his review of "Dracula" as the trailer indicated.

Variety prompted ChatGPT with the same setup (request negative quotes about Coppola's prior films from named critics) and received responses strikingly similar to the trailer's quotes. The trailer's marketing consultant had used ChatGPT to compile the critic quotes and did not verify them. Lionsgate fired the marketing consultant responsible and issued an apology: "We offer our sincere apologies to the critics involved and to Francis Ford Coppola and American Zoetrope for this inexcusable error in our vetting process."

### What specifically failed in fact-checking

Marketing-consultant level: the consultant accepted ChatGPT's output as fact and inserted it into a high-visibility trailer.

Studio level: Lionsgate's review process did not verify the cited critic quotes against the named publications. A 30-second verification step per quote (open The New Yorker archive, search for the cited Pauline Kael review of The Godfather, locate the quote) would have surfaced every fabrication. None of the cited critics is alive (Kael died in 2001, Sarris in 2012, Canby in 2000, Ebert in 2013); the quotes could not be verified through a current contact with the critic, but the archival verification is straightforward.

### Which v2.0 protocol would have caught it

- **C1-COMPOSITE-001 (composite quotes).** The quotes have the structural shape of composite or fabricated quotes: plausible critic, plausible publication, plausible tone for the named film. The per-clause source verification would have surfaced the absence of each quote in the cited review.
- **C1-PARAPH-001 (paraphrase boundary drift).** The Roger Ebert quote was a real quote misattributed to a different film. This is the bidirectional paraphrase-boundary failure: real verbatim text with a fabricated attribution.
- **4e (misattributing quotes or examples)** per v2.0 refresh. The Ebert quote is the canonical misattribution case: a real quote, real speaker, real publication, wrong source film.
- **4f residual pure-fabrication.** The other quotes (Kael, Sarris, Canby) are pure-fabrication cases.

### Lessons for newsroom editors and fact-checkers

1. Marketing copy is editorial copy. The verification standard for a trailer's critic quotes is the same as the standard for a newspaper's critic quotes. The lower verification standard for marketing copy is institutional habit, not editorial rule.
2. Verifying a critic quote is a 30-second task per quote (open the named publication's archive, search the quote, confirm the review). The verification step is not optional, and the cost of skipping it is reputational. Coppola, the named critics' estates, the publications, and Lionsgate all carry reputational cost from the trailer.
3. Citing dead critics from past reviews of past films is a frictionless way to compose plausible-but-fabricated quotes. The "dead authors cannot be reached for comment" pattern is not a verification shortcut; it is a flag for heightened scrutiny.
4. The marketing consultant's use of ChatGPT to produce historical critic commentary is the same use-pattern as the Springer Mastering ML author's use of ChatGPT for academic references (incident 6) and the Mata attorney's use of ChatGPT for case citations (incident 1). The pattern recurs across domains because the affordance is the same: ask the model for plausible historical commentary, accept the output as fact.

### Sources

- Variety, "'Megalopolis' Trailer Pulled Due to Fake Critic Quotes: 'We Screwed Up'": https://variety.com/2024/film/news/lionsgate-pulls-megalopolis-trailer-offline-fake-critic-quotes-1236114337/ [verified 2026-05-18].
- Variety, "'Megalopolis' Trailer Seemingly Fabricates Quotes From Movie Critics" [verified 2026-05-18].
- Variety, "'Megalopolis' Trailer's Fake Critic Quotes Were AI-Generated" [verified 2026-05-18].
- The Hollywood Reporter, "Lionsgate Pulls 'Megalopolis' Trailer Featuring Fake Movie Critic Quotes" [verified 2026-05-18].
- CNN, "'Megalopolis' trailer pulled following fake critic quotes," 2024-08-22 [verified 2026-05-18].
- Roger Ebert "Batman" 1989 review provenance for the misattributed quote [verified 2026-05-18 via Variety reporting].

---

## 13. Washington Post "Your Personal Podcast" AI-generated scripts

**Date.** Launched December 10, 2025; press coverage of internal failures from Semafor and others December 2025 onward.
**Venue.** Washington Post.
**Domain.** News product (AI-generated audio).

### What happened

The Washington Post launched "Your Personal Podcast," a feature that used AI to generate personalized audio summaries from Post articles for subscribers. Internal pre-launch testing showed that between 68 percent and 84 percent of generated scripts failed an internal quality metric. The Post's product review team recommended moving forward with the release, with the framing that the team would "iterate through the remaining issues."

The post-launch reality surfaced through Semafor reporting in December 2025. The AI-generated scripts contained: fabricated quotes attributed to real public figures, misattributed quotes (real quotes assigned to the wrong source), invented commentary presented as the Post's editorial position, interpretation of sources' quotes as the Post's position, and pronunciation errors.

Internal reaction was substantial: leaders on the editorial side expressed alarm; some newsroom staff described the errors as "fireable offenses if made by a human journalist on staff." Karen Pensiero, the Post's head of standards, wrote that the mistakes had been "frustrating for all of us."

### What specifically failed in fact-checking

Pre-launch test failure: the internal quality metric failed at 68 to 84 percent rates. The remediation step (do not ship until the metric is acceptable) was not taken. The product-side decision to ship anyway is the upstream failure.

Production-side per-script failure: each script that fabricated a quote, misattributed a quote, or invented a position represents an unverified output that reached subscribers without per-item review.

The model used for script generation could be checked against per-family hallucination signatures, but the Post's published reporting does not specify which model family produced the failing outputs.

### Which v2.0 protocol would have caught it

- **C1-NESTED-001 (nested attribution flattening).** The "interpreting a source's quotes as the Post's position" failure is the canonical nested-attribution collapse: the source said X, the Post reported the source said X, the AI summarized "the Post said X." The per-speaker verification in C1-NESTED-001 would have surfaced the collapse.
- **C1-PARAPH-001 (paraphrase boundary drift).** Fabricated quotes attributed to real public figures are paraphrase-to-quote drift with fabricated content. Bidirectional audit would have surfaced quoted text not in the source.
- **C1-COMPOSITE-001 (composite quotes).** Some of the misattributed quotes are likely composite-quote failures: real fragments from disparate parts of the article (or from multiple articles) stitched into single utterances. The per-clause verification would have decomposed them.
- **4e (misattributing quotes or examples)** per v2.0 refresh. Real quotes assigned to the wrong source is the canonical misattribution failure. Cross-reference to C1-NESTED-001 and C1-COMPOSITE-001 protocols.

### Lessons for newsroom editors and fact-checkers

1. Internal quality-metric failure at 68 to 84 percent rates is not a launch signal. The product-side framing of "iterate through the remaining issues" is a costume framing for shipping unverified output. The metric was not telling the team to ship; it was telling the team not to ship.
2. AI-generated audio is editorial output. The verification standard is the editorial standard. The technical-product-team framing of "iterate" should not override the editorial-side standard of "verify before publish."
3. Misattribution of quotes to real public figures carries legal exposure (defamation, false-light invasion of privacy). The verification floor is not editorial preference; it is legal requirement.
4. The Post's standards-side framing ("frustrating for all of us") understates the institutional stakes. A standards-side reaction proportional to the failure would have included a product pause, not a continued ship.

### Sources

- Semafor, "'Iterate through': Why The Washington Post launched an error-ridden AI product," 2025-12-14 [verified 2026-05-18].
- Semafor, "Washington Post's AI-generated podcasts rife with errors, fictional quotes," 2025-12-11 [verified 2026-05-18].
- Editor and Publisher, "Washington Post's AI-generated podcasts rife with errors, fictional quotes" [verified 2026-05-18].
- The Media Copilot, "Washington Post AI Podcast Launch Failed Quality Tests" [verified 2026-05-18].
- Futurism, "The Washington Post Deployed Its Disastrous AI-Generated Podcasts Even After Internal Tests Showed It Was Failing Miserably" [verified 2026-05-18].
- 68 to 84 percent script failure rate in pre-launch testing [verified 2026-05-18].

---

## 14. Nieman Lab synthetic-byline cases (Margaux Blanchard, Victoria Goldiee)

**Date.** Blanchard byline contamination publicized 2025; Goldiee byline contamination publicized early 2026; Reuters Institute and Nieman Lab analytical coverage February 2026.
**Venue.** Multiple publications affected, including Wired, Business Insider, Architectural Digest, the Journal of the Law Society of Scotland, and others. Coverage compiled by Nieman Lab and the Reuters Institute.
**Domain.** News bylines (synthetic-byline contamination).

### What happened

Two coordinated patterns of synthetic-byline contamination reached major English-language publications.

First: "Margaux Blanchard." Articles bylined "Margaux Blanchard" were published in Wired (a feature on couples getting married in the Minecraft game), Business Insider (first-person essays), and other outlets in 2025. The articles were AI-generated; "Margaux Blanchard" was a synthetic identity. Wired and Business Insider removed the articles after the contamination surfaced.

Second: "Victoria Goldiee." After the Blanchard pattern, another synthetic-byline freelancer pitched and published under "Victoria Goldiee" at outlets including Architectural Digest and the Journal of the Law Society of Scotland. Nicholas Hune-Brown of The Local in Toronto discovered the contamination when a Goldiee pitch arrived too polished and the claimed groundwork could not be verified. Hune-Brown traced Goldiee's articles and found that quotes attributed to real experts were not remembered by those experts, and other "experts" cited in Goldiee's articles did not appear to exist.

Both patterns combine three failures: a synthetic identity (no human freelancer behind the byline), AI-generated copy, and fabricated source quotes within the AI-generated copy.

### What specifically failed in fact-checking

Editorial intake level: the assigning editor accepted a pitch from a "freelancer" whose identity could not be verified through standard journalistic channels (LinkedIn, prior bylines, mutual contacts, in-person meeting). The editorial intake assumed the byline corresponded to a real person.

Editorial production level: the editor accepted the submitted article without an annotated-draft check (requesting the writer's notes, interview audio, or source materials). The production process treated the article as a freelance submission rather than as an unverified AI-generated artifact.

Source-verification level: the named experts cited in the AI-generated articles were not contacted by the assigning publication. A 5-minute follow-up call to each cited expert would have surfaced the fabrications. The publication's freelance workflow did not include the call.

### Which v2.0 protocol would have caught it

- **C1-SYNTH-001 (AI-generated synthetic sources).** "Margaux Blanchard" and "Victoria Goldiee" are themselves AI-generated synthetic sources at the byline level. The trace-back procedure (verify the author's basic provenance: prior bylines, institutional affiliation, LinkedIn or other professional registry) would have surfaced the synthetic identities.
- **C1-COMPOSITE-001 (composite quotes).** The fabricated quotes within Goldiee's articles include both fully fabricated quotes and composite quotes constructed from real experts' actual statements. The per-clause verification would have surfaced both.
- **4d (incorrect organization or entity names)** per v2.0 refresh. The synthetic-byline pattern is the entity-level analog of the synthetic-source pattern: the byline is the entity, and it is fabricated.

### Lessons for newsroom editors and fact-checkers

1. Freelance-intake workflows assume the byline corresponds to a real person. The assumption is no longer cost-free. Verification of the freelancer's identity via standard journalistic channels (LinkedIn check, prior bylines, mutual contacts, video call) is now mandatory.
2. The Local in Toronto's response (require annotated drafts as evidence of the writing process) is the right shape. The annotated draft is a verification artifact that AI-generated copy cannot easily produce.
3. Each cited expert should be contacted by the assigning publication independently of the writer's correspondence. The 5-minute follow-up call is cheap and catches the synthetic-source failure at the latest possible point in the workflow.
4. The Blanchard and Goldiee patterns are presumed to recur. The "every media era gets the fabulists it deserves" framing (Nieman Lab, November 2025) is the long-form analysis; the operational lesson is to add identity verification and source verification to the freelance intake.

### Sources

- Nieman Lab, "How AI is transforming freelance journalism," 2026-02 [verified 2026-05-18].
- Nieman Lab, "'Every media era gets the fabulists it deserves,'" 2025-11 [verified 2026-05-18].
- Reuters Institute, "Speed, hoaxes and mistrust: How AI is transforming freelance journalism" [verified 2026-05-18].
- The Local (Toronto) editorial response, via Nieman Lab and Reuters Institute reporting [verified 2026-05-18].
- "Margaux Blanchard" byline at Wired and Business Insider [verified 2026-05-18 via Nieman Lab coverage].
- "Victoria Goldiee" byline at Architectural Digest and Journal of the Law Society of Scotland [verified 2026-05-18 via Nieman Lab and Reuters Institute coverage].

---

## 15. Google AI Overviews year bug

**Date.** Surfaced late May 2025; fixed May 29, 2025.
**Venue.** Google Search "AI Overviews" feature.
**Domain.** Search product (consumer-facing AI summary).

### What happened

In late May 2025, Google's AI Overviews feature responded to queries about the current year with the incorrect answer "2024." For a query "is it 2025," the AI Overview replied: "No, it is not 2025. The current year is 2024, as of today, May 27, 2024." The error appeared at scale across multiple users and was documented in screenshots posted to r/google and other forums.

Google fixed the bug late on May 29, 2025. The product subsequently returned the correct year.

The incident is not a citation fabrication. It is a temporal-drift failure: the model's training-cutoff knowledge produced a present-tense response anchored to a past date. The mechanism is the v1.1.0 SKILL section 4g failure mode (outdated or superseded data) operating in a high-visibility consumer product.

### What specifically failed in fact-checking

There was no per-query fact-checking; AI Overviews is a real-time generated response and does not include a verification step. The failure is in the model architecture, not in the editorial workflow.

But the broader product-level failure is: a consumer-facing AI product was shipped with no validation that present-tense temporal claims align with current calendar time. The validation gap is the product gap.

### Which v2.0 protocol would have caught it

- **4g (outdated or superseded data, refreshed as "wrong context for correct facts" per C2-4G-001).** The 2024 claim is a temporal-drift failure: the model's training cutoff produced a temporally incorrect present-tense claim. The freshness ceiling per claim type (Claude exec's contribution: regulatory 30 days, exec roles 60 days, court rulings until docket event, deployed AI products 90 days, current date 1 day) would have flagged any present-tense temporal claim from a model with a training cutoff for verification.
- **C1-TOOLHALL-001 (tool-specific hallucination patterns).** Gemini family has documented temporal-drift behavior under the "knowledge cutoff recency illusion" framing (DeepSeek contribution to v2.0). The per-family priority check for Gemini deep-research mode includes flagging every vague attribution and every present-tense temporal claim.

### Lessons for newsroom editors and fact-checkers

1. The temporal-drift pattern is not exotic. Any model with a training cutoff will produce wrong present-tense temporal claims unless retrieval-augmented or explicitly told the current date.
2. Newsroom AI tools that summarize current events should include a current-date check before publication. The check is cheap (current date == today?).
3. The Google AI Overviews 2024 response is the canonical 4g example for v2.0. It demonstrates the "knowledge cutoff recency illusion" at scale: the model presents stale data as current without flagging the temporal gap.
4. The product-team decision to ship without a current-date validation is the upstream failure. Product teams shipping AI summaries of current events should include validation for present-tense temporal claims as a baseline requirement.

### Sources

- TechCrunch, "Google fixes bug that led AI Overviews to say it's now 2024," 2025-05-30 [verified 2026-05-18].
- Android Authority, "Google fixes AI Overview bug that didn't know what year it is" [verified 2026-05-18].
- Android Authority, "Google Search's AI Overview cannot correctly tell you if it's 2025" [verified 2026-05-18].
- Republic World, "'No, It Is Not 2025': Google's New AI Search Feature Gets Basic Facts Wrong" [verified 2026-05-18].
- TopMostAds, "Google AI Overviews bug 2025: Analysis & Impact" [verified 2026-05-18].
- Fix date May 29, 2025 [verified 2026-05-18]. Bug surface date late May 2025 [verified 2026-05-18].

---

## Cross-cutting patterns across the incident archive

After cataloging the 15 incidents, several patterns are visible in the archive considered as a whole. These patterns reinforce the structural changes in v2.0.

### Pattern: the same user-pattern recurs across domains

The Mata attorney (legal), the Mostafavi attorney (legal), the Goldberg Segalla attorney (legal), the Buscaglia freelancer (journalism), the Madhavan author (academic publishing), the Megalopolis marketing consultant (marketing), and the MAHA Report writers (government) all used the same affordance: ask an LLM for plausible historical or domain-specific content, accept the output, insert it into a document, and skip the verification step. The verification step is what separates each domain's professional standard from each domain's failure. The skip pattern is identical across domains. v2.0's per-family hallucination signatures (C1-TOOLHALL-001) and the demoted 4f (split into the C1-URLROT-001 / C1-SYNTH-001 / C1-LAUNDER-001 trio) target this pattern.

### Pattern: graph independence vs. raw count

Mostafavi's verification design (four LLMs cross-checking) is the canonical failure of raw-count multi-source confidence. v2.0 makes graph independence the condition. The Mata attorney's "ask ChatGPT to confirm the cases ChatGPT produced" is the degenerate case of the same failure: zero-source corroboration. The Springer Mastering ML book becomes a single-upstream synthetic source that downstream papers will laundering-chain to. C1-LAUNDER-001 names the pattern; the archive establishes the prevalence.

### Pattern: cost asymmetry

The verification cost in every entry is bounded: a 30-second Westlaw search, a 5-minute Google Scholar query, a 5-minute call to a cited expert, a grep for "oaicite" in a document, a Wayback Machine lookup. The failure cost is unbounded: sanctions, retracted books, recalled trailers, subscriber-trust loss, federal-report credibility damage, defamation exposure. The cost-asymmetry argument for verification is one-sided. The fact that the verification step is skipped at scale across the archive entries means the cost asymmetry is not the operating constraint. Habit, workflow design, and institutional incentives are.

### Pattern: institutional review does not substitute for editorial review

Springer's editorial review did not catch the Madhavan citations. The ICLR review process caught the BrainMIND placeholders but only after the manuscript reached the review queue. The Washington Post's product review team recommended shipping the AI podcast despite the 68 to 84 percent test-failure rate. The MAHA Commission's signatures did not constitute citation review. The pattern is: institutional review is not the verification step. Verification is the verification step. The institutional review presupposes that verification has happened.

### Pattern: the per-family hallucination signature is real

Mostafavi's case (4 LLMs cross-checking), the MAHA Report ("oaicite" marker in 37+ footnotes), the Megalopolis trailer (ChatGPT-style critic-quote production), and the Stanford RegLab measurements (per-product hallucination rate differences) all evidence per-family hallucination signatures. The C1-TOOLHALL-001 section in v2.0 names the signatures; the archive establishes the empirical basis.

---

## Verification status summary

| Incident | Year | Core facts | Cornerstone verification |
|---|---|---|---|
| 1 Mata v. Avianca | 2023 | [verified 2026-05-18] | $5,000 sanction, S.D.N.Y., Castel, Justia case record |
| 2 Mostafavi sanction | 2025 | [verified 2026-05-18] | $10,000 sanction, California 2nd District Court of Appeal Division Three, 21 of 23 fabricated quotes |
| 3 Goldberg Segalla / CHA | 2025 | [verified 2026-05-18] | $59,500 total sanction ($10,000 + $49,500), Cook County, December 9, 2025 |
| 4 Charlotin database | 2024 to 2026 | [verified 2026-05-18] | 1,455 cases, Charlotin at HEC, public database online |
| 5 Chicago Sun-Times | 2025 | [verified 2026-05-18] | Heat Index supplement, May 18 2025, 10 of 15 fabricated, Buscaglia / King Features Syndicate |
| 6 Springer Mastering ML | 2025 | [verified 2026-05-18] | Madhavan, April 2025 publication, $169 ebook, 2/3 of 18 sampled citations fabricated, August 2025 retraction |
| 7 BBC/EBU report | 2025 | [verified 2026-05-18] | October 21 2025 release, 22 PSMs, 18 countries, 14 languages, 3,000+ responses, 45 percent significant-issue rate |
| 8 Topaz Lancet letter | 2026 | [verified 2026-05-18] | Topaz at Columbia, Lancet letter May 7 2026, 2.5M papers audited, 1 in 277 in 2026, 12-fold rise from 2023 |
| 9 Stanford RegLab Magesh | 2024 | [verified 2026-05-18] | Magesh, Surani, Dahl, Suzgun, Manning, Ho, Stanford RegLab preprint May 2024, JELS 2025, 17 to 33 percent rates, 202 queries |
| 10 Tsinghua BrainMIND ICLR | 2025 | [partially verified] | The Decoder reporting confirms the pattern; specific ICLR submission docket not confirmed in consulted reporting |
| 11 MAHA Report | 2025 | [verified 2026-05-18] | 522 footnotes, 37 "oaicite" markers, 7+ non-existent studies, NOTUS and WaPo May 2025 reporting |
| 12 Megalopolis trailer | 2024 | [verified 2026-05-18] | August 22 2024 pull, fabricated Kael / Sarris / Canby quotes, real Ebert quote misattributed to Dracula (actually Batman 1989) |
| 13 WaPo AI podcast | 2025 to 2026 | [verified 2026-05-18] | December 10 2025 launch, 68 to 84 percent pre-launch failure rate, Semafor Dec 2025 reporting |
| 14 Nieman synthetic bylines | 2025 to 2026 | [verified 2026-05-18] | "Margaux Blanchard" 2025 Wired and Business Insider; "Victoria Goldiee" 2025 to 2026 Architectural Digest and others |
| 15 Google AI Overviews year | 2025 | [verified 2026-05-18] | Bug surfaced late May 2025, fix May 29 2025, "2024" present-tense response at scale |

Verification was performed via WebSearch and WebFetch on 2026-05-18. Where a primary publication's URL returned HTTP 403 on automated fetch (Lancet article, EBU report), verification was performed via secondary reporting from Retraction Watch, Nature, The Scientist, NPR, CBC, and The Register, all of which independently reported the cornerstone facts. The triangulation across multiple independent secondary sources establishes the verified status.

---

## How to use this archive in fact-checking workflows

This archive is a reference, not a checklist. Use it as:

1. **A training set for editorial workflows.** Each incident is a worked example of how a specific verification gap produces a publication failure. Editors training on the v2.0 SKILL should be able to identify which v2.0 protocol would have caught each incident.
2. **A cost-asymmetry argument.** When a writer or editor objects to a verification step as "too expensive," the relevant counterfactual is the incident in this archive where the same step was skipped. The asymmetry is one-sided in every documented case.
3. **A pattern-recognition aid.** The cross-cutting patterns section names the recurrences across domains. An editor reviewing AI-generated content should recognize the pattern shape, not just the surface symptom.
4. **An empirical anchor for the v2.0 structural changes.** The demotion of 4f as a single bucket (into the C1-URLROT-001 / C1-SYNTH-001 / C1-LAUNDER-001 trio plus residual pure-fabrication) is justified by the archive: incidents 1, 2, 3, 5, 6, 8, 10, 11 all involve fabricated citations, and the v2.0 trio better classifies them than 4f alone. Incidents 12, 13, 14 involve quotation and attribution failures that the C1-NESTED-001 / C1-PARAPH-001 / C1-COMPOSITE-001 protocols target. Incident 15 is the canonical 4g (refreshed 4g, "wrong context for correct facts") example. Incident 9 is the empirical anchor for C1-TOOLHALL-001.

---

## Cross-references

- **detailed-protocols.md:** C1-NESTED-001, C1-PARAPH-001, C1-COMPOSITE-001, C1-POSSHIFT-001, C1-TRANS-001, C1-URLROT-001, C1-SYNTH-001, C1-LAUNDER-001, C1-TOOLHALL-001. Each C1 ID is cited in the "Which v2.0 protocol would have caught it" section of the relevant incident.
- **detailed-criteria.md:** A3 patterns (refreshed 42 criteria from v3.1.0) are referenced where stylistic signals correlate with the incidents documented here, particularly the per-family hallucination signatures.
- **per-family-hallucination-signatures.md:** Detailed per-family fabrication signatures for Claude, GPT, Gemini, Llama, DeepSeek, Grok. The archive's per-incident "Which v2.0 protocol would have caught it" sections frequently cite C1-TOOLHALL-001; the family-specific detail lives in per-family-hallucination-signatures.md.
- **citation-laundering-detection.md:** Detailed graph-traversal protocol for C1-LAUNDER-001. The archive's incidents involving citation laundering (1, 2, 3, 5, 6, 8, 11) reference the detailed protocol.
- **bibliography.md:** Consolidated bibliography for synthesis-fact-checking v2.0.

---

## End of archive

This archive will grow as new incidents are documented. The 15 entries above are the v2.0 baseline. The archive is not a snapshot; it is the start of a compounding record.

Em-dash audit on this file: zero em-dashes self-audited via grep before saving.
