# Open-Weight Runner Contract

## Purpose

Provide one reproducible generation through an OpenAI-compatible chat
completions endpoint while capturing enough metadata to audit the event. The
contract intentionally has no detector-feedback or rewrite loop.

## Request

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

## Model-selection evidence

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

## Response requirements

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

## Endpoint safety

Loopback HTTP and HTTPS endpoints are accepted by default. LAN or hosted
OpenAI-compatible endpoints require `--allow-non-loopback`. API credentials
must come from an environment variable named with `--api-key-env`; the key is
never written to the manifest or error output. Endpoint URLs containing user
information, query parameters, or fragments are rejected so secrets do not
enter shell history or an accidental record.

## Generation semantics

- one request produces one output and one manifest;
- do not silently retry a completed response because its style is undesirable;
- network or response-shape failures leave no completed manifest;
- the raw response content is written without editorial normalization;
- local generation fails closed when no native runtime receipt is supplied;
- the manifest binds the receipt's exact bytes with SHA-256 and byte count;
- detector results are not inputs to the runner;
- callers who need multiple samples invoke the runner independently and assign
  independent record IDs.

## Reproducibility limit

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
