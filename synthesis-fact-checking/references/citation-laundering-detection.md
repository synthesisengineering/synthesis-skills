# Citation Laundering Detection: Graph-Traversal Protocol

**Part of:** synthesis-fact-checking v2.0
**Section reference:** C1-LAUNDER-001
**Status:** Active and accelerating (2026)
**Related protocols:** C1-SYNTH-001 (AI-generated synthetic sources), C1-URLROT-001 (URL rot vs. hallucination distinction)

This file specifies the concrete graph-traversal procedure that section 2 of the parent SKILL.md (Multi-Source Confidence Framework) depends on. v1.1.0 of synthesis-fact-checking established the principle that cross-corroboration among LLM outputs is not independent verification. It did not specify the trace-back procedure that turns the principle into operational practice. This file is that procedure.

---

## 1. The Problem

### 1.1 What citation laundering is

Citation laundering is the process by which an unverified or fabricated claim acquires the appearance of multi-source confirmation through a chain of mutually citing artifacts, even though every citation in the chain ultimately traces to a single non-authoritative upstream.

The shape is recursive. An AI system generates content containing a claim. That content is indexed by a search engine. A second AI system, searching for sources on the same topic, retrieves the first AI's content and cites it. A third AI system, performing research, retrieves and cites the second AI's output. By the third hop, the claim appears to have three independent corroborating sources. It has one. The other two are citations of citations.

The reader, the fact-checker, and the downstream AI all see a claim with three references attached to it. Multi-source confidence (the v1.1.0 heuristic that two or three corroborating sources increases confidence) was designed under the assumption of graph independence: that two sources citing the same claim mean two authors independently reached the same factual conclusion. Citation laundering violates that assumption. The corroboration is purely topological; the sources cite one another, not the underlying fact.

### 1.2 Why v1.1.0 needs revision

The v1.1.0 Multi-Source Confidence table reads count-as-confidence. Three sources is "very high" confidence; two sources is "high" confidence; one source is "moderate" confidence; conflicting sources is "low" confidence.

Every row of that table conditions on raw citation count. None of them conditions on graph independence. If three sources all trace to one upstream, the table prescribes "very high" confidence for what is, in graph-independence terms, a single-source claim.

The revision is structural, not cosmetic. The corrected framework requires counting the number of independent upstream nodes in the citation graph, not the number of citations in the draft.

### 1.3 What this protocol provides

A specific five-step procedure that takes a draft claim with N attached citations as input and returns:

- The citation graph for the claim (nodes, edges, terminal upstreams).
- The count of graph-independent upstreams.
- The upstream provenance classification for each terminal node.
- A graph-conditioned confidence rating that replaces the raw-count rating from v1.1.0 section 2.
- A remediation action: verified, re-source, hedge, or remove.

Worked examples in section 4 trace the procedure end-to-end. Section 6 specifies the revised v1.1.0 section 2 text suitable for citation from SKILL.md.

---

## 2. Why This Matters at 2026 Scale

### 2.1 The recursive contamination baseline

Two measurements set the scale of the problem.

First, Ahrefs measured that 74.2 percent of newly indexed English-language web pages in April 2025 contained AI-generated content. Spennemann (arxiv 2504.08755) documented 30 to 40 percent of active web pages showing AI signatures. The corpus that downstream AI systems treat as ground truth, and the corpus that human researchers treat as ground truth, are now substantially synthetic.

Second, the academic literature itself is contaminated. Topaz et al., in a May 2026 Lancet letter (specific venue flagged for verification during synthesis), found that one in 277 PubMed papers in 2026 referenced a fabricated paper. The same study reported a twelvefold rise in fabricated citation rates from 2023 (Claude exec framing; the Perplexity citation of the same study reports the comparison as a sixfold rise from 2023 to 2025, with the twelvefold figure incorporating 2026 data points). Either framing puts the trajectory in the same direction at the same order of magnitude: PubMed has become a laundering venue.

PubMed is a specifically severe case because it is treated as authoritative by downstream systems. An AI agent doing literature review tends to weight PubMed-indexed citations higher than blog posts or news articles. A fabricated paper laundered through PubMed acquires the prestige of the indexing venue without ever passing peer review at the underlying claim level. The 1-in-277 figure represents the floor of detected fabrications. Undetected laundering chains, where the upstream is real but the cited claim was not actually made by the upstream paper, would inflate this number further.

### 2.2 Implications for multi-source confidence

The v1.1.0 framework assumed that source agreement was a useful proxy for verification. Under contamination at 30 to 75 percent of the corpus, that proxy fails. The expected base rate of two AI-derived sources agreeing on a fabricated claim is now nontrivial. The expected base rate of three AI-derived sources agreeing on a fabricated claim is also nontrivial when laundering chains are active.

The shift is from "agreement-as-evidence" to "graph-independent-agreement-as-evidence." The corrected rule: confidence rises with the number of upstream nodes that are causally unrelated to one another, not with the count of citations a fact has accumulated.

### 2.3 The interaction with C1-SYNTH-001

Citation laundering chains and AI-generated synthetic sources (C1-SYNTH-001) compose. A synthetic source is the upstream root of a laundering chain. The chain is the propagation mechanism by which a single synthetic upstream contaminates downstream multi-source confidence assessments.

