# Article writing: pre-publication critical review

Phase 3 of the workflow: eleven lenses to run on a finished draft before it is published.

Contents:
- Lenses 1 to 3: credibility and positioning, substance density, stranger read (with the translation-pass re-verification sub-step)
- Lenses 4 to 6: insight quality, engagement and shareability, title magnetism
- Lenses 7 to 9: confidentiality and exposure, limitations and honesty, AI slop final pass
- Lenses 10 and 11: lede protection from provenance scaffolding, semantic sibling search after any finding

## Phase 3: Pre-Publication Critical Review

After the draft is complete, review it critically through these lenses before publishing. This phase exists because a draft can be well-written, factually accurate, and still damage the author's reputation or expose information that must stay private.

### 1. Credibility and Positioning

**Does this make the author look like a deeply experienced expert?**

- Read every anecdote from the perspective of a skeptical peer. Does any story position the author as someone who made an avoidable mistake rather than someone who discovered a non-obvious insight?
- Vulnerability is strategic when it demonstrates wisdom earned. It backfires when it reveals carelessness.
- Test: "Would a senior leader in my field read this and think 'that happened because they didn't have basic guardrails'?" If yes, reframe the story to show what was being deliberately tested or explored, or replace it.

### 2. Substance Density

**Is there real, valuable substance in every paragraph?**

