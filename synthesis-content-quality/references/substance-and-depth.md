# Substance and Depth Detection (Section A2)

> **Pattern catalog as of 2026-05.**
>
> Substance and depth failures are model-agnostic. They reflect the structural pressures of helpfulness-optimized LLM training (RLHF for length, alignment for safety, reward for "comprehensive" coverage) rather than any one family's style. This catalog stays stable across model generations because the underlying training pressures are stable. The patterns below are durable; refresh examples as new model defaults emerge.

This file is the full reference for Section A2 of `synthesis-content-quality` v4.0. The 17 sub-patterns below were promoted from v3.1.0 criterion 27 ("Superficial Depth") after unanimous cross-LLM consensus that the single criterion was load-bearing and compressed. This file is the practical workflow document for an editor evaluating AI-assisted or AI-generated content for substance.

---

## Philosophical framing

Substance and depth detection draws from three literatures.

**Frankfurt-style bullshit.** Harry Frankfurt's *On Bullshit* (2005) distinguishes lying from bullshit: the liar asserts the opposite of what they believe; the bullshitter is indifferent to truth. Hicks, Humphries, and Slater apply this to LLMs in "ChatGPT is Bullshit" (Ethics and Information Technology 26:38, 2024): LLMs do not lie because lying requires belief; they bullshit because they generate output optimized for plausibility, not truth. The model performs the shape of insight without delivering the insight. This is not a moral failing; it is the mechanical consequence of next-token prediction with helpfulness-tuned RLHF.

**Pseudo-profundity.** Pennycook et al. (2015) define pseudo-profundity as the tendency to ascribe profundity to vacuous statements, introducing the Bullshit Receptivity Scale (BSRS) with sentences like "Wholeness quiets infinite phenomena." Grammatically valid, lexically rich, rhythmically satisfying. They sound deep; they are not. LLM thought-leadership prose produces the same effect at lower intensity: "True innovation requires more than new ideas; it requires a new way of thinking about ideas." On second reading, tautological.

**Slop as a phenomenon.** Shaib et al. (2025) "Measuring AI 'Slop' in Text" finds that "slop" judgments correlate with latent dimensions of coherence and relevance, providing operational definitions for what editors mean when they say content "feels like AI." Sourati et al. (2025) on homogenization and Padmakumar and He (2024) on output diversity loss provide the empirical backdrop: AI output has measurably less diversity than human-written corpora.

For a newsroom editor reviewing AI-assisted submissions, this section provides 17 tests applicable in roughly five minutes per piece. The patterns catch what an experienced editor catches intuitively when they read AI-generated content and say "this says nothing." The catalog makes the intuition explicit, testable, and trainable.

---

## Reading the catalog

Each sub-pattern entry has four parts: **Description** (what the pattern is, grounded in the literature), **Concrete examples** (abbreviated; fuller sets in the unified bucket A document), **Fix or remediation** (what to do when detected), and a **Metadata** line consolidating location/register, model attribution, signal strength, base rate, causal hypothesis, detection difficulty, false positive risk, sources, era status, and zone tag.

All 17 substance-and-depth patterns share two metadata values:

- **Era status: Active (timeless).** The underlying training pressures (helpfulness-tuned RLHF, length rewards, alignment safety, lack of grounded retrieval) persist across model generations.
- **Zone tag: BODY-PERSISTENT.** Substance failures describe the substantive content of a piece, not its conversational wrapper.

The unverified Claude-pool figures (62 percent specificity-test failure, 73 percent zero-load-bearing-claims) appear with the flag `[opus-expansion-unverified-study]`. The underlying study has not been independently published; treat as Claude-pool research finding pending verification.

---

## A2-SUB-001: The deletion test

**Description.** A sentence or paragraph fails the deletion test if removing it from the piece does not change any claim, evidence, or transition in the surrounding content. Failed-deletion content is Frankfurt-style bullshit by construction: the writer was indifferent to truth at that point in the text. The test operationalizes the question "does this content carry weight?" If nothing collapses when you remove it, it was not load-bearing.

**Concrete examples.**

- "Innovation is a key driver of business success." Delete; nothing changes.
- "In today's rapidly evolving digital landscape, organizations must leverage innovative solutions to stay ahead of the curve." Delete; nothing changes.
- "It is important to consider multiple perspectives when making decisions." Delete; nothing changes.
- "The importance of this topic cannot be overstated. Researchers and practitioners alike recognize that this area deserves careful attention." Two-sentence delete; nothing changes.

**Fix or remediation.** Delete it, or convert it into a specific claim with evidence. If the paragraph survives the test after revision, strengthen it with a specific claim, datum, or distinction that would be lost if removed.

**Metadata.** Location: warm-up paragraphs, body connective tissue, conclusion openers. Model attribution: all families; highest in GPT and Claude. Signal strength: HIGH. Base rate: HIGH (40 to 73 percent of paragraphs in unedited output across samples; 73 percent claim from `[opus-expansion-unverified-study]`). Causal hypothesis: RLHF reward for length and comprehensiveness; training on padded corporate and academic prose. Detection difficulty: medium. False positive risk: LOW. Sources: Hicks et al. 2024, Frankfurt 2005, Pennycook 2015, PR Daily 2026, Shaib et al. 2025. Era: Active (timeless). Zone: BODY-PERSISTENT.

---

## A2-SUB-002: The specificity test (any-topic test)

**Description.** A sentence or paragraph fails the specificity test when substituting a different topic, company, or subject for the named one would produce an equally valid paragraph. The paragraph applies to any instance of its category. The test catches content that pretends to be about the named subject but is actually about the category. Per the unverified Claude-pool figure, 62 percent of sentences in unedited business and journalism prompts failed this test `[opus-expansion-unverified-study]`.

