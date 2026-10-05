# Coverage map: tree of thought 1.0.0 to 2.0.0

Every part of the 1.0.0 SKILL.md and where it lives now. Nothing was removed or moved out of SKILL.md; `v5-skill-coverage-check.py` finds all 58 old lines verbatim.

| 1.0.0 section | Now |
|---|---|
| Frontmatter description | Unchanged (288 characters) |
| Opening line | SKILL.md (verbatim) |
| How it works, steps 1 to 8 | SKILL.md (verbatim); summarized in Binding rules 3 to 5 |
| Template 1: General-purpose | SKILL.md (verbatim); the template is the working text of the technique, so it stays where it is used |
| Template 2: Domain-expert variant | SKILL.md (verbatim), for the same reason |
| Guidance for choosing experts | SKILL.md (verbatim); summarized in Binding rule 2 |
| When to use, When NOT to use | SKILL.md (verbatim); summarized in Binding rule 1 |
| `depends_on`, `source_repo`, `source_type`, `author` | Kept: `synthesis-agent-conformance` checks them in its source contract and `synthesis-onboarding` modular install reads `depends_on` |

## The 1.0.0 frontmatter, verbatim

Kept on record so the old description and metadata are not lost.

```yaml
---
name: synthesis-tree-of-thought
description: "Multi-expert collaborative reasoning technique. Use when asked to apply tree of thought, multi-expert brainstorming, collaborative reasoning, expert panel analysis, or when a problem benefits from simulating multiple domain experts debating step by step to reach a well-vetted conclusion."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
