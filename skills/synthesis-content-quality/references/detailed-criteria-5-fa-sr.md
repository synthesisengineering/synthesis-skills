# Detailed Criteria Reference (v4.0), part 5 of 5

Part 5 of the file split from [detailed-criteria.md](detailed-criteria.md), which keeps the opening sections and lists every part. The text below is unchanged.

Contents:
- Section A3-FA: Frame and Audience (A3-FA-001 to A3-FA-011, 11 entries)
- Section A3-SR: Social-register (A3-SR-001 to A3-SR-005, 5 entries)
- Cross-file dependencies
- Cross-skill dependencies
- End of catalog

## Section A3-FA: Frame and Audience

### A3-FA-001: Insider Context Collapse

- **Description.** Right vocabulary deployed in a frame the reader does not share. The article references tools, abstractions, version numbers, code identifiers, internal events, or internal directories as if the reader has the writer's project context. Distinct from A3-CX-002 (lack of personal detail) which catches the OPPOSITE direction (writing too generic to convey expertise). Insider context collapse is writing too specific to the writer's frame for the reader to land on. The grammar is clean; the saturated AI vocabulary is absent; the meaning is private. Per `[chatgpt]`'s PROMOTE and `[deepseek]`'s synergistically-PROMOTE.
- **Concrete examples.**
  1. Tool or project names introduced without inline definition: "synthesis-console v0.8.0"
  2. Internal abstractions used as if known: "the cockpit's NEEDS YOU region," "the parser"
  3. Version numbers in prose: "v0.8.3 to v0.8.5"
  4. Code identifiers in prose without descriptive context (function names, class names, file paths).
  5. References to internal events: "another session reviewing the code," "the X arc."
  6. Internal directories or paths used as if the reader knows the project layout.
  7. (Per `[chatgpt]`) Agentic environments where the model speaks from a private frame: "I will now invoke the database update function" without explaining what database or what update.
- **Location and register.** Body paragraphs throughout. Strongest in technical, teaching, and how-to writing.
- **Model attribution.** All families. Most pronounced in agentic and connector-rich environments where the model has private context not shared with the reader.
- **Time evolution.** Active and growing per `[chatgpt]`'s analysis: strongly relevant in agentic and connector-rich environments where models speak from a private frame without realizing it.
- **Sources.** v3.1.0 criterion 37; `[chatgpt]` PROMOTE; `[deepseek]` PROMOTE; cross-link to synthesis-reader-briefing skill.
- **Signal strength.** HIGH (promoted from MED).
- **Base rate.** Moderate to high in unedited AI output that draws on private context (agentic environments, RAG with internal documents).
- **Causal hypothesis (ranked).** Primary: helpfulness optimization without reader-context tracking. Secondary: training data exposure to inside-team communications. Tertiary: system prompt artifacts that inject private context.
- **Detection difficulty.** Hard. The writer cannot detect this by re-reading because the writer is the insider. The check has to be procedural: every paragraph compared against an explicit reader briefing (see `synthesis-reader-briefing`).
- **False positive risk.** Moderate. Threshold calibrates by genre: strict for technical or teaching prose, looser for personal-narrative where unexplained texture is part of the form.
- **Fix or remediation.** Every internal term gets either an inline introduction on first use or a replacement with descriptive language. Build a reader briefing before drafting.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-FA-002: Version-Specific Personality Slip

- **Description.** Pre-trained personality traits surfacing in inappropriate registers. GPT-4o's "warmth" leaking into legal advisory output; Claude's "thoughtful" register leaking into casual chat; Gemini's academic-formality leaking into product copy. The model adopts the persona it was trained for regardless of context fit. Per the Claude expansion's A3-NEW-012.
- **Concrete examples.**
  1. GPT-4o producing a legal memo with warm openers and personalizations.
  2. Claude producing casual social-media drafts with thoughtful-essay register.
  3. Gemini producing marketing copy with formal academic register (cross-link to A1-GEMINI-010).
  4. (Per `[opus-expansion]`) Grok producing a children's-content draft with edgy-internet register.