**Concrete examples.**

- "We are committed to delivering value to our customers." Applies to every company.
- "Our approach combines proven methodology with innovative thinking." Applies to every consulting firm.
- "The future of our industry depends on adapting to change." Applies to every industry.
- "Apple has navigated significant challenges in recent years, demonstrating resilience and adaptability in a rapidly evolving market." Substitute any Fortune 500 name; paragraph remains valid.
- "Acme Corp prioritizes customer satisfaction and operational excellence, leveraging cutting-edge technology to drive growth." Substitute Globex Inc; no adjustment needed.

**Fix or remediation.** Add specific facts, dates, numbers, or events that would not apply to a different subject. Force the inclusion of hard data (revenue figures, founder names, dates, product names, personnel decisions, geographies).

**Metadata.** Location: business and analysis writing, company profiles, policy analysis, case studies, executive summaries. Model attribution: all families; highest in business and marketing without grounded retrieval. Signal strength: HIGH (95 percent confidence). Base rate: HIGH in business copy, MED in technical writing; 78 percent of AI-generated corporate blog posts failed in one sample. Causal hypothesis: training data skew toward generic business writing; RLHF reward for inoffensive content; safety tuning that defaults to generic statements. Detection difficulty: easy (run the substitution). False positive risk: LOW. Sources: PR Daily 2026, Hicks et al. 2024, Shaib et al. 2025, "The Slop Era" (New Yorker 2025). Era: Active (timeless). Zone: BODY-PERSISTENT.

---

## A2-SUB-003: Load-bearing claim count

**Description.** Count the sentences in a paragraph that make claims the rest of the piece depends on. A paragraph with zero load-bearing claims is Frankfurt-bullshit by definition. A load-bearing claim is one that is falsifiable, contestable, or informative; one that, if removed, would weaken the argument. Meta-statements ("This article will examine..."), hedges ("It is important to consider..."), and framing ("The relationship between X and Y is complex...") do not count.

DeepSeek defines a quantitative threshold: a load-bearing claim density below 0.2 claims per sentence is suspect. Per the Claude-pool figure, 73 percent of paragraphs contributed zero load-bearing claims `[opus-expansion-unverified-study]`.

**Concrete examples.**

- A 5-sentence paragraph where each sentence rephrases the same framing has 0 load-bearing claims.
- A 5-sentence paragraph that opens with a claim, supports with a specific example, contextualizes with a named source, names a tradeoff, and points to the next step has 5 load-bearing claims.
- High count: "A 2024 meta-analysis of 47 studies found that X reduces Y by 15 to 22 percent under conditions of Z. The effect disappeared when [specific condition] was present."
- Low count: "The relationship between X and Y is complex and multifaceted. Experts have varying views on the matter. The full picture requires careful analysis of many factors."

**Fix or remediation.** Identify the main claim of each paragraph and make it explicit. Replace meta-statements with the specific claims they were meant to frame. Request bulleted lists of assertions before requesting narrative prose. Edit to raise claim density; cut filler.

**Metadata.** Location: all analytical writing; most pronounced in long-form essays, white papers, executive briefings. Model attribution: all families; mean density approximately 0.18 per the DeepSeek measurement. Signal strength: HIGH when density below 0.3 (90 percent confidence). Base rate: HIGH. Causal hypothesis: RLHF reward for "helpful" responses avoiding contestation; refusal-avoidance; token-length optimization without density reward. Detection difficulty: medium. False positive risk: LOW for sustained low density. Sources: Shaib et al. 2025, Hicks et al. 2024, ACM 2025 analysis of AI-generated essays. Era: Active (timeless). Zone: BODY-PERSISTENT.

---

## A2-SUB-004: Novelty signal

**Description.** A paragraph has low novelty when every claim it contains would already be known to a well-informed reader of the topic. The paragraph summarizes consensus rather than advancing, contextualizing, or challenging it. Novelty depends on audience: a definition of "machine learning" is novel for a general audience but slop for an ML conference audience. The test is calibrated to the stated audience of the piece.

DeepSeek measures novelty as the percentage of sentences introducing new, non-obvious information. AI output typically scores below 15 percent.

**Concrete examples.**

- Zero novelty: "Artificial intelligence has transformed many industries in recent years, with applications ranging from healthcare to finance."
- Zero novelty: "Strong communication is important for team success."
- High novelty: "Strong communication on this team broke down at the handoff between design and engineering, traced to a missing weekly sync now scheduled Monday 10am."
- Zero novelty: "Email marketing can be an effective way to reach customers."
- High novelty: "Email open rates for B2B SaaS declined 12 percent in Q3 2025 according to Campaign Monitor."

**Fix or remediation.** Distinguish introductory from analytical sections. Mark background clearly. Make sure analytical sections contain claims beyond the background. Delete truisms. Explicitly prompt for "new insights," "contrarian views," or "unexpected findings." Ask "what here would surprise an expert in the field?"

**Metadata.** Location: introduction and background sections; SEO-optimized content; research papers, news analysis, thought leadership. Model attribution: all families; highest when prompts ask for "background" or "overview." Signal strength: MEDIUM. Base rate: HIGH in explanatory contexts; below 15 percent novelty typical. Causal hypothesis: training data skew toward encyclopedic text; RLHF reward for consensus-corroborated content; refusal-avoidance. Detection difficulty: hard (requires domain expertise and audience clarity). False positive risk: medium (introductions legitimately cover background). Sources: Shaib et al. 2025, Hicks et al. 2024, Nieman Lab 2025. Era: Active (timeless). Zone: BODY-PERSISTENT.

---

## A2-SUB-005: Insight-to-word ratio