- Read each paragraph and ask: what does the reader learn here that they didn't know before? If the answer is "nothing" or "a restatement of the previous point," cut or compress.
- Watch for warm-up paragraphs that delay the insight, setup sentences that state the obvious, and summary paragraphs that repeat what was just said.
- Common offenders: "AI agents are capable of extraordinary work" (everyone knows this), "No component exists in isolation" (textbook truism), "The user is not an abstraction" (platitude preceding a good example that doesn't need it).

### 3. Stranger Read

**Could a reader with no prior context — exactly the reader described in the briefing from Phase 0 — follow this article?**

The check is procedural, not vibes-based. The writer is the insider; the jargon reads as natural prose to the person who wrote it. Re-reading the draft and trusting your judgment will not catch this. The audit has to scan paragraph by paragraph against the briefing.

Specific patterns to flag (calibrated by genre per the briefing — strict for technical/teaching, looser for personal-narrative):

- Tool or project names introduced without inline definition on first use
- Internal abstractions deployed as if known ("the cockpit," "the dashboard's X," "the parser")
- Version numbers in prose (v0.8.3, v2.4.0, "Phase 2 (2026-04-22)")
- Code identifiers in prose without descriptive context (function names, class names, file paths)
- References to internal events that don't parse outside the project ("another session reviewing the code," "the X arc," "my fix arc")
- Internal directory or file paths used as if the reader knows the project layout

For technical/teaching articles: every internal term must be either introduced inline on first use OR replaced with descriptive language. For personal-narrative articles: the emotional arc must be followable, but unexplained texture (a name, a place, a small ritual) is allowed and often desired.

#### Translation-pass re-verification (sub-step)

After any de-jargoning, anonymization, or accessibility pass that replaces precision-bearing terms with vaguer prose, every concrete claim must be re-verified against the source material the de-jargoning replaced. The translation pass introduces its own accuracy hazard:

- "v0.8.0" becomes "the first version" and the sentence may no longer be true (the tool may have had earlier versions; only one feature was new in v0.8.0).
- "the function walks the rendered HTML" softens to "an application-level layer above the parser" and a verifiable claim becomes a possibly-wrong one.
- A specific metric ("94.4% classified correctly") rephrased generally ("most classified correctly") loses information that may have been load-bearing for the argument.

List every term replaced during the translation pass; re-verify each against the source. The Stranger Read lens replaces; this sub-step verifies the replacement is still true. Both are required. See [`synthesis-fact-checking`](../../synthesis-fact-checking/SKILL.md) Section 7.5 for the full protocol.

### 4. Insight Quality

**Does this article contain at least one idea the reader hasn't encountered before?**

- An insight reframes how the reader thinks. It's not a fact, it's a shift in perspective.
- Test: after reading each section, can you articulate a specific new mental model, distinction, or principle the reader now has? If a section only restates established ideas, it needs either a novel angle or a novel example.

### 5. Engagement and Shareability

**Would someone share this because of what's in it, not just because they know the author?**

- Is there a "gem" moment — a sentence or passage so striking that people would screenshot it?
- Are there pull quotes (3-4 blockquoted passages) that work as standalone tweetable insights?
- Does the opening hook signal the article's actual scope? A small-sounding hook for a big-scope article will lose readers who assume the piece is about the small thing.
- Does the article have structural variety? If every section follows the same template (definition → example → another example → non-technical example), readers will start skimming by section 3.

### 6. Title Magnetism

**Would someone click this title in a feed?**

- Descriptive titles are searchable. Provocative titles get clicked. The best titles are both.
- Test: does the title make you curious, or does it just describe the contents? "Five Modes of Reasoning for Human-AI Collaboration" describes. "Five Modes for Thinking Across Boundaries" intrigues slightly more. The ideal title makes the reader think "I want to know what that means."

### 7. Confidentiality and Exposure (CRITICAL)

**Run the full anonymization protocol from the Ethical Storytelling section in [research-and-drafting.md](research-and-drafting.md).**

- For every real example: apply all four tests (outsider, insider, adversary, irony)
- For every "anonymized" example: verify that the scenario itself isn't a fingerprint
- For every operational decision described: ask whether describing it publicly re-creates the risk it was designed to mitigate

### 8. Limitations and Honesty

**Does the article acknowledge where its claims fail?**

- A framework presented without limitations reads as oversold. One paragraph on "when this doesn't apply" builds more credibility than ten paragraphs of advocacy.
- Test: if a smart, skeptical reader asks "but what about...?" — does the article already have an answer?

### 9. AI Slop Final Pass

**Run the [`synthesis-content-quality`](../../synthesis-content-quality/SKILL.md) framework on the final draft.**

- Pay special attention to: hyperbolic subheadings, borrowed canonical examples (jet engine/market, bus route nobody rides), dramatic fragment construction, section-ending summaries.
- Criterion #37 (Insider Context Collapse) catches frame-level slop that the Stranger Read lens may have missed; treat as a backstop, not a substitute.
- Check that pull quotes exist and are placed for visual rhythm across the article's length.

### 10. Lede Protection From Provenance Scaffolding

**Does the article's first meaningful sentence belong to the article, not to its paperwork?**

Provenance notes are legitimate and sometimes required — a whole-article revision note must precede the content it covers, a disclosure note must be visible before the material it governs. The failure mode is letting that scaffolding become the article's opening: the reader's first contact is administrative text instead of the piece's own promise.

- A short standfirst (one or two sentences of the article's actual claim or stake) may earn attention *before* a whole-article note; the note then follows immediately, before the body it covers.
- The note must not be the article's first meaningful sentence when a standfirst can lawfully precede it.
- The valid sequence is: standfirst → provenance note → body. The invalid sequence is: provenance note as de-facto lede.
- Within-article, section-scoped notes attach to their sections, not to the top.

### 11. Semantic Sibling Search After Any Finding

**One confirmed defect is a search obligation, not a closed item.** When review holds an article for a claim-level defect (an unsupported universal, a broadened scope, a misattributed position), search on two axes before the finding is closed:

- **Within the article:** scan the whole artifact for other instances of the same defect class. A repair that resolves the flagged instance while a stronger, load-bearing instance survives in the same article is worse than no repair — it retires the finding without curing the defect.
- **Across the batch or corpus:** scan sibling articles for the same *semantic* claim, not merely the same exact phrase. Two articles independently asserting the same unsupported universal are one claim family; the first finding reopens the family everywhere it appears.
