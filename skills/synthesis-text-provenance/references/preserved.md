# Text provenance: preserved text

Contents:
- Why this text was retired
- SKILL.md 2.0.0: binding rules 6 and 7, Scripts, two checklist items
- references/workflow.md: the intro line, three contents lines, step 3's runner sentence, steps 4 to 6
- references/provenance-manifest.md: the whole 1.0.1 file
- references/open-weight-runner-contract.md: the whole 1.0.1 file

## Why this text was retired

The v5 code evaluation (`tool-scripts.md`, synthesis-text-provenance rows) ruled
`provenance_manifest.py` (600 lines), `local_generate.py` (240) and
`ollama_metadata.py` (151) CUT as never used: "No manifest exists in any
workspace; the skill's boundaries (never defeat or deny a provider mark) are
prose and stay." `text_integrity_audit.py` (KEEP) moved to synthesis-clean-text.
The record, the runtime metadata and the one-request generation are kept as
manual procedures; the schema-2 self-hash, the canonical JSON fixture and the
runner's built-in refusals are replaced by recomputed `shasum` hashes and the
written rules in the runner contract. Everything below is verbatim.

## SKILL.md 2.0.0

6. **Preserve raw input, output and hashes before editing**; hash-bind the native runtime receipt; validate and verify the manifest and its direct parents.
7. **Audit without rewriting.** The integrity audit reports Unicode facts, never writes a cleaned copy, and is not proof of a statistical watermark.

## Scripts

Run from the skill folder. Full flags are in references/workflow.md, steps 4 to 6.

- `python3 scripts/provenance_manifest.py create ... --manifest provenance.json` prints `created canonical self-hashed schema-2 manifest`; `validate provenance.json` prints `valid ...`; `verify provenance.json` checks the self-hash, referenced files and `--parent-manifest` links.
- `python3 scripts/text_integrity_audit.py article.txt --format human` (or `--format json --fail-on-findings`) prints code points, positions, normalization differences, hashes and line endings; exit 1 on findings with that flag, 2 on error.
- `python3 scripts/ollama_metadata.py --model example-model --output ollama-metadata.json` writes the bounded Ollama runtime receipt.
- `python3 scripts/local_generate.py --endpoint http://127.0.0.1:11434/v1/chat/completions ...` generates once and writes the output and a valid manifest.

From the completion checklist:

- [ ] Hosted versus local selection follows the stated requirement.
- [ ] Raw input/output and hashes are preserved before editing.
- [ ] Native runtime receipt is hash-bound for local generation.
- [ ] Manifest validation, self-hash, file hashes, and direct-parent lineage
      verification pass.

## references/workflow.md 2.0.0

The seven workflow steps in full, with every command and option. SKILL.md carries the binding rules, the boundary, the script summary and the completion checklist.

- 4. Create the evidence bundle (`provenance_manifest.py create`, `validate`, `verify`)
- 5. Run non-mutating integrity inspection when relevant (`text_integrity_audit.py`)
- 6. Run local generation when it satisfies the policy (`ollama_metadata.py`, `local_generate.py`)

From step 3:

The local runner is provider-neutral and speaks to a loopback
OpenAI-compatible endpoint.

### 4. Create the evidence bundle

Preserve:

- prompt or prompt hash and a private pointer;
- source-input hashes;
- model requested and model returned;
- runtime and endpoint class;
- parameters actually set or returned;
- raw output and SHA-256 hash;
- parent record IDs and human-edit description;
- detector and integrity-audit results with tool versions and limitations.

Create and validate the manifest:

```bash
python3 scripts/provenance_manifest.py create \
  --generation-mode local_open_weight \
  --provider local \
  --model example-model \
  --runtime ollama \
  --runtime-receipt ollama-metadata.json \
  --endpoint-class local_loopback \
  --prompt-file prompt.txt \
  --output-file output.txt \
  --manifest provenance.json

python3 scripts/provenance_manifest.py validate provenance.json
python3 scripts/provenance_manifest.py verify provenance.json
```

For an edited or derived output, add each direct parent with
`--parent-manifest parent.json` during creation and pass the same explicit
parent manifest to `verify`. Parent links contain hashes and record IDs, not
paths; verification never follows a path stored by a parent.

The full schema and field semantics are in
[`references/provenance-manifest.md`](provenance-manifest.md).

### 5. Run non-mutating integrity inspection when relevant

