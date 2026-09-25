# Same-native ownership after a released seat

PM identities are terminal after release. Reclaiming the same project in the
same native conversation correctly allocates a new seat; that alone cannot
change the owner of a retained autopilot journal. `owner.resume` connects those
owners through the existing run lock, event writer and host-local indexes.

This operation is distinct from transferring work to a different native
conversation. That still requires `owner.transfer.prepare` followed by
`owner.transfer.accept`. A missing predecessor, active predecessor, changed
native identity, changed machine/worktree/branch, pending handoff or terminal
run cannot use same-native renewal.

## Evidence and invocation

Use the ordinary `autopilot.py command` entry point with `--name owner.resume`,
the selected project/run, existing native actor, expected revision and a stable
command ID. Its payload has these fields:

```json
{
  "previous_owner": {"session_uuid": "PREVIOUS-UUID", "native_ref": "codex:NATIVE-UUID"},
  "basis_revision": 15,
  "basis_digest": "SHA256-OF-CANONICAL-OLD-STATE",
  "plan_digest": "SHA256-OF-CURRENT-HUMAN-PLAN",
  "user_message": {
    "offset": 1234,
    "length": 456,
    "sha256": "SHA256-OF-EXACT-NATIVE-JSONL-RECORD",
    "excerpt": "The exact direct-user paragraph being interpreted."
  },
  "reason": "The authenticated owner's interpretation of the user's resume instruction."
}
```

The owner computes the state digest with `run_state._digest(state)` and the
human-plan digest with `run_state._plan_digest(project, state)`. The user-message
locator points into the current native root transcript, not a copied artifact.
PM's production observer establishes the client identity and exclusive current
claims. The reader then verifies native producer identity, inode/header, complete
record boundaries, exact bytes, user origin, and a timestamp strictly after the
old seat's terminal timestamp. Quoted paragraphs, fenced and indented code,
HTML containers, tools, peers, child/metadata messages and known hook/heartbeat
injections are refused. Fence boundaries retain their opening character and
length; a different or shorter marker cannot expose an example as user prose.
Lazy blockquote continuation lines remain quoted until a paragraph boundary.

The current direct-user text reader covers Codex and Claude root transcripts.
Muse's raw user-intent envelope does not yet have a qualified direct-user text
contract; renewal refuses explicitly on that client rather than claiming an
opaque payload is human approval. Other client families likewise require their
production PM identity and qualified direct-user text reader before acceptance.

Native provenance is not a machine-certified interpretation of natural
language. The operation records the actual excerpt and the admitted agent's
interpretation separately, always with `authority_granted: false`. It does not
mint an approval receipt, add action scope, activate a schedule or replay an
effect. Existing action owners continue to enforce authorization.

## Acknowledging a restart pause

An optional `restart_wait` object names `id` and `sha256` of one exact pending
user wait. The run must be `waiting_user`, and the observed user message must
postdate both that wait's creation and the old seat's release. Use this only
when the current user has resumed the session that was paused for restart.

Existing wait records do not encode a typed reason category. The agent's
identification of that wait as a restart pause is therefore explicitly recorded
judgment, not semantic permission inferred by a string matcher. The original
wait row is preserved in `restart_acknowledgment.prior`; the journal also retains
it verbatim in all prior events. Only the named wait becomes resolved. Other
waits, external effects, permission gates, contracts and profiles remain intact.

## Recovery and verification

The new event changes the owner and sets `recovering`; it preserves the same
run ID, prior events, costs including unknowns, failed attempts, original
deadline, workflow, children, evidence, artifacts and contract/profile history.
It adds a provenance record to `ownership_recoveries`. Apart from the optional
exact restart-pause acknowledgment, it leaves all waits untouched. Follow with
ordinary controller recovery and the existing source/effect/worker readbacks.

Admission and source bytes are checked again immediately before append. A
changed claim, plan, source or stale expected revision fails without a new
event. Exact command retries use the existing idempotency contract; changing
the body or trying to consume the renewal again under a different ID fails.
Old and new owner indexes use the same interrupted-transfer recovery conventions
as the existing transfer operation. Ownership renewal proves neither native
continuation nor process-loss survival.