**Description.** Approximate insight density: distinct claims per 100 words. AI slop often has 0 to 1 claim per 100 words. Substantive writing has 3 to 6 per 100 words. The ratio operationalizes the editorial intuition that AI prose is "padded": grammatically clean, structurally sound, and weight-bearing only at sparse intervals.

DeepSeek sets a threshold of below 0.05 insights per 100 words as suspect. Perplexity frames AI prose as typically delivering 1 insight per 5 to 10 sentences versus skilled analytical prose at 1 per 2 to 3 sentences.

**Concrete examples.**

- Low ratio (0.5 per 100 words): A 200-word paragraph with one buried claim ("the migration took six weeks") in 199 words of framing.
- High ratio (3 per 100 words): A 200-word paragraph with six specific claims, each backed by an example.
- Low ratio: "Machine learning has become increasingly important across many fields. Many organizations are adopting it. This adoption raises important questions. These questions deserve careful consideration." Four sentences, zero insights.
- High ratio: "Transformer models require compute that scales quadratically with sequence length, which is why context windows were limited to 4K tokens until sliding-window attention made 100K+ contexts economical." One sentence, two insights.
- Low ratio: A three-page email explaining a single one-line code change.

**Fix or remediation.** Tighten ruthlessly. Ask of each sentence: what does the reader learn from this that they did not know before? Demand conciseness. Use strict length limits ("Under 50 words") in generation prompts.

**Metadata.** Location: all analytical prose; long-form, newsletters, social threads, internal corporate communications. Model attribution: all families; particularly verbose in Claude and GPT. Signal strength: HIGH for sustained low ratios (85 percent confidence). Base rate: HIGH. Causal hypothesis: RLHF reward for length correlating with perceived thoroughness; helpfulness optimization driving verbosity. Detection difficulty: medium. False positive risk: LOW for sustained measurement. Sources: Hicks et al. 2024, Shaib et al. 2025, editorial practitioner methodology. Era: Active (timeless). Zone: BODY-PERSISTENT.

---

## A2-SUB-006: The any-company test (specialization for business writing)

**Description.** A sentence in a piece about a specific company fails the any-company test if it would apply equally to any company. This is a specialization of A2-SUB-002 (specificity test) for business writing. Most marketing copy and many press releases fail this test universally. The any-company test is sharper than the general specificity test because the named company creates a presumption of specificity that the prose fails to honor.

Originally described as an editorial heuristic in PR Daily (2026) for distinguishing generic from substantive executive communication.

**Concrete examples.**

- Fails: "We are dedicated to our customers and committed to excellence."
- Passes: "We migrated 12 million customer records from Postgres to Spanner over six weeks because Postgres replication had a 4-hour failover window incompatible with our SLAs."
- Fails: "Microsoft has demonstrated a commitment to innovation and a focus on delivering value to customers."
- Passes: "Netflix's Q3 2024 revenue of $9.83B, driven by 14.4 percent growth in advertising-supported tier subscriptions and margin expansion from its password-sharing crackdown."
- Fails: Passages about "Acme Corp's digital transformation" that read identically when "Beta Inc" is substituted.
- Fails: "Company X must align people, process, and technology"; "leaders should move with urgency and care."

**Fix or remediation.** Add specific data that is company-unique: revenue figures, product names, personnel decisions, dates, locations, customer counts. Require specific incentives, constraints, actors, and metrics.

**Metadata.** Location: business writing, company analysis, strategy decks, leadership posts. Model attribution: all families; most pronounced without grounding data. Signal strength: HIGH. Base rate: HIGH in business copy without grounding. Causal hypothesis: training data skew, corporate-register marketing templates, safety tuning. Detection difficulty: easy. False positive risk: LOW. Sources: PR Daily 2026, Hicks et al. 2024. Era: Active (timeless). Zone: BODY-PERSISTENT.

---

## A2-SUB-007: Hedging as substance evasion

**Description.** A hedge that would be appropriate if uncertainty existed is used to avoid making a claim the evidence would support. The hedge masks the absence of substance by making non-commitment look like epistemic humility. The key distinction: hedging that narrows or qualifies a real claim is legitimate; hedging that replaces the claim is evasion.

Per Hicks et al. (2024), "non-commitment is its own form of disregard for truth." The bullshitter does not need to assert falsity; declining to assert anything at all is sufficient.

**Concrete examples.**

- Uniform hedging (evades commitment): "This approach may improve performance, potentially leading to better outcomes, which could translate into business value."
- Selective hedging on the genuinely uncertain part: "This approach improves p99 latency by 30 to 40 percent on our workload; it may also reduce p50, though the data is noisy."
- Evasion: "It is generally understood that, in many cases, effective leadership can contribute to positive organizational outcomes."
- Evasion: "While it's difficult to draw definitive conclusions, the evidence does suggest that the approach can be effective under certain conditions."
- Evasion: "It could be argued that this approach may perhaps yield varying degrees of success."

**Fix or remediation.** Replace with either a specific claim or an explicit statement of what is and is not known. Strip the qualifiers and ask if the remaining sentence makes a verifiable claim. Replace with specific confidence intervals or remove.

**Metadata.** Location: academic writing, scientific reports, policy documents, advisory content, literature reviews. Model attribution: Claude highest (Constitutional AI), GPT high, Gemini medium. Signal strength: MEDIUM alone; HIGH combined with A2-SUB-003 (80 percent confidence). Base rate: HIGH in unedited output. Causal hypothesis: alignment and safety tuning reward non-commitment; refusal-avoidance substitutes hedges; reward shaping penalizes overconfidence. Detection difficulty: medium (read for what was not said). False positive risk: medium (some uncertainty is genuine). Sources: BlogPros 2026, Hicks et al. 2024, Linguistics Journal 2026. Era: Active (timeless). Zone: BODY-PERSISTENT.

