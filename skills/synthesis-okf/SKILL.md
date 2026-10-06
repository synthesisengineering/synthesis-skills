---
name: synthesis-okf
description: "Validate, convert and author content for Google's Open Knowledge Format (OKF v0.1) with a conformance validator, an idempotent frontmatter converter and a consistency checker. Use to adopt OKF for an LLM wiki, audit conformance, check frontmatter or taxonomy drift, or convert markdown notes."
license: CC0-1.0
depends_on: []
metadata:
  author: Rajiv Pant
  version: "2.0.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# synthesis-okf

Google's Open Knowledge Format (OKF v0.1, announced 2026-06-12) formalizes a pattern many
"LLM wiki" knowledge bases already use: a directory tree of markdown files with YAML
frontmatter, readable by any agent that can `cat` a file, shippable by anyone who can
`git clone` a repo. Per the spec's own §10, this is exactly the pattern OKF names as one
of its target use cases — the differentiator is only that it's now specified.

Google's reference repo (`github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf`)
ships an enrichment agent and an HTML visualizer, but no conformance validator or converter.
This skill fills that gap: a conformance validator, a converter, a house-consistency
checker, and a procedure proven across several real-world repo conversions.

## Binding rules

1. **Conformance (§9) has exactly three hard rules:** every non-reserved `.md` file has parseable YAML frontmatter, every frontmatter block has a non-empty `type`, and the reserved `index.md` and `log.md` follow their defined structure.
2. **Everything else is soft guidance.** Never reject a bundle for missing optional fields, unknown `type` values, broken cross-links or a missing `index.md`.
3. **Dry-run the converter first, always,** and review what it would change before writing.
4. **Existing frontmatter is never overwritten,** only backfilled where missing.
5. **Curate descriptions by hand** in `<bundle>-descriptions.yaml`; extracting them from file bodies is unreliable.
6. **When `.agents/knowledge-base.yaml` exists, run `okf_consistency.py` and resolve every CONFLICT and DUPLICATE.** Its configured date field is the sole last-update key.
7. **`type` values are free-form (spec §4.1).** Name types after what the files are; do not force one vocabulary across different repos.
8. **Before committing, review the diff** so no README's unique guidance is lost in its regenerated `index.md`.

## Contents

- [references/tools.md](references/tools.md): each tool's flags, behavior, checks and exit codes in full. Read it when running a tool for the first time or reading its output.
- [references/conversion-procedure.md](references/conversion-procedure.md): the full step-by-step conversion playbook. Read it before converting a corpus.
- [references/lessons.md](references/lessons.md): known lessons from real conversions, and related skills. Read it before a conversion or when generated links break.
- [references/okf-spec-v0.1.md](references/okf-spec-v0.1.md): the OKF v0.1 specification, verbatim. Read the section you need when a case is unclear.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.1.0 text now lives.
- The spec in brief, Commands, The conversion procedure: below.

## The spec, in brief

A **bundle** is a directory (conventionally a repo's `source/` directory, or the whole
repo for a dedicated knowledge repo). A **concept** is one markdown file: one unit of
knowledge. Conformance (§9) has exactly three hard rules:

1. Every non-reserved `.md` file has a parseable YAML frontmatter block.
2. Every frontmatter block has a non-empty `type` field.
3. Reserved filenames (`index.md`, `log.md`) follow their defined structure when present.

Everything else — missing optional fields (`title`, `description`, `tags`, `timestamp`,
`resource`), unknown `type` values, broken cross-links, missing `index.md` — is soft
guidance. A validator or consumer must not reject a bundle for any of it. Full spec:
[references/okf-spec-v0.1.md](references/okf-spec-v0.1.md) (verbatim, 451 lines).

`index.md` and `log.md` are the only two reserved filenames. `index.md` is a directory
listing for progressive disclosure and carries no frontmatter, except the bundle-root
`index.md`, which may declare `okf_version: "0.1"`. `log.md` is a chronological change
history (`## YYYY-MM-DD` headings, newest first). Both are excluded from a bundle's own
"knowledge" content — they're navigation scaffolding, not concepts.

## Commands

```bash
python3 scripts/okf_validate.py <bundle_dir> [--summary] [--check-links] [--quiet]
```

Exit codes: `0` conformant, `1` errors found, `2` usage error.

```bash
python3 scripts/okf_convert.py <bundle_dir> \
  --type-map instructions=Instruction,runbooks=Runbook,datasets=Dataset,contexts=Context \
  --descriptions <repo>-descriptions.yaml \
  [--dry-run]
```

`--dry-run` prints what would change without writing anything. Always run this first.

```bash
python3 scripts/okf_consistency.py <repo_root> [<repo-relative-doc> ...] [--strict]
```

It reports `file:line — SEVERITY — finding`. Exit `1` when a `CONFLICT` or `DUPLICATE` exists; warnings are review findings unless `--strict` is supplied; exit `2` for a missing or invalid config or an unsafe path.

## The conversion procedure

Full step-by-step, proven across multiple real conversions (a public 26-doc repo, a
72-doc personal knowledge base, and several other repos of varying size): see
[references/conversion-procedure.md](references/conversion-procedure.md). Summary:

1. **Baseline** — run the validator, expect non-conformant.
2. **Author descriptions** — the editorial 20%. Write `<bundle>-descriptions.yaml`.
3. **Convert** — dry-run first, review, then apply for real.
4. **Validate to clean** — 0 errors, 0 warnings, `--check-links` too.
5. **Check house consistency** — when `.agents/knowledge-base.yaml` exists, run
   `okf_consistency.py` and resolve every conflict/duplicate.
6. **Compiler config** — if the bundle feeds a compilation pipeline, add `**/index.md` and
   `**/log.md` to its exclude list (navigation scaffolding, not knowledge to compile).
7. **Review the diff** — confirm no README's unique guidance was lost in its `index.md`
   regeneration; spot-check descriptions.
8. **Commit.**
