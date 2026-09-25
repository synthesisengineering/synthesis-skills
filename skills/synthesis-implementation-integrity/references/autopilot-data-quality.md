# Data and document outcome review

Define the requested measure, population, units, time interval and reader's
decision. Recompute using source values. State whether missing values are
excluded, imputed or counted, and show the resulting denominator and coverage.
A correct sum over the wrong population does not answer the question.

The executed consumer should verify the task's critical arithmetic, joins,
filters, units and transformation lineage. Include the source identity or digest
that makes the output reproducible. Preserve excluded rows and account for
unmatched and duplicate keys. Review the actual consumer program and its expected
result; a fixed number, matching row count or shallow existence check cannot
prove these properties. Choose adverse data that exposes the relevant defect.
For example, a mean over two observed values and two missing values distinguishes
a valid denominator of two from an invalid denominator of four.

Evaluate reader usability separately: the display must make the denominator,
uncertainty, units and practical conclusion understandable. A sound compact
report need not become a longer dashboard. Seed a semantic defect that obscures
the population or changes the reader's interpretation despite correct numbers.
For spreadsheets, PDFs or rendered documents, use their owning format tools and
inspect the actual exported or rendered consumer when that is part of the task.
A text-only judgment does not certify rendering or application behavior.

Re-run the original consumer after a changed source or repaired transformation.
Retain the earlier result and its source lineage. Source quotes establish which
bytes were reviewed; they do not independently establish statistical validity.