- **Location and register.** Body paragraphs. Strongest tell when the personality slips into a register where it does not belong.
- **Model attribution.** All families with family-specific tells per the examples above.
- **Time evolution.** Stable. Reflects RLHF persona-tuning.
- **Sources.** Claude expansion's A3-NEW-012.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate. Higher when the user has not specified the target register explicitly.
- **Causal hypothesis (ranked).** Primary: RLHF persona tuning. Secondary: training data exposure to a specific register the model has learned to default to. Tertiary: system prompt artifacts.
- **Detection difficulty.** Medium. Requires recognizing the register mismatch.
- **False positive risk.** Moderate. Some legitimate writing has register variance; the discriminator is whether the mismatch undermines the genre's purpose.
- **Fix or remediation.** Explicit register prompting. Specify the target register and tone in the prompt. Edit register-mismatched content into the target register.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-FA-003: Search-Answer Wrapper Voice

- **Description.** Prose that reads like a search product answer rather than an authored article: concise first answer, then expandable sections, then citations or pseudo-citations. Per `[chatgpt]`'s A3-NEW-026.
- **Concrete examples.**
  1. Article opens with a one-paragraph direct answer, followed by "Here is a detailed look at..." then sections that elaborate.
  2. (Per `[chatgpt]`) Each section closes with citations or links that read as search-result groundings rather than as authored citations.
  3. (Per `[opus-expansion]`) The article structure mimics a search-engine knowledge-panel: definition, key facts, relevance, sources.
- **Location and register.** Article-level structure. Densest in retrieval-augmented and search-grounded AI output.
- **Model attribution.** Perplexity, Bing-grounded ChatGPT, Gemini-with-grounding, Claude-with-search.
- **Time evolution.** Active and growing as more retrieval-grounded systems deploy.
- **Sources.** `[chatgpt]`'s A3-NEW-026.
- **Signal strength.** MEDIUM.
- **Base rate.** High in retrieval-augmented AI output.
- **Causal hypothesis (ranked).** Primary: product wrapper personalization of retrieval-augmented systems. Secondary: RLHF reward modeling for "answer-first" output. Tertiary: training data exposure to search-result rendering conventions.
- **Detection difficulty.** Medium. Requires noticing structural mimicry of search-result conventions.
- **False positive risk.** Moderate. Some legitimate writing uses answer-first structure.
- **Fix or remediation.** Rewrite into authored-article structure: build the argument, do not pre-empt it. Move citations into footnotes or inline attribution rather than search-result bibliography.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-FA-004: Process-Theater Transparency

- **Description.** The draft narrates "how it analyzed" or "what it checked" in polished process language without verifiable evidence that those checks occurred. The transparency claims are performative rather than substantive. Per `[chatgpt]`'s A3-NEW-025.
- **Concrete examples.**
  1. "I reviewed multiple sources and synthesized the key findings."
  2. "After careful analysis of the data, I have identified three patterns."
  3. (Per `[chatgpt]`) "I cross-referenced the claims against the primary sources to ensure accuracy."
  4. (Per `[opus-expansion]`) "Drawing on my training in multiple domains, I have considered several perspectives."
- **Location and register.** Article openers and section transitions. Most common in retrieval-augmented or "research mode" AI output.
- **Model attribution.** All families. Most pronounced in extended-thinking and research-style prompts.
- **Time evolution.** Active. Growing as reasoning-mode systems deploy.
- **Sources.** `[chatgpt]`'s A3-NEW-025.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate.
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling for "transparent" output that announces process. Secondary: training data exposure to research-report conventions. Tertiary: helpfulness optimization.
- **Detection difficulty.** Easy. Grep for the process-theater phrasing.
- **False positive risk.** Moderate.
- **Fix or remediation.** Remove the process announcements. Let the content's quality demonstrate the analysis.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER and MID-BODY-INSERT.

---

### A3-FA-005: Uncritical Acceptance of Prompt Framing

