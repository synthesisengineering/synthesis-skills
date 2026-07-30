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
2. **Claim.** Register an unused session id with your exact machine,
   project, worktree/branch, resource claims, and context role — owner for
   the project's canonical context, contributor for a bounded slice.
3. **Isolate.** Create worktrees only after the claim, always naming the
   repository explicitly (a `cd`-dependent worktree command in the wrong
   directory creates a worktree of the wrong repository).
4. **Work.** Heartbeat at checkpoints; keep the plan file current at phase
   boundaries — it is the artifact that survives a crash (see "Digests").
5. **Close.** Commit and push durable state, message affected sessions,
   release the claim, and retire merged worktrees with
   `retire_worktree.py`, never by hand.

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
2. registers a unique session id, machine, project id, worktree/branch pair,
   context role, and source-area claims;
3. uses an isolated worktree when another live session touches the same
   repository;
4. heartbeats at checkpoints; and
5. commits project state and releases its claims before pausing.

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
  `resources/artifacts/contributions/<session-id>.md`.

The contribution artifact records:

- claimed scope and branch/worktree;
- files changed and commits created;
- tests and checks that actually ran;
- remaining risks or gates; and
- the exact context changes the owner should reconcile.

Use this shape:

```markdown
# Contribution — <session id>

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
