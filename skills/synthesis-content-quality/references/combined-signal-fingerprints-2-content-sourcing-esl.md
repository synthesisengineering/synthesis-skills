# Combined-Signal Fingerprints (B2), part 2 of 2

Part 2 of the file split from [combined-signal-fingerprints.md](combined-signal-fingerprints.md), which keeps the opening sections and lists every part. The text below is unchanged.

Contents:
- Substantive-content combos (body-zone) (33 combos: B2-COMBO 004, 005, 006, 009, 013, 015, 016, 017, 022, 023, 035, 036, 038, 039, 040, 041, 042, 044, 045, 059, 064, 065, 066, 068, 069, 071, 072, 073, 074, 077, 078, 079, 080)
- Citation and sourcing combos (2 combos: B2-COMBO 007, 067)
- Markdown-leakage and wrapper-artifact combos (1 combo: B2-COMBO 012)
- Social-register combos (2 combos: B2-COMBO 031, 075)
- ESL safe-harbor (negative markers) (1 combo: B2-COMBO 010)
- Historical and era-tagged combos
- GPT-5-stripped combos
- Convergent clusters
- Cross-references
- Self-audit

## Substantive-content combos (body-zone)

Combos that identify body-zone substance and structure problems. These are the combos editors auditing artifact-only content should focus on most.

### B2-COMBO-004: Marketing copy AI signature

- **Constituent criteria.** #2 (promotional language) + #8 (marketing intensifiers) + #28 (generic insight in business voice).
- **Why combination is stronger.** Three independent marketing-register patterns plus generic-insight together signal AI-generated marketing copy rather than human marketing copy where one or two of these may appear naturally.
- **False-positive estimate.** Below 3 percent in non-marketing contexts; higher in actual marketing where humans produce similar density.
- **Primary model attribution.** GPT family in marketing-tuned products; Gemini consumer-facing tunes; Claude when given marketing-style prompts.
- **Concrete example.** A product-description response containing "transform your workflow" + "unlock unprecedented value" + "deliver excellence at scale".
- **Fix.** Cut the intensifiers, name what the product specifically does and the measurable outcomes.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Claude expansion. Related to ChatGPT B2-COMBO-064 (promotional pacing quadruple) and Manus AI B2-COMBO-079 (promotional brochure with emoji).

### B2-COMBO-005: LinkedIn AI post

- **Constituent criteria.** #5 (negative parallelism) + #1 (hyperbole) + #4 (participial phrases).
- **Why combination is stronger.** Three rhetorical patterns characteristic of AI LinkedIn writing; co-occurrence in a single post identifies AI generation.
- **False-positive estimate.** Below 5 percent in LinkedIn-style content (higher base rate of these patterns from human LinkedIn posters dilutes signal).
- **Primary model attribution.** All major frontier models when given a LinkedIn-style prompt.
- **Concrete example.** "Successful leaders don't manage time, they invest it. Always learning, constantly growing, never settling."
- **Fix.** Concrete, specific anecdote with a name and a number. Avoid aphorisms.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Claude expansion. Related to Perplexity B2-COMBO-031.

### B2-COMBO-006: Outline-mode default scaffold

- **Constituent criteria.** #17 (section labels) + #13 (bolding) + #12 (bulleted bolded lead-ins).
- **Why combination is stronger.** Three structural defaults applied to content that does not require structure (narrative, essay, conversational response) indicate the model is defaulting rather than serving the content.
- **False-positive estimate.** Below 2 percent in narrative or essay genres; higher in legitimate documentation.
- **Primary model attribution.** Claude and GPT both default to this in default deployments.
- **Concrete example.** A response with "## Background" header, "## Approach" header, each section having bolded subsection lead-ins and bulleted lists.
- **Fix.** Use prose for prose content. Headers belong in documentation, not essays.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Claude expansion.

### B2-COMBO-009: PubMed AI signature

- **Constituent criteria.** #33 (saturated vocabulary) + #9 (hedge intensifiers) + #6 (transition words).
- **Why combination is stronger.** Three independent patterns associated with academic AI assistance; co-occurrence in biomedical or academic abstracts is the empirical anchor for the 13.5 percent of 2024 biomedical abstracts processed with LLMs finding.
- **False-positive estimate.** Below 2 percent in non-academic contexts; higher in genuine academic writing (Liang ESL caveat applies).
- **Primary model attribution.** GPT family in academic-prompt outputs. Anchored by Kobak et al. arxiv 2406.07016.
- **Concrete example.** "We delve into the intricate dynamics that may underscore the importance of...; furthermore, this could potentially navigate the complexities of...; moreover, these findings might warrant additional investigation."
- **Fix.** Replace focal words; cut hedge density; replace transitions with logical connection.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Claude expansion.

### B2-COMBO-013: Article-as-tweet pattern

