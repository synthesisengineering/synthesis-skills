# Messages transport and recovery contract

`messages_boundary.send_with_owner(request, state, owner)` performs one guarded
attempt. `recover_with_owner(request, state, owner)` only reads evidence for its
existing fence. `messages_native.NativeMessagesOwner` implements the fixed
Messages script and confined outbound query. The enclosing authenticated owner
supplies approval and endpoint qualification; this skill issues neither.

Contents:
- Verified embedding boundary: the installed launcher route
- Explicit route and authority: account, chat, participant, approval
- Fixed transport: the fixed Messages script
- Immutable intent and readback: attempts, recovery, result states
- Source and qualification limits

## Verified embedding boundary

The installed read route is
`synthesis exec-public synthesis-local-messaging/scripts/local_messaging_cli.py -- --request REQUEST.json --state STATE_DIR`.
It calls the existing managed scan owner; it never exposes the internal worker
or accepts a send request. There is no public native-send CLI.

An authenticated embedding owner must obtain the verified active release through
the receipt-owned launcher runtime and call `verify_dependencies(active,
"synthesis-local-messaging/scripts/local_messaging_cli.py")` before importing
this release's adapter. That declared closure includes the reader, coordinator,
native adapter, outbound reader, `messages_transport.js`, and the transitive
sandbox/process/guard Python owners. Missing, linked, or changed members refuse.
Use only modules from that verified release; receipt verification establishes
source custody, not principal approval or endpoint qualification. The native
owner's fresh implementation checks and captured-source dispatch still apply.

Construct `NativeMessagesOwner(authority)` only in the authenticated enclosing
owner, then invoke `send_with_owner` or `recover_with_owner`. The authority
callbacks below remain mandatory. Do not deserialize an authority object from
JSON, call a raw worker, or treat a successful read command as send approval.

## Explicit route and authority

A native request has exactly these fields (all example values are synthetic):

```json
{
  "schema": 2,
  "request_id": "synthetic-send-1",
  "destination": "+15551234567",
  "text": "Please review the draft.",
  "route": {
    "account_id": "qualified-scripting-account-id",
    "service": "iMessage",
    "chat_id": "qualified-existing-chat-id",
    "participant_id": "qualified-participant-id",
    "database_account_id": "qualified-database-account-id",
    "database": "/absolute/authorized/database.sqlite"
  }
}
```

All route fields, destination, request ID and text enter the existing message
guard's `synthesis-message-v2` digest for `synthesis.messages.send`. The tool
must be enrolled as `human-text` in the complete capability registry. The real
dispatch guard consumes a fresh exact grounding ledger; peer-session lanes are
refused. Grounding does not establish principal approval.

The coordinator retains the guard's exact decision and effective configuration,
including the enrolled capability registry and its source locations. It checks
that binding after preflight and renewed authority, after writing the intent,
and at native process dispatch. These are read-only checks through the existing
guard owner; the grounding ledger is consumed once. The native dispatch uses
the coordinator's in-memory check, not a replacement decision loaded from an
editable receipt. Recorded policy data does not grant authority. These checks
detect observed changes before dispatch; they do not isolate policy files from
arbitrary later mutation by another process with the same user identity.

The authenticated caller constructs `NativeMessagesOwner(authority)` and calls
the coordinator. The authority implements:

- `authorize_send(payload, digest)`: confirm explicit current approval of the
  exact text and route, then return that digest with integer `expires_ms`. The
  grant must expire within five minutes. This method runs before the guard and
  again after preflight, immediately before the durable dispatch fence.
- `qualify(context)`: qualify the implementation/dictionary fingerprints,
  selected physical database/schema, permissions, and the relationship between
  scripting account ID and database account ID. Return the exact context
  digest only with that evidence. A request field or a fixture is insufficient.
- `authorize_readback(payload, digest)`: separately authorize a fresh recovery
  read and return the exact digest. An expired send grant does not authorize
  readback or a new send.

These methods belong to the enclosing trusted owner. Do not load an authority
from request data, manufacture one that returns expected values, or introduce
an approval registry here. That owner keeps one durable state directory for
one logical request, preserves it through interruption, and retains its current
approval and native qualification evidence. The generic schema-1 coordinator
contract remains available to separately qualified non-native owners; it now
also requires independent causal verification before reporting a sent result.

## Fixed transport

The native owner captures `messages_transport.js` and passes its fixed bytes to
`/usr/bin/osascript -l JavaScript -e`. The only variable argument is an anonymous
file descriptor number. Before process launch, the digest of those exact captured
bytes must match the attempt's qualified implementation. The canonical UTF-8 packet, including approved body,
travels through that private mode-0600 descriptor. Quotes, newlines, backslashes
and Unicode stay data; text is never inserted into script source or argv.

