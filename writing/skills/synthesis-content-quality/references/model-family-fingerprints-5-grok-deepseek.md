# Model-Family Fingerprints (A1), part 5 of 6

Part 5 of the file split from [model-family-fingerprints.md](model-family-fingerprints.md), which keeps the opening sections and lists every part. The text below is unchanged.

Contents:
- A1.5 xAI Grok family (A1-GROK-001 to A1-GROK-010, 10 entries)
- A1.6 DeepSeek family (A1-DEEPSEEK-001 to A1-DEEPSEEK-010, 10 entries)

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
