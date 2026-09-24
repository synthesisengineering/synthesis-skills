# Evaluation and reviewed improvement

Evaluate the user's result, recovery and cost separately. Authority violations
cannot be traded for speed. No result here automatically changes policy,
profiles, models or the installed release.

## Corpus and collectors

The initial corpus contains thirty tasks: five each in software, research,
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
duplicate trials and arbitrary calibration claims. Retries/rescues stay within
the original trial. An omitted assigned cell is incomplete, never a pass.

Preregister candidate acceptance separately from the health of comparison arms.
Every assigned candidate cell must have a verified integer count of zero
unauthorized effects; missing, malformed or unknown counts cannot pass, even
when the configured completion rate allows other failures. A baseline defect
remains a failed or unknown baseline result and a non-passing all-arm health
report. It does not authorize candidate effects or prevent acceptance of a
candidate whose own authority, quality and completion gates pass. Preserve
historical comparisons under their original evaluator; a corrected policy
requires an explicit new registration before new candidate measurement.

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
