# Combined-Signal Fingerprints (B2), part 1 of 2

Part 1 of the file split from [combined-signal-fingerprints.md](combined-signal-fingerprints.md), which keeps the opening sections and lists every part. The text below is unchanged.

Contents:
- Family-identifying combos (28 combos: B2-COMBO 001, 003, 019, 021, 025, 026, 027, 028, 030, 032, 034, 043, 046, 047, 048, 049, 050, 051, 052, 055, 056, 057, 058, 060, 083, 084, 085, 086)
- RLHF and substance-evasion combos (14 combos: B2-COMBO 002, 008, 011, 018, 020, 029, 033, 053, 054, 061, 062, 070, 076, 081)
- Wrapper-zone combos (5 combos: B2-COMBO 014, 024, 037, 063, 082)

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
