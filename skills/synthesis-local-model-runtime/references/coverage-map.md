# Coverage map: local model runtime 1.1.0 to 2.0.0

Every part of the 1.1.0 SKILL.md and where it lives now. Nothing was removed.

Contents:
- The 1.1.0 SKILL.md sections, and the existing reference files
- Scripts, assets and tests (prose pass); lines the coverage check reports
- The 1.1.0 frontmatter
- Scripts in v5 (M3): files, subcommands, edge cases E85 to E87, old tests, replaced passages

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

That held for the prose pass. M3 then slimmed the script and replaced its tests; see `## Scripts in v5 (M3)` at the end.

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

## Scripts in v5 (M3)

Verdict (evaluation `tool-scripts.md`, row synthesis-local-model-runtime): **SLIM** to about 450
lines; keep profile, the catalog check, recommend, and a thin install and update over Ollama;
keep the command names the published article documents.

| Old file | Verdict | Lines before, after | Now |
|---|---|---|---|
| `scripts/local_model_runtime.py` | SLIM | 2,640, 795 | Fresh rewrite: `profile`, `runtimes`, `catalog`, `recommend`, `install`, `update`, `configure-ollama` |
| `scripts/test_local_model_runtime.py` | rewritten | 965, 0 (deleted) | `tests/test_local_models_runtime.py` (505 lines, 63 tests, fake runners for `ollama`, `lms`, `launchctl` and the loopback API) |
| `assets/model_catalog.json` | kept | unchanged | Its `local_import_fallback` blocks stay as pinned evidence; nothing reads them now |
| `assets/policy.example.json` | kept | 13, 14 | Adds `"excluded_families": []` |

Why 795 lines and not 450: the article prints the LM Studio install (with `--yes`), the update
receipt directory and `configure-ollama` with backup, reload, health check and rollback, and each
must keep working; the catalog validator, the privacy-safe profile and the E85 to E87 gates take
the rest. Everything the article does not print went.

### Subcommands and behaviour

