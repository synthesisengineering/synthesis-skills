# Recovery capsules and cold resumption

The authoritative run journal owns execution history. Context lifecycle owns
retention and reconstruction; PM owns project selection and current authority.
Neither a capsule nor a transcript grants a new claim, changes the outcome
contract, replays an external effect, or proves a future wake.

## Produce and retain

The ordinary autopilot `checkpoint` operation embeds a bounded capsule in its
existing journal event. It references the exact preceding event and its state
digest, current contract and profile, every contract/profile revision, acceptance
criteria, authorization references, graph, waits, effects, child records, resource
owner state, registered artifacts, native handles and current input identities.
The controller returns `coverage.recovery_capsule` with the event reference,
JSON pointer, digest, revision and whether it is the current head.

Opaque extension references retain decision and resource owners without copying
their authority or guessing future schemas. Null measured usage stays unknown.
The capsule contains references, not a second copy of all project source or a
second execution database. Earlier capsules remain in their original events.
The reference projection has a 256 KiB limit; exceeding it preserves the journal
and the last capsule and returns an actionable error, never a truncated PASS.

Register useful intermediate child outputs as durable artifacts when they exist.
The capsule retains these artifacts when they fall within the child's declared
output roots, even before a final child return. Unregistered files, unsaved
reasoning and a model's hidden state are not invented as recovered work. Retain
declared output and scratch roots for inspection under the existing path owner.

## Consume through existing owners

1. Resolve the project through the PM registry and full causal project resolver
   before reading its execution journal. The controller uses explicit repo-guard,
   checkpoint receipt and coordination roots and does not fetch or refresh the
   board. A newer conflicting checkout or unattributed local changes must be
   reconciled through PM; a capsule cannot override that result.
2. Obtain fresh native-to-seat identity and the exact current PM claim. Recovery
   uses the existing journal lock and expected-revision CAS. A released claim,
   foreign native actor or copied event cannot acquire authority from the capsule.
3. Invoke the ordinary controller `recover`. `capsule_ref`, when supplied, must
   name this run's authentic checkpoint event at the current head. Old capsules,
   another run, copied JSON, changed instructions and changed registered artifact
   identities are refused. Omitting it still recovers from the verified journal;
   it never imports an arbitrary capsule as truth.
4. Reconcile current native sources, artifacts, unresolved effects and running
   children. Unknown action outcomes require actual action-owner readback. Do
   not issue the action again to determine whether it happened. Retain partial
   child output and establish actual worker disposition before reassignment.
5. The existing journal rebuilds current JSON, summary and plan projections.
   Interrupted committed request prefixes are retried with the same request body
   and ID. Partial or malformed committed events remain visible and block
   recovery; projections never replace their authority.
6. Read the returned `coverage.recovery` and `next` obligations. `RECONCILE`
   fences new tasks, delegation, new effects and completion while permitting
   cancellation, artifact repair and the necessary owner readbacks. `READY`
   means current recovery admission, not that all outcome criteria passed.

`coverage.recovery` names its observed revision and whether that admission is
still the current journal head. It separates the recorded admission from fresh
owner-bound external readback, including on an idempotent request replay. A new
native cancellation removes readiness without appending a fabricated event.
Actual work admission also rechecks native, instruction and artifact currentness;
a cached clear report never establishes future absence. Newly admitted effects
and children remain governed by their existing owners and do not invalidate the
earlier recovery merely because ordinary work has begun.

## Changed instructions and ownership

A diagnostic checkpoint cannot silently adopt changed controlling instructions.
An unrelated contract edit cannot clear that obligation either. The current
authorized agent must read and reconcile the actual instructions with the
existing contract, then use controller `record` with kind
`recovery_instructions`, the exact current `plan_digest`, `contract_digest` and
an explanation. This acknowledgement records the current owner's interpretation;
it grants no approval, cannot expand action authority, and cannot override a
native cancellation or missing native source. Contract changes remain subject to
the existing contract owner's evidence and authorization rules. A stale digest,
changed owner/claim or further instruction edit invalidates the acknowledgement.
Restoring the actual original instructions also resolves their drift.

The existing two-phase `owner.transfer.prepare` / `owner.transfer.accept`
protocol is the only implemented ownership-transfer path. It requires an exact
target, an unexpired prepared basis, official PM release/claim and fresh target
native admission. A dead process is not a grant to take over its claim. After a
legitimate transfer, native source generations still require explicit bounded
reconciliation; earlier producer history stays retained and its negative
coverage is not upgraded to known absence.

## Declared survival boundary

A new local Python interpreter recovering the real PM/journal proves cold
interpreter reconstruction. It does not prove application exit, logout, reboot,
network outage, computer power-off or another machine's operation. The capsule
marks these boundaries UNKNOWN unless their existing native owner supplies
separate actual evidence. Local absolute native/owner locators are never
silently rewritten into another machine's identity.

Optional Console supervision is described in
[the autopilot supervision contract](../../synthesis-autopilot/references/supervision.md).
Its source queue does not itself supply native launch authority or satisfy an
independent survival/backstop requirement.