The protocols are distinct because the remediation is distinct. C1-SYNTH-001 remediation: detect the synthetic source, remove the citation, re-source. C1-LAUNDER-001 remediation: map the graph, identify the single upstream, treat the claim as single-sourced regardless of citation count, then apply C1-SYNTH-001 to the upstream if it is itself synthetic. Both protocols apply to chains where the upstream is synthetic; only C1-LAUNDER-001 applies to chains where the upstream is real but downstream sources have detached from it.

### 2.4 The interaction with C1-URLROT-001

URL rot (a previously valid URL no longer resolves) and hallucination (a URL never existed) are distinct failure modes per C1-URLROT-001. Laundering chains interact with both. A laundered citation may point to a URL that has rotted: the chain originally laundered a real (but weak) source; the source has since died; the chain still propagates the claim. A laundered citation may point to a URL that was always hallucinated: the chain laundered the fabrication itself.

Trace-back must classify each node in the chain by URL status. A laundering chain with a dead-but-once-real upstream is materially different from a laundering chain with a never-existed upstream, and the remediation differs.

---

## 3. Detection Protocol

The protocol has five steps. Each step has explicit inputs, outputs, and stopping conditions. The protocol applies to any draft claim with two or more citations, or to any claim whose author has expressed "multi-source confidence" reasoning.

### 3.1 Step 1: Build the citation graph

**Input:** A draft claim with N attached citations.

**Output:** A directed graph G where nodes are sources and edges represent "cites" relationships.

**Procedure:**

1. List every source cited in support of the claim. Label them S1, S2, ..., SN. These are the level-0 nodes.
2. For each level-0 node, retrieve the source. If the source has its own citations for the same claim, record them as level-1 nodes. Label them S1.1, S1.2, S2.1, etc. Edges go from level-0 to level-1.
3. Repeat at level 2: for each level-1 node, retrieve and identify its citations for the same claim. Record edges.
4. Continue until one of three terminal conditions is reached:
   - **Primary upstream:** the node is a primary document (peer-reviewed paper with DOI, government data release, original interview transcript, official statement, dataset). Mark it as PRIMARY.
   - **Dead end:** the node makes the claim with no further citation ("studies show," "research indicates," "experts say" with no specific document named). Mark it as DEAD-END.
   - **Cycle:** the node cites a previously visited node. Mark it as CYCLE and note the cycle members.
5. Record the graph structure: every node, every edge, every terminal classification, every URL status (live, dead, never-existed), every publication date.

**Practical tools:** Connected Papers (connectedpapers.com) for academic graph traversal, Semantic Scholar's citation graph API for programmatic access, OpenAlex for cross-disciplinary citation networks, ResearchRabbit for visualization of academic chains, Google Scholar's "cited by" feature for backwards traversal. For non-academic chains, use the Wayback Machine to retrieve historical versions of intermediate sources and identify their citations as they existed at publication time. The urlhealth tool (Rao et al. 2026) classifies URLs as LIVE, DEAD, LIKELY_HALLUCINATED, or UNKNOWN; apply this at every node to populate the URL status field.

**Common pitfall:** stopping at the level-0 nodes because they "look authoritative." The whole point of laundering is that level-0 nodes look authoritative. The graph must be expanded to terminal conditions, not to subjective authority.

### 3.2 Step 2: Identify the upstream

**Input:** The graph G from step 1.

**Output:** The set of terminal upstream nodes U = {U1, U2, ...}.

**Procedure:**

1. From the graph G, extract every node marked PRIMARY or DEAD-END (cycles are excluded because they do not terminate in a verifying source).
2. For each path from a level-0 node to a terminal, record the terminal. The set U is the union of all terminals reached from any level-0 path.
3. The size of U is the number of distinct upstreams in the chain.

**Common shapes:**

- **Single-upstream collapse:** all paths lead to one terminal. U = {U1}. This is the canonical laundering signature regardless of the level-0 citation count.
- **Multi-upstream fan-out:** different level-0 nodes lead to different terminals. U = {U1, U2, U3, ...}. This is the shape multi-source confidence was designed for.
- **Mixed:** some level-0 nodes collapse to one upstream; others reach a separate upstream. U is smaller than the level-0 count but larger than 1.

**Common pitfall:** treating two level-0 nodes that cite the same level-1 node as evidence of two different upstream perspectives. They are not. They are one upstream cited by two intermediaries.

### 3.3 Step 3: Check upstream provenance

**Input:** The terminal upstream set U from step 2.

**Output:** A provenance classification for each Ui in U.

**Procedure:** For each Ui, classify it into one of the following provenance categories.

