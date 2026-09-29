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
