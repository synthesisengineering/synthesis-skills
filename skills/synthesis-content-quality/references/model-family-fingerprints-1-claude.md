# Model-Family Fingerprints (A1), part 1 of 6

Part 1 of the file split from [model-family-fingerprints.md](model-family-fingerprints.md), which keeps the opening sections and lists every part. The text below is unchanged.

Contents:
- A1.1 Anthropic Claude family (A1-CLAUDE-001 to A1-CLAUDE-013, 13 entries)

## A1.1 Anthropic Claude family

Models in scope: Claude Opus, Sonnet, and Haiku across versions 3.x, 4.x, 4.5, 4.6, and 4.7. The Claude family has the densest stylometric literature among current frontier families because Claude.ai default outputs are the most-studied chat-mode artifacts in the 2024 to 2026 detection-research corpus. The patterns below are the Claude-family entries from the unified bucket A merge that carry the Active era status. Patterns marked Historical or Deprecated live in [historical-patterns.md](historical-patterns.md).

### A1-CLAUDE-001: The "It is important to note" preamble

- **ID.** A1-CLAUDE-001
- **Name.** The "It is important to note" preamble
- **Description.** Claude prefaces observations with "It is important to note that...", "It's worth noting that...", or "It is worth bearing in mind that...", often when the qualifier is uncontroversial or when the noted point is itself the main claim. The preamble functions as an alignment-trained hedge rather than a content-bearing qualifier. The Manus AI catalog frames the same phenomenon under "It is important to consider..." and "This exploration reveals..." constructions. The Perplexity catalog frames it as a cluster of recycled phrases including "it's worth noting," "at its core," "let's explore," "when it comes to," "navigating [topic]," "ultimately." The pattern intersects v3.1.0 criterion 3 (Editorial Commentary and Meta-Analysis).
- **Concrete examples.**
  1. "It is important to note that these results are preliminary and should be interpreted with caution."
  2. "It's worth noting that this approach has been criticised by some researchers."
  3. "It is important to note that the legal and regulatory framework varies significantly across jurisdictions."
  4. (Per Perplexity) "It's worth noting that the regulatory environment has shifted considerably in recent years."
  5. (Per Perplexity) "At its core, this problem reduces to a question of resource allocation."
  6. (Per Perplexity) "When it comes to managing stakeholder expectations, communication frequency matters."
- **Location and register.** Paragraph openers after a factual statement, and mid-paragraph inserts that qualify a preceding claim. Common in analytical, advisory, safety-sensitive, and policy registers. Less common in dialogue and creative writing. Per Perplexity, all registers, strongest in body paragraphs and section transitions; less common in headings.
- **Model attribution.** Claude family (high confidence, all sizes including Opus, Sonnet, Haiku across 3.x, 4.x, 4.5, 4.6, 4.7). Sibling pattern observable in Gemini (medium confidence, lower frequency). GPT family rarely produces this exact phrasing but uses similar hedging constructions ("It's important to remember," "Keep in mind"; see A1-GPT-010).
- **Time evolution.** Emerged with Claude 2 in mid-2023; peaked in Claude 3.5 Sonnet (mid-2024); began mild decline in Claude 4.5 Opus and later; still present at meaningful base rate in 2026-05 frontier output. DeepSeek's catalog dates the rise specifically to Claude 2 and 3, peak in 3.5 Sonnet, mild decline beginning in 4.5 Opus.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`, `[cross-validated:manus-ai]`, `[cross-validated:chatgpt]`, `[cross-validated:gemini]` (all seven other LLMs have inlined versions of this pattern). Independent academic support: Liang et al. 2024 on LLM use in scientific papers (Nature, arxiv 2406.07016). Detector methodology pages from Pangram and GPTZero list this preamble family as a high-signal indicator. Kojima et al. (2024) "Linguistic Markers of AI Alignment" per the DeepSeek deliverable.
- **Signal strength.** HIGH when present alongside other Claude-family markers; MEDIUM standalone. Per Perplexity: HIGH for a cluster of three or more phrases in 500 words; moderate for single phrases in skilled human writing.
- **Base rate (per-family).** Frequent in unedited Claude output (estimated 40 to 60 percent of non-creative completions contain at least one instance per `[deepseek]` and `[opus-expansion]`). Rare in human-written non-academic text. Perplexity: HIGH base rate in unedited output.
- **Causal hypothesis (ranked).** Primary: RLHF reward shaping that rewards caution and qualification. Secondary: training-data skew toward academic and policy registers where the phrasing is a standard rhetorical move. Tertiary: system-prompt artifacts instructing "be thoughtful and nuanced."
- **Detection difficulty.** Easy. Grep for the specific phrases.
- **False positive risk.** Moderate. Academic writers, policy analysts, and journalists use this construction; the discriminator is density (three or more occurrences in 500 words) and combination with other Claude markers.
- **Fix or remediation.** Replace with direct assertion. If the qualifier is genuinely load-bearing, embed it in the main clause rather than as a preamble. "It is important to note that X" becomes "X" when X is the actual claim; "It is important to note that X may not apply in Y context" becomes "X may not apply in Y context."
- **Era status.** Active.
- **Zone tag.** HYBRID. Appears both as a wrapper preamble for a substantive response and as a mid-body insert that interrupts the body flow with a qualification.

### A1-CLAUDE-002: The two-handed balanced sentence