| Category | Definition | Trust signal |
|----------|------------|--------------|
| **PEER-REVIEWED** | Paper with DOI in a journal with documented peer review and editorial board | Highest |
| **PRIMARY-DOCUMENT** | Government data release, official statement, original interview transcript, original dataset | Highest |
| **REPUTABLE-NEWS** | Reporting by news organization with documented editorial standards, named author, retraction policy | High |
| **TRADE-PUBLICATION** | Industry publication with named editorial team, but lower verification rigor than reputable news | Moderate |
| **PERSONAL-BLOG** | Named individual's blog, no editorial review, but identifiable author with traceable credentials | Low |
| **AI-CONTENT-FARM** | Site producing AI-generated content at volume, no editorial process, no traceable byline, AI markers in content | Very low (treat as not-a-source) |
| **USER-GENERATED-FORUM** | Reddit, Twitter, Stack Exchange, or similar; user posts without editorial review | Very low |
| **SYNTHETIC-CITATION** | Citation to a paper, expert, or institution that does not exist | Zero (not a source) |
| **DEAD-END** | Source makes the claim without citing further; the claim originates at this node by assertion | Depends on the asserting node's provenance category |

**Detection signals for AI-CONTENT-FARM upstream:**

- Domain registered within the past 18 months.
- No identifiable editorial team or contact information.
- High-volume publishing on niche topics with comprehensive coverage and uniform structure.
- Stylometric AI markers per synthesis-content-quality A1 patterns (saturated vocabulary, exhausted metaphors, conclusion-shaped paragraphs that do not conclude).
- No outgoing primary-document citations.
- Author bylines, if present, lead to LinkedIn pages with no traceable institutional affiliations.

**Detection signals for SYNTHETIC-CITATION upstream:**

- DOI returns 404 or resolves to a different paper than cited.
- Authors not findable on Google Scholar or institutional sites.
- Journal name plausible but not in CrossRef.
- Citation matches the Claude DOI-fabrication signature, GPT URL-fabrication signature, or family-specific hallucination patterns per C1-TOOLHALL-001.

**Common pitfall:** classifying a Wikipedia article or a news aggregator as the upstream. Wikipedia is almost never an upstream; it is an intermediate node. News aggregators that republish or summarize other reporting are intermediate nodes. Trace until the claim originates, not until the citation looks credible.

### 3.4 Step 4: Apply graph independence check

**Input:** The terminal upstream set U with provenance classifications.

**Output:** A graph-independence count GI = |U_valid|, where U_valid is the subset of U with provenance category PEER-REVIEWED, PRIMARY-DOCUMENT, or REPUTABLE-NEWS.

**Procedure:**

1. Drop from U any node classified as SYNTHETIC-CITATION (it is not a source).
2. Drop from U any node classified as AI-CONTENT-FARM (it is not a source for fact-checking purposes).
3. Drop from U any DEAD-END node whose asserting node was itself classified low (PERSONAL-BLOG, AI-CONTENT-FARM, USER-GENERATED-FORUM, DEAD-END recursively).
4. Count the remaining nodes. This is GI, the graph-independent upstream count.

**Common pitfall:** counting a chain that has three level-0 citations but all collapse to one PEER-REVIEWED upstream as GI=3. The level-0 count is irrelevant. GI=1 in that case.

**Cycle handling:** if the graph contains a cycle (A cites B, B cites A; or A cites B cites C cites A), the cycle does not contribute an upstream. Cycles are evidence of laundering by definition: no node in a cycle terminates in a verifying source.

### 3.5 Step 5: Score the claim's true source count

**Input:** GI from step 4.

**Output:** A confidence rating that replaces the v1.1.0 raw-count rating, plus a remediation action.

**Procedure:** Apply the revised confidence table from section 6 below. Briefly, the table reads:

- GI=0: claim is unverifiable. Remediation: remove the claim or hedge to opinion-marked language with no factual claim attached.
- GI=1: claim is single-sourced regardless of level-0 citation count. Apply standard primary-source verification per v1.1.0 section 3. If the single upstream is PEER-REVIEWED or PRIMARY-DOCUMENT, the claim is verifiable but should not be presented as multi-source corroborated.
- GI=2: claim has true two-source corroboration. Apply v1.1.0 "high confidence" verification.
- GI=3 or higher: claim has true multi-source corroboration. Apply v1.1.0 "very high confidence" verification.

**Document everything.** The graph, the upstream classifications, GI, the confidence rating, and the remediation action all go into the review-log.md per the SKILL.md template. Future readers (you in three months; another AI agent; another writer) need to see the graph to trust the assessment. Citation-laundering remediation is not auditable without the underlying graph.

---

## 4. Worked Examples

### 4.1 The "31% drop in problem-solving" case

The canonical example per Claude exec 2026-05-18.

**The claim as it appeared in a draft article:** "Recent research shows a 31 percent drop in problem-solving performance among knowledge workers using LLM tools."

**Citations attached to the claim:** Three sources, all from late 2025 or early 2026, each described as supporting the 31 percent figure.

**Step 1 graph traversal:**

- S1 (level-0): A news article on a productivity-focused publication, dated November 2025.
- S2 (level-0): A LinkedIn long-form post by an executive, dated December 2025.
- S3 (level-0): A blog post on a research aggregator, dated January 2026.

Retrieving S1: the news article cites "a study by researchers at a major university" but provides no specific paper title, author names, or DOI. S1's only citation for the 31 percent figure is "an arXiv preprint by [generic author names]."

Retrieving S2: the LinkedIn post cites S1 explicitly. It does not cite the arXiv preprint directly.

Retrieving S3: the research aggregator blog post cites S1 and S2. It does not cite the arXiv preprint directly.

