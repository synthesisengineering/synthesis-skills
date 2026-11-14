# Open-Weight Runner Contract

## Purpose

Produce one reproducible generation through a local OpenAI-compatible chat
completions endpoint while capturing enough metadata to audit the event. The
contract intentionally has no detector-feedback or rewrite loop. It is a
procedure run by hand; v5 ships no runner script.

## Before the request

Gather:

- one UTF-8 user prompt file, and an optional UTF-8 system prompt file;
- the exact model ID requested;
- the provider and runtime labels;
- the endpoint URL (loopback by default; see Endpoint safety);
- temperature, maximum output tokens, and optional seed;
- optional reasoning effort (`none`, `low`, `medium`, or `high`) where the
  endpoint implements it.

Capture the runtime's own metadata before generating, so the record cannot
omit or overwrite it. For Ollama:

```bash
{ ollama --version; ollama list | grep '<model>'; ollama show <model>; } > runtime-metadata.txt
ollama show <model> --license | shasum -a 256
ollama show <model> --template | shasum -a 256
```

That keeps the runtime version, the tag's digest, details, parameters and
capabilities, and hashes of the license and template. Declare anything missing
as unknown; leave out the full tensor inventory. An Ollama tag is never proof
of authorship, license compliance, or watermark absence.

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

## The request

Send one request and keep the raw response:

```bash
curl -s http://127.0.0.1:11434/v1/chat/completions \
  -H 'Content-Type: application/json' -d @request.json > response.json
python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"], end="")' \
  < response.json > output.txt
```

The response's `choices[0].message.content` must contain non-whitespace final
text. A response that exhausts its allowance in reasoning and returns no final
content is a failed generation, not valid zero-byte evidence. The returned
`model` field may be absent: record unknown, never the requested ID. Record
`finish_reason`, `usage` and `system_fingerprint` when present.

## Endpoint safety

Use a loopback endpoint (`127.0.0.1`, `::1` or `localhost`) by default. A LAN
or hosted endpoint is a deliberate choice recorded as such. Read an API key
from an environment variable in the command (`-H "Authorization: Bearer
$KEY"`), never type it inline, and never write it into the record or
`request.json`. Do not use an endpoint URL that carries user information, query
parameters or fragments, so secrets stay out of shell history and records.

## Generation semantics

- one request produces one output and one provenance record;
- do not silently retry a completed response because its style is undesirable;
- a network or response-shape failure leaves no record of a success;
- keep the raw response content without editorial normalization;
- local generation without captured runtime metadata is not recorded as local
  open-weight generation;
- the record binds the metadata file's exact bytes with SHA-256 and byte count;
- detector results are never inputs to generation;
- several samples are several independent requests, each with its own record.

## Reproducibility limit

Parameters and hashes make the call auditable, not necessarily bit-for-bit
reproducible. Runtime versions, kernels, quantization, model files, sampling
implementations, and nondeterministic hardware may change output. Record those
details in project-level run metadata when exact reproduction matters.
