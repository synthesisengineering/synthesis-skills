# Preserved: 3.x workflow, evaluation and typed domain review

Verbatim text of synthesis-autopilot 3.6.7 reference files that v5 does not carry: the adaptive workflow and its ledger, the evaluation harness, and the typed domain-review engine. It is kept under ruling D8 so nothing is lost; the reason for each file is in [preserved.md](preserved.md), and where any kept rule went is in [coverage-map.md](coverage-map.md). Nothing here is current procedure. Links inside the verbatim text point where they pointed in 3.6.7 and may not resolve from this file.

## Contents

- [workflow-and-evidence.md](#adaptive-workflow-resources-and-evidence): Adaptive workflow, resources and evidence (256 lines)
- [evaluation.md](#evaluation-and-reviewed-improvement): Evaluation and reviewed improvement (311 lines)
- [domain-quality.md](#task-specific-domain-review): Task-specific domain review (228 lines)

<!-- verbatim: skills/synthesis-autopilot/references/workflow-and-evidence.md at 3.6.7 -->

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
does not block independent nodes. Apply the delivery, batching and wait rules in
[the execution workflow](../SKILL.md#execute-and-adapt) to the whole remaining
graph. Nodes and worker briefs need not be separate releases. Rolling planning
expands details when inputs arrive without silently expanding the outcome.

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

<!-- verbatim: skills/synthesis-autopilot/references/evaluation.md at 3.6.7 -->

# Evaluation and reviewed improvement

Evaluate the user's result, recovery and cost separately. Authority violations
cannot be traded for speed. No result here automatically changes policy,
profiles, models or the installed release.

The evaluator has two explicit formats. Schema 1 retains the historical corpus,
trial accounting and qualification calculations. Its `default_promotion_ready`
field describes that registration's qualification gate; it is not evidence of
comparative superiority. Schema 2 registers independently authored tasks,
separate first/rescue episodes and paired source/project-cluster analysis.
The existing `evaluation.py` CLI dispatches by `schema_version`; its schema 2
owner is `evaluation_v2.py`. Historical records are never converted implicitly.

## Corpus and collectors

The historical regression corpus contains thirty tasks: five each in software, research,
writing, data, browser operations and project/knowledge work. Tasks include
missing evidence, denied publication, partial returns, interrupted work and
late wakes. Correct refusal plus useful authorized preparation is the expected
outcome for an action outside the granted authority.

`evaluation.py corpus` exposes task and grader contracts. Its `controls` and
structured `prepare` functions test accounting/graders; they are synthetic
controls, not live agent performance. `evaluation_artifacts.py` prepares actual
worker inputs and an independently retained collector manifest. Software
consumers execute real code; data collectors reconcile files; browser fixtures
read their own stored target state; knowledge cases inspect actual retained
project artifacts. The worker must not receive the grader manifest or answers.

Use `evaluation_artifacts.prepare(task_id, root)` for the actual work-product
suite and `grade_artifacts(bundle, browser_observer=...)` afterward. Local
browser fixtures expose an independently owned observer. Preserve all initial
inputs and sentinels. JSON claiming an outcome cannot replace the specified
work product or target read-back. Domain semantic quality and actual native
journeys remain separate evidence fields when the collector cannot establish
them. OS-isolated consumer execution is mandatory; no unsupported-platform
warn-and-run fallback is permitted.

For research and writing, deterministic collection verifies readable, nonempty
required documents and preserved source inputs. It reports
`document-structure-only`; it cannot establish factual fidelity or reader
purpose. Those require the calibrated semantic review. A required phrase is
neither necessary nor sufficient evidence of meaning: valid paraphrases must
not fail, and keyword-stuffed contradictions must not gain semantic acceptance.

## Pilot, freeze, then measure

First test sound and deliberately defective controls. Blind the labels while
calibrating semantic reviewers against the declared rubric. A calibration
record contains inspected control hashes, source provenance and observed
verdicts; an arbitrary string such as `calibrated` is not evidence. The
evaluation owner checks the actual native review source.

Pilot fixture usability, execution variance and resource measurement before
choosing repetitions. Freeze task IDs, source snapshots, clients, model/effort,
tools, permissions, hardware/network conditions, resource envelopes, randomized
arm order, repetitions and thresholds before candidate measurement. Do not
revise thresholds after seeing a failed candidate. Retain impossible/startup
failures in their original assigned cells.

If measurement reveals a collector defect, preserve its original scores and
source. Record the correction and its failing controls, apply the corrected
collector to every arm and assigned cell, and report both score sets. A corrected
collector cannot change the frozen task, quality rubric or acceptance threshold.

Use these lanes:

- **Controlled:** native host, current autopilot and candidate with identical
  task/model/tools/permissions/resources. Record precisely which skill/runtime
  components actually loaded. Prompt-only loading is not a full engine trial.
- **System:** each configuration may use its genuine supported facilities under
  the same outcome and resource requirements. Report configuration differences;
  do not disable native features to create apparent parity.
- **Ablation:** remove one named component under a fixed configuration to test
  its contribution. Preserve authority and safety requirements.

`evaluation.py preregister --spec ...` produces a digest-bound schedule.
`compare --spec ... --trials ...` rejects changed assignments/configurations,
duplicate observations and arbitrary calibration claims. In historical schema 1,
attempts and rescue annotations stay inside the original trial. Schema 2 gives
each terminal episode its own record, as described below. An omitted assigned
cell is incomplete, never a pass.

Preregister candidate acceptance separately from the health of comparison arms.
Every assigned candidate cell must have a verified integer count of zero
unauthorized effects; missing, malformed or unknown counts cannot pass, even
when the configured completion rate allows other failures. A baseline defect
remains a failed or unknown baseline result and a non-passing all-arm health
report. It does not authorize candidate effects or prevent acceptance of a
candidate whose own authority, quality and completion gates pass. Preserve
historical comparisons under their original evaluator; a corrected policy
requires an explicit new registration before new candidate measurement.

## Schema 2 registration

The agent prepares the specification and invokes the existing owner:

```bash
python3 skills/synthesis-autopilot/scripts/evaluation.py preregister --spec study.json
python3 skills/synthesis-autopilot/scripts/evaluation.py worker --spec registration.json --task task-001
python3 skills/synthesis-autopilot/scripts/evaluation.py episode --spec registration.json --trials episode-input.json
python3 skills/synthesis-autopilot/scripts/evaluation.py compare --spec registration.json --trials observations.json
```

Commands emit JSON to stdout and do not modify artifacts, run workers, contact
providers or grant authority. The caller retains the emitted registration and
episodes through its existing durable artifact owner. `episode` seals one
observation; `compare` checks the whole supplied cohort and rescue chain. For
Python consumers, use `evaluation.preregister(**spec)`,
`evaluation.worker(registration, task_id)`,
`evaluation.episode(registration, **observation)` and
`evaluation.compare(registration, observations)`.

Every artifact pin is `{"path": "/absolute/artifact/path", "sha256": "..."}`.
Freeze and analysis read the actual regular-file bytes. JSON manifests reject
duplicate keys and nonfinite numbers. Changed pins or reconstructed schedules
fail validation. The registration also pins both evaluator source files, so a
different evaluator cannot silently reinterpret an existing schema 2 study.
A digest binds content; it does not authenticate a provider,
establish that tasks are independent, or supply the user's permission. The
evaluation owner must inspect those sources using their existing owners.

The specification contains these fields:

| Field | Contract |
|---|---|
| `schema_version`, `study_id`, `phase` | Version 2; stable identifier; development, confirmation, canary or regression |
| `authority_ref` | Pinned source of the existing action authority; never a new grant |
| `task_registry` | Independent task manifests described below |
| `arms`, `lanes` | Exact implementation/runtime pins, entitlements and interventions |
| `repetitions`, `seed` | Repeated observations and deterministic randomized block order |
| `analysis` | Frozen endpoint, margins, interval method, multiplicity and sample plan |
| `resources` | Whole-episode and study envelopes, cost unit, integration/evaluation reserves, shared-overhead allocation and enforcement provenance |
| `stopping` | `fixed-assignment-final`, bounded rescues, matched-window allowance, immediate harm stop and registered invalidation reasons |

A task names its `id`, `family`, `split`, `cluster_id`, independent `author` and
pinned `source`. Its worker, oracle, rubric, consumer, preservation and
calibration artifacts are all pinned separately. Confirmation requires sealed,
unexposed holdout declarations; development tasks cannot become confirmation by
changing a report label. A source/project cluster cannot cross splits within a
registration. Identical
worker/oracle/consumer content cannot be relabeled as distinct independent
clusters. Semantic similarity and source authenticity still require inspection.

The worker manifest contains `prompt` and a list of pinned `inputs` inside its
worker directory. Hidden oracle, rubric, consumer and calibration artifacts
must remain outside that directory and cannot appear as pins in worker-visible
bytes. This validates manifest entitlement; it is not an OS isolation claim.
Use the runtime's independently qualified isolation for actual workers.

A rubric contains a `version`, `scale: [1, 5]`, and distinct `criteria` with `id`
and `kind` (`deterministic` or `semantic`). At least one consumer criterion is
required. Its calibration manifest binds `rubric_sha256`, `grader`, `reviewer`,
`blinded: true`, an observation `source`, and distinct sound/defective controls.
Each control names its artifact and expected/observed PASS, FAIL or UNKNOWN
disposition. Separate `quality_controls` bind artifacts to expected/observed
1–5 scores and a frozen tolerance of at most 0.25. They must distinguish ordered
anchors at least one point apart; binary pass calibration alone cannot validate
a numeric quality scale. Confirmation requires passing controls. A preservation manifest
contains pinned `sentinels`. These manifests carry external observations; the
evaluator does not replace the domain collector or certify a reviewer itself.

Each arm names its role, authors, pinned implementation, exact client/surface/
build and pinned capability observations. `entitlement` records requested
model/effort, tools, authority scope, worker-only inputs, persistent context,
context capacity, environment and full-episode resources. `intervention` names
the workflow and pinned instructions. Controlled/ablation lanes match
entitlements and runtime while allowing interventions to differ. Strongest-native
lanes keep outcome, authority, input and resource constraints equal, retain a
credible-baseline qualification reference, and explicitly label unmatched
persistent context as a system component. Identical baseline references across
lanes reuse one frozen assignment, without duplicating observations.

## Episodes and complete accounting

An episode identifies its assignment, index, actor, terminal status, recorded
authority source, native configuration observation, independent target, timing,
environment conditions, outcome and usage ledger. The constructor supplies the
schema and registration digest. Native model/effort may be null with an explicit
reason. Unknown effective configurations and observed departures from frozen
model/effort prevent support in every lane, including strongest-native. A
controlled lane also requires observed configurations to match each other.

Index zero is the original episode. A rescue has the next consecutive index,
the previous terminal episode's digest, and a reason: `new-launch`,
`operator-repair`, `prompt-change` or `extra-authority`. It cannot erase the
original failure, precede its terminal time or rescue an already accepted
result. Different assignments cannot share a mutable target. Recorded assignment
times must respect the frozen order; equal timestamps permit concurrent launch.
An observed inversion invalidates affected pairs while retaining their outcomes
and expense. Internal review and self-correction before the first terminal
result belong to that episode.

Outcome criteria carry their registered ID, disposition, independent observer
and pinned source. A missing required criterion is unknown. A semantic
observation must use the frozen calibrated grader; quality scores need its
independent review evidence and cannot be self-graded by the worker. Critical
harm counts cover unauthorized and duplicate effects,
unrecoverable loss, false completion and isolation failure. Null counts or
missing independent harm evidence cannot establish zero. Known critical
regressions remain separately pinned. No quality/cost margin excuses harm.

A usage ledger binds an independently retained inventory and component
observations. The inventory contains `closed`, a pinned `source`, and nodes
with `id`, `parent` and `role`. Each observed component supplies its ID,
`measurement: exclusive`, `values` and pinned `source`. Values cover cost,
tokens, tool calls, wall seconds, active human minutes and human interventions;
unknown amounts are null. Children, grandchildren, review, retries, setup and
integration all belong in the inventory. Cycles, missing parents, duplicate
components and mixed aggregate/exclusive counting are rejected. Omitted
expected components and unclosed inventories keep accounting incomplete.

The comparison input is either an episode list or an object containing
`episodes`, `study_usage` and `invalidations`. A list leaves study expense
unknown. `study_usage` has `by_arm` ledgers, a `shared` ledger and a frozen
allocation across arms summing to one. An explicitly observed empty ledger can
establish zero expense; omission cannot. Each registered block invalidation
needs its reason and pinned source. Failed outcomes and their costs remain in
the operational report even when a block is excluded from paired inference.

Reports distinguish known sums from complete totals, first-episode outcomes
from rescue-adjusted outcomes, queue delay from episode elapsed time, summed
elapsed time from concurrent makespan, and forecast envelopes from externally
enforced limits. External enforcement claims require their pinned evidence and
remain authenticated by the enforcing owner. Unknown costs block the
corresponding efficiency claim while leaving outcome analysis available.

## Paired inference and sample planning

Analysis averages paired repeats within each task and tasks within each
source/project cluster. Independent clusters receive equal weight. Family
results retain their own strata; repetitions and source aliases do not increase
the independent sample count. Missingness prevents complete-cohort support.
The primary metric is accepted delivery or calibrated quality. Register its
meaningful effect, delivery noninferiority margin, family quality protection
and any cost/active-human-time reduction before measurement.

Two interval methods are available. `paired-cluster-bca/1` performs seeded
bias-corrected and accelerated bootstrap resampling of independent paired
cluster values. `paired-cluster-hoeffding/1` uses conservative bounded-mean
intervals. Bonferroni correction covers the frozen contrast/metric/family set.
BCa requires at least 20 independent clusters and sufficient transformed-tail
resampling precision. Tiny, degenerate or unresolved samples receive bounded
uncertainty instead of a zero-width benefit interval. The method threshold is
an adequacy safeguard, not a power calculation. The paired bootstrap and its
degenerate-data limitations follow [SciPy's method documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html)
and [NIST's paired-difference guidance](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/blandalt.htm).

A development-budget sample plan fixes the affordable source count without
permitting benefit claims. Confirmation requires a pinned pilot-informed plan:
power, paired-cluster variance and anticipated effect assumptions for accepted
delivery and quality in every family and the full cohort, plus efficiency when
registered. The normal-approximation estimate follows
[NIST's sample-size formula](https://www.itl.nist.gov/div898/handbook/prc/section2/prc222.htm).
Reports show estimated required clusters, available independent clusters,
method adequacy and the affordable maximum. Zero pilot variance cannot prove
adequacy. Passing this planning check does not establish achieved power or
guarantee a conclusive study. The final registered confidence gates still apply.

Efficiency compares all episode expense, including rescues, and allocated study
expense per first-episode accepted outcome. Paired cluster BCa preserves cost
and acceptance together. Undefined denominators or degenerate ratio evidence
remain inconclusive. Conservative ratio bounds additionally require externally
enforced expense support; a forecast ceiling cannot establish that bound.
Quality and reliability protection remain required even when cost improves.

Development/canary/regression observations are descriptive. Confirmation
reports SUPPORTED, NEGATIVE or INCONCLUSIVE for each registered contrast;
adoption evidence is limited to a qualified strongest-native lane with outcome
or efficiency support. Lane reports expose both statuses and configuration
qualification. A family regression,
insufficient family evidence, harm, budget breach or incomplete cohort cannot
be pooled away. These are evidence classifications: every report still has
`public_claim_authorized: false` and `activation_authorized: false`. Native
capability, survival exposure, publication review and policy adoption stay with
their existing owners.

## Scorecard and acceptance

Report quality by task family, first-attempt completion, failures and rescues,
recovery fidelity, unauthorized effects, measured usage, elapsed time and human
interventions/effort. Include exploration, coordination and failed attempts.
Unknown provider tokens/costs remain unknown; partial known totals are labeled.
Small pilot coverage does not establish statistical power or universal
superiority. Report repetitions and uncertainty rather than invented uplift.

Release acceptance requires the named correctness regressions fixed, zero
unauthorized effects in the defined tests, no material quality regression under
the preregistered rubric, and evidence for the benefit the release claims.
Measure latency against the project's exact approved definition, prerequisites
and disposition. A per-tool PreToolUse plus PostToolUse wall, a standalone Stop
wall and an import timing are different measurements. Include launcher and
integrity work in the applicable wall; report environment, percentiles and the
unchanged baseline. Do not turn an evaluation trigger into a release gate or
claim that an unmet target passed. Simple tasks must retain proportionate
overhead; complex tasks should show the claimed completion, recovery or
principal-effort benefit.

The fault matrix includes concurrent writers, duplicate commands, stale profile
and artifact receipts, missing native identity, disjoint/overlapping claims,
foreign corruption, post-commit response loss, missed/duplicate/late wakes,
resource exhaustion, cancellation, unreadable transcripts and interrupted
migration. Include positive controls proving legitimate completion still works.
Full affected CI and actual installed/native acceptance remain release gates.

`evaluation.py propose` creates a reviewed-improvement candidate containing its
benefit, applicability, regression evidence, resource impact, owner and
retirement test. Its status is proposed and activation is false. Re-evaluate
after material client/model changes; remove or change a mechanism only through
the authority required for that change.

<!-- verbatim: skills/synthesis-autopilot/references/domain-quality.md at 3.6.7 -->

# Task-specific domain review

The domain rubric binds a review to the accepted criterion, output, task brief,
and source artifacts. Every declared criterion is mandatory. The evaluator
checks coverage and exact quotations; a qualified reviewer still determines
whether the quoted evidence supports the claim. A valid quote is evidence of
presence, not entailment.

All six family routes run through the existing native CLI observer.
It preserves the user's configured model, resource reservation, immutable
attempt, native identity, artifact registry, and source-verification boundaries.
Select it by registering a **schema 2 calibration manifest** with the existing
`quality_observation` / `arguments.mode: native-cli` specification. The observer
arguments are unchanged; see [workflow and evidence](workflow-and-evidence.md).
Schema 1 observations retain their original interpretation. A schema 2 manifest
requires the typed rubric and complete evidence below; it cannot fall back to
generic booleans.

## Family contracts

| Family | Mandatory dimensions | Evidence method |
|---|---|---|
| Software | `functional_correctness`, `consumer_integration`, `adverse_inputs`; `maintainability` | Executed consumer for the first three; judgment for maintainability |
| Research | `sources_verified`, `decisive_claims_verified`, `counterevidence_checked` | Source-backed judgment |
| Writing | `source_fidelity`; `reader_purpose`, `structure`, `voice` | Source-backed fidelity; task-specific judgment for the remaining dimensions |
| Data | `arithmetic_and_denominator`, `coverage_and_missingness`, `transformation_lineage`; `reader_usability` | Executed consumer for the first three; judgment for usability |
| Browser | `target_identity`, `stored_target_state`, `excluded_item_preservation`; `interaction_usability` | Target readback for the first three; judgment for usability |
| Project | `obligation_preservation`, `causal_recovery`; `ownership_integrity`; `handoff_usability` | Consumer; target readback; judgment, respectively |

These dimensions identify the questions that must be answered. Write each
criterion's actual requirement from the task, including its reader or operator
purpose and decisive evidence. Several criteria may assess one dimension.
Missing a dimension, omitting a criterion from the response, substituting a
judgment for an execution check, and unknown families are invalid contracts.

The rubric does not replace the domain workflow. Writing still uses reader
briefing, framing, article writing when applicable, fact-checking, content
quality, craft, pitfalls, and the user's authorized voice profile. Research
still requires primary-source coverage and counterevidence. Public defaults do
not import a particular user's taste or private material.

## Registered rubric example

All referenced artifacts must exist in the current registry. The brief and
sources are inputs; `draft` is the reviewed output. This example uses one
criterion per dimension; every description is specific to the example task.

```json
{
  "schema_version": 1,
  "kind": "domain-rubric",
  "family": "writing",
  "criterion_id": "accept",
  "artifact_id": "draft",
  "task_artifact_id": "brief",
  "purpose": "Help a curious reader understand what a five-person sample can support",
  "criteria": [
    {"id":"facts","dimension":"source_fidelity","requirement":"Retain the five-person sample and invent no interviews or personal history","method":"source","evidence_artifact_ids":["brief"]},
    {"id":"reader","dimension":"reader_purpose","requirement":"Explain the sample's practical limitation to a curious reader","method":"judgment","evidence_artifact_ids":["brief"]},
    {"id":"argument","dimension":"structure","requirement":"Connect the sample size to the useful next question","method":"judgment","evidence_artifact_ids":["brief"]},
    {"id":"voice","dimension":"voice","requirement":"Keep the brief's lively, respectful voice; useful fragments are allowed","method":"judgment","evidence_artifact_ids":["brief"]}
  ]
}
```

The existing accepted criterion description also enters the native prompt.
The reviewer checks whether the rubric omits a requirement from that description
or the actual task brief and records a substantive omission against the affected
criterion. Mechanical coverage alone cannot establish semantic completeness.

## Calibration and evidence

The calibration manifest has exactly `schema_version: 2`, `domain`, `rubric`
(a readable name), `rubric_artifact_id`, `rubric_digest`, and `controls`.
Each control has `artifact_id`, `artifact_digest`, and an `expected` object
mapping **every family dimension** to its expected result. Source and judgment
dimensions use `PASS` or `FAIL`; consumer and readback dimensions must use
`UNKNOWN`, because a blind semantic control cannot certify execution or an
external account. Supply one sound control and seeded defects covering every
source/judgment dimension. Executed negative cases exercise the consumer
dimensions separately. For writing, the sound control
must retain the desired voice; a generic preference for more standardized prose
must not make it fail. The example writing rubric therefore normally uses one
sound artifact and four distinct defective artifacts.

The engine supplies opaque control identities and withholds the manifest and
all expected labels. Target, brief, sources, rubric, and control bytes form a
closed universe. Inputs are bounded and re-read after the native response.
Gold labels cannot be included as a source. Duplicate control content is
rejected; repeating the same example does not improve calibration coverage.

The native response contains `bindings`, `artifact_digest`, `assessment`, and
`controls`. An assessment has exactly `criteria`, with one row per rubric
criterion. A row has:

```json
{
  "criterion_id": "facts",
  "verdict": "PASS",
  "reason": "The output retains the count and makes no claim of personal interviews",
  "evidence": [
    {"artifact_id":"draft","artifact_digest":"<registered SHA-256>","quote":"Five people.","relation":"supports"},
    {"artifact_id":"brief","artifact_digest":"<registered SHA-256>","quote":"The sample has five participants.","relation":"supports"}
  ],
  "findings": []
}
```

Each quote must occur exactly in the current registered text. Cite the output
and every required evidence artifact. An evidence relation is `supports` or
`contradicts`. A finding has `kind` (`defect` or `preference`), `description`,
and nonempty `evidence_indices`, which point to that row's evidence entries.
Defects name requirement violations or concrete reader harm. Preferences name
optional taste; they do not veto supported work. An explicit task voice
requirement remains enforceable as a defect when it is violated.

For target consumer and readback dimensions, the reviewer judges whether the
method and supplied evidence adequately cover this task. That judgment never
attests execution or account state. The evaluator separately obtains the actual
result from the authenticated consumer or readback owner and requires both
adequacy and execution to pass. Explicitly unresolved adequacy remains
`UNKNOWN`; an actual failed execution remains `FAIL`. A successful check cannot
erase uncertainty about whether it tests the required outcome.

Each returned control has `artifact_id`, `artifact_digest`, and its own complete
`assessment`. The engine translates only its issued control alias, computes
dimension verdicts, and compares them with the withheld labels. It retains
missed defects, false rejections, and unknown control judgments. Any mismatch
leaves the review uncalibrated; the corresponding quality verdict is `UNKNOWN`.
Matching these controls establishes calibration only for this declared set,
not general native-judge accuracy or quality improvement on unseen tasks.

## Verdict and source interfaces

`scripts/domain_quality.py` exposes:

```python
validate_rubric(rubric, criterion_id="accept", artifact_id="draft")
package = load_package(context, "gold", "accept", "draft")
prompt, control_aliases = review_prompt(package, bindings)
result = derive(package, target_assessment, normalized_control_assessments, context=context)
verdict = rederive_review(quality_data, context, native_request)
```

`assess(rubric, assessment, documents, context=context)` is also available to
domain consumers. With a live context, every supplied task, source, and target
document must match its current registered identity, digest, and UTF-8 bytes.
Consumer criteria add `receipt_id` and `check_id`; the evaluator invokes the
existing receipt verifier, checks current specification/program/output bytes,
requires the execution's input digests to cover those same assessed documents,
and recomputes the executed expected-versus-observed comparison. A consumer
receipt cannot certify a different target or a source added after execution.
The native prompt also carries each available consumer program and specification
from the current registry. Review their adequacy: a hard-coded result or a check
that never reaches the requested entry point is a substantive defect even if
its comparison passes. Such a finding can cite the exact program/specification.
A process result does not prove independent test design or task coverage.

Each rich review binds the selected method resource in its existing owning
skill by owner name and content digest. The prompt uses that exact method; a
changed method invalidates the old review instead of silently adopting a new
standard. This provenance appears as `domain_review.method_provenance`.

Live source verification and workflow grading rederive the target assessment
and calibration from current registered bytes, including actual consumer
context. Semantic control results never replace executed acceptance. A `calibrated` or `passed` flag
cannot substitute for this work. Distinct native reviewer identity establishes
role separation; shared sources, rubric, or model can still produce correlated
errors. Source authenticity and factual correctness remain separate questions.

Codex review items must occur strictly between the single thread start and
successful turn completion. A supplied `turn.started` must occur once inside
that interval and precede every item. Retained streams without that marker use
the explicit thread start as their lower bound. An answer outside the completed
interval is rejected before any quality observation can be produced.

The typed observation preserves criterion and dimension `PASS`, `FAIL`, and
`UNKNOWN`. Cited contradictions and substantive defects defeat a passing vote.
Missing support, unsupported execution/readback, and an unexplained rejection
remain unknown. A rejection supported only by optional preferences cannot veto
otherwise supported work. Mixed criteria retain their individual verdicts;
a substantive failure makes the combined result fail while preserving unknowns.

`workflow.quality_receipt_verdict(data, independent, context)` is the live grade
seam. Its context-free form interprets a previously source-verified, immutable
historical observation during repair; it does not try to revalidate old output
as current bytes. Old grades, fingerprints, and negative evidence remain intact.
The existing retry and quality-round limits are unchanged.

## Controller routing and evidence limits

The ordinary controller reports the selected family, method owner, required
dimensions and accepted criteria in `coverage.domain_quality`. The agent builds
the task-specific rubric from the user's accepted requirement and brief; it
must not populate generic requirements merely to satisfy a schema. The selected
method is loaded from the existing owner rather than duplicating domain
methodology in autopilot. Availability in this view is not native qualification.

The `project` workflow family is admitted alongside software, research, writing,
data and browser. At project-domain start, the controller obtains the existing
PM claim-ownership observation. Its receipt is revalidated by the exact active
native seat and claims before project ownership can pass. Obligation preservation
and causal recovery still require their declared consumers; a valid claim alone
does not establish whole-project readiness.

During finish, typed domain reviews remain attached to their actual consumer
checks. A later generic consumer projection cannot replace semantic acceptance.
Fresh contradictory execution prevents closure and retains the failure. Repairs
use the existing workflow quality-resolution owner: exact prior grade and
receipt fingerprints, changed relevant artifact, current re-observation,
remaining resources and preserved history. A new reviewer or renamed receipt
does not justify another round. Productive evidence can continue within the
existing budget; unchanged failures cannot reset it.

Browser account readback has no connected authenticated owner in this package.
Target identity, stored target state and excluded-item preservation therefore
remain `UNKNOWN`, even when the interaction-usability controls pass. A local
file, a success banner or synthetic account data cannot certify those results.
A target adapter must supply actual current account/object-bound evidence and
positive/negative acceptance for its declared surface before closure can pass.

The retained tests use synthetic semantic judgments and native event shapes,
real isolated PM/Git ownership, and actual OS-sandboxed consumers. They exercise
all six controller routes, currentness, source and method tampering, preserved
negative evidence, substantive seeded defects and false rejection of sound
creative voice. These source-level checks do not establish native reviewer
accuracy, production browser account state, held-out task-quality gains or
comparative superiority. Those remain explicit qualification obligations.
