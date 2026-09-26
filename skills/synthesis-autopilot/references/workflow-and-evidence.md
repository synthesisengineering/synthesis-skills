# Adaptive workflow, resources and evidence

The workflow shares the run engine's authenticated, serialized transaction. It
does not own a second project registry or grant permission to tools. Its commands
use `autopilot.py command --name workflow.<command>`; see the
[command interface](run-contracts.md) for common arguments.

## Explain the defaults

Resolve five independent dimensions: domains, uncertainty (`low`/`high`),
effect (`none`/`local-reversible`/`external`), horizon (`turn`/`session`/`reboot`),
and whether independent work is available. A mixed task has multiple domains.
The resolver adds checks for each domain, independent evidence for high
uncertainty, effect reconciliation for external actions, and observed survival
for a reboot horizon. It does not change models or grant new action authority.

Public defaults, user preferences, project preferences and explicit instruction
deltas retain provenance. Unknown fields and malformed types are rejected.
Optional checks may be disabled with a reason. Invariant/domain requirements
cannot be disabled by a preference. Blog material is opt-in, reusable lessons
are conditional, and completion reporting is domain-neutral. Explicit migration
of old preferences preserves personal choices and records renamed report items.
Active runs retain their frozen profile until an authorized amendment.

```json
{
  "dimensions": {
    "domains":["software"], "uncertainty":"low",
    "effect":"local-reversible", "horizon":"turn", "parallelizable":false
  }
}
```

This is a `workflow.configure` payload. Reconfiguration with changed settings
requires a core amendment and a reason. Reconcile active tasks and child returns
first. Accounting survives amendments. Use stable evidence at material
boundaries; do not oscillate between strategies on each new message.

## Work graph and delegation

`workflow.graph` declares nodes with dependency and criterion references. The
graph must cover every required criterion, have no cycles, and stay inside the
scope contract. `ready_tasks` returns dependency-ready work in priority order;
the work-in-progress limit applies when starting a node. A blocked dependency
does not block independent nodes. Rolling planning expands details when inputs
arrive without silently expanding the outcome.

`workflow.dispatch` requires a typed brief, admitted exact paths, criterion
references, an integration owner and a resource reservation. It records the
worker handle and cancellation/return expectations. Actual native dispatch
remains the host's job. Existing coordination addresses peers; a saved queue
item is not proof that a worker received it or woke.

Every dispatch supplies `file_contract` schema version 1, with `immutable_inputs`
(`artifact_id`, absolute `path`, current `digest`), `output_roots` and a separate
`scratch_root`. Immutable inputs must bind to registered project artifacts;
every writable root needs current PM admission. Input and writable roles cannot
overlap. Physical inspection rejects links or aliasing that could redirect a
write, and the worker receives the exact role inventory, deadline and reservation.
An empty execution log is not permission to add an entry.

The `peer` and native collaboration `artifact-only` modes retain their existing
identity and integration contracts. Their typed file roles are instructions;
these interfaces do not themselves establish per-child filesystem enforcement.
The explicit `native-cli` mode selects `client: claude`, `codex` or `muse`, declares
`required_capabilities` from the client's reported operations, and stays
under the current parent's admitted output/scratch paths, and leaves the producer
identity unknown until an actual native launch establishes it. Configured model
and effort are retained. Unsupported boundaries refuse execution rather than
launching a worker with a claimed protection it does not have. `explain` reports
the worker declaration separately from root-session support. Claude/Codex workers
provide native `read`, `write`, `edit` and `shell`; Muse provides the explicit
`artifact-generation` operation through a no-tools model invocation and validated
parent materialization. Unsupported requirements are rejected before a provider
call. A missing child capability does not remove ordinary root-session tools.

Register this observation specification as an input artifact, then invoke the
generic `observe --name native_worker` interface with its `check_id`:

```json
{"schema_version":1,"kind":"native_worker",
 "arguments":{"child_id":"worker-a","timeout_seconds":120}}
```

