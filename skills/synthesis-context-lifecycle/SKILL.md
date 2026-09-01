---
name: synthesis-context-lifecycle
description: "Three-tier context architecture for managing AI working memory across long-running projects. Use when asked to: manage context, project context, session management, context lifecycle, working memory, archival, archive sessions, context maintenance, garbage collection for context, tiered context."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.17.0"
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

### Three Tiers

```
project/
├── CONTEXT.md      # Working memory (budget: ≤150 lines)
├── REFERENCE.md    # Semantic memory (stable facts, update in place)
├── reference/      # Semantic memory, sharded — once one file is not enough
│   └── <topic>.md  # One topic per file; REFERENCE.md becomes its index
├── sessions/       # Episodic memory (archived session logs)
│   └── YYYY-MM.md  # Monthly files
└── [other files]   # Transcripts, artifacts, etc.
```

This maps to both cognitive science and systems engineering:

| Human memory | CPU cache | Synthesis equivalent | Properties |
|-------------|-----------|---------------------|------------|
| Working memory | L1 cache | CONTEXT.md | Small capacity, constantly refreshed, always loaded |
| Semantic memory | L2 cache | REFERENCE.md | Facts and relationships, updated in place, loaded on demand |
| Episodic memory | L3 cache | sessions/ | Chronological events, append-only, searched when needed |
| Procedural memory | Firmware | CLAUDE.md / AGENTS.md + lessons/ | How to do things, rules, patterns |

These are design principles, not metaphors. Each memory type has different storage, retrieval, and maintenance characteristics.

For cross-agent work, the project context files are the durable memory layer. Chat history, model memory, and compaction summaries may help within one tool, but they are not the source of truth. Claude Code, Codex, Cursor, or another capable agent should be able to resume from the same `CONTEXT.md`, `REFERENCE.md`, and `sessions/` archive.

### CONTEXT.md — Working Memory

**Purpose:** Everything the AI collaborator needs to be effective in THIS session.

**Budget:** ≤150 lines (hard). For completed projects: ≤80 lines.

**Contains ONLY:**
- Phase/status header (~5 lines)
- Current state (~15 lines)
- Active tasks with priorities (~50 lines)
- Recent session summaries — last 1-2 only (~30 lines)
- Links to REFERENCE.md and sessions/ (~5 lines)
- Budget footer (~2 lines)

**Does NOT contain:**
- Completed task checklists (archive to sessions/ first, verify, then remove)
- Session logs older than 1 week (move to sessions/)
- Stable reference facts (live in REFERENCE.md)
- Detailed historical narrative (live in session archive)
- Per-session agent provenance (attribution lines live in sessions/; at most a short `(via Codex)`-style tag in the status header when agent identity changes how to interpret state — see Agent Attribution)

**Template — new project:**

```markdown
# [Project Name] — Working Context

**Phase:** Initial
**Status:** [description]
**Last session:** YYYY-MM-DD

---

## Current State

[What exists, what doesn't, starting conditions]

## What's Next

1. [ ] [First task]
2. [ ] [Second task]

---

*This file follows the Tiered Context Architecture. Budget: ≤150 lines.*
```

**Template — mature project:**

```markdown
# [Project Name] — Working Context

**Phase:** [Current phase]
**Status:** [Active/Paused]
**Last session:** YYYY-MM-DD

For stable reference facts: see [REFERENCE.md](REFERENCE.md)
For session history: see [sessions/](sessions/)

---

## Current State

- **Production:** [version, deployment status]
- **Blockers:** [if any]

*State as of: YYYY-MM-DD (round N)*  ← as-of marker; see Editing below

## What's Next — Prioritized

**High:**
1. [ ] [Task with context]

**Medium:**
2. [ ] [Task]

**Deferred:**
3. [ ] [Task — reason for deferral]

## Recent Session: YYYY-MM-DD

[Summary: what was done, decisions made, outcomes]

---

*This file follows the Tiered Context Architecture. Budget: ≤150 lines.*
```

**Template — completed project:**

```markdown
# [Project Name] — Context

**Status:** Completed
**Completed:** YYYY-MM-DD
**Outcome:** [1-2 sentence summary]

---

## Summary

[What was built/accomplished, 5-10 lines]

## Key Decisions

[Notable decisions that might matter if revisited, 5-10 lines]

---

*Completed project. For historical sessions, see [sessions/](sessions/).*
```

### REFERENCE.md — Semantic Memory

**Purpose:** Stable facts that don't change session-to-session.

**Budget:** ≤300 lines (soft) for a **bounded** project. Exceeding it signals the scope may be too broad — the right response is usually to split the project or move narrative into `sessions/`.

