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

Rules 1 to 11 are the operating contract, verbatim and in its original order; 12 to 16 distill the rules in references/selection-and-boundaries.md.

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
   Separate installation commands merge their verified selections; an
   explicit inventory refresh replaces selections with the current plan.
11. When a Hugging Face registry pull fails after catalog-pinned GGUF layers are
   cached, permit the deterministic local-import recovery only after every full
   digest and exact size matches. Never import an unpinned partial download.
12. **Weights must fit with operating and context headroom;** disk fit alone is never enough.
13. **Never silently replace a requested artifact or quantization;** a changed plan needs a new visible diff.
14. **Model stores stay outside source repositories, synthesis workspaces, iCloud Drive and protected roots;** never move model binaries by hand.
15. **Never invent:** missing hardware facts stay `unknown`, a failed pull or update never claims a change, and changed state after planning means re-plan.
16. **Possession is not provenance.** This skill does not establish training-data provenance, watermark absence, authorship or trustworthiness.

## Contents

- [references/commands.md](references/commands.md): every command with its flags: LM Studio, explicit artifacts, cached-layer recovery, verify, benchmark, update, `configure-ollama`. Read it before running anything beyond the quick start.
- [references/selection-and-boundaries.md](references/selection-and-boundaries.md): recommendation rules, storage guard, per-machine mapping and `resolve`, runtime and capability boundaries, failure handling. Read it when choosing artifacts or reporting results.
- [references/architecture.md](references/architecture.md): read it when extending the runtime or inventory schema.
- [references/catalog-maintenance.md](references/catalog-maintenance.md): read it before changing model records.
- [references/security-and-privacy.md](references/security-and-privacy.md): read it when reviewing downloads, identifiers, paths or subprocess behavior.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.1.0 text now lives (ruling D8).
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

Every subcommand of `scripts/local_model_runtime.py` prints JSON; a plan that is not ready, a failed verification or receipt, or a blocked run exits 2.

- `profile`, `runtimes`, `catalog`: the privacy-safe hardware profile, runtime availability and capability, the validated catalog summary.
- `recommend [--runtime lm_studio]`: one fitting artifact per family.
- `install [--artifact ID] [--recover-cached] [--yes]`: the plan, or the executed result.
- `verify --artifact ID`, `benchmark --artifact ID --output-dir DIR [--think]`: identity check; bounded sample receipt.
- `update --model NAME | --all [--receipt-dir DIR] [--yes]`: the update plan, or before-and-after identity receipts.
- `inventory --save`, `resolve --family NAME`: register this machine; the exact runtime name and identity for automation.
- `configure-ollama --kv-cache-type f16 [--yes]`: the validated Homebrew service change.
