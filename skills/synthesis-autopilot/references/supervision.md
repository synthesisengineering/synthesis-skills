# Optional supervision through existing owners

The optional integration uses the existing Console process as an independent
visible observer. It does not install a new guard daemon or change the existing
native-toolchain ADR. Console lifecycle, launchd/systemd enrollment and uninstall
remain with Console's existing installers. Enabling a journal enrollment is
separate from activating a service; neither operation authorizes the other.

## Source interface

Authenticated native agents submit the ordinary controller `record` operation
with `kind: supervision`. The controller applies closed-schema actions through
the existing PM admission, run lock and CAS journal. The browser and Console
status process cannot construct an actor or grant approval. The implementation
does not expose a shell command string or arbitrary executable to the queue.

| Action | Fields beyond `kind` and `action` | Meaning |
| --- | --- | --- |
| `enroll` | `authority_ref`, `max_requests`, `max_attempts`, `lease_seconds`, `backoff_seconds` | Explicit opt-in bound to current owner/claim, contract, profile and controlling instructions. The authority reference must already occur in the current contract. |
| `request` | `request_id`, `job_id` | Retain a request concerning one existing native continuation job. This does not register or launch it. |
| `claim` | `request_id` | Recheck current native capability/job, recovery, waits, effects, artifacts and children. Successful admission issues a bounded request-only lease and increasing fence. |
| `reconcile` | `request_id` | Read existing owner-verified subsequent wake evidence. Missing or ambiguous delivery remains unresolved and is never replayed. |
| `cancel` | `request_id`, `reason` | Preserve a request cancellation tombstone. Native job cancellation remains a separate action with its required readback. |
| `stop` | `reason` | Stop admission and cancel retained intents; preserve diagnostics. Does not claim that a native job or Console process was stopped. |
| `uninstall` | `reason` | Retire the optional journal enrollment and preserve tombstones. Actual Console service removal belongs to its lifecycle owner. |

The queue permits at most 64 retained request identities, five admission attempts
per request, a lease of at most 300 seconds, and configured exponential backoff.
Limits must be explicit finite positive integers. The same identity cannot be
reused after completion or cancellation. A leased or ambiguous request cannot
be claimed again; expiry requires reconciliation. A fresh native wake may resolve
the observation, but it does not prove that this optional observer caused it or
that the task outcome succeeded.

Queue state, configuration, lease fences, attempts, backoff and tombstones live
only in `extensions.supervision` of the authoritative run journal. There is no
additional authority database. Enrollment is invalid when the actual owner,
claim, contract, profile or instructions change. Cancellation remains possible
under fresh current PM authority. Re-enrollment cannot erase retained requests
or active uncertainty. A future schema upgrade must retain these obligations.

## Read-only Console adapter

`supervision.status_view(state)` produces a finite historical projection;
the ordinary controller also returns it as `coverage.supervision`. It includes
the schema, lifecycle, journal revision, bounded requests, status counts,
diagnostics, supported-schema health and explicit survival limits. Console may
display or poll this projection through its existing bounded subprocess/status
adapter. No PM actor is required to display historical records; a fresh native
actor is required for every mutation.

An application must not infer current external state from the read-only view.
Provider effects and current native bytes are checked at actual admission.
Request-only dispatch data binds the exact job, request, journal revision,
owner, contract, profile, plan, fence and validity end; its fields explicitly
deny effect replay and ownership transfer. Those fields are not a provider
credential or an instruction for Console to impersonate the native owner.

## Owner-prepared native continuation

An actual current native agent can prepare one exact-session launch through
controller `record(kind=launch_prepare)`. Required fields are `permit_id`,
`authority_ref`, `token_sha256`, `expires_at`, `max_wall_seconds` and
`max_output_bytes`. The authority reference must already be in the current run
contract. Enrollment, current effects, native invalidation, waits, children,
inputs, instructions and resource admission must all permit continuation.

