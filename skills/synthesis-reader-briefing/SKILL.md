---
name: synthesis-reader-briefing
description: "Pre-writing reader briefing methodology for public articles. A required precondition for any article that draws on internal source material (lessons, project context, codebases) and is published to an external audience. Catches insider context collapse before it becomes a draft. Use when asked to: write article, plan article, brief audience, audience analysis, reader briefing, pre-writing, before drafting, who is this for."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Reader Briefing

A pre-writing discipline for public articles. The briefing is a short structured document, written before drafting begins, that establishes who the article is for and what they bring to the page. It is the audit anchor that the rest of the writing process compares against.

This skill is foundation infrastructure. Other writing skills (`synthesis-article-writing`, `synthesis-article-refresh`, the various backdated- and refresh-style skills) treat a committed briefing as a hard precondition: without one, they refuse to proceed.

---

## Why this skill exists

AI-assisted writing has a specific failure mode: when source material (lessons, project context, commit messages, codebases) is loaded into the writing process, the draft inherits the source's framing. The source was written by the writer for the writer. It assumes its reader already has the context. An article written for a stranger has to assume the opposite. Translating between those frames is the actual writing work, and it is the work AI is most likely to skip when given source material to follow.

The result is **insider context collapse** — right vocabulary deployed for an audience that does not share the writer's context. The grammar is clean, the saturated AI vocabulary is absent, the mechanical quality checks pass, and the article is unreadable to the people it is for.

The fix is procedural: a structured briefing before drafting, then an audit pass against the briefing during review. The check has to be procedural because the writer is the insider — the jargon reads as natural prose to the person who wrote it. Reading the draft and trusting your judgment will not catch this.

This skill is also the procedural workaround for the well-known curse-of-knowledge bias in writing: experts cannot easily imagine what it is like to not know what they know. The briefing forces the imagination.

---

## When to apply

- Any public-facing article, blog post, or essay where the reader is not assumed to share the writer's project context.
- Any documentation written for an external audience (open-source contributors, customers, prospective users).
- Any post that draws from internal lessons, project files, commit messages, or codebases as source material. The risk is highest when source material is rich and the writer is AI-assisted.

## When NOT to apply

- Internal documentation written for a specific team that already shares the context. There, the insider language is fast communication, not jargon.
- Personal lesson capture for the writer's own memory. No translation needed; the reader and writer are the same person.
- Source material itself (commit messages, project context, runbooks). These should be written for their actual readers (future-self, teammate, AI agent picking up the thread), which is closer to the writer's frame.

---

## The four core questions (universal)

Every briefing answers these four, in any order, in plain prose. One paragraph per question is enough. No checklists, no fill-in-the-blank — the answers are the briefing.

1. **Who is this for?** Specifically. Not "everyone" or "anyone interested in X." Name the actual reader: a software engineer who has never used your tools? A technical leader evaluating a methodology? A parent who has held a meaningful private moment with their child?

2. **What do they bring to the page?** What knowledge, experience, or expectation does the reader arrive with? General engineering vocabulary? Familiarity with a specific debate? A shared human experience the article can activate without explaining it?

3. **What does this article ask of them?** What attention, prior context, or willingness to follow does the article require? Ten minutes of focused reading? Patience for one new principle and a worked example? A few minutes of attention and the willingness to feel something?

4. **What does the reader leave with?** A new mental model? A felt experience? A sharpened position? A specific tactic they can apply Monday morning? Be concrete — "they understand the topic better" is not an answer.

The four questions are universal across genres. The answers shift dramatically. The structural decisions for the article fall out of the answers, not from a template.

---

## How the answers shift by genre

The briefing is universal. The article structure is genre-dependent and follows from the briefing. Four worked examples, with the structural implication for each.

### Technical / teaching article

Example briefing for a synthesis-coding article on a software pattern:

> **Who:** software engineers and technical leaders who have built something with LLMs but have never used my tools.
>
> **What they bring:** general software-engineering vocabulary, basic LLM familiarity, no prior context with my projects or workflow.
>
> **What this asks:** ten minutes of focused reading; engagement with one new principle plus a worked example.
>
> **What they leave with:** a transferable design pattern they can apply to their own work — specifically, what to do when the producer at one end of a software interface is non-deterministic.

**Structural implication:** universal-frame-first. Anchor the principle in shared engineering vocabulary in paragraph 1, before introducing the tool-specific worked example. The reader needs the anchor before the specifics will land.

### Personal / narrative article

Example briefing for a personal essay on a moment with a child:

> **Who:** anyone who has been a parent, or anyone who has held a private moment in public — a moment seen, briefly, by a stranger.
>
> **What they bring:** shared human experience of love, vulnerability, being seen by someone unexpected. They do not need to know my family or my circumstances.
>
> **What this asks:** a few minutes of attention; willingness to feel something specific.
>
> **What they leave with:** a felt experience that may resonate with a private moment from their own life.

**Structural implication:** scene-first. The reader brings the shared experience; a scene activates that experience directly. No universal frame needed — the specifics are the door, not the obstacle. Unexplained texture (a name, a place, a small inside ritual) is welcome; the emotional arc must be followable, but every reference does not need to be decoded. Over-explanation kills the form.

