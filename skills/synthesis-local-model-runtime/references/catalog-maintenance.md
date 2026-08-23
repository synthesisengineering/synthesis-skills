# Catalog Maintenance

## Evidence required for every artifact

1. Official upstream model card and license.
2. Artifact publisher page naming the exact quantization and file or runtime
   id.
3. Current size and minimum runtime compatibility.
4. Total and active parameter counts kept separate for MoE models.
5. A bounded planning context assumption.
6. Verification date and status.
7. For each additional managed runtime, the exact acquisition target,
   quantization publisher, artifact source URL, format, and at least two
   unambiguous inventory match terms.

Prefer official runtime artifacts. A reputable community quantization is
acceptable only when the catalog names the publisher separately and the local
inventory captures the digest resolved after installation.

## Update procedure

1. Re-open all source URLs; a prior model card is cached evidence, not current
   truth.
2. Confirm the runtime id exists without pulling it.
3. Reconcile size and quantization across the artifact page and runtime
   metadata.
4. Add or update the record. Never repoint an existing catalog id to a different
   quantization.
5. Run `local_model_runtime.py catalog` and the unit tests.
6. Run each managed runtime planner against 16, 24, 32, 64, 96, and 128 GiB
   fixtures. Missing runtime targets must block or select a separately verified
   candidate; they must never be inferred.
7. Test each acquisition command as an argument array and verify the runtime's
   non-mutating inventory response independently.
8. Record the user-visible catalog change in the plugin release notes.

LM Studio targets use credential-free `https://huggingface.co/` repository
URLs with an explicit `@quantization` suffix. The `match_terms` must identify
both the repository and quantization in `lms ls --json --variants` output. A
single generic term such as `q8_0` is invalid because it can match unrelated
models.

For a Hugging Face artifact with local-import recovery, fetch its public
Ollama-compatible registry manifest and pin only GGUF model/projector layers.
Record each full digest, media type, and byte size plus the manifest URL. Do not
pin a layer from terminal progress output or infer it from a repository file
name.

## Retirement

Mark a removed or superseded artifact `retired`; do not delete its record while
an inventory may reference it. The planner excludes retired records. Inventory
verification can still explain an installed historical artifact.
