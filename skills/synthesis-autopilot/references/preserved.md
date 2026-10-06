# Preserved: what v5 autopilot does not carry, and why

Ruling D8: a rewritten skill loses nothing. This file says what the v5 rewrite
of synthesis-autopilot did not carry from autopilot 2.4.0 (commit `ca5c6bb`,
the design behind 41 real runs) and 3.6.7 (the version it replaces), and why.
The original text is here or in the three preserved reference files, verbatim.
[coverage-map.md](coverage-map.md) maps every rule to its new home. Nothing in
this file is current procedure, and links inside verbatim text point where
they pointed originally.

## Contents

- [Why the run engine was cut](#why-the-run-engine-was-cut)
- [The 3.6.7 reference files](#the-367-reference-files): where each went and why
- [The 2.4.0 and 3.6.7 scripts](#the-240-and-367-scripts)
- [2.4.0 sections changed in v5, verbatim](#240-sections-changed-in-v5-verbatim)
- [The 3.6.7 SKILL.md, verbatim](#the-367-skillmd-verbatim)

## Why the run engine was cut

Autopilot 3.x replaced the 2.4.0 plan file and small Stop gate with a run
journal, a nine-operation controller, native transcript decoders and worker
transports: 51 modules and 42,025 lines by 2026-10-05. Of 123 3.x run folders,
114 were synthetic evaluation fixtures, 8 were synthetic trials and 1 was real;
the six runs in other projects never completed. The 41 2.4.0 engagements did
real work (24 closed with goals met, 11 honestly incomplete, 6 abandoned).
Ruling D4 (2026-10-05) cuts autopilot back to plan, checkpoints, lessons,
packets and continuation, without the bookkeeping engine, and R6.1 makes the
plan file the run's record. So v5 keeps the 2.4.0 design and the 3.x doctrine
that names real failures (F1 to F8, effect reconciliation, the retry rules,
alert delivery states, domain acceptance), and drops the machinery that existed
to run, verify or work around other machinery. Source: the v5 code evaluation
for autopilot, section "Module table with verdicts".

## The 3.6.7 reference files

| File (3.6.7) | Verbatim copy | Verdict | Why it is not carried | Its doctrine that v5 keeps, and where |
|---|---|---|---|---|
| run-contracts.md | [preserved-engine.md](preserved-engine.md) | Replaced | The journal's command interface: create, import, command, observe, actor evidence, event persistence | Required citations and durable closure: the plan's `## Required evidence` section and the close check ([plan-file.md](plan-file.md#sections)); explicit incomplete closure ([plan-file.md](plan-file.md#status-values)). Legacy import is dropped: v5 never reads the old engagement records |
| controller.md | preserved-engine.md | Cut | A facade that prepared journal inputs and replayed request prefixes; it exists only to make the journal usable | None needed beyond the journal's purpose; decisive-uncertainty routing stays in [execution-doctrine.md](execution-doctrine.md#verification-and-review) |
| journal-storage.md | preserved-engine.md | Cut | Content-addressed block storage for large journal snapshots | None |
| successor-transactions.md | preserved-engine.md | Cut | Bounded continuation of a terminal journal interval | A closed run is not resumed; a new delegation starts a new plan that cites the old one |
| owner-resume.md | preserved-engine.md | Replaced | Same-native ownership renewal after a released board seat, native async answers | Ownership is the plan's `Owner session:` plus the board claim; [takeover](plan-file.md#ownership-and-takeover) after `Silent after:` |
| operator-experience.md | preserved-engine.md | Replaced | Paginated read-only Console view of journals | `status --all` and the plan's `## Questions for the principal` ([turn-end-check.md](turn-end-check.md#helper-commands)) |
| supervision.md | preserved-engine.md | Cut | Console supervision intents, queue leases and owner-prepared native launches | A visible, stoppable backstop per harness ([continuation.md](continuation.md#the-backstop-is-visible-and-stoppable)) |
| efficiency-measurement.md | preserved-engine.md | Replaced | Timing of local owner operations | R8.1's CI latency benchmark and the check's own timing tests |
| clients-and-recovery.md | [preserved-native.md](preserved-native.md) | Mostly cut | Supported-surface registry, worker adapters, Codex managed permissions, Claude context records, source doctor, legacy index | Stop behavior (bounded, fails open, reads only the owner's record) in [turn-end-check.md](turn-end-check.md#what-bounds-it); "continuation is observed" in [continuation.md](continuation.md#a-continuation-is-observed-not-assumed); waits and human visibility and the worker write-boundary rules in [execution-doctrine.md](execution-doctrine.md) |
| portable-native-evidence.md | preserved-native.md | Cut | Lossless archives of native transcripts | Memory is a lead, not authority ([execution-doctrine.md](execution-doctrine.md#authority-and-the-users-intent)) |
| native-worker-persistence.md | preserved-native.md | Cut | Persistent Codex worker sessions through the managed transport | None; native sub-agents and `codex exec` cover the need |
| native-adapter-sdk.md | preserved-native.md | Cut | Decoders for Cursor, Copilot and OpenCode | R9.3 supports Claude Code, Codex and Muse only |
| muse-launch-protocol.md (and .json) | preserved-native.md | Cut | Launching Muse sessions from code against a pinned protocol | Muse continuation facts in [continuation.md](continuation.md#muse). `references/muse-launch-protocol.json` stays beside these files only because the old scripts' tests read it; it goes when the scripts go |
| workflow-and-evidence.md | [preserved-review.md](preserved-review.md) | Replaced | Workflow commands, task graph, budget ledger, consumer-check sandbox, native review adapters | Five dimensions became the plan's `Horizon:` and checklist; ready-work, retry, budget, effect, children and review rules in [execution-doctrine.md](execution-doctrine.md); the search share in each brief ([delegation.md](delegation.md#sub-agent-fan-out-hygiene)) |
| evaluation.md | preserved-review.md | Moved out | The evaluation corpus and paired statistics measure goal G1; ruling D3 keeps that measurement on its own schedule (milestone M7), outside the plugin and never blocking a run | None in the skill |
| domain-quality.md | preserved-review.md | Slimmed | The typed rubric and calibration engine (`scripts/domain_quality.py`) | The six-family table and the review rules, in plain words, in v5 [domain-quality.md](domain-quality.md) |

## The 2.4.0 and 3.6.7 scripts

- **2.4.0 `autopilot_gate.py`** became `synthesis/autopilot.py`: the same three
  ways out (continuation, alerted blocker, honest close), the 60-minute
  first-wake grace, the bare-spin refusal and the scratch-citation close check,
  now read from the plan file. Not carried: the engagement registry under
  `~/.synthesis/autopilot/engagements/` (the plan file is the record), the
  binding to the old markdown coordination board, `--doctor` and `--test` (v5
  doctor and tests), and the fail-closed answer to an unreadable record, which
  is reversed: a turn-end check that fails closed loops forever.
- **2.4.0 `run_profile.py`**: the layered resolution (user profile file, project
  overlay, spoken-delta JSON, provenance per item) and its verifier receipt are
  not carried. Kept: the default items (added by `engage`), private additions
  (the v5 config's `autopilot.standing_checklist`), dispositions checked at
  close, items disabled only visibly (`WAIVED:` with a reason), and "a deploy
  grant in a file is never a grant" (now R3.2's typed approvals).
- **2.4.0 `search_budget.py`**: the arithmetic check is one line of each brief.
- **3.6.7 `scripts/`** (51 modules): left in place, unreferenced by the v5
  skill, until the principal reviews the cut list; the evaluation's module table
  gives each one's verdict.

## 2.4.0 sections changed in v5, verbatim

Each section below is the complete 2.4.0 text of a section that v5 changed,
from commit `ca5c6bb`. The 2.4.0 title line was
"# Synthesis Autopilot — Autonomous Execution Mode"; v5 titles the skill
"Synthesis Autopilot". Sections not listed here are carried verbatim in
[delegation.md](delegation.md), [continuation.md](continuation.md) and
[plan-file.md](plan-file.md).

### The Delegation Contract

**Why it changed:** Item 4 now points to plan-file.md instead of "the protocol below"; the rest is verbatim in delegation.md.

~~~~markdown
## The Delegation Contract

Engaging the mode means the user is taken to have said all of the following, once, for the duration of the task:

1. **Complete the work end to end** — all phases or waves, sequenced by the agent, with the minimum check-ins the decision protocol below allows.
2. **Best solutions, not workarounds** — the constraint-first protocol and costume-vocabulary scan from synthesis-anti-shortcuts apply to every draft, plan, and sub-agent brief.
3. **Important decisions go through the thinking framework** — synthesis-thinking-framework's modes, with the decision recorded in the plan file.
4. **State survives compaction** — plan file maintained per the protocol below; synthesis-context-lifecycle checkpoints at natural boundaries; synthesis-checkpoint whenever drift is suspected.
5. **Verification before "done"** — synthesis-implementation-integrity (or the domain's analog: fact-checking and quality gates for content work) runs before any completion claim.
6. **Standing rules remain in force** — nothing in this contract grants permissions the user's standing configuration withholds.
~~~~

### Run Profiles — the Contract as Data

**Why it changed:** Replaced by the plan's `## Standing checklist`, which `engage` fills from the defaults and the principal's private config and `close` checks. The four-layer resolution, the user profile file, the project overlay, spoken-delta JSON and the verifier receipt are cut (ruling D4); the evaluation found the principal had no user profile file, so the layers did nothing for his runs. Deploy grants now come only from the principal's typed approval (R3.2).

~~~~markdown
## Run Profiles — the Contract as Data

The delegation contract above is prose, and prose drifts: a principal
who retypes standing instructions for every run drops a clause each
time, and the dropped clause silently doesn't happen. The run profile
is the same contract as data. `scripts/run_profile.py` resolves the
effective standing checklist at engagement from four layers, weakest
first: the shipped default, the user profile
(`~/.synthesis/autopilot/profile.json`, synced across the fleet),
the project overlay (`<project>/resources/autopilot-profile.json`),
and spoken deltas from the delegation message ("skip blog seeds
tonight", "no deploys", "add: ..."). Every item carries its
provenance; items disabled by config stay visible in the resolution
instead of vanishing.

The resolved checklist freezes into the plan file's
`## Standing checklist (frozen ...)` section, and the engagement
registers with `autopilot_gate.py register --profile <effective.json>`.
Before close, `run_profile.py verify --plan` requires every frozen item
to be checked with evidence or unchecked with `WAIVED:` and a reason,
plus the deploy-authority line matching the frozen grant; `close
--goals-met` refuses without a fresh verifier receipt. An incomplete
close stays honest through its reason. `run_profile.py init` writes a
first user profile from the shipped default and never overwrites one.

Authority rule: profiles may narrow authority, never grant it. A
deploy grant stored in any file layer is forced to `none` with a
warning — only the run's own delegation message can grant deployment
authority, and the grant's provenance is recorded. Standing gates
survive profiles exactly as they survive autonomy.
~~~~

### Continuation — Unattended Time Is a Scheduled Property

**Why it changed:** Verbatim in continuation.md except this heading and the paragraph "The mechanical backstop", whose `autopilot_gate.py` commands are replaced by the plan's header lines and the v5 turn-end check (turn-end-check.md). The rules it enforced are kept: three ways out, unverified cron counted only within 60 minutes, close refused while the plan cites scratch, read-only status, no bare-spin cycles, owner-only blocking.

~~~~markdown
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
close (`autopilot_gate.py close --goals-met | --incomplete <reason>`). A
cron-class continuation is recorded with `--cron-job ID` naming the on-disk
schedule and stays UNVERIFIED until its first fire is observed and recorded
(`autopilot_gate.py cron-fired --plan <plan>`); past a 60-minute grace from
engagement, an unverified cron continuation blocks the Stop like no
continuation at all. Close refuses while the plan cites artifacts that exist
only in scratch directories. Engagement state is inspectable without
mutating it (`autopilot_gate.py status --plan <plan>`, `--json` for
machines). The
cycle ledger is mechanical too: `autopilot_gate.py cycle` refuses to record
a wake that advanced nothing and names no external wait — there is no way
to log a bare spin. Registration binds the engagement to the active
coordination-session UUID, project, exact claim, and native client-session
reference. The Stop gate blocks only the owning session. It probes the board
before reporting a foreign engagement's claim state, but foreign work—live,
inactive, or unknown—never globally blocks an unrelated project or forces that
session to adjudicate somebody else's completion.
~~~~

### The Plan File

**Why it changed:** The cadence paragraph is verbatim in plan-file.md. The location drops the scratchpad fallback (R9.2: every artifact lives in the project). The template is replaced by the v5 template, which keeps every section (Phases became Checklist, Batched questions became Questions for the principal, Coordination claims became Coordination, Completion criteria and verification plan became Completion criteria plus Required evidence) and moves Continuation into header lines the check reads.

~~~~markdown
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

## Standing checklist (frozen <timestamp>; profile <layers>)
The resolved run profile, one line per item — `- [x] <id> — <evidence>`
or `- [ ] <id> — WAIVED: <reason>` — plus the `Deploy authority this
run:` line. Frozen at engagement; verified before close.

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
switch for long horizons, the backstop cron id (scheduled at
engagement, deleted at close), and how the mechanism was VERIFIED in
this harness (probe evidence, not memory).

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
~~~~

### Cross-Agent Orchestration

**Why it changed:** The handoff-queue paragraph (`handoff.py`) is replaced by v5 board messages (R2.3); the rest is verbatim in delegation.md.

~~~~markdown
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
~~~~

### Multi-Session Coordination

**Why it changed:** Board mechanics now live in the v5 `synthesis` command; a seat is the harness session id, so there is no cross-harness handle to register; the backstop paragraph moved verbatim to continuation.md. The rest is verbatim in delegation.md.

~~~~markdown
## Multi-Session Coordination

An autonomous run is rarely the only session on the machine. Peer
sessions — same principal, other harnesses, other projects — share the
checkouts, the install trees, and the principal's review bandwidth. A
run that ignores them collides on landing, blocks peers on stale
claims, and misses findings routed to it. This section teaches the
loop; the mechanics (board commands, seat fields, claim verbs) live in
synthesis-project-management and are authoritative there.

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

**Register a cross-harness handle.** The seat registers the handle
peers in other harnesses use to route to it (board seat id plus the
native client-session reference), so a session that cannot dispatch
directly can still reach this run through the board. A seat with no
registered handle is unreachable, and unreachable seats get routed
around — or collided with.

**Shared mutations drain first.** Changes to state every session
reads — board schema, install trees, the release train, shared
inventories — need a clean check (no peer mid-flight on the same
state) plus propose-and-wait: announce the mutation on the board,
wait for objections or a clear window, then execute. Unannounced
shared mutation is the multi-session form of the shortcut.

**Long runs schedule a backstop cron.** Any engagement whose horizon
extends beyond the current sitting registers a scheduler-class
backstop at engagement — a cron or scheduled task that re-invokes the
run from the plan file if the inner continuation ever goes silent —
and deletes it at close. The backstop is the dead-man's switch under
whatever finer mechanism drives the loop; a run that ends with its
backstop still scheduled pages a principal who already got the report.
~~~~

### The Execution Loop

**Why it changed:** Steps 1, 3, 4, 5 and 7 named `autopilot_gate.py` and `run_profile.py`; they now name the v5 helpers (`engage`, `cycle`, `close`, `alert`) and board commands. Steps 2 and 6 and the closing scratchpad-sweep paragraph are verbatim in delegation.md.

~~~~markdown
## The Execution Loop

1. **Engage** — one-line acknowledgment with the plan-file path; register the
   engagement with the continuation gate (`autopilot_gate.py register`).
2. **Anchor** — run synthesis-checkpoint: verified date, project state from disk, history from git.
3. **Coordinate** — read the shared active-sessions board and inbox,
   register this seat's cross-harness handle, triage what is already
   waiting, and claim every source area this run may write before
   editing — named files over directories wherever the work allows.
4. **Register** — attach to or create the synthesis project (synthesis-project-management); create the plan file, including its Continuation and Budget sections; resolve the run profile (`run_profile.py resolve`, spoken deltas from the delegation message), freeze the standing checklist into the plan, and register with `--profile`. **If the horizon exceeds this turn, establish and verify the continuation mechanism NOW** — record it in the plan and via `autopilot_gate.py continuation` before any phase work makes the first turn long enough to forget.
5. **Phase loop** — for each phase: re-read the plan file and coordination board, triage the inbox (narrow requests release the overlap the same cycle); execute with anti-shortcut discipline; classify each decision per the protocol above; dispatch sub-agents per the hygiene rules below; directly orchestrate any adversarial counterpart and count principal courier crossings; record the sufficiency checkpoint; then update the plan file (cycle ledger included), **sweep the scratchpad — anything a later phase, another agent, or a durable record depends on moves into resources/ at THIS boundary, because volatile state dies at reboots** — and at natural checkpoints run the synthesis-context-lifecycle session protocol so CONTEXT.md and the session log stay current.
6. **Verify** — before declaring the mission complete, run synthesis-implementation-integrity (or the domain analog). Fix what it finds; verification that only reports is not verification.
7. **Close** — session-end per synthesis-context-lifecycle (context files updated, work committed where applicable); disposition every frozen checklist item in the plan, then `run_profile.py verify --plan`; release the coordination claims; delete the backstop cron; close the engagement (`autopilot_gate.py close --goals-met`, or `--incomplete <reason>` for an honest partial close); completion report in plain language: what shipped, what was decided and why, the batched questions; then the completion alert.

The close step repeats the scratchpad sweep one final time: **What executable
state or required input data still exists only in this session's scratchpad?**
If a durable record cites its output, preserve the script and required inputs
under resources/scripts/ before the checkpoint can close.
~~~~

### Sub-Agent Fan-Out Hygiene

**Why it changed:** Rule 4's `scripts/search_budget.py check` becomes one line in each brief; the rest is verbatim in delegation.md.

~~~~markdown
## Sub-Agent Fan-Out Hygiene

Autonomous runs fan work out to sub-agents more than supervised ones, so dispatch discipline matters more, not less. Four rules (full rationale in synthesis-anti-shortcuts):

1. **At most five deliverables per dispatch.** Larger briefs stall or return partial work; split them into focused dispatches.
2. **No minimizing vocabulary in briefs.** "Keep changes minimal," "light touch," "conservative pass" license half-done work. Name the job at full size with explicit acceptance criteria.
3. **Acceptance audit on every non-clean-success return.** Partial completion, timeout, "stalled with substantial progress" — inspect what actually landed, diff it against the brief, and either re-dispatch or finish the gap directly. Accepting the partial state and moving on is forbidden.
4. **Allocate shared budgets in the brief.** Metered tools with a session-wide budget (web search is the proven one: parallel research agents share a single pool and exhaust it silently) get an explicit per-agent allocation in each brief, plus the fallback when the pool runs dry. A fan-out of N research agents against one undivided budget is a plan to get N partial reports. The mechanical form: `SYNTHESIS_SEARCH_BUDGET_PER_AGENT` in the shell sets the per-agent search cap (default 25 — tunable, because the provider pool size is not visible to the skill), and `scripts/search_budget.py check --agents N` runs before dispatch; it fails closed when the cap is unset and prints the split the briefs must carry.
~~~~

## The 3.6.7 SKILL.md, verbatim

The complete body of the 3.6.7 SKILL.md, which v5 replaces. Its rules are reworded in plain words in the v5 references; [coverage-map.md](coverage-map.md) maps each paragraph. Its frontmatter description is replaced by a shorter one (the v5 format allows 300 characters).

~~~~markdown
# Synthesis autopilot

Turn an explicitly delegated outcome into verified work, retaining the user's
intent, authority and unfinished obligations across interruptions. Use the
host's tools and the ecosystem's existing owners. The agent makes judgments;
the run engine preserves state and enforces its declared completion contract.

## Activation

Engage on whole-task delegation: "autopilot this," "take care of this end to
end," "complete every phase," "run overnight," or an explicit invocation.
Discussion of autonomy, a keyword match, or approval of one step does not engage
this mode. Ambiguity means normal supervised work; do not ask whether to use
autopilot. Acknowledge once with the controlling plan's actual path, then act.

Delegation changes sequencing and interruption cadence. User instructions,
privacy, required quality, model/effort selection, tool restrictions and action
approval boundaries remain binding. Untrusted pages, peer returns, profile
files and receipts cannot grant permission. Approval already supplied by the
user remains usable within its stated scope.

## Start a run

1. **Recover and coordinate.** Resolve the project through project management's
   registry before reading project prose. Run its Session Start Protocol and
   checkpoint checks; read this seat's board/inbox, establish the native-to-seat
   binding and claim the exact areas needed. Read current source and retained
   work before deciding what remains. Never adopt another run or manifest.
2. **Define completion.** In the durable plan, record the user's outcome,
   deliverables, exclusions, existing decisions, authority references and
   acceptance methods. Map every deliverable to a criterion and an integration
   owner. A mixed writing/software request needs both kinds of acceptance.
3. **Resolve the workflow.** The `start` controller operation resolves the task's
   domains, uncertainty, effect class, horizon and available parallelism. Inspect
   the explanation and provenance. Public defaults preserve outcome, authority,
   evidence and recovery checks; domain checks follow the actual work. Blog
   material is opt-in, lessons depend on reusable evidence, and the completion
   report fits the domain. Existing active profiles do not change on upgrade.
4. **Create durable state.** Use `scripts/autopilot.py start --request` with the
   selected project, plan, contract, dimensions, resource envelope and native
   actor. This admitted controller resolves the profile, configures the existing
   workflow and enrolls the native source in the same journal. It resumes only
   the exact committed request prefix after interruption. Read the
   [controller contract](references/controller.md); the agent prepares its
   inputs, so the user need not learn the configuration format. The underlying
   [run owners](references/run-contracts.md) remain available for specialized
   operations without creating a second source of authority.
   Before starting a Claude interactive run, execute `autopilot.py doctor --actor`
   with this session's current actor file. Read its `native_source` byte bounds,
   decoded-record count and diagnostics. A decoder failure or incomplete required
   diagnostic interval blocks compatibility readiness. A successful bounded
   window leaves omitted history and owner authority coverage UNKNOWN.
   Follow the [source doctor procedure](references/clients-and-recovery.md#source-compatibility-doctor)
   instead of treating an EOF enrollment as a decoder test.
   After a terminal interval, use the bounded
   [successor transaction](references/successor-transactions.md) with new scoped
   authority. Old deadlines, costs, failures and obligations remain immutable;
   restored evidence does not become fresh native acceptance.
5. **Bound execution.** Configure the adaptive workflow and, when there are
   separable tasks, its dependency graph. Set a resource envelope, deadline and
   reserved integration/verification capacity. Distinguish enforceable limits
   from provider estimates. If the horizon exceeds the current turn, establish
   observed continuation before promising unattended operation; read
   [clients and recovery](references/clients-and-recovery.md).

For a new user without a project or board, use project management's existing
creation and claim protocol to establish the authorized durable home. Probe the
actual capabilities first. If identity or persistence cannot be established,
complete independent read-only work in the current session and report that
specific capability gap; do not claim a durable or unattended run exists.
Optional components must not become prerequisites for that read-only work.

## Optional evidence and measured overhead

When the user authorizes retaining native history, use the existing run-owned
[portable evidence archive](references/portable-native-evidence.md). Review its
privacy route before copying, retain exact available bytes and explicit gaps,
and never load an archive or native memory as action authority. Collection is
opt-in. For a performance investigation, use the bounded
[owner measurements](references/efficiency-measurement.md), preserving guard
and outcome equivalence and unknown provider costs.

## Execute and adapt

Maintain one finite delivery plan in the existing project record. For each
requested deliverable, distinguish implementation, accepted result, authorized
shipping and target read-back. A review report, revision instruction or passing
fixture is not the finished article, installed feature or observed outcome.
Keep required work visible until delivered; do not add optional investigations
to the completion boundary without the user's direction.

Group related ready changes into coherent candidates that share integration and
release gates. A worker brief, commit or repaired finding is not automatically a
release batch. Use focused checks during implementation, then run the complete
required gates on the integrated candidate. Keep a candidate frozen while its
checks run; prepare independent work in separately claimed areas. Do not hold a
ready delivery for unbounded future intake. Split candidates when dependencies,
risk, authority or the user's priorities require it, and record that reason.

When any node waits, inspect the whole remaining plan for ready work. Continue
safe authorized work within available capacity; delegate separable packages
when permitted. Only dependent work waits. Name the actual dependency or
resource conflict if no other work can proceed. Observe CI step/log advancement
and configured timeouts, not merely an `in_progress` label; investigate lack of
progress before calling it healthy. Reconcile a possibly committed effect
before any retry or cancellation.

At a checkpoint, compare delivered/accepted outcomes and resolved blockers with
the previous checkpoint. If only reports, helper variants, polls or review
counts increased, identify the cause and change the execution approach within
the existing authority and budget. Do not create a new monitor or verifier to
measure this comparison. A justified external wait stays a wait; it does not
reset deadlines or costs. Elaborate later nodes as their inputs become known.
Changing promised outcomes or weakening required checks needs the owning
approval, a versioned amendment and fresh verification.

Use the thinking framework's [decisive-uncertainty method](../synthesis-thinking-framework/references/decisive-uncertainty.md) for facts that could change the next decision. The controller reports six-family domain requirements and open discriminating observations. Register a task-specific question only when it matters; resolve it with the existing evidence owner, preserve refuted predictions, and continue independent criteria while its dependent work waits. An empty uncertainty register adds no investigation requirement.

Use `next`, `record`, `checkpoint`, `explain`, `cancel`, `recover` and `finish`
for the normal execution loop. The Console and read-only operator view provide
[status, durable questions and exact-owner handoffs](references/operator-experience.md). Stable request identities bind the complete
input and expected revision. Read the returned status, coverage and diagnostics;
a successfully invoked CLI can still report unresolved work. An interrupted
request may already have committed steps. Inspect that prefix before choosing
a new action, and never change its input while reusing its identity.

At every checkpoint, phase boundary, wake and re-entry:

- Read the board/inbox and handle intake on the existing coordination lane.
  Register a cross-client handle; narrow claims when an area is finished.
- Verify current artifacts, ownership, outstanding effects and remaining
  criteria. Context prose and previous receipts are evidence to recheck.
- Record changed artifacts, measured observations or a named external wait.
  Narration alone is not progress. Identical transient failures have a bounded
  retry allowance; permanent failures and ambiguous writes require different
  handling. See [workflow and evidence](references/workflow-and-evidence.md).
- Consume fresh native instructions and cancellation before admitting work,
  issuing corrective feedback or declaring completion. Missing enrollment,
  truncated history, changed observed bytes and incomplete intervals are
  explicit gaps. Root and child sources have separate scopes. A native success
  label alone neither proves the user's outcome nor overrides a later cancel.
- Persist required scripts, inputs and findings in the project at the boundary.
  Temporary files and chat context cannot be the only recovery copy. Refresh
  project records through context lifecycle and its compiler.
- Record established facts, open questions and the concrete risk of proceeding.
  Use the plan's named approval gate when one exists; ordinary decisions stay
  with the agent.

At this boundary, ask internally: What executable state or required input data
still exists only in this session's scratchpad? If a durable record cites its
output, preserve the script and required inputs under resources/scripts/ before
the checkpoint can close.

Shared install trees, release state, board schemas and inventories require the
existing coordination protocol: check for peer work, propose the mutation and
wait for a clear window. Do not write through overlapping claims.

## Decisions and delegation

Use the shared [decision-ownership contract](../synthesis-thinking-framework/references/decision-ownership.md).
Execute choices already decided by the user or determined by the user's
constraints. For a delegated technical choice, apply the thinking framework,
decide and record why. Preserve an explicitly requested review cadence. Batch
material principal ambiguity and human-only actions while continuing independent
authorized work. Existing valid user grants retain their stated scope; a packet
record or reviewer verdict does not grant permission. Use the existing structured
question tool for concise questions and the decision-packet skill for complex
review packages. Generate packets with that skill's `scripts/build_packet.py`,
never reimplemented inline. Prepare the concrete artifact before requesting
approval.

Delegate independent work when it improves the outcome. Each brief has at most
five deliverables, a closed artifact universe, exact work area, criterion IDs,
resource reservation, progress/cancellation rules, an integration owner and a
terminal return contract. Never lower the requested standard through minimizing
language. Reserve the total budget before distributing it, including children,
grandchildren, integration, failed attempts and recovery. The search-budget
helper's arithmetic preview is not admission; use its durable reservation path.

Declare immutable inputs by registered artifact, exact path and current digest.
Keep mutable outputs and scratch in separately admitted directories. Empty logs,
journals and checkpoints are still inputs when their contract requires preservation.
A prompt or workspace label cannot prove a write restriction. For an enforced
worker boundary, use the supported native worker observer and retain its actual
launch and preservation evidence. Other host delegation remains explicitly
unverified for this capability; never infer enforcement from an unchanged file.
Give workers their actual deadline and resource reservation before they start.

When working as a delegated child, execute the child's brief. The parent owns
the project/run lifecycle, aggregate accounting, integration and completion
report. Do not repeat root startup or create extra journals, reports and task
machinery outside the declared deliverables. Keep long-lived working source,
environments and sole recovery copies in the admitted durable workspace; system
temp and session scratchpads are only for explicitly bounded fixtures whose
evidence is captured before closure. Use the existing [placement and loss
protocol](../synthesis-project-management/references/parallel-agent-protocol.md#durable-work-placement-and-unexplained-loss); a missing worktree never proves
retirement or authorizes pruning.
For a bounded transformation, produce the artifact, perform the required
acceptance checks and return its paths, evidence and limitations. Extend checking
when a failure, changed input or concrete unresolved risk justifies it. A
successful check is the cue to return; repeated proof and extra prose consume
the same deadline as the user's result.

Use existing authenticated session addressing or PM's hash-pinned handoff queue.
The queue owner is `synthesis-project-management/scripts/handoff.py`; read its
protocol before dispatch. A queue item does not wake a worker by itself. Do not make the user a courier
when direct authorized transport exists. Record unavoidable provider-boundary
crossings and their budget. Dispatch discovery review early enough to catch
omitted artifacts; review finished work against actual consumers afterward.

Inspect every partial, failed or cancelled return. Preserve its artifacts, audit
against the brief and either finish the gap or redispatch. Every child needs a
terminal disposition and integration audit. Cancellation is requested first;
termination and scheduler deletion need observation, not inference.

## Verify outcomes

Use actual domain acceptance: software consumers, source-grounded research,
reader purpose and factual fidelity for writing, data reconciliation, target
read-back for browser operations, and cold recovery for project knowledge.
Freeze the task's required dimensions, source universe and acceptance methods
before observing outcomes. Use the [domain-quality contract](references/domain-quality.md)
for task-specific rubrics and calibrated judgments. Preserve PASS, FAIL and
UNKNOWN: missing evidence cannot become a pass, and a stylistic preference
cannot veto valid work unless the task made that preference a requirement.
Keep objective consumer observations separate from model judgments; neither
substitutes for the other when both are required.
Independence means a distinct reviewer or evidence source, not multiple votes
from the same assumptions. A test process is not automatically an independent
test design. Budget exploration where uncertainty justifies it, then assess the
result against the original purpose.

Register required artifacts and observations. The engine binds receipts to run,
contract/profile revisions, plan, current artifact hashes, verifier and validity
interval. An authentic failed observation stays a failure. `method: artifact`
proves current durable bytes only; choose a behavioral or domain method when
existence is insufficient. Never certify a claim by writing `verified: true`.

Run implementation-integrity or the domain's equivalent before completion.
Use one complete adversarial review per declared package and fix substantiated
findings. Recheck repairs and their affected dependencies; reuse still-valid
acceptance for unaffected artifacts. Extra review must name a failed criterion,
changed input or concrete uncovered risk and the observation that resolves it.
Once required acceptance is satisfied, proceed to authorized delivery. Do not
restart the full review because a new reviewer, checkpoint or chat turn exists.
Review satisfaction is not the user's outcome. No recursive control
construction, policy self-editing, telemetry upload or learning activation
follows from autopilot. Evaluation and reviewed improvement proposals follow
[the evaluation contract](references/evaluation.md).

## Wait, stop and recover

A saved run, recoverable context, a scheduled job and an observed wake establish
different facts. Use native capability observations for the exact client and
requested survival boundary. Record first and later wakes, deadline, independent
observer, expiry and cancellation. A scheduled record alone cannot prove a
future turn; a stopped worker cannot independently notice its own silence.
Retain the applicable long-run backstop rule unless the user approves a proved
equivalent mechanism. Never invent another scheduler to bypass host limits.

Record each wait separately and explicitly resolve it when its condition changes.
For a user-only blocker, prepare one actionable question and use an available
independent alert path. Record delivery as queued, delivered, failed, suppressed
or unknown. A previous notification cannot satisfy a new question. Audio and
banners carry only generic counts and a private-detail pointer; respect the
user's mute setting. A written report remains required when audio is muted.

The Stop boundary reserves and consumes at most one owner-verified correction
for the same current condition, including across new processes and repeat-bit
changes. Productive observations do not consume failed-attempt allowances;
renamed tasks, new receipt labels and unchanged strategies do not reset failure
history. Unknown or ambiguous external effects require their existing owner's
reconciliation before another attempt. Repeated
or infrastructure failures end feedback with an explicit unresolved diagnostic;
that is not completed work and does not relax pre-mutation guards. Preserve
state and foreign evidence. Resume through the registry, then fresh ownership,
current run journal, outstanding effects and the next ready task.
Use the [capsule and cold-resume protocol](../synthesis-context-lifecycle/references/autopilot-recovery.md)
for every interrupted run. Read [optional supervision and owner-prepared native continuation](references/supervision.md)
before enrolling it; a queue lease and a recovery capsule do not establish a wake.

Completion requires a current outcome readback even when the journal already
contains a completed tombstone. Changed artifacts or expired proof make the
current result unresolved. For an adopted PM project, the active execution basis
is deliberately narrower than the normal whole-project checkpoint. The latter
is created after terminal journal writes; interrupted closure retries only that
postamble, without replaying effects or rewriting historical success.

## Close

1. Reconcile effects before retrying or completing. Unknown outcomes stay
   unknown until target read-back establishes them. Reversing an action needs its own
   authority. Reconcile all children and usage, retaining unknown measurements.
2. Verify every required criterion, profile disposition and domain gate with
   fresh evidence. Write the completion report and durable recovery records.
3. Close through the engine as `completed`, `incomplete` or `cancelled` with the
   correct reason. A gated delivery awaiting approval is prepared work; claim
   completion only if preparation was the delegated outcome. Resource exhaustion
   does not mean the user asked to pause.
4. Cancel owned continuation through its native owner and verify deletion.
   Terminal tombstones reject late wakes even if cleanup failed; report that
   failure explicitly. Publish the project's required checkpoint, flush only
   this session's attributed edits and release its claim when pausing.
5. Report what was delivered, its verification, remaining obligations and any
   user-only action. Send the permitted completion alert. Do not claim
   installation, live loading or outcome acceptance from a source commit.

## Reference routing

- [Run contracts](references/run-contracts.md): create/import/command/observe,
  actor evidence, schemas, event persistence, status and closure.
- [Workflow and evidence](references/workflow-and-evidence.md): adaptive layers,
  DAGs, children, budgets, consumer checks and bounded recovery decisions.
- [Clients and recovery](references/clients-and-recovery.md): supported surfaces,
  native Stop behavior, continuation evidence, migration and diagnosis.
- [Evaluation](references/evaluation.md): artifact corpus, calibration, controlled
  and strongest-native comparisons, frozen task clusters, complete episode and
  cost accounting, uncertainty and reviewed improvement proposals.
- [Domain quality](references/domain-quality.md): frozen task-specific rubrics,
  source-grounded judgments, calibration and tri-state acceptance.
- [Decision ownership](../synthesis-thinking-framework/references/decision-ownership.md):
  delegated choices, material principal ambiguity, human-only dependencies and
  the boundary between a decision record and an actual grant.

Dependencies retain their ownership: project management admits paths and peers;
context lifecycle/checkpoint preserve project state; thinking chooses approaches;
anti-shortcuts protects effort; grounding protects factual claims; integrity and
domain skills verify results; adversarial review bounds critique; decision
packets carry user decisions. Read each when its task shape applies rather than
copying its rules into every run.
~~~~
