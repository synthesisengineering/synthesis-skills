# Coverage map: response merger 1.0.0 to 2.0.0

Every part of the 1.0.0 SKILL.md and where it lives now. Nothing was removed or moved out of SKILL.md; `v5-skill-coverage-check.py` finds all 27 old lines verbatim.

| 1.0.0 section | Now |
|---|---|
| Frontmatter description | Unchanged (229 characters) |
| Opening line | SKILL.md (verbatim) |
| Input | SKILL.md (verbatim) |
| Process, Steps 1 to 3, with the critical rules | SKILL.md (verbatim); the critical rules are summarized in Binding rules 1 and 2, Step 2 in rule 3 |
| Output structure | SKILL.md (verbatim); summarized in Binding rule 4 |
| Related | SKILL.md (verbatim) |
| `user-invocable`, `depends_on`, `source_repo`, `source_type`, `author` | Kept: Claude Code reads `user-invocable`, `synthesis-agent-conformance` checks the rest in its source contract, and `synthesis-onboarding` modular install reads `depends_on` |

## The 1.0.0 frontmatter, verbatim

Kept on record so the old description and metadata are not lost.

```yaml
---
name: synthesis-response-merger
description: "Combine multiple LLM responses into a single unified document. Use when asked to combine responses, merge outputs, synthesize responses, unify documents, or consolidate multiple AI-generated answers into one comprehensive result."
license: "CC0-1.0"
user-invocable: false
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