- **Constituent criteria.** #39 (social section labels) + #17 (section labels generally) + #28 (generic insight).
- **Why combination is stronger.** Social posts structured with explicit labels and section markers indicate AI structural defaults applied to an unstructured genre.
- **False-positive estimate.** Below 5 percent.
- **Primary model attribution.** GPT and Claude when given social-media prompts. Grok in some configurations.
- **Concrete example.** A "LinkedIn post" output structured with explicit "**Key insight:**" + "**Why this matters:**" + "**Action:**" labels.
- **Fix.** Social posts should read as posts, not as outlines. Remove labels.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Claude expansion.

### B2-COMBO-015: Outline rendered as poem

- **Constituent criteria.** #17 (section labels) + #13 (bolding) + uniformly short paragraph structure (A1-CLAUDE-008 variant).
- **Why combination is stronger.** Creative output should not have outline scaffold; when it does, the model is defaulting rather than serving the form.
- **False-positive estimate.** Below 5 percent.
- **Primary model attribution.** Claude when asked for "creative" output that the model interprets as needing structure. Per Walsh et al. CHR 2024.
- **Concrete example.** A "poem" output that consists of one-line bullets each starting with a bolded phrase.
- **Fix.** Creative output should not have outline scaffold. Strip the structure or rewrite without it.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Claude expansion.

### B2-COMBO-016: Consulting register

- **Constituent criteria.** #25 (industry slop) + #33 (saturated vocabulary) + #8 (marketing intensifiers).
- **Why combination is stronger.** Three independent corporate-register defaults in one response signal AI generation of consulting-style copy.
- **False-positive estimate.** Below 3 percent in non-consulting contexts; higher in genuine consulting where humans produce similar density.
- **Primary model attribution.** GPT family in business-prompt outputs.
- **Concrete example.** "To unlock value at scale, we leverage best-in-class methodology to navigate the complexities of digital transformation."
- **Fix.** Replace every word with a more specific or simpler alternative.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Claude expansion. Related to ChatGPT B2-COMBO-068 (business slop triple).

### B2-COMBO-017: Wikipedia paste

- **Constituent criteria.** #1 (hyperbole at low density) + #24 (vague attribution) + #4 (participial phrases).
- **Why combination is stronger.** Three independent patterns characteristic of Wikipedia-trained AI output. WikiProject AI Cleanup methodology documents this signature.
- **False-positive estimate.** Below 2 percent.
- **Primary model attribution.** Llama family especially (per A1-LLAMA-007). Models with heavy Wikipedia training corpus.
- **Concrete example.** "Often regarded as a foundational figure in the field, [Person Name] is widely considered to have made significant contributions to..."
- **Fix.** Replace with specific verifiable claims and named sources.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Claude expansion.

### B2-COMBO-022: List-and-summary sandwich

- **Constituent criteria.** #12 (bulleted bolded lead-ins) + #7 (mid-section summary) + #13 (bolding).
- **Why combination is stronger.** List structure followed by summary of the list creates redundancy; AI default is to do both.
- **False-positive estimate.** Below 3 percent in long-form output.
- **Primary model attribution.** GPT-4o (very high confidence); Claude family.
- **Concrete example.** A response with a bolded-lead-in list of 5 items, immediately followed by a sentence "In summary, these five considerations are interconnected and should be evaluated together."
- **Fix.** Either the list speaks for itself or the summary speaks for itself. Cut one.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Claude expansion.

### B2-COMBO-023: Code-comment overload

- **Constituent criteria.** Code outputs with comment density above 30 percent of line count, where comments restate what the code does rather than why.
- **Why combination is stronger.** AI defaults to over-commenting in tutorial-style; production code reveals this pattern.
- **False-positive estimate.** Below 5 percent in production code; higher in tutorial code where humans also over-comment.
- **Primary model attribution.** Llama family especially (per A1-LLAMA-005); also Claude and GPT in tutorial-prompt outputs.
- **Concrete example.** A function with one-line comments before every line, each comment restating what the line of code already says.
- **Fix.** Delete the restating comments. Keep comments that explain why (constraint, hidden assumption, design decision).
- **Zone.** BODY-PERSISTENT (the code is the body for code artifacts).
- **Era status.** Active.
- **Contributor.** Claude expansion.

### B2-COMBO-035: Section-Level Completion Template

- **Constituent criteria.** A1-CLAUDE-007 (Section-Capping Summary) + A1-CLAUDE-012 ("Underscores the Importance" Closer) + A2-SUB-001 (Deletion Test Failure on the closing sentence).
- **Why combination is stronger.** Every section ending with a summary that underscores importance and fails the deletion test means the entire document's section structure is pure scaffolding with no load-bearing content at any closing position.
- **False-positive estimate.** 6 to 9 percent.
- **Primary model attribution.** Claude (primary); GPT-4o (secondary).
- **Concrete example.** A long-form article with five sections, each closing on "This underscores the importance of [theme]" or similar.
- **Fix.** Cut the section closers. If a section needs a conclusion, the conclusion should be a specific claim, not a rhetorical close.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Perplexity.

### B2-COMBO-036: Motivational content

