# Reader briefing: background

Why this skill exists, and the skills it works beside.

## Why this skill exists

AI-assisted writing has a specific failure mode: when source material (lessons, project context, commit messages, codebases) is loaded into the writing process, the draft inherits the source's framing. The source was written by the writer for the writer. It assumes its reader already has the context. An article written for a stranger has to assume the opposite. Translating between those frames is the actual writing work, and it is the work AI is most likely to skip when given source material to follow.

The result is **insider context collapse** — right vocabulary deployed for an audience that does not share the writer's context. The grammar is clean, the saturated AI vocabulary is absent, the mechanical quality checks pass, and the article is unreadable to the people it is for.

The fix is procedural: a structured briefing before drafting, then an audit pass against the briefing during review. The check has to be procedural because the writer is the insider — the jargon reads as natural prose to the person who wrote it. Reading the draft and trusting your judgment will not catch this.

This skill is also the procedural workaround for the well-known curse-of-knowledge bias in writing: experts cannot easily imagine what it is like to not know what they know. The briefing forces the imagination.

---

## Related

- [`synthesis-thinking-framework`](../../synthesis-thinking-framework/SKILL.md) — the design-thinking mode ("the user is not an abstraction") is what this skill operationalizes. The briefing is the procedural workaround for the curse-of-knowledge bias.
- [`synthesis-content-quality`](../../synthesis-content-quality/SKILL.md) — criterion #37 (Insider Context Collapse) detects briefing failures in finished drafts. The briefing prevents; the criterion catches the cases where prevention was skipped.
- [`synthesis-content-framing`](../../synthesis-content-framing/SKILL.md) — has an "Audience Declaration" rule about declaring audience IN the article opening. The briefing is the BEFORE-WRITING complement.
- [`synthesis-article-writing`](../../synthesis-article-writing/SKILL.md) — depends on this skill; Phase 0 of the article-writing workflow is the briefing.
- [`synthesis-fact-checking`](../../synthesis-fact-checking/SKILL.md) — pairs with the article-writing skill's translation-pass re-verification step. After de-jargoning, every concrete claim is re-verified.

Part of the [synthesis writing](https://synthesiswriting.org) craft — the writer writes, the AI assists.
