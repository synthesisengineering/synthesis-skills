# Software outcome review

Trace the requested user entry point through the actual consumer. Identify the
accepted input, the changed behavior, the observable output and the failure
behavior before judging a patch. A module test does not establish that a CLI,
service endpoint or installed integration calls that module.

For functional correctness, run the public path against a useful positive
case. For consumer integration, retain the invoked entry point and its actual
output. For adverse inputs, exercise the cases that could change the user's
outcome: invalid values, missing dependencies, partial writes, cancellation,
repeated requests or concurrent ownership, as the task requires. Compare the
observed result with an expectation derived from the requirement. An assertion
that duplicates the implementation is weak evidence even when it executes.

Inspect the supplied consumer program and specification. Reject a hard-coded
success, a disconnected import, a test that never reaches the changed path, or
an expectation that restates the defect. The review request includes those
current bytes so this inspection is possible. A successful process establishes
only its declared comparison; adequacy remains a review judgment.

Judge maintainability against the task: clear ownership, comprehensible control
flow and the cost of making the next foreseeable change. Do not reject correct,
readable work because it uses a different optional style. A useful sound control
uses a legitimate alternative design. A seeded defect should hide a required
error path or make the public interface call unchanged code. Bind every finding
to the requirement and current source, retain failed evidence, and recheck a
repair through the original consumer. Calibrated semantic judgment and executed
behavior remain separate dimensions of acceptance.
