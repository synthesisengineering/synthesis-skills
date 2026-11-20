# Coverage maps: context lifecycle

Read when checking where a rule of an earlier text lives now (ruling D8). Two rewrites, newest first: 2.8.2 to
2.9.0, the rewrite to the repository's standard (`docs/skill-writing.md`), then 1.22.0 to 2.0.0, the v5 restructure,
kept word for word one heading level down. Between 2.0.0 and 2.8.2 the skill added rules 14 and 15 and
references/session-transcripts.md, and moved no rule.

Contents:
- 2.8.2 to 2.9.0: SKILL.md; references/procedure.md; references/preserved.md; where the binding rules state the
  moved procedure; files unchanged
- 1.22.0 to 2.0.0 (v5): the coverage check, the frontmatter before v5, the 1.22.0 SKILL.md and reference files, the
  scripts, the R1.5 scenarios and their tests

## 2.8.2 to 2.9.0: the rewrite to the D8 standard

Every rule and requirement of the 2.8.2 SKILL.md, in its order, and where it lives in 2.9.0. **Kept**: the same
words in the same file. **Moved**: the same words in another file. **Reworded**: the same rule in new words, with
the old words in [preserved.md](preserved.md). **Merged**: two passages that said the same thing, now said once.
**Added**: a new sentence, with its source. Nothing was dropped. Binding rules keep their numbers, which the skill's
evaluation cases, its procedure ("hand off per rule 12") and two tests cite: `tests/test_sessions.py` reads rule 15,
and synthesis-implementation-integrity's `tests/test_r5_contract.py` reads rule 10. Each rule now carries its
trigger, scope and reason in SKILL.md (W2, W5); where a rule takes a sentence from a reference, the reference keeps
that sentence word for word.

### SKILL.md

