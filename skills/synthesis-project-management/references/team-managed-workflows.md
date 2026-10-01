# Managed team workflows

Use the existing `synthesis team` commands with an explicit JSON `--request` file.
The release launcher verifies the record, enrollment and journal readers used by
these routes. No command authenticates a human account, changes hosting ACLs,
releases somebody else's claim, or sends a message to an external service.

## Restricted project readers

An organization-owned project index opts in with exactly one line:

```text
# Synthesis-Team: team.json @ <exact-sha256> / <repository-id>
```

The sibling declaration must name the index repository's exact `origin` URL.
The current native board binding, opaque person, and declaration digest must
agree before the resolver, write admission, project routing, portfolio review,
context doctor or machine inventory exposes enrolled project records. A missing
or retired principal refuses. The local Git record also detects removal of a
committed enrollment marker from the working index.

A project reference sent to the coordination board must be readable by every
active human in the bound declaration. Restricted project IDs therefore do
not become shared-board messages. This contract covers these managed owners;
it cannot prevent an independent host tool or privileged filesystem editor
from reading or replacing data. Hosting ACLs and trusted enrollment remain
necessary. Generic un-enrolled indexes keep their ordinary route.

## Contribution inventory and appointment

`contributions` takes `team`, `team_digest`, `inventory`, and optionally
`evidence_root`. The inventory binds one exact declared repository and records
`observed_at`, complete coverage with an exact item count and no continuation
cursor, and every issue's dated events. Lanes, audience, runtime and evidence
plane are report fields; no remote label changes occur. Unanswered items remain
right-censored at the observation time. A median over answered items is not a
production response SLO or proof of remote coverage.

For appointments, save each captured event in the existing project at
`resources/evidence/contributions/<sha256>.json`. Its exact body is
`{"issue_id": "<id>", "event": <event-without-sha256>}`. The inventory names that
hash. Capture provenance is an operator attestation; these bytes do not prove
provider authentication. `propose-role` requires that evidence directory and
returns a proposal, never an appointment. It takes `person`, `role`, explicit
`scope`, active `backup`, and optional exact `replaces` appointment ID. A
contributor needs accepted work; repeat contributor and maintainer need three
accepted items, with a maintainer spanning two lanes. Runtime stewardship also
requires live runtime/compatibility evidence for every requested runtime scope.
These are published proposal thresholds, not claims about existing contributors.

`appoint` takes the project, project-relative team record, exact old digest,
board and native payload, complete inventory, proposal, explicit approval
attestation and timestamp. It rechecks current scoped appointing authority and
captured evidence, then publishes through the existing claimed-record
transaction. Source evidence is retained by that transaction. The new role
history preserves replaced occupants and attribution. It grants no hosting
membership. The board owner must explicitly bind the newly approved declaration
before another native session uses its changed roles.

## Departure and asset custody

`observe-offboarding` takes a bound team, person, board and explicit repo-guard
root. Its coverage is the exact retained board projects and supplied guard root,
not an assertion that an arbitrary machine has no other state. Active or parked
claims, attributed pending edits, nonterminal owned runs, unsettled effects,
unresolved child work and unreadable journals prevent managed readiness.
Each project is read through the bounded operator view; corrupt or incomplete
pages cannot become a clean result.

`offboard` requires the exact observation-derived approval, current native
claim, departure time and complete service-custodian succession. It preserves
opaque identities and historical authors, closes occupancies, and refuses an
unresolved mirror owner or backup obligation. It writes the new declaration
through the record owner. Hosting revocation stays `UNVERIFIED_EXTERNAL`.

After that approved departed-person record exists, `assets-plan` takes an
organization manifest and exact principal selection. `assets-retire` takes its
15-minute plan, `approval_digest` and optional `dry_run`. It uses the existing
enrollment lock, receipt CAS and copy journal to archive exact principal-owned
derived skill copies. Source repositories, private data and other people's
copies remain. Edited copies, stale receipt generations and historical copies
without principal custody refuse; none is reassigned by inference.

## Mandatory publication policy

The existing publication guard can enroll exact `team_contracts` entries with
physical `repository`, declaration `path`, `sha256`, human `person` and optional
additional `policy_layers`. Mandatory restrictions are unioned; approval roles
are intersected. The guard enforces `human-publication` and
`no-rapid-redeploy`; an unknown required control refuses because this owner
cannot prove it. Team policy never bypasses the existing exact approval,
artifact readback or single-use consumption. Changed source, roles or policy
invalidate the prior approval. Local principal selection is not human login.
