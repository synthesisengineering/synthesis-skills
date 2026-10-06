---
name: synthesis-adversarial-review
description: "Run bounded adversarial review by differently shaped agents against the principal's outcome: artifact-complete rounds, production-topology handoffs, concessions, a markdown findings table, sufficiency rulings, post-publication acceptance. Use for adversarial, cross-agent or red-team review."
license: "Apache-2.0"
depends_on: ["synthesis-grounding-discipline", "synthesis-anti-shortcuts", "synthesis-project-management"]
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Adversarial Review

Differently shaped agents attack the same work from different blind spots, in bounded rounds, to deliver what the principal asked to ship.

Before freezing or accepting a package, apply the mandatory [domain contracts and replay scorecard](references/domain-review-contract.md).

## Binding rules

The rules follow the protocol's sections in order, Purpose through Completion Report; [references/protocol.md](references/protocol.md) holds each section in full.

1. **The review exists to deliver the principal's outcome:** the artifacts and enforced boundaries the principal asked to ship, at the accepted quality bar. Reviewer satisfaction, control growth and a large finding count are not completion criteria.
2. **The review grants no publication, deployment, communication or repair authority.** Apply the shared [decision ownership contract](../synthesis-thinking-framework/references/decision-ownership.md) and record the technical sufficiency owner first.
3. **For [typed domain review](../synthesis-autopilot/references/domain-quality.md), freeze the accepted requirement, source universe, domain method and rubric before the attempt.** Replacing a reviewer without changed work or a concrete open risk does not justify another round.
4. **Record the contract before dispatching a reviewer:** the principal outcome; the Closed review universe; consequence and depth; a Round-trip budget that counts principal courier crossings; and the Stop rule.
5. **Executor and Adversarial reviewer are separate roles.** Rotate the blind spot, not the agent name. Concession is health: record what each side conceded.
6. **An adjudicator settles surviving disagreements** and owns ledger transitions. The repairer never edits, moves or deletes the reviewer's reproducer without the adjudicator's recorded approval.
7. **Every goal-focused round runs five terminal stages:**
   1. **Contract.** Restate the outcome, decision owners, approval gates, artifact universe and attack plane.
   2. **Attack.** Derive counterexamples from the production path; encode real defects as failing fixtures before repair.
   3. **Disposition.** One terminal row per artifact and finding; prose and executable repair are not interchangeable.
   4. **Concept sweep.** Search the whole evidence package for the claim a repair displaced.
   5. **Sufficiency.** Record established, open, and risk of shipping now. At a principal-owned or supervised checkpoint, the principal's ruling terminates the loop.
8. **A `ship-blocking` finding stays in the delivery** until repaired, conceded or resolved by its decision owner; a `ship-improving` finding names its follow-up project. A repair reopens only its failed criteria.
9. **Sidecars are claims.** Every handoff names the production entry point, the enforcing boundary, the receipt consumer, the exact artifacts, each finding's reproducer, the concept sweep owed after a provenance correction, and what the evidence does not verify.
10. **One findings file per engagement,** a markdown table in the project's `resources/` (see Findings file below). Each finding carries a state, a classification, an authority label, a separate enforcement outcome, evidence, and a follow-up project when ship-improving; only the adjudicator changes a state, and every change appends a transition line.
11. **A finding in generation N+1 of an unrequested control stops control growth;** generation N+2 needs an explicit principal decision.
12. **After publication, a second agent derives the live universe from destination state** and records a per-artifact matrix. A correction beyond the current grant needs fresh approval.
13. **Surface a known-false claim once,** in the principal's terms. A proposed loosening nominates the loosener for review. Approval fatigue is a failure mode.
14. **Report the principal outcome first** and name the unverified remainder. "The reviewer is satisfied" is never a completion signal.

## Contents

- [references/protocol.md](references/protocol.md): every protocol section in full, with the reasons, the findings-file template and field list, and the post-publication steps. Read the matching section before running that stage of a review.
- [references/domain-review-contract.md](references/domain-review-contract.md): the review package, its four profiles and seven records, the checks the reviewer applies by hand, and the twelve lessons and scorecard. Read it before freezing or accepting any package.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.2.1 text and each script change now lives.
- [references/preserved.md](references/preserved.md): the retired ledger command, validator and diagnostic text, verbatim. Read only to review the change.
- Findings file: below.

## Findings file

Create `resources/<engagement>-findings.md` in the owning project from the template in [references/protocol.md](references/protocol.md#finding-ledger) (principal outcome, round-trip budget and courier crossings, proportionality, the findings table, the transitions list), and claim it with `synthesis claim <path>`. Before each transition, re-read the row and confirm its state is the one you are moving from; read the whole table back before every handoff. Git keeps its history; a transition line is never edited or deleted.
