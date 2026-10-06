# Detailed Criteria Reference (v4.0), part 3 of 5

Part 3 of the file split from [detailed-criteria.md](detailed-criteria.md), which keeps the opening sections and lists every part. The text below is unchanged.

Contents:
- Section A3-CS: Citation and Sourcing (A3-CS-001 to A3-CS-006, 6 entries)
- Section A3-CX: Context-Specific (A3-CX-001 to A3-CX-005, 5 entries)
- Section A3-HD: Hyperbolic and Dramatic (A3-HD-001 to A3-HD-007, 7 entries)
- Section A3-CE: Confidentiality and Exposure (A3-CE-001 to A3-CE-002, 2 entries)

## Section A3-CS: Citation and Sourcing

### A3-CS-001: Hallucinated Citations

- **Description.** Fabricated sources, misattributed quotes, non-existent journal articles with plausible-sounding titles. Among the most dangerous AI content problems because the citations appear authoritative while spreading misinformation. Cross-references A3-TF-003 (broken or fabricated links), A3-TF-004 (citation abnormalities), and A3-CS-003 (retrieval-citation mismatch). See `synthesis-fact-checking` v2.0 for the full verification protocol.
- **Concrete examples.**
  1. Plausible-sounding but non-existent journal article title with fabricated authors.
  2. Real authors paired with a paper they did not write.
  3. (Per Walters and Wilder 2023) GPT-3.5 hallucinated citation rate of 30 to 55 percent in scientific writing prompts.
  4. (Per Chelli et al. 2024 JMIR) GPT-4o 56 percent citation error rate.
  5. (Per Stanford RegLab) Legal AI 17 to 33 percent hallucination rate even with RAG.
  6. (Per Damien Charlotin database) Over 1,455 sanctioned legal cases involving AI-fabricated citations as of 2025.
- **Location and register.** Body paragraphs. Densest in research-style, journalistic, legal, and policy prose.
- **Model attribution.** All families. Claude family particularly prone to DOI fabrication. GPT family prone to URL fabrication. Gemini prone to vague attribution. Bard (Historical, 2023) measured at 91 percent citation hallucination rate at launch.
- **Time evolution.** GPT-3.5 (Historical): 30 to 55 percent. GPT-4 (Historical): 18 to 29 percent. Bard (Historical): 91 percent. GPT-4o (current-era declining): 56 percent. Legal AI with RAG (current): 17 to 33 percent. Despite improvements, the criterion has not been solved.
- **Sources.** v3.1.0 criterion 23; Walters and Wilder (2023); Chelli et al. (2024); Stanford RegLab / Magesh et al. (2024); Damien Charlotin database (2025); `[chatgpt]`, `[deepseek]`, and `[claude-exec-2026-05-18]` all PROMOTE.
- **Signal strength.** HIGH.
- **Base rate.** See time-evolution measurements above.
- **Causal hypothesis (ranked).** Primary: training data quality for citation correctness is fundamentally weak. Secondary: generative defaults under benchmark pressure (the model would rather produce a plausible citation than admit ignorance). Tertiary: helpfulness optimization.
- **Detection difficulty.** Medium. Requires verifying each citation against the actual source.
- **False positive risk.** Very low when the citation is verified to not exist or to misattribute.
- **Fix or remediation.** Verify every citation before publication. Replace fabricated citations with real ones or remove the underlying claim.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-CS-002: Vague Attribution to Unnamed Authorities

