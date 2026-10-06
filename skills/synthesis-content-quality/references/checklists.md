# Content quality: revision passes and quick checklists

The five revision passes for creators using AI assistance, and the quick-reference checklists for a fast review or a pre-publication pass. Moved verbatim from SKILL.md 4.2.0.

Contents:
- Systematic Revision Process for Creators: five passes.
- Quick-Reference Checklist: high-risk phrases, high-risk vocabulary, exhausted metaphor phrases, high-risk subheading patterns, highest-yield combined signals per family, the A2 substance quick-check, stranger-read patterns, anonymization checks, the ESL safe-harbor check, and the Human Touch test.

## Systematic Revision Process for Creators

When using AI to assist content creation, revise through these five passes:

1. **Eliminate formulaic patterns.** Vary sentence and paragraph length. Reduce mechanical rule of three. Remove promotional language and editorial commentary. Replace generic descriptions with specifics. Cut wrapper-zone language (sycophantic openers, concierge closers) if it leaked into the artifact.

2. **Apply the A2 substance tests.** Run the deletion test on every paragraph: if removing it changes nothing, delete it. Apply the any-company test to business content. Count load-bearing claims; aim for 3+ per 100 words in substantive prose.

3. **Verify and enhance sourcing.** Check all citations exist and are relevant (use synthesis-fact-checking C1-URLROT-001 and C1-SYNTH-001 protocols). Add specific attribution. Include original research or first-hand sources.

4. **Inject personality and voice.** Use natural transitions. Vary rhetorical structures. Include humor or perspective where appropriate. Let imperfections remain if they sound natural. Apply zone awareness: strip wrapper-zone patterns ("You're absolutely right", "I hope this helps") even if they read warmly.

5. **Apply the Human Touch test.** Would a reader recognize this as distinctly yours? Does it include knowledge only you would have? Does it sound like how you actually write? Would anyone else write it exactly this way? Have you added genuine value beyond what AI provided?

## Quick-Reference Checklist

### High-Risk Phrases (any context)

- "stands as a testament to," "plays a vital/significant role"
- "rich cultural heritage," "breathtaking," "nestled in the heart of"
- "it's important to note," "it is worth mentioning," "one cannot overlook"
- "not only... but also," "it's not just X, it's Y"
- "Moreover," "Furthermore," "Additionally," "Nevertheless" (especially in clusters)
- "In summary," "In conclusion," "Overall," "In essence"

### High-Risk Vocabulary (flag when 3+ cluster in a single piece)

- delve, tapestry, nuanced, robust, foster, beacon, catalyst
- synergy, pivotal, overarching, multifaceted, landscape (abstract)
- leverage (verb), streamline, spearhead, underscore, harness
- intricate, navigate the complexities of, in the realm of

### Exhausted Metaphor Phrases

- "navigating the complex landscape of..."
- "viewed through the lens of..."
- "a symphony of moving parts"
- "at the intersection of X and Y"
- "the fabric of..." / "a tapestry of..."
- "unpacking the layers of..."
- "Ultimately, finding a balance between X and Y is crucial"

### High-Risk Subheading Patterns

- "The X that changed everything"
- "A game-changing approach to..."
- "The revolutionary/transformative..."
- "Why X will never be the same"
- "The surprising truth about..."
- "What nobody tells you about..."

### Highest-Yield Combined Signals (per family)

When seen together, these combinations indicate the named family with low false-positive rate:

- **Claude family:** em-dash density + bolded lead-ins + uniform paragraphs (B2-COMBO-003).
- **GPT-4o:** saturated vocab + exhausted metaphor + section-ending summary (B2-COMBO-001).
- **Gemini:** plain-text markdown leakage + vague attribution + "cool/neat/unique" register (B2-COMBO-012 plus GEMINI signatures).
- **GPT-5.1 stripped:** zero em-dashes + low concierge tone + still-present focal vocabulary + rule-of-three + uniform paragraphs (B2-COMBO-025).

### A2 Substance Quick-Check (5 minutes)

Run on three sample paragraphs from any piece:

- [ ] **Deletion test** (`A2-SUB-001`): could this paragraph be removed without losing claim, evidence, or transition?
- [ ] **Specificity test** (`A2-SUB-002`): would this sentence apply equally to any subject in its genre?
- [ ] **Any-company test** (`A2-SUB-006`): if this is business content, would this paragraph apply equally to any company?
- [ ] **Load-bearing claim count** (`A2-SUB-003`): how many sentences carry claims the rest of the piece depends on?
- [ ] **Pseudo-profundity check** (`A2-SUB-011`): does any sentence sound deep but say nothing on inspection?

### Stranger-Read Patterns (Before Publishing)

Threshold calibrates by genre per the reader briefing: strict for technical or teaching content, looser for personal narrative.

- [ ] Tool or project name appears without inline definition on first use
- [ ] Internal abstraction used without prior introduction
- [ ] Version number appears in prose
- [ ] Code identifier in prose without descriptive context
- [ ] Reference to internal events without explanation
- [ ] Internal directory or path used as if reader knows the project layout

See criterion `A3-FA-001` (insider context collapse) and [`synthesis-reader-briefing`](../../synthesis-reader-briefing/SKILL.md).

### Anonymization Checks (Before Publishing)

- [ ] Outsider test: could a stranger narrow this to a small set of companies?
- [ ] Insider test: does this confirm something an insider suspected?
- [ ] Adversary test: could a reporter use this as evidence?
- [ ] Irony test: does publishing this undermine what the example describes protecting?
- [ ] Are specific numbers (14 components, 6 engineers) identifying?
- [ ] Are stakeholder dynamics identifying?
- [ ] Are vocabulary choices (exact terminology changes) identifying?

### ESL Safe-Harbor Check

Before flagging a piece as AI-generated based on uniform-paragraphs + restricted-vocab + heavy-transitions, verify at least one of these register-specific AI markers is also present:

- [ ] Saturated AI vocabulary cluster (3+ from the focal-word list)
- [ ] Em-dash density (per-family calibrated)
- [ ] System-prompt artifact bleed
- [ ] Chatbot reflex (sycophancy opener, concierge closer)
- [ ] Hallucinated citation or fabricated DOI

If none, the piece is likely non-native English human writing. Do not flag.

Also test against known-human strong and weak prose, dialect, translated and multilingual prose, accessibility-oriented plain language, formulaic professional genres, and mixed human/model editing. Do not manufacture errors or irregularity to make writing seem human.

### The Human Touch Test

Before publishing AI-assisted content:

1. Would a reader recognize this as distinctly mine?
2. Does it include knowledge only I would have?
3. Does it sound like how I actually write?
4. Would anyone else write it exactly this way?
5. Have I added genuine value beyond what AI provided?

If you cannot answer yes to most of these, revise further.
