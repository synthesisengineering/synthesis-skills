# Decisive uncertainty and observation

Record an uncertainty when resolving it could change the next decision or a
required acceptance result. Name the decision, why this fact matters, the
different consequences of the plausible answers, and the cheapest credible
observation that distinguishes them. A list of everything not known creates
work without improving the result.

For a diagnosis, write a falsifiable hypothesis and its predicted observation
before changing the implementation. Preserve a refuted hypothesis and its
evidence. For research, bind the decisive claim to primary sources and
counterevidence. For creative work, compare alternatives against the reader's
purpose and voice. These methods share a decision boundary, not one generic
test. Do not replace missing domain evidence with a confidence number.

## Admitted local observation

When an autopilot run can answer the question through a registered local
consumer, use the existing controller and journal. The controller owns no
second question database. Record `kind: uncertainty` with this `question`:

```json
{
  "id": "missing-values",
  "decision": "Choose the report's denominator",
  "why_decisive": "Counting missing rows would change the recommended mean",
  "if_supported": "Retain the observed-value calculation",
  "if_refuted": "Repair the denominator and rerun the original consumer",
  "affected_criteria": ["report-correctness"],
  "observation_check_id": "mean-check",
  "cost_rank": 1,
  "expected_supported": {"mean": 3, "coverage": "2/4"},
  "expected_refuted": {"mean": 1.5, "coverage": "2/4"}
}
```

The question binds the run and the exact affected criterion definitions. The
check and program must already be registered inputs for an affected criterion.
`cost_rank` is a declared relative ordering of credible observations, not a
measured price or an invented confidence score. Actual usage remains with the
resource owner. Distinct branches and predictions are required. Adequacy of the
hypothesis and test remains a judgment that can be challenged with evidence.

Run the actual consumer through the existing observation path. Then record
`kind: uncertainty_observe`, the question `id`, and its `receipt_id`. The owner
reopens the current specification, program, target and all recorded execution
inputs. It verifies receipt identity and scope, bounded sandboxed execution and
the actual output. It chooses `supported` or `refuted` by exact comparison with
the two predictions. The caller supplies neither the branch nor a PASS flag.
A healthy execution that disproves the check's original expectation can resolve
the question as refuted; its failed acceptance verdict remains unchanged.

An observation matching neither prediction leaves the question open. This is
new evidence about the hypothesis, not permission to select the convenient
branch. A missing source, changed program, stale output or unauthenticated
receipt also leaves it open. A source quotation alone cannot resolve a semantic
or external-state question through this local execution adapter.

## Admission, steering and capture

The controller reports open questions in declared observation order. Tasks
whose acceptance criteria depend on an unresolved question cannot start, retry
or complete. Independent task criteria remain available. Direct verification
and completed closure use the same guard; cancellation and incomplete closure
remain available. This prevents a direct engine call from bypassing the
controller's display. It does not turn every question into a Stop correction
or reset existing failure and resource histories.

Changed observed inputs reopen the recorded affected acceptance closure. An
unrelated criterion does not change the question's semantic identity, though
the evidence owner may still require fresh receipts for an amended contract.
When the question or its affected requirement changes, record
`kind: uncertainty_revise` with `id`, `expected_question_digest`, the new
`question`, and the material `reason`. Obtain the digest from the current
controller view. The owner retains the earlier question, exact negative or
positive proofs and revision reason; unchanged revisions and stale amendment
bases are rejected. It clears only that question's current resolution, never
its history. History bounds prevent relabeling an endless investigation as new
work.

The profile owner captures a resolved local diagnostic decision with its
question, distinct prediction, current executed observation and consequence.
This satisfies only that diagnostic capture. Research, high-uncertainty
recommendations, explicit semantic criteria and other material decisions retain
their existing semantic evidence requirements. Stored fields do not establish
that a recommendation is wise or an external account changed.

Stop investigating when the required observation and acceptance result resolve
the decision. Continue when a new source, a changed output, a disproved premise
or a concrete acceptance failure warrants it. Report the conclusion, evidence,
tradeoff and consequence. Keep private reasoning private.
