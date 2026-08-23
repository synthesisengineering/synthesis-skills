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

# Synthesis Local Model Runtime

Select local models from measured capacity and dated artifact evidence. Do not
turn a model name, parameter count, vendor origin, or successful launch into a
claim that an artifact is safe, private, independent, unmarked, or suitable for
every workload.

## Operating contract

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

To use LM Studio instead of the default Ollama adapter, install its `lms` CLI,
then select the runtime explicitly. The catalog must contain an exact LM Studio
target for every requested artifact:

```bash
python3 scripts/local_model_runtime.py recommend \
  --runtime lm_studio \
  --policy assets/policy.example.json
python3 scripts/local_model_runtime.py install \
  --runtime lm_studio \
  --artifact qwen3.8-27b-q8-0
```

The second command is a dry run. Add `--yes` only after inspecting the exact
Hugging Face repository, quantization, publisher, and disk estimate.

To install explicit catalog entries instead of policy selections:

```bash
python3 scripts/local_model_runtime.py install \
  --artifact qwen3.8-27b-q8-0 \
  --artifact glm-4.7-flash-q8-0 \
  --yes
```

If an authorized Hugging Face pull already cached every catalog-pinned GGUF
layer but failed during final registry metadata retrieval, inspect the dry run
and then recover without repeating the network request:

```bash
python3 scripts/local_model_runtime.py install \
  --artifact qwen3.8-27b-q8-0 \
  --recover-cached
python3 scripts/local_model_runtime.py install \
  --artifact qwen3.8-27b-q8-0 \
  --recover-cached \
  --yes
```

Recovery fails closed unless every required cached layer matches the catalog's
full SHA-256 digest and exact byte size. Its receipt reports zero network
transfer separately from worst-case additional runtime materialization. Ollama
may normalize the GGUF into a new runtime layer and retain the original cache;
hard links eliminate only a separate staging copy.

To verify and benchmark an installed artifact:

```bash
python3 scripts/local_model_runtime.py verify \
  --artifact qwen3.8-27b-q8-0
python3 scripts/local_model_runtime.py benchmark \
  --artifact qwen3.8-27b-q8-0 \
  --output-dir /path/outside/the/source/repository
```

LM Studio verification uses its JSON inventory and a catalog identity made
from repository and quantization terms. That is a runtime-metadata identity,
not a content digest. Ollama verification retains the stronger local digest.

## Updating installed models

Plan updates by naming the installed Ollama models exactly:

```bash
python3 scripts/local_model_runtime.py update \
  --model gemma4:e4b \
  --model gemma4:26b \
  --model gemma4:31b
```

Execute the same plan only after inspection:

```bash
python3 scripts/local_model_runtime.py update \
  --model gemma4:e4b \
  --model gemma4:26b \
  --model gemma4:31b \
  --receipt-dir /path/outside/the/source/repository \
  --yes
```

Use `--all` instead of repeated `--model` flags only when every installed
Ollama model is in scope. The command rejects unknown or uninstalled names,
uses argument-array subprocesses, re-enumerates each model after its pull, and
compares digest and size. An unchanged digest is a successful
`already-current` result, not an unverified assumption. A failed pull or a
model missing after the pull makes the receipt fail.

LM Studio model updates remain blocked. Its CLI supports downloads and JSON
inventory, but the skill has no stable content identity with which to prove
that a re-download replaced an installed model. It does not turn a download
attempt into an update claim.

Benchmarks set the Ollama `think` field to `false` by default so a bounded token
budget measures the requested final response. Pass `--think` only when the
reasoning trace is itself the workload under evaluation; the receipt records
the chosen mode. The receipt rejects length-stopped output and detects raw
`<think>` markup. When reasoning was requested off, leaked markup is preserved
as evidence but is not accepted as a final-response benchmark.

Some model architectures require a specific Ollama KV-cache representation.
The planner compares catalog requirements with the effective service setting
and blocks an incompatible plan. On a macOS Homebrew service, inspect the
validated change before applying it:

```bash
python3 scripts/local_model_runtime.py configure-ollama \
  --kv-cache-type f16
python3 scripts/local_model_runtime.py configure-ollama \
  --kv-cache-type f16 \
  --yes
```

The mutating command accepts only the standard current-user Homebrew
LaunchAgent with the expected label and `ollama serve` command. It writes a
private backup, changes one allowlisted environment value, reloads the service,
waits for a healthy loopback API, and restores the prior plist if reload fails.

## Recommendation rules

- Model weights must fit along with the declared operating and context
  headroom. Disk fit alone is never enough.
