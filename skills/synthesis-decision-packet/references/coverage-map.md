# Coverage map: decision packet 1.8.0 to 2.0.0

Every part of the 1.8.0 SKILL.md and where it lives now. Nothing was removed. The six load-bearing properties keep their order as binding rules 1 to 6.

Text that scripts and tests depend on stays in SKILL.md: `build_packet.py` sends readers to "the anti-trigger in SKILL.md" (When NOT to use it, kept verbatim), to "the reader contract in SKILL.md" and to "SKILL.md requires this" for `--strict-reader` (binding rule 8 states both, and the full contract is in references/authoring.md). `synthesis-project-management/scripts/test_handoff.py` asserts SKILL.md names `synthesis-project-management/scripts/handoff.py`; the Contents line for background.md names it. Every command, flag and path is kept exactly as written.

| 1.8.0 section | Now |
|---|---|
| Frontmatter description (long) | Shortened to under 300 characters, keeping its trigger words: five or more decisions, review, migration, upgrade, triage, backlog |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type` | Kept (the installer and source checks read them) |
| Title | SKILL.md (verbatim) |
| "**Version 1.7.0** (2026-09-26)" line | references/background.md (verbatim, with a note that the frontmatter said 1.8.0) |
| Opening measurement paragraph | SKILL.md and references/background.md (verbatim) |
| Shape table, "The failure is not that the principal lacks information" | references/background.md (verbatim) |
| "The property to preserve above all others" | SKILL.md and references/background.md (verbatim) |
| When to use it, including Natural fits | SKILL.md (verbatim); binding rule 7 |
| When NOT to use it | SKILL.md (verbatim) |
| The six load-bearing properties | references/authoring.md (verbatim); binding rules 1 to 6 |
| Inspect the actual material | references/authoring.md (verbatim apart from one link path); binding rule 13 |
| Prior positions and contrary evidence | references/authoring.md (verbatim); binding rule 10 |
| Content requirements | references/authoring.md (verbatim); binding rule 10 |
| The reader contract (v1.1.0) | references/authoring.md (verbatim); binding rule 8 |
| Use, including File it, Record what came back, note whitespace, schema-2 records, idempotent imports | references/filing-and-authority.md (verbatim); the command block also stays in SKILL.md |
| Provenance and action authority | references/filing-and-authority.md (verbatim); binding rule 12 |
| Enforcement (v1.5.0), Generate from a data array, what the generator refuses | references/enforcement.md (verbatim); binding rule 9 |
| Two defects that are permanent fixtures | references/enforcement.md (verbatim); binding rule 11 |
| Relationship to other skills | references/background.md (verbatim) |
| Changelog | references/background.md (verbatim) |
| Related | references/background.md (verbatim) |
| Retiring historical interfaces | references/filing-and-authority.md (verbatim apart from one link path) |

## Existing reference files

Both keep their content. worked-example.md (over 150 lines) gained a short contents list after its opening paragraph; `scripts/test_build_packet.py` parses its code blocks, and the list adds none. review-assets.md is under 150 lines and unchanged.

## Lines the coverage check reports, and why

Before this map was written, `v5-skill-coverage-check.py` reported 2 lines as not found verbatim (it now finds them only because this map quotes them), both moved from SKILL.md into references/ with a link adjusted for the deeper folder; the wording is unchanged:

- Inspect the actual material: `Read [the review-asset contract](references/review-assets.md) before constructing` now links `review-assets.md`.
- Retiring historical interfaces: `Read [artifact succession](../synthesis-context-lifecycle/references/artifact-succession.md)` now links `../../synthesis-context-lifecycle/references/artifact-succession.md`.

## The 1.8.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-decision-packet
description: Collect many parallel decisions from a principal in one sitting instead of one per turn. Generates a self-contained HTML packet — one row per decision carrying the item, the agent's recommendation, the reasoning, and a link — with buttons labeled by what pressing them does, the consequence under each button, a per-row note box, local persistence, and a paste-able summary the principal returns in a single message; files the spec, the page, and the returned rulings in the owning project's resources/artifacts/ so every agent on the project can read them. Use when you owe five or more decisions of the same shape; when a review, migration, upgrade, triage, or backlog pass has produced a list someone must rule on; or when a per-item conversation is burning round-trips.
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.8.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