**For a standing project, that reading is wrong**, and saying it anyway produces advice nobody can take. A project declared `bounded: false` in `index.yaml` — an operations seat, a standing stewardship — exists precisely to accumulate durable operating knowledge. Its reference has no natural ceiling, and "your scope is too broad" is not a defect report about a seat, it is a description of what a seat is. See **Sharding the semantic tier** below.

**Contains:**
- Project overview and goals (if not obvious from name)
- Team roster with roles
- URLs, repos, remotes, deployment configuration
- Architecture decisions and conventions
- File indexes (transcript logs, artifact locations)
- Setup and cleanup instructions

**Key property:** Update IN PLACE, not append. When a team member leaves, update the roster — do not add a dated note. When a URL changes, change the URL. This is a living reference document, not a log.

**Template:**

```markdown
# [Project Name] — Reference

Stable facts for this project. Updated in place when facts change.

---

## Quick Reference

| Resource | Location |
|----------|----------|
| [Key URL] | [value] |
| [Key command] | [value] |

## Team

| Name | Role | Notes |
|------|------|-------|
| [Name] | [Role] | [Status] |

## Architecture

[Key decisions, conventions, patterns]

## Related Files

[Index of transcripts, artifacts, external documents]
```

### Sharding the semantic tier — `reference/`

The episodic tier solved unbounded growth years ago: `sessions/` is a directory, and no single file has to hold every session. The semantic tier never got that treatment. `REFERENCE.md` was a single file with a soft cap and **no overflow mechanism**, which is fine for a bounded arc whose scope really is limited, and structurally broken for a standing project whose whole function is accumulating operating knowledge.

`reference/` is the same move, one tier over.

**When to shard.** A bounded project should not: hitting 300 lines is real information about its scope. A standing project shards when one file stops being readable — in practice around the same 300 lines.

**What changes when you do.** `REFERENCE.md` stops being the content and becomes the **index over it**:

```markdown
# [Project] — Reference

Stable facts, sharded by topic. Each entry links one file in `reference/`.

| Topic | What lives there |
|---|---|
| [People and roles](reference/people.md) | roster, reporting lines, who owns what |
| [Tooling and auth](reference/tooling.md) | CLIs, credentials posture, known limitations |
| [Routing](reference/routing.md) | what this seat owns and where work goes |
```

**Budgets after sharding.** The index is working-memory-shaped and held to **≤150 lines**; each `reference/<topic>.md` gets the old **≤300**. The scope signal moves from one line count to the *number of topics* — which is the honest measure for a standing project anyway.

**The invariant that keeps sharding safe:** every topic file is linked from the index. A topic nothing points at is unreachable from session start, which makes sharding a way to lose content rather than organise it. The doctor reports an unlinked topic (`reference-index-orphan`) and a `reference/` with no index at all (`reference-index-missing`, a defect).

**Migration is not required.** A project under the budget keeps one `REFERENCE.md` and nothing changes. `bounded` defaults to `true` when unset, so projects that never declare themselves standing behave exactly as before.

**The whole vocabulary, so a finding is a remedy and not just a string.** A report names the check that fired; a name absent from this skill leaves its reader nothing to do.

| Check | Fires when | Severity |
|---|---|---|
| `reference-budget` | a **bounded** project's `REFERENCE.md` is over 300 lines | warning |
| `reference-shard` | a **standing** project's `REFERENCE.md` is over 300 lines — outgrown one file, not overbroad in scope | warning |
| `reference-index-budget` | once sharded, `REFERENCE.md` is over 150 lines — the index has started holding content again | warning |
| `reference-topic-budget` | a `reference/<topic>.md` is over 300 lines | warning |
| `reference-index-orphan` | a topic file is not linked from the index | warning |
| `reference-index-missing` | `reference/` exists with no `REFERENCE.md` index at all | defect |

### sessions/ — Episodic Archive

**Purpose:** Historical record of what happened and when. Rarely read, but searchable when historical context is needed.

**Organization:** Monthly files named `YYYY-MM.md`.

**Template:**

```markdown
# Session Archive — [Month] [Year]

Archived from CONTEXT.md on YYYY-MM-DD. See REFERENCE.md for stable project facts.

---

### YYYY-MM-DD: [Session title — what was accomplished]

[Summary: 5-15 lines per session. What was done, decisions made, outcomes.]

*Attribution — agent: … · model: … · effort: … · scope: … · verified: … · ref: …*  ← optional; see Agent Attribution
```

### Agent Attribution — recording which agent did what

Multiple agents can write to the same project files — Claude Code, Codex, Cursor, subagents, or the same tool at different model/effort settings — and git authorship often cannot distinguish them: different tools commonly commit under the same human author identity, and `Co-Authored-By` trailers are authored claims, not harness-verified facts. When agent provenance would help future work, record it explicitly.

