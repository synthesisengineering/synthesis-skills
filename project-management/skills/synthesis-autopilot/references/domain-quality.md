# Domain acceptance

What each kind of work must pass before it counts as accepted, and which kind of
evidence settles each question. The table is the 3.x family contract; the
typed rubric engine that enforced it was cut, and its full text is in
[preserved-review.md](preserved-review.md#task-specific-domain-review).

## Family contracts

| Family | Mandatory dimensions | Evidence method |
|---|---|---|
| Software | `functional_correctness`, `consumer_integration`, `adverse_inputs`; `maintainability` | Executed consumer for the first three; judgment for maintainability |
| Research | `sources_verified`, `decisive_claims_verified`, `counterevidence_checked` | Source-backed judgment |
| Writing | `source_fidelity`; `reader_purpose`, `structure`, `voice` | Source-backed fidelity; task-specific judgment for the remaining dimensions |
| Data | `arithmetic_and_denominator`, `coverage_and_missingness`, `transformation_lineage`; `reader_usability` | Executed consumer for the first three; judgment for usability |
| Browser | `target_identity`, `stored_target_state`, `excluded_item_preservation`; `interaction_usability` | Target readback for the first three; judgment for usability |
| Project | `obligation_preservation`, `causal_recovery`; `ownership_integrity`; `handoff_usability` | Consumer; target readback; judgment, respectively |

"Executed consumer" means running the real entry point the work serves (the
test suite, the CLI, the importer) and reading its actual result. "Target
readback" means reading the system that was changed (the account, the page, the
repository) after the change. "Judgment" is a reviewer's assessment against the
task's own requirement.

## How to use it

- In the plan's completion criteria, write each relevant dimension as a
  criterion in the task's own terms, with its reader or operator purpose and the
  evidence that would settle it. Several criteria may assess one dimension.
  A mixed task (writing plus software) needs both families' checks.
- A judgment cannot stand in for an execution check, and an execution check
  cannot stand in for a required judgment. A consumer or readback dimension
  without its actual execution stays UNKNOWN, however good the review.
- A valid quote is evidence of presence, not entailment: a reviewer still has to
  establish that the quoted source supports the claim.
- A hard-coded result, or a check that never reaches the requested entry point,
  is a defect even when it passes.
- Defects name a broken requirement or concrete reader harm; preferences name
  optional taste and do not veto supported work. An explicit voice requirement
  in the task is enforceable as a defect.
- When calibrating a reviewer on sound and seeded-defect examples, the sound
  example keeps the desired voice; a generic preference for standardized prose
  must not make it fail. Matching such controls shows calibration on that set
  only, not general reviewer accuracy.
- Browser and account work stays UNKNOWN on its first three dimensions until
  something reads the actual account or object back. A local file, a success
  banner or synthetic data cannot certify them.
- The table does not replace the domain's own workflow. Writing still uses
  reader briefing, framing, article writing where it applies, fact-checking,
  content quality, craft, pitfalls and the user's authorized voice profile.
  Research still requires primary sources and counterevidence. Public defaults
  do not import any particular user's taste or private material.
