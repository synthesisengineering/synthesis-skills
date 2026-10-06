# Detailed Criteria Reference (v4.0), part 1 of 5

Part 1 of the file split from [detailed-criteria.md](detailed-criteria.md), which keeps the opening sections and lists every part. The text below is unchanged.

Contents:
- Section A3-LT: Language and Tone (A3-LT-001 to A3-LT-015, 15 entries)

## Section A3-LT: Language and Tone

### A3-LT-001: Undue Emphasis on Importance and Symbolism

- **Description.** LLMs inflate the significance of subjects by connecting them to broader, grandiose themes. The construction reads as evaluative claim ("X stands as a testament to Y") in places where a neutral descriptive sentence would serve. Sibling to A3-LT-002 (promotional language) and A3-BT-002 (exhausted metaphors). The Perplexity catalog's A1-CLAUDE-026 "Underscores the importance" closer is the same phenomenon at the structural level.
- **Concrete examples.**
  1. "The restaurant stands as a testament to community resilience."
  2. "This minor product update represents a watershed moment in technological innovation."
  3. "The town embodies the spirit of cultural heritage and economic vitality."
  4. "Her work carries enhanced significance in light of recent developments."
  5. (Per Perplexity) "This collaboration underscores the importance of cross-functional alignment."
- **Location and register.** Body paragraphs and section closers. Strongest in feature journalism, profile writing, marketing copy, and any register where significance is being claimed rather than demonstrated. Less common in technical writing where evidence is expected to carry the weight.
- **Model attribution.** All RLHF-tuned families produce this pattern. Claude family (HIGH confidence per `[cross-validated:claude-exec+perplexity+manus-ai]`), GPT family (HIGH), Gemini (MEDIUM-HIGH). Llama lower (per `[gemini]`: 0.21x Llama distinctiveness ratio relative to other families on this construction class).
- **Time evolution.** Present from earliest instruction-tuned models forward. Has not visibly declined across model generations because human preference data continues to favor "significant-sounding" prose for prompts requesting analysis or summary. Per `[chatgpt]`: stable across 2022 to 2026.
- **Sources.** v3.1.0 criterion 1; Manus AI's A3-NEW-014 (unwarranted optimism) intersects; Perplexity's A1-CLAUDE-026; Pinker (2014) on prose inflation per `[manus-ai]`. Stockton's "Don't Write Like AI" series (2025) per `[claude-exec-2026-05-18]`.
- **Signal strength.** MEDIUM. HIGH when clustering with A3-LT-002 (promotional language), A3-BT-001 (saturated vocabulary), and A3-LT-007 (section-ending summaries).
- **Base rate.** Moderate to high in unedited AI output for content with descriptive or evaluative prompts. Per `[opus-expansion]`: 30 to 50 percent of feature-style completions contain at least one instance.
- **Causal hypothesis (ranked).** Primary: RLHF reward shaping that scores prose with explicit significance markers higher than neutral description. Secondary: training-data skew toward marketing, journalism, and biographical genres where this register is common. Tertiary: helpfulness optimization (the model assumes the reader wants confirmation that the subject matters).
- **Detection difficulty.** Easy. Grep for the lexical markers ("stands as a testament," "plays a vital role," "represents a milestone," "embodies").
- **False positive risk.** Moderate. Skilled feature writers use these constructions sparingly for genuine emphasis. The discriminator is density (three or more in a single piece) and whether the significance claim is followed by evidence.
- **Fix or remediation.** Replace with descriptive prose plus evidence. "The restaurant stands as a testament to community resilience" becomes "The restaurant has hosted free meals for displaced families every Tuesday since the 2024 floods."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.
- **Notes on disagreement.** Perplexity proposes DEMOTE on the related "As an AI language model, I" surface form (genuinely declining). The merged v4.0 entry retains the broader symbolism-inflation pattern at MED and treats the "As an AI" preamble separately as a Historical-era pattern (see A3-TF-002).

---

### A3-LT-002: Promotional and Travel Brochure Language

- **Description.** Content reads like marketing copy: saturated marketing-register adjectives ("breathtaking," "captivating," "stunning"), generic place descriptors ("nestled in the heart of," "a hidden gem"), and uniformly positive evaluation. The pattern is most diagnostic when applied to topics that do not warrant marketing register (technical infrastructure, internal process documents, plain news).
- **Concrete examples.**
  1. "Nestled in the heart of the countryside, the town of Millbrook boasts a rich cultural heritage and stunning natural beauty."
  2. "This captivating destination offers visitors a unique blend of historic charm and modern amenities."
  3. "Our breathtaking new product is a must-have for the modern consumer."
  4. (Per `[chatgpt]`) "The platform delivers unparalleled value to its diverse and vibrant user community."
  5. (Per `[manus-ai]`) "A renowned hidden gem offering an authentic experience for those seeking adventure off the beaten path."
