# Project format versions

Projects carry an on-disk format version so the system can evolve
without breaking old projects. Added in skill v2.16.0.

## v1 (unmarked)

`CONTEXT.md` + `REFERENCE.md` + `sessions/YYYY-MM.md`, with no
marker file. Everything in every workspace predating v2 is v1.

## v2 (marked, strictly additive)

Everything in v1, plus exactly three files:

```
{project-id}/
├── .synthesis-project.yaml  # format_version, id, migration record
├── RESUME_STATE.json        # resume state, schema v1 (below)
└── sessions/INDEX.md        # generated per-period manifest
```

`RESUME_STATE.json` schema v1 keys: `schema` (1), `goal`,
`status`, `open_loops[]` ({id, text, owner, since}), `last_session`
(period), `last_brief` (one paragraph), `updated_at`. Fresh
migrations write a skeleton labeled `"skeleton": true` with
`unverified` loops; the next real session verifies and overwrites.

`CURRENT_STATE.json` is a different file with a different owner:
the operational handoff shape managed by `project_state.py`.
Migration never touches it; resume reads both (resume state first,
operational state second).

## Engine

`scripts/project_format.py`:

- `detect <dir>` → missing | v1 | v2 | partial | unknown.
- `migrate --check <dir>` → what would be added; writes nothing.
- `migrate [--goal TEXT] [--status TEXT] <dir>` → adds the three
  files, then verifies by re-reading them.
- `archive [--older-than-days N] [--check] <dir>` → moves session
  periods older than N days to `sessions/archive/` (v2 only, never
  the newest period) and regenerates the index, which covers both
  live and archived periods. Default retention is 365 days — a
  year of live history unless the principal says otherwise.

## Explicit closeout refresh

Run `project_format.py refresh --check <dir>` to preview and
`project_format.py refresh <dir>` to apply. It refreshes the generated index and
resume candidates using the existing schema. Indexes recognize all six ATX
heading levels, skip fenced examples, and distinguish dated entries from
interior undated headings. Long indexes state the full entry count and the
number omitted from the compact listing.

Migration and refresh seed unchecked `CONTEXT.md` tasks alongside markers in
the newest session log. Candidates carry relative source path, line and source
digest, remain `unverified`, and are never automatically treated as completed.
Repeated task wording keeps distinct source occurrences. Candidate IDs survive
line shifts; source hashes and line numbers describe the original observation,
not a claim that unchanged wording has been reverified.
Refresh preserves curated goal/status/brief, reviewed loops, additional state
fields, and candidates whose source disappears. It adds only new candidate IDs.
Human or authenticated session reconciliation still owns verification and closure.

A second unchanged refresh preserves bytes and modification times. All inputs
preflight before output writes; each output replacement is atomic, but the
index and resume state are **not** a multi-file filesystem transaction. If the
process stops between them, rerun refresh under the same normal project-records
ownership to converge. The command refuses malformed state, symlink targets and
an index owned by another writer. Duplicate JSON keys are refused, including in
curated nested fields. File mode and contents are synced before each rename,
then the parent directory is synced; a post-rename error requires inspecting the
outputs before retry. It never edits `CURRENT_STATE.json`.

## Rules for every version, present and future

Material preservation applies independently of format. The shared checkpoint and
doctor result exposes declared inputs and association reachability for v1 before
structured NOT_APPLICABLE. Follow [material context](../../synthesis-context-lifecycle/references/material-context.md);
do not migrate or enroll a project to manufacture coverage. Refresh preserves
curated loops and avoids recreating exact terminal source spans; changed source
bytes require reconciliation, and absent source never completes an obligation.

- New versions are strictly additive. Old readers keep working.
- Migration is pull-based, on resume: inform the principal in one
  line, migrate, verify, then resume work. Never migrate under a
  live foreign claim.
- Migration never overwrites: existing state/index files are kept
  and validated; a kept file that fails validation fails the
  migration closed (marker rolled back) for a human to fix.
- Downgrade is deleting the added files.
- Writers refresh the state file and index at session close; never
  hand-edit `<!-- generated -->` sections.
