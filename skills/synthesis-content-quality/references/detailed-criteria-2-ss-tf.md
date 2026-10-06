# Detailed Criteria Reference (v4.0), part 2 of 5

Part 2 of the file split from [detailed-criteria.md](detailed-criteria.md), which keeps the opening sections and lists every part. The text below is unchanged.

Contents:
- Section A3-SS: Style and Structural (A3-SS-001 to A3-SS-011, 11 entries)
- Section A3-TF: Technical and Formatting (A3-TF-001 to A3-TF-008, 8 entries)

## Section A3-SS: Style and Structural

### A3-SS-001: Excessive Em Dashes

- **Description.** Em dashes (the long dash, Unicode U+2014) used at notably higher density than human writers, in particular as parenthetical-substitute punctuation around mid-sentence asides and as the punctuation between an independent clause and an appositive. Cross-references A1-CLAUDE-004 (em-dash density), A3-SR-005 (em-dashes in social posts), and A3-SS-008 (en-dash overuse as em-dash replacement). Largest tier-shift divergence in the catalog.
- **Concrete examples.**
  1. Human-typical: "The migration, which took six weeks, was worth the effort." Claude-tendency: "The migration (which took six weeks and required cross-team coordination) was worth the effort," substituted with em-dashes in the original output.
  2. (Per `[perplexity]`) "The integration, already underway in three pilot markets, faces regulatory headwinds that could delay the rollout by as much as 18 months." When original output used em-dashes around the parenthetical clause.
  3. (Per `[perplexity]`) "Machine learning models, particularly transformer architectures, perform best when fine-tuned on domain-specific data." Same em-dash substitution.
  4. (Per `[opus-expansion]`) "There are three concerns, cost, complexity, and time, that need to be addressed before proceeding." Em-dashes used as oxford-comma substitutes.
- **Location and register.** Universal across registers. Densest in long-form analytical prose. Notably present in social-media posts (especially LinkedIn) where human writers tend to avoid the character.
- **Model attribution.** Claude family (HIGH; single strongest token-level fingerprint as of 2025). Pre-GPT-5.1 ChatGPT (HIGH). GPT-5.1+ (LOW; explicit anti-em-dash personalization rolled out in 2025 dropped its rate). Llama and Meta.ai (NEAR-ZERO per `[gemini]` A1-LLAMA-001: 0.0 occurrences per 1,000 words). Gemini variable depending on system prompt.
- **Time evolution.** Present from Claude 2 forward at increasing density through 3.5 Sonnet. ChatGPT had high em-dash rate through GPT-4o; rate dropped sharply after the GPT-5.1 anti-em-dash personalization update in 2025. Claude has not made an equivalent adjustment as of 2026-05. Per `[chatgpt]`'s DEMOTE recommendation: frontier models show reduced rates while retaining the social-specific version at high confidence. Per `[grok]`'s DEMOTE: same direction.
- **Sources.** v3.1.0 criterion 11; `[claude-exec-2026-05-18]` (identified as "the single strongest token-level tell on Claude and pre-GPT-5.1 ChatGPT"); Plagiarism Today June 2025 ("Em Dashes, Hyphens and Spotting AI Writing"); `[cross-validated:perplexity+deepseek+manus-ai+gemini]`; Pangram Labs (2026) detector methodology lists em-dash density among trained features; BlogPros (2026); LinkedIn practitioner catalog 2025.
- **Signal strength.** HIGH for Claude family and pre-GPT-5.1 ChatGPT (promoted from LOW). LOW for GPT-5.1+ and Llama families. Per-family weighting is essential. Per Perplexity threshold: 5+ em-dashes per 500 words is a HIGH signal in Claude.
- **Base rate.** Very high in unedited Claude output (estimated 80 to 95 percent of long-form completions contain at least one em-dash; many contain dense clusters per `[opus-expansion]`). High in pre-GPT-5.1 ChatGPT. Near zero in Llama and Meta.ai. Low in current GPT-5.1.
- **Causal hypothesis (ranked).** Primary: training-data skew toward edited prose corpora (academic, journalism) that overrepresent em-dashes relative to general web text. Secondary: RLHF reward modeling that reads em-dashes as a polish signal. Tertiary: tokenizer effects (the em-dash is a single token in most tokenizers, making it cheap to generate). Per Perplexity: RLHF rewards readability; em-dashes score well on readability metrics because they reduce sentence count while preserving information density.
- **Detection difficulty.** Easy. Character search.
- **False positive risk.** Moderate. Some skilled writers (journalism, certain literary genres) use em-dashes heavily as a stylistic choice. The discriminator is density per 1,000 tokens and combination with other markers.
- **Fix or remediation.** Replace with commas (for parentheticals of moderate weight), parentheses (for stronger asides), colons (for appositives), or sentence breaks (for cases where the em-dash was joining two complete thoughts). Per Perplexity: split at the dash. "X, already Y, does Z" becomes "X does Z. (It was already Y.)"
- **Era status.** Active for Claude. Declining for GPT family. Historical for newer Meta/Llama output where the base rate has always been near zero.
- **Zone tag.** BODY-PERSISTENT.
- **Notes on disagreement.** ChatGPT proposes DEMOTE (frontier models reduced rates). Manus AI proposes REVISE (less reliable standalone). Grok proposes DEMOTE. Claude expansion proposes PROMOTE (LOW to HIGH for Claude). Gemini proposes per-family split (DEPRECATE for Llama, PROMOTE for GPT/Claude). Merged: PROMOTE with per-family weighting per Gemini's split.

