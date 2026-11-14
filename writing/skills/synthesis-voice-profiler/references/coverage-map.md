# Coverage map: voice profiler 1.0.0 to 2.0.0

Every part of the 1.0.0 SKILL.md and where it lives now. Nothing was removed; `v5-skill-coverage-check.py` finds all 116 old lines verbatim.

| 1.0.0 section | Now |
|---|---|
| Frontmatter description | Rewritten to 286 characters; it keeps the triggers "create a voice profile", "analyze writing style", "extract voice", "profile my writing" and "build a voice section" |
| Opening paragraph | SKILL.md (verbatim) |
| What This Produces | SKILL.md (verbatim); summarized in Binding rule 6 |
| Process, Step 1: Collect Writing Samples | SKILL.md (verbatim); summarized in Binding rule 1 |
| Step 2: heading and instruction paragraph | SKILL.md (verbatim), with a new line pointing to the question bank; summarized in Binding rule 2 |
| Step 2: question bank, questions 1 to 10 | references/diagnostics-and-analysis.md (verbatim) |
| Step 3: heading and lead-in line | SKILL.md (verbatim), with a new line naming the six dimensions and pointing to their checklists; summarized in Binding rule 3 |
| Step 3: the six dimensions and their checklists | references/diagnostics-and-analysis.md (verbatim) |
| Step 4: heading, lead-in line, and "Adapt the template" paragraph | SKILL.md (verbatim), with a new line pointing to the template; summarized in Binding rule 4 |
| Step 4: the voice profile template | references/profile-template.md (verbatim) |
| Step 5: Review and Refine | SKILL.md (verbatim); summarized in Binding rule 5 |
| Integration | references/integration.md (verbatim) |
| When to Re-Run, Related | SKILL.md (verbatim) |
| Horizontal rules between sections | Dropped as layout only |
| `user-invocable`, `depends_on`, `source_repo`, `source_type`, `author` | Kept: Claude Code reads `user-invocable`, `synthesis-agent-conformance` checks the rest in its source contract, and `synthesis-onboarding` modular install reads `depends_on` |

## The 1.0.0 frontmatter, verbatim

Kept on record so the old description and metadata are not lost.

```yaml
---
name: synthesis-voice-profiler
description: "Generate a structured writing voice profile from sample texts and diagnostic questions. Outputs an agent-instruction voice section that other skills automatically consume. Use when asked to: create voice profile, analyze writing style, extract voice, profile my writing, build voice section, writing DNA, style analysis."
license: "CC0-1.0"
user-invocable: true
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
