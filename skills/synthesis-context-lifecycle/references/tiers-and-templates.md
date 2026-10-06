# The three tiers: what goes where, templates and attribution

The tiered context architecture in full: what each tier holds, its budget and
template, how a standing project shards its reference, how agents record
provenance, and how to judge a record's quality.

## Contents

- [The Problem](#the-problem)
- [Three tiers](#three-tiers)
- [CONTEXT.md — Working Memory](#contextmd--working-memory), including the current-state block
- [REFERENCE.md — Semantic Memory](#referencemd--semantic-memory)
- [Sharding the semantic tier — `reference/`](#sharding-the-semantic-tier--reference)
- [sessions/ — Episodic Archive](#sessions--episodic-archive)
- [Agent Attribution — recording which agent did what](#agent-attribution--recording-which-agent-did-what)
- [Measuring Context Quality](#measuring-context-quality)
- [Context as Infrastructure](#context-as-infrastructure)
- [Evolution Stages](#evolution-stages)

## The Problem

AI collaborators start every session with zero context. Their effectiveness depends entirely on the quality of the context they receive. For short-lived projects (2-3 sessions), a single context file works. For long-running projects spanning weeks or months, that file grows unboundedly — combining four types of information with fundamentally different lifecycles:

| Information type | Access pattern | Growth pattern | Ideal treatment |
|-----------------|----------------|----------------|-----------------|
| **Working memory** (current state, active tasks) | Every session | Constant | Keep lean, refresh often |
| **Episodic memory** (session logs) | Rarely after 1 week | Unbounded append | Archive monthly |
| **Semantic memory** (stable facts, reference) | Most sessions | Slow, update-in-place | Separate file |
| **Completed work records** | Almost never | Unbounded append | Delete after archiving |

Combining all four in one file means the file grows linearly with session count, with no mechanism for information to leave. This is the classic **hot/warm/cold data problem** from database engineering, manifesting in AI context management.

## Three tiers

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

## CONTEXT.md — Working Memory

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

For stable reference facts: see [REFERENCE.md](../REFERENCE.md)
For session history: see [sessions/](../sessions/)

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

*Completed project. For historical sessions, see [sessions/](../sessions/).*
```

**The current-state block.** The `synthesis` SessionStart hook re-injects the
active project's `PRIME-DIRECTIVE.md` and the part of CONTEXT.md between
`<!-- synthesis-current-state:start -->` and `<!-- synthesis-current-state:end -->`,
at session start and again after compaction (R1.2); without the markers it
re-injects the first 60 lines. Keep the block short and current: Phase,
Status, Last session, the one `**Plan:**` field (`none` when there is no
plan), and the next actions. One `Plan:` field only: two declarations are
reported as ambiguous, and links elsewhere in the file never count as the plan.

```markdown
<!-- synthesis-current-state:start -->
**Phase:** [Current phase]
**Status:** Active
**Last session:** YYYY-MM-DD
**Plan:** [plan](resources/artifacts/YYYY-MM-DD-plan.md)
**Next actions:**
- [The next step, specific enough to start without asking]
<!-- synthesis-current-state:end -->
```

## REFERENCE.md — Semantic Memory

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

## Sharding the semantic tier — `reference/`

The episodic tier solved unbounded growth years ago: `sessions/` is a directory, and no single file has to hold every session. The semantic tier never got that treatment. `REFERENCE.md` was a single file with a soft cap and **no overflow mechanism**, which is fine for a bounded arc whose scope really is limited, and structurally broken for a standing project whose whole function is accumulating operating knowledge.

`reference/` is the same move, one tier over.

**When to shard.** A bounded project should not: hitting 300 lines is real information about its scope. A standing project shards when one file stops being readable — in practice around the same 300 lines.

**What changes when you do.** `REFERENCE.md` stops being the content and becomes the **index over it**:

```markdown
# [Project] — Reference

Stable facts, sharded by topic. Each entry links one file in `reference/`.

| Topic | What lives there |
|---|---|
| [People and roles](../reference/people.md) | roster, reporting lines, who owns what |
| [Tooling and auth](../reference/tooling.md) | CLIs, credentials posture, known limitations |
| [Routing](../reference/routing.md) | what this seat owns and where work goes |
```

**Budgets after sharding.** The index is working-memory-shaped and held to **≤150 lines**; each `reference/<topic>.md` gets the old **≤300**. The scope signal moves from one line count to the *number of topics* — which is the honest measure for a standing project anyway.

**The invariant that keeps sharding safe:** every topic file is linked from the index. A topic nothing points at is unreachable from session start, which makes sharding a way to lose content rather than organise it. The v5 doctor checks only the index's line budget, so keeping every topic linked, and never leaving `reference/` without its index, is the writer's job.

**Migration is not required.** A project under the budget keeps one `REFERENCE.md` and nothing changes. `bounded` defaults to `true` when unset, so projects that never declare themselves standing behave exactly as before.

**What the doctor reports.** One check, `reference-budget` (a warning), on live projects only: REFERENCE.md over 300 lines, or over 150 once `reference/` exists. For a project declared `bounded: false` its remedy is to shard; for a bounded one, to split the project or move narrative into `sessions/`.

## sessions/ — Episodic Archive

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

## Agent Attribution — recording which agent did what

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
