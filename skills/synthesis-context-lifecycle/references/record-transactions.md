# Recoverable multi-file record edits

`context_edit.py apply-transaction` edits existing UTF-8 project records using
one transaction. Its file list contains project-relative paths and the same
ordered operations as the single-file `apply` command. Per-file `max_lines`,
`allow_header_lag`, `allow_stale_body` and `state_reviewed` retain their ordinary
meanings. Whole-table boundaries, LF/CRLF and final mode remain checked.

```json
[
  {"file": "CONTEXT.md", "edits": [{"op": "set-field", "field": "Phase", "value": "Review"}]},
  {"file": "REFERENCE.md", "edits": [{"op": "replace", "anchor": "Pending review", "replacement": "Reviewed"}]}
]
```

This example is syntax, not an assertion that a review occurred. Preserve the
ordinary evidence and coherence requirements for the actual edit.

## Authority and scope

The caller supplies a native event file. PM's existing `run_admission` verifies
its transcript/native seat, registry, physical checkout/branch and exact path
claims. A claimed project name alone is insufficient. Claims must cover every
target plus the `.record-transactions` directory. Recovery requires the
original native/seat/claim binding and repeats admission before each remaining
replacement. A JSON journal is not transferable permission. A changed claim,
foreign owner, alias, symlink, hardlink or different source inode refuses the
operation. No protective hook is disabled.

A transaction covers files beneath one project on one filesystem. The registry
owner also uses this journal for its exact `@registry` target, with the shared
registry lock and separate registry claim. Arbitrary outside targets and deletion
are not transaction operations.
Explicit `create` requests contain UTF-8 `text` and a nonexecutable `mode`
(0600 or 0644); the target must be absent. The owner uses atomic no-clobber
linking, not an overwriting rename, and authenticates its exact two-name
interruption state before retiring the staged name. A third hardlink or foreign
file refuses. Caller intent IDs identify retries and grant no authority.

The PM [migration owner](../../synthesis-project-management/references/project-migration.md)
uses this same transaction engine. Its optional source-custody list binds up to
512 unchanged inputs; their exact bytes are archived privately before durable
commit, authenticated on recovery, and counted in the 32 MiB aggregate budget.
Source custody cannot overlap an effect. It never restores over a later writer.
Schema-2 journals carry this additive/custody contract; historical schema-1
journals keep their exact original recovery semantics. Neither schema supplies
new cross-project or native mutation authority.

## Commit and recovery

1. Resolve every target and operation; check complete final results, byte/line
   limits, table boundaries and currency. Ordinary preflight refusal changes no
   target. Dry-run performs this preflight and authority check without creating
   a transaction store or target file.
2. Stage and fsync complete new files with final modes. Pin original and staged
   device/inode/hash/size/mode, the project-directory identity and native claim.
   Sync the manifest and commit decision, then atomically expose the active
   transaction directory. Preparatory artifacts that precede that boundary are
   retained custody; no target has changed.
3. Persist the active transaction identity in history before replacing a target.
   Replace each target, sync its directory, and retain all remaining staged
   bytes. Before each replacement, recheck authority and exact current source.
4. Read every final target back. Persist completion and clear the active history
   binding, then move the journal into completed custody and sync directories.
   Completion is reported only after these steps succeed.

Once committed intent exists, recovery rolls forward to that declared result.
It accepts only the exact pinned original file or the exact staged replacement
already installed by this transaction. A third state is foreign/ambiguous work;
all bytes remain untouched by recovery and the owner must reconcile evidence.
Missing/corrupt journals or changed authority do not authorize reconstruction by
guesswork. A completed transaction cannot be replayed over later edits. Removing
an active directory alone cannot clear the independent active-history binding.

An I/O error after a rename may mean effects occurred. Inspect the retained
transaction and use `recover-transaction`; never label the whole edit unchanged
from an error code. Process-loss tests exercise real subprocess exit; they do
not simulate every storage controller's power-loss semantics. Filesystem fsync
errors remain failures rather than inferred durability.

