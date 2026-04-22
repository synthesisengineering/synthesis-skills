---
name: synthesis-project-management
description: "Lightweight project management system designed for human-agent collaboration, optimized for context preservation across sessions. Use when asked to: project management, project setup, project tracking, synthesis project, manage project, set up project, project structure, session protocol."
license: "CC0-1.0"
depends_on: ["synthesis-context-lifecycle"]
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/rajivpant/synthesis-skills"
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
- **Multiple projects** create confusion about current state
- **Lessons learned** get lost instead of compounding

This system provides persistent state that survives context loss.

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
  - id: my-project
    name: My Project Name
    status: active
    description: Brief description of what this project accomplishes
    tags:
      - tag1
      - tag2
    last_session: YYYY-MM-DD

  - id: finished-project
    name: Finished Project
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
3. **Update index.yaml** — Set `last_session` date
4. **Commit all changes** — Do not leave uncommitted work

---

## File Requirements by Project Status

| Status | CONTEXT.md | REFERENCE.md | sessions/ | CONTEXT.md budget |
|--------|------------|-------------|-----------|------------------|
| active | Required | When needed | When needed | ≤150 lines |
| paused | Required | When needed | When needed | ≤150 lines |
| ongoing | Required | When needed | When needed | ≤150 lines |
| completed | Required (summary) | Optional | Optional | ≤80 lines |
| archived | Frozen | Frozen | Frozen | N/A |

---

## Project Discovery

When a user mentions a project:

1. Read `projects/index.yaml`
2. Match user's phrase against project `name`, `description`, `id`, `tags`
3. If match found, read the project's `CONTEXT.md`
4. Summarize current state and next steps
5. Begin work from where it left off

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

---

## Why This Works

1. **Filesystem is persistent** — Survives context compaction
2. **Convention-based** — Same structure everywhere, easy to navigate
3. **Tiered by lifecycle** — Hot data in CONTEXT.md, warm in REFERENCE.md, cold in sessions/
4. **Budgeted** — 150-line cap prevents degradation over time
5. **Self-maintaining** — Archival protocol is garbage collection for context
6. **Searchable** — Agents grep, humans `ls -t`
7. **Scales** — Tested across 60+ projects over months of continuous use
