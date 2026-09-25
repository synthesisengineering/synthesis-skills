# Operator status and handoff

A user delegates an outcome in ordinary language. The agent resolves the project,
prepares its controlling plan and completion contract, and invokes the existing
controller. The Console's first-task form composes that delegation; it does not
create a run, invent a native actor or grant new authority.

`operator_status.py` is a read-only projection of the existing run owner. It
streams and validates the selected event chain, checks the project binding, and
keeps current projections subordinate to the journal. Missing or stale derived
files prompt an owner rebuild. Corrupt chains and redirected or oversized paths
produce an unhealthy result. Discovery returns eight runs per page, with a
maximum page size of 32, a 4,096-entry inventory ceiling and a 32 MiB bound per
journal. Filesystem recency orders discovery only; it does not establish progress
or authority. Cursors bind the exact project inventory and page size; a changed
inventory requires refreshing the first page. Older runs and their retained
questions remain available through page links. Each question page states its
coverage, and an exact run can be selected independently. These are operator-read
limits, not completion or resource-policy thresholds.

Console registry selection invokes PM's existing causal resolver with fetching,
canonical fast-forward and coordination refresh disabled. A newer attributed
worktree can supply the selected journal while the canonical checkout remains
unchanged. Conflicts and unknown recovery state show explicit diagnostics with
no canonical fallback. The response binds the registry path and bytes, selected
physical project, causal head and tree. This selection grants no native identity,
claim, write permission or fresh completion acceptance.

The view distinguishes recorded work, waiting, unhealthy recovery, completed and
cancelled runs. A recorded terminal result does not establish current artifact
acceptance. Native liveness, actual notification delivery, loaded-session code,
billed usage and continuation remain unknown without their respective current
owner proofs. Last useful progress comes from the workflow's meaningful progress
records; narration and the journal update time are not native heartbeats.

Pending questions are available through the Console's source-gated question
fallback. Rendering, preparing or copying an answer changes no wait. The current
authenticated native owner must match the pending question and use the existing
wait-resolution evidence path. No Console answer is an approval receipt.

Recovery and cancellation handoffs retain an exact run, request identity and
expected revision. The user copies them into the owning native task; the owner
performs current PM/native admission and controller CAS. A prepared request is
not queued, performed or acknowledged. Replays follow the controller's existing
idempotence rules. A cancelled run may still retain unfinished child, effect or
continuation cleanup; cancellation is not verified termination.

For a damaged installation, use existing onboarding and skills-manager doctor,
repair and update owners. Preserve evidence before repair. Updated installed
bytes do not imply an already running task loaded them. Checkpoint and recover
with freshly loaded skills through the normal native owner when required. A cold
recovery starts from the project registry and journal, then reconciles authority,
inputs, effects and children. A recovery capsule conveys references and duties;
it cannot transfer ownership or prove survival.

If the A9 supervision owner is present, its bounded `status_view(state)` supplies
historical queue, lease, backoff and cancellation facts. The Console does not
create a second queue or actor. Request completion means the owner subsequently
observed its bound native wake; it does not prove this display caused the wake
or that the user's task finished. Automatic launch from this Console remains
unavailable. Primary-pane loss is qualified separately from machine or process
survival, and a readable local fallback is not a delivery receipt for an OS
notification.