The agent generates a fresh cryptographically random token, submits only its
SHA256 digest, and supplies the token to the existing local Console adapter by a
private credential handoff. Never put a token in a browser request, URL, command
argument, journal, or logs. The plan does not authorize a browser to prepare a
grant. A grant expires within one hour and before the run deadline, permits one
native turn with at most 900 seconds and four MiB of transport output, and binds
its real issuer, exact native UUID, project, run, claim, contract/profile/plan,
artifact identities and runtime/attribution root. Unknown model/billing use is
not recorded as zero. Current workflow resource admission still applies.

The bounded deterministic entry point `prepared_native_launch.py` reads one
stdin JSON object with exactly `project`, `run_id`, `permit_id`, `token`, and
`runtime_root` (or null for the configured default). It accepts no actor, prompt,
command or executable. It initializes the existing owners, resolves the project,
inspects current issuer authority and consumes the grant under the existing run
lock. Its journal events identify a prepared-grant consumer explicitly; they do
not pretend that Console is a native agent. Submission rechecks the same fence.
Uncertain delivery and interrupted consumed grants cannot be retried blindly.

Grant mutations stay in `extensions.prepared_native_launch` of the same journal.
`record(kind=launch_cancel, permit_id, reason)` leaves a cancellation tombstone.
A running transport polls that tombstone and requests exact native turn
cancellation. Process termination alone is not proof of provider cancellation;
missing native terminal readback remains UNKNOWN. Native terminal success means
only that a transport turn ended: it never completes a Synthesis criterion or
run. The resumed native agent must authenticate its own identity and run the
ordinary resolver/admission/controller recovery protocol before taking action.

Delegated journal/projection writes go through the existing repo-guard
attribution owner. It verifies the committed one-use grant event and pre-edit
basis, current issuer, exact input set and exact changed paths, then takes the
existing lifecycle lock and atomic writer. Projection bytes must match the
owner's deterministic journal/plan compiler and the controlling human plan
basis; an allowed filename cannot authorize arbitrary content. It preserves
unrelated manifest rows and rejects a foreign manifest or concurrent producer
edit. It does not repair foreign
attribution, manufacture claims, publish, or create another authority database.

## Native transport and lifecycle evidence boundaries

The implemented transport uses Muse MSP `session/resume`, its native exclusive
writer lease, and `turn/start` with queue semantics. It binds the actual installed
versioned binary and refuses changed bytes, a different/forked session, an active
turn, wrong workspace or pending human request. It never changes native trust,
sandbox, model, provider or approval settings. The source contains finite tests;
release/native receipts must separately bind the actual installed binary.
Both directions of the stdio exchange are bounded, including write backpressure
and shutdown. A terminal needs a typed, exact-session source range and nonempty
cursor; malformed or foreign terminal data remains UNKNOWN. Native terminal
readback never attests the quality or completion of the Synthesis task.

Codex `turn/start` can steer an active turn and its exported contract has no
atomic idle precondition. Claude's background resume can copy an active session.
Neither is treated as safe exact-session mutual exclusion. Those transports
explicitly refuse automatic launch until their native ownership mechanism is
qualified; ordinary native-owned scheduling remains separate.

A11's Console surface is read-only. Connecting the existing Console process to
the stdin consumer and private owner-grant credential handoff is an explicit
integration and enrollment action, not an effect of viewing the page. There is
no new daemon. The existing request-only queue continues to report automatic
job launch unavailable; the prepared transport is a distinct finite capability.

A same-session local native turn does not establish survival after app exit,
logout, reboot, offline operation, machine loss or a machine transfer. Actual
first and later automatic wakes, independent overdue observation, cancellation
readback, native PM cold recovery and Console lifecycle installation remain
separate acceptance observations. Preserve the independent backstop requirement
until demonstrated equivalent behavior is accepted.

For operational health, inspect Console's existing lifecycle receipt, the queue
projection and `coverage.prepared_native_launch`. For upgrades, stop admission,
retain consumed grants, cancellation tombstones and uncertain effects, install
the reviewed owner package through the normal release process, then re-enroll
through fresh native admission. For removal, retire journal enrollment and use
Console's existing service uninstaller; verify both independently.