- **Constituent criteria.** A2-SUB-011 (Pseudo-profundity) + #39 (Motivational Platitude) + #38 (LinkedIn Hyperbole).
- **Why combination is stronger.** Three independent motivational-register markers indicate AI thought-leadership generation.
- **False-positive estimate.** Medium-low.
- **Primary model attribution.** All families when given motivational-content prompts.
- **Concrete example.** "Greatness isn't built in a day. It's forged in the quiet moments when no one is watching. The most successful leaders understand this truth deeply."
- **Fix.** Cut the aphorisms. Anchor in a specific person doing a specific thing.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Perplexity.

### B2-COMBO-038: Technical documentation AI

- **Constituent criteria.** A1-GPT-013 (Listicle Default) + A1-GPT-002 (Header Cascade) + A1-LLAMA-007 (Code-comment bleedthrough).
- **Why combination is stronger.** Three structural defaults from different families converging in technical documentation.
- **False-positive estimate.** Medium-low.
- **Primary model attribution.** Mixed (GPT and Llama, depending on the deployment).
- **Concrete example.** Documentation with five top-level headers, each opening to a bullet list, with code blocks heavily commented.
- **Fix.** Structural review: are the headers earning their place, or is this list-of-lists masquerading as documentation? Cut redundant comments.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Perplexity.

### B2-COMBO-039: Academic AI

- **Constituent criteria.** #16 (Passive voice) + #17 (Nominalization) + #28 (Hedged stats) + #29 (Vague attribution).
- **Why combination is stronger.** Four independent academic-register patterns co-occurring with hedge density and vague attribution. Distinct from the PubMed signature (B2-COMBO-009) in emphasizing nominalization and passive voice rather than focal vocabulary.
- **False-positive estimate.** Higher than other combos; some academic genres legitimately produce this. Apply with caution in academic contexts; ESL safe-harbor applies.
- **Primary model attribution.** GPT family in academic-prompt outputs.
- **Concrete example.** "Investigation of the phenomenon was conducted by means of a multifaceted approach. It is suggested by the data that further analysis may be warranted."
- **Fix.** Active voice. Specific nouns. Direct attribution. Replace hedging with confidence intervals or explicit uncertainty bounds.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Perplexity.

### B2-COMBO-040: Press release AI

- **Constituent criteria.** #14 (Hollow intensifiers) + A1-GPT-008 ("Robust"/"Innovative") + A1-GPT-003 ("Landscape"/"Ecosystem").
- **Why combination is stronger.** Three independent press-release patterns indicating AI generation.
- **False-positive estimate.** Lower than expected for press release register (humans produce these too) when all three markers are present at meaningful density.
- **Primary model attribution.** GPT family in business-content prompts.
- **Concrete example.** "Our truly innovative, industry-leading platform delivers robust solutions across the entire digital ecosystem."
- **Fix.** Cut every adjective without a specific claim attached. State what the product does, what it measurably delivers, and to whom.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Perplexity.

### B2-COMBO-041: Policy brief AI

- **Constituent criteria.** A2-SUB-008 (Survey-without-claim) + A2-SUB-010 (Both-sides) + #7 (Hedged claims without data).
- **Why combination is stronger.** Three independent refusal-avoidance markers in a policy context. Policy briefs are particularly vulnerable to AI's both-sides default.
- **False-positive estimate.** Higher than other refusal-avoidance combos because policy genre legitimately surveys positions.
- **Primary model attribution.** Claude family especially.
- **Concrete example.** A policy brief that lists positions A, B, and C in similar word counts and closes "the optimal approach depends on contextual factors."
- **Fix.** A policy brief should commit. If there is genuine uncertainty, name the data that would settle it and recommend a study.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Perplexity.

### B2-COMBO-042: Summary-of-nothing

- **Constituent criteria.** A2-SUB-012 (Conclusion-shaped non-conclusion) + A2-SUB-001 (Deletion failure) + A1-CLAUDE-012 ("Underscores the importance").
- **Why combination is stronger.** Three independent empty-content markers signal a paragraph that fails every substance test.
- **False-positive estimate.** Low.
- **Primary model attribution.** Claude family (A1-CLAUDE-012 anchor).
- **Concrete example.** "In conclusion, this examination of the topic underscores the importance of considering the various factors involved in the broader context."
- **Fix.** Cut the paragraph. If a conclusion is needed, write a specific claim.
- **Zone.** WRAPPER-CLOSER.
- **Era status.** Active.
- **Contributor.** Perplexity.

### B2-COMBO-044: Creative writing AI

- **Constituent criteria.** A2-SUB-009 (Generic insight) + A2-SUB-002 (Any-topic test failure) + #19 (Elevated vocabulary).
- **Why combination is stronger.** Three independent patterns indicating AI creative writing that fails the specificity and substance tests. Distinct from non-creative AI patterns because the elevated vocabulary in fiction or essay context reads as performance.
- **False-positive estimate.** Medium-low.
- **Primary model attribution.** All families when given creative-writing prompts.
- **Concrete example.** A "short story" output where the protagonist could be any protagonist, the setting could be any setting, and the prose uses elevated vocabulary without specific sensory anchor.
- **Fix.** Anchor in specific sensory detail. Name what only this character, this place, this moment could produce.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Perplexity.

