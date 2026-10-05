# Writing pitfalls: the pattern catalog

The full text of the 23 patterns, then the quick-reference checklist used when scanning.

Contents:
- The Pattern Catalog: cringe family (1 to 6), throat-clearing (7 to 10), caveat overload (11 to 13), reader-relationship missteps (14 to 16), sentence-level weakness (17 to 20), cliché reliance (21), stilted formality (22 and 23)
- Quick-Reference Checklist: high-risk phrases to grep for, cringe patterns beyond phrases, structural checks

## The Pattern Catalog

Each pattern is tagged with its confidence tier: **[HIGH]** (almost always a pitfall), **[MED]** (often a pitfall but context-dependent), or **[LOW]** (a pitfall only in certain registers).

### Cringe family

1. **Humble-bragging** [HIGH] — Self-praise wrapped in modesty: "I'm not very good at speaking but I keep getting invited to keynote..." Fix: state the substance directly or omit the framing entirely. Trust the reader to evaluate.

2. **Credential-stuffing** [HIGH] — Listing roles, awards, or titles inside the body of personal writing where they don't serve the argument: "As someone who has worked at Programmer, Manager, Regional Director, Vice President levels..." Fix: let the analysis demonstrate authority. The byline carries credentials; the body should not repeat them.

3. **Pre-emptive originality defense** [HIGH] — Disclaiming claims nobody made: "I do not claim these ideas as original." Fix: omit. Confident writers do not preempt plagiarism charges nobody filed. The disclaimer signals insecurity, not intellectual humility.

4. **Third-person self-reference in personal writing** [HIGH] — Switching to third person in personal essays or blog posts: "the author has been..." in a piece otherwise written in first person. Fix: stay in first person throughout. Third-person self-reference is appropriate in academic CVs and bio blocks; never in personal essays.

5. **Apologizing-while-bragging** [MED] — Combining a brag and an apology in one move: "I apologize for the length, but I had to cover all twelve speaking engagements." Fix: cut both halves. Either the substance justifies the length (no apology needed) or it does not (cut the substance).

6. **Reverse humble-brag** [MED] — Publicly downplaying achievements in a way that highlights them: "I was just lucky to be invited to speak at Davos." Fix: state the fact plainly or omit. Either "I spoke at Davos" or skip it.

### Throat-clearing

7. **Meta-narration** [HIGH] — Telling the reader what the article will do instead of doing it: "In this article I will discuss..." or "First I will examine X, then Y, then Z." Fix: just do it. The reader figures out structure from the structure itself.

8. **Long preambles before the actual point** [MED] — Multiple paragraphs of context before the lede. Fix: open with the point. Context can come after if needed, or in inline asides.

9. **"Before I begin..." openings** [HIGH] — Any preamble that delays the start: "Before I begin, let me say a word about..." Fix: cut. The article begins when the reader starts reading.

10. **Setup-without-payoff** [MED] — Building elaborate framing for an insight that does not justify the buildup. Fix: match setup intensity to insight weight. If the insight is small, the setup should be smaller — or the insight needs to be reworked into something that earns the buildup.

### Caveat overload

11. **More hedges than claims** [HIGH] — Every assertion qualified to the point of dissolution: "It might be that, in some cases, perhaps, X could possibly Y." Fix: state the claim. Add ONE precision qualifier if needed. More than one usually means the claim is not ready to make.

12. **Defensive parenthetical clusters** [MED] — Multiple parenthetical insertions defending against possible objections inside a single sentence. Fix: address objections in their own sentences if they matter, or trust the reader to raise them.

13. **"Of course there are exceptions" without naming any** [MED] — Generic acknowledgment of complexity that does no work. Fix: either name the exceptions (specific) or omit (let the simple claim stand and accept minor edge cases).

### Reader-relationship missteps

14. **Reader-flattering postures** [HIGH] — Pre-emptive flattery of the reader: "As intelligent readers like you no doubt know..." or "Anyone smart enough to be reading this..." Fix: omit. Flattery weakens both writer and reader.

15. **Reader-condescending postures** [HIGH] — Pre-emptive talking-down: "Allow me to explain to those unfamiliar..." or "For those who don't know..." Fix: just explain or assume baseline knowledge appropriate to the venue.

16. **"As we all know" and variants** [HIGH] — "As we all know," "needless to say," "it goes without saying" (yet you are saying it). Fix: cut. If everyone knows, omit. If not everyone knows, just state it.

### Sentence-level weakness

