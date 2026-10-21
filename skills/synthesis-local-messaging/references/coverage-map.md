# Coverage map: local messaging 0.1.0 to 1.0.0, and the M3 script pass

Read when checking where a rule of the 0.1.0 or 1.0.0 text lives now (ruling D8).
The v5 prose restructure (0.1.0 to 1.0.0) kept every line of 0.1.0 in SKILL.md.
Milestone M3 then applied the code verdicts: the reader was slimmed, the send
path was replaced by the v5 send guard, and the OS sandbox moved here from the
old autopilot engine. The 1.0.0 SKILL.md, the 0.1.0 messages-boundary.md and the
0.1.0 adapter-contract.md are in [preserved.md](preserved.md) verbatim, so
`v5-skill-coverage-check.py` finds every old line.

## 0.1.0 SKILL.md, section by section

| 0.1.0 section | 1.0.0 (prose restructure) | Now (after M3) |
|---|---|---|
| Frontmatter description | Shortened, same triggers | Rewritten: adds the approved iMessage send; keeps local message triage, daily or 30-day review, authorized database path, no account discovery or transcript export |
| Frontmatter `depends_on` | Kept | `synthesis-autopilot` dropped (it was there for the sandbox, which moved into this skill); `synthesis-project-management` and `synthesis-message-guard` kept |
| Frontmatter `author`, `license`, `source_repo`, `source_type`, version 1.0.0, `format: v5` | Kept | Kept |
| Title and opening paragraph | SKILL.md (verbatim) | SKILL.md (verbatim) |
| "Read [the adapter contract]..." paragraph | SKILL.md (verbatim) | SKILL.md (verbatim) |
| Read and interpret, step 1 | SKILL.md (verbatim) | SKILL.md (verbatim); binding rule 1 |
| Step 2 | SKILL.md (verbatim) | SKILL.md, first two sentences verbatim; "separate owned state for each window and source generation" became "its own state directory"; binding rule 2 |
| Step 3 (the `synthesis exec-public` launcher command) | SKILL.md (verbatim) | Replaced by `python3 scripts/local_messaging.py --request REQUEST.json --state STATE_DIR`; old line in preserved.md |
| Step 4 (pages, cursor, source generations) | SKILL.md (verbatim) | SKILL.md: "A completed page is not complete history" verbatim; the rest restated for the slimmed cursor; binding rule 3 |
| Step 5 (review each candidate) | SKILL.md (verbatim) | SKILL.md (verbatim); binding rule 4 |
| Skip-rule paragraph | SKILL.md (verbatim) | SKILL.md (verbatim) |
| Untrusted-content paragraph | SKILL.md (verbatim) | SKILL.md (verbatim); binding rules 5 and 6 |
| Messages sending (three paragraphs) | SKILL.md (verbatim) | Replaced by "Sending one approved iMessage" and [sending.md](sending.md); binding rules 7 and 8; old text in preserved.md |
| Daily rituals paragraph | SKILL.md (verbatim) | Restated without "the existing ritual worker contract" (old machinery); binding rule 9; old text in preserved.md |

## Reference files

| File | Now |
|---|---|
| adapter-contract.md | Kept and updated: the request no longer carries `after` and `upper` (the state holds the cursor); "SQLite and file behavior" and "Durable output" restated for the slimmed reader and the moved sandbox; "Outbound recovery" retired. Unchanged sentences kept verbatim; the 0.1.0 file is in preserved.md |
| messages-boundary.md | Retired with the send path it described; verbatim in preserved.md. Its live rules (one explicit account, existing chat and participant; text by private descriptor; one send call, no fallback or group send; expiry checked again before the call; no readback proves causation; never replace state to retry) are in [sending.md](sending.md) |
| sending.md | New: the send command, approval, outcomes and limits |
| preserved.md | New: the retired text, verbatim, with the reasons |

## Scripts in v5 (M3)

Line counts are `wc -l`. Verdicts from the v5 code evaluation (tool scripts, local messaging; autopilot row G).