Following S1's reference: the arXiv preprint is locatable. The authors have no ORCID identifiers, no institutional affiliations on the preprint's metadata, and no other papers indexed in Google Scholar. The preprint claims a 31 percent drop based on a self-reported survey of 47 participants, with no preregistration, no peer review, and no methods section detailing the problem-solving instrument used.

**Step 2 upstream identification:** All three level-0 paths converge on the arXiv preprint. U = {U1: arXiv preprint by non-ORCID authors}.

**Step 3 provenance classification:** The arXiv preprint is technically locatable, so it is not SYNTHETIC-CITATION in the URL sense. But: no institutional affiliations, no peer review, no ORCIDs, no preregistration, no methods detail, no replication. The preprint is PERSONAL-BLOG-equivalent in provenance terms. Possibly AI-CONTENT-FARM if the authors are themselves synthetic.

**Step 4 independence check:** GI = 0 if the preprint is classified PERSONAL-BLOG (low-trust upstream); GI = 1 if treated charitably as a preprint with weak provenance. Either way, the draft's three level-0 citations represent at most a single upstream of weak provenance, not three independent sources.

**Step 5 scoring and remediation:** The claim is unverifiable as stated. Remediation: remove the 31 percent specific figure; do not claim "research shows" without naming a verifiable study; if the underlying intuition (LLM tools may impair certain problem-solving) is worth preserving, source it from a different study with verifiable provenance or explicitly hedge it.

**Lesson:** Three news outlets independently writing about a topic looks like multi-source corroboration. When all three cite each other or one common preprint, GI=1. The publication dates of S1, S2, S3 (Nov 2025, Dec 2025, Jan 2026) are also a tell: a true multi-source claim usually accumulates citations over a longer window from authors not in conversation with each other. A two-month cluster around a single preprint is a signature of laundering, not corroboration.

### 4.2 The PubMed laundering case (Topaz et al. May 2026 Lancet letter)

