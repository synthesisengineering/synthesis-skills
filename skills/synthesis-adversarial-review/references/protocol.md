# The adversarial review protocol, in full

Every section of the review protocol as written in 1.2.1, except the Finding Ledger section, which v5 rewrote around a markdown findings table (the 1.2.1 text is verbatim in [preserved.md](preserved.md)). SKILL.md's binding rules summarize each section; read the full section here before running that part of a review.

Contents:
- Purpose: the principal's outcome, typed domain review, authority, decision ownership
- Before Round One: Proportionality Contract (five items to record)
- Roles and Blind-Spot Rotation
- Adjudication and Separation of Duties (the third role, the reproducer rule, the revisit trigger)
- Goal-Focused Round (five terminal stages, ship-blocking versus ship-improving, closing a round)
- Sidecars, Evidence, and Handoff Topology
- Finding Ledger (the markdown findings table, finding fields, compare-before-write, what counts as an enforced gate)
- Bounded Control Depth
- Bounded Post-Publication Acceptance (five steps)
- Agent-Principal Norms
- Completion Report

## Purpose

Adversarial collaboration is useful when differently shaped agents attack the same work
from different blind spots. It is not an invitation to maximize rounds. The review exists
to deliver the principal's outcome: the artifacts and enforced boundaries the principal
asked to ship, at the accepted quality bar. Reviewer satisfaction, control growth, and a
large finding count are not completion criteria.

For [typed domain review](../../synthesis-autopilot/references/domain-quality.md), freeze the accepted requirement, source universe, domain method and rubric before the attempt. Use sound controls that preserve legitimate creative variation and seeded defects that change the user's outcome. Keep semantic calibration, actual consumer execution and target readback separate. Recheck the original evidence after a repair; replacing a reviewer without changed work or a concrete open risk does not justify another round.

This skill governs the review protocol. It does not grant publication, deployment,
communication, or repair authority. Those approval boundaries survive the review.

Apply the shared [decision ownership contract](../../synthesis-thinking-framework/references/decision-ownership.md).
Record the technical sufficiency owner and the controlling instruction before review.
Explicit supervised checkpoints remain binding; a designated integrator may resolve
technical sufficiency under delegation without asking the principal again. Existing
user grants persist within their exact scope. Preferences and receipts cannot create
authority or weaken required acceptance criteria.

## Before Round One: Proportionality Contract

Record this section in the engagement plan before dispatching a reviewer:

1. **Principal outcome.** State the outcome in the principal's terms, including the
   artifact or system boundary that must ship.
2. **Closed review universe.** Enumerate the artifacts, surfaces, and decision planes.
   Each assigned plane receives a per-artifact terminal disposition in the same round.
3. **Consequence and depth.** Name the harm the review is meant to prevent and the one
   verifier generation justified by that harm.
4. **Round-trip budget.** Set a budget for principal courier crossings. Agent-to-agent
   transport is not a principal crossing; a required human copy/paste is. Declare,
   batch, and count every such crossing. Exceeding the budget is a blocked-state alert.
5. **Stop rule.** Define green artifact acceptance, allowed open risks, approval gates,
   and the sufficiency checkpoint. Fewer rounds must come from complete coverage and
   stronger fixtures, never from fewer checks or lower quality.

If the universe cannot be enumerated, record why and define the bounded derivation that
will close it. “Representative samples” do not support a closed-world completion claim.

## Roles and Blind-Spot Rotation

Use at least two roles:

- **Executor:** owns the principal's artifacts, production implementation, and repairs.
- **Adversarial reviewer:** derives attacks independently, attempts to falsify the
  executor's claims, and does not inherit the executor's preferred abstraction.

Rotate the blind spot, not merely the agent name. Useful rotations include artifact versus
control plane, semantic versus structural evidence, producer versus consumer, pre-change
versus post-change state, and source versus destination representation. The reviewer reads
the bounded evidence package but independently re-derives the load-bearing facts.

Concession is health. A loop in which neither side ever reverses is two agents defending
priors. Every round records which claims the executor conceded, which the reviewer
conceded, and which remain evidence-bearing disagreements.

## Adjudication and Separation of Duties

