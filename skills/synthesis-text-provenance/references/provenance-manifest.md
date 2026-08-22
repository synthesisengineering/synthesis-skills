# Provenance Manifest, Schema 1

The JSON manifest records one text generation or editing event. It preserves
hashes and lineage; it is not a proof that the recorded operator told the
truth. Signatures or external credentials can be layered on later without
changing the meaning of the core fields.

## Top-level fields

- `schema_version`: currently `1`.
- `record_id`: UUID for this event.
- `created_at`: UTC RFC 3339 timestamp.
- `generation_mode`: `human`, `hosted`, `local_open_weight`, `mixed`, or
  `unknown`.
- `provider`, `model_requested`, `model_returned`, `runtime`: strings or null.
- `endpoint_class`: `none`, `hosted`, `local_loopback`, `local_lan`, or
  `unknown`.
- `prompt`: SHA-256, byte count, and path pointer for the exact prompt file.
- `sources`: zero or more hashed source inputs.
- `output`: SHA-256, byte count, and path pointer for the output.
- `parameters`: values set by the caller plus the runner's bounded
  `reported_response` metadata (`finish_reason`, `usage`, and
  `system_fingerprint` when available).
- `parents`: prior manifest record IDs.
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

`verify` resolves relative pointers from the manifest directory and recomputes
hashes. A pass establishes byte equality with the recorded files at verification
time. It does not establish authorship, copyright ownership, truthfulness of
metadata, or absence of a watermark.
