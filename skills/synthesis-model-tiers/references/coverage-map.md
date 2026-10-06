# Coverage map: model tiers 2.2.0 to 3.0.0

Every part of the 2.2.0 SKILL.md and where it lives now. Nothing was removed. The Resolution rules stay in SKILL.md with their numbers 1 to 6. `scripts/test_catalog.py` reads `tiers.yaml` and references/catalog-verification.yaml, never SKILL.md; neither file changed, and every command, path and environment variable is kept exactly as written.

| 2.2.0 section | Now |
|---|---|
| Frontmatter description (long keyword list) | Shortened to under 300 characters, keeping its trigger words: model tiers, which model, effort level, model selection, switch models, model equivalents, update model table. The old labels (frontier, efficient, light) remain in references/background.md |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type` | Kept (the installer and source checks read them) |
| Title and the two opening paragraphs | SKILL.md (verbatim); binding rule 1 |
| The three roles | SKILL.md (verbatim) |
| Choosing a role: diagnostic difficulty, not apparent size | references/choosing-a-role.md (verbatim); binding rules 2 and 3 |
| Why these words | references/background.md (verbatim apart from one link path) |
| Resolution rules 1 to 6 | SKILL.md (verbatim); binding rules 4, 5 and 6 restate resolution rules 6, 5 and 1 |
| What this file is NOT | references/background.md (verbatim) |
| Update protocol | references/maintaining-the-table.md (verbatim apart from one link path); binding rules 6 to 8 |
| Consumer guidance | references/maintaining-the-table.md (verbatim); binding rule 8 |
| License, Author | references/background.md (verbatim) |

## Existing reference files

naming-rationale.md is under 150 lines and unchanged. catalog-verification.yaml is 178 lines of data, so a five-line YAML comment listing its top-level keys was added at the top; the parsed data is identical (checked with `yaml.safe_load` before and after), and `scripts/test_catalog.py` still passes. It is listed in Contents although the format test checks only `.md` files, because every file in references/ must be reachable from Contents.

## Lines the coverage check reports, and why

`v5-skill-coverage-check.py` reports 2 lines as not found verbatim. Each moved from SKILL.md into references/ and its link lost the `references/` prefix so it still resolves one folder down; the wording is unchanged:

- Why these words: "The labels name the work you hand a model, not the model itself..." (link to naming-rationale.md)
- Update protocol, step 2: "Record the documentation retrieval date per provider (`verified:`)..." (link to catalog-verification.yaml)

**2026-10-06.** `scripts/test_catalog.py` reads both files through the plugin's standard-library YAML reader (`synthesis/yamlish.py`) instead of PyYAML, so CI runs it; both files read identically under each.

## The 2.2.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-model-tiers
description: "Cross-provider model-tier convention for agentic work: three role labels (judgment, routine, bulk — formerly frontier, efficient, light) resolved to current model IDs per provider in tiers.yaml, so skills, project docs, and memory never hardcode model names. Also carries the role-selection rule: route by whether the CAUSE is known, not by how small the task looks — a symptom report is diagnosis and belongs in judgment even when the subject is one file. Use when asked about: model tiers, which model, model selection, judgment model, routine model, bulk model, frontier model, efficient model, switch models, model equivalents across providers, update model table, which effort level, low effort, wrong model for the task."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.2.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
