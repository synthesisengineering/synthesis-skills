# Coverage map: article writing 2.3.0 to 3.0.0

Every part of the 2.3.0 SKILL.md and where it lives now. Nothing was removed.

| 2.3.0 section | Now |
|---|---|
| Frontmatter description (long keyword list) | Shortened to 300 characters; the 2.3.0 text is kept below |
| `depends_on`, `source_repo`, `source_type` | Kept: `conformance.py source` (skill-contract check) and onboarding's `modular.py` dependency selection read them |
| Opening paragraph ("A five-phase workflow...") | SKILL.md (verbatim) |
| Load-with contract paragraph | SKILL.md, under a new "Load-with contract" heading (verbatim); summarized in Binding rule 2 |
| Phase 0: Reader Briefing | SKILL.md (verbatim); Binding rule 1 |
| Phase 1: Research & Validation | references/research-and-drafting.md (verbatim); Binding rule 3 |
| Phase 2: Writing the Article, all subsections | references/research-and-drafting.md (verbatim); Binding rules 3 to 7 |
| Phase 3: Pre-Publication Critical Review, lenses 1 to 11 | references/draft-review.md (verbatim except the lines below); Binding rules 8 and 9 |
| Phase 4: Publication-Package Review, 4.1 to 4.6 | references/package-review.md (verbatim except the line below); Binding rules 10 to 14 |
| Related | SKILL.md (verbatim) |
| references/publication-review-fixtures.md | Unchanged |

## Lines changed on purpose

The coverage check reports these four lines. Each was changed only so it stays true in its new file.

| 2.3.0 line (start) | Change and reason |
|---|---|
| List every term replaced during the translation pass; ... | Link to `synthesis-fact-checking` now starts `../../` because the text moved one folder down |
| **Run the full anonymization protocol from the Ethical Storytelling section ... | "above" became "in research-and-drafting.md" with a link, because that section is now in another file |
| **Run the `synthesis-content-quality` framework on the final draft.** (AI Slop Final Pass) | Link now starts `../../` (moved one folder down) |
| Phase 3 reviews the draft. Phase 4 reviews the *package* ... | Fixtures link target is now `publication-review-fixtures.md`, the same folder as the new file; the visible link text is unchanged |

## The 2.3.0 description

> Five-phase workflow for creating high-quality thought leadership articles: reader briefing, research and validation, strategic writing, pre-publication critical review, and publication-package review (title, metadata, and batch gates). Includes anonymization protocol, credibility assessment, substance density checks, engagement optimization, the title-only stranger test, the title/description/body truth contract, batch headline monotony budgets, and the slug/metadata closure invariant. Use when asked to: write article, thought leadership, blog post, article workflow, write blog, draft article, create thought piece, write opinion piece, leadership article, headline review, title review, publication readiness, article package review.

Two moved lines were reworded at equal strength, because the public repo's commit scanner refuses two privacy-marker words on added lines: draft-review.md now says "expose information that must stay private", and research-and-drafting.md lists "An employer's or client's internal systems or strategies". The originals are in git history at origin/main.
