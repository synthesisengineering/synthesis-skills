# Coverage map: text provenance 1.0.1 to 2.0.0

Every part of the 1.0.1 SKILL.md and where it lives now. Nothing was removed at the 2.0.0 prose move; the v5 script change that followed is in its own section below, and [preserved.md](preserved.md) holds every replaced passage verbatim.

| 1.0.1 section | Now |
|---|---|
| Frontmatter description (folded block) | One quoted line under 300 characters; keeps the scope (hosted, local and open-weight models), the trigger list (watermark capability checks, reproducible records, mixed-authorship lineage, text-integrity audits, authorized detector results) and the "do not use to" exclusion |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type`, `license` | Kept (the modular installer and the source checks read them); version bumped to 2.0.0 and quoted; `format: v5` added |
| Title | SKILL.md (verbatim) |
| Opening: four judgments and "No result on one axis proves another" | SKILL.md, "Four judgments" (verbatim); binding rule 1 distills it |
| Trigger boundary | SKILL.md (verbatim) |
| Non-negotiable boundary | SKILL.md (verbatim). Kept in SKILL.md because synthesis-content-quality's `test_additive_upgrade_contract.py` reads "Do not provide or execute a workflow whose objective is to" and "optimize paraphrasing" from this file. Binding rules 2 and 5 distill it |
| Workflow, steps 1 to 7, with every command | references/workflow.md (verbatim apart from three link paths); binding rules 3 to 9 distill them |
| (new) Scripts | SKILL.md: each script's command line and what it prints, taken from the scripts' own print statements (format rule 7). Every command and flag in references/workflow.md is unchanged |
| Completion checklist | SKILL.md (verbatim) |

## Existing reference files

capability-claims.md, open-weight-runner-contract.md and provenance-manifest.md are unchanged; each is under 150 lines, so none needs a contents list.

## Scripts and tests

At the 2.0.0 prose move every script under `scripts/`, the test `scripts/test_provenance_tools.py` and `tests/fixtures/` were unchanged.

## v5 script changes (2026-10-05)

Verdicts from the v5 code evaluation (`tool-scripts.md`, synthesis-text-provenance rows).

| Part | Verdict | Now |
|---|---|---|
| `scripts/provenance_manifest.py` (600 lines) | CUT, never used (no manifest exists in any workspace) | The record is a markdown file in the project; references/provenance-manifest.md keeps every field (renamed for prose), the audit-entry rule that detector feedback is never an optimization objective, the privacy rules, and the verification limits; `shasum -a 256` replaces the self-hash and `verify`. The 1.0.1 file is verbatim in [preserved.md](preserved.md) |
| `scripts/local_generate.py` (240 lines) | CUT, never used | references/open-weight-runner-contract.md, rewritten as a procedure by hand: one `curl` request to a loopback endpoint, the raw response kept, empty final content is a failed generation, the returned model never inferred, secrets from the environment only, no URL with user information or query, one request one record, no detector input. Model-selection evidence and the reproducibility limit are verbatim |
| `scripts/ollama_metadata.py` (151 lines) | CUT, never used | The same file's "Before the request": `ollama --version`, `ollama list`, `ollama show` captured first, license and template hashed, unknowns declared, the tensor inventory left out |
| `scripts/text_integrity_audit.py` (191 lines) | KEEP, move into clean-text | `synthesis-clean-text/scripts/text_integrity_audit.py`, unchanged, with its tests; workflow step 5 and binding rule 7 point there |
| `scripts/test_provenance_tools.py`, `tests/fixtures/canonical-manifest-v2.json` | Removed with the code | The five integrity tests moved to synthesis-clean-text `tests/test_text_integrity_audit.py`; the manifest, runner and metadata tests left with their scripts |

Prose changed: SKILL.md binding rules 6 and 7, Contents, "Scripts" (now "Tools", every command shown is one that exists), and two checklist items; references/workflow.md (its intro, contents lines for steps 4 to 6, one sentence in step 3, and steps 4 to 6). The Non-negotiable boundary section stays whole in SKILL.md, because synthesis-content-quality's `test_additive_upgrade_contract.py` reads it. Python lines: 1,182 before (plus 511 of tests), none after in this skill.

## Lines the coverage check reports, and why

Three lines of the 1.0.1 SKILL.md are not carried over verbatim in the live text; `v5-skill-coverage-check.py` reported them until this block quoted them. Each is the second half of a sentence in workflow steps 2, 3 and 4, moved to references/workflow.md with its wording unchanged and only the link target adjusted (`references/x.md` became `x.md`, because the file now sits inside references/). The lines below are exactly as 1.0.1 had them, kept only as a record.

````markdown
[`references/capability-claims.md`](references/capability-claims.md).
[`references/open-weight-runner-contract.md`](references/open-weight-runner-contract.md).
[`references/provenance-manifest.md`](references/provenance-manifest.md).
````

## The 1.0.1 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-text-provenance
description: >
  Plan, record, and audit text provenance across hosted, local, and open-weight
  model workflows. Use for text provenance, watermark capability checks,
  local-model generation, reproducible AI-assistance records, mixed-authorship
  lineage, text-integrity audits, authorized detector results, and claims about
  what a provenance signal can or cannot prove. Do not use to defeat provider
  marks, evade detectors, or disguise AI authorship.
license: Apache-2.0
depends_on: []
metadata:
  author: Rajiv Pant
  version: 1.0.1
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
