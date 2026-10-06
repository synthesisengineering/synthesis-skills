# Coverage map: local messaging 0.1.0 to 1.0.0

Every part of the 0.1.0 SKILL.md and where it lives now. Nothing was removed or moved out: the whole text fit under the 8,000-byte limit with the binding rules and contents added, so every line stays in SKILL.md verbatim. The version goes from 0.1.0 to 1.0.0, the next major version.

`synthesis-onboarding/scripts/test_local_messaging_runtime.py` reads both SKILL.md and references/messages-boundary.md and requires each to hold exactly one backticked synthesis exec-public command, which it runs through the installed launcher. That command stays in SKILL.md, step 3, exactly as written; the binding rules, the contents list and this map name it without repeating it in that form, and the contents list added to messages-boundary.md names no command.

| 0.1.0 section | Now |
|---|---|
| Frontmatter description | Shortened to under 300 characters, keeping its trigger words: local message triage, daily or trailing-window review, Messages guard integration, and its limits (authorized database path; no account discovery, transcript export or send authority); "does not ... activate rituals" is now binding rule 9 |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type` | Kept (the installer and source checks read them) |
| Title and opening paragraph | SKILL.md (verbatim) |
| "Read [the adapter contract]..." paragraph | SKILL.md (verbatim), now the first paragraph of Read and interpret so the purpose, binding rules and contents come first |
| Read and interpret, steps 1 to 5 and the two paragraphs after them | SKILL.md (verbatim); binding rules 1 to 6 |
| Messages sending | SKILL.md (verbatim); binding rules 7 and 8 |
| Daily rituals paragraph | SKILL.md (verbatim); binding rule 9 |

## Existing reference files

Both keep their content. messages-boundary.md (over 150 lines) gained a short contents list after its opening paragraph. adapter-contract.md is under 150 lines and unchanged.

## Lines the coverage check reports, and why

`v5-skill-coverage-check.py` reports no lines: every line of the 0.1.0 text is present verbatim.

## The 0.1.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-local-messaging
description: Read explicitly selected local Messages or WhatsApp SQLite data into bounded notes and source pointers. Use for local message triage, daily or trailing-window review, and Messages guard integration. Requires an authorized database path; does not discover accounts, export transcripts, activate rituals, or grant send authority.
license: "Apache-2.0"
depends_on: ["synthesis-project-management", "synthesis-autopilot", "synthesis-message-guard"]
metadata:
  author: "Synthesis Engineering"
  version: "0.1.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
