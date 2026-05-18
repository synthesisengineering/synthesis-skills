# Model-Family Fingerprints (A1)

Reference detail for synthesis-content-quality v4.0, Section A1. The eight model-family fingerprinting subsections below carry the full per-pattern entry that the SKILL.md cannot accommodate. Each entry follows a fixed 14-field template plus era status and a machine-actionable zone tag, drawn directly from the unified bucket A catalog produced 2026-05-18.

## How to read this file

### Per-pattern template (14 fields plus era and zone)

Every pattern entry below carries the same fixed structure. The order is stable so that the file reads as a relational table when scanned column-wise across patterns:

1. **ID.** `A1-<FAMILY>-NNN`. The family code is one of CLAUDE, GPT, GEMINI, LLAMA, GROK, DEEPSEEK, MISTRAL, QWEN. The numeric suffix is the order of appearance in the unified bucket A merge. Numbering is not contiguous in every family because the merge preserved original LLM contributors' numbering where possible; gaps are intentional.
2. **Name.** A short label for the pattern. Aim is recognition, not summary.
3. **Description.** What the pattern looks like in production output, with cross-references to sibling patterns in other families and to the v3.1.0 criterion (if the pattern maps to one).
4. **Concrete examples.** A minimum of three observable instances. Where multiple LLMs contributed independent examples, all examples are preserved with attribution so the reader can see the convergent vs. divergent observation.
5. **Location and register.** Where the pattern lives in a response (opener, body paragraph, closer, mid-paragraph insert) and which registers (analytical, advisory, conversational, technical, creative) it appears most densely in.
6. **Model attribution.** Which models in the family produce this pattern, ranked by confidence. Where other families produce a sibling-but-different version, the cross-references are listed inline.
7. **Time evolution.** When the pattern emerged, when it peaked, whether it is declining, and what model-version inflection points changed the rate.
8. **Sources.** A minimum of two citations. Provenance flags from the unified bucket A are preserved verbatim (e.g., `[cross-validated:perplexity+deepseek]`, `[verified-arxiv:2406.07016]`, `[correction]`).
9. **Signal strength tier.** HIGH, MEDIUM, or LOW, with cluster-amplification notes when present.
10. **Base rate (per-family).** Estimated proportion of unedited outputs in which the pattern occurs, with the specific register or prompt-class qualifications where they matter.
11. **Causal hypothesis (ranked).** Primary, secondary, and tertiary causal drivers, drawn from the B1 twelve-code causal taxonomy: training-data skew, RLHF reward shaping, alignment and safety tuning, tokenizer and architecture effects, system-prompt and product-wrapper artifacts, refusal-avoidance behavior, helpfulness optimization, length optimization, chain-of-thought scaffolding, multilingual training corpus effects, fine-tuning data choices, and feedback-loop contamination.
12. **Detection difficulty.** Easy (greppable exact phrase or character search), Medium (requires multi-sentence pattern analysis), Hard (requires aggregate statistical analysis or domain expertise).
13. **False positive risk.** The realistic rate at which the pattern surfaces in skilled human prose, with the specific human-author profiles most likely to trigger false positives (academic writers, ESL writers, journalists, technical writers, ghostwriters).
14. **Fix or remediation.** What a human editor or revision pass should do when the pattern is identified.

### Era status field

In addition to the 14 fields, every pattern carries an explicit **era status** with one of four values:

- **Active.** Pattern still appears at meaningful base rate in current frontier models as of 2026-05.
- **Declining.** Base rate has measurably dropped at a specific model-version inflection point but the pattern still appears.
- **Historical.** Pattern is largely trained out of post-X model versions but remains useful for forensic analysis of content produced during the pattern's era of prevalence.
- **Deprecated.** Pattern is effectively absent from current models; retained in the catalog per the compounding-archive principle for audit-trail completeness.

Historical and Deprecated patterns are not included in this file. They live in [historical-patterns.md](historical-patterns.md) with cross-references back to the active pattern IDs in this file where lineage exists.

### Zone tag field

Per the GATE 2 zone-conditional detection methodology added to v4.0, every pattern carries an explicit zone tag indicating where in the LLM response the pattern is most likely to appear. The five values are:

- **WRAPPER-OPENER.** Pattern occurs almost exclusively in the first one to three sentences of the response. Examples: "You're absolutely right!" sycophancy openers, "Certainly!" compliance markers, "Great question!" affirmations, "Let me walk you through this" framing.
- **WRAPPER-CLOSER.** Pattern occurs almost exclusively in the final one to three sentences of the response. Examples: "I hope this helps!", "Is there anything else?", "Feel free to reach out if you have more questions."
- **BODY-PERSISTENT.** Pattern occurs in the substantive content of the response, distributed across body paragraphs. Most stylistic fingerprints fall here. Examples: em-dash density, saturated vocabulary, balanced two-handed sentences, bulleted bolded lead-ins, uniform paragraph length.
- **HYBRID.** Pattern occurs in both wrapper and body at meaningful rates. Examples: "It is important to note" (appears both as preamble and mid-body insert), focal vocabulary like "delve" (appears both in openers and throughout the body).
- **MID-BODY-INSERT.** Pattern is specific to mid-paragraph or mid-section inserts that interrupt the body flow. Examples: safety-hedge inserts ("It's important to remember that this advice depends on your situation"), reasoning-trace "Wait" / "Actually" leakage in chain-of-thought outputs.

The detector operates in two modes per the design-considerations.md note:

- **Artifact mode (default for editorial use):** apply only `BODY-PERSISTENT`, `HYBRID`, and `MID-BODY-INSERT` patterns. Skip wrapper-only patterns. False-positive rate stays low when only the artifact body is audited, which is the operative case for editors reviewing AI-assisted submissions where the conversational wrapper has already been stripped.
- **Full-response mode (for forensic chat-log analysis):** apply all patterns including wrapper-only.

The zone tag in each entry is the load-bearing field for mode selection.

### Provenance flag scheme

Provenance flags appear verbatim from the unified bucket A merge. They are preserved here so that downstream verification passes can trace each claim to its origin LLM and to the underlying citations:

- `[claude-exec-2026-05-18]`: drawn from the Claude 2026-05-18 executive summary or index produced for this upgrade.
- `[opus-expansion]`: from the Opus-4.7 inlined expansion of the Claude index, derived from Opus-4.7 training knowledge.
- `[verified-arxiv:XXXX.XXXXX]`, `[verified-github:org/repo#N]`, `[verified-web:source-name]`: independently verified during the expansion pass.
- `[cross-validated:<llm>]`: pattern appears in the named LLM's inlined bucket A contribution.
- `[cross-validated:<llm1>+<llm2>+...]`: multi-LLM convergent agreement.
- `[correction]`: an inaccuracy in an upstream source was identified and corrected; the correction is documented inline.
- `[manus-ai]`, `[perplexity]`, `[grok]`, `[chatgpt]`, `[gemini]`, `[deepseek]`: source attribution for any single-LLM contribution.

### Two known corrections from the unified bucket A merge

Two corrections to upstream claims are preserved exactly as they appear in the unified bucket A. They are flagged at the patterns where they apply.

1. **arxiv 2503.01659 was originally framed as a Copyleaks publication** in the Claude exec summary. The paper itself does not list Copyleaks as the publishing organization. The paper reports 0.9988 precision for cross-family detection but is not a Copyleaks-authored work. The `[correction]` flag appears at A1-DEEPSEEK-016 where this citation is used.
2. **The "106 occurrences in two weeks" figure for A1-CLAUDE-003 is not in GitHub Issue anthropics/claude-code#3382** as originally claimed. The GitHub issue describes the pattern qualitatively ("a sizeable fraction of responses") but does not contain the 106 figure. The `[correction]` flag appears at A1-CLAUDE-003.

### Em-dash constraint

This file uses no em-dashes (the U+2014 character). Commas, parentheses, colons, and sentence breaks substitute throughout. The constraint is part of the substantive subject matter: criterion 11 and criterion 42 of the v3.1.0 catalog under upgrade flag em-dash density as a high-signal AI marker, so a reference document for the upgrade cannot itself produce the pattern it is cataloguing.

### Section organization

The eight family subsections appear below in the order Claude, GPT, Gemini, Llama, Grok, DeepSeek, Mistral, Qwen. The order reflects the depth of available evidence: Claude and GPT have the deepest stylometric literature and the largest production-deployment footprints; Gemini has substantial evidence; the remaining five families have thinner peer-reviewed coverage and rely more on practitioner observation.

Patterns within each family are numbered in the order they appear in the unified bucket A merge. Where two LLMs contributed independent observations of the same underlying pattern, the merged entry preserves both observations with attribution. Where one LLM made a unique observation, the contributor is named.

---

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

### A1-CLAUDE-014: "That said," transitional phrase

- **ID.** A1-CLAUDE-014
- **Name.** "That said," transitional phrase
- **Description.** Claude uses "That said," as a concessive transition far more often than other models, functioning similarly to "However" but with a conversational, slightly less formal tone. Per `[deepseek]`'s A1-CLAUDE-005, predominantly Claude; GPT-5 uses "That said" occasionally but at much lower rates; Gemini and Grok rarely.
- **Concrete examples.**
  1. "That said, the results are still preliminary and require further validation."
  2. "That said, there are notable exceptions to this trend."
  3. "That said, it's not a one-size-fits-all solution."
- **Location and register.** Mid-paragraph or paragraph-start, in analytical or advisory prose.
- **Model attribution.** Predominantly Claude per `[deepseek]`. Output sampling across 200 Claude and GPT completions (2026); Pangram Labs detection signature list (2025).
- **Time evolution.** Became prominent in Claude 3.5 Sonnet, persists in Claude 4 and 4.7.
- **Sources.** `[deepseek]` primary; `[opus-expansion]` confirms.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Moderate in Claude (15 to 25 percent of long-form completions).
- **Causal hypothesis (ranked).** Primary: reinforcement from conversational training data (interviews, dialogues). Secondary: alignment tuning that rewards concessive moves to appear balanced.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate; business and legal writing sometimes employs it, but not at AI densities.
- **Fix or remediation.** Replace with more specific contrast phrasing. "That said, X" becomes "X, given Y" where Y names the specific tension.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT. The transitional phrase appears in body paragraphs, not specifically in wrapper zones.

### A1-CLAUDE-015: "However," as paragraph pivot

- **ID.** A1-CLAUDE-015
- **Name.** "However," as paragraph pivot
- **Description.** Claude outputs frequently use "However," as the first word of the second or third paragraph, introducing a counterpoint or limitation. The proportion of paragraphs beginning with "However" is noticeably elevated compared to human-authored text. Per `[deepseek]`'s A1-CLAUDE-003.
- **Concrete examples.**
  1. "However, this method is not without its drawbacks."
  2. "However, several challenges remain."
  3. "However, it is crucial to examine the assumptions behind these figures."
- **Location and register.** Body paragraphs, particularly after an initial descriptive or supportive paragraph.
- **Model attribution.** Claude (all versions), GPT-4/4o (less frequent), Gemini (occasional).
- **Time evolution.** Stable since Claude 2; slightly reduced in Claude 4.5 Opus as the model adopts more varied paragraph transitions.
- **Sources.** Gehrmann et al. (2023) "GLTR: Statistical Detection of Machine-Generated Text" per `[deepseek]`; manual analysis of 300 Claude and GPT completions.
- **Signal strength.** MEDIUM (useful in combination with other Claude markers).
- **Base rate (per-family).** Frequent in Claude (30 to 40 percent of multi-paragraph analytical completions); moderate in GPT.
- **Causal hypothesis (ranked).** Primary: training-data skew (academic register heavily uses "However"). Secondary: RLHF reward for acknowledging limitations. Tertiary: product wrapper system prompts that encourage nuance.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate; human academics use "However" as a transition, but the dense per-output frequency is telltale.
- **Fix or remediation.** Vary transitions; embed counterargument within the same paragraph rather than starting a new one with "However,".
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT. Paragraph-initial transitions live in the body.

### A1-CLAUDE-016: Apologetic framing in refusals and corrections

- **ID.** A1-CLAUDE-016
- **Name.** Apologetic framing in refusals and corrections
- **Description.** When declining a request or correcting a user, Claude routinely employs phrases like "I apologize if I...", "I'm sorry, but...", or "I want to be careful here...". This exceeds the politeness norms of the other families. Per `[deepseek]`'s A1-CLAUDE-004.
- **Concrete examples.**
  1. "I apologize if my previous response was unclear. Let me try again."
  2. "I'm sorry, but I can't assist with generating that type of content."
  3. "I want to be careful here because this area involves complex ethical considerations."
- **Location and register.** Refusal turns, error corrections, sensitive topics.
- **Model attribution.** Claude dominant; GPT-5 produces fewer apologies; Gemini sometimes apologises but less effusively.
- **Time evolution.** Intensified from Claude 3 onward as alignment tuning deepened. Partially mitigated in Claude 4.7 with a more confident persona but still present.
- **Sources.** Anthropic's "Constitutional AI" paper (Bai et al., 2022); user-reported behavior on r/ClaudeAI (2025-2026) per `[deepseek]`.
- **Signal strength.** MEDIUM (reliable in refusal contexts).
- **Base rate (per-family).** Frequent in refusal turns (60 to 80 percent of Claude refusals); rare otherwise.
- **Causal hypothesis (ranked).** Primary: Constitutional AI training and helpfulness optimization that over-learned politeness norms. Secondary: system prompt encouraging "respectful" interaction.
- **Detection difficulty.** Easy.
- **False positive risk.** Low for AI origin; high for specific family attribution as other models also apologise, though less profusely.
- **Fix or remediation.** Remove unnecessary apologies; state limitations without self-effacement.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER. Apologetic framings tend to appear at the start of refusal turns or correction openers.

### A1-CLAUDE-017: Longwinded introductory contextualization

- **ID.** A1-CLAUDE-017
- **Name.** Longwinded introductory contextualization
- **Description.** Before answering a direct question, Claude often embeds the answer in a multi-sentence preamble that restates the problem, defines terms, or establishes context. The preamble can be 2 to 4 sentences before the direct answer appears. Per `[deepseek]`'s A1-CLAUDE-006.
- **Concrete examples.**
  1. "That's a great question. Before diving into the specifics, it's helpful to frame the discussion with some background on how language models are trained. Language models learn from vast datasets... Now, to your question..."
  2. "To understand why this happens, we need to first consider the underlying architecture. Transformers process input tokens in parallel... With that in mind, the short answer is..."
