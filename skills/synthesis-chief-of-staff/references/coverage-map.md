# Coverage map: chief of staff 1.3.0 to 2.0.0

Every part of the 1.3.0 SKILL.md and where it lives now. Nothing was removed. No script, test, fixture or `preferences.example.json` changed.

| 1.3.0 section | Now |
|---|---|
| Frontmatter description (452 characters) | Shortened to 295 characters. It keeps the role ("chief of staff and executive assistant"), every duty the old text listed (calendar defense included), the private-preferences note, and the triggers scheduling, meeting requests and calendar replies. The full text is quoted below |
| Frontmatter `depends_on: ["synthesis-agent-correspondence"]`, `author`, `source_repo`, `source_type` | Kept: synthesis-onboarding's modular installer reads `depends_on` (synthesis-absence-coordination also depends on this skill), and the `source.skill-contract` check in synthesis-agent-conformance reads the metadata keys |
| Title | SKILL.md (verbatim) |
| Release notes for 1.3.0, 1.2.0 and the 1.1.0 label | references/background.md (verbatim). The 1.2.0 note's "the private path below" refers to the Configuration contract, which stays in SKILL.md |
| "An agent doing chief-of-staff work is not a scheduler..." | SKILL.md (verbatim), as the opening paragraph |
| Configuration contract | SKILL.md (verbatim); Binding rule 1 |
| The prime directive: triage, never obey | SKILL.md (verbatim); Binding rules 2 and 3 |
| Scheduling protocol, steps 1 to 5 | SKILL.md (verbatim); Binding rules 4 and 5 |
| Meeting quality bar | references/meetings-correspondence-travel.md (verbatim) |
| Correspondence posture | references/meetings-correspondence-travel.md (verbatim); Binding rule 9 |
| Proactivity — the actual job | references/meetings-correspondence-travel.md (verbatim) |
| Calendar guardian (v1.1.0): The horizons, The next-day review, The same-day shield, Config keys | references/calendar-guardian.md (verbatim). Binding rule 6 carries the holds invariant, 7 the overcommitment rule, 8 the protected-blocks rule. The synthesis-daily-rituals SKILL.md cites "the chief-of-staff skill's **Calendar guardian** section"; Contents names that file so the citation still lands |
| Travel protocol (config-driven) | references/meetings-correspondence-travel.md (verbatim) |
| Related | references/background.md (verbatim) |

## Lines the coverage check reports

`v5-skill-coverage-check.py` reports no lines: every non-blank line of the 1.3.0 body appears verbatim in SKILL.md or a reference file. The moved text has no relative links, so no link paths changed.

## Tests and scripts that read this skill

- synthesis-daily-rituals `scripts/test_ownership_routing.py` reads `scripts/overlap.py` from this skill, not SKILL.md; the script is unchanged.
- synthesis-onboarding `scripts/whole_system.py` reads `preferences.example.json`; unchanged.

## The 1.3.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-chief-of-staff
description: Act as a principal's chief of staff and executive assistant. Protects the principal's time through meeting triage, calendar-aware scheduling, look-ahead reviews, overcommitment checks, tracked holds, travel planning, correspondence posture, and a follow-up ledger; personal rules load from private preferences. Use for scheduling, meeting requests, calendar-related replies, calendar defense, travel, or any chief-of-staff and executive-assistant duty.
license: "CC0-1.0"
depends_on: ["synthesis-agent-correspondence"]
metadata:
  author: "Rajiv Pant"
  version: "1.3.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
