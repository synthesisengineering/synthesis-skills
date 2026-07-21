---
name: synthesis-project-management
description: "Lightweight project management system designed for human-agent collaboration, optimized for context preservation across sessions. Use when asked to: project management, project setup, project tracking, synthesis project, manage project, set up project, project structure, session protocol."
license: "CC0-1.0"
depends_on: ["synthesis-context-lifecycle"]
metadata:
  author: "Rajiv Pant"
  version: "1.3.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Project Management System

A lightweight project management system designed for human-agent collaboration. Optimized for context preservation across conversation sessions and context compaction events.

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

---

## Problem This Solves

When working with AI assistants on multi-session projects:
- **Context compaction** (conversation summarization) loses detailed progress
- **Session boundaries** create information gaps
- **Tool switching** between Claude Code, Codex, Cursor, and other agents can strand context in tool-specific transcripts
- **Multiple projects** create confusion about current state
- **Lessons learned** get lost instead of compounding

This system provides persistent state that survives context loss.

The project files are the durable memory layer. Treat chat history, model memory, and compaction summaries as helpful but insufficient. A user should be able to pause in one capable agent environment, open the same project in another, read the project context, and continue.

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

Project `id` slugs are read every day — in the index, in directory paths, in editor and window titles. Two rules, keyed to whether the project has a defined end state:

**Bounded projects (ones that will someday reach `completed`) get verb-first outcome names.** The name states the finish line: `migrate-blog-to-astro`, `accept-vendor-contract-2026-03`, `release-kb-company-wide`. When the outcome is in the name, "is this done?" answers itself, scope gets declared at creation time, and zombie projects — bounded work that sits `active` in the index for months because nothing in its name says what done means — become visible on sight.

**Ongoing projects (`ongoing` status — operations seats, product stewardships) keep noun names.** They name the thing being stewarded (`payments-platform`, `workspace-operations`) because there is no finish line to state. Time-boxed instances of a standing role (`platform-2026-q3`) already carry their end in the date suffix; wrapping them in a generic verb (`do-platform-2026-q3-work`) adds ceremony, not information.

**Generic verbs are banned.** `do-`, `work-on-`, `handle-`, `manage-`, `run-`, `support-` say nothing — every project is doing work. The verb must name the specific outcome. This makes the rule double as a classification diagnostic: if no specific verb fits, the project is probably not bounded — model it as `ongoing`, or split it until concrete outcomes emerge.

**Existing projects keep their names.** Renames churn paths, cross-references, and history for no behavioral gain. The convention applies to projects created after adoption; a mixed index is expected and harmless, since `status` — not the name — remains the machine-readable lifecycle field.

---

## Components

### 1. Project Index (`index.yaml`)

Single source of truth for all projects. Status is a field, not a folder.

```yaml
# Projects Index
# Last updated: YYYY-MM-DD

# Status values:
#   active    - Currently being worked on
#   paused    - Started but on hold
#   ongoing   - Continuous/maintenance work, no defined end state
#   completed - Has defined deliverables that are done
#   archived  - Old/obsolete, kept for reference only

projects:
  - id: migrate-blog-to-astro        # bounded → verb-first outcome name (see Project Naming)
    name: Migrate Blog to Astro
    status: active
    description: Brief description of what this project accomplishes
    tags:
      - tag1
      - tag2
    last_session: YYYY-MM-DD

  - id: payments-platform            # ongoing stewardship → noun name
    name: Payments Platform
    status: ongoing
    description: Standing stewardship of the thing being maintained
    tags:
      - tag1
    last_session: YYYY-MM-DD

  - id: launch-newsletter
    name: Launch Newsletter
    status: completed
    completed_date: YYYY-MM-DD
    description: What was accomplished
    tags:
      - tag1
    outcome: success
    key_result: Brief summary of what was delivered
```

**Update when:** Session end (update `last_session`), project status changes, new project added.

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

Cross-project mistakes, insights, and patterns. All in one folder with date prefixes.

**File naming:** `YYYY-MM-DD-topic-slug.md`

**For incidents/mistakes:**
```markdown
---
type: incident
title: Brief Title
severity: minor | moderate | serious | critical
---

# {Topic}: {Brief Title}

## What Happened
## Root Cause
## Impact
## Lesson
## Prevention
```

**For patterns (generalized insights):**
```markdown
---
type: pattern
title: Pattern Name
---

# {Pattern Name}

## Context
## Problem
## Solution
## Examples
```

**Update when:** Immediately when you learn something reusable.

### 4. Agent Attribution

When multiple agents contribute materially to a project — Claude Code, Codex, Cursor, subagents, or different model/effort settings — record provenance where it helps future work. Git authorship alone cannot distinguish agents (different tools commonly commit as the same human), so the session log carries it: one italic line per contributing agent at the end of the entry in `sessions/YYYY-MM.md`:

```
*Attribution — agent: Codex CLI · model: unknown · effort: unknown · scope: single-stack sweep only (session lacked the Gmail connector) · verified: plan re-run to zero · ref: d4e5f6a*
```

