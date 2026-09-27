# Ritual evidence and verified execution

This reference is mandatory before day-start and before recording a worker
completion. It supplements the worker contract without changing the desk's
nonblocking fold or granting cross-workspace authority.

## One verified execution owner

Use the installed `synthesis exec-public` owner for each ritual helper, followed
by that helper's existing arguments:

```text
synthesis exec-public synthesis-daily-rituals/scripts/portfolio_review.py
synthesis exec-public synthesis-daily-rituals/scripts/decay_sweep.py
synthesis exec-public synthesis-daily-rituals/scripts/pr_queue_scan.py
synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py
synthesis exec-public synthesis-daily-rituals/scripts/gchat_preflight.py
synthesis exec-public synthesis-daily-rituals/scripts/ritual_state.py
```

The launcher verifies the selected release, interpreter, helper and registered
local dependencies. A missing registration or integrity refusal is a readiness
failure: retain the diagnostic and repair through the installed lifecycle owner.
Do not switch to direct Python execution, a source checkout or another client to
route around it. `--help` establishes parser availability only, never a successful
sync, account grant, network operation, artifact, or real lifecycle acceptance.

## Workspace worker artifact is completion evidence

The existing `~/.synthesis/ritual/workers.yaml` registry remains the owner. Each
registered worker declares `workspace_root` (an absolute or `~` path) and
`surfaces` (the full list of required coverage surfaces), in addition to its
existing workspace key, seat, status and artifact directory. The artifact directory
must be a real directory strictly inside that workspace root. Declare the actual
workspace's sources from its existing repo manifest, sync configuration and
practices; do not silently substitute an empty or reduced list. Missing declarations
are a readiness gap, not permission to alter the registry or disable evidence.
Use the owner's read-only `worker-readiness --workspace <id>` subcommand to expose
that gap before starting work. Configuration enrollment remains the registry owner's
authorized action; do not fabricate readiness by inferring it from a missing file.

Run the worker from within its registered workspace and retain its own claims.
Write the real artifact to its registered directory as
`YYYY-MM-DD-<run_type>.md` (day-start, midday, day-end or weekly-review). Keep the
existing frontmatter and fixed body sections. Additionally record `session` as
the actual current native/coordination identity and `outcome` as the exact outcome
passed to the recorder: clean/complete/completed/success, or
partial/failed/skipped/blocked/degraded. Unknown outcome labels refuse. `started` and `finished` are observed, timezone-aware wall
clock times; `date` is the logical workday, which can differ across midnight.
Include every declared surface exactly once with its real status and detail, and
explicit `gaps`. A clean result requires every surface synced and no gaps. An
unread or failed surface stays partial/failed and cannot become a clean result.

Add `lesson_candidates: []` to frontmatter when there are none. Otherwise use a
list of `{id: <candidate-id>, pointer: <absolute workspace-local file>}` entries.
Pointers must refer to real owned regular files within the worker's workspace.
Add the mandatory final `## Lesson candidates` body section after `## Backlog
deltas`; state `none` or name the local candidates and their pointers. The worker
keeps detailed source material in its workspace; the desk consumes the worker
artifact and routes candidate decisions without copying private source prose into
another workspace. Candidate existence is not acceptance as a durable lesson.
Keep/drop approval and the existing lessons/project record process remain intact.

Record only after the artifact is complete, using the existing recorder with
`--workspace`, `--direction`, explicit `--date`, `--outcome` and `--session`.
The recorder loads the registry itself, derives the exact artifact path and
verifies its contents. `--pointer` remains a narrative pointer, never substitute
evidence or an override to a foreign artifact. A worker record gets an artifact
SHA-256 receipt, byte count, seat and session. Missing, unreadable, linked,
foreign, changing, oversized or invalid artifacts refuse the append. A dormant
worker cannot record. The recorder does not create or backfill evidence, infer
coverage, prove native identity, send messages, or give the worker new claims.
The registry and native coordination layer retain their separate authority.

Without a registered worker the existing single-session ritual remains valid.
Explicit `--mode worker` with no registered workspace refuses, and a malformed
registry refuses rather than silently reverting to single-session behavior.
Historical artifactless records remain historical; never invent replacement
artifacts or rewrite old records to make coverage appear complete.

## Record durability and interrupted writes

The recorder serializes cooperating writers with a bounded exclusive file lock.
It completes short writes, fsyncs the file, checks exact readback and fsyncs the
parent before reporting success. Regular files do not inherit pipe atomicity
from `PIPE_BUF`. Zero-progress writes, failed fsync, changed files and interrupted
non-newline tails refuse. Retain ambiguous bytes for owner reconciliation;
repeating a refused operation is not evidence that its earlier effect was absent.
Linked files and aliased parent paths refuse. A process crash can leave an
interrupted tail, which is preserved rather than silently overwritten.

## Migration markers are not workdays

`mode=migration` identifies bookkeeping. Open-workday derivation excludes those
markers on both sides: a marker cannot create an open day or close real work.
Records, the unknown-workspace baseline and all historical timestamps stay intact.
No invented paired day-end, historical close or backfill is needed.

## Names-only credential-path review at day-start

After resolving this workspace and before reporting day-start coverage, run:

```text
synthesis exec-public synthesis-daily-rituals/scripts/ritual_state.py credential-paths --workspace-root <actual workspace root>
```

The owner reads the existing `.agents/repos.yaml` and each declared local Git
index's tracked **names**. It includes dormant repositories and repositories with
`ritual_sync: false`, because those flags do not eliminate tracked-file exposure.
It never reads tracked file contents or Git blobs, and does not contact a provider.
Git indirection must stay inside this exact workspace. Linked worktrees require
reciprocal checkout metadata; a pointer to another checkout's ordinary `.git`
directory refuses. The index and metadata identities are rechecked after Git
returns. Changed sources remain gaps, and their names are not attributed to the
previous checkout. Separate metadata directories without reciprocal worktree
ownership require explicit owner support and currently refuse.
Untracked files are outside this particular check and are never described as scanned.

Report candidate repository-relative paths privately, with the qualification
“credential-looking names; contents not inspected.” Sample/template names also
remain candidates: a filename alone cannot prove that a file is safe or secret.
The output's `complete` field describes inventory coverage, not absence of secrets.
Missing clones, malformed/foreign paths, unreadable indexes, limits or failed
commands remain explicit gaps and return a nonzero status. Partial coverage can
never support a “none found across the workspace” statement. Runaway bounds are
256 repositories, 8 MiB of path output per repo, 16 MiB across the workspace,
5 seconds per repo and 45 seconds
overall. Preserve the actual coverage and gaps in the worker artifact.

No rotation, key creation, purge, content scan, deletion or history rewrite is
part of this check. Those actions require their own authorization and provider
or repository owners. Do not place these paths in audible alerts or banners.
