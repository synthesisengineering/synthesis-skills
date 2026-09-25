# Admitted execution controller

The normal agent interface has eight operations over the existing PM admission,
run journal, workflow, evidence and completion owners. It does not create another
scheduler, private state store, tool launcher or acceptance authority. The agent
interprets the user's intent and produces the request; users need not author JSON.

## Invocation and identities

Invoke `scripts/autopilot.py <operation> --project <absolute-project-path>
--request <request-file-or-dash> --actor <native-actor-file>`. The actor contains
the actual native event and coordination board. Native source mode is the default;
`--source-mode synthetic` labels a fixture and cannot qualify native execution.

Every request is schema 1 with `request_id`, `operation`, `project_id` and `input`.
After `start`, include the returned `run_id` and the current `expected_revision`.
The complete request is bound to its stable ID. A changed body cannot reuse an
existing ID, even after partial progress. The existing journal commits each step
with that binding; there is no separate request database. Inspect committed
events before recovering a failed invocation. Exact retries reuse committed
prefixes and cannot replay an external effect through a new label.

JSON inputs reject unknown fields, duplicate keys, nonfinite values, excessive
depth and unsafe paths. The request limit is 256 KiB. Managed input bytes are
content addressed under the admitted run home; unreferenced staging files remain
recovery material rather than evidence. Responses are bounded and include an
exact journal reference when further pagination is required.

## Operations

| Operation | Purpose and required interpretation |
| --- | --- |
| `start` | Supply `plan_ref`, `outcome_contract`, task `dimensions`, and `resource_envelope` containing `limits` and an actual authorized `deadline`. Optional preference references and task graph use their existing owner schemas. Resolve the profile, create the run, configure workflow and enroll the current native source. |
| `next` | Inspect ready work with `mode: inspect`, or admit a selected task with `mode: start`. Dependency, current authority, resources, history and native instructions constrain admission. A readiness result does not itself execute a task. |
| `record` | Register a durable artifact, invoke a supported observer, ingest a bounded native page, record a task attempt, bind a real profile obligation, or register/revise/resolve a decisive uncertainty. The specific kind has a closed input schema. Caller PASS fields are never evidence. |
| `checkpoint` | Preserve current progress and, when requested and applicable, obtain the existing PM execution-basis observation. This observation does not certify a normal whole-project clean checkpoint. |
| `explain` | Inspect contract, profile, coverage, ready work and unresolved obligations. Without a native actor, this is a historical read-only snapshot. Current ownership and acceptance require authenticated readback. |
| `cancel` | Record the user's cancellation while retaining partial work, effects and child obligations. A requested child or schedule cancellation still requires observed disposition. |
| `recover` | Run the full causal PM resolver, re-admit the actual owner, recover a committed request prefix and reconcile native source generations explicitly. An optional `capsule_ref` must name the current authentic checkpoint event. Rotation never silently resets a cursor. |
| `finish` | Invoke actual outcome, quality, profile and completion owners. A completed tombstone is historical state; stale current artifacts, expired evidence or new native invalidations prevent a current completed result. |

The response contains `status`, `run_id`, `revision`, `committed_event_ids`,
`next`, `coverage` and `diagnostics`. Read those fields rather than equating
process exit zero with completion. A missing capability is UNKNOWN, not PASS.

## Domain evidence and decisive observations

`coverage.domain_quality` reports all selected domain families, their existing
method owners and required dimensions. A method's availability is not a
qualification claim. Rich reviews combine task-specific semantic calibration
with actual consumer or readback requirements; `finish` preserves that combined
review instead of replacing it with a generic process result. Read
[domain quality](domain-quality.md) for the six family contracts.

The `record` kinds `uncertainty`, `uncertainty_observe` and
`uncertainty_revise` use the thinking framework's
[decisive-uncertainty contract](../../synthesis-thinking-framework/references/decisive-uncertainty.md).
`coverage.decision_uncertainty` reports current open/resolved questions, exact
source evidence and affected criteria. `next` suggests the declared cheapest
credible observations before dependent task work. The same current-evidence
guard applies to direct task admission, verification and completed closure.
Independent criteria, cancellation and incomplete closure remain available.
A registered question does not grant action authority or reset retry budgets.

