# Preserved: the 2.21.6 state, format, closure, team and record references, verbatim

Structured state, format versions and migration, checkpoint closure recovery,
execution evidence, canonical landing, autopilot project quality and team
governance, unchanged; also the 2.21.6 records-and-conventions and
codex-dispatch references, which v5 carries forward with small edits. v5 cut or
replaced the rest;
[coverage-map.md](coverage-map.md) gives the verdict and the v5 part for each.
Read only to review the cut.

## Contents

- [project-state-recovery.md](#project-state-recoverymd)
- [project-formats.md](#project-formatsmd)
- [project-migration.md](#project-migrationmd)
- [checkpoint-closure-recovery.md](#checkpoint-closure-recoverymd)
- [execution-basis.md](#execution-basismd)
- [autopilot-project-quality.md](#autopilot-project-qualitymd)
- [canonical-landing.md](#canonical-landingmd)
- [team-contract.md](#team-contractmd)
- [team-managed-workflows.md](#team-managed-workflowsmd)
- [records-and-conventions.md](#records-and-conventionsmd)
- [codex-dispatch.md](#codex-dispatchmd)

## project-state-recovery.md

Verbatim from `skills/synthesis-project-management/references/project-state-recovery.md` at 2.21.6. Links inside point where they pointed then.

# Project-state recovery

`scripts/project_state.py resolve` discovers a named project's state across the
canonical checkout, registered isolated worktrees, local and remote refs,
attributed dirty paths, lifecycle manifests and receipts, the active-project
pointer, and coordination claims. Each candidate records its worktree or ref,
project-touching commit, project tree, timestamp, dirty-path hashes, and owning
session where one is provable.

Equality and Git ancestry are the only ordering evidence. Timestamps describe
observations but never select a winner. A dirty state extends its exact base
commit; if a newer committed project state exists, the two are divergent until
reconciled. Two distinct attributed dirty states are also divergent. Missing
worktrees, unreadable evidence, and failed fetches are `UNKNOWN`; divergent
states are `CONFLICT`; an attributed interruption is `LOCAL_RECOVERABLE`.

A canonical checkout may fast-forward automatically only when its current head
is an ancestor of the selected head, tracked and staged state are clean, no
untracked path would be overwritten, and the selected project still exists
after the move. Otherwise the resolver reports the exact fresher source without
mutating unrelated state.

## Checkpoint applicability

The checkpoint CLI, validation, native project discovery and refresh inspection
share the structured-state applicability decision. A verified registered ordinary
project that never adopted structured state returns `NOT_APPLICABLE`,
`checkpoint_accepted: false` and `no_receipt_issued: true`, with successful command
completion. This is neither project health nor a recovery/authority receipt.
Ordinary context, session records and normal continuity obligations still apply.

Existing state, compiled state markers and verified Git adoption evidence retain
the structured obligation. Deleted, malformed, unreadable or unsafe state remains
blocking. Missing project paths, missing registration or unverifiable evidence
cannot establish non-applicability. Removing the state file is not a migration.
The direct `checkpoint_project` function is a receipt-only API for adopted state;
command and hook callers establish applicability before requesting a receipt.

Structured projects store mutable operational truth in `CURRENT_STATE.json`:
phase, status, accepted baseline, controlling plan, next actions, last session,
owning coordination session, repository/project identity, durable Markdown
hashes, and source-repository heads. The bounded current-state block in
CONTEXT.md is compiled from it; narrative and historical acceptance remain
Markdown.

`scripts/plan_reference.py` is the shared controlling-plan resolver for state
and client context. A structured `controlling_plan` field takes precedence;
otherwise an explicit context field takes precedence. `Controlling plan: none`
and an explicit `No active plan` line stop selection: historical links cannot
become a controlling plan. The existing absent-plan payload value is `unknown`,
with an explicit no-active-plan diagnostic; structured state still requires a
verified plan file and does not acquire a new null schema value.
Without an explicit field, one standalone link labeled `plan`, `active plan`,
`current plan` or `controlling plan`, in the document header or a section with
one of those names, is a shorthand declaration. Checklist,
paragraph, historical and fenced-example links do not establish authority.
Multiple declarations refuse rather than selecting by link order or path prefix.
Malformed, missing or ambiguous references refuse resolution. Parent-project
plans are allowed only inside the same repository, without traversing internal
symlinks. Outside Git, plans remain project-local. Stored paths are portable
project-relative references, not worktree-specific absolute names.

Parent-plan bytes enter semantic state and checkpoint hashes. Editing or deleting
that plan invalidates the prior receipt; deletion reports recoverable rather
than throwing an unhandled exception. Historical prose is retained, not rewritten
to match a newer structured field. If structured state is absent, competing
explicit legacy fields remain ambiguous and require reconciliation.

Release-currency prose checks prioritize the structured accepted baseline over
a candidate phase. Candidate, planned and example versions are not shipped
evidence; separately affirmed releases still expose a stale baseline. This is
a bounded consistency check, not proof of publication. Verify Git, release
receipts and installed payloads before making an external-state claim.

Use the same executable to create and verify that state; do not hand-edit the
compiled block:

```bash
python3 scripts/project_state.py build \
  --project /absolute/project/path --project-id example \
  --phase "implementation" --status active \
  --controlling-plan resources/artifacts/plan.md \
  --accepted-baseline 1.2.3 --next-action "Run acceptance" \
  --last-session 2026-09-03 --session-id SESSION_UUID \
  --source-head /absolute/source/repository=COMMIT

python3 scripts/project_state.py checkpoint \
  --project /absolute/project/path --session-id SESSION_UUID \
  --coordination-board /absolute/active-sessions.md \
  --receipt-root /absolute/project-state/receipts \
  --source-head /absolute/source/repository=COMMIT
```

Every repeated `--source-head` is resolved to a commit before the state or
receipt is issued. `validate` accepts the same source bindings. A changed
source head invalidates the prior clean receipt instead of being treated as a
fresh handoff.

The lifecycle hook first refreshes the coordination lease, then issues a clean
receipt only when the event matches one active coordination seat and its
project, state, claim, Git identity, durable hashes, and live source heads all
validate. An interrupted event retains the file-attributed pending manifest
and remains recoverable, but never receives a clean receipt. Foreign project
sessions never block one another.

## project-formats.md

Verbatim from `skills/synthesis-project-management/references/project-formats.md` at 2.21.6. Links inside point where they pointed then.

# Project format versions

Projects carry an on-disk format version so the system can evolve
without breaking old projects. Added in skill v2.16.0.

## v1 (unmarked)

`CONTEXT.md` + `REFERENCE.md` + `sessions/YYYY-MM.md`, with no
marker file. Everything in every workspace predating v2 is v1.

## v2 (marked, strictly additive)

Everything in v1, plus exactly three files:

```
{project-id}/
├── .synthesis-project.yaml  # format_version, id, migration record
├── RESUME_STATE.json        # resume state, schema v1 (below)
└── sessions/INDEX.md        # generated per-period manifest
```

`RESUME_STATE.json` schema v1 keys: `schema` (1), `goal`,
`status`, `open_loops[]` ({id, text, owner, since}), `last_session`
(period), `last_brief` (one paragraph), `updated_at`. Fresh
migrations write a skeleton labeled `"skeleton": true` with
`unverified` loops; the next real session verifies and overwrites.

`CURRENT_STATE.json` is a different file with a different owner:
the operational handoff shape managed by `project_state.py`.
Migration never touches it; resume reads both (resume state first,
operational state second).

## Engine

`scripts/project_format.py`:

- `detect <dir>` → missing | v1 | v2 | partial | unknown.
- `migrate --check <dir>` → what would be added; writes nothing.
- `migrate [--goal TEXT] [--status TEXT] <dir>` → adds the three
  files, then verifies by re-reading them.
- `archive [--older-than-days N] [--check] <dir>` → moves session
  periods older than N days to `sessions/archive/` (v2 only, never
  the newest period) and regenerates the index, which covers both
  live and archived periods. Default retention is 365 days — a
  year of live history unless the principal says otherwise.

## Explicit closeout refresh

Run `project_format.py refresh --check <dir>` to preview and
`project_format.py refresh <dir>` to apply. It refreshes the generated index and
resume candidates using the existing schema. Indexes recognize all six ATX
heading levels, skip fenced examples, and distinguish dated entries from
interior undated headings. Long indexes state the full entry count and the
number omitted from the compact listing.

Migration and refresh seed unchecked `CONTEXT.md` tasks alongside explicit
markers in the newest session log. A session marker starts an unquoted line
(with at most three leading spaces) or an unordered/numbered list item and is
exactly `TODO:`, `FIXME:`, `XXX:`, `OPEN:` or `TBD:`, followed by horizontal
whitespace and nonempty task text. Lowercase words, labels inside ordinary
prose, checked tasks, fenced/indented code and blockquote examples (including
lazy continuation until a blank or new block) do not seed candidates.
Unchecked context tasks likewise start an unquoted list item outside code.
Session marker text remains a bounded 120-character candidate preview;
its source path, line and digest retain the complete underlying evidence. Candidates carry relative source path, line and source
digest, remain `unverified`, and are never automatically treated as completed.
Repeated task wording keeps distinct source occurrences. Candidate IDs survive
line shifts; source hashes and line numbers describe the original observation,
not a claim that unchanged wording has been reverified.
Refresh preserves curated goal/status/brief, reviewed loops, additional state
fields, and candidates whose source disappears. It adds only new candidate IDs.
Human or authenticated session reconciliation still owns verification and closure.

A second unchanged refresh preserves bytes and modification times. All inputs
preflight before output writes; each output replacement is atomic, but the
index and resume state are **not** a multi-file filesystem transaction. If the
process stops between them, rerun refresh under the same normal project-records
ownership to converge. The command refuses malformed state, symlink targets and
an index owned by another writer. Duplicate JSON keys are refused, including in
curated nested fields. File mode and contents are synced before each rename,
then the parent directory is synced; a post-rename error requires inspecting the
outputs before retry. It never edits `CURRENT_STATE.json`.

## Rules for every version, present and future

Material preservation applies independently of format. The shared checkpoint and
doctor result exposes declared inputs and association reachability for v1 before
structured NOT_APPLICABLE. Follow [material context](../../synthesis-context-lifecycle/references/material-context.md);
do not migrate or enroll a project to manufacture coverage. Refresh preserves
curated loops and avoids recreating exact terminal source spans; changed source
bytes require reconciliation, and absent source never completes an obligation.

- New versions are strictly additive. Old readers keep working.
- Migration is pull-based, on resume: inform the principal in one
  line, migrate, verify, then resume work. Never migrate under a
  live foreign claim.
- Migration never overwrites: existing state/index files are kept
  and validated; a kept file that fails validation fails the
  migration closed (marker rolled back) for a human to fix.
- Downgrade is deleting the added files.
- Writers refresh the state file and index at session close; never
  hand-edit `<!-- generated -->` sections.

## project-migration.md

Verbatim from `skills/synthesis-project-management/references/project-migration.md` at 2.21.6. Links inside point where they pointed then.

# Explicit project-format migration

Use `synthesis project-migrate plan --index <registry> --select <project-id>
--target-format 2 --json`. Repeat `--select` for an exact set, or choose
`--all-declared` to freeze all IDs in that explicitly selected registry. No home,
workspace or repository crawl selects projects implicitly. Each project is
resolved causally with fetch, fast-forward and coordination refresh disabled.
For several workspaces, produce a separate exact plan for each declared registry;
those plans retain independent consent and owner boundaries.

The only implemented transition is the existing v1→v2 format. This package does
not choose SQLite, invent a future format, replace CONTEXT/REFERENCE/session
records, or infer that upgrading the ecosystem release upgrades a project.
Partial, ambiguous or unknown formats refuse. A verified existing v2 project can
appear in a plan as `verify-current`, with no rewriting. Its marker, state and
session index must validate rather than merely exist.

The preview includes exact selected IDs, registry and directory identities,
source inode/hash/mode/size evidence, complete proposed UTF-8 output bytes and
hashes, a one-hour validity interval, and a digest. The canonical builders create
`.synthesis-project.yaml`, `RESUME_STATE.json`, and `sessions/INDEX.md`.
A generated resume skeleton and extracted open loops are marked unverified;
they never become a decision, approval, proof of completion or native acceptance.
The preview is a private proposed diff, not consent to apply it.

`project-migrate apply --plan <preview> --approve <digest> --board <board>
--native-payload <payload>` accepts that exact reviewed plan. `--dry-run` checks
inputs and real authority without creating a store, archive or target. `--project
<id>` selects one project already in the approved plan for execution by its real
native owner. Other projects remain explicitly pending. Without this selector,
every requested project's authority is checked before the first mutation.

PM admission still binds a native seat to its exact project/checkout and claim.
An approved multi-project plan is not permission to impersonate other sessions,
create their claims, release them, or bypass their record barriers. Execute each
project through its genuine owner; archive and transfer are not approvals.
Claims must cover the new paths and the existing `.record-transactions` store.

The existing record transaction owner stages new files, captures the exact
original CONTEXT/REFERENCE/session bytes into its private source custody,
fsyncs custody and commit intent, then uses no-clobber creation. A new competing
file is preserved. Modes are private 0600; no executable records are created.
Source files remain byte-for-byte and inode-for-inode unchanged. The manifest
retains their original identities and authenticated copies before effects.

One project is a cooperative recoverable transaction, not simultaneous atomic
renames visible to arbitrary readers. A selected set is not one global filesystem
transaction. Consent freshness is rechecked under the project lock immediately
before each new project transaction, after whole-set preflight and re-derivation.
A wait or earlier project cannot extend that lifetime. If a later outside change
or expiry interrupts execution, completed project
receipts remain committed and other projects remain incomplete. Existing managed
readers refuse an active partial transaction. External readers do not acquire
this protection merely by reading ordinary paths.

`project-migrate recover --plan <preview> --approve <digest> --board <board>
--native-payload <payload>` can finish only the exact original journal intent;
expiry does not authorize new migrations. The same `--project <id>` selector
limits recovery to one approved project under its genuine owner. It retains missing/corrupt/foreign
states rather than overwriting them. Completed intent is verified by its
independent history binding, manifest/commit hash, preserved source custody and
exact final target inodes. Identical repeat application verifies completed intents even after preview
expiry; it cannot start an uncommitted project with expired consent. Verification
and exact-journal recovery do not authorize new effects;
later edits are not silently migrated again. `project-migrate verify --plan
<preview>` verifies derived format custody. It does not establish client reload,
hook trust, native execution or cross-client semantic acceptance.

Plans allow at most 128 selected projects and 512 source files per project,
8 MiB per input, 32 MiB combined source custody/output per transaction and a
1 MiB plan. Capacity exhaustion is a refusal, never silent truncation. The
existing record owner retains its five-second locks and 4,096-entry history
bound. Preserve interrupted preparations, original failures and completed
custody through the project evidence owner; never prune them to pass a gate.

Deployment requires the matching onboarding CLI, project-format builders and
record-transaction module in one verified release. Installation alone is not
migration. An actual selected-project migration and each client's native reload
remain separately observable acceptance operations.

## checkpoint-closure-recovery.md

Verbatim from `skills/synthesis-project-management/references/checkpoint-closure-recovery.md` at 2.21.6. Links inside point where they pointed then.

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

## Committed local source retained after claim release

A source branch awaiting publication can retain its exact native manifest after
the owner completes its checkpoint and releases the claim. The observer may
return `NOT_APPLICABLE` only with a source-only manifest and a complete, safe,
exact-session `LOCAL_READY` receipt whose manifest digest, repository identities,
branches, heads, file bytes and modes still agree. Attributed files must also be
committed and clean; the local handoff writer can record uncommitted work, so its
readiness label alone never satisfies this condition. Changed or missing evidence
and any context-publication obligation remain blocking. Applicable structured
project checks still run.

This result records observer non-applicability, with `checkpoint_accepted:false`
and no project receipt. It neither certifies remote readiness nor grants new
ownership or publication permission. The manifest and local receipt are retained.
Do not create a replacement claim, delete attribution, or publish a gated source
branch merely to stop repeated diagnostics. The ordinary owner checkpoint and
authorized publication/retirement protocols keep their existing requirements.

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

## execution-basis.md

Verbatim from `skills/synthesis-project-management/references/execution-basis.md` at 2.21.6. Links inside point where they pointed then.

# Complete execution evidence at project scale

An execution basis binds the retained project bytes used by an admitted
autopilot run. It does not replace project management's whole-project checkpoint
or grant run ownership, action authority, native capability or task completion.

The execution receipt carries file-commitment schema 3 with a framed SHA-256
commitment to each member's relative name and type. Regular files bind their
normalized size and complete contents. Retained symlinks bind their link text
and inode metadata; FIFOs, sockets and device entries bind their type and inode
metadata. These custody-only members are never opened or followed as execution
inputs. Unowned directories, including empty directories, bind their names and
permissions. A second commitment
omits only the explicitly named CURRENT_STATE record and carries the context
record separately for the existing verified terminal-state successor check.
The selected run's owner-verified journal projections and digest-addressed
managed inputs retain their established derivation rules. Other runs, archives
and unknown evidence files stay included.

The inventory reads arbitrary evidence in chunks of at most 1 MiB. Semantic
documents and structured inputs retain their separate 16 MiB parsing bound.
Directory-descriptor traversal and before/after identity checks reject linked
project ancestors, changed directory membership, replacement, truncation and
growth. The plan, journal projections and immutable inputs must remain regular
files. Directory paths derived from the selected journal and inputs are owned
by their exact derivations; unrelated directories and evidence remain included.
A complete second metadata pass checks for observed changes after a file was
hashed. This is observed consistency, not an atomic filesystem snapshot against
an arbitrary concurrently hostile process.

Each operation permits at most 250,000 entry visits across both passes, 16 GiB
of streamed contents and 128 directory levels, with a checked 120-second
monotonic deadline. Saturation refuses the operation. It never returns a
partial inventory or silently omits large files. The deadline is cooperative
around local filesystem calls; it cannot cancel an indefinitely blocked kernel
filesystem operation.

Larger observations require a managed immutable input selected explicitly by
the existing `checkpoint` operation's `inventory_policy_id`. Its typed JSON is:

```json
{
  "schema_version": 1,
  "kind": "execution-inventory-policy",
  "limits": {"entries": 2000000, "bytes": 17179869184, "seconds": 240, "depth": 128}
}
```

Materialize the value through the existing `input.materialize` owner. Every
limit must be a positive integer. Supported ceilings are 4,000,000 entry visits
across both passes, 64 GiB, 300 seconds and 128 directory levels. A policy is a
processing budget, never ownership or permission. The receipt binds its input
ID, path, digest and limits into the file commitment. Validation re-reads the
immutable policy and the entire project. No inventory cache is accepted.

Automatic checkpoints retain the explicitly selected policy from the current
checkpoint journal. Passing `inventory_policy_id: null` explicitly restores the
default bounds. Profile evidence uses the same selection. An unselected project
always uses the protective defaults; no environment variable or discovered
policy file can raise them. A policy applies to each complete inventory, so a
caller that performs several inventories must also bound its aggregate work.

Validation re-observes the complete inventory. A changed, added, renamed or
missing member invalidates the commitment. Current proof reporting uses the
same fresh inventory that it validated, avoiding a second complete inventory.
A successful terminal PM successor
requires the existing ordinary owner proof, unchanged operational fields and
the complete non-state commitment; changing the aggregate digest in a receipt
does not manufacture valid evidence.

Older execution receipts require fresh capture through the existing admitted
checkpoint or recovery owner. They are not silently converted. Retain the old
receipt and any failed recovery prefix; reconcile the actual journal before
retrying an interrupted request. Never reset costs, deadlines or unfinished
obligations to obtain a new receipt.

## autopilot-project-quality.md

Verbatim from `skills/synthesis-project-management/references/autopilot-project-quality.md` at 2.21.6. Links inside point where they pointed then.

# Project and knowledge outcome review

Use the [material-context inventory](../../synthesis-context-lifecycle/references/material-context.md)
as a declared denominator in the existing obligation-preservation and causal
recovery rubric. Compare retained source and output spans, including reasons,
temporary conditions, uncertainty and cancellation. Keep whole-session scope,
historical gaps and independent semantic acceptance explicit. Calibrate with a
faithful concise paraphrase plus omitted-condition, invented-approval and dropped
request controls. Programmed fixture judgments do not establish model accuracy.

Trace each remaining obligation from its durable source to a current retained
record, owner and next action. Compare obligation identities and meaningful
content, not just counts. An omitted obligation or a changed unresolved status
is a defect even when the handoff reads well.

For causal recovery, the consumer should demonstrate that the selected record
and source generation can reconstruct the declared work without replaying an
ambiguous effect, replacing a newer fact or erasing retained evidence. Use the
existing project resolver and checkpoint owner when the task claims whole-project
readiness. A selected artifact digest proves only that artifact's bytes.

Ownership integrity uses the current PM/native claim-ownership receipt. The
six-family controller collects that readback for a project-domain run, and the
evidence owner revalidates it against the exact active seat and claims. A stale,
released or foreign seat cannot certify ownership. This readback does not grant
permission to release another seat, adopt its manifest or rewrite its work.

Judge handoff usability against the receiving worker's actual task. It should
identify the remaining outcome, relevant sources, authority boundaries, effects
awaiting reconciliation and next execution step. A sound concise handoff is a
positive control. Seed failures such as dropping one retained obligation,
selecting an older causal generation or stating that ownership is transferable
without admission. Execution checks and semantic calibration remain separate.
The execution-basis checkpoint and the final whole-project checkpoint also
retain their distinct scopes.

## canonical-landing.md

Verbatim from `skills/synthesis-project-management/references/canonical-landing.md` at 2.21.6. Links inside point where they pointed then.

# Canonical Checkout Landing

`scripts/canonical_landing.py` observes one literal `git push REMOTE
SOURCE:main` and fast-forwards the canonical checkout to the verified
remote commit — behind the explicit-push trigger only. Dynamic,
grouped, multi-ref, nested, and script-internal pushes are never
landed; neither are pushes with force, dry-run, deletion, or mirror
flags. Shell parsing comes from sibling
`scripts/publication_command.py`.

Entry points: `capture_before` records the pre-tool source at the
push boundary; `process_after` makes one bounded landing attempt
per call. Receipts distinguish observed remote state (`observed`,
`remote_published`), canonical state (`canonical`), and claim
cleanup (`claim_cleanup`).

Landing admits a board claim on the incoming paths, then re-verifies
checkout identity, cleanliness, remote stability, and claim authority
before the fast-forward, and restores only its own authority
afterward. It refuses: foreign same-checkout use, unclean or
diverged canonicals, non-main checkouts, in-progress Git operations,
submodules, unbounded checkout effects (filters, fsmonitor, hooks),
and contributor seats landing canonical context. A refused landing
is a maintenance finding in the receipt, never a partial write.

## team-contract.md

Verbatim from `skills/synthesis-project-management/references/team-contract.md` at 2.21.6. Links inside point where they pointed then.

# Team contract and participation boundaries

Read this contract before enabling multi-person coordination. Its owner is
`scripts/team_contract.py`; the existing coordination, project-state, enrollment,
Git guard and repository ACL owners remain authoritative for their own effects.
This is an opt-in source contract. A passing validator is not account enrollment,
proof of a person's identity, a host ACL, permission to send, or a native trial.

## Organization, people and standing roles

A version-1 team declaration binds an organization, deletion unit and monotonic
revision to people, immutable host account IDs, repositories, entitlements,
standing-role occupancy and release governance. Usernames are display labels.
Keep real roster/account mappings in the organization's approved private store.
A service identity names active human custodians and cannot occupy a human role.
Retired opaque IDs remain in attributable history; private biographical records
follow their deletion unit. Never rewrite an old author as the new occupant.

A standing role is separate from a temporary coordination session. Its dated,
non-overlapping occupancy records the prior and next human, a digest of the
succession brief, and explicit cover. `transfer_occupancy` is a pure proposed
transformation with a revision compare; the organization owner publishes it
under the existing claimed-record transaction and approval boundary. It does
not transfer sessions, leases, credentials, repository access or old approvals.
Offboarding checks account revocation, open occupancy and outstanding owned
claims separately; unknown evidence cannot become an offboarding pass.

## Enabling a team board

1. Verify all selected readers understand schema 6, using the release-bound
   coordination/conformance owners. Readers that cannot parse the schema must
   refuse it. Preserve the original board and history through the existing
   migration/record owner; do not hand-rewrite a live shared board.
2. Under the board owner's authority, release all existing sessions through
   their actual owners. Use `coordination.py migrate --team-contract team.json
   --team-digest <sha256> --expected-board-sha256 <reviewed-board-sha256>` to bind
   the regular sibling declaration through the existing lock/Git CAS owner.
   The command refuses stale boards, active/parked sessions and source drift;
   ordinary session mutations cannot add, remove or replace this binding.
   This explicit enrollment records a declaration, never a reader-readiness
   attestation. Actual reader qualification is the separate prerequisite above.
3. Claim through the current coordination CLI with `--person <opaque-id>` and,
   when applicable, `--standing-role <opaque-id>`. The native session, agent,
   client and machine must match their existing exact identity checks. The
   person must be the current occupant or explicit cover for the standing role.
4. Every claim still uses existing repository identity, scope and lease rules.
   Changing the person label on an existing session is forbidden. Succession
   names the incoming principal explicitly; it cannot adopt a foreign claim.
5. Include one `Session identity: {"session":"…","person":"…","native":"…"}`
   line in each newly written dated session entry. Keep legacy unattributed
   entries unattributed. The context doctor counts distinct sessions on the same
   day and refuses contradictory identity metadata; nested headings are not
   extra sessions. Checkpoint receipts bind the writer tuple to the board digest.

These declarations do not authenticate the human who supplied an opaque ID.
The repository/board hosting ACL and organization enrollment ceremony are the
identity backstop. Test those with a genuinely independent person before
claiming team acceptance. Editor bypass, remote-host enforcement and stale
lease behavior must be exercised at the actual deployment boundary.

## Shared and private sources

Shared organizational records and each person's private companion are distinct
repositories in the same deletion unit. A private companion has one declared
reader; that does not imply administrators cannot access the hosting service.
A shared reference may not depend on content inaccessible to its reader set.
An unavailable private tier is `UNKNOWN/UNAVAILABLE`, not an empty or clean tier.
Registry union must retain repository-qualified project identities and conflicting
sources; do not merge restricted prose into the shared index. Review each
lesson's audience before promotion. Archive ownership follows the source owner.

## Policy and approvals

Mandatory restrictions compose by union; allowed approval roles compose by
intersection. Empty eligible roles mean no authority. Reader floors only rise.
An individual allowlist never subtracts a team requirement. Actor identity and
the subjects mentioned in content are separate disclosure checks. Reuse each
existing action owner for exact approval and single-use receipt enforcement.

For Git, the owner may enroll digest-bound `team_policy_files` in the existing
private guard configuration. Each source has schema 1, organization, explicit
credential-free `repository_prefixes`, and `mandatory_patterns`. No exemptions
are accepted. The mandatory rules run before personal allowlists and path
exclusions, for both staged content and commit messages. Changed source bytes,
unsafe file identities and malformed declarations refuse the operation. This
package does not activate a policy or configure a host branch rule.

## Enrollment and releases

The organization manifest may bind `team_contract: {path, sha256}`. Persist
`principal_selection: {person, requested, team_digest}` in that organization's
existing desired-state entry. Enrollment derives required, optional and role-
gated resources from the complete inventory; excluded resources are excluded,
not permanent errors. A changed declaration requires renewed explicit selection.
Fresh selection uses the actual enrollment owner: `synthesis enroll --org-repo
<approved-repository> --team-person <opaque-id> --team-digest <reviewed-sha256>`.
Repeat `--team-entitlement <id>` for optional resources. Omitting optional resources
selects only eligible required resources. Repeating enrollment without these flags
preserves the existing explicit selection; changing any selection requires both
person and current declaration digest. Stale declarations or unauthorized resources
refuse before enrollment effects. This is selection, not human authentication.

Each knowledge entitlement binds a declared repository ID; its actual source
remote and reader set are checked before acquisition. A required resource
outside that person's audience remains excluded, and an explicit request refuses.
Host membership is person-once; native authentication, client readiness,
configuration and receipts are machine-each. No secret is copied by this contract.

Receipts and caches are organization/deletion-unit-qualified. Installing another
organization cannot retire the first organization's copies. A target collision
refuses; it does not silently replace an installed skill. Unscoped historical
copies require owner-led reconciliation rather than automatic reassignment.
Shared skill sources pin stable/edge plus an exact version, mirror owner and
review/direct-main-audit policy. Personal configuration belongs outside installed
copies; private namespaces use opaque principal IDs. Existing release and
verified-runtime owners enforce integrity and installed dependency closure.

## Fleet and actual acceptance

Reuse causal project recovery, machine-sync and fleet-handoff owners. Wall-clock
order alone cannot resolve conflicting updates. Offline or unknown remote state
never proves freshness, grants a lease or authorizes overwriting a peer. Fleet
health contains only declared opaque identities, capability state and evidence
pointers, not transcripts, secrets or private content. Environment-specific
resource/secret declarations stay separate; no migration is activated here.
A local per-person Console may observe shared sources under the person's ACL.
A hosted team Console requires a separate identity/authentication design.

Completion requires an independent second person to perform a complete native
session cycle, plus real second-machine enrollment and interruption recovery.
Synthetic adapter fixtures, installed bytes and declared identities establish
only their named layers. Preserve failed trials and unknown historical evidence.

## Managed action and contribution owners

Read [managed team workflows](team-managed-workflows.md) before using team-bound
registry readers, publication approvals, contribution reports, appointments or
retirement. These commands reuse record, coordination, enrollment and release
owners; their acceptance boundaries distinguish managed custody from host access.

## team-managed-workflows.md

Verbatim from `skills/synthesis-project-management/references/team-managed-workflows.md` at 2.21.6. Links inside point where they pointed then.

# Managed team workflows

Use the existing `synthesis team` commands with an explicit JSON `--request` file.
The release launcher verifies the record, enrollment and journal readers used by
these routes. No command authenticates a human account, changes hosting ACLs,
releases somebody else's claim, or sends a message to an external service.

## Restricted project readers

An organization-owned project index opts in with exactly one line:

```text
# Synthesis-Team: team.json @ <exact-sha256> / <repository-id>
```

The sibling declaration must name the index repository's exact `origin` URL.
The current native board binding, opaque person, and declaration digest must
agree before the resolver, write admission, project routing, portfolio review,
context doctor or machine inventory exposes enrolled project records. A missing
or retired principal refuses. The local Git record also detects removal of a
committed enrollment marker from the working index.

A project reference sent to the coordination board must be readable by every
active human in the bound declaration. Restricted project IDs therefore do
not become shared-board messages. This contract covers these managed owners;
it cannot prevent an independent host tool or privileged filesystem editor
from reading or replacing data. Hosting ACLs and trusted enrollment remain
necessary. Generic un-enrolled indexes keep their ordinary route.

## Contribution inventory and appointment

`contributions` takes `team`, `team_digest`, `inventory`, and optionally
`evidence_root`. The inventory binds one exact declared repository and records
`observed_at`, complete coverage with an exact item count and no continuation
cursor, and every issue's dated events. Lanes, audience, runtime and evidence
plane are report fields; no remote label changes occur. Unanswered items remain
right-censored at the observation time. A median over answered items is not a
production response SLO or proof of remote coverage.

For appointments, save each captured event in the existing project at
`resources/evidence/contributions/<sha256>.json`. Its exact body is
`{"issue_id": "<id>", "event": <event-without-sha256>}`. The inventory names that
hash. Capture provenance is an operator attestation; these bytes do not prove
provider authentication. `propose-role` requires that evidence directory and
returns a proposal, never an appointment. It takes `person`, `role`, explicit
`scope`, active `backup`, and optional exact `replaces` appointment ID. A
contributor needs accepted work; repeat contributor and maintainer need three
accepted items, with a maintainer spanning two lanes. Runtime stewardship also
requires live runtime/compatibility evidence for every requested runtime scope.
These are published proposal thresholds, not claims about existing contributors.

`appoint` takes the project, project-relative team record, exact old digest,
board and native payload, complete inventory, proposal, explicit approval
attestation and timestamp. It rechecks current scoped appointing authority and
captured evidence, then publishes through the existing claimed-record
transaction. Source evidence is retained by that transaction. The new role
history preserves replaced occupants and attribution. It grants no hosting
membership. The board owner must explicitly bind the newly approved declaration
before another native session uses its changed roles.

## Departure and asset custody

`observe-offboarding` takes a bound team, person, board and explicit repo-guard
root. Its coverage is the exact retained board projects and supplied guard root,
not an assertion that an arbitrary machine has no other state. Active or parked
claims, attributed pending edits, nonterminal owned runs, unsettled effects,
unresolved child work and unreadable journals prevent managed readiness.
Each project is read through the bounded operator view; corrupt or incomplete
pages cannot become a clean result.

`offboard` requires the exact observation-derived approval, current native
claim, departure time and complete service-custodian succession. It preserves
opaque identities and historical authors, closes occupancies, and refuses an
unresolved mirror owner or backup obligation. It writes the new declaration
through the record owner. Hosting revocation stays `UNVERIFIED_EXTERNAL`.

After that approved departed-person record exists, `assets-plan` takes an
organization manifest and exact principal selection. `assets-retire` takes its
15-minute plan, `approval_digest` and optional `dry_run`. It uses the existing
enrollment lock, receipt CAS and copy journal to archive exact principal-owned
derived skill copies. Source repositories, private data and other people's
copies remain. Edited copies, stale receipt generations and historical copies
without principal custody refuse; none is reassigned by inference.

## Mandatory publication policy

The existing publication guard can enroll exact `team_contracts` entries with
physical `repository`, declaration `path`, `sha256`, human `person` and optional
additional `policy_layers`. Mandatory restrictions are unioned; approval roles
are intersected. The guard enforces `human-publication` and
`no-rapid-redeploy`; an unknown required control refuses because this owner
cannot prove it. Team policy never bypasses the existing exact approval,
artifact readback or single-use consumption. Changed source, roles or policy
invalidate the prior approval. Local principal selection is not human login.

## records-and-conventions.md

Verbatim from `skills/synthesis-project-management/references/records-and-conventions.md` at 2.21.6. Links inside point where they pointed then.

# Records and conventions — formats, naming, and rationale

Detailed formats and the reasoning behind the durable-record layer. The
operating rules live in `SKILL.md`; this file carries the full versions.

## Why not your tool's built-in memory?

Several AI coding tools now ship a per-project memory feature that writes its
own notes as it works. It's genuinely useful within a single tool, on a single
machine, for a single session's worth of context. It is not a substitute for
this system, for three structural reasons:

- **Single-tool.** A memory file your tool writes for itself is invisible to
  every other agent you use. If you work across Claude Code, Codex, Cursor, or
  others — even occasionally — that memory doesn't travel with you.
- **Single-machine.** These features are typically scoped to the machine they
  run on, with no built-in sync. Work on a second machine, and the memory
  starts over from zero.
- **Not version-controlled.** Without git, there's no history, no diff, no
  recovery from a bad write, and no way to review what got saved.

This system solves all three by being nothing more than files in a git
repository: `CONTEXT.md`, `REFERENCE.md`, `sessions/`, and `lessons/`,
readable and writable by any agent through the existing record owners. Native
memory remains enabled as an untrusted capture buffer. Review and route exports
to the actual private repository and canonical record; synthesis records win
conflicts. Clearing requires separately qualified harness-native capability and
verified publication, and never follows from a local ingestion receipt alone.

## Project naming — the full rationale

Project `id` slugs are read every day — in the index, in directory paths, in
editor and window titles. Two rules, keyed to whether the project has a
defined end state:

**Bounded projects (ones that will someday reach `completed`) get verb-first
outcome names.** The name states the finish line: `migrate-blog-to-astro`,
`accept-vendor-contract-2026-03`, `release-kb-company-wide`. When the outcome
is in the name, "is this done?" answers itself, scope gets declared at
creation time, and zombie projects — bounded work that sits `active` in the
index for months because nothing in its name says what done means — become
visible on sight.

**Ongoing projects (`ongoing` status — operations seats, product
stewardships) keep noun names.** They name the thing being stewarded
(`payments-platform`, `workspace-operations`) because there is no finish line
to state. Time-boxed instances of a standing role (`platform-2026-q3`)
already carry their end in the date suffix; wrapping them in a generic verb
(`do-platform-2026-q3-work`) adds ceremony, not information.

**Generic verbs are banned.** `do-`, `work-on-`, `handle-`, `manage-`,
`run-`, `support-` say nothing — every project is doing work. The verb must
name the specific outcome. This makes the rule double as a classification
diagnostic: if no specific verb fits, the project is probably not bounded —
model it as `ongoing`, or split it until concrete outcomes emerge.

**Existing projects keep their names.** Renames churn paths,
cross-references, and history for no behavioral gain. The convention applies
to projects created after adoption; a mixed index is expected and harmless,
since `status` — not the name — remains the machine-readable lifecycle field.

## index.yaml — full example

```yaml
# Projects Index
# Last updated: YYYY-MM-DD

# Status values:
#   active    - Currently being worked on
#   paused    - Started but on hold
#   ongoing   - Continuous/maintenance work, no defined end state
#   completed - Has defined deliverables that are done
#   archived  - Old/obsolete, kept for reference only

projects:
  - id: migrate-blog-to-astro        # bounded → verb-first outcome name
    name: Migrate Blog to Astro
    status: active
    description: Brief description of what this project accomplishes
    tags:
      - tag1
      - tag2
    last_session: YYYY-MM-DD

  - id: payments-platform            # ongoing stewardship → noun name
    name: Payments Platform
    status: ongoing
    description: Standing stewardship of the thing being maintained
    tags:
      - tag1
    last_session: YYYY-MM-DD

  - id: launch-newsletter
    name: Launch Newsletter
    status: completed
    completed_date: YYYY-MM-DD
    description: What was accomplished
    tags:
      - tag1
    outcome: success
    key_result: Brief summary of what was delivered
```

## Lesson file formats

File naming: `YYYY-MM-DD-topic-slug.md`, all in the top-level `lessons/`
folder.

For incidents and mistakes:

```markdown
---
type: incident
title: Brief Title
severity: minor | moderate | serious | critical
---

# {Topic}: {Brief Title}

## What Happened
## Root Cause
## Impact
## Lesson
## Prevention
```

For patterns (generalized insights):

```markdown
---
type: pattern
title: Pattern Name
---

# {Pattern Name}

## Context
## Problem
## Solution
## Examples
```

## Agent attribution — full rules

When multiple agents contribute materially to a project — Claude Code, Codex,
Cursor, subagents, or different model/effort settings — record provenance
where it helps future work. Git authorship alone cannot distinguish agents
(different tools commonly commit as the same human), so the session log
carries it: one italic line per contributing agent at the end of the entry in
`sessions/YYYY-MM.md`:

```
*Attribution — agent: Codex CLI · model: unknown · effort: unknown · scope: single-stack sweep only (session lacked the Gmail connector) · verified: plan re-run to zero · ref: d4e5f6a*
```

Rules: record `model`/`effort` only when the current session or the user
explicitly provides them — otherwise the literal word `unknown`, never
inferred (git `Co-Authored-By` trailers are claims, not verification).
`verified` names only checks that actually ran. Never record secrets,
OAuth/callback URLs, or private config values. CONTEXT.md gets at most a
short `(via Codex)`-style tag when agent identity changes interpretation;
REFERENCE.md carries only stable agent facts (e.g., a standing connector
gap), removed when no longer true. Attribute only when it helps future work —
this is provenance, not telemetry.

The canonical convention with field definitions and worked examples lives in
the synthesis-context-lifecycle skill, "Agent Attribution."

## codex-dispatch.md

Verbatim from `skills/synthesis-project-management/references/codex-dispatch.md` at 2.21.6. Links inside point where they pointed then.

# Dispatching to Codex — the wrapper and the failures it removes

`scripts/codex_dispatch.py` is the supported path for sending a prompt to
Codex non-interactively. Use it instead of shelling out to `codex` directly.

```bash
python3 scripts/codex_dispatch.py --doctor
python3 scripts/codex_dispatch.py --prompt-file brief.md --out review.txt --report-only
```

Three failures it removes, each observed in production on 2026-08-30:

- **The silent stdin hang.** `codex exec` reads stdin when stdin is open.
  Backgrounded from a shell that leaves it open, it prints
  `Reading additional input from stdin...` and blocks forever. One dispatch
  sat at 0.0% CPU with a 39-byte output file for two and a half hours while
  the dispatching agent assumed a long review was running. The wrapper always
  passes `stdin=DEVNULL`.
- **Stall indistinguishable from work.** The wrapper watches *output growth*,
  not elapsed time, so a genuinely slow review is not killed while a blocked
  process is. It reports which one it found.
- **"Codex is unavailable."** The binary is not on PATH; it lives under
  `~/.codex/plugins/`. An agent that runs `codex` and gets *command not
  found* may wrongly report that cross-agent dispatch is impossible and stop.
  `--doctor` resolves the binary, prints the version, and proves
  authentication with a live round trip. Never report Codex as unreachable
  without running it.
