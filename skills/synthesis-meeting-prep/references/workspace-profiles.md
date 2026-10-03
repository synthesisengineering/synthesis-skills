# Workspace profile ownership and migration

The caller resolves an approved private context repository using the current
workspace registry and retention rules. Supply its exact absolute Git checkout
root as `--context-repo` and its stable id as `--workspace`. The prep owner checks
filesystem and Git-root identity; it does not prove repository privacy or infer
ownership from file contents. A conflicting `.owner.json` refuses the operation.

The fixed profile directory is `profiles/meeting-prep` inside that repository.
Deleting the owning repository therefore includes its relationship-bound
profiles. Keep records covered by the principal's independent retention duties
in their separately approved owner; classify mixed legacy content before moving
it. Do not duplicate private profiles into public fixtures, reports, or another
workspace as part of migration.

## Exact selection

Build a private JSON map containing only authorized source paths and verified
SHA-256 values. The map is itself private context and follows the same routing
policy. This is the closed schema (the hash below is illustrative):

```json
{
  "schema": 1,
  "legacy_root": "/absolute/legacy-profile-directory",
  "context_repo": "/absolute/approved-private-context-repository",
  "workspace": "example",
  "files": [
    {"path": "readers/synthetic.md", "sha256": "0000000000000000000000000000000000000000000000000000000000000000", "workspace": "example"},
    {"path": "readers/unresolved.md", "sha256": null, "workspace": null}
  ]
}
```

Only `principal.json` and `readers/<id>.md` are selectable. Selected entries
must name the destination workspace and exact current hash. Entries assigned
to another workspace or `null` are counted and never opened by migration.
Omitted entries are untouched. Up to 128 entries, 8 MiB per selected file, and
32 MiB total selected data are permitted. Duplicate paths or JSON fields,
traversal, symlink ancestry, special files, and hardlinked source files refuse.
An existing destination is never overwritten. Legacy sources inside Git must
use the Git record owner instead of this untracked-global migration.

## Preflight, apply, and interruption

Run `scripts/prep_init.py migrate --map /absolute/private-map.json` for read-only
preflight. It validates all selected sources and destination slots. For a
retained migration it also revalidates physical source, staged, and destination
custody. A passing preflight grants no permission to route unresolved content.

With explicit authorization for that exact map, add `--apply`. The existing
record owner holds bounded cooperative locks on the source directory and
repository in deterministic order. Each file is staged privately at the
destination, linked into an empty final slot, and verified by identity and
hash. Its original then moves atomically into retained custody under the
legacy directory, is verified again, and is deleted only after the final copy
is reverified. The destination receipt records every completed boundary.

After interruption, repeat the exact same map and `--apply`. Completed members
are verified without deleting newly appeared source paths. Interrupted staged
links, retained originals, and receipts are reused only when their identities
and hashes match. Partial writes, changed files, missing custody, or foreign
occupied slots refuse and retain the available evidence for explicit
reconciliation. A batch can finish some files before interruption; the receipt
records which ones. This is not an all-or-nothing filesystem transaction.

Receipts and staged paths live beneath the destination's
`profiles/meeting-prep/.migrations/<map-digest>/`. Original custody lives under
`<legacy-root>/.meeting-prep-migration-<map-digest>/` until verified deletion.
A completed operation leaves metadata and empty custody directories intact.
Never remove retained evidence merely to make a refused retry pass. Locks
coordinate participating record owners; they do not exclude arbitrary external
filesystem writes. The byte and identity checks detect such changes at each
read boundary and preserve changed originals moved into custody.

Commit and publish the resulting private repository records through its normal
coordination and record workflow. The prep tool neither commits nor changes a
repository's remote permissions. Local migration success is distinct from
remote custody and from loading a released skill in an AI client.
