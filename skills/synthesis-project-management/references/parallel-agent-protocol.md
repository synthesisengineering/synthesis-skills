# Parallel agent protocol

Synthesis project management supports independent Claude Code, OpenAI Codex,
Cursor, and other root sessions without making any client the owner of project
memory.

## Quickstart — many agents, projects, and computers

The order of operations for every root session, in any client, on any
machine:

1. **Anchor.** Verify the date, then run `coordination.py status` — it
   refreshes the lease mirror when one is configured — and read your
   project's `CONTEXT.md`, `REFERENCE.md`, latest session entry, and
   controlling plan. Trust `git log`, not cached prose; a
   `handoff.record-freshness` failure or a SessionStart staleness warning
   means pull the checkout before believing anything the record says.
2. **Claim.** Let the helper allocate a UUIDv7 session identity and its compact
   and speakable aliases while registering your exact machine, project,
   worktree/branch, resource claims, and context role — owner for the project's
   canonical context, contributor for a bounded slice. A migrated letter is a
   legacy alias, not a claim.
3. **Isolate.** Create worktrees only after the claim, always naming the
   repository explicitly (a `cd`-dependent worktree command in the wrong
   directory creates a worktree of the wrong repository).
4. **Work.** Heartbeat at checkpoints; keep the plan file current at phase
   boundaries — it is the artifact that survives a crash (see "Digests").
5. **Close.** Update durable project tiers, create the local handoff receipt,
   message affected sessions, release the claim, and retire merged worktrees
   with `retire_worktree.py`, never by hand. Publish the attributed batch
   only for explicit remote handoff or day-end.

## Addressing a peer session — resolve, receipt, gate

Three naming systems cover one population of sessions: the board's
identities (UUIDv7 with compact and speakable aliases), each client's chat
handles (Claude Code's `local_<uuid>` desktop session ids, Codex thread
ids), and the harness's peer registry (derived display names that duplicate
freely, each backed by a Unix socket). Only the board answers "what does
this session own"; only the session itself knows all of its handles. The
join is therefore registered by the session: the board row carries its
primary **client session ref** (`ccd:local_<uuid>` on the desktop,
`cc:<uuid>` in a terminal, `codex:<uuid>` for Codex via the exported
`SYNTHESIS_CLIENT_SESSION_REF`), and a **seat** sidecar beside the board
(`seats/<session uuid>.json`, written at claim, refreshed at heartbeat,
removed at release) carries the rest: harness session id, desktop id, pid,
machine.

Seven recorded misdeliveries (2026-08-19 through 2026-09-02, one of them
the day after the resolver shipped) share one shape: an agent chose a
target by a display name at the moment of sending. The protocol removes
that moment.

1. **Resolve first.** `coordination.py resolve --to <project|session|ref>`
   returns exactly one target (exit 0), prints the exact invocation per
   lane, and writes a **delivery receipt** under
   `receipts/<sender key>/` naming that target and those addresses, valid
   for 20 minutes. Several candidates exit 20 and issue nothing — narrow
   with `--role owner` or an exact id; none exit 21 — use the bus. Titles
   and display names are deliberately not selectors.
2. **Lanes are exact addresses, computed from live truth.**
   - *bus*: `coordination.py message --to <compact id>` — always available,
     delivered to the addressed seat (or its project's sessions) at that
     session's next prompt by the plugin's inbox hook.
   - *ccd*: `mcp__ccd_session_mgmt__send_message` with the row's
     `local_<uuid>` — same machine only.
   - *harness*: `SendMessage` to `uds:<socket>` — the registry's socket for
     the seat's harness session id, only while that process is alive on this
     machine. The registry name is printed for display; it is never the
     address. A bare name, `name [ref]`, or `[ref]` is refused.
   - *codex*: `codex queue --thread <uuid> --message …` — same machine.
3. **The gate enforces it.** `scripts/peer_send_gate.py --gate`, registered
   in the plugin's `hooks/hooks.json` for both clients on `SendMessage`,
   the ccd send tool, and the shell tools (for `codex queue`), admits a
   direct send only when: the address equals a live receipt held by this
   sender; the target row is still active; the harness registry still maps
   that socket to the receipt's session; the sender holds an active seat;
   the message carries the sender's board id (so the reply resolves without
   guessing); and the same text has not gone to a different session within
   15 minutes (that is a broadcast). A reply may copy the `from=` of a
   message this session received — the harness wrote that address. In-process
   targets (`main`, spawned agent ids, named teammates) pass. Every decision
   lands in `peer-sends.jsonl`. Anything the gate cannot verify blocks.
