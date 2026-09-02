---
name: synthesis-project-management
description: "Lightweight project management system designed for human-agent collaboration, optimized for context preservation and cross-agent coordination across sessions. Use when asked to: project management, project setup, project tracking, synthesis project, manage project, set up project, project structure, session protocol, parallel root sessions, advisory locks, cross-agent coordination."
license: "CC0-1.0"
depends_on: ["synthesis-context-lifecycle"]
metadata:
  author: "Rajiv Pant"
  version: "2.11.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Project Management System

A lightweight project management system designed for human-agent collaboration. Optimized for context preservation across conversation sessions and context compaction events.

## v2.11.0 — One document, load-bearing; depth in references

Every operating rule stays here, inside the 500-line budget; examples and
rationale live in `references/`. Peer addressing (resolve, receipts, gated
lanes, delivered bus) is in full in [references/parallel-agent-protocol.md](references/parallel-agent-protocol.md).

## Configuration

These values are user-specific. Update them for your environment.

| Setting | Value | Description |
|---------|-------|-------------|
| `ai_knowledge_workspace` | `ai-knowledge-{workspace}` | Root directory for your ai-knowledge repo (e.g., `ai-knowledge-rajiv`) |
| `projects_path` | `projects/` | Directory within the workspace for all project folders |
| `index_file` | `projects/index.yaml` | Single index file for all projects |
| `lessons_path` | `lessons/` | Cross-project lessons and patterns directory |

---

## Design Principles

1. **Discoverability over documentation** — Agents can search/grep; humans need quick orientation. Prefer consistent naming conventions over maintained indexes.
2. **Convention over configuration** — Consistent structure means less cognitive load. When everything follows the same pattern, both humans and agents know where to look.
3. **Single source of truth** — No duplicate indexes to maintain. Files should be self-describing through front matter and naming conventions.
4. **Self-describing files** — Date prefixes, status in index.yaml, front matter metadata. No separate documentation that can get stale.
5. **Agents do the work** — Templates are obsolete. To create something new, examine an existing example and adapt it. Agents excel at this.
6. **Coordinate before concurrent writes** — Separate root sessions share a
   session registry and message board outside the repositories they edit. Every
   session reads it, registers its project, claims its write areas, and records
   its isolated worktree before editing.
7. **One context owner per project** — Parallel sessions may contribute to one
   project, but only one session writes canonical project context. Other
   sessions write isolated contribution artifacts for deterministic
   reconciliation.

---

## Problem This Solves

When working with AI assistants on multi-session projects:
- **Context compaction** (conversation summarization) loses detailed progress
- **Session boundaries** create information gaps
- **Tool switching** between Claude Code, Codex, Cursor, and other agents can strand context in tool-specific transcripts
- **Multiple projects** create confusion about current state
- **Parallel root sessions** can edit the same repository without seeing each
  other's in-flight state
- **Lessons learned** get lost instead of compounding

This system provides persistent state that survives context loss. The project
files are the durable memory layer: chat history, model memory, and compaction
summaries are helpful but insufficient. A user should be able to pause in one
capable agent environment, open the project in another, and continue. A
tool's built-in per-project memory is not a substitute — it is single-tool,
single-machine, and not version-controlled (full argument:
[references/records-and-conventions.md](references/records-and-conventions.md)).

---

## System Architecture

All project management lives in one location within your ai-knowledge workspace:

```
ai-knowledge-{workspace}/
└── projects/
    ├── index.yaml               # Single index for ALL projects (status field, not folders)
    │
    ├── {project-id}/            # Project folders (flat structure)
    │   ├── CONTEXT.md           # Working memory — active state (budget: ≤150 lines)
    │   ├── REFERENCE.md         # Semantic memory — stable facts (updated in place)
    │   ├── sessions/            # Episodic memory — archived session logs
    │   │   └── YYYY-MM.md       #   Monthly files
    │   ├── README.md            # Static documentation (optional)
    │   └── resources/           # Project data and artifacts (optional)
    │       ├── in/              # Inputs
    │       ├── artifacts/       # Working data
    │       ├── out/             # Outputs
    │       └── scripts/         # One-off scripts
    │
ai-knowledge-{workspace}/
└── lessons/                    # Cross-workspace lessons (top-level, no underscore, ADR-017)
    └── YYYY-MM-DD-*.md         # Date-prefixed for discoverability
```

