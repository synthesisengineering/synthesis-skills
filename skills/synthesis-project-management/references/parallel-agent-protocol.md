# Parallel agent protocol

Synthesis project management supports independent Claude Code, OpenAI Codex,
Cursor, and other root sessions without making any client the owner of project
memory.

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
`repository` (the local bare mirror, default `.lease-repo` beside the board).
Every mutating command then performs an atomic compare-and-swap ref update on
the shared remote — the server-side ref transaction is the mutual exclusion —
and rewrites the local board as a mirror of the accepted state. Concurrent
advances trigger a bounded refetch-and-retry against fresh content; an
unreachable remote fails the mutation closed rather than falling back to a
local-only write. `status` refreshes the mirror from the remote and reports a
refresh failure as a problem (strict mode fails); `doctor` fails when the
mirror and remote differ. The remote must be one both machines can push to;
enable the lease on every machine that writes the board, or its writes bypass
the shared exclusion.

Without a configured lease, simultaneous cross-machine writes to the same
resources remain prohibited.
