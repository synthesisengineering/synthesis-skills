# Coordination lease refresh and authority fences

The coordination board is a local mirror of a configured Git lease ref. A
successful fetch establishes the read snapshot; a successful compare-and-swap
establishes authority at that ref. A cached mirror is never a write grant.

## Refresh modes

`lease_refresh(board)` and ordinary `coordination status` always fetch. Only
`status --passive-stop`, used by the passive part of the native Stop checkpoint
hook, accepts a previous successful fetch younger than 300 seconds. At exactly
300 seconds it fetches again. A hit reports `cache_hit: true`,
`refreshed: false`, its age and the previously fetched SHA. It never reports a
new remote observation. Wall-clock rollback or a nonfinite age is a miss.

The board-specific `.<board-name>.lease-fetch.json` stamp is local operational
state. Under the same `.active-sessions.lock` used by mutations, refresh reads
the lease configuration, validates a potential hit, fetches when necessary,
accepts the mirror, and atomically records the stamp. The binding contains the
canonical board path, remote, ref, lease repository path, mirror SHA-256 and
fetched Git SHA. A missing or changed mirror/configuration, malformed stamp,
symlink stamp or invalid time is a miss. The stamp is written only after a
successful fetch and mirror write. A stamp-write error leaves the successful
fetch usable for that call but cannot create a cache hit. A forced fetch failure
invalidates previous cached evidence under the lock. An unpublished configured
ref is not authority for a retained local board; only a mutation can bootstrap
the lease. A declared lease with missing configuration refuses.

Local lock ordering prevents a refresh from restoring stale bytes after a
same-machine claim or release. A mutation invalidates its old refresh stamp and
always fetches before examining or changing claims. A passive read checks the
current mirror digest, so it cannot overlook a completed local mutation.

## Paths that require fresh authority

Claims, releases, heartbeats, messages and other board mutations always fetch.
`check-staged` publishes an identity operation with `require_fence=True`; even
unchanged content retains its compare-and-swap fence and retry on a competing
advance. Its override revalidation uses the same requirement. Other mutations
may skip publication when their fetched content is unchanged, without skipping
the fetch. An unleased board is read under the local mutation lock.

Project resolution, active-pointer validation, peer resolution, live inbox
delivery and SessionStart always refresh. Peer resolution refuses to create a
delivery receipt after a refresh failure. Inbox failure emits an unavailable
notice instead of delivering stale messages or advancing a watermark. Its
native hook remains nonblocking to the prompt. SessionStart refreshes even when
there is no active-project pointer. Explicit no-refresh recovery and diagnostic
modes retain their documented local-only meaning; diagnostics do not update a
stamp, mirror, receipt or delivery watermark.

Before any checkpoint receipt is created, `checkpoint_project` obtains an
uncached lock/CAS-fenced board snapshot. This applies to both the direct CLI and
the native hook. The native hook rechecks its transcript/seat binding against
that snapshot; a released claim, changed native identity or unavailable remote
cannot become a receipt merely because the passive Stop observation succeeded.
The receipt binds the claim from that snapshot. A remote change after a
successful CAS is a subsequent transaction, not an extension of the receipt's
authority. Checkpoint validation still compares retained claim/state bindings.

## Recovery retention

Identical local board bytes are not rewritten and do not create a backup.
Changed bytes require a verified recovery copy before atomic replacement.
After successful replacement, pruning retains at most 200 generated regular
backups for that exact board, including the just-created copy even when the
clock moved backward. Other board names, unknown filenames, directories and
symlinks are preserved. A symlink backup directory refuses before writing.
Backup creation/verification or mirror-write failure does not prune recovery
copies. A pruning failure is reported as maintenance failure after the already
successful mutation, so callers do not retry a published operation blindly.

## Worktree discovery

Each `ClaimScopeResolver` lives for one board transaction. Ordinary lookups,
including a repeated exact scope, revalidate native Git root/common-directory identity.
Git resolves worktree configuration, global/system/environment configuration and
conditional includes; filesystem markers alone cannot establish that identity.
The effective configuration (with its origins) must remain unchanged across
discovery. Registered worktree listings are reused only for the same effective
configuration and unchanged common-directory registry, including configuration,
child `gitdir`, `commondir` and `config.worktree` files. Configuration or registry
changes during discovery refuse. Native probing also detects nested checkouts.
Unregistered, missing and ambiguous identities retain their refusal behavior.

Board validation gathers all unique physical prefixes before pair comparisons,
then uses those observations only for pure comparison within an explicit snapshot
context. Before any verdict returns, it revalidates every physical mapping and
native identity/configuration/registry observation. A changed mapping, newly nested
checkout, missing registration or changed/unreadable configuration refuses the
whole validation. The caller cannot publish authority or mutate protected state
inside that provisional context. This bounds subprocess work by unique scopes
instead of claim-pair count without making an unchecked identity verdict reusable.

No identity or ownership verdict persists between board transactions. Writers,
commit checks, project/inbox resolution and later Stop invocations construct
new resolvers. This is subprocess deduplication within a transaction, not a
time-based cache of authorization.
