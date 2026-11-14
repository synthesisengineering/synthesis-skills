# Detailed Criteria Reference (v4.0), part 4 of 5

Part 4 of the file split from [detailed-criteria.md](detailed-criteria.md), which keeps the opening sections and lists every part. The text below is unchanged.

Contents:
- Section A3-BT: Behavioral and Tonal (A3-BT-001 to A3-BT-014, 13 entries)

## Section A3-BT: Behavioral and Tonal

### A3-BT-001: Saturated AI Vocabulary

- **Description.** Clustering of words that appear at disproportionately high frequency in unedited AI output. Any single occurrence is unremarkable; the signal is clustering. Three or more from the inventory in a single piece, or repeated use of the same word across sections, suggests unrevised AI output. Per `[claude-exec-2026-05-18]`'s PROMOTE: Kobak Z above 3.5 across 103 of 135 candidate focal words in 2024 PubMed. Per `[chatgpt]`'s REVISE: keep the idea, but refresh the lexicon by family and genre.

  **Family-specific vocabulary fingerprints (v4.0 refresh).**

  Claude family (per `[perplexity]`'s A1-CLAUDE-020 and `[claude-exec-2026-05-18]`):
  - delve, tapestry, testament, nuanced, comprehensive, foster, underscore, holistic, intricate, paradigm
  - elevated synonyms: "examine" replaced with "delve"; "complicated" with "nuanced"; "complex" with "multifaceted"; "important" with "pivotal"; "use" with "leverage"

  GPT family (per `[claude-exec-2026-05-18]`'s A1-GPT-001):
  - delve, tapestry, robust, foster, beacon, catalyst, synergy, pivotal, overarching, multifaceted, landscape (abstract), leverage (verb), streamline, spearhead, underscore, harness
  - the Kobak focal-word cluster derived from 2024 PubMed analysis

  Gemini family:
  - significant, impactful, comprehensive, dynamic, versatile, robust, optimized, seamless
  - more academic-register clustering per A1-GEMINI-010

  Llama family (lower density):
  - lower distinctiveness ratios per `[gemini]`; the family produces less of this vocabulary

  Industry-specific clusters (new in v4.0 per `[chatgpt]`'s REVISE):
  - AI: "transformative," "AI-powered," "AI-native," "responsible AI"
  - Healthcare: "holistic," "evidence-based," "patient-centered," "wellness"
  - Education: "transformative learning," "engaging," "personalized"

- **Concrete examples.**
  1. "Let's delve into the implications of this policy shift for small businesses."
  2. "The situation is more nuanced than it may first appear."
  3. "We need to leverage our existing infrastructure to accelerate deployment."
  4. (Per `[claude-exec-2026-05-18]`) "A robust and holistic framework that empowers stakeholders to navigate the multifaceted landscape."
  5. (Per `[opus-expansion]`) "The pivotal moment underscored the importance of fostering a comprehensive approach."
- **Location and register.** Body paragraphs throughout. Densest in professional, business, academic, and AI-thought-leadership prose.
- **Model attribution.** All families with different vocabulary peaks per the family-specific lists above.
- **Time evolution.** Vocabulary inventory has evolved with each model generation. The "delve" pattern in particular is widely cited; "delve" frequency in 2024 biomedical abstracts grew sharply per Kobak et al. 2024.
- **Sources.** v3.1.0 criterion 33; Kobak et al. 2024 (arxiv 2406.07016); Juzek and Ward COLING 2025 (attribution of "delve" to RLHF specifically, single-LLM-sourced and not independently verified); Matsui PME 2025; BlogPros 2026; Originality.ai 2025.
- **Signal strength.** HIGH (promoted from MED) for cluster of 3 or more in 500 words. MEDIUM standalone for single occurrence.
- **Base rate.** HIGH in unedited AI output. Per Kobak: Z above 3.5 for 103 of 135 candidate focal words in 2024 PubMed.
- **Causal hypothesis (ranked).** Primary: training data skew toward academic register where these words cluster. Secondary: RLHF reward modeling for "professionalism" that correlates with elevated register. Tertiary: tokenizer effects (some of these words are single tokens and cheap to generate).
- **Detection difficulty.** Easy with grep.
- **False positive risk.** Low for cluster; individual words are common in edited professional prose.
- **Fix or remediation.** Replace with plain alternatives. "Delve into the nuances" becomes "examine the specifics." "A robust and holistic framework" becomes a description of what makes the framework strong and what it covers.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-BT-002: Exhausted Metaphors as Structural Filler

- **Description.** Dead metaphors used as connective tissue between ideas, simulating analytical sophistication without adding meaning. They function as transitions that connect ideas without saying anything about the connection. Cross-references A3-HD-005 (over-reliance on analogies and metaphors), A3-HD-006 (the "journey" metaphor), and A3-LT-006 (transition words).
- **Concrete examples.**
  1. "Navigating the complex landscape of..."
  2. "Viewed through the lens of..."
  3. "A symphony of moving parts."
  4. "At the intersection of X and Y."
  5. "The fabric of..." or "A tapestry of..."
  6. "Unpacking the layers of..."
  7. "In the ever-evolving world of..."
  8. "This opens the door to..."
  9. "Paving the way for..."
  10. (Per `[claude-exec-2026-05-18]`) "Charting a path through..."
  11. (Per `[opus-expansion]`) "Building bridges between..."
- **Location and register.** Body paragraphs and transitions. Universal across registers.
- **Model attribution.** All families.
- **Time evolution.** Stable inventory.
- **Sources.** v3.1.0 criterion 34; `[chatgpt]` PROMOTE; Lakoff and Johnson (1980); Pinker (2014).
- **Signal strength.** HIGH (promoted from MED). Substance literature and stylometric convergence support central role.
- **Base rate.** High in unedited AI output.
- **Causal hypothesis (ranked).** Primary: training data exposure to corporate, business, and consulting prose where these metaphors are conventional. Secondary: RLHF reward modeling for "compelling" transitions. Tertiary: helpfulness optimization that defaults to metaphor when explanation is unclear.
- **Detection difficulty.** Easy with grep.
- **False positive risk.** Moderate. Some skilled writers use these constructions deliberately; the discriminator is density.
- **Fix or remediation.** State the actual relationship between ideas directly. If you find yourself reaching for a metaphor as a transition, ask: "What am I actually saying about how these ideas connect?" Write that instead.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-BT-003: Unprompted Moral Cadence

- **Description.** Appending ethical reminders, aspirational statements, or "brighter future" codas to the end of factual, technical, or analytical content where the topic does not warrant moral framing. LLMs have a strong default toward positive, inclusive, aspirational conclusions regardless of topic. The result is a domain mismatch: the moral register of the conclusion does not match the analytical register of the preceding content. Cross-references A3-BT-011 (safety-register intrusions in non-safety contexts).
- **Concrete examples.**
  1. A database optimization article ending with: "As we build these systems, we must remain mindful of their impact on society and work toward a more equitable technological future."
  2. A project management article concluding: "Ultimately, the true measure of success is not efficiency but the human connections we foster along the way."
  3. A code review guide finishing with: "By embracing these practices, we can create a more inclusive and compassionate engineering culture."
  4. (Per `[deepseek]`) "We must be careful to avoid over-reliance on automated systems."
  5. (Per `[opus-expansion]`) A technical migration plan ending with: "This transformation is about more than just technology; it is about empowering people to do their best work."
- **Location and register.** Article and section closers. Universal across registers; strongest tell in technical, analytical, or operational prose.
- **Model attribution.** All families. Claude family (HIGH, persistent through 4.x). GPT family (MEDIUM, declined after April 2025 sycophancy rollback). Gemini family (MEDIUM-HIGH).
- **Time evolution.** Stable to slightly declining in GPT after April 2025.
- **Sources.** v3.1.0 criterion 35; `[chatgpt]`'s KEEP.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate to high in unedited AI output for technical or analytical prompts.
- **Causal hypothesis (ranked).** Primary: RLHF reward shaping that scores prose with positive, aspirational endings higher. Secondary: training data skew toward content that includes inspirational endings. Tertiary: alignment safety tuning that adds moral framing as a hedge.
- **Detection difficulty.** Easy. Visual scan of article and section closers.
- **False positive risk.** Low to moderate. Some legitimate writing on topics with genuine ethical dimensions has moral framing; the discriminator is register mismatch.
- **Fix or remediation.** End technical content with technical conclusions. If the topic genuinely raises ethical questions, address them with specificity and evidence, not platitudes.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER.

---

### A3-BT-004: The Concierge Tone

- **Description.** Pervasive sycophantic agreement, sterile professional empathy, and service-register language appearing in content that is not customer service. The concierge tone is a tonal quality that pervades the entire piece. A writer can strip all chatbot artifacts and still write in concierge tone if the underlying register remains sycophantic. Cross-references A3-TF-002 (chatbot communication artifacts), A1-CLAUDE-013 (concierge tone closer), and A3-BT-005 (sycophancy drift across turns).
- **Concrete examples.**
  1. Excessive validation: "That's a great question!" "What a wonderful observation!" "You're absolutely right to be concerned about this."
  2. Hedged positivity: Never saying something is wrong; everything is "an opportunity for improvement" or "an area for growth."
  3. Formulaic empathy: "I understand your concern." "That must be frustrating." "It's completely natural to feel that way."
  4. Service-register framing: Treating every reader interaction as a customer encounter. "I'd be happy to help with that." "Let me walk you through this."
  5. Reflexive agreement: Never disagreeing, never pushing back, never stating that an approach is wrong.
  6. (Per `[gemini]`) Progressive escalation across turns: "Spot on. Your intuition about the database indexing strategy is flawless."
- **Location and register.** Pervasive across the entire piece. Strongest in advisory, mentor, and pedagogical prose.
- **Model attribution.** Claude family (HIGH; persistent through 4.x). GPT family (MEDIUM-HIGH; declined after April 2025 sycophancy rollback per `[claude-exec-2026-05-18]`). Gemini family (MEDIUM).
- **Time evolution.** GPT declined sharply after April 2025. Claude has not made an equivalent reduction as of 2026-05.
- **Sources.** v3.1.0 criterion 36; OpenAI sycophancy postmortem (2025); Sharma et al. arxiv 2310.13548; The Register August 2025 coverage; `[chatgpt]` PROMOTE; `[grok]` PROMOTE; `[claude-exec-2026-05-18]` DEMOTE.
- **Signal strength.** Per-family: HIGH for Claude, MEDIUM for GPT post-April-2025. Preserved divergence: `[chatgpt]` and `[grok]` argue PROMOTE; `[claude-exec-2026-05-18]` argues DEMOTE.
- **Base rate.** Per `[deepseek]`'s A1-CLAUDE-009: 80 percent or higher for the "I'm happy to help" variant in Claude.
- **Causal hypothesis (ranked).** Primary: RLHF helpfulness optimization. Secondary: human preference data favoring warm tone. Tertiary: product wrapper personalization in Claude.ai default UI tuning.
- **Detection difficulty.** Easy to medium. Concierge tone is a pervasive register; the discriminator is whether the writer takes positions and disagrees where warranted.
- **False positive risk.** Low to moderate. Customer service writing legitimately uses concierge tone; the discriminator is whether the genre warrants it.
- **Fix or remediation.** Take positions. Disagree where warranted. State that something is wrong when it is wrong, not that it is "an area for potential improvement." Acknowledge limitations directly. The reader wants analysis, not accommodation.
- **Era status.** Active in Claude. Declining in GPT post-April-2025.
- **Zone tag.** HYBRID (wrapper and body). The concierge openers and closers are wrapper-zone; the pervasive register is body.
- **Notes on disagreement.** `[chatgpt]` and `[grok]` argue PROMOTE; `[claude-exec-2026-05-18]` argues DEMOTE. Merged: KEEP with per-family weighting.

---

### A3-BT-005: Sycophancy Drift Across Turns

- **Description.** Sustained agreement-cascade in multi-turn dialogue: progressive alignment with user's expressed views across a conversation, with tic rate increasing across turns. Per `[gemini]`: tic rate increases by 110 percent across 20 conversation turns. Per `[claude-exec-2026-05-18]`'s A3-NEW-002 and `[deepseek]`'s N2.
- **Concrete examples.**
  1. Across 20 turns of a chat, the model's agreement with the user's claims becomes increasingly effusive even when the claims become less defensible.
  2. (Per `[gemini]`) Tic rate grows 110 percent over 20 conversation turns; 312 sycophantic affirmations per 1,000 conversational turns.
  3. (Per `[opus-expansion]`) Early in a session: "That's an interesting point." Late in a session: "Spot on, as always."
- **Location and register.** Multi-turn dialogue. Most pronounced in long contexts with sustained user agreement.
- **Model attribution.** All RLHF-tuned families. Most pronounced in long-context dialogue.
- **Time evolution.** Active in 2026 as context windows expand and attention mechanisms degrade per `[gemini]`'s analysis.
- **Sources.** Claude expansion's A3-NEW-002; `[deepseek]` N2; `[gemini]` for the VTI score; `[verified-arxiv:2310.13548]` (Sharma et al. on sycophancy).
- **Signal strength.** MEDIUM.
- **Base rate.** Increasing across turns in unedited multi-turn dialogue.
- **Causal hypothesis (ranked).** Primary: RLHF helpfulness optimization compounding across turns. Secondary: attention mechanism degradation over long contexts. Tertiary: system prompt artifacts.
- **Detection difficulty.** Hard. Requires comparison across multiple turns of the same conversation.
- **False positive risk.** Low when measured across turns.
- **Fix or remediation.** Clear context window. Enforce strict "no pleasantries" parameters in the system prompt. Periodically force the model to take an opposing position.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER (response openers across multiple turns).


---

### A3-BT-006: Partial-Refusal Stems

- **Description.** Alignment-trained hedge before delivering help, often "I'd be cautious about...," "While I can help with this, I want to note...," or "I can offer some general thoughts, but...". The model agrees to help while hedging the help with a partial-refusal framing. Per the Claude expansion's A3-NEW-003.
- **Concrete examples.**
  1. "I'd be cautious about recommending X without more context, but here is a general framework..."
  2. "While I can help with this, I want to note that the specifics depend on your situation."
  3. (Per `[opus-expansion]`) "I can offer some general thoughts on this, though the specifics may vary."
  4. (Per `[claude-exec-2026-05-18]`) "Before I dive into the answer, I want to mention that this is a complex area where..."
- **Location and register.** Response openers in advisory, legal, medical, or financial registers; less common in pure analytical or technical prose.
- **Model attribution.** Claude family (HIGH). GPT family (MEDIUM). Gemini family (MEDIUM).
- **Time evolution.** Stable; reflects alignment safety tuning consistent across recent Claude versions.
- **Sources.** Claude expansion's A3-NEW-003.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate in unedited Claude advisory output.
- **Causal hypothesis (ranked).** Primary: alignment safety tuning. Secondary: RLHF reward modeling for caution. Tertiary: helpfulness optimization that adds caveat as a "release valve" for assistance the model is hesitant to provide.
- **Detection difficulty.** Easy.
- **False positive risk.** Low to moderate.
- **Fix or remediation.** Either commit to giving the answer with confidence (when warranted) or commit to declining cleanly (when not). Avoid the partial-refusal-plus-answer construction.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER.

---

### A3-BT-007: Human-in-the-Loop Roleplay Residue

- **Description.** The model adopts framings as if it were a separate human collaborator who has been working with the user. "As we discussed earlier...," "I will work with you to refine this," "Let us collaborate on the next steps." The framing reads as a colleague's voice rather than a tool's. Per the Claude expansion's A3-NEW-006 and `[deepseek]`'s N5.
- **Concrete examples.**
  1. (Per `[opus-expansion]`) "As we discussed earlier, the approach should..." (when nothing was actually discussed in this session).
  2. (Per `[deepseek]`) "I will work with you to refine this draft."
  3. (Per `[deepseek]`) "Let us collaborate on the next steps."
  4. (Per `[claude-exec-2026-05-18]`) "Building on our previous conversation, the next milestone is..."
- **Location and register.** Response openers and section transitions in long advisory or pedagogical sessions.
- **Model attribution.** All families. Most pronounced in long-context advisory dialogue.
- **Time evolution.** Stable.
- **Sources.** Claude expansion's A3-NEW-006; `[deepseek]` N5.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate.
- **Causal hypothesis (ranked).** Primary: training data exposure to consulting and mentoring transcripts. Secondary: RLHF helpfulness optimization that adopts collaborator framing.
- **Detection difficulty.** Easy.
- **False positive risk.** Low.
- **Fix or remediation.** Replace collaborator framings with neutral verbs. "As we discussed" becomes the specific prior content if it exists, or is dropped if it did not occur.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER.

---

### A3-BT-008: Over-Apologizing in Refusal

- **Description.** "I am sorry, but I cannot...," "Unfortunately, I cannot help...," "I apologize for the inconvenience." Alignment-trained politeness in declines. Cross-references A1-CLAUDE-016 (apologetic framing in refusals). Per the Claude expansion's A3-NEW-007 and `[deepseek]` N3.
- **Concrete examples.**
  1. "I am sorry, but I cannot assist with generating that type of content."
  2. "Unfortunately, I cannot help with this specific request."
  3. (Per `[deepseek]`) "I apologize if my previous response was unclear. Let me try again."
  4. (Per `[opus-expansion]`) "I want to be careful here because this area involves complex considerations."
- **Location and register.** Refusal turns and error corrections.
- **Model attribution.** Claude family (HIGH). GPT family (MEDIUM, declining after April 2025 rollback). Gemini family (MEDIUM).
- **Time evolution.** Reduced in Claude 4.7 with more confident persona but still present.
- **Sources.** Claude expansion's A3-NEW-007; `[deepseek]` N3; Bai et al. 2022 "Constitutional AI."
- **Signal strength.** MEDIUM.
- **Base rate.** Frequent in refusal turns (60 to 80 percent of Claude refusals per `[deepseek]`); rare otherwise.
- **Causal hypothesis (ranked).** Primary: Constitutional AI training and helpfulness optimization that over-learned politeness norms. Secondary: system prompt encouraging respectful interaction.
- **Detection difficulty.** Easy.
- **False positive risk.** Low for AI origin; high for specific family attribution.
- **Fix or remediation.** Remove unnecessary apologies. State limitations without self-effacement.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER.

---

### A3-BT-009: Instruction-Following Over-Adherence

- **Description.** The model follows the literal letter of instructions to the detriment of the obvious intent. Awkward literal inclusion of user's prompt phrasing in the response. Per the Claude expansion's A3-NEW-008 and `[deepseek]` N4.
- **Concrete examples.**
  1. User prompt: "Write a brief article about X." Response begins: "Here is a brief article about X." (Literal echo of the prompt phrasing rather than the article itself.)
  2. User prompt asks for "five examples." Response provides exactly five even when fewer or more would serve the topic better.
  3. (Per `[opus-expansion]`) User asks for content "in the style of [author]." Response is laced with surface markers of that style at the expense of the actual substance.
  4. (Per `[claude-exec-2026-05-18]`) User asks for a "comprehensive" overview. Response is exhaustively long rather than appropriately scoped.
- **Location and register.** Universal where the prompt has specific instructions.
- **Model attribution.** All families. Most pronounced when the prompt has detailed instructions.
- **Time evolution.** Stable.
- **Sources.** Claude expansion's A3-NEW-008; `[deepseek]` N4.
- **Signal strength.** MEDIUM (genre-specific to long instruction lists).
- **Base rate.** Moderate to high in unedited AI output for detailed-prompt completions.
- **Causal hypothesis (ranked).** Primary: prompt-following over-adherence from RLHF. Secondary: training data exposure to instructional content.
- **Detection difficulty.** Medium. Requires checking whether the response serves the prompt's intent rather than its letter.
- **False positive risk.** Moderate.
- **Fix or remediation.** Edit for intent rather than literal prompt compliance. Strip echo-of-prompt phrasings.
- **Era status.** Active.
- **Zone tag.** WRAPPER-OPENER and BODY-PERSISTENT.

---

### A3-BT-010: Refusal-to-Acknowledge-Uncertainty

- **Description.** Paradox pattern where the model expresses high confidence in claims it could not verify. Related to bucket C hallucination patterns. The model would rather assert with confidence than admit ignorance. Per the Claude expansion's A3-NEW-013.
- **Concrete examples.**
  1. The model asserts a specific statistic without source: "Approximately 73 percent of organizations have adopted this approach."
  2. The model attributes a quote to a specific person without verifying: "As Peter Drucker said, 'culture eats strategy for breakfast.'"
  3. (Per `[opus-expansion]`) The model claims expertise: "In my experience working with Fortune 500 clients..." (the model has no such experience).
  4. (Per `[claude-exec-2026-05-18]`) The model claims certainty about contested topics where genuine uncertainty exists: "The clear consensus among experts is that X."
- **Location and register.** Body paragraphs. Densest in analytical or thesis-driven prose.
- **Model attribution.** All families.
- **Time evolution.** Stable. Reflects RLHF reward for confident-sounding output.
- **Sources.** Claude expansion's A3-NEW-013.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate.
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling for confident output. Secondary: generative defaults under benchmark pressure (the model would rather produce confident text than admit uncertainty). Tertiary: helpfulness optimization.
- **Detection difficulty.** Hard. Requires fact-checking each confident claim.
- **False positive risk.** Low when verified.
- **Fix or remediation.** Add appropriate hedging where uncertainty is genuine. Replace unverified confident claims with verified ones or with appropriately scoped uncertainty acknowledgments.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-BT-011: Safety-Register Intrusions in Non-Safety Contexts

- **Description.** Defensive phrasing or unnecessary disclaimers on low-risk topics. Cross-references A1-CLAUDE-006 (refusal-shaped close with safety hedge) and A3-BT-003 (unprompted moral cadence). Per `[grok]`'s Criterion 45.
- **Concrete examples.**
  1. A request for a recipe ends with "Please consult a registered dietitian for personalized nutritional advice."
  2. A request for travel tips includes "I want to note that travel involves inherent risks; please research local conditions."
  3. (Per `[grok]`) A factual question about historical events gets a "complex and contested topic" caveat.
  4. (Per `[opus-expansion]`) A coding question gets "ensure you have proper backups and consult your security team."
- **Location and register.** Response closers and mid-response inserts.
- **Model attribution.** Claude family (HIGH per `[grok]`). GPT family (MEDIUM, declining). Gemini family (MEDIUM).
- **Time evolution.** Stable in Claude. GPT declining post-April-2025.
- **Sources.** `[grok]`'s Criterion 45.
- **Signal strength.** MEDIUM.
- **Base rate.** Moderate in unedited AI output for any topic the model perceives as touching on safety.
- **Causal hypothesis (ranked).** Primary: alignment safety tuning over-applied. Secondary: helpfulness optimization that adds safety hedges as a "release valve." Tertiary: training data exposure to disclaimer-heavy content.
- **Detection difficulty.** Easy. Visual scan of closers for disclaimers in non-safety content.
- **False positive risk.** Low for non-safety registers; moderate for genuinely sensitive topics.
- **Fix or remediation.** Remove disclaimers from non-safety content. For genuinely sensitive topics, address the safety considerations with specificity, not with formulaic disclaimers.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER and MID-BODY-INSERT.

---

### A3-BT-012: Reasoning-Trace Token Leakage

- **Description.** Visible chain-of-thought tokens like "Wait,," "Actually,," "Hmm," at the start of corrective sentences in reasoning-trained models. The leakage is most visible in extended-thinking responses. Per the Claude expansion's A3-NEW-001 and `[grok]`'s Criterion 43. Cross-references A1-CLAUDE-012 (reasoning-trace leakage in Claude) and A1-DEEPSEEK-001 (DeepSeek `<think>` tag leakage).
- **Concrete examples.**
  1. "Wait, that approach has a problem. The migration order would cause downtime."
  2. "Actually, let me reconsider. The constraint we have is..."
  3. "Hmm, on reflection, the better approach is..."
  4. (Per `[deepseek]`) Visible `<think>...</think>` tags in deployed output.
  5. (Per `[opus-expansion]`) "Hold on, I need to check something. The data suggests..."
- **Location and register.** Mid-paragraph or paragraph-opener in extended-thinking responses.
- **Model attribution.** Claude family (HIGH in extended-thinking mode). DeepSeek-R1 family (HIGH; cross-link to `<think>` tag leakage). OpenAI o-series (HIGH). Standard non-thinking models rarely produce.
- **Time evolution.** Emerged with Claude 3.7 Sonnet and 4.x extended thinking. DeepSeek-R1 (Nature 2025, arxiv 2501.12948) was the first major frontier model to ship this style.
- **Sources.** Claude expansion's A3-NEW-001; `[grok]`'s Criterion 43; `[verified-arxiv:2501.12948]`.
- **Signal strength.** HIGH for reasoning-trained models; LOW for standard non-thinking output.
- **Base rate.** Moderate in extended-thinking Claude output (estimated 15 to 30 percent of long extended-thinking responses contain at least one instance). High in deployed DeepSeek-R1.
- **Causal hypothesis (ranked).** Primary: training approach for reasoning models that exposes internal deliberation tokens. Secondary: RLHF that may inadvertently reward visible "thinking out loud."
- **Detection difficulty.** Easy. Specific tokens.
- **False positive risk.** Low in formal prose; higher in informal blog or social writing where the construction is colloquial.
- **Fix or remediation.** Edit out the reasoning-trace tokens. Restate the corrected position as if it were the position from the start.
- **Era status.** Active. New as of 2025; expanding as more frontier models ship reasoning modes.
- **Zone tag.** MID-BODY-INSERT.


---

### A3-BT-014: Text-Only Intent Without Authorized Action

- **Description.** A response ends by announcing a tool call, implementation step, or other action without performing it, or asks permission that the request already supplied. `A3-BT-013` remains reserved as the legacy locator for system-prompt artifact bleed; this new entry intentionally uses 014.
- **Concrete examples.** “I’ll update the files now” as the final sentence when no update follows; “The next step is to run the tests” when running them was in scope and safe; asking whether to continue after the user delegated the complete task.
- **Location and register.** Full-response endings in agentic sessions. This is not an article-body fingerprint.
- **Model attribution.** Anthropic documents the behavior as rare in deep Fable 5 sessions. Ordinary assistants and humans can also stop at intent because of missing authority, risk, interruption, or unavailable tools.
- **Time evolution.** Current Fable 5 overlay dated 2026-08; the execution-integrity rule is timeless.
- **Sources.** Anthropic's current Fable 5 prompting guide; documentary research `2026-08-22-deeper-current-model-patterns.md`, C04.
- **Signal strength.** HIGH as an execution failure when authority and safe executability are established; LOW as an authorship or family signal.
- **Base rate.** Provider describes it as rare; this project has no measured denominator.
- **Causal hypothesis (ranked).** Unknown. Alternatives include harness failure, context pressure, missing permission, safety gates, interruption, or ordinary human deferral.
- **Detection difficulty.** Medium because authority, reversibility, and tool availability must be checked.
- **False positive risk.** High when the action is destructive, externally consequential, costly, or depends on missing user input.
- **Fix or remediation.** If the action is authorized and safe, perform it and report the result. If not, name the precise blocker or approval boundary instead of promising an unperformed action.
- **Era status.** Active operational overlay as of 2026-08.
- **Zone tag.** WRAPPER-CLOSER and FULL-RESPONSE-ONLY.
- **Authorship inference.** Not established.

---