### B2-COMBO-045: SEO content AI

- **Constituent criteria.** A2-SUB-004 (Novelty deficit) + A2-SUB-009 (Generic insight) + A1-GPT-009 (Transition cascade).
- **Why combination is stronger.** Three independent SEO-content patterns signal AI content-farm generation.
- **False-positive estimate.** Higher than other combos in SEO context (humans produce this too), but combined with the transition cascade lands at meaningful density.
- **Primary model attribution.** GPT family at scale.
- **Concrete example.** A "how to" article where each section opens with "Furthermore" or "Additionally," each paragraph offers a universally-applicable claim, and nothing in the article is novel relative to the top 100 articles on the same query.
- **Fix.** Identify what the article knows that the top 100 do not. If nothing, the article should not exist.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Perplexity.

### B2-COMBO-059: The Specificity Hallucination

- **Constituent criteria.** A2-SUB-003 (Specificity Void) + #19 (Citation Laundering).
- **Why combination is stronger.** The model provides a generic interchangeable claim but attaches a highly specific (and often fabricated) citation to it, attempting to validate the void.
- **False-positive estimate.** 2.0 percent.
- **Primary model attribution.** OpenAI GPT-5.4.
- **Concrete example.** "The company's commitment to customer satisfaction sets it apart (Smith et al., 2025)."
- **Fix.** Verify the citation. If absent, cut the citation. If present, the citation likely makes a more specific claim than the prose uses; restate the prose to match.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Gemini.

### B2-COMBO-064: Promotional pacing quadruple

- **Constituent criteria.** #1 (Symbol inflation) + #2 (Brochure language) + #28 (Hype subheads) + #29 (Dramatic fragments).
- **Why combination is stronger.** Together they mark synthetic promotional pacing across four independent registers.
- **False-positive estimate.** Very low.
- **Primary model attribution.** GPT, Gemini, SEO workflows.
- **Concrete example.** A product launch announcement that uses "stands as a testament to" symbolism, "rich heritage of innovation" brochure language, "The Revolutionary Future of X" subheading, and "Everything changed" dramatic fragments.
- **Fix.** Cut promotional adjectives. State what the product does and the measurable outcome.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** ChatGPT.

### B2-COMBO-065: Empty analysis triple

- **Constituent criteria.** #4 (Participial pseudo-analysis) + #27 (Shallow expertise) + A2-SUB-001 (Deletion-test failure).
- **Why combination is stronger.** Isolates empty analysis. Participial pseudo-analysis is the rhetorical envelope; shallow expertise is the substance failure; deletion test confirms the words are not load-bearing.
- **False-positive estimate.** Very low.
- **Primary model attribution.** Cross-family.
- **Concrete example.** "The company announced new initiatives, highlighting its commitment to innovation, with significant implications for the broader industry landscape."
- **Fix.** What specifically did the company announce, and what specifically does it imply? If those questions cannot be answered, the paragraph should be cut.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** ChatGPT.

### B2-COMBO-066: Templated discourse planning

- **Constituent criteria.** #6 (Mechanical transitions) + #7 (Section summaries) + #8 (Rule of three) + #10 (Uniform length).
- **Why combination is stronger.** Indicate templated discourse planning. Four independent structural defaults applied uniformly.
- **False-positive estimate.** Low.
- **Primary model attribution.** Older GPT, Gemini, generic blog AI.
- **Concrete example.** An article where each paragraph begins with a transition, each section closes with a summary, every list is exactly three items, and paragraph lengths cluster within 20 percent of mean.
- **Fix.** Vary all four dimensions deliberately. The structural uniformity is the signal; varied structure reads as human.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active but Declining.
- **Contributor.** ChatGPT.

### B2-COMBO-068: Business slop triple

- **Constituent criteria.** #25 (Industry clichés) + #26 (Lack of specificity) + A2-SUB-006 (Any-company survivability).
- **Why combination is stronger.** Classic business slop. The any-company test failure is the deepest substance failure; combined with industry clichés and lack of specificity, the content could appear in any company's blog without alteration.
- **False-positive estimate.** Very low.
- **Primary model attribution.** Business copy across all families.
- **Concrete example.** "In today's rapidly evolving business environment, organizations must continuously adapt to stay competitive. Strategic alignment between teams and leadership is essential for sustained success."
- **Fix.** Replace every interchangeable claim with one that names this company, this team, this competitor, this measurable outcome.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** ChatGPT.

### B2-COMBO-069: AI essay voice triple

- **Constituent criteria.** #33 (Saturated AI vocabulary) + #34 (Dead metaphors) + #35 (Moral coda).
- **Why combination is stronger.** Create the strongest "AI essay voice" package. Distinct from family-specific combos because it identifies the cross-family AI essay shape.
- **False-positive estimate.** Low.
- **Primary model attribution.** GPT, Claude, Gemini.
- **Concrete example.** "We must delve into the intricate tapestry of modern challenges. As we navigate this complex landscape, we have a responsibility to ensure that the path forward serves all stakeholders."
- **Fix.** Cut the focal words. Replace dead metaphors with specific claims. Cut the moral coda unless the topic genuinely requires moral commentary.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** ChatGPT.