**The finding:** Topaz et al., in a Lancet letter dated May 2026 (specific venue flagged for verification during the synthesis pass), reported that 1 in 277 PubMed papers in 2026 referenced a fabricated paper. The rate represented a twelvefold rise from 2023 in the Claude exec framing of the study (Perplexity's framing of the same study reports a sixfold rise from 2023 to 2025; both formulations appear in the source literature, with the twelvefold figure incorporating the 2026 data points).

**The laundering mechanism (as reconstructed from the Topaz et al. analysis):**

- A researcher or research-assistant AI generates a literature review draft. The draft includes citations to studies that do not exist.
- The draft is published as a preprint or, with insufficient review, in a journal that is itself PubMed-indexed.
- The fabricated citation now exists in PubMed.
- Downstream researchers searching PubMed for related work retrieve the laundering paper. Some of them cite the fabricated paper from the laundering paper without independently verifying that the fabricated paper exists. The fabricated paper now has citation count > 0.
- AI literature-review tools, retrieving from PubMed, treat the fabricated paper as authoritative because PubMed-indexed papers are trusted as a class. The tools generate further reviews citing the fabricated paper.
- The fabricated paper's citation count compounds. By 2026, 1 in 277 indexed papers participates in such a chain.

**Detection in practice:**

When fact-checking a medical or scientific claim with PubMed-indexed citations, do not treat PubMed presence as verification. Apply the full graph traversal:

- Retrieve the cited paper directly (not just the abstract from a database).
- Verify the paper's own citations are real (especially for review papers and meta-analyses, which by their nature aggregate other citations).
- Verify the paper's authors have other indexed work, ORCIDs, and traceable institutional affiliations.
- Verify the journal is in a recognized indexer (Scopus, Web of Science) with documented peer review.
- If the paper is a review citing the claim of interest, follow the review's citation to the original empirical paper and verify that paper directly.

**Cross-reference to C1-SYNTH-001:** The fabricated paper that originates the chain is a SYNTHETIC-CITATION upstream. The laundering protocol detects the chain shape; the synthetic-sources protocol classifies the upstream. Both are needed; applying only one misses the other half of the failure mode.

### 4.3 The Wikipedia-news-AI-farm invented example

A worked example showing how a chain that appears to cross publication categories can still collapse to one upstream.

**The claim as it appeared in a draft article:** "An estimated 42 percent of small businesses adopted AI tools in 2025."

**Citations attached to the claim:**

- S1: A Wikipedia article on AI adoption with the 42 percent figure cited inline.
- S2: A news article from a technology publication, dated mid-2025, also citing the 42 percent figure.

The draft writer reasons: Wikipedia plus a major news outlet is two independent sources. Multi-source confidence is satisfied. Confidence is high.

**Step 1 graph traversal:**

- S1 (Wikipedia article): the inline citation for the 42 percent figure points to a footnote. The footnote cites a research report URL from a domain the writer does not recognize.
- S2 (news article): the article's text says "according to a 2025 report, 42 percent of small businesses ...". The hyperlink in the article points to the same research report URL as the Wikipedia footnote.

Following the research report URL: the domain was registered eight months ago. The site publishes "research reports" on AI adoption, supply chain efficiency, marketing trends, and other unrelated topics at a rate of three to four reports per week. No editorial team is named on the About page. Reports do not list methodology, sample size, response rate, or survey instrument. The site uses uniformly templated structure across reports.

The 42 percent figure appears in a report titled "AI in Small Business: 2025 Adoption Trends" published by this site. The report cites "industry surveys" without naming any.

**Step 2 upstream identification:** Both level-0 paths converge on this single research-report site. U = {U1: the research-report domain}.

**Step 3 provenance classification:** The research-report site presents AI-CONTENT-FARM markers (domain age, volume, no editorial team, no methodology, uniform structure across unrelated topics, no traceable bylines). Classification: AI-CONTENT-FARM.

**Step 4 independence check:** GI = 0. The Wikipedia article and the news article do not constitute two sources; they both forward the same content-farm claim.

**Step 5 scoring and remediation:** Remove the 42 percent figure. The claim is unverifiable. If the underlying point (adoption is rising among small businesses) is worth preserving, source it from a different study with traceable methodology, or rewrite as a hedged general observation that does not depend on a specific number.

**Lesson:** Surface-level credibility (Wikipedia + technology news outlet) is not graph independence. Both intermediate nodes can be doing the same thing: trusting and forwarding a single low-provenance upstream. The graph traversal is the only reliable way to detect this; visual inspection of citation surface ("two named sources, looks fine") will miss it every time.

### 4.4 The peer-reviewed-but-stale-citation case

A worked example showing that not every laundering chain ends in fabrication; some end in real but non-supporting upstreams.

**The claim as it appeared in a draft article:** "A Nature review confirms that the drug shows efficacy in 73 percent of cases."

**Citations attached to the claim:** One source: a Nature review article from 2025.

**Step 1 graph traversal:**

- S1 (Nature review): the review discusses the drug's efficacy in a section that cites "Smith et al. 2012" for the 73 percent figure.

Following Smith et al. 2012: the original 2012 paper is a pilot study with 11 participants, of whom 8 (73 percent) showed response on a non-validated outcome instrument. The paper itself notes that "these preliminary findings require confirmation in a larger trial."

A 2018 follow-up trial by a different group (n = 412) found 31 percent efficacy on a validated outcome instrument.

The 2025 Nature review cites Smith et al. 2012 for the 73 percent figure without mentioning the 2018 follow-up.

**Step 2 upstream identification:** U = {U1: Smith et al. 2012 pilot}.

**Step 3 provenance classification:** Smith et al. 2012 is PEER-REVIEWED but the citation is misused. The Nature review treats the pilot's 73 percent as a confirmed efficacy rate; the underlying paper does not support that framing.

**Step 4 independence check:** GI = 1, but the upstream does not support the claim as stated.

**Step 5 scoring and remediation:** The citation is laundered through the Nature review's misframing. Remediation: trace through the review to the underlying primary, find that the primary contradicts the framing, correct the claim. The correct framing might be "an early pilot reported 73 percent efficacy in a small sample, but later trials found 31 percent in larger validated samples." Or, simpler: remove the laundered citation and use the more recent trial.

**Lesson:** Laundering is not always about fabrication. Sometimes the upstream is real, the citation is real, but the chain has detached the framing from the original methodology. Section 5 of the SKILL.md (Quote Verification Protocol) and section 6 (Study Verification Protocol) handle the corrective step once the graph identifies that the chain terminates in a real-but-misrepresented upstream.

### 4.5 The cycle case

A worked example showing a true graph cycle, where no terminal upstream is reached.

**The claim:** "Experts estimate $2 billion in damages from AI-related errors in 2025."

**Citations attached:** Three sources, all blogs or research aggregators.

**Step 1 graph traversal:**

- S1 (research aggregator blog): cites the $2 billion figure with a link to S2.
- S2 (technology blog): cites the $2 billion figure with a link to S3.
- S3 (industry newsletter): cites the $2 billion figure with a link to S1.

The three sources form a cycle: A cites B cites C cites A. No node provides a primary upstream.

**Step 2 upstream identification:** U = {} (empty set; the cycle does not terminate).

**Step 3 provenance classification:** N/A; no upstream to classify.

**Step 4 independence check:** GI = 0.

**Step 5 scoring and remediation:** The claim is unverifiable. The cycle is itself definitive evidence of laundering: three sources cite each other circularly, with no node bearing the original assertion. Remove the claim.

**Lesson:** Cycles are an unambiguous laundering signature. When the trace-back returns to a previously visited node without ever reaching a terminal, the cycle is the conclusion. No further work is needed to confirm laundering; the graph topology has done it. Note that cycles in academic citation graphs (mutual citations among coauthors over time) are different from cycles in fact-laundering graphs; the discriminator is whether any node carries the original empirical assertion. If no node does, the cycle is a laundering cycle.

---

## 5. Tools and Aids

The graph traversal is feasible by hand for short chains. For longer chains, tooling reduces the time cost. None of the following tools fully automates the protocol; all of them assist specific steps.

### 5.1 Academic citation graph tools

- **Connected Papers** (connectedpapers.com). Builds a visual graph of papers related to a seed paper through citation, co-citation, and bibliographic coupling. Useful for identifying whether a cited paper sits in a well-connected scientific cluster or is isolated. An isolated paper in a graph dense with established work is a candidate SYNTHETIC-CITATION upstream.

- **Semantic Scholar** (semanticscholar.org). API access to the Open Research Corpus. Supports forward citation traversal (papers citing X) and backward traversal (papers cited by X). Provides influence and citation count metrics. The S2 API is the most programmatically tractable for batch graph construction.

- **OpenAlex** (openalex.org). Cross-disciplinary citation network. Supports filtering by venue, by author, by institution. Useful for verifying author institutional affiliations during the provenance classification step.

- **ResearchRabbit** (researchrabbit.ai). Visualization layer over Semantic Scholar with collaborative annotation. Useful for documenting traversal decisions when multiple fact-checkers are working on the same draft.

- **Google Scholar** ("Cited by" link). Quick backward and forward traversal at the per-paper level. Lower data quality than Semantic Scholar or OpenAlex, but covers gray literature better.

- **arXiv** (arxiv.org). For preprints. arXiv's listing includes the author-submitted reference list; cross-reference each cited paper against indexed databases. The "31% drop in problem-solving" case (section 4.1) bottomed out in an arXiv preprint with non-ORCID authors; arXiv's own metadata makes it possible to flag that author signature.

### 5.2 URL and web-archival tools

- **urlhealth (Rao et al. 2026)**, arxiv 2604.03173. Classifies URLs as LIVE, DEAD, LIKELY_HALLUCINATED, or UNKNOWN. Applied to every node in the graph, urlhealth populates the URL status field for the provenance classification step. Used in conjunction with C1-URLROT-001 to distinguish rot from hallucination.

- **Wayback Machine** (web.archive.org). Retrieves historical versions of web pages. Critical when an intermediate node in a chain has been edited or removed. The Wayback version at the cited publication date is the version the chain author actually saw.

- **CrossRef** (crossref.org). DOI registry. Verifies that a cited DOI resolves to the paper claimed and that the paper's metadata matches the citation in the draft. Catches the Claude DOI-fabrication signature per C1-TOOLHALL-001.

- **Retraction Watch Database** (retractiondatabase.org). Catalogs retracted papers. Catches the case where a cited paper has been retracted between draft writing and fact-check.

### 5.3 AI-content detection tools

For classifying intermediate or upstream nodes as AI-CONTENT-FARM, apply the synthesis-content-quality skill's A1 model-family fingerprints to the cited source text. Specifically:

- Score the source for saturated AI vocabulary (criteria from A3.1 in synthesis-content-quality v4.0).
- Apply the substance-and-depth tests (A2) to assess insight-to-word ratio and load-bearing claim count.
- Check for combined-signal fingerprints (B2) that indicate generated rather than authored content.

A source that scores high on stylistic AI markers and also has the institutional markers of a content farm (recent domain registration, no editorial team, no traceable bylines) is a strong AI-CONTENT-FARM classification.

### 5.4 General fact-checking organizations

Professional fact-checking organizations publish methodologies that overlap with this protocol:

- **Snopes** (snopes.com). Methodology pages describe primary-source verification practices.
- **PolitiFact** (politifact.com). Documents the trace-back procedure for political claims with multiple citations.
- **Full Fact** (fullfact.org). UK-based; publishes detailed provenance analyses including citation graphs for high-profile claims.

These organizations do not automate the graph traversal, but their methodology articles are useful training material for fact-checkers learning the protocol.

### 5.5 Internal tooling notes

For long-running fact-check work on a particular publication or domain, building an internal database of previously verified upstreams accelerates future graph traversal. A claim that has appeared in five articles you fact-checked, each time tracing to the same PRIMARY-DOCUMENT upstream, does not need full re-traversal the sixth time; it needs re-verification that the upstream still exists and still says what it said. A claim that has appeared in five articles you fact-checked, each time tracing to a different AI-CONTENT-FARM upstream, signals a saturation of the corpus with laundered variants of the claim; the next instance gets routed to deeper verification immediately.

---

## 6. Revision to v1.1.0 Section 2 Multi-Source Confidence Framework

This section provides the explicit text revision suitable for citation from SKILL.md when v2.0 is drafted. The revision preserves the v1.1.0 methodology shape (a confidence table conditional on source count) while replacing the conditioning variable from raw count to graph-independent count.

### 6.1 Revised section text

The following text replaces v1.1.0 section 2 in its entirety.

> ## 2. Multi-Source Confidence Framework
>
> When synthesizing from multiple research sources (for example, several AI deep-research outputs on the same topic, or several news articles citing the same finding), the degree of agreement between sources provides a useful signal for accuracy only if the sources are graph-independent. Two citations that trace to the same upstream constitute one source, not two.
>
> ### 2.1 Graph independence vs. raw citation count
>
> Raw citation count is the number of distinct level-0 citations attached to a claim. Graph independence is the number of distinct upstream nodes (PEER-REVIEWED, PRIMARY-DOCUMENT, or REPUTABLE-NEWS terminals) reached by following the citation chains backward from each level-0 citation.
>
> Multi-source confidence applies only to graph-independent counts. The trace-back procedure for computing graph independence is specified in references/citation-laundering-detection.md.
>
> ### 2.2 Confidence levels (revised)
>
> | Graph-Independent Upstream Count (GI) | Confidence | Required Action |
> |--------|------------|-----------------|
> | **GI = 3 or higher** | Very high | Still verify against the primary upstreams. Three or more graph-independent upstreams agreeing is strong evidence. Verify that each upstream is a true primary or a reputable secondary, not a content farm. |
> | **GI = 2** | High | Verify numbers, names, and framing against both primary upstreams. Direction is likely correct; specifics may differ between the two sources, which itself is informative. |
> | **GI = 1** | Moderate | Treat as single-sourced regardless of how many level-0 citations the draft attaches. Apply the standard primary-source verification per section 3. |
> | **GI = 0 (cycles, dead-ends, content-farm upstreams only)** | Unverifiable | Remove the claim or hedge to opinion-marked language with no factual claim attached. Do not publish as established fact. |
> | **Upstreams conflict** | Low | Go to the upstreams directly. Do not average; do not pick the "most credible" upstream by surface appearance. The conflict is itself evidence that the claim is contested. |
>
> ### 2.3 Why raw count is no longer sufficient
>
> Citation laundering chains (per C1-LAUNDER-001) form because LLM-generated content is indexed, cited by other AI systems, and progressively given the appearance of independent verification through multiplying citations. Under 2026-era contamination (74 percent of newly indexed English-language web pages contain AI-generated content per Ahrefs; 1 in 277 PubMed papers references a fabricated paper per Topaz et al. May 2026 Lancet letter), the base rate of raw multi-citation agreement on a fabricated claim is nontrivial. Raw count is no longer a reliable proxy for independent verification.
>
> Graph independence is the corrected proxy. Three sources that all trace to one upstream is GI=1, regardless of the level-0 count. Two sources that trace to two genuinely independent upstreams is GI=2, regardless of whether the level-0 count looks impressive.
>
> ### 2.4 When to apply the full trace-back
>
> The full graph traversal (references/citation-laundering-detection.md, section 3) is required for:
>
> - Any claim presented in the draft with explicit multi-source reasoning ("multiple sources confirm," "several studies show," "experts agree").
> - Any claim whose verification matters to the article's argument (load-bearing claims).
> - Any claim with citations to sources you do not regularly verify and cannot vouch for from institutional knowledge.
>
> The full traversal is not required for routine claims with a single citation that you can verify directly against the primary upstream in standard time. For those, sections 3 (Verification Hierarchy) and 5 (Quote Verification Protocol) cover the procedure.

### 6.2 Cross-references to other v2.0 sections

The revised section 2 cross-references the following v2.0 SKILL.md sections:

- Section 3 (Verification Hierarchy): standard primary-source verification for GI=1 and GI>=2 claims.
- Section 5 (Quote Verification Protocol): applied at the upstream once identified.
- Section 6 (Study Verification Protocol): applied at PEER-REVIEWED upstreams.
- Section 8.7 (C1-SYNTH-001): applied when the upstream is classified AI-CONTENT-FARM or SYNTHETIC-CITATION.
- Section 8.6 (C1-URLROT-001): applied at every node for URL status classification.
- Section 8.8 (C1-LAUNDER-001): the canonical pointer to this file (references/citation-laundering-detection.md).
- Section 8.9 (C1-TOOLHALL-001): applied during provenance classification to identify model-family hallucination signatures in synthetic upstreams.

---

## 7. Limitations

The protocol is not omniscient. Several failure modes remain.

### 7.1 Chains too long to trace

Some chains exceed the depth at which manual or even automated traversal is tractable. A chain of 12 hops through a mix of academic preprints, news aggregators, and content farms can require days of work to trace. In practice, the protocol caps at four to six hops; beyond that, the cost of full traversal exceeds the value of verifying the specific claim, and the fact-checker either removes the claim or accepts a hedged version.

The mitigation is the truncation rule: if a chain has not terminated in a PRIMARY-DOCUMENT or PEER-REVIEWED node within four hops, treat the claim as if GI = 0 and apply the unverifiable remediation. This is conservative; it discards some claims whose upstreams are real but deeply buried. The conservatism is justified by the 2026 base-rate of laundering: a four-hop chain that has not surfaced a primary is more likely laundered than legitimately deep.

### 7.2 Sources in non-indexed venues

The graph traversal depends on intermediate sources being retrievable. When an intermediate source is in a non-indexed venue (a private corporate report; a paywalled trade publication without preview access; an audio recording transcribed without a published transcript; an internal document leaked but not republished), the chain breaks at that node. The fact-checker cannot follow the citation forward, and the upstream remains uncertain.

The mitigation is documentation: record the chain as far as it could be traced, mark the unretrievable node as UNKNOWN, and assess whether the claim can be supported by the verifiable portion of the chain alone. If the chain terminates at the unretrievable node, the claim's verifiability is conditional on the reader trusting that node. The article should explicitly acknowledge that conditionality rather than presenting the claim as multi-source verified.

### 7.3 AI-laundering inside non-public training data

The protocol traces the public citation graph. It does not have visibility into the training data of the AI systems that generated the draft. A claim may originate in a synthetic upstream that was never indexed publicly, was instead encoded into a model's parameters, and surfaces in outputs as parametric recall rather than as a citation chain.

This is the deepest form of laundering: the chain does not exist on the public web because the propagation happened inside training pipelines. The output presents a confident factual claim with no chain to trace.

The mitigation is structural rather than tactical. For claims that cannot be supported by any traceable citation chain at all (the AI asserts the claim without sourcing it, and no public corpus contains a corroborating statement), the claim is unverifiable per section 2.2 (GI = 0). The fact-checker treats it as if it had no citation. The fact that an AI emitted it with confidence is not, by itself, evidence; confidence calibration is treated separately in synthesis-content-quality.

The deeper mitigation is research-level: training data transparency requirements, model card disclosures of training corpora, and tools that can attribute outputs to specific training-data sources. These are out of scope for the fact-checker's per-draft workflow; they are tracked in the bibliography for synthesis-skills evolution.

### 7.4 Chain authenticity vs. claim accuracy

The protocol verifies that a citation chain is graph-independent. It does not, by itself, verify that the upstream is correct. A claim that traces to a PEER-REVIEWED primary in a top-tier journal still requires reading the primary to confirm the claim is accurately framed. The 2025-Nature-pilot-study case (section 4.4) is an example: the graph traversal identifies a real upstream, but the claim is laundered through framing drift rather than through chain fabrication.

The mitigation is to compose this protocol with the rest of the SKILL.md sections. Graph independence is necessary but not sufficient. Sections 4 (Common Error Patterns), 5 (Quote Verification), 6 (Study Verification), and 8 (Translation-Pass Re-Verification) cover the remaining verification work once the chain is mapped.

### 7.5 Adversarial laundering

The protocol assumes good-faith propagation: chains form because AI systems are trained to seek and cite sources, not because anyone is deliberately constructing laundering chains. Adversarial laundering (a bad actor seeding fake sources to influence downstream AI retrievals) is a different threat model. The graph traversal still detects the chain topology, but adversaries can construct chains designed to evade specific provenance checks (fake PEER-REVIEWED upstreams with synthetic author profiles on real-looking institutional pages; coordinated content-farm networks with curated stylistic variation).

The mitigation in this protocol is the provenance classification rigor: institutional affiliations checked against authoritative directories, ORCIDs verified against publication records, journal indexing verified in CrossRef and Scopus rather than self-attested. Adversarial laundering survives some of these checks but not all; the residual risk is acknowledged and tracked as an open research problem.

---

## 8. Summary

Citation laundering chains are the failure mode where multi-source confidence from v1.1.0 section 2 breaks. The remediation is the graph-traversal protocol specified in section 3 of this file: build the citation graph, identify terminal upstreams, classify provenance, count graph-independent upstreams, and score the claim against the revised confidence table in section 6.

The protocol composes with C1-SYNTH-001 (synthetic upstreams) and C1-URLROT-001 (URL status at each node). It does not replace primary-source verification; it specifies when primary-source verification is required despite the surface appearance of multi-source agreement.

The protocol is operational. It produces a graph, a count, and a remediation action. The graph is auditable. The remediation is unambiguous. The cost is the time to trace four to six hops; the benefit is that the v1.1.0 multi-source heuristic no longer fails silently against the 2026 contamination baseline.

---

## Bibliography for this file

- Ahrefs (2025). Measurement of AI-generated content in newly indexed English-language web pages (April 2025). *Source for: 74.2 percent contamination figure.*
- Enago (2025). "AI Hallucinations in Research: Why 40 percent of AI Citations Are Wrong." *Source for: hallucination chain documentation.*
- Penn (Rao, Wong, Callison-Burch) (2026). arxiv 2604.03173. *Source for: per-family hallucination percentages, urlhealth classifier (LIVE, DEAD, LIKELY_HALLUCINATED, UNKNOWN).*
- Retrieval Collapse (2026). arxiv 2602.16136. *Source for: 67 percent pool contamination yields 80 percent exposure contamination.*
- Spennemann, D. (2025). arxiv 2504.08755. *Source for: 30 to 40 percent of active web pages with AI signatures.*
- STAT News (2026-05-06). Coverage of Topaz et al. *Source for: fabricated citation propagation in academic literature.*
- Topaz et al. (2026). Lancet letter, May 2026. "Fabricated citations in academic literature." *Source for: 1 in 277 PubMed papers in 2026 reference a fabricated paper; twelvefold rise from 2023 per Claude exec framing, sixfold rise from 2023 to 2025 per Perplexity framing of the same study. Specific Lancet venue flagged for verification during synthesis.*
- synthesis-fact-checking v1.1.0, section 2 (Multi-Source Confidence Framework). Source repo: github.com/synthesisengineering/synthesis-skills. *Source for: the original multi-source confidence heuristic this protocol revises.*
- Gemini contribution to bucket C, "Primary-Backed Reference Chain (PBRC)" framing. *Source for: the trace-back protocol naming convention.*
- Snopes, PolitiFact, Full Fact methodology pages. *Sources for: professional fact-checking practices that overlap with the graph traversal protocol.*
- Claude exec 2026-05-18 canonical examples: "31 percent drop in problem-solving" laundered through three sources collapsing to single arXiv preprint by non-ORCID authors. *Source for: the canonical worked example in section 4.1.*

Em-dash audit on this file: zero em-dashes verified by grep before save.
