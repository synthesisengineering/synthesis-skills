# Coverage map: implementation integrity 1.4.1 to 2.0.0

Every part of the 1.4.1 SKILL.md and where it lives now. Nothing was removed. No script or test under `scripts/` changed, and the three existing reference files are unchanged (each is under 50 lines; synthesis-autopilot's `domain_quality.py` loads the two `autopilot-*-quality.md` files by path, and synthesis-skills-manager links `verification-custody.md`).

| 1.4.1 section | Now |
|---|---|
| Frontmatter description (470 characters) | Shortened to 296 characters, keeping what the skill checks (data chains, placeholders, test honesty, environment parity, boundaries) and the triggers verify implementation, check completeness, is this done, integrity check, self-review, pre-PR check, ship check. The full text is quoted below |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type` | Kept: synthesis-onboarding's modular installer reads `depends_on`, and the `source.skill-contract` check in synthesis-agent-conformance reads the metadata keys |
| Title and first paragraph ("Verify that the implementation satisfies the user's outcome...") | SKILL.md (verbatim); Binding rule 1 |
| "Verification has an endpoint..." paragraph | references/scope-and-report.md (verbatim), under a new "Where verification ends" heading; Binding rule 7 |
| Autopilot task contracts paragraph | references/scope-and-report.md (verbatim apart from link paths, below); Binding rule 8 keeps the original links |
| Verification custody line | references/scope-and-report.md (verbatim apart from its link path, below); Binding rule 2 |
| When to Invoke | references/scope-and-report.md (verbatim) |
| Where This Fits — Verification Chain | references/background.md (verbatim) |
| Scope and stopping rule | references/scope-and-report.md (verbatim); Binding rules 3 and 7. Its "the relevant passes below" are in references/passes.md |
| The Seven Integrity Passes, Passes 1 to 7 | references/passes.md (verbatim); Binding rules 4 (Pass 3, step 6), 5 (Passes 1 and 5) and 6 (Pass 2) |
| Quick Integrity Check (5 minutes) | references/passes.md (verbatim) |
| Domain-Specific Checks: Database / ORM, API, Frontend / UI, Configuration & Deployment | references/domain-checks.md (verbatim) |
| The Integrity Report, with the severity scale | references/scope-and-report.md (verbatim) |
| Executable Acceptance Manifests | SKILL.md (verbatim, whole); Binding rule 9 |
| Extract, Do Not Restate | SKILL.md (verbatim, whole); Binding rule 9 |
| Authority Lives at the Boundary | SKILL.md (verbatim, whole); Binding rule 9 |
| Anti-Patterns This Protocol Prevents, all five | references/background.md (verbatim); Binding rule 6 restates "I'll Come Back to This" |
| Relationship to Other Skills | references/background.md (verbatim) |

The last three sections that stay in SKILL.md stay whole because `scripts/test_r5_contract.py` reads each one from SKILL.md as a `##` section and checks its wording. All three of those tests pass.

## Lines the coverage check reports, and why

`v5-skill-coverage-check.py` reports two lines. Both moved into references/scope-and-report.md with their wording unchanged; only their link targets gained a level so they still resolve:

- `For autopilot task contracts, use the owning [software](references/autopilot-software-quality.md) and [data/document](references/autopilot-data-quality.md) methods...` The two targets became `autopilot-software-quality.md` and `autopilot-data-quality.md`.
- `Before verification, follow [verification custody](../synthesis-implementation-integrity/references/verification-custody.md)...` The target became `../../synthesis-implementation-integrity/references/verification-custody.md`.

## The 1.4.1 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-implementation-integrity
description: "Post-implementation verification protocol that catches incomplete work, hidden shortcuts, and gaps between 'tests pass' and 'production works.' Systematically traces data chains, detects placeholders, audits test honesty, and verifies environment parity. Use when asked to: verify implementation, check completeness, implementation review, is this done, built properly, no shortcuts, verify work, completion check, integrity check, self-review, pre-PR check, ship check."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.4.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
