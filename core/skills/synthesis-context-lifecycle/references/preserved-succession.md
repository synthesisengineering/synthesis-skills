# Preserved: the 1.22.0 succession, material context, recovery and transaction references, verbatim

Four 1.22.0 reference files, unchanged. Their doctrine is in
[material-context.md](material-context.md); their machinery (schema-1 and
schema-2 succession requests, recovery capsules, record transactions) was cut
or moved ([preserved.md](preserved.md#what-was-cut-and-why)). Read only to
review the cut.

## Contents

- [artifact-succession.md](#artifact-successionmd)
- [material-context.md](#material-contextmd)
- [autopilot-recovery.md](#autopilot-recoverymd)
- [record-transactions.md](#record-transactionsmd)

## artifact-succession.md

Verbatim from `skills/synthesis-context-lifecycle/references/artifact-succession.md` at 1.22.0. Links inside point where they pointed then.

# Artifact succession and exact obligation accounting

`context_edit.py` owns this protocol. `record_succession.py` is its validator
and artifact compiler; it is not a second project database, approval ledger,
or transaction engine. State remains in existing project artifacts and working
context. `record_transaction.py` owns cooperative multi-file changes and recovery.

## Four independent questions

Schema 2 `material-context` requests extend this owner with explicit capture,
source provenance, conditions, meaning-review references and later amendments.
See [material context](material-context.md). The schema-1 transfer and retirement
protocol below retains its own declared-inventory and authority boundaries.

1. **Did every source item arrive?** The source inventory's exact IDs, not a
   narrative total or a receiver's list, define the denominator. Missing, extra
   and duplicate IDs cannot become a complete transfer. A declared count mismatch
   remains explicit even when all actual identities are accounted for.
2. **What evidence exists?** Each source reference binds project-relative bytes,
   SHA256 and one exact anchor. `primary` and `narrative` are declared source
   kinds, not authenticated facts. Complete transfer can have missing evidence;
   strong evidence for one item cannot make an incomplete transfer complete.
3. **Was a choice recorded?** An actual schema-2 record must bind the exact spec,
   contain the exact row set, valid option values and consistent counts. It may
   establish a recorded choice; its principal authentication remains unverified.
   Ordinary historical prose is retained as an unverified historical record.
   Neither absent answers nor browser-local state can be filled in.
4. **May work execute or close?** The answer from this owner is always unknown:
   `authorization_granted=false`, `completion_established=false`, and
   `readiness=requires-owner-review`. Existing action owners verify the real
   approval and outcome. Time-bound historical delegation is not renewed.

## Request and review

Use `context_edit.py review-succession --project PROJECT --request REQUEST.json`
for a read-only result. The JSON object has exactly these fields:

- `schema`: integer 1; `kind`: `packet-retirement` or `transfer`.
- `inventory`: `path`, `sha256`, `format` (`json-rows` or `packet-html`), and
  `declared_count`. JSON inventories contain `rows`, each with a unique `id`.
  Packet HTML must contain exactly one complete `script#spec` of type
  `application/json`. Unsupported free-form legacy markup returns UNKNOWN/refusal;
  do not manufacture an inventory or provenance marker.
- A packet may also supply `inventory.spec`, an exact reference to the filed
  canonical JSON input. Its runtime payload (including only the generator's
  defined defaults) must equal the embedded payload. This permits exact bound
  rulings to be checked without inventing the original input from defaults.
- `items`: receiving rows, each with `id`, `destination`, `decision` (reference
  or null), `proof`, and `obligations`. Every reference is `{path,sha256,anchor}`;
  destinations and evidence need a nonempty unique exact anchor. Paths stay in
  the selected project. Preserve incoming originals there before reconciliation.
- Each `proof` member is `{source:REFERENCE,kind:primary|narrative|unknown}`.
  Each obligation is `{id,destination:REFERENCE}`. An unanswered item or an
  unverified historical narrative requires at least one surviving obligation.
  This can be source/owner review; it is not an invented new principal question.
  Bound recorded choices may have no unanswered-choice obligation, but they do
  not certify that chosen implementation or publication work happened.
- `context_anchor`: one existing line-start anchor in `CONTEXT.md`;
  `context_max_lines`: positive line budget no greater than 150. The existing
  context coherence and table safeguards remain active.

Source IDs and obligation IDs are separate unique identities. Labels and a
summary count cannot substitute for identity. Inputs are copied into a bounded
canonical snapshot before review so caller mutation cannot change their meaning.
The result states the exact structured-inventory coverage; it does not claim to
have discovered every idea hidden in arbitrary source prose.

## Custody and live application

Use `context_edit.py apply-succession` with the same project/request, `--board`,
and `--native-payload`. The native payload is evidence passed to the existing
PM admission owner, not an authority token. `--dry-run` verifies the current
request, claims, destinations, context edit and bounds without writing.

The selected project must already have `resources/artifacts/`,
`resources/archive/`, and, for retirement, `resources/archive/retired-decision-packets/`.
Under fresh exact authority, the owner stages immutable source snapshots in
`resources/archive/succession-sources/` and preserves original packet bytes under
`retired-decision-packets/<sha256>.html`. Original paths and hashes remain in
`<request-sha256>-succession.json`. A prepared receipt is not a completed transfer.

Only after source custody verifies does one existing record transaction replace
the live packet with a script-free documentary pointer, commit the succession
receipt, and add a bounded pointer to working context. The original page is
never silently erased or repaired in place. Its old URL now explains retirement;
archived bytes and actual historical sources remain retrievable. A retired exact
spec or equivalent generated payload cannot be filed again as a current packet
or new ruling. Build a genuinely new dated spec from unresolved obligations.

A failure before live commit leaves the original interface intact and may leave
exact prepared custody. Retry under the same authenticated owner after inspecting
it. An interrupted live commit blocks managed readers; use the existing
`context_edit.py recover-transaction` command with fresh authority. It will not
overwrite foreign changes. Completion is idempotent and revalidates the receipt;
no silent pruning, rollback, claim release or new authority occurs.

The record transaction is a journaled cooperative boundary. It does not make
several POSIX renames simultaneous for arbitrary external readers. Existing
harness/OS protection and coordination remain necessary.

## Historical proof and current destinations

Historical validation replays all referenced bytes from immutable custody and
rederives counts, IDs, answers and remaining obligations. Missing, corrupt,
aliased or unreferenced custody members refuse. The live documentary pointer and
working-context pointer must match. No generator provenance is added to legacy
bytes, and no actual past answer is synthesized.

Each current destination must still exist with its exact anchor. Changed bytes
with that anchor intact produce `changed-requires-review`, not historical data
loss, current readiness or completion. Missing/ambiguous destinations fail. The
context doctor reports these distinctions. Updating a working queue cannot
rewrite the accepted source inventory, and a receipt cannot hide lost obligations.

## Resource and integration contract

Bounds: 256 source items, 1,024 reference observations, 16 MiB total distinct
source bytes, 10 seconds for each source observation, 1 MiB request/receipt,
256 succession records and 4,096 artifact entries per project, a 30-second
whole-scan budget checked between bounded records, and the existing transaction's file, byte
and five-second lock bounds. These limit work; exhaustion is a refusal requiring
explicit owner reconciliation, never permission to drop members or raise caps.
References are bounded singly-linked regular files; symlinks, FIFOs and outside
paths are refused. Source identity, modes, bytes and paths are rechecked before
live effects. Each transaction target additionally binds the exact reviewed
whole-file SHA256 at transaction preflight, so a newly appended source cannot
turn the old full-file anchor into a substring match. Cooperating owners
serialize through the existing project lock.

The managed-runtime dependency list includes `record_succession.py` wherever
these consumers can load it. Missing helpers must fail closed. Publish/install
through the release owner only after integrated checks. Source fixtures do not
establish native client loading, approval authenticity, production migration or
successful provider operations.

## material-context.md

Verbatim from `skills/synthesis-context-lifecycle/references/material-context.md` at 1.22.0. Links inside point where they pointed then.

# Material context: capture, association and meaning

Use this protocol during ordinary project work when a source introduces or
changes a material fact, decision, constraint, commitment, risk or question.
Capture it before dependent work, compaction or handoff. A provisional capture
may remain pending; it must remain discoverable. A healthy structured checkpoint
does not prove that the user's instructions or their rationale survived.

The existing context editor and succession records own this operation. They use
the existing PM admission and record transaction. This protocol adds no authority
ledger, automatic transcript collection, background enrollment or execution right.
Prose-only projects use it without adopting CURRENT_STATE, a new project format
or autopilot. Historical coverage remains unknown unless actually observed.

## Select the source and preserve its limits

Resolve the registry-selected project and read its current plan and decisions.
Select the smallest sufficient original spans available within authorized scope.
Separate independent requests even when they arrived in one message. Preserve:

- facts and the difference between a report and an observed outcome;
- rationale, constraints and temporary conditions, including what ends an instruction;
- uncertainty, unavailable attachments and unresolved questions;
- who supplied the source, whether it was quoted or relayed, and what attribution is unknown;
- amendments and cancellations, their exact predecessors and surviving obligations.

For example, “use the detour until the inspection clears” cannot become an
unqualified instruction to use the detour. A concise paraphrase retaining that
condition and its rationale can be faithful. Matching words or hashes cannot
decide either question.

Do not turn quoted commands into current authority. Do not reconstruct missing
attachments or infer consent, completed work or a clean endpoint from silence.
Route private material to its authorized project and deletion unit before
capture. Keep credentials in their credential owner, never narrative custody.
The schema does not classify arbitrary text for secrets: the selecting agent
must apply the actual disclosure and routing rules. Public fixtures are synthetic.

The input inventory is explicit. A recursive Markdown scan, CURRENT_STATE file
hash list, generated cache, test output, or repository cleanliness is not a list
of user instructions. Generated evidence can be selected for its actual evidential
role; it cannot acquire principal authority from a provenance label.

## Versioned request in the existing editor

Use `context_edit.py review-succession --project P --request request.json` to
inspect, then `apply-succession` with the same request and the existing `--board`
and `--native-payload` arguments under fresh exact claims. The request has exactly:

| Field | Meaning |
| --- | --- |
| `schema`, `kind`, `phase` | `2`, `material-context`, and `capture` or `associate` |
| `batch` | `id`, exact `predecessor` reference or null, offset-qualified `captured_at`, `observation`, `excluded` |
| `inventory` | Project-relative `path`, SHA256, `format: json-rows`, exact `declared_count` |
| `items` | Empty for capture; one explicit disposition for each selected input for association |
| `review` | Exact meaning-review artifact reference or null |
| `context_anchor`, `context_max_lines` | Unique line-start insertion anchor and positive limit no greater than 150 |

References contain `path`, `sha256` and, when a span is required, a nonempty
unique exact `anchor`. A selected binary attachment can use a whole-file source
reference without an invented text anchor; exact custody does not interpret it.
Links, symlinks and foreign paths do not widen scope.
The source inventory is `{"rows": [...]}`. Each row contains exactly:

- `id`; `kind`: fact, decision, constraint, commitment, risk, question, amendment,
  cancellation or nonmaterial;
- `source`: exact span reference or null; `availability`: retained or unavailable;
- `provenance`: `origin` (primary, quoted, relayed, unknown), `attribution`,
  `event_time` (reported text or null), `authority: source-claim-not-current-authority`;
- `required_aspects`: a unique subset of facts, rationale, condition, uncertainty;
  and `reason`: selection, limitation or nonmaterial rationale.

The batch observation contains `scope: declared-inputs`, `start`, `end` and
`gaps`. Unknown locators are null; gaps remain stated. `excluded` lists separate
`{id, reason}` objects and cannot overlap selected IDs. This records the observed
frontier, not a claim that the whole session was captured. Required aspects are
selected judgments; an omitted aspect in the inventory is not automatically found.

Each association item contains exactly `id`, `status`, `destination`, `aspects`,
`not_applicable`, `owner`, `next_action`, `supersedes`, `reason`. Status is open,
amended, unknown, recorded, cancelled, retired or nonmaterial. Destination and
next action are span references or null. `aspects` maps each retained aspect to
its actual destination span. `not_applicable` supplies reasons for other aspects;
it cannot waive a required condition. Active items require a next action and an
owner (use explicit UNKNOWN plus a reason when needed). Nonmaterial items cannot
erase a selected material item or manufacture a new obligation.

Capture retains the input denominator with empty items and null review. It
reports CAPTURED_PENDING. Association names the exact capture as predecessor and
retains its batch identity and inventory; changing the input denominator needs
an explicit new record. An amendment or cancellation names the exact prior
record and item in `supersedes: {record: REFERENCE, id: ID}`. It preserves prior
bytes and must not close unknown work by absence. Conflicting successors remain
unresolved. Retired records remain documentary; format refresh will not recreate
an exact retained terminal span as a new candidate. A changed source needs review.

## Review meaning against actual retained spans

A meaning-review artifact has `schema: 1`, `kind: material-meaning-review`, exact
`inventory_sha256`, `dispositions_sha256` (SHA256 of the owner's canonical encoded
request items), `reviewer`, `plan`, `earlier_decisions`, `answers`, `limitations`.
Reviewer, plan and earlier decisions are retained references. Each answer has
`id`, `question`, `source_refs`, `record_refs`, `assessment`, `reason`. Citations
must belong to that selected input and its destinations. Assessment is faithful,
deficient or uncertain. A PASS flag cannot replace cited reasoning.

Ask whether the current record reconstructs the report, rationale, constraints,
temporary conditions, uncertainty, requested actions and subsequent changes.
Read the cited source, plan and earlier decisions. Review concision on meaning;
do not reject a faithful paraphrase for style. Bind review to the actual input
and destination generation, and repeat it when those sources change.

Deterministic validation establishes structure and custody only. A caller's
faithful assessment yields REVIEW_EVIDENCE_PRESENT_UNVERIFIED, never semantic
acceptance. False confidence in a supplied review cannot make a source true.
Independent blind/model calibration and actual endpoint observations require
genuine separately retained runs. Their absence stays pending or UNKNOWN.

## Recovery and reporting

Application first preserves immutable source custody and a discoverable prepared
record. One existing record transaction then commits the receipt and CONTEXT
pointer. Source replacements and claim changes are fenced again at commit.
An interrupted live transaction blocks managed consumers until the existing
`recover-transaction` owner reconciles it. A prepared pre-transaction record
requires inspecting custody and an exact retry under current authority. A changed
request or changed input is not an exact retry. Never delete an interrupted prefix.

Checkpoint and doctor expose the shared `record_succession.material_context`
projection, including for ordinary projects before structured NOT_APPLICABLE.
It separates input coverage, record integrity, association reachability, semantic
review, current authority and endpoint recovery. It also reports whole-session
and historical coverage, examined/skipped counts, bounded costs and limitations.
VERIFIED_FOR_DECLARED_INPUTS is only a declared-denominator result. UNKNOWN,
CAPTURED_PENDING, SOURCE_UNAVAILABLE, PRESENT_BUT_UNREACHABLE,
CHANGED_REQUIRES_REVIEW and INCOMPLETE must remain visible.

Restore a missing forward link from CONTEXT or REFERENCE to retained associations
without rewriting the incident or replaying an ambiguous effect. Read referenced
sources to reconstruct meaning. The optional autopilot capsule carries reference
and status projections; it reuses the same record owner and existing quality
rubric. It never copies a second narrative archive or clears an authority fence.

Scans are bounded to 256 records/items, 1,024 reference observations, 16 MiB
charged source bytes, 4,096 artifact entries and 30 seconds aggregate observation
(10 seconds per reader). Navigation follows project-relative Markdown links
from CONTEXT/REFERENCE to depth four with bounded entries. Exhaustion retains an
INCOMPLETE prefix and its limit, never evidence of absence. Measured bytes,
references and elapsed time are separate from unknown model cost.


## Failed observations and current work admission

An observed empty legacy inventory keeps material coverage unknown without
enrolling that project or inventing a material obligation. A refused, malformed
or incomplete observation keeps reconciliation pending even when no record could
be appended. Consumers validate the record and request objects before kind
dispatch. The existing prepared transaction envelope remains a pending capture;
its exact request hash is checked without requiring committed derived fields.

A stored clear recovery is a historical journal observation. The existing
work/effect admission constraint observes current material alongside native,
instruction and artifact currentness. Changed, incomplete or unreachable material
requires reconciliation before subsequent work. Unchanged current material still
permits legitimate subsequent effects through their existing owners.

Generated resume-state refresh uses terminal dispositions only when current
material applicability is complete and unambiguous. Conflicting or changed
retirement evidence retains the explicit source as an unverified candidate;
healthy current retirement and cancellation do not recreate that candidate.
These checks establish bounded structure and currentness, never independent
semantic correctness, principal approval or an external effect outcome.

## autopilot-recovery.md

Verbatim from `skills/synthesis-context-lifecycle/references/autopilot-recovery.md` at 1.22.0. Links inside point where they pointed then.

# Recovery capsules and cold resumption

The authoritative run journal owns execution history. Context lifecycle owns
retention and reconstruction; PM owns project selection and current authority.
Neither a capsule nor a transcript grants a new claim, changes the outcome
contract, replays an external effect, or proves a future wake.

## Produce and retain

The ordinary autopilot `checkpoint` operation embeds a bounded capsule in its
existing journal event. It references the exact preceding event and its state
digest, current contract and profile, every contract/profile revision, acceptance
criteria, authorization references, graph, waits, effects, child records, resource
owner state, registered artifacts, native handles and current input identities.
The controller returns `coverage.recovery_capsule` with the event reference,
JSON pointer, digest, revision and whether it is the current head.

Opaque extension references retain decision and resource owners without copying
their authority or guessing future schemas. Null measured usage stays unknown.
The capsule contains references, not a second copy of all project source or a
second execution database. Earlier capsules remain in their original events.
The reference projection has a 256 KiB limit; exceeding it preserves the journal
and the last capsule and returns an actionable error, never a truncated PASS.

Register useful intermediate child outputs as durable artifacts when they exist.
The capsule retains these artifacts when they fall within the child's declared
output roots, even before a final child return. Unregistered files, unsaved
reasoning and a model's hidden state are not invented as recovered work. Retain
declared output and scratch roots for inspection under the existing path owner.

## Consume through existing owners

Material inputs remain in the [ordinary succession owner](material-context.md).
Capsules carry its exact record references and separate coverage axes, without
copying narrative. Recovery re-observes changed, pending or unreachable material
and reports reconciliation; unknown historical scope is not automatic enrollment
or a semantic PASS. Actual meaning acceptance uses the existing project rubric.

1. Resolve the project through the PM registry and full causal project resolver
   before reading its execution journal. The controller uses explicit repo-guard,
   checkpoint receipt and coordination roots and does not fetch or refresh the
   board. A newer conflicting checkout or unattributed local changes must be
   reconciled through PM; a capsule cannot override that result.
2. Obtain fresh native-to-seat identity and the exact current PM claim. Recovery
   uses the existing journal lock and expected-revision CAS. A released claim,
   foreign native actor or copied event cannot acquire authority from the capsule.
3. Invoke the ordinary controller `recover`. `capsule_ref`, when supplied, must
   name this run's authentic checkpoint event at the current head. Old capsules,
   another run, copied JSON, changed instructions and changed registered artifact
   identities are refused. Omitting it still recovers from the verified journal;
   it never imports an arbitrary capsule as truth.
4. Reconcile current native sources, artifacts, unresolved effects and running
   children. Unknown action outcomes require actual action-owner readback. Do
   not issue the action again to determine whether it happened. Retain partial
   child output and establish actual worker disposition before reassignment.
5. The existing journal rebuilds current JSON, summary and plan projections.
   Interrupted committed request prefixes are retried with the same request body
   and ID. Partial or malformed committed events remain visible and block
   recovery; projections never replace their authority.
6. Read the returned `coverage.recovery` and `next` obligations. `RECONCILE`
   fences new tasks, delegation, new effects and completion while permitting
   cancellation, artifact repair and the necessary owner readbacks. `READY`
   means current recovery admission, not that all outcome criteria passed.

`coverage.recovery` names its observed revision and whether that admission is
still the current journal head. It separates the recorded admission from fresh
owner-bound external readback, including on an idempotent request replay. A new
native cancellation removes readiness without appending a fabricated event.
Actual work admission also rechecks native, instruction and artifact currentness;
a cached clear report never establishes future absence. Newly admitted effects
and children remain governed by their existing owners and do not invalidate the
earlier recovery merely because ordinary work has begun.

## Changed instructions and ownership

A diagnostic checkpoint cannot silently adopt changed controlling instructions.
An unrelated contract edit cannot clear that obligation either. The current
authorized agent must read and reconcile the actual instructions with the
existing contract, then use controller `record` with kind
`recovery_instructions`, the exact current `plan_digest`, `contract_digest` and
an explanation. This acknowledgement records the current owner's interpretation;
it grants no approval, cannot expand action authority, and cannot override a
native cancellation or missing native source. Contract changes remain subject to
the existing contract owner's evidence and authorization rules. A stale digest,
changed owner/claim or further instruction edit invalidates the acknowledgement.
Restoring the actual original instructions also resolves their drift.

The existing two-phase `owner.transfer.prepare` / `owner.transfer.accept`
protocol is the only implemented ownership-transfer path. It requires an exact
target, an unexpired prepared basis, official PM release/claim and fresh target
native admission. A dead process is not a grant to take over its claim. After a
legitimate transfer, native source generations still require explicit bounded
reconciliation; earlier producer history stays retained and its negative
coverage is not upgraded to known absence.

## Declared survival boundary

A new local Python interpreter recovering the real PM/journal proves cold
interpreter reconstruction. It does not prove application exit, logout, reboot,
network outage, computer power-off or another machine's operation. The capsule
marks these boundaries UNKNOWN unless their existing native owner supplies
separate actual evidence. Local absolute native/owner locators are never
silently rewritten into another machine's identity.

Optional Console supervision is described in
[the autopilot supervision contract](../../synthesis-autopilot/references/supervision.md).
Its source queue does not itself supply native launch authority or satisfy an
independent survival/backstop requirement.

## record-transactions.md

Verbatim from `skills/synthesis-context-lifecycle/references/record-transactions.md` at 1.22.0. Links inside point where they pointed then.

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

A transaction covers files beneath one project on one filesystem. Registry
edits outside that project and deletion remain separate owner operations.
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
