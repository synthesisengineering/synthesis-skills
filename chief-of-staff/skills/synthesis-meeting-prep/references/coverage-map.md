# Coverage map: meeting prep 1.3.0 to 2.0.0

Every part of the 1.3.0 SKILL.md and where it lives now. Nothing was removed. Section numbers 1 to 5 are unchanged: sections 2, 3 and 5 stay in SKILL.md under their old headings, and sections 1 and 4 keep their headings in the files named below. No script or test reads text from SKILL.md; every command, flag and path is kept exactly as written.

| 1.3.0 section | Now |
|---|---|
| Frontmatter description | Shortened to under 300 characters, keeping its trigger words: 1:1s, reviews, forums, external meetings, interviews, follow-through, debrief |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type` | Kept (the installer and source checks read them) |
| Title | SKILL.md (verbatim) |
| "**Version 1.0.0** (2026-09-20): first release" note | references/background.md (verbatim) |
| Opening paragraph ("An agent preparing a principal...") | SKILL.md (verbatim) |
| 1. Configuration contract | references/profiles-and-sharing.md (verbatim apart from one link path); binding rule 11 |
| 2. The prep loop | SKILL.md (verbatim); binding rules 1, 3 and 6 to 9 |
| Shared prep contributions | references/profiles-and-sharing.md (verbatim); binding rule 12 |
| 3. The debrief loop | SKILL.md (verbatim); binding rule 10 |
| 4. Integration seams | references/background.md (verbatim) |
| 5. What the skill refuses | SKILL.md (verbatim); binding rules 1 to 5 |

## Existing reference files

All four keep their content. Short contents lists were added after the opening paragraph of the two over 150 lines, factor-inventory.md and requirements.md. structures.md and workspace-profiles.md are under 150 lines and unchanged.

## Lines the coverage check reports, and why

Before this map was written, `v5-skill-coverage-check.py` reported 1 line as not found verbatim (it now finds it only because this map quotes it). In section 1, `see [workspace-profiles.md](references/workspace-profiles.md). Migrating one` moved into references/ and its link now points to `workspace-profiles.md`, one folder down; the wording is unchanged.

## v5 script changes (2026-10-05)

Verdicts from the v5 code evaluation (`tool-scripts.md`, synthesis-meeting-prep rows): `prep_lint.py` KEEP; `prep_init.py` SLIM to about 180 lines that scaffold into `<workspace private repo>/profiles/meeting-prep`, because the migration is done (`~/.synthesis/meeting-prep/readers` is empty) and the grants solved an old-board problem.

| Part | Now |
|---|---|
| `prep_lint.py` (298 lines) | Unchanged; its tests moved from `scripts/test_prep_lint.py` to `tests/test_prep_lint.py` (only the import path changed) |
| `prep_init.py` `resolve`, `init`, `add-reader` | Kept, 569 lines before and 214 after. Same owner rules: an explicit absolute `--context-repo` that is exactly its Git checkout root (never home, `/`, a symlink, a subfolder or a path with `..`), a stable `--workspace` id, the `.owner.json` binding (a conflicting, boolean-schema, symlinked or hard-linked marker refuses; existing profiles with no marker refuse), no symlinked folder on the path, never overwrite (O_EXCL), 0600 files and 0700 folders, the 8 MiB bound checked before anything is created. The dependency on synthesis-context-lifecycle's `record_transaction.py` is gone; plain `os.open(O_EXCL)` gives the same no-overwrite and concurrency result |
| `prep_init.py migrate` | Removed (job finished). Its procedure is verbatim in [preserved.md](preserved.md); references/workspace-profiles.md now says how to handle a stray legacy profile by hand |
| `prep_init.py share-pack`, `write-pack` | Removed (REPLACE by the v5 board). Shared contributions go through `synthesis who`, `synthesis msg`, and the holder's `synthesis release`/`claim` of one file; binding rule 12 and references/profiles-and-sharing.md say so. The old text is verbatim in [preserved.md](preserved.md) |
| `scripts/test_prep_init.py`, `scripts/test_profile_workspace.py` | Merged into `tests/test_prep_init.py`: every scaffold and ownership test kept (including the concurrent same-reader creation and the boolean owner-marker schema); the migration and grant tests left with their code |

Scenarios from section 3 of the evaluation: E73 (profiles in the workspace's private repository, never `~/.synthesis`) is `tests/test_prep_init.py::test_workspace_profiles_are_separate_by_explicit_owner` and `test_cli_without_owner_refuses_before_writing`; E74 (a "don't raise" line outside the footer, ticket IDs for a non-technical reader, invented precision, no basis) is `tests/test_prep_lint.py`.

Prose changed with the scripts: SKILL.md binding rule 12, the Contents lines for the two profile references, and prep-loop step 5, which now shows the exact `prep_lint.py` command line. The 1.3.0 step 5 opened with this line, reworded only to carry the flags:

```text
5. **Lint.** Run `scripts/prep_lint.py` on the draft. It checks the
```

references/profiles-and-sharing.md (the last paragraph of section 1 and the whole shared-contributions section) and references/workspace-profiles.md (the migration sections) changed too; the old text is verbatim in [preserved.md](preserved.md).

## The 1.3.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-meeting-prep
description: "Prepare a principal for any meeting the way a wise chief of staff would: weigh 60+ factors across the meeting, participants, principal's position, knowledge, and risk; model the readers before drafting; deliver a dense, scannable pack with a capture half; then debrief the transcript into decisions, commitments, and reader-profile updates. Use for 1:1s, reviews, forums, external meetings, interviews, and post-meeting follow-through."
license: "CC0-1.0"
depends_on: ["synthesis-context-lifecycle"]
metadata:
  author: "Rajiv Pant"
  version: "1.3.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