The engine chooses the controller-owned evidence directory and the client from
the admitted dispatch; the specification cannot supply arbitrary commands,
environment variables or a different runtime directory. The single-attempt
launch retains native identity, boundary configuration, resource observations,
output hashes and input-preservation results. Missing usage stays unknown.
`workflow.worker_record` binds that observation using `child_id` and `receipt_id`.
A successful native turn does not satisfy the task's quality criteria: return
and independent integration still follow. A failed or interrupted attempt keeps
its evidence and cannot silently repeat the provider call.

`workflow.return` retains completed, partial, failed and cancelled results.
`workflow.integrate` records the root's acceptance audit. A cancellation request
is not termination; inspect retained output and establish the child's terminal
disposition. Completed children still require integration. Completing the parent with an
unreconciled child or required audit is rejected. An honest incomplete closure
preserves those obligations; it does not turn them into successful integration.

## Budget and progress

### Persistent attempts and current native instructions

`workflow.attempt` derives its outcome from an actual owner observation or a
supported current native process result. Task labels and caller-supplied success
do not classify the result. Attempts, materially changed strategies, re-arms,
failure families and lineage remain in the existing run journal. Productive
observations do not spend failed-attempt allowances, while new receipt IDs,
renamed tasks and graph changes cannot erase prior failures.