- **Description.** The tendency of an LLM to uncritically adopt the assumptions, biases, or framing present in the user's prompt, even if those assumptions are flawed or lead to a biased output. Per `[manus-ai]`'s A3-NEW-003.
- **Concrete examples.**
  1. (Per `[manus-ai]`) Prompt: "Write an article about why [controversial policy] is beneficial for society." AI generates a purely positive article without acknowledging counterarguments or potential downsides.
  2. (Per `[manus-ai]`) Prompt: "Explain the superiority of [Company X]'s product over its competitors." AI produces a marketing piece that uncritically praises Company X without objective comparison.
  3. (Per `[manus-ai]`) Prompt: "Discuss the historical event from the perspective of [biased historical figure]." AI generates content that fully adopts the figure's biased viewpoint without critical distance.
- **Location and register.** Any content generated in response to a biased or leading prompt.
- **Model attribution.** Common across all LLM families.
- **Time evolution.** Stable. Alignment safety tuning addresses some cases; many remain.
- **Sources.** `[manus-ai]`'s A3-NEW-003; Bender et al. (2021); Weidinger et al. (2021).
- **Signal strength.** HIGH.
- **Base rate.** Variable depending on prompt construction.
- **Causal hypothesis (ranked).** Primary: helpfulness optimization that prioritizes prompt compliance over critical evaluation. Secondary: prompt-following over-adherence. Tertiary: alignment tuning that does not always catch framing biases.
- **Detection difficulty.** Medium. Requires noticing what is absent from the response (counterarguments, alternative perspectives, critical distance).
- **False positive risk.** Low when the bias is verifiable.
- **Fix or remediation.** Reframe the prompt to ask for balanced consideration. Explicitly request counterarguments, alternative perspectives, or critical analysis.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-FA-006: Calibration Mismatch

- **Description.** High-polish prose paired with weak evidence and few abstentions. Especially relevant where models guess under benchmark pressure rather than admit uncertainty. The polish creates an inflated confidence signal that does not match the underlying evidence. Per `[chatgpt]`'s A3-NEW-028.
- **Concrete examples.**
  1. A polished analytical article that makes specific claims about historical events without acknowledging the gaps in evidence.
  2. A technical writeup that asserts specific performance numbers without citing measurements.
  3. (Per `[chatgpt]`) An advisory document with confident recommendations that lacks the abstentions a careful expert would include.
  4. (Per `[opus-expansion]`) A legal-style analysis that states specific holdings without citing the cases that established them.
- **Location and register.** Body paragraphs throughout polished AI output.
- **Model attribution.** All families. Most pronounced in extended-context completions where the polish has had room to develop.
- **Time evolution.** Active. The pattern compounds as models are tuned for confident output.
- **Sources.** `[chatgpt]`'s A3-NEW-028.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate.
- **Causal hypothesis (ranked).** Primary: generative defaults under benchmark pressure. Secondary: RLHF reward modeling for confident output. Tertiary: helpfulness optimization.
- **Detection difficulty.** Hard. Requires evaluating evidence-to-claim ratio.
- **False positive risk.** Moderate.
- **Fix or remediation.** Add appropriate hedging and abstentions. Cite evidence for specific claims. Replace unverified confident claims with verified ones or with appropriately scoped uncertainty.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-FA-007: Acronym Saturation

