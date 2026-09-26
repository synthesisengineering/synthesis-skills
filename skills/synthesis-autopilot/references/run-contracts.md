# Run contracts and command interface

For ordinary delegated work, use the eight-operation
[execution controller](controller.md). It prepares inputs and invokes the same
owners described here, retaining exact request prefixes across interruption.
The lower-level interface remains useful for specialized observations, effects
and explicit recovery; it does not bypass current workflow constraints.

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
