# Coverage map: skill router 1.5.0 to 2.0.0

Every part of the 1.5.0 SKILL.md and where it lives now. Nothing was removed.

| 1.5.0 section | Now |
|---|---|
| Frontmatter description | Two words trimmed ("correct" became "right", one comma dropped) and the text quoted, bringing it to 298 characters; meaning and triggers unchanged |
| Opening paragraph 1 (narrowest workflow, relative paths, multiple skills) | Binding rules 1 to 3, one sentence each, word for word |
| Opening paragraph 2 (route by outcome, operative references, mandatory checks, decision ownership) | Binding rules 4 to 7, one sentence each, word for word |
| Route by outcome, all six groups | SKILL.md (verbatim). It stays in SKILL.md because it is the router: `synthesis-adversarial-review/scripts/protocol_acceptance.py` and `synthesis-promotion-gate/scripts/test_skill_contract.py` read its routes from SKILL.md |
| Closing line "Do not substitute this routing summary..." | Binding rule 8, word for word |
| `depends_on`, `source_repo`, `source_type`, `author` | Kept: `synthesis-agent-conformance` checks them in its source contract and `synthesis-onboarding` modular install reads `depends_on` |

A new one-paragraph purpose statement opens SKILL.md, as the v5 format requires.

## Lines restructured in place

The two opening paragraphs were split at sentence boundaries into Binding rules 1 to 7, and the closing line became Binding rule 8. Every word stayed and the order is unchanged. The 1.5.0 lines were:

```text
Choose the narrowest matching workflow, then read its sibling `SKILL.md` completely before acting. Resolve every path relative to this skill's directory. Load multiple skills when the request crosses categories; their `depends_on` declarations remain authoritative.
Route by the requested outcome and the current stage. Load operative references when their task shape applies, without copying entire catalogs into each run. Preserve mandatory evidence, authority, coordination and domain checks. Loading a skill does not reopen a settled decision or turn delegated implementation choices into user approval gates; use the [decision-ownership contract](../synthesis-thinking-framework/references/decision-ownership.md) when instructions appear to disagree.
Do not substitute this routing summary for the selected skill's instructions.
```

## The 1.5.0 frontmatter, verbatim

Kept on record so the old description and metadata are not lost.

```yaml
---
name: synthesis-skill-router
description: Route a request to the correct synthesis engineering, coding, writing, project-management, knowledge, operations, or agent-governance skill while keeping specialist metadata out of Codex's bounded prompt. Use when a task appears to match a synthesis workflow but the user did not name the exact skill.
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.5.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
