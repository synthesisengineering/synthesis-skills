# Bounded successor transactions

Use `autopilot.py successor` through the ordinary controller when a terminal
interval needs an explicitly authorized continuation. The agent prepares the
request after project recovery and current native PM admission. A saved
reference or an automation wake alone is not permission to continue work.

The operation derives one initial snapshot inside the existing run journal.
It keeps the predecessor as an immutable digest-bound reference and copies its
complete current obligations. It neither introduces a second budget store nor
accepts a batch of arbitrary mutations. This avoids an admission round trip for
each reservation, settlement and artifact while preserving a fresh authority
check before and after the complete derivation.

## Request and ownership

The schema-1 controller request uses `operation: successor`, `request_id`,
`project_id` and `input`; it omits `run_id` and `expected_revision`. Its closed
input is:

```json
{
  "predecessor": {
    "run_id": "00000000-0000-4000-8000-000000000001",
    "revision": 42,
    "event_digest": "<exact SHA-256 of the committed head>",
    "state_digest": "<exact SHA-256 of its canonical decoded state>",
    "deadline": "<immutable predecessor deadline>"
  },
  "deadline": "<new explicitly authorized interval deadline>",
  "authorization_ref": {
    "path": "resources/artifacts/continuation-authority.md",
    "digest": "<SHA-256 of the exact scoped authority record>"
  }
}
```

Use actual digests and timestamps, not these explanatory placeholders. The
reference records the human instruction's scope and provenance; its existence
never grants an external effect, more resource capacity or a different account.
The existing PM owner must authenticate the same native identity, seat,
repository and branch, with current exclusive claims for the new run home,
predecessor, plan, plan lock and authority reference. Same-native seat renewal
and cross-native handoff remain their separate existing protocols.

The child identity is deterministic for the resolved project and predecessor.
One predecessor cannot acquire two competing children by changing a request ID.
Exact concurrent retries serialize through the normal journal lock. Reusing a
child identity with a different request, deadline, authority reference or
predecessor head is refused, including after interruption.

## Carried state and current evidence

The owner fully replays every linked predecessor and checks its exact terminal
head and deadline. It retains the full nested resource ledger and all known and
UNKNOWN actual usage, hard or forecast enforcement, consumed trial allowances,
failed strategies, waits, artifacts, receipts, native cursors, child dispositions
and unfinished graph work. Limits cannot be replaced through this operation.
A later authorized capacity change must use its existing resource owner.

Every registered artifact is reopened through a bounded descriptor read and
matched to its retained digest. Missing, changed, symlinked, nonregular or
oversized evidence refuses the operation. Known unresolved external effects,
live or unaudited children, running graph nodes, active native continuations and
unresolved prepared launches require reconciliation before admission. A terminal
run does not itself prove all worker or process custody is settled.

The child starts `preparing`, with a new interval deadline and current workflow
binding. Historical receipts and verification entries retain their original
run/source bindings. They do not become current verification, fresh loaded
skills, native enrollment, wake survival or new action authority. `next`, native
source reconciliation and `finish` still invoke their ordinary current-source,
release-generation, authority, budget and evidence checks. Known gaps in older
untyped history remain explicitly unqualified.

## Commit and recovery

The authoritative commit is one complete successor event appended by the existing
journal owner. Before that event, a pending runtime index cannot supply a run and
managed discovery refuses it. A crash after append leaves a committed `preparing`
run; current/plan/index projections may still need reconstruction. There is no
automatic work dispatch or enrollment during this transaction.

Retry the exact request. Recovery verifies the complete predecessor chain,
artifacts, native ownership and fresh pre/post admission, then rebuilds only the
derived projections/index. Changed authority, claim generation, plan semantics,
predecessor bytes or input paths refuse recovery. An already committed child can
be reconstructed after its deadline, but subsequent work cannot ignore expiry.
The original predecessor and its deadline are never rewritten. Earlier request
registrations remain in that predecessor rather than becoming new commands.

The fences assume cooperating owner-managed writers plus ordinary filesystem
identity checks. No multi-file transaction can freeze unrelated privileged
filesystem writers. Journal digests, descriptor identity, path rechecks, locks
and final admission detect the supported races; these are not a claim of global
filesystem immutability.

## Bounds and refusal

The request remains bounded by the controller's 256 KiB limit. This operation
admits at most 32 linked predecessors, 10,000 aggregate historical events,
2,048 reservations and 10,000 artifact/reference entries. Ledger ancestry is
bounded to 32 levels. Each artifact uses the existing 64 MiB logical record
ceiling and the aggregate artifact read is at most 1 GiB. Journal witness counts
use the existing event plus block-store limits; no normal journal/storage cap
is raised. These limits keep full verification bounded and refuse excessive
input rather than silently pruning it.

Admission has a 120-second cooperative deadline, checked during bounded reads,
replay and lock acquisition. Existing individual PM/native operations retain
whatever stricter finite subprocess deadline their owner enforces; the transaction
deadline is not a promise to preempt arbitrary Python callbacks. The new interval
must be future, later than its predecessor and within seven days of admission.
There are no internal retries. A refusal retains every original byte and reports
the bound or unresolved custody; it cannot refund cost or manufacture completion.


Interrupted-prefix recovery binds the exact request, semantic plan digest, native
identity, coordination board and claim generation. The pending runtime index is
only a recovery hint: it grants no execution authority. After the child event is
committed, ordinary writers refuse any new parent event, including terminal-safe
observations; finish parent custody reconciliation before creating its child.
This preserves the child's exact-head lineage without rewriting the predecessor.
Journal discovery counts every physical entry before sorting, including retained
staging entries, and refuses excessive cardinality or elapsed enumeration.

Coordination reads invoked by a worker thread use the same finite process owner
in a dedicated supervisor whose main thread owns signal handling. The caller's
anonymous pipe provides parent-death custody; EOF terminates and reaps the owned
command group. Main-thread signal handlers and the existing anonymous snapshot
FD rules are unchanged. This does not claim custody over deliberately escaped
process sessions.

The thread supervisor executes a bounded anonymous snapshot of the module code
already resident in the caller, under isolated Python with bytecode-cache writes
disabled. It never reopens the module pathname at dispatch. The descriptor must
be an owned anonymous regular file and its exact size and digest must match
before decoding. This internal snapshot is not caller-provided serialized code.
