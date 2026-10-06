# Parallel sessions: claims, context ownership and messages

Many root sessions (Claude Code, Codex, Muse) share one Mac and often one
repository. Durable project files solve handoff across time; they do not
prevent two live sessions from writing the same files at once. The `synthesis`
board does: each session is one small file under `~/.synthesis/v5/state/`,
listing its harness, project, goal and claims, so no hook ever re-reads a large
shared file.

## Contents

- [Quickstart](#quickstart)
- [How claims behave](#how-claims-behave)
- [Claim scope over the task lifecycle](#claim-scope-over-the-task-lifecycle)
- [Different projects](#different-projects)
- [The same project: one context owner](#the-same-project-one-context-owner)
- [projects/index.yaml has many writers](#projectsindexyaml-has-many-writers)
- [Priority, stale claims and takeover](#priority-stale-claims-and-takeover)
- [Addressing a peer session](#addressing-a-peer-session)
- [Shared repositories and worktrees](#shared-repositories-and-worktrees)
- [Release trains](#release-trains)
- [Digests: what survives a crash](#digests-what-survives-a-crash)
- [Pauses, crashes and merge requests](#pauses-crashes-and-merge-requests)
- [Newer state and version skew](#newer-state-and-version-skew)
- [Durable work placement](#durable-work-placement)
- [Across Macs](#across-macs)

## Quickstart

The order of operations for every root session, in any harness:

1. **Anchor.** Verify the date, run `synthesis who` and `synthesis inbox`, and
   read your project's `CONTEXT.md`, `REFERENCE.md`, latest session entry and
   plan (`synthesis resume <project>` prints them with warnings). Trust
   `git log`, not cached prose.
2. **Claim.** `synthesis claim <absolute paths> --project <id> --goal "<goal>"`.
   The harness's own session id is your identity; `synthesis who` shows its
   six-letter short name. Claim the smallest coherent area the current task
   needs.
3. **Isolate.** Same-file work in parallel needs separate worktrees:
   `synthesis worktree create <repo> <absolute path> <branch>` claims the path
   first, then adds the worktree.
4. **Work.** Review claim scope at checkpoints and task or phase changes.
   Claim more before writing outside the claim; release finished areas with
   `synthesis release <paths>`. Keep the plan current at phase boundaries; it
   survives a crash.
5. **Close.** Update the project tiers, message affected sessions, release
   claims with `synthesis release`, and retire merged worktrees with
   `synthesis worktree retire <path>`, never by hand.

## How claims behave

- A claim is an absolute path; a trailing `/**` claims the whole subtree.
  Relative, `~` and symlinked spellings are resolved to one real path, so two
  spellings of one file conflict.
- A claim may name a path that does not exist yet, such as a new worktree or
  file, and still conflicts with overlapping claims. Claim first, then create
  (lesson 2026-09-17, "create then claim for greenfield seats").
- An overlapping claim is refused with the holder's id, harness, project and
  goal. A refused claim stops the dependent operation: never ignore the refusal,
  run the effect in parallel, or treat a later retry as proof of the cause.
- Re-claiming adds to what the session holds; omission never shrinks a claim,
  so a re-claim written from a compacted context cannot silently drop areas.
  Shrink only with `synthesis release <paths>`.
- The git pre-commit check refuses a commit that touches a file inside another
  live session's claim, with the holder named.

## Claim scope over the task lifecycle

Claims reserve the smallest coherent area needed for the current authorized
task. Use exact files for independent edits. A directory claim is appropriate
when the task requires coordinated changes across that directory, such as a
multi-file implementation and its tests; directories are not categorically
forbidden. Naming a project does not by itself require claiming its whole repo.

Before writing outside the accepted area, expand the claim and verify that the
expansion was accepted without overlap. Do not reserve speculative future work,
adjacent projects, or whole repositories merely because they might become
useful later. An intended expansion is not write authority.

At each task or phase change and each normal execution checkpoint, compare the
held areas with what remains to do. Release completed areas promptly after
their required closure is complete; keep only the paths still needed for actual
work or its unfinished checkpoint. At a pause or task completion, release the
remaining claim explicitly. A read-only refresh reports any recommended scope
change without changing claims.

Only change the claims this session owns. Broad scope, age, app closure or a
quiet session never authorizes releasing a foreign claim. Coordinate an overlap
through the owning session or the user's explicit direction.

Claims remain resource-based. Two different synthesis projects can still
conflict when they edit the same repository or home configuration, so project
ids alone never grant write safety. Advisory does not mean optional: the
filesystem cannot stop every tool, so the claim and the commit check make the
shared obligation visible.

## Different projects

Different projects may run at the same time. Each session reads the board and
its own project context; claims its areas under its project id; shares a
checkout with another live session only with disjoint claims, else uses an
isolated worktree; commits only its own paths; and updates project state and
releases its claims before pausing.

## The same project: one context owner

Same-project parallelism uses a single-writer, multiple-contributor model:

- one root session is the **context owner**: only it writes `CONTEXT.md`,
  `REFERENCE.md`, `sessions/`, the controlling plan and the project's
  `projects/index.yaml` entry;
- other root sessions are **contributors**: their implementation claims never
  overlap, and each writes its result to
  `resources/artifacts/contributions/<short id>.md`.

The board does not enforce this; the rule does. Before writing canonical
context, check `synthesis who` for another live session on the project
(`synthesis resume` names it). If one owns it, contribute instead and message
it.

The contribution artifact records the claimed scope and branch or worktree;
files changed and commits created; tests and checks that actually ran;
remaining risks or gates; and the exact context changes the owner should
reconcile. Use this shape:

```markdown
# Contribution — <short id>

**Project:** <project id>
**Claim:** <claimed paths>
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

## projects/index.yaml has many writers

The index is one file that every project's status change touches: the shape of
the single-slot problem a lock alone cannot fix (lesson 2026-09-02). Before
editing it, claim the file itself, re-read it after the claim is granted, make
the one edit, commit it with `git commit -o`, and release the claim:

```bash
synthesis claim "$KB/projects/index.yaml" --project <id> --goal "set <id> to paused"
# re-read, edit one entry, commit only that path
synthesis release "$KB/projects/index.yaml"
```

A second session that needs the index waits for the release or messages the
holder; no entry is lost to a concurrent overwrite.

## Priority, stale claims and takeover

- **Autonomous claims keep priority.** When an autonomous session (an autopilot
  run) and an interactive session overlap, the autonomous session keeps its
  claim; the interactive session yields unless the principal explicitly
  reorders them. Ask the holder to release with `synthesis msg` first.
- **Stale claims are advisory, never deleted by hand.** A session quiet for
  8 hours shows as STALE in `synthesis who --all`. Its claims stop blocking
  commits, but its session file and claims stay on the board, and a new
  overlapping claim is still refused until you ask for the takeover. The one
  sanctioned transfer is `synthesis claim <paths> --take`: it removes the stale
  holder's overlapping claims, grants yours, and posts a notice the holder sees
  when it wakes. Never release, edit or delete another session's claims or session file.
- **Live but idle is not stale.** A live holder is asked, not overridden: post a
  message, and when it does not answer, ask the principal.

## Addressing a peer session

Seven recorded misdeliveries (2026-08-19 through 2026-09-02, one of them the
day after the resolver shipped) share one shape: an agent chose a target by a
display name at the moment of sending. The protocol removes that moment.

- An address is a session id, its short name, or `project:<id>`.
  `synthesis msg <address> "<text>"` delivers to exactly one live session, which
  sees it at its next prompt; `synthesis inbox` lists unread messages.
- A project with two live sessions refuses and lists both; nothing is
  broadcast or guessed. Display names, chat titles and `[ref]` labels are never
  addresses.
- Every message carries the sender's id, so the reply resolves without
  guessing. The same text to a second session within an hour is refused as a
  broadcast.
- A plain project message reaches the sessions working the project now; a
  session that joins later does not see it. `--durable` (project addresses only)
  reaches every session that works on the project, now or later, once each:
  use it for handoffs that must survive session turnover.
- **Never assign work to a guess.** An unresolvable peer means a message to
  `project:<id>`, which its sessions see at their next prompt; a dispatch to the
  wrong session starts work in a context with the wrong claims, and the
  receiving session cannot tell it was a guess.

When naming a session id to the principal — status, refusal relay, or ask —
annotate it as `id (project · harness)` from the live board row. A bare id
tells them nothing about where to go; tool diagnostics already render this
form, and prose must match it.

Sub-agents spawned by one orchestrator remain governed by that orchestrator.
Independent root sessions use the board; do not mistake a shared git worktree
or shared chat history for coordination.

## Shared repositories and worktrees

Independent implementation sessions use isolated worktrees by default. Sharing
one checkout is also supported when every claimed area is disjoint. Those
sessions must sequence branch and index operations and commit only their own
exact paths: disjoint file ownership does not provide a private Git index.
`git commit -o <paths>` scopes the commit to those paths, so co-staged foreign
files never sweep in. A typical isolated shape is:

```text
repository
├── worktree-codex/   feature/codex-<scope>
└── worktree-claude/  feature/claude-<scope>
```

Non-overlapping file claims are still required. Worktree isolation prevents git
index and branch collisions; resource claims prevent semantic collisions.

`synthesis worktree` takes every path explicitly and never picks a repository
from the current directory:

- `create <repo> <path> <branch> [--from <ref>]` claims the path, then adds the
  worktree; if git refuses, the claim is released.
- `retire <path> [--delete-remote]` removes a worktree only when nothing would
  be lost: it refuses dirty trees (ignored files included, naming them), work
  not merged into the freshly fetched remote default branch (a squash merge
  counts only by identical content), the main checkout, a locked worktree, the
  current directory's tree, and a tree inside another live session's claim.
  "Merged on the remote" is the bar; a stale local ref proves nothing.
- `land <path>` fast-forwards the main checkout to the remote default branch
  only when it is on that branch, clean and behind, and otherwise says why.

## Release trains

Path claims keep concurrent sessions off each other's files, but some
resources are not files: a repository's release identity (its `main`, its
version number, its changelog top) is one shared slot that every releasing
session mutates. Five same-day overtakes between two parallel release
trains (2026-09-01) showed that message-based sequencing fails exactly when
it matters — an autonomous session mid-transaction does not re-read the
board between authoring a version and merging.

The pattern: claim the one path that stands for the release, as the release
skill names it (R7.7), from version authoring through the gated release, and
release it immediately after. Identical claims conflict, so the claim is the
lock. A dead holder's claim goes stale after 8 hours; take it over only with
`--take` after messaging the holder, or on the principal's word.

## Digests: what survives a crash

Semantic continuity does not come from copying chat transcripts. The durable
digest of a session is the controlling plan file updated at every phase
boundary (decisions, evidence, open loops, approval gates, user
instructions), plus the session-log entry written at close. A session that
dies mid-flight loses at most the work since its last plan-file update —
which is why the update belongs at every phase boundary, not at the end.
Contributor sessions get the same protection from their contribution
artifact. No separate digest artifact exists, deliberately: a second place
to record decisions is a second place for the record to drift.

## Pauses, crashes and merge requests

A pause is a coordination event: write the project checkpoint or contribution
artifact; message any affected session; release the claims. When the work will
continue on another Mac, also run `synthesis handoff`.

A crashed or closed session's claims go stale after 8 hours and stop blocking
commits; its successor takes over only the overlap it needs, with `--take`.
Removing a live session's claims is the principal's decision, never another
agent's.

A merge or fast-forward request sent to another session names the target head
it was tested against (`fast-forward clean as of main=<sha>`); the receiver
re-runs `git merge-base --is-ancestor <current-target-head> <source-head>`
against the target's current head, not the named sha, before acting, and any
advance of the target since the named head invalidates the claim.

## Newer state and version skew

A plugin release reaches the sessions on a Mac at different times, so version
skew between the files and the code reading them is a permanent condition, not
a transition (origin, 2026-09-01: a session on an older cache read a freshly
migrated board and reported the board itself as corrupt). When you, a hook or a
script meet a board file, record or format written by a newer version than the
one running, say which version you run (`synthesis version`) and that the
plugin needs updating. Never rewrite, migrate or "repair" the newer file to
make an older reader happy.

## Durable work placement

Create long-lived worktrees, source copies, virtual environments and sole
recovery evidence under the durable workspace, for example
`~/workspaces/example/.worktrees/feature-review`. System temporary directories
and session scratchpads have no durable retention contract. Their retention
varies by OS, administrator policy, storage pressure and file timestamps; never
promise a universal number of safe days or keep them alive by touching files.
`synthesis worktree create` warns when the path is under a temporary directory.

A vanished worktree or tracked file is unexplained loss evidence, not
retirement. Preserve the common Git directory, refs, surviving files and logs
before any separately authorized recovery. Never prune to make disappearance
look like retirement.

## Across Macs

The board is per Mac: claims coordinate sessions on one machine. Git carries
project records between Macs. Hand work over with `synthesis handoff` on the
source Mac (it must end READY), then resume on the destination, which fetches,
fast-forwards when clean, and never pulls over its own uncommitted changes.
Simultaneous writes to the same records from two Macs are prohibited; divergence
is reconciled by hand, never by which copy is newer by date.
