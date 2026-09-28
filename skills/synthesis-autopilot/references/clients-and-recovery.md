# Native clients, continuation and recovery

Run `autopilot.py explain` for the canonical supported-surface registry, or
`explain --surface <id>` for one entry. Conformance and onboarding consume this
registry instead of maintaining conflicting support claims. An installed skill
is distinct from a wired hook, a live-loaded version, an observed wake and an
accepted user outcome.

| Surface family | Declared integration | What still needs live evidence |
|---|---|---|
| Claude Code CLI and desktop | Native lifecycle adapter | Actual client version, event path and requested continuation survival |
| Codex CLI and desktop | Native lifecycle adapter | Actual client version, event path and requested continuation survival |
| Muse CLI | Native lifecycle adapter | Actual wrapper invocation, normalized events and requested survival |
| Cursor IDE/CLI/cloud | Skill portability | Native hook and scheduling support for the exact surface |
| Copilot CLI/VS Code/cloud | Skill portability | Native hook and scheduling support for the exact surface |
| Hermes | Prospective | Installed integration and acceptance |

Do not generate Claude-shaped hook output for a different dialect. Cursor and
Copilot adapters have their own bounded response shapes; declaring an adapter
does not upgrade their support level. An unknown native client ends corrective
feedback with an explicit unresolved diagnostic.

## Native worker capabilities

The parent session and a launched child worker are separate surfaces. The new
native-worker adapter narrows one invocation to its declared file and tool roles;
it does not change the user's global client settings or remove ordinary native
features from a root session.

Claude and Codex worker adapters support file operations and a protected shell.
Muse's artifact-generation adapter uses a native model invocation with no tools.
The parent supplies bounded registered input bytes and validates structured UTF-8
outputs before materializing them under a fresh path admission. It exposes no
native Read/Write/Edit, shell or MCP capability to that worker. The tested Muse
custom profiles denied intended writes, and its hook parser permitted tools after
hook infrastructure failures; neither could establish the required boundary.
A child that needs a native file tool or shell is rejected by this adapter.
The parent can still perform that work through its ordinary authorized native
session; the adapter does not remove those features from Muse itself.
The declared capability and an actual successful invocation remain different
facts. Other client surfaces do not acquire worker isolation from skill loading.

Worker capabilities describe available operations; write-preservation does not
claim that Claude or Codex can read only the listed files. Any broader read
restriction needs its own actual evidence. Declare the operations a child
requires, immutable registered inputs, separate
output and scratch roots, deadline and resource reservation. Fresh PM admission
is still required. Keep native startup/readback, actual tool results, producer
identity and preservation observations. An unchanged file alone cannot prove
that mutation was prevented. Authentication/runtime read exceptions are narrow
implementation requirements, not permission for a model to inspect private
files. File read/write isolation and shell-network isolation require their own
positive and negative evidence.

Timeouts retain partial native evidence and known identity/usage; absent provider
usage stays unknown. Cleanup observes process identity and reports unresolved
children. It does not claim that polling detects every possible detached process.
A worker's terminal turn is neither a task-quality verdict nor parent integration.
Only artifacts actually observed in its output manifest may be attributed to it,
and integration cannot replace its measured usage with a smaller estimate.

## Stop behavior

The installed verified launcher contains infrastructure/import failures at the
native boundary. Autopilot also normalizes the host's repeat indication and
loop bound. An unresolved active run can request a supported bounded correction.
A repeated or infrastructure failure ends feedback explicitly unresolved. This
ends the feedback loop; it does not certify completion, discard manifests or
disable pre-mutation protection.

Stop reads only indexed records for the current native identity/seat. It never
runs model inference, consumer programs, network fetches or a global legacy
inventory. Current PM admission and evidence remain required. Released terminal
runs retain their stop-safe tombstones; released unfinished ownership cannot
authorize continued mutations.

The combined Stop entry loads PM's native identity observer directly, including
in a fresh process with no session-reference environment hint. Surface labels
select the response dialect; they never establish ownership. Native transcript
evidence is required before treating an empty runtime as having no owned work.
A verified native identity with only closed indexed engagements produces no
autopilot warning. Missing identity, conflicting surface hints and unfinished
owned work remain unresolved without creating repeated corrective turns.

## Continuation is observed

Capability records name the exact surface, version and survival horizon. Native
registration/listing proves a job exists, not that it will execute. Observed
first and later wakes, validity intervals, run binding and an independent
overdue observer establish the narrower guarantee the adapter supports.
Session death, expiry, revoked ownership and unsupported reboot survival stay
unresolved; a file containing a job ID is insufficient.