A third role settles what concession cannot. Use it in every engagement with
evidence-bearing disagreements:

- **Adjudicator:** decides concede-or-challenge on each surviving disagreement,
  owns finding-state transitions in the ledger, and writes the transition
  rationale. The adjudicator authors neither attacks nor repairs in the same
  round it judges.

Separation rule: the repairer (executor) may add acceptance evidence but must
not edit, move, or delete the reviewer's reproducer — the command or procedure
that reproduces each finding. Reproducer changes need the adjudicator's
explicit approval, recorded in the finding's transition history. A repair that
cannot pass beside an untouched reproducer is not a repair.

Transitions stay inside the ledger's state set (`open | challenged |
repaired-prose | repaired-source | repaired-verified | conceded |
awaiting-principal`) with the compare-before-write discipline below. The
adjudicator's transitions carry the `principal-rule` or `agent-heuristic`
authority label of the evidence they rest on, never a bare verdict.

Revisit trigger (ruled 2026-09-19): the three roles live in this one skill by
decision, not by default. If this skill's size or a role-confusion incident
(a reviewer editing a reproducer, an adjudication bypassed) demonstrates that
packaging is the fix, re-open the three-skill split then.

## Goal-Focused Round

One goal-focused round has five terminal stages:

1. **Contract.** Restate the principal's outcome, recorded decisions and their owners, approval gates,
   assigned artifact universe, and this round's attack plane.
2. **Attack.** Derive counterexamples from the production path. Start controls at
   generation zero: encode motivating real defects as failing fixtures before repair.
3. **Disposition.** Give every artifact and finding one terminal row. Valid labels include
   accepted, blocked, repaired-prose, repaired-source, repaired-verified, conceded, and
   awaiting-principal; prose and executable repair are not interchangeable.
4. **Concept sweep.** Search the whole evidence package for the semantic claim a repair
   displaced. A corrected row beside stale summaries, receipts, headings, or sidecars is
   not a correction.
5. **Sufficiency.** Record established, open, and risk of shipping now. The delegated
   integrator decides technical sufficiency against the accepted criteria. At a
   principal-owned or explicitly supervised checkpoint, the principal's ruling terminates the loop.
   A technical ruling does not grant publication or waive an unsatisfied action gate.

Until artifact acceptance is green, most effort belongs to the principal's artifacts.
System improvements route separately unless they block delivery. A `ship-improving`
finding names its follow-up project; it does not extend the current delivery. A
`ship-blocking` finding remains in the delivery until repaired, conceded by the reviewer,
or resolved by its recorded decision owner within that owner's authority. New factual
counterevidence can reopen a locked premise through that owner; retain the prior decision
and invalidate dependent evidence. The reviewer never silently rewrites the premise.

Once required acceptance is satisfied, close the round and advance the accepted
artifacts to their authorized next step. Repairs reopen their failed criteria
and affected dependencies, not every previously accepted artifact. Name the
changed input, factual counterevidence or uncovered criterion before reopening
accepted work. Another reviewer's stylistic preference is not a new requirement.
For corpus work, retain item-level dispositions so one article's repair does not
restart review of the entire accepted corpus. A revision brief is not a revised
article when the task requires finished prose.

## Sidecars, Evidence, and Handoff Topology

Sidecars are claims. A manifest, receipt, verifier output, summary, or acceptance matrix
has no more authority than the production boundary that consumes it. Verify the claimed
artifact set and state rather than accepting the sidecar because it is structured.

Every review handoff names the applicable boundaries below; for a prose-only review, identify the reader-facing artifact and publication authority rather than inventing a receipt service:

- the **production entry point** whose behavior matters;
- the **enforcing boundary** that can refuse the state-changing action;
- the **receipt consumer** that validates the receipt before permitting that action;
- the exact artifacts, hashes, versions, and declared representations in scope;
- the command or procedure that reproduces each finding;
- the concept sweep required after any attribution or provenance correction;
- what the evidence does not verify.

A diagnostic is not an acceptance test; an acceptance test is not an enforced gate. Only
a fail-closed caller at the state-changing boundary can issue an authority receipt.

## Finding Ledger

Keep one findings file per engagement in the owning project's `resources/`
directory, `resources/<engagement>-findings.md`, claimed with
`synthesis claim <path>` by the session that adjudicates. It is a markdown table
plus an append-only transitions list, so any agent can read it and git keeps
its history:

```markdown
# Findings: <engagement id>

