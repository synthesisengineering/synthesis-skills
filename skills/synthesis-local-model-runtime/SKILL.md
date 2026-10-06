---
name: synthesis-local-model-runtime
description: "Profile a computer, compare Ollama, LM Studio, llama.cpp and MLX-LM, recommend open-weight models that fit its memory and storage, install and update them with identity receipts, and verify inference. Use for local models, Ollama, which model fits this Mac or PC, model inventory or local benchmarks."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Local Model Runtime

Select local models from measured capacity and dated artifact evidence. Do not
turn a model name, parameter count, vendor origin, or successful launch into a
claim that an artifact is safe, private, independent, unmarked, or suitable for
every workload.

## Binding rules

Rules 1 to 11 are the operating contract in its original order (10 and 11 changed in v5; references/preserved.md keeps the old text); 12 to 18 distill references/selection-and-boundaries.md and references/catalog-maintenance.md.

1. Profile the machine with `scripts/local_model_runtime.py profile`. The
   profiler emits only selection-relevant fields. It never emits hostnames,
   serial numbers, hardware UUIDs, provisioning identifiers, or account data.
2. Validate the bundled catalog before using it:
   `scripts/local_model_runtime.py catalog`.
3. Inspect `runtimes` and choose a managed environment. Ollama is the default;
   LM Studio is the optional managed alternative. llama.cpp and MLX-LM are
   reported as direct runtimes with their actual capability boundaries.
4. Load any local policy and create a dry-run plan. Recommendation applies
   exclusions first, then hard memory, storage, and runtime-configuration
   gates, then quality ordering.
5. Present the exact artifacts, quantizations, distribution channels, disk
   estimate, remaining free space, runtime prerequisites, and reasons.
6. Install only after the user authorizes the downloads. `install` is dry-run
   unless `--yes` is supplied.
7. Verify the runtime's resolved artifact metadata. Record what actually
   installed, not what the catalog predicted.
8. Update installed Ollama models only through an explicit model list or
   explicit `--all`. `update` is dry-run unless `--yes` is supplied and records
   both identities even when the pull is an already-current no-op.
9. Run bounded functional and performance checks one model at a time. Unload
   each model after testing.
10. Update the per-machine inventory only after verified state transitions.
   Separate installation commands merge their verified selections; a failed
   pull writes nothing.
11. When a pull fails, rerun the same install later: Ollama keeps the layers it
   already holds. Never import a partial download by hand.
12. **Weights must fit with operating and context headroom;** disk fit alone is never enough.
13. **Never silently replace a requested artifact or quantization;** a changed plan needs a new visible diff.
14. **Model stores stay outside source repositories, synthesis workspaces, iCloud Drive and protected roots;** never move model binaries by hand.
15. **Never invent:** missing hardware facts stay `unknown`, a failed pull or update never claims a change, and changed state after planning means re-plan.
16. **Possession is not provenance.** This skill does not establish training-data provenance, watermark absence, authorship or trustworthiness.
17. **Exclusions bind explicit requests too:** an `--artifact` in an excluded family, organization, lineage or artifact list is blocked, never installed.
18. **The catalog is dated evidence:** more than three months after `verified_on` it is stale (`catalog` exits 1); re-verify the entries you rely on first.

## Contents

- [references/commands.md](references/commands.md): every command with its flags: LM Studio, explicit artifacts, exit codes and the stale catalog, failed pulls, verifying and benchmarking with Ollama itself, update, `configure-ollama`. Read it before running anything beyond the quick start.
- [references/selection-and-boundaries.md](references/selection-and-boundaries.md): recommendation rules (exclusions first), storage guard, the per-machine mapping and how automation reads it, runtime and capability boundaries, failure handling. Read it when choosing artifacts or reporting results.
- [references/architecture.md](references/architecture.md): read it when extending the runtime or inventory schema.
- [references/catalog-maintenance.md](references/catalog-maintenance.md): read it before changing model records.
- [references/security-and-privacy.md](references/security-and-privacy.md): read it when reviewing downloads, identifiers, paths or subprocess behavior.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.1.0 text and of the old script now lives (ruling D8).
- [references/preserved.md](references/preserved.md): read when you need the cut subcommands (`verify`, `benchmark`, `inventory`, `resolve`, `--recover-cached`) or any passage replaced in v5, verbatim.
- Quick start, Subcommands: below.

## Quick start

```bash
python3 scripts/local_model_runtime.py profile
python3 scripts/local_model_runtime.py runtimes
python3 scripts/local_model_runtime.py catalog
python3 scripts/local_model_runtime.py recommend \
  --policy assets/policy.example.json
python3 scripts/local_model_runtime.py install \
  --policy assets/policy.example.json
```

The final command prints a complete non-mutating plan. Repeat it with `--yes`
only after the named artifacts and total download size are authorized.

## Subcommands

Every subcommand of `scripts/local_model_runtime.py` prints JSON. A plan that is not ready, a failed pull, update or service change, or invalid input exits 2; `catalog` exits 1 when the catalog is stale.

- `profile`, `runtimes`: the privacy-safe hardware profile; runtime availability and capability.
- `catalog`: the validated catalog summary with `verified_on`, `stale_after` and `age_days`.
- `recommend [--runtime lm_studio]`: one fitting artifact per family.
- `install [--runtime lm_studio] [--artifact ID]... [--machine-label NAME] [--yes]`: the plan, or the installed, verified artifacts and the inventory path.
- `update --model NAME... | --all [--receipt-dir DIR] [--yes]`: the update plan, or the before-and-after identity receipt.
- `configure-ollama --kv-cache-type f16|q8_0|q4_0 [--yes]`: the validated Homebrew service change.
- Every command takes `--policy FILE`, `--catalog FILE`, `--state-dir DIR`, `--model-store DIR`, `--protected-root DIR`.

Verify and benchmark with Ollama itself (references/commands.md).
