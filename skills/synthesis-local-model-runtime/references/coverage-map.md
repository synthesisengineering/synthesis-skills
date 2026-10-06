# Coverage map: local model runtime 1.1.0 to 2.0.0

Every part of the 1.1.0 SKILL.md and where it lives now. Nothing was removed.

| 1.1.0 section | Now |
|---|---|
| Frontmatter description (long keyword list) | Shortened to under 300 characters; keeps profiling, the four runtimes, fit to memory and storage, install and update with identity receipts, verified inference, and the triggers local models, Ollama, which model fits this Mac or PC, model inventory and benchmarks. The named model families (Qwen, GLM, Kimi, DeepSeek) and "MLX model selection" are covered by "open-weight models" and the runtime list |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type`, `license` | Kept (the modular installer and the source checks read them); version bumped to 2.0.0; `format: v5` added |
| Title and opening paragraph | SKILL.md (verbatim) |
| Operating contract, items 1 to 11 | SKILL.md, "Binding rules" 1 to 11 (verbatim, same numbers). The heading "Operating contract" was renamed "Binding rules" (the v5 format requires that heading) |
| Quick start, first command block and the sentence after it | SKILL.md, "Quick start" (verbatim) and references/commands.md (verbatim) |
| Quick start, the rest (LM Studio, explicit artifacts, cached-layer recovery, verify and benchmark) | references/commands.md (verbatim; every command, flag and path unchanged) |
| Updating installed models (update, LM Studio block, `--think`, `configure-ollama`) | references/commands.md (verbatim) |
| Recommendation rules | references/selection-and-boundaries.md (verbatim); binding rules 12 and 13 distill the fit and no-silent-replacement rules |
| Storage guard | references/selection-and-boundaries.md (verbatim); binding rule 14 |
| Per-machine mapping | references/selection-and-boundaries.md (verbatim) |
| Runtime boundary, including the three "Read references/..." pointers | references/selection-and-boundaries.md (verbatim apart from three link paths); the pointers also appear in SKILL.md Contents as "read when" lines |
| Capability boundary | references/selection-and-boundaries.md (verbatim); binding rule 16 |
| Failure handling | references/selection-and-boundaries.md (verbatim); binding rule 15 |
| (new) Subcommands | SKILL.md: each subcommand of `scripts/local_model_runtime.py` and what it prints (JSON; exit 2 when not ready, failed or blocked), read from the script's argument parser and `main()` (format rule 7) |

## Existing reference files

architecture.md, catalog-maintenance.md and security-and-privacy.md are unchanged; each is under 150 lines, so none needs a contents list.

## Scripts, assets and tests

`scripts/local_model_runtime.py`, `scripts/test_local_model_runtime.py`, `assets/model_catalog.json` and `assets/policy.example.json` are unchanged. No test reads text from this SKILL.md.

## Lines the coverage check reports, and why

One heading of the 1.1.0 SKILL.md was renamed and three lines had link targets adjusted; `v5-skill-coverage-check.py` reported them until this block quoted them.

- `## Operating contract` became `## Binding rules`; the eleven items under it are verbatim.
- The three lines of the Runtime boundary pointer paragraph ("Read references/architecture.md when extending...", "references/catalog-maintenance.md before...", "references/security-and-privacy.md when...") moved to references/selection-and-boundaries.md with their wording unchanged and only the link target adjusted (`references/x.md` became `x.md`, because the file now sits inside references/).

The lines below are exactly as 1.1.0 had them, kept only as a record.

````markdown
## Operating contract
Read [references/architecture.md](references/architecture.md) when extending
[references/catalog-maintenance.md](references/catalog-maintenance.md) before
[references/security-and-privacy.md](references/security-and-privacy.md) when
````

## The 1.1.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-local-model-runtime
description: "Profile a computer, compare Ollama, LM Studio, llama.cpp, and MLX-LM, recommend local open-weight model artifacts that fit its real memory and storage, install approved artifacts through deterministic managed-runtime adapters, update installed Ollama models with before-and-after identity receipts, maintain a privacy-safe per-machine inventory, and verify local inference. Use for: local models, open weights, Ollama, LM Studio, llama.cpp, MLX model selection, model updates, which model fits this Mac or PC, install Qwen/GLM/Kimi/DeepSeek locally, hardware profile for LLMs, model inventory, local inference benchmark."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.1.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
