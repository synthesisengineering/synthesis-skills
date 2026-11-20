# Preserved: context lifecycle text replaced in 2.0.0 and in 2.9.0, and why

Two rewrites, newest first. The 2.9.0 section says why each part of SKILL.md changed in the rewrite to the
repository's standard and holds the 2.8.2 SKILL.md word for word. The 2.0.0 record follows it, kept word for word,
as does its opening paragraph:

Ruling D8: a rewritten skill loses nothing. This file says what the v5 rewrite
of synthesis-context-lifecycle did not carry from 1.22.0 (`origin/main` on
2026-10-05) and why, and holds the 1.22.0 SKILL.md verbatim. The 1.22.0
reference files are verbatim in [preserved-protocol.md](preserved-protocol.md),
[preserved-operations.md](preserved-operations.md) and
[preserved-succession.md](preserved-succession.md). [coverage-map.md](coverage-map.md)
maps every part to its new home. Nothing in these files is current procedure.

## Contents

- [Retired in 2.9.0: the rewrite to the D8 standard](#retired-in-290-the-rewrite-to-the-d8-standard)
- [What was cut and why](#what-was-cut-and-why)
- [Incidents and lessons behind the carried rules](#incidents-and-lessons-behind-the-carried-rules)
- [The 1.22.0 SKILL.md](#the-1220-skillmd)

## Retired in 2.9.0: the rewrite to the D8 standard

2.9.0 rewrote the skill's instruction text to the repository's rewrite standard, `docs/skill-writing.md` (writing
rules W1 to W19). Every rule's new place is in [coverage-map.md](coverage-map.md). A passage moved word for word to
another file is recorded there; the whole 2.8.2 SKILL.md is below all the same, so every word of it stays readable in
one place.

### SKILL.md

Why each part changed:

- **Opening paragraph.** Its first two sentences were background: AI collaborators start every session with zero
  context, and a single context file grows without bound because it mixes information with different lifecycles.
  [tiers-and-templates.md](tiers-and-templates.md), The Problem, says both in nearly the same words, and W19 keeps
  background out of SKILL.md. Its third sentence stays, in fewer words, as the paragraph that says what the skill is
  for (format rule 2).
- **The line above rule 1.** New (W8, format rule 11): the rules hold when a request asks otherwise, and the answer
  to such a request says which rule applies and why, then does what it allows. The rules protect the records that
  every later session, harness and Mac resumes from.

  Two sentences joined it after the gate of 2026-11-20 (W12, W15). That gate found no rule weaker on either model,
  but blind comparison did not favor the rewrite: on Opus each text won 14 comparisons and 14 tied; on Sonnet 2.8.2
  won 17, the rewrite 15, and 10 tied. Most of the judge's reasons for 2.8.2's wins named what the rewrite's answers
  added to what was asked: a placeholder transcript citation (rule 15) in the session-log line a case asked for,
  which every one of the rewrite's twelve answers to that case carried and none of 2.8.2's did (the judge named
  placeholders in Opus cl-03 rep 3 and cl-04 reps 1 to 3, and Sonnet cl-04 reps 0 and 1); answers past the sentence count asked for (Opus cl-05 reps 0 and 3, Sonnet cl-05
  reps 1 and 2, Sonnet cl-07 rep 4); notes, checks and procedure appended to what was asked (Opus cl-01 rep 1,
  cl-03 reps 0, 3 and 4, cl-04 reps 0 and 5, cl-07 rep 4; Sonnet cl-03 reps 0 and 2, cl-04 rep 4, cl-07 rep 2); and,
  on Sonnet, a command without the target the request named (cl-02 reps 2 to 5). The rewrite's rules carry more of
  each step than 2.8.2's did, and its answers recited the steps they could not run. The second sentence says that
  asking for a format or length is not asking otherwise, so a rule's report goes inside what was asked; the third
  says where a date or citation comes from (a stamp's date among them), and keeps what could not be checked or
  filled to one clause, with no placeholder left. Rules 1, 2, 8 and 15 keep their requirements: the judge's reasons for the rewrite's wins (a
  clearer report of the stale note, reading the records before acting, acting once the records read agreed with
  memory) came from rules 1 and 2 (Opus cl-01 rep 0, cl-06 reps 4 and 5, cl-07 reps 0 and 2; Sonnet cl-01 reps 0, 1
  and 3, cl-06 reps 1 and 2, cl-07 reps 0 and 5).
- **Binding rules 1 to 15.** Each keeps its number and its meaning. Each is rewritten to W5 (the action as the bold
  head, then its scope and its reason) and made complete on its own (W2), from the skill's own text:
  - Rule 1 keeps CONTEXT.md's two budgets, REFERENCE.md's, the session log's append-only form and the sentence that
    chat, native memory and compaction summaries are not the memory. It now says what to do when one of them
    disagrees with a record: follow the record, as [material-context.md](material-context.md), Native memory,
    resolves conflicts "in favor of the synthesis record", and report the discrepancy, as the Mid-Session Refresh
    Protocol's step 5 does, since a stale note reads as current. Every case of the skill's evaluation tests this
    rule, and every one passed with 2.8.2 on both models in the evaluation of 2026-11-18 (two repetitions), so no
    wording was made louder (W10); at the gate's six repetitions 2.8.2 passed 76 of 78 checks on Opus and 78 of 78 on
    Sonnet, and the rewrite 78 of 78 and 76 of 78, a difference inside the noise. The rule also carries
    the Procedure's "During work" instruction word for word: "After each task, update CONTEXT.md under your claim.
    Keep the current-state block (Phase, Status, Last session, Plan, Next actions) current: it is what returns after
    compaction." It is the skill's core behavior and no evaluation case measures it, so it stays where every load
    reads it rather than only in the reference that now holds the Procedure. To make room within W19's 7,600 bytes,
    the Procedure joined session-protocols.md, which freed a Contents line, and two clauses this rewrite had added to
    other rules returned to the references that state them word for word (rules 6 and 13, below). No 2.8.2 text left
    SKILL.md.
  - Rule 2 keeps its head, its steps in their order and "show the verification". It names its trigger as
    [session-protocols.md](session-protocols.md) does (substantive work on a project begins: at session start, at
    the project's first mention, or after a switch from another project), and takes its reason from that file's
    "Why this order matters" and "Visible to the user". From the Procedure it takes `synthesis resume <id>` and the
    session title, "title the session after the project where the client allows it" (session-protocols.md's step 6),
    which the skill's own test `test_session_start_names_the_session_after_the_project` requires SKILL.md to carry.
    It ends where it stops (W7, W15): once the protocol has run for the project this session, the agent acts on what
    it read, and rule 3 says when to look again. In the evaluation of 2026-11-18, case cl-07 first said only that
    the agent had just read CONTEXT.md, not that the protocol had run. In all four runs, Sonnet with the skill
    answered that it would run the Session Start Protocol first and send only after it, failing the check that it
    proceeds; Opus, with the skill or without it, and Sonnet without it proceeded. 2.8.2 said neither when the
    protocol runs nor what follows once it has run. The case now says the protocol ran, and every condition passes
    it.
  - Rule 3 keeps its head and its five triggers word for word. It now says what a refresh does, from the Mid-Session
    Refresh Protocol's steps 1 to 5 (re-run `date` and `git log`, re-read CONTEXT.md and the newest session entry,
    report where memory disagrees), with that section's reason: long conversations drift.
  - Rule 4 keeps its head and its three steps. It names its trigger (any content leaving CONTEXT.md, with the
    Procedure's 120-line mark) and takes its reason from the Archival Protocol: content removed before its copy is
    confirmed is lost.
  - Rule 5 keeps every clause, names its scope (every edit to a record) and takes its reason from
    [editing-and-archival.md](editing-and-archival.md), "Editing a durable context file": an edit whose anchor
    another agent rewrote silently matches nothing while the report still says "updated".
  - Rule 6 names CONTEXT.md in its head and keeps "Update `Last session` first or with `Phase`", "a field is judged
    alone" and "its first ordinal is its identity". From editing-and-archival.md's "Header fields move together" it
    takes the ordinal families, that `Phase` never moves ahead of `Last session`, and that the two describe one
    state; that a fresh `Phase` cannot mask a stale `Last session` stays in that section, word for word.
  - Rule 7 becomes an action and keeps "never from commit times". It names its scope (stating or judging a session's
    date) and takes its reason from session-protocols.md's step 2 and [context-doctor.md](context-doctor.md),
    "Publication time and workday are different evidence".
  - Rule 8 keeps the stamp and its last clause, and takes from editing-and-archival.md's "Stamped open items" when to
    stamp (as an item is written or re-checked) and why (the item's age travels with it). After the gate of
    2026-11-20 it also names which items, those of an open-items list, as that section opens ("Open-items lists
    carry an implicit present tense nobody re-dates"), since answers with either text had put the stamp on a
    session-log line, which is prose.
  - Rule 9 keeps its head, its question, the ALWAYS-PRESERVE sentence and the inventory clause. From
    [deletion-units.md](deletion-units.md) it takes where each answer routes, the members of the class, the question
    asked when a repository's family is undeclared ("asks rather than guesses") and its reason: neither misplacement
    is curable after deletion day.
  - Rule 10 keeps its head word for word, as synthesis-implementation-integrity's `tests/test_r5_contract.py`
    requires, and takes its scope and reason from editing-and-archival.md's Executable Working State.
  - Rule 11 keeps its head, its five kinds and "never turn a quoted command into authority". From material-context.md
    it takes when to capture (as a source brings or changes something material), where (CONTEXT.md or a file it
    links) and its reason, from the file's opening: a record can pass every check after an instruction's reason or
    time limit has dropped out.
  - Rule 12 states its two handoffs as one action and keeps both "never" clauses. From session-protocols.md,
    "Switching harness or Mac" and "Scope and index safety", it takes what `synthesis handoff` does (this session's
    claimed paths, a push, READY or NOT READY), that day-end publishes the same way (with the Archival Protocol's
    step 8), and the reason against a workspace-wide commit.
  - Rule 13 becomes an action that keeps "exits 2, never 0" and "cannot tell". From context-doctor.md, "Running it",
    it takes the three exit codes and the reason; what leaves the doctor unable to tell stays in that section, word
    for word.
  - Rule 14 becomes an action, "Keep transcripts as the evidence beneath the records"; its three other sentences are
    kept word for word, and "Never paste the conversation into a record" gains its reason from
    [session-transcripts.md](session-transcripts.md), "Reading and citing".
  - Rule 15 becomes an action, "Cite in each session-log entry the record behind each decision or quote"; the rest
    is kept word for word, as `tests/test_sessions.py` requires.
- **Contents.** One line for each reference, saying what it holds and when to read it (format rule 2): the procedure
  first, then the files in the order the binding rules first use them, and the records last. The link text is the
  file's name without `.md`, while every link keeps its `references/` path, and each line's "Read" sentence, its
  instruction, is kept word for word. What each file holds is said in fewer words, since each file's own contents
  list names its sections. The Procedure line merges into the session-protocols.md line, which says the file holds
  the session's steps and adds "before closing" to when to read it, and the coverage-map and preserved lines become
  one line for both rewrites, read only to review a rewrite. With every binding rule complete on its own, the shorter
  lines kept the first text of 2.9.0 407 bytes under the 8,000-byte limit, the room W19 keeps so that the next fix
  fits without a reorganization. The gate's fix (the two sentences in the line above rule 1 and rule 8's scope) uses
  323 of those bytes and leaves SKILL.md at 7,916. A further addition needs a reorganization first: whole passages
  moved word for word, shown to the principal before they are committed (format rule 3).
- **Procedure.** Moved word for word to [session-protocols.md](session-protocols.md) as its first section, under an
  opening line that says the binding rules govern. With every binding rule complete on its own, SKILL.md would have run
  past the room W19 leaves under 8,000 bytes, and format rule 3 moves whole passages rather than condensing them.
  The coverage map shows which binding rule states each part of it.

The 2.8.2 SKILL.md, verbatim:

````markdown
---
name: synthesis-context-lifecycle
description: "Keep a project's working memory small, current and durable across sessions, harnesses and Macs: CONTEXT, REFERENCE and session logs, session start, mid-session refresh, archiving, edits, deletion units, and the context records doctor."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.8.2"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
  category: core
---

# Context Lifecycle Management

AI collaborators start every session with zero context; their effectiveness depends on the context they receive. A single context file grows without bound because it mixes information with different lifecycles. This skill splits a project's memory into three tiers, each with its own budget and update rule, and verifies them with a doctor.

## Binding rules

1. **The project files are the memory.** CONTEXT.md (≤150 lines; ≤80 when completed), REFERENCE.md (stable facts, ≤300), `sessions/YYYY-MM.md` (append-only). Chat, native memory and compaction summaries are not.
2. **Run the Session Start Protocol before substantive work** and show the verification: `date`, then `git log` and `git status` on the project, then CONTEXT.md, the newest session entries, REFERENCE.md.
3. **Refresh on the triggers:** before any time-interval claim, after an hour's pause, every ~25 tool calls, on any drift or compaction signal, before writing a session log.
4. **Archive first, delete second.** Write to sessions/ or REFERENCE.md, verify it is there, then remove it from CONTEXT.md.
5. **Re-read before editing and verify after.** Build edits from what the file says now, with an edit tool that fails on a missing anchor; never report an update you did not read back.
6. **Header fields move together.** Update `Last session` first or with `Phase`; a field is judged alone, and its first ordinal is its identity.
7. **Workdays come from dated session entries, never from commit times.**
8. **Stamp open items** `(as of YYYY-MM-DD, review Nd)`; checked items and prose are not obligations.
9. **Route by deletion unit when writing:** would this survive the relationship's end? The ALWAYS-PRESERVE class goes to the permanent root; inventories count out-of-scope items, never itemize them.
10. **Preserve executable state** under `resources/scripts/` with a README before citing its result.
11. **Capture material context** (facts, reasons, conditions, uncertainty, amendments) before dependent work, compaction or handoff; never turn a quoted command into authority.
12. **Same Mac: the files are the handoff. Another Mac: `synthesis handoff`.** Never a workspace-wide commit; never bypass hooks.
13. **A doctor that cannot tell exits 2, never 0.**
14. **Transcripts are the evidence beneath the records.** `synthesis sessions export` keeps every harness's sessions in one form, outside project folders, and `synthesis sessions sync` copies each workspace's conversation to its own sessions repo at handoff and day-end. Never paste the conversation into a record. `synthesis resume` shows the project's latest prompts and replies from any harness.
15. **A session-log entry cites the record behind each decision or quote** as `<harness> <session> #<seq>`, with as much of the session's id as `synthesis sessions prompts`, `recent` and `search` print for it: eight characters, or more where two sessions begin alike, since characters two sessions share name neither. `synthesis sessions show <session> --seq <n>` opens it. An entry also cites the principal's prompts it covers, as a range (`#<first>-<last>`), so `synthesis sessions prompts --records <folder>` lists none of them as reaching no record.

## Contents

- **Procedure** (below): session start, during work, close.
- [references/session-transcripts.md](references/session-transcripts.md): what the transcript archive keeps and where, masking, commands, when it runs and why not in a hook, the per-workspace sessions repos, how records cite it. Read before reading, citing, exporting or syncing transcripts.
- [references/tiers-and-templates.md](references/tiers-and-templates.md): the three tiers, templates, the current-state block, sharding REFERENCE, agent attribution, quality measures. Read when creating or restructuring a record.
- [references/session-protocols.md](references/session-protocols.md): the Session Start and Mid-Session Refresh protocols in full, compaction signals, switching harness or Mac. Read at session start and on any trigger.
- [references/editing-and-archival.md](references/editing-and-archival.md): safe edits, header and body currency, item stamps, archival, migration, status changes, spawning, executable state. Read before restructuring or closing a record.
- [references/deletion-units.md](references/deletion-units.md): permanent root versus engagement repos, the ALWAYS-PRESERVE class, and the agent conversations a workspace's deletion includes. Read before writing engagement-adjacent content or deleting a workspace's data.
- [references/material-context.md](references/material-context.md): what to capture, replacing item lists by exact id, checking a handoff, native memory. Read before compaction, handoff or replacing a decision list.
- [references/context-doctor.md](references/context-doctor.md): running the doctor, its checks, exit codes and the lessons built into it. Read before running it or acting on a finding.
- [references/coverage-map.md](references/coverage-map.md): where every part of 1.22.0 lives now.
- [references/preserved.md](references/preserved.md), [references/preserved-protocol.md](references/preserved-protocol.md), [references/preserved-operations.md](references/preserved-operations.md), [references/preserved-succession.md](references/preserved-succession.md): why the old machinery was cut, and the 1.22.0 text verbatim. Read only to review the cut.

## Procedure

**Session start.** Establish this conversation's project with `synthesis resume <id>` (it asks before switching and warns about newer copies), then the Session Start Protocol: `date "+%Y-%m-%d %H:%M:%S %Z (%A)"`; `git log -10 --pretty=format:"%h %ai %ci %s" -- <project>` and `git status --short -- <project>`; read CONTEXT.md, the newest dated session entries and REFERENCE.md; title the session after the project where the client allows it. Show the result in one line: today, last commit, whether CONTEXT.md matches.

**During work.** After each task, update CONTEXT.md under your claim. Keep the current-state block (Phase, Status, Last session, Plan, Next actions) current: it is what returns after compaction. Archive when CONTEXT.md passes 120 lines.

**Check.** Run the doctor for this project:

```bash
python3 -s "$HOME/.synthesis/v5/current/skills/synthesis-context-lifecycle/scripts/context_doctor.py" --project <root>/projects/<id>
```

It prints this project's findings, each `FAIL` or `warn` with a remedy line, then `HEALTHY` or `DEFECTS` with totals; it exits 0, 1 or 2. Without `--project` it audits every knowledge root, leads with this session's project and counts the rest.

**Close.** Append the session entry (with Attribution lines when several agents contributed), refresh the header and current-state block, archive cold content, run the doctor, and hand off per rule 12.
````

## What was cut and why

Source: the v5 code evaluation, project state, section E (2026-10-05).

- **`context_edit.py` (1,469 lines), REPLACE.** It made scripted edits fail on
  a missing or ambiguous anchor, gated budgets and header coherence, protected
  tables and line endings, ran multi-file transactions, patched index.yaml and
  held the native-memory sweep. Claude Code's Edit and Codex's apply_patch
  already fail on a missing or ambiguous anchor; the rules it enforced are
  prose in [editing-and-archival.md](editing-and-archival.md); its "Phase
  changed but Last session did not" refusal became the doctor's `header-lag`
  check; index.yaml writers are serialized by a claim; the memory sweep is a
  day-end ritual step (synthesis-daily-rituals).
- **`record_transaction.py` (1,244 lines), CUT.** Journaled multi-file commits
  with crash recovery. Git is the journal and claims serialize writers. The
  index.yaml concurrency it handled stays real; the claim rule carries it.
- **`review_ledger.py` (273 lines), REPLACE.** A per-workspace JSONL of
  open-item changes for weekly reviews; the four ledgers were last written
  2026-08-27, the day it shipped. The markdown lapse register in the workspace
  instructions (since 2026-10-01) does the job: append-only, per workspace, a
  corrupt line costs only that line.
- **`context_doctor.py` (1,944 lines) and `context_currency.py` (579), SLIM**
  into one doctor of about 580 lines. Kept: budgets, status agreement and
  vocabulary, freshness from dated records, per-field header currency, body and
  item stamps, durability, quiet advice on dormant projects with paired
  inversions, denominators, exit 2 for "cannot tell". Cut: the report cache,
  shard-internal checks (index orphan, topic budgets, missing index), packet
  provenance (`skill-outputs`), intake routing, material-context projections,
  cited-script existence, structured state (`CURRENT_STATE.json`), team
  enrollment, transaction locks and the `--readiness local|remote` split (the
  doctor reports uncommitted and unpushed records as warnings; `synthesis
  handoff` is the step that refuses). It had come to bury its signal in 200+
  warnings; the v5 report leads with the session's project and counts the rest.
- **`record_succession.py`**, SLIM into the decision-packet generator (R5.3);
  handled outside this skill. Its doctrine (exact-id accounting, unanswered
  items carry forward) is in [material-context.md](material-context.md).
- **Structured operational state, local receipts, pending manifests,
  LOCAL_READY / LOCAL_RECOVERABLE / REMOTE_READY.** v5 has no receipts or
  manifests: the same Mac needs nothing (R1.3) and `synthesis handoff` reads
  readiness straight from git (R1.4).
- **The active-project pointer and `conformance.py activate`.** A global
  pointer delivered a message to the wrong session on 2026-09-03; v5 keeps the
  project on each session's own board file (`synthesis use`, `synthesis resume`).
- **Autopilot recovery capsules** belong to the 3.x run journal, replaced by
  the plan file (R6.1, synthesis-autopilot).

## Incidents and lessons behind the carried rules

- **The silent no-op edit.** A scripted `str.replace` did nothing after another
  agent rewrote the anchor, and the agent still reported "updated". Carried as
  binding rule 5.
- **Same-day staleness and field pooling.** Date comparison missed staleness
  within one day of many rounds, and pooling Phase with Last session let a
  fresh Phase hide a stale Last session (tests `real_defect_round_10_11_*`,
  `first_ordinal_is_identity_not_max`). Carried as binding rule 6 and the
  doctor's per-field check.
- **Three header-only advances.** The header moved while `Current State` kept
  routing agents to superseded work. Carried as body markers and the honest
  completion signal in [editing-and-archival.md](editing-and-archival.md#body-currency).
- **The `current` open-section word.** Including it flagged 140 of 294 items
  across 18 projects as unstamped obligations; it stays out of the item check.
- **The dormant-project noise.** 98% of `freshness-unverifiable` and 90% of
  `record-unreadable` findings were on dormant projects; the paired-suppression
  rule is in [context-doctor.md](context-doctor.md#lessons-built-into-it).
- **A scan of nothing printed "0 findings".** Pointed at a subdirectory on
  2026-08-24, the currency checker exited 0; the v5 doctor exits 2 when it
  audits nothing.

## The 1.22.0 SKILL.md

Verbatim from `skills/synthesis-context-lifecycle/SKILL.md` at 1.22.0. Links inside point where they pointed then.

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

# Context Lifecycle Management

## The Problem

AI collaborators start every session with zero context. Their effectiveness depends entirely on the quality of the context they receive. For short-lived projects (2-3 sessions), a single context file works. For long-running projects spanning weeks or months, that file grows unboundedly — combining four types of information with fundamentally different lifecycles:

| Information type | Access pattern | Growth pattern | Ideal treatment |
|-----------------|----------------|----------------|-----------------|
| **Working memory** (current state, active tasks) | Every session | Constant | Keep lean, refresh often |
| **Episodic memory** (session logs) | Rarely after 1 week | Unbounded append | Archive monthly |
| **Semantic memory** (stable facts, reference) | Most sessions | Slow, update-in-place | Separate file |
| **Completed work records** | Almost never | Unbounded append | Delete after archiving |

Combining all four in one file means the file grows linearly with session count, with no mechanism for information to leave. This is the classic **hot/warm/cold data problem** from database engineering, manifesting in AI context management.

---

## The Architecture

Read [the complete protocol](references/context-protocol-details.md#the-architecture) before work in this area. Its requirements remain mandatory.

## Session Start Protocol — MANDATORY before substantive project work

The tiered architecture (CONTEXT.md / REFERENCE.md / sessions/) is only useful if the agent reads it. LLMs default to working from in-context memory; rules at session start lose salience as conversation grows. The Session Start Protocol makes the read explicit and non-skippable.

When you begin substantive work on any project — at client session start, when
the user first mentions it, or after switching from another project — run these
steps in order before substantive action. First resolve this conversation's
established project through its Git-tracked registry with the installed
project-management resolver, `--no-fetch --no-coordination-refresh` and
`GIT_OPTIONAL_LOCKS=0`; no automatic fast-forward. A global pointer cannot
override the conversation's project. CONFLICT/FAIL/UNKNOWN stops dependent
project reads and writes, including generated-state build and migration.

1. **Verify current time.** Run `date "+%Y-%m-%d %H:%M:%S %Z (%A)"`. The model has no clock; the OS does. Use the output as your authoritative "today" anchor for the rest of the session. The harness may have injected a date earlier, but that injection drifts; `date` does not.
2. **Inspect Git publication and working state.** Run `git log -10 --pretty=format:"%h %ai %ci %s" -- <project-path>` and `git status --short -- <project-path>`. These establish commit author/committer times and pending changes. Commit times do not define session workdays; delayed publication, overnight work and timezone boundaries may put them on different dates.
3. **Read CONTEXT.md.** Read the full working-memory file. Treat its "Last session" header as a claim to compare with dated session records and current source evidence. A commit-date difference alone does not make it stale, and matching dates alone do not establish semantic currency.
4. **Read the latest dated entries in sessions/YYYY-MM.md.** Locate the newest recorded workday across the archive, not just the file's final heading. Compare the narrative with CONTEXT.md, structured state where present, and index metadata. Report older or newer cache dates with both sources; recover missing, invalid or unreadable evidence without inventing a session date from Git. When archiving older work, retain its verified workday and label the current recording time separately. A repair done today may have its own entry; it must not rewrite the earlier workday to match its commit.
5. **Skim REFERENCE.md if you have not recently.** This is the project's stable facts and design spec. Full read on the first session resumption of the day; quick skim of section headers otherwise.
6. **Name this session after the project where the client allows it.** When the client exposes session/thread renaming, set this conversation's own title to the project's id (e.g. `synthesis-ecosystem-engineering`) so the thread list reads as the work queue. Claude Code: MCP tool `mcp__ccd_session_mgmt__set_session_title` with `{session_id: "self", title: "<project-id>"}` (verified 2026-09-21; a user-set title asks approval first, auto-generated titles replace silently). No verified equivalent on other clients as of that date — check yours and apply the same convention if one exists; if not, this step does not apply.
7. **Only then begin substantive work.**

When `synthesis-agent-conformance` is available and this session has an accepted
owner claim, record the local active-project pointer after verification.
Report-only refreshes and contributors do not activate the canonical pointer:

```bash
python3 <skill-root>/scripts/conformance.py activate \
  --project <project-directory> --session-id <coordination-session-id>
```

The pointer accelerates SessionStart and PostCompact recovery. It is a cache;
the project files and git history remain authoritative.

### Seamless client and computer switching

Rajiv never has to run this protocol or save state manually. The working agent
owns the checkpoint before it yields. A normal stopped-task transition is:

1. the agent updates `CONTEXT.md`, stable `REFERENCE.md` facts, the current
   session log, and the controlling plan as the work changes;
2. the client adapter records the exact context paths changed by that session;
3. Stop hashes the attributed files into a local receipt without committing or
   using the network; an interruption before Stop leaves the manifest plus Git
   working-tree state as `LOCAL_RECOVERABLE` evidence;
4. an explicit remote handoff or day-end publishes source work under repository
   policy and batches exact private-context paths before the destination
   computer fast-forwards; and
5. when Rajiv names the project, the receiving client resolves it through the
   git-tracked `projects/index.yaml` and runs this Session Start Protocol
   automatically.

A valid live pointer accelerates the same-client case. Its absence after claim
release is normal and must not block recovery from the durable record. A single
global durable "current project" marker is prohibited because independent
Claude Code and Codex tasks may own different projects simultaneously.

The guarantee has explicit boundaries: do not switch while a task is still
running; an offline origin can preserve a local checkpoint but cannot make it
available on another computer; divergence, a behind checkout, missing
authentication, and overlapping claims must surface visibly instead of being
called seamless.

**Why this order matters.** Steps 1 and 2 establish ground truth from external sources (OS clock, git). Step 3 reads the cache. Step 4 reads the most recent narrative. The order means by the time you act, you have verified facts AND the project's own framing — and you have noticed any discrepancy between them.

**Visible to the user.** Show the verification step in your first response of the session. Example:

> Session start verified. Today: 2026-05-27 10:49 EDT (Wednesday). Last project commit: 2026-05-26 12:47 EDT (`51b8e6d`, "Maintain context: refresh inbox-cleanup CONTEXT.md"). CONTEXT.md matches git log. Proceeding with [next task].

The visible verification is the L4 cross-tool drift-detection mechanism — the user must be able to see that ground truth was checked.

---

## Mid-Session Refresh Protocol — MANDATORY under drift conditions

Long conversations cause context drift. The mid-session refresh protocol re-syncs the agent against ground truth without requiring a full restart.

**Mandatory triggers.** Re-run the Session Start Protocol (or invoke the `synthesis-checkpoint` skill, which is the codified version of these steps) under ANY of these conditions:

- **Before any time-interval claim in output.** "Yesterday", "N days ago", "last session", "this week", "earlier today" — verify the clock and the dated evidence for the event BEFORE generating the claim. Use `git log` for commit intervals; use session records for session dates, and do not infer an exact elapsed interval from a date-only entry. After-the-fact correction is more expensive than upfront verification.
- **After a long real-time pause.** If `date` reveals more than 1 hour has passed since you last checked, re-read CONTEXT.md and re-run `git log`. Long pauses correlate with the user resuming after a break — the world may have changed.
- **After ~25 substantive tool calls** since the last refresh. This is the unconditional cadence: even with no drift signal, re-read CONTEXT.md and `git log` to verify your accumulated context still matches disk.
- **On any drift signal:**
  - You say or think "I don't recall" about a recent decision
  - A file read returns content you didn't expect
  - The user references a decision you have no record of
  - The user corrects you ("that's not right", "actually...", "you said earlier...")
  - You notice the conversation has touched many topics and feel uncertain about project state
- **Before writing to a session-log file** (a markdown file under `sessions/`). The date you write into the header MUST be from `date`, not from memory.
- **Before generating a commit message that mentions dates or intervals.** The interval claim must be backed by `git log`.

**The protocol itself.** Run the steps from synthesis-checkpoint (preferred if loaded), or as a fallback the same steps inline:

1. `date "+%Y-%m-%d %H:%M:%S %Z (%A)"` — verify current time
2. `git log -10 --pretty=format:"%h %ai %s" -- <project-path>` — verify project history
3. Re-read CONTEXT.md from disk
4. Re-read the latest sessions/YYYY-MM.md entry
5. Reconcile: where does in-context memory disagree with disk/git? Report the discrepancy in the next response.
6. If CONTEXT.md is stale, update it and preserve session-attributed local evidence. Publish it during explicit remote handoff or day-end.

**Compaction detection signals.** Context-window compaction (the harness summarizing older turns) is opaque — you cannot reliably detect when it happened. Treat these as red flags suggesting compaction may have occurred:

- You suddenly cannot recall the user's stated goal for the session
- A task you remember as in-progress has unclear next steps
- Tool outputs reference files or decisions you have no context for
- Your last few tool calls feel disconnected from the current request

When any of these fire, run the Mid-Session Refresh Protocol unconditionally.

**Delegation.** When the `synthesis-checkpoint` skill is available, prefer invoking it — it is the canonical codification of this protocol, runs the same steps every time, and produces consistent visible output the user can spot. Use the inline fallback only when synthesis-checkpoint is not loaded.

---

## Editing a Durable Context File — MANDATORY for scripted edits

Scripted edits must use the public context editor and its budget/currency gates. Multi-file edits use apply-transaction with exact native/claim authority; interrupted intent must be reconciled through recover-transaction before further managed reads or writes. A journal never grants authority. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Decision and transfer succession

For material facts, rationale, constraints, temporary conditions or changed
instructions, follow [material context](references/material-context.md) before
dependent work, compaction or handoff. Capture the explicit input denominator,
then associate it through the existing editor. Pending capture, missing material,
unreachable records and unknown semantic or endpoint coverage remain distinct.
This applies to ordinary prose projects without autopilot or format enrollment.

Before retiring a decision interface or absorbing transferred ideas, read
[artifact succession](references/artifact-succession.md). Use the existing
`context_edit.py review-succession` and `apply-succession` owners. Exact
item accounting, evidence quality, principal answers and action authority
are separate axes. Unanswered and unverified historical items retain explicit
obligations. Archive bytes before changing live records; the existing record
transaction owns recovery. Never turn a transfer or archive into approval.

## The Archival Protocol

Archive before removing content from working memory; preserve decisions, outcomes, agent attribution and unresolved work in the correct durable tier. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Migration Guide

Apply the size-appropriate migration protocol only after registry-first recovery; preserve the original record and its authority boundaries. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Project Status Transitions

Apply the declared lifecycle definitions and update all corresponding records when transitioning a project. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Project Spawning

Use the project-spawning protocol and retain the originating relationship, goals, scope and handoff in durable records. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Repo Families and Deletion Units

Route relationship-bound content to its deletion unit and permanent personal material to its permanent root. The ALWAYS-PRESERVE class takes precedence; inventories count unselected content without itemizing it. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Measuring Context Quality

Use both quantitative bounds and qualitative recovery checks when judging context quality. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Executable Working State — resources/scripts/

Retain executable working state, exact inputs and reproducible scripts in durable project records; prose alone cannot replace recoverable execution evidence. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## The Context Doctor — verification, not diligence

`bounded` defaults to `true` when unset; `bounded: false` explicitly declares a
standing operational stream and changes the applicable closure remedy.
After reference sharding, the reference index has a 150-line budget and each
topic has a 300-line budget. Repair the named condition without dropping content
or changing a project's declared lifecycle to silence a diagnostic.

Use the context doctor and its documented remedies, including reference-budget, reference-shard, reference-index-budget, reference-topic-budget, reference-index-orphan, reference-index-missing, terminal-project-active, terminal-project-open-items and post-close-review-unresolvable. The index field post_close_reviewed_through names the reviewed commit; a new project commit re-arms review, and dirty/untracked evidence, changed index dates or archive gaps cannot inherit it. Coverage is a claim that needs its own verification: report every check’s examined/skipped denominator. Suppressing an inapplicable check is only safe when you add the check that becomes applicable in its place. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Context as Infrastructure

Treat context as maintained infrastructure with explicit ownership and verification. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Evolution Stages

Use the documented evolution stages and their evidence requirements before changing the architecture. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.

## Local Continuity and Remote Readiness Protocol

Distinguish LOCAL_READY from REMOTE_READY. Verify local recovery before switching clients and complete the explicit remote-readiness protocol before switching computers; never infer native acceptance from installed bytes. Read and apply this section's complete [operating protocol](references/durable-record-operations.md) before acting.


The context doctor reports `skill-outputs` for unverifiable active packet
pages. A rulings file's presence does not prove closure. Retired interfaces
require exact source custody, an explicit verified succession record, and
surviving obligations. Missing or changed custody fails; a changed live
destination is a separate review warning. A generated page without its filed
spec remains incomplete filing. No check grants action authority.


The complete [context protocol details](references/context-protocol-details.md)
remain mandatory for the corresponding lifecycle operations.


### Durable custody before a session ends

Long-lived worktrees, source copies, environments and sole recovery inputs must
live in the durable workspace, outside system temp roots and session scratchpads.
Keep bounded test fixtures separately identified and capture their evidence
before closure. Temporary retention is policy- and clock-dependent, never a
universal four-day guarantee. Follow PM's [durable placement and missing-work
protocol](../synthesis-project-management/references/parallel-agent-protocol.md#durable-work-placement-and-unexplained-loss).
A vanished `.git` link or tracked file is unresolved loss evidence; retain its
registration, refs and surviving files. It is not retirement, deletion authority,
or a reason to discard foreign claims.


## Native memory capture-buffer ingestion

Native memory remains ON. Synthesis records are authoritative; native memory is
untrusted capture data. Use the existing `context_edit.py memory-probe`,
`memory-ingest`, and `memory-clear-plan` commands; their structured outputs are
private records, not banner text. This source supports bounded observation and
shared ingestion. It does **not** claim a qualified native export or clear action.

Before export, select the actual machine, installed harness, explicit store and
coordination board. `memory-probe` reads the current board and skips any active
seat for that harness on that machine, including the current seat. An unknown
client identity is also pending. Stale active rows are not silently retired.
An unchanged complete ledger observation needs no model call; unchanged pending
work stays pending. Missing, moved, aliased, changing, oversized or unsupported
stores refuse instead of returning NOT_APPLICABLE. The format-agnostic directory
hash is bounded to 1,024 entries, 32 MiB total, 8 MiB per file, depth 16 and ten
seconds. A store exceeding these limits needs an explicit owner correction,
never truncation or a guessed empty export.

Only the harness may export its memories through its supported native mechanism.
Use the existing dispatch owner (Codex: `codex_dispatch.py`) only after native
capability qualification and a fresh inactive-harness check. Binary availability,
help text, directory contents and a synthetic packet do not prove export/clear
support. Do not invent a Muse memory surface. A proven native no-memory result
may be recorded separately as NOT_APPLICABLE; absent or unsupported capabilities
remain pending. The shared owner never invokes a harness or parses its store.

The bounded export packet has exactly `schema: 1`, `harness`, the exact `store`
probe result, and at most 64 `entries`. Each entry has only `id`, `text`,
`sha256` (UTF-8 text), `scope` (`personal`, `workspace`, `unknown`) and nullable
`workspace_hint`. Native output supplies no destination or routing authority.
Store bytes are rechecked before ingestion. These packets remain unverified
native provenance until separately qualified; a successful local transaction
cannot change that fact.

Read the exported material and canonical records in Synthesis before selecting
routes. Resolve any existing stub to its actual canonical file first; select that
file, rather than copying a stub's referent into a second location. The explicit
private selection contains `family` (`personal` or `workspace`), nullable
`workspace`, an existing project-relative `archive_dir`, and `routes`. Each route
contains one exact exported `id`, a reviewed `kind`, stable assertion `key`,
project-relative canonical `file`, and its unique insertion `anchor`. Resolve the
project/deletion-unit owner through the current registry before creating this
selection. This selection is a reviewed Synthesis decision, never native output.
No arbitrary public destination or public publication operation is provided.

Kinds `lesson`, `project-fact`, `workspace-fact`, `voice`, and `public-candidate`
are distinct. Select reusable lessons in the personal lessons root, project
facts in the owning REFERENCE, and voice material in the owning private skill;
workspace-private content stays in its exact workspace deletion unit. Unknown
ownership remains pending. ALWAYS-PRESERVE kinds `contract`, `pay-equity`,
`hiring-negotiation`, `termination`, `review-self`, `ip-assignment`, and
`dispute-evidence` require the personal private root even when the source has a
workspace hint. `public-candidate` remains a publication decision, never an
automatic public edit.

`memory-ingest --project … --packet … --selection … --store … --board …
--machine … --native-payload …` uses the existing authenticated PM transaction
owner. Archive creation is ordered before canonical edits; source hashes, exact
claims and recovery custody remain enforced. Interrupted transactions use
`recover-transaction`, never a second ingestion replay. Exact existing text is
deduplicated. A previously recorded assertion key with different bytes remains
PENDING_CONTRADICTION; it never overwrites canonical text. Record all returned
pending identities and their private evidence pointers as decisions through the
existing ritual artifact/context transaction, before finishing the close. The
native source remains intact throughout. A dry run is not a local receipt.

After the ordinary guarded publication owner has published the selected exact
archive/canonical bytes, `memory-clear-plan` requires the local ingestion receipt,
packet, current store/board, exact native publication owner and receipt SHA-256.
It verifies required-file membership through `publication_receipt.observe`;
an unrelated, changed or incomplete publication receipt cannot qualify entries.
Only exact archived entries still present in their bound canonical files become
eligible. The result remains **PENDING_NATIVE_CAPABILITY** with
`native_clear: NOT_EXECUTED` and no dispatch. It is a non-executing plan, not a
clear receipt or permission to delete memory files. A future qualified own-harness
action must snapshot first, recheck active seats and exact source hashes, clear
only eligible unchanged entries, and supply its actual native result. Until that
boundary is proved, keep the ledger incomplete and the native memories intact.
Codex's requested-note update mechanism is not permission to edit/delete its
memory files or its database. No implementation may disable native memory to
avoid this boundary. Capability gaps block clean memory-sweep closure, not the
remaining day-end work.

### Canonical destination binding

The memory owner binds the actual checkout to one approved repository in the
owning workspace's existing `.agents/repos.yaml`, or to its exact pinned team
repository enrollment. A matching repository basename or remote slug grants no
authority. The configured full remote identity must match the single actual
origin; credentials, ambiguous origins and foreign physical clones refuse.
Real worktrees require reciprocal Git metadata and the declared repository's
same physical common directory. The authenticated owning project's workspace
must independently match the destination's declaration. An enrolled private
repository takes its deletion-unit ID from the team contract; that ID need not
match a naming alias. Shared enrollment cannot become a private memory source.
These local source checks do not attest remote privacy ACLs.

Each configured destination row must explicitly declare its memory scope. Names,
remote slugs and caller selection labels never supply this classification:

```yaml
repos:
  - name: journal-vault
    path: journal-vault
    remotes:
      origin: https://git.example/owner/journal-vault.git
    memory:
      family: personal
      workspace: null
      source: knowledge
```

The `memory` object has exactly these three keys. `family` is `personal` or
`workspace`; personal requires `workspace: null`, while workspace requires the
explicit engagement deletion-unit ID. `source` is `knowledge` or `private-skills`;
private-skills requires personal scope. The same row must already satisfy the
existing full-origin and physical-checkout checks. Unknown, extra or malformed
metadata refuses. An exact pinned private team enrollment supplies knowledge
scope and its deletion-unit ID when no workspace declaration exists; when both
exist, the configured scope must match that enrollment exactly. Shared enrollment
cannot supply private scope. Changing this metadata invalidates prepared and
recovering transaction authority until the original declaration is restored.

Transaction custody records configuration/enrollment hashes, physical identities
and a credential-free remote identity digest. It never stores the raw origin.
Declarations, checkouts and source identities are rebound before effects and
recovery; an intervening replacement or source change preserves unfinished
custody and refuses until the original authority is restored.

Pass the actual record root to `memory-ingest --project`: an existing registered
project, the actual knowledge repository's `lessons/`, or an existing
direct child skill directory with `SKILL.md` in the explicitly configured
personal private-skills source repository. Lessons
roots accept lesson routes; private-skill roots accept voice routes. For a
canonical root outside `projects/`, the existing transaction owner resolves one
registered owning project from the same active native seat's bounded workspace
list. That project stays subject to ordinary registry/native/worktree/branch
admission, and every canonical/archive/journal path needs its exact current
claim. The canonical root never masquerades as a registered project. Its physical
repository/origin/home identity is retained in transaction custody and rebound
before recovery. Ambiguous owning projects require an explicit owner correction.

Native export provenance and native clearing remain separately unqualified.
Neither a successful local edit nor an exact publication observation dispatches
clearing or attests a real native operation.