**When to attribute.** Only when it helps future work: cross-agent handoffs; sessions where an agent's tool or capability gap shaped the scope; multi-model or subagent contributions; work whose verification status a future reader must trust or re-check. Routine sessions in a single-agent project need no attribution line. This is provenance, not telemetry — never log every edit, and never let attribution bloat CONTEXT.md.

**Format.** One italic line at the end of the session entry in `sessions/YYYY-MM.md`, one line per materially-contributing agent:

```
*Attribution — agent: <app/tool> · model: <version string or unknown> · effort: <setting or unknown> · scope: <what this agent did> · verified: <checks actually run, or none> · ref: <commit hash / artifact path or unknown>*
```

Field rules:

- **agent** — the app or tool: `Claude Code`, `Codex CLI`, `Cursor`, `Claude Code subagent (Explore)`.
- **model** — the exact model/version string, ONLY if the current session or the user explicitly provides it (e.g., the session's own environment states it). Otherwise the literal word `unknown`.
- **effort** — reasoning-effort or mode setting (`max`, `high`, `default`) when explicitly known; otherwise `unknown`.
- **scope** — what this agent contributed to this entry, one clause.
- **verified** — the verification actually performed (`plan re-run to zero`, `tests green`, `none`). Never claim a check that did not run.
- **ref** — durable pointer: commit hash or `resources/artifacts/` path; `unknown` if none exists yet.

**Unknown means unknown.** Never infer model/effort from memory, prior sessions, vibes, or git trailers. A wrong provenance claim is worse than an explicit `unknown`.

**Never record secrets.** No token values, OAuth or callback URLs, credential material, or private config values in any attribution field.

**Placement by tier:**

- `sessions/YYYY-MM.md` — the home for attribution lines (episodic, append-only).
- `CONTEXT.md` — at most a short parenthetical tag — `(via Codex)` — in the status/Last-session line, and only when agent identity changes how to interpret state. Never full attribution lines.
- `REFERENCE.md` — no per-session provenance. Stable agent facts only (e.g., "Codex sessions lack the Gmail connector; scope sweeps accordingly"), updated in place and removed when no longer true.
- `resources/artifacts/` — a substantial standalone artifact MAY open with a short Provenance block (agent / model / effort / date / verification / commit) when it will outlive its session entry.

**Cache-vs-truth still applies.** An attribution line is a claim recorded at write time by the writing agent. When provenance matters downstream, re-verify against `git log` and the artifact itself rather than trusting the line.

**Examples.**

Routine single-agent session (line optional; include once a project becomes multi-agent):

```
*Attribution — agent: Claude Code · model: claude-fable-5 · effort: unknown · scope: full sweep + session log · verified: plan re-run to zero · ref: a1b2c3d*
```

Cross-agent handoff (each agent's entry carries its own line; a capability gap that shaped scope belongs in `scope`):

```
*Attribution — agent: Codex CLI · model: unknown · effort: unknown · scope: single-stack sweep only (session lacked the Gmail connector) · verified: plan re-run to zero · ref: d4e5f6a*
```

Multi-model / subagent work (one line per contributor under the orchestrating entry):

```
*Attribution — agent: Claude Code · model: claude-fable-5 · effort: max · scope: orchestration + final review · verified: acceptance audit of subagent output · ref: b7c8d9e*
*Attribution — agent: Claude Code subagent (Explore) · model: unknown · effort: unknown · scope: repo-wide call-site inventory · verified: none (inventory only) · ref: resources/artifacts/2026-07-05-call-sites.md*
```

---

## Session Start Protocol — MANDATORY before substantive project work

The tiered architecture (CONTEXT.md / REFERENCE.md / sessions/) is only useful if the agent reads it. LLMs default to working from in-context memory; rules at session start lose salience as conversation grows. The Session Start Protocol makes the read explicit and non-skippable.

When you begin substantive work on any project — at client session start, when
the user first mentions it, or after switching from another project — run these
steps in order before substantive action:

1. **Verify current time.** Run `date "+%Y-%m-%d %H:%M:%S %Z (%A)"`. The model has no clock; the OS does. Use the output as your authoritative "today" anchor for the rest of the session. The harness may have injected a date earlier, but that injection drifts; `date` does not.
2. **Verify project history from git.** Run `git log -10 --pretty=format:"%h %ai %s" -- <project-path>`. The output is the source of truth for "what happened when in this project." Note the most recent commit's timestamp and subject.
3. **Read CONTEXT.md.** This is the project's working memory. Read the full file. Note the "Last session" header but treat it as a cache — compare it to step 2's git output. If CONTEXT.md is older than the most recent commit, the file is stale and needs an update before the session ends.
4. **Read the latest entry in sessions/YYYY-MM.md.** This is the most recent narrative of what was done. Read at minimum the last session entry (the bottom of the file). If your session-start verification revealed CONTEXT.md was stale, also read any entries between CONTEXT.md's claimed "last session" and the current most-recent commit.
5. **Skim REFERENCE.md if you have not recently.** This is the project's stable facts and design spec. Full read on the first session resumption of the day; quick skim of section headers otherwise.
6. **Only then begin substantive work.**

When `synthesis-agent-conformance` is available, record the local
active-project pointer after verification:

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

- **Before any time-interval claim in output.** "Yesterday", "N days ago", "last session", "this week", "earlier today" — verify with `date` and `git log` BEFORE generating the claim. After-the-fact correction is more expensive than upfront verification.
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

A scripted edit to `CONTEXT.md`, `REFERENCE.md`, or a session log is an
assertion that a specific change was made. A bare `str.replace()` asserts
nothing: when an anchor no longer matches — because another agent legitimately
rewrote that region between sessions — the replacement silently becomes a
no-op while the surrounding "updated" message stays cheerful and false. The
result is committed, and record-versus-git checks still pass, because the file
is committed. It is simply not current.

**Never hand-roll replacement logic against a durable context file.** Use
`scripts/context_edit.py`, which fails closed:

```bash
python3 scripts/context_edit.py set-field --file CONTEXT.md \
  --field Phase --value "Round 3 complete"

python3 scripts/context_edit.py replace --file CONTEXT.md \
  --anchor "$OLD" --replacement "$NEW" [--count N] [--max-lines 150]

python3 scripts/context_edit.py insert-before --file sessions/2026-08.md \
  --anchor "## 2026-08-20" --text "$NEW_ENTRY"
```

It refuses, without writing, when the anchor is absent, when it matches a
different number of times than declared, when the replacement would leave the
file byte-identical, when the result would exceed a stated line budget, or when
the target is a symlink. It writes atomically and then re-reads the file to
confirm the change is actually on disk. There is no flag that makes a missing
anchor succeed. `--dry-run` previews without writing and still refuses a bad
anchor. Import `replace_once` or `set_field` to use it from Python.

The helper also refuses to *create* a stale header: an edit that leaves
`**Phase:**` ahead of `**Last session:**` in the same ordinal family (round,
wave, phase, step, part) is refused with both fields named —
`--allow-header-lag` records an explicit override. Update `Last session`
first or in the same change; it may lead `Phase` mid-update. Independently,
the context doctor fails a project whose header describes an older state than
its own session log (`header-currency`), including same-day staleness where
date comparison sees nothing. Each field is judged separately, so a fresh
`Phase` cannot mask a stale `Last session`.

**Body currency.** Header freshness is necessary, not sufficient: three
real defects advanced the header while `Current State` kept routing agents to
superseded work — and a current header above stale operational sections is a
*stronger* false receipt than an obviously stale file. Operational sections
(`## Current State`, `## What's Next`) therefore end with an as-of marker:

```markdown
*State as of: 2026-08-24 (round 14)*
```

The marker converts prose currency into the structured comparison the header
already gets. With it in place: the doctor fails a section whose marker lags
the session log (`body-currency`); `context_edit.py` refuses a header advance
that leaves a marker behind (`--allow-stale-body` records an override); and
advancing a marker while its section's prose is byte-identical requires
`--state-reviewed`, which records the assertion that the section was re-read
and still holds — a silent bump would recreate the header defect one level
down. Markerless records are reported as *unverifiable*, never as clean.

The completion signal is deliberately honest: every gated edit's success line
names the body state (`as-of markers current`, `body lags`, or `body currency
unverifiable`). A tool that mechanizes the easy half of a task and prints
unqualified success for it manufactures a completion signal for partial work
— that mechanism-shaped failure caused all three real occurrences, and the
signal is the part of this design that addresses it.

Two companion rules, because the tool cannot enforce them alone:

- **Re-read before editing.** When re-taking a claim on a project another
  agent may have touched, read the current file and build anchors from what it
  says now — never from strings you remember writing. Alternating agents on
  one `CONTEXT.md` is a standing pattern in cross-agent work, not an accident.
- **Never report success you did not verify.** A message saying a record was
  updated is a claim about your own action, and nothing else in the system
  checks it.

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
8. **Record local readiness.** The client edit hook attributes the changed files automatically. Commit and push during an explicit remote handoff or day-end, scoped to the exact files and repository policy.

**CRITICAL: Archive FIRST, then delete. NEVER delete content from CONTEXT.md before confirming it exists in sessions/ or REFERENCE.md. Two-phase commit: write to destination, verify, then remove from source.**

**ALSO CRITICAL: local continuity and remote readiness are different states.** Do not create a network commit after every context edit. Keep the local tiers current, and publish them through explicit remote handoff or day-end.

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

---

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

---

## Project Status Transitions

| Transition | CONTEXT.md Action | Other Actions |
|-----------|-------------------|---------------|
| active → completed | Rewrite as completion summary (≤80 lines) | Simplify REFERENCE.md |
| active → paused | Add "Paused State" header with reason | Archive session logs |
| paused → active | Remove "Paused State" header, refresh | Update last_session |
| completed → archived | Freeze all files | Set status in index.yaml |
| active → spawned | Remove spawned scope | Create new project |

---

## Project Spawning

When a sub-scope exceeds the parent project's boundaries:

1. Create new project directory
2. Seed CONTEXT.md with fresh working memory (not a copy)
3. Add to index.yaml with `related:` linking to parent
4. Remove spawned scope from parent's CONTEXT.md
5. Cross-reference both projects

**The test:** Would a new team member reading only the parent's CONTEXT.md be confused by the spawned work? If yes, spawn it.

---

## Repo Families and Deletion Units

The three tiers describe how a project's context is structured. One level up sits a different question: **which repository may a piece of context live in at all?** For anyone whose work spans multiple professional relationships — clients, employers, partnerships — the durable-memory layer divides into two families with fundamentally different lifecycles:

- **The permanent knowledge root.** The person's own long-lived knowledge base — their projects, lessons, daily plans, accumulated career record. It survives every professional relationship and is never deleted wholesale.
- **Per-engagement private repos.** Workspace-scoped context repositories created for one client, employer, or engagement. Each one is a **deletion unit**: if the counterparty exercises a delete-my-data request — at contract end, under a nondisclosure obligation, during offboarding — the repo is deleted or returned *as a unit*. The repo boundary is what makes the promise keepable. Design for that day from the first commit.

### The routing test

Before writing engagement-adjacent content into any repository, ask: **would this survive the relationship's end?**

- Material the counterparty could rightfully ask to have deleted — information they shared in confidence, their internal discussions, work products they own, context learned inside their walls — routes to the engagement repo, the deletion unit.
- The person's own permanent record routes to the permanent root.

The test is about the content's rightful owner and lifecycle, not about where the content happened to arrive or which window was open when it was learned.

### Both misplacement directions fail — asymmetrically

**Engagement material in the permanent root is a compliance failure.** When the deletion request comes, the misplaced material silently survives a deletion the person promised — or is legally bound — to perform. Nothing in the permanent root's lifecycle will ever remove it, and honoring the request now requires hunting down every stray copy, which is exactly the manual process repo-level deletion units exist to make unnecessary. The failure is against someone else, and it is discovered (if ever) by the counterparty.

**Permanent material in an engagement repo is self-inflicted loss.** When the deletion unit is deleted — correctly, on request — the person's own records are destroyed along with the counterparty's data: records they were entitled to keep and may one day need. Recovery is impossible precisely because the deletion was performed properly.

Neither direction is curable after deletion day. That is why routing happens at write time, not at cleanup time.

### The ALWAYS-PRESERVE class

Some records concern an engagement but belong to the person: they document the person's own side of the professional relationship, and a counterparty's delete-my-data request does not reach them. The generic class:

- contracts and signed agreements
- pay, equity, and benefits records
- hiring and negotiation correspondence
- termination and separation records
- performance reviews, given and received
- IP assignments and licensing grants
- evidence relevant to an actual or foreseeable dispute

ALWAYS-PRESERVE material routes to the permanent root **always** — even when it arrives through engagement channels, even mid-engagement, even when the surrounding conversation is otherwise engagement-confidential. A copy may exist inside the deletion unit for working convenience; the canonical record may never live *only* there, because the deletion unit's lifecycle would take it.

### Inventories count; they never itemize

When an inventory of one repository is produced for any audience beyond its owner — a deletion attestation, an offboarding report, a migration plan — items outside the inventory's scope are **counted, never itemized**. An identifier plus a descriptive title is already a disclosure of the item's existence and subject. "Four items out of scope for this inventory" conveys completeness; a filename-and-title listing of out-of-scope material leaks the very content the repo boundary protects.

### Instance specifics live in private configuration

This section is the mechanism. Which repositories are deletion units, which root is permanent, and any additions to the preserve class are facts about one person's setup — declared in that person's private agent instructions or configuration, never in this public skill. An agent applying the mechanism reads the instance declarations first, and asks rather than guesses when a repository's family is undeclared.

---

## Measuring Context Quality

### Quantitative

| Metric | Target |
|--------|--------|
| CONTEXT.md line count | ≤150 (active) / ≤80 (completed) |
| REFERENCE.md line count | ≤300 (bounded projects); standing projects shard into `reference/` |
| REFERENCE.md as index, once sharded | ≤150 |
| `reference/<topic>.md` line count | ≤300 each |
| Unlinked files in `reference/` | 0 |
| Stale session logs (>1 week old in CONTEXT.md) | 0 |
| Completed tasks remaining in CONTEXT.md | 0 |
| Budget footer present | Yes |

### Qualitative

After reading CONTEXT.md, the AI collaborator should be able to answer:
1. What is the current state of this project?
2. What should I work on next?
3. What was done in the last session?
4. Where do I find stable reference information?

If any question cannot be answered from CONTEXT.md alone (with a pointer to REFERENCE.md), the working memory is incomplete.

---

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

The context doctor reports `artifact-cites-missing-script` when a Markdown file
directly under `resources/artifacts/` cites a nonexistent, non-regular, escaped,
or symlink-traversing `resources/scripts/` target. That check establishes path
existence and portability at the citation boundary; it does not prove the
script is correct, the inputs are sufficient, or the regenerated conclusion is
valid. Those questions remain with the artifact's acceptance evidence and the
implementation-integrity review.

## The Context Doctor — verification, not diligence

Everything above describes what a well-maintained context layer looks like. None of it verifies that yours *is* one. That gap matters more than it first appears: the durable layer is what makes cross-agent, cross-machine resumption possible, so it is the foundation every other guarantee stands on — and until you can check it, its health is an assertion by the same agent that was supposed to maintain it.

Every other protective layer in the synthesis stack carries a health check. `synthesis-git-hooks` has `--doctor`. Conformance has its own suite. The context layer had none, which made it the one fail-open control in a stack built on fail-closed ones.

`scripts/context_doctor.py` closes that. It audits every project in every configured source and reports what would degrade a cold resumption:

```bash
python3 <skill>/scripts/context_doctor.py            # all sources from console.yaml
python3 <skill>/scripts/context_doctor.py --source ~/kb   # explicit source roots
python3 <skill>/scripts/context_doctor.py --project ~/kb/projects/alpha
python3 <skill>/scripts/context_doctor.py --json     # for consoles and rituals
python3 <skill>/scripts/context_doctor.py --quiet --readiness local
python3 <skill>/scripts/context_doctor.py --project ~/kb/projects/alpha --readiness remote
```

What it checks:

| Group | Checks |
|-------|--------|
| Tier structure | CONTEXT.md present; sessions/ once there is history to archive; REFERENCE.md once a project has accumulated stable facts |
| Budgets | CONTEXT.md ≤150 active / ≤80 completed; REFERENCE.md ≤300 (warning). A standing project (`bounded: false`) over budget is told to shard, not to narrow its scope |
| Semantic shard | once `reference/` exists: index ≤150, each topic ≤300, every topic linked from the index, and an index actually present (defect if not) |
| Cross-tier agreement | index.yaml status agrees with the CONTEXT.md header; completed projects carry `completed_date`; indexed projects have directories and vice versa |
| Freshness | index.yaml `last_session` and the CONTEXT.md header agree with real git history. Applies to live projects; for a terminal one the question inverts to whether it is still being worked |
| Durability | tier files are tracked by git; local mode reports recoverable uncommitted or ahead state as warnings; remote mode requires a clean upstream-current branch |
| Executable state | artifact citations to missing, non-regular, escaped, or symlink-traversing `resources/scripts/` targets warn; existence does not establish correctness |
| Disclosure | anything unverifiable is reported rather than skipped — unreadable status headers and freshness that cannot be established both surface as findings |

Exit codes follow the guard contract: `0` healthy, `1` defects found, `2` the doctor could not establish ground truth. The third is the important one — an unreadable source or a source outside git exits 2 rather than reporting health, because a check that cannot run must never look like a check that passed.

**The status vocabulary is enforced, not assumed** (v1.13.0). `status` answers
one question — does this project claim attention — with four values: `active`,
`paused`, `completed`, `archived`. Everything orthogonal is a qualifier field
(`bounded`, `superseded_by`, `wake_when`, `blocked_by`, `completed_date`), so the
vocabulary does not have to grow as new distinctions appear.

The `status-vocabulary` check reports an unrecognised status as a **defect** and
a retired one as a **warning** naming what it should become. This exists because
an unvalidated vocabulary is not a vocabulary: on a real corpus, `complete`
survived for months as a typo of `completed` and this tool *absorbed* it,
hardcoding it into the terminal set rather than rejecting it. Worse, `superseded`
was absent from that set while also not being a completion word to the header
parser, so five projects parsed as making no completion claim at all — they sat
permanently as `record-unreadable` and never received their cross-tier check. A
status the doctor does not recognise silently disables every check keyed off it,
which is the most expensive kind of quiet failure a health check can have.

**Nothing is skipped silently.** A check that cannot run reports that it could not run. When every recent commit touching a project is a repo-wide sweep, freshness is unverifiable and says so; when a CONTEXT.md has no parseable status header, the cross-check is reported as unavailable rather than passed. Silent skips are indistinguishable from clean results, and that is the property this tool exists to remove.

**A check must know when it does not apply** (v1.7.0). Several checks ask questions that only have meaning about work in progress: how fresh is this record, are its open items still current, is its status header parseable for a cross-check. Asked of a project that shipped in May, each is unanswerable *and* unactionable.

Measured on a 175-project corpus before this rule existed: **98%** of `freshness-unverifiable` and **90%** of `record-unreadable` were raised against dormant projects — completed, archived, or paused. They accounted for most of 193 warnings that nobody had acted on, and 193 unactioned warnings is the fail-open state the doctor exists to end. Applying the rule took the corpus from 193 warnings to 93 without weakening a single check that applies.

Two properties keep the suppression honest:

- **It errs toward live.** An unset or unrecognised status counts as active, because the records whose state cannot be read are the ones most likely to be wrong. Only an explicit dormant status suppresses.
- **It is paired with an inversion.** A project declared *completed* that is still receiving real session commits is a live record error, and `terminal-project-active` reports it. That question was invisible before — the old code asked only whether a terminal project's freshness could be verified, never whether its terminal claim was still true. On the same corpus it surfaced thirteen genuine stale records, the worst 194 days past its own completion date.

  The inversion anchors on `completed_date`. Closing a project is itself work — the archive pass, the trim to budget — and those commits land after its final *working* session by design; measured against `last_session` they read as "still being worked," which is the opposite of what they are. Two of this check's first nine findings were exactly that. It falls back to `last_session` only when `completed_date` is missing or unreadable, because a record too incomplete to anchor on is the one most likely to be wrong.

The general form, worth more than the fix: **suppressing an inapplicable check is only safe when you add the check that becomes applicable in its place.** Silence alone is indistinguishable from a guard that stopped working.

**A suppression must be answerable, and its answer must expire** (v1.8.0). `terminal-project-active` shipped in v1.7.0 with a remedy the system could not accept: "record why the commits are maintenance rather than work," and no field to record it in. Worse than unactionable — it was self-sustaining, because the commits that dispose of a project are themselves post-completion commits, so resolving the finding re-created it.

The acknowledgment is an index field, and index-side is a correctness requirement rather than a preference: the freshness walk is `git log -- <project_path>`, so a marker written inside the project would re-extend newest-commit by the act of writing it.

```yaml
post_close_reviewed_through: 3e79b38...   # carries the comparison
post_close_reviewed_on: '2026-08-31'          # human readability only
```

It names a commit, not a date. A date over-covers by up to a day, and two disposition commits minutes apart either side of a recorded date would see the second silently swallowed. A sha that no longer resolves raises `post-close-review-unresolvable` as a **defect** — an acknowledgment whose evidence has vanished fails loudly rather than continuing to assert a review of history that was rewritten. One new project commit re-arms the question, which is what keeps this an acknowledgment rather than a mute button.

**Every gated check reports its denominator** (v1.8.0). A check that finds nothing and a check that examined nothing are indistinguishable in a findings list, and so is a deliberate skip. The report now states both:

```
coverage  item-currency: examined 41, skipped 31 (31 dormant)
```

This is the general form of the pairing rule, and the cheaper half of it. v1.7.0 suppressed open-item checks on dormant projects and shipped **no paired check** — in the release whose headline principle forbids that, asserted in the changelog, in this file, and in the project record, and enforced by none of them. A printed `skipped 141` invites the question nobody asked. The pairing itself is `terminal-project-open-items`: a project claiming to be finished while still listing obligations it owes.

The general form, which covers both this and the case where a check simply reaches less than it appears to: **a guard's coverage is a claim that needs its own verification, separate from whether it passes.**

**Bulk commits are not sessions.** The freshness checks ignore any commit touching more than a few projects at once. A path migration or a repo-wide restructure touches every project and says nothing about when any one of them was worked; counting those as sessions makes every dormant project look stale. False alarms are not a cosmetic problem — a doctor that cries wolf gets ignored, and an ignored doctor is the fail-open state it was built to end.

**The report cache.** Every full-corpus run writes its JSON report to `$SYNTHESIS_HOME/context-doctor/last-report.json` (v1.2.0+), so fast surfaces — SessionStart hooks, console pages — can show the latest corpus state without paying for a fresh audit. Single-project runs never touch the cache: a one-project result must not masquerade as corpus state. Suppress with `--no-report-cache`.

**Enforcement posture.** Day-start and ordinary same-machine handoffs use `--readiness local`: structural defects still fail, while attributed uncommitted or ahead state is visible as a warning. Explicit cross-machine handoff and day-end use `--readiness remote` for every project worked and fail closed until its context is committed, pushed, and upstream-current. Corpus-wide findings remain report-only.

**Where it runs.** Day-start refreshes the corpus cache in local mode. Day-end and explicit remote handoff run per-project remote mode. SessionStart and Synthesis Console surface the cached result. The JSON output includes its readiness mode so a local pass cannot masquerade as remote readiness.

---

## Context as Infrastructure

In traditional engineering, code is managed as infrastructure — version control, CI/CD, testing, deployment. In synthesis engineering (human-AI collaborative development), there is a third infrastructure layer: **context infrastructure** — the structured information that enables an AI collaborator to be effective across sessions.

The three infrastructure layers:

1. **Code infrastructure** — git, CI/CD, deployment (solved by traditional engineering)
2. **Knowledge infrastructure** — lessons, runbooks, compiled knowledge bases (the organizational learning layer)
3. **Context infrastructure** — working memory, reference facts, session history (the novel contribution — no equivalent in traditional engineering because human engineers carry context in their heads)

---

## Evolution Stages

1. **Ad hoc** — Re-explain everything each session (most AI users today)
2. **Monolithic** — Single context file that grows forever (common early approach)
3. **Tiered** — Working memory + reference + archive with lifecycle management (this skill)
4. **Compiled** — Context automatically assembled from project state, code, and history (future vision)

Stage 3 is the 80/20 solution that makes long-running AI-assisted projects sustainable. Stage 4 is the long-term vision where context at session start is compiled from live project state rather than manually maintained.

---

## Local Continuity and Remote Readiness Protocol

Context is maintained continuously, but it is not published after every
prompt or response. The system exposes three honest states:

- **LOCAL_READY:** project tiers and working-tree edits are available on the
  shared local filesystem. PostToolUse records every repository edit in a
  client-session manifest; Stop adds an atomic content receipt when such edits
  exist. A clean task with no project-file edits needs no empty receipt. Claude
  Code and Codex can switch on the same machine without a commit or network
  call.
- **LOCAL_RECOVERABLE:** an interrupted task left its edit manifest but never
  reached Stop. The receiving client reads project files, Git status and diff,
  the controlling plan, and the manifest before continuing.
- **REMOTE_READY:** complete source-repository branch heads are clean and
  equal to their fetched upstreams;
  private project context has been committed and pushed in exact-path batches;
  pending manifests are retired; remote-mode context doctor and conformance
  pass.

### Automatic same-machine handoff

Before a natural pause, the agent updates CONTEXT.md, REFERENCE.md, the
current session log, plan artifacts, and index.yaml as the work requires. It
releases or narrows coordination claims. The hooks record local evidence.
Rajiv does not run a lifecycle command, save state manually, or wait for a
network commit before opening the project in the other client.

A new client resolves the named project from projects/index.yaml, reads the
durable tiers and linked plan, then treats Git status and diff as newer truth
than cached prose. If a task was interrupted, it reconstructs the incomplete
work from the attributed manifest and working tree rather than discarding it.

### Explicit cross-machine handoff

Before changing computers, invoke synthesis-mac-sync in remote-handoff mode.
That workflow checks coordination, refreshes project tiers, publishes source
repositories under their own branch and review policies, flushes exact private
context paths, runs the doctor and conformance in remote mode, and verifies
upstream equality. Day-end performs the same transition automatically.

On the destination computer, synchronize repositories first, verify no
divergence or overlapping lease, then resume through the normal Session Start
Protocol. Offline, behind, diverged, or policy-blocked state is not
REMOTE_READY and must be reported explicitly.

### Scope and index safety

Never run a workspace-wide commit over dirty files. Remote publication uses
only session-attributed context paths. Source repos follow their own branch,
review, and deployment policies. Before every commit, inspect status and the
staged index; do not include another session's paths. Never bypass hooks.

Use synthesis-repo-guard for local receipts and pending publication;
synthesis-agent-conformance `continuity --readiness local|remote` for the two
gates; and context_doctor with the matching readiness mode.
