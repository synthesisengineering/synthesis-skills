# Records and conventions — structure, formats, naming, and rationale

The durable-record layer: where project files live, what each holds, how
projects and lessons are named, and how agents record provenance.

## Contents

- [Problem this solves](#problem-this-solves)
- [Design principles](#design-principles)
- [Configuration](#configuration)
- [System architecture](#system-architecture)
- [Why not your tool's built-in memory?](#why-not-your-tools-built-in-memory)
- [Project naming — the full rationale](#project-naming--the-full-rationale)
- [index.yaml — full example](#indexyaml--full-example)
- [Tiered context](#tiered-context)
- [Lesson file formats](#lesson-file-formats)
- [Agent attribution — full rules](#agent-attribution--full-rules)

## Problem this solves

When working with AI assistants on multi-session projects:
- **Context compaction** (conversation summarization) loses detailed progress
- **Session boundaries** create information gaps
- **Tool switching** between Claude Code, Codex, Muse, and other agents can strand context in tool-specific transcripts
- **Multiple projects** create confusion about current state
- **Parallel root sessions** can edit the same repository without seeing each
  other's in-flight state
- **Lessons learned** get lost instead of compounding

This system provides persistent state that survives context loss. Project files are
the durable memory layer; chat history, model memory and compaction summaries are insufficient.
A user can pause in one capable agent environment and continue in another.

## Design principles

1. **Discoverability over documentation** — Agents can search/grep; humans need quick orientation. Prefer consistent naming conventions over maintained indexes.
2. **Convention over configuration** — Consistent structure means less cognitive load. When everything follows the same pattern, both humans and agents know where to look.
3. **Single source of truth** — No duplicate indexes to maintain. Files should be self-describing through front matter and naming conventions.
4. **Self-describing files** — Date prefixes, status in index.yaml, front matter metadata. No separate documentation that can get stale.
5. **Agents do the work** — Templates are obsolete. To create something new, examine an existing example and adapt it. Agents excel at this.
6. **Coordinate before concurrent writes** — Separate root sessions share the
   `synthesis` board outside the repositories they edit. Every session reads
   it, records its project and claims its write areas before editing.
7. **One context owner per project** — Parallel sessions may contribute to one
   project, but only one session writes canonical project context. Other
   sessions write isolated contribution artifacts for the owner to reconcile.

## Configuration

These values are user-specific. The `synthesis` CLI finds knowledge checkouts
through `knowledge_roots` in `~/.synthesis/v5/config.json`, else every
`~/workspaces/*/ai-knowledge-*`.

| Setting | Value | Description |
|---------|-------|-------------|
| `ai_knowledge_workspace` | `ai-knowledge-{workspace}` | Root directory for your ai-knowledge repo |
| `projects_path` | `projects/` | Directory within the workspace for all project folders |
| `index_file` | `projects/index.yaml` | Single index file for all projects |
| `lessons_path` | `lessons/` | Cross-project lessons and patterns directory |

## System architecture

All project management lives in one location within your ai-knowledge workspace:

```
ai-knowledge-{workspace}/
└── projects/
    ├── index.yaml               # Single index for ALL projects (status field, not folders)
    │
    ├── {project-id}/            # Project folders (flat structure)
    │   ├── PRIME-DIRECTIVE.md   # Optional: re-injected at session start and after compaction
    │   ├── CONTEXT.md           # Working memory — active state (budget: ≤150 lines)
    │   ├── REFERENCE.md         # Semantic memory — stable facts (updated in place)
    │   ├── sessions/            # Episodic memory — archived session logs
    │   │   └── YYYY-MM.md       #   Monthly files
    │   ├── README.md            # Static documentation (optional)
    │   └── resources/           # Project data and artifacts (optional)
    │       ├── in/              # Inputs
    │       ├── artifacts/       # Working data, plans, contributions
    │       ├── out/             # Outputs
    │       └── scripts/         # One-off scripts
    │
ai-knowledge-{workspace}/
└── lessons/                    # Cross-workspace lessons (top-level, no underscore, ADR-017)
    └── YYYY-MM-DD-*.md         # Date-prefixed for discoverability
```

Project records are written only in the canonical knowledge checkout, never in
a worktree of it: two checkouts each carrying their own copy of a project's
state is how a resume reads stale records (R1.6). `synthesis resume` warns when
a worktree or local branch holds a newer or diverged copy, and names where.

| Decision | Rationale |
|----------|-----------|
| **Flat project folders** | Status is in `index.yaml`, not folder names. No moving folders when status changes. |
| **`lessons/` at top level (no underscore)** | Lessons are a peer content domain to projects, not a sub-component. Top-level layout matches semantic equality (ADR-017). |
| **Three-tier context** | CONTEXT.md (working memory), REFERENCE.md (stable facts), sessions/ (history). See the synthesis-context-lifecycle skill. One plain-markdown format; there are no format versions to migrate. |
| **Date-prefixed lesson files** | Enables time-based discovery. `ls -t` shows recent. No index needed. |
| **No templates folder** | Agents examine existing examples and adapt. Templates are a pre-AI pattern. |
| **No patterns.md** | Patterns are lessons with `type: pattern` in front matter. One folder to search. |

## Why not your tool's built-in memory?

Several AI coding tools now ship a per-project memory feature that writes its
own notes as it works. It's genuinely useful within a single tool, on a single
machine, for a single session's worth of context. It is not a substitute for
this system, for three structural reasons:

- **Single-tool.** A memory file your tool writes for itself is invisible to
  every other agent you use. If you work across Claude Code, Codex, Muse, or
  others — even occasionally — that memory doesn't travel with you.
- **Single-machine.** These features are typically scoped to the machine they
  run on, with no built-in sync. Work on a second machine, and the memory
  starts over from zero.
- **Not version-controlled.** Without git, there's no history, no diff, no
  recovery from a bad write, and no way to review what got saved.

This system solves all three by being nothing more than files in a git
repository: `CONTEXT.md`, `REFERENCE.md`, `sessions/`, and `lessons/`,
readable and writable by any agent. Native memory stays enabled as a capture
buffer, never a record: the day-end ritual reviews it and moves what is durable
into the right repository and record, and synthesis records win any conflict.

## Project naming — the full rationale

Project `id` slugs are read every day — in the index, in directory paths, in
editor and window titles. Two rules, keyed to whether the project has a
defined end state:

**Bounded projects (ones that will someday reach `completed`) get verb-first
outcome names.** The name states the finish line: `migrate-blog-to-astro`,
`accept-vendor-contract-2026-03`, `release-kb-company-wide`. When the outcome
is in the name, "is this done?" answers itself, scope gets declared at
creation time, and zombie projects — bounded work that sits `active` in the
index for months because nothing in its name says what done means — become
visible on sight.

**Standing projects (`bounded: false` — operations seats, product
stewardships) keep noun names.** They name the thing being stewarded
(`payments-platform`, `workspace-operations`) because there is no finish line
to state. Time-boxed instances of a standing role (`platform-2026-q3`)
already carry their end in the date suffix; wrapping them in a generic verb
(`do-platform-2026-q3-work`) adds ceremony, not information.

**Generic verbs are banned.** `do-`, `work-on-`, `handle-`, `manage-`,
`run-`, `support-` say nothing — every project is doing work. The verb must
name the specific outcome. This makes the rule double as a classification
diagnostic: if no specific verb fits, the project is probably not bounded —
model it as standing, or split it until concrete outcomes emerge.

**Existing projects keep their names.** Renames churn paths,
cross-references, and history for no behavioral gain. The convention applies
to projects created after adoption; a mixed index is expected and harmless,
since `status` — not the name — remains the machine-readable lifecycle field.

## index.yaml — full example

`status` answers one question: does this project claim attention? It has four
values. Everything orthogonal is a qualifier field (`bounded`,
`superseded_by`, `wake_when`, `blocked_by`, `completed_date`), so the
vocabulary does not have to grow. Update the index when a project's status
changes or a project is added, under a claim on the file
([coordination.md](coordination.md#projectsindexyaml-has-many-writers)).

```yaml
# Projects Index
# Last updated: YYYY-MM-DD

# Status values:
#   active    - I intend to touch this within 30 days
#   paused    - Started but on hold (wake_when says what resumes it)
#   completed - Delivered what it promised (terminal; needs completed_date)
#   archived  - Closed without delivering, or superseded (terminal)
# Qualifier: bounded: false marks a standing project with no end state.

projects:
  - id: migrate-blog-to-astro        # bounded → verb-first outcome name
    name: Migrate Blog to Astro
    status: active
    description: Brief description of what this project accomplishes
    tags:
      - tag1
      - tag2
    last_session: YYYY-MM-DD

  - id: payments-platform            # standing stewardship → noun name
    name: Payments Platform
    status: active
    bounded: false
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

## Tiered context

Projects use a three-tier context system that separates information by
lifecycle. This prevents unbounded growth of context files and keeps AI
collaborators effective across long-running projects. Templates, archival and
the doctor live in the synthesis-context-lifecycle skill.

| Tier | File | Purpose | Budget | Update pattern |
|------|------|---------|--------|---------------|
| Working memory | CONTEXT.md | Current state, active tasks, recent sessions | ≤150 lines (hard) | Every session |
| Semantic memory | REFERENCE.md | Stable facts (team, URLs, architecture) | ≤300 lines (soft) | Updated in place when facts change |
| Episodic memory | sessions/YYYY-MM.md | Archived session logs | No budget | Append-only, monthly files |

**Archival:** at session start, if CONTEXT.md exceeds 120 lines, archive
completed tasks and old session logs to sessions/, move stable facts to
REFERENCE.md, verify content exists in the destination, then remove it from
CONTEXT.md. Archive FIRST, delete second.

## Lesson file formats

Cross-project mistakes, insights, and patterns go in one folder, the top-level
`lessons/`, immediately when you learn something reusable. File naming:
`YYYY-MM-DD-topic-slug.md`.

For incidents and mistakes:

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

For patterns (generalized insights):

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

## Agent attribution — full rules

When multiple agents contribute materially to a project — Claude Code, Codex,
Muse, subagents, or different model/effort settings — record provenance
where it helps future work. Git authorship alone cannot distinguish agents
(different tools commonly commit as the same human), so the session log
carries it: one italic line per contributing agent at the end of the entry in
`sessions/YYYY-MM.md`:

```
*Attribution — agent: Codex CLI · model: unknown · effort: unknown · scope: single-stack sweep only (session lacked the Gmail connector) · verified: plan re-run to zero · ref: d4e5f6a*
```

Rules: record `model`/`effort` only when the current session or the user
explicitly provides them — otherwise the literal word `unknown`, never
inferred (git `Co-Authored-By` trailers are claims, not verification).
`verified` names only checks that actually ran. Never record secrets,
OAuth/callback URLs, or private config values. CONTEXT.md gets at most a
short `(via Codex)`-style tag when agent identity changes interpretation;
REFERENCE.md carries only stable agent facts (e.g., a standing connector
gap), removed when no longer true. Attribute only when it helps future work —
this is provenance, not telemetry.

The canonical convention with field definitions and worked examples lives in
the synthesis-context-lifecycle skill, "Agent Attribution."