## Visibility to readers

Ordinary POSIX path replacement does **not** simultaneously publish several
files. This is a cooperative logical transaction with deterministic recovery,
not a filesystem-level all-or-none rename guarantee. A generation-pointer
scheme would require changing the public layout and all ordinary path readers;
this owner keeps the accepted CONTEXT/REFERENCE/session interfaces.

Managed context edits, causal project selection, state compilation/checkpoint
verification, format refresh, context doctor, and checkpoint refresh hold the
same project-directory lock across their complete operation. They refuse an
unfinished transaction before accepting records. Read-only inspection does not
create lock files, modify the transaction, claim ownership, or repair it. Locks
wait at most five seconds. Raw JSON decoders/digest utilities do not certify a
coherent project; their managed callers supply this boundary. An external text
editor, direct file reader, older installation, Git checkout or other writer
that does not use this protocol can still observe or cause intermediate state.
Coordination ownership and final snapshot checks remain required.

The transaction keeps up to 128 files, 1,000 operations per file, 8 MiB per file,
32 MiB total output, a 1 MiB manifest, and 4,096 completed identities per store.
Capacity exhaustion refuses further writes without deleting history. Retain
all preparation/completion artifacts through the project's normal evidence
custody; do not clear a store to silence a refusal.

## Publishing completed record edits

Transaction completion means the local record mutation committed. It does not
mean `REMOTE_READY`. Completion receipts include `publication.required_files`,
an exact SHA-256 map covering the changed targets, shared history, completed
manifest, commit decision and preserved source copies for that transaction.
Registry edits include `projects/index.yaml` in the same selection. Keep the
journals tracked alongside the records: do not add an ignore rule, exclude the
store from the context doctor, or delete it to make readiness pass.

Before remote handoff, the agent runs the existing editor's read-only selection:

```bash
python3 scripts/context_edit.py transaction-publication --project /absolute/project
```

Its `required_files` includes all retained transaction-store bytes, failed
preparations and current target bytes. The owner verifies completed history and
commit bindings and archived source digests, refuses unfinished active intent, unsafe files, changing bytes
or membership, and returns `remote_ready: false`. Historical journals retain
their original native/inode/path evidence; a selection never replays it or
turns it into authority on another checkout. Missing or corrupted custody must
be reconciled before publication. Bounded selection refusal never means a
partially listed store is complete.

Use the current session's exact claims and ordinary attribution/publication
owner for those selected files. Stage and commit only the reviewed selection,
including the journals, while preserving every unrelated staged path; verify
the actual selected committed blobs, then publish through the existing guarded
remote-handoff owner. A receipt does not grant disclosure or Git authority.
Run context doctor at remote readiness after publication and verify the
ordinary publication receipt/remote refs. Neither the plan nor a local commit
asserts remote delivery. A later transaction changes history and creates new
journal bytes, so obtain a fresh selection before the next handoff.

### Optional resolver fast-forward

Ordinary project resolution holds shared record locks. When the caller explicitly
enables canonical fast-forward, the resolver also acquires exclusive barriers
for every existing project directory in that canonical checkout, in stable path
order. Git fast-forward is checkout-wide, so limiting its lock to the selected
project would allow unrelated records to change during another managed read.
An existing transaction or reader prevents that mutation; a fresh record
directory appearing after lock admission refuses fast-forward. These locks do
not grant write authority or enable fast-forward when the caller did not request
it. The original upstream, source-tree, clean-checkout and retention gates remain.

Failed pre-commit preparations never authorize effects and are retained. A retry
under the same caller intent uses a distinct preparation directory after fresh
source and native authority checks. At most 64 retained preparation directories
are admitted per store (and 64 initial store preparations per project); reaching
that bound refuses further preparation and requires explicit custody review,
never automatic pruning. A published active commit still requires exact recovery.
