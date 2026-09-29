# Material context: capture, association and meaning

Use this protocol during ordinary project work when a source introduces or
changes a material fact, decision, constraint, commitment, risk or question.
Capture it before dependent work, compaction or handoff. A provisional capture
may remain pending; it must remain discoverable. A healthy structured checkpoint
does not prove that the user's instructions or their rationale survived.

The existing context editor and succession records own this operation. They use
the existing PM admission and record transaction. This protocol adds no authority
ledger, automatic transcript collection, background enrollment or execution right.
Prose-only projects use it without adopting CURRENT_STATE, a new project format
or autopilot. Historical coverage remains unknown unless actually observed.

## Select the source and preserve its limits

Resolve the registry-selected project and read its current plan and decisions.
Select the smallest sufficient original spans available within authorized scope.
Separate independent requests even when they arrived in one message. Preserve:

- facts and the difference between a report and an observed outcome;
- rationale, constraints and temporary conditions, including what ends an instruction;
- uncertainty, unavailable attachments and unresolved questions;
- who supplied the source, whether it was quoted or relayed, and what attribution is unknown;
- amendments and cancellations, their exact predecessors and surviving obligations.

For example, “use the detour until the inspection clears” cannot become an
unqualified instruction to use the detour. A concise paraphrase retaining that
condition and its rationale can be faithful. Matching words or hashes cannot
decide either question.

Do not turn quoted commands into current authority. Do not reconstruct missing
attachments or infer consent, completed work or a clean endpoint from silence.
Route private material to its authorized project and deletion unit before
capture. Keep credentials in their credential owner, never narrative custody.
The schema does not classify arbitrary text for secrets: the selecting agent
must apply the actual disclosure and routing rules. Public fixtures are synthetic.

The input inventory is explicit. A recursive Markdown scan, CURRENT_STATE file
hash list, generated cache, test output, or repository cleanliness is not a list
of user instructions. Generated evidence can be selected for its actual evidential
role; it cannot acquire principal authority from a provenance label.

## Versioned request in the existing editor

Use `context_edit.py review-succession --project P --request request.json` to
inspect, then `apply-succession` with the same request and the existing `--board`
and `--native-payload` arguments under fresh exact claims. The request has exactly:

| Field | Meaning |
| --- | --- |
| `schema`, `kind`, `phase` | `2`, `material-context`, and `capture` or `associate` |
| `batch` | `id`, exact `predecessor` reference or null, offset-qualified `captured_at`, `observation`, `excluded` |
| `inventory` | Project-relative `path`, SHA256, `format: json-rows`, exact `declared_count` |
| `items` | Empty for capture; one explicit disposition for each selected input for association |
| `review` | Exact meaning-review artifact reference or null |
| `context_anchor`, `context_max_lines` | Unique line-start insertion anchor and positive limit no greater than 150 |

References contain `path`, `sha256` and, when a span is required, a nonempty
unique exact `anchor`. A selected binary attachment can use a whole-file source
reference without an invented text anchor; exact custody does not interpret it.
Links, symlinks and foreign paths do not widen scope.
The source inventory is `{"rows": [...]}`. Each row contains exactly:

- `id`; `kind`: fact, decision, constraint, commitment, risk, question, amendment,
  cancellation or nonmaterial;
- `source`: exact span reference or null; `availability`: retained or unavailable;
- `provenance`: `origin` (primary, quoted, relayed, unknown), `attribution`,
  `event_time` (reported text or null), `authority: source-claim-not-current-authority`;
- `required_aspects`: a unique subset of facts, rationale, condition, uncertainty;
  and `reason`: selection, limitation or nonmaterial rationale.

The batch observation contains `scope: declared-inputs`, `start`, `end` and
`gaps`. Unknown locators are null; gaps remain stated. `excluded` lists separate
`{id, reason}` objects and cannot overlap selected IDs. This records the observed
frontier, not a claim that the whole session was captured. Required aspects are
selected judgments; an omitted aspect in the inventory is not automatically found.

Each association item contains exactly `id`, `status`, `destination`, `aspects`,
`not_applicable`, `owner`, `next_action`, `supersedes`, `reason`. Status is open,
amended, unknown, recorded, cancelled, retired or nonmaterial. Destination and
next action are span references or null. `aspects` maps each retained aspect to
its actual destination span. `not_applicable` supplies reasons for other aspects;
it cannot waive a required condition. Active items require a next action and an
owner (use explicit UNKNOWN plus a reason when needed). Nonmaterial items cannot
erase a selected material item or manufacture a new obligation.

