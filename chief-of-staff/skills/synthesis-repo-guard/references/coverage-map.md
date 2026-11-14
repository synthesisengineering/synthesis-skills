# Coverage map: synthesis-repo-guard 2.7.3 to 3.0.0 (v5)

Ruling D8: every part of the 2.7.3 text has a new home, or sits in
[preserved.md](preserved.md) with the reason it was cut. Code verdicts come from the v5
code evaluation (guards and rituals report, repo-guard rows).

## Contents

- Coverage check result
- SKILL.md sections
- Scripts and their verdicts
- Edge cases and where they are held
- Frontmatter before v5 (verbatim)

## Coverage check result

Run on 2026-10-05 from the v5 worktree:

```text
$ python3 v5-skill-coverage-check.py <v5 worktree> synthesis-repo-guard
synthesis-repo-guard: 298 old lines, 0 not found verbatim
```

## SKILL.md sections

| 2.7.3 section | 3.0.0 home | How |
|---|---|---|
| Frontmatter description | SKILL.md description | Reworded |
| Large-manifest paragraph | preserved.md | Cut with the manifests |
| The Problem | SKILL.md purpose paragraph; binding rule 2 | Reworded; the two v1 failures (unactionable or leaky alerts, alerts on machine-fixable states) are in scan.md (Alerts) and binding rule 2 |
| The Architecture, three layers | SKILL.md purpose; preserved.md | Detector and messenger kept (`repo_sync_check.py`); checkpointer replaced by `synthesis handoff` |
| Confidentiality rule for alert surfaces (ABSOLUTE) | Binding rules 2 and 3; [scan.md](scan.md#alerts) | Reworded; the rule unchanged |
| Detection vs. commit, scoping rules | Binding rules 1 and 5 | Reworded |
| The checkpointer: local by default, remote by explicit event | Binding rule 4; [handoff-rules.md](handoff-rules.md) | Replaced by `synthesis handoff`; event-driven rule kept |
| The auto-sync class + runtime guard | Binding rule 7; [handoff-rules.md](handoff-rules.md) | The runtime remote check kept as a rule (not yet in the handoff; listed there) |
| Safety properties | [handoff-rules.md](handoff-rules.md#the-rules) | Each property a row, with whether the handoff enforces it |
| Stranded entries and per-repository retirement | preserved.md; the per-path lesson in handoff-rules.md | Cut with the manifests |
| Quick Start | Procedure | Rewritten for the slim script |
| Exit codes | [scan.md](scan.md#exit-codes-and-options) | Detector column verbatim |
| What the detector reports | [scan.md](scan.md#what-the-detector-reports) | Verbatim table, markers renamed to the JSON types |
| AI Tool Integration (Claude Code, Codex, Cursor hooks) | preserved.md | Cut: no Stop-time checkpoint in v5 |
| synthesis-console | [scan.md](scan.md#synthesis-console) | Tile and quiet-audio kept; Sync now and producer receipts need the console change at cutover |
| Scheduled execution, read-only only | [scan.md](scan.md#scheduled-execution--read-only-only); binding rule 4 | Verbatim, with the checkpointer sentence generalized |
| Relationship to Other Skills | SKILL.md procedure step 4 | Reworded: day-end runs handoff, then the scan |
| Command Reference | Procedure; scan.md options | Rewritten |
| Design Principles 1 to 7 | Binding rules 1, 2, 4, 6; scan.md | Reworded |
| Changelog 1.1.0 to 2.5.0 | preserved.md | History |
| Exact publication feedback | preserved.md | Cut with the receipts |

## Scripts and their verdicts

| 2.7.3 script | Verdict | Now |
|---|---|---|
| `repo_sync_check.py` (394 lines) | SLIM | `scripts/repo_sync_check.py` (about 110 lines with its docstring): the scan, the JSON report, the count-only alert and the mute flag |
| `checkpoint_sync.py` (4,022) | REPLACE | `synthesis handoff` (`synthesis/project.py`); rules in handoff-rules.md |
| `pending_manifest.py` (138) | CUT | none |
| `publication_receipt.py` (274) | CUT | none |
| Seven test files (4,484 lines) | REPLACE | `tests/test_repo_sync_check.py` in this skill; handoff tests belong to the project-state part |

## Edge cases and where they are held

| Scenario (guards evaluation section 3) | Held by |
|---|---|
| 14 alerts carry a count and a pointer only, silent while quiet-audio exists | `test_the_alert_carries_a_count_and_a_pointer_never_a_name` |
| Section 5 item 11: a read-only scan reports stranded source repos | `test_each_kind_of_stranded_work_is_reported_and_a_clean_repo_is_not`, `test_the_scan_only_reads` |
| Section 5 item 10: the console's report interface | the report's keys pinned in `test_each_kind_of_stranded_work_...`; scan.md documents it |
| 3 to 12 handoff rules | handoff-rules.md; tests belong to `synthesis handoff` (the project-state part); 3, 4, 6, 11, 12 not yet implemented there |
| 13 console plan-marker writes commit through the handoff | cutover change in synthesis-console |

## Frontmatter before v5 (verbatim)

```yaml
---
name: synthesis-repo-guard
description: "Workspace git-sync guard: detects unsynced repos, records session-attributed local handoff receipts, and batches private project-context commits for explicit remote handoff or day-end. Reports through confidentiality-safe channels."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.7.3"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