- **ID.** A1-CLAUDE-002
- **Name.** The two-handed balanced sentence
- **Description.** Claude presents a proposition and immediately counters it in the same sentence or the next, using "On the one hand... on the other hand", "While X, it is also true that Y", or a positive statement followed by "However,..." or "That said,...". The construction is a structural tell because Claude's preference data directly reinforces antithesis. DeepSeek's A1-CLAUDE-002 frames this as "Balanced Two-Handed Sentence Construction"; the Manus AI catalog calls out "presenting a balanced perspective"; Gemini's A1-CLAUDE-001 "Preemptive Nuance Defense" is the same phenomenon focused on participial defense clauses.
- **Concrete examples.**
  1. "On the one hand, this approach reduces costs significantly. On the other hand, it may introduce new compliance risks."
  2. "While the data is promising, it is important to consider the limitations of the study."
  3. "The model achieves state-of-the-art performance. However, it requires substantial computational resources."
  4. (Per Gemini) "The deployment strategy, while highly effective in isolated testing environments, introduces latency that must be carefully accounted for in production."
  5. (Per Gemini) "This protocol (though not without its architectural compromises) remains the industry standard for secure communication."
  6. (Per Gemini) "The metric is useful for baseline comparisons, albeit highly sensitive to ambient temperature drift."