---

## A2-SUB-008: Survey-without-claim pattern

**Description.** A piece surveys multiple positions or options without taking a position. The paragraph or section covers all perspectives, aspects, or factors without committing to any. The reader finishes better informed about what questions exist but no better positioned to answer them. The pattern is a topical survey with no thesis.

The distinguishing feature from A2-SUB-010 (both-sides-without-position): survey-without-claim covers many positions; both-sides covers exactly two with false symmetry. Both fail to commit, but the structural failure differs.

**Concrete examples.**

- A 1000-word piece on database choice that describes Postgres, MySQL, MongoDB, and Cassandra without recommending one for the specific use case discussed.
- A report on climate change impacts that lists numerous effects but avoids policy recommendations or statements about urgency.
- "Some researchers argue X. Others argue Y. A third perspective holds Z. Each view has merit, and the debate continues."
- "Proponents argue X, while detractors maintain Y. Ultimately, the situation requires ongoing monitoring by regulatory bodies."
- "Some researchers argue X. Others contend Y. Still others find Z. These different viewpoints highlight the complexity of the issue."

**Fix or remediation.** Add a position. After presenting multiple views, identify which one is best supported by the evidence and say so. Prompt the model explicitly to act as an advocate for a specific outcome. Demand a thesis statement; remove survey without synthesis.

**Metadata.** Location: analysis, editorial, advisory content, academic essays, op-eds, policy briefs. Model attribution: Claude very high, GPT high, Gemini high. Signal strength: HIGH combined with A2-SUB-007 (88 percent confidence). Base rate: HIGH; near universal in zero-shot policy or opinion prompts. Causal hypothesis: alignment tuning for balanced perspectives; RLHF reward for "fairness"; Constitutional constraints; training on survey-style data. Detection difficulty: medium (read the final paragraph). False positive risk: medium (journalism legitimately presents multiple views). Sources: BlogPros 2026, Hicks et al. 2024, Wired 2025. Era: Active (timeless). Zone: BODY-PERSISTENT.

---

## A2-SUB-009: Generic insight

**Description.** A claim phrased generically that does no specific work. Sibling to A2-SUB-002 (specificity test failure) but at the claim level rather than the paragraph level. A generic insight is a truism dressed in formal language: technically true, applicable to any era and any subject, providing no specific value.

**Concrete examples.**

- Generic: "Good leadership requires both vision and execution."
- Specific: "On this team, the gap was between quarterly vision (clear, communicated, agreed) and weekly execution (unowned, drifting). We closed it by adding a 30-minute Monday review of the prior week's vision-to-execution delta."
- Generic: "Effective communication is crucial for team success."
- Generic: "Innovation drives progress in the technology sector."
- Generic: "Customer satisfaction is a top priority for businesses."
- Generic: "Strong leadership is essential to navigating periods of uncertainty."
- Generic: "Organizations must embrace digital transformation to remain competitive."

**Fix or remediation.** For every generic insight, ask: "In what year would this be false? For what company would this not apply?" If no answer exists, delete or replace with a specific claim. Replace with time-bound and context-bound statements. Demand specific, actionable, or counter-intuitive insights.

**Metadata.** Location: business writing, motivational content, advice articles, LinkedIn-style content; very high in marketing. Model attribution: all families; GPT-4o and Claude particularly. Signal strength: MEDIUM alone; HIGH for density (3 or more per page). Base rate: HIGH; very high in marketing genre. Causal hypothesis: training data includes generic business writing; RLHF reward for "resonant" content. Detection difficulty: easy. False positive risk: LOW. Sources: Hicks et al. 2024, Pennycook 2015, Shaib et al. 2025. Era: Active (timeless). Zone: BODY-PERSISTENT.

---

## A2-SUB-010: Both-sides-without-position

**Description.** More specific than A2-SUB-008 (survey-without-claim). This pattern presents exactly two opposing positions as though they are equivalent, even when evidence strongly favors one side. The both-sides framing is a rhetorical construction, not an epistemic judgment. The model rigorously maps two opposing viewpoints with perfect symmetry, granting exactly equal weight to both, regardless of the actual empirical evidence supporting either side.

This is the "refusal to conclude" framing: the model has done the analytical work to identify the positions but withholds the synthetic judgment that would resolve them.

**Concrete examples.**

- No commit: "Some argue X, while others argue Y, and both perspectives have merit."
- Commit: "X is the better approach for our load pattern because Y considerations are not load-bearing in our context."
- "Some people believe vaccines are safe and effective. Others have concerns about side effects. It's important for individuals to do their own research." (Asymmetric evidence presented symmetrically.)
- "Proponents of the policy argue it will reduce inequality. Critics argue it will harm economic growth. Both perspectives have merit."
- "Advocates point to the economic benefits, whereas opponents highlight the environmental costs, leaving the debate entirely open."
- "Proponents say X, opponents say Y. The issue remains contentious, and future developments will determine the outcome."

**Fix or remediation.** Identify whether evidence actually divides evenly. If one side is better supported, say so and cite the evidence. Reserve balance for genuine uncertainty. Require a decision; if the evidence is mixed, state the weight of evidence.

**Metadata.** Location: opinion pieces, analytical articles, policy briefs, debate summaries, technical comparisons. Model attribution: Claude very high (Constitutional AI), GPT high, Gemini high. Signal strength: HIGH when evidence favors one side (85 percent confidence). Base rate: HIGH in policy contexts; dominant in comparative tasks. Causal hypothesis: alignment and safety tuning for balanced perspectives; bias-reduction RLHF that cannot distinguish genuine controversy from false balance. Detection difficulty: hard (requires domain knowledge about evidence quality). False positive risk: medium (genuine controversies deserve balanced presentation). Sources: v3.1.0 criterion 33; Hicks et al. 2024; ACL 2025. Era: Active (timeless). Zone: BODY-PERSISTENT.

