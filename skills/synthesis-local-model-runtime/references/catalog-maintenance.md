# Catalog Maintenance

## Evidence required for every artifact

1. Official upstream model card and license.
2. Artifact publisher page naming the exact quantization and file or runtime
   id.
3. Current size and minimum runtime compatibility.
4. Total and active parameter counts kept separate for MoE models.
5. A bounded planning context assumption.
6. Verification date and status.

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
6. Run the planner against 16, 24, 32, 64, 96, and 128 GiB fixtures.
7. Record the user-visible catalog change in the plugin release notes.

## Retirement

Mark a removed or superseded artifact `retired`; do not delete its record while
an inventory may reference it. The planner excludes retired records. Inventory
verification can still explain an installed historical artifact.
