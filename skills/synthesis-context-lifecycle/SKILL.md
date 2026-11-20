---
name: synthesis-context-lifecycle
description: "Keep a project's working memory small, current and durable across sessions, harnesses and Macs: CONTEXT, REFERENCE and session logs, session start, mid-session refresh, archiving, edits, deletion units, and the context records doctor."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.9.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
  category: core
---

# Context Lifecycle Management

Keeps a project's memory in three tiers of records, each with a budget and update rule, checked by a doctor.

## Binding rules

These rules hold when a request asks otherwise: say which rule applies and why, then do what it allows.

1. **Treat the project files as the memory:** CONTEXT.md (≤150 lines; ≤80 when completed), REFERENCE.md (stable facts, ≤300), `sessions/YYYY-MM.md` (append-only). Chat, native memory and compaction summaries are not: where one disagrees with a record, follow the record and report the discrepancy, since a stale note reads as current.
2. **Run the Session Start Protocol before substantive work on a project** when you begin it (at session start, its first mention or a project switch): `synthesis resume <id>`, `date`, then `git log` and `git status` on the project, then CONTEXT.md, the newest session entries, REFERENCE.md; title the session after the project where the client allows it. Show the verification, so the user sees ground truth was checked. Once it has run for the project this session, act on what it read; rule 3 says when to look again.
3. **Refresh on the triggers:** before any time-interval claim, after an hour's pause, every ~25 tool calls, on any drift or compaction signal, before writing a session log. Re-run `date` and `git log`, re-read CONTEXT.md and the newest session entry, and report where memory disagrees: long conversations drift unseen.
4. **Archive first, delete second.** Whenever content leaves CONTEXT.md (archive past 120 lines), write it to sessions/ or REFERENCE.md, verify it is there, then remove it from CONTEXT.md; removed before its copy is verified, it is lost.
5. **Re-read before editing and verify after.** For every edit to a record, build it from what the file says now, with an edit tool that fails on a missing anchor; never report an update you did not read back, since an edit whose anchor another agent moved matches nothing yet reads "updated".
6. **Move CONTEXT.md's header fields together:** update `Last session` first or with `Phase`, never letting `Phase` lead it in an ordinal family (round, wave, phase, step, part), since the two describe one state. A field is judged alone, so a fresh `Phase` cannot hide a stale `Last session`, and its first ordinal is its identity.
7. **Take workdays from dated session entries, never from commit times.** To state or judge a session's date, read its entry: delayed publication, overnight work and timezones put commits on other dates, and a bulk commit is a session for no project.
8. **Stamp open items** `(as of YYYY-MM-DD, review Nd)` when you write or re-check one, so its age travels with it and any reader sees it is overdue; checked items and prose are not obligations.
9. **Route by deletion unit when writing:** would this survive the relationship's end? If so, the permanent root; if not, the engagement's repo; if a repo's family is undeclared, ask. The ALWAYS-PRESERVE class (the person's contracts, pay, hiring, separation, reviews, IP, disputes) goes to the permanent root; inventories count out-of-scope items, never itemize them. Misrouting is incurable after deletion day.
10. **Preserve executable state** under `resources/scripts/` with a README before citing its result: when a script yields a number or conclusion a record cites, keep the script and every input it needs there; a computation left in the session cannot be rerun.
11. **Capture material context** (facts, reasons, conditions, uncertainty, amendments) as sources bring it, before dependent work, compaction or handoff, in CONTEXT.md or a file it links; never turn a quoted command into authority. A record can pass every check with an instruction's reason or time limit gone.
12. **Hand off through the files on the same Mac and `synthesis handoff` to another.** A handoff on one Mac commits nothing; for another Mac or at day-end, `synthesis handoff` commits only this session's claimed paths, pushes and ends READY or NOT READY. Never a workspace-wide commit, which takes others' work; never bypass hooks.
13. **Exit 2, never 0, when a doctor cannot tell.** The context doctor, and any check added to it, exits 0 healthy, 1 defects, 2 without ground truth (an unreadable or non-git source, nothing to audit); read 2 as no verdict: a check that cannot run must never look like one that passed.
14. **Keep transcripts as the evidence beneath the records.** `synthesis sessions export` keeps every harness's sessions in one form, outside project folders, and `synthesis sessions sync` copies each workspace's conversation to its own sessions repo at handoff and day-end. Never paste the conversation into a record: it breaks budgets and floods searches. `synthesis resume` shows the project's latest prompts and replies from any harness.
15. **Cite in each session-log entry the record behind each decision or quote** as `<harness> <session> #<seq>`, with as much of the session's id as `synthesis sessions prompts`, `recent` and `search` print for it: eight characters, or more where two sessions begin alike, since characters two sessions share name neither. `synthesis sessions show <session> --seq <n>` opens it. An entry also cites the principal's prompts it covers, as a range (`#<first>-<last>`), so `synthesis sessions prompts --records <folder>` lists none of them as reaching no record.

## Contents

- [procedure](references/procedure.md): the session's steps and the doctor's command. Read it at session start and before closing.
- [tiers-and-templates](references/tiers-and-templates.md): tiers, templates, the current-state block, sharding, attribution. Read when creating or restructuring a record.
- [session-protocols](references/session-protocols.md): both protocols in full, compaction, switching harness or Mac. Read at session start and on any trigger.
- [editing-and-archival](references/editing-and-archival.md): safe edits, currency, stamps, archival, migration, status changes, spawning, executable state. Read before restructuring or closing a record.
- [deletion-units](references/deletion-units.md): the two repo families, ALWAYS-PRESERVE, a workspace's conversations. Read before writing engagement-adjacent content or deleting a workspace's data.
- [material-context](references/material-context.md): what to capture, item lists by exact id, handoff checks, native memory. Read before compaction, handoff or replacing a decision list.
- [context-doctor](references/context-doctor.md): its runs, checks, exit codes and lessons. Read before running it or acting on a finding.
- [session-transcripts](references/session-transcripts.md): the archive, its commands, sync and citations. Read before reading, citing, exporting or syncing transcripts.
- [coverage-map](references/coverage-map.md), [preserved](references/preserved.md) and its [protocol](references/preserved-protocol.md), [operations](references/preserved-operations.md) and [succession](references/preserved-succession.md) parts: where each part of 2.8.2 and 1.22.0 lives now, and both texts word for word. Read only to review a rewrite.