---

### A3-SS-002: Bulleted Lists with Bolded Lead-ins

- **Description.** Formulaic bullet points where each item begins with a bolded short noun phrase followed by a colon or period, then the body text. The structure is consistent within a single response, often three to seven items long, and reads as outline-mode prose rather than natural list construction. Cross-references A1-CLAUDE-005 and A1-GPT-008 (numbered-list scaffolding and listicle-default mode).
- **Concrete examples.**
  1. "**Cost efficiency:** The new approach reduces server expenses by 40 percent."
  2. "**Scalability:** Adding capacity is now a configuration change rather than a rebuild."
  3. "**Developer experience:** Engineers report 30 percent faster iteration."
  4. (Per `[deepseek]`) "**Improved efficiency:** The new process reduces the time required for data entry by nearly 40%, freeing up staff for higher-value tasks."
  5. (Per `[deepseek]`) "**Enhanced security:** By implementing multi-factor authentication, the system ensures that only authorized users can access sensitive information."
- **Location and register.** Body of explanatory and analytical responses. Particularly dense in product, business, and technical-writing registers. Rare in dialogue and fiction.
- **Model attribution.** Claude family (HIGH). GPT family (HIGH, especially 4o). Gemini (MEDIUM-HIGH; markdown-leaked variant where the bold formatting renders incorrectly in non-rendering channels, cross-link to A1-GEMINI-001 plain-text markdown leakage).
- **Time evolution.** Present from Claude 2 forward; standardized in 3.x; high density in 4.x default outputs without explicit "do not use bullets" system prompt.
- **Sources.** v3.1.0 criterion 12; `[claude-exec-2026-05-18]`; `[cross-validated:perplexity+gemini+manus-ai]`; Walsh et al. CHR 2024 documents the outline-rendered-as-poem effect in LLM creative output.
- **Signal strength.** HIGH (promoted from MED) when combined with em-dash density (A3-SS-001) or uniform paragraph length (A3-LT-010). MEDIUM standalone.
- **Base rate.** High in unedited Claude output for explanatory or comparative responses (estimated 50 to 70 percent of responses containing 3+ items use this bolded-lead-in structure). High in GPT 4o. Moderate in Gemini.
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling that scores well-organized structured output. Secondary: training-data skew toward documentation and product copy corpora. Tertiary: system-prompt artifacts in Claude.ai default UI tuning.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate. Technical documentation, product copywriters, and how-to guides legitimately use this structure. The discriminator is density (every response using it for every list) and combination with other markers.
- **Fix or remediation.** When the structure is genuinely warranted (true parallel items where each has the same scaffold), keep it. When the response is short or the items are heterogeneous, write the items as prose or use plain bullets without bolded lead-ins.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-SS-003: Excessive Bolding and Formatting

- **Description.** Mechanical, over-consistent use of bold text for key terms throughout an article. LLMs sometimes emphasize terms they deem "important" without understanding that excessive formatting reduces readability. Combinable with A3-SS-005 (markdown formatting leakage) and adjacent to A3-SS-002 (bulleted lead-ins). Per `[perplexity]`: accurate for GPT-4o; reducing in GPT-4.1.
- **Concrete examples.**
  1. "**Key insight**: The **migration** improved **performance** by 40 percent and reduced **costs** by 25 percent, demonstrating the **value** of the **approach**."
  2. "The **decision** was made to **prioritize** the **customer experience** over **internal metrics**."
  3. (Per `[opus-expansion]`) Multiple sentences in a paragraph with **bolded** terms that simply restate ordinary nouns or verbs in **emphatic** form rather than marking genuinely **important** terms.
- **Location and register.** Body paragraphs. Densest in product, business, and technical-writing registers.
- **Model attribution.** Claude family (MEDIUM-HIGH). GPT-4o family (HIGH; reducing in GPT-4.1 per `[perplexity]`). Gemini (MEDIUM-HIGH; cross-link to A1-GEMINI-001 markdown leakage).
- **Time evolution.** Peaked in 2024 Claude and GPT-4o; reducing in GPT-4.1 specifically. Claude has not made an equivalent reduction.
- **Sources.** v3.1.0 criterion 13; `[claude-exec-2026-05-18]`; `[perplexity]` REVISE recommendation for version note.
- **Signal strength.** MEDIUM (promoted from LOW). HIGH when combined with A3-SS-002.
- **Base rate.** High in unedited Claude and GPT-4o output for explanatory prose.
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling that scores prose with explicit emphasis higher. Secondary: training-data skew toward marketing and product documentation where bolding is conventional. Tertiary: system-prompt artifacts.
- **Detection difficulty.** Easy. Visual scan of formatting density.
- **False positive risk.** Low to moderate. Technical and educational writing legitimately uses bolding for key terms; the discriminator is density (more than one bolded term per paragraph throughout).
- **Fix or remediation.** Bold sparingly. If everything is emphasized, nothing is. Reserve bold for terms that the reader will need to recognize again later.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-SS-004: Emoji Usage in Inappropriate Contexts

- **Description.** Emojis appearing in article text, headers, or formal content where they do not belong. Some LLMs insert emojis to "add emotion" or "engage readers," but do so without understanding context or audience appropriateness. Cross-references A1-GEMINI-027 (emoji in explanations) per the unified bucket A. Wrapper-sensitive: stronger for GPT-4o-era consumer surfaces and social drafts than for APIs.
- **Concrete examples.**
  1. A formal policy memo containing "Key benefits include..."
  2. A technical report header reading "Architecture Overview"
  3. A news article body containing "The CEO confirmed the merger"
  4. (Per `[opus-expansion]`) An academic-style essay with section headers that begin with thematic emojis (rocket for "growth," lightbulb for "ideas," graph for "metrics") despite the publication context not warranting them.
