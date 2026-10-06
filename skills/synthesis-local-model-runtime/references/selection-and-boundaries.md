# Local model runtime: selection rules and boundaries

Read when choosing artifacts, placing a model store, using the per-machine mapping from automation, deciding what a runtime can do, stating what a result proves, or handling a failure.

Contents:
- Recommendation rules
- Storage guard
- Per-machine mapping (`inventory --save`, `resolve --family`)
- Runtime boundary: Ollama, LM Studio, llama.cpp and MLX-LM
- Capability boundary: what this skill does not establish
- Failure handling

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

Read [references/architecture.md](architecture.md) when extending
the runtime or inventory schema. Read
[references/catalog-maintenance.md](catalog-maintenance.md) before
changing model records. Read
[references/security-and-privacy.md](security-and-privacy.md) when
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
