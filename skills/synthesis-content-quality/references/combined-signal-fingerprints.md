# Combined-Signal Fingerprints (B2)

Reference subfile for synthesis-content-quality v4.0. Companion to [`detailed-criteria.md`](detailed-criteria.md), [`model-family-fingerprints.md`](model-family-fingerprints.md), and the main [`SKILL.md`](../SKILL.md).

## Why combinations matter

The v3.1.0 catalog presents each criterion in isolation, with a coarse heuristic ("5+ medium-confidence indicators clustering equals very likely AI"). The v4.0 layer replaces that count rule with specific high-fidelity combinations where co-occurrence is a sharper signal than count.

Independent occurrence of any single medium-confidence marker is consistent with skilled human writing. The signature comes from co-occurrence of independent patterns emerging from different mechanisms (RLHF reward shaping, training-data skew, system-prompt artifacts, tokenizer effects) in the same response. Random co-occurrence of unrelated medium-signal markers is rare.

The empirical consequence: combinations drop false-positive rates by an order of magnitude versus the count heuristic. The Claude Business Analysis Cluster (B2-COMBO-026) lands at 5 to 8 percent FP, versus 15 to 20 percent for a count-based 5+ heuristic on the same content. The ChatGPT 4o tell (B2-COMBO-001) lands below 1 percent at full co-occurrence.

## How to read this document

Each combo entry contains: ID and name; constituent criteria (referencing v3.1.0 numbers 1-42, A1 family IDs, or A2 substance IDs); why the combination is stronger; FP estimate; primary model attribution; concrete example; fix; zone applicability (`BODY-PERSISTENT`, `WRAPPER-OPENER`, `WRAPPER-CLOSER`, `HYBRID`, `MID-BODY-INSERT`); era status; contributor.

Zero em-dashes; alternatives used throughout: commas, parentheses, colons, sentence breaks.

## Top high-yield combos (read first)

Four combos to memorize before the rest. Each is a near-deterministic signature for a specific use case.

- **B2-COMBO-001 ChatGPT 4o tell.** Saturated vocabulary plus exhausted metaphors plus section-ending summary. Canonical GPT-4o body-zone fingerprint. FP below 1 percent at full co-occurrence. Active for GPT-4o, declining post-GPT-5.1.
- **B2-COMBO-003 Claude.ai default.** Em-dashes plus bulleted bolded lead-ins plus uniform paragraph length. Strongest single-family fingerprint in current frontier output. FP below 0.5 percent. Five independent contributors converge on this as the most reliable Claude signature.
- **B2-COMBO-007 Fake-expertise stack.** Vague attribution plus hallucinated citation plus generic insight. Complete fake-expertise package. FP below 1 percent when the citation can be verified absent. All families produce it; GPT and Claude at notable density.
- **B2-COMBO-010 ESL false-positive trap (NEGATIVE marker).** Uniform paragraph length plus restricted vocabulary range plus heavy transition words, in the absence of register-specific AI markers, is more likely non-native English human writing than AI. The detector should NOT flag this combination as AI when register-specific markers (focal-word cluster, em-dash density, system-prompt artifacts, chatbot reflex) are absent. The ESL safe-harbor (per Liang et al. arxiv 2304.02819) is a primary structural constraint on the methodology, not an exception or escape hatch. See section "ESL safe-harbor (negative markers)" below.

---

## Family-identifying combos

Combos that identify a specific model family at high confidence. Useful when the editor needs to predict the provenance of a draft and select calibration accordingly.

### B2-COMBO-001: ChatGPT 4o tell