17. **Empty intensifiers** [MED] — Adverbs that do not add information: very, really, actually, literally (when not literal), basically, essentially. Fix: cut. If "X is true" needs "really" to land, the X needs to be stronger, not the adverb.

18. **Passive-voice misuse** [MED] — Passive where active is clearer and the actor matters. Fix: use active voice when the actor matters. Passive is appropriate when the actor is unknown, unimportant, or deliberately suppressed (e.g., "mistakes were made" is sometimes the precise frame).

19. **Buried lede** [HIGH] — The most important point comes after several paragraphs of buildup. Fix: move the lede up. Reader attention is highest at the start.

20. **Weak openings** [MED] — Opening with "I," "There is," "There are," or a long throat-clearing sentence. Fix: open with something concrete. A specific image, claim, or scene.

### Cliché reliance and dead metaphors

21. **Cliché as substitute for thought** [MED] — Familiar phrases that have stopped meaning anything specific: "at the end of the day," "moving the needle," "low-hanging fruit," "thinking outside the box," "a perfect storm," "moving forward," "circle back," "boil the ocean," "drink from the firehose." Fix: state the underlying claim in original language. Cliché is the writer's brain on autopilot.

This is distinct from the AI-typical "exhausted metaphor" pattern (covered in `synthesis-content-quality` v4.0 as A3-BT-002) — that pattern catches mechanical recombination of training-set phrases like "navigating the complex landscape of." Human cliché reliance is laziness; AI exhausted metaphor is statistical artifact. Different root causes; both pollute prose.

### Stilted formality

22. **Register mismatch** [MED] — Writing in a register that does not fit the venue: corporate-formal in a personal essay, academic in a popular piece, breezy in a serious analysis. Fix: pick the register that matches audience and venue. Personal essays use first person and contractions. Popular technical writing uses active voice and concrete examples. Read a few exemplars in the target venue if unsure.

**Article register in a social media post** is the dominant modern variant of this pitfall, and its symptoms are now common enough to be cataloged separately. They include: third-person narration of first-person experience ("the site" / "the audit" / "the fix" where it should be "my site" / "my audit" / "my fix"); formal severity labels imported from source material (CRITICAL / HIGH / MEDIUM in a conversational post); essay structure markers ("first", "second", "the principle", "the takeaway", "in summary"); no first-person pronouns in posts about the author's own work; no closing engagement; sentences over 25 words without compression; over-smoothed prose with no rhythmic variation. The same writer's voice should sound different in articles vs social posts — same person, different mode. See [`synthesis-content-quality`](../../synthesis-content-quality/SKILL.md) criteria 38-41 for the AI-detectable variants and [`synthesis-content-distribution`](../../synthesis-content-distribution/SKILL.md) "Social register vs article register" for the rationale and the expectation gap that drives the failure.

The current canonical social-register locators are A3-SR-001 through A3-SR-005. The older criteria 38-41 wording above remains as a historical locator for readers of earlier versions.

23. **Unnecessary editorial intervention** [HIGH] — Editing that makes accurate, purposeful prose longer, more generic, more symmetrical, or less recognizably the writer's own without correcting a concrete problem. Fix: require every edit to name the defect it repairs. Preserve a strong sentence when the proposed change has no demonstrable gain.

For deeper examples and fix guidance on each pattern, see [`references/detailed-pitfalls.md`](detailed-pitfalls.md).

## Quick-Reference Checklist

### High-Risk Phrases to Grep For

- "I do not claim these ideas as original"
- "the author has" (in first-person writing)
- "Before I begin," "Allow me to begin"
- "As we all know," "needless to say," "it goes without saying"
- "In this article I will," "In this post I will"
- "Of course there are exceptions" (without specifics following)
- "As intelligent readers like you," "for those unfamiliar"
- "I'm not very good at X but..."
- "I apologize for the length"
- "very," "really," "actually," "literally," "basically," "essentially" (audit cluster usage)

### Cringe Patterns Beyond Phrases

- Title or credential listing inside body text of personal writing
- Switch from first person to third person mid-piece
- Closing parenthetical disclaimers about authorship or originality
- Public modesty about widely-known achievements

### Structural Checks

- [ ] Lede appears in the first paragraph (not the third)
- [ ] No meta-narration of the article's structure
- [ ] No "before we begin" preambles
- [ ] Hedges and qualifiers are sparing, not constant
- [ ] Reader is treated as an adult (neither flattered nor talked down to)
- [ ] Register matches the venue
- [ ] No clichés substituting for original phrasing
