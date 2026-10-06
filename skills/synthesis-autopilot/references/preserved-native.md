# Preserved: 3.x native transcript decoders and worker transports

Verbatim text of synthesis-autopilot 3.6.7 reference files that v5 does not carry: native client surfaces, transcript evidence and archives, managed workers, extra-harness adapters and the Muse launch protocol. It is kept under ruling D8 so nothing is lost; the reason for each file is in [preserved.md](preserved.md), and where any kept rule went is in [coverage-map.md](coverage-map.md). Nothing here is current procedure. Links inside the verbatim text point where they pointed in 3.6.7 and may not resolve from this file.

## Contents

- [clients-and-recovery.md](#native-clients-continuation-and-recovery): Native clients, continuation and recovery (506 lines)
- [portable-native-evidence.md](#portable-native-evidence-and-memory-boundaries): Portable native evidence and memory boundaries (215 lines)
- [native-worker-persistence.md](#registered-native-session-continuity): Registered native session continuity (33 lines)
- [native-adapter-sdk.md](#additional-native-adapter-qualification-sdk): Additional native adapter qualification SDK (94 lines)
- [muse-launch-protocol.md](#current-muse-launch-protocol): Current Muse launch protocol (86 lines)

<!-- verbatim: skills/synthesis-autopilot/references/clients-and-recovery.md at 3.6.7 -->

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
native acceptance unknown. With the current `--actor`, it also diagnoses bounded
current Claude source bytes as described in the source doctor procedure below.
Run the existing conformance and PM doctors for
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

The interactive transcript adapter classifies records by their native channel.
An `attachment` has a closed, typed identity/envelope and a bounded opaque JSON
body. Its subtype and body fields do not grant semantics: environment snapshots,
hook output, queued prompts, tool listings, permissions, instructions and usage
inside that body all become digest-bound `context.attachment`. Unknown attachment
subtypes are equally inert. Optional `gitBranch`, `slug`, `rendered` and
`renderedInHumanTurn` fields and nullable `parentUuid` are supported. A qualified
child attachment remains confined to its exact native agent identity.

Presentation records (`last-prompt`, `custom-title`, `agent-name`, `mode`,
`atis-latch`), queue operations, file-history snapshots/deltas and UI cost state
become `context.metadata`. File-history records may omit `sessionId` only inside
an independently qualified source with an exact source locator; such a record
cannot qualify a source or supply identity. The closed interactive system
subtypes `compact_boundary`, `stop_hook_summary` and `api_error` become
`context.system`. Retained UI cost totals never enter measured usage.

Every context observation contains a record digest and source locator, without
copying context bodies. None is a fresh principal instruction, approval,
cancellation, execution effect, measured usage or completion receipt. Ordinary
user messages, tool calls/results and response usage retain their existing
semantics. Unknown top-level channels/system subtypes, malformed envelopes,
foreign or mixed identities and incomplete frames remain explicit gaps or
pending bytes. Large supported records use the existing bounded actual-byte
readback path, including message siblings with tool or usage data. The 1 MiB
record ceiling is unchanged; a projection never certifies an oversized record.
When a valid multi-fact message would overflow a page's event budget, its whole
frame is yielded for the next page. A single frame exceeding the event ceiling
still leaves a gap, rather than silently discarding material siblings.

### Source compatibility doctor

Before Claude interactive readiness or a new run, the agent uses the current
session's actor file, whose native payload supplies the transcript and identity:

```bash
python3 "$AUTOPILOT/scripts/autopilot.py" doctor --actor "$ACTOR"
```

The supported CLI verifies that native identity through the existing PM owner,
then decodes actual current source records through `native.read_page`. It does
not test an empty EOF enrollment. By default it examines at most the final
4 MiB, 32 pages and ten seconds, with a final exact-byte readback. The logical
span limit is separate from physical reads: each operation reserves its worst
case before I/O against a ceiling of sixteen times the logical budget plus
4 MiB by default. `--native-physical-byte-budget N` sets a smaller or larger
explicit ceiling, up to 512 MiB; the report includes reserved and completed
physical bytes. A ceiling or deadline exhausted mid-check leaves it incomplete. It emits only
counts, byte bounds, adapter identity and diagnostics; no transcript bodies are
copied. The returned `native_source.status` is PASS only when the entire required
diagnostic window was decoded and read back, with at least one record checked.
For a tail sample or explicit nonzero start, `source_history_coverage` remains
UNKNOWN and omitted bytes are named; negative authority coverage always remains
UNKNOWN. Appends outside the frozen interval are reported as uninspected bytes
and do not invalidate decoding of that interval. Rewritten inspected/header
bytes, malformed records or unsupported semantic channels fail loudly. An
incomplete required window is UNKNOWN. FAIL and UNKNOWN diagnostic checks give
the CLI a nonzero exit status.

For a bounded earlier interval, use `--native-from-byte N` and optionally
`--native-byte-budget N` (at most 16 MiB). Starts must be complete-record
boundaries. An explicit start requires coverage through the frozen source end;
a byte budget that truncates that required interval returns UNKNOWN. A completed
nonzero interval diagnoses only those bytes; it does not establish
absence of instructions or cancellation elsewhere. Inspect any failed offset
and report remaining coverage before making a native-readiness claim. Missing
actor evidence leaves the module-only doctor unable to establish native
compatibility. For other clients this probe is NOT_APPLICABLE; their doctor behavior stays
unchanged and native acceptance remains UNKNOWN without their existing
conformance checks.

This is a read-only diagnostic. It never admits a run, consumes principal
instructions, mutates peer journals, restores failed runs, counts provider cost
or proves native execution, installation, wake survival or owner authority.

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

<!-- verbatim: skills/synthesis-autopilot/references/portable-native-evidence.md at 3.6.7 -->

# Portable native evidence and memory boundaries

## What the archive preserves

The native observation adapters remain the identity and interpretation owners.
`native_archive.py` retains an explicitly selected, reviewed prefix of a source
as exact bytes, in immutable blocks owned by the existing run journal. The
journal's `native_archives` extension binds the descriptor, source generation,
offsets, hashes, source stat observation, adapter/codec hashes and routing.
Neither the descriptor nor a transport export grants authority.

Use the existing `autopilot.py command` owner with `native.archive.capture`,
`native.archive.export`, or `native.archive.restore`. Each operation requires
fresh PM/native admission and a source-backed `authority` receipt for that exact
request. The receipt data is `{approved: true, action: <command>,
request_sha256: <canonical request without authorization field>}`. It uses the
existing native-review authorization owner. Do not manufacture a native user
message from agent narration. The agent prepares the request and existing
native decision surface for the user; the user does not need to author JSON.
Already supplied authority must still cover the exact source and privacy route.
An unavailable native authorization adapter is a reported capability gap.

A capture request has `archive_id`, `source_id`, `route`, and `authorization`.
`source_id` names a currently enrolled root or admitted child/worker, not an
arbitrary remembered transcript path. The route is a strict object:

- `schema_version: 1`, current `project_id`, one `privacy_domain`, and
  `retention_class` of `permanent` or `engagement`;
- `classification: single-domain-reviewed`, `source_domains: [privacy_domain]`,
  exact `source_generation`, `reviewed_bytes`, and `reviewed_sha256`;
- `attachments`, an explicit inventory. A captured attachment requires `id`,
  that same `privacy_domain`, `status: capture`, absolute `path`, exact `bytes`
  and `sha256`. An absent body instead records `not-provided`, `not-authorized`,
  `unavailable`, or `opaque` with its ID and domain.

The domain declaration records the owner's actual review. The codec cannot
infer semantic privacy from a source path or content hash. Unknown or multiple
domains refuse before copying. Do not copy an entire mixed-engagement transcript
into every project. Use the established privacy/deletion-unit routing and retain
ALWAYS-PRESERVE material in its proper permanent owner separately. No cross-domain
store, automatic upload, automatic collection, encryption/key choice, retention
deletion or native memory setting is enabled by this feature.

A new snapshot may extend its prior exact prefix, including completing a
previous partial line. Changed prefixes, truncation, rotation, unsafe nodes,
symlink ancestors, hard-linked inputs, attachment drift or concurrent changes
refuse and preserve prior evidence. Review a new generation through the existing
source owner; do not silently reset the archive's earlier coverage.

## Available bytes and interpretation

The export contains exact `native.jsonl`, a deterministic `portable.jsonl`,
explicit captured attachments, and a final `manifest.json` commit marker.
The envelope separately binds the codec and normalizer used at export; the
original capture keeps its own version hashes. A later adapter upgrade must not
misattribute a regenerated view to the old normalizer.
Portable rows retain source order, raw offsets/hashes, native lineage and the
original structured record when within the bounded interpretation envelope.
Known roles, tool calls/results, compactions and child relationships use the
existing six native adapters. Unknown types, malformed records, opaque encrypted
values, large external bodies and partial tails remain explicit; exact bytes
are recoverable regardless of whether interpretation succeeds. A record may
contain multiple native observations. It remains one source record, so the
portable view does not pretend two projections are two conversations.

No decryption, hidden reasoning recovery, timestamp-based causal reordering,
attachment-path following, harness mutation or prompt replay occurs. Native
attachments that are not explicitly supplied are not fabricated. Attachment
discovery coverage remains `UNKNOWN`; a selected inventory is not an exhaustive
claim about a client's private attachment store.

`verify_export` checks membership, sizes and hashes without opening the original
source or importing native state. `restore_export` reconstructs the exact
immutable evidence blocks when both the original source and original store are
unavailable. The managed restore additionally requires a current registered
manifest, the same project/privacy route and new owner authorization. It does
not restore an old seat, a claim, an approval, or a client's configuration.
Archive/export integrity is separate from authentic native provenance.

Exports use a new directory and write the manifest last. A crash leaves retained
partial evidence with no success marker. Never overwrite that directory or
assume an ambiguous earlier operation failed. Inspect custody and choose a new
explicit destination. The run command's existing request identity and journal
replay prevent repeating an already committed export. A crash before the journal
commit can leave a complete unreferenced export; it is evidence to reconcile,
not a reason to replace it.

Bounds are deliberate: 64 MiB source prefix, 16 MiB aggregate attachments,
128 declared attachments, 16,384 records, 256 KiB inline interpretation per
record, 64 KiB raw blocks, 64 archive identities and 128 MiB aggregate logical
archive data per run. Existing journal-store ceilings also apply. Exceeding a
bound is a specific incomplete operation, never a truncated successful export.
A source larger than the prefix envelope uses the bounded one-generation stream
owner below. Never invent a rotation or split one actual generation into fictional
native sources. Product defaults remain finite.

## Retained native observation shapes

Decoder generation v14 accepts the closed forms for unlinked output metadata,
partial environment skill patches, nullable command-search paths and streamed
retained sender history. Unlinked outputs remain unpaired observations; missing
native call identities are never invented. Partial patches cannot establish a
complete world state, and retained text does not grant action authority.

Existing bindings require explicit generation reconciliation. Event-count,
usage, journal-storage, input-byte and process-time limits continue to apply;
schema acceptance does not establish that a whole retained history fits those
limits or that a managed native recovery was admitted.

## Large histories: exact bounded continuation

`native_archive_stream.py` reuses the existing native binding, authority receipts,
PM admission and immutable `journal_storage` codec. It adds no second state
ledger. `describe(binding, target_bytes=..., segment_bytes=...)` streams a bounded
proposal: one exact generation, reviewed target prefix length and full SHA-256,
contiguous absolute segment ranges/digests, framing offsets and observed source
identity. The proposal does not authorize capture. The source must remain stable
during that descriptor pass; no locking or modification of the native file is
attempted. Later appends do not alter the approved prefix and are explicitly
outside its coverage. A changed approved range, header, inode or generation
refuses; earlier retained segments remain available.

The agent prepares a `plan(snapshot, route, additional_capacity_bytes=0)` and the
existing source-backed native decision receipt. The stream route uses the same
seven identity/privacy fields above, without prefix length/hash or attachments;
those lengths/hashes live in the snapshot. Attachment discovery remains UNKNOWN.
Actual attachment custody uses the existing explicitly authorized prefix archive
inventory; the stream never follows paths mentioned in a transcript.

Managed commands run through the existing `autopilot.py command` owner:

- `native.archive.stream.plan`: `stream_id`, currently enrolled `source_id`,
  exact `plan`, `authorization`. The current native user receipt binds the entire
  plan and its finite added allowance. Registration reserves aggregate logical
  capacity before any source copy.
- `native.archive.stream.capture`: `stream_id`, `plan_sha256`, `index`. Each
  operation revalidates the original exact plan authority, current native source
  admission and current PM owner; it copies only that one approved range.
- `native.archive.stream.export.segment`: the preceding range fields plus a
  separate exact `authorization`. It writes a fresh segment directory under the
  claimed project evidence root. A replay uses the journal command identity;
  unjournaled partial directories remain ambiguous and are never overwritten.
- `native.archive.stream.publish`: `stream_id`, `plan_sha256`, separate exact
  `authorization`. It verifies every retained body and every exported segment,
  contiguous framing and the predeclared whole-source digest before writing the
  final portable manifest. Segment receipts alone cannot establish completion.
- `native.archive.stream.restore.plan`: a new `stream_id`, current registered
  `manifest_artifact_id`, the exact registered `manifest_sha256`, and fresh exact `authorization`. This permits evidence
  restoration only, not enrollment of the old native source or its approvals.
- `native.archive.stream.restore.segment`: `stream_id`, `plan_sha256`, `index`.
  It revalidates the current registered bundle and source-backed restoration
  permission before copying one segment to the current run's existing store.

The default aggregate logical capacity remains 128 MiB across prefix archives
and stream reservations. Only an explicitly authorized plan can add a finite
allowance, bound to that snapshot; it is not a grant to another account, machine,
project or privacy domain. The absolute admitted ceiling is 16 GiB per run,
64 stream identities and 4,096 segments. Each segment is at most 64 MiB; raw
blocks remain 64 KiB. The original journal store's 512 MiB ceiling is unchanged:
stream partitions call the same storage owner beneath the current run, and
aggregate prewrite accounting includes retained crash leftovers. New snapshots
and restores reserve their logical bytes separately, even if some bytes repeat.
No unlimited storage, implicit archival schedule or deletion is introduced.

Each bounded streaming verification pass has a 120-second deadline and a finite
byte/member count. The descriptor and final whole-snapshot verification may read
more than one segment without holding the whole source in memory. Large/slow
operations may refuse on their explicit bound and retain incomplete evidence;
that is not a successful archive. The surrounding execution owner retains its
process deadline and cleanup responsibility.

Portable stream directories contain exact `native.bin` segment bytes and
bounded `portable.jsonl` views. Fragments crossing a segment boundary and ranges
beyond the interpretation count are explicitly labeled raw references; they are
not dropped, invented or claimed as fully interpreted records. Complete bounded
records use the existing adapter with absolute source offsets and verified line
ordinals. Reconstruct the original available source by streaming segment bytes
in declared order. `verify_bundle` and managed recovery require the exact whole
SHA-256, framing, closed membership and current body bytes. Both the original
native source and original store may be unavailable. `COMPLETE` means the exact
reviewed snapshot is complete; it never claims the active source's current EOF,
all possible attachments, native authenticity or model compliance.

Both prefix and stream verification compare bounded no-follow directory/member
identity snapshots before and after the read interval. Root and attachment
additions, path replacement, hardlinks, changed bytes and late restore races
refuse before success or materialization. This is a verified interval, not an
atomic filesystem snapshot or a promise about external mutation after return.

## Memory is a lead, not an action capability

Native memory may suggest a question or a source to inspect. It cannot choose a
project over the current registry, replace the causal selected state, select a
foreign owner, revive released claims, change a source hash, expand the current
outcome contract or approve publication. Reconstruct these at the actual action
boundary through PM, current source and the relevant action owner. Recalled
receipts and portable archives remain data. No model-wide compliance guarantee
follows from mechanical source tests.

System/developer instructions and the user's current authorization remain above
skill guidance. Synthesis does not try to rewrite that hierarchy or disable a
host's capabilities. Keep native memory ON in every harness under the current
capture-buffer policy. Synthesis records win conflicts. Use the existing ritual
and context-edit ingestion owners; native export/clear capability remains a
separate qualification boundary. A local archive or ingestion receipt never
permits raw-file deletion, disabling memory, or an invented native clear result.

Run the synthetic boundary suite across Claude, Codex, Muse, Cursor, Copilot and
OpenCode adapter inputs. Run actual PM/journal consumer controls for stale owner,
source, routing, instruction and approval data. Treat unavailable native control
surfaces, current-client reload/trust, and actual cross-machine recovery as
explicit qualification gaps. Source tests and a self-contained export do not
establish live loading or native process-loss survival.

Both prefix `native.archive.restore` and stream `native.archive.stream.restore.plan` require the reviewed root manifest SHA-256 in the authorized request. An artifact ID is a mutable locator, never approval of subsequently re-registered bytes or increased capacity. Each stream segment rechecks that same digest and complete bundle membership immediately before materialization.

<!-- verbatim: skills/synthesis-autopilot/references/native-worker-persistence.md at 3.6.7 -->

# Registered native session continuity

This package extends the existing `delegation_boundary` native worker. It adds no scheduler, permission authority, account store or D3 study assignment.

The file contract may contain `native_session`, an exact `{artifact_id,path,digest}` member also present in `immutable_inputs`. Its closed JSON has schema_version=1, kind=native-worker-session, operation=allocate|resume, run_id, child_id, owner={session_uuid,native_ref}, source and account_scope registered file references, and predecessor_child_id (null only for allocate). Neither a supplied session ID nor a transcript path is admitted in this intent.

The supported persistent path is Codex's existing managed owner, bound to an explicit registered scoped account record. That record declares the exact model and effort; the current selected and native-observed values must match it. The product does not hardcode this evaluation's model or effort. Ordinary unscoped workers retain the existing ephemeral path. Muse/Hermes/Claude persistence is not claimed by this extension. The source reference must identify the accepted current activated release bytes; the execution account is source-pinned, current and bounded by the unchanged run deadline. Existing PM, claims, executable, permission policy and final pre-effect checks remain authoritative.

Allocation requires exactly native-callback and emits no model turn. A successful verified allocation may complete as model-free work, retaining protection UNKNOWN. It cannot prove protected execution. Its receipt records the actual native identity and bounded current transcript prefix after process cleanup.

Resume requires a productive capability and an exact predecessor child whose completed receipt is authenticated by both existing journal observation and evidence records, raw transport custody, current artifacts and freshness. Account, source, compiled profile, executable and integration owner must match. Failed/cancelled/incomplete predecessors, foreign identities, corrupt prefixes and an already-attempted successor are refused. An uncertain allocation is retained rather than replayed. Ancestry is finite (32). Every productive resume uses the same existing managed connection for fresh permission probes and the productive turn. A prior ENFORCED result does not substitute for this connection's proof.

The post-cleanup checkpoint binds the actual transport identity and exact append-only transcript prefix. Historical predecessor verification retains its authenticated output manifest; it does not require old output bytes to remain unchanged after an authorized successor. Immutable inputs and raw evidence still must verify. Ordinary completion continues to require current outputs. Full available native history can be exported through the existing bounded native observation/archive owners; this checkpoint alone is not a whole-history archive.

Original native failures remain failures. Source fixtures and an observed cold connection are separate from real OS process-loss survival and installed live loading. No native/provider call was performed by this package.

Allocation completion and independent integration consume the existing authenticated `native_worker` evidence. The integration review binds the actual native producer, not the parent dispatch identity, and requires that producer to match the verified receipt and recorded child observation. A copied receipt or changed child summary supplies no authority.

The complete source acceptance fixture drives actual PM admission, dispatch, journal observation, worker recording, return and independent integration through allocation, productive resume and a fresh-connection cold resume. Only native transport and installed-source observations are programmed. Current account/profile checks, source/claim freshness, uncertain predecessors and consumed attempts remain enforced. This fixture is not live native recovery evidence.

## Interrupted observer custody

A native observation has one original command identity and a private, exclusive local lease. The journal first records `prepared`, then `dispatch_fenced` immediately before invoking the existing adapter. The latter means an external effect may have started; it does not prove launch or termination. Cancellation records remain independently visible while the observer runs. Local process cleanup, observed native terminal status and unmeasured expense remain separate facts.

Use the existing controller `recover` operation with fresh current revision and the original authenticated actor. It first reconciles any original pending intent through `native.execution.recover`; it never launches the worker again. A still-held, replaced, aliased, malformed or foreign lease refuses recovery. The original board, native owner, claim, plan, profile, contract and registered check must still match. PID liveness alone never supplies authority.

When a process dies after the private lease was durably created but before the intent event, the exact original request may reacquire the retained lease. Complete journal replay must show no original prepare or dispatch; the lease must bind the same run, command digest and owner. Its inode, nonce and content remain intact. An active holder or unbound file refuses reuse; nothing is deleted or adopted by guessed ownership.

After `prepared`, an inactive lease and absent attempt directory permit the source-owned `not_started` disposition. After `dispatch_fenced`, a missing, partial, changed or unverifiable receipt leaves the intent pending and external effects unknown. Recovery accepts only the existing worker verifier's exact original raw receipt, file and executable evidence, nonce and cleanup proof. It commits the original result once, then an independent recovery acknowledgement. An interrupted acknowledgement may retry its exact request; a changed request cannot steal an original ID or replay execution.

An incomplete close can retain unresolved intent custody. A later exact receipt can reconcile that same original child while the interval remains incomplete with its original terminal record. The existing worker-record, return, independent native audit and integration owners can then settle that child's measured or unknown costs. Only new nonrequired, source-verified child-audit evidence can be registered on this narrow terminal path. Unrelated artifacts, work, allowances, successful/cancelled terminal intervals and foreign children remain refused. An undispatched child has no invented producer receipt or zero-cost measurement; its independent audit references the journal-proven child identity and retains unmeasured usage as unknown.

Historical unversioned intents without the original lease cannot acquire this proof retrospectively. Missing custody is an explicit unresolved obligation. Synthetic process-loss tests establish source behavior only; installed/native survival still needs its separately admitted real qualification.

<!-- verbatim: skills/synthesis-autopilot/references/native-adapter-sdk.md at 3.6.7 -->

# Additional native adapter qualification SDK

The additional adapters decode bounded observations for Cursor, GitHub Copilot, and OpenCode. They share the existing source reader and capability inventory. They do not authenticate a native producer, admit a run, grant a tool permission, or certify a task outcome. `assess()` keeps native and outcome cells `UNKNOWN`; a source file or a caller's `mode="native"` cannot change them.

## Implemented source contracts

| Client package | Input grammar | Useful observations | Qualification boundaries |
| --- | --- | --- | --- |
| `native_cursor` | Cursor documented hook inputs with `hook_event_name`; explicit capture route for IDE, CLI, or cloud | Session/generation IDs, tool-use IDs, structured tool results, interruption, compaction, subordinate child observations | No provider token schema. Child-stop without a child ID cannot cancel the root. Hook deployment and permissions require exact-surface native tests. |
| `native_copilot` | Documented camelCase and PascalCase hooks; SDK event schema from `@github/copilot-sdk` 1.0.14 | Session IDs, SDK tool-call IDs, API-call usage identity, root/child cancellation distinction, compaction and permission observations | CamelCase hook route must come from a retained capture envelope. Hooks lacking call IDs cannot be paired by adjacency. SDK previous-event links are retained but do not prove complete delivery. CLI, VS Code, and cloud are separate surfaces. |
| `native_opencode` | V2 event and SDK readback schemas from `@opencode/client` 2.0.16 | Session/parent IDs, durable sequence, tool-call IDs, direct-shell result and output range, response usage, compaction, interruption and permission observations | OpenCode V1 is a different protocol. A live subscription has no replay guarantee. Tool names on `session.tool.called` need their earlier identity event. A readback's session request needs owner-held transport custody. |

Copilot protection is **`FAIL_OPEN_PATHS`**. The official hook reference says command-hook timeouts and HTTP-hook failures can allow execution. A registered hook, a successful hook call, or this adapter's presence cannot justify a protected-client badge. Cursor's `failClosed` must be configured and tested on the selected surface; `preToolUse`'s `ask` result and `sessionStart`'s `continue=false` do not establish enforced approval. OpenCode permission replies are observed data; this package emits none.

## Python interfaces

Each package exports the same observation interface as the existing native dialects:

```python
qualify_source(header, *, expected_root_session_id,
               expected_thread_id=None, expected_parent_thread_id=None,
               expected_agent_id=None)
decode_record(row, producer, *, mode="synthetic", source_locator=None)
describe_contract()
is_ignored_projection(projected, producer)
record_sequences(row, producer)
```

`qualify_source` checks the declared native identity and lineage. Its returned producer always has `authentication="owner_admission_required"` and `root_authority=False`. Decode candidates carry typed facts, native IDs, source locators, and an explicit mode. Tool results always keep `outcome_pass=False`. User text never proves a human identity or grants authority.

The shared `native_observations` reader imports these packages through its fixed registry. It retains its bounded incremental reader, source generation and current-range verification. Capture order and OpenCode durable order are independent sequence lanes in the existing cursor. Repeated, reversed, or skipped sequence values refuse complete coverage. Suffix revalidation accepts `prior_sequences` only from the owner-verified cursor at its exact lower boundary; an arbitrary caller frontier is not evidence. Ingestion commits still belong to the existing admitted journal/CAS owner.

This package does not widen `observation_bridge` or PM root admission. An unsupported client cannot become a run owner merely by supplying a valid header. Existing owner commands reject a substituted additional-client transcript and preserve the journal. A future admitted native transport must join the actual surface, session, producer build, permission posture, and current source bytes through the current PM/native owner. It must not add a second journal or issue a reusable caller-controlled verification token.

The qualification SDK provides:

```python
capture_record(client, surface, event, payload, *, session_id,
               producer_version, capture_id, sequence)
inspect_source(path, *, client, session_id, mode="synthetic",
               max_pages=16, page_bytes=1024*1024)
assess(surface, *, required=(), source_report=None)
```

`capture_record` wraps a transport payload. The envelope is a provenance claim, not a signature. Retain the original native source and exact byte locators separately when transforming SSE, HTTP readbacks, or other wire formats into captured JSONL. Capture IDs, versions, sessions, and surface labels cannot change inside one source. The SDK refuses cached modules loaded from another source tree.

`inspect_source` invokes the actual bounded reader, reducer, and current-positive-range revalidator. It reports diagnostics, gaps, pending bytes, coverage and observations. Its source status `CURRENT` means those selected bytes decoded and revalidated within the reported scope. It does not mean complete native delivery, authenticated origin, historical absence, or current task acceptance. Positive event memory is capped at 512; use the admitted journal reader for longer runs. The JSON parser caps input at 1 MiB, depth at 32, nodes at 16,384, and arrays/objects at 1,024 entries. OpenCode assistant readbacks are capped at 64 content parts; larger material remains a reference/gap requiring bounded reconciliation.

`assess` obtains surfaces from the canonical capability registry and returns separate `documented`, `implemented`, `installed`, `native`, and `outcome` cells for ten capabilities. Required capabilities stay unresolved until their actual native/outcome owners supply qualifying evidence. JSON assertions such as `verified=true` and `native_provenance="VERIFIED"` cannot satisfy a requirement. Source availability does not change the existing surface levels: Cursor/Copilot remain skill-only, and OpenCode is observation-only.

## Strict JSON command interface

The SDK script accepts one JSON object on stdin and emits one bounded JSON result. It supports only `describe` and `inspect`; it has no action callback, native executor, installer, permission response, Goal, scheduler, or settings operation.

```json
{"operation":"describe","surface":"copilot-cli"}
```

```json
{"operation":"inspect","path":"/absolute/public-fixture.jsonl","client":"opencode","session_id":"session-public","mode":"synthetic"}
```

Unknown fields, duplicate fields, scalar requests, malformed JSON and nonfinite numbers return `UNRESOLVED` with a nonzero exit. The output cap is 4 MiB. Large transcripts use paginated native ingestion rather than an unbounded qualification response.

## Qualification procedure

1. Pin and verify the official client and schema artifacts before execution. Record the exact version, binary/package digest, surface, account boundary, permission configuration, source paths and bounded trial procedure. Installed discovery and `--help` output prove neither tool execution nor permissions.
2. Start with a public synthetic fixture. Through the real client, produce a harmless tool result with a unique native call ID and independently read the current result bytes. Retain failed/refused attempts. A direct API shell call proves only that local native consumer; it does not prove provider-driven tool use or approval enforcement.
3. Attempt a denied effect within the delegated test scope and observe the actual refusal. Test crash/timeout behavior separately where the official surface can fail open. Never bypass the native permission decision to make the test pass.
4. Observe an active cancellation and terminal readback with exact session/turn/child IDs. An idle `interrupted=false`, a request acknowledgement, a killed probe process, or a child-stop alone is not root cancellation acceptance. Keep all unresolved child and background work visible.
5. Test same-size tampering, truncation, replacement, missed notifications, partial and oversized records, duplicate response IDs, unknown grammar, sequence holes, provisional counters and root/child identity substitution. Revalidate current positive ranges at consumption. Keep cumulative/aggregate counters separate from per-response settlement; billing and full-tree scope remain unknown without independent proof.
6. For recovery and continuation, name the actual tested horizon and reconstruct the existing journal and source custody. Live event streams, retained state, manual resume, and scheduled delivery are different claims. No Goal, schedule, plugin registration, permission observation, or native success message can complete the portable task.

If authentication, a license, workspace trust, UI presence, or a user-owned permission choice is required, record the exact surface and missing action. The decoder and synthetic controls remain usable while those native gates remain unresolved. Do not replace a required capability with a simulated success.

## Primary specifications

The source contracts were checked against these primary interfaces on 2026-09-25:

- [Cursor hooks](https://cursor.com/docs/hooks) and [CLI output formats](https://cursor.com/docs/cli/reference/output-format). CLI print streams are not claimed by the hook decoder.
- [GitHub Copilot hook reference](https://docs.github.com/en/copilot/reference/hooks-reference), [CLI quickstart](https://docs.github.com/en/copilot/get-started/cli-quickstart), and [official Copilot SDK](https://github.com/github/copilot-sdk).
- [OpenCode V2 client](https://opencode.ai/v2/docs/build/client), [SDK](https://opencode.ai/v2/docs/build/sdk), [API](https://opencode.ai/v2/docs/api), and [OpenAPI schema](https://opencode.ai/v2/openapi.json). The experimental session log and live subscription have different retention contracts; a `log.synced` frontier alone does not supply historical records.

### Native call identity

Tool pairing requires a native call ID and the same source generation, producer,
mode and native call scope. Copilot SDK scope retains the actual `agentId`
(including the root's null value); Cursor scope retains `conversation_id` and
`generation_id`. Those raw scope fields participate in semantic identity and
current-byte rederivation. A root call cannot consume a child result, and a
Cursor result cannot reuse a call from another generation. Hook records lacking
a native call ID remain separate `missing_identity` observations even when their
names, arguments or positions match. Source currentness alone is not a paired
process result or outcome authority.

<!-- verbatim: skills/synthesis-autopilot/references/muse-launch-protocol.md at 3.6.7 -->

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
