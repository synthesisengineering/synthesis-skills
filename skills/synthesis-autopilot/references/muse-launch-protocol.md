# Current Muse launch protocol

The finite launch owner qualifies the stable interface exported by Muse
1.4.0-R4161.1, whose server identifies itself as 1.4.0. The exact fingerprint is
`sha256:36466f634c8c78a812462ec941187fd4547b232ee06153e5feb2a1482f0d3d7f`.
[Selected official definitions](muse-launch-protocol.json) retain the exported
fields, descriptions and source digest. They are definition excerpts, not a
complete JSON Schema or an execution receipt. The separately pinned historical
passive-wire adapter retains its own qualification; this contract does not
silently widen that adapter or reinterpret historical observations.

## Admission and handoff

A real Muse owner prepares a permit through the existing journal. The owner
adds `native_protocol`, which binds the supported schema and server version,
nonexperimental durable posture, and SHA256 of the launch, contract and preparation-owner modules.
The caller cannot choose that binding. Reservation and submission recheck it
under the existing run lock; process construction also rechecks it. A missing
or changed binding refuses new admission. Retained permits and consumed or
uncertain effects remain readable and must be reconciled; upgrading does not
mint a replacement permit or authorize replay. A fresh grant requires the
ordinary native owner, current policy, resource and identity checks.

`initialize` requests no extra capabilities, no experimental API and no user
input dialogs. Before `initialized` or `session/resume`, the response must
identify the qualified schema, server and POSIX platform, explicit durable
sessions and a typed bounded set of known capability grants. The protocol permits
policy-implicit grants. Observing `userShell` never authorizes calling it.
Unknown capabilities, versions or durability states require qualification and
are refused. Home and user-agent fields are validated but excluded from the
compact protocol receipt. Wire and executable digests retain their existing
custody role.

The exact `session/resume` request excludes items and has no config override,
new session or fork instruction. Its complete required metadata and history
must agree with that request: a nonempty observed cursor, explicit excluded
history, no pending human requests, no attention, the exact idle unforked
session and workspace, a durable absolute path and verified onRequest approval.
Missing fields are not reconstructed. Resumed approval is read, never changed.
Model, provider and reasoning-effort settings are not reconfigured. The native
schema describes a durable session reasoning default sampled at submission;
this observation does not prove the model or effort of an unexecuted turn.

## Delivery and terminal boundaries

The current stable `ifBusy` choices are queue, steer and replace; there is no
atomic reject-if-busy option. `session/resume` loads a session on the host and
subscribes this connection; it does not prove an exclusive connection lease.
Native sessionInUse errors, active state and pending requests refuse before
submission. An idle read can race: a well-formed queued acknowledgement is
recorded with its exact command and newly minted turn identity in the existing
single-use journal, then withdrawn outside the submission lock.

The owner sends one exact `turn/unqueue`. Its accepted reply alone does not
complete reconciliation: a matching `turn/unqueued` event must bind the session,
new queued turn, original start command, cursor and durable session source range.
If the exact unqueue command is explicitly rejected, the owner sends one
`turn/cancel` naming only that newly allocated turn, never an omitted or current
foreground turn. Rejection does not establish why unqueue failed. Cancellation
is proven only by that turn's valid terminal `cancelled`; other valid terminal
outcomes retain their own meaning. Unqueue and cancellation share the remaining
original wall budget and a ten-second cleanup ceiling. There is no new trial,
provider allowance, repeated submit or automatic recovery replay.

Malformed, steered or lost start acknowledgements never authorize withdrawal of
an unproven turn. They retain the exact attempted command with unresolved custody.
Lost/malformed unqueue acknowledgement, missing event, wrong identity or uncertain
cancellation remains UNKNOWN. Narrow withdrawal still runs when the post-send
journal fence refuses; process cleanup still runs after an interrupted withdrawal.
The known removal or terminal evidence is retained in `queue_reconciliation`;
the original raced launch stays UNKNOWN and its consumed permit cannot replay.

Only a started acknowledgement for the exact command, with a real returned
turn ID and `startedNewTurn: true`, reaches terminal observation. Terminals need
the exact session/turn, known disposition, nonempty opaque cursor and typed
ordered source range for that session or turn. Native failed terminals require
typed failure details; failure details on a nonfailed terminal are contradictory.
Even a well-formed native completion never accepts the Synthesis task. Native
FAILED stays failed; malformed terminals and uncertain cancellation stay UNKNOWN.

No request grants approvals, enables trust, changes sandbox policy, discovers
credentials or adds provider/network access. The existing output/wall/ack limits,
restricted launch flags, process-group cleanup and one-use journal gates remain.
Source tests and replay of a real initialize response establish interface checks
only. Native writer exclusion, model execution, enforced sandboxing, recovery,
app-exit survival and installed live loading each require their own evidence.
