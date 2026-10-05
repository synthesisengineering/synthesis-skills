# Coverage map: code planning 1.1.1 to 2.0.0

Every part of the 1.1.1 SKILL.md and where it lives now. Nothing was removed or moved out of SKILL.md.

| 1.1.1 section | Now |
|---|---|
| Frontmatter description | Rewritten to 248 characters; it keeps the triggers "generate code", "implement a feature", "write code" and "tackle a coding task" and the four things the skill does |
| Opening line | SKILL.md (verbatim) |
| Decision-ownership paragraph | Binding rules 1 to 3, one sentence each, word for word (below) |
| Inputs | SKILL.md (verbatim) |
| Process, Steps 1 to 4 | SKILL.md (verbatim); Step 2 is summarized in Binding rules 4 and 5, Step 3 in rule 6, Step 4 in rule 7 |
| When to skip multi-approach evaluation | SKILL.md (verbatim); summarized in Binding rule 4 |
| Principles | SKILL.md (verbatim); summarized in Binding rule 8 |
| `user-invocable`, `depends_on`, `source_repo`, `source_type`, `author` | Kept: Claude Code reads `user-invocable`, `synthesis-agent-conformance` checks the rest in its source contract, and `synthesis-onboarding` modular install reads `depends_on` |

## Lines restructured in place

The decision-ownership paragraph was split at sentence boundaries into Binding rules 1 to 3. Every word stayed and the order is unchanged. The 1.1.1 line was:

```text
Before choosing or asking, apply the shared [decision ownership contract](../synthesis-thinking-framework/references/decision-ownership.md). Honor explicit supervised checkpoints; decide technical choices within delegated work and continue. Existing user grants persist within their scope. A skill, preference or receipt cannot create new authority.
```

## The 1.1.1 frontmatter, verbatim

Kept on record so the old description and metadata are not lost.

```yaml
---
name: synthesis-code-planning
description: "Structured approach to code generation, implementing features, and writing code. Use when asked to generate code, implement a feature, write code, or tackle a coding task. Applies constraints, compares remaining viable approaches, resolves delegated technical choices, and implements the selected solution with evidence."
license: "CC0-1.0"
user-invocable: false
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.1.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