For Claude's same-session `turn_end` path, the worker and independent overdue
observer form one bound pair. A replacement worker needs its own observer;
deleting a prior pair cannot prove cleanup of its replacement. Cron deadlines
derive from the actual local-time schedule plus the native jitter allowance.
That derivation is a deadline model, not a host execution guarantee. Registration
starts with `awaiting_first_wake`; only observed first and later wakes establish
verified continuation within the currently admitted lease. An elapsed initial wake
deadline rejects a new registration but does not invalidate the historical
registration of a still-live pair. Every later wake is checked against its own
derived deadline, the current pair and the lease.

Keep a live pair admitted with an explicit `continuation.renew` before its lease
expires. First obtain a new native `CronList` containing the unchanged worker
and backstop. Register a `continuation-renewal` observation specification with
`readback_call_id` and `previous_lease_receipt`, run that observer, then submit
its receipt to `continuation.renew`. The new expiry remains at most five minutes
after that actual readback and cannot exceed the original capability or
registration receipt's expiry, nor any previous lease receipt it depends on.
The command cannot revive an expired, overdue or cancelled pair, change its
owner, or erase its observed wakes and next deadline. Renewal is not a wake.
It does not promise indefinite survival: complete fresh observed recovery and
re-registration before those evidence boundaries, including observed
cancellation of the old pair before admitting its replacement. Keeping the same
job IDs or extending a receipt file cannot extend that authority.

Later wake specifications retain the original `registration_receipt` and name
the current `lease_receipt`. Choose a fresh native list completed **before** the
exact wake's enqueue; a list produced in response to that wake cannot prove its
prior registration. Admit intermediate actual wakes as they arrive, and renew
while the pair remains live. Historical receipts retain only their exact
reducer-admitted fingerprint and intake time. Their native bytes, current
ownership and receipt expiry are still checked; a new stale or backdated
envelope gains no historical exemption.

Native tool receipts are parsed from authenticated local transcript evidence,
paired by tool-call identity and restricted to supported non-executing APIs.
An arbitrary shell command cannot mint scheduler or delivery evidence. Current
evidence may be unreadable in an encrypted transcript; report that limitation
instead of inferring its contents.

Use `continuation.cancel` to record intent before requesting cancellation through
the owning host API, then `continuation.cancel-confirm` with observed deletion.
Closing the run creates a tombstone that rejects a late wake. Failed cleanup is
still reported; the tombstone is not proof a host job disappeared.

## Waits and human visibility

Each user/external wait has an identity and explicit resolution. Successful
progress cannot silently erase unrelated waits. Notification receipts bind the
current pending wait set, question content and native delivery event. Unrelated
later bookkeeping may preserve that binding; adding a new wait invalidates it.
A queued message is not delivered. A muted alert is suppressed, not delivered.
Voice/banners use generic counts and a private-detail pointer; actual details
stay in the permitted private report. A blank UI pane is not evidence the agent
stopped, and a spinner is not evidence useful work continues.

## Diagnosis and migration

`autopilot.py doctor` checks module/schema availability and explicitly labels
native acceptance unknown. Run the existing conformance and PM doctors for
their owning boundaries. A module import check cannot prove the whole system.

Before switching an existing installation to the new engine, run:

```sh
python3 "$AUTOPILOT/scripts/autopilot.py" doctor --index-legacy --actor "$ACTOR"
```

This explicit maintenance operation builds a host-local index from bounded
legacy-record reads. It preserves every source byte and does not adopt a run.
An immutable index generation commits atomically. Stop subsequently reads only
the selected native/seat records. Unknown/unassignable legacy records remain
visible in the inventory report without blocking an unrelated owner's run.
Corrupt selected records remain a fail-closed recovery problem.

Explicit indexing also preserves Claude desktop host-to-native bindings observed
from exact PM seat sidecars. These discovery records survive sidecar removal on
release and later inventory refreshes; they never restore active claim authority.
If release erased the only binding before indexing, the inventory reports the
unfinished record as unattributable. Only an explicitly selected plan makes that
unbound record a blocking recovery question; unrelated Stop events do not adopt
it. Closed legacy records need no continued execution and remain quiet.

A nonempty legacy registry without an index produces one terminal unresolved
health message naming this doctor action. The agent performs it within existing
authorization; do not ask the user to run a shell command. Import only an
explicitly selected owned engagement. Preserve source bytes, historical profile,
waits and terminal evidence. Rebuild current acceptance; an old success receipt
is not fresh evidence. If older sessions add engagements during upgrade,
refresh the index at the migration checkpoint.

