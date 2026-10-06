# Preserved: the 2.21.6 coordination references, verbatim

The 2.21.6 coordination protocol, board template, session identity and
durable delivery references, unchanged. v5 replaced the board engine with
`synthesis claim`, `release`, `who`, `msg` and `inbox` over one small file per
session; [coordination.md](coordination.md) carries the rules that still hold,
and [coverage-map.md](coverage-map.md) says where each one went. Read only to
review the cut.

## Contents

- [parallel-agent-protocol.md](#parallel-agent-protocolmd)
- [active-sessions-template.md](#active-sessions-templatemd)
- [session-identity.md](#session-identitymd)
- [session-words-v1.LICENSE.md](#session-words-v1licensemd)
- [project-durable-delivery.md](#project-durable-deliverymd)

## parallel-agent-protocol.md

Verbatim from `skills/synthesis-project-management/references/parallel-agent-protocol.md` at 2.21.6. Links inside point where they pointed then.

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
   legacy alias, not a claim. Claim the smallest coherent area needed for the
   current task, following the scope rules below.
3. **Isolate.** For an absent checkout, use `scripts/create_worktree.py` under
   the exact native seat. Its authenticated creation-only reservation precedes
   Git effects; after creation, claim the exact edit paths before writing.
   Name the repository and target explicitly (see "Absent checkout creation").
4. **Work.** Heartbeat and review claim scope at checkpoints and task/phase
   changes. Expand before additional writes; narrow completed areas promptly.
   Keep the plan current at phase boundaries — it survives a crash (see "Digests").
5. **Close.** Update durable project tiers, create the local handoff receipt,
   message affected sessions, release the claim, and retire merged worktrees
   with `retire_worktree.py`, never by hand. Publish the attributed batch
   only for explicit remote handoff or day-end. A merge or fast-forward
   request sent to another session names the target head it was
   tested against (`fast-forward clean as of main=<sha>`); the receiver
   re-runs `git merge-base --is-ancestor <current-target-head> <source-head>`
   against the target's current head, not the named sha, before acting, and
   any advance of the target since the named head invalidates the claim.

## Claim scope over the task lifecycle

Claim admission uses the shared `scripts/claim_scope.py` conflict predicate.
Besides physical overlap, the same `projects/` metadata path in registered Git
worktrees conflicts when their verified Git common directory is identical.
Disjoint exact files and segment globs remain independent; ordinary source
paths outside `projects/` remain isolated by checkout. Every relative filesystem
claim needs one unambiguous absolute workspace context before admission, even
with no peer rows. `repo:path` is not a repository selector: use an absolute path
(or a relative path with one exact workspace). Absolute filenames may contain
colons. Adding a workspace binds retained relative claims to their original
checkout and new relative claims to the explicitly requested checkout; ambiguous
new requests refuse before writing the board. Missing or ambiguous native Git
evidence still refuses a possible logical metadata overlap. `release-train:<plugin>`
is a separate mutex and never grants file writes. Creation reservations remain
exclusive to the worktree-creation owner and never grant edit authority.

Conflict identity does not grant write authority. Check-staged still requires
the actor's exact physical worktree, branch and staged paths. A currency guard
may ask whether a claim intersects the broader possible repair area (the project
subtree or registry); that is explicitly broader than comparing two exact edits
and is never proof of ownership or permission to write another checkout.

Claims reserve the smallest coherent area needed for the current authorized
task. Use exact files for independent edits. A directory claim is appropriate
when the task requires coordinated changes across that directory, such as a
multi-file implementation and its tests; directories are not categorically
forbidden. Naming a project does not by itself require claiming its whole repo.

Before writing outside the accepted area, expand the claim and verify that the
expansion was accepted without overlap. Do not reserve speculative future work,
adjacent projects, or whole repositories merely because they might become
useful later. An intended expansion is not write authority.

Re-claiming merges by default: a `claim --id` call unions the named areas
and workspaces with what the row already holds, and names what it retained
and added. Omission never shrinks a claim — a re-claim written from a
compacted context cannot silently drop the areas it forgot to restate.
For the same authenticated seat and project, the role also keeps the higher of
its existing and requested values (`none`, `contributor`, `owner`). A helper
sharing that identity cannot demote the owner through an incremental claim.
The command reports a retained role; an explicit `--replace` can change it only
when the replacement scope passes the ordinary context and ownership checks.
This does not inherit a role across projects or authorize a foreign session.
Canonical-context claims are checked against that effective role inside the
locked, authenticated update, including when a helper repeats an already held
context path. A new contributor, a cross-project claim, or an explicit role
replacement cannot borrow the prior owner's authority to bypass this check.
Shrinking is the explicit `narrow` verb, which names each area or
workspace to release (`--release`; `--keep` names what to retain and
releases the held complement instead), refuses targets the row does not
hold, warns loudly when the seat would keep nothing, and prints the
released and retained sets. `--area` is a deprecated alias for the
release sense. The rare full reset is `claim --replace`,
which sets the row to exactly the call and names every drop loudly.
Never re-claim a subset expecting the rest to fall away; that was the
pre-ruling-B replace trap.

At each task or phase change and each normal execution checkpoint, compare the
held areas with what remains to do. Narrow the claim as areas finish (via
the `narrow` verb, never by re-claiming a subset), and release completed
areas promptly after their required closure is complete; keep only the paths
still needed for actual work or its unfinished checkpoint.
At a pause or task completion, release or narrow the remaining claim explicitly.
A read-only refresh reports any recommended scope change without mutating claims.

Only change the claims this session owns. Broad scope, age, app closure or a
quiet heartbeat never authorizes narrowing or releasing a foreign claim.
Coordinate an overlap through the owning session or the user's explicit
administrative direction; do not apply automatic release or preemptive claims.

## Addressing a peer session — resolve, receipt, gate

The board reader uses the single canonical `## Messages` section and its final
`---` / `## Protocol` boundary. Ordinary level-two headings inside a real message
remain part of its body. Fenced or indented code examples confer no addressed
message, release, reply, or handoff authority. An unclosed fence, duplicated or
missing boundary, or invalid preamble is ambiguous and blocks protective
consumers. Writers refuse ambiguous unquoted boundaries without rewriting the
approved body; put literal structural examples inside a closed code block.
Historical message bodies and unread watermarks are not migrated by this repair.

A direct delivery lane needs independently observed local machine identity and
current target/seat/native-reference agreement. The `--local-machine` option
restricts that observation; it cannot declare a remote machine local. Fleet
display labels never substitute for the observed OS hostname. Receipts are
rechecked against current authority before a local process is probed or a lane
is admitted; changed target or seat identity requires a fresh resolution.


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

When naming a session id to the principal — status, refusal relay, or ask —
annotate it as `id (project · harness)` from the live board row. A bare id
tells them nothing about where to go; tool diagnostics already render this
form, and prose must match it.

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
   - *codex*: `<codex-cli> queue --thread <uuid> --message …` — same machine,
     and only when this machine has a Codex CLI that actually runs. The
     resolver finds it through the conformance skill's client-binary owner
     (`SYNTHESIS_CODEX_BIN`, then PATH, then the documented app locations,
     each found launcher passing a bounded `--version` probe) and prints that
     exact binary. A launcher that exists but cannot start its CLI is no
     lane; the resolver says the codex lane is closed and why.
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
   One boundary is stated rather than hidden: on the shell lane the gate
   reads the command text of the tool call, so a `codex queue` invoked
   from inside a script file is invisible to it, whether that script is
   run by path or piped to a shell on its stdin — the boundary every
   shell-level guard shares. Invoke `codex queue` directly in the tool
   call; wrapping it in a script, run by path or through a pipe, is
   evasion, not delivery, and the send log will show no decision for it.
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
3. shares a checkout with another live session only with disjoint claimed
   areas (the claim-time banner names who is already there), else uses an
   isolated worktree; sharing seats commit only their own paths;
4. heartbeats at checkpoints; and
5. updates project state, leaves attributed local evidence, and releases its claims before pausing; remote publication belongs to explicit handoff or day-end.

Claims remain resource-based. Two different synthesis projects can still
conflict when they edit the same repository or home configuration, so project
ids alone never grant write safety.

## The same project

Same-project parallelism uses a single-writer/multiple-contributor model:

- one root session is the **context owner**;
- other root sessions are **contributors**;
- implementation claims never overlap (worktrees may be shared when the
  claims on them are disjoint);
- contributors do not edit `CONTEXT.md`, `REFERENCE.md`, `sessions/`, the
  controlling plan, or `projects/index.yaml`; and
- every contributor writes a session-specific artifact under
  `resources/artifacts/contributions/<compact-session-id>.md`.

### Advisory claims and shared checkouts

A row quiet past the stale threshold is ADVISORY automatically: its areas no
longer block, and each grant through one is recorded on the bus as a DOWNGRADE
NOTICE addressed to the quiet seat. Advisory is not release — the row stays
active, duplicate-owner exclusivity still holds, undated heartbeats keep
blocking, and no agent releases another live seat. A revived seat heartbeats to
re-assert; if its areas now collide with a live claim, the heartbeat is refused
with the collision named, and the seat narrows or releases first. Paused
sessions narrow or release explicitly rather than leaning on the threshold.

Same-checkout sharing is granted with a banner naming the seats already there.
Sharing seats inspect the index before every commit and commit only their own
paths: `git commit -o <paths>` scopes the pre-commit hook to just those paths
(probed 2026-09-18), so co-staged foreign files never sweep, while a bare
`git commit` fails closed on them. Push races on a shared branch serialize on
pull, git-natively. Mixed absolute/relative spellings of one path still
conflict everywhere area overlap is computed.

### Claim succession

A dead seat — active, with a dated heartbeat quiet past the stale threshold —
transfers without administrative release. The `succeed` verb releases the dead
row and lands its scope on the successor row inside one locked update, so the
areas are never unheld or double-held, and appends a SUCCESSION NOTICE to the
bus addressed to the dead seat. Death is the authority, and the notice is the
loud record; `stale` output names exactly the succession candidates.

```bash
# Step into the dead seat's full scope as a new row (project, context
# role, areas, workspaces):
python3 <root>/scripts/coordination.py succeed --from <dead-id> \
  --agent <agent> --mode <mode> --goal <goal>

# Or merge the dead seat's areas and workspaces into an owned row
# (which keeps its own project and context role):
python3 <root>/scripts/coordination.py succeed --from <dead-id> \
  --session <own-id>
```

Succession refuses rather than guesses: a live seat refuses (duplicate-owner
exclusivity still holds between live seats), an undated heartbeat refuses, a
`--session` the caller does not own refuses, and a scope that would collide
with a third live seat refuses with nothing changed. Concurrent successions
of one dead seat serialize on the board lock — exactly one wins. A revived
owner re-claims; if its areas now collide with a live claim, the claim names
the collision.

### Idle-holder escalation

An idle-but-alive holder is not dead, so succession does not apply; the
standing idle-holder direction (ecosystem DECISIONS.md, 2026-09-20)
governs instead. Ask first: `request-narrow` posts a structured request
the holder's next prompt honors automatically — clean areas narrow off,
dirty areas reply `held`, unverifiable checkouts defer without a reply.
Narrow second: an unanswered request older than 10 minutes, with a
harness log that has not grown since the request and a clean checkout
under the areas, escalates via `narrow --administrative --basis
idle-holder --reason <request id>`, callable only by the requester. The
escalation appends a `recorded-administrative-narrow` block addressed to
the holder, so a revived holder meets it in its inbox.

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
record. A contributor's merge or fast-forward claim is scoped to the target
head it names (`fast-forward clean as of main=<sha>`); before acting on it the
owner re-runs the ancestry check against the target's current head, not the
named sha (`git merge-base --is-ancestor <current-target-head> <source-head>`),
and if the target has advanced past the named head the claim is void and the
contributor re-tests against the current head.

## Shared repositories

Independent implementation sessions use isolated worktrees by default. Sharing
one checkout is also supported when every claimed area is disjoint. Those seats
must sequence branch/index operations and commit only their own exact paths;
disjoint file ownership does not provide a private Git index. A typical isolated
shape is:

```text
repository
├── worktree-codex/   feature/codex-<scope>
└── worktree-claude/  feature/claude-<scope>
```

Non-overlapping file claims are still required. Worktree isolation prevents git
index and branch collisions; resource claims prevent semantic collisions.

### Absent checkout creation

A future path is not a registered Git checkout. Do not claim an absent native
workspace, claim a whole repository to get past discovery, or create a branch
first and retroactively claim it. With an already authenticated active seat,
`scripts/create_worktree.py --board <board> --session <exact-id> --repository
<existing-root> --target <absent-absolute-path> --branch <new-branch> --ref
<commit-ish>` publishes `create:<target>` through the existing board owner before
creating anything. The target's parent must already exist. The helper checks
symlink-free descriptor ancestry, existing physical claims and other creation
reservations, and serializes local creators. Every creation/claim-effect local
board lock has a five-second acquisition ceiling. A configured remote lease is fenced
through its owner; unavailable ownership refuses before the effect.

A creation reservation reserves only that checkout creation. It grants no source
edit or staged-commit authority. Success releases only that reservation; the
original workspace and edit-claim sets stay exact. Adding a workspace would give
existing relative claims a new physical meaning. The result is
`created-awaiting-workspace-and-edit-claim`: explicitly register that workspace
and acquire its required narrow edit claims next.
Failure or interruption retains the reservation and partial tree, including a
successfully created tree whose reservation release failed. Inspect those exact
objects under the native owner before recovery or explicit narrowing; never
retry Git creation against a partial target or erase the retained tree. Neither
selectors, legacy aliases nor a copied environment label authenticate ownership.

### Claim-dependent effects

A refused claim terminates the dependent operation. `coordination.py claim`
already exits nonzero on refusal; never ignore that exit, queue the effect in
parallel, or treat a serialized retry as proof of the original cause. For an
explicit dependent command, place `--then-cwd <absolute-directory>
--then-timeout <seconds> --then <executable> <arguments...>` last in the claim
invocation. This owner runs the exact argv only after successful claim and seat
persistence plus a fresh native ownership check. The default ceiling is 60
seconds, configurable through 900; captured output is capped at one MiB. Child
failure, output overflow, interruption and timeout remain failures; the owner
terminates its process group and retains the claim and partial work.

This sequencing is not a sandbox, extra write permission or protection against a
program deliberately escaping its process group. Commands still require their
normal authorization, narrowly claimed paths, native hook checks and configured
OS boundaries. Keep larger workflows in their existing execution owners.

### Bounded passive resnapshot

Passive path and broad project-repair readers may repeat their complete snapshot
once when positively verified new registrations appeared in a worktree registry.
The common directory, configuration and all old registry entries must retain
identity; no provisional verdict escapes. Removed/replaced registrations, changed
physical paths or configuration, unreadable state and continued disagreement
refuse. The second observation still enforces overlaps. This does not authorize
writes, extend the caller's existing time budget or weaken mutating admissions.
The broad reader uses `claim_scope.project_claim_overlaps` for the whole row set;
per-row calls cannot establish a shared observation boundary.

## Pauses, crashes, and stale sessions

A pause is a coordination event:

1. write the project checkpoint or contribution artifact;
2. commit and push it;
3. message any affected session; and
4. release or narrow the claim.

Heartbeats make abandoned sessions visible. A stale timestamp downgrades the
row to ADVISORY automatically — its areas stop blocking, with each grant
through recorded on the bus. A dead seat's scope transfers through claim
succession (above), which releases the dead row as part of the transfer; only
seats succession cannot judge — live, or undated — still need explicit action.

### Administrative release

When a session is genuinely gone — a crashed client, a closed laptop, a chat
that will never resume — but its seat is not dead by the heartbeat rule (a
recent stamp, or an undated one succession refuses to guess about), only
removal frees owner exclusivity and keeps the board truthful. That release
decision belongs to the user, not to elapsed time and not to another agent's
judgment. The user (or a session acting on the user's
explicit direction, recorded in that session's log) runs:

```bash
python3 <root>/scripts/coordination.py release --id <stale-id> \
  --administrative \
  --reason "Operator confirmed the abandoned session may be released"
```

The administrative path records the target, caller identity, timestamp, and
reason on the board before it marks the row released. Existing-row `claim`,
`heartbeat`, and normal `release` mutations are bound to the exact seat
recorded at claim, so parsing another session's id from a diagnostic cannot
mutate it. An agent must never administratively release a peer on its own
initiative — route the request through the board's
message log or the user, exactly as with any other overlap.

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

Claim cleanup reads only the claim owner's row. The retained runtime runs its
pinned status read inside the verified child and returns that one row, so the
reply stays row-sized however many sessions the board holds. An active owner
must still prove its native identity before any narrowing or retry. A released
or absent owner holds no live claims on the pinned board; the helper records
that nothing was narrowed and completes the remaining verified steps for any
caller, because no seat can authenticate as a closed owner.

## Handoff queue mechanics

`handoff.py` payloads are stored as durable files under
`resources/handoffs/` with a sha256 recorded at write time; `read` refuses a
payload whose bytes have changed since the handoff. The queue
(`resources/handoffs/queue.json`) is written atomically. Reader identity
comes from `--as` or `SYNTHESIS_HANDOFF_SELF` — with neither, `read` refuses
rather than guess, because guessing could claim another agent's work.


## Durable work placement and unexplained loss

Create long-lived worktrees, source copies, virtual environments and sole
recovery evidence under the durable workspace, for example
`~/workspaces/example/.worktrees/feature-review`. System temporary directories
and session scratchpads have no durable retention contract. Their retention
varies by OS, administrator policy, storage pressure and file timestamps; never
promise a universal number of safe days or keep them alive by touching files.

The existing `scripts/create_worktree.py` owner refuses a temporary destination
before publishing a reservation or creating the target. It checks canonical
paths and temporary-root aliases while retaining exact native identity, board
serialization, parent-descriptor verification and ordinary claims. A bounded
synthetic test may explicitly pass `--fixture-deadline <epoch-seconds>` no more
than 900 seconds ahead. Its receipt says `ephemeral-test-fixture`; this neither
grants edit authority nor establishes durable custody. Preserve the test inputs,
outputs and evidence before closure; the deadline never authorizes deletion.
Do not label production work a test to bypass durable placement.

`fleet_doctor.py --board <board> --repo <repository>` inspects the selected Git
registrations, missing linked metadata and vanished tracked paths without
pruning. Optional repeated `--source-path` and `--venv` flags inspect only the
declared source/virtual-environment paths, not a whole disk. The doctor reports
recoverable registered HEAD/branch evidence where available. Missing paths,
unknown age, or a prunable registration do not prove which cleaner ran, loss of
all refs, completion, or permission to release anyone's claims. Preserve the
common Git directory, refs, surviving files and logs before any separately
authorized recovery. Never prune to make disappearance look like retirement.

`retire_worktree.py` distinguishes unexplained registered-checkout loss from its
existing exact, verified retirement-intent recovery. The latter still requires
its own retained identity, manifest and branch proofs. Temporary placement
alone does not prevent the sanctioned retirement of a verified complete owned
fixture; missing evidence never authorizes cleanup.

### Registered nested retirement and existing temporary work

Retire a registered nested linked worktree through `retire_worktree.py` with its
owning repository, including a checkout under `.claude/worktrees/`. The checkpoint
owner retains the exact native Git/common-directory, checkout and metadata identity
in the prepared intent and revalidates it immediately before removal. Completion
checks the surviving repository/common-directory and absent registration against
that intent. An interrupted removal resumes the same pinned intent; a missing
nested path without that proof cannot manufacture a successful retirement. Main
checkouts, aliases, ancestors, dirty/ignored content and foreign or changed state
still refuse. Durable retirement state and the executing runtime must survive
the target.

Existing temporary work remains claimable for preservation and recovery. A claim
is ownership of work, not permission to create new durable work under temporary
storage. Keep the durable-creation gate. Fleet doctor reports this machine's
declared workspace exposure even when `--repo` narrows the Git comparison, and
continues explicit source/venv diagnosis after a repository inspection failure.
It does not scan the disk, touch files to extend retention, rebuild environments,
remove registrations, or assert an OS expiration time. Preserve a missing path's
registration, references and evidence; recover or relocate only with verified
custody. Venv metadata presence is not proof of package/runtime health.

## active-sessions-template.md

Verbatim from `skills/synthesis-project-management/references/active-sessions-template.md` at 2.21.6. Links inside point where they pointed then.

# Synthesis — Cross-Agent Session Coordination

Shared advisory-lock and message board for independent agent sessions operating
on the same ecosystem.

Schema: v6

## Active sessions

| session uuid | compact id | speakable id v1 | legacy id | agent | machine | machine label | client session ref | project | started | heartbeat | mode | workspace(s) / branch | goal | claimed areas (advisory lock) | context role | status | person | standing role |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

## Messages

Append addressed messages here. Use a heading:

```markdown
### → <recipient compact id>, from <sender compact id> — <timestamp>

<message>
```

---

## Protocol

1. Read this file at SessionStart and every synthesis checkpoint.
2. Claim the smallest coherent area currently needed before writing: exact
   files for independent edits, directories for coordinated multi-file work.
   Expand and verify acceptance before extra writes; do not preclaim future work.
3. Do not write through an overlapping active claim.
4. Every root session that writes git state uses an isolated worktree and branch.
5. One session owns canonical project context; contributors use separate artifacts.
6. An existing autonomous claim keeps priority over an interactive session.
   Under the standing idle-holder direction the interactive session may
   request-narrow and, after 10 idle minutes, narrow administratively
   under the receipt instead of yielding.
7. Put asynchronous handoffs under `## Messages`, addressed to a session id or
   `<project> sessions`; the addressed seat receives them at its next prompt.
   `<project> sessions [durable]` (posted with `message --to <project>
   --durable`) additionally reaches any future owner/contributor seat
   for the project, however old; retire it with `message --resolve
   <key>` once done.
   Direct sends go through `resolve` (which issues the delivery receipt the
   send gate requires); display names and chat titles are never addresses.
8. Heartbeat and review scope at checkpoints and task/phase changes. Narrow or
   release completed areas promptly after required closure; retain only current
   needs. Release or narrow at pause and session end. Never automatically release
   or narrow another session's claim, except an idle-holder administrative
   narrow under the standing direction and its receipt.

## Identity

- `session uuid` is the canonical UUIDv7 used by leases, pointers, and durable
  machine references.
- `compact id` and `speakable id v1` are exact encodings of the same 60 random
  bits from that UUID. Either can select the session at the CLI.
- `legacy id` preserves pre-v3 letter identifiers. It is a lookup alias, not a
  claim and not the canonical identity.
- `machine` is the fleet machine-id (UUID4, one per Mac); `machine label` is
  its human name for display. Liveness is heartbeat age, never pid: a pid is
  meaningful only on the row's own machine.
- `status` may be `parked` for an unreachable row: its claims are frozen, not
  freed, and overlapping claims record `overlaps-parked` instead of refusing.
- Claims are the resource paths in `claimed areas (advisory lock)`; they belong
  to a session identity.

## session-identity.md

Verbatim from `skills/synthesis-project-management/references/session-identity.md` at 2.21.6. Links inside point where they pointed then.

# Coordination session identity

Schema v3 separates a session's identity from its claims. The canonical
identity is a full UUIDv7. Human operators get two exact aliases, while claims
remain the source-area paths attached to the session.

## Representations

| Representation | Shape | Bits | Purpose |
|---|---|---:|---|
| Canonical | `019fff79-5858-7993-a329-b301bccf5d62` | 128 | Durable machine identity, lease ownership, pointers |
| Compact | `s-6adk-06yc-yqb2` | 60 | Fast visual scanning and typing |
| Speakable v1 | `crater-sunset-alone-okay-23906` | 60 | Dictation, reading, and short-term recall |
| Legacy | `AX` | historical | Explicit lookup mapping for migrated v1/v2 boards |

Since schema v4 a row also carries a **client session ref** (for example
`ccd:local_<uuid>`), which is not an identity: it is the client-native
delivery address registered at claim time, resolvable through
`coordination.py resolve` but never a substitute for the UUID in pointers,
leases, or receipts. A session's other handles (harness session id,
desktop id, pid, machine) live in a **seat** sidecar,
`seats/<session uuid>.json` beside the board, written at claim and removed
at release; `resolve` joins the row, the seat, and the harness's live peer
registry into exact per-lane addresses and issues a delivery receipt the
send gate matches. See the parallel-agent protocol's "Addressing a peer
session."

UUIDv7 follows RFC 9562: 48 milliseconds-of-Unix-time bits, required version
and variant fields, and 74 random bits. The alias token uses only the low 60
bits of `rand_b`; no timestamp, version, or variant bit enters either
human-facing identity.

The compact form encodes the token as 12 Crockford Base32 symbols and groups
them four at a time. Decoding accepts Crockford's case folding and the
`I`/`L`→`1`, `O`→`0` aliases; rendering uses lowercase and omits `I`, `L`, `O`,
and `U`.

The speakable v1 form splits the same token into four 11-bit word indexes and a
16-bit integer. Four indexes select entries from the fixed 2,048-entry English
list; the integer renders as `00000` through `65535`. It therefore carries the
same 60 bits as the compact form and round-trips exactly. This is an identifier
encoding, not a password, recovery phrase, or cryptographic secret.

The v1 vocabulary vendors the BIP-39 English word list because it is exactly
2,048 entries, uses lowercase ASCII, avoids similar words, and gives each word
a unique first-four-letter prefix. The exact decoded bytes are pinned to SHA-256
`2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda`.
BIP-39 and its word list are MIT-licensed. Sources:

- RFC 9562, section 5.7: <https://www.rfc-editor.org/rfc/rfc9562.html#section-5.7>
- Crockford Base32: <https://www.crockford.com/base32.html>
- BIP-39 specification and license: <https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki>
- Canonical English word list: <https://github.com/bitcoin/bips/blob/master/bip-0039/english.txt>

## Allocation and lookup

`coordination.py claim` allocates UUIDv7 plus both aliases inside the same
locked or lease-backed compare-and-swap transaction that publishes the row.
It checks every canonical and human selector for collisions and regenerates
before publication. This makes concurrent machines serialize allocation
against the accepted remote board rather than against stale local memory.

`claim`, `heartbeat`, `release`, active-project validation, SessionStart
summaries, and addressed messages accept or resolve the full UUID, compact
alias, speakable alias, or legacy mapping. New claims normally omit an ID:

```bash
python3 scripts/coordination.py claim \
  --agent "OpenAI Codex" --project example --mode interactive \
  --context-role owner --goal "Implement the checkpoint" \
  --workspace "/workspace/checkouts/example @ feature/checkpoint" --area "repo/**"
```

The output returns all three current identities. Subsequent commands may use
the compact or speakable form:

```bash
python3 scripts/coordination.py heartbeat --session s-6adk-06yc-yqb2
python3 scripts/coordination.py release \
  --session crater-sunset-alone-okay-23906
```

Selectors address a row; they do not authorize its mutation. Existing-row
claim changes, heartbeat, and normal release match the running harness identity
against the seat recorded when the claim was made. Releasing another session
is a separate administrative operation that requires
`--administrative --reason <text>` and records that override on the board.

`coordination.py migrate` upgrades the whole v1/v2 board atomically, assigns
each historical row a UUIDv7 and both aliases, and preserves its old letter in
`legacy id`. Messages and history are left intact. Once migrated, canonical
machine references use the UUID even when a human supplied a legacy selector.

## Engine older than board

A board is shared by every session on every machine that mounts it, and a
plugin release reaches those sessions at different times, so version skew
between the board and the engines reading it is a permanent condition rather
than a transition. `rows()` refuses a board whose declared `Schema:` is newer
than the running engine, and a row wider than the engine's newest column set
is refused the same way; both messages name the newest installed engine to
invoke — resolved from the plugin cache the running script lives in — or the
plugin refresh when none is newer. The refusal is fail-closed by design: a
stale engine must never rewrite a newer board, and the remedy is always the
same, run the current engine's `coordination.py`. `doctor` reports the same
line. Origin (2026-09-01): a session on an older cache read the freshly
migrated v4 board and reported the board itself as corrupt.

Since 4.82.0 every command also prints a one-line stderr notice whenever a
newer engine is installed beside the one running (`note: this coordination
engine is X but Y is installed; run <path>`), so a path resolved once and
kept for hours shows its age in output the agent is already reading. The
version-independent path to pin is `~/.synthesis/plugins/synthesis-skills/current`,
maintained by the gated release (see synthesis-skills-manager).

## Collision boundary

The UUID remains authoritative even if a human alias collision were ever
encountered. Sixty random alias bits give about a 1-in-1.15-quintillion chance
for one specified pair; the birthday probability is roughly 4.3e-7 across one
million allocated sessions. The transactional collision check prevents a
duplicate from being published to one lease-backed board. Independent boards
may reuse a human alias without ambiguity because their lease/board scope is
part of the durable identity boundary.

## session-words-v1.LICENSE.md

Verbatim from `skills/synthesis-project-management/references/session-words-v1.LICENSE.md` at 2.21.6. Links inside point where they pointed then.

# BIP-39 English word list notice

`session-words-v1.txt.zlib.b85` is a losslessly compressed Base85 copy of the
English word list from BIP-39, authored by Marek Palatinus, Pavol Rusnak, Aaron
Voisine, and Sean Bowe. BIP-39 declares the MIT
License. Canonical source:
<https://github.com/bitcoin/bips/blob/master/bip-0039/english.txt>.

MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## project-durable-delivery.md

Verbatim from `skills/synthesis-project-management/references/project-durable-delivery.md` at 2.21.6. Links inside point where they pointed then.

# Durable project delivery

A plain project bus message (`--to <project>`) reaches the sessions of
its time only: seats that claim later never see it in `inbox` (the
claim floor). A **durable** project message additionally reaches any
future owner/contributor seat for the project, however old — the
mode for handoffs that must survive seat turnover.

```bash
ROOT=<synthesis-project-management-root>/scripts/coordination.py
# Post: project addresses only; --durable with a seat handle or
# --free-address is refused.
python3 $ROOT message --from s-6adk-06yc-yqb2 \
  --to synthesis-ecosystem-engineering --durable \
  --text "Defect 4 fixed on main; re-run the drill before release."
# Retire by key prefix once done; only a live owner/contributor seat
# on the message's project may resolve it. The bus stays append-only:
# the resolution is recorded alongside the inbox watermarks.
python3 $ROOT message --from s-6adk-06yc-yqb2 --resolve 9f2c41ab
```

Semantics:

- Delivery is per-seat: each owner/contributor seat sees each
  unresolved durable message once (watermarked like the rest of the
  inbox). Seats with any other role, and seats on other projects,
  never match.
- Resolution is audited: `inbox/resolved.json` records the message
  key plus who retired it and when. Unknown or ambiguous key
  prefixes fail closed.
- The SessionStart/UserPromptSubmit inbox hook reads the same path,
  so durable items surface in the normal session-start board read
  with no protocol change.