4. **Never assign work to a guess.** An unresolvable peer means a bus
   message addressed to the project, which its sessions self-select at their
   next prompt — a dispatch to the wrong session starts work in a context
   with the wrong claims, and the receiving session cannot tell it was a
   guess.
5. **One seat, one row.** A claim with no `--session` whose detected ref
   matches its own active row updates that row in place; two active rows
   with one ref refuse until the stale one is released. Sub-agents spawned
   by a session inherit its environment and therefore its seat.
6. **Codex sessions register the same way.** Their hooks receive the thread
   id and the SessionStart context states it; a Codex shell carries no
   thread id, so the agent exports `SYNTHESIS_CLIENT_SESSION_REF=codex:<id>`
   before `claim` and `resolve`. Receipts are then filed under the key the
   gate derives from the hook payload; a mismatch simply finds no receipt.
   Codex reaches its peers through the same resolver and gate; Claude
   sessions reach Codex through `codex queue` or the bus.
7. **`whoami` and `inbox`.** `coordination.py whoami` prints this shell's
   identity, seat, and the lanes peers would use; `inbox` lists unread bus
   messages for the seat and marks them read. The doctor counts seats and
   names those without an active row; `peer_send_gate.py --doctor` verifies
   the gate's inputs for this session.

The synthesis-message-guard `peer_send_resolution` lane (config-adopted)
remains a second, independent existence check on the ccd tool; the plugin
gate above is the intent check and runs regardless of private configuration.

Migration is staged: the engine reads schemas v1–v4 and writes each board's
declared schema; a shared board flips to v4 only via an explicit `migrate`
run after every machine's client is current, so older parsers mid-flight
fail closed on nothing. Seats and receipts are sidecars and need no schema
change; an engine without them simply offers the bus.

## Release trains — serializing a shared publish surface

Path claims keep concurrent sessions off each other's files, but some
resources are not files: a repository's release identity (its `main`, its
version number, its changelog top) is one shared slot that every releasing
session mutates. Five same-day overtakes between two parallel release
trains (2026-09-01) showed that message-based sequencing fails exactly when
it matters — an autonomous session mid-transaction does not re-read the
board between authoring a version and merging.

The pattern: claim a **virtual resource** — a non-path token such as
`release-train:<plugin>` — through the ordinary claim machinery. Identical
tokens conflict under the same overlap refusal that guards paths (and the
lease compare-and-swap serializes them across machines), so the claim is
the lock; path claims never false-positive against it. The consuming
boundary then enforces possession fail-closed: synthesis-skills'
`release.py` preflight refuses every publish-capable mode on a
board-carrying machine unless the running session holds the train. Hold it
from version authoring through the gated release; release it immediately
after. A dead holder is freed only by the user via the stale-claim review.

## Digests — what survives a crash

Semantic continuity does not come from copying chat transcripts. The durable
digest of a session is the controlling plan file updated at every phase
boundary (decisions, evidence, open loops, approval gates, user
instructions), plus the session-log entry written at close. A session that
dies mid-flight loses at most the work since its last plan-file update —
which is why the update belongs at every phase boundary, not at the end.
Contributor sessions get the same protection from their contribution
artifact. No separate digest artifact exists, deliberately: a second place
to record decisions is a second place for the record to drift.

## Different projects

Different projects may run at the same time. Each session:

1. reads the coordination board and its own project context;
2. registers a unique UUIDv7 session identity, machine, project id, worktree/branch pair,
   context role, and source-area claims;
3. uses an isolated worktree when another live session touches the same
   repository;
4. heartbeats at checkpoints; and
5. updates project state, leaves attributed local evidence, and releases its claims before pausing; remote publication belongs to explicit handoff or day-end.

Claims remain resource-based. Two different synthesis projects can still
conflict when they edit the same repository or home configuration, so project
ids alone never grant write safety.

## The same project

