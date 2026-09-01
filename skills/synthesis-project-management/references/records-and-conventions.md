# Records and conventions — formats, naming, and rationale

Detailed formats and the reasoning behind the durable-record layer. The
operating rules live in `SKILL.md`; this file carries the full versions.

## Why not your tool's built-in memory?

Several AI coding tools now ship a per-project memory feature that writes its
own notes as it works. It's genuinely useful within a single tool, on a single
machine, for a single session's worth of context. It is not a substitute for
this system, for three structural reasons:

- **Single-tool.** A memory file your tool writes for itself is invisible to
  every other agent you use. If you work across Claude Code, Codex, Cursor, or
  others — even occasionally — that memory doesn't travel with you.
- **Single-machine.** These features are typically scoped to the machine they
  run on, with no built-in sync. Work on a second machine, and the memory
  starts over from zero.
- **Not version-controlled.** Without git, there's no history, no diff, no
  recovery from a bad write, and no way to review what got saved.

This system solves all three by being nothing more than files in a git
repository: `CONTEXT.md`, `REFERENCE.md`, `sessions/`, and `lessons/`,
readable and writable by any agent that can read and write files. If your
tool's native memory feature can be redirected or disabled, doing so and
routing that content here instead avoids maintaining two parallel, drifting
memories of the same work.

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

**Ongoing projects (`ongoing` status — operations seats, product
stewardships) keep noun names.** They name the thing being stewarded
(`payments-platform`, `workspace-operations`) because there is no finish line
to state. Time-boxed instances of a standing role (`platform-2026-q3`)
already carry their end in the date suffix; wrapping them in a generic verb
(`do-platform-2026-q3-work`) adds ceremony, not information.

**Generic verbs are banned.** `do-`, `work-on-`, `handle-`, `manage-`,
`run-`, `support-` say nothing — every project is doing work. The verb must
name the specific outcome. This makes the rule double as a classification
diagnostic: if no specific verb fits, the project is probably not bounded —
model it as `ongoing`, or split it until concrete outcomes emerge.

**Existing projects keep their names.** Renames churn paths,
cross-references, and history for no behavioral gain. The convention applies
to projects created after adoption; a mixed index is expected and harmless,
since `status` — not the name — remains the machine-readable lifecycle field.

## index.yaml — full example

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
  - id: migrate-blog-to-astro        # bounded → verb-first outcome name
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

## Lesson file formats

File naming: `YYYY-MM-DD-topic-slug.md`, all in the top-level `lessons/`
folder.

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
Cursor, subagents, or different model/effort settings — record provenance
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