Rules: record `model`/`effort` only when the current session or the user explicitly provides them — otherwise the literal word `unknown`, never inferred (git `Co-Authored-By` trailers are claims, not verification). `verified` names only checks that actually ran. Never record secrets, OAuth/callback URLs, or private config values. CONTEXT.md gets at most a short `(via Codex)`-style tag when agent identity changes interpretation; REFERENCE.md carries only stable agent facts (e.g., a standing connector gap), removed when no longer true. Attribute only when it helps future work — this is provenance, not telemetry.

**Full convention with field definitions and examples:** the synthesis-context-lifecycle skill, "Agent Attribution."

---

## The Protocol

### During Work

```
Complete task → Update CONTEXT.md → Commit → Next task
```

**NOT:**
```
Complete task → Complete task → Complete task → (context compaction) → Lost details
```

### Session Start

1. **Read CONTEXT.md** — Understand current state before touching code
2. **Check line count** — If CONTEXT.md >150 lines, archive before starting work
3. **Read REFERENCE.md** — If it exists and the task needs reference details
4. **Search lessons/** — `grep` for relevant past experiences
5. **Check related projects** — Look at `related:` tags in index.yaml

### Session End

1. **Final CONTEXT.md update** — Ensure all sections current (≤150 lines)
2. **Archive if needed** — Move old sessions to sessions/, stable facts to REFERENCE.md
3. **Attribute if warranted** — If multiple agents/models contributed materially, end the session-log entry with Attribution line(s) (see Agent Attribution)
4. **Update index.yaml** — Set `last_session` date
5. **Commit all changes** — Do not leave uncommitted work

### Cross-Agent Handoff

Before pausing work that may continue in another tool:

1. Update `CONTEXT.md` with current state, decisions, and next actions
2. Move stable facts into `REFERENCE.md`
3. Append chronological detail to `sessions/YYYY-MM.md`
4. End the session-log entry with an Attribution line for the departing agent (see Agent Attribution) — the receiving agent should know who did what, with what verification
5. Save substantial plans, audits, or checklists under `resources/artifacts/`
6. Commit and push the project-management changes

When resuming work from another agent, trust the project files over tool-specific memory. The continuity source of truth is the synthesis project context, not the previous assistant's chat transcript.

### Parallel Sub-Agent Dispatch

Fan-out to multiple sub-agents working the same project concurrently — a batch of parallel repo migrations, a multi-agent reorganization run, several research tasks feeding one project — is now a common pattern, not an edge case. Two risks are specific to concurrent writers and aren't covered by the sequential protocols above.

**Git-index collisions.** When more than one agent (or background process) can commit to the same repo in the same window, `git add <your files>` followed by a bare `git commit` does not commit only what you just added — it commits everything currently staged, including anything another agent staged first. `git add` extends the index; it does not replace it. Before every commit in a repo where concurrent writers are plausible, run `git status --short` and `git diff --cached --name-only` first, and commit only the paths this invocation intends (`git commit -o <paths>`, or unstage what isn't yours). Treat this as a mechanical prefix to the commit step, not a judgment call reserved for commits that "feel risky" — the risk lives in what might already be staged, which by definition isn't visible without looking first. (General git-mechanics and repo-scoping rules live in synthesis-context-lifecycle's Commit Protocol; this is the one addition specific to concurrent writers in the same repo.)

**Tracking-doc aggregation.** A sub-agent dispatched against its own slice of a project — its own repo, its own batch — correctly leaves its siblings' in-flight work alone. That discipline has a side effect: no single agent sees the combined result. A shared tracking doc (CONTEXT.md, index.yaml) updated only by whichever agent happened to touch it last will under- or overstate what the batch actually accomplished. After any parallel dispatch, the orchestrator — not an individual sub-agent — reads every report as a set, reconciles them, and updates CONTEXT.md/index.yaml to reflect the true combined state.

---

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
3. If match found, read the project's `CONTEXT.md`
4. Summarize current state and next steps
5. **Re-verify scope before dispatching work, especially for a paused project.** CONTEXT.md's "N items remaining" (or any count a plan document asserts is current) is a claim made at write time, not a live query — it goes stale the moment anything else touches the same corpus, even a workstream that has nothing to do with this project and doesn't know it exists. Before batch-dispatching agents against a stated scope, re-derive it from live state with a cheap direct check (`find`, `grep`, `wc -l` against the actual files or repos) rather than trusting the document's count. This is cheapest immediately before dispatch — the highest-leverage moment to catch drift, before agent-hours are spent at the wrong scope — and it applies even within a single session, since a count computed early in a long run can go stale by the time a later phase acts on it. If the recount disagrees with the document, update the document in the same pass rather than silently working around the discrepancy. (Distinct from context-lifecycle's Session Start Protocol, which verifies CONTEXT.md's own freshness against this project's git log — that catches a stale *file*; this catches a stale *scope claim* that can drift even when the file itself looks current.)
6. Begin work from where it left off

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

---

## Why This Works

1. **Filesystem is persistent** — Survives context compaction
2. **Convention-based** — Same structure everywhere, easy to navigate
3. **Tiered by lifecycle** — Hot data in CONTEXT.md, warm in REFERENCE.md, cold in sessions/
4. **Budgeted** — 150-line cap prevents degradation over time
5. **Self-maintaining** — Archival protocol is garbage collection for context
6. **Searchable** — Agents grep, humans `ls -t`
7. **Scales** — Tested across 60+ projects over months of continuous use
