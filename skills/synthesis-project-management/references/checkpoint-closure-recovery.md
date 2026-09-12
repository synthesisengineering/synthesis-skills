# Checkpoint closure recovery

Three conditions have separate evidence: native identity, project ownership,
and retained-edit continuity. An outstanding manifest is not a claim, a claim
is not a publication receipt, and structured-state applicability is not a
declaration that edits are safe.

## Native identity and ownership

The public Stop command receives a native `session_id` and `transcript_path`.
Claude Desktop delivery uses a different host identifier. Its active board
row and existing coordination seat sidecar must agree on coordination UUID,
compact ID, host ID, client, and machine; the sidecar's native UUID must match
the validated transcript. A typed Desktop reference, payload task selector,
or unrelated coordination UUID cannot supply ownership.

If Stop cannot match the native event, inspect that binding before changing
claims. Widening path claims cannot repair an identity mismatch. Missing or
invalid binding evidence remains visible, and an unbound or foreign active
seat requires the normal ownership protocol. No diagnostic grants permission
to claim, release, migrate, publish, or repair another session's manifest.

Prose-only projects do not require creating structured state to finish a
checkpoint. Their local attributed-edit receipt still applies. For adopted
structured state, the native owner must also satisfy its state/claim-bound
receipt. Keep each result and its applicability explicit.

## A removed worktree leaves attributed paths

Use `retire_worktree.py` for normal removal. It records a durable intent before
deletion and resumes reconciliation afterward. Repeating removal by hand loses
the evidence that this workflow preserves.

For a prior removal, preserve the manifest and available receipts. If its exact
historical HEAD can be independently verified, the existing
`checkpoint_sync.py --reconcile-retired-worktree` path verifies that commit
against a freshly fetched remote base. A deleted branch does not itself remove
commits from merged history, but current file existence cannot identify the
removed worktree's HEAD or prove all its edits were preserved.

When the historical HEAD is retained in this native session's local handoff,
an explicitly authorized repair can instead select:

```
checkpoint_sync.py --reconcile-retired-worktree ABSOLUTE_REMOVED_WORKTREE \
  --retirement-repository ABSOLUTE_REPOSITORY --retirement-base origin/main \
  --retirement-session NATIVE_SESSION_UUID --dry-run --json
```

The invoking native identity must match `--retirement-session`. This mode
derives the HEAD from the retained receipt. It requires the receipt to bind the
exact current manifest digest, every affected path's bytes or deletion, and
each present file's Git mode. It verifies those observations against the
historical Git tree and proves that tree's commit is in the fetched remote
base. It does not inspect or consume other sessions' pending manifests.

After reviewing a successful preview within the granted repair scope, omit
`--dry-run` to execute the same verification and retirement transaction. The
transaction records exact manifest and receipt post-images before changing
either. Interrupted attempts resume without inventing evidence or duplicating
retirement. If other attributed paths remain, their retained receipt is
deterministically narrowed so a second removed worktree remains recoverable.
Later or changed attribution blocks replay and is preserved.

Older receipts may lack a manifest digest or file-mode evidence. Missing,
stale, inconsistent, or unavailable proof remains a named recovery gap; do not
backfill it from assumptions, synthesize an approval, or delete the manifest
to obtain a green Stop. Independently reconstructible historical evidence or
an explicit administrative decision is required for such a case. Source
repair does not itself authorize repairing existing native manifests.

## A worktree removed before any record could name it

When the worktree vanished before a retirement intent or a Stop receipt named
it, no historical HEAD exists to verify. `checkpoint_sync.py` reports each
such path as `stranded`, names the missing worktree root, and keeps
evaluating the manifest's other repositories. A path whose repository still
resolves is not stranded; it stays `deleted-or-missing`. When git cannot
answer for the nearest existing ancestor (a timeout, a missing binary) the
path is reported `failed` as `stranded classification unavailable` and stays
on the manifest; a `.git` entry visible in the ancestor chain likewise keeps
it out of `stranded` even when git refuses the repository.

If an intent or this session's retained receipt does name the worktree, the
report points at that evidence (`--complete-worktree-retirement`, or
`--reconcile-retired-worktree ... --retirement-session`), and Stop leaves the
receipt unchanged so the evidence survives. The session-bound form is named
only while the receipt is LOCAL_READY and bound to the current manifest
digest; a receipt the manifest outgrew names the receipt's own head through
`--retirement-head`, which retires only what that head proves. Only when
neither exists is the explicit administrative decision above expressed as:

```
checkpoint_sync.py --flush-session NATIVE_SESSION_ID --drop-stranded \
  --assert "<why the work is known published>" --dry-run --json
```

Review the preview, then omit `--dry-run`. The drop recomputes the stranded
set, refuses if the worktree root exists again, writes an append-only record
under `~/.synthesis/repo-guard/retired-pending/` carrying the dropped paths,
the nearest existing ancestor, the missing worktree root, whether any intent
or receipt named it, any repository whose HEAD tracks the same relative path
with its blob oid, the assertion, the acting identity and the timestamp, and
only then rewrites the manifest without those entries. A blank assertion
(whitespace or invisible format characters only) is refused; existing
records are never replaced. The same flush retires the
entries of every repository whose result proves publication and keeps the
blocked repositories' entries, so a manifest no longer accretes published
work behind one blocked repository.
