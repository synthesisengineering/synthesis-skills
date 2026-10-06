# Editing, archiving and changing a project's records

## Contents

- [Editing a durable context file](#editing-a-durable-context-file)
- [Header fields move together](#header-fields-move-together)
- [Body currency](#body-currency)
- [Stamped open items](#stamped-open-items)
- [The Archival Protocol](#the-archival-protocol)
- [Migration Guide](#migration-guide)
- [Project Status Transitions](#project-status-transitions)
- [Project Spawning](#project-spawning)
- [Executable Working State — resources/scripts/](#executable-working-state--resourcesscripts)

## Editing a durable context file

An edit to `CONTEXT.md`, `REFERENCE.md`, or a session log is an assertion that
a specific change was made. A bare `str.replace()` asserts nothing: when an
anchor no longer matches — because another agent legitimately rewrote that
region between sessions — the replacement silently becomes a no-op while the
surrounding "updated" message stays cheerful and false. The result is
committed, and record-versus-git checks still pass, because the file is
committed. It is simply not current.

**Never hand-roll replacement logic against a durable context file.** Use the
harness's own edit tool (Claude Code's Edit, Codex's apply_patch, Muse's
equivalent): each fails when its anchor is missing or matches more than once.
A script that edits records must do the same: refuse a missing or ambiguous
anchor, refuse an edit that changes nothing, write atomically, and read the
file back before saying it changed.

Keep Markdown tables whole: an edit must not leave a blank or non-row line
inside a table, drop its header or delimiter while keeping rows, or cross a
table boundary; replace or remove a whole table deliberately. Keep line endings
as they are. Archive durable facts before deleting them.

Two companion rules, because no tool can enforce them alone:

- **Re-read before editing.** When re-taking a claim on a project another
  agent may have touched, read the current file and build anchors from what it
  says now — never from strings you remember writing. Alternating agents on
  one `CONTEXT.md` is a standing pattern in cross-agent work, not an accident.
- **Never report success you did not verify.** A message saying a record was
  updated is a claim about your own action, and nothing else in the system
  checks it.

## Header fields move together

`**Phase:**` and `**Last session:**` describe one state. Update `Last session`
first or in the same edit; it may lead `Phase` mid-update, but `Phase` must
never move ahead of it in the same ordinal family (round, wave, phase, step,
part). The context doctor reports a project whose header describes an older
state than its own session log (`header-currency`), including same-day
staleness where date comparison sees nothing, and a `Phase` that moved while
`Last session` did not (`header-lag`). Each field is judged separately, so a
fresh `Phase` cannot mask a stale `Last session`, and the first ordinal in a
field is its identity ("round 11 — round 10 refuted" is round 11).

## Body currency

Header freshness is necessary, not sufficient: three
real defects advanced the header while `Current State` kept routing agents to
superseded work — and a current header above stale operational sections is a
*stronger* false receipt than an obviously stale file. Operational sections
(`## Current State`, `## What's Next`) therefore end with an as-of marker:

```markdown
*State as of: 2026-08-24 (round 14)*
```

The marker converts prose currency into the structured comparison the header
already gets. With it in place the doctor fails a section whose marker lags
the session log (`body-currency`). Advance a marker only after re-reading the
section and rewriting what changed: a marker bumped over unchanged, stale prose
would recreate the header defect one level down. Markerless ordinal-paced
records are reported as *unverifiable*, never as clean; a record whose current
state lives in the `synthesis-current-state` block is not asked for markers.

Report completion honestly: say whether you rewrote the operational sections
or only the header. A tool or agent that mechanizes the easy half of a task and
prints unqualified success for it manufactures a completion signal for partial
work — that mechanism-shaped failure caused all three real occurrences.

## Stamped open items

Open-items lists carry an implicit present tense nobody re-dates. Stamp each
live item when you write or re-check it:

```markdown
- [ ] Chase the feedback ask (as of 2026-08-10, review 7d)
```

The stamp makes the item's age travel with it, so appending stays safe and any
reader can compute overdue-ness without a ritual having run. The doctor warns
on live projects about an item past its horizon (14 days when none is given; an
explicit `0d` means daily), a live list with no stamps, and a stamp that does
not parse or names an impossible date. Checked items and narrative bullets are
not obligations. The day-end ritual reads these stamps; an item that passes its
date with no decision lapsed and goes in the lapse register.

## The Archival Protocol

### When to Archive

Archive when ANY of these conditions are true:
- CONTEXT.md exceeds 120 lines (approaching 150-line budget)
- Session logs in CONTEXT.md are older than 1 week
- A project phase transition occurs
- The user explicitly requests cleanup

### Step by Step

1. **Read** CONTEXT.md and count lines.
2. **Identify cold content:**
   - Completed task items
   - Session summaries older than 1 week
   - Stable facts that belong in REFERENCE.md
   - Detailed narratives that belong in sessions/
3. **Create files if needed:**
   - REFERENCE.md (if stable facts exist and no REFERENCE.md yet)
   - sessions/ directory
   - sessions/YYYY-MM.md for the relevant month
4. **Archive FIRST** (two-phase commit — write to destination before removing from source):
   - Session logs → sessions/YYYY-MM.md (append chronologically)
   - Stable facts → REFERENCE.md (organize by category)
   - Completed tasks → sessions/YYYY-MM.md (summarize, then remove from CONTEXT.md)
5. **Verify archives exist** — Confirm moved content is present in its destination file.
6. **Only then rewrite CONTEXT.md** with archived content removed.
7. **Verify:**
   - CONTEXT.md ≤150 lines
   - No information lost (everything archived before removal)
   - Cross-references updated (CONTEXT.md points to REFERENCE.md and sessions/)
8. **Leave it on disk.** The same Mac needs no commit. When the work moves to another Mac, or at day-end, `synthesis handoff` commits and pushes exactly the paths this session changed inside its claims.

**CRITICAL: Archive FIRST, then delete. NEVER delete content from CONTEXT.md before confirming it exists in sessions/ or REFERENCE.md. Two-phase commit: write to destination, verify, then remove from source.**

**ALSO CRITICAL: same-Mac continuity and another Mac's readiness are different states.** Do not create a network commit after every context edit. Keep the local tiers current, and publish them with `synthesis handoff` at a handoff or day-end.

### Decision Tree: Where Does This Content Belong?

```
Is this information needed for TODAY's work?
├── Yes → CONTEXT.md
└── No
    ├── Is it a stable fact (team, URL, architecture)?
    │   ├── Yes → REFERENCE.md (update in place)
    │   └── No
    │       ├── Is it a record of what happened during a session?
    │       │   ├── Yes → sessions/YYYY-MM.md
    │       │   └── No
    │       │       └── Is it a reusable lesson?
    │       │           ├── Yes → lessons/
    │       │           └── No → delete it
    └── Exception: completed milestones (≤10 lines) stay in CONTEXT.md
```

## Migration Guide

### For Projects Over 500 Lines

Full restructuring. Do NOT mechanically split — each project needs judgment about what is working memory vs reference vs archive.

1. Read the entire CONTEXT.md
2. Identify the four content types
3. Create REFERENCE.md with semantic content
4. Create sessions/ with episodic content (grouped by month)
5. Rewrite CONTEXT.md as fresh working memory
6. Verify nothing was lost

### For Projects 150-500 Lines

Moderate restructuring:
1. Extract obvious semantic content (team, URLs, architecture) → REFERENCE.md
2. Move session logs → sessions/
3. Tighten CONTEXT.md to ≤150 lines

### For Projects Under 150 Lines

Lightweight touch:
1. Add budget footer
2. If >20 lines of reference material exist, consider extracting to REFERENCE.md
3. If completed, simplify to completion summary format

## Project Status Transitions

| Transition | CONTEXT.md Action | Other Actions |
|-----------|-------------------|---------------|
| active → completed | Rewrite as completion summary (≤80 lines) | Simplify REFERENCE.md |
| active → paused | Add "Paused State" header with reason | Archive session logs |
| paused → active | Remove "Paused State" header, refresh | Update last_session |
| completed → archived | Freeze all files | Set status in index.yaml |
| active → spawned | Remove spawned scope | Create new project |

Every index change happens under a claim on `projects/index.yaml`, because
many sessions write that one file (synthesis-project-management,
coordination).

## Project Spawning

When a sub-scope exceeds the parent project's boundaries:

1. Create new project directory
2. Seed CONTEXT.md with fresh working memory (not a copy)
3. Add to index.yaml with `related:` linking to parent
4. Remove spawned scope from parent's CONTEXT.md
5. Cross-reference both projects

**The test:** Would a new team member reading only the parent's CONTEXT.md be confused by the spawned work? If yes, spawn it.

## Executable Working State — resources/scripts/

Durable prose is incomplete when its cited computation exists only in the
session that wrote it. If a script produces a number or conclusion cited in a
durable record, preserve the script and every required input before recording
the result. Put that executable working state under `resources/scripts/` and
cite its canonical, project-relative path from the artifact or session record.

Each preserved computation carries a `resources/scripts/README.md` that names:

- the script and its purpose;
- every input, dependency, and expected output;
- the regeneration order and exact invocation;
- whether each input is immutable, append-only, or intentionally refreshed;
- the success and failure exit behavior.

Portable means a cold resumer can run the script from repository state. A
script that depends on a session-temporary download, chat attachment, shell
variable, or scratchpad value is not preserved until that required state is
also stored at a project-relative path or documented as an independently
obtainable immutable input.

Before citing a script's result, check that the cited path exists and runs
from repository state: the v5 doctor does not check citations, and existence
never proves the script, its inputs or the conclusion correct. Those questions
stay with the artifact's acceptance evidence and the implementation-integrity
review.
