---
name: synthesis-adversarial-review
description: "Run bounded, differently-shaped-agent adversarial review against the principal's outcome, with artifact-complete rounds, production-topology handoffs, explicit concessions, a fail-closed finding ledger, sufficiency rulings, and independent post-publication acceptance. Use for adversarial review, cross-agent review, red-team collaboration, review rounds, finding-ledger work, or reviewer handoffs."
license: "Apache-2.0"
depends_on: ["synthesis-grounding-discipline", "synthesis-anti-shortcuts", "synthesis-project-management"]
metadata:
  author: "Rajiv Pant"
  version: "1.1.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Adversarial Review

## Purpose

Adversarial collaboration is useful when differently shaped agents attack the same work
from different blind spots. It is not an invitation to maximize rounds. The review exists
to deliver the principal's outcome: the artifacts and enforced boundaries the principal
asked to ship, at the accepted quality bar. Reviewer satisfaction, control growth, and a
large finding count are not completion criteria.

This skill governs the review protocol. It does not grant publication, deployment,
communication, or repair authority. Those approval boundaries survive the review.

Apply the shared [decision ownership contract](../synthesis-thinking-framework/references/decision-ownership.md).
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

## Sidecars, Evidence, and Handoff Topology

Sidecars are claims. A manifest, receipt, verifier output, summary, or acceptance matrix
has no more authority than the production boundary that consumes it. Verify the claimed
artifact set and state rather than accepting the sidecar because it is structured.

Every review handoff names:

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

Create one YAML ledger per engagement in the owning project's `resources/` directory:

```bash
python3 scripts/finding_ledger.py init \
  --resources-root resources \
  --file resources/<engagement>-findings.yaml \
  --engagement <id> \
  --principal-outcome '<outcome>' \
  --round-trip-budget <count> \
  --proportionality 'AGENT HEURISTIC: <bounded rationale>'
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

Ledger edits are compare-before-write operations. `transition` requires the recorded prior
state; missing or duplicate ids, stale expected state, unknown keys, invalid classification,
and symlink targets refuse without writing. Every command requires the owning project's
literal `resources/` root, rejects a target outside it or any symlinked path component, and
holds the resources-directory lock across read, expected-state comparison, replacement,
and read-back. Use `validate` before handoff.

Acceptance manifests label each case `diagnostic | acceptance-test | enforced-gate`.
Section-shape and vocabulary checks are diagnostics, not behavioral acceptance. A manifest
does not issue an authority receipt. Native agent scenarios establish protocol behavior;
only a fail-closed caller at the state-changing boundary can claim an enforced gate.

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