Capture retains the input denominator with empty items and null review. It
reports CAPTURED_PENDING. Association names the exact capture as predecessor and
retains its batch identity and inventory; changing the input denominator needs
an explicit new record. An amendment or cancellation names the exact prior
record and item in `supersedes: {record: REFERENCE, id: ID}`. It preserves prior
bytes and must not close unknown work by absence. Conflicting successors remain
unresolved. Retired records remain documentary; format refresh will not recreate
an exact retained terminal span as a new candidate. A changed source needs review.

## Review meaning against actual retained spans

A meaning-review artifact has `schema: 1`, `kind: material-meaning-review`, exact
`inventory_sha256`, `dispositions_sha256` (SHA256 of the owner's canonical encoded
request items), `reviewer`, `plan`, `earlier_decisions`, `answers`, `limitations`.
Reviewer, plan and earlier decisions are retained references. Each answer has
`id`, `question`, `source_refs`, `record_refs`, `assessment`, `reason`. Citations
must belong to that selected input and its destinations. Assessment is faithful,
deficient or uncertain. A PASS flag cannot replace cited reasoning.

Ask whether the current record reconstructs the report, rationale, constraints,
temporary conditions, uncertainty, requested actions and subsequent changes.
Read the cited source, plan and earlier decisions. Review concision on meaning;
do not reject a faithful paraphrase for style. Bind review to the actual input
and destination generation, and repeat it when those sources change.

Deterministic validation establishes structure and custody only. A caller's
faithful assessment yields REVIEW_EVIDENCE_PRESENT_UNVERIFIED, never semantic
acceptance. False confidence in a supplied review cannot make a source true.
Independent blind/model calibration and actual endpoint observations require
genuine separately retained runs. Their absence stays pending or UNKNOWN.

## Recovery and reporting

Application first preserves immutable source custody and a discoverable prepared
record. One existing record transaction then commits the receipt and CONTEXT
pointer. Source replacements and claim changes are fenced again at commit.
An interrupted live transaction blocks managed consumers until the existing
`recover-transaction` owner reconciles it. A prepared pre-transaction record
requires inspecting custody and an exact retry under current authority. A changed
request or changed input is not an exact retry. Never delete an interrupted prefix.

Checkpoint and doctor expose the shared `record_succession.material_context`
projection, including for ordinary projects before structured NOT_APPLICABLE.
It separates input coverage, record integrity, association reachability, semantic
review, current authority and endpoint recovery. It also reports whole-session
and historical coverage, examined/skipped counts, bounded costs and limitations.
VERIFIED_FOR_DECLARED_INPUTS is only a declared-denominator result. UNKNOWN,
CAPTURED_PENDING, SOURCE_UNAVAILABLE, PRESENT_BUT_UNREACHABLE,
CHANGED_REQUIRES_REVIEW and INCOMPLETE must remain visible.

Restore a missing forward link from CONTEXT or REFERENCE to retained associations
without rewriting the incident or replaying an ambiguous effect. Read referenced
sources to reconstruct meaning. The optional autopilot capsule carries reference
and status projections; it reuses the same record owner and existing quality
rubric. It never copies a second narrative archive or clears an authority fence.

Scans are bounded to 256 records/items, 1,024 reference observations, 16 MiB
charged source bytes, 4,096 artifact entries and 30 seconds aggregate observation
(10 seconds per reader). Navigation follows project-relative Markdown links
from CONTEXT/REFERENCE to depth four with bounded entries. Exhaustion retains an
INCOMPLETE prefix and its limit, never evidence of absence. Measured bytes,
references and elapsed time are separate from unknown model cost.


## Failed observations and current work admission

An observed empty legacy inventory keeps material coverage unknown without
enrolling that project or inventing a material obligation. A refused, malformed
or incomplete observation keeps reconciliation pending even when no record could
be appended. Consumers validate the record and request objects before kind
dispatch. The existing prepared transaction envelope remains a pending capture;
its exact request hash is checked without requiring committed derived fields.

A stored clear recovery is a historical journal observation. The existing
work/effect admission constraint observes current material alongside native,
instruction and artifact currentness. Changed, incomplete or unreachable material
requires reconciliation before subsequent work. Unchanged current material still
permits legitimate subsequent effects through their existing owners.

Generated resume-state refresh uses terminal dispositions only when current
material applicability is complete and unambiguous. Conflicting or changed
retirement evidence retains the explicit source as an unverified candidate;
healthy current retirement and cancellation do not recreate that candidate.
These checks establish bounded structure and currentness, never independent
semantic correctness, principal approval or an external effect outcome.