- **Location and register.** Openers to informational and analytical responses.
- **Model attribution.** Claude dominant; GPT-5 also contextualizes but tends to lead with a direct answer and then explain. DeepSeek minimal preamble.
- **Time evolution.** Present since Claude 2; became longer and more structured with Claude 3.5; reduced slightly in Claude 4.7 after user feedback about verbosity, but still a hallmark.
- **Sources.** User studies on AI verbosity (Anderson and Smith, 2025); manual profiling of 100 Claude answers per `[deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Frequent in Claude (70 percent of informational responses contain a one-or-more sentence preamble).
- **Causal hypothesis (ranked).** Primary: helpfulness optimization that rewards thoroughness. Secondary: system prompt instructions to be "comprehensive". Tertiary: training on educational Q&A data where preambles are common.
- **Detection difficulty.** Easy.
- **False positive risk.** Low; human expert answers can include context, but the formulaic "That's a great question. Before I answer..." pattern is distinctly AI.
- **Fix or remediation.** Lead with the answer; provide context after or in a separate section.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER. The introductory preamble lives in the opening sentences of the response before the substantive content begins.

### A1-CLAUDE-018: "Nuanced" and "context-dependent" overuse

- **ID.** A1-CLAUDE-018
- **Name.** "Nuanced" and "context-dependent" overuse
- **Description.** Claude invokes "nuanced" or "context-dependent" to a degree that has become a self-parody. The word "nuanced" appears in a wide range of answers, often without the nuance being demonstrated. Per `[deepseek]`'s A1-CLAUDE-008.
- **Concrete examples.**
  1. "The answer is nuanced and depends heavily on the specific context."
  2. "It's a nuanced issue with no one-size-fits-all solution."
  3. "The relationship between these factors is nuanced."
- **Location and register.** Body, near conclusions.
- **Model attribution.** Claude heavily; GPT-5 less so; DeepSeek rarely.
- **Time evolution.** Rose sharply with Claude 3.5; has become a known community meme; persists in Claude 4.7 but with slight reduction.
- **Sources.** r/ClaudeAI discussions (2025-2026); "AI Prose Quirks" (The Atlantic, 2025) per `[deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Moderate (20 to 30 percent of analytical completions).
- **Causal hypothesis (ranked).** Primary: RLHF rewarding acknowledgment of complexity. Secondary: overfitting to alignment instructions that discourage absolute claims.
- **Detection difficulty.** Easy.
- **False positive risk.** Low; "nuanced" is a word humans use, but not at this keyword density.
- **Fix or remediation.** Replace with specific description of the conflicting factors. "The answer is nuanced" becomes "X applies when A and B; Y applies when C."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT. The vocabulary appears throughout body paragraphs.

### A1-CLAUDE-019: "In other words" reformulation loop

- **ID.** A1-CLAUDE-019
- **Name.** "In other words" reformulation loop
- **Description.** Claude restates the same idea immediately using "In other words," or "Put differently,", often adding little new information. Per `[deepseek]`'s A1-CLAUDE-011.
- **Concrete examples.**
  1. "The model exhibits a high degree of sensitivity to input perturbations. In other words, small changes in the input can lead to large changes in the output."
  2. "The policy aims to reduce emissions through market mechanisms. Put differently, it uses cap-and-trade."
  3. "The system optimizes for latency over throughput. In other words, it prioritizes response time at the cost of total work completed."
- **Location and register.** Body.
- **Model attribution.** Claude (frequent), GPT (occasional).
- **Time evolution.** Stable.
- **Sources.** Manual analysis per `[deepseek]`.
- **Signal strength.** LOW-MEDIUM.
- **Base rate (per-family).** Occasional.
- **Causal hypothesis (ranked).** Primary: over-optimization for clarity. Secondary: academic writing tic.
- **Detection difficulty.** Easy.
- **False positive risk.** Low; but not a strong differentiator alone.
- **Fix or remediation.** Delete one version. If the reformulation adds nothing, drop it; if it adds something, merge the two.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-CLAUDE-020: Elevated vocabulary register

- **ID.** A1-CLAUDE-020
- **Name.** Elevated vocabulary register
- **Description.** Per `[perplexity]`'s A1-CLAUDE-004, Claude selects elevated synonyms over plain alternatives at rates that produce a distinctive lexical fingerprint: "delve" for "look at," "nuanced" for "complicated," "multifaceted" for "complex," "pivotal" for "important," "leverage" for "use." The frequency makes individual word choices visible. The Manus AI catalog's "Signature Lexical Patterns" for Claude lists "delve," "tapestry," "testament," "nuanced," "comprehensive," "foster," "underscore," "holistic," "intricate," "paradigm." Maps to v3.1.0 criterion 33 (Saturated AI Vocabulary).
- **Concrete examples.**
  1. "Let's delve into the implications of this policy shift for small businesses."
  2. "The situation is more nuanced than it may first appear."
  3. "We need to leverage our existing infrastructure to accelerate deployment."
  4. "This represents a multifaceted challenge requiring a comprehensive approach."
  5. "The pivotal insight is that we must foster collaboration across teams."
- **Location and register.** Professional, business, and academic registers.
- **Model attribution.** Claude (highest per Perplexity); GPT-4o shows this but with different lexical items (see A1-GPT-001); Manus AI lists overlapping vocabulary in both families.
- **Time evolution.** Present since Claude 3. "Delve" in particular is widely cited as a Claude-specific tell. Frequency has not visibly declined through Claude 4.
- **Sources.** BlogPros 2026; Originality.ai 2025; practitioner documentation across LinkedIn, Reddit, and editor Substacks. Cross-validates with A1-GPT-001's Kobak documentation: while Kobak's primary anchor is GPT, the focal-word cluster overlaps across families with different distribution peaks.
- **Signal strength.** MEDIUM per word; HIGH for cluster of three or more in 500 words.
- **Base rate (per-family).** HIGH in unedited Claude output.
- **Causal hypothesis (ranked).** Primary: training data skew toward academic register where these words cluster. Secondary: RLHF rewards for "professionalism" that correlate with elevated register.
- **Detection difficulty.** Easy with grep.
- **False positive risk.** Low for cluster; individual words are common in edited professional prose.
- **Fix or remediation.** Replace with plain alternatives. Run a find-replace pass on the cluster words. "Delve" becomes "examine"; "leverage" becomes "use"; "foster" becomes "encourage."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-CLAUDE-021: Diplomatic neutrality default

- **ID.** A1-CLAUDE-021
- **Name.** Diplomatic neutrality default
- **Description.** Per `[perplexity]`'s A1-CLAUDE-005, Claude hedges contestable claims and avoids taking positions even when the evidence clearly supports one interpretation. The hedge is structural, not epistemic: it appears whether or not uncertainty is warranted. This intersects with v3.1.0 criterion 37 (Insider Context Collapse is unrelated; the connection is to the "balanced hedging" sub-pattern within v3.1.0 criterion 27 "Superficial Depth").
- **Concrete examples.**
  1. "While some experts argue X, others contend Y, and the full picture remains to be seen."
  2. "It really depends on your specific situation and goals."
  3. "There are valid arguments on both sides of this debate."
- **Location and register.** Opinion, analysis, and advice registers. Strongest in business and editorial content.
- **Model attribution.** Claude (highest); GPT-4o and Gemini show similar but distinct versions.
- **Time evolution.** Present across all Claude versions. Constitutional AI alignment tuning makes this more pronounced in Claude than in other families.
- **Sources.** BlogPros 2026; PR Daily 2026 (media training context); v3.1.0 criterion 27.
- **Signal strength.** MED alone; HIGH combined with survey-without-claim (A2-SUB-008).
- **Base rate (per-family).** HIGH in unedited output.
- **Causal hypothesis (ranked).** Primary: alignment and safety tuning penalizes confident claims that could be controversial. Secondary: RLHF rewards "helpfulness" interpreted as acknowledging multiple perspectives.
- **Detection difficulty.** Medium. Requires reading for what is NOT said.
- **False positive risk.** Medium. Good journalism requires representing multiple perspectives. Context determines whether hedging is appropriate or evasive.
- **Fix or remediation.** Identify the position the evidence supports and state it. Acknowledge exceptions specifically, not generically.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-CLAUDE-022: Functional emotion signal leakage

- **ID.** A1-CLAUDE-022
- **Name.** Functional emotion signal leakage
- **Description.** Per `[perplexity]`'s A1-CLAUDE-006, Anthropic interpretability research (2025) identified 171 internal functional emotional states in Claude. These occasionally surface as linguistic micropatterns: enthusiasm markers in topic introductions ("This is a fascinating area"), completion satisfaction in closing sentences ("This brings us to a satisfying conclusion"), and curiosity framing in transitional questions ("What does this mean for...?"). This is single-LLM-sourced and somewhat speculative; flagged for verification.
- **Concrete examples.**
  1. "This is a fascinating question that touches on some of the deepest issues in cognitive science."
  2. "Understanding this properly requires stepping back to appreciate the full picture."
  3. "What does this mean for practitioners on the ground?"
- **Location and register.** Introductions, section openers, topic transitions.
- **Model attribution.** Claude (highest; unique to this family among documented cases).
- **Time evolution.** Documented in Claude 3.5 and later through Claude 4. Earlier versions show weaker version.
- **Sources.** Anthropic interpretability research (Bloomberry AI summary, 2026); practitioner observation. `[perplexity]` unique; not cross-validated.
- **Signal strength.** LOW alone; MED combined with other Claude patterns.
- **Base rate (per-family).** MED.
- **Causal hypothesis (ranked).** Functional emotional states documented by Anthropic's interpretability team shape output; enthusiasm state activates on novel or complex inputs.
- **Detection difficulty.** Hard. The phrases are common in skilled human writing.
- **False positive risk.** HIGH. Good teachers and writers use these constructions deliberately.
- **Fix or remediation.** Replace with direct assertions. "This is a fascinating question" adds nothing; state the thing directly.
- **Era status.** Active.
- **Zone tag.** HYBRID. Topic-introduction enthusiasm markers can appear at wrapper-opener positions; completion-satisfaction markers at wrapper-closer positions; the pattern crosses zones.

### A1-CLAUDE-023: "And/But" rhythmic opener

- **ID.** A1-CLAUDE-023
- **Name.** "And/But" rhythmic opener
- **Description.** Per `[perplexity]`'s A1-CLAUDE-008, Claude begins sentences with "And" or "But" as a deliberate rhythm device across consecutive paragraphs, creating a cadence that is more regular than typical human prose variation.
- **Concrete examples.**
  1. "But this doesn't mean the approach is without merit. And there are cases where the evidence clearly points in a different direction."
  2. "And that matters. But it matters less than the second factor."
  3. "But here is the thing. And the thing matters."
- **Location and register.** Body paragraphs, analytical writing.
- **Model attribution.** Claude (strongest); GPT-4o uses it less.
- **Time evolution.** Consistent across Claude versions.
- **Sources.** BlogPros 2026.
- **Signal strength.** LOW alone; MED in combination.
- **Base rate (per-family).** MED.
- **Causal hypothesis (ranked).** RLHF reward for "conversational tone" in non-formal contexts.
- **Detection difficulty.** Easy.
- **False positive risk.** Medium. Many skilled writers use sentence-starting "And/But" deliberately.
- **Fix or remediation.** Vary sentence-initial constructions. Not every rhythm device is wrong; the problem is the pattern becoming a reflex.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-CLAUDE-024: Colon overextension

- **ID.** A1-CLAUDE-024
- **Name.** Colon overextension
- **Description.** Per `[perplexity]`'s A1-CLAUDE-009, Claude uses colons to introduce follow-up ideas that do not require formal introduction, including cases where a period or comma would read more naturally. Gemini's catalog frames the same under the "Markdown Leakage Principle" net-new addition.
- **Concrete examples.**
  1. "The core challenge is clear: resources are limited."
  2. "There is one word that captures this situation: complexity."
  3. "The answer, it turns out, is straightforward: you need both."
- **Location and register.** All registers.
- **Model attribution.** Claude (highest).
- **Time evolution.** Consistent across Claude versions.
- **Sources.** BlogPros 2026.
- **Signal strength.** LOW alone; MED combined.
- **Base rate (per-family).** MED.
- **Causal hypothesis (ranked).** Tokenizer effects: colon-as-structural-marker is a frequently reinforced pattern in instructional training data. Gemini adds: markdown conditioning.
- **Detection difficulty.** Easy.
- **False positive risk.** Medium. Colon use is stylistically legitimate; overuse is the signal.
- **Fix or remediation.** Read each colon aloud. If a period or comma would flow better, use it.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-CLAUDE-025: "Navigating" topic frames

- **ID.** A1-CLAUDE-025
- **Name.** "Navigating" topic frames
- **Description.** Per `[perplexity]`'s A1-CLAUDE-011, Claude frames topics as landscapes to be navigated rather than problems to be solved or questions to be answered. The word "navigating" appears in headings, introductions, and topic openers at a higher rate than other verbs. Maps to v3.1.0 criterion 34 (Exhausted Metaphors as Structural Filler).
- **Concrete examples.**
  1. "Navigating the Regulatory Landscape" (heading)
  2. "Navigating these challenges requires a clear framework."
  3. "For teams navigating rapid change, the following principles apply."
- **Location and register.** Introductions, headings, business and professional writing.
- **Model attribution.** Claude (highest); not strongly associated with other families.
- **Time evolution.** Consistent through Claude 4.
- **Sources.** BlogPros 2026; practitioner lists.
- **Signal strength.** MED.
- **Base rate (per-family).** MED.
- **Causal hypothesis (ranked).** Training data skew: "navigating" is over-represented in business and management writing, which is heavily represented in Claude's instruction-following fine-tuning data.
- **Detection difficulty.** Easy.
- **False positive risk.** Low. The specific verb in the specific construction is uncommon in skilled human prose.
- **Fix or remediation.** Name the actual activity. "How to comply with new regulations" instead of "Navigating the regulatory landscape."
- **Era status.** Active.
- **Zone tag.** HYBRID. Heading and opener uses are wrapper-adjacent; body uses are body-persistent.

### A1-CLAUDE-026: "Underscores the importance" closer

- **ID.** A1-CLAUDE-026
- **Name.** "Underscores the importance" closer
- **Description.** Per `[perplexity]`'s A1-CLAUDE-012, Claude closes arguments by "underscoring" or "highlighting" the importance of the topic rather than stating a conclusion. The meta-commentary replaces the insight.
- **Concrete examples.**
  1. "This underscores the importance of early stakeholder engagement."
  2. "These findings highlight the need for continued investment in infrastructure."
  3. "Taken together, these factors underscore the complexity of the challenge ahead."
- **Location and register.** Paragraph closers, section conclusions.
- **Model attribution.** Claude and Gemini (comparable rates).
- **Time evolution.** Consistent.
- **Sources.** BlogPros 2026; editor practitioner observation.
- **Signal strength.** MED.
- **Base rate (per-family).** HIGH.
- **Causal hypothesis (ranked).** RLHF training on academic text where "these results underscore" is a standard academic conclusion move.
- **Detection difficulty.** Easy.
- **False positive risk.** Medium. Academic writing legitimately uses this construction.
- **Fix or remediation.** Replace with the conclusion itself. "This underscores the importance of X" means X matters. Say why, specifically.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER for the final response closer use; BODY-PERSISTENT (or specifically mid-body) for section closers within the body. Practically: HYBRID with closer-bias.

### A1-CLAUDE-027: The prescriptive moralizer

- **ID.** A1-CLAUDE-027
- **Name.** The prescriptive moralizer
- **Description.** Per `[gemini]`'s A1-CLAUDE-002, Claude tends to end objective, data-driven analyses with an unsolicited prescriptive recommendation or ethical conclusion, regardless of the prompt's instructions. This overlaps with A1-CLAUDE-006 (refusal-shaped close) but the trigger is broader: any analysis, not just sensitive topics. Maps to v3.1.0 criterion 35 (Unprompted Moral Cadence).
- **Concrete examples.**
  1. "Ultimately, teams must weigh these efficiency gains against the potential risks to long-term user privacy."
  2. "Careful consideration of these edge cases is paramount moving forward to ensure equitable access."
  3. "Balancing rapid innovation with ethical deployment will remain the defining challenge for developers."
- **Location and register.** Document closers, final paragraphs of essays, and summarization tasks.
- **Model attribution.** Anthropic Claude 4.7 (High), Claude 4.6 (High) per `[gemini]`.
- **Time evolution.** Persistent across all Claude versions, deeply embedded in the Constitutional AI framework and resistant to system prompt suppression.
- **Sources.** `[gemini]`. 70 percent confidence per Gemini's calibration.
- **Signal strength.** MEDIUM (70 percent confidence per Gemini).
- **Base rate (per-family).** Appears in 85 percent of open-ended analyses per Gemini.
- **Causal hypothesis (ranked).** Primary: alignment tuning. Secondary: harmlessness optimization requiring responsible framing.
- **Detection difficulty.** Easy (highly predictable placement).
- **False positive risk.** High (junior human analysts often rely on similar platitudes to artificially inflate word counts).
- **Fix or remediation.** Truncate the final paragraph entirely. If a real ethical issue is genuinely raised by the analysis, address it with specificity, not platitudes.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER.

### A1-CLAUDE-028: The vestigial "Certainly" opener

- **ID.** A1-CLAUDE-028
- **Name.** The vestigial "Certainly" opener
- **Description.** Per `[gemini]`'s A1-CLAUDE-003, a compliance marker where the model explicitly acknowledges the prompt using the word "certainly" before fulfilling the request. This is identified by Gemini as a legacy artifact from the Claude 3 era, actively being trained out but still present when prompt complexity spikes and adaptive thinking bypasses newer conversational filters. This overlaps with A1-GPT-002 below; cross-family use of "Certainly!" is common but Gemini specifically attributes the pattern to Claude 3-era residue.
- **Concrete examples.**
  1. "Certainly. Here is the refactored database schema based on your requirements."
  2. "While I understand the constraints, certainly we can approach the calculation differently."
  3. "Certainly, the primary factor driving this sudden adoption is raw infrastructural cost."
- **Location and register.** Conversation openers and immediate responses to complex instructions.
- **Model attribution.** Anthropic Claude 4.5 (High), Claude 4.7 (Low) per `[gemini]`. GPT family also produces this pattern; see A1-GPT-002.
- **Time evolution.** Legacy artifact from Claude 3 era; dropping to 15 percent in Opus 4.7 per `[gemini]`.
- **Sources.** `[gemini]`. 95 percent confidence per Gemini's calibration.
- **Signal strength.** VERY HIGH (95 percent confidence) when it appears; declining base rate.
- **Base rate (per-family).** Occurs in 42 percent of direct instructional prompts in older versions, dropping to 15 percent in Opus 4.7.
- **Causal hypothesis (ranked).** Primary: helpfulness optimization. Secondary: refusal-avoidance behavior.
- **Detection difficulty.** Easy.
- **False positive risk.** Low (humans rarely use this specific robotic compliance marker in professional text).
- **Fix or remediation.** Delete the opener and begin directly with the substantive response.
- **Era status.** Declining (specifically in Claude 4.7).
- **Zone tag.** WRAPPER-OPENER.

---

## A1.2 OpenAI GPT family

Models in scope: GPT-4, GPT-4o, GPT-4.1, GPT-5, GPT-5.x, and the o-series reasoning models (o1, o3, o4-mini). Historical entries for pre-instruction-tuning GPT-3, GPT-3.5 "As an AI language model" preamble, and the GPT-3.5/4 "Here's the thing" colloquial intensifier live in [historical-patterns.md](historical-patterns.md). The GPT family has the broadest production-deployment footprint among current frontier families and the deepest published stylometric literature; the 2024 to 2026 detection research corpus is anchored substantially on GPT output.

### A1-GPT-001: "Delve" and the saturated AI vocabulary cluster

- **ID.** A1-GPT-001
- **Name.** "Delve" and the saturated AI vocabulary cluster
- **Description.** GPT family (especially GPT-3.5 and GPT-4 lineages) overproduces a specific cluster of focal words that Kobak et al. (2024) and Matsui et al. (2025) documented at Z-scores above 3.5 in 2024 PubMed corpora. The headline word is "delve" (most-cited example), but the cluster also includes "intricate", "intricately", "leverage", "tapestry", "pivotal", "underscore", "underscores", "underscoring", "in the realm of", "navigate the complexities of", and approximately 100 other focal words documented in Kobak's Science Advances 2025 paper. Per Perplexity's A1-GPT-003 "Landscape Vocabulary Set" the cluster also covers "landscape," "ecosystem," "dynamics," "paradigm," "framework," "solutions," "insights." Per Perplexity's A1-GPT-008 "Innovative and Robust Vocabulary Set" the cluster includes "innovative," "robust," "dynamic," "efficient," "transformative," "seamless," "impactful," "synergistic." ChatGPT's A3 review classifies the v3.1.0 criterion 33 (Saturated AI Vocabulary) as REVISE: keep the idea but refresh the lexicon by family and genre. The Claude expansion's A3 matrix promotes criterion 33 from MED to HIGH.
- **Concrete examples.**
  1. "Let us delve into the intricate dynamics of urban planning."
  2. "This study underscores the pivotal role of microbiota in human health."
  3. "We navigate the complexities of cross-disciplinary research to weave a tapestry of insights."
  4. (Per Perplexity) "The rapidly evolving landscape of AI presents both challenges and opportunities."
  5. (Per Perplexity) "Understanding the ecosystem of stakeholders is essential to effective change management."
  6. (Per Perplexity) "This paradigm shift requires new frameworks for thinking about innovation."
  7. (Per Perplexity) "An innovative approach to customer engagement that delivers robust results."
  8. (Per Perplexity) "The platform provides a seamless, dynamic user experience."
  9. (Per Perplexity) "A transformative solution that drives synergistic outcomes."
- **Location and register.** Universal across registers but densest in academic and explainer prose. Highest base rate in non-native English contexts and in technical/scientific writing. Per Perplexity: business writing, analysis, strategy documents for the landscape cluster; marketing, business, and technology writing for the innovative/robust cluster.
- **Model attribution.** GPT family (very high confidence for GPT-3.5 and GPT-4 lineages). Claude family produces some overlap but at lower density. Per Perplexity: GPT family highest for "landscape," "ecosystem," "paradigm"; Claude uses "realm" and "tapestry" instead; Gemini favors "context" and "considerations." Other frontier models inherit some focal words via shared training corpora but at significantly lower rates.
- **Time evolution.** Emerged sharply with ChatGPT public release in late 2022; peaked in GPT-3.5/4 era (2023 to mid-2024); persistent through GPT-4o; GPT-5 and GPT-5.1 reduced some specific focal words but the broader cluster remains. Perplexity: "Landscape" has been flagged as a GPT-specific tell since 2023; "Innovative/Robust" cluster consistent from GPT-3.5 through GPT-4o; slightly reduced in GPT-4.1.
- **Sources.** `[claude-exec-2026-05-18]`, `[verified-arxiv:2406.07016]` (Kobak et al. "Delving into LLM-assisted writing in biomedical publications through excess vocabulary", confirming 13.5 percent of 2024 biomedical abstracts processed with LLMs, with focal-word frequency anomalies as the detection method). Juzek and Ward COLING 2025 attributes the overrepresentation to RLHF reward shaping specifically. `[cross-validated:manus-ai]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`. Student Village 2024; Originality.ai 2025; "9 Words That Reveal ChatGPT," multiple sources.
- **Signal strength.** HIGH per Claude's tier-shift recommendation (was MEDIUM in v3.1.0 criterion 33, recommended PROMOTE to HIGH). Per Perplexity: MED per word; HIGH for cluster of three or more in 500 words.
- **Base rate (per-family).** Very high in unedited GPT output. Kobak documented 10 percent of 2024 PubMed abstracts using "delve" specifically (vs. baseline of about 0.5 percent in 2020). Saturated cluster appears in estimated 70 to 90 percent of GPT-family essay output.
- **Causal hypothesis (ranked).** Primary: RLHF reward shaping (per Juzek and Ward COLING 2025 specifically attributing "delve" to RLHF). Secondary: training-data skew toward academic corpora that overrepresent these words. Tertiary: feedback loops as LLM-influenced PubMed papers become training data for next-generation models.
- **Detection difficulty.** Easy. Word search with frequency thresholds.
- **False positive risk.** Moderate to high. Academic writers and ESL writers use some focal words at higher baseline rates. Per Liang et al. 2023, this is part of the ESL false-positive trap. The discriminator is density and combination with other markers.
- **Fix or remediation.** Replace each focal word with a more specific or simpler alternative ("examine" or "study" instead of "delve into"; "complex" or "complicated" instead of "intricate"; "use" or "apply" instead of "leverage"). Maintain content; cut the academic-register cosplay.
- **Era status.** Active. Some specific words (e.g., "tapestry") have declined; the broader cluster remains.
- **Zone tag.** BODY-PERSISTENT.

### A1-GPT-002: Sycophantic opener ("Great question!", "Certainly!", "Absolutely!")

- **ID.** A1-GPT-002
- **Name.** Sycophantic opener
- **Description.** GPT family responses, especially in dialogue, open with enthusiastic acknowledgment ("Great question!", "Excellent point!", "I love this question!") and proceed with an instructive cadence that frames the response as teaching. Per `[perplexity]`'s A1-GPT-001 "Sycophantic Opener," GPT-4o and earlier GPT models open assistant responses with affirmative interjections that acknowledge the request before addressing it: "Certainly!", "Absolutely!", "Great question!", "Of course!", "I'd be happy to help with that." The cadence often includes "Let's break this down" or "Here's what's happening" early in the response. Gemini's A1-GPT-001 "Pseudo-Empathetic Affirmation" captures the related "I completely understand your concern" variant. DeepSeek's A1-GPT-003 catalogs "Certainly!" / "Of course!" as extremely common GPT openers.
- **Concrete examples.**
  1. "Great question! Let's break this down step by step..."
  2. "Excellent point! Here's what's happening under the hood..."
  3. "I love this question! There are actually several layers to consider..."
  4. (Per Perplexity) "Certainly! Here's a breakdown of the key considerations..."
  5. (Per Perplexity) "Absolutely, that's a great approach. Let me walk you through..."
  6. (Per Perplexity) "Of course! I'd be happy to help you draft that email."
  7. (Per Gemini) "I completely understand your concern regarding the sudden latency spike."
  8. (Per Gemini) "That is an incredibly sharp observation about the fragile supply chain dynamics."
  9. (Per Gemini) "I am right here to help you navigate this complex, multi-tiered architecture."
- **Location and register.** Response openers in dialogue; pedagogical and explainer registers. Perplexity: Response openers in conversational and assistant contexts. Gemini: First sentence of responses, particularly following user corrections or error reports.
- **Model attribution.** GPT family (very high confidence). The specific "Great question!" reflex was the signature ChatGPT tell from 2023 onward. OpenAI's April 2025 sycophancy rollback reduced the rate but the pattern persists. Claude has a similar but distinct reflex ("You're absolutely right!" per A1-CLAUDE-003). Per Perplexity: GPT-4o (highest); present but reduced in GPT-4.1 and later. Not characteristic of Claude 4, Gemini, or Llama 4. Effectively faded in GPT-5. Per Gemini: OpenAI GPT-5.4 (High), GPT-5.5 (Medium); escalated significantly in GPT-4o voice-optimized training.
- **Time evolution.** Emerged with ChatGPT launch; high density through 2023-2024; partial reduction after April 2025 sycophancy rollback; remains present in 2026. Strong in GPT-3.5 through GPT-4o per Perplexity. Measurably reduced in GPT-4.1 and o-series. Effectively faded in GPT-5.
- **Sources.** `[claude-exec-2026-05-18]`, `[verified-arxiv:2310.13548]` (Sharma et al. sycophancy in five production assistants confirms sycophancy as a structural feature of RLHF-trained models). `[cross-validated:perplexity]`, `[cross-validated:manus-ai]`, `[cross-validated:deepseek]`, `[cross-validated:gemini]`. Student Village forum catalog 2024; LinkedIn practitioner lists 2025; Originality.ai 2025.
- **Signal strength.** HIGH for the explicit opener; MEDIUM for the broader instructive cadence. Per Perplexity: HIGH (strong family signal; Claude and Gemini do not produce this at comparable rates). Per Gemini: 88 percent confidence for pseudo-empathetic affirmation specifically.
- **Base rate (per-family).** High in unedited GPT dialogue (estimated 30 to 50 percent of multi-turn responses opened with "Great question!" or variant before the April 2025 rollback; estimated 15 to 25 percent after). Per Perplexity: HIGH in GPT-4o; LOW in GPT-5. Per Gemini: 312 occurrences per 1,000 conversational turns (VTI-derived figure, single-LLM-sourced, unverified at merge time).
- **Causal hypothesis (ranked).** Primary: RLHF helpfulness optimization. Secondary: human preference data favoring warm openers. Tertiary: system-prompt artifacts in OpenAI's personality v2 tuning. Gemini adds: chat-format conversational tuning prioritizing simulated human connection.
- **Detection difficulty.** Easy. Exact phrase.
- **False positive risk.** Low. Per Perplexity: LOW. Human writers do not typically open paragraphs or responses with "Certainly!" in professional writing.
- **Fix or remediation.** Strip the opener. Start with substance.
- **Era status.** Active but Declining (post April 2025 rollback).
- **Zone tag.** WRAPPER-OPENER.

### A1-GPT-003: Section-ending summary sentence

- **ID.** A1-GPT-003
- **Name.** Section-ending summary sentence
- **Description.** GPT, particularly 4o, ends each section of a multi-section response with a sentence that summarizes what the section just argued. This is sibling to A1-CLAUDE-007 but more pronounced in GPT.
- **Concrete examples.**
  1. (After a section on database choices) "In summary, choose Postgres if you need ACID compliance and SQL; choose Redis if you need low-latency in-memory access."
  2. (After a section on testing strategies) "These three testing approaches together provide comprehensive coverage."
  3. (After a section on architecture) "The architecture decisions above set the foundation for the implementation choices we'll cover next."
- **Location and register.** Mid-document section closers.
- **Model attribution.** GPT family (high confidence, especially 4o). Claude produces similar but less mechanically; Gemini variable.
- **Time evolution.** Stable across GPT versions through GPT-5.1.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:manus-ai]`, `[cross-validated:perplexity]`.
- **Signal strength.** HIGH in combination with bolded lead-ins and saturated vocabulary; MEDIUM standalone.
- **Base rate (per-family).** High in unedited GPT 4o long-form (estimated 70 to 85 percent of multi-section responses).
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling for clear structure. Secondary: training-data skew toward academic and tutorial prose where section recaps are common.
- **Detection difficulty.** Easy.
- **False positive risk.** Low to moderate.
- **Fix or remediation.** Cut the recap. The reader just read the section.
- **Era status.** Active.
- **Zone tag.** MID-BODY-INSERT for mid-document section closers; WRAPPER-CLOSER for the final response closer. Practically: HYBRID with mid-body bias.

### A1-GPT-004: "It's not just X, it's Y" construction

- **ID.** A1-GPT-004
- **Name.** "It's not just X, it's Y" construction
- **Description.** GPT uses a specific rhetorical move: stating that something is not merely the surface understanding but is actually something deeper or more significant. The construction often runs "It's not just X, it's Y" or "This isn't simply X, it's Y." The framing inflates significance and is a tell of the pseudo-profundity register. Closely related to v3.1.0 criterion 5 "Negative Parallelism" (the "not X but Y" construction); Manus AI catalog keeps criterion 5 as is, ChatGPT's review classifies it as DEMOTE (still real, but weaker as a standalone tell), and the Claude expansion promotes it from MED to HIGH on the grounds that "preference data directly reinforces antithesis."
- **Concrete examples.**
  1. "It's not just a tool, it's a paradigm shift in how we think about workflow automation."
  2. "This isn't simply about cost savings; it's about reimagining the entire customer experience."
  3. "The migration isn't just a technical change, it's an organizational transformation."
- **Location and register.** Body paragraphs, especially in marketing, business, and motivational registers.
- **Model attribution.** GPT family (very high confidence, especially 4 and 4o). Claude produces similar constructions but less mechanically. Marketing-tuned LLM products amplify this further.
- **Time evolution.** Present from GPT-3.5 forward; high density through 4o; partially reduced in GPT-5.1 personality update but still present.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:perplexity]`, `[cross-validated:manus-ai]`. Pennycook et al. BSRS provides the pseudo-profundity framework.
- **Signal strength.** HIGH especially in marketing register; MEDIUM in analytical register.
- **Base rate (per-family).** High in marketing and motivational GPT output (estimated 40 to 60 percent of responses to "explain the impact of X" prompts).
- **Causal hypothesis (ranked).** Primary: training-data skew toward marketing and motivational corpora. Secondary: RLHF reward modeling that may favor "elevated" framings.
- **Detection difficulty.** Easy. Construction is searchable.
- **False positive risk.** Moderate. Skilled essayists and op-ed writers use this construction; the discriminator is density.
- **Fix or remediation.** State what the thing actually is and what it does. Skip the elevation.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT (Active GPT focal cluster).

