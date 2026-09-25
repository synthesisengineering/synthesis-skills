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