- **Description.** Claims attributed to generic, unnamed sources: "Experts say," "Studies have shown," "Research indicates," "Analysts believe," "Industry leaders suggest." Distinct from A3-CS-001 (hallucinated citations) which fabricates specific sources; this is the broader pattern of unnamed appeal to authority. Cross-references A1-GEMINI-002 (the Gemini-characteristic "studies show" without identifiers) and A3-CS-006 (generic authority laundering).
- **Concrete examples.**
  1. "Experts say this approach is the most effective."
  2. "Studies have shown a strong correlation."
  3. "Research indicates significant improvement."
  4. "Analysts believe the trend will continue."
  5. "Industry leaders suggest this is the future of the field."
  6. (Per `[grok]`'s A3-NEW-033) "Recent studies have demonstrated..."
- **Location and register.** Body paragraphs. Densest in journalism, business writing, and policy prose.
- **Model attribution.** Gemini family (HIGH; cross-link to A1-GEMINI-002). Claude family (MEDIUM-HIGH). GPT family (MEDIUM-HIGH).
- **Time evolution.** Stable. Cross-family persistence per `[claude-exec-2026-05-18]`'s analysis.
- **Sources.** v3.1.0 criterion 24; `[claude-exec-2026-05-18]` PROMOTE; A1-GEMINI-002.
- **Signal strength.** HIGH (promoted from MED). Criterion now load-bearing for Gemini family attribution.
- **Base rate.** High in unedited AI output for argumentative or thesis-driven prompts.
- **Causal hypothesis (ranked).** Primary: training data exposure to journalistic and corporate prose where vague attribution is conventional. Secondary: helpfulness optimization (the model wants to support claims but lacks specific sources). Tertiary: generative defaults under benchmark pressure.
- **Detection difficulty.** Easy. Grep for the inventory ("experts say," "studies show," "research indicates").
- **False positive risk.** Moderate. Some legitimate journalism uses these phrases when specific attribution is unavailable; the discriminator is whether the writer could have provided specific attribution.
- **Fix or remediation.** Replace with specific attribution: name the experts, name the studies, link to the research. If specific attribution is not available, remove the claim or qualify it appropriately.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-CS-003: Retrieval-Citation Mismatch

- **Description.** A cited page exists, but it is a redirect, a copied version, or a syndicated source rather than the claimed original. This now appears often enough in AI search systems to deserve its own content-quality criterion as well as a fact-checking protocol. Per `[chatgpt]`'s A3-NEW-024. Cross-link to bucket C URL-rot vs hallucination protocol.
- **Concrete examples.**
  1. Citation links to a content aggregator's repost of a New York Times article, not to the original article.
  2. Citation links to a Wayback Machine archive when the original URL is alive but the model retrieved the archive.
  3. (Per `[chatgpt]`) Citation links to a syndicated press release on a third-party site rather than the company's original announcement.
  4. (Per `[opus-expansion]`) Citation links to a translated version on a different language site, where the translation introduces drift.
- **Location and register.** Citations in retrieval-augmented or search-grounded AI output.
- **Model attribution.** All retrieval-augmented systems (Perplexity AI, Claude with search, ChatGPT with browsing, Gemini with grounding).
- **Time evolution.** Active and growing as more retrieval-augmented systems deploy.
- **Sources.** `[chatgpt]`'s A3-NEW-024; cross-link to bucket C URL-rot vs hallucination protocol.
- **Signal strength.** MEDIUM-HIGH.
- **Base rate.** Moderate in retrieval-augmented output.
- **Causal hypothesis (ranked).** Primary: retrieval system returning a redirect or syndication target rather than the original. Secondary: model not verifying that the retrieved URL is the canonical source. Tertiary: training-data skew toward aggregator and syndication sites.
- **Detection difficulty.** Medium. Requires checking that the cited URL is the canonical original.
- **False positive risk.** Low when the mismatch is verified.
- **Fix or remediation.** Update the citation to the canonical original source. Verify retrieval-augmented citations resolve to the actual primary source.
- **Era status.** Active (growing).
- **Zone tag.** BODY-PERSISTENT.

---

### A3-CS-004: Source-Theater Abundance

- **Description.** Many sources are named or linked, but the prose never binds them to argument, mechanism, or judgment. The writer (or model) is performing the appearance of sourcing without engaging with the sources' content. Sibling to A2-SUB-014 (evidence displacement). Per `[chatgpt]`'s A3-NEW-027.
- **Concrete examples.**
  1. An article cites ten studies in a single paragraph without analyzing any of their findings or methodologies.
  2. Each paragraph closes with a citation, but the citations support claims that are too general to be informative.
  3. (Per `[chatgpt]`) A footer reference list of 30+ sources, but the body text engages with only two or three of them.
  4. (Per `[opus-expansion]`) Inline citations to authors who are named but whose specific contributions are not discussed.
- **Location and register.** Body paragraphs. Densest in research-style and academic-adjacent AI output.
- **Model attribution.** All families. Most pronounced in retrieval-augmented and academic-style prompts.
- **Time evolution.** Active and growing as retrieval-augmented systems scale.
- **Sources.** `[chatgpt]`'s A3-NEW-027.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate in research-style AI output.
- **Causal hypothesis (ranked).** Primary: training data exposure to citation-heavy academic prose. Secondary: helpfulness optimization (the model wants to demonstrate that it has done the research). Tertiary: generative defaults under benchmark pressure for citation density.
- **Detection difficulty.** Medium. Requires reading the citations and verifying they support the prose's argument.
- **False positive risk.** Moderate. Some legitimate academic writing has citation density without deep engagement; the discriminator is whether the writer engages with the cited content's substance.
- **Fix or remediation.** Cut citations that do not bind to argument or mechanism. Replace with engagement: name the specific contribution, analyze the methodology, contrast with other sources.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-CS-005: Synthetic-Source Contamination

- **Description.** The source itself is AI-generated or recursively derivative. This is no longer hypothetical given the scale of AI-authored web content. Per `[chatgpt]`'s A3-NEW-029. Cross-link to bucket C AI-generated synthetic sources protocol.
- **Concrete examples.**
  1. Article cites a "study" that turns out to be an AI-generated summary on a content farm.
  2. Article cites a "blog post" by an author who does not exist (LinkedIn profile is also AI-generated).
  3. (Per `[chatgpt]`) Citation to a "research report" by a "think tank" that has no human staff.
  4. (Per `[opus-expansion]`) Wikipedia citation traces to a paragraph that was added by an AI-edit (per WikiProject AI Cleanup observations).
- **Location and register.** Citations in any AI-augmented or AI-generated content.
- **Model attribution.** All families. The risk is in the source ecosystem, not the citing model.
- **Time evolution.** Active and rapidly growing. WikiProject AI Cleanup work documents the scale on Wikipedia specifically.
- **Sources.** `[chatgpt]`'s A3-NEW-029; WikiProject AI Cleanup methodology.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate and growing.
- **Causal hypothesis (ranked).** Primary: scale of AI-authored web content. Secondary: retrieval systems indexing AI-generated content without distinguishing it from human-authored content. Tertiary: content-farm SEO optimization.
- **Detection difficulty.** Hard. Requires investigating the source's provenance.
- **False positive risk.** Moderate. Some human-authored content is mistaken for AI-generated; the discriminator is documented provenance.
- **Fix or remediation.** Verify source provenance. Prefer sources with verifiable human authorship and editorial oversight.
- **Era status.** Active (rapidly growing).
- **Zone tag.** BODY-PERSISTENT.

---

### A3-CS-006: Generic Authority Laundering

- **Description.** Vague attribution to "leading experts" or "recent studies" used without traceable attribution. Sibling to v3.1.0 criterion 24 (A3-CS-002) and A1-GEMINI-002. Per `[grok]`'s A3-NEW-033. The distinction from A3-CS-002 is the specific framing of "leading," "top," "renowned," or "preeminent" experts and "groundbreaking," "landmark," or "comprehensive" studies, which adds an authority-laundering layer to the vague attribution.
- **Concrete examples.**
  1. "Leading experts in the field agree that..."
  2. "Top industry analysts have concluded that..."
  3. "A landmark study has shown that..."
  4. "Preeminent researchers have demonstrated..."
  5. (Per `[grok]`) "Renowned authorities have established that..."
- **Location and register.** Body paragraphs. Densest in argumentative, thought-leadership, and SEO-optimized content.
- **Model attribution.** All families. GPT-4o family (HIGH for this surface form). Gemini and Claude (MEDIUM).
- **Time evolution.** Stable.
- **Sources.** `[grok]`'s A3-NEW-033; cross-link to A3-CS-002.
- **Signal strength.** MEDIUM.
- **Base rate.** High in unedited AI output for thought-leadership or argumentative prompts.
- **Causal hypothesis (ranked).** Primary: training data exposure to SEO and thought-leadership content where authority laundering is conventional. Secondary: RLHF reward modeling that scores authority-claiming prose higher. Tertiary: helpfulness optimization.
- **Detection difficulty.** Easy. Grep for the inventory ("leading experts," "top analysts," "landmark study," "preeminent").
- **False positive risk.** Moderate. Some legitimate writing uses authority qualifiers; the discriminator is whether the authority is named.
- **Fix or remediation.** Replace with named attribution. "Leading experts" becomes the specific names; "landmark study" becomes the named study with year and journal.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.


---

## Section A3-CX: Context-Specific

### A3-CX-001: Industry-Specific Slop Patterns

- **Description.** Domain-characteristic AI patterns that recur across content in a given industry. Different domains show different default vocabularies. Per `[chatgpt]`'s REVISE and `[claude-exec-2026-05-18]`'s REVISE: split by genre in v4.0, especially technical docs, business copy, and social posts.
- **Concrete examples.** Examples are organized by industry domain because the slop inventory is domain-specific.

  **Technology writing.**
  - "Innovative," "cutting-edge," "revolutionary"
  - "Robust," "scalable," "flexible"
  - "Game-changing," "paradigm shift"
  - Buzzword clustering without substance

  **Travel and lifestyle.**
  - "Hidden gem," "off the beaten path"
  - "Picturesque," "charming," "quaint"
  - "Must-see destinations"
  - Generic itinerary patterns

  **Business and corporate.**
  - "Synergy," "leverage," "optimize"
  - "Strategic," "value-add," "best-in-class"
  - Mission statement language throughout

  **Product reviews.**
  - Uniformly positive tone
  - Generic praise without specific details
  - Comparison without actual product experience

  **AI thought leadership (new in v4.0).**
  - "Transformative AI," "AI-powered," "AI-native"
  - "The future of work," "the next frontier"
  - "Responsible AI," "ethical AI deployment"
  - "Human-in-the-loop," "AI-augmented workflow"

  **Healthcare and wellness (new in v4.0).**
  - "Holistic approach," "evidence-based"
  - "Personalized care," "patient-centered"
  - "Mind-body connection," "wellness journey"

- **Location and register.** Body paragraphs throughout. Strongest in trade publications, industry blogs, and SEO-optimized content.
- **Model attribution.** All families. The slop is industry-specific, not model-specific, because training data exposure to industry corpora is broadly similar across models.
- **Time evolution.** Vocabulary evolves with industry trends. AI-thought-leadership slop is new in 2024-2026; healthcare slop has been stable.
- **Sources.** v3.1.0 criterion 25; `[chatgpt]` REVISE; `[claude-exec-2026-05-18]` REVISE.
- **Signal strength.** MEDIUM.
- **Base rate.** High in unedited AI output for industry-specific prompts.
- **Causal hypothesis (ranked).** Primary: training data exposure to industry corpora. Secondary: RLHF reward modeling that scores "professional" or "domain-appropriate" output higher. Tertiary: helpfulness optimization that mimics the register of the industry.
- **Detection difficulty.** Easy with industry-specific grep lists.
- **False positive risk.** Moderate. Industry writers use industry vocabulary; the discriminator is the density and whether the vocabulary is functioning as substance or as filler.
- **Fix or remediation.** Replace buzzwords with concrete descriptions. "Cutting-edge technology" becomes the specific technical capability. "Holistic approach" becomes the specific scope and integration.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-CX-002: Lack of Personal Detail, Experience, or Specificity

- **Description.** Generic descriptions without specific examples, personal anecdotes, or experiential details. Humans who have experienced something provide specific sensory details, personal reactions, and concrete examples; AI generalizes. Cross-references A3-FA-001 (insider context collapse) which catches the opposite direction (writing too specific to the writer's frame for the reader to land on). Per `[claude-exec-2026-05-18]`'s PROMOTE: reliable across families.
- **Concrete examples.**
  1. AI: "The restaurant offers excellent service and a diverse menu featuring both traditional and innovative dishes."
  2. Human: "The waiter recommended the braised short rib after learning I don't eat seafood. The meat fell apart at the touch of my fork, and the red wine reduction had a subtle coffee undertone that lingered."
  3. AI: "The conference brought together leading thinkers from across the industry, fostering productive discussions and meaningful connections."
  4. Human: "Sarah pulled me aside during the coffee break to tell me her team had given up on the same architecture I was about to defend. We ended up rebuilding our slides together over lunch."
- **Location and register.** Body paragraphs. Strongest in feature, profile, and review writing.
- **Model attribution.** All families. Per `[claude-exec-2026-05-18]`: reliable across families.
- **Time evolution.** Stable. The pattern reflects a fundamental limit of LLMs without specific personal context.
- **Sources.** v3.1.0 criterion 26; `[claude-exec-2026-05-18]` PROMOTE; `[chatgpt]` notes expert documentation may legitimately omit personal detail.
- **Signal strength.** HIGH (promoted from MED) with caveat. The caveat: expert technical documentation may legitimately omit personal detail because the value is in the technical content, not the experiential context.
- **Base rate.** High in unedited AI output for feature, profile, or review prompts.
- **Causal hypothesis (ranked).** Primary: training data does not include the specific personal context the writer would have. Secondary: helpfulness optimization (the model produces a complete-sounding response with generalized content). Tertiary: RLHF reward modeling that scores polished generic prose higher than specific imperfect prose.
- **Detection difficulty.** Medium. Requires reading for specificity rather than spotting a phrase.
- **False positive risk.** Moderate. Some legitimate writing is appropriately generic; the discriminator is whether the genre warrants specifics and whether the writer could have provided them.
- **Fix or remediation.** Add specific sensory details, personal reactions, and concrete examples. Replace generic descriptors with specific ones.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-CX-003: Superficial Depth Without Expertise

- **Description.** Content covers a topic broadly without demonstrating actual understanding or expertise. Restates common knowledge without original insight; uses technical terms correctly but superficially; avoids controversial or nuanced aspects; provides "both sides" artificially balanced treatment; lacks specific examples, case studies, or detailed analysis. v4.0 promotes this criterion to section A2 (substance and depth detection) as a full top-level section with sub-patterns. This entry remains here as a pointer to the section.
- **Sub-patterns (now in A2).**
  - A2-SUB-001: The deletion test (does removing the sentence change the meaning?)
  - A2-SUB-002: The specificity test (could this sentence be true of any company in any era?)
  - A2-SUB-003: Load-bearing claim count per paragraph
  - A2-SUB-004: Novelty signal (does this say something that requires expertise?)
  - A2-SUB-005: Insight-to-word ratio
  - A2-SUB-006: The any-company test (the PR Daily 2026 AI comparison drill)
  - A2-SUB-007: Hedging as substance evasion
  - A2-SUB-008: Survey-without-claim pattern
  - A2-SUB-009: Generic insight
  - A2-SUB-010: Both-sides-without-position
  - A2-SUB-011: Pseudo-profundity (anchored in Pennycook et al. 2015)
  - A2-SUB-012: Conclusion-shaped paragraphs that do not conclude
  - A2-SUB-013: Frictionless-transition padding
  - A2-SUB-014: Evidence displacement
  - A2-SUB-015: So-What test
- **Sources.** v3.1.0 criterion 27; unanimous PROMOTE-to-section across all seven LLMs in unified bucket A; Hicks et al. (2024) "ChatGPT is bullshit" (Frankfurt-style indifference-to-truth analysis); Pennycook et al. (2015); Frankfurt (2005).
- **Signal strength.** HIGH.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.
- **Note.** Full pattern entries for the A2 sub-patterns live in `references/substance-and-depth.md`. This entry exists in the catalog for navigation only.

---

### A3-CX-004: Over-Generalization from Limited Data

- **Description.** Drawing broad conclusions or making sweeping statements based on a small number of examples, limited studies, or anecdotal evidence, without acknowledging the limitations. Per `[manus-ai]`'s A3-NEW-004.
- **Concrete examples.**
  1. (Per `[manus-ai]`) "A recent study of 50 individuals showed significant improvement, proving that this treatment is universally effective."
  2. (Per `[manus-ai]`) "My friend tried this diet and lost weight, so it's clearly the best approach for everyone."
  3. (Per `[manus-ai]`) "Because two companies in a specific niche adopted this strategy, it is now a universal best practice for the entire industry."
  4. (Per `[opus-expansion]`) "Survey data from 100 respondents demonstrates a clear consumer preference for X."
- **Location and register.** Body paragraphs. Densest in opinion, analysis, advocacy, and persuasive writing.
- **Model attribution.** All families. Most pronounced when prompted for persuasive or thesis-driven content.
- **Time evolution.** Stable. The pattern reflects training-data exposure to opinion journalism and marketing prose.
- **Sources.** `[manus-ai]`'s A3-NEW-004; Kahneman (2011); Gigerenzer (2007).
- **Signal strength.** HIGH.
- **Base rate.** Moderate to high in unedited AI output for opinion or persuasive prompts.
- **Causal hypothesis (ranked).** Primary: training data exposure to opinion-style writing that overgeneralizes. Secondary: RLHF reward modeling for confident-sounding claims. Tertiary: helpfulness optimization (the model produces a definitive-sounding answer rather than a nuanced one).
- **Detection difficulty.** Medium. Requires checking whether the cited evidence supports the breadth of the claim.
- **False positive risk.** Low when the overgeneralization is verifiable.
- **Fix or remediation.** Acknowledge the limitations of the evidence. Replace sweeping claims with claims appropriately scoped to what the evidence supports.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-CX-005: Unnecessary Historical Context and "Once Upon a Time" Openers

- **Description.** Starting an article or section with overly broad, generic historical context that is not directly relevant or necessary for the main topic, often using phrases like "From the dawn of time...," "Since ancient civilizations...," "Throughout history...," "As long as commerce has existed." The historical opener provides zero novel information to a well-informed reader. Per `[manus-ai]`'s A3-NEW-005 and `[gemini]`'s A2-SUB-007.
- **Concrete examples.**
  1. (Per `[manus-ai]`) "From the dawn of civilization, humans have sought to understand the mysteries of the universe, a quest that continues to this day with the advent of quantum computing."
  2. (Per `[manus-ai]`) "Since ancient times, storytelling has been a fundamental aspect of human culture, a tradition that now finds new expression in the digital age with AI-generated narratives."
  3. (Per `[gemini]`) "Since the dawn of the internet, companies have struggled with cybersecurity."
  4. (Per `[gemini]`) "Throughout history, technological innovation has consistently disrupted traditional markets."
  5. (Per `[gemini]`) "As long as commerce has existed, supply and demand have dictated pricing structures."
- **Location and register.** Article openers. Universal across registers, densest in introductions, essays, and general informational content.
- **Model attribution.** GPT family (HIGH). Claude family (MEDIUM-HIGH). Gemini (MEDIUM).
- **Time evolution.** Stable. Reflects training-data heavy on high school and undergraduate essay structures.
- **Sources.** `[manus-ai]`'s A3-NEW-005; `[gemini]`'s A2-SUB-007; Pinker (2014); Strunk and White (2000).
- **Signal strength.** HIGH.
- **Base rate.** Per `[gemini]`: 35 percent of zero-shot essay prompts.
- **Causal hypothesis (ranked).** Primary: training data heavily weighted toward high school and undergraduate essay structures. Secondary: helpfulness optimization (the model provides "context" even when the reader does not need it). Tertiary: RLHF reward modeling for "well-grounded" openings.
- **Detection difficulty.** Easy.
- **False positive risk.** Low to moderate.
- **Fix or remediation.** Remove the historical context if it is not load-bearing for the main argument. Start directly with the topic at hand.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER (when at the very start) and BODY-PERSISTENT (when used as a section opener).


---

## Section A3-HD: Hyperbolic and Dramatic

### A3-HD-001: Hyperbolic Subheadings and Section Titles

- **Description.** Subheadings that inflate the significance of the section's content rather than describing it. LLMs optimize for engagement by default, producing subheadings that advertise rather than describe. Per `[gemini]`'s category-level DEMOTE for groups 28-32: contradicted by the genre-specific persistence in SEO and social-optimized generative copy.
- **Concrete examples.**
  1. "The word that changed everything"
  2. "A game-changing approach to X"
  3. "The revolutionary insight"
  4. "Why X will never be the same"
  5. "The surprising truth about X"
  6. "What nobody tells you about X"
  7. (Per `[chatgpt]`) "The one mistake that could ruin your strategy"
  8. (Per `[opus-expansion]`) "The hidden cost of X that experts won't tell you"
- **Location and register.** Section headers and subheaders. Densest in SEO content, business blogs, listicles, and self-help writing.
- **Model attribution.** GPT family (HIGH). Claude family (MEDIUM-HIGH). Gemini (MEDIUM).
- **Time evolution.** Stable. Reflects training-data exposure to SEO and engagement-optimized content.
- **Sources.** v3.1.0 criterion 28; `[cross-validated:manus-ai+perplexity+chatgpt]`.
- **Signal strength.** MEDIUM.
- **Base rate.** High in unedited AI output for blog or article prompts. Moderate in technical or analytical writing.
- **Causal hypothesis (ranked).** Primary: training data exposure to SEO and engagement-optimized content. Secondary: RLHF reward modeling that scores "compelling" headlines higher. Tertiary: helpfulness optimization (the model assumes the reader wants engagement).
- **Detection difficulty.** Easy. Visual scan of headers.
- **False positive risk.** Low. The pattern is distinctive.
- **Fix or remediation.** Subheadings should describe what the section contains. "The structural blind spot in test suites" tells the reader what they will read. "The gap nobody talks about" tells the reader nothing except that the writer thinks they have discovered something important.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-HD-002: Dramatic Fragment Construction

- **Description.** Short dramatic sentences or fragments used for artificial emphasis, creating theatrical pacing. One or two dramatic fragments per article is a legitimate rhetorical device; a pattern of them (especially at section boundaries) is AI-style pacing that substitutes theatrics for substance.
- **Concrete examples.**
  1. "And it was a disaster."
  2. "Everything changed."
  3. "The results were stunning."
  4. "But there was a problem."
  5. "That's when it clicked."
  6. (Per `[chatgpt]`) "And then it happened."
- **Location and register.** Section boundaries and dramatic-pacing moments. Densest in narrative-driven content, profile writing, and storytelling-heavy business prose.
- **Model attribution.** All families. GPT family (HIGH for storytelling prompts). Claude family (MEDIUM-HIGH).
- **Time evolution.** Stable.
- **Sources.** v3.1.0 criterion 29; `[cross-validated:manus-ai+perplexity+chatgpt]`.
- **Signal strength.** MEDIUM. Useful when clustered with hyperbolic subheadings (A3-HD-001) and moral cadence (A3-BT-003).
- **Base rate.** Moderate in narrative AI output.
- **Causal hypothesis (ranked).** Primary: training data exposure to narrative-driven and dramatic prose. Secondary: RLHF reward modeling that scores "compelling" pacing higher. Tertiary: helpfulness optimization that adds dramatic beats.
- **Detection difficulty.** Easy. Pattern visible across section boundaries.
- **False positive risk.** Moderate. Skilled writers use dramatic fragments deliberately; the discriminator is density and mechanical placement at section boundaries.
- **Fix or remediation.** Let content create impact through specificity and evidence. "Revenue dropped 40 percent in six weeks" has more impact than "And then everything changed."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-HD-003: Borrowed Canonical Examples

- **Description.** Using the same illustrative examples that appear in every article on a topic. These examples are over-represented in training data because they appear in thousands of articles. A writer who uses them is summarizing a field; a writer who works in the field has their own examples drawn from their own experience. Per `[chatgpt]`'s REVISE: stronger than before in AI thought-leadership content; expand examples beyond design-thinking canon into AI ethics and product strategy canons.
- **Concrete examples.**
  1. "A jet engine is complicated; a market is complex." (Cynefin framework)
  2. "The bus route that nobody rides." (design thinking)
  3. "The restaurant with great food but no customers." (marketing or systems thinking)
  4. "The boiling frog." (change management)
  5. "The Swiss cheese model." (error prevention)
  6. (New in v4.0 per `[chatgpt]`) "The paperclip maximizer." (AI safety)
  7. (New in v4.0) "The trolley problem." (AI ethics)
  8. (New in v4.0) "Goodhart's law in practice." (metrics gaming)
  9. (New in v4.0) "The bike-shedding effect." (organizational decision-making)
- **Location and register.** Body paragraphs throughout. Densest in thought-leadership, business strategy, design thinking, and AI ethics content.
- **Model attribution.** All families. Claude family particularly likely to use these examples per `[claude-exec-2026-05-18]`.
- **Time evolution.** Stable inventory, growing with new canons (AI ethics, product strategy).
- **Sources.** v3.1.0 criterion 30; `[chatgpt]` REVISE.
- **Signal strength.** MEDIUM.
- **Base rate.** High in unedited AI thought-leadership content.
- **Causal hypothesis (ranked).** Primary: training data over-representation of these examples. Secondary: helpfulness optimization (the model reaches for the most-cited example as the "safe" choice).
- **Detection difficulty.** Easy with a list of known canonical examples.
- **False positive risk.** Moderate. Some writers use these examples deliberately as common reference points; the discriminator is whether the writer adds their own analysis or just repeats the canonical framing.
- **Fix or remediation.** Replace borrowed examples with original ones from your own work or construct novel examples that illustrate the same principle.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-HD-004: Unwarranted Optimism or Pessimism

- **Description.** Content that expresses an extreme degree of optimism or pessimism about a topic without sufficient evidence or balanced consideration of risks and benefits. Per `[manus-ai]`'s A3-NEW-001.
- **Concrete examples.**
  1. (Per `[manus-ai]`) "This new technology will unequivocally solve all of humanity's energy problems." (Unwarranted optimism.)
  2. (Per `[manus-ai]`) "The future of the industry is bleak, with no hope for recovery or innovation." (Unwarranted pessimism.)
  3. (Per `[manus-ai]`) "Our groundbreaking product is guaranteed to deliver unprecedented results and transform your business overnight."
  4. (Per `[opus-expansion]`) "By 2030, AI will have eliminated 40 percent of all knowledge work."
- **Location and register.** Body paragraphs. Densest in marketing, trend analysis, speculative articles, and opinion pieces.
- **Model attribution.** All families. Most pronounced when prompted for future outlooks or persuasive content.
- **Time evolution.** Stable.
- **Sources.** `[manus-ai]`'s A3-NEW-001; O'Neil (2016); Zuboff (2019).
- **Signal strength.** HIGH.
- **Base rate.** Medium in unedited AI output. Higher when prompted for persuasive or future-oriented content.
- **Causal hypothesis (ranked).** Primary: training data skew (models learn from highly polarized or marketing-driven content). Secondary: helpfulness optimization (models aim to provide a clear, albeit extreme, stance).
- **Detection difficulty.** Medium. Requires evaluating the balance and evidence supporting the emotional tone.
- **False positive risk.** Medium. Human writers can also be overly optimistic or pessimistic, but usually with more nuanced reasoning.
- **Fix or remediation.** Demand a balanced perspective, evidence for claims, and a discussion of potential downsides or alternative scenarios.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-HD-005: Over-Reliance on Analogies and Metaphors

- **Description.** Excessive use of analogies, metaphors, or similes that, while sometimes illustrative, become convoluted, obscure meaning, or feel forced. Per `[manus-ai]`'s A3-NEW-002. Distinct from A3-BT-002 (exhausted metaphors as structural filler) which catches specific dead metaphors; this is the broader pattern of overusing analogy as an explanation strategy.
- **Concrete examples.**
  1. (Per `[manus-ai]`) "The blockchain is like a digital ledger, a distributed database, a cryptographic chain, and a decentralized network, all woven into a tapestry of innovation." (Too many overlapping metaphors.)
  2. (Per `[manus-ai]`) "Our new software is the North Star guiding your business through the stormy seas of the market, a beacon of hope in the digital wilderness."
  3. (Per `[manus-ai]`) "The human brain is a complex supercomputer, a vast library, a bustling city, and a delicate ecosystem, all working in concert."
- **Location and register.** Body paragraphs. Densest in explanatory articles, educational content, creative writing, and marketing materials.
- **Model attribution.** Claude family (HIGH per `[manus-ai]`). Gemini family (HIGH).
- **Time evolution.** Stable.
- **Sources.** `[manus-ai]`'s A3-NEW-002; Lakoff and Johnson (1980); Gentner and Markman (1997).
- **Signal strength.** MEDIUM.
- **Base rate.** Medium.
- **Causal hypothesis (ranked).** Primary: training data skew (models learn from texts rich in rhetorical devices). Secondary: helpfulness optimization (models try to make complex topics accessible).
- **Detection difficulty.** Easy to medium.
- **False positive risk.** Medium.
- **Fix or remediation.** Demand clarity and conciseness. Reduce the number of analogies or refine them for greater impact.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-HD-006: The "Journey" Metaphor Overuse

- **Description.** The pervasive and often cliched use of the "journey" metaphor to describe processes, experiences, or transformations, particularly in business or personal development contexts. Sibling to A3-BT-002 (exhausted metaphors as structural filler) but elevated to its own entry because the "journey" metaphor is uniquely persistent across families and uniquely overused. Per `[manus-ai]`'s A3-NEW-009.
- **Concrete examples.**
  1. (Per `[manus-ai]`) "Our customers embark on a digital transformation journey with us."
  2. (Per `[manus-ai]`) "The product development journey was fraught with challenges, but ultimately rewarding."
  3. (Per `[manus-ai]`) "Your personal growth journey begins today."
  4. (Per `[opus-expansion]`) "We are at the beginning of an AI journey that will reshape every industry."
- **Location and register.** Body paragraphs and section openers. Densest in business strategy, personal development, marketing, and consulting prose.
- **Model attribution.** All families. GPT family (HIGH for marketing prompts). Claude family (HIGH for business strategy).
- **Time evolution.** Stable. The journey metaphor has been a fixture of business writing for decades and is heavily represented in training data.
- **Sources.** `[manus-ai]`'s A3-NEW-009; Lakoff and Johnson (1980); Pinker (2014).
- **Signal strength.** HIGH.
- **Base rate.** High in unedited AI output for business and personal-development prompts.
- **Causal hypothesis (ranked).** Primary: training data exposure to business and self-help corpora where the metaphor is canonical. Secondary: RLHF reward modeling for "compelling" framing. Tertiary: helpfulness optimization.
- **Detection difficulty.** Easy. Grep for "journey."
- **False positive risk.** Moderate. Some legitimate writing uses "journey" as a domain-appropriate metaphor; the discriminator is whether the metaphor adds meaning or is a placeholder.
- **Fix or remediation.** Replace with specific process language. "Digital transformation journey" becomes "digital transformation initiative" or, better, the specific changes the initiative involves.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-HD-007: Uncritical Use of "Synergy" and "Holistic"

- **Description.** Deployment of buzzwords like "synergy" and "holistic" without clear definition, specific application, or genuine meaning, often to create an impression of sophistication or comprehensiveness. Sibling to A3-BT-001 (saturated AI vocabulary) but elevated because "synergy" and "holistic" specifically are over-represented and rarely carry concrete meaning. Per `[manus-ai]`'s A3-NEW-010.
- **Concrete examples.**
  1. (Per `[manus-ai]`) "Our team fosters synergy to achieve holistic solutions."
  2. (Per `[manus-ai]`) "We believe in a holistic approach to customer engagement, creating synergistic opportunities."
  3. (Per `[manus-ai]`) "The new strategy promotes cross-functional synergy for a holistic impact."
  4. (Per `[deepseek]`) "A synergistic blend of capabilities for a holistic transformation."
- **Location and register.** Body paragraphs. Densest in corporate, consulting, and business strategy prose.
- **Model attribution.** All families. GPT-4o family (HIGH for corporate prompts). Claude family (MEDIUM-HIGH).
- **Time evolution.** Stable.
- **Sources.** `[manus-ai]`'s A3-NEW-010; Pinker (2014); Strunk and White (2000).
- **Signal strength.** HIGH.
- **Base rate.** High in unedited AI corporate content.
- **Causal hypothesis (ranked).** Primary: training data exposure to corporate prose. Secondary: RLHF reward modeling for "professional" output.
- **Detection difficulty.** Easy. Grep for "synergy" and "holistic."
- **False positive risk.** Low. The terms are nearly always functioning as buzzwords rather than as meaningful descriptors.
- **Fix or remediation.** Replace with specific descriptions. "Cross-functional synergy" becomes the specific cross-functional behaviors. "Holistic approach" becomes the specific scope and integration.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.


---

## Section A3-CE: Confidentiality and Exposure

### A3-CE-001: Scenario Fingerprinting in "Anonymized" Examples

- **Description.** Removing company names while keeping the scenario, specific numbers, stakeholder dynamics, vocabulary, and industry context. The scenario IS the identifier; names are the least important part. A story about "a content platform used by journalists" where you "changed fourteen components from 'generate' to 'draft'" is identifiable to anyone who knows the author's work. Cross-references A3-CE-002 (operational decisions presented as teaching material).
- **Concrete examples.**
  1. "A content platform used by journalists" where the author publicly works at one of two such platforms.
  2. "We changed fourteen components from 'generate' to 'draft'" where the specific count plus the vocabulary change is a fingerprint.
  3. "Six engineers in a Slack channel" where the team size plus the channel-name pattern is identifiable.
  4. (Per `[claude-exec-2026-05-18]`) "A Fortune 500 media company restructured its newsroom AI strategy" where the combination of size, industry, and decision narrows to a small set.
- **Location and register.** Body paragraphs in case-study, lessons-learned, and thought-leadership content.
- **Model attribution.** All families. The pattern is not model-attributable per se; it arises from how the writer constructs examples, but LLMs assisting in drafting can amplify the pattern by retrieving plausible specific details that turn out to be fingerprinting.
- **Time evolution.** Stable. The risk grows with the writer's public visibility.
- **Sources.** v3.1.0 criterion 31; the four-test protocol below.
- **Signal strength.** HIGH.
- **Base rate.** Variable. Higher when the writer has substantial public work that creates a context for re-identification.
- **Causal hypothesis (ranked).** Primary: writer-side construction error (the writer assumes name removal is sufficient). Secondary: helpfulness optimization when LLM assists drafting (the model fills in plausible specifics that turn out to be fingerprinting).
- **Detection difficulty.** Hard. Requires the four-test protocol below applied with knowledge of the writer's other work.
- **False positive risk.** Moderate. Some genuinely transformable examples will be flagged conservatively; the discriminator is whether any single test fails.
- **Fix or remediation.** Apply the four-test protocol before using any real example.
  1. **Outsider test.** Could a stranger narrow this to a small set of companies or situations?
  2. **Insider test.** Does this confirm something an insider suspected but could not prove?
  3. **Adversary test.** Could a reporter or competitor use this as evidence or ammunition?
  4. **Irony test.** Does publishing this example undermine the very thing the example describes protecting?
  If ANY test fails, the example cannot be used regardless of whether names are removed. Transform the scenario, not just redact the names. Change the industry, the stakeholder type, the numbers, and the vocabulary simultaneously.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-CE-002: Operational Decisions Presented as Teaching Material

- **Description.** Internal product strategy decisions, risk mitigation choices, and private operational changes described as case studies, even without names. If the decision was made to manage risk, describing it publicly re-creates the risk. Cross-references A3-CE-001 (scenario fingerprinting).
- **Concrete examples.**
  1. An article about careful language choices that reveals you made those choices is self-defeating.
  2. A case study about restructuring a team to manage internal politics reveals the politics it was designed to manage.
  3. (Per `[claude-exec-2026-05-18]`) A blog post about how you "soft-launched" a feature to avoid stakeholder pushback reveals the stakeholder pushback that was the constraint.
  4. (Per `[opus-expansion]`) A talk about how you "deprioritized" a project for political reasons exposes the political constraint.
- **Location and register.** Body paragraphs in case-study, lessons-learned, leadership, and thought-leadership content.
- **Model attribution.** Not model-attributable. The pattern is in the writer's construction.
- **Time evolution.** Stable.
- **Sources.** v3.1.0 criterion 32.
- **Signal strength.** HIGH.
- **Base rate.** Variable.
- **Causal hypothesis (ranked).** Primary: writer-side construction error (the writer separates the operational lesson from the operational context that motivated the lesson). Secondary: helpfulness optimization (the LLM extracts a teachable pattern without flagging that the pattern is the confidentiality issue).
- **Detection difficulty.** Hard. Requires checking whether the published lesson re-creates the risk that motivated the lesson.
- **False positive risk.** Moderate.
- **Fix or remediation.** Use genuinely universal patterns, publicly known examples from other companies (with attribution), fictional scenarios clearly marked as illustrative, or the author's personal methodology (which is already public). If the specifics of the decision are what makes the example valuable, the example is too specific to publish safely.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.


---
