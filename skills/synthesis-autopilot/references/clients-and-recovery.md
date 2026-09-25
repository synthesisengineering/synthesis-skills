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