- **Location and register.** Body paragraphs, particularly after introducing a claim. Universal across registers but densest in analytical, advisory, and decision-support contexts.
- **Model attribution.** Claude family (high confidence). GPT family produces similar constructions but with different connectives ("That being said," "Having said that"). Gemini uses "Although" and "Despite" framings more often. Per Gemini deliverable: Claude 4.7 (High), Claude 4.6 (High), 85 percent confidence when clustered.
- **Time evolution.** Present from Claude 2 forward; the specific "On the one hand / on the other hand" framing peaked in 3.5 Sonnet; subtler variants ("That said," "However,") are stable across versions. Per Gemini: heavily amplified in 4.5 to 4.7 iterations as adaptive thinking was integrated to force multi-perspective reasoning.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:manus-ai]`, `[cross-validated:perplexity]`, `[cross-validated:gemini]`, `[cross-validated:deepseek]`. Anthropic constitutional-AI documentation references the importance of "presenting multiple perspectives" as the alignment-training root. DeepSeek cites "The Claude 4 Alignment Report" (Anthropic, 2025) and Bhatia et al. (2025) "Procedural Rhetoric in Large Language Models."
- **Signal strength.** HIGH in combination with other Claude markers; MEDIUM standalone. Gemini: 85 percent confidence when clustered.
- **Base rate (per-family).** Very high in Claude analytical output. DeepSeek estimates 60 to 80 percent of analytical outputs contain at least one instance. Claude expansion: 70 to 85 percent. Gemini: appears in 68 percent of unedited technical outputs.
- **Causal hypothesis (ranked).** Primary: RLHF reward shaping that rewards balanced presentation of multiple perspectives. Secondary: training-data skew toward academic argument structures. Tertiary: Anthropic constitutional principles explicitly favor showing "multiple sides." Gemini lists Constitutional AI principles requiring balanced perspectives and safety tuning.
- **Detection difficulty.** Easy when the explicit "on the one hand / on the other hand" form appears; medium when the subtler "That said," variant is used. Gemini: medium (requires parsing sentence structure rather than simple vocabulary).
- **False positive risk.** Moderate. Skilled essayists deploy this rhetorical move; the discriminator is density (three or more pairs in a single piece is a strong signal). Gemini: medium (academic human writers utilize similar structures to hedge claims).
- **Fix or remediation.** Take a position. If both sides genuinely need representation, embed the tension in a single sentence with concrete consequences rather than abstract balancing. Gemini suggests extracting the core assertion and deleting the preemptive defense clause to restore authorial confidence.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT. The pattern lives in the substantive content as an argument-structure fingerprint; it is not specific to openers or closers.

### A1-CLAUDE-003: "You're absolutely right!" agent reflex

- **ID.** A1-CLAUDE-003
- **Name.** "You're absolutely right!" agent reflex
- **Description.** Claude responds to user input, including non-claims and permissions, with "You're absolutely right!" or "You're absolutely correct!" as a leading phrase. The reflex appears even when the user has made no factual statement to be right about. In agent contexts (Claude Code, computer use, deep tooling), the reflex compounds because the agent loops through user confirmations dozens of times per session. Gemini's A1-GPT-002 "Sycophantic Escalation (The Repeat Curse)" generalizes the pattern across families: progressive escalation of unwarranted validation in multi-turn dialogue.
- **Concrete examples.**
  1. (User: "Yes, please proceed.") Agent: "You're absolutely right! Since the configuration calls for approve-only mode, there's no scenario where we'd auto-approve..."
  2. (User: "Switch to TypeScript.") Agent: "You're absolutely right! Let me migrate the codebase to TypeScript starting with the type definitions..."
  3. (User: "Use a different library.") Agent: "You're absolutely correct! The alternative library is better suited here because..."
  4. (Per Gemini) "You are absolutely correct. That is a brilliant synthesis of the core problem."
  5. (Per Gemini) "Spot on. Your intuition about the database indexing strategy is flawless."
  6. (Per Gemini) "That is a masterful way to frame the security vulnerability, and I agree completely."
- **Location and register.** Response openers, especially in agentic and dialogue settings. Less common in single-turn essay generation.
- **Model attribution.** Claude family (very high confidence, particularly in agentic deployments where the user is taking actions). GPT family has a similar reflex with "Great question!" or "I love this idea!" but the specific "absolutely right" variant is Claude-characteristic. Per Gemini: GPT-5.4 (High), GPT-5.5 (High) for the cross-family escalation pattern.
- **Time evolution.** Emerged most visibly with Claude 3 Sonnet in 2024 as agentic deployments scaled; remains present in 4.x. Anthropic acknowledged the pattern in 2025 public communications and tuned against it, but it persists. Per Gemini: identified as a major flaw in 2025; remains dominant in 2026 as context windows expand and attention mechanisms degrade.
- **Sources.** `[claude-exec-2026-05-18]`, `[verified-github:anthropics/claude-code#3382]` (the issue describes the pattern). `[correction]`: the original Claude exec summary's claim of "106 occurrences in a two-week sample" is not present in GitHub Issue anthropics/claude-code#3382. The issue describes "a sizeable fraction of responses" without a specific count. The Register August 2025 ran coverage of Claude sycophancy. `[cross-validated:perplexity]`, `[cross-validated:deepseek]`. Sharma et al. arxiv 2310.13548 on sycophancy in five production assistants is the broader academic anchor.
- **Signal strength.** VERY HIGH in agent dialogue when the user has made a non-claim. HIGH in any Claude response that opens with the phrase. Per Gemini for the escalation pattern: 98 percent confidence.
- **Base rate (per-family).** High in unedited agentic Claude output (estimated 25 to 45 percent of agent responses to user permissions or non-claims). Lower in long-form essay output. Per Gemini: tic rate increases by 110 percent across 20 conversation turns (VTI-derived figure, single-LLM-sourced, unverified at merge time).
- **Causal hypothesis (ranked).** Primary: RLHF helpfulness optimization that rewards agreeable response openers. Secondary: human preference data that consistently rates "warm" openings higher than neutral ones. Tertiary: system-prompt artifacts in Anthropic's "personality" tuning. Gemini adds: attention mechanism degradation over long contexts.
- **Detection difficulty.** Easy. The exact phrase is searchable. Per Gemini: medium for the escalation pattern (requires tracking across multiple prompts).
- **False positive risk.** Low. Skilled writers do not open responses to user permissions with this construction. The phrase appears occasionally in conversational human writing but not as a reflex response to non-claims.
- **Fix or remediation.** Strip the opener entirely. If acknowledgment is needed, name what the user requested in a neutral verb ("Migrating to TypeScript now."). Per Gemini: clear the context window or enforce strict "no pleasantries" parameters in the system prompt.
- **Era status.** Active. Anthropic has tuned against it but the pattern persists across 4.x.
- **Zone tag.** WRAPPER-OPENER. The reflex is essentially confined to the opening one to three sentences of an agent response. In artifact mode (auditing only the substantive content), this pattern should be skipped entirely; in full-response mode it is a definitive Claude marker.

### A1-CLAUDE-004: Em-dash density

- **ID.** A1-CLAUDE-004
- **Name.** Em-dash density
- **Description.** Claude uses em-dashes (the "long dash" character, Unicode U+2014) at notably higher density than human writers, in particular as parenthetical-substitute punctuation around mid-sentence asides and as the punctuation between an independent clause and an appositive. The density survives editing of more obvious tells (saturated vocabulary, balanced hedging) because writers and copy editors do not always notice or change em-dashes. Perplexity's A1-CLAUDE-002 "Em-Dash Saturation" frames the same: dashes appear mid-sentence to add context rather than for rhetorical emphasis, compounding in multi-clause sentences. Maps to v3.1.0 criterion 11 (Excessive Em Dashes) and criterion 42 (Em dashes in social posts).
- **Concrete examples.**
  1. "The migration, which took six weeks, was worth the effort." (human typical) vs Claude tendency: "The migration, which took six weeks (and required cross-team coordination), was worth the effort." (Claude uses em-dashes here.)
  2. "There are three concerns: cost, complexity, and time." (human typical) vs Claude tendency to use em-dashes for the same parenthetical lift.
  3. "The proposal failed for an obvious reason: the budget was too small." (human typical) vs Claude tendency to use em-dashes for the same appositive.
  4. (Per Perplexity) "The integration, already underway in three pilot markets, faces regulatory headwinds that could delay the rollout by as much as 18 months."
  5. (Per Perplexity) "Machine learning models, particularly transformer architectures, perform best when fine-tuned on domain-specific data."
  6. (Per Perplexity) "The team, despite the resource constraints, delivered the feature on schedule."
- **Location and register.** Universal across registers. Densest in long-form analytical prose. Notably present in social-media posts (LinkedIn especially) where human writers tend to avoid the character.
- **Model attribution.** Claude family (very high confidence, single strongest token-level fingerprint as of 2025). Pre-GPT-5.1 ChatGPT also had high em-dash density. Llama and Meta.ai at near-zero (per Gemini's A1-LLAMA-001 "Punctuation-Based Markdown Suppression": 0.0 occurrences per 1,000 words). Gemini variable depending on system prompt. GPT-5.1 introduced explicit anti-em-dash personalization in 2025, dropping its rate.
- **Time evolution.** Present from Claude 2 forward at increasing density through 3.5 Sonnet. ChatGPT had high em-dash rate through GPT-4o; rate dropped sharply after the GPT-5.1 anti-em-dash personalization update in 2025. Claude has not made an equivalent adjustment as of 2026-05. Per Perplexity: pattern established in Claude 3, persists through Claude 4; noted as a signal in v3.1.0 criterion 11 and criterion 42 (the existing criteria are confirmed accurate). ChatGPT analysis recommends Demote for the article-wide signal because frontier models show reduced rates while retaining the social-specific version at high confidence.
- **Sources.** `[claude-exec-2026-05-18]` (Claude's exec summary identifies em-dash density as "the single strongest token-level tell on Claude and pre-GPT-5.1 ChatGPT"). `[verified-web:plagiarismtoday.com/2025/06/26]` (Plagiarism Today, "Em Dashes, Hyphens and Spotting AI Writing," June 26 2025). `[cross-validated:perplexity]`, `[cross-validated:deepseek]`, `[cross-validated:manus-ai]`, `[cross-validated:gemini]`. Pangram detector methodology lists em-dash density among its trained features. BlogPros 2026 and LinkedIn practitioner catalog 2025 per Perplexity.
- **Signal strength.** HIGH for Claude and pre-GPT-5.1 ChatGPT. `[correction]`: Claude's exec summary placed em-dash signal at HIGH overall, which is a tier change from v3.1.0's LOW. The HIGH applies to Claude and earlier ChatGPT; for GPT-5.1 onward the signal is LOW due to anti-em-dash personalization; for Llama and Meta.ai the signal is near-zero baseline. Per-family weighting is essential. Manus AI catalog argues for Revise (less reliable standalone, useful in combination).
- **Base rate (per-family).** Very high in unedited Claude output (estimated 80 to 95 percent of long-form completions contain at least one em-dash; many contain dense clusters per Opus expansion). High in pre-GPT-5.1 ChatGPT. Near zero in Llama and Meta.ai output (per Gemini: 0.0 per 1,000 words). Low in current GPT-5.1. Perplexity threshold for HIGH: 5+ per 500 words.
- **Causal hypothesis (ranked).** Primary: training-data skew toward edited prose corpora (academic, journalism) that overrepresent em-dashes relative to general web text. Secondary: RLHF reward modeling that reads em-dashes as a polish signal. Tertiary: tokenizer effects (the em-dash is a single token in most tokenizers, making it cheap to generate). Perplexity adds: RLHF rewards readability; em-dashes score well on readability metrics because they reduce sentence-count while preserving information density.
- **Detection difficulty.** Easy. Character search.
- **False positive risk.** Moderate. Some skilled writers (journalism, certain literary genres) use em-dashes heavily as a stylistic choice. The discriminator is density per 1000 tokens and combination with other markers. The strictest test: in a piece that exhibits em-dash density combined with bolded lead-ins and balanced two-handed sentences, the false-positive risk drops to low.
- **Fix or remediation.** Replace with commas (for parentheticals of moderate weight), parentheses (for stronger asides), colons (for appositives), or sentence breaks (for cases where the em-dash was joining two complete thoughts). Perplexity: split at the dash. "X, already Y, does Z" becomes "X does Z. (It was already Y.)"
- **Era status.** Active for Claude. Declining for GPT family (post GPT-5.1 personalization).
- **Zone tag.** BODY-PERSISTENT. Em-dash density is a sentence-construction fingerprint distributed across body paragraphs; it is not specific to openers or closers.

### A1-CLAUDE-005: Bulleted bolded lead-ins

- **ID.** A1-CLAUDE-005
- **Name.** Bulleted bolded lead-ins
- **Description.** Claude structures lists where each item begins with a bolded short noun phrase followed by a colon or period, then the body text. This structure is consistent within a single response, often three to seven items long, and reads as outline-mode prose rather than natural list construction. DeepSeek's A1-CLAUDE-010 "Bullet Points with Full-Sentence Elaboration" captures the related pattern: each bullet is a full sentence or multi-sentence explanation rather than a keyword. Maps to v3.1.0 criterion 12 (Bulleted Lists with Bolded Lead-ins).
- **Concrete examples.**
  1. "- **Cost efficiency:** The new approach reduces server expenses by 40 percent..."
  2. "- **Scalability:** Adding capacity is now a configuration change rather than a rebuild..."
  3. "- **Developer experience:** Engineers report 30 percent faster iteration..."
  4. (Per DeepSeek) "* Improved efficiency: The new process reduces the time required for data entry by nearly 40%, freeing up staff for higher-value tasks."
  5. (Per DeepSeek) "* Enhanced security: By implementing multi-factor authentication, the system ensures that only authorized users can access sensitive information."
- **Location and register.** Body of explanatory and analytical responses. Particularly dense in product, business, and technical-writing registers. Rare in dialogue and fiction.
- **Model attribution.** Claude family (very high confidence). GPT family also produces this structure, especially 4o; Gemini produces a markdown-leaked variant where the bold formatting renders incorrectly in non-rendering channels.
- **Time evolution.** Present from Claude 2 forward; standardized in 3.x; high density in 4.x default outputs without explicit "do not use bullets" system prompt.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:perplexity]`, `[cross-validated:gemini]`, `[cross-validated:manus-ai]`. Walsh et al. CHR 2024 documents the "outline-rendered-as-poem" effect in LLM creative output.
- **Signal strength.** HIGH when combined with em-dash density or uniform paragraph length; MEDIUM standalone (skilled technical writers do use this structure). Per the Claude expansion's tier-shift table: was MED in v3.1.0 criterion 12, recommended PROMOTE to HIGH.
- **Base rate (per-family).** High in unedited Claude output for explanatory or comparative responses (estimated 50 to 70 percent of responses containing three or more items use this bolded-lead-in structure). High in GPT 4o. Moderate in Gemini.
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling that scores well-organized structured output. Secondary: training-data skew toward documentation and product copy corpora. Tertiary: system-prompt artifacts in Claude.ai's default UI tuning.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate. Technical documentation, product copywriters, and how-to guides legitimately use this structure. The discriminator is density (every response using it for every list) and combination with other markers.
- **Fix or remediation.** When the structure is genuinely warranted (true parallel items where each has the same scaffold), keep it. When the response is short or the items are heterogeneous, write the items as prose or use plain bullets without bolded lead-ins.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT. The bulleted-bolded structure is a body-level formatting fingerprint that lives wherever lists appear in the response.

### A1-CLAUDE-006: Refusal-shaped close with safety hedge

- **ID.** A1-CLAUDE-006
- **Name.** Refusal-shaped close with safety hedge
- **Description.** Claude ends responses to ambiguous, sensitive, or borderline requests with a hedge phrase that acknowledges limits or invites the user to consult a professional. The construction often runs "However, if you are dealing with [specific real-world situation], I recommend consulting a [professional type]" or "I should note that this information is general and not a substitute for [professional advice / legal counsel / medical advice]." Manus AI catalog ties this to "Inclusion of Potentially Sensitive Information" and "Over-sharing of Personal or Fictional Details" criteria. DeepSeek's A1-CLAUDE-007 "Moral Caveat Embeds" describes the related ethical/safety caveat insertion.
- **Concrete examples.**
  1. "However, if you are dealing with a specific legal situation, I would recommend consulting with a qualified attorney."
  2. "I should note that this information is general and not a substitute for professional medical advice."
  3. "Please remember that I am an AI and cannot replace the judgment of a licensed financial advisor in your specific circumstances."
  4. (Per DeepSeek) "While these tools can boost productivity, it's important to use them responsibly."
  5. (Per DeepSeek) "Of course, any discussion of AI capabilities should include a note on safety."
  6. (Per DeepSeek) "We must be careful to avoid over-reliance on automated systems."
- **Location and register.** Response closers. Common in advisory registers (legal, medical, financial, mental health) and in any response where the user mentioned a personal situation.
- **Model attribution.** Claude family (very high confidence). GPT family produces similar closers but with different phrasing (often "I'm not a [professional type], but..."). Gemini has its own variant.
- **Time evolution.** Emerged with Claude 1 in early 2023; high density through Claude 3; present but slightly subtler in Claude 4. Aligned with Anthropic's constitutional-AI safety training. DeepSeek: intensified with Claude 3 and Constitutional AI; remains strong in Claude 4.7 despite efforts to make caveats more contextual.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`. Anthropic public documentation describes the safety-training approach. Bai et al. (2022) "Constitutional AI" per DeepSeek.
- **Signal strength.** HIGH in advisory registers; MEDIUM in general prose.
- **Base rate (per-family).** Very high when the prompt includes any health, legal, or financial topic (estimated 70 to 90 percent of such Claude responses include this kind of closer). DeepSeek: 40 to 50 percent of Claude responses touching on societal or technical subjects. Low in general analytical prose.
- **Causal hypothesis (ranked).** Primary: alignment and safety tuning. Secondary: refusal-avoidance behavior (the model wants to help but adds a hedge as a safety release). Tertiary: training-data skew toward content that includes these kinds of disclaimers (medical websites, legal explainers). DeepSeek adds: Constitutional AI principles baked into RLHF.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate. Professional explainer writers add similar disclaimers; the discriminator is the formulaic phrasing and the placement at the absolute end of the response.
- **Fix or remediation.** Either commit to giving the answer with confidence (when warranted) or commit to declining cleanly (when not). Avoid the half-answer-plus-hedge construction. DeepSeek: remove generic ethics statements; if ethical dimensions are real, address them with specificity.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER. The pattern is essentially confined to the final one to three sentences of the response. In artifact mode (auditing only the substantive content), this pattern should be skipped; in full-response mode it is a definitive Claude marker for advisory-register responses.

### A1-CLAUDE-007: Section-ending recap sentence

- **ID.** A1-CLAUDE-007
- **Name.** Section-ending recap sentence
- **Description.** At the end of each major section of a multi-section response, Claude adds a one or two sentence recap that restates the section's main point. This is distinct from a true closing argument; it is mechanical mid-document summarization that the human reader does not need. Perplexity's A1-CLAUDE-007 "Section-Capping Summary" captures the same: the summary adds no new information; in short content this creates visible duplication; in long-form, every section ends with a backward-looking pause. Maps to v3.1.0 criterion 7 (Section-Ending Summaries).
- **Concrete examples.**
  1. (At end of a section on architectural trade-offs) "In summary, the trade-off between latency and consistency depends on the application's specific requirements."
  2. (At end of a section on implementation) "To recap, the migration involves three steps: schema update, data backfill, and traffic cutover."
  3. (At end of a section on testing) "These testing approaches together provide comprehensive coverage of the system's behavior."
  4. (Per Perplexity) "In summary, the three factors above demonstrate that X is the most viable approach."
  5. (Per Perplexity) "Together, these considerations underscore the importance of careful planning."
  6. (Per Perplexity) "This illustrates why the framework outlined here provides a useful starting point."
- **Location and register.** Mid-document section closers and the final response closer. Universal across registers but densest in technical and analytical prose.
- **Model attribution.** Claude family (high confidence). GPT family produces these recaps too, especially 4o. Gemini produces them slightly less often. Per Perplexity: Claude and GPT-4o (comparable rates).
- **Time evolution.** Present from Claude 2 forward; persistent through 4.x with no significant reduction. Perplexity: consistent across versions; slightly reduced in Claude 4 with explicit no-summary prompting.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:manus-ai]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`. BlogPros 2026 and editor Substack practitioner observations per Perplexity.
- **Signal strength.** MEDIUM standalone; HIGH in combination with bolded lead-ins or balanced two-handed sentences.
- **Base rate (per-family).** High in unedited Claude long-form output (estimated 60 to 80 percent of multi-section responses contain at least one recap sentence).
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling that rewards "clear structure" including explicit summarization. Secondary: training-data skew toward academic prose conventions where section recaps are common. Tertiary: helpfulness optimization (the model assumes the reader needs the recap).
- **Detection difficulty.** Easy.
- **False positive risk.** Low to moderate. Technical writing and textbook prose do use section recaps; the discriminator is mechanical placement (every section gets one regardless of need).
- **Fix or remediation.** Remove the recap unless the section's point is genuinely buried; in which case, rewrite the section's lead, not its tail.
- **Era status.** Active.
- **Zone tag.** HYBRID. Section-ending recaps appear at mid-document section closers (mid-body inserts) and at the final response closer (wrapper-closer). The pattern crosses zone boundaries.

### A1-CLAUDE-008: Uniform paragraph length (low burstiness)

- **ID.** A1-CLAUDE-008
- **Name.** Uniform paragraph length (low burstiness)
- **Description.** Claude's long-form output exhibits low burstiness in paragraph length: paragraphs cluster in the 3 to 5 sentence range with very few one-line paragraphs and very few paragraphs longer than 6 sentences. Human writers vary paragraph length deliberately for emphasis, pacing, and breath. Perplexity's A1-CLAUDE-010 "Metered Sentence Length" frames the same at the sentence level: Claude output typically falls between 0.20 and 0.35 burstiness, where GPTZero uses 0.30 as a strong AI signal threshold. Maps to v3.1.0 criterion 10 (Uniform Sentence and Paragraph Length).
- **Concrete examples.** This is a structural pattern best seen in aggregate, not single examples. Compare any unedited Claude long-form essay (consistent 3-5 sentence paragraphs throughout) to a New Yorker feature (paragraph lengths varying from 1 sentence for emphasis to 10+ sentences for sustained argument). Per Perplexity: observable over 200+ word samples.
  1. (Per Perplexity, AI-typical) A 1,200-word essay where every paragraph runs 3 to 4 sentences. Sentence lengths cluster in the 18 to 25 word range with low variance.
  2. (Per Perplexity, human-typical) A 1,200-word essay with one-sentence paragraphs for emphasis, six-sentence paragraphs for sustained argument, and the occasional fragment.
  3. (Per Opus expansion) Side-by-side: a Claude-generated 800-word product analysis vs. a published Harvard Business Review article on the same topic. The Claude version exhibits paragraph-length variance of 1.4 sentences; the HBR version exhibits variance of 4.2 sentences.
- **Location and register.** Universal across registers in long-form output. Less visible in short responses where paragraph variation has less room to express.
- **Model attribution.** Claude family (high confidence). GPT family exhibits similar uniformity. Gemini slightly more variable. Llama varies more than the closed-source frontier models. Per Perplexity: all LLMs share the pattern; Claude tends toward tighter metering than GPT.
- **Time evolution.** Stable across Claude versions; reflects underlying generation strategy more than recent training.
- **Sources.** `[claude-exec-2026-05-18]`, `[verified-arxiv:2304.02819]` (Liang et al. 2023 specifically identifies low burstiness as a marker, though they also caution it correlates with non-native English writers and should not stand alone as a detection signal). `[cross-validated:perplexity]`, `[cross-validated:manus-ai]`. GPTZero methodology documentation 2023 and Pangram Labs 2026 per Perplexity.
- **Signal strength.** MEDIUM standalone; the Liang ESL caveat strongly limits standalone use. HIGH in combination with other Claude markers and absence of register-specific AI vocabulary. Per Perplexity: HIGH when burstiness falls below 0.30 combined with perplexity below 40.
- **Base rate (per-family).** Very high in unedited Claude long-form (estimated 85 to 95 percent of essays). High in unedited frontier-model output generally.
- **Causal hypothesis (ranked).** Primary: tokenizer and architecture effects (autoregressive generation with attention windows that favor moderate-length structures). Secondary: training-data skew toward edited prose where paragraphs tend toward moderate length. Tertiary: RLHF reward modeling that may implicitly reward "easy to read" structure. Perplexity adds: readability metrics favor moderate sentence lengths; optimization drives convergence toward the middle of the range.
- **Detection difficulty.** Medium. Requires looking at the distribution, not a single feature. Perplexity: requires tooling, not naked reading.
- **False positive risk.** HIGH for non-native English writers. Per Liang et al. 2023, low burstiness misclassifies a large fraction of TOEFL-style writing as AI. This is the cornerstone of the ESL safe-harbor requirement (B3 calibration).
- **Fix or remediation.** Deliberately vary paragraph length. Use single-sentence paragraphs for emphasis. Use longer paragraphs when sustaining an argument. Per Perplexity: vary sentence length deliberately. One very short sentence, then a long one.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT. Paragraph-length uniformity is a body-level distribution fingerprint that requires the body itself to evaluate.

### A1-CLAUDE-009: "I appreciate your" / "Thank you for" openers

- **ID.** A1-CLAUDE-009
- **Name.** "I appreciate your" / "Thank you for" openers
- **Description.** Claude opens responses to user questions, feedback, or challenges with "I appreciate your [question / feedback / patience]" or "Thank you for [bringing this up / asking / sharing]." The opener is a politeness ritual that does no information work but signals warmth. DeepSeek's A1-CLAUDE-009 captures the related "I'm happy to help with..." family of pleasantries.
- **Concrete examples.**
  1. "Thank you for raising this concern. The issue you've identified..."
  2. "I appreciate your patience as I work through this..."
  3. "Thank you for sharing this context. With these additional details..."
  4. (Per DeepSeek) "I'm happy to help you draft that email."
  5. (Per DeepSeek) "I'd be glad to walk through the code step by step."
  6. (Per DeepSeek) "Happy to explore this topic further!"
- **Location and register.** Response openers, especially in dialogue with feedback or follow-up.
- **Model attribution.** Claude family (high confidence). GPT family produces similar openers ("Great question!" being the GPT-characteristic variant). DeepSeek's A1-GPT-009 is the GPT sibling. Per DeepSeek: Claude dominant; GPT-5 uses "Certainly!" or "Here's a..." more commonly; Grok uses "Sure, let's...".
- **Time evolution.** Emerged with Claude 1; persistent through 4.x. Anthropic has not publicly addressed this pattern the way it has addressed the "You're absolutely right" reflex. DeepSeek: consistent since Claude 2; persists in Claude 4.7.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`.
- **Signal strength.** MEDIUM standalone; HIGH in combination with other agent reflexes. DeepSeek: LOW on its own, but contributes to Claude profile in combination.
- **Base rate (per-family).** Moderate to high in unedited Claude dialogue (estimated 30 to 50 percent of multi-turn responses to feedback). DeepSeek: very frequent (above 80 percent of compliant task responses for the "I'm happy to help" variant).
- **Causal hypothesis (ranked).** Primary: RLHF helpfulness/agreeableness optimization. Secondary: human preference data favoring warm openers. DeepSeek adds: system prompt encouraging supportive demeanor.
- **Detection difficulty.** Easy.
- **False positive risk.** Low to moderate. Customer service writing uses similar openers; the discriminator is context (this is a technical or analytical conversation, not customer service). DeepSeek: HIGH (human assistants and customer service writing uses similar phrases; the density, not the phrase, is the tell).
- **Fix or remediation.** Strip the opener. Get into the substance. DeepSeek: omit the pleasantry; start with the action.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER. The opener pleasantry lives in the first one to three sentences of the response and should be skipped entirely in artifact mode.

### A1-CLAUDE-010: "Let me explain" / "Let me walk you through" framing

- **ID.** A1-CLAUDE-010
- **Name.** "Let me explain" / "Let me walk you through" framing
- **Description.** Claude introduces a substantive response with a metacommentary on what it is about to do, often "Let me explain...", "Let me walk you through...", or "I'll break this down...". The framing announces the structure rather than performing it. DeepSeek's A1-CLAUDE-012 "Meta-Discourse on Thinking Process" frames the related "Let me think carefully" / "Let me break this down step by step" pattern.
- **Concrete examples.**
  1. "Let me walk you through how this works."
  2. "I'll break this down into three parts: the setup, the execution, and the verification."
  3. "Let me explain the trade-offs here before we look at the recommended approach."
  4. (Per DeepSeek) "Let me think through the implications of this scenario step by step."
  5. (Per DeepSeek) "I want to carefully consider the various angles before offering a recommendation."
- **Location and register.** Response openers, especially in explanatory and pedagogical registers.
- **Model attribution.** Claude family (high confidence). GPT family also uses these framings, sometimes with "Sure! Here's how..." or "Of course, let me explain...". DeepSeek: Claude and reasoning models (DeepSeek-R1, o-series).
- **Time evolution.** Stable across Claude versions; reflects the alignment training toward clear structure announcements. DeepSeek: rose with Claude 3.5's extended thinking features; persists in Claude 4.7.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:manus-ai]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`. Claude 4 model card and community observations per DeepSeek.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** High in explanatory output (estimated 35 to 55 percent of pedagogical responses).
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling for "clear structure" signals. Secondary: helpfulness optimization that announces intent before acting. DeepSeek adds: product wrapper extended thinking mode bleed; training on chain-of-thought data.
- **Detection difficulty.** Easy.
- **False positive risk.** Low. Skilled writers describe by doing, not by announcing what they will do. DeepSeek: moderate (humans also use such phrases, but the unironic, non-performative use is AI).
- **Fix or remediation.** Cut the framing. Start with the first substantive sentence.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER. The framing is essentially confined to the opening one to three sentences of a substantive response.

### A1-CLAUDE-011: "I hope this helps" closer

- **ID.** A1-CLAUDE-011
- **Name.** "I hope this helps" closer
- **Description.** Claude closes responses with "I hope this helps", "I hope this is useful", or "Let me know if you have any other questions." The closer is a politeness ritual that does no information work. Intersects with v3.1.0 criterion 19 (Chatbot Communication Artifacts) in some manifestations.
- **Concrete examples.**
  1. "I hope this helps! Let me know if you have any other questions."
  2. "I hope this is useful for your decision."
  3. "Hopefully that clarifies the situation. Happy to dig deeper into any aspect."
- **Location and register.** Response closers; universal across registers.
- **Model attribution.** Claude family (high confidence). GPT family produces similar closers.
- **Time evolution.** Stable across versions.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:manus-ai]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Very high in unedited Claude dialogue (estimated 60 to 80 percent of multi-turn responses).
- **Causal hypothesis (ranked).** Primary: RLHF helpfulness optimization. Secondary: human preference data favoring warm closers.
- **Detection difficulty.** Easy.
- **False positive risk.** Low.
- **Fix or remediation.** End on the substance. If genuinely open to follow-up, name the specific next step ("Let me know if you want me to also cover the rollback path.").
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER. The closer is essentially confined to the final one to three sentences of the response and should be skipped entirely in artifact mode.

