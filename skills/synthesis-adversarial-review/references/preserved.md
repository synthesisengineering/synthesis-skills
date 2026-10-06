# Adversarial review: preserved text

Contents:
- Why these passages were retired
- SKILL.md 2.0.0: the opening sentence, the binding-rules preamble, rule 10, the ledger command
- references/protocol.md: the 1.2.1 "Finding Ledger" section
- references/domain-review-contract.md: the whole 1.2.1 file
- references/profiles.json and references/schemas/: a summary

Text retired on 2026-10-05 with the three scripts it described. Verdicts from the
v5 code evaluation (`tool-scripts.md`, synthesis-adversarial-review rows), all CUT:

- `finding_ledger.py` (534 lines): "It serves the old review-and-release loop; v5
  principle 1 rules out ledgers; a markdown findings table does the job."
- `protocol_acceptance.py` (195 lines): "v5's skill-format checker covers skill
  structure."
- `review_contract.py` (831 lines): "No content-work use found; serves the
  autopilot review machinery."

Their rules survive as prose: the findings table in references/protocol.md
("Finding Ledger"), and the checks a reviewer applies by hand in
references/domain-review-contract.md. Everything below is verbatim, with the file
it came from.

## SKILL.md 2.0.0, opening and Binding rules preamble

Before freezing or accepting a package, apply the mandatory [domain contracts and replay scorecard](references/domain-review-contract.md); validate exact source bindings with `scripts/review_contract.py` and retain the existing ledger/action owners.

The headings below are the protocol's sections, in the order `scripts/protocol_acceptance.py` checks. [references/protocol.md](references/protocol.md) holds each section in full.

## SKILL.md 2.0.0, binding rule 10

10. **One ledger per engagement, edited only through `scripts/finding_ledger.py`** (command below). Each finding carries a state, a classification, an authority label, a separate enforcement outcome, evidence, and a follow-up project when ship-improving.

## SKILL.md 2.0.0, "Finding ledger command"

## Finding ledger command

Create one YAML ledger per engagement in the owning project's `resources/` directory:

```bash
python3 scripts/finding_ledger.py init \
  --resources-root resources \
  --file resources/<engagement>-findings.yaml \
  --engagement <id> \
  --principal-outcome '<outcome>' \
  --round-trip-budget <count> \
  --proportionality 'AGENT HEURISTIC: <bounded rationale>'
```

Use `validate` before every handoff.

## references/protocol.md, "Finding Ledger" (1.2.1)

## Finding Ledger

Create one YAML ledger per engagement in the owning project's `resources/` directory:

```bash
python3 scripts/finding_ledger.py init \
  --resources-root resources \
  --file resources/<engagement>-findings.yaml \
  --engagement <id> \
  --principal-outcome '<outcome>' \
  --round-trip-budget <count> \
  --proportionality 'AGENT HEURISTIC: <bounded rationale>'
```

Each finding must carry:

- one state: `open | challenged | repaired-prose | repaired-source |
  repaired-verified | conceded | awaiting-principal`;
- one classification: `ship-blocking | ship-improving`;
- an authority label: `principal-rule | agent-heuristic`, plus a provenance id;
- an enforcement outcome in a separate field;
- evidence and an append-only transition history;
- a follow-up project when classified `ship-improving`.

The authority label and enforcement outcome answer different questions. `AGENT HEURISTIC`
may be the honest provenance label while enforcement is still wrong. Exercise every report
branch and verify finding, authority, and enforcement outcome independently.

Ledger edits are compare-before-write operations. `transition` requires the recorded prior
state; missing or duplicate ids, stale expected state, unknown keys, invalid classification,
and symlink targets refuse without writing. Every command requires the owning project's
literal `resources/` root, rejects a target outside it or any symlinked path component, and
holds the resources-directory lock across read, expected-state comparison, replacement,
and read-back. Use `validate` before handoff.

Acceptance manifests label each case `diagnostic | acceptance-test | enforced-gate`.
Section-shape and vocabulary checks are diagnostics, not behavioral acceptance. A manifest
does not issue an authority receipt. Native agent scenarios establish protocol behavior;
only a fail-closed caller at the state-changing boundary can claim an enforced gate.

## references/domain-review-contract.md (1.2.1, the whole file)

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

## references/profiles.json and references/schemas/ (summary)

`profiles.json` (schema 1) listed the four profiles' planes, now the profile table
in references/domain-review-contract.md, and seven scorecard metrics:
principal_sittings, rereads, duplicate_work, elapsed_target_seconds,
severity_found, repair_defects, omitted_planes. The seven JSON schemas
(`claim`, `decision`, `evidence`, `finding`, `handoff`, `target`,
`terminal-result`) required the fields now listed in that file's records table.
The JSON files themselves stay readable at `origin/main`.