- **Location and register.** Universal in travel, lifestyle, food, retail, and real-estate writing. Strong tell when found in technical writing, internal communications, or news where the register does not match the content.
- **Model attribution.** All families. Claude and GPT-4o dense; Gemini somewhat less; Llama notably less per `[gemini]`. Per Matsui et al. PME 2025 (the academic anchor): saturated marketing-register vocabulary documented at Z above 3.5 across 103 of 135 candidate focal words in 2024 PubMed corpora when prompted for promotional registers.
- **Time evolution.** Stable across generations. The lexical inventory has evolved with consumer-marketing trends (the addition of "vibrant," "authentic," "curated" to the cluster) but the underlying pattern is consistent.
- **Sources.** v3.1.0 criterion 2; Matsui (2025) PME per `[claude-exec-2026-05-18]`; `[cross-validated:manus-ai+perplexity+chatgpt]`. Strunk and White (2000) on advertising-register cliches per `[manus-ai]`.
- **Signal strength.** HIGH (promoted from MED). The empirical anchor in Matsui 2025 and the cross-family persistence support the promotion.
- **Base rate.** High in unedited AI output for travel, lifestyle, retail, and real-estate prompts. Moderate elsewhere. Per `[opus-expansion]`: 65 to 80 percent of unedited completions for promotional prompts; 15 to 25 percent for general analytical prompts (register bleed).
- **Causal hypothesis (ranked).** Primary: training-data skew (the model has seen vast quantities of marketing copy and overweights it). Secondary: RLHF reward modeling that scores polished, positive language higher. Tertiary: helpfulness optimization that interprets "describe this place" as a request to promote.
- **Detection difficulty.** Easy. Saturated marketing vocabulary is grep-able. The register bleed into non-marketing prompts is the more useful diagnostic.
- **False positive risk.** Low for register bleed (technical or analytical content with marketing register is a clear tell). Moderate for actual marketing prompts where the register is contextually appropriate.
- **Fix or remediation.** Replace promotional adjectives with specific factual descriptions. "Stunning natural beauty" becomes a description of what specifically can be seen. "Rich cultural heritage" becomes the named institutions, festivals, or traditions.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-LT-003: Editorial Commentary and Meta-Analysis

- **Description.** LLMs inject interpretation, importance judgments, or explicit guidance about what readers should think, often using meta-commentary phrases ("it's important to note," "notably," "it is worth mentioning") to flag what the reader should care about rather than letting the content carry the signal. Cross-references A3-CLAUDE-001 (the "It is important to note" preamble) and A3-LT-007 (section-ending summaries). Per Perplexity's A1-CLAUDE-001 "Transitional Phrase Cluster" the cluster includes "it's worth noting," "at its core," "let's explore," "when it comes to," "navigating [topic]," and "ultimately."
- **Concrete examples.**
  1. "It's important to note that this development represents a significant shift in the industry."
  2. "It is worth emphasizing that stakeholders should pay close attention to these emerging trends."
  3. "Notably, the policy change comes at a critical juncture for the sector."
  4. "Interestingly, the data reveals a pattern that has not been previously observed."
  5. (Per ChatGPT) "Crucially, the implications of this finding extend far beyond the immediate context."
  6. (Per Perplexity) "At its core, this problem reduces to a question of resource allocation."
- **Location and register.** Paragraph openers and sentence beginnings. Universal across registers, densest in analytical, policy, and advisory prose. Particularly common after a factual statement, where the meta-commentary functions as an alignment-trained hedge rather than load-bearing qualifier.
- **Model attribution.** Claude family (HIGH per `[cross-validated:claude-exec+perplexity+deepseek+manus-ai+chatgpt+gemini]`). GPT family (MEDIUM-HIGH; uses similar hedging constructions with different phrasing such as "It's important to remember" or "Keep in mind"). Gemini also produces this pattern.
- **Time evolution.** Emerged with Claude 2 in mid-2023; peaked in Claude 3.5 Sonnet (mid-2024); began mild decline in Claude 4.5 Opus and later; still at meaningful base rate in 2026-05.
- **Sources.** v3.1.0 criterion 3; `[cross-validated:claude-exec+perplexity+chatgpt]`. Liang et al. 2024 (Nature, arxiv 2406.07016) on LLM use in scientific papers. Pangram and GPTZero detector methodology pages list this preamble family as a high-signal indicator.
- **Signal strength.** MEDIUM standalone. HIGH when clustered with three or more from the broader Perplexity cluster ("it's worth noting," "at its core," "when it comes to") in 500 words.
- **Base rate.** Frequent in unedited Claude output (estimated 40 to 60 percent of non-creative completions contain at least one instance per `[deepseek]` and `[opus-expansion]`). Rare in human-written non-academic text.
- **Causal hypothesis (ranked).** Primary: RLHF reward shaping that rewards caution and qualification. Secondary: training-data skew toward academic and policy registers. Tertiary: system-prompt artifacts instructing "be thoughtful and nuanced."
- **Detection difficulty.** Easy. Grep for the specific phrases. Differentiating genuine analysis from empty commentary markers requires reading context.
- **False positive risk.** Moderate. Academic and policy writers use this construction; the discriminator is density and combination with other markers.
- **Fix or remediation.** Replace with direct assertion. If the qualifier is genuinely load-bearing, embed it in the main clause rather than as a preamble. "It's important to note that the regulatory environment has shifted" becomes "The regulatory environment shifted in 2025." Cross-link to A2-SUB-007 (hedging as substance evasion).
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT (also HYBRID at wrapper boundaries).
- **Notes on disagreement.** ChatGPT's REVISE recommendation focuses on differentiating genuine analysis from empty commentary; that distinction is folded into the fix guidance above.

