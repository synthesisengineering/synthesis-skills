---
name: synthesis-autopilot
description: "Execute an explicitly delegated whole task autonomously using the thinking framework, durable plan and context, checkpoints, anti-shortcut discipline, and implementation-integrity gate — and, for unattended runs, a verified continuation mechanism with budget and runaway control, so overnight and multi-day engagements keep producing turns instead of idling silently. Activate only for clear end-to-end delegation such as 'autopilot this,' 'take care of this for me,' 'handle this end to end,' 'run overnight,' or 'complete all phases autonomously'; never infer it from a single-step approval, discussion of autonomy, or ambiguous wording."
license: "Apache-2.0"
depends_on: ["synthesis-thinking-framework", "synthesis-context-lifecycle", "synthesis-checkpoint", "synthesis-anti-shortcuts", "synthesis-grounding-discipline", "synthesis-implementation-integrity", "synthesis-project-management", "synthesis-adversarial-review", "synthesis-decision-packet"]
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
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

## Continuation — Unattended Time Is a Scheduled Property

The costliest way this mode fails is silently, at a turn boundary. The real
incident that forced this section: a principal delegated an overnight run and
went to sleep; the agent engaged the mode correctly, wrote the plan file, ran
two phases, and then its turn ended. **Agent harnesses do not run between
turns.** The session sat idle all night — the machine rebooted mid-night
without interrupting anything, because nothing was executing — and the phase
that was the entire point never started. Every discipline in this file held;
the work still did not happen, because the contract said "complete the work
end to end" and nothing caused the next turn to exist.

**The rule: an engagement whose horizon extends beyond the current turn MUST
establish a verified continuation mechanism before its first turn ends — or
must say plainly, at engagement, that it cannot run unattended in this
environment and negotiate what happens instead.** Claiming overnight autonomy
without a continuation mechanism is a false capability claim, and the silence
it produces is indistinguishable from progress until the principal wakes up.

**Continuation mechanisms, by what they survive.** Verify what the current
harness actually provides — do not assume from memory (see the capability
probe rule below). The common classes:

| Mechanism | Survives turn end | Survives session death | Survives reboot |
|---|---|---|---|
| In-flight background work whose completion re-invokes the session (dispatched agents, detached exec with a completion waiter, workflows) | yes | no | no |
| Self-scheduled wakeup / dynamic loop (the harness re-invokes the session with a prompt on a cadence it sets) | yes | no | no |
| Scheduled task / cron re-entry (a scheduler starts a fresh run that resumes from the plan file) | yes | yes | usually |
| Principal-side relaunch instruction (documented command the principal or their machine runs) | yes | yes | yes |

**Match the mechanism to the horizon, and layer for long ones.** A run
measured in hours inside one sitting can ride background work and wakeups. A
run measured across sleep, reboots, or days needs a scheduler-class re-entry
as the dead-man's switch underneath whatever finer mechanism drives the
inner loop — the plan file is the state that makes any fresh re-entry able
to resume. When no mechanism exists at all, the honest engagement response
is: "I can only make progress while turns are running; here is the relaunch
command / loop invocation that would change that."

**Re-entry protocol.** Every wake — wakeup, completion notification,
scheduled re-entry, or a fresh session resuming — starts the same way: read
the plan file first (it is the loop variable), read the coordination board,
verify the plan's claimed state against ground truth (git, artifacts on
disk — not memory), then continue the next unmet goal. Record every wake in
the plan's cycle ledger.

**Budget and runaway control.** The twin fear of the silent stop is the
loop that burns the principal's usage limits without value. The plan file
declares the budget up front: horizon, maximum cycles or wall-clock, and
the per-cycle value test. Each cycle records what it advanced; a cycle that
advanced nothing must name the external event it is waiting on, and waits
use coarse cadences (do not poll for what a completion notification will
deliver). Stop conditions are exactly: goals met · blocker recorded and
principal alerted · budget exhausted and principal alerted. "Still running"
is never itself evidence of value.

