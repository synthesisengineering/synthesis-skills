# Coverage map: context lifecycle 1.22.0 to 2.0.0 (v5)

Ruling D8: every rule of the old text has a new home, or sits in a preserved
file with the reason. "Verbatim" means the old lines appear unchanged in the
named file. "Reworded" means kept in plain words for v5, with the original in
the preserved files. "Cut" means not carried; the reason is here and in
[preserved.md](preserved.md#what-was-cut-and-why).

## Contents

- [Coverage check results](#coverage-check-results)
- [Frontmatter before v5 (verbatim)](#frontmatter-before-v5-verbatim)
- [1.22.0 SKILL.md](#1220-skillmd)
- [1.22.0 reference files](#1220-reference-files)
- [Scripts](#scripts)
- [R1.5 scenarios and their tests](#r15-scenarios-and-their-tests)

## Coverage check results

Run on 2026-10-05 from the v5 worktree:

```text
$ python3 v5-skill-coverage-check.py <v5 worktree> synthesis-context-lifecycle
synthesis-context-lifecycle: 1560 old lines, 0 not found verbatim
```

## Frontmatter before v5 (verbatim)

```yaml
---
name: synthesis-context-lifecycle
description: "Three-tier context architecture for managing AI working memory across long-running projects. Use when asked to: manage context, project context, session management, context lifecycle, working memory, archival, archive sessions, context maintenance, garbage collection for context, tiered context."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.22.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

Kept: `name`, `license`, `depends_on`, `author`, `source_repo`, `source_type`.
Version 2.0.0, `format: v5` added, description rewritten under 300 characters
with the old triggers (project context, session management, working memory,
archival, context maintenance).

## 1.22.0 SKILL.md

| 1.22.0 section | v5 home | How |
|---|---|---|
| The Problem (paragraph and four-type table) | SKILL.md purpose paragraph; [tiers-and-templates.md](tiers-and-templates.md#the-problem) | Verbatim in the reference, summarized in the purpose paragraph |
| The Architecture (pointer) | [tiers-and-templates.md](tiers-and-templates.md) | The full architecture, verbatim |
| Session Start Protocol: registry-first resolver, `--no-fetch`, no global pointer | Binding rule 2; [session-protocols.md](session-protocols.md#session-start-protocol) | Reworded: `synthesis resume`; "a global pointer cannot override the conversation's project" kept as "there is no global pointer" |
| Session Start steps 1 to 7 | session-protocols.md | Verbatim (step 4's "structured state where present" dropped) |
| `conformance.py activate` pointer | session-protocols.md | Replaced: `synthesis use` or `synthesis resume` records the session's project; SessionStart re-injects it |
| Seamless client and computer switching (five steps, boundaries) | [session-protocols.md](session-protocols.md#switching-harness-or-mac); Binding rule 12 | Steps reworded to v5 (no Stop receipts; `synthesis handoff`); the boundaries paragraph verbatim |
| Why this order matters; Visible to the user | session-protocols.md | Verbatim |
| Mid-Session Refresh Protocol: triggers, protocol, compaction signals, delegation | Binding rule 3; [session-protocols.md](session-protocols.md#mid-session-refresh-protocol) | Verbatim; step 6 reworded |
| Editing a Durable Context File (pointer) | Binding rule 5; [editing-and-archival.md](editing-and-archival.md) | See the reference rows |
| Decision and transfer succession | Binding rule 11; [material-context.md](material-context.md) | Doctrine kept; `review-succession`/`apply-succession` cut |
| The Archival Protocol | Binding rule 4; [editing-and-archival.md](editing-and-archival.md#the-archival-protocol) | Verbatim except step 8 and the remote-readiness note |
| Migration Guide; Project Status Transitions; Project Spawning | editing-and-archival.md | Verbatim |
| Repo Families and Deletion Units | Binding rule 9; [deletion-units.md](deletion-units.md) | Verbatim |
| Measuring Context Quality; Context as Infrastructure; Evolution Stages | [tiers-and-templates.md](tiers-and-templates.md#measuring-context-quality) | Verbatim |
| Executable Working State | Binding rule 10; [editing-and-archival.md](editing-and-archival.md#executable-working-state--resourcesscripts) | Verbatim; the citation check is the writer's (the doctor no longer runs it) |
| The Context Doctor (bounded, reference shard vocabulary, post-close review, denominators) | Binding rule 13; [context-doctor.md](context-doctor.md) | Reworded to the v5 doctor; shard-internal checks cut; post-close review kept |
| Local Continuity and Remote Readiness Protocol | [session-protocols.md](session-protocols.md#switching-harness-or-mac) | Replaced: R1.3 and R1.4 |
| `skill-outputs` packet check paragraph | — | Cut from the doctor (packet provenance is synthesis-decision-packet's) |
| "complete context protocol details remain mandatory" | — | The references are listed in Contents with read-when lines |
| Durable custody before a session ends | synthesis-project-management [coordination.md](../../synthesis-project-management/references/coordination.md#durable-work-placement) | Reworded; temporary-placement rules verbatim there |
| Native memory capture-buffer ingestion (`memory-probe`, `memory-ingest`, `memory-clear-plan`) | [material-context.md](material-context.md#native-memory); synthesis-daily-rituals day-end | Replaced: the sweep is a day-end ritual step; routing kinds and the ALWAYS-PRESERVE rule kept in prose |
| Canonical destination binding (`repos.yaml` memory scope) | — | Cut with the memory-ingest command it configured |

## 1.22.0 reference files

| File | v5 home | How |
|---|---|---|
| context-protocol-details.md: The Architecture (tiers, CONTEXT, REFERENCE, sharding, sessions, attribution) | [tiers-and-templates.md](tiers-and-templates.md) | Verbatim, except the shard check vocabulary (the doctor keeps only the budget) and the added current-state block |
| ...: Measuring Context Quality | tiers-and-templates.md | Verbatim |
| ...: The Context Doctor | [context-doctor.md](context-doctor.md) | Lessons verbatim; usage, checks table and report cache replaced by the v5 doctor |
| ...: Structured operational state | — | Cut: no `CURRENT_STATE.json`; the current-state block stays in CONTEXT.md |
| ...: Context as Infrastructure; Evolution Stages | tiers-and-templates.md | Verbatim |
| ...: Local Continuity and Remote Readiness Protocol | session-protocols.md | Replaced (see above) |
| durable-record-operations.md: Editing (context_edit commands, apply, transactions, file inputs, table and line safety, header lag, body currency, companion rules) | [editing-and-archival.md](editing-and-archival.md) | Rules kept; commands replaced by harness edit tools; header lag became the doctor's `header-lag`; companion rules verbatim |
| ...: Archival, Migration, Status Transitions, Spawning, Deletion Units, Quality, Executable State, Infrastructure, Evolution | editing-and-archival.md, deletion-units.md, tiers-and-templates.md | Verbatim |
| ...: The Context Doctor (duplicate) | context-doctor.md | As above |
| ...: Shared registry entry edits; removing the final registry entry | synthesis-project-management [coordination.md](../../synthesis-project-management/references/coordination.md#projectsindexyaml-has-many-writers) | Replaced: claim the index, edit, commit only it |
| artifact-succession.md | [material-context.md](material-context.md#replacing-an-item-list-or-a-decision-interface); synthesis-decision-packet | Four questions kept; request schema, custody and bounds cut |
| material-context.md | [material-context.md](material-context.md) | What to preserve, the detour example and the authority rules verbatim; schema-2 requests, review artifacts and scan bounds cut |
| autopilot-recovery.md | synthesis-autopilot | Replaced by the plan file (R6.1) |
| record-transactions.md | — | Cut: git is the journal; claims serialize writers |

## Scripts

| Script | Verdict | v5 home | Tests |
|---|---|---|---|
| context_doctor.py | SLIM | `scripts/context_doctor.py` (rewritten, about 590 lines) | tests/test_context_doctor.py |
| context_currency.py | SLIM | merged into the doctor (per-field ordinals, body markers, item stamps) | tests/test_context_doctor.py |
| context_edit.py | REPLACE | harness Edit and apply_patch; `header-lag` in the doctor; memory sweep in day-end | tests/test_context_doctor.py (`phase_moved_but_last_session_did_not`) |
| record_transaction.py | CUT | — | — |
| record_succession.py | SLIM (outside this skill) | the decision-packet generator | handled by its owner |
| review_ledger.py | REPLACE | the lapse register (workspace instructions, day-end and weekly review) | — |

## R1.5 scenarios and their tests

All in `tests/test_context_doctor.py`.

| Scenario (v5 code evaluation, section 3) | Test |
|---|---|
| CONTEXT.md over 150 (active) or 80 (completed) fails; REFERENCE.md over 300 warns | `context_over_150_lines_active_or_80_completed_fails_and_reference_over_300_warns`, `a_standing_project_over_its_reference_budget_is_told_to_shard` |
| index and CONTEXT status disagree; Status wins over Phase; "not complete" is never completed | `index_and_context_status_must_agree`, `status_wins_over_phase_wording`, `unknown_status_is_a_defect_and_a_retired_one_a_warning` |
| Last session behind the newest log entry, including same-day staleness by round; each field alone; first ordinal is identity | `last_session_behind_the_newest_log_entry_fails`, `same_day_staleness_is_caught_by_round_and_each_field_is_judged_alone`, `the_first_ordinal_in_a_field_is_its_identity` |
| "Phase changed but Last session did not" (from the old editor) | `phase_moved_but_last_session_did_not` |
| A bulk commit is not a session | `a_bulk_commit_touching_many_projects_is_not_a_session` |
| Stamped items past the horizon; unstamped; checked and narrative are not obligations; malformed and impossible stamps | `item_stamps` |
| Paused and completed stay quiet; work after completion is reported | `paused_and_completed_projects_stay_quiet_on_advice_but_not_on_work_after_completion`, `a_post_close_review_silences_the_finding_until_a_new_commit_and_must_resolve` |
| Unreadable or non-git source exits non-zero, never clean; missing index is a defect | `unreadable_or_non_git_sources_cannot_be_called_healthy`, `nothing_to_audit_is_not_a_clean_result`, `projects_without_an_index_and_index_entries_without_a_folder_are_defects`, `discovered_roots_without_projects_are_skipped_but_a_named_one_cannot_be_audited` |
| Gitignored or uncommitted CONTEXT.md is reported | `a_gitignored_context_is_a_defect_and_an_uncommitted_one_a_warning`, `durability_no_remote_is_a_defect_and_unpushed_a_warning` |
| Output leads with the active project and counts the rest; a new convention starts as a warning | `output_leads_with_the_active_project_and_counts_the_rest`, `item_stamps`, `a_single_project_run_shows_its_full_list` |
| Section marker staleness | `a_stale_section_marker_fails` |
| Session titled after the project (2026-09-21, from the old `test_session_start_protocol.py`) | `session_start_names_the_session_after_the_project` |
