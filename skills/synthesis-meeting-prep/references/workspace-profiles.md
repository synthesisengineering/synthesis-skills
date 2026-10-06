# Workspace profile ownership

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

## Legacy profiles

The 1.3.0 hash-bound migration (`prep_init.py migrate`) moved the old global
profiles into their owning repositories and has finished; the tool is
retired, and its full description is in [preserved.md](preserved.md). Should
a stray legacy profile turn up, resolve its owner first and move it with
ordinary file and git operations into that owner's repository, then commit
there.

Commit and publish profile records through the private repository's normal
record workflow. `prep_init.py` neither commits nor changes a repository's
remote permissions.
