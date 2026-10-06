# Coverage map: meeting prep 1.3.0 to 2.0.0

Every part of the 1.3.0 SKILL.md and where it lives now. Nothing was removed. Section numbers 1 to 5 are unchanged: sections 2, 3 and 5 stay in SKILL.md under their old headings, and sections 1 and 4 keep their headings in the files named below. No script or test reads text from SKILL.md; every command, flag and path is kept exactly as written.

| 1.3.0 section | Now |
|---|---|
| Frontmatter description | Shortened to under 300 characters, keeping its trigger words: 1:1s, reviews, forums, external meetings, interviews, follow-through, debrief |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type` | Kept (the installer and source checks read them) |
| Title | SKILL.md (verbatim) |
| "**Version 1.0.0** (2026-09-20): first release" note | references/background.md (verbatim) |
| Opening paragraph ("An agent preparing a principal...") | SKILL.md (verbatim) |
| 1. Configuration contract | references/profiles-and-sharing.md (verbatim apart from one link path); binding rule 11 |
| 2. The prep loop | SKILL.md (verbatim); binding rules 1, 3 and 6 to 9 |
| Shared prep contributions | references/profiles-and-sharing.md (verbatim); binding rule 12 |
| 3. The debrief loop | SKILL.md (verbatim); binding rule 10 |
| 4. Integration seams | references/background.md (verbatim) |
| 5. What the skill refuses | SKILL.md (verbatim); binding rules 1 to 5 |

## Existing reference files

All four keep their content. Short contents lists were added after the opening paragraph of the two over 150 lines, factor-inventory.md and requirements.md. structures.md and workspace-profiles.md are under 150 lines and unchanged.

## Lines the coverage check reports, and why

Before this map was written, `v5-skill-coverage-check.py` reported 1 line as not found verbatim (it now finds it only because this map quotes it). In section 1, `see [workspace-profiles.md](references/workspace-profiles.md). Migrating one` moved into references/ and its link now points to `workspace-profiles.md`, one folder down; the wording is unchanged.

## The 1.3.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-meeting-prep
description: "Prepare a principal for any meeting the way a wise chief of staff would: weigh 60+ factors across the meeting, participants, principal's position, knowledge, and risk; model the readers before drafting; deliver a dense, scannable pack with a capture half; then debrief the transcript into decisions, commitments, and reader-profile updates. Use for 1:1s, reviews, forums, external meetings, interviews, and post-meeting follow-through."
license: "CC0-1.0"
depends_on: ["synthesis-context-lifecycle"]
metadata:
  author: "Rajiv Pant"
  version: "1.3.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
