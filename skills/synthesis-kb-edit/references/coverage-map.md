# Coverage map: kb-edit 1.0.0 to 2.0.0

Every part of the 1.0.0 SKILL.md and where it lives now. Nothing was removed.

| 1.0.0 section | Now |
|---|---|
| Frontmatter description (folded block, 519 characters) | Shortened to 285 characters, keeping its trigger phrases: update a knowledge base, edit KB content, fix a durable fact, add a concept, ship a KB edit, open a review request, synchronize after publication. The full text is quoted below |
| Frontmatter `depends_on: [synthesis-okf]`, `author`, `source_repo`, `source_type` | Kept: synthesis-onboarding's modular installer reads `depends_on`, and the `source.skill-contract` check in synthesis-agent-conformance reads the metadata keys |
| Title and opening paragraph | SKILL.md (verbatim) |
| Configuration gate | SKILL.md (verbatim); Binding rule 1 |
| Route by intent | SKILL.md (verbatim) |
| Plain-language interaction | SKILL.md (verbatim); Binding rule 11 |
| Edit and ship workflow, steps 1 to 7 | references/edit-and-ship.md (verbatim); Binding rules 2 to 8 summarize the gates in steps 1 to 7 |
| Synchronize after publication | SKILL.md (verbatim); Binding rule 10 |
| Hard invariants | references/edit-and-ship.md (verbatim, after step 7); each invariant is restated in Binding rules 1, 2, 4, 6, 7, 8 and 9 |
| references/knowledge-base-config-v1.md | Unchanged (118 lines, so no contents list was needed) |

## Lines the coverage check reports

`v5-skill-coverage-check.py` reports no lines: every non-blank line of the 1.0.0 body appears verbatim in SKILL.md or references/edit-and-ship.md. The moved text has no relative links, so no link paths changed.

## v5 script changes (2026-10-05)

The v5 code evaluation (`tool-scripts.md`, row `synthesis-kb-edit/scripts/kb_config.py`) ruled KEEP. `scripts/kb_config.py` (283 lines) is unchanged; its tests moved from `scripts/test_kb_config.py` to `tests/test_kb_config.py` (path change only, PyYAML skipped where missing) and gained `test_symlinked_contract_path_that_leaves_the_repo_is_refused`, which with the existing `test_rejects_path_escape` holds scenario E93 (a contract path that escapes the repository is refused). No prose changed.

**2026-10-06.** `kb_config.py` reads the contract through the plugin's standard-library YAML reader (`synthesis/yamlish.py`) instead of PyYAML, so it and its tests run on Apple's `/usr/bin/python3` and in CI, which had skipped the test file.

## The 1.0.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-kb-edit
description: >
  Edit, validate, and ship Markdown knowledge-base changes through a repository's
  config-driven workflow. Reads .agents/knowledge-base.yaml for the editable
  bundle, generated/refused paths, topic routing, frontmatter schema,
  confidentiality control, Git host, branching, and review policy. Use when a
  user asks to update a knowledge base, edit KB content, fix a durable fact,
  add a concept, ship an existing KB edit, open a knowledge-base review
  request, or synchronize a local knowledge-base checkout after publication.
license: Apache-2.0
depends_on:
  - synthesis-okf
metadata:
  author: Rajiv Pant
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
