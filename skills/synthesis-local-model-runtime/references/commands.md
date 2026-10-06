# Local model runtime: commands

Every documented command, exactly as written, with what each step requires. Read before installing, recovering, verifying, benchmarking, updating or reconfiguring Ollama.

Contents:
- Quick start: profile, runtimes, catalog, recommend, install (Ollama default)
- LM Studio instead of Ollama; installing explicit catalog entries
- Recovering cached Hugging Face layers (`--recover-cached`)
- Verifying and benchmarking an installed artifact
- Updating installed models (`update --model`, `--all`, `--receipt-dir`), LM Studio update block
- Benchmark reasoning mode (`--think`)
- Ollama KV-cache configuration (`configure-ollama`)

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
