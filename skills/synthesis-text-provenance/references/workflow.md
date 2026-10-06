# Text provenance: the full workflow

The seven workflow steps in full, with every command and option. SKILL.md carries the binding rules, the boundary, the script summary and the completion checklist.

Contents:
- 1. Define the provenance requirement
- 2. Re-verify current capability claims
- 3. Select the generation path
- 4. Create the evidence bundle (`provenance_manifest.py create`, `validate`, `verify`)
- 5. Run non-mutating integrity inspection when relevant (`text_integrity_audit.py`)
- 6. Run local generation when it satisfies the policy (`ollama_metadata.py`, `local_generate.py`)
- 7. Report bounded conclusions

## Workflow

### 1. Define the provenance requirement

Record the actual constraint before selecting a model:

- privacy or data-egress requirement;
- reproducibility requirement;
- provider-mark policy;
- disclosure or recordkeeping requirement;
- quality threshold;
- allowed runtimes and licenses;
- whether a provider or standards detector is authorized and available.

Do not collapse “I do not want a hosted-provider mark” into “make generated
text look human.” The first is a model-selection and provenance requirement;
the second is an authorship-evasion objective.

### 2. Re-verify current capability claims

Provider behavior, regulation, model IDs, detector access, and local runtimes
change. Search current primary documentation before making a claim. Record:

- provider, exact model, product surface, region, and date;
- whether the capability is deployed, a roadmap statement, research, or
  third-party observation;
- whether verification is public, account-bound, provider-only, or absent;
- what a positive and negative result can and cannot establish.

Use the evidence classes and bounded language in
[`references/capability-claims.md`](capability-claims.md).

### 3. Select the generation path

Use this order:

1. If a hosted provider's documented behavior satisfies the requirement, use
   it and record the exact surface.
2. If provider-added text marking conflicts with the requirement, select an
   authorized local/open-weight model before generating.
3. If no path satisfies both quality and provenance constraints, report the
   conflict. Do not claim an unverified workaround removes a mark.

The local runner is provider-neutral and speaks to a loopback
OpenAI-compatible endpoint. See
[`references/open-weight-runner-contract.md`](open-weight-runner-contract.md).

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

### 7. Report bounded conclusions

Use conclusions shaped like:

- “The provider documents text marking for this exact surface as of DATE.”
- “This authorized detector returned RESULT under TOOL VERSION; the provider
  states that this result does not prove AUTHORSHIP CLAIM.”
- “The integrity audit found U+200B at these positions. That finding describes
  Unicode content, not a token-distribution watermark.”
- “No compatible public detector was found in the bounded sources reviewed;
  verification remains unavailable, not negative.”

Never write “watermark-free,” “undetectable,” “human-written,” or “clean” when
the evidence establishes only a narrower technical fact.