- Principal outcome: <outcome>
- Round-trip budget: <count>; principal courier crossings so far: <count>
- Proportionality: AGENT HEURISTIC: <bounded rationale>

| ID | Finding | State | Class | Authority (provenance) | Enforcement outcome | Evidence | Follow-up project |
|---|---|---|---|---|---|---|---|
| F1 | <one line> | open | ship-blocking | agent-heuristic (<provenance id>) | <what enforcement does today> | <reproducer, path> | — |

## Transitions

- <YYYY-MM-DD HH:MM> F1 open → challenged, by <adjudicator>: <evidence and rationale>
```

Each finding must carry:

- one state: `open | challenged | repaired-prose | repaired-source |
  repaired-verified | conceded | awaiting-principal`;
- one classification: `ship-blocking | ship-improving`;
- an authority label: `principal-rule | agent-heuristic`, plus a provenance id;
- an enforcement outcome in a separate field;
- evidence and an append-only transition history;
- a follow-up project when classified `ship-improving`.

The authority label and enforcement outcome answer different questions. `AGENT HEURISTIC`
may be the honest provenance label while enforcement is still wrong. Exercise every report
branch and verify finding, authority, and enforcement outcome independently.

Edits are compare-before-write. Before a transition, re-read the file and confirm the
finding's current state is the one you are moving from; if it is not, someone else moved
it, so stop and reconcile rather than overwrite. Only the adjudicator changes a State
cell, and every change appends one line to Transitions (never edit or delete a past
line). A new finding gets a fresh ID; a duplicate ID, a state outside the set, a missing
classification, or a ship-improving row without a follow-up project is a defect to fix
before handoff. Read the whole table back before each handoff.

Section-shape and vocabulary checks are diagnostics, not behavioral acceptance. Native
agent scenarios establish protocol behavior; only a fail-closed caller at the
state-changing boundary can claim an enforced gate. In v5 those callers are the guards
(sends, deploys, commits) and PR CI, which is the only release gate.

## Bounded Control Depth

Verifying a verifier once is legitimate. A finding in generation N+1 of a control the
principal did not request stops control growth; it does not automatically start generation N+2. If a round's findings are entirely self-inflicted by the newly introduced control,
record them, state the consequence for the principal's outcome, and refuse another control
round without an explicit principal decision.

This bound does not waive a defect in the requested artifacts or enforcing boundary. It
prevents an auxiliary control from becoming the mission.

## Bounded Post-Publication Acceptance

Publication or deployment begins a separate acceptance phase; it is not implied by a
successful build or publisher-authored receipt.

1. A second agent derives the live artifact universe from destination state, not from the
   publisher's receipt.
2. Validate the verifier with a known-good and known-bad positive control before
   interpreting a uniform result.
3. Record a per-artifact matrix across source, live origin, discovery surfaces, links,
   hygiene, and destination-specific deployment terminal state.
4. Distinguish exact-session readiness from aggregate project hygiene and prove durable
   artifact, board delivery, lifecycle receipt, remote publication, and receiver
   acceptance independently.
5. End when every artifact has a terminal verdict. Generic review does not reopen an
   approval already exercised. For a reproduced correction, the existing action owner
   checks whether the current grant covers the exact new payload and target. Obtain
   fresh approval when that action exceeds the grant or its policy requires it; do not
   infer renewed permission from a technical acceptance record.

## Agent-Principal Norms

- An agent has standing to surface a known-false claim once in the principal's own stated
  terms, especially when the agent is the reason the claim is known false.
- A proposed constraint loosening nominates the loosener for review.
- Principal rules and agent heuristics remain explicitly labeled. Approval fatigue is a
  failure mode: a gate that fires on trivia teaches rubber-stamping.

## Completion Report

Report the principal outcome first, then the artifact matrix, ship-blocking findings,
ship-improving follow-ups, concessions, courier-crossing count, sufficiency ruling, and
approval gates. Name the unverified remainder. “The reviewer is satisfied” is never a
completion signal.