### B2-COMBO-071: Generic help-content generation

- **Constituent criteria.** #12 (Bolded lead-ins) + #13 (Excessive formatting) + #17 (Title-case headers).
- **Why combination is stronger.** Marks generic help-center generation. Three structural defaults that the help-center genre rewards in human authors too, but at lower density.
- **False-positive estimate.** Medium-low.
- **Primary model attribution.** All family help-content prompts.
- **Concrete example.** A help-center article with "**How to do X**" + "**Why this matters**" + "**Common questions**" all bolded and title-cased.
- **Fix.** Calibrate against the publication's house style. If the publication is helpcenter.example.com and this is its house style, the combo signals adoption of AI defaults rather than human deviation.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** ChatGPT.

### B2-COMBO-072: Draft-stage synthetic assembly

- **Constituent criteria.** #18 (Placeholder residue) + #20 (Link problems) + #23 (Hallucinated sources).
- **Why combination is stronger.** Implies draft-stage synthetic assembly. Three independent unedited-output markers that should not co-exist in published content.
- **False-positive estimate.** Near-zero.
- **Primary model attribution.** Any workflow with copy-paste publishing.
- **Concrete example.** A published article containing "[INSERT QUOTE HERE]" + a broken URL + a citation that resolves to nothing.
- **Fix.** Revert to draft. The publishing workflow needs gatekeeping; this content should not have shipped.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** ChatGPT.

### B2-COMBO-073: Field-summary writing

- **Constituent criteria.** #30 (Canonical examples) + #27 (Superficial depth) + #3 (Meta-analysis).
- **Why combination is stronger.** Indicates field-summary writing instead of lived expertise. Canonical examples plus shallow analysis plus meta-commentary describes content where the writer summarizes a field rather than working in it.
- **False-positive estimate.** Low.
- **Primary model attribution.** Thought leadership and academic explainers.
- **Concrete example.** A "thought leadership" piece on systems thinking that opens with the Cynefin framework, references "the bus route that nobody rides," and never includes an example from the writer's own experience.
- **Fix.** Replace canonical examples with examples the writer has actually lived. If none exist, the writer should not be writing the article.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** ChatGPT.

### B2-COMBO-074: Private-material publication risk

- **Constituent criteria.** #31 (Scenario fingerprinting) + #32 (Operational decisions presented as case study) + #37 (Insider context collapse).
- **Why combination is stronger.** Flags private internal material publication risk. Three independent confidentiality-exposure patterns indicate the writer has reused internal context for external content without adequate transformation.
- **False-positive estimate.** Very low.
- **Primary model attribution.** Enterprise and product organizations whose AI-assisted drafting reuses internal scenarios.
- **Concrete example.** A "case study about a content platform used by journalists" where the writer "changed fourteen components" from "generate" to "draft," using internal directory paths and abstractions as if known to the reader.
- **Fix.** Apply the four-test protocol (Outsider, Insider, Adversary, Irony). The piece may not be publishable in its current form regardless of style edits.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** ChatGPT.

### B2-COMBO-077: Retrieval-citation mismatch

- **Constituent criteria.** A3-NEW-001 (Retrieval-citation mismatch) + #21 (Citation abnormality) + #23 (Hallucinated citations).
- **Why combination is stronger.** Separates retrieval failure from ordinary bad sourcing. A retrieval system that returns sources but the model citation does not match them is a different failure mode from pure hallucination.
- **False-positive estimate.** Very low.
- **Primary model attribution.** AI search, RAG, research assistants.
- **Concrete example.** A search-grounded response citing "Smith 2024" when the retrieved source is actually Jones 2023, plus broken citation formatting, plus an additional fabricated citation.
- **Fix.** Verify every citation against the actual source. If the retrieval system is unreliable, fix the retrieval system before publishing.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** ChatGPT.

### B2-COMBO-078: Manus AI essay-structure cluster

- **Constituent criteria.** "Undue Emphasis on Importance and Symbolism" (A3-1) + "Section-Ending Summaries" (A3-7) + "Overuse of Transition Words" (A3-6).
- **Why combination is stronger.** The combination of grandiose language, mechanical summarization, and stilted transitions creates a highly artificial essay-like structure that is rarely found in natural human writing.
- **False-positive estimate.** Low (compared to count-based heuristic).
- **Primary model attribution.** GPT (OpenAI), Claude (Anthropic).
- **Concrete example.** A blog post starting with "In today's dynamic landscape, the advent of AI stands as a testament to human ingenuity. Moreover, its profound implications cannot be overlooked... In conclusion, the aforementioned points underscore the transformative potential of artificial intelligence."
- **Fix.** Cut every element of grandiose framing. State the specific claim. Vary transitions.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Manus AI.

### B2-COMBO-079: Promotional brochure with emoji

