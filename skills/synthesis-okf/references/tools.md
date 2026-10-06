# OKF: the three tools

Moved verbatim from the 1.1.0 SKILL.md. Read it when running a tool for the first time, or when reading its output or exit code.

Contents:
- `okf_validate.py`: conformance checker
- `okf_convert.py`: idempotent frontmatter backfill, and the curated descriptions file
- `okf_consistency.py`: configured house-consistency checker, its seven checks and exit codes

## Tools

### `scripts/okf_validate.py` — conformance checker

```bash
python3 scripts/okf_validate.py <bundle_dir> [--summary] [--check-links] [--quiet]
```

Checks the three hard rules against every `.md` file in the bundle. `--summary` prints a
concept/type breakdown; `--check-links` additionally reports broken relative links (as
info, never as a conformance failure — broken links are explicitly valid per §5.3).
Exit codes: `0` conformant, `1` errors found, `2` usage error.

### `scripts/okf_convert.py` — idempotent frontmatter backfill

```bash
python3 scripts/okf_convert.py <bundle_dir> \
  --type-map instructions=Instruction,runbooks=Runbook,datasets=Dataset,contexts=Context \
  --descriptions <repo>-descriptions.yaml \
  [--dry-run]
```

Backfills OKF frontmatter onto an existing markdown corpus without disturbing what's
already there:

- Assigns `type` by top-level subdirectory per `--type-map` (free-form per spec §4.1 —
  name types after what they actually are; richer repos can add finer types like
  `Biography Timeline Entry` or a repo-specific `Client` type for a `clients/` directory).
- Existing frontmatter fields are **never overwritten**, only backfilled where missing —
  safe to run against a corpus where some files already carry hand-authored metadata.
- Derives `title` from each file's H1 if absent, `timestamp` from the file's last git-commit
  time if absent.
- Renames in-bundle `README.md` files to the reserved `index.md` (no frontmatter needed)
  and regenerates them in OKF §6 style: lead paragraph (preserved verbatim from the
  original README) + a concept list grouped by type + a subdirectories list. Walks every
  ancestor directory up to the bundle root, not just each concept file's direct parent,
  so a directory holding only subdirectories (no concept file directly inside it) still
  gets its own `index.md` and its parent's link to it isn't left broken.
- Sets `okf_version: "0.1"` on the bundle-root `index.md` only, per spec.
- `--dry-run` prints what would change without writing anything. Always run this first.

`--descriptions <file>.yaml` supplies curated `{description, tags}` per concept relpath —
the one genuinely editorial step. Auto-extracting a good one-sentence description from a
file's body is unreliable (skill-stub runbooks in particular tend to be a title plus an
`npx` code fence with no real prose to extract from); curate this file by hand per bundle.

### `scripts/okf_consistency.py` — configured house-consistency checker

```bash
python3 scripts/okf_consistency.py <repo_root> [<repo-relative-doc> ...] [--strict]
```

Reads `.agents/knowledge-base.yaml` and its configured `taxonomy_path`. With no
document arguments it checks the full configured bundle. It reports
`file:line — SEVERITY — finding` in this order:

1. Inline metadata that duplicates frontmatter.
2. Date aliases and inline dates that conflict with the configured
   `frontmatter.date_field`.
3. Status/confidence and lifecycle/current-phase conflicts.
4. Missing required fields, fields outside the house schema, malformed tags,
   and values absent from the taxonomy.
5. Long resource-linked concepts without a canonical-source or synchronization
   note.
6. Frontmatter title and H1 disagreement.
7. Filename, date-in-name, and configured topic-routing placement problems.

Exit `1` when a `CONFLICT` or `DUPLICATE` exists; warnings are review findings
unless `--strict` is supplied. Exit `2` for a missing/invalid config or unsafe
path. The config's date field is the sole last-update key: if it declares
`timestamp`, an added `last_updated` is a conflict, not a tolerated alias.
