# Coverage map: project management 2.21.6 to 3.0.0 (v5)

Ruling D8: every rule of the old text has a new home, or sits in a preserved
file with the reason. "Verbatim" means the old lines appear unchanged in the
named file. "Reworded" means the rule is kept in plain words for v5 commands,
with the original in the preserved files. "Cut" means not carried; the reason
is here and in [preserved.md](preserved.md).

## Contents

- [Coverage check results](#coverage-check-results)
- [Frontmatter before v5 (verbatim)](#frontmatter-before-v5-verbatim)
- [2.21.6 SKILL.md](#2216-skillmd)
- [2.21.6 reference files](#2216-reference-files)
- [Scripts](#scripts)
- [Edge cases from the code evaluation](#edge-cases-from-the-code-evaluation)

## Coverage check results

Run on 2026-10-05 from the v5 worktree:

```text
$ python3 v5-skill-coverage-check.py <v5 worktree> synthesis-project-management
synthesis-project-management: 2021 old lines, 0 not found verbatim
```

Every 2.21.6 line is in a v5 file: the carried rules in the new references,
and the whole 2.21.6 text in the three preserved files.

## Frontmatter before v5 (verbatim)

```yaml
---
name: synthesis-project-management
description: "Lightweight project management system designed for human-agent collaboration, optimized for context preservation and cross-agent coordination across sessions. Use when asked to: project management, project setup, project tracking, synthesis project, manage project, set up project, project structure, session protocol, parallel root sessions, advisory locks, cross-agent coordination."
license: "CC0-1.0"
depends_on: ["synthesis-context-lifecycle"]
metadata:
  author: "Rajiv Pant"
  version: "2.21.6"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

`name`, `license`, `depends_on`, `author`, `source_repo` and `source_type` are
kept; the version is 3.0.0; `format: v5` is added; the description is
rewritten to 300 characters with the old triggers (project setup, tracking,
session protocol, parallel root sessions, cross-agent coordination).

## 2.21.6 SKILL.md

| 2.21.6 section or rule | v5 home | How |
|---|---|---|
| Title and purpose paragraph | SKILL.md purpose paragraph | Reworded |
| Team contract and managed workflow pointer | — | Cut: team governance (`team_contract.py`, `team_records.py`, `contribution_evidence.py`) was never enrolled; R7.4 asks for one-page colleague onboarding, owned by synthesis-onboarding |
| Configuration table | [records-and-conventions.md](records-and-conventions.md#configuration) | Verbatim table, plus how the CLI finds knowledge roots |
| Design Principles 1 to 5 | [records-and-conventions.md](records-and-conventions.md#design-principles) | Verbatim |
| Design Principles 6 (coordinate before concurrent writes), 7 (one context owner) | records-and-conventions.md; Binding rules 2 and 3 | Reworded to the `synthesis` board |
| Problem This Solves | [records-and-conventions.md](records-and-conventions.md#problem-this-solves) | Verbatim (Cursor became Muse, the supported harness) |
| System Architecture tree | [records-and-conventions.md](records-and-conventions.md#system-architecture) | Verbatim, plus PRIME-DIRECTIVE.md and the one-place rule (R1.6, Binding rule 1) |
| Key Structural Decisions table | records-and-conventions.md | Verbatim except "on-disk format versions (v1/v2) and the migration contract", cut (one format) |
| Project Naming | Binding rules list it under records; [records-and-conventions.md](records-and-conventions.md#project-naming--the-full-rationale) | Verbatim rationale; `ongoing` became `bounded: false` per the 2026-08-28 status vocabulary |
| "For explicit selected-project upgrades, follow the migration owner" | — | Cut: no format migration in v5 |
| Components 1, Project Index; multi-status example; "derive session currency" and parent-plan resolver | [records-and-conventions.md](records-and-conventions.md#indexyaml--full-example); `synthesis resume` (`project.plan`) | Index reworded to the four-status vocabulary; structured-state currency cut (no `CURRENT_STATE.json`); plan resolution is the single `Plan:` field |
| Components 2, Tiered Context; archival protocol | [records-and-conventions.md](records-and-conventions.md#tiered-context); synthesis-context-lifecycle | Verbatim table and archival rule; "autopilot receipts bind ... execution basis" cut (R6.1 plan file) |
| Components 3, Lessons | [records-and-conventions.md](records-and-conventions.md#lesson-file-formats) | Verbatim |
| Components 4, Agent Attribution | [records-and-conventions.md](records-and-conventions.md#agent-attribution--full-rules) | Verbatim |
| During Work | [discovery-and-handoff.md](discovery-and-handoff.md#during-work) | Verbatim loop; "local receipt" and material-context protocol pointer reworded |
| Session Start steps 1 to 6 | [discovery-and-handoff.md](discovery-and-handoff.md#session-start); Procedure 1 to 4 | Reworded: `synthesis who`, `synthesis resume`; resolver flags, transaction journals and `CURRENT_STATE.json` cut |
| Session End steps 1 to 6 | [discovery-and-handoff.md](discovery-and-handoff.md#session-end); Procedure 9 to 11 | Steps 1 to 3 verbatim; 4 and 5 (structured state, format refresh, Stop receipts) cut; 6 reworded (only the holder releases) |
| Refresh-and-report paragraph, NOT_APPLICABLE paragraphs, closure recovery pointer | synthesis-checkpoint; [preserved.md](preserved.md#the-2216-skillmd) | Cut: receipts, manifests and Stop applicability are gone |
| Cross-Agent Session Coordination: board, schema v4 rows, `coordination.py` commands | [coordination.md](coordination.md); Procedure | Replaced by `synthesis claim`, `release`, `who`, `msg`, `inbox` |
| Coordination rules 1 (read at start and checkpoints), 2 (claim before write), 3 (no writing through overlap) | Binding rule 2; [coordination.md](coordination.md#claim-scope-over-the-task-lifecycle) | Verbatim scope text; `create_worktree.py` and `--then` replaced by `synthesis worktree create` |
| Rule 4, share checkouts only with disjoint areas | [coordination.md](coordination.md#shared-repositories-and-worktrees) | Verbatim |
| Rule 5, one context owner | Binding rule 3; [coordination.md](coordination.md#the-same-project-one-context-owner) | Verbatim, now a prose rule (the board does not enforce it) |
| Rule 6, autonomous claim keeps priority; idle-holder exception | Binding rule 5; [coordination.md](coordination.md#priority-stale-claims-and-takeover) | Priority verbatim; the request-narrow escalation cut (no narrowing verbs) |
| Rule 7, sends need a receipt; addresses resolved, never guessed | Binding rule 7; [coordination.md](coordination.md#addressing-a-peer-session) | Reworded: the board resolves or refuses; receipts and lanes cut |
| Rule 8, heartbeat, narrow, release; stale is advisory | Binding rule 6; coordination.md | Reworded: activity refreshes the session; stale after 8 hours; `--take` |
| Rule 9, advisory does not mean optional | [coordination.md](coordination.md#claim-scope-over-the-task-lifecycle) | Verbatim |
| Inbox identity paragraph; OS lock, backups, lease, retirement pointers | — | Cut: lease and per-board locking machinery; the board's own claim lock is in `synthesis/board.py` |
| Cross-Agent Handoff steps 1 to 5 | [discovery-and-handoff.md](discovery-and-handoff.md#cross-agent-handoff) | Verbatim |
| Steps 6 to 9 (LOCAL_READY, conformance activate, mac-sync remote handoff, pointer archive) | discovery-and-handoff.md steps 6 to 8 | Replaced: same Mac needs nothing (R1.3); another Mac runs `synthesis handoff` (R1.4) |
| Merge or fast-forward request names the target head | [coordination.md](coordination.md#pauses-crashes-and-merge-requests) | Verbatim |
| Resuming from another agent; `project_state.py resolve` | discovery-and-handoff.md; `synthesis resume` | Reworded |
| The Handoff Queue (`handoff.py`) | [discovery-and-handoff.md](discovery-and-handoff.md#work-handed-between-agents) | Replaced by a brief file plus `synthesis msg`; the two supervision rules kept |
| Parallel Sub-Agent Dispatch | [discovery-and-handoff.md](discovery-and-handoff.md#parallel-sub-agent-dispatch); Binding rule 8 | Verbatim |
| Dispatching to Codex | Binding rule 12; [codex-dispatch.md](codex-dispatch.md) | Verbatim reasons |
| File Requirements by Project Status | [discovery-and-handoff.md](discovery-and-handoff.md#file-requirements-by-project-status) | Verbatim except the `ongoing` row, now `bounded: false` |
| Project Discovery steps 1 to 7 | [discovery-and-handoff.md](discovery-and-handoff.md#project-discovery); Binding rules 9 and 10 | Verbatim; step 4's resolver became `synthesis resume` |
| Common Mistakes | [discovery-and-handoff.md](discovery-and-handoff.md#common-mistakes) | Verbatim; the board row reworded; the outcome-review row reworded without receipts |

## 2.21.6 reference files

| File | v5 home | How |
|---|---|---|
| parallel-agent-protocol.md: Quickstart | [coordination.md](coordination.md#quickstart) | Reworded to v5 commands |
| ...: Claim scope over the task lifecycle | coordination.md | Verbatim except `claim_scope.py`, worktree-alias metadata conflicts and `narrow`/`--replace` (cut: per-session files and plain path claims) |
| ...: Addressing a peer session | [coordination.md](coordination.md#addressing-a-peer-session) | The incident and annotation rules verbatim; lanes, receipts, seats and the shell-parsing gate cut (R8.1, 88 ms) |
| ...: Release trains | [coordination.md](coordination.md#release-trains) | Rationale verbatim; mechanism reworded to a board claim the release skill names |
| ...: Digests | [coordination.md](coordination.md#digests-what-survives-a-crash) | Verbatim |
| ...: Different projects; The same project; contribution artifact | coordination.md | Verbatim |
| ...: Advisory claims and shared checkouts; claim succession; idle-holder escalation | [coordination.md](coordination.md#priority-stale-claims-and-takeover) | Reworded: stale after 8 hours, `--take` with a notice; succession and administrative narrowing cut |
| ...: Shared repositories | [coordination.md](coordination.md#shared-repositories-and-worktrees) | Verbatim |
| ...: Absent checkout creation; claim-dependent effects; bounded passive resnapshot | coordination.md ("How claims behave") | Replaced by `synthesis worktree create`; a refused claim stops dependent effects (verbatim rule) |
| ...: Pauses, crashes, and stale sessions; administrative release | [coordination.md](coordination.md#pauses-crashes-and-merge-requests) | Reworded; administrative release cut (the principal decides) |
| ...: Commit authority (check-staged selector) | `synthesis/commit_check.py` | Replaced: the commit check reads the harness session id, never a pointer |
| ...: Resuming and the active-project pointer | [discovery-and-handoff.md](discovery-and-handoff.md#cross-agent-handoff) | Working-tree-truth paragraph verbatim; the pointer cut (no global pointer) |
| ...: Cross-machine boundary; lease bootstrap and retirement | [coordination.md](coordination.md#across-macs) | Cut: the lease; claims are per Mac, git carries records |
| ...: Worktree retirement | coordination.md; `synthesis worktree retire` | Replaced: the safety rules kept in `synthesis/worktree.py` |
| ...: Handoff queue mechanics | discovery-and-handoff.md | Replaced (see the queue row above) |
| ...: Durable work placement and unexplained loss; nested retirement | [coordination.md](coordination.md#durable-work-placement) | Verbatim placement rules; `fleet_doctor` and intent recovery cut |
| active-sessions-template.md | coordination.md | Replaced: no shared board file; its protocol lines are in coordination.md |
| session-identity.md | coordination.md ("Quickstart") | Replaced: the harness session id plus a six-letter short name; UUIDv7, Crockford and speakable aliases cut; the version-skew rule kept ([coordination.md](coordination.md#newer-state-and-version-skew)) |
| session-words-v1.LICENSE.md, session-words-v1.txt.zlib.b85 | — | Cut with the speakable aliases they served; the license text is in preserved-coordination.md |
| project-durable-delivery.md | [coordination.md](coordination.md#addressing-a-peer-session) | Replaced by `synthesis msg project:<id> --durable` |
| records-and-conventions.md | [records-and-conventions.md](records-and-conventions.md) | Verbatim except the native-memory paragraph (the sweep is a day-end ritual step) and `ongoing` |
| codex-dispatch.md | [codex-dispatch.md](codex-dispatch.md) | Verbatim, plus output and discovery order |
| project-state-recovery.md | `synthesis resume` warnings | Replaced: newer copy, upstream and conflict warnings from local git; `CURRENT_STATE.json`, receipts and checkpoint applicability cut |
| project-formats.md, project-migration.md | — | Cut: one format |
| checkpoint-closure-recovery.md | — | Cut: manifests, Stop receipts and stranded-path flushing are gone; `synthesis handoff` commits only claimed paths |
| execution-basis.md | synthesis-autopilot | Replaced by the plan file (R6.1) |
| autopilot-project-quality.md | [discovery-and-handoff.md](discovery-and-handoff.md#common-mistakes) (last row) | Reworded: obligations, owners, next actions and handoff usability are checked separately |
| canonical-landing.md | `synthesis worktree land` | Replaced (R1.3) |
| team-contract.md, team-managed-workflows.md | — | Cut (see the SKILL.md row) |
| acceptance-suite.yaml (not markdown) | — | Cut: it enumerated `check-staged` fixtures; the v5 commit check has its own tests |

## Scripts

Verdicts from the v5 code evaluation (project state, sections 1 and 2). Test
files beside the scripts were removed with them; their cases live on as the v5
tests named here.

| Script | Verdict | v5 home | Tests |
|---|---|---|---|
| coordination.py | SLIM | `synthesis/board.py`, `synthesis/cli.py` | tests/test_board.py, tests/test_peers.py |
| board_grammar.py | REPLACE | per-session JSON files; version-skew rule in coordination.md | tests/test_board.py |
| board_inbox.py | SLIM | `hook.user_prompt_submit`, `board.inbox` | tests/test_peers.py (`the_recipient_sees_a_message_once_at_its_next_prompt`) |
| claim_scope.py | SLIM | `board.overlaps` | tests/test_board.py |
| coordination_schema.py | SLIM | `board.short_name`; version-skew prose | tests/test_peers.py (`short_name`) |
| coordination_lock.py | SLIM | `board._claim_lock` | tests/test_board.py |
| coordination_archive.py | REPLACE | message files | tests/test_peers.py |
| coordination_process.py | CUT | — | — |
| pointer_lock.py | REPLACE | per-session state | tests/test_continuity.py (`compaction_brings_back_this_sessions_own_project`) |
| native_identity.py | REPLACE | `paths.session_id` | tests/test_continuity.py |
| native_git.py | CUT | — | — |
| peer_addressing.py | SLIM | `board.resolve`, `board.message` | tests/test_peers.py |
| peer_send_gate.py | SLIM | `board.resolve` (no shell parser) | tests/test_peers.py |
| project_recipient.py | CUT | — | — |
| fleet_bootstrap.py | SLIM | synthesis-onboarding (new-Mac setup) | owned by that helper |
| fleet_doctor.py | REPLACE | `synthesis doctor` | tests/test_doctor.py |
| fleet_handoff.py | SLIM | `project.handoff` (source checks), `project.resume` (destination checks) | tests/test_handoff.py, tests/test_resume.py |
| fleet_identity.py, fleet_logical.py, fleet_subscriptions.py | CUT | — | — |
| fleet_paths.py | SLIM | synthesis-onboarding doctor path checks | owned by that helper |
| create_worktree.py | REPLACE | `synthesis worktree create` | tests/test_worktree.py |
| retire_worktree.py | SLIM | `synthesis worktree retire` | tests/test_worktree.py |
| retirement_runtime.py | CUT | — | — |
| canonical_landing.py | SLIM | `synthesis worktree land` | tests/test_worktree.py (`land_*`) |
| prune_tool_snapshots.py | CUT | — | — |
| project_state.py | SLIM | `project.resume` newer-copy and upstream warnings | tests/test_resume.py |
| plan_reference.py | SLIM | `project.plan` (one `Plan:` field) | tests/test_resume.py (`the_plan_comes_from_one_field`, `two_plan_declarations_are_ambiguous`) |
| execution_checkpoint.py, run_admission.py | REPLACE | synthesis-autopilot plan file (R6.1); claims and the commit check (R2.1) | tests/test_autopilot.py, tests/test_commit_check.py |
| project_format.py, project_migration.py | CUT | — | — |
| codex_dispatch.py | KEEP | `scripts/codex_dispatch.py` (its binary discovery inlined from the conformance skill so it stands alone) | tests/test_codex_dispatch.py |
| handoff.py | REPLACE | `synthesis msg` with a brief file | tests/test_peers.py |
| team_contract.py, team_records.py, contribution_evidence.py | CUT | — | — |
| publication_command.py | SLIM, then REPLACE | `synthesis/guards.py` shell classification | tests/test_guards.py, tests/test_deploy_rules.py; uncovered cases listed in the M3 report |

## Edge cases from the code evaluation

Section 3 of the evaluation, R1 and R2. R1 cases are this skill's and
synthesis-project-resume's; R2 cases belong to the board in `synthesis/`.

| Scenario | Held by |
|---|---|
| R1.1 session on project Y asked to resume X names both and asks | tests/test_resume.py `a_session_working_another_project_is_asked_before_switching` |
| R1.1 resuming the held project confirms in one line | `resuming_the_project_this_session_already_holds_confirms_in_one_line` |
| R1.1 unknown id offers to start; no near match | `an_unknown_id_offers_to_start_a_project_and_never_picks_a_near_match` |
| R1.1 canonical behind its upstream lists the changes since | `a_checkout_behind_its_fetched_upstream_lists_the_changes_since` |
| R1.1 unreachable remote said once; resume continues | `an_unreachable_remote_or_no_upstream_is_said_once_and_resume_continues` |
| R1.1 newer copy on an unmerged worktree branch, named | `a_newer_copy_on_an_unmerged_worktree_branch_is_named_with_where` |
| R1.1 two diverged copies: conflict, not picked by time | `two_diverged_copies_are_reported_as_a_conflict_and_neither_is_picked`, `uncommitted_edits_in_two_working_copies_are_a_conflict` |
| R1.1 future date in a session body or generated index does not move the newest session | `the_newest_session_ignores_dates_in_entry_bodies_and_the_generated_index` |
| R1.2 `Plan: none`, historical links, two declarations | `the_plan_comes_from_one_field_and_none_means_none`, `two_plan_declarations_are_ambiguous_and_neither_is_chosen`, `the_reinjected_brief_names_the_plan_or_says_there_is_none` |
| R1.2 re-injection from this session's own state, never a pointer | tests/test_continuity.py `compaction_brings_back_this_sessions_own_project_never_another_sessions` |
| R1.3 push to main lands the canonical checkout only when clean and not diverged | tests/test_worktree.py `land_*` |
| R1.3 worktree under a temporary directory warns | `synthesis/worktree.py` create warning; doctor path checks are synthesis-onboarding's |
| R1.4 dirty, unpushed or upstream-less records refuse and never say ready | tests/test_handoff.py `a_branch_without_an_upstream_is_refused_and_listed`, `a_diverged_branch_is_neither_pushed_nor_forced`, `a_refusing_hook_is_read_from_git_not_from_a_missing_error_line` |
| R1.4 another session's files stay out of the commit | `only_changes_inside_this_sessions_claims_are_committed_and_pushed` |
| R1.4 destination with uncommitted changes refuses to pull over them | tests/test_resume.py `local_uncommitted_changes_are_listed_and_never_pulled_over` |
| R1.4 a refusing hook is read from git log and status | `a_refusing_hook_is_read_from_git_not_from_a_missing_error_line` |
| R1.4 index locks left alone; detached HEAD refused | `an_index_lock_is_left_alone_and_nothing_is_committed`, `a_detached_head_is_refused` |
| R1.5 | synthesis-context-lifecycle tests/test_context_doctor.py |
| R2.1 overlapping claims refused with name and goal; containment; distinct subtrees | tests/test_board.py |
| R2.1 claims on paths that do not exist yet | tests/test_worktree.py `create_claims_the_path_for_this_session_then_adds_the_worktree` |
| R2.1 one context owner; index.yaml writers; autonomous priority | Prose rules: Binding rules 3 to 5 and coordination.md (the board does not enforce them) |
| R2.3 delivery once at the next prompt; durable; ambiguity refused; display names refused; broadcast refused; sender id | tests/test_peers.py |
| R2.4 stale shows and is taken over only on request, holder told | tests/test_board.py `stale_claim_is_taken_over_only_on_request_and_the_holder_is_told` |
| R2.1 spellings through `~` and symlinks; `a/*` versus `a/**`; staged renames; copied session ids; re-claim merge; claim usage errors. R2.2 missing board. R2.4 concurrent takeover, takeover overlapping a third live session, undated session. R2.5 newer schema | Not covered by a v5 test yet; listed in the M3 report for the board's owner |