- **Constituent criteria.** "Promotional and Travel Brochure Language" (A3-2) + "Emoji Usage in Inappropriate Contexts" (A3-14) + "Redundant Modifiers" (A3-NEW-008).
- **Why combination is stronger.** The blend of marketing jargon, misplaced emojis, and redundant adjectives creates a distinctly artificial and often overly enthusiastic tone, common in less refined AI outputs.
- **False-positive estimate.** Low.
- **Primary model attribution.** Gemini (Google), Grok (xAI).
- **Concrete example.** "Unlock the truly vibrant potential of our breathtaking new platform! It's an absolutely revolutionary breakthrough!"
- **Fix.** Cut every redundant modifier ("truly," "absolutely," "completely"). Cut the emoji if the register is formal. Replace promotional adjectives with the specific feature and the specific outcome.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Manus AI.

### B2-COMBO-080: Superficial-analytical participial cluster

- **Constituent criteria.** "Superficial Analysis with Participial Phrases" (A3-4) + "Over-reliance on Abstract Nouns" (A3-NEW-007) + "Hedging-as-Substance-Evasion" (A2-7).
- **Why combination is stronger.** Results in prose that sounds analytical and authoritative but lacks concrete meaning. The participial phrases add shallow commentary, abstract nouns obscure agency, and hedging avoids any firm claims.
- **False-positive estimate.** Medium-low.
- **Primary model attribution.** Claude (Anthropic), GPT (OpenAI), DeepSeek.
- **Concrete example.** "The company announced new policies, highlighting its commitment to sustainability, with the implementation of strategies aimed at optimization of resource utilization, which appears to suggest a positive trajectory."
- **Fix.** Active voice. Concrete nouns. Specific verbs. Direct claims.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Manus AI.

---

## Citation and sourcing combos

Combos that identify problems with sources, citations, and attribution. Cross-reference [`synthesis-fact-checking`](../../synthesis-fact-checking/SKILL.md) v2.0 for verification protocols.

### B2-COMBO-007: Fake-expertise stack

- **Constituent criteria.** #24 (vague attribution) + #23 (hallucinated citation) + A2-SUB-009 (generic insight).
- **Why combination is stronger.** Vague attribution wrapped around generic insight with hallucinated citation is a complete fake-expertise package that should not survive editorial review.
- **False-positive estimate.** Below 1 percent when the citation can be verified absent. Definitive when combined with citation that resolves to nothing.
- **Primary model attribution.** All families produce this; GPT and Claude at notable density.
- **Concrete example.** "Studies show that organizations with strong cultures outperform their peers by 30 percent (Smith and Jones, 2019), demonstrating the strategic importance of intentional culture-building."
- **Fix.** Remove the fabricated citation and the claim it supports. Re-source from verifiable evidence.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Claude expansion. Strong overlap with ChatGPT B2-COMBO-067.

### B2-COMBO-067: Source theater triple

- **Constituent criteria.** #21 (Citation abnormality) + #23 (Hallucinated references) + #24 (Unnamed authorities).
- **Why combination is stronger.** Signals source theater or fabricated research. Three independent citation-failure patterns in one piece is a strong signal of unverified sourcing.
- **False-positive estimate.** Very low.
- **Primary model attribution.** Retrieval-heavy workflows.
- **Concrete example.** "Research has shown that effective leadership drives organizational success (Multiple studies, 2020-2024). Studies suggest that employees value purpose-driven work over pay alone (Smith, 2023)."
- **Fix.** Verify every citation. Replace fabricated and unnamed sources with verified specific references.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** ChatGPT.

---

## Markdown-leakage and wrapper-artifact combos

### B2-COMBO-012: Markdown-leak combination

- **Constituent criteria.** #15 (markdown leakage) + #12 (bulleted bolded lead-ins) + #38 (social-side bolded lead-ins in posts).
- **Why combination is stronger.** Markdown literally rendering in a plain-text channel co-occurring with structural artifacts is near-deterministic for AI output.
- **False-positive estimate.** Below 1 percent in plain-text channels.
- **Primary model attribution.** Gemini family especially (per A1-GEMINI-001); GPT family in non-rendering channels.
- **Concrete example.** A plain-text Slack message that contains literal `**bold**` and `- bullet` markdown rendering as visible characters.
- **Fix.** Strip markdown for plain-text channels; render in channels that support it.
- **Zone.** BODY-PERSISTENT (the markdown appears inline in the body the AI produced).
- **Era status.** Active.
- **Contributor.** Claude expansion. Strong overlap with ChatGPT B2-COMBO-063.

---

## Social-register combos

Combos specific to social media posts (LinkedIn, Twitter/X, Threads, BlueSky, Reddit). The thresholds tighten in social register; some patterns that are LOW in articles become HIGH in social.

### B2-COMBO-031: LinkedIn AI Package