On recovery, resolve the project first, establish current identity and exact
ownership, read the authoritative journal, reconcile outstanding effects and
children, validate artifact hashes and find the next ready obligation. A
portable capsule references registry, native-claim and input observations plus
the actual remaining criteria. A copied summary alone cannot prove continuity.
Preserve foreign runs, claims and manifests throughout this process.

### Explicit Codex managed permission ownership

A registered delegation file contract may include `permissions: {source, profile}`.
`source` is an exact immutable input reference; its JSON bytes must describe the
same closed `profile`. The profile names the current native executable, exact
read/write/deny paths, disabled network, and `approval_policy: never`. Write roots
must equal the existing output and scratch contract. The existing delegation
owner checks current PM admission, source bytes and path identity before launch
and before an effect. The profile compiler uses the current native `deny` value;
it does not rewrite global configuration or use a legacy sandbox flag.

The managed app-server connection verifies actual configuration and returned
`activePermissionProfile` before an effect. Its send boundary accepts only the
exact precomputed request sequence: initialization, configuration readback,
thread start/read/resume and the individually admitted turn or fixed probe.
Every process endpoint, `thread/shellCommand`, unknown alias, unsolicited approval
response and reordered or changed request is refused before transport write.
Named profiles require the official experimental schema opt-in. That opt-in is
local to this restricted connection and grants no additional execution authority.

`native-callback` observes context delivery without a model turn.
`native-permission-probe` runs only the registered canonical `native_protection.py`
producer and its exact registered specification on the same connection/profile.
The parent first proves readable and denied canaries exist and a nonce listener
is healthy, then verifies the same canaries and listener after the command. Only
EPERM/EACCES proves a tested denial; absent files, connection refusal and timeout
do not. The authenticated worker receipt can qualify `ENFORCED` solely for those
observed filesystem/network controls. Configuration, exit zero, copied probe JSON
and caller-provided PASS cannot qualify it. This observed result flows through
existing worker recording, native observation, vendor evidence and child return
owners; signing, publication, cold recovery and other hosts remain separate.

The same owner supports a separately admitted model-free persistent allocation
for an exact-session study. It requires `persistent_allocation: true`, only
`native-callback`, and `allocation: {account_scope, source_generation}`. A current
owner revalidation callback authenticates the account/source and decision before
thread creation. The returned persistent idle identity and real transcript are
read back and pinned. Allocation emits no turn or command. An uncertain response
is retained as incomplete; the owner does not automatically retry it.

Ordinary study work calls `managed_native.execute(..., revalidate=..., resume=...)`
with the admitted `session_id`, exact transcript prefix `{path, sha256, size}`,
account-scope pin and source generation. The owner reads the native thread before
resume, rejects busy/foreign sessions, explicitly selects the named permissions,
verifies configuration and idle state again, and revalidates current authority
before the exact turn. No path/history override or replacement ephemeral session
is permitted. The transcript may grow, but its original approved prefix must
remain byte-identical. Actual expense accounting continues to use that original
native transcript; the transport does not invent usage values. Response and
request captures remain available to the actual study consumer.

These mechanisms and synthetic fixtures establish source behavior. Installing
bytes does not prove live loading, native enforcement, callback trust, accepted
model work or recovery. Real qualification must use current installed/source,
account, native identity and admission evidence through the existing owners.

### Protected productive turns and exact current account

An ordinary managed worker now performs the canonical read/write/network probe,
checks the host canaries and healthy listener before and after that probe, rereads
the active profile and idle session, and sends the admitted turn on that same
owned connection. It rechecks the host controls after the terminal turn. A prior
probe, configured profile, copied result, or successful command alone cannot set
`ENFORCED`. The stored current-connection nonce, exact probe request, native thread
and turn, profile, raw request/response streams, and source receipts are replayed
through the existing PM observation, vendor and child-return consumers.

The managed-turn source dialect validates the current official typed item, hook,
turn and usage grammar. Missing pairs, foreign identities, unknown methods,
malformed fields, partial terminals and mutated source bytes remain incomplete
or refused. The typed helper participates in the source adapter generation.
This qualifies the admitted foreground turn only; complete native hook coverage,
live desktop loading and cold recovery remain separate observations.

Scoped study allocation and exact persistent resume additionally use native
`account/read` with `refreshToken: false` on the same connection before session
effects and again immediately before a productive turn. Actual ChatGPT account
routing must match the existing pinned evaluation-account digest, OpenAI must be
the effective provider, and alternate provider definitions are refused. This
reads no credential values, changes no login or global setting, and supplies no
new account authority. The parent owner still revalidates machine, account,
source, deadline and admission at the actual write boundary. Uncertain persistent
allocation is retained without automatic replay.

