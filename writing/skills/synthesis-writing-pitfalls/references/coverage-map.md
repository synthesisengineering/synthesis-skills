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

## The 1.1.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-writing-pitfalls
description: >
  Universal bad-writing patterns produced by human authors and editors, independent of AI.
  Covers cringe (humble-bragging, defensive disclaimers, third-person self-reference in personal
  writing, pre-emptive originality defense, apologizing-while-bragging), throat-clearing,
  caveat overload, reader-relationship missteps, sentence-level weakness, cliché reliance, and
  stilted formality. Use when reviewing or editing prose for craft failures, doing archive
  scans, self-editing drafts, or training writers and editors. Apply alongside
  synthesis-content-quality (AI-specific patterns) and synthesis-writing-craft (positive principles).
license: CC0-1.0
depends_on: []
metadata:
  author: Rajiv Pant
  version: 1.1.0
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

## The 1.1.0 lines with old link paths

The nine lines listed above exactly as 1.1.0 had them, so synthesis-content-quality's no-removals test can match each one. The links here are written for SKILL.md's folder and are kept only as a record.

```markdown
**Article register in a social media post** is the dominant modern variant of this pitfall, and its symptoms are now common enough to be cataloged separately. They include: third-person narration of first-person experience ("the site" / "the audit" / "the fix" where it should be "my site" / "my audit" / "my fix"); formal severity labels imported from source material (CRITICAL / HIGH / MEDIUM in a conversational post); essay structure markers ("first", "second", "the principle", "the takeaway", "in summary"); no first-person pronouns in posts about the author's own work; no closing engagement; sentences over 25 words without compression; over-smoothed prose with no rhythmic variation. The same writer's voice should sound different in articles vs social posts — same person, different mode. See [`synthesis-content-quality`](../synthesis-content-quality/SKILL.md) criteria 38-41 for the AI-detectable variants and [`synthesis-content-distribution`](../synthesis-content-distribution/SKILL.md) "Social register vs article register" for the rationale and the expectation gap that drives the failure.
For deeper examples and fix guidance on each pattern, see [`references/detailed-pitfalls.md`](references/detailed-pitfalls.md).
This skill catches HUMAN-SOURCE failures. For AI-generation patterns (saturated vocabulary clustering, exhausted metaphors as structural filler, the concierge tone, hyperbolic subheadings, the rule of three, mechanical transitions, etc.), use [`synthesis-content-quality`](../synthesis-content-quality/SKILL.md). The two skills together cover the bad-writing landscape from both root-cause directions.
For positive principles (what to DO instead of what to avoid), use [`synthesis-writing-craft`](../synthesis-writing-craft/SKILL.md).
- [`synthesis-content-quality`](../synthesis-content-quality/SKILL.md) — AI-generation patterns and AI-slop detection
- [`synthesis-writing-craft`](../synthesis-writing-craft/SKILL.md) — Positive principles drawn from the writing-craft tradition
- [`synthesis-reader-briefing`](../synthesis-reader-briefing/SKILL.md) — Pre-writing audience analysis that prevents many of these pitfalls upstream
- [`synthesis-article-writing`](../synthesis-article-writing/SKILL.md) — End-to-end article workflow with quality gates
- [`synthesis-article-refresh`](../synthesis-article-refresh/SKILL.md) — Refresh and revitalize older articles
```