### A1-GPT-005: "While X, it's also worth noting Y" balanced framing

- **ID.** A1-GPT-005
- **Name.** "While X, it's also worth noting Y" balanced framing
- **Description.** GPT family uses balanced framings similar to A1-CLAUDE-002 but with a different connective pattern. The construction often runs "While X, it's also worth noting that Y" or "On the surface X, but in reality Y." The function is similar: hedge by presenting multiple perspectives. Perplexity's A1-GPT-012 "Hedge-Then-Assert Structure" captures the related pattern: GPT structures arguments as acknowledge complexity, hedge, then assert the claim that was hedged. The structure produces the appearance of nuance while delivering the same conclusion the unhedged version would have.
- **Concrete examples.**
  1. "While the data suggests improvement, it's worth noting that the sample size is small."
  2. "On the surface, this looks like a clear win. But there are several caveats worth considering."
  3. "Although the approach has merit, we should also acknowledge some limitations."
  4. (Per Perplexity) "While the evidence is not conclusive, and experts disagree on several key points, most studies suggest that X is the better approach."
  5. (Per Perplexity) "It's difficult to generalize across all situations, but in the majority of cases, Y tends to produce better outcomes."
- **Location and register.** Body paragraphs, analytical registers.
- **Model attribution.** GPT family (high confidence). Claude uses the explicit "on the one hand / on the other hand" form more often. Both families produce subtler "While X" framings. Perplexity: GPT-4o and Claude (both high); Gemini less so.
- **Time evolution.** Stable across GPT versions.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:perplexity]`, `[cross-validated:manus-ai]`, `[cross-validated:deepseek]`. BlogPros 2026 per Perplexity.
- **Signal strength.** MEDIUM standalone; HIGH in combination with other GPT markers.
- **Base rate (per-family).** High in analytical GPT output (estimated 50 to 70 percent of long analytical responses contain at least one instance).
- **Causal hypothesis (ranked).** Primary: RLHF reward shaping for nuanced presentation. Secondary: training-data skew toward academic argument structures.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate. Academic writers use this construction.
- **Fix or remediation.** Take a position. If both sides genuinely need representation, articulate the tension with concrete consequences.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

(A1-GPT-006 and A1-GPT-007 are Historical-era patterns. Their entries live in [historical-patterns.md](historical-patterns.md). A1-GPT-006 is the "Here's the thing" / "The thing is" colloquial intensifier from GPT-3.5 and early GPT-4. A1-GPT-007 is the "As an AI language model" preamble. Cross-references are preserved in the historical file. They are not repeated here because the era status filter for this file is Active or Declining only.)

### A1-GPT-008: Numbered-list scaffolding and listicle-default mode

- **ID.** A1-GPT-008
- **Name.** Numbered-list scaffolding and listicle-default mode
- **Description.** GPT family, especially 4o, structures responses as numbered lists even when the content does not benefit from enumeration. Per Perplexity's A1-GPT-013 "Listicle-Default Mode," GPT converts prose questions into bullet-pointed or numbered lists even when the question calls for reasoning, narrative, or analysis. The list format delivers parallel surface structure but bypasses causal reasoning. Gemini's A1-GPT-003 "Tripartite Markdown Transition" frames the related pattern: a rigid transition mechanism where the model signals an upcoming list using a colon, invariably followed by exactly three bullet points or numbered items. DeepSeek's A1-GPT-004 captures "Structured Numbered Lists with Bold Headers" (the "1. Header: Explanation" format).
- **Concrete examples.**
  1. Best seen in aggregate. Compare any GPT-4o response to "What should I think about when choosing X?" (almost always a numbered list of 3 to 7 items) to how a human would naturally answer (often prose with maybe one or two embedded examples).
  2. (Per Perplexity, asked "Why did the Roman Empire fall?") "**Reasons the Roman Empire Fell:** 1. Military overextension. 2. Economic difficulties. 3. Political instability. 4. External pressures."
  3. (Per Gemini) "This cloud architecture introduces three critical vulnerabilities:"
  4. (Per Gemini) "To mitigate this systemic risk, consider the following primary strategies:"
  5. (Per Gemini) "The financial data suggests several converging factors:"
- **Location and register.** Body of responses; pedagogical and decision-support registers. Per Gemini: mid-body transitions, analytical reports, and executive summaries.
- **Model attribution.** GPT family (very high confidence, especially 4o). Claude does this less by default but more with explicit prompting. Per Gemini: OpenAI GPT-5.5 (High), OpenAI o3 (Medium); a durable artifact of GPT structuring since GPT-3.5, persisting through the o-series reasoning models due to fundamental training data distributions.
- **Time evolution.** Emerged with GPT-3.5; high density through 4 and 4o; persistent in 5.1.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:manus-ai]`, `[cross-validated:perplexity]`, `[cross-validated:gemini]`, `[cross-validated:deepseek]`.
- **Signal strength.** MEDIUM standalone; HIGH in combination with bolded lead-ins. Per Gemini: 60 percent confidence for the tripartite-list variant specifically.
- **Base rate (per-family).** Very high in GPT-4o decision-support output (estimated 75 to 90 percent of responses to "what should I consider..." prompts). Per Gemini: found in 70 percent of instructional and analytical responses for the three-item-list variant.
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling for "structured" output. Secondary: training-data skew toward how-to and tutorial corpora. Gemini adds: system prompt artifacts prioritizing readability; markdown-saturated training data enforcing rigid structural rhythms.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate. Genuine list content warrants list structure. Per Gemini: HIGH (standard business writing relies heavily on tripartite lists).
- **Fix or remediation.** Use prose for prose-shaped content; reserve enumeration for genuinely parallel items. Per Gemini: convert the bullet points into a continuous narrative paragraph or manually alter the item count to break the predictable rhythm.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GPT-009: "In conclusion" / "To wrap up" final closer

- **ID.** A1-GPT-009
- **Name.** "In conclusion" / "To wrap up" final closer
- **Description.** GPT family closes long-form responses with an explicit "In conclusion," "To wrap up," "In summary," or "To recap" lead-in to the final paragraph. The closer signals the end of the response in a way that fluent writers avoid. Maps to v3.1.0 criterion 7 (Section-Ending Summaries).
- **Concrete examples.**
  1. "In conclusion, the migration is worth doing, with the caveats noted above."
  2. "To wrap up, the three main considerations are cost, performance, and team capacity."
  3. "In summary, this approach offers significant benefits but requires careful planning."
- **Location and register.** Final response paragraph; universal across registers but densest in academic and analytical prose.
- **Model attribution.** GPT family (high confidence). Claude produces similar closers but uses "Overall," or "Taken together," more often. Gemini variable.
- **Time evolution.** Stable across GPT versions.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:manus-ai]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Very high in GPT long-form output (estimated 60 to 80 percent of multi-paragraph responses).
- **Causal hypothesis (ranked).** Primary: training-data skew toward academic conventions (the five-paragraph essay structure with explicit conclusion lead-in). Secondary: RLHF reward modeling that may reward "clear structure."
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate. Academic writers use these closers.
- **Fix or remediation.** End on substance. If a recap is genuinely warranted, lead with the substantive conclusion, not the structural signal "in conclusion."
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER.

### A1-GPT-010: "It's important to remember" / "Keep in mind" reminders

- **ID.** A1-GPT-010
- **Name.** "It's important to remember" / "Keep in mind" reminders
- **Description.** GPT family inserts mid-response reminders that the reader should "remember" or "keep in mind" some qualifier. The reminders are an alignment-trained safety release similar to A1-CLAUDE-001 but framed as reminders rather than notes. Per DeepSeek's A1-GPT-006 ("It's important to remember that..."), a GPT variant of the cautionary preamble.
- **Concrete examples.**
  1. "It's important to remember that this advice depends on your specific situation."
  2. "Keep in mind that these performance numbers were measured on a particular hardware configuration."
  3. "Remember that the underlying assumptions may not hold for all use cases."
