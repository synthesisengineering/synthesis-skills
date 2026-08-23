# Architecture

## Layers

1. **Safe profile:** read-only hardware, storage, and runtime facts. The output
   schema deliberately has no field for a hostname, serial, hardware UUID,
   account, or network address.
2. **Catalog:** dated, reviewable artifact facts. An entry identifies the
   upstream model and the separately accountable quantization publisher.
3. **Policy:** local choices such as required families, excluded organizations,
   exact overrides, protected paths, and retained resource headroom.
4. **Planner:** deterministic filtering and ranking against the safe profile.
5. **Runtime adapter:** explicit model pull, resolved metadata read, bounded
   generation, and unload behavior.
6. **Inventory:** an atomic map from an opaque locally generated machine id to
   the safe profile, intended selections, and resolved installed artifacts.

The catalog predicts. The runtime receipt establishes what is present. The
benchmark establishes what happened in one bounded run. Keep these claims
separate.

## Runtime adapter contract

An adapter must implement:

- version discovery;
- effective model-store discovery or an explicit unverifiable result;
- non-mutating installed-model enumeration;
- installation by argument-array subprocess with no shell evaluation;
- resolved artifact metadata including a local digest or content identity;
- a loopback-only bounded generation call;
- explicit unload.

Version 1.0 implements this contract for Ollama. Hugging Face GGUF ids remain
Ollama artifacts after import, so the inventory records the full runtime name
and resolved Ollama digest in addition to upstream and publisher metadata.

## Schema evolution

Catalog and inventory schemas carry integer `schema_version` fields. A future
version may add fields but must reject an unknown higher schema unless a tested
migration exists. Do not silently reinterpret capacity units or runtime model
ids.

## Cross-machine use

Run the profiler and planner separately on each computer. Do not copy a
recommendation from one machine merely because both are Apple silicon or both
report the same nominal RAM. Available disk, runtime version, store location,
and user policy are part of the decision.

The opaque machine id is random local state, not a hardware fingerprint. To
build a comparison table, export and merge safe inventory entries. A friendly
label is optional and user supplied.
