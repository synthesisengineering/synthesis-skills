# Architecture

## Layers

1. **Safe profile:** read-only hardware, storage, runtime, and effective
   serving-configuration facts. The output schema deliberately has no field
   for a hostname, serial, hardware UUID, account, or network address.
2. **Catalog:** dated, reviewable artifact facts. An entry identifies the
   upstream model and the separately accountable quantization publisher.
3. **Policy:** local choices such as required families, excluded organizations,
   exact overrides, protected paths, and retained resource headroom.
4. **Planner:** deterministic filtering and ranking against the safe profile.
5. **Runtime adapter:** capability-graded planning, acquisition, enumeration,
   verification, update, execution, serving, and configuration behavior.
6. **Inventory:** an atomic map from an opaque locally generated machine id to
   the safe profile, intended selections, and resolved installed artifacts.

Installation transitions merge selections so an explicit one-model command
cannot erase earlier verified choices. A deliberate inventory refresh replaces
the selection set with the policy's current recommendation.

The catalog predicts. The runtime receipt establishes what is present. The
benchmark establishes what happened in one bounded run. Keep these claims
separate.

Runtime fit includes configuration, not just the executable version. Catalog
entries may constrain the Ollama KV-cache types that can represent their head
dimensions. The planner blocks a mismatch before installation or use.

Bounded final-response benchmarks disable optional model thinking by default
and record the setting. Reasoning-trace evaluation is an explicit opt-in
because it changes both the workload and token-budget interpretation. A clean
final-response pass requires a non-empty stop-completed response. Raw thinking
markup makes a reasoning-disabled run non-accepted even when final prose follows;
the original output remains unchanged for diagnosis.

## Capability-graded runtime contract

Popularity does not make runtime contracts interchangeable. The skill exposes
four capability groups for every detected runtime: management, identity,
execution, and serving. A command may run only when the selected adapter marks
that exact capability true.

The managed runtimes are:

- **Ollama:** complete managed adapter. Catalog targets resolve to Ollama model
  names. Local digests support before-and-after update receipts.
- **LM Studio:** partial managed adapter. Catalog targets resolve to exact
  Hugging Face repository and quantization requests accepted by `lms get`.
  `lms ls --json --variants` supplies non-mutating inventory. Its identity is a
  hash of allowlisted runtime metadata, not a content digest, so automated
  model-content updates remain disabled.

The direct runtimes are llama.cpp and MLX-LM. Both can execute and serve models
on Apple silicon. Neither is represented as a managed model registry by this
skill. Their caches and caller-supplied files remain outside the inventory and
update contract.

## Managed adapter requirements

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

The macOS Homebrew configuration adapter is narrower than the serving adapter.
It accepts only the expected current-user LaunchAgent label and two-argument
`ollama serve` command, changes only an allowlisted KV-cache value, creates a
private backup, reloads through `launchctl`, and proves API health. A failed
reload restores the original plist. Because Ollama exposes the KV-cache type as
a global service setting, the planner evaluates every selected artifact against
the same effective value. Re-profile after Homebrew upgrades or service
regeneration.

Ollama implements the complete contract. Hugging Face GGUF ids remain
Ollama artifacts after import, so the inventory records the full runtime name
and resolved Ollama digest in addition to upstream and publisher metadata.

LM Studio implements only the capability subset described above. Catalog
schema 2 stores its exact target separately from the legacy Ollama target and
names the quantization publisher for that target. A successful download is not
enough: the adapter re-enumerates JSON inventory and requires one unambiguous
repository-plus-quantization match before writing inventory.

For Hugging Face registry timeouts after all large layers are present, the
adapter may use Ollama's supported local multi-GGUF create path. The catalog
pins the registry manifest URL plus each GGUF model/projector layer's full
digest, media type, and size. The adapter re-hashes every cached layer, creates
same-volume temporary hard links, imports the directory, removes the links,
and then applies the normal runtime identity and inventory gates.
The hard links eliminate a separate staging copy. Ollama may still normalize a
GGUF into a new runtime layer and retain the registry cache, so the recovery
receipt budgets the full layer total as possible additional disk use.

## Schema evolution

Catalog and inventory schemas carry integer `schema_version` fields. A future
version may add fields but must reject an unknown higher schema unless a tested
migration exists. Do not silently reinterpret capacity units or runtime model
ids.

Catalog schema 1 remains readable as Ollama-only input. Schema 2 adds optional
runtime targets. An absent LM Studio target blocks that artifact for LM Studio;
the planner may select another verified artifact in the family, but it never
constructs a target from model-name similarity.

## Update transactions

Updates are explicit state transitions, not periodic background activity. A
dry-run plan snapshots safe installed metadata. Execution invokes the runtime's
native pull for the same validated name, re-enumerates the model, and records
both states. Digest or size changes produce `updated`; identical content
identity produces `already-current`. Either is successful evidence. A failed
pull or absent post-pull model produces a failed receipt.

`--all` means every installed Ollama model. It is never the implicit default.
When an existing per-machine inventory maps one of the updated names, the
successful result refreshes that record atomically. Models outside the
inventory still receive receipts without creating an opaque machine identity.

## Cross-machine use

Run the profiler and planner separately on each computer. Do not copy a
recommendation from one machine merely because both are Apple silicon or both
report the same nominal RAM. Available disk, runtime version, store location,
and user policy are part of the decision.

The opaque machine id is random local state, not a hardware fingerprint. To
build a comparison table, export and merge safe inventory entries. A friendly
label is optional and user supplied.
