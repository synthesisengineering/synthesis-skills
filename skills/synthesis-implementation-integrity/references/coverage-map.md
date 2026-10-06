# Coverage map: implementation integrity 1.4.1 to 2.0.0

Every part of the 1.4.1 SKILL.md and where it lives now. Nothing was removed at the 2.0.0 prose move, when no script or test under `scripts/` changed, and the three existing reference files are unchanged (each is under 50 lines; synthesis-autopilot's `domain_quality.py` loads the two `autopilot-*-quality.md` files by path, and synthesis-skills-manager links `verification-custody.md`).

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
| Executable Acceptance Manifests | At 2.0.0: SKILL.md (verbatim, whole). Since the v5 script change: SKILL.md "Executable Acceptance", rewritten for PR CI; the 1.4.1 text is verbatim in [preserved.md](preserved.md). Binding rule 9 |
| Extract, Do Not Restate | SKILL.md (verbatim, whole); Binding rule 9 |
| Authority Lives at the Boundary | At 2.0.0: SKILL.md (verbatim, whole). Since the v5 script change: its first paragraph rewritten around v5's enforcing boundaries (merge on PR CI, the approval-code guards, the commit check), its last paragraph verbatim; the 1.4.1 text is in [preserved.md](preserved.md). Binding rule 9 |
| Anti-Patterns This Protocol Prevents, all five | references/background.md (verbatim); Binding rule 6 restates "I'll Come Back to This" |
| Relationship to Other Skills | references/background.md (verbatim) |

The last three sections that stay in SKILL.md stay there because `tests/test_r5_contract.py` (formerly `scripts/`) reads each one from SKILL.md as a `##` section and checks its wording.

## v5 script changes (2026-10-05)

The v5 code evaluation (`tool-scripts.md`, row `synthesis-implementation-integrity/scripts/acceptance_suite.py`) ruled REPLACE: "PR CI running pytest is the only gate" (v5 principle 5, R7.3).

| Part | Now |
|---|---|
| `scripts/acceptance_suite.py` (974 lines), `scripts/test_acceptance_suite.py`, `scripts/test_acceptance_batches.py` | Removed. The tests had begun to fail on this branch because `acceptance-suite.yaml` (22,795 lines) was deleted with the release machinery; they tested the manifest runner, not a rule another part of v5 relies on. The rules the manifest carried (closed universe, every changed surface has a case, red before green, terminal states, the unverified remainder) are in SKILL.md "Executable Acceptance", applied to the pull request's CI run. The script also imported synthesis-skills-manager's `release_check_groups.py`, which goes with the old release machinery |
| SKILL.md "Executable Acceptance Manifests" | Renamed "Executable Acceptance" and rewritten: PR CI on the exact head is the acceptance evidence, the PR diff is the changed-surface universe, the PR description names entry point, enforcing boundary, consumer and remainder |
| SKILL.md "Authority Lives at the Boundary" | First paragraph rewritten around v5's real boundaries; the transaction-bound receipt paragraph retired (verbatim in [preserved.md](preserved.md)); the last paragraph unchanged |
| `scripts/test_r5_contract.py` | `tests/test_r5_contract.py`, with four changes: the two integrity tests check the rewritten sections; the scratchpad-sweep test reads autopilot's `references/delegation.md`, where the rebuilt autopilot (commit 5f535c4) keeps the question (its close step, verbatim); and the scripts-tier test follows synthesis-context-lifecycle's v5 rewrite (commit b6a2877): the "Executable Working State — resources/scripts/" section moved from SKILL.md to `references/editing-and-archival.md` (the test finds it in whichever live reference holds it), the old SKILL.md pointer "Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting" became binding rule 10 ("Preserve executable state under `resources/scripts/`") plus a Contents link to that reference, both now asserted, and "does not prove the script is correct" was reworded as "existence never proves the script ... correct", which the test accepts. Every other contract phrase is unchanged and still asserted. The disclosure-policy test is unchanged |

Three of the old tests read the autopilot SKILL.md the rebuild replaced; only one of them was in this skill (`test_checkpoint_and_autopilot_ask_the_scratchpad_sweep_question`, repointed as above). The other two are in synthesis-adversarial-review; its coverage map says where each went. Python lines: 974 before (plus 1,908 of tests), none after.

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
