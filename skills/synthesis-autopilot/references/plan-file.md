# The plan file

An autopilot run is one markdown plan file in the project, plus the checkpoints
(CONTEXT.md, the session log) and lessons it produces; nothing else (R6.1).

The plan file is the mode's survival mechanism. Chat context compacts; the plan file does not.

It is also the switch the turn-end check reads, so a few lines have fixed
spellings, described here.

## Contents

- [Where it lives](#where-it-lives)
- [Header lines](#header-lines): the lines before the first `##` heading, which the check reads
- [Status values](#status-values): what each status asks of the agent
- [Sections](#sections): the checklists and how evidence is written
- [Default standing checklist](#default-standing-checklist)
- [Template](#template): copy this to start a run
- [Cadence](#cadence)
- [Ownership and takeover](#ownership-and-takeover)

## Where it lives

`<project>/resources/artifacts/<date>-<task-slug>-autopilot-plan.md`, inside the
synthesis project the work belongs to (synthesis-project-management). If the work
has no project yet, create one through that skill first: every record and
artifact of a run lives in the project, never only in a harness's private store
or a scratchpad (R9.2).

Write the plan from the [template](#template), then engage it:

```sh
python3 -S "$HOME/.synthesis/v5/current/synthesis/autopilot.py" engage --plan <plan path>
```

Engage refuses a plan with no `- [ ]` items under `## Checklist`, none under
`## Completion criteria`, or no `Horizon:` line, and refuses a plan another live
session owns. Otherwise it claims the plan file on the coordination board (so
no other session can write or commit it), fills `Owner session:`, `Status:` and
`Engaged:` when they are empty, adds any missing standing-checklist items, and
points the turn-end check at the plan. Its output is shown in
[turn-end-check.md](turn-end-check.md#helper-commands).

## Header lines

One per line, `Name: value`, before the first `## ` heading. Bold markers are
allowed. A value written as `<placeholder>` counts as empty. Lines inside HTML
comments or fenced blocks are ignored everywhere in the file, so comments can
carry guidance.

| Line | Values | What reads it |
|---|---|---|
| `Status:` | `running`, `waiting`, `blocked`, `paused`, `done`, `incomplete — <reason>`, `cancelled — <reason>` | The turn-end check and `close` (see [Status values](#status-values)) |
| `Owner session:` | The harness's session id; `engage` fills it | The check acts only for the owning session; any other session is never blocked |
| `Engaged:` | ISO time with offset; `engage` fills it | The 60-minute grace for a continuation's first wake |
| `Horizon:` | `turn`, `sitting`, `overnight` or `days`, then "until <when>" | `overnight` and `days` require a continuation and a backstop |
| `Continuation:` | The mechanism that causes the next turn, with its job id, or `none: this sitting only` | Needed while waiting; must read `deleted <time>` (or `ended`, `stopped`) before close |
| `First wake:` | `not yet`, or the time the first wake was observed | A scheduled continuation counts once a first wake is recorded, or within 60 minutes of `Engaged:` |
| `Backstop:` | Scheduler job and `stop: <how to stop it>`, or `none (<why>)` for short horizons | Required for `overnight`/`days`; must read `deleted <time>` before close |
| `Waiting on:` | The external event and when it is due | Required while `Status: waiting` |
| `Silent after:` | Minutes (default 480, the board's eight-hour stale rule) | How long the plan may sit unchanged before another session may take it over |
| `Harness:` | `claude-code`, `codex` or `muse` | Information for whoever resumes the run |

## Status values

- **running**: work is in progress. At turn end the check asks for the next
  open checklist item unless a background task the harness reports (Claude
  Code's `background_tasks`) will wake the session.
- **waiting**: no item can advance until an external event (CI, a reply, a
  scheduled export). Requires `Waiting on:` and a continuation that will wake the
  session: one the harness reports (`session_crons`, `background_tasks`), or a
  recorded `Continuation:` whose first wake was observed or is still inside the
  60-minute grace. Overnight and longer horizons also need the backstop.
- **blocked**: every remaining path needs the principal (a fact only they know,
  a value trade-off, an approval, a credential). Each open blocker carries its
  own `alerted <time> (<outcome>)` note, and a blocker that says a capability is
  missing carries `probe: <command> -> <output>`.
- **paused**: the principal asked to pause. Write who asked and when after the
  word. Never the agent's own choice: using up a budget or a context window is
  not a pause.
- **done**: every checklist item and completion criterion checked with evidence,
  every standing item dispositioned, no open blocker, every file under
  `## Required evidence` present inside the project, and every scheduled job
  recorded as deleted.
- **incomplete — <reason>** and **cancelled — <reason>**: an honest close short
  of the goal. The reason is required, and scheduled jobs must still be deleted.
  Incomplete closure preserves the work and the reason; it cannot be presented as success.

## Sections

Checklists use `- [ ]` (open) and `- [x]` (done). Evidence or a waiver follows
` — ` (an em or en dash, or `--`) after the item text.

- **Checklist**: the deliverables in order, numbered. The check names the first
  open one in its continuation request, so write each as the next action.
- **Completion criteria**: what "done" means, each checked as
  `- [x] <criterion> — <command or observation and its result>`. A criterion
  checked without evidence is not met: missing evidence stays unknown, never a pass.
- **Required evidence**: one cited file per list item (a markdown link, a
  backticked path or a bare path). At a done close each must exist inside the
  project; a file in a scratch or temp folder, a missing file or a URL refuses the
  close. Ordinary links elsewhere in the plan, fenced examples and comments
  create no obligation.
- **Standing checklist**: the standing instructions as items,
  `- [x] <id>: <text> — <evidence>` or `- [ ] <id>: <text> — WAIVED: <reason>`.
  Items added mid-run need a disposition too.
- **Blockers**: `- [ ] <what blocks> — probe: <command> -> <output> — alerted <time> (<outcome>)`;
  check it, with how it was resolved, when it no longer blocks. An open blocker
  lets a turn end only while `Status: blocked`; while the run is running it is a
  record, not a way out of the work, and a done close refuses while one is open.
- **Questions for the principal**: only questions the principal alone can
  answer; `- [ ]` open, `- [x] <question> — <answer and date>` answered.
  `status --all` shows the open ones, so the principal sees them even when a
  harness pane is blank.
- **Cycle ledger**: one line per wake, appended with the `cycle` helper.
- **Mission, Principal outcome, Standing instructions, Constraints and decisions
  already made, Coordination, Proportionality, Cross-agent orchestration and
  round-trip budget, Budget, Decisions log, Sufficiency checkpoint**: as in the
  template; nothing reads them mechanically.

## Default standing checklist

`engage` adds these when missing, plus any items the principal's private config
lists under `autopilot.standing_checklist` (each `{"id": ..., "text": ...}`), so
nobody retypes standing instructions for each run:

| id | Item |
|---|---|
| `end-to-end` | Complete the work end to end: every item closed or the run closed honestly incomplete. |
| `framework-decisions` | Open important decisions go through the thinking framework, recorded with rationale. |
| `plan-current` | Plan re-read after any suspected compaction or wake, and updated at every phase boundary. |
| `project-files-current` | Project files (CONTEXT.md, session log) current at every phase boundary and at close. |
| `verify-before-done` | Verification before any completion claim: focused tests per change, full suites per phase. |
| `lessons-filed` | Durable lessons filed as work proceeds, not at the end. |
| `completion-report` | Completion report plus batched questions (a decision packet when complex) ready at close. |

Blog-material seeds are not a public default; a principal who wants them adds a
`blog-seeds` item in their private config. Deploy authority is never a
checklist item or a grant in any file: each deploy needs the principal's own
approval in the session (R3.2).

## Template

```markdown
# Autopilot plan: <mission in a few words>

Status: running
Owner session: <filled by engage>
Harness: <claude-code, codex or muse>
Engaged: <filled by engage>
Horizon: sitting <!-- turn, sitting, overnight or days, then "until <when>" -->
Continuation: none: this sitting only <!-- the mechanism and job id; references/continuation.md -->
First wake: not yet
Backstop: none (horizon is this sitting) <!-- overnight or days: scheduler job id — stop: <how to stop it> -->
Waiting on: <only while Status is waiting: the external event and when it is due>
Silent after: 480 <!-- minutes unchanged before another session may take the run over -->

## Mission
What "done" means, in the user's terms.

## Principal outcome
The artifact or system outcome the principal asked to ship. Reviewer
satisfaction and control construction are not substitutes.

## Standing instructions
The delegation contract (references/delegation.md), restated, so a
post-compaction re-read restores the mode, not just the task.

## Constraints and decisions already made
Everything the user has decided; never re-litigate these.

## Checklist
- [ ] 1. <first deliverable, written as the next action>
- [ ] 2. <next deliverable>

## Completion criteria
- [ ] <criterion> <!-- when checked: — <command or observation and its result> -->

## Required evidence
<!-- one file per line that the completion report or a ruling rests on, e.g. - [report](../evidence/report.md) -->

## Standing checklist
<!-- engage adds the default items; disposition each before close -->

## Blockers
<!-- - [ ] <what blocks> — probe: <command> -> <output> — alerted <time> (<outcome>) -->

## Questions for the principal
<!-- - [ ] <question only the principal can answer> -->

## Coordination
Session id, claimed paths, overlaps checked, and messages pending.

## Proportionality
Consequence being prevented, bounded review universe, justified control
depth, and why the planned review effort is proportionate.

## Cross-agent orchestration and round-trip budget
Counterpart sessions, direct dispatch path, provider-boundary exception if
one exists, allowed principal courier crossings, current count, and the
blocked-state alert threshold.

## Budget
Horizon; maximum cycles or wall-clock; the per-cycle value test; counters
updated each cycle. Stop conditions: goals met · blocker + alert ·
budget exhausted + alert.

## Cycle ledger

## Decisions log
Dated entries: decision, thinking-framework mode used, rationale.

## Sufficiency checkpoint
Established, open, risk of shipping now, and the principal's ruling.
```

## Cadence

**Cadence.** Re-read the plan file after any suspected compaction (it is the recovery seed — read it before anything else) and before every phase transition. Update it at every phase boundary: checklist state, decisions log, new batched questions. The standing-instructions section makes the file self-carrying: an agent that has lost the conversation can resume the mode from the file alone.

At engagement and at every phase boundary, also write the plan path and the next
open item into the project's CONTEXT.md current-state block. The session-start
hook re-injects that block after compaction, so the run's directive and next step
come back without anyone asking for them (R6.3, R1.2).

## Ownership and takeover

One session owns a plan: the one named on `Owner session:`, holding the board
claim on the plan file. Only the owner records cycles or closes. Another
session that needs the run messages the owner (`synthesis msg <owner> ...`).

When the plan has sat unchanged, and its owner has not touched the board, for
longer than `Silent after:` allows (eight hours by default), another session may
run `takeover --plan <path>`. Takeover releases the old owner's claim on the
plan, claims it, notifies the old owner on the board, rewrites `Owner session:`,
and logs the takeover in the cycle ledger. Deadlines, open items, blockers and
questions stay exactly as they were. A run whose backstop starts a fresh session
(a Claude Code desktop scheduled task) sets `Silent after:` to about twice the
backstop's interval, so the backstop can pick up a run whose owner died.
