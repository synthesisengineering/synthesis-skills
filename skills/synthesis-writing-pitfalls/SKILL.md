---
name: synthesis-writing-pitfalls
description: "Catch human-source bad-writing patterns: humble-bragging, credential-stuffing, throat-clearing, caveat overload, reader flattery or condescension, weak sentences, cliché, register mismatch, needless edits. Use when reviewing, editing or self-editing prose, or scanning an archive."
license: CC0-1.0
depends_on: []
metadata:
  author: Rajiv Pant
  version: 2.0.0
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Writing Pitfalls

Universal bad-writing patterns that human authors and editors fall into, independent of AI. This skill is the human-source counterpart to `synthesis-content-quality` (which catches AI-generation patterns) and the negative complement to `synthesis-writing-craft` (which carries positive principles).

## Binding rules

1. **Identify a pattern by its function, not its surface form.** The same words can be a pitfall in one venue and right in another, so calibrate by venue, audience and intent.
2. **The fix is some version of: trust the reader, drop the defense, state the substance plainly.**
3. **Every edit names the defect it repairs** (pattern 23). Keep a strong sentence when a change has no demonstrable gain.
4. **Prose cues do not establish authorship.** Classify the pattern, explain its effect and revise; never turn a style cue into a claim that a human or a model wrote it.
5. **Keep the two root causes apart.** Human-source patterns are fixed here; AI-generation patterns go to `synthesis-content-quality`. Merging them obscures both fixes.
6. **One high-confidence indicator means a craft failure** whoever wrote it; three or more medium ones warrant revision, five or more substantial revision.
7. **Read the families, not just the hits**: a cluster names the underlying problem more clearly than any single indicator.

## Contents

- [references/catalog.md](references/catalog.md): the full text of patterns 1 to 23 with their fixes, and the quick-reference checklist (phrases to grep for, cringe patterns beyond phrases, structural checks). Read it when scanning or editing.
- [references/detailed-pitfalls.md](references/detailed-pitfalls.md): examples, why each pattern fails, fixes and edge cases for all 23. Read it when a case is unclear or when teaching.
- [references/background.md](references/background.md): why this is a separate skill, the core philosophy, how it differs from AI-pattern detection, related skills. Read it when choosing between this skill and its siblings.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.1.0 text now lives.
- When to use, Pattern index, Detection process: below.

## When to Use This Skill

- Reviewing or editing prose for craft failures
- Auditing an existing archive of writing
- Self-editing a draft before publication
- Training writers or editors
- Performing editorial review when AI involvement is unlikely or irrelevant
- Running a comprehensive scan over older or pre-AI content

## Pattern index

Each pattern is tagged with its confidence tier: **[HIGH]** (almost always a pitfall), **[MED]** (often a pitfall but context-dependent), or **[LOW]** (a pitfall only in certain registers). Numbers match the catalog and the detailed reference.

Cringe family:

1. **Humble-bragging** [HIGH]
2. **Credential-stuffing** [HIGH]
3. **Pre-emptive originality defense** [HIGH]
4. **Third-person self-reference in personal writing** [HIGH]
5. **Apologizing-while-bragging** [MED]
6. **Reverse humble-brag** [MED]

Throat-clearing:

7. **Meta-narration** [HIGH]
8. **Long preambles before the actual point** [MED]
9. **"Before I begin..." openings** [HIGH]
10. **Setup-without-payoff** [MED]

Caveat overload:

11. **More hedges than claims** [HIGH]
12. **Defensive parenthetical clusters** [MED]
13. **"Of course there are exceptions" without naming any** [MED]

Reader-relationship missteps:

14. **Reader-flattering postures** [HIGH]
15. **Reader-condescending postures** [HIGH]
16. **"As we all know" and variants** [HIGH]

Sentence-level weakness:

17. **Empty intensifiers** [MED]
18. **Passive-voice misuse** [MED]
19. **Buried lede** [HIGH]
20. **Weak openings** [MED]

Cliché reliance and dead metaphors:

21. **Cliché as substitute for thought** [MED]

Stilted formality:

22. **Register mismatch** [MED]
23. **Unnecessary editorial intervention** [HIGH]

## Detection Process

### Step 1: Scan for High-Confidence Indicators

Check for: pre-emptive originality defenses, third-person self-reference in personal writing, "Before I begin," "As we all know," reader-flattering or reader-condescending postures, buried ledes.

If any are present, the prose almost certainly has a craft failure regardless of who wrote it.

### Step 2: Count Medium-Confidence Indicators

- 3 or more present: revision warranted
- 5 or more present: substantial revision warranted

### Step 3: Assess by Family

- Multiple cringe-family patterns: the writer is performing credibility instead of demonstrating it
- Multiple throat-clearing patterns: the writer has not yet figured out what they are saying
- Multiple caveat-overload patterns: the writer does not believe their own claims
- Multiple reader-relationship missteps: the writer has not figured out who the reader is

The family pattern often points to the underlying problem more clearly than any single indicator.

### Step 4: Calibrate by Venue

A pattern that is a clear pitfall in a personal blog post may be neutral or appropriate in a legal brief, an academic paper, or a corporate memo. Apply the catalog with judgment about register.

---

Part of the [synthesis writing](https://synthesiswriting.org) craft — the writer writes, the AI assists.
