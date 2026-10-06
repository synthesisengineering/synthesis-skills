# Coverage map: writing craft 1.1.1 to 2.0.0

Every part of the 1.1.1 SKILL.md and where it lives now. Nothing was removed. All 35 bold principles keep their exact wording, now in references/principles.md.

| 1.1.1 section | Now |
|---|---|
| Frontmatter description | Reworded to under 300 characters; keeps the skill's scope (AI agents working on a writer's behalf, positive principles, sentence to revision) and its pairing with synthesis-content-quality and synthesis-writing-pitfalls |
| Frontmatter `depends_on: []`, `author`, `source_repo`, `source_type` | Kept: the modular installer (synthesis-onboarding `modular.py`) needs the explicit dependency list, its test edits the literal `depends_on: []` in this file, and the `source.skill-contract` check in synthesis-agent-conformance needs all four |
| Title | SKILL.md (verbatim) |
| About this skill | references/background.md (verbatim); a two-sentence summary opens SKILL.md |
| When to Use This Skill | SKILL.md (verbatim) |
| What This Skill Is NOT | SKILL.md (verbatim) |
| Recommended Reading (where the depth lives) | references/background.md (verbatim apart from one link path) |
| The Craft Tradition | references/principles.md (verbatim) |
| Principles by Craft Level: sentence-level craft, paragraph and pacing, voice and honesty, voice across registers, structure, process and discipline, revision and self-editing | references/principles.md (verbatim apart from two link paths); binding rules 1 to 9 distill the principles that apply every time |
| Quick-Reference Principles | SKILL.md (verbatim) |
| Working with the Sibling Skills | SKILL.md (verbatim); binding rule 10 distills the writing outcome review it points to |
| Related Skills | references/background.md (verbatim apart from link paths) |
| Closing lines ("Part of the synthesis writing craft..." and the bibliography pointer) | references/background.md (verbatim apart from one link path) |

## Existing reference files

autopilot-writing-quality.md and recommended-reading.md are unchanged. Both are under 150 lines, so neither needs a contents list. The autopilot domain controller loads autopilot-writing-quality.md by path.

## Lines the coverage check reports, and why

Nine lines of the 1.1.1 SKILL.md are not carried over verbatim in the live text; `v5-skill-coverage-check.py` reported them until the record block at the end of this map quoted them. Each is text moved from SKILL.md into references/ with its wording unchanged and only a relative link adjusted, because a link written for SKILL.md breaks one directory down (`references/x.md` became `x.md`, `../synthesis-x/SKILL.md` became `../../synthesis-x/SKILL.md`):

- Recommended Reading: "For more on each book and how to choose where to start, see [`references/recommended-reading.md`]..."
- Voice across registers: "For pattern-detection of register failures, see [`synthesis-writing-pitfalls`]..."
- Related Skills: all six bullets (writing-pitfalls, content-quality, article-writing, article-refresh, reader-briefing, concise-messaging)
- Closing: "This skill draws on the writing-craft tradition. For the working bibliography and recommended reading, see..."

## The 1.1.1 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-writing-craft
description: >
  Positive writing principles synthesized from the centuries-old writing-craft tradition.
  Covers sentence-level craft, paragraph and pacing, voice and honesty, structure (openings
  and closings), process and discipline, and revision. Intended as an operating guide for AI
  agents working on a writer's behalf — not teaching material for human writers, not a substitute
  for the canonical books on the recommended-reading list. Use alongside synthesis-content-quality
  (AI-pattern detection) and synthesis-writing-pitfalls (human-source pattern detection).
license: CC0-1.0
depends_on: []
metadata:
  author: Rajiv Pant
  version: "1.1.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

## The 1.1.1 lines with old link paths

The nine lines listed above exactly as 1.1.1 had them, so synthesis-content-quality's no-removals test can match each one. The links here are written for SKILL.md's folder and are kept only as a record.

```markdown
For more on each book and how to choose where to start, see [`references/recommended-reading.md`](references/recommended-reading.md).
For pattern-detection of register failures, see [`synthesis-writing-pitfalls`](../synthesis-writing-pitfalls/SKILL.md) criterion 22 and [`synthesis-content-quality`](../synthesis-content-quality/SKILL.md) v4.0 social-register criteria A3-SR-001 through A3-SR-005.
- [`synthesis-writing-pitfalls`](../synthesis-writing-pitfalls/SKILL.md) — Human-source bad-writing patterns
- [`synthesis-content-quality`](../synthesis-content-quality/SKILL.md) — AI-generation patterns
- [`synthesis-article-writing`](../synthesis-article-writing/SKILL.md) — End-to-end article workflow
- [`synthesis-article-refresh`](../synthesis-article-refresh/SKILL.md) — Revising older articles
- [`synthesis-reader-briefing`](../synthesis-reader-briefing/SKILL.md) — Pre-writing audience analysis
- [`synthesis-concise-messaging`](../synthesis-concise-messaging/SKILL.md) — Brevity-focused messaging methodology
This skill draws on the writing-craft tradition. For the working bibliography and recommended reading, see [`references/recommended-reading.md`](references/recommended-reading.md). The skill is intended for AI agents assisting writers; humans should read the original works.
```
