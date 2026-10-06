# OKF: known lessons from real conversions, and related skills

Moved verbatim from the 1.1.0 SKILL.md; only link paths changed. Read it before a conversion, or when a converted bundle has broken generated links.

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

- [`synthesis-context-lifecycle`](../../synthesis-context-lifecycle/SKILL.md) — the tiered
  CONTEXT.md/REFERENCE.md/sessions/ project-memory pattern this skill's own conversion
  procedure was tracked with; OKF is about the *content* corpus, not the project-management
  layer (which stays explicitly out of OKF's own bundle scope).
- [`synthesis-anti-shortcuts`](../../synthesis-anti-shortcuts/SKILL.md) — dispatch/acceptance
  hygiene for running this conversion at scale (one sub-agent per repo).
- [`synthesis-kb-edit`](../../synthesis-kb-edit/SKILL.md) — config-driven editing
  and shipping; this skill owns its format and consistency gates.
- [`synthesis-knowledge-capture`](../../synthesis-knowledge-capture/SKILL.md) —
  durable fact extraction and in-place reconciliation before validation.
