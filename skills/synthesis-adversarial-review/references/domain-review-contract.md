# Domain review package

Use `scripts/review_contract.py` for every closed review package. Keep the existing
finding ledger, approval owner and execution journal as the state owners; this
package is a bounded source-binding diagnostic, never a second authority store.
Run the release-verified entrypoint with the exact package root and bundle path.
Its success means structure and current source bytes match. It does not mean
observations are true, a person is authenticated, review is sufficient, or any
publication is authorized. The existing effect owner must check its own receipt.

## Four profiles and seven records

Choose editorial, code/control, research, or operations/compliance before work.
`profiles.json` lists the required planes. The seven schema files describe
provider-neutral target, claim, finding, evidence, decision, handoff and terminal
result records. `review_contract.validate` checks raw unique identities before
aggregation, cross-record references, current source bytes, target fingerprints
and distinct destination outcomes. Unknown fields and malformed paths refuse.
A finding refers to the existing ledger ID; a decision refers to its actual
owner receipt. JSON schemas aid interchange; the production validator and the
native effect owner remain mandatory, and schema validation alone grants nothing.

Freeze the full artifact × plane matrix in the review target. Each assigned cell
needs an explicit terminal disposition, including absent evidence. A source
snapshot is not proof its producer works. Native capability and release-history
evidence are different. The reviewer derives load-bearing facts independently;
copied receipts do not establish independence. A handoff identifies the receiver,
not a claim that a listed producer's work is the receiver's observation.

## Mechanical controls and their limits

- `instrument_inventory` examines Python, JavaScript, C and shell files plus
  executable files regardless of filename. Declare producer/validator/test/build/
  fixture roles and a terminal result for every discovered instrument. Missing
  declarations or changed source refuse. Discovery itself executes no script.
- `content_checks` keeps source scaffolds, required rendered content, attribution
  directives and actual named-entity presence independent. It reports candidates;
  a source sentence or keyword match cannot settle an editorial judgment.
- `calibration` requires positive and negative controls and preserves errors or
  missing runs. Uniform failures do not prove the target is defective.
- `corpus_key` changes on source bytes, population and publication disposition.
  A title/headline change must also invalidate the unpublished URL-identity plane.
- `publication_diagnostics` separates each destination's observed bytes from
  the approved bytes. Matching bytes grant no authority. Use actual origin and
  rendered checks, including retired-route identity, before a publication result.
- `saved_outputs` opens the named saved files and retains every prior-output
  disposition. Input parsing cannot prove generated-output attribution.
- `lifecycle_scopes` never collapses exact-session state, aggregate hygiene,
  communication delivery and continuity into one readiness label.
- `custody_scope` keeps durable deletions and disposable fixtures separate.
  Actual move/delete authority and old custody proof belong to their owners.

Every source read is bounded, no-follow and identity checked. A validation has a
64 MiB aggregate read budget and a ten-second deadline; target and evidence bytes
are checked again before success. An exceeded budget refuses, never truncates. Instrument discovery
has finite entry/time bounds. Large histories use the existing archive owner;
do not raise this diagnostic's limit or reinterpret truncated data as complete.

## Ten retained replay shapes

The shipped test corpus retains independent controls for: uniform failure of 60
cases; durable versus disposable paths; exact-session readiness with aggregate
open work; delivered board message with incomplete continuity; a 455-item corpus
changed by 30 publications; mixed automatic/manual destination outcomes; approval
versus actual bytes; independently derived reviewer inputs; destination-relative
handoff links; and exact saved output with prior custody. Historical incidents
remain private evidence. Synthetic replays do not reclassify original failures.

## Twelve lessons and the acceptance scorecard

1. Artifact readiness and publication are distinct; enumerate destinations.
2. Reviewers derive facts and test both false positives and false negatives.
3. Validate real destination topology and each outcome.
4. An owner transition preserves source/approval provenance; no silent adoption.
5. Corpus mutation invalidates earlier counts and dependent receipts.
6. Preserve durable custody separately from disposable temporary files.
7. Exact-session readiness does not close other manifests or owners.
8. Message delivery is not lifecycle completion.
9. Post-publication review is bounded; reopen only on new concrete counterevidence.
10. Approval is exact, scoped and consumed by the actual action owner.
11. Relative links resolve from their actual destination, not the author's cwd.
12. Verify generated outputs, not only command inputs.

For each lesson record source, changed owner, causal fixture, actual observed
result and remaining native/human boundary. Keep immutable snapshots; cover all
planes in one round; preserve reviewer reproductions during repair; label content,
control and platform separately; carry one structured decision packet; stop at the
recorded sufficiency ruling without inflating permissions. Serious incidents get
replayed against the original principal outcome. Native Claude/Codex comparisons
and same-agent replay must report actual runs rather than synthetic labels.

`scorecard` records principal sittings, rereads, duplicate work, elapsed target
seconds, severity found, repair defects and omitted planes. Missing observations
remain null. No universal superiority, model compliance or token savings follows
from fixture success. Keep executor, reviewer and adjudicator in the current
single skill per the saved packaging decision; split only with new role-confusion
or size evidence showing that packaging is the repair. This package introduces
referenced protocols and typed data, not a redundant review lifecycle engine.
