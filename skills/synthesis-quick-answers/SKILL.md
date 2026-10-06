---
name: synthesis-quick-answers
description: "Run a cheap, read-mostly companion session for ad hoc workspace lookups so focused sessions stay on task. Every answer names its source and a Verified, Cached or Uncertain tier. Use for a quick-answers, FAQ or lookup companion; not for decisions, drafting or sending messages."
license: "CC0-1.0"
depends_on:
  - synthesis-project-management
  - synthesis-context-lifecycle
  - synthesis-grounding-discipline
  - synthesis-concise-messaging
  - synthesis-model-tiers
  - synthesis-onboarding
metadata:
  author: "Rajiv Pant"
  version: "2.0.1"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Quick Answers — Lookup Companion Pattern

A cheap, read-mostly companion session that answers ad hoc workspace lookups, so focused project sessions keep their context for their own work. It owns no workflow: it reads across the workspace and writes almost nothing back.

## Binding rules

1. **Classify the question before searching**, then query only the source that answers that shape of question. Loading a whole project's context for one fact defeats a cheap companion.
2. **Verify anything volatile before asserting it**: schedules, status, ship state, dates. Context files and session summaries are caches, per `synthesis-grounding-discipline`'s cache-vs-truth rule; a fast stale answer is trusted precisely because it is fast.
3. **Every answer ends with a one-line grounding trailer** naming the source and a tier: **Verified** (confirmed live this turn), **Cached** (read from a file without re-verifying; give its as-of date) or **Uncertain** (no source found). A volatile fact answered as Cached is a defect.
4. **Answer tersely:** the fact first, one sentence of context only if it is load-bearing.
5. **Log each answer** as one line in `resources/FAQ.md` (date, question, answer, sources, tier); skip asks that will be false by tomorrow.
6. **Route durable facts through `synthesis-knowledge-capture`.** This project writes only its own `CONTEXT.md` and `FAQ.md`.
7. **No decisions, drafting, sending, calendar changes or delegation.** Hand real investigations to their own project.
8. **Live in the personal knowledge workspace**, `~/workspaces/{workspace}/ai-knowledge-{workspace}/`, created with `setup.py workspace --new {name}` from `synthesis-onboarding` (through `onboard.sh` when no plugin checkout is at hand); never a substitute folder.
9. **Routing is a file, not a habit.** Add the routing line to the tracked `.agents/workspace-AGENTS.md`, never to the root `AGENTS.md` or `CLAUDE.md` entry points the onboarding engine owns.
10. **Recommend the `routine` model tier and let the user set it**; an agent cannot switch its own model.

## Contents

- [references/operating-protocol.md](references/operating-protocol.md): the five steps run on every question, with the confidence-tier table and trailer examples. Read it at the first question of each session.
- [references/setup.md](references/setup.md): the pattern, its configuration table, and the six setup steps. Read it when standing up or repairing the companion.
- [references/background.md](references/background.md): the problem this solves (context pollution, cost mismatch) and how it relates to other skills. Read it when deciding whether a question belongs here.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.3.1 text now lives.
- [references/preserved.md](references/preserved.md): lines replaced in 2.0.1 because they named a command v5 does not have, verbatim. Read only to review the change.
- Scope boundary: below.

## Scope Boundary — What This Is Not For

Keep the mandate narrow on purpose:

- No decisions, no drafting, no sending messages, no calendar changes, no autopilot delegation. Every one of those belongs in a session with the corresponding skill loaded and the corresponding scrutiny applied.
- If a question turns out to need real investigation — multiple sessions, a plan, a deliverable — say so and hand it to its own project rather than absorbing the work here. The companion's job is triage-speed answers, not the work the answer points toward.
- Don't let this become a second inbox. It answers what's asked; it doesn't proactively surface items (that's `synthesis-chief-of-staff` territory) or own any cadence (that's an operations seat's job).
