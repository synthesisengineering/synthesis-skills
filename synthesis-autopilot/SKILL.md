---
name: synthesis-autopilot
description: "Autonomous-execution mode for explicitly delegated work. A thin composition layer that sequences the synthesis stack — thinking framework for decisions, plan file + context lifecycle + checkpoint for compaction survival, anti-shortcuts for solution quality, implementation integrity for verification — so one delegation phrase replaces a retyped block of standing instructions. Activate ONLY on explicit whole-task delegation: take care of this for me, autopilot this, handle this end to end, run with it with minimal check-ins, complete all phases autonomously, I trust you to finish this without me. Do NOT activate on vague keyword matches, on 'go ahead' approval of a single step, on discussion about autonomy, or on any ambiguous phrasing — users supervise some work by choice, and under-firing costs only a few extra check-ins while over-firing removes supervision the user wanted."
license: "Apache-2.0"
depends_on: ["synthesis-thinking-framework", "synthesis-context-lifecycle", "synthesis-checkpoint", "synthesis-anti-shortcuts", "synthesis-implementation-integrity", "synthesis-project-management"]
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Autopilot — Autonomous Execution Mode

## The Problem

Users who delegate whole tasks to an agent end up retyping the same paragraph of standing instructions every time: complete all the phases, don't check in constantly, use my decision framework, keep a plan file, don't lose state when the context compacts, build the real solution rather than a workaround. Retyped instructions have three failure modes. They drift — each retelling drops a clause, and the dropped clause (usually verification, or the decision protocol) silently doesn't happen. They decay — a long autonomous run outlives its own instructions when the context window compacts, and the agent reverts to conservative defaults mid-task. And they don't compose — the instruction block names disciplines that live in separate skills, and a paraphrase of a skill is weaker than the skill.

This skill encodes the delegation contract once. One explicit phrase from the user engages the mode; the mode sequences the skills that already exist rather than restating them.

## What This Is — and Is Not

**A mode.** Activation changes the agent's check-in cadence and self-management for the current delegated task: fewer questions, batched questions, a plan file that survives compaction, verification before "done." It does not change the quality bar — the anti-shortcut and integrity disciplines apply to all work, supervised or not.

**A thin composition layer.** Every discipline this mode invokes is defined in its own skill, listed in `depends_on`. This file sequences them and states the protocol that is unique to autonomous runs (trigger discipline, the plan file, batched decisions, alerts). When this file and a dependency appear to disagree, the dependency is authoritative for its own domain.

**Not an authority expansion.** Autonomy governs how the agent sequences work and how often it interrupts — never what it is permitted to do. See "Standing Gates Survive Autonomy" below.

## Activation — Trigger Discipline

Users supervise some work by choice. This mode must never self-select onto work the user intended to watch.

**Activate when the user explicitly delegates a whole task:**

- "Take care of this for me" / "handle this end to end"
- "Autopilot this" / "run with it — minimal check-ins"
- "Complete all the phases without checking in" / "work through the whole plan on your own"
- "I trust you to finish this autonomously"
- Explicit invocation of this skill by name or slash command

**Do not activate on:**

- "Go ahead" / "yes, do it" on a single step — that approves a step, it does not delegate the task
- General feedback like "you could be more autonomous" — a preference to note, not a mode to engage
- Conversation *about* autonomy, autopilot, or this skill
- Keyword coincidence in the task's subject matter
- Ambiguous phrasing. When genuinely unsure, proceed normally without the mode. Under-firing costs a few extra check-ins; over-firing removes supervision the user chose to keep.

**Never ask "should I use autopilot?"** If the phrasing is explicit, asking is false consultation (see synthesis-anti-shortcuts); if it is not explicit, the answer is already no.

**On activation, acknowledge in one line** — mode plus plan-file path, e.g. "Autopilot engaged — plan file: `resources/artifacts/2026-07-08-migration-autopilot-plan.md`." Then start the first phase. Do not recite the mission back, list the phases in chat, or ask for confirmation; the plan file holds all of that.