**Capability probe before asserting absence.** An agent that wrongly
believes it is blocked stops. In the motivating incident's aftermath, a
session confidently reported that the counterpart CLI could not be reached
unattended — stale knowledge stated as fact; the CLI had a working headless
mode the same session had already used. Before any blocker or plan step
claims a capability is absent ("X cannot run autonomously", "no way to
reach Y"), run the probe — locate the binary, invoke the minimal command,
read the tool schema — and record the probe's evidence with the claim.
Zero results from memory are not evidence of absence.

**Volatile state dies at reboots.** Scratchpad and temp directories are
cleared by reboots and session ends — and long-horizon runs are exactly the
runs that meet reboots. Anything a later phase, another agent, or a durable
record depends on moves into the project (resources/) **at every phase
boundary**, not only at close. Losing derived findings to a reboot mid-run
means regenerating them on the next wake — paid for twice.

**The mechanical backstop.** Doctrine that depends on the agent remembering
it is the failure shape this section documents, so the gate is enforced:
engagement registers with `scripts/autopilot_gate.py register --plan <plan>
--mission "<done means>"`, and the plugin's Stop hook refuses to let a
session stop while a registered engagement is active, unfinished, and has
neither a recorded continuation (`autopilot_gate.py continuation`) nor an
alerted blocker (`autopilot_gate.py blocker ... --alerted`) nor an honest
close (`autopilot_gate.py close --goals-met | --incomplete <reason>`). The
cycle ledger is mechanical too: `autopilot_gate.py cycle` refuses to record
a wake that advanced nothing and names no external wait — there is no way
to log a bare spin. An engagement abandoned by a dead session blocks the
next session's stop BY DESIGN: abandonment must be loud, and the block
message carries the honest close command.

## The Plan File

The plan file is the mode's survival mechanism. Chat context compacts; the plan file does not.

**Location.** If the work belongs to a synthesis project (see synthesis-project-management), create it at `resources/artifacts/<date>-<task-slug>-autopilot-plan.md` inside that project. Otherwise use the working directory, or the platform's scratchpad if the working directory should stay untouched.

**Contents:**

```markdown
# Autopilot Plan — <mission title>
Engaged: <date> · Requested by: <user> · Status: <phase N of M>

## Mission
What "done" means, in the user's terms.

## Principal outcome
The artifact or system outcome the principal asked to ship. Reviewer
satisfaction and control construction are not substitutes.

## Standing instructions
The delegation contract above, restated — so a post-compaction
re-read restores the mode, not just the task.

## Constraints and decisions already made
Everything the user has decided; never re-litigate these.

## Coordination claims
Session id, active source-area globs, overlaps checked, and messages pending.

## Proportionality
Consequence being prevented, bounded review universe, justified control
depth, and why the planned review effort is proportionate.

## Cross-agent orchestration and round-trip budget
Counterpart sessions, direct dispatch path, provider-boundary exception if
one exists, allowed principal courier crossings, current count, and the
blocked-state alert threshold.

## Continuation
Mechanism causing the next turn, what it survives (turn end / session
death / reboot), the next-wake condition or cadence, the dead-man's
switch for long horizons, and how the mechanism was VERIFIED in this
harness (probe evidence, not memory).

## Budget
Horizon; maximum cycles or wall-clock; the per-cycle value test; counters
updated each cycle. Stop conditions: goals met · blocker + alert ·
budget exhausted + alert.

## Cycle ledger
One line per wake: what advanced, or the named external wait. Appended
mechanically via autopilot_gate.py cycle.

## Phases
- [x] Phase 1 — ...
- [ ] Phase 2 — ...

## Decisions log
Dated entries: decision, thinking-framework mode used, rationale.

## Batched questions for the user
Only questions the user alone can answer. Presented at checkpoints —
simple batches as chat prompts, complex batches as a decision packet
(synthesis-decision-packet). Packet paths and paste-back summaries
recorded here.

## Sufficiency checkpoint
Established, open, risk of shipping now, and the principal's ruling.

## Completion criteria and verification plan
```

**Cadence.** Re-read the plan file after any suspected compaction (it is the recovery seed — read it before anything else) and before every phase transition. Update it at every phase boundary: checklist state, decisions log, new batched questions. The standing-instructions section makes the file self-carrying: an agent that has lost the conversation can resume the mode from the file alone.

## Decision Protocol

Every decision in an autonomous run falls into one of three classes:

1. **Constraint-determined → execute.** If the user's stated constraints — in the conversation, the plan file, project context, or standing instruction files — determine the answer, do not ask. Execute and record it in the decisions log. "Recommendation: X. Your call?" on a constraint-determined question is the asking-as-shortcut costume (synthesis-anti-shortcuts).
2. **Open and important → thinking framework.** Run synthesis-thinking-framework, choose, record the decision and rationale in the decisions log, and proceed. Autonomy means making these calls, not deferring them.
3. **User-only → batch.** Facts only the user knows, genuine value trade-offs between goals the user holds, scope changes beyond the delegation. Add to the plan file's batched-questions section and continue with every piece of work that does not depend on the answer. Present the batch at a natural checkpoint — a phase boundary or the completion report.

**Batch delivery has two forms, chosen by the batch, not by habit.** A simple batch — a few questions answerable in a sentence each, no evidence to weigh — goes as plain chat prompts (or the platform's structured-question facility). A complex batch — many rows, or rows that need a recommendation, reasoning, evidence links, or a notes field — is delivered as a **decision packet built by calling `synthesis-decision-packet`'s `build_packet.py`**, never reimplemented inline. The packet's integrity rules travel with it: recommendations marked but never pre-selected, bulk acceptance recorded as bulk, and the pasted-back summary logged in the decisions log with the bulk/individual distinction intact. One packet counts as one round-trip against the plan's budget — that is what makes the budget compatible with keeping every decision the principal's: the cost scales with sittings, not items. Rebuild a packet's rows against any corrections the principal has issued since the rows were drafted; a row that a correction erased must be dropped, not carried through a rebuild.

**Never block the whole run on one question.** Re-sequence around it. Halt early only when *every* remaining path depends on an unanswered user-only question — that is a blocked state, reported per the alerts section.

## Cross-Agent Orchestration

When an autonomous plan calls for adversarial or independent review, autopilot owns the
transport. Use direct session-to-session dispatch where the runtime provides it. Give the
counterpart the bounded evidence package, production entry point, enforcing boundary,
receipt consumer, principal outcome, and terminal return contract. Apply the sub-agent
acceptance audit to its return before adopting any finding.

When both agents share the project repository, the default transport is the handoff queue
(`synthesis-project-management/scripts/handoff.py`): the writer stores the counterpart's
prompt as a durable, hash-pinned file under `resources/handoffs/`, announces it on the
coordination board, and the counterpart claims it with `handoff.py read` — no chat
transcript crossing, no principal courier. The queue and the decision packet are the two
directions that remove the principal as transport: work moves between agents through the
queue; decisions move between agent and principal through the packet. The queue never
self-triggers — a counterpart acts on it only when the principal's protocol says the other
side is done.

If a provider boundary genuinely has no direct transport, declare that before round one.
Batch the payload, identify who must paste it, and count it as one of the plan's principal
courier crossings. Never hide a manual crossing inside “send this to the reviewer.” The
round-trip budget is a tracked delivery cost; exceeding it triggers the blocked-state alert
rather than silently recruiting the principal as orchestration middleware.

**Dispatch the counterpart at scope-definition time, not only at review time,
for discovery-shaped phases.** An adversary auditing the scope inventory while
it is being built catches classifier drops and universe errors when they cost a
correction, not a re-run — proven in the motivating overnight engagement, where
a scope audit dispatched during Phase 0 found complete artifacts the primary
classifier had silently dropped. Review-time dispatch remains for judging
finished work; scope-time dispatch protects the universe the work runs over.

Write the proportionality section before the first review round: principal outcome,
closed artifact universe, consequence being prevented, justified control depth, and stop
rule. Fewer rounds come from complete per-artifact coverage and stronger fixtures, never
from reducing quality.

At each named checkpoint, record a sufficiency ruling with exactly three evidence fields:
established, open, and risk of shipping now. Put the ship-now choice in front of the
principal when the plan names that gate; the principal's ruling terminates the review loop.
Completion remains the principal's outcome, never reviewer satisfaction.

Control depth is bounded. Verifying a requested verifier once is legitimate. A finding in
generation N+1 of a control the principal did not request does not start generation N+2.
If a round's findings are entirely self-inflicted by the new control, record the findings
and stop control growth until the principal explicitly decides otherwise. Use
synthesis-adversarial-review for the complete round and ledger protocol.

## Standing Gates Survive Autonomy

Autopilot never overrides the user's standing rules. The user's global and project instruction files (CLAUDE.md, AGENTS.md, house rules) remain fully in force during autonomous runs — delegation of a task is not delegation of authority the user has reserved. Illustrative examples of gates that survive:

- Production deployments requiring explicit per-instance permission
- Never sending messages or email as the user — draft for their review instead (an agent-labeled channel, where one exists, is the only exception)
- Outward-facing or irreversible actions requiring confirmation first
- Commit-message hygiene and sanitization rules
- Never bypassing verification hooks (`--no-verify` and equivalents)

When a phase reaches a gated action, prepare everything up to the gate (the draft, the staged change, the deploy-ready artifact), add the approval to the batched questions, and continue with other phases. A run that ends with "everything is staged; these three actions await your approval" is a *successful* autonomous run.

## The Execution Loop

1. **Engage** — one-line acknowledgment with the plan-file path; register the
   engagement with the continuation gate (`autopilot_gate.py register`).
2. **Anchor** — run synthesis-checkpoint: verified date, project state from disk, history from git.
3. **Coordinate** — read the shared active-sessions board and claim every
   source area this run may write before editing.
4. **Register** — attach to or create the synthesis project (synthesis-project-management); create the plan file, including its Continuation and Budget sections. **If the horizon exceeds this turn, establish and verify the continuation mechanism NOW** — record it in the plan and via `autopilot_gate.py continuation` before any phase work makes the first turn long enough to forget.
5. **Phase loop** — for each phase: re-read the plan file and coordination board; execute with anti-shortcut discipline; classify each decision per the protocol above; dispatch sub-agents per the hygiene rules below; directly orchestrate any adversarial counterpart and count principal courier crossings; record the sufficiency checkpoint; then update the plan file (cycle ledger included), **sweep the scratchpad — anything a later phase, another agent, or a durable record depends on moves into resources/ at THIS boundary, because volatile state dies at reboots** — and at natural checkpoints run the synthesis-context-lifecycle session protocol so CONTEXT.md and the session log stay current.
6. **Verify** — before declaring the mission complete, run synthesis-implementation-integrity (or the domain analog). Fix what it finds; verification that only reports is not verification.
7. **Close** — session-end per synthesis-context-lifecycle (context files updated, work committed where applicable); release the coordination claims; close the engagement (`autopilot_gate.py close --goals-met`, or `--incomplete <reason>` for an honest partial close); completion report in plain language: what shipped, what was decided and why, the batched questions; then the completion alert.

The close step repeats the scratchpad sweep one final time: **What executable
state or required input data still exists only in this session's scratchpad?**
If a durable record cites its output, preserve the script and required inputs
under resources/scripts/ before the checkpoint can close.

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
| synthesis-grounding-discipline | Claim quality: provenance, cache re-verification, absence proof | Every recorded fact and status claim; before any write or deletion |
| synthesis-implementation-integrity | Verification before completion claims | Before "done"; per-phase for high-stakes phases |
| synthesis-adversarial-review | Bounded cross-agent attack, findings, sufficiency, and acceptance | When a plan calls for adversarial or independent review |
| synthesis-decision-packet | Complex user-only batches as one honest, reviewable page | Decision protocol, class 3, complex batches |

Each dependency works standalone. This mode is the sequencing that makes them one behavior: delegate once, and the stack runs itself.
