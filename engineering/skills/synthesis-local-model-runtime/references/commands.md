# Local model runtime: commands

Every documented command, exactly as written, with what each step requires. Read before installing, verifying, benchmarking, updating or reconfiguring Ollama.

Contents:
- Quick start: profile, runtimes, catalog, recommend, install (Ollama default)
- LM Studio instead of Ollama; installing explicit catalog entries
- Exit codes and the catalog's three-month rule
- When a pull fails
- Verifying and benchmarking an installed artifact (with Ollama itself)
- Updating installed models (`update --model`, `--all`, `--receipt-dir`), LM Studio update block
- Benchmark reasoning mode (`think`)
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

An explicit `--artifact` request still passes every policy exclusion and every
memory, context, disk, runtime-version and KV-cache gate; a blocked plan refuses
`--yes`. `install --machine-label NAME` sets an optional friendly label in the
inventory (no organization or client names). Every command also takes
`--catalog FILE`, `--policy FILE`, `--state-dir DIR` (inventory and service
backups, default `~/.synthesis/local-models/`), `--model-store DIR` and
`--protected-root DIR` (repeatable).

## Exit codes and the catalog's three-month rule

Every command prints JSON. Exit 0 means done, or the plan is ready; exit 2
means blocked, invalid or failed, with `{"error": ..., "status": "blocked"}`.
`catalog` exits 1 when the catalog is valid but stale: its `verified_on` date is
more than three calendar months old. Its JSON then carries `"status": "stale"`,
`stale_after`, `age_days` and a warning, and `recommend` and `install` add the
same warning to their plans without blocking them. Treat a stale catalog's
sizes, tags and runtime requirements as cached evidence: re-verify the entries
you rely on (catalog-maintenance.md) before authorizing a download.

## When a pull fails

A failed pull is a failure: the command exits 2 and writes nothing to the
inventory. Rerun the same `install ... --yes` later; Ollama skips the layers it
already holds, so only the missing pieces transfer again. Never import a
partial download by hand or treat a completed progress bar as proof of content.

## Verifying and benchmarking an installed artifact

`install --yes` already verifies each artifact: after the pull it lists the
model again, requires a content digest, checks the catalog's
`expected_digest_prefix` when there is one, and only then records it. To
re-check later, compare the ID column of `ollama list` with that prefix, or
rerun `install --artifact ID --yes`, which pulls (a no-op when current),
re-verifies and refreshes the inventory record.

Run the bounded functional and performance check with Ollama's own loopback
API, one model at a time; `keep_alive: 0` unloads the model afterwards:

```bash
curl -s http://127.0.0.1:11434/api/generate -d '{
  "model": "hf.co/bartowski/Qwen3.8-27B-GGUF:Q8_0",
  "prompt": "Explain one practical benefit and one limitation of running an open-weight language model locally.",
  "stream": false, "think": false, "keep_alive": 0,
  "options": {"temperature": 0, "seed": 7, "num_predict": 256, "num_ctx": 8192}
}' > /path/outside/the/source/repository/qwen3.8-27b-q8-0-benchmark.json
```

Accept the run only when `response` is non-empty, `done_reason` is `stop`, and,
with `think` false, the response holds no `<think>` markup. Speed is
`eval_count / eval_duration * 1e9` tokens per second. Keep the saved JSON as the
receipt; a run that merely returned bytes is not a functional pass.

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

The receipt is the printed JSON; `--receipt-dir` also saves it there as
`ollama-update-<UTC timestamp>.json` and refuses a directory inside the skill.
The first failure stops the run and exits 2. An update does not rewrite the
inventory: its record keeps the identity verified at install, and the receipt
holds the new one.

LM Studio model updates remain blocked. Its CLI supports downloads and JSON
inventory, but the skill has no stable content identity with which to prove
that a re-download replaced an installed model. It does not turn a download
attempt into an update claim.

Benchmarks set the Ollama `think` field to `false` by default so a bounded token
budget measures the requested final response. Set it to `true` only when the
reasoning trace is itself the workload under evaluation, and record the chosen
mode with the receipt. Reject length-stopped output. When reasoning was
requested off, leaked `<think>` markup is preserved as evidence but is not
accepted as a final-response benchmark.

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
