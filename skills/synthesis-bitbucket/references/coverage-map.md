# Coverage map: bitbucket 1.2.2 to 2.0.0

Every part of the 1.2.2 SKILL.md and where it lives now. Nothing was removed. No script, test or fixture under `scripts/` changed.

| 1.2.2 section | Now |
|---|---|
| Frontmatter description (464 characters) | Shortened to 297 characters. It keeps every trigger phrase ("bitbucket, bkt, bitbucket pr, open bitbucket pr, review bitbucket pr, bitbucket cli, bitbucket api") and names the PR lifecycle, reads, the `bkt api` escape hatch, repository binding and write safety. The full text is quoted below |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type` | Kept: synthesis-onboarding's modular installer reads `depends_on`, and the `source.skill-contract` check in synthesis-agent-conformance reads the metadata keys |
| Title and the three opening paragraphs (what `bkt` is, the rule in one line, companion skills) | SKILL.md (verbatim) |
| Install and pin | references/setup.md (verbatim); Binding rule 7 |
| Authenticate | references/setup.md (verbatim); Binding rule 8 |
| Configure connection context and bind each repository, with the context-host gotcha | references/setup.md (verbatim); Binding rule 8 |
| Explicit repository binding | SKILL.md (verbatim); Binding rules 4 and 5 |
| Command catalog: Read, Write, Escape hatch | SKILL.md (verbatim); Binding rule 6 restates the `pipeline run` warning |
| `gh` → `bkt` map, with the no-labels and PR-states note | SKILL.md (verbatim) |
| PR queue | references/pr-queue.md (verbatim) |
| Safety rules 1 to 3 | Binding rules 1 to 3 (verbatim, same numbers) |
| When NOT to apply | SKILL.md (verbatim) |

## Lines the coverage check reports, and why

Before this map existed, `v5-skill-coverage-check.py` reported one line: the heading `## Safety rules`. This map quotes it, so the check now reports none. It was renamed: the three safety rules are now the first three Binding rules, word for word and with the same numbers, under the `## Binding rules` heading the v5 format requires. The moved text has no relative links, so no link paths changed.

## The 1.2.2 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-bitbucket
description: "Work with Bitbucket Cloud repos through the open-source bkt CLI — PR lifecycle (list, view, diff, comment, approve, merge), repo/branch reads, and the bkt api escape hatch. Encodes auth setup, the context-host gotcha, a gh-to-bkt command map, and write-safety rules so agents use one consistent command surface instead of reinventing REST calls. Use when asked to: bitbucket, bkt, bitbucket pr, open bitbucket pr, review bitbucket pr, bitbucket cli, bitbucket api."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.2.2"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
