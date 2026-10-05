---
name: synthesis-reader-briefing
description: "Pre-writing reader briefing, required before drafting a public article that draws on internal source material. Catches insider context collapse and declares series dependency. Use to write or plan an article, brief the audience, do pre-writing, ask who this is for, or settle a prerequisite."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Reader Briefing

A pre-writing discipline for public articles. The briefing is a short structured document, written before drafting begins, that establishes who the article is for and what they bring to the page. It is the audit anchor that the rest of the writing process compares against.

This skill is foundation infrastructure. Other writing skills (`synthesis-article-writing`, `synthesis-article-refresh`, the various backdated- and refresh-style skills) treat a committed briefing as a hard precondition: without one, they refuse to proceed.

## Binding rules

1. **No public article draft without a committed briefing.** Write `.briefing.md` beside the draft and commit it before drafting; dependent skills refuse to proceed without one, because drafting without it is the failure this skill prevents.
2. **Answer the four questions specifically, in plain prose,** one paragraph each. "Everyone" or "they understand the topic better" is not an answer.
3. **Let the answers set the structure,** not a template: the genre's shape (universal-frame-first, scene-first, claim-first, problem-first) follows from them.
4. **Declare series dependency as exactly one state:** `standalone`, `standalone after compact context`, or `true prerequisite`. A true prerequisite needs a link and a one-sentence reason; no article owes a cross-link quota.
5. **Audit each paragraph against the briefing while drafting, and read as a stranger before commit.** The writer is the insider, so judgment by feel will not catch insider context collapse.

## Contents

- [references/genres.md](references/genres.md): four worked briefings (technical, personal, opinion, advisory) and the structure each implies. Read when writing a briefing or choosing the article's shape.
- [references/series-dependency.md](references/series-dependency.md): the five fields and three states of the series-dependency contract, and what it deliberately does not require. Read when the article belongs, or might belong, to a body of related work.
- [references/audit-and-precondition.md](references/audit-and-precondition.md): the paragraph-level audit, the stranger-read pass, and the hard precondition with its rationale. Read while drafting and before committing.
- [references/background.md](references/background.md): why the skill exists (insider context collapse, the curse of knowledge) and related skills. Read once, or when choosing between this skill and a sibling.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.1.0 text now lives (ruling D8).
- When to apply, When NOT to apply, The four core questions, Output format: below. Whether the skill applies, the briefing itself, and where to save it.

## When to apply

- Any public-facing article, blog post, or essay where the reader is not assumed to share the writer's project context.
- Any documentation written for an external audience (open-source contributors, customers, prospective users).
- Any post that draws from internal lessons, project files, commit messages, or codebases as source material. The risk is highest when source material is rich and the writer is AI-assisted.

## When NOT to apply

- Internal documentation written for a specific team that already shares the context. There, the insider language is fast communication, not jargon.
- Personal lesson capture for the writer's own memory. No translation needed; the reader and writer are the same person.
- Source material itself (commit messages, project context, runbooks). These should be written for their actual readers (future-self, teammate, AI agent picking up the thread), which is closer to the writer's frame.

## The four core questions (universal)

Every briefing answers these four, in any order, in plain prose. One paragraph per question is enough. No checklists, no fill-in-the-blank — the answers are the briefing.

1. **Who is this for?** Specifically. Not "everyone" or "anyone interested in X." Name the actual reader: a software engineer who has never used your tools? A technical leader evaluating a methodology? A parent who has held a meaningful private moment with their child?

2. **What do they bring to the page?** What knowledge, experience, or expectation does the reader arrive with? General engineering vocabulary? Familiarity with a specific debate? A shared human experience the article can activate without explaining it?

3. **What does this article ask of them?** What attention, prior context, or willingness to follow does the article require? Ten minutes of focused reading? Patience for one new principle and a worked example? A few minutes of attention and the willingness to feel something?

4. **What does the reader leave with?** A new mental model? A felt experience? A sharpened position? A specific tactic they can apply Monday morning? Be concrete — "they understand the topic better" is not an answer.

The four questions are universal across genres. The answers shift dramatically. The structural decisions for the article fall out of the answers, not from a template.

## Output format

The briefing is a short markdown document, four paragraphs (one per question), saved as `.briefing.md` in the same directory as the draft.

**Locations:**
- For articles in destination repos: `content/posts/YYYY/MM/DD-slug/.briefing.md` alongside `index.md`.
- For drafts in `<your knowledge repo>/projects/<project>/drafts/`: `<slug>.briefing.md` adjacent to `<slug>.md`.
- The briefing survives the draft-promotion workflow when the draft moves; archived in the project history if the article is dropped.

**Optional addition:** a one-paragraph "structural implication" derived from the four answers, naming the genre and the structural shape (universal-frame-first, scene-first, claim-first, problem-first). This is a check on whether the briefing was specific enough to suggest a structure. If you cannot write the structural implication from the four answers, the answers need to be more specific.

**What the briefing is not:** a fill-in-the-blank template, a checklist, a one-line audience tag. A specific paragraph per question, in plain prose, is the minimum that produces a useful audit anchor.
