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
The structured-question and cross-chat evidence forms below extend that reader.
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

## Native asynchronous answers

A Codex answer delivered by `request_user_input_async` can supply the human
observation. Keep the ordinary reply record locator; set `excerpt` to the exact
selected option and add this `question` object:

```json
{
  "offset": 1000,
  "length": 300,
  "sha256": "SHA256-OF-QUESTION-CALL-RECORD",
  "interval_sha256": "SHA256-FROM-QUESTION-OFFSET-THROUGH-REPLY-END",
  "call_id": "NATIVE-QUESTION-CALL-ID",
  "message_id": "NATIVE-USER-REPLY-ID",
  "question_index": 0,
  "title": "The exact question shown to the human."
}
```

The existing native question owner verifies one matching question call, its
`accepted: true` acknowledgment, and one later root-user reply. It binds the
question index, full title, offered options and chosen answer. The complete
interval is limited to 16 MiB and 16,384 records; every selected record is checked
by the native adapter. Its hash also binds the acknowledgment and intervening
records across admission and commit. Missing coverage refuses; a transcript
suffix does not substitute for an older question.

The original refusal of an unbound `<send_user_message_question_reply>` remains.
Assistant/tool/heartbeat content and a quoted response do not qualify. This
form records the full question and selected answer alongside the owner's
interpretation. A selected option is evidence of the human's choice, not a new
action-approval receipt.

## Human evidence from another Codex chat

The native run owner still renews the same recipient conversation. The source
conversation supplies the human evidence; it does not become the run owner.
A fresh message through the existing `send_message_to_thread` tool can carry
this exact JSON object as its prompt:

```json
{
  "owner_resume": {
    "scope": {
      "run_id": "EXACT-RECIPIENT-RUN-ID",
      "project_id": "EXACT-PROJECT-ID",
      "recipient_native_ref": "codex:RECIPIENT-NATIVE-UUID",
      "previous_owner": {
        "session_uuid": "EXACT-PREVIOUS-SEAT-UUID",
        "native_ref": "codex:RECIPIENT-NATIVE-UUID"
      },
      "basis_revision": 15,
      "basis_digest": "SHA256-OF-CANONICAL-OLD-STATE",
      "plan_digest": "SHA256-OF-CURRENT-HUMAN-PLAN",
      "restart_wait": null
    },
    "source_native_payload": {
      "session_id": "SENDER-NATIVE-UUID",
      "transcript_path": "ABSOLUTE-PATH-TO-SENDER-NATIVE-TRANSCRIPT"
    },
    "user_message": {
      "offset": 1400,
      "length": 250,
      "sha256": "SHA256-OF-SENDER-USER-REPLY",
      "excerpt": "The exact selected option.",
      "question": "THE-COMPLETE-QUESTION-OBJECT-DESCRIBED-ABOVE"
    }
  }
}
```

These are schema illustrations. Populate every value from the current recipient
run and native source records. `question` must be the complete object, not the
illustrative string. Include the exact `restart_wait` object in both the scope
and command when acknowledging a restart pause; otherwise the scope contains
null and the command omits it. A changed run revision, plan or wait requires a
fresh matching delivery.

Use the existing send tool with its current human authorization. A successful
sender response containing only `threadId` is an acknowledged dispatch, not
proof of delivery. On the recipient, locate the host's `response_item` of type
`function_call_output`, namespace `codex_app`, name `send_message_to_thread`, and
its matching `event_msg.item_completed`. The first record has no `call_id`; its
host metadata binds the receiver message/turn IDs. The second names the actual
recipient thread and the identical message ID and output. Supply their exact
record locators as the command's `user_message`:

```json
{
  "delegation": {
    "receipt": {"offset": 2000, "length": 800, "sha256": "EXACT-RECORD-SHA256"},
    "completion": {"offset": 2800, "length": 700, "sha256": "EXACT-RECORD-SHA256"}
  }
}
```

The receiving owner authenticates its native transcript, verifies the host
routing pair and exact scope, then independently authenticates the sender's
native transcript and re-reads the human question proof. The human answer must
postdate the old seat's release, precede delivery, and satisfy the original wait
chronology when applicable. Both native sources are checked again before commit.

The host's sender-user-message excerpt is partial historical context and does
not transfer permission. This protocol does not use it as authority. Plain
forwarded prose, a claimed approval, a sender tool result alone, nested forwards,
and a historical delivery lacking the exact evidence pointer all refuse. The
owner records the human evidence and its own interpretation separately; existing
action owners still decide authorization. No arbitrary JavaScript wrapper is
parsed or executed to establish this proof.

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

An elapsed workflow deadline remains elapsed after seat renewal. Reconciliation
may recover ownership without admitting more productive work. A terminal run
cannot be renewed. A newly authorized interval uses the existing
[successor transaction](successor-transactions.md), preserving the exact
predecessor head, costs and obligations; renewal never extends a deadline.