---

## A2-SUB-011: Pseudo-profundity

**Description.** Sentences that sound deep or insightful on first reading but dissolve into tautology or emptiness on second reading. Named and studied by Pennycook et al. (2015), which defined the Bullshit Receptivity Scale (BSRS) using sentences like "Wholeness quiets infinite phenomena" and "The invisible is beyond infinite perception."

The pattern applies to AI-generated business, motivational, and philosophical prose at lower intensity than the BSRS test items but with the same structural property: the sentence performs depth without containing it.

**Concrete examples.**

- Pure BSRS-style: "Wholeness quiets infinite phenomena."
- Tautological: "True leadership is about more than just leading."
- Aphoristic-empty: "True innovation requires more than new ideas; it requires a new way of thinking about ideas."
- Aphoristic-empty: "The most important decisions are often the ones we don't realize we're making."
- Business-pseudo-profound: "Complexity reveals the hidden architecture of change."
- Business-pseudo-profound: "The future belongs to those who can navigate ambiguity."
- Corporate-meaningless: "The synergy of our holistic alignment creates a transformative impact on user empowerment."
- Corporate-meaningless: "Strategic intention is the ultimate mechanic of future manifestation."

**Fix or remediation.** Test each aphoristic sentence by converting it to its literal paraphrase. "True innovation requires a new way of thinking about ideas" means: "Thinking differently produces better ideas." Is that the claim? If so, say that. Translate into plain language; if it vanishes, it was empty.

**Metadata.** Location: motivational content, leadership writing, thought leadership, LinkedIn posts, marketing copy. Model attribution: all families, highest in motivational contexts; GPT and Claude both produce these when prompted for philosophical content. Signal strength: HIGH (90 percent confidence). Base rate: MEDIUM in most genres; HIGH in motivational and thought-leadership. Causal hypothesis: training data skew toward motivational content (TED talks, LinkedIn, business books) that rewards aphoristic constructions; mimicry of shallow inspirational language. Detection difficulty: medium (requires reading twice). False positive risk: LOW (skilled writers produce genuine aphorisms; the test is dissolution on second reading). Sources: Pennycook et al. 2015 (canonical BSRS reference); Hicks et al. 2024. Era: Active (timeless). Zone: BODY-PERSISTENT.

---

## A2-SUB-012: Conclusion-shaped paragraphs that do not conclude

**Description.** A paragraph uses conclusion-signal words ("In summary," "Therefore," "Ultimately,") but reaches no new claim that the body did not already make. The paragraph is formatted as a conclusion (final position, conclusion-signal phrasing) but does not reach a conclusion. It restates the topic, acknowledges complexity, and defers rather than resolving.

The pattern mimics the syntactic rhythm and structure of a conclusion without performing the synthetic work a conclusion is supposed to do.

**Concrete examples.**

- "In conclusion, the migration is worth doing if the team has capacity to do it well." (When the body has not established when the team would have capacity.)
- "In conclusion, the various factors discussed highlight the complexity of the issue, and further research will be essential to fully understand its implications."
- "Ultimately, the integration of AI into daily life presents both opportunities and challenges, requiring careful consideration from policymakers and individuals alike."
- "To summarize, the company's new strategy aims to enhance efficiency, foster innovation, and expand market reach, positioning it for future success."
- "Ultimately, there are no easy answers to these questions. Each situation requires careful consideration of the relevant factors."
- "Ultimately, the path forward is balance"; "the answer lies in thoughtful integration"; "success depends on navigating both sides carefully."

**Fix or remediation.** A conclusion should answer the question the document posed or make the strongest version of the argument. If the document surveyed a topic, the conclusion should state what the best available answer is, with explicit acknowledgment of what remains uncertain. Truncate the final paragraph if it adds no new claim.

**Metadata.** Location: document closers, section closers, final paragraphs. Model attribution: all families; highest when models are asked to "conclude" explicitly. Signal strength: HIGH (90 percent confidence). Base rate: HIGH; near universal unless explicitly prompted to omit conclusions. Causal hypothesis: RLHF reward for "completeness" without penalizing vacuous conclusions; academic training data skew; standard essay-format templates. Detection difficulty: easy. False positive risk: LOW. Sources: BlogPros 2026, Hicks et al. 2024, Shaib et al. 2025. Era: Active (timeless). Zone: BODY-PERSISTENT.

---

## A2-SUB-013: Frictionless-transition padding

**Description.** A piece uses transition words ("Furthermore," "Moreover," "Additionally," "On the other hand,") at high density to glue together paragraphs that would not naturally connect. The transitions are the symptom of missing argumentative scaffolding. Each transition word is a small piece of textual reassurance to the reader that the argument is progressing, when in fact the argument is repeating, restating, or wandering.

Sibling to v3.1.0 criterion 6 (Overuse of Transition Words and Formal Conjunctions), but framed as a substance failure rather than a stylistic one. The transition words are not the problem; the absence of underlying argumentative logic the transitions are supposed to signal is the problem.

**Concrete examples.**

- A piece where each paragraph opens with "Furthermore," "Additionally," "Moreover" in succession without these words being earned by the underlying logic.
- An essay where every paragraph begins with a transition word and ends with a summary sentence, creating the appearance of structured argument while the content underneath is restatement.
- A blog post where "On the other hand" introduces a paragraph that does not contrast with the previous paragraph; the transition is decorative.

