---
name: synthesis-context-lifecycle
description: "Three-tier context architecture for managing AI working memory across long-running projects. Use when asked to: manage context, project context, session management, context lifecycle, working memory, archival, archive sessions, context maintenance, garbage collection for context, tiered context."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.3.0"
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

**Budget:** ≤300 lines (soft). Exceeding 300 lines signals the project scope may be too broad.

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

When you (the AI agent) begin substantive work on any project — whether at the literal start of a Claude Code session, when the user first mentions a project in conversation, or when resuming a project after working on something else — run these steps in order BEFORE any other action:

1. **Verify current time.** Run `date "+%Y-%m-%d %H:%M:%S %Z (%A)"`. The model has no clock; the OS does. Use the output as your authoritative "today" anchor for the rest of the session. The harness may have injected a date earlier, but that injection drifts; `date` does not.
2. **Verify project history from git.** Run `git log -10 --pretty=format:"%h %ai %s" -- <project-path>`. The output is the source of truth for "what happened when in this project." Note the most recent commit's timestamp and subject.
3. **Read CONTEXT.md.** This is the project's working memory. Read the full file. Note the "Last session" header but treat it as a cache — compare it to step 2's git output. If CONTEXT.md is older than the most recent commit, the file is stale and needs an update before the session ends.
4. **Read the latest entry in sessions/YYYY-MM.md.** This is the most recent narrative of what was done. Read at minimum the last session entry (the bottom of the file). If your session-start verification revealed CONTEXT.md was stale, also read any entries between CONTEXT.md's claimed "last session" and the current most-recent commit.
5. **Skim REFERENCE.md if you have not recently.** This is the project's stable facts and design spec. Full read on the first session resumption of the day; quick skim of section headers otherwise.
6. **Only then begin substantive work.**

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
6. If CONTEXT.md is stale, update it. Commit and push the correction separately.

**Compaction detection signals.** Context-window compaction (the harness summarizing older turns) is opaque — you cannot reliably detect when it happened. Treat these as red flags suggesting compaction may have occurred:

- You suddenly cannot recall the user's stated goal for the session
- A task you remember as in-progress has unclear next steps
- Tool outputs reference files or decisions you have no context for
- Your last few tool calls feel disconnected from the current request

When any of these fire, run the Mid-Session Refresh Protocol unconditionally.

**Delegation.** When the `synthesis-checkpoint` skill is available, prefer invoking it — it is the canonical codification of this protocol, runs the same steps every time, and produces consistent visible output the user can spot. Use the inline fallback only when synthesis-checkpoint is not loaded.

---

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
8. **Commit AND push** with message: "Maintain context: archive sessions, extract reference facts". Stage only the files this invocation modified — do not `git add -A`. See the Commit Protocol section below for the full rule.

**CRITICAL: Archive FIRST, then delete. NEVER delete content from CONTEXT.md before confirming it exists in sessions/ or REFERENCE.md. Two-phase commit: write to destination, verify, then remove from source.**

**ALSO CRITICAL: Commit-and-push is part of this protocol, not an afterthought.** Every non-trivial context modification (archival or otherwise) must be committed and pushed in the same invocation. See the Commit Protocol section for scoping rules.

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

## Measuring Context Quality

### Quantitative

| Metric | Target |
|--------|--------|
| CONTEXT.md line count | ≤150 (active) / ≤80 (completed) |
| REFERENCE.md line count | ≤300 |
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

## Commit Protocol — Not Optional

Context files are only useful if they reach the remote repository. Every invocation that creates or modifies context files (CONTEXT.md, REFERENCE.md, session archives, daily plans, transcripts) must commit and push those changes before the invocation ends.

This is not deferred to "end of day" or "end of session." Treat it as part of the same action: if you wrote to a context file, you also commit and push it. Interactive sessions span multiple turns and may not have a clean "end" — so the commit must happen at the point of modification, not at some later checkpoint that may never arrive.

### Scope Rule: Only Commit Repos Touched in This Invocation

Never run workspace-wide commit or push operations. Only commit repos where this specific invocation created or modified files. If the user has other uncommitted work in unrelated repos (personal projects, other workspaces, unrelated branches), leave those alone — they belong to other sessions.

The pattern:
1. Track which files THIS invocation modified (the agent's own action history is the source of truth).
2. Group those files by containing repo.
3. For each containing repo: `git add` ONLY those specific files (never `git add -A` or `git add .`), commit, push.
4. Never touch repos where you did not create or modify files in this invocation.

### Why Point-of-Modification, Not Session-End

Context that exists only on one machine is invisible to the next session on a different machine. The entire point of structured context is cross-session continuity — uncommitted context breaks that guarantee.

Deferring commits to session-end has three failure modes:
1. **Session never ends cleanly.** Long-running conversations resume across days; a "session-end" hook may never fire.
2. **Modified ritual modes skip the day-end checklist.** Mid-day syncs, vacation/observer catch-ups, and partial rituals update context without running the full day-end sequence. If commit is only in day-end, these updates never ship.
3. **Multiple invocations compound uncommitted work.** By the time someone notices, there's a week of context changes stranded on one machine.

### Verification

Use `synthesis-repo-guard` as a detector across the workspace (reports dirty repos) but NEVER as a committer. The commit step must be explicit and per-repo-scoped to this invocation's actual changes. See `synthesis-repo-guard` for session-end hook integration — that hook should alert and surface dirty repos, not blanket-commit them.