Invisible Unicode and normalization differences can affect text handling, but
they are not proof of a statistical watermark. Audit without rewriting:

```bash
python3 scripts/text_integrity_audit.py article.txt --format human
python3 scripts/text_integrity_audit.py article.txt --format json --fail-on-findings
```

The script reports code points, positions, normalization differences, hashes,
and line-ending counts. For a file, it performs two complete byte reads and
refuses the audit if their SHA-256 hashes differ. Standard input is necessarily
single-read. The script never writes a cleaned copy.

### 6. Run local generation when it satisfies the policy

For an already running loopback OpenAI-compatible endpoint, capture the native
runtime receipt first. The bundled metadata helper supports Ollama:

```bash
python3 scripts/ollama_metadata.py \
  --model example-model \
  --output ollama-metadata.json
```

Then bind that receipt into the one-shot generation manifest:

```bash
python3 scripts/local_generate.py \
  --endpoint http://127.0.0.1:11434/v1/chat/completions \
  --provider local \
  --runtime ollama \
  --runtime-receipt ollama-metadata.json \
  --model example-model \
  --reasoning-effort none \
  --prompt-file prompt.txt \
  --output-file output.txt \
  --manifest provenance.json
```

The runner records one generation. It does not call a detector, regenerate
selectively, or optimize against provenance results. Non-loopback endpoints are
rejected unless the operator passes `--allow-non-loopback` deliberately.
An empty or whitespace-only final response is a failed generation and produces
no output or manifest. `--reasoning-effort` is optional because not every
OpenAI-compatible endpoint implements it; when supplied, it is included in the
request and manifest parameters.

The receipt preserves the runtime version, model digest, size, quantization,
license and template hashes, selected model metadata, and declared unknowns.
It deliberately excludes the full tensor inventory and never treats an Ollama
tag as proof of authorship, license compliance, or watermark absence.

## references/provenance-manifest.md 1.0.1

### Provenance Manifest, Schema 2

The JSON manifest records one text generation or editing event. It preserves
hashes and direct-parent lineage; it is not a proof that the recorded operator
told the truth. A self-hash detects accidental or undisclosed content changes,
but it is not a digital signature or third-party timestamp.

### Canonical self-hash

`manifest_sha256` is SHA-256 over UTF-8 JSON with object keys sorted,
no insignificant whitespace, non-ASCII characters preserved, and
`manifest_sha256` itself omitted. NaN, infinity, duplicate object keys, and
non-JSON values are rejected. The hash is independent of pretty-printing and
object insertion order.

The deterministic fixture at
`tests/fixtures/canonical-manifest-v2.json` pins the canonicalization contract.

### Top-level fields

- `schema_version`: currently `2`.
- `record_id`: UUID for this event.
- `created_at`: UTC RFC 3339 timestamp.
- `manifest_sha256`: canonical manifest-content hash defined above.
- `generation_mode`: `human`, `hosted`, `local_open_weight`, `mixed`, or
  `unknown`.
- `provider`, `model_requested`, `model_returned`, `runtime`: strings or null.
- `runtime_receipt`: a file record for a native runtime receipt, or null. A
  file record carries its path pointer, SHA-256, and byte count. Schema 2
  requires this record when `generation_mode` is `local_open_weight`.
- `endpoint_class`: `none`, `hosted`, `local_loopback`, `local_lan`, or
  `unknown`.
- `prompt`: SHA-256, byte count, and path pointer for the exact prompt file.
- `sources`: zero or more hashed source inputs.
- `output`: SHA-256, byte count, and path pointer for the output.
- `parameters`: values set by the caller plus the runner's bounded
  `reported_response` metadata (`finish_reason`, `usage`, and
  `system_fingerprint` when available).
- `parents`: direct-parent records containing exactly `record_id`,
  `manifest_sha256`, and `output_sha256`. Parent records never contain paths.
- `human_edit_description`: free text or null.
- `audits`: authorized detector or integrity results.
- `notes`: bounded unknowns and access gaps.

### Audit record

Every audit record contains:

- `tool` and `version`;
- `kind`: `text_integrity`, `provider_detector`, `standards_detector`, or
  `other`;
- `result`: the tool's result without reinterpretation;
- `limitations`: what the result cannot prove;
- `optimization_used`: must be `false`.

The validator rejects a record that says detector feedback was used as an
optimization objective. This is a workflow boundary, not a claim that the JSON
cannot be falsified.

