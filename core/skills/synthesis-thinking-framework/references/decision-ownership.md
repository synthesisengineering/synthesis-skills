# Decision ownership

Use this contract when planning, reviewing or collecting decisions. It changes
who resolves a choice, not the required quality or permission to affect a target.

| Decision | Owner and next action |
|---|---|
| User instructions or established constraints determine the choice | Apply it, record the source and continue. Do not invent alternatives or ask the user to decide it again. |
| A technical choice is inside delegated work | The designated agent or integrator decides using the evidence, records the reason and continues. A close choice alone is not a new approval gate. |
| Missing information materially changes the requested outcome | Obtain the smallest necessary clarification. Continue independent authorized work while the answer is pending. |
| The user reserved a decision, requested a supervised checkpoint, or the action requires an unsatisfied approval | Prepare the concrete reviewable package and ask its actual owner. Block only the dependent action. |

## Preserve the controlling instruction

Read the current request, applicable user and project instructions, and existing
grants before classifying a decision. Explicit user instructions override skill
defaults. A grant already supplied remains usable within its scope until changed,
revoked or expired. Do not require a new packet or schema version to recreate it.
Permission tied to one payload, target or occasion does not authorize another.

Record the execution mode and its source once. **Supervised** work honors the
user's requested review points. **Delegated** work carries technical choices,
briefs, checkpoints and review through to completion without serial approval
requests. A default supervised workflow in a loaded skill must not overwrite
explicit delegation; delegation must not erase an explicit request to pause.
Ordinary authorized work does not require starting an unattended run.

Private or organization preferences may guide choices within that authority.
They never grant permission, override the current request, weaken required checks
or authorize data sharing. Keep private preferences out of public skill defaults.
Apply the user's declared preference precedence; when none is declared, the
specific current instruction governs over a general preference.

## Records and consequential actions

A useful decision record names the choice, owner, source of authority, rationale,
affected artifacts or targets, and any condition that would reopen it. A packet
response, hash, receipt, peer report or preference file is evidence to inspect;
its presence does not authenticate a principal or grant action authority.

The existing action owner verifies the trusted instruction and exact operation:
principal, scope, target, payload, validity and applicable restrictions. A changed
spec or choice meaning invalidates reuse of a response for that changed operation.
An older unbound record stays historical evidence; inspect its trusted source
before relying on it. Its age or format alone neither revokes a real user grant
nor turns it into permission for new work.

An unanswered question, elapsed timer, missing UI or failed notification is never
approval. Retain the pending question and route it through an available authorized
surface; do not repeatedly ask unchanged questions or silently proceed.

## Reopening a premise

Locked decisions prevent casual churn. New factual counterevidence may challenge
a premise: retain the evidence, identify dependent decisions and checks, and send
the proposed amendment to the recorded owner. A delegated owner may amend within
the grant; a principal-owned decision returns to the principal. Preserve unrelated
completed work and the earlier record. Reviewers may challenge a premise without
silently replacing it or editing the executor's work. Required acceptance criteria
cannot be waived merely by calling their failure a technical choice.
