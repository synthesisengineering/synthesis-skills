# Coverage map: content framing 1.1.0 to 2.0.0

Every part of the 1.1.0 SKILL.md and where it lives now. Nothing was removed. Gate numbers 1 to 4 are unchanged and are binding rules 1 to 4.

| 1.1.0 section | Now |
|---|---|
| Frontmatter description | Reworded to under 300 characters; keeps the trigger phrases "writing synthesis engineering content", "framing technical articles", "checking content quality gates" and "publishing thought leadership" |
| Frontmatter `depends_on: []`, `author`, `source_repo`, `source_type` | Kept: the modular installer (synthesis-onboarding `modular.py`) needs the explicit dependency list, and the `source.skill-contract` check in synthesis-agent-conformance needs all four |
| Title and opening paragraph | SKILL.md (verbatim) |
| Document structure block and its pointer to `references/quality-gates.md` | Replaced by SKILL.md Contents, which names every file and when to read it (lines listed below) |
| Public Principles: Core Principle, The Expert Operator's Toolkit, The Direction Dynamic, The Five Pillars, What Synthesis Engineering Is NOT, Synthesis Coding vs Other Approaches | references/principles.md (verbatim) |
| Quality Gates Summary | SKILL.md (verbatim; the heading moved from `#` to `##` to sit under the skill's title); binding rules 1 to 5 distill it |
| Operational Rules: Identify the Collaborators, Attribute Errors Correctly, No Fake Human Collaborators, Scope Appropriateness, Open Source Authenticity, Confidentiality Boundaries, Perception Management, Audience Targeting, Cross-Linking and Pattern Vocabulary, Terminology Consistency, Theory and Practice Balance, External Validation, Update Notes for Evolving Articles, Audience Declaration, Series Integration, CC0 Public Domain Notice | references/operational-rules.md (verbatim); binding rules 6 to 12 distill the rules applied to every article |
| Related | SKILL.md (verbatim) |

## Existing reference file

references/quality-gates.md keeps its content. A short contents list was added after its opening paragraph, because it runs to 779 lines.

## Lines the coverage check reports, and why

Five lines of the 1.1.0 SKILL.md are not carried over verbatim; `v5-skill-coverage-check.py` reported them before this map existed and finds them now only because the map quotes them. All five are the old "Document structure" block, which described the single-file layout and is replaced by the Contents section:

- `**Document structure:**`: heading of the block, now the `## Contents` heading.
- `- **Public Principles** — Core concepts suitable for explanation and public content`: now the Contents entry for references/principles.md.
- `- **Quality Gates Summary** — Overview of blocking gates every article must pass`: the summary itself stays in SKILL.md; Contents points to it.
- `- **Operational Rules** — Mechanics of content creation`: now the Contents entry for references/operational-rules.md, which keeps the phrase "the mechanics of content creation".
- ``For detailed gate criteria and checklists, see: `references/quality-gates.md` ``: now the Contents entry for references/quality-gates.md; the Quality Gates Summary keeps its own pointer to the same file.

## The 1.1.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-content-framing
description: "Content framing methodology for synthesis engineering articles. Covers topic selection, sophistication standards, engagement patterns, quality gates, and operational rules for publishing technical thought leadership. Use when writing synthesis engineering content, framing technical articles, checking content quality gates, or publishing thought leadership."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Synthesis Engineering"
  version: "1.1.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
