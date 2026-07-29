# OKF Conversion Procedure

The repeatable playbook for converting an existing markdown corpus into a conformant
OKF v0.1 bundle. Proven on a public 26-doc reference-implementation repo (2026-06-17,
0 errors / 0 warnings) and several other repos of varying size since. Tooling:
[`okf_convert.py`](../scripts/okf_convert.py), [`okf_validate.py`](../scripts/okf_validate.py).

## Conventions (finalized)

- **Bundle = the corpus you want agent-readable** (conventionally a repo's `source/`
  directory). Project-management scaffolding (task trackers, session logs, daily plans,
  compiled build output) is a separate layer with its own conventions, not part of the
  OKF bundle.
- **`type` by top-level subdir:** `instructions/`→`Instruction`, `runbooks/`→`Runbook`, `datasets/`→`Dataset`, `contexts/`→`Context`. (Richer repos may add finer types, e.g. `Biography Timeline Entry`.) Free-form per spec §4.1; keep self-explanatory.
- **Frontmatter order:** `type` (required), `title` (from H1), `description` (curated), `tags` (block list), `timestamp` (file's last git-commit time, ISO 8601 w/ offset). `resource` only where a canonical URI exists — legitimately absent for abstract concepts (so the validator does not warn on it).
- **`README.md` → `index.md`:** READMEs are non-reserved (would need frontmatter); renamed to the reserved `index.md` (no frontmatter) and regenerated in OKF §6 style — lead paragraph + `# <Type>` concept lists + `# Subdirectories`. Links/descriptions drawn from sibling frontmatter.
- **Root `source/index.md`** carries `okf_version: "0.1"` (the one place frontmatter is permitted in an index).
- **Compiler:** add `**/index.md` and `**/log.md` to the repo's `compile-config.yaml` `exclude` (OKF navigation scaffolding, not knowledge to compile) — mirrors the prior `**/README.md` exclusion.

## Steps (per repo)

1. **Baseline:** `okf_validate.py <repo>/source --summary` (expect non-conformant).
2. **Author descriptions** (the editorial 20%): write `<repo>-descriptions.yaml` mapping each concept relpath → `{description, tags}`. Author from the concept's *purpose*, not its body — many runbooks are thin skill-pointers whose real content lives in the installed skill.
3. **Convert:** `okf_convert.py <repo>/source --type-map instructions=Instruction,runbooks=Runbook,datasets=Dataset,contexts=Context --descriptions <repo>-descriptions.yaml`. (Run `--dry-run` first to review.)
4. **Validate to clean:** `okf_validate.py <repo>/source --summary --check-links` → **0 errors, 0 warnings**.
5. **Compiler config:** add `index.md`/`log.md` to `exclude`.
6. **Review the diff** (`git status`, `git diff`): confirm READMEs→index.md lost no unique guidance; spot-check descriptions. READMEs are git-tracked, so the rename is fully reversible.
7. **Commit:** generic commit message for any public-facing repo; check the staged git index before committing if sub-agents or parallel processes touched the same tree (a shared-index sweep, not a per-repo rule).

## Lessons from real conversions

- **Description seeding fails on skill-stub runbooks** (body is "converted to a skill" + an `npx` code fence). The fence-aware extractor now returns empty rather than seeding a shell command; descriptions are curated in the per-repo YAML. This will recur in every repo whose runbooks point to skills.
- **`resource` is genuinely N/A** for Instruction/Runbook/Dataset concepts — don't force it; the validator correctly treats its absence as fine.
- **The converter is idempotent-friendly:** existing frontmatter is back-filled (`type` added if missing), never overwritten — safe to run against a corpus where some files already carry hand-authored frontmatter.
- **Heterogeneity across repos is expected.** A richer, more specialized corpus may warrant finer types than the coarse `Instruction`/`Runbook`/`Dataset` split (e.g. a dedicated type for a large, structurally distinct subdirectory) and its own curated description set. Audit per bundle at step 1 rather than assuming one type-map fits every corpus.