---

### A3-LT-004: Superficial Analysis with Participial Phrases

- **Description.** Sentences end with "-ing" phrases that add shallow analytical commentary without substance. The construction simulates inference (it looks like the writer is drawing a conclusion) without providing the inference content. Cross-references A2-SUB substance tests and A3-BT-002 (exhausted metaphors).
- **Concrete examples.**
  1. "The company announced new policies, highlighting its commitment to sustainability."
  2. "The festival attracts thousands of visitors annually, underscoring the region's cultural importance."
  3. "The research revealed new findings, demonstrating the team's innovative approach."
  4. "The CEO addressed the criticism directly, signaling a new era of transparency."
  5. (Per ChatGPT) "Sales exceeded projections, reflecting strong consumer confidence."
  6. (Per ChatGPT) "The report cited multiple data sources, ensuring a comprehensive analysis."
- **Location and register.** Sentence closers throughout body paragraphs. Strongest in feature journalism, corporate communications, and analyst commentary. Less common in dialogue, fiction, and casual prose.
- **Model attribution.** All families (HIGH for Claude and GPT-4o; MEDIUM for Gemini). Per `[chatgpt]`: better evidence in 2025-2026 that these structures simulate inference without adding content.
- **Time evolution.** Stable across model generations. Reflects training-data exposure to corporate communications and analytical journalism, both of which overuse the construction.
- **Sources.** v3.1.0 criterion 4; `[chatgpt]` for PROMOTE recommendation; cross-link to A2 substance-test framework per the unified bucket A consensus.
- **Signal strength.** HIGH (promoted from MED). Promotion rests on the cross-link to A2 substance tests: the construction is a substance-evasion device, and the substance test is the diagnostic.
- **Base rate.** Moderate to high in unedited AI output for analytical or news-style prompts. Per `[opus-expansion]`: 35 to 55 percent of news-summary completions contain at least one instance.
- **Causal hypothesis (ranked).** Primary: training-data skew toward corporate communications. Secondary: RLHF reward modeling that scores prose with explicit conclusion markers higher. Tertiary: helpfulness optimization that interprets "analyze this" as a request to add interpretive flourish even when the content does not support genuine inference.
- **Detection difficulty.** Easy. The "-ing" closer is grep-able.
- **False positive risk.** Moderate. The construction is legitimate when the participial phrase carries actual content; the discriminator is whether the participial closer adds inference or merely repackages what the main clause already said.
- **Fix or remediation.** Either provide real analysis with evidence (replacing the participial phrase with a new sentence that carries the inference content) or let the statement stand alone. "The CEO addressed the criticism directly, signaling a new era of transparency" becomes "The CEO addressed the criticism in a 40-minute open Q&A; she committed to monthly all-hands meetings, a reversal of the prior policy."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-LT-005: Negative Parallelism

- **Description.** Overuse of "not X but Y" constructions to create artificial contrast and drama. Includes the variants "not just X, but Y," "not only X, but also Y," "it is not merely X; it is Y." Preference data in RLHF directly reinforces antithesis per `[claude-exec-2026-05-18]`'s causal analysis. ChatGPT and Stockton's "Don't Write Like AI" series (2025) argue for DEMOTE on the basis that many human essayists use this construction naturally.
- **Concrete examples.**
  1. "The restaurant is not just a place to eat, but a cornerstone of community gathering."
  2. "This technology is not merely an improvement, but a revolutionary breakthrough."
  3. "The policy change represents not only a shift in strategy but also a commitment to transparency."
  4. (Per Claude expansion) "It's not just about cost reduction; it's about reimagining the entire workflow."
  5. (Per Claude expansion) "The migration was not simply a technical upgrade but a strategic repositioning."
