# Local model runtime: preserved text

Passages replaced on 2026-10-05 when `scripts/local_model_runtime.py` was slimmed from 2,640 to
about 800 lines (v5 code verdict: SLIM, "keep profile, catalog check, recommend and a thin install and
update over Ollama; keep the documented command names"). Each is kept verbatim with the file it came
from; the replacement sits at the same place in that file, and references/coverage-map.md
(`## Scripts in v5 (M3)`) says what replaced each piece. The old script and its tests stay readable
with `git show origin/main:skills/synthesis-local-model-runtime/scripts/local_model_runtime.py`.

Contents:
- Why these subcommands went
- Commands of subcommands cut in M3 (`verify`, `benchmark`, `inventory`, `resolve`, `--recover-cached`)
- Cached-layer recovery: the incident, the rule and the mechanism (cut in M3)
- The per-machine resolver and inventory refresh (cut in M3)
- Other replaced lines (catalog schema 1, the version label, contents lists)

## Why these subcommands went

The published article "Choosing local models by measuring the machine" (2026-08-23) prints
`profile`, `runtimes`, `catalog`, `recommend`, `install`, `update` and `configure-ollama`, and
those still work with the flags it prints. It prints none of the five below, and no skill or live
script calls them; a script in one closed 2026-08 research project ran `benchmark`. They were cut
to fit the slim script:

- `verify` and `benchmark` re-implemented what Ollama already offers. `install --yes` verifies
  each artifact as it lands, `ollama list` shows the digest prefix, and the bounded benchmark
  runs against Ollama's loopback API with the same settings and acceptance rules
  (references/commands.md).
- `inventory --save` and `resolve` maintained and read the machine map; `install --yes` still
  writes it, and references/selection-and-boundaries.md says how automation reads it.
- `--recover-cached` imported catalog-pinned GGUF layers after a registry timeout. The one
  machine inventory on record shows it used once, on 2026-08-23, for one of four installs.
  Ollama keeps the layers it already holds, so rerunning the pull repeats only the missing
  pieces; the recovery saved waiting for the registry, at the cost of a hard-link and re-hash
  path through runtime-owned storage.

## Commands of subcommands cut in M3

### SKILL.md: the Subcommands section

````markdown
## Subcommands

Every subcommand of `scripts/local_model_runtime.py` prints JSON; a plan that is not ready, a failed verification or receipt, or a blocked run exits 2.

- `profile`, `runtimes`, `catalog`: the privacy-safe hardware profile, runtime availability and capability, the validated catalog summary.
- `recommend [--runtime lm_studio]`: one fitting artifact per family.
- `install [--artifact ID] [--recover-cached] [--yes]`: the plan, or the executed result.
- `verify --artifact ID`, `benchmark --artifact ID --output-dir DIR [--think]`: identity check; bounded sample receipt.
- `update --model NAME | --all [--receipt-dir DIR] [--yes]`: the update plan, or before-and-after identity receipts.
- `inventory --save`, `resolve --family NAME`: register this machine; the exact runtime name and identity for automation.
- `configure-ollama --kv-cache-type f16 [--yes]`: the validated Homebrew service change.
````

### references/commands.md: opening line and contents list

````markdown
Every documented command, exactly as written, with what each step requires. Read before installing, recovering, verifying, benchmarking, updating or reconfiguring Ollama.

Contents:
- Quick start: profile, runtimes, catalog, recommend, install (Ollama default)
- LM Studio instead of Ollama; installing explicit catalog entries
- Recovering cached Hugging Face layers (`--recover-cached`)
- Verifying and benchmarking an installed artifact
- Updating installed models (`update --model`, `--all`, `--receipt-dir`), LM Studio update block
- Benchmark reasoning mode (`--think`)
- Ollama KV-cache configuration (`configure-ollama`)
````

### references/commands.md: verify and benchmark

````markdown
To verify and benchmark an installed artifact:

```bash
python3 scripts/local_model_runtime.py verify \
  --artifact qwen3.8-27b-q8-0
python3 scripts/local_model_runtime.py benchmark \
  --artifact qwen3.8-27b-q8-0 \
  --output-dir /path/outside/the/source/repository
```
````

### references/commands.md: benchmark reasoning mode (`--think`)

````markdown
Benchmarks set the Ollama `think` field to `false` by default so a bounded token
budget measures the requested final response. Pass `--think` only when the
reasoning trace is itself the workload under evaluation; the receipt records
the chosen mode. The receipt rejects length-stopped output and detects raw
`<think>` markup. When reasoning was requested off, leaked markup is preserved
as evidence but is not accepted as a final-response benchmark.
````

## Cached-layer recovery: the incident, the rule and the mechanism

The recovery came from a live install in which every large GGUF layer downloaded but a final registry request timed out. The lessons it recorded (a completed progress bar proves nothing; zero network transfer is not zero disk growth; never import an unpinned partial download) are kept in the rules that replaced these lines.

### SKILL.md: binding rule 11

````markdown
11. When a Hugging Face registry pull fails after catalog-pinned GGUF layers are
   cached, permit the deterministic local-import recovery only after every full
   digest and exact size matches. Never import an unpinned partial download.
````

### references/commands.md: recovering cached Hugging Face layers

````markdown
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
````

### references/selection-and-boundaries.md: recommendation rules on recovery

````markdown
- A local-import recovery preserves the catalog artifact id and runtime model
  name but records `catalog-pinned-local-import` as the installation method.
  It is a recovery path for verified cached layers, not another acquisition
  channel.
- Never equate zero recovery download with zero disk growth. Budget the exact
  cached-layer total as worst-case additional runtime materialization.
````

### references/architecture.md: the local multi-GGUF create path

````markdown
For Hugging Face registry timeouts after all large layers are present, the
adapter may use Ollama's supported local multi-GGUF create path. The catalog
pins the registry manifest URL plus each GGUF model/projector layer's full
digest, media type, and size. The adapter re-hashes every cached layer, creates
same-volume temporary hard links, imports the directory, removes the links,
and then applies the normal runtime identity and inventory gates.
The hard links eliminate a separate staging copy. Ollama may still normalize a
GGUF into a new runtime layer and retain the registry cache, so the recovery
receipt budgets the full layer total as possible additional disk use.
````

### references/catalog-maintenance.md: pinning layers for recovery

````markdown
For a Hugging Face artifact with local-import recovery, fetch its public
Ollama-compatible registry manifest and pin only GGUF model/projector layers.
Record each full digest, media type, and byte size plus the manifest URL. Do not
pin a layer from terminal progress output or infer it from a repository file
name.
````

### references/security-and-privacy.md: the recovery rule

````markdown
- A registry-timeout recovery must use only catalog-pinned cached GGUF layers,
  verify their full SHA-256 digests and exact sizes, and create same-volume
  temporary hard links. `--recover-cached` must skip acquisition rather than
  retrying the failed registry request. Never accept a filename or a completed
  progress bar as content verification.
````

## The per-machine resolver and inventory refresh

### SKILL.md: binding rule 10

````markdown
10. Update the per-machine inventory only after verified state transitions.
   Separate installation commands merge their verified selections; an
   explicit inventory refresh replaces selections with the current plan.
````

### references/selection-and-boundaries.md: contents line

````markdown
- Per-machine mapping (`inventory --save`, `resolve --family`)
````

### references/selection-and-boundaries.md: `inventory --save` and `resolve`

````markdown
Use `inventory --save` to register or refresh a machine without installing.
Export the JSON when comparing several computers. Friendly machine labels are
optional and should not contain private organization or client names.

Automation should call `resolve --family <family>` before using a local model.
Resolution succeeds only when the current opaque machine record both selects
and verifies that artifact; it returns the exact runtime name and the strongest
available identity. Ollama uses a content digest. LM Studio uses a labeled
runtime-metadata identity. This makes the mapping an enforcement input rather
than a passive spreadsheet.
````

### references/architecture.md: installation transitions

````markdown
Installation transitions merge selections so an explicit one-model command
cannot erase earlier verified choices. A deliberate inventory refresh replaces
the selection set with the policy's current recommendation.
````

### references/architecture.md: updates refreshing the inventory

````markdown
`--all` means every installed Ollama model. It is never the implicit default.
When an existing per-machine inventory maps one of the updated names, the
successful result refreshes that record atomically. Models outside the
inventory still receive receipts without creating an opaque machine identity.
````

## Other replaced lines

### SKILL.md: the line introducing the binding rules

````markdown
Rules 1 to 11 are the operating contract, verbatim and in its original order; 12 to 16 distill the rules in references/selection-and-boundaries.md.
````

### SKILL.md: Contents lines

````markdown
- [references/commands.md](references/commands.md): every command with its flags: LM Studio, explicit artifacts, cached-layer recovery, verify, benchmark, update, `configure-ollama`. Read it before running anything beyond the quick start.
- [references/selection-and-boundaries.md](references/selection-and-boundaries.md): recommendation rules, storage guard, per-machine mapping and `resolve`, runtime and capability boundaries, failure handling. Read it when choosing artifacts or reporting results.

- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.1.0 text now lives (ruling D8).
````

### references/selection-and-boundaries.md: runtime boundary opening (the version label and benchmarks)

````markdown
Version 1.1 uses capability-graded adapters:

- Ollama is the default managed runtime. It supports catalog planning,
  installation, inventory, digest verification, bounded benchmarks, service
  configuration, and verified updates.
````

### references/architecture.md: managed adapter requirements (generation and unload moved to the documented benchmark)

````markdown
An adapter must implement:

- version discovery;
- effective model-store discovery or an explicit unverifiable result;
- non-mutating installed-model enumeration;
- installation by argument-array subprocess with no shell evaluation;
- resolved artifact metadata including a local digest or content identity;
- an explicit capability map;
- a loopback-only bounded generation call when benchmarking is supported;
- explicit unload when benchmarking is supported;
- before-and-after content identity when updates are supported.

````

### references/architecture.md: catalog schema 1 (the slim script reads schema 2 only)

````markdown
Catalog schema 1 remains readable as Ollama-only input. Schema 2 adds optional
runtime targets. An absent LM Studio target blocks that artifact for LM Studio;
the planner may select another verified artifact in the family, but it never
constructs a target from model-name similarity.
````

### references/security-and-privacy.md: local API (the script now sends no prompts)

````markdown
Generation and metadata calls use loopback HTTP only. The executable has no
option to send prompts to a remote host. A future remote adapter is a separate
capability and requires its own disclosure and credential review.
````
