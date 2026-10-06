# Coverage map: synthesis-daily-rituals 2.45.1 to 3.0.0 (v5)

Ruling D8: every rule of the old text has a new home, or sits in a preserved file with the
reason. "Verbatim" means the old lines appear unchanged in the named file; "reworded" means the
rule is kept in plain words there with v5 commands, and the original wording is in
[preserved-skill-v2-part1.md](preserved-skill-v2-part1.md) or
[preserved-skill-v2-part2.md](preserved-skill-v2-part2.md); "retired" means not carried, with the
reason in [preserved.md](preserved.md).

Contents: Coverage check results · Frontmatter before v5 (verbatim) · SKILL.md sections ·
Reference files · Scripts by verdict · Tests · Edge cases and the test that holds each.

## Coverage check results

Run on 2026-10-05 from the v5 worktree against `origin/main`:

```text
$ python3 v5-skill-coverage-check.py <v5 worktree> synthesis-daily-rituals
synthesis-daily-rituals: 2095 old lines, 16 not found verbatim
```

The 16 lines are the anonymized ones: five example lines in `draft-grounding.md`, six in
`mailbox-manifest.md` and five in `version-history.md` named private people, a client project
and personal addresses. Each is kept with a neutral placeholder in the same file and the same
place ([preserved.md](preserved.md#anonymized-lines)). Every other old line is in a v5 file.

## Frontmatter before v5 (verbatim)

```yaml
---
name: synthesis-daily-rituals
description: "Day-start and day-end checklists for synthesis engineering projects. Execute dependency-ordered rituals for context optimization, channel sync across Slack, Google Chat, email, meeting transcripts, and document comments, catch-up reads, PR reviews, day planning, and communications. Use when asked about: daily ritual, morning routine, day start, day end, daily checklist, morning checklist, end of day checklist, daily workflow."
license: "Apache-2.0"
depends_on:
  - synthesis-context-lifecycle
  - synthesis-project-management
  - synthesis-slack-sync
  - synthesis-repo-guard
  - synthesis-checkpoint
metadata:
  author: "Rajiv Pant"
  version: "2.45.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

v5 changes: the description is cut to the 300-character limit with the strongest triggers kept
(day start, day end, morning routine, end of day, daily ritual, weekly review) and two added
(quick close, sync channels); `synthesis-repo-guard` leaves `depends_on` because day-end now
publishes with `synthesis handoff`; version 3.0.0; `format: v5`.

## SKILL.md sections

| 2.45.1 section | v5 home | How |
|---|---|---|
| Title and opening paragraph (global checklists, project supplements) | SKILL.md purpose paragraph | Reworded |
| Pointers to version history, worker contract, watermarks, plan format, draft grounding; `<…-root>` placeholders under the stable plugin path | SKILL.md Contents; the `<rituals>` placeholder | Reworded; the stable-path rule retired with the old release layout ([preserved.md](preserved.md)) |
| Mandatory ritual evidence route; mechanical owner map; declared acquisition entries | Retired | Machinery CUT ([preserved.md](preserved.md), [preserved-retired-references.md](preserved-retired-references.md)) |
| Configuration table; project supplement paragraph | Paths stated in [day-start.md](day-start.md) and [day-end.md](day-end.md); supplement in the purpose paragraph and Step 3b | Reworded |
| Day-end installer paragraph | [scripts.md](scripts.md) and SKILL.md closing line; `synthesis install` | Reworded (install REPLACED) |
| Script invocation (`synthesis exec-public`) | [scripts.md](scripts.md) | Retired: launcher cut |
| Distributed ritual execution — desk and workers (all eight bullets) | [ritual-worker-contract.md](ritual-worker-contract.md) (Terms, Desk obligations, Plan storage separation carry each rule verbatim); Binding rule 8; `ritual_workers.py coverage` | Verbatim in the contract |
| Day-Start Step 1: date, per-project verification, checkpoint | [day-start.md](day-start.md) Step 1 | Verbatim |
| Step 1: git-hooks, message-guard, email monitoring, parity doctors | [day-start.md](day-start.md) Step 1 "Protection health" (`synthesis doctor`) | Reworded; rationale verbatim |
| Step 1: context-integrity check | [day-start.md](day-start.md) Step 1 (`context_doctor.py --root`, exit 0/1/2) | Reworded; rationale verbatim |
| Step 1: portfolio review | [day-start.md](day-start.md) Step 1 | Verbatim, command updated |
| Step 1: coordination archive, orphan snapshot maintenance | Retired | Board and snapshot store gone |
| Step 1: coordination-claim review | [day-start.md](day-start.md) Step 1 "Stale-claim review" | Rationale verbatim; `synthesis who --all`, `msg`, `claim --take` |
| Step 1: ritual state read; weekly-review-owed check | [day-start.md](day-start.md) Step 1; [weekly-and-longer.md](weekly-and-longer.md) | Verbatim rationale; the Friday-it-satisfies rule added from the 2026-08-27 lesson |
| Step 1 closing (L1/L2/L3) | [day-start.md](day-start.md) Step 1 | Verbatim |
| Step 2 Context Optimization | [day-start.md](day-start.md) Step 2 | Verbatim |
| Step 3 Sync intro; 3a Source-Code Sync (all bullets, four states, remote layout paragraph) | [day-start.md](day-start.md) 3a | Verbatim rules; `repo_state.py` states extend the four (DIRTY, BEHIND, EXCLUDED added) |
| 3b Channel Sync (Slack, Google Chat, email, document comments, name surfaces not swept, watermark gate, project steps) | [day-start.md](day-start.md) 3b; [sync-watermarks.md](sync-watermarks.md) | Verbatim with v5 commands; connector reads advance (2026-10-01) |
| 3c Meeting Transcripts (acquisition bullet; automated and manual paths) | [day-start.md](day-start.md) 3c | Paths verbatim; acquisition bullet retired |
| 3d Inbox Hygiene | [day-start.md](day-start.md) 3d | Verbatim |
| 4 Catch-Up Read (cross-check, ownership routing, time-block layer) | [day-start.md](day-start.md) Step 4 | Verbatim; the publish-and-overlap bullet becomes "read every owned calendar; an unread window is not free" (overlap service retired) |
| 5 PR Review Queue | [day-start.md](day-start.md) Step 5 | Verbatim plus `pr_queue_scan.py` |
| 6 Day Plan (every bullet) | [day-start.md](day-start.md) Step 6 | Verbatim |
| 7 Morning Messages | [day-start.md](day-start.md) Step 7; Binding rule 7 | Verbatim; approval line added (R3.1) |
| (new) Record the day-start | [day-start.md](day-start.md) Step 8 | The old Step 7 said day-start records too; v5 makes it a step |
| Draft Message Rules (the digest) | [draft-grounding.md](draft-grounding.md) (full protocol); Binding rule 7 | Digest verbatim in the preserved part 2; the full rules verbatim in draft-grounding |
| Daily Plan Structure (digest and revert protection) | [plan-format.md](plan-format.md) | Verbatim there |
| Mid-Day Sync Protocol | [mid-day-and-modes.md](mid-day-and-modes.md) | Verbatim; "Record after every sync" reworded for R1.3 |
| Vacation / Observer Mode Ritual | [mid-day-and-modes.md](mid-day-and-modes.md) | Verbatim except persistence lines (R1.3) and the private path generalized |
| Concurrent-Seats Mode Ritual (six rules, keeps) | [mid-day-and-modes.md](mid-day-and-modes.md); Binding rule 10 | Verbatim; rules 2, 3, 6 name v5 commands |
| Day-End modes (table, Quick Close moments, weekly attachment) | [day-end.md](day-end.md) | Verbatim |
| Day-End 1 Transcript Sync | [day-end.md](day-end.md) Step 1 | Verbatim with v5 commands |
| Day-End 2 Source-Code Sync | [day-end.md](day-end.md) Step 2 | Verbatim; manifest bullet reworded to claims |
| Day-End 3 Integration Sweep | [day-end.md](day-end.md) Step 3 | Verbatim; deploy approval noted (R3.2) |
| Day-End 4, 4a Calendar Guardian, the decay sweep, outcomes | [day-end.md](day-end.md) Step 4a, 4b | Verbatim; lapse marking and register added (workspace instructions, 2026-10-01 and 2026-10-05) |
| Day-End 5 Lessons Learned | [day-end.md](day-end.md) Step 5 | Verbatim |
| Day-End 5a Native memory sweep | [day-end.md](day-end.md) Step 5a | Rewritten for v5; old text in [preserved.md](preserved.md) |
| (new) Provenance scan | [day-end.md](day-end.md) Step 5b | From guards-rituals edge case 68 and the quote-provenance check's SLIM verdict |
| Day-End 6 Career Amplification | [day-end.md](day-end.md) Step 6 | Verbatim |
| Day-End 7 Context Capture (date discipline, stamped open items, MEMORY.md, index, local gate, record) | [day-end.md](day-end.md) Step 7 | Verbatim; the gate uses `context_doctor.py --project` |
| Day-End 8 Skills Maintenance | [day-end.md](day-end.md) Step 8 | Reworded (`synthesis doctor` reports drift; Muse added) |
| Day-End 9 Machine Sync | [day-end.md](day-end.md) Step 9 | Reworded to the v5 leave procedure |
| Day-End 10 Weekly Loose-Ends Review (gating, scope, sources, classes, output, failure mode) | [weekly-and-longer.md](weekly-and-longer.md) | Verbatim; gating states the Friday-it-satisfies rule; lapse register source added |
| Day-End 11 Remote Readiness | [day-end.md](day-end.md) Step 11 | Reworded to `synthesis handoff`, the records doctor and `repo_state.py --discover`; closing paragraph verbatim |
| Ritual Persistence Protocol (local, remote, hygiene, completion) | [day-end.md](day-end.md) "Publishing at day-end" | Hygiene paragraph verbatim; modes reworded (R1.3, R1.4); handoff edge cases 5 to 12 stated |
| Autonomous Work and Audio Alerts | [mid-day-and-modes.md](mid-day-and-modes.md); Binding rule 9 | Verbatim |
| (new) Quarterly, six-month and annual reviews | [weekly-and-longer.md](weekly-and-longer.md) | From the workspace instructions (2026-10-05) |

## Reference files

| 2.45.1 file | v5 home | How |
|---|---|---|
| `version-history.md` (66,799 bytes, over one read) | [version-history.md](version-history.md) (intro and index, new 3.0.0 entry), [version-history-2.27-to-2.45.md](version-history-2.27-to-2.45.md), [version-history-2.3-to-2.26.md](version-history-2.3-to-2.26.md) | Split by section, verbatim except five anonymized lines |
| `plan-format.md` | Same file | Verbatim |
| `draft-grounding.md` | Same file | Verbatim plus a contents line; five example lines anonymized |
| `decay-sweep.md` | Same file | Verbatim except the command line (now `python3`) |
| `mailbox-manifest.md` | Same file | Verbatim; the example manifest and incident sentence anonymized |
| `ownership-routing.md` | Same file | Verbatim routing and movable-side rules; the shared time-block layer, seat publish procedure, overlap call and layer coverage retired with the chief-of-staff skill's removal of `overlap.py` ([preserved.md](preserved.md#retired-from-ownership-routingmd)) |
| `sync-watermarks.md` | Same file | Verbatim except the verbs block, the store path, schema-1 reading (retired) and the slack-sync step numbers; connector rule added |
| `ritual-worker-contract.md` | Same file | Verbatim except the fleet-doctor sentence; Executable evidence contract and Native memory sweep retired to [preserved.md](preserved.md); "Recording a worker run" added |
| `ritual-evidence.md`, `acquisition-evidence.md`, `acquisition-entry.md`, `mechanical-extraction.md` | [preserved-retired-references.md](preserved-retired-references.md) | Verbatim; retired (CUT machinery) |

## Scripts by verdict

Verdicts from `guards-rituals.md` (synthesis-daily-rituals rows).

| Script (lines before) | Verdict | v5 (lines after) | Notes |
|---|---|---|---|
| `ritual_state.py` (1,213) | SLIM | `ritual_state.py` (197) plus `synthesis/rituals.py` (151, shared with the hook and the nudge) | Log, two clocks, per-workspace views, empty-workspace refusal; migration, doctor, baseline, credential-paths, worker-readiness and the inline suite cut |
| `ritual_workers.py` (673) | SLIM | 108 | Registry and the coverage line; artifact custody and memory hashing cut |
| `sync_watermark.py` (705) | SLIM | 345 | All the R5.2 rules; schema-1 migration and acquisition evidence cut. Longer than the 250 target because the CLI keeps its full help and status printout |
| `repo_state.py` (450) | SLIM | 143 | Fetch and count without `coordination_process.py`; adds `--discover` (the strand scan for day-end and leaving a Mac, replacing the scan half of `repo_sync_check.py`) and `--ff` (refuses a dirty tree, compare-and-swap for other branches) |
| `decay_sweep.py` (288) | KEEP | 288 | Unchanged |
| `portfolio_review.py` (275) | KEEP | 264 | Dropped the `team_contract` import (team contracts CUT); PyYAML replaced by `simple_yaml.py`; console config path no longer reads `SYNTHESIS_HOME` |
| `pr_queue_scan.py` (402) | KEEP | 399 | PyYAML replaced: without it the scan skipped itself with exit 0, an unscanned queue reading as empty |
| `mailboxes.py` (251) | KEEP | 249 | PyYAML replaced |
| `gchat_preflight.py` (248) | KEEP | 247 | PyYAML replaced |
| `day-end`, `day-end-nudge.sh` (183) | KEEP | 161 | The nudge asks `current/synthesis/rituals.py --owed-today` instead of embedding a query of its own; bash kept |
| `com.synthesis.day-end-nudge.plist` | KEEP | unchanged | Template `synthesis install` loads |
| (new) `simple_yaml.py` | — | 256 | Standard-library reader for the manifests; agrees with PyYAML on all 43 manifests on the author's Mac |
| `acquisition_evidence.py`, `acquisition_transport.py`, `archive_publish.py` (929) | CUT | deleted | Caused the 2026-10-01 regression |
| `credential_paths.py` (344) | REPLACE | deleted | The commit check's filename rule (scenario 50, guards helper) |
| `install_day_end.py` (160) | REPLACE | deleted | `synthesis install` (wiring handed to the coordinator) |

Python lines (non-test) before: 6,121; after: 2,496 in the skill (256 of them the new YAML reader) plus 151 in `synthesis/rituals.py`.

## Tests

| Old test file | v5 | Why |
|---|---|---|
| `test_ritual_state.py` | `tests/test_ritual_state.py` | Ported; the self-test case removed with the inline suite; nine R5.1 cases added |
| `test_sync_watermark.py` | `tests/test_sync_watermark.py` | Ported; schema-1, acquisition-clock and other skills' prose cases removed; connector and empty-workspace cases added |
| `test_ritual_workers.py`, `test_repo_state.py`, `test_install_day_end.py` | `tests/test_ritual_workers.py`, `tests/test_repo_state.py`, `tests/test_day_end.py` | Rewritten for the slim scripts; launcher and nudge cases carried |
| `test_decay_sweep.py`, `test_portfolio_review.py`, `test_pr_queue_scan.py`, `test_mailboxes.py`, `test_gchat_preflight.py`, `test_ownership_routing.py` | Same names under `tests/` | Moved; the team-boundary case removed with `team_contract` |
| `test_acquisition_evidence.py`, `test_ritual_custody.py`, `test_ritual_evidence.py`, `test_ritual_read_identity.py`, `test_b11_ritual_ref_race.py` | Deleted | They tested cut custody and evidence machinery |
| `test_skill_documents.py`, `test_version_record.py` | Deleted | The 500-line budget and version labels are replaced by `tests/test_skill_format.py` |
| (new) | `tests/test_simple_yaml.py`, and `tests/test_rituals.py` in the core | The YAML reader; the SessionStart line and the nudge answer |

## Edge cases and the test that holds each

Scenario numbers from `guards-rituals.md` section 3, and R1.2 from the same list.

| Scenario | Test |
|---|---|
| 2 (R1.2) no day-start recorded today, said in one line | `tests/test_rituals.py::test_the_line_describes_this_workspace_without_naming_any` |
| 14 (R1.4) alerts carry a count and a pointer, no names; mute flag | `test_rituals.py` (no names in the line); `tests/test_day_end.py::test_the_banner_text_is_fixed_and_names_nothing`; mute flag in [mid-day-and-modes.md](mid-day-and-modes.md) |
| 53 two workspaces close the same evening | `tests/test_ritual_state.py::test_two_workspaces_closing_the_same_evening_both_keep_their_close` |
| 54 a 01:30 close counts for the logical workday | `test_ritual_state.py::test_a_close_written_after_midnight_counts_for_the_workday_it_names`, `test_a_record_needs_its_logical_date` |
| 55 Thursday review for Friday's obligation | `test_ritual_state.py::test_an_early_weekly_review_recorded_for_its_friday_is_not_owed_on_friday`; `test_rituals.py::test_weekly_review_is_anchored_to_the_most_recent_friday` |
| 56 empty workspace refused | `test_ritual_state.py::test_an_empty_workspace_is_refused_on_every_view`, `test_record_refuses_an_empty_workspace_before_appending`; `test_sync_watermark.py::test_an_empty_workspace_is_refused` |
| 57 decay tag in an earlier plan; misconfigured roots BLOCKED | `tests/test_decay_sweep.py` (kept) |
| 58 forty stale projects, three named | `tests/test_portfolio_review.py::test_output_is_capped_and_says_how_many_were_withheld` |
| 59 missing or unauthenticated host CLI lists the repo unscanned | `tests/test_pr_queue_scan.py` (kept) |
| 60 one closed, another not: the nudge still fires; missing tool fires | `tests/test_day_end.py::test_one_closed_workspace_does_not_silence_the_nudge_for_another`, `test_the_nudge_fires_when_its_state_tool_cannot_answer` |
| 61 a 09:15 read; later sync re-reads; status lists every target not re-read | `tests/test_sync_watermark.py::test_a_target_read_before_the_run_is_stale`, `test_declared_targets_block_individually` |
| 62 no advance on a failed read; never backwards; future refused; bare date for today refused | `test_sync_watermark.py::test_watermark_never_moves_backwards`, `test_future_watermark_is_refused`, `test_a_bare_date_means_end_of_day_so_today_is_refused_mid_day` |
| 63 fractional Slack ts dropped, never rounded up | `test_sync_watermark.py::test_slack_ts_with_a_fractional_part_is_floored_to_the_second` |
| 64 a deferral needs a reason and lapses after a day | `test_sync_watermark.py::test_deferral_requires_a_reason`, `test_explicit_deferral_unblocks_for_one_day_only` |
| 65 a due mailbox neither swept nor deferred fails, named | `tests/test_mailboxes.py::test_unswept_due_accounts_are_blind_and_fail` |
| 66 the Chat list hits its cap; `users/<id>` is never a space | `tests/test_gchat_preflight.py::test_short_page_and_page_cap_mark_the_set_bounded`, `test_a_person_id_is_never_a_read_target` |
| 67 connector reads advance with no token or receipt | `test_sync_watermark.py::test_a_connector_read_advances_without_a_token_or_receipt` |
| 68 day-end provenance over Slack timestamps written today | [day-end.md](day-end.md) Step 5b runs `provenance_scan.py` (built and tested by the guardrails helper) |
| R1.4 (project-state) uncommitted changes on arrival: refuse to pull, list them | `tests/test_repo_state.py::test_uncommitted_changes_are_listed_and_never_pulled_over` |
| Lesson 2026-09-14 one workspace's review silences another | `test_ritual_state.py::test_weekly_review_recorded_for_one_workspace_leaves_another_owed` |
| R8.1 the session line stays fast | `test_rituals.py::test_the_line_is_fast_on_a_year_of_records` |
| R8.5 Apple's Python reads every manifest | `tests/test_simple_yaml.py` |