### Opinion / argument article

Example briefing for a leadership-industry opinion post:

> **Who:** industry peers in a position to act on the topic — CTOs, VPs, decision-makers who have already formed views.
>
> **What they bring:** prior exposure to the debate, opinions of their own, often disagreement with positions like the one I am about to take.
>
> **What this asks:** willingness to consider a position they may disagree with; attention to the reasoning, not just the conclusion.
>
> **What they leave with:** a sharpened position (mine or theirs) and concrete reasoning to defend or attack it.

**Structural implication:** claim-first. State the position explicitly early. Lay out the reasoning with evidence. Engage the strongest counter-arguments on their merits. The reader is not a stranger to the topic; they are a peer who deserves an argument, not an introduction.

### Advisory / strategic article

Example briefing for a synthesis-engineering article on a methodology:

> **Who:** leaders evaluating whether to adopt a methodology — typically CPTOs, CTOs, or senior product leaders.
>
> **What they bring:** real problems they are trying to solve, skepticism of new frameworks, and limited time.
>
> **What this asks:** fifteen minutes of reading; willingness to map the framework onto their own situation.
>
> **What they leave with:** a decision criterion (when this fits, when it does not), not a prescription.

**Structural implication:** problem-first. Open with the situation the reader is in. Introduce the framework as a response. Close with applicability tests so the reader can evaluate fit without buying the whole package.

---

## The audit discipline

The briefing is the audit anchor for the rest of the writing process. Two checks:

**Paragraph-level audit during drafting.** Every paragraph compared against the four answers. Any paragraph that requires knowledge "what they bring" does not include, fails. Any paragraph that does not move the reader toward "what they leave with," fails. The check is not "is this paragraph good?" — it is "does this paragraph work for the reader the briefing describes?"

**Stranger-read pass before commit.** Read the draft as if you have never used the tools, never read the source material, never been in the conversation. Every term that lights up associated context only because YOU have that context flags as a translation gap. The threshold calibrates by genre: for technical articles, every internal abstraction needs introduction; for personal narratives, the emotional arc must be followable, but unexplained texture is allowed.

**Why procedural, not vibes-based.** The writer is the insider. Every internal term, project version, code identifier, and family-vocabulary reference activates context in the writer's head and reads naturally in the draft. Re-reading the draft and trusting your judgment will not catch this. The audit has to compare each paragraph against the briefing, paragraph by paragraph, with the briefing as the external anchor.

---

## The hard precondition

For any public-facing article, the briefing must be written and committed alongside the draft before drafting begins. Skills that depend on this one (`synthesis-article-writing`, `synthesis-article-refresh`, etc.) treat the absence of a briefing as refusal-to-proceed. This is intentional friction: drafting without a briefing is the documented failure mode this skill exists to prevent.

The friction lands in the right place. Writing a four-paragraph briefing is fast — typically under ten minutes. The friction it adds is small; the friction it prevents (a draft that requires structural rewrite because the framing is wrong) is large.

---

## Output format

The briefing is a short markdown document, four paragraphs (one per question), saved as `.briefing.md` in the same directory as the draft.

**Locations:**
- For articles in destination repos: `content/posts/YYYY/MM/DD-slug/.briefing.md` alongside `index.md`.
- For drafts in `ai-knowledge-rajiv/projects/<project>/drafts/`: `<slug>.briefing.md` adjacent to `<slug>.md`.
- The briefing survives the draft-promotion workflow when the draft moves; archived in the project history if the article is dropped.

**Optional addition:** a one-paragraph "structural implication" derived from the four answers, naming the genre and the structural shape (universal-frame-first, scene-first, claim-first, problem-first). This is a check on whether the briefing was specific enough to suggest a structure. If you cannot write the structural implication from the four answers, the answers need to be more specific.

**What the briefing is not:** a fill-in-the-blank template, a checklist, a one-line audience tag. A specific paragraph per question, in plain prose, is the minimum that produces a useful audit anchor.

---

## Related

- [`synthesis-thinking-framework`](../synthesis-thinking-framework/SKILL.md) — the design-thinking mode ("the user is not an abstraction") is what this skill operationalizes. The briefing is the procedural workaround for the curse-of-knowledge bias.
- [`synthesis-content-quality`](../synthesis-content-quality/SKILL.md) — criterion #37 (Insider Context Collapse) detects briefing failures in finished drafts. The briefing prevents; the criterion catches the cases where prevention was skipped.
- [`synthesis-content-framing`](../synthesis-content-framing/SKILL.md) — has an "Audience Declaration" rule about declaring audience IN the article opening. The briefing is the BEFORE-WRITING complement.
- [`synthesis-article-writing`](../synthesis-article-writing/SKILL.md) — depends on this skill; Phase 0 of the article-writing workflow is the briefing.
- [`synthesis-fact-checking`](../synthesis-fact-checking/SKILL.md) — pairs with the article-writing skill's translation-pass re-verification step. After de-jargoning, every concrete claim is re-verified.

Part of the [synthesis writing](https://synthesiswriting.org) craft — the writer writes, the AI assists.
