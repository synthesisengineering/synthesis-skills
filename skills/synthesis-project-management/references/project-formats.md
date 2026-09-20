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

## Rules for every version, present and future

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
