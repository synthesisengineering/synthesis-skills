---
name: synthesis-okf
description: >
  Validate, convert, and author content for Google's Open Knowledge Format (OKF v0.1) —
  the markdown-plus-YAML-frontmatter knowledge-bundle spec announced 2026-06-12. Includes
  a conformance validator (the checker Google's own OKF repo ships none of), a converter
  that backfills OKF frontmatter onto an existing markdown corpus idempotently, and the
  proven repo-by-repo conversion procedure. Use when adopting OKF for an "LLM wiki" style
  knowledge base, auditing conformance, or converting a corpus of markdown notes/docs into
  a conformant, agent-readable bundle.
license: CC0-1.0
depends_on: []
metadata:
  author: Rajiv Pant
---

# synthesis-okf

Google's Open Knowledge Format (OKF v0.1, announced 2026-06-12) formalizes a pattern many
"LLM wiki" knowledge bases already use: a directory tree of markdown files with YAML
frontmatter, readable by any agent that can `cat` a file, shippable by anyone who can
`git clone` a repo. Per the spec's own §10, this is exactly the pattern OKF names as one
of its target use cases — the differentiator is only that it's now specified.

Google's reference repo (`github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf`)
ships an enrichment agent and an HTML visualizer, but no conformance validator or converter.
This skill fills that gap: a validator, a converter, and the procedure proven across
several real-world repo conversions.

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

## The conversion procedure

Full step-by-step, proven across multiple real conversions (a public 26-doc repo, a
72-doc personal knowledge base, and several other repos of varying size): see
[references/conversion-procedure.md](references/conversion-procedure.md). Summary:

1. **Baseline** — run the validator, expect non-conformant.
2. **Author descriptions** — the editorial 20%. Write `<bundle>-descriptions.yaml`.
3. **Convert** — dry-run first, review, then apply for real.
4. **Validate to clean** — 0 errors, 0 warnings, `--check-links` too.
5. **Compiler config** — if the bundle feeds a compilation pipeline, add `**/index.md` and
   `**/log.md` to its exclude list (navigation scaffolding, not knowledge to compile).
6. **Review the diff** — confirm no README's unique guidance was lost in its `index.md`
   regeneration; spot-check descriptions.
7. **Commit.**

## Known lessons from real conversions

- **The converter needs to walk every ancestor directory, not just each file's direct
  parent, when deciding what needs an `index.md`.** A purely-organizational directory
  (holding only subdirectories, no concept file of its own) is easy to miss and leaves a
  dangling link from its parent's generated index. Fixed in this skill's copy of
  `okf_convert.py` — if you're comparing against an older copy, this is the diff to look for.
- **Space-containing filenames break generated links.** CommonMark markdown link
  destinations can't contain unescaped spaces; a runbook named `Podcast Transcript
  Enhancement.md` needs a kebab-case rename (`git mv`, preserves history) before the
  converter's generated index links to it correctly.
- **Workspace-private / minimal-stub repos may have no `sources:`/`compilation:` block at
  all in their compile config** — if there's nothing for a compiler to walk, step 5 (the
  `index.md`/`log.md` exclude) has nothing to add to; that's a legitimate no-op, not a gap.
- **A bundle with zero markdown files is vacuously conformant.** Don't treat an empty
  `source/` tree as something needing conversion — there's nothing non-conformant about it.
- **`type` values are genuinely free-form (spec §4.1, no central registry).** Don't force
  a one-size-fits-all vocabulary across very different repos; a richer repo earns its own
  finer-grained types where the coarse `Instruction`/`Runbook`/`Dataset` split loses
  real distinctions worth keeping (e.g. a repo with substantial per-client content
  benefits from its own `Client` type rather than folding everything into `Dataset`).

## Related skills

- [`synthesis-context-lifecycle`](../synthesis-context-lifecycle/SKILL.md) — the tiered
  CONTEXT.md/REFERENCE.md/sessions/ project-memory pattern this skill's own conversion
  procedure was tracked with; OKF is about the *content* corpus, not the project-management
  layer (which stays explicitly out of OKF's own bundle scope).
- [`synthesis-anti-shortcuts`](../synthesis-anti-shortcuts/SKILL.md) — dispatch/acceptance
  hygiene for running this conversion at scale (one sub-agent per repo).
