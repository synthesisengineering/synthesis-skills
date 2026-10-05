# Coverage map: thinking framework 2.1.1 to 3.0.0

Every part of the 2.1.1 SKILL.md and where it lives now. Nothing was removed; `v5-skill-coverage-check.py` finds all 218 old lines verbatim.

| 2.1.1 section | Now |
|---|---|
| Frontmatter description | Rewritten to 281 characters; it keeps the five mode names and the pre-response protocol, and adds when to use the skill |
| Opening paragraph (five-mode methodology, depth follows uncertainty) | SKILL.md (verbatim) |
| The Five Thinking Modes: intro paragraph and modes 1 to 5 | references/five-modes.md (verbatim); summarized in Binding rules 1 and 2 |
| Pre-Response Protocol, checks 1 to 4 | SKILL.md (verbatim); summarized in Binding rules 3 and 4 |
| Depth Calibration | SKILL.md (verbatim); summarized in Binding rules 1 and 9 |
| Decision ownership and execution | SKILL.md (verbatim); summarized in Binding rules 5 to 8 |
| Relationship to Other Skills | references/related-skills.md (verbatim) |
| references/decision-ownership.md, references/decisive-uncertainty.md | Unchanged; both under 150 lines, so neither needs its own contents list |
| `depends_on`, `source_repo`, `source_type`, `author` | Kept: `synthesis-agent-conformance` checks them in its source contract and `synthesis-onboarding` modular install reads `depends_on` |

## The 2.1.1 frontmatter, verbatim

Kept on record so the old description and metadata are not lost.

```yaml
---
name: synthesis-thinking-framework
description: "Five-mode thinking methodology (first principles, systems thinking, complexity thinking, analogical thinking, design thinking) with a pre-response protocol for non-trivial problems. Provides the foundational reasoning approach that other synthesis skills build upon."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.1.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