- **Location and register.** Body paragraphs throughout, particularly in thesis-statement positions (opening of sections, transitions between arguments) and conclusions.
- **Model attribution.** Claude family (HIGH per `[claude-exec-2026-05-18]`). GPT family (MEDIUM). The Claude-specific elevation rests on preference-data reinforcement of antithesis structures.
- **Time evolution.** Present from earliest Claude versions forward; stable through 4.x. GPT family rate has been roughly stable across generations.
- **Sources.** v3.1.0 criterion 5; `[claude-exec-2026-05-18]`; Stockton (2025) "Don't Write Like AI" series for the DEMOTE counterargument.
- **Signal strength.** MEDIUM (KEEP with note). The disagreement between ChatGPT (DEMOTE) and the Claude expansion (PROMOTE) is preserved. The merged decision keeps the tier at MEDIUM but flags that combination weighting matters more in v4.0.
- **Base rate.** Moderate in unedited AI output (estimated 20 to 35 percent of analytical or argumentative completions contain at least one instance per `[opus-expansion]`). Higher for opinion or thesis-driven prompts.
- **Causal hypothesis (ranked).** Primary: RLHF preference data that consistently rates antithesis higher than declarative parallelism (per `[claude-exec-2026-05-18]`'s causal analysis). Secondary: training-data skew toward rhetoric corpora where the construction is foundational.
- **Detection difficulty.** Easy. The "not just X but Y" surface form is grep-able.
- **False positive risk.** Moderate. Skilled essayists deploy the construction sparingly for genuine contrast; the discriminator is density (three or more in a single piece is a strong signal).
- **Fix or remediation.** Use the structure sparingly and only when the contrast is genuine and significant. When the "Y" reframes rather than contrasts with "X," collapse to a single positive claim.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.
- **Notes on disagreement.** ChatGPT argues DEMOTE (human essayists use this naturally); Claude expansion argues PROMOTE (preference data specifically reinforces antithesis). Both views have merit. Merged decision: KEEP at MEDIUM with combination-weighting note.

---

### A3-LT-006: Overuse of Transition Words and Formal Conjunctions

- **Description.** Excessive, stilted use of transitional phrases that create an essay-like or overly formal tone. The pattern is the density and mechanical placement, not the words themselves. Cross-references A3-LT-014 (orphaned demonstratives) and A3-FA-008 (cross-sentence lexical echoing).
- **Concrete examples.**
  1. "Moreover, the data suggests a significant trend."
  2. "Furthermore, we must consider the implications."
  3. "Additionally, it is worth noting the broader context."
  4. (Per `[deepseek]`'s A1-CLAUDE-015) "However, several challenges remain."
  5. (Per `[deepseek]`) "Consequently, the team revised its approach."
  6. (Per `[chatgpt]`) "Nevertheless, the underlying assumptions warrant scrutiny."
- **Location and register.** Paragraph openers. Densest in academic, policy, and analytical prose. Strong tell when used in casual or short-form content where transitions should be implicit.
- **Model attribution.** All families. Claude (HIGH for "However," paragraph pivot per `[deepseek]`'s A1-CLAUDE-015: 30 to 40 percent of multi-paragraph analytical completions). GPT family (MEDIUM; "Moreover" and "Furthermore" densest in 4o). Gemini (MEDIUM).
- **Time evolution.** Stable across generations. Per `[chatgpt]`'s DEMOTE recommendation: frontier models have improved slightly. Per `[claude-exec-2026-05-18]`'s PROMOTE recommendation: the combination signal has strengthened even if standalone signal has weakened.
- **Sources.** v3.1.0 criterion 6; `[chatgpt]` for DEMOTE; `[claude-exec-2026-05-18]` for PROMOTE; `[deepseek]`'s A1-CLAUDE-015 for "However" pivot density.
- **Signal strength.** LOW base rate; MEDIUM clustered with three or more from the transition-word inventory. Combination signal: HIGH when paired with uniform sentence length (A3-LT-010), bulleted bolded lead-ins (A3-SS-002), and section-ending summaries (A3-LT-007).
- **Base rate.** High in unedited AI long-form (estimated 70 to 90 percent of multi-paragraph completions contain at least one). Moderate in short-form.
- **Causal hypothesis (ranked).** Primary: training-data skew toward academic and analytical writing where these transitions are conventional. Secondary: RLHF reward modeling that scores "well-organized" output higher. Tertiary: helpfulness optimization that announces logical structure explicitly.
- **Detection difficulty.** Easy. Grep for the inventory.
- **False positive risk.** Moderate. Skilled analytical writers use these transitions; the discriminator is density and combination.
- **Fix or remediation.** Let ideas connect through logical flow. When transitions are needed, vary them and use the simplest option that works. Replace formal conjunctions with implicit transitions or with the simplest connective ("And," "But," "So").
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.
- **Notes on disagreement.** ChatGPT and Gemini propose DEMOTE; Claude expansion proposes PROMOTE. Merged: KEEP with combination weighting.

---

### A3-LT-007: Section-Ending Summaries

- **Description.** Paragraphs or sections end with explicit summary statements ("In summary," "In conclusion," "Overall," "In essence," "To summarize," "Ultimately,") mimicking academic essay structure. The summary adds no new information in short content; in long-form, every section ends with a backward-looking pause. Cross-references A1-CLAUDE-007 (section-ending recap sentence) and A2-SUB-013 (frictionless-transition padding).
- **Concrete examples.**
  1. "In summary, the three factors above demonstrate that X is the most viable approach."
  2. "Overall, the data supports the conclusion that..."
  3. "Ultimately, finding a balance between performance and cost is crucial."
  4. (Per Perplexity) "Together, these considerations underscore the importance of careful planning."
  5. (Per Perplexity) "This illustrates why the framework outlined here provides a useful starting point."
- **Location and register.** Mid-document section closers and final response closers. Universal across registers, densest in technical and analytical prose.
- **Model attribution.** Claude family (HIGH); GPT-4o family (HIGH); Gemini (MEDIUM-HIGH). Per Perplexity: comparable rates in Claude and GPT-4o. Per `[deepseek]`: 60 to 80 percent of multi-section completions.
- **Time evolution.** Present from Claude 2 forward; persistent through 4.x. Slightly reduced in Claude 4 with explicit no-summary system prompting.
- **Sources.** v3.1.0 criterion 7; `[cross-validated:manus-ai+perplexity+deepseek]`; BlogPros 2026 practitioner observations per Perplexity.
- **Signal strength.** MEDIUM standalone; HIGH in combination with bolded lead-ins (A3-SS-002) and balanced two-handed sentences (A3-LT-005).
- **Base rate.** High in unedited AI long-form (estimated 60 to 80 percent of multi-section responses). High in templated blog and educational content. Lower in dialogue.
- **Causal hypothesis (ranked).** Primary: RLHF reward modeling that rewards clear structure including explicit summarization. Secondary: training-data skew toward academic prose. Tertiary: helpfulness optimization (the model assumes the reader needs the recap).
- **Detection difficulty.** Easy.
- **False positive risk.** Low to moderate. Technical writing and textbooks use section recaps; the discriminator is mechanical placement (every section gets one regardless of need).
- **Fix or remediation.** Remove the recap unless the section's point is genuinely buried. If buried, rewrite the section's lead, not its tail. News articles, blogs, and most media content do not summarize sections like essays.
- **Era status.** Active.
- **Zone tag.** WRAPPER-CLOSER for final-closer instances; BODY-PERSISTENT for mid-document section closers.

---

### A3-LT-008: The Rule of Three

- **Description.** Formulaic grouping of ideas, traits, or examples in threes. The rule of three is a legitimate rhetorical device; the LLM pathology is using it as a default structure for every list, every adjective cluster, every example set. Human writing varies list lengths naturally. Cross-references A3-SS-002 (bulleted lists with bolded lead-ins) and A3-LT-006 (transition density).
- **Concrete examples.**
  1. "Innovative, impactful, and transformative."
  2. "Boost morale, increase productivity, and foster collaboration."
  3. "Keynote sessions, panel discussions, and networking opportunities."
  4. (Per `[chatgpt]`) "Cost-effective, scalable, and future-proof."
  5. (Per `[chatgpt]`) "Creative, smart, and funny."
- **Location and register.** Universal. Strongest in branding copy, executive summaries, and AI polished prose where the structure has become a "safe" default.
- **Model attribution.** All families. Claude and GPT both dense. Less common in Llama per `[gemini]`.
- **Time evolution.** Stable across model generations.
- **Sources.** v3.1.0 criterion 8; `[cross-validated:manus-ai+perplexity+chatgpt]`.
- **Signal strength.** MEDIUM.
- **Base rate.** High in unedited AI output for list-prompts (estimated 80 to 95 percent of "list three..." prompts produce exactly three regardless of natural fit).
- **Causal hypothesis (ranked).** Primary: training-data prevalence (the rule of three is the most common list-cardinality in human writing). Secondary: RLHF reward modeling that scores tidy triadic structure higher. Tertiary: tokenizer effects (three-item lists are concise and complete-feeling).
- **Detection difficulty.** Medium. Pattern requires noticing consistent triadic structure across multiple sentences and paragraphs, not just one occurrence.
- **False positive risk.** Moderate. The rule of three is a legitimate human rhetorical device. The discriminator is mechanical application (every list is three, every adjective set is three).
- **Fix or remediation.** Vary list lengths. Sometimes two items are enough; sometimes four or five are warranted. Let content dictate structure, not formula.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-LT-009: Vague Evidential Passive Voice

- **Description.** Overreliance on passive constructions that indirectly attribute claims to unnamed authorities, particularly the "[Subject] has been described as," "[Subject] is widely regarded as," "[Subject] is considered to be," and "[Subject] has been praised for" family. The v3.1.0 phrasing was "Passive Voice and 'Has Been Described As' Construction"; v4.0 narrows to vague evidential passives per `[chatgpt]`'s REVISE recommendation, because passive voice broadly is too weak a signal. The construction creates an illusion of authority without providing attribution. Cross-references A3-CS-002 (vague attribution to unnamed authorities) and A1-GEMINI-010 (formal academic register default).
- **Concrete examples.**
  1. "The framework is widely regarded as a foundational contribution to the field."
  2. "The methodology has been described as both rigorous and innovative."
  3. "The leader is considered to be one of the most influential figures of the era."
  4. (Per `[perplexity]`) "The technique is known for its versatility across domains."
  5. (Per `[chatgpt]`) "It has been argued that this approach yields better long-term outcomes."
- **Location and register.** Body paragraphs. Strongest in encyclopedic, profile, and review writing. Per Perplexity: more characteristic of Gemini and formal-register outputs than Claude 4.
- **Model attribution.** Gemini family (HIGH per `[perplexity]`; cross-link to A1-GEMINI-010 formal academic register default). Claude family (MEDIUM). GPT family (MEDIUM). Llama (LOW per `[gemini]`).
- **Time evolution.** Stable. The construction has been a persistent feature of Wikipedia-style training data, which all major families have ingested.
- **Sources.** v3.1.0 criterion 9; `[perplexity]` for Gemini attribution; `[chatgpt]` for REVISE recommendation to narrow scope.
- **Signal strength.** LOW (revised from broader passive-voice claim). HIGH when paired with A3-CS-002 (vague attribution) in a single passage.
- **Base rate.** Moderate in unedited Gemini and Wikipedia-style output. Lower in Claude and GPT.
- **Causal hypothesis (ranked).** Primary: training-data skew toward encyclopedic and biographical corpora. Secondary: RLHF reward modeling that scores "authoritative-sounding" prose higher. Tertiary: alignment safety tuning that prefers indirect attribution to avoid making the model assert claims directly.
- **Detection difficulty.** Easy. Grep for the formulaic phrasing.
- **False positive risk.** Moderate. Profile writing legitimately uses these constructions; the discriminator is density and absence of named attribution.
- **Fix or remediation.** Use direct statements with specific attribution. "The framework is widely regarded as foundational" becomes "Kahneman and Tversky (1979) named the framework prospect theory; it has been cited in over 70,000 papers."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-LT-010: Uniform Sentence and Paragraph Length

- **Description.** Mechanically consistent structure: sentences cluster within a narrow length band, paragraphs cluster in the 3 to 5 sentence range. Human writing exhibits "burstiness," varying paragraph length deliberately for emphasis, pacing, and breath. Cross-references A1-CLAUDE-008 (uniform paragraph length / low burstiness) and A3-SS-009 (over-consistent paragraph rhythm across genres).
- **Concrete examples.** This is a structural pattern best seen in aggregate, not single examples. Compare an unedited Claude long-form essay (consistent 3 to 5 sentence paragraphs throughout) to a feature in The New Yorker (paragraph lengths varying from 1 sentence for emphasis to 10+ sentences for sustained argument). Per Perplexity: observable over 200+ word samples. GPTZero uses 0.30 burstiness as a strong AI signal threshold.
- **Location and register.** Universal across registers in long-form output. Less visible in short responses where paragraph variation has less room to express.
- **Model attribution.** Claude family (HIGH per `[claude-exec-2026-05-18]` and `[perplexity]`). GPT family (HIGH; GPT-4o slightly more uniform than GPT-5 series). Gemini (MEDIUM). Llama (MEDIUM; varies more than closed-source frontier models).
- **Time evolution.** Stable across versions; reflects underlying generation strategy more than recent training.
- **Sources.** v3.1.0 criterion 10; Liang et al. 2023 (Patterns 2023, arxiv 2304.02819); GPTZero methodology documentation 2023; Pangram Labs 2026. Zaitsu et al. PLoS One 2025 (single-LLM-sourced) suggests Llama 3.1 places separately on MDS dimensions.
- **Signal strength.** HIGH (promoted from MED) for native-English content. MEDIUM for ESL content due to the Liang et al. 2023 ESL false-positive risk. The ESL safe-harbor is essential: low burstiness misclassifies a large fraction of TOEFL-style writing as AI per Liang et al. 2023.
- **Base rate.** Very high in unedited AI long-form (estimated 85 to 95 percent of essays exhibit burstiness below 0.35). Sourati et al. (2025) and Padmakumar and He (2024) document homogenization survey and output diversity loss respectively.
- **Causal hypothesis (ranked).** Primary: tokenizer and architecture effects (autoregressive generation with attention windows that favor moderate-length structures). Secondary: training-data skew toward edited prose where paragraphs tend toward moderate length. Tertiary: RLHF reward modeling that may implicitly reward easy-to-read structure.
- **Detection difficulty.** Medium. Requires looking at the distribution, not a single feature.
- **False positive risk.** HIGH for non-native English writers (Liang et al. 2023). Cornerstone of the ESL safe-harbor requirement in B3 calibration.
- **Fix or remediation.** Deliberately vary paragraph length. Single-sentence paragraphs for emphasis; longer paragraphs when sustaining an argument. Vary sentence length: one very short sentence, then a long one.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-LT-011: Unnatural or Stilted Phrasing Beyond Formal Conjunctions

- **Description.** Use of awkward, overly formal, or grammatically correct but unnatural sentence constructions that do not reflect typical human speech or writing patterns. Distinct from A3-LT-006 (transition words): this is the broader register-mismatch pattern where the model defaults to register-elevated phrasing even when context calls for plainer prose. Per `[manus-ai]`'s A3-NEW-006.
- **Concrete examples.**
  1. (Per `[manus-ai]`) "It is incumbent upon us to endeavor to ascertain the optimal pathway forward."
  2. (Per `[manus-ai]`) "The aforementioned considerations warrant careful deliberation prior to the implementation of said strategy."
  3. (Per `[manus-ai]`) "One must not underestimate the profound implications that may arise from such a confluence of factors."
  4. (Per `[opus-expansion]`) "We shall undertake the requisite analysis to facilitate the determination of an appropriate course of action."
- **Location and register.** Body paragraphs. Strongest when used in casual, conversational, or technical-practical contexts where the register is mismatched.
- **Model attribution.** All families. Most pronounced in Gemini formal-register default (cross-link to A1-GEMINI-010) and in Claude when prompted for formal contexts.
- **Time evolution.** Stable; tied to training-data corpora that include formal academic and legal prose.
- **Sources.** `[manus-ai]`'s A3-NEW-006; Pinker (2014); Strunk and White (2000).
- **Signal strength.** HIGH.
- **Base rate.** Moderate in unedited AI output; high when prompted for formal contexts; high when the model misjudges the register.
- **Causal hypothesis (ranked).** Primary: training-data skew toward formal corpora. Secondary: RLHF reward modeling for "professional" output. Tertiary: helpfulness optimization that defaults to elevated register when uncertain.
- **Detection difficulty.** Medium. Requires reading for register fit.
- **False positive risk.** Moderate. Legal, academic, and policy writing use this register legitimately; the discriminator is whether the context warrants it.
- **Fix or remediation.** Replace with plain alternatives. "It is incumbent upon us to endeavor to ascertain" becomes "We need to find out."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-LT-012: Over-Reliance on Abstract Nouns (Nominalization Cascade)

- **Description.** Excessive use of abstract nouns ("implementation," "optimization," "utilization," "prioritization") instead of more concrete verbs or active constructions, leading to dense and less engaging prose. Merges with v3.1.0 criterion 17's nominalization-cascade aspect (the v3.1.0 criterion 17 also covered title case in headers; v4.0 separates the two concepts into A3-SS-007 for title case and A3-LT-012 for nominalization). Per `[manus-ai]`'s A3-NEW-007 and `[perplexity]`'s REVISE on v3.1.0 criterion 17.
- **Concrete examples.**
  1. (Per `[manus-ai]`) "The implementation of the new strategy led to the optimization of resource utilization."
  2. (Per `[manus-ai]`) "Our objective is the prioritization of customer satisfaction through the enhancement of service delivery."
  3. (Per `[manus-ai]`) "The analysis involved the examination of data for the identification of patterns."
  4. (Per `[opus-expansion]`) "Implementation of the framework necessitates the consideration of multiple factors and the alignment of stakeholder expectations."
- **Location and register.** Body paragraphs. Strongest in corporate, governmental, and consulting prose.
- **Model attribution.** All families. Gemini (HIGH; cross-link to A1-GEMINI-010 formal academic register). Claude (MEDIUM-HIGH). GPT (MEDIUM).
- **Time evolution.** Stable.
- **Sources.** `[manus-ai]`'s A3-NEW-007; `[perplexity]` REVISE on criterion 17; Pinker (2014); Strunk and White (2000).
- **Signal strength.** HIGH.
- **Base rate.** High in unedited AI corporate or formal output.
- **Causal hypothesis (ranked).** Primary: training-data skew toward corporate and policy prose. Secondary: RLHF reward modeling for "professional" output. Tertiary: helpfulness optimization that defaults to abstraction when concrete examples are unclear.
- **Detection difficulty.** Easy. Grep for the "-tion" cluster and similar abstract-noun endings.
- **False positive risk.** Moderate. Some technical and policy writing legitimately uses abstract nouns; the discriminator is the density and whether the abstract nouns could be replaced with concrete verbs without information loss.
- **Fix or remediation.** Replace abstract-noun constructions with active verbs. "Implementation of the new strategy led to optimization of resource utilization" becomes "The new strategy used resources more efficiently."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-LT-013: Redundant Modifiers and Adverbial Overkill

- **Description.** Use of unnecessary adverbs or adjectives that add little to no meaning, often redundantly emphasizing a point already clear from the main verb or noun. Per `[manus-ai]`'s A3-NEW-008.
- **Concrete examples.**
  1. (Per `[manus-ai]`) "He carefully scrutinized the document in detail." ("Scrutinized" already implies carefulness and detail.)
  2. (Per `[manus-ai]`) "The completely unique solution truly revolutionized the industry."
  3. (Per `[manus-ai]`) "She personally oversaw the project herself."
  4. (Per `[opus-expansion]`) "The team thoroughly investigated all the various different options."
- **Location and register.** Body paragraphs. Universal across registers, densest in promotional and analytical prose.
- **Model attribution.** All families. GPT-4o family (HIGH). Claude (MEDIUM-HIGH). Gemini (MEDIUM).
- **Time evolution.** Stable.
- **Sources.** `[manus-ai]`'s A3-NEW-008; Pinker (2014); Strunk and White (2000).
- **Signal strength.** HIGH.
- **Base rate.** Moderate to high in unedited AI output.
- **Causal hypothesis (ranked).** Primary: training-data skew toward overwritten prose. Secondary: RLHF reward modeling that scores "emphatic" prose higher. Tertiary: helpfulness optimization that adds intensifiers to make claims feel more substantial.
- **Detection difficulty.** Medium. Requires noticing redundancy rather than spotting a specific phrase.
- **False positive risk.** Low. Genuinely redundant modifiers are clear once flagged.
- **Fix or remediation.** Remove the redundant modifier. "Carefully scrutinized in detail" becomes "scrutinized."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-LT-014: Orphaned Demonstratives

- **Description.** "This is important," "That said," "These factors," and similar demonstrative constructions used without clear antecedent. The demonstrative does not refer to a specific prior noun phrase but to the general gestalt of the previous text. Per the Claude expansion's A3-NEW-005.
- **Concrete examples.**
  1. "This is important to consider when evaluating the options." (What is "this"?)
  2. "These factors must be weighed carefully." (Which factors?)
  3. "That said, several caveats apply." (To what was just said? What in particular?)
  4. (Per `[opus-expansion]`) "This represents a significant development in the field."
- **Location and register.** Paragraph openers and sentence beginnings. Universal across registers, densest in analytical and policy prose where the writer is summarizing or transitioning.
- **Model attribution.** All families. Per the Claude expansion's analysis: medium-high in Claude, GPT, Gemini.
- **Time evolution.** Stable. Reflects training-data exposure to academic and policy prose where demonstratives are used as cohesive devices, often loosely.
- **Sources.** Claude expansion's A3-NEW-005; `[opus-expansion]`.
- **Signal strength.** MEDIUM. HIGH when clustered with other transitional patterns (A3-LT-006).
- **Base rate.** Moderate.
- **Causal hypothesis (ranked).** Primary: training-data skew toward academic prose. Secondary: RLHF reward modeling that scores prose with explicit cohesive markers higher. Tertiary: tokenizer effects (demonstratives are short and cheap to produce).
- **Detection difficulty.** Medium. Requires checking whether the demonstrative has a specific antecedent.
- **False positive risk.** Moderate. Demonstratives with specific antecedents are normal; the discriminator is the orphaned use.
- **Fix or remediation.** Replace the demonstrative with the specific noun phrase. "These factors" becomes "the latency, cost, and consistency factors." "That said" becomes "Despite the speed improvements, X remains a concern."
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.

---

### A3-LT-015: "In Other Words" Reformulation Loop

- **Description.** Claude (and to a lesser degree other families) restates the same idea immediately using "In other words," "Put differently," or "Stated another way," often adding no new information. The reformulation loop is sibling to A1-CLAUDE-019 and to the over-explanation pattern. Per `[deepseek]`'s A1-CLAUDE-019.
- **Concrete examples.**
  1. (Per `[deepseek]`) "The model exhibits a high degree of sensitivity to input perturbations. In other words, small changes in the input can lead to large changes in the output."
  2. (Per `[deepseek]`) "The policy aims to reduce emissions through market mechanisms. Put differently, it uses cap-and-trade."
  3. (Per `[opus-expansion]`) "The framework is over-determined. Stated another way, it has more constraints than degrees of freedom."
- **Location and register.** Body paragraphs. Strongest in pedagogical and analytical prose.
- **Model attribution.** Claude (frequent per `[deepseek]`); GPT (occasional); Gemini (occasional).
- **Time evolution.** Stable.
- **Sources.** `[deepseek]`'s A1-CLAUDE-019; `[opus-expansion]`.
- **Signal strength.** LOW-MEDIUM. Not a strong differentiator alone.
- **Base rate.** Occasional.
- **Causal hypothesis (ranked).** Primary: over-optimization for clarity. Secondary: academic writing tic in training data.
- **Detection difficulty.** Easy.
- **False positive risk.** Low when the reformulation is redundant; moderate when the reformulation actually clarifies.
- **Fix or remediation.** Delete one version. Keep the more concrete one.
- **Era status.** Active.
- **Zone tag.** BODY-PERSISTENT.


---