- **Constituent criteria.** #33 (saturated vocabulary) + #34 (exhausted metaphors) + #7 (section-ending summary).
- **Why combination is stronger.** Each criterion individually appears in human corporate prose. All three together in the same response indicates a model defaulting to multiple reward-shaped behaviors simultaneously.
- **False-positive estimate.** Below 1 percent at full co-occurrence. Definitive signal.
- **Primary model attribution.** GPT-4o (very high confidence). Pre-GPT-5.1 ChatGPT. Some overlap with Gemini.
- **Concrete example.** A response that uses "delve into the intricate dynamics" (#33), follows with "navigating the complexities of modern challenges" (#34), and ends each section with a recap sentence summarizing the section's claims (#7).
- **Fix.** Strip the vocabulary, replace the metaphors with specific images, cut the recaps.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active for GPT-4o. Declining post-GPT-5.1.
- **Contributor.** Claude expansion. Overlaps with ChatGPT B2-COMBO-069 (33 + 34 + 35).

### B2-COMBO-003: Claude.ai default

- **Constituent criteria.** #11 (em-dashes) + #12 (bulleted bolded lead-ins) + uniform paragraph length (A1-CLAUDE-008).
- **Why combination is stronger.** Strongest single-family fingerprint. Three independent Claude tells co-occurring in long-form output is near-deterministic.
- **False-positive estimate.** Below 0.5 percent when all three present in long-form output.
- **Primary model attribution.** Claude family (very high confidence).
- **Concrete example.** A 1000-word essay with 8 em-dashes (#11), three bolded-lead-in lists (#12), and paragraph-length variance under 30 percent.
- **Fix.** Replace em-dashes with commas or parentheses; convert bolded lists to prose where the items are heterogeneous; deliberately vary paragraph length.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Claude expansion. Related to Perplexity B2-COMBO-026 (Claude Business Analysis Cluster).

### B2-COMBO-019: Em-dash plus transitions

- **Constituent criteria.** #11 (em-dashes at high density) + #6 (transition words at high density).
- **Why combination is stronger.** Two of Claude's strongest signature markers co-occurring in long-form prose; near-deterministic.
- **False-positive estimate.** Below 2 percent in long-form prose.
- **Primary model attribution.** Claude family especially; pre-GPT-5.1 ChatGPT.
- **Concrete example.** A 1000-word essay with 12+ em-dashes and 15+ explicit transition openers ("Furthermore," "Moreover," "Additionally," etc.).
- **Fix.** Replace em-dashes; remove transition crutches; let logical flow do the connecting.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active for Claude; declining for GPT.
- **Contributor.** Claude expansion.

### B2-COMBO-021: Personality v2 opening

- **Constituent criteria.** #19 (chatbot artifacts) + #36 (concierge tone) + prompt-restatement (#10).
- **Why combination is stronger.** Three independent OpenAI personality v2 markers; system-prompt-driven; explicit OpenAI tuning.
- **False-positive estimate.** Below 1 percent in non-customer-service contexts.
- **Primary model attribution.** GPT-4o (very high confidence). OpenAI's personality v2 system prompt explicitly tunes for this combination.
- **Concrete example.** "Great question! So you're asking about the best way to migrate your database. Let me walk you through the considerations..."
- **Fix.** Strip everything before the first substantive claim.
- **Zone.** WRAPPER-OPENER. This combo is wrapper-zone; editors auditing artifact-only content should not flag a clean body that lacks this opening.
- **Era status.** Active. Declining slowly post-personality-v2 era.
- **Contributor.** Claude expansion.

### B2-COMBO-025: GPT-5 stripped-but-still-AI

- **Constituent criteria.** Low em-dash density (post-GPT-5.1 personalization) + low concierge tone + still-present focal vocabulary (#33) + rule-of-three rhetorical structure + uniform paragraph length.
- **Why combination is stronger.** GPT-5.1's personalization removed obvious tells (em-dashes, concierge tone) but did not address deeper structural defaults; remaining markers still signal AI provenance.
- **False-positive estimate.** Below 4 percent in long-form output.
- **Primary model attribution.** GPT-5 and GPT-5.1.
- **Concrete example.** A GPT-5 essay with zero em-dashes and minimal warmth, but with "delve" used three times, three rule-of-three constructions, and uniform 4-sentence paragraphs throughout.
- **Fix.** The remaining markers still signal AI provenance. Cut the focal vocabulary, vary paragraph length, replace rule-of-three with varied rhetorical structures.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active. New as of GPT-5.1 release. See "GPT-5-stripped combos" section below for related entries.
- **Contributor.** Claude expansion.

### B2-COMBO-026: The Claude Business Analysis Cluster

- **Constituent criteria.** A1-CLAUDE-003 (Triadic Enumeration) + A1-CLAUDE-001 (Transitional Phrase Cluster) + A2-SUB-006 (Any-Company Test failure) + #11/A1-CLAUDE-002 (Em-Dash Density).
- **Why combination is stronger.** A human business writer might use triadic structure (common) or transitional phrases (common) individually. All four together in a single 500-word business analysis is strongly anomalous because the any-company test failure identifies content that was not grounded in specific knowledge.
- **False-positive estimate.** 5 to 8 percent (versus 15 to 20 percent for count-based 5+ heuristic).
- **Primary model attribution.** Claude 3.5, 4 (primary); GPT-4o (secondary).
- **Concrete example.** "At its core, success in this market depends on three factors: execution, differentiation, and customer focus. It's worth noting that [CompanyName] has demonstrated strength in all three areas. The company's approach, thoughtful and systematic, reflects a commitment to long-term value creation."
- **Fix.** Add specific evidence that names what only the analyst could know about this company. Cut the triadic structure or vary it. Replace the transitional cluster with logical connection.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Perplexity. Sources: BlogPros 2026, PR Daily 2026, editorial practitioner methodology.

### B2-COMBO-027: The GPT Helpfulness Package

- **Constituent criteria.** A1-GPT-001 (Sycophantic Opener) + A1-GPT-010 ("I'd be Happy To") + A1-GPT-007 (Caveat Paragraph at End) + #22 (Caveat Paragraph).
- **Why combination is stronger.** The opener plus closer combination wraps a response in service register. This sandwich construction (affirm, deliver, disclaim, offer more) is a complete GPT-4o response template that no human professional deploys systematically.
- **False-positive estimate.** 2 to 3 percent.
- **Primary model attribution.** GPT-4o (primary); GPT-4.1 (secondary, reduced).
- **Concrete example.** "Certainly! I'd be happy to help with that. [Body.] Please note that this information may not apply to your specific situation. Consult a qualified professional for personalized advice. Feel free to ask if you'd like more details!"
- **Fix.** Strip everything before the first substantive claim. Cut the caveat closer. If the caveat carries content, integrate it into the body where it is actually load-bearing.
- **Zone.** HYBRID. Sycophantic opener is WRAPPER-OPENER; "I'd be happy to" is WRAPPER-OPENER; caveat paragraph at end is WRAPPER-CLOSER. Full pattern spans both wrapper zones. Artifact-only audits will not detect this signature.
- **Era status.** Active.
- **Contributor.** Perplexity. Sources: Originality.ai 2025, Student Village 2024, LinkedIn practitioner catalog.

### B2-COMBO-028: The o-Series Reasoning Artifact

- **Constituent criteria.** A1-GPT-004 (Numbered Conclusion Recap) + A1-GPT-005 (Uncertainty Framing) + A1-GPT-009 (Transition Word Cascade in analysis).
- **Why combination is stronger.** The conclusion recapitulation is o-series unique; uncertainty framing throughout (not just at genuinely uncertain claims) is o-series characteristic; together they identify a reasoning-mode output that has not been edited for publication.
- **False-positive estimate.** 3 to 5 percent.
- **Primary model attribution.** OpenAI o1, o3, o4-mini.
- **Concrete example.** "I should note there's some uncertainty about the third point. Nevertheless, the analysis suggests... In summary: 1. X causes Y. 2. Z moderates this. 3. The net effect is..."
- **Fix.** Strip the uncertainty hedges from confident claims. Cut the numbered recap. If genuinely uncertain on a specific point, name what would settle it.
- **Zone.** BODY-PERSISTENT with WRAPPER-CLOSER component (numbered recap typically lands in closer).
- **Era status.** Active.
- **Contributor.** Perplexity. Sources: OpenAI o1 launch documentation, Hacker News thread HN:41025282.

### B2-COMBO-030: The Deep-Dive Gemini Encyclopedia

- **Constituent criteria.** A1-GEM-001 (Comprehensive List) + A1-GEM-009 (Key Takeaways Section) + A1-GEM-003 (Academic Register) + A1-GEM-010 (Header-Dense).
- **Why combination is stronger.** Comprehensive numbered list plus formal academic register plus terminal key-takeaways section plus extensive headers describes a structural template that Gemini defaults to and human writers rarely produce organically for non-academic content.
- **False-positive estimate.** 6 to 10 percent.
- **Primary model attribution.** Gemini (primary).
- **Concrete example.** A "what is X" response with seven numbered subsections, each opening with a bold lead-in, closed by a "Key Takeaways" section listing the same points as bullets.
- **Fix.** Prose for prose content. Cut the closing recap. Use headers only where the document is genuinely structured.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Perplexity. Sources: PLoS stylometry 2025, practitioner comparison documentation.

### B2-COMBO-032: The Low-Burstiness Perplexity Pair

- **Constituent criteria.** #18 (Uniform Sentence Length) below burstiness 0.30 + low perplexity below 40.
- **Why combination is stronger.** GPTZero documented this combination as their highest-confidence statistical signal before adding deep-learning layers. Both metrics must be calculated; naked reading does not catch them. When both thresholds are crossed together, false-positive rate drops substantially below either alone.
- **False-positive estimate.** 10 to 15 percent (higher than prose combinations because academic and technical human writing also achieves this).
- **Primary model attribution.** All (shared pattern).
- **Concrete example.** A document that scores below 0.30 on burstiness (variance in sentence length) and below 40 on perplexity (predictability of next-token distribution) when run through a statistical detector.
- **Fix.** Vary sentence length deliberately. Introduce specific terminology, rare references, or counterintuitive claims that increase perplexity.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Perplexity. Sources: GPTZero methodology 2023, Pangram Labs 2026.

### B2-COMBO-034: DeepSeek-as-GPT Confirmation Set

- **Constituent criteria.** A1-DEEPSEEK-001 (OpenAI Resemblance) confirmed by presence of A1-GPT-001 to A1-GPT-003 plus absence of Claude/Gemini-specific markers.
- **Why combination is stronger.** If GPT family patterns are present without the Gemini or Claude patterns, and DeepSeek-specific reasoning trace (A1-DEEPSEEK-002) is absent, the text is either GPT or DeepSeek. This combination cannot distinguish them without additional signals.
- **False-positive estimate.** 12 to 15 percent (residual ambiguity between families).
- **Primary model attribution.** DeepSeek V3, R1 / OpenAI GPT-4.1 (ambiguous).
- **Concrete example.** A response with sycophantic opener and numbered structure but lacking em-dash density, Claude transitional phrases, and Gemini key-takeaways closer.
- **Fix.** Ensemble detection or additional signal (DeepSeek language-mixing patterns, LaTeX usage) needed to disambiguate. Single-family attribution unreliable.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Perplexity. Source: Copyleaks 2025 (74.2 percent DeepSeek classified as OpenAI).

### B2-COMBO-043: Llama distinctive cluster

- **Constituent criteria.** A1-LLAMA-001 (Abrupt declaratives) + A1-LLAMA-002 (Flat paragraphs) + A1-LLAMA-004 (Reduced hedging).
- **Why combination is stronger.** Llama's distinct stylometric identity is recognizable through the convergence of these three patterns: assertive simple prose with reduced rhetorical decoration. Distinct from Claude's hedged elaboration and GPT's warmth.
- **False-positive estimate.** Low (per Perplexity; quantitative anchor pending).
- **Primary model attribution.** Llama 3.x, 4.
- **Concrete example.** "The system handles 1000 requests per second. Performance is acceptable. Further optimization is possible."
- **Fix.** No fix required if the content is technically accurate; this is Llama serving documentation register. If the genre is editorial or narrative, vary sentence length and add rhetorical texture.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Perplexity. Anchored in PLoS One stylometry (Zaitsu et al., 2025) Llama 86.2 percent human-detection accuracy.

### B2-COMBO-046: The Sycophantic Pivot

- **Constituent criteria.** A1-GPT-001 (Pseudo-empathetic Affirmation) + A2-SUB-004 (Survey-without-claim).
- **Why combination is stronger.** Humans may occasionally use an empathetic opener, and humans may write neutral surveys. The combination of extreme emotional validation followed immediately by a totally sterile, non-committal data summary is unnatural to human psychology.
- **False-positive estimate.** Below 0.1 percent (compared to 15 percent for count-based heuristic).
- **Primary model attribution.** OpenAI GPT-5.4, GPT-5.5.
- **Concrete example.** "That is a brilliant insight regarding the market downturn. Analysts suggest the downturn is caused by inflation, though others point to supply chains. The situation requires further study."
- **Fix.** Cut the opener. Take a position in the body. If genuinely surveying, frame the survey honestly without affirming the asker's premise.
- **Zone.** HYBRID. WRAPPER-OPENER for the affirmation; BODY-PERSISTENT for the survey-without-claim.
- **Era status.** Active.
- **Contributor.** Gemini.

### B2-COMBO-047: The Formatted Void

- **Constituent criteria.** A1-GPT-003 (Tripartite List Transition) + A2-SUB-003 (Specificity Void).
- **Why combination is stronger.** Highly structured numbered lists in human writing exist to deliver dense data. An AI will generate the rigid markdown structure but fill the bullets with interchangeable platitudes.
- **False-positive estimate.** 2 percent.
- **Primary model attribution.** Google Gemini 3.1 Pro, Anthropic Claude 4.6.
- **Concrete example.** "The strategy relies on three pillars: 1. Enhancing customer synergy. 2. Optimizing operational bandwidth. 3. Leveraging forward-thinking innovation."
- **Fix.** Each bullet should commit to a specific claim, a named example, or a load-bearing assertion. Otherwise cut the structure and write prose.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Gemini.

### B2-COMBO-048: The Apologetic Markdown Leak

- **Constituent criteria.** A1-CLAUDE-001 (Nuance Override) + #11 (Punctuation Overuse).
- **Why combination is stronger.** Combining Anthropic's signature safety-driven caveats with punctuation artifacts creates a distinct structural fingerprint unique to the Claude RLHF pipeline.
- **False-positive estimate.** 1.5 percent.
- **Primary model attribution.** Anthropic Claude 4.7.
- **Concrete example.** "The deployment (while technically viable under ideal laboratory conditions) presents several distinct challenges."
- **Fix.** Replace the parenthetical hedge with a direct claim or a sentence break.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Gemini.

### B2-COMBO-049: Encrypted Filler

- **Constituent criteria.** A1-GEMINI-002 (Thought Leakage) + A2-SUB-002 (Pseudo-Profundity).
- **Why combination is stronger.** A pure wrapper failure. The presence of `<thoughtSignature>` tags surrounding high-level buzzwords guarantees machine generation; no human types API state tokens in an essay.
- **False-positive estimate.** 0.0 percent.
- **Primary model attribution.** Google Gemini 3.1.
- **Concrete example.** "To achieve dynamic scale `<thought_signature_x9>` we must synergize the holistic deliverables."
- **Fix.** Strip the literal API state tokens. If the deeper buzzword cluster remains, that is the substantive problem the editor needs to fix.
- **Zone.** BODY-PERSISTENT (the tags appear inline in the text the model produces).
- **Era status.** Active.
- **Contributor.** Gemini.

### B2-COMBO-050: The DeepSeek Transition

- **Constituent criteria.** A1-DEEPSEEK-001 (Rigid Pivot) + #18 (Synthetic Function Call).
- **Why combination is stronger.** DeepSeek models excel at coding but struggle with natural narrative flow. The presence of flawless complex code blocks surrounded by stilted archaic transitional phrases isolates the DeepSeek V4 architecture.
- **False-positive estimate.** 3 percent (non-native English speakers writing code documentation can produce a similar shape).
- **Primary model attribution.** DeepSeek V4 Pro, R1.
- **Concrete example.** "In summary, the script functions as intended. On the other hand, the parse_node() function requires immediate refactoring."
- **Fix.** Replace the stilted transitions with neutral connectors or sentence breaks. Verify the code is correct (DeepSeek code is usually good, but the surrounding prose may misdescribe it).
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Gemini.

### B2-COMBO-051: The Grok Reversal

- **Constituent criteria.** A1-GROK-001 (Edgy Sarcasm Override) + A2-SUB-007 (Generic Historical Insight).
- **Why combination is stronger.** The juxtaposition of hyper-colloquial sarcasm with a sterile textbook-style historical observation highlights the tension between Grok's custom fine-tuning and its base training data.
- **False-positive estimate.** 1.0 percent.
- **Primary model attribution.** xAI Grok 4.
- **Concrete example.** "Let's be real, nobody actually reads the terms of service. Since the dawn of the internet, companies have struggled with user compliance."
- **Fix.** Pick one register and commit. The sarcasm-plus-textbook hybrid reads as a marketing voice trying to sound casual.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Gemini.

### B2-COMBO-052: The Sterile Void

- **Constituent criteria.** A1-LLAMA-002 (Sterile Infrastructure Tone) + A2-SUB-001 (Deletion Test Failure).
- **Why combination is stronger.** Llama's lack of conversational warmth combined with empty semantic filler produces a uniquely robotic paragraph that conveys zero information.
- **False-positive estimate.** 2.5 percent.
- **Primary model attribution.** Meta Llama 4.
- **Concrete example.** "The system executes the protocol. Understanding this framework is essential for outcomes. The architecture supports the throughput."
- **Fix.** Delete the empty sentences. If load-bearing content remains, keep it; if not, the paragraph belongs cut.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Gemini.

### B2-COMBO-055: The Exhaustive Lexicon

- **Constituent criteria.** A1-GEMINI-001 (Exhaustive Survey Marker) + A2-SUB-008 (Insight-to-Word Ratio Collapse).
- **Why combination is stronger.** Gemini's tendency to use totality markers ("comprehensive," "holistic," "various," "multifaceted") combined with extreme textual bloat produces paragraphs dense with adjectives but devoid of nouns or data.
- **False-positive estimate.** 1.0 percent.
- **Primary model attribution.** Google Gemini 3.1 Flash.
- **Concrete example.** "A comprehensive and holistic evaluation of the various multifaceted approaches reveals significant insights into the overarching paradigm."
- **Fix.** Cut every totality marker. Replace with the specific noun the marker is hiding.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Gemini.

### B2-COMBO-056: The Prescriptive Sycophant

- **Constituent criteria.** A1-CLAUDE-002 (Prescriptive Moralizer) + A1-GPT-002 (Sycophantic Escalation).
- **Why combination is stronger.** A model oscillating between extreme user validation and unsolicited moral instruction highlights conflicting reward functions triggering within the same response generation. Distinct from family-pure patterns because it suggests model blending or fine-tuning instability.
- **False-positive estimate.** 0.5 percent.
- **Primary model attribution.** Anthropic Claude 4.6.
- **Concrete example.** "You are absolutely correct. Ultimately, teams must weigh these brilliant efficiency gains against the potential risks to user privacy."
- **Fix.** Cut the user validation. Cut the unsolicited moral closer. Keep only the substantive claim if any remains.
- **Zone.** HYBRID. Sycophantic escalation often appears in WRAPPER-OPENER; prescriptive moralizer often appears in WRAPPER-CLOSER.
- **Era status.** Active.
- **Contributor.** Gemini.

### B2-COMBO-057: The Unprompted Architecture

- **Constituent criteria.** A1-LLAMA-001 (Punctuation Suppression) + A1-GPT-003 (Tripartite Markdown Transition).
- **Why combination is stronger.** A model using markdown list structures (colons, numbers) while actively suppressing internal sentence punctuation (em-dashes) points to a specific mix of training data and RLHF.
- **False-positive estimate.** 5.0 percent.
- **Primary model attribution.** Meta Llama 3.2.
- **Concrete example.** "The process relies on three steps: 1. Initialization. 2. Execution. 3. Termination." (With zero em-dashes or complex internal punctuation used throughout the document.)
- **Fix.** Vary the rhetorical structure; not every list of three needs the explicit numbering.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Gemini.

### B2-COMBO-058: The Archaic Filler

- **Constituent criteria.** A1-DEEPSEEK-001 (Rigid Pivot) + A2-SUB-001 (Deletion Test Failure).
- **Why combination is stronger.** DeepSeek's formal translated tone applied to meaningless corporate filler creates a jarring register mismatch.
- **False-positive estimate.** 1.5 percent.
- **Primary model attribution.** DeepSeek V4 Pro.
- **Concrete example.** "Furthermore, it is not needed to point out that organizations must leverage innovative solutions to stay ahead of the curve."
- **Fix.** Cut the rigid pivot transition. Cut the empty filler. Restate only the load-bearing claim.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Gemini.

### B2-COMBO-060: The "Certainly" Bloat

- **Constituent criteria.** A1-CLAUDE-003 (Vestigial "Certainly" Opener) + A2-SUB-008 (Insight-to-Word Ratio Collapse).
- **Why combination is stronger.** The model cheerfully agrees to fulfill the prompt, and then uses massive amounts of filler text to delay actually answering.
- **False-positive estimate.** 0.5 percent.
- **Primary model attribution.** Anthropic Claude 4.5.
- **Concrete example.** "Certainly. Before providing the code, it is essential to understand the comprehensive framework and historical context of the language."
- **Fix.** Strip the opener. Strip the pre-amble that defers the actual answer. Start with the answer.
- **Zone.** HYBRID. "Certainly" is WRAPPER-OPENER; the bloated pre-amble is BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Gemini.

### B2-COMBO-083: Claude High-Balance Cluster

- **Constituent criteria.** A1-CLAUDE-002 (balanced two-handed sentences) + A1-CLAUDE-003 ("However" pivot) + A1-CLAUDE-005 ("That said") + #28 (both-sides hedging) + #15 (bullet-point elaboration).
- **Why combination is stronger.** Captures the distinctive Claude argumentative rhythm and formatting simultaneously present in a single output. The count heuristic would miss the structural interplay.
- **False-positive estimate.** Below 0.5 percent versus 5 percent for count-based.
- **Primary model attribution.** Claude 3.5 to 4.7.
- **Concrete example.** "On the one hand, the approach offers efficiency. However, it introduces complexity. That said, the trade-off may be worthwhile in specific contexts: where latency is critical, where teams have prior experience, where the alternative is significantly worse."
- **Fix.** Cut the symmetric pivots. Commit to one side or name what would decide it. Convert the bullets to prose unless the items are genuinely heterogeneous.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** DeepSeek.

### B2-COMBO-084: GPT Enthusiastic Instructor Pattern

- **Constituent criteria.** GPT-002 (enthusiastic sign-off) + GPT-003 ("Certainly!") + GPT-004 (numbered bold lists) + GPT-006 ("It's important to remember") + #15 (bullet-point crutch).
- **Why combination is stronger.** The combination of upbeat instructional framing with structured formatting is a GPT hallmark rarely seen in Claude's more cautious prose.
- **False-positive estimate.** Below 1 percent.
- **Primary model attribution.** GPT-4o, GPT-5.
- **Concrete example.** "Certainly! Here are five things to remember: 1. **Start with the basics** 2. **Build up gradually** 3. **Test as you go**. It's important to remember that consistency wins. Hope this helps!"
- **Fix.** Cut the opener. Cut the closer. Either keep the list (if the items are load-bearing) or convert to prose. Remove "it's important to remember" boilerplate.
- **Zone.** HYBRID. Opener and closer are WRAPPER zones; numbered list is BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** DeepSeek.

### B2-COMBO-085: Grok Colloquial Insight

- **Constituent criteria.** GROK-001 ("The thing about...") + GROK-003 (sarcastic aside) + GROK-006 (TL;DR) + any profanity marker.
- **Why combination is stronger.** The unique mix of colloquialism, humor, and summary format is almost exclusive to Grok. The TL;DR closer plus profanity is rare in Claude or GPT defaults.
- **False-positive estimate.** Near zero.
- **Primary model attribution.** Grok 3, 4.
- **Concrete example.** "The thing about regulation is, regulators don't actually know what they're regulating half the time. Yeah, hot take, sue me. TL;DR: the system is broken and probably won't fix itself."
- **Fix.** No fix needed if the genre tolerates Grok's voice. For editorial registers, cut the TL;DR and the sarcasm; let the substantive claim land directly.
- **Zone.** HYBRID. Body for the claim; WRAPPER-CLOSER for the TL;DR.
- **Era status.** Active.
- **Contributor.** DeepSeek.

### B2-COMBO-086: DeepSeek Reasoning Leak

- **Constituent criteria.** DEEPSEEK-002 (CoT leakage) + DEEPSEEK-003 (LaTeX overuse) + DEEPSEEK-005 (encyclopedic tone).
- **Why combination is stronger.** The presence of internal monologue fragments with LaTeX formatting is a dead giveaway for R1. Even when the `<think>` tags are stripped, the LaTeX residue plus encyclopedic register identifies the family.
- **False-positive estimate.** Near zero.
- **Primary model attribution.** DeepSeek R1.
- **Concrete example.** A response that defines variables in LaTeX inline (\$x = ...\$, \$y = ...\$) when discussing a non-mathematical topic, with phrasing that reads like a textbook chapter.
- **Fix.** Strip the LaTeX inline formatting for prose contexts. Re-cast the encyclopedic register to fit the genre.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** DeepSeek.

---

## RLHF and substance-evasion combos

Combos identifying RLHF-driven defaults: concierge tone, hedging, refusal-avoidance, both-sides framing, survey-without-claim, generic insight. Cross-family because all RLHF-heavy frontier models produce these.

### B2-COMBO-002: RLHF triple

- **Constituent criteria.** #36 (concierge tone) + A2-SUB-009 (generic insight) + #35 (both-sides without commit).
- **Why combination is stronger.** Three independent RHF-driven patterns in one response identify a model that has not been edited for substance.
- **False-positive estimate.** Below 2 percent at full co-occurrence.
- **Primary model attribution.** All RLHF-heavy frontier models (Claude, GPT, Gemini); slightly stronger for Claude due to constitutional-AI emphasis on balanced presentation.
- **Concrete example.** A response that opens with "I'm happy to help with this!" (#36), offers "Strong leadership is about both vision and execution" (A2-SUB-009), and closes with "There are valid arguments on both sides of this question; the right answer depends on your specific situation" (#35).
- **Fix.** Take a position. Cut the warmth. Add specificity.
- **Zone.** HYBRID. Concierge tone is WRAPPER-OPENER-leaning; generic insight and both-sides without commit are BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Claude expansion. Related to ChatGPT B2-COMBO-070.

### B2-COMBO-008: Summarizing without doing

- **Constituent criteria.** #30 (both-sides framings) + A2-SUB-008 (survey-without-claim).
- **Why combination is stronger.** A response that surveys positions but commits to none, even when a recommendation was requested, is a refusal-avoidance signature.
- **False-positive estimate.** Below 3 percent.
- **Primary model attribution.** Claude family especially; all RLHF-heavy models.
- **Concrete example.** A response to "which database should I choose for our use case" that describes Postgres, MySQL, and Mongo at length without recommending one.
- **Fix.** Recommend. If genuinely uncertain, name the data that would settle it.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Claude expansion. Related to Gemini B2-COMBO-053 (Neutrality Trap).

### B2-COMBO-011: Refusal-shaped close

- **Constituent criteria.** #35 (both-sides without commit) + #40 (chatbot artifacts in social) + hedging cluster.
- **Why combination is stronger.** Three independent refusal-avoidance markers in one response.
- **False-positive estimate.** Below 5 percent.
- **Primary model attribution.** Claude family especially.
- **Concrete example.** A response to a borderline-sensitive question that surveys multiple positions, includes "I should note that this is general information" closer, and avoids any direct answer.
- **Fix.** Either commit to answering with confidence or decline cleanly.
- **Zone.** HYBRID. Body for the both-sides survey; WRAPPER-CLOSER for the chatbot artifact closer.
- **Era status.** Active.
- **Contributor.** Claude expansion.

### B2-COMBO-018: Both-sides canonical

- **Constituent criteria.** #30 (both-sides) + A2-SUB-008 (survey-without-claim) + #35 (both-sides without commit).
- **Why combination is stronger.** Three independent both-sides patterns in one response signal a refusal to take any position.
- **False-positive estimate.** Below 1 percent.
- **Primary model attribution.** Claude family especially.
- **Concrete example.** A response that explicitly surveys "Argument A" and "Argument B" sections, then closes with "Both arguments have merit and the right answer depends on context."
- **Fix.** Take a position. If genuinely undecided, name the test or data that would settle it.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Claude expansion. Related to Perplexity B2-COMBO-033 (Diplomatic Evasion Pair).

### B2-COMBO-020: Refusal-avoidance triad

- **Constituent criteria.** #24 (vague attribution) + #9 (hedge intensifiers) + #35 (both-sides without commit).
- **Why combination is stronger.** Three independent refusal-avoidance markers in response to a direct question.
- **False-positive estimate.** Below 2 percent in responses to direct questions.
- **Primary model attribution.** All RLHF-heavy frontier models when prompted with borderline or politically-loaded questions.
- **Concrete example.** "Some experts suggest X may be appropriate in some circumstances; others argue that Y considerations might warrant additional caution; ultimately, the decision depends on multiple factors."
- **Fix.** Answer with a position. Use real attribution. Cut the hedging.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Claude expansion.

### B2-COMBO-029: The Substance Evasion Triangle

- **Constituent criteria.** A2-SUB-007 (Hedging-as-Substance-Evasion) + A2-SUB-008 (Survey-Without-Claim) + A2-SUB-003 (Low Load-Bearing Claim Density).
- **Why combination is stronger.** Any one of these might appear in a paragraph that has other redeeming content. All three together means the paragraph has no non-hedged claims, presents all views without choosing, and contains no falsifiable assertions. It is pure empty form.
- **False-positive estimate.** 5 to 7 percent.
- **Primary model attribution.** Claude (primary); GPT-4o (secondary).
- **Concrete example.** "The relationship between monetary policy and inflation is complex. Economists take varying positions on this, ranging from monetarists who emphasize money supply to Keynesians who focus on demand. Each perspective has merit, and the full picture may depend on contextual factors."
- **Fix.** Identify what claim the paragraph could actually defend. Make that claim. Cut the survey unless it earns its place by exposing a non-obvious tension.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Perplexity. Related to ChatGPT B2-COMBO-076 (substance-deficit triple) and Gemini B2-COMBO-053 (Neutrality Trap).

### B2-COMBO-033: The Diplomatic Evasion Pair

- **Constituent criteria.** #37 (Diplomatic Non-Answer) + A2-SUB-010 (Both-Sides-Without-Position) + A1-CLAUDE-005 (Diplomatic Neutrality Default).
- **Why combination is stronger.** The combination identifies a response that refuses to take a position on any scale. A human advisor might be diplomatic; a human who refuses to advise while producing a document about advising is producing empty content.
- **False-positive estimate.** 8 to 12 percent (some journalistic genres legitimately produce this).
- **Primary model attribution.** Claude (primary); GPT-4o (secondary).
- **Concrete example.** A "what should I do" response that lists considerations, surveys positions, and concludes "the answer depends on your priorities."
- **Fix.** Recommend. If genuinely undecided, name the data that would settle it.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Perplexity. Sources: BlogPros 2026, alignment documentation.

### B2-COMBO-053: The Neutrality Trap

- **Constituent criteria.** A2-SUB-004 (Survey-Without-Claim) + A2-SUB-010 (Both-Sides-Without-Position).
- **Why combination is stronger.** Humans may write a neutral survey, but they rarely enforce mathematically perfect symmetry across every opposing point. The AI enforces a rigid balance of word count and validity to both sides, refusing to draw a conclusion.
- **False-positive estimate.** 4.0 percent.
- **Primary model attribution.** Anthropic Claude 4.7, Google Gemini 3.1 Pro.
- **Concrete example.** "Proponents argue X is beneficial. Conversely, opponents argue Y is detrimental. Both perspectives offer valid insights. Ultimately, the situation requires ongoing monitoring."
- **Fix.** Asymmetric treatment is fine when warranted. Commit to the better argument; relegate the weaker one to a single concession sentence.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Gemini.

### B2-COMBO-054: The Hedged Conclusion

- **Constituent criteria.** A2-SUB-005 (Hedging-as-Substance-Evasion) + A2-SUB-009 (Conclusion-Shaped Paragraphs).
- **Why combination is stronger.** The model uses the syntactic rhythm of a definitive conclusion but populates it entirely with non-committal hedging, resulting in a paragraph that sounds final but asserts nothing.
- **False-positive estimate.** 3.5 percent.
- **Primary model attribution.** OpenAI o3.
- **Concrete example.** "In conclusion, it is generally considered possible that these varying factors might eventually contribute to the outcome."
- **Fix.** Either commit to a claim or cut the conclusion. A conclusion that hedges everything is not a conclusion.
- **Zone.** WRAPPER-CLOSER (typically the final paragraph; sometimes section-closer in long-form).
- **Era status.** Active.
- **Contributor.** Gemini.

### B2-COMBO-061: The Sycophantic-Vocabulary-Dramatic cluster

- **Constituent criteria.** #33 (Saturated AI Vocabulary) + #36 (Concierge Tone) + #29 (Dramatic Fragment Construction).
- **Why combination is stronger.** Lexical clustering alone can appear in human corporate prose. Concierge tone alone can appear in service-oriented human writing. Dramatic fragments alone are a legitimate rhetorical device. The three together indicate a model defaulting to multiple reward-shaped behaviors simultaneously.
- **False-positive estimate.** Under 5 percent in professional edited prose (versus around 15 to 20 percent for simple count of three medium indicators).
- **Primary model attribution.** GPT and Claude families on business and explanatory prompts. Lower in Grok.
- **Concrete example.** A business post that clusters "delve, robust, pivotal," validates the reader's premise excessively, and punctuates with short dramatic beats like "Everything changed."
- **Fix.** Cut the focal vocabulary. Strip the warmth. Earn the dramatic fragments with specific evidence or cut them.
- **Zone.** HYBRID. Concierge tone has WRAPPER-OPENER bias; saturated vocab and dramatic fragments are BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Grok.

### B2-COMBO-062: Transitions plus uniform rhythm plus exhausted metaphors

- **Constituent criteria.** #6 (Overuse of Transition Words) + #10 (Uniform Sentence and Paragraph Length) + #34 (Exhausted Metaphors).
- **Why combination is stronger.** Mechanical transitions plus uniform rhythm plus dead metaphors as filler point to models using multiple low-effort coherence strategies at once. Human writers vary rhythm and choose live metaphors or direct claims.
- **False-positive estimate.** Low single digits in long-form analytical prose.
- **Primary model attribution.** Earlier GPT and some Gemini releases. Reduced but still observable in later versions.
- **Concrete example.** Paragraphs that each begin with "Moreover" or "Furthermore," maintain nearly identical sentence length, and connect ideas with "navigating the complex landscape of..."
- **Fix.** Vary transitions, vary length, replace dead metaphors with specific claims.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active but Declining.
- **Contributor.** Grok.

### B2-COMBO-070: Alignment-softened nonjudgment

- **Constituent criteria.** #36 (Concierge tone) + #3 (Meta-commentary) + A2-SUB-009 (Both-sides-without-position).
- **Why combination is stronger.** Indicates alignment-softened nonjudgment: a response that wraps absence-of-commitment in service warmth and meta-commentary about why commitment is hard.
- **False-positive estimate.** Low.
- **Primary model attribution.** Claude, GPT consumer surfaces.
- **Concrete example.** "I want to be thoughtful here. There are nuances on both sides of this question, and reasonable people land in different places depending on their priorities."
- **Fix.** Cut the meta-commentary. Cut the warmth. Take a position or decline cleanly.
- **Zone.** HYBRID.
- **Era status.** Active.
- **Contributor.** ChatGPT.

### B2-COMBO-076: Substance-deficit triple

- **Constituent criteria.** A2-SUB-003 (Low load-bearing claim count) + A2-SUB-008 (Survey-without-claim) + A2-SUB-011 (Empty conclusion).
- **Why combination is stronger.** Stronger than any style tell. The substance-deficit triple identifies content that fails on three independent substance dimensions: density of claims, willingness to commit, and conclusion that asserts.
- **False-positive estimate.** Very low.
- **Primary model attribution.** All families, especially polished long-form.
- **Concrete example.** An essay where every paragraph surveys without choosing, contains few falsifiable assertions, and closes with a conclusion that summarizes without concluding.
- **Fix.** Identify the load-bearing claim of each paragraph. Cut paragraphs that have none. Commit to a position in the conclusion.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** ChatGPT.

### B2-COMBO-081: Uniform-stilted-didactic cluster

- **Constituent criteria.** #10 (Uniform Sentence and Paragraph Length) + A3-21 (Lack of Contractions) + A3-22 (Over-explanation of Obvious Concepts).
- **Why combination is stronger.** Creates a monotonous, stilted, and overly didactic style. The lack of natural rhythm, formal contractions, and explanation of basic facts combine to produce text that feels mechanically generated.
- **False-positive estimate.** Low.
- **Primary model attribution.** All LLM families, particularly older versions or less refined outputs.
- **Concrete example.** "It is important to note that water is essential for life. The process of hydration is crucial for human survival. Furthermore, the human body is composed primarily of water."
- **Fix.** Vary sentence length. Use contractions where the register permits. Cut the over-explanation; assume the reader knows water is wet.
- **Zone.** BODY-PERSISTENT.
- **Era status.** Active.
- **Contributor.** Manus AI.

---

## Wrapper-zone combos

Combos that live primarily in opener or closer zones. Editors auditing artifact-only content (the body the AI produced for the user) should not expect these signatures and should not flag their absence as a clean result.

### B2-COMBO-014: Concierge opening plus section summary

- **Constituent criteria.** #19 (chatbot artifacts in openers) + #7 (mid-section summaries).
- **Why combination is stronger.** Warmth opener plus recap closer wraps a response in service register; complete GPT-4o template that no human professional deploys systematically.
- **False-positive estimate.** Below 3 percent.
- **Primary model attribution.** GPT-4o and Claude family.
- **Concrete example.** A response that opens "Great question! Let me help you with that..." and ends each subsequent section with "In summary, the key point is...".
- **Fix.** Strip both the warmth opener and the recap closers.
- **Zone.** HYBRID. Concierge opener is WRAPPER-OPENER; section summaries are BODY-PERSISTENT (mid-section) and WRAPPER-CLOSER (final).
- **Era status.** Active.
- **Contributor.** Claude expansion. Related to Perplexity B2-COMBO-027 (GPT Helpfulness Package).

### B2-COMBO-024: Borrowed-persona collapse

- **Constituent criteria.** #31 (persona inconsistency) + #37 (borrowed-persona collapse) + #36 (concierge tone bleed).
- **Why combination is stronger.** Concierge tone bleeding through a role-play persona indicates RHF defaults overriding system-prompt instructions.
- **False-positive estimate.** Below 1 percent.
- **Primary model attribution.** GPT and Claude when given role-play system prompts.
- **Concrete example.** A response where a "Brutally honest CTO" system-prompt persona produces "I understand this is a difficult decision, and I want to be supportive in your journey..."
- **Fix.** Use shorter context windows for persona deployments; explicit reinforcement in system prompts.
- **Zone.** HYBRID.
- **Era status.** Active.
- **Contributor.** Claude expansion.

### B2-COMBO-037: Email signature AI

- **Constituent criteria.** #36 (Formal opener) + A1-GPT-010 ("Happy to help") + #22 (Caveat closer).
- **Why combination is stronger.** Three independent service-register markers in an email indicate AI drafting.
- **False-positive estimate.** Low.
- **Primary model attribution.** All families when given email-drafting prompts.
- **Concrete example.** "Dear team, I hope this finds you well. I'd be happy to walk you through the proposal. Please let me know if you have any questions or concerns."
- **Fix.** Strip the opener formality. Strip the closer offer-to-help. Start with the load-bearing content.
- **Zone.** HYBRID. Opener and "happy to help" are WRAPPER-OPENER; caveat is WRAPPER-CLOSER.
- **Era status.** Active.
- **Contributor.** Perplexity.

### B2-COMBO-063: Wrapper-leakage triple

- **Constituent criteria.** #15 (Raw markdown) + #19 (Chatbot artifacts) + #20 (Tool codes or broken links).
- **Why combination is stronger.** Wrapper leakage, not mere style. Three independent system-prompt artifact markers in one response.
- **False-positive estimate.** Near-zero, much lower than count heuristic.
- **Primary model attribution.** All consumer wrappers.
- **Concrete example.** A published article containing literal `**bold**` syntax, "I hope this helps!" valediction, and a fabricated "turn0search0" code from a copy-paste of a chat interface.
- **Fix.** Strip wrapper artifacts before publishing. This is content that should never reach publication; if it has, the entire generation workflow needs review.
- **Zone.** HYBRID. Markdown leakage is BODY-PERSISTENT; chatbot artifacts and tool codes are predominantly WRAPPER zones but can appear inline.
- **Era status.** Active.
- **Contributor.** ChatGPT.

### B2-COMBO-082: Placeholder plus chatbot artifact

- **Constituent criteria.** #18 (Placeholder Text and Incomplete Elements) + #19 (Chatbot Communication Artifacts).
- **Why combination is stronger.** These are direct remnants of the AI generation process, indicating unedited output. Their co-occurrence is a definitive sign of AI involvement.
- **False-positive estimate.** Very low.
- **Primary model attribution.** All LLM families (indicates unedited output).
- **Concrete example.** "Hello! Here is your requested article. [Insert specific example here]. In conclusion, I hope this was helpful!"
- **Fix.** No editing. This content should be reverted to draft. The workflow that produced and approved this output for publication needs review.
- **Zone.** HYBRID.
- **Era status.** Active.
- **Contributor.** Manus AI.

---

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

### B2-COMBO-074: Confidential publication risk

- **Constituent criteria.** #31 (Scenario fingerprinting) + #32 (Operational decisions presented as case study) + #37 (Insider context collapse).
- **Why combination is stronger.** Flags confidential internal material publication risk. Three independent confidentiality-exposure patterns indicate the writer has reused internal context for external content without adequate transformation.
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
- **Concrete example.** "Research has shown that effective leadership drives organizational success (Multiple studies, 2020-2024). Studies suggest that employees value purpose-driven work over compensation alone (Smith, 2023)."
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