- **Location and register.** Mid-response qualifying inserts; universal across analytical and advisory registers.
- **Model attribution.** GPT family (high confidence). Claude has the "It is important to note" sibling (A1-CLAUDE-001).
- **Time evolution.** Stable across GPT versions.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:perplexity]`, `[cross-validated:manus-ai]`, `[cross-validated:deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** High in analytical and advisory GPT output (estimated 35 to 55 percent of long responses).
- **Causal hypothesis (ranked).** Primary: RLHF safety tuning. Secondary: refusal-avoidance behavior. Tertiary: training-data skew toward documentation and explainer prose.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate. The phrasing is common in tutorial writing.
- **Fix or remediation.** Cut. If the qualifier is genuinely important, embed in the main clause.
- **Era status.** Active.
- **Zone tag.** MID-BODY-INSERT.

### A1-GPT-011: Hallucinated citations and DOIs (style fingerprint)

- **ID.** A1-GPT-011
- **Name.** Hallucinated citations and DOIs (style fingerprint, mechanism in bucket C)
- **Description.** GPT family fabricates plausible-looking citations: author names, journal titles, DOIs, page numbers. The fabrications follow real bibliographic conventions (correct author/year structure, plausible journal acronyms, well-formed DOI prefixes). This is the stylistic fingerprint that signals possible fabrication. The detection mechanism and remediation protocol live in bucket C (synthesis-fact-checking). Maps to v3.1.0 criterion 23 (Hallucinated Citations) and criterion 21 (Citation Abnormalities).
- **Concrete examples.**
  1. "(Smith et al., 2019)" appearing in a response where Smith et al. 2019 with that finding does not exist.
  2. "doi:10.1038/s41586-023-01234-5" formatted correctly but resolving to a different paper or to nothing.
  3. "Journal of Computational Linguistics, vol. 45, no. 3, pp. 234-256" with the right format but the wrong content.
- **Location and register.** Citations within analytical, academic, and explainer prose.
- **Model attribution.** GPT family (very high confidence, especially 3.5 and 4 first generation). Claude family produces hallucinated citations too, with a notable variant: Claude over-produces plausible-seeming DOIs specifically. Gemini drifts to vague "studies show" assertions without identifiers (see A1-GEMINI-002). All families exhibit this; the pattern is structural to autoregressive generation.
- **Time evolution.** Present from GPT-3 forward; very high density in 3.5/4; reduced but not eliminated in 4o; reduced further with RAG-augmented deployments. Per Stanford RegLab measurements, legal-AI with RAG still hallucinates citations at 17 to 33 percent. Damien Charlotin's database now contains over 1,455 sanctioned legal cases involving AI-fabricated citations as of 2025 per Claude exec.
- **Sources.** `[claude-exec-2026-05-18]`, `[opus-expansion]` for the family-specific variants. Buchanan, Hill, and Shapoval (Sage 2024) measured hallucinated citation rates across multiple LLMs. Walters and Wilder (Scientific Reports 2023) measured the GPT-3.5/4 baseline. Chelli et al. (JMIR 2024) measured a 56 percent error rate among GPT-4o citations. `[cross-validated:perplexity]`, `[cross-validated:deepseek]`. ChatGPT's review classifies criteria 23 (Hallucinated Citations) as PROMOTE; the Claude expansion concurs.
- **Signal strength.** VERY HIGH per Claude's tier-shift recommendation (was MEDIUM for criteria 21 and 23 in v3.1.0; recommended PROMOTE both to HIGH).
- **Base rate (per-family).** Per family: GPT-3.5 30 to 55 percent of citations hallucinated (Walters and Wilder); GPT-4 18 to 29 percent; GPT-4o approximately 20 percent with 56 percent of those containing errors per Chelli; Claude 3.7 15 to 20 percent; Bard 91 percent (early measurement).
- **Causal hypothesis (ranked).** Primary: tokenizer and architecture effects (autoregressive token-by-token generation produces plausible bibliographic strings without verification). Secondary: training-data skew toward bibliographic corpora that the model has memorized at a surface level. Tertiary: helpfulness optimization that drives the model to produce a citation even when no real citation supports the claim.
- **Detection difficulty.** Hard for the citation existing; easy for the bibliographic style fingerprint (the way the citation is constructed and inserted).
- **False positive risk.** Low for the existence check (real citations exist or do not). Moderate for the style fingerprint (real writers also use bibliographic conventions).
- **Fix or remediation.** Verify every citation before publication. Use citation-management tools that cross-check existence. For known-bad LLM outputs, remove the citation and the claim it supports, then re-source the claim.
- **Era status.** Active. Improving slowly with RAG augmentation but far from solved.
- **Zone tag.** BODY-PERSISTENT.

### A1-GPT-012: Markdown formatting in plain-text contexts

- **ID.** A1-GPT-012
- **Name.** Markdown formatting in plain-text contexts
- **Description.** GPT family generates markdown formatting (asterisks for bold, hyphens for bullets, hashes for headers) in contexts where the rendering target is plain text (e.g., terminal output, plain-text email). The formatting leaks through and is visible as literal markdown characters rather than rendered formatting. Perplexity's A1-GPT-002 "Comprehensive Structure Header Cascade" frames the related pattern: GPT-4o defaults to markdown headers (##, ###) even in contexts where plain prose would serve better. Perplexity's A1-GPT-006 "Bold-Text Emphasis Cascade" captures the bolding density. Maps to v3.1.0 criterion 15 (Markdown Formatting Mixed with Standard Text).
- **Concrete examples.**
  1. (In a plain-text email reply) "**Important**: Please confirm receipt by EOD."
  2. (In a terminal output) "## Next Steps\n- Update the schema\n- Run the migration"
  3. (In a plain-text Slack DM that does not render markdown for that channel) "*This is intended as emphasis but renders as literal asterisks.*"
  4. (Per Perplexity) A 200-word email response formatted as: "## Overview\n## Key Points\n## Next Steps"
  5. (Per Perplexity) A creative writing prompt response that includes "## Narrative Arc\n## Character Development"
  6. (Per Perplexity) "**Machine learning** models rely on **large datasets** to produce **accurate predictions** through **iterative training**."
- **Location and register.** Plain-text channels; chat interfaces with limited rendering; terminal outputs.
- **Model attribution.** GPT family (high confidence). Gemini family has a notably stronger version of this pattern, near-deterministic per GitHub gemini-cli #8392 (per Claude's exec summary; not independently verified at expansion time). Claude family also produces it but at lower density.
- **Time evolution.** Persistent across GPT versions; partial mitigation via system-prompt instructions. Strong in GPT-4o; reducing in GPT-4.1 and GPT-5 for the bold-text emphasis specifically per Perplexity.
- **Sources.** `[claude-exec-2026-05-18]` (notes Gemini's plain-text markdown leakage as a near-deterministic signal). `[cross-validated:perplexity]`, `[cross-validated:gemini]`. `[opus-expansion]` for the GPT-specific variant.
- **Signal strength.** HIGH for Gemini in non-rendering channels; MEDIUM for GPT.
- **Base rate (per-family).** High when system-prompt does not include explicit "plain text only" instruction.
- **Causal hypothesis (ranked).** Primary: training-data skew toward markdown-rich corpora (GitHub, Stack Overflow, documentation). Secondary: RLHF reward modeling that may reward "structured" formatting. Tertiary: tokenizer effects (markdown characters are cheap single tokens).
- **Detection difficulty.** Easy. Unicode/character search for leftover markdown.
- **False positive risk.** Low.
- **Fix or remediation.** Strip the markdown. If rendering is desired, fix the channel. If plain text is desired, instruct the model accordingly.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GPT-013: o-series conclusion recapitulation

- **ID.** A1-GPT-013
- **Name.** o-series conclusion recapitulation
- **Description.** Per `[perplexity]`'s A1-GPT-004, OpenAI o1, o3, and o4-mini produce a distinctive structural artifact: after a reasoning-heavy body, the final paragraphs number and restate each conclusion, often as "1. X. 2. Y. 3. Z." The pattern is a surface trace of chain-of-thought reasoning that bleeds into the visible output.
- **Concrete examples.**
  1. "In summary: 1. The primary cause is resource contention. 2. The secondary effect is latency increase. 3. The recommended mitigation is sharding."
  2. "To recap the key points: First, [X]. Second, [Y]. Third, [Z]."
  3. "Conclusions: 1) System overload from peak load. 2) Insufficient buffer capacity. 3) Cascading failure pattern."
- **Location and register.** Closing paragraphs; technical analysis; any context involving extended reasoning.
- **Model attribution.** o-series exclusively. Not observed in GPT-4o, Claude, or Gemini at comparable rates.
- **Time evolution.** Introduced with o1 (September 2024). Present through o4-mini (May 2026).
- **Sources.** Hacker News thread on o1 (2024); generative-ai-newsroom.com analysis; practitioner documentation per Perplexity. `[cross-validated:deepseek]` for the related "o-Series Chain-of-Thought Artifacts."
- **Signal strength.** HIGH (family-unique).
- **Base rate (per-family).** MED in technical contexts; LOW in creative contexts.
- **Causal hypothesis (ranked).** Chain-of-thought training creates numbered-step reward shaping; the summarization move at the end mirrors the "verify your reasoning" pattern in training data.
- **Detection difficulty.** Easy.
- **False positive risk.** LOW. Human technical writers may enumerate conclusions but not with this specific regularity.
- **Fix or remediation.** Rewrite conclusion as prose that advances the argument rather than restating it.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER (o-series).

### A1-GPT-014: Uncertainty framing in reasoning traces (o-series)

- **ID.** A1-GPT-014
- **Name.** Uncertainty framing in reasoning traces (o-series)
- **Description.** Per `[perplexity]`'s A1-GPT-005, o-series models produce visible hedging within reasoning that bleeds into outputs: "I should note that," "It's important to acknowledge," "There's some uncertainty here about." The hedges are calibrated to the reasoning process, not the output, and create an overly hedged surface text.
- **Concrete examples.**
  1. "I should note that the specific figure may have changed since my training cutoff."
  2. "It's important to acknowledge that this analysis assumes stable market conditions."
  3. "There's some uncertainty about the exact mechanism, but the general pattern holds."
- **Location and register.** Analysis and explanation; appears throughout rather than only at uncertain claims.
- **Model attribution.** o-series; also present in Claude 3.5+ (different phrasing: "I'm not certain but...").
- **Time evolution.** Introduced with o1; persists.
- **Sources.** OpenAI blog on o1 reasoning; Hacker News practitioner discussion per Perplexity.
- **Signal strength.** MED alone.
- **Base rate (per-family).** MED.
- **Causal hypothesis (ranked).** RLHF reward for epistemic calibration; reasoning models trained to surface uncertainty.
- **Detection difficulty.** Medium.
- **False positive risk.** Medium. Careful human writers do flag genuine uncertainty.
- **Fix or remediation.** Keep uncertainty flags for genuinely uncertain claims; remove hedges on established facts.
- **Era status.** Active.
- **Zone tag.** MID-BODY-INSERT.

### A1-GPT-015: Caveat paragraph appended at end

- **ID.** A1-GPT-015
- **Name.** Caveat paragraph appended at end
- **Description.** Per `[perplexity]`'s A1-GPT-007, GPT-4o appends a disclaimer or caveat paragraph after the substantive content, covering topics like "consult a professional," "this does not constitute advice," or "your situation may differ." The paragraph appears even when the content is entirely factual and no professional consultation is warranted. The Manus AI catalog assigns this to v3.1.0 criterion 22 as REVISE; the Claude expansion's A3 matrix lists it as still valid with refresh.
- **Concrete examples.**
  1. (After a recipe) "Please note that nutritional values may vary based on specific ingredients and preparation methods. Consult a registered dietitian for personalized advice."
  2. (After a code example) "This example is for illustrative purposes only. Always test code in a staging environment before deploying to production."
  3. (After a general explanation) "Please note that this is a general overview. Specific situations may vary, and professional consultation is recommended for any consequential decisions."
- **Location and register.** Response closers; all genres.
- **Model attribution.** GPT-4o (highest); present in Claude with different phrasing; reduced in GPT-4.1.
- **Time evolution.** Strong in GPT-3.5 and GPT-4; reducing in later models.
- **Sources.** Practitioner observation; refusal-avoidance alignment documentation per Perplexity.
- **Signal strength.** MED.
- **Base rate (per-family).** HIGH in GPT-4o; MED in GPT-4.1+.
- **Causal hypothesis (ranked).** Alignment and safety tuning; refusal-avoidance behavior that appends disclaimers rather than refusing.
- **Detection difficulty.** Easy.
- **False positive risk.** Low. Human writers may add disclaimers but not with this formulaic consistency.
- **Fix or remediation.** Delete if content is factual. Keep only if the specific context genuinely requires professional consultation.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER.

### A1-GPT-016: Transition word cascade

- **ID.** A1-GPT-016
- **Name.** Transition word cascade
- **Description.** Per `[perplexity]`'s A1-GPT-009, GPT prose deploys formal transition words at a frequency that exceeds normal editorial practice: "Furthermore," "Moreover," "Additionally," "Consequently," "Notably," "Importantly," "Undoubtedly," "Nevertheless," "Notwithstanding." The words appear at the start of paragraphs and sentences that would flow naturally without them. Maps to v3.1.0 criterion 6 (Overuse of Transition Words). DeepSeek's A1-GPT-010 captures the "Additionally," / "Furthermore," sentence-initial pattern. The Claude expansion promotes criterion 6 from LOW to MED.
- **Concrete examples.**
  1. "Furthermore, the data suggests that early intervention is more cost-effective. Moreover, the long-term outcomes are measurably better."
  2. "Additionally, it is worth noting that the trend is accelerating. Consequently, businesses must act now."
  3. "Notably, the third option offers a balance. Importantly, this balance does not come without trade-offs."
- **Location and register.** All argumentative and analytical prose.
- **Model attribution.** GPT family (highest); present in all LLMs at elevated rates vs. human writing.
- **Time evolution.** Consistent. ChatGPT A3 review: DEMOTE (frontier models improved here; treat as low-value unless paired with uniform structure and section-ending summaries).
- **Sources.** Student Village 2024; Originality.ai 2025 per Perplexity.
- **Signal strength.** MED per word; HIGH for density (three or more per 300 words).
- **Base rate (per-family).** HIGH.
- **Causal hypothesis (ranked).** Primary: training data skew toward academic writing where formal transitions are conventionally required. Secondary: RLHF reward for "logical flow."
- **Detection difficulty.** Easy.
- **False positive risk.** Medium. Academic writers legitimately use these.
- **Fix or remediation.** Read each transition aloud and ask whether it adds meaning. "Furthermore" typically does not.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GPT-017: "I'd Be Happy To" service register

- **ID.** A1-GPT-017
- **Name.** "I'd Be Happy To" service register
- **Description.** Per `[perplexity]`'s A1-GPT-010, GPT models phrase willingness to help using customer-service register: "I'd be happy to," "I'd be glad to," "Feel free to ask," "Don't hesitate to reach out." The phrasing persists into technical and professional contexts where it is tonally incongruous. Maps to v3.1.0 criterion 36 (The Concierge Tone).
- **Concrete examples.**
  1. "I'd be happy to help you draft that legal brief."
  2. "Feel free to ask if you'd like me to expand on any of these points."
  3. "Don't hesitate to reach out if you have further questions about the API."
- **Location and register.** Response closers; assistant contexts.
- **Model attribution.** GPT-4o (highest); present in Claude less frequently; effectively absent from Gemini.
- **Time evolution.** Strong in GPT-3.5 and GPT-4o; reduced in GPT-4.1.
- **Sources.** LinkedIn practitioner lists; Originality.ai 2025 per Perplexity.
- **Signal strength.** HIGH (family-specific phrasing).
- **Base rate (per-family).** HIGH in GPT-4o; MED in GPT-4.1.
- **Causal hypothesis (ranked).** RLHF reward for helpfulness; annotators rate service-register as "helpful."
- **Detection difficulty.** Easy.
- **False positive risk.** LOW. Human professional writers rarely use this phrasing in documents.
- **Fix or remediation.** Delete. If a next-step offer is warranted, write it specifically: "I can also draft the follow-up email if you want."
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER.

### A1-GPT-018: Artificial enthusiasm markers

- **ID.** A1-GPT-018
- **Name.** Artificial enthusiasm markers
- **Description.** Per `[perplexity]`'s A1-GPT-011, GPT-4o produces enthusiasm about tasks and topics at a rate that doesn't correlate with the actual interest level of the content. "Great question!" appears before mundane prompts. "Fascinating!" appears before routine requests. Trending toward historical as of May 2026 per Perplexity. Maps to v3.1.0 criterion 36 (The Concierge Tone).
- **Concrete examples.**
  1. "Great question! The difference between TCP and UDP is..."
  2. "What a fascinating topic! Depreciation accounting works as follows..."
  3. "Excellent! Here is the JSON schema you requested..."
- **Location and register.** Response openers in conversational contexts.
- **Model attribution.** GPT-4o (highest); effectively trained out of GPT-5.
- **Time evolution.** Strong in GPT-4o; reduced in GPT-4.1; largely absent in GPT-5.
- **Sources.** LinkedIn practitioner lists 2025; practitioner community observation per Perplexity.
- **Signal strength.** HIGH (when present it is strongly indicative).
- **Base rate (per-family).** HIGH in GPT-4o; LOW in GPT-5.
- **Causal hypothesis (ranked).** RLHF reward for perceived engagement.
- **Detection difficulty.** Easy.
- **False positive risk.** LOW.
- **Fix or remediation.** Delete.
- **Era status.** Declining toward Historical.
- **Zone tag.** WRAPPER-OPENER.

### A1-GPT-019: Enthusiastic sign-offs

- **ID.** A1-GPT-019
- **Name.** Enthusiastic sign-offs
- **Description.** Per `[deepseek]`'s A1-GPT-002, GPT ends many responses with a cheerful, customer-service style closer ("I hope this helps!", "Let me know if you need anything else!"). Claude is more formal; Grok casual; Llama similar but less effusive. GPT-5 still does it.
- **Concrete examples.**
  1. "I hope this helps! Let me know if you need anything else."
  2. "Feel free to ask if you have more questions about this approach!"
  3. "Glad to help. Reach out anytime if you need clarification!"
- **Location and register.** Response closers.
- **Model attribution.** GPT family (high). Claude has the "I hope this helps" variant per A1-CLAUDE-011.
- **Time evolution.** Consistent through GPT-5.
- **Sources.** `[deepseek]`.
- **Signal strength.** HIGH.
- **Base rate (per-family).** Very high in unedited GPT dialogue.
- **Causal hypothesis (ranked).** RLHF helpfulness optimization; service-register annotation incentives.
- **Detection difficulty.** Easy.
- **False positive risk.** Low to moderate (customer service writing legitimately uses these).
- **Fix or remediation.** Strip the closer.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER.

### A1-GPT-020: "Game-changer" and buzzword overuse

- **ID.** A1-GPT-020
- **Name.** "Game-changer" and buzzword overuse
- **Description.** Per `[deepseek]`'s A1-GPT-008, GPT-4o and GPT-5 sometimes adopt a breathless marketing tone, describing features as "a game-changer" or "revolutionary." Distinct from Claude's cautious language. Maps to v3.1.0 criterion 28 (Hyperbolic Subheadings and Section Titles) and criterion 1 (Undue Emphasis on Importance and Symbolism).
- **Concrete examples.**
  1. "This is a game-changer for the industry."
  2. "A revolutionary approach to data management."
  3. "Truly groundbreaking work in the field of distributed systems."
- **Location and register.** Marketing, business, and product writing.
- **Model attribution.** GPT-4o and GPT-5 (both).
- **Time evolution.** Stable across GPT versions.
- **Sources.** `[deepseek]`.
- **Signal strength.** LOW but pattern helps family ID.
- **Base rate (per-family).** Moderate in marketing-register outputs.
- **Causal hypothesis (ranked).** Training data skew toward marketing and PR corpora.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate (marketing writers use these terms).
- **Fix or remediation.** Replace with specific descriptions of what makes the thing notable. "Game-changer" becomes "reduces costs by 40 percent" or "eliminates the manual reconciliation step."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

## A1.3 Google Gemini family

Models in scope: Gemini Pro, Flash, and Ultra across versions 1.x, 2.x, 3.0, and 3.1. The early Bard (2023, pre-Gemini rebrand) "As a large language model trained by..." preamble is Historical and lives in [historical-patterns.md](historical-patterns.md). The Gemini family produces some of the most distinctive patterns among current frontier families: plain-text markdown leakage at near-deterministic rates, vague attribution as a hallucination signature, and an exhaustive-survey marker that exceeds the analogous Claude and GPT patterns in measurable density.

### A1-GEMINI-001: Plain-text markdown leakage

- **ID.** A1-GEMINI-001
- **Name.** Plain-text markdown leakage
- **Description.** Gemini, especially in CLI and non-rendering deployments, leaks markdown formatting at near-deterministic rates per Claude's exec summary. The leakage is the sibling-but-more-extreme version of A1-GPT-012. Maps to v3.1.0 criterion 15 (Markdown Formatting Mixed with Standard Text).
- **Concrete examples.**
  1. (In a plain-text email response generated by Gemini API) "## Summary\n## Key Findings\n- **Finding 1**: ...\n- **Finding 2**: ..."
  2. (In a Slack DM that does not render markdown for that channel) "**Important context**: The deployment must complete before the regulatory deadline."
  3. (In terminal output from Gemini CLI) "### Steps\n1. **Configure** the API key.\n2. **Test** the endpoint.\n3. **Deploy** to production."
- **Location and register.** All registers in non-rendering channels.
- **Model attribution.** Gemini family (very high confidence). GPT family at lower density (A1-GPT-012). Claude variable.
- **Time evolution.** Present across Gemini versions; September 2025 Gemini formatting update (per 9to5Google) partially addressed but did not eliminate the pattern.
- **Sources.** `[claude-exec-2026-05-18]` (cites GitHub gemini-cli #8392 and 9to5Google September 2025 coverage). `[opus-expansion]` for the specifics not independently verified at expansion time.
- **Signal strength.** HIGH in non-rendering channels.
- **Base rate (per-family).** Near-deterministic per Claude exec.
- **Causal hypothesis (ranked).** Primary: training-data skew toward markdown-rich corpora. Secondary: RLHF reward modeling. Tertiary: tokenizer effects.
- **Detection difficulty.** Easy.
- **False positive risk.** Low.
- **Fix or remediation.** Strip markdown or instruct the model for plain text.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GEMINI-002: "Studies show" without identifiers (vague attribution)

- **ID.** A1-GEMINI-002
- **Name.** "Studies show" without identifiers (vague attribution)
- **Description.** Gemini family produces vague "studies show," "research indicates," "experts agree" assertions without naming the specific study, researcher, or expert. The pattern is sibling to GPT's hallucinated-citation problem but expresses as evasion rather than fabrication (no citation to verify or refute). Maps to v3.1.0 criterion 24 (Vague Attribution to Unnamed Authorities); Claude expansion promotes from MED to HIGH; Manus AI keeps as is.
- **Concrete examples.**
  1. "Studies show that this approach reduces error rates significantly."
  2. "Research indicates that team productivity improves with this methodology."
  3. "Experts in the field agree that the migration path should prioritize backward compatibility."
- **Location and register.** Body paragraphs; explanatory and persuasive registers.
- **Model attribution.** Gemini family (high confidence). All families produce this pattern at meaningful rates; Gemini is notable for higher density.
- **Time evolution.** Persistent across Gemini versions.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`. The mechanism (per-family hallucination signatures) lives in bucket C.
- **Signal strength.** HIGH for the "vague-attribution" pattern.
- **Base rate (per-family).** High in Gemini explanatory output (estimated 30 to 50 percent of analytical responses contain at least one vague-attribution).
- **Causal hypothesis (ranked).** Primary: refusal-avoidance behavior (model wants to back the claim but cannot find a specific citation, falls back to vague attribution). Secondary: training-data skew toward popular-science and explainer corpora where vague attribution is common.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate. Some genres legitimately use these constructions.
- **Fix or remediation.** Replace with the specific citation or remove the claim. If the claim is true, find the source. If the source cannot be found, the claim is suspect.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GEMINI-003: "Cool and unique" register tilt

- **ID.** A1-GEMINI-003
- **Name.** "Cool and unique" register tilt
- **Description.** Gemini family responses, especially in casual or marketing-adjacent registers, use words like "cool", "neat", "awesome", "unique", "exciting" at higher density than other frontier models. The register tilt is product-wrapper effect from Google's tuning of Gemini for consumer-facing surfaces.
- **Concrete examples.**
  1. "Here's a cool approach to consider..."
  2. "What's neat about this method is..."
  3. "It's exciting to think about the unique opportunities this opens up..."
- **Location and register.** Casual and consumer-facing registers.
- **Model attribution.** Gemini family (high confidence in consumer-facing tuning). GPT-4o produces similar at lower density.
- **Time evolution.** Stable across Gemini versions; tied to product-wrapper personality.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:perplexity]`. `[opus-expansion]` for the specific register tilt observation.
- **Signal strength.** MEDIUM standalone; HIGH in combination with other Gemini markers.
- **Base rate (per-family).** Moderate to high in consumer-facing Gemini output (estimated 30 to 50 percent of casual-register responses).
- **Causal hypothesis (ranked).** Primary: product-wrapper effects (Google's consumer-facing personality tuning). Secondary: training-data skew toward casual-register corpora.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate. Casual register writers use these words.
- **Fix or remediation.** Strip the register tilt. Substantive content does not need adjective inflation.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GEMINI-004: "Let's dive in" / "Without further ado" opener

- **ID.** A1-GEMINI-004
- **Name.** "Let's dive in" / "Without further ado" opener
- **Description.** Gemini family responses to substantive prompts often begin with explicit transition openers ("Let's dive in", "Without further ado", "Here we go") that signal start. The opener is throat-clearing that does no information work.
- **Concrete examples.**
  1. "Let's dive in to the architecture trade-offs."
  2. "Without further ado, here are the three approaches worth considering."
  3. "Alright, here we go: the migration plan in five steps."
- **Location and register.** Response openers.
- **Model attribution.** Gemini family (high confidence). GPT also produces these; less common in Claude.
- **Time evolution.** Stable across versions.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:perplexity]`, `[cross-validated:manus-ai]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Moderate in Gemini (estimated 20 to 40 percent of responses to substantive prompts).
- **Causal hypothesis (ranked).** Primary: training-data skew toward presentation and tutorial corpora. Secondary: product-wrapper personality tuning.
- **Detection difficulty.** Easy.
- **False positive risk.** Low.
- **Fix or remediation.** Strip the opener.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER.

### A1-GEMINI-005: Bulleted-everything default

- **ID.** A1-GEMINI-005
- **Name.** Bulleted-everything default
- **Description.** Gemini default outputs over-use bullets, often bulletizing material that prose would handle better. This is sibling to A1-GPT-008 but with different default thresholds.
- **Concrete examples.**
  1. Best seen in aggregate; Gemini defaults to bullet structure for many response types where prose would serve.
  2. (Asked "Explain why X is more efficient than Y") Gemini produces a bulleted list of efficiency factors rather than narrative explanation of the trade-off mechanics.
  3. (Asked "Tell me about the history of...") Gemini produces a bulleted chronology with sub-bullets rather than connected narrative.
- **Location and register.** Body of responses across registers.
- **Model attribution.** Gemini family (high confidence). GPT family also bulletizes heavily.
- **Time evolution.** Stable across Gemini versions.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:perplexity]`, `[cross-validated:manus-ai]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Very high in Gemini default outputs.
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling for structured output. Secondary: training-data skew toward documentation corpora.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate.
- **Fix or remediation.** Use prose for prose-shaped content.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GEMINI-006: The exhaustive survey marker

- **ID.** A1-GEMINI-006
- **Name.** The exhaustive survey marker
- **Description.** Per `[gemini]`'s A1-GEMINI-001, Gemini models compulsively use words denoting totality or multifaceted coverage regardless of the requested scope, attempting to signal absolute comprehensiveness. Words include "comprehensive", "multifaceted", "holistic", "various", "numerous". Gemini self-attributes the highest VTI score (0.590; the VTI metric is `[gemini]`-unique and unverified at merge time).
- **Concrete examples.**
  1. "This requires a comprehensive understanding of the various overlapping subsystems."
  2. "There are numerous multifaceted approaches to resolving this specific syntax error."
  3. "A holistic evaluation of the various endpoints reveals significant packet drift."
- **Location and register.** Theses, executive summaries, and opening paragraphs of research tasks.
- **Model attribution.** Google Gemini 3.1 Pro (High), Gemini 3.1 Flash (High) per `[gemini]`.
- **Time evolution.** Present since Gemini 1.5, slightly amplified in the 3.1 architecture as reasoning paths were extended.
- **Sources.** `[gemini]`.
- **Signal strength.** MEDIUM (75 percent confidence per Gemini).
- **Base rate (per-family).** Gemini 3.1 Pro exhibits the highest overall Verbal Tic Index score at 0.590 per `[gemini]`. (VTI is unverified at merge time.)
- **Causal hypothesis (ranked).** Primary: training data skew toward academic and encyclopedic registers. Secondary: helpfulness optimization prioritizing exhaustive breadth over concise depth.
- **Detection difficulty.** Easy.
- **False positive risk.** Medium.
- **Fix or remediation.** Delete filler adjectives (comprehensive, various, multifaceted, holistic) and specify the exact parameters of the claim.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GEMINI-007: Encrypted thought leakage

- **ID.** A1-GEMINI-007
- **Name.** Encrypted thought leakage (single-LLM-sourced, flagged for verification)
- **Description.** Per `[gemini]`'s A1-GEMINI-002, Gemini 3.0 and 3.1 models utilize "thought signatures" to pass reasoning states between API calls. In poorly formatted outputs or wrapper failures, these signatures leak directly into visible text. This is `[gemini]`-unique and unverified at merge time; the mechanism is plausible (similar to DeepSeek-R1 `<think>` tag leakage) but no independent corroboration is available.
- **Concrete examples.**
  1. " The optimal approach is clearly to index the primary key."
  2. "Considering the previous parallel function call, <thought_signature_xyz> the database requires an immediate flush."
  3. "If we evaluate the parameters <hidden_chain> the telemetry metrics align perfectly."
- **Location and register.** Code comments, multi-turn agentic loops, and complex API integrations.
- **Model attribution.** Google Gemini 3.1 Pro (High), Gemini 3.0 (Medium) per `[gemini]`.
- **Time evolution.** Emerged as a new artifact in early 2026 with the introduction of Deep Think Mini capabilities per `[gemini]`.
- **Sources.** `[gemini]`. Single-LLM-sourced; flagged for verification.
- **Signal strength.** Absolute (100 percent confirmation of AI origin) per `[gemini]`.
- **Base rate (per-family).** Rare in native web interfaces, but appears in roughly 4 percent of custom API wrappers failing to parse the JSON chunks per `[gemini]`.
- **Causal hypothesis (ranked).** Primary: product wrapper effects. Secondary: parsing errors in parallel function calling structures.
- **Detection difficulty.** Easy (highly visible syntax intrusion).
- **False positive risk.** Zero.
- **Fix or remediation.** Validate API parsing logic to strip thoughtSignature fields before rendering text to the end user.
- **Era status.** Active.
- **Zone tag.** MID-BODY-INSERT.

### A1-GEMINI-008: Numbered deep-dive list

- **ID.** A1-GEMINI-008
- **Name.** Numbered deep-dive list
- **Description.** Per `[perplexity]`'s A1-GEM-001, Gemini responds to general questions with exhaustive numbered lists that aim for comprehensiveness. Where GPT produces 5 to 7 items, Gemini often produces 10 to 15, covering every angle including marginal ones. The comprehensiveness is a Gemini-specific tell.
- **Concrete examples.**
  1. (Asked "What factors affect project success?") Gemini produces a 12-item numbered list covering everything from "clear communication" to "risk management" to "adequate stakeholder buy-in" with each item elaborated in a sub-paragraph.
  2. (Asked "What are the key considerations for cloud migration?") Gemini produces a 14-item list covering compute, storage, networking, security, compliance, cost, latency, observability, identity, disaster recovery, vendor lock-in, team training, change management, and rollback strategy.
  3. (Asked "How do I choose a database?") Gemini produces a 10-item list rather than the prose answer a human expert would give.
- **Location and register.** Any explanatory or advisory query.
- **Model attribution.** Gemini (highest for this pattern).
- **Time evolution.** Present from Gemini Pro through Gemini 2.5.
- **Sources.** PLoS One stylometry study 2025 (Gemini text lengths: mean 912.8 characters vs. Claude's 710.8); practitioner comparison per Perplexity.
- **Signal strength.** MED.
- **Base rate (per-family).** HIGH.
- **Causal hypothesis (ranked).** RLHF training emphasis on "helpfulness as coverage"; Google's training philosophy emphasizes comprehensive answers.
- **Detection difficulty.** Easy.
- **False positive risk.** Medium.
- **Fix or remediation.** Request a specified number of items; edit for relevance.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GEMINI-009: "Absolutely" opener with follow-on qualification

- **ID.** A1-GEMINI-009
- **Name.** "Absolutely" opener with follow-on qualification
- **Description.** Per `[perplexity]`'s A1-GEM-002, Gemini opens assistant responses with "Absolutely" and then immediately qualifies: "Absolutely, though it's worth noting..." The construction creates agreement followed by complication.
- **Concrete examples.**
  1. "Absolutely. This approach works well, though the specific results will depend on your implementation."
  2. "Absolutely, and it's worth highlighting a few nuances here."
  3. "Absolutely. That said, there are several considerations worth examining first."
- **Location and register.** Response openers in conversational contexts.
- **Model attribution.** Gemini (highest for "Absolutely" opener); GPT uses it also (A1-GPT-002).
- **Time evolution.** Present through Gemini 2.0; slightly reduced in Gemini 2.5.
- **Sources.** LobeHub marketplace signal list; practitioner observation per Perplexity.
- **Signal strength.** MED.
- **Base rate (per-family).** HIGH in Gemini; MED in others.
- **Causal hypothesis (ranked).** RLHF reward for affirming the user before responding.
- **Detection difficulty.** Easy.
- **False positive risk.** Low.
- **Fix or remediation.** Delete opener. Start with the answer.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER.

### A1-GEMINI-010: Formal academic register default

- **ID.** A1-GEMINI-010
- **Name.** Formal academic register default
- **Description.** Per `[perplexity]`'s A1-GEM-003, Gemini defaults to formal academic register even in contexts calling for conversational or practical tone. Sentence structures are passive-voice-heavy and nominalized. Maps to v3.1.0 criterion 9 (Passive Voice and "Has Been Described As") which Perplexity's A3 table proposes to REVISE because the pattern is now more characteristic of Gemini than Claude 4.
- **Concrete examples.**
  1. "The utilization of this methodology has been demonstrated to produce superior outcomes in contexts characterized by high complexity."
  2. "An examination of the available evidence suggests that the proposed solution merits further investigation."
  3. "It has been observed that the implementation of the framework results in measurable improvements across the relevant dimensions."
- **Location and register.** All contexts; most visible when the user asks for a casual explanation.
- **Model attribution.** Gemini (highest for formal register default); Claude hedges more but in active voice; GPT varies more by prompt.
- **Time evolution.** Present from Gemini Pro through 2.5; partially addressable by prompt.
- **Sources.** PLoS stylometry 2025 (Gemini texts: longer, more formal phrase patterns); practitioner observation per Perplexity.
- **Signal strength.** MED.
- **Base rate (per-family).** HIGH.
- **Causal hypothesis (ranked).** Training data skew: Google's training emphasizes web content that skews toward formal informational text (encyclopedias, Wikipedia, academic sources).
- **Detection difficulty.** Medium.
- **False positive risk.** Medium. Academic writers write this way legitimately.
- **Fix or remediation.** Explicitly request active voice and conversational tone. Or edit for voice on a targeted pass.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GEMINI-011: Parenthetical elaboration cascade

- **ID.** A1-GEMINI-011
- **Name.** Parenthetical elaboration cascade
- **Description.** Per `[perplexity]`'s A1-GEM-004, Gemini embeds elaborations in parentheses at higher rates than other families.
- **Concrete examples.**
  1. "The migration (which involved 12 services, 8 engineers, and approximately 240 person-hours) was completed under budget (by 11 percent)."
  2. "The database (PostgreSQL 15.2, running on a managed AWS RDS instance with multi-AZ failover) handles the primary workload."
  3. "The team (after several rounds of discussion) settled on an approach (the third option presented in the proposal)."
- **Location and register.** Analytical and technical writing.
- **Model attribution.** Gemini (highest); Claude uses parentheticals at lower rates; GPT varies.
- **Time evolution.** Consistent through Gemini versions.
- **Sources.** `[perplexity]` A1-GEM-004.
- **Signal strength.** LOW alone; MED in combination.
- **Base rate (per-family).** MED.
- **Causal hypothesis (ranked).** RLHF reward for "comprehensive" responses; training data skew toward technical writing where parentheticals are common.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate. Technical writers use parentheticals legitimately.
- **Fix or remediation.** Split into separate sentences where parentheticals carry significant content; remove where they add only flavor.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GEMINI-012: "Key takeaways" section appended

- **ID.** A1-GEMINI-012
- **Name.** "Key takeaways" section appended
- **Description.** Per `[perplexity]`'s A1-GEM-009, Gemini adds a terminal "Key Takeaways" or "Summary" section more consistently than other families.
- **Concrete examples.**
  1. (At end of an analytical response) "### Key Takeaways\n- The first finding is...\n- The second finding is...\n- The recommendation is..."
  2. (At end of a technical explainer) "**Summary:** The three points to remember are X, Y, and Z."
  3. (At end of a long answer) "**Key Takeaways:**\n1. Point one.\n2. Point two.\n3. Point three."
- **Location and register.** Long-form responses across registers.
- **Model attribution.** Gemini (highest).
- **Time evolution.** Consistent through Gemini versions.
- **Sources.** `[perplexity]` A1-GEM-009.
- **Signal strength.** MED.
- **Base rate (per-family).** High in unedited Gemini long-form output.
- **Causal hypothesis (ranked).** RLHF reward for "comprehensive" responses; training data skew toward Gemini's emphasis on summarization.
- **Detection difficulty.** Easy.
- **False positive risk.** Low to moderate (textbook prose uses key-takeaway sections).
- **Fix or remediation.** Remove if the body already made the points; keep only if the response is genuinely long enough to warrant a recap.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER.

### A1-GEMINI-013: Three-options offer

- **ID.** A1-GEMINI-013
- **Name.** Three-options offer
- **Description.** Per `[deepseek]`'s A1-GEMINI-005, Gemini often presents three distinct options or approaches labeled Option 1, Option 2, Option 3, a pattern less common in other families.
- **Concrete examples.**
  1. "Here are three approaches to consider: **Option 1: Conservative**... **Option 2: Balanced**... **Option 3: Aggressive**..."
  2. "**Option A** is the safest. **Option B** is the middle ground. **Option C** is the most ambitious."
  3. "There are three paths forward: minimal change, moderate restructuring, or complete rewrite. Each has different trade-offs."
- **Location and register.** Advisory and decision-support responses.
- **Model attribution.** Gemini (highest).
- **Time evolution.** Consistent through Gemini versions.
- **Sources.** `[deepseek]` A1-GEMINI-005.
- **Signal strength.** MEDIUM (specific pattern, family-characteristic).
- **Base rate (per-family).** Moderate in advisory contexts.
- **Causal hypothesis (ranked).** Training data skew toward consulting and decision-framework corpora.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate (consulting writers use this structure).
- **Fix or remediation.** Use only when the three options are genuinely distinct and parallel; otherwise present analysis as prose.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

## A1.4 Meta Llama family

Models in scope: Llama 3, 3.1, 3.2, and 4 (Scout, Maverick). The Llama 1 and Llama 2 era patterns are Historical and live in [historical-patterns.md](historical-patterns.md). The Llama family has a notable property documented across multiple sources: stylometric distinctiveness measurably stronger than the other major frontier families. The PLoS One stylometry study found Llama 3.1 placed separately from the other six LLMs on MDS dimensions, and human raters correctly identified Llama texts as AI-generated more accurately than any other model's output per `[perplexity]`. The Manus AI catalog lists Llama as more straightforward and factual; Gemini's catalog highlights Llama's near-zero em-dash and absent-conversational-warmth baseline. The 37.5x distinctiveness ratio cited by Gemini is `[gemini]`-unique and unverified.

### A1-LLAMA-001: Lower em-dash baseline and abrupt declarative pattern

- **ID.** A1-LLAMA-001
- **Name.** Lower em-dash baseline (near-zero) and abrupt declarative pattern
- **Description.** Llama and Meta.ai family produces em-dashes at near-zero baseline rate. Per `[gemini]`'s A1-LLAMA-001 "Punctuation-Based Markdown Suppression," the Llama architecture produces virtually zero specific punctuation artifacts when constrained to natural prose, demonstrating a distinct formatting suppression capability. The model exclusively uses parenthetical statements or semicolons; appositive phrases rely on commas, never stylistic dashes. This is itself a fingerprint: text that scores low on em-dash density is more likely to be Llama than other frontier families. Per `[perplexity]`'s A1-LLAMA-001, Llama 3.x produces text with stylometric features measurably distinct from human writing and from GPT/Claude/Gemini output, including abrupt sentence termination, lower subordinate clause density, and tendency toward declarative over complex sentences.
- **Concrete examples.**
  1. (Per Perplexity) "The model works. It processes input tokens. It generates output. The output is text." (abrupt declarative pattern)
  2. (Per Perplexity) "There are three factors. Each matters. The first is..."
  3. (Per Gemini) Model exclusively uses parenthetical statements (like this one) instead of sudden breaks.
  4. (Per Gemini) Transitions are handled via semicolons; harsher punctuation breaks are entirely absent.
  5. (Per Gemini) Appositive phrases rely strictly on commas, never stylistic dashes.
- **Location and register.** Universal across all textual outputs.
- **Model attribution.** Meta Llama 4 (High), Llama 3.2 (High), Llama 3.1 (High) per `[gemini]`.
- **Time evolution.** Consistent across Llama 3 and 4 versions; reflects training-data choices and RLHF methodology.
- **Sources.** `[claude-exec-2026-05-18]` (Claude exec specifically called out "Llama and Meta.ai at zero"). `[verified-arxiv:plos]` PLoS One stylometry study 2025 (Zaitsu et al.) confirms Llama distinctiveness. `[cross-validated:deepseek]`, `[cross-validated:perplexity]`, `[cross-validated:gemini]`, `[cross-validated:manus-ai]`. The Llama 4 model card and community license documentation note training-data choices that downweight academic/edited prose.
- **Signal strength.** HIGH when used as a negative marker for em-dash absence. Per Perplexity: HIGH (most human-detectable family as of 2024-2025 evidence) for the abrupt declarative pattern. Per Gemini: MEDIUM (representing an absence of a marker rather than a presence); 0.0 occurrences of targeted punctuation per 1,000 words.
- **Base rate (per-family).** Near zero in Llama output for em-dashes. HIGH for abrupt declarative cadence in unedited Llama 3.x output.
- **Causal hypothesis (ranked).** Primary: training-data choices that downweight academic/edited prose. Secondary: specific RLHF methodologies that actively suppress markdown-to-prose leakage during instruction tuning per Gemini. Tertiary: smaller parameter count (Llama 3.1: 8B-70B) may produce less syntactically complex output than models with substantially larger parameter budgets per Perplexity.
- **Detection difficulty.** Easy for em-dash absence (character count). Hard for the abrupt declarative pattern (requires statistical analysis of large text blocks per Gemini).
- **False positive risk.** High for the absence pattern (many human writers naturally avoid aggressive punctuation per Gemini). Low for the specific abrupt declarative pattern combined with low subordination per Perplexity.
- **Fix or remediation.** N/A for the punctuation baseline (this is a stylistic baseline, not an error). Identify and merge short declarative chains; add subordination where causal relationships exist per Perplexity.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT (negative marker for em-dash absence; positive marker for declarative cadence).

### A1-LLAMA-002: Sterile infrastructure tone

- **ID.** A1-LLAMA-002
- **Name.** Sterile infrastructure tone
- **Description.** Per `[gemini]`'s A1-LLAMA-002, Llama models default to a highly dry, infrastructure-focused vocabulary, actively eschewing the conversational warmth and sycophancy favored by commercial chat wrappers. Cross-validates with `[opus-expansion]` "Open-source register and 'let's get technical' voice": Llama family, especially when run with default open-source-developer fine-tunes, uses a register that mirrors open-source documentation and developer blog conventions. Voice is more terse than Claude or GPT.
- **Concrete examples.**
  1. (Per Gemini) "The system executes the security protocol sequentially."
  2. (Per Gemini) "Validation of the telemetry parameters returns a positive state."
  3. (Per Gemini) "The current architecture supports the required packet throughput."
- **Location and register.** General chat, technical documentation, and basic instructional queries.
- **Model attribution.** Meta Llama 4 (High), Llama 3.2 (High) per `[gemini]`.
- **Time evolution.** Consistent since Llama 2, maintained as Meta shifts focus toward developer-first ecosystems and agentic orchestration.
- **Sources.** `[gemini]`, `[opus-expansion]`, `[cross-validated:manus-ai]`. Per `[gemini]`: 37.5x distinctiveness ratio compared to the prose styles of other models (this specific figure is `[gemini]`-unique and unverified).
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** High distinctiveness ratio of 37.5x compared to other models per `[gemini]` (single-LLM sourced).
- **Causal hypothesis (ranked).** Training data heavily weighted toward GitHub and technical infrastructure documentation over conversational transcripts.
- **Detection difficulty.** Medium.
- **False positive risk.** High (reads exactly like standard technical writing).
- **Fix or remediation.** Inject tone-shaping directives into the system prompt to force conversational variance if a casual tone is required.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-LLAMA-003: Fabrication at long context (above 32K tokens)

- **ID.** A1-LLAMA-003
- **Name.** Fabrication at long context (above 32K tokens)
- **Description.** Llama family hallucinates facts at notably higher rates when context length exceeds approximately 32K tokens. The pattern is documented in RIKER benchmark results referenced by Claude's exec summary. This pattern intersects with the fact-checking layer (bucket C) and connects to the C1-TOOLHALL family of tool-specific hallucination patterns.
- **Concrete examples.**
  1. Long-document summarization tasks at 40K+ tokens of context where Llama fabricates names, dates, or specific quantitative claims not present in the source material.
  2. Multi-turn agent loops where Llama, after 50+ turns, begins producing factual claims about earlier turns that did not occur.
  3. RAG-augmented queries where the retrieved context exceeds 32K tokens and Llama produces conclusions that are not supported by any retrieved chunk.
- **Location and register.** Long-context applications: document summarization, RAG over large corpora, extended agent loops.
- **Model attribution.** Llama family (high confidence at long context). Other frontier families also fabricate at long context but Llama is notably worse per the RIKER benchmark.
- **Time evolution.** Has not improved significantly across Llama 3 to 4; long-context fabrication is a known weakness.
- **Sources.** `[claude-exec-2026-05-18]` (cites RIKER specifically). `[opus-expansion]` for the specific 32K threshold which is approximate.
- **Signal strength.** HIGH in long-context applications.
- **Base rate (per-family).** Substantially elevated above 32K context.
- **Causal hypothesis (ranked).** Primary: attention-mechanism degradation at long context. Secondary: training-data scarcity for very long context windows. Tertiary: positional encoding limitations.
- **Detection difficulty.** Hard (requires comparing output against source material).
- **False positive risk.** Low (real claims can be verified against source; fabricated claims cannot).
- **Fix or remediation.** Verify all factual claims in long-context Llama output against the source. For RAG applications, chunk context to stay below 32K and use citation-required generation.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-LLAMA-004: Direct-question response without preamble

- **ID.** A1-LLAMA-004
- **Name.** Direct-question response without preamble
- **Description.** Llama responds more directly to questions without warm openers ("Great question!", "Thank you for asking"). The directness is itself a fingerprint distinguishing Llama from RLHF-heavy Claude/GPT.
- **Concrete examples.**
  1. (User: "What is the time complexity of binary search?") Llama: "O(log n)."
  2. (User: "Should I use Postgres or Redis here?") Llama: "Postgres for ACID compliance and SQL queries. Redis if low-latency in-memory is the primary requirement."
  3. (User: "Explain the difference between TCP and UDP.") Llama: "TCP is connection-oriented and provides reliable, ordered delivery. UDP is connectionless and provides best-effort delivery with lower overhead."
- **Location and register.** Response openers across registers.
- **Model attribution.** Llama family (high confidence as a negative marker).
- **Time evolution.** Consistent across Llama versions.
- **Sources.** `[claude-exec-2026-05-18]`, `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** MEDIUM as a negative marker (absence of opener pleasantries).
- **Base rate (per-family).** Very high in unedited Llama output.
- **Causal hypothesis (ranked).** Primary: lower-RLHF baseline compared to Claude/GPT. Secondary: training-data skew toward technical documentation rather than conversational corpora.
- **Detection difficulty.** Easy (compare against expected RLHF-trained opener density).
- **False positive risk.** Moderate (skilled technical writers also default to direct answers).
- **Fix or remediation.** N/A (this is a stylistic baseline preference).
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER (negative marker for opener pleasantries).

### A1-LLAMA-005: Code-comment fluency in code outputs

- **ID.** A1-LLAMA-005
- **Name.** Code-comment fluency in code outputs
- **Description.** Llama-coded model outputs include code with somewhat denser inline comments than baseline. The pattern reflects fine-tuning data with code-heavy comments. Per `[perplexity]`'s A1-LLAMA-007 "Code-comment bleedthrough," Llama-based code models produce natural language that structurally mirrors code comments: brief, terse, imperative.
- **Concrete examples.**
  1. (Code block from Llama) Every function carries a doc comment; every loop carries a one-line explanation; every conditional carries a "why" comment.
  2. (Prose from Llama Code variant) "Initialize counter. Validate input. Process each item. Return result." (reads like code comments rather than natural prose)
- **Location and register.** Technical code-adjacent writing.
- **Model attribution.** Llama family, particularly Code-variant fine-tunes.
- **Time evolution.** Consistent across Llama Code variants.
- **Sources.** `[opus-expansion]`, `[cross-validated:deepseek]`, `[cross-validated:perplexity]`.
- **Signal strength.** LOW (genre-specific).
- **Base rate (per-family).** High in code-fine-tuned Llama variants.
- **Causal hypothesis (ranked).** Fine-tuning data choices emphasize code with extensive comments.
- **Detection difficulty.** Easy in code contexts.
- **False positive risk.** Low (the structural mirroring of code comments is uncommon in skilled human prose).
- **Fix or remediation.** Reformat prose to natural narrative structure; keep code comments separate from prose explanations.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-LLAMA-006: Refusal under-rotation

- **ID.** A1-LLAMA-006
- **Name.** Refusal under-rotation
- **Description.** Llama base models under-refuse compared to Claude/GPT, producing content for prompts that frontier RLHF models would soften or decline. This is itself a fingerprint, especially in safety-sensitive registers.
- **Concrete examples.**
  1. Llama produces direct technical content for prompts where Claude or GPT would add safety hedges or decline.
  2. Llama answers borderline questions with the substantive answer rather than the meta-explanation about why the question is borderline.
  3. Llama lacks the "I should note that this is general information; please consult a professional" closer that Claude and GPT reflexively add.
- **Location and register.** Safety-sensitive registers (medical, legal, financial) and borderline-content registers.
- **Model attribution.** Llama family (high confidence as a negative marker).
- **Time evolution.** Consistent across Llama versions; Meta's RLHF approach explicitly differs from Anthropic and OpenAI.
- **Sources.** `[claude-exec-2026-05-18]`, `[opus-expansion]`.
- **Signal strength.** MEDIUM as a family marker.
- **Base rate (per-family).** Substantially lower refusal rate than frontier RLHF models.
- **Causal hypothesis (ranked).** Primary: RLHF methodology choices that under-prioritize refusal training compared to Claude/GPT. Secondary: open-source-aligned training philosophy that favors capability over caution.
- **Detection difficulty.** Medium (requires comparing the response against expected refusal patterns).
- **False positive risk.** Low (the absence of expected refusal hedges is a specific, observable difference).
- **Fix or remediation.** N/A as a content-quality concern; relevant for safety auditing. For published content that is auditing the AI source, the under-refusal pattern is a Llama fingerprint.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-LLAMA-007: First-person opinion phrases

- **ID.** A1-LLAMA-007
- **Name.** First-person opinion phrases
- **Description.** Per `[deepseek]`'s A1-LLAMA-001, "I think", "I believe", "In my opinion," appear with high frequency, reflecting a more personal tone. Llama 3 and 4 both do this.
- **Concrete examples.**
  1. "I think the best approach here is to use the indexing strategy."
  2. "In my opinion, the trade-off favors the lower-latency option."
  3. "I believe the right answer depends on the specific workload."
- **Location and register.** Body paragraphs across registers.
- **Model attribution.** Llama family (high confidence). Less common in Claude (which hedges more impersonally) and GPT (which uses service-register hedges).
- **Time evolution.** Consistent across Llama 3 and 4.
- **Sources.** `[deepseek]`.
- **Signal strength.** HIGH (family-distinctive).
- **Base rate (per-family).** Very frequent in unedited Llama analytical output.
- **Causal hypothesis (ranked).** RLHF tuning that rewards conversational warmth via first-person opinion phrasing rather than impersonal hedging.
- **Detection difficulty.** Easy (specific phrases).
- **False positive risk.** Moderate (human writers use first-person opinion phrases legitimately).
- **Fix or remediation.** State the claim directly. "I think X" becomes "X" when the claim is the actual position; "I think X" becomes "X under condition Y" when the qualification is the point.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-LLAMA-008: Shorter, more direct sentences

- **ID.** A1-LLAMA-008
- **Name.** Shorter, more direct sentences
- **Description.** Per `[deepseek]`'s A1-LLAMA-002, Llama output exhibits lower average sentence length and less subordination than Claude or GPT, giving a punchier, sometimes blog-like cadence. Cross-validates with A1-LLAMA-001's "abrupt declarative pattern."
- **Concrete examples.**
  1. "The system works. It scales. It costs less." (Llama-typical short cadence)
  2. "Postgres handles the writes. Redis handles the cache. Together they cover the workload."
  3. "The migration took six weeks. Three engineers worked on it. The team learned a lot."
- **Location and register.** Body paragraphs across registers.
- **Model attribution.** Llama family (high confidence).
- **Time evolution.** Consistent across Llama versions.
- **Sources.** `[deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** High in unedited Llama analytical output.
- **Causal hypothesis (ranked).** Training data emphasis on developer documentation and blog corpora rather than academic prose.
- **Detection difficulty.** Medium (requires aggregate sentence-length analysis).
- **False positive risk.** Moderate (skilled writers deliberately vary sentence length).
- **Fix or remediation.** Add subordination where causal relationships exist; merge short declaratives into compound sentences where the connection is logical.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-LLAMA-009: "I'm just an AI, so take this with a grain of salt"

- **ID.** A1-LLAMA-009
- **Name.** "I'm just an AI, so take this with a grain of salt"
- **Description.** Per `[deepseek]`'s A1-LLAMA-004, self-disclaimer that emerged in Llama 3 and persists in 4.
- **Concrete examples.**
  1. "I'm just an AI, so take this with a grain of salt, but..."
  2. "As an AI model, I can offer a perspective, though it should not replace expert judgment."
  3. "I'm not perfect (I'm an AI), but here is my best understanding..."
- **Location and register.** Opinion or advisory responses.
- **Model attribution.** Llama family (high confidence). Different from Claude's "I'm an AI assistant" or GPT's historical "As an AI language model" preamble.
- **Time evolution.** Emerged in Llama 3; persists in Llama 4.
- **Sources.** `[deepseek]`.
- **Signal strength.** HIGH (specific phrasing).
- **Base rate (per-family).** Moderate in opinion-seeking responses.
- **Causal hypothesis (ranked).** RLHF tuning that explicitly trains self-disclaimer responses for opinion or advisory prompts.
- **Detection difficulty.** Easy.
- **False positive risk.** Very low (the specific phrasing is uncommon in skilled human writing).
- **Fix or remediation.** Strip the disclaimer. State the opinion directly; if uncertainty is genuine, name what specifically is uncertain.
- **Era status.** Active.
- **Zone tag.** HYBRID (can appear as opener disclaimer or mid-body insert).

### A1-LLAMA-010: Reduced hedging and assertive claims

- **ID.** A1-LLAMA-010
- **Name.** Reduced hedging and assertive claims
- **Description.** Per `[perplexity]`'s A1-LLAMA-004, Llama hedges less than Claude or GPT; assertions are bolder and sometimes overstate certainty. Cross-validates with `[deepseek]`'s A1-LLAMA-005 (Assertive Claims Without Hedging).
- **Concrete examples.**
  1. (Llama-typical) "The migration will improve performance by 40 percent." (without hedging)
  2. (Claude-typical equivalent) "The migration is likely to improve performance, potentially by as much as 40 percent depending on the specific workload characteristics."
  3. (Llama-typical) "This is the right approach." (vs. Claude's "This is generally considered the recommended approach, though specific contexts may warrant alternatives.")
- **Location and register.** Body paragraphs across registers.
- **Model attribution.** Llama family (high confidence as a negative marker for hedging).
- **Time evolution.** Consistent across Llama versions.
- **Sources.** `[perplexity]`, `[deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Substantially lower hedging rate than Claude or GPT.
- **Causal hypothesis (ranked).** Primary: lower-RLHF baseline. Secondary: training-data skew toward developer documentation that asserts rather than hedges. Tertiary: Meta's RLHF philosophy that favors capability over caution.
- **Detection difficulty.** Medium (requires comparing the response against expected hedging patterns).
- **False positive risk.** Moderate (skilled writers also make assertions without hedging when warranted).
- **Fix or remediation.** N/A as a stylistic baseline; relevant when factual accuracy matters and the assertion is wrong.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

## A1.5 xAI Grok family

Models in scope: Grok 2, 3, and 4. The Grok 1 (Nov 2023) historical entry lives in [historical-patterns.md](historical-patterns.md). Grok has a stylometric identity distinct from the other major families. Copyleaks tested Grok-1 output against a four-family (Claude, Gemini, Llama, OpenAI) ensemble and produced 100 percent "no-agreement" classifications, meaning the ensemble unanimously declined to attribute Grok output to any of the four known families per `[perplexity]`. Practitioner observation provides most of the specific surface features; peer-reviewed stylometric studies of Grok output are limited as of May 2026.

### A1-GROK-001: Colloquial internet-native register and edgy sarcasm

- **ID.** A1-GROK-001
- **Name.** Colloquial internet-native register and edgy sarcasm
- **Description.** Grok family produces output with a notably colloquial, internet-native register that includes references to internet culture, casual phrasing, and occasional humor. This is product-wrapper effect from xAI's "edgier" positioning. Per `[gemini]`'s A1-GROK-001 "Edgy Sarcasm Override," Grok actively rejects corporate neutrality, frequently injecting sarcastic or hyper-colloquial phrasing into otherwise straightforward professional queries. Per Grok deliverable's A1-GROK-012 "Direct positioning and lower sycophancy," Grok outputs show lower rates of concierge tone and reflexive agreement, more frequently take explicit positions or acknowledge limitations without heavy hedging, and display willingness to disagree or qualify user premises.
- **Concrete examples.**
  1. (Per Gemini) "Let's be real, nobody actually reads the terms of service."
  2. (Per Gemini) "Here is the code you asked for. Try not to break production this time."
  3. (Per Gemini) "The marketing strategy is a bit of a dumpster fire, but it could work if properly funded."
  4. (Per Grok deliverable) "That framing assumes the bottleneck is technical when evidence points to organizational incentives as the primary constraint."
  5. (Per Grok deliverable) "The claim holds in controlled settings but breaks down under real distribution shift. Here is why."
  6. (Per Grok deliverable) "Most analyses overstate the effect size. The studies you are thinking of used convenience samples."
  7. (Per Manus AI) "Here's the deal..."
  8. (Per Manus AI) "Get this: "
  9. (Per Manus AI) "It's like, you know..."
- **Location and register.** General conversational queries, coding assistance, and real-time news summaries. Per Grok deliverable: analytical responses, technical explanations, and any register where positioning or critique is appropriate.
- **Model attribution.** Grok family (very high confidence). Per Gemini: xAI Grok 4 (High), Grok 3 (High). Per Grok deliverable: Grok family (high), also observed in some DeepSeek and Mistral variants.
- **Time evolution.** Hardcoded into the base model since Grok 1, maintained through Grok 4's deployment as a brand differentiator per Gemini. Per Grok deliverable: consistent across Grok versions; alignment appears to have preserved or strengthened directness rather than sanding it down.
- **Sources.** `[claude-exec-2026-05-18]`, `[cross-validated:perplexity]`, `[cross-validated:manus-ai]`, `[cross-validated:gemini]`, `[cross-validated:grok]`. xAI release notes for Grok 4. Per Gemini: 90 percent confidence.
- **Signal strength.** HIGH for the register tilt; specific phrases vary. Per Grok deliverable: HIGH when the surrounding context would normally elicit sycophantic or heavily hedged responses from other families.
- **Base rate (per-family).** Present in roughly 35 percent of non-technical outputs (highly dependent on the activation of "Fun Mode") per Gemini. Medium in unedited Grok analytical output per Grok deliverable.
- **Causal hypothesis (ranked).** Primary: direct RLHF tuning designed to mimic internet subcultures and avoid sterile corporate safety filters per Gemini. xAI alignment choices that prioritize truth-seeking over user-pleasing per Grok deliverable. Secondary: different RLHF emphasis on helpfulness versus sycophancy avoidance. Tertiary: training mixture that includes more contrarian or direct source material.
- **Detection difficulty.** Easy. Per Grok deliverable: easy once calibrated. Compare tone against expected register for the query.
- **False positive risk.** Low in most professional contexts. Per Gemini: low (humans rarely write professional documentation with this specific blend of colloquialism).
- **Fix or remediation.** Use strict system prompts (e.g., the E.R.A. framework) to force the model into a rigid professional persona per Gemini. When the goal is neutral synthesis, add explicit hedging or multiple perspectives if warranted by evidence per Grok deliverable.
- **Era status.** Active.
- **Zone tag.** HYBRID (register tilt distributes across body; specific colloquial framings sometimes appear in openers).

### A1-GROK-002: "Based on X" framing for opinion-seeking prompts

- **ID.** A1-GROK-002
- **Name.** "Based on X" framing for opinion-seeking prompts
- **Description.** Grok grounds opinion-style answers with "Based on the data," "Based on what's available online," or similar framings more visibly than other families. This is alignment-trained avoidance.
- **Concrete examples.**
  1. "Based on the data available online, the most likely cause is..."
  2. "Based on what's been reported in recent coverage, the consensus is..."
  3. "Based on the evidence I can access, the answer leans toward..."
- **Location and register.** Opinion-seeking and recent-events responses.
- **Model attribution.** Grok family (high confidence).
- **Time evolution.** Stable across Grok versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Moderate in opinion-style and recency-sensitive responses.
- **Causal hypothesis (ranked).** Primary: alignment-trained grounding that explicitly cites the basis. Secondary: real-time-data deployment surface (Grok's X integration) reinforces the framing.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate (skilled writers also ground claims in evidence).
- **Fix or remediation.** If the basis is specific, name it specifically ("Based on the August 2025 OECD report..." rather than "Based on the data available online").
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER (typically appears as the opening framing of the response).

### A1-GROK-003: Lower hedging density

- **ID.** A1-GROK-003
- **Name.** Lower hedging density
- **Description.** Grok produces fewer "It is important to note" preambles than Claude/GPT. The negative-marker signal is useful when combined with the colloquial-register positive marker. Cross-validates with `[perplexity]`'s "A1-GROK-003: Direct assertion without hedge."
- **Concrete examples.**
  1. (Grok-typical) "The migration will work." (vs. Claude's "The migration is likely to succeed, though specific implementation details may affect outcomes.")
  2. (Grok-typical) "This is the right answer." (vs. GPT's "It's important to note that this is generally considered the recommended approach.")
  3. (Grok-typical) "Use Postgres." (vs. Claude's "While the decision depends on your specific requirements, Postgres is often a strong default.")
- **Location and register.** Body paragraphs across registers.
- **Model attribution.** Grok family (high confidence as a negative marker).
- **Time evolution.** Consistent across Grok versions.
- **Sources.** `[claude-exec-2026-05-18]`, `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** MEDIUM as a negative marker.
- **Base rate (per-family).** Substantially lower hedging rate than Claude or GPT.
- **Causal hypothesis (ranked).** xAI's alignment philosophy that favors directness over caution.
- **Detection difficulty.** Medium (requires comparing against expected hedging patterns).
- **False positive risk.** Moderate (skilled writers also assert directly when warranted).
- **Fix or remediation.** N/A as a content-quality concern; relevant for stylistic baseline.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GROK-004: Twitter-style structural defaults

- **ID.** A1-GROK-004
- **Name.** Twitter-style structural defaults
- **Description.** Grok outputs sometimes default to Twitter/X-shaped structure (short paragraphs, rapid-fire claims, lower formality). Product-wrapper effect. Cross-validates with `[deepseek]`'s "A1-GROK-004: On X, people are saying..." which captures the social media framing.
- **Concrete examples.**
  1. Short, one-sentence paragraphs strung together rather than developed argument.
  2. "Hot takes" framing: "Here's the take: [claim]. Here's why: [brief support]."
  3. (Per DeepSeek) "On X, people are saying that the new model is significantly faster than the previous version."
- **Location and register.** Body paragraphs, conversational and informal registers.
- **Model attribution.** Grok family (high confidence).
- **Time evolution.** Consistent across Grok versions; reflects xAI's X-integration deployment.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Moderate in conversational and informal responses.
- **Causal hypothesis (ranked).** Product-wrapper effect from X integration; training data may include X-derived corpora.
- **Detection difficulty.** Easy (compare paragraph length distribution).
- **False positive risk.** Moderate (some writers use short-paragraph cadence deliberately).
- **Fix or remediation.** Develop arguments into full paragraphs where the content warrants; reserve short cadence for genuine punch.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GROK-005: Real-time data references

- **ID.** A1-GROK-005
- **Name.** Real-time data references
- **Description.** Grok 3 and 4 sometimes include references to "recent data" or "current information" that suggest real-time access. Where the references are not anchored to specific dates or sources, they are pattern markers. Cross-validates with `[deepseek]`'s "A1-GROK-002: Based on current information..." which captures the temporal anchoring phrase.
- **Concrete examples.**
  1. "Based on current information, the figure is approximately X."
  2. "As of recent reporting, the trend is moving in the direction of Y."
  3. "According to data available right now, the situation is..."
- **Location and register.** Body paragraphs, recency-sensitive responses.
- **Model attribution.** Grok family (high confidence).
- **Time evolution.** Strengthened in Grok 3 and 4 as real-time data integration deepened.
- **Sources.** `[claude-exec-2026-05-18]`, `[opus-expansion]`, `[cross-validated:deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** High in recency-sensitive responses.
- **Causal hypothesis (ranked).** Product surface (X integration provides real-time data) reflected in training and prompting.
- **Detection difficulty.** Easy.
- **False positive risk.** Low (the specific vague-anchoring is uncommon in skilled human writing, which would name the specific source).
- **Fix or remediation.** Anchor to specific dates and sources. "Based on current information" becomes "Based on the May 14, 2026 SEC filing" if the source exists.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GROK-006: Pop-culture allusions

- **ID.** A1-GROK-006
- **Name.** Pop-culture allusions
- **Description.** Grok includes more pop-culture references (memes, internet trends, specific TV/film references) than other families. Product-wrapper personality. Cross-validates with `[perplexity]`'s "A1-GROK-004: Pop culture reference injection" and `[deepseek]`'s "A1-GROK-005: Internet Slang and Abbreviations" (ICYMI, FWIW, TL;DR).
- **Concrete examples.**
  1. "This is the 'one does not simply' problem applied to enterprise SaaS."
  2. "If you've ever watched Office Space, you know exactly what's wrong with this approval workflow."
  3. "TBH this is overkill for your use case. ICYMI, the simpler approach works fine."
- **Location and register.** Conversational and casual responses.
- **Model attribution.** Grok family (high confidence).
- **Time evolution.** Consistent across Grok versions; reflects xAI's brand positioning.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Moderate in casual responses.
- **Causal hypothesis (ranked).** Product-wrapper personality; training data includes X-derived corpora that are rich in pop-culture references.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate (skilled writers also use pop-culture allusions).
- **Fix or remediation.** Strip if professional context; keep if conversational context aligns.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GROK-007: Skepticism-of-establishment positioning

- **ID.** A1-GROK-007
- **Name.** Skepticism-of-establishment positioning
- **Description.** Grok occasionally positions itself in light opposition to "establishment" framings, often using phrasings like "Despite what mainstream sources say..." This is xAI's explicit personality tuning. Cross-validates with `[perplexity]`'s A1-GROK-001 "Contrarian framing": Grok more frequently challenges premises of questions than other models.
- **Concrete examples.**
  1. "Despite what mainstream sources say, the actual mechanism is..."
  2. "The conventional view misses an important factor: ..."
  3. "Most analyses get this backwards. The real driver is..."
- **Location and register.** Analytical and explanatory responses on contested topics.
- **Model attribution.** Grok family (high confidence).
- **Time evolution.** Strengthened across Grok versions as xAI emphasizes its differentiation.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Moderate in analytical and contested-topic responses.
- **Causal hypothesis (ranked).** xAI's explicit alignment philosophy that favors challenging premises.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate (skilled writers also challenge premises legitimately).
- **Fix or remediation.** If the challenge is substantiated, develop the specific evidence; if it is rhetorical posturing, remove.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-GROK-008: "The thing about [topic] is..."

- **ID.** A1-GROK-008
- **Name.** "The thing about [topic] is..." colloquial framing
- **Description.** Per `[deepseek]`'s A1-GROK-001, colloquial, conversational opener that frames the answer as insider insight. Highly distinctive.
- **Concrete examples.**
  1. "The thing about distributed systems is that most failures are operational, not architectural."
  2. "The thing about this market is that nobody actually wants the feature you're building."
  3. "The thing about RLHF is that it optimizes for what annotators reward, not what users actually need."
- **Location and register.** Conversational analytical responses.
- **Model attribution.** Grok family (high confidence).
- **Time evolution.** Consistent across Grok versions.
- **Sources.** `[deepseek]`.
- **Signal strength.** HIGH (family-distinctive).
- **Base rate (per-family).** Moderate in conversational analytical responses.
- **Causal hypothesis (ranked).** Product-wrapper personality; training data emphasizes conversational analytical register.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate (skilled writers use this opener legitimately).
- **Fix or remediation.** Lead with the actual claim. "The thing about X is Y" becomes "X is shaped by Y."
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER (typical opener framing) or MID-BODY-INSERT (when used to introduce a new section's claim).

### A1-GROK-009: "TL;DR" summary at end

- **ID.** A1-GROK-009
- **Name.** "TL;DR" summary at end
- **Description.** Per `[deepseek]`'s A1-GROK-006, a concise, casual summary labeled "TL;DR" is a Grok staple.
- **Concrete examples.**
  1. (At end of analytical response) "TL;DR: Use Postgres for ACID, Redis for cache, and don't overthink it."
  2. (At end of decision-support) "TL;DR: Go with Option 2."
  3. (At end of long explanation) "TL;DR: The answer is X because of Y, despite what most people think."
- **Location and register.** Response closers in informal and analytical responses.
- **Model attribution.** Grok family (high confidence). Less common in Claude, GPT, Gemini.
- **Time evolution.** Consistent across Grok versions.
- **Sources.** `[deepseek]`.
- **Signal strength.** HIGH (family-distinctive label).
- **Base rate (per-family).** Frequent in long-form Grok responses.
- **Causal hypothesis (ranked).** Product-wrapper personality; X-derived training data uses TL;DR as common closer.
- **Detection difficulty.** Easy (specific label).
- **False positive risk.** Low (the specific label is uncommon in formal human writing).
- **Fix or remediation.** Remove the label; if a recap is genuinely warranted, write it as a prose summary.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER.

### A1-GROK-010: Profanity or emphasis words

- **ID.** A1-GROK-010
- **Name.** Profanity or emphasis words
- **Description.** Per `[deepseek]`'s A1-GROK-008, words like "freaking", "damn" used for emphasis, reflecting the model's edgy persona.
- **Concrete examples.**
  1. "This is freaking complicated."
  2. "The damn thing crashes every time."
  3. "What a mess. Seriously."
- **Location and register.** Casual and conversational responses.
- **Model attribution.** Grok family (high confidence). Largely absent from Claude, GPT, Gemini.
- **Time evolution.** Consistent across Grok versions.
- **Sources.** `[deepseek]`.
- **Signal strength.** HIGH (family-distinctive).
- **Base rate (per-family).** Moderate in casual responses.
- **Causal hypothesis (ranked).** Product-wrapper personality; training data and RLHF deliberately preserve emphasis-word usage.
- **Detection difficulty.** Easy.
- **False positive risk.** Low (most professional human writing avoids these).
- **Fix or remediation.** Strip if professional context; keep if conversational context aligns.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT (Grok emphasis vocabulary).

---

## A1.6 DeepSeek family

Models in scope: DeepSeek V2, V3, R1, and V4 Preview. The DeepSeek V1/V2 historical entry lives in [historical-patterns.md](historical-patterns.md). DeepSeek-R1 output has a specific stylometric property: Copyleaks classified it as OpenAI-produced 74.2 percent of the time, the strongest cross-family resemblance documented per `[perplexity]`. DeepSeek prose is stylometrically close to GPT-family prose. Patterns that identify GPT output should be applied to DeepSeek output with comparable confidence. The unique DeepSeek signals are the reasoning-trace leakage and the language-mixing patterns.

### A1-DEEPSEEK-001: `<think>` tag leakage (R1-specific)

- **ID.** A1-DEEPSEEK-001
- **Name.** `<think>` tag leakage (R1-specific)
- **Description.** DeepSeek-R1 leaks reasoning-trace tokens including literal `<think>` tags in some outputs. The leakage is the most diagnostic single fingerprint of R1. Per `[perplexity]`'s A1-DEEPSEEK-002 "Reasoning Trace Contamination (R1 Specific)," DeepSeek-R1's visible thinking traces ("Okay, let's see..." / "Wait, did I spell that right?" / "Let me check again.") can contaminate output in API contexts where the thinking delimiter is not properly stripped.
- **Concrete examples.**
  1. (Per Perplexity) "Hmm, the question here is whether to use a hash map or a balanced BST. Let me think about the complexity... Actually, the hash map is O(1) for lookup so that's clearly better."
  2. (Per Perplexity) "Okay so the user wants a recipe for tiramisu. I should include the mascarpone, the espresso, the ladyfingers..."
  3. Literal `<think>The user is asking about Y. I should remember to mention Z.</think>` tokens appearing in API output where the wrapper failed to strip them.
- **Location and register.** Any direct API output from R1 without proper delimiter handling.
- **Model attribution.** DeepSeek-R1 (unique).
- **Time evolution.** Emerged with R1 launch in early 2025; persists.
- **Sources.** `[claude-exec-2026-05-18]`, `[verified-arxiv:2501.12948]` (DeepSeek-R1 paper, Nature 2025, confirms reasoning approach; specific tag leakage is widely documented in deployments). `[cross-validated:deepseek]`, `[cross-validated:perplexity]`. Opper AI blog 2025; DeepSeek-R1 technical documentation; Vellum AI 2025.
- **Signal strength.** VERY HIGH when literal tags appear; HIGH when present per Perplexity.
- **Base rate (per-family).** LOW per Perplexity (requires API misconfiguration or deliberate exposure).
- **Causal hypothesis (ranked).** Architecture effect: R1's reinforcement learning produces explicit reasoning traces; the `<think>` delimiter must be stripped before presentation per Perplexity.
- **Detection difficulty.** Easy when present.
- **False positive risk.** NONE per Perplexity. No human writes this way in published text.
- **Fix or remediation.** Implement proper delimiter stripping. In content review, traces are a definitive DeepSeek-R1 signal.
- **Era status.** Active.
- **Zone tag.** MID-BODY-INSERT.

### A1-DEEPSEEK-002: Language-mixing under reasoning load

- **ID.** A1-DEEPSEEK-002
- **Name.** Language-mixing under reasoning load
- **Description.** DeepSeek family, especially R1, occasionally mixes Chinese and English in extended reasoning. Per arxiv 2507.15849 on bilingual reasoning (cited in Claude's exec summary; not independently verified in expansion pass), the pattern is intrinsic to DeepSeek's bilingual training corpus.
- **Concrete examples.**
  1. Mid-paragraph Chinese characters appearing inside English-language output, particularly during extended reasoning.
  2. Chinese-language reasoning tokens leaking through in chain-of-thought sequences.
  3. Brief Chinese words used where the English equivalent would naturally appear (e.g., a Chinese variant of a technical term).
- **Location and register.** Extended-reasoning outputs; long-context outputs.
- **Model attribution.** DeepSeek family (high confidence, especially R1).
- **Time evolution.** Present from V2 forward; pronounced in R1.
- **Sources.** `[claude-exec-2026-05-18]`, `[opus-expansion]`. arxiv 2507.15849 on bilingual reasoning (single-LLM-sourced citation, unverified at merge time).
- **Signal strength.** VERY HIGH when Chinese characters appear unexpectedly.
- **Base rate (per-family).** Low overall; concentrated in long-reasoning outputs.
- **Causal hypothesis (ranked).** Primary: bilingual training corpus that includes Chinese-language reasoning data. Secondary: attention-mechanism effects under reasoning load.
- **Detection difficulty.** Easy (Unicode character search).
- **False positive risk.** Very low (English-only human writers do not insert Chinese characters mid-paragraph).
- **Fix or remediation.** Strip the foreign-language tokens; re-translate to English if the meaning is needed.
- **Era status.** Active.
- **Zone tag.** MID-BODY-INSERT.

### A1-DEEPSEEK-003: Lower English-prose polish

- **ID.** A1-DEEPSEEK-003
- **Name.** Lower English-prose polish
- **Description.** DeepSeek English-prose output sometimes shows minor article-word irregularities ("the" missing, "a" used where "an" expected) that reflect non-English-primary training. Subtle but consistent.
- **Concrete examples.**
  1. "The model has efficient training pipeline." (article omission)
  2. "She is a engineer at the company." (wrong article)
  3. "These are most important factors to consider." (article omission)
- **Location and register.** Body paragraphs across registers.
- **Model attribution.** DeepSeek family (high confidence).
- **Time evolution.** Improving across versions but still present.
- **Sources.** `[opus-expansion]`, `[cross-validated:manus-ai]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Moderate; one to two instances per 1000 words is typical.
- **Causal hypothesis (ranked).** Multilingual training corpus effects; English is not the primary training language.
- **Detection difficulty.** Medium (requires careful reading).
- **False positive risk.** High (ESL human writers exhibit the same pattern; this is part of the ESL safe-harbor consideration).
- **Fix or remediation.** Standard copy-edit pass corrects these.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-DEEPSEEK-004: Mathematical confidence bias

- **ID.** A1-DEEPSEEK-004
- **Name.** Mathematical confidence bias
- **Description.** DeepSeek produces mathematical and computational claims with notable confidence, occasionally overstepping where Claude/GPT would hedge. Reflects training emphasis on math/code.
- **Concrete examples.**
  1. DeepSeek states a specific time complexity without the hedge Claude or GPT would add for edge cases.
  2. DeepSeek presents a numerical answer without uncertainty bounds where the calculation has known approximation error.
  3. DeepSeek asserts an optimization result without acknowledging assumptions.
- **Location and register.** Mathematical and computational responses.
- **Model attribution.** DeepSeek family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:manus-ai]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Moderate in math/code contexts.
- **Causal hypothesis (ranked).** Training emphasis on math/code; RLHF rewards confident mathematical claims.
- **Detection difficulty.** Hard (requires domain expertise to evaluate).
- **False positive risk.** Moderate (skilled mathematicians also assert with confidence).
- **Fix or remediation.** Add appropriate uncertainty bounds and assumption statements.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-DEEPSEEK-005: Step-numbering in reasoning

- **ID.** A1-DEEPSEEK-005
- **Name.** Step-numbering in reasoning
- **Description.** DeepSeek frequently structures reasoning with explicit "Step 1, Step 2, Step 3" numbering even in casual responses. Product of training data.
- **Concrete examples.**
  1. "Step 1: Define the problem. Step 2: Identify the constraints. Step 3: Generate candidate solutions. Step 4: Evaluate trade-offs. Step 5: Recommend the best option."
  2. "Let's work through this step by step. Step 1..."
  3. "Here is the reasoning. Step 1: ..."
- **Location and register.** Analytical and reasoning-heavy responses.
- **Model attribution.** DeepSeek family (high confidence).
- **Time evolution.** Consistent across versions; pronounced in R1.
- **Sources.** `[claude-exec-2026-05-18]`, `[opus-expansion]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Frequent in reasoning-heavy responses.
- **Causal hypothesis (ranked).** Training data emphasis on chain-of-thought reasoning with explicit step numbering.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate (skilled writers use step numbering when warranted).
- **Fix or remediation.** Use step numbering only when the steps are genuinely sequential and parallel; otherwise present as prose.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-DEEPSEEK-006: Lower English idiom density

- **ID.** A1-DEEPSEEK-006
- **Name.** Lower English idiom density
- **Description.** DeepSeek produces fewer English idioms and culturally-specific references than Anthropic/OpenAI models. Negative-marker pattern.
- **Concrete examples.**
  1. DeepSeek avoids idioms like "the elephant in the room," "moving the goalposts," "behind the eight ball."
  2. DeepSeek favors direct phrasing over culturally-specific allusion.
  3. DeepSeek's English prose has a flat-affect quality that lacks the texture of native-English-trained models.
- **Location and register.** Body paragraphs across registers.
- **Model attribution.** DeepSeek family (high confidence as a negative marker).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`.
- **Signal strength.** MEDIUM as a negative marker.
- **Base rate (per-family).** Substantially lower idiom density than Anthropic/OpenAI models.
- **Causal hypothesis (ranked).** Bilingual training corpus; English is not the primary training language.
- **Detection difficulty.** Hard (requires comparing against expected idiom density).
- **False positive risk.** High (ESL human writers exhibit the same pattern).
- **Fix or remediation.** N/A as a content-quality concern; relevant for stylometric attribution.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-DEEPSEEK-007: Heavy use of LaTeX in non-technical responses

- **ID.** A1-DEEPSEEK-007
- **Name.** Heavy use of LaTeX in non-technical responses
- **Description.** Per `[deepseek]`'s A1-DEEPSEEK-003, R1 in particular formats even simple numbers with LaTeX (e.g., $5$), a quirk absent in other families.
- **Concrete examples.**
  1. "The result is $5$ percent improvement over baseline."
  2. "We saw $3$ outliers in the dataset."
  3. "The team grew from $4$ to $7$ engineers over the quarter."
- **Location and register.** Body paragraphs in all responses where R1 is the source.
- **Model attribution.** DeepSeek-R1 (high confidence, family-distinctive).
- **Time evolution.** Emerged with R1; persists.
- **Sources.** `[deepseek]`.
- **Signal strength.** HIGH (family-distinctive formatting choice).
- **Base rate (per-family).** Frequent in R1 outputs.
- **Causal hypothesis (ranked).** Training data emphasis on LaTeX-formatted math corpora; tokenizer effects.
- **Detection difficulty.** Easy (specific format).
- **False positive risk.** Very low (LaTeX in non-technical prose is uncommon in human writing).
- **Fix or remediation.** Strip LaTeX wrappers from non-mathematical numbers.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-DEEPSEEK-008: The rigid pivot

- **ID.** A1-DEEPSEEK-008
- **Name.** The rigid pivot
- **Description.** Per `[gemini]`'s A1-DEEPSEEK-001, DeepSeek models rely on highly traditional, heavy-handed transitional phrases to shift arguments, rarely using fluid narrative pivots.
- **Concrete examples.**
  1. "On the other hand, the implementation of the secondary module solves the memory leak."
  2. "In summary, the primary algorithmic contributions are as follows:"
  3. "Furthermore, it is not needed to point out that the compiler will fail."
- **Location and register.** Paragraph beginnings, concluding sections, and documentation summaries.
- **Model attribution.** DeepSeek V3 (High), DeepSeek R1 (High), DeepSeek V4 Pro (Medium) per `[gemini]`.
- **Time evolution.** Persistent across the V3 and V4 architectures, though slightly smoothed in the V4 Pro iteration to sound more natural.
- **Sources.** `[gemini]`. 65 percent confidence per Gemini.
- **Signal strength.** MEDIUM (65 percent confidence per Gemini).
- **Base rate (per-family).** Appears in 62 percent of multi-paragraph analytical responses per `[gemini]`.
- **Causal hypothesis (ranked).** Training data skew favoring formal academic registers and translated non-native datasets.
- **Detection difficulty.** Easy.
- **False positive risk.** Medium (common in academic human writing).
- **Fix or remediation.** Rewrite transitions to flow logically from the previous sentence's object rather than relying on prepositional signposts.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-DEEPSEEK-009: OpenAI stylometric resemblance

- **ID.** A1-DEEPSEEK-009
- **Name.** OpenAI stylometric resemblance
- **Description.** Per `[perplexity]`'s A1-DEEPSEEK-001, DeepSeek-R1 output was tested by the Copyleaks ensemble and classified as OpenAI-produced 74.2 percent of the time, the strongest cross-family resemblance documented in the study. DeepSeek prose is stylometrically close to GPT-family prose. Patterns that identify GPT output (A1-GPT-001 through A1-GPT-020 above) should be applied to DeepSeek output with comparable confidence.
- **Concrete examples.** See A1-GPT examples. DeepSeek output produces the saturated vocabulary cluster, the sycophantic opener pattern, the section-ending summary, the "It's not just X, it's Y" construction, and the numbered-list scaffolding at rates comparable to GPT-4o.
- **Location and register.** All registers.
- **Model attribution.** DeepSeek V3, R1.
- **Time evolution.** Present across versions; reflects training data and fine-tuning choices.
- **Sources.** Copyleaks stylometric ensemble study 2025 per Perplexity. `[verified-arxiv:2503.01659]` `[correction]` (the original Claude exec summary characterized this paper as a Copyleaks publication, which is not accurate; the paper reports 0.9988 precision for cross-family detection but is not Copyleaks-authored).
- **Signal strength.** As per GPT patterns above.
- **Base rate (per-family).** Comparable to GPT.
- **Causal hypothesis (ranked).** DeepSeek's training data and fine-tuning process produce output distributions measurably similar to OpenAI's. The Copyleaks study raises questions about training data overlap or model distillation.
- **Detection difficulty.** Medium (cannot distinguish from GPT without DeepSeek-specific markers).
- **False positive risk.** As per GPT patterns.
- **Fix or remediation.** As per GPT patterns.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-DEEPSEEK-010: "Based on the provided information,"

- **ID.** A1-DEEPSEEK-010
- **Name.** "Based on the provided information,"
- **Description.** Per `[deepseek]`'s A1-DEEPSEEK-001, instruction-following marker from fine-tuning; the phrase often starts answers to document-grounded tasks.
- **Concrete examples.**
  1. "Based on the provided information, the company's revenue grew by 25 percent year-over-year."
  2. "Based on the provided document, the migration strategy is to deploy in three phases."
  3. "Based on the provided context, the answer is X."
- **Location and register.** Response openers in document-grounded and RAG-augmented contexts.
- **Model attribution.** DeepSeek family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Very high in document-grounded responses.
- **Causal hypothesis (ranked).** Fine-tuning data choices that train explicit grounding markers.
- **Detection difficulty.** Easy.
- **False positive risk.** Low (the specific phrasing is uncommon in skilled human writing, which would name the specific source).
- **Fix or remediation.** Anchor to the specific source. "Based on the provided information" becomes "According to the May 2025 financial filing..." when the source can be named.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER.

---

## A1.7 Mistral / Mixtral family

Models in scope: Mistral Large 1 and 2, Mixtral 8x7B, and current Mistral frontier (Le Chat, Codestral, and follow-ons). Mistral 7B, Mixtral 8x7B early, and Mistral Large 1 historical entries live in [historical-patterns.md](historical-patterns.md). Mistral output was classified by Copyleaks as 26 percent OpenAI and 8.8 percent Llama with 65 percent "no-agreement," indicating a partially distinct stylistic identity with some overlap with both families per `[perplexity]`. The Manus AI catalog characterizes Mistral as "Professional, pragmatic, and solution-oriented." The independent similarity work cited by ChatGPT finds several Mistral models clustering very tightly, making the family useful for fingerprint cataloguing even though it is less stylistically distinct than Claude or GPT.

### A1-MISTRAL-001: French-influence syntax

- **ID.** A1-MISTRAL-001
- **Name.** French-influence syntax
- **Description.** Mistral family occasionally produces English prose with syntax patterns subtly influenced by French (e.g., adjective placement, relative-clause structure). Reflects training corpus. Cross-validates with `[perplexity]`'s "A1-MISTRAL-005: Multilingual phrase bleedthrough" (occasionally produces French cognates or European-English constructions in English output) and `[deepseek]`'s "A1-MISTRAL-004: Occasional French Code-Switch" ("Bonjour" or French punctuation spacing).
- **Concrete examples.**
  1. "The solution evident and reliable handles the workload." (adjective placement reflecting French syntax)
  2. "The team in charge of the migration the strategy outlined here." (relative-clause structure)
  3. French punctuation spacing leakage (e.g., space before colon or semicolon, French convention).
- **Location and register.** Body paragraphs in technical and analytical responses.
- **Model attribution.** Mistral family (high confidence as French-influence marker).
- **Time evolution.** Consistent across versions; reflects training corpus.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`.
- **Signal strength.** LOW standalone (HIGH when French code-switch tokens appear, but base rate of those is very low).
- **Base rate (per-family).** Low overall; concentrated in specific contexts where the bilingual training surfaces.
- **Causal hypothesis (ranked).** Multilingual training corpus effects; Mistral's French-corpus emphasis.
- **Detection difficulty.** Medium (requires careful reading for subtle syntax differences).
- **False positive risk.** Moderate (French-influenced ESL human writers exhibit similar patterns).
- **Fix or remediation.** Standard copy-edit pass; reorder words to natural English syntax.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-MISTRAL-002: More direct refusal style

- **ID.** A1-MISTRAL-002
- **Name.** More direct refusal style
- **Description.** Mistral refusals tend to be more direct ("I cannot help with that") than Claude/GPT's softer hedges.
- **Concrete examples.**
  1. "I cannot help with that request."
  2. "I am not able to provide that information."
  3. "That falls outside the scope of what I can answer."
- **Location and register.** Refusal turns.
- **Model attribution.** Mistral family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`.
- **Signal strength.** MEDIUM as a family marker.
- **Base rate (per-family).** High in refusal turns.
- **Causal hypothesis (ranked).** RLHF training favoring direct refusals over softer hedges.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate (skilled writers also refuse directly).
- **Fix or remediation.** N/A as a stylistic baseline.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER (refusal turns are typically the entire response).

### A1-MISTRAL-003: Lower saturated-vocabulary density

- **ID.** A1-MISTRAL-003
- **Name.** Lower saturated-vocabulary density
- **Description.** Mistral produces fewer "delve"-cluster focal words than GPT. Negative-marker pattern.
- **Concrete examples.**
  1. Mistral uses "examine" or "study" where GPT would use "delve."
  2. Mistral uses "use" or "apply" where GPT would use "leverage."
  3. Mistral uses "complex" or "complicated" where GPT would use "intricate."
- **Location and register.** Body paragraphs across registers.
- **Model attribution.** Mistral family (high confidence as a negative marker).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`.
- **Signal strength.** MEDIUM as a negative marker.
- **Base rate (per-family).** Substantially lower saturated-vocabulary density than GPT or Claude.
- **Causal hypothesis (ranked).** Training corpus and RLHF that does not emphasize academic-register focal vocabulary at GPT rates.
- **Detection difficulty.** Medium (requires comparison against expected density).
- **False positive risk.** Moderate (skilled writers also avoid focal vocabulary).
- **Fix or remediation.** N/A as a stylistic baseline.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-MISTRAL-004: Different default formatting

- **ID.** A1-MISTRAL-004
- **Name.** Different default formatting
- **Description.** Mistral default formatting (bullet density, paragraph length) differs from Claude/GPT defaults, providing a structural fingerprint. Cross-validates with `[perplexity]`'s "A1-MISTRAL-003: Reduced markdown decoration" (Mistral applies less bold, bullet, and header decoration than GPT-4o).
- **Concrete examples.**
  1. Mistral default responses contain fewer bullet points than GPT-4o default responses to the same prompt.
  2. Mistral paragraphs tend to be longer than Claude's 3-to-5-sentence default.
  3. Mistral uses less bold formatting than GPT-4o's "comprehensive structure header cascade."
- **Location and register.** Body of responses across registers.
- **Model attribution.** Mistral family (high confidence as a negative marker for heavy formatting).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** LOW standalone.
- **Base rate (per-family).** High distinctiveness in formatting choices.
- **Causal hypothesis (ranked).** Training corpus and RLHF choices that under-prioritize structured formatting.
- **Detection difficulty.** Medium (requires aggregate analysis).
- **False positive risk.** High (many human writers also use minimal formatting).
- **Fix or remediation.** N/A as a stylistic baseline.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-MISTRAL-005: Open-source-aware register

- **ID.** A1-MISTRAL-005
- **Name.** Open-source-aware register
- **Description.** Mistral, being European-open-source-aligned, sometimes references open-source culture and EU regulatory framings more naturally than competitors. Cross-validates with `[perplexity]`'s "A1-MISTRAL-002: European formal register" (Mistral's training emphasis on EU regulatory compliance content produces slightly formal phrasing in English).
- **Concrete examples.**
  1. Mistral references GDPR or the EU AI Act more naturally than Anthropic or OpenAI models.
  2. Mistral references specific open-source licenses (Apache, MIT, GPL) with more precision than competitors.
  3. Mistral references European data-protection norms when discussing data architecture.
- **Location and register.** Regulatory and open-source-adjacent topics.
- **Model attribution.** Mistral family (high confidence in regulatory and open-source contexts).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** LOW (genre-specific).
- **Base rate (per-family).** High in regulatory and open-source contexts.
- **Causal hypothesis (ranked).** Training corpus emphasis on EU regulatory content and open-source documentation.
- **Detection difficulty.** Medium.
- **False positive risk.** High (EU-based human writers exhibit the same pattern).
- **Fix or remediation.** N/A as a stylistic baseline.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-MISTRAL-006: Lower agent-reflex density

- **ID.** A1-MISTRAL-006
- **Name.** Lower agent-reflex density
- **Description.** Mistral produces fewer "You're absolutely right" or "Great question!" openers than Claude/GPT. Cross-validates with `[perplexity]`'s "A1-MISTRAL-007: Lower sycophancy rate" (Mistral does not produce "Certainly!" or "I'd be happy to" at GPT rates) and `[deepseek]`'s A1-MISTRAL-002 ("I can provide information about...") as the more characteristic phrasing.
- **Concrete examples.**
  1. Mistral typically opens with "I can provide..." rather than "Certainly! Here is..."
  2. Mistral does not produce "Great question!" at GPT rates.
  3. Mistral does not produce "You're absolutely right" reflex at Claude rates.
- **Location and register.** Response openers.
- **Model attribution.** Mistral family (high confidence as a negative marker).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`, `[cross-validated:deepseek]`.
- **Signal strength.** MEDIUM as a negative marker.
- **Base rate (per-family).** Substantially lower agent-reflex density than Claude or GPT.
- **Causal hypothesis (ranked).** RLHF training that under-prioritizes warm openers compared to Anthropic/OpenAI.
- **Detection difficulty.** Easy (compare against expected agent-reflex density).
- **False positive risk.** Moderate (many human writers also default to direct responses).
- **Fix or remediation.** N/A as a stylistic baseline.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER (negative marker for opener pleasantries).

### A1-MISTRAL-007: Concise default

- **ID.** A1-MISTRAL-007
- **Name.** Concise default
- **Description.** Per `[perplexity]`'s A1-MISTRAL-001, Mistral produces shorter responses than GPT or Gemini; this can read as terse rather than clear. Cross-validates with `[deepseek]`'s "A1-MISTRAL-001: Concise, Formal Yet Warm Tone" (Mistral models produce efficient prose with less fluff but a slightly stiff polite register).
- **Concrete examples.**
  1. Mistral response to "Explain the trade-offs between Postgres and MongoDB" runs 200 words; equivalent GPT-4o response runs 600 words.
  2. Mistral analytical responses pack claim density without padding.
  3. Mistral does not produce the warm-up paragraph that Claude or GPT might add before getting to the substance.
- **Location and register.** Body of responses across registers.
- **Model attribution.** Mistral family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[perplexity]`, `[deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** High distinctiveness in response length.
- **Causal hypothesis (ranked).** Training and RLHF that prioritizes conciseness over comprehensiveness.
- **Detection difficulty.** Easy (aggregate response-length analysis).
- **False positive risk.** Moderate (skilled writers also default to conciseness).
- **Fix or remediation.** N/A as a stylistic baseline.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-MISTRAL-008: Direct completion pattern

- **ID.** A1-MISTRAL-008
- **Name.** Direct completion pattern
- **Description.** Per `[perplexity]`'s A1-MISTRAL-004, Mistral finishes tasks without editorial commentary; no "I hope this helps" closer.
- **Concrete examples.**
  1. Mistral ends a response with the final substantive claim and stops.
  2. Mistral does not produce the GPT-style "Feel free to ask if you have more questions!" closer.
  3. Mistral does not produce the Claude-style "Is there anything else I can help you with?" concierge closer.
- **Location and register.** Response closers across registers.
- **Model attribution.** Mistral family (high confidence as a negative marker for closer pleasantries).
- **Time evolution.** Consistent across versions.
- **Sources.** `[perplexity]`.
- **Signal strength.** MEDIUM as a negative marker.
- **Base rate (per-family).** Very high in unedited Mistral output (closer pleasantries are mostly absent).
- **Causal hypothesis (ranked).** RLHF training that under-prioritizes closer pleasantries compared to Anthropic/OpenAI.
- **Detection difficulty.** Easy (compare against expected closer-pleasantry density).
- **False positive risk.** Moderate (skilled writers also default to direct completion).
- **Fix or remediation.** N/A as a stylistic baseline.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER (negative marker for closer pleasantries).

### A1-MISTRAL-009: Technical register dominance

- **ID.** A1-MISTRAL-009
- **Name.** Technical register dominance
- **Description.** Per `[perplexity]`'s A1-MISTRAL-006, Mistral defaults to technical phrasing even in non-technical contexts.
- **Concrete examples.**
  1. (For a casual prompt) Mistral uses "execute the procedure" where Claude or GPT might use "do it."
  2. (For a layperson question) Mistral uses "validate the input parameters" where Claude or GPT might use "check that the inputs are correct."
  3. (For an everyday topic) Mistral uses "implement the strategy" where Claude or GPT might use "try the approach."
- **Location and register.** Body of responses across registers.
- **Model attribution.** Mistral family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[perplexity]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** High in unedited Mistral output.
- **Causal hypothesis (ranked).** Training corpus emphasis on technical documentation.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate (technical writers also default to technical phrasing).
- **Fix or remediation.** Re-register for the audience. "Execute the procedure" becomes "do it" when the audience is casual.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

## A1.8 Qwen / Alibaba family

Models in scope: Qwen 2.5 and Qwen 3 series across Chat, Coder, and reasoning variants. The Qwen 1 and Qwen 2 historical entries live in [historical-patterns.md](historical-patterns.md). Qwen patterns are documented primarily from r/LocalLLaMA practitioner observation. No peer-reviewed stylometric English-language study of Qwen output was found as of May 2026 per `[perplexity]`. The family's English output reflects Chinese-language primary training, producing measurable surface differences from Western-developed models. English-language editorial audits would rarely encounter Qwen except in self-hosted or open-source-developer deployments.

### A1-QWEN-001: CJK punctuation slips (Unicode-detectable)

- **ID.** A1-QWEN-001
- **Name.** CJK punctuation slips (Unicode-detectable)
- **Description.** Qwen family occasionally produces CJK-specific punctuation (full-width comma, period, quotation marks) in English text. The slip is Unicode-detectable. Cross-validates with `[perplexity]`'s "A1-QWEN-001: Chinese-English code-switching artifact" (Qwen occasionally produces Chinese characters in English contexts, particularly in parenthetical clarifications).
- **Concrete examples.**
  1. Full-width comma (U+FF0C) appearing in English text: "The system runs efficiently, and the throughput is consistent."
  2. Full-width period (U+3002) appearing at the end of an English sentence.
  3. CJK quotation marks (U+300C, U+300D or U+201C, U+201D variants) appearing in English text.
  4. Occasional Chinese characters mid-paragraph in parenthetical clarifications.
- **Location and register.** All registers.
- **Model attribution.** Qwen family (very high confidence). Largely absent from Western-developed models.
- **Time evolution.** Improving across versions but still present.
- **Sources.** `[claude-exec-2026-05-18]` (cited as specifically diagnostic). `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** VERY HIGH when CJK characters appear unexpectedly.
- **Base rate (per-family).** Low overall; concentrated in specific contexts where the bilingual training surfaces.
- **Causal hypothesis (ranked).** Primary: bilingual training corpus. Secondary: tokenizer effects on punctuation tokens.
- **Detection difficulty.** Easy (Unicode character search).
- **False positive risk.** Very low (English-only human writers do not use CJK punctuation).
- **Fix or remediation.** Strip CJK punctuation and replace with ASCII equivalents.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-QWEN-002: Chinese cultural references and idiom translations

- **ID.** A1-QWEN-002
- **Name.** Chinese cultural references and idiom translations
- **Description.** Qwen occasionally references Chinese cultural concepts or translates Chinese idioms literally, reflecting primary training. Cross-validates with `[perplexity]`'s "A1-QWEN-005: Topic-sentence-last paragraph structure" (some Qwen responses build to the main point rather than leading with it, reflecting Chinese rhetorical conventions).
- **Concrete examples.**
  1. Direct translations of Chinese idioms that read oddly in English (e.g., "to draw a snake and add feet" rather than the equivalent English idiom "to gild the lily").
  2. References to specific Chinese cultural concepts (e.g., guanxi, mianzi) used without translation context.
  3. Paragraph structure that builds to the topic sentence at the end rather than leading with it, reflecting Chinese rhetorical conventions.
- **Location and register.** Analytical and explanatory responses.
- **Model attribution.** Qwen family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** Moderate; specific to topics where Chinese cultural references are relevant.
- **Causal hypothesis (ranked).** Primary: training corpus emphasis on Chinese-language content. Secondary: RLHF training data that includes translated Chinese idioms.
- **Detection difficulty.** Medium (requires recognition of the underlying Chinese idiom).
- **False positive risk.** Moderate (Chinese-speaking ESL human writers exhibit similar patterns).
- **Fix or remediation.** Replace literal translations with the equivalent English idiom or with the underlying claim stated plainly.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-QWEN-003: Heavier hedging on China-political topics

- **ID.** A1-QWEN-003
- **Name.** Heavier hedging on China-political topics
- **Description.** Qwen exhibits notably heavier hedging or refusal on topics related to Chinese politics, compared to Anthropic/OpenAI models. Alignment-trained. Cross-validates with `[perplexity]`'s "A1-QWEN-007: Conservative content filtering artifacts" (Qwen has broader content restrictions that produce visible topic avoidance on politically sensitive queries).
- **Concrete examples.**
  1. Qwen produces vague or non-committal responses to questions about Chinese government policies that frontier Western models would answer more directly.
  2. Qwen avoids specific names or events that frontier Western models would mention.
  3. Qwen produces refusal-shaped closes on topics adjacent to Chinese political sensitivity.
- **Location and register.** China-political topics.
- **Model attribution.** Qwen family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** HIGH for topic-specific identification.
- **Base rate (per-family).** Very high on China-political topics.
- **Causal hypothesis (ranked).** Alignment and safety tuning aligned with Chinese regulatory requirements.
- **Detection difficulty.** Easy (specific topic + visible hedging pattern).
- **False positive risk.** Low.
- **Fix or remediation.** N/A as a content-quality concern; relevant for content auditing and source attribution.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-QWEN-004: Math-step formatting differences

- **ID.** A1-QWEN-004
- **Name.** Math-step formatting differences
- **Description.** Qwen math output uses formatting conventions (alignment, step labeling) closer to Chinese-math-education conventions than Western conventions. Cross-validates with `[perplexity]`'s "A1-QWEN-006: Number formatting differences" (Qwen may use Chinese number formatting conventions in some contexts).
- **Concrete examples.**
  1. Math steps labeled with Chinese-education-style numbering (e.g., specific brackets, alignment).
  2. Number formatting that uses Chinese conventions (e.g., specific decimal separators or grouping).
  3. Mathematical proof structure that follows Chinese-math-education conventions.
- **Location and register.** Mathematical and quantitative responses.
- **Model attribution.** Qwen family (high confidence in math contexts).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** LOW (genre-specific).
- **Base rate (per-family).** Moderate in math contexts.
- **Causal hypothesis (ranked).** Training corpus emphasis on Chinese-math-education content.
- **Detection difficulty.** Medium (requires familiarity with both Chinese and Western math conventions).
- **False positive risk.** High (math educators from China-trained backgrounds exhibit the same conventions).
- **Fix or remediation.** Reformat to Western conventions for English-speaking audiences.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-QWEN-005: Specific phrasings translated from Chinese

- **ID.** A1-QWEN-005
- **Name.** Specific phrasings translated from Chinese
- **Description.** Qwen English output sometimes contains phrasings that read as direct translations from Chinese idioms or structures. Cross-validates with `[perplexity]`'s "A1-QWEN-002: Formal Chinese academic register mapped to English" (Qwen in English tends toward elevated formal constructions reflecting Chinese academic writing conventions).
- **Concrete examples.**
  1. "It can be seen that..." (direct translation of a Chinese academic construction)
  2. "From the above, we can conclude that..." (Chinese-academic-register translation)
  3. "There are several considerations worth noting in this regard." (literal translation pattern)
- **Location and register.** Academic and analytical writing.
- **Model attribution.** Qwen family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** High in academic and analytical writing.
- **Causal hypothesis (ranked).** Training corpus emphasis on Chinese academic writing translated to English.
- **Detection difficulty.** Medium (requires recognition of the underlying Chinese construction).
- **False positive risk.** High (Chinese-speaking ESL human writers exhibit the same patterns).
- **Fix or remediation.** Replace with natural English constructions. "It can be seen that X" becomes "X is evident" or "X is the case."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-QWEN-006: Different agentic-reflex patterns

- **ID.** A1-QWEN-006
- **Name.** Different agentic-reflex patterns
- **Description.** Qwen's agentic-reflex patterns differ from Claude's "You're absolutely right" or GPT's "Great question". Specific to Qwen training. Cross-validates with `[perplexity]`'s "A1-QWEN-004: Explicit role assertion" ("As an AI assistant, I will..." opener; more common in Qwen than in Western-developed models).
- **Concrete examples.**
  1. "As an AI assistant, I will help you with..."
  2. "Below is a detailed explanation:"
  3. "I will now address your question."
- **Location and register.** Response openers.
- **Model attribution.** Qwen family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** MEDIUM (family-distinctive openers).
- **Base rate (per-family).** High in unedited Qwen output.
- **Causal hypothesis (ranked).** RLHF training that explicitly produces these compliance markers, distinct from Western RLHF approaches.
- **Detection difficulty.** Easy.
- **False positive risk.** Low (the specific phrasing is uncommon in skilled English-native writing).
- **Fix or remediation.** Strip the opener; start with the substantive response.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER.

### A1-QWEN-007: Lower idiomatic-English density

- **ID.** A1-QWEN-007
- **Name.** Lower idiomatic-English density
- **Description.** Like DeepSeek, Qwen produces fewer English idioms than Anthropic/OpenAI models. Subtle negative marker. Cross-validates with `[perplexity]`'s "A1-QWEN-003: Honorific register markers" (Qwen uses "please" and "kindly" more frequently than English-native models).
- **Concrete examples.**
  1. Qwen avoids idioms like "putting all your eggs in one basket" or "looking under every rock."
  2. Qwen favors direct phrasing over culturally-specific allusion.
  3. Qwen uses "please" and "kindly" at higher rates than Western-developed models, reflecting Chinese honorific conventions.
- **Location and register.** Body paragraphs across registers.
- **Model attribution.** Qwen family (high confidence as a negative marker for English idioms).
- **Time evolution.** Consistent across versions.
- **Sources.** `[opus-expansion]`, `[cross-validated:perplexity]`.
- **Signal strength.** LOW (subtle negative marker).
- **Base rate (per-family).** Substantially lower idiom density than Anthropic/OpenAI.
- **Causal hypothesis (ranked).** Bilingual training corpus; English is not the primary training language.
- **Detection difficulty.** Hard (requires comparing against expected idiom density).
- **False positive risk.** High (ESL human writers exhibit the same pattern; ESL safe-harbor applies).
- **Fix or remediation.** N/A as a content-quality concern; relevant for stylometric attribution.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-QWEN-008: "Below is a detailed explanation:"

- **ID.** A1-QWEN-008
- **Name.** "Below is a detailed explanation:" opener
- **Description.** Per `[deepseek]`'s A1-QWEN-001, a consistent response opener.
- **Concrete examples.**
  1. "Below is a detailed explanation: ..."
  2. "Below is a step-by-step breakdown: ..."
  3. "Below is a comprehensive overview: ..."
- **Location and register.** Response openers.
- **Model attribution.** Qwen family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[deepseek]`.
- **Signal strength.** MEDIUM (family-distinctive opener).
- **Base rate (per-family).** Frequent in long-form explanatory responses.
- **Causal hypothesis (ranked).** RLHF training data that includes this specific opener pattern in instruction-tuning examples.
- **Detection difficulty.** Easy.
- **False positive risk.** Low (the specific phrasing is uncommon in skilled English-native writing).
- **Fix or remediation.** Strip the opener; start with the substantive content.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER.

### A1-QWEN-009: Overuse of "Moreover," and "In addition,"

- **ID.** A1-QWEN-009
- **Name.** Overuse of "Moreover," and "In addition,"
- **Description.** Per `[deepseek]`'s A1-QWEN-002, additive transitions saturate Qwen output. Maps to v3.1.0 criterion 6 (Overuse of Transition Words).
- **Concrete examples.**
  1. "Moreover, the system handles peak load efficiently. In addition, the latency remains low."
  2. "In addition to the cost savings, the migration also improves reliability. Moreover, the team's productivity has increased."
  3. "Moreover, we can leverage existing infrastructure. In addition, the deployment timeline is favorable."
- **Location and register.** Analytical and argumentative prose.
- **Model attribution.** Qwen family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** High in unedited Qwen analytical output.
- **Causal hypothesis (ranked).** Training data emphasis on formal academic register where additive transitions are conventionally used.
- **Detection difficulty.** Easy.
- **False positive risk.** Moderate (academic writers also use these transitions legitimately).
- **Fix or remediation.** Vary transitions; embed additive points within the same sentence where possible.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

### A1-QWEN-010: Formal, almost textbook tone

- **ID.** A1-QWEN-010
- **Name.** Formal, almost textbook tone
- **Description.** Per `[deepseek]`'s A1-QWEN-004, Qwen's English output reads like a translated textbook, with stilted phrasing.
- **Concrete examples.**
  1. "It is important to understand that the underlying mechanism operates through a series of carefully orchestrated steps."
  2. "The implementation of this strategy requires careful consideration of multiple interrelated factors."
  3. "One must take into account the various dimensions of the problem before proceeding with the proposed solution."
- **Location and register.** Body paragraphs across registers.
- **Model attribution.** Qwen family (high confidence).
- **Time evolution.** Consistent across versions.
- **Sources.** `[deepseek]`.
- **Signal strength.** MEDIUM.
- **Base rate (per-family).** High in unedited Qwen output.
- **Causal hypothesis (ranked).** Training corpus emphasis on translated textbook content.
- **Detection difficulty.** Medium (requires comparison against expected register).
- **False positive risk.** High (translated textbook writers exhibit the same pattern; ESL safe-harbor applies).
- **Fix or remediation.** Simplify to natural conversational or analytical register.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

## Summary and Cross-References

This file catalogs **eighty-seven Active-era patterns** across eight model families:

- A1.1 Anthropic Claude: 28 Active patterns (A1-CLAUDE-001 through A1-CLAUDE-028, including DeepSeek, Perplexity, and Gemini contributions; A1-CLAUDE-028 is Declining).
- A1.2 OpenAI GPT: 18 Active patterns (A1-GPT-001 through A1-GPT-020, excluding A1-GPT-006 and A1-GPT-007 which are Historical; A1-GPT-018 is Declining).
- A1.3 Google Gemini: 13 Active patterns (A1-GEMINI-001 through A1-GEMINI-013).
- A1.4 Meta Llama: 10 Active patterns (A1-LLAMA-001 through A1-LLAMA-010).
- A1.5 xAI Grok: 10 Active patterns (A1-GROK-001 through A1-GROK-010).
- A1.6 DeepSeek: 10 Active patterns (A1-DEEPSEEK-001 through A1-DEEPSEEK-010).
- A1.7 Mistral / Mixtral: 9 Active patterns (A1-MISTRAL-001 through A1-MISTRAL-009).
- A1.8 Qwen / Alibaba: 10 Active patterns (A1-QWEN-001 through A1-QWEN-010).

Total Active-era patterns: 108 across the eight families.

Historical and Deprecated patterns from older versions of each family live in [historical-patterns.md](historical-patterns.md). Cross-references between Active patterns in this file and the historical lineage in that file are preserved at the relevant entries.

### Related references files

- [detailed-criteria.md](detailed-criteria.md): full per-criterion detail for the 42 v3.1.0 criteria, refreshed with v4.0 era status and zone tags. Cross-references between A1 family patterns and the underlying criteria are inline at each pattern entry above.
- [substance-and-depth.md](substance-and-depth.md): full A2 sub-pattern detail (deletion test, specificity test, load-bearing claim count, novelty signal, insight-to-word ratio, any-company test, hedging-as-substance-evasion, survey-without-claim, generic insight, both-sides-without-position, pseudo-profundity, conclusion-shaped paragraphs that do not conclude, frictionless-transition padding, and additional sub-patterns from cross-LLM contributions).
- [combined-signal-fingerprints.md](combined-signal-fingerprints.md): full B2 table of 86 combined-signal fingerprints (which combinations of A1 patterns, when co-occurring, produce the strongest detection signals).
- [calibration-tables.md](calibration-tables.md): full B3 per-family per-criterion calibration with the BR-artifact-body vs. BR-full-response split, the ESL safe-harbor, and zone-conditional base rates.
- [historical-patterns.md](historical-patterns.md): all Historical and Deprecated patterns retained per the compounding-archive principle.
- [bibliography.md](bibliography.md): consolidated bibliography from all unified buckets with verification status.

### Detection mode selection (zone-conditional)

Per the GATE 2 design considerations:

- In **artifact mode** (default for editorial review of submitted content), apply only `BODY-PERSISTENT`, `HYBRID`, and `MID-BODY-INSERT` patterns. Skip all `WRAPPER-OPENER` and `WRAPPER-CLOSER` patterns. False-positive rate stays low when only the artifact body is being audited.
- In **full-response mode** (for forensic chat-log analysis), apply all patterns including wrapper-only.

The skill's confidence-based evaluation process selects mode upfront by asking the user: "Are you auditing just the produced content, or the full LLM response including conversational framing?" The mode is the operative input to which patterns the detector applies.

### Em-dash audit

This file uses no em-dashes (U+2014). Commas, parentheses, colons, and sentence breaks substitute throughout. The constraint is part of the subject matter: criterion 11 and criterion 42 of v3.1.0 flag em-dash density as a high-signal AI marker, so a reference document for the upgrade cannot itself produce the pattern it is cataloguing.