- **Constituent criteria.** #38 (LinkedIn Hyperbole) + A2-SUB-011 (Pseudo-Profundity) + A2-SUB-009 (Generic Insight) + A1-CLAUDE-001 (Transitional Cluster).
- **Why combination is stronger.** LinkedIn AI output has a recognizable voice: enthusiastic opener, pseudo-profound one-liner, generic insight, smooth transition to call to action. The combination is so widely recognized it has spawned entire sub-Reddit communities (r/linkedinlunatics).
- **False-positive estimate.** 4 to 6 percent.
- **Primary model attribution.** All (this is a genre-level signal more than a family signal).
- **Concrete example.** "Thrilled to share this exciting milestone! True leadership isn't about being in charge, it's about charging those around you. What lessons have you learned about trust? Comment below!"
- **Fix.** Cut the opener. Cut the aphorism. Anchor in a specific example. The CTA may stay if it earns the question.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Perplexity. Sources: r/linkedinlunatics community documentation, Shaib et al. 2025, BlogPros 2026.

### B2-COMBO-075: AI social-post signature

- **Constituent criteria.** #38 (Spec-language uppercase) + #39 (Article structure) + #42 (Social em-dashes).
- **Why combination is stronger.** A high-fidelity AI social-post signature. Three independent social-register failures co-occurring on a single post.
- **False-positive estimate.** Very low.
- **Primary model attribution.** LinkedIn, X, Threads outputs.
- **Concrete example.** A LinkedIn post structured with "**The Principle:**" + "**The Takeaway:**" labels, containing em-dashes and CRITICAL/HIGH severity labels lifted from a technical spec.
- **Fix.** Translate to conversational equivalents. First-person narration. Replace em-dashes with commas, parentheses, or sentence breaks. Strip the article structure.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** ChatGPT.

---

## ESL safe-harbor (negative markers)

The single most important calibration consideration in v4.0. Read this section in full.

### B2-COMBO-010: ESL false-positive trap (NEGATIVE marker)