The shared finite RPC owner rejects unsolicited, duplicate and future response
IDs before another request can use them. An already-started fragmented frame is
completed under the existing byte/time bounds before a new request is emitted;
legitimate asynchronous notifications remain permitted. The managed owner also
refuses turn-specific notifications observed before its productive request.
These checks bind captured transport order, not a claim about unobserved bytes.

Completed item notifications cannot retain an in-progress status. Every item
actually included in a terminal turn snapshot must match a uniquely observed
completed item; unseen, duplicate or contradictory entries remain refused. An
omitted snapshot entry is not fabricated into an observation.

Admitted file and managed-profile reads retain no-follow directory and file
descriptors through the bounded read and verify identity, mode and byte stability
before returning content. They keep the existing 16 MiB artifact and 128 KiB
profile limits, with at most 256 ancestry components and a ten-second read bound.
Profile decoding consumes those exact bytes; a second pathname read cannot race
the admitted digest. Unchanged hardlink metadata remains available to the
existing role-specific authority checks.


## Interactive Claude context records

The interactive transcript adapter recognizes the closed native shapes
`attachment.edited_text_file`, `attachment.total_tokens_reminder`, `last-prompt`,
`custom-title`, `agent-name`, `mode`, and `atis-latch`. Attachments become
`context.attachment`; presentation and context metadata become
`context.metadata`. Each observation retains its exact source locator and a
record digest. Bodies remain source material: file excerpts and rendered text
are not principal instructions, the prompt summary is not a new user message,
a token reminder is not measured expenditure, and a mode/name field does not
establish permissions or identity. No text is executed or promoted into a
permission, completion, usage, wake, or recovery receipt.

Only the observed closed shapes are supported. Unknown fields/subtypes,
malformed nested values, foreign identity, print-stream records in an
interactive source, and incomplete frames retain explicit gaps or pending
bytes. Existing native user-message invalidation retains precedence before or
after these context records. This support does not qualify unobserved child
attachment envelopes or other lifecycle records.

A decoder upgrade changes the source-generation binding. It does not reset an
existing cursor or erase an original failed generation. Use the existing
`native.reconcile` command with the exact prior generation and cursor digest to
reread an explicit bounded interval, then use `native.observe` for catch-up.
Re-reading from the original enrollment offset can establish current parsing
coverage while keeping the old gaps in journal history. Selecting a new interval
alone does not resolve the previous invalidation scope: current execution
admission stays UNKNOWN without the existing genuine native-user resume receipt.
The receipt must bind the exact prior invalidations and current user record;
attachment content, titles, and `last-prompt` cannot supply it. A general
whole-original-interval replay reconciliation without that receipt is not
implemented by this schema change. Do not change the old journal or infer its
outcome from successful local parser tests.

### Bounded replay of the original enrolled interval

`recover` with `reconcile_sources: true` detects a decoder-only generation change
on the same exact native source and starts `native.reconcile` replay. An explicit
`mode: replay` reconciliation binds the prior generation and cursor digest; it
cannot choose a later start offset or supply a resume instruction. The existing
`autopilot.py recover` command drives the finite sequence inside one external
operation, keeping the enrolled transcript unchanged until that operation returns.
Each internal `native.observe` commits one bounded validation step in the existing
run journal. No transcript, provider, configuration or effect is written. A live
producer that appends during the operation invalidates its snapshot; the driver
does not conceal or accept that mutation.

Replay checks every retained generation's range hashes and enrollment anchor,
then the exact old indexed event batches, then the entire original enrolled
interval under the current decoder. Source identity, pathname ancestry, size,
mtime/ctime, link count, cursor, enrollment and range digests remain bound across
steps. The per-step source page and witness ceiling is 1 MiB; old-batch lookup has
the existing 8 MiB consumption ceiling and successor depth bound. Existing event,
generation and journal storage ceilings remain in force. Current controller
coverage reports phase, verified witness/batch counts and decoded frontier.

Only complete unchanged replay can reconcile a decoder gap. A prefix, interrupted
page, unknown schema, changed or aliased source, conflicting meaning, missing old
event, capacity exhaustion or partial frame leaves the interval UNKNOWN. A failed
replay is retained and does not restart on another ordinary recovery request.
Its concrete failure must be reconciled explicitly. A later source change makes
completed snapshot coverage stale and requires another bounded reconciliation.
These are current readbacks, not simultaneous filesystem snapshots or permission
proofs.

