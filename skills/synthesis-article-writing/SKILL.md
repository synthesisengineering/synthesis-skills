---
name: synthesis-article-writing
description: "Write and review thought leadership articles and blog posts: reader briefing, research, drafting, critical review, and publication-package review (title-only stranger test, title/description/body truth contract, batch headline budgets, slug closure). Use for headline or publication-readiness review."
license: "CC0-1.0"
depends_on: ["synthesis-reader-briefing", "synthesis-content-quality"]
metadata:
  author: "Rajiv Pant"
  version: "3.0.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Article Writing

A five-phase workflow for creating high-quality thought leadership articles: reader briefing, research/validation, strategic writing, pre-publication critical review, and publication-package review. Use when exploring a book, concept, or trend and connecting it to your expertise.

## Binding rules

1. **No briefing, no draft.** Write the four-paragraph reader briefing as `.briefing.md` beside the draft before any research or drafting (Phase 0).
2. **Article-level work loads the whole stack** in the load-with contract below; a prose-only review clears bodies while their titles fail.
3. **Cite everything and draft only from verified research.** Rate each item's confidence, use only Verified and Likely accurate items, and ask rather than invent.
4. **Name removal is not anonymization.** Every real example must pass the outsider, insider, adversary and irony tests; one failure rules it out.
5. **Never** attribute unverified quotes to real people, invent technical achievements, or create scenarios inconsistent with the author's public record. These are fabrication bans, not identifiability tests.
6. **Write alt text when you place an image**, after viewing it; never infer its content from the filename, since a file named for a person may be a letter they wrote.
7. **No inline author bio** on a site whose layout renders one; it would duplicate the layout's single source of truth.
8. **Run all eleven Phase 3 lenses before publishing.** After any de-jargoning pass, re-verify every replaced term against its source.
9. **One confirmed defect is a search obligation:** look for the same defect across the article and the batch before closing it.
10. **Title-only stranger test for every article:** record subject, stake, specificity and jargon debt before reading the description or body. A description cannot repair a failed title; without a per-article title table, no readiness sign-off.
11. **Title, description, lede, headings and body must make the same claim.** A broadened title or heading fails even when every sentence is accurate.
12. **State each article's reader value in one sentence.** "No slop markers" is negative evidence and does not establish value.
13. **A new final title on an unpublished article reopens its slug and metadata** until every surface closes together; a clean build does not prove the routes are right.
14. **Measure replacement titles on the same axes as the diagnosis**, so a cure cannot push a different formula over budget.

## Contents

- [references/research-and-drafting.md](references/research-and-drafting.md): Phase 1 (research principles, confidence levels, deliverables, output format) and Phase 2 (writing principles, content architecture, voice, hyperlinks, alt text, ethical storytelling and anonymization, output deliverables, author bios, success criteria). Read it before researching or drafting.
- [references/draft-review.md](references/draft-review.md): Phase 3, the eleven critical-review lenses. Read it when reviewing a finished draft.
- [references/package-review.md](references/package-review.md): Phase 4, sections 4.1 to 4.6 (title-only test, newcomer lens, truth contract, batch budget, reader-value row, slug closure). Read it for headline, metadata, batch or publication-readiness review.
- [references/publication-review-fixtures.md](references/publication-review-fixtures.md): seventeen worked fixtures and the disposition a correct review must reach. Read it when testing a review process or changing these gates.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 2.3.0 text now lives.
- Load-with contract, Phase 0: below.

## Load-with contract

**Load-with contract for publication review.** Article drafting, headline work, article-package review, and publication-readiness review load the full prose-quality stack ([`synthesis-content-quality`](../synthesis-content-quality/SKILL.md), [`synthesis-writing-pitfalls`](../synthesis-writing-pitfalls/SKILL.md), [`synthesis-writing-craft`](../synthesis-writing-craft/SKILL.md), plus the author's private voice skill where one exists) **and** the framing plane: [`synthesis-reader-briefing`](../synthesis-reader-briefing/SKILL.md), [`synthesis-content-framing`](../synthesis-content-framing/SKILL.md), and this skill. A prose-stack-only route reviews bodies while the title/lede/reader-entry plane goes unexamined — the documented Set A failure mode: a full-body review cleared 29 of 30 packages whose titles then failed a title-only skim (6 keep / 8 tune / 16 replace). Do not load the framing plane for every email or sentence edit; the trigger is article-level framing or publication readiness.

## Phase 0: Reader Briefing (REQUIRED PRECONDITION)

**Hard precondition.** Before any research or drafting begins, write a four-paragraph reader briefing using the [`synthesis-reader-briefing`](../synthesis-reader-briefing/SKILL.md) skill. The briefing answers four questions: who is this for, what do they bring to the page, what does the article ask of them, what does the reader leave with.

The briefing lives as `.briefing.md` adjacent to the draft (in the same directory as the article markdown file). Without a committed briefing, this skill refuses to proceed. The friction is intentional — drafting without a briefing is the documented failure mode of inheriting source-material framing in articles meant for an external audience.

The briefing is the audit anchor that Phase 2 (writing) and Phase 3 (review) compare against. The article's structural decisions (universal-frame-first vs scene-first vs claim-first vs problem-first) follow from the briefing's answers, not from a template.

See [`synthesis-reader-briefing`](../synthesis-reader-briefing/SKILL.md) for the four questions, worked examples across genres (technical, personal-narrative, opinion, advisory), and the audit discipline.

## Related

Part of the [synthesis writing](https://synthesiswriting.org) craft — the writer writes, the AI assists.