- **Constituent criteria.** Uniform paragraph length (A1-CLAUDE-008) + restricted vocabulary range + heavy transition words (#6).
- **Status.** This is a **NEGATIVE marker**: when these three appear together in the absence of register-specific AI markers (focal-word cluster, em-dash density, system-prompt artifacts), the content is more likely to be non-native English human writing than AI.
- **Primary attribution.** ESL writers (Liang et al. 2023, `[verified-arxiv:2304.02819]`).
- **Concrete example.** A TOEFL-style essay with consistent 4-sentence paragraphs, vocabulary range under 1500 distinct words, transition openers on most paragraphs, and NO occurrence of "delve," "intricate," "navigate the complexities," or em-dashes.
- **Fix.** No fix needed. The system should be calibrated NOT to flag this combination as AI. Per Pangram's training methodology (arxiv 2402.14873), hard-negative-mining against this combination is essential.
- **Zone.** Applies in all zones; the safe-harbor is structural rather than zone-specific.
- **Era status.** Active and structural (this is a permanent calibration consideration).
- **Contributor.** Claude expansion.

### How to apply the ESL safe-harbor

Mechanical rule for v4.0:

1. **Cornerstone signature check.** Detect: uniform paragraph length plus restricted vocabulary plus heavy transitions.
2. **Register-specific marker check.** If cornerstone is present, look for at least one of: focal-word cluster (#33), em-dash density above 5 per 500 words (#11), system-prompt artifact (#19, including markdown leakage in plain-text channels), or chatbot reflex (#36 concierge tone, "I'd be happy to help" openers).
3. **Decision rule.** Cornerstone plus at least one register-specific marker: proceed with AI assessment. Cornerstone alone, no register-specific markers: do NOT flag as AI. Treat as non-native English human writing.
4. **Why this matters.** Per Liang et al. 2023, GPT detectors misclassify a large fraction of non-native English writing as AI-generated; documented misclassification rates of 50 to 70 percent on TOEFL essay corpus for several commercial detectors. The cornerstone signature is also the LLM signature; without the register-specific check, any methodology that uses the cornerstone alone is structurally biased.
5. **Pangram methodology.** Per arxiv 2402.14873 (cited but not independently verified at expansion time), Pangram achieved near-zero FP on TOEFL samples through hard-negative mining against this combination. The v4.0 system should replicate this calibration discipline.
6. **The safe-harbor is a primary structural constraint, not an exception.** Methodology that does not implement this discipline produces unacceptable false positives against an identifiable population of writers.

---

## Historical and era-tagged combos

Compounding-archive principle: patterns are never deleted from the catalog. Patterns trained out of current frontier models retain diagnostic value for older content. Combos with declining base rates carry era status; the methodology stays stable while the catalog refreshes.

**Historical family patterns** (retain diagnostic value for pre-2024 content): A1-GPT-HISTORICAL-001 ("As an AI language model" preamble; 15 to 25 percent in 2023, near-zero in 2026); A1-BARD-001 (Bard-era 91 percent hallucinated citations); A1-LLAMA-HISTORICAL-001 (pre-instruction-tuned Llama 1/2); A1-GROK-HISTORICAL-001 (Grok 1 register); A1-DEEPSEEK-HISTORICAL-001 (V1/V2 language-mixing, reduced in V3+); A1-MISTRAL-HISTORICAL-001 (pre-2024 EU-French effects); A1-QWEN-HISTORICAL-001 (Qwen 1/2). Full detail in [`historical-patterns.md`](historical-patterns.md).

**Active combos with declining base rates:** B2-COMBO-001 (declining post-GPT-5.1); B2-COMBO-019 (declining for GPT per anti-em-dash personalization); B2-COMBO-062 (reduced in later GPT/Gemini); B2-COMBO-066 (older GPT/Gemini characteristic); B2-COMBO-014 (declining for GPT-4o post April 2025 sycophancy rollback, still active for Claude); B2-COMBO-027 (reduced in GPT-4.1, further reduced in GPT-5).

---

## GPT-5-stripped combos

Combos that remain detectable in GPT-5 and GPT-5.1 output despite personalization changes that stripped obvious tells (em-dashes, concierge tone).

GPT-5.1's anti-em-dash personalization shifted Claude versus ChatGPT BR rankings by 30+ points within a single release. This is the empirical anchor for quarterly re-calibration. The personalization removed obvious style tells but did not address deeper structural defaults. Editors auditing GPT-5+ output should focus on substance combos rather than historical style combos.

**Key GPT-5-stripped combos:**

- **B2-COMBO-025:** Low em-dash density plus low concierge tone plus still-present focal vocabulary plus rule-of-three plus uniform paragraph length. Canonical entry.
- **B2-COMBO-029, B2-COMBO-076:** Substance evasion combos; work regardless of style personalization.
- **B2-COMBO-046, B2-COMBO-047:** Sycophantic pivot and formatted void; survive because the underlying behavior is RLHF-driven, not stylistic.

Per v4.0 calibration: quarterly frontier-output sampling is mandated; affected combos are re-tagged within 14 days of major releases. The compounding-archive principle keeps old combos with era updates rather than removing them.

---

## Convergent clusters

Six clusters where multiple Phase 1.5 contributors converged. Convergence is a robustness signal: when independent deep-research deliverables surface the same combination, the combination is unusually reliable.

1. **Em-dash plus transition plus uniform-length Claude cluster.** Five contributors: Claude expansion (B2-COMBO-003 + B2-COMBO-019), Perplexity (B2-COMBO-026), DeepSeek (B2-COMBO-083), Grok (B2-COMBO-062), partially ChatGPT. Strongest single-family fingerprint in current frontier output.
2. **Sycophantic opener plus caveat closer GPT-4o cluster.** Six contributors: Claude expansion (B2-COMBO-014 + B2-COMBO-021), Perplexity (B2-COMBO-027), DeepSeek (B2-COMBO-084), ChatGPT (B2-COMBO-070), Gemini (B2-COMBO-060), Manus AI (B2-COMBO-082). Strongest wrapper-zone fingerprint.
3. **Both-sides plus survey plus hedge Substance Evasion cluster.** Five contributors: Claude expansion (B2-COMBO-018), Perplexity (B2-COMBO-029), ChatGPT (B2-COMBO-076), Gemini (B2-COMBO-053), Manus AI (B2-COMBO-080). Most reliable substance-evasion fingerprint.
4. **Hallucinated citation plus vague attribution plus generic insight Fake Expertise cluster.** Four contributors: Claude expansion (B2-COMBO-007), ChatGPT (B2-COMBO-067 + B2-COMBO-077), Gemini (B2-COMBO-059), Perplexity (implicit in B2-COMBO-035). Most reliable citation-failure fingerprint.
5. **Markdown leak plus chatbot artifact Wrapper Leakage cluster.** Four contributors: Claude expansion (B2-COMBO-012), ChatGPT (B2-COMBO-063), Manus AI (B2-COMBO-082), Gemini (B2-COMBO-049). Definitive sign of unedited AI output.
6. **A2 substance/depth family dominated by RHF as primary cause.** All eight contributors agree. Reward modeling does not optimize for truth; it optimizes for what raters prefer; raters prefer well-organized empty content over substantive messy content. The fix lives in editing, not in choosing a different model.

---

## Cross-references

Constituent criteria resolve to [`detailed-criteria.md`](detailed-criteria.md) (42 v3.1.0 criteria), [`model-family-fingerprints.md`](model-family-fingerprints.md) (A1 family patterns), and [`substance-and-depth.md`](substance-and-depth.md) (A2 substance patterns). Calibration framework: [`calibration-tables.md`](calibration-tables.md). ESL safe-harbor and zone-conditional methodology: [`SKILL.md`](../SKILL.md). Historical/Deprecated combos: [`historical-patterns.md`](historical-patterns.md). Citation verification: [`synthesis-fact-checking`](../../synthesis-fact-checking/SKILL.md). Bibliography: [`bibliography.md`](bibliography.md).

---

## Self-audit

Em-dash count: zero. Recency floor: 2026-05. Compounding-archive principle: no combo deleted; historical combos retained with era status. Zone tagging: every combo carries an applicability tag. ESL safe-harbor: B2-COMBO-010 prominently called out as NEGATIVE marker.
