# Text provenance: the full workflow

The seven workflow steps in full, with every command and option. SKILL.md carries the binding rules, the boundary, the tool summary and the completion checklist. Steps 4 to 6 were rewritten in v5 when the manifest and generation scripts were retired; the 1.0.1 text is verbatim in [preserved.md](preserved.md).

Contents:
- 1. Define the provenance requirement
- 2. Re-verify current capability claims
- 3. Select the generation path
- 4. Create the evidence bundle (the provenance record, hashed with `shasum -a 256`)
- 5. Run non-mutating integrity inspection when relevant (clean-text's `text_integrity_audit.py`)
- 6. Run local generation when it satisfies the policy (by hand, per the runner contract)
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

Local generation is provider-neutral and speaks to a loopback
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

Write them as a provenance record, a markdown file kept in the project beside
the text (for example `resources/provenance/<record id>.md`), before anyone
edits the output. Hash the files with the operating system's own tool and paste
the values in:

```bash
shasum -a 256 prompt.txt output.txt runtime-metadata.txt
```

For an edited or derived output, name each direct parent by its record ID and
its output's SHA-256; a parent link holds hashes and IDs, never a path to
follow. To verify, re-run `shasum -a 256` on the recorded files and compare;
for lineage, compare each parent record's output hash with the child's parent
link, one edge at a time. The fields, privacy rules and what verification can
and cannot show are in [`references/provenance-manifest.md`](provenance-manifest.md).

### 5. Run non-mutating integrity inspection when relevant

Invisible Unicode and normalization differences can affect text handling, but
they are not proof of a statistical watermark. Audit without rewriting, with
the audit script that lives in synthesis-clean-text:

```bash
python3 ../synthesis-clean-text/scripts/text_integrity_audit.py article.txt --format human
python3 ../synthesis-clean-text/scripts/text_integrity_audit.py article.txt --format json --fail-on-findings
```

The script reports code points, positions, normalization differences, hashes,
and line-ending counts. For a file, it performs two complete byte reads and
refuses the audit if their SHA-256 hashes differ. Standard input is necessarily
single-read. The script never writes a cleaned copy. Record its result in the
provenance record's audits, with its limitation.

### 6. Run local generation when it satisfies the policy

Follow [`references/open-weight-runner-contract.md`](open-weight-runner-contract.md):
record the runtime's own metadata first, send one request to the loopback
endpoint, keep the raw response, and write the provenance record. One request
produces one output; there is no detector call, selective regeneration or
optimization against provenance results. A response whose final content is
empty or whitespace is a failed generation and gets no record as a success.

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
