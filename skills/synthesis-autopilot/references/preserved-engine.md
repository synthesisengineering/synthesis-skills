# Preserved: the 3.x run engine

Verbatim text of synthesis-autopilot 3.6.7 reference files that v5 does not carry: the run journal, its nine-operation controller, successor transactions, owner resume, the Console supervision and operator views, and owner-overhead measurement. It is kept under ruling D8 so nothing is lost; the reason for each file is in [preserved.md](preserved.md), and where any kept rule went is in [coverage-map.md](coverage-map.md). Nothing here is current procedure. Links inside the verbatim text point where they pointed in 3.6.7 and may not resolve from this file.

## Contents

- [run-contracts.md](#run-contracts-and-command-interface): Run contracts and command interface (252 lines)
- [controller.md](#admitted-execution-controller): Admitted execution controller (153 lines)
- [journal-storage.md](#bounded-journal-storage): Bounded journal storage (62 lines)
- [successor-transactions.md](#bounded-successor-transactions): Bounded successor transactions (138 lines)
- [owner-resume.md](#same-native-ownership-after-a-released-seat): Same-native ownership after a released seat (206 lines)
- [operator-experience.md](#operator-status-and-handoff): Operator status and handoff (63 lines)
- [supervision.md](#optional-supervision-through-existing-owners): Optional supervision through existing owners (178 lines)
- [efficiency-measurement.md](#measuring-local-owner-overhead): Measuring local owner overhead (46 lines)

<!-- verbatim: skills/synthesis-autopilot/references/run-contracts.md at 3.6.7 -->

# Run contracts and command interface

For ordinary delegated work, use the nine-operation
[execution controller](controller.md). It prepares inputs and invokes the same
owners described here, retaining exact request prefixes across interruption.
The lower-level interface remains useful for specialized observations, effects
and explicit recovery; it does not bypass current workflow constraints.

For a new interval after a terminal run, use the controller’s
[`successor` operation](successor-transactions.md). It retains the complete
verified ledger and obligations with one pre/post admission pair, without
rewriting the predecessor or separately re-registering each item.

Large retained histories use the same owner through [bounded journal storage](journal-storage.md).
Storage representation does not change command, custody or approval semantics.

The agent prepares these inputs after registry-first project recovery and exact
PM ownership. A user asks for the outcome; JSON authoring is the agent's work.
Use the installed verified skill root. Examples below use the shell variables
`AUTOPILOT`, `PROJECT`, `PLAN`, and `ACTOR` for already verified absolute paths.
They do not create authority, claim an arbitrary directory, or discover a
project by scanning prose.

## Inputs

The native actor is `{"board":"/absolute/coordination/active-sessions.md",
"native_payload":{...}}`. Preserve the real event's session identity, transcript
path, working directory and event name. The PM adapter independently validates
the native transcript and the seat's exact claim. A display name, seat UUID,
environment variable or caller-written receipt alone is insufficient.

The plan must be a current readable file inside the registered project and
covered by the authenticated claim. The run directory must also be claimed.
Source work in another repository requires the owning PM admission for those
paths and its actual worktree/branch; project membership is not ownership.

A completion contract uses schema version 1. This small example accepts durable
bytes only. For executable behavior, use `consumer-check` and its evidence ID;
for editorial quality, use a calibrated native review and the domain workflow.

```json
{
  "schema_version": 1,
  "scope": ["Produce the requested local report"],
  "exclusions": ["Publication"],
  "authority_refs": [],
  "outcomes": [{"id":"report", "criteria":["report-present"]}],
  "criteria": [{
    "id":"report-present", "description":"The report is retained in the project",
    "required":true, "method":"artifact", "artifact_ids":["report"], "evidence_ids":[]
  }]
}
```

Resolve an effective profile with `run_profile.py resolve --help`. The source
preference schema is 2; the resolved run profile is schema 1. Map each profile
item to relevant `criterion_ids`, or supply a fresh typed `profile` observation
that establishes its disposition. Mapping every item to one existence check
would not establish the user's requested result. Do not remove inconvenient
profile obligations to make closure pass.

```sh
python3 "$AUTOPILOT/scripts/autopilot.py" create \
  --project "$PROJECT" --project-id "$PROJECT_ID" --plan "$PLAN" \
  --contract "$PROJECT/resources/contract.json" \
  --profile "$PROJECT/resources/effective-profile.json" \
  --actor "$ACTOR" --command-id create-initial
```

Retain the returned `run_id` and `revision`. Every mutation names both an
expected revision and a command ID. Repeating the same command ID and payload
returns its existing result. Reusing an ID for changed input or a stale revision
is rejected. Read current state before deciding whether a failed call persisted;
do not invent a new ID to repeat an ambiguous external action.

## Commands and observations

```sh
python3 "$AUTOPILOT/scripts/autopilot.py" command \
  --project "$PROJECT" --run-id "$RUN_ID" --actor "$ACTOR" \
  --expected-revision "$REVISION" --command-id register-report \
  --name artifact.register --payload "$PROJECT/resources/register-report.json"
```

The registration payload is:
`{"id":"report","path":"resources/report.md","role":"output",
"required":true,"retention":"durable"}`. Inputs and evidence use the same
shape with `role: input` or `role: evidence`. Paths must stay inside the durable
project. Missing files, symlinks, temporary dependencies, the controlling plan
and the run's own projections cannot certify completion. Registration hashes
the actual bytes; changing them invalidates acceptance.

| Command | Required intent |
|---|---|
| `transition` | Explicit allowed `status`; entering verification does not verify anything |
| `progress` | A `summary`; recorded as narration, not measured progress |
| `wait.add` | Unique `id`, `kind` (`user` or `external`) and concrete `reason` |
| `wait.resolve` | The wait `id` and a trusted wait-resolution `evidence` reference |
| `artifact.register` | Current durable file with typed role and requirement |
| `evidence.record` | `id`, `kind`, `artifact_id` for a current typed receipt |
| `criterion.evidence.bind` | Select a fresh immutable quality/consumer attempt for an already declared criterion slot, with exact prior ID/digest |
| `verify` | Explicit `criteria` while verifying; optional `profile_evidence` |
| `close` | `status`: `completed`, `incomplete` or `cancelled`; honest `reason` for noncompletion |
| `contract.amend` / `profile.amend` | Versioned replacement; weakening requires authenticated owning evidence |
| `effect.prepare` / `effect.observe` / `effect.reconcile` | Intention, unknown outcome, then target-bound read-back; no external write is executed |
| `continuation.register` / `continuation.wake` | Observed registration and each distinct actual native wake; registration also names the admitted `horizon` |
| `continuation.renew` | A `receipt` from the `continuation-renewal` observer; extend the same live pair without resetting wake history or deadline |
| `continuation.cancel` / `continuation.cancel-confirm` | Cancellation intent, then native readback of the exact pair's removal |
| `owner.transfer.prepare` / `owner.transfer.accept` / `owner.transfer.revoke` | Bounded same-board intent, exclusive PM claim transition, then exact native target acceptance |
| `owner.resume` | Same native conversation, terminal prior seat, exclusive replacement seat and current direct-user evidence; retains obligations and enters recovery |

For a released seat replaced within the same native conversation, use the
[same-native owner renewal protocol](owner-resume.md). It does not substitute
for transferring work to a different native conversation.

Handoff uses two authenticated phases because PM correctly prohibits both seats
holding overlapping mutable claims. While it still owns the run, the predecessor
calls `owner.transfer.prepare` with `id`, `target` (`session_uuid` and `native_ref`
from an active seat on the same board), and a future `expires_at` no more than one
hour away. The target can initially hold a disjoint preparation area with context
role `none`. Preparation records intent; it does not authenticate an incoming
event as the target or transfer any claim.

The predecessor then releases or narrows its own PM claim. The target obtains
the exact run, plan and plan-lock claims through PM and calls
`owner.transfer.accept` with the prepared `id`, expected revision and its own
native actor. Acceptance checks the same board, exact target seat/native identity,
current exclusive admission, unchanged prepared revision, all durable obligations,
human plan digest and expiry, then checks admission again immediately before the
event commit. It sets `recovering`; existing waits, effects, criteria and workflow
remain obligations, and earlier evidence gains no trust. The old one-step
`owner.transfer` command is unavailable.

Before releasing its claim, the predecessor can call `owner.transfer.revoke`
with the matching `id`. Revocation also requires fresh owner admission. Any run
mutation after preparation invalidates acceptance, as does an edited human plan,
expiry or revocation. Revoke and prepare a new intent after such changes. A
released predecessor must reclaim through PM before revoking; an expired intent
does not confer takeover permission. Exact command retries remain idempotent;
consumed intents cannot be accepted under a new command ID. Possession of a
journal or intent never substitutes for PM/native authority.

Use `observe`, with the same revision/ID arguments, for bundled observers. Its
payload is only `{"check_id":"registered-spec-id"}`. The observer reads or
executes the declared check and writes an event itself. It does not accept a
caller-supplied PASS. Manual receipt registration establishes format and hashes;
the receipt's registered source and acceptance predicate must still validate.

For lease renewal, the registered specification is
`{"schema_version":1,"kind":"continuation-renewal","arguments":{"readback_call_id":"native-list-call","previous_lease_receipt":"current-lease-receipt"}}`.
Invoke `observe --name continuation-renewal` with its `check_id`, then
`command --name continuation.renew` with `{"receipt":"renewal-observation-id"}`.
Both use the normal actor, expected revision and distinct command IDs. Fresh
PM admission and actual same-pair native readback remain required; expiry is
bounded by the unchanged five-minute maximum and the capability, original
registration and previous lease receipt expiries. Renewal cannot replace fresh
observed recovery and re-registration before those evidence boundaries. See
[native clients and recovery](clients-and-recovery.md) for wake ordering.

## Evidence and recovery

Each evidence or observation ID identifies one immutable attempt. Replay its
original command ID to recover the result; a new attempt needs a new ID and its
own resource accounting. It cannot overwrite an earlier failed observation.
For `quality_observation` and `consumer-check`, select the new attempt without
changing the acceptance contract:

```json
{"criterion_id":"accept","slot":"review","receipt_id":"review-2",
 "expected_prior_receipt_id":"review","expected_prior_digest":"<exact prior digest>"}
```

The slot must already be in that criterion's `evidence_ids`. An initially empty
slot uses explicit null prior ID and digest. Selection requires fresh authentic
evidence for the current criterion artifact and records the selected ID/digest.
It grants no authority, supplies no passing verdict and cannot resolve a failed
workflow grade. Contract or profile amendments clear these selections. Follow
the bounded repair sequence in [workflow and evidence](workflow-and-evidence.md)
before trying to complete work that failed quality review.

Receipts bind run, contract/profile digests, current artifact inputs, producer,
observation time and expiry. Verification additionally binds the plan and
verifier version. A genuine observation of a failed check is not a passing
criterion. Unknown sources, self-asserted independence, stale inputs and expired
receipts fail acceptance. New verification is needed after a material change.

The authoritative store is `resources/autopilot-runs/<run-id>/events/` under
the project. `current.json`, `summary.md` and the plan's managed cycle block
are readable projections. A persisted event survives a crash before projection.
`rebuild` regenerates projections under fresh ownership; it does not rewrite
the journal or mark work complete. Preserve events when moving the project.

`status --actor ...` checks the current criterion evidence. Without an actor,
status labels its information recorded-only/UNKNOWN. `run_profile.py verify`
reads the engine's current completion report; it does not mint an attestation.
The command interface's tests exercise creation, status, cancellation, forged
closure refusal and bounded Stop using real PM fixtures.

## Close and import

Register the actual outputs, collect trusted evidence, enter `verifying`, and
verify all required criteria. Then close. The engine also checks current
profiles, unfinished waits/effects, child audits, resource accounting and domain
quality. A failed required check leaves the run incomplete. Explicit incomplete
closure preserves the work and the reason; it cannot be presented as success.

`import --legacy ...` consumes an explicitly selected, owned old engagement.
It preserves the original bytes and historical profile, records provenance,
and enters recovery. Old `goals_met` and old verification receipts do not
become current acceptance. The original remains intact. A changed original
must be reviewed; an old import digest cannot conceal its new obligations.
See [clients and recovery](clients-and-recovery.md) for the legacy owner index.

### Required citations and durable closure

A controlling plan or a required Markdown packet can declare retained evidence
with `Required acceptance evidence: [report](resources/report.md)` or a heading
named `Required acceptance evidence` followed by its citation list. Markdown
strong markers (`**` or `__`) around the label and optional closing heading
hashes preserve the same obligation. The same
contract accepts `Required recovery inputs`, `Required artifacts`, and
`Required scripts`. A declaration is an evidence obligation, never an approval
or permission grant. Ordinary links, historical discussion outside those
sections, fenced examples, and HTML comments do not create obligations.

Completed closure and the completion report check these declarations against
the existing artifact register. Every cited target must be a current,
digest-verified durable project artifact. Markdown packets recursively apply
the same declaration contract. An actual retained bundle or manifest is cited
at its durable registered path; its existence does not validate a different
scratch-only path or certify the bundle's semantic completeness. Keep the
existing domain verification for those contents.

Supported citations are inline Markdown links, reference links with explicit
definitions, absolute or document-relative paths, and local `file:` URLs.
Spaces may be percent-encoded or enclosed in angle brackets. Missing files,
changed bytes, symlinks, unsupported declarations, unresolved references,
remote-only URLs, and targets outside the project yield `UNKNOWN` and refuse
completed closure. Conflicting reference definitions are checked only when a
required citation uses them; unrelated historical definitions create no
obligation. Incomplete and cancelled closure remain available and keep
unfinished obligations honest. Promote required scratch evidence into the
project, register its bytes, and update the controlling citation before
verifying completion.

One observation reads at most 64 plan/packet documents, 4 MiB of their total
text, and 1,024 explicit citations. These are traversal and parser limits, not
provider or user spending limits. Repeated packet references are visited once;
cycles cannot create an unbounded traversal. Exceeding a limit refuses
completion without advancing the run. Large retained evidence files and
bundles use their ordinary artifact verification; these limits apply to the
Markdown documents that declare their relationships.

<!-- verbatim: skills/synthesis-autopilot/references/controller.md at 3.6.7 -->

# Admitted execution controller

The normal agent interface has nine operations over the existing PM admission,
run journal, workflow, evidence and completion owners. It does not create another
scheduler, private state store, tool launcher or acceptance authority. The agent
interprets the user's intent and produces the request; users need not author JSON.

## Invocation and identities

Invoke `scripts/autopilot.py <operation> --project <absolute-project-path>
--request <request-file-or-dash> --actor <native-actor-file>`. The actor contains
the actual native event and coordination board. Native source mode is the default;
`--source-mode synthetic` labels a fixture and cannot qualify native execution.

Every request is schema 1 with `request_id`, `operation`, `project_id` and `input`.
After `start` or `successor`, include the returned `run_id` and the current `expected_revision`.
The complete request is bound to its stable ID. A changed body cannot reuse an
existing ID, even after partial progress. The existing journal commits each step
with that binding; there is no separate request database. Inspect committed
events before recovering a failed invocation. Exact retries reuse committed
prefixes and cannot replay an external effect through a new label.

JSON inputs reject unknown fields, duplicate keys, nonfinite values, excessive
depth and unsafe paths. The request limit is 256 KiB. Managed input bytes are
content addressed under the admitted run home; unreferenced staging files remain
recovery material rather than evidence. Responses are bounded and include an
exact journal reference when further pagination is required.

## Operations

| Operation | Purpose and required interpretation |
| --- | --- |
| `start` | Supply `plan_ref`, `outcome_contract`, task `dimensions`, and `resource_envelope` containing `limits` and an actual authorized `deadline`. Optional preference references and task graph use their existing owner schemas. Resolve the profile, create the run, configure workflow and enroll the current native source. |
| `successor` | Derive a bounded continuation from an exact terminal predecessor through one atomic journal append. Supply its exact head/deadline, a new authorized deadline and a digest-bound scoped authorization reference. Limits, costs, history and obligations come from the owner, never replacement caller totals. Read [successor transactions](successor-transactions.md). |
| `next` | Inspect ready work with `mode: inspect`, or admit a selected task with `mode: start`. Dependency, current authority, resources, history and native instructions constrain admission. A readiness result does not itself execute a task. |
| `record` | Register a durable artifact, invoke a supported observer, ingest a bounded native page, record a task attempt, bind a real profile obligation, or register/revise/resolve a decisive uncertainty. The specific kind has a closed input schema. Caller PASS fields are never evidence. |
| `checkpoint` | Preserve current progress and, when requested and applicable, obtain the existing PM execution-basis observation. This observation does not certify a normal whole-project clean checkpoint. |
| `explain` | Inspect contract, profile, coverage, ready work and unresolved obligations. Without a native actor, this is a historical read-only snapshot. Current ownership and acceptance require authenticated readback. |
| `cancel` | Record the user's cancellation while retaining partial work, effects and child obligations. A requested child or schedule cancellation still requires observed disposition. |
| `recover` | Run the full causal PM resolver, re-admit the actual owner, reconcile original interrupted native-worker custody without replay, recover a committed request prefix and reconcile native source generations explicitly. An optional `capsule_ref` must name the current authentic checkpoint event. Rotation never silently resets a cursor. |
| `finish` | Invoke actual outcome, quality, profile and completion owners. A completed tombstone is historical state; stale current artifacts, expired evidence or new native invalidations prevent a current completed result. |

The response contains `status`, `run_id`, `revision`, `committed_event_ids`,
`next`, `coverage` and `diagnostics`. Read those fields rather than equating
process exit zero with completion. A missing capability is UNKNOWN, not PASS.

## Domain evidence and decisive observations

`coverage.domain_quality` reports all selected domain families, their existing
method owners and required dimensions. A method's availability is not a
qualification claim. Rich reviews combine task-specific semantic calibration
with actual consumer or readback requirements; `finish` preserves that combined
review instead of replacing it with a generic process result. Read
[domain quality](domain-quality.md) for the six family contracts.

The `record` kinds `uncertainty`, `uncertainty_observe` and
`uncertainty_revise` use the thinking framework's
[decisive-uncertainty contract](../../synthesis-thinking-framework/references/decisive-uncertainty.md).
`coverage.decision_uncertainty` reports current open/resolved questions, exact
source evidence and affected criteria. `next` suggests the declared cheapest
credible observations before dependent task work. The same current-evidence
guard applies to direct task admission, verification and completed closure.
Independent criteria, cancellation and incomplete closure remain available.
A registered question does not grant action authority or reset retry budgets.

Checkpoints retain a journal-owned recovery capsule; interrupted work follows
[the cold-resume protocol](../../synthesis-context-lifecycle/references/autopilot-recovery.md).
`record` also routes explicit `recovery_instructions` acknowledgement and the
closed [optional supervision actions](supervision.md). These operations retain
the existing authority and action-owner boundaries.

## Native evidence and currentness

Enrollment binds the exact admitted producer and begins at a complete native
record frontier. Earlier history is explicitly UNKNOWN. A source label or an
agent's claimed task ID cannot establish parentage: child evidence needs its
actual admitted dispatch and unique native parent/root/task identity.

Ingestion commits normalized events, witnesses, cursor and projection together
under the existing compare-and-swap journal. Consumption reopens current source
bytes. Positive call/result evidence and complete negative coverage are different
claims: verifying a successful tool result does not prove no later cancellation
occurred. The same decoder checks native sequence gaps during ingestion and
interval readback. Unsupported records, missing intervals, changed producer
bytes, rotation and partial tails preserve explicit uncertainty.

For sustained runs, current invalidation checks combine the journal's retained
invalidation index with current positive source witnesses and a bounded unread
tail. Normal bounded ingestion advances through benign history without requiring
a human approval for each page. A clear result means no unresolved journaled
invalidation and no invalidation in that current tail; historical negative
coverage remains UNKNOWN. This assumes a cooperating native append-only
producer. It does not prove that every old benign byte escaped a same-size edit
by an arbitrary filesystem writer. Recognized cancellations, unread gaps and
unreconciled source generations cannot be hidden by that scope limit.

Fresh root instruction and cancellation checks constrain work admission, Stop
feedback and completion. Child cancellation has its own admitted source scope.
Source reconciliation cannot erase a known cancellation merely by selecting a
later byte offset. Any resumed instruction must retain its exact native evidence
and owner-bound reconciliation; unknown historical coverage is never relabeled
as a complete transcript.

Native dialect translation covers declared Codex, Claude and Muse record shapes.
Parsing a dialect does not qualify every client transport or every outcome type.
The implemented child locator and native process outcome interpreter name their
specific supported surfaces. A missing host capability remains visible while
independent authorized work continues.

## Adaptive defaults and persistence

Canonical profile obligations have owner-derived semantics. A direct task with
no actual material choice can make decision capture inapplicable. Lessons are
required when a reusable finding or an explicit selection calls for them; an
unselected optional capture does not force filler prose. A custom enabled item
needs a real criterion mapping. Caller text and an unrelated artifact-existence
check cannot discharge the standing outcome and safety invariants.

The workflow retains failed attempts, strategy identity, evidence generations,
re-arm decisions and resource accounting. Productive work continues beyond the
old numeric observation and grading ceilings. Repeated unchanged transient
failures, permanent failures, unavailable authority and ambiguous effects remain
different conditions. New labels and reconfiguration cannot reset their history.
An actual hard resource limit is checked again when admitting the next task.
Unknown provider cost remains unknown and does not refund its reservation.

Stop first screens unresolved runs, then reserves one eligible correction in the
journal. The verified native launcher consumes that reservation at emission.
Concurrent processes, a fresh repeat bit or replayed proof cannot emit it twice.
Terminal infrastructure diagnostics end feedback explicitly unresolved, retaining
pre-mutation protection and recovery evidence.

## Project closure

An adopted PM project presents a circularity if its current clean-checkpoint
receipt must cover the journal write that consumes that receipt. The execution
basis avoids this by naming its narrower scope: it binds current project facts,
plan, inputs, sources and other runs, while accounting for only the selected
run's verified derived journal projections.

After the terminal event, the controller invokes the normal PM checkpoint owner
outside that journal. An interrupted postamble remains pending. Its exact retry
does only the remaining checkpoint work; it does not repeat terminal effects.
The resulting clean-checkpoint successor is bound to the terminal head and
unchanged operational meaning. Changed plan, project facts or unrelated bytes
still invalidate it. Current completion rechecks both the outcome and applicable
closure evidence before reporting success.

Owner-prepared native continuation uses the same `record` operation with
`kind: launch_prepare` or `kind: launch_cancel`; their exact fields and the
stdin-only service consumer are defined in [supervision](supervision.md).
Only an actual current native owner can prepare a grant. A transport observation
is never a task acceptance receipt, and a service cannot supply a native actor.

<!-- verbatim: skills/synthesis-autopilot/references/journal-storage.md at 3.6.7 -->

# Bounded journal storage

The run journal owns durable state, command replay, native observation custody
and the event chain. Large snapshots use content-addressed blocks under the
same run directory. The storage codec introduces no actor, scheduling service,
claim, model budget or permission authority.

A snapshot above 1 MiB is represented by a descriptor containing the root block
digest, complete logical JSON digest and exact logical byte count. Blocks carry
JSON fragments and references. Dictionary partitions use hashes of their keys,
so unrelated changes can reuse retained fragments. Lists and strings are split
in order. No observation, cursor, event index, failed result or prior event is
removed during encoding. The event's existing logical digest remains unchanged.

The admitted writer holds the existing run lock and checks the complete event
and projection block set before committing. It installs immutable blocks,
flushes each file and the containing directory, then commits the event. Derived
projections follow. A crash before event commit can leave unreferenced blocks;
they confer no state and still count against capacity. A crash after commit is
recovered through ordinary same-command replay or projection rebuild. It does
not replay an external effect.

Readers authenticate every referenced block, reject links and nonregular files,
check expanded size and reference/depth bounds, and recheck the logical content
digest. Missing or changed blocks make the journal unverifiable. Readers retain
support for existing inline historical events because those original bytes and
digests remain the historical authority; they are never rewritten as migration.

| Bound | Value | Purpose |
|---|---:|---|
| Inline snapshot | 1 MiB | Switch storage representation before the former file-size boundary |
| Leaf JSON | 64 KiB | Bound individual decoded fragments |
| Physical block | 128 KiB | Allow framing while bounding each file read |
| Logical snapshot | 64 MiB | Bound an admitted operation's total retained state |
| Native projection share | 32 MiB | Reserve room for the index, cursor, latest batch and other owners |
| References in one read | 16,384 | Bound malicious expansion and traversal |
| Codec depth | 64 | Bound recursive representation processing |
| Store bytes per run | 512 MiB | Bound cumulative immutable retention, including orphans |
| Store entries per run | 32,768 | Bound directory work and inode use |

The existing 10,000 journal-event and 10,000 native-index limits remain. Reaching
any bound refuses the next append with the previous committed state and cursor
intact. The owner must plan an explicitly linked bounded continuation; deleting
history or manufacturing a successful observation cannot satisfy that refusal.

Native event consumption retrieves the exact historical batch through the
block tree and compares its digest to the already authenticated current event
index. This avoids reading a complete growing snapshot for every selected old
observation. Every physical read counts against the existing 8 MiB consumption
budget. That component lookup proves only the selected batch; full-chain
validation remains with the run owner. The operator view keeps its existing
two-second verification budget and never turns a timeout into a partial PASS.

Prepared native launch attribution derives both descriptor and block bytes from
the committed owner state. The ordinary repository attribution owner verifies
those bytes; a block-shaped filename grants no ownership of unrelated edits.

After installing a release with this codec, recover the existing run through
its normal authenticated owner. Read the last committed revision, preserve the
failed append evidence, and continue observation from the retained cursor. No
manual migration, snapshot deletion, cursor edit or native permission change
is needed.

<!-- verbatim: skills/synthesis-autopilot/references/successor-transactions.md at 3.6.7 -->

# Bounded successor transactions

Use `autopilot.py successor` through the ordinary controller when a terminal
interval needs an explicitly authorized continuation. The agent prepares the
request after project recovery and current native PM admission. A saved
reference or an automation wake alone is not permission to continue work.

The operation derives one initial snapshot inside the existing run journal.
It keeps the predecessor as an immutable digest-bound reference and copies its
complete current obligations. It neither introduces a second budget store nor
accepts a batch of arbitrary mutations. This avoids an admission round trip for
each reservation, settlement and artifact while preserving a fresh authority
check before and after the complete derivation.

## Request and ownership

The schema-1 controller request uses `operation: successor`, `request_id`,
`project_id` and `input`; it omits `run_id` and `expected_revision`. Its closed
input is:

```json
{
  "predecessor": {
    "run_id": "00000000-0000-4000-8000-000000000001",
    "revision": 42,
    "event_digest": "<exact SHA-256 of the committed head>",
    "state_digest": "<exact SHA-256 of its canonical decoded state>",
    "deadline": "<immutable predecessor deadline>"
  },
  "deadline": "<new explicitly authorized interval deadline>",
  "authorization_ref": {
    "path": "resources/artifacts/continuation-authority.md",
    "digest": "<SHA-256 of the exact scoped authority record>"
  }
}
```

Use actual digests and timestamps, not these explanatory placeholders. The
reference records the human instruction's scope and provenance; its existence
never grants an external effect, more resource capacity or a different account.
The existing PM owner must authenticate the same native identity, seat,
repository and branch, with current exclusive claims for the new run home,
predecessor, plan, plan lock and authority reference. Same-native seat renewal
and cross-native handoff remain their separate existing protocols.

The child identity is deterministic for the resolved project and predecessor.
One predecessor cannot acquire two competing children by changing a request ID.
Exact concurrent retries serialize through the normal journal lock. Reusing a
child identity with a different request, deadline, authority reference or
predecessor head is refused, including after interruption.

## Carried state and current evidence

The owner fully replays every linked predecessor and checks its exact terminal
head and deadline. It retains the full nested resource ledger and all known and
UNKNOWN actual usage, hard or forecast enforcement, consumed trial allowances,
failed strategies, waits, artifacts, receipts, native cursors, child dispositions
and unfinished graph work. Limits cannot be replaced through this operation.
A later authorized capacity change must use its existing resource owner.

Every registered artifact is reopened through a bounded descriptor read and
matched to its retained digest. Missing, changed, symlinked, nonregular or
oversized evidence refuses the operation. Known unresolved external effects,
live or unaudited children, running graph nodes, active native continuations and
unresolved prepared launches require reconciliation before admission. A terminal
run does not itself prove all worker or process custody is settled.

The child starts `preparing`, with a new interval deadline and current workflow
binding. Historical receipts and verification entries retain their original
run/source bindings. They do not become current verification, fresh loaded
skills, native enrollment, wake survival or new action authority. `next`, native
source reconciliation and `finish` still invoke their ordinary current-source,
release-generation, authority, budget and evidence checks. Known gaps in older
untyped history remain explicitly unqualified.

## Commit and recovery

The authoritative commit is one complete successor event appended by the existing
journal owner. Before that event, a pending runtime index cannot supply a run and
managed discovery refuses it. A crash after append leaves a committed `preparing`
run; current/plan/index projections may still need reconstruction. There is no
automatic work dispatch or enrollment during this transaction.

Retry the exact request. Recovery verifies the complete predecessor chain,
artifacts, native ownership and fresh pre/post admission, then rebuilds only the
derived projections/index. Changed authority, claim generation, plan semantics,
predecessor bytes or input paths refuse recovery. An already committed child can
be reconstructed after its deadline, but subsequent work cannot ignore expiry.
The original predecessor and its deadline are never rewritten. Earlier request
registrations remain in that predecessor rather than becoming new commands.

The fences assume cooperating owner-managed writers plus ordinary filesystem
identity checks. No multi-file transaction can freeze unrelated privileged
filesystem writers. Journal digests, descriptor identity, path rechecks, locks
and final admission detect the supported races; these are not a claim of global
filesystem immutability.

## Bounds and refusal

The request remains bounded by the controller's 256 KiB limit. This operation
admits at most 32 linked predecessors, 10,000 aggregate historical events,
2,048 reservations and 10,000 artifact/reference entries. Ledger ancestry is
bounded to 32 levels. Each artifact uses the existing 64 MiB logical record
ceiling and the aggregate artifact read is at most 1 GiB. Journal witness counts
use the existing event plus block-store limits; no normal journal/storage cap
is raised. These limits keep full verification bounded and refuse excessive
input rather than silently pruning it.

Admission has a 120-second cooperative deadline, checked during bounded reads,
replay and lock acquisition. Existing individual PM/native operations retain
whatever stricter finite subprocess deadline their owner enforces; the transaction
deadline is not a promise to preempt arbitrary Python callbacks. The new interval
must be future, later than its predecessor and within seven days of admission.
There are no internal retries. A refusal retains every original byte and reports
the bound or unresolved custody; it cannot refund cost or manufacture completion.


Interrupted-prefix recovery binds the exact request, semantic plan digest, native
identity, coordination board and claim generation. The pending runtime index is
only a recovery hint: it grants no execution authority. After the child event is
committed, ordinary writers refuse any new parent event, including terminal-safe
observations; finish parent custody reconciliation before creating its child.
This preserves the child's exact-head lineage without rewriting the predecessor.
Journal discovery counts every physical entry before sorting, including retained
staging entries, and refuses excessive cardinality or elapsed enumeration.

Coordination reads invoked by a worker thread use the same finite process owner
in a dedicated supervisor whose main thread owns signal handling. The caller's
anonymous pipe provides parent-death custody; EOF terminates and reaps the owned
command group. Main-thread signal handlers and the existing anonymous snapshot
FD rules are unchanged. This does not claim custody over deliberately escaped
process sessions.

The thread supervisor executes a bounded anonymous snapshot of the module code
already resident in the caller, under isolated Python with bytecode-cache writes
disabled. It never reopens the module pathname at dispatch. The descriptor must
be an owned anonymous regular file and its exact size and digest must match
before decoding. This internal snapshot is not caller-provided serialized code.

<!-- verbatim: skills/synthesis-autopilot/references/owner-resume.md at 3.6.7 -->

# Same-native ownership after a released seat

PM identities are terminal after release. Reclaiming the same project in the
same native conversation correctly allocates a new seat; that alone cannot
change the owner of a retained autopilot journal. `owner.resume` connects those
owners through the existing run lock, event writer and host-local indexes.

This operation is distinct from transferring work to a different native
conversation. That still requires `owner.transfer.prepare` followed by
`owner.transfer.accept`. A missing predecessor, active predecessor, changed
native identity, changed machine/worktree/branch, pending handoff or terminal
run cannot use same-native renewal.

## Evidence and invocation

Use the ordinary `autopilot.py command` entry point with `--name owner.resume`,
the selected project/run, existing native actor, expected revision and a stable
command ID. Its payload has these fields:

```json
{
  "previous_owner": {"session_uuid": "PREVIOUS-UUID", "native_ref": "codex:NATIVE-UUID"},
  "basis_revision": 15,
  "basis_digest": "SHA256-OF-CANONICAL-OLD-STATE",
  "plan_digest": "SHA256-OF-CURRENT-HUMAN-PLAN",
  "user_message": {
    "offset": 1234,
    "length": 456,
    "sha256": "SHA256-OF-EXACT-NATIVE-JSONL-RECORD",
    "excerpt": "The exact direct-user paragraph being interpreted."
  },
  "reason": "The authenticated owner's interpretation of the user's resume instruction."
}
```

The owner computes the state digest with `run_state._digest(state)` and the
human-plan digest with `run_state._plan_digest(project, state)`. The user-message
locator points into the current native root transcript, not a copied artifact.
The structured-question and cross-chat evidence forms below extend that reader.
PM's production observer establishes the client identity and exclusive current
claims. The reader then verifies native producer identity, inode/header, complete
record boundaries, exact bytes, user origin, and a timestamp strictly after the
old seat's terminal timestamp. Quoted paragraphs, fenced and indented code,
HTML containers, tools, peers, child/metadata messages and known hook/heartbeat
injections are refused. Fence boundaries retain their opening character and
length; a different or shorter marker cannot expose an example as user prose.
Lazy blockquote continuation lines remain quoted until a paragraph boundary.

The current direct-user text reader covers Codex and Claude root transcripts.
Muse's raw user-intent envelope does not yet have a qualified direct-user text
contract; renewal refuses explicitly on that client rather than claiming an
opaque payload is human approval. Other client families likewise require their
production PM identity and qualified direct-user text reader before acceptance.

Native provenance is not a machine-certified interpretation of natural
language. The operation records the actual excerpt and the admitted agent's
interpretation separately, always with `authority_granted: false`. It does not
mint an approval receipt, add action scope, activate a schedule or replay an
effect. Existing action owners continue to enforce authorization.

## Native asynchronous answers

A Codex answer delivered by `request_user_input_async` can supply the human
observation. Keep the ordinary reply record locator; set `excerpt` to the exact
selected option and add this `question` object:

```json
{
  "offset": 1000,
  "length": 300,
  "sha256": "SHA256-OF-QUESTION-CALL-RECORD",
  "interval_sha256": "SHA256-FROM-QUESTION-OFFSET-THROUGH-REPLY-END",
  "call_id": "NATIVE-QUESTION-CALL-ID",
  "message_id": "NATIVE-USER-REPLY-ID",
  "question_index": 0,
  "title": "The exact question shown to the human."
}
```

The existing native question owner verifies one matching question call, its
`accepted: true` acknowledgment, and one later root-user reply. It binds the
question index, full title, offered options and chosen answer. The complete
interval is limited to 16 MiB and 16,384 records; every selected record is checked
by the native adapter. Its hash also binds the acknowledgment and intervening
records across admission and commit. Missing coverage refuses; a transcript
suffix does not substitute for an older question.

The original refusal of an unbound `<send_user_message_question_reply>` remains.
Assistant/tool/heartbeat content and a quoted response do not qualify. This
form records the full question and selected answer alongside the owner's
interpretation. A selected option is evidence of the human's choice, not a new
action-approval receipt.

## Human evidence from another Codex chat

The native run owner still renews the same recipient conversation. The source
conversation supplies the human evidence; it does not become the run owner.
A fresh message through the existing `send_message_to_thread` tool can carry
this exact JSON object as its prompt:

```json
{
  "owner_resume": {
    "scope": {
      "run_id": "EXACT-RECIPIENT-RUN-ID",
      "project_id": "EXACT-PROJECT-ID",
      "recipient_native_ref": "codex:RECIPIENT-NATIVE-UUID",
      "previous_owner": {
        "session_uuid": "EXACT-PREVIOUS-SEAT-UUID",
        "native_ref": "codex:RECIPIENT-NATIVE-UUID"
      },
      "basis_revision": 15,
      "basis_digest": "SHA256-OF-CANONICAL-OLD-STATE",
      "plan_digest": "SHA256-OF-CURRENT-HUMAN-PLAN",
      "restart_wait": null
    },
    "source_native_payload": {
      "session_id": "SENDER-NATIVE-UUID",
      "transcript_path": "ABSOLUTE-PATH-TO-SENDER-NATIVE-TRANSCRIPT"
    },
    "user_message": {
      "offset": 1400,
      "length": 250,
      "sha256": "SHA256-OF-SENDER-USER-REPLY",
      "excerpt": "The exact selected option.",
      "question": "THE-COMPLETE-QUESTION-OBJECT-DESCRIBED-ABOVE"
    }
  }
}
```

These are schema illustrations. Populate every value from the current recipient
run and native source records. `question` must be the complete object, not the
illustrative string. Include the exact `restart_wait` object in both the scope
and command when acknowledging a restart pause; otherwise the scope contains
null and the command omits it. A changed run revision, plan or wait requires a
fresh matching delivery.

Use the existing send tool with its current human authorization. A successful
sender response containing only `threadId` is an acknowledged dispatch, not
proof of delivery. On the recipient, locate the host's `response_item` of type
`function_call_output`, namespace `codex_app`, name `send_message_to_thread`, and
its matching `event_msg.item_completed`. The first record has no `call_id`; its
host metadata binds the receiver message/turn IDs. The second names the actual
recipient thread and the identical message ID and output. Supply their exact
record locators as the command's `user_message`:

```json
{
  "delegation": {
    "receipt": {"offset": 2000, "length": 800, "sha256": "EXACT-RECORD-SHA256"},
    "completion": {"offset": 2800, "length": 700, "sha256": "EXACT-RECORD-SHA256"}
  }
}
```

The receiving owner authenticates its native transcript, verifies the host
routing pair and exact scope, then independently authenticates the sender's
native transcript and re-reads the human question proof. The human answer must
postdate the old seat's release, precede delivery, and satisfy the original wait
chronology when applicable. Both native sources are checked again before commit.

The host's sender-user-message excerpt is partial historical context and does
not transfer permission. This protocol does not use it as authority. Plain
forwarded prose, a claimed approval, a sender tool result alone, nested forwards,
and a historical delivery lacking the exact evidence pointer all refuse. The
owner records the human evidence and its own interpretation separately; existing
action owners still decide authorization. No arbitrary JavaScript wrapper is
parsed or executed to establish this proof.

## Acknowledging a restart pause

An optional `restart_wait` object names `id` and `sha256` of one exact pending
user wait. The run must be `waiting_user`, and the observed user message must
postdate both that wait's creation and the old seat's release. Use this only
when the current user has resumed the session that was paused for restart.

Existing wait records do not encode a typed reason category. The agent's
identification of that wait as a restart pause is therefore explicitly recorded
judgment, not semantic permission inferred by a string matcher. The original
wait row is preserved in `restart_acknowledgment.prior`; the journal also retains
it verbatim in all prior events. Only the named wait becomes resolved. Other
waits, external effects, permission gates, contracts and profiles remain intact.

## Recovery and verification

The new event changes the owner and sets `recovering`; it preserves the same
run ID, prior events, costs including unknowns, failed attempts, original
deadline, workflow, children, evidence, artifacts and contract/profile history.
It adds a provenance record to `ownership_recoveries`. Apart from the optional
exact restart-pause acknowledgment, it leaves all waits untouched. Follow with
ordinary controller recovery and the existing source/effect/worker readbacks.

Admission and source bytes are checked again immediately before append. A
changed claim, plan, source or stale expected revision fails without a new
event. Exact command retries use the existing idempotency contract; changing
the body or trying to consume the renewal again under a different ID fails.
Old and new owner indexes use the same interrupted-transfer recovery conventions
as the existing transfer operation. Ownership renewal proves neither native
continuation nor process-loss survival.

An elapsed workflow deadline remains elapsed after seat renewal. Reconciliation
may recover ownership without admitting more productive work. A terminal run
cannot be renewed. A newly authorized interval uses the existing
[successor transaction](successor-transactions.md), preserving the exact
predecessor head, costs and obligations; renewal never extends a deadline.

<!-- verbatim: skills/synthesis-autopilot/references/operator-experience.md at 3.6.7 -->

# Operator status and handoff

A user delegates an outcome in ordinary language. The agent resolves the project,
prepares its controlling plan and completion contract, and invokes the existing
controller. The Console's first-task form composes that delegation; it does not
create a run, invent a native actor or grant new authority.

`operator_status.py` is a read-only projection of the existing run owner. It
streams and validates the selected event chain, checks the project binding, and
keeps current projections subordinate to the journal. Missing or stale derived
files prompt an owner rebuild. Corrupt chains and redirected or oversized paths
produce an unhealthy result. Discovery returns eight runs per page, with a
maximum page size of 32, a 4,096-entry inventory ceiling and a 32 MiB bound per
journal. Filesystem recency orders discovery only; it does not establish progress
or authority. Cursors bind the exact project inventory and page size; a changed
inventory requires refreshing the first page. Older runs and their retained
questions remain available through page links. Each question page states its
coverage, and an exact run can be selected independently. These are operator-read
limits, not completion or resource-policy thresholds.

Console registry selection invokes PM's existing causal resolver with fetching,
canonical fast-forward and coordination refresh disabled. A newer attributed
worktree can supply the selected journal while the canonical checkout remains
unchanged. Conflicts and unknown recovery state show explicit diagnostics with
no canonical fallback. The response binds the registry path and bytes, selected
physical project, causal head and tree. This selection grants no native identity,
claim, write permission or fresh completion acceptance.

The view distinguishes recorded work, waiting, unhealthy recovery, completed and
cancelled runs. A recorded terminal result does not establish current artifact
acceptance. Native liveness, actual notification delivery, loaded-session code,
billed usage and continuation remain unknown without their respective current
owner proofs. Last useful progress comes from the workflow's meaningful progress
records; narration and the journal update time are not native heartbeats.

Pending questions are available through the Console's source-gated question
fallback. Rendering, preparing or copying an answer changes no wait. The current
authenticated native owner must match the pending question and use the existing
wait-resolution evidence path. No Console answer is an approval receipt.

Recovery and cancellation handoffs retain an exact run, request identity and
expected revision. The user copies them into the owning native task; the owner
performs current PM/native admission and controller CAS. A prepared request is
not queued, performed or acknowledged. Replays follow the controller's existing
idempotence rules. A cancelled run may still retain unfinished child, effect or
continuation cleanup; cancellation is not verified termination.

For a damaged installation, use existing onboarding and skills-manager doctor,
repair and update owners. Preserve evidence before repair. Updated installed
bytes do not imply an already running task loaded them. Checkpoint and recover
with freshly loaded skills through the normal native owner when required. A cold
recovery starts from the project registry and journal, then reconciles authority,
inputs, effects and children. A recovery capsule conveys references and duties;
it cannot transfer ownership or prove survival.

If the A9 supervision owner is present, its bounded `status_view(state)` supplies
historical queue, lease, backoff and cancellation facts. The Console does not
create a second queue or actor. Request completion means the owner subsequently
observed its bound native wake; it does not prove this display caused the wake
or that the user's task finished. Automatic launch from this Console remains
unavailable. Primary-pane loss is qualified separately from machine or process
survival, and a readable local fallback is not a delivery receipt for an OS
notification.

<!-- verbatim: skills/synthesis-autopilot/references/supervision.md at 3.6.7 -->

# Optional supervision through existing owners

The optional integration uses the existing Console process as an independent
visible observer. It does not install a new guard daemon or change the existing
native-toolchain ADR. Console lifecycle, launchd/systemd enrollment and uninstall
remain with Console's existing installers. Enabling a journal enrollment is
separate from activating a service; neither operation authorizes the other.

## Source interface

Authenticated native agents submit the ordinary controller `record` operation
with `kind: supervision`. The controller applies closed-schema actions through
the existing PM admission, run lock and CAS journal. The browser and Console
status process cannot construct an actor or grant approval. The implementation
does not expose a shell command string or arbitrary executable to the queue.

| Action | Fields beyond `kind` and `action` | Meaning |
| --- | --- | --- |
| `enroll` | `authority_ref`, `max_requests`, `max_attempts`, `lease_seconds`, `backoff_seconds` | Explicit opt-in bound to current owner/claim, contract, profile and controlling instructions. The authority reference must already occur in the current contract. |
| `request` | `request_id`, `job_id` | Retain a request concerning one existing native continuation job. This does not register or launch it. |
| `claim` | `request_id` | Recheck current native capability/job, recovery, waits, effects, artifacts and children. Successful admission issues a bounded request-only lease and increasing fence. |
| `reconcile` | `request_id` | Read existing owner-verified subsequent wake evidence. Missing or ambiguous delivery remains unresolved and is never replayed. |
| `cancel` | `request_id`, `reason` | Preserve a request cancellation tombstone. Native job cancellation remains a separate action with its required readback. |
| `stop` | `reason` | Stop admission and cancel retained intents; preserve diagnostics. Does not claim that a native job or Console process was stopped. |
| `uninstall` | `reason` | Retire the optional journal enrollment and preserve tombstones. Actual Console service removal belongs to its lifecycle owner. |

The queue permits at most 64 retained request identities, five admission attempts
per request, a lease of at most 300 seconds, and configured exponential backoff.
Limits must be explicit finite positive integers. The same identity cannot be
reused after completion or cancellation. A leased or ambiguous request cannot
be claimed again; expiry requires reconciliation. A fresh native wake may resolve
the observation, but it does not prove that this optional observer caused it or
that the task outcome succeeded.

Queue state, configuration, lease fences, attempts, backoff and tombstones live
only in `extensions.supervision` of the authoritative run journal. There is no
additional authority database. Enrollment is invalid when the actual owner,
claim, contract, profile or instructions change. Cancellation remains possible
under fresh current PM authority. Re-enrollment cannot erase retained requests
or active uncertainty. A future schema upgrade must retain these obligations.

## Read-only Console adapter

`supervision.status_view(state)` produces a finite historical projection;
the ordinary controller also returns it as `coverage.supervision`. It includes
the schema, lifecycle, journal revision, bounded requests, status counts,
diagnostics, supported-schema health and explicit survival limits. Console may
display or poll this projection through its existing bounded subprocess/status
adapter. No PM actor is required to display historical records; a fresh native
actor is required for every mutation.

An application must not infer current external state from the read-only view.
Provider effects and current native bytes are checked at actual admission.
Request-only dispatch data binds the exact job, request, journal revision,
owner, contract, profile, plan, fence and validity end; its fields explicitly
deny effect replay and ownership transfer. Those fields are not a provider
credential or an instruction for Console to impersonate the native owner.

## Owner-prepared native continuation

An actual current native agent can prepare one exact-session launch through
controller `record(kind=launch_prepare)`. Required fields are `permit_id`,
`authority_ref`, `token_sha256`, `expires_at`, `max_wall_seconds` and
`max_output_bytes` and `native_posture`. The authority reference must already be in the current run
contract. Enrollment, current effects, native invalidation, waits, children,
inputs, instructions and resource admission must all permit continuation.

The native posture is an explicit requested launch policy, not a reconstructed
fact about an earlier host. Muse's `serve` sandbox is fixed for the process
lifetime; a saved Session carries approval mode but does not establish the
previous shell, write, trust or network settings. The owner must retain the
original launch-policy evidence and preserve every known stricter restriction.
If that evidence or the authority to select the requested policy is missing,
do not prepare a grant by guessing the previous defaults.

The supported closed object is `{"schema_version":1,"profile":"muse-restricted-v1",
"sandbox_enabled":true,"network":"restricted","shell_enabled":true,
"write_enabled":true,"workspace_trust":false,"approval_mode":"onRequest"}`.
`shell_enabled` and `write_enabled` may be explicitly false to retain stricter
restrictions. All other values and extra fields are refused. The journal binds
this requested-policy object to the one-use permit; its booleans are not native
enforcement attestations. Inherited environment, saved trust and policy precedence
remain UNKNOWN unless independently established for the actual host generation.
Before reservation and again before spawn,
the consumer validates it and uses only fixed `serve` flags: network restricted,
plus disable-shell or disable-write when selected. It never accepts raw flags,
disables the sandbox, or enables workspace trust. Network, disabled shell and
disabled write have explicit flags. Sandbox enabled and workspace trust disabled
use documented native defaults by omitting their disable/trust flags; those
omissions do not prove effective inherited-policy enforcement.
After exact-session resume, the actual Session must report `onRequest`; missing
or different approval state prevents `turn/start`. No approval-mode change is
sent. The retained native trial supports this explicit profile; it does not
qualify every possible historical or future host policy.

The agent generates a fresh cryptographically random token, submits only its
SHA256 digest, and supplies the token to the existing local Console adapter by a
private credential handoff. Never put a token in a browser request, URL, command
argument, journal, or logs. The plan does not authorize a browser to prepare a
grant. A grant expires within one hour and before the run deadline, permits one
native turn with at most 900 seconds and four MiB of transport output, and binds
its real issuer, exact native UUID, project, run, claim, contract/profile/plan,
artifact identities and runtime/attribution root. Unknown model/billing use is
not recorded as zero. Current workflow resource admission still applies.

The bounded deterministic entry point `prepared_native_launch.py` reads one
stdin JSON object with exactly `project`, `run_id`, `permit_id`, `token`, and
`runtime_root` (or null for the configured default). It accepts no actor, prompt,
command or executable. It initializes the existing owners, resolves the project,
inspects current issuer authority and consumes the grant under the existing run
lock. Its journal events identify a prepared-grant consumer explicitly; they do
not pretend that Console is a native agent. Submission rechecks the same fence.
Uncertain delivery and interrupted consumed grants cannot be retried blindly.

Grant mutations stay in `extensions.prepared_native_launch` of the same journal.
`record(kind=launch_cancel, permit_id, reason)` leaves a cancellation tombstone.
A running transport polls that tombstone and requests exact native turn
cancellation. Process termination alone is not proof of provider cancellation;
missing native terminal readback remains UNKNOWN. Native terminal success means
only that a transport turn ended: it never completes a Synthesis criterion or
run. The resumed native agent must authenticate its own identity and run the
ordinary resolver/admission/controller recovery protocol before taking action.

Delegated journal/projection writes go through the existing repo-guard
attribution owner. It verifies the committed one-use grant event and pre-edit
basis, current issuer, exact input set and exact changed paths, then takes the
existing lifecycle lock and atomic writer. Projection bytes must match the
owner's deterministic journal/plan compiler and the controlling human plan
basis; an allowed filename cannot authorize arbitrary content. It preserves
unrelated manifest rows and rejects a foreign manifest or concurrent producer
edit. It does not repair foreign
attribution, manufacture claims, publish, or create another authority database.

## Native transport and lifecycle evidence boundaries

Read the [current Muse launch protocol](muse-launch-protocol.md) before preparing
or consuming a Muse grant. Its owner-derived protocol binding and verified
handshake are mandatory in addition to every authority and policy gate below.

The implemented transport uses Muse MSP `session/resume` and `turn/start`
with queue semantics. Resume does not establish a connection-exclusive lease.
A new queued turn is reconciled through exact `turn/unqueue` custody; missing
authoritative removal remains unresolved. It binds the actual installed
versioned binary and refuses changed bytes, a different/forked session, an active
turn, wrong workspace or pending human request. The fixed launch-argument
mapping above is enforced; no model, provider, trust or approval reconfiguration
is performed. The source contains finite tests;
release/native receipts must separately bind the actual installed binary.
Both directions of the stdio exchange are bounded, including write backpressure
and shutdown. A terminal needs a typed, exact-session source range and nonempty
cursor; malformed or foreign terminal data remains UNKNOWN. Native terminal
readback never attests the quality or completion of the Synthesis task.

Codex `turn/start` can steer an active turn and its exported contract has no
atomic idle precondition. Claude's background resume can copy an active session.
Neither is treated as safe exact-session mutual exclusion. Those transports
explicitly refuse automatic launch until their native ownership mechanism is
qualified; ordinary native-owned scheduling remains separate.

A11's Console surface is read-only. Connecting the existing Console process to
the stdin consumer and private owner-grant credential handoff is an explicit
integration and enrollment action, not an effect of viewing the page. There is
no new daemon. The existing request-only queue continues to report automatic
job launch unavailable; the prepared transport is a distinct finite capability.

A same-session local native turn does not establish survival after app exit,
logout, reboot, offline operation, machine loss or a machine transfer. Actual
first and later automatic wakes, independent overdue observation, cancellation
readback, native PM cold recovery and Console lifecycle installation remain
separate acceptance observations. Preserve the independent backstop requirement
until demonstrated equivalent behavior is accepted.

For operational health, inspect Console's existing lifecycle receipt, the queue
projection and `coverage.prepared_native_launch`. For upgrades, stop admission,
retain consumed grants, cancellation tombstones and uncertain effects, install
the reviewed owner package through the normal release process, then re-enroll
through fresh native admission. For removal, retire journal enrollment and use
Console's existing service uninstaller; verify both independently.

<!-- verbatim: skills/synthesis-autopilot/references/efficiency-measurement.md at 3.6.7 -->

# Measuring local owner overhead

Use `scripts/efficiency_profile.py` for an explicitly requested, read-only local
profile. Supply a bounded case object with `schema_version: 1`, `owner`
(`startup`, `resume`, `checkpoint`, or `review`), absolute current `project`,
`project_id`, `run_id`, and the existing native `actor`. The agent prepares the
case and a new retained scratch directory, invokes the owner, and summarizes
its report. It never launches a provider, native agent, local model or service.

The four measured boundaries are exact: PM current native/claim admission;
current run journal plus fresh owner/evidence inspection; the checkpoint's
read-only capsule calculation under active admission; and the deterministic
criterion report. This is not a timing claim for the entire UI session startup,
a full checkpoint publication, a paid independent review, or a native app.

Each run retains inputs, stdout, stderr, process-owner disposition, source
hashes and a report. Source hashes describe on-disk files for loaded modules at
probe completion, not an attestation of executable memory. It compares new Python interpreters with repeated calls
inside a single interpreter. Every repetition still admits current authority
and checks current bytes. OS filesystem caches are not flushed. The first
sample in the warm process includes its initial imports; later samples reveal
in-process reuse. Do not discard that first sample to inflate a speedup.

Reports include wall time, process CPU, peak traced Python allocation and
process-lifetime RSS high-water. RSS is not a per-operation delta. Provider
input/output/cached tokens, harness-wide tool totals and energy remain `null`
when not observed. Never substitute zero, a guessed tokenizer count or machine
power specifications for absent measurements.

A matching refusal is outcome equivalence, not operational readiness. Both
fields are shown. Source digests must also match across modes. Changed input,
revoked claims, corrupted evidence and unsupported capabilities require explicit
refusal/invalidation controls alongside current positive controls. Preserve all
results and unknowns. Record the experiment before choosing an optimization;
measure the changed implementation against the same outcome and guard checks.

The existing one-operation PM admission token is a useful deterministic
optimization: local observers can share that freshly issued token during the
operation, and it expires immediately afterward. It cannot be serialized or
replayed from native memory. A persistent cache of old authority would have a
different safety contract and is not an efficiency improvement.

Limits are 1–5 cold probes and 1–5 warm repetitions, up to 30 seconds per owned
process with the existing 1 MiB output bound. An interrupted/failed probe is
incomplete; retained diagnostic completeness may be unknown. Automatic retry,
model selection, new compute allowances and native-memory activation are absent.