### Key Structural Decisions

| Decision | Rationale |
|----------|-----------|
| **Flat project folders** | Status is in `index.yaml`, not folder names. No moving folders when status changes. |
| **`lessons/` at top level (no underscore)** | Lessons are a peer content domain to projects, not a sub-component. Top-level layout matches semantic equality (ADR-017). |
| **Three-tier context** | CONTEXT.md (working memory), REFERENCE.md (stable facts), sessions/ (history). See the synthesis-context-lifecycle skill. |
| **Date-prefixed lesson files** | Enables time-based discovery. `ls -t` shows recent. No index needed. |
| **No templates folder** | Agents examine existing examples and adapt. Templates are a pre-AI pattern. |
| **No patterns.md** | Patterns are lessons with `type: pattern` in front matter. One folder to search. |

---

## Project Naming

Two rules, keyed to whether the project has a defined end state:

- **Bounded projects** (ones that will someday reach `completed`) get
  **verb-first outcome names** stating the finish line:
  `migrate-blog-to-astro`, `release-kb-company-wide`. With the outcome in the
  name, "is this done?" answers itself and zombie projects show on sight.
- **Ongoing projects** (`ongoing` status — operations seats, stewardships)
  keep **noun names** for the thing being stewarded (`payments-platform`);
  there is no finish line to state.

**Generic verbs are banned** (`do-`, `work-on-`, `handle-`, `manage-`,
`run-`, `support-`): the verb must name the specific outcome, and when no
specific verb fits, the project is probably `ongoing` or needs splitting.
**Existing projects keep their names** — renames churn paths and history for
no behavioral gain; `status`, not the name, is the machine-readable field.
Full rationale:
[references/records-and-conventions.md](references/records-and-conventions.md).

---

## Components

### 1. Project Index (`index.yaml`)

Single source of truth for all projects. Status is a field, not a folder:
`active` (being worked), `paused`, `ongoing` (no defined end state),
`completed` (+ `completed_date`, `outcome`, `key_result`), `archived`.

```yaml
projects:
  - id: migrate-blog-to-astro        # bounded → verb-first outcome name
    name: Migrate Blog to Astro
    status: active
    description: Brief description of what this project accomplishes
    tags: [tag1, tag2]
    last_session: YYYY-MM-DD
```

Full multi-status example:
[references/records-and-conventions.md](references/records-and-conventions.md).
**Update when:** session end (update `last_session`), project status changes,
new project added.

### 2. Tiered Context Architecture

Projects use a three-tier context system that separates information by lifecycle. This prevents unbounded growth of context files and keeps AI collaborators effective across long-running projects.

**Detailed documentation:** See the synthesis-context-lifecycle skill for templates, migration guides, decision trees, and quality metrics.

**The three tiers:**

| Tier | File | Purpose | Budget | Update pattern |
|------|------|---------|--------|---------------|
| Working memory | CONTEXT.md | Current state, active tasks, recent sessions | ≤150 lines (hard) | Every session |
| Semantic memory | REFERENCE.md | Stable facts (team, URLs, architecture) | ≤300 lines (soft) | Updated in place when facts change |
| Episodic memory | sessions/YYYY-MM.md | Archived session logs | No budget | Append-only, monthly files |

**Archival protocol:** At session start, if CONTEXT.md exceeds 120 lines: archive completed tasks and old session logs to sessions/, move stable facts to REFERENCE.md, verify content exists in destination, then remove from CONTEXT.md. Archive FIRST, delete second — two-phase commit.

### 3. Lessons (`lessons/`)

Cross-project mistakes, insights, and patterns, one folder, date-prefixed
files (`YYYY-MM-DD-topic-slug.md`). Incidents carry `type: incident` front
matter with What Happened / Root Cause / Impact / Lesson / Prevention;
generalized insights carry `type: pattern` with Context / Problem / Solution
/ Examples. Full format blocks:
[references/records-and-conventions.md](references/records-and-conventions.md).
**Update when:** immediately when you learn something reusable.

### 4. Agent Attribution