Same-project parallelism uses a single-writer/multiple-contributor model:

- one root session is the **context owner**;
- other root sessions are **contributors**;
- implementation claims and worktrees never overlap;
- contributors do not edit `CONTEXT.md`, `REFERENCE.md`, `sessions/`, the
  controlling plan, or `projects/index.yaml`; and
- every contributor writes a session-specific artifact under
  `resources/artifacts/contributions/<compact-session-id>.md`.

The contribution artifact records:

- claimed scope and branch/worktree;
- files changed and commits created;
- tests and checks that actually ran;
- remaining risks or gates; and
- the exact context changes the owner should reconcile.

Use this shape:

```markdown
# Contribution — <compact session id>

**Project:** <project id>
**Claim:** <resource globs>
**Worktree:** <absolute path>
**Branch:** <branch>
**Status:** ready for reconciliation

## Result

<what changed>

## Commits and files

<commit ids and changed paths>

## Verification

<commands and results that actually ran>

## Context reconciliation

<specific CONTEXT/REFERENCE/session/plan updates for the owner>

## Gates or conflicts

<none, or exact unresolved boundary>
```

The context owner reads all new contribution artifacts as a set, verifies their
claims against git and test output, merges or integrates the implementation,
updates canonical project context once, then records which artifacts were
reconciled. This prevents last-writer-wins corruption of the durable project
record.

## Shared repositories

Independent root sessions never share a worktree, index, or branch. A safe
shape is:

```text
repository
├── worktree-codex/   feature/codex-<scope>
└── worktree-claude/  feature/claude-<scope>
```

Non-overlapping file claims are still required. Worktree isolation prevents git
index and branch collisions; resource claims prevent semantic collisions.

## Pauses, crashes, and stale sessions

A pause is a coordination event:

1. write the project checkpoint or contribution artifact;
2. commit and push it;
3. message any affected session; and
4. release or narrow the claim.

Heartbeats make abandoned sessions visible, but a stale timestamp never
transfers ownership automatically. Another session may take over only after the
user or the owning session explicitly releases or reassigns the claim.

### Administrative release

When a session is genuinely gone — a crashed client, a closed laptop, a chat
that will never resume — its `active` row keeps blocking overlapping claims
by design. The release decision belongs to the user, not to elapsed time and
not to another agent's judgment. The user (or a session acting on the user's
explicit direction, recorded in that session's log) runs:

```bash
python3 <root>/scripts/coordination.py release --id <stale-id>
```

`release` marks the row released without touching its history; nothing else
on the board changes. An agent must never administratively release a peer on
its own initiative — route the request through the board's message log or
the user, exactly as with any other overlap.

## Commit authority — check-staged selector precedence

`check-staged` selects the committing session from, in order: an explicit
`--session`, then `SYNTHESIS_COORDINATION_SESSION`, then `owner_session` in
the active-project pointer. The board is refreshed from its configured lease
before evaluation. A missing or unreadable board, an inactive session, a
detached branch, an unregistered worktree, or an unreadable index refuses.
To make a deliberately exceptional commit, pass `--override-reason` (or set
`SYNTHESIS_COORDINATION_OVERRIDE_REASON` when the git-hook boundary invokes
the check); the override is not authority until its board write completes
and the index revalidates unchanged.

## Resuming and the active-project pointer

When resuming work from another agent, resolve the named project through the
git-tracked `projects/index.yaml`, run local continuity for a stopped
project, read `CONTEXT.md` and the linked plan, and inspect Git status and
diff before acting. Working-tree truth supersedes cached project prose after
an interrupted task. The continuity source of truth is the
filesystem-backed synthesis record, not the previous assistant's chat
transcript.

The pointer is a leased acceleration cache for a live context owner. Claim
release archives it recoverably into
`~/.synthesis/active-project-history/`, so its absence after a clean stop is
expected. Never replace it with one git-tracked global "current project"
value: parallel Claude Code and Codex sessions can legitimately work
different projects. A stopped task resumes by named-project registry
resolution; a task opened inside the project directory can also be
discovered from its durable file structure.

Cross-computer recovery adds two preconditions: the source machine must
reach `REMOTE_READY` through synthesis-mac-sync or day-end, and the
destination must fetch and fast-forward before Session Start. Offline,
divergent, behind, unpublished, or overlapping-claim states are reported
explicitly and are not remote-continuity passes.