- **Description.** The model coins or repeats acronyms at unusual density. Genre-specific to technical or governmental writing. Unexplained acronyms used as shorthand inappropriately. Per the Claude expansion's A3-NEW-009 and `[deepseek]` N6.
- **Concrete examples.**
  1. A technical report uses ML, NLP, LLM, RLHF, RAG, AGI, ASI, NLU, NLG, ANN, CNN, RNN, GAN, VAE, GPT, BERT, T5, FLAN, all in a single section.
  2. A government policy memo uses CMS, CMMI, MIPS, ACO, HCC, RVU, FFS, MA, VBP, APM in sequence without definitions for an audience outside the field.
  3. (Per `[opus-expansion]`) A consulting deliverable uses internal acronyms (the client's project codes) that have no meaning to a third-party reader.
- **Location and register.** Body paragraphs in technical and policy writing.
- **Model attribution.** All families. Most pronounced in technical or governmental prompts.
- **Time evolution.** Stable.
- **Sources.** Claude expansion's A3-NEW-009; `[deepseek]` N6.
- **Signal strength.** LOW (genre-specific).
- **Base rate.** Genre-specific.
- **Causal hypothesis (ranked).** Primary: training data exposure to acronym-heavy genres. Secondary: helpfulness optimization (the model adopts the register it perceives as professional).
- **Detection difficulty.** Easy. Visual scan of acronym density.
- **False positive risk.** Moderate. Some genres legitimately use high acronym density.
- **Fix or remediation.** Define acronyms on first use. Reduce acronym density where the audience does not share the field's shorthand.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-FA-008: Cross-Sentence Lexical Echoing

- **Description.** Repetition of rare or distinctive adjectives or nouns across non-adjacent sentences without rhetorical purpose. The same focal word from the A3-BT-001 cluster recurs at intervals shorter than a human writer would tolerate. Sibling to A3-BT-001 (saturated AI vocabulary). Per `[grok]`'s Criterion 46.
- **Concrete examples.**
  1. "Nuanced" appearing in paragraphs 1, 3, and 5 without paragraph 2 or 4 needing it.
  2. "Robust" used three times across a 500-word article in unrelated contexts.
  3. (Per `[grok]`) "Multifaceted" recurring across three sections describing different topics.
- **Location and register.** Body paragraphs across an entire article. Strongest in long-form AI output.
- **Model attribution.** All families. Reflects training-data lexical preferences.
- **Time evolution.** Stable.
- **Sources.** `[grok]`'s Criterion 46.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate in unedited AI long-form.
- **Causal hypothesis (ranked).** Primary: training data over-representation of these focal words. Secondary: tokenizer effects (focal words are single tokens and cheap to repeat). Tertiary: RLHF reward modeling for "professional" lexical choices.
- **Detection difficulty.** Medium. Requires checking word frequency across non-adjacent sentences.
- **False positive risk.** Moderate. Some legitimate writing repeats key terms for rhetorical effect.
- **Fix or remediation.** Replace repeated focal words with varied alternatives. Use synonyms or rephrase to avoid the echo.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.


---

### A3-FA-009: Voice Normalization During Editing

- **Description.** An edit makes intelligible prose more generic by flattening idiolect, dialect, multilingual cadence, sentence-shape variation, humor, or deliberate irregularity without improving meaning, accuracy, or venue fit.
- **Concrete examples.** A compact first-person aside becomes a formal transition; regionally natural phrasing is standardized despite being clear; a writer's alternating fragments and long sentences become uniform medium-length paragraphs; an editor adds headings and a summary to prose whose original movement was implicit.
- **Location and register.** Editing, rewriting, copyediting, tone conversion, and mixed human/model workflows.
- **Model attribution.** Model-agnostic preservation risk. Current-model frequency is a controlled-test question.
- **Time evolution.** Timeless as editorial overreach; prevalence varies by prompt and editing surface.
- **Sources.** August 2026 accepted first-tranche preservation synthesis; provenance-known human-control evaluation pending.
- **Signal strength.** HIGH for voice preservation when changes have no named benefit; not an authorship signal.
- **Base rate.** Unmeasured.
- **Causal hypothesis (ranked).** Alternatives include house style, accessibility needs, editor preference, risk aversion, model-default cadence, and prompt ambiguity.
- **Detection difficulty.** Medium. Requires the source, the edit, audience knowledge, and an explicit editing objective.
- **False positive risk.** High when the agreed brief requires house-style normalization, accessibility changes, translation, legal clarity, or a different venue.
- **Fix or remediation.** Revert changes that cannot name a benefit in meaning, accuracy, voice, rhythm, structure, accessibility, or venue fit. Preserve intelligible variation and obtain author approval for consequential normalization.
- **Era status.** Active (timeless editorial category).
- **Zone tag.** BODY-PERSISTENT.
- **Evidence status.** Accepted preservation risk; model-specific promotion not authorized.
- **Authorship inference.** Not established.

---

### A3-FA-010: Private Working-Language Leakage

- **Description.** A user-facing summary or artifact relies on shorthand developed during the model's private work: arrow chains, hyphen-stacked compounds, unexplained model-created labels, local ontologies, deep implementation references, or allusions to reasoning the reader never saw. The failure is dependence on unseen context, not jargon or punctuation by itself.
- **Concrete examples.** A handoff invokes “the RCD path” without ever defining the model-created label; a summary uses `parse→gate→hydrate` as if the reader observed the intermediate design; an artifact refers to “the second-root fix” or “the constraint-collapse layer” without introduction.
- **Location and register.** Long-session summaries, handoffs, technical explanations, and agentic final answers.
- **Model attribution.** Anthropic documents the behavior and mitigation for Fable 5. Practitioner reports provide only anecdotal Opus 5 corroboration. Standard technical shorthand and human team vocabulary remain ordinary alternatives.
- **Time evolution.** Current Fable 5 overlay dated 2026-08; the audience-dependence test is timeless.
- **Sources.** Anthropic's current Fable 5 prompting guide; documentary research `2026-08-22-deeper-current-model-patterns.md`, C01.
- **Signal strength.** HIGH for reader-context failure; MEDIUM as a current Fable combined signal only with corroboration; never sufficient alone for attribution.
- **Base rate.** Not published by the provider; unmeasured in this project.
- **Causal hypothesis (ranked).** Unknown. Plausible alternatives include long-context compression, terse-output pressure, team shorthand, expert-audience assumptions, and ordinary human omission.
- **Detection difficulty.** Medium. Extract specialized labels and ask whether each is standard for the audience, introduced in the artifact, necessary, and explained.
- **False positive risk.** Moderate to high in architecture records, mathematical writing, and expert handoffs.
- **Fix or remediation.** Define necessary terms on first use, replace temporary work labels with descriptive language, and remove details that depend on unseen reasoning rather than the reader's decision.
- **Era status.** Active current-family overlay as of 2026-08.
- **Zone tag.** FULL-RESPONSE-HANDOFF and BODY-PERSISTENT.
- **Authorship inference.** Not established.

---

### A3-FA-011: Non-Material Work and Correction Chronology

- **Description.** The response narrates upcoming actions, discarded options, explored roots, or self-corrections that could have been incorporated silently and do not change the reader's evidence, conclusion, decision, risk, or ability to reproduce the work. Unlike process theater, the chronology may be truthful; its failure is that it is not load-bearing.
- **Concrete examples.** “First I considered three database engines, but I won’t discuss two of them”; a final answer recounts a typo the model noticed and corrected before presenting the result; repeated “I’ll check…” announcements before ordinary tool calls; an explanation spends more space on rejected roots than on the selected mechanism.
- **Location and register.** Agentic wrapper updates, multi-turn corrections, final handoffs, and research narratives.
- **Model attribution.** Anthropic documents progress narration and non-material correction narration for Opus 5 and unused-option or root elaboration for Fable 5. Audit trails, incident reports, and transparent research logs can legitimately preserve chronology.
- **Time evolution.** Current Opus 5 and Fable 5 overlay dated 2026-08; materiality remains the durable test.
- **Sources.** Anthropic's current Opus 5 and Fable 5 prompting guides; documentary research `2026-08-22-deeper-current-model-patterns.md`, C02.
- **Signal strength.** HIGH for editorial waste after the materiality test; MEDIUM in a current-Claude combined assessment; never sufficient for provider attribution.
- **Base rate.** Not published by the provider; unmeasured in this project.
- **Causal hypothesis (ranked).** Unknown. Alternatives include transparency requirements, audit logging, model defaults, user requests for progress, and ordinary human narration.
- **Detection difficulty.** Medium. Remove each chronology sentence and ask whether evidence, conclusion, decision, risk, or reproducibility changes.
- **False positive risk.** Moderate in live progress updates and high in formal audit trails or incident retrospectives.
- **Fix or remediation.** State the corrected outcome directly. Retain only chronology that changes a conclusion, decision, risk, evidence interpretation, or reproducibility.
- **Era status.** Active current-family overlay as of 2026-08.
- **Zone tag.** WRAPPER-UPDATE, WRAPPER-CLOSER, and FULL-RESPONSE-HANDOFF.
- **Authorship inference.** Not established.

---

## Section A3-SR: Social-register

The social-register criteria apply when the artifact is a social media post (LinkedIn, Twitter/X, Threads, BlueSky, Reddit, Facebook, Instagram). Some are tolerable in articles but flag immediately in social. The thresholds differ from articles per the explanatory note in the parent SKILL.md "Social-register failures" section.

### A3-SR-001: Imported Spec Language Uppercase

- **Description.** Uppercase severity labels (CRITICAL, HIGH, MEDIUM, LOWER) lifted from technical specs into a LinkedIn or Twitter post. The labels read as press-release register in conversational mode.
- **Concrete examples.**
  1. "CRITICAL update: I have just shipped..." in a LinkedIn post.
  2. "HIGH priority: The team has identified..." in a Twitter thread.
  3. (Per `[opus-expansion]`) "MEDIUM impact: Our quarterly results show..."
- **Location and register.** Social post openers and section transitions. HIGH for social; LOW for articles where the labels can be domain-appropriate.
- **Model attribution.** All families. Most pronounced when the AI is asked to convert technical content to social.
- **Time evolution.** Stable.
- **Sources.** v3.1.0 criterion 38; `[chatgpt]`'s KEEP.
- **Signal strength.** HIGH for social posts.
- **Base rate.** Moderate when AI-drafting social posts derived from internal technical content.
- **Causal hypothesis (ranked).** Primary: training data over-representation of technical specs and press releases. Secondary: helpfulness optimization that preserves the source register.
- **Detection difficulty.** Easy.
- **False positive risk.** Low for social.
- **Fix or remediation.** Translate to conversational equivalents ("significant," "smaller," "minor") or describe without labeling.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT (in the social-post artifact).

---

### A3-SR-002: Article Structure in Social Posts

- **Description.** Topic sentences, transitions ("First," "Second," "Finally"), formal labels ("The principle," "The takeaway," "In summary") imported into a social post. Reads as essay, not conversation.
- **Concrete examples.**
  1. "First, let me set the context. Second, here is what happened. Finally, here is the takeaway." in a LinkedIn post.
  2. "The principle: technology should serve people. The application: our new product does X."
  3. (Per `[chatgpt]`) "In summary, the key insight is that..."
- **Location and register.** Social posts of any length. HIGH for social.
- **Model attribution.** All families when prompted for social drafts.
- **Time evolution.** Stable.
- **Sources.** v3.1.0 criterion 39; `[perplexity]`'s KEEP (cross-link to A2-SUB-011); `[deepseek]`'s DEMOTE for Facebook-specific style (which is genuinely declining).
- **Signal strength.** HIGH for social posts (highly diagnostic for AI-generated LinkedIn and X drafts).
- **Base rate.** High in unedited AI social drafts.
- **Causal hypothesis (ranked).** Primary: training data exposure to essay structures. Secondary: helpfulness optimization that structures output regardless of genre. Tertiary: RLHF reward modeling for "clear" output.
- **Detection difficulty.** Easy.
- **False positive risk.** Low for social. Moderate for longer-form LinkedIn pieces that approach essay length.
- **Fix or remediation.** Reframe as thoughts flowing in real time, not structured exposition. Use sentence-level flow rather than paragraph-level structure.
- **Era status.** Active. Facebook-specific style declining per `[deepseek]`.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-SR-003: Third-Person Narration of First-Person Experience

- **Description.** A post about the author's own experience that uses "the site," "the audit," "the fix" instead of "my site," "my audit," "my fix." Reads as third-party reporting on the author.
- **Concrete examples.**
  1. "The site lost 60 percent of search traffic" (in a personal post; should be "my site").
  2. "The audit identified three issues" (in a personal post; should be "my audit").
  3. (Per `[opus-expansion]`) "The product launched last week" when describing one's own product launch.
- **Location and register.** Personal-brand and founder-post contexts. HIGH for social.
- **Model attribution.** All families when AI-drafting first-person social posts.
- **Time evolution.** Stable.
- **Sources.** v3.1.0 criterion 40; `[cross-validated:manus-ai+perplexity+chatgpt]`.
- **Signal strength.** HIGH for social.
- **Base rate.** Moderate to high in AI-drafted personal social posts.
- **Causal hypothesis (ranked).** Primary: training data exposure to third-person reporting. Secondary: helpfulness optimization that defaults to third-person "objective" register. Tertiary: alignment safety tuning that discourages first-person opinion-stating.
- **Detection difficulty.** Easy.
- **False positive risk.** Low.
- **Fix or remediation.** First-person throughout. Personal pronoun in every paragraph for long-form social.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-SR-004: Lack of Closing Engagement in Social

- **Description.** Posts that close the loop cleanly and walk away. Conversational posts invite response. Per `[perplexity]`'s REVISE: AI Reddit simulation has improved; downgrade from HIGH to MED. Per `[chatgpt]`'s REVISE: lower dependence because some human high-status posters deliberately do not ask questions.
- **Concrete examples.**
  1. A post that ends with the final statement of the lesson rather than inviting comment.
  2. A LinkedIn post that closes with a polished tagline rather than a question.
  3. (Per `[opus-expansion]`) A Twitter thread that ends with "End of thread" rather than "What have you seen?"
- **Location and register.** Social post closers. MED for social (downgraded from HIGH).
- **Model attribution.** All families.
- **Time evolution.** Declining as AI Reddit simulation has improved at including engagement closers per `[perplexity]`.
- **Sources.** v3.1.0 criterion 41; `[perplexity]` REVISE; `[chatgpt]` REVISE.
- **Signal strength.** MEDIUM for social (downgraded from HIGH).
- **Base rate.** Moderate.
- **Causal hypothesis (ranked).** Primary: training data exposure to essay or article structure rather than conversation. Secondary: RLHF reward modeling for "complete" output.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate. Some high-status human posters deliberately omit engagement asks; the discriminator is the writer's typical pattern.
- **Fix or remediation.** End with a question, an observation that begs a follow-up, or a deliberate variant of "tell me what you have seen." Not every post needs it, but the default for conversational posts is yes.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER (in the social-post artifact).

---

### A3-SR-005: Em Dashes in Social Posts

- **Description.** Em-dash usage in social posts. Criterion A3-SS-001 covers em-dash overuse in general writing (HIGH for Claude family, LOW for Llama/GPT-5.1+, applies to all writing). For social posts the threshold tightens: any em-dash usage is a tell. Fast-scrolling social readers register em-dashes as the AI-typical polished-prose signal even when used correctly.
- **Concrete examples.**
  1. A LinkedIn post containing any em-dash.
  2. A Twitter thread with em-dashes around a parenthetical.
  3. (Per `[claude-exec-2026-05-18]`) An Instagram caption using em-dash for emphasis.
- **Location and register.** Social posts. MED for social (promoted from LOW per cross-modal consistency with A3-SS-001).
- **Model attribution.** Claude family (HIGH for em-dash usage in any context, including social). GPT family (DECLINING after GPT-5.1 personalization). Llama (NEAR-ZERO baseline).
- **Time evolution.** Stable for Claude. Declining for GPT.
- **Sources.** v3.1.0 criterion 42; `[claude-exec-2026-05-18]` PROMOTE alongside criterion 11 for cross-modal consistency.
- **Signal strength.** MEDIUM for social (promoted from LOW). HIGH when combined with other social-register failures.
- **Base rate.** Moderate in AI-drafted social content from Claude.
- **Causal hypothesis (ranked).** Primary: training data skew toward edited prose (the model has not learned to suppress em-dashes for social register). Secondary: tokenizer effects.
- **Detection difficulty.** Easy. Character search for U+2014.
- **False positive risk.** Low for social.
- **Fix or remediation.** Replace with commas, parentheses, colons, or sentence breaks. Articles can use em-dashes sparingly for genuine dramatic pause; social posts should not.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT (in the social-post artifact).

---

## Cross-file dependencies

Entries in this file depend on patterns documented in other references/ files:

- **A3-LT-003, A3-BT-001, A3-BT-002.** Family-specific vocabulary fingerprints reference the per-family pattern catalog in `references/model-family-fingerprints.md`. The Claude expansion's A1-CLAUDE-001, A1-CLAUDE-020, A1-GPT-001, and A1-GEMINI-010 entries provide the full per-family detail.
- **A3-SS-001, A3-SS-002, A3-SS-003.** Combined-signal fingerprints (em-dashes + bolded lead-ins + uniform paragraphs) live in `references/combined-signal-fingerprints.md`. B2-COMBO-003 is the canonical Claude.ai default Combo.
- **A3-LT-010, A3-CX-002, A3-FA-001, A3-BT-001.** Calibration tables with per-family base rates and ESL safe-harbor splits live in `references/calibration-tables.md`. The Liang et al. 2023 ESL false-positive risk anchors the safe-harbor.
- **A3-CX-003.** The full A2 substance-and-depth section, with all 15+ sub-patterns, lives in `references/substance-and-depth.md`. This entry exists in the catalog for navigation only.
- **A3-CS-001, A3-CS-003, A3-CS-005, A3-TF-003, A3-TF-004.** Citation-related criteria cross-link to `synthesis-fact-checking` v2.0 references for the full verification protocols. See specifically the C1 protocol sections (nested attribution, paraphrase drift, composite quotes, URL rot vs hallucination, synthetic sources, citation laundering chains).
- **A3-TF-002, A3-BT-002, A3-BT-004, A3-BT-005.** Historical-era patterns (Bard, Llama 1/2, Grok 1, DeepSeek V1/V2, Mistral 7B / Mixtral, Qwen 1/2, pre-instruction-tuning GPT-3) are catalogued in `references/historical-patterns.md` per the compounding-archive principle.
- **All entries.** The consolidated bibliography across this catalog lives in `references/bibliography.md`, including Kobak et al. 2024, Liang et al. 2023, Sharma et al. 2023, Bitton et al. 2025, DeepSeek-R1 (Nature 2025), Plagiarism Today June 2025, Hicks et al. 2024 ("ChatGPT is bullshit"), Pennycook et al. 2015 on pseudo-profundity, Frankfurt 2005, and the per-LLM-cited industry-press references.

## Cross-skill dependencies

- **synthesis-fact-checking v2.0.** The citation-related entries in this file (A3-CS-001 through A3-CS-006, A3-TF-003, A3-TF-004) depend on the C1 protocol sections in the fact-checking skill for verification methodology.
- **synthesis-reader-briefing.** A3-FA-001 (Insider Context Collapse) is detected via the reader-briefing methodology. The fix is procedural and lives in the reader-briefing skill.
- **synthesis-writing-pitfalls.** Universal human-source bad-writing patterns are complementary to the AI-source patterns here. Use both for comprehensive review.
- **synthesis-writing-craft.** Positive principles from the writing-craft tradition complement these negative-pattern entries.
- **synthesis-clean-text.** Generation-time hygiene; this file is for detection-time review. Both are used together.
- **synthesis-content-distribution.** A3-SR-001 through A3-SR-005 (social-register failures) cross-link to the social register vs article register section in synthesis-content-distribution.

---

## End of catalog

This file documents 74 distinct entries: 42 renumbered v3.1.0 criteria plus 32 net-new entries from A3.3 of the unified bucket, with the 16-field template applied uniformly. Era status and zone tags are populated for every entry per the compounding-archive principle and the zone-conditional detection methodology recorded in the author's research design notes (not published).

Em-dash count: zero throughout. Verified via grep at write-time.