Checkpoints retain a journal-owned recovery capsule; interrupted work follows
[the cold-resume protocol](../../synthesis-context-lifecycle/references/autopilot-recovery.md).
`record` also routes explicit `recovery_instructions` acknowledgement and the
closed [optional supervision actions](supervision.md). These operations retain
the existing authority and action-owner boundaries.

## Native evidence and currentness

Enrollment binds the exact admitted producer and begins at a complete native
record frontier. Earlier history is explicitly UNKNOWN. A source label or an
agent's claimed task ID cannot establish parentage: child evidence needs its
actual admitted dispatch and unique native parent/root/task identity.

Ingestion commits normalized events, witnesses, cursor and projection together
under the existing compare-and-swap journal. Consumption reopens current source
bytes. Positive call/result evidence and complete negative coverage are different
claims: verifying a successful tool result does not prove no later cancellation
occurred. The same decoder checks native sequence gaps during ingestion and
interval readback. Unsupported records, missing intervals, changed producer
bytes, rotation and partial tails preserve explicit uncertainty.

For sustained runs, current invalidation checks combine the journal's retained
invalidation index with current positive source witnesses and a bounded unread
tail. Normal bounded ingestion advances through benign history without requiring
a human approval for each page. A clear result means no unresolved journaled
invalidation and no invalidation in that current tail; historical negative
coverage remains UNKNOWN. This assumes a cooperating native append-only
producer. It does not prove that every old benign byte escaped a same-size edit
by an arbitrary filesystem writer. Recognized cancellations, unread gaps and
unreconciled source generations cannot be hidden by that scope limit.

Fresh root instruction and cancellation checks constrain work admission, Stop
feedback and completion. Child cancellation has its own admitted source scope.
Source reconciliation cannot erase a known cancellation merely by selecting a
later byte offset. Any resumed instruction must retain its exact native evidence
and owner-bound reconciliation; unknown historical coverage is never relabeled
as a complete transcript.

Native dialect translation covers declared Codex, Claude and Muse record shapes.
Parsing a dialect does not qualify every client transport or every outcome type.
The implemented child locator and native process outcome interpreter name their
specific supported surfaces. A missing host capability remains visible while
independent authorized work continues.

## Adaptive defaults and persistence

Canonical profile obligations have owner-derived semantics. A direct task with
no actual material choice can make decision capture inapplicable. Lessons are
required when a reusable finding or an explicit selection calls for them; an
unselected optional capture does not force filler prose. A custom enabled item
needs a real criterion mapping. Caller text and an unrelated artifact-existence
check cannot discharge the standing outcome and safety invariants.

The workflow retains failed attempts, strategy identity, evidence generations,
re-arm decisions and resource accounting. Productive work continues beyond the
old numeric observation and grading ceilings. Repeated unchanged transient
failures, permanent failures, unavailable authority and ambiguous effects remain
different conditions. New labels and reconfiguration cannot reset their history.
An actual hard resource limit is checked again when admitting the next task.
Unknown provider cost remains unknown and does not refund its reservation.

Stop first screens unresolved runs, then reserves one eligible correction in the
journal. The verified native launcher consumes that reservation at emission.
Concurrent processes, a fresh repeat bit or replayed proof cannot emit it twice.
Terminal infrastructure diagnostics end feedback explicitly unresolved, retaining
pre-mutation protection and recovery evidence.

## Project closure

An adopted PM project presents a circularity if its current clean-checkpoint
receipt must cover the journal write that consumes that receipt. The execution
basis avoids this by naming its narrower scope: it binds current project facts,
plan, inputs, sources and other runs, while accounting for only the selected
run's verified derived journal projections.

After the terminal event, the controller invokes the normal PM checkpoint owner
outside that journal. An interrupted postamble remains pending. Its exact retry
does only the remaining checkpoint work; it does not repeat terminal effects.
The resulting clean-checkpoint successor is bound to the terminal head and
unchanged operational meaning. Changed plan, project facts or unrelated bytes
still invalidate it. Current completion rechecks both the outcome and applicable
closure evidence before reporting success.

Owner-prepared native continuation uses the same `record` operation with
`kind: launch_prepare` or `kind: launch_cancel`; their exact fields and the
stdin-only service consumer are defined in [supervision](supervision.md).
Only an actual current native owner can prepare a grant. A transport observation
is never a task acceptance receipt, and a service cannot supply a native actor.
