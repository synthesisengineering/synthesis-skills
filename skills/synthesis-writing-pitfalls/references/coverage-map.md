# Coverage map: writing pitfalls 1.1.0 to 2.0.0

Every part of the 1.1.0 SKILL.md and where it lives now. Nothing was removed.

| 1.1.0 section | Now |
|---|---|
| Frontmatter description (long keyword list) | Shortened to 280 characters; the 1.1.0 text is kept below |
| `depends_on`, `source_repo`, `source_type` | Kept: `conformance.py source` (skill-contract check) and onboarding's `modular.py` dependency selection read them |
| Opening paragraph ("Universal bad-writing patterns...") | SKILL.md (verbatim) |
| When to Use This Skill | SKILL.md (verbatim) |
| Why This Is a Separate Skill | references/background.md (verbatim); Binding rule 5 |
| Core Philosophy | references/background.md (verbatim); Binding rules 1 and 2 |
| The Pattern Catalog: tier legend, seven families, patterns 1 to 23 and their notes | references/catalog.md (verbatim); the tier legend and each pattern's number, name and tier are repeated in SKILL.md's Pattern index; Binding rule 3 carries pattern 23 |
| Pointer to references/detailed-pitfalls.md | references/catalog.md (link path adjusted, see below) and SKILL.md Contents |
| Detection Process, steps 1 to 4 | SKILL.md (verbatim); Binding rules 6 and 7 |
| Quick-Reference Checklist | references/catalog.md (verbatim) |
| Distinct from AI-Pattern Detection | references/background.md (verbatim); Binding rules 4 and 5 |
| Related Skills | references/background.md (verbatim) |
| Closing line ("Part of the synthesis writing craft") | SKILL.md (verbatim) |
| references/detailed-pitfalls.md | Unchanged except for a new contents list and a pointer to catalog.md after its opening paragraph |

## Lines changed on purpose

The coverage check reports nine lines. Each was changed only so its links still resolve from the new folder.

| 1.1.0 line (start) | Change and reason |
|---|---|
| **Article register in a social media post** is the dominant modern variant ... | Two links to sibling skills now start `../../`, because the text moved into references/ |
| For deeper examples and fix guidance on each pattern, see ... | Link target is now `detailed-pitfalls.md`, the same folder; the visible text is unchanged |
| This skill catches HUMAN-SOURCE failures. ... | Link now starts `../../` (moved one folder down) |
| For positive principles (what to DO instead of what to avoid) ... | Link now starts `../../` |
| The five Related Skills bullets (content-quality, writing-craft, reader-briefing, article-writing, article-refresh) | Each link now starts `../../` |

## The 1.1.0 description

> Universal bad-writing patterns produced by human authors and editors, independent of AI. Covers cringe (humble-bragging, defensive disclaimers, third-person self-reference in personal writing, pre-emptive originality defense, apologizing-while-bragging), throat-clearing, caveat overload, reader-relationship missteps, sentence-level weakness, cliché reliance, and stilted formality. Use when reviewing or editing prose for craft failures, doing archive scans, self-editing drafts, or training writers and editors. Apply alongside synthesis-content-quality (AI-specific patterns) and synthesis-writing-craft (positive principles).