| 2.8.2 | 2.9.0 | How |
|---|---|---|
| Frontmatter: name, description, license, `depends_on`, author, source, format, category | Frontmatter | Kept. The description is unchanged: it already leads with the key use case, and the evaluation harness cannot test a new one (W1) |
| Title | Title | Kept |
| Opening paragraph, first two sentences: AI collaborators start every session with zero context; a single context file grows without bound because it mixes information with different lifecycles | references/tiers-and-templates.md, The Problem | Merged: The Problem says both in nearly the same words, and background stays out of SKILL.md (W19) |
| Opening paragraph, third sentence: "This skill splits a project's memory into three tiers, each with its own budget and update rule, and verifies them with a doctor." | Opening paragraph | Reworded: "Keeps a project's memory in three tiers of records, each with a budget and update rule, checked by a doctor" (format rule 2) |
| (none) | The line above rule 1: the rules hold when a request asks otherwise; say which rule applies and why, then do what it allows | Added (W8, format rule 11): the rules protect the records every later session resumes from |
| Rule 1: the project files are the memory: CONTEXT.md (≤150 lines; ≤80 when completed), REFERENCE.md (stable facts, ≤300), `sessions/YYYY-MM.md` (append-only); chat, native memory and compaction summaries are not | Rule 1 | Reworded (W2, W5): the head as an action, "Treat the project files as the memory"; the three files with their budgets and "Chat, native memory and compaction summaries are not" kept word for word; what to do when one of them disagrees with a record: follow the record (material-context.md, Native memory) and report the discrepancy (session-protocols.md, the Mid-Session Refresh Protocol's step 5), with the reason, a stale note reads as current |
| Rule 2: run the Session Start Protocol before substantive work and show the verification: `date`, then `git log` and `git status` on the project, then CONTEXT.md, the newest session entries, REFERENCE.md | Rule 2 | Reworded, with a fix for an evaluation finding (W2, W5, W7, W15): the head kept, with "on a project"; the trigger, from session-protocols.md (at session start, at the project's first mention, after a switch from another project); `synthesis resume <id>` and "title the session after the project where the client allows it" from the Procedure, the second as the skill's own test `test_session_start_names_the_session_after_the_project` requires; the steps in their order and "show the verification" kept; the reason, from session-protocols.md's "Why this order matters" and "Visible to the user"; the stop: once the protocol has run for the project this session, act on what it read, with rule 3 deciding when to look again. Case cl-07's first version said only that CONTEXT.md had just been read, and in all four runs Sonnet with the skill said it would run the protocol before sending; the case now says the protocol ran |
| Rule 3: refresh on the triggers: before any time-interval claim, after an hour's pause, every ~25 tool calls, on any drift or compaction signal, before writing a session log | Rule 3 | Reworded (W2, W5): the head and the five triggers kept word for word; what a refresh does, from the Mid-Session Refresh Protocol's steps 1 to 5; the reason, from that section's opening |
| Rule 4: archive first, delete second: write to sessions/ or REFERENCE.md, verify it is there, then remove it from CONTEXT.md | Rule 4 | Reworded (W2, W5): the head and the three steps kept; the trigger, any content leaving CONTEXT.md, with the Procedure's 120-line mark; the reason, from the Archival Protocol |
| Rule 5: re-read before editing and verify after: build edits from what the file says now, with an edit tool that fails on a missing anchor; never report an update you did not read back | Rule 5 | Reworded (W5, W14): every clause kept; the scope, every edit to a record; the reason, from editing-and-archival.md's "Editing a durable context file" |
| Rule 6: header fields move together: update `Last session` first or with `Phase`; a field is judged alone, and its first ordinal is its identity | Rule 6 | Reworded (W2, W5): the head as an action naming CONTEXT.md; every clause kept; from editing-and-archival.md's "Header fields move together": the ordinal families, `Phase` never ahead of `Last session`, the two describing one state, and a fresh `Phase` that cannot hide a stale `Last session` |
| Rule 7: workdays come from dated session entries, never from commit times | Rule 7 | Reworded (W5, W14): the head as an action, "never from commit times" kept; the scope, stating or judging a session's date; the reason, from session-protocols.md's step 2 and context-doctor.md's "Publication time and workday are different evidence" |
| Rule 8: stamp open items `(as of YYYY-MM-DD, review Nd)`; checked items and prose are not obligations | Rule 8 | Reworded (W3, W5): the stamp and the last clause kept; when to stamp, as an item is written or re-checked, and the reason, from editing-and-archival.md's "Stamped open items" |
| Rule 9: route by deletion unit when writing: would this survive the relationship's end? The ALWAYS-PRESERVE class goes to the permanent root; inventories count out-of-scope items, never itemize them | Rule 9 | Reworded (W2, W5, W7): every clause kept; from deletion-units.md: where each answer routes, the class's members, asking when a repository's family is undeclared ("asks rather than guesses"), and the reason, that neither misplacement is curable after deletion day |
| Rule 10: preserve executable state under `resources/scripts/` with a README before citing its result | Rule 10 | Kept word for word, as `tests/test_r5_contract.py` requires, with its scope and reason added from editing-and-archival.md's Executable Working State (W2, W5) |
| Rule 11: capture material context (facts, reasons, conditions, uncertainty, amendments) before dependent work, compaction or handoff; never turn a quoted command into authority | Rule 11 | Reworded (W2, W5): every clause kept; from material-context.md: when (as a source brings it), where (CONTEXT.md or a file it links), and the reason, from the file's opening |
| Rule 12: same Mac: the files are the handoff; another Mac: `synthesis handoff`; never a workspace-wide commit; never bypass hooks | Rule 12 | Reworded (W2, W5): the head as one action for both handoffs; both "never" clauses kept; from session-protocols.md: what `synthesis handoff` does, that day-end publishes the same way (with the Archival Protocol's step 8), and the reason against a workspace-wide commit |
| Rule 13: a doctor that cannot tell exits 2, never 0 | Rule 13 | Reworded (W5, W14): the head as an action keeping "exits 2, never 0" and "cannot tell"; the exit codes, what leaves the doctor unable to tell, how to read a 2, and the reason, from context-doctor.md's "Running it" |
| Rule 14: transcripts are the evidence beneath the records; what `synthesis sessions export` and `synthesis sessions sync` do; never paste the conversation into a record; what `synthesis resume` shows | Rule 14 | Reworded (W5): the head as an action, "Keep transcripts as the evidence beneath the records"; its other three sentences kept word for word; the reason for the third, from session-transcripts.md's "Reading and citing" |
| Rule 15: a session-log entry cites the record behind each decision or quote, how much of the id, how to open it, and the range for the principal's prompts | Rule 15 | Reworded (W5): the head as an action, "Cite in each session-log entry the record behind each decision or quote"; the rest kept word for word, as `tests/test_sessions.py` requires |
| Contents: "**Procedure** (below): session start, during work, close." | Contents: the procedure.md line | Reworded: the Procedure lives in references/procedure.md, read at session start and before closing |
| Contents: the session-transcripts.md line | Contents | Reworded: link text the file's name; "the archive, its commands, sync and citations" for its longer list, which the file's own contents names; "Read before reading, citing, exporting or syncing transcripts." kept word for word; placed after the doctor line, since the lines follow the order in which the rules first use the files |
| Contents: the tiers-and-templates.md line | Contents | Reworded: link text the file's name; the same parts in fewer words, "quality measures" left to the file's contents; "Read when creating or restructuring a record." kept word for word |
| Contents: the session-protocols.md line | Contents | Reworded: link text the file's name; "both protocols in full, compaction" for "the Session Start and Mid-Session Refresh protocols in full, compaction signals"; "Read at session start and on any trigger." kept word for word |
| Contents: the editing-and-archival.md line | Contents | Reworded: link text the file's name; "currency" and "stamps" for "header and body currency" and "item stamps"; "Read before restructuring or closing a record." kept word for word |
| Contents: the deletion-units.md line | Contents | Reworded: link text the file's name; "the two repo families, ALWAYS-PRESERVE, a workspace's conversations" for its longer wording; "Read before writing engagement-adjacent content or deleting a workspace's data." kept word for word |
| Contents: the material-context.md line | Contents | Reworded: link text the file's name; "item lists by exact id, handoff checks" for "replacing item lists by exact id, checking a handoff"; "Read before compaction, handoff or replacing a decision list." kept word for word |
| Contents: the context-doctor.md line | Contents | Reworded: link text the file's name; "its runs, checks, exit codes and lessons" for "running the doctor, its checks, exit codes and the lessons built into it"; "Read before running it or acting on a finding." kept word for word |
| Contents: the coverage-map.md line, "where every part of 1.22.0 lives now." | Contents: the records line | Merged with the preserved line: where each part of 2.8.2 and 1.22.0 lives now, read only to review a rewrite |
| Contents: the preserved line, "why the old machinery was cut, and the 1.22.0 text verbatim. Read only to review the cut." | Contents: the records line | Reworded: all four files linked as before; "both texts word for word"; "Read only to review a rewrite", since the files now hold two rewrites |
| Procedure: its heading and "Session start" | references/procedure.md | Moved word for word; rule 2 states it (below) |
| Procedure: "During work" | references/procedure.md | Moved word for word; rule 4 states part of it (below) |
| Procedure: "Check", the doctor's command and what it prints | references/procedure.md | Moved word for word; rule 13 states the exit contract, and context-doctor.md also gives the command and its output (format rule 7) |
| Procedure: "Close" | references/procedure.md | Moved word for word; rules 4, 6, 12, 13 and 15 state parts of it (below). With every binding rule complete on its own, SKILL.md would have run past the room W19 leaves under 8,000 bytes, and format rule 3 moves whole passages rather than condensing them |

### references/procedure.md

| 2.8.2 | 2.9.0 | How |
|---|---|---|
| (none) | Title and opening line: what the file holds, when to read it, that the binding rules govern ("rule 12" is binding rule 12), and where the protocols are in full | Added (format rules 4 and 11) |
| SKILL.md: Procedure | The same section, heading included | Moved word for word |

### references/preserved.md

| 2.8.2 | 2.9.0 | How |
|---|---|---|
| Title: "Preserved: what context lifecycle 2.0.0 does not carry, and why" | "Preserved: context lifecycle text replaced in 2.0.0 and in 2.9.0, and why" | Reworded: the file holds both rewrites |
| (none) | The paragraph before the 2.0.0 opening paragraph: two rewrites, newest first | Added |
| The opening paragraph, the three Contents lines and every section | The same | Kept word for word; Contents gains the 2.9.0 section's line first |
| (none) | Retired in 2.9.0: why each part of SKILL.md changed, then the 2.8.2 SKILL.md word for word | Added (format rule 5) |

### Where the binding rules state the moved procedure

| Moved passage, now in references/procedure.md | Stated in SKILL.md by |
|---|---|
| Session start: `synthesis resume <id>`, then the Session Start Protocol's steps in order | Rule 2; the exact `date`, `git log` and `git status` options stay in procedure.md and session-protocols.md |
| Session start: title the session after the project where the client allows it | Rule 2, word for word, as `test_session_start_names_the_session_after_the_project` requires |
| Session start: show the result in one line: today, last commit, whether CONTEXT.md matches | Rule 2, "Show the verification"; the line's three parts stay in procedure.md |
| During work: after each task, update CONTEXT.md under your claim | No rule, as in 2.8.2: procedure.md |
| During work: keep the current-state block current, since it is what returns after compaction | No rule, as in 2.8.2: procedure.md and tiers-and-templates.md, the current-state block |
| During work: archive when CONTEXT.md passes 120 lines | Rule 4 |
| Check: the doctor's command and what it prints | Rule 13, the exit contract; the command in procedure.md and context-doctor.md |
| Close: append the session entry, with Attribution lines when several agents contributed | Rule 15, the entry's citations; the Attribution lines in tiers-and-templates.md, Agent Attribution |
| Close: refresh the header and current-state block | Rule 6, the header |
| Close: archive cold content | Rule 4 |
| Close: run the doctor | Rule 13 |
| Close: hand off per rule 12 | Rule 12 |

### Files unchanged

`references/session-protocols.md`, `references/tiers-and-templates.md`, `references/editing-and-archival.md`,
`references/deletion-units.md`, `references/material-context.md`, `references/context-doctor.md`,
`references/session-transcripts.md`, `references/preserved-protocol.md`, `references/preserved-operations.md`,
`references/preserved-succession.md`, `scripts/context_doctor.py`, `tests/test_context_doctor.py` and
`agents/openai.yaml`. In this file, the 1.22.0 to 2.0.0 map below is kept word for word one heading level down.

## Coverage map: context lifecycle 1.22.0 to 2.0.0 (v5)

Ruling D8: every rule of the old text has a new home, or sits in a preserved
file with the reason. "Verbatim" means the old lines appear unchanged in the
named file. "Reworded" means kept in plain words for v5, with the original in
the preserved files. "Cut" means not carried; the reason is here and in
[preserved.md](preserved.md#what-was-cut-and-why).

### Contents

- [Coverage check results](#coverage-check-results)
- [Frontmatter before v5 (verbatim)](#frontmatter-before-v5-verbatim)
- [1.22.0 SKILL.md](#1220-skillmd)
- [1.22.0 reference files](#1220-reference-files)
- [Scripts](#scripts)
- [R1.5 scenarios and their tests](#r15-scenarios-and-their-tests)

### Coverage check results

Run on 2026-10-05 from the v5 worktree:

```text
$ python3 v5-skill-coverage-check.py <v5 worktree> synthesis-context-lifecycle
synthesis-context-lifecycle: 1560 old lines, 0 not found verbatim
```

### Frontmatter before v5 (verbatim)

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

### 1.22.0 SKILL.md

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

### 1.22.0 reference files

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

### Scripts

| Script | Verdict | v5 home | Tests |
|---|---|---|---|
| context_doctor.py | SLIM | `scripts/context_doctor.py` (rewritten, about 590 lines) | tests/test_context_doctor.py |
| context_currency.py | SLIM | merged into the doctor (per-field ordinals, body markers, item stamps) | tests/test_context_doctor.py |
| context_edit.py | REPLACE | harness Edit and apply_patch; `header-lag` in the doctor; memory sweep in day-end | tests/test_context_doctor.py (`phase_moved_but_last_session_did_not`) |
| record_transaction.py | CUT | — | — |
| record_succession.py | SLIM (outside this skill) | the decision-packet generator | handled by its owner |
| review_ledger.py | REPLACE | the lapse register (workspace instructions, day-end and weekly review) | — |

### R1.5 scenarios and their tests

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
| Unreadable or non-git source exits non-zero, never clean; missing index is a defect; an index.yaml the plugin's YAML reader (`synthesis/yamlish.py`, since 2026-10-05) refuses is unreadable | `unreadable_or_non_git_sources_cannot_be_called_healthy`, `an_index_the_yaml_reader_refuses_cannot_be_called_healthy`, `nothing_to_audit_is_not_a_clean_result`, `projects_without_an_index_and_index_entries_without_a_folder_are_defects`, `discovered_roots_without_projects_are_skipped_but_a_named_one_cannot_be_audited` |
| Gitignored or uncommitted CONTEXT.md is reported | `a_gitignored_context_is_a_defect_and_an_uncommitted_one_a_warning`, `durability_no_remote_is_a_defect_and_unpushed_a_warning` |
| Output leads with the active project and counts the rest; a new convention starts as a warning | `output_leads_with_the_active_project_and_counts_the_rest`, `item_stamps`, `a_single_project_run_shows_its_full_list` |
| Section marker staleness | `a_stale_section_marker_fails` |
| Session titled after the project (2026-09-21, from the old `test_session_start_protocol.py`) | `session_start_names_the_session_after_the_project` |