When multiple agents contribute materially, the session log carries
provenance: one italic `*Attribution — agent: … · model: … · effort: … ·
scope: … · verified: … · ref: …*` line per contributing agent at the end of
the entry. Record `model`/`effort` only when explicitly provided — otherwise
the literal word `unknown`, never inferred; `verified` names only checks
that actually ran; never record secrets. Attribute only when it helps future
work. Full rules and the canonical convention:
[references/records-and-conventions.md](references/records-and-conventions.md)
and the synthesis-context-lifecycle skill.

---

## The Protocol

### During Work

```
Complete task → Update CONTEXT.md → local receipt → Next task
```

**NOT:** task → task → task → (context compaction) → lost details.

### Session Start

1. **Read the coordination board** — If
   `~/.synthesis/coordination/active-sessions.md` exists, read it before any
   write and register or refresh this session's project, worktree, branch,
   context role, and claims
2. **Read CONTEXT.md** — Understand current state before touching code
3. **Check line count** — If CONTEXT.md >150 lines, archive before starting work
4. **Read REFERENCE.md** — If it exists and the task needs reference details
5. **Search lessons/** — `grep` for relevant past experiences
6. **Check related projects** — Look at `related:` tags in index.yaml

### Session End

1. **Final CONTEXT.md update** — Ensure all sections current (≤150 lines)
2. **Archive if needed** — Move old sessions to sessions/, stable facts to REFERENCE.md
3. **Attribute if warranted** — If multiple agents/models contributed materially, end the session-log entry with Attribution line(s) (see Agent Attribution)
4. **Update index.yaml** — Set `last_session` date
5. **Verify local continuity** — Confirm session-attributed state is readable;
   do not create a commit or network push solely because the user is switching
   clients on this machine
6. **Release coordination claims** — Mark the session released or narrow its
   claims before pausing or ending

### Cross-Agent Session Coordination

Durable project files solve handoff across time; they do not prevent two live
root sessions from writing the same files at once. Concurrent Claude Code,
Codex, Cursor, or other root sessions share the coordination board at
`~/.synthesis/coordination/active-sessions.md` — outside any repository a
session may restructure. Schema v4 rows carry: canonical UUIDv7 plus compact
and speakable aliases (and any legacy mapping), agent, machine, the
client session ref (client-native delivery handle, registered automatically
at claim), project, start/heartbeat, mode, isolated worktree/branch pairs,
goal, claimed area globs, context role, and status; `## Messages` is the
append-only addressed bus, `## Protocol` the human-readable rules.

Use `scripts/coordination.py` for atomic, file-locked updates:

```bash
# Review claims that have gone quiet (reports only; never mutates)
python3 <synthesis-project-management-root>/scripts/coordination.py stale

# Read before writing
python3 <synthesis-project-management-root>/scripts/coordination.py status

# Claim one or more source areas
python3 <synthesis-project-management-root>/scripts/coordination.py claim \
  --agent "OpenAI Codex" --project example-project \
  --mode autonomous --context-role owner --goal "Cross-client conformance" \
  --workspace "/tmp/synthesis-skills-b @ feature/cross-client" \
  --area "synthesis-skills/**" --area "ai-knowledge-*/projects/**"

# Refresh the lease timestamp at every checkpoint
python3 <synthesis-project-management-root>/scripts/coordination.py heartbeat \
  --session s-6adk-06yc-yqb2

# Verify the current index against this session's exact board claim
python3 <synthesis-project-management-root>/scripts/coordination.py \
  check-staged --session s-6adk-06yc-yqb2 --repository /path/to/worktree

# Resolve a peer: exact address per lane + the receipt the send gate matches
python3 <synthesis-project-management-root>/scripts/coordination.py resolve \
  --to example-project --role owner

# This shell's identity, seat, and lanes; unread bus messages for its seat
python3 <synthesis-project-management-root>/scripts/coordination.py whoami
python3 <synthesis-project-management-root>/scripts/coordination.py inbox --mark-read

# Leave a handoff (--to must resolve; --free-address records exceptions)
printf '%s\n' "Source checks pass; live install awaits authorization." |
  python3 <synthesis-project-management-root>/scripts/coordination.py message \
    --from s-6adk-06yc-yqb2 --to crater-sunset-alone-okay-23907

# Release every claim at session end
python3 <synthesis-project-management-root>/scripts/coordination.py release \
  --session s-6adk-06yc-yqb2
```

`claim` allocates the identity and prints all three exact forms (UUID,
compact, speakable); any form selects the session, letters like `AX` are
migrated legacy aliases, and claims are the `--area` resource paths. Bit
layout and lookup contract:
[references/session-identity.md](references/session-identity.md).
Check-staged selector precedence and override recording:
[references/parallel-agent-protocol.md](references/parallel-agent-protocol.md)
("Commit authority").

Rules:

1. **Read at SessionStart and every synthesis checkpoint.**
2. **Claim before write.** Area globs describe source ownership, not merely the
   current file. Claim before creating a branch or editing. Name the synthesis
   project even when the session's claims span several repositories.
3. **Do not write through overlap.** If a claim conflicts, stop writes in that
   area and use the message log or the user to sequence work.
4. **Isolate git state.** Independent root sessions never write through the
   same worktree, index, or branch. Different projects may proceed in parallel
   only from isolated worktrees when they touch the same repository.
5. **One context owner.** A project has one `owner` session for `CONTEXT.md`,
   `REFERENCE.md`, `sessions/`, its controlling plan, and `projects/index.yaml`.
   Same-project `contributor` sessions claim non-overlapping implementation
   areas and write their result to a session-specific contribution artifact.
   The owner verifies and reconciles those artifacts into canonical context.
6. **Autonomous claim keeps priority.** When an autonomous and interactive
   session overlap, the autonomous session keeps its existing claim; the
   interactive session yields unless the user explicitly reorders them.
7. **Direct sends need a receipt; addresses are resolved, never guessed.**
   `resolve` issues a delivery receipt for one target; the plugin's gate
   admits a direct send only at that exact address, re-verified live. Names,
   titles, and `[ref]` labels are never addresses; the message carries your
   board id; the same text to a second peer is a refused broadcast. The bus
   reaches the addressed seat at its next prompt: unresolvable means bus.
8. **Heartbeat and release explicitly.** Refresh the heartbeat at checkpoints.
   A paused or completed session releases or narrows its claims. Stale `active`
   rows remain blocking until explicitly resolved; time alone never transfers
   ownership. Review them on a cadence — `coordination.py stale` surfaces
   quiet claims with physical evidence and prints the release command without
   ever running it; day-start is the natural place to catch them.
9. **Advisory does not mean optional.** The filesystem cannot stop every tool,
   so the protocol and checkpoint hooks make the shared obligation visible.

The script uses an OS file lock, verified backups, and atomic replacement,
and refuses overlapping areas, shared worktrees or branches, duplicate
context owners, and contributor claims on canonical context; mixed
absolute/relative spellings of one path still conflict. Cross-machine
simultaneity requires the git-backed lease (compare-and-swap on a shared
remote, fail-closed when unreachable); retire merged worktrees with
`scripts/retire_worktree.py`, never by hand. Board file shape:
[references/active-sessions-template.md](references/active-sessions-template.md).
Lease bootstrap and retirement, worktree-retirement mechanics, peer
addressing, digests, and administrative release:
[references/parallel-agent-protocol.md](references/parallel-agent-protocol.md).

### Cross-Agent Handoff

Before pausing work that may continue in another tool, the outgoing agent runs
this protocol automatically. The principal does not invoke lifecycle commands
or save state by hand:

1. Update `CONTEXT.md` with current state, decisions, and next actions
2. Move stable facts into `REFERENCE.md`
3. Append chronological detail to `sessions/YYYY-MM.md`
4. End the session-log entry with an Attribution line for the departing agent (see Agent Attribution) — the receiving agent should know who did what, with what verification
5. Save substantial plans, audits, or checklists under `resources/artifacts/`
6. Verify `LOCAL_READY` or `LOCAL_RECOVERABLE`; a same-machine client switch
   does not require a commit, push, or manual lifecycle command
7. If `synthesis-agent-conformance` is installed, run its `activate`,
   `pointer`, and `continuity --readiness local` commands for the project
8. When changing computers, run `synthesis-mac-sync` remote-handoff mode, then
   verify `continuity --readiness remote`. Day-end performs the same transition.
9. Release or transfer this session's coordination claims. A normal release
   recoverably archives an active-project pointer owned by that session; a
   pointer owned by another session is untouched.

Resuming from another agent: resolve the named project through the
git-tracked `projects/index.yaml`, read `CONTEXT.md` and the linked plan,
and inspect Git status and diff before acting — working-tree truth
supersedes cached project prose. Pointer semantics and cross-computer
recovery preconditions:
[references/parallel-agent-protocol.md](references/parallel-agent-protocol.md)
("Resuming and the active-project pointer").

### The Handoff Queue — Work Transfer Between Agents

The protocol above hands a project's *state* between tools. When two root
sessions collaborate on one project, the *work item* itself also needs a
transport that is not the principal's clipboard. `scripts/handoff.py` is that
transport:

```bash
handoff.py write --to codex --from claude --file prompt.md [--round N]
handoff.py read  --as codex          # oldest pending addressed to me
handoff.py list                      # full queue, both directions
handoff.py done  --id h-XXXXXXXXXX   # close a claimed handoff
```

Two rules keep this supervised:

- **Nothing self-triggers.** An agent reads the queue when the principal, or
  a coordination-board message the principal's protocol allows, says the
  other side is done. Announce every `write` with `coordination.py message`
  (the script prints the exact command). Supervision by exception is the
  point; unattended is not uncontrolled.
- **The queue is one of two directions.** It moves work *between agents*.
  Decisions *between agent and principal* travel as a decision packet
  (`synthesis-decision-packet`). Together they remove the principal as the
  transport layer while leaving every crossing visible in the project.

Payload integrity (sha256-pinned files, atomic queue writes, refuse-to-guess
reader identity):
[references/parallel-agent-protocol.md](references/parallel-agent-protocol.md)
("Handoff queue mechanics").

### Parallel Sub-Agent Dispatch

Fan-out to multiple sub-agents working the same project concurrently — a batch of parallel repo migrations, a multi-agent reorganization run, several research tasks feeding one project — is now a common pattern, not an edge case. Two risks are specific to concurrent writers and aren't covered by the sequential protocols above.

**Git-index collisions.** When more than one agent (or background process) can commit to the same repo in the same window, `git add <your files>` followed by a bare `git commit` does not commit only what you just added — it commits everything currently staged, including anything another agent staged first. `git add` extends the index; it does not replace it. Before every commit in a repo where concurrent writers are plausible, run `git status --short` and `git diff --cached --name-only` first, and commit only the paths this invocation intends (`git commit -o <paths>`, or unstage what isn't yours). Treat this as a mechanical prefix to the commit step, not a judgment call reserved for commits that "feel risky" — the risk lives in what might already be staged, which by definition isn't visible without looking first. (General git-mechanics and repo-scoping rules live in synthesis-context-lifecycle's Commit Protocol; this is the one addition specific to concurrent writers in the same repo.)

**Tracking-doc aggregation.** A sub-agent dispatched against its own slice of a project — its own repo, its own batch — correctly leaves its siblings' in-flight work alone. That discipline has a side effect: no single agent sees the combined result. A shared tracking doc (CONTEXT.md, index.yaml) updated only by whichever agent happened to touch it last will under- or overstate what the batch actually accomplished. After any parallel dispatch, the orchestrator — not an individual sub-agent — reads every report as a set, reconciles them, and updates CONTEXT.md/index.yaml to reflect the true combined state.

Sub-agents spawned by one orchestrator remain governed by that orchestrator.
Independent root sessions use the cross-agent coordination board above; do not
mistake a shared git worktree or shared chat history for coordination.

---

### Dispatching to Codex — use the wrapper, never bare `codex exec`

`scripts/codex_dispatch.py` is the supported path for sending a prompt to
Codex non-interactively:

```bash
python3 scripts/codex_dispatch.py --doctor
python3 scripts/codex_dispatch.py --prompt-file brief.md --out review.txt --report-only
```

It removes three production-observed failures: the silent stdin hang
(`stdin=DEVNULL` always), stalls indistinguishable from work (it watches
output growth, not elapsed time), and the false "Codex is unavailable"
(`--doctor` resolves the binary and proves authentication — never report
Codex unreachable without running it). Incident detail:
[references/codex-dispatch.md](references/codex-dispatch.md).

## File Requirements by Project Status

| Status | CONTEXT.md | REFERENCE.md | sessions/ | CONTEXT.md budget |
|--------|------------|-------------|-----------|------------------|
| active | Required | When needed | When needed | ≤150 lines |
| paused | Required | When needed | When needed | ≤150 lines |
| ongoing | Required | When needed | When needed | ≤150 lines |
| completed | Required (summary) | Optional | Optional | ≤80 lines |
| archived | Frozen | Frozen | Frozen | N/A |

Resuming a `paused` project carries the highest scope-drift risk of any status — see the scope re-verification step in Project Discovery below before dispatching work against one.

---

## Project Discovery

When a user mentions a project:

1. Read `projects/index.yaml`
2. Match user's phrase against project `name`, `description`, `id`, `tags`
3. **Check the match against the session's own context before switching.**
   A session usually carries project evidence of its own: the conversation's
   established project, the session name, the active-project pointer, the
   working directory. When the named project *contradicts* that evidence,
   surface the contradiction and ask ("This session has been working project
   Y — did you mean X, or should this stay in Y?"); never silently resolve
   to the name. Names are typed by humans navigating many similarly-named
   projects, so a name is one signal, not an override; a silent wrong
   resolution sends a full session's work to the wrong project's records
   (this happened on 2026-08-20). Resolve without asking only when name and
   session evidence agree, or when the session carries no project evidence
   at all.
4. If match found (and confirmed where step 3 required it), read the
   project's `CONTEXT.md`
5. Summarize current state and next steps
6. **Re-verify scope before dispatching work, especially for a paused project.** CONTEXT.md's "N items remaining" (or any count a plan document asserts is current) is a claim made at write time, not a live query — it goes stale the moment anything else touches the same corpus, even a workstream that has nothing to do with this project and doesn't know it exists. Before batch-dispatching agents against a stated scope, re-derive it from live state with a cheap direct check (`find`, `grep`, `wc -l` against the actual files or repos) rather than trusting the document's count. This is cheapest immediately before dispatch — the highest-leverage moment to catch drift, before agent-hours are spent at the wrong scope — and it applies even within a single session, since a count computed early in a long run can go stale by the time a later phase acts on it. If the recount disagrees with the document, update the document in the same pass rather than silently working around the discrepancy. (Distinct from context-lifecycle's Session Start Protocol, which verifies CONTEXT.md's own freshness against this project's git log — that catches a stale *file*; this catches a stale *scope claim* that can drift even when the file itself looks current.)
7. Begin work from where it left off

---

## Common Mistakes

| Mistake | Consequence | Prevention |
|---------|-------------|------------|
| Not updating CONTEXT.md | Lost progress after compaction | Update after EVERY task |
| Deferring updates to "session end" | Forget to update | Update immediately |
| Putting management files in project repos | Exposes internal process | Keep in ai-knowledge-{workspace} |
| Not checking lessons/ | Repeat mistakes | Grep at session start |
| Creating separate patterns.md | Duplicate, gets stale | Use `type: pattern` in lessons/ |
| Maintaining index files for lessons | Gets stale | Use date prefixes, `ls -t` |
| Trusting a paused project's stated remaining-scope count | Batch-dispatches the wrong amount of work — wastes agent-hours on already-done items, or silently leaves new items undone | Re-derive the count from live disk/repo state immediately before dispatch, even when the document looks current |
| Bare `git commit` in a repo where sub-agents dispatch concurrently | Sweeps another agent's staged work into your commit | `git status --short` / `git diff --cached --name-only` before every commit; commit only your own paths |
| Editing before reading or claiming the coordination board | Two root sessions overwrite or invalidate each other's work | Read at SessionStart/checkpoint; claim source-area globs before writes |
| Resolving a named project over the session's own contradicting context | A full session's work lands in the wrong project's records while the intended project's ask goes unfulfilled | When the name and the session's evidence disagree, ask a one-line clarifying question before switching (Project Discovery step 3) |

---

## Why This Works

1. **Filesystem is persistent** — Survives context compaction
2. **Convention-based** — Same structure everywhere, easy to navigate
3. **Tiered by lifecycle** — Hot data in CONTEXT.md, warm in REFERENCE.md, cold in sessions/
4. **Budgeted** — 150-line cap prevents degradation over time
5. **Self-maintaining** — Archival protocol is garbage collection for context
6. **Searchable** — Agents grep, humans `ls -t`
7. **Scales** — Tested across 60+ projects over months of continuous use
