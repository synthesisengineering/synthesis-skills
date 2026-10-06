# Provenance record

A provenance record is a short markdown file that records one text generation
or editing event. It preserves hashes and direct-parent lineage; it is not a
proof that the recorded operator told the truth. Hashes detect accidental or
undisclosed content changes, but a record is not a digital signature or
third-party timestamp. Keep it in the project, beside the text it describes.

## Fields

- `record id`: a fresh identifier for this event (for example the output of
  `uuidgen`).
- `created`: UTC timestamp.
- `generation mode`: `human`, `hosted`, `local_open_weight`, `mixed`, or
  `unknown`.
- `provider`, `model requested`, `model returned`, `runtime`: as observed, or
  `unknown`. Record the returned model only from the response; never infer it
  from the request.
- `runtime metadata`: for local generation, the path and SHA-256 of the
  runtime-metadata file captured before generating (see the runner contract).
  Local open-weight generation without it is unrecorded.
- `endpoint class`: `none`, `hosted`, `local_loopback`, `local_lan`, or
  `unknown`.
- `prompt`: SHA-256, byte count, and a path pointer for the exact prompt file.
- `sources`: zero or more hashed source inputs.
- `output`: SHA-256, byte count, and a path pointer for the output.
- `parameters`: values set by the caller, plus `finish_reason`, `usage` and
  `system_fingerprint` when the response reported them.
- `parents`: for each direct parent, its record id and its output's SHA-256.
  Parent links never contain paths.
- `human edit`: what a person changed, or none.
- `audits`: authorized detector or integrity results (below).
- `notes`: bounded unknowns and access gaps.

## Audit entries

Every audit entry records:

- the tool and its version;
- the kind: text integrity, provider detector, standards detector, or other;
- the result, without reinterpretation;
- its limitations: what the result cannot prove;
- that detector feedback was not used as an optimization objective. A record
  that says otherwise describes a workflow this skill refuses.

## Path and privacy rules

Use project-relative paths when a record will be shared. Do not place raw
prompts, authentication values, identity references, internal endpoint
addresses, or restricted source content in a public record. Store private
material in its authorized repository and record only hashes plus a private
pointer.

## Verification

Re-run `shasum -a 256` on the prompt, source, output and runtime-metadata files
and compare with the record. A match establishes byte equality with the
recorded files at verification time. For lineage, open each direct parent's
record explicitly and compare its output hash with the child's parent link; do
not follow a path from a record, and verify each earlier edge on its own when a
complete chain is required.

A match does not establish authorship, copyright ownership, truthfulness of
metadata, authenticity of the operator, or absence of a watermark.
