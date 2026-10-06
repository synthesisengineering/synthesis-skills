# Coverage map: synthesis-okf 1.1.0 to 2.0.0

Every part of the 1.1.0 SKILL.md and where it lives now. Nothing was removed. No script or test reads text from SKILL.md; every command, flag and path is kept exactly as written, and SKILL.md's Commands section repeats the three command lines with their exit codes.

| 1.1.0 section | Now |
|---|---|
| Frontmatter description (folded, long) | Shortened to under 300 characters, keeping its trigger words: validate, convert, author, OKF, LLM wiki, audit conformance, frontmatter or taxonomy drift, convert markdown notes |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type` | Kept (the installer and source checks read them) |
| Title and the two opening paragraphs | SKILL.md (verbatim) |
| The spec, in brief | SKILL.md (verbatim); binding rules 1 and 2 |
| Tools: `okf_validate.py`, `okf_convert.py`, `okf_consistency.py` | references/tools.md (verbatim); command lines and exit codes also in SKILL.md under Commands; binding rules 3 to 6 |
| The conversion procedure (summary) | SKILL.md (verbatim); binding rule 8 |
| Known lessons from real conversions | references/lessons.md (verbatim); binding rule 7 |
| Related skills | references/lessons.md (verbatim apart from link paths) |

## Existing reference files

Both keep their content. okf-spec-v0.1.md is over 150 lines, so a contents list was added above its first heading, marked as added for navigation; the 451 lines of specification text below it are unchanged, so the "(verbatim, 451 lines)" note in SKILL.md still describes the specification itself. conversion-procedure.md is under 150 lines and unchanged.

## Lines the coverage check reports, and why

Before this map was written, `v5-skill-coverage-check.py` reported 4 lines as not found verbatim (it now finds them only because this map quotes them). All four are the Related skills bullets, moved from SKILL.md into references/lessons.md, whose links gained one `../` for the deeper folder; the wording is unchanged:

- `` - [`synthesis-context-lifecycle`](../synthesis-context-lifecycle/SKILL.md) — the tiered ``
- `` - [`synthesis-anti-shortcuts`](../synthesis-anti-shortcuts/SKILL.md) — dispatch/acceptance ``
- `` - [`synthesis-kb-edit`](../synthesis-kb-edit/SKILL.md) — config-driven editing ``
- `` - [`synthesis-knowledge-capture`](../synthesis-knowledge-capture/SKILL.md) — ``

## v5 script changes (2026-10-05)

Verdicts from the v5 code evaluation (`tool-scripts.md`, synthesis-okf rows): `okf_validate.py` and `okf_convert.py` KEEP; `okf_consistency.py` SLIM to about 300 lines.

| Part | Now |
|---|---|
| `okf_validate.py` (189 lines), `okf_convert.py` (326 lines) | Unchanged. The published article on the validator documents its command line, which is the same. New tests: `tests/test_okf_validate.py` (scenario E92: frontmatter with a non-empty `type` on every non-reserved file, broken links reported only under `--check-links` and only as info, exit 2 for a missing bundle) and `tests/test_okf_convert.py` (`--dry-run` writes nothing; backfill never overwrites existing fields; the converted bundle validates) |
| `okf_consistency.py` (630 lines) | 357 lines (target about 300), same command line, same seven checks, same messages, severities, ordering and exit codes: on a synthetic repository exercising every check, the old and new scripts printed byte-identical reports. The size came from one-finding-per-twelve-lines construction, now one helper call each. One defect fixed while slimming: an unsafe `topic_routing` path used to raise an uncaught error mid-report; it now exits 2 like every other contract error |
| `scripts/test_okf_consistency.py` | `tests/test_okf_consistency.py` (path change only; PyYAML is skipped where missing, since CI's Python has only pytest) |

No prose changed: every command in SKILL.md and references/tools.md is unchanged.

## The 1.1.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-okf
description: >
  Validate, convert, and author content for Google's Open Knowledge Format (OKF v0.1) —
  the markdown-plus-YAML-frontmatter knowledge-bundle spec announced 2026-06-12. Includes
  a conformance validator (the checker Google's own OKF repo ships none of), a converter
  that backfills OKF frontmatter onto an existing markdown corpus idempotently, a
  config-driven seven-point metadata-consistency checker, and the proven repo-by-repo
  conversion procedure. Use when adopting OKF for an "LLM wiki" style knowledge base,
  auditing conformance, checking frontmatter/body drift or taxonomy consistency, or
  converting a corpus of markdown notes/docs into a conformant, agent-readable bundle.
license: CC0-1.0
depends_on: []
metadata:
  author: Rajiv Pant
  version: "1.1.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