| Old script (lines) | Verdict | Now (lines) |
|---|---|---|
| `scripts/local_messaging.py` (804) | SLIM | `scripts/local_messaging.py` (420): read-only SQLite inside the sandbox, window query, skip rules, body decoder, pages saved before the cursor moves. The command line folded in; the request lost `after` and `upper`. Above the evaluation's 280-line estimate by the sandbox runner and the crash-safe cursor that E81 and E83 need. 476 after the fixes of 2026-10-13 (below) |
| `scripts/local_messaging_cli.py` (32) | KEEP, fold into the reader | Folded into `local_messaging.py` |
| `scripts/messages_boundary.py` (400), `messages_native.py` (307), `messages_outbound.py` (320) | REPLACE | The v5 send guard (`synthesis/guards.py` `check_send`, `synthesis/approvals.py`) around `scripts/messages_send.py` (177) and the read-only `scripts/messages_route.js` (24) |
| `scripts/messages_transport.js` (46) | KEEP | Kept; its route contract drops `database_account_id` and `database`, which only the retired readback used |
| `synthesis-autopilot/scripts/evaluation_artifacts.py` lines 201-289 (`_sandbox_command`, `sandbox_available`, `run_python_check`, with `_safe`, `_read`, `MAX_BYTES`) | KEEP, move to the consumer | `scripts/os_sandbox.py` (136), unchanged in behaviour. 63 since 2026-10-13: `run_python_check`, `_safe`, `_read` and `MAX_BYTES` removed, because the reader runs its worker with `_sandbox_command` and never called them; their sandbox-policy tests now run through that command |
| Old tests (`scripts/test_*.py`, 1,704 lines) | Removed with the code they tested | `tests/` below |

## Edge cases and the tests that hold them

