# Coverage map: fleet secrets 1.0.0 to 2.0.0

Every part of the 1.0.0 SKILL.md and where it lives now. At the 2.0.0 prose move nothing was removed or moved out: the whole text fits under the 8,000-byte limit, so it stayed in SKILL.md, with every command, flag and path as written. The v5 script change that followed is in its own section below; [preserved.md](preserved.md) holds the 2.0.0 SKILL.md and the 1.0.0 reference file verbatim.

| 1.0.0 section | Now |
|---|---|
| Frontmatter description | Kept unchanged; it is already under 300 characters |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type` | Kept (the installer and source checks read them) |
| Title and the two opening paragraphs | SKILL.md (verbatim) |
| Non-negotiables | SKILL.md, as binding rules 1 to 5: the same words, numbered instead of bulleted |
| Manifest schema | SKILL.md (verbatim) |
| Commands | SKILL.md (verbatim) |
| Enrollment (new Mac) | SKILL.md (verbatim); binding rules 6 and 7 |
| Rotation | SKILL.md (verbatim); binding rule 8 |
| (Opening paragraph: the age/SOPS stub) | binding rule 9 |

## Existing reference files

enrollment-age-sops.md is under 150 lines and unchanged.

## Lines the coverage check reports, and why

`v5-skill-coverage-check.py` reports 6 lines as not found verbatim, all from the Non-negotiables section:

- **"## Non-negotiables":** the heading was renamed "## Binding rules", because the format requires that section first and these five rules are exactly what must hold every time.
- **The first line of each of the five rules** ("- The secrets manifest carries refs only...", "- The real secrets manifest lives in the personal sphere...", "- No secret value or vault item content appears...", "- Service-account tokens (headless hosts) live in the OS credential store,", "- Every protective check fails closed: missing `op`, signed-out `op`,"): the bullet marker "- " became a number ("1. " to "5. "). The words are unchanged, and the continuation lines are found verbatim.

## v5 script changes (2026-10-05)

The v5 code evaluation (`tool-scripts.md`, row `synthesis-fleet-secrets/scripts/...`) ruled all four scripts CUT, never used (`op` not installed, no manifest outside test fixtures; R3.3 covers secrets in commits), and the brief asked that the skill's rules stay usable as a manual procedure.

| 2.0.0 part | Now |
|---|---|
| `secrets_manifest.py` (190 lines; normative field rules, rejects `value:`, unknown keys, duplicate paths) | Removed. The field table stays in SKILL.md and is read by hand before any write; binding rule 1 makes a `value:` key a defect to delete and rotate |
| `secrets_provider.py` (194; `OnePasswordBackend`, `AgeSopsBackend` stub, provider interface) | Removed. `op read` replaces `get`; the Python interface snippet is in [preserved.md](preserved.md) |
| `materialize.py` (330; dry-run, backup before overwrite, owner-only writes) | SKILL.md "Materialize by hand": list first, `umask 077`, back up, `op read`, `chmod 600` |
| `secrets_doctor.py` (259; `op` available, manifest valid, modes, values absent from the manifest and from git under `--scan-root`) | SKILL.md "Check by hand": `op whoami`, `stat`, a `grep` for `value:`, and `git grep -q -F -f <secret file>` per repository, where exit 2 or more counts as a failed check (rule 5) |
| `test_*.py` (four files, 752 lines) | Removed with the scripts; they used fake refs only |
| Description | Rewritten to say the procedure is by hand (the 1.0.0 one is quoted below) |
| Opening paragraph 2 ("This skill ships the 1Password (`op` CLI) backend tonight...") and binding rule 9 | The age/SOPS backend is a ruled future design; rule 9 says so without naming a stub class |
| Commands | "Materialize by hand" and "Check by hand" |
| Enrollment step 3, Rotation's "verify with the doctor" | Reworded to the manual check; the old lines are verbatim in [preserved.md](preserved.md) |
| references/enrollment-age-sops.md | The opening paragraph, step 3 and the implementation checklist no longer name provider classes; the rest is unchanged. The 1.0.0 file is verbatim in [preserved.md](preserved.md) |

Python lines: 973 before (plus 752 of tests), none after. Open question for the coordinator (evaluation section 5, item 15): which path a new Mac uses for credentials is not settled by this skill; mac-sync keeps its own credentials folder.

## The 1.0.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-fleet-secrets
description: "Provision machine secrets from a vault-backed provider across a personal Mac fleet. Use when asked to: fleet secrets, secrets manifest, materialize secrets, op backend, vault provisioning, secrets doctor, enroll a Mac's secrets, rotate fleet secrets."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