- **Location and register.** Universal where emojis appear. Strongest signal when found in formal, technical, academic, journalistic, or business prose where the register is mismatched. Normal in social media, casual blogs, or intentionally informal content.
- **Model attribution.** Gemini family (HIGH; cross-link to A1-GEMINI-027). GPT-4o family (MEDIUM-HIGH on consumer surfaces). Claude family (LOW). DeepSeek (LOW).
- **Time evolution.** GPT-4o-era consumer surfaces peaked emoji usage in 2024; reducing in later versions. Gemini retains higher rates per Bloomberry AI 2026 observations.
- **Sources.** v3.1.0 criterion 14; `[chatgpt]`'s REVISE recommendation; `[claude-exec-2026-05-18]`'s REVISE recommendation.
- **Signal strength.** LOW for general AI detection. HIGH when context-mismatched (formal content with emojis).
- **Base rate.** Moderate in unedited Gemini and GPT-4o output for consumer or social-style prompts. Low elsewhere.
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling that scores "engaging" or "friendly" output higher. Secondary: training-data skew toward social-media and consumer-content corpora. Tertiary: system-prompt artifacts in consumer-surface tunings (Gemini consumer apps in particular).
- **Detection difficulty.** Easy. Visual scan.
- **False positive risk.** Low when context-mismatched. Moderate in genuinely informal contexts.
- **Fix or remediation.** Remove emojis from formal content. Retain in casual or social content if the register supports them.
- **Era status.** Active.
- **Zone tag.** HYBRID (wrapper and body).

---

### A3-SS-005: Markdown Formatting Mixed with Standard Text