- Prefer the highest-ranked artifact that meets recommended memory. Use a
  minimum-memory fit only when policy permits it, and label it constrained.
- Account for all artifacts in a multi-model installation plan, even though
  only one is loaded at a time.
- A larger total parameter count can still be faster when only a small MoE
  subset activates per token. Record total and active parameters separately.
- Context-window marketing is not a memory plan. The catalog's
  `planning_context_tokens` is the bounded sizing assumption; a larger context
  needs a fresh plan and benchmark.
- Prefer curated runtime artifacts when quality is comparable. When a
  community quantization is required, record both the upstream model owner and
  the artifact publisher, then capture the resolved local digest.
- Never silently replace a requested artifact or quantization. A changed plan
  requires a new visible diff.
- A local-import recovery preserves the catalog artifact id and runtime model
  name but records `catalog-pinned-local-import` as the installation method.
  It is a recovery path for verified cached layers, not another acquisition
  channel.
- Never equate zero recovery download with zero disk growth. Budget the exact
  cached-layer total as worst-case additional runtime materialization.

## Storage guard

Model stores must stay outside source repositories, synthesis workspaces,
iCloud Drive, and other declared protected roots. The tool resolves Ollama's
effective store from an explicit flag, `OLLAMA_MODELS`, the macOS Homebrew
service configuration when available, or the standard `~/.ollama/models`
default. It refuses installation when that path is protected or cannot be
validated.

Do not move existing model binaries by hand. A runtime-owned model store may
be content-addressed and shared across model names.

## Per-machine mapping

The state directory defaults to `~/.synthesis/local-models/`. A successful
installation creates a random opaque machine id and updates `machines.json`
atomically. The mapping contains the safe hardware profile, selected catalog
ids, resolved runtime metadata, verification results, and timestamps. It does
not derive identity from hardware serials.

Use `inventory --save` to register or refresh a machine without installing.
Export the JSON when comparing several computers. Friendly machine labels are
optional and should not contain private organization or client names.

Automation should call `resolve --family <family>` before using a local model.
Resolution succeeds only when the current opaque machine record both selects
and verifies that artifact; it returns the exact runtime name and the strongest
available identity. Ollama uses a content digest. LM Studio uses a labeled
runtime-metadata identity. This makes the mapping an enforcement input rather
than a passive spreadsheet.

## Runtime boundary

Version 1.1 uses capability-graded adapters:

- Ollama is the default managed runtime. It supports catalog planning,
  installation, inventory, digest verification, bounded benchmarks, service
  configuration, and verified updates.
- LM Studio is an optional managed runtime. It supports catalog planning,
  noninteractive exact downloads through `lms get`, JSON inventory, and
  runtime-metadata verification. Verified model-content updates and the
  skill's benchmark protocol are not supported.
- llama.cpp and MLX-LM are substantial direct runtimes for execution and local
  serving. The profile detects them and reports their capabilities, but the
  skill does not own their model acquisition or lifecycle.

Use `runtimes` to see both availability and capability. Never infer one
runtime's lifecycle semantics from another runtime's popularity.

Read [references/architecture.md](references/architecture.md) when extending
the runtime or inventory schema. Read
[references/catalog-maintenance.md](references/catalog-maintenance.md) before
changing model records. Read
[references/security-and-privacy.md](references/security-and-privacy.md) when
reviewing downloads, identifiers, paths, or subprocess behavior.

## Capability boundary

This skill establishes local possession, runtime identity, bounded functional
behavior, and observed performance. It does not establish:

- training-data provenance;
- the absence or presence of a text watermark;
- authorship or human authorship;
- freedom from hidden behavior;
- legal suitability for a particular use;
- trustworthiness based on a model provider's country or reputation.

Use a provenance skill for generation manifests and integrity receipts. Use a
writing-quality skill for prose evaluation. Neither should feed detector scores
into an evasion or watermark-removal loop.

## Failure handling

- Missing or malformed hardware facts remain `unknown`; never invent them.
- A runtime below an artifact's minimum version blocks installation.
- A failed pull never creates an installed inventory record.
- A failed update produces a failed receipt and never claims the model changed.
- A model absent from the runtime after a reported pull is a failure.
- A runtime without a provable update identity remains blocked for updates.
- A functional check and a benchmark are separate. Preserve both results.
- Installed metadata is not a functional pass. A model that cannot generate
  under the effective runtime configuration remains unusable until that
  incompatibility is resolved and the bounded benchmark passes.
- If disk, runtime, or model state changes after planning, rerun the plan.
