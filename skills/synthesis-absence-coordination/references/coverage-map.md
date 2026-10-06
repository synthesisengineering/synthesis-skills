# Coverage map: absence coordination 1.0.0 to 2.0.0

Every part of the 1.0.0 SKILL.md and where it lives now. Nothing was removed, and no line needed rewording, so the coverage check finds every old line verbatim.

| 1.0.0 section | Now |
|---|---|
| Frontmatter description (long, unquoted) | One quoted line under 300 characters; keeps the absence kinds, notification order, coverage and reachability, recurring-meeting release, the personal-continuity tier, out-of-office set and clear, the return sweep, and the triggers planning time off, announcing an absence and arranging coverage. "Booking work travel", "travel-logistics forwarding" and "returning from one" are covered by "conference", the workflow's logistics step and "return sweep"; the private-config sentence now opens SKILL.md |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type`, `license` | Kept (the modular installer and the source checks read them); version bumped to 2.0.0; `format: v5` added |
| Title | SKILL.md (verbatim) |
| "**Version 1.0.0** (2026-08-12)" | references/doctrine.md, "Release notes" (verbatim), with a 2.0.0 note added |
| An absence is a handoff, not an announcement | references/doctrine.md (verbatim); the SKILL.md opening paragraph summarizes it |
| Configuration contract | SKILL.md (verbatim, links unchanged); binding rule 1 |
| The five failures this skill prevents | SKILL.md (verbatim) |
| Notification order, and The hard gates table | references/doctrine.md (verbatim); binding rules 2 to 5, 7 and 8 restate the cc rule and the five gates |
| Required content: coverage and reachability | references/doctrine.md (verbatim); binding rules 5 and 6 |
| Recipient tiers, Disclosure is per tier, Never use a distribution alias for a tier | references/doctrine.md (verbatim); binding rules 9 and 10. `validate_config.py` points readers to SKILL.md, "Never use a distribution alias", so binding rule 9 keeps those words in SKILL.md |
| The personal-continuity tier | references/doctrine.md (verbatim) |
| Absence types, Two triggers, The quiet type | references/doctrine.md (verbatim); binding rule 11 |
| Workflow, steps 1 to 6 | references/workflow.md (verbatim); binding rules 4 and 12 |
| The ledger | references/workflow.md (verbatim); binding rule 8 |
| Rolling it out | references/workflow.md (verbatim) |
| Adapting this skill | references/workflow.md (verbatim) |

## Existing reference files

message-templates.md is over 150 lines, so it gained a short contents list under its title; no other line changed. config-schema.md and quickstart.md are unchanged.

## Scripts, config and tests

`validate_config.py`, `test_validate_config.py` and `example-config.yaml` are unchanged, and the documented command `python3 validate_config.py ~/.synthesis/absence-coordination/config.yaml` stays in SKILL.md exactly as written.

**2026-10-06.** `validate_config.py` and its test read YAML through the plugin's standard-library reader (`synthesis/yamlish.py`) instead of PyYAML, so the validator no longer exits 2 on a Python without PyYAML, and CI runs the test. Its command line and exit codes are unchanged.

## The 1.0.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-absence-coordination
description: Coordinate an absence end to end — vacation, conference travel, family visits, medical leave — the way a good chief of staff would. Covers the notification order that protects relationships (principals hear it from you, never from their own assistant or a group channel), coverage and reachability as required content rather than afterthoughts, recurring-meeting release, the personal-continuity tier that keeps a trainer or therapist or tutor in the loop while you travel, travel-logistics forwarding, out-of-office set AND clear, and the return sweep. All names, tiers, channels, and lead times load from a private config, so the skill is publishable and the configuration is yours. Use when planning time off, booking work travel, announcing an absence, arranging coverage, or returning from one.
license: "Apache-2.0"
depends_on: ["synthesis-chief-of-staff", "synthesis-agent-correspondence", "synthesis-catchup-ledger"]
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