## Cross-machine boundary

Git carries durable project state and contribution artifacts between machines.
The default live board uses an OS file lock, which is authoritative among
processes sharing that filesystem. File-sync conflict resolution is not a
distributed lock.

For simultaneous sessions on different machines, opt the board into the
git-backed lease by writing `lease.json` beside it:

```json
{"remote": "git@example.com:owner/coordination.git"}
```

Optional keys: `ref` (default `refs/synthesis/coordination-board`) and
`repository` (the local bare mirror, default `.lease-repo` beside the board;
point it at a non-synced location such as `~/.cache/...` when the board
directory itself is file-synced, so replication carries only the static
config, never git-object churn). Every mutating command then performs an
atomic compare-and-swap ref update on the shared remote — the server-side
ref transaction is the mutual exclusion — and rewrites the local board as a
mirror of the accepted state. Concurrent advances trigger a bounded
refetch-and-retry against fresh content; an unreachable remote fails the
mutation closed rather than falling back to a local-only write. `status`
refreshes the mirror from the remote and reports a refresh failure as a
problem (strict mode fails); `doctor` fails when the mirror and remote
differ.

A leased board **declares itself**: mutations keep a `Lease: <remote>` line
in the board header, and the declaration travels with the board content —
through file sync, mirrors, and the leased ref. A lease-aware helper that
finds the declaration without a local `lease.json` refuses to mutate, which
turns the silent-loss scenario (a machine writing local-only changes that
the next lease refetch would drop) into a loud, actionable error.

### Bootstrapping another machine

1. Let the file-synced board directory replicate `lease.json` (or copy it),
   including its `remote`; adjust `repository` to a machine-local path.
2. Confirm the machine can push to the lease remote with its existing
   credentials.
3. Run `coordination.py status` — the mirror refreshes from the remote — and
   then claim normally. If a mutation is refused with the
   declared-but-unconfigured error, the config has not arrived yet; copy it
   rather than working around the refusal.

Use a helper at least as new as the lease feature for every board write; an
older helper writes the local file directly and its change is dropped at the
next lease refetch.

### Retiring a lease

`coordination.py lease-disable` removes the declaration and publishes the
undeclared board through the compare-and-swap path, then moves the local
`lease.json` to a timestamped `.disabled-` file; remove the config from the
other machines before their next board write, or their mutation re-enables
the lease. `lease-disable --local-only` exists solely for a lease whose
remote is permanently unreachable; with a working remote the published path
is the only sanctioned one.

Without a configured lease, simultaneous cross-machine writes to the same
resources remain prohibited.

## Worktree retirement

Retire merged feature worktrees with the fail-closed helper instead of raw
git:

```bash
python3 <root>/scripts/retire_worktree.py \
  --repository /path/to/repo --worktree /path/to/worktree --delete-remote
```

It takes the repository explicitly (never the current directory), fetches
before verifying, requires the branch to be fully contained in the remote
base, refuses main worktrees, dirty trees, detached heads, and a working
directory inside the target, and deletes branches with safe delete only.
"Merged on the remote" is the retirement bar — a stale local ref proving
nothing.

The helper holds the shared handoff lifecycle lock across preparation,
removal, and reconciliation; pins the remote commit; content-addresses its
reconciler outside the target; and fsyncs a resumable intent before removal.
Unexplained missing paths remain blocking Stop failures. There is no offline
or local-ref escape hatch. If interruption lands after removal, rerun the
same helper command: it finds the matching prepared intent, executes that
exact pinned reconciler, completes reconciliation idempotently, and then
finishes branch cleanup. Optional remote deletion uses a compare-and-delete
lease and refuses an advanced or differently sourced branch.

## Handoff queue mechanics

`handoff.py` payloads are stored as durable files under
`resources/handoffs/` with a sha256 recorded at write time; `read` refuses a
payload whose bytes have changed since the handoff. The queue
(`resources/handoffs/queue.json`) is written atomically. Reader identity
comes from `--as` or `SYNTHESIS_HANDOFF_SELF` — with neither, `read` refuses
rather than guess, because guessing could claim another agent's work.