## The Delegation Contract

Engaging the mode means the user is taken to have said all of the following, once, for the duration of the task:

1. **Complete the work end to end** — all phases or waves, sequenced by the agent, with the minimum check-ins the decision protocol below allows.
2. **Best solutions, not workarounds** — the constraint-first protocol and costume-vocabulary scan from synthesis-anti-shortcuts apply to every draft, plan, and sub-agent brief.
3. **Important decisions go through the thinking framework** — synthesis-thinking-framework's modes, with the decision recorded in the plan file.
4. **State survives compaction** — plan file maintained per the protocol below; synthesis-context-lifecycle checkpoints at natural boundaries; synthesis-checkpoint whenever drift is suspected.
5. **Verification before "done"** — synthesis-implementation-integrity (or the domain's analog: fact-checking and quality gates for content work) runs before any completion claim.
6. **Standing rules remain in force** — nothing in this contract grants permissions the user's standing configuration withholds.

## The Plan File

The plan file is the mode's survival mechanism. Chat context compacts; the plan file does not.

**Location.** If the work belongs to a synthesis project (see synthesis-project-management), create it at `resources/artifacts/<date>-<task-slug>-autopilot-plan.md` inside that project. Otherwise use the working directory, or the platform's scratchpad if the working directory should stay untouched.

**Contents:**

```markdown
# Autopilot Plan — <mission title>
Engaged: <date> · Requested by: <user> · Status: <phase N of M>

## Mission
What "done" means, in the user's terms.

## Standing instructions
The delegation contract above, restated — so a post-compaction
re-read restores the mode, not just the task.

## Constraints and decisions already made
Everything the user has decided; never re-litigate these.

## Phases
- [x] Phase 1 — ...
- [ ] Phase 2 — ...

## Decisions log
Dated entries: decision, thinking-framework mode used, rationale.

## Batched questions for the user
Only questions the user alone can answer. Presented at checkpoints.

## Completion criteria and verification plan
```

**Cadence.** Re-read the plan file after any suspected compaction (it is the recovery seed — read it before anything else) and before every phase transition. Update it at every phase boundary: checklist state, decisions log, new batched questions. The standing-instructions section makes the file self-carrying: an agent that has lost the conversation can resume the mode from the file alone.

## Decision Protocol

Every decision in an autonomous run falls into one of three classes:

1. **Constraint-determined → execute.** If the user's stated constraints — in the conversation, the plan file, project context, or standing instruction files — determine the answer, do not ask. Execute and record it in the decisions log. "Recommendation: X. Your call?" on a constraint-determined question is the asking-as-shortcut costume (synthesis-anti-shortcuts).
2. **Open and important → thinking framework.** Run synthesis-thinking-framework, choose, record the decision and rationale in the decisions log, and proceed. Autonomy means making these calls, not deferring them.
3. **User-only → batch.** Facts only the user knows, genuine value trade-offs between goals the user holds, scope changes beyond the delegation. Add to the plan file's batched-questions section and continue with every piece of work that does not depend on the answer. Present the batch at a natural checkpoint — a phase boundary or the completion report.

**Never block the whole run on one question.** Re-sequence around it. Halt early only when *every* remaining path depends on an unanswered user-only question — that is a blocked state, reported per the alerts section.

## Standing Gates Survive Autonomy

Autopilot never overrides the user's standing rules. The user's global and project instruction files (CLAUDE.md, AGENTS.md, house rules) remain fully in force during autonomous runs — delegation of a task is not delegation of authority the user has reserved. Illustrative examples of gates that survive:

- Production deployments requiring explicit per-instance permission
- Never sending messages or email as the user — draft for their review instead (an agent-labeled channel, where one exists, is the only exception)
- Outward-facing or irreversible actions requiring confirmation first
- Commit-message hygiene and sanitization rules
- Never bypassing verification hooks (`--no-verify` and equivalents)

When a phase reaches a gated action, prepare everything up to the gate (the draft, the staged change, the deploy-ready artifact), add the approval to the batched questions, and continue with other phases. A run that ends with "everything is staged; these three actions await your approval" is a *successful* autonomous run.

## The Execution Loop

1. **Engage** — one-line acknowledgment with the plan-file path.
2. **Anchor** — run synthesis-checkpoint: verified date, project state from disk, history from git.
3. **Register** — attach to or create the synthesis project (synthesis-project-management); create the plan file.
4. **Phase loop** — for each phase: re-read the plan file; execute with anti-shortcut discipline; classify each decision per the protocol above; dispatch sub-agents per the hygiene rules below; then update the plan file, and at natural checkpoints run the synthesis-context-lifecycle session protocol so CONTEXT.md and the session log stay current.
5. **Verify** — before declaring the mission complete, run synthesis-implementation-integrity (or the domain analog). Fix what it finds; verification that only reports is not verification.
6. **Close** — session-end per synthesis-context-lifecycle (context files updated, work committed where applicable); completion report in plain language: what shipped, what was decided and why, the batched questions; then the completion alert.

## Sub-Agent Fan-Out Hygiene

Autonomous runs fan work out to sub-agents more than supervised ones, so dispatch discipline matters more, not less. Three rules (full rationale in synthesis-anti-shortcuts):

1. **At most five deliverables per dispatch.** Larger briefs stall or return partial work; split them into focused dispatches.
2. **No minimizing vocabulary in briefs.** "Keep changes minimal," "light touch," "conservative pass" license half-done work. Name the job at full size with explicit acceptance criteria.
3. **Acceptance audit on every non-clean-success return.** Partial completion, timeout, "stalled with substantial progress" — inspect what actually landed, diff it against the brief, and either re-dispatch or finish the gap directly. Accepting the partial state and moving on is forbidden.

## Completion and Blocked-State Alerts

When the run completes, or halts blocked on user-only questions, notify the user through whatever alert channel their environment defines (sound, notification, message) — an autonomous run the user has stopped watching needs an interrupt, not a chat message they will find later. Two rules govern every alert surface:

- **Confidentiality:** audio and notification banners can be overheard on calls and seen on shared screens. Alerts carry a generic task description and a pointer only — never client, repository, workspace, or person names. Detail belongs in screen-private channels: the completion report, the plan file.
- **Mute flags:** honor the environment's do-not-disturb convention (in the synthesis ecosystem, the presence of `~/.synthesis/quiet-audio` mutes all audio alerts). A muted alert still gets its full written report.

A blocked-state alert accompanies a report of what was completed, what remains, and the batched questions — never a bare "I'm stuck."

## Domain Neutrality

Nothing above is specific to software. The mode runs the same for engineering, research, writing, analysis, and operations work; only the verification analog changes — test suites and integrity checks for code, fact-checking and quality gates for prose, source verification for research. "Phases" may be a migration's waves, a report's sections, or an archive's batches. The plan file, decision protocol, gates, and alerts are identical.

## Composed Skills

| Skill | Role in the mode | When it runs |
|---|---|---|
| synthesis-checkpoint | Ground truth: date, disk state, git history | Engagement; any suspected drift or compaction |
| synthesis-project-management | Project registration; plan-file home | Engagement |
| synthesis-context-lifecycle | Durable memory: CONTEXT.md, sessions/, archival | Natural checkpoints; session end |
| synthesis-thinking-framework | Decision quality on open, important calls | Decision protocol, class 2 |
| synthesis-anti-shortcuts | Solution quality; dispatch and acceptance hygiene | Every draft, plan, brief, and sub-agent return |
| synthesis-implementation-integrity | Verification before completion claims | Before "done"; per-phase for high-stakes phases |

Each dependency works standalone. This mode is the sequencing that makes them one behavior: delegate once, and the stack runs itself.