Original events, invalidations, failed gaps, costs and run outcomes remain in their
original journals. Identical observations are validated without charging usage
again, changing tool-pair outcomes or issuing effects. Newly observable facts are
recorded as observations only. Prior invalidation IDs are revalidated under the
new decoder only after their exact semantic correspondence has been established;
a cancellation stays invalidating. Already committed native observations in a
successor are read through their exact batch digest and the existing owner-linked
lineage, never by assuming its revision belongs to the successor's directory.
Pre-enrollment scope and actual client/process survival remain UNKNOWN. Closed
runs are not reopened, and no fresh user authorization is manufactured.

The optional `replay_limits` request object has exactly four positive integer
fields: `steps`, `bytes`, `sources`, and `wall_millis`. Defaults are 128 steps,
64 MiB of conservative validation-read allowance, eight sources, and 30 seconds.
Explicit request ceilings are 4,096 steps, 16 GiB, 64 sources, and 900 seconds.
A larger interval can require a larger explicitly declared allowance within those
ceilings; the driver does not automatically refill it. The byte charge covers
original range, semantic component and native page validation with fixed reader
revalidation allowances. PM resolution, journal admission/commit and final
readback retain their existing separate bounds; this is not a claim about total
filesystem I/O or model tokens. One already admitted finite owner transaction may
finish after the wall deadline, but no new validation transaction may start.

Bounds belong to the exact existing request digest. Its committed recovery-admit
time anchors the deadline, capped by the original workflow deadline. Source
membership, dense step ordinal, action and conservative byte charge are recovered
from the existing journal request steps. A charged step binds the inspected run
revision before its effect, so an intervening transaction cannot silently change
its phase. Reissuing the same request after interruption resumes that exact
committed prefix without resetting counters or time. Changing a bound under the
same request ID is refused. A newly admitted distinct request is explicit work,
not an automatic retry; it retains prior outcomes and costs.

`coverage.replay_driver` reports committed steps, charged validation bytes, source
frontiers, original start/deadline and the exact limited, interrupted, unknown or
complete disposition. Exhaustion returns RECONCILE without an extra catch-up.
Complete means this finite validation finished; current source readback, original
invalidation, user cancellation, run termination, native protection and survival
remain separate gates. No human authorization is inferred from a completed
replay, and the command makes no native or provider calls.


### Protected work after original-history recovery

A complete original-history certificate binds one exact native source snapshot.
A normal tool/result append makes that certificate stale until the existing
replay owner validates the previously certified bytes and the new tail. The
controller performs this finite preflight for protected next/start, dispatch,
attempt/progress, effect preparation, native-worker observation, launch
preparation, productive supervision and completed finish. Cleanup, cancellation
and read-only inspection remain separate. Direct low-level mutation owners
continue to refuse stale native evidence; a preflight never waives their fresh
commit-time checks or grants an external effect.

For the same source identity and decoder, refresh checks each retained prefix
range once and decodes only the new tail under a stable source stamp. It keeps
the source generation, historical semantic aliases, original enrollment,
cancellation and failed dispositions. Benign growth does not spend decoder
generation capacity. Decoder changes still require full semantic replay.
Every source read remains bounded; a changed prefix, unsupported tail, incomplete
record, failed refresh, changed source during validation or cancellation prevents
protected admission. A changing source is not treated as append-only merely
because its size increased.

The existing default replay envelope remains 128 steps, 64 MiB conservatively
charged validation reads, eight sources and 30 seconds. A protected facade
request can declare a closed top-level replay_limits object with exactly steps,
bytes, sources and wall_millis. The command/observe CLI accepts the same object
as --replay-limits pointing to a bounded JSON file. The existing caps remain
4096 steps, 16 GiB, 64 sources and 900 seconds, also bounded by the run deadline.
Large histories require an explicit adequate finite declaration; defaults do
not claim to cover arbitrarily large transcripts. Actual native data may remain
UNKNOWN when the admitted envelope cannot complete validation.

Each protected request uses the existing journal's recovery admission, source
reconciliation, charged observation steps and readback. Same-request retries
retain the original timestamp, deadline, counters and committed prefix. They
cannot replenish an exhausted allowance or repeat a committed effect. A
controller record with kind protected_command names only an existing supported
productive command, its exact payload and original command_id; the existing
command owner still supplies all authorization and effect semantics. The
CLI routes the corresponding protected command/observe calls through that
facade. There is no new scheduler, permission ledger or model loop.

Source tests qualify this producer/consumer contract only. They do not establish
live hook loading, host survival, native cold recovery or comparative superiority.