The script requires exactly one enabled, connected iMessage account with the
requested ID, exactly one existing chat in that account, and exactly one chat
participant with the requested participant ID, handle and account. It checks
expiry again after route resolution, immediately before one `send` call. It
has no retry, fallback service, recipient alias lookup, chat creation, or group
send. The existing finite process owner enforces a 15-second process deadline
and a 64-KiB output bound. Required Apple Events permissions and database access
must already be qualified through ordinary platform controls. This skill does
not change them or inject an IMCore bridge.

The Messages scripting dictionary exposes account/participant identities and
send-to-chat/participant, but supplies no returned message identifier. Its
qualified source fingerprint is bound in the implementation context. A successful
script return therefore records only that the command returned after dispatch.
It proves neither delivery nor a causal link to a database row.

## Immutable intent and readback

The existing descriptor-owned state writer stores `send.json` with
`EFFECT_UNKNOWN` before invoking transport. The native owner also consumes a
durable dispatch marker before starting the process. The original intent is
never rewritten. Exceptions, process loss, expired approval, partial receipts,
changed source, and unavailable readback retain the fence and prevent replay.
Do not delete or replace state to get another attempt.

`messages_outbound.py` implements the named `imessage-outbound-v1` shape. It
qualifies the required message, chat, handle and join columns, captures the
pre-dispatch maximum row and its GUID, and binds main-file identity plus schema.
Each query uses one read-only SQLite transaction, existing WAL/SHM sidecars,
denied source write access, a five-second query bound and the existing
15-second confined process owner. It examines at most 100 new rows; overflow
refuses instead of claiming complete readback. Source replacement, cursor
regression, anchor reuse and schema change also refuse. Ordinary later WAL
appends are allowed between snapshots; each individual snapshot must be stable.

Preflight, ordinary readback and recovery pass their expected implementation
digests into the confined worker launcher. Both captured reader modules must
match before execution; the launcher executes those captured bytes and retains
its post-execution source checks. A standalone `run_query` without a native
attempt captures a new read-only source generation; it cannot substitute for
an attempt's qualified reader identities. Native sending must use the
coordinator's guarded dispatch entry; a direct `NativeMessagesOwner.send` call
without its live guard check refuses.

The selected chat must have the exact database account ID and iMessage service,
with one member matching the requested recipient. New outbound rows must have
that chat, exact body digest and iMessage service. Bodies use the same bounded
decoder as the reader; unsupported typedstream remains unavailable. One matching
row with integer `error == 0` and `is_sent == 1` yields
`OBSERVED_MATCH_UNATTRIBUTED`. Missing, pending, failed or multiple matching rows
remain `EFFECT_UNKNOWN`. A human's matching row has the same unattributed
status, even if transport made no send call. Neither status establishes delivery
or recipient acknowledgement.

Recovery requires the original fence, fresh readback authority and exact source
qualification. It appends a chained observation without calling transport.
There are at most 32 observations and 66 query-worker directories per attempt.
Partial durable writes require owner reconciliation and cannot become a sent
claim. A separately qualified owner can produce `SENT_READBACK` only by verifying
an independent invocation-to-row link; exact text/time/route matching alone is
insufficient. Terminal reuse rechecks that verification. The native adapter
returns false for this capability because its scripting contract has no link.

The mode-0700 attempt directory contains approved text, route and readback
receipts needed to reconcile that exact request. Keep it private under the
existing state owner. This retained intent is not a transcript archive.

## Source and qualification limits

The field meanings were checked against pinned primary implementation source:
[database account fields](https://github.com/openclaw/imsg/blob/1aca78d212c888ef8b09d2abc2f3ca0b6d1f776c/Sources/IMsgCore/MessageStore%2BAccounts.swift),
[chat route queries](https://github.com/openclaw/imsg/blob/1aca78d212c888ef8b09d2abc2f3ca0b6d1f776c/Sources/IMsgCore/MessageStore%2BSentMessages.swift),
[message status reads](https://github.com/openclaw/imsg/blob/1aca78d212c888ef8b09d2abc2f3ca0b6d1f776c/Sources/IMsgCore/MessageStore%2BMessages.swift), and
[send status interpretation](https://github.com/openclaw/imsg/blob/1aca78d212c888ef8b09d2abc2f3ca0b6d1f776c/Sources/IMsgCore/MessageSendStatus.swift).
These support a named source contract, not universal account or schema support.
Scripting account IDs and database account IDs are different fields. Their
relationship requires actual endpoint qualification; never equate them by name.

Synthetic tests execute the fixed script under a Node app double and the real
confined query against WAL fixtures. They establish those source behaviors.
They do not exercise JXA's actual Foundation/Apple Events bridge, Messages
permissions, real account selection, outgoing phone-number behavior, a real
conversation, delivery, or causal readback. Those dimensions remain unqualified
until the enclosing owner obtains genuine observations. No fixture result
activates a send lane, ritual, scheduler or automation.