**Fix or remediation.** Cut the transitions. If the paragraphs do not naturally connect without the transition glue, the argument needs repair, not transition glue.

**Metadata.** Location: body sections of essays, blog posts, white papers; especially common in long-form output without an outline. Model attribution: all families. Signal strength: MEDIUM (sharpens combined with A2-SUB-001). Base rate: HIGH in unedited AI long-form output. Causal hypothesis: RLHF reward for "smooth" prose; training data skew toward formal essays; token-by-token generation producing transitions opportunistically. Detection difficulty: easy (count transition openers per paragraph). False positive risk: medium (academic and legal writing use heavy transitions legitimately). Sources: Claude expansion; v3.1.0 criterion 6. Era: Active (timeless). Zone: BODY-PERSISTENT.

---

## A2-SUB-014: Evidence displacement

**Description.** Facts, quotations, and studies appear in the text, but they never do argumentative work. Each citation is a fact stated without inference; each quote is presented without interpretation; each sourced survey appears without a relevance test for the argument at hand. The pattern produces a surface impression of rigor (sources cited, data referenced) while the underlying argument remains unsupported because the evidence is decorative rather than load-bearing.

Particularly strong in AI-assisted synthesis and search-answer workflows where retrieval surfaces sources but the generation step does not integrate them into the argument.

**Concrete examples.**