- **Description.** Presence of Markdown syntax elements in published content that did not render. The content was generated for a Markdown-rendering channel and copy-pasted into a non-rendering one without translation. Very strong drafting-residue signal.
- **Concrete examples.**
  1. Asterisks for bold or italic appearing literally: `*emphasis*` or `**strong**`
  2. Underscores for emphasis: `_italic_`
  3. Hash symbols for headers appearing in body text: `## Section Title` as a line
  4. Backticks for code appearing literally: `` `inline code` ``
  5. Numbers with periods for lists when not rendered: `1. First item` `2. Second item`
  6. Triple backticks marking code blocks visibly: ` ``` `
- **Location and register.** Universal where it appears. Strongest tell in news articles, blog posts, and any rendered HTML or print publication context.
- **Model attribution.** All families. Gemini family (HIGH per `[claude-exec-2026-05-18]` A1-GEMINI-001 plain-text markdown leakage; cross-link to GitHub gemini-cli #8392). Claude family (MEDIUM). GPT (MEDIUM). Llama (MEDIUM per `[perplexity]`'s A1-LLAMA-017 markdown underuse, which is the inverse pattern).
- **Time evolution.** Stable across generations. Gemini formatting update per 9to5Google September 2025 changed defaults.
- **Sources.** v3.1.0 criterion 15; `[cross-validated:manus-ai+chatgpt+grok]`; GitHub gemini-cli #8392 per `[claude-exec-2026-05-18]`.
- **Signal strength.** HIGH.
- **Base rate.** Low to moderate; depends entirely on whether the channel renders Markdown.
- **Causal hypothesis (ranked).** Primary: training-data skew (LLMs are trained heavily on GitHub, Reddit, Discord, and other Markdown-rendering surfaces). Secondary: system-prompt defaults that request Markdown formatting regardless of channel.
- **Detection difficulty.** Easy.
- **False positive risk.** Very low when in a non-rendering channel.
- **Fix or remediation.** Translate to the target platform's formatting. Convert `**bold**` to actual bold tags or to plain text with quotation marks if no bold is available. Strip header hashes.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-SS-006: Curly vs. Straight Quotes

- **Description.** Inconsistent use of curly quotes (typographic apostrophes and quotation marks) versus straight quotes, or the wrong type for the context. Per `[chatgpt]`'s DEPRECATE recommendation: too toolchain-dependent and too weak as a modern provenance signal. The toolchain (text editor, copy-paste path, rendering target) determines quote style more than the model.
- **Concrete examples.**
  1. Curly quotes in a Markdown source file destined for a renderer that does not handle them.
  2. Straight quotes in a typeset book or magazine article where curly quotes are standard.
  3. Mixed quote styles within a single document.
- **Location and register.** Universal where the quote style is mismatched to the target.
- **Model attribution.** Per `[perplexity]`: primarily Gemini and formal-register outputs. Per `[chatgpt]`: too toolchain-dependent for reliable attribution.
- **Time evolution.** No reliable evolution; tied more to channel and editing pipeline than to model.
- **Sources.** v3.1.0 criterion 16; `[chatgpt]`'s DEPRECATE recommendation; `[perplexity]`'s REVISE.
- **Signal strength.** DEPRECATED (retained for archive per the compounding-archive principle). Effectively LOW.
- **Base rate.** Too channel-dependent for meaningful base rate.
- **Causal hypothesis (ranked).** Primary: tokenizer and rendering pipeline. Secondary: training-data quote-style mix. Tertiary: editor and channel translation gaps.
- **Detection difficulty.** Easy when present.
- **False positive risk.** High. Many human-written documents have mixed quote styles for the same toolchain reasons.
- **Fix or remediation.** Apply consistent quote style per the target channel. Use the channel's standard conversion tools rather than relying on model output.
- **Era status.** Deprecated. Retained for archival use only.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-SS-007: Title Case in Headers and Nominalization Cascade

- **Description.** Section headers capitalize every major word (Title Case) instead of using sentence case, especially in journalism contexts. The v3.1.0 criterion 17 combined this with the nominalization-cascade concept; v4.0 separates the title-case aspect (A3-SS-007) from the nominalization-cascade aspect (A3-LT-012) for clarity. Per `[chatgpt]`'s DEMOTE: publishing-style dependent; weak standalone evidence. Per `[perplexity]`'s REVISE: primarily Gemini and formal-register outputs.
- **Concrete examples.**
  1. AI default: "The Evolution Of Modern Technology" (every major word capitalized).
  2. Journalism standard: "The evolution of modern technology" (sentence case).
  3. AI default: "How To Optimize Your Workflow For Maximum Productivity"
  4. AI default: "Five Key Insights From The Latest Industry Report"
- **Location and register.** Section headers and subheaders. Strongest tell when found in journalism or web-content contexts where sentence case is the standard.
- **Model attribution.** Gemini family (HIGH per `[perplexity]`). GPT-4o family (MEDIUM-HIGH). Claude family (MEDIUM). Llama (LOW).
- **Time evolution.** Stable. Reflects training-data exposure to academic and marketing prose, which use title case heavily.
- **Sources.** v3.1.0 criterion 17; `[chatgpt]` DEMOTE; `[perplexity]` REVISE.
- **Signal strength.** LOW (demoted from MED). HIGH when context-mismatched (journalism context with title-case headers).
- **Base rate.** Moderate to high in unedited AI output for content with headers. Lower in casual or social formats.
- **Causal hypothesis (ranked).** Primary: training-data skew toward academic, marketing, and SEO content where title case is conventional. Secondary: system-prompt defaults.
- **Detection difficulty.** Easy. Visual scan of header capitalization.
- **False positive risk.** Moderate. Marketing and academic contexts legitimately use title case.
- **Fix or remediation.** Apply the target publication's house style for header capitalization. Most journalism, blogs, and modern web content use sentence case.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-SS-008: En-Dash Overuse as Em-Dash Replacement

- **Description.** Emerging pattern in models where em-dash use has been tuned down. As GPT-5.1's anti-em-dash personalization rolled out, some output shifted to en-dashes (Unicode U+2013) for the same parenthetical-substitute function. The substitution is detectable because en-dashes have a narrower legitimate use (ranges, compound modifiers) than the broader parenthetical role they have begun to fill. Per the Claude expansion's A3-NEW-004.
- **Concrete examples.**
  1. Mid-sentence en-dashes substituting for the em-dash function: "The team, despite the resource constraints, delivered the feature on schedule" where the original output used en-dashes around the parenthetical.
  2. En-dash between independent clause and appositive: "There are three concerns: cost, complexity, and time" rendered with en-dashes instead.
- **Location and register.** Universal. Densest in GPT-5.1+ analytical prose.
- **Model attribution.** GPT-5.1+ primarily; emerging in other families that have personalized against em-dashes.
- **Time evolution.** New as of 2025 with GPT-5.1's anti-em-dash rollout.
- **Sources.** Claude expansion's A3-NEW-004; `[opus-expansion]`.
- **Signal strength.** MEDIUM (emerging).
- **Base rate.** Low but growing.
- **Causal hypothesis (ranked).** Primary: RLHF personalization (GPT-5.1's explicit em-dash penalty) without retraining the underlying use case, causing the model to substitute the nearest-shape character. Secondary: tokenizer effects (en-dash is also a single token).
- **Detection difficulty.** Easy. Character search for U+2013 in non-range contexts.
- **False positive risk.** Moderate. En-dashes have legitimate uses (number ranges, compound modifiers); the discriminator is en-dashes in clearly parenthetical positions.
- **Fix or remediation.** Replace with commas, parentheses, colons, or sentence breaks, same as for em-dashes.
- **Era status.** Active (emerging in 2025-2026).
- **Zone tag.** BODY-PERSISTENT.

---

### A3-SS-009: Over-Consistent Paragraph Rhythm Across Genres

- **Description.** Visual and syntactic uniformity that survives genre shift. The same paragraph rhythm appears whether the model is writing a recipe, a code explanation, or a legal analysis. Sibling to A3-LT-010 (uniform sentence and paragraph length) but distinct in that it focuses on cross-genre persistence rather than within-document homogeneity. Per `[grok]`'s Criterion 44.
- **Concrete examples.** This is a cross-document pattern best seen by comparing the model's output for prompts of different genres. A recipe in 3-to-5-sentence paragraphs; a code explanation in 3-to-5-sentence paragraphs; a legal analysis in 3-to-5-sentence paragraphs. Human writers shift rhythm to match the genre.
- **Location and register.** Universal across genres in unedited AI output.
- **Model attribution.** All families. Most pronounced in Claude and GPT.
- **Time evolution.** Stable; reflects underlying generation strategy.
- **Sources.** `[grok]`'s Criterion 44.
- **Signal strength.** MEDIUM.
- **Base rate.** High in unedited AI output across multi-genre samples.
- **Causal hypothesis (ranked).** Primary: tokenizer and architecture effects. Secondary: training-data skew toward moderate-paragraph-length prose across genres. Tertiary: RLHF reward modeling for readability that converges on a single rhythm.
- **Detection difficulty.** Hard. Requires distribution analysis across multiple documents.
- **False positive risk.** Moderate. Some skilled writers maintain consistent rhythm across genres as a stylistic choice.
- **Fix or remediation.** Deliberately vary rhythm by genre. Short, punchy paragraphs for recipes; longer for legal analysis; varied for technical explanation.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.


---

### A3-SS-010: Disproportionate Structure

- **Description.** Headings, bullets, recaps, labels, and report ceremony exceed the artifact's complexity or the venue's needs. The prose spends more structure on displaying organization than the ideas require.
- **Concrete examples.** A 500-word explanation uses eight headings and a concluding checklist; a three-point note wraps each point in a titled section, bold lead-in, recap, and “key takeaway”; an answer adds a framework name to an ordinary sequence of observations.
- **Location and register.** Explanatory articles, executive briefs, technical answers, social posts, and model-assisted edits.
- **Model attribution.** Model-agnostic editorial category. Current-model frequency is a controlled-test question, not an active family fingerprint.
- **Time evolution.** Timeless as an editorial failure; product and prompt defaults can change prevalence.
- **Sources.** August 2026 accepted first-tranche editorial synthesis; controlled frequency measurement pending.
- **Signal strength.** HIGH for editorial harm when the structure obscures or inflates simple content; not an authorship signal.
- **Base rate.** Unmeasured.
- **Causal hypothesis (ranked).** Alternatives include helpfulness or formatting defaults, prompt wording, genre imitation, ordinary human template use, and editor preference. Do not select one without evidence.
- **Detection difficulty.** Easy to observe; context-sensitive to judge.
- **False positive risk.** High in reference manuals, procedures, compliance material, and genuinely parallel complex artifacts.
- **Fix or remediation.** Remove headings, lists, recaps, and labels until each surviving structural element helps the reader navigate a real distinction. Keep genre-required structure.
- **Era status.** Active (timeless editorial category).
- **Zone tag.** BODY-PERSISTENT.
- **Evidence status.** Accepted generic editorial category; model-specific promotion not authorized.
- **Authorship inference.** Not established.

---

### A3-SS-011: Current-Claude Deliverable Padding

- **Description.** A report, Markdown document, handoff, or summary grows through filler sections, redundant summaries, boilerplate, unused-option surveys, overlong root explanations, or structure whose headings outweigh its substance. This is a current-family combination of existing deletion, recap, and proportional-structure failures; it is not unique to Claude.
- **Concrete examples.** A four-question audit receives nine sections plus an executive summary and a final recap; a code-change note explains alternatives that were never viable; a handoff repeats the same outcome under “Summary,” “What changed,” and “Key takeaways”; a short fix receives a framework name and a multi-level outline.
- **Location and register.** Reports, Markdown artifacts, summaries, documentation, pull-request descriptions, and long-session handoffs.
- **Model attribution.** Claude Opus 5 and Claude Fable 5 are the documented current-family scope. Other models and human template use remain plausible alternatives.
- **Time evolution.** Current-model overlay dated 2026-08; retain the generic component rules when this overlay ages.
- **Sources.** Anthropic's current Opus 5 prompting guide names longer reports, filler sections, redundant summaries, and boilerplate. Anthropic's current Fable 5 guide names unused-option surveys, long root explanations, and over-structured descriptions. Documentary research: `2026-08-22-deeper-current-model-patterns.md`, C03.
- **Signal strength.** HIGH for editorial harm after a task-coverage and deletion test; MEDIUM as one component of a current-Claude family assessment; never sufficient for provider attribution.
- **Base rate.** Not published by the provider; unmeasured in this project.
- **Causal hypothesis (ranked).** Unknown without a controlled comparison. Plausible alternatives include model defaults, broad prompts, requested comprehensiveness, house templates, and ordinary human over-structure.
- **Detection difficulty.** Medium. Map each section to a requested question, evidentiary need, decision, or action.
- **False positive risk.** Moderate to high for complex audits, legal analysis, reference manuals, and required templates.
- **Fix or remediation.** Delete or merge every section that does not answer a requested question, establish evidence, resolve a decision, or enable action. Preserve complexity the task genuinely requires.
- **Era status.** Active current-family overlay as of 2026-08.
- **Zone tag.** BODY-PERSISTENT and FULL-RESPONSE-HANDOFF.
- **Authorship inference.** Not established; evaluate only as an additive combined signal under the four-axis boundary.

---

## Section A3-TF: Technical and Formatting

### A3-TF-001: Placeholder Text and Incomplete Elements

- **Description.** Bracketed placeholders or unfilled template tokens left in published content. A user copied AI-generated text with placeholders they were supposed to fill in but forgot. Very strong drafting-residue signal.
- **Concrete examples.**
  1. `[Insert source here]`
  2. `[Add specific example]`
  3. `[URL of reliable source]`
  4. `[Citation needed]`
  5. `[Date]`
  6. `:contentReference[oaicite:0]` (XML-like ChatGPT artifact variant)
- **Location and register.** Universal where it appears. Strongest tell in any published content.
- **Model attribution.** All families. Sometimes ChatGPT's `oaicite` artifacts are the most distinctive.
- **Time evolution.** Stable.
- **Sources.** v3.1.0 criterion 18; `[cross-validated:manus-ai+perplexity+chatgpt]`. Perplexity recommends adding burstiness metric below 0.30 as a paired check.
- **Signal strength.** HIGH.
- **Base rate.** Low overall but definitive when present.
- **Causal hypothesis (ranked).** Primary: drafting workflow gap (user copied output without filling in placeholders). Secondary: training-data skew toward template-style outputs.
- **Detection difficulty.** Easy. Grep for bracket patterns.
- **False positive risk.** Very low when in published content.
- **Fix or remediation.** Fill in the placeholders or remove the bracketed text and restructure the paragraph.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-TF-002: Chatbot Communication Artifacts

- **Description.** Text that includes meta-communication between the chatbot and user, leaked into the published artifact. Includes salutations, valedictions, knowledge cutoff disclaimers, instructions to the user, offers to assist further. Cross-references A1-CLAUDE-009 ("I appreciate your" openers), A1-CLAUDE-011 ("I hope this helps" closer), A1-CLAUDE-013 (concierge tone closer), A1-GPT-009 ("In conclusion" closer), and A1-GPT-021 (knowledge-cutoff disclaimer, declining).
- **Concrete examples.**
  1. Salutation: "Dear [Reader]," or "Hello!"
  2. Valediction: "Thank you for your time and consideration."
  3. Instructions to user: "Here is your article on [topic]:"
  4. Knowledge cutoff: "As of my last training update in [date]..."
  5. Disclaimer: "Please consult a professional before..."
  6. Offer to assist: "If you have any questions or need further clarification, feel free to ask!"
- **Location and register.** Universal where it appears. Strongest tell in any published content (article, blog post, report) where the wrapper has leaked through.
- **Model attribution.** All families. Claude family particularly distinctive for "I hope this helps" closers and "I appreciate your" openers. GPT family for "Certainly!" openers and "Sure! Here's how..." framings. Gemini for "Without further ado" openers. Llama for "I'm just an AI, so take this with a grain of salt" disclaimers per `[deepseek]`. Grok for "I'm Grok, an AI by xAI. I'll keep it real."
- **Time evolution.** "As an AI language model" preamble near-extinct in current frontier models (Historical era status; persisted in GPT-3.5 and early GPT-4 2022-2024). "I hope this helps" persists. April 2025 OpenAI sycophancy rollback measurably reduced GPT's wrapper density.
- **Sources.** v3.1.0 criterion 19; `[cross-validated:manus-ai+perplexity+chatgpt+grok]`. Per `[perplexity]`: cross-link to A1-CLAUDE-020 (elevated vocabulary register) and A1-GPT-001 (saturated AI vocabulary cluster).
- **Signal strength.** HIGH. Among the clearest wrapper leaks in published prose.
- **Base rate.** Low in published content if the editor has done basic cleanup; high in raw output.
- **Causal hypothesis (ranked).** Primary: product wrapper personalization and RLHF helpfulness optimization. Secondary: training-data skew toward customer-service and dialogue corpora. Tertiary: system-prompt artifacts.
- **Detection difficulty.** Easy. Grep for the inventory.
- **False positive risk.** Very low. The phrases are characteristic of chatbot wrappers, not professional writing.
- **Fix or remediation.** Strip the openers and closers. Get into the substance. End on the substance.
- **Era status.** Active for most patterns. Historical for "As an AI language model" (declined after early-2024 RLHF updates).
- **Zone tag.** WRAPPER-OPENER for openers and salutations; WRAPPER-CLOSER for valedictions, "I hope this helps," and concierge closers.

---

### A3-TF-003: Broken or Fabricated Links and Technical Codes

- **Description.** Links, DOIs, ISBNs, or other technical identifiers that do not resolve or are invalid. LLMs hallucinate citations that look credible but do not actually exist. Cross-references A3-CS-001 (hallucinated citations) and A3-CS-003 (retrieval-citation mismatch). Per `[chatgpt]`'s PROMOTE recommendation: wrapper artifacts, fake URLs, and citation errors remain common; the criterion in v3.1.0 was about phrase repetition; v4.0 expands to include broken or fabricated links and technical codes.
- **Concrete examples.**
  1. URL leading to a 404 error.
  2. DOI that does not resolve to any article.
  3. ISBN with invalid checksum.
  4. Generic placeholder link: `[Link to source]`
  5. ChatGPT-specific artifact "turn0search0"
  6. (Per `[claude-exec-2026-05-18]`) Fabricated arxiv ID with plausible format but no underlying paper.
- **Location and register.** Universal where citations appear. Densest in research-style, journalistic, and policy prose.
- **Model attribution.** All families. Claude family (DOI fabrication per the bucket C catalog). GPT family (URL fabrication). Gemini (vague attribution per A1-GEMINI-002).
- **Time evolution.** Stable to growing. Per `[chatgpt]` and Stanford RegLab measurements: 17 to 33 percent legal-AI hallucination rates even with RAG augmentation persist into 2026.
- **Sources.** v3.1.0 criterion 20; Stanford RegLab / Magesh et al. (2024); Damien Charlotin database (2025) of over 1,455 sanctioned legal cases involving AI-fabricated citations; `[chatgpt]` PROMOTE.
- **Signal strength.** HIGH.
- **Base rate.** High in unedited AI output for research-style prompts. Per Walters and Wilder (2023): 30 to 55 percent hallucination rates in GPT-3.5; 18 to 29 percent in GPT-4 (cited from `[claude-exec-2026-05-18]`'s reference list). Per Chelli et al. (2024) JMIR: 56 percent error rate among GPT-4o citations.
- **Causal hypothesis (ranked).** Primary: training data lacks reliable signals for citation validity. Secondary: generative defaults under benchmark pressure (the model would rather produce a plausible-looking citation than admit ignorance). Tertiary: helpfulness optimization.
- **Detection difficulty.** Easy. Click links, verify DOIs resolve, check ISBNs with checksum validators.
- **False positive risk.** Very low when the link or identifier does not resolve.
- **Fix or remediation.** Verify every link and identifier before publication. Replace fabricated citations with real ones or remove the claim that required citation.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-TF-004: Citation Abnormalities

- **Description.** References that appear legitimate but reveal AI generation upon inspection. Citations repeated without proper reference tagging, real sources cited for unrelated content, citations formatted in unusual or inconsistent styles, multiple identical citations in close proximity. Cross-references A3-CS-001 (hallucinated citations) and A3-CS-002 (vague attribution).
- **Concrete examples.**
  1. Multiple identical citations in close proximity rather than using a single citation or cross-referencing.
  2. Real source cited for completely unrelated content (the citation exists but does not support the claim being made).
  3. Citation formatting inconsistent across the document (mix of APA, MLA, Chicago).
  4. Generic citations: "According to experts..." without naming experts.
  5. (Per Stanford RegLab) Real case law cited for a holding the case did not establish.
- **Location and register.** Body paragraphs. Densest in legal, academic, policy, and research-style prose.
- **Model attribution.** All families. Stanford RegLab measured 17 to 33 percent hallucination rates even with RAG-augmented legal AI.
- **Time evolution.** Stable to growing per `[chatgpt]`'s and DeepSeek's PROMOTE recommendation: retrieval-era source theater makes this more load-bearing.
- **Sources.** v3.1.0 criterion 21; Stanford RegLab / Magesh et al. (2024); Damien Charlotin database (2025).
- **Signal strength.** HIGH (promoted from MED).
- **Base rate.** Per Stanford RegLab: 17 to 33 percent legal AI hallucination rates even with RAG.
- **Causal hypothesis (ranked).** Primary: training data quality for citation correctness is low. Secondary: generative defaults under benchmark pressure. Tertiary: helpfulness optimization (the model produces a plausible citation when uncertain).
- **Detection difficulty.** Medium. Requires checking whether the cited source actually supports the claim.
- **False positive risk.** Low when the citation does not support the claim.
- **Fix or remediation.** Verify every citation supports the claim it is cited for. Replace or remove unsupported citations.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-TF-005: Suspiciously Long Edit Summaries and Caveat Paragraphs

- **Description.** In platforms with edit tracking (Wikipedia, GitHub commits, Google Docs revision history), unusually long, formal edit summaries written in first-person paragraphs. Human editors typically write brief, informal edit summaries; LLMs generate formal, comprehensive summaries when prompted to explain changes. The v4.0 entry extends the criterion to include "caveat paragraphs" appended at the end of articles, which serve a similar register-mismatch function. Per `[chatgpt]`'s REVISE: scope narrowly to platforms where edit summaries have stable norms. Per `[perplexity]`: most pronounced in GPT-4o A1-GPT-015 (caveat paragraph appended at end); reducing in Claude 4.
- **Concrete examples.**
  1. (Wikipedia-style) "Refined the language of the article for a neutral, encyclopedic tone consistent with content guidelines. Removed promotional wording, ensured factual accuracy, and maintained a clear, well-structured presentation."
  2. (Caveat paragraph) "It is important to note that this analysis is based on publicly available information and may not reflect the full complexity of the situation. Readers are encouraged to consult additional sources and exercise their own judgment."
  3. (Per `[claude-exec-2026-05-18]`) Disclaimer paragraph appended at the end of a technical article that the article's content did not warrant.
- **Location and register.** Edit summaries on tracked platforms; article closers for the caveat-paragraph variant.
- **Model attribution.** GPT-4o family (HIGH for caveat paragraphs per `[perplexity]`'s A1-GPT-015). Claude family (MEDIUM, reducing in Claude 4 per `[perplexity]`). Wikipedia editor catalog includes the pattern as a primary AI tell.
- **Time evolution.** Stable for Wikipedia edit summaries. Caveat paragraphs peaking in GPT-4o; reducing in newer versions.
- **Sources.** v3.1.0 criterion 22; `[chatgpt]` REVISE; `[perplexity]` REVISE; WikiProject AI Cleanup methodology.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate on Wikipedia and GitHub for tracked edits. Moderate in GPT-4o caveat closers.
- **Causal hypothesis (ranked).** Primary: training data exposure to formal editing prose (Wikipedia talk pages, GitHub commit conventions). Secondary: RLHF reward modeling for "comprehensive" explanations. Tertiary: system prompt artifacts on platforms that request edit summaries.
- **Detection difficulty.** Easy. Visual scan of length and formality.
- **False positive risk.** Moderate. Some careful human editors write thorough edit summaries.
- **Fix or remediation.** For edit summaries: shorten to a few words describing the change. For caveat paragraphs: remove unless the article genuinely needs limitations stated, in which case integrate the limitations into the relevant sections.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER for caveat paragraphs; outside the main artifact for edit summaries.

---

### A3-TF-006: System-Prompt Artifact Bleed

- **Description.** Phrases like "You are a helpful AI assistant" or visible system-prompt fragments leaking into output. Distinct from A3-TF-002 (chatbot communication artifacts) which are downstream wrapper artifacts; this is the upstream system-prompt configuration appearing literally. Per the Claude expansion's A3-NEW-010.
- **Concrete examples.**
  1. "You are a helpful AI assistant designed to provide accurate and thoughtful responses."
  2. (Per `[opus-expansion]`) Text beginning with the literal opening "As [persona name], I will..."
  3. "Your task is to..." appearing literally in published output where it was meant to be a system-level instruction.
  4. (Per `[claude-exec-2026-05-18]`) Visible role descriptions like "[ROLE: Senior Editor]" left in published copy.
- **Location and register.** Universal where it appears. Strongest tell at the very start of an article or response.
- **Model attribution.** All families. Most common when users are inexperienced with prompt engineering or when API requests have malformed system messages.
- **Time evolution.** Stable. The pattern depends more on user error than on model behavior.
- **Sources.** Claude expansion's A3-NEW-010; `[opus-expansion]`.
- **Signal strength.** HIGH (rare but definitive).
- **Base rate.** Low. Most production deployments suppress system-prompt leakage. Higher in self-hosted and developer-tool deployments.
- **Causal hypothesis (ranked).** Primary: system-prompt configuration error or copy-paste mishap. Secondary: model failure to distinguish between system context and user-facing output.
- **Detection difficulty.** Easy when visible.
- **False positive risk.** Very low.
- **Fix or remediation.** Remove the leaked content. Fix the upstream system-prompt configuration.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER.

---

### A3-TF-007: Date Inconsistency and Knowledge-Cutoff Contradiction

- **Description.** References to "current" dates that contradict the model's knowledge cutoff or release date; useful for forensic dating of outputs. The model claims to be discussing recent events but cites no source for events after its training data cutoff, or it describes 2026 events as "recent" when it was trained on data only through early 2025. Per the Claude expansion's A3-NEW-011.
- **Concrete examples.**
  1. A model with a knowledge cutoff in 2024 describing a 2026 event as "recent" without external retrieval context.
  2. Author bio claiming "as of [year]" where the year is later than the model's cutoff.
  3. (Per `[opus-expansion]`) Article references a "recent study" without naming it, in a context where the model could not have known about studies after its cutoff.
  4. (Per `[claude-exec-2026-05-18]`) Inconsistent date references within a single document (some dates from 2024, others from 2026) suggesting the model is fabricating temporal context.
- **Location and register.** Universal. Most useful in content claiming currency or recency.
- **Model attribution.** All families. Most pronounced when the model is asked to produce time-sensitive content without retrieval augmentation.
- **Time evolution.** Persistent. Newer models have later cutoffs but the pattern recurs whenever the writer asks for content beyond the cutoff.
- **Sources.** Claude expansion's A3-NEW-011; `[opus-expansion]`.
- **Signal strength.** MEDIUM. HIGH when paired with specific fabricated facts (cross-link to A3-TF-003).
- **Base rate.** Moderate in content with explicit "current" or "recent" framings.
- **Causal hypothesis (ranked).** Primary: knowledge cutoff staleness. Secondary: helpfulness optimization (the model would rather produce "current" content than acknowledge the cutoff). Tertiary: generative defaults under benchmark pressure.
- **Detection difficulty.** Medium. Requires cross-referencing dates against the model's known cutoff.
- **False positive risk.** Moderate. Some content legitimately uses approximate or evolving dates.
- **Fix or remediation.** Verify dates against the model's cutoff. For genuinely current content, use retrieval augmentation; for content within the cutoff window, ensure dates align.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.


---

### A3-TF-008: Current Tool, XML, and Reference Residue

- **Description.** Visible output contains a tool call rendered as prose, internal XML or thinking tags, current reference placeholders, or a broken reference graph. This is deterministic technical residue when unintended; it establishes tool or workflow involvement more strongly than it establishes who wrote the surrounding prose.
- **Concrete examples.** Visible structured tool-call arguments that never executed; internal XML or thinking-like tags; `oai_citation`, `attributableIndex`, `contentReference`, `turn0search0`, or comparable product markers; a named reference used but never defined; a reference declared but never used. UTM or referrer parameters may show a link's tool path but do not prove prose authorship.
- **Location and register.** Published articles, copied research answers, tool-heavy transcripts, references, and footnotes.
- **Model attribution.** Anthropic documents visible tool-call or internal-XML artifacts for Opus 5 when thinking is disabled. Current ChatGPT and other product markers are surface-specific and can survive copy-and-paste. Do not infer a model from a quoted fixture or copied link.
- **Time evolution.** Product markers change frequently; refresh the inventory without deleting historical markers.
- **Sources.** Anthropic's current Opus 5 prompting guide; current WikiProject AI Cleanup field evidence; documentary research `2026-08-22-deeper-current-model-patterns.md`, C05.
- **Signal strength.** HIGH as a technical QA defect when unintended; LOW for provider or prose-authorship attribution without corroborating provenance.
- **Base rate.** Unmeasured and surface-dependent.
- **Causal hypothesis (ranked).** Product rendering failure, malformed tool handling, incomplete copy-and-paste, reference export bug, or intentional quotation.
- **Detection difficulty.** Easy for literal markers; medium for reference-graph mismatches.
- **False positive risk.** Very low for unintended literal residue; high for authorship claims.
- **Fix or remediation.** Remove unintended residue, repair the reference graph, verify that cited sources support the claims, and correct the upstream renderer or export path. Preserve literal markers when the artifact is teaching or testing them.
- **Era status.** Active; inventory dated 2026-08.
- **Zone tag.** BODY-PERSISTENT and WRAPPER-ARTIFACT.
- **Authorship inference.** Tool involvement may be supported; surrounding-text authorship is not established.

---