Current native instructions constrain task admission, completion and Stop
feedback even when the positive progress observation came from a local owner.
Authenticated retry approval can reconcile its exact message and condition;
it cannot clear an unrelated cancellation. Missing enrollment or incomplete
source coverage produces an explicit recovery obligation. The controller's
[native evidence contract](controller.md#native-evidence-and-currentness)
separates current interval coverage from historical absence claims.

The current Stop policy first screens every unresolved run, reserves one
eligible correction in the existing journal and lets the verified native
launcher consume that exact reservation. A repeated native callback or another
process cannot emit the same correction again. A terminal diagnostic is not a
completion receipt, and a Stop reservation never grants action authority.

### Resource accounting

Declare `workflow.budget` once, before distributing work. Its `limits` map names
each resource with an integer `limit` and `enforcement: hard` or `forecast`.
A forecast may have a null limit; an unknown hard limit is invalid. Include a
future ISO deadline. Reserve root integration and verification capacity too.

`workflow.reserve` and `workflow.settle` operate on one shared ledger. A child
reservation comes from its parent's remaining envelope. Descendant expenditure
counts once toward the total, including failed attempts. Unknown measured usage
retains its reservation and stays null; it is never imputed as zero. A known
overrun remains visible even when another dimension is unknown. Measured zero
is different from a missing measurement. Provider costs are forecasts unless a
trusted provider exposes enforceable accounting.

A completed outcome may retain explicitly reported unknown forecast usage when every hard resource dimension and descendant operation has been reconciled. Its unknown values and conservative reservations remain visible. An interrupted or null settlement remains unresolved, including after an earlier partial measurement; unknown cost cannot excuse unfinished work or a missing hard-limit measurement.

The search helper has two distinct uses: `check` reports arithmetic only;
`reserve` and `settle` mutate this ledger with current PM ownership. Reserve the
whole fan-out, then allocate children. Calls made outside this protocol are not
intercepted; do not claim provider-wide enforcement from a local ledger.

`workflow.progress` records evidence, output hashes and classified outcomes.
Narration alone cannot count as progress. The default permits one identical
transient retry; repeated failures then require a changed strategy or named
wait. Permanent failures and ambiguous writes are not blindly retried. An
overall attempt bound prevents cycling through cosmetic variations. Deadline
and resource exhaustion preserve unfinished obligations with explicit status.

## Actual consumer checks

Register the output, a reviewed Python consumer, and a JSON specification as
durable artifacts. The consumer and specification use role `input`. Example:

```json
{
  "schema_version":1, "kind":"python-consumer", "criterion_id":"accept",
  "artifact_id":"output", "script_artifact_id":"consumer",
  "expected":{"answer":5}, "argv":[], "timeout_seconds":5
}
```

Invoke `observe --name consumer-check` with its registered `check_id`. The
engine runs the actual consumer under OS isolation, bounded time/output and
restricted filesystem/network access. It hashes outputs and compares parsed
observations with the declared result. Missing isolation is a failure, not an
unsandboxed fallback. macOS uses the native sandbox; Linux requires bubblewrap.
Review the check's adequacy: a separate process does not make a self-designed
test independent, and an expected constant is not a useful consumer.

Other bundled observation specifications use
`{"schema_version":1,"kind":"project-resolution","arguments":{}}`.
The same pattern supplies claim/native identity checks, working inputs,
task/progress/profile observations and recovery components. Kind-specific
arguments are validated; arbitrary code and supplied result flags are refused.

## Domain quality and native review

`workflow.grade` consumes a trusted `quality_observation` about the **reviewed
output**. The receipt artifact's identity is different from that output's
identity. Both remain bound to current bytes. Software checks actual consumer
behavior; research checks decisive sources/counterexamples; writing checks
reader purpose and factual fidelity; data checks reconciliation/missingness;
browser work checks actual target read-back; knowledge work checks recovery.

Calibrate semantic rubrics on blind sound/defective controls. Native review
provenance must pair an actual supported dispatch with its actual return,
preserve the current run/contract/profile/artifact bindings, and identify a
distinct reviewer. A shell printing JSON, encrypted unreadable return, echoed
prompt or self-review cannot supply independent acceptance. Unknown remains
unknown. Multiple agreeing agents cannot compensate for missing evidence.

A failed or disputed grade retains its original receipt and artifact digests.
One repair round is available within the existing deadline and resource envelope:
correct and re-register the output, reserve a separate verification attempt,
collect a fresh review under a new ID, and settle its actual usage. Register a
`quality_resolution` check with arguments `criterion_id`, `prior_grade_digest`
and the new `receipt_ids`, then observe it. The deterministic producer proves
that the reviewed output changed and binds the historical failure to the exact
fresh review. It does not grant approval or declare the repair successful.

Pass that observation as `resolution_receipt_id` to `workflow.grade`, using the
new review IDs. The old grade moves into `quality_history`; the original
observations remain intact. Select the new review for the unchanged criterion
slot with `criterion.evidence.bind`, then run normal criterion, task, resource
and profile verification. A second failed grade exhausts the two-round limit;
requesting another vote, changing only a review specification, or resetting an
expired budget does not constitute a repair.

For an independent writing or research review in a supported local CLI, a
`quality_observation` specification may select `arguments.mode: native-cli`.
Declare `client` (`claude`, `codex`, or `muse`), `criterion_id`, `artifact_id`,
`calibration_manifest_id`, `reservation_id`, `timeout_seconds`, and
`max_cost_usd`. Reserve `wall_millis` and `usd_micros` through the workflow with
category `verification` before invoking it. Native currency must be explicitly
`forecast`: a CLI request budget does not establish a hard dollar ceiling.
Reconcile the measured execution and retain unavailable cost as unknown.

The adapter supplies only registered output, rubric, and blinded controls. It
preserves the user's configured model selection, uses native tool restrictions,
and verifies the actual child identity and response. Muse additionally requires
a temporary native configuration with an empty toolset and reminder roster,
verified before sending the registered inputs. The existing authentication file
is referenced in place; unrelated settings and credentials are not copied.
Failure to establish this boundary prevents the review from starting.

An exclusive durable attempt marker precedes each native invocation. A timeout
or interrupted return cannot automatically repeat the paid call under the same
reservation. Inspect its retained outcome and accounting before authorizing a
separate attempt. Controls that fail calibration remain recorded failures;
neither a fluent review nor native process success overrides them.

External effects use core intent/reconciliation commands and the existing
action owner. A lost response may follow a committed write; read the target by
the original operation identity before retrying. Observation must bind this
attempt, target and payload. Local state alone cannot make an arbitrary remote
effect exactly once. Reversing an action requires its own action authority.

The search reservation adapter enforces `SYNTHESIS_SEARCH_BUDGET_PER_AGENT`
when it is configured, before making any shared-ledger reservation. Each
requested per-agent allocation must be at or below that positive integer cap;
a present but empty, malformed, zero or negative setting refuses admission.
An absent setting leaves the explicit per-agent allocation governed by the
shared run ledger. The arithmetic `check` command still requires a configured
cap because it has no explicit per-agent allocation. Neither a large global
ledger ceiling nor a model-token allowance overrides this separate search
policy. Accepted reservations still consume the shared fan-out total and use
its existing atomic revision, nesting, settlement and unknown-cost rules.