- Statistic with no inference: "The market is projected to grow 14 percent by 2027." (No connection drawn to the argument being made.)
- Quote with no interpretation: "As Smith (2023) writes, 'governance is hard.'" (No explanation of what Smith's claim implies for the current piece.)
- Sourced survey with no relevance test: "A 2024 Pew survey found 67 percent of respondents agreed with X." (Without addressing whether the survey methodology applies to the current question.)
- A paragraph that cites three studies, names the authors, gives the years, and provides no synthetic claim that uses any of them.

**Fix or remediation.** After each cited fact, add the sentence "Therefore, for this argument, it means X." If the "therefore" sentence cannot be written, the citation is decorative and should be removed or the argument restructured around it.

**Metadata.** Location: research summaries, fact-heavy articles, white papers, search-engine answer surfaces. Model attribution: strong in AI-assisted synthesis and search-answer workflows. Signal strength: medium-high. Base rate: medium. Causal hypothesis: retrieval wrappers surfacing sources without integration; citation theater; source-stacking prompts. Detection difficulty: medium (read for what each citation contributes). False positive risk: medium (literature reviews legitimately list sources). Sources: ChatGPT contribution; retrieval-augmented generation literature. Era: Active (timeless). Zone: BODY-PERSISTENT.

---

## A2-SUB-015: The "So What?" test

**Description.** After reading a paragraph, ask "So what?" If no answer that advances understanding or action can be given, the paragraph is empty. This is an editorial heuristic that operationalizes the substance question at the paragraph level. The reader's implicit "so what?" is the gold standard for whether a paragraph earned its place in the piece.

**Concrete examples.**

- Fails: A paragraph about market trends without implications for the company, the reader, or the decision being made.
- Fails: A paragraph that defines a term without explaining why the definition matters here.
- Passes: A paragraph about market trends that explicitly states which decision should change as a result.

**Fix or remediation.** Add the implication, or delete the paragraph.

**Metadata.** Location: all analytical prose. Model attribution: universal. Signal strength: MEDIUM. Base rate: HIGH in unedited AI output. Causal hypothesis: same as A2-SUB-001 (RLHF for length over information density). Detection difficulty: easy (ask "so what?"). False positive risk: LOW. Sources: DeepSeek contribution; editorial practitioner heuristic. Era: Active (timeless). Zone: BODY-PERSISTENT.

---

## A2-SUB-016: Evidence-to-claim ratio

**Description.** For each claim in the piece, is evidence (data, citation, example) provided? AI frequently makes claims without support, relying on the model's authoritative tone to substitute for actual sourcing. The ratio is calculated as the number of claims that have supporting evidence divided by the total number of claims.

**Concrete examples.**

- Unsupported: "Employee burnout is a growing concern." (No statistic, no source, no example.)
- Supported: "Employee burnout rose 23 percent year-over-year in 2024 according to Gallup's State of the American Workplace report."
- Unsupported: "AI will fundamentally change knowledge work."
- Supported: "GitHub Copilot users complete coding tasks 55 percent faster according to GitHub's 2023 productivity study."

**Fix or remediation.** For every claim, attach evidence. If evidence is not available, soften the claim to reflect the actual epistemic status.

**Metadata.** Location: all analytical prose; especially business writing, thought leadership, op-eds. Model attribution: universal across families; approximately 70 percent of AI-generated analytical text contains unsupported claims (DeepSeek sample). Signal strength: MEDIUM (sharpens combined with A2-SUB-003 and A2-SUB-014). Base rate: HIGH in unedited AI output. Causal hypothesis: models generate plausible rather than sourceable text; training data includes many opinion pieces without evidence; RLHF reward for assertive prose without rewarding citation. Detection difficulty: medium. False positive risk: medium (memoir and personal essay legitimately make personal-experience claims). Sources: DeepSeek contribution. Era: Active (timeless). Zone: BODY-PERSISTENT.

---

## A2-SUB-017: Specificity score

**Description.** Assign a score 1 to 5 on how many specific, non-generic details the text contains. AI text consistently scores 1 to 2; human expert text scores 3 to 5. The score operationalizes the "would this apply to any company" intuition from A2-SUB-006 in a quantitative form an editor can apply quickly.

Specificity dimensions to count:

- Named entities (people, companies, products, places)
- Numbers (revenue, percentages, counts, dates)
- Concrete examples (named instances rather than generic categories)
- Domain-specific vocabulary used precisely
- Causal mechanisms explicitly stated

**Concrete examples.**

- Score 1: "Our solution leverages AI to drive efficiencies."
- Score 5: "Our NLP pipeline reduced false positives by 22 percent on the CoNLL-2003 dataset compared to BERT-base."
- Score 1: "The company has strong leadership."
- Score 5: "CEO Lisa Su led AMD's 2017 EPYC launch, recapturing 24 percent server market share by 2024 according to Mercury Research."

**Fix or remediation.** Demand specific details. Replace generic claims with named entities, numbers, and concrete examples.

**Metadata.** Location: all analytical prose; especially useful for business writing. Model attribution: universal across families. Signal strength: HIGH. Base rate: HIGH for low scores (1 to 2) in unedited AI output. Causal hypothesis: same as A2-SUB-006 (training data skew, safety tuning preferring generic, lack of grounded retrieval). Detection difficulty: easy. False positive risk: LOW. Sources: DeepSeek contribution; journalistic specificity standards. Era: Active (timeless). Zone: BODY-PERSISTENT.

---

## Cluster map

The 17 sub-patterns cluster in five characteristic ways. One test per cluster usually surfaces the dominant failure mode without running all 17:

1. **Empty-paragraph cluster:** A2-SUB-001 (deletion test), A2-SUB-005 (insight-to-word ratio), A2-SUB-015 (so what?). All measure whether a paragraph carries weight. Diagnose once with the deletion test; the others usually follow.
2. **Generic-content cluster:** A2-SUB-002 (specificity test), A2-SUB-006 (any-company test), A2-SUB-009 (generic insight), A2-SUB-017 (specificity score). Substitution and counting variants of the same property.
3. **Evasion cluster:** A2-SUB-007 (hedging), A2-SUB-008 (survey-without-claim), A2-SUB-010 (both-sides), A2-SUB-012 (conclusion-shaped non-conclusion). Reluctance to commit at sentence, paragraph, and document levels.
4. **Performance cluster:** A2-SUB-011 (pseudo-profundity), A2-SUB-013 (transition padding), A2-SUB-014 (evidence displacement). Surface performances of depth, connection, and rigor that the prose does not actually deliver.
5. **Claim-density cluster:** A2-SUB-003 (load-bearing claim count), A2-SUB-004 (novelty signal), A2-SUB-016 (evidence-to-claim ratio). Three slices of how much the prose contributes per unit of length.

---

## Application workflow for editors

This is the operational summary. An editor reviewing AI-assisted content should be able to evaluate substance and depth in roughly five minutes using the workflow below.

### Five-minute substance evaluation

**Minute 1: Document-level scan.**

Read the introduction and conclusion. Apply two tests:

1. **A2-SUB-012 (conclusion-shaped non-conclusion).** Does the conclusion answer the question the introduction posed? Does it commit to a position? If it restates, defers, or "ultimately calls for further research," flag the document as substance-evasive at the document level.
2. **A2-SUB-008 (survey-without-claim) or A2-SUB-010 (both-sides-without-position).** Does the piece take a position? If it surveys without committing, flag.

If both tests fail at the document level, the substance problem is structural; deeper paragraph-level testing will not save the piece. The fix is editorial: ask the author to commit to a thesis.

**Minute 2: Sample-paragraph deletion test.**

Pick three paragraphs from the body: one near the start, one in the middle, one near the end. Apply A2-SUB-001 (deletion test) to each: would the piece be weaker if this paragraph were removed?

- If 0 of 3 paragraphs are load-bearing: the piece is substance-empty. Major rewrite required.
- If 1 of 3 paragraphs is load-bearing: substantial cuts needed. The piece is mostly filler.
- If 2 of 3 paragraphs are load-bearing: targeted edits needed. Mark the filler paragraph for cut or rewrite.
- If 3 of 3 paragraphs are load-bearing: the document-level structure may be fine; check substance at a finer grain.

**Minute 3: Specificity scan on the body.**

Apply A2-SUB-002 (specificity test) or A2-SUB-006 (any-company test) to the entire body. Read with the question "could I substitute a different subject and still have the same paragraphs?" If yes anywhere in the body, mark those paragraphs.

A quick proxy: A2-SUB-017 (specificity score). Read the body and assign a 1 to 5 score. If the score is 1 or 2 for the entire body, the substance failure is at the claim level; the piece needs more specific examples, numbers, and named entities.

**Minute 4: Claim and evidence audit.**

Apply A2-SUB-003 (load-bearing claim count) and A2-SUB-016 (evidence-to-claim ratio) together. Count claims in the body and check whether each has supporting evidence.

- High claim density with high evidence ratio: the piece has substance.
- High claim density with low evidence ratio: the piece makes assertions but does not support them. The fix is sourcing.
- Low claim density: the piece is filler regardless of evidence. The fix is to make the implicit claims explicit and add the missing claims.

If the evidence is present but does not advance the argument, also apply A2-SUB-014 (evidence displacement): are the citations decorative or load-bearing?

**Minute 5: Genre-specific checks.**

Depending on the genre, apply targeted tests:

- **Motivational, leadership, thought-leadership content.** Apply A2-SUB-011 (pseudo-profundity). Read each aphoristic sentence twice; paraphrase it literally; if it dissolves, mark it.
- **Analytical and policy content.** Apply A2-SUB-007 (hedging as substance evasion). Strip the qualifiers from each sentence; if what remains makes no verifiable claim, the hedge is hiding emptiness.
- **Business and corporate writing.** Apply A2-SUB-006 (any-company test) and A2-SUB-009 (generic insight). The dominant failure modes in business genres are generic content and pseudo-specificity.
- **Long-form essays, white papers, blog posts.** Apply A2-SUB-005 (insight-to-word ratio) and A2-SUB-013 (frictionless-transition padding). If the ratio is below 1 claim per 100 words or transitions dominate openers, the piece is padded.
- **News analysis, research summaries.** Apply A2-SUB-004 (novelty signal). Is the analytical content distinguishable from the background content? Is any of it new to a well-informed reader?

### Output of the five-minute evaluation

After five minutes, the editor has verdicts on commitment (Minute 1), paragraph load-bearing (Minute 2), specificity (Minute 3), claim density and evidence (Minute 4), and genre-specific failure modes (Minute 5). The headline result is the four-quadrant assessment:

| Document commits | Paragraphs load-bearing | Verdict |
|---|---|---|
| Yes | Yes | Substance present. Fine-tune at the sentence level. |
| Yes | No | Structural commitment but empty body. Cut filler; tighten. |
| No | Yes | Body has substance but no thesis. Add commitment; rewrite intro and conclusion. |
| No | No | Substance-empty piece. Major rewrite or rejection. |

### When to apply the full 17-test catalog

The five-minute workflow is sufficient for most editorial review. Apply the full 17-test catalog when training editors, when the workflow produces an ambiguous verdict, or when building detection tools or content-team checklists.

### Workflow integration with other A-section patterns

Substance and depth detection (A2) is complementary to model-family fingerprinting (A1) and to the refreshed 42-criterion catalog (A3). The recommended sequence: (1) zone detection (full response or artifact only); (2) A1 family fingerprinting; (3) A2 substance evaluation via the five-minute workflow above; (4) A3 stylistic and structural scan; (5) B2 combined-signal evaluation if AI provenance is in question. For editorial purposes, A2 is the highest-yield pass. Substance is what readers care about; style and family fingerprints are secondary.

---

## Common false positives and how to handle them

Substance tests have lower false positive rates than A1 style-based tests, but the false positives that do occur cluster in specific genres. The general principle: apply each test in the context of the genre and to its underlying intent, not its mechanical form.

- **Personal essay and memoir.** A2-SUB-016 (evidence-to-claim ratio) false-positives because the evidence is the author's experience, not externally citable. Adjusted test: is the claim grounded in a specific named experience?
- **Literature review, annotated bibliography.** A2-SUB-014 (evidence displacement) false-positives where listing sources is the explicit purpose. Apply only when the genre purports to make an argument.
- **Introductory and educational content.** A2-SUB-004 (novelty signal) false-positives because consensus is the point. Calibrate novelty to the stated audience.
- **Straight news with intentional neutrality.** A2-SUB-008 and A2-SUB-010 false-positive where journalistic convention is to present without committing. Apply only to analytical or opinion journalism.
- **Academic writing with epistemic hedging.** A2-SUB-007 false-positives where hedging is a discipline norm. Apply the qualifier-stripping test: if the unhedged sentence still makes a claim, the hedge is legitimate.

---

## Era and recency note

All 17 sub-patterns are catalogued as **Active (timeless)**. The underlying mechanisms (helpfulness-tuned RLHF, length rewards, alignment for safety, lack of grounded retrieval) are structural properties of the current LLM training paradigm. If a future paradigm shifts reward modeling toward information density or verified tool-use signals, prevalence may attenuate; the detection methodology (deletion test, specificity test, load-bearing claim counting) is durable across paradigm shifts.

The Claude-pool figures (62 percent specificity-test failure, 73 percent zero-load-bearing-claims) are flagged `[opus-expansion-unverified-study]` and should be replaced when independent measurement becomes available. The patterns themselves are observable in any sample of unedited AI output regardless of the specific figures.

---

## Bibliography for A2

**Academic sources.**

- Frankfurt, Harry G. (2005). *On Bullshit.* Princeton University Press.
- Hicks, Michael Townsen; Humphries, James; and Slater, Joe. (2024). "ChatGPT is Bullshit." *Ethics and Information Technology* 26:38.
- Pennycook, Gordon; Cheyne, James Allan; Barr, Nathaniel; Koehler, Derek J.; and Fugelsang, Jonathan A. (2015). "On the reception and detection of pseudo-profound bullshit." *Judgment and Decision Making* 10(6):549-563.
- Shaib, Chantal; Chakrabarty, Tuhin; Garcia-Olano, Diego; and Wallace, Byron C. (2025). "Measuring AI 'Slop' in Text." arXiv 2509.19163.
- Sourati et al. (2025). Homogenization survey of AI output diversity.
- Padmakumar, Vishakh; and He, He. (2024). On output diversity loss in language models.

**Practitioner sources.**

- PR Daily (2026); BlogPros (2026); Nieman Lab (2025); The New Yorker (2025) "The Slop Era"; Wired (2025); ACL (2025) "The Refusal to Conclude in AI Writing."

**Cross-skill references.**

- `synthesis-content-quality/SKILL.md`: section A2 summary and zone methodology.
- `synthesis-content-quality/references/detailed-criteria.md`: refreshed v3.1.0 criteria including criterion 27 (now promoted to this section).
- `synthesis-content-quality/references/model-family-fingerprints.md`: A1 model-family patterns.
- `synthesis-content-quality/references/combined-signal-fingerprints.md`: B2 combined-signal patterns.
- `synthesis-writing-pitfalls/SKILL.md`: universal human-source patterns.
- `synthesis-writing-craft/SKILL.md`: positive principles complementary to the negative patterns in this section.
- `synthesis-fact-checking/SKILL.md`: claim verification methodology that complements substance evaluation.

---

Part of the [synthesis writing](https://synthesiswriting.org) craft.
