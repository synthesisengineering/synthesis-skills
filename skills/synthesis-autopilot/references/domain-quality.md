# Task-specific domain review

The domain rubric binds a review to the accepted criterion, output, task brief,
and source artifacts. Every declared criterion is mandatory. The evaluator
checks coverage and exact quotations; a qualified reviewer still determines
whether the quoted evidence supports the claim. A valid quote is evidence of
presence, not entailment.

The writing and research route runs through the existing native CLI observer.
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
mapping **every family dimension** to `PASS` or `FAIL`. Supply one sound control
and seeded defects covering every dimension. For writing, the sound control
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
result = derive(package, target_assessment, normalized_control_assessments)
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
A process result
does not prove independent test design or that the check covers the task.

Live source verification and workflow grading rederive the target assessment
and calibration from current registered bytes. A `calibrated` or `passed` flag
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

## Remaining integration and evidence limits

Writing/research native routing and rich workflow grading are connected in
this package. Six-family rubric validation and direct consumer assessment are
available. General task admission, automatic rubric selection, six-family
controller routing and closure, and evidence-based repair policy remain A2/A3
integration obligations.

Target/account readback has no connected owner in this domain interface. Those
criteria return `UNKNOWN`; a no-tools reviewer cannot certify them. Completion
requires the appropriate native readback adapter to bind actual target identity,
stored state, current receipt provenance, and preservation evidence. A local
file readback cannot stand in for a browser account result.

The retained tests exercise synthetic task judgments, actual native event
parsers, source verification, workflow grade/repair boundaries, and an actual
sandboxed Python consumer that catches a wrong denominator. They do not run a
paid model experiment or establish native judgment quality. Held-out native
acceptance and comparative benefit remain evaluation obligations.