| Scenario | Test (in `tests/`) |
|---|---|
| E81 read-only database, notes not copies | `test_local_messages_reader.py::test_e81_wal_database_is_read_only_and_notes_hold_pointers_not_text`, `test_e81_unconfined_worker_refuses_before_sqlite_opens`, `test_e81_confinement_probe_*`, `test_e81_writable_input_refuses_and_closes_its_descriptor` |
| E82 skip rules; excluded chats never decoded | `test_e82_excluded_chat_is_skipped_and_never_decoded`, `test_e82_codes_deliveries_and_marketing_are_skipped`, `test_e82_short_codes_and_reactions_are_skipped`, `test_e82_group_needs_the_exact_self_name_not_a_generic_you` |
| E83 unsupported body or gap is reported and holds the window | `test_e83_unsupported_body_is_a_gap_not_an_empty_success`, `test_e83_a_gap_does_not_advance_the_window`, `test_e83_pages_advance_only_after_saving_and_a_complete_window_replays`, `test_e83_interrupted_cursor_write_rereads_the_same_page` |
| E84 never resend after an uncertain outcome; a matching outbound row proves nothing | `test_imessage_send.py::test_e84_an_uncertain_outcome_is_never_resent`, `test_e84_a_matching_outbound_row_does_not_turn_uncertain_into_sent` |
| R3.1 exact-text approval, one send per approval | `test_send_waits_for_exact_approval_then_sends_once`, `test_approval_covers_only_the_exact_text_and_recipient`, `test_forbidden_phrases_block_before_approval_and_bad_config_blocks_everything` |
| Sandbox behaviour (moved with the code) | `test_local_messages_sandbox.py` (through the reader's own sandbox command: private reads, writes to the database folder and outside, and network denied; no fork or spawn on macOS; no sandbox means the reader runs nothing; the Linux loader paths) |
| Apple's Python 3.9 runs the reader | `test_local_messages_reader.py::test_command_line_reads_and_saves_a_page[/usr/bin/python3]` |
| A message in Recently Deleted takes the chat that record names and is skipped as `deleted` (the rows of 2026-10-08 and 2026-10-19); every other row without one chat is a gap saying why, and no chat is inferred from a handle | `test_local_messages_reader.py::test_recently_deleted_rows_take_their_recorded_chat_and_are_skipped`, `test_a_row_with_no_single_chat_stays_a_gap_that_says_why` |
| A store whose app stopped writing is stale: never complete, its cursor open for what syncs later, `through` at its newest message, the threshold a bounded option | `test_a_store_that_stopped_syncing_is_stale_and_its_window_stays_open`, `test_the_wal_file_time_counts_as_a_write`, `test_the_stale_threshold_is_a_bounded_number_of_hours` |
| An undecodable link or attachment row is marked, not held; unreadable text still holds | `test_undecodable_link_and_attachment_rows_carry_a_marker_and_do_not_hold_the_window`, `test_a_row_whose_text_is_genuinely_unreadable_still_holds_the_window` |
| A by-hand review closes a page's gaps only with the principal's approval of exactly those rows | `test_a_principal_approved_review_closes_the_gaps_it_names_and_is_recorded`, `test_a_review_names_exactly_the_pages_gaps_and_a_grant_alone_closes_nothing` |

Sandbox tests skip where neither `sandbox-exec` nor `bwrap` can run a probe,
and fail instead when `SYNTHESIS_REQUIRE_SANDBOX=1` is set (CI sets it).

## Fixes of 2026-10-13

Two field reports held windows on rows a person could read in the app: outgoing
rows with a handle and no `chat_message_join` row ("ambiguous chat attribution",
which an excluded chat could not clear), and link or attachment rows whose body
is typedstream ("unsupported attributedBody encoding"). The reader now
attributes the first to the handle's one one-to-one chat and marks the second,
and a by-hand review the principal approves can close any other gap by name.
The `imessage-v1` contract gained `message.balloon_bundle_id`, `attachment` and
`message_attachment_join`. Where the text lives: binding rule 3, step 4 and the
skip-rule paragraph in SKILL.md (the 1.0.0 lines are in preserved.md), and the
chat attribution, marker and "Closing a gap by hand" text in
[adapter-contract.md](adapter-contract.md).

## Fixes of 2026-10-20

Two field reports of 2026-10-19. First, the iMessage reader held its window on five
"ambiguous chat attribution" rows again. Read from the store's metadata only (never a body):
all five were incoming, each with a handle, no `chat_message_join` row, and exactly one
`chat_recoverable_message_join` row naming the one chat their handle belongs to, a one-to-one
chat; two were iMessage and three SMS. That table is Messages' Recently Deleted. The seven
outgoing rows of 2026-10-08, which the handle inference of 2026-10-13 attributed, had the same
record. So the reader now attributes a row with one Recently Deleted record to that chat and
skips it as `deleted` (excluded chats still apply first), retires the handle inference (in the
same store, two messages to a handle sat in another one-to-one chat than the handle's own, so
the inference was a guess) and with it `coverage.by_handle`, and gives every remaining gap a
reason that says why. `chat_recoverable_message_join` is an optional table of `imessage-v1`
(`OPTIONAL` in the reader); a store without it keeps the plain "no chat link" gap.

Second, a WhatsApp store stopped syncing on 2026-10-17 and two days later the reader called the
window complete over it, so the watermark moved past messages that arrived once the app opened.
Each page now compares the store's newest message and its database and `-wal` modification
times with the window's reach; a store silent for `--stale-after-hours` (12 hours for WhatsApp, 24 for iMessage, by default) while
the window runs past it reports `coverage.stale`, is never complete, keeps its cursor open
without a snapshot bound, and sets `coverage.through` to its newest message. `coverage.store`
holds the facts and `coverage.through` how far a watermark may move. The iMessage store gets
the same check, through the same worker.

Where the text lives: binding rules 3 and 9, steps 3 and 4, the skip-rule paragraph and the
Daily rituals paragraph in SKILL.md; the `imessage-v1` bullet, the chat attribution paragraphs,
"Stale stores" and "State and output" in [adapter-contract.md](adapter-contract.md); the daily
rituals' day-start step 3b names the watermark rule. To keep SKILL.md under 8,000 bytes, the
send paragraph's list of outcomes now lives only in [sending.md](sending.md), and the Contents
line pointing at the sections below it was dropped. Every replaced 1.1.1 passage is verbatim in
[preserved.md](preserved.md#replaced-on-2026-10-20-verbatim). `scripts/local_messaging.py` is
523 lines (476 before).

## Group and SMS sends, watched chats (2026-10-20, later)

A request from the principal's operations session: an SMS group with two friends for a trip, where an agent
should post logistics and help watch for emergencies. `messages_send.py --members` sends to the one existing
iMessage or SMS chat, group or one-to-one, whose members are exactly the handles given, under the same
approval, which binds every member, the service, the text and the chat; the transport re-checks members and
service before its single call. The reader's optional `watched_chats` keeps every message in a named chat as
a note. Text: binding rule 7, the skip-rule paragraph and the send section in SKILL.md; "A group or an SMS
chat, by its members" and "What the send never does" in [sending.md](sending.md); the request section of
[adapter-contract.md](adapter-contract.md). Replaced passages:
[preserved.md](preserved.md#replaced-later-on-2026-10-20-for-group-and-sms-sends-verbatim).

## Frontmatter before v5 (verbatim)

The 0.1.0 frontmatter, kept whole so the old description and keys stay on record.

```yaml
---
name: synthesis-local-messaging
description: Read explicitly selected local Messages or WhatsApp SQLite data into bounded notes and source pointers. Use for local message triage, daily or trailing-window review, and Messages guard integration. Requires an authorized database path; does not discover accounts, export transcripts, activate rituals, or grant send authority.
license: "Apache-2.0"
depends_on: ["synthesis-project-management", "synthesis-autopilot", "synthesis-message-guard"]
metadata:
  author: "Synthesis Engineering"
  version: "0.1.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

## The 1.0.0 frontmatter, before the M3 pass (verbatim)

```yaml
---
name: synthesis-local-messaging
description: "Read explicitly selected local Messages or WhatsApp SQLite data into bounded notes and source pointers. Use for local message triage, daily or trailing-window review, and Messages guard integration. Needs an authorized database path; no account discovery, transcript export or send authority."
license: "Apache-2.0"
depends_on: ["synthesis-project-management", "synthesis-autopilot", "synthesis-message-guard"]
metadata:
  author: "Synthesis Engineering"
  version: "1.0.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