| Before (1.1.0 script) | Now |
|---|---|
| `profile` | Kept. Windows memory now comes from PowerShell CIM (`TotalPhysicalMemory`) instead of `ctypes`; the MLX-LM version is `null` when `--version` prints none (the old fallback read the interpreter's package metadata); LM Studio's `lms version --json` build identity is no longer recorded |
| `runtimes`, `catalog` | Kept. `catalog` adds `verified_on`, `stale_after`, `age_days` and exits 1 when stale (E87); it no longer profiles the machine first, so it runs anywhere, including CI |
| `recommend [--runtime lm_studio]` | Kept. New policy field `excluded_families`; with no `required_families`, the implied families are those that survive exclusions; a policy context above an artifact's catalog sizing blocks it; plans carry a stale-catalog warning |
| `install [--runtime] [--artifact ID]... [--machine-label] [--yes]` | Kept, with the inventory write after each verified artifact |
| `install --recover-cached`, and the automatic import after a failed pull | Cut. Rerunning the pull reuses the layers Ollama holds; text in preserved.md |
| `verify --artifact ID [--runtime]` | Cut. `install --yes` verifies as it lands; re-check with `ollama list` or a re-run of `install` (references/commands.md) |
| `benchmark --artifact ID [--prompt-file] [--output-dir] [--num-predict] [--num-ctx] [--think]` | Cut. The same bounded call and acceptance rules run against Ollama's loopback API (references/commands.md) |
| `inventory [--save] [--machine-label]` | Cut. `install --yes` registers the machine; read `machines.json` directly |
| `resolve --family F \| --artifact ID` | Cut. The rule for reading the machine map is in references/selection-and-boundaries.md |
| `update --model NAME... \| --all [--receipt-dir DIR] [--yes]` | Kept. No longer rewrites the inventory after an update; the receipt carries the new identity |
| `configure-ollama --kv-cache-type T [--yes]` | Kept |
| Catalog schema 1 | No longer read (legacy format); the bundled catalog is schema 2 |
| `update --yes` | Now also refuses a model store inside a protected root, as install always did |

### Edge cases

| Edge case | Tests holding it |
|---|---|
| E85: an excluded family is never selected, by recommend or by an explicit install | `test_e85_excluded_family_is_never_recommended`, `test_e85_excluded_lineage_and_organization_are_applied_before_ranking`, `test_e85_explicit_install_cannot_bypass_a_family_exclusion`, `test_e85_an_override_cannot_name_an_excluded_artifact` |
| E86: limited memory or disk reserve refuses oversized artifacts | `test_e86_limited_memory_refuses_oversized_artifacts_and_keeps_the_one_that_fits`, `test_e86_minimum_memory_fit_needs_explicit_policy_permission`, `test_e86_unknown_memory_stays_unknown_and_blocks`, `test_e86_disk_reserve_refuses_an_oversized_plan`, `test_e86_context_beyond_the_catalog_sizing_is_refused` |
| E86: installs need `--yes` | `test_e86_install_without_yes_is_a_dry_run` (also `test_update_without_yes_pulls_nothing`, `test_configure_ollama_dry_run_changes_nothing`) |
| E86: a failed pull writes no inventory | `test_e86_failed_pull_writes_no_inventory`, `test_e86_a_pull_that_is_not_listed_with_the_catalog_digest_writes_no_inventory`, `test_lm_studio_failed_or_ambiguous_download_writes_no_inventory` |
| E86: a cached GGUF is imported only when every digest and size matches | Cut with cached-layer recovery: no import path remains, so nothing is imported. The old tests (`test_failed_registry_pull_uses_pinned_cached_gguf_import`, `test_cached_gguf_import_rejects_digest_mismatch`) stay readable at origin/main |
| E87: the catalog is flagged stale after three months | `test_e87_catalog_more_than_three_months_old_is_stale`, `test_e87_catalog_command_flags_a_synthetic_old_catalog_and_exits_1`, `test_e87_recommend_warns_on_a_stale_catalog_without_blocking` |

The catalog evidence that section 5 item 13 of the evaluation asks M3 to list is held by
`test_bundled_catalog_is_valid_with_four_families_and_lm_studio_targets`,
`test_catalog_validation_refuses_unsafe_or_malformed_entries` and
`test_the_article_example_selects_four_artifacts_on_128_gib`. The article's printed commands are
held by `test_every_command_the_article_prints_still_parses`.

### Old tests and where their scenarios went

Catalog validity, duplicates, credential URLs and LM Studio match terms: the two catalog tests.
The 128 GiB overrides, runtime version, KV cache, disk reserve, minimum-memory fit, base-family
exclusion and explicit bypass: the recommendation and E85/E86 tests above. Duplicate explicit
ids: `test_explicit_ids_must_be_unique_catalog_ids`. UUID-like values, `~/workspaces` and
explicit protected roots: the profile and store tests. Random machine id, merged selections and
a symlinked state root: `test_install_records_verified_identity_and_merges_selections`,
`test_install_refuses_a_symlinked_state_directory`. Managed and direct runtimes:
`test_runtimes_distinguish_managed_and_direct_capabilities`. LM Studio targets, install, failed
download and blocked update: the LM Studio tests. Update plan, changed and already-current
receipts, failure: the update tests. `:latest` normalization and the bounded HTTP error body:
their own tests. The three Homebrew service tests: the configure-ollama tests. Dropped with their
code: inventory refresh after update, `resolve` (two tests), cached-layer recovery (four tests),
benchmark thinking and length-stop checks (four tests; the acceptance rules are now prose in
references/commands.md).

### Replaced passages

Every line replaced in this pass is in references/preserved.md, verbatim, under its file:

- SKILL.md: the line introducing the binding rules, rules 10 and 11, three Contents lines and
  the Subcommands section. Rules 17 and 18 are new (E85, E87).
- references/commands.md: the opening line and contents list, cached-layer recovery, `verify`
  and `benchmark`, and the `--think` paragraph. New: exit codes and the three-month rule, failed
  pulls, verifying and benchmarking with Ollama itself.
- references/selection-and-boundaries.md: the contents line, two recovery bullets,
  `inventory --save` and `resolve`, and the runtime-boundary opening. New: exclusions-first and
  context bullets, reading the machine map, the stale-catalog failure rule.
- references/architecture.md: installation transitions, the adapter's generation and unload
  requirements, the multi-GGUF recovery path, catalog schema 1, and updates refreshing the
  inventory.
- references/catalog-maintenance.md: pinning layers for recovery. New: the Catalog age section.
- references/security-and-privacy.md: the recovery rule and the local API paragraph.