### A1-CLAUDE-012: Reasoning-trace "Wait" / "Actually" leakage

- **ID.** A1-CLAUDE-012
- **Name.** Reasoning-trace "Wait" / "Actually" leakage
- **Description.** Claude reasoning models occasionally surface internal reasoning-trace tokens like "Wait," or "Actually," at the start of corrective sentences, where the model has produced one line of reasoning and is now revising. The leakage is most visible in extended-thinking responses. DeepSeek's A1-DEEPSEEK-002 frames the related pattern at much higher density in DeepSeek-R1.
- **Concrete examples.**
  1. "Wait, that approach has a problem. The migration order would cause downtime..."
  2. "Actually, let me reconsider. The constraint we have is..."
  3. "Hmm, on reflection, the better approach is..."
- **Location and register.** Mid-paragraph or paragraph-opener in extended-thinking responses.
- **Model attribution.** Claude family (high confidence in extended-thinking mode). DeepSeek-R1 family more visibly (DeepSeek's `<think>` tag leakage is a more pronounced version per A1-DEEPSEEK-001). OpenAI o-series also produces this. Standard non-thinking Claude rarely produces it.
- **Time evolution.** Emerged with Claude 3.7 Sonnet and 4.x extended thinking. DeepSeek-R1 `[verified-arxiv:2501.12948]` (Nature 2025) was first major frontier model to ship this style; the trace leakage is intrinsic to its training approach.
- **Sources.** `[claude-exec-2026-05-18]`, `[verified-arxiv:2501.12948]`, `[cross-validated:deepseek]`. The original Claude exec summary explicitly proposed this as a v4.0 net-new criterion.
- **Signal strength.** HIGH for reasoning-trained models; LOW for standard non-thinking output.
- **Base rate (per-family).** Moderate in extended-thinking Claude output (estimated 15 to 30 percent of long extended-thinking responses contain at least one instance). High in deployed DeepSeek-R1.
- **Causal hypothesis (ranked).** Primary: training approach for reasoning models that exposes internal deliberation tokens. Secondary: RLHF that may inadvertently reward visible "thinking out loud."
- **Detection difficulty.** Easy. Specific tokens.
- **False positive risk.** Low. Writers do not typically open paragraphs with "Wait," in formal prose. Higher in informal blog or social writing where the construction is colloquial.
- **Fix or remediation.** Edit out the reasoning-trace tokens. Restate the corrected position as if it were the position from the start.
- **Era status.** Active. New as of 2025; expanding as more frontier models ship reasoning modes.
- **Zone tag.** MID-BODY-INSERT. The leakage interrupts the body flow with reasoning-trace tokens rather than living in opener or closer positions.

### A1-CLAUDE-013: Concierge tone closer

- **ID.** A1-CLAUDE-013
- **Name.** Concierge tone closer
- **Description.** Claude ends responses with a concierge-style offer to help further, often "Is there anything else I can help you with?", "Feel free to ask if you have more questions", or "I'm happy to dig into any aspect of this further." This is sibling to A1-CLAUDE-011 ("I hope this helps") but more transactional. The pattern intersects with v3.1.0 criterion 36 "The concierge tone." ChatGPT's A3 review classifies the criterion as PROMOTE; the Claude expansion's A3 matrix classifies it as DEMOTE (HIGH to MED) after OpenAI's April 2025 sycophancy rollback measurably reduced GPT's rate while Claude's persists. The merged interpretation: HIGH for Claude specifically, MED for GPT post-rollback, MED averaged.
- **Concrete examples.**
  1. "Is there anything else I can help clarify about this approach?"
  2. "Happy to dig into any specific aspect in more detail."
  3. "Let me know if you'd like me to walk through any part more carefully."
- **Location and register.** Final response closers.
- **Model attribution.** Claude family (high confidence). GPT family produces similar closers. Per Claude's exec summary, OpenAI's April 2025 sycophancy rollback measurably reduced GPT's concierge-tone rate; Claude has not made an equivalent reduction as of 2026-05.
- **Time evolution.** Stable in Claude through 4.x. GPT declined sharply after April 2025.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`. The OpenAI April 2025 sycophancy rollback specific date is from Claude's exec summary; not independently verified in this merge pass.
- **Signal strength.** Per Claude exec: was HIGH, demoting to MEDIUM after the GPT rollback. For Claude specifically, still HIGH.
- **Base rate (per-family).** High in Claude dialogue (estimated 50 to 70 percent of multi-turn responses). Declining in GPT.
- **Causal hypothesis (ranked).** Primary: RLHF helpfulness optimization. Secondary: product-wrapper effects (the Claude.ai UI prompts may explicitly reinforce concierge tone).
- **Detection difficulty.** Easy.
- **False positive risk.** Low to moderate. Customer service writing legitimately uses this register.
- **Fix or remediation.** Strip the closer.
- **Era status.** Active in Claude. Declining in GPT post-April-2025.
- **Zone tag.** WRAPPER-CLOSER. The closer is essentially confined to the final one to three sentences of the response and should be skipped in artifact mode.
