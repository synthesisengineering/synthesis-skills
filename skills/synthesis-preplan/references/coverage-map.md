# Coverage map: preplan 1.1.0 to 2.0.0

Every part of the 1.1.0 SKILL.md and where it lives now. Nothing was removed. `scripts/test_acknowledgments.py` is unchanged and still passes: the Acknowledgments section stays in SKILL.md, word for word.

| 1.1.0 section | Now |
|---|---|
| Frontmatter description (folded block, 418 characters) | Shortened to 296 characters. It keeps what the skill does (lock architecture decisions, resolve delegated technical choices, ask structured questions for the user's, hand a reviewable decision set to the planning step) and the triggers preplan, pre-plan a ticket, lock decisions, and open design questions. The full text is quoted below |
| Frontmatter `user-invocable`, `depends_on`, `author` ("Emil Peñalo"), `source_repo`, `source_type` | Kept: Claude Code reads `user-invocable`, synthesis-onboarding's modular installer reads `depends_on`, and the `source.skill-contract` check in synthesis-agent-conformance reads the metadata keys |
| Title and opening paragraph | SKILL.md (verbatim) |
| Decision ownership and execution mode, first two paragraphs | SKILL.md (verbatim). Its "review points below" are Steps 2, 5 and 6, now in references/workflow.md |
| Decision ownership, third paragraph ("The skill exists because the hard part of planning...") | references/background.md (verbatim) |
| Where this sits | references/background.md (verbatim) |
| When to use, When not to use | SKILL.md (verbatim) |
| Step 1: Source-of-truth grounding | references/workflow.md (verbatim); Binding rule 1 |
| Step 2: Initial assessment, with the execution-lane artifact | references/workflow.md (verbatim apart from one link path, below); Binding rule 8 |
| Step 3: Preliminary plan | references/workflow.md (verbatim) |
| Step 4: Open-questions Q&A loop, the three response modes, loop continuation | references/workflow.md (verbatim); Binding rules 5 and 6 |
| Step 5: Decision summary file, with its file structure and changelog row | references/workflow.md (verbatim); Binding rule 3 |
| Step 6: Handoff to your planning step | references/workflow.md (verbatim apart from one link path, below); Binding rules 2 to 4 |
| Plan document format, and its five gate subsections | references/plan-document-format.md (verbatim) |
| Q&A rubric details, and the three checks | references/workflow.md (verbatim, after Step 6); Binding rule 9 |
| Skip-Q&A behavior | references/workflow.md (verbatim) |
| Soft-fail behaviors | SKILL.md (verbatim) |
| Rules (eight bullets) | Binding rules 1 to 8, same order and same words; only the list marker changed, below |
| Acknowledgments | SKILL.md (verbatim); `test_acknowledgments.py` reads it there |
| references/commit-by-commit.md (472 lines) and references/single-commit.md (232 lines) | Content unchanged. Each gained a short contents list after its opening paragraphs, because both are over 150 lines |
| assets/handoff-template.md | Unchanged; now listed in Contents |

## Lines the coverage check reports, and why

Before this map existed, `v5-skill-coverage-check.py` reported 11 lines; this map quotes the `## Rules` heading, so it now reports the other 10. None is lost:

- **`## Rules` heading:** renamed. Its eight bullets are now Binding rules 1 to 8 under the `## Binding rules` heading the v5 format requires.
- **The eight Rules bullets** ("Don't skip the source-of-truth fetch", "Don't author the plan inside this skill", "Two durable artifacts", "Carry the execution contract in the handoff", "Lean don't dictate", "Reverse leans freely", "The commit-by-commit workflow lives at", "State the execution lane before touching a file"): each `- ` marker became its rule number. Every word after the marker is unchanged.
- **Two lines with link paths adjusted,** moved into references/workflow.md with their wording unchanged:
  - Step 2, item 5 ("Execution lane, with a one-line reason"): the `references/commit-by-commit.md` and `references/single-commit.md` targets became `commit-by-commit.md` and `single-commit.md`, since the files now sit beside it.
  - Step 6, item 1 ("Load the handoff template"): the `assets/handoff-template.md` target became `../assets/handoff-template.md`.

## The 1.1.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-preplan
description: >
  Architecture-decision pre-planning for tickets or issues with real design
  choices. Resolves delegated technical decisions and asks structured questions
  for choices the user owns, then hands a reviewable decision set to the planning
  step. Use when asked to: preplan, pre-plan this
  ticket, let's pre-plan, lock decisions for, design questions for, what are the
  open questions on, plan a ticket with real design choices.
license: "CC0-1.0"
user-invocable: true
depends_on: ["synthesis-code-audit"]
metadata:
  author: "Emil Peñalo"
  version: "1.1.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
