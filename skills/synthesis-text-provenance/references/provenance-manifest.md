# Provenance Manifest, Schema 2

The JSON manifest records one text generation or editing event. It preserves
hashes and direct-parent lineage; it is not a proof that the recorded operator
told the truth. A self-hash detects accidental or undisclosed content changes,
but it is not a digital signature or third-party timestamp.

## Canonical self-hash

`manifest_sha256` is SHA-256 over UTF-8 JSON with object keys sorted,
no insignificant whitespace, non-ASCII characters preserved, and
`manifest_sha256` itself omitted. NaN, infinity, duplicate object keys, and
non-JSON values are rejected. The hash is independent of pretty-printing and
object insertion order.

The deterministic fixture at
`tests/fixtures/canonical-manifest-v2.json` pins the canonicalization contract.

## Top-level fields

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

## Audit record

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

## Path and privacy rules

Use project-relative paths when a manifest will be shared. Do not place raw
prompts, authentication values, identity references, internal endpoint
addresses, or restricted source content in a public manifest. Store private
material in its authorized repository and record only hashes plus a private
pointer.

## Verification semantics

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
