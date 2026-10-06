# Coverage map: fleet secrets 1.0.0 to 2.0.0

Every part of the 1.0.0 SKILL.md and where it lives now. Nothing was removed or moved out: the whole text fits under the 8,000-byte limit, so it stays in SKILL.md. No script or test reads text from SKILL.md; `scripts/secrets_provider.py` names references/enrollment-age-sops.md in an error message, and that file is unchanged. Every command, flag and path is kept exactly as written.

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
