# Delegation: activation, contract, decisions and coordination

The autopilot 2.4.0 text that worked in 41 real runs, kept verbatim except
where it named 2.4.0 machinery; those passages now name the v5 helpers, and
their originals are in [preserved.md](preserved.md#240-sections-changed-in-v5-verbatim).
The run engine's own rules (plan file, continuation, turn-end check) are in the
other references.

## Contents

- [The Problem](#the-problem) and [What This Is — and Is Not](#what-this-is--and-is-not)
- [Activation — Trigger Discipline](#activation--trigger-discipline): when to engage, and the one-line acknowledgment
- [The Delegation Contract](#the-delegation-contract): what engaging means the user said
- [Decision Protocol](#decision-protocol): the three classes, batching, decision packets
- [Cross-Agent Orchestration](#cross-agent-orchestration): counterparts, transport, proportionality, sufficiency
- [Multi-Session Coordination](#multi-session-coordination): the board, claims, shared mutations
- [Standing Gates Survive Autonomy](#standing-gates-survive-autonomy)
- [The Execution Loop](#the-execution-loop): engagement to close, step by step
- [Sub-Agent Fan-Out Hygiene](#sub-agent-fan-out-hygiene)
- [Completion and Blocked-State Alerts](#completion-and-blocked-state-alerts)
- [Domain Neutrality](#domain-neutrality) and [Composed Skills](#composed-skills)

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
4. **State survives compaction** — plan file maintained per [plan-file.md](plan-file.md); synthesis-context-lifecycle checkpoints at natural boundaries; synthesis-checkpoint whenever drift is suspected.
5. **Verification before "done"** — synthesis-implementation-integrity (or the domain's analog: fact-checking and quality gates for content work) runs before any completion claim.
6. **Standing rules remain in force** — nothing in this contract grants permissions the user's standing configuration withholds.

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

When both agents share the machine, the default transport is the v5 coordination board:
write the counterpart's brief as a file in the project (`resources/handoffs/`), then send
`synthesis msg <session id or project:<id>> "<path and what to do>"`; the recipient sees it
at its next prompt — no chat transcript crossing, no principal courier. The board and the
decision packet are the two directions that remove the principal as transport: work moves
between agents through the board; decisions move between agent and principal through the
packet. A message never wakes a session by itself — the counterpart acts on it at its next
prompt or scheduled wake.

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

## Multi-Session Coordination

An autonomous run is rarely the only session on the machine. Peer
sessions — same principal, other harnesses, other projects — share the
checkouts, the install trees, and the principal's review bandwidth. A
run that ignores them collides on landing, blocks peers on stale
claims, and misses findings routed to it. This section teaches the
loop; the mechanics live in the v5 `synthesis` command (`claim`, `release`, `who`,
`msg`, `inbox`, `use`) and synthesis-project-management, and are authoritative there.

**Poll the board at every checkpoint, and own triage.** Engagement,
every phase boundary, every wake or re-entry, and close: read the
shared board and this seat's inbox. Triage is the seat's own job, not
a principal question — acknowledge the sender on their lane, file
findings as intake, act on requests (narrow, pause, hand off) in the
same cycle. An inbox that only grows is a run that stopped listening.

**Claim before writing; narrow before peer landings.** Every writable
area is claimed before the first write, and claims stay as narrow as
the work: named files over directories wherever the work allows. When
a peer requests a narrowing for their landing, release the overlap the
same cycle — verify none of the peer's paths are paths this run still
needs, narrow, and confirm on the lane. Never write through an
overlapping active claim; never hold a directory claim past the moment
named files would do.

**Be reachable.** In v5 a seat is the harness's own session id,
registered on the board at session start; peers in any harness address
it by that id, its short name or `project:<id>`. Set the run's project
with `synthesis use <project>` so project-addressed messages reach it.
A session nobody can address is unreachable, and unreachable seats get
routed around — or collided with.

**Shared mutations drain first.** Changes to state every session
reads — board schema, install trees, the release train, shared
inventories — need a clean check (no peer mid-flight on the same
state) plus propose-and-wait: announce the mutation on the board,
wait for objections or a clear window, then execute. Unannounced
shared mutation is the multi-session form of the shortcut.

**Long runs schedule a backstop.** The rule, kept verbatim, and how to
make the backstop visible and stoppable in each harness are in
[continuation.md](continuation.md#the-backstop-is-visible-and-stoppable).

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
3. **Coordinate** — read the board and inbox (`synthesis who`,
   `synthesis inbox`), set the project (`synthesis use <project>`), triage
   what is already waiting, and claim every source area this run may write
   before editing (`synthesis claim <paths>`) — named files over directories
   wherever the work allows.
4. **Register** — attach to or create the synthesis project (synthesis-project-management); create the plan file from [the template](plan-file.md#template), including its Continuation, Backstop and Budget lines and any standing-checklist changes the delegation message asked for; run `engage --plan <path>`, which claims the plan, fills the owner and adds the standing checklist. **If the horizon exceeds this turn, establish and verify the continuation mechanism NOW** — record it on the plan's `Continuation:` and `Backstop:` lines ([continuation.md](continuation.md)) before any phase work makes the first turn long enough to forget.
5. **Phase loop** — for each phase: re-read the plan file and coordination board, triage the inbox (narrow requests release the overlap the same cycle); execute with anti-shortcut discipline; classify each decision per the protocol above; dispatch sub-agents per the hygiene rules below; directly orchestrate any adversarial counterpart and count principal courier crossings; record the sufficiency checkpoint; then update the plan file (cycle ledger included, via `cycle`), **sweep the scratchpad — anything a later phase, another agent, or a durable record depends on moves into resources/ at THIS boundary, because volatile state dies at reboots** — and at natural checkpoints run the synthesis-context-lifecycle session protocol so CONTEXT.md and the session log stay current.
6. **Verify** — before declaring the mission complete, run synthesis-implementation-integrity (or the domain analog). Fix what it finds; verification that only reports is not verification.
7. **Close** — session-end per synthesis-context-lifecycle (context files updated, work committed where applicable); disposition every standing-checklist item in the plan; delete every scheduled job and read the deletion back; close the run (`close --done`, or `--incomplete <reason>` for an honest partial close), which checks all of it and releases the plan's claim; release the other coordination claims; completion report in plain language: what shipped, what was decided and why, the batched questions; then the completion alert (`alert --kind done`).

The close step repeats the scratchpad sweep one final time: **What executable
state or required input data still exists only in this session's scratchpad?**
If a durable record cites its output, preserve the script and required inputs
under resources/scripts/ before the checkpoint can close.

## Sub-Agent Fan-Out Hygiene

Autonomous runs fan work out to sub-agents more than supervised ones, so dispatch discipline matters more, not less. Four rules (full rationale in synthesis-anti-shortcuts):

1. **At most five deliverables per dispatch.** Larger briefs stall or return partial work; split them into focused dispatches.
2. **No minimizing vocabulary in briefs.** "Keep changes minimal," "light touch," "conservative pass" license half-done work. Name the job at full size with explicit acceptance criteria.
3. **Acceptance audit on every non-clean-success return.** Partial completion, timeout, "stalled with substantial progress" — inspect what actually landed, diff it against the brief, and either re-dispatch or finish the gap directly. Accepting the partial state and moving on is forbidden.
4. **Allocate shared budgets in the brief.** Metered tools with a session-wide budget (web search is the proven one: parallel research agents share a single pool and exhaust it silently) get an explicit per-agent allocation in each brief, plus the fallback when the pool runs dry. A fan-out of N research agents against one undivided budget is a plan to get N partial reports. Each brief carries its share in one line, for example "your share of web searches is 25 (six agents, 150 in all); when it runs out, return what you have and name the unanswered questions". Where `SYNTHESIS_SEARCH_BUDGET_PER_AGENT` is set, it is the per-agent share (25 is a reasonable default — tunable, because the provider pool size is not visible to the skill). Nothing intercepts calls made outside the brief, so the share in the brief is the control.

## Completion and Blocked-State Alerts

When the run completes, or halts blocked on user-only questions, notify the user through whatever alert channel their environment defines (sound, notification, message) — an autonomous run the user has stopped watching needs an interrupt, not a chat message they will find later. Two rules govern every alert surface:

- **Confidentiality:** audio and notification banners can be overheard on calls and seen on shared screens. Alerts carry a generic task description and a pointer only — never client, repository, workspace, or person names. Detail belongs in screen-private channels: the completion report, the plan file.
- **Mute flags:** honor the environment's do-not-disturb convention (in the synthesis ecosystem, the presence of `~/.synthesis/quiet-audio` mutes all audio alerts). A muted alert still gets its full written report.

A blocked-state alert accompanies a report of what was completed, what remains, and the batched questions — never a bare "I'm stuck."

In v5, `alert --kind blocked|done|budget --count N` posts the banner and speaks
the generic text, honoring the mute flag, and prints one outcome per channel.
Record that outcome on the blocker or close line: a queued or posted
notification is not proof the person saw it, a muted alert is suppressed, not
delivered, and an earlier alert does not cover a new question.

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