### Path and privacy rules

Use project-relative paths when a manifest will be shared. Do not place raw
prompts, authentication values, identity references, internal endpoint
addresses, or restricted source content in a public manifest. Store private
material in its authorized repository and record only hashes plus a private
pointer.

### Verification semantics

`verify` checks the canonical self-hash, resolves relative pointers from the
manifest directory, and recomputes prompt, source, output, and runtime-receipt
hashes. A pass establishes byte equality with the recorded files at
verification time.

For every recorded parent, pass the direct parent's manifest explicitly:

```bash
python3 scripts/provenance_manifest.py verify child.json \
  --parent-manifest parent.json
```

Lineage verification reads only explicitly supplied parent manifest files. It
compares their self-hash and recorded output hash with the child's path-free
parent record. It does not follow a path from manifest content, open the
parent's recorded output, or recurse into earlier ancestors. Verify each prior
edge explicitly when a complete chain is required.

A pass does not establish authorship, copyright ownership, truthfulness of
metadata, authenticity of the operator, or absence of a watermark.

## references/open-weight-runner-contract.md 1.0.1

### Open-Weight Runner Contract (1.0.1)

### Purpose

Provide one reproducible generation through an OpenAI-compatible chat
completions endpoint while capturing enough metadata to audit the event. The
contract intentionally has no detector-feedback or rewrite loop.

### Request

- one UTF-8 user prompt file;
- optional UTF-8 system prompt file;
- exact model ID requested;
- provider and runtime labels supplied by the operator;
- endpoint URL;
- native runtime-receipt file for local generation;
- temperature, maximum output tokens, and optional seed;
- optional OpenAI-compatible reasoning effort (`none`, `low`, `medium`, or
  `high`);
- output path and manifest path.

### Model-selection evidence

Before acquiring or naming a local/open-weight model as a provenance control,
record the exact upstream model-card revision, license text, weight or package
identity, runtime tag and digest, quantization, template, and known provenance
or marking disclosures. Recheck these facts at acquisition time and again at
the forward test. A model name, publisher, country of origin, open-weight label,
or local execution path does not by itself establish trust, license compliance,
reproducibility, or absence of a statistical mark.

If the selected model is unavailable, keep the acquisition or execution gap
explicit. Do not silently substitute a different family, quantization, runtime,
or provider and retain the original label.

### Response requirements

The endpoint must return JSON with:

```json
{
  "choices": [{"message": {"content": "text"}}],
  "model": "returned-model-id"
}
```

The returned model field may be absent. Record `null`; do not infer it from the
request. Record `finish_reason`, `usage`, and `system_fingerprint` when the
endpoint returns them; an absent field remains `null`.
`choices[0].message.content` must contain non-whitespace final text. A response
that exhausts its allowance in reasoning and returns no final content is a
failed generation, not valid zero-byte evidence.

### Endpoint safety

Loopback HTTP and HTTPS endpoints are accepted by default. LAN or hosted
OpenAI-compatible endpoints require `--allow-non-loopback`. API credentials
must come from an environment variable named with `--api-key-env`; the key is
never written to the manifest or error output. Endpoint URLs containing user
information, query parameters, or fragments are rejected so secrets do not
enter shell history or an accidental record.

### Generation semantics

- one request produces one output and one manifest;
- do not silently retry a completed response because its style is undesirable;
- network or response-shape failures leave no completed manifest;
- the raw response content is written without editorial normalization;
- local generation fails closed when no native runtime receipt is supplied;
- the manifest binds the receipt's exact bytes with SHA-256 and byte count;
- detector results are not inputs to the runner;
- callers who need multiple samples invoke the runner independently and assign
  independent record IDs.

### Reproducibility limit

Parameters and hashes make the call auditable, not necessarily bit-for-bit
reproducible. Runtime versions, kernels, quantization, model files, sampling
implementations, and nondeterministic hardware may change output. Record those
details in project-level run metadata when exact reproduction matters.

Capture the receipt before generation so the generation manifest cannot
overwrite or omit the runtime observation. For Ollama, `ollama_metadata.py`
queries `/api/version`, `/api/tags`, and `/api/show` on loopback. It stores a
bounded receipt with the tag digest, runtime version, details, capabilities,
parameters, selected model-info fields, and hashes of the license and template.
Missing values are declared as unknown; the full tensor inventory is excluded.
